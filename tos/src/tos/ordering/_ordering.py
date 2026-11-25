"""Causal-ordering primitive — promoted core (time design §5 / #4 §3.1 PROMOTE)."""

from __future__ import annotations

from enum import StrEnum

from tos.canonical import FrozenModel


class Ordering(StrEnum):
    """A pairwise causal-ordering result (ADR-002-016 §11 / ADR-002-008 §10)."""

    BEFORE = "BEFORE"
    AFTER = "AFTER"
    AMBIGUOUS = "AMBIGUOUS"


class OrderingEvent(FrozenModel):
    """Ordering coordinates for one event (ADR-002-016 §11 line 306-315)."""

    event_id: str | None = None
    quorum_commit_index: int | None = None
    egress_journal_sequence: int | None = None
    source_continuity_id: str | None = None
    source_native_sequence: int | None = None
    local_monotonic_value: int | None = None
    causal_predecessor_ids: tuple[str, ...] = ()
    time_lo: int | None = None
    time_hi: int | None = None


def _cmp(a: int, b: int) -> Ordering | None:
    """Return BEFORE/AFTER for a strict comparison, or ``None`` when equal."""
    if a < b:
        return Ordering.BEFORE
    if a > b:
        return Ordering.AFTER
    return None


def compare_order(a: OrderingEvent, b: OrderingEvent) -> Ordering:
    """Order two events by the §11 / §10 priority, else AMBIGUOUS."""
    if a.quorum_commit_index is not None and b.quorum_commit_index is not None:
        result = _cmp(a.quorum_commit_index, b.quorum_commit_index)
        if result is not None:
            return result
    if a.egress_journal_sequence is not None and b.egress_journal_sequence is not None:
        result = _cmp(a.egress_journal_sequence, b.egress_journal_sequence)
        if result is not None:
            return result
    same_continuity = (
        a.source_continuity_id is not None
        and a.source_continuity_id == b.source_continuity_id
    )
    if same_continuity:
        if (
            a.source_native_sequence is not None
            and b.source_native_sequence is not None
        ):
            result = _cmp(a.source_native_sequence, b.source_native_sequence)
            if result is not None:
                return result
        if a.local_monotonic_value is not None and b.local_monotonic_value is not None:
            result = _cmp(a.local_monotonic_value, b.local_monotonic_value)
            if result is not None:
                return result
    if b.event_id is not None and b.event_id in a.causal_predecessor_ids:
        return Ordering.AFTER
    if a.event_id is not None and a.event_id in b.causal_predecessor_ids:
        return Ordering.BEFORE
    if None not in (a.time_lo, a.time_hi, b.time_lo, b.time_hi):
        if a.time_hi < b.time_lo:  # type: ignore[operator]
            return Ordering.BEFORE
        if b.time_hi < a.time_lo:  # type: ignore[operator]
            return Ordering.AFTER
    return Ordering.AMBIGUOUS
