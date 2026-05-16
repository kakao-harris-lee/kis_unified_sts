"""Daily Pullback Entry Strategy.

일봉 기반 눌림목 진입 전략:
- SMA(200) 위에서 장기 상승 추세 확인
- SMA(20) 아래로 눌림 발생 시 진입
- RSI(5) 과매도 확인
- SMA(60) 상승으로 중기 추세 건전성 확인

Entry Conditions (Long):
    1. close > SMA(200) — 장기 상승장
    2. close <= SMA(20) — 20일선 눌림
    3. RSI(5) < rsi_oversold — 단기 과매도
    4. SMA(60) > SMA(60, 5일전) — 중기 추세 상승 (옵션)
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from shared.config.mixins import ConfigMixin
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator

logger = logging.getLogger(__name__)


@dataclass
class DailyPullbackConfig(ConfigMixin):
    """Daily Pullback 진입 전략 설정."""

    # SMA periods
    sma_long_period: int = 200
    sma_short_period: int = 20
    sma_mid_period: int = 60

    # RSI
    rsi_period: int = 5
    rsi_oversold: float = 45.0

    # Mid trend filter
    require_mid_trend: bool = True
    mid_trend_lookback: int = 5

    # Stop loss
    stop_loss_pct: float = 7.0

    # Signal cooldown (days since last signal for same code)
    signal_cooldown_days: int = 5

    # Confidence
    confidence_base: float = 0.6
    min_confidence: float = 0.0


class DailyPullbackEntry(EntrySignalGenerator[DailyPullbackConfig]):
    """일봉 눌림목 진입 전략.

    Entry conditions (Long):
        1. close > SMA(200) — 장기 상승 추세
        2. close <= SMA(20) — 20일선 눌림
        3. RSI(5) < rsi_oversold — 단기 과매도
        4. SMA(60) > SMA(60, 5일전) — 중기 상승 (옵션)

    이 전략은 일봉 전용이며, indicators dict에 사전 계산된
    SMA/RSI 값이 포함되어 있다고 가정합니다.
    """

    CONFIG_CLASS = DailyPullbackConfig

    def __init__(self, config: DailyPullbackConfig):
        super().__init__(config)
        self._last_signal_date: dict[str, datetime] = {}

    def _validate_config(self):
        assert self.config.sma_long_period > 0, "sma_long_period must be positive"
        assert self.config.sma_short_period > 0, "sma_short_period must be positive"
        assert self.config.sma_mid_period > 0, "sma_mid_period must be positive"
        assert self.config.rsi_period > 0, "rsi_period must be positive"
        assert (
            0 < self.config.rsi_oversold < 100
        ), "rsi_oversold must be between 0 and 100"
        assert self.config.stop_loss_pct > 0, "stop_loss_pct must be positive"
        assert (
            self.config.signal_cooldown_days >= 0
        ), "signal_cooldown_days must be >= 0"
        assert (
            0 < self.config.confidence_base <= 1.0
        ), "confidence_base must be in (0, 1]"
        assert (
            0.0 <= self.config.min_confidence <= 1.0
        ), "min_confidence must be in [0, 1]"

    @property
    def name(self) -> str:
        return "daily_pullback"

    @property
    def required_indicators(self) -> list[str]:
        return ["sma_200", "sma_20", "sma_60", "rsi_5"]

    async def generate(self, context: EntryContext) -> Signal | None:
        """Generate entry signal based on daily pullback conditions."""
        data = context.market_data or {}
        indicators = context.indicators or {}

        def _get(key: str, default: float = 0.0) -> float:
            # Check exact key, then daily_ prefixed key (paper trading injects daily_ prefix)
            for k in (key, f"daily_{key}"):
                if k in indicators:
                    val = indicators.get(k, default)
                    return float(val) if val is not None else default
                if k in data:
                    val = data.get(k, default)
                    return float(val) if val is not None else default
            return default

        code = str(data.get("code", "") or "")
        name = str(data.get("name", "") or "")
        close = _get("close", 0)

        if not code or close <= 0:
            return None

        now = context.timestamp

        # --- Cooldown ---
        if self.config.signal_cooldown_days > 0:
            last_date = self._last_signal_date.get(code)
            if last_date:
                days_since = (now - last_date).days
                if days_since < self.config.signal_cooldown_days:
                    return None

        # --- Condition 1: close > SMA(200) — 장기 상승 ---
        sma_long = _get("sma_200", 0)
        if sma_long <= 0 or close <= sma_long:
            return None

        # --- Condition 2: close <= SMA(20) — 눌림 ---
        sma_short = _get("sma_20", 0)
        if sma_short <= 0 or close > sma_short:
            return None

        # --- Condition 3: RSI(5) < rsi_oversold ---
        rsi = _get("rsi_5", 50)
        if rsi >= self.config.rsi_oversold:
            return None

        # --- Condition 4 (optional): SMA(60) 상승 ---
        if self.config.require_mid_trend:
            sma_mid = _get("sma_60", 0)
            sma_mid_prev = _get("sma_60_prev", 0)
            if sma_mid > 0 and sma_mid_prev > 0 and sma_mid <= sma_mid_prev:
                return None

        # --- Calculate stop loss and confidence ---
        stop_loss = close * (1.0 - self.config.stop_loss_pct / 100.0)
        confidence = self._calculate_confidence(close, sma_long, sma_short, rsi)
        if confidence < self.config.min_confidence:
            return None

        logger.info(
            f"DailyPullback LONG signal: {code} close={close:.0f}, "
            f"SMA200={sma_long:.0f}, SMA20={sma_short:.0f}, "
            f"RSI5={rsi:.1f}, confidence={confidence:.2f}"
        )
        self._last_signal_date[code] = now

        return Signal(
            code=code,
            name=name,
            signal_type=SignalType.ENTRY,
            price=close,
            timestamp=now,
            strategy="daily_pullback",
            confidence=confidence,
            metadata={
                "signal_direction": "long",
                "trigger": "pullback_to_sma20",
                "stop_loss": stop_loss,
                "sma_200": sma_long,
                "sma_20": sma_short,
                "rsi_5": rsi,
            },
        )

    def _calculate_confidence(
        self,
        close: float,
        sma_long: float,
        sma_short: float,
        rsi: float,
    ) -> float:
        """Calculate signal confidence 0-1."""
        base = self.config.confidence_base

        # RSI depth: deeper oversold = higher confidence
        rsi_depth = max(0.0, self.config.rsi_oversold - rsi)
        rsi_score = min(0.15, rsi_depth / self.config.rsi_oversold * 0.15)

        # Trend strength: how far above SMA200
        if sma_long > 0:
            trend_pct = (close - sma_long) / sma_long
            trend_score = min(0.15, trend_pct * 0.5)
        else:
            trend_score = 0.0

        # Pullback depth: how close to SMA20 (deeper pullback = slightly higher)
        if sma_short > 0:
            pullback_pct = max(0.0, (sma_short - close) / sma_short)
            pullback_score = min(0.1, pullback_pct * 2.0)
        else:
            pullback_score = 0.0

        return max(0.1, min(1.0, base + rsi_score + trend_score + pullback_score))
