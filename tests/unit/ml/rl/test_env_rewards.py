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


class TestRiskComponent:
    """리스크 컴포넌트 (r_risk) 테스트

    r_risk = max(0.0, -unrealized_pnl / initial_balance)

    검증 사항:
    - 미실현 손실 시: r_risk > 0 (페널티 발생)
    - 미실현 수익 시: r_risk = 0 (페널티 없음)
    - 포지션 없음: r_risk = 0
    - Drawdown 페널티: actual_pnl <= max_loss 시 강제 청산 + 추가 페널티
    - 손실 페널티 계수: loss_penalty_coeff 배율 적용
    """

    def test_long_position_unrealized_loss_penalty(self, env: FuturesTradingEnv):
        """롱 포지션 미실현 손실: r_risk 페널티 발생"""
        env.reset()
        entry_price = env._get_current_price()

        # 롱 진입
        env.step(Action.LONG_ENTRY)

        # 가격 하락 시뮬레이션 (미실현 손실 발생)
        for _ in range(5):
            env.step(Action.HOLD)

        # 가격 하락 강제 설정
        price_decrease = 3.0  # 3 포인트 하락
        env.prices[env.current_step, 3] = entry_price - price_decrease
        current_price = env._get_current_price()

        # Hold 행동 (미실현 손실 상태 유지)
        _, reward, _, _, info = env.step(Action.HOLD)

        # 미실현 손익 계산
        unrealized_pnl = (
            (current_price - entry_price)
            * env.config.contract_multiplier
            * env.config.max_contracts
        )
        expected_r_risk = max(0.0, -unrealized_pnl / env.config.initial_balance)

        # Hold 시: trade_pnl=0, trade_cost=0, r_risk > 0
        expected_reward = (
            env.config.w_profit * 0.0
            - env.config.w_cost * 0.0
            - env.config.w_risk * expected_r_risk
        ) * env.config.reward_scale

        assert unrealized_pnl < 0, "Test setup error: should have unrealized loss"
        assert expected_r_risk > 0, "r_risk should be positive for unrealized loss"
        assert reward == pytest.approx(expected_reward, rel=1e-5), (
            f"Long unrealized loss penalty mismatch: expected {expected_reward}, got {reward}"
        )

        # 보상이 음수여야 함 (페널티)
        assert reward < 0, "Reward should be negative due to risk penalty"

        # 포지션 유지 확인
        assert env.position == PositionSide.LONG
        assert env.contracts == env.config.max_contracts

    def test_short_position_unrealized_loss_penalty(self, env: FuturesTradingEnv):
        """숏 포지션 미실현 손실: r_risk 페널티 발생"""
        env.reset()
        entry_price = env._get_current_price()

        # 숏 진입
        env.step(Action.SHORT_ENTRY)

        # 가격 상승 시뮬레이션 (숏은 가격 상승 시 손실)
        for _ in range(5):
            env.step(Action.HOLD)

        # 가격 상승 강제 설정
        price_increase = 3.0  # 3 포인트 상승
        env.prices[env.current_step, 3] = entry_price + price_increase
        current_price = env._get_current_price()

        # Hold 행동 (미실현 손실 상태 유지)
        _, reward, _, _, info = env.step(Action.HOLD)

        # 미실현 손익 계산 (숏: entry_price - current_price)
        unrealized_pnl = (
            (entry_price - current_price)
            * env.config.contract_multiplier
            * env.config.max_contracts
        )
        expected_r_risk = max(0.0, -unrealized_pnl / env.config.initial_balance)

        # Hold 시: trade_pnl=0, trade_cost=0, r_risk > 0
        expected_reward = (
            env.config.w_profit * 0.0
            - env.config.w_cost * 0.0
            - env.config.w_risk * expected_r_risk
        ) * env.config.reward_scale

        assert unrealized_pnl < 0, "Test setup error: short should have unrealized loss"
        assert expected_r_risk > 0, "r_risk should be positive for unrealized loss"
        assert reward == pytest.approx(expected_reward, rel=1e-5), (
            f"Short unrealized loss penalty mismatch: expected {expected_reward}, got {reward}"
        )

        # 보상이 음수여야 함 (페널티)
        assert reward < 0, "Reward should be negative due to risk penalty"

        # 포지션 유지 확인
        assert env.position == PositionSide.SHORT
        assert env.contracts == env.config.max_contracts

    def test_long_position_unrealized_profit_no_penalty(self, env: FuturesTradingEnv):
        """롱 포지션 미실현 수익: r_risk = 0 (페널티 없음)"""
        env.reset()
        entry_price = env._get_current_price()

        # 롱 진입
        env.step(Action.LONG_ENTRY)

        # 가격 상승 시뮬레이션 (미실현 수익 발생)
        for _ in range(5):
            env.step(Action.HOLD)

        # 가격 상승 강제 설정
        price_increase = 3.0  # 3 포인트 상승
        env.prices[env.current_step, 3] = entry_price + price_increase
        current_price = env._get_current_price()

        # Hold 행동 (미실현 수익 상태 유지)
        _, reward, _, _, info = env.step(Action.HOLD)

        # 미실현 손익 계산
        unrealized_pnl = (
            (current_price - entry_price)
            * env.config.contract_multiplier
            * env.config.max_contracts
        )
        expected_r_risk = max(0.0, -unrealized_pnl / env.config.initial_balance)

        # Hold 시: trade_pnl=0, trade_cost=0, r_risk=0 (수익이므로 페널티 없음)
        expected_reward = (
            env.config.w_profit * 0.0
            - env.config.w_cost * 0.0
            - env.config.w_risk * expected_r_risk
        ) * env.config.reward_scale

        assert unrealized_pnl > 0, "Test setup error: should have unrealized profit"
        assert expected_r_risk == 0.0, "r_risk should be 0 for unrealized profit"
        assert reward == pytest.approx(expected_reward, abs=1e-9), (
            f"Long unrealized profit reward mismatch: expected {expected_reward}, got {reward}"
        )

        # 보상이 0이어야 함 (Hold 행동, 페널티 없음)
        assert reward == pytest.approx(0.0, abs=1e-9), "Reward should be 0 (no penalty, no profit)"

        # 포지션 유지 확인
        assert env.position == PositionSide.LONG
        assert env.contracts == env.config.max_contracts

    def test_short_position_unrealized_profit_no_penalty(self, env: FuturesTradingEnv):
        """숏 포지션 미실현 수익: r_risk = 0 (페널티 없음)"""
        env.reset()
        entry_price = env._get_current_price()

        # 숏 진입
        env.step(Action.SHORT_ENTRY)

        # 가격 하락 시뮬레이션 (숏은 가격 하락 시 수익)
        for _ in range(5):
            env.step(Action.HOLD)

        # 가격 하락 강제 설정
        price_decrease = 3.0  # 3 포인트 하락
        env.prices[env.current_step, 3] = entry_price - price_decrease
        current_price = env._get_current_price()

        # Hold 행동 (미실현 수익 상태 유지)
        _, reward, _, _, info = env.step(Action.HOLD)

        # 미실현 손익 계산 (숏: entry_price - current_price)
        unrealized_pnl = (
            (entry_price - current_price)
            * env.config.contract_multiplier
            * env.config.max_contracts
        )
        expected_r_risk = max(0.0, -unrealized_pnl / env.config.initial_balance)

        # Hold 시: trade_pnl=0, trade_cost=0, r_risk=0 (수익이므로 페널티 없음)
        expected_reward = (
            env.config.w_profit * 0.0
            - env.config.w_cost * 0.0
            - env.config.w_risk * expected_r_risk
        ) * env.config.reward_scale

        assert unrealized_pnl > 0, "Test setup error: short should have unrealized profit"
        assert expected_r_risk == 0.0, "r_risk should be 0 for unrealized profit"
        assert reward == pytest.approx(expected_reward, abs=1e-9), (
            f"Short unrealized profit reward mismatch: expected {expected_reward}, got {reward}"
        )

        # 보상이 0이어야 함 (Hold 행동, 페널티 없음)
        assert reward == pytest.approx(0.0, abs=1e-9), "Reward should be 0 (no penalty, no profit)"

        # 포지션 유지 확인
        assert env.position == PositionSide.SHORT
        assert env.contracts == env.config.max_contracts

    def test_flat_position_no_risk_penalty(self, env: FuturesTradingEnv):
        """포지션 없음: r_risk = 0"""
        env.reset()

        # Hold 행동 (포지션 없음)
        _, reward, _, _, info = env.step(Action.HOLD)

        # 포지션 없으므로: trade_pnl=0, trade_cost=0, r_risk=0
        expected_reward = 0.0

        assert reward == pytest.approx(expected_reward, abs=1e-9), (
            f"Flat position reward should be 0, got {reward}"
        )

        # 포지션 없음 확인
        assert env.position == PositionSide.FLAT
        assert env.contracts == 0

    def test_max_loss_triggers_drawdown_penalty(self, env: FuturesTradingEnv):
        """max_loss 초과: 강제 청산 + drawdown 페널티 발생"""
        env.reset()
        entry_price = env._get_current_price()

        # 롱 진입
        env.step(Action.LONG_ENTRY)

        # 큰 손실 발생 시뮬레이션
        # max_loss = -50M, initial_balance = 100M
        # 손실률 50% 이상 발생시키기
        # unrealized_pnl = -50M 이상 필요
        # price_decrease = 50M / (contract_multiplier * max_contracts)
        loss_amount = abs(env.config.max_loss)
        required_price_decrease = loss_amount / (
            env.config.contract_multiplier * env.config.max_contracts
        )

        # 가격 급락 설정 (max_loss를 초과하도록)
        for _ in range(10):
            env.step(Action.HOLD)

        env.prices[env.current_step, 3] = entry_price - required_price_decrease - 10.0
        current_price = env._get_current_price()

        # Hold 행동 → max_loss 체크 → 강제 청산 트리거
        _, reward, terminated, _, info = env.step(Action.HOLD)

        # 미실현 손익 계산
        unrealized_pnl = (
            (current_price - entry_price)
            * env.config.contract_multiplier
            * env.config.max_contracts
        )
        actual_pnl = env.total_pnl + unrealized_pnl

        # max_loss 초과 확인
        assert actual_pnl <= env.config.max_loss, (
            f"Test setup error: actual_pnl ({actual_pnl}) should be <= max_loss ({env.config.max_loss})"
        )

        # 강제 청산되어야 함
        assert terminated is True, "Episode should be terminated due to max_loss"
        assert env.position == PositionSide.FLAT, "Position should be forcefully closed"
        assert env.contracts == 0, "No contracts should remain"

        # Drawdown 페널티 계산
        # penalty = max_loss * loss_penalty_coeff / initial_balance * reward_scale
        expected_penalty = (
            env.config.max_loss
            * env.config.loss_penalty_coeff
            / env.config.initial_balance
            * env.config.reward_scale
        )

        # 보상은 강제 청산 보상 + drawdown 페널티를 포함
        # 강제 청산 시 실현 손익 발생 + 페널티 추가
        # 보상이 큰 음수여야 함
        assert reward < 0, f"Reward should be negative due to drawdown penalty, got {reward}"

        # 페널티가 적용되었는지 확인 (정확한 값 검증은 어렵지만 크기 확인)
        assert reward < expected_penalty, (
            f"Reward should include drawdown penalty: "
            f"reward={reward}, expected_penalty={expected_penalty}"
        )

    def test_loss_penalty_coefficient_application(
        self, env: FuturesTradingEnv, sample_data: tuple[np.ndarray, np.ndarray]
    ):
        """loss_penalty_coeff가 drawdown 페널티에 적용됨"""
        # 기본 설정 (loss_penalty_coeff=2.0)
        features, prices = sample_data
        entry_price = prices[0, 3]

        # 손실 페널티 계수가 다른 두 환경 생성
        config_low_coeff = RLEnvConfig(
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
            reward_scale=100.0,
            max_loss=-50_000_000,
            loss_penalty_coeff=1.0,  # 낮은 계수
        )

        config_high_coeff = RLEnvConfig(
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
            reward_scale=100.0,
            max_loss=-50_000_000,
            loss_penalty_coeff=3.0,  # 높은 계수
        )

        env_low = FuturesTradingEnv(day_data=features, config=config_low_coeff, prices=prices.copy())
        env_high = FuturesTradingEnv(day_data=features, config=config_high_coeff, prices=prices.copy())

        # 두 환경 모두 초기화 및 진입
        env_low.reset()
        env_high.reset()

        env_low.step(Action.LONG_ENTRY)
        env_high.step(Action.LONG_ENTRY)

        # 큰 손실 발생시키기 (max_loss 초과)
        loss_amount = abs(config_low_coeff.max_loss)
        required_price_decrease = loss_amount / (
            config_low_coeff.contract_multiplier * config_low_coeff.max_contracts
        )

        for _ in range(10):
            env_low.step(Action.HOLD)
            env_high.step(Action.HOLD)

        # 동일한 가격 하락 적용
        env_low.prices[env_low.current_step, 3] = entry_price - required_price_decrease - 10.0
        env_high.prices[env_high.current_step, 3] = entry_price - required_price_decrease - 10.0

        # Hold 행동 → 강제 청산
        _, reward_low, terminated_low, _, _ = env_low.step(Action.HOLD)
        _, reward_high, terminated_high, _, _ = env_high.step(Action.HOLD)

        # 둘 다 종료되어야 함
        assert terminated_low is True, "Low coeff env should terminate"
        assert terminated_high is True, "High coeff env should terminate"

        # 높은 계수 환경의 페널티가 더 커야 함 (보상이 더 음수)
        assert reward_high < reward_low, (
            f"Higher loss_penalty_coeff should result in more negative reward: "
            f"low_coeff={reward_low}, high_coeff={reward_high}"
        )

        # 페널티 차이 계산
        expected_penalty_low = (
            config_low_coeff.max_loss
            * config_low_coeff.loss_penalty_coeff
            / config_low_coeff.initial_balance
            * config_low_coeff.reward_scale
        )
        expected_penalty_high = (
            config_high_coeff.max_loss
            * config_high_coeff.loss_penalty_coeff
            / config_high_coeff.initial_balance
            * config_high_coeff.reward_scale
        )

        # 페널티 비율이 계수 비율과 일치해야 함
        coeff_ratio = config_high_coeff.loss_penalty_coeff / config_low_coeff.loss_penalty_coeff
        penalty_ratio = expected_penalty_high / expected_penalty_low

        assert penalty_ratio == pytest.approx(coeff_ratio, rel=1e-6), (
            f"Penalty ratio should match coefficient ratio: "
            f"coeff_ratio={coeff_ratio}, penalty_ratio={penalty_ratio}"
        )

    def test_risk_penalty_scales_with_unrealized_loss(self, env: FuturesTradingEnv):
        """미실현 손실 크기에 비례하여 r_risk 증가"""
        env.reset()
        entry_price = env._get_current_price()

        # 롱 진입
        env.step(Action.LONG_ENTRY)

        # 작은 손실 발생
        for _ in range(5):
            env.step(Action.HOLD)

        small_decrease = 1.0
        env.prices[env.current_step, 3] = entry_price - small_decrease
        _, reward_small, _, _, _ = env.step(Action.HOLD)

        # 큰 손실 발생
        for _ in range(5):
            env.step(Action.HOLD)

        large_decrease = 5.0
        env.prices[env.current_step, 3] = entry_price - large_decrease
        _, reward_large, _, _, _ = env.step(Action.HOLD)

        # 큰 손실의 페널티가 더 커야 함
        assert reward_large < reward_small, (
            f"Larger unrealized loss should result in more negative reward: "
            f"small_loss={reward_small}, large_loss={reward_large}"
        )

        # r_risk 계산
        unrealized_pnl_small = -small_decrease * env.config.contract_multiplier
        unrealized_pnl_large = -large_decrease * env.config.contract_multiplier

        r_risk_small = -unrealized_pnl_small / env.config.initial_balance
        r_risk_large = -unrealized_pnl_large / env.config.initial_balance

        # r_risk 비율이 손실 비율과 일치해야 함
        loss_ratio = large_decrease / small_decrease
        risk_ratio = r_risk_large / r_risk_small

        assert risk_ratio == pytest.approx(loss_ratio, rel=1e-6), (
            f"Risk penalty should scale linearly with unrealized loss: "
            f"loss_ratio={loss_ratio}, risk_ratio={risk_ratio}"
        )


class TestMTMComponent:
    """MTM (Mark-to-Market) 컴포넌트 (r_mtm) 테스트

    r_mtm = (unrealized_pnl - prev_unrealized_pnl) / initial_balance

    검증 사항:
    - w_mtm=0일 때: MTM 비활성 (보상에 기여하지 않음)
    - w_mtm>0일 때: 미실현 손익 변화를 추적
    - 진입 시: r_mtm = 0 (이전 미실현 손익 없음)
    - 보유 중 가격 상승: r_mtm > 0 (LONG), r_mtm < 0 (SHORT)
    - 보유 중 가격 하락: r_mtm < 0 (LONG), r_mtm > 0 (SHORT)
    - 청산 시: r_mtm 계산 안 함 (r_profit과 이중 계산 방지)
    - FLAT 포지션: r_mtm = 0
    """

    @pytest.fixture
    def mtm_config(self) -> RLEnvConfig:
        """MTM 활성화 설정 (w_mtm=0.3)"""
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
            n_position_features=6,
            w_profit=1.0,
            w_cost=1.0,
            w_risk=0.5,
            w_mtm=0.3,  # MTM 활성화
            inaction_penalty=0.0,
            reward_scale=100.0,
            max_loss=-50_000_000,
            loss_penalty_coeff=2.0,
        )

    @pytest.fixture
    def mtm_env(
        self, mtm_config: RLEnvConfig, sample_data: tuple[np.ndarray, np.ndarray]
    ) -> FuturesTradingEnv:
        """MTM 활성화 환경"""
        features, prices = sample_data
        return FuturesTradingEnv(day_data=features, config=mtm_config, prices=prices)

    def test_mtm_disabled_when_w_mtm_zero(self, env: FuturesTradingEnv):
        """w_mtm=0일 때 MTM이 보상에 기여하지 않음"""
        env.reset()
        entry_price = env._get_current_price()

        # 롱 진입
        env.step(Action.LONG_ENTRY)

        # 가격 상승
        price_increase = 5.0
        env.prices[env.current_step, 3] = entry_price + price_increase

        # Hold
        _, reward, _, _, _ = env.step(Action.HOLD)

        # MTM이 비활성화되어 있으므로 (w_mtm=0.0)
        # 보상은 r_profit(0) - r_cost(0) - r_risk(0)만 포함
        # Hold 시 실현 손익 없고, 비용도 없으므로 보상은 r_risk만 영향
        assert env.config.w_mtm == 0.0, "Test assumes w_mtm=0"

        # r_risk는 미실현 이익 시 0이므로 Hold 보상은 0
        unrealized_pnl = price_increase * env.config.contract_multiplier
        assert unrealized_pnl > 0, "Should have unrealized profit"

        # 보상 계산: profit(0) - cost(0) - risk(0) = 0
        expected_reward = 0.0
        assert reward == pytest.approx(expected_reward, abs=1e-6), (
            f"Hold reward with w_mtm=0 should be 0: expected {expected_reward}, got {reward}"
        )

    def test_mtm_zero_on_long_entry(self, mtm_env: FuturesTradingEnv):
        """롱 진입 시 r_mtm=0 (이전 미실현 손익 없음)"""
        mtm_env.reset()
        entry_price = mtm_env._get_current_price()

        # 진입 직전 _prev_unrealized_pnl = 0
        assert mtm_env._prev_unrealized_pnl == 0.0

        # 롱 진입
        _, reward, _, _, _ = mtm_env.step(Action.LONG_ENTRY)

        # 진입 직후 unrealized_pnl = 0 (진입가 = 현재가)
        # r_mtm = (0 - 0) / initial_balance = 0
        # 진입 비용만 있으므로 r_profit < 0, r_cost > 0
        entry_cost = (
            entry_price * mtm_env.config.contract_multiplier * mtm_env.config.commission_rate
        )
        expected_r_profit = -entry_cost / mtm_env.config.initial_balance
        expected_r_cost = entry_cost / mtm_env.config.initial_balance
        expected_r_mtm = 0.0
        expected_reward = (
            mtm_env.config.w_profit * expected_r_profit
            - mtm_env.config.w_cost * expected_r_cost
            - mtm_env.config.w_risk * 0.0
            + mtm_env.config.w_mtm * expected_r_mtm
        ) * mtm_env.config.reward_scale

        assert reward == pytest.approx(expected_reward, rel=1e-6), (
            f"Long entry reward mismatch: expected {expected_reward}, got {reward}"
        )

    def test_mtm_zero_on_short_entry(self, mtm_env: FuturesTradingEnv):
        """숏 진입 시 r_mtm=0 (이전 미실현 손익 없음)"""
        mtm_env.reset()
        entry_price = mtm_env._get_current_price()

        # 숏 진입
        _, reward, _, _, _ = mtm_env.step(Action.SHORT_ENTRY)

        # 진입 직후 r_mtm = 0
        entry_cost = (
            entry_price * mtm_env.config.contract_multiplier * mtm_env.config.commission_rate
        )
        expected_r_profit = -entry_cost / mtm_env.config.initial_balance
        expected_r_cost = entry_cost / mtm_env.config.initial_balance
        expected_r_mtm = 0.0
        expected_reward = (
            mtm_env.config.w_profit * expected_r_profit
            - mtm_env.config.w_cost * expected_r_cost
            - mtm_env.config.w_risk * 0.0
            + mtm_env.config.w_mtm * expected_r_mtm
        ) * mtm_env.config.reward_scale

        assert reward == pytest.approx(expected_reward, rel=1e-6), (
            f"Short entry reward mismatch: expected {expected_reward}, got {reward}"
        )

    def test_mtm_positive_on_long_profit(self, mtm_env: FuturesTradingEnv):
        """롱 포지션 가격 상승 시 r_mtm > 0"""
        mtm_env.reset()
        entry_price = mtm_env._get_current_price()

        # 롱 진입
        mtm_env.step(Action.LONG_ENTRY)

        # 가격 상승
        price_increase = 5.0
        mtm_env.prices[mtm_env.current_step, 3] = entry_price + price_increase

        # Hold
        _, reward, _, _, _ = mtm_env.step(Action.HOLD)

        # 미실현 손익 변화 계산
        prev_unrealized_pnl = 0.0  # 진입 직후
        current_unrealized_pnl = price_increase * mtm_env.config.contract_multiplier
        mtm_change = current_unrealized_pnl - prev_unrealized_pnl

        expected_r_mtm = mtm_change / mtm_env.config.initial_balance
        assert expected_r_mtm > 0, "MTM should be positive for long profit"

        # 보상 계산: profit(0) - cost(0) - risk(0) + mtm(>0)
        expected_reward = (
            mtm_env.config.w_mtm * expected_r_mtm
        ) * mtm_env.config.reward_scale

        assert reward == pytest.approx(expected_reward, rel=1e-6), (
            f"Hold reward with MTM mismatch: expected {expected_reward}, got {reward}"
        )

    def test_mtm_negative_on_long_loss(self, mtm_env: FuturesTradingEnv):
        """롱 포지션 가격 하락 시 r_mtm < 0"""
        mtm_env.reset()
        entry_price = mtm_env._get_current_price()

        # 롱 진입
        mtm_env.step(Action.LONG_ENTRY)

        # 가격 하락
        price_decrease = 3.0
        mtm_env.prices[mtm_env.current_step, 3] = entry_price - price_decrease

        # Hold
        _, reward, _, _, _ = mtm_env.step(Action.HOLD)

        # 미실현 손익 변화 계산
        prev_unrealized_pnl = 0.0
        current_unrealized_pnl = -price_decrease * mtm_env.config.contract_multiplier
        mtm_change = current_unrealized_pnl - prev_unrealized_pnl

        expected_r_mtm = mtm_change / mtm_env.config.initial_balance
        assert expected_r_mtm < 0, "MTM should be negative for long loss"

        # 보상 계산: r_risk도 음수 (미실현 손실)
        expected_r_risk = -current_unrealized_pnl / mtm_env.config.initial_balance

        expected_reward = (
            -mtm_env.config.w_risk * expected_r_risk
            + mtm_env.config.w_mtm * expected_r_mtm
        ) * mtm_env.config.reward_scale

        assert reward == pytest.approx(expected_reward, rel=1e-5), (
            f"Hold reward with negative MTM mismatch: expected {expected_reward}, got {reward}"
        )

    def test_mtm_positive_on_short_loss(self, mtm_env: FuturesTradingEnv):
        """숏 포지션 가격 상승 시 r_mtm < 0 (손실)"""
        mtm_env.reset()
        entry_price = mtm_env._get_current_price()

        # 숏 진입
        mtm_env.step(Action.SHORT_ENTRY)

        # 가격 상승 (숏에게는 불리)
        price_increase = 4.0
        mtm_env.prices[mtm_env.current_step, 3] = entry_price + price_increase

        # Hold
        _, reward, _, _, _ = mtm_env.step(Action.HOLD)

        # 숏은 가격 상승 시 손실
        prev_unrealized_pnl = 0.0
        current_unrealized_pnl = -price_increase * mtm_env.config.contract_multiplier
        mtm_change = current_unrealized_pnl - prev_unrealized_pnl

        expected_r_mtm = mtm_change / mtm_env.config.initial_balance
        assert expected_r_mtm < 0, "MTM should be negative for short loss"

        # r_risk도 음수
        expected_r_risk = -current_unrealized_pnl / mtm_env.config.initial_balance

        expected_reward = (
            -mtm_env.config.w_risk * expected_r_risk
            + mtm_env.config.w_mtm * expected_r_mtm
        ) * mtm_env.config.reward_scale

        assert reward == pytest.approx(expected_reward, rel=1e-5), (
            f"Hold reward with short MTM mismatch: expected {expected_reward}, got {reward}"
        )

    def test_mtm_negative_on_short_profit(self, mtm_env: FuturesTradingEnv):
        """숏 포지션 가격 하락 시 r_mtm > 0 (이익)"""
        mtm_env.reset()
        entry_price = mtm_env._get_current_price()

        # 숏 진입
        mtm_env.step(Action.SHORT_ENTRY)

        # 가격 하락 (숏에게는 유리)
        price_decrease = 6.0
        mtm_env.prices[mtm_env.current_step, 3] = entry_price - price_decrease

        # Hold
        _, reward, _, _, _ = mtm_env.step(Action.HOLD)

        # 숏은 가격 하락 시 이익
        prev_unrealized_pnl = 0.0
        current_unrealized_pnl = price_decrease * mtm_env.config.contract_multiplier
        mtm_change = current_unrealized_pnl - prev_unrealized_pnl

        expected_r_mtm = mtm_change / mtm_env.config.initial_balance
        assert expected_r_mtm > 0, "MTM should be positive for short profit"

        # r_risk는 0 (이익이므로)
        expected_reward = (
            mtm_env.config.w_mtm * expected_r_mtm
        ) * mtm_env.config.reward_scale

        assert reward == pytest.approx(expected_reward, rel=1e-6), (
            f"Hold reward with short profit MTM mismatch: expected {expected_reward}, got {reward}"
        )

    def test_mtm_tracks_incremental_changes(self, mtm_env: FuturesTradingEnv):
        """MTM은 스텝 간 미실현 손익 변화만 추적 (누적 아님)"""
        mtm_env.reset()
        entry_price = mtm_env._get_current_price()

        # 롱 진입
        mtm_env.step(Action.LONG_ENTRY)

        # 첫 번째 가격 상승
        price_1 = entry_price + 2.0
        mtm_env.prices[mtm_env.current_step, 3] = price_1
        _, reward_1, _, _, _ = mtm_env.step(Action.HOLD)

        # 미실현 손익: 0 → 2.0 * multiplier
        unrealized_1 = 2.0 * mtm_env.config.contract_multiplier
        expected_r_mtm_1 = unrealized_1 / mtm_env.config.initial_balance
        expected_reward_1 = (
            mtm_env.config.w_mtm * expected_r_mtm_1
        ) * mtm_env.config.reward_scale

        assert reward_1 == pytest.approx(expected_reward_1, rel=1e-6)

        # 두 번째 가격 상승
        price_2 = entry_price + 5.0  # 추가로 3.0 상승
        mtm_env.prices[mtm_env.current_step, 3] = price_2
        _, reward_2, _, _, _ = mtm_env.step(Action.HOLD)

        # 미실현 손익: 2.0 → 5.0 (변화: +3.0)
        unrealized_2 = 5.0 * mtm_env.config.contract_multiplier
        prev_unrealized_2 = 2.0 * mtm_env.config.contract_multiplier
        mtm_change_2 = unrealized_2 - prev_unrealized_2

        expected_r_mtm_2 = mtm_change_2 / mtm_env.config.initial_balance
        expected_reward_2 = (
            mtm_env.config.w_mtm * expected_r_mtm_2
        ) * mtm_env.config.reward_scale

        assert reward_2 == pytest.approx(expected_reward_2, rel=1e-6), (
            f"Second MTM reward should reflect incremental change: "
            f"expected {expected_reward_2}, got {reward_2}"
        )

        # 두 번째 변화가 더 크므로 보상도 더 큼
        assert reward_2 > reward_1, "Larger MTM change should result in larger reward"

    def test_mtm_not_applied_on_exit(self, mtm_env: FuturesTradingEnv):
        """청산 시 MTM 계산 안 함 (r_profit과 이중 계산 방지)"""
        mtm_env.reset()
        entry_price = mtm_env._get_current_price()

        # 롱 진입
        mtm_env.step(Action.LONG_ENTRY)

        # 가격 상승
        price_increase = 7.0
        mtm_env.prices[mtm_env.current_step, 3] = entry_price + price_increase

        # Hold 후 exit
        mtm_env.step(Action.HOLD)

        exit_price = mtm_env._get_current_price()
        _, reward, _, _, _ = mtm_env.step(Action.LONG_EXIT)

        # 청산 시 r_mtm은 계산되지 않음 (r_profit에 포함)
        gross_pnl = (
            (exit_price - entry_price)
            * mtm_env.config.contract_multiplier
            * mtm_env.config.max_contracts
        )
        exit_cost = exit_price * mtm_env.config.contract_multiplier * mtm_env.config.commission_rate
        trade_pnl = gross_pnl - exit_cost

        expected_r_profit = trade_pnl / mtm_env.config.initial_balance
        expected_r_cost = exit_cost / mtm_env.config.initial_balance
        # r_mtm은 청산 시 0
        expected_r_mtm = 0.0

        expected_reward = (
            mtm_env.config.w_profit * expected_r_profit
            - mtm_env.config.w_cost * expected_r_cost
            + mtm_env.config.w_mtm * expected_r_mtm
        ) * mtm_env.config.reward_scale

        assert reward == pytest.approx(expected_reward, rel=1e-5), (
            f"Exit reward should not include MTM: expected {expected_reward}, got {reward}"
        )

        # 포지션 청산 확인
        assert mtm_env.position == PositionSide.FLAT

    def test_mtm_zero_when_flat(self, mtm_env: FuturesTradingEnv):
        """FLAT 포지션일 때 r_mtm=0"""
        mtm_env.reset()

        # FLAT 상태에서 Hold
        _, reward, _, _, _ = mtm_env.step(Action.HOLD)

        # FLAT이므로 모든 컴포넌트 0
        expected_reward = 0.0
        assert reward == pytest.approx(expected_reward, abs=1e-6), (
            f"FLAT position reward should be 0: expected {expected_reward}, got {reward}"
        )

        assert mtm_env.position == PositionSide.FLAT

    def test_mtm_scaling_with_weight(self, sample_data: tuple[np.ndarray, np.ndarray]):
        """w_mtm 가중치에 따라 MTM 보상 스케일 변화"""
        features, prices = sample_data

        # w_mtm=0.3 환경
        config_low = RLEnvConfig(
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
            w_mtm=0.3,
            inaction_penalty=0.0,
            reward_scale=100.0,
            max_loss=-50_000_000,
            loss_penalty_coeff=2.0,
        )
        env_low = FuturesTradingEnv(day_data=features, config=config_low, prices=prices)

        # w_mtm=0.9 환경
        config_high = RLEnvConfig(
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
            w_mtm=0.9,  # 3배 증가
            inaction_penalty=0.0,
            reward_scale=100.0,
            max_loss=-50_000_000,
            loss_penalty_coeff=2.0,
        )
        env_high = FuturesTradingEnv(day_data=features, config=config_high, prices=prices)

        # 동일한 시나리오 실행
        env_low.reset()
        env_high.reset()

        entry_price = env_low._get_current_price()

        # 롱 진입
        env_low.step(Action.LONG_ENTRY)
        env_high.step(Action.LONG_ENTRY)

        # 가격 상승
        price_increase = 4.0
        env_low.prices[env_low.current_step, 3] = entry_price + price_increase
        env_high.prices[env_high.current_step, 3] = entry_price + price_increase

        # Hold
        _, reward_low, _, _, _ = env_low.step(Action.HOLD)
        _, reward_high, _, _, _ = env_high.step(Action.HOLD)

        # w_mtm이 3배 증가하면 MTM 컴포넌트 기여도도 3배
        weight_ratio = config_high.w_mtm / config_low.w_mtm
        assert weight_ratio == pytest.approx(3.0, rel=1e-6)

        # 보상 비율 확인 (대략 3배)
        # reward = w_mtm * r_mtm * reward_scale
        # 다른 컴포넌트가 0이므로 보상 비율 = w_mtm 비율
        reward_ratio = reward_high / reward_low
        assert reward_ratio == pytest.approx(weight_ratio, rel=1e-6), (
            f"Reward should scale with w_mtm: weight_ratio={weight_ratio}, "
            f"reward_ratio={reward_ratio}"
        )
