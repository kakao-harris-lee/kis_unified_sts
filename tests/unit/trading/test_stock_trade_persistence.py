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
    hold_minutes: int = 30,
) -> Position:
    entry_time = datetime(2026, 4, 10, 9, 15, 0)
    exit_time = entry_time + timedelta(minutes=hold_minutes)
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
async def test_save_stock_trade_rejects_negative_hold_window():
    """exit_time이 entry_time보다 빠른 불가능한 거래는 적재하지 않는다."""
    config = PositionTrackerConfig(asset_class="stock", batch_size=50)
    tracker = PositionTracker(config=config)
    tracker._get_db_client = MagicMock(return_value=(MagicMock(), "market"))

    position = _make_closed_stock_position(hold_minutes=-30)
    result = await tracker.save_stock_trade_to_db(position)

    assert result is False
    assert tracker._pending_stock_trades == []


@pytest.mark.asyncio
async def test_save_stock_trade_rejects_futures_asset_class():
    """asset_class != 'stock'인 tracker에서 stock 저장 호출 시 조용히 no-op + warn."""
    config = PositionTrackerConfig(asset_class="futures", batch_size=50)
    tracker = PositionTracker(config=config)

    position = _make_closed_stock_position()
    result = await tracker.save_stock_trade_to_db(position)

    assert result is False
    assert tracker._pending_stock_trades == []


class TestOrchestratorRouting:
    """Asset-class routing: stock → save_stock_trade_to_db, futures → save_futures_trade_to_db."""

    @pytest.mark.asyncio
    async def test_stock_orchestrator_routes_to_stock_trades(self):
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator

        cfg = TradingConfig(
            asset_class="stock",
            strategy_name="momentum_breakout",
            initial_capital=100_000_000.0,
            order_amount_per_trade=1_000_000.0,
        )
        orch = TradingOrchestrator(cfg)
        closed = _make_closed_stock_position(strategy="momentum_breakout")

        save_stock = AsyncMock(return_value=True)
        save_futures = AsyncMock(return_value=True)
        orch._position_tracker = MagicMock()
        orch._position_tracker.save_stock_trade_to_db = save_stock
        orch._position_tracker.save_futures_trade_to_db = save_futures

        await orch._persist_closed_position(closed, "momentum_breakout")

        save_stock.assert_awaited_once_with(closed)
        save_futures.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_futures_orchestrator_routes_to_futures_trades(self):
        from services.trading.orchestrator import TradingConfig, TradingOrchestrator

        cfg = TradingConfig(
            asset_class="futures",
            strategy_name="setup_a_gap_reversion",
            initial_capital=10_000_000.0,
            order_amount_per_trade=1_000_000.0,
            symbols=["A05603"],
        )
        orch = TradingOrchestrator(cfg)
        closed = _make_closed_stock_position(strategy="setup_a_gap_reversion")

        save_stock = AsyncMock(return_value=True)
        save_futures = AsyncMock(return_value=True)
        orch._position_tracker = MagicMock()
        orch._position_tracker.save_stock_trade_to_db = save_stock
        orch._position_tracker.save_futures_trade_to_db = save_futures

        await orch._persist_closed_position(closed, "setup_a_gap_reversion")

        save_futures.assert_awaited_once()
        save_stock.assert_not_awaited()
