"""Realized variance computation from intraday bars.

Provides 5m / 30m / daily RV components used as HAR-RV regressors.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def resample_to_5min(bars_1m: pd.DataFrame) -> pd.DataFrame:
    """Resample 1-minute bars to 5-minute closes. Forward-fills gaps.

    Args:
        bars_1m: DataFrame with DatetimeIndex (UTC) and ``close`` column.

    Returns:
        DataFrame with 5-minute interval index and ``close`` column.
    """
    if bars_1m.empty:
        return bars_1m
    out = bars_1m["close"].resample("5min").last()
    out = out.ffill()
    return out.to_frame(name="close")


def compute_intraday_realized_variance(bars_1m: pd.DataFrame) -> float:
    """Sum of 5-minute squared log-returns over the provided window.

    A daily realized variance is the sum across one trading day; this helper
    is window-agnostic — caller chooses the slice.

    Args:
        bars_1m: 1-minute bars with ``close``.

    Returns:
        Realized variance (unitless squared-return sum). 0.0 if fewer than 2
        bars after resample.
    """
    if bars_1m.empty or len(bars_1m) < 2:
        return 0.0
    df5 = resample_to_5min(bars_1m)
    if len(df5) < 2:
        return 0.0
    log_returns = np.log(df5["close"]).diff().dropna()
    if log_returns.empty:
        return 0.0
    return float((log_returns**2).sum())


def daily_rv_series(
    bars_1m: pd.DataFrame,
    session_tz: str = "Asia/Seoul",
    regular_session_only: bool = True,
    session_start: str = "09:00",
    session_end: str = "15:30",
) -> pd.Series:
    """Compute one daily RV per session date.

    Args:
        bars_1m: 1-minute bars with UTC index.
        session_tz: timezone used to assign a calendar date to each bar.
        regular_session_only: if true, ignore bars outside the regular KST
            cash/futures day session before grouping.
        session_start: inclusive local session start in HH:MM.
        session_end: exclusive local session end in HH:MM.

    Returns:
        Series indexed by Date (KST), values = realized variance for that day.
    """
    if bars_1m.empty:
        return pd.Series(dtype=float)
    local = bars_1m.copy()
    if local.index.tz is None:
        local.index = local.index.tz_localize("UTC")
    local.index = local.index.tz_convert(session_tz)
    if regular_session_only:
        start = pd.to_datetime(session_start).time()
        end = pd.to_datetime(session_end).time()
        times = local.index.time
        local = local[(times >= start) & (times < end)]
        if local.empty:
            return pd.Series(dtype=float)
    local["session_date"] = local.index.date
    rvs: dict = {}
    for session_date, group in local.groupby("session_date"):
        rvs[session_date] = compute_intraday_realized_variance(
            group.drop(columns=["session_date"])
        )
    return pd.Series(rvs).sort_index()
