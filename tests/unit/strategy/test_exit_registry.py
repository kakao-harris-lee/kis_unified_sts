"""Tests for Exit Strategy Registry."""

import pytest
from shared.strategy.registry import ExitRegistry, register_builtin_components


@pytest.fixture(autouse=True)
def setup_registry():
    """Ensure builtin components are registered before each test."""
    register_builtin_components()
    yield


class TestExitRegistry:
    """Test ExitRegistry functionality."""

    def test_atr_trailing_exit_registered(self):
        """atr_trailing exit strategy should be registered."""
        assert "atr_trailing" in ExitRegistry.list_all()

    def test_atr_trailing_exit_creation(self):
        """atr_trailing exit strategy should be creatable."""
        config = {
            "atr_multiplier": 2.0,
            "initial_stop_atr": 1.5,
            "max_hold_minutes": 30,
            "stop_loss_ticks": 10,
            "take_profit_ticks": 20,
        }

        exit_strategy = ExitRegistry.create("atr_trailing", config)
        assert exit_strategy is not None
        assert exit_strategy.config.atr_multiplier == 2.0

    def test_three_stage_exit_still_registered(self):
        """three_stage should still be available."""
        assert "three_stage" in ExitRegistry.list_all()

    def test_atr_trailing_required_indicators(self):
        """ATR trailing should require 'atr' indicator."""
        config = {"atr_multiplier": 2.0}
        exit_strategy = ExitRegistry.create("atr_trailing", config)
        assert "atr" in exit_strategy.required_indicators
