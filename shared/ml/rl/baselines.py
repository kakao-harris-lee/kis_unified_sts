"""MA-CROSS 베이스라인 전략

이동평균 교차 전략. RL 모델과의 성능 비교 기준선.
설정은 config/ml/rl_mppo.yaml의 ma_cross 섹션에서 로드.

Usage:
    baseline = MACrossBaseline()
    results = baseline.evaluate(test_days, test_prices)
"""

from __future__ import annotations

import copy
import logging
from typing import Any

import numpy as np

from shared.config import ConfigLoader
from shared.ml.rl.env import FuturesTradingEnv, RLEnvConfig, Action, PositionSide

logger = logging.getLogger(__name__)


class MACrossBaseline:
    """이동평균 교차 베이스라인

    단기 MA > 장기 MA → 롱 진입
    단기 MA < 장기 MA → 숏 진입
    """

    def __init__(self, config_path: str = "ml/rl_mppo.yaml"):
        config = ConfigLoader.load(config_path)
        ma_config = config.get("ma_cross", {})
        self.short_window = ma_config.get("short_window", 5)
        self.long_window = ma_config.get("long_window", 20)
        self._env_config = RLEnvConfig.from_yaml(config_path)

    def get_action(
        self,
        prices_so_far: np.ndarray,
        position: int,
    ) -> int:
        """현재 상태에서 MA 교차 행동 결정

        Args:
            prices_so_far: 현재까지의 종가 배열
            position: 현재 포지션 (0=flat, 1=long, -1=short)

        Returns:
            Action 값
        """
        if len(prices_so_far) < self.long_window:
            return Action.HOLD

        short_ma = np.mean(prices_so_far[-self.short_window :])
        long_ma = np.mean(prices_so_far[-self.long_window :])

        if short_ma > long_ma:
            # 골든 크로스
            if position == PositionSide.FLAT:
                return Action.LONG_ENTRY
            elif position == PositionSide.SHORT:
                return Action.SHORT_EXIT
        elif short_ma < long_ma:
            # 데드 크로스
            if position == PositionSide.FLAT:
                return Action.SHORT_ENTRY
            elif position == PositionSide.LONG:
                return Action.LONG_EXIT

        return Action.HOLD

    def evaluate(
        self,
        test_days: list[np.ndarray],
        test_prices: list[np.ndarray],
        slippage: float = 0.0,
    ) -> dict[str, float]:
        """MA-CROSS 백테스트 평가

        Args:
            test_days: 테스트 일별 피처 배열 리스트
            test_prices: 테스트 일별 OHLC 배열 리스트
            slippage: 슬리피지 값

        Returns:
            평가 지표 딕셔너리
        """
        config = copy.copy(self._env_config)
        config.slippage = slippage

        daily_returns = []
        total_trades = 0
        total_wins = 0
        gross_profit = 0.0
        gross_loss = 0.0

        for day_data, day_prices in zip(test_days, test_prices):
            env = FuturesTradingEnv(
                day_data=day_data, config=config, prices=day_prices
            )
            obs, info = env.reset()

            # 종가 히스토리 (MA 계산용)
            close_history: list[float] = []

            terminated = False
            while not terminated:
                current_price = day_prices[env.current_step, 3]  # close
                close_history.append(current_price)

                action = self.get_action(
                    np.array(close_history),
                    int(env.position),
                )

                obs, reward, terminated, truncated, info = env.step(action)

            daily_return = (
                (info["balance"] - config.initial_balance) / config.initial_balance
            )
            daily_returns.append(daily_return)
            total_trades += info["n_trades"]
            total_wins += env.wins

            for trade in env.trade_history:
                pnl = trade["pnl"]
                if pnl > 0:
                    gross_profit += pnl
                elif pnl < 0:
                    gross_loss += abs(pnl)

        avg_return = np.mean(daily_returns) * 100 if daily_returns else 0.0
        rr_ratio = gross_profit / gross_loss if gross_loss > 0 else float("inf")
        win_rate = (total_wins / max(total_trades, 1)) * 100

        return {
            "model": "MA-CROSS",
            "avg_return_pct": round(avg_return, 2),
            "rr_ratio": round(rr_ratio, 2),
            "win_rate_pct": round(win_rate, 1),
            "total_trades": total_trades,
            "slippage": slippage,
        }
