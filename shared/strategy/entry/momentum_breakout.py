"""Momentum Breakout Entry Strategy.

멀티 타임프레임 모멘텀 돌파 전략:
- 일간 고점 돌파(N-day high breakout) + RVOL + 거래량 확인
- 사전 스크리닝된 종목(daily_watchlist)에서만 발동
- 누적 점수(accumulation_score)로 confidence 보정

Entry Conditions:
1. code in daily_watchlist["strategies"]["momentum_breakout"]
2. close > high_5 * (1 + breakout_buffer_pct / 100)
   OR (optional) intrabar high breakout with close reclaim
3. rvol >= rvol_threshold
4. volume >= volume_ma * volume_threshold
5. ATR/close >= round_trip_cost * min_atr_cost_ratio  (minimum edge filter)
6. Time: after skip_market_open_minutes, before market close buffer
7. Cooldown: signal_cooldown_seconds per symbol
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Dict, Optional
from zoneinfo import ZoneInfo

_KST = ZoneInfo("Asia/Seoul")

from shared.config.mixins import ConfigMixin
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator
from shared.strategy.market_time import to_kst

logger = logging.getLogger(__name__)


@dataclass
class MomentumBreakoutConfig(ConfigMixin):
    """Momentum Breakout 진입 전략 설정."""

    # Breakout detection
    daily_high_period: int = 20
    breakout_buffer_pct: float = 0.1  # close must exceed high_5 by 0.1%
    intrabar_breakout_enabled: bool = False
    intrabar_reclaim_pct: float = 0.05  # allow close to dip below high_5 by this %
    intrabar_min_rvol: float = 1.8

    # Volume confirmation
    rvol_threshold: float = 1.5
    volume_threshold: float = 1.0  # current volume >= volume_ma * threshold

    # Accumulation score filter (from overnight scan)
    accumulation_score_min: int = 60

    # Minimum edge filter (ATR/close >= round_trip_cost * min_atr_cost_ratio)
    min_atr_cost_ratio: float = 2.0
    round_trip_cost: float = 0.005  # 0.5% round trip (commission + slippage)

    # Stop-loss ATR multiplier (used in entry signal metadata)
    stop_atr_multiplier: float = 1.5

    # Time filters
    skip_market_open_minutes: int = 30
    skip_market_close_minutes: int = 15
    market_open_hour: int = 9
    market_open_minute: int = 0
    market_close_hour: int = 15
    market_close_minute: int = 15

    # Cooldown
    signal_cooldown_seconds: int = 600  # 10 minutes

    # Signal properties
    allow_short: bool = False
    confidence_base: float = 0.65

    # Trend mode (activated when regime matches trend_mode_regimes)
    trend_mode_enabled: bool = False
    trend_mode_regimes: list[str] = field(default_factory=lambda: ["BULL", "BULL_STRONG", "BULL_MODERATE", "SIDEWAYS_UP"])
    trend_rvol_threshold: float = 1.0
    trend_breakout_buffer_pct: float = 0.0
    trend_signal_cooldown_seconds: int = 60
    # EMA pullback trigger (trend_mode only)
    trend_ema_pullback_enabled: bool = True
    trend_ema_fast: int = 5
    trend_ema_mid: int = 20
    trend_ema_slow: int = 60
    trend_ema_touch_buffer_atr: float = 1.0
    trend_rsi_min: float = 40.0
    # Trend mode exit overrides
    trend_exit_stop_atr_multiplier: float = 2.5
    trend_exit_trail_activation_atr: float = 1.5
    trend_exit_trail_atr_multiplier: float = 2.5
    trend_exit_max_hold_days: int = 15

    def validate(self) -> None:
        assert self.daily_high_period > 0, "daily_high_period must be positive"
        assert self.breakout_buffer_pct >= 0, "breakout_buffer_pct must be non-negative"
        assert self.intrabar_reclaim_pct >= 0, "intrabar_reclaim_pct must be non-negative"
        assert self.intrabar_min_rvol > 0, "intrabar_min_rvol must be positive"
        assert self.rvol_threshold > 0, "rvol_threshold must be positive"
        assert self.volume_threshold >= 0, "volume_threshold must be non-negative"
        assert 0 <= self.accumulation_score_min <= 100, "accumulation_score_min must be 0-100"
        assert self.min_atr_cost_ratio > 0, "min_atr_cost_ratio must be positive"
        assert self.round_trip_cost >= 0, "round_trip_cost must be non-negative"
        assert self.signal_cooldown_seconds >= 0, "signal_cooldown_seconds must be >= 0"
        assert self.skip_market_open_minutes >= 0, "skip_market_open_minutes must be >= 0"
        assert self.skip_market_close_minutes >= 0, "skip_market_close_minutes must be >= 0"
        assert 0.0 < self.confidence_base <= 1.0, "confidence_base must be in (0, 1]"


class MomentumBreakoutEntry(EntrySignalGenerator[MomentumBreakoutConfig]):
    """Momentum Breakout 진입 전략.

    Entry conditions (ALL must be true):
    1. Stock in daily_watchlist["strategies"]["momentum_breakout"] list
    2. Price: close breakout OR (optional) intrabar breakout + reclaim
    3. ATR edge: ATR / close >= round_trip_cost * min_atr_cost_ratio
    4. RVOL >= rvol_threshold
    5. Volume >= volume_ma * volume_threshold
    6. Time: outside open/close buffer windows
    7. Cooldown: signal_cooldown_seconds elapsed since last signal

    Optional confidence boost:
    - accumulation_candidates score available for this code → +0.1 bonus
    """

    CONFIG_CLASS = MomentumBreakoutConfig

    def __init__(self, config: MomentumBreakoutConfig):
        super().__init__(config)
        self._last_signal_time: Dict[str, datetime] = {}

    def _validate_config(self):
        self.config.validate()

    @property
    def name(self) -> str:
        return "momentum_breakout"

    @property
    def required_indicators(self) -> list[str]:
        return ["close", "high_5", "rvol", "volume", "volume_ma", "atr",
                "ema_5", "ema_20", "ema_60", "ema_aligned", "rsi"]

    async def generate(self, context: EntryContext) -> Optional[Signal]:
        """Generate entry signal based on momentum breakout conditions."""
        data = context.market_data or {}
        indicators = context.indicators or {}

        def _get(key: str, default: float = 0.0) -> float:
            """Prefer indicators dict, fall back to market_data."""
            if key in indicators:
                val = indicators[key]
            else:
                val = data.get(key, default)
            try:
                return float(val) if val is not None else default
            except (TypeError, ValueError):
                return default

        code = str(data.get("code", "") or "")
        name_str = str(data.get("name", "") or "")
        close = _get("close", 0.0)

        if not code or close <= 0:
            return None

        # --- Layer 1: daily watchlist gate ---
        # In static mode, only symbols approved by DailyScanner pass.
        # In dynamic mode (daily_watchlist empty), bypass the check.
        daily_watchlist = context.metadata.get("daily_watchlist", {})
        if daily_watchlist:
            strategies_watchlist = daily_watchlist.get("strategies", {})
            momentum_list = strategies_watchlist.get("momentum_breakout", [])
            if code not in momentum_list:
                return None

        now = context.timestamp
        # Market hour filters use KST; context.timestamp is UTC-aware (PR #159).
        now_kst = to_kst(now)

        # --- Detect trend mode ---
        is_trend_mode = (
            self.config.trend_mode_enabled
            and context.metadata.get("regime") in self.config.trend_mode_regimes
        )

        # --- Compute effective parameters ---
        effective_rvol = self.config.trend_rvol_threshold if is_trend_mode else self.config.rvol_threshold
        effective_buffer = self.config.trend_breakout_buffer_pct if is_trend_mode else self.config.breakout_buffer_pct
        effective_cooldown = self.config.trend_signal_cooldown_seconds if is_trend_mode else self.config.signal_cooldown_seconds

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
            return None
        if self.config.skip_market_open_minutes > 0:
            if now_kst < open_dt + timedelta(minutes=self.config.skip_market_open_minutes):
                logger.debug(f"{code}: Skipping market open window")
                return None
        if self.config.skip_market_close_minutes > 0:
            if now_kst >= close_dt - timedelta(minutes=self.config.skip_market_close_minutes):
                logger.debug(f"{code}: Skipping market close window")
                return None

        # --- Cooldown ---
        if effective_cooldown > 0:
            last_time = self._last_signal_time.get(code)
            if last_time and (now - last_time).total_seconds() < effective_cooldown:
                logger.debug(
                    f"{code}: Cooldown active "
                    f"({(now - last_time).total_seconds():.0f}s / {effective_cooldown}s)"
                )
                return None

        # --- Minimum edge filter: ATR / close >= round_trip_cost * min_atr_cost_ratio ---
        atr = _get("atr", 0.0)
        if atr <= 0 or close <= 0:
            logger.debug(f"{code}: Invalid ATR ({atr}) or close ({close})")
            return None

        min_edge = self.config.round_trip_cost * self.config.min_atr_cost_ratio
        if (atr / close) < min_edge:
            logger.debug(
                f"{code}: Minimum edge filter failed — ATR/close={atr/close:.4f} < {min_edge:.4f}"
            )
            return None

        # --- Breakout trigger: close breakout OR intrabar breakout + reclaim ---
        high_5 = _get("high_5", 0.0)
        if high_5 <= 0:
            logger.debug(f"{code}: high_5 not available or zero")
            return None

        breakout_threshold = high_5 * (1.0 + effective_buffer / 100.0)
        close_breakout = close > breakout_threshold

        intrabar_breakout = False
        intrabar_reclaim_floor = high_5
        high_price = _get("high", close)
        if (
            not close_breakout
            and self.config.intrabar_breakout_enabled
            and high_price > breakout_threshold
        ):
            intrabar_reclaim_floor = high_5 * (
                1.0 - self.config.intrabar_reclaim_pct / 100.0
            )
            if close >= intrabar_reclaim_floor:
                intrabar_breakout = True

        # --- RVOL confirm ---
        rvol = _get("rvol", 0.0)
        required_rvol = effective_rvol
        if intrabar_breakout:
            required_rvol = max(required_rvol, self.config.intrabar_min_rvol)

        trigger_type: Optional[str] = None

        if not close_breakout and not intrabar_breakout:
            # No breakout — try EMA pullback in trend mode
            if (
                is_trend_mode
                and self.config.trend_ema_pullback_enabled
            ):
                if rvol >= effective_rvol and self._check_ema_pullback(close, atr, indicators):
                    trigger_type = "ema_pullback"

            if trigger_type is None:
                logger.debug(
                    f"{code}: No breakout — close={close:.2f}, high={high_price:.2f}, "
                    f"threshold={breakout_threshold:.2f}"
                )
                return None
        else:
            if rvol < required_rvol:
                logger.debug(
                    f"{code}: RVOL {rvol:.2f} below threshold {required_rvol:.2f}"
                )
                return None
            trigger_type = "close" if close_breakout else "intrabar_reclaim"

        # --- Volume confirm ---
        volume = _get("volume", 0.0)
        volume_ma = _get("volume_ma", 0.0)
        if volume_ma > 0 and volume < volume_ma * self.config.volume_threshold:
            logger.debug(
                f"{code}: Volume {volume:.0f} below threshold "
                f"{volume_ma * self.config.volume_threshold:.0f}"
            )
            return None

        # --- Confidence calculation ---
        confidence = self._calculate_confidence(
            close=close,
            high_5=high_5,
            rvol=rvol,
            code=code,
            accumulation_candidates=context.metadata.get("accumulation_candidates", {}),
        )

        # --- Record signal time ---
        self._last_signal_time[code] = now

        # --- Compute stop loss price ---
        stop_loss_price = close - atr * self.config.stop_atr_multiplier
        breakout_pct = ((close - high_5) / high_5) * 100.0

        logger.info(
            f"MomentumBreakout LONG signal: {code} ({name_str}) "
            f"close={close:.2f}, high_5={high_5:.2f}, "
            f"breakout={breakout_pct:.2f}% ({trigger_type}), rvol={rvol:.2f}, "
            f"atr={atr:.2f}, confidence={confidence:.2%}, trend_mode={is_trend_mode}"
        )

        metadata = {
            "signal_direction": "long",
            "stop_loss": stop_loss_price,
            "atr": atr,
            "rvol": rvol,
            "high_5": high_5,
            "breakout_pct": breakout_pct if trigger_type != "ema_pullback" else 0.0,
            "breakout_type": trigger_type,
            "trigger": trigger_type,
            "trend_mode": is_trend_mode,
            "breakout_threshold": breakout_threshold,
            "intrabar_high": high_price,
            "intrabar_reclaim_floor": intrabar_reclaim_floor if trigger_type != "ema_pullback" else 0.0,
        }
        if is_trend_mode:
            metadata.update({
                "exit_stop_atr_multiplier": self.config.trend_exit_stop_atr_multiplier,
                "exit_trail_activation_atr": self.config.trend_exit_trail_activation_atr,
                "exit_trail_atr_multiplier": self.config.trend_exit_trail_atr_multiplier,
                "exit_max_hold_days": self.config.trend_exit_max_hold_days,
            })

        return Signal(
            code=code,
            name=name_str,
            signal_type=SignalType.ENTRY,
            price=close,
            timestamp=now,
            strategy="momentum_breakout",
            confidence=confidence,
            metadata=metadata,
        )

    def _check_ema_pullback(
        self, close: float, atr: float, indicators: dict
    ) -> bool:
        """Check EMA pullback trigger conditions.

        Conditions:
        0. ema_daily_aligned = True (daily EMA5d > EMA10d > EMA20d, multi-day uptrend)
        1. ema_aligned = True (EMA5 > EMA20 > EMA60, intraday alignment)
        2. close near EMA20: |close - ema_20| <= ATR * ema_touch_buffer_atr
        3. close > ema_5 (bounce confirmed)
        4. RSI > trend_rsi_min
        """
        # Daily-scale trend gate: only enter pullbacks in sustained uptrends
        if not indicators.get("ema_daily_aligned", False):
            return False

        ema_aligned = indicators.get("ema_aligned", False)
        if not ema_aligned:
            return False

        ema_mid = float(indicators.get(f"ema_{self.config.trend_ema_mid}", 0) or 0)
        ema_fast = float(indicators.get(f"ema_{self.config.trend_ema_fast}", 0) or 0)
        if ema_mid <= 0 or ema_fast <= 0:
            return False

        # Pullback location: close near EMA20
        if atr > 0 and abs(close - ema_mid) > atr * self.config.trend_ema_touch_buffer_atr:
            return False

        # Bounce confirmation: close > EMA fast
        if close <= ema_fast:
            return False

        # RSI health check
        rsi = float(indicators.get("rsi", 50) or 50)
        if rsi < self.config.trend_rsi_min:
            return False

        return True

    def _calculate_confidence(
        self,
        close: float,
        high_5: float,
        rvol: float,
        code: str,
        accumulation_candidates: dict,
    ) -> float:
        """Compute confidence in [0, 1].

        Base confidence is config.confidence_base.
        Bonuses:
        - RVOL above threshold: up to +0.15 (scales with extra RVOL above threshold)
        - Accumulation score available and >= min: +0.10 flat bonus
        """
        confidence = self.config.confidence_base

        # RVOL bonus: scale linearly, cap at +0.15 for rvol = threshold + 3
        extra_rvol = max(0.0, rvol - self.config.rvol_threshold)
        rvol_bonus = min(0.15, extra_rvol / 3.0 * 0.15)
        confidence += rvol_bonus

        # Accumulation score bonus
        if code in accumulation_candidates:
            score = accumulation_candidates[code]
            try:
                score_val = int(score)
            except (TypeError, ValueError):
                score_val = 0
            if score_val >= self.config.accumulation_score_min:
                confidence += 0.10

        return max(0.0, min(1.0, confidence))
