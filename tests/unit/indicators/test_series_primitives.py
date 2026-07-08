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
    ema,
    rolling_return_std,
    rvol_last,
    sma,
    swing_low,
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
