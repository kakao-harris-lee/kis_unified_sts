"""Unit tests for SlippageModel and SlippageModelConfig.

Tests cover:
- Configuration creation and defaults
- Time-of-day multipliers
- Slippage calculation with various order sizes, spreads, and depths
- Edge cases and boundary conditions
"""

from datetime import datetime, time

import pytest

from shared.execution.slippage_model import (
    SlippageModel,
    SlippageModelConfig,
    _parse_time,
    _time_in_window,
    _to_bool,
)


class TestSlippageModelConfig:
    """Tests for SlippageModelConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = SlippageModelConfig()

        assert config.enabled is False
        assert config.base_spread_bps == 1.0
        assert config.depth_impact_factor == 0.5
        assert config.time_of_day_multipliers == {}
        assert config.min_slippage_bps == 0.5
        assert config.max_slippage_bps == 10.0

    def test_custom_config(self):
        """Test custom configuration values."""
        config = SlippageModelConfig(
            enabled=True,
            base_spread_bps=2.5,
            depth_impact_factor=0.8,
            min_slippage_bps=1.0,
            max_slippage_bps=15.0,
        )

        assert config.enabled is True
        assert config.base_spread_bps == 2.5
        assert config.depth_impact_factor == 0.8
        assert config.min_slippage_bps == 1.0
        assert config.max_slippage_bps == 15.0

    def test_from_dict_basic(self):
        """Test creating config from dictionary."""
        data = {
            "enabled": True,
            "base_spread_bps": 2.0,
            "depth_impact_factor": 0.6,
            "min_slippage_bps": 0.8,
            "max_slippage_bps": 12.0,
        }

        config = SlippageModelConfig.from_dict(data)

        assert config.enabled is True
        assert config.base_spread_bps == 2.0
        assert config.depth_impact_factor == 0.6
        assert config.min_slippage_bps == 0.8
        assert config.max_slippage_bps == 12.0

    def test_from_dict_with_time_multipliers(self):
        """Test creating config with time-of-day multipliers."""
        data = {
            "enabled": True,
            "base_spread_bps": 2.0,
            "time_of_day_multipliers": {
                "09:00-10:00": 1.5,
                "14:00-15:15": 1.3,
            },
        }

        config = SlippageModelConfig.from_dict(data)

        assert config.time_of_day_multipliers == {
            "09:00-10:00": 1.5,
            "14:00-15:15": 1.3,
        }

    def test_from_dict_none_input(self):
        """Test from_dict with None input returns disabled default."""
        config = SlippageModelConfig.from_dict(None)

        assert config.enabled is False
        assert config.base_spread_bps == 1.0

    def test_from_dict_empty_dict(self):
        """Test from_dict with empty dict uses defaults."""
        config = SlippageModelConfig.from_dict({})

        assert config.enabled is False
        assert config.base_spread_bps == 1.0
        assert config.depth_impact_factor == 0.5

    def test_from_dict_partial_data(self):
        """Test from_dict with partial data fills in defaults."""
        data = {
            "enabled": True,
            "base_spread_bps": 3.0,
        }

        config = SlippageModelConfig.from_dict(data)

        assert config.enabled is True
        assert config.base_spread_bps == 3.0
        assert config.depth_impact_factor == 0.5  # Default
        assert config.min_slippage_bps == 0.5  # Default

    def test_from_dict_invalid_time_multiplier(self):
        """Test from_dict with invalid time multiplier (should warn and skip)."""
        data = {
            "enabled": True,
            "time_of_day_multipliers": {
                "09:00-10:00": 1.5,
                "invalid": "not_a_number",  # Invalid
            },
        }

        config = SlippageModelConfig.from_dict(data)

        # Should only include valid multiplier
        assert "09:00-10:00" in config.time_of_day_multipliers
        assert config.time_of_day_multipliers["09:00-10:00"] == 1.5

    def test_get_time_multiplier_no_multipliers(self):
        """Test get_time_multiplier with no multipliers configured."""
        config = SlippageModelConfig()

        multiplier = config.get_time_multiplier(time(10, 30))

        assert multiplier == 1.0

    def test_get_time_multiplier_matching_window(self):
        """Test get_time_multiplier with matching time window."""
        config = SlippageModelConfig(
            time_of_day_multipliers={
                "09:00-10:00": 1.5,
                "14:00-15:15": 1.3,
            }
        )

        # Test matching first window
        multiplier = config.get_time_multiplier(time(9, 30))
        assert multiplier == 1.5

        # Test matching second window
        multiplier = config.get_time_multiplier(time(14, 30))
        assert multiplier == 1.3

    def test_get_time_multiplier_no_match(self):
        """Test get_time_multiplier with no matching window."""
        config = SlippageModelConfig(
            time_of_day_multipliers={
                "09:00-10:00": 1.5,
            }
        )

        # Time outside window
        multiplier = config.get_time_multiplier(time(11, 0))
        assert multiplier == 1.0

    def test_get_time_multiplier_boundary(self):
        """Test get_time_multiplier at exact boundary times."""
        config = SlippageModelConfig(
            time_of_day_multipliers={
                "09:00-10:00": 1.5,
            }
        )

        # Exact start time
        assert config.get_time_multiplier(time(9, 0)) == 1.5

        # Just before end time (end is exclusive)
        assert config.get_time_multiplier(time(9, 59)) == 1.5

        # Just before start
        assert config.get_time_multiplier(time(8, 59)) == 1.0

        # At exact end (exclusive)
        assert config.get_time_multiplier(time(10, 0)) == 1.0

        # Just after end
        assert config.get_time_multiplier(time(10, 1)) == 1.0


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_to_bool_with_bool(self):
        """Test _to_bool with boolean input."""
        assert _to_bool(True) is True
        assert _to_bool(False) is False

    def test_to_bool_with_string(self):
        """Test _to_bool with string input."""
        assert _to_bool("true") is True
        assert _to_bool("True") is True
        assert _to_bool("TRUE") is True
        assert _to_bool("1") is True
        assert _to_bool("yes") is True
        assert _to_bool("on") is True
        assert _to_bool("enabled") is True

        assert _to_bool("false") is False
        assert _to_bool("0") is False
        assert _to_bool("no") is False

    def test_to_bool_with_number(self):
        """Test _to_bool with numeric input."""
        assert _to_bool(1) is True
        assert _to_bool(1.0) is True
        assert _to_bool(0) is False
        assert _to_bool(0.0) is False

    def test_to_bool_with_invalid(self):
        """Test _to_bool with invalid input uses default."""
        assert _to_bool(None, default=False) is False
        assert _to_bool(None, default=True) is True
        assert _to_bool([], default=False) is False

    def test_parse_time_valid(self):
        """Test _parse_time with valid time strings."""
        t = _parse_time("09:00")
        assert t == time(9, 0)

        t = _parse_time("14:30")
        assert t == time(14, 30)

        t = _parse_time("00:00")
        assert t == time(0, 0)

        t = _parse_time("23:59")
        assert t == time(23, 59)

    def test_parse_time_invalid_format(self):
        """Test _parse_time with invalid format."""
        with pytest.raises(ValueError):
            _parse_time("9:00:00")  # Too many parts

        with pytest.raises(ValueError):
            _parse_time("9")  # Missing minutes

        with pytest.raises(ValueError):
            _parse_time("invalid")

    def test_time_in_window_normal_window(self):
        """Test _time_in_window with normal time window."""
        # Inside window
        assert _time_in_window(time(9, 30), "09:00-10:00") is True
        assert _time_in_window(time(9, 0), "09:00-10:00") is True
        assert _time_in_window(time(9, 59), "09:00-10:00") is True

        # Outside window (end is exclusive)
        assert _time_in_window(time(10, 0), "09:00-10:00") is False
        assert _time_in_window(time(8, 59), "09:00-10:00") is False
        assert _time_in_window(time(10, 1), "09:00-10:00") is False

    def test_time_in_window_overnight(self):
        """Test _time_in_window with overnight time window."""
        # Overnight window (23:00-01:00), end is exclusive
        assert _time_in_window(time(23, 30), "23:00-01:00") is True
        assert _time_in_window(time(0, 30), "23:00-01:00") is True
        assert _time_in_window(time(0, 59), "23:00-01:00") is True

        # Outside overnight window (end exclusive)
        assert _time_in_window(time(1, 0), "23:00-01:00") is False
        assert _time_in_window(time(12, 0), "23:00-01:00") is False
        assert _time_in_window(time(1, 1), "23:00-01:00") is False

    def test_time_in_window_invalid_format(self):
        """Test _time_in_window with invalid window format."""
        # No hyphen
        assert _time_in_window(time(9, 0), "09:00") is False

        # Invalid time format
        assert _time_in_window(time(9, 0), "invalid-10:00") is False


class TestSlippageModel:
    """Tests for SlippageModel."""

    def test_disabled_model_returns_zero(self):
        """Test that disabled slippage model returns zero slippage."""
        config = SlippageModelConfig(enabled=False)
        model = SlippageModel(config)

        slippage = model.calculate_slippage(
            order_size=10.0,
            current_spread=0.05,
            available_depth=100.0,
        )

        assert slippage == 0.0

    def test_base_slippage_small_order(self):
        """Test base slippage for small order (no depth penalty)."""
        config = SlippageModelConfig(
            enabled=True,
            base_spread_bps=2.0,
            depth_impact_factor=0.5,
            min_slippage_bps=0.5,
            max_slippage_bps=10.0,
        )
        model = SlippageModel(config)

        # Small order relative to depth, typical spread
        slippage = model.calculate_slippage(
            order_size=10.0,
            current_spread=0.05,  # Typical spread
            available_depth=100.0,  # Plenty of depth
        )

        # Should be close to base_spread_bps (2.0)
        assert slippage >= config.min_slippage_bps
        assert slippage <= config.max_slippage_bps
        assert slippage == pytest.approx(2.0, abs=0.1)

    def test_depth_impact_order_exceeds_depth(self):
        """Test depth impact when order size exceeds available depth."""
        config = SlippageModelConfig(
            enabled=True,
            base_spread_bps=2.0,
            depth_impact_factor=0.5,
            min_slippage_bps=0.5,
            max_slippage_bps=10.0,
        )
        model = SlippageModel(config)

        # Order is 2x available depth
        slippage = model.calculate_slippage(
            order_size=200.0,
            current_spread=0.05,
            available_depth=100.0,
        )

        # Depth penalty = (200/100 - 1.0) * 0.5 = 0.5 bps
        # Total = 2.0 (base) + 0.5 (depth) = 2.5 bps
        assert slippage > 2.0  # More than base
        assert slippage == pytest.approx(2.5, abs=0.1)

    def test_depth_impact_no_depth_available(self):
        """Test depth impact when no depth is available."""
        config = SlippageModelConfig(
            enabled=True,
            base_spread_bps=2.0,
            depth_impact_factor=0.5,
            min_slippage_bps=0.5,
            max_slippage_bps=10.0,
        )
        model = SlippageModel(config)

        # No depth available
        slippage = model.calculate_slippage(
            order_size=10.0,
            current_spread=0.05,
            available_depth=0.0,
        )

        # Penalty = depth_impact_factor * 2.0 = 0.5 * 2.0 = 1.0
        # Total = 2.0 (base) + 1.0 (no depth penalty) = 3.0 bps
        assert slippage > 2.0
        assert slippage == pytest.approx(3.0, abs=0.1)

    def test_wide_spread_impact(self):
        """Test slippage increase with wider spread."""
        config = SlippageModelConfig(
            enabled=True,
            base_spread_bps=2.0,
            depth_impact_factor=0.5,
            min_slippage_bps=0.5,
            max_slippage_bps=10.0,
        )
        model = SlippageModel(config)

        # Wide spread (2x typical)
        slippage = model.calculate_slippage(
            order_size=10.0,
            current_spread=0.10,  # 2x typical (0.05)
            available_depth=100.0,
        )

        # Spread penalty = (0.10/0.05 - 1.0) * 2.0 = 2.0 bps
        # Total = 2.0 (base) + 2.0 (spread) = 4.0 bps
        assert slippage > 2.0
        assert slippage == pytest.approx(4.0, abs=0.1)

    def test_narrow_spread_no_extra_penalty(self):
        """Test that narrow spread doesn't add penalty."""
        config = SlippageModelConfig(
            enabled=True,
            base_spread_bps=2.0,
            depth_impact_factor=0.5,
            min_slippage_bps=0.5,
            max_slippage_bps=10.0,
        )
        model = SlippageModel(config)

        # Narrow spread (less than typical)
        slippage = model.calculate_slippage(
            order_size=10.0,
            current_spread=0.03,  # Less than typical (0.05)
            available_depth=100.0,
        )

        # No spread penalty added for narrow spreads
        # Should be just base_spread_bps
        assert slippage == pytest.approx(2.0, abs=0.1)

    def test_time_of_day_multiplier(self):
        """Test time-of-day multiplier effect."""
        config = SlippageModelConfig(
            enabled=True,
            base_spread_bps=2.0,
            depth_impact_factor=0.5,
            time_of_day_multipliers={
                "09:00-10:00": 1.5,  # 50% increase
            },
            min_slippage_bps=0.5,
            max_slippage_bps=10.0,
        )
        model = SlippageModel(config)

        # During high volatility window
        timestamp = datetime(2024, 1, 1, 9, 30)
        slippage = model.calculate_slippage(
            order_size=10.0,
            current_spread=0.05,
            available_depth=100.0,
            timestamp=timestamp,
        )

        # Base slippage ~2.0, multiplied by 1.5 = 3.0 bps
        assert slippage == pytest.approx(3.0, abs=0.1)

    def test_time_of_day_multiplier_no_match(self):
        """Test slippage when time doesn't match any multiplier window."""
        config = SlippageModelConfig(
            enabled=True,
            base_spread_bps=2.0,
            depth_impact_factor=0.5,
            time_of_day_multipliers={
                "09:00-10:00": 1.5,
            },
            min_slippage_bps=0.5,
            max_slippage_bps=10.0,
        )
        model = SlippageModel(config)

        # Outside the window
        timestamp = datetime(2024, 1, 1, 11, 0)
        slippage = model.calculate_slippage(
            order_size=10.0,
            current_spread=0.05,
            available_depth=100.0,
            timestamp=timestamp,
        )

        # No multiplier applied (1.0), just base slippage
        assert slippage == pytest.approx(2.0, abs=0.1)

    def test_min_slippage_clamping(self):
        """Test that slippage is clamped to minimum value."""
        config = SlippageModelConfig(
            enabled=True,
            base_spread_bps=0.1,  # Very low base
            depth_impact_factor=0.0,  # No depth impact
            min_slippage_bps=1.0,  # Minimum floor
            max_slippage_bps=10.0,
        )
        model = SlippageModel(config)

        slippage = model.calculate_slippage(
            order_size=1.0,
            current_spread=0.05,
            available_depth=1000.0,
        )

        # Should be clamped to min_slippage_bps
        assert slippage == 1.0

    def test_max_slippage_clamping(self):
        """Test that slippage is clamped to maximum value."""
        config = SlippageModelConfig(
            enabled=True,
            base_spread_bps=2.0,
            depth_impact_factor=5.0,  # Very high impact
            min_slippage_bps=0.5,
            max_slippage_bps=10.0,  # Maximum cap
        )
        model = SlippageModel(config)

        # Huge order, no depth, wide spread
        slippage = model.calculate_slippage(
            order_size=10000.0,
            current_spread=0.50,
            available_depth=1.0,
        )

        # Should be clamped to max_slippage_bps
        assert slippage == 10.0

    def test_combined_factors(self):
        """Test slippage with multiple factors combined."""
        config = SlippageModelConfig(
            enabled=True,
            base_spread_bps=2.0,
            depth_impact_factor=0.5,
            time_of_day_multipliers={
                "09:00-10:00": 1.5,
            },
            min_slippage_bps=0.5,
            max_slippage_bps=10.0,
        )
        model = SlippageModel(config)

        # Large order, wide spread, high volatility time
        timestamp = datetime(2024, 1, 1, 9, 30)
        slippage = model.calculate_slippage(
            order_size=150.0,  # 1.5x depth
            current_spread=0.10,  # 2x typical spread
            available_depth=100.0,
            timestamp=timestamp,
        )

        # Base: 2.0
        # Depth penalty: (1.5 - 1.0) * 0.5 = 0.25
        # Spread penalty: (2.0 - 1.0) * 2.0 = 2.0
        # Subtotal: 2.0 + 0.25 + 2.0 = 4.25
        # Time multiplier: 4.25 * 1.5 = 6.375 bps
        assert slippage > 5.0
        assert slippage < 7.0
        assert slippage == pytest.approx(6.375, abs=0.2)

    def test_default_timestamp(self):
        """Test that default timestamp (now) is used when not provided."""
        config = SlippageModelConfig(
            enabled=True,
            base_spread_bps=2.0,
            min_slippage_bps=0.5,
            max_slippage_bps=10.0,
        )
        model = SlippageModel(config)

        # Should not raise error without timestamp
        slippage = model.calculate_slippage(
            order_size=10.0,
            current_spread=0.05,
            available_depth=100.0,
        )

        assert slippage >= config.min_slippage_bps
        assert slippage <= config.max_slippage_bps

    def test_zero_order_size(self):
        """Test slippage calculation with zero order size."""
        config = SlippageModelConfig(
            enabled=True,
            base_spread_bps=2.0,
            depth_impact_factor=0.5,
            min_slippage_bps=0.5,
            max_slippage_bps=10.0,
        )
        model = SlippageModel(config)

        slippage = model.calculate_slippage(
            order_size=0.0,
            current_spread=0.05,
            available_depth=100.0,
        )

        # Zero order has no depth impact
        # Should be base slippage or min
        assert slippage >= config.min_slippage_bps
        assert slippage <= config.base_spread_bps + 0.5

    def test_large_order_small_depth(self):
        """Test realistic scenario: large order on thin book."""
        config = SlippageModelConfig(
            enabled=True,
            base_spread_bps=2.0,
            depth_impact_factor=0.5,
            min_slippage_bps=1.0,
            max_slippage_bps=10.0,
        )
        model = SlippageModel(config)

        # 10 contracts vs 3 available (realistic mini futures)
        slippage = model.calculate_slippage(
            order_size=10.0,
            current_spread=0.05,
            available_depth=3.0,
        )

        # Depth ratio = 10/3 = 3.33
        # Depth penalty = (3.33 - 1.0) * 0.5 = 1.165
        # Total = 2.0 + 1.165 = 3.165 bps (before time multiplier)
        assert slippage > 2.0
        assert slippage < 5.0
        assert slippage == pytest.approx(3.165, abs=0.2)

    def test_perfect_liquidity(self):
        """Test scenario with perfect liquidity (very deep book)."""
        config = SlippageModelConfig(
            enabled=True,
            base_spread_bps=2.0,
            depth_impact_factor=0.5,
            min_slippage_bps=0.5,
            max_slippage_bps=10.0,
        )
        model = SlippageModel(config)

        # Small order vs huge depth
        slippage = model.calculate_slippage(
            order_size=1.0,
            current_spread=0.05,
            available_depth=10000.0,
        )

        # No depth penalty, just base slippage
        assert slippage == pytest.approx(2.0, abs=0.1)

    def test_multiple_time_windows(self):
        """Test with multiple time-of-day windows."""
        config = SlippageModelConfig(
            enabled=True,
            base_spread_bps=2.0,
            time_of_day_multipliers={
                "09:00-10:00": 1.5,
                "14:00-15:15": 1.3,
                "12:00-13:00": 0.8,  # Lunch hour - lower volatility
            },
            min_slippage_bps=0.5,
            max_slippage_bps=10.0,
        )
        model = SlippageModel(config)

        # Morning window
        slippage_morning = model.calculate_slippage(
            order_size=10.0,
            current_spread=0.05,
            available_depth=100.0,
            timestamp=datetime(2024, 1, 1, 9, 30),
        )
        assert slippage_morning == pytest.approx(3.0, abs=0.1)  # 2.0 * 1.5

        # Lunch window
        slippage_lunch = model.calculate_slippage(
            order_size=10.0,
            current_spread=0.05,
            available_depth=100.0,
            timestamp=datetime(2024, 1, 1, 12, 30),
        )
        assert slippage_lunch == pytest.approx(1.6, abs=0.1)  # 2.0 * 0.8

        # Afternoon window
        slippage_afternoon = model.calculate_slippage(
            order_size=10.0,
            current_spread=0.05,
            available_depth=100.0,
            timestamp=datetime(2024, 1, 1, 14, 30),
        )
        assert slippage_afternoon == pytest.approx(2.6, abs=0.1)  # 2.0 * 1.3
