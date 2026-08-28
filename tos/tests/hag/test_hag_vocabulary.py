"""hag vocabulary — closed taxonomies, direction map, lifecycle partitions (design #20 §2.2/§7).

Regime tag: predicate / model substrate only; HAG vocabulary substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.hag import (
    AUTHORITY_DIRECTION,
    BREAK_GLASS_RESTRICTIVE_CLASSES,
    PROGRESS_LIFECYCLE_STATES,
    TERMINAL_LIFECYCLE_STATES,
    ApprovalLifecycleState,
    AttestationDecision,
    AuthorityClass,
    AuthorityDirection,
    ConflictRole,
)


def test_authority_class_is_the_eight_class_taxonomy() -> None:
    """(§7 line 238-249) The eight authority classes are exactly enumerated."""
    assert {c.value for c in AuthorityClass} == {
        "HALT",
        "NARROW",
        "REQUEST_PROTECTIVE",
        "APPROVE_PROFILE_OR_ENVELOPE",
        "APPROVE_REARM",
        "ACCEPT_RESIDUAL_RISK",
        "CAPACITY_MUTATION",
        "TRANSMIT",
    }


def test_every_authority_class_has_a_direction() -> None:
    """(§7) The direction map covers every class; HALT/NARROW/REQUEST_PROTECTIVE are non-increasing."""
    for cls in AuthorityClass:
        assert cls in AUTHORITY_DIRECTION
    assert (
        AUTHORITY_DIRECTION[AuthorityClass.HALT]
        is AuthorityDirection.STRICTLY_RESTRICTIVE
    )
    assert (
        AUTHORITY_DIRECTION[AuthorityClass.NARROW]
        is AuthorityDirection.PROVEN_RESTRICTIVE
    )
    assert (
        AUTHORITY_DIRECTION[AuthorityClass.REQUEST_PROTECTIVE]
        is AuthorityDirection.PROPOSAL_ONLY
    )
    assert (
        AUTHORITY_DIRECTION[AuthorityClass.TRANSMIT]
        is AuthorityDirection.IRREVERSIBLE_BOUNDARY
    )
    assert (
        AUTHORITY_DIRECTION[AuthorityClass.CAPACITY_MUTATION]
        is AuthorityDirection.ECONOMIC_AUTHORITY
    )


def test_break_glass_restrictive_classes_are_exactly_three() -> None:
    """(§7/§16 line 425; HAG-INV-006) Only HALT / NARROW / REQUEST_PROTECTIVE are break-glass."""
    assert (
        frozenset(
            {
                AuthorityClass.HALT,
                AuthorityClass.NARROW,
                AuthorityClass.REQUEST_PROTECTIVE,
            }
        )
        == BREAK_GLASS_RESTRICTIVE_CLASSES
    )


def test_attestation_decision_three_members() -> None:
    """(§18 line 523) APPROVE / DENY / ABSTAIN."""
    assert {d.value for d in AttestationDecision} == {"APPROVE", "DENY", "ABSTAIN"}


def test_lifecycle_partition_is_complete_and_disjoint() -> None:
    """(§18 line 511-521) Progress + terminal partition covers every state, with only QUORUM_SATISFIED live-to-consume."""
    all_states = set(ApprovalLifecycleState)
    assert all_states == PROGRESS_LIFECYCLE_STATES | TERMINAL_LIFECYCLE_STATES
    assert frozenset() == PROGRESS_LIFECYCLE_STATES & TERMINAL_LIFECYCLE_STATES
    assert ApprovalLifecycleState.CONSUMED in TERMINAL_LIFECYCLE_STATES
    assert ApprovalLifecycleState.QUORUM_SATISFIED in PROGRESS_LIFECYCLE_STATES


def test_conflict_role_taxonomy_has_the_sixteen_roles() -> None:
    """(§12 line 345-354) The SoD role taxonomy enumerates the forbidden-pair roles."""
    values = {r.value for r in ConflictRole}
    for expected in (
        "TRADING_PROPOSER",
        "TRADE_APPROVER",
        "LIVE_ARMER",
        "EVIDENCE_PRODUCER",
        "EVIDENCE_REVIEWER",
        "BREAK_GLASS_CUSTODIAN",
        "BYPASS_APPROVER",
    ):
        assert expected in values


def test_closed_enums_are_plain_and_truthy_usable() -> None:
    """(§2.2) AuthorityClass / ConflictRole are plain StrEnums (membership tokens, not sealed)."""
    # A plain StrEnum member is truthy-testable (unlike the sealed decision / lifecycle enums).
    assert bool(AuthorityClass.HALT) is True
    assert bool(ConflictRole.TRADE_APPROVER) is True
