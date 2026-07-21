"""Time-side ordering mapping — REUSE promoted ``compare_order`` (time design §5).

Time contributes **no new comparison logic** (that would risk drift from the
shipped, ratified ordering law — DRY, CLAUDE.md). It only maps Time Health
Snapshot coordinates onto :class:`tos.ordering.OrderingEvent` and calls the
promoted :func:`tos.ordering.compare_order` (time design §0.4b/§5).

The coordinate mapping is **strictly frame-separated (MAJOR-1)**:

* ``local_monotonic_value`` (+ ``monotonic_continuity_id``) -> the priority-3
  per-continuity fields ``local_monotonic_value`` / ``source_continuity_id``;
  compared only inside ``compare_order``'s ``same_continuity`` guard.
* :class:`~tos.time.elements.UncertaintyInterval` (reference frame, §2.6) -> the
  priority-4 ``time_lo`` / ``time_hi`` interval (the un-guarded interval branch is
  reference-frame only).

The monotonic coordinate is **never** placed on ``time_lo``/``time_hi``: two
cross-continuity events carrying only a monotonic coordinate therefore resolve to
``AMBIGUOUS`` (the interval branch sees ``None`` and cannot sort), which is the
MAJOR-1 property fixed in the tests. [TIME-AC-004, TIME-AC-007; SAFE-031, SAFE-035]

Pure module: ``tos.ordering`` / ``tos.time`` only.
"""

from __future__ import annotations

from tos.ordering import OrderingEvent
from tos.time.elements import MonotonicReading, UncertaintyInterval


def ordering_event_from_monotonic(
    reading: MonotonicReading, *, event_id: str | None = None
) -> OrderingEvent:
    """Map a per-continuity monotonic reading to an OrderingEvent (§10 priority-3).

    ``time_lo``/``time_hi`` are left ``None`` on purpose: the monotonic frame must
    never enter the reference-frame interval branch (MAJOR-1). The value is only
    ever compared within its own ``monotonic_continuity_id``.

    Args:
        reading: The per-continuity monotonic reading (opaque injected coordinate).
        event_id: Optional event identity for typed causal-link ordering.

    Returns:
        An :class:`~tos.ordering.OrderingEvent` carrying only monotonic coords.
    """
    return OrderingEvent(
        event_id=event_id,
        source_continuity_id=reading.monotonic_continuity_id,
        local_monotonic_value=reading.local_monotonic_value,
    )


def ordering_event_from_reference_interval(
    interval: UncertaintyInterval, *, event_id: str | None = None
) -> OrderingEvent:
    """Map a reference-frame uncertainty interval to an OrderingEvent (§10 priority-4).

    Only the reference-frame interval enters ``time_lo``/``time_hi`` (the closed-
    interval, disjoint-only convention of ``compare_order`` is preserved
    verbatim — overlap/touch => AMBIGUOUS).

    Args:
        interval: The reference-frame uncertainty interval (§2.6).
        event_id: Optional event identity for typed causal-link ordering.

    Returns:
        An :class:`~tos.ordering.OrderingEvent` carrying only the time interval.
    """
    return OrderingEvent(
        event_id=event_id,
        time_lo=interval.lo,
        time_hi=interval.hi,
    )
