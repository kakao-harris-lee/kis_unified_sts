"""MANDATED test-only seam cross-check: ioc <-> are (design #14 §3.4; §14 line 369)."""

from __future__ import annotations

from tos.are import AggregateRiskDecision, RiskDecisionResult, decision_content_ref
from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.ioc import OrderConformanceProof

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


def _real_decision() -> AggregateRiskDecision:
    """Issue a real are AggregateRiskDecision (are/records.py:451, actual signature)."""
    return AggregateRiskDecision.issue(
        scheme=_SCHEME,
        decision_id="are-dec-1",
        decision_generation=2,
        result=RiskDecisionResult.GRANT,
    )


def test_proof_binds_are_decision_content_ref_scalars() -> None:
    """(§14 line 369) The proof binds the are decision's exact (id, generation, digest) scalars."""
    decision = _real_decision()
    decision_id, generation, digest = decision_content_ref(decision)
    proof = OrderConformanceProof.issue(
        scheme=_SCHEME,
        proof_id="proof-1",
        proof_generation=1,
        aggregate_risk_decision_id=decision_id,
        aggregate_risk_decision_generation=generation,
        aggregate_risk_decision_digest=digest,
    )
    assert proof.aggregate_risk_decision_id == decision.decision_id
    assert proof.aggregate_risk_decision_generation == decision.decision_generation
    assert proof.aggregate_risk_decision_digest == decision.canonical_digest


def test_decision_ref_is_scalar_not_a_decision_object() -> None:
    """(§3.4) The seam carries scalars — the proof holds no are object, only digest scalars."""
    decision = _real_decision()
    proof = OrderConformanceProof.issue(
        scheme=_SCHEME,
        proof_id="proof-2",
        proof_generation=1,
        aggregate_risk_decision_digest=decision.canonical_digest,
    )
    assert isinstance(proof.aggregate_risk_decision_digest, str)
    assert not isinstance(proof.aggregate_risk_decision_digest, AggregateRiskDecision)


def test_tampered_decision_digest_does_not_bind() -> None:
    """(§14 line 369 polarity) A proof binding a tampered are digest does NOT reference the decision."""
    decision = _real_decision()
    proof = OrderConformanceProof.issue(
        scheme=_SCHEME,
        proof_id="proof-3",
        proof_generation=1,
        aggregate_risk_decision_digest="tampered",
    )
    assert proof.aggregate_risk_decision_digest != decision.canonical_digest
