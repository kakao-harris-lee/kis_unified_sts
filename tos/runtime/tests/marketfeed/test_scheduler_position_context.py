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
from tos_runtime.marketfeed.ports import TickOutcome
from tos_runtime.marketfeed.scheduler import TickScheduler
from tos_runtime.marketfeed.store import SqliteSnapshotStore

from ._fixtures import BAR_ONE_AS_OF, INSTRUMENT, SCHEME, loaded_policy, observation

_ACCOUNT = "acct-position-context"
_INSTRUMENT_CLASS = "krx-stock"
_NOW_MS = BAR_ONE_AS_OF + 100


class _OneObservationIntake:
    """An intake that yields the one fixture observation, then nothing."""

    def __init__(self) -> None:
        self.polls = 0

    def poll(self, *, instrument: str, after_as_of_ms: int | None) -> tuple[Any, ...]:
        del instrument, after_as_of_ms
        self.polls += 1
        return (observation(),) if self.polls == 1 else ()


class _FixedPositionContext:
    """A position source that answers with a fixed verdict and counts its calls."""

    def __init__(self, context: PositionContext | None) -> None:
        self._context = context
        self.calls = 0
        self.views: list[ContextValueView | None] = []

    def read(self, view: ContextValueView | None) -> PositionContext | None:
        self.calls += 1
        self.views.append(view)
        return self._context


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
) -> tuple[TickScheduler, SqliteEventInbox]:
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
    scheduler = TickScheduler(
        instruments=(INSTRUMENT,),
        instrument_class=_INSTRUMENT_CLASS,
        account=_ACCOUNT,
        direction="LONG",
        quantity_basis="RISK",
        unit="SHARES",
        policy=loaded_policy(root),
        scheme=SCHEME,
        intake=_OneObservationIntake(),
        store=SqliteSnapshotStore(root / "marketfeed.sqlite3"),
        time_projection=time_projection,
        time_service=time_service,
        session_owner=session_owner,
        driver=None,
        inbox=inbox,
        evidence_store=MagicMock(),
        poll_interval_ms=400,
        position_context=position_context,
    )
    return scheduler, inbox


def _stored(inbox: SqliteEventInbox) -> tuple[str, str]:
    """``(event_id, payload_json)`` of the ONE row this inbox admitted."""
    rows = inbox._conn.execute(
        "SELECT event_id, payload_json FROM events ORDER BY seq"
    ).fetchall()
    assert len(rows) == 1, rows
    return rows[0][0], rows[0][1]


def test_an_enabled_tick_stores_the_position_inside_the_inbox_event(
    tmp_path: Path,
) -> None:
    """D-a: the context is read before ``enqueue`` and travels in the payload boot replays."""
    source = _FixedPositionContext(_flat())
    scheduler, inbox = _scheduler(tmp_path, name="on", position_context=source)
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
    finally:
        inbox.close()


def test_a_source_that_proves_nothing_leaves_the_key_out_of_the_stored_event(
    tmp_path: Path,
) -> None:
    """An UNKNOWN position is an ABSENT namespace — the serialized payload has no such key."""
    source = _FixedPositionContext(None)
    scheduler, inbox = _scheduler(tmp_path, name="unknown", position_context=source)
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
    off_scheduler, off_inbox = _scheduler(tmp_path, name="off")
    unknown_source = _FixedPositionContext(None)
    on_scheduler, on_inbox = _scheduler(
        tmp_path, name="off-control", position_context=unknown_source
    )
    try:
        assert off_scheduler.tick_once().outcome is TickOutcome.TICKED
        assert on_scheduler.tick_once().outcome is TickOutcome.TICKED
        assert _stored(off_inbox) == _stored(on_inbox)
        assert "position_context" not in _stored(off_inbox)[1]
    finally:
        off_inbox.close()
        on_inbox.close()


def test_an_unwired_tick_never_reads_the_position_at_all(tmp_path: Path) -> None:
    """The reader is not merely ignored when off — it is never called (no evidence scan)."""
    source = _FixedPositionContext(_flat())
    scheduler, inbox = _scheduler(tmp_path, name="never", position_context=None)
    try:
        assert scheduler.tick_once().outcome is TickOutcome.TICKED
        assert source.calls == 0
    finally:
        inbox.close()
