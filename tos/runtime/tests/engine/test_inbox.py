"""Hermetic tests for :class:`tos_runtime.engine.inbox.SqliteEventInbox` (TOS Phase 3 Wave 1
Lane A-R; plan §1.1 "enqueue 중복 거부 · 소비 순서 = seq").
"""

from __future__ import annotations

from pathlib import Path

from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos_runtime.engine.inbox import SqliteEventInbox

from . import _fixtures as fx


def test_enqueue_assigns_increasing_seq(inbox: SqliteEventInbox) -> None:
    r1 = inbox.enqueue(fx.decision_tick_event(seq=1))
    r2 = inbox.enqueue(fx.decision_tick_event(seq=2))
    assert r1.seq == 1
    assert r2.seq == 2
    assert inbox.count == 2


def test_duplicate_event_id_is_a_typed_refusal_not_an_exception(
    inbox: SqliteEventInbox,
) -> None:
    event = fx.decision_tick_event(seq=1)
    r1 = inbox.enqueue(event)
    r2 = inbox.enqueue(event)
    assert r2.duplicate is True
    assert r2.seq == r1.seq
    assert r2.event_id == r1.event_id
    assert inbox.count == 1


def test_different_events_get_different_ids(inbox: SqliteEventInbox) -> None:
    r1 = inbox.enqueue(fx.decision_tick_event(seq=1))
    r2 = inbox.enqueue(fx.decision_tick_event(seq=2))
    assert r1.event_id != r2.event_id


def test_next_unconsumed_returns_oldest_first_then_none(
    inbox: SqliteEventInbox,
) -> None:
    inbox.enqueue(fx.decision_tick_event(seq=1))
    inbox.enqueue(fx.decision_tick_event(seq=2))
    first = inbox.next_unconsumed()
    assert first is not None
    seq, event = first
    assert seq == 1
    inbox.mark_consumed(seq, evidence_seq=100, generation=1)

    second = inbox.next_unconsumed()
    assert second is not None
    assert second[0] == 2
    inbox.mark_consumed(2, evidence_seq=101, generation=1)

    assert inbox.next_unconsumed() is None


def test_mark_consumed_is_reflected_in_is_consumed(inbox: SqliteEventInbox) -> None:
    receipt = inbox.enqueue(fx.decision_tick_event(seq=1))
    assert inbox.is_consumed(receipt.seq) is False
    inbox.mark_consumed(receipt.seq, evidence_seq=7, generation=1)
    assert inbox.is_consumed(receipt.seq) is True


def test_replay_yields_every_admitted_event_consumed_or_not(
    inbox: SqliteEventInbox,
) -> None:
    inbox.enqueue(fx.decision_tick_event(seq=1))
    r2 = inbox.enqueue(fx.decision_tick_event(seq=2))
    inbox.mark_consumed(r2.seq, evidence_seq=1, generation=1)

    replayed = list(inbox.replay())
    assert [seq for seq, _event in replayed] == [1, 2]


def test_count_survives_reopening_the_same_file(tmp_path: Path) -> None:
    scheme = get_scheme(EV_L1_PROVISIONAL_VERSION)
    path = tmp_path / "reopen-inbox.sqlite3"
    first = SqliteEventInbox(path, scheme=scheme)
    first.enqueue(fx.decision_tick_event(seq=1))
    first.enqueue(fx.decision_tick_event(seq=2))
    first.close()

    reopened = SqliteEventInbox(path, scheme=scheme)
    assert reopened.count == 2
    reopened.close()
