"""Sibling verdict → positive-admit :class:`StageVerdict` adapters (design #31 §4.1 / §5.2).

These are the **contract-typing edges** of the design's §0.3 allowlist: the sequencer references
the sibling packages for their verdict *types*, while the stage *logic* stays injected. Each
adapter here is a pure wrapper that applies the sibling's own mandated consume gate:

| sibling | native verdict | mandated positive gate |
| --- | --- | --- |
| ``tos.venue`` | ``OrderAdmissibilityResult`` | ``result is ADMISSIBLE`` |
| ``tos.ioc`` | ``ConformanceResult`` | ``result is CONFORMANT`` |
| ``tos.are`` | ``RiskDecisionResult`` | ``result is GRANT`` |
| ``tos.afg`` | ``ActionFlowResult`` | ``result is GRANT`` |
| ``tos.cur`` | ``ProofResult`` | ``result is CURRENT`` |

Three disciplines are enforced here rather than left to each stage author:

* **Positive identity only.** Every gate is ``result is <PASS member>``. A negated gate
  (``result is not DENY``) is forbidden — it fails open on ``None`` and on any future member
  (design #31 §4.2 rule 1 / §6). ``None`` is always ``StageOutcome.UNKNOWN``, never a pass.
* **``RESTRICTED_PROTECTIVE_ONLY`` is not a pass.** venue's four-valued result carries a
  protective-only member that a truthiness read would treat as permission. It denies here with a
  distinct reason: a protective path proceeds only through venue's own
  ``protective_label_no_bypass``, and the Coordinator SHALL NOT self-classify anything as
  protective (RFC-005 §12:371; the #21/#18 folding precedent).
* **Structural binding extraction.** The digest and identity a verdict carries are read off the
  artifact (``canonical_digest``, ``proof_id``, ``permit_id``, …), never taken from a caller's
  claim (구조 파생 > 자기신고).

None of these adapters grants anything: the wrapped verdict is one current input, and every
returned record carries the all-false Coordinator authority block.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #31 §0.3).
"""

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
    """Wrap a venue Order Admissibility result (ADR-002-019 §5.4; design #31 §5.2).

    ``ADMISSIBLE`` alone admits. ``RESTRICTED_PROTECTIVE_ONLY`` **denies** with its own reason:
    it permits no ordinary new risk, and only venue's ``protective_label_no_bypass`` may route a
    separately-authorized protective action (ADR-002-019 §1:29 / §19:426; RFC-005 §12:371).

    Args:
        result: The venue result (``None`` => ``UNKNOWN``, never a pass).
        decision: The issued Order Admissibility Decision, when one exists (its digest/identity is
            recorded structurally).
        step: The commitment step this verdict answers.
        authority_class: Where the stage logic came from.

    Returns:
        The positive-admit :class:`StageVerdict`.
    """
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
    """Wrap an ioc Order Conformance result (ADR-002-020 §14:372; design #31 §5.2).

    ``CONFORMANT`` alone admits; ``NON_CONFORMANT`` and ``UNKNOWN`` are both denial (§14:374), and
    ``CONFORMANT`` itself "grants no approval or authority … usable only as one current input"
    (§14:376). ``ConformanceResult`` is truthy-untestable by construction, so the identity gate is
    the only way to read it.

    Args:
        result: The conformance result (``None`` => ``UNKNOWN``).
        proof: The issued Order Conformance Proof; its digest is what step 12 binds.
        step: The commitment step this verdict answers.
        authority_class: Where the stage logic came from.

    Returns:
        The positive-admit :class:`StageVerdict`.
    """
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
    """Wrap an are Aggregate Risk Decision result (ADR-002-021 §5.5:132; design #31 §5.2).

    ``GRANT`` alone admits and "authorizes only an exact RCL allocation request; it creates no
    capacity and permits no send". ``UNKNOWN`` "consumes conservative capacity and blocks new
    risk" (ARE-INV-006:173) — restrictive, never a soft pass. The Aggregate Risk **Authority
    runtime** is a future owning runtime, so the default authority class here is
    ``NON_AUTHORITATIVE_PROVISIONAL`` (design #31 §4.4).

    Args:
        result: The aggregate-risk result (``None`` => ``UNKNOWN``).
        decision: The issued Aggregate Risk Decision, when one exists.
        step: The commitment step this verdict answers.
        authority_class: Where the stage logic came from.

    Returns:
        The positive-admit :class:`StageVerdict`.
    """
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
    """Wrap an afg Action Flow Decision result (ADR-002-022 §5.4:125; design #31 §5.2).

    ``GRANT`` alone admits and "is not capacity or permission to send"; ``UNKNOWN`` consumes
    conservative capacity and blocks new normal risk (AFG-INV-007:181). The Action Flow **Governor
    runtime** is a future owning runtime (design #31 §4.4).

    Args:
        result: The action-flow result (``None`` => ``UNKNOWN``).
        decision: The issued Action Flow Decision, when one exists.
        step: The commitment step this verdict answers.
        authority_class: Where the stage logic came from.

    Returns:
        The positive-admit :class:`StageVerdict`.
    """
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
    """Wrap the single-use Action Flow Permit that step 9 creates (ADR-002-002 §11.2 step 9).

    Presence alone is not permission: a permit "is not Live Authorization, a Transmission
    Capability, or broker permission" (ADR-002-022 §5.5:129) — it is a mandatory *precondition*.
    The permit identity recorded here is what the Coordinator's step-12 attempt request binds
    (ADR-002-002 §11.3:599). A missing permit is ``UNKNOWN``, never a pass; the engine issues,
    claims, and consumes nothing.

    Args:
        permit: The issued permit (``None`` => ``UNKNOWN``).
        step: The commitment step this verdict answers.
        authority_class: Where the stage logic came from.

    Returns:
        The positive-admit :class:`StageVerdict`.
    """
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
    """Wrap the ADR-002-020 step-5 conservative Economic Effect Envelope (design #31 §5.2).

    ``EconomicEffectEnvelope`` *is* the rcl :class:`~tos.rcl.CapacityVector` type (the single
    ``ioc -> rcl`` edge). The structural gate:

    * a missing envelope, or one with **no** declared component, is ``UNKNOWN`` — an ∅ envelope
      derives nothing, and an empty vector is not "no effect" (both-ways ∅ discipline);
    * a declared dimension whose magnitude is ``None`` is UNKNOWN and capacity-consuming
      (``tos.rcl.vector`` §5.3), so it is ``UNKNOWN`` here too — never a pass;
    * otherwise ``ADMIT``: the envelope is a complete, current input to the capacity stages.

    Args:
        envelope: The derived envelope (``None`` => ``UNKNOWN``).
        step: The commitment step this verdict answers.
        authority_class: Where the stage logic came from.

    Returns:
        The positive-admit :class:`StageVerdict`.
    """
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
    """Wrap the step-14 single-use Transmission Capability (ADR-002-002 §11.3 step 14 / §12).

    The Coordinator neither issues nor reuses a capability (RFC-005 §12:358): the ledger issues or
    authorizes issuance, and only a committed claim consumes its nonce. This adapter merely
    observes that one exists and records its identity; a missing capability is ``UNKNOWN``.

    Args:
        capability: The issued capability (``None`` => ``UNKNOWN``).
        step: The commitment step this verdict answers.
        authority_class: Where the stage logic came from.

    Returns:
        The positive-admit :class:`StageVerdict`.
    """
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
    """Wrap a cur Egress Currentness proof result — **the D-E4 hand-off typing** (design #31 §12-3).

    ⚠ The slice-1 sequencer never calls this: steps 15-19 are constitutionally D-E4 and D-E1
    guarantees nothing about final-egress currentness / QCC / single-use (design #31 §4.5 item-7 /
    §10.2-3). It is provided so the send-boundary owner consumes the *same* positive-identity
    gate the rest of the flow uses: only ``CURRENT`` satisfies the check, and ``CURRENT`` itself
    grants no authority (ADR-002-024 §12:316).

    Args:
        result: The currentness proof result (``None`` => ``UNKNOWN``).
        proof: The Egress Currentness Proof, when one exists.
        step: The commitment step this verdict answers.
        authority_class: Where the stage logic came from.

    Returns:
        The positive-admit :class:`StageVerdict`.
    """
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
