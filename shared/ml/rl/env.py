"""KOSPI200 선물 RL 환경

Gymnasium 커스텀 환경. 하루 1분봉 = 1 에피소드.
sb3-contrib ActionMasker와 호환되는 action_masks() 메서드 포함.

행동 공간 (Discrete 5):
    0: 롱 진입
    1: 롱 청산
    2: 숏 진입
    3: 숏 청산
    4: Hold (관망)

상태 공간 (Box):
    - 시장 피처 (25개): RLFeatureCalculator에서 생성
    - 포지션 피처 (3개): position, contracts, unrealized_pnl_normalized
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from shared.config import ConfigLoader

logger = logging.getLogger(__name__)


class Action(IntEnum):
    """RL 행동 정의"""

    LONG_ENTRY = 0
    LONG_EXIT = 1
    SHORT_ENTRY = 2
    SHORT_EXIT = 3
    HOLD = 4


class PositionSide(IntEnum):
    """포지션 방향"""

    FLAT = 0
    LONG = 1
    SHORT = -1


@dataclass
class RLEnvConfig:
    """환경 설정 - config/ml/rl_mppo.yaml에서 로드

    모든 값은 YAML config에서 로드. 하드코딩 금지.
    """

    # 환경
    initial_balance: float = 10_000_000
    commission_rate: float = 0.00003
    tick_size: float = 0.05
    tick_value: int = 250_000
    contract_multiplier: int = 250_000
    max_contracts: int = 1
    slippage: float = 0.0

    # 상태 공간
    n_market_features: int = 25
    n_position_features: int = 3

    # 장 운영시간
    market_open: str = "09:00"
    market_close: str = "15:45"

    # 보상함수 가중치
    w_profit: float = 1.0
    w_cost: float = 1.0
    w_risk: float = 0.5
    max_loss: float = -500_000
    loss_penalty_coeff: float = 2.0

    @classmethod
    def from_yaml(cls, path: str = "ml/rl_mppo.yaml") -> RLEnvConfig:
        """YAML 설정 파일에서 환경 설정 로드"""
        data = ConfigLoader.load(path)
        env_cfg = data.get("env", {})
        reward_cfg = data.get("reward", {})

        merged = {}
        for f in cls.__dataclass_fields__:
            if f in env_cfg:
                merged[f] = env_cfg[f]
            elif f in reward_cfg:
                merged[f] = reward_cfg[f]

        return cls(**merged)


class FuturesTradingEnv(gym.Env):
    """KOSPI200 선물 일중 매매 Gymnasium 환경

    에피소드 = 1 거래일 (1분봉 기준 ~405 스텝)
    보유 포지션은 장 마감 시 강제 청산.

    Usage:
        env = FuturesTradingEnv(day_data=features_array, config=config)
        obs, info = env.reset()
        for _ in range(max_steps):
            action = agent.predict(obs, action_masks=env.action_masks())
            obs, reward, terminated, truncated, info = env.step(action)
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        day_data: np.ndarray,
        config: RLEnvConfig | None = None,
        prices: np.ndarray | None = None,
    ):
        """
        Args:
            day_data: (n_steps, n_market_features) 정규화된 피처 배열
            config: 환경 설정. None이면 YAML에서 로드
            prices: (n_steps, 4) OHLC 원본 가격 (수익 계산용)
        """
        super().__init__()

        self.config = config or RLEnvConfig.from_yaml()
        self.day_data = day_data
        self.prices = prices  # (n_steps, 4): open, high, low, close

        n_features = self.config.n_market_features + self.config.n_position_features

        # 행동 공간: 5개 이산 행동
        self.action_space = spaces.Discrete(len(Action))

        # 관측 공간: 시장 피처 + 포지션 피처
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(n_features,), dtype=np.float32
        )

        # 상태 초기화
        self._reset_state()

    def _reset_state(self) -> None:
        """내부 상태 초기화"""
        self.current_step = 0
        self.balance = self.config.initial_balance
        self.position = PositionSide.FLAT
        self.contracts = 0
        self.entry_price = 0.0
        self.total_pnl = 0.0
        self.n_trades = 0
        self.wins = 0
        self.losses = 0
        self.trade_history: list[dict[str, Any]] = []

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        """환경 초기화 (에피소드 시작)"""
        super().reset(seed=seed)
        self._reset_state()

        obs = self._get_observation()
        info = self._get_info()
        return obs, info

    def step(
        self, action: int
    ) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        """1스텝 실행

        Args:
            action: Action enum 값 (0~4)

        Returns:
            observation, reward, terminated, truncated, info
        """
        action = Action(action)
        current_price = self._get_current_price()
        prev_balance = self.balance

        # 행동 실행
        trade_pnl = self._execute_action(action, current_price)

        # 보상 계산
        reward = self._calculate_reward(trade_pnl, current_price, prev_balance)

        # 다음 스텝
        self.current_step += 1

        # 종료 조건
        terminated = False
        truncated = False

        # 마지막 스텝: 강제 청산
        if self.current_step >= len(self.day_data) - 1:
            if self.position != PositionSide.FLAT:
                close_pnl = self._force_close(current_price)
                reward += self._calculate_reward(
                    close_pnl, current_price, self.balance - close_pnl
                )
            terminated = True

        # 최대 손실 초과
        if self.balance <= self.config.initial_balance + self.config.max_loss:
            if self.position != PositionSide.FLAT:
                self._force_close(current_price)
            terminated = True
            reward += self.config.max_loss * self.config.loss_penalty_coeff / (
                self.config.initial_balance
            )

        obs = self._get_observation()
        info = self._get_info()

        return obs, float(reward), terminated, truncated, info

    def action_masks(self) -> np.ndarray:
        """유효한 행동 마스크 반환

        sb3-contrib ActionMasker에서 사용.

        Returns:
            (5,) bool 배열. True = 유효한 행동
        """
        masks = np.zeros(len(Action), dtype=bool)

        # Hold는 항상 가능
        masks[Action.HOLD] = True

        if self.position == PositionSide.FLAT:
            # 포지션 없음 → 진입만 가능
            masks[Action.LONG_ENTRY] = True
            masks[Action.SHORT_ENTRY] = True
        elif self.position == PositionSide.LONG:
            # 롱 보유 → 롱 청산만 가능
            masks[Action.LONG_EXIT] = True
        elif self.position == PositionSide.SHORT:
            # 숏 보유 → 숏 청산만 가능
            masks[Action.SHORT_EXIT] = True

        return masks

    def _execute_action(self, action: Action, price: float) -> float:
        """행동 실행 및 거래 손익 반환

        무효한 행동은 Hold로 대체.

        Returns:
            이번 행동에 의한 실현 손익 (진입 시 0, 청산 시 실현 PnL)
        """
        masks = self.action_masks()

        # 무효한 행동 → Hold 대체
        if not masks[action]:
            return 0.0

        trade_pnl = 0.0

        if action == Action.LONG_ENTRY:
            exec_price = self._apply_slippage(price, is_buy=True)
            cost = exec_price * self.config.contract_multiplier * self.config.commission_rate
            self.position = PositionSide.LONG
            self.contracts = self.config.max_contracts
            self.entry_price = exec_price
            self.balance -= cost
            trade_pnl = -cost  # 진입 비용

        elif action == Action.LONG_EXIT:
            exec_price = self._apply_slippage(price, is_buy=False)
            cost = exec_price * self.config.contract_multiplier * self.config.commission_rate
            pnl = (
                (exec_price - self.entry_price)
                * self.config.contract_multiplier
                * self.contracts
            )
            trade_pnl = pnl - cost
            self.balance += trade_pnl
            self.total_pnl += trade_pnl
            self._record_trade(pnl=trade_pnl)
            self._clear_position()

        elif action == Action.SHORT_ENTRY:
            exec_price = self._apply_slippage(price, is_buy=False)
            cost = exec_price * self.config.contract_multiplier * self.config.commission_rate
            self.position = PositionSide.SHORT
            self.contracts = self.config.max_contracts
            self.entry_price = exec_price
            self.balance -= cost
            trade_pnl = -cost

        elif action == Action.SHORT_EXIT:
            exec_price = self._apply_slippage(price, is_buy=True)
            cost = exec_price * self.config.contract_multiplier * self.config.commission_rate
            pnl = (
                (self.entry_price - exec_price)
                * self.config.contract_multiplier
                * self.contracts
            )
            trade_pnl = pnl - cost
            self.balance += trade_pnl
            self.total_pnl += trade_pnl
            self._record_trade(pnl=trade_pnl)
            self._clear_position()

        return trade_pnl

    def _calculate_reward(
        self, trade_pnl: float, current_price: float, prev_balance: float
    ) -> float:
        """보상함수 (논문 식 2~5)

        R = w_profit * r_profit - w_cost * r_cost - w_risk * r_risk

        모든 가중치는 config에서 로드.
        """
        cfg = self.config

        # 수익 보상 (정규화)
        r_profit = trade_pnl / cfg.initial_balance

        # 비용 보상 (수수료)
        r_cost = abs(trade_pnl) * cfg.commission_rate / cfg.initial_balance if trade_pnl != 0 else 0.0

        # 리스크 보상 (미실현 손실)
        unrealized_pnl = self._get_unrealized_pnl(current_price)
        r_risk = max(0.0, -unrealized_pnl / cfg.initial_balance)

        reward = cfg.w_profit * r_profit - cfg.w_cost * r_cost - cfg.w_risk * r_risk

        return reward

    def _get_observation(self) -> np.ndarray:
        """현재 관측값 (시장 피처 + 포지션 피처)"""
        step = min(self.current_step, len(self.day_data) - 1)

        # 시장 피처 (25개)
        market_features = self.day_data[step].copy()

        # 포지션 피처 (3개)
        position_features = np.array(
            [
                float(self.position),  # -1, 0, 1
                float(self.contracts) / max(self.config.max_contracts, 1),
                self._get_unrealized_pnl(self._get_current_price())
                / self.config.initial_balance,
            ],
            dtype=np.float32,
        )

        obs = np.concatenate([market_features, position_features]).astype(np.float32)
        return obs

    def _get_current_price(self) -> float:
        """현재 종가 반환"""
        step = min(self.current_step, len(self.day_data) - 1)
        if self.prices is not None and step < len(self.prices):
            return float(self.prices[step, 3])  # close price
        return 0.0

    def _get_unrealized_pnl(self, current_price: float) -> float:
        """미실현 손익 계산"""
        if self.position == PositionSide.FLAT:
            return 0.0

        if self.position == PositionSide.LONG:
            return (
                (current_price - self.entry_price)
                * self.config.contract_multiplier
                * self.contracts
            )
        else:  # SHORT
            return (
                (self.entry_price - current_price)
                * self.config.contract_multiplier
                * self.contracts
            )

    def _apply_slippage(self, price: float, is_buy: bool) -> float:
        """슬리피지 적용 (불리한 방향)

        롱 진입/숏 청산: price + slippage * tick_size (비싸게)
        숏 진입/롱 청산: price - slippage * tick_size (싸게)
        """
        slip = self.config.slippage * self.config.tick_size
        if is_buy:
            return price + slip
        return price - slip

    def _force_close(self, price: float) -> float:
        """포지션 강제 청산 (장 마감)"""
        if self.position == PositionSide.LONG:
            return self._execute_action(Action.LONG_EXIT, price)
        elif self.position == PositionSide.SHORT:
            return self._execute_action(Action.SHORT_EXIT, price)
        return 0.0

    def _clear_position(self) -> None:
        """포지션 초기화"""
        self.position = PositionSide.FLAT
        self.contracts = 0
        self.entry_price = 0.0

    def _record_trade(self, pnl: float) -> None:
        """거래 기록"""
        self.n_trades += 1
        if pnl > 0:
            self.wins += 1
        elif pnl < 0:
            self.losses += 1

        self.trade_history.append(
            {
                "step": self.current_step,
                "pnl": pnl,
                "balance": self.balance,
                "position": int(self.position),
            }
        )

    def _get_info(self) -> dict[str, Any]:
        """추가 정보"""
        win_rate = self.wins / max(self.n_trades, 1)
        return {
            "balance": self.balance,
            "total_pnl": self.total_pnl,
            "n_trades": self.n_trades,
            "win_rate": win_rate,
            "position": int(self.position),
            "step": self.current_step,
        }


def mask_fn(env: FuturesTradingEnv) -> np.ndarray:
    """sb3-contrib ActionMasker 용 마스크 함수

    Usage:
        from sb3_contrib.common.wrappers import ActionMasker
        env = ActionMasker(env, mask_fn)
    """
    return env.action_masks()
