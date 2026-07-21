"""ERI-EV-006 (core) — causal ordering & time ambiguity (design #4 §4.3, ADR §11).

Ordering follows the §11 priority (quorum -> egress journal -> source-native ->
component continuity + local monotonic -> typed causal links -> trustworthy-time
interval). A bare cross-host wall clock never orders; cross-continuity monotonic
values are never subtracted; overlapping time uncertainty is ambiguous, not
sorted.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from tos.evidence import Ordering, OrderingEvent, compare_order


@given(a=st.integers(0, 1000), b=st.integers(0, 1000))
def test_quorum_index_orders(a: int, b: int) -> None:
    """Quorum commit index is the top ordering basis."""
    ea = OrderingEvent(quorum_commit_index=a)
    eb = OrderingEvent(quorum_commit_index=b)
    result = compare_order(ea, eb)
    if a < b:
        assert result is Ordering.BEFORE
    elif a > b:
        assert result is Ordering.AFTER
    else:
        assert result is Ordering.AMBIGUOUS


def test_wall_clock_alone_does_not_order() -> None:
    """No trustworthy-time interval and no other basis => ambiguous (§11 line 304)."""
    ea = OrderingEvent(event_id="a")
    eb = OrderingEvent(event_id="b")
    assert compare_order(ea, eb) is Ordering.AMBIGUOUS


def test_same_continuity_monotonic_orders() -> None:
    """Within one continuity, local monotonic value orders events."""
    ea = OrderingEvent(source_continuity_id="c1", local_monotonic_value=1)
    eb = OrderingEvent(source_continuity_id="c1", local_monotonic_value=2)
    assert compare_order(ea, eb) is Ordering.BEFORE
    assert compare_order(eb, ea) is Ordering.AFTER


def test_cross_continuity_monotonic_not_subtracted() -> None:
    """Different continuities cannot be ordered by their monotonic values (§11 313)."""
    ea = OrderingEvent(source_continuity_id="c1", local_monotonic_value=100)
    eb = OrderingEvent(source_continuity_id="c2", local_monotonic_value=1)
    # No shared basis and no time interval => ambiguous, not "100 > 1".
    assert compare_order(ea, eb) is Ordering.AMBIGUOUS


def test_overlapping_time_uncertainty_is_ambiguous() -> None:
    """Overlapping trustworthy-time intervals are ambiguous, not sorted (§11 313)."""
    ea = OrderingEvent(event_id="a", time_lo=10, time_hi=30)
    eb = OrderingEvent(event_id="b", time_lo=20, time_hi=40)
    assert compare_order(ea, eb) is Ordering.AMBIGUOUS


def test_disjoint_time_intervals_order() -> None:
    """Disjoint trustworthy-time intervals order as a last-resort basis (§11 311)."""
    ea = OrderingEvent(event_id="a", time_lo=10, time_hi=20)
    eb = OrderingEvent(event_id="b", time_lo=30, time_hi=40)
    assert compare_order(ea, eb) is Ordering.BEFORE
    assert compare_order(eb, ea) is Ordering.AFTER


def test_typed_causal_link_orders() -> None:
    """A typed causal predecessor link orders the child after its parent."""
    parent = OrderingEvent(event_id="parent")
    child = OrderingEvent(event_id="child", causal_predecessor_ids=("parent",))
    assert compare_order(child, parent) is Ordering.AFTER
    assert compare_order(parent, child) is Ordering.BEFORE


def test_priority_quorum_over_time() -> None:
    """Quorum index outranks a conflicting trustworthy-time interval."""
    # Quorum says a before b; time intervals (if trusted) would say a after b.
    ea = OrderingEvent(event_id="a", quorum_commit_index=1, time_lo=100, time_hi=110)
    eb = OrderingEvent(event_id="b", quorum_commit_index=2, time_lo=10, time_hi=20)
    assert compare_order(ea, eb) is Ordering.BEFORE


@given(lo=st.integers(0, 100), width=st.integers(0, 50), gap=st.integers(1, 50))
def test_disjoint_intervals_always_order(lo: int, width: int, gap: int) -> None:
    """Property: strictly disjoint intervals never resolve to ambiguous."""
    ea = OrderingEvent(event_id="a", time_lo=lo, time_hi=lo + width)
    b_lo = lo + width + gap
    eb = OrderingEvent(event_id="b", time_lo=b_lo, time_hi=b_lo + width)
    assert compare_order(ea, eb) is Ordering.BEFORE
