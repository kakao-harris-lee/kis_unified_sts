"""The two ordering helpers + the §6.3 (h)/(i)/(j) canaries (design #29 §5.0 NEW-1 / v1.3).

``restriction_floor_not_behind`` is *at-or-ahead* (equal passes) and
``generation_strictly_advances`` is *strictly ahead* (equal is a §5.8 reuse and denies). They are
deliberately **two** helpers: merging them in either direction is a real defect, and the two
canaries below pin that decision.

* (i) moving the ``equal ⇒ True`` short-circuit **after** the ``compare_order`` call in the floor
  helper turns every legitimate equal-floor decision into a denial, because ``compare_order`` maps
  an equal pair to ``Ordering.AMBIGUOUS`` (``tos/src/tos/ordering/_ordering.py`` lines 77-83);
* (j) injecting ``equal ⇒ True`` into the generation helper reopens §5.8 generation reuse.

Regime tag: release-admission predicate/model substrate only; closes no SCI-EV.
"""

from __future__ import annotations

import pytest
import tos.sci as sci
from hypothesis import given
from hypothesis import strategies as st
from tos.ordering import Ordering, OrderingEvent, compare_order

_SCALARS = st.integers(min_value=-1000, max_value=1000)


def test_ordering_maps_an_equal_pair_to_ambiguous() -> None:
    """The upstream fact both helpers are built around (``_ordering.py`` lines 77-83).

    ``_cmp`` returns ``None`` for an equal pair and ``compare_order`` falls through every other
    priority to ``AMBIGUOUS``. This is *why* the floor helper's equal short-circuit must precede the
    comparison, and *why* the generation helper needs no special equal case.
    """
    assert (
        compare_order(
            OrderingEvent(quorum_commit_index=5), OrderingEvent(quorum_commit_index=5)
        )
        is Ordering.AMBIGUOUS
    )


# --- restriction_floor_not_behind (at-or-ahead) -----------------------------------------------


def test_floor_equal_is_not_behind() -> None:
    """(§15 step 7) An equal floor means the decision observed the current restriction."""
    assert sci.restriction_floor_not_behind(7, 7) is True


def test_floor_ahead_is_not_behind() -> None:
    """(§15 step 7) A decision that saw a newer floor is at-or-ahead."""
    assert sci.restriction_floor_not_behind(8, 7) is True


def test_floor_behind_denies() -> None:
    """(§16 line 348) A decision behind the active floor has not seen the newest restrictive fact."""
    assert sci.restriction_floor_not_behind(6, 7) is False


@pytest.mark.parametrize("pair", [(None, 7), (7, None), (None, None)])
def test_absent_floor_denies(pair: tuple[int | None, int | None]) -> None:
    """(§5.0) A ``None`` on either side is unknown ordering — denial."""
    assert sci.restriction_floor_not_behind(*pair) is False


@given(decision=_SCALARS, active=_SCALARS)
def test_floor_helper_is_exactly_at_or_ahead(decision: int, active: int) -> None:
    """(property) The helper is ``decision >= active`` over the ordering-scalar domain."""
    assert sci.restriction_floor_not_behind(decision, active) is (decision >= active)


# --- generation_strictly_advances (strictly ahead) --------------------------------------------


def test_generation_strictly_advances_passes() -> None:
    """(§5.8) A strictly following generation advances."""
    assert sci.generation_strictly_advances(41, 42) is True


def test_generation_equal_is_a_reuse_and_denies() -> None:
    """(§5.8 line 131 / §6.3 (j)) "It cannot be reused" — an equal generation denies."""
    assert sci.generation_strictly_advances(42, 42) is False


def test_generation_regression_denies() -> None:
    """(§5.8) A regressing generation denies."""
    assert sci.generation_strictly_advances(42, 41) is False


@pytest.mark.parametrize("pair", [(None, 42), (42, None), (None, None)])
def test_absent_generation_denies(pair: tuple[int | None, int | None]) -> None:
    """(§5.0) A ``None`` on either side denies."""
    assert sci.generation_strictly_advances(*pair) is False


@given(predecessor=_SCALARS, successor=_SCALARS)
def test_generation_helper_is_exactly_strictly_ahead(
    predecessor: int, successor: int
) -> None:
    """(property) The helper is ``successor > predecessor`` over the ordering-scalar domain."""
    assert sci.generation_strictly_advances(predecessor, successor) is (
        successor > predecessor
    )


# --- the §6.3 (h)/(i)/(j) canaries ------------------------------------------------------------


def _mutant_floor_short_circuit_moved(
    decision_floor: int | None, active_floor: int | None
) -> bool:
    """§6.3 (i) mutant: the ``equal ⇒ True`` short-circuit moved **after** ``compare_order``."""
    if decision_floor is None or active_floor is None:
        return False
    ordering = compare_order(
        OrderingEvent(quorum_commit_index=active_floor),
        OrderingEvent(quorum_commit_index=decision_floor),
    )
    if ordering is Ordering.BEFORE:
        return True
    return decision_floor == active_floor and ordering is Ordering.BEFORE


def test_canary_i_short_circuit_order_is_load_bearing() -> None:
    """(§6.3 (i)) Moving the equal short-circuit after ``compare_order`` is a false-negative.

    The mutant denies a perfectly legitimate equal-floor decision — the property the real helper
    satisfies (``decision >= active``) fails for the mutant, so the canary is live.
    """
    assert sci.restriction_floor_not_behind(7, 7) is True
    assert _mutant_floor_short_circuit_moved(7, 7) is False


def _mutant_generation_allows_equal(
    predecessor: int | None, successor: int | None
) -> bool:
    """§6.3 (j) mutant: ``equal ⇒ True`` injected into the generation helper."""
    if predecessor is None or successor is None:
        return False
    if predecessor == successor:
        return True
    return (
        compare_order(
            OrderingEvent(quorum_commit_index=predecessor),
            OrderingEvent(quorum_commit_index=successor),
        )
        is Ordering.BEFORE
    )


def test_canary_j_generation_reuse_stays_sealed() -> None:
    """(§6.3 (j) / §5.8 line 131) The floor helper's equal rule would reopen generation reuse."""
    assert sci.generation_strictly_advances(42, 42) is False
    assert _mutant_generation_allows_equal(42, 42) is True


def _mutant_ambiguous_folds_to_pass(
    predecessor: int | None, successor: int | None
) -> bool:
    """§6.3 (h) mutant: ``is Ordering.BEFORE`` relaxed to ``is not Ordering.AFTER``."""
    if predecessor is None or successor is None:
        return False
    return (
        compare_order(
            OrderingEvent(quorum_commit_index=predecessor),
            OrderingEvent(quorum_commit_index=successor),
        )
        is not Ordering.AFTER
    )


def test_canary_h_ambiguous_must_not_fold_to_a_pass() -> None:
    """(§6.3 (h)) Folding ``AMBIGUOUS`` into a pass reopens generation reuse.

    On ``generation_strictly_advances`` the mutant is **killed**: an equal pair maps to
    ``AMBIGUOUS``, which ``is not AFTER``, so a reused generation would pass. On
    ``restriction_floor_not_behind`` the same edit is an **equivalent mutant** — the equal case is
    short-circuited before the comparison and two unequal ints never produce ``AMBIGUOUS`` — which
    is recorded here rather than hidden.
    """
    assert sci.generation_strictly_advances(42, 42) is False
    assert _mutant_ambiguous_folds_to_pass(42, 42) is True


def test_helpers_never_accept_a_string_coordinate() -> None:
    """(NEW-1) ``compare_order`` is ``OrderingEvent``-only; a raw string is never ordered here.

    Both helpers take ``int | None`` ordering scalars and wrap them in an ``OrderingEvent``; the
    string form that would silently produce ``AMBIGUOUS`` never reaches the comparison.
    """
    import inspect

    for helper in (sci.restriction_floor_not_behind, sci.generation_strictly_advances):
        annotations = inspect.get_annotations(helper, eval_str=True)
        for name, annotation in annotations.items():
            if name == "return":
                continue
            assert annotation == (
                int | None
            ), f"{helper.__name__}({name}) must be an int|None ordering scalar, not {annotation}"
