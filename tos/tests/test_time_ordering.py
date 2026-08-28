"""Time ordering — REUSE promoted ``compare_order`` + MAJOR-1 frame separation.

EV-L1 predicate substrate only; TIME-EV-007 remains NOT_IMPLEMENTED pending
EV-L2/L3 fault injection. Time contributes NO new comparison logic; it maps
snapshot coordinates onto ``tos.ordering.OrderingEvent`` with strict frame
separation (time design §5). The MAJOR-1 property fixes that a monotonic-only
cross-continuity pair is AMBIGUOUS — proving time never pushes the per-continuity
monotonic frame onto the reference-frame interval branch.
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.ordering import Ordering, compare_order
from tos.time import (
    MonotonicReading,
    UncertaintyInterval,
    ordering_event_from_monotonic,
    ordering_event_from_reference_interval,
)


@given(v1=st.integers(0, 10**6), v2=st.integers(0, 10**6))
def test_major1_cross_continuity_monotonic_only_is_ambiguous(v1: int, v2: int) -> None:
    """MAJOR-1: two cross-continuity monotonic-only events are always AMBIGUOUS.

    The monotonic mapping leaves ``time_lo``/``time_hi`` None, so the un-guarded
    reference-frame interval branch cannot order them — precisely the safety
    property that stops monotonic values from being subtracted across continuities.
    """
    a = ordering_event_from_monotonic(
        MonotonicReading(monotonic_continuity_id="c1", local_monotonic_value=v1)
    )
    b = ordering_event_from_monotonic(
        MonotonicReading(monotonic_continuity_id="c2", local_monotonic_value=v2)
    )
    assert a.time_lo is None and a.time_hi is None
    assert b.time_lo is None and b.time_hi is None
    assert compare_order(a, b) is Ordering.AMBIGUOUS


@given(v1=st.integers(0, 1000), v2=st.integers(0, 1000))
def test_same_continuity_monotonic_orders(v1: int, v2: int) -> None:
    """Within one continuity, the monotonic frame orders (§10 priority-3)."""
    a = ordering_event_from_monotonic(
        MonotonicReading(monotonic_continuity_id="c1", local_monotonic_value=v1)
    )
    b = ordering_event_from_monotonic(
        MonotonicReading(monotonic_continuity_id="c1", local_monotonic_value=v2)
    )
    result = compare_order(a, b)
    if v1 < v2:
        assert result is Ordering.BEFORE
    elif v1 > v2:
        assert result is Ordering.AFTER
    else:
        assert result is Ordering.AMBIGUOUS


@given(lo=st.integers(0, 100), width=st.integers(0, 50), gap=st.integers(1, 50))
def test_reference_interval_disjoint_orders(lo: int, width: int, gap: int) -> None:
    """Disjoint reference-frame intervals order (§10 priority-4)."""
    a = ordering_event_from_reference_interval(
        UncertaintyInterval(lo=lo, hi=lo + width)
    )
    b_lo = lo + width + gap
    b = ordering_event_from_reference_interval(
        UncertaintyInterval(lo=b_lo, hi=b_lo + width)
    )
    assert compare_order(a, b) is Ordering.BEFORE
    assert compare_order(b, a) is Ordering.AFTER


def test_reference_interval_overlap_is_ambiguous() -> None:
    """Overlapping reference-frame intervals are AMBIGUOUS, not sorted (§10 259)."""
    a = ordering_event_from_reference_interval(UncertaintyInterval(lo=10, hi=30))
    b = ordering_event_from_reference_interval(UncertaintyInterval(lo=20, hi=40))
    assert compare_order(a, b) is Ordering.AMBIGUOUS


def test_reference_interval_one_sided_unknown_is_ambiguous() -> None:
    """A one-sided-unknown (None) endpoint disables interval ordering (UNKNOWN fail-closed)."""
    a = ordering_event_from_reference_interval(UncertaintyInterval(lo=None, hi=20))
    b = ordering_event_from_reference_interval(UncertaintyInterval(lo=30, hi=40))
    assert compare_order(a, b) is Ordering.AMBIGUOUS
