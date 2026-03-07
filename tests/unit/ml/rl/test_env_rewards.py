"""RL 환경 보상 함수 단위 테스트

FuturesTradingEnv 보상 계산 컴포넌트 검증:
- 수익 컴포넌트 (r_profit): 실현 손익 정규화
- 비용 컴포넌트 (r_cost): 수수료 비용 정규화
- 리스크 컴포넌트 (r_risk): 미실현 손실 페널티
- MTM 컴포넌트 (r_mtm): 미실현 손익 변화
- 보상 스케일링 (reward_scale): 최종 보상 배율
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("gymnasium")

from shared.ml.rl.env import (
    Action,
    FuturesTradingEnv,
    PositionSide,
    RLEnvConfig,
)


@pytest.fixture
def config() -> RLEnvConfig:
    """기본 테스트 설정

    초기 잔고를 증거금보다 충분히 크게 설정하여 진입 가능하도록 함.
    price ~350, multiplier=250_000, margin_rate=0.15 → margin ~13.1M → balance=100M

    보상 가중치:
    - w_profit=1.0: 수익 컴포넌트 가중치
    - w_cost=1.0: 비용 컴포넌트 가중치
    - w_risk=0.5: 리스크 컴포넌트 가중치
    - w_mtm=0.0: MTM 컴포넌트 비활성
    - reward_scale=100.0: 최종 보상 스케일
    """
    return RLEnvConfig(
        initial_balance=100_000_000,
        commission_rate=0.00003,
        tick_size=0.05,
        tick_value=250_000,
        contract_multiplier=250_000,
        max_contracts=1,
        slippage=0.0,
        margin_rate=0.15,
        n_market_features=25,
        n_position_features=6,  # position(3) + time(3)
        w_profit=1.0,
        w_cost=1.0,
        w_risk=0.5,
        w_mtm=0.0,  # MTM 비활성
        inaction_penalty=0.0,
        reward_scale=100.0,
        max_loss=-50_000_000,
        loss_penalty_coeff=2.0,
    )


@pytest.fixture
def sample_data() -> tuple[np.ndarray, np.ndarray]:
    """샘플 데이터 (100 스텝)

    Returns:
        (features, prices) 튜플
        - features: (100, 25) 시장 피처
        - prices: (100, 4) OHLC 가격
    """
    n_steps = 100
    n_features = 25

    np.random.seed(42)
    features = np.random.randn(n_steps, n_features).astype(np.float32)
    prices = np.zeros((n_steps, 4), dtype=np.float32)

    # 안정적인 가격 생성
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
def env(config: RLEnvConfig, sample_data: tuple[np.ndarray, np.ndarray]) -> FuturesTradingEnv:
    """테스트 환경"""
    features, prices = sample_data
    return FuturesTradingEnv(day_data=features, config=config, prices=prices)


class TestProfitComponent:
    """수익 컴포넌트 (r_profit) 테스트

    r_profit = trade_pnl / initial_balance

    검증 사항:
    - 진입 시: trade_pnl = -commission (진입 비용)
    - 청산 시: trade_pnl = gross_pnl - commission (실현 손익 - 수수료)
    - Hold 시: trade_pnl = 0
    - 정규화: initial_balance로 나눔
    """

    def test_long_entry_has_negative_profit_from_commission(self, env: FuturesTradingEnv):
        """롱 진입: 수수료로 인한 음의 실현 손익"""
        env.reset()
        initial_price = env._get_current_price()

        # 롱 진입
        _, reward, _, _, info = env.step(Action.LONG_ENTRY)

        # 진입 비용 계산
        expected_cost = (
            initial_price * env.config.contract_multiplier * env.config.commission_rate
        )
        expected_trade_pnl = -expected_cost
        expected_r_profit = expected_trade_pnl / env.config.initial_balance

        # 보상 계산: r_profit 컴포넌트만 확인 (w_profit=1.0, reward_scale=100.0)
        # reward = (w_profit * r_profit - w_cost * r_cost - w_risk * r_risk) * reward_scale
        # 진입 시: r_cost = expected_cost / initial_balance, r_risk = 0 (아직 손실 없음)
        expected_r_cost = expected_cost / env.config.initial_balance
        expected_reward = (
            env.config.w_profit * expected_r_profit
            - env.config.w_cost * expected_r_cost
            - env.config.w_risk * 0.0
        ) * env.config.reward_scale

        # 진입 직후는 미실현 손익이 0이므로 r_risk=0
        assert reward == pytest.approx(expected_reward, rel=1e-6), (
            f"Long entry reward mismatch: expected {expected_reward}, got {reward}"
        )

        # 포지션 확인
        assert env.position == PositionSide.LONG
        assert env.contracts == env.config.max_contracts
        assert env.entry_price == pytest.approx(initial_price, rel=1e-6)

    def test_long_exit_with_profit(self, env: FuturesTradingEnv):
        """롱 청산 (수익): 양의 실현 손익 - 수수료"""
        env.reset()
        entry_price = env._get_current_price()

        # 롱 진입
        env.step(Action.LONG_ENTRY)

        # 가격 상승 시뮬레이션 (10 스텝 후)
        for _ in range(10):
            env.step(Action.HOLD)

        exit_price = env._get_current_price()

        # 가격이 상승했는지 확인 (샘플 데이터가 랜덤이므로 강제로 상승 케이스 생성)
        # exit_price가 entry_price보다 낮을 수 있으므로 직접 설정
        price_increase = 5.0  # 5 포인트 상승
        env.prices[env.current_step, 3] = entry_price + price_increase
        exit_price = env._get_current_price()

        # 롱 청산
        _, reward, _, _, info = env.step(Action.LONG_EXIT)

        # 실현 손익 계산
        gross_pnl = (
            (exit_price - entry_price)
            * env.config.contract_multiplier
            * env.config.max_contracts
        )
        exit_cost = exit_price * env.config.contract_multiplier * env.config.commission_rate
        expected_trade_pnl = gross_pnl - exit_cost
        expected_r_profit = expected_trade_pnl / env.config.initial_balance

        # 청산 시: r_cost = exit_cost / initial_balance, r_risk = 0 (포지션 없음)
        expected_r_cost = exit_cost / env.config.initial_balance
        expected_reward = (
            env.config.w_profit * expected_r_profit
            - env.config.w_cost * expected_r_cost
            - env.config.w_risk * 0.0
        ) * env.config.reward_scale

        assert expected_trade_pnl > 0, "Test setup error: trade should be profitable"
        assert reward == pytest.approx(expected_reward, rel=1e-5), (
            f"Long exit profit reward mismatch: expected {expected_reward}, got {reward}"
        )

        # 포지션 청산 확인
        assert env.position == PositionSide.FLAT
        assert env.contracts == 0

    def test_long_exit_with_loss(self, env: FuturesTradingEnv):
        """롱 청산 (손실): 음의 실현 손익 - 수수료"""
        env.reset()
        entry_price = env._get_current_price()

        # 롱 진입
        env.step(Action.LONG_ENTRY)

        # 가격 하락 시뮬레이션
        for _ in range(10):
            env.step(Action.HOLD)

        # 가격 하락 강제 설정
        price_decrease = 5.0  # 5 포인트 하락
        env.prices[env.current_step, 3] = entry_price - price_decrease
        exit_price = env._get_current_price()

        # 롱 청산
        _, reward, _, _, info = env.step(Action.LONG_EXIT)

        # 실현 손익 계산
        gross_pnl = (
            (exit_price - entry_price)
            * env.config.contract_multiplier
            * env.config.max_contracts
        )
        exit_cost = exit_price * env.config.contract_multiplier * env.config.commission_rate
        expected_trade_pnl = gross_pnl - exit_cost
        expected_r_profit = expected_trade_pnl / env.config.initial_balance

        # 청산 시: r_cost = exit_cost / initial_balance, r_risk = 0
        expected_r_cost = exit_cost / env.config.initial_balance
        expected_reward = (
            env.config.w_profit * expected_r_profit
            - env.config.w_cost * expected_r_cost
            - env.config.w_risk * 0.0
        ) * env.config.reward_scale

        assert expected_trade_pnl < 0, "Test setup error: trade should be losing"
        assert reward == pytest.approx(expected_reward, rel=1e-5), (
            f"Long exit loss reward mismatch: expected {expected_reward}, got {reward}"
        )

        # 포지션 청산 확인
        assert env.position == PositionSide.FLAT
        assert env.contracts == 0

    def test_short_entry_has_negative_profit_from_commission(self, env: FuturesTradingEnv):
        """숏 진입: 수수료로 인한 음의 실현 손익"""
        env.reset()
        initial_price = env._get_current_price()

        # 숏 진입
        _, reward, _, _, info = env.step(Action.SHORT_ENTRY)

        # 진입 비용 계산
        expected_cost = (
            initial_price * env.config.contract_multiplier * env.config.commission_rate
        )
        expected_trade_pnl = -expected_cost
        expected_r_profit = expected_trade_pnl / env.config.initial_balance

        # 보상 계산
        expected_r_cost = expected_cost / env.config.initial_balance
        expected_reward = (
            env.config.w_profit * expected_r_profit
            - env.config.w_cost * expected_r_cost
            - env.config.w_risk * 0.0
        ) * env.config.reward_scale

        assert reward == pytest.approx(expected_reward, rel=1e-6), (
            f"Short entry reward mismatch: expected {expected_reward}, got {reward}"
        )

        # 포지션 확인
        assert env.position == PositionSide.SHORT
        assert env.contracts == env.config.max_contracts
        assert env.entry_price == pytest.approx(initial_price, rel=1e-6)

    def test_short_exit_with_profit(self, env: FuturesTradingEnv):
        """숏 청산 (수익): 양의 실현 손익 - 수수료"""
        env.reset()
        entry_price = env._get_current_price()

        # 숏 진입
        env.step(Action.SHORT_ENTRY)

        # 가격 하락 시뮬레이션 (숏은 가격 하락 시 수익)
        for _ in range(10):
            env.step(Action.HOLD)

        # 가격 하락 강제 설정
        price_decrease = 5.0  # 5 포인트 하락
        env.prices[env.current_step, 3] = entry_price - price_decrease
        exit_price = env._get_current_price()

        # 숏 청산
        _, reward, _, _, info = env.step(Action.SHORT_EXIT)

        # 실현 손익 계산 (숏: entry_price - exit_price)
        gross_pnl = (
            (entry_price - exit_price)
            * env.config.contract_multiplier
            * env.config.max_contracts
        )
        exit_cost = exit_price * env.config.contract_multiplier * env.config.commission_rate
        expected_trade_pnl = gross_pnl - exit_cost
        expected_r_profit = expected_trade_pnl / env.config.initial_balance

        # 청산 시: r_cost = exit_cost / initial_balance, r_risk = 0
        expected_r_cost = exit_cost / env.config.initial_balance
        expected_reward = (
            env.config.w_profit * expected_r_profit
            - env.config.w_cost * expected_r_cost
            - env.config.w_risk * 0.0
        ) * env.config.reward_scale

        assert expected_trade_pnl > 0, "Test setup error: short trade should be profitable"
        assert reward == pytest.approx(expected_reward, rel=1e-5), (
            f"Short exit profit reward mismatch: expected {expected_reward}, got {reward}"
        )

        # 포지션 청산 확인
        assert env.position == PositionSide.FLAT
        assert env.contracts == 0

    def test_short_exit_with_loss(self, env: FuturesTradingEnv):
        """숏 청산 (손실): 음의 실현 손익 - 수수료"""
        env.reset()
        entry_price = env._get_current_price()

        # 숏 진입
        env.step(Action.SHORT_ENTRY)

        # 가격 상승 시뮬레이션 (숏은 가격 상승 시 손실)
        for _ in range(10):
            env.step(Action.HOLD)

        # 가격 상승 강제 설정
        price_increase = 5.0  # 5 포인트 상승
        env.prices[env.current_step, 3] = entry_price + price_increase
        exit_price = env._get_current_price()

        # 숏 청산
        _, reward, _, _, info = env.step(Action.SHORT_EXIT)

        # 실현 손익 계산 (숏: entry_price - exit_price)
        gross_pnl = (
            (entry_price - exit_price)
            * env.config.contract_multiplier
            * env.config.max_contracts
        )
        exit_cost = exit_price * env.config.contract_multiplier * env.config.commission_rate
        expected_trade_pnl = gross_pnl - exit_cost
        expected_r_profit = expected_trade_pnl / env.config.initial_balance

        # 청산 시: r_cost = exit_cost / initial_balance, r_risk = 0
        expected_r_cost = exit_cost / env.config.initial_balance
        expected_reward = (
            env.config.w_profit * expected_r_profit
            - env.config.w_cost * expected_r_cost
            - env.config.w_risk * 0.0
        ) * env.config.reward_scale

        assert expected_trade_pnl < 0, "Test setup error: short trade should be losing"
        assert reward == pytest.approx(expected_reward, rel=1e-5), (
            f"Short exit loss reward mismatch: expected {expected_reward}, got {reward}"
        )

        # 포지션 청산 확인
        assert env.position == PositionSide.FLAT
        assert env.contracts == 0

    def test_hold_action_has_zero_realized_profit(self, env: FuturesTradingEnv):
        """Hold 행동: 실현 손익 = 0"""
        env.reset()

        # Hold 행동
        _, reward, _, _, info = env.step(Action.HOLD)

        # Hold는 거래가 없으므로 trade_pnl = 0, trade_cost = 0
        # r_profit = 0, r_cost = 0, r_risk = 0 (포지션 없음)
        expected_reward = 0.0

        assert reward == pytest.approx(expected_reward, abs=1e-9), (
            f"Hold reward should be 0, got {reward}"
        )

        # 포지션 없음 확인
        assert env.position == PositionSide.FLAT
        assert env.contracts == 0

    def test_hold_while_holding_position_has_zero_realized_profit(self, env: FuturesTradingEnv):
        """포지션 보유 중 Hold: 실현 손익 = 0 (미실현 손익은 r_risk에 반영)"""
        env.reset()
        entry_price = env._get_current_price()

        # 롱 진입
        env.step(Action.LONG_ENTRY)

        # 가격 변동 후 Hold
        for _ in range(5):
            env.step(Action.HOLD)

        # 가격 하락 시뮬레이션 (미실현 손실 발생)
        price_decrease = 3.0
        env.prices[env.current_step, 3] = entry_price - price_decrease
        current_price = env._get_current_price()

        # Hold 행동
        _, reward, _, _, info = env.step(Action.HOLD)

        # Hold는 거래 없음: trade_pnl = 0, trade_cost = 0
        # 하지만 미실현 손실이 있으므로 r_risk > 0
        unrealized_pnl = (
            (current_price - entry_price)
            * env.config.contract_multiplier
            * env.config.max_contracts
        )
        expected_r_risk = max(0.0, -unrealized_pnl / env.config.initial_balance)
        expected_reward = (
            env.config.w_profit * 0.0
            - env.config.w_cost * 0.0
            - env.config.w_risk * expected_r_risk
        ) * env.config.reward_scale

        assert unrealized_pnl < 0, "Test setup error: should have unrealized loss"
        assert reward == pytest.approx(expected_reward, rel=1e-5), (
            f"Hold with position reward mismatch: expected {expected_reward}, got {reward}"
        )

        # 포지션 유지 확인
        assert env.position == PositionSide.LONG
        assert env.contracts == env.config.max_contracts

    def test_profit_normalization_by_initial_balance(self, env: FuturesTradingEnv):
        """실현 손익은 초기 잔고로 정규화됨"""
        env.reset()
        entry_price = env._get_current_price()

        # 롱 진입 후 청산
        env.step(Action.LONG_ENTRY)
        for _ in range(10):
            env.step(Action.HOLD)

        # 고정 가격 설정
        price_increase = 10.0
        env.prices[env.current_step, 3] = entry_price + price_increase
        exit_price = env._get_current_price()

        # 청산
        _, reward, _, _, info = env.step(Action.LONG_EXIT)

        # 실현 손익 계산
        gross_pnl = (
            (exit_price - entry_price)
            * env.config.contract_multiplier
            * env.config.max_contracts
        )
        exit_cost = exit_price * env.config.contract_multiplier * env.config.commission_rate
        trade_pnl = gross_pnl - exit_cost

        # 정규화된 수익
        normalized_profit = trade_pnl / env.config.initial_balance

        # normalized_profit이 보상 계산에 사용됨
        expected_r_cost = exit_cost / env.config.initial_balance
        expected_reward = (
            env.config.w_profit * normalized_profit
            - env.config.w_cost * expected_r_cost
            - env.config.w_risk * 0.0
        ) * env.config.reward_scale

        assert reward == pytest.approx(expected_reward, rel=1e-5), (
            f"Normalized reward mismatch: expected {expected_reward}, got {reward}"
        )

        # 정규화 값 범위 확인 (일반적으로 |normalized_profit| < 0.1)
        assert abs(normalized_profit) < 0.5, (
            f"Normalized profit seems too large: {normalized_profit}"
        )

    def test_reward_scaling_multiplier(self, env: FuturesTradingEnv, sample_data: tuple[np.ndarray, np.ndarray]):
        """보상 스케일링: reward_scale 배율 적용 확인"""
        # reward_scale을 10.0으로 변경한 환경 생성
        config_low_scale = RLEnvConfig(
            initial_balance=100_000_000,
            commission_rate=0.00003,
            tick_size=0.05,
            tick_value=250_000,
            contract_multiplier=250_000,
            max_contracts=1,
            slippage=0.0,
            margin_rate=0.15,
            n_market_features=25,
            n_position_features=6,
            w_profit=1.0,
            w_cost=1.0,
            w_risk=0.5,
            w_mtm=0.0,
            reward_scale=10.0,  # 낮은 스케일
            max_loss=-50_000_000,
            loss_penalty_coeff=2.0,
        )

        # 동일한 데이터로 두 환경 생성
        features, prices = sample_data
        env1 = FuturesTradingEnv(day_data=features, config=env.config, prices=prices)  # scale=100
        env2 = FuturesTradingEnv(day_data=features, config=config_low_scale, prices=prices)  # scale=10

        # 동일한 행동 시퀀스 실행
        env1.reset()
        env2.reset()

        _, reward1, _, _, _ = env1.step(Action.LONG_ENTRY)
        _, reward2, _, _, _ = env2.step(Action.LONG_ENTRY)

        # 보상 비율은 scale 비율과 동일해야 함
        expected_ratio = env.config.reward_scale / config_low_scale.reward_scale  # 100 / 10 = 10
        actual_ratio = reward1 / reward2 if reward2 != 0 else 0

        assert actual_ratio == pytest.approx(expected_ratio, rel=1e-5), (
            f"Reward scaling ratio mismatch: expected {expected_ratio}, got {actual_ratio}"
        )

    def test_commission_is_deducted_from_profit(self, env: FuturesTradingEnv):
        """수수료는 실현 손익에서 차감됨"""
        env.reset()
        entry_price = env._get_current_price()

        # 롱 진입
        env.step(Action.LONG_ENTRY)
        entry_cost = entry_price * env.config.contract_multiplier * env.config.commission_rate

        # 가격 변동 후 청산
        for _ in range(10):
            env.step(Action.HOLD)

        price_increase = 10.0
        env.prices[env.current_step, 3] = entry_price + price_increase
        exit_price = env._get_current_price()

        # 청산
        prev_total_pnl = env.total_pnl
        _, reward, _, _, info = env.step(Action.LONG_EXIT)

        # 총 실현 손익 확인
        gross_pnl = (
            (exit_price - entry_price)
            * env.config.contract_multiplier
            * env.config.max_contracts
        )
        exit_cost = exit_price * env.config.contract_multiplier * env.config.commission_rate

        # total_pnl은 진입 비용(-entry_cost)와 청산 손익(gross_pnl - exit_cost)의 합
        expected_total_pnl = -entry_cost + (gross_pnl - exit_cost)

        assert env.total_pnl == pytest.approx(expected_total_pnl, rel=1e-5), (
            f"Total PnL mismatch: expected {expected_total_pnl}, got {env.total_pnl}"
        )

        # 수수료가 차감되었는지 확인 (gross_pnl보다 작아야 함)
        net_pnl = env.total_pnl + entry_cost  # 진입 비용 제거하여 청산 손익만 확인
        assert net_pnl < gross_pnl, (
            f"Net PnL should be less than gross PnL due to commission: "
            f"net={net_pnl}, gross={gross_pnl}"
        )

        # 차감된 금액이 exit_cost와 일치
        commission_deducted = gross_pnl - net_pnl
        assert commission_deducted == pytest.approx(exit_cost, rel=1e-5), (
            f"Commission deducted mismatch: expected {exit_cost}, got {commission_deducted}"
        )

    def test_multiple_trades_accumulate_profit(self, env: FuturesTradingEnv):
        """여러 거래의 실현 손익이 누적됨"""
        env.reset()

        # 첫 번째 거래: 롱 진입 후 수익 청산
        entry_price_1 = env._get_current_price()
        env.step(Action.LONG_ENTRY)

        for _ in range(5):
            env.step(Action.HOLD)

        env.prices[env.current_step, 3] = entry_price_1 + 5.0
        env.step(Action.LONG_EXIT)

        total_pnl_after_first_trade = env.total_pnl

        # 두 번째 거래: 숏 진입 후 수익 청산
        for _ in range(5):
            env.step(Action.HOLD)

        entry_price_2 = env._get_current_price()
        env.step(Action.SHORT_ENTRY)

        for _ in range(5):
            env.step(Action.HOLD)

        env.prices[env.current_step, 3] = entry_price_2 - 5.0
        env.step(Action.SHORT_EXIT)

        total_pnl_after_second_trade = env.total_pnl

        # 두 번째 거래의 손익이 첫 번째에 누적됨
        assert total_pnl_after_second_trade > total_pnl_after_first_trade, (
            "Second profitable trade should increase total PnL"
        )

        # 거래 횟수 확인
        assert env.n_trades == 2, f"Expected 2 trades, got {env.n_trades}"

    def test_profit_calculation_with_max_contracts(self, env: FuturesTradingEnv, sample_data: tuple[np.ndarray, np.ndarray]):
        """최대 계약 수량으로 손익 계산 확인"""
        # max_contracts=2로 설정한 환경
        config_multi = RLEnvConfig(
            initial_balance=200_000_000,  # 증거금 여유 확보
            commission_rate=0.00003,
            tick_size=0.05,
            tick_value=250_000,
            contract_multiplier=250_000,
            max_contracts=2,  # 2계약
            slippage=0.0,
            margin_rate=0.15,
            n_market_features=25,
            n_position_features=6,
            w_profit=1.0,
            w_cost=1.0,
            w_risk=0.5,
            w_mtm=0.0,
            reward_scale=100.0,
            max_loss=-50_000_000,
            loss_penalty_coeff=2.0,
        )

        features, prices = sample_data
        env_multi = FuturesTradingEnv(day_data=features, config=config_multi, prices=prices)

        env_multi.reset()
        entry_price = env_multi._get_current_price()

        # 롱 진입 (2계약)
        env_multi.step(Action.LONG_ENTRY)

        assert env_multi.contracts == 2

        # 가격 상승 후 청산
        for _ in range(10):
            env_multi.step(Action.HOLD)

        price_increase = 5.0
        env_multi.prices[env_multi.current_step, 3] = entry_price + price_increase
        exit_price = env_multi._get_current_price()

        env_multi.step(Action.LONG_EXIT)

        # 손익 계산 (2계약)
        expected_gross_pnl = (
            (exit_price - entry_price)
            * config_multi.contract_multiplier
            * 2  # 2계약
        )

        # 실제 손익은 수수료 차감 후
        entry_cost = entry_price * config_multi.contract_multiplier * config_multi.commission_rate * 2
        exit_cost = exit_price * config_multi.contract_multiplier * config_multi.commission_rate * 2
        expected_total_pnl = expected_gross_pnl - entry_cost - exit_cost

        assert env_multi.total_pnl == pytest.approx(expected_total_pnl, rel=1e-5), (
            f"Multi-contract PnL mismatch: expected {expected_total_pnl}, got {env_multi.total_pnl}"
        )


class TestCostComponent:
    """비용 컴포넌트 (r_cost) 테스트

    r_cost = trade_cost / initial_balance
    trade_cost = commission + slippage_cost

    검증 사항:
    - 진입 시: commission = price * multiplier * commission_rate
    - 청산 시: commission = price * multiplier * commission_rate
    - 슬리피지: slippage_cost = price * multiplier * slippage
    - Hold 시: trade_cost = 0
    - 정규화: initial_balance로 나눔
    """

    def test_long_entry_commission_cost(self, env: FuturesTradingEnv):
        """롱 진입: 수수료 비용 계산"""
        env.reset()
        entry_price = env._get_current_price()

        # 롱 진입
        _, reward, _, _, info = env.step(Action.LONG_ENTRY)

        # 진입 비용 계산
        expected_commission = (
            entry_price * env.config.contract_multiplier * env.config.commission_rate
        )
        expected_slippage = entry_price * env.config.contract_multiplier * env.config.slippage
        expected_cost = expected_commission + expected_slippage
        expected_r_cost = expected_cost / env.config.initial_balance

        # 슬리피지가 0이므로 비용은 수수료만
        assert env.config.slippage == 0.0, "Test assumes slippage=0"
        assert expected_cost == expected_commission

        # r_cost 검증 (보상 계산에 사용됨)
        # reward = (w_profit * r_profit - w_cost * r_cost - w_risk * r_risk) * reward_scale
        # 진입 시: r_profit = -expected_cost / initial_balance (수수료 차감)
        expected_r_profit = -expected_cost / env.config.initial_balance
        expected_reward = (
            env.config.w_profit * expected_r_profit
            - env.config.w_cost * expected_r_cost
            - env.config.w_risk * 0.0
        ) * env.config.reward_scale

        assert reward == pytest.approx(expected_reward, rel=1e-6), (
            f"Long entry cost reward mismatch: expected {expected_reward}, got {reward}"
        )

        # 포지션 확인
        assert env.position == PositionSide.LONG
        assert env.contracts == env.config.max_contracts

    def test_short_entry_commission_cost(self, env: FuturesTradingEnv):
        """숏 진입: 수수료 비용 계산"""
        env.reset()
        entry_price = env._get_current_price()

        # 숏 진입
        _, reward, _, _, info = env.step(Action.SHORT_ENTRY)

        # 진입 비용 계산
        expected_commission = (
            entry_price * env.config.contract_multiplier * env.config.commission_rate
        )
        expected_cost = expected_commission  # slippage=0
        expected_r_cost = expected_cost / env.config.initial_balance

        # r_cost 검증
        expected_r_profit = -expected_cost / env.config.initial_balance
        expected_reward = (
            env.config.w_profit * expected_r_profit
            - env.config.w_cost * expected_r_cost
            - env.config.w_risk * 0.0
        ) * env.config.reward_scale

        assert reward == pytest.approx(expected_reward, rel=1e-6), (
            f"Short entry cost reward mismatch: expected {expected_reward}, got {reward}"
        )

        # 포지션 확인
        assert env.position == PositionSide.SHORT
        assert env.contracts == env.config.max_contracts

    def test_long_exit_commission_cost(self, env: FuturesTradingEnv):
        """롱 청산: 수수료 비용 계산"""
        env.reset()
        entry_price = env._get_current_price()

        # 롱 진입
        env.step(Action.LONG_ENTRY)

        # 가격 변동 후 청산
        for _ in range(10):
            env.step(Action.HOLD)

        exit_price = env._get_current_price()

        # 롱 청산
        _, reward, _, _, info = env.step(Action.LONG_EXIT)

        # 청산 비용 계산
        expected_exit_commission = (
            exit_price * env.config.contract_multiplier * env.config.commission_rate
        )
        expected_exit_cost = expected_exit_commission  # slippage=0
        expected_r_cost = expected_exit_cost / env.config.initial_balance

        # 실현 손익 계산
        gross_pnl = (
            (exit_price - entry_price)
            * env.config.contract_multiplier
            * env.config.max_contracts
        )
        trade_pnl = gross_pnl - expected_exit_cost
        expected_r_profit = trade_pnl / env.config.initial_balance

        # 보상 검증
        expected_reward = (
            env.config.w_profit * expected_r_profit
            - env.config.w_cost * expected_r_cost
            - env.config.w_risk * 0.0
        ) * env.config.reward_scale

        assert reward == pytest.approx(expected_reward, rel=1e-5), (
            f"Long exit cost reward mismatch: expected {expected_reward}, got {reward}"
        )

        # 포지션 청산 확인
        assert env.position == PositionSide.FLAT
        assert env.contracts == 0

    def test_short_exit_commission_cost(self, env: FuturesTradingEnv):
        """숏 청산: 수수료 비용 계산"""
        env.reset()
        entry_price = env._get_current_price()

        # 숏 진입
        env.step(Action.SHORT_ENTRY)

        # 가격 변동 후 청산
        for _ in range(10):
            env.step(Action.HOLD)

        exit_price = env._get_current_price()

        # 숏 청산
        _, reward, _, _, info = env.step(Action.SHORT_EXIT)

        # 청산 비용 계산
        expected_exit_commission = (
            exit_price * env.config.contract_multiplier * env.config.commission_rate
        )
        expected_exit_cost = expected_exit_commission  # slippage=0
        expected_r_cost = expected_exit_cost / env.config.initial_balance

        # 실현 손익 계산 (숏: entry_price - exit_price)
        gross_pnl = (
            (entry_price - exit_price)
            * env.config.contract_multiplier
            * env.config.max_contracts
        )
        trade_pnl = gross_pnl - expected_exit_cost
        expected_r_profit = trade_pnl / env.config.initial_balance

        # 보상 검증
        expected_reward = (
            env.config.w_profit * expected_r_profit
            - env.config.w_cost * expected_r_cost
            - env.config.w_risk * 0.0
        ) * env.config.reward_scale

        assert reward == pytest.approx(expected_reward, rel=1e-5), (
            f"Short exit cost reward mismatch: expected {expected_reward}, got {reward}"
        )

        # 포지션 청산 확인
        assert env.position == PositionSide.FLAT
        assert env.contracts == 0

    def test_hold_action_has_zero_cost(self, env: FuturesTradingEnv):
        """Hold 행동: 거래 비용 = 0"""
        env.reset()

        # Hold 행동
        _, reward, _, _, info = env.step(Action.HOLD)

        # Hold는 거래 없음: trade_cost = 0, r_cost = 0
        # r_profit = 0, r_risk = 0 (포지션 없음)
        expected_reward = 0.0

        assert reward == pytest.approx(expected_reward, abs=1e-9), (
            f"Hold reward should be 0 (no cost), got {reward}"
        )

        # 포지션 없음 확인
        assert env.position == PositionSide.FLAT
        assert env.contracts == 0

    def test_hold_while_holding_position_has_zero_cost(self, env: FuturesTradingEnv):
        """포지션 보유 중 Hold: 거래 비용 = 0"""
        env.reset()

        # 롱 진입
        env.step(Action.LONG_ENTRY)

        # Hold 행동
        _, reward, _, _, info = env.step(Action.HOLD)

        # Hold는 거래 없음: trade_cost = 0, r_cost = 0
        # r_profit = 0, r_risk는 미실현 손익에 따라 달라짐
        # 진입 직후 가격 변동이 없으면 r_risk ≈ 0
        expected_reward = (
            env.config.w_profit * 0.0
            - env.config.w_cost * 0.0
            - env.config.w_risk * 0.0  # 가격 변동 없음
        ) * env.config.reward_scale

        # 보상이 0에 가까워야 함 (미세한 가격 변동은 허용)
        assert abs(reward) < 1.0, (
            f"Hold reward should be near 0 (no cost), got {reward}"
        )

        # 포지션 유지 확인
        assert env.position == PositionSide.LONG
        assert env.contracts == env.config.max_contracts

    def test_slippage_cost_on_entry(self, env: FuturesTradingEnv, sample_data: tuple[np.ndarray, np.ndarray]):
        """슬리피지가 있는 경우 진입 비용 = 수수료 + 슬리피지"""
        # slippage=0.1 (10 틱)로 설정한 환경
        config_with_slippage = RLEnvConfig(
            initial_balance=100_000_000,
            commission_rate=0.00003,
            tick_size=0.05,
            tick_value=250_000,
            contract_multiplier=250_000,
            max_contracts=1,
            slippage=0.1,  # 슬리피지 설정
            margin_rate=0.15,
            n_market_features=25,
            n_position_features=6,
            w_profit=1.0,
            w_cost=1.0,
            w_risk=0.5,
            w_mtm=0.0,
            reward_scale=100.0,
            max_loss=-50_000_000,
            loss_penalty_coeff=2.0,
        )

        features, prices = sample_data
        env_slip = FuturesTradingEnv(day_data=features, config=config_with_slippage, prices=prices)

        env_slip.reset()
        entry_price = env_slip._get_current_price()

        # 롱 진입
        _, reward, _, _, info = env_slip.step(Action.LONG_ENTRY)

        # 진입 비용 = 수수료 + 슬리피지
        expected_commission = (
            entry_price * config_with_slippage.contract_multiplier * config_with_slippage.commission_rate
        )
        expected_slippage = (
            entry_price * config_with_slippage.contract_multiplier * config_with_slippage.slippage
        )
        expected_total_cost = expected_commission + expected_slippage
        expected_r_cost = expected_total_cost / config_with_slippage.initial_balance

        # 슬리피지가 포함되었는지 확인
        assert expected_slippage > 0, "Test setup error: slippage should be > 0"
        assert expected_total_cost > expected_commission, (
            "Total cost should be greater than commission due to slippage"
        )

        # 보상 검증
        expected_r_profit = -expected_total_cost / config_with_slippage.initial_balance
        expected_reward = (
            config_with_slippage.w_profit * expected_r_profit
            - config_with_slippage.w_cost * expected_r_cost
            - config_with_slippage.w_risk * 0.0
        ) * config_with_slippage.reward_scale

        assert reward == pytest.approx(expected_reward, rel=1e-6), (
            f"Entry with slippage reward mismatch: expected {expected_reward}, got {reward}"
        )

    def test_slippage_cost_on_exit(self, env: FuturesTradingEnv, sample_data: tuple[np.ndarray, np.ndarray]):
        """슬리피지가 있는 경우 청산 비용 = 수수료 + 슬리피지"""
        # slippage=0.1로 설정한 환경
        config_with_slippage = RLEnvConfig(
            initial_balance=100_000_000,
            commission_rate=0.00003,
            tick_size=0.05,
            tick_value=250_000,
            contract_multiplier=250_000,
            max_contracts=1,
            slippage=0.1,  # 슬리피지 설정
            margin_rate=0.15,
            n_market_features=25,
            n_position_features=6,
            w_profit=1.0,
            w_cost=1.0,
            w_risk=0.5,
            w_mtm=0.0,
            reward_scale=100.0,
            max_loss=-50_000_000,
            loss_penalty_coeff=2.0,
        )

        features, prices = sample_data
        env_slip = FuturesTradingEnv(day_data=features, config=config_with_slippage, prices=prices)

        env_slip.reset()
        entry_price = env_slip._get_current_price()

        # 롱 진입
        env_slip.step(Action.LONG_ENTRY)

        # 가격 변동 후 청산
        for _ in range(10):
            env_slip.step(Action.HOLD)

        # 가격 상승 설정
        env_slip.prices[env_slip.current_step, 3] = entry_price + 5.0
        exit_price = env_slip._get_current_price()

        # 롱 청산
        _, reward, _, _, info = env_slip.step(Action.LONG_EXIT)

        # 청산 비용 = 수수료 + 슬리피지
        expected_exit_commission = (
            exit_price * config_with_slippage.contract_multiplier * config_with_slippage.commission_rate
        )
        expected_exit_slippage = (
            exit_price * config_with_slippage.contract_multiplier * config_with_slippage.slippage
        )
        expected_exit_cost = expected_exit_commission + expected_exit_slippage
        expected_r_cost = expected_exit_cost / config_with_slippage.initial_balance

        # 슬리피지가 포함되었는지 확인
        assert expected_exit_slippage > 0, "Test setup error: exit slippage should be > 0"
        assert expected_exit_cost > expected_exit_commission, (
            "Exit cost should be greater than commission due to slippage"
        )

        # 실현 손익 계산
        gross_pnl = (
            (exit_price - entry_price)
            * config_with_slippage.contract_multiplier
            * config_with_slippage.max_contracts
        )
        trade_pnl = gross_pnl - expected_exit_cost
        expected_r_profit = trade_pnl / config_with_slippage.initial_balance

        # 보상 검증
        expected_reward = (
            config_with_slippage.w_profit * expected_r_profit
            - config_with_slippage.w_cost * expected_r_cost
            - config_with_slippage.w_risk * 0.0
        ) * config_with_slippage.reward_scale

        assert reward == pytest.approx(expected_reward, rel=1e-5), (
            f"Exit with slippage reward mismatch: expected {expected_reward}, got {reward}"
        )

    def test_cost_normalization_by_initial_balance(self, env: FuturesTradingEnv):
        """거래 비용은 초기 잔고로 정규화됨"""
        env.reset()
        entry_price = env._get_current_price()

        # 롱 진입
        _, reward, _, _, info = env.step(Action.LONG_ENTRY)

        # 진입 비용 계산
        entry_cost = entry_price * env.config.contract_multiplier * env.config.commission_rate
        normalized_cost = entry_cost / env.config.initial_balance

        # 정규화된 비용이 보상 계산에 사용됨
        expected_r_cost = normalized_cost
        expected_r_profit = -entry_cost / env.config.initial_balance
        expected_reward = (
            env.config.w_profit * expected_r_profit
            - env.config.w_cost * expected_r_cost
            - env.config.w_risk * 0.0
        ) * env.config.reward_scale

        assert reward == pytest.approx(expected_reward, rel=1e-6), (
            f"Normalized cost reward mismatch: expected {expected_reward}, got {reward}"
        )

        # 정규화 값 범위 확인 (일반적으로 normalized_cost < 0.001)
        assert normalized_cost < 0.01, (
            f"Normalized cost seems too large: {normalized_cost}"
        )

    def test_cost_scales_with_contract_size(self, env: FuturesTradingEnv, sample_data: tuple[np.ndarray, np.ndarray]):
        """비용은 계약 수량에 비례함"""
        # max_contracts=2로 설정한 환경
        config_multi = RLEnvConfig(
            initial_balance=200_000_000,  # 증거금 여유 확보
            commission_rate=0.00003,
            tick_size=0.05,
            tick_value=250_000,
            contract_multiplier=250_000,
            max_contracts=2,  # 2계약
            slippage=0.0,
            margin_rate=0.15,
            n_market_features=25,
            n_position_features=6,
            w_profit=1.0,
            w_cost=1.0,
            w_risk=0.5,
            w_mtm=0.0,
            reward_scale=100.0,
            max_loss=-50_000_000,
            loss_penalty_coeff=2.0,
        )

        features, prices = sample_data
        env_multi = FuturesTradingEnv(day_data=features, config=config_multi, prices=prices)

        env_multi.reset()
        entry_price = env_multi._get_current_price()

        # 롱 진입 (2계약)
        _, reward, _, _, info = env_multi.step(Action.LONG_ENTRY)

        # 진입 비용 = 수수료 × 계약 수량
        # 주의: 수수료는 가격 × multiplier × rate이므로, 2계약이면 2배가 됨
        expected_cost_per_contract = (
            entry_price * config_multi.contract_multiplier * config_multi.commission_rate
        )
        expected_total_cost = expected_cost_per_contract * config_multi.max_contracts
        expected_r_cost = expected_total_cost / config_multi.initial_balance

        # 2계약 비용이 1계약의 2배인지 확인
        assert expected_total_cost == pytest.approx(expected_cost_per_contract * 2, rel=1e-6), (
            "Cost should scale linearly with contract size"
        )

        # 보상 검증
        expected_r_profit = -expected_total_cost / config_multi.initial_balance
        expected_reward = (
            config_multi.w_profit * expected_r_profit
            - config_multi.w_cost * expected_r_cost
            - config_multi.w_risk * 0.0
        ) * config_multi.reward_scale

        assert reward == pytest.approx(expected_reward, rel=1e-6), (
            f"Multi-contract cost reward mismatch: expected {expected_reward}, got {reward}"
        )

    def test_commission_rate_affects_cost(self, env: FuturesTradingEnv, sample_data: tuple[np.ndarray, np.ndarray]):
        """수수료율이 비용에 영향을 미침"""
        # 높은 수수료율 설정
        config_high_commission = RLEnvConfig(
            initial_balance=100_000_000,
            commission_rate=0.0001,  # 0.01% (기본의 3배 이상)
            tick_size=0.05,
            tick_value=250_000,
            contract_multiplier=250_000,
            max_contracts=1,
            slippage=0.0,
            margin_rate=0.15,
            n_market_features=25,
            n_position_features=6,
            w_profit=1.0,
            w_cost=1.0,
            w_risk=0.5,
            w_mtm=0.0,
            reward_scale=100.0,
            max_loss=-50_000_000,
            loss_penalty_coeff=2.0,
        )

        features, prices = sample_data
        env_high = FuturesTradingEnv(day_data=features, config=config_high_commission, prices=prices)

        # 기본 환경과 높은 수수료 환경 비교
        env.reset()
        env_high.reset()

        entry_price = env._get_current_price()

        # 동일한 행동 수행
        _, reward_normal, _, _, _ = env.step(Action.LONG_ENTRY)
        _, reward_high, _, _, _ = env_high.step(Action.LONG_ENTRY)

        # 높은 수수료 환경의 보상이 더 낮아야 함 (비용이 크므로)
        assert reward_high < reward_normal, (
            f"Higher commission should result in lower reward: "
            f"normal={reward_normal}, high={reward_high}"
        )

        # 비용 차이 계산
        cost_normal = entry_price * env.config.contract_multiplier * env.config.commission_rate
        cost_high = entry_price * config_high_commission.contract_multiplier * config_high_commission.commission_rate

        # 수수료율 비율만큼 비용 차이가 있어야 함
        commission_ratio = config_high_commission.commission_rate / env.config.commission_rate
        assert cost_high == pytest.approx(cost_normal * commission_ratio, rel=1e-6), (
            f"Cost should scale with commission rate: "
            f"normal={cost_normal}, high={cost_high}, ratio={commission_ratio}"
        )
