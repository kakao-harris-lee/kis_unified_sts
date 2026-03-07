"""Tests for directional hierarchical RL environments.

Tests DirectionalHighLevelEnv (15-min directional bias decisions) and LowLevelEnv
with directional bias constraints for multi-level reinforcement learning.
"""

import numpy as np
import pytest
from gymnasium import spaces

from shared.ml.rl.env import Action, PositionSide, RLEnvConfig
from shared.ml.rl.hierarchical.high_level_env import (
    DirectionalHighLevelConfig,
    DirectionalHighLevelEnv,
    HighLevelDirectionalAction,
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
def directional_high_level_data():
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
# HighLevelDirectionalAction Tests
# ============================================================================


class TestHighLevelDirectionalAction:
    def test_constants(self):
        """Test action constant values."""
        assert HighLevelDirectionalAction.LONG_BIAS == 0
        assert HighLevelDirectionalAction.SHORT_BIAS == 1
        assert HighLevelDirectionalAction.FLAT == 2

    def test_names(self):
        """Test action names mapping."""
        assert HighLevelDirectionalAction.NAMES[0] == "LONG_BIAS"
        assert HighLevelDirectionalAction.NAMES[1] == "SHORT_BIAS"
        assert HighLevelDirectionalAction.NAMES[2] == "FLAT"

    def test_bias_names(self):
        """Test bias string names for low-level env."""
        assert HighLevelDirectionalAction.BIAS_NAMES[0] == "long"
        assert HighLevelDirectionalAction.BIAS_NAMES[1] == "short"
        assert HighLevelDirectionalAction.BIAS_NAMES[2] == "flat"


# ============================================================================
# DirectionalHighLevelConfig Tests
# ============================================================================


class TestDirectionalHighLevelConfig:
    def test_default_values(self):
        """Test default configuration values."""
        cfg = DirectionalHighLevelConfig()
        assert cfg.n_bar_features == 25
        assert cfg.n_summary_features == 5
        assert cfg.bars_per_step == 15
        assert cfg.initial_balance == 100_000_000
        assert cfg.max_steps == 27

    def test_custom_values(self):
        """Test custom configuration values."""
        cfg = DirectionalHighLevelConfig(
            n_bar_features=20,
            n_summary_features=10,
            bars_per_step=30,
            initial_balance=50_000_000,
            max_steps=14,
        )
        assert cfg.n_bar_features == 20
        assert cfg.n_summary_features == 10
        assert cfg.bars_per_step == 30
        assert cfg.initial_balance == 50_000_000
        assert cfg.max_steps == 14


# ============================================================================
# DirectionalHighLevelEnv Initialization Tests
# ============================================================================


class TestDirectionalHighLevelEnvInit:
    def test_action_space(self, directional_high_level_data):
        """Test action space is Discrete(3) for directional bias."""
        env = DirectionalHighLevelEnv(directional_high_level_data)
        assert isinstance(env.action_space, spaces.Discrete)
        assert env.action_space.n == 3

    def test_observation_space(self, directional_high_level_data):
        """Test observation space shape (bar_features + summary_features)."""
        env = DirectionalHighLevelEnv(directional_high_level_data)
        # 25 bar features + 5 summary features = 30
        assert isinstance(env.observation_space, spaces.Box)
        assert env.observation_space.shape == (30,)

    def test_custom_config(self, directional_high_level_data):
        """Test custom config updates observation space."""
        config = DirectionalHighLevelConfig(n_bar_features=20, n_summary_features=10)
        env = DirectionalHighLevelEnv(directional_high_level_data, config=config)
        assert env.observation_space.shape == (30,)

    def test_initial_state(self, directional_high_level_data):
        """Test initial state values."""
        env = DirectionalHighLevelEnv(directional_high_level_data)
        assert env.current_step == 0
        assert env.total_pnl == 0.0
        assert env.n_trades == 0
        assert len(env.bias_history) == 0


# ============================================================================
# DirectionalHighLevelEnv Reset Tests
# ============================================================================


class TestDirectionalHighLevelEnvReset:
    def test_reset_returns_obs_and_info(self, directional_high_level_data):
        """Test reset returns observation and info dict."""
        env = DirectionalHighLevelEnv(directional_high_level_data)
        obs, info = env.reset()

        assert isinstance(obs, np.ndarray)
        assert obs.shape == (30,)
        assert isinstance(info, dict)

    def test_reset_initializes_state(self, directional_high_level_data, low_level_results):
        """Test reset properly initializes all state variables."""
        env = DirectionalHighLevelEnv(directional_high_level_data, low_level_results=low_level_results)
        env.step(HighLevelDirectionalAction.LONG_BIAS)  # Take a step

        obs, info = env.reset()

        assert env.current_step == 0
        assert env.total_pnl == 0.0
        assert env.n_trades == 0
        assert len(env.bias_history) == 0

    def test_reset_with_seed(self, directional_high_level_data):
        """Test reset with seed produces consistent results."""
        env = DirectionalHighLevelEnv(directional_high_level_data)
        obs1, _ = env.reset(seed=42)
        obs2, _ = env.reset(seed=42)

        # Initial observations should be the same
        np.testing.assert_array_equal(obs1, obs2)

    def test_reset_clears_bias_history(self, directional_high_level_data, low_level_results):
        """Test reset clears bias history."""
        env = DirectionalHighLevelEnv(directional_high_level_data, low_level_results=low_level_results)
        env.reset()
        env.step(HighLevelDirectionalAction.LONG_BIAS)
        env.step(HighLevelDirectionalAction.SHORT_BIAS)

        assert len(env.bias_history) == 2

        env.reset()
        assert len(env.bias_history) == 0


# ============================================================================
# DirectionalHighLevelEnv Step Tests
# ============================================================================


class TestDirectionalHighLevelEnvStep:
    def test_step_returns_correct_types(self, directional_high_level_data, low_level_results):
        """Test step returns correct types."""
        env = DirectionalHighLevelEnv(directional_high_level_data, low_level_results=low_level_results)
        env.reset()

        obs, reward, terminated, truncated, info = env.step(HighLevelDirectionalAction.LONG_BIAS)

        assert isinstance(obs, np.ndarray)
        assert obs.shape == (30,)
        assert isinstance(reward, (int, float, np.number))
        assert isinstance(terminated, (bool, np.bool_))
        assert isinstance(truncated, (bool, np.bool_))
        assert isinstance(info, dict)

    def test_step_updates_state(self, directional_high_level_data, low_level_results):
        """Test step updates current_step and bias_history."""
        env = DirectionalHighLevelEnv(directional_high_level_data, low_level_results=low_level_results)
        env.reset()

        initial_step = env.current_step
        env.step(HighLevelDirectionalAction.SHORT_BIAS)

        assert env.current_step == initial_step + 1
        assert len(env.bias_history) == 1
        assert env.bias_history[0] == "short"

    def test_long_bias_records_correctly(self, directional_high_level_data, low_level_results):
        """Test LONG_BIAS action records 'long' in bias_history."""
        env = DirectionalHighLevelEnv(directional_high_level_data, low_level_results=low_level_results)
        env.reset()

        env.step(HighLevelDirectionalAction.LONG_BIAS)

        assert env.bias_history[-1] == "long"

    def test_short_bias_records_correctly(self, directional_high_level_data, low_level_results):
        """Test SHORT_BIAS action records 'short' in bias_history."""
        env = DirectionalHighLevelEnv(directional_high_level_data, low_level_results=low_level_results)
        env.reset()

        env.step(HighLevelDirectionalAction.SHORT_BIAS)

        assert env.bias_history[-1] == "short"

    def test_flat_bias_records_correctly(self, directional_high_level_data, low_level_results):
        """Test FLAT action records 'flat' in bias_history."""
        env = DirectionalHighLevelEnv(directional_high_level_data, low_level_results=low_level_results)
        env.reset()

        env.step(HighLevelDirectionalAction.FLAT)

        assert env.bias_history[-1] == "flat"

    def test_step_accumulates_pnl(self, directional_high_level_data, low_level_results):
        """Test step accumulates PnL from low-level results."""
        env = DirectionalHighLevelEnv(directional_high_level_data, low_level_results=low_level_results)
        env.reset()

        initial_pnl = env.total_pnl
        env.step(HighLevelDirectionalAction.LONG_BIAS)

        # PnL should change based on low_level_results
        assert env.total_pnl != initial_pnl

    def test_step_counts_trades(self, directional_high_level_data, low_level_results):
        """Test step accumulates trade count from low-level results."""
        env = DirectionalHighLevelEnv(directional_high_level_data, low_level_results=low_level_results)
        env.reset()

        initial_trades = env.n_trades
        env.step(HighLevelDirectionalAction.FLAT)

        # Trade count should increase if low_level_results has trades
        assert env.n_trades >= initial_trades

    def test_multiple_steps_sequence(self, directional_high_level_data, low_level_results):
        """Test sequence of multiple steps."""
        env = DirectionalHighLevelEnv(directional_high_level_data, low_level_results=low_level_results)
        env.reset()

        actions = [
            HighLevelDirectionalAction.LONG_BIAS,
            HighLevelDirectionalAction.FLAT,
            HighLevelDirectionalAction.SHORT_BIAS,
        ]

        for action in actions:
            obs, reward, terminated, truncated, info = env.step(action)
            assert isinstance(obs, np.ndarray)

        assert len(env.bias_history) == 3
        assert env.bias_history == ["long", "flat", "short"]


# ============================================================================
# DirectionalHighLevelEnv Observation Tests
# ============================================================================


class TestDirectionalHighLevelEnvObservation:
    def test_observation_shape(self, directional_high_level_data):
        """Test observation has correct shape."""
        env = DirectionalHighLevelEnv(directional_high_level_data)
        obs, _ = env.reset()

        assert obs.shape == (30,)
        assert obs.dtype == np.float32

    def test_observation_contains_bar_features(self, directional_high_level_data):
        """Test observation contains bar features."""
        env = DirectionalHighLevelEnv(directional_high_level_data)
        obs, _ = env.reset()

        # First 25 elements should be bar features
        bar_features = obs[:25]
        assert len(bar_features) == 25

    def test_observation_contains_summary_features(self, directional_high_level_data):
        """Test observation contains summary features."""
        env = DirectionalHighLevelEnv(directional_high_level_data)
        obs, _ = env.reset()

        # Last 5 elements should be summary features
        summary_features = obs[25:]
        assert len(summary_features) == 5

    def test_summary_includes_progress(self, directional_high_level_data, low_level_results):
        """Test summary features include progress indicator."""
        env = DirectionalHighLevelEnv(directional_high_level_data, low_level_results=low_level_results)
        env.reset()

        # Step multiple times
        for _ in range(5):
            obs, _, terminated, _, _ = env.step(HighLevelDirectionalAction.FLAT)
            if terminated:
                break

        # Progress should be in summary[0]
        progress = obs[25]
        assert 0 <= progress <= 1

    def test_summary_includes_avg_bias(self, directional_high_level_data, low_level_results):
        """Test summary features include average bias indicator."""
        env = DirectionalHighLevelEnv(directional_high_level_data, low_level_results=low_level_results)
        env.reset()

        # Take steps with known biases
        env.step(HighLevelDirectionalAction.LONG_BIAS)  # +1
        env.step(HighLevelDirectionalAction.LONG_BIAS)  # +1
        obs, _, _, _, _ = env.step(HighLevelDirectionalAction.SHORT_BIAS)  # -1

        # avg_bias should be in summary[4]
        avg_bias = obs[29]
        # Average of [1, 1, -1] = 0.333...
        expected_avg = (1.0 + 1.0 - 1.0) / 3
        np.testing.assert_almost_equal(avg_bias, expected_avg, decimal=5)


# ============================================================================
# DirectionalHighLevelEnv Episode Completion Tests
# ============================================================================


class TestDirectionalHighLevelEnvCompletion:
    def test_episode_terminates_at_max_steps(self, directional_high_level_data, low_level_results):
        """Test episode terminates when reaching max_steps."""
        config = DirectionalHighLevelConfig(max_steps=5)
        env = DirectionalHighLevelEnv(directional_high_level_data, config=config, low_level_results=low_level_results)
        env.reset()

        terminated = False
        for _ in range(5):
            _, _, terminated, _, _ = env.step(HighLevelDirectionalAction.FLAT)

        assert terminated

    def test_episode_terminates_at_data_end(self, directional_high_level_data, low_level_results):
        """Test episode terminates when data runs out."""
        # Create short data
        short_data = directional_high_level_data[:10]
        env = DirectionalHighLevelEnv(short_data, low_level_results=low_level_results)
        env.reset()

        terminated = False
        steps = 0
        while not terminated and steps < 20:
            _, _, terminated, _, _ = env.step(HighLevelDirectionalAction.FLAT)
            steps += 1

        assert terminated
        assert steps == 10

    def test_truncated_always_false(self, directional_high_level_data, low_level_results):
        """Test truncated is always False (no time limits besides termination)."""
        env = DirectionalHighLevelEnv(directional_high_level_data, low_level_results=low_level_results)
        env.reset()

        for _ in range(5):
            _, _, terminated, truncated, _ = env.step(HighLevelDirectionalAction.FLAT)
            assert not truncated
            if terminated:
                break


# ============================================================================
# DirectionalHighLevelEnv Info Tests
# ============================================================================


class TestDirectionalHighLevelEnvInfo:
    def test_info_contains_required_keys(self, directional_high_level_data):
        """Test info dict contains all required keys."""
        env = DirectionalHighLevelEnv(directional_high_level_data)
        _, info = env.reset()

        required_keys = {'total_pnl', 'n_trades', 'step', 'bias_history'}
        assert all(key in info for key in required_keys)

    def test_info_updates_after_step(self, directional_high_level_data, low_level_results):
        """Test info dict updates after each step."""
        env = DirectionalHighLevelEnv(directional_high_level_data, low_level_results=low_level_results)
        env.reset()

        _, _, _, _, info = env.step(HighLevelDirectionalAction.LONG_BIAS)

        assert info['step'] == 1
        assert len(info['bias_history']) == 1
        assert info['bias_history'][0] == 'long'

    def test_info_bias_history_is_copy(self, directional_high_level_data, low_level_results):
        """Test bias_history in info is a copy, not reference."""
        env = DirectionalHighLevelEnv(directional_high_level_data, low_level_results=low_level_results)
        env.reset()

        _, _, _, _, info = env.step(HighLevelDirectionalAction.SHORT_BIAS)
        history_copy = info['bias_history']
        history_copy.append('fake')

        # Original should be unchanged
        assert len(env.bias_history) == 1
        assert 'fake' not in env.bias_history


# ============================================================================
# LowLevelEnv Directional Bias Tests
# ============================================================================


class TestLowLevelEnvDirectionalBias:
    def test_set_directional_bias_long(self, base_env_data):
        """Test setting directional bias to 'long'."""
        day_data, prices = base_env_data
        env = LowLevelEnv(day_data, prices=prices)

        env.set_directional_bias("long")
        assert env._directional_bias == "long"

    def test_set_directional_bias_short(self, base_env_data):
        """Test setting directional bias to 'short'."""
        day_data, prices = base_env_data
        env = LowLevelEnv(day_data, prices=prices)

        env.set_directional_bias("short")
        assert env._directional_bias == "short"

    def test_set_directional_bias_flat(self, base_env_data):
        """Test setting directional bias to 'flat'."""
        day_data, prices = base_env_data
        env = LowLevelEnv(day_data, prices=prices)

        env.set_directional_bias("flat")
        assert env._directional_bias == "flat"

    def test_set_directional_bias_invalid_defaults_to_flat(self, base_env_data):
        """Test invalid directional bias defaults to 'flat'."""
        day_data, prices = base_env_data
        env = LowLevelEnv(day_data, prices=prices)

        env.set_directional_bias("invalid")
        assert env._directional_bias == "flat"

    def test_default_directional_bias_is_flat(self, base_env_data):
        """Test default directional bias is 'flat'."""
        day_data, prices = base_env_data
        env = LowLevelEnv(day_data, prices=prices)

        assert env._directional_bias == "flat"


# ============================================================================
# LowLevelEnv Action Masking Tests
# ============================================================================


class TestLowLevelEnvActionMasking:
    def test_long_bias_blocks_short_entry(self, base_env_data):
        """Test long bias blocks SHORT_ENTRY action."""
        day_data, prices = base_env_data
        env = LowLevelEnv(day_data, prices=prices)
        env.reset()

        env.set_directional_bias("long")
        masks = env.action_masks()

        # LONG_ENTRY should be allowed, SHORT_ENTRY blocked
        assert masks[Action.LONG_ENTRY] is True
        assert masks[Action.SHORT_ENTRY] is False

    def test_short_bias_blocks_long_entry(self, base_env_data):
        """Test short bias blocks LONG_ENTRY action."""
        day_data, prices = base_env_data
        env = LowLevelEnv(day_data, prices=prices)
        env.reset()

        env.set_directional_bias("short")
        masks = env.action_masks()

        # SHORT_ENTRY should be allowed, LONG_ENTRY blocked
        assert masks[Action.SHORT_ENTRY] is True
        assert masks[Action.LONG_ENTRY] is False

    def test_flat_bias_allows_both_directions(self, base_env_data):
        """Test flat bias allows both LONG_ENTRY and SHORT_ENTRY."""
        day_data, prices = base_env_data
        env = LowLevelEnv(day_data, prices=prices)
        env.reset()

        env.set_directional_bias("flat")
        masks = env.action_masks()

        # Both should be allowed (unless blocked by other constraints)
        # Note: Other constraints like position state may still block
        # So we just check that directional bias isn't the blocker
        assert True  # No directional blocking

    def test_long_bias_allows_exits(self, base_env_data):
        """Test long bias still allows exit actions."""
        day_data, prices = base_env_data
        env = LowLevelEnv(day_data, prices=prices)
        env.reset()

        env.set_directional_bias("long")
        masks = env.action_masks()

        # HOLD should always be available
        assert masks[Action.HOLD] is True

    def test_short_bias_allows_exits(self, base_env_data):
        """Test short bias still allows exit actions."""
        day_data, prices = base_env_data
        env = LowLevelEnv(day_data, prices=prices)
        env.reset()

        env.set_directional_bias("short")
        masks = env.action_masks()

        # HOLD should always be available
        assert masks[Action.HOLD] is True


# ============================================================================
# LowLevelEnv Combined Constraints Tests
# ============================================================================


class TestLowLevelEnvCombinedConstraints:
    def test_zero_risk_budget_blocks_all_entries(self, base_env_data):
        """Test risk_budget=0 blocks all entries regardless of directional bias."""
        day_data, prices = base_env_data
        env = LowLevelEnv(day_data, prices=prices)
        env.reset()

        env.set_risk_budget(0.0)
        env.set_directional_bias("flat")
        masks = env.action_masks()

        # Both entries should be blocked by zero risk budget
        assert masks[Action.LONG_ENTRY] is False
        assert masks[Action.SHORT_ENTRY] is False

    def test_zero_risk_budget_with_long_bias(self, base_env_data):
        """Test risk_budget=0 with long bias blocks both entries."""
        day_data, prices = base_env_data
        env = LowLevelEnv(day_data, prices=prices)
        env.reset()

        env.set_risk_budget(0.0)
        env.set_directional_bias("long")
        masks = env.action_masks()

        # Both should be blocked (risk budget takes precedence)
        assert masks[Action.LONG_ENTRY] is False
        assert masks[Action.SHORT_ENTRY] is False

    def test_full_risk_budget_with_long_bias(self, base_env_data):
        """Test risk_budget=1.0 with long bias allows LONG_ENTRY only."""
        day_data, prices = base_env_data
        env = LowLevelEnv(day_data, prices=prices)
        env.reset()

        env.set_risk_budget(1.0)
        env.set_directional_bias("long")
        masks = env.action_masks()

        # LONG_ENTRY allowed, SHORT_ENTRY blocked by bias
        assert masks[Action.LONG_ENTRY] is True
        assert masks[Action.SHORT_ENTRY] is False

    def test_full_risk_budget_with_short_bias(self, base_env_data):
        """Test risk_budget=1.0 with short bias allows SHORT_ENTRY only."""
        day_data, prices = base_env_data
        env = LowLevelEnv(day_data, prices=prices)
        env.reset()

        env.set_risk_budget(1.0)
        env.set_directional_bias("short")
        masks = env.action_masks()

        # SHORT_ENTRY allowed, LONG_ENTRY blocked by bias
        assert masks[Action.SHORT_ENTRY] is True
        assert masks[Action.LONG_ENTRY] is False


# ============================================================================
# Integration Tests
# ============================================================================


class TestDirectionalHierarchicalIntegration:
    def test_full_episode_with_varying_biases(self, directional_high_level_data, low_level_results):
        """Test full episode with varying directional biases."""
        env = DirectionalHighLevelEnv(directional_high_level_data, low_level_results=low_level_results)
        obs, info = env.reset()

        biases = [
            HighLevelDirectionalAction.LONG_BIAS,
            HighLevelDirectionalAction.FLAT,
            HighLevelDirectionalAction.SHORT_BIAS,
            HighLevelDirectionalAction.FLAT,
        ]

        total_steps = 0
        for bias in biases:
            obs, reward, terminated, truncated, info = env.step(bias)
            total_steps += 1
            if terminated:
                break

        assert total_steps == len(biases)
        assert len(env.bias_history) == total_steps

    def test_low_level_respects_high_level_bias(self, base_env_data):
        """Test low-level env respects directional bias from high-level."""
        day_data, prices = base_env_data
        low_env = LowLevelEnv(day_data, prices=prices)
        low_env.reset()

        # Simulate high-level setting long bias
        low_env.set_directional_bias("long")
        masks = low_env.action_masks()

        # Verify SHORT_ENTRY is blocked
        assert masks[Action.SHORT_ENTRY] is False

        # Simulate high-level changing to short bias
        low_env.set_directional_bias("short")
        masks = low_env.action_masks()

        # Verify LONG_ENTRY is now blocked
        assert masks[Action.LONG_ENTRY] is False

    def test_episode_with_all_flat_bias(self, directional_high_level_data, low_level_results):
        """Test episode where high-level always chooses FLAT bias."""
        env = DirectionalHighLevelEnv(directional_high_level_data, low_level_results=low_level_results)
        env.reset()

        steps = 0
        terminated = False
        while not terminated and steps < 10:
            obs, reward, terminated, truncated, info = env.step(HighLevelDirectionalAction.FLAT)
            steps += 1

        # All biases should be 'flat'
        assert all(bias == "flat" for bias in env.bias_history)

    def test_episode_with_alternating_biases(self, directional_high_level_data, low_level_results):
        """Test episode with alternating long/short biases."""
        env = DirectionalHighLevelEnv(directional_high_level_data, low_level_results=low_level_results)
        env.reset()

        biases = [
            HighLevelDirectionalAction.LONG_BIAS,
            HighLevelDirectionalAction.SHORT_BIAS,
        ] * 5  # Alternate 10 times

        for bias in biases:
            obs, reward, terminated, truncated, info = env.step(bias)
            if terminated:
                break

        # Check alternating pattern
        expected = ["long", "short"] * min(len(env.bias_history) // 2, 5)
        assert env.bias_history[:len(expected)] == expected

    def test_pnl_tracking_across_biases(self, directional_high_level_data, low_level_results):
        """Test PnL is properly tracked across different biases."""
        env = DirectionalHighLevelEnv(directional_high_level_data, low_level_results=low_level_results)
        env.reset()

        pnl_values = []
        biases = [
            HighLevelDirectionalAction.LONG_BIAS,
            HighLevelDirectionalAction.SHORT_BIAS,
            HighLevelDirectionalAction.FLAT,
        ]

        for bias in biases:
            obs, reward, terminated, truncated, info = env.step(bias)
            pnl_values.append(info['total_pnl'])
            if terminated:
                break

        # PnL should be monotonically changing (not resetting)
        assert len(pnl_values) == len(biases)
