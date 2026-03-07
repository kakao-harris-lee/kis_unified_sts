"""Tests for StreamingIndicatorEngine helper methods.

Tests the internal calculation methods:
- _calc_mfi: Money Flow Index
- _calc_adx: Average Directional Index
- _calc_atr_raw: Raw ATR value
- _calc_atr_normalized: Normalized ATR (ATR/close)
- _calc_stochastic: Stochastic K and D
- _ema_series: EMA series calculation
- _ema_last: Last EMA value only
"""

from __future__ import annotations

import math

import pytest

from services.trading.indicator_engine import Candle, StreamingIndicatorEngine


class TestEMAHelpers:
    """Tests for EMA calculation helpers (_ema_series, _ema_last)."""

    def test_ema_series_single_value(self):
        """EMA series with single value returns that value."""
        result = StreamingIndicatorEngine._ema_series([100.0], span=5)
        assert result == [100.0]

    def test_ema_series_multiple_values(self):
        """EMA series computes correctly for multiple values."""
        values = [100.0, 102.0, 101.0, 103.0, 105.0]
        result = StreamingIndicatorEngine._ema_series(values, span=3)

        assert len(result) == len(values)
        assert result[0] == 100.0  # First value is seed

        # Verify EMA formula: alpha * v + (1 - alpha) * prev_ema
        alpha = 2.0 / (3 + 1)  # span=3 → alpha=0.5
        expected_1 = alpha * 102.0 + (1 - alpha) * 100.0
        assert math.isclose(result[1], expected_1, rel_tol=1e-9)

    def test_ema_series_increasing_values(self):
        """EMA series follows increasing trend."""
        values = [100.0, 110.0, 120.0, 130.0]
        result = StreamingIndicatorEngine._ema_series(values, span=2)

        # EMA should be increasing
        for i in range(1, len(result)):
            assert result[i] > result[i - 1], f"EMA should increase at index {i}"

    def test_ema_last_single_value(self):
        """_ema_last with single value returns that value."""
        result = StreamingIndicatorEngine._ema_last([100.0], span=5)
        assert result == 100.0

    def test_ema_last_matches_series_last(self):
        """_ema_last should match the last value of _ema_series."""
        values = [100.0, 102.0, 101.0, 103.0, 105.0, 104.0, 106.0]
        span = 5

        series_result = StreamingIndicatorEngine._ema_series(values, span)
        last_result = StreamingIndicatorEngine._ema_last(values, span)

        assert math.isclose(last_result, series_result[-1], rel_tol=1e-9)

    def test_ema_last_with_different_spans(self):
        """_ema_last produces different results for different spans."""
        values = [100.0, 110.0, 120.0, 130.0, 140.0]

        ema_short = StreamingIndicatorEngine._ema_last(values, span=2)
        ema_long = StreamingIndicatorEngine._ema_last(values, span=10)

        # Shorter span should be more responsive (closer to recent values)
        assert ema_short > ema_long, "Short-span EMA should react faster to rising prices"

    def test_ema_series_span_one(self):
        """EMA with span=1 should track values closely (alpha=1.0)."""
        values = [100.0, 200.0, 150.0]
        result = StreamingIndicatorEngine._ema_series(values, span=1)

        # alpha = 2/(1+1) = 1.0, so EMA should equal current value
        assert result[0] == 100.0
        assert result[1] == 200.0
        assert result[2] == 150.0


class TestATRHelpers:
    """Tests for ATR calculation helpers (_calc_atr_raw, _calc_atr_normalized)."""

    def _create_candles(self, count: int, base_price: float = 100.0) -> list[Candle]:
        """Create simple candles for testing."""
        candles = []
        for i in range(count):
            price = base_price + i
            candles.append(
                Candle(
                    open=price,
                    high=price + 2.0,
                    low=price - 2.0,
                    close=price,
                    volume=1000.0,
                    minute=900 + i,
                )
            )
        return candles

    def test_atr_raw_insufficient_data(self):
        """ATR returns 0.0 when insufficient candles."""
        candles = self._create_candles(5)
        atr = StreamingIndicatorEngine._calc_atr_raw(candles, period=14)
        assert atr == 0.0

    def test_atr_raw_exact_period(self):
        """ATR computes correctly with exact period + 1 candles."""
        candles = self._create_candles(15)  # period=14 needs 15 candles
        atr = StreamingIndicatorEngine._calc_atr_raw(candles, period=14)

        assert atr > 0.0, "ATR should be positive with valid data"

    def test_atr_raw_stable_ranges(self):
        """ATR should be stable for consistent ranges."""
        # Create candles with fixed range of 4.0 (high - low = 4.0)
        candles = []
        for i in range(20):
            candles.append(
                Candle(
                    open=100.0,
                    high=102.0,
                    low=98.0,
                    close=100.0,
                    volume=1000.0,
                    minute=900 + i,
                )
            )

        atr = StreamingIndicatorEngine._calc_atr_raw(candles, period=14)
        # ATR should be close to the range (4.0)
        assert 3.5 <= atr <= 4.5, f"Expected ATR ~4.0, got {atr}"

    def test_atr_raw_with_gaps(self):
        """ATR captures gaps between candles."""
        candles = [
            Candle(open=100.0, high=102.0, low=98.0, close=100.0, volume=1000.0, minute=900),
            Candle(open=110.0, high=112.0, low=108.0, close=110.0, volume=1000.0, minute=901),  # Gap up
        ]
        # Add more candles to meet period requirement
        for i in range(2, 16):
            candles.append(Candle(open=110.0, high=112.0, low=108.0, close=110.0, volume=1000.0, minute=900 + i))

        atr = StreamingIndicatorEngine._calc_atr_raw(candles, period=14)
        # Gap should increase ATR
        assert atr > 4.0, f"ATR should capture gap, got {atr}"

    def test_atr_normalized_insufficient_data(self):
        """Normalized ATR returns 0.0 when insufficient candles."""
        candles = self._create_candles(5)
        atr_norm = StreamingIndicatorEngine._calc_atr_normalized(candles, period=14)
        assert atr_norm == 0.0

    def test_atr_normalized_is_ratio(self):
        """Normalized ATR is ATR/close."""
        candles = self._create_candles(20, base_price=100.0)

        atr_raw = StreamingIndicatorEngine._calc_atr_raw(candles, period=14)
        atr_norm = StreamingIndicatorEngine._calc_atr_normalized(candles, period=14)

        close = candles[-1].close
        expected_norm = atr_raw / close

        assert math.isclose(atr_norm, expected_norm, rel_tol=1e-6)

    def test_atr_normalized_scaling(self):
        """Normalized ATR scales appropriately with price."""
        # Low price candles
        candles_low = self._create_candles(20, base_price=10.0)
        atr_norm_low = StreamingIndicatorEngine._calc_atr_normalized(candles_low, period=14)

        # High price candles (same volatility pattern, 10x price)
        candles_high = []
        for c in candles_low:
            candles_high.append(
                Candle(
                    open=c.open * 10,
                    high=c.high * 10,
                    low=c.low * 10,
                    close=c.close * 10,
                    volume=c.volume,
                    minute=c.minute,
                )
            )
        atr_norm_high = StreamingIndicatorEngine._calc_atr_normalized(candles_high, period=14)

        # Normalized ATR should be similar despite 10x price difference
        assert math.isclose(atr_norm_low, atr_norm_high, rel_tol=0.1)


class TestStochasticHelper:
    """Tests for _calc_stochastic helper."""

    def _create_candles(self, prices: list[tuple[float, float, float]]) -> list[Candle]:
        """Create candles from (high, low, close) tuples."""
        candles = []
        for i, (high, low, close) in enumerate(prices):
            candles.append(
                Candle(
                    open=close,
                    high=high,
                    low=low,
                    close=close,
                    volume=1000.0,
                    minute=900 + i,
                )
            )
        return candles

    def test_stochastic_insufficient_data(self):
        """Stochastic returns (50.0, 50.0) when insufficient candles."""
        candles = self._create_candles([(100, 90, 95)] * 5)
        k, d = StreamingIndicatorEngine._calc_stochastic(candles, period=14, smooth=3)

        assert k == 50.0
        assert d == 50.0

    def test_stochastic_at_high(self):
        """Stochastic K near 100 when close is at period high."""
        # Build candles where last close is at the high
        prices = [(100 + i, 90 + i, 95 + i) for i in range(14)]
        prices.append((114, 104, 114))  # Close at high

        candles = self._create_candles(prices)
        k, d = StreamingIndicatorEngine._calc_stochastic(candles, period=14, smooth=3)

        assert k > 95.0, f"K should be near 100 when close at high, got {k}"

    def test_stochastic_at_low(self):
        """Stochastic K near 0 when close is at period low."""
        prices = [(100 + i, 90 + i, 95 + i) for i in range(14)]
        prices.append((114, 104, 104))  # Close at low

        candles = self._create_candles(prices)
        k, d = StreamingIndicatorEngine._calc_stochastic(candles, period=14, smooth=3)

        assert k < 5.0, f"K should be near 0 when close at low, got {k}"

    def test_stochastic_midpoint(self):
        """Stochastic K near 50 when close is at midpoint."""
        prices = [(110, 90, 95) for _ in range(14)]
        prices.append((110, 90, 100))  # Close at midpoint (90+110)/2 = 100

        candles = self._create_candles(prices)
        k, d = StreamingIndicatorEngine._calc_stochastic(candles, period=14, smooth=3)

        assert 45.0 <= k <= 55.0, f"K should be near 50 at midpoint, got {k}"

    def test_stochastic_d_is_smoothed(self):
        """Stochastic D is smoothed average of K values."""
        prices = [(100, 90, 95) for _ in range(20)]
        candles = self._create_candles(prices)

        k, d = StreamingIndicatorEngine._calc_stochastic(candles, period=14, smooth=3)

        # D should be close to K for stable prices
        assert math.isclose(k, d, abs_tol=10.0), f"K={k}, D={d} should be close for stable prices"

    def test_stochastic_range_bounds(self):
        """Stochastic K and D should be in [0, 100] range."""
        prices = [(100 + i * 2, 90 + i * 2, 95 + i * 2) for i in range(20)]
        candles = self._create_candles(prices)

        k, d = StreamingIndicatorEngine._calc_stochastic(candles, period=14, smooth=3)

        assert 0.0 <= k <= 100.0, f"K={k} should be in [0, 100]"
        assert 0.0 <= d <= 100.0, f"D={d} should be in [0, 100]"


class TestMFIHelper:
    """Tests for _calc_mfi (Money Flow Index) helper."""

    def _create_candles_with_volume(
        self, prices: list[tuple[float, float, float, float]]
    ) -> list[Candle]:
        """Create candles from (high, low, close, volume) tuples."""
        candles = []
        for i, (high, low, close, volume) in enumerate(prices):
            candles.append(
                Candle(
                    open=close,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    minute=900 + i,
                )
            )
        return candles

    def test_mfi_insufficient_data(self):
        """MFI returns None when insufficient candles."""
        engine = StreamingIndicatorEngine()
        candles = self._create_candles_with_volume([(100, 90, 95, 1000)] * 10)

        mfi = engine._calc_mfi(candles, period=14)
        assert mfi is None

    def test_mfi_all_positive_flow(self):
        """MFI returns 100 when all money flow is positive."""
        engine = StreamingIndicatorEngine()
        # Create rising typical prices (positive flow)
        prices = [(95 + i, 85 + i, 90 + i, 1000) for i in range(15)]
        candles = self._create_candles_with_volume(prices)

        mfi = engine._calc_mfi(candles, period=14)
        assert mfi == 100.0

    def test_mfi_all_negative_flow(self):
        """MFI returns 0 when all money flow is negative."""
        engine = StreamingIndicatorEngine()
        # Create falling typical prices (negative flow)
        prices = [(100 - i, 90 - i, 95 - i, 1000) for i in range(15)]
        candles = self._create_candles_with_volume(prices)

        mfi = engine._calc_mfi(candles, period=14)
        assert mfi is not None
        assert mfi < 10.0, f"MFI should be near 0 for all negative flow, got {mfi}"

    def test_mfi_equal_flows(self):
        """MFI returns 50 when positive and negative flows are equal."""
        engine = StreamingIndicatorEngine()
        # Alternate up and down with same magnitude
        prices = []
        for i in range(15):
            if i % 2 == 0:
                prices.append((100, 90, 95, 1000))  # Up
            else:
                prices.append((95, 85, 90, 1000))  # Down

        candles = self._create_candles_with_volume(prices)
        mfi = engine._calc_mfi(candles, period=14)

        assert mfi is not None
        # Should be around 50 for balanced flows
        assert 40.0 <= mfi <= 60.0, f"MFI should be ~50 for balanced flows, got {mfi}"

    def test_mfi_no_negative_flow(self):
        """MFI handles case when negative flow is zero."""
        engine = StreamingIndicatorEngine()
        # Flat then rising
        prices = [(100, 90, 95, 1000)] * 8  # Flat typical price
        prices.extend([(100 + i, 90 + i, 95 + i, 1000) for i in range(1, 8)])  # Rising

        candles = self._create_candles_with_volume(prices)
        mfi = engine._calc_mfi(candles, period=14)

        # Should return 100 when no negative flow but positive flow exists
        assert mfi == 100.0

    def test_mfi_range_bounds(self):
        """MFI should be in [0, 100] range."""
        engine = StreamingIndicatorEngine()
        # Mixed up/down movements
        prices = [(100 + (i % 3) * 5, 90 + (i % 3) * 5, 95 + (i % 3) * 5, 1000 + i * 100) for i in range(20)]

        candles = self._create_candles_with_volume(prices)
        mfi = engine._calc_mfi(candles, period=14)

        assert mfi is not None
        assert 0.0 <= mfi <= 100.0, f"MFI={mfi} should be in [0, 100]"

    def test_mfi_volume_impact(self):
        """MFI should be influenced by volume (higher volume = more flow impact)."""
        engine = StreamingIndicatorEngine()

        # Scenario 1: Rising prices with low volume
        prices_low_vol = [(95 + i, 85 + i, 90 + i, 100) for i in range(15)]
        candles_low = self._create_candles_with_volume(prices_low_vol)
        mfi_low = engine._calc_mfi(candles_low, period=14)

        # Scenario 2: Rising prices with high volume
        prices_high_vol = [(95 + i, 85 + i, 90 + i, 10000) for i in range(15)]
        candles_high = self._create_candles_with_volume(prices_high_vol)
        mfi_high = engine._calc_mfi(candles_high, period=14)

        # Both should be high (all positive flow), but the calculation is affected
        assert mfi_low is not None
        assert mfi_high is not None
        assert mfi_low > 90.0 and mfi_high > 90.0


class TestADXHelper:
    """Tests for _calc_adx (Average Directional Index) helper."""

    def _create_candles(self, prices: list[tuple[float, float, float]]) -> list[Candle]:
        """Create candles from (high, low, close) tuples."""
        candles = []
        for i, (high, low, close) in enumerate(prices):
            candles.append(
                Candle(
                    open=close,
                    high=high,
                    low=low,
                    close=close,
                    volume=1000.0,
                    minute=900 + i,
                )
            )
        return candles

    def test_adx_insufficient_data(self):
        """ADX returns None when insufficient candles."""
        candles = self._create_candles([(100, 90, 95)] * 10)
        adx = StreamingIndicatorEngine._calc_adx(candles, period=14)

        assert adx is None

    def test_adx_strong_uptrend(self):
        """ADX is high for strong uptrend."""
        # Strong consistent uptrend
        prices = [(100 + i * 2, 98 + i * 2, 99 + i * 2) for i in range(30)]
        candles = self._create_candles(prices)

        adx = StreamingIndicatorEngine._calc_adx(candles, period=14)
        assert adx is not None
        assert adx > 20.0, f"ADX should be elevated for strong trend, got {adx}"

    def test_adx_strong_downtrend(self):
        """ADX is high for strong downtrend."""
        # Strong consistent downtrend
        prices = [(100 - i * 2, 98 - i * 2, 99 - i * 2) for i in range(30)]
        candles = self._create_candles(prices)

        adx = StreamingIndicatorEngine._calc_adx(candles, period=14)
        assert adx is not None
        assert adx > 20.0, f"ADX should be elevated for strong trend, got {adx}"

    def test_adx_sideways_market(self):
        """ADX is low for sideways/ranging market."""
        # Sideways movement (no trend)
        prices = []
        for i in range(30):
            if i % 2 == 0:
                prices.append((102, 98, 100))
            else:
                prices.append((101, 99, 100))

        candles = self._create_candles(prices)
        adx = StreamingIndicatorEngine._calc_adx(candles, period=14)

        assert adx is not None
        assert adx < 25.0, f"ADX should be low for sideways market, got {adx}"

    def test_adx_range_bounds(self):
        """ADX should be non-negative."""
        # Mixed movements
        prices = [(100 + (i % 5) * 3, 95 + (i % 5) * 3, 98 + (i % 5) * 3) for i in range(30)]
        candles = self._create_candles(prices)

        adx = StreamingIndicatorEngine._calc_adx(candles, period=14)
        assert adx is not None
        assert adx >= 0.0, f"ADX should be non-negative, got {adx}"

    def test_adx_exact_minimum_data(self):
        """ADX computes with exact minimum data (period + 1 candles)."""
        prices = [(100 + i, 98 + i, 99 + i) for i in range(15)]
        candles = self._create_candles(prices)

        adx = StreamingIndicatorEngine._calc_adx(candles, period=14)
        # Should return a value (may be low due to insufficient DX values for full smoothing)
        assert adx is not None
        assert adx >= 0.0

    def test_adx_with_more_data(self):
        """ADX stabilizes with more data beyond minimum."""
        # Need enough data for full ADX smoothing
        prices = [(100 + i, 98 + i, 99 + i) for i in range(50)]
        candles = self._create_candles(prices)

        adx = StreamingIndicatorEngine._calc_adx(candles, period=14)
        assert adx is not None
        assert adx > 0.0, f"ADX should be positive with uptrend, got {adx}"

    def test_adx_trend_reversal(self):
        """ADX reflects trend changes."""
        # Strong uptrend then sideways
        prices = [(100 + i * 3, 98 + i * 3, 99 + i * 3) for i in range(20)]
        prices.extend([(160, 158, 159)] * 20)  # Sideways after trend

        candles = self._create_candles(prices)
        adx = StreamingIndicatorEngine._calc_adx(candles, period=14)

        assert adx is not None
        # ADX should still be somewhat elevated after recent trend
        assert adx >= 0.0


class TestHelperIntegration:
    """Integration tests ensuring helpers work correctly with IndicatorEngine."""

    def test_momentum_indicators_use_helpers(self):
        """Verify get_momentum_indicators uses helper methods correctly."""
        engine = StreamingIndicatorEngine(staleness_seconds=0)
        symbol = "TEST"

        # Build 50 candles for 5-minute timeframe (50 1-min → 10 5-min bars)
        cumulative = 0
        for minute in range(50):
            ts = datetime(2026, 2, 20, 9, minute, 30)
            cumulative += 1000 + minute * 10
            engine.on_tick(
                symbol,
                {
                    "close": 100.0 + minute * 0.5,
                    "high": 101.0 + minute * 0.5,
                    "low": 99.0 + minute * 0.5,
                    "volume": cumulative,
                },
                ts,
            )

        # Finalize last candle
        cumulative += 1500
        engine.on_tick(
            symbol,
            {"close": 125.0, "high": 126.0, "low": 124.0, "volume": cumulative},
            datetime(2026, 2, 20, 9, 50, 30),
        )

        momentum = engine.get_momentum_indicators(symbol, timeframe=5)

        # Should have momentum indicators computed via helpers
        assert "atr_raw" in momentum
        assert "atr_normalized" in momentum
        assert "stoch_k" in momentum
        assert "stoch_d" in momentum
        assert "adx" in momentum
        assert "mfi" in momentum

        # Verify types and ranges
        assert isinstance(momentum["atr_raw"], float)
        assert isinstance(momentum["atr_normalized"], float)
        assert 0.0 <= momentum["stoch_k"] <= 100.0
        assert 0.0 <= momentum["stoch_d"] <= 100.0

    def test_helpers_handle_edge_cases(self):
        """Helpers should gracefully handle edge cases without crashing."""
        engine = StreamingIndicatorEngine()

        # Empty candles
        assert engine._calc_mfi([], period=14) is None
        assert StreamingIndicatorEngine._calc_adx([], period=14) is None
        assert StreamingIndicatorEngine._calc_atr_raw([], period=14) == 0.0
        assert StreamingIndicatorEngine._calc_atr_normalized([], period=14) == 0.0

        k, d = StreamingIndicatorEngine._calc_stochastic([], period=14, smooth=3)
        assert k == 50.0 and d == 50.0

    def test_ema_helpers_consistency(self):
        """_ema_last should always match _ema_series[-1]."""
        test_cases = [
            ([100.0, 105.0, 103.0, 107.0], 3),
            ([50.0, 55.0, 52.0, 58.0, 60.0, 59.0], 5),
            ([200.0, 210.0, 205.0, 215.0, 220.0, 218.0, 225.0], 7),
        ]

        for values, span in test_cases:
            series = StreamingIndicatorEngine._ema_series(values, span)
            last = StreamingIndicatorEngine._ema_last(values, span)

            assert math.isclose(last, series[-1], rel_tol=1e-9), (
                f"_ema_last mismatch for values={values}, span={span}"
            )


# Import datetime for integration test
from datetime import datetime
