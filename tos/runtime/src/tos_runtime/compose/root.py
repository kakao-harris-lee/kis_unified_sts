"""``compose_paper_runtime`` — the ONE composition root (design #40 D1.1;"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Callable
from pathlib import Path

from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine import (
    StageRequest,
    StrategyRegistry,
)

from tos_runtime.brokercap import is_broker_reaching
from tos_runtime.calendar.config import load_calendar_config
from tos_runtime.calendar.ports import WallClockReference
from tos_runtime.compose._attempt_arm import attempt_action_class
from tos_runtime.compose._authority_heartbeat import with_authority_heartbeat
from tos_runtime.compose._broker_facts_wiring import build_broker_facts
from tos_runtime.compose._broker_posttrade_wiring import (
    attach_fill_observer,
    build_broker_posttrade,
    fill_observer_pass,
)
from tos_runtime.compose._finalize_wiring import _finalize
from tos_runtime.compose._held_position_wiring import HeldPositionBridge
from tos_runtime.compose._kis_credential_wiring import KisCredentialSessionsCell
from tos_runtime.compose._marketfeed_wiring import build_tick_scheduler
from tos_runtime.compose._operations_wiring import apply_operations_wiring
from tos_runtime.compose._recovery_wiring import apply_recovery_barrier
from tos_runtime.compose._release_wiring import apply_release_wiring
from tos_runtime.compose._request_digest import KisWireCodecDigest
from tos_runtime.compose._riskstate_provider_wiring import (
    build_risk_state_providers,
)
from tos_runtime.compose._riskstate_wiring import build_risk_state_service
from tos_runtime.compose._session_wiring import (
    CALENDAR_CONFIG_NAME,
    SessionInboxCell,
    apply_session_wiring,
    build_egress_trading_date_reader,
    build_session_facts_owner,
)
from tos_runtime.compose._standing_wiring import build_standing_approval
from tos_runtime.compose._transport_wiring import TransportKind, evidence_recorder
from tos_runtime.compose._types import (
    ComposedRuntime,
    ConstructionConfig,
    ReleaseAdmissionRefused,
    RiskStateConfigError,
)
from tos_runtime.compose._venue_ledger_wiring import (
    build_synthetic_venue_ledger,
)
from tos_runtime.compose._venue_wiring import (
    build_band_reader_factory,
    build_venue_service,
)
from tos_runtime.compose._wiring import (
    _boot_services,
    _build_construction_stages,
    _build_context_resolver,
    _build_realized_stages,
    _build_stage_map,
)
from tos_runtime.rcl.log import StaleEpochRead
from tos_runtime.recon.witness_synthetic_venue import (
    SYNTHETIC_VENUE_LEDGER_PROVENANCE,
)
from tos_runtime.risk.aggregate import (
    AggregateRiskDecisionInputs,
)
from tos_runtime.risk.flow import ActionFlowDecisionInputs
from tos_runtime.riskstate.close_bound import (
    CloseAuthoritySource,
    DurableEntryCloseBoundReader,
)
from tos_runtime.time.sources import (
    MonotonicSource,
)

__all__ = [
    "ComposedRuntime",
    "ConstructionConfig",
    "ReleaseAdmissionRefused",
    "RiskStateConfigError",
    "TransportKind",
    "compose_paper_runtime",
]

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

_TIME_CONFIG_NAME = "time.yaml"
_AUTHORITY_CONFIG_NAME = "authority.yaml"
_RISK_CONFIG_NAME = "risk.yaml"
_CURRENTNESS_CONFIG_NAME = "currentness.yaml"
_RELEASE_CONFIG_NAME = "release.yaml"

_APPROVALS_DIRNAME = "approvals"


def _close_authority_for(transport_kind: TransportKind) -> CloseAuthoritySource:
    """What a CLOSE's quantity bound may rest on, from the boot's transport kind (#1011)."""
    if transport_kind is TransportKind.SYNTHETIC:
        return CloseAuthoritySource.DURABLE_EVIDENCE
    return CloseAuthoritySource.BROKER_HELD_PROOF


def compose_paper_runtime(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    environment_label: str,
    *,
    construction: ConstructionConfig,
    aggregate_risk_inputs_provider: (
        Callable[[StageRequest], AggregateRiskDecisionInputs | None] | None
    ) = None,
    action_flow_inputs_provider: (
        Callable[[StageRequest], ActionFlowDecisionInputs | None] | None
    ) = None,
    registry: StrategyRegistry | None = None,
    authority_domain: str = "trading",
    continuity_id: str = "paper-runtime",
    monotonic_source: MonotonicSource | None = None,
    allow_no_strategies: bool = False,
    transport_kind: TransportKind = TransportKind.SYNTHETIC,
    projection_path: Path | None = None,
    backup_root: Path | None = None,
    wall_clock: WallClockReference | None = None,
) -> ComposedRuntime:
    """Wire the whole Phase 2 paper-runtime service chain, in order (module"""
    uid = os.getuid()
    boot = _boot_services(
        config_dir,
        data_dir,
        custody_root,
        environment_label,
        uid,
        authority_domain,
        monotonic_source,
        registry,
        allow_no_strategies,
        transport_kind,
    )
    boot.risk.environment_scope_dimension_state.active_scope = (
        boot.broker_scopes.active_scope
    )
    boot.risk.release_dimension_state.release_admitted = boot.release_admitted

    calendar_config = load_calendar_config(config_dir / CALENDAR_CONFIG_NAME)
    session_inbox_cell = SessionInboxCell()
    session_facts_owner = build_session_facts_owner(
        config_dir=config_dir,
        calendar=calendar_config,
        wall_clock=wall_clock,
        evidence_store=boot.infra.evidence_store,
        time_config=boot.infra.time_config,
        time_service=boot.infra.time_service,
        tick_generation_reader=session_inbox_cell.read,
    )

    session_phase_reader = lambda: session_facts_owner.phase_for_step3(  # noqa: E731
        construction.instrument_class
    )

    trading_date_reader = lambda: session_facts_owner.trading_date_now(  # noqa: E731
        construction.instrument_class
    )
    credential_sessions_cell = KisCredentialSessionsCell()
    broker_facts = build_broker_facts(
        config_dir=config_dir,
        broker_scopes=boot.broker_scopes,
        transport_config=boot.transport_config,
        credential_sessions_cell=credential_sessions_cell,
        monotonic=boot.infra.monotonic_source,
        evidence_sink=evidence_recorder(boot.infra.evidence_store, boot.identity),
        account=construction.account,
        instrument=construction.instrument,
    )
    venue_ledger = build_synthetic_venue_ledger(
        config_dir=config_dir,
        data_dir=data_dir,
        transport_kind=transport_kind,
        scheme=_SCHEME,
        trading_date_now=trading_date_reader,
    )
    posttrade = build_broker_posttrade(
        config_dir=config_dir,
        broker_scopes=boot.broker_scopes,
        transport_config=boot.transport_config,
        credential_sessions_cell=credential_sessions_cell,
        trading_date_now=trading_date_reader,
    )
    if (
        posttrade.enabled
        and posttrade.observer_config is not None
        and posttrade.observer_config.held_position_max_age_ms is not None
    ):
        posttrade.held_position_bridge = HeldPositionBridge(
            log=boot.rcl.rcl_log,
            now=boot.infra.monotonic_source.now_ms,
            today=trading_date_reader,
            max_age_ms=posttrade.observer_config.held_position_max_age_ms,
        )
    venue_service, loaded_ocp = build_venue_service(
        config_dir=config_dir,
        scheme=_SCHEME,
        construction=construction,
        environment_label=environment_label,
        session_phase_reader=session_phase_reader,
        tick_generation_reader=session_inbox_cell.read,
        evidence_store=boot.infra.evidence_store,
        instance_document=boot.instance_document,
        egress_coordinates=boot.egress_coordinates,
        transport_kind=transport_kind,
        calendar_config=calendar_config,
        transport_config=boot.transport_config,
        band_reader_factory=build_band_reader_factory(
            config_dir=config_dir,
            broker_scopes=boot.broker_scopes,
            monotonic=boot.infra.monotonic_source,
            evidence_sink=evidence_recorder(boot.infra.evidence_store, boot.identity),
            credential_sessions_cell=credential_sessions_cell,
            trading_date_reader=trading_date_reader,
        ),
        trading_date_reader=trading_date_reader,
    )

    entry_close_bound_reader = DurableEntryCloseBoundReader(
        rcl_log=boot.rcl.rcl_log,
        evidence_store=boot.infra.evidence_store,
        projection=boot.risk.projection,
        account=construction.account,
        instrument=construction.instrument,
    ).read
    construction_stages = _build_construction_stages(
        construction,
        venue_service=venue_service,
        loaded_ocp=loaded_ocp,
        entry_close_bound_reader=entry_close_bound_reader,
    )
    risk_providers = build_risk_state_providers(
        config_dir=config_dir,
        aggregate_risk_inputs_provider=aggregate_risk_inputs_provider,
        action_flow_inputs_provider=action_flow_inputs_provider,
    )
    risk_state_files_exist = risk_providers.files_exist
    risk_state_cell = risk_providers.cell

    realized = _build_realized_stages(
        infra=boot.infra,
        rcl=boot.rcl,
        risk=boot.risk,
        construction_stages=construction_stages,
        construction=construction,
        aggregate_risk_inputs_provider=risk_providers.aggregate_inputs,
        action_flow_inputs_provider=risk_providers.action_flow_inputs,
        close_proof_fence_reader=risk_providers.close_fence,
        custody_root=custody_root,
        environment_label=environment_label,
        uid=uid,
        standing=build_standing_approval(
            boot,
            construction_stages.construction_stage,
            trading_date_reader=trading_date_reader,
            custody_root=custody_root,
            environment_label=environment_label,
            uid=uid,
        ),
    )
    stages = _build_stage_map(construction_stages, realized)

    request_bytes_digest_source = (
        KisWireCodecDigest(
            field_map=boot.transport_config.field_map,
            static_body_fields=boot.transport_config.static_body_fields,
            price_scale=boot.transport_config.price_scale,
        )
        if boot.transport_config is not None
        else None
    )
    context_resolver = _build_context_resolver(
        transport_config=boot.transport_config,
        construction_stages=construction_stages,
        realized=realized,
        flow_governor=boot.risk.flow_governor,
        currentness_assembler=boot.risk.currentness_assembler,
        proof_issuer=boot.risk.proof_issuer,
        session_facts_current_reader=lambda: session_facts_owner.session_facts_current(
            construction.instrument_class,
        ),
        tradability_facts_current_reader=broker_facts.tradability(
            lambda: session_facts_owner.tradability_facts_current(
                broker_reaching=is_broker_reaching(boot.broker_scopes.active_scope),
            )
        ),
        account_facts_current_reader=broker_facts.account(
            lambda: session_facts_owner.account_facts_current(
                broker_reaching=is_broker_reaching(boot.broker_scopes.active_scope),
            )
        ),
        mock_generation_reader=broker_facts.generation,
        observed_session_phase_reader=session_phase_reader,
        egress_coordinates=boot.egress_coordinates,
        broker_scopes=boot.broker_scopes,
        instance_document=boot.instance_document,
        construction=construction,
        environment_label=environment_label,
        continuity_id=continuity_id,
        authority_epoch_service=boot.rcl.authority_epoch_service,
        monitor_owners=boot.risk.monitor_owners,
        projection=boot.risk.projection,
        evidence_store=boot.infra.evidence_store,
        request_bytes_digest_source=request_bytes_digest_source,
    )

    composed = _finalize(
        config_dir=config_dir,
        data_dir=data_dir,
        infra=boot.infra,
        rcl=boot.rcl,
        risk=boot.risk,
        construction_stages=construction_stages,
        realized=realized,
        stages=stages,
        context_resolver=context_resolver,
        identity=boot.identity,
        registry=boot.registry,
        release_admitted=boot.release_admitted,
        continuity_id=continuity_id,
        broker_scopes=boot.broker_scopes,
        instance_document=boot.instance_document,
        transport_kind=transport_kind,
        transport_config=boot.transport_config,
        trading_date_now=build_egress_trading_date_reader(
            trading_date_reader, time_service=boot.infra.time_service
        ),
        credential_sessions_cell=credential_sessions_cell,
        venue_ledger=venue_ledger.ledger,
    )
    composed.venue_ledger = venue_ledger
    if venue_ledger.witness is not None:
        composed.broker_witness_provenance = SYNTHETIC_VENUE_LEDGER_PROVENANCE
    composed.venue = venue_service
    boot.risk.monitor_owners.inbox_cell.inbox = composed.inbox

    def _rcl_tip_reader() -> int | None:
        try:
            view = boot.rcl.rcl_log.read_linearizable(
                writer_epoch=boot.rcl.writer_epoch
            )
        except (StaleEpochRead, sqlite3.Error, OSError):
            return None
        return None if view.last_seq is None else view.last_seq

    if risk_state_files_exist:
        risk_state_cell["service"] = build_risk_state_service(
            config_dir=config_dir,
            scheme=_SCHEME,
            construction=construction,
            environment_label=environment_label,
            evidence_store=boot.infra.evidence_store,
            inbox=composed.inbox,
            rcl_log=boot.rcl.rcl_log,
            scenario_set=boot.risk.risk_service.scenario_set,
            required_scenario_kinds=boot.risk.required_scenario_kinds,
            rcl_tip_reader=_rcl_tip_reader,
            monotonic_reader=boot.infra.monotonic_source.now_ms,
            max_attempts_reader=lambda: boot.risk.flow_governor.envelope.max_attempts,
            construction_stage_reader=(
                lambda: construction_stages.construction_stage.construction
            ),
            effect_envelope_reader=lambda: construction_stages.economic_stage.envelope,
            venue_allowed_sides=venue_service.shape_constraints.allowed_sides,
            action_class_reader=lambda: attempt_action_class(
                construction_stages.construction_stage, construction.action_class
            ),
            attempt_arm_direction_reader=lambda: getattr(
                getattr(construction_stages.construction_stage, "attempt", None),
                "direction",
                None,
            ),
            held_position_proof_reader=(
                None
                if posttrade.held_position_bridge is None
                else posttrade.held_position_bridge.consume
            ),
            held_position_currentness_reader=(
                None
                if posttrade.held_position_bridge is None
                else posttrade.held_position_bridge.cell.validate_consumed
            ),
            close_authority=_close_authority_for(transport_kind),
            entry_close_bound_reader=entry_close_bound_reader,
        )
    composed.risk_state = risk_state_cell["service"]
    composed = apply_session_wiring(
        composed,
        session_inbox_cell=session_inbox_cell,
        session_facts_owner=session_facts_owner,
    )
    composed = apply_release_wiring(
        composed,
        config_dir=config_dir,
        scheme=_SCHEME,
        monotonic_source=boot.infra.monotonic_source,
        post_trade_dimension_state=boot.risk.post_trade_dimension_state,
        posttrade=posttrade,
        venue_witness=venue_ledger.witness,
    )
    composed = apply_recovery_barrier(
        composed,
        config_dir=config_dir,
        data_dir=data_dir,
        custody_root=custody_root,
        scheme=_SCHEME,
        witness=(
            posttrade.witness if posttrade.witness is not None else venue_ledger.witness
        ),
    )
    composed = attach_fill_observer(
        composed, posttrade, monotonic=boot.infra.monotonic_source
    )
    boot.risk.recovery_dimension_state.verdict = composed.recovery
    composed.marketfeed = build_tick_scheduler(
        config_dir=config_dir,
        data_dir=data_dir,
        scheme=_SCHEME,
        time_config=boot.infra.time_config,
        time_service=composed.time_service,
        session_owner=session_facts_owner,
        driver=composed.driver,
        inbox=composed.inbox,
        evidence_store=composed.evidence_store,
        custody=boot.infra.custody,
        monotonic=boot.infra.monotonic_source,
        credential_sessions=composed.kis_credential_sessions,
        broker_scopes=boot.broker_scopes,
        runtime_identity=boot.identity,
        after_pass=with_authority_heartbeat(composed, fill_observer_pass(composed)),
    )
    composed = apply_operations_wiring(
        composed, projection_path=projection_path, backup_root=backup_root
    )
    return composed
