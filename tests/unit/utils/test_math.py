"""Tests for math utilities."""

import logging

from shared.utils.math import safe_divide, safe_pct_change


class TestSafeDivide:
    """Tests for safe_divide function."""

    def test_normal_division(self):
        """Test normal division works correctly."""
        assert safe_divide(10, 2) == 5.0
        assert safe_divide(7, 2) == 3.5
        assert safe_divide(-10, 2) == -5.0

    def test_division_by_zero_returns_default(self):
        """Test division by zero returns default value."""
        assert safe_divide(10, 0) == 0.0
        assert safe_divide(10, 0, default=0.0) == 0.0
        assert safe_divide(-5, 0) == 0.0

    def test_custom_default_value(self):
        """Test custom default value for division by zero."""
        assert safe_divide(10, 0, default=float("inf")) == float("inf")
        assert safe_divide(10, 0, default=-1.0) == -1.0
        assert safe_divide(10, 0, default=100) == 100.0

    def test_integer_inputs(self):
        """Test with integer inputs."""
        result = safe_divide(10, 3)
        assert isinstance(result, float)
        assert abs(result - 3.333333) < 0.001

    def test_zero_numerator(self):
        """Test zero numerator returns zero."""
        assert safe_divide(0, 5) == 0.0
        assert safe_divide(0, -5) == 0.0

    def test_negative_denominator(self):
        """Test negative denominator."""
        assert safe_divide(10, -2) == -5.0
        assert safe_divide(-10, -2) == 5.0

    def test_small_numbers(self):
        """Test with very small numbers."""
        result = safe_divide(1e-10, 1e-5)
        assert abs(result - 1e-5) < 1e-10

    def test_large_numbers(self):
        """Test with large numbers."""
        result = safe_divide(1e15, 1e10)
        assert abs(result - 1e5) < 1

    def test_warn_on_division_by_zero(self, caplog):
        """Test warning is logged when warn=True."""
        with caplog.at_level(logging.WARNING):
            result = safe_divide(10, 0, warn=True)

        assert result == 0.0
        assert "Division by zero avoided" in caplog.text

    def test_no_warn_by_default(self, caplog):
        """Test no warning by default."""
        with caplog.at_level(logging.WARNING):
            safe_divide(10, 0)

        assert "Division by zero avoided" not in caplog.text


class TestSafePctChange:
    """Tests for safe_pct_change function."""

    def test_positive_change(self):
        """Test positive percentage change."""
        result = safe_pct_change(100, 110)
        assert abs(result - 0.10) < 0.001  # 10% increase

    def test_negative_change(self):
        """Test negative percentage change."""
        result = safe_pct_change(100, 90)
        assert abs(result - (-0.10)) < 0.001  # 10% decrease

    def test_no_change(self):
        """Test no change returns zero."""
        assert safe_pct_change(100, 100) == 0.0

    def test_zero_old_value_returns_default(self):
        """Test zero old value returns default."""
        assert safe_pct_change(0, 100) == 0.0
        assert safe_pct_change(0, 100, default=float("inf")) == float("inf")

    def test_doubling(self):
        """Test 100% increase (doubling)."""
        result = safe_pct_change(50, 100)
        assert abs(result - 1.0) < 0.001

    def test_halving(self):
        """Test 50% decrease (halving)."""
        result = safe_pct_change(100, 50)
        assert abs(result - (-0.5)) < 0.001

    def test_negative_values(self):
        """Test with negative values."""
        # From -100 to -50: (-50 - (-100)) / -100 = 50 / -100 = -0.5
        result = safe_pct_change(-100, -50)
        assert abs(result - (-0.5)) < 0.001

    def test_integer_inputs(self):
        """Test with integer inputs."""
        result = safe_pct_change(100, 150)
        assert isinstance(result, float)
        assert abs(result - 0.5) < 0.001
