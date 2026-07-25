"""UNKNOWN confinement + economic continuity + predicate-only §6 rules (design #15 §5.5/§5.6/§6).

unknown_confines (§5.5): UNKNOWN blocks ordinary new risk and CANNOT be offset by capacity /
label / priority / human preference (IAP-INV-010/013). economic_effect_outlives (§5.6): expiry /
invalidation / missing-ACK / cancel-ACK never releases capacity or erases exposure (expiry ≠
release). predicate-only: independent_validation_declared (§6.1), no_widening_no_union +
approval_grants_no_authority (§6.3), active_egress_currentness (§6.4), stale_generation_fenced +
conflicting_evaluators_unknown (§6.5), recovery_revives_nothing (§6.6).

Regime tag: predicate / model substrate only; IAP-EV-002/006/008/009/010/011/012 NOT_IMPLEMENTED
(+Security / +Broker / runtime residue); EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.iap import (
    ApprovalAuthorityEffect,
    ApprovalResult,
    active_egress_currentness,
    approval_grants_no_authority,
    conflicting_evaluators_unknown,
    economic_effect_outlives,
    independent_validation_declared,
    no_widening_no_union,
    recovery_revives_nothing,
    stale_generation_fenced,
    unknown_confines,
)

from ._iap_strategies import TRIBOOL, ordering_event

# ---------------------------------------------------------------------------
# §5.5 unknown_confines — capacity / label / priority cannot offset uncertainty
# ---------------------------------------------------------------------------


@given(
    capacity_available=TRIBOOL,
    protective_or_priority_label=TRIBOOL,
    human_preference=TRIBOOL,
)
def test_unknown_state_blocks_regardless_of_offsets(
    capacity_available: bool | None,
    protective_or_priority_label: bool | None,
    human_preference: bool | None,
) -> None:
    """(§16 line 391/393, IAP-AC-009) UNKNOWN blocks new risk regardless of capacity / label / priority / human."""
    assert (
        unknown_confines(
            any_unknown_state=True,
            capacity_available=capacity_available,
            protective_or_priority_label=protective_or_priority_label,
            human_preference=human_preference,
        )
        is True
    )


def test_undetermined_state_fails_closed_to_blocked() -> None:
    """(fail-closed) An undetermined (None) uncertainty state blocks new risk (fail-closed)."""
    assert unknown_confines(any_unknown_state=None) is True


def test_no_uncertainty_does_not_block_by_uncertainty() -> None:
    """(positive side) Only a positively-False (no) uncertainty state is not blocked by uncertainty."""
    assert unknown_confines(any_unknown_state=False, capacity_available=True) is False


# ---------------------------------------------------------------------------
# §5.6 economic_effect_outlives — expiry ≠ release
# ---------------------------------------------------------------------------


def test_expiry_does_not_release_capacity() -> None:
    """(IAP-INV-011, IAP-AC-011) Without a positively-proven terminal release, the effect outlives (expiry ≠ release)."""
    assert economic_effect_outlives(terminal_release_proven=None) is True
    assert economic_effect_outlives(terminal_release_proven=False) is True


def test_positively_proven_release_outlives_is_false() -> None:
    """(positive side) Only a positively-proven terminal release lets the effect NOT outlive."""
    assert economic_effect_outlives(terminal_release_proven=True) is False


# ---------------------------------------------------------------------------
# §6.1 independent_validation_declared
# ---------------------------------------------------------------------------


def test_independent_validation_requires_all_positive() -> None:
    """(§10 line 274, IAP-AC-002) True only when not proposer-only, not shared-failure-path, and declared."""
    assert (
        independent_validation_declared(
            proposer_only_value=False,
            shared_failure_path=False,
            common_mode_declared=True,
        )
        is True
    )


@given(
    proposer_only_value=TRIBOOL,
    shared_failure_path=TRIBOOL,
    common_mode_declared=TRIBOOL,
)
def test_independent_validation_fails_closed(
    proposer_only_value: bool | None,
    shared_failure_path: bool | None,
    common_mode_declared: bool | None,
) -> None:
    """(§10) Any proposer-only / shared-failure-path / undeclared-common-mode fails closed to False."""
    result = independent_validation_declared(
        proposer_only_value=proposer_only_value,
        shared_failure_path=shared_failure_path,
        common_mode_declared=common_mode_declared,
    )
    expected = (
        proposer_only_value is False
        and shared_failure_path is False
        and common_mode_declared is True
    )
    assert result is expected


# ---------------------------------------------------------------------------
# §6.3 no_widening_no_union + all-false authority
# ---------------------------------------------------------------------------


def test_no_widening_requires_single_exact_no_union() -> None:
    """(IAP-INV-007) True only for a single exact decision with no union of narrower decisions."""
    assert (
        no_widening_no_union(single_exact_decision=True, no_union_of_narrower=True)
        is True
    )
    assert (
        no_widening_no_union(single_exact_decision=None, no_union_of_narrower=True)
        is False
    )
    assert (
        no_widening_no_union(single_exact_decision=True, no_union_of_narrower=False)
        is False
    )


def test_approval_grants_no_authority_on_all_false() -> None:
    """(§7 / IAP-INV-005) The default all-false authority effect grants nothing."""
    assert approval_grants_no_authority(ApprovalAuthorityEffect()) is True


# ---------------------------------------------------------------------------
# §6.4 active_egress_currentness — cache / absence ≠ currentness
# ---------------------------------------------------------------------------


def test_active_currentness_requires_active_bounded_proof() -> None:
    """(§15 line 381, IAP-AC-008) True only for an active bounded proof, not inferred from absence."""
    assert (
        active_egress_currentness(
            active_bounded_proof=True,
            inferred_from_absence=False,
            single_authoritative_consumption=True,
        )
        is True
    )


def test_absence_inferred_currentness_fails_closed() -> None:
    """(§14 line 365 / §15 line 381) Currentness inferred from absence of an event fails closed."""
    assert (
        active_egress_currentness(
            active_bounded_proof=True,
            inferred_from_absence=True,
            single_authoritative_consumption=True,
        )
        is False
    )
    assert (
        active_egress_currentness(
            active_bounded_proof=None,
            inferred_from_absence=False,
            single_authoritative_consumption=True,
        )
        is False
    )


# ---------------------------------------------------------------------------
# §6.5 stale_generation_fenced + conflicting_evaluators_unknown
# ---------------------------------------------------------------------------


def test_older_generation_is_fenced_by_newer() -> None:
    """(§17 line 405, IAP-INV-012) An older generation is fenced (provably precedes) a newer one."""
    older, newer = ordering_event(1), ordering_event(2)
    assert stale_generation_fenced(older, newer) is True


def test_ambiguous_generation_pair_fails_closed() -> None:
    """(§19 line 433 wall-clock) An unordered / cross-continuity pair fails closed (not fenced)."""
    a = ordering_event(1, continuity="cont-a")
    b = ordering_event(2, continuity="cont-b")  # different continuity => AMBIGUOUS
    assert stale_generation_fenced(a, b) is False
    # A newer-before-older pair is also not "older fenced by newer".
    assert stale_generation_fenced(ordering_event(2), ordering_event(1)) is False


def test_conflicting_evaluators_is_unknown_no_majority() -> None:
    """(§17 line 403, IAP-AC-010) Conflicting results => UNKNOWN (retained, no majority / newest)."""
    conflict = [ApprovalResult.APPROVE, ApprovalResult.DENY, ApprovalResult.APPROVE]
    assert conflicting_evaluators_unknown(conflict) is ApprovalResult.UNKNOWN


def test_conflicting_evaluators_empty_is_unknown() -> None:
    """(∅ fail-closed) An empty evaluator set => UNKNOWN."""
    assert conflicting_evaluators_unknown([]) is ApprovalResult.UNKNOWN


def test_unanimous_evaluators_return_agreed_result() -> None:
    """(positive side) A unanimous evaluator set returns the single agreed result."""
    assert (
        conflicting_evaluators_unknown([ApprovalResult.APPROVE, ApprovalResult.APPROVE])
        is ApprovalResult.APPROVE
    )
    assert conflicting_evaluators_unknown([ApprovalResult.DENY]) is ApprovalResult.DENY


@given(st.lists(st.sampled_from(list(ApprovalResult)), min_size=1, max_size=6))
def test_conflicting_evaluators_property(results: list[ApprovalResult]) -> None:
    """(property) UNKNOWN iff the results conflict; else the single agreed result — never a majority pick."""
    outcome = conflicting_evaluators_unknown(results)
    if len(set(results)) > 1:
        assert outcome is ApprovalResult.UNKNOWN
    else:
        assert outcome is results[0]


# ---------------------------------------------------------------------------
# §6.6 recovery_revives_nothing
# ---------------------------------------------------------------------------


def test_recovery_revives_nothing() -> None:
    """(§20 line 447, IAP-INV-014) Nothing revives a prior decision / permission / authority — unconditional True."""
    assert recovery_revives_nothing() is True
