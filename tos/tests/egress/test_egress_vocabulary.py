"""EGRESS vocabulary — closed enum membership + spec-term fidelity (design #22 §2.2).

Regime tag: structural / coordinate predicate substrate only; EGRESS vocabulary substrate;
EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.egress import (
    CommitProofValidity,
    EgressAdmission,
    RestrictiveLatchState,
    SignerRole,
)


def test_egress_admission_members() -> None:
    """(§2.2(1)) EgressAdmission is exactly {ADMIT, DENY}."""
    assert {m.value for m in EgressAdmission} == {"ADMIT", "DENY"}


def test_commit_proof_validity_members() -> None:
    """(§2.2(2)) CommitProofValidity is exactly {VALID, INVALID, UNKNOWN}."""
    assert {m.value for m in CommitProofValidity} == {"VALID", "INVALID", "UNKNOWN"}


def test_restrictive_latch_state_members() -> None:
    """(§2.2(3)) RestrictiveLatchState is exactly {CLEAR, DENY_LATCHED}."""
    assert {m.value for m in RestrictiveLatchState} == {"CLEAR", "DENY_LATCHED"}


def test_signer_role_is_closed_two_member_taxonomy() -> None:
    """(§2.2(4)) SignerRole is the closed {QUORUM_MEMBER, LEADER} leader-vs-quorum axis."""
    assert {m.value for m in SignerRole} == {"QUORUM_MEMBER", "LEADER"}


def test_signer_role_is_plain_and_truthy_usable() -> None:
    """(§2.2(4)) SignerRole is a plain StrEnum (membership token) — NOT truthy-sealed."""
    # A plain StrEnum member is truthy-usable (it is a membership token, never a gate result).
    assert bool(SignerRole.QUORUM_MEMBER) is True
    assert (SignerRole.LEADER is SignerRole.LEADER) is True
