"""Unit tests for :mod:`tos_runtime.recovery.possibly_live` (TOS Phase 5 W1; Phase 3 carryover
ⓗ). Mirrors ``tos/runtime/tests/engine/test_driver.py``'s own crash-window construction
technique — a durable inbox/evidence store is built directly, never through a real driver crash.
"""

from __future__ import annotations

import pytest
from tos.engine.records import event_identity
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.recovery.possibly_live import (
    PossiblyLiveAttempt,
    reconstruct_possibly_live_attempts,
)

from .conftest import SCHEME, fx

pytestmark = pytest.mark.usefixtures("_hermetic_network_guard", "_hermetic_write_guard")


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
    inbox.mark_handling_started(
        receipt.seq, evidence_seq=marker.seq, generation=marker.key_generation
    )
    consumed = evidence_store.append(
        {"event_id": event_id}, kind="EVENT_CONSUMED", record_class="EVENT_CONSUMED"
    )
    inbox.mark_consumed(
        receipt.seq, evidence_seq=consumed.seq, generation=consumed.key_generation
    )
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
    inbox.mark_handling_started(
        receipt.seq, evidence_seq=marker.seq, generation=marker.key_generation
    )

    attempts = reconstruct_possibly_live_attempts(inbox, scheme=SCHEME)

    assert attempts == (
        PossiblyLiveAttempt(
            event_id=event_id,
            inbox_seq=receipt.seq,
            handling_started_evidence_seq=marker.seq,
            handling_started_generation=marker.key_generation,
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
        inbox.mark_handling_started(
            receipt.seq, evidence_seq=marker.seq, generation=marker.key_generation
        )
        event_ids.append(event_id)

    attempts = reconstruct_possibly_live_attempts(inbox, scheme=SCHEME)
    assert [attempt.event_id for attempt in attempts] == event_ids
