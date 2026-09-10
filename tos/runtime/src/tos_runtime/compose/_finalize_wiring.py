"""``tos_runtime.compose`` finalization — the tail of ``compose_paper_runtime`` (engine core +
gateway + durable inbox/driver wiring, boot-time replay re-verification, and the final
:class:`~tos_runtime.compose._types.ComposedRuntime` assembly).

Split out of ``_wiring.py`` (independent review MEDIUM-5, T2 lane C re-review) purely for the
size budget — no behavioural difference from having :func:`_finalize` inline there. ``_wiring.py``
had grown past its own "성장 금지" (no-growth) landing condition; :func:`_finalize` was itself a
registered 112-line over-budget function whose entire body is engine/transport hand-off wiring —
the same concern :mod:`tos_runtime.compose._engine_wiring` and
:mod:`tos_runtime.compose._transport_wiring` already own. Moving it here, alongside its own small
:func:`_build_engine_configuration` helper, retires both the module-level ``_wiring.py`` exception
and (via the ``_verify_boot_replay`` extraction below) the function-level ``_finalize`` exception.

Depends on ``_wiring.py``'s own private phase-result dataclasses (:class:`~tos_runtime.compose.
_wiring._Infra`, :class:`~tos_runtime.compose._wiring._RclAndAuthority`,
:class:`~tos_runtime.compose._wiring._ConstructionStages`, :class:`~tos_runtime.compose._wiring.
_RealizedStages`) — a ONE-DIRECTION dependency (this module imports from ``_wiring.py``;
``_wiring.py`` never imports back from this module — :func:`~tos_runtime.compose.root.
compose_paper_runtime` imports :func:`_finalize` directly from here instead), so there is no
import cycle.

:func:`~tos_runtime.compose.root.compose_paper_runtime` is the orchestrator that calls
:func:`_finalize`, in the design #40 §5 order.
"""

from __future__ import annotations

from pathlib import Path

from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine import EngineConfiguration, StrategyRegistry
from tos.workload import RuntimeIdentity

from tos_runtime.brokercap import BrokerScopesConfig, InstanceDocument
from tos_runtime.compose._currentness_wiring import _RiskAndCurrentness
from tos_runtime.compose._engine_config import load_engine_config
from tos_runtime.compose._engine_wiring import (
    ENGINE_DRIVER_CONFIG_NAME,
    load_engine_driver_config,
    verify_replay_or_halt,
    wire_engine_and_driver,
)
from tos_runtime.compose._preconditions import (
    COORDINATOR_PRECONDITIONS_CONFIG_NAME,
    load_coordinator_preconditions_config,
)
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.compose._types import ComposedRuntime
from tos_runtime.compose._wiring import (
    _ConstructionStages,
    _Infra,
    _RclAndAuthority,
    _RealizedStages,
)
from tos_runtime.compose.context import ComposeContextResolver
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.engine.replay import ReplayVerdict
from tos_runtime.posttrade.config import load_finality_config
from tos_runtime.transport.kis_mock.config import KisMockTransportConfig

__all__ = ["_finalize"]

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

_ENGINE_CONFIG_NAME = "engine.yaml"
#: TOS Phase 3 Wave 2 Lane C-R follow-up (team-lead CR-4 dispatch, plan §2.2) — the SYNTHETIC
#: post-trade finality policy (:mod:`tos_runtime.posttrade.config`).
_FINALITY_CONFIG_NAME = "finality.yaml"


def _build_engine_configuration(config_dir: Path) -> EngineConfiguration:
    """Load ``engine.yaml``'s two operator-configured bounds (pre-merge fix
    F5, 2026-09-08 — CLAUDE.md non-negotiable: thresholds belong in config,
    never a hardcoded literal) and construct the kernel's own
    ``EngineConfiguration`` — the ``canonicalization_version``/
    ``enforcement_mechanism_version`` fields are compose's own fixed
    identity, not operator-configured, and stay as they were."""
    engine_config = load_engine_config(config_dir / _ENGINE_CONFIG_NAME)
    return EngineConfiguration(
        dsl_evaluation_budget_steps=engine_config.dsl_evaluation_budget_steps,
        max_unresolved_send_per_scope=engine_config.max_unresolved_send_per_scope,
        canonicalization_version=EV_L1_PROVISIONAL_VERSION,
        enforcement_mechanism_version="compose-paper-runtime-v1",
    )


def _verify_boot_replay(
    *,
    config_dir: Path,
    infra: _Infra,
    wired_inbox: SqliteEventInbox,
    wired_resolved_registry: StrategyRegistry,
    stages: dict,
    engine_configuration: EngineConfiguration,
) -> ReplayVerdict:
    """Independent boot-time re-derivation over whatever this inbox has already durably admitted
    (design plan §1.1 "부팅 시 verify_rcl_log_or_halt 뒤에 실행"). Split out of :func:`_finalize`
    purely for the size budget (independent review MEDIUM-5) — no behavioural difference.

    Reported deviation from the plan's literal adjacency: ``verify_rcl_log_or_halt`` itself runs
    earlier, inside ``_boot_services``, before the engine core/gateway/inbox exist to replay at
    all — this is the earliest point in compose an engine replay check is constructible, and it
    still runs strictly after the RCL log's own integrity is re-verified (the substantive
    ordering requirement). See :mod:`tos_runtime.engine.replay`'s own module docstring for what
    "side-effect-free" does and does not cover for a core that DID have a working transmit in its
    original run.
    """
    engine_driver_config = load_engine_driver_config(
        config_dir / ENGINE_DRIVER_CONFIG_NAME
    )
    return verify_replay_or_halt(
        inbox=wired_inbox,
        evidence_store=infra.evidence_store,
        emergency_log=infra.emergency_log,
        registry=wired_resolved_registry,
        stages=stages,
        configuration=engine_configuration,
        scheme=_SCHEME,
        window_events=engine_driver_config.replay_window_events,
    )


def _finalize(
    *,
    config_dir: Path,
    data_dir: Path,
    infra: _Infra,
    rcl: _RclAndAuthority,
    risk: _RiskAndCurrentness,
    construction_stages: _ConstructionStages,
    realized: _RealizedStages,
    stages: dict,
    context_resolver: ComposeContextResolver,
    identity: RuntimeIdentity,
    registry: StrategyRegistry | None,
    release_admitted: bool,
    continuity_id: str,
    broker_scopes: BrokerScopesConfig,
    instance_document: InstanceDocument | None,
    transport_kind: TransportKind,
    transport_config: KisMockTransportConfig | None,
) -> ComposedRuntime:
    """The gateway + ``EngineCore`` + durable inbox/driver wiring (delegated to
    :func:`~tos_runtime.compose._engine_wiring.wire_engine_and_driver`) + the boot-time replay
    check (:func:`_verify_boot_replay`) + the final :class:`~tos_runtime.compose._types.
    ComposedRuntime` assembly — the tail of :func:`~tos_runtime.compose.root.
    compose_paper_runtime`, split out purely for the size budget (module docstring)."""
    engine_configuration = _build_engine_configuration(config_dir)
    # Coordinator-preconditions governance posture (design #31 §9-10; plan §2.1) — fail-closed,
    # from its own example-shaped file, same as every other tos_runtime.*.config value.
    coordinator_preconditions_config = load_coordinator_preconditions_config(
        config_dir / COORDINATOR_PRECONDITIONS_CONFIG_NAME
    )
    # SYNTHETIC post-trade finality policy (CR-4, plan §2.2) — fail-closed, from its own file.
    finality_config = load_finality_config(config_dir / _FINALITY_CONFIG_NAME)
    wired = wire_engine_and_driver(
        data_dir=data_dir,
        context_resolver=context_resolver,
        identity=identity,
        evidence_store=infra.evidence_store,
        emergency_log=infra.emergency_log,
        projection=risk.projection,
        stages=stages,
        configuration=engine_configuration,
        registry=registry,
        scheme=_SCHEME,
        continuity_id=continuity_id,
        monotonic_source=infra.monotonic_source,
        max_send_result_wait_ms=infra.time_config.max_send_result_wait_ms,
        authority_epoch_service=rcl.authority_epoch_service,
        live_authorization_state=coordinator_preconditions_config.live_authorization_state,
        finality_config=finality_config,
        nonlive_admitted=coordinator_preconditions_config.nonlive_broker_consuming_admitted,
        active_scope=broker_scopes.active_scope,
        instance_document=instance_document,
        custody=infra.custody,
        transport_kind=transport_kind,
        transport_config=transport_config,
    )

    _verify_boot_replay(
        config_dir=config_dir,
        infra=infra,
        wired_inbox=wired.inbox,
        wired_resolved_registry=wired.resolved_registry,
        stages=stages,
        engine_configuration=engine_configuration,
    )

    return ComposedRuntime(
        custody=infra.custody,
        key_provider=infra.key_provider,
        evidence_store=infra.evidence_store,
        emergency_log=infra.emergency_log,
        time_service=infra.time_service,
        rcl_log=rcl.rcl_log,
        writer_epoch=rcl.writer_epoch,
        identity=identity,
        authority_epoch_service=rcl.authority_epoch_service,
        intent_registry=rcl.intent_registry,
        risk_service=risk.risk_service,
        flow_governor=risk.flow_governor,
        currentness_assembler=risk.currentness_assembler,
        proof_issuer=risk.proof_issuer,
        step4_recorder=realized.step4_recorder,
        step9_recorder=realized.step9_recorder,
        step14_stage=realized.step14_stage,
        construction_stage=construction_stages.construction_stage,
        venue_stage=construction_stages.venue_stage,
        proof_stage=construction_stages.proof_stage,
        context_resolver=context_resolver,
        core=wired.core,
        gateway=wired.gateway,
        transport=wired.transport,
        registry=wired.resolved_registry,
        release_admitted=release_admitted,
        required_scenario_kinds=risk.required_scenario_kinds,
        inbox=wired.inbox,
        driver=wired.driver,
        scopes=broker_scopes,
    )
