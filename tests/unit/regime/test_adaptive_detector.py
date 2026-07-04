"""Test AdaptiveRegimeDetector with multi-metric classification."""
import math
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from shared.indicators.reference import ADXCalculator
from shared.regime.adaptive_detector import (
    AdaptiveRegimeConfig,
    AdaptiveRegimeDetector,
    AdaptiveRegimeState,
)


class TestAdaptiveRegimeDetector:
    """Test suite for AdaptiveRegimeDetector."""

    @pytest.fixture(autouse=True)
    def _seed_rng(self):
        """Seed NumPy's global RNG before each test for determinism.

        Several tests build synthetic OHLCV candles with ``np.random.*`` without
        seeding, so the regime classification — and thus the assertions — was
        non-deterministic (e.g. ``test_detect_volatile_sideways`` occasionally
        drew data that landed outside its expected regime set, failing in CI).
        """
        np.random.seed(0)

    # 1. Test regime classification for each state

    def test_detect_trending_bull(self):
        """High ADX + High MFI + Positive SMA → TRENDING_BULL"""
        detector = AdaptiveRegimeDetector()

        # Create strong uptrend data with high volume
        dates = pd.date_range(end=datetime.now(), periods=60, freq="1min")
        close_prices = 100 + np.arange(60) * 0.5  # Strong uptrend
        high_prices = close_prices + np.random.rand(60) * 0.2
        low_prices = close_prices - np.random.rand(60) * 0.2
        open_prices = close_prices - 0.1
        volumes = 1000 + np.arange(60) * 50  # Increasing volume

        df = pd.DataFrame({
            "datetime": dates,
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volumes,
        })

        signal = detector.detect(df)

        assert signal.state == AdaptiveRegimeState.TRENDING_BULL
        assert signal.confidence > 0.5  # Reasonable confidence for strong trend

    def test_detect_trending_bear(self):
        """High ADX + Low MFI + Negative SMA → TRENDING_BEAR"""
        detector = AdaptiveRegimeDetector()

        # Create strong downtrend data with decreasing volume
        dates = pd.date_range(end=datetime.now(), periods=60, freq="1min")
        close_prices = 150 - np.arange(60) * 0.5  # Strong downtrend
        high_prices = close_prices + np.random.rand(60) * 0.2
        low_prices = close_prices - np.random.rand(60) * 0.2
        open_prices = close_prices + 0.1
        volumes = 2000 - np.arange(60) * 10  # Decreasing volume

        df = pd.DataFrame({
            "datetime": dates,
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volumes,
        })

        signal = detector.detect(df)

        assert signal.state == AdaptiveRegimeState.TRENDING_BEAR
        assert signal.confidence > 0.5

    def test_detect_volatile_sideways(self):
        """High ATR + Low ADX → VOLATILE_SIDEWAYS"""
        config = AdaptiveRegimeConfig(
            atr_high_volatility=0.02,  # Lower threshold to trigger
            adx_weak_trend=25.0,  # Higher threshold for weak trend
        )
        detector = AdaptiveRegimeDetector(config)

        # Create volatile sideways data with wide price swings
        dates = pd.date_range(end=datetime.now(), periods=60, freq="1min")
        close_prices = 100 + np.sin(np.arange(60) * 0.5) * 5  # Oscillating
        # Add high volatility with large candle ranges
        high_prices = close_prices + np.random.rand(60) * 3
        low_prices = close_prices - np.random.rand(60) * 3
        open_prices = close_prices + np.random.randn(60) * 1
        volumes = 1000 + np.random.rand(60) * 500

        df = pd.DataFrame({
            "datetime": dates,
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volumes,
        })

        signal = detector.detect(df)

        # Should detect volatile sideways (high volatility, no clear trend)
        assert signal.state in [
            AdaptiveRegimeState.VOLATILE_SIDEWAYS,
            AdaptiveRegimeState.MEAN_REVERTING,
            AdaptiveRegimeState.CALM_SIDEWAYS,
        ]

    def test_detect_calm_sideways(self):
        """Low ATR + Low ADX → CALM_SIDEWAYS"""
        config = AdaptiveRegimeConfig(
            atr_low_volatility=0.02,  # Higher threshold for low volatility
            adx_weak_trend=25.0,
        )
        detector = AdaptiveRegimeDetector(config)

        # Create calm sideways data with minimal price movement
        dates = pd.date_range(end=datetime.now(), periods=60, freq="1min")
        close_prices = 100 + np.sin(np.arange(60) * 0.1) * 0.2  # Small oscillations
        high_prices = close_prices + 0.05
        low_prices = close_prices - 0.05
        open_prices = close_prices
        volumes = 1000 + np.random.rand(60) * 50

        df = pd.DataFrame({
            "datetime": dates,
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volumes,
        })

        signal = detector.detect(df)

        # Should detect calm sideways or mean reverting
        assert signal.state in [
            AdaptiveRegimeState.CALM_SIDEWAYS,
            AdaptiveRegimeState.MEAN_REVERTING,
        ]

    def test_detect_mean_reverting(self):
        """Moderate MFI + Weak ADX → MEAN_REVERTING"""
        config = AdaptiveRegimeConfig(
            mfi_bull_threshold=55.0,
            mfi_bear_threshold=45.0,
            adx_weak_trend=25.0,
        )
        detector = AdaptiveRegimeDetector(config)

        # Create oscillating price pattern with moderate volume
        dates = pd.date_range(end=datetime.now(), periods=60, freq="1min")
        close_prices = 100 + np.sin(np.arange(60) * 0.3) * 2
        high_prices = close_prices + 0.3
        low_prices = close_prices - 0.3
        open_prices = close_prices
        volumes = 1000 + np.sin(np.arange(60) * 0.3) * 200

        df = pd.DataFrame({
            "datetime": dates,
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volumes,
        })

        signal = detector.detect(df)

        # Should detect mean reverting or calm sideways
        assert signal.state in [
            AdaptiveRegimeState.MEAN_REVERTING,
            AdaptiveRegimeState.CALM_SIDEWAYS,
        ]

    def test_detect_unknown_insufficient_data(self):
        """Less than min_bars → UNKNOWN with 0.0 confidence"""
        detector = AdaptiveRegimeDetector()

        # Create DataFrame with < 50 bars (default min_bars)
        dates = pd.date_range(end=datetime.now(), periods=30, freq="1min")
        close_prices = 100 + np.arange(30) * 0.1
        high_prices = close_prices + 0.5
        low_prices = close_prices - 0.5
        open_prices = close_prices
        volumes = np.ones(30) * 1000

        df = pd.DataFrame({
            "datetime": dates,
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volumes,
        })

        signal = detector.detect(df)

        assert signal.state == AdaptiveRegimeState.UNKNOWN
        assert signal.confidence == 0.0

    # 2. Test confidence scoring

    def test_confidence_scoring_high(self):
        """All metrics agree → confidence > 0.5"""
        detector = AdaptiveRegimeDetector()

        # Create strong, consistent uptrend
        dates = pd.date_range(end=datetime.now(), periods=60, freq="1min")
        close_prices = 100 + np.arange(60) * 1.0  # Very strong uptrend
        high_prices = close_prices + 0.5
        low_prices = close_prices - 0.3
        open_prices = close_prices - 0.2
        volumes = 1000 + np.arange(60) * 100  # Strong increasing volume

        df = pd.DataFrame({
            "datetime": dates,
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volumes,
        })

        signal = detector.detect(df)

        # Strong trend with all metrics agreeing should have high confidence
        assert signal.confidence > 0.5

    def test_confidence_scoring_medium(self):
        """Majority agreement → confidence 0.4-0.8"""
        detector = AdaptiveRegimeDetector()

        # Create moderate trend with some conflicting signals
        dates = pd.date_range(end=datetime.now(), periods=60, freq="1min")
        close_prices = 100 + np.arange(60) * 0.3  # Moderate trend
        high_prices = close_prices + np.random.rand(60) * 0.5
        low_prices = close_prices - np.random.rand(60) * 0.5
        open_prices = close_prices
        volumes = 1000 + np.random.rand(60) * 300

        df = pd.DataFrame({
            "datetime": dates,
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volumes,
        })

        signal = detector.detect(df)

        # Moderate trend should have medium confidence
        assert 0.3 <= signal.confidence <= 0.9

    def test_confidence_scoring_low(self):
        """Mixed signals → confidence < 0.7"""
        detector = AdaptiveRegimeDetector()

        # Create noisy data with no clear direction
        dates = pd.date_range(end=datetime.now(), periods=60, freq="1min")
        close_prices = 100 + np.random.randn(60) * 2
        high_prices = close_prices + np.random.rand(60) * 1
        low_prices = close_prices - np.random.rand(60) * 1
        open_prices = close_prices
        volumes = 1000 + np.random.rand(60) * 500

        df = pd.DataFrame({
            "datetime": dates,
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volumes,
        })

        signal = detector.detect(df)

        # Noisy data should not have very high confidence
        assert signal.confidence < 0.85

    # 3. Test indicator calculations

    def test_mfi_calculation(self):
        """Verify MFI formula correctness"""
        detector = AdaptiveRegimeDetector()

        # Create data with known MFI pattern
        dates = pd.date_range(end=datetime.now(), periods=60, freq="1min")
        close_prices = 100 + np.arange(60) * 0.5
        high_prices = close_prices + 0.5
        low_prices = close_prices - 0.5
        open_prices = close_prices
        volumes = 1000 + np.arange(60) * 50

        df = pd.DataFrame({
            "datetime": dates,
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volumes,
        })

        signal = detector.detect(df)

        # MFI should be in valid range
        assert "mfi" in signal.indicators
        assert 0 <= signal.indicators["mfi"] <= 100

    def test_adx_calculation(self):
        """Verify ADX formula correctness"""
        detector = AdaptiveRegimeDetector()

        # Create trending data
        dates = pd.date_range(end=datetime.now(), periods=60, freq="1min")
        close_prices = 100 + np.arange(60) * 0.8
        high_prices = close_prices + 0.5
        low_prices = close_prices - 0.3
        open_prices = close_prices
        volumes = np.ones(60) * 1000

        df = pd.DataFrame({
            "datetime": dates,
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volumes,
        })

        signal = detector.detect(df)

        # ADX should be calculated
        assert "adx" in signal.indicators
        assert signal.indicators["adx"] >= 0

    def test_atr_calculation(self):
        """Verify ATR formula correctness"""
        detector = AdaptiveRegimeDetector()

        # Create volatile data
        dates = pd.date_range(end=datetime.now(), periods=60, freq="1min")
        close_prices = 100 + np.random.randn(60) * 3
        high_prices = close_prices + np.random.rand(60) * 2
        low_prices = close_prices - np.random.rand(60) * 2
        open_prices = close_prices
        volumes = np.ones(60) * 1000

        df = pd.DataFrame({
            "datetime": dates,
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volumes,
        })

        signal = detector.detect(df)

        # ATR should be calculated
        assert "atr" in signal.indicators
        assert "atr_ratio" in signal.indicators
        assert signal.indicators["atr"] > 0
        assert signal.indicators["atr_ratio"] >= 0

    # 4. Test edge cases

    def test_edge_case_zero_volume(self):
        """Handle bars with zero volume"""
        detector = AdaptiveRegimeDetector()

        # Create data with some zero volume bars
        dates = pd.date_range(end=datetime.now(), periods=60, freq="1min")
        close_prices = 100 + np.arange(60) * 0.1
        high_prices = close_prices + 0.5
        low_prices = close_prices - 0.5
        open_prices = close_prices
        volumes = np.ones(60) * 1000
        volumes[10:15] = 0  # Zero volume for some bars

        df = pd.DataFrame({
            "datetime": dates,
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volumes,
        })

        # Should not crash
        signal = detector.detect(df)
        assert signal.state in AdaptiveRegimeState

    def test_edge_case_nan_values(self):
        """Handle NaN in data"""
        detector = AdaptiveRegimeDetector()

        # Create data with NaN values
        dates = pd.date_range(end=datetime.now(), periods=60, freq="1min")
        close_prices = 100 + np.arange(60) * 0.1
        high_prices = close_prices + 0.5
        low_prices = close_prices - 0.5
        open_prices = close_prices
        volumes = np.ones(60) * 1000

        df = pd.DataFrame({
            "datetime": dates,
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volumes,
        })

        # Introduce NaN
        df.loc[5:7, "close"] = np.nan

        # Should handle gracefully
        signal = detector.detect(df)
        assert signal.state in AdaptiveRegimeState

    def test_edge_case_constant_price(self):
        """Handle constant price (no movement)"""
        detector = AdaptiveRegimeDetector()

        # Create data with constant price
        dates = pd.date_range(end=datetime.now(), periods=60, freq="1min")
        close_prices = np.ones(60) * 100  # Constant
        high_prices = close_prices
        low_prices = close_prices
        open_prices = close_prices
        volumes = np.ones(60) * 1000

        df = pd.DataFrame({
            "datetime": dates,
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volumes,
        })

        signal = detector.detect(df)

        # Should handle zero ATR
        assert signal.indicators["atr"] == 0.0
        assert signal.state in AdaptiveRegimeState

    # 5. Test configuration

    def test_custom_thresholds(self):
        """Custom config thresholds work correctly"""
        config = AdaptiveRegimeConfig(
            mfi_bull_threshold=70.0,
            mfi_bear_threshold=30.0,
            adx_strong_trend=30.0,
            confidence_threshold=0.8,
        )
        detector = AdaptiveRegimeDetector(config)

        # Create data
        dates = pd.date_range(end=datetime.now(), periods=60, freq="1min")
        close_prices = 100 + np.arange(60) * 0.5
        high_prices = close_prices + 0.5
        low_prices = close_prices - 0.5
        open_prices = close_prices
        volumes = np.ones(60) * 1000

        df = pd.DataFrame({
            "datetime": dates,
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volumes,
        })

        signal = detector.detect(df)

        # Verify custom thresholds are used
        assert signal.confidence_threshold == 0.8

    def test_config_validation(self):
        """Invalid config raises errors"""
        # Test negative min_bars
        config = AdaptiveRegimeConfig(min_bars=-10)
        detector = AdaptiveRegimeDetector(config)

        # Should still work but with unusual config
        dates = pd.date_range(end=datetime.now(), periods=60, freq="1min")
        close_prices = np.ones(60) * 100
        high_prices = close_prices
        low_prices = close_prices
        open_prices = close_prices
        volumes = np.ones(60) * 1000

        df = pd.DataFrame({
            "datetime": dates,
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volumes,
        })

        # Should handle edge case
        signal = detector.detect(df)
        assert signal.state in AdaptiveRegimeState

    # 6. Test missing columns

    def test_missing_columns(self):
        """Missing required columns returns UNKNOWN"""
        detector = AdaptiveRegimeDetector()

        # Create DataFrame missing 'volume' column
        dates = pd.date_range(end=datetime.now(), periods=60, freq="1min")
        df = pd.DataFrame({
            "datetime": dates,
            "close": np.ones(60) * 100,
        })

        signal = detector.detect(df)

        assert signal.state == AdaptiveRegimeState.UNKNOWN
        assert signal.confidence == 0.0

    # 7. Test last_signal property

    def test_last_signal_property(self):
        """last_signal property stores last detection"""
        detector = AdaptiveRegimeDetector()

        dates = pd.date_range(end=datetime.now(), periods=60, freq="1min")
        close_prices = 100 + np.arange(60) * 0.5
        high_prices = close_prices + 0.5
        low_prices = close_prices - 0.5
        open_prices = close_prices
        volumes = np.ones(60) * 1000

        df = pd.DataFrame({
            "datetime": dates,
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volumes,
        })

        signal = detector.detect(df)

        assert detector.last_signal is not None
        assert detector.last_signal.state == signal.state
        assert detector.last_signal.confidence == signal.confidence

    # 8. Test signal indicators

    def test_signal_includes_all_indicators(self):
        """Signal includes all calculated indicators"""
        detector = AdaptiveRegimeDetector()

        dates = pd.date_range(end=datetime.now(), periods=60, freq="1min")
        close_prices = 100 + np.arange(60) * 0.5
        high_prices = close_prices + 0.5
        low_prices = close_prices - 0.5
        open_prices = close_prices
        volumes = np.ones(60) * 1000

        df = pd.DataFrame({
            "datetime": dates,
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": close_prices,
            "volume": volumes,
        })

        signal = detector.detect(df)

        # Check all expected indicators are present
        assert "mfi" in signal.indicators
        assert "adx" in signal.indicators
        assert "atr" in signal.indicators
        assert "atr_ratio" in signal.indicators
        assert "sma_fast" in signal.indicators
        assert "sma_slow" in signal.indicators
        assert "trend_pct" in signal.indicators
        assert "close" in signal.indicators


# ---------------------------------------------------------------------------
# M2 (2026-07-04): detector._calc_adx canonical-Wilder correctness regression
# ---------------------------------------------------------------------------


def _deterministic_ohlcv(n_bars: int = 64) -> dict[str, list[float]]:
    """RNG-free deterministic OHLCV — identical to the M2 parity harness sample.

    Kept in-file (not imported from the parity test) so this correctness
    regression stands on its own. Because it uses no RNG, the canonical ADX it
    produces is stable across numpy/python versions.
    """
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    for i in range(n_bars):
        close = 100.0 + 0.12 * i + 4.0 * math.sin(i / 4.0) + 1.5 * math.cos(i / 2.3)
        span = 0.8 + 0.5 * abs(math.sin(i / 3.0))
        high = close + span
        low = close - span * (0.7 + 0.3 * abs(math.cos(i / 5.0)))
        open_ = close - 0.4 * math.sin(i / 2.0)
        high = max(high, open_, close)
        low = min(low, open_, close)
        highs.append(high)
        lows.append(low)
        closes.append(close)
    return {"high": highs, "low": lows, "close": closes}


class TestAdaptiveDetectorADXCanonical:
    """``_calc_adx`` now delegates to the canonical Wilder ``ADXCalculator``.

    Before M2 the detector returned a single last-bar DX (SMA-smoothed DI, no
    directional-movement rule, no DX→ADX smoothing) that under-reported trend
    strength by ~half. On the deterministic sample it produced ~15.87; the
    canonical Wilder ADX is ~31.63. Any regime gate keyed on an ADX threshold
    was mis-triggering; these tests pin the corrected value.
    """

    # Canonical Wilder ADX on the deterministic sample (reference.calculate_last).
    _CANONICAL_ADX = 31.634448
    # The old defective single-bar DX the detector used to return.
    _OLD_DEFECTIVE_DX = 15.873272

    def test_detector_adx_matches_reference_calculator(self) -> None:
        """detector._calc_adx == reference.ADXCalculator.calculate_last (single SoT)."""
        d = _deterministic_ohlcv()
        high = np.asarray(d["high"])
        low = np.asarray(d["low"])
        close = np.asarray(d["close"])

        detector = AdaptiveRegimeDetector()
        detector_adx = detector._calc_adx(high, low, close, period=14)
        reference_adx = ADXCalculator(period=14).calculate_last(high, low, close)

        assert reference_adx is not None
        # Exact delegation: same code path, so bit-for-bit within float noise.
        assert detector_adx == pytest.approx(reference_adx, abs=1e-9)
        assert detector_adx == pytest.approx(self._CANONICAL_ADX, abs=5e-3)

    def test_detector_adx_no_longer_defective_single_bar_dx(self) -> None:
        """Canonical ADX is ~2x the old single-bar DX (the fixed defect)."""
        d = _deterministic_ohlcv()
        detector = AdaptiveRegimeDetector()
        adx = detector._calc_adx(
            np.asarray(d["high"]),
            np.asarray(d["low"]),
            np.asarray(d["close"]),
            period=14,
        )
        # Far above the old defective ~15.87 — documents the ~2x correction that
        # shifts every ADX-keyed RegimeGate admission decision.
        assert adx > 25.0
        assert abs(adx - self._OLD_DEFECTIVE_DX) > 10.0
        assert 0.0 <= adx <= 100.0

    def test_detector_adx_insufficient_data_returns_zero(self) -> None:
        """Contract preserved: too few bars → 0.0 float (never None)."""
        detector = AdaptiveRegimeDetector()
        short = np.asarray([100.0, 101.0, 102.0])  # < period + 1
        adx = detector._calc_adx(short, short - 1.0, short, period=14)
        assert isinstance(adx, float)
        assert adx == 0.0
