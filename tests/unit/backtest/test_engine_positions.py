"""Tests for BacktestEngine._open_position() and _close_position() — slippage and commission."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from shared.backtest.config import BacktestConfig, CostConfig, RiskConfig
from shared.backtest.engine import BacktestEngine, ExitReason, SignalType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ohlcv(n: int = 100, code: str = "005930") -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing."""
    base = datetime(2024, 1, 2, 9, 0)
    rng = np.random.default_rng(42)
    price = 100.0
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


class _HoldStrategy:
    """Always HOLD — used to test direct _open_position / _close_position calls."""

    name = "hold"

    def on_bar(self, bar: dict) -> SignalType:
        return SignalType.HOLD


# ---------------------------------------------------------------------------
# Tests: _open_position (Position Opening)
# ---------------------------------------------------------------------------


class TestOpenPositionStock:
    """Tests for _open_position with stock configuration."""

    def test_open_buy_position_creates_position(self):
        """Opening a BUY position should create position entry and deduct capital."""
        config = BacktestConfig.stock(initial_capital=10_000_000, position_size_pct=10.0)
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        initial_capital = engine.capital
        price = 50000.0
        timestamp = datetime(2024, 1, 2, 9, 0)

        engine._open_position(
            code="005930",
            name="Samsung",
            side="BUY",
            price=price,
            timestamp=timestamp,
            bar={"atr": 1500.0},
        )

        # Position should be created
        assert "005930" in engine.positions
        pos = engine.positions["005930"]
        assert pos.code == "005930"
        assert pos.name == "Samsung"
        assert pos.side == "BUY"
        assert pos.entry_price == price
        assert pos.entry_time == timestamp
        assert pos.atr_at_entry == 1500.0
        assert pos.quantity > 0

        # Capital should be deducted
        assert engine.capital < initial_capital

    def test_open_sell_position_short(self):
        """Opening a SELL position (short) should work correctly."""
        config = BacktestConfig.stock(initial_capital=10_000_000)
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        engine._open_position(
            code="005930",
            name="Samsung",
            side="SELL",
            price=50000.0,
            timestamp=datetime(2024, 1, 2, 9, 0),
        )

        assert "005930" in engine.positions
        assert engine.positions["005930"].side == "SELL"

    def test_position_size_calculation_with_percentage(self):
        """Position size should be calculated from capital percentage."""
        config = BacktestConfig.stock(
            initial_capital=10_000_000,
            position_size_pct=10.0,  # 10% = 1M
        )
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        price = 50000.0
        # Expected: 1M / (50K * 1.00025) ≈ 19 shares
        # effective_price = 50000 * (1 + 0.00015 + 0.0001) = 50000 * 1.00025 = 50012.5
        # quantity = 1_000_000 / 50012.5 ≈ 19.99

        engine._open_position(
            code="005930",
            name="Samsung",
            side="BUY",
            price=price,
            timestamp=datetime(2024, 1, 2, 9, 0),
        )

        pos = engine.positions["005930"]
        assert pos.quantity == 19  # int(1_000_000 / 50012.5)

    def test_position_size_with_order_amount_per_stock(self):
        """order_amount_per_stock should override position_size_pct."""
        config = BacktestConfig.stock(
            initial_capital=10_000_000,
            position_size_pct=50.0,  # 50% would be 5M
            order_amount_per_stock=2_000_000,  # But fixed 2M takes priority
        )
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        price = 100000.0
        # Expected: 2M / (100K * 1.00025) ≈ 19 shares

        engine._open_position(
            code="005930",
            name="Samsung",
            side="BUY",
            price=price,
            timestamp=datetime(2024, 1, 2, 9, 0),
        )

        pos = engine.positions["005930"]
        expected_qty = int(2_000_000 / (price * 1.00025))
        assert pos.quantity == expected_qty

    def test_commission_and_slippage_applied(self):
        """Commission and slippage should be applied to capital deduction."""
        cost = CostConfig(commission_rate=0.0002, slippage_rate=0.0003, tax_rate=0.0)
        config = BacktestConfig(
            initial_capital=10_000_000,
            position_size_pct=10.0,
            cost=cost,
        )
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        initial_capital = engine.capital
        price = 50000.0

        engine._open_position(
            code="005930",
            name="Samsung",
            side="BUY",
            price=price,
            timestamp=datetime(2024, 1, 2, 9, 0),
        )

        pos = engine.positions["005930"]
        quantity = pos.quantity

        # Calculate expected cost
        commission = price * quantity * 0.0002
        slippage = price * quantity * 0.0003
        total_cost = price * quantity + commission + slippage

        capital_spent = initial_capital - engine.capital
        assert abs(capital_spent - total_cost) < 1.0  # Allow for rounding

    def test_insufficient_capital_no_position_opened(self):
        """Position should not open if insufficient capital."""
        config = BacktestConfig.stock(initial_capital=10_000)  # Very low capital
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        engine._open_position(
            code="005930",
            name="Samsung",
            side="BUY",
            price=50000.0,  # Would require 50K+ per share
            timestamp=datetime(2024, 1, 2, 9, 0),
        )

        # No position should be created
        assert "005930" not in engine.positions

    def test_max_positions_limit_enforced(self):
        """Should not open more positions than max_positions limit."""
        config = BacktestConfig.stock(initial_capital=100_000_000, max_positions=2)
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        # Open 2 positions (at limit)
        engine._open_position(
            code="005930",
            name="Samsung",
            side="BUY",
            price=50000.0,
            timestamp=datetime(2024, 1, 2, 9, 0),
        )
        engine._open_position(
            code="000660",
            name="SK Hynix",
            side="BUY",
            price=100000.0,
            timestamp=datetime(2024, 1, 2, 9, 1),
        )

        assert len(engine.positions) == 2

        # Try to open 3rd position (should be rejected)
        engine._open_position(
            code="035420",
            name="NAVER",
            side="BUY",
            price=200000.0,
            timestamp=datetime(2024, 1, 2, 9, 2),
        )

        assert len(engine.positions) == 2  # Still only 2
        assert "035420" not in engine.positions

    def test_atr_captured_from_bar(self):
        """ATR value should be captured from bar data at entry."""
        config = BacktestConfig.stock(initial_capital=10_000_000)
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        engine._open_position(
            code="005930",
            name="Samsung",
            side="BUY",
            price=50000.0,
            timestamp=datetime(2024, 1, 2, 9, 0),
            bar={"atr": 2500.0},
        )

        pos = engine.positions["005930"]
        assert pos.atr_at_entry == 2500.0

    def test_atr_defaults_to_zero_if_missing(self):
        """ATR should default to 0 if not in bar data."""
        config = BacktestConfig.stock(initial_capital=10_000_000)
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        engine._open_position(
            code="005930",
            name="Samsung",
            side="BUY",
            price=50000.0,
            timestamp=datetime(2024, 1, 2, 9, 0),
            bar={},  # No ATR
        )

        pos = engine.positions["005930"]
        assert pos.atr_at_entry == 0.0


class TestOpenPositionFutures:
    """Tests for _open_position with futures configuration."""

    def test_open_futures_position_fixed_quantity(self):
        """Futures position should use fixed quantity (1 contract)."""
        config = BacktestConfig.futures(
            initial_capital=10_000_000,
            contracts=1,
            point_value=250_000,
        )
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        initial_capital = engine.capital

        engine._open_position(
            code="101S6000",
            name="KOSPI200 Futures",
            side="BUY",
            price=350.0,
            timestamp=datetime(2024, 1, 2, 9, 0),
        )

        # Position should be created with 1 contract
        assert "101S6000" in engine.positions
        pos = engine.positions["101S6000"]
        assert pos.quantity == 1

        # Capital should NOT be deducted for futures (margin-based)
        assert engine.capital == initial_capital

    def test_open_futures_short_position(self):
        """Futures SELL (short) position should work."""
        config = BacktestConfig.futures(initial_capital=10_000_000)
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        engine._open_position(
            code="101S6000",
            name="KOSPI200 Futures",
            side="SELL",
            price=350.0,
            timestamp=datetime(2024, 1, 2, 9, 0),
        )

        assert "101S6000" in engine.positions
        assert engine.positions["101S6000"].side == "SELL"


# ---------------------------------------------------------------------------
# Tests: _close_position (Position Closing)
# ---------------------------------------------------------------------------


class TestClosePositionStock:
    """Tests for _close_position with stock configuration."""

    def test_close_buy_position_profit(self):
        """Closing a profitable BUY position should add to capital."""
        config = BacktestConfig.stock(initial_capital=10_000_000)
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        # Open position
        entry_price = 50000.0
        engine._open_position(
            code="005930",
            name="Samsung",
            side="BUY",
            price=entry_price,
            timestamp=datetime(2024, 1, 2, 9, 0),
        )

        capital_after_open = engine.capital
        pos = engine.positions["005930"]
        quantity = pos.quantity

        # Close with profit
        exit_price = 55000.0  # +10% gain
        engine._close_position(
            code="005930",
            exit_price=exit_price,
            exit_time=datetime(2024, 1, 2, 15, 0),
            reason=ExitReason.TAKE_PROFIT,
        )

        # Position should be removed
        assert "005930" not in engine.positions

        # Capital should increase (profit minus costs)
        assert engine.capital > capital_after_open

        # Trade should be recorded
        assert len(engine.trades) == 1
        trade = engine.trades[0]
        assert trade.code == "005930"
        assert trade.side == "BUY"
        assert trade.entry_price == entry_price
        assert trade.exit_price == exit_price
        assert trade.quantity == quantity
        assert trade.pnl > 0  # Profitable
        assert trade.exit_reason == "take_profit"

    def test_close_buy_position_loss(self):
        """Closing a losing BUY position should subtract from capital."""
        config = BacktestConfig.stock(initial_capital=10_000_000)
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        # Open position
        entry_price = 50000.0
        engine._open_position(
            code="005930",
            name="Samsung",
            side="BUY",
            price=entry_price,
            timestamp=datetime(2024, 1, 2, 9, 0),
        )

        capital_after_open = engine.capital

        # Close with loss
        exit_price = 45000.0  # -10% loss
        engine._close_position(
            code="005930",
            exit_price=exit_price,
            exit_time=datetime(2024, 1, 2, 15, 0),
            reason=ExitReason.STOP_LOSS,
        )

        # Capital should decrease (loss + costs)
        assert engine.capital < capital_after_open

        # Trade should show loss
        trade = engine.trades[0]
        assert trade.pnl < 0  # Loss

    def test_close_sell_position_profit(self):
        """Closing a profitable SELL (short) position should add to capital."""
        config = BacktestConfig.stock(initial_capital=10_000_000)
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        # Open short position
        entry_price = 50000.0
        engine._open_position(
            code="005930",
            name="Samsung",
            side="SELL",
            price=entry_price,
            timestamp=datetime(2024, 1, 2, 9, 0),
        )

        capital_after_open = engine.capital

        # Close short with profit (price went down)
        exit_price = 45000.0  # -10% = profit for short
        engine._close_position(
            code="005930",
            exit_price=exit_price,
            exit_time=datetime(2024, 1, 2, 15, 0),
            reason=ExitReason.TAKE_PROFIT,
        )

        # Capital should increase
        assert engine.capital > capital_after_open

        # Trade should be profitable
        trade = engine.trades[0]
        assert trade.side == "SELL"
        assert trade.pnl > 0  # Profit from short

    def test_close_sell_position_loss(self):
        """Closing a losing SELL (short) position should subtract from capital."""
        config = BacktestConfig.stock(initial_capital=10_000_000)
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        # Open short position
        entry_price = 50000.0
        engine._open_position(
            code="005930",
            name="Samsung",
            side="SELL",
            price=entry_price,
            timestamp=datetime(2024, 1, 2, 9, 0),
        )

        capital_after_open = engine.capital

        # Close short with loss (price went up)
        exit_price = 55000.0  # +10% = loss for short
        engine._close_position(
            code="005930",
            exit_price=exit_price,
            exit_time=datetime(2024, 1, 2, 15, 0),
            reason=ExitReason.STOP_LOSS,
        )

        # Capital should decrease
        assert engine.capital < capital_after_open

        # Trade should show loss
        trade = engine.trades[0]
        assert trade.pnl < 0  # Loss

    def test_commission_slippage_tax_applied_on_close(self):
        """Commission, slippage, and tax should be applied on position close."""
        cost = CostConfig.stock()  # Includes 0.23% tax
        config = BacktestConfig(
            initial_capital=10_000_000,
            position_size_pct=10.0,
            cost=cost,
        )
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        # Open position
        engine._open_position(
            code="005930",
            name="Samsung",
            side="BUY",
            price=50000.0,
            timestamp=datetime(2024, 1, 2, 9, 0),
        )

        pos = engine.positions["005930"]
        quantity = pos.quantity

        # Close position
        exit_price = 55000.0
        engine._close_position(
            code="005930",
            exit_price=exit_price,
            exit_time=datetime(2024, 1, 2, 15, 0),
            reason=ExitReason.SIGNAL,
        )

        # Calculate expected costs
        revenue = exit_price * quantity
        commission = revenue * cost.commission_rate
        slippage = revenue * cost.slippage_rate
        tax = revenue * cost.tax_rate  # 0.23% for stock sell
        total_cost = commission + slippage + tax

        # Trade should record commission + tax
        trade = engine.trades[0]
        expected_commission = commission + tax
        assert abs(trade.commission - expected_commission) < 1.0

    def test_pnl_calculation_accuracy_buy(self):
        """PnL calculation for BUY position should be accurate."""
        config = BacktestConfig.stock(
            initial_capital=10_000_000,
            position_size_pct=10.0,
        )
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        entry_price = 50000.0
        exit_price = 55000.0

        engine._open_position(
            code="005930",
            name="Samsung",
            side="BUY",
            price=entry_price,
            timestamp=datetime(2024, 1, 2, 9, 0),
        )

        pos = engine.positions["005930"]
        quantity = pos.quantity

        engine._close_position(
            code="005930",
            exit_price=exit_price,
            exit_time=datetime(2024, 1, 2, 15, 0),
            reason=ExitReason.SIGNAL,
        )

        # Calculate expected PnL
        revenue = exit_price * quantity
        cost_cfg = config.cost
        commission = revenue * cost_cfg.commission_rate
        slippage = revenue * cost_cfg.slippage_rate
        tax = revenue * cost_cfg.tax_rate
        total_cost = commission + slippage + tax
        net_revenue = revenue - total_cost

        expected_pnl = net_revenue - (entry_price * quantity)

        trade = engine.trades[0]
        assert abs(trade.pnl - expected_pnl) < 1.0  # Allow rounding difference

    def test_pnl_pct_calculation(self):
        """PnL percentage should be calculated correctly."""
        config = BacktestConfig.stock(initial_capital=10_000_000)
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        entry_price = 50000.0
        exit_price = 55000.0  # +10%

        engine._open_position(
            code="005930",
            name="Samsung",
            side="BUY",
            price=entry_price,
            timestamp=datetime(2024, 1, 2, 9, 0),
        )

        engine._close_position(
            code="005930",
            exit_price=exit_price,
            exit_time=datetime(2024, 1, 2, 15, 0),
            reason=ExitReason.SIGNAL,
        )

        trade = engine.trades[0]
        expected_pnl_pct = (exit_price - entry_price) / entry_price * 100
        assert abs(trade.pnl_pct - expected_pnl_pct) < 0.01

    def test_exit_reason_tracked(self):
        """Exit reason should be tracked in statistics."""
        config = BacktestConfig.stock(initial_capital=10_000_000)
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        # Open and close with specific reason
        engine._open_position(
            code="005930",
            name="Samsung",
            side="BUY",
            price=50000.0,
            timestamp=datetime(2024, 1, 2, 9, 0),
        )

        engine._close_position(
            code="005930",
            exit_price=55000.0,
            exit_time=datetime(2024, 1, 2, 15, 0),
            reason=ExitReason.TRAILING_STOP,
        )

        # Exit reason should be counted
        assert "trailing_stop" in engine.exit_reasons
        assert engine.exit_reasons["trailing_stop"] == 1

    def test_close_nonexistent_position_no_error(self):
        """Closing a non-existent position should be silently ignored."""
        config = BacktestConfig.stock(initial_capital=10_000_000)
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        # Try to close position that doesn't exist
        engine._close_position(
            code="999999",
            exit_price=50000.0,
            exit_time=datetime(2024, 1, 2, 15, 0),
            reason=ExitReason.SIGNAL,
        )

        # Should not crash, no trades recorded
        assert len(engine.trades) == 0


class TestClosePositionFutures:
    """Tests for _close_position with futures configuration."""

    def test_close_futures_buy_position_profit(self):
        """Closing a profitable futures BUY position should add PnL to capital."""
        config = BacktestConfig.futures(
            initial_capital=10_000_000,
            point_value=250_000,
        )
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        initial_capital = engine.capital

        # Open futures position
        entry_price = 350.0
        engine._open_position(
            code="101S6000",
            name="KOSPI200 Futures",
            side="BUY",
            price=entry_price,
            timestamp=datetime(2024, 1, 2, 9, 0),
        )

        # Capital unchanged after open (margin-based)
        assert engine.capital == initial_capital

        # Close with profit
        exit_price = 355.0  # +5 points
        engine._close_position(
            code="101S6000",
            exit_price=exit_price,
            exit_time=datetime(2024, 1, 2, 15, 0),
            reason=ExitReason.TAKE_PROFIT,
        )

        # Calculate expected PnL
        # (355 - 350) * 1 contract * 250,000 = 1,250,000
        point_diff = exit_price - entry_price
        gross_pnl = point_diff * 1 * 250_000

        # Subtract costs
        notional = exit_price * 1 * 250_000
        commission = notional * config.cost.commission_rate
        slippage = notional * config.cost.slippage_rate
        expected_pnl = gross_pnl - commission - slippage

        # Capital should increase by net PnL
        assert abs(engine.capital - (initial_capital + expected_pnl)) < 1.0

        # Trade should be recorded
        trade = engine.trades[0]
        assert trade.side == "BUY"
        assert abs(trade.pnl - expected_pnl) < 1.0

    def test_close_futures_sell_position_profit(self):
        """Closing a profitable futures SELL (short) position should add PnL."""
        config = BacktestConfig.futures(
            initial_capital=10_000_000,
            point_value=250_000,
        )
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        initial_capital = engine.capital

        # Open short futures position
        entry_price = 350.0
        engine._open_position(
            code="101S6000",
            name="KOSPI200 Futures",
            side="SELL",
            price=entry_price,
            timestamp=datetime(2024, 1, 2, 9, 0),
        )

        # Close short with profit (price went down)
        exit_price = 345.0  # -5 points = profit for short
        engine._close_position(
            code="101S6000",
            exit_price=exit_price,
            exit_time=datetime(2024, 1, 2, 15, 0),
            reason=ExitReason.TAKE_PROFIT,
        )

        # Calculate expected PnL for short
        # (350 - 345) * 1 * 250,000 = 1,250,000
        point_diff = entry_price - exit_price
        gross_pnl = point_diff * 1 * 250_000

        notional = exit_price * 1 * 250_000
        commission = notional * config.cost.commission_rate
        slippage = notional * config.cost.slippage_rate
        expected_pnl = gross_pnl - commission - slippage

        assert abs(engine.capital - (initial_capital + expected_pnl)) < 1.0

        trade = engine.trades[0]
        assert trade.side == "SELL"
        assert trade.pnl > 0  # Profitable short

    def test_close_futures_buy_position_loss(self):
        """Closing a losing futures BUY position should subtract PnL from capital."""
        config = BacktestConfig.futures(
            initial_capital=10_000_000,
            point_value=250_000,
        )
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        initial_capital = engine.capital

        # Open futures position
        entry_price = 350.0
        engine._open_position(
            code="101S6000",
            name="KOSPI200 Futures",
            side="BUY",
            price=entry_price,
            timestamp=datetime(2024, 1, 2, 9, 0),
        )

        # Close with loss
        exit_price = 345.0  # -5 points
        engine._close_position(
            code="101S6000",
            exit_price=exit_price,
            exit_time=datetime(2024, 1, 2, 15, 0),
            reason=ExitReason.STOP_LOSS,
        )

        # Capital should decrease
        assert engine.capital < initial_capital

        trade = engine.trades[0]
        assert trade.pnl < 0  # Loss

    def test_futures_commission_applied(self):
        """Futures commission should be lower than stocks."""
        config = BacktestConfig.futures(
            initial_capital=10_000_000,
            point_value=250_000,
        )
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        # Open and close
        engine._open_position(
            code="101S6000",
            name="KOSPI200 Futures",
            side="BUY",
            price=350.0,
            timestamp=datetime(2024, 1, 2, 9, 0),
        )

        engine._close_position(
            code="101S6000",
            exit_price=355.0,
            exit_time=datetime(2024, 1, 2, 15, 0),
            reason=ExitReason.SIGNAL,
        )

        trade = engine.trades[0]
        # Futures commission rate is 0.00003 (0.003%)
        notional = 355.0 * 1 * 250_000
        expected_commission = notional * 0.00003
        expected_slippage = notional * 0.0001
        expected_costs = expected_commission + expected_slippage

        # Commission field should only contain commission (no tax for futures)
        assert abs(trade.commission - expected_commission) < 1.0


class TestPositionLifecycle:
    """Integration tests for full position lifecycle (open → close)."""

    def test_multiple_positions_tracked_correctly(self):
        """Multiple simultaneous positions should be tracked independently."""
        config = BacktestConfig.stock(
            initial_capital=100_000_000,
            max_positions=5,
        )
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        # Open 3 positions
        codes = ["005930", "000660", "035420"]
        for i, code in enumerate(codes):
            engine._open_position(
                code=code,
                name=code,
                side="BUY",
                price=50000.0 + i * 10000,
                timestamp=datetime(2024, 1, 2, 9, i),
            )

        assert len(engine.positions) == 3

        # Close middle position
        engine._close_position(
            code="000660",
            exit_price=65000.0,
            exit_time=datetime(2024, 1, 2, 15, 0),
            reason=ExitReason.SIGNAL,
        )

        assert len(engine.positions) == 2
        assert "000660" not in engine.positions
        assert "005930" in engine.positions
        assert "035420" in engine.positions

    def test_capital_tracking_through_multiple_trades(self):
        """Capital should be accurately tracked through multiple trades."""
        config = BacktestConfig.stock(
            initial_capital=10_000_000,
            position_size_pct=20.0,  # 2M per trade
        )
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        initial_capital = engine.capital

        # Trade 1: Profit
        engine._open_position(
            code="005930",
            name="Samsung",
            side="BUY",
            price=50000.0,
            timestamp=datetime(2024, 1, 2, 9, 0),
        )
        engine._close_position(
            code="005930",
            exit_price=55000.0,
            exit_time=datetime(2024, 1, 2, 15, 0),
            reason=ExitReason.TAKE_PROFIT,
        )

        capital_after_trade1 = engine.capital
        assert capital_after_trade1 > initial_capital  # Made profit

        # Trade 2: Loss
        engine._open_position(
            code="000660",
            name="SK Hynix",
            side="BUY",
            price=100000.0,
            timestamp=datetime(2024, 1, 3, 9, 0),
        )
        engine._close_position(
            code="000660",
            exit_price=95000.0,
            exit_time=datetime(2024, 1, 3, 15, 0),
            reason=ExitReason.STOP_LOSS,
        )

        capital_after_trade2 = engine.capital
        assert capital_after_trade2 < capital_after_trade1  # Lost money

        # Net result should match trades
        total_pnl = sum(t.pnl for t in engine.trades)
        expected_capital = initial_capital + total_pnl
        assert abs(engine.capital - expected_capital) < 1.0

    def test_daily_trades_counter_incremented(self):
        """Daily trades counter should increment on position open."""
        config = BacktestConfig.stock(initial_capital=10_000_000)
        engine = BacktestEngine(_HoldStrategy(), config)
        engine._reset()

        assert engine._daily_trades == 0

        engine._open_position(
            code="005930",
            name="Samsung",
            side="BUY",
            price=50000.0,
            timestamp=datetime(2024, 1, 2, 9, 0),
        )

        assert engine._daily_trades == 1

        engine._open_position(
            code="000660",
            name="SK Hynix",
            side="BUY",
            price=100000.0,
            timestamp=datetime(2024, 1, 2, 9, 1),
        )

        assert engine._daily_trades == 2
