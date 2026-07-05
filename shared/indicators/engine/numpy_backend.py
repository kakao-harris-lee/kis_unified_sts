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
from shared.indicators.engine.spec import IndicatorSpec, OHLCVWindow


def _int(params: Mapping[str, float], name: str, default: int) -> int:
    return int(params.get(name, default))


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


_TABLE = {
    "vwap": _vwap,
    "rvol": _rvol,
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
