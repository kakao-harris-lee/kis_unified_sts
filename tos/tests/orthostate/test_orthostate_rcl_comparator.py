"""The additive rcl capacity comparator that orthostate REUSEs (design #8 §3.4b/§9.1).

``capacity_at_least_as_conservative`` is exposed additively on ``tos.rcl`` for the
orthostate coupling / restart predicates (CPL-1, §5.3a dominance, §6.3 restart). It is
tested here — the orthostate side — so the ratified rcl suite stays green unchanged (this
adds no test to ``tos/tests/rcl``). It is reflexive, total on the nine capacity states,
ranks QUARANTINED_UNKNOWN >= POTENTIALLY_LIVE (the CPL-5 dominance basis), and ranks
RELEASED as the least conservative.
"""

from __future__ import annotations

import itertools

from tos.rcl import CapacityState, capacity_at_least_as_conservative

_S = CapacityState


def test_comparator_is_reflexive() -> None:
    """Every capacity state is at least as conservative as itself."""
    for state in _S:
        assert capacity_at_least_as_conservative(state, state) is True


def test_comparator_is_total_and_antisymmetric() -> None:
    """(total order) For every ordered pair, at least one direction holds; equal only when both."""
    for a, b in itertools.product(_S, _S):
        ab = capacity_at_least_as_conservative(a, b)
        ba = capacity_at_least_as_conservative(b, a)
        assert ab or ba  # total
        if ab and ba:
            assert a is b  # antisymmetric on the strict rank (distinct ranks per state)


def test_comparator_is_transitive() -> None:
    """(transitivity) a >= b and b >= c implies a >= c across all triples."""
    for a, b, c in itertools.product(_S, _S, _S):
        if capacity_at_least_as_conservative(
            a, b
        ) and capacity_at_least_as_conservative(b, c):
            assert capacity_at_least_as_conservative(a, c)


def test_quarantined_unknown_dominates_potentially_live() -> None:
    """(§5.3a basis) QUARANTINED_UNKNOWN >= POTENTIALLY_LIVE (and strictly more conservative)."""
    assert (
        capacity_at_least_as_conservative(_S.QUARANTINED_UNKNOWN, _S.POTENTIALLY_LIVE)
        is True
    )
    assert (
        capacity_at_least_as_conservative(_S.POTENTIALLY_LIVE, _S.QUARANTINED_UNKNOWN)
        is False
    )


def test_released_is_least_conservative() -> None:
    """RELEASED is at least as conservative as nothing but itself; everything dominates it."""
    for state in _S:
        assert capacity_at_least_as_conservative(state, _S.RELEASED) is True
        if state is not _S.RELEASED:
            assert capacity_at_least_as_conservative(_S.RELEASED, state) is False


def test_quarantined_unknown_is_most_conservative() -> None:
    """QUARANTINED_UNKNOWN dominates every capacity state (the CPL-5 exact obligation)."""
    for state in _S:
        assert capacity_at_least_as_conservative(_S.QUARANTINED_UNKNOWN, state) is True
