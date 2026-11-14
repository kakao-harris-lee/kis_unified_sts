"""Time-side ordering mapping — REUSE promoted ``compare_order`` (time design §5)."""

from __future__ import annotations

from tos.ordering import OrderingEvent
from tos.time.elements import MonotonicReading, UncertaintyInterval


def ordering_event_from_monotonic(
    reading: MonotonicReading, *, event_id: str | None = None
) -> OrderingEvent:
    """Map a per-continuity monotonic reading to an OrderingEvent (§10 priority-3)."""
    return OrderingEvent(
        event_id=event_id,
        source_continuity_id=reading.monotonic_continuity_id,
        local_monotonic_value=reading.local_monotonic_value,
    )


def ordering_event_from_reference_interval(
    interval: UncertaintyInterval, *, event_id: str | None = None
) -> OrderingEvent:
    """Map a reference-frame uncertainty interval to an OrderingEvent (§10 priority-4)."""
    return OrderingEvent(
        event_id=event_id,
        time_lo=interval.lo,
        time_hi=interval.hi,
    )
