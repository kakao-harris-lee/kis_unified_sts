"""Tests for realized variance computation."""
import numpy as np
import pandas as pd
import pytest

from shared.forecasting.realized_variance import (
    compute_intraday_realized_variance,
    resample_to_5min,
)


@pytest.fixture
def synthetic_1min_bars():
    """390 minutes (one KOSPI session) of synthetic prices with known vol."""
    n = 390
    np.random.seed(42)
    # log returns ~ N(0, 0.0005)  ≈ 0.5% intraday vol
    returns = np.random.normal(0, 0.0005, n)
    log_prices = 5.5 + np.cumsum(returns)  # start ≈ 244 (KOSPI200 ~250)
    closes = np.exp(log_prices)
    times = pd.date_range("2026-05-12 00:00:00", periods=n, freq="1min", tz="UTC")
    return pd.DataFrame({"close": closes}, index=times)


def test_resample_to_5min_aggregates_correctly(synthetic_1min_bars):
    df5 = resample_to_5min(synthetic_1min_bars)
    assert len(df5) == 390 // 5  # 78 bars
    # Each 5m close = last 1m close of that window
    assert df5.iloc[0]["close"] == pytest.approx(
        synthetic_1min_bars.iloc[4]["close"]
    )


def test_resample_to_5min_with_missing_minutes_forward_fills():
    times = pd.date_range("2026-05-12 00:00:00", periods=10, freq="1min", tz="UTC")
    closes = pd.Series([100.0] * 10, index=times)
    closes.iloc[3] = np.nan
    df = pd.DataFrame({"close": closes})
    df5 = resample_to_5min(df)
    assert not df5["close"].isna().any()


def test_compute_intraday_realized_variance_positive(synthetic_1min_bars):
    rv = compute_intraday_realized_variance(synthetic_1min_bars)
    assert rv > 0
    # ≈ 78 × 0.0005² = 1.95e-5, within order of magnitude
    assert 1e-6 < rv < 1e-3


def test_compute_realized_variance_empty_returns_zero():
    empty = pd.DataFrame({"close": []}, index=pd.DatetimeIndex([], tz="UTC"))
    assert compute_intraday_realized_variance(empty) == 0.0


def test_compute_realized_variance_single_bar_returns_zero():
    times = pd.date_range("2026-05-12 00:00:00", periods=1, freq="1min", tz="UTC")
    df = pd.DataFrame({"close": [100.0]}, index=times)
    assert compute_intraday_realized_variance(df) == 0.0
