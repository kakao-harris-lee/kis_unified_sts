from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from shared.backtest.adapter import BacktestStrategyAdapter


class _CaptureExitStrategy:
    name = "capture_exit"
    required_indicators = ("atr", "volume_velocity")

    def __init__(self) -> None:
        self.exit_context = None

    async def check_exit(self, context):
        self.exit_context = context
        return False, None


def test_backtest_exit_merges_resolved_indicators_into_market_data():
    strategy = _CaptureExitStrategy()
    adapter = BacktestStrategyAdapter(
        strategy,
        {
            "strategy": {
                "entry": {"params": {}},
                "exit": {"type": "atr_dynamic", "params": {}},
            }
        },
    )
    adapter._indicator_resolver = MagicMock()
    adapter._indicator_resolver.collect_exit_indicators.return_value = {
        "atr": 1250.0,
        "volume_velocity": -10_000.0,
    }
    adapter.set_position(
        {
            "code": "005930",
            "side": "BUY",
            "entry_price": 70_000.0,
            "quantity": 10,
            "highest_price": 71_000.0,
            "lowest_price": 69_500.0,
            "entry_time": datetime(2026, 5, 15, 9, 30),
        }
    )

    adapter.check_exit(
        {
            "datetime": datetime(2026, 5, 15, 10, 0),
            "code": "005930",
            "open": 70_500.0,
            "high": 71_000.0,
            "low": 70_000.0,
            "close": 70_800.0,
            "volume": 100_000,
        }
    )

    assert strategy.exit_context is not None
    assert strategy.exit_context.indicators["atr"] == 1250.0
    assert strategy.exit_context.market_data["atr"] == 1250.0
    assert strategy.exit_context.market_data["volume_velocity"] == -10_000.0
    assert strategy.exit_context.market_data["close"] == 70_800.0
