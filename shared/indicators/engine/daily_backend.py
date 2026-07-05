"""Daily-convention indicator backend (value-preserving retirement of daily.py).

``shared/indicators/daily.py::calculate_daily_indicators`` computes daily SMA /
EMA / RSI with pandas (``rolling(min_periods=period)``, ``ewm(adjust=False)``, an
ewm-seeded RSI with explicit zero-gain/zero-loss handling). To retire that math
into the engine *without changing any value*, this backend reproduces the exact
pandas operations behind the ``IndicatorBackend`` interface — using pandas
internally so the ewm/rolling semantics are bit-identical (numpy re-derivation of
pandas ewm NaN handling is error-prone). ``calculate_daily_indicators`` becomes a
thin orchestrator (keeping its look-ahead guard + validation) that delegates each
period to :func:`daily_indicator_engine`.

Distinct from the runtime intraday conventions in
:mod:`shared.indicators.engine.streaming_backend` (first-delta RSI, etc.) — daily
uses its own seeding, so it is its own backend/engine.
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


def _sma(close: pd.Series, period: int) -> float:
    """Full-window SMA (``min_periods=period``): NaN when under-warmed."""
    return float(close.rolling(window=period, min_periods=period).mean().iloc[-1])


def _ema(close: pd.Series, period: int) -> float:
    """EMA with ``adjust=False`` (matches ``calculate_daily_indicators``)."""
    return float(close.ewm(span=period, adjust=False).mean().iloc[-1])


def _rsi(close: pd.Series, period: int) -> float:
    """Daily RSI: ewm(alpha=1/period, min_periods=period, adjust=False) of
    gains/losses with the exact zero-gain/zero-loss handling of daily.py."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    zero_loss = avg_loss.iloc[-1] == 0
    zero_gain = avg_gain.iloc[-1] == 0
    if zero_loss and zero_gain:
        return 50.0
    if zero_loss and not zero_gain:
        return 100.0
    if zero_gain and not zero_loss:
        return 0.0
    rs = avg_gain.iloc[-1] / avg_loss.iloc[-1]
    return float(100 - (100 / (1 + rs)))


class DailyCompatBackend(IndicatorBackend):
    """Daily SMA / EMA / RSI (the exact ``calculate_daily_indicators`` math)."""

    @property
    def name(self) -> str:
        return "daily_compat"

    def supported_ids(self) -> frozenset[str]:
        return frozenset({"sma", "ema", "rsi"})

    def compute(self, spec: IndicatorSpec, window: OHLCVWindow) -> IndicatorResult:
        if len(window) == 0:
            raise IndicatorComputationError(f"empty OHLCV window for {spec.key}")
        p: Mapping[str, float] = spec.param_map
        close = pd.Series(np.asarray(window.close, dtype=float))
        iid = spec.indicator_id
        if iid == "sma":
            value = _sma(close, _int(p, "period", 20))
        elif iid == "ema":
            value = _ema(close, _int(p, "period", 20))
        elif iid == "rsi":
            value = _rsi(close, _int(p, "period", 14))
        else:
            raise UnsupportedIndicatorError(
                f"DailyCompatBackend cannot compute '{iid}'"
            )
        series = {"value": np.array([value])}
        return IndicatorResult(
            spec=spec, series=series, latest={"value": last_finite(series["value"])}
        )
