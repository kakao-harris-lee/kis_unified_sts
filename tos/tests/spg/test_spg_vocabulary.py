"""spg vocabulary: verbatim counts + lifecycle non-revival (design #12 §2.2).

The StrEnums are authored verbatim from ADR-002-014 §12.1/§12.2/§5.9/§5.3/§11/§13. These
tests lock the member counts and — critically — that the transition tables contain **no**
terminal -> ``ACTIVE`` arrow (§12.1 line 334 / §12.2 line 348 non-revival).
"""

from __future__ import annotations

from tos.spg import (
    BREAK_GLASS_ALLOWED_ACTIONS,
    MODELED_BUNDLE_MEMBERS,
    ActivationVerdict,
    BreakGlassAction,
    BundleMemberKind,
    ChangeDirection,
    EnvelopeState,
    ProfileState,
    ValidationReason,
    envelope_transition_allowed,
    profile_transition_allowed,
)


def test_envelope_state_has_nine_verbatim_members() -> None:
    """(§2.2(1)) EnvelopeState is the 9 ADR §12.1 states."""
    assert len(EnvelopeState) == 9
    assert {s.value for s in EnvelopeState} == {
        "DRAFT",
        "VALIDATED",
        "APPROVED",
        "STAGED",
        "ACTIVE",
        "REJECTED",
        "RESTRICTED",
        "SUPERSEDED",
        "REVOKED",
    }


def test_profile_state_has_eleven_verbatim_members() -> None:
    """(§2.2(2)) ProfileState is the 11 ADR §12.2 states."""
    assert len(ProfileState) == 11
    assert {s.value for s in ProfileState} == {
        "DRAFT",
        "VALIDATED",
        "APPROVED",
        "STAGED",
        "ACTIVATION_READY",
        "ACTIVE",
        "REJECTED",
        "SUSPENDED",
        "SUPERSEDED",
        "REVOKED",
        "EXPIRED",
    }


def test_change_direction_has_three_members_no_unorderable() -> None:
    """(§2.2(3) v1.1 MINOR-1) ChangeDirection is 3 tokens; UNORDERABLE is NOT an enum value."""
    assert len(ChangeDirection) == 3
    assert {d.value for d in ChangeDirection} == {
        "RESTRICTIVE",
        "PERMISSIVE",
        "AUTHORITY_INCREASING",
    }
    assert "UNORDERABLE" not in {d.value for d in ChangeDirection}
    # The unorderable fact rides in the reason set instead.
    assert ValidationReason.UNORDERABLE_DIRECTION in set(ValidationReason)


def test_bundle_member_kind_has_29_modeled_members() -> None:
    """(§2.2(4) MAJOR-3) 29 top-level members are modeled; 7 sub-generation refs are deferred."""
    assert len(BundleMemberKind) == 29
    assert frozenset(BundleMemberKind) == MODELED_BUNDLE_MEMBERS
    # The two symmetric sub-generations are BOTH deferred (never modeled as enum values).
    values = {m.value for m in BundleMemberKind}
    assert "RELEASE_GENERATION" not in values
    assert "POST_TRADE_OBLIGATION_GENERATION" not in values


def test_validation_reason_has_ten_members() -> None:
    """(§2.2(5)) The §11/§20 reject reason class has 10 members."""
    assert len(ValidationReason) == 10


def test_activation_verdict_has_three_members() -> None:
    """(§2.2(6)) ActivationVerdict is COMMITTABLE / DENIED / DEFERRED."""
    assert {v.value for v in ActivationVerdict} == {
        "COMMITTABLE",
        "DENIED",
        "DEFERRED",
    }


def test_break_glass_allowed_is_halt_and_restrictive_only() -> None:
    """(§6.2) Break-glass is confined to HALT / RESTRICTIVE_OVERRIDE (§8 line 251)."""
    assert (
        frozenset({BreakGlassAction.HALT, BreakGlassAction.RESTRICTIVE_OVERRIDE})
        == BREAK_GLASS_ALLOWED_ACTIONS
    )


# ---------------------------------------------------------------------------
# Transition tables — non-revival
# ---------------------------------------------------------------------------


def test_envelope_forward_lifecycle_allowed() -> None:
    """The DRAFT -> VALIDATED -> APPROVED -> STAGED -> ACTIVE forward path is allowed."""
    assert envelope_transition_allowed(EnvelopeState.DRAFT, EnvelopeState.VALIDATED)
    assert envelope_transition_allowed(EnvelopeState.STAGED, EnvelopeState.ACTIVE)
    assert envelope_transition_allowed(EnvelopeState.ACTIVE, EnvelopeState.RESTRICTED)


def test_envelope_terminals_never_return_to_active() -> None:
    """(§12.1 line 334) No terminal envelope state returns to ACTIVE (non-revival)."""
    for terminal in (
        EnvelopeState.RESTRICTED,
        EnvelopeState.SUPERSEDED,
        EnvelopeState.REVOKED,
        EnvelopeState.REJECTED,
    ):
        assert not envelope_transition_allowed(terminal, EnvelopeState.ACTIVE)


def test_profile_forward_lifecycle_allowed() -> None:
    """The profile forward path (through ACTIVATION_READY) is allowed."""
    assert profile_transition_allowed(
        ProfileState.STAGED, ProfileState.ACTIVATION_READY
    )
    assert profile_transition_allowed(
        ProfileState.ACTIVATION_READY, ProfileState.ACTIVE
    )
    assert profile_transition_allowed(ProfileState.ACTIVE, ProfileState.EXPIRED)


def test_profile_terminals_never_return_to_active() -> None:
    """(§12.2 line 348) No terminal profile state returns to ACTIVE (non-revival)."""
    for terminal in (
        ProfileState.SUSPENDED,
        ProfileState.SUPERSEDED,
        ProfileState.REVOKED,
        ProfileState.EXPIRED,
        ProfileState.REJECTED,
    ):
        assert not profile_transition_allowed(terminal, ProfileState.ACTIVE)


def test_no_transition_table_has_any_terminal_to_active_arrow() -> None:
    """(non-revival regression) Neither table contains ANY (terminal, ACTIVE) arrow."""
    from tos.spg.predicates import _ENVELOPE_TRANSITIONS, _PROFILE_TRANSITIONS

    env_terminals = {
        EnvelopeState.RESTRICTED,
        EnvelopeState.SUPERSEDED,
        EnvelopeState.REVOKED,
        EnvelopeState.REJECTED,
    }
    assert not any(
        frm in env_terminals and to is EnvelopeState.ACTIVE
        for (frm, to) in _ENVELOPE_TRANSITIONS
    )
    prof_terminals = {
        ProfileState.SUSPENDED,
        ProfileState.SUPERSEDED,
        ProfileState.REVOKED,
        ProfileState.EXPIRED,
        ProfileState.REJECTED,
    }
    assert not any(
        frm in prof_terminals and to is ProfileState.ACTIVE
        for (frm, to) in _PROFILE_TRANSITIONS
    )


def test_unlisted_transition_is_forbidden() -> None:
    """A wild jump (DRAFT -> ACTIVE, skipping the lifecycle) is not allowed."""
    assert not envelope_transition_allowed(EnvelopeState.DRAFT, EnvelopeState.ACTIVE)
    assert not profile_transition_allowed(ProfileState.DRAFT, ProfileState.ACTIVE)
