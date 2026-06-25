"""Trend Pullback Entry Strategy.

멀티 타임프레임 추세 추종 눌림목 전략:
- 일간 SMA(200) 위에서 장기 상승 추세 확인
- BB 하단 터치 + RSI 과매도에서 반등 진입
- Williams %R 과매도 반전 시 진입
- 일간 watchlist 기반 후보 종목 필터링

Entry Conditions (Long):
    Trend filter: close > SMA(200) — 장기 상승 추세
    Primary: BB touch (close <= bb_lower * buffer) AND RSI < rsi_oversold
    OR
    Alternative: Williams %R reversal (prev_wr < oversold AND current_wr >= reversal)
                 AND RSI < rsi_oversold (both triggers require RSI confirm)
    Volume confirm: volume >= volume_ma * volume_threshold
    Edge filter: atr/close >= round_trip_cost * min_atr_cost_ratio
"""

import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

_KST = ZoneInfo("Asia/Seoul")

from shared.config.mixins import ConfigMixin
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator
from shared.strategy.entry.daily_watchlist_gate import daily_watchlist_allows
from shared.strategy.market_time import to_kst

logger = logging.getLogger(__name__)


@dataclass
class TrendPullbackConfig(ConfigMixin):
    """Trend Pullback 진입 전략 설정"""

    # Bollinger Bands
    bb_period: int = 20
    bb_std: float = 2.0
    bb_touch_buffer: float = 1.005  # close <= bb_lower * bb_touch_buffer

    # RSI
    rsi_oversold: float = 35.0

    # Williams %R
    williams_r_oversold: float = -80.0
    williams_r_reversal: float = -70.0

    # Volume
    volume_threshold: float = 1.0  # volume >= volume_ma * threshold

    # Minimum edge filter
    min_atr_cost_ratio: float = 2.0
    round_trip_cost: float = 0.005  # 0.5% round-trip cost

    # Stop-loss ATR multiplier (used in entry signal metadata)
    stop_atr_multiplier: float = 2.5
    stop_fallback_cost_multiplier: float = 3.0

    # Time filters
    skip_market_open_minutes: int = 30
    skip_market_close_minutes: int = 15
    market_open_hour: int = 9
    market_open_minute: int = 0
    market_close_hour: int = 15
    market_close_minute: int = 15

    # Cooldown
    signal_cooldown_seconds: int = 300

    # Short
    allow_short: bool = False

    # Confidence
    confidence_base: float = 0.6


class TrendPullbackEntry(EntrySignalGenerator[TrendPullbackConfig]):
    """멀티 타임프레임 추세 추종 눌림목 진입 전략.

    Entry conditions (Long):
        Layer 1: code must be in daily_watchlist["strategies"]["trend_pullback"]
        Trend filter: close > SMA(200) — 장기 상승 추세
        Time: skip first 30 min and last 15 min of session
        Cooldown: no signal within signal_cooldown_seconds
        Edge: atr/close >= round_trip_cost * min_atr_cost_ratio
        Trigger (at least one + RSI confirm):
            - BB touch: close <= bb_lower * bb_touch_buffer AND rsi < rsi_oversold
            - WR reversal: prev_wr < oversold AND current_wr >= reversal AND rsi < rsi_oversold
        Volume: volume >= volume_ma * volume_threshold
    """

    CONFIG_CLASS = TrendPullbackConfig

    def __init__(self, config: TrendPullbackConfig):
        super().__init__(config)
        self._prev_williams_r: dict[str, float] = {}
        self._last_signal_time: dict[str, datetime] = {}

    def _validate_config(self):
        assert self.config.bb_period > 0, "bb_period must be positive"
        assert self.config.bb_std > 0, "bb_std must be positive"
        assert self.config.bb_touch_buffer >= 1.0, "bb_touch_buffer must be >= 1.0"
        assert 0 < self.config.rsi_oversold < 50, "rsi_oversold must be between 0 and 50"
        assert -100 <= self.config.williams_r_oversold <= 0, "williams_r_oversold must be between -100 and 0"
        assert -100 <= self.config.williams_r_reversal <= 0, "williams_r_reversal must be between -100 and 0"
        assert self.config.volume_threshold > 0, "volume_threshold must be positive"
        assert self.config.min_atr_cost_ratio > 0, "min_atr_cost_ratio must be positive"
        assert self.config.round_trip_cost > 0, "round_trip_cost must be positive"
        assert self.config.signal_cooldown_seconds >= 0, "signal_cooldown_seconds must be >= 0"
        assert self.config.skip_market_open_minutes >= 0, "skip_market_open_minutes must be >= 0"
        assert self.config.skip_market_close_minutes >= 0, "skip_market_close_minutes must be >= 0"
        assert 0 < self.config.confidence_base <= 1.0, "confidence_base must be in (0, 1]"

    @property
    def name(self) -> str:
        return "trend_pullback"

    @property
    def required_indicators(self) -> list[str]:
        return ["bb_lower", "bb_middle", "rsi", "volume", "volume_ma", "atr", "momentum_5m", "daily_sma_200"]

    async def generate(self, context: EntryContext) -> Optional[Signal]:
        """Generate entry signal based on trend pullback conditions."""
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

        # --- Layer 1: daily watchlist filter ---
        # Empty/absent per-strategy list → dynamic mode (no daily constraint);
        # gate only when a non-empty pre-screen list exists for this strategy.
        if not daily_watchlist_allows(context.metadata, "trend_pullback", code):
            return None

        # --- Trend filter: close > SMA(200) — 장기 상승 추세 ---
        sma_200 = _get("sma_200", 0)
        if sma_200 <= 0 or close <= sma_200:
            logger.debug(f"TrendPullback {code}: SMA filter fail (close={close}, sma_200={sma_200})")
            return None

        now = context.timestamp
        # Market hour filters use KST; context.timestamp is UTC-aware (PR #159).
        now_kst = to_kst(now)

        # --- Time filters ---
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

        if now_kst < open_dt:
            logger.debug(f"TrendPullback {code}: before market open")
            return None

        if self.config.skip_market_open_minutes > 0:
            if now_kst < open_dt + timedelta(minutes=self.config.skip_market_open_minutes):
                logger.debug(f"TrendPullback {code}: skip market open window")
                return None

        if self.config.skip_market_close_minutes > 0:
            if now_kst >= close_dt - timedelta(minutes=self.config.skip_market_close_minutes):
                logger.debug(f"TrendPullback {code}: skip market close window")
                return None

        # --- Cooldown ---
        if self.config.signal_cooldown_seconds > 0:
            last_time = self._last_signal_time.get(code)
            if last_time and (now - last_time).total_seconds() < self.config.signal_cooldown_seconds:
                logger.debug(f"TrendPullback {code}: cooldown active")
                return None

        # --- Minimum edge filter: atr/close >= round_trip_cost * min_atr_cost_ratio ---
        atr = _get("atr", 0)
        if atr > 0 and close > 0:
            atr_ratio = atr / close
            min_required = self.config.round_trip_cost * self.config.min_atr_cost_ratio
            if atr_ratio < min_required:
                logger.debug(f"TrendPullback {code}: ATR cost ratio too low ({atr_ratio:.6f} < {min_required:.6f})")
                return None

        # --- Extract Williams %R from momentum_5m ---
        self._update_prev_williams_r(code, context)
        prev_wr = self._prev_williams_r.get(f"{code}__prev")

        # --- Extract current indicators ---
        bb_lower = _get("bb_lower", 0)
        rsi = _get("rsi", 50)

        # --- Intraday triggers ---
        trigger_type: Optional[str] = None

        # Trigger 1: BB touch + RSI confirm
        if bb_lower > 0 and close <= bb_lower * self.config.bb_touch_buffer:
            if rsi < self.config.rsi_oversold:
                trigger_type = "bb_touch"

        # Trigger 2: Williams %R reversal + RSI confirm
        if trigger_type is None and prev_wr is not None:
            momentum = indicators.get("momentum_5m", {})
            if isinstance(momentum, dict) and "williams_r" in momentum:
                current_wr = float(momentum["williams_r"])
                if (
                    prev_wr < self.config.williams_r_oversold
                    and current_wr >= self.config.williams_r_reversal
                    and rsi < self.config.rsi_oversold
                ):
                    trigger_type = "wr_reversal"

        if trigger_type is None:
            logger.debug(
                f"TrendPullback {code}: no trigger (bb_lower={bb_lower}, close={close}, rsi={rsi:.1f})"
            )
            return None

        # --- Volume confirm ---
        volume = _get("volume", 0)
        volume_ma = _get("volume_ma", 0)
        if volume_ma > 0 and volume < volume_ma * self.config.volume_threshold:
            logger.debug(
                f"TrendPullback {code}: volume filter fail "
                f"(vol={volume}, vol_ma={volume_ma}, threshold={self.config.volume_threshold})"
            )
            return None

        # --- Calculate stop loss and confidence ---
        stop_loss = (
            close - atr * self.config.stop_atr_multiplier
            if atr > 0
            else close * (1 - self.config.round_trip_cost * self.config.stop_fallback_cost_multiplier)
        )
        confidence = self._calculate_confidence(close, bb_lower, rsi, trigger_type)

        logger.info(
            f"TrendPullback LONG signal: {code} close={close}, "
            f"bb_lower={bb_lower}, rsi={rsi:.1f}, "
            f"trigger={trigger_type}, confidence={confidence:.2f}"
        )
        self._last_signal_time[code] = now

        return Signal(
            code=code,
            name=name,
            signal_type=SignalType.ENTRY,
            price=close,
            timestamp=now,
            strategy="trend_pullback",
            confidence=confidence,
            metadata={
                "signal_direction": "long",
                "trigger": trigger_type,
                "stop_loss": stop_loss,
                "atr": atr,
                "rsi": rsi,
                "bb_lower": bb_lower,
            },
        )

    def _update_prev_williams_r(self, code: str, context: EntryContext) -> None:
        """Store current williams_r as previous for next tick.

        Uses two keys: current and prev, so we can detect crossings.
        """
        indicators = context.indicators or {}
        momentum = indicators.get("momentum_5m", {})
        if isinstance(momentum, dict) and "williams_r" in momentum:
            current_wr = float(momentum["williams_r"])
            # Promote current → prev
            current_key = f"{code}__current"
            prev_key = f"{code}__prev"
            prev_current = self._prev_williams_r.get(current_key)
            if prev_current is not None:
                self._prev_williams_r[prev_key] = prev_current
            self._prev_williams_r[current_key] = current_wr

    def _calculate_confidence(
        self,
        close: float,
        bb_lower: float,
        rsi: float,
        trigger_type: str,
    ) -> float:
        """Calculate signal confidence 0-1."""
        base = self.config.confidence_base

        # RSI depth score: how oversold
        rsi_depth = max(0.0, self.config.rsi_oversold - rsi)
        rsi_score = min(0.2, rsi_depth / self.config.rsi_oversold * 0.2)

        # BB depth score: how far below lower band
        bb_score = 0.0
        if bb_lower > 0 and trigger_type == "bb_touch":
            pct_below = max(0.0, (bb_lower - close) / bb_lower)
            bb_score = min(0.2, pct_below * 100 * 0.2)

        return max(0.1, min(1.0, base + rsi_score + bb_score))
