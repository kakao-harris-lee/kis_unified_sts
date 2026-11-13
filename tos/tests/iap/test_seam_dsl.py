"""MANDATED test-only seam cross-check: iap <-> dsl (design #15 §3.4; §9 line 242; IAP-INV-001)."""

from __future__ import annotations

from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.dsl import DecisionContextCapsuleRef, Proposer, build_proposal
from tos.iap import ProposalApprovalRequest

from ._iap_strategies import complete_request

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


def _real_proposal():
    """Build a real content-addressed dsl Proposal (proposal.py:68)."""
    return build_proposal(
        scheme=_SCHEME,
        proposer=Proposer(strategy_id="strat-1", strategy_version="v1"),
        account="ACCT-1",
        instrument="INSTR-1",
        direction="LONG",
        position_effect="OPEN",
        quantity_basis="SHARES:100",
        rationale="seam binding fixture",
        decision_context_capsule=DecisionContextCapsuleRef(
            capsule_id="cap-1", canonical_digest="cap-digest-1"
        ),
        dsl_version="1.0",
        config_version="1.0",
    )


def test_request_binds_exact_proposal_scalar() -> None:
    """(§9 line 242) The request binds the proposal's exact (id, digest) scalar — the polarity holds."""
    proposal = _real_proposal()
    assert proposal.proposal_id is not None
    assert proposal.canonical_digest is not None
    request = complete_request(
        proposal_id=proposal.proposal_id, proposal_digest=proposal.canonical_digest
    )
    assert request.proposal_id == proposal.proposal_id
    assert request.proposal_digest == proposal.canonical_digest


def test_proposal_is_content_addressed_id_equals_f_digest() -> None:
    """(§0.4d) The dsl Proposal is IdDerived (id = f(digest)); iap references it, never redefines it."""
    proposal = _real_proposal()
    assert proposal.proposal_id is not None
    assert proposal.canonical_digest is not None
    assert proposal.canonical_digest in proposal.proposal_id


def test_tampered_proposal_digest_does_not_bind() -> None:
    """(§9 line 242 polarity) A request binding a tampered digest does NOT reference the proposal."""
    proposal = _real_proposal()
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
