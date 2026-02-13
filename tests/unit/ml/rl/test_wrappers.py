"""Tests for ContinuousActionWrapper.

Tests continuous action space wrapper for SAC algorithm,
verifying action mapping, space transformation, and integration
with FuturesTradingEnv.
"""

import numpy as np
import pytest
from gymnasium import spaces

from shared.ml.rl.env import Action, FuturesTradingEnv, PositionSide, RLEnvConfig
from shared.ml.rl.wrappers import ContinuousActionWrapper


@pytest.fixture
def base_env_data():
    """Generate minimal FuturesTradingEnv test data."""
    n_steps = 100
    n_features = 25

    # Market features (25 columns)
    day_data = np.random.randn(n_steps, n_features).astype(np.float32)
    # Normalize to reasonable ranges
    day_data[:, 0] = np.clip(day_data[:, 0] * 0.001, -0.01, 0.01)  # returns
    day_data[:, 1:] = np.clip(day_data[:, 1:], -3, 3)  # other features

    # OHLC prices
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
def base_env(base_env_data):
    """Create base FuturesTradingEnv."""
    day_data, prices = base_env_data
    config = RLEnvConfig(
        initial_balance=10_000_000,
        max_contracts=1,
        commission_rate=0.00003,
    )
    return FuturesTradingEnv(day_data=day_data, config=config, prices=prices)


@pytest.fixture
def wrapped_env(base_env):
    """Create wrapped environment with default thresholds."""
    return ContinuousActionWrapper(base_env)


class TestContinuousActionWrapperInit:
    def test_action_space_is_box(self, wrapped_env):
        assert isinstance(wrapped_env.action_space, spaces.Box)

    def test_action_space_bounds(self, wrapped_env):
        assert wrapped_env.action_space.low[0] == -1.0
        assert wrapped_env.action_space.high[0] == 1.0

    def test_action_space_shape(self, wrapped_env):
        assert wrapped_env.action_space.shape == (1,)

    def test_action_space_dtype(self, wrapped_env):
        assert wrapped_env.action_space.dtype == np.float32

    def test_observation_space_unchanged(self, base_env, wrapped_env):
        # Wrapper should not change observation space
        assert wrapped_env.observation_space == base_env.observation_space

    def test_custom_thresholds(self, base_env):
        wrapper = ContinuousActionWrapper(
            base_env, entry_threshold=0.5, exit_threshold=0.2
        )
        assert wrapper.entry_threshold == 0.5
        assert wrapper.exit_threshold == 0.2


class TestActionMappingFlat:
    """Test action mapping when position is FLAT."""

    def test_strong_positive_maps_to_long_entry(self, wrapped_env):
        wrapped_env.env.position = PositionSide.FLAT
        action = wrapped_env._map_to_discrete(0.8)
        assert action == Action.LONG_ENTRY

    def test_strong_negative_maps_to_short_entry(self, wrapped_env):
        wrapped_env.env.position = PositionSide.FLAT
        action = wrapped_env._map_to_discrete(-0.8)
        assert action == Action.SHORT_ENTRY

    def test_threshold_boundary_long(self, wrapped_env):
        wrapped_env.env.position = PositionSide.FLAT
        # Just above threshold
        action = wrapped_env._map_to_discrete(0.31)
        assert action == Action.LONG_ENTRY
        # Just below threshold
        action = wrapped_env._map_to_discrete(0.29)
        assert action == Action.HOLD

    def test_threshold_boundary_short(self, wrapped_env):
        wrapped_env.env.position = PositionSide.FLAT
        # Just below negative threshold
        action = wrapped_env._map_to_discrete(-0.31)
        assert action == Action.SHORT_ENTRY
        # Just above negative threshold
        action = wrapped_env._map_to_discrete(-0.29)
        assert action == Action.HOLD

    def test_zero_maps_to_hold(self, wrapped_env):
        wrapped_env.env.position = PositionSide.FLAT
        action = wrapped_env._map_to_discrete(0.0)
        assert action == Action.HOLD

    def test_small_values_map_to_hold(self, wrapped_env):
        wrapped_env.env.position = PositionSide.FLAT
        for val in [0.1, -0.1, 0.2, -0.2]:
            action = wrapped_env._map_to_discrete(val)
            assert action == Action.HOLD


class TestActionMappingLong:
    """Test action mapping when position is LONG."""

    def test_negative_below_exit_threshold_maps_to_exit(self, wrapped_env):
        wrapped_env.env.position = PositionSide.LONG
        action = wrapped_env._map_to_discrete(-0.5)
        assert action == Action.LONG_EXIT

    def test_exit_threshold_boundary(self, wrapped_env):
        wrapped_env.env.position = PositionSide.LONG
        # Just below exit threshold (more negative)
        action = wrapped_env._map_to_discrete(-0.11)
        assert action == Action.LONG_EXIT
        # Just above exit threshold
        action = wrapped_env._map_to_discrete(-0.09)
        assert action == Action.HOLD

    def test_positive_maps_to_hold(self, wrapped_env):
        wrapped_env.env.position = PositionSide.LONG
        action = wrapped_env._map_to_discrete(0.8)
        assert action == Action.HOLD

    def test_zero_maps_to_hold(self, wrapped_env):
        wrapped_env.env.position = PositionSide.LONG
        action = wrapped_env._map_to_discrete(0.0)
        assert action == Action.HOLD


class TestActionMappingShort:
    """Test action mapping when position is SHORT."""

    def test_positive_above_exit_threshold_maps_to_exit(self, wrapped_env):
        wrapped_env.env.position = PositionSide.SHORT
        action = wrapped_env._map_to_discrete(0.5)
        assert action == Action.SHORT_EXIT

    def test_exit_threshold_boundary(self, wrapped_env):
        wrapped_env.env.position = PositionSide.SHORT
        # Just above exit threshold
        action = wrapped_env._map_to_discrete(0.11)
        assert action == Action.SHORT_EXIT
        # Just below exit threshold
        action = wrapped_env._map_to_discrete(0.09)
        assert action == Action.HOLD

    def test_negative_maps_to_hold(self, wrapped_env):
        wrapped_env.env.position = PositionSide.SHORT
        action = wrapped_env._map_to_discrete(-0.8)
        assert action == Action.HOLD

    def test_zero_maps_to_hold(self, wrapped_env):
        wrapped_env.env.position = PositionSide.SHORT
        action = wrapped_env._map_to_discrete(0.0)
        assert action == Action.HOLD


class TestStepIntegration:
    def test_step_accepts_continuous_action(self, wrapped_env):
        wrapped_env.reset(seed=None)
        action = np.array([0.5], dtype=np.float32)
        obs, reward, terminated, truncated, info = wrapped_env.step(action)

        assert obs is not None
        assert isinstance(reward, (int, float))
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)
        assert isinstance(info, dict)

    def test_step_clips_out_of_bounds_action(self, wrapped_env):
        """Actions outside [-1, 1] should be clipped."""
        wrapped_env.reset(seed=None)
        wrapped_env.env.position = PositionSide.FLAT

        # Action > 1 should be clipped to 1, still trigger LONG_ENTRY
        action = np.array([2.0], dtype=np.float32)
        obs, reward, terminated, truncated, info = wrapped_env.step(action)
        assert obs is not None  # Should not error

        # Action < -1 should be clipped to -1, still trigger SHORT_ENTRY
        wrapped_env.reset(seed=None)
        action = np.array([-2.0], dtype=np.float32)
        obs, reward, terminated, truncated, info = wrapped_env.step(action)
        assert obs is not None

    def test_step_sequence_flat_to_long(self, wrapped_env):
        """Test sequence: FLAT -> LONG entry -> LONG exit."""
        wrapped_env.reset(seed=None)

        # Initial position is FLAT
        assert wrapped_env.env.position == PositionSide.FLAT

        # Strong positive -> LONG entry
        action = np.array([0.8], dtype=np.float32)
        obs, reward, terminated, truncated, info = wrapped_env.step(action)

        # Check if position changed (depends on base env logic)
        # This is an integration test, so we just verify no errors
        assert obs is not None

        # If we're now LONG, negative action should trigger exit
        if wrapped_env.env.position == PositionSide.LONG:
            action = np.array([-0.8], dtype=np.float32)
            obs, reward, terminated, truncated, info = wrapped_env.step(action)
            assert obs is not None

    def test_step_returns_correct_types(self, wrapped_env):
        wrapped_env.reset(seed=None)
        action = np.array([0.0], dtype=np.float32)
        obs, reward, terminated, truncated, info = wrapped_env.step(action)

        assert isinstance(obs, np.ndarray)
        assert obs.dtype == np.float32
        assert isinstance(reward, (int, float, np.number))
        assert isinstance(terminated, (bool, np.bool_))
        assert isinstance(truncated, (bool, np.bool_))
        assert isinstance(info, dict)


class TestResetIntegration:
    def test_reset_works(self, wrapped_env):
        obs, info = wrapped_env.reset(seed=None)
        assert obs is not None
        assert isinstance(obs, np.ndarray)
        assert isinstance(info, dict)

    def test_reset_with_seed(self, wrapped_env):
        obs1, info1 = wrapped_env.reset(seed=42)
        obs2, info2 = wrapped_env.reset(seed=42)
        # With same seed, initial obs should be identical
        np.testing.assert_array_equal(obs1, obs2)


class TestCustomThresholds:
    def test_higher_entry_threshold_requires_stronger_signal(self, base_env):
        wrapper = ContinuousActionWrapper(base_env, entry_threshold=0.7)
        wrapper.env.position = PositionSide.FLAT

        # 0.5 is not enough now
        action = wrapper._map_to_discrete(0.5)
        assert action == Action.HOLD

        # 0.8 is enough
        action = wrapper._map_to_discrete(0.8)
        assert action == Action.LONG_ENTRY

    def test_lower_exit_threshold_exits_earlier(self, base_env):
        wrapper = ContinuousActionWrapper(base_env, exit_threshold=0.05)
        wrapper.env.position = PositionSide.LONG

        # Small negative action triggers exit
        action = wrapper._map_to_discrete(-0.06)
        assert action == Action.LONG_EXIT

        # Very small negative action doesn't
        action = wrapper._map_to_discrete(-0.04)
        assert action == Action.HOLD


class TestEdgeCases:
    def test_exactly_at_thresholds(self, wrapped_env):
        """Test behavior exactly at threshold values."""
        wrapped_env.env.position = PositionSide.FLAT

        # Exactly at entry threshold (0.3)
        action = wrapped_env._map_to_discrete(0.3)
        # Should not trigger (> is used, not >=)
        assert action == Action.HOLD

        # Just past threshold
        action = wrapped_env._map_to_discrete(0.300001)
        assert action == Action.LONG_ENTRY

    def test_unknown_position_defaults_to_hold(self, wrapped_env):
        """If position is somehow invalid, should return HOLD."""
        # Manually set invalid position
        wrapped_env.env.position = 999
        action = wrapped_env._map_to_discrete(0.8)
        assert action == Action.HOLD

    def test_array_input_extracts_first_element(self, wrapped_env):
        """Step should handle multi-element arrays by taking first."""
        wrapped_env.reset(seed=None)
        # Pass multi-element array (though action_space is (1,))
        action = np.array([0.5, 0.3, 0.1], dtype=np.float32)
        obs, reward, terminated, truncated, info = wrapped_env.step(action)
        assert obs is not None  # Should use action[0] = 0.5


class TestWrapperAttributes:
    def test_wrapper_exposes_unwrapped_env(self, wrapped_env, base_env):
        """Wrapper should provide access to base environment."""
        assert wrapped_env.env is base_env
        assert wrapped_env.unwrapped is base_env.unwrapped

    def test_wrapper_preserves_metadata(self, wrapped_env, base_env):
        """Wrapper should preserve environment metadata."""
        # Gymnasium wrappers should preserve metadata
        assert hasattr(wrapped_env, 'metadata')
