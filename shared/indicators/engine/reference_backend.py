"""Reference-convention indicator backend (single SoT home of the reference math).

Purpose
-------
This module is the P1-a absorption of ``shared/indicators/reference.py`` into
the engine (``docs/plans/2026-07-08-new-architecture-refactoring-plan.md`` §3):
the standard-accurate reference calculators created during the M2 indicator
consolidation now live here — exposed through the same
:class:`~shared.indicators.engine.base.IndicatorBackend` interface as the
TA-Lib / streaming / momentum / daily backends — instead of forming a second
hand-rolled calculation SoT next to the engine. ``shared.indicators.reference``
remains the public import path as a thin re-export shim, so every existing
consumer keeps working with byte-identical values.

The calculators provide canonically-correct, single-source implementations of
indicators that the M1 parity harness (``tests/unit/indicators/test_calc_parity``)
found to be either non-standard or outright defective across the runtime and
regime paths:

    * ``ADXCalculator``            -- textbook Wilder-smoothed ADX. The runtime
      ``services/trading/indicator_calculations._calc_adx`` is already correct
      Wilder ADX; ``shared/regime/adaptive_detector._calc_adx`` is NOT -- it
      returns a single, SMA-smoothed DX (no directional-movement rule, no final
      DX smoothing). This class is the correct implementation the detector should
      delegate to.
    * ``StochRSICalculator``       -- Stochastic RSI computed on a Wilder RSI
      series. There is currently NO producer of ``stochrsi_k``/``stochrsi_d`` in
      the codebase even though ``StochRSITrendEntry`` consumes them, so that
      strategy is inert (always reads the neutral 50 default). This class is the
      missing producer.

Design constraints
------------------
* Pure ``numpy``/``pandas`` -- no new third-party dependency (no TA-Lib, no
  pandas-ta). Deterministic and version-stable.
* Causal by construction -- every value at bar ``i`` depends only on bars
  ``<= i`` (rolling / Wilder recursion). Each ``calculate`` accepts the optional
  ``LookaheadGuard`` hooks (mirroring ``momentum.TRIXCalculator``) so callers in
  backtest mode can assert no future data leaked in via the input frame.
* Value-preserving -- the calculator classes are the *only* home of this math;
  :class:`ReferenceBackend` wraps them for engine consumers, and the
  ``shared.indicators.reference`` shim re-exports them for direct consumers
  (``shared/indicators/volume_ratio.py``, ``shared/regime/adaptive_detector.py``,
  ``shared/strategy/entry/trix_golden.py``, ``shared/llm/stock_screening.py``,
  runtime ATR/StochRSI paths). Numeric contracts are pinned by
  ``tests/unit/indicators/test_reference_contract.py``.

Standards references
--------------------
* Wilder, J. Welles. *New Concepts in Technical Trading Systems* (1978) --
  origin of RSI, ADX/DMI, and Wilder smoothing (RMA, alpha = 1/period).
* Bollinger, John. *Bollinger on Bollinger Bands* (2001).
* Chande & Kroll. *The New Technical Trader* (1994) -- Stochastic RSI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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

# ---------------------------------------------------------------------------
# Wilder smoothing (RMA) -- shared primitive for RSI / ADX
# ---------------------------------------------------------------------------


def wilder_rma(values: np.ndarray, period: int) -> np.ndarray:
    """Wilder's running moving average (a.k.a. RMA / Wilder smoothing).

    Seeds the first output at index ``period-1`` with the simple mean of the
    first ``period`` samples, then applies the Wilder recursion::

        rma[i] = (rma[i-1] * (period - 1) + values[i]) / period

    Indices ``< period-1`` are ``NaN`` (warmup). This is the average-based form
    of Wilder smoothing; because +DI/-DI are ratios of two RMAs the sum-based
    original form (Wilder 1978) yields identical DI values.

    This matches the smoothing used by the (correct) runtime ADX in
    ``services/trading/indicator_calculations._calc_adx``.

    Args:
        values: 1-D float array.
        period: Wilder period (> 0).

    Returns:
        Array of the same length as ``values`` with ``NaN`` warmup.
    """
    n = values.shape[0]
    out = np.full(n, np.nan, dtype=float)
    if period <= 0 or n < period:
        return out
    seed = float(np.mean(values[:period]))
    out[period - 1] = seed
    prev = seed
    inv = 1.0 / period
    pm1 = period - 1
    for i in range(period, n):
        prev = (prev * pm1 + values[i]) * inv
        out[i] = prev
    return out


def wilder_rsi(close: pd.Series | np.ndarray, period: int = 14) -> pd.Series:
    """Wilder RSI series with ``NaN`` warmup (no neutral fill).

    Same smoothing convention as ``shared.indicators.momentum.RSICalculator``
    (Wilder EMA, ``alpha = 1/period``), but intentionally preserves ``NaN``
    during warmup instead of filling 50. That neutral fill is a strategy-path
    convenience; for Stochastic RSI it would distort the rolling min/max
    normalization, so the reference keeps the raw series.

    Args:
        close: Close-price series.
        period: RSI lookback (default 14).

    Returns:
        RSI ``pd.Series`` in ``[0, 100]`` (``NaN`` during warmup).
    """
    close_s = pd.Series(np.asarray(close, dtype=float))
    delta = close_s.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    alpha = 1.0 / period
    avg_gain = gain.ewm(alpha=alpha, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=alpha, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - 100.0 / (1.0 + rs)
    # avg_loss == 0 with avg_gain > 0 -> all gains -> RSI 100
    rsi = rsi.where(~((avg_loss == 0.0) & (avg_gain > 0.0)), 100.0)
    # avg_gain == 0 with avg_loss > 0 -> all losses -> RSI 0
    rsi = rsi.where(~((avg_gain == 0.0) & (avg_loss > 0.0)), 0.0)
    # flat (both zero) -> neutral 50
    rsi = rsi.where(~((avg_gain == 0.0) & (avg_loss == 0.0)), 50.0)
    return rsi


# ---------------------------------------------------------------------------
# ADX (Average Directional Index) -- canonical Wilder implementation
# ---------------------------------------------------------------------------


@dataclass
class ADXConfig:
    """ADX configuration.

    Attributes:
        period: Wilder period for DMI / DX smoothing (default 14).
    """

    period: int = 14


class ADXCalculator:
    """Average Directional Index (ADX) -- textbook Wilder implementation.

    Convention (Wilder 1978 / standard DMI):
        1. TR   = max(H-L, |H-Cp|, |L-Cp|)
        2. +DM  = up_move   if (up_move > down_move and up_move > 0)   else 0
           -DM  = down_move if (down_move > up_move and down_move > 0) else 0
           where up_move = H-Hp, down_move = Lp-L
        3. Wilder-smooth TR, +DM, -DM (``wilder_rma``)
        4. +DI = 100 * smoothed(+DM) / smoothed(TR)
           -DI = 100 * smoothed(-DM) / smoothed(TR)
        5. DX  = 100 * |+DI - -DI| / (+DI + -DI)
        6. ADX = Wilder-smooth(DX)         <-- the step the regime detector omits

    Contrast with ``shared/regime/adaptive_detector._calc_adx``, which:
        * uses ``np.maximum(H-Hp, 0)`` / ``np.maximum(Lp-L, 0)`` -- it never
          zeroes the smaller move, so +DM and -DM can both be non-zero (the
          directional-movement rule is missing);
        * smooths DI with a *simple* rolling mean, not Wilder smoothing;
        * returns a single ``dx`` from the last bar with NO step-6 smoothing.
    That function is named ADX but is really an SMA-DI single-bar DX.
    """

    def __init__(self, period: int = 14):
        self.config = ADXConfig(period=period)

    def _dmi_frame(
        self, high: np.ndarray, low: np.ndarray, close: np.ndarray
    ) -> dict[str, np.ndarray]:
        """Compute full-length +DI / -DI / DX / ADX arrays (``NaN`` warmup)."""
        period = self.config.period
        n = high.shape[0]
        plus_di = np.full(n, np.nan, dtype=float)
        minus_di = np.full(n, np.nan, dtype=float)
        dx = np.full(n, np.nan, dtype=float)
        adx = np.full(n, np.nan, dtype=float)
        if n < 2:
            return {
                "plus_di": plus_di,
                "minus_di": minus_di,
                "dx": dx,
                "adx": adx,
            }

        up_move = high[1:] - high[:-1]
        down_move = low[:-1] - low[1:]
        plus_dm = np.where((up_move > down_move) & (up_move > 0.0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0.0), down_move, 0.0)

        tr1 = high[1:] - low[1:]
        tr2 = np.abs(high[1:] - close[:-1])
        tr3 = np.abs(low[1:] - close[:-1])
        tr = np.maximum(tr1, np.maximum(tr2, tr3))

        atr_s = wilder_rma(tr, period)
        pdm_s = wilder_rma(plus_dm, period)
        mdm_s = wilder_rma(minus_dm, period)

        # Preserve NaN warmup (where wilder_rma has not yet seeded); a zero ATR
        # inside the valid region means "no range" -> DI/DX = 0.
        valid = ~np.isnan(atr_s)
        positive = valid & (atr_s > 0.0)
        pdi = np.full_like(atr_s, np.nan)
        mdi = np.full_like(atr_s, np.nan)
        pdi[valid] = 0.0
        mdi[valid] = 0.0
        with np.errstate(divide="ignore", invalid="ignore"):
            pdi[positive] = 100.0 * pdm_s[positive] / atr_s[positive]
            mdi[positive] = 100.0 * mdm_s[positive] / atr_s[positive]
        di_sum = pdi + mdi
        dx_arr = np.full_like(atr_s, np.nan)
        dx_positive = valid & (di_sum > 0.0)
        dx_arr[valid] = 0.0
        with np.errstate(divide="ignore", invalid="ignore"):
            dx_arr[dx_positive] = (
                100.0
                * np.abs(pdi[dx_positive] - mdi[dx_positive])
                / di_sum[dx_positive]
            )

        # dx_arr / pdi / mdi are aligned to bars 1..n-1; NaN warmup carried from
        # wilder_rma. Re-Wilder-smooth DX (over its own valid tail) -> ADX.
        adx_tail = self._smooth_dx(dx_arr)

        # Map the (n-1)-length diff arrays back onto the n-length bar index.
        plus_di[1:] = pdi
        minus_di[1:] = mdi
        dx[1:] = dx_arr
        adx[1:] = adx_tail
        return {"plus_di": plus_di, "minus_di": minus_di, "dx": dx, "adx": adx}

    def _smooth_dx(self, dx_arr: np.ndarray) -> np.ndarray:
        """Wilder-smooth the DX series over its non-NaN tail -> ADX series."""
        period = self.config.period
        out = np.full(dx_arr.shape[0], np.nan, dtype=float)
        valid = np.flatnonzero(~np.isnan(dx_arr))
        if valid.size < period:
            return out
        start = valid[0]
        tail = dx_arr[start:]
        smoothed = wilder_rma(tail, period)
        out[start:] = smoothed
        return out

    def calculate(
        self,
        df: pd.DataFrame,
        *,
        lookahead_guard: Any = None,
        context_timestamp: Any = None,
        context_info: str | None = None,
    ) -> pd.DataFrame:
        """Add ``plus_di``, ``minus_di``, ``dx``, ``adx`` columns to ``df``.

        Args:
            df: DataFrame with ``high``, ``low``, ``close`` columns.
            lookahead_guard: Optional ``LookaheadGuard`` for backtest assertions.
            context_timestamp: Reference timestamp for the guard.
            context_info: Optional context label for guard messages.

        Returns:
            The same DataFrame with ADX/DMI columns added.
        """
        if lookahead_guard is not None and context_timestamp is not None:
            timestamps = df["timestamp"].tolist() if "timestamp" in df.columns else None
            lookahead_guard.check(
                df["close"].tolist(),
                timestamps,
                context_timestamp,
                context_info or "reference:adx_close",
            )

        high = df["high"].to_numpy(dtype=float)
        low = df["low"].to_numpy(dtype=float)
        close = df["close"].to_numpy(dtype=float)
        cols = self._dmi_frame(high, low, close)
        df["plus_di"] = cols["plus_di"]
        df["minus_di"] = cols["minus_di"]
        df["dx"] = cols["dx"]
        df["adx"] = cols["adx"]
        return df

    def calculate_last(
        self,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
    ) -> float | None:
        """Return the final (latest-bar) ADX value, or ``None`` if insufficient.

        Convenience for scalar callers (e.g. the regime detector delegation
        target). Mirrors the runtime ``_calc_adx`` return contract.

        Args:
            high: High-price array.
            low: Low-price array.
            close: Close-price array.

        Returns:
            Final ADX float, or ``None`` when there is not enough data.
        """
        high = np.asarray(high, dtype=float)
        low = np.asarray(low, dtype=float)
        close = np.asarray(close, dtype=float)
        if high.shape[0] < self.config.period + 1:
            return None
        adx = self._dmi_frame(high, low, close)["adx"]
        valid = adx[~np.isnan(adx)]
        if valid.size == 0:
            return None
        return float(valid[-1])


# ---------------------------------------------------------------------------
# Stochastic RSI -- the missing producer of stochrsi_k / stochrsi_d
# ---------------------------------------------------------------------------


@dataclass
class StochRSIConfig:
    """Stochastic RSI configuration.

    Attributes:
        rsi_period: Wilder RSI lookback (default 14).
        stoch_period: Rolling window for RSI min/max normalization (default 14).
        k_period: SMA smoothing for %K (default 3).
        d_period: SMA smoothing for %D (default 3).
    """

    rsi_period: int = 14
    stoch_period: int = 14
    k_period: int = 3
    d_period: int = 3


class StochRSICalculator:
    """Stochastic RSI (Chande & Kroll) on a Wilder RSI series.

    Formula:
        rsi         = wilder_rsi(close, rsi_period)               # [0, 100]
        stochrsi    = 100 * (rsi - min(rsi, stoch_period))
                          / (max(rsi, stoch_period) - min(rsi, stoch_period))
        %K          = SMA(stochrsi, k_period)                     # [0, 100]
        %D          = SMA(%K, d_period)                           # [0, 100]

    When the RSI window is flat (max == min) the raw StochRSI is set to 50
    (neutral) to avoid division by zero.

    This is the producer that ``shared/strategy/entry/stochrsi_trend.py``
    requires. That strategy reads flat keys ``stochrsi_k``, ``stochrsi_d`` and
    ``stochrsi_k_prev`` (the previous bar's %K, needed for crossover detection);
    ``latest_values`` emits exactly those three keys.

    RSI convention: the same Wilder smoothing as
    ``shared.indicators.momentum.RSICalculator``, via the module-level
    ``wilder_rsi`` helper (kept ``NaN`` during warmup so the min/max
    normalization is not distorted by a neutral fill).
    """

    def __init__(
        self,
        rsi_period: int = 14,
        stoch_period: int = 14,
        k_period: int = 3,
        d_period: int = 3,
    ):
        self.config = StochRSIConfig(
            rsi_period=rsi_period,
            stoch_period=stoch_period,
            k_period=k_period,
            d_period=d_period,
        )

    def calculate(
        self,
        df: pd.DataFrame,
        *,
        lookahead_guard: Any = None,
        context_timestamp: Any = None,
        context_info: str | None = None,
    ) -> pd.DataFrame:
        """Add ``stochrsi``, ``stochrsi_k``, ``stochrsi_d`` columns to ``df``.

        Args:
            df: DataFrame with a ``close`` column.
            lookahead_guard: Optional ``LookaheadGuard`` for backtest assertions.
            context_timestamp: Reference timestamp for the guard.
            context_info: Optional context label for guard messages.

        Returns:
            The same DataFrame with StochRSI columns added.
        """
        close = df["close"]
        if lookahead_guard is not None and context_timestamp is not None:
            timestamps = df["timestamp"].tolist() if "timestamp" in df.columns else None
            lookahead_guard.check(
                close.tolist(),
                timestamps,
                context_timestamp,
                context_info or "reference:stochrsi_close",
            )

        rsi = wilder_rsi(close, self.config.rsi_period)
        rsi.index = df.index

        sp = self.config.stoch_period
        rsi_min = rsi.rolling(window=sp, min_periods=sp).min()
        rsi_max = rsi.rolling(window=sp, min_periods=sp).max()
        rng = rsi_max - rsi_min

        with np.errstate(divide="ignore", invalid="ignore"):
            raw = np.where(rng != 0.0, 100.0 * (rsi - rsi_min) / rng, 50.0)
        # Preserve warmup NaN (where rsi_min/rsi_max are NaN), keep flat->50.
        raw = np.where(np.isnan(rsi_min.to_numpy()), np.nan, raw)
        stochrsi = pd.Series(raw, index=df.index)

        k = stochrsi.rolling(window=self.config.k_period, min_periods=1).mean()
        d = k.rolling(window=self.config.d_period, min_periods=1).mean()

        df["stochrsi"] = stochrsi
        df["stochrsi_k"] = k
        df["stochrsi_d"] = d
        return df

    def latest_values(self, df: pd.DataFrame) -> dict[str, float]:
        """Return the flat dict the strategy path consumes.

        Emits ``stochrsi_k``, ``stochrsi_d`` (latest bar) and ``stochrsi_k_prev``
        (previous bar's %K, for crossover detection). NaN warmup values fall
        back to the neutral 50 that the strategy already uses as its default, so
        the strategy behaves identically to today until enough bars exist.

        Args:
            df: DataFrame already processed by ``calculate`` (or a raw frame with
                a ``close`` column, in which case it is computed first).

        Returns:
            ``{"stochrsi_k": ..., "stochrsi_d": ..., "stochrsi_k_prev": ...}``.
        """
        if "stochrsi_k" not in df.columns:
            df = self.calculate(df)
        k_series = df["stochrsi_k"]
        d_series = df["stochrsi_d"]

        def _val(series: pd.Series, pos: int) -> float:
            if len(series) < abs(pos):
                return 50.0
            v = series.iloc[pos]
            return 50.0 if pd.isna(v) else float(v)

        return {
            "stochrsi_k": _val(k_series, -1),
            "stochrsi_d": _val(d_series, -1),
            "stochrsi_k_prev": _val(k_series, -2),
        }


# ---------------------------------------------------------------------------
# ATR (Average True Range) -- canonical TR + explicit smoothing-mode knob
# ---------------------------------------------------------------------------


@dataclass
class ATRConfig:
    """ATR configuration.

    Attributes:
        period: Smoothing window for True Range (default 14).
        mode: Smoothing family. ``"sma"`` (default) is a simple trailing mean of
            True Range -- the de-facto convention of every *standalone* ATR
            consumer in this repo (runtime ``_calc_atr_raw``/``_calc_atr_normalized``,
            ``regime._calc_atr``, ``technical._calc_atr``, the LLM/screening and
            ``trix_golden`` ``atr_pct`` helpers). ``"wilder"`` is Wilder's RMA of
            True Range -- the ATR the reference :class:`ADXCalculator` smooths
            internally; on real intraday data it runs materially higher than the
            SMA form, so switching a consumer to it MOVES that consumer's
            ATR-scaled stops/filters and requires a backtest gate.
    """

    period: int = 14
    mode: str = "sma"


class ATRCalculator:
    """Average True Range with an explicit smoothing-mode knob.

    True Range (Wilder 1978) is ``max(H-L, |H-Cp|, |L-Cp|)`` and is computed
    causally: TR at bar ``i`` uses only bars ``<= i`` (needs the prior close, so
    bar 0 has no TR). The array returned by :meth:`true_range` is length ``n-1``,
    aligned to bars ``1..n-1`` (the same alignment the reference
    :class:`ADXCalculator` uses internally), so ``mode="wilder"`` reproduces that
    ADX-internal ATR exactly.

    Motivation: the repo currently carries seven divergent ATR copies. All agree
    on the max-of-three True Range but split on smoothing (six use SMA, only the
    ADX-internal path uses Wilder -- ~24% apart on real data) and on
    normalization (some return raw ATR, some return ``atr/close`` under a
    misleading ``*_pct`` name). This calculator is the single canonical source
    they can delegate to; it mirrors Bollinger's explicit ``ddof`` knob by making
    the SMA-vs-Wilder choice explicit instead of an accident of which copy a
    caller happened to reach. It is additive -- nothing is rewired here; consumer
    migration is a separate, backtest-gated step.

    ATR is emitted raw; callers that want a price-relative figure call
    :meth:`atr_fraction_last`, which returns an explicit ``atr/close`` fraction
    (not a percent) so the ``*_pct``-named-but-returns-a-fraction trap in the
    current copies is not reproduced.
    """

    def __init__(self, period: int = 14, mode: str = "sma"):
        if mode not in ("sma", "wilder"):
            raise ValueError(f"ATR mode must be 'sma' or 'wilder', got {mode!r}")
        if period <= 0:
            raise ValueError(f"ATR period must be > 0, got {period}")
        self.config = ATRConfig(period=period, mode=mode)

    @staticmethod
    def true_range(
        high: np.ndarray | list[float],
        low: np.ndarray | list[float],
        close: np.ndarray | list[float],
    ) -> np.ndarray:
        """Return the True Range array aligned to bars ``1..n-1`` (length ``n-1``).

        Args:
            high: High-price series.
            low: Low-price series.
            close: Close-price series.

        Returns:
            ``max(H-L, |H-Cp|, |L-Cp|)`` for each bar from 1 onward; empty array
            when fewer than 2 bars are supplied.
        """
        h = np.asarray(high, dtype=float)
        low_a = np.asarray(low, dtype=float)
        c = np.asarray(close, dtype=float)
        if h.shape[0] < 2:
            return np.empty(0, dtype=float)
        tr1 = h[1:] - low_a[1:]
        tr2 = np.abs(h[1:] - c[:-1])
        tr3 = np.abs(low_a[1:] - c[:-1])
        tr: np.ndarray = np.maximum(tr1, np.maximum(tr2, tr3))
        return tr

    def _smooth(self, tr: np.ndarray) -> np.ndarray:
        """Smooth the True Range tail per ``mode`` (``NaN`` warmup preserved)."""
        period = self.config.period
        if self.config.mode == "wilder":
            return wilder_rma(tr, period)
        out = np.full(tr.shape[0], np.nan, dtype=float)
        if tr.shape[0] < period:
            return out
        # Trailing simple mean of TR: identical to sum(tr[-period:]) / period at
        # every position, matching the runtime ``_calc_atr_raw`` convention.
        cumsum = np.cumsum(np.insert(tr, 0, 0.0))
        out[period - 1 :] = (cumsum[period:] - cumsum[:-period]) / period
        return out

    def atr_series(
        self,
        high: np.ndarray | list[float],
        low: np.ndarray | list[float],
        close: np.ndarray | list[float],
    ) -> np.ndarray:
        """Return the full-length ATR series (length ``n``, ``NaN`` warmup + bar 0)."""
        h = np.asarray(high, dtype=float)
        out = np.full(h.shape[0], np.nan, dtype=float)
        tr = self.true_range(high, low, close)
        if tr.shape[0] == 0:
            return out
        out[1:] = self._smooth(tr)
        return out

    def atr_last(
        self,
        high: np.ndarray | list[float],
        low: np.ndarray | list[float],
        close: np.ndarray | list[float],
    ) -> float | None:
        """Return the latest ATR value, or ``None`` when there is not enough data."""
        series = self.atr_series(high, low, close)
        valid = series[~np.isnan(series)]
        if valid.size == 0:
            return None
        return float(valid[-1])

    def atr_fraction_last(
        self,
        high: np.ndarray | list[float],
        low: np.ndarray | list[float],
        close: np.ndarray | list[float],
    ) -> float | None:
        """Return ``atr_last / last_close`` (an explicit fraction), or ``None``."""
        atr = self.atr_last(high, low, close)
        if atr is None:
            return None
        last_close = float(np.asarray(close, dtype=float)[-1])
        if last_close == 0.0:
            return None
        return atr / last_close

    def calculate(
        self,
        df: pd.DataFrame,
        *,
        lookahead_guard: Any = None,
        context_timestamp: Any = None,
        context_info: str | None = None,
    ) -> pd.DataFrame:
        """Add an ``atr`` column to ``df`` (``NaN`` warmup).

        Args:
            df: DataFrame with ``high``, ``low``, ``close`` columns.
            lookahead_guard: Optional ``LookaheadGuard`` for backtest assertions.
            context_timestamp: Reference timestamp for the guard.
            context_info: Optional context label for guard messages.

        Returns:
            The same DataFrame with an ``atr`` column added.
        """
        if lookahead_guard is not None and context_timestamp is not None:
            timestamps = df["timestamp"].tolist() if "timestamp" in df.columns else None
            lookahead_guard.check(
                df["close"].tolist(),
                timestamps,
                context_timestamp,
                context_info or "reference:atr_close",
            )
        high = df["high"].to_numpy(dtype=float)
        low = df["low"].to_numpy(dtype=float)
        close = df["close"].to_numpy(dtype=float)
        df["atr"] = self.atr_series(high, low, close)
        return df


class MFICalculator:
    """Money Flow Index (regime convention: whole-series flows, sum last period).

    Canonical home for the previously hand-rolled ``AdaptiveRegimeDetector._calc_mfi``
    (its sibling ADX/ATR already delegate here). Convention preserved exactly:
    typical-price money flow, classified per consecutive-bar direction over the
    whole series, then the *last* ``period`` positive/negative flows are summed.
    Neutral ``50.0`` when fewer than ``period`` classified bars; ``100.0`` when the
    summed negative flow is zero (note: differs from the intraday streaming MFI,
    which returns 50 on a flat window — this is the regime detector's own contract).
    """

    def __init__(self, period: int = 14):
        if period <= 0:
            raise ValueError(f"MFI period must be > 0, got {period}")
        self.period = period

    @staticmethod
    def _classified_flows(
        high: np.ndarray | list[float] | Any,
        low: np.ndarray | list[float] | Any,
        close: np.ndarray | list[float] | Any,
        volume: np.ndarray | list[float] | Any,
    ) -> tuple[list[float], list[float]]:
        """Classify per-bar money flow by consecutive typical-price direction.

        Returns the (positive, negative) flow lists aligned to bars ``1..n-1``
        (bar 0 has no prior typical price). This is the single home of the
        regime-convention classification, shared by :meth:`mfi_last` and
        :meth:`mfi_series`.
        """
        h = np.asarray(high, dtype=float)
        low_a = np.asarray(low, dtype=float)
        c = np.asarray(close, dtype=float)
        v = np.asarray(volume, dtype=float)
        tp = (h + low_a + c) / 3.0
        mf = tp * v
        positive_flow: list[float] = []
        negative_flow: list[float] = []
        for i in range(1, tp.shape[0]):
            if tp[i] > tp[i - 1]:
                positive_flow.append(mf[i])
                negative_flow.append(0.0)
            elif tp[i] < tp[i - 1]:
                positive_flow.append(0.0)
                negative_flow.append(mf[i])
            else:
                positive_flow.append(0.0)
                negative_flow.append(0.0)
        return positive_flow, negative_flow

    @staticmethod
    def _mfi_value(positive_mf: float, negative_mf: float) -> float:
        """MFI from summed flows; ``100.0`` when the negative flow is zero."""
        if negative_mf == 0:
            return 100.0
        money_ratio = positive_mf / negative_mf
        return float(100 - (100 / (1 + money_ratio)))

    def mfi_last(
        self,
        high: np.ndarray | list[float] | Any,
        low: np.ndarray | list[float] | Any,
        close: np.ndarray | list[float] | Any,
        volume: np.ndarray | list[float] | Any,
    ) -> float:
        """Latest MFI scalar (regime convention)."""
        positive_flow, negative_flow = self._classified_flows(high, low, close, volume)
        if len(positive_flow) < self.period:
            return 50.0
        positive_mf = sum(positive_flow[-self.period :])
        negative_mf = sum(negative_flow[-self.period :])
        return self._mfi_value(positive_mf, negative_mf)

    def mfi_series(
        self,
        high: np.ndarray | list[float] | Any,
        low: np.ndarray | list[float] | Any,
        close: np.ndarray | list[float] | Any,
        volume: np.ndarray | list[float] | Any,
    ) -> np.ndarray:
        """Full-length MFI series (regime convention per bar, ``NaN`` warmup).

        The value at bar ``i`` equals :meth:`mfi_last` on the window ending at
        bar ``i`` (identical slice-and-sum arithmetic), except that bars with
        fewer than ``period`` classified flows are ``NaN`` warmup here where
        the scalar form maps them to the neutral ``50.0`` sentinel.

        Args:
            high: High-price series.
            low: Low-price series.
            close: Close-price series.
            volume: Volume series.

        Returns:
            Length-``n`` MFI array aligned to the input bars.
        """
        n = int(np.asarray(close, dtype=float).shape[0])
        out = np.full(n, np.nan, dtype=float)
        if n == 0:
            return out
        positive_flow, negative_flow = self._classified_flows(high, low, close, volume)
        for i in range(self.period, n):
            positive_mf = sum(positive_flow[i - self.period : i])
            negative_mf = sum(negative_flow[i - self.period : i])
            out[i] = self._mfi_value(positive_mf, negative_mf)
        return out


# ---------------------------------------------------------------------------
# Engine backend -- exposes the reference calculators behind IndicatorBackend
# ---------------------------------------------------------------------------


class ReferenceBackend(IndicatorBackend):
    """Reference-convention calculators behind the engine interface.

    Thin adapter over the calculator classes in this module — it owns no math
    of its own, so the reference convention has exactly one home. Registered
    via :func:`shared.indicators.engine.registry.reference_indicator_engine`
    and comparable against :class:`~shared.indicators.engine.talib_backend.
    TALibBackend` through the same :class:`~shared.indicators.engine.shadow.
    ShadowDelta` mechanism as the other compat backends.

    Indicator ids (reference conventions, ``NaN`` warmup preserved):

    * ``rsi``        -- Wilder RSI (:func:`wilder_rsi`); flat window -> 50.
    * ``adx``        -- canonical Wilder ADX (:class:`ADXCalculator`); also
      emits ``plus_di`` / ``minus_di`` / ``dx``.
    * ``stochrsi``   -- Stochastic RSI (:class:`StochRSICalculator`); emits
      raw ``value`` plus ``k`` / ``d``.
    * ``atr``        -- SMA-of-True-Range (:class:`ATRCalculator`
      ``mode="sma"``, the repo's standalone-consumer convention).
    * ``atr_wilder`` -- Wilder RMA of True Range (``mode="wilder"``; matches
      TA-Lib ATR). A distinct id because :class:`IndicatorSpec` params are
      numeric-only and the mode choice moves ATR-scaled thresholds.
    * ``mfi``        -- regime-convention MFI (:class:`MFICalculator`); flat
      window -> 100 (zero negative flow).
    """

    @property
    def name(self) -> str:
        return "reference"

    def supported_ids(self) -> frozenset[str]:
        return frozenset({"rsi", "adx", "stochrsi", "atr", "atr_wilder", "mfi"})

    def compute(self, spec: IndicatorSpec, window: OHLCVWindow) -> IndicatorResult:
        if len(window) == 0:
            raise IndicatorComputationError(f"empty OHLCV window for {spec.key}")
        params = spec.param_map
        iid = spec.indicator_id
        if iid == "rsi":
            rsi = wilder_rsi(window.close, period=_int(params, "period", 14))
            series: dict[str, np.ndarray] = {"value": rsi.to_numpy(dtype=float)}
        elif iid == "adx":
            frame = ADXCalculator(period=_int(params, "period", 14))._dmi_frame(
                window.high, window.low, window.close
            )
            series = {
                "value": frame["adx"],
                "plus_di": frame["plus_di"],
                "minus_di": frame["minus_di"],
                "dx": frame["dx"],
            }
        elif iid == "stochrsi":
            calc = StochRSICalculator(
                rsi_period=_int(params, "rsi_period", 14),
                stoch_period=_int(params, "stoch_period", 14),
                k_period=_int(params, "k_period", 3),
                d_period=_int(params, "d_period", 3),
            )
            df = calc.calculate(pd.DataFrame({"close": window.close}))
            series = {
                "value": df["stochrsi"].to_numpy(dtype=float),
                "k": df["stochrsi_k"].to_numpy(dtype=float),
                "d": df["stochrsi_d"].to_numpy(dtype=float),
            }
        elif iid in ("atr", "atr_wilder"):
            mode = "wilder" if iid == "atr_wilder" else "sma"
            atr = ATRCalculator(period=_int(params, "period", 14), mode=mode)
            series = {"value": atr.atr_series(window.high, window.low, window.close)}
        elif iid == "mfi":
            mfi = MFICalculator(period=_int(params, "period", 14))
            series = {
                "value": mfi.mfi_series(
                    window.high, window.low, window.close, window.volume
                )
            }
        else:
            raise UnsupportedIndicatorError(f"ReferenceBackend cannot compute '{iid}'")
        latest = {output: last_finite(arr) for output, arr in series.items()}
        return IndicatorResult(spec=spec, series=series, latest=latest)
