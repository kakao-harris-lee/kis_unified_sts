"""MANDATED test-only seam cross-check: venue <-> ioc (design #19 §3.4(d) / §7)."""

from __future__ import annotations

from tos.ioc import CanonicalBrokerCommand, OrderConformanceProof
from tos.venue import venue_admissibility_decision_digest_of

from ._venue_strategies import clean_decision


def test_ioc_proof_carries_the_venue_admissibility_decision_digest_slot() -> None:
    """(seam) The ioc OrderConformanceProof slot exists and accepts a str | None digest."""
    assert "venue_admissibility_decision_digest" in OrderConformanceProof.model_fields
    proof = OrderConformanceProof(venue_admissibility_decision_digest=None)
    assert proof.venue_admissibility_decision_digest is None


def test_venue_decision_digest_fills_the_ioc_slot() -> None:
    """(seam positive) A venue-produced decision digest is exactly what the ioc slot carries."""
    decision = clean_decision()
    produced = venue_admissibility_decision_digest_of(decision)
    assert isinstance(produced, str)
    proof = OrderConformanceProof(venue_admissibility_decision_digest=produced)
    assert proof.venue_admissibility_decision_digest == decision.canonical_digest


def test_venue_consumes_ioc_candidate_command_digest_scalar() -> None:
    """(seam, reverse direction) venue binds the ioc candidate command id/digest as scalars."""
    assert "command_id" in CanonicalBrokerCommand.model_fields
    assert "canonical_digest" in CanonicalBrokerCommand.model_fields
    decision = clean_decision()
    assert decision.candidate_command_id == "ioc-cmd-1"
    assert decision.candidate_command_digest == "ioc-cmd-digest"


def test_none_decision_produces_no_digest() -> None:
    """(seam, fail-closed) A None decision produces no digest into the ioc slot."""
    assert venue_admissibility_decision_digest_of(None) is None
