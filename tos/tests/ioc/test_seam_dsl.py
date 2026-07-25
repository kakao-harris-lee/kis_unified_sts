"""MANDATED test-only seam cross-check: ioc <-> dsl (design #14 §3.4/§0.4d; IOC-INV-001).

ioc binds the dsl ``Proposal`` (the immutable Intent proposal identity) by ``proposal_id`` +
``proposal_digest`` **scalar** (IOC-INV-001) — it does NOT import ``tos.dsl`` at runtime, nor
redefine the content-addressed ``Proposal``. This file imports the real dsl ``Proposal`` builder
(``proposal.py:68``) as a **test** to lock the digest-binding polarity: an
``ApprovedIntentContract`` that binds the exact ``(proposal_id, canonical_digest)`` of a proposal
references that proposal, and a tampered digest does not.

A test-only cross-import is NOT a runtime package edge (design #14 §3.4/§7.1); dsl is one of the
twelve siblings ioc never imports at runtime (the §7.1 closure test asserts its absence).
"""

from __future__ import annotations

from tos.canonical import EV_L1_PROVISIONAL_VERSION, IndependentIdArtifact, get_scheme
from tos.dsl import DecisionContextCapsuleRef, Proposer, build_proposal
from tos.ioc import ApprovedIntentContract

from ._ioc_strategies import issue_intent

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


def test_intent_binds_exact_proposal_scalar() -> None:
    """(IOC-INV-001) The contract binds the proposal's exact (id, digest) scalar — the polarity holds."""
    proposal = _real_proposal()
    assert proposal.proposal_id is not None
    assert proposal.canonical_digest is not None
    contract = issue_intent(
        proposal_id=proposal.proposal_id, proposal_digest=proposal.canonical_digest
    )
    assert contract.proposal_id == proposal.proposal_id
    assert contract.proposal_digest == proposal.canonical_digest


def test_proposal_is_content_addressed_id_equals_f_digest() -> None:
    """(§0.4d) The dsl Proposal is IdDerived (id = f(digest)); ioc references it, never redefines it."""
    proposal = _real_proposal()
    # content-addressed: the id is derived from the digest (a distinct polarity from the ioc
    # IndependentIdArtifact contract, which keeps id ⊥ digest for forgery detection).
    assert proposal.proposal_id is not None
    assert proposal.canonical_digest is not None
    assert proposal.canonical_digest in proposal.proposal_id


def test_tampered_proposal_digest_does_not_bind() -> None:
    """(IOC-INV-001 polarity) A contract binding a tampered digest does NOT reference the proposal."""
    proposal = _real_proposal()
    contract = issue_intent(
        proposal_id=proposal.proposal_id, proposal_digest="tampered-digest"
    )
    assert contract.proposal_digest != proposal.canonical_digest


def test_ioc_contract_id_is_independent_not_derived() -> None:
    """(§0.4d) The ioc ApprovedIntentContract keeps id ⊥ digest (IndependentIdArtifact), unlike Proposal."""
    contract = issue_intent()
    assert contract.intent_id is not None
    assert contract.canonical_digest is not None
    # id is NOT f(digest) — the digest is not a substring of the injected governance id.
    assert contract.canonical_digest not in contract.intent_id
    assert issubclass(ApprovedIntentContract, IndependentIdArtifact)
