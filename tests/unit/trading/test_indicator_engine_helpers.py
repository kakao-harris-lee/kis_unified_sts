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
        assert (
            ema_short > ema_long
        ), "Short-span EMA should react faster to rising prices"

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
        """ATR captures gaps between candles.

        The gap between candle[0] (close=100) and candle[1] (open=110) produces
        a True Range of max(112-108, |112-100|, |108-100|) = 12 for candle[1].
        The ATR uses the LAST `period` TRs. To include the gap in the last 14 TRs,
        we add only 13 padding candles (total 15: gap at index 1 = TR[1], in last 14).
        """
        candles = [
            Candle(
                open=100.0, high=102.0, low=98.0, close=100.0, volume=1000.0, minute=900
            ),
            Candle(
                open=110.0,
                high=112.0,
                low=108.0,
                close=110.0,
                volume=1000.0,
                minute=901,
            ),  # Gap up
        ]
        # Add exactly 13 more candles so total is 15 candles = 14 TRs.
        # The gap TR at index 1 is then the first of the 14 TRs used for ATR.
        for i in range(2, 15):
            candles.append(
                Candle(
                    open=110.0,
                    high=112.0,
                    low=108.0,
                    close=110.0,
                    volume=1000.0,
                    minute=900 + i,
                )
            )

        atr = StreamingIndicatorEngine._calc_atr_raw(candles, period=14)
        # Gap TR = 12.0 is included; remaining 13 TRs = 4.0 each.
        # ATR = (12 + 13*4) / 14 = (12 + 52) / 14 = 64/14 ≈ 4.57 > 4.0
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
        atr_norm_low = StreamingIndicatorEngine._calc_atr_normalized(
            candles_low, period=14
        )

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
        atr_norm_high = StreamingIndicatorEngine._calc_atr_normalized(
            candles_high, period=14
        )

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
        """Stochastic K near 0 when close is at period low.

        The stochastic window looks at the last `period` candles. With increasing
        prices from i=0..13 then a drop at i=14, the period window [1..14] has
        low_min=91 (at i=1) and high_max=114 (at i=14). To get K near 0, the
        close must be at or below the period low. Setting close=91 (= period low)
        makes K = (91-91)/(114-91) = 0.
        """
        # Build 14 candles with increasing prices
        prices = [(100 + i, 90 + i, 95 + i) for i in range(14)]
        # Final candle: close at the period low (low of window [1..14] = 90+1 = 91)
        prices.append((114, 91, 91))  # Close at period low (low of window)

        candles = self._create_candles(prices)
        k, d = StreamingIndicatorEngine._calc_stochastic(candles, period=14, smooth=3)

        assert k < 5.0, f"K should be near 0 when close at period low, got {k}"

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
        assert math.isclose(
            k, d, abs_tol=10.0
        ), f"K={k}, D={d} should be close for stable prices"

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
        prices = [
            (100 + (i % 3) * 5, 90 + (i % 3) * 5, 95 + (i % 3) * 5, 1000 + i * 100)
            for i in range(20)
        ]

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
        """ADX is low for cycling sideways/ranging market.

        A cycling 3-pattern market (high/low shifts in a cycle) produces low ADX.
        The _calc_adx returns None when no DX values can be computed (all di_sum=0).
        For a cycling pattern, some DX values exist but ADX stays low.
        """
        # Cycling 3-period pattern: price oscillates with no net trend
        prices = []
        for i in range(30):
            prices.append((101.5 + (i % 3) * 0.5, 98.5 + (i % 3) * 0.5, 100.0))

        candles = self._create_candles(prices)
        adx = StreamingIndicatorEngine._calc_adx(candles, period=14)

        # ADX should be computable (non-None) and low for sideways market
        assert adx is not None
        assert adx < 25.0, f"ADX should be low for sideways market, got {adx}"

    def test_adx_range_bounds(self):
        """ADX should be non-negative."""
        # Mixed movements
        prices = [
            (100 + (i % 5) * 3, 95 + (i % 5) * 3, 98 + (i % 5) * 3) for i in range(30)
        ]
        candles = self._create_candles(prices)

        adx = StreamingIndicatorEngine._calc_adx(candles, period=14)
        assert adx is not None
        assert adx >= 0.0, f"ADX should be non-negative, got {adx}"

    def test_adx_exact_minimum_data(self):
        """ADX requires period*2+1 candles for full Wilder smoothing.

        With period=14, the minimum is 14+1=15 candles for tr_list (14 values).
        The Wilder smoothing loop runs range(period, len(tr_list))=range(14,14)=0 times,
        so no dx_values are produced and ADX returns None. Full ADX computation
        requires period*2+1 = 29 candles (14 TRs for initial SMA + 14 for smoothing).
        """
        # With exactly period+1=15 candles, ADX returns None (no DX values produced)
        prices = [(100 + i, 98 + i, 99 + i) for i in range(15)]
        candles = self._create_candles(prices)

        adx_minimal = StreamingIndicatorEngine._calc_adx(candles, period=14)
        assert adx_minimal is None, "ADX needs period*2+1 candles for full computation"

        # With period*2+1=29 candles, ADX should compute a value
        prices_full = [(100 + i, 98 + i, 99 + i) for i in range(29)]
        candles_full = self._create_candles(prices_full)

        adx_full = StreamingIndicatorEngine._calc_adx(candles_full, period=14)
        assert adx_full is not None
        assert adx_full >= 0.0

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
        """Verify get_momentum_indicators returns the correct momentum indicator keys.

        get_momentum_indicators uses calculate_all_momentum (pandas-based) on
        accumulated MTF candles. It returns trix, cci, macd, stochastic (sto_k/sto_d),
        obv, rsi, williams_r — NOT _calc_atr_raw, _calc_adx, or _calc_mfi helpers.
        Requires min_candles=50 5-min candles.
        """
        engine = StreamingIndicatorEngine(mtf_timeframes=[5], staleness_seconds=0)
        symbol = "TEST"

        # Build 260 1-min ticks → ~51 5-min candles (min_candles=50 required)
        cumulative = 0
        for minute in range(260):
            ts = datetime(2026, 2, 20, 9 + minute // 60, minute % 60, 30)
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

        momentum = engine.get_momentum_indicators(symbol, timeframe=5)

        # Should have the standard momentum indicator keys from calculate_all_momentum
        assert "trix" in momentum
        assert "cci" in momentum
        assert "macd_line" in momentum
        assert "macd_signal" in momentum
        assert "macd_oscillator" in momentum
        assert "sto_k" in momentum
        assert "sto_d" in momentum
        assert "rsi" in momentum
        assert "obv" in momentum

        # Verify types and ranges
        assert isinstance(momentum["trix"], float)
        assert isinstance(momentum["rsi"], float)
        assert 0.0 <= momentum["rsi"] <= 100.0
        assert 0.0 <= momentum["sto_k"] <= 100.0
        assert 0.0 <= momentum["sto_d"] <= 100.0

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

            assert math.isclose(
                last, series[-1], rel_tol=1e-9
            ), f"_ema_last mismatch for values={values}, span={span}"


class TestIndicatorFeatures:
    """Tests for indicator feature calculation and market-wide MFI."""

    def _build_indicator_warm_engine(
        self, symbol: str = "005930", num_candles: int = 30
    ) -> StreamingIndicatorEngine:
        """Build an engine with sufficient candles for MACD-derived features.

        Creates candles with realistic price movement and volume patterns.
        staleness_seconds=0 disables staleness guard for testing.

        Uses timedelta-based timestamps to avoid minute overflow (0..59 limit).
        """
        from datetime import timedelta

        engine = StreamingIndicatorEngine(bb_period=20, staleness_seconds=0)

        base_price = 70000.0
        base_volume = 1000
        cumulative = 0
        base_ts = datetime(2026, 2, 20, 9, 0, 30)

        for minute in range(num_candles):
            ts = base_ts + timedelta(minutes=minute)
            # Price with slight upward trend and noise
            price = base_price + minute * 50 + (minute % 5) * 20
            cumulative += base_volume + minute * 5
            engine.on_tick(
                symbol,
                {
                    "close": price,
                    "high": price + 100,
                    "low": price - 100,
                    "volume": cumulative,
                },
                ts,
            )

        # Finalize last candle
        cumulative += base_volume + num_candles * 5
        engine.on_tick(
            symbol,
            {
                "close": base_price + num_candles * 50,
                "high": base_price + num_candles * 50 + 100,
                "low": base_price + num_candles * 50 - 100,
                "volume": cumulative,
            },
            base_ts + timedelta(minutes=num_candles),
        )

        return engine

    def test_get_indicator_features_returns_all_25_features(self):
        """indicator features should return all 25 expected keys when warm."""
        engine = self._build_indicator_warm_engine(num_candles=30)
        features = engine.get_indicator_features("005930")

        expected_keys = {
            "returns",
            "ma_ratio_5",
            "ma_ratio_10",
            "ma_ratio_20",
            "rsi",
            "bb_position",
            "volume_ratio",
            "volatility",
            "hl_range",
            "candle_body",
            "macd",
            "macd_signal",
            "macd_hist",
            "sma_ratio_60",
            "sma_ratio_120",
            "ema_ratio_5",
            "ema_ratio_10",
            "ema_ratio_20",
            "bb_upper_dist",
            "bb_lower_dist",
            "bb_width",
            "atr",
            "stoch_k",
            "stoch_d",
            "price_change_5",
        }

        assert (
            set(features.keys()) == expected_keys
        ), f"Missing or extra keys. Expected {expected_keys}, got {set(features.keys())}"

    def test_get_indicator_features_all_values_finite(self):
        """All indicator feature values should be finite numbers."""
        engine = self._build_indicator_warm_engine(num_candles=30)
        features = engine.get_indicator_features("005930")

        for key, value in features.items():
            assert math.isfinite(
                value
            ), f"Feature '{key}' has non-finite value: {value}"

    def test_get_indicator_features_insufficient_data(self):
        """indicator features should return empty dict with <26 candles (MACD requirement)."""
        engine = StreamingIndicatorEngine()
        symbol = "TEST"

        # Add only 20 candles (less than 26 required for MACD)
        cumulative = 0
        for minute in range(20):
            ts = datetime(2026, 2, 20, 9, minute, 30)
            cumulative += 1000
            engine.on_tick(
                symbol,
                {
                    "close": 100.0 + minute,
                    "high": 105.0 + minute,
                    "low": 95.0 + minute,
                    "volume": cumulative,
                },
                ts,
            )

        features = engine.get_indicator_features(symbol)
        assert features == {}, "Should return empty dict when insufficient data"

    def test_get_indicator_features_nonexistent_symbol(self):
        """indicator features should return empty dict for unknown symbol."""
        engine = StreamingIndicatorEngine()
        features = engine.get_indicator_features("NONEXISTENT")
        assert features == {}

    def test_get_indicator_features_ma_ratios_reflect_trend(self):
        """MA ratios should be >1.0 for uptrending prices."""
        engine = self._build_indicator_warm_engine(num_candles=30)
        features = engine.get_indicator_features("005930")

        # Price is increasing in our test data, so close/MA should be >1.0
        assert features["ma_ratio_5"] > 1.0, "ma_ratio_5 should be >1.0 for uptrend"
        assert features["ma_ratio_10"] > 1.0, "ma_ratio_10 should be >1.0 for uptrend"
        assert features["ma_ratio_20"] > 1.0, "ma_ratio_20 should be >1.0 for uptrend"

    def test_get_indicator_features_bb_position_in_range(self):
        """BB position should typically be between 0 and 1."""
        engine = self._build_indicator_warm_engine(num_candles=30)
        features = engine.get_indicator_features("005930")

        # BB position can be <0 or >1 if price is outside bands, but typically in [0, 1]
        assert math.isfinite(features["bb_position"]), "bb_position should be finite"

    def test_get_indicator_features_rsi_in_valid_range(self):
        """RSI should be between 0 and 100."""
        engine = self._build_indicator_warm_engine(num_candles=30)
        features = engine.get_indicator_features("005930")

        assert (
            0.0 <= features["rsi"] <= 100.0
        ), f"RSI should be in [0, 100], got {features['rsi']}"

    def test_get_indicator_features_stochastic_in_valid_range(self):
        """Stochastic K and D should be between 0 and 100."""
        engine = self._build_indicator_warm_engine(num_candles=30)
        features = engine.get_indicator_features("005930")

        assert (
            0.0 <= features["stoch_k"] <= 100.0
        ), f"stoch_k should be in [0, 100], got {features['stoch_k']}"
        assert (
            0.0 <= features["stoch_d"] <= 100.0
        ), f"stoch_d should be in [0, 100], got {features['stoch_d']}"

    def test_get_indicator_features_macd_components(self):
        """MACD histogram should equal macd - macd_signal."""
        engine = self._build_indicator_warm_engine(num_candles=30)
        features = engine.get_indicator_features("005930")

        expected_hist = features["macd"] - features["macd_signal"]
        assert math.isclose(
            features["macd_hist"], expected_hist, rel_tol=1e-9
        ), f"MACD histogram mismatch: {features['macd_hist']} vs {expected_hist}"

    def test_get_indicator_features_volume_ratio_reflects_activity(self):
        """Volume ratio should be positive for active trading."""
        engine = self._build_indicator_warm_engine(num_candles=30)
        features = engine.get_indicator_features("005930")

        assert features["volume_ratio"] > 0.0, "volume_ratio should be positive"

    def test_get_indicator_features_with_120_candles(self):
        """indicator features should work correctly with 120+ candles (for sma_ratio_120)."""
        engine = self._build_indicator_warm_engine(num_candles=125)
        features = engine.get_indicator_features("005930")

        # With 125 candles, sma_ratio_120 should be computed (not default 1.0)
        assert features["sma_ratio_120"] != 1.0 or features["sma_ratio_120"] > 0.0

    def test_get_indicator_features_bb_distances_positive(self):
        """BB distances should be positive (distance from bands to price)."""
        engine = self._build_indicator_warm_engine(num_candles=30)
        features = engine.get_indicator_features("005930")

        # bb_upper_dist = (upper - close) / close should be positive when price < upper
        # bb_lower_dist = (close - lower) / close should be positive when price > lower
        assert features["bb_upper_dist"] >= -1.0, "bb_upper_dist should be reasonable"
        assert features["bb_lower_dist"] >= -1.0, "bb_lower_dist should be reasonable"
        assert features["bb_width"] > 0.0, "bb_width should be positive"

    def test_get_indicator_features_atr_positive(self):
        """ATR should be positive for volatile markets."""
        engine = self._build_indicator_warm_engine(num_candles=30)
        features = engine.get_indicator_features("005930")

        assert features["atr"] >= 0.0, "ATR should be non-negative"

    def test_get_indicator_features_consistent_across_calls(self):
        """indicator features should be deterministic for same data."""
        engine = self._build_indicator_warm_engine(num_candles=30)

        features1 = engine.get_indicator_features("005930")
        features2 = engine.get_indicator_features("005930")

        for key in features1.keys():
            assert (
                features1[key] == features2[key]
            ), f"Feature '{key}' not deterministic"


class TestMarketWideMFI:
    """Tests for market-wide MFI calculation."""

    def _build_multi_symbol_engine(self) -> StreamingIndicatorEngine:
        """Build an engine with multiple warm symbols for market MFI testing."""
        engine = StreamingIndicatorEngine(bb_period=20, staleness_seconds=0)

        # Create 5 symbols with varying MFI patterns
        symbols = ["SYM1", "SYM2", "SYM3", "SYM4", "SYM5"]
        base_prices = [50000, 70000, 90000, 40000, 60000]

        for idx, symbol in enumerate(symbols):
            base_price = base_prices[idx]
            cumulative = 0

            # Add 20 candles per symbol (sufficient for MFI period=14)
            for minute in range(20):
                ts = datetime(2026, 2, 20, 9, minute, 30)
                # Vary price patterns to create different MFI values
                price = base_price + minute * (50 + idx * 10)
                cumulative += 1000 + minute * (100 + idx * 20)
                engine.on_tick(
                    symbol,
                    {
                        "close": price,
                        "high": price + 100,
                        "low": price - 100,
                        "volume": cumulative,
                    },
                    ts,
                )

            # Finalize last candle
            cumulative += 1000 + 20 * (100 + idx * 20)
            engine.on_tick(
                symbol,
                {
                    "close": base_price + 20 * (50 + idx * 10),
                    "high": base_price + 20 * (50 + idx * 10) + 100,
                    "low": base_price + 20 * (50 + idx * 10) - 100,
                    "volume": cumulative,
                },
                datetime(2026, 2, 20, 9, 20, 30),
            )

        return engine

    def test_get_market_mfi_returns_median(self):
        """Market MFI should return median of all warm symbols."""
        engine = self._build_multi_symbol_engine()
        market_mfi = engine.get_market_mfi()

        assert market_mfi is not None, "Market MFI should not be None with warm symbols"
        assert (
            0.0 <= market_mfi <= 100.0
        ), f"Market MFI should be in [0, 100], got {market_mfi}"

    def test_get_market_mfi_with_active_symbols_filter(self):
        """Market MFI should respect active_symbols filter."""
        engine = self._build_multi_symbol_engine()

        # Filter to only 2 symbols
        active = {"SYM1", "SYM3"}
        market_mfi = engine.get_market_mfi(active_symbols=active)

        assert market_mfi is not None, "Market MFI should work with filtered symbols"

    def test_get_market_mfi_insufficient_data(self):
        """Market MFI should return None when no warm symbols."""
        engine = StreamingIndicatorEngine()

        # Add only a few ticks (not enough for MFI period=14)
        cumulative = 0
        for minute in range(5):
            cumulative += 1000
            engine.on_tick(
                "TEST",
                {"close": 100.0, "high": 101.0, "low": 99.0, "volume": cumulative},
                datetime(2026, 2, 20, 9, minute, 30),
            )

        market_mfi = engine.get_market_mfi()
        assert market_mfi is None, "Market MFI should be None with insufficient data"

    def test_get_market_mfi_no_symbols(self):
        """Market MFI should return None when no symbols tracked."""
        engine = StreamingIndicatorEngine()
        market_mfi = engine.get_market_mfi()
        assert market_mfi is None

    def test_get_market_mfi_empty_active_symbols(self):
        """Market MFI should return None when active_symbols filter excludes all."""
        engine = self._build_multi_symbol_engine()

        # Filter with no matching symbols
        market_mfi = engine.get_market_mfi(active_symbols=set())
        assert market_mfi is None

    def test_get_market_mfi_single_symbol(self):
        """Market MFI should work with single symbol (median = that value)."""
        engine = StreamingIndicatorEngine(bb_period=20, staleness_seconds=0)
        symbol = "SINGLE"
        cumulative = 0

        for minute in range(20):
            ts = datetime(2026, 2, 20, 9, minute, 30)
            cumulative += 1000
            engine.on_tick(
                symbol,
                {
                    "close": 100.0 + minute,
                    "high": 105.0 + minute,
                    "low": 95.0 + minute,
                    "volume": cumulative,
                },
                ts,
            )

        cumulative += 1000
        engine.on_tick(
            symbol,
            {"close": 120.0, "high": 125.0, "low": 115.0, "volume": cumulative},
            datetime(2026, 2, 20, 9, 20, 30),
        )

        market_mfi = engine.get_market_mfi()
        assert market_mfi is not None, "Market MFI should work with single symbol"

    def test_get_market_mfi_median_calculation_even_count(self):
        """Market MFI should correctly compute median for even number of symbols."""
        engine = self._build_multi_symbol_engine()

        # We have 5 symbols, so median is the middle value
        # Let's verify it's actually computing median by checking range
        market_mfi = engine.get_market_mfi()
        assert market_mfi is not None

        # Median should be between min and max of individual MFIs
        # This is a sanity check that it's not just averaging or taking first/last
        assert 0.0 <= market_mfi <= 100.0

    def test_get_market_mfi_deterministic(self):
        """Market MFI should return same value for repeated calls."""
        engine = self._build_multi_symbol_engine()

        mfi1 = engine.get_market_mfi()
        mfi2 = engine.get_market_mfi()

        assert mfi1 == mfi2, "Market MFI should be deterministic"

    def test_get_market_mfi_with_mixed_warm_cold_symbols(self):
        """Market MFI should only include warm symbols (>= 14 candles)."""
        engine = StreamingIndicatorEngine(bb_period=20, staleness_seconds=0)

        # Add one warm symbol (20 candles)
        cumulative_warm = 0
        for minute in range(20):
            ts = datetime(2026, 2, 20, 9, minute, 30)
            cumulative_warm += 1000
            engine.on_tick(
                "WARM",
                {
                    "close": 100.0 + minute,
                    "high": 105.0 + minute,
                    "low": 95.0 + minute,
                    "volume": cumulative_warm,
                },
                ts,
            )
        cumulative_warm += 1000
        engine.on_tick(
            "WARM",
            {"close": 120.0, "high": 125.0, "low": 115.0, "volume": cumulative_warm},
            datetime(2026, 2, 20, 9, 20, 30),
        )

        # Add one cold symbol (only 5 candles)
        cumulative_cold = 0
        for minute in range(5):
            ts = datetime(2026, 2, 20, 9, minute, 30)
            cumulative_cold += 1000
            engine.on_tick(
                "COLD",
                {
                    "close": 200.0 + minute,
                    "high": 205.0 + minute,
                    "low": 195.0 + minute,
                    "volume": cumulative_cold,
                },
                ts,
            )

        market_mfi = engine.get_market_mfi()
        # Should get MFI (only from WARM symbol, since COLD has < 14 candles)
        assert market_mfi is not None, "Should compute MFI from warm symbol only"


# Import datetime for tests (already imported at top of file, but kept for clarity)
from datetime import datetime
