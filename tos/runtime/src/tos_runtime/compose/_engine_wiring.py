"""``tos_runtime.compose`` engine-driver wiring — TOS Phase 3 Wave 1 Lane A-R.

Split out of ``_wiring.py``/``root.py`` for the size budget
(``tools/tos_size_budget.py`` — ``_wiring.py`` was already registered at 1116
lines before this wave; see ``config/tos_size_budget.yaml``), not for any
behavioural reason: :func:`build_engine_driver` is called from
``_wiring.py``'s own ``_finalize`` exactly once, in the design #40 §5 order
this compose root already documents (engine core wired first, driver last —
the driver needs the composed core AND gateway to exist).

Owns two things:

1. :func:`load_engine_driver_config` — the ``replay_window_events`` boot-time
   cost bound (plan §1.1; see ``tos/runtime/config/engine_driver.example.yaml``).
2. :func:`build_engine_driver` — constructs the durable
   :class:`~tos_runtime.engine.inbox.SqliteEventInbox` (its own sqlite file,
   SEPARATE from the evidence store — D3 failure-domain separation, operator-
   confirmed item 2) and the :class:`~tos_runtime.engine.driver.EngineDriver`
   bound to the already-composed core and gateway.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib
(``pathlib``, ``yaml``) + ``tos.canonical``/``tos.egressgw``/``tos.engine`` +
``tos_runtime.*`` only. No ``shared.*``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from tos.brokeradapter import SyntheticFillPolicy, SyntheticPaperTransport
from tos.canonical import CanonicalizationScheme
from tos.egressgw import BrokerEgressGateway
from tos.engine import (
    CommitmentStep,
    EngineConfiguration,
    EngineCore,
    NullEvidenceSink,
    Stage,
    StrategyRegistry,
)
from tos.workload import RuntimeIdentity

from tos_runtime.compose._boot_integrity import verify_engine_replay_or_halt
from tos_runtime.compose.context import ComposeContextResolver
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.engine.replay import ReplayVerdict
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.sinks import (
    EngineEvidenceSinkAdapter,
    GatewayEvidenceSinkAdapter,
)
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.obligation import CapacityObligationRecorder
from tos_runtime.rcl.projection import SqliteReservationProjectionReader
from tos_runtime.time.sources import MonotonicSource

__all__ = [
    "ENGINE_DRIVER_CONFIG_NAME",
    "INBOX_FILE_NAME",
    "EngineDriverConfig",
    "EngineDriverConfigError",
    "WiredEngine",
    "build_engine_driver",
    "load_engine_driver_config",
    "verify_replay_or_halt",
    "wire_engine_and_driver",
]

ENGINE_DRIVER_CONFIG_NAME = "engine_driver.yaml"

#: The durable event inbox's own sqlite file name — a SEPARATE file from
#: ``evidence.sqlite3`` (module docstring item 2 / D3 failure-domain
#: separation).
INBOX_FILE_NAME = "inbox.sqlite3"


class EngineDriverConfigError(Exception):
    """Raised when the engine-driver config is missing, malformed, or
    carries an unfilled (named-TBD) field — fail-closed at load, never a
    silent default."""


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
    """Load + fail-closed-validate the engine-driver config from ``path``.

    Raises:
        EngineDriverConfigError: The file is missing/unreadable/not valid
            YAML/not a mapping, the key is absent, still ``null``, not an
            int, or not a positive int.
    """
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
    scheme: CanonicalizationScheme,
    continuity_id: str,
    monotonic_source: MonotonicSource,
    max_send_result_wait_ms: int | None,
) -> tuple[SqliteEventInbox, EngineDriver]:
    """Construct the durable inbox and the engine driver, bound to ``gateway``.

    Args:
        data_dir: Directory for the inbox's own sqlite file (SEPARATE from
            the evidence store's — module docstring item 2).
        core: The already-composed :class:`~tos.engine.EngineCore`.
        gateway: The already-composed send boundary whose retained
            ``.results`` the driver drains.
        evidence_store: The durable evidence store the driver appends
            ``EVENT_CONSUMED`` receipts into.
        scheme: The canonicalization scheme for event identity and the
            outcome-digest stand-in.
        continuity_id: The single stream continuity every coordinate this
            driver issues carries.
        monotonic_source: The injected monotonic clock for timeout
            injection.
        max_send_result_wait_ms: The injected wait bound before a
            SENT_UNCONFIRMED hand-off is timed out; ``None`` disables
            timeout injection.

    Returns:
        ``(inbox, driver)`` — the driver is already bound to ``gateway``.
    """
    inbox = SqliteEventInbox(data_dir / INBOX_FILE_NAME, scheme=scheme)
    driver = EngineDriver(
        core=core,
        inbox=inbox,
        evidence_store=evidence_store,
        scheme=scheme,
        continuity_id=continuity_id,
        monotonic_source=monotonic_source,
        max_send_result_wait_ms=max_send_result_wait_ms,
    )
    driver.bind_gateway(gateway)
    return inbox, driver


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
) -> ReplayVerdict:
    """Build the side-effect-free replay core factory and run the boot-time replay check.

    Split out of ``_wiring.py``'s ``_finalize`` purely for the size budget (its own function-size
    limit) — the replay core factory closes over ``registry``/``stages``/``configuration`` the
    SAME way ``_finalize`` builds its real ``core``, just with ``transmit=None`` and a discarding
    sink (see :mod:`tos_runtime.engine.replay`'s own module docstring for exactly what that does
    and does not guarantee).
    """

    def _replay_core_factory() -> EngineCore:
        return EngineCore(
            registry=registry,
            stages=stages,
            configuration=configuration,
            transmit=None,
            sink=NullEvidenceSink(),
            scheme=scheme,
        )

    return verify_engine_replay_or_halt(
        inbox,
        evidence_store,
        emergency_log,
        _replay_core_factory,
        scheme=scheme,
        window_events=window_events,
    )


@dataclass
class WiredEngine:
    """Every artifact :func:`wire_engine_and_driver` assembles — handed straight into
    :class:`~tos_runtime.compose._types.ComposedRuntime`'s matching fields by ``_finalize``.
    """

    gateway: BrokerEgressGateway
    transport: SyntheticPaperTransport
    core: EngineCore
    resolved_registry: StrategyRegistry
    inbox: SqliteEventInbox
    driver: EngineDriver


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
    max_send_result_wait_ms: int | None,
) -> WiredEngine:
    """The gateway + ``EngineCore`` + durable inbox/driver wiring — split out of ``_wiring.py``'s
    ``_finalize`` purely for the size budget; no behavioural difference from having this inline
    there. Builds, in order: the obligation recorder + gateway evidence sink -> the synthetic
    transport + ``BrokerEgressGateway`` -> the resolved registry + engine evidence sink ->
    ``EngineCore`` (steps 2-11/13/14 + this gateway as ``transmit``) -> the durable inbox +
    :class:`~tos_runtime.engine.driver.EngineDriver`, bound to both (TOS Phase 3 Wave 1 Lane A-R,
    plan §1.1: "engine core wired first, driver last").
    """
    # Kernel round #1 §3 (lane B): the reservation id bound to any attempt in THIS compose root
    # is always this same formula — the SAME one _build_realized_stages' AtomicCommitStage
    # reservation_id_provider and _build_currentness_stages' TransmissionCapabilityStage
    # context_reader already use — because this compose root wires exactly one InstrumentKey
    # (context_resolver.instrument_key) for its whole process lifetime (see
    # tos_runtime.rcl.obligation's own module docstring, "Reservation-id resolution").
    instrument_key = context_resolver.instrument_key
    obligation_recorder = CapacityObligationRecorder(
        store=evidence_store,
        emergency_log=emergency_log,
        projection=projection,
        reservation_id_resolver=lambda _attempt_id: (
            f"resv-{instrument_key.account}-{instrument_key.instrument}"
        ),
    )
    # Independent review finding #8: wiring on_refusal here means a SEND_REFUSED whose
    # obligation this recorder cannot verify (e.g. the rcl projection's sqlite read fails) now
    # raises out of GatewayEvidenceSinkAdapter.record and transitively out of
    # BrokerEgressGateway.__call__ — deliberate, fail-closed (sinks.py's own module + record()
    # docstrings carry the full rationale).
    gateway_sink = GatewayEvidenceSinkAdapter(
        evidence_store, runtime_identity=identity, on_refusal=obligation_recorder
    )
    transport = SyntheticPaperTransport(
        SyntheticFillPolicy(fill_numerator=1, fill_denominator=1, lot_size=Decimal("1"))
    )
    gateway = BrokerEgressGateway(
        contexts=context_resolver, transport=transport, sink=gateway_sink
    )

    resolved_registry = registry if registry is not None else StrategyRegistry()
    engine_sink = EngineEvidenceSinkAdapter(evidence_store, runtime_identity=identity)
    core = EngineCore(
        registry=resolved_registry,
        stages=stages,
        configuration=configuration,
        transmit=gateway,
        sink=engine_sink,
    )

    inbox, driver = build_engine_driver(
        data_dir=data_dir,
        core=core,
        gateway=gateway,
        evidence_store=evidence_store,
        scheme=scheme,
        continuity_id=continuity_id,
        monotonic_source=monotonic_source,
        max_send_result_wait_ms=max_send_result_wait_ms,
    )
    return WiredEngine(
        gateway=gateway,
        transport=transport,
        core=core,
        resolved_registry=resolved_registry,
        inbox=inbox,
        driver=driver,
    )
