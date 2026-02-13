"""Low-Level RL 환경 (1분봉)

FuturesTradingEnv를 확장하여 high-level의 risk_budget을 반영.
risk_budget = 0이면 진입 불가 (HOLD만 허용).
risk_budget = 0.5이면 포지션 축소 진입.
risk_budget = 1.0이면 풀 사이즈 진입.

High-level이 15분마다 risk_budget을 업데이트.
"""

from __future__ import annotations

import logging

import numpy as np

from shared.ml.rl.env import Action, FuturesTradingEnv, PositionSide, RLEnvConfig

logger = logging.getLogger(__name__)


class LowLevelEnv(FuturesTradingEnv):
    """Low-Level 1분봉 환경 (High-level risk_budget 반영)

    FuturesTradingEnv 상속. risk_budget으로 행동 제약:
    - risk_budget = 0: 진입 불가, 기존 포지션 강제 청산
    - risk_budget = 0.5: 축소 진입 (max_contracts * 0.5)
    - risk_budget = 1.0: 풀 사이즈

    Usage:
        env = LowLevelEnv(day_data, config, prices)
        env.set_risk_budget(0.5)
        obs = env.reset()
    """

    def __init__(
        self,
        day_data: np.ndarray,
        config: RLEnvConfig | None = None,
        prices: np.ndarray | None = None,
    ):
        super().__init__(day_data=day_data, config=config, prices=prices)
        self._risk_budget = 1.0
        self._original_max_contracts = self.config.max_contracts

    def set_risk_budget(self, budget: float) -> None:
        """High-level에서 risk_budget 업데이트

        Args:
            budget: [0, 1] 범위. 0=거래금지, 1=풀사이즈
        """
        self._risk_budget = max(0.0, min(1.0, budget))

        # max_contracts 조정
        scaled = round(self._original_max_contracts * self._risk_budget)
        self.config.max_contracts = max(0, scaled)

    def action_masks(self) -> np.ndarray:
        """risk_budget 반영 행동 마스크"""
        masks = super().action_masks()

        # risk_budget = 0이면 진입 불가
        if self._risk_budget <= 0:
            masks[Action.LONG_ENTRY] = False
            masks[Action.SHORT_ENTRY] = False

        return masks

    def get_15min_segment_results(
        self,
        start_step: int,
        end_step: int,
    ) -> dict[str, float]:
        """특정 구간의 PnL/거래 요약

        High-level 학습 시 사용: 15분 구간의 low-level 결과 요약.

        Returns:
            {"pnl": float, "n_trades": int, "win_rate": float}
        """
        segment_trades = [
            t for t in self.trade_history
            if start_step <= t["step"] < end_step
        ]

        pnl = sum(t["pnl"] for t in segment_trades)
        n_trades = len(segment_trades)
        wins = sum(1 for t in segment_trades if t["pnl"] > 0)
        win_rate = wins / max(n_trades, 1)

        return {"pnl": pnl, "n_trades": n_trades, "win_rate": win_rate}
