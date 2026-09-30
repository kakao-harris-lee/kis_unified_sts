"""Unit tests for :mod:`tos_runtime.recovery.possibly_live` (TOS Phase 5 W1; Phase 3 carryover
ⓗ). Mirrors ``tos/runtime/tests/engine/test_driver.py``'s own crash-window construction
technique — a durable inbox/evidence store is built directly, never through a real driver crash.
"""

from __future__ import annotations

import pytest
from tos.engine.records import event_identity
from tos.evidence import EvidenceAppendReceipt
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.recovery.possibly_live import (
    PossiblyLiveAttempt,
    reconstruct_possibly_live_attempts,
)

from .conftest import SCHEME, fx

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


def _mark_handling_started(
    inbox: SqliteEventInbox, seq: int, marker: EvidenceAppendReceipt
) -> tuple[int, int]:
    """Records ``inbox.mark_handling_started(...)`` and returns ``marker``'s
    narrowed ``(seq, key_generation)`` for callers that also assert against a
    :class:`~tos_runtime.recovery.possibly_live.PossiblyLiveAttempt`'s own
    non-Optional fields — a successful evidence ``append()`` never returns
    either as ``None`` (``EvidenceAppendReceipt``'s own docstring: "a failed
    or partial append never returns this type")."""
    assert marker.seq is not None
    assert marker.key_generation is not None
    inbox.mark_handling_started(
        seq, evidence_seq=marker.seq, generation=marker.key_generation
    )
    return marker.seq, marker.key_generation


def _mark_consumed(
    inbox: SqliteEventInbox, seq: int, consumed: EvidenceAppendReceipt
) -> None:
    """``inbox.mark_consumed(...)``, narrowing ``consumed``'s ``seq``/
    ``key_generation`` the same way as :func:`_mark_handling_started`."""
    assert consumed.seq is not None
    assert consumed.key_generation is not None
    inbox.mark_consumed(
        seq, evidence_seq=consumed.seq, generation=consumed.key_generation
    )


def test_empty_inbox_yields_no_possibly_live_attempts(inbox: SqliteEventInbox) -> None:
    assert reconstruct_possibly_live_attempts(inbox, scheme=SCHEME) == ()


def test_pending_never_started_event_is_not_possibly_live(
    inbox: SqliteEventInbox,
) -> None:
    """An admitted-but-never-touched event (no ``EVENT_HANDLING_STARTED`` marker at all) is
    ordinary pending work, not a crash-window candidate."""
    inbox.enqueue(fx.crossing_event(seq=1))
    assert reconstruct_possibly_live_attempts(inbox, scheme=SCHEME) == ()


def test_consumed_event_is_not_possibly_live(
    inbox: SqliteEventInbox, evidence_store: SqliteEvidenceStore
) -> None:
    """A row that reached ``EVENT_CONSUMED`` (handling started AND finished) is resolved, not
    possibly-live — mirrors independent review finding #3's own "consumed => done" half.
    """
    event = fx.crossing_event(seq=1)
    receipt = inbox.enqueue(event)
    event_id = event_identity(event, scheme=SCHEME)
    marker = evidence_store.append(
        {"event_id": event_id},
        kind="EVENT_HANDLING_STARTED",
        record_class="EVENT_HANDLING_STARTED",
    )
    _mark_handling_started(inbox, receipt.seq, marker)
    consumed = evidence_store.append(
        {"event_id": event_id}, kind="EVENT_CONSUMED", record_class="EVENT_CONSUMED"
    )
    _mark_consumed(inbox, receipt.seq, consumed)
    assert reconstruct_possibly_live_attempts(inbox, scheme=SCHEME) == ()


def test_handling_started_without_consumed_is_possibly_live(
    inbox: SqliteEventInbox, evidence_store: SqliteEvidenceStore
) -> None:
    """The finding-#3 crash window itself: ``EVENT_HANDLING_STARTED`` durably recorded, no
    ``EVENT_CONSUMED`` at all — this is the row a real process crash between the two would
    leave behind."""
    event = fx.crossing_event(seq=1)
    receipt = inbox.enqueue(event)
    event_id = event_identity(event, scheme=SCHEME)
    marker = evidence_store.append(
        {"event_id": event_id},
        kind="EVENT_HANDLING_STARTED",
        record_class="EVENT_HANDLING_STARTED",
    )
    evidence_seq, generation = _mark_handling_started(inbox, receipt.seq, marker)

    attempts = reconstruct_possibly_live_attempts(inbox, scheme=SCHEME)

    assert attempts == (
        PossiblyLiveAttempt(
            event_id=event_id,
            inbox_seq=receipt.seq,
            handling_started_evidence_seq=evidence_seq,
            handling_started_generation=generation,
        ),
    )


def test_multiple_possibly_live_attempts_are_all_returned_conservatively(
    inbox: SqliteEventInbox, evidence_store: SqliteEvidenceStore
) -> None:
    """Conservative-by-construction (module docstring): every ambiguous row is included, never
    just the first / most-recent one."""
    event_ids = []
    for seq in (1, 2, 3):
        event = fx.crossing_event(seq=seq)
        receipt = inbox.enqueue(event)
        event_id = event_identity(event, scheme=SCHEME)
        marker = evidence_store.append(
            {"event_id": event_id},
            kind="EVENT_HANDLING_STARTED",
            record_class="EVENT_HANDLING_STARTED",
        )
        _mark_handling_started(inbox, receipt.seq, marker)
        event_ids.append(event_id)

    attempts = reconstruct_possibly_live_attempts(inbox, scheme=SCHEME)
    assert [attempt.event_id for attempt in attempts] == event_ids
