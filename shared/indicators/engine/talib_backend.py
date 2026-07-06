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


def _stochrsi(
    mod: Any, w: OHLCVWindow, p: Mapping[str, float]
) -> dict[str, np.ndarray]:
    fastk, fastd = mod.STOCHRSI(
        w.close,
        timeperiod=_int(p, "period", 14),
        fastk_period=_int(p, "k", 5),
        fastd_period=_int(p, "d", 3),
        fastd_matype=0,
    )
    return {"k": fastk, "d": fastd}


# --- Phase A: additional single-input overlap / MA studies on close ----------


def _dema(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {"value": mod.DEMA(w.close, timeperiod=_int(p, "period", 20))}


def _tema(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {"value": mod.TEMA(w.close, timeperiod=_int(p, "period", 20))}


def _trima(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {"value": mod.TRIMA(w.close, timeperiod=_int(p, "period", 20))}


def _kama(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {"value": mod.KAMA(w.close, timeperiod=_int(p, "period", 10))}


def _wma(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {"value": mod.WMA(w.close, timeperiod=_int(p, "period", 20))}


def _t3(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {
        "value": mod.T3(
            w.close,
            timeperiod=_int(p, "period", 5),
            vfactor=_float(p, "volume_factor", 0.7),
        )
    }


def _midpoint(
    mod: Any, w: OHLCVWindow, p: Mapping[str, float]
) -> dict[str, np.ndarray]:
    return {"value": mod.MIDPOINT(w.close, timeperiod=_int(p, "period", 14))}


def _midprice(
    mod: Any, w: OHLCVWindow, p: Mapping[str, float]
) -> dict[str, np.ndarray]:
    return {"value": mod.MIDPRICE(w.high, w.low, timeperiod=_int(p, "period", 14))}


def _sar(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {
        "value": mod.SAR(
            w.high,
            w.low,
            acceleration=_float(p, "af_start", 0.02),
            maximum=_float(p, "af_max", 0.2),
        )
    }


# --- Phase A: additional momentum / oscillator studies -----------------------


def _adxr(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {"value": mod.ADXR(w.high, w.low, w.close, timeperiod=_int(p, "period", 14))}


def _apo(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {
        "value": mod.APO(
            w.close, fastperiod=_int(p, "fast", 12), slowperiod=_int(p, "slow", 26)
        )
    }


def _ppo(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {
        "value": mod.PPO(
            w.close, fastperiod=_int(p, "fast", 12), slowperiod=_int(p, "slow", 26)
        )
    }


def _cmo(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {"value": mod.CMO(w.close, timeperiod=_int(p, "period", 14))}


def _bop(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {"value": mod.BOP(w.open, w.high, w.low, w.close)}


def _ultosc(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {
        "value": mod.ULTOSC(
            w.high,
            w.low,
            w.close,
            timeperiod1=_int(p, "period1", 7),
            timeperiod2=_int(p, "period2", 14),
            timeperiod3=_int(p, "period3", 28),
        )
    }


def _aroon(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    # TA-Lib AROON takes a single timeperiod and returns (down, up).
    down, up = mod.AROON(w.high, w.low, timeperiod=_int(p, "period", 14))
    return {"up": up, "down": down}


def _mom(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {"value": mod.MOM(w.close, timeperiod=_int(p, "period", 10))}


# --- Phase A: volatility / statistic studies ---------------------------------


def _natr(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {"value": mod.NATR(w.high, w.low, w.close, timeperiod=_int(p, "period", 14))}


def _stddev(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {"value": mod.STDDEV(w.close, timeperiod=_int(p, "period", 20))}


def _var(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {"value": mod.VAR(w.close, timeperiod=_int(p, "period", 20))}


def _linearreg(
    mod: Any, w: OHLCVWindow, p: Mapping[str, float]
) -> dict[str, np.ndarray]:
    return {"value": mod.LINEARREG(w.close, timeperiod=_int(p, "period", 14))}


def _max(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {"value": mod.MAX(w.close, timeperiod=_int(p, "period", 30))}


def _min(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {"value": mod.MIN(w.close, timeperiod=_int(p, "period", 30))}


# --- Phase A: volume studies -------------------------------------------------


def _ad(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {"value": mod.AD(w.high, w.low, w.close, w.volume)}


def _adosc(mod: Any, w: OHLCVWindow, p: Mapping[str, float]) -> dict[str, np.ndarray]:
    return {
        "value": mod.ADOSC(
            w.high,
            w.low,
            w.close,
            w.volume,
            fastperiod=_int(p, "fast", 3),
            slowperiod=_int(p, "slow", 10),
        )
    }


# --- A5: candlestick pattern recognition -------------------------------------
#
# TA-Lib CDL* functions take (open, high, low, close) and return an int32 series
# of -100 (bearish) / 0 (none) / +100 (bullish); a few also take a ``penetration``
# double. The signed integer IS the signal, so builder conditions express
# direction with the existing operators: ``value greater_than 0`` (bullish
# occurred), ``value less_than 0`` (bearish), ``value equals 100`` (strict).
#
# Frontend catalog id -> (CDL function name, has_penetration_param). Some ids
# intentionally share one CDL function whose signed output distinguishes them
# (rising/falling three-methods; up/down gap three-methods).
_CDL_TABLE: dict[str, tuple[str, bool]] = {
    "doji": ("CDLDOJI", False),
    "dragonfly_doji": ("CDLDRAGONFLYDOJI", False),
    "gravestone_doji": ("CDLGRAVESTONEDOJI", False),
    "long_legged_doji": ("CDLLONGLEGGEDDOJI", False),
    "hammer": ("CDLHAMMER", False),
    "hanging_man": ("CDLHANGINGMAN", False),
    "inverted_hammer": ("CDLINVERTEDHAMMER", False),
    "shooting_star": ("CDLSHOOTINGSTAR", False),
    "marubozu": ("CDLMARUBOZU", False),
    "closing_marubozu": ("CDLCLOSINGMARUBOZU", False),
    "spinning_top": ("CDLSPINNINGTOP", False),
    "belt_hold": ("CDLBELTHOLD", False),
    "high_wave": ("CDLHIGHWAVE", False),
    "rickshaw_man": ("CDLRICKSHAWMAN", False),
    "engulfing": ("CDLENGULFING", False),
    "harami": ("CDLHARAMI", False),
    "harami_cross": ("CDLHARAMICROSS", False),
    "piercing": ("CDLPIERCING", False),
    "dark_cloud_cover": ("CDLDARKCLOUDCOVER", True),
    "counterattack": ("CDLCOUNTERATTACK", False),
    "on_neck": ("CDLONNECK", False),
    "in_neck": ("CDLINNECK", False),
    "thrusting": ("CDLTHRUSTING", False),
    "separating_lines": ("CDLSEPARATINGLINES", False),
    "kicking": ("CDLKICKING", False),
    "matching_low": ("CDLMATCHINGLOW", False),
    "gap_side_by_side_white": ("CDLGAPSIDESIDEWHITE", False),
    "homing_pigeon": ("CDLHOMINGPIGEON", False),
    "dojistar": ("CDLDOJISTAR", False),
    "morning_star": ("CDLMORNINGSTAR", True),
    "morning_doji_star": ("CDLMORNINGDOJISTAR", True),
    "evening_star": ("CDLEVENINGSTAR", True),
    "evening_doji_star": ("CDLEVENINGDOJISTAR", True),
    "three_white_soldiers": ("CDL3WHITESOLDIERS", False),
    "three_black_crows": ("CDL3BLACKCROWS", False),
    "three_inside": ("CDL3INSIDE", False),
    "three_outside": ("CDL3OUTSIDE", False),
    "abandoned_baby": ("CDLABANDONEDBABY", True),
    "three_stars_in_south": ("CDL3STARSINSOUTH", False),
    "advance_block": ("CDLADVANCEBLOCK", False),
    "stalled_pattern": ("CDLSTALLEDPATTERN", False),
    "tasuki_gap": ("CDLTASUKIGAP", False),
    "upside_gap_two_crows": ("CDLUPSIDEGAP2CROWS", False),
    "three_line_strike": ("CDL3LINESTRIKE", False),
    "unique_three_river": ("CDLUNIQUE3RIVER", False),
    "breakaway": ("CDLBREAKAWAY", False),
    "mat_hold": ("CDLMATHOLD", True),
    "rising_three_methods": ("CDLRISEFALL3METHODS", False),
    "falling_three_methods": ("CDLRISEFALL3METHODS", False),
    "ladder_bottom": ("CDLLADDERBOTTOM", False),
    "concealing_baby_swallow": ("CDLCONCEALBABYSWALL", False),
    "stick_sandwich": ("CDLSTICKSANDWICH", False),
    "tristar": ("CDLTRISTAR", False),
    "identical_three_crows": ("CDLIDENTICAL3CROWS", False),
    "two_crows": ("CDL2CROWS", False),
    "up_down_gap_three_methods": ("CDLXSIDEGAP3METHODS", False),
    "kicking_by_length": ("CDLKICKINGBYLENGTH", False),
}


def _candlestick(
    fn_name: str, has_penetration: bool
) -> Callable[[Any, OHLCVWindow, Mapping[str, float]], dict[str, np.ndarray]]:
    """Build a compute fn for one TA-Lib CDL* pattern.

    The CDL output is int32 (-100/0/+100); we cast to float64 so it flows through
    the engine's finite/latest machinery like any other series. ``penetration``
    (for the few patterns that accept it) is a builder-tunable param.
    """

    def _compute(
        mod: Any, w: OHLCVWindow, p: Mapping[str, float]
    ) -> dict[str, np.ndarray]:
        cdl = getattr(mod, fn_name)
        if has_penetration:
            raw = cdl(
                w.open,
                w.high,
                w.low,
                w.close,
                penetration=_float(p, "penetration", 0.3),
            )
        else:
            raw = cdl(w.open, w.high, w.low, w.close)
        return {"value": np.asarray(raw, dtype=np.float64)}

    return _compute


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
    "stochrsi": _TalibIndicator(_stochrsi, ("k", "d")),
    "trix": _TalibIndicator(_trix, ("value", "signal")),
    # Phase A — overlap / moving-average studies
    "dema": _TalibIndicator(_dema, ("value",)),
    "tema": _TalibIndicator(_tema, ("value",)),
    "trima": _TalibIndicator(_trima, ("value",)),
    "kama": _TalibIndicator(_kama, ("value",)),
    "wma": _TalibIndicator(_wma, ("value",)),
    "t3": _TalibIndicator(_t3, ("value",)),
    "midpoint": _TalibIndicator(_midpoint, ("value",)),
    "midprice": _TalibIndicator(_midprice, ("value",)),
    "sar": _TalibIndicator(_sar, ("value",)),
    # Phase A — momentum / oscillator studies
    "adxr": _TalibIndicator(_adxr, ("value",)),
    "apo": _TalibIndicator(_apo, ("value",)),
    "ppo": _TalibIndicator(_ppo, ("value",)),
    "cmo": _TalibIndicator(_cmo, ("value",)),
    "bop": _TalibIndicator(_bop, ("value",)),
    "ultosc": _TalibIndicator(_ultosc, ("value",)),
    "aroon": _TalibIndicator(_aroon, ("up", "down")),
    "momentum": _TalibIndicator(_mom, ("value",)),
    # Phase A — volatility / statistic studies
    "natr": _TalibIndicator(_natr, ("value",)),
    "std": _TalibIndicator(_stddev, ("value",)),
    "variance": _TalibIndicator(_var, ("value",)),
    "regression": _TalibIndicator(_linearreg, ("value",)),
    "maximum": _TalibIndicator(_max, ("value",)),
    "minimum": _TalibIndicator(_min, ("value",)),
    # Phase A — volume studies
    "ad": _TalibIndicator(_ad, ("value",)),
    "adosc": _TalibIndicator(_adosc, ("value",)),
    # Phase A — frontend-catalog aliases mapping to the same TA-Lib math as a
    # canonical id above (kept as distinct ids so the builder catalog's existing
    # ids resolve without a frontend rename).
    "lwma": _TalibIndicator(_wma, ("value",)),
    "volatility_ind": _TalibIndicator(_stddev, ("value",)),
    "adl": _TalibIndicator(_ad, ("value",)),
    "cho": _TalibIndicator(_adosc, ("value",)),
}

# A5 — register every candlestick pattern from _CDL_TABLE (single-output, int
# signal cast to float). Data-driven: adding a pattern is one _CDL_TABLE entry.
for _cdl_id, (_cdl_fn, _cdl_pen) in _CDL_TABLE.items():
    _TABLE[_cdl_id] = _TalibIndicator(_candlestick(_cdl_fn, _cdl_pen), ("value",))


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
