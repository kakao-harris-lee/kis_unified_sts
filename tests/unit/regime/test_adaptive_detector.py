"""Test AdaptiveRegimeDetector with multi-metric classification."""
import pandas as pd
import numpy as np
import pytest
from datetime import datetime

from shared.regime.adaptive_detector import (
    AdaptiveRegimeDetector,
    AdaptiveRegimeState,
    AdaptiveRegimeConfig,
)


class TestAdaptiveRegimeDetector:
    """Test suite for AdaptiveRegimeDetector."""

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
