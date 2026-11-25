"""Momentum-convention indicator backend (value-preserving retirement of momentum.py).

``shared/indicators/momentum.py`` computes TRIX / CCI / MACD / (slow) Stochastic /
Williams %R / OBV / RSI with bespoke pandas conventions (``adjust=False`` EMAs,
``min_periods=1`` rolling windows, a vectorized MAD for CCI, ewm-seeded RSI with
explicit zero-gain/zero-loss handling, HTS-compatible column names like ``sto_k`` /
``macd_line``). This backend hosts those exact algorithms behind the engine
interface — returning the **full series** per output (not just the latest), since
consumers use the whole column (``DivergenceDetector``, strategy df access).

Uses pandas internally so the ewm/rolling/NaN semantics are bit-identical. Distinct
from the streaming / daily / TA-Lib engines (its own conventions + column names), so
it lives behind :func:`momentum_indicator_engine`. The ``momentum.py`` calculator
classes become thin delegates; ``calculate_all_momentum`` + ``DivergenceDetector``
are unchanged. Pinned by ``test_momentum_backend_golden.py``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from shared.indicators.engine.base import (
    IndicatorBackend,
    IndicatorComputationError,
    IndicatorResult,
    UnsupportedIndicatorError,
    last_finite,
)
from shared.indicators.engine.params import float_param as _float
from shared.indicators.engine.params import int_param as _int
from shared.indicators.engine.spec import IndicatorSpec, OHLCVWindow


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _rolling_mad(values: np.ndarray, period: int) -> np.ndarray:
    """Rolling mean-absolute-deviation (pandas min_periods=1), verbatim from CCI."""
    n = values.shape[0]
    out = np.empty(n, dtype=float)
    ramp = min(period - 1, n)
    for i in range(ramp):
        w = values[: i + 1]
        out[i] = np.abs(w - w.mean()).mean()
    if n >= period:
        windows = sliding_window_view(values, period)
        out[period - 1 :] = np.abs(windows - windows.mean(axis=1, keepdims=True)).mean(
            axis=1
        )
    return out


def _trix(df: pd.DataFrame, n: int, signal: int) -> dict[str, np.ndarray]:
    close = df["close"]
    ema1 = _ema(close, n)
    ema2 = _ema(ema1, n)
    ema3 = _ema(ema2, n)
    ema3_arr = ema3.to_numpy()
    ema3_prev = ema3.shift(1).to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        trix = np.where(ema3_prev != 0, (ema3_arr - ema3_prev) / ema3_prev * 100.0, 0.0)
    trix_signal = _ema(pd.Series(trix, index=df.index), signal).to_numpy()
    return {"trix": trix, "trix_signal": trix_signal}


def _cci(df: pd.DataFrame, period: int, constant: float) -> dict[str, np.ndarray]:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    tp_sma = tp.rolling(window=period, min_periods=1).mean()
    mean_dev = pd.Series(_rolling_mad(tp.to_numpy(dtype=float), period), index=tp.index)
    denominator = constant * mean_dev
    cci = np.where(denominator != 0, (tp - tp_sma) / denominator, 0.0)
    return {"cci": cci}


def _macd(df: pd.DataFrame, fast: int, slow: int, signal: int) -> dict[str, np.ndarray]:
    close = df["close"]
    macd_line = _ema(close, fast) - _ema(close, slow)
    macd_signal = _ema(macd_line, signal)
    macd_oscillator = macd_line - macd_signal
    return {
        "macd_line": macd_line.to_numpy(),
        "macd_signal": macd_signal.to_numpy(),
        "macd_oscillator": macd_oscillator.to_numpy(),
    }


def _stochastic(
    df: pd.DataFrame, fastk: int, slowk: int, slowd: int
) -> dict[str, np.ndarray]:
    lowest_low = df["low"].rolling(window=fastk, min_periods=1).min().to_numpy()
    highest_high = df["high"].rolling(window=fastk, min_periods=1).max().to_numpy()
    close = df["close"].to_numpy()
    denominator = highest_high - lowest_low
    with np.errstate(divide="ignore", invalid="ignore"):
        raw_k = np.where(
            denominator != 0, (close - lowest_low) / denominator * 100.0, 50.0
        )
    raw_k_series = pd.Series(raw_k, index=df.index)
    sto_k = raw_k_series.rolling(window=slowk, min_periods=1).mean()
    sto_d = sto_k.rolling(window=slowd, min_periods=1).mean()
    return {"sto_k": sto_k.to_numpy(), "sto_d": sto_d.to_numpy()}


def _williams_r(df: pd.DataFrame, period: int) -> dict[str, np.ndarray]:
    highest_high = df["high"].rolling(window=period, min_periods=1).max().to_numpy()
    lowest_low = df["low"].rolling(window=period, min_periods=1).min().to_numpy()
    close = df["close"].to_numpy()
    denominator = highest_high - lowest_low
    with np.errstate(divide="ignore", invalid="ignore"):
        wr = np.where(
            denominator != 0,
            ((highest_high - close) / denominator) * -100.0,
            -50.0,
        )
    return {"williams_r": wr}


def _obv(df: pd.DataFrame) -> dict[str, np.ndarray]:
    direction = np.sign(df["close"].diff().fillna(0))
    return {"obv": (direction * df["volume"]).cumsum().to_numpy()}


def _rsi(df: pd.DataFrame, period: int) -> dict[str, np.ndarray]:
    delta = df["close"].diff().to_numpy()
    gain = np.maximum(delta, 0.0)
    loss = np.maximum(-delta, 0.0)
    alpha = 1.0 / period
    avg_gain = (
        pd.Series(gain, index=df.index)
        .ewm(alpha=alpha, min_periods=period, adjust=False)
        .mean()
        .to_numpy()
    )
    avg_loss = (
        pd.Series(loss, index=df.index)
        .ewm(alpha=alpha, min_periods=period, adjust=False)
        .mean()
        .to_numpy()
    )
    zero_loss = avg_loss == 0.0
    zero_gain = avg_gain == 0.0
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / np.where(zero_loss, np.nan, avg_loss)
        rsi = 100.0 - 100.0 / (1.0 + rs)
    rsi = np.where(zero_loss & zero_gain, 50.0, rsi)
    rsi = np.where(zero_loss & ~zero_gain, 100.0, rsi)
    rsi = np.where(zero_gain & ~zero_loss, 0.0, rsi)
    rsi = np.where(np.isnan(rsi), 50.0, rsi)
    return {"rsi": rsi}


def _df_from_window(window: OHLCVWindow) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": np.asarray(window.open, dtype=float),
            "high": np.asarray(window.high, dtype=float),
            "low": np.asarray(window.low, dtype=float),
            "close": np.asarray(window.close, dtype=float),
            "volume": np.asarray(window.volume, dtype=float),
        }
    )


class MomentumCompatBackend(IndicatorBackend):
    """TRIX / CCI / MACD / slow-Stochastic / Williams %R / OBV / RSI, the exact
    ``shared.indicators.momentum`` math (full-series output)."""

    @property
    def name(self) -> str:
        return "momentum_compat"

    def supported_ids(self) -> frozenset[str]:
        return frozenset(
            {"trix", "cci", "macd", "stochastic", "williams_r", "obv", "rsi"}
        )

    def compute(self, spec: IndicatorSpec, window: OHLCVWindow) -> IndicatorResult:
        if len(window) == 0:
            raise IndicatorComputationError(f"empty OHLCV window for {spec.key}")
        p = spec.param_map
        df = _df_from_window(window)
        iid = spec.indicator_id
        if iid == "trix":
            series = _trix(df, _int(p, "n", 12), _int(p, "signal", 9))
        elif iid == "cci":
            series = _cci(df, _int(p, "period", 9), _float(p, "constant", 0.015))
        elif iid == "macd":
            series = _macd(
                df, _int(p, "fast", 12), _int(p, "slow", 26), _int(p, "signal", 9)
            )
        elif iid == "stochastic":
            series = _stochastic(
                df,
                _int(p, "fastk_period", 12),
                _int(p, "slowk_period", 5),
                _int(p, "slowd_period", 5),
            )
        elif iid == "williams_r":
            series = _williams_r(df, _int(p, "period", 14))
        elif iid == "obv":
            series = _obv(df)
        elif iid == "rsi":
            series = _rsi(df, _int(p, "period", 14))
        else:
            raise UnsupportedIndicatorError(
                f"MomentumCompatBackend cannot compute '{iid}'"
            )
        latest = {out: last_finite(arr) for out, arr in series.items()}
        return IndicatorResult(spec=spec, series=series, latest=latest)
