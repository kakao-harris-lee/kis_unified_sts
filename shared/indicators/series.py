"""Series primitives for strategy consumers (P1-b2 single owner).

Home of the small, generic indicator math that entry/exit generators used to
compute inline from raw price series (EMA regime filters, SMA/volume-MA,
rolling return volatility, RVOL, rolling extrema) — moved here so the
computation has exactly one owner inside the indicator package and strategies
only *read* precomputed values
(``docs/plans/2026-07-08-new-architecture-refactoring-plan.md`` §3, P1-b item 2).

Conventions are pinned bit-for-bit to the strategy sites they absorb:

* pandas ``ewm(span=..., adjust=False)`` EMA and plain ``rolling(period)``
  (NaN warmup, ``min_periods == window``) — the same expressions the strategy
  files carried, and the same EMA convention as the engine's
  ``MomentumCompatBackend``/``DailyCompatBackend`` internals.
* ``rolling(period).std()`` uses the pandas default ``ddof=1``.

Golden pins: ``tests/unit/strategy/test_p1b2_embedded_math_golden.py`` (strategy
outputs) and ``tests/unit/indicators/test_series_primitives.py`` (primitive
contracts). Convergence of these pandas conventions onto the TA-Lib backend is
the separately-gated P1-c convention flip — do not change values here without
that gate.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd


def ema(series: pd.Series, span: int) -> pd.Series:
    """Exponential moving average, ``ewm(span=span, adjust=False).mean()``.

    Args:
        series: Input series (e.g. close prices).
        span: EMA span (> 0).

    Returns:
        EMA series aligned to the input index.
    """
    return series.ewm(span=span, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    """Simple moving average with NaN warmup (``min_periods == period``).

    Args:
        series: Input series (e.g. close prices or volume).
        period: Rolling window length (> 0).

    Returns:
        SMA series aligned to the input index (NaN for the first
        ``period - 1`` rows).
    """
    return series.rolling(period).mean()


def rolling_return_std(close: pd.Series, period: int) -> pd.Series:
    """Rolling standard deviation of simple bar-to-bar returns.

    ``close.pct_change().rolling(period).std()`` — the return-volatility
    filter convention (pandas default ``ddof=1``; NaN warmup).

    Args:
        close: Close-price series.
        period: Rolling window length (> 0).

    Returns:
        Return-volatility series aligned to the input index.
    """
    return close.pct_change().rolling(period).std()


def rvol_last(volume: pd.Series, period: int) -> float | None:
    """Latest relative volume: last volume over its ``period``-bar SMA.

    Args:
        volume: Volume series.
        period: SMA window for the volume baseline (> 0).

    Returns:
        ``volume[-1] / sma(volume, period)[-1]``, or ``None`` when the series
        is empty or the baseline is not yet available / not positive.
    """
    if len(volume) == 0:
        return None
    vol_ma = sma(volume, period).iloc[-1]
    if pd.isna(vol_ma) or float(vol_ma) <= 0.0:
        return None
    return float(volume.iloc[-1]) / float(vol_ma)


def swing_low(lows: pd.Series, lookback: int) -> float | None:
    """Lowest low over the ``lookback`` bars *before* the last (signal) bar.

    Rolling-extrema primitive for swing-low stops: the window excludes the
    current bar so an intrabar low cannot stop itself out.

    Args:
        lows: Low-price series (last element = current/signal bar).
        lookback: Number of prior bars to scan (> 0).

    Returns:
        The window minimum, or ``None`` when fewer than ``lookback + 1`` bars
        are available.
    """
    if len(lows) < lookback + 1:
        return None
    window = lows.iloc[-(lookback + 1) : -1]
    if window.empty:
        return None
    return float(window.min())


def window_extremes(
    history: list[tuple[datetime, float]],
    window_seconds: float,
    current_ts: datetime,
) -> tuple[float, float] | None:
    """(max, min) of the prices whose timestamp falls inside a rolling window.

    Rolling-extrema primitive over a timestamped tick history: only entries
    with ``ts >= current_ts - window_seconds`` are considered. Interpretation
    of the extremes (e.g. adverse-move direction per position side) stays with
    the caller.

    Args:
        history: ``(timestamp, price)`` pairs in any order.
        window_seconds: Rolling window width in seconds.
        current_ts: Right edge of the window (tz-aware KST preferred).

    Returns:
        ``(peak, trough)`` of the in-window prices, or ``None`` when no entry
        falls inside the window.
    """
    cutoff = current_ts - timedelta(seconds=window_seconds)
    in_window = [price for ts, price in history if ts >= cutoff]
    if not in_window:
        return None
    return max(in_window), min(in_window)
