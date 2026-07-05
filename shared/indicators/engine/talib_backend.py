"""TA-Lib implementation of :class:`IndicatorBackend`.

TA-Lib is the Track A single source of truth for *standard* indicators — it
carries the industry-standard conventions (Wilder RSI/ADX/ATR, population-std
Bollinger) that the repo previously re-derived by hand in 5-7 duplicated
``_calc_*`` copies. This backend wraps it behind the engine interface and
normalizes TA-Lib's multi-output tuples onto builder-catalog output ids.

The import is lazy (module-level, guarded) so this module can be imported for
type-checking / registry wiring even where the TA-Lib wheel is absent; a
concrete :class:`TALibBackend` instance requires it. Indicators TA-Lib does not
provide (``vwap``, ``rvol``, ``volume_acceleration``, ``ichimoku``) are simply
not in :meth:`supported_ids`; a NumPy/Numba backend will cover them (WS-A5).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

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

try:  # pragma: no cover - exercised via availability branch in tests
    import talib as _talib
except ImportError:  # pragma: no cover
    _talib = None  # type: ignore[assignment]


def _ema_nan_aware(mod: Any, series: np.ndarray, period: int) -> np.ndarray:
    """EMA of ``series`` that tolerates a leading run of NaN warmup values.

    TA-Lib's ``EMA`` propagates NaN from the head, so we EMA only the finite
    tail and re-pad the head with NaN. Used for TRIX's signal line, which is an
    EMA of the (NaN-warmed) TRIX series.
    """
    out = np.full(series.shape, np.nan, dtype=np.float64)
    finite = np.flatnonzero(np.isfinite(series))
    if finite.size == 0:
        return out
    start = int(finite[0])
    tail = np.ascontiguousarray(series[start:], dtype=np.float64)
    out[start:] = mod.EMA(tail, timeperiod=period)
    return out


# --- per-indicator compute functions (mod, window, params) -> {output: series}


def _rsi(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {"value": mod.RSI(w.close, timeperiod=_int(p, "period", 14))}


def _ema(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {"value": mod.EMA(w.close, timeperiod=_int(p, "period", 20))}


def _sma(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {"value": mod.SMA(w.close, timeperiod=_int(p, "period", 20))}


def _volume_ma(
    mod: Any, w: OHLCVWindow, p: Mapping[str, float]
) -> dict[str, np.ndarray]:
    return {"value": mod.SMA(w.volume, timeperiod=_int(p, "period", 20))}


def _atr(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {"value": mod.ATR(w.high, w.low, w.close, timeperiod=_int(p, "period", 14))}


def _adx(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {"value": mod.ADX(w.high, w.low, w.close, timeperiod=_int(p, "period", 14))}


def _willr(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {
        "value": mod.WILLR(w.high, w.low, w.close, timeperiod=_int(p, "period", 14))
    }


def _cci(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {"value": mod.CCI(w.high, w.low, w.close, timeperiod=_int(p, "period", 9))}


def _mfi(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {
        "value": mod.MFI(
            w.high, w.low, w.close, w.volume, timeperiod=_int(p, "period", 14)
        )
    }


def _obv(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {"value": mod.OBV(w.close, w.volume)}


def _roc(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {"value": mod.ROC(w.close, timeperiod=_int(p, "period", 10))}


def _mom(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {"value": mod.MOM(w.close, timeperiod=_int(p, "period", 10))}


def _bollinger(
    mod: Any, w: OHLCVWindow, p: Mapping[str, float]
) -> dict[str, np.ndarray]:
    period = _int(p, "period", 20)
    std = _float(p, "std", 2.0)
    upper, middle, lower = mod.BBANDS(
        w.close, timeperiod=period, nbdevup=std, nbdevdn=std, matype=0
    )
    return {"upper": upper, "middle": middle, "lower": lower}


def _macd(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    macd, signal, hist = mod.MACD(
        w.close,
        fastperiod=_int(p, "fast", 12),
        slowperiod=_int(p, "slow", 26),
        signalperiod=_int(p, "signal", 9),
    )
    return {"value": macd, "signal": signal, "histogram": hist}


def _stochastic(
    mod: Any, w: OHLCVWindow, p: Mapping[str, float]
) -> dict[str, np.ndarray]:
    slowk, slowd = mod.STOCH(
        w.high,
        w.low,
        w.close,
        fastk_period=_int(p, "k_period", 14),
        slowk_period=_int(p, "d_period", 3),
        slowk_matype=0,
        slowd_period=_int(p, "d_period", 3),
        slowd_matype=0,
    )
    return {"k": slowk, "d": slowd}


def _trix(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    value = mod.TRIX(w.close, timeperiod=_int(p, "n", 12))
    signal = _ema_nan_aware(mod, value, _int(p, "signal", 9))
    return {"value": value, "signal": signal}


@dataclass(frozen=True)
class _TalibIndicator:
    """How to compute one indicator via TA-Lib."""

    fn: Callable[[Any, OHLCVWindow, Mapping[str, float]], dict[str, np.ndarray]]
    outputs: tuple[str, ...]


# Data-driven registry: adding an indicator is one entry here + a compute fn.
_TABLE: dict[str, _TalibIndicator] = {
    "rsi": _TalibIndicator(_rsi, ("value",)),
    "ema": _TalibIndicator(_ema, ("value",)),
    "sma": _TalibIndicator(_sma, ("value",)),
    "volume_ma": _TalibIndicator(_volume_ma, ("value",)),
    "atr": _TalibIndicator(_atr, ("value",)),
    "adx": _TalibIndicator(_adx, ("value",)),
    "williams_r": _TalibIndicator(_willr, ("value",)),
    "cci": _TalibIndicator(_cci, ("value",)),
    "mfi": _TalibIndicator(_mfi, ("value",)),
    "obv": _TalibIndicator(_obv, ("value",)),
    "roc": _TalibIndicator(_roc, ("value",)),
    "mom": _TalibIndicator(_mom, ("value",)),
    "bollinger": _TalibIndicator(_bollinger, ("upper", "middle", "lower")),
    "macd": _TalibIndicator(_macd, ("value", "signal", "histogram")),
    "stochastic": _TalibIndicator(_stochastic, ("k", "d")),
    "trix": _TalibIndicator(_trix, ("value", "signal")),
}


class TALibBackend(IndicatorBackend):
    """Compute standard indicators through TA-Lib."""

    def __init__(self) -> None:
        if _talib is None:  # pragma: no cover - guarded by available()
            raise RuntimeError(
                "TA-Lib is not installed; install the `TA-Lib` wheel "
                "(python:3.11-slim base) to use TALibBackend."
            )
        self._talib = _talib

    @staticmethod
    def available() -> bool:
        """Whether the TA-Lib wheel is importable in this environment."""
        return _talib is not None

    @property
    def name(self) -> str:
        return "talib"

    def supported_ids(self) -> frozenset[str]:
        return frozenset(_TABLE)

    def compute(self, spec: IndicatorSpec, window: OHLCVWindow) -> IndicatorResult:
        entry = _TABLE.get(spec.indicator_id)
        if entry is None:
            raise UnsupportedIndicatorError(
                f"TALibBackend cannot compute '{spec.indicator_id}'"
            )
        if len(window) == 0:
            raise IndicatorComputationError(f"empty OHLCV window for {spec.key}")
        try:
            series = entry.fn(self._talib, window, spec.param_map)
        except Exception as exc:  # noqa: BLE001 - re-wrapped with context
            raise IndicatorComputationError(
                f"TA-Lib failed for {spec.key}: {exc}"
            ) from exc
        missing = set(entry.outputs) - set(series)
        if missing:
            raise IndicatorComputationError(
                f"{spec.indicator_id} backend did not emit declared outputs: "
                f"{sorted(missing)}"
            )
        latest = {output: last_finite(arr) for output, arr in series.items()}
        return IndicatorResult(spec=spec, series=series, latest=latest)
