"""LLM-directed indicator composite entry (futures) — succeeds RL_mppo.

Design: docs/superpowers/specs/2026-05-16-llm-directed-indicator-futures-design.md
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from shared.config.mixins import ConfigMixin
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator
from shared.strategy.market_time import to_kst
from shared.strategy.signals.indicator_families import (
    momentum_reversal_score,
    trend_breakout_score,
    volatility_regime_magnitude,
    volume_microstructure_score,
)

logger = logging.getLogger(__name__)

_KST = ZoneInfo("Asia/Seoul")
_VOL_UNSET = object()


@dataclass
class LLMDirectedIndicatorConfig(ConfigMixin):
    """Config for LLMDirectedIndicatorEntry."""

    # Bias mapper
    bias_confidence_min: float = 0.6  # LLM confidence below -> FLAT
    # Evolution hook (spec section 7 Path B). "hard" = directional mask
    # (Approach A, the only behavior implemented here). "soft" is reserved
    # for the future soft-modulation path and is NOT implemented in this
    # plan -- the switch is shipped so Path B needs no schema change later.
    mask_mode: str = "hard"

    # Ensemble weights (3 directional families)
    w_momentum: float = 0.34
    w_trend: float = 0.33
    w_volume: float = 0.33
    entry_threshold: float = 0.30  # |ensemble| floor
    vol_threshold_mult: float = 0.5  # eff_thr = thr*(1+mult*vol_mag)

    # Market-hours (futures, KST)
    market_open_hour: int = 9
    market_open_minute: int = 0
    market_close_hour: int = 15
    market_close_minute: int = 45
    skip_market_open_minutes: int = 15
    skip_market_close_minutes: int = 30
    signal_cooldown_seconds: int = 180

    # Risk
    stop_loss_pct: float = 3.0

    # Per-family scorer shape (decisive-probe spike, 2026-05-17).
    # Defaults == the original hardcoded scorer constants → zero
    # behavior change unless explicitly overridden / Optuna-tuned.
    mom_rsi_pivot: float = 50.0          # momentum: RSI neutral pivot
    trend_spread_saturation: float = 50.0  # trend: EMA-spread saturation
    trend_adx_full: float = 40.0         # trend: ADX at full strength


def _map_llm_bias(
    market_context: Any | None, config: LLMDirectedIndicatorConfig
) -> str:
    """Map LLM MarketContext -> 'LONG_BIAS' | 'SHORT_BIAS' | 'FLAT'.

    None / low-confidence / non-directional -> FLAT (indicators run
    standalone -- NEVER no-trade; design spec section 2 decision #2).
    """
    if market_context is None:
        return "FLAT"
    try:
        conf = float(getattr(market_context, "confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        return "FLAT"
    if conf < config.bias_confidence_min:
        return "FLAT"
    # is_bullish wins over is_bearish if a (degenerate) context reports both.
    try:
        is_bull = getattr(market_context, "is_bullish", None)
        is_bear = getattr(market_context, "is_bearish", None)
        if callable(is_bull) and is_bull():
            return "LONG_BIAS"
        if callable(is_bear) and is_bear():
            return "SHORT_BIAS"
    except Exception:  # noqa: BLE001 — never break the entry loop; degrade to FLAT
        logger.warning(
            "_map_llm_bias: is_bullish/is_bearish raised; defaulting to FLAT"
        )
        return "FLAT"
    return "FLAT"


class LLMDirectedIndicatorEntry(EntrySignalGenerator[LLMDirectedIndicatorConfig]):
    """LLM bias-masked 3-family indicator ensemble entry (futures)."""

    CONFIG_CLASS = LLMDirectedIndicatorConfig

    def __init__(self, config: LLMDirectedIndicatorConfig):
        super().__init__(config)
        self._last_signal_at: dict[str, datetime] = {}
        self._vol_cache: Any = _VOL_UNSET
        self._vol_cache_mono: float = 0.0

    def _validate_config(self):
        assert self.config.entry_threshold > 0, "entry_threshold > 0"
        assert 0.0 <= self.config.bias_confidence_min <= 1.0

    @property
    def name(self) -> str:
        return "llm_directed_indicator"

    @property
    def required_indicators(self) -> list[str]:
        return [
            "momentum_5m",
            "ema_5",
            "ema_20",
            "adx",
            "vwap",
            "volume_velocity",
            "rvol",
            "atr",
        ]

    def _get_vol_forecast(self) -> Any | None:
        import time as _t

        now = _t.monotonic()
        if self._vol_cache is not _VOL_UNSET and now - self._vol_cache_mono < 60.0:
            return self._vol_cache
        try:
            from shared.forecasting.vol_reader import read_latest_vol_forecast
            from shared.streaming.client import RedisClient

            vf = read_latest_vol_forecast(RedisClient.get_client())
        except Exception as exc:  # noqa: BLE001 — never break entry loop
            logger.debug("vol forecast fetch failed: %s", exc)
            vf = None
        self._vol_cache = vf
        self._vol_cache_mono = now
        return vf

    async def generate(self, context: EntryContext) -> Signal | None:
        data = context.market_data or {}
        ind = context.indicators or {}
        code = str(data.get("code", "") or "BACKTEST")
        close = float(data.get("close", ind.get("close", 0)) or 0)
        if close <= 0:
            return None

        now = context.timestamp
        now_kst = to_kst(now)
        c = self.config
        open_dt = datetime.combine(
            now_kst.date(), time(c.market_open_hour, c.market_open_minute), tzinfo=_KST
        )
        close_dt = datetime.combine(
            now_kst.date(),
            time(c.market_close_hour, c.market_close_minute),
            tzinfo=_KST,
        )
        if now_kst < open_dt + timedelta(minutes=c.skip_market_open_minutes):
            return None
        if now_kst >= close_dt - timedelta(minutes=c.skip_market_close_minutes):
            return None
        if c.signal_cooldown_seconds > 0:
            last = self._last_signal_at.get(code)
            if last and (now - last).total_seconds() < (c.signal_cooldown_seconds):
                return None

        bias = _map_llm_bias(context.market_context, c)

        ind_for_score = dict(ind)
        ind_for_score.setdefault("close", close)
        m = momentum_reversal_score(
            ind_for_score, rsi_pivot=c.mom_rsi_pivot
        )
        t = trend_breakout_score(
            ind_for_score,
            spread_saturation=c.trend_spread_saturation,
            adx_full=c.trend_adx_full,
        )
        v = volume_microstructure_score(ind_for_score)
        vol_mag = volatility_regime_magnitude(ind_for_score, self._get_vol_forecast())

        ensemble = c.w_momentum * m + c.w_trend * t + c.w_volume * v
        eff_threshold = c.entry_threshold * (1.0 + c.vol_threshold_mult * vol_mag)
        direction = "long" if ensemble > 0 else "short"

        trace = (
            f"bias={bias} m={m:.2f} t={t:.2f} v={v:.2f} "
            f"vol={vol_mag:.2f} ens={ensemble:.3f} "
            f"eff_thr={eff_threshold:.3f} dir={direction}"
        )

        if bias == "LONG_BIAS" and direction == "short":
            logger.info("[llm_directed] masked short | %s", trace)
            return None
        if bias == "SHORT_BIAS" and direction == "long":
            logger.info("[llm_directed] masked long | %s", trace)
            return None
        if abs(ensemble) < eff_threshold:
            logger.info("[llm_directed] below thr | %s", trace)
            return None

        llm_conf = 0.5
        if context.market_context is not None:
            try:
                llm_conf = float(
                    getattr(context.market_context, "confidence", 0.5) or 0.5
                )
            except (TypeError, ValueError):
                llm_conf = 0.5
        confidence = max(0.1, min(1.0, 0.5 * min(1.0, abs(ensemble)) + 0.5 * llm_conf))

        logger.info("[llm_directed] ENTER %s | %s", direction.upper(), trace)
        self._last_signal_at[code] = now
        return Signal(
            code=code,
            name=str(data.get("name", "") or ""),
            signal_type=SignalType.ENTRY,
            price=close,
            timestamp=now,
            strategy="llm_directed_indicator",
            confidence=confidence,
            metadata={
                "signal_direction": direction,
                "stop_loss_pct": float(c.stop_loss_pct),
                "ensemble": ensemble,
                "llm_bias": bias,
            },
        )
