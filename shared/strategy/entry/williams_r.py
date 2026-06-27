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
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from shared.config.mixins import ConfigMixin
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator
from shared.strategy.entry.gates import (
    MarketSessionWindow,
    cooldown_elapsed,
    is_in_entry_session,
)

logger = logging.getLogger(__name__)


@dataclass
class WilliamsRConfig(ConfigMixin):
    """Williams %R 진입 전략 설정"""

    # Williams %R
    williams_r_period: int = 14
    oversold_threshold: float = -80.0
    reversal_threshold: float = -80.0
    # Short-side mirror (only used when allow_short=True — futures bidirectional)
    overbought_threshold: float = -20.0
    overbought_reversal_threshold: float = -20.0

    # Filters
    trend_filter: bool = True  # long: close > bb_middle / short: close < bb_middle
    volume_confirm: bool = True
    volume_threshold: float = 1.0
    allow_short: bool = False
    market_state_filter: dict[str, Any] = field(
        default_factory=lambda: {
            "enabled": False,
            "allowed_states": [],
            "blocked_states": [],
        }
    )
    max_full_size_bb_distance_pct: float = 0.0
    overextended_position_size_multiplier: float = 1.0

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

    # Multi-timeframe: 1 = 1-minute base (default, no-op); N>1 → N-min closed-bar
    # cadence via DecisionCadenceGate (bb_reversion_15m pattern).
    timeframe_minutes: int = 1  # >1 → decide on closed N-min bars


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
        assert (
            -100 <= self.config.oversold_threshold <= 0
        ), "oversold_threshold must be between -100 and 0"
        assert (
            -100 <= self.config.reversal_threshold <= 0
        ), "reversal_threshold must be between -100 and 0"
        assert self.config.volume_threshold > 0, "volume_threshold must be positive"
        assert (
            self.config.signal_cooldown_seconds >= 0
        ), "signal_cooldown_seconds must be >= 0"
        assert self.config.max_full_size_bb_distance_pct >= 0
        assert 0 < self.config.overextended_position_size_multiplier <= 1.0
        assert self.config.skip_market_open_minutes >= 0
        assert self.config.skip_market_close_minutes >= 0

    @property
    def name(self) -> str:
        return "williams_r"

    @property
    def _momentum_key(self) -> str:
        """Single source of truth for the timeframe-selected momentum bundle
        key. Used by BOTH required_indicators (what the resolver injects) and
        generate()'s read site (what is dereferenced). If these ever desync,
        generate() silently returns None forever — so they MUST share this.
        """
        tf = self.config.timeframe_minutes
        return "momentum_5m" if tf <= 1 else f"momentum_{tf}m"

    @property
    def required_indicators(self) -> list[str]:
        tf = self.config.timeframe_minutes
        indicators = [self._momentum_key, "bb_middle"]
        if tf > 1:
            indicators.append(f"mtf_base_{tf}m")
        if self.config.market_state_filter.get("enabled", False):
            indicators.append("mfi")
        if self.config.volume_confirm:
            indicators.extend(["rvol", "volume", "volume_ma"])
        return indicators

    @staticmethod
    def _state_name(state: Any) -> str | None:
        if state is None:
            return None
        if hasattr(state, "regime"):
            state = state.regime
        if hasattr(state, "value"):
            state = state.value
        return str(state).upper()

    async def generate(self, context: EntryContext) -> Signal | None:
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
        window = MarketSessionWindow(
            market_open_hour=self.config.market_open_hour,
            market_open_minute=self.config.market_open_minute,
            market_close_hour=self.config.market_close_hour,
            market_close_minute=self.config.market_close_minute,
            skip_market_open_minutes=self.config.skip_market_open_minutes,
            skip_market_close_minutes=self.config.skip_market_close_minutes,
        )

        if not is_in_entry_session(context.timestamp, window):
            return None

        # --- Cooldown ---
        if not cooldown_elapsed(
            now=context.timestamp,
            last_signal_at=self._last_signal_at.get(code),
            cooldown_seconds=self.config.signal_cooldown_seconds,
        ):
            return None

        # --- Extract Williams %R from the timeframe-selected momentum bundle ---
        momentum = indicators.get(self._momentum_key, {})
        if not isinstance(momentum, dict) or "williams_r" not in momentum:
            return None

        current_wr = float(momentum["williams_r"])
        prev_wr = self._prev_williams_r.get(code)
        self._prev_williams_r[code] = current_wr

        if prev_wr is None:
            return None

        # --- Direction detection ---
        # LONG: oversold reversal — prev bar deep in oversold, current crossed up.
        is_long = (
            prev_wr < self.config.oversold_threshold
            and current_wr >= self.config.reversal_threshold
        )
        # SHORT: overbought reversal — mirror of LONG. Only when allow_short
        # (futures bidirectional); stock keeps allow_short=False so this path
        # is inert and behavior is unchanged.
        is_short = self.config.allow_short and (
            prev_wr > self.config.overbought_threshold
            and current_wr <= self.config.overbought_reversal_threshold
        )

        if not is_long and not is_short:
            return None
        # If both somehow match (degenerate thresholds), prefer LONG.
        direction = "long" if is_long else "short"

        # --- Market-state filter ---
        state = (
            context.metadata.get("market_state")
            or context.metadata.get("regime")
            or indicators.get("market_state")
            or data.get("market_state")
        )
        state_name = self._state_name(state)
        filter_cfg = self.config.market_state_filter or {}
        if filter_cfg.get("enabled", False):
            allowed_states = [s.upper() for s in filter_cfg.get("allowed_states", [])]
            blocked_states = [s.upper() for s in filter_cfg.get("blocked_states", [])]
            if state_name is None:
                logger.debug("Market state missing for %s; skipping", code)
                return None
            if blocked_states and state_name in blocked_states:
                return None
            if allowed_states and state_name not in allowed_states:
                return None

        # --- Trend filter ---
        # LONG wants close above BB middle (uptrend), SHORT below (downtrend).
        if self.config.trend_filter:
            bb_middle = _get("bb_middle", 0)
            if bb_middle > 0:
                if direction == "long" and close <= bb_middle:
                    return None
                if direction == "short" and close >= bb_middle:
                    return None

        # --- Volume filter (direction-agnostic) ---
        # Prefer the canonical `rvol` (recent vs baseline volume ratio) which
        # the indicator engine always exposes. The raw `volume` key is NOT
        # emitted by the indicator pipeline (only volume_ma/rvol are), so the
        # old `volume < threshold * volume_ma` test resolved volume→0 and
        # rejected 100% of signals. Fall back to the raw comparison only when
        # rvol is unavailable (e.g. a caller supplying volume via market_data).
        if self.config.volume_confirm:
            rvol = indicators.get("rvol")
            if rvol is not None:
                if float(rvol) < self.config.volume_threshold:
                    return None
            else:
                volume = _get("volume", 0)
                volume_ma = _get("volume_ma", 0)
                if volume_ma > 0 and volume < self.config.volume_threshold * volume_ma:
                    return None

        bb_middle = _get("bb_middle", 0)
        bb_distance_pct = (
            ((close - bb_middle) / bb_middle) * 100.0 if bb_middle > 0 else 0.0
        )
        rvol = indicators.get("rvol")
        mfi = indicators.get("mfi")
        wr_reversal_points = current_wr - prev_wr
        wr_depth_points = (
            self.config.oversold_threshold - prev_wr
            if direction == "long"
            else prev_wr - self.config.overbought_threshold
        )
        position_size_multiplier = 1.0
        if (
            direction == "long"
            and self.config.max_full_size_bb_distance_pct > 0
            and bb_distance_pct > self.config.max_full_size_bb_distance_pct
        ):
            position_size_multiplier = self.config.overextended_position_size_multiplier

        # --- Confidence calculation ---
        confidence = self._calculate_confidence(
            prev_wr, current_wr, close, bb_middle, direction
        )

        logger.info(
            f"Williams %%R {direction.upper()} signal: {code} close={close}, "
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
                "signal_direction": direction,
                "stop_loss_pct": float(self.config.stop_loss_pct),
                "williams_r": current_wr,
                "prev_williams_r": prev_wr,
                "wr_reversal_points": wr_reversal_points,
                "wr_depth_points": wr_depth_points,
                "rvol": float(rvol) if rvol is not None else None,
                "mfi": float(mfi) if mfi is not None else None,
                "market_state": state_name,
                "bb_middle": bb_middle,
                "bb_distance_pct": bb_distance_pct,
                "confidence": confidence,
                "position_size_multiplier": position_size_multiplier,
            },
        )

    def _calculate_confidence(
        self,
        prev_wr: float,
        current_wr: float,
        close: float,
        bb_middle: float,
        direction: str = "long",
    ) -> float:
        """Calculate signal confidence 0-1.

        Based on reversal depth and trend distance. SHORT mirrors LONG:
        reversal depth measured from the overbought line, trend distance
        rewards price *below* BB middle.
        """
        _ = current_wr
        if direction == "short":
            reversal_depth = abs(prev_wr - self.config.overbought_threshold)
        else:
            reversal_depth = abs(prev_wr - self.config.oversold_threshold)
        depth_score = min(1.0, reversal_depth / self.config.confidence_reversal_scale)

        trend_score = 0.0
        if bb_middle > 0:
            if direction == "long" and close > bb_middle:
                pct = ((close - bb_middle) / bb_middle) * 100
                trend_score = min(1.0, pct / self.config.confidence_trend_scale)
            elif direction == "short" and close < bb_middle:
                pct = ((bb_middle - close) / bb_middle) * 100
                trend_score = min(1.0, pct / self.config.confidence_trend_scale)

        return max(0.1, min(1.0, (depth_score + trend_score) / 2))
