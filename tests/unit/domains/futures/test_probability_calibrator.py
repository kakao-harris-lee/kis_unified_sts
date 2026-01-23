"""Tests for division by zero protection in dl_trend.py"""

import pytest

from domains.futures.strategies.dl_trend import (
    EnsembleFilter,
    ProbabilityCalibrator,
    TechnicalData,
)


class TestProbabilityCalibratorDivisionSafety:
    """Test ProbabilityCalibrator.get_zscore() division safety."""

    def test_zscore_with_constant_history_returns_none(self):
        """When all history values are identical, std=0, should return None."""
        calibrator = ProbabilityCalibrator(window_size=100, min_samples=10)

        # Add identical values (std will be 0)
        for _ in range(50):
            calibrator.update(horizon=10, prob=0.5)

        # Should return None (not raise ZeroDivisionError)
        result = calibrator.get_zscore(horizon=10, prob=0.6)
        assert result is None

    def test_zscore_with_very_small_std_returns_none(self):
        """When std is extremely small, should return None."""
        calibrator = ProbabilityCalibrator(window_size=100, min_samples=10)

        # Add nearly identical values (std will be extremely small, < 1e-8)
        for i in range(50):
            calibrator.update(horizon=10, prob=0.5 + (i % 2) * 1e-10)

        result = calibrator.get_zscore(horizon=10, prob=0.6)
        assert result is None


class TestEnsembleFilterDivisionSafety:
    """Test EnsembleFilter._extract_probabilities() division safety."""

    def test_extract_probabilities_all_zero(self):
        """When all probabilities are 0, should handle gracefully."""
        filter_instance = EnsembleFilter()

        # Calling _extract_probabilities directly
        up, down, hold = filter_instance._extract_probabilities(0.0, 0.0, 0.0)

        # Should not raise ZeroDivisionError
        # Should return some reasonable default
        assert up + down + hold == pytest.approx(1.0, abs=0.01)

    def test_extract_probabilities_near_zero_total(self):
        """When probabilities sum to near-zero, should handle gracefully."""
        filter_instance = EnsembleFilter()

        up, down, hold = filter_instance._extract_probabilities(0.0001, 0.0001, 0.0001)

        # Should normalize correctly
        total = up + down + hold
        assert total == pytest.approx(1.0, abs=0.01)

    def test_extract_probabilities_negative_values(self):
        """Negative probabilities should be handled (clamped or error)."""
        filter_instance = EnsembleFilter()

        # This tests robustness against bad input
        up, down, hold = filter_instance._extract_probabilities(-0.1, 0.5, 0.5)

        # Either clamp to 0 or all probabilities should still sum to ~1.0
        assert up >= 0
        assert down >= 0
        assert hold >= 0

    def test_check_entry_with_zero_probabilities_does_not_crash(self):
        """check_entry should not crash with zero probabilities."""
        filter_instance = EnsembleFilter()

        tech = TechnicalData(
            ma_fast=100.0,
            ma_slow=100.0,
            ichimoku_span_a=100.0,
            ichimoku_span_b=100.0,
            atr=1.0,
            is_ready=True,
            current_price=100.0,
        )

        # Should not crash with zero probabilities
        result = filter_instance.check_entry(
            up_prob=0.0,
            tech=tech,
            down_prob=0.0,
            hold_prob=0.0,
        )

        # Should reject the entry (no clear direction)
        assert result.can_enter is False

    def test_extract_probabilities_returns_normalized_values(self):
        """After normalization, probabilities should sum to 1.0."""
        filter_instance = EnsembleFilter()

        # Test with various abnormal inputs
        test_cases = [
            (0.0, 0.0, 0.0),  # All zero -> uniform (1/3, 1/3, 1/3)
            (0.5, 0.3, 0.1),  # Sum < 1.0 (0.9)
            (0.6, 0.5, 0.2),  # Sum > 1.0 (1.3)
            (-0.1, 0.6, 0.5),  # Negative value
        ]

        for up, down, hold in test_cases:
            result_up, result_down, result_hold = filter_instance._extract_probabilities(
                up, down, hold
            )

            # Should normalize to sum to 1.0
            total = result_up + result_down + result_hold
            assert total == pytest.approx(1.0, abs=0.01), (
                f"Probabilities should sum to 1.0, got {total:.6f} for input "
                f"({up}, {down}, {hold}) -> ({result_up:.6f}, {result_down:.6f}, {result_hold:.6f})"
            )

            # All values should be non-negative
            assert result_up >= 0, f"up_prob should be >= 0, got {result_up}"
            assert result_down >= 0, f"down_prob should be >= 0, got {result_down}"
            assert result_hold >= 0, f"hold_prob should be >= 0, got {result_hold}"

    def test_zscore_returns_none_for_inf_mean(self):
        """When mean/std is infinite, should return None."""
        calibrator = ProbabilityCalibrator(window_size=10, min_samples=5)

        # Add normal values first
        for i in range(10):
            calibrator.update(horizon=1, prob=0.5)

        # Mock the history to include inf (edge case)
        calibrator._history[1].append(float('inf'))

        result = calibrator.get_zscore(horizon=1, prob=0.6)
        assert result is None  # Should handle gracefully

    def test_zscore_uses_class_constant_threshold(self):
        """Verify class constant MIN_STD_THRESHOLD is used."""
        assert hasattr(ProbabilityCalibrator, 'MIN_STD_THRESHOLD')
        assert ProbabilityCalibrator.MIN_STD_THRESHOLD == 1e-8
