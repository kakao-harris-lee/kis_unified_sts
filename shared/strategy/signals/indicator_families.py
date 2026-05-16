"""Pure indicator-family scorers for LLMDirectedIndicatorEntry.

3 directional scorers → float in [-1, +1] (+ = long bias, - = short bias).
1 volatility scorer → magnitude in [0, 1] (regime selectivity modulator).

Contract: every scorer returns 0.0 (neutral) on missing/invalid input and
never raises — the entry strategy must degrade to a reduced signal, never
to a structural zero (design spec section 5).
"""
from __future__ import annotations

from typing import Any


def _f(d: dict, key: str) -> float | None:
    try:
        v = d.get(key)
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _clip(x: float) -> float:
    return max(-1.0, min(1.0, x))


def momentum_reversal_score(indicators: dict[str, Any]) -> float:
    """Oversold -> +1 (long reversal), overbought -> -1. Avg of available
    RSI / Williams %R / Stochastic %K, each mapped so midpoint = 0."""
    mom = indicators.get("momentum_5m")
    if not isinstance(mom, dict):
        return 0.0
    parts: list[float] = []
    rsi = _f(mom, "rsi")
    if rsi is not None:
        parts.append((50.0 - rsi) / 50.0)
    wr = _f(mom, "williams_r")  # range -100..0; -50 = midpoint
    if wr is not None:
        parts.append((-50.0 - wr) / 50.0)
    k = _f(mom, "sto_k")
    if k is not None:
        parts.append((50.0 - k) / 50.0)
    if not parts:
        return 0.0
    return _clip(sum(parts) / len(parts))


def trend_breakout_score(indicators: dict[str, Any]) -> float:
    """EMA fast/slow alignment scaled by ADX strength, VWAP-side confirm."""
    ema_f = _f(indicators, "ema_5")
    ema_s = _f(indicators, "ema_20")
    if ema_f is None or ema_s is None or ema_s == 0.0:
        return 0.0
    raw = (ema_f - ema_s) / abs(ema_s)            # signed trend
    direction = _clip(raw * 50.0)                 # ~2% spread saturates
    adx = _f(indicators, "adx")
    strength = min(1.0, (adx or 0.0) / 40.0)      # ADX>=40 -> full
    score = direction * strength
    vwap = _f(indicators, "vwap")
    close = _f(indicators, "close")
    if vwap is not None and close is not None and vwap != 0.0:
        confirm = 0.2 if (close > vwap) == (score >= 0) else -0.2
        score = _clip(score + confirm)
    return _clip(score)


def volume_microstructure_score(indicators: dict[str, Any]) -> float:
    """Volume-velocity direction, damped by rvol, VWAP-deviation confirm."""
    vel = _f(indicators, "volume_velocity")
    if vel is None:
        return 0.0
    rvol = _f(indicators, "rvol")
    gate = min(1.0, (rvol if rvol is not None else 1.0))  # rvol<1 damps
    base = _clip(vel) * gate
    vwap = _f(indicators, "vwap")
    close = _f(indicators, "close")
    if vwap is not None and close is not None and vwap != 0.0:
        dev = _clip(((close - vwap) / abs(vwap)) * 50.0)
        base = _clip(0.5 * base + 0.5 * dev * gate)
    return _clip(base)


def volatility_regime_magnitude(
    indicators: dict[str, Any], vol_forecast: Any | None
) -> float:
    """Non-directional [0,1]. Prefer HAR-RV regime_percentile; else ATR/close
    (2%+ intraday ATR ~ high-vol regime)."""
    if vol_forecast is not None:
        try:
            pct = float(vol_forecast.regime_percentile)
            return max(0.0, min(1.0, pct / 100.0))
        except (TypeError, ValueError, AttributeError):
            pass
    atr = _f(indicators, "atr")
    close = _f(indicators, "close")
    if atr is None or close is None or close == 0.0:
        return 0.0
    return max(0.0, min(1.0, (atr / close) / 0.02))
