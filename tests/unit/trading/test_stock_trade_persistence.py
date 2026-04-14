"""PositionTracker.save_stock_trade_to_db — 주식 전용 적재 경로 회귀 테스트."""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.trading.position_tracker import PositionTracker, PositionTrackerConfig
from shared.models.position import Position, PositionSide, PositionState


def _make_closed_stock_position(
    code: str = "000720",
    entry_price: float = 100000.0,
    exit_price: float = 98500.0,
    quantity: int = 10,
    strategy: str = "momentum_breakout",
) -> Position:
    entry_time = datetime(2026, 4, 10, 9, 15, 0)
    exit_time = entry_time + timedelta(minutes=30)
    pos = Position(
        id="test-stk-1",
        code=code,
        name="TEST",
        strategy=strategy,
        side=PositionSide.LONG,
        entry_price=entry_price,
        quantity=quantity,
        entry_time=entry_time,
        state=PositionState.MAXIMIZE,
        execution_venue="KRX",
    )
    pos.exit_price = exit_price
    pos.exit_time = exit_time
    pos.exit_reason = "rule_based_exit"
    pos.current_price = exit_price
    return pos


@pytest.mark.asyncio
async def test_save_stock_trade_appends_to_buffer():
    """save_stock_trade_to_db 호출이 _pending_stock_trades 버퍼에 row를 추가해야 한다."""
    config = PositionTrackerConfig(asset_class="stock", batch_size=50)
    tracker = PositionTracker(config=config)
    tracker._get_db_client = MagicMock(return_value=(MagicMock(), "market"))

    position = _make_closed_stock_position()
    await tracker.save_stock_trade_to_db(position)

    assert len(tracker._pending_stock_trades) == 1
    row = tracker._pending_stock_trades[0]
    # Row: (id, code, name, side, strategy, execution_venue,
    #       entry_date, entry_price, exit_date, exit_price, quantity,
    #       pnl, pnl_pct, commission, slippage, hold_seconds,
    #       exit_reason, exit_state, metadata_json)
    assert row[0] == "test-stk-1"
    assert row[1] == "000720"
    assert row[4] == "momentum_breakout"
    assert row[11] == pytest.approx(-15000.0)  # (98500-100000)*10
    assert row[15] == 1800  # 30 min


@pytest.mark.asyncio
async def test_save_stock_trade_flushes_when_batch_full():
    """버퍼가 batch_size에 도달하면 _flush_stock_trades_batch 호출."""
    config = PositionTrackerConfig(asset_class="stock", batch_size=2)
    tracker = PositionTracker(config=config)
    tracker._get_db_client = MagicMock(return_value=(MagicMock(), "market"))
    tracker._flush_stock_trades_batch = AsyncMock()

    for i in range(2):
        pos = _make_closed_stock_position(code=f"00072{i}")
        await tracker.save_stock_trade_to_db(pos)

    tracker._flush_stock_trades_batch.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_stock_trade_rejects_futures_asset_class():
    """asset_class != 'stock'인 tracker에서 stock 저장 호출 시 조용히 no-op + warn."""
    config = PositionTrackerConfig(asset_class="futures", batch_size=50)
    tracker = PositionTracker(config=config)

    position = _make_closed_stock_position()
    result = await tracker.save_stock_trade_to_db(position)

    assert result is False
    assert tracker._pending_stock_trades == []
