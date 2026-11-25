"""Sibling verdict → positive-admit :class:`StageVerdict` adapters (design #31 §4.1 / §5.2)."""

from __future__ import annotations

from tos.afg import ActionFlowDecision, ActionFlowPermit, ActionFlowResult
from tos.are import AggregateRiskDecision, RiskDecisionResult
from tos.cur import EgressCurrentnessProof, ProofResult
from tos.engine.records import StageVerdict
from tos.engine.vocabulary import CommitmentStep, StageAuthorityClass, StageOutcome
from tos.ioc import ConformanceResult, EconomicEffectEnvelope, OrderConformanceProof
from tos.rcl import TransmissionCapability
from tos.venue import OrderAdmissibilityDecision, OrderAdmissibilityResult

__all__ = [
    "action_flow_decision_verdict",
    "action_flow_permit_verdict",
    "aggregate_risk_decision_verdict",
    "conformance_proof_verdict",
    "economic_effect_envelope_verdict",
    "egress_currentness_verdict",
    "transmission_capability_verdict",
    "venue_admissibility_verdict",
]


def _verdict(
    *,
    step: CommitmentStep,
    outcome: StageOutcome,
    authority_class: StageAuthorityClass,
    native: object | None = None,
    native_value: str | None = None,
    bound_digest: str | None = None,
    bound_identity: str | None = None,
    reason: str | None = None,
) -> StageVerdict:
    """Assemble a :class:`StageVerdict`, deriving the native type name structurally."""
    return StageVerdict(
        step=step,
        outcome=outcome,
        authority_class=authority_class,
        native_verdict_type=None if native is None else type(native).__name__,
        native_verdict_value=native_value,
        bound_digest=bound_digest,
        bound_identity=bound_identity,
        reason=reason,
    )


def venue_admissibility_verdict(
    result: OrderAdmissibilityResult | None,
    decision: OrderAdmissibilityDecision | None = None,
    *,
    step: CommitmentStep = CommitmentStep.VENUE_ADMISSIBILITY_DECISION,
    authority_class: StageAuthorityClass = StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
) -> StageVerdict:
    """Wrap a venue Order Admissibility result (ADR-002-019 §5.4; design #31 §5.2)."""
    digest = None if decision is None else decision.canonical_digest
    identity = None if decision is None else decision.decision_id
    if result is None:
        return _verdict(
            step=step,
            outcome=StageOutcome.UNKNOWN,
            authority_class=authority_class,
            native=decision,
            bound_digest=digest,
            bound_identity=identity,
            reason="no venue admissibility result was produced",
        )
    if result is OrderAdmissibilityResult.ADMISSIBLE:
        outcome = StageOutcome.ADMIT
        reason = None
    elif result is OrderAdmissibilityResult.UNKNOWN:
        outcome = StageOutcome.UNKNOWN
        reason = "venue admissibility is UNKNOWN — restrictive (ADR-002-019 §8:245)"
    elif result is OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY:
        outcome = StageOutcome.DENY
        reason = (
            "venue admissibility is RESTRICTED_PROTECTIVE_ONLY — no ordinary new risk; a "
            "protective action proceeds only through venue protective_label_no_bypass, and the "
            "Coordinator self-classifies nothing as protective (RFC-005 §12:371)"
        )
    else:
        outcome = StageOutcome.DENY
        reason = "venue admissibility is INADMISSIBLE"
    return _verdict(
        step=step,
        outcome=outcome,
        authority_class=authority_class,
        native=result,
        native_value=str(result.value),
        bound_digest=digest,
        bound_identity=identity,
        reason=reason,
    )


def conformance_proof_verdict(
    result: ConformanceResult | None,
    proof: OrderConformanceProof | None = None,
    *,
    step: CommitmentStep = CommitmentStep.ORDER_CONFORMANCE_PROOF,
    authority_class: StageAuthorityClass = StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
) -> StageVerdict:
    """Wrap an ioc Order Conformance result (ADR-002-020 §14:372; design #31 §5.2)."""
    digest = None if proof is None else proof.canonical_digest
    identity = None if proof is None else proof.proof_id
    if result is None:
        return _verdict(
            step=step,
            outcome=StageOutcome.UNKNOWN,
            authority_class=authority_class,
            native=proof,
            bound_digest=digest,
            bound_identity=identity,
            reason="no conformance result was produced",
        )
    if result is ConformanceResult.CONFORMANT:
        outcome = StageOutcome.ADMIT
        reason = None
    elif result is ConformanceResult.UNKNOWN:
        outcome = StageOutcome.UNKNOWN
        reason = "order conformance is UNKNOWN — denial (ADR-002-020 §14:374)"
    else:
        outcome = StageOutcome.DENY
        reason = "order conformance is NON_CONFORMANT"
    return _verdict(
        step=step,
        outcome=outcome,
        authority_class=authority_class,
        native=result,
        native_value=str(result.value),
        bound_digest=digest,
        bound_identity=identity,
        reason=reason,
    )


def aggregate_risk_decision_verdict(
    result: RiskDecisionResult | None,
    decision: AggregateRiskDecision | None = None,
    *,
    step: CommitmentStep = CommitmentStep.AGGREGATE_RISK_DECISION,
    authority_class: StageAuthorityClass = StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL,
) -> StageVerdict:
    """Wrap an are Aggregate Risk Decision result (ADR-002-021 §5.5:132; design #31 §5.2)."""
    digest = None if decision is None else decision.canonical_digest
    identity = None if decision is None else decision.decision_id
    if result is None:
        return _verdict(
            step=step,
            outcome=StageOutcome.UNKNOWN,
            authority_class=authority_class,
            native=decision,
            bound_digest=digest,
            bound_identity=identity,
            reason="no aggregate-risk result was produced",
        )
    if result is RiskDecisionResult.GRANT:
        outcome = StageOutcome.ADMIT
        reason = None
    elif result is RiskDecisionResult.UNKNOWN:
        outcome = StageOutcome.UNKNOWN
        reason = "aggregate risk is UNKNOWN — blocks new risk (ARE-INV-006:173)"
    else:
        outcome = StageOutcome.DENY
        reason = "aggregate risk decision is DENY"
    return _verdict(
        step=step,
        outcome=outcome,
        authority_class=authority_class,
        native=result,
        native_value=str(result.value),
        bound_digest=digest,
        bound_identity=identity,
        reason=reason,
    )


def action_flow_decision_verdict(
    result: ActionFlowResult | None,
    decision: ActionFlowDecision | None = None,
    *,
    step: CommitmentStep = CommitmentStep.ACTION_FLOW_DECISION,
    authority_class: StageAuthorityClass = StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL,
) -> StageVerdict:
    """Wrap an afg Action Flow Decision result (ADR-002-022 §5.4:125; design #31 §5.2)."""
    digest = None if decision is None else decision.canonical_digest
    identity = None if decision is None else decision.decision_id
    if result is None:
        return _verdict(
            step=step,
            outcome=StageOutcome.UNKNOWN,
            authority_class=authority_class,
            native=decision,
            bound_digest=digest,
            bound_identity=identity,
            reason="no action-flow result was produced",
        )
    if result is ActionFlowResult.GRANT:
        outcome = StageOutcome.ADMIT
        reason = None
    elif result is ActionFlowResult.UNKNOWN:
        outcome = StageOutcome.UNKNOWN
        reason = "action flow is UNKNOWN — blocks new normal risk (AFG-INV-007:181)"
    else:
        outcome = StageOutcome.DENY
        reason = "action flow decision is DENY"
    return _verdict(
        step=step,
        outcome=outcome,
        authority_class=authority_class,
        native=result,
        native_value=str(result.value),
        bound_digest=digest,
        bound_identity=identity,
        reason=reason,
    )


def action_flow_permit_verdict(
    permit: ActionFlowPermit | None,
    *,
    step: CommitmentStep = CommitmentStep.ATOMIC_COMMIT,
    authority_class: StageAuthorityClass = StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL,
) -> StageVerdict:
    """Wrap the single-use Action Flow Permit that step 9 creates (ADR-002-002 §11.2 step 9)."""
    if permit is None or permit.permit_id is None:
        return _verdict(
            step=step,
            outcome=StageOutcome.UNKNOWN,
            authority_class=authority_class,
            native=permit,
            reason="no Action Flow Permit identity was committed",
        )
    return _verdict(
        step=step,
        outcome=StageOutcome.ADMIT,
        authority_class=authority_class,
        native=permit,
        bound_digest=permit.canonical_digest,
        bound_identity=permit.permit_id,
    )


def economic_effect_envelope_verdict(
    envelope: EconomicEffectEnvelope | None,
    *,
    step: CommitmentStep = CommitmentStep.ECONOMIC_EFFECT_ENVELOPE,
    authority_class: StageAuthorityClass = StageAuthorityClass.AVAILABLE_PURE_PREDICATE,
) -> StageVerdict:
    """Wrap the ADR-002-020 step-5 conservative Economic Effect Envelope (design #31 §5.2)."""
    if envelope is None:
        return _verdict(
            step=step,
            outcome=StageOutcome.UNKNOWN,
            authority_class=authority_class,
            reason="no Economic Effect Envelope was derived",
        )
    if not envelope.components:
        return _verdict(
            step=step,
            outcome=StageOutcome.UNKNOWN,
            authority_class=authority_class,
            native=envelope,
            reason="the Economic Effect Envelope declares no dimension — nothing was derived",
        )
    unknown_dimensions = tuple(
        component.dimension_id
        for component in envelope.components
        if component.magnitude is None
    )
    if unknown_dimensions:
        return _verdict(
            step=step,
            outcome=StageOutcome.UNKNOWN,
            authority_class=authority_class,
            native=envelope,
            reason=(
                f"Economic Effect Envelope dimensions {unknown_dimensions} are UNKNOWN — "
                "capacity-consuming, never a permissive default (ADR-002-002 §5.3)"
            ),
        )
    return _verdict(
        step=step,
        outcome=StageOutcome.ADMIT,
        authority_class=authority_class,
        native=envelope,
    )


def transmission_capability_verdict(
    capability: TransmissionCapability | None,
    *,
    step: CommitmentStep = CommitmentStep.TRANSMISSION_CAPABILITY,
    authority_class: StageAuthorityClass = StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL,
) -> StageVerdict:
    """Wrap the step-14 single-use Transmission Capability (ADR-002-002 §11.3 step 14 / §12)."""
    if capability is None or capability.capability_id is None:
        return _verdict(
            step=step,
            outcome=StageOutcome.UNKNOWN,
            authority_class=authority_class,
            native=capability,
            reason="no single-use Transmission Capability identity was issued",
        )
    return _verdict(
        step=step,
        outcome=StageOutcome.ADMIT,
        authority_class=authority_class,
        native=capability,
        bound_digest=capability.canonical_digest,
        bound_identity=capability.capability_id,
    )


def egress_currentness_verdict(
    result: ProofResult | None,
    proof: EgressCurrentnessProof | None = None,
    *,
    step: CommitmentStep = CommitmentStep.SEND_BOUNDARY_VERIFICATION,
    authority_class: StageAuthorityClass = StageAuthorityClass.DEFERRED_SEND_BOUNDARY,
) -> StageVerdict:
    """Wrap a cur Egress Currentness proof result — **the D-E4 hand-off typing** (design #31 §12-3)."""
    digest = None if proof is None else proof.canonical_digest
    identity = None if proof is None else proof.proof_id
    if result is None:
        return _verdict(
            step=step,
            outcome=StageOutcome.UNKNOWN,
            authority_class=authority_class,
            native=proof,
            bound_digest=digest,
            bound_identity=identity,
            reason="no egress currentness result was produced",
        )
    if result is ProofResult.CURRENT:
        outcome = StageOutcome.ADMIT
        reason = None
    elif result is ProofResult.UNKNOWN:
        outcome = StageOutcome.UNKNOWN
        reason = "egress currentness is UNKNOWN — blocks new risk (CUR-INV-011:183)"
    else:
        outcome = StageOutcome.DENY
        reason = "egress currentness is RESTRICTED"
    return _verdict(
        step=step,
        outcome=outcome,
        authority_class=authority_class,
        native=result,
        native_value=str(result.value),
        bound_digest=digest,
        bound_identity=identity,
        reason=reason,
    )
