"""Tests for SlippageModel integration with BacktestEngine.

Verifies that the backtest engine correctly uses the slippage model
for futures trading when configured.

Test Coverage:
1. Basic slippage model usage (enabled/disabled/None)
2. Long position entry/exit slippage
3. Short position entry/exit slippage
4. Direct comparison tests showing P&L impact
5. Multi-trade cumulative slippage impact

Expected Behavior:
- BUY entry: pays MORE (worse fill) → entry_price increases
- SELL entry (short): receives LESS (worse fill) → entry_price decreases
- BUY exit (closing long): receives LESS (worse fill) → exit_price decreases
- SELL exit (closing short): pays MORE (worse fill) → exit_price increases
- Overall: P&L is lower with slippage (more realistic backtest results)
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


def test_backtest_slippage_comparison_long_position():
    """Direct comparison: backtest with slippage enabled vs disabled for long position.

    Verifies that:
    1. Slippage model increases entry price (worse fill on buy)
    2. Slippage model decreases exit price (worse fill on sell)
    3. Total P&L is lower with slippage (more realistic)
    """

    class BuyHoldSellStrategy:
        """Strategy that buys on bar 1, holds, exits on bar 4."""

        name = "comparison_test"

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

    # Create test data with clear price movement
    # Entry at 100.0, Exit at 100.15 (profit expected)
    data = create_test_data(num_bars=5, base_price=100.0)

    # ========== Run WITHOUT slippage model ==========
    config_no_slippage = BacktestConfig.futures(
        initial_capital=10_000_000,
        contracts=1,
        point_value=250_000,
    )
    config_no_slippage.slippage_model = None

    strategy_no_slip = BuyHoldSellStrategy()
    engine_no_slip = BacktestEngine(strategy_no_slip, config_no_slippage)
    result_no_slip = engine_no_slip.run(data)

    # ========== Run WITH slippage model ==========
    slippage_config = SlippageModelConfig(
        enabled=True,
        base_spread_bps=2.0,  # 2 bps base slippage
        depth_impact_factor=0.5,
        min_slippage_bps=1.0,
        max_slippage_bps=10.0,
    )
    slippage_model = SlippageModel(slippage_config)

    config_with_slippage = BacktestConfig.futures(
        initial_capital=10_000_000,
        contracts=1,
        point_value=250_000,
    )
    config_with_slippage.slippage_model = slippage_model

    strategy_with_slip = BuyHoldSellStrategy()
    engine_with_slip = BacktestEngine(strategy_with_slip, config_with_slippage)
    result_with_slip = engine_with_slip.run(data)

    # ========== Compare Results ==========
    assert result_no_slip.total_trades == 1, "No slippage: expected 1 trade"
    assert result_with_slip.total_trades == 1, "With slippage: expected 1 trade"

    trade_no_slip = result_no_slip.trades[0]
    trade_with_slip = result_with_slip.trades[0]

    # Entry price comparison: slippage should increase entry price (worse fill)
    assert trade_no_slip.entry_price == 100.0, "No slippage: entry at market price"
    assert trade_with_slip.entry_price > trade_no_slip.entry_price, (
        f"Slippage should increase entry price: "
        f"{trade_with_slip.entry_price} > {trade_no_slip.entry_price}"
    )

    # Exit price comparison: slippage should decrease exit price (worse fill)
    assert trade_no_slip.exit_price == 100.15, "No slippage: exit at market price"
    assert trade_with_slip.exit_price < trade_no_slip.exit_price, (
        f"Slippage should decrease exit price: "
        f"{trade_with_slip.exit_price} < {trade_no_slip.exit_price}"
    )

    # P&L comparison: slippage should reduce profit
    pnl_no_slip = trade_no_slip.profit
    pnl_with_slip = trade_with_slip.profit

    assert pnl_with_slip < pnl_no_slip, (
        f"Slippage should reduce P&L: "
        f"{pnl_with_slip:,.0f} < {pnl_no_slip:,.0f}"
    )

    # Calculate slippage impact
    slippage_cost = pnl_no_slip - pnl_with_slip
    assert slippage_cost > 0, "Slippage cost should be positive"

    # Verify slippage is reasonable (not excessive)
    # With base_spread_bps=2.0, expected ~4 bps total (entry + exit)
    # Max is 20 bps (10 bps entry + 10 bps exit)
    max_expected_slippage = 100.0 * 0.002 * 250_000  # 20 bps * point_value
    assert slippage_cost <= max_expected_slippage, (
        f"Slippage cost {slippage_cost:,.0f} should not exceed {max_expected_slippage:,.0f}"
    )


def test_backtest_slippage_comparison_short_position():
    """Direct comparison: backtest with slippage enabled vs disabled for short position.

    Verifies that:
    1. Slippage model decreases entry price (worse fill on short sell)
    2. Slippage model increases exit price (worse fill on buy to cover)
    3. Total P&L is lower with slippage (more realistic)
    """

    class ShortHoldCoverStrategy:
        """Strategy that shorts on bar 1, holds, covers on bar 4."""

        name = "short_comparison_test"

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

    # Create test data with price increase (short should lose money)
    data = create_test_data(num_bars=5, base_price=100.0)

    # ========== Run WITHOUT slippage model ==========
    config_no_slippage = BacktestConfig.futures(
        initial_capital=10_000_000,
        contracts=1,
        point_value=250_000,
    )
    config_no_slippage.slippage_model = None

    strategy_no_slip = ShortHoldCoverStrategy()
    engine_no_slip = BacktestEngine(strategy_no_slip, config_no_slippage)
    result_no_slip = engine_no_slip.run(data)

    # ========== Run WITH slippage model ==========
    slippage_config = SlippageModelConfig(
        enabled=True,
        base_spread_bps=2.0,
        depth_impact_factor=0.5,
        min_slippage_bps=1.0,
        max_slippage_bps=10.0,
    )
    slippage_model = SlippageModel(slippage_config)

    config_with_slippage = BacktestConfig.futures(
        initial_capital=10_000_000,
        contracts=1,
        point_value=250_000,
    )
    config_with_slippage.slippage_model = slippage_model

    strategy_with_slip = ShortHoldCoverStrategy()
    engine_with_slip = BacktestEngine(strategy_with_slip, config_with_slippage)
    result_with_slip = engine_with_slip.run(data)

    # ========== Compare Results ==========
    assert result_no_slip.total_trades == 1, "No slippage: expected 1 trade"
    assert result_with_slip.total_trades == 1, "With slippage: expected 1 trade"

    trade_no_slip = result_no_slip.trades[0]
    trade_with_slip = result_with_slip.trades[0]

    # Entry price comparison: slippage should decrease entry price (worse fill on short)
    assert trade_no_slip.entry_price == 100.0, "No slippage: entry at market price"
    assert trade_with_slip.entry_price < trade_no_slip.entry_price, (
        f"Slippage should decrease short entry price: "
        f"{trade_with_slip.entry_price} < {trade_no_slip.entry_price}"
    )

    # Exit price comparison: slippage should increase exit price (worse fill on cover)
    assert trade_no_slip.exit_price == 100.15, "No slippage: exit at market price"
    assert trade_with_slip.exit_price > trade_no_slip.exit_price, (
        f"Slippage should increase cover price: "
        f"{trade_with_slip.exit_price} > {trade_no_slip.exit_price}"
    )

    # P&L comparison: slippage should make loss larger (or profit smaller)
    pnl_no_slip = trade_no_slip.profit
    pnl_with_slip = trade_with_slip.profit

    assert pnl_with_slip < pnl_no_slip, (
        f"Slippage should reduce P&L (increase loss): "
        f"{pnl_with_slip:,.0f} < {pnl_no_slip:,.0f}"
    )

    # Calculate slippage impact
    slippage_cost = pnl_no_slip - pnl_with_slip
    assert slippage_cost > 0, "Slippage cost should be positive"

    # Verify slippage is reasonable (not excessive)
    max_expected_slippage = 100.0 * 0.002 * 250_000  # 20 bps max
    assert slippage_cost <= max_expected_slippage, (
        f"Slippage cost {slippage_cost:,.0f} should not exceed {max_expected_slippage:,.0f}"
    )


def test_backtest_slippage_impact_on_winrate():
    """Test that slippage model affects overall backtest performance metrics.

    Verifies that a strategy with multiple trades shows measurable difference
    in total P&L, win rate, and other metrics when slippage is enabled.
    """

    class MultiTradeStrategy:
        """Strategy that makes multiple trades throughout the backtest."""

        name = "multi_trade_test"

        def __init__(self):
            self.position = None
            self.bar_count = 0
            self.trade_count = 0

        def set_position(self, position):
            self.position = position

        def on_bar(self, bar):
            self.bar_count += 1
            # Trade every 10 bars (5 trades total in 50 bars)
            if self.bar_count % 10 == 1 and self.trade_count < 5:
                self.trade_count += 1
                return SignalType.BUY if self.trade_count % 2 == 1 else SignalType.SELL
            elif self.bar_count % 10 == 6 and self.position is not None:
                return SignalType.SELL if self.position.side == "BUY" else SignalType.BUY
            return SignalType.HOLD

    # Create test data with some volatility
    data = create_test_data(num_bars=50, base_price=100.0)

    # ========== Run WITHOUT slippage ==========
    config_no_slippage = BacktestConfig.futures(
        initial_capital=10_000_000,
        contracts=1,
        point_value=250_000,
    )
    config_no_slippage.slippage_model = None

    strategy_no_slip = MultiTradeStrategy()
    engine_no_slip = BacktestEngine(strategy_no_slip, config_no_slippage)
    result_no_slip = engine_no_slip.run(data)

    # ========== Run WITH slippage ==========
    slippage_config = SlippageModelConfig(
        enabled=True,
        base_spread_bps=2.0,
        depth_impact_factor=0.5,
        min_slippage_bps=1.0,
        max_slippage_bps=10.0,
    )
    slippage_model = SlippageModel(slippage_config)

    config_with_slippage = BacktestConfig.futures(
        initial_capital=10_000_000,
        contracts=1,
        point_value=250_000,
    )
    config_with_slippage.slippage_model = slippage_model

    strategy_with_slip = MultiTradeStrategy()
    engine_with_slip = BacktestEngine(strategy_with_slip, config_with_slippage)
    result_with_slip = engine_with_slip.run(data)

    # ========== Compare Overall Performance ==========
    # Both should have same number of trades
    assert result_no_slip.total_trades == result_with_slip.total_trades, (
        "Trade count should be the same"
    )
    assert result_no_slip.total_trades > 0, "Should have at least one trade"

    # Final capital should be lower with slippage
    assert result_with_slip.final_capital <= result_no_slip.final_capital, (
        f"Final capital with slippage ({result_with_slip.final_capital:,.0f}) "
        f"should be <= without slippage ({result_no_slip.final_capital:,.0f})"
    )

    # Total return should be lower with slippage
    assert result_with_slip.total_return <= result_no_slip.total_return, (
        f"Total return with slippage ({result_with_slip.total_return:.2%}) "
        f"should be <= without slippage ({result_no_slip.total_return:.2%})"
    )

    # Calculate cumulative slippage cost across all trades
    total_slippage_cost = (
        result_no_slip.final_capital - result_with_slip.final_capital
    )

    # With multiple trades, slippage cost should be measurable
    if result_no_slip.total_trades > 0:
        avg_slippage_per_trade = total_slippage_cost / result_no_slip.total_trades
        assert avg_slippage_per_trade >= 0, (
            "Average slippage per trade should be non-negative"
        )
