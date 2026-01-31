from __future__ import annotations

import pytest

from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator, ExitSignalGenerator, PositionSizer, TradingStrategy
from services.trading.strategy_manager import StrategyManager, StrategyManagerConfig


class _DummyEntry(EntrySignalGenerator[dict]):
    @property
    def name(self) -> str:
        return "dummy_entry_component"

    @property
    def required_indicators(self) -> list[str]:
        return []

    def _validate_config(self):
        return

    async def generate(self, context: EntryContext):
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

    async def should_exit(self, context):
        return (False, None)

    async def scan_positions(self, positions, market_data, market_state=None):
        return []


class _DummySizer(PositionSizer[dict]):
    def calculate(self, signal, account_balance, current_positions):
        return 1


@pytest.mark.asyncio
async def test_strategy_manager_overwrites_signal_strategy_to_trading_strategy_name():
    # Provide a non-existent strategy name to avoid auto-loading all built-in strategies.
    sm = StrategyManager(
        asset_class="stock",
        strategy_names=["__does_not_exist__"],
        config=StrategyManagerConfig(),
    )

    strategy = TradingStrategy(
        name="my_trading_strategy",
        entry=_DummyEntry({}),
        exit=_DummyExit({}),
        position_sizer=_DummySizer({}),
    )
    sm.add_strategy(strategy)

    ctx = EntryContext(market_data={"code": "000000", "close": 100.0})
    signals = await sm.check_entries(ctx)

    assert len(signals) == 1
    sig = signals[0]
    assert sig.strategy == "my_trading_strategy"
    assert sig.metadata.get("entry_component") == "component_name"
