"""RL M-PPO 진입 전략

학습된 Maskable PPO 모델의 행동을 EntrySignalGenerator 인터페이스로 래핑.
StrategyFactory에서 YAML 설정으로 생성 가능.

Usage:
    strategy = StrategyFactory.create_from_file("futures", "rl_mppo")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional
from zoneinfo import ZoneInfo

from shared.ml.base import get_device
from shared.strategy.base import EntryContext, EntrySignalGenerator
from shared.strategy.registry import EntryRegistry

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
    min_confidence: float = 0.6
    skip_market_open_minutes: int = 5
    skip_market_close_minutes: int = 10


@EntryRegistry.register("rl_mppo")
class RLMPPOEntry(EntrySignalGenerator[RLMPPOConfig]):
    """학습된 M-PPO 모델 기반 진입 시그널 생성기

    학습된 Maskable PPO 모델을 로드하여 EntrySignalGenerator 인터페이스로 래핑.
    DLTrendEntry와 동일한 패턴으로 구현.

    행동 매핑:
        0 (LONG_ENTRY) → Signal(BUY)
        2 (SHORT_ENTRY) → Signal(SELL)
        기타 → None (진입 없음)
    """

    CONFIG_CLASS = RLMPPOConfig

    def __init__(self, config: RLMPPOConfig):
        super().__init__(config)
        self._model = None
        self._feature_calculator = None
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

        # 시간 필터
        if not self._is_trading_time(context.timestamp):
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
        confidence = self._get_action_confidence(model, obs, action, action_masks)
        if confidence < self.config.min_confidence:
            logger.debug(
                f"RL action {action} confidence {confidence:.3f} "
                f"below threshold {self.config.min_confidence}"
            )
            return None

        # 행동 → Signal 변환
        price = context.market_data.get("close", 0.0)
        code = context.market_data.get("code", "101S3000")

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
                    "direction": "short",
                    "rl_action": action,
                    "rl_confidence": confidence,
                },
            )

        return None

    def _get_env_config(self):
        """RL 환경 설정 로드 (lazy)"""
        if self._env_config is None:
            from shared.ml.rl.env import RLEnvConfig
            self._env_config = RLEnvConfig.from_yaml()
        return self._env_config

    def _load_model(self) -> Any:
        """학습된 모델 로드 (lazy loading)"""
        if self._model is not None:
            return self._model

        model_path = Path(self.config.model_path)
        if not model_path.exists():
            logger.error(f"RL model not found: {model_path}")
            return None

        try:
            from sb3_contrib import MaskablePPO

            self._model = MaskablePPO.load(
                str(model_path),
                device=self._device,
            )
            logger.info(f"RL model loaded: {model_path} (device={self._device})")
            return self._model
        except Exception as e:
            logger.error(f"Failed to load RL model: {e}")
            return None

    def _build_observation(self, context: EntryContext) -> Any:
        """EntryContext → RL 관측값 변환

        시장 피처 (25개) + 포지션 피처 (3개) = 28차원
        """
        import numpy as np

        indicators = context.indicators
        market_data = context.market_data

        # 시장 피처 (25개) - indicators에서 수집
        from shared.ml.rl.features import RL_FEATURE_COLUMNS

        market_features = []
        missing_features = []
        for col in RL_FEATURE_COLUMNS:
            val = indicators.get(col, market_data.get(col, None))
            if val is None:
                missing_features.append(col)
                market_features.append(0.0)
            else:
                market_features.append(float(val))

        if missing_features:
            logger.warning(
                f"Missing {len(missing_features)} RL features (filled with 0.0): "
                f"{missing_features[:5]}{'...' if len(missing_features) > 5 else ''}"
            )

        # 포지션 피처 (3개)
        position = 0.0  # flat (진입 판단이므로 항상 flat)
        contracts = 0.0
        unrealized_pnl = 0.0

        if context.current_positions:
            pos = context.current_positions[0]
            if hasattr(pos, "side"):
                position = 1.0 if pos.side == "long" else -1.0
            env_cfg = self._get_env_config()
            contracts = getattr(pos, "quantity", 0) / max(env_cfg.max_contracts, 1)
            unrealized_pnl = getattr(pos, "unrealized_pnl", 0.0) / env_cfg.initial_balance

        obs = np.array(
            market_features + [position, contracts, unrealized_pnl],
            dtype=np.float32,
        )

        return obs

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
            if side == "long":
                masks[1] = True  # LONG_EXIT
            elif side == "short":
                masks[3] = True  # SHORT_EXIT

        return masks

    def _get_action_confidence(
        self, model: Any, obs: Any, action: int, action_masks: Any
    ) -> float:
        """행동의 확률(confidence) 추출"""
        try:
            import numpy as np
            import torch

            obs_tensor = torch.as_tensor(obs).float().unsqueeze(0).to(self._device)
            with torch.no_grad():
                dist = model.policy.get_distribution(obs_tensor)
                probs = dist.distribution.probs.cpu().numpy()[0]
                return float(probs[action])
        except Exception as e:
            logger.debug(f"Failed to get action confidence: {e}")
            return 1.0  # 확률 추출 실패 시 기본값

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
