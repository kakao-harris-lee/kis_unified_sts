"""The scheduler attaches the position BEFORE the event is enqueued (plan P4 §2 D1, stage S2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from tos.dsl import ContextValueView, PositionContext, flat_position_context
from tos.engine import TimeAdmissionInputs
from tos.time import SessionContext
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.marketfeed.ports import (
    AbsentPositionContext,
    PositionContextReason,
    TickOutcome,
)
from tos_runtime.marketfeed.scheduler import (
    POSITION_CONTEXT_ABSENT_KIND,
    TickScheduler,
)
from tos_runtime.marketfeed.store import SqliteSnapshotStore

from ._fixtures import BAR_ONE_AS_OF, INSTRUMENT, SCHEME, loaded_policy, observation

_ACCOUNT = "acct-position-context"
_INSTRUMENT_CLASS = "krx-stock"
_NOW_MS = BAR_ONE_AS_OF + 100
_BAR_MS = 60_000


class _SequencedIntake:
    """An intake that yields one newer observation per poll, then nothing."""

    def __init__(self, count: int) -> None:
        self.polls = 0
        self._count = count

    def poll(self, *, instrument: str, after_as_of_ms: int | None) -> tuple[Any, ...]:
        del instrument, after_as_of_ms
        self.polls += 1
        if self.polls > self._count:
            return ()
        return (
            observation(
                raw_event_id=f"raw-{self.polls}",
                as_of_ms=BAR_ONE_AS_OF + (self.polls - 1) * _BAR_MS,
            ),
        )


class _FixedPositionContext:
    """A position source that answers with a fixed verdict and counts its calls."""

    def __init__(self, context: PositionContext | AbsentPositionContext) -> None:
        self._context = context
        self.calls = 0
        self.views: list[ContextValueView | None] = []

    def read(
        self, view: ContextValueView | None
    ) -> PositionContext | AbsentPositionContext:
        self.calls += 1
        self.views.append(view)
        return self._context


class _SequencedPositionContext:
    """A position source that walks a fixed list of readings, one per tick."""

    def __init__(self, *readings: PositionContext | AbsentPositionContext) -> None:
        self._readings = list(readings)
        self.calls = 0

    def read(
        self, view: ContextValueView | None
    ) -> PositionContext | AbsentPositionContext:
        del view
        reading = self._readings[self.calls]
        self.calls += 1
        return reading


def _absent(
    reason: PositionContextReason, *, bound_refusal: str | None = None
) -> AbsentPositionContext:
    return AbsentPositionContext(
        reason=reason, bound_refusal=bound_refusal, as_of=BAR_ONE_AS_OF
    )


def _flat() -> PositionContext:
    return flat_position_context(
        source_ref=f"scope:{_ACCOUNT}::{INSTRUMENT}@evidence:7",
        as_of=BAR_ONE_AS_OF,
        scheme=SCHEME,
    )


def _scheduler(
    tmp_path: Path,
    *,
    name: str,
    position_context: Any = None,
    ticks: int = 1,
    poll_interval_ms: int = 400,
) -> tuple[TickScheduler, SqliteEventInbox, MagicMock]:
    """A real scheduler over real snapshot/inbox stores — only the clock seams are doubles."""
    root = tmp_path / name
    root.mkdir()
    inbox = SqliteEventInbox(root / "inbox.sqlite3", scheme=SCHEME)
    time_service = MagicMock()
    time_service.wall_clock_now.return_value = _NOW_MS
    session_owner = MagicMock()
    session_owner.session_context.return_value = SessionContext(
        phase="CONTINUOUS", is_open=True
    )
    time_projection = MagicMock()
    time_projection.return_value = TimeAdmissionInputs()
    evidence_store = MagicMock()
    scheduler = TickScheduler(
        instruments=(INSTRUMENT,),
        instrument_class=_INSTRUMENT_CLASS,
        account=_ACCOUNT,
        direction="LONG",
        quantity_basis="RISK",
        unit="SHARES",
        policy=loaded_policy(root),
        scheme=SCHEME,
        intake=_SequencedIntake(ticks),
        store=SqliteSnapshotStore(root / "marketfeed.sqlite3"),
        time_projection=time_projection,
        time_service=time_service,
        session_owner=session_owner,
        driver=None,
        inbox=inbox,
        evidence_store=evidence_store,
        poll_interval_ms=poll_interval_ms,
        position_context=position_context,
    )
    return scheduler, inbox, evidence_store


def _stored(inbox: SqliteEventInbox) -> tuple[str, str]:
    """``(event_id, payload_json)`` of the ONE row this inbox admitted."""
    rows = inbox._conn.execute(  # noqa: SLF001
        "SELECT event_id, payload_json FROM events ORDER BY seq"
    ).fetchall()
    assert len(rows) == 1, rows
    return rows[0][0], rows[0][1]


def _appended(evidence_store: MagicMock, kind: str) -> list[dict[str, Any]]:
    """Every payload this scheduler appended under ``kind``, in call order."""
    return [
        call.args[0]
        for call in evidence_store.append.call_args_list
        if call.kwargs.get("kind") == kind
    ]


def _appended_kinds(evidence_store: MagicMock) -> list[str]:
    return [call.kwargs.get("kind") for call in evidence_store.append.call_args_list]


def test_an_enabled_tick_stores_the_position_inside_the_inbox_event(
    tmp_path: Path,
) -> None:
    """D-a: the context is read before ``enqueue`` and travels in the payload boot replays."""
    source = _FixedPositionContext(_flat())
    scheduler, inbox, evidence_store = _scheduler(
        tmp_path, name="on", position_context=source
    )
    try:
        result = scheduler.tick_once()
        assert result.outcome is TickOutcome.TICKED
        assert result.position_context is not None
        _event_id, payload_json = _stored(inbox)
        stored = json.loads(payload_json)["decision_tick"]["position_context"]
        assert stored["side"] == "FLAT"
        assert stored["canonical_digest"] == result.position_context.canonical_digest
        assert source.calls == 1
        assert source.views == [result.value_view]
        assert _appended(evidence_store, POSITION_CONTEXT_ABSENT_KIND) == []
    finally:
        inbox.close()


def test_a_source_that_proves_nothing_leaves_the_key_out_of_the_stored_event(
    tmp_path: Path,
) -> None:
    """An UNKNOWN position is an ABSENT namespace — the serialized payload has no such key."""
    source = _FixedPositionContext(_absent(PositionContextReason.QUANTITY_UNSETTLED))
    scheduler, inbox, _evidence_store = _scheduler(
        tmp_path, name="unknown", position_context=source
    )
    try:
        result = scheduler.tick_once()
        assert result.outcome is TickOutcome.TICKED
        assert result.position_context is None
        _event_id, payload_json = _stored(inbox)
        assert "position_context" not in json.loads(payload_json)["decision_tick"]
        assert source.calls == 1
    finally:
        inbox.close()


def test_an_unwired_tick_stores_exactly_what_it_stored_before_the_field_existed(
    tmp_path: Path,
) -> None:
    """Off must be byte-identical: same stored JSON and same event id as the UNKNOWN path."""
    off_scheduler, off_inbox, off_store = _scheduler(tmp_path, name="off")
    unknown_source = _FixedPositionContext(
        _absent(PositionContextReason.QUANTITY_UNSETTLED)
    )
    on_scheduler, on_inbox, _on_store = _scheduler(
        tmp_path, name="off-control", position_context=unknown_source
    )
    try:
        assert off_scheduler.tick_once().outcome is TickOutcome.TICKED
        assert on_scheduler.tick_once().outcome is TickOutcome.TICKED
        assert _stored(off_inbox) == _stored(on_inbox)
        assert "position_context" not in _stored(off_inbox)[1]
        assert _appended(off_store, POSITION_CONTEXT_ABSENT_KIND) == []
        assert _appended_kinds(off_store) == ["MARKETFEED_QUEUED_UNTIL_RECOVERY"]
    finally:
        off_inbox.close()
        on_inbox.close()


def test_an_unwired_tick_never_reads_the_position_at_all(tmp_path: Path) -> None:
    """The reader is not merely ignored when off — it is never called (no evidence scan)."""
    source = _FixedPositionContext(_flat())
    scheduler, inbox, _evidence_store = _scheduler(
        tmp_path, name="never", position_context=None
    )
    try:
        assert scheduler.tick_once().outcome is TickOutcome.TICKED
        assert source.calls == 0
    finally:
        inbox.close()


def test_one_row_per_reason_change_never_one_per_tick(tmp_path: Path) -> None:
    """A steady absence is recorded ONCE; the recovery back to present is its own row."""
    unsettled = _absent(PositionContextReason.QUANTITY_UNSETTLED)
    source = _SequencedPositionContext(unsettled, unsettled, unsettled, _flat())
    scheduler, inbox, evidence_store = _scheduler(
        tmp_path,
        name="streak",
        position_context=source,
        ticks=4,
        poll_interval_ms=0,
    )
    try:
        for _ in range(4):
            assert scheduler.tick_once().outcome is TickOutcome.TICKED
        rows = _appended(evidence_store, POSITION_CONTEXT_ABSENT_KIND)
        assert [row["reason"] for row in rows] == ["QUANTITY_UNSETTLED", "PRESENT"]
        assert rows[0] == {
            "instrument": INSTRUMENT,
            "reason": "QUANTITY_UNSETTLED",
            "bound_refusal": None,
            "as_of_ms": BAR_ONE_AS_OF,
        }
    finally:
        inbox.close()


def test_a_different_bound_refusal_is_its_own_row(tmp_path: Path) -> None:
    """A send in flight and an unreadable store must not look like the same absence."""
    source = _SequencedPositionContext(
        _absent(
            PositionContextReason.BOUND_REFUSED, bound_refusal="HISTORY_READ_FAILED"
        ),
        _absent(
            PositionContextReason.BOUND_REFUSED, bound_refusal="HISTORY_READ_FAILED"
        ),
        _absent(PositionContextReason.BOUND_REFUSED, bound_refusal="SCOPE_READ_FAILED"),
    )
    scheduler, inbox, evidence_store = _scheduler(
        tmp_path,
        name="refusals",
        position_context=source,
        ticks=3,
        poll_interval_ms=0,
    )
    try:
        for _ in range(3):
            assert scheduler.tick_once().outcome is TickOutcome.TICKED
        rows = _appended(evidence_store, POSITION_CONTEXT_ABSENT_KIND)
        assert [row["bound_refusal"] for row in rows] == [
            "HISTORY_READ_FAILED",
            "SCOPE_READ_FAILED",
        ]
        assert {row["reason"] for row in rows} == {"BOUND_REFUSED"}
    finally:
        inbox.close()


def test_a_healthy_tree_records_nothing_at_all(tmp_path: Path) -> None:
    """PRESENT is the starting reason, so an enabled tree that never loses it stays silent."""
    source = _SequencedPositionContext(_flat(), _flat())
    scheduler, inbox, evidence_store = _scheduler(
        tmp_path,
        name="healthy",
        position_context=source,
        ticks=2,
        poll_interval_ms=0,
    )
    try:
        for _ in range(2):
            assert scheduler.tick_once().outcome is TickOutcome.TICKED
        assert _appended(evidence_store, POSITION_CONTEXT_ABSENT_KIND) == []
    finally:
        inbox.close()
