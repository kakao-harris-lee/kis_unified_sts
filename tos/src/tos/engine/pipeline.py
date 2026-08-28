"""Decision-pipeline orchestration — the RFC-003 §7 four-phase span (design #31 §3).

The pipeline **drives** the already-shipped evaluator; it never re-authors it (design #31 §0.2-1 /
§3.1). RFC-003 §7:199-215 phases, realized here:

1. **Accept context** (§7:201-204). A missing / stale / incomplete / invalid Capsule forbids a
   decision and yields a restrictive no-action. So the Capsule's issuance, digest, required-covered
   completeness (``tos.capsule.capsule`` lines 189-204), scope agreement, and the injected
   :mod:`tos.time` freshness verdicts are all confirmed **positively** *before* ``evaluate`` is
   called; if any fails, ``evaluate`` is not called at all.
2. **Interpret** (§7:205-207). :func:`tos.dsl.evaluate` — a pure function whose signature exposes
   no ambient source and no fetch callable, so "no hidden state, default, or out-of-context fetch"
   is structural, not promised.
3. **Decide** (§7:208-212). The returned ``DecisionKind`` outcome. Slice #1 is per-instrument
   (RFC-003 §9:327-339), so a ``VECTOR`` outcome is **fail-closed**: no progress, restrictive
   no-action, recorded. The vector folding rule belongs to a later multi-symbol cycle.
4. **Bind and emit** (§7:213-215). The outcome already binds the exact Capsule identity + digest
   through ``RecordedInputSignature``; "binding does not create authority". Emission ends the
   pipeline (§7:217-220) — approval, commitment, and transmission are the sequencer's downstream.

**Bounded evaluation (design #31 §3.4 / D3).** :func:`tos.dsl.resolve_bound` is symbolic integer
accounting, not a runtime interrupt: it cannot stop ``evaluate`` mid-run and ``evaluate`` reports
no step count. So the budget is a **pre-evaluation gate** over a statically derived work count
(:func:`~tos.engine.admission.policy_work_steps`), and an exhausted budget folds to a *distinctly
recorded* degradation no-action that never enters the commitment flow.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #31 §0.3). No clock, no RNG.
"""

from __future__ import annotations

from dataclasses import dataclass

from tos.dsl import (
    BoundState,
    EvaluationResult,
    NoActionOutcome,
    Outcome,
    PortfolioVector,
    Proposal,
    RecordedInputSignature,
    degrades_to_no_action,
    evaluate_resolved,
    resolve_bound,
    select_outcome,
)
from tos.engine._base import ArtifactStatus, CanonicalizationScheme
from tos.engine.admission import policy_work_steps
from tos.engine.records import (
    DecisionTickPayload,
    EngineConfiguration,
    EngineEvidenceRecord,
    InstrumentKey,
    RegisteredStrategy,
    TimeAdmissionInputs,
)
from tos.engine.sink import EvidenceSink
from tos.engine.vocabulary import EvidenceKind, HaltReason
from tos.time import (
    FreshnessVerdict,
    freshness_verdict,
    session_open_positively,
    snapshot_age_admissible,
    state_permits_new_normal_risk,
)

__all__ = [
    "PipelineResult",
    "capsule_admitted",
    "run_decision_pipeline",
    "time_admits",
]

#: The rationale recorded on a bounded-evaluation degradation. A recorded decision states why it
#: followed from the context (RFC-008 §7); a degradation's "why" is the exhausted bound.
_DEGRADED_RATIONALE = (
    "bounded evaluation exhausted its injected symbolic budget before evaluation — degraded to "
    "no-action for the strategy scope (DCE-INV-007; design #31 §3.4)"
)


@dataclass(frozen=True)
class PipelineResult:
    """The outcome of one decision-pipeline run (design #31 §3).

    ``proposal`` is populated **only** when the run produced a single per-instrument Proposal that
    passed the scope cross-check; it is what the sequencer consumes. Every other terminal shape —
    a withheld decision, an ordinary no-action, a degradation, an unsupported vector — leaves it
    ``None`` and records a named :class:`~tos.engine.vocabulary.HaltReason`.
    """

    instrument_key: InstrumentKey
    halt_reason: HaltReason | None = None
    proposal: Proposal | None = None
    outcome: Outcome | None = None
    signature: RecordedInputSignature | None = None
    bound_state: BoundState | None = None
    work_steps: int | None = None
    detail: str | None = None

    @property
    def degraded(self) -> bool:
        """Whether this run folded to a bounded-evaluation degradation (design #31 §3.4)."""
        return self.halt_reason is HaltReason.DEGRADED_BOUND_EXHAUSTED

    @property
    def outcome_digest(self) -> str | None:
        """The emitted outcome's canonical digest, when an outcome was emitted."""
        return None if self.outcome is None else self.outcome.canonical_digest


def time_admits(inputs: TimeAdmissionInputs) -> tuple[bool, str | None]:
    """Whether the injected time coordinates positively admit a decision (design #31 §2.3).

    Four positive checks, each delegated to the shipped clock-free :mod:`tos.time` predicates —
    the engine recomputes none of them:

    * :func:`~tos.time.freshness_verdict` is ``FRESH`` (UNKNOWN / STALE / CONFLICTED deny);
    * :func:`~tos.time.snapshot_age_admissible` is ``True`` (an unknown age bound or an
      unestablished maximum denies);
    * :func:`~tos.time.session_open_positively` is ``True`` (unknown phase, missing calendar,
      tz conflict, ambiguous local time, or a boundary inside the uncertainty interval all deny);
    * :func:`~tos.time.state_permits_new_normal_risk` is ``True`` — only ``TRUSTED`` permits new
      normal risk.

    A missing session context, uncertainty interval, or health state denies: absence is not
    permission.

    Args:
        inputs: The injected time coordinates carried by the event.

    Returns:
        ``(admitted, reason)`` — ``reason`` is ``None`` only when admitted.
    """
    verdict = freshness_verdict(
        source_age=inputs.source_age,
        delay_bounds=inputs.delay_bounds,
        max_age_bound=inputs.max_age_bound,
        future_tolerance=inputs.future_tolerance,
    )
    if verdict is not FreshnessVerdict.FRESH:
        return False, f"freshness verdict is {verdict.value}, not FRESH (ADR-002-008 §9)"
    if not snapshot_age_admissible(inputs.snapshot_age_bound, inputs.maximum_consumer_age_ms):
        return False, (
            "snapshot age bound is inadmissible or unestablished "
            f"(bound={inputs.snapshot_age_bound!r}, max={inputs.maximum_consumer_age_ms!r})"
        )
    if inputs.session_context is None or inputs.uncertainty_interval is None:
        return False, (
            "session context / uncertainty interval is absent — a session is never assumed open "
            "(ADR-002-008 §12:319)"
        )
    if not session_open_positively(inputs.session_context, inputs.uncertainty_interval):
        return False, "the session is not positively, unambiguously open (ADR-002-008 §12:319)"
    if inputs.health_state is None:
        return False, "time health state is absent — new normal risk is not permitted"
    if not state_permits_new_normal_risk(inputs.health_state):
        return False, (
            f"time health state {inputs.health_state.value} does not permit new normal risk — "
            "only TRUSTED does (ADR-002-008 §6.1-6.3)"
        )
    return True, None


def capsule_admitted(
    payload: DecisionTickPayload,
) -> tuple[HaltReason | None, str | None]:
    """Whether the bound Decision Context Capsule may be used (RFC-003 §7:201-204).

    A missing, stale, incomplete, or invalid Capsule forbids a decision. Every check is positive:

    * the Capsule is ``ISSUED`` and carries a concrete canonical digest (a ``DRAFT`` capsule is
      pre-issuance — its digest is not yet computed);
    * its ``_REQUIRED_COVERED`` set is complete (``missing_required_fields()`` is empty);
    * its declared scope agrees exactly with the event's instrument key — the third leg of the
      event ↔ strategy ↔ capsule agreement (design #31 §3.3);
    * the injected time coordinates admit (:func:`time_admits`).

    Args:
        payload: The ``DECISION_TICK`` payload.

    Returns:
        ``(halt_reason, detail)`` — ``(None, None)`` when the Capsule is admitted.
    """
    capsule = payload.capsule
    if capsule.status is not ArtifactStatus.ISSUED:
        return HaltReason.CAPSULE_NOT_ISSUED, f"capsule status is {capsule.status}"
    if capsule.canonical_digest is None or capsule.capsule_id is None:
        return HaltReason.CAPSULE_INCOMPLETE, "capsule identity/digest is absent"
    missing = capsule.missing_required_fields()
    if missing:
        return HaltReason.CAPSULE_INCOMPLETE, f"capsule required-covered fields missing: {missing}"
    key = payload.instrument_key
    if capsule.scope.account != key.account or capsule.scope.instrument != key.instrument:
        return HaltReason.CAPSULE_SCOPE_MISMATCH, (
            f"capsule scope ({capsule.scope.account!r}, {capsule.scope.instrument!r}) does not "
            f"match the event key ({key.account!r}, {key.instrument!r})"
        )
    admitted, reason = time_admits(payload.time)
    if not admitted:
        return HaltReason.TIME_NOT_ADMITTED, reason
    return None, None


def _degraded_no_action(
    *,
    entry: RegisteredStrategy,
    payload: DecisionTickPayload,
    scheme: CanonicalizationScheme,
) -> NoActionOutcome:
    """Build the recorded degradation No-Action Outcome (the ``on_exhaustion`` factory, §3.4)."""
    strategy = entry.strategy
    capsule = payload.capsule
    return NoActionOutcome.issue(  # type: ignore[return-value]
        scheme=scheme,
        outcome_id=(
            f"degraded:{strategy.strategy_id}:{capsule.capsule_id}:{entry.config.config_version}"
        ),
        rationale=_DEGRADED_RATIONALE,
        decision_context_capsule={
            "capsule_id": capsule.capsule_id,
            "canonical_digest": capsule.canonical_digest,
        },
        strategy_version=strategy.canonical_digest,
        dsl_version=strategy.dsl_version,
        config_version=entry.config.config_version,
    )


def run_decision_pipeline(
    *,
    entry: RegisteredStrategy,
    payload: DecisionTickPayload,
    configuration: EngineConfiguration,
    scheme: CanonicalizationScheme,
    sink: EvidenceSink,
) -> PipelineResult:
    """Run the RFC-003 §7 four-phase decision pipeline for one registered strategy.

    Args:
        entry: The admitted strategy + its authored configuration + its derived key.
        payload: The ``DECISION_TICK`` payload.
        configuration: The injected engine configuration (budget, versions).
        scheme: The resolved canonicalization scheme bound into emitted artifacts.
        sink: The provisional evidence sink.

    Returns:
        The :class:`PipelineResult`. ``proposal`` is set only when a single per-instrument Proposal
        was emitted and its scope matched the key.
    """
    key = payload.instrument_key

    # --- phase 1: accept context (RFC-003 §7:201-204) ----------------------------------------
    if entry.instrument_key != key:
        return _withheld(
            sink,
            key,
            HaltReason.EVENT_STRATEGY_KEY_MISMATCH,
            f"event key {(key.account, key.instrument)} does not match the strategy's declared "
            f"key {(entry.instrument_key.account, entry.instrument_key.instrument)}",
        )
    halt, detail = capsule_admitted(payload)
    if halt is not None:
        return _withheld(sink, key, halt, detail)

    # --- bounded-evaluation pre-gate (design #31 §3.4) ---------------------------------------
    policy = entry.strategy.policy
    if policy is None:  # pragma: no cover - admission refuses a policy-less strategy
        return _withheld(
            sink, key, HaltReason.CAPSULE_INCOMPLETE, "registered strategy carries no policy"
        )
    work_steps = policy_work_steps(policy)
    bound_state = resolve_bound(
        work_steps=work_steps, budget_steps=configuration.dsl_evaluation_budget_steps
    )

    def _on_exhaustion() -> NoActionOutcome:
        return _degraded_no_action(entry=entry, payload=payload, scheme=scheme)

    if degrades_to_no_action(bound_state):
        degraded = select_outcome(
            bound_state, completed_outcome=_on_exhaustion(), on_exhaustion=_on_exhaustion
        )
        sink.record(
            EngineEvidenceRecord(
                kind=EvidenceKind.DECISION_DEGRADED,
                instrument_key=key,
                halt_reason=HaltReason.DEGRADED_BOUND_EXHAUSTED,
                outcome_type=type(degraded).__name__,
                outcome_digest=degraded.canonical_digest,
                capsule_id=payload.capsule.capsule_id,
                capsule_digest=payload.capsule.canonical_digest,
                strategy_version=entry.strategy.canonical_digest,
                config_version=entry.config.config_version,
                detail=(
                    f"work_steps={work_steps} exceeded the injected budget_steps="
                    f"{configuration.dsl_evaluation_budget_steps}; the commitment flow is not "
                    "entered"
                ),
            )
        )
        return PipelineResult(
            instrument_key=key,
            halt_reason=HaltReason.DEGRADED_BOUND_EXHAUSTED,
            outcome=degraded,
            bound_state=bound_state,
            work_steps=work_steps,
        )

    # --- phases 2-4: interpret / decide / bind and emit (RFC-003 §7:205-215) ------------------
    # The resolved Critical Input value view rides through unconditionally (design #32 §3.2 (3)):
    # ``payload.value_view`` is ``None`` for a value-free tick, and ``evaluate_resolved`` with
    # ``resolved_context=None`` reproduces the shipped ``evaluate`` exactly — same environment,
    # same outcome, same signature. When a view *is* present its canonical digest is appended to
    # the recorded signature, so two bars that differ only in their values are distinguishable on
    # replay (RFC-008 §9:302-306).
    result: EvaluationResult = evaluate_resolved(
        entry.strategy,
        payload.capsule,
        entry.config,
        scheme=scheme,
        enforcement_mechanism_version=configuration.enforcement_mechanism_version,
        resolved_context=payload.value_view,
    )
    outcome = select_outcome(
        bound_state, completed_outcome=result.outcome, on_exhaustion=_on_exhaustion
    )

    if isinstance(outcome, PortfolioVector):
        return _withheld(
            sink,
            key,
            HaltReason.VECTOR_OUTCOME_UNSUPPORTED,
            "a DecisionKind.VECTOR outcome violates the slice's per-instrument premise "
            "(RFC-003 §9:327-339); the vector folding rule belongs to a later multi-symbol cycle",
            outcome=outcome,
            signature=result.recorded_input_signature,
            bound_state=bound_state,
            work_steps=work_steps,
        )

    if isinstance(outcome, NoActionOutcome):
        sink.record(
            EngineEvidenceRecord(
                kind=EvidenceKind.DECISION_OUTCOME_EMITTED,
                instrument_key=key,
                halt_reason=HaltReason.NO_ACTION_OUTCOME,
                outcome_type=type(outcome).__name__,
                outcome_digest=outcome.canonical_digest,
                capsule_id=result.recorded_input_signature.capsule_id,
                capsule_digest=result.recorded_input_signature.capsule_canonical_digest,
                strategy_version=result.recorded_input_signature.authored_strategy_version,
                config_version=result.recorded_input_signature.config_version,
                detail="no-action leaves exposure and starts no commitment flow (RFC-003 §7:217)",
            )
        )
        return PipelineResult(
            instrument_key=key,
            halt_reason=HaltReason.NO_ACTION_OUTCOME,
            outcome=outcome,
            signature=result.recorded_input_signature,
            bound_state=bound_state,
            work_steps=work_steps,
        )

    # A Proposal (action or explicit flat). Its scope must be the dispatch key — a structural
    # cross-check, not a trusted claim (design #31 §3.3 삼자 일치).
    if outcome.account != key.account or outcome.instrument != key.instrument:
        return _withheld(
            sink,
            key,
            HaltReason.PROPOSAL_SCOPE_MISMATCH,
            f"emitted proposal scope ({outcome.account!r}, {outcome.instrument!r}) does not match "
            f"the dispatch key ({key.account!r}, {key.instrument!r})",
            outcome=outcome,
            signature=result.recorded_input_signature,
            bound_state=bound_state,
            work_steps=work_steps,
        )

    sink.record(
        EngineEvidenceRecord(
            kind=EvidenceKind.DECISION_OUTCOME_EMITTED,
            instrument_key=key,
            outcome_type=type(outcome).__name__,
            outcome_digest=outcome.canonical_digest,
            capsule_id=result.recorded_input_signature.capsule_id,
            capsule_digest=result.recorded_input_signature.capsule_canonical_digest,
            strategy_version=result.recorded_input_signature.authored_strategy_version,
            config_version=result.recorded_input_signature.config_version,
            detail="proposal emitted; binding creates no authority (RFC-003 §7:215)",
        )
    )
    return PipelineResult(
        instrument_key=key,
        proposal=outcome,
        outcome=outcome,
        signature=result.recorded_input_signature,
        bound_state=bound_state,
        work_steps=work_steps,
    )


def _withheld(
    sink: EvidenceSink,
    key: InstrumentKey,
    halt_reason: HaltReason,
    detail: str | None,
    *,
    outcome: Outcome | None = None,
    signature: RecordedInputSignature | None = None,
    bound_state: BoundState | None = None,
    work_steps: int | None = None,
) -> PipelineResult:
    """Record a withheld decision and return the restrictive :class:`PipelineResult`.

    A withheld decision is a *recorded* restrictive no-action: the pipeline neither evaluates nor
    proposes, and it never constructs a No-Action artifact bound to a Capsule it just rejected
    (RFC-003 §7:203-204; design #31 §3.1).
    """
    sink.record(
        EngineEvidenceRecord(
            kind=EvidenceKind.DECISION_WITHHELD,
            instrument_key=key,
            halt_reason=halt_reason,
            outcome_type=None if outcome is None else type(outcome).__name__,
            outcome_digest=None if outcome is None else outcome.canonical_digest,
            detail=detail,
        )
    )
    return PipelineResult(
        instrument_key=key,
        halt_reason=halt_reason,
        outcome=outcome,
        signature=signature,
        bound_state=bound_state,
        work_steps=work_steps,
        detail=detail,
    )
