"""Tests for SlippageModel integration with BacktestEngine.

Verifies that the backtest engine correctly uses the slippage model
for futures trading when configured.
"""

import pandas as pd
import pytest
from datetime import datetime, timedelta

from shared.backtest.engine import BacktestEngine, SignalType
from shared.backtest.config import BacktestConfig
from shared.execution.slippage_model import SlippageModel, SlippageModelConfig


class SimpleStrategy:
    """Test strategy that buys on first bar and holds."""

    name = "test_strategy"

    def __init__(self):
        self.position = None
        self.bar_count = 0

    def set_position(self, position):
        """Set current position state."""
        self.position = position

    def on_bar(self, bar):
        """Generate signal: buy on first bar, hold thereafter."""
        self.bar_count += 1
        if self.bar_count == 1:
            return SignalType.BUY
        return SignalType.HOLD


def create_test_data(num_bars=10, base_price=100.0):
    """Create test OHLCV data for backtesting."""
    start_date = datetime(2024, 1, 1, 9, 0)
    dates = [start_date + timedelta(minutes=i) for i in range(num_bars)]

    return pd.DataFrame(
        {
            "datetime": dates,
            "open": [base_price] * num_bars,
            "high": [base_price + 0.1] * num_bars,
            "low": [base_price - 0.1] * num_bars,
            "close": [base_price + (i * 0.05) for i in range(num_bars)],
            "volume": [1000] * num_bars,
        }
    )


def test_backtest_uses_slippage_model():
    """Test that BacktestEngine uses SlippageModel for futures entry when configured."""
    # Create slippage model with known parameters
    slippage_config = SlippageModelConfig(
        enabled=True,
        base_spread_bps=2.0,  # 2 bps base slippage
        depth_impact_factor=0.5,
        min_slippage_bps=1.0,
        max_slippage_bps=10.0,
    )
    slippage_model = SlippageModel(slippage_config)

    # Create backtest config for futures with slippage model
    config = BacktestConfig.futures(
        initial_capital=10_000_000,
        contracts=1,
        point_value=250_000,  # KOSPI200 futures
    )
    config.slippage_model = slippage_model

    # Create test data
    data = create_test_data(num_bars=5, base_price=100.0)

    # Run backtest
    strategy = SimpleStrategy()
    engine = BacktestEngine(strategy, config)
    result = engine.run(data)

    # Verify that a trade occurred
    assert result.total_trades == 1, "Expected exactly one trade (forced close at end)"

    # Get the trade
    trade = result.trades[0]

    # The entry price should be adjusted for slippage
    # With base_spread_bps=2.0 and no depth/spread penalties (using defaults),
    # expected slippage ~2 bps = 0.0002 = 0.02%
    # For BUY: entry_price should be higher than market price (100.0)
    market_price = 100.0
    expected_min_entry = market_price  # At minimum, entry price equals market
    expected_max_entry = market_price * 1.001  # At most, 10 bps (max_slippage_bps)

    assert (
        trade.entry_price >= expected_min_entry
    ), f"Entry price {trade.entry_price} should be >= market price {expected_min_entry}"
    assert (
        trade.entry_price <= expected_max_entry
    ), f"Entry price {trade.entry_price} should be <= max slippage price {expected_max_entry}"

    # Verify entry price is actually adjusted (not equal to market price)
    assert (
        trade.entry_price > market_price
    ), f"Entry price {trade.entry_price} should be higher than market {market_price} due to slippage"


def test_backtest_without_slippage_model():
    """Test that BacktestEngine works without slippage model (backward compatibility)."""
    # Create backtest config for futures WITHOUT slippage model
    config = BacktestConfig.futures(
        initial_capital=10_000_000,
        contracts=1,
        point_value=250_000,
    )
    # Explicitly set slippage_model to None
    config.slippage_model = None

    # Create test data
    data = create_test_data(num_bars=5, base_price=100.0)

    # Run backtest
    strategy = SimpleStrategy()
    engine = BacktestEngine(strategy, config)
    result = engine.run(data)

    # Verify that a trade occurred
    assert result.total_trades == 1

    # Get the trade
    trade = result.trades[0]

    # Without slippage model, entry price should equal market price
    market_price = 100.0
    assert (
        trade.entry_price == market_price
    ), f"Entry price {trade.entry_price} should equal market {market_price} without slippage model"


def test_backtest_slippage_model_disabled():
    """Test that BacktestEngine respects enabled=False in slippage config."""
    # Create slippage model with enabled=False
    slippage_config = SlippageModelConfig(
        enabled=False,  # Disabled
        base_spread_bps=2.0,
    )
    slippage_model = SlippageModel(slippage_config)

    # Create backtest config
    config = BacktestConfig.futures(
        initial_capital=10_000_000,
        contracts=1,
        point_value=250_000,
    )
    config.slippage_model = slippage_model

    # Create test data
    data = create_test_data(num_bars=5, base_price=100.0)

    # Run backtest
    strategy = SimpleStrategy()
    engine = BacktestEngine(strategy, config)
    result = engine.run(data)

    # Verify that a trade occurred
    assert result.total_trades == 1

    # Get the trade
    trade = result.trades[0]

    # With disabled slippage model, entry price should equal market price
    market_price = 100.0
    assert (
        trade.entry_price == market_price
    ), f"Entry price {trade.entry_price} should equal market {market_price} when slippage model is disabled"


def test_backtest_short_entry_slippage():
    """Test that short entry (SELL) applies slippage correctly (worse fill price)."""

    class ShortStrategy:
        """Test strategy that sells (short) on first bar."""

        name = "short_test"

        def __init__(self):
            self.position = None
            self.bar_count = 0

        def set_position(self, position):
            self.position = position

        def on_bar(self, bar):
            self.bar_count += 1
            if self.bar_count == 1:
                return SignalType.SELL  # Short entry
            return SignalType.HOLD

    # Create slippage model
    slippage_config = SlippageModelConfig(
        enabled=True,
        base_spread_bps=2.0,
        min_slippage_bps=1.0,
        max_slippage_bps=10.0,
    )
    slippage_model = SlippageModel(slippage_config)

    # Create backtest config
    config = BacktestConfig.futures(
        initial_capital=10_000_000,
        contracts=1,
        point_value=250_000,
    )
    config.slippage_model = slippage_model

    # Create test data
    data = create_test_data(num_bars=5, base_price=100.0)

    # Run backtest
    strategy = ShortStrategy()
    engine = BacktestEngine(strategy, config)
    result = engine.run(data)

    # Verify trade occurred
    assert result.total_trades == 1

    trade = result.trades[0]
    assert trade.side == "SELL", "Expected short position"

    # For SELL (short entry), slippage means worse fill = LOWER price
    market_price = 100.0
    expected_min_entry = market_price * 0.999  # At most 10 bps below
    expected_max_entry = market_price  # At minimum, equals market

    assert (
        trade.entry_price >= expected_min_entry
    ), f"Short entry {trade.entry_price} should be >= {expected_min_entry}"
    assert (
        trade.entry_price <= expected_max_entry
    ), f"Short entry {trade.entry_price} should be <= market {expected_max_entry}"

    # Verify entry price is actually adjusted (lower than market for short)
    assert (
        trade.entry_price < market_price
    ), f"Short entry {trade.entry_price} should be lower than market {market_price} due to slippage"


def test_backtest_exit_slippage():
    """Test that BacktestEngine uses SlippageModel for exit slippage calculation."""

    class BuyHoldSellStrategy:
        """Test strategy that buys on first bar, holds for 3 bars, then sells."""

        name = "buy_hold_sell_test"

        def __init__(self):
            self.position = None
            self.bar_count = 0

        def set_position(self, position):
            self.position = position

        def on_bar(self, bar):
            self.bar_count += 1
            if self.bar_count == 1:
                return SignalType.BUY  # Entry
            elif self.bar_count == 4:
                return SignalType.SELL  # Exit
            return SignalType.HOLD

    # Create slippage model with known parameters
    slippage_config = SlippageModelConfig(
        enabled=True,
        base_spread_bps=2.0,  # 2 bps base slippage
        depth_impact_factor=0.5,
        min_slippage_bps=1.0,
        max_slippage_bps=10.0,
    )
    slippage_model = SlippageModel(slippage_config)

    # Create backtest config for futures with slippage model
    config = BacktestConfig.futures(
        initial_capital=10_000_000,
        contracts=1,
        point_value=250_000,  # KOSPI200 futures
    )
    config.slippage_model = slippage_model

    # Create test data with price movement
    data = create_test_data(num_bars=5, base_price=100.0)

    # Run backtest
    strategy = BuyHoldSellStrategy()
    engine = BacktestEngine(strategy, config)
    result = engine.run(data)

    # Verify that a trade occurred
    assert result.total_trades == 1, "Expected exactly one trade"

    # Get the trade
    trade = result.trades[0]

    # Verify it's a BUY position
    assert trade.side == "BUY", "Expected a BUY position"

    # Entry price should be higher than market (buy slippage)
    entry_market_price = 100.0
    assert trade.entry_price > entry_market_price, (
        f"Entry price {trade.entry_price} should be higher than market {entry_market_price}"
    )

    # Exit price should be lower than market (sell slippage when closing long)
    # Bar 4 has close price = 100.0 + (3 * 0.05) = 100.15
    exit_market_price = 100.15
    assert trade.exit_price < exit_market_price, (
        f"Exit price {trade.exit_price} should be lower than market {exit_market_price} due to exit slippage"
    )

    # Verify exit price is within expected slippage range
    # With base_spread_bps=2.0, expected ~2 bps = 0.0002 = 0.02%
    expected_min_exit = exit_market_price * 0.999  # At most 10 bps below (max_slippage_bps)
    expected_max_exit = exit_market_price  # At minimum, equals market

    assert trade.exit_price >= expected_min_exit, (
        f"Exit price {trade.exit_price} should be >= {expected_min_exit}"
    )
    assert trade.exit_price <= expected_max_exit, (
        f"Exit price {trade.exit_price} should be <= market {expected_max_exit}"
    )


def test_backtest_exit_slippage_short():
    """Test that exit slippage for short positions (buy to cover) applies correctly."""

    class ShortHoldCoverStrategy:
        """Test strategy that shorts on first bar, holds, then covers."""

        name = "short_hold_cover_test"

        def __init__(self):
            self.position = None
            self.bar_count = 0

        def set_position(self, position):
            self.position = position

        def on_bar(self, bar):
            self.bar_count += 1
            if self.bar_count == 1:
                return SignalType.SELL  # Short entry
            elif self.bar_count == 4:
                return SignalType.BUY  # Cover (exit)
            return SignalType.HOLD

    # Create slippage model
    slippage_config = SlippageModelConfig(
        enabled=True,
        base_spread_bps=2.0,
        min_slippage_bps=1.0,
        max_slippage_bps=10.0,
    )
    slippage_model = SlippageModel(slippage_config)

    # Create backtest config
    config = BacktestConfig.futures(
        initial_capital=10_000_000,
        contracts=1,
        point_value=250_000,
    )
    config.slippage_model = slippage_model

    # Create test data
    data = create_test_data(num_bars=5, base_price=100.0)

    # Run backtest
    strategy = ShortHoldCoverStrategy()
    engine = BacktestEngine(strategy, config)
    result = engine.run(data)

    # Verify trade occurred
    assert result.total_trades == 1, "Expected exactly one trade"

    trade = result.trades[0]
    assert trade.side == "SELL", "Expected a SELL (short) position"

    # Entry price should be lower than market (short entry slippage)
    entry_market_price = 100.0
    assert trade.entry_price < entry_market_price, (
        f"Short entry {trade.entry_price} should be lower than market {entry_market_price}"
    )

    # Exit price should be higher than market (buy to cover slippage)
    # Bar 4 has close price = 100.0 + (3 * 0.05) = 100.15
    exit_market_price = 100.15
    assert trade.exit_price > exit_market_price, (
        f"Exit price {trade.exit_price} should be higher than market {exit_market_price} due to exit slippage (buy to cover)"
    )

    # Verify exit price is within expected slippage range
    expected_min_exit = exit_market_price  # At minimum, equals market
    expected_max_exit = exit_market_price * 1.001  # At most 10 bps above (max_slippage_bps)

    assert trade.exit_price >= expected_min_exit, (
        f"Exit price {trade.exit_price} should be >= market {expected_min_exit}"
    )
    assert trade.exit_price <= expected_max_exit, (
        f"Exit price {trade.exit_price} should be <= {expected_max_exit}"
    )
