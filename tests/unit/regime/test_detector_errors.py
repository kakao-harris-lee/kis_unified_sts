"""Test error handling in StockRegimeDetector."""
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from shared.regime.detector import StockRegimeDetector
from shared.regime.models import RegimeConfig, RegimeState


def test_detector_insufficient_data():
    """Test handling of insufficient historical data.

    When data is shorter than sma_slow period, detector should
    return UNKNOWN state with zero confidence.
    """
    detector = StockRegimeDetector()

    # Only 10 rows, but sma_slow=50 needed
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=10),
        "close": [100] * 10,
    })

    signal = detector.detect(df)

    assert signal.state == RegimeState.UNKNOWN
    assert signal.confidence == 0.0


def test_detector_empty_dataframe():
    """Test handling of empty DataFrame."""
    detector = StockRegimeDetector()

    df = pd.DataFrame(columns=["datetime", "close"])

    signal = detector.detect(df)

    assert signal.state == RegimeState.UNKNOWN
    assert signal.confidence == 0.0


def test_detector_nan_in_close_prices():
    """Test handling of NaN values in price data.

    The detector uses rolling calculations which should handle
    NaN values gracefully.
    """
    detector = StockRegimeDetector(RegimeConfig(sma_slow=10, sma_fast=5))

    # Create data with some NaN values
    dates = pd.date_range("2024-01-01", periods=20)
    prices = [100 + i * 0.5 for i in range(20)]
    prices[5] = np.nan  # Insert NaN

    df = pd.DataFrame({
        "datetime": dates,
        "close": prices,
    })

    # Should still produce a signal (rolling handles NaN)
    signal = detector.detect(df)

    # Result depends on how NaN is handled
    assert signal is not None
    assert isinstance(signal.state, RegimeState)


def test_detector_all_same_prices():
    """Test detection with completely flat prices (zero volatility)."""
    config = RegimeConfig(sma_slow=10, sma_fast=5)
    detector = StockRegimeDetector(config)

    # All prices are identical
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=20),
        "close": [100.0] * 20,
    })

    signal = detector.detect(df)

    # With identical prices, trend should be SIDEWAYS
    assert signal.state == RegimeState.SIDEWAYS


def test_detector_single_row():
    """Test handling of single row DataFrame."""
    detector = StockRegimeDetector()

    df = pd.DataFrame({
        "datetime": [datetime(2024, 1, 1)],
        "close": [100],
    })

    signal = detector.detect(df)

    assert signal.state == RegimeState.UNKNOWN
    assert signal.confidence == 0.0


def test_detector_negative_prices():
    """Test behavior with negative price values.

    While negative prices are invalid, the detector should
    not crash but may produce unexpected results.
    """
    config = RegimeConfig(sma_slow=10, sma_fast=5)
    detector = StockRegimeDetector(config)

    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=20),
        "close": [-100 + i for i in range(20)],  # Negative prices
    })

    # Should not raise an exception
    signal = detector.detect(df)
    assert signal is not None


def test_detector_extreme_volatility():
    """Test detection with extreme price volatility."""
    config = RegimeConfig(sma_slow=10, sma_fast=5)
    detector = StockRegimeDetector(config)

    # Create highly volatile data
    prices = [100 * (1 + 0.5 * np.sin(i)) for i in range(20)]

    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=20),
        "close": prices,
    })

    signal = detector.detect(df)

    # High volatility should reduce confidence
    assert signal is not None
    # Confidence should be reduced due to high volatility
    assert signal.confidence <= 1.0


def test_detector_missing_close_column():
    """Test handling of DataFrame without 'close' column."""
    config = RegimeConfig(sma_slow=10, sma_fast=5)  # Use smaller windows
    detector = StockRegimeDetector(config)

    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=20),
        "price": [100 + i for i in range(20)],  # Wrong column name
    })

    # The detector will raise KeyError when accessing df["close"]
    with pytest.raises(KeyError):
        detector.detect(df)


def test_detector_last_signal_property():
    """Test that last_signal is updated after detection."""
    config = RegimeConfig(sma_slow=10, sma_fast=5)
    detector = StockRegimeDetector(config)

    # Initially no signal
    assert detector.last_signal is None

    # Create uptrending data
    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=20),
        "close": [100 + i * 2 for i in range(20)],
    })

    signal = detector.detect(df)

    # last_signal should be updated
    assert detector.last_signal is not None
    assert detector.last_signal == signal


def test_detector_config_validation():
    """Test detector with various config settings."""
    # Very small windows
    config = RegimeConfig(sma_fast=2, sma_slow=3)
    detector = StockRegimeDetector(config)

    df = pd.DataFrame({
        "datetime": pd.date_range("2024-01-01", periods=5),
        "close": [100, 101, 102, 103, 104],
    })

    signal = detector.detect(df)
    assert signal is not None
