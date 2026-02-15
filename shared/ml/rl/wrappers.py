"""RL 환경 래퍼

연속 행동 공간 래퍼 (SAC용) 등 환경 변환 유틸리티.

Usage:
    from shared.ml.rl.wrappers import ContinuousActionWrapper
    env = ContinuousActionWrapper(base_env)
"""

from __future__ import annotations

import logging

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from shared.ml.rl.env import Action, PositionSide

logger = logging.getLogger(__name__)


class ContinuousActionWrapper(gym.Wrapper):
    """FuturesTradingEnv를 연속 행동 공간으로 변환하는 래퍼 (SAC용)

    연속 행동 [-1, 1]을 포지션 타겟으로 해석:
        action > entry_threshold  → LONG 진입 (flat일 때) 또는 SHORT 청산 (short일 때)
        action < -entry_threshold → SHORT 진입 (flat일 때) 또는 LONG 청산 (long일 때)
        |action| <= dead_zone     → HOLD (관망)

    SAC는 네이티브 action masking을 지원하지 않으므로,
    무효한 행동은 자동으로 HOLD로 대체됨 (base env에서 처리).

    Args:
        env: FuturesTradingEnv 인스턴스
        entry_threshold: 진입 임계값 (default 0.3)
        exit_threshold: 청산 임계값 (default 0.1)
    """

    def __init__(
        self,
        env: gym.Env,
        entry_threshold: float = 0.3,
        exit_threshold: float = 0.1,
    ):
        super().__init__(env)
        self.action_space = spaces.Box(
            low=-1.0, high=1.0, shape=(1,), dtype=np.float32
        )
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold

    def reset(self, *, seed=None, options=None):
        """Reset environment, compatible with FuturesTradingEnv signature."""
        return self.env.reset(seed=seed, options=options)

    def step(self, action: np.ndarray):
        continuous_val = float(np.clip(action[0], -1.0, 1.0))
        discrete_action = self._map_to_discrete(continuous_val)
        return self.env.step(discrete_action)

    def _map_to_discrete(self, action: float) -> int:
        """연속 행동을 이산 행동으로 변환

        포지션 상태에 따라 적절한 이산 행동을 선택.
        무효 행동(예: flat인데 EXIT)은 base env의 action_masks()에서
        자동으로 HOLD로 대체되므로, 여기서는 의미적 매핑만 수행.
        """
        position = self.env.position

        if position == PositionSide.FLAT:
            if action > self.entry_threshold:
                return Action.LONG_ENTRY
            elif action < -self.entry_threshold:
                return Action.SHORT_ENTRY
            return Action.HOLD

        elif position == PositionSide.LONG:
            if action < -self.exit_threshold:
                return Action.LONG_EXIT
            return Action.HOLD

        elif position == PositionSide.SHORT:
            if action > self.exit_threshold:
                return Action.SHORT_EXIT
            return Action.HOLD

        return Action.HOLD
