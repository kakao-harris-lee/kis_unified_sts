"""High-Level RL 환경 (15분봉)

15분봉 단위로 의사결정:
    - 시장 레짐 판정 (aggressive / neutral / defensive)
    - 리스크 예산 할당 (low_level이 사용할 max position scale)

행동 공간: Discrete(3)
    0: AGGRESSIVE — risk_budget=1.0 (풀 사이즈)
    1: NEUTRAL — risk_budget=0.5
    2: DEFENSIVE — risk_budget=0.0 (거래 금지)

관측 공간: 15분봉 기술적 피처 + 일중 PnL 요약

보상: 15분 간격 동안의 low-level PnL (위임된 수익)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

logger = logging.getLogger(__name__)


class HighLevelAction:
    """High-level 행동 상수"""

    AGGRESSIVE = 0
    NEUTRAL = 1
    DEFENSIVE = 2
    RISK_BUDGETS = {0: 1.0, 1: 0.5, 2: 0.0}
    NAMES = {0: "AGGRESSIVE", 1: "NEUTRAL", 2: "DEFENSIVE"}


@dataclass
class HighLevelConfig:
    """High-level 환경 설정"""

    n_bar_features: int = 25        # 15분봉 피처 수
    n_summary_features: int = 5     # PnL 요약 피처 수
    bars_per_step: int = 15         # 15분 = 15개 1분봉
    initial_balance: float = 100_000_000
    max_steps: int = 27             # 405분 / 15분 = 27 스텝


class HighLevelEnv(gym.Env):
    """High-Level 15분봉 환경

    에피소드 = 1 거래일.
    15분마다 레짐/리스크 결정 → low-level에 위임.
    보상 = low-level의 실현 PnL.

    Usage:
        env = HighLevelEnv(day_data_15m=features_15m, config=config)
        obs, info = env.reset()
        action = high_level_model.predict(obs)
        obs, reward, done, truncated, info = env.step(action)
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        day_data_15m: np.ndarray,
        config: HighLevelConfig | None = None,
        low_level_results: list[dict[str, float]] | None = None,
    ):
        """
        Args:
            day_data_15m: (n_steps_15m, n_features) 15분봉 피처
            config: 환경 설정
            low_level_results: 사전 계산된 low-level 결과 (학습 효율화용)
        """
        super().__init__()
        self.config = config or HighLevelConfig()
        self.day_data = day_data_15m
        self.low_level_results = low_level_results or []

        n_obs = self.config.n_bar_features + self.config.n_summary_features

        self.action_space = spaces.Discrete(3)
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(n_obs,), dtype=np.float32
        )

        self._reset_state()

    def _reset_state(self) -> None:
        self.current_step = 0
        self.total_pnl = 0.0
        self.cumulative_reward = 0.0
        self.n_trades = 0
        self.risk_budget_history: list[float] = []

    def reset(self, *, seed=None, _options=None):
        super().reset(seed=seed)
        self._reset_state()
        return self._get_observation(), self._get_info()

    def step(self, action: int):
        risk_budget = HighLevelAction.RISK_BUDGETS.get(action, 0.5)
        self.risk_budget_history.append(risk_budget)

        # low-level 결과에서 이 스텝의 PnL 가져오기
        step_pnl = 0.0
        if self.current_step < len(self.low_level_results):
            result = self.low_level_results[self.current_step]
            step_pnl = result.get("pnl", 0.0) * risk_budget
            self.n_trades += result.get("n_trades", 0)

        self.total_pnl += step_pnl
        reward = step_pnl / self.config.initial_balance * 100  # 정규화

        self.current_step += 1
        terminated = self.current_step >= min(
            len(self.day_data), self.config.max_steps
        )

        return self._get_observation(), float(reward), terminated, False, self._get_info()

    def _get_observation(self) -> np.ndarray:
        step = min(self.current_step, len(self.day_data) - 1)
        bar_features = self.day_data[step].copy()

        # PnL 요약 피처
        progress = self.current_step / max(self.config.max_steps, 1)
        pnl_norm = self.total_pnl / self.config.initial_balance
        avg_risk = (
            np.mean(self.risk_budget_history)
            if self.risk_budget_history
            else 0.5
        )
        summary = np.array(
            [
                progress,
                np.sin(2 * np.pi * progress),
                np.cos(2 * np.pi * progress),
                pnl_norm,
                avg_risk,
            ],
            dtype=np.float32,
        )

        return np.concatenate([bar_features, summary]).astype(np.float32)

    def _get_info(self) -> dict[str, Any]:
        return {
            "total_pnl": self.total_pnl,
            "n_trades": self.n_trades,
            "step": self.current_step,
            "risk_budget_history": self.risk_budget_history.copy(),
        }
