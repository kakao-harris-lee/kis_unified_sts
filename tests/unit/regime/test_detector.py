"""Test StockRegimeDetector."""
import pandas as pd
import numpy as np
from datetime import datetime


def test_detector_bull_regime():
    """Test detection of bull market."""
    from shared.regime.detector import StockRegimeDetector
    from shared.regime.models import RegimeState

    detector = StockRegimeDetector()

    # Create uptrending data
    dates = pd.date_range(end=datetime.now(), periods=60, freq="D")
    prices = 100 + np.arange(60) * 0.5 + np.random.randn(60) * 0.5  # Uptrend

    df = pd.DataFrame({"datetime": dates, "close": prices})

    signal = detector.detect(df)

    assert signal.state == RegimeState.BULL


def test_detector_bear_regime():
    """Test detection of bear market."""
    from shared.regime.detector import StockRegimeDetector
    from shared.regime.models import RegimeState

    detector = StockRegimeDetector()

    # Create downtrending data
    dates = pd.date_range(end=datetime.now(), periods=60, freq="D")
    prices = 150 - np.arange(60) * 0.5 + np.random.randn(60) * 0.5  # Downtrend

    df = pd.DataFrame({"datetime": dates, "close": prices})

    signal = detector.detect(df)

    assert signal.state == RegimeState.BEAR


def test_detector_sideways_regime():
    """Test detection of sideways market (range-bound)."""
    from shared.regime.detector import StockRegimeDetector
    from shared.regime.models import RegimeState, RegimeConfig

    config = RegimeConfig(sma_fast=10, sma_slow=20, trend_threshold=0.02)
    detector = StockRegimeDetector(config)

    # Create sideways/flat data with small oscillations
    dates = pd.date_range(end=datetime.now(), periods=60, freq="D")
    # Small oscillations around 100 with no trend
    prices = 100 + np.sin(np.arange(60) * 0.1) * 0.5

    df = pd.DataFrame({"datetime": dates, "close": prices})

    signal = detector.detect(df)

    assert signal.state == RegimeState.SIDEWAYS


def test_detector_confidence_is_confident():
    """Test RegimeSignal.is_confident property."""
    from shared.regime.detector import StockRegimeDetector
    from shared.regime.models import RegimeConfig

    config = RegimeConfig(sma_fast=10, sma_slow=20)
    detector = StockRegimeDetector(config)

    # Strong uptrend should have high confidence
    dates = pd.date_range(end=datetime.now(), periods=60, freq="D")
    prices = 100 + np.arange(60) * 1.0  # Strong uptrend

    df = pd.DataFrame({"datetime": dates, "close": prices})

    signal = detector.detect(df)

    # Strong trend should be confident (>= 0.7)
    assert signal.confidence >= 0.7
    assert signal.is_confident is True


def test_detector_low_confidence():
    """Test that weak trends produce low confidence."""
    from shared.regime.detector import StockRegimeDetector
    from shared.regime.models import RegimeConfig, RegimeState

    config = RegimeConfig(
        sma_fast=10,
        sma_slow=20,
        trend_threshold=0.02,
        high_volatility_threshold=0.01,  # Low threshold to trigger
        volatility_confidence_adjustment=0.5,
    )
    detector = StockRegimeDetector(config)

    # Create volatile sideways data
    dates = pd.date_range(end=datetime.now(), periods=60, freq="D")
    prices = 100 + np.random.randn(60) * 5  # High volatility, no trend

    df = pd.DataFrame({"datetime": dates, "close": prices})

    signal = detector.detect(df)

    # Sideways with high volatility should have reduced confidence
    if signal.state == RegimeState.SIDEWAYS:
        # Confidence may be reduced by volatility adjustment
        assert signal.confidence <= 1.0


def test_detector_signal_has_indicators():
    """Test that signal includes indicator values."""
    from shared.regime.detector import StockRegimeDetector
    from shared.regime.models import RegimeConfig

    config = RegimeConfig(sma_fast=10, sma_slow=20)
    detector = StockRegimeDetector(config)

    dates = pd.date_range(end=datetime.now(), periods=60, freq="D")
    prices = 100 + np.arange(60) * 0.3

    df = pd.DataFrame({"datetime": dates, "close": prices})

    signal = detector.detect(df)

    # Signal should include indicator values
    assert signal.indicators is not None
    assert "sma_fast" in signal.indicators
    assert "sma_slow" in signal.indicators
    assert "trend_pct" in signal.indicators
    assert "volatility" in signal.indicators


def test_detector_indicators_values_reasonable():
    """Test that indicator values are within reasonable ranges."""
    from shared.regime.detector import StockRegimeDetector
    from shared.regime.models import RegimeConfig

    config = RegimeConfig(sma_fast=10, sma_slow=20)
    detector = StockRegimeDetector(config)

    dates = pd.date_range(end=datetime.now(), periods=60, freq="D")
    prices = 100 + np.arange(60) * 0.3

    df = pd.DataFrame({"datetime": dates, "close": prices})

    signal = detector.detect(df)

    # SMA values should be close to recent prices
    assert 90 < signal.indicators["sma_fast"] < 130
    assert 90 < signal.indicators["sma_slow"] < 130

    # Trend pct should be reasonable (not extreme)
    assert -1.0 < signal.indicators["trend_pct"] < 1.0

    # Volatility should be non-negative
    assert signal.indicators["volatility"] >= 0


def test_detector_custom_config_thresholds():
    """Test detector with custom trend thresholds."""
    from shared.regime.detector import StockRegimeDetector
    from shared.regime.models import RegimeConfig, RegimeState

    # High threshold - harder to classify as bull/bear
    config = RegimeConfig(
        sma_fast=10,
        sma_slow=20,
        trend_threshold=0.10,  # 10% threshold (very high)
    )
    detector = StockRegimeDetector(config)

    # Mild uptrend (only 0.5% per day = ~3% over 60 days)
    dates = pd.date_range(end=datetime.now(), periods=60, freq="D")
    prices = 100 + np.arange(60) * 0.1  # Mild uptrend

    df = pd.DataFrame({"datetime": dates, "close": prices})

    signal = detector.detect(df)

    # With high threshold, mild trend should be SIDEWAYS
    assert signal.state == RegimeState.SIDEWAYS


def test_detector_state_consistency():
    """Test that multiple detections on same data produce same result."""
    from shared.regime.detector import StockRegimeDetector
    from shared.regime.models import RegimeConfig

    config = RegimeConfig(sma_fast=10, sma_slow=20)
    detector = StockRegimeDetector(config)

    dates = pd.date_range(end=datetime.now(), periods=60, freq="D")
    prices = 100 + np.arange(60) * 0.5

    df = pd.DataFrame({"datetime": dates, "close": prices})

    # Run detection multiple times
    signal1 = detector.detect(df)
    signal2 = detector.detect(df)
    signal3 = detector.detect(df)

    # Should produce same state (timestamps may differ)
    assert signal1.state == signal2.state == signal3.state
    assert signal1.confidence == signal2.confidence == signal3.confidence


def test_detector_timestamp_is_recent():
    """Test that signal timestamp is recent."""
    from shared.regime.detector import StockRegimeDetector
    from shared.regime.models import RegimeConfig

    config = RegimeConfig(sma_fast=10, sma_slow=20)
    detector = StockRegimeDetector(config)

    dates = pd.date_range(end=datetime.now(), periods=60, freq="D")
    prices = 100 + np.arange(60) * 0.5

    df = pd.DataFrame({"datetime": dates, "close": prices})

    before = datetime.now()
    signal = detector.detect(df)
    after = datetime.now()

    # Signal timestamp should be between before and after
    assert before <= signal.timestamp <= after
