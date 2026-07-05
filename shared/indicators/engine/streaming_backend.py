"""Streaming-convention indicator backend (value-preserving runtime SoT).

The decoupled/monolith runtime historically computed RSI/Bollinger/MFI/ADX/
Stochastic/RVOL with hand-rolled ``_calc_*`` methods on
``services.trading.indicator_calculations.IndicatorCalculationMixin``. Those
carry the runtime's *specific* conventions — first-delta-seeded Wilder RSI,
sample-std (ddof=1) Bollinger, a lenient ADX warmup, fast %K Stochastic — which
differ from TA-Lib's standard conventions on the short, early-session windows the
runtime actually uses (see ``docs/analysis/2026-07-05-shadow-parity-realdata.md``).

To retire the duplicated math into the engine *without changing any live signal*,
this backend hosts those exact algorithms behind the ``IndicatorBackend``
interface. The runtime ``_calc_*`` become thin delegates to
:func:`streaming_indicator_engine`; the math lives here, once. The no-code builder
keeps using :func:`shared.indicators.engine.default_engine` (TA-Lib standard
conventions) — the two engines are deliberately distinct because the builder wants
standard indicators while the runtime must preserve its historical values.

Each algorithm is copied verbatim from the pre-retirement ``_calc_*`` and pinned
bit-for-bit by ``tests/unit/indicators/engine/test_streaming_backend_golden.py``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

import numpy as np

from shared.indicators.engine.base import (
    IndicatorBackend,
    IndicatorComputationError,
    IndicatorResult,
    UnsupportedIndicatorError,
)
from shared.indicators.engine.params import float_param as _float
from shared.indicators.engine.params import int_param as _int
from shared.indicators.engine.spec import IndicatorSpec, OHLCVWindow

_NAN = np.array([np.nan])


def _scalar(value: float | None) -> np.ndarray:
    """Wrap a streaming scalar (or None) as a 1-element series for the engine.

    ``None`` (insufficient-data contract of ``_calc_mfi``/``_calc_adx``) maps to
    NaN, which :meth:`IndicatorResult.flat_latest` drops — so the runtime's
    "only include when not None" behavior is preserved by omission.
    """
    return _NAN if value is None else np.array([float(value)])


def _rsi(closes: list[float], period: int) -> float:
    """Verbatim ``_calc_rsi``: Wilder EMA over the FULL series, first-delta seed."""
    if len(closes) < period + 1:
        return 50.0
    alpha = 1.0 / period
    one_minus = 1.0 - alpha
    avg_gain = 0.0
    avg_loss = 0.0
    seeded = False
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gain = delta if delta > 0.0 else 0.0
        loss = -delta if delta < 0.0 else 0.0
        if not seeded:
            avg_gain, avg_loss, seeded = gain, loss, True
        else:
            avg_gain = alpha * gain + one_minus * avg_gain
            avg_loss = alpha * loss + one_minus * avg_loss
    if avg_loss == 0.0:
        return 100.0 if avg_gain > 0.0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def _bb(
    closes: list[float], period: int, std_mult: float
) -> tuple[float, float, float]:
    """Verbatim ``_calc_bb``: sample std (ddof=1). Returns (lower, middle, upper)."""
    window = closes[-period:]
    n = len(window)
    mean = sum(window) / n
    variance = sum((x - mean) ** 2 for x in window) / (n - 1)
    std = math.sqrt(variance)
    return mean - std_mult * std, mean, mean + std_mult * std


def _rvol(volumes: list[float], short: int, long: int) -> float:
    """Verbatim ``_calc_rvol``: short-window avg / long-window avg volume."""
    n = len(volumes)
    sw = min(short, n)
    lw = min(long, n)
    if lw == 0 or sw == 0:
        return 1.0
    short_avg = sum(volumes[-sw:]) / sw
    long_avg = sum(volumes[-lw:]) / lw
    if long_avg == 0:
        return 1.0
    return short_avg / long_avg


def _mfi(
    high: list[float],
    low: list[float],
    close: list[float],
    vol: list[float],
    period: int,
) -> float | None:
    """Verbatim ``_calc_mfi``: typical-price money-flow over the last period+1 bars."""
    if len(close) < period + 1:
        return None
    idx = range(len(close))[-(period + 1) :]
    positive_flow = 0.0
    negative_flow = 0.0
    prev = None
    for i in idx:
        tp_curr = (high[i] + low[i] + close[i]) / 3
        raw_flow = tp_curr * vol[i]
        if prev is not None:
            if tp_curr > prev:
                positive_flow += raw_flow
            elif tp_curr < prev:
                negative_flow += raw_flow
        prev = tp_curr
    if negative_flow == 0:
        return 100.0 if positive_flow > 0 else 50.0
    money_ratio = positive_flow / negative_flow
    return 100.0 - (100.0 / (1.0 + money_ratio))


def _adx(
    high: list[float], low: list[float], close: list[float], period: int
) -> float | None:
    """Verbatim ``_calc_adx``: Wilder ADX with the lenient partial-DX warmup."""
    n = len(close)
    if n < period + 1:
        return None
    tr_list: list[float] = []
    plus_dm_list: list[float] = []
    minus_dm_list: list[float] = []
    for i in range(1, n):
        h, lo, pc, ph, pl = high[i], low[i], close[i - 1], high[i - 1], low[i - 1]
        tr = max(h - lo, abs(h - pc), abs(lo - pc))
        up_move = h - ph
        down_move = pl - lo
        plus_dm = up_move if (up_move > down_move and up_move > 0) else 0.0
        minus_dm = down_move if (down_move > up_move and down_move > 0) else 0.0
        tr_list.append(tr)
        plus_dm_list.append(plus_dm)
        minus_dm_list.append(minus_dm)
    if len(tr_list) < period:
        return None
    atr = sum(tr_list[:period]) / period
    plus_di_smooth = sum(plus_dm_list[:period]) / period
    minus_di_smooth = sum(minus_dm_list[:period]) / period
    dx_values: list[float] = []
    for i in range(period, len(tr_list)):
        atr = (atr * (period - 1) + tr_list[i]) / period
        plus_di_smooth = (plus_di_smooth * (period - 1) + plus_dm_list[i]) / period
        minus_di_smooth = (minus_di_smooth * (period - 1) + minus_dm_list[i]) / period
        if atr > 0:
            plus_di = 100 * plus_di_smooth / atr
            minus_di = 100 * minus_di_smooth / atr
        else:
            plus_di = 0.0
            minus_di = 0.0
        di_sum = plus_di + minus_di
        if di_sum > 0:
            dx_values.append(100 * abs(plus_di - minus_di) / di_sum)
    if len(dx_values) < period:
        return sum(dx_values) / len(dx_values) if dx_values else None
    adx = sum(dx_values[:period]) / period
    for dx in dx_values[period:]:
        adx = (adx * (period - 1) + dx) / period
    return adx


def _stochastic(
    high: list[float], low: list[float], close: list[float], period: int, smooth: int
) -> tuple[float, float]:
    """Verbatim ``_calc_stochastic``: fast %K and its ``smooth``-SMA %D."""
    n = len(close)
    if n < period:
        return 50.0, 50.0
    start = max(period - 1, n - smooth - 2)
    k_vals: list[float] = []
    for i in range(start, n):
        ws = i - period + 1
        low_min = min(low[j] for j in range(ws, i + 1))
        high_max = max(high[j] for j in range(ws, i + 1))
        denom = high_max - low_min
        k_vals.append(100 * (close[i] - low_min) / (denom + 1e-10))
    stoch_k = k_vals[-1]
    stoch_d = sum(k_vals[-smooth:]) / min(smooth, len(k_vals))
    return stoch_k, stoch_d


class StreamingCompatBackend(IndicatorBackend):
    """Runtime-convention indicators (the exact pre-retirement ``_calc_*`` math)."""

    @property
    def name(self) -> str:
        return "streaming_compat"

    def supported_ids(self) -> frozenset[str]:
        return frozenset({"rsi", "bollinger", "mfi", "adx", "rvol", "stochastic"})

    def compute(self, spec: IndicatorSpec, window: OHLCVWindow) -> IndicatorResult:
        if len(window) == 0:
            raise IndicatorComputationError(f"empty OHLCV window for {spec.key}")
        p: Mapping[str, float] = spec.param_map
        close = [float(x) for x in window.close]
        high = [float(x) for x in window.high]
        low = [float(x) for x in window.low]
        vol = [float(x) for x in window.volume]
        iid = spec.indicator_id

        if iid == "rsi":
            series = {"value": _scalar(_rsi(close, _int(p, "period", 14)))}
        elif iid == "bollinger":
            period = _int(p, "period", 20)
            if len(close) < period:
                series = {"lower": _NAN, "middle": _NAN, "upper": _NAN}
            else:
                lo_, mid, up = _bb(close, period, _float(p, "std", 2.0))
                series = {
                    "lower": np.array([lo_]),
                    "middle": np.array([mid]),
                    "upper": np.array([up]),
                }
        elif iid == "mfi":
            series = {
                "value": _scalar(_mfi(high, low, close, vol, _int(p, "period", 14)))
            }
        elif iid == "adx":
            series = {"value": _scalar(_adx(high, low, close, _int(p, "period", 14)))}
        elif iid == "rvol":
            series = {
                "value": _scalar(
                    _rvol(vol, _int(p, "short_window", 5), _int(p, "long_window", 20))
                )
            }
        elif iid == "stochastic":
            k, d = _stochastic(
                high, low, close, _int(p, "k_period", 14), _int(p, "d_period", 3)
            )
            series = {"k": np.array([k]), "d": np.array([d])}
        else:
            raise UnsupportedIndicatorError(
                f"StreamingCompatBackend cannot compute '{iid}'"
            )

        from shared.indicators.engine.base import last_finite

        latest = {out: last_finite(arr) for out, arr in series.items()}
        return IndicatorResult(spec=spec, series=series, latest=latest)
