"""VWAP reclaim entry for stock trend-continuation pilots."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from shared.config.mixins import ConfigMixin
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator
from shared.strategy.market_time import to_kst

logger = logging.getLogger(__name__)

_KST = ZoneInfo("Asia/Seoul")


@dataclass
class TrendContinuationVWAPConfig(ConfigMixin):
    """Config for long-only stock trend-continuation entries."""

    allowed_regimes: list[str] = field(
        default_factory=lambda: ["BULL", "BULL_STRONG", "BULL_MODERATE", "SIDEWAYS_UP"]
    )
    require_regime: bool = True

    require_daily_trend: bool = True
    require_daily_sma60_rising: bool = True
    daily_rsi_min: float = 45.0
    daily_rsi_max: float = 82.0
    daily_volume_ratio_min: float = 1.0

    vwap_reclaim_buffer_pct: float = 0.05
    max_price_vs_vwap_pct: float = 3.0
    rvol_threshold: float = 1.5
    volume_threshold: float = 1.0
    require_above_open: bool = True

    skip_market_open_minutes: int = 20
    skip_market_close_minutes: int = 15
    market_open_hour: int = 9
    market_open_minute: int = 0
    market_close_hour: int = 15
    market_close_minute: int = 15
    signal_cooldown_seconds: int = 7200

    stop_loss_pct: float = 3.0
    confidence_base: float = 0.68
    confidence_max: float = 0.95
    confidence_rvol_bonus: float = 0.10
    confidence_daily_volume_bonus: float = 0.07

    def validate(self) -> None:
        if self.daily_rsi_min < 0 or self.daily_rsi_max > 100:
            raise ValueError("daily RSI bounds must be inside [0, 100]")
        if self.daily_rsi_min >= self.daily_rsi_max:
            raise ValueError("daily_rsi_min must be below daily_rsi_max")
        if self.daily_volume_ratio_min < 0:
            raise ValueError("daily_volume_ratio_min must be non-negative")
        if self.vwap_reclaim_buffer_pct < 0:
            raise ValueError("vwap_reclaim_buffer_pct must be non-negative")
        if self.max_price_vs_vwap_pct < 0:
            raise ValueError("max_price_vs_vwap_pct must be non-negative")
        if self.rvol_threshold <= 0:
            raise ValueError("rvol_threshold must be positive")
        if self.volume_threshold < 0:
            raise ValueError("volume_threshold must be non-negative")
        if self.signal_cooldown_seconds < 0:
            raise ValueError("signal_cooldown_seconds must be non-negative")
        if self.stop_loss_pct <= 0:
            raise ValueError("stop_loss_pct must be positive")
        if not 0.0 < self.confidence_base <= 1.0:
            raise ValueError("confidence_base must be in (0, 1]")
        if not self.confidence_base <= self.confidence_max <= 1.0:
            raise ValueError("confidence_max must be between confidence_base and 1")


class TrendContinuationVWAPEntry(EntrySignalGenerator[TrendContinuationVWAPConfig]):
    """Long-only continuation entry gated by daily trend and intraday VWAP reclaim."""

    CONFIG_CLASS = TrendContinuationVWAPConfig

    def __init__(self, config: TrendContinuationVWAPConfig) -> None:
        super().__init__(config)
        self._last_signal_at: dict[str, datetime] = {}

    def _validate_config(self) -> None:
        self.config.validate()

    @property
    def name(self) -> str:
        return "trend_continuation_vwap"

    @property
    def required_indicators(self) -> list[str]:
        return [
            "close",
            "open",
            "vwap",
            "rvol",
            "volume",
            "volume_ma",
            "daily_close",
            "daily_sma_20",
            "daily_sma_60",
            "daily_sma_60_prev",
            "daily_rsi_5",
            "daily_volume_ratio",
        ]

    async def generate(self, context: EntryContext) -> Signal | None:
        data = context.market_data or {}
        indicators = context.indicators or {}
        code = str(data.get("code", "") or "")
        name = str(data.get("name", "") or code)
        close = self._value(context, "close", default=0.0)
        if not code or close <= 0:
            return None

        regime = self._regime_name(context.metadata.get("regime"))
        if self.config.require_regime and regime not in {
            item.upper() for item in self.config.allowed_regimes
        }:
            logger.debug("%s: regime %s not allowed", code, regime)
            return None

        now = context.timestamp
        now_kst = to_kst(now)
        if not self._inside_time_window(now_kst):
            return None
        if self._is_cooling_down(code, now):
            return None

        if self.config.require_daily_trend and not self._daily_trend_ok(context):
            return None

        vwap = self._value(context, "vwap", default=0.0)
        if vwap <= 0:
            return None
        reclaim_level = vwap * (1.0 + self.config.vwap_reclaim_buffer_pct / 100.0)
        if close <= reclaim_level:
            return None
        price_vs_vwap_pct = (close - vwap) / vwap * 100.0
        if (
            self.config.max_price_vs_vwap_pct > 0
            and price_vs_vwap_pct > self.config.max_price_vs_vwap_pct
        ):
            return None

        if self.config.require_above_open:
            open_price = self._value(context, "open", default=0.0)
            if open_price > 0 and close <= open_price:
                return None

        rvol = self._value(context, "rvol", default=0.0)
        if rvol < self.config.rvol_threshold:
            return None

        volume = self._value(context, "volume", default=0.0)
        volume_ma = self._value(context, "volume_ma", default=0.0)
        if volume_ma > 0 and volume < volume_ma * self.config.volume_threshold:
            return None

        daily_volume_ratio = self._value(context, "daily_volume_ratio", default=0.0)
        confidence = self._confidence(rvol, daily_volume_ratio)
        self._last_signal_at[code] = now

        logger.info(
            "TrendContinuationVWAP LONG signal: %s close=%.2f vwap=%.2f "
            "rvol=%.2f daily_volume_ratio=%.2f confidence=%.2f",
            code,
            close,
            vwap,
            rvol,
            daily_volume_ratio,
            confidence,
        )
        return Signal(
            code=code,
            name=name,
            signal_type=SignalType.ENTRY,
            price=close,
            timestamp=now,
            strategy=self.name,
            confidence=confidence,
            metadata={
                "signal_direction": "long",
                "trigger": "vwap_reclaim",
                "stop_loss": close * (1.0 - self.config.stop_loss_pct / 100.0),
                "stop_loss_pct": self.config.stop_loss_pct,
                "vwap": vwap,
                "price_vs_vwap_pct": price_vs_vwap_pct,
                "rvol": rvol,
                "daily_volume_ratio": daily_volume_ratio,
                "regime": regime,
            },
        )

    def _daily_trend_ok(self, context: EntryContext) -> bool:
        daily_close = self._value(context, "daily_close", default=0.0)
        daily_sma_20 = self._value(context, "daily_sma_20", default=0.0)
        daily_sma_60 = self._value(context, "daily_sma_60", default=0.0)
        daily_sma_60_prev = self._value(context, "daily_sma_60_prev", default=0.0)
        daily_rsi = self._value(context, "daily_rsi_5", default=0.0)
        daily_volume_ratio = self._value(context, "daily_volume_ratio", default=0.0)

        if daily_close <= 0 or daily_sma_20 <= 0 or daily_sma_60 <= 0:
            return False
        if not (daily_close > daily_sma_20 > daily_sma_60):
            return False
        if (
            self.config.require_daily_sma60_rising
            and daily_sma_60_prev > 0
            and daily_sma_60 < daily_sma_60_prev
        ):
            return False
        if not (self.config.daily_rsi_min <= daily_rsi <= self.config.daily_rsi_max):
            return False
        if (
            self.config.daily_volume_ratio_min > 0
            and daily_volume_ratio < self.config.daily_volume_ratio_min
        ):
            return False
        return True

    def _inside_time_window(self, now_kst: datetime) -> bool:
        open_dt = datetime.combine(
            now_kst.date(),
            time(self.config.market_open_hour, self.config.market_open_minute),
            tzinfo=_KST,
        )
        close_dt = datetime.combine(
            now_kst.date(),
            time(self.config.market_close_hour, self.config.market_close_minute),
            tzinfo=_KST,
        )
        if now_kst < open_dt + timedelta(minutes=self.config.skip_market_open_minutes):
            return False
        if now_kst >= close_dt - timedelta(
            minutes=self.config.skip_market_close_minutes
        ):
            return False
        return True

    def _is_cooling_down(self, code: str, now: datetime) -> bool:
        if self.config.signal_cooldown_seconds <= 0:
            return False
        last = self._last_signal_at.get(code)
        if last is None:
            return False
        return (now - last).total_seconds() < self.config.signal_cooldown_seconds

    def _confidence(self, rvol: float, daily_volume_ratio: float) -> float:
        rvol_extra = max(0.0, rvol - self.config.rvol_threshold)
        rvol_bonus = min(
            self.config.confidence_rvol_bonus,
            rvol_extra
            / max(1.0, self.config.rvol_threshold)
            * self.config.confidence_rvol_bonus,
        )
        daily_volume_extra = max(
            0.0, daily_volume_ratio - self.config.daily_volume_ratio_min
        )
        daily_volume_bonus = min(
            self.config.confidence_daily_volume_bonus,
            daily_volume_extra
            / max(1.0, self.config.daily_volume_ratio_min)
            * self.config.confidence_daily_volume_bonus,
        )
        return min(
            self.config.confidence_max,
            self.config.confidence_base + rvol_bonus + daily_volume_bonus,
        )

    def _value(self, context: EntryContext, key: str, default: float = 0.0) -> float:
        for source in (
            context.indicators or {},
            context.market_data or {},
            (context.metadata or {}).get("symbol_metadata", {}),
        ):
            if not isinstance(source, dict) or key not in source:
                continue
            try:
                value = source.get(key)
                return float(value) if value is not None else default
            except (TypeError, ValueError):
                return default
        return default

    @staticmethod
    def _regime_name(regime: Any) -> str:
        if regime is None:
            return ""
        if hasattr(regime, "value"):
            regime = regime.value
        return str(regime).upper()
