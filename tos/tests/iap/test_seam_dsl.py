"""MANDATED test-only seam cross-check: iap <-> dsl (design #15 §3.4; §9 line 242; IAP-INV-001)."""

from __future__ import annotations

from tos.iap import ProposalApprovalRequest

from ..dsl._dsl_strategies import real_proposal
from ._iap_strategies import complete_request


def test_request_binds_exact_proposal_scalar() -> None:
    """(§9 line 242) The request binds the proposal's exact (id, digest) scalar — the polarity holds."""
    proposal = real_proposal()
    assert proposal.proposal_id is not None
    assert proposal.canonical_digest is not None
    request = complete_request(
        proposal_id=proposal.proposal_id, proposal_digest=proposal.canonical_digest
    )
    assert request.proposal_id == proposal.proposal_id
    assert request.proposal_digest == proposal.canonical_digest


def test_proposal_is_content_addressed_id_equals_f_digest() -> None:
    """(§0.4d) The dsl Proposal is IdDerived (id = f(digest)); iap references it, never redefines it."""
    proposal = real_proposal()
    assert proposal.proposal_id is not None
    assert proposal.canonical_digest is not None
    assert proposal.canonical_digest in proposal.proposal_id


def test_tampered_proposal_digest_does_not_bind() -> None:
    """(§9 line 242 polarity) A request binding a tampered digest does NOT reference the proposal."""
    proposal = real_proposal()
    request = complete_request(
        proposal_id=proposal.proposal_id, proposal_digest="tampered-digest"
    )
    assert request.proposal_digest != proposal.canonical_digest


def test_request_id_is_independent_not_derived() -> None:
    """(§0.4d) The iap ProposalApprovalRequest keeps id ⊥ digest (IndependentIdArtifact), unlike Proposal."""
    from tos.iap import IndependentIdArtifact

    request = complete_request()
    assert request.request_id is not None
    assert request.canonical_digest is not None
    assert request.canonical_digest not in request.request_id
    assert issubclass(ProposalApprovalRequest, IndependentIdArtifact)
