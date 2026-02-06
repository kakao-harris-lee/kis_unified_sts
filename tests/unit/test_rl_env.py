"""RL 환경 단위 테스트

FuturesTradingEnv의 핵심 동작을 검증:
- 관측 공간/행동 공간 shape
- action_masks 로직
- 보상 계산
- 포지션 전환
- 강제 청산
"""

from __future__ import annotations

import numpy as np
import pytest

from shared.ml.rl.env import (
    Action,
    FuturesTradingEnv,
    PositionSide,
    RLEnvConfig,
    mask_fn,
)


@pytest.fixture
def config() -> RLEnvConfig:
    """기본 테스트 설정"""
    return RLEnvConfig(
        initial_balance=10_000_000,
        commission_rate=0.00003,
        tick_size=0.05,
        tick_value=250_000,
        contract_multiplier=250_000,
        max_contracts=1,
        slippage=0.0,
        n_market_features=25,
        n_position_features=3,
        w_profit=1.0,
        w_cost=1.0,
        w_risk=0.5,
        max_loss=-500_000,
        loss_penalty_coeff=2.0,
    )


@pytest.fixture
def sample_data() -> tuple[np.ndarray, np.ndarray]:
    """샘플 데이터 (100 스텝)"""
    n_steps = 100
    n_features = 25

    np.random.seed(42)
    features = np.random.randn(n_steps, n_features).astype(np.float32)
    prices = np.zeros((n_steps, 4), dtype=np.float32)

    base_price = 350.0
    for i in range(n_steps):
        price = base_price + np.random.normal(0, 0.5)
        prices[i] = [
            price - 0.1,  # open
            price + 0.3,  # high
            price - 0.3,  # low
            price,         # close
        ]
        base_price = price

    return features, prices


@pytest.fixture
def env(config, sample_data) -> FuturesTradingEnv:
    """테스트 환경"""
    features, prices = sample_data
    return FuturesTradingEnv(day_data=features, config=config, prices=prices)


class TestObservationSpace:
    """관측 공간 테스트"""

    def test_observation_shape(self, env: FuturesTradingEnv):
        """관측값 shape = (28,): 25 시장 + 3 포지션"""
        obs, info = env.reset()
        assert obs.shape == (28,), f"Expected (28,), got {obs.shape}"

    def test_observation_dtype(self, env: FuturesTradingEnv):
        """관측값 dtype은 float32"""
        obs, _ = env.reset()
        assert obs.dtype == np.float32

    def test_initial_position_features(self, env: FuturesTradingEnv):
        """초기 포지션 피처 = [0, 0, 0]"""
        obs, _ = env.reset()
        position_features = obs[-3:]
        np.testing.assert_array_almost_equal(position_features, [0, 0, 0])


class TestActionSpace:
    """행동 공간 테스트"""

    def test_action_space_size(self, env: FuturesTradingEnv):
        """5개 이산 행동"""
        assert env.action_space.n == 5

    def test_action_enum_values(self):
        """Action enum 값 검증"""
        assert Action.LONG_ENTRY == 0
        assert Action.LONG_EXIT == 1
        assert Action.SHORT_ENTRY == 2
        assert Action.SHORT_EXIT == 3
        assert Action.HOLD == 4


class TestActionMasks:
    """행동 마스크 테스트"""

    def test_flat_position_masks(self, env: FuturesTradingEnv):
        """포지션 없으면: 진입 + Hold만 가능"""
        env.reset()
        masks = env.action_masks()

        assert masks[Action.LONG_ENTRY] is np.True_
        assert masks[Action.SHORT_ENTRY] is np.True_
        assert masks[Action.HOLD] is np.True_
        assert masks[Action.LONG_EXIT] is np.False_
        assert masks[Action.SHORT_EXIT] is np.False_

    def test_long_position_masks(self, env: FuturesTradingEnv):
        """롱 보유: 롱 청산 + Hold만 가능"""
        env.reset()
        env.step(Action.LONG_ENTRY)
        masks = env.action_masks()

        assert masks[Action.LONG_EXIT] is np.True_
        assert masks[Action.HOLD] is np.True_
        assert masks[Action.LONG_ENTRY] is np.False_
        assert masks[Action.SHORT_ENTRY] is np.False_
        assert masks[Action.SHORT_EXIT] is np.False_

    def test_short_position_masks(self, env: FuturesTradingEnv):
        """숏 보유: 숏 청산 + Hold만 가능"""
        env.reset()
        env.step(Action.SHORT_ENTRY)
        masks = env.action_masks()

        assert masks[Action.SHORT_EXIT] is np.True_
        assert masks[Action.HOLD] is np.True_
        assert masks[Action.LONG_ENTRY] is np.False_
        assert masks[Action.SHORT_ENTRY] is np.False_
        assert masks[Action.LONG_EXIT] is np.False_

    def test_mask_fn_compatibility(self, env: FuturesTradingEnv):
        """mask_fn은 env.action_masks()와 동일"""
        env.reset()
        expected = env.action_masks()
        actual = mask_fn(env)
        np.testing.assert_array_equal(actual, expected)


class TestPositionTransitions:
    """포지션 상태 전환 테스트"""

    def test_flat_to_long(self, env: FuturesTradingEnv):
        """Flat → Long 전환"""
        env.reset()
        env.step(Action.LONG_ENTRY)
        assert env.position == PositionSide.LONG
        assert env.contracts == env.config.max_contracts

    def test_long_to_flat(self, env: FuturesTradingEnv):
        """Long → Flat 전환"""
        env.reset()
        env.step(Action.LONG_ENTRY)
        env.step(Action.LONG_EXIT)
        assert env.position == PositionSide.FLAT
        assert env.contracts == 0

    def test_flat_to_short(self, env: FuturesTradingEnv):
        """Flat → Short 전환"""
        env.reset()
        env.step(Action.SHORT_ENTRY)
        assert env.position == PositionSide.SHORT
        assert env.contracts == env.config.max_contracts

    def test_short_to_flat(self, env: FuturesTradingEnv):
        """Short → Flat 전환"""
        env.reset()
        env.step(Action.SHORT_ENTRY)
        env.step(Action.SHORT_EXIT)
        assert env.position == PositionSide.FLAT
        assert env.contracts == 0

    def test_invalid_action_becomes_hold(self, env: FuturesTradingEnv):
        """무효 행동 → Hold (포지션 불변)"""
        env.reset()
        # Flat에서 LONG_EXIT 시도 → 무효
        obs, reward, _, _, _ = env.step(Action.LONG_EXIT)
        assert env.position == PositionSide.FLAT


class TestReward:
    """보상 함수 테스트"""

    def test_hold_zero_reward(self, env: FuturesTradingEnv):
        """Hold 행동 → 보상 ≈ 0"""
        env.reset()
        _, reward, _, _, _ = env.step(Action.HOLD)
        assert abs(reward) < 0.01, f"Hold reward should be ~0, got {reward}"

    def test_commission_cost(self, env: FuturesTradingEnv):
        """진입 시 수수료로 약간의 음수 보상"""
        env.reset()
        _, reward, _, _, _ = env.step(Action.LONG_ENTRY)
        # 수수료 비용이 있으므로 음수
        assert reward < 0, f"Entry should have negative reward due to commission, got {reward}"


class TestEpisodeTermination:
    """에피소드 종료 테스트"""

    def test_terminates_at_end(self, env: FuturesTradingEnv):
        """데이터 끝에서 에피소드 종료"""
        env.reset()
        terminated = False
        for _ in range(200):  # 100 스텝 데이터
            _, _, terminated, _, _ = env.step(Action.HOLD)
            if terminated:
                break
        assert terminated, "Episode should terminate at end of data"

    def test_force_close_at_end(self, env: FuturesTradingEnv):
        """마지막 스텝에서 포지션 강제 청산"""
        env.reset()
        env.step(Action.LONG_ENTRY)

        # 끝까지 Hold
        terminated = False
        for _ in range(200):
            _, _, terminated, _, info = env.step(Action.HOLD)
            if terminated:
                break

        assert terminated
        assert env.position == PositionSide.FLAT, "Position should be flat after episode end"

    def test_info_contains_metrics(self, env: FuturesTradingEnv):
        """info에 거래 통계 포함"""
        obs, info = env.reset()
        assert "balance" in info
        assert "total_pnl" in info
        assert "n_trades" in info
        assert "win_rate" in info
        assert "position" in info


class TestSlippage:
    """슬리피지 테스트"""

    def test_buy_slippage_unfavorable(self, config: RLEnvConfig, sample_data):
        """매수 슬리피지: 더 비싸게 체결"""
        config.slippage = 1.0  # 1 tick
        features, prices = sample_data
        env = FuturesTradingEnv(day_data=features, config=config, prices=prices)
        env.reset()

        base_price = prices[0, 3]  # close
        exec_price = env._apply_slippage(base_price, is_buy=True)
        assert exec_price > base_price, "Buy should execute at higher price with slippage"
        assert exec_price == base_price + config.tick_size

    def test_sell_slippage_unfavorable(self, config: RLEnvConfig, sample_data):
        """매도 슬리피지: 더 싸게 체결"""
        config.slippage = 1.0
        features, prices = sample_data
        env = FuturesTradingEnv(day_data=features, config=config, prices=prices)
        env.reset()

        base_price = prices[0, 3]
        exec_price = env._apply_slippage(base_price, is_buy=False)
        assert exec_price < base_price, "Sell should execute at lower price with slippage"
        assert exec_price == base_price - config.tick_size


class TestTradeHistory:
    """거래 기록 테스트"""

    def test_trade_recorded_on_close(self, env: FuturesTradingEnv):
        """청산 시 거래 기록"""
        env.reset()
        env.step(Action.LONG_ENTRY)
        env.step(Action.LONG_EXIT)

        assert env.n_trades == 1
        assert len(env.trade_history) == 1
        assert "pnl" in env.trade_history[0]
        assert "step" in env.trade_history[0]

    def test_win_loss_counting(self, env: FuturesTradingEnv):
        """승/패 카운트"""
        env.reset()
        env.step(Action.LONG_ENTRY)
        env.step(Action.LONG_EXIT)

        assert env.wins + env.losses == env.n_trades
