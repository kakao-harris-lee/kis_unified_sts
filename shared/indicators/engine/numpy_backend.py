"""NumPy implementation of :class:`IndicatorBackend` for non-TA-Lib indicators.

TA-Lib does not provide the platform's volume/microstructure indicators
(``vwap``, ``rvol``, ...). This backend covers them in plain NumPy so the engine
can still emit a complete flat panel, and — together with
:mod:`shared.indicators.engine.talib_backend` — demonstrates the whole point of
the backend abstraction: standard indicators route to TA-Lib, custom ones here,
composed behind one registry.

Pure NumPy (no TA-Lib, no Numba) so it is always available. Numba ``@njit``
acceleration for heavier custom indicators (CVD, volume profile, ichimoku)
layers on in WS-A5 without changing this interface.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from shared.indicators.engine.base import (
    IndicatorBackend,
    IndicatorComputationError,
    IndicatorResult,
    UnsupportedIndicatorError,
    last_finite,
)
from shared.indicators.engine.params import int_param as _int
from shared.indicators.engine.spec import IndicatorSpec, OHLCVWindow


def _rolling_mean(values: np.ndarray, window: int) -> np.ndarray:
    """Trailing rolling mean; NaN until ``window`` samples are available."""
    out = np.full(values.shape, np.nan, dtype=np.float64)
    if window <= 0 or values.shape[0] < window:
        return out
    cumsum = np.cumsum(np.insert(values, 0, 0.0))
    out[window - 1 :] = (cumsum[window:] - cumsum[:-window]) / window
    return out


def _vwap(w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    """Cumulative VWAP over the window (typical price weighted by volume)."""
    typical = (w.high + w.low + w.close) / 3.0
    cum_pv = np.cumsum(typical * w.volume)
    cum_v = np.cumsum(w.volume)
    value = np.divide(
        cum_pv,
        cum_v,
        out=np.full(cum_v.shape, np.nan, dtype=np.float64),
        where=cum_v > 0,
    )
    return {"value": value}


def _rvol(w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    """Relative volume = short-window mean volume / long-window mean volume."""
    short = _rolling_mean(w.volume, _int(p, "short_window", 5))
    long = _rolling_mean(w.volume, _int(p, "long_window", 20))
    value = np.divide(
        short, long, out=np.full(long.shape, np.nan, dtype=np.float64), where=long > 0
    )
    return {"value": value}


def _volume_acceleration(
    w: OHLCVWindow, p: Mapping[str, float]
) -> dict[str, np.ndarray]:
    """Second difference of volume (rate of change of volume velocity), bar-based.

    A bar-native proxy for the runtime's tick/second-based accelerator: NaN for
    the first two bars, then ``vol[i] - 2*vol[i-1] + vol[i-2]``.
    """
    vol = w.volume
    accel = np.full(vol.shape, np.nan, dtype=np.float64)
    if vol.shape[0] >= 3:
        accel[2:] = vol[2:] - 2.0 * vol[1:-1] + vol[:-2]
    return {"value": accel}


def _rolling_extreme(values: np.ndarray, window: int, take_max: bool) -> np.ndarray:
    """Trailing rolling max/min; NaN until ``window`` samples are available."""
    out = np.full(values.shape, np.nan, dtype=np.float64)
    n = values.shape[0]
    if window <= 0 or n < window:
        return out
    reducer = np.max if take_max else np.min
    for i in range(window - 1, n):
        out[i] = reducer(values[i - window + 1 : i + 1])
    return out


def _ichimoku(w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    """Ichimoku cloud spans (current-bar, unshifted).

    Standard 9/26/52 conversion/base/span periods. Spans are reported at the
    current bar (the traditional forward-26 displacement is omitted so builder
    conditions compare against the price at the same bar).
    """
    tenkan_p = _int(p, "tenkan", 9)
    kijun_p = _int(p, "kijun", 26)
    span_b_p = _int(p, "span_b", 52)
    tenkan = (
        _rolling_extreme(w.high, tenkan_p, True)
        + _rolling_extreme(w.low, tenkan_p, False)
    ) / 2.0
    kijun = (
        _rolling_extreme(w.high, kijun_p, True)
        + _rolling_extreme(w.low, kijun_p, False)
    ) / 2.0
    span_a = (tenkan + kijun) / 2.0
    span_b = (
        _rolling_extreme(w.high, span_b_p, True)
        + _rolling_extreme(w.low, span_b_p, False)
    ) / 2.0
    return {
        "span_a": span_a,
        "span_b": span_b,
        "cloud_top": np.maximum(span_a, span_b),
        "cloud_bottom": np.minimum(span_a, span_b),
    }


_TABLE = {
    "vwap": _vwap,
    "rvol": _rvol,
    "volume_acceleration": _volume_acceleration,
    "ichimoku": _ichimoku,
}


class NumpyBackend(IndicatorBackend):
    """Compute custom (non-TA-Lib) indicators in pure NumPy."""

    @property
    def name(self) -> str:
        return "numpy"

    def supported_ids(self) -> frozenset[str]:
        return frozenset(_TABLE)

    def compute(self, spec: IndicatorSpec, window: OHLCVWindow) -> IndicatorResult:
        fn = _TABLE.get(spec.indicator_id)
        if fn is None:
            raise UnsupportedIndicatorError(
                f"NumpyBackend cannot compute '{spec.indicator_id}'"
            )
        if len(window) == 0:
            raise IndicatorComputationError(f"empty OHLCV window for {spec.key}")
        try:
            series = fn(window, spec.param_map)
        except Exception as exc:  # noqa: BLE001 - re-wrapped with context
            raise IndicatorComputationError(
                f"NumPy indicator failed for {spec.key}: {exc}"
            ) from exc
        latest = {output: last_finite(arr) for output, arr in series.items()}
        return IndicatorResult(spec=spec, series=series, latest=latest)
