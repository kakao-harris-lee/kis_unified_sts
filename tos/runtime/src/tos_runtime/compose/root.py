"""``compose_paper_runtime`` — the ONE composition root (design #40 D1.1;
slice plan §4 item 1).

"composition root 는 `tos_runtime.compose` 단 하나 — 커널 Protocol 심을
구현체와 한 자리에서 결선한다." This module is that one place. It wires, in
the stated order (slice plan §4):

    identity -> release admission (refuse => raise, nothing constructed) ->
    custody -> evidence store (``FileKeyProvider``) -> emergency log
    -> Trustworthy Time service (``start()``) -> RCL log (``acquire_epoch`` +
    generation seed) -> Safety Authority epoch service -> Intent Registry
    -> risk services (Aggregate Risk Authority + Action Flow Governor)
    -> currentness (assembler + proof issuer) -> ``EngineCore`` (real
    ``Stage``s for steps 4, 6-10, 13, 14; the kernel's OWN existing
    implementations for steps 2, 3, 5, 11) -> ``BrokerEgressGateway`` (the
    compose-root ``SendBoundaryContext`` resolver,
    :mod:`tos_runtime.compose.context`) -> ``SyntheticPaperTransport``
    -> the TOS Phase 5 W1 recovery barrier
    (:func:`~tos_runtime.compose._recovery_wiring.apply_recovery_barrier` — see
    that module's own docstring for why this runs here, right after ``_finalize``,
    rather than literally "before the engine driver is wired": the durable inbox
    the barrier reads does not exist any earlier in this function).

    **Release admission is moved ahead of custody/evidence/RCL, reported
    deviation from the plan's literal listed order.** See the "identity +
    release admission FIRST" comment inside this function for why: the
    gate's only real input is this process's own
    :class:`~tos.workload.RuntimeIdentity` (pure computation, no I/O) plus
    the static ``release.yaml`` snapshot — it depends on neither the
    evidence store nor the RCL log — and the compose end-to-end test's
    scenario 7 requires "release admission refusal ⇒ compose raises before
    any service starts (assert no sqlite files created)", which is only
    achievable if the gate runs before any sqlite file is opened. The
    listed order's actual intent — "nothing past this gate is
    constructed" — is preserved exactly; only its position relative to
    custody/evidence/RCL construction moved earlier.

**Steps 2/3/5/11 reuse the kernel's own, already-shipped Order Construction
stages** (``tos.egressgw.{OrderConstructionStage,VenueConstraintStage,
EconomicEffectStage,ConformanceProofStage}`` — the same four classes
``tos/tests/slice/_slice_fixtures.py::construction_stages`` wires for the
kernel's own end-to-end test). They are **not** stand-ins
(``tos.engine.standins.ProvisionalStandIn``): each is backed by a real,
already-shipped kernel predicate call (design #34 §3.2), so using them here
keeps this composition's own ``NON_AUTHORITATIVE_PROVISIONAL`` count at
exactly zero for every one of steps 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14 —
see the compose end-to-end test's ``test_stand_in_zero_across_the_wired_steps``.

**Order-construction facts are genuinely per-strategy configuration** (an
Authorized Construction Envelope, a sizing bound, a venue policy/snapshot/
decision, an order shape + its constraints) — there is no Phase-2 runtime
that derives these (Order Construction Policy governance, RFC-002 §9.1:553,
is a separate, still-unratified artifact; a real venue-constraint service is
Phase 4+). :class:`ConstructionConfig` is therefore an explicit, caller-
supplied parameter group (mirroring how ``_slice_fixtures.py`` injects the
same facts for the kernel's own e2e test) rather than a fifth positional
argument invented to look like it comes from a file that does not exist yet.

Firewall (tools/tos_firewall_check.py R1, runtime scope): stdlib + ``tos.*``
+ ``tos_runtime.*`` only. No ``shared.*``.
"""

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
from tos_runtime.compose._finalize_wiring import _finalize
from tos_runtime.compose._marketfeed_wiring import build_tick_scheduler
from tos_runtime.compose._operations_wiring import apply_operations_wiring
from tos_runtime.compose._recovery_wiring import apply_recovery_barrier
from tos_runtime.compose._release_wiring import apply_release_wiring
from tos_runtime.compose._request_digest import KisWireCodecDigest
from tos_runtime.compose._riskstate_wiring import build_risk_state_service
from tos_runtime.compose._session_wiring import (
    CALENDAR_CONFIG_NAME,
    SessionInboxCell,
    apply_nontrade_wiring,
    apply_session_wiring,
    build_nontrade_admissibility_provider,
    build_nontrade_processor,
    build_session_facts_owner,
)
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.compose._types import (
    ComposedRuntime,
    ConstructionConfig,
    ReleaseAdmissionRefused,
    RiskStateConfigError,
)
from tos_runtime.compose._venue_wiring import build_venue_service
from tos_runtime.compose._wiring import (
    _boot_services,
    _build_construction_stages,
    _build_context_resolver,
    _build_realized_stages,
    _build_stage_map,
)
from tos_runtime.nontrade.config import NONTRADE_CONFIG_NAME
from tos_runtime.rcl.log import StaleEpochRead
from tos_runtime.risk.aggregate import (
    AggregateRiskDecisionInputs,
)
from tos_runtime.risk.flow import ActionFlowDecisionInputs
from tos_runtime.riskstate.policies import (
    ACTION_FLOW_POLICY_CONFIG_NAME,
    AGGREGATE_RISK_POLICY_CONFIG_NAME,
)
from tos_runtime.riskstate.service import RiskStateService
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

#: Config file names expected directly under ``config_dir`` (each shaped like
#: its ``tos/runtime/config/*.example.yaml`` counterpart).
_TIME_CONFIG_NAME = "time.yaml"
_AUTHORITY_CONFIG_NAME = "authority.yaml"
_RISK_CONFIG_NAME = "risk.yaml"
_CURRENTNESS_CONFIG_NAME = "currentness.yaml"
_RELEASE_CONFIG_NAME = "release.yaml"

#: Where operator-authored Independent Approval decisions live, keyed by
#: proposal digest (``tos_runtime.authority.iap`` module docstring:
#: "approvals/<proposal_digest>.yaml").
_APPROVALS_DIRNAME = "approvals"


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
    """Wire the whole Phase 2 paper-runtime service chain, in order (module
    docstring: exact order + every reported deviation).

    Args:
        config_dir: Directory holding every ``*.yaml`` config (every named-TBD filled).
        data_dir: Directory for the RCL log / evidence store / emergency log.
        custody_root: The D4 custody directory.
        environment_label: Boot-argument environment label (never ``os.environ`` — D1.1).
        construction: Per-strategy Order Construction facts (steps 2/3/5/11) — :class:`ConstructionConfig`.
        aggregate_risk_inputs_provider: Supplies step 6's inputs. ``None`` (the default) uses
            the production :class:`~tos_runtime.riskstate.service.RiskStateService` instead —
            see :attr:`ComposedRuntime.risk_state`'s own docstring for the exact boot rule
            (TOS risk state service wave, plan §3 "run 차단 목록"). An explicit callable
            (the pre-existing test seam) still returns ``None`` per-request for restrictive
            UNKNOWN exactly as before.
        action_flow_inputs_provider: Supplies step 7's inputs, analogously.
        registry: An injected strategy registry — mutually exclusive with a populated strategies directory.
        authority_domain: The Safety Authority epoch's governed domain name.
        continuity_id: The ordering-event continuity id.
        allow_no_strategies: ``False`` refuses with neither source (finding #8).
        transport_kind: ``synthetic`` (the default) or ``kis-mock`` (TOS KIS MOCK transport plan
            T2 lane C — :mod:`tos_runtime.compose._transport_wiring`). Boot refuses when this
            disagrees with the active broker scope's own shape
            (:func:`~tos_runtime.compose._transport_wiring.refuse_transport_scope_mismatch`) or,
            for ``kis-mock``, when the custody principal for either KIS MOCK scope does not match
            the active scope's own principal
            (:func:`~tos_runtime.compose._transport_wiring.refuse_custody_principal_mismatch`).
        projection_path: TOS Phase 5 W4 §2 decisions 7/9/11 — where the operator projection JSON
            is exported, or ``None`` (the default) to disable export entirely. Never a fabricated
            default path.
        backup_root: TOS Phase 5 W4 §2 decision 11 — where to look for the latest durable-set
            backup manifest, or ``None`` (the default) to skip backup observation entirely.
        wall_clock: TOS Phase 5 W5 plan §2 decision 2 — the injected wall-clock reference for
            the KST session/calendar owner, or ``None`` (the default) for the production
            default (G-1, runtime operations wiring plan §2 decision 1):
            :class:`~tos_runtime.calendar.ports.TrustedWallClockReference` bound to this call's
            own ``TrustworthyTimeService`` — reads a real value once that service's boot-time
            ``evaluate()`` cycles (below) have reached ``HealthState.TRUSTED``, honestly
            ``None`` otherwise; no CLI flag overrides this default (an explicit ``wall_clock``
            argument, e.g. ``FixedWallClockReference``/``AbsentWallClockReference``, is
            test-only).

    Returns:
        The fully wired :class:`ComposedRuntime`.
    Raises:
        ReleaseAdmissionRefused / config or custody exceptions / StrategyRegistryResolutionRefused
        / :class:`~tos_runtime.compose._transport_wiring.TransportWiringError` /
        :class:`RiskStateConfigError` / :class:`~tos_runtime.compose._riskstate_wiring
        .RiskPolicyScopeMismatch`.
    """
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
    # Late-bind the ENVIRONMENT_SCOPE dimension reader's cell now the active broker
    # scope is resolved (W3.1 independent review MEDIUM-2; plan §2 decision 3) — the
    # SAME "constructed before its dependency exists" ordering already documented for
    # ACTION_FLOW/TRADING_APPROVAL below, except this one is already satisfiable right
    # here: `_boot_services` resolves `broker_scopes` internally before returning.
    boot.risk.environment_scope_dimension_state.active_scope = (
        boot.broker_scopes.active_scope
    )
    # Late-bind the RELEASE dimension reader's cell now STAGE B has actually run
    # (Phase 5 W3.2, plan §2 decision 6) — `_boot_services` only returns at all once
    # `_stage_b_release_probe` has admitted (a refusal raises instead), so this is
    # always `True` here; see `_ReleaseDimensionState`'s own docstring for why that is
    # honest, not fabricated.
    boot.risk.release_dimension_state.release_admitted = boot.release_admitted

    # TOS Phase 5 W5 (plan §2 decisions 1-5): the KST session/venue-facts owner. Built here,
    # before `_build_construction_stages`, because step 3 needs a phase reader at construction
    # time; its tick-generation reader is a late-bound cell (mirrors `_SafetyMesh`'s own inbox
    # cell, `_safety_wiring.py`) since the durable inbox does not exist until `_finalize` --
    # `apply_session_wiring` below fills it in once it does.
    # TOS venue constraint service wave (plan §2 decision 9): `calendar.yaml` is loaded EXACTLY
    # ONCE here and the SAME `CalendarConfig` is threaded into both `build_session_facts_owner`
    # (the session-phase owner) and `build_venue_service` (the admitting-phase token
    # cross-check below) — never a second file read.
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

    # Shared reader (SAME callable object at both call sites below) so step 3's own fold and
    # the send-boundary context's `observed_session_phase` field can never disagree within one
    # attempt (SessionFactsOwner.observe caches per tick generation).
    session_phase_reader = lambda: session_facts_owner.phase_for_step3(  # noqa: E731
        construction.instrument_class
    )

    # TOS venue constraint service wave (plan §2 decisions 1-9): the governed venue-constraint
    # service, built BEFORE `_build_construction_stages` (step 2 needs the loaded Order
    # Construction Policy's own coordinates; step 3 needs the live service itself). Boot
    # refusals here (policy activation / scope mismatch — `build_venue_service`'s own
    # docstring "Order of boot refusals") surface before any evidence past what
    # `_boot_services` already wrote.
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
    )

    construction_stages = _build_construction_stages(
        construction,
        venue_service=venue_service,
        loaded_ocp=loaded_ocp,
    )
    # Late-bind the CONSTRAINT dimension reader's cell now step 3's own VerdictRecorder
    # exists (Phase 5 W3.2, plan §2 decision 2).
    boot.risk.constraint_dimension_state.venue_recorder = (
        construction_stages.venue_recorder
    )
    # Late-bind the CONSTRUCTION dimension reader's cell now step 2's own stage exists
    # (Phase 5 W3.2, plan §2 decision 3).
    boot.risk.construction_dimension_state.construction_stage = (
        construction_stages.construction_stage
    )
    # TOS risk state service wave (plan §2.4/§3): decide NOW (file existence only, no I/O on
    # the not-yet-existing durable inbox) whether the production RiskStateService will supply
    # any provider the caller left `None` — a caller-supplied `None` with the two governed
    # policy files ALSO absent is a production-boot refusal (`RiskStateConfigError`), never a
    # silent "every attempt is UNKNOWN forever" runtime. The service ITSELF is constructed
    # later, right where `venue_service` is attached below, because `InboxFlowReader` needs
    # the REAL durable inbox `_finalize` has not built yet at this point in the function (the
    # SAME "constructed before its dependency exists" ordering already documented for
    # `_ActionFlowDimensionState`/`_RecoveryDimensionState` above) — `_risk_state_cell` is the
    # late-bound slot both thunks below close over; `composed.risk_state` is filled from the
    # SAME cell once the real service exists, so a caller never observes a torn state.
    risk_state_files_exist = (
        config_dir / AGGREGATE_RISK_POLICY_CONFIG_NAME
    ).is_file() and (config_dir / ACTION_FLOW_POLICY_CONFIG_NAME).is_file()
    if not risk_state_files_exist and (
        aggregate_risk_inputs_provider is None or action_flow_inputs_provider is None
    ):
        raise RiskStateConfigError(
            f"{config_dir}: aggregate_risk_policy.yaml/action_flow_policy.yaml are not both "
            "present, and at least one of aggregate_risk_inputs_provider/"
            "action_flow_inputs_provider was left None — refusing to boot with a permanently "
            "UNKNOWN step 6/7 (TOS risk state service wave plan §3)"
        )
    risk_state_cell: dict[str, RiskStateService | None] = {"service": None}

    def _aggregate_provider(
        request: StageRequest,
    ) -> AggregateRiskDecisionInputs | None:
        if aggregate_risk_inputs_provider is not None:
            return aggregate_risk_inputs_provider(request)
        service = risk_state_cell["service"]
        return None if service is None else service.aggregate_inputs_for(request)

    def _action_flow_provider(request: StageRequest) -> ActionFlowDecisionInputs | None:
        if action_flow_inputs_provider is not None:
            return action_flow_inputs_provider(request)
        service = risk_state_cell["service"]
        return None if service is None else service.action_flow_inputs_for(request)

    realized = _build_realized_stages(
        infra=boot.infra,
        rcl=boot.rcl,
        risk=boot.risk,
        construction_stages=construction_stages,
        construction=construction,
        aggregate_risk_inputs_provider=_aggregate_provider,
        action_flow_inputs_provider=_action_flow_provider,
        custody_root=custody_root,
        environment_label=environment_label,
        uid=uid,
    )
    # Late-bind the ACTION_FLOW / TRADING_APPROVAL dimension readers' cells now steps
    # 9/4's VerdictRecorders exist (Phase 5 W3-b, plan §2 decision 3).
    boot.risk.action_flow_dimension_state.step9_recorder = realized.step9_recorder
    boot.risk.trading_approval_dimension_state.step4_recorder = realized.step4_recorder
    # Late-bind the DECISION_PROOF_INTENT dimension reader's cell now step 13's own
    # VerdictRecorder exists (Phase 5 W3.2, plan §2 decision 2).
    boot.risk.decision_proof_intent_dimension_state.step13_recorder = (
        realized.step13_recorder
    )
    stages = _build_stage_map(construction_stages, realized)

    # T2 lane C: a kis-mock boot binds the genuine KIS wire-codec digest into the context
    # resolver (closing the T2 lane A gap for THIS wiring path) — synthetic keeps the stand-in.
    request_bytes_digest_source = (
        KisWireCodecDigest(
            field_map=boot.transport_config.field_map,
            static_body_fields=boot.transport_config.static_body_fields,
        )
        if boot.transport_config is not None
        else None
    )
    context_resolver = _build_context_resolver(
        construction_stages=construction_stages,
        realized=realized,
        flow_governor=boot.risk.flow_governor,
        currentness_assembler=boot.risk.currentness_assembler,
        proof_issuer=boot.risk.proof_issuer,
        pending_dimension_specs=boot.risk.pending_dimension_specs,
        session_facts_current_reader=lambda: session_facts_owner.session_facts_current(
            construction.instrument_class,
        ),
        tradability_facts_current_reader=lambda: session_facts_owner.tradability_facts_current(
            broker_reaching=is_broker_reaching(boot.broker_scopes.active_scope),
        ),
        account_facts_current_reader=lambda: session_facts_owner.account_facts_current(
            broker_reaching=is_broker_reaching(boot.broker_scopes.active_scope),
        ),
        observed_session_phase_reader=session_phase_reader,
        egress_coordinates=boot.egress_coordinates,
        broker_scopes=boot.broker_scopes,
        instance_document=boot.instance_document,
        construction=construction,
        environment_label=environment_label,
        continuity_id=continuity_id,
        authority_epoch_service=boot.rcl.authority_epoch_service,
        safety_mesh=boot.risk.safety_mesh,
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
        # The broker-acknowledged result's KST trading date, through the SAME trusted wall
        # clock and calendar as every session phase (plan 2026-09-26 egress trading date).
        trading_date_now=lambda: session_facts_owner.trading_date_now(
            construction.instrument_class
        ),
    )
    # TOS venue constraint service wave (plan §2 decision 9) — attach the already-live venue
    # service to the composed runtime (the service itself was built earlier, above, before
    # `_build_construction_stages`; this just publishes it on `ComposedRuntime.venue`, mirroring
    # `apply_session_wiring`'s own "attach the already-built owner" idiom below).
    composed.venue = venue_service
    # Late-bind the safety-mesh inbox cell now the durable inbox exists (Phase 5 W3-b,
    # plan §2 decision 6/8) — RestrictiveLatchOwner's new-risk-halt reader and
    # MonitoringService's inbox-backlog observer both close over this cell.
    boot.risk.safety_mesh.inbox_cell.inbox = composed.inbox
    # TOS risk state service wave (plan §2.4) — build the real RiskStateService now the
    # durable inbox exists (`InboxFlowReader` needs it), fill the late-bound cell the two
    # thunks above already close over, and attach it to the composed runtime. Only when the
    # two governed policy files exist (the `risk_state_files_exist` decision, above) — a
    # caller that supplied both explicit providers with the files absent legitimately keeps
    # `risk_state` at its `None` default (the pre-existing test seam).

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
            hse_envelope=boot.risk.safety_mesh.profile_service.envelope,
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
        )
    composed.risk_state = risk_state_cell["service"]
    # TOS Phase 5 W5 — late-bind the session-facts owner's own tick-generation cell now
    # the durable inbox exists (same ordering as the safety-mesh cell above), and attach
    # the owner to the composed runtime.
    composed = apply_session_wiring(
        composed,
        session_inbox_cell=session_inbox_cell,
        session_facts_owner=session_facts_owner,
    )
    # TOS runtime operations wiring plan §2 decision 3 + follow-up (originally W5 plan §2
    # decision 7, rollover) — the ONE honest venue-admissibility provider, built once and
    # shared by the dry-run non-trade processor AND observe_nontrade's engine path
    # (build_nontrade_admissibility_provider's own docstring), PLUS the engine driver's shared
    # new-risk latch bind (apply_nontrade_wiring's own docstring — both independent of whether
    # a nontrade.yaml exists at all). The dry-run processor itself stays optional: a config_dir
    # with no nontrade.yaml at all (every compose e2e test that predates this wiring) leaves
    # composed.nontrade None, exactly like projection_path/backup_root's own optionality —
    # never a boot refusal for a caller that has not configured this yet.
    nontrade_admissibility_provider = build_nontrade_admissibility_provider(
        construction=construction,
        venue_service=venue_service,
        session_phase_reader=session_phase_reader,
    )
    composed = apply_nontrade_wiring(
        composed,
        nontrade_processor=(
            build_nontrade_processor(
                config_dir=config_dir,
                admissibility_provider=nontrade_admissibility_provider,
            )
            if (config_dir / NONTRADE_CONFIG_NAME).is_file()
            else None
        ),
        admissibility_provider=nontrade_admissibility_provider,
    )
    # TOS Phase 5 W2-R (plan §10 row ①③) — attach the finality release consumer BEFORE the
    # recovery barrier runs (see apply_release_wiring's own docstring for why running before a
    # possible driver detach is harmless).
    composed = apply_release_wiring(
        composed,
        config_dir=config_dir,
        scheme=_SCHEME,
        monotonic_source=boot.infra.monotonic_source,
        post_trade_dimension_state=boot.risk.post_trade_dimension_state,
    )
    composed = apply_recovery_barrier(
        composed,
        config_dir=config_dir,
        data_dir=data_dir,
        custody_root=custody_root,
        scheme=_SCHEME,
    )
    # Late-bind the RECOVERY dimension reader's cell now the barrier has actually run
    # (Phase 5 W3-b, plan §2 decision 3) — strictly before this function ever hands
    # `composed` to a caller that could drive an attempt (_RecoveryDimensionState's own
    # docstring).
    boot.risk.recovery_dimension_state.verdict = composed.recovery
    # TOS tick-source wave (plan §2 decisions 1-9) — build the tick scheduler now
    # `composed.driver` reflects the FINAL post-barrier value (`_marketfeed_wiring.py`'s own
    # module docstring on why this must run after `apply_recovery_barrier`, unlike `venue`
    # above). `None` when `marketfeed.yaml` is absent — an operator who has not adopted this
    # wave yet, never a boot refusal.
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
        broker_scopes=boot.broker_scopes,
        runtime_identity=boot.identity,
    )
    # TOS Phase 5 W4 (plan §2 decision 11) — operations facts + (optional) operator
    # projection, wired last: every durable fact this reads (evidence/RCL/inbox,
    # release_admitted, recovery) already exists by this point.
    composed = apply_operations_wiring(
        composed, projection_path=projection_path, backup_root=backup_root
    )
    return composed
