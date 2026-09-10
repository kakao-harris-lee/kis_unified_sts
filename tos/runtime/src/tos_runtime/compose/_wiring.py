"""``tos_runtime.compose`` phase-wiring helpers — split out of root.py
purely for the size budget (tools/tos_size_budget.py file-level + per-
function limits); no behavioural difference from having them inline in
root.py. :func:`~tos_runtime.compose.root.compose_paper_runtime` is the
orchestrator that calls these, in the design #40 §5 order.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tos.authority import AuthorityTransitionReason
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.egress import EgressCoordinateSet
from tos.egressgw import (
    ConformanceProofStage,
    EconomicEffectStage,
    OrderConstructionStage,
    VenueConstraintStage,
)
from tos.engine import (
    CommitmentStep,
    EngineConfiguration,
    StageRequest,
    StrategyRegistry,
)
from tos.engine.records import InstrumentKey
from tos.iap import ApprovalResult, IndependentApprovalDecision, exact_binding_holds
from tos.time import HealthState
from tos.workload import RuntimeIdentity

from tos_runtime.authority.epoch import (
    AuthorityRuntimeConfig,
    SafetyAuthorityEpochService,
    load_authority_config,
)
from tos_runtime.authority.iap import (
    IntentRegistry,
    LoadedApproval,
    OperatorApprovalFileError,
    load_operator_approval_with_receipt,
)
from tos_runtime.authority.stages import IndependentApprovalStage
from tos_runtime.brokercap import (
    BrokerScopesConfig,
    InstanceDocument,
    credential_route_inventory,
    load_active_instance_document,
    load_broker_scopes,
    refuse_principal_collision,
    transport_nature,
)
from tos_runtime.compose._boot_integrity import (
    record_operator_attested_inputs,
    verify_rcl_log_or_halt,
)
from tos_runtime.compose._currentness_wiring import (
    _build_risk_and_currentness,
    _RiskAndCurrentness,
)
from tos_runtime.compose._egress_attestations import EgressAttestations
from tos_runtime.compose._egress_coordinates import (
    EgressCoordinatesConfig,
    load_egress_coordinates,
)
from tos_runtime.compose._engine_config import load_engine_config
from tos_runtime.compose._engine_wiring import (
    ENGINE_DRIVER_CONFIG_NAME,
    load_engine_driver_config,
    verify_replay_or_halt,
    wire_engine_and_driver,
)
from tos_runtime.compose._pending_dimensions import PendingDimensionSpec
from tos_runtime.compose._preconditions import (
    COORDINATOR_PRECONDITIONS_CONFIG_NAME,
    load_coordinator_preconditions_config,
)
from tos_runtime.compose._request_digest import (
    CapsuleStandInDigest,
    RequestBytesDigestSource,
)
from tos_runtime.compose._risk_attestations import (
    wrap_action_flow_inputs_provider,
    wrap_aggregate_risk_inputs_provider,
)
from tos_runtime.compose._types import (
    ComposedRuntime,
    ConstructionConfig,
    ReleaseAdmissionRefused,
)
from tos_runtime.compose.context import (
    ComposeContextResolver,
    RecordingActionFlowGovernor,
    VerdictRecorder,
    make_permit_provider,
)
from tos_runtime.currentness.proof import EgressCurrentnessProofIssuer
from tos_runtime.currentness.stages import (
    AttemptBindVerificationStage,
    TransmissionCapabilityContext,
    TransmissionCapabilityStage,
)
from tos_runtime.currentness.vector import CurrentnessAssembler
from tos_runtime.custody.file_custody import FileCustody
from tos_runtime.custody.key_provider import FileKeyProvider
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.ports import EvidenceAppendPort
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.config import load_finality_config
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.release.admission import ReleaseAdmissionService
from tos_runtime.release.config import load_release_config
from tos_runtime.risk.aggregate import (
    AggregateRiskDecisionInputs,
)
from tos_runtime.risk.flow import ActionFlowDecisionInputs
from tos_runtime.risk.ledger_stages import (
    ActionFlowDecisionStage,
    AggregateRiskDecisionStage,
    AtomicCommitStage,
    CommitmentUnavailabilityStage,
    LedgerVerificationStage,
)
from tos_runtime.strategy.resolve import (
    ResolvedStrategyRegistry,
    resolve_strategy_registry,
)
from tos_runtime.time.config import TrustworthyTimeConfig, load_time_config
from tos_runtime.time.generation import seed_from
from tos_runtime.time.service import TimeServiceNotStarted, TrustworthyTimeService
from tos_runtime.time.sources import (
    LocalSystemClockReader,
    MonotonicSource,
    ProcessMonotonicSource,
)

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Config file names expected directly under ``config_dir`` (each shaped like
#: its ``tos/runtime/config/*.example.yaml`` counterpart).
_TIME_CONFIG_NAME = "time.yaml"
_AUTHORITY_CONFIG_NAME = "authority.yaml"
_RISK_CONFIG_NAME = "risk.yaml"
_CURRENTNESS_CONFIG_NAME = "currentness.yaml"
_CURRENTNESS_DIMENSIONS_CONFIG_NAME = "currentness_dimensions.yaml"
_RELEASE_CONFIG_NAME = "release.yaml"
_EGRESS_COORDINATES_CONFIG_NAME = "egress_coordinates.yaml"
#: TOS Phase 4 plan §2 decisions 1-2 (G-4) — the runtime-configured Broker
#: Scope table :mod:`tos_runtime.brokercap.scopes` loads.
_BROKER_SCOPES_CONFIG_NAME = "broker_scopes.yaml"
#: TOS Phase 3 Wave 2 Lane C-R follow-up (team-lead CR-4 dispatch, plan §2.2) — the SYNTHETIC
#: post-trade finality policy (:mod:`tos_runtime.posttrade.config`).
_FINALITY_CONFIG_NAME = "finality.yaml"

#: Where operator-authored Independent Approval decisions live, keyed by
#: proposal digest (``tos_runtime.authority.iap`` module docstring:
#: "approvals/<proposal_digest>.yaml").
_APPROVALS_DIRNAME = "approvals"


def _time_permits_new_risk(time_service: TrustworthyTimeService) -> Callable[[], bool]:
    """Re-review addendum B (2026-09-08): the catch below is narrowed to
    ``TimeServiceNotStarted`` only — the ONE exception
    ``TrustworthyTimeService.current_snapshot`` raises before ``start()``
    or the first successful ``evaluate()`` (``tos_runtime/time/service.py``,
    ``current_snapshot``'s own docstring + ``_require_started``, lines
    187-201). A previous bare catch-all also hid programming errors as a
    silent time refusal; everything else now propagates."""

    def _check() -> bool:
        try:
            snapshot = time_service.current_snapshot()
        except TimeServiceNotStarted:
            return False
        from tos.time import state_permits_new_normal_risk

        return state_permits_new_normal_risk(snapshot.health_state) is True

    return _check


def _rcl_tip_generation_provider(
    rcl_log: SqliteCommitLog, writer_epoch: int
) -> Callable[[StageRequest], int]:
    """A ``GenerationProvider`` (snapshot/decision generation, step 6; also
    used as ``permit_generation_provider``, step 9) derived from the RCL
    log's own current linearizable tip sequence — never a fabricated
    constant (team-lead follow-up guidance, 2026-09-08).

    ``AggregateRiskService.decide``/``ActionFlowGovernor.build_permit`` need
    these generation numbers to CREATE a snapshot/decision/permit's own
    identity digest — they cannot be read back FROM the not-yet-created
    artifact, so the only real, structurally-derived, monotonically
    advancing number this composition can supply at that point is the log's
    own tip at the moment of the call (the same real artifact ACTION_FLOW's
    own currentness dimension reader already keys off,
    :func:`_action_flow_dimension_reader_for`).

    Returns ``0`` only for a genuinely empty log with no committed tip yet
    — never for a log-read failure. ``StaleEpochRead``/``sqlite3.Error``/
    ``OSError`` propagate unchanged (re-review finding F2, 2026-09-08: a
    swallowed failure here previously returned ``0`` for two DIFFERENT
    decisions across a transient failure, breaking the forward-only
    ``(decision_id, decision_generation, digest)`` monotonicity
    ``tos.are.predicates`` assumes). ``AggregateRiskDecisionStage.__call__``
    calls both generation providers INSIDE its own ``try/except`` (step 6),
    so a propagated failure there maps to ``UNKNOWN`` correctly; the step-9
    permit path has no such enclosing guard, so
    :func:`~tos_runtime.compose.context.make_permit_provider` catches this
    provider's propagated failure itself and reports "no permit" (also
    ``UNKNOWN``, never a fabricated generation) — see that function's own
    docstring.
    """

    def _provider(_request: StageRequest) -> int:
        view = rcl_log.read_linearizable(writer_epoch=writer_epoch)
        return 0 if view.last_seq is None else view.last_seq

    return _provider


def _decision_provider(
    custody_root: Path,
    environment_label: str,
    uid: int,
    time_service: TrustworthyTimeService,
    time_config: TrustworthyTimeConfig,
    evidence: EvidenceAppendPort,
) -> Callable[[StageRequest], LoadedApproval | None]:
    """Lazily loads the operator approval file bound to a proposal's own
    digest (``approvals/<proposal_digest>.yaml``) — never computed, never
    cached across a restart (module docstring; ``tos_runtime.authority.iap``
    "zero auto-approval"). Uses ``load_operator_approval_with_receipt``
    (re-review finding #3) so the resolved ``LoadedApproval`` carries the
    receipt facts ``IndependentApprovalStage`` threads into expiry — this is
    the ONE call site that closes G-1's "expiry path unwired" gap.

    Re-review finding #7 (LOW): a refusal — a malformed/refused file, as
    opposed to no file at all — is durably recorded as
    ``IAP_APPROVAL_FILE_REFUSED`` before this swallows it to ``None``, so an
    operator's expiry-or-custody-refused intent stays visible instead of
    reading identically to "no decision authored yet"."""
    approvals_dir = custody_root / _APPROVALS_DIRNAME

    def _provider(request: StageRequest) -> LoadedApproval | None:
        proposal = request.proposal
        digest = getattr(proposal, "canonical_digest", None)
        if digest is None:
            return None
        path = approvals_dir / f"{digest}.yaml"
        if not path.is_file():
            return None
        try:
            return load_operator_approval_with_receipt(
                path,
                time=time_service,
                time_config=time_config,
                expected_owner_uid=uid,
                environment_label=environment_label,
            )
        except OperatorApprovalFileError as exc:
            evidence.append(
                {"path": str(path), "error": str(exc)},
                kind="IAP_APPROVAL_FILE_REFUSED",
                record_class="IAP_APPROVAL_FILE_REFUSED",
            )
            return None

    return _provider


# ===========================================================================
# compose_paper_runtime's own phase helpers (tos_size_budget.py decompose —
# each phase stays under the 100-line function budget; compose_paper_runtime
# itself is the orchestrator, calling these in the design #40 §5 order).
# ===========================================================================


def _build_identity(environment_label: str) -> RuntimeIdentity:
    """This process's :class:`~tos.workload.RuntimeIdentity` — pure
    computation, no I/O (so a STAGE A release-admission probe can run
    against it before any file is opened)."""
    return RuntimeIdentity(
        cell_id=environment_label,
        runtime_generation=0,
        process_nonce=secrets.token_hex(8),
        code_digest=_SCHEME.compute_digest({"component": "tos_runtime.compose"}),
    )


def _stage_a_release_probe(
    release_service: ReleaseAdmissionService,
    release_config: object,
    identity: RuntimeIdentity,
) -> None:
    """STAGE A release-admission probe (reported deviation from the plan's
    literal listed order — see :func:`compose_paper_runtime`'s own module
    docstring "Release admission is moved ahead of custody/evidence/RCL").

    ``tos.sci.software_deployment_ok_verdict`` hard-requires
    ``active_currentness_current is True`` — a genuinely per-attempt,
    post-currentness-wiring fact that cannot exist before the RCL/time/
    currentness stack is up. But the compose e2e test's scenario 7 requires
    "release admission refusal => compose raises before any service starts
    (assert no sqlite files created)" for the ordinary refusal case (an
    operator-approved ``expected_code_digest`` that does not match this
    build) — that particular fact (``identity.code_digest ==
    expected_code_digest``) is pure computation, no I/O, available
    immediately. So release admission runs TWICE: this STAGE A probe, with
    ``currentness_current`` forced to ``True`` so ONLY the digest/admission-
    result/restriction facts can fail it (never a false pass — Stage A can
    only ever refuse EARLIER than the truth, never admit something Stage B
    would refuse), and a STAGE B check later (:func:`_stage_b_release_probe`,
    once currentness is actually wired) with the REAL, honestly-derived
    boot-time currentness signal.

    Raises:
        ReleaseAdmissionRefused: The probe denies.
    """
    stage_a_admitted = release_service.decide(identity, currentness_current=True)
    if not stage_a_admitted:
        raise ReleaseAdmissionRefused(
            "compose_paper_runtime: release admission denied at the "
            f"pre-I/O STAGE A probe ({release_config!r}) — refusing to "
            "construct any custody/evidence/RCL/engine/gateway service "
            "(slice plan §4 item 1 fail-closed boot refusal)"
        )


@dataclass
class _Infra:
    custody: FileCustody
    key_provider: FileKeyProvider
    evidence_store: SqliteEvidenceStore
    emergency_log: EmergencyAppendLog
    time_service: TrustworthyTimeService
    time_config: TrustworthyTimeConfig
    #: The RESOLVED monotonic source (never ``None`` here, unlike the caller-facing optional
    #: parameter) — TOS Phase 3 Wave 1 Lane A-R's ``EngineDriver`` timeout injection reuses the
    #: SAME source ``TrustworthyTimeService`` was built with, rather than reading a second,
    #: independent ``time.monotonic()`` (design #40 D1.1 "never an ambient clock read").
    monotonic_source: MonotonicSource


def _build_custody_evidence_time(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    environment_label: str,
    identity: RuntimeIdentity,
    uid: int,
    monotonic_source: MonotonicSource | None,
) -> _Infra:
    """custody / evidence store (``FileKeyProvider``) / emergency log /
    Trustworthy Time (``start()`` + two boot-time ``evaluate()`` cycles) —
    design #40 §5 order 1, D3/D4."""
    resolved_monotonic_source = (
        monotonic_source if monotonic_source is not None else ProcessMonotonicSource()
    )
    key_provider = FileKeyProvider(custody_root, expected_owner_uid=uid)
    evidence_store = SqliteEvidenceStore(
        data_dir / "evidence.sqlite3", key_provider=key_provider
    )
    custody = FileCustody(
        custody_root,
        environment_label=environment_label,
        expected_owner_uid=uid,
        evidence=evidence_store,
    )
    emergency_log = EmergencyAppendLog(data_dir / "emergency.jsonl")

    time_config = load_time_config(config_dir / _TIME_CONFIG_NAME)
    time_service = TrustworthyTimeService(
        monotonic=resolved_monotonic_source,
        references=(LocalSystemClockReader(),),
        config=time_config,
        identity=identity,
        evidence=evidence_store,
    )
    time_service.start()
    # Two health-check cycles: UNINITIALIZED -> SYNCHRONIZING -> TRUSTED
    # (tos_runtime.time.service's own state-machine table). Compose runs
    # these two ONCE, at boot, only so the Stage B release-admission check
    # has a real, non-vacuous "is time currently TRUSTED" fact to derive its
    # boot-time currentness signal from; ONGOING health-check cycles past
    # this point remain the caller's own job (no daemon loop here —
    # cli.py's own module docstring).
    time_service.evaluate()
    time_service.evaluate()

    return _Infra(
        custody=custody,
        key_provider=key_provider,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        time_service=time_service,
        time_config=time_config,
        monotonic_source=resolved_monotonic_source,
    )


@dataclass
class _RclAndAuthority:
    rcl_log: SqliteCommitLog
    writer_epoch: int
    authority_epoch_service: SafetyAuthorityEpochService
    intent_registry: IntentRegistry


def _build_rcl_and_authority(
    data_dir: Path,
    config_dir: Path,
    identity: RuntimeIdentity,
    evidence_store: SqliteEvidenceStore,
    time_service: TrustworthyTimeService,
    time_config: TrustworthyTimeConfig,
    authority_domain: str,
) -> _RclAndAuthority:
    """RCL log (``acquire_epoch`` + generation seed) + Safety Authority epoch
    service + Intent Registry — design #40 §5 order 3-4."""
    rcl_log = SqliteCommitLog(data_dir / "rcl.sqlite3", evidence_port=evidence_store)
    writer_epoch = rcl_log.acquire_epoch(identity, runtime_generation=0)
    # Seeded for parity with design #40 D1.1 ("runtime_generation은 D2 epoch와
    # 같은 트랜잭션에서 증가"); not separately consumed by this compose root.
    seed_from(rcl_log)

    authority_config: AuthorityRuntimeConfig = load_authority_config(
        config_dir / _AUTHORITY_CONFIG_NAME
    )
    authority_epoch_service = SafetyAuthorityEpochService(
        rcl_log,
        time_service,
        evidence_store,
        authority_domain=authority_domain,
        writer_epoch=writer_epoch,
        config=authority_config,
    )
    authority_epoch_service.transition(
        leader_identity=identity.process_nonce or "compose-root",
        transition_reason=AuthorityTransitionReason.EXPLICIT_ADMINISTRATIVE_REVOCATION,
    )
    # load_authority_config fail-closed-resolves this to a positive int
    # (never None) — asserted here only to narrow the type for mypy.
    policy_generation = authority_config.trading_approval_policy_generation
    assert policy_generation is not None
    intent_registry = IntentRegistry(
        rcl_log,
        evidence_store,
        writer_epoch=writer_epoch,
        trading_approval_policy_generation=policy_generation,
        # re-review finding #3: removes two of G-1's three wiring blockers.
        # Two REAL-service blockers remain, both in the time service's own
        # snapshot issuance (time/service.py::_issue_snapshot): it populates
        # neither ``wall_clock_observation`` nor
        # ``suspension_status.suspension_ms`` (the latter became load-bearing
        # once finding #2 made IAP read the OBSERVED suspension), so a
        # configured ``max_decision_age_ms`` denies fail-closed until the
        # slice-#1 time design revisits both (operator gate, not this round).
        time=time_service,
        time_config=time_config,
    )

    return _RclAndAuthority(
        rcl_log=rcl_log,
        writer_epoch=writer_epoch,
        authority_epoch_service=authority_epoch_service,
        intent_registry=intent_registry,
    )


def _stage_b_release_probe(
    release_service: ReleaseAdmissionService,
    identity: RuntimeIdentity,
    time_service: TrustworthyTimeService,
    rcl_log: SqliteCommitLog,
) -> bool:
    """STAGE B release admission — the real, honestly-derived boot-time
    currentness signal (see :func:`_stage_a_release_probe`'s own docstring
    for why this is a SEPARATE, later check).

    ``currentness_current`` here is deliberately NOT
    ``tos.cur.predicates.vector_complete`` over the full per-attempt Safety
    Currentness Vector — even though that vector now genuinely reaches
    complete for a well-formed attempt (4 structurally-owned dimensions +
    17 operator-attested pending dimensions, see
    :mod:`tos_runtime.compose._pending_dimensions`), it is answering a
    DIFFERENT question here anyway (is THIS attempt's currentness current,
    not is the deployed software's own operating posture current — what
    ``tos.sci``'s release gate actually asks). The boot-time proxy
    used here — Trustworthy Time reports ``TRUSTED`` AND the RCL Writer
    Epoch was positively acquired — is the compose root's own honestly-
    observed, non-fabricated currentness fact at the moment of composition.

    Returns:
        Whether release admission holds (``True`` always, when this
        function returns at all — it raises otherwise).

    Raises:
        ReleaseAdmissionRefused: The probe denies.
    """
    boot_currentness_current = (
        time_service.health_state is HealthState.TRUSTED and rcl_log.current_epoch() > 0
    )
    release_admitted = release_service.decide(
        identity, currentness_current=boot_currentness_current
    )
    if not release_admitted:
        raise ReleaseAdmissionRefused(
            "compose_paper_runtime: release admission denied at STAGE B "
            f"(boot_currentness_current={boot_currentness_current!r}) — "
            "refusing to construct any engine/gateway service (slice plan "
            "§4 item 1 fail-closed boot refusal)"
        )
    return release_admitted


@dataclass
class _ConstructionStages:
    construction_stage: OrderConstructionStage
    venue_stage: VenueConstraintStage
    economic_stage: EconomicEffectStage
    proof_stage: ConformanceProofStage


def _build_construction_stages(construction: ConstructionConfig) -> _ConstructionStages:
    """Steps 2/3/5/11 — the kernel's OWN, already-shipped Order Construction
    stages (design #34 §3.2)."""
    construction_stage = OrderConstructionStage(
        envelope=construction.envelope,
        price=construction.price,
        venue_constraint=construction.venue_constraint,
        scheme=_SCHEME,
        intent_id=f"intent-{construction.account}-{construction.instrument}",
        intent_version="intent-v1",
        envelope_id="compose-envelope",
        policy_id="compose-ocp",
        policy_version="ocp-v1",
        policy_generation=1,
        command_id=f"cmd-{construction.account}-{construction.instrument}",
        generation=1,
        price_field_key=construction.price_field_key,
    )
    venue_stage = VenueConstraintStage(
        observed_session_phase=construction.observed_session_phase,
        action_class=construction.action_class,
        snapshot=construction.venue_snapshot,
        policy=construction.venue_policy,
        shape=construction.order_shape,
        constraints=construction.venue_shape_constraints,
        decision=construction.venue_decision,
        shape_price_field_key=construction.shape_price_field_key,
    )
    economic_stage = EconomicEffectStage(construction_stage=construction_stage)
    proof_stage = ConformanceProofStage(
        construction_stage=construction_stage,
        scheme=_SCHEME,
        proof_id=f"ocp-proof-{construction.account}-{construction.instrument}",
        proof_generation=1,
        required_authority_scope=(f"scope-{construction.instrument}",),
    )
    return _ConstructionStages(
        construction_stage=construction_stage,
        venue_stage=venue_stage,
        economic_stage=economic_stage,
        proof_stage=proof_stage,
    )


@dataclass
class _RealizedStages:
    step4_recorder: VerdictRecorder
    step6_stage: AggregateRiskDecisionStage
    step7_stage: ActionFlowDecisionStage
    step8_stage: LedgerVerificationStage
    step9_recorder: VerdictRecorder
    step10_stage: CommitmentUnavailabilityStage
    step13_stage: AttemptBindVerificationStage
    step14_stage: TransmissionCapabilityStage


def _build_step4_recorder(
    intent_registry: IntentRegistry,
    construction_stage: OrderConstructionStage,
    custody_root: Path,
    environment_label: str,
    uid: int,
    infra: _Infra,
) -> VerdictRecorder:
    """Step 4 (``IndependentApprovalStage``), wrapped for verdict recording."""

    def _consuming_command_identity(request: StageRequest, decision: object) -> str:
        # ⚠ structural (구조 파생 > 자기신고): reads step 2's own already-built
        # candidate command, never a caller-supplied claim. Step 4 runs after
        # step 2 in COMMITMENT_FLOW_ORDER, so construction_stage.construction
        # is already populated by the time this provider is called.
        artifact = construction_stage.construction
        if artifact is not None and artifact.command is not None:
            return artifact.command.command_id or ""
        return getattr(request.proposal, "canonical_digest", None) or ""

    def _consuming_command_digest(request: StageRequest, decision: object) -> str:
        artifact = construction_stage.construction
        if artifact is not None and artifact.command is not None:
            return artifact.command.canonical_digest or ""
        return ""

    def _envelope_equivalent_provider(
        _request: StageRequest, decision: IndependentApprovalDecision
    ) -> bool | None:
        """Structural derivation (team-lead follow-up guidance, 2026-09-08):
        compares the operator decision's OWN ``approved_intent_envelope_digest``
        against the ACTUAL ``tos.ioc.ApprovedIntentContract`` step 2
        (``OrderConstructionStage``, same synchronous flow, already runs
        before step 4 in ``COMMITMENT_FLOW_ORDER``) already built — via
        ``tos.iap.exact_binding_holds`` (§13's bidirectional set comparison),
        never a caller-supplied claim. ``None`` (UNKNOWN) when step 2 has not
        yet produced an intent for this attempt — never assumed-equal."""
        artifact = construction_stage.construction
        if artifact is None or artifact.intent is None:
            return None
        binding = exact_binding_holds(
            {"approved_intent_envelope": decision.approved_intent_envelope_digest},
            {"approved_intent_envelope": artifact.intent.canonical_digest},
        )
        if binding is ApprovalResult.APPROVE:
            return True
        if binding is ApprovalResult.DENY:
            return False
        return None

    return VerdictRecorder(
        IndependentApprovalStage(
            intent_registry,
            decision_provider=_decision_provider(
                custody_root,
                environment_label,
                uid,
                infra.time_service,
                infra.time_config,
                infra.evidence_store,
            ),
            command_identity_provider=_consuming_command_identity,
            command_digest_provider=_consuming_command_digest,
            # decision_current_provider omitted (team-lead follow-up guidance,
            # 2026-09-08): IndependentApprovalStage's own default now calls
            # registry.decision_current(decision) — lane P's real derivation
            # (policy-generation equality + log-derived supersession, see
            # tos_runtime.authority.iap's "Decision currency has no kernel
            # predicate" section). Compose need not re-wrap it in a lambda.
            envelope_equivalent_provider=_envelope_equivalent_provider,
        )
    )


def _build_realized_stages(
    *,
    infra: _Infra,
    rcl: _RclAndAuthority,
    risk: _RiskAndCurrentness,
    construction_stages: _ConstructionStages,
    construction: ConstructionConfig,
    aggregate_risk_inputs_provider: Callable[
        [StageRequest], AggregateRiskDecisionInputs | None
    ],
    action_flow_inputs_provider: Callable[
        [StageRequest], ActionFlowDecisionInputs | None
    ],
    custody_root: Path,
    environment_label: str,
    uid: int,
) -> _RealizedStages:
    """Steps 4, 6-10, 13, 14 — the real runtime Stages (never stand-ins)."""
    rcl_log, writer_epoch = rcl.rcl_log, rcl.writer_epoch
    intent_registry = rcl.intent_registry
    risk_service, flow_governor = risk.risk_service, risk.flow_governor
    projection = risk.projection
    construction_stage = construction_stages.construction_stage
    proof_stage = construction_stages.proof_stage
    step4_recorder = _build_step4_recorder(
        intent_registry, construction_stage, custody_root, environment_label, uid, infra
    )
    time_gate = _time_permits_new_risk(infra.time_service)
    generation_provider = _rcl_tip_generation_provider(rcl_log, writer_epoch)

    # Re-review finding F4 (2026-09-08): the caller-supplied inputs
    # providers stay scenario-specific (cells/cause/snapshot/...), but the
    # six step 6/7 admission witnesses with no Phase 2 producer are ALWAYS
    # overridden here from operator-attested config — never a caller
    # literal — and generation_current is ALWAYS derived, never attested
    # (see tos_runtime.compose._risk_attestations's own module docstring).
    step6_stage = AggregateRiskDecisionStage(
        risk_service,
        inputs_provider=wrap_aggregate_risk_inputs_provider(
            aggregate_risk_inputs_provider, risk.risk_attestations
        ),
        snapshot_generation_provider=generation_provider,
        decision_generation_provider=generation_provider,
        time_permits_new_risk=time_gate,
    )
    step7_stage = ActionFlowDecisionStage(
        flow_governor,
        inputs_provider=wrap_action_flow_inputs_provider(
            action_flow_inputs_provider,
            risk.risk_attestations,
            generation_provider,
        ),
        time_permits_new_risk=time_gate,
    )
    step8_stage = LedgerVerificationStage(
        rcl_log, projection, writer_epoch=writer_epoch
    )
    permit_provider = make_permit_provider(
        flow_governor,
        permit_generation_provider=generation_provider,
        command_identity_provider=lambda request: request.proposal.canonical_digest
        or "",
    )
    step9_recorder = VerdictRecorder(
        AtomicCommitStage(
            rcl_log,
            writer_epoch=writer_epoch,
            permit_provider=permit_provider,
            reservation_id_provider=lambda request: (
                f"resv-{request.instrument_key.account}-"
                f"{request.instrument_key.instrument}"
            ),
            time_permits_new_risk=time_gate,
        )
    )
    step10_stage = CommitmentUnavailabilityStage(projection)
    step13_stage, step14_stage = _build_currentness_stages(
        rcl_log=rcl_log,
        writer_epoch=writer_epoch,
        proof_stage=proof_stage,
        flow_governor=flow_governor,
        step4_recorder=step4_recorder,
        construction=construction,
    )
    return _RealizedStages(
        step4_recorder=step4_recorder,
        step6_stage=step6_stage,
        step7_stage=step7_stage,
        step8_stage=step8_stage,
        step9_recorder=step9_recorder,
        step10_stage=step10_stage,
        step13_stage=step13_stage,
        step14_stage=step14_stage,
    )


def _build_currentness_stages(
    *,
    rcl_log: SqliteCommitLog,
    writer_epoch: int,
    proof_stage: ConformanceProofStage,
    flow_governor: RecordingActionFlowGovernor,
    step4_recorder: VerdictRecorder,
    construction: ConstructionConfig,
) -> tuple[AttemptBindVerificationStage, TransmissionCapabilityStage]:
    """Steps 13 (Attempt Bind Verification) + 14 (Transmission Capability) —
    split out of :func:`_build_realized_stages` purely for the size budget."""
    step13_stage = AttemptBindVerificationStage(
        # ⚠ structural re-derivation, never a self-comparison (구조 파생 >
        # 자기신고): each reader reads the LIVE artifact these steps already
        # produced — never `attempt.<field>` itself, which is the very claim
        # `exact_binding_holds` exists to independently re-check.
        reservation_digest_reader=lambda _attempt: (
            None if proof_stage.proof is None else proof_stage.proof.canonical_digest
        ),
        # bound_chain["action_flow_permit"] is `attempt.action_flow_permit_
        # identity` (an IDENTITY, not a digest), so the live counterpart
        # compared against it must be the permit's own identity too.
        permit_digest_reader=lambda _attempt: (
            None
            if flow_governor.last_permit is None
            else flow_governor.last_permit.permit_id
        ),
        approval_digest_reader=lambda _attempt: (
            None
            if step4_recorder.last_verdict is None
            else step4_recorder.last_verdict.bound_digest
        ),
    )
    step14_stage = TransmissionCapabilityStage(
        rcl_log,
        writer_epoch=writer_epoch,
        context_reader=lambda request: TransmissionCapabilityContext(
            reservation_identity=(
                f"resv-{request.instrument_key.account}-"
                f"{request.instrument_key.instrument}"
            ),
            account_scope=request.instrument_key.account,
            instrument_scope=request.instrument_key.instrument,
            side_action_scope=construction.outbound_side,
        ),
    )
    return step13_stage, step14_stage


def _default_request_bytes_digest_source(
    construction: ConstructionConfig, egress_coordinates: EgressCoordinatesConfig
) -> CapsuleStandInDigest:
    """The unchanged capsule-terminus stand-in (T2 lane A —
    :mod:`tos_runtime.compose._request_digest` module docstring): the SAME boot-time constant
    ``_build_context_resolver`` computed before this lane, over
    ``egress_coordinates.capsule_terminus_fields``, now wrapped in the new digest-source seam.
    """
    return CapsuleStandInDigest(
        digest=_SCHEME.compute_digest(
            {
                name: getattr(construction, name)
                for name in egress_coordinates.capsule_terminus_fields
            }
        )
    )


def _build_context_resolver(
    *,
    construction_stages: _ConstructionStages,
    realized: _RealizedStages,
    flow_governor: RecordingActionFlowGovernor,
    currentness_assembler: CurrentnessAssembler,
    proof_issuer: EgressCurrentnessProofIssuer,
    pending_dimension_specs: tuple[PendingDimensionSpec, ...],
    egress_attestations: EgressAttestations,
    egress_coordinates: EgressCoordinatesConfig,
    broker_scopes: BrokerScopesConfig,
    instance_document: InstanceDocument | None,
    construction: ConstructionConfig,
    environment_label: str,
    continuity_id: str,
    request_bytes_digest_source: RequestBytesDigestSource | None = None,
) -> ComposeContextResolver:
    """The gateway's lazy ``SendBoundaryContext`` resolver (design #35 §3.1
    (3)), wired with this environment's transport nature / credential-route
    inventory / authorized coordinates.

    G-4 CLOSED (plan §2 decision 2): transport nature / credential-route
    inventory are STRUCTURALLY DERIVED from ``broker_scopes.active_scope``
    (:func:`~tos_runtime.brokercap.transport_nature` /
    :func:`~tos_runtime.brokercap.credential_route_inventory`), never the
    three old ``f"synthetic-paper-{environment_label}"`` literals; the old
    R2 literal-comparison boot refusal is likewise generalized to
    :func:`~tos_runtime.brokercap.refuse_principal_collision` over EVERY
    configured scope's principal.

    ``instance_document`` is loaded EXACTLY ONCE per boot, by
    :func:`_resolve_strategies_and_attested_inputs`, and threaded through
    :class:`_BootResult` (finding F9 — no second re-load here).

    Args:
        request_bytes_digest_source: T2 lane A's digest-source seam. ``None``
            (every caller today) builds :func:`_default_request_bytes_digest_source`.

    Raises:
        BrokerScopeConfigError: ``active_principal`` collides with a scope's
            own principal (generalized R2), or a config/kernel mismatch.
    """
    refuse_principal_collision(
        broker_scopes, active_principal=egress_coordinates.active_principal
    )
    return ComposeContextResolver(
        construction_stage=construction_stages.construction_stage,
        proof_stage=construction_stages.proof_stage,
        venue_stage=construction_stages.venue_stage,
        step4_recorder=realized.step4_recorder,
        step9_recorder=realized.step9_recorder,
        step14_stage=realized.step14_stage,
        flow_governor=flow_governor,
        currentness_assembler=currentness_assembler,
        proof_issuer=proof_issuer,
        pending_dimension_specs=pending_dimension_specs,
        egress_attestations=egress_attestations,
        broker_scopes=broker_scopes,
        instance_document=instance_document,
        # Transport's OWN identity (slice #3) — derived from the active scope, G-4 closed.
        transport_nature=transport_nature(broker_scopes.active_scope),
        environment_label=environment_label,
        # ONE source (finding #1): same value as authorized_coordinates below,
        # required by the kernel's claim-principal-matches-active-principal check.
        principal=egress_coordinates.active_principal,
        credential_route_inventory=credential_route_inventory(
            broker_scopes, active_principal=egress_coordinates.active_principal
        ),
        authorized_coordinates=EgressCoordinateSet(
            endpoint=egress_coordinates.endpoint,
            account=construction.account,
            environment=environment_label,
            action=egress_coordinates.action,
            method=egress_coordinates.method,
            route_identity=egress_coordinates.route_identity,
            credential_generation=egress_coordinates.credential_generation,
            broker_session_generation=egress_coordinates.broker_session_generation,
            egress_generation=egress_coordinates.egress_generation,
            active_principal=egress_coordinates.active_principal,
        ),
        # STAND-IN by default; T2 lane A: a caller may inject a real codec digest instead.
        request_bytes_digest_source=(
            request_bytes_digest_source
            if request_bytes_digest_source is not None
            else _default_request_bytes_digest_source(construction, egress_coordinates)
        ),
        outbound_side=construction.outbound_side,
        action_class=construction.action_class,
        observed_session_phase=construction.observed_session_phase,
        continuity_id=continuity_id,
        instrument_key=InstrumentKey(
            account=construction.account, instrument=construction.instrument
        ),
        venue_snapshot=construction.venue_snapshot,
        venue_policy=construction.venue_policy,
        venue_decision=construction.venue_decision,
    )


_ENGINE_CONFIG_NAME = "engine.yaml"


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
) -> ComposedRuntime:
    """The gateway + ``EngineCore`` + durable inbox/driver wiring (delegated to
    :func:`~tos_runtime.compose._engine_wiring.wire_engine_and_driver`) + the boot-time replay
    check + the final :class:`~tos_runtime.compose._types.ComposedRuntime` assembly — the tail of
    :func:`~tos_runtime.compose.root.compose_paper_runtime`, split out purely for the size
    budget."""
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
    )

    # Independent boot-time re-derivation over whatever this inbox has already durably admitted
    # (design plan §1.1 "부팅 시 verify_rcl_log_or_halt 뒤에 실행"). Reported deviation from the
    # plan's literal adjacency: verify_rcl_log_or_halt itself runs earlier, inside _boot_services,
    # before the engine core/gateway/inbox exist to replay at all — this is the earliest point in
    # compose an engine replay check is constructible, and it still runs strictly after the RCL
    # log's own integrity is re-verified (the substantive ordering requirement). See
    # tos_runtime.engine.replay's own module docstring for what "side-effect-free" does and does
    # not cover for a core that DID have a working transmit in its original run.
    engine_driver_config = load_engine_driver_config(
        config_dir / ENGINE_DRIVER_CONFIG_NAME
    )
    verify_replay_or_halt(
        inbox=wired.inbox,
        evidence_store=infra.evidence_store,
        emergency_log=infra.emergency_log,
        registry=wired.resolved_registry,
        stages=stages,
        configuration=engine_configuration,
        scheme=_SCHEME,
        window_events=engine_driver_config.replay_window_events,
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


def _resolve_strategies_and_attested_inputs(
    config_dir: Path,
    environment_label: str,
    identity: RuntimeIdentity,
    infra: _Infra,
    risk: _RiskAndCurrentness,
    registry: StrategyRegistry | None,
    allow_no_strategies: bool,
) -> tuple[
    EgressCoordinatesConfig,
    BrokerScopesConfig,
    ResolvedStrategyRegistry,
    InstanceDocument | None,
]:
    """Load ``egress_coordinates.yaml`` + ``broker_scopes.yaml`` (TOS Phase 4
    plan §2 decisions 1-2, G-4), resolve the ONE strategy source (TOS Phase
    3 슬라이스 D-R ``[D-R-2]``), load the active scope's INSTANCE document
    EXACTLY ONCE (finding F9 — threaded through :class:`_BootResult`, no
    second re-load), and records ``OPERATOR_ATTESTED_INPUTS`` — split out
    of :func:`_boot_services` for the size budget.

    ``allow_no_strategies`` (finding #8): ``False`` (the default) REFUSES
    when neither a strategies directory nor an injected registry is
    supplied — see :func:`~tos_runtime.strategy.resolve.
    resolve_strategy_registry`'s own docstring."""
    egress_coordinates = load_egress_coordinates(
        config_dir / _EGRESS_COORDINATES_CONFIG_NAME,
        environment_label=environment_label,
    )
    broker_scopes = load_broker_scopes(
        config_dir / _BROKER_SCOPES_CONFIG_NAME,
        environment_label=environment_label,
    )
    instance_document = load_active_instance_document(broker_scopes)
    resolved_strategies = resolve_strategy_registry(
        config_dir,
        injected_registry=registry,
        evidence_store=infra.evidence_store,
        emergency_log=infra.emergency_log,
        identity=identity,
        allow_no_strategies=allow_no_strategies,
    )
    record_operator_attested_inputs(
        config_dir,
        infra.evidence_store,
        identity,
        risk.egress_attestations,
        risk.risk_attestations,
        egress_coordinates,
        resolved_strategies.loaded,
        resolved_strategies.loaded_bindings,
        broker_scopes=broker_scopes,
        instance_document=instance_document,
    )
    return egress_coordinates, broker_scopes, resolved_strategies, instance_document


@dataclass
class _BootResult:
    """:func:`_boot_services`'s return value — named fields instead of a
    growing tuple purely so callers never destructure it (size-budget win: a
    named-attribute return avoids the multi-line unpacking assignment a
    growing tuple forces). ``registry`` is the RESOLVED
    :class:`~tos.engine.StrategyRegistry` (TOS Phase 3 슬라이스 D-R
    ``[D-R-2]``) — never the caller's raw injected one."""

    identity: RuntimeIdentity
    infra: _Infra
    rcl: _RclAndAuthority
    risk: _RiskAndCurrentness
    release_admitted: bool
    egress_coordinates: EgressCoordinatesConfig
    broker_scopes: BrokerScopesConfig
    #: Loaded EXACTLY ONCE (finding F9) — never re-loaded downstream.
    instance_document: InstanceDocument | None
    registry: StrategyRegistry


def _boot_services(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    environment_label: str,
    uid: int,
    authority_domain: str,
    monotonic_source: MonotonicSource | None,
    registry: StrategyRegistry | None,
    allow_no_strategies: bool,
) -> _BootResult:
    """Identity + STAGE A release probe + custody/evidence/time + RCL/
    authority + risk/currentness + strategy-source resolution
    (:func:`_resolve_strategies_and_attested_inputs` — TOS Phase 3 슬라이스
    D-R ``[D-R-2]``) + STAGE B release probe — split out of
    :func:`~tos_runtime.compose.root.compose_paper_runtime` purely for the
    size budget; the actual STAGE A/B split and its rationale live on
    :func:`_stage_a_release_probe`/:func:`_stage_b_release_probe`
    themselves."""
    identity = _build_identity(environment_label)
    release_config = load_release_config(config_dir / _RELEASE_CONFIG_NAME)
    release_service = ReleaseAdmissionService(release_config)
    _stage_a_release_probe(release_service, release_config, identity)

    infra = _build_custody_evidence_time(
        config_dir,
        data_dir,
        custody_root,
        environment_label,
        identity,
        uid,
        monotonic_source,
    )
    rcl = _build_rcl_and_authority(
        data_dir,
        config_dir,
        identity,
        infra.evidence_store,
        infra.time_service,
        infra.time_config,
        authority_domain,
    )
    verify_rcl_log_or_halt(
        rcl.rcl_log, infra.evidence_store, infra.emergency_log, identity
    )
    risk = _build_risk_and_currentness(
        config_dir,
        rcl.rcl_log,
        rcl.writer_epoch,
        infra.evidence_store,
        infra.time_service,
        rcl.authority_epoch_service,
    )
    egress_coordinates, broker_scopes, resolved_strategies, instance_document = (
        _resolve_strategies_and_attested_inputs(
            config_dir,
            environment_label,
            identity,
            infra,
            risk,
            registry,
            allow_no_strategies,
        )
    )
    release_admitted = _stage_b_release_probe(
        release_service, identity, infra.time_service, rcl.rcl_log
    )
    return _BootResult(
        identity=identity,
        infra=infra,
        rcl=rcl,
        risk=risk,
        release_admitted=release_admitted,
        egress_coordinates=egress_coordinates,
        broker_scopes=broker_scopes,
        instance_document=instance_document,
        registry=resolved_strategies.registry,
    )


def _build_stage_map(
    construction_stages: _ConstructionStages, realized: _RealizedStages
) -> dict:
    """The ``CommitmentStep`` -> ``Stage`` map ``EngineCore`` is wired with —
    split out purely for the size budget."""
    return {
        CommitmentStep.CANDIDATE_COMMAND_CONSTRUCTION: construction_stages.construction_stage,
        CommitmentStep.VENUE_ADMISSIBILITY_DECISION: construction_stages.venue_stage,
        CommitmentStep.INDEPENDENT_APPROVAL: realized.step4_recorder,
        CommitmentStep.ECONOMIC_EFFECT_ENVELOPE: construction_stages.economic_stage,
        CommitmentStep.AGGREGATE_RISK_DECISION: realized.step6_stage,
        CommitmentStep.ACTION_FLOW_DECISION: realized.step7_stage,
        CommitmentStep.LEDGER_VERIFICATION: realized.step8_stage,
        CommitmentStep.ATOMIC_COMMIT: realized.step9_recorder,
        CommitmentStep.COMMITMENT_UNAVAILABILITY: realized.step10_stage,
        CommitmentStep.ORDER_CONFORMANCE_PROOF: construction_stages.proof_stage,
        CommitmentStep.ATTEMPT_BIND_VERIFICATION: realized.step13_stage,
        CommitmentStep.TRANSMISSION_CAPABILITY: realized.step14_stage,
    }
