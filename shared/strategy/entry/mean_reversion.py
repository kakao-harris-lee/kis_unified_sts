"""Mean Reversion Entry Strategy.

Entry strategy based on Bollinger Bands and RSI:
- BUY when price below lower band AND RSI oversold
- SELL when price above upper band AND RSI overbought

Migrated from kospi_mini_sts.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

_KST = ZoneInfo("Asia/Seoul")

from shared.config.mixins import ConfigMixin
from shared.models.signal import Signal, SignalType
from shared.strategy.base import EntryContext, EntrySignalGenerator
from shared.strategy.gates.adapter_helper import apply_regime_gate
from shared.strategy.gates.regime_gate import GateConfig
from shared.strategy.market_time import to_kst

logger = logging.getLogger(__name__)


@dataclass
class MeanReversionConfig(ConfigMixin):
    """Mean Reversion 전략 설정"""

    bb_period: int = 20
    bb_std: float = 2.0
    bb_touch_buffer: float = 1.0
    rsi_period: int = 14
    rsi_oversold: int = 30
    rsi_deep_oversold: int = 25
    rsi_overbought: int = 70
    allow_short: bool = False

    # Volume confirmation
    volume_confirm: bool = False
    volume_ma_period: int = 20
    volume_threshold: float = 1.2

    # Market state filter
    market_state_filter: dict[str, Any] = field(
        default_factory=lambda: {
            "enabled": False,
            "allowed_states": [],
            "blocked_states": [],
        }
    )

    # Market cap filter (unit should match data source)
    min_market_cap: float = 0.0

    # Time filters
    market_open_hour: int = 9
    market_open_minute: int = 0
    market_close_hour: int = 15
    market_close_minute: int = 15
    skip_market_open_minutes: int = 0
    skip_market_close_minutes: int = 0

    # Cooldown
    signal_cooldown_seconds: int = 0

    # --- Phase 1 quality filters ---
    vwap_filter: bool = False  # close < vwap 필터
    adx_filter: bool = False  # ADX < threshold 필터
    adx_max_threshold: float = 25.0  # ADX 상한 (추세장 차단)
    bbw_filter: bool = False  # BB Bandwidth 최소 필터
    bbw_min_threshold: float = 0.01  # BBW 최소값 (1% bandwidth)
    percent_b_filter: bool = False  # %B 깊이 필터
    percent_b_threshold: float = 0.0  # %B < threshold (0.0 = 밴드 이하)

    # Risk hint for sizing
    stop_loss_pct: float = 1.5
    # Confidence calculation parameters
    bb_width_scale_factor: float = 0.5

    # Market regime filter (LLM-based)
    regime_filter: bool = False  # Enable regime-based filtering
    block_long_in_strong_bearish: bool = True  # Skip LONG signals in STRONG_BEARISH regime

    # Multi-timeframe base: 0 = 1-minute base (default); N = N-min MTF base
    # When set, required_indicators includes mtf_base_{N}m to trigger T1–T4 machinery.
    timeframe_minutes: int = 0


class MeanReversionEntry(EntrySignalGenerator[MeanReversionConfig]):
    """Mean reversion entry strategy.

    Entry conditions:
    - Long: Price < BB lower AND RSI < oversold
    - Short: Price > BB upper AND RSI > overbought
    """

    CONFIG_CLASS = MeanReversionConfig

    def __init__(self, config: MeanReversionConfig, gate_cfg: "GateConfig | None" = None):
        super().__init__(config)
        self._last_signal_at: dict[str, datetime] = {}
        self._gate_cfg = gate_cfg  # P2-③ T6

    def _validate_config(self):
        """설정 유효성 검증"""
        assert self.config.bb_period > 0, "bb_period must be positive"
        assert self.config.rsi_period > 0, "rsi_period must be positive"
        assert 0 < self.config.rsi_oversold < 50, "rsi_oversold must be between 0 and 50"
        assert 0 < self.config.rsi_deep_oversold < 50, "rsi_deep_oversold must be between 0 and 50"
        assert 50 < self.config.rsi_overbought < 100, "rsi_overbought must be between 50 and 100"
        assert self.config.bb_touch_buffer > 0, "bb_touch_buffer must be positive"
        assert self.config.volume_threshold > 0, "volume_threshold must be positive"
        assert self.config.volume_ma_period > 0, "volume_ma_period must be positive"
        assert self.config.signal_cooldown_seconds >= 0, "signal_cooldown_seconds must be >= 0"
        assert self.config.min_market_cap >= 0, "min_market_cap must be >= 0"
        assert self.config.skip_market_open_minutes >= 0, "skip_market_open_minutes must be >= 0"
        assert self.config.skip_market_close_minutes >= 0, "skip_market_close_minutes must be >= 0"

    @property
    def name(self) -> str:
        return "mean_reversion"

    @property
    def required_indicators(self) -> list[str]:
        indicators = ["bb_lower", "bb_upper", "bb_middle", "rsi"]
        if self.config.volume_confirm:
            indicators.extend(["volume", "volume_ma"])
        if self.config.vwap_filter:
            indicators.append("vwap")
        if self.config.adx_filter:
            indicators.append("adx")
        if self.config.timeframe_minutes > 1:
            indicators.append(f"mtf_base_{self.config.timeframe_minutes}m")
        return indicators

    async def generate(self, context: EntryContext) -> Optional[Signal]:
        """Generate entry signal based on mean reversion conditions."""
        data = context.market_data or {}
        indicators = context.indicators or {}

        def _get_value(key: str, default: float = 0.0) -> float:
            if key in indicators:
                return float(indicators.get(key, default) or default)
            return float(data.get(key, default) or default)

        close = _get_value("close", 0)
        bb_lower = _get_value("bb_lower", 0)
        bb_upper = _get_value("bb_upper", 0)
        rsi = _get_value("rsi", 50)
        volume = _get_value("volume", 0)
        volume_ma = _get_value("volume_ma", 0)
        code = str(data.get("code", "") or "")
        name = str(data.get("name", "") or "")

        if not code:
            return None

        # Dip candidates gate: only evaluate symbols in dip_candidates list
        # (populated by Screener loser ranking → Orchestrator LLM filter)
        dip_candidates = context.metadata.get("dip_candidates", {})
        if dip_candidates and code not in dip_candidates:
            return None

        # Market cap filter
        market_cap = data.get("market_cap")
        if market_cap is None:
            market_cap = data.get("market_capitalization")
        if market_cap is None:
            market_cap = data.get("market_cap_krw")
        if market_cap is None:
            market_cap = data.get("market_cap_bil")

        if self.config.min_market_cap > 0:
            if market_cap is None:
                logger.debug("Market cap missing for %s; skipping", code)
                return None
            if float(market_cap) < self.config.min_market_cap:
                return None

        # Time filters
        now = context.timestamp
        # Market hour filters use KST; context.timestamp is UTC-aware (PR #159).
        now_kst = to_kst(now)
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
            open_cutoff = open_dt + timedelta(minutes=self.config.skip_market_open_minutes)
            if now_kst < open_cutoff:
                return None

        if self.config.skip_market_close_minutes > 0:
            close_cutoff = close_dt - timedelta(minutes=self.config.skip_market_close_minutes)
            if now_kst >= close_cutoff:
                return None

        # Cooldown by symbol
        if self.config.signal_cooldown_seconds > 0:
            last_time = self._last_signal_at.get(code)
            if last_time:
                elapsed = (now - last_time).total_seconds()
                if elapsed < self.config.signal_cooldown_seconds:
                    return None

        # Market state filter
        market_state = context.metadata.get("market_state")
        if market_state is None:
            market_state = indicators.get("market_state")
        if market_state is None:
            market_state = data.get("market_state")

        state_name = str(market_state).upper() if market_state is not None else None
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

        # Volume confirmation
        if self.config.volume_confirm:
            if volume_ma <= 0:
                logger.debug("Volume MA missing for %s; skipping", code)
                return None
            if volume < (self.config.volume_threshold * volume_ma):
                return None

        bb_middle = _get_value("bb_middle", 0)

        # --- Phase 1 quality filters ---

        # 1) VWAP 필터: 세션 평균가 이하에서만 진입
        if self.config.vwap_filter:
            vwap = _get_value("vwap", 0)
            if vwap > 0 and close >= vwap:
                return None

        # 2) ADX 필터: 추세 강도 높으면 MR 부적합
        if self.config.adx_filter:
            adx = _get_value("adx", 0)
            if adx > self.config.adx_max_threshold:
                return None

        # 3) BB Bandwidth 필터: 밴드 좁으면 (squeeze) 진입 안함
        if self.config.bbw_filter:
            if bb_middle > 0:
                bbw = (bb_upper - bb_lower) / bb_middle
                if bbw < self.config.bbw_min_threshold:
                    return None

        # 4) %B 깊이 필터: 밴드 스침이 아닌 의미있는 침투 요구
        if self.config.percent_b_filter:
            bb_width = bb_upper - bb_lower
            if bb_width > 0:
                percent_b = (close - bb_lower) / bb_width
                if percent_b > self.config.percent_b_threshold:
                    return None

        # Determine oversold threshold based on regime
        oversold_threshold = self.config.rsi_oversold
        if state_name == "SIDEWAYS_DOWN":
            oversold_threshold = self.config.rsi_deep_oversold

        # === P2-③ T6: Determine candidate direction + apply RegimeGate ONCE ===
        # Cheap recompute (existing branches also do this) — preferable to 4 gate calls
        _long_candidate = (
            close <= bb_lower * self.config.bb_touch_buffer
            and rsi < oversold_threshold
        )
        _short_candidate = (
            self.config.allow_short
            and close >= bb_upper / self.config.bb_touch_buffer
            and rsi > self.config.rsi_overbought
        )
        _candidate_direction = (
            "long" if _long_candidate
            else ("short" if _short_candidate else None)
        )
        if _candidate_direction is not None and self._gate_cfg is not None:
            try:
                from shared.db.client import get_clickhouse_client
                from shared.db.config import ClickHouseConfig
                from shared.streaming.client import RedisClient
                _redis = RedisClient.get_client()
                _ch = get_clickhouse_client(ClickHouseConfig.from_env()).get_sync_client()
            except Exception:  # noqa: BLE001
                _redis, _ch = None, None
            if _redis is not None and _ch is not None:
                _stand_in = type("X", (), {
                    "metadata": {"signal_direction": _candidate_direction}})()
                blocked = apply_regime_gate(
                    gate_cfg=self._gate_cfg,
                    decision_signal=_stand_in,
                    context=context,
                    strategy_name="mean_reversion",
                    redis=_redis,
                    ch_client=_ch,
                )
                if blocked:
                    return None

        # Check for long entry (oversold)
        long_touch = close <= bb_lower * self.config.bb_touch_buffer
        if long_touch and rsi < oversold_threshold:
            # Apply regime filter for LONG signals
            if self.config.regime_filter and self.config.block_long_in_strong_bearish:
                if context.market_context is not None:
                    from shared.llm.data_classes import MarketSignal

                    if context.market_context.overall_signal == MarketSignal.STRONG_BEARISH:
                        logger.info(
                            f"Blocking Mean Reversion LONG signal for {code} due to STRONG_BEARISH regime "
                            f"(regime={context.market_context.regime}, signal={context.market_context.overall_signal.name})"
                        )
                        # Continue to check for SHORT signals if enabled
                        # (fall through to SHORT check below)
                    else:
                        # Regime allows LONG signals
                        logger.info(
                            f"Mean Reversion LONG signal: {code} close={close}, "
                            f"bb_lower={bb_lower}, rsi={rsi} (regime={context.market_context.regime})"
                        )
                        self._last_signal_at[code] = now
                        return Signal(
                            code=code,
                            name=name,
                            signal_type=SignalType.ENTRY,
                            price=close,
                            timestamp=context.timestamp,
                            strategy="mean_reversion",
                            confidence=self._calculate_confidence(close, bb_lower, bb_upper, rsi, is_long=True),
                            metadata={
                                "signal_direction": "long",
                                "stop_loss_pct": float(self.config.stop_loss_pct),
                            },
                        )
                else:
                    # No market context available - allow signal (graceful degradation)
                    logger.info(
                        f"Mean Reversion LONG signal: {code} close={close}, "
                        f"bb_lower={bb_lower}, rsi={rsi} (no regime data)"
                    )
                    self._last_signal_at[code] = now
                    return Signal(
                        code=code,
                        name=name,
                        signal_type=SignalType.ENTRY,
                        price=close,
                        timestamp=context.timestamp,
                        strategy="mean_reversion",
                        confidence=self._calculate_confidence(close, bb_lower, bb_upper, rsi, is_long=True),
                        metadata={
                            "signal_direction": "long",
                            "stop_loss_pct": float(self.config.stop_loss_pct),
                        },
                    )
            else:
                # Regime filter disabled - allow signal
                logger.info(
                    f"Mean Reversion LONG signal: {code} close={close}, "
                    f"bb_lower={bb_lower}, rsi={rsi}"
                )
                self._last_signal_at[code] = now
                return Signal(
                    code=code,
                    name=name,
                    signal_type=SignalType.ENTRY,
                    price=close,
                    timestamp=context.timestamp,
                    strategy="mean_reversion",
                    confidence=self._calculate_confidence(close, bb_lower, bb_upper, rsi, is_long=True),
                    metadata={
                        "signal_direction": "long",
                        "stop_loss_pct": float(self.config.stop_loss_pct),
                    },
                )

        # Check for short entry (overbought)
        if not self.config.allow_short:
            return None

        short_touch = close >= bb_upper / self.config.bb_touch_buffer
        if short_touch and rsi > self.config.rsi_overbought:
            logger.info(
                f"Mean Reversion SHORT signal: {code} close={close}, "
                f"bb_upper={bb_upper}, rsi={rsi}"
            )
            self._last_signal_at[code] = now
            return Signal(
                code=code,
                name=name,
                signal_type=SignalType.ENTRY,
                price=close,
                timestamp=context.timestamp,
                strategy="mean_reversion",
                confidence=self._calculate_confidence(close, bb_lower, bb_upper, rsi, is_long=False),
                metadata={
                    "signal_direction": "short",
                    "stop_loss_pct": float(self.config.stop_loss_pct),
                },
            )

        return None

    def _calculate_confidence(
        self, close: float, bb_lower: float, bb_upper: float, rsi: float, is_long: bool
    ) -> float:
        """Calculate signal confidence 0-1."""
        bb_width = bb_upper - bb_lower
        if bb_width <= 0:
            return 0.5

        if is_long:
            # How close to (or below) lower band — accounts for touch buffer
            buffer_line = bb_lower * self.config.bb_touch_buffer
            bb_score = min(1, max(0, (buffer_line - close) / (bb_width * self.config.bb_width_scale_factor)))
            # How oversold - guard against division by zero
            if self.config.rsi_oversold <= 0:
                rsi_score = 0.5
            else:
                rsi_score = max(0, (self.config.rsi_oversold - rsi) / self.config.rsi_oversold)
        else:
            # How close to (or above) upper band — accounts for touch buffer
            buffer_line = bb_upper / self.config.bb_touch_buffer
            bb_score = min(1, max(0, (close - buffer_line) / (bb_width * self.config.bb_width_scale_factor)))
            # How overbought - guard against division by zero
            divisor = 100 - self.config.rsi_overbought
            if divisor <= 0:
                rsi_score = 0.5
            else:
                rsi_score = max(0, (rsi - self.config.rsi_overbought) / divisor)

        return (bb_score + rsi_score) / 2
