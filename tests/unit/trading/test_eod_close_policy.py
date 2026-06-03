"""주식 EOD 전량 청산 차단 회귀 테스트.

CLAUDE.md: "EOD 전량 청산 금지. Intraday trading이 아님. 상승 여력 종목 보유 유지."
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from services.trading.orchestrator import TradingConfig, TradingOrchestrator
from shared.models.position import Position, PositionSide


def _make_open_position(code: str, strategy: str) -> Position:
    return Position(
        id=f"p-{code}",
        code=code,
        name=f"NAME-{code}",
        strategy=strategy,
        side=PositionSide.LONG,
        entry_price=100.0,
        quantity=10,
        entry_time=datetime(2026, 4, 14, 9, 15),
    )


class TestStockEODPolicy:
    @pytest.mark.asyncio
    async def test_stock_positions_not_force_closed_at_eod(self):
        """주식 orchestrator의 _close_intraday_positions는 no-op."""
        cfg = TradingConfig(
            asset_class="stock",
            strategy_name="momentum_breakout",
            initial_capital=100_000_000,
            order_amount_per_trade=1_000_000,
        )
        orch = TradingOrchestrator(cfg)

        tracker = MagicMock()
        tracker.positions = [
            _make_open_position("000720", "momentum_breakout"),
            _make_open_position("005930", "trend_pullback"),
        ]
        tracker.close_position = MagicMock()
        orch._position_tracker = tracker
        orch._state_publisher = None
        orch._sync_open_positions_metric = MagicMock()

        await orch._close_intraday_positions(
            {"000720": {"close": 100}, "005930": {"close": 100}}
        )

        tracker.close_position.assert_not_called()

    @pytest.mark.asyncio
    async def test_futures_non_rl_positions_still_force_closed(self):
        """선물은 기존과 동일하게 EOD 청산 유지.

        RL 전략은 자체 EOD 안전장치가 있으므로 이 메서드가 건드리지 않고,
        그 외 legacy intraday 전략만 청산 대상.
        """
        cfg = TradingConfig(
            asset_class="futures",
            strategy_name="setup_a_gap_reversion",
            initial_capital=10_000_000,
            order_amount_per_trade=1_000_000,
            symbols=["A05603"],
        )
        orch = TradingOrchestrator(cfg)

        tracker = MagicMock()
        non_rl_pos = _make_open_position("A05603", "legacy_intraday")
        tracker.positions = [non_rl_pos]
        closed_pos = _make_open_position("A05603", "legacy_intraday")
        closed_pos.exit_price = 100.0
        tracker.close_position = MagicMock(return_value=closed_pos)
        orch._position_tracker = tracker
        orch._state_publisher = None
        orch._sync_open_positions_metric = MagicMock()

        await orch._close_intraday_positions({"A05603": {"close": 100}})

        tracker.close_position.assert_called_once()

    @pytest.mark.asyncio
    async def test_futures_rl_positions_not_force_closed(self):
        """선물 RL 전략 포지션은 자체 EOD 안전장치가 있으므로 이 메서드에서 청산 금지."""
        cfg = TradingConfig(
            asset_class="futures",
            strategy_name="setup_a_gap_reversion",
            initial_capital=10_000_000,
            order_amount_per_trade=1_000_000,
            symbols=["A05603"],
        )
        orch = TradingOrchestrator(cfg)

        tracker = MagicMock()
        rl_pos = _make_open_position("A05603", "setup_a_gap_reversion")
        tracker.positions = [rl_pos]
        tracker.close_position = MagicMock()
        orch._position_tracker = tracker
        orch._state_publisher = None
        orch._sync_open_positions_metric = MagicMock()

        await orch._close_intraday_positions({"A05603": {"close": 100}})

        tracker.close_position.assert_not_called()
