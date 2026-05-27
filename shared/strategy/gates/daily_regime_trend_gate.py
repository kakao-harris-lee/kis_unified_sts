"""Daily trend-regime direction gate for futures entries.

The gate is intentionally a pure filter: it never creates signals, and it only
decides whether an already-generated intraday setup may pass based on daily
trend context injected into ``EntryContext.indicators``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class DailyRegimeDecision:
    """Result of applying the daily trend-regime gate."""

    allowed: bool
    reason: str
    bias: str


class DailyRegimeTrendFilterConfig(BaseModel):
    """Config for daily trend-regime direction gating."""

    enabled: bool = Field(default=False)
    permissive_on_missing: bool = Field(default=True)
    block_sideways: bool = Field(default=True)
    close_key: str = Field(default="daily_close")
    ema_short_key: str = Field(default="daily_ema_20")
    ema_short_prev_key: str = Field(default="daily_ema_20_prev")
    ema_long_key: str = Field(default="daily_ema_60")
    rsi_key: str = Field(default="daily_rsi_14")
    min_ema_gap_pct: float = Field(default=0.005, ge=0.0, le=1.0)
    long_min_rsi: float = Field(default=50.0, ge=0.0, le=100.0)
    short_max_rsi: float = Field(default=50.0, ge=0.0, le=100.0)
    neutral_rsi_low: float = Field(default=45.0, ge=0.0, le=100.0)
    neutral_rsi_high: float = Field(default=55.0, ge=0.0, le=100.0)


def _read_float(
    payload: dict[str, Any],
    key: str,
    *,
    positive: bool = True,
) -> float | None:
    raw = payload.get(key)
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if positive and value <= 0:
        return None
    if not positive and value < 0:
        return None
    return value


def apply_daily_regime_trend_filter(
    *,
    config: DailyRegimeTrendFilterConfig,
    indicators: dict[str, Any],
    signal_direction: str,
) -> DailyRegimeDecision:
    """Return whether a candidate entry may pass the daily trend gate."""

    if not config.enabled:
        return DailyRegimeDecision(True, "disabled", "unknown")

    close = _read_float(indicators, config.close_key)
    ema_short = _read_float(indicators, config.ema_short_key)
    ema_short_prev = _read_float(indicators, config.ema_short_prev_key)
    ema_long = _read_float(indicators, config.ema_long_key)
    rsi = _read_float(indicators, config.rsi_key, positive=False)

    missing = [
        name
        for name, value in (
            (config.close_key, close),
            (config.ema_short_key, ema_short),
            (config.ema_short_prev_key, ema_short_prev),
            (config.ema_long_key, ema_long),
            (config.rsi_key, rsi),
        )
        if value is None
    ]
    if missing:
        reason = "missing_daily_regime:" + ",".join(missing)
        return DailyRegimeDecision(config.permissive_on_missing, reason, "unknown")

    assert close is not None
    assert ema_short is not None
    assert ema_short_prev is not None
    assert ema_long is not None
    assert rsi is not None

    ema_gap_pct = abs(ema_short - ema_long) / close
    if config.block_sideways:
        if ema_gap_pct < config.min_ema_gap_pct:
            return DailyRegimeDecision(False, "daily_sideways:ema_gap", "sideways")
        if config.neutral_rsi_low <= rsi <= config.neutral_rsi_high:
            return DailyRegimeDecision(False, "daily_sideways:rsi_neutral", "sideways")

    long_bias = (
        close > ema_short
        and ema_short > ema_long
        and ema_short > ema_short_prev
        and rsi >= config.long_min_rsi
    )
    short_bias = (
        close < ema_short
        and ema_short < ema_long
        and ema_short < ema_short_prev
        and rsi <= config.short_max_rsi
    )

    if long_bias and not short_bias:
        bias = "long"
    elif short_bias and not long_bias:
        bias = "short"
    else:
        bias = "sideways"

    if bias == "long" and signal_direction == "short":
        return DailyRegimeDecision(False, "daily_long_bias_blocks_short", bias)
    if bias == "short" and signal_direction == "long":
        return DailyRegimeDecision(False, "daily_short_bias_blocks_long", bias)
    if bias == "sideways" and config.block_sideways:
        return DailyRegimeDecision(False, "daily_sideways:no_directional_bias", bias)

    return DailyRegimeDecision(True, f"daily_{bias}_bias", bias)
