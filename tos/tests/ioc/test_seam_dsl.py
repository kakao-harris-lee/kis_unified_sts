"""MANDATED test-only seam cross-check: ioc <-> dsl (design #14 §3.4/§0.4d; IOC-INV-001)."""

from __future__ import annotations

from tos.canonical import IndependentIdArtifact
from tos.ioc import ApprovedIntentContract

from ..dsl._dsl_strategies import real_proposal
from ._ioc_strategies import issue_intent


def test_intent_binds_exact_proposal_scalar() -> None:
    """(IOC-INV-001) The contract binds the proposal's exact (id, digest) scalar — the polarity holds."""
    proposal = real_proposal()
    assert proposal.proposal_id is not None
    assert proposal.canonical_digest is not None
    contract = issue_intent(
        proposal_id=proposal.proposal_id, proposal_digest=proposal.canonical_digest
    )
    assert contract.proposal_id == proposal.proposal_id
    assert contract.proposal_digest == proposal.canonical_digest


def test_proposal_is_content_addressed_id_equals_f_digest() -> None:
    """(§0.4d) The dsl Proposal is IdDerived (id = f(digest)); ioc references it, never redefines it."""
    proposal = real_proposal()
    assert proposal.proposal_id is not None
    assert proposal.canonical_digest is not None
    assert proposal.canonical_digest in proposal.proposal_id


def test_tampered_proposal_digest_does_not_bind() -> None:
    """(IOC-INV-001 polarity) A contract binding a tampered digest does NOT reference the proposal."""
    proposal = real_proposal()
    contract = issue_intent(
        proposal_id=proposal.proposal_id, proposal_digest="tampered-digest"
    )
    assert contract.proposal_digest != proposal.canonical_digest


def test_ioc_contract_id_is_independent_not_derived() -> None:
    """(§0.4d) The ioc ApprovedIntentContract keeps id ⊥ digest (IndependentIdArtifact), unlike Proposal."""
    contract = issue_intent()
    assert contract.intent_id is not None
    assert contract.canonical_digest is not None
    assert contract.canonical_digest not in contract.intent_id
    assert issubclass(ApprovedIntentContract, IndependentIdArtifact)
