from __future__ import annotations

import pytest

from services.trading.strategy_manager import StrategyManager, StrategyManagerConfig
from shared.models.signal import Signal, SignalType
from shared.strategy.base import (
    EntryContext,
    EntrySignalGenerator,
    ExitSignalGenerator,
    PositionSizer,
    TradingStrategy,
)


class _DummyEntry(EntrySignalGenerator[dict]):
    @property
    def name(self) -> str:
        return "dummy_entry_component"

    @property
    def required_indicators(self) -> list[str]:
        return []

    def _validate_config(self):
        return

    async def generate(self, _context: EntryContext):
        # Intentionally return a different "strategy" name to ensure StrategyManager rewrites it.
        return Signal(
            code="000000",
            name="DUMMY",
            signal_type=SignalType.ENTRY,
            strategy="component_name",
            price=100.0,
            confidence=0.9,
        )


class _DummyExit(ExitSignalGenerator[dict]):
    @property
    def name(self) -> str:
        return "dummy_exit"

    def _validate_config(self):
        return

    async def should_exit(self, _context):
        return (False, None)

    async def scan_positions(self, _positions, _market_data, _market_state=None):
        return []


class _DummySizer(PositionSizer[dict]):
    def calculate(self, _signal, _account_balance, _current_positions):
        return 1


@pytest.mark.asyncio
async def test_strategy_manager_overwrites_signal_strategy_to_trading_strategy_name():
    # Provide no strategy_names to avoid auto-loading from disk (avoids ConfigNotFoundError).
    # Disable cost filter to avoid ATR/price validation rejecting the test signal.
    sm = StrategyManager(
        asset_class="stock",
        strategy_names=[],
        config=StrategyManagerConfig(cost_filter_enabled=False),
    )

    strategy = TradingStrategy(
        name="my_trading_strategy",
        entry=_DummyEntry({}),
        exit=_DummyExit({}),
        position_sizer=_DummySizer({}),
    )
    sm.add_strategy(strategy)

    # Market data must be keyed by symbol for cost filter to find price
    ctx = EntryContext(market_data={"000000": {"code": "000000", "close": 100.0}})
    signals = await sm.check_entries(ctx)

    assert len(signals) == 1
    sig = signals[0]
    assert sig.strategy == "my_trading_strategy"
    assert sig.metadata.get("entry_component") == "component_name"
