"""PositionTracker runtime-ledger persistence tests."""

from datetime import datetime, timedelta

import pytest

from services.trading.position_tracker import PositionTracker, PositionTrackerConfig
from shared.models.position import Position, PositionSide, PositionState
from shared.storage.runtime_ledger import SQLiteRuntimeLedger


def _tracker_with_sqlite_ledger(
    tmp_path,
) -> tuple[PositionTracker, SQLiteRuntimeLedger]:
    ledger = SQLiteRuntimeLedger(tmp_path / "runtime.db")
    tracker = PositionTracker(
        config=PositionTrackerConfig(
            asset_class="stock",
            runtime_ledger_backend="sqlite",
            flush_interval_seconds=0,
        ),
        runtime_ledger=ledger,
    )
    return tracker, ledger


def _closed_position() -> Position:
    entry_time = datetime(2026, 6, 3, 9, 0, 0)
    pos = Position(
        id="pos-001",
        code="005930",
        name="Samsung",
        side=PositionSide.LONG,
        quantity=10,
        entry_price=71000.0,
        entry_time=entry_time,
        current_price=72000.0,
        highest_price=72100.0,
        lowest_price=70900.0,
        state=PositionState.MAXIMIZE,
        strategy="bb_reversion",
        fee_rate=0.0015,
        metadata={"commission": 100.0, "slippage": 50.0},
    )
    pos.exit_price = 72000.0
    pos.exit_time = entry_time + timedelta(hours=1)
    pos.exit_reason = "signal_exit"
    return pos


@pytest.mark.asyncio
async def test_save_and_load_open_positions_from_runtime_ledger(tmp_path):
    tracker, ledger = _tracker_with_sqlite_ledger(tmp_path)

    position = tracker.add_position(
        code="005930",
        name="Samsung",
        entry_price=71000.0,
        quantity=10,
        strategy="bb_reversion",
        fee_rate=0.0015,
    )
    assert position is not None

    saved = await tracker.save_to_db()
    assert saved == 1

    recovered = PositionTracker(
        config=PositionTrackerConfig(
            asset_class="stock",
            runtime_ledger_backend="sqlite",
            flush_interval_seconds=0,
        ),
        runtime_ledger=ledger,
    )
    loaded = await recovered.load_from_db()

    assert loaded == 1
    loaded_pos = recovered.get_position(position.id)
    assert loaded_pos is not None
    assert loaded_pos.code == "005930"
    assert loaded_pos.side == PositionSide.LONG
    assert loaded_pos.fee_rate == 0.0015
    assert loaded_pos.execution_venue == "KRX"


@pytest.mark.asyncio
async def test_closed_position_snapshot_and_stock_trade_use_runtime_ledger(tmp_path):
    tracker, ledger = _tracker_with_sqlite_ledger(tmp_path)
    position = _closed_position()

    assert await tracker.save_closed_to_db(position) is True
    assert await tracker.save_stock_trade_to_db(position) is True

    open_positions = ledger.load_open_positions("stock")
    trades = ledger.query_trades({"asset_class": "stock", "code": "005930"})

    assert open_positions == []
    assert len(trades) == 1
    assert trades[0]["id"] == "pos-001"
    assert trades[0]["pnl"] == 10000.0
    assert trades[0]["pnl_pct"] == pytest.approx(1.40845, rel=1e-4)
    assert trades[0]["hold_seconds"] == 3600
    assert trades[0]["payload"]["commission"] == 100.0
    assert trades[0]["track_id"] == "B"  # stock trade → portfolio track B


@pytest.mark.asyncio
async def test_futures_trade_tagged_track_c_in_runtime_ledger(tmp_path):
    tracker, ledger = _futures_tracker_with_ledger(tmp_path)
    position = _closed_position()

    assert await tracker.save_futures_trade_to_db(position, "futures") is True

    trades = ledger.query_trades({"track_id": "C"})
    assert len(trades) == 1
    assert trades[0]["id"] == "pos-001"
    assert trades[0]["asset_class"] == "futures"
    # Track filter isolates C from B rows (3B per-track PnL contract).
    assert ledger.query_trades({"track_id": "B"}) == []


@pytest.mark.asyncio
async def test_runtime_ledger_backend_does_not_fill_legacy_batches(tmp_path):
    tracker, _ledger = _tracker_with_sqlite_ledger(tmp_path)
    position = _closed_position()

    assert await tracker.save_closed_to_db(position) is True
    assert await tracker.save_stock_trade_to_db(position) is True

    assert tracker._pending_swing_positions == []
    assert tracker._pending_stock_trades == []


# --- Durable open-position persistence (SQLite) ---


def _futures_tracker_with_ledger(
    tmp_path,
) -> tuple[PositionTracker, SQLiteRuntimeLedger]:
    """Futures tracker wired to a real SQLite runtime ledger."""
    ledger = SQLiteRuntimeLedger(tmp_path / "runtime.db")
    tracker = PositionTracker(
        config=PositionTrackerConfig(
            asset_class="futures",
            runtime_ledger_backend="sqlite",
            flush_interval_seconds=0,
        ),
        runtime_ledger=ledger,
    )
    return tracker, ledger


@pytest.mark.asyncio
async def test_open_position_written_to_position_snapshots(tmp_path):
    """(a) Open positions are durably written to position_snapshots."""
    tracker, ledger = _futures_tracker_with_ledger(tmp_path)
    position = tracker.add_position(
        code="101S6000",
        name="KOSPI200 F",
        entry_price=350.0,
        quantity=1,
        strategy="setup_a_gap_reversion",
        side=PositionSide.LONG,
    )
    assert position is not None

    saved = await tracker.save_to_db()
    assert saved == 1

    open_rows = ledger.load_open_positions("futures")
    assert len(open_rows) == 1
    assert open_rows[0]["position_id"] == position.id
    assert open_rows[0]["is_open"] == 1
    assert open_rows[0]["symbol"] == "101S6000"


@pytest.mark.asyncio
async def test_repeated_open_snapshots_upsert_single_row(tmp_path):
    """Idempotent: repeated open mirrors UPSERT one row (no duplicate spam)."""
    import sqlite3

    tracker, ledger = _futures_tracker_with_ledger(tmp_path)
    position = tracker.add_position(
        code="101S6000",
        name="KOSPI200 F",
        entry_price=350.0,
        quantity=1,
        strategy="setup_a_gap_reversion",
        side=PositionSide.LONG,
    )
    assert position is not None

    # Simulate three auto-flush mirror cycles with a moving current price.
    for tick in range(3):
        position.current_price = 350.0 + tick
        assert await tracker.save_to_db() == 1

    conn = sqlite3.connect(tmp_path / "runtime.db")
    try:
        total, open_count = conn.execute(
            "SELECT count(*), sum(is_open) FROM position_snapshots"
        ).fetchone()
    finally:
        conn.close()

    assert total == 1, "open snapshots must UPSERT a single row per position"
    assert open_count == 1


@pytest.mark.asyncio
async def test_recovery_loads_from_sqlite_when_redis_empty(tmp_path):
    """(b) A fresh tracker (Redis empty) recovers open positions from SQLite."""
    tracker, ledger = _futures_tracker_with_ledger(tmp_path)
    position = tracker.add_position(
        code="101S6000",
        name="KOSPI200 F",
        entry_price=350.0,
        quantity=2,
        strategy="setup_c_event_reaction",
        side=PositionSide.SHORT,
    )
    assert position is not None
    assert await tracker.save_to_db() == 1

    # New tracker process — nothing in memory ("Redis empty"), only SQLite.
    recovered = PositionTracker(
        config=PositionTrackerConfig(
            asset_class="futures",
            runtime_ledger_backend="sqlite",
            flush_interval_seconds=0,
        ),
        runtime_ledger=ledger,
    )
    loaded = await recovered.load_from_db()

    assert loaded == 1
    rec_pos = recovered.get_position(position.id)
    assert rec_pos is not None
    assert rec_pos.code == "101S6000"
    assert rec_pos.side == PositionSide.SHORT
    assert rec_pos.quantity == 2


@pytest.mark.asyncio
async def test_closed_position_not_re_recovered(tmp_path):
    """(c) A closed position is superseded in place and never recovered as open."""
    from datetime import datetime as _dt

    tracker, ledger = _futures_tracker_with_ledger(tmp_path)
    position = tracker.add_position(
        code="101S6000",
        name="KOSPI200 F",
        entry_price=350.0,
        quantity=1,
        strategy="setup_a_gap_reversion",
        side=PositionSide.LONG,
    )
    assert position is not None

    # Mirror the open snapshot, then close it (close snapshot supersedes).
    assert await tracker.save_to_db() == 1
    position.exit_price = 360.0
    position.exit_time = _dt.now()
    position.exit_reason = "take_profit"
    assert await tracker.save_closed_to_db(position) is True

    # load_open_positions filters is_open=1, so the closed row is excluded.
    assert ledger.load_open_positions("futures") == []

    recovered = PositionTracker(
        config=PositionTrackerConfig(
            asset_class="futures",
            runtime_ledger_backend="sqlite",
            flush_interval_seconds=0,
        ),
        runtime_ledger=ledger,
    )
    assert await recovered.load_from_db() == 0
    assert recovered.get_position(position.id) is None


@pytest.mark.asyncio
async def test_no_duplicate_when_present_in_redis_and_sqlite(tmp_path):
    """(d) A position already in memory (Redis) is not double-added from SQLite."""
    tracker, ledger = _futures_tracker_with_ledger(tmp_path)
    position = tracker.add_position(
        code="101S6000",
        name="KOSPI200 F",
        entry_price=350.0,
        quantity=1,
        strategy="setup_a_gap_reversion",
        side=PositionSide.LONG,
    )
    assert position is not None
    assert await tracker.save_to_db() == 1

    # Simulate a process where Redis recovery already restored this position
    # into a fresh tracker; the SQLite fallback must not duplicate it.
    target = PositionTracker(
        config=PositionTrackerConfig(
            asset_class="futures",
            runtime_ledger_backend="sqlite",
            flush_interval_seconds=0,
        ),
        runtime_ledger=ledger,
    )
    # Pre-seed as if recovered from Redis.
    assert target.add_recovered_position(position) is True
    assert target.position_count == 1

    # SQLite fallback finds the same id already tracked -> loads 0 new.
    loaded = await target.load_from_db()
    assert loaded == 0
    assert target.position_count == 1
