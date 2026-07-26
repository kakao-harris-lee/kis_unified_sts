"""recovery_inventory_complete — completeness both-ways + ∅ (design #17 §5.1; SBR-EV-004).

Regime tag: predicate / model substrate only; SBR-EV-004 NOT_IMPLEMENTED (`/3` residue);
EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.sbr import RecoveryBarrierPolicy, recovery_inventory_complete

from ._sbr_strategies import DEPENDENCY_KINDS, clean_inventory_cut, clean_policy


def test_complete_cut_is_complete_positive_side() -> None:
    """(§5.1 positive) A cut covering every required bounded dependency is complete."""
    assert recovery_inventory_complete(clean_inventory_cut(), clean_policy()) is True


def test_missing_required_dependency_is_incomplete() -> None:
    """(§5.1 / SBR-AC-004 line 641) An omitted required dependency => incomplete (NOT_READY)."""
    cut = clean_inventory_cut()
    missing = cut.model_copy(
        update={"observed_dependency_kinds": DEPENDENCY_KINDS - {"protective"}}
    )
    assert recovery_inventory_complete(missing, clean_policy()) is False


def test_unbounded_dependency_is_incomplete() -> None:
    """(§12 line 162) An unbounded dependency window => incomplete."""
    cut = clean_inventory_cut()
    unbounded = cut.model_copy(
        update={"unbounded_dependency_kinds": frozenset({"capacity"})}
    )
    assert recovery_inventory_complete(unbounded, clean_policy()) is False


def test_ambiguous_time_is_non_permissive() -> None:
    """(§12 line 335) A time-ambiguous cut stays non-permissive."""
    cut = clean_inventory_cut()
    for ambiguous in (True, None):
        assert (
            recovery_inventory_complete(
                cut.model_copy(update={"time_ambiguous": ambiguous}), clean_policy()
            )
            is False
        )


def test_missing_conservative_witness_is_incomplete() -> None:
    """(§12 line 332) A flat snapshot missing an unobserved-window / bound / repeat witness fails."""
    cut = clean_inventory_cut()
    for witness in (
        "unobserved_window_assumptions_present",
        "max_adverse_bounds_present",
        "required_repeat_observations_met",
    ):
        for value in (False, None):
            assert (
                recovery_inventory_complete(
                    cut.model_copy(update={witness: value}), clean_policy()
                )
                is False
            )


def test_empty_required_set_is_fail_closed() -> None:
    """(∅ / §4.7) A cut with no required dependency proves nothing — vacuous completeness fails."""
    cut = clean_inventory_cut(required=frozenset())
    empty_policy = RecoveryBarrierPolicy(
        policy_id="p", required_dependency_kinds=frozenset()
    )
    assert recovery_inventory_complete(cut, empty_policy) is False


def test_none_inputs_fail_closed() -> None:
    """(∅) A None cut / policy proves nothing."""
    assert recovery_inventory_complete(None, clean_policy()) is False
    assert recovery_inventory_complete(clean_inventory_cut(), None) is False
