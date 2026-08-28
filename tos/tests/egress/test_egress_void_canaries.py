"""∅-void both-ways canaries across the egress predicates (design #22 §4.7).

Every empty-input guard is checked in BOTH directions: the forbidden (vacuous-permissive) direction
fires, and the legitimate positive direction is NOT blocked. A vacuous-satisfied quorum is a safety
violation; a vacuous-rejected genuine quorum is an availability violation — both are defects (#12
both-ways lesson). Both the ∅-signer-set (reject) and the ∅-active-principal-set (a legitimate
fully-fenced deny-all safety state) and the ∅-restrictive-event (availability) directions are
asserted.

Regime tag: structural / coordinate predicate substrate only; EGRESS-EV substrate;
EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.egress import (
    RestrictiveLatchState,
    credential_route_authority_disjoint,
    monotonic_denial_no_revival,
    quorum_commit_certificate_structurally_complete,
    quorum_threshold_structurally_met,
    stale_principal_structurally_rejected,
)

from ._egress_strategies import (
    clean_active_set,
    clean_inventory_entry,
    clean_qcc,
    clean_signers,
)


def test_empty_signer_set_blocks_but_two_signers_pass() -> None:
    """(∅ both-ways) ∅ signers ⇒ 0 < N ⇒ reject; two distinct eligible-signed ⇒ pass."""
    assert quorum_threshold_structurally_met((), 2) is False
    assert quorum_threshold_structurally_met(clean_signers(), 2) is True


def test_empty_signer_set_makes_qcc_incomplete_but_populated_is_complete() -> None:
    """(∅ both-ways) A QCC with ∅ signers is incomplete; one with two signers is complete."""
    assert (
        quorum_commit_certificate_structurally_complete(
            clean_qcc(signer_coordinates=())
        )
        is False
    )
    assert quorum_commit_certificate_structurally_complete(clean_qcc()) is True


def test_empty_active_principal_set_is_a_lawful_deny_all_safe_state() -> None:
    """(∅ both-ways / §4.7) An ∅ active-principal set is a lawful fully-fenced deny-all safe state.

    An ∅ set is constructible (a legitimate fully-fenced hard-fence-complete state — NOT a defect),
    and every principal check against it correctly denies (no false membership); a populated set
    admits its live principal.
    """
    empty_set = clean_active_set(egress_generation=9, principals=())
    assert empty_set.active_principals == ()
    # deny-all: no principal is admitted from an empty committed set.
    assert (
        stale_principal_structurally_rejected(
            "principal-1", empty_set, expected_generation=9
        )
        is False
    )
    # …but a populated set still admits its live principal (availability side).
    assert (
        stale_principal_structurally_rejected(
            "principal-1", clean_active_set(egress_generation=9), expected_generation=9
        )
        is True
    )


def test_empty_restrictive_event_stream_does_not_spuriously_deny() -> None:
    """(∅ both-ways / §4.7 availability) ∅ events invalidate nothing — a CLEAR latch stays CLEAR."""
    assert (
        monotonic_denial_no_revival(RestrictiveLatchState.CLEAR, [])
        is RestrictiveLatchState.CLEAR
    )
    # …but a latched deny is never revived by an empty stream either (safety side).
    assert (
        monotonic_denial_no_revival(RestrictiveLatchState.DENY_LATCHED, [])
        is RestrictiveLatchState.DENY_LATCHED
    )


def test_empty_inventory_denies_but_disjoint_inventory_passes() -> None:
    """(∅ both-ways) ∅ inventory ⇒ disjointness unproven ⇒ deny; a genuinely disjoint one passes."""
    assert credential_route_authority_disjoint([]) is False
    disjoint = [
        clean_inventory_entry(
            principal="inside-1",
            usable_credential=True,
            broker_route=True,
            inside_boundary=True,
        )
    ]
    assert credential_route_authority_disjoint(disjoint) is True
