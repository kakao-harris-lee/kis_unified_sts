"""``tos_runtime.compose`` currentness dimension-reader factories + their late-bound
state cells — split out of ``_currentness_wiring.py`` purely for the size budget
(tools/tos_size_budget.py file-level limit); no behavioural difference from having
them inline there. :func:`_build_dimension_readers` is the ONE assembly point that
builds the full ``dimension_readers`` map
:class:`~tos_runtime.currentness.vector.CurrentnessAssembler` is constructed with —
called from :func:`~tos_runtime.compose._currentness_wiring._build_risk_and_currentness`.

Every reader here is a ``Callable[[], DimensionReport | None]`` closure factory:
``None`` in from the underlying stage/service/verdict means "cannot observe yet",
never a fabricated positive (the "구조 파생 > 자기신고" discipline every reader below
follows) — see :class:`~tos_runtime.currentness.vector.DimensionReport`'s own
docstring for the shared field contract (``bound_generation``/``positively_established``/
``restrictive_floor``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from tos.are import RiskDecisionResult
from tos.authority import currentness_admissible
from tos.brokercap import environment_binding_ok
from tos.cur import (
    MANDATED_DIMENSION_FLOOR,
    CurrentnessPolicy,
    DimensionKey,
    policy_covers_mandated_dimensions,
)
from tos.egressgw import OrderConstructionStage
from tos.engine.vocabulary import StageOutcome
from tos.ioc import ConformanceResult
from tos.sbr import ReadinessVerdict

from tos_runtime.authority.epoch import SafetyAuthorityEpochService
from tos_runtime.brokercap.scopes import BrokerScope, transport_nature
from tos_runtime.compose._safety_wiring import _SafetyMesh
from tos_runtime.compose.context import RecordingAggregateRiskService, VerdictRecorder
from tos_runtime.currentness.vector import DimensionReport
from tos_runtime.posttrade.release_consumer import FinalityReleaseConsumer
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.recovery.barrier import RecoveryVerdict

__all__ = [
    "_ActionFlowDimensionState",
    "_ConstraintDimensionState",
    "_ConstructionDimensionState",
    "_DecisionProofIntentDimensionState",
    "_DimensionStates",
    "_EnvironmentScopeDimensionState",
    "_PostTradeDimensionState",
    "_RecoveryDimensionState",
    "_ReleaseDimensionState",
    "_TradingApprovalDimensionState",
    "_action_flow_dimension_reader_for",
    "_aggregate_risk_dimension_reader_for",
    "_authority_dimension_reader_for",
    "_build_dimension_readers",
    "_constraint_dimension_reader_for",
    "_construction_dimension_reader_for",
    "_currentness_policy_dimension_reader_for",
    "_decision_proof_intent_dimension_reader_for",
    "_environment_scope_dimension_reader_for",
    "_post_trade_dimension_reader_for",
    "_recovery_dimension_reader_for",
    "_release_dimension_reader_for",
    "_trading_approval_dimension_reader_for",
]


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

    W3.1 independent review MEDIUM-3: this reader used to ask whether ``policy``
    covers the mandated floor right after ``policy`` had been BUILT from that same
    floor (below, ``required_dimensions=tuple(sorted(MANDATED_DIMENSION_FLOOR, ...))``)
    — a tautology no operator config value could ever change. Fixed: ``policy`` is now
    built from the operator-declared ``required_dimensions`` key
    (:mod:`tos_runtime.currentness.config`'s own module docstring) — a genuinely
    separate, independently-editable source — so the reader's
    :func:`~tos.cur.predicates.policy_covers_mandated_dimensions` call against the
    kernel's own :data:`~tos.cur.MANDATED_DIMENSION_FLOOR` (never
    ``CurrentnessAssembler``'s own narrower ``self._mandated`` — a SEPARATE,
    deliberately smaller floor this class itself is constructed with; see its own
    docstring) now genuinely checks the operator's declared config against the kernel's
    mandated floor, never a comparison this module authors itself (MEDIUM-A
    discipline, module docstring).

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

    ``CurrentnessAssembler`` is constructed (in
    :func:`~tos_runtime.compose._currentness_wiring._build_risk_and_currentness`,
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


@dataclass
class _EnvironmentScopeDimensionState:
    """A late-bound cell for the ENVIRONMENT_SCOPE dimension reader (below).

    ``CurrentnessAssembler`` is constructed in
    :func:`~tos_runtime.compose._currentness_wiring._build_risk_and_currentness`
    (design #40 §5 order 6) strictly BEFORE
    :func:`~tos_runtime.compose._wiring._resolve_strategies_and_attested_inputs` loads
    the broker-scopes config and resolves ``active_scope`` — so this reader closes over
    this mutable cell, and ``_wiring.py``'s ``_boot_services`` fills in
    :attr:`active_scope` right after that resolution returns (the same "constructed
    before its dependency exists" ordering :class:`_RecoveryDimensionState` already
    documents).
    """

    active_scope: BrokerScope | None = None


def _environment_scope_dimension_reader_for(
    environment_label: str,
    state: _EnvironmentScopeDimensionState,
) -> Callable[[], DimensionReport | None]:
    """The ENVIRONMENT_SCOPE currentness dimension (Phase 5 W3-b, plan §2 decision 3 —
    dimension-owner replacement 4/9).

    W3.1 independent review MEDIUM-2: the original reader asked
    :func:`~tos.brokercap.predicates.environment_binding_ok` whether ``environment_label``
    equals ``environment_label`` — a tautology (module docstring, MEDIUM-A discipline
    forbids exactly this). Fixed with three genuinely distinct sources instead of one
    variable read three times, mirroring the SAME broker-reaching / non-broker-reaching
    split :func:`~tos_runtime.brokercap.derive.derive_item6_item12`'s own item 12 already
    applies (never re-derived here — this reader reuses the public
    :func:`~tos_runtime.brokercap.scopes.transport_nature` helper, the SAME structural
    fact that split keys off):

    - A scope whose :func:`~tos_runtime.brokercap.scopes.transport_nature`
      ``reaches_broker`` ``is False`` (``SYNTHETIC``/``NONE`` endpoint classes — an
      explicit identity check, W3.1 independent review LOW-8, never truthiness: the
      field's own type is ``bool | None``, and ``None`` must never silently take this
      vacuous-True branch) has no environment binding evidence to check at all —
      ``positively_established=True`` vacuously, the same "no constraint generation
      exists to be stale" discipline :func:`derive_item6_item12` already documents for
      its own item 12, never a fabricated pass invented for this reader alone.
    - For every other case (``reaches_broker`` is ``True`` OR ``None`` — unknown
      reachability never gets the vacuous pass either), the real three-source check,
      both sides in the SAME
      broker-environment-axis string space (never ``environment_label``, the operator's
      OWN, differently-typed deployment label — D1.1 — which is not what this predicate
      compares at all): ``scope_environment`` is
      ``active_scope.environment_binding[capability_tuples[0].environment]`` — this
      scope's own config-declared axis binding table (independent-review finding F4);
      ``evidence_environment`` is ``active_scope.instance.environment`` — the Broker
      Capability Profile INSTANCE document's OWN declared environment, a file-loaded
      fact from a COMPLETELY SEPARATE source (the loader itself already "refuses when it
      disagrees with ``environment_binding[tuple.environment]``" — :class:`~tos_runtime
      .brokercap.scopes.ScopeInstanceBinding`'s own docstring, so this reader re-confirms
      at read-time what the loader only checked once at boot, exactly the "trust but
      verify" discipline two independently-sourced fields earn), or ``None`` when no
      instance is bound (a broker-reaching scope with no instance is a genuine gap,
      never papered over); ``inherited`` is ``False`` only when that instance binding is
      actually present — a real structural guarantee from the same loader-time
      cross-check, not a hardcoded literal.

    Returns ``None`` (dimension absent, never a fabricated verdict) until
    :attr:`_EnvironmentScopeDimensionState.active_scope` is filled in — the same
    composition-time-window discipline :func:`_recovery_dimension_reader_for` documents.
    """

    def _reader() -> DimensionReport | None:
        active_scope = state.active_scope
        if active_scope is None:
            return None
        if transport_nature(active_scope).reaches_broker is False:
            return DimensionReport(
                bound_generation=0, positively_established=True, restrictive_floor=0
            )
        scope_environment = (
            active_scope.environment_binding.get(
                active_scope.capability_tuples[0].environment
            )
            if active_scope.capability_tuples
            else None
        )
        instance = active_scope.instance
        evidence_environment = instance.environment if instance is not None else None
        inherited = False if instance is not None else None
        return DimensionReport(
            bound_generation=0,
            positively_established=environment_binding_ok(
                evidence_environment=evidence_environment,
                scope_environment=scope_environment,
                inherited=inherited,
            ),
            restrictive_floor=0,
        )

    return _reader


def _aggregate_risk_dimension_reader_for(
    risk_service: RecordingAggregateRiskService,
) -> Callable[[], DimensionReport | None]:
    """The AGGREGATE_RISK currentness dimension (Phase 5 W3.2, plan §2 decision 4 —
    dimension-owner replacement 1/6 of this wave's six).

    The owner is step 6's own :class:`~tos_runtime.compose.context
    .RecordingAggregateRiskService` — this reader copies its already-decided
    :attr:`~tos.are.AggregateRiskDecision.result` verbatim via the mandated positive-
    identity check (``is tos.are.RiskDecisionResult.GRANT``, never truthiness — the
    SAME "구조 파생 > 자기신고" discipline every other reader in this module already
    applies), and :attr:`~tos.are.AggregateRiskDecision.decision_generation` as a REAL,
    non-invented generation (unlike :func:`_recovery_dimension_reader_for`'s explicit
    ``0``, this owner actually has one to report).

    **Disclosed partial ownership (plan §2 decision 4).** ``risk_service.decide``'s own
    kernel predicates (``snapshot_scope_complete`` / ``adverse_increment`` /
    ``envelope_bound_not_enlarged``) already consumed three step 6/7 admission witnesses
    — ``numerically_safe`` / ``valuation_ok`` / ``all_fields_attributed`` — that this
    composition still supplies from :mod:`tos_runtime.compose._risk_attestations` as
    operator-attested config, not a runtime-derived fact (re-review finding F4,
    ``_wiring.py``'s ``wrap_aggregate_risk_inputs_provider``). This dimension is
    therefore a **verdict owner**, not an **input owner**: it honestly reports the
    kernel's own already-computed GRANT/DENY/UNKNOWN result, but that result's own
    inputs are still attestations underneath it — a future Phase 6 owner for those three
    keys does not change what this reader reports, only what feeds it.

    Returns ``None`` (dimension absent, never a fabricated verdict) until step 6 has
    recorded its first decision for this process — the same "no attempt yet" absence
    every recorder-backed reader in this module already returns.
    """

    def _reader() -> DimensionReport | None:
        decision = risk_service.last_decision
        if decision is None:
            return None
        return DimensionReport(
            bound_generation=decision.decision_generation,
            positively_established=decision.result is RiskDecisionResult.GRANT,
            restrictive_floor=0,
        )

    return _reader


@dataclass
class _ConstructionDimensionState:
    """A late-bound cell for the CONSTRUCTION dimension reader (below).

    ``CurrentnessAssembler`` is constructed (in
    :func:`~tos_runtime.compose._currentness_wiring._build_risk_and_currentness`,
    design #40 §5 order 6) strictly BEFORE :func:`~tos_runtime.compose._wiring
    ._build_construction_stages` builds step 2's own ``OrderConstructionStage`` — the
    same "constructed before its dependency exists" ordering :class:`_RecoveryDimensionState`
    already documents.
    """

    construction_stage: OrderConstructionStage | None = None


def _construction_dimension_reader_for(
    state: _ConstructionDimensionState,
) -> Callable[[], DimensionReport | None]:
    """The CONSTRUCTION currentness dimension (Phase 5 W3.2, plan §2 decision 3 —
    dimension-owner replacement 2/6 of this wave's six).

    The owner is step 2's own :class:`~tos.egressgw.OrderConstructionStage` —
    ``.construction`` is a :class:`~tos.egressgw.CandidateConstruction`, which its OWN
    kernel validator (``records.py``'s ``_shape_is_one_of_the_sanctioned_bundles``)
    already guarantees carries either NO ioc verdict (denied) or ALL THREE (built) —
    never a partially-formed mix. This reader reads exactly those three already-computed
    verdicts, never re-deriving them: :attr:`~tos.egressgw.CandidateConstruction
    .conformance_result` / ``.numerical_result`` (both :class:`~tos.ioc.ConformanceResult`
    — the mandated positive-identity check, ``is ConformanceResult.CONFORMANT``, never
    truthiness; the type's own ``__bool__`` raises for exactly this reason) and
    ``.no_silent_widening_ok`` (already a plain ``bool``).

    ``bound_generation=0``: step 2 is wired with a compose-literal ``generation=1``
    (``_wiring.py``'s ``_build_construction_stages``), never a real per-attempt counter,
    so there is no honest generation-COUNTER fact to report — the same "an owner
    reporting 0 is that owner's own deliberate choice, not an invented default"
    discipline :func:`_recovery_dimension_reader_for`'s own ``bound_generation=0``
    already documents for the SAME kind of gap. (The kernel's own
    :func:`~tos.cur.predicates.dimension_positively_established` requires a CONCRETE
    ``bound_generation`` — ``None`` is treated as a missing coordinate, never as "no
    generation exists", so ``0`` is the only honest choice here, not ``None``.)

    Returns ``None`` (dimension absent) until the cell is filled in, or while step 2 has
    not yet produced a candidate for this attempt (``stage.construction is None``) —
    never a fabricated verdict for either case.
    """

    def _reader() -> DimensionReport | None:
        stage = state.construction_stage
        if stage is None:
            return None
        artifact = stage.construction
        if artifact is None:
            return None
        established = (
            artifact.conformance_result is ConformanceResult.CONFORMANT
            and artifact.numerical_result is ConformanceResult.CONFORMANT
            and artifact.no_silent_widening_ok is True
        )
        return DimensionReport(
            bound_generation=0,
            positively_established=established,
            restrictive_floor=0,
        )

    return _reader


@dataclass
class _ConstraintDimensionState:
    """A late-bound cell for the CONSTRAINT dimension reader (below).

    Step 3's own ``VenueConstraintStage`` is built alongside step 2 in
    :func:`~tos_runtime.compose._wiring._build_construction_stages`, strictly AFTER this
    module's :func:`~tos_runtime.compose._currentness_wiring._build_risk_and_currentness`
    runs — the same ordering :class:`_ConstructionDimensionState` already documents.
    Unlike CONSTRUCTION, the cell holds a :class:`~tos_runtime.compose.context
    .VerdictRecorder` WRAPPING the stage (never the bare stage itself): the raw
    ``VenueConstraintStage`` instance stays the one :class:`~tos_runtime.compose.context
    .ComposeContextResolver` reads ``.resolved_shape``/``.shape_constraints`` off
    directly (unchanged by this wave), and the recorder is a SEPARATE wrapper around the
    SAME instance, registered as the actual ``CommitmentStep.VENUE_ADMISSIBILITY_DECISION``
    callable in the engine's stage map — mirroring exactly how step 4/9's recorders
    coexist with their own raw stage/service objects elsewhere in this codebase.
    """

    venue_recorder: VerdictRecorder | None = None


def _constraint_dimension_reader_for(
    state: _ConstraintDimensionState,
) -> Callable[[], DimensionReport | None]:
    """The CONSTRAINT currentness dimension (Phase 5 W3.2, plan §2 decision 2/3 —
    dimension-owner replacement 3/6 of this wave's six).

    Derived from step 3's own ``VenueConstraintStage`` outcome — the SAME structural-
    derivation discipline :func:`_trading_approval_dimension_reader_for` already applies
    to step 4 (``positively_established`` only when step 3 itself last recorded
    ``StageOutcome.ADMIT`` via the kernel's own ``order_shape_admissible``, which
    ``VenueConstraintStage.__call__`` already evaluates — never a second call to it here).

    **Disclosed partial coverage (plan §2 decision 2, survey §1 CONSTRAINT row).** The
    kernel's OWN :func:`~tos.venue.predicates.account_constraint_conservative` is a
    SEPARATE CONSTRAINT-axis predicate this composition has no caller for anywhere (no
    lane ever builds the ``AccountConstraintInputs`` it needs) — this reader reports only
    what step 3's stage ALREADY evaluates (``order_shape_admissible``), never inventing
    inputs to reach the uncalled predicate too. The same partial-coverage honesty
    :func:`_environment_scope_dimension_reader_for`'s own module history already
    established (W3.1 independent review MEDIUM-4's EGRESS_IDENTITY reversion) — this
    reader reports its own real, if partial, coverage rather than over-claiming full
    CONSTRAINT-axis establishment.

    ``bound_generation=0``: step 3's :class:`~tos.engine.records.StageVerdict` carries no
    generation counter of its own — the same explicit-``0`` discipline
    :func:`_construction_dimension_reader_for` documents.

    Returns ``None`` (dimension absent) until the cell is filled in, or while step 3 has
    not yet recorded any verdict for this attempt.
    """

    def _reader() -> DimensionReport | None:
        recorder = state.venue_recorder
        verdict = recorder.last_verdict if recorder is not None else None
        if verdict is None:
            return None
        return DimensionReport(
            bound_generation=0,
            positively_established=verdict.outcome is StageOutcome.ADMIT,
            restrictive_floor=0,
        )

    return _reader


@dataclass
class _DecisionProofIntentDimensionState:
    """A late-bound cell for the DECISION_PROOF_INTENT dimension reader (below).

    Step 13's own ``AttemptBindVerificationStage`` is built in
    :func:`~tos_runtime.compose._wiring._build_currentness_stages`, strictly AFTER this
    module's :func:`~tos_runtime.compose._currentness_wiring._build_risk_and_currentness`
    runs — the same ordering :class:`_ConstraintDimensionState` already documents. The
    cell holds a :class:`~tos_runtime.compose.context.VerdictRecorder` wrapping step 13
    (nothing else reads the raw stage directly today, so this wave replaces it outright
    rather than keeping a parallel raw reference, unlike CONSTRAINT's venue stage).
    """

    step13_recorder: VerdictRecorder | None = None


def _decision_proof_intent_dimension_reader_for(
    state: _DecisionProofIntentDimensionState,
) -> Callable[[], DimensionReport | None]:
    """The DECISION_PROOF_INTENT currentness dimension (Phase 5 W3.2, plan §2 decision 2 —
    dimension-owner replacement 4/6 of this wave's six).

    Derived from step 13's own ``AttemptBindVerificationStage`` outcome —
    ``positively_established`` only when step 13 itself last recorded
    ``StageOutcome.ADMIT`` via the kernel's own ``tos.iap.exact_binding_holds``, which
    that stage already evaluates every attempt (never a second call to it here). This
    axis is deliberately DISJOINT from TRADING_APPROVAL (step 4,
    :func:`_trading_approval_dimension_reader_for`): step 4 answers "was this decision
    independently approved", step 13 answers "does the reservation/permit/approval
    digest chain THIS attempt actually carries still match what was bound" — two
    different kernel predicates over two different Stages, never the same fact read
    twice under two names.

    **Considered and rejected: sourcing from the item-16 egress currentness proof
    instead (survey §0 DECISION_PROOF_INTENT row's "또는 proof.result" alternative).**
    :meth:`~tos_runtime.currentness.proof.EgressCurrentnessProofIssuer.item16_fields`
    would seem to offer both a verdict (``egress_currentness_result``) and a real
    generation (``committed_revision.commit_index``) for this SAME attempt — but
    :meth:`~tos_runtime.compose.context.ComposeContextResolver
    ._issue_egress_currentness_proof` assembles the FULL currentness vector (which would
    have to invoke THIS very reader) strictly BEFORE it ever calls
    ``proof_issuer.issue(...)`` for that attempt (two-pass assemble, then issue — module
    docstring, "Two-pass assemble"). A reader that read this attempt's own proof would
    therefore always observe "no proof issued yet" during the ONLY assemble() calls that
    happen before issuance — a genuine circular dependency (this dimension gates whether
    the vector is complete enough to issue a ``CURRENT`` proof; the proof cannot supply
    the fact that gates its own issuance), not merely an ordering inconvenience. This
    reader therefore sources ONLY from step 13's own recorder, never from the proof
    issuer, and ``bound_generation=0`` (no independent, non-circular generation fact
    exists at step 13's own :class:`~tos.engine.records.StageVerdict` — the same
    explicit-``0`` discipline :func:`_recovery_dimension_reader_for` documents, never
    ``None``: the kernel's own :func:`~tos.cur.predicates.dimension_positively_established`
    treats a ``None`` ``bound_generation`` as a missing coordinate, so ``0`` is the only
    honest choice) — a considered deviation from treating ``committed_revision.commit_index``
    as available, documented here rather than silently reaching for a value this module
    cannot actually supply without contradiction.

    Returns ``None`` (dimension absent) until the cell is filled in, or while step 13 has
    not yet recorded any verdict for this attempt.
    """

    def _reader() -> DimensionReport | None:
        recorder = state.step13_recorder
        verdict = recorder.last_verdict if recorder is not None else None
        if verdict is None:
            return None
        return DimensionReport(
            bound_generation=0,
            positively_established=verdict.outcome is StageOutcome.ADMIT,
            restrictive_floor=0,
        )

    return _reader


@dataclass
class _PostTradeDimensionState:
    """A late-bound cell for the POST_TRADE dimension reader (below).

    TOS Phase 5 W2-R's own :class:`~tos_runtime.posttrade.release_consumer
    .FinalityReleaseConsumer` is built (and possibly never built at all, when
    ``runtime.driver`` did not survive to receive one — see
    :func:`~tos_runtime.compose._release_wiring.apply_release_wiring`'s own docstring)
    strictly AFTER this module's
    :func:`~tos_runtime.compose._currentness_wiring._build_risk_and_currentness` runs —
    the same "constructed before its dependency exists" ordering every other late-bound
    cell in this module documents, except here the dependency may never arrive at all,
    which is exactly why :attr:`consumer` stays ``None``-typed rather than
    assumed-eventual.
    """

    consumer: FinalityReleaseConsumer | None = None


def _post_trade_dimension_reader_for(
    state: _PostTradeDimensionState,
) -> Callable[[], DimensionReport | None]:
    """The POST_TRADE currentness dimension (Phase 5 W3.2, plan §2 decision 5 —
    dimension-owner replacement 5/6 of this wave's six).

    **A deliberately different axis from every other reader in this module.** Every
    other dimension answers "is it currently safe to SEND this attempt"; POST_TRADE
    answers "did this SCOPE's most recent SEND finish cleanly" — a fact about the past,
    not the present attempt. Sourced from
    :meth:`~tos_runtime.posttrade.release_consumer.FinalityReleaseConsumer
    .latest_release_is_conflict_free`, which scans this consumer's own durable
    ``CAPACITY_RELEASE_INTENT``/``CAPACITY_RELEASE_HELD`` evidence rows for this
    consumer's own reservation scope and reports ``False`` only when the MOST RECENT one
    is a HELD row whose reason is ``ReleaseHoldReason.NOT_CORROBORATED`` — the one HELD
    reason that structurally means gate 3's reconciliation found a genuine conflict
    (an orphan broker order or a non-``MATCHED`` classification) between what this scope
    expected and what actually happened downstream. Every other HELD reason (no witness
    yet, proof not yet reloaded, reconciliation itself unavailable, ...) is a normal,
    transient "not yet complete" gate, not a conflict this dimension reports on — folding
    them all into ``False`` would permanently block new risk on ordinary pipeline timing,
    which plan §2 decision 5 explicitly rejects.

    **First attempt ⇒ ``True``, never ``None`` (plan §2 decision 5's own correction).** A
    scope with NO recorded post-trade evidence at all has no post-trade fact yet — which
    is the NORMAL state before any attempt has ever sent, not an unknown or absent state
    that should block the very first send. :meth:`FinalityReleaseConsumer
    .latest_release_is_conflict_free` itself returns ``True`` for this case (vacuous
    pass, mirroring :func:`_environment_scope_dimension_reader_for`'s own vacuous-True
    discipline for a non-broker-reaching scope).

    Returns ``None`` (dimension absent, never a fabricated verdict) ONLY when this
    composition never built a consumer at all (:attr:`_PostTradeDimensionState.consumer`
    stays ``None`` — e.g. the W1 recovery barrier detached the driver before release
    wiring could attach one) — a genuinely different case from "no evidence yet",
    which the consumer itself already resolves to ``True``.

    ``bound_generation=0``: no process-wide generation counter exists for a per-scope
    evidence scan (the same explicit-``0`` discipline CONSTRUCTION/CONSTRAINT/
    DECISION_PROOF_INTENT above document — never ``None``, which the kernel's own
    :func:`~tos.cur.predicates.dimension_positively_established` treats as a missing
    coordinate).
    """

    def _reader() -> DimensionReport | None:
        consumer = state.consumer
        if consumer is None:
            return None
        return DimensionReport(
            bound_generation=0,
            positively_established=consumer.latest_release_is_conflict_free(),
            restrictive_floor=0,
        )

    return _reader


@dataclass
class _ReleaseDimensionState:
    """A late-bound cell for the RELEASE dimension reader (below).

    :func:`~tos_runtime.compose._wiring._stage_b_release_probe` runs inside
    :func:`~tos_runtime.compose._wiring._boot_services`, strictly AFTER this module's
    :func:`~tos_runtime.compose._currentness_wiring._build_risk_and_currentness` — the
    same ordering discipline every other late-bound cell in this module documents.
    """

    release_admitted: bool | None = None


def _release_dimension_reader_for(
    state: _ReleaseDimensionState,
) -> Callable[[], DimensionReport | None]:
    """The RELEASE currentness dimension (Phase 5 W3.2, plan §2 decision 6 —
    dimension-owner replacement 6/6 of this wave's six).

    The owner is boot's own STAGE B release probe
    (:func:`~tos_runtime.compose._wiring._stage_b_release_probe`), which already calls
    the kernel's ``tos.sci.predicates.software_deployment_ok_verdict`` and either admits
    (returning ``True``) or raises :class:`~tos_runtime.compose._wiring
    .ReleaseAdmissionRefused` — a composition that reaches THIS reader at all has, by
    construction, already survived that refusal, so :attr:`_ReleaseDimensionState
    .release_admitted` is always ``True`` once filled (never independently re-evaluated
    here). This is a real, kernel-derived fact honestly reported, not a fabricated
    constant — it happens to be constant for this process's entire lifetime because a
    live ``ComposedRuntime`` cannot otherwise exist (the SAME "single boot-time judgement,
    not a versioned counter" shape :func:`_recovery_dimension_reader_for`'s own
    ``bound_generation=0`` documents for a different owner).

    **Disclosed static input (survey §0 RELEASE row).** The probe's own
    ``ReleaseAdmissionConfig.admission_result`` is an OPERATOR-DECLARED STATIC value
    (``tos_runtime/release/config.py``'s own module docstring: "Phase 2 has no live SCI
    admission-decision runtime") — this reader reports the kernel verdict the probe
    already computed over that static input, never claiming the input itself became
    live.

    ``bound_generation=0``: ``ReleaseAdmissionConfig`` carries no Release Generation
    field at all (survey §0) — the same explicit-``0`` discipline every other
    generation-less reader in this module documents (never ``None``, which the kernel's
    own :func:`~tos.cur.predicates.dimension_positively_established` treats as a missing
    coordinate, not an honest absence).

    Returns ``None`` (dimension absent) only during the composition-time window before
    ``_boot_services`` has returned — the same window every other late-bound cell in
    this module documents.
    """

    def _reader() -> DimensionReport | None:
        if state.release_admitted is None:
            return None
        return DimensionReport(
            bound_generation=0,
            positively_established=state.release_admitted,
            restrictive_floor=0,
        )

    return _reader


@dataclass
class _DimensionStates:
    """Every late-bound dimension-reader cell :func:`_build_dimension_readers` creates —
    bundled so :func:`~tos_runtime.compose._currentness_wiring._build_risk_and_currentness`
    can hand all of them to :class:`~tos_runtime.compose._currentness_wiring
    ._RiskAndCurrentness` in one field, and :func:`~tos_runtime.compose.root
    .compose_paper_runtime` can late-bind each once its own recorder/verdict exists."""

    action_flow: _ActionFlowDimensionState
    recovery: _RecoveryDimensionState
    trading_approval: _TradingApprovalDimensionState
    environment_scope: _EnvironmentScopeDimensionState
    #: Phase 5 W3.2's five late-bound cells (plan §2 decisions 2-6) — see each cell's own
    #: docstring above.
    construction: _ConstructionDimensionState
    constraint: _ConstraintDimensionState
    decision_proof_intent: _DecisionProofIntentDimensionState
    post_trade: _PostTradeDimensionState
    release: _ReleaseDimensionState


def _build_dimension_readers(
    *,
    rcl_log: SqliteCommitLog,
    writer_epoch: int,
    authority_epoch_service: SafetyAuthorityEpochService,
    currentness_policy: CurrentnessPolicy,
    environment_label: str,
    safety_mesh: _SafetyMesh,
    risk_service: RecordingAggregateRiskService,
) -> tuple[
    dict[DimensionKey, tuple[str, Callable[[], DimensionReport | None]]],
    _DimensionStates,
]:
    """The full ``dimension_readers`` map (module docstring, "Reader map") — split out
    of :func:`~tos_runtime.compose._currentness_wiring._build_risk_and_currentness`
    purely for the size budget; no behavioural difference from having this inline
    there."""
    dimension_states = _DimensionStates(
        action_flow=_ActionFlowDimensionState(),
        recovery=_RecoveryDimensionState(),
        trading_approval=_TradingApprovalDimensionState(),
        environment_scope=_EnvironmentScopeDimensionState(),
        construction=_ConstructionDimensionState(),
        constraint=_ConstraintDimensionState(),
        decision_proof_intent=_DecisionProofIntentDimensionState(),
        post_trade=_PostTradeDimensionState(),
        release=_ReleaseDimensionState(),
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
            _environment_scope_dimension_reader_for(
                environment_label, dimension_states.environment_scope
            ),
        ),
        DimensionKey.AGGREGATE_RISK: (
            "tos_runtime.risk",
            _aggregate_risk_dimension_reader_for(risk_service),
        ),
        DimensionKey.CONSTRUCTION: (
            "tos_runtime.compose",
            _construction_dimension_reader_for(dimension_states.construction),
        ),
        DimensionKey.CONSTRAINT: (
            "tos_runtime.compose",
            _constraint_dimension_reader_for(dimension_states.constraint),
        ),
        DimensionKey.DECISION_PROOF_INTENT: (
            "tos_runtime.currentness",
            _decision_proof_intent_dimension_reader_for(
                dimension_states.decision_proof_intent
            ),
        ),
        DimensionKey.POST_TRADE: (
            "tos_runtime.posttrade",
            _post_trade_dimension_reader_for(dimension_states.post_trade),
        ),
        DimensionKey.RELEASE: (
            "tos_runtime.release",
            _release_dimension_reader_for(dimension_states.release),
        ),
        **safety_mesh.dimension_readers,
    }
    return dimension_readers, dimension_states
