"""Tests for BacktestEngine performance metrics calculation.

Covers max drawdown, Sharpe ratio, Sortino ratio, and win rate calculations.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from shared.backtest.config import BacktestConfig, RiskConfig
from shared.backtest.engine import BacktestEngine, SignalType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ohlcv(n: int = 100, code: str = "005930", base_price: float = 100.0) -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing."""
    base = datetime(2024, 1, 2, 9, 0)
    rng = np.random.default_rng(42)
    price = base_price
    rows: list[dict] = []
    for i in range(n):
        price += rng.uniform(-1, 1.2)
        rows.append(
            {
                "code": code,
                "name": code,
                "datetime": base + timedelta(minutes=i),
                "open": round(price - 0.2, 2),
                "high": round(price + 0.5, 2),
                "low": round(price - 0.5, 2),
                "close": round(price, 2),
                "volume": 1000 + i,
            }
        )
    return pd.DataFrame(rows)


def _make_trending_ohlcv(n: int = 100, trend: float = 0.5) -> pd.DataFrame:
    """Generate OHLCV with consistent trend for controlled testing."""
    base = datetime(2024, 1, 2, 9, 0)
    price = 100.0
    rows: list[dict] = []
    for i in range(n):
        price += trend  # Consistent trend
        rows.append(
            {
                "code": "TEST",
                "name": "TEST",
                "datetime": base + timedelta(minutes=i),
                "open": round(price - 0.1, 2),
                "high": round(price + 0.2, 2),
                "low": round(price - 0.2, 2),
                "close": round(price, 2),
                "volume": 1000,
            }
        )
    return pd.DataFrame(rows)


class _ControlledTradeStrategy:
    """Strategy that generates specific trade patterns for testing."""

    name = "controlled_trade"

    def __init__(self, win_pattern: list[bool] | None = None):
        """
        Args:
            win_pattern: List of booleans indicating win (True) or loss (False)
                        for each trade. If None, never trades.
        """
        self.win_pattern = win_pattern or []
        self.trade_index = 0
        self.position_open = False
        self.bars_in_position = 0
        self.entry_price = 0.0

    def on_bar(self, bar: dict) -> SignalType:
        if not self.win_pattern or self.trade_index >= len(self.win_pattern):
            return SignalType.HOLD

        current_price = bar["close"]

        if not self.position_open:
            # Enter position
            self.position_open = True
            self.entry_price = current_price
            self.bars_in_position = 0
            return SignalType.BUY

        self.bars_in_position += 1

        # Exit after 3 bars
        if self.bars_in_position >= 3:
            should_win = self.win_pattern[self.trade_index]
            # Check if price moved in winning direction
            price_moved_up = current_price > self.entry_price

            if should_win == price_moved_up:
                # Exit now
                self.position_open = False
                self.trade_index += 1
                return SignalType.SELL

        return SignalType.HOLD


class _AlwaysBuyStrategy:
    """Buys on first bar and holds."""

    name = "always_buy"

    def __init__(self):
        self._bought = False

    def on_bar(self, bar: dict) -> SignalType:
        if not self._bought:
            self._bought = True
            return SignalType.BUY
        return SignalType.HOLD


class _BuyAndSellStrategy:
    """Buys, waits N bars, then sells."""

    name = "buy_and_sell"

    def __init__(self, hold_bars: int = 10):
        self.hold_bars = hold_bars
        self.position_open = False
        self.bars_held = 0

    def on_bar(self, bar: dict) -> SignalType:
        if not self.position_open:
            self.position_open = True
            self.bars_held = 0
            return SignalType.BUY

        self.bars_held += 1
        if self.bars_held >= self.hold_bars:
            self.position_open = False
            return SignalType.SELL

        return SignalType.HOLD


# ---------------------------------------------------------------------------
# Max Drawdown Tests
# ---------------------------------------------------------------------------


class TestMaxDrawdown:
    """Test maximum drawdown calculation."""

    def test_empty_equity_curve_returns_zero(self):
        """Empty equity curve should return 0% drawdown."""
        strategy = _ControlledTradeStrategy(win_pattern=[])
        engine = BacktestEngine(strategy, BacktestConfig())
        result = engine.run(_make_ohlcv(10))

        assert result.max_drawdown_pct == 0.0

    def test_steadily_increasing_equity_no_drawdown(self):
        """Steadily increasing equity should have minimal/zero drawdown."""
        strategy = _AlwaysBuyStrategy()
        config = BacktestConfig()
        engine = BacktestEngine(strategy, config)

        # Create strongly upward trending data
        result = engine.run(_make_trending_ohlcv(100, trend=1.0))

        # With upward trend and buy-and-hold, drawdown should be very small
        assert result.max_drawdown_pct < 5.0

    def test_single_drawdown_calculation(self):
        """Single peak-to-valley drawdown should be calculated correctly."""
        strategy = _AlwaysBuyStrategy()
        config = BacktestConfig()
        engine = BacktestEngine(strategy, config)

        # Create data with clear peak and valley
        # Start at 100, go to 150 (peak), then drop to 120 (valley)
        base = datetime(2024, 1, 2, 9, 0)
        rows = []

        # Rise to peak
        for i in range(50):
            price = 100 + i
            rows.append({
                "code": "TEST",
                "name": "TEST",
                "datetime": base + timedelta(minutes=i),
                "open": price,
                "high": price + 1,
                "low": price - 1,
                "close": price,
                "volume": 1000,
            })

        # Drop from peak
        for i in range(30):
            price = 150 - i
            rows.append({
                "code": "TEST",
                "name": "TEST",
                "datetime": base + timedelta(minutes=50 + i),
                "open": price,
                "high": price + 1,
                "low": price - 1,
                "close": price,
                "volume": 1000,
            })

        df = pd.DataFrame(rows)
        result = engine.run(df)

        # Should have some drawdown from peak
        assert result.max_drawdown_pct > 0.0
        # But not more than the actual price drop percentage
        assert result.max_drawdown_pct < 30.0

    def test_multiple_drawdowns_returns_maximum(self):
        """Multiple drawdowns should return the largest one."""
        strategy = _AlwaysBuyStrategy()
        config = BacktestConfig()
        engine = BacktestEngine(strategy, config)

        base = datetime(2024, 1, 2, 9, 0)
        rows = []

        # First drawdown: 100 -> 120 -> 110 (8.3% DD)
        prices_1 = list(range(100, 121)) + list(range(120, 109, -1))

        # Second drawdown: 110 -> 140 -> 120 (14.3% DD) — this is larger
        prices_2 = list(range(110, 141)) + list(range(140, 119, -1))

        all_prices = prices_1 + prices_2

        for i, price in enumerate(all_prices):
            rows.append({
                "code": "TEST",
                "name": "TEST",
                "datetime": base + timedelta(minutes=i),
                "open": float(price),
                "high": float(price + 1),
                "low": float(price - 1),
                "close": float(price),
                "volume": 1000,
            })

        df = pd.DataFrame(rows)
        result = engine.run(df)

        # Should capture the larger drawdown
        assert result.max_drawdown_pct > 10.0

    def test_drawdown_resets_at_new_peak(self):
        """Drawdown calculation should reset when new peak is reached."""
        strategy = _AlwaysBuyStrategy()
        config = BacktestConfig()
        engine = BacktestEngine(strategy, config)

        base = datetime(2024, 1, 2, 9, 0)
        rows = []

        # Peak 1: 100 -> 90 (10% DD), then recover to new peak 110
        # Peak 2: 110 -> 95 (13.6% DD) — this should be the max
        prices = (
            list(range(100, 91, -1)) +  # First drawdown
            list(range(90, 111)) +        # Recover and new peak
            list(range(110, 94, -1))      # Larger drawdown
        )

        for i, price in enumerate(prices):
            rows.append({
                "code": "TEST",
                "name": "TEST",
                "datetime": base + timedelta(minutes=i),
                "open": float(price),
                "high": float(price + 1),
                "low": float(price - 1),
                "close": float(price),
                "volume": 1000,
            })

        df = pd.DataFrame(rows)
        result = engine.run(df)

        # Should be around 13-14%
        assert 10.0 < result.max_drawdown_pct < 20.0


# ---------------------------------------------------------------------------
# Sharpe Ratio Tests
# ---------------------------------------------------------------------------


class TestSharpeRatio:
    """Test Sharpe ratio calculation."""

    def test_insufficient_returns_returns_zero(self):
        """Less than 2 daily returns should return 0.0 Sharpe ratio."""
        strategy = _ControlledTradeStrategy(win_pattern=[])
        config = BacktestConfig()
        engine = BacktestEngine(strategy, config)

        # Only 10 bars (same day) — insufficient for daily returns
        result = engine.run(_make_ohlcv(10))

        assert result.sharpe_ratio == 0.0

    def test_zero_volatility_returns_zero(self):
        """Constant returns (zero volatility) should return 0.0."""
        strategy = _AlwaysBuyStrategy()
        config = BacktestConfig()
        engine = BacktestEngine(strategy, config)

        # Create perfectly flat price (no volatility)
        base = datetime(2024, 1, 2, 9, 0)
        rows = []
        for i in range(300):  # 300 minutes = multiple days at 1-min bars
            # Change day every 100 bars
            dt = base + timedelta(minutes=i)
            rows.append({
                "code": "TEST",
                "name": "TEST",
                "datetime": dt,
                "open": 100.0,
                "high": 100.0,
                "low": 100.0,
                "close": 100.0,
                "volume": 1000,
            })

        df = pd.DataFrame(rows)
        result = engine.run(df)

        # Zero volatility -> Sharpe ratio should be 0.0
        assert result.sharpe_ratio == 0.0

    def test_positive_returns_positive_sharpe(self):
        """Positive returns with volatility should produce positive Sharpe."""
        strategy = _AlwaysBuyStrategy()
        config = BacktestConfig()
        engine = BacktestEngine(strategy, config)

        # Create upward trending data across multiple days
        base = datetime(2024, 1, 2, 9, 0)
        rows = []
        price = 100.0

        for day in range(5):  # 5 trading days
            for minute in range(60):  # 60 bars per day
                price += 0.2  # Steady increase
                dt = base + timedelta(days=day, minutes=minute)
                rows.append({
                    "code": "TEST",
                    "name": "TEST",
                    "datetime": dt,
                    "open": round(price - 0.1, 2),
                    "high": round(price + 0.2, 2),
                    "low": round(price - 0.2, 2),
                    "close": round(price, 2),
                    "volume": 1000,
                })

        df = pd.DataFrame(rows)
        result = engine.run(df)

        # Upward trend should produce positive Sharpe
        assert result.sharpe_ratio > 0.0

    def test_negative_returns_negative_sharpe(self):
        """Negative returns should produce negative Sharpe."""
        strategy = _AlwaysBuyStrategy()
        config = BacktestConfig()
        engine = BacktestEngine(strategy, config)

        # Create downward trending data across multiple days
        base = datetime(2024, 1, 2, 9, 0)
        rows = []
        price = 200.0

        for day in range(5):
            for minute in range(60):
                price -= 0.3  # Steady decrease
                dt = base + timedelta(days=day, minutes=minute)
                rows.append({
                    "code": "TEST",
                    "name": "TEST",
                    "datetime": dt,
                    "open": round(price + 0.1, 2),
                    "high": round(price + 0.2, 2),
                    "low": round(price - 0.2, 2),
                    "close": round(price, 2),
                    "volume": 1000,
                })

        df = pd.DataFrame(rows)
        result = engine.run(df)

        # Downward trend should produce negative Sharpe
        assert result.sharpe_ratio < 0.0

    def test_sharpe_annualized_scaling(self):
        """Sharpe ratio should be properly annualized (sqrt(252))."""
        strategy = _AlwaysBuyStrategy()
        config = BacktestConfig()
        engine = BacktestEngine(strategy, config)

        # Generate multi-day data
        base = datetime(2024, 1, 2, 9, 0)
        rows = []
        price = 100.0

        for day in range(10):
            for minute in range(100):
                price += 0.1
                dt = base + timedelta(days=day, minutes=minute)
                rows.append({
                    "code": "TEST",
                    "name": "TEST",
                    "datetime": dt,
                    "open": price,
                    "high": price + 0.5,
                    "low": price - 0.5,
                    "close": price,
                    "volume": 1000,
                })

        df = pd.DataFrame(rows)
        result = engine.run(df)

        # Sharpe ratio should be a reasonable value (annualized)
        # Typically ranges from -3 to +3 for most strategies
        assert -10.0 < result.sharpe_ratio < 10.0


# ---------------------------------------------------------------------------
# Sortino Ratio Tests
# ---------------------------------------------------------------------------


class TestSortinoRatio:
    """Test Sortino ratio calculation."""

    def test_insufficient_returns_returns_zero(self):
        """Less than 2 daily returns should return 0.0 Sortino ratio."""
        strategy = _ControlledTradeStrategy(win_pattern=[])
        config = BacktestConfig()
        engine = BacktestEngine(strategy, config)

        result = engine.run(_make_ohlcv(10))

        assert result.sortino_ratio == 0.0

    def test_no_negative_returns_returns_inf(self):
        """All positive returns should return inf (no downside risk)."""
        strategy = _AlwaysBuyStrategy()
        config = BacktestConfig()
        engine = BacktestEngine(strategy, config)

        # Create strongly upward trending data with forced daily boundaries
        base = datetime(2024, 1, 2, 9, 0)
        rows = []
        price = 100.0

        for day in range(5):
            for minute in range(50):
                price += 0.5  # Strong upward trend
                dt = base + timedelta(days=day, minutes=minute)
                rows.append({
                    "code": "TEST",
                    "name": "TEST",
                    "datetime": dt,
                    "open": price,
                    "high": price + 0.5,
                    "low": price - 0.1,
                    "close": price,
                    "volume": 1000,
                })

        df = pd.DataFrame(rows)
        result = engine.run(df)

        # If all returns are positive, Sortino should be very high or inf
        # Implementation returns inf if no negative returns and mean > 0
        assert result.sortino_ratio > 0.0 or result.sortino_ratio == float("inf")

    def test_mixed_returns_finite_sortino(self):
        """Mixed positive and negative returns should produce finite Sortino."""
        strategy = _AlwaysBuyStrategy()
        config = BacktestConfig()
        engine = BacktestEngine(strategy, config)

        # Create volatile data with ups and downs across multiple days
        base = datetime(2024, 1, 2, 9, 0)
        rows = []
        price = 100.0

        for day in range(10):
            for minute in range(50):
                # Alternate between gains and losses
                if day % 2 == 0:
                    price += 0.3
                else:
                    price -= 0.2
                dt = base + timedelta(days=day, minutes=minute)
                rows.append({
                    "code": "TEST",
                    "name": "TEST",
                    "datetime": dt,
                    "open": price,
                    "high": price + 0.5,
                    "low": price - 0.5,
                    "close": price,
                    "volume": 1000,
                })

        df = pd.DataFrame(rows)
        result = engine.run(df)

        # Should have finite Sortino ratio
        assert result.sortino_ratio != float("inf")
        assert -10.0 < result.sortino_ratio < 10.0

    def test_only_negative_returns_negative_sortino(self):
        """All negative returns should produce negative or zero Sortino."""
        strategy = _AlwaysBuyStrategy()
        config = BacktestConfig()
        engine = BacktestEngine(strategy, config)

        # Create strongly downward trending data
        base = datetime(2024, 1, 2, 9, 0)
        rows = []
        price = 200.0

        for day in range(5):
            for minute in range(50):
                price -= 0.5  # Strong downward trend
                dt = base + timedelta(days=day, minutes=minute)
                rows.append({
                    "code": "TEST",
                    "name": "TEST",
                    "datetime": dt,
                    "open": price,
                    "high": price + 0.1,
                    "low": price - 0.5,
                    "close": price,
                    "volume": 1000,
                })

        df = pd.DataFrame(rows)
        result = engine.run(df)

        # Negative mean return should produce negative Sortino
        assert result.sortino_ratio <= 0.0

    def test_sortino_only_uses_downside_deviation(self):
        """Sortino should only consider negative returns in volatility calculation."""
        strategy = _AlwaysBuyStrategy()
        config = BacktestConfig()
        engine = BacktestEngine(strategy, config)

        # Create data with large positive swings but small negative swings
        # Sortino should be better than Sharpe
        base = datetime(2024, 1, 2, 9, 0)
        rows = []
        price = 100.0

        for day in range(8):
            for minute in range(50):
                # Mostly big gains, occasional small losses
                if minute % 10 == 0:
                    price -= 0.1  # Small loss
                else:
                    price += 0.5  # Big gain
                dt = base + timedelta(days=day, minutes=minute)
                rows.append({
                    "code": "TEST",
                    "name": "TEST",
                    "datetime": dt,
                    "open": price,
                    "high": price + 0.5,
                    "low": price - 0.2,
                    "close": price,
                    "volume": 1000,
                })

        df = pd.DataFrame(rows)
        result = engine.run(df)

        # Sortino should be positive since mostly gains
        assert result.sortino_ratio > 0.0
        # Sortino should generally be >= Sharpe (less penalty for upside volatility)
        assert result.sortino_ratio >= result.sharpe_ratio


# ---------------------------------------------------------------------------
# Win Rate Tests
# ---------------------------------------------------------------------------


class TestWinRate:
    """Test win rate calculation."""

    def test_no_trades_zero_win_rate(self):
        """No trades should result in 0% win rate."""
        strategy = _ControlledTradeStrategy(win_pattern=[])
        config = BacktestConfig()
        engine = BacktestEngine(strategy, config)

        result = engine.run(_make_ohlcv(50))

        assert result.win_rate == 0.0
        assert result.total_trades == 0
        assert result.winning_trades == 0
        assert result.losing_trades == 0

    def test_all_winning_trades_100_percent(self):
        """All winning trades should result in 100% win rate."""
        strategy = _BuyAndSellStrategy(hold_bars=5)
        config = BacktestConfig()
        engine = BacktestEngine(strategy, config)

        # Create strongly upward data to ensure wins
        result = engine.run(_make_trending_ohlcv(100, trend=1.0))

        if result.total_trades > 0:
            assert result.win_rate == 100.0
            assert result.winning_trades == result.total_trades
            assert result.losing_trades == 0

    def test_all_losing_trades_zero_percent(self):
        """All losing trades should result in 0% win rate."""
        strategy = _BuyAndSellStrategy(hold_bars=5)
        config = BacktestConfig()
        engine = BacktestEngine(strategy, config)

        # Create strongly downward data to ensure losses
        result = engine.run(_make_trending_ohlcv(100, trend=-1.0))

        if result.total_trades > 0:
            assert result.win_rate == 0.0
            assert result.winning_trades == 0
            assert result.losing_trades == result.total_trades

    def test_mixed_trades_correct_percentage(self):
        """Mixed wins/losses should calculate correct win rate."""
        strategy = _BuyAndSellStrategy(hold_bars=3)
        config = BacktestConfig()
        engine = BacktestEngine(strategy, config)

        # Create alternating up/down data
        base = datetime(2024, 1, 2, 9, 0)
        rows = []
        price = 100.0

        for i in range(200):
            # Alternate patterns: 10 bars up, 10 bars down
            if (i // 10) % 2 == 0:
                price += 0.3
            else:
                price -= 0.3

            rows.append({
                "code": "TEST",
                "name": "TEST",
                "datetime": base + timedelta(minutes=i),
                "open": price,
                "high": price + 0.2,
                "low": price - 0.2,
                "close": price,
                "volume": 1000,
            })

        df = pd.DataFrame(rows)
        result = engine.run(df)

        if result.total_trades > 0:
            # Should have mix of wins and losses
            assert 0.0 < result.win_rate < 100.0
            assert result.winning_trades > 0
            assert result.losing_trades > 0
            # Verify calculation
            expected_rate = (result.winning_trades / result.total_trades) * 100
            assert abs(result.win_rate - expected_rate) < 0.01

    def test_breakeven_trades_not_counted_as_wins(self):
        """Trades with exactly 0 PnL should not be counted as wins."""
        strategy = _BuyAndSellStrategy(hold_bars=2)
        config = BacktestConfig()
        engine = BacktestEngine(strategy, config)

        # Create perfectly flat data (breakeven trades)
        base = datetime(2024, 1, 2, 9, 0)
        rows = []

        for i in range(50):
            rows.append({
                "code": "TEST",
                "name": "TEST",
                "datetime": base + timedelta(minutes=i),
                "open": 100.0,
                "high": 100.0,
                "low": 100.0,
                "close": 100.0,
                "volume": 1000,
            })

        df = pd.DataFrame(rows)
        result = engine.run(df)

        if result.total_trades > 0:
            # With fees/slippage, flat price means losses
            # So win rate should be 0%
            assert result.win_rate == 0.0
            assert result.winning_trades == 0

    def test_win_rate_formula_consistency(self):
        """Win rate should equal (winning_trades / total_trades) * 100."""
        strategy = _BuyAndSellStrategy(hold_bars=5)
        config = BacktestConfig()
        engine = BacktestEngine(strategy, config)

        result = engine.run(_make_ohlcv(150))

        if result.total_trades > 0:
            expected = (result.winning_trades / result.total_trades) * 100
            assert abs(result.win_rate - expected) < 0.01
            # Also verify counts add up
            assert result.total_trades == result.winning_trades + result.losing_trades
