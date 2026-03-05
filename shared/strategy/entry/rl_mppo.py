"""RL M-PPO 진입 전략

학습된 Maskable PPO 모델의 행동을 EntrySignalGenerator 인터페이스로 래핑.
StrategyFactory에서 YAML 설정으로 생성 가능.

Usage:
    strategy = StrategyFactory.create_from_file("futures", "rl_mppo")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from shared.ml.base import get_device
from shared.strategy.base import EntryContext, EntrySignalGenerator
from shared.strategy.registry import EntryRegistry
from shared.strategy.rl_model_helpers import (
    build_rl_observation,
    derive_features_from_ohlcv,
    get_action_confidence,
    get_action_probabilities,
    get_rl_env_config,
    load_rl_model,
    load_rl_scaler,
    parse_hhmm,
)

if TYPE_CHECKING:
    from shared.models.signal import Signal

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")


@dataclass
class RLMPPOConfig:
    """RL M-PPO 진입 전략 설정

    config/strategies/futures/rl_mppo.yaml의 entry.params에서 로드.
    """

    model_path: str = "models/futures/rl/mppo_best/best_model.zip"
    deterministic: bool = True
    device: str = "auto"
    scaler_path: str = ""
    min_confidence: float = 0.6
    backtest_min_confidence: float = 0.35
    long_min_confidence: float | None = None
    short_min_confidence: float | None = None
    backtest_long_min_confidence: float | None = None
    backtest_short_min_confidence: float | None = None
    skip_market_open_minutes: int = 5
    skip_market_close_minutes: int = 10
    apply_time_filter_in_backtest: bool = False
    day_session_enabled: bool = True
    day_market_open: str = "09:00"
    day_market_close: str = "15:45"
    night_session_enabled: bool = False
    night_market_open: str = "18:00"
    night_market_close: str = "05:00"
    night_skip_market_open_minutes: int | None = None
    night_skip_market_close_minutes: int | None = None
    paper_skip_market_open_minutes: int | None = None
    paper_skip_market_close_minutes: int | None = None
    paper_night_skip_market_open_minutes: int | None = None
    paper_night_skip_market_close_minutes: int | None = None
    # Hard safety gate: block entries when remaining time to session close is too short.
    eod_hard_block_minutes: int = 10
    night_eod_hard_block_minutes: int | None = None
    paper_eod_hard_block_minutes: int | None = None
    paper_night_eod_hard_block_minutes: int | None = None
    enable_hold_override: bool = True
    hold_override_max_gap: float = 0.12
    hold_override_min_entry_prob: float = 0.33
    hold_override_min_confidence: float = 0.35
    backtest_hold_override_min_confidence: float = 0.30
    adaptive_confidence_enabled: bool = False
    adaptive_confidence_metric: str = "atr_ratio"  # atr_ratio | atr | bb_width
    adaptive_confidence_trigger: float = 0.0
    adaptive_confidence_backtest_boost: float = 0.0
    adaptive_confidence_live_boost: float = 0.0
    adaptive_confidence_backtest_boost_long: float | None = None
    adaptive_confidence_backtest_boost_short: float | None = None
    adaptive_confidence_live_boost_long: float | None = None
    adaptive_confidence_live_boost_short: float | None = None
    adaptive_hold_confidence_backtest_boost: float = 0.0
    adaptive_hold_confidence_live_boost: float = 0.0
    adaptive_confidence_cap: float = 0.95
    # Paper-session only overrides (no effect on backtest/live).
    paper_min_confidence: float | None = None
    paper_long_min_confidence: float | None = None
    paper_short_min_confidence: float | None = None
    paper_enable_hold_override: bool | None = None
    paper_hold_override_max_gap: float | None = None
    paper_hold_override_min_entry_prob: float | None = None
    paper_hold_override_min_confidence: float | None = None
    risk_off_long_block_enabled: bool = True
    risk_off_change_threshold: float = -0.02
    risk_off_regime_block_enabled: bool = True
    risk_off_short_min_confidence: float | None = None
    risk_off_backtest_short_min_confidence: float | None = None
    risk_off_paper_short_min_confidence: float | None = None
    risk_off_hold_override_prefer_short: bool = True
    risk_off_hold_override_max_long_advantage: float = 0.05
    risk_off_flip_long_to_short_enabled: bool = False
    risk_off_flip_min_short_prob: float = 0.30
    risk_off_regime_keywords: list[str] = field(
        default_factory=lambda: [
            "BEAR",
            "RISK_OFF",
            "STRONG_BEARISH",
            "BEARISH",
            "SIDEWAYS_DOWN",
        ]
    )


@EntryRegistry.register("rl_mppo")
class RLMPPOEntry(EntrySignalGenerator[RLMPPOConfig]):
    """학습된 M-PPO 모델 기반 진입 시그널 생성기

    학습된 Maskable PPO 모델을 로드하여 EntrySignalGenerator 인터페이스로 래핑.

    행동 매핑:
        0 (LONG_ENTRY) → Signal(BUY)
        2 (SHORT_ENTRY) → Signal(SELL)
        기타 → None (진입 없음)
    """

    CONFIG_CLASS = RLMPPOConfig

    def __init__(self, config: RLMPPOConfig):
        super().__init__(config)
        self._model = None
        self._scaler = None
        self._device = get_device(config.device)
        self._env_config = None  # lazy loaded

    def _validate_config(self) -> None:
        """설정 유효성 검증"""
        assert 0.0 <= self.config.min_confidence <= 1.0, (
            "min_confidence must be between 0.0 and 1.0"
        )
        for key, value in (
            ("long_min_confidence", self.config.long_min_confidence),
            ("short_min_confidence", self.config.short_min_confidence),
            ("backtest_long_min_confidence", self.config.backtest_long_min_confidence),
            ("backtest_short_min_confidence", self.config.backtest_short_min_confidence),
            ("paper_min_confidence", self.config.paper_min_confidence),
            ("paper_long_min_confidence", self.config.paper_long_min_confidence),
            ("paper_short_min_confidence", self.config.paper_short_min_confidence),
            ("paper_hold_override_max_gap", self.config.paper_hold_override_max_gap),
            (
                "paper_hold_override_min_entry_prob",
                self.config.paper_hold_override_min_entry_prob,
            ),
            (
                "paper_hold_override_min_confidence",
                self.config.paper_hold_override_min_confidence,
            ),
            (
                "risk_off_short_min_confidence",
                self.config.risk_off_short_min_confidence,
            ),
            (
                "risk_off_backtest_short_min_confidence",
                self.config.risk_off_backtest_short_min_confidence,
            ),
            (
                "risk_off_paper_short_min_confidence",
                self.config.risk_off_paper_short_min_confidence,
            ),
            (
                "risk_off_flip_min_short_prob",
                self.config.risk_off_flip_min_short_prob,
            ),
        ):
            if value is None:
                continue
            assert 0.0 <= value <= 1.0, f"{key} must be between 0.0 and 1.0"
        assert 0.0 <= self.config.hold_override_max_gap <= 1.0, (
            "hold_override_max_gap must be between 0.0 and 1.0"
        )
        assert 0.0 <= self.config.hold_override_min_entry_prob <= 1.0, (
            "hold_override_min_entry_prob must be between 0.0 and 1.0"
        )
        assert 0.0 <= self.config.hold_override_min_confidence <= 1.0, (
            "hold_override_min_confidence must be between 0.0 and 1.0"
        )
        assert 0.0 <= self.config.backtest_hold_override_min_confidence <= 1.0, (
            "backtest_hold_override_min_confidence must be between 0.0 and 1.0"
        )
        assert self.config.adaptive_confidence_metric in {"atr_ratio", "atr", "bb_width"}, (
            "adaptive_confidence_metric must be one of atr_ratio/atr/bb_width"
        )
        assert self.config.adaptive_confidence_trigger >= 0.0, (
            "adaptive_confidence_trigger must be non-negative"
        )
        assert 0.0 <= self.config.adaptive_confidence_backtest_boost <= 1.0, (
            "adaptive_confidence_backtest_boost must be between 0.0 and 1.0"
        )
        assert 0.0 <= self.config.adaptive_confidence_live_boost <= 1.0, (
            "adaptive_confidence_live_boost must be between 0.0 and 1.0"
        )
        for key, value in (
            (
                "adaptive_confidence_backtest_boost_long",
                self.config.adaptive_confidence_backtest_boost_long,
            ),
            (
                "adaptive_confidence_backtest_boost_short",
                self.config.adaptive_confidence_backtest_boost_short,
            ),
            (
                "adaptive_confidence_live_boost_long",
                self.config.adaptive_confidence_live_boost_long,
            ),
            (
                "adaptive_confidence_live_boost_short",
                self.config.adaptive_confidence_live_boost_short,
            ),
        ):
            if value is None:
                continue
            assert 0.0 <= value <= 1.0, f"{key} must be between 0.0 and 1.0"
        assert 0.0 <= self.config.adaptive_hold_confidence_backtest_boost <= 1.0, (
            "adaptive_hold_confidence_backtest_boost must be between 0.0 and 1.0"
        )
        assert 0.0 <= self.config.adaptive_hold_confidence_live_boost <= 1.0, (
            "adaptive_hold_confidence_live_boost must be between 0.0 and 1.0"
        )
        assert 0.0 <= self.config.adaptive_confidence_cap <= 1.0, (
            "adaptive_confidence_cap must be between 0.0 and 1.0"
        )
        assert self.config.skip_market_open_minutes >= 0, (
            "skip_market_open_minutes must be non-negative"
        )
        assert self.config.skip_market_close_minutes >= 0, (
            "skip_market_close_minutes must be non-negative"
        )
        if self.config.night_skip_market_open_minutes is not None:
            assert self.config.night_skip_market_open_minutes >= 0, (
                "night_skip_market_open_minutes must be non-negative"
            )
        if self.config.night_skip_market_close_minutes is not None:
            assert self.config.night_skip_market_close_minutes >= 0, (
                "night_skip_market_close_minutes must be non-negative"
            )
        if self.config.paper_skip_market_open_minutes is not None:
            assert self.config.paper_skip_market_open_minutes >= 0, (
                "paper_skip_market_open_minutes must be non-negative"
            )
        if self.config.paper_skip_market_close_minutes is not None:
            assert self.config.paper_skip_market_close_minutes >= 0, (
                "paper_skip_market_close_minutes must be non-negative"
            )
        if self.config.paper_night_skip_market_open_minutes is not None:
            assert self.config.paper_night_skip_market_open_minutes >= 0, (
                "paper_night_skip_market_open_minutes must be non-negative"
            )
        if self.config.paper_night_skip_market_close_minutes is not None:
            assert self.config.paper_night_skip_market_close_minutes >= 0, (
                "paper_night_skip_market_close_minutes must be non-negative"
            )
        assert self.config.eod_hard_block_minutes >= 0, (
            "eod_hard_block_minutes must be non-negative"
        )
        if self.config.night_eod_hard_block_minutes is not None:
            assert self.config.night_eod_hard_block_minutes >= 0, (
                "night_eod_hard_block_minutes must be non-negative"
            )
        if self.config.paper_eod_hard_block_minutes is not None:
            assert self.config.paper_eod_hard_block_minutes >= 0, (
                "paper_eod_hard_block_minutes must be non-negative"
            )
        if self.config.paper_night_eod_hard_block_minutes is not None:
            assert self.config.paper_night_eod_hard_block_minutes >= 0, (
                "paper_night_eod_hard_block_minutes must be non-negative"
            )
        assert self.config.risk_off_change_threshold <= 0.0, (
            "risk_off_change_threshold must be <= 0.0"
        )
        assert 0.0 <= self.config.risk_off_hold_override_max_long_advantage <= 1.0, (
            "risk_off_hold_override_max_long_advantage must be between 0.0 and 1.0"
        )
        if self.config.risk_off_regime_keywords:
            assert all(
                isinstance(item, str) and item.strip()
                for item in self.config.risk_off_regime_keywords
            ), "risk_off_regime_keywords must contain non-empty strings"

    @property
    def name(self) -> str:
        return "rl_mppo"

    @property
    def required_indicators(self) -> list[str]:
        """RL 피처 계산에 필요한 지표 목록"""
        return [
            "rsi",
            "macd",
            "macd_signal",
            "macd_hist",
            "bb_position",
            "bb_upper_dist",
            "bb_lower_dist",
            "bb_width",
            "atr",
            "stoch_k",
            "stoch_d",
            "ohlcv",
        ]

    async def generate(self, context: EntryContext) -> Signal | None:
        """진입 시그널 생성

        학습된 M-PPO 모델의 predict로 행동을 결정하고,
        LONG_ENTRY/SHORT_ENTRY인 경우 Signal 반환.

        Args:
            context: 진입 컨텍스트 (market_data, indicators)

        Returns:
            Signal if entry condition met, None otherwise
        """
        from shared.models.signal import Signal, SignalType

        # 시간 필터 (기본: 실시간만 적용, 옵션으로 백테스트에도 적용 가능)
        is_backtest = bool(context.metadata.get("is_backtest"))
        is_paper = bool(context.metadata.get("paper_trading")) and not is_backtest
        enforce_time_filter = (not is_backtest) or self.config.apply_time_filter_in_backtest
        if enforce_time_filter and not self._is_trading_time(context.timestamp, is_paper=is_paper):
            return None

        # 모델 로드 (lazy)
        model = self._load_model()
        if model is None:
            return None

        # 관측값 구성
        obs = self._build_observation(context)
        if obs is None:
            return None

        # 행동 마스크 구성
        action_masks = self._build_action_masks(context)

        # 모델 예측
        try:
            action, _states = model.predict(
                obs,
                deterministic=self.config.deterministic,
                action_masks=action_masks,
            )
            action = int(action)
        except Exception as e:
            logger.warning(f"RL model prediction failed: {e}")
            return None

        # action probabilities (masked+normalized)
        action_probs = get_action_probabilities(model, obs, action_masks, self._device)
        confidence = action_probs.get(
            action,
            get_action_confidence(model, obs, action, action_masks, self._device),
        )

        long_prob = action_probs.get(0, 0.0)
        short_prob = action_probs.get(2, 0.0)
        hold_prob = action_probs.get(4, 0.0)
        self._record_action_probabilities(long_prob, short_prob, hold_prob)
        risk_off, risk_off_reason = self._detect_risk_off_context(context)

        override_reason = ""
        if action == 4:  # HOLD
            override_action = self._maybe_override_hold(
                action_probs,
                is_paper=is_paper,
                risk_off=risk_off,
            )
            if override_action is not None:
                action = override_action
                confidence = action_probs.get(action, confidence)
                override_reason = "hold_override"

        if (
            risk_off
            and action == 0
            and self.config.risk_off_flip_long_to_short_enabled
            and short_prob >= float(self.config.risk_off_flip_min_short_prob)
        ):
            action = 2
            confidence = short_prob
            override_reason = "risk_off_flip_to_short"

        base_threshold = self._resolve_base_threshold(
            is_backtest=is_backtest,
            is_paper=is_paper,
            override_reason=override_reason,
            action=action,
            risk_off=risk_off,
        )
        threshold, threshold_reason, regime_metric = self._resolve_effective_threshold(
            context=context,
            is_backtest=is_backtest,
            override_reason=override_reason,
            base_threshold=base_threshold,
            action=action,
        )
        if self.config.risk_off_long_block_enabled and risk_off and action == 0:
            logger.info(
                "RL long entry blocked in risk-off context: code=%s reason=%s",
                context.market_data.get("code", ""),
                risk_off_reason,
            )
            return None

        if confidence < threshold:
            logger.debug(
                f"RL action {action} confidence {confidence:.3f} "
                f"below threshold {threshold:.3f} ({threshold_reason})"
            )
            return None

        meta_common = {
            "rl_action": action,
            "rl_confidence": confidence,
            "rl_long_prob": long_prob,
            "rl_short_prob": short_prob,
            "rl_hold_prob": hold_prob,
            "rl_override_reason": override_reason,
            "rl_threshold": threshold,
            "rl_threshold_base": base_threshold,
            "rl_threshold_reason": threshold_reason,
            "rl_regime_metric": regime_metric,
            "rl_risk_off": risk_off,
            "rl_risk_off_reason": risk_off_reason,
        }

        # 행동 → Signal 변환
        price = float(context.market_data.get("close", 0.0) or 0.0)
        code = context.market_data.get("code", "101S3000")
        if price <= 0:
            return None

        if action == 0:  # LONG_ENTRY
            return Signal(
                code=code,
                name=context.market_data.get("name", "KOSPI200선물"),
                signal_type=SignalType.ENTRY,
                strategy=self.name,
                price=price,
                confidence=confidence,
                timestamp=context.timestamp,
                metadata={
                    "signal_direction": "long",
                    "direction": "long",
                    **meta_common,
                },
            )
        elif action == 2:  # SHORT_ENTRY
            return Signal(
                code=code,
                name=context.market_data.get("name", "KOSPI200선물"),
                signal_type=SignalType.ENTRY,
                strategy=self.name,
                price=price,
                confidence=confidence,
                timestamp=context.timestamp,
                metadata={
                    "signal_direction": "short",
                    "direction": "short",
                    **meta_common,
                },
            )

        return None

    def _detect_risk_off_context(self, context: EntryContext) -> tuple[bool, str]:
        reasons: list[str] = []

        if self.config.risk_off_regime_block_enabled:
            regime_matches = self._match_risk_off_regime(context)
            if regime_matches:
                reasons.append(f"regime:{regime_matches}")

        day_change = self._extract_day_change_ratio(context.market_data)
        if (
            day_change is not None
            and day_change <= float(self.config.risk_off_change_threshold)
        ):
            reasons.append(f"day_change:{day_change:.4f}")

        if reasons:
            return True, ";".join(reasons)
        return False, ""

    def _match_risk_off_regime(self, context: EntryContext) -> str:
        keywords = [k.upper().strip() for k in self.config.risk_off_regime_keywords if k.strip()]
        if not keywords:
            return ""

        candidates: list[str] = []
        for value in (
            context.metadata.get("regime"),
            context.metadata.get("market_state"),
            context.market_data.get("regime"),
            context.market_data.get("market_state"),
        ):
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip().upper())

        if not candidates:
            return ""

        for candidate in candidates:
            for keyword in keywords:
                if keyword in candidate:
                    return candidate
        return ""

    def _extract_day_change_ratio(self, market_data: dict[str, Any]) -> float | None:
        open_price = self._as_positive_float(
            market_data.get("open", market_data.get("day_open"))
        )
        close_price = self._as_positive_float(market_data.get("close"))
        if open_price is not None and close_price is not None and open_price > 0:
            return (close_price - open_price) / open_price

        for key in ("change_rate", "day_change_rate", "change_pct", "change_percent"):
            parsed = self._parse_ratio(market_data.get(key))
            if parsed is not None:
                return parsed

        change = market_data.get("change")
        parsed_change = self._parse_ratio(change)
        if parsed_change is not None and abs(parsed_change) <= 1.0:
            return parsed_change
        return None

    @staticmethod
    def _parse_ratio(value: Any) -> float | None:
        if value is None:
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if abs(parsed) > 1.0:
            return parsed / 100.0
        return parsed

    def _maybe_override_hold(
        self,
        action_probs: dict[int, float],
        *,
        is_paper: bool,
        risk_off: bool,
    ) -> int | None:
        """HOLD가 근소 우세인 경우 진입 액션으로 오버라이드."""
        enable_override = (
            self.config.paper_enable_hold_override
            if is_paper and self.config.paper_enable_hold_override is not None
            else self.config.enable_hold_override
        )
        if not enable_override:
            return None

        max_gap = (
            self.config.paper_hold_override_max_gap
            if is_paper and self.config.paper_hold_override_max_gap is not None
            else self.config.hold_override_max_gap
        )
        min_entry_prob = (
            self.config.paper_hold_override_min_entry_prob
            if is_paper and self.config.paper_hold_override_min_entry_prob is not None
            else self.config.hold_override_min_entry_prob
        )

        hold_prob = float(action_probs.get(4, 0.0))
        long_prob = float(action_probs.get(0, 0.0))
        short_prob = float(action_probs.get(2, 0.0))

        best_action, best_prob = (
            (0, long_prob) if long_prob >= short_prob else (2, short_prob)
        )
        if (
            risk_off
            and self.config.risk_off_hold_override_prefer_short
            and short_prob >= min_entry_prob
        ):
            long_advantage = long_prob - short_prob
            if long_advantage <= float(self.config.risk_off_hold_override_max_long_advantage):
                best_action, best_prob = 2, short_prob
        if best_prob < min_entry_prob:
            return None

        gap = hold_prob - best_prob
        if gap > max_gap:
            return None

        logger.debug(
            "RL hold override: hold=%.3f best_entry=%.3f action=%s gap=%.3f",
            hold_prob,
            best_prob,
            best_action,
            gap,
        )
        return best_action

    def _record_action_probabilities(
        self, long_prob: float, short_prob: float, hold_prob: float
    ) -> None:
        """Emit Prometheus metrics for RL action probabilities."""
        try:
            from services.monitoring.metrics import get_metrics_collector

            get_metrics_collector().record_rl_entry_action_probabilities(
                strategy=self.name,
                long_prob=long_prob,
                short_prob=short_prob,
                hold_prob=hold_prob,
            )
        except Exception:
            # Metrics should never break trading logic.
            pass

    def _resolve_base_threshold(
        self,
        *,
        is_backtest: bool,
        is_paper: bool,
        override_reason: str,
        action: int,
        risk_off: bool,
    ) -> float:
        if risk_off and action == 2:
            if (
                is_paper
                and self.config.risk_off_paper_short_min_confidence is not None
            ):
                return float(self.config.risk_off_paper_short_min_confidence)
            if (
                is_backtest
                and self.config.risk_off_backtest_short_min_confidence is not None
            ):
                return float(self.config.risk_off_backtest_short_min_confidence)
            if self.config.risk_off_short_min_confidence is not None:
                return float(self.config.risk_off_short_min_confidence)

        if override_reason:
            if is_paper and self.config.paper_hold_override_min_confidence is not None:
                return float(self.config.paper_hold_override_min_confidence)
            return (
                self.config.backtest_hold_override_min_confidence
                if is_backtest
                else self.config.hold_override_min_confidence
            )
        if is_paper:
            if action == 0 and self.config.paper_long_min_confidence is not None:
                return float(self.config.paper_long_min_confidence)
            if action == 2 and self.config.paper_short_min_confidence is not None:
                return float(self.config.paper_short_min_confidence)
            if self.config.paper_min_confidence is not None:
                return float(self.config.paper_min_confidence)
        if action == 0:
            directional = (
                self.config.backtest_long_min_confidence
                if is_backtest
                else self.config.long_min_confidence
            )
            if directional is not None:
                return float(directional)
        elif action == 2:
            directional = (
                self.config.backtest_short_min_confidence
                if is_backtest
                else self.config.short_min_confidence
            )
            if directional is not None:
                return float(directional)
        return float(self.config.backtest_min_confidence if is_backtest else self.config.min_confidence)

    def _resolve_effective_threshold(
        self,
        *,
        context: EntryContext,
        is_backtest: bool,
        override_reason: str,
        base_threshold: float,
        action: int,
    ) -> tuple[float, str, float | None]:
        if not self.config.adaptive_confidence_enabled:
            return base_threshold, "adaptive_disabled", None

        trigger = float(self.config.adaptive_confidence_trigger)
        if trigger <= 0:
            return base_threshold, "adaptive_no_trigger", None

        regime_metric = self._extract_regime_metric(context)
        if regime_metric is None:
            return base_threshold, "adaptive_metric_unavailable", None

        if regime_metric < trigger:
            return base_threshold, f"adaptive_normal:{regime_metric:.6f}", regime_metric

        if override_reason:
            boost = (
                self.config.adaptive_hold_confidence_backtest_boost
                if is_backtest
                else self.config.adaptive_hold_confidence_live_boost
            )
        else:
            boost = self._resolve_directional_adaptive_boost(
                action=action,
                is_backtest=is_backtest,
            )

        effective = min(
            float(self.config.adaptive_confidence_cap),
            float(base_threshold) + max(0.0, float(boost)),
        )
        return effective, f"adaptive_high_vol:{regime_metric:.6f}", regime_metric

    def _resolve_directional_adaptive_boost(self, *, action: int, is_backtest: bool) -> float:
        if action == 0:
            directional = (
                self.config.adaptive_confidence_backtest_boost_long
                if is_backtest
                else self.config.adaptive_confidence_live_boost_long
            )
            if directional is not None:
                return float(directional)
        elif action == 2:
            directional = (
                self.config.adaptive_confidence_backtest_boost_short
                if is_backtest
                else self.config.adaptive_confidence_live_boost_short
            )
            if directional is not None:
                return float(directional)
        return float(
            self.config.adaptive_confidence_backtest_boost
            if is_backtest
            else self.config.adaptive_confidence_live_boost
        )

    def _extract_regime_metric(self, context: EntryContext) -> float | None:
        metric = str(self.config.adaptive_confidence_metric).strip().lower()
        if metric == "atr_ratio":
            atr = self._as_positive_float(
                context.indicators.get("atr", context.market_data.get("atr"))
            )
            price = self._as_positive_float(
                context.market_data.get("close", context.indicators.get("close"))
            )
            if atr is None or price is None or price <= 0:
                return None
            return atr / price
        if metric == "atr":
            return self._as_positive_float(
                context.indicators.get("atr", context.market_data.get("atr"))
            )
        if metric == "bb_width":
            return self._as_positive_float(
                context.indicators.get("bb_width", context.market_data.get("bb_width"))
            )
        return None

    @staticmethod
    def _as_positive_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    def _load_model(self) -> Any:
        """학습된 모델 로드 (lazy loading, 모듈 캐시 사용)"""
        if self._model is not None:
            return self._model
        self._model = load_rl_model(self.config.model_path, self._device)
        return self._model

    def _load_scaler(self) -> Any:
        """Load scaler used in RL training (lazy, 모듈 캐시 사용)."""
        if self._scaler is not None:
            return self._scaler
        self._scaler = load_rl_scaler(self.config.scaler_path, self.config.model_path)
        return self._scaler

    def _get_env_config(self):
        """RL 환경 설정 로드 (lazy)"""
        if self._env_config is None:
            self._env_config = get_rl_env_config()
        return self._env_config

    def _build_observation(self, context: EntryContext) -> Any:
        """EntryContext → RL 관측값 변환

        시장 피처 (25개) + 포지션 피처 (3개) + 시간 피처 (3개) = 31차원
        """
        env_cfg = self._get_env_config()

        # 포지션 피처
        position_side = 0.0
        contracts = 0.0
        unrealized_pnl = 0.0

        if context.current_positions:
            pos = context.current_positions[0]
            side = getattr(pos, "side", None)
            side_val = getattr(side, "value", side)
            if str(side_val).lower() == "long":
                position_side = 1.0
            elif str(side_val).lower() == "short":
                position_side = -1.0
            contracts = getattr(pos, "quantity", 0) / max(env_cfg.max_contracts, 1)
            # Position.unrealized_pnl lacks contract_multiplier; match training env
            raw_pnl = getattr(pos, "unrealized_pnl", 0.0)
            unrealized_pnl = (raw_pnl * env_cfg.contract_multiplier) / env_cfg.initial_balance

        derived = derive_features_from_ohlcv(context.indicators, context.market_data)
        scaler = self._load_scaler()

        return build_rl_observation(
            market_data=context.market_data,
            indicators=context.indicators,
            position_side=position_side,
            contracts=contracts,
            unrealized_pnl=unrealized_pnl,
            timestamp=context.timestamp,
            scaler=scaler,
            env_config=env_cfg,
            ohlcv_derived=derived,
        )

    def _build_action_masks(self, context: EntryContext) -> Any:
        """포지션 기반 행동 마스크 생성"""
        import numpy as np

        masks = np.zeros(5, dtype=bool)
        masks[4] = True  # Hold 항상 가능

        if not context.current_positions:
            # 포지션 없음 → 진입만 가능
            masks[0] = True  # LONG_ENTRY
            masks[2] = True  # SHORT_ENTRY
        else:
            pos = context.current_positions[0]
            side = getattr(pos, "side", None)
            side_val = getattr(side, "value", side)
            if str(side_val).lower() == "long":
                masks[1] = True  # LONG_EXIT
            elif str(side_val).lower() == "short":
                masks[3] = True  # SHORT_EXIT

        return masks

    def _is_trading_time(self, timestamp: datetime, *, is_paper: bool = False) -> bool:
        """거래 가능 시간 확인

        주/야간 세션별로 장 시작 후 skip_open, 장 마감 전 skip_close를 적용한다.
        """
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=KST)

        current_minute = timestamp.hour * 60 + timestamp.minute
        day_skip_open = (
            int(self.config.paper_skip_market_open_minutes)
            if is_paper and self.config.paper_skip_market_open_minutes is not None
            else int(self.config.skip_market_open_minutes)
        )
        day_skip_close = (
            int(self.config.paper_skip_market_close_minutes)
            if is_paper and self.config.paper_skip_market_close_minutes is not None
            else int(self.config.skip_market_close_minutes)
        )
        day_hard_close_block = (
            int(self.config.paper_eod_hard_block_minutes)
            if is_paper and self.config.paper_eod_hard_block_minutes is not None
            else int(self.config.eod_hard_block_minutes)
        )
        sessions: list[tuple[time, time, int, int, int]] = []
        if self.config.day_session_enabled:
            sessions.append(
                (
                    self._parse_session_time(
                        self.config.day_market_open, default_hour=9, default_minute=0
                    ),
                    self._parse_session_time(
                        self.config.day_market_close, default_hour=15, default_minute=45
                    ),
                    day_skip_open,
                    day_skip_close,
                    day_hard_close_block,
                )
            )

        if self.config.night_session_enabled:
            night_skip_open = (
                int(self.config.paper_night_skip_market_open_minutes)
                if is_paper and self.config.paper_night_skip_market_open_minutes is not None
                else int(
                    self.config.night_skip_market_open_minutes
                    if self.config.night_skip_market_open_minutes is not None
                    else self.config.skip_market_open_minutes
                )
            )
            night_skip_close = (
                int(self.config.paper_night_skip_market_close_minutes)
                if is_paper and self.config.paper_night_skip_market_close_minutes is not None
                else int(
                    self.config.night_skip_market_close_minutes
                    if self.config.night_skip_market_close_minutes is not None
                    else self.config.skip_market_close_minutes
                )
            )
            night_hard_close_block = (
                int(self.config.paper_night_eod_hard_block_minutes)
                if is_paper
                and self.config.paper_night_eod_hard_block_minutes is not None
                else int(
                    self.config.night_eod_hard_block_minutes
                    if self.config.night_eod_hard_block_minutes is not None
                    else (
                        self.config.paper_eod_hard_block_minutes
                        if is_paper and self.config.paper_eod_hard_block_minutes is not None
                        else self.config.eod_hard_block_minutes
                    )
                )
            )
            sessions.append(
                (
                    self._parse_session_time(
                        self.config.night_market_open, default_hour=18, default_minute=0
                    ),
                    self._parse_session_time(
                        self.config.night_market_close, default_hour=5, default_minute=0
                    ),
                    night_skip_open,
                    night_skip_close,
                    night_hard_close_block,
                )
            )

        for session_open, session_close, skip_open, skip_close, hard_close_block in sessions:
            if self._is_within_session(
                current_minute=current_minute,
                session_open=session_open,
                session_close=session_close,
                skip_open=max(0, skip_open),
                skip_close=max(0, skip_close),
                hard_close_block=max(0, hard_close_block),
            ):
                return True
        return False

    @staticmethod
    def _parse_session_time(value: str, *, default_hour: int, default_minute: int) -> time:
        hour, minute = parse_hhmm(value, default_hour=default_hour, default_minute=default_minute)
        return time(hour=hour, minute=minute)

    @staticmethod
    def _is_within_session(
        *,
        current_minute: int,
        session_open: time,
        session_close: time,
        skip_open: int,
        skip_close: int,
        hard_close_block: int = 0,
    ) -> bool:
        open_minute = session_open.hour * 60 + session_open.minute
        close_minute = session_close.hour * 60 + session_close.minute

        # Raw session membership check (without skip windows).
        if open_minute <= close_minute:
            in_raw_session = open_minute <= current_minute <= close_minute
        else:
            in_raw_session = current_minute >= open_minute or current_minute <= close_minute
        if not in_raw_session:
            return False

        # Hard block near session close: block when remaining minutes <= threshold.
        if hard_close_block > 0:
            remaining_to_close = (close_minute - current_minute) % 1440
            if remaining_to_close <= hard_close_block:
                return False

        start_minute = (open_minute + skip_open) % 1440
        end_minute = (close_minute - skip_close) % 1440
        span = (end_minute - start_minute) % 1440
        if span <= 0:
            return False

        if start_minute <= end_minute:
            return start_minute <= current_minute <= end_minute
        return current_minute >= start_minute or current_minute <= end_minute
