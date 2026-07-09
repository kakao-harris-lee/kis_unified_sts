"""Contract tests for the P1-b2 series primitives and stateful quote trackers.

Pins the exact conventions the primitives absorbed from the strategy files
(``shared/indicators/series.py``, ``shared/indicators/engine/stateful.py``):
pandas ``ewm(span, adjust=False)`` EMA, plain ``rolling(period)`` SMA with NaN
warmup, ``pct_change().rolling().std()`` return-vol (ddof=1), RVOL None-gating,
swing-low excluding the signal bar, timestamped window extrema, minute-keyed
return / spike-hit tracking.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from shared.indicators.engine.stateful import MinuteReturnTracker, SpikeHitWindow
from shared.indicators.series import (
    atr_series_padded,
    ema,
    macd_lines,
    normalized_slope,
    relative_strength_pct,
    rolling_return_std,
    rolling_std,
    rsi_sma,
    rvol_last,
    sma,
    swing_low,
    trailing_change_pct,
    trailing_max,
    trailing_mean_ratio,
    window_extremes,
)

_KST = ZoneInfo("Asia/Seoul")


@pytest.fixture()
def close() -> pd.Series:
    rng = np.random.default_rng(5)
    return pd.Series(100.0 + np.cumsum(rng.normal(0.0, 0.5, 60)))


# ---------------------------------------------------------------------------
# Stateless series primitives
# ---------------------------------------------------------------------------


def test_ema_matches_pandas_ewm_convention(close: pd.Series) -> None:
    expected = close.ewm(span=20, adjust=False).mean()
    pd.testing.assert_series_equal(ema(close, 20), expected)


def test_sma_matches_plain_rolling_with_nan_warmup(close: pd.Series) -> None:
    expected = close.rolling(20).mean()
    got = sma(close, 20)
    pd.testing.assert_series_equal(got, expected)
    assert got.iloc[:19].isna().all()
    assert not np.isnan(got.iloc[19])


def test_rolling_return_std_matches_pct_change_convention(close: pd.Series) -> None:
    expected = close.pct_change().rolling(30).std()
    pd.testing.assert_series_equal(rolling_return_std(close, 30), expected)


def test_rvol_last_value() -> None:
    volume = pd.Series([100.0, 200.0, 300.0, 400.0])
    # SMA(2) last = 350 -> rvol = 400 / 350
    assert rvol_last(volume, 2) == pytest.approx(400.0 / 350.0)


def test_rvol_last_none_when_warmup_or_empty_or_zero() -> None:
    assert rvol_last(pd.Series([], dtype=float), 5) is None
    assert rvol_last(pd.Series([100.0, 200.0]), 5) is None  # NaN baseline
    assert rvol_last(pd.Series([0.0, 0.0, 0.0]), 3) is None  # zero baseline


def test_swing_low_excludes_signal_bar() -> None:
    lows = pd.Series([10.0, 9.0, 9.5, 8.5, 7.0])
    # lookback=3 -> window is bars [-4:-1] = [9.0, 9.5, 8.5]; the 7.0 signal
    # bar is excluded.
    assert swing_low(lows, 3) == pytest.approx(8.5)


def test_swing_low_none_when_insufficient() -> None:
    assert swing_low(pd.Series([10.0, 9.0, 8.0]), 3) is None


def test_window_extremes_filters_by_cutoff() -> None:
    now = datetime(2026, 3, 16, 10, 0, tzinfo=_KST)
    history = [
        (now - timedelta(seconds=120), 999.0),  # outside the 60s window
        (now - timedelta(seconds=45), 105.0),
        (now - timedelta(seconds=10), 95.0),
        (now, 100.0),
    ]
    assert window_extremes(history, 60.0, now) == (105.0, 95.0)


def test_window_extremes_none_when_empty_window() -> None:
    now = datetime(2026, 3, 16, 10, 0, tzinfo=_KST)
    history = [(now - timedelta(seconds=120), 100.0)]
    assert window_extremes(history, 60.0, now) is None


# ---------------------------------------------------------------------------
# P1-b3/b4 primitives
# ---------------------------------------------------------------------------


def test_rolling_std_matches_pandas_convention(close: pd.Series) -> None:
    pd.testing.assert_series_equal(rolling_std(close, 20), close.rolling(20).std())


def test_rsi_sma_matches_rolling_mean_convention(close: pd.Series) -> None:
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    want = 100 - (100 / (1 + gain / loss))
    pd.testing.assert_series_equal(rsi_sma(close, 14), want)


def test_rsi_sma_degenerate_windows() -> None:
    up = pd.Series([float(100 + i) for i in range(20)])
    down = pd.Series([float(200 - i) for i in range(20)])
    flat = pd.Series([100.0] * 20)
    assert rsi_sma(up, 14).iloc[-1] == 100.0
    assert rsi_sma(down, 14).iloc[-1] == 0.0
    assert pd.isna(rsi_sma(flat, 14).iloc[-1])  # 0/0 — caller applies sentinel


def test_macd_lines_adjust_false_composes_ema(close: pd.Series) -> None:
    macd, signal, hist = macd_lines(close)
    pd.testing.assert_series_equal(macd, ema(close, 12) - ema(close, 26))
    pd.testing.assert_series_equal(signal, ema(macd, 9))
    pd.testing.assert_series_equal(hist, macd - signal)


def test_macd_lines_adjust_true_legacy_convention(close: pd.Series) -> None:
    macd, signal, hist = macd_lines(close, adjust=True)
    want_macd = close.ewm(span=12).mean() - close.ewm(span=26).mean()
    pd.testing.assert_series_equal(macd, want_macd)
    pd.testing.assert_series_equal(signal, want_macd.ewm(span=9).mean())
    pd.testing.assert_series_equal(hist, macd - signal)
    # The two conventions genuinely differ (P1-c convergence candidate).
    assert macd_lines(close)[0].iloc[-1] != macd.iloc[-1]


def test_trailing_max_clamps_and_gates() -> None:
    assert trailing_max([1.0, 5.0, 3.0], 2) == 5.0
    assert trailing_max([1.0, 5.0, 3.0], 10) == 5.0  # clamps to history
    assert trailing_max(pd.Series([2.0, 7.0, 4.0]), 2) == 7.0
    assert trailing_max([], 5) is None
    assert trailing_max([1.0], 0) is None


def test_trailing_change_pct_ratio_form() -> None:
    values = [100.0, 110.0, 121.0]
    assert trailing_change_pct(values, 2) == ((121.0 / 100.0) - 1.0) * 100
    assert trailing_change_pct(values, 3) is None  # needs offset+1 values
    assert trailing_change_pct([0.0, 100.0], 1) is None  # zero base
    assert trailing_change_pct(values, 0) is None


def test_relative_strength_pct_diff_form() -> None:
    subject = pd.Series([100.0, 105.0, 110.0])
    benchmark = pd.Series([200.0, 202.0, 204.0])
    want = ((110.0 - 100.0) / 100.0 * 100) - ((204.0 - 200.0) / 200.0 * 100)
    assert relative_strength_pct(subject, benchmark, 3) == want
    assert relative_strength_pct(subject, benchmark, 4) is None
    assert relative_strength_pct(pd.Series([0.0, 1.0]), benchmark, 2) is None


def test_trailing_mean_ratio_np_mean_form() -> None:
    volumes = np.array([10.0, 10.0, 10.0, 30.0, 30.0])
    ratio, short_avg, long_avg = trailing_mean_ratio(volumes, 2, 5)
    assert (ratio, short_avg, long_avg) == (30.0 / 18.0, 30.0, 18.0)
    assert trailing_mean_ratio(np.zeros(5), 2, 5) == (None, 0.0, 0.0)
    assert trailing_mean_ratio([], 2, 5) == (None, 0.0, 0.0)


def test_normalized_slope_mean_normalized_polyfit() -> None:
    y = np.array([100.0, 110.0, 120.0, 130.0])
    want = float(np.polyfit(np.arange(4), y / np.mean(y), 1)[0])
    assert normalized_slope(y) == want
    assert normalized_slope([1.0]) is None
    assert normalized_slope([1.0, -1.0]) is None  # zero mean


def test_atr_series_padded_convention() -> None:
    rng = np.random.default_rng(11)
    n = 30
    close = 100.0 + np.cumsum(rng.normal(0.0, 1.0, n))
    spread = np.abs(rng.normal(0.0, 0.6, n))
    high, low = close + spread, close - spread
    got = atr_series_padded(high, low, close, period=14)
    # Reference: np.roll prev_close with first bar seeded by close[0].
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(
        high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close))
    )
    want = pd.Series(tr).rolling(window=14, min_periods=1).mean().values
    assert np.array_equal(got, want)
    assert not np.isnan(got).any()  # padded: no NaN warmup
    assert atr_series_padded([], [], [], 14).shape == (0,)
    single = atr_series_padded([101.0], [99.0], [100.0], 14)
    assert single.tolist() == [2.0]


# ---------------------------------------------------------------------------
# Stateful minute-keyed trackers
# ---------------------------------------------------------------------------


def test_minute_return_tracker_read_and_commit() -> None:
    tracker = MinuteReturnTracker()
    assert tracker.return_pct("A", 100, 101.0) == 0.0  # nothing committed yet
    tracker.commit("A", 100, 100.0)
    # Same minute -> 0.0 (strictly-greater key required)
    assert tracker.return_pct("A", 100, 101.0) == 0.0
    # Next minute -> +1%
    assert tracker.return_pct("A", 101, 101.0) == pytest.approx(1.0)
    # Read is pure: repeated reads identical, other codes unaffected
    assert tracker.return_pct("A", 101, 101.0) == pytest.approx(1.0)
    assert tracker.return_pct("B", 101, 101.0) == 0.0
    # Non-positive committed close -> 0.0
    tracker.commit("A", 101, 0.0)
    assert tracker.return_pct("A", 102, 101.0) == 0.0
    tracker.reset("A")
    assert tracker.return_pct("A", 103, 101.0) == 0.0


def test_spike_hit_window_dedupes_minutes_and_prunes() -> None:
    window = SpikeHitWindow(lookback_minutes=3)
    assert window.record_and_count("A", 100, True) == 1
    # Same minute is not re-recorded (first observation wins)
    assert window.record_and_count("A", 100, False) == 1
    assert window.record_and_count("A", 101, False) == 1
    assert window.record_and_count("A", 102, True) == 2
    # Minute 103 prunes minute 100 (window = 101..103)
    assert window.record_and_count("A", 103, True) == 2
    # Independent per code
    assert window.record_and_count("B", 103, True) == 1
    window.reset()
    assert window.record_and_count("A", 104, False) == 0


def test_spike_hit_window_rejects_non_positive_lookback() -> None:
    with pytest.raises(ValueError):
        SpikeHitWindow(lookback_minutes=0)
