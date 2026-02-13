"""Tests for hierarchical RL environments.

Tests HighLevelEnv (15-min decisions) and LowLevelEnv (1-min execution)
for multi-level reinforcement learning.
"""

import numpy as np
import pytest
from gymnasium import spaces

from shared.ml.rl.env import Action, FuturesTradingEnv, PositionSide, RLEnvConfig
from shared.ml.rl.hierarchical.high_level_env import (
    HighLevelAction,
    HighLevelConfig,
    HighLevelEnv,
)
from shared.ml.rl.hierarchical.low_level_env import LowLevelEnv


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def base_env_data():
    """Generate test data for 1-min env (405 bars = 1 trading day)."""
    n_steps = 405  # 09:00-15:45
    n_features = 25

    day_data = np.random.randn(n_steps, n_features).astype(np.float32)
    day_data[:, 0] = np.clip(day_data[:, 0] * 0.001, -0.01, 0.01)  # returns
    day_data[:, 1:] = np.clip(day_data[:, 1:], -3, 3)

    base_price = 350.0
    prices = np.zeros((n_steps, 4), dtype=np.float32)
    for i in range(n_steps):
        close = base_price + np.random.randn() * 0.5
        high = close + abs(np.random.randn() * 0.3)
        low = close - abs(np.random.randn() * 0.3)
        open_ = close + np.random.randn() * 0.1
        prices[i] = [open_, high, low, close]

    return day_data, prices


@pytest.fixture
def high_level_data():
    """Generate test data for 15-min env (27 bars)."""
    n_steps = 27  # 405 / 15 = 27
    n_features = 25

    data_15m = np.random.randn(n_steps, n_features).astype(np.float32)
    data_15m[:, 0] = np.clip(data_15m[:, 0] * 0.001, -0.01, 0.01)
    data_15m[:, 1:] = np.clip(data_15m[:, 1:], -3, 3)

    return data_15m


@pytest.fixture
def low_level_results():
    """Generate mock low-level results for 27 segments."""
    results = []
    for i in range(27):
        results.append({
            'pnl': np.random.randn() * 1000,
            'n_trades': np.random.randint(0, 3),
            'win_rate': np.random.rand(),
        })
    return results


# ============================================================================
# HighLevelEnv Tests
# ============================================================================


class TestHighLevelAction:
    def test_constants(self):
        assert HighLevelAction.AGGRESSIVE == 0
        assert HighLevelAction.NEUTRAL == 1
        assert HighLevelAction.DEFENSIVE == 2

    def test_risk_budgets_in_config(self):
        cfg = HighLevelConfig()
        assert cfg.risk_budgets[0] == 1.0
        assert cfg.risk_budgets[1] == 0.5
        assert cfg.risk_budgets[2] == 0.0

    def test_names(self):
        assert HighLevelAction.NAMES[0] == "AGGRESSIVE"
        assert HighLevelAction.NAMES[1] == "NEUTRAL"
        assert HighLevelAction.NAMES[2] == "DEFENSIVE"


class TestHighLevelConfig:
    def test_default_values(self):
        cfg = HighLevelConfig()
        assert cfg.n_bar_features == 25
        assert cfg.n_summary_features == 5
        assert cfg.bars_per_step == 15
        assert cfg.initial_balance == 100_000_000
        assert cfg.max_steps == 27


class TestHighLevelEnvInit:
    def test_action_space(self, high_level_data):
        env = HighLevelEnv(high_level_data)
        assert isinstance(env.action_space, spaces.Discrete)
        assert env.action_space.n == 3

    def test_observation_space(self, high_level_data):
        env = HighLevelEnv(high_level_data)
        # 25 bar features + 5 summary features = 30
        assert isinstance(env.observation_space, spaces.Box)
        assert env.observation_space.shape == (30,)

    def test_custom_config(self, high_level_data):
        config = HighLevelConfig(n_bar_features=20, n_summary_features=10)
        env = HighLevelEnv(high_level_data, config=config)
        assert env.observation_space.shape == (30,)

    def test_initial_state(self, high_level_data):
        env = HighLevelEnv(high_level_data)
        assert env.current_step == 0
        assert env.total_pnl == 0.0
        assert env.n_trades == 0


class TestHighLevelEnvReset:
    def test_reset_returns_obs_and_info(self, high_level_data):
        env = HighLevelEnv(high_level_data)
        obs, info = env.reset()

        assert isinstance(obs, np.ndarray)
        assert obs.shape == (30,)
        assert isinstance(info, dict)

    def test_reset_initializes_state(self, high_level_data, low_level_results):
        env = HighLevelEnv(high_level_data, low_level_results=low_level_results)
        env.step(0)  # Take a step

        obs, info = env.reset()

        assert env.current_step == 0
        assert env.total_pnl == 0.0
        assert env.n_trades == 0
        assert len(env.risk_budget_history) == 0

    def test_reset_with_seed(self, high_level_data):
        env = HighLevelEnv(high_level_data)
        obs1, _ = env.reset(seed=42)
        obs2, _ = env.reset(seed=42)

        # Initial observations should be the same
        np.testing.assert_array_equal(obs1, obs2)


class TestHighLevelEnvStep:
    def test_step_returns_correct_types(self, high_level_data, low_level_results):
        env = HighLevelEnv(high_level_data, low_level_results=low_level_results)
        env.reset()

        obs, reward, terminated, truncated, info = env.step(HighLevelAction.AGGRESSIVE)

        assert isinstance(obs, np.ndarray)
        assert obs.shape == (30,)
        assert isinstance(reward, (int, float, np.number))
        assert isinstance(terminated, (bool, np.bool_))
        assert isinstance(truncated, (bool, np.bool_))
        assert isinstance(info, dict)

    def test_step_updates_state(self, high_level_data, low_level_results):
        env = HighLevelEnv(high_level_data, low_level_results=low_level_results)
        env.reset()

        initial_step = env.current_step
        env.step(HighLevelAction.NEUTRAL)

        assert env.current_step == initial_step + 1
        assert len(env.risk_budget_history) == 1
        assert env.risk_budget_history[0] == 0.5  # NEUTRAL budget

    def test_aggressive_uses_full_risk_budget(self, high_level_data, low_level_results):
        env = HighLevelEnv(high_level_data, low_level_results=low_level_results)
        env.reset()

        obs, reward, terminated, truncated, info = env.step(HighLevelAction.AGGRESSIVE)

        assert env.risk_budget_history[-1] == 1.0

    def test_defensive_uses_zero_risk_budget(self, high_level_data, low_level_results):
        env = HighLevelEnv(high_level_data, low_level_results=low_level_results)
        env.reset()

        env.step(HighLevelAction.DEFENSIVE)

        assert env.risk_budget_history[-1] == 0.0

    def test_step_accumulates_pnl(self, high_level_data, low_level_results):
        env = HighLevelEnv(high_level_data, low_level_results=low_level_results)
        env.reset()

        initial_pnl = env.total_pnl
        env.step(HighLevelAction.AGGRESSIVE)

        # PnL should have changed (unless low_level_results[0]['pnl'] was exactly 0)
        assert env.total_pnl != initial_pnl or low_level_results[0]['pnl'] == 0

    def test_step_scales_pnl_by_risk_budget(self, high_level_data):
        # Create deterministic low-level results
        results = [{'pnl': 1000.0, 'n_trades': 1, 'win_rate': 1.0} for _ in range(27)]
        env = HighLevelEnv(high_level_data, low_level_results=results)
        env.reset()

        # AGGRESSIVE (risk_budget=1.0) -> full PnL
        env.step(HighLevelAction.AGGRESSIVE)
        pnl_aggressive = env.total_pnl

        # NEUTRAL (risk_budget=0.5) -> half PnL
        env.reset()
        env.step(HighLevelAction.NEUTRAL)
        pnl_neutral = env.total_pnl

        assert abs(pnl_neutral - pnl_aggressive / 2) < 0.01

    def test_episode_terminates_at_max_steps(self, high_level_data, low_level_results):
        env = HighLevelEnv(high_level_data, low_level_results=low_level_results)
        env.reset()

        terminated = False
        steps = 0
        while not terminated:
            obs, reward, terminated, truncated, info = env.step(HighLevelAction.NEUTRAL)
            steps += 1
            if steps > 30:  # Safety limit
                break

        assert terminated
        assert env.current_step >= 27  # Should terminate at or before max_steps


class TestHighLevelEnvObservation:
    def test_observation_contains_bar_features(self, high_level_data):
        env = HighLevelEnv(high_level_data)
        obs, _ = env.reset()

        # First 25 elements should be bar features
        bar_features = obs[:25]
        first_bar = high_level_data[0]

        np.testing.assert_array_almost_equal(bar_features, first_bar)

    def test_observation_contains_summary_features(self, high_level_data):
        env = HighLevelEnv(high_level_data)
        obs, _ = env.reset()

        # Last 5 elements are summary features
        summary = obs[25:]
        assert len(summary) == 5

        # At reset: progress=0, sin/cos, pnl_norm=0, avg_risk=0.5
        assert summary[0] == 0.0  # progress
        assert summary[3] == 0.0  # pnl_norm
        assert summary[4] == 0.5  # avg_risk (default)

    def test_observation_progress_increases(self, high_level_data, low_level_results):
        env = HighLevelEnv(high_level_data, low_level_results=low_level_results)
        env.reset()

        env.step(HighLevelAction.NEUTRAL)
        obs, _, _, _, _ = env.step(HighLevelAction.NEUTRAL)

        progress = obs[25]  # First summary feature
        expected_progress = 2 / 27
        assert progress == pytest.approx(expected_progress, abs=0.01)


class TestHighLevelEnvInfo:
    def test_info_contains_total_pnl(self, high_level_data, low_level_results):
        env = HighLevelEnv(high_level_data, low_level_results=low_level_results)
        env.reset()

        _, _, _, _, info = env.step(HighLevelAction.AGGRESSIVE)

        assert 'total_pnl' in info
        assert isinstance(info['total_pnl'], (int, float))

    def test_info_contains_n_trades(self, high_level_data, low_level_results):
        env = HighLevelEnv(high_level_data, low_level_results=low_level_results)
        env.reset()

        _, _, _, _, info = env.step(HighLevelAction.NEUTRAL)

        assert 'n_trades' in info
        assert isinstance(info['n_trades'], int)

    def test_info_contains_risk_history(self, high_level_data, low_level_results):
        env = HighLevelEnv(high_level_data, low_level_results=low_level_results)
        env.reset()

        env.step(HighLevelAction.AGGRESSIVE)
        _, _, _, _, info = env.step(HighLevelAction.DEFENSIVE)

        assert 'risk_budget_history' in info
        assert len(info['risk_budget_history']) == 2
        assert info['risk_budget_history'][0] == 1.0
        assert info['risk_budget_history'][1] == 0.0


# ============================================================================
# LowLevelEnv Tests
# ============================================================================


class TestLowLevelEnvInit:
    def test_inherits_from_futures_trading_env(self, base_env_data):
        day_data, prices = base_env_data
        config = RLEnvConfig(max_contracts=5)
        env = LowLevelEnv(day_data, config, prices)

        assert isinstance(env, FuturesTradingEnv)
        assert env._original_max_contracts == 5
        assert env._risk_budget == 1.0

    def test_initial_risk_budget_is_one(self, base_env_data):
        day_data, prices = base_env_data
        env = LowLevelEnv(day_data, prices=prices)

        assert env._risk_budget == 1.0


class TestLowLevelEnvSetRiskBudget:
    def test_set_risk_budget_updates_value(self, base_env_data):
        day_data, prices = base_env_data
        env = LowLevelEnv(day_data, prices=prices)

        env.set_risk_budget(0.5)
        assert env._risk_budget == 0.5

    def test_set_risk_budget_scales_max_contracts(self, base_env_data):
        day_data, prices = base_env_data
        config = RLEnvConfig(max_contracts=10)
        env = LowLevelEnv(day_data, config, prices)

        env.set_risk_budget(0.5)
        assert env.config.max_contracts == 5  # 10 * 0.5 = 5

    def test_set_risk_budget_zero_disables_trading(self, base_env_data):
        day_data, prices = base_env_data
        config = RLEnvConfig(max_contracts=5)
        env = LowLevelEnv(day_data, config, prices)

        env.set_risk_budget(0.0)
        assert env.config.max_contracts == 0

    def test_set_risk_budget_clips_to_range(self, base_env_data):
        day_data, prices = base_env_data
        env = LowLevelEnv(day_data, prices=prices)

        # Test upper bound
        env.set_risk_budget(1.5)
        assert env._risk_budget == 1.0

        # Test lower bound
        env.set_risk_budget(-0.5)
        assert env._risk_budget == 0.0

    def test_set_risk_budget_rounds_contracts(self, base_env_data):
        day_data, prices = base_env_data
        config = RLEnvConfig(max_contracts=10)
        env = LowLevelEnv(day_data, config, prices)

        env.set_risk_budget(0.33)  # 10 * 0.33 = 3.3 -> round to 3
        assert env.config.max_contracts == 3


class TestLowLevelEnvActionMasks:
    def test_risk_budget_zero_blocks_entry(self, base_env_data):
        day_data, prices = base_env_data
        env = LowLevelEnv(day_data, prices=prices)
        env.reset()

        env.set_risk_budget(0.0)
        masks = env.action_masks()

        assert masks[Action.LONG_ENTRY] == False
        assert masks[Action.SHORT_ENTRY] == False
        assert masks[Action.HOLD] == True

    def test_risk_budget_positive_allows_entry_when_flat(self, base_env_data):
        day_data, prices = base_env_data
        env = LowLevelEnv(day_data, prices=prices)
        env.reset()

        # Ensure position is FLAT
        env.position = PositionSide.FLAT

        env.set_risk_budget(0.5)
        masks = env.action_masks()

        # Entry should be allowed (if other conditions allow)
        # This depends on base env logic, but risk_budget shouldn't block it
        assert masks[Action.HOLD] == True

    def test_action_masks_preserves_base_logic(self, base_env_data):
        """Risk budget modification should preserve base action mask logic."""
        day_data, prices = base_env_data
        env = LowLevelEnv(day_data, prices=prices)
        env.reset()

        # With risk_budget=1.0, masks should match base env
        env.set_risk_budget(1.0)
        env.position = PositionSide.LONG

        masks = env.action_masks()

        # When LONG, should not allow LONG_ENTRY or SHORT_EXIT
        assert masks[Action.LONG_ENTRY] == False
        assert masks[Action.SHORT_EXIT] == False
        assert masks[Action.LONG_EXIT] == True
        assert masks[Action.HOLD] == True


class TestLowLevelEnvSegmentResults:
    def test_get_15min_segment_results_structure(self, base_env_data):
        day_data, prices = base_env_data
        env = LowLevelEnv(day_data, prices=prices)
        env.reset()

        # Run some steps to generate trades
        for _ in range(30):
            action = np.random.randint(0, 5)
            env.step(action)

        results = env.get_15min_segment_results(0, 30)

        assert 'pnl' in results
        assert 'n_trades' in results
        assert 'win_rate' in results

    def test_segment_results_filters_by_step_range(self, base_env_data):
        day_data, prices = base_env_data
        env = LowLevelEnv(day_data, prices=prices)
        env.reset()

        # Manually add trades to history
        env.trade_history.append({'step': 5, 'pnl': 1000})
        env.trade_history.append({'step': 10, 'pnl': -500})
        env.trade_history.append({'step': 20, 'pnl': 2000})

        # Get segment [0, 15)
        results = env.get_15min_segment_results(0, 15)

        # Should include trades at step 5 and 10, but not 20
        assert results['n_trades'] == 2
        assert results['pnl'] == 500  # 1000 - 500

    def test_segment_results_calculates_win_rate(self, base_env_data):
        day_data, prices = base_env_data
        env = LowLevelEnv(day_data, prices=prices)
        env.reset()

        env.trade_history.append({'step': 5, 'pnl': 1000})
        env.trade_history.append({'step': 10, 'pnl': 500})
        env.trade_history.append({'step': 15, 'pnl': -300})

        results = env.get_15min_segment_results(0, 20)

        # 2 wins out of 3 trades
        assert results['win_rate'] == pytest.approx(2/3, abs=0.01)

    def test_segment_results_handles_no_trades(self, base_env_data):
        day_data, prices = base_env_data
        env = LowLevelEnv(day_data, prices=prices)
        env.reset()

        results = env.get_15min_segment_results(0, 15)

        assert results['pnl'] == 0
        assert results['n_trades'] == 0
        # Win rate with no trades = 0/1 = 0
        assert results['win_rate'] == 0.0


class TestLowLevelEnvIntegration:
    def test_step_works_with_risk_budget(self, base_env_data):
        day_data, prices = base_env_data
        env = LowLevelEnv(day_data, prices=prices)
        env.reset()

        env.set_risk_budget(0.5)

        # Should be able to step without errors
        obs, reward, terminated, truncated, info = env.step(Action.HOLD)

        assert obs is not None
        assert isinstance(reward, (int, float, np.number))

    def test_full_episode_with_varying_risk_budget(self, base_env_data):
        day_data, prices = base_env_data
        env = LowLevelEnv(day_data, prices=prices)
        env.reset()

        # Simulate 15-min segments with different risk budgets
        segment_length = 15
        risk_budgets = [1.0, 0.5, 0.0, 1.0]

        for budget in risk_budgets:
            env.set_risk_budget(budget)

            for _ in range(min(segment_length, 50)):  # Limited steps for testing
                obs, reward, terminated, truncated, info = env.step(Action.HOLD)
                if terminated:
                    break

        # Should complete without errors
        assert True


class TestEdgeCases:
    def test_high_level_env_with_no_low_level_results(self, high_level_data):
        """Should handle missing low-level results gracefully."""
        env = HighLevelEnv(high_level_data)
        env.reset()

        obs, reward, terminated, truncated, info = env.step(HighLevelAction.AGGRESSIVE)

        # Reward should be 0 (no low-level PnL)
        assert reward == 0.0

    def test_low_level_env_with_minimal_data(self):
        """Should handle very short episodes."""
        day_data = np.random.randn(10, 25).astype(np.float32)
        prices = np.random.randn(10, 4).astype(np.float32) + 350

        env = LowLevelEnv(day_data, prices=prices)
        env.reset()

        # Should not crash
        env.set_risk_budget(0.5)
        obs, reward, terminated, truncated, info = env.step(Action.HOLD)
        assert obs is not None
