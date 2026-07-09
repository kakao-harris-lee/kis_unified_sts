"""Backtest-adapter-convention indicator backend (value-preserving delegation).

The ``shared/backtest`` adapters historically hand-rolled their indicator math
inline (``daily_adapter.prescan_data``, ``adapter._MarketDataEnricher.enrich``,
``market_context_replay._compute_atr``) — the root of backtest↔live indicator
divergence flagged by P1-b of
``docs/plans/2026-07-08-new-architecture-refactoring-plan.md``. Following the
established compat-backend pattern (:mod:`daily_backend`, :mod:`momentum_backend`,
:mod:`streaming_backend`), this backend hosts those exact conventions —
**reproduced bit-for-bit, moved verbatim** — behind the ``IndicatorBackend``
interface so the indicator package is the single owner of the math. The
adapters become thin delegates; the golden regression
``tests/unit/backtest/test_indicator_delegation_golden.py`` pins bit-identity.

Convention notes (each id documents where it deliberately differs from the
standard/reference implementations — P1-c convention-flip candidates):

* ``sma`` — pandas trailing rolling mean with an explicit ``min_periods`` knob
  (``min_periods=period`` for the daily adapter's SMA-200/20/60 full-window
  contract, ``min_periods=1`` for its ``ma20``).
* ``rsi`` — the daily backtest Wilder-EMA RSI: ``ewm(alpha=1/period)`` on
  ``where``-clamped gains/losses. Unlike ``shared.indicators.reference.wilder_rsi``
  it emits **NaN** (not 100/50) on zero-loss / flat windows (zero-gain windows
  yield ``0.0``, matching the reference), and the ``where(..., 0.0)`` fill makes
  bar 0 a hard zero rather than NaN, which shifts the ewm seed one bar earlier.
* ``atr`` — SMA-of-TR where bar 0's TR is ``high-low`` (the pandas
  ``concat(...).max(axis=1)`` NaN-skip) and warmup is ``min_periods=period``.
  Differs from ``reference.ATRCalculator(mode="sma")`` only in that bar-0 TR
  inclusion (the reference drops bar 0, so its first valid value lands one bar
  later and excludes the seed TR).
* ``atr_partial`` — the futures replay ATR: same TR seed, but smoothed with
  **partial-window numpy slice means from bar 0** (no NaN warmup at all). The
  full-series 90th percentile consumed by Setup D depends on those partial
  values, so this convention must be preserved exactly.
* ``highest_high`` — trailing rolling max with ``min_periods=1`` (partial
  windows from bar 0), unlike the standard ``donchian`` NaN warmup.
* ``volume_ratio`` — current volume vs the trailing mean of the **previous**
  ``lookback`` volumes (``shift(1)``), ``min_periods=1``, hard ``1.0`` where the
  average is not positive.
* ``rvol_prev_mean`` — current bar volume vs the mean of **all** previous bars
  in the window (the enricher's expanding 500-bar deque), NaN until
  ``min_bars`` bars exist or when the previous mean is not positive.
* ``volume_velocity`` — first difference of volume (``value``) and the
  difference of consecutive first differences (``acceleration``), NaN warmup.
  The parenthesization ``(v[i]-v[i-1]) - (v[i-1]-v[i-2])`` is kept (not the
  algebraically equal ``v[i]-2*v[i-1]+v[i-2]`` of the standard numpy backend)
  so float results stay bit-identical for non-integer volumes.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from shared.indicators.engine.base import (
    IndicatorBackend,
    IndicatorComputationError,
    IndicatorResult,
    UnsupportedIndicatorError,
    last_finite,
)
from shared.indicators.engine.params import int_param as _int
from shared.indicators.engine.spec import IndicatorSpec, OHLCVWindow


def _sma(w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    """Trailing pandas rolling mean of close with explicit ``min_periods``."""
    period = _int(p, "period", 20)
    min_periods = _int(p, "min_periods", period)
    value = pd.Series(w.close).rolling(window=period, min_periods=min_periods).mean()
    return {"value": value.to_numpy()}


def _rsi(w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    """Daily-backtest Wilder-EMA RSI (verbatim ``_compute_rsi``): NaN on
    zero-loss windows, bar-0 gain/loss filled to 0.0 (not NaN)."""
    period = _int(p, "period", 14)
    series = pd.Series(w.close)
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return {"value": rsi.to_numpy()}


def _atr(w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    """SMA-of-TR ATR, bar-0 TR = high-low, ``min_periods=period`` warmup
    (verbatim daily-adapter block)."""
    period = _int(p, "period", 22)
    high = pd.Series(w.high)
    low = pd.Series(w.low)
    prev_close = pd.Series(w.close).shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    value = tr.rolling(window=period, min_periods=period).mean()
    return {"value": value.to_numpy()}


def _atr_partial(w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    """Replay ATR (verbatim ``market_context_replay._compute_atr``): TR seed
    ``high-low`` at bar 0, partial-window numpy slice means from bar 0."""
    period = _int(p, "period", 14)
    highs, lows, closes = w.high, w.low, w.close
    n = len(closes)
    tr = np.empty(n)
    tr[0] = highs[0] - lows[0]
    for i in range(1, n):
        tr[i] = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
    atr = np.empty(n)
    for i in range(n):
        start = max(0, i - period + 1)
        atr[i] = tr[start : i + 1].mean()
    return {"value": atr}


def _highest_high(w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    """Trailing rolling max of high with ``min_periods=1`` (partial warmup)."""
    period = _int(p, "period", 22)
    value = pd.Series(w.high).rolling(window=period, min_periods=1).max()
    return {"value": value.to_numpy()}


def _volume_ratio(w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    """Volume vs trailing mean of the previous ``lookback`` volumes
    (``shift(1)``, ``min_periods=1``); hard 1.0 where the average is not > 0."""
    lookback = max(1, _int(p, "lookback", 20))
    volume = pd.Series(w.volume)
    volume_avg = volume.shift(1).rolling(window=lookback, min_periods=1).mean()
    value = np.where(volume_avg > 0, volume / volume_avg, 1.0)
    return {"value": value}


def _rvol_prev_mean(w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    """Bar volume vs mean of ALL previous window volumes (expanding), NaN until
    ``min_bars`` total bars exist or when the previous mean is not positive.

    ``np.cumsum`` accumulates sequentially left-to-right, exactly like the
    enricher's ``sum(bar_vols[:-1])``, so the previous-mean is bit-identical.
    """
    min_bars = max(1, _int(p, "min_bars", 20))
    vol = w.volume
    n = vol.shape[0]
    out = np.full(n, np.nan, dtype=np.float64)
    if n >= 2:
        prefix = np.cumsum(vol)
        prev_counts = np.arange(1, n, dtype=np.float64)
        prev_mean = prefix[:-1] / prev_counts
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = vol[1:] / prev_mean
        valid = (np.arange(2, n + 1) >= min_bars) & (prev_mean > 0)
        out[1:][valid] = ratio[valid]
    return {"value": out}


def _volume_velocity(w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    """First difference of volume (``value``) and difference of consecutive
    first differences (``acceleration``); NaN warmup (<2 / <3 bars)."""
    vol = w.volume
    n = vol.shape[0]
    velocity = np.full(n, np.nan, dtype=np.float64)
    accel = np.full(n, np.nan, dtype=np.float64)
    if n >= 2:
        velocity[1:] = vol[1:] - vol[:-1]
    if n >= 3:
        accel[2:] = velocity[2:] - velocity[1:-1]
    return {"value": velocity, "acceleration": accel}


_TABLE = {
    "sma": _sma,
    "rsi": _rsi,
    "atr": _atr,
    "atr_partial": _atr_partial,
    "highest_high": _highest_high,
    "volume_ratio": _volume_ratio,
    "rvol_prev_mean": _rvol_prev_mean,
    "volume_velocity": _volume_velocity,
}


class BacktestCompatBackend(IndicatorBackend):
    """Exact ``shared/backtest`` adapter conventions behind the engine API."""

    @property
    def name(self) -> str:
        return "backtest_compat"

    def supported_ids(self) -> frozenset[str]:
        return frozenset(_TABLE)

    def compute(self, spec: IndicatorSpec, window: OHLCVWindow) -> IndicatorResult:
        fn = _TABLE.get(spec.indicator_id)
        if fn is None:
            raise UnsupportedIndicatorError(
                f"BacktestCompatBackend cannot compute '{spec.indicator_id}'"
            )
        if len(window) == 0:
            raise IndicatorComputationError(f"empty OHLCV window for {spec.key}")
        try:
            series = fn(window, spec.param_map)
        except Exception as exc:  # noqa: BLE001 - re-wrapped with context
            raise IndicatorComputationError(
                f"Backtest-compat indicator failed for {spec.key}: {exc}"
            ) from exc
        latest = {output: last_finite(arr) for output, arr in series.items()}
        return IndicatorResult(spec=spec, series=series, latest=latest)
