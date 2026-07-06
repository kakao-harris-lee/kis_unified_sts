"""Unit tests for shared/indicators/momentum.py

Tests TRIX, CCI, MACD, Stochastic, RSI, OBV calculators and
DivergenceDetector with known-input / known-output verification.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from shared.indicators.momentum import (
    CCICalculator,
    DivergenceDetector,
    MACDCalculator,
    OBVDataFrameCalculator,
    RSICalculator,
    StochasticCalculator,
    TRIXCalculator,
    calculate_all_momentum,
)

# =============================================================================
# TRIX Calculator
# =============================================================================


def _make_ohlcv(close_values: list[float], volume: float = 1000.0) -> pd.DataFrame:
    """Helper: build a minimal OHLCV DataFrame from close values."""
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


class TestTRIXCalculator:
    def test_adds_columns(self):
        """TRIX calculator adds trix and trix_signal columns."""
        df = _make_ohlcv(list(range(1, 61)))
        calc = TRIXCalculator(n=12, signal=9)
        result = calc.calculate(df.copy())
        assert "trix" in result.columns
        assert "trix_signal" in result.columns

    def test_trix_values_are_finite(self):
        """TRIX values should be finite for reasonable input (after row 0)."""
        closes = np.linspace(100, 120, 100).tolist()
        df = _make_ohlcv(closes)
        result = TRIXCalculator(n=12, signal=9).calculate(df)
        # Row 0 is NaN due to shift(1), remaining rows must be finite
        assert result["trix"].iloc[1:].isna().sum() == 0
        assert np.all(np.isfinite(result["trix"].iloc[1:].values))

    def test_constant_price_trix_near_zero(self):
        """For constant price, TRIX should be near zero."""
        df = _make_ohlcv([100.0] * 100)
        result = TRIXCalculator(n=12, signal=9).calculate(df)
        # After warm-up, TRIX should be ~0
        assert abs(result["trix"].iloc[-1]) < 0.001

    def test_uptrend_positive_trix(self):
        """Steady uptrend should produce positive TRIX values (after warm-up)."""
        closes = np.linspace(100, 200, 120).tolist()
        df = _make_ohlcv(closes)
        result = TRIXCalculator(n=12, signal=9).calculate(df)
        # Last 10 bars should be positive
        assert all(result["trix"].iloc[-10:] > 0)


# =============================================================================
# CCI Calculator
# =============================================================================


class TestCCICalculator:
    def test_adds_column(self):
        df = _make_ohlcv(list(range(50, 100)))
        result = CCICalculator(period=9).calculate(df.copy())
        assert "cci" in result.columns

    def test_constant_cci_zero(self):
        """CCI should be 0 for constant price (no deviation)."""
        df = _make_ohlcv([100.0] * 50)
        # override high/low to match close for true constant
        df["high"] = 100.0
        df["low"] = 100.0
        result = CCICalculator(period=9).calculate(df)
        # CCI should be very close to 0
        assert abs(result["cci"].iloc[-1]) < 1.0

    def test_cci_finite(self):
        closes = np.random.default_rng(42).normal(100, 5, 100).tolist()
        df = _make_ohlcv(closes)
        result = CCICalculator(period=9).calculate(df)
        assert result["cci"].isna().sum() == 0


# =============================================================================
# MACD Calculator
# =============================================================================


class TestMACDCalculator:
    def test_adds_columns(self):
        df = _make_ohlcv(list(range(1, 61)))
        result = MACDCalculator(fast=12, slow=26, signal=9).calculate(df.copy())
        assert "macd_line" in result.columns
        assert "macd_signal" in result.columns
        assert "macd_oscillator" in result.columns

    def test_macd_oscillator_is_diff(self):
        """MACD oscillator = MACD line - signal."""
        df = _make_ohlcv(np.linspace(100, 130, 60).tolist())
        result = MACDCalculator(fast=12, slow=26, signal=9).calculate(df)
        diff = result["macd_line"] - result["macd_signal"]
        np.testing.assert_allclose(
            result["macd_oscillator"].values, diff.values, atol=1e-10
        )

    def test_constant_macd_zero(self):
        """Constant price → all MACD values ~0."""
        df = _make_ohlcv([50.0] * 60)
        result = MACDCalculator().calculate(df)
        assert abs(result["macd_line"].iloc[-1]) < 0.01
        assert abs(result["macd_oscillator"].iloc[-1]) < 0.01


# =============================================================================
# Stochastic Calculator
# =============================================================================


class TestStochasticCalculator:
    def test_adds_columns(self):
        df = _make_ohlcv(list(range(50, 100)))
        result = StochasticCalculator(12, 5, 5).calculate(df.copy())
        assert "sto_k" in result.columns
        assert "sto_d" in result.columns

    def test_stochastic_range(self):
        """Stochastic %K and %D should be 0~100."""
        rng = np.random.default_rng(42)
        closes = rng.normal(100, 10, 120).tolist()
        df = _make_ohlcv(closes)
        result = StochasticCalculator(12, 5, 5).calculate(df)
        assert result["sto_k"].min() >= -0.01  # Allow minor float drift
        assert result["sto_k"].max() <= 100.01
        assert result["sto_d"].min() >= -0.01
        assert result["sto_d"].max() <= 100.01

    def test_constant_price_stochastic_neutral(self):
        """Constant price → %K ~ 50 (denominator=0 branch)."""
        df = _make_ohlcv([100.0] * 50)
        df["high"] = 100.0
        df["low"] = 100.0
        result = StochasticCalculator(12, 5, 5).calculate(df)
        # Should use neutral 50 when range is 0
        assert result["sto_k"].iloc[-1] == pytest.approx(50.0)


# =============================================================================
# RSI Calculator
# =============================================================================


class TestRSICalculator:
    def test_adds_column(self):
        df = _make_ohlcv(list(range(50, 100)))
        result = RSICalculator(period=14).calculate(df.copy())
        assert "rsi" in result.columns

    def test_rsi_range(self):
        """RSI should be in [0, 100]."""
        rng = np.random.default_rng(123)
        closes = rng.uniform(80, 120, 100).tolist()
        df = _make_ohlcv(closes)
        result = RSICalculator(period=14).calculate(df)
        assert result["rsi"].min() >= -0.01
        assert result["rsi"].max() <= 100.01

    def test_all_up_rsi_high(self):
        """Mostly increasing with tiny noise → RSI near 100."""
        rng = np.random.default_rng(99)
        base = np.linspace(100, 200, 50)
        # Add tiny noise so loss isn't exactly zero (avoids 0/0 edge)
        noisy = base + rng.normal(0, 0.01, 50)
        df = _make_ohlcv(noisy.tolist())
        result = RSICalculator(period=14).calculate(df)
        assert result["rsi"].iloc[-1] > 90


# =============================================================================
# OBV Calculator
# =============================================================================


class TestOBVCalculator:
    def test_adds_column(self):
        df = _make_ohlcv([100, 101, 102, 101, 103])
        result = OBVDataFrameCalculator().calculate(df.copy())
        assert "obv" in result.columns

    def test_obv_up_down(self):
        """OBV sums +volume when close goes up, -volume when down."""
        df = pd.DataFrame(
            {
                "close": [100, 102, 101, 104],
                "volume": [1000, 2000, 1500, 3000],
            }
        )
        result = OBVDataFrameCalculator().calculate(df)
        # Bar 0: direction=0 → cumsum starts at 0
        # Bar 1: +2000 → 2000
        # Bar 2: -1500 → 500
        # Bar 3: +3000 → 3500
        expected = [0, 2000, 500, 3500]
        np.testing.assert_array_equal(result["obv"].values, expected)


# =============================================================================
# DivergenceDetector
# =============================================================================


class TestDivergenceDetector:
    def test_bearish_divergence(self):
        """Price higher highs + indicator lower highs ⇒ bearish."""
        # Construct pattern with two peaks:
        # Peak 1 at ~index 5, Peak 2 at ~index 15 (higher price, lower indicator)
        n = 20
        prices = np.zeros(n)
        indicators = np.zeros(n)

        # Up-down-up-down pattern with rising price peaks
        for i in range(n):
            if i == 5:
                prices[i] = 110  # First peak
                indicators[i] = 50
            elif i == 15:
                prices[i] = 120  # Higher high
                indicators[i] = 40  # Lower high
            elif i == 4 or i == 6:
                prices[i] = 100
                indicators[i] = 40
            elif i == 14 or i == 16:
                prices[i] = 105
                indicators[i] = 30
            else:
                prices[i] = 95
                indicators[i] = 25

        detector = DivergenceDetector(lookback=20, min_peaks=2)
        result = detector.detect_bearish(pd.Series(prices), pd.Series(indicators))
        assert result is True

    def test_no_bearish_when_price_falling(self):
        """Price falling + indicator falling ⇒ not bearish divergence."""
        n = 20
        prices = np.zeros(n)
        indicators = np.zeros(n)

        for i in range(n):
            if i == 5:
                prices[i] = 120
                indicators[i] = 50
            elif i == 15:
                prices[i] = 110  # Lower high ← no divergence
                indicators[i] = 40
            elif i in (4, 6):
                prices[i] = 100
                indicators[i] = 40
            elif i in (14, 16):
                prices[i] = 100
                indicators[i] = 30
            else:
                prices[i] = 95
                indicators[i] = 25

        detector = DivergenceDetector(lookback=20, min_peaks=2)
        assert (
            detector.detect_bearish(pd.Series(prices), pd.Series(indicators)) is False
        )

    def test_bullish_divergence(self):
        """Price lower lows + indicator higher lows ⇒ bullish."""
        n = 20
        prices = np.zeros(n)
        indicators = np.zeros(n)

        for i in range(n):
            if i == 5:
                prices[i] = 80  # First trough
                indicators[i] = 20
            elif i == 15:
                prices[i] = 70  # Lower low
                indicators[i] = 30  # Higher low
            elif i in (4, 6):
                prices[i] = 90
                indicators[i] = 30
            elif i in (14, 16):
                prices[i] = 85
                indicators[i] = 40
            else:
                prices[i] = 100
                indicators[i] = 50

        detector = DivergenceDetector(lookback=20, min_peaks=2)
        assert detector.detect_bullish(pd.Series(prices), pd.Series(indicators)) is True

    def test_insufficient_data(self):
        """Short series ⇒ no divergence."""
        detector = DivergenceDetector(lookback=20)
        short = pd.Series([1.0, 2.0])
        assert detector.detect_bearish(short, short) is False
        assert detector.detect_bullish(short, short) is False


# =============================================================================
# calculate_all_momentum convenience function
# =============================================================================


class TestCalculateAllMomentum:
    def test_all_columns_present(self):
        """calculate_all_momentum adds all expected indicator columns."""
        df = _make_ohlcv(np.linspace(100, 130, 80).tolist())
        result = calculate_all_momentum(df)
        expected_cols = [
            "trix",
            "trix_signal",
            "cci",
            "macd_line",
            "macd_signal",
            "macd_oscillator",
            "sto_k",
            "sto_d",
            "obv",
            "rsi",
        ]
        for col in expected_cols:
            assert col in result.columns, f"Missing column: {col}"

    def test_no_nans_in_tail(self):
        """Last rows should not contain NaN for any indicator."""
        df = _make_ohlcv(np.linspace(100, 150, 120).tolist())
        result = calculate_all_momentum(df)
        tail = result.iloc[-5:]
        cols = [
            "trix",
            "trix_signal",
            "cci",
            "macd_oscillator",
            "sto_k",
            "sto_d",
            "rsi",
        ]
        for col in cols:
            assert tail[col].isna().sum() == 0, f"NaN in {col}"

    def test_without_obv_rsi(self):
        """Can skip OBV and RSI columns."""
        df = _make_ohlcv(np.linspace(100, 130, 80).tolist())
        result = calculate_all_momentum(df, include_obv=False, include_rsi=False)
        assert "obv" not in result.columns
        assert "rsi" not in result.columns
        # Core columns still present
        assert "trix" in result.columns
        assert "macd_oscillator" in result.columns
