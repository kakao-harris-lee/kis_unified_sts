"""``tos_runtime.compose`` currentness/risk phase-wiring helpers — split out
of ``_wiring.py`` purely for the size budget (tools/tos_size_budget.py file-
level limit); no behavioural difference from having them inline there.
:func:`~tos_runtime.compose._wiring._boot_services` calls
:func:`_build_risk_and_currentness`, in the design #40 §5 order 5-6.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tos.afg import ActionAmplificationEnvelope
from tos.authority import currentness_admissible
from tos.brokercap import environment_binding_ok
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.cur import (
    MANDATED_DIMENSION_FLOOR,
    CurrentnessPolicy,
    DimensionKey,
    policy_covers_mandated_dimensions,
)
from tos.egress import (
    CredentialRouteInventoryEntry,
    credential_route_authority_disjoint,
)
from tos.engine.vocabulary import StageOutcome
from tos.sbr import ReadinessVerdict

from tos_runtime.authority.epoch import SafetyAuthorityEpochService
from tos_runtime.compose._egress_attestations import (
    EgressAttestations,
    load_egress_attestations,
)
from tos_runtime.compose._pending_dimensions import (
    PendingDimensionSpec,
    load_pending_currentness_dimensions,
)
from tos_runtime.compose._risk_attestations import (
    RiskAttestations,
    load_risk_attestations,
)
from tos_runtime.compose._safety_wiring import _SafetyMesh
from tos_runtime.compose.context import (
    RecordingActionFlowGovernor,
    RecordingAggregateRiskService,
    VerdictRecorder,
)
from tos_runtime.currentness.config import load_currentness_config
from tos_runtime.currentness.proof import EgressCurrentnessProofIssuer
from tos_runtime.currentness.vector import CurrentnessAssembler, DimensionReport
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.projection import SqliteReservationProjectionReader
from tos_runtime.recovery.barrier import RecoveryVerdict
from tos_runtime.risk.aggregate import (
    load_adverse_scenario_set,
    load_required_scenario_kinds,
)
from tos_runtime.time.service import TrustworthyTimeService

__all__ = [
    "_ActionFlowDimensionState",
    "_RiskAndCurrentness",
    "_action_flow_dimension_reader_for",
    "_authority_dimension_reader_for",
    "_build_risk_and_currentness",
]

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Same config file name ``_wiring.py`` uses for the risk/currentness configs
#: (``tos/runtime/config/risk.example.yaml`` / ``currentness.example.yaml``
#: / ``currentness_dimensions.example.yaml``).
_RISK_CONFIG_NAME = "risk.yaml"
_CURRENTNESS_CONFIG_NAME = "currentness.yaml"
_CURRENTNESS_DIMENSIONS_CONFIG_NAME = "currentness_dimensions.yaml"
_EGRESS_ATTESTATIONS_CONFIG_NAME = "egress_attestations.yaml"
_RISK_ATTESTATIONS_CONFIG_NAME = "risk_attestations.yaml"


@dataclass
class _RiskAndCurrentness:
    projection: SqliteReservationProjectionReader
    risk_service: RecordingAggregateRiskService
    flow_governor: RecordingActionFlowGovernor
    required_scenario_kinds: frozenset
    currentness_assembler: CurrentnessAssembler
    proof_issuer: EgressCurrentnessProofIssuer
    #: The 17 operator-attested pending currentness dimensions (team-lead
    #: follow-up guidance) — see
    #: :mod:`tos_runtime.compose._pending_dimensions`'s own module docstring.
    pending_dimension_specs: tuple[PendingDimensionSpec, ...]
    #: The 5 operator-attested egress-gate stand-ins (items 6/12/16 — team-lead
    #: follow-up guidance) — see
    #: :mod:`tos_runtime.compose._egress_attestations`'s own module docstring.
    egress_attestations: EgressAttestations
    #: The 6 operator-attested step 6/7 admission witnesses (re-review
    #: finding F4) — see
    #: :mod:`tos_runtime.compose._risk_attestations`'s own module docstring.
    risk_attestations: RiskAttestations
    #: The late-bound cell the ACTION_FLOW dimension reader closes over —
    #: filled in with step 9's ``VerdictRecorder`` once
    #: ``_build_realized_stages`` creates it (see
    #: ``_ActionFlowDimensionState``'s own docstring for why).
    action_flow_dimension_state: _ActionFlowDimensionState
    #: Late-bound cell the RECOVERY dimension reader closes over — filled in with the
    #: W1 recovery barrier's own verdict once ``apply_recovery_barrier`` runs (see
    #: ``_RecoveryDimensionState``'s own docstring for why).
    recovery_dimension_state: _RecoveryDimensionState
    #: Late-bound cell the TRADING_APPROVAL dimension reader closes over — filled in
    #: with step 4's own ``VerdictRecorder`` once ``_build_realized_stages`` creates it
    #: (see ``_TradingApprovalDimensionState``'s own docstring for why).
    trading_approval_dimension_state: _TradingApprovalDimensionState
    #: Late-bound cell the EGRESS_IDENTITY dimension reader closes over — filled in
    #: with the composed credential-route inventory once ``_build_context_resolver``
    #: returns (see ``_EgressIdentityDimensionState``'s own docstring for why).
    egress_identity_dimension_state: _EgressIdentityDimensionState
    #: The four W3-a1/a2 safety-mesh services + item-16 latch owner (Phase 5 W3-b, plan §2
    #: decision 8) — see :mod:`tos_runtime.compose._safety_wiring`'s own module docstring.
    safety_mesh: _SafetyMesh


def _authority_dimension_reader_for(
    authority_epoch_service: SafetyAuthorityEpochService,
) -> Callable[[], DimensionReport | None]:
    def _reader() -> DimensionReport | None:
        state = authority_epoch_service.current_state()
        if state.current_epoch_floor is None:
            return None
        witness = authority_epoch_service.witness()
        return DimensionReport(
            bound_generation=state.current_epoch_floor,
            positively_established=currentness_admissible(witness),
            restrictive_floor=0,
        )

    return _reader


@dataclass
class _ActionFlowDimensionState:
    """A late-bound cell for the ACTION_FLOW dimension reader (below).

    ``CurrentnessAssembler`` is constructed before ``_build_realized_stages``
    creates step 9's ``VerdictRecorder`` (the currentness/risk wiring order,
    design #40 §5, runs before the engine Stage wiring) — so the reader
    closes over this mutable cell, and :func:`compose_paper_runtime` fills
    in ``step9_recorder`` right after ``_build_realized_stages`` returns.
    """

    step9_recorder: VerdictRecorder | None = None


def _action_flow_dimension_reader_for(
    rcl_log: SqliteCommitLog,
    writer_epoch: int,
    state: _ActionFlowDimensionState,
) -> Callable[[], DimensionReport | None]:
    """The ACTION_FLOW currentness dimension, derived from step 9's own
    ``AtomicCommitStage`` outcome (team-lead follow-up guidance, 2026-09-08:
    "derive it from AtomicCommitStage's own AppendReceipt seq, not from Q's
    standalone issue_permit").

    ``ActionFlowPermit.rcl_commitment_ref`` itself stays ``None``
    (``tos_runtime.risk.flow.ActionFlowGovernor.build_permit``'s own
    docstring — the durable commit lives in step 9's single
    ``apply_reservation_transition`` entry instead), so this reader does
    NOT read that field; it independently re-reads the RCL log's own
    CURRENT tip (never step 9's self-reported claim) and reports
    ``positively_established`` only when step 9 itself last recorded
    ``ADMIT`` — the same "구조 파생, never a caller-supplied claim"
    discipline every other reader in this module already follows.
    """

    def _reader() -> DimensionReport | None:
        verdict = state.step9_recorder.last_verdict if state.step9_recorder else None
        if verdict is None or verdict.outcome is not StageOutcome.ADMIT:
            return None
        view = rcl_log.read_linearizable(writer_epoch=writer_epoch)
        if view.last_seq is None:
            return None
        return DimensionReport(
            bound_generation=view.last_seq,
            positively_established=True,
            restrictive_floor=0,
        )

    return _reader


def _currentness_policy_dimension_reader_for(
    policy: CurrentnessPolicy,
) -> Callable[[], DimensionReport | None]:
    """The CURRENTNESS_POLICY currentness dimension (Phase 5 W3-b, plan §2
    decision 3 — the first of the 9 dimension-owner replacements).

    No new runtime state is needed: this composition already builds its own
    governing ``policy`` (below, ``required_dimensions=MANDATED_DIMENSION_FLOOR``)
    — the reader only asks the kernel's own
    :func:`~tos.cur.predicates.policy_covers_mandated_dimensions` whether
    THIS policy declares at least the FULL mandated floor (never
    ``CurrentnessAssembler``'s own narrower ``self._mandated`` — a SEPARATE,
    deliberately smaller floor this class itself is constructed with; see
    its own docstring), never a comparison this module authors itself
    (MEDIUM-A discipline, module docstring).

    Always returns a report (never ``None``): ``policy`` is always present
    at composition time, so there is no "cannot observe yet" case here,
    unlike the RCL-backed readers above.
    """

    def _reader() -> DimensionReport | None:
        return DimensionReport(
            bound_generation=policy.policy_generation,
            positively_established=policy_covers_mandated_dimensions(
                policy, MANDATED_DIMENSION_FLOOR
            ),
            restrictive_floor=0,
        )

    return _reader


@dataclass
class _RecoveryDimensionState:
    """A late-bound cell for the RECOVERY dimension reader (below).

    ``CurrentnessAssembler`` is constructed (in :func:`_build_risk_and_currentness`,
    design #40 §5 order 6) strictly BEFORE the TOS Phase 5 W1 recovery barrier ever
    runs (:func:`~tos_runtime.compose._recovery_wiring.apply_recovery_barrier` is the
    LAST call in :func:`~tos_runtime.compose.root.compose_paper_runtime`, after
    ``_finalize``) — so this reader closes over this mutable cell, and
    ``compose_paper_runtime`` fills in :attr:`verdict` right after
    ``apply_recovery_barrier`` returns, before it ever hands the composed runtime to a
    caller that could drive an attempt (the exact same ordering discipline
    :class:`_ActionFlowDimensionState` already relies on for step 9's recorder).
    """

    verdict: RecoveryVerdict | None = None


def _recovery_dimension_reader_for(
    state: _RecoveryDimensionState,
) -> Callable[[], DimensionReport | None]:
    """The RECOVERY currentness dimension (Phase 5 W3-b, plan §2 decision 3 —
    dimension-owner replacement 2/9).

    The owner is W1's own :class:`~tos_runtime.recovery.barrier.RecoveryBarrier` —
    this reader copies its already-decided :attr:`~tos_runtime.recovery.barrier
    .RecoveryVerdict.readiness_verdict` verbatim (the SAME
    ``is ReadinessVerdict.READY`` identity check
    :meth:`~tos_runtime.recovery.barrier.RecoveryVerdict.ready` itself is —
    ``tos.sbr``'s own non-truthy discipline forbids ``if verdict:``), never a second
    judgement of its own (MEDIUM-A discipline, module docstring).

    ``bound_generation=0`` is this reader's own deliberate, explicit statement, not an
    invented placeholder: the recovery barrier is a single boot-time judgement (design
    #17 §3.5), not a versioned/generational artifact, so there is no real generation
    counter to report (the same "an owner reporting 0 is that owner's own choice"
    discipline :class:`~tos_runtime.currentness.vector.DimensionReport`'s own docstring
    states).

    Returns ``None`` (dimension absent, never a fabricated verdict) until
    :attr:`_RecoveryDimensionState.verdict` is filled in — i.e. for the entire
    composition-time window before ``compose_paper_runtime`` has actually run the
    barrier.
    """

    def _reader() -> DimensionReport | None:
        verdict = state.verdict
        if verdict is None:
            return None
        return DimensionReport(
            bound_generation=0,
            positively_established=verdict.readiness_verdict is ReadinessVerdict.READY,
            restrictive_floor=0,
        )

    return _reader


@dataclass
class _TradingApprovalDimensionState:
    """A late-bound cell for the TRADING_APPROVAL dimension reader (below) — the SAME
    "constructed before the recorder exists" ordering :class:`_ActionFlowDimensionState`
    already documents, for step 4's own :class:`~tos_runtime.compose.context
    .VerdictRecorder` instead of step 9's."""

    step4_recorder: VerdictRecorder | None = None


def _trading_approval_dimension_reader_for(
    state: _TradingApprovalDimensionState,
) -> Callable[[], DimensionReport | None]:
    """The TRADING_APPROVAL currentness dimension (Phase 5 W3-b, plan §2 decision 3 —
    dimension-owner replacement 3/9).

    Derived from step 4's own ``IndependentApprovalStage`` outcome — the SAME
    structural-derivation discipline :func:`_action_flow_dimension_reader_for` already
    applies to step 9 (``positively_established`` only when step 4 itself last recorded
    ``ADMIT``, never a second comparison against the decision this reader would have to
    re-fetch via :meth:`~tos_runtime.authority.iap.IntentRegistry.decision_current`
    itself — that call needs a SPECIFIC per-attempt
    ``IndependentApprovalDecision``/``LoadedApproval`` this parameterless reader has no
    way to obtain; step 4's own recorded verdict is this attempt's actual, already-
    decided answer to exactly that question).

    ``bound_generation=0``: step 4's :class:`~tos.engine.records.StageVerdict` carries
    no generation counter of its own to report (an explicit, deliberate 0, not an
    invented default — same discipline as :func:`_recovery_dimension_reader_for`).

    Returns ``None`` (dimension absent) whenever step 4 has not yet recorded ANY verdict
    for this attempt, or its own recorder has not yet been late-bound into ``state``
    (composition-time window, mirrors :func:`_action_flow_dimension_reader_for`).
    """

    def _reader() -> DimensionReport | None:
        recorder = state.step4_recorder
        verdict = recorder.last_verdict if recorder is not None else None
        if verdict is None:
            return None
        return DimensionReport(
            bound_generation=0,
            positively_established=verdict.outcome is StageOutcome.ADMIT,
            restrictive_floor=0,
        )

    return _reader


def _environment_scope_dimension_reader_for(
    environment_label: str,
) -> Callable[[], DimensionReport | None]:
    """The ENVIRONMENT_SCOPE currentness dimension (Phase 5 W3-b, plan §2 decision 3 —
    dimension-owner replacement 4/9).

    No new runtime state is needed: this composition already computes the SAME three
    facts :mod:`tos_runtime.compose.context` passes as
    ``scope_environment``/``evidence_environment``/``environment_inherited`` on every
    ``send_boundary_context`` call (``environment_label`` for both environment tokens,
    ``environment_inherited=False`` — this composition wires exactly one environment for
    its whole process lifetime, never a cross-environment inheritance path) — the reader
    only asks the kernel's own :func:`~tos.brokercap.predicates.environment_binding_ok`
    over those SAME values, never re-deriving or comparing them itself (MEDIUM-A
    discipline, module docstring).

    Always returns a report (never ``None``): ``environment_label`` is a boot argument,
    always present at composition time.
    """

    def _reader() -> DimensionReport | None:
        return DimensionReport(
            bound_generation=0,
            positively_established=environment_binding_ok(
                evidence_environment=environment_label,
                scope_environment=environment_label,
                inherited=False,
            ),
            restrictive_floor=0,
        )

    return _reader


@dataclass
class _EgressIdentityDimensionState:
    """A late-bound cell for the EGRESS_IDENTITY dimension reader (below).

    ``CurrentnessAssembler`` is constructed inside :func:`_build_risk_and_currentness`
    (design #40 §5 order 6) strictly BEFORE this composition's credential-route
    inventory is resolved (:func:`~tos_runtime.brokercap.credential_route_inventory` is
    called by ``_wiring.py``'s ``_build_context_resolver``, part of order 7+) — so this
    reader closes over this mutable cell, and
    :func:`~tos_runtime.compose.root.compose_paper_runtime` fills in
    :attr:`credential_route_inventory` right after ``_build_context_resolver`` returns,
    strictly before it ever hands the composed runtime to a caller that could drive an
    attempt (the same ordering discipline :class:`_ActionFlowDimensionState` already
    documents).
    """

    credential_route_inventory: tuple[CredentialRouteInventoryEntry, ...] | None = None


def _egress_identity_dimension_reader_for(
    state: _EgressIdentityDimensionState,
) -> Callable[[], DimensionReport | None]:
    """The EGRESS_IDENTITY currentness dimension (Phase 5 W3-b, plan §2 decision 3 —
    dimension-owner replacement 5/9).

    **Partial coverage, honestly disclosed.** ``tos.egress``'s own EGRESS_IDENTITY-
    shaped predicates are :func:`~tos.egress.predicates.credential_route_authority_disjoint`
    (used here — over the SAME ``credential_route_inventory`` tuple
    :mod:`tos_runtime.compose.context` already threads into every
    ``send_boundary_context`` call, never re-derived),
    :func:`~tos.egress.predicates.stale_principal_structurally_rejected` (needs a
    committed :class:`~tos.egress.ActiveEgressPrincipalSet` this composition tracks
    NOWHERE — no runtime owner exists yet for that structure), and
    :func:`~tos.egress.predicates.egress_generation_monotonic` (needs a PRIOR/new
    :class:`~tos.ordering.OrderingEvent` pair; a currentness dimension reader is a
    parameterless, per-boot fact, not a per-attempt comparison, so there is no honest
    "prior" this reader could hold without inventing one). Per the plan's own "if no
    honest source exists for a dimension, STOP that dimension" instruction (applied here
    at the sub-predicate level): this reader uses ONLY the one predicate it can
    honestly evaluate, and omits the other two rather than fabricating their inputs —
    a real gap, not silently smoothed over (W3.2 follow-up: a runtime owner for the
    active-principal-set / prior-event history would complete this dimension).

    ``bound_generation=0``: the credential-route inventory is a static,
    boot-time-resolved configuration table (``tos_runtime.brokercap.credential_route_inventory``),
    not a generational artifact — an explicit, deliberate 0 (same discipline as the
    other new readers above).

    Returns ``None`` (dimension absent) until :attr:`_EgressIdentityDimensionState
    .credential_route_inventory` is late-bound (composition-time window).
    """

    def _reader() -> DimensionReport | None:
        inventory = state.credential_route_inventory
        if inventory is None:
            return None
        return DimensionReport(
            bound_generation=0,
            positively_established=credential_route_authority_disjoint(inventory),
            restrictive_floor=0,
        )

    return _reader


def _load_action_flow_envelope(path: Path) -> ActionAmplificationEnvelope:
    """Build the Action Flow Governor's ``ActionAmplificationEnvelope`` from
    the ``risk.yaml`` block (``tos_runtime.risk`` has no dedicated loader for
    this — see ``tos/runtime/config/risk.example.yaml``'s own comment: "is
    constructed directly by the composition root")."""
    import yaml

    from tos_runtime.risk.aggregate import AggregateRiskConfigError

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise AggregateRiskConfigError(f"cannot read {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise AggregateRiskConfigError(f"{path} must be a top-level mapping")
    fields = (
        "max_fan_out",
        "max_depth",
        "max_attempts",
        "max_mutations",
        "max_queries",
        "max_queue_depth",
        "max_in_flight",
        "max_elapsed_monotonic",
        "max_duplicate_redelivery_expansion",
        "max_failover_reconnect_replay_expansion",
        "max_amplification_per_cause",
    )
    missing = [name for name in fields if raw.get(name) is None]
    if missing:
        raise AggregateRiskConfigError(
            f"{path}: ActionAmplificationEnvelope axes still null (named-TBD): "
            f"{missing} — refusing to start"
        )
    return ActionAmplificationEnvelope(**{name: raw[name] for name in fields})


@dataclass
class _DimensionStates:
    """Every late-bound dimension-reader cell :func:`_build_dimension_readers` creates —
    bundled so :func:`_build_risk_and_currentness` can hand all three to
    :class:`_RiskAndCurrentness` in one field, and :func:`~tos_runtime.compose.root
    .compose_paper_runtime` can late-bind each once its own recorder/verdict exists."""

    action_flow: _ActionFlowDimensionState
    recovery: _RecoveryDimensionState
    trading_approval: _TradingApprovalDimensionState
    egress_identity: _EgressIdentityDimensionState


def _build_dimension_readers(
    *,
    rcl_log: SqliteCommitLog,
    writer_epoch: int,
    authority_epoch_service: SafetyAuthorityEpochService,
    currentness_policy: CurrentnessPolicy,
    environment_label: str,
    safety_mesh: _SafetyMesh,
) -> tuple[
    dict[DimensionKey, tuple[str, Callable[[], DimensionReport | None]]],
    _DimensionStates,
]:
    """The full ``dimension_readers`` map (module docstring, "Reader map") — split out
    of :func:`_build_risk_and_currentness` purely for the size budget; no behavioural
    difference from having this inline there."""
    dimension_states = _DimensionStates(
        action_flow=_ActionFlowDimensionState(),
        recovery=_RecoveryDimensionState(),
        trading_approval=_TradingApprovalDimensionState(),
        egress_identity=_EgressIdentityDimensionState(),
    )
    dimension_readers: dict[
        DimensionKey, tuple[str, Callable[[], DimensionReport | None]]
    ] = {
        DimensionKey.SAFETY_AUTHORITY: (
            "tos_runtime.authority",
            _authority_dimension_reader_for(authority_epoch_service),
        ),
        DimensionKey.ACTION_FLOW: (
            "tos_runtime.risk",
            _action_flow_dimension_reader_for(
                rcl_log, writer_epoch, dimension_states.action_flow
            ),
        ),
        DimensionKey.CURRENTNESS_POLICY: (
            "tos_runtime.currentness",
            _currentness_policy_dimension_reader_for(currentness_policy),
        ),
        DimensionKey.RECOVERY: (
            "tos_runtime.recovery",
            _recovery_dimension_reader_for(dimension_states.recovery),
        ),
        DimensionKey.TRADING_APPROVAL: (
            "tos_runtime.authority.iap",
            _trading_approval_dimension_reader_for(dimension_states.trading_approval),
        ),
        DimensionKey.ENVIRONMENT_SCOPE: (
            "tos_runtime.brokercap",
            _environment_scope_dimension_reader_for(environment_label),
        ),
        DimensionKey.EGRESS_IDENTITY: (
            "tos_runtime.egress",
            _egress_identity_dimension_reader_for(dimension_states.egress_identity),
        ),
        **safety_mesh.dimension_readers,
    }
    return dimension_readers, dimension_states


def _build_risk_and_currentness(
    config_dir: Path,
    rcl_log: SqliteCommitLog,
    writer_epoch: int,
    evidence_store: SqliteEvidenceStore,
    time_service: TrustworthyTimeService,
    authority_epoch_service: SafetyAuthorityEpochService,
    environment_label: str,
    safety_mesh: _SafetyMesh,
) -> _RiskAndCurrentness:
    """Aggregate Risk Authority + Action Flow Governor (order 5), currentness
    assembler + Egress Currentness Proof issuer (order 6). ``environment_label`` /
    ``safety_mesh`` are forwarded to :func:`_build_dimension_readers` (Phase 5 W3-b)."""
    projection = SqliteReservationProjectionReader(rcl_log)
    scenario_set = load_adverse_scenario_set(config_dir / _RISK_CONFIG_NAME)
    required_scenario_kinds = load_required_scenario_kinds(
        config_dir / _RISK_CONFIG_NAME
    )
    risk_service = RecordingAggregateRiskService(
        projection, scenario_set, evidence_store
    )
    envelope = _load_action_flow_envelope(config_dir / _RISK_CONFIG_NAME)
    flow_governor = RecordingActionFlowGovernor(
        rcl_log, evidence_store, envelope, writer_epoch=writer_epoch
    )

    # Loaded (and thereby fail-closed validated at startup) even though this
    # slice's proof issuance path does not yet consume
    # `max_claim_to_send_bound_ms` directly.
    load_currentness_config(config_dir / _CURRENTNESS_CONFIG_NAME)
    # Narrowed to exactly MANDATED_DIMENSION_FLOOR (the 21 non-conditional
    # DimensionKey members) — never the full 22-member enum, which would
    # also require the conditional RESTRICTED_LIVE_TRIAL dimension this
    # composition has no basis to attest at all (§9:258, RLP-deferred,
    # out of Phase 2 scope). "A policy may require more, never fewer"
    # (tos.cur.predicates.vector_complete's own §5.1 rule) — this IS the
    # floor, not a narrowing below it.
    currentness_policy = CurrentnessPolicy.issue(
        scheme=_SCHEME,
        policy_id="compose-currentness-policy",
        policy_generation=1,
        required_dimensions=tuple(
            sorted(MANDATED_DIMENSION_FLOOR, key=lambda k: k.value)
        ),
    )
    assert isinstance(currentness_policy, CurrentnessPolicy)

    dimension_readers, dimension_states = _build_dimension_readers(
        rcl_log=rcl_log,
        writer_epoch=writer_epoch,
        authority_epoch_service=authority_epoch_service,
        currentness_policy=currentness_policy,
        environment_label=environment_label,
        safety_mesh=safety_mesh,
    )
    currentness_assembler = CurrentnessAssembler(
        rcl_log,
        time_service,
        writer_epoch=writer_epoch,
        policy=currentness_policy,
        mandated=frozenset({DimensionKey.COMMIT_LOG, DimensionKey.TRUSTWORTHY_TIME}),
        dimension_readers=dimension_readers,
    )
    # `is_complete` is the SAME currentness_assembler.is_complete callable
    # every other consumer uses (== tos.cur.predicates.vector_complete,
    # never re-derived) — the issuer derives `result` from it per issuance,
    # never from a caller-supplied claim.
    proof_issuer = EgressCurrentnessProofIssuer(
        rcl_log,
        writer_epoch=writer_epoch,
        is_complete=currentness_assembler.is_complete,
    )
    pending_dimension_specs = load_pending_currentness_dimensions(
        config_dir / _CURRENTNESS_DIMENSIONS_CONFIG_NAME
    )
    egress_attestations = load_egress_attestations(
        config_dir / _EGRESS_ATTESTATIONS_CONFIG_NAME
    )
    risk_attestations = load_risk_attestations(
        config_dir / _RISK_ATTESTATIONS_CONFIG_NAME
    )

    return _RiskAndCurrentness(
        projection=projection,
        risk_service=risk_service,
        flow_governor=flow_governor,
        required_scenario_kinds=required_scenario_kinds,
        currentness_assembler=currentness_assembler,
        pending_dimension_specs=pending_dimension_specs,
        egress_attestations=egress_attestations,
        risk_attestations=risk_attestations,
        action_flow_dimension_state=dimension_states.action_flow,
        recovery_dimension_state=dimension_states.recovery,
        trading_approval_dimension_state=dimension_states.trading_approval,
        egress_identity_dimension_state=dimension_states.egress_identity,
        safety_mesh=safety_mesh,
        proof_issuer=proof_issuer,
    )
