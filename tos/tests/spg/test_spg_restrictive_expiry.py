"""Restrictive precedence + change direction + expiry non-revival (§5.5/§5.6; SPG-EV-006/008).

change_direction folds unorderable/unproven to AUTHORITY_INCREASING; a restrictive override
needs a proven RESTRICTIVE direction + all preservation flags; expiry revives nothing.
"""

from __future__ import annotations

from tos.spg import (
    ChangeDirection,
    change_direction,
    expiry_revives_nothing,
    expiry_suspends_new_risk,
    restrictive_override_admissible,
)

from ._spg_strategies import (
    all_preserved_override_inputs,
    restrictive_direction_inputs,
)

# ---------------------------------------------------------------------------
# change_direction — both-ways + fold-to-authority-increasing
# ---------------------------------------------------------------------------


def test_pure_tightening_is_restrictive() -> None:
    """(canary + §14 line 393) A proven, semantics-preserving tightening => RESTRICTIVE."""
    assert (
        change_direction(restrictive_direction_inputs()) is ChangeDirection.RESTRICTIVE
    )


def test_widening_is_permissive() -> None:
    """(canary -) A widened dimension => PERMISSIVE."""
    assert (
        change_direction(restrictive_direction_inputs(any_dimension_widened=True))
        is ChangeDirection.PERMISSIVE
    )


def test_previously_denied_now_permitted_is_authority_increasing() -> None:
    """(§5.9 line 143) Permitting a previously denied scope => AUTHORITY_INCREASING."""
    assert (
        change_direction(
            restrictive_direction_inputs(previously_denied_now_permitted=True)
        )
        is ChangeDirection.AUTHORITY_INCREASING
    )


def test_unorderable_folds_to_authority_increasing() -> None:
    """(§11 line 317) Unorderable / unproven direction folds to AUTHORITY_INCREASING."""
    assert (
        change_direction(
            restrictive_direction_inputs(all_dimensions_ordered_conservative=None)
        )
        is ChangeDirection.AUTHORITY_INCREASING
    )
    assert (
        change_direction(
            restrictive_direction_inputs(all_dimensions_ordered_conservative=False)
        )
        is ChangeDirection.AUTHORITY_INCREASING
    )


def test_semantics_change_forbids_restrictive_presumption() -> None:
    """(§14 line 405) A nominal reduction that changes semantics is NOT restrictive."""
    assert (
        change_direction(restrictive_direction_inputs(semantics_changed=True))
        is ChangeDirection.AUTHORITY_INCREASING
    )
    # None (unknown) also fails closed.
    assert (
        change_direction(restrictive_direction_inputs(semantics_changed=None))
        is ChangeDirection.AUTHORITY_INCREASING
    )


def test_default_direction_is_authority_increasing() -> None:
    """(∅-seal / fail-closed) A bare ChangeDirectionInputs (all None) => AUTHORITY_INCREASING."""
    from tos.spg import ChangeDirectionInputs

    assert (
        change_direction(ChangeDirectionInputs())
        is ChangeDirection.AUTHORITY_INCREASING
    )


# ---------------------------------------------------------------------------
# restrictive_override_admissible — both-ways
# ---------------------------------------------------------------------------


def test_restrictive_override_positive_side() -> None:
    """(canary +) A RESTRICTIVE direction + all preserved => admissible."""
    assert (
        restrictive_override_admissible(
            ChangeDirection.RESTRICTIVE, all_preserved_override_inputs()
        )
        is True
    )


def test_non_restrictive_direction_never_admissible() -> None:
    """(canary -) A PERMISSIVE / AUTHORITY_INCREASING direction is never an admissible override."""
    for direction in (
        ChangeDirection.PERMISSIVE,
        ChangeDirection.AUTHORITY_INCREASING,
    ):
        assert (
            restrictive_override_admissible(direction, all_preserved_override_inputs())
            is False
        )


def test_each_unpreserved_flag_blocks_override() -> None:
    """(fail-closed §14 line 401) Any un-preserved protected state blocks the override."""
    for field in (
        "no_auto_revert",
        "capacity_preserved",
        "orders_preserved",
        "exposure_preserved",
        "unknown_preserved",
        "protective_preserved",
    ):
        inputs = all_preserved_override_inputs(**{field: None})
        assert (
            restrictive_override_admissible(ChangeDirection.RESTRICTIVE, inputs)
            is False
        )


# ---------------------------------------------------------------------------
# expiry — suspends new risk + revives nothing
# ---------------------------------------------------------------------------


def test_expiry_suspends_new_risk_both_ways() -> None:
    """(canary) Expired / unverifiable time suspends new risk; only positive-both clears it."""
    assert expiry_suspends_new_risk(not_expired=False, time_verifiable=True) is True
    assert expiry_suspends_new_risk(not_expired=True, time_verifiable=False) is True
    assert expiry_suspends_new_risk(not_expired=None, time_verifiable=True) is True
    assert expiry_suspends_new_risk(not_expired=True, time_verifiable=None) is True
    # positive side: not-expired AND time-verifiable => not suspended
    assert expiry_suspends_new_risk(not_expired=True, time_verifiable=True) is False


def test_expiry_revives_nothing_unconditionally() -> None:
    """(SPG-INV-013 §18 line 472-482) Expiry revives nothing — unconditionally True."""
    assert expiry_revives_nothing() is True
