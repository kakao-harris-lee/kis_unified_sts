"""RL M-PPO 진입 전략

학습된 Maskable PPO 모델의 행동을 EntrySignalGenerator 인터페이스로 래핑.
StrategyFactory에서 YAML 설정으로 생성 가능.

Usage:
    strategy = StrategyFactory.create_from_file("futures", "rl_mppo")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from zoneinfo import ZoneInfo

from shared.ml.base import get_device
from shared.strategy.base import EntryContext, EntrySignalGenerator
from shared.strategy.registry import EntryRegistry
from shared.strategy.rl_model_helpers import (
    build_rl_observation,
    derive_features_from_ohlcv,
    get_action_confidence,
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
    skip_market_open_minutes: int = 5
    skip_market_close_minutes: int = 10


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
        assert self.config.skip_market_open_minutes >= 0, (
            "skip_market_open_minutes must be non-negative"
        )
        assert self.config.skip_market_close_minutes >= 0, (
            "skip_market_close_minutes must be non-negative"
        )

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

    async def generate(self, context: EntryContext) -> Optional["Signal"]:
        """진입 시그널 생성

        학습된 M-PPO 모델의 predict로 행동을 결정하고,
        LONG_ENTRY/SHORT_ENTRY인 경우 Signal 반환.

        Args:
            context: 진입 컨텍스트 (market_data, indicators)

        Returns:
            Signal if entry condition met, None otherwise
        """
        from shared.models.signal import Signal, SignalType

        # 시간 필터 (백테스트에서는 학습 환경과 동일하게 시간 필터 생략)
        if not context.metadata.get("is_backtest") and not self._is_trading_time(
            context.timestamp
        ):
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

        # action probability → confidence
        confidence = get_action_confidence(
            model, obs, action, action_masks, self._device
        )
        threshold = (
            self.config.backtest_min_confidence
            if context.metadata.get("is_backtest")
            else self.config.min_confidence
        )
        if confidence < threshold:
            logger.debug(
                f"RL action {action} confidence {confidence:.3f} "
                f"below threshold {threshold}"
            )
            return None

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
                    "rl_action": action,
                    "rl_confidence": confidence,
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
                    "rl_action": action,
                    "rl_confidence": confidence,
                },
            )

        return None

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

    def _is_trading_time(self, timestamp: datetime) -> bool:
        """거래 가능 시간 확인

        장 시작 후 skip_market_open_minutes, 장 마감 전 skip_market_close_minutes 제외
        """
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=KST)

        t = timestamp.time()
        from datetime import time

        # 장 시작: 09:00 + skip
        open_hour, open_min = 9, 0 + self.config.skip_market_open_minutes
        if open_min >= 60:
            open_hour += open_min // 60
            open_min = open_min % 60
        market_start = time(open_hour, open_min)

        # 장 마감: 15:45 - skip
        close_total = 15 * 60 + 45 - self.config.skip_market_close_minutes
        close_hour = close_total // 60
        close_min = close_total % 60
        market_end = time(close_hour, close_min)

        return market_start <= t <= market_end
