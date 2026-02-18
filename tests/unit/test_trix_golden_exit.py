"""Unit tests for shared/strategy/exit/trix_golden_exit.py

Tests TRIX Golden Exit strategy — stop loss, partial (50%) exit,
full exit (TRIX dead cross / 0-line cross), bearish divergence,
and EOD close.
"""

from __future__ import annotations

from datetime import datetime, time

import numpy as np
import pandas as pd
import pytest

from shared.indicators.momentum import calculate_all_momentum
from shared.models.position import Position, PositionSide, PositionState
from shared.models.signal import ExitReason
from shared.strategy.base import ExitContext
from shared.strategy.exit.trix_golden_exit import TrixGoldenExit, TrixGoldenExitConfig

# =============================================================================
# Helpers
# =============================================================================


def _make_ohlcv(close_values: list[float], volume: float = 10000.0) -> pd.DataFrame:
    n = len(close_values)
    return pd.DataFrame(
        {
            "open": close_values,
            "high": [c * 1.01 for c in close_values],
            "low": [c * 0.99 for c in close_values],
            "close": close_values,
            "volume": [volume] * n,
        }
    )


def _make_position(
    code: str = "005930",
    entry_price: float = 100.0,
    quantity: int = 100,
    side: PositionSide = PositionSide.LONG,
    pid: str = "test-pos-1",
) -> Position:
    return Position(
        id=pid,
        code=code,
        name="삼성전자",
        side=side,
        quantity=quantity,
        entry_price=entry_price,
        entry_time=datetime(2026, 3, 15, 10, 0, 0),
        current_price=entry_price,
        highest_price=entry_price,
        lowest_price=entry_price,
        state=PositionState.SURVIVAL,
        strategy="trix_golden",
    )


def _build_momentum_df(n: int = 80) -> pd.DataFrame:
    """Build a DataFrame with all momentum columns."""
    closes = np.linspace(100, 110, n).tolist()
    df = _make_ohlcv(closes)
    return calculate_all_momentum(df)


def _build_exit_market_data(
    code: str,
    current_price: float,
    df: pd.DataFrame,
) -> dict:
    """Build market_data dict for ExitContext."""
    return {
        code: {
            "close": current_price,
            "price": current_price,
            "momentum_5m": {
                "trix": float(df["trix"].iloc[-1]),
                "trix_signal": float(df["trix_signal"].iloc[-1]),
                "df": df,
            },
        }
    }


# =============================================================================
# Config validation tests
# =============================================================================


class TestTrixGoldenExitConfig:
    def test_defaults(self):
        config = TrixGoldenExitConfig()
        assert config.stop_loss_pct == -0.03
        assert config.partial_exit_ratio == 0.5

    def test_validate_positive_stop_loss_raises(self):
        config = TrixGoldenExitConfig(stop_loss_pct=0.03)
        with pytest.raises(ValueError, match="negative"):
            config.validate()

    def test_validate_bad_partial_ratio_raises(self):
        config = TrixGoldenExitConfig(partial_exit_ratio=1.0)
        with pytest.raises(ValueError, match="between 0 and 1"):
            config.validate()


# =============================================================================
# Stop Loss
# =============================================================================


class TestStopLoss:
    @pytest.mark.asyncio
    async def test_hard_stop_loss(self):
        """Price drops below stop_loss_pct → full exit."""
        exit_strategy = TrixGoldenExit(TrixGoldenExitConfig(stop_loss_pct=-0.03))
        position = _make_position(entry_price=100.0, quantity=100)

        # Price dropped 4% → below -3% threshold
        current_price = 96.0
        df = _build_momentum_df(80)
        market_data = _build_exit_market_data("005930", current_price, df)

        ctx = ExitContext(
            position=position,
            market_data=market_data,
            timestamp=datetime(2026, 3, 15, 11, 0, 0),
        )
        should_exit, signal = await exit_strategy.should_exit(ctx)

        assert should_exit is True
        assert signal is not None
        assert signal.reason == ExitReason.STOP_LOSS
        assert signal.quantity == 100  # Full exit
        assert signal.metadata.get("trigger") == "hard_stop"

    @pytest.mark.asyncio
    async def test_no_stop_loss_when_profitable(self):
        """Price above entry → no stop loss triggered."""
        exit_strategy = TrixGoldenExit(
            TrixGoldenExitConfig(stop_loss_pct=-0.03, use_swing_low_stop=False)
        )
        position = _make_position(entry_price=100.0, quantity=100)

        current_price = 105.0
        df = _build_momentum_df(80)
        # Force no other exit conditions
        n = len(df)
        df.loc[n - 2, "trix"] = 0.05
        df.loc[n - 2, "trix_signal"] = 0.04
        df.loc[n - 1, "trix"] = 0.06
        df.loc[n - 1, "trix_signal"] = 0.04  # No dead cross

        market_data = _build_exit_market_data("005930", current_price, df)
        ctx = ExitContext(
            position=position,
            market_data=market_data,
            timestamp=datetime(2026, 3, 15, 11, 0, 0),
        )
        should_exit, signal = await exit_strategy.should_exit(ctx)
        assert should_exit is False


# =============================================================================
# Partial Exit (50%)
# =============================================================================


class TestPartialExit:
    @pytest.mark.asyncio
    async def test_trix_peak_out_partial(self):
        """TRIX peak-out triggers partial (50%) exit."""
        config = TrixGoldenExitConfig(partial_exit_ratio=0.5, use_swing_low_stop=False)
        exit_strategy = TrixGoldenExit(config)
        position = _make_position(entry_price=100.0, quantity=100, pid="pos-partial")

        df = _build_momentum_df(80)
        n = len(df)

        # Set up: TRIX was rising (peak tracked), now declining
        # First register the peak by calling update_state
        df_peak = df.copy()
        df_peak.loc[n - 1, "trix"] = 0.10  # High TRIX
        df_peak.loc[n - 1, "trix_signal"] = 0.05
        peak_data = _build_exit_market_data("005930", 105.0, df_peak)
        ctx_peak = ExitContext(
            position=position,
            market_data=peak_data,
            timestamp=datetime(2026, 3, 15, 10, 30, 0),
        )
        exit_strategy.update_state(ctx_peak)

        # Now TRIX is declining past peak
        df_decline = df.copy()
        df_decline.loc[n - 2, "trix"] = 0.08
        df_decline.loc[n - 2, "trix_signal"] = 0.05
        df_decline.loc[n - 1, "trix"] = 0.06  # Declining, below peak 0.10
        df_decline.loc[n - 1, "trix_signal"] = 0.05

        # Ensure no dead cross or 0-line cross
        df_decline.loc[n - 2, "trix_signal"] = 0.05

        current_price = 105.0  # In profit
        market_data = _build_exit_market_data("005930", current_price, df_decline)

        ctx = ExitContext(
            position=position,
            market_data=market_data,
            timestamp=datetime(2026, 3, 15, 11, 0, 0),
        )
        should_exit, signal = await exit_strategy.should_exit(ctx)

        assert should_exit is True
        assert signal is not None
        assert signal.quantity == 50  # 100 * 0.5
        assert signal.metadata.get("partial") is True
        assert signal.metadata.get("trigger") == "trix_peak_out"

    @pytest.mark.asyncio
    async def test_partial_exit_only_in_profit(self):
        """Partial exit only triggers when position is in profit."""
        config = TrixGoldenExitConfig(partial_exit_ratio=0.5, use_swing_low_stop=False)
        exit_strategy = TrixGoldenExit(config)
        position = _make_position(entry_price=100.0, quantity=100, pid="pos-loss")

        df = _build_momentum_df(80)
        n = len(df)

        # Set up peak
        exit_strategy._trix_peak["pos-loss"] = 0.10

        # TRIX declining but position is at a loss
        df.loc[n - 2, "trix"] = 0.08
        df.loc[n - 1, "trix"] = 0.06
        df.loc[n - 2, "trix_signal"] = 0.05
        df.loc[n - 1, "trix_signal"] = 0.05

        current_price = 98.0  # Below entry → loss
        market_data = _build_exit_market_data("005930", current_price, df)
        ctx = ExitContext(
            position=position,
            market_data=market_data,
            timestamp=datetime(2026, 3, 15, 11, 0, 0),
        )
        should_exit, signal = await exit_strategy.should_exit(ctx)
        # Should not fire partial (may fire stop loss only if below threshold)
        if should_exit:
            assert signal.metadata.get("partial") is not True

    @pytest.mark.asyncio
    async def test_no_second_partial(self):
        """After partial exit, no second partial (goes to full exit check)."""
        config = TrixGoldenExitConfig(partial_exit_ratio=0.5, use_swing_low_stop=False)
        exit_strategy = TrixGoldenExit(config)
        pid = "pos-already-partial"
        exit_strategy._partial_exited[pid] = True  # Already done

        position = _make_position(entry_price=100.0, quantity=50, pid=pid)
        df = _build_momentum_df(80)
        n = len(df)

        # TRIX declining but not dead cross
        df.loc[n - 2, "trix"] = 0.05
        df.loc[n - 2, "trix_signal"] = 0.04
        df.loc[n - 1, "trix"] = 0.045
        df.loc[n - 1, "trix_signal"] = 0.04

        current_price = 105.0
        market_data = _build_exit_market_data("005930", current_price, df)
        ctx = ExitContext(
            position=position,
            market_data=market_data,
            timestamp=datetime(2026, 3, 15, 11, 0, 0),
        )
        should_exit, signal = await exit_strategy.should_exit(ctx)
        # Not a dead cross so should not fire full exit either
        assert should_exit is False


# =============================================================================
# Full Exit (TRIX Dead Cross / 0-line)
# =============================================================================


class TestFullExit:
    @pytest.mark.asyncio
    async def test_trix_dead_cross_full_exit(self):
        """TRIX dead cross → full exit."""
        exit_strategy = TrixGoldenExit(TrixGoldenExitConfig(use_swing_low_stop=False))
        exit_strategy._partial_exited["pos-dc"] = True  # Skip partial
        position = _make_position(entry_price=100.0, quantity=50, pid="pos-dc")

        df = _build_momentum_df(80)
        n = len(df)

        # Dead cross: prev TRIX >= signal, cur TRIX < signal
        df.loc[n - 2, "trix"] = 0.05
        df.loc[n - 2, "trix_signal"] = 0.05
        df.loc[n - 1, "trix"] = 0.03
        df.loc[n - 1, "trix_signal"] = 0.05

        current_price = 102.0
        market_data = _build_exit_market_data("005930", current_price, df)
        ctx = ExitContext(
            position=position,
            market_data=market_data,
            timestamp=datetime(2026, 3, 15, 11, 0, 0),
        )
        should_exit, signal = await exit_strategy.should_exit(ctx)

        assert should_exit is True
        assert signal is not None
        assert signal.quantity == 50  # All remaining
        assert signal.metadata.get("trigger") == "trix_dead_cross"

    @pytest.mark.asyncio
    async def test_trix_zero_line_cross_full_exit(self):
        """TRIX crosses below 0 → full exit."""
        exit_strategy = TrixGoldenExit(TrixGoldenExitConfig(use_swing_low_stop=False))
        exit_strategy._partial_exited["pos-zc"] = True
        position = _make_position(entry_price=100.0, quantity=50, pid="pos-zc")

        df = _build_momentum_df(80)
        n = len(df)

        # 0-line cross: prev TRIX >= 0, cur TRIX < 0, but no dead cross
        df.loc[n - 2, "trix"] = 0.01
        df.loc[n - 2, "trix_signal"] = 0.05
        df.loc[n - 1, "trix"] = -0.01
        df.loc[n - 1, "trix_signal"] = 0.04

        current_price = 101.0
        market_data = _build_exit_market_data("005930", current_price, df)
        ctx = ExitContext(
            position=position,
            market_data=market_data,
            timestamp=datetime(2026, 3, 15, 11, 0, 0),
        )
        should_exit, signal = await exit_strategy.should_exit(ctx)

        assert should_exit is True
        assert signal is not None
        # Could match dead cross first (since trix < signal is also new here)
        # Both are full exits — either trigger is fine
        assert signal.quantity == 50


# =============================================================================
# EOD Close
# =============================================================================


class TestEODClose:
    @pytest.mark.asyncio
    async def test_eod_full_close(self):
        """After EOD time → full close."""
        config = TrixGoldenExitConfig(
            eod_close_enabled=True,
            eod_close_hour=15,
            eod_close_minute=15,
            use_swing_low_stop=False,
        )
        exit_strategy = TrixGoldenExit(config)
        position = _make_position(entry_price=100.0, quantity=100)

        df = _build_momentum_df(80)
        current_price = 102.0
        market_data = _build_exit_market_data("005930", current_price, df)

        # 15:20 — past EOD
        ctx = ExitContext(
            position=position,
            market_data=market_data,
            timestamp=datetime(2026, 3, 15, 15, 20, 0),
        )
        should_exit, signal = await exit_strategy.should_exit(ctx)

        assert should_exit is True
        assert signal.reason == ExitReason.EOD_CLOSE
        assert signal.quantity == 100

    @pytest.mark.asyncio
    async def test_no_eod_when_disabled(self):
        """eod_close_enabled=False → no EOD close."""
        config = TrixGoldenExitConfig(eod_close_enabled=False, use_swing_low_stop=False)
        exit_strategy = TrixGoldenExit(config)
        position = _make_position(entry_price=100.0, quantity=100)

        df = _build_momentum_df(80)
        n = len(df)
        # Ensure no other exit triggers
        df.loc[n - 2, "trix"] = 0.05
        df.loc[n - 2, "trix_signal"] = 0.04
        df.loc[n - 1, "trix"] = 0.06
        df.loc[n - 1, "trix_signal"] = 0.04

        current_price = 102.0
        market_data = _build_exit_market_data("005930", current_price, df)
        ctx = ExitContext(
            position=position,
            market_data=market_data,
            timestamp=datetime(2026, 3, 15, 15, 20, 0),
        )
        should_exit, signal = await exit_strategy.should_exit(ctx)
        assert should_exit is False


# =============================================================================
# Bearish Divergence
# =============================================================================


class TestBearishDivergence:
    @pytest.mark.asyncio
    async def test_divergence_triggers_full_exit(self):
        """Bearish divergence → immediate full exit (highest priority)."""
        config = TrixGoldenExitConfig(divergence_lookback=20)
        exit_strategy = TrixGoldenExit(config)
        position = _make_position(entry_price=100.0, quantity=100)

        # Build a df with bearish divergence pattern
        n = 80
        closes = [100.0] * n
        for i in range(n):
            closes[i] = 100.0 + np.sin(i * 0.15) * 5

        df = _make_ohlcv(closes)
        df = calculate_all_momentum(df)

        # Manually inject bearish divergence in last 20 bars:
        # Price: higher highs, TRIX: lower highs
        base = n - 20
        for j in range(20):
            idx = base + j
            if j == 5:
                df.loc[idx, "close"] = 110.0
                df.loc[idx, "trix"] = 0.10
            elif j == 15:
                df.loc[idx, "close"] = 115.0  # Higher high
                df.loc[idx, "trix"] = 0.05  # Lower high (divergence)
            elif j in (4, 6, 14, 16):
                df.loc[idx, "close"] = 105.0
                df.loc[idx, "trix"] = 0.03
            else:
                df.loc[idx, "close"] = 102.0
                df.loc[idx, "trix"] = 0.02

        current_price = 105.0
        market_data = _build_exit_market_data("005930", current_price, df)
        ctx = ExitContext(
            position=position,
            market_data=market_data,
            timestamp=datetime(2026, 3, 15, 11, 0, 0),
        )
        should_exit, signal = await exit_strategy.should_exit(ctx)

        assert should_exit is True
        assert signal is not None
        assert signal.reason == ExitReason.INDICATOR_EXIT
        assert signal.metadata.get("trigger") == "bearish_divergence"
        assert signal.quantity == 100  # Full exit


# =============================================================================
# Cleanup
# =============================================================================


class TestCleanup:
    def test_cleanup_position(self):
        """cleanup_position removes all tracking state."""
        exit_strategy = TrixGoldenExit(TrixGoldenExitConfig())
        pid = "cleanup-test"
        exit_strategy._partial_exited[pid] = True
        exit_strategy._trix_peak[pid] = 0.15
        exit_strategy._rsi_was_overbought[pid] = True

        exit_strategy.cleanup_position(pid)

        assert pid not in exit_strategy._partial_exited
        assert pid not in exit_strategy._trix_peak
        assert pid not in exit_strategy._rsi_was_overbought

    def test_cleanup_nonexistent_noop(self):
        """Cleaning up an unknown position should not raise."""
        exit_strategy = TrixGoldenExit(TrixGoldenExitConfig())
        exit_strategy.cleanup_position("nonexistent")  # Should not raise
