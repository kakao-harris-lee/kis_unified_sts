"""Causal-ordering primitive — promoted core (time design §5 / #4 §3.1 PROMOTE).

Promoted out of ``tos.evidence.predicates`` into a dedicated ``tos.ordering``
core module so both ``tos.evidence`` (ADR-002-016 §11 causal order) and
``tos.time`` (ADR-002-008 §10 trustworthy-time order) share **one** ordering
law without importing each other (time design §0.4b / §5). ``tos.evidence``
would be a *consumer* of time (an evidence record references a time snapshot —
``SAFETY-EVIDENCE-ENVELOPE.time_evidence``), so a ``time -> evidence`` edge is a
layering inversion; both packages instead depend one-directionally on
``tos.ordering``, which itself depends only on ``tos.canonical`` for
:class:`~tos.canonical.FrozenModel` (a single core-internal edge).

Ordering follows the §11 / §10 priority in order:

  1. quorum commit index,
  2. egress journal sequence,
  3. source-native sequence (same continuity only),
  4. component continuity + local monotonic value (same continuity only),
  5. typed causal predecessor links,
  6. trustworthy-time interval (disjoint intervals only).

A bare cross-host wall clock never orders; cross-continuity monotonic values are
never subtracted (compared only within the same ``source_continuity_id``);
overlapping trustworthy-time uncertainty is **ambiguous, not sorted**. The
interval branch (``time_lo``/``time_hi``) is reference/trustworthy-time frame
only — the per-continuity local-monotonic frame must never be placed on it
(time design MAJOR-1). This module re-defines no logic beyond what was ratified
and shipped in evidence ``86d8fa4e``.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; no ``shared.*``,
no ``tos.evidence`` / ``tos.time`` / ``tos.capsule`` (time design §0.3/§5).
"""

from __future__ import annotations

from enum import StrEnum

from tos.canonical import FrozenModel


class Ordering(StrEnum):
    """A pairwise causal-ordering result (ADR-002-016 §11 / ADR-002-008 §10)."""

    BEFORE = "BEFORE"
    AFTER = "AFTER"
    AMBIGUOUS = "AMBIGUOUS"


class OrderingEvent(FrozenModel):
    """Ordering coordinates for one event (ADR-002-016 §11 line 306-315).

    Carries the §11 ordering bases in priority order. Cross-continuity
    ``source_native_sequence`` / ``local_monotonic_value`` are never subtracted
    (compared only within the same ``source_continuity_id``); a bare wall clock is
    absent by construction (only a trustworthy-time *interval* ``time_lo``/
    ``time_hi`` participates).

    ``time_lo``/``time_hi`` are a **reference/trustworthy-time frame** interval
    (ADR-002-008 §10 priority-4). The per-continuity local-monotonic frame
    (priority-3) is carried separately in ``local_monotonic_value`` and must never
    be mapped onto ``time_lo``/``time_hi`` — doing so would create an un-guarded
    cross-continuity order, violating the §8 non-subtraction rule (time design
    MAJOR-1).
    """

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
    """Order two events by the §11 / §10 priority, else AMBIGUOUS.

    Priority (ADR-002-016 §11 line 306-311 / ADR-002-008 §10 line 249-261):
    quorum commit index -> egress journal sequence -> source-native sequence
    (same continuity only) -> component continuity + local monotonic (same
    continuity only) -> typed causal links -> trustworthy-time interval (disjoint
    only). A bare cross-host wall clock never orders (§11 line 304); overlapping
    time uncertainty is **ambiguous, not sorted** (§11 line 313). Cross-continuity
    monotonic values are never subtracted (§11 line 313).

    Args:
        a: The first event.
        b: The second event.

    Returns:
        ``BEFORE`` (a precedes b), ``AFTER`` (a follows b), or ``AMBIGUOUS``.
    """
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
    # Typed causal links (immutable id references).
    if b.event_id is not None and b.event_id in a.causal_predecessor_ids:
        return Ordering.AFTER
    if a.event_id is not None and a.event_id in b.causal_predecessor_ids:
        return Ordering.BEFORE
    # Trustworthy-time interval: only disjoint intervals order; overlap => ambiguous.
    if None not in (a.time_lo, a.time_hi, b.time_lo, b.time_hi):
        if a.time_hi < b.time_lo:  # type: ignore[operator]
            return Ordering.BEFORE
        if b.time_hi < a.time_lo:  # type: ignore[operator]
            return Ordering.AFTER
    return Ordering.AMBIGUOUS
