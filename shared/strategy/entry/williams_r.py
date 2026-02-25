"""Williams %R Entry Strategy.

과매도 반전 감지 기반 진입 전략:
- Williams %R이 과매도 구간(-80 이하)에서 반전 상승할 때 매수
- 추세 필터(close > BB middle)와 거래량 확인으로 false signal 감소

Williams %R Formula:
    %R = ((Highest High(n) - Close) / (Highest High(n) - Lowest Low(n))) * -100
    Range: -100 ~ 0
    Oversold: < -80, Overbought: > -20
"""

import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any, Optional

from shared.config.mixins import ConfigMixin
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator

logger = logging.getLogger(__name__)


@dataclass
class WilliamsRConfig(ConfigMixin):
    """Williams %R 진입 전략 설정"""

    # Williams %R
    williams_r_period: int = 14
    oversold_threshold: float = -80.0
    reversal_threshold: float = -80.0

    # Filters
    trend_filter: bool = True  # close > bb_middle (20-SMA)
    volume_confirm: bool = True
    volume_threshold: float = 1.0
    allow_short: bool = False

    # Risk
    stop_loss_pct: float = 3.0

    # Time filters
    signal_cooldown_seconds: int = 300
    skip_market_open_minutes: int = 30
    skip_market_close_minutes: int = 15
    market_open_hour: int = 9
    market_open_minute: int = 0
    market_close_hour: int = 15
    market_close_minute: int = 15

    # Confidence scaling
    confidence_reversal_scale: float = 50.0
    confidence_trend_scale: float = 10.0


class WilliamsREntry(EntrySignalGenerator[WilliamsRConfig]):
    """Williams %R 과매도 반전 진입 전략.

    Entry conditions (Long):
        1. 직전 %R < oversold_threshold (과매도 진입)
        2. 현재 %R >= reversal_threshold (반전 확인)
        3. close > bb_middle (추세 필터, 선택적)
        4. volume >= volume_threshold × volume_ma (거래량 확인, 선택적)
    """

    CONFIG_CLASS = WilliamsRConfig

    def __init__(self, config: WilliamsRConfig):
        super().__init__(config)
        self._last_signal_at: dict[str, datetime] = {}
        self._prev_williams_r: dict[str, float] = {}

    def _validate_config(self):
        assert self.config.williams_r_period > 0, "williams_r_period must be positive"
        assert -100 <= self.config.oversold_threshold <= 0, "oversold_threshold must be between -100 and 0"
        assert -100 <= self.config.reversal_threshold <= 0, "reversal_threshold must be between -100 and 0"
        assert self.config.volume_threshold > 0, "volume_threshold must be positive"
        assert self.config.signal_cooldown_seconds >= 0, "signal_cooldown_seconds must be >= 0"
        assert self.config.skip_market_open_minutes >= 0
        assert self.config.skip_market_close_minutes >= 0

    @property
    def name(self) -> str:
        return "williams_r"

    @property
    def required_indicators(self) -> list[str]:
        indicators = ["momentum_5m", "bb_middle"]
        if self.config.volume_confirm:
            indicators.extend(["volume", "volume_ma"])
        return indicators

    async def generate(self, context: EntryContext) -> Optional[Signal]:
        """Generate entry signal based on Williams %R oversold reversal."""
        data = context.market_data or {}
        indicators = context.indicators or {}

        def _get(key: str, default: float = 0.0) -> float:
            if key in indicators:
                return float(indicators.get(key, default) or default)
            return float(data.get(key, default) or default)

        close = _get("close", 0)
        code = str(data.get("code", "") or "")
        name = str(data.get("name", "") or "")

        if not code or close <= 0:
            return None

        now = context.timestamp

        # --- Time filters ---
        open_dt = datetime.combine(
            now.date(),
            time(self.config.market_open_hour, self.config.market_open_minute),
            tzinfo=now.tzinfo,
        )
        close_dt = datetime.combine(
            now.date(),
            time(self.config.market_close_hour, self.config.market_close_minute),
            tzinfo=now.tzinfo,
        )

        if now < open_dt:
            return None
        if self.config.skip_market_open_minutes > 0:
            if now < open_dt + timedelta(minutes=self.config.skip_market_open_minutes):
                return None
        if self.config.skip_market_close_minutes > 0:
            if now >= close_dt - timedelta(minutes=self.config.skip_market_close_minutes):
                return None

        # --- Cooldown ---
        if self.config.signal_cooldown_seconds > 0:
            last_time = self._last_signal_at.get(code)
            if last_time and (now - last_time).total_seconds() < self.config.signal_cooldown_seconds:
                return None

        # --- Extract Williams %R from momentum_5m ---
        momentum = indicators.get("momentum_5m", {})
        if not isinstance(momentum, dict) or "williams_r" not in momentum:
            return None

        current_wr = float(momentum["williams_r"])
        prev_wr = self._prev_williams_r.get(code)
        self._prev_williams_r[code] = current_wr

        if prev_wr is None:
            return None

        # --- Oversold reversal detection ---
        # Previous bar was in oversold zone, current bar crossed above reversal line
        if not (prev_wr < self.config.oversold_threshold and current_wr >= self.config.reversal_threshold):
            return None

        # --- Trend filter: close > BB middle (20-SMA) ---
        if self.config.trend_filter:
            bb_middle = _get("bb_middle", 0)
            if bb_middle > 0 and close <= bb_middle:
                return None

        # --- Volume filter ---
        if self.config.volume_confirm:
            volume = _get("volume", 0)
            volume_ma = _get("volume_ma", 0)
            if volume_ma > 0 and volume < self.config.volume_threshold * volume_ma:
                return None

        # --- Confidence calculation ---
        confidence = self._calculate_confidence(
            prev_wr, current_wr, close, _get("bb_middle", 0)
        )

        logger.info(
            f"Williams %%R LONG signal: {code} close={close}, "
            f"prev_wr={prev_wr:.1f}, current_wr={current_wr:.1f}, "
            f"confidence={confidence:.2f}"
        )
        self._last_signal_at[code] = now

        return Signal(
            code=code,
            name=name,
            signal_type=SignalType.ENTRY,
            price=close,
            timestamp=now,
            strategy="williams_r",
            confidence=confidence,
            metadata={
                "signal_direction": "long",
                "stop_loss_pct": float(self.config.stop_loss_pct),
                "williams_r": current_wr,
                "prev_williams_r": prev_wr,
            },
        )

    def _calculate_confidence(
        self,
        prev_wr: float,
        current_wr: float,
        close: float,
        bb_middle: float,
    ) -> float:
        """Calculate signal confidence 0-1.

        Based on reversal depth and trend distance.
        """
        # Reversal depth: how deep into oversold the previous bar was
        reversal_depth = abs(prev_wr - self.config.oversold_threshold)
        depth_score = min(1.0, reversal_depth / self.config.confidence_reversal_scale)

        # Trend distance: how far above bb_middle
        trend_score = 0.0
        if bb_middle > 0 and close > bb_middle:
            pct_above = ((close - bb_middle) / bb_middle) * 100
            trend_score = min(1.0, pct_above / self.config.confidence_trend_scale)

        return max(0.1, min(1.0, (depth_score + trend_score) / 2))
