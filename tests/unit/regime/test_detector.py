"""Test StockRegimeDetector."""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


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
