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


@pytest.mark.asyncio
async def test_runtime_ledger_backend_does_not_fill_clickhouse_batches(tmp_path):
    tracker, _ledger = _tracker_with_sqlite_ledger(tmp_path)
    position = _closed_position()

    assert await tracker.save_closed_to_db(position) is True
    assert await tracker.save_stock_trade_to_db(position) is True

    assert tracker._pending_swing_positions == []
    assert tracker._pending_stock_trades == []
