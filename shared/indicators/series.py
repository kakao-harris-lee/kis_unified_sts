"""Series primitives for strategy consumers (P1-b2..b4 single owner).

Home of the small, generic indicator math that entry/exit generators used to
compute inline from raw price series (EMA regime filters, SMA/volume-MA,
rolling return volatility, RVOL, rolling extrema) — moved here so the
computation has exactly one owner inside the indicator package and strategies
only *read* precomputed values
(``docs/plans/2026-07-08-new-architecture-refactoring-plan.md`` §3, P1-b item 2).

P1-b items 3/4 extend this module with the conventions absorbed from the last
hand-rolled sites outside the package (services/trading residuals,
daily_scanner, accumulation scanner, LLM analyzers, regime detectors):
SMA-convention RSI, MACD lines (both EWM adjust conventions), plain rolling
std, trailing extrema/ROC/mean-ratio, mean-normalized regression slope, and
the padded-ATR variant. Each is a P1-c convergence candidate onto the engine
backends (see per-function notes).

Conventions are pinned bit-for-bit to the sites they absorb:

* pandas ``ewm(span=..., adjust=False)`` EMA and plain ``rolling(period)``
  (NaN warmup, ``min_periods == window``) — the same expressions the strategy
  files carried, and the same EMA convention as the engine's
  ``MomentumCompatBackend``/``DailyCompatBackend`` internals. Empirically
  bit-identical to the manual ``alpha = 2/(span+1)`` first-value-seeded loop
  the services/trading residuals used.
* ``rolling(period).std()`` uses the pandas default ``ddof=1``.

Golden pins: ``tests/unit/strategy/test_p1b2_embedded_math_golden.py`` (strategy
outputs), ``tests/unit/indicators/test_series_primitives.py`` (primitive
contracts), plus the P1-b3/b4 site pins
(``tests/unit/trading/test_p1b3_trading_residuals_golden.py``,
``tests/unit/test_daily_scanner_indicator_golden.py``,
``tests/unit/scanner/test_accumulation_indicator_golden.py``,
``tests/unit/llm/test_llm_indicator_golden.py``,
``tests/unit/regime/test_regime_indicator_golden.py``). Convergence of these
pandas conventions onto the TA-Lib backend is the separately-gated P1-c
convention flip — do not change values here without that gate.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from shared.indicators.reference import ATRCalculator


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


# ---------------------------------------------------------------------------
# P1-b3/b4 primitives (absorbed from services/scanner/llm/regime sites)
# ---------------------------------------------------------------------------


def rolling_std(series: pd.Series, period: int) -> pd.Series:
    """Plain rolling standard deviation, ``rolling(period).std()`` (``ddof=1``).

    NaN warmup (``min_periods == period``). Used for Bollinger-style band
    width and return-volatility filters where the caller supplies the series
    (prices or pre-computed returns).

    Args:
        series: Input series.
        period: Rolling window length (> 0).

    Returns:
        Rolling std series aligned to the input index.
    """
    return series.rolling(period).std()


def rsi_sma(close: pd.Series, period: int = 14) -> pd.Series:
    """SMA-convention RSI series (Cutler-style rolling-mean gains/losses).

    ``gain/loss = rolling(period).mean()`` of the positive/negative deltas —
    NOT Wilder-smoothed. Values: all-gain windows → 100.0 (``rs = inf``),
    all-loss windows → 0.0, flat windows (0/0) → NaN (callers apply their own
    sentinel), warmup → NaN.

    This is the convention the LLM analyzers, daily scanner, and index
    analyzers carried inline. P1-c convergence candidate onto the engine's
    Wilder RSI (``reference.wilder_rsi`` / TA-Lib ``rsi``) — a numeric-only
    behavior change gated separately.

    Args:
        close: Close-price series.
        period: RSI lookback (default 14).

    Returns:
        RSI series in ``[0, 100]`` aligned to the input index.
    """
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def macd_lines(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal_span: int = 9,
    *,
    adjust: bool = False,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD / signal / histogram series.

    ``adjust=False`` (default) is the recursive EWM convention (same as
    :func:`ema` and the streaming engine's MACD). ``adjust=True`` is the
    pandas-default weighted EWM that the legacy LLM futures analyzers carried
    (``close.ewm(span=..)`` without ``adjust=``); it is kept only to preserve
    those sites bit-for-bit and is a P1-c convergence candidate onto the
    ``adjust=False`` convention.

    Args:
        close: Close-price series.
        fast: Fast EMA span (default 12).
        slow: Slow EMA span (default 26).
        signal_span: Signal EMA span (default 9).
        adjust: pandas EWM ``adjust`` flag (see above).

    Returns:
        ``(macd, signal, histogram)`` series aligned to the input index.
    """
    if adjust:
        fast_ema = close.ewm(span=fast, adjust=True).mean()
        slow_ema = close.ewm(span=slow, adjust=True).mean()
        macd = fast_ema - slow_ema
        signal = macd.ewm(span=signal_span, adjust=True).mean()
    else:
        macd = ema(close, fast) - ema(close, slow)
        signal = ema(macd, signal_span)
    return macd, signal, macd - signal


def trailing_max(values: pd.Series | Sequence[float], period: int) -> float | None:
    """Maximum of the last ``min(period, len)`` values.

    Rolling-extrema primitive for high-N breakout levels and high-proximity
    metrics (the max-side sibling of :func:`swing_low`, but *including* the
    last bar and clamping the window to the available history).

    Args:
        values: Price series or plain sequence (last element = newest).
        period: Trailing window length; ``<= 0`` returns ``None``.

    Returns:
        The window maximum (NaN entries skipped per pandas ``max``), or
        ``None`` when the window is empty. NaN is returned as-is when every
        in-window value is NaN.
    """
    if period <= 0:
        return None
    series = (
        values
        if isinstance(values, pd.Series)
        else pd.Series(list(values), dtype=float)
    )
    window = series.tail(min(len(series), period))
    if len(window) == 0:
        return None
    return float(window.max())


def trailing_change_pct(
    values: pd.Series | Sequence[float], offset: int
) -> float | None:
    """Percent change from ``offset`` bars back: ``(last / base - 1) * 100``.

    ROC/momentum primitive (ratio form). ``base = values[-offset - 1]``, i.e.
    the change spans exactly ``offset`` bar-to-bar moves. NaN inputs propagate
    (only an exact-zero base is guarded).

    Args:
        values: Price series or plain sequence (last element = newest).
        offset: Number of bars back for the base; ``<= 0`` returns ``None``.

    Returns:
        Percent change, or ``None`` when there are not enough values or the
        base is exactly zero.
    """
    if offset <= 0:
        return None
    series = (
        values
        if isinstance(values, pd.Series)
        else pd.Series(list(values), dtype=float)
    )
    if len(series) <= offset:
        return None
    base = float(series.iloc[-offset - 1])
    last = float(series.iloc[-1])
    if base == 0.0:
        return None
    return ((last / base) - 1.0) * 100


def relative_strength_pct(
    subject_close: pd.Series, benchmark_close: pd.Series, window: int
) -> float | None:
    """Relative strength: subject minus benchmark percent change over a window.

    Window-edge convention (difference form): both changes are computed as
    ``(end - start) / start * 100`` with ``start = close[-window]`` — i.e. the
    change spans ``window - 1`` bar-to-bar moves. This is the accumulation
    scanner's 20d relative-strength convention; note it differs by one bar
    from :func:`trailing_change_pct` (P1-c convergence candidate).

    Args:
        subject_close: Subject (stock) close series.
        benchmark_close: Benchmark (market index) close series.
        window: Trailing window length (> 0).

    Returns:
        ``subject_pct - benchmark_pct``, or ``None`` when either series is
        shorter than ``window`` or either start price is zero.
    """
    if window <= 0 or len(subject_close) < window or len(benchmark_close) < window:
        return None
    s_start = subject_close.iloc[-window]
    s_end = subject_close.iloc[-1]
    b_start = benchmark_close.iloc[-window]
    b_end = benchmark_close.iloc[-1]
    if s_start == 0 or b_start == 0:
        return None
    s_pct = (s_end - s_start) / s_start * 100
    b_pct = (b_end - b_start) / b_start * 100
    return float(s_pct - b_pct)


def trailing_mean_ratio(
    values: np.ndarray | Sequence[float], short_window: int, long_window: int
) -> tuple[float | None, float, float]:
    """Ratio of short-window to long-window trailing means (``np.mean`` form).

    RVOL-style volume-buildup primitive: ``mean(values[-short:]) /
    mean(values[-long:])``. Windows clamp to the available history (numpy
    slice semantics) — callers gate on minimum length. P1-c convergence
    candidate onto the engine's ``rvol`` indicator (short/long window ratio).

    Args:
        values: Input sequence (typically volumes, newest last).
        short_window: Short trailing window (> 0).
        long_window: Long trailing window (> 0).

    Returns:
        ``(ratio, short_avg, long_avg)``; ``ratio`` is ``None`` when the long
        mean is zero. Empty input returns ``(None, 0.0, 0.0)``.
    """
    arr = np.asarray(values)
    if short_window <= 0 or long_window <= 0 or arr.shape[0] == 0:
        return None, 0.0, 0.0
    short_avg = float(np.mean(arr[-short_window:]))
    long_avg = float(np.mean(arr[-long_window:]))
    if long_avg == 0:
        return None, short_avg, long_avg
    return short_avg / long_avg, short_avg, long_avg


def normalized_slope(values: Sequence[float] | np.ndarray) -> float | None:
    """Mean-normalized linear-regression slope of a series.

    Fits ``y / mean(y) = m*x + b`` over ``x = 0..n-1`` (``np.polyfit`` degree
    1) and returns ``m`` — the per-bar trend of the series expressed as a
    fraction of its mean level. This is the accumulation scanner's OBV-trend
    convention (scale-free so OBV magnitude does not matter).

    Args:
        values: Input sequence (e.g. OBV values, newest last). Integer input
            is kept as-is so the division matches the historical int/float
            promotion exactly.

    Returns:
        Normalized slope, or ``None`` when fewer than 2 values are supplied
        or the mean is zero.
    """
    y = np.asarray(values)
    if y.shape[0] < 2:
        return None
    y_mean = np.mean(y)
    if y_mean == 0:
        return None
    coeffs = np.polyfit(np.arange(y.shape[0]), y / y_mean, 1)
    return float(coeffs[0])


def atr_series_padded(
    high: np.ndarray | Sequence[float],
    low: np.ndarray | Sequence[float],
    close: np.ndarray | Sequence[float],
    period: int = 14,
) -> np.ndarray:
    """Full-length ATR with partial-window warmup (``min_periods=1``).

    Padded convention (accumulation scanner): the first bar's True Range is
    seeded with ``prev_close = close[0]`` (so ``TR[0] = max(H0-L0, |H0-C0|,
    |L0-C0|)``), later bars use the canonical
    :meth:`~shared.indicators.reference.ATRCalculator.true_range`, and the
    smoothing is a ``rolling(period, min_periods=1)`` mean — every position
    holds a value (no NaN warmup). P1-c convergence candidate onto
    ``ATRCalculator(mode="sma")`` (NaN-warmup convention).

    Args:
        high: High-price series.
        low: Low-price series.
        close: Close-price series.
        period: ATR period (default 14).

    Returns:
        ATR array of the same length as the input (empty input → empty array).
    """
    h = np.asarray(high, dtype=float)
    low_a = np.asarray(low, dtype=float)
    c = np.asarray(close, dtype=float)
    if h.shape[0] == 0:
        return np.empty(0, dtype=float)
    tr_tail = ATRCalculator.true_range(h, low_a, c)
    tr0 = max(h[0] - low_a[0], abs(h[0] - c[0]), abs(low_a[0] - c[0]))
    true_range = np.concatenate(([tr0], tr_tail))
    return pd.Series(true_range).rolling(window=period, min_periods=1).mean().to_numpy()
