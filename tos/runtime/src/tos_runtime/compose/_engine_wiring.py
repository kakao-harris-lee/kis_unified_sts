"""``tos_runtime.compose`` engine-driver wiring — TOS Phase 3 Wave 1 Lane A-R."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from tos.brokeradapter import Transport
from tos.canonical import CanonicalizationScheme
from tos.egressgw import BrokerEgressGateway
from tos.engine import (
    CommitmentStep,
    EngineConfiguration,
    EngineCore,
    InstrumentKey,
    NullEvidenceSink,
    ProvisionalReservationLedger,
    Stage,
    StrategyRegistry,
)
from tos.workload import RuntimeIdentity

from tos_runtime.authority.epoch import SafetyAuthorityEpochService
from tos_runtime.brokercap.instance import InstanceDocument
from tos_runtime.brokercap.scopes import BrokerScope
from tos_runtime.compose._boot_integrity import (
    EngineReplayDiverged,
    verify_engine_replay_or_halt,
)
from tos_runtime.compose._posttrade_source import (
    broker_posttrade_enabled,
    finality_producer_for,
)
from tos_runtime.compose._preconditions import (
    RuntimeCoordinatorPreconditions,
    _ReplayPreconditions,
)
from tos_runtime.compose._transport_wiring import (
    SealRegistry,
    TransportKind,
    build_transport,
)
from tos_runtime.compose.context import ComposeContextResolver
from tos_runtime.custody.ports import CredentialCustody
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.engine.orthostate_projection import OrthostateProjector
from tos_runtime.engine.replay import ReplayVerdict
from tos_runtime.engine.replay_releases import RclCommitted
from tos_runtime.engine.replay_stage import EventCorrelatingCore, RecordedStage
from tos_runtime.engine.replay_transmit import RecordedTransmit, any_recorded_hand_off
from tos_runtime.evidence.emergency import EmergencyAppendLog, record_halt
from tos_runtime.evidence.sinks import (
    EngineEvidenceSinkAdapter,
    GatewayEvidenceSinkAdapter,
)
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.config import FinalityConfig
from tos_runtime.rcl.obligation import CapacityObligationRecorder
from tos_runtime.rcl.projection import SqliteReservationProjectionReader
from tos_runtime.rcl.reservation_lookup import reservation_id_for_attempt
from tos_runtime.recovery.composite_state_writer import (
    COMPOSITE_STATE_STORE_FILE_NAME,
    CompositeStateWriter,
)
from tos_runtime.time.sources import MonotonicSource
from tos_runtime.transport.kis_mock.config import KisMockTransportConfig
from tos_runtime.transport.kis_mock.credential_session import KisCredentialSessions
from tos_runtime.venue_ledger.synthetic import SyntheticVenueLedger

__all__ = [
    "ENGINE_DRIVER_CONFIG_NAME",
    "INBOX_FILE_NAME",
    "REPLAY_VERDICT_IDENTICAL_KIND",
    "EngineDriverConfig",
    "EngineDriverConfigError",
    "WiredEngine",
    "build_engine_driver",
    "load_engine_driver_config",
    "verify_replay_or_halt",
    "wire_engine_and_driver",
]

ENGINE_DRIVER_CONFIG_NAME = "engine_driver.yaml"

INBOX_FILE_NAME = "inbox.sqlite3"

REPLAY_VERDICT_IDENTICAL_KIND = "REPLAY_VERDICT_IDENTICAL"

ENGINE_LEDGER_NOT_PRISTINE_KIND = "ENGINE_LEDGER_NOT_PRISTINE"


class EngineDriverConfigError(Exception):
    """Raised when the engine-driver config is missing, malformed, or"""


@dataclass(frozen=True)
class EngineDriverConfig:
    """The one operator-configured engine-driver bound (module docstring)."""

    replay_window_events: int


def _require_positive_int(raw: Any, field: str, path: Path) -> int:
    value = raw.get(field) if isinstance(raw, dict) else None
    if isinstance(value, bool) or not isinstance(value, int):
        raise EngineDriverConfigError(
            f"{path}: {field!r} is missing, still null (named-TBD), or not "
            "an int — refusing to start until an operator supplies a "
            "concrete value"
        )
    if value <= 0:
        raise EngineDriverConfigError(
            f"{path}: {field!r} must be a positive int (got {value!r}) — a "
            "zero/negative replay window is not a smaller window, it is a "
            "silently-disabled one"
        )
    return value


def load_engine_driver_config(path: Path) -> EngineDriverConfig:
    """Load + fail-closed-validate the engine-driver config from ``path``."""
    if not path.is_file():
        raise EngineDriverConfigError(f"engine-driver config file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EngineDriverConfigError(
            f"engine-driver config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise EngineDriverConfigError(
            f"engine-driver config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise EngineDriverConfigError(
            f"engine-driver config file must be a top-level mapping: {path}"
        )
    return EngineDriverConfig(
        replay_window_events=_require_positive_int(raw, "replay_window_events", path)
    )


def build_engine_driver(
    *,
    data_dir: Path,
    core: EngineCore,
    gateway: BrokerEgressGateway,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    scheme: CanonicalizationScheme,
    continuity_id: str,
    monotonic_source: MonotonicSource,
    max_send_result_wait_ms: int,
    finality_config: FinalityConfig,
    authority_epoch_current: Callable[[], bool | None],
    broker_sourced: bool = False,
) -> tuple[SqliteEventInbox, EngineDriver]:
    """Construct the durable inbox and the engine driver, bound to ``gateway``."""
    inbox = SqliteEventInbox(data_dir / INBOX_FILE_NAME, scheme=scheme)
    orthostate_projector = OrthostateProjector(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        authority_epoch_current=authority_epoch_current,
    )
    finality_producer = finality_producer_for(broker_sourced, finality_config, scheme)
    recovery_composite_writer = CompositeStateWriter(
        data_dir / COMPOSITE_STATE_STORE_FILE_NAME
    )
    driver = EngineDriver(
        core=core,
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        scheme=scheme,
        continuity_id=continuity_id,
        monotonic_source=monotonic_source,
        max_send_result_wait_ms=max_send_result_wait_ms,
        orthostate_projector=orthostate_projector,
        finality_producer=finality_producer,
        recovery_composite_writer=recovery_composite_writer,
    )
    driver.bind_gateway(gateway)
    return inbox, driver


def _require_pristine_ledger(
    live_core: EngineCore,
    instrument_key: InstrumentKey,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
) -> ProvisionalReservationLedger:
    """The live core's ledger, for the boot replay to rebuild in place (#944)."""
    ledger = live_core.ledger
    if ledger.outstanding_count(instrument_key) == 0:
        return ledger
    record_halt(
        evidence_store,
        emergency_log,
        payload={
            "account": instrument_key.account,
            "instrument": instrument_key.instrument,
            "detail": "the live engine already holds a reservation before the boot replay "
            "rebuilt it — refusing to add a replay onto a projection it did not derive",
        },
        kind=ENGINE_LEDGER_NOT_PRISTINE_KIND,
        record_class=ENGINE_LEDGER_NOT_PRISTINE_KIND,
    )
    raise EngineReplayDiverged(
        "boot replay refused: the live engine's reservation projection is not empty "
        f"before the rebuild ({instrument_key.account}/{instrument_key.instrument})"
    )


def verify_replay_or_halt(
    *,
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    registry: StrategyRegistry,
    stages: dict[CommitmentStep, Stage],
    configuration: EngineConfiguration,
    scheme: CanonicalizationScheme,
    window_events: int,
    live_core: EngineCore,
    instrument_key: InstrumentKey,
    rcl_committed: RclCommitted | None = None,
) -> ReplayVerdict:
    """Build the side-effect-free replay core factory and run the boot-time replay check, which"""
    ledger = _require_pristine_ledger(
        live_core, instrument_key, evidence_store, emergency_log
    )

    def _replay_core_factory() -> EventCorrelatingCore:
        recorded_stage = RecordedStage(evidence_store)
        core = EngineCore(
            registry=registry,
            stages=dict.fromkeys(stages, recorded_stage),
            configuration=configuration,
            ledger=ledger,
            preconditions=_ReplayPreconditions(),
            transmit=(
                RecordedTransmit(evidence_store)
                if any_recorded_hand_off(evidence_store)
                else None
            ),
            sink=NullEvidenceSink(),
            scheme=scheme,
        )
        return EventCorrelatingCore(
            core=core, recorded_stage=recorded_stage, scheme=scheme
        )

    verdict = verify_engine_replay_or_halt(
        inbox,
        evidence_store,
        emergency_log,
        _replay_core_factory,
        scheme=scheme,
        window_events=window_events,
        rcl_committed=rcl_committed,
    )
    evidence_store.append(
        {
            "total_compared": verdict.total_compared,
            "uncompared": verdict.uncompared,
            "has_unverifiable_receipts": verdict.has_unverifiable_receipts,
        },
        kind=REPLAY_VERDICT_IDENTICAL_KIND,
        record_class=REPLAY_VERDICT_IDENTICAL_KIND,
    )
    return verdict


@dataclass
class WiredEngine:
    """Every artifact :func:`wire_engine_and_driver` assembles — handed straight into"""

    gateway: BrokerEgressGateway
    transport: Transport
    core: EngineCore
    resolved_registry: StrategyRegistry
    inbox: SqliteEventInbox
    driver: EngineDriver


def _build_preconditions(
    authority_epoch_service: SafetyAuthorityEpochService,
    live_authorization_state: str,
    *,
    nonlive_admitted: bool,
    active_scope: BrokerScope,
    instance_document: InstanceDocument | None,
) -> RuntimeCoordinatorPreconditions:
    """The live core's RFC-002 §10.7 Coordinator positive gates (design #31 §9-10; plan §2.1)."""
    return RuntimeCoordinatorPreconditions(
        epoch_service=authority_epoch_service,
        live_authorization_state=live_authorization_state,
        nonlive_admitted=nonlive_admitted,
        active_scope=active_scope,
        instance_document=instance_document,
    )


def wire_engine_and_driver(
    *,
    data_dir: Path,
    context_resolver: ComposeContextResolver,
    identity: RuntimeIdentity,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    projection: SqliteReservationProjectionReader,
    stages: dict[CommitmentStep, Stage],
    configuration: EngineConfiguration,
    registry: StrategyRegistry | None,
    scheme: CanonicalizationScheme,
    continuity_id: str,
    monotonic_source: MonotonicSource,
    max_send_result_wait_ms: int,
    authority_epoch_service: SafetyAuthorityEpochService,
    live_authorization_state: str,
    finality_config: FinalityConfig,
    nonlive_admitted: bool,
    active_scope: BrokerScope,
    instance_document: InstanceDocument | None,
    custody: CredentialCustody,
    transport_kind: TransportKind,
    transport_config: KisMockTransportConfig | None,
    credential_sessions: KisCredentialSessions,
    trading_date_now: Callable[[], str | None] | None = None,
    venue_ledger: SyntheticVenueLedger | None = None,
) -> WiredEngine:
    """The gateway + ``EngineCore`` + durable inbox/driver wiring — split out of ``_wiring.py``'s"""
    instrument_key = context_resolver.instrument_key
    obligation_recorder = CapacityObligationRecorder(
        store=evidence_store,
        emergency_log=emergency_log,
        projection=projection,
        reservation_id_resolver=lambda attempt_id: reservation_id_for_attempt(
            evidence_store,
            projection,
            account=instrument_key.account,
            instrument=instrument_key.instrument,
            attempt_id=attempt_id,
        ),
    )
    seal_registry = SealRegistry()
    gateway_sink = GatewayEvidenceSinkAdapter(
        evidence_store,
        runtime_identity=identity,
        on_refusal=obligation_recorder,
        on_record=(
            seal_registry.capture if transport_kind is TransportKind.KIS_MOCK else None
        ),
    )
    transport = build_transport(
        transport_kind,
        transport_config=transport_config,
        custody=custody,
        monotonic=monotonic_source,
        seal_lookup=seal_registry,
        evidence_store=evidence_store,
        runtime_identity=identity,
        trading_date_now=trading_date_now,
        credential_sessions=credential_sessions,
        venue_ledger=venue_ledger,
    )
    gateway = BrokerEgressGateway(
        contexts=context_resolver, transport=transport, sink=gateway_sink
    )

    resolved_registry = registry if registry is not None else StrategyRegistry()
    engine_sink = EngineEvidenceSinkAdapter(evidence_store, runtime_identity=identity)
    preconditions = _build_preconditions(
        authority_epoch_service,
        live_authorization_state,
        nonlive_admitted=nonlive_admitted,
        active_scope=active_scope,
        instance_document=instance_document,
    )
    core = EngineCore(
        registry=resolved_registry,
        stages=stages,
        configuration=configuration,
        preconditions=preconditions,
        transmit=gateway,
        transport_nature=context_resolver.transport_nature,
        sink=engine_sink,
    )

    inbox, driver = build_engine_driver(
        data_dir=data_dir,
        core=core,
        gateway=gateway,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        scheme=scheme,
        continuity_id=continuity_id,
        monotonic_source=monotonic_source,
        max_send_result_wait_ms=max_send_result_wait_ms,
        finality_config=finality_config,
        authority_epoch_current=preconditions.authority_epoch_current,
        broker_sourced=broker_posttrade_enabled(active_scope, transport_config),
    )
    return WiredEngine(
        gateway=gateway,
        transport=transport,
        core=core,
        resolved_registry=resolved_registry,
        inbox=inbox,
        driver=driver,
    )
