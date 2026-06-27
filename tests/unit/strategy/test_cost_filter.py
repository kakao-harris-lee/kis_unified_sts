"""Test cost-aware signal filtering."""
from datetime import datetime

import pytest

from shared.models.signal import Signal, SignalType
from shared.strategy.filters import CostFilter, CostFilterConfig


class TestCostFilterConfig:
    """Test CostFilterConfig validation."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CostFilterConfig()
        assert config.min_atr_cost_ratio == 1.5
        assert config.commission_rate == 0.003
        assert config.slippage_bps == 1.5

    def test_custom_config(self):
        """Test custom configuration values."""
        config = CostFilterConfig(
            min_atr_cost_ratio=2.0,
            commission_rate=0.005,
            slippage_bps=2.0,
        )
        assert config.min_atr_cost_ratio == 2.0
        assert config.commission_rate == 0.005
        assert config.slippage_bps == 2.0

    def test_min_atr_cost_ratio_must_be_positive(self):
        """Test min_atr_cost_ratio must be > 0."""
        with pytest.raises(ValueError):
            CostFilterConfig(min_atr_cost_ratio=0.0)

        with pytest.raises(ValueError):
            CostFilterConfig(min_atr_cost_ratio=-1.0)

    def test_commission_rate_bounds(self):
        """Test commission_rate must be in [0.0, 0.1]."""
        # Valid boundary values
        CostFilterConfig(commission_rate=0.0)  # Min
        CostFilterConfig(commission_rate=0.1)  # Max

        # Invalid values
        with pytest.raises(ValueError):
            CostFilterConfig(commission_rate=-0.001)

        with pytest.raises(ValueError):
            CostFilterConfig(commission_rate=0.11)

    def test_slippage_bps_bounds(self):
        """Test slippage_bps must be in [0.0, 100.0]."""
        # Valid boundary values
        CostFilterConfig(slippage_bps=0.0)  # Min
        CostFilterConfig(slippage_bps=100.0)  # Max

        # Invalid values
        with pytest.raises(ValueError):
            CostFilterConfig(slippage_bps=-0.1)

        with pytest.raises(ValueError):
            CostFilterConfig(slippage_bps=101.0)


class TestCostFilter:
    """Test CostFilter signal checking."""

    def _create_signal(self, code: str = "005930") -> Signal:
        """Helper to create a test signal."""
        return Signal(
            code=code,
            name="삼성전자",
            signal_type=SignalType.ENTRY,
            strategy="test_strategy",
            price=70000,
            timestamp=datetime(2026, 3, 8, 10, 0, 0),
        )

    def test_initialization(self):
        """Test filter initialization and round-trip cost calculation."""
        config = CostFilterConfig(
            commission_rate=0.003,  # 0.3%
            slippage_bps=1.5,  # 0.015%
        )
        cost_filter = CostFilter(config)

        # Round-trip cost = 0.003 + 0.00015 = 0.00315 (0.315%)
        expected_cost = 0.003 + (1.5 / 10000.0)
        assert cost_filter._round_trip_cost == pytest.approx(expected_cost)

    def test_signal_passes_with_sufficient_edge(self):
        """Test signal passes when edge ratio exceeds threshold."""
        config = CostFilterConfig(min_atr_cost_ratio=1.5)
        cost_filter = CostFilter(config)
        signal = self._create_signal()

        # ATR = 1000, Price = 70000 → expected_move = 1000/70000 = 1.43%
        # Round-trip cost ≈ 0.315% → edge_ratio = 1.43% / 0.315% ≈ 4.54
        # 4.54 > 1.5 → PASS
        indicators = {"atr": 1000.0}
        price = 70000.0

        passed, reason = cost_filter.check_signal(signal, indicators, price)

        assert passed is True
        assert reason is None

        # Verify statistics
        stats = cost_filter.get_stats()
        assert stats["total_checks"] == 1
        assert stats["passed"] == 1
        assert stats["rejected_insufficient_edge"] == 0

    def test_signal_rejected_with_insufficient_edge(self):
        """Test signal rejected when edge ratio below threshold."""
        config = CostFilterConfig(min_atr_cost_ratio=2.0)
        cost_filter = CostFilter(config)
        signal = self._create_signal()

        # ATR = 200, Price = 70000 → expected_move = 200/70000 = 0.286%
        # Round-trip cost ≈ 0.315% → edge_ratio = 0.286% / 0.315% ≈ 0.91
        # 0.91 < 2.0 → REJECT
        indicators = {"atr": 200.0}
        price = 70000.0

        passed, reason = cost_filter.check_signal(signal, indicators, price)

        assert passed is False
        assert reason is not None
        assert "Insufficient edge ratio" in reason

        # Verify statistics
        stats = cost_filter.get_stats()
        assert stats["total_checks"] == 1
        assert stats["passed"] == 0
        assert stats["rejected_insufficient_edge"] == 1

    def test_rejection_with_missing_atr(self):
        """Test signal rejected when ATR is missing from indicators."""
        config = CostFilterConfig()
        cost_filter = CostFilter(config)
        signal = self._create_signal()

        # No ATR in indicators
        indicators = {"rsi": 50.0}
        price = 70000.0

        passed, reason = cost_filter.check_signal(signal, indicators, price)

        assert passed is False
        assert reason is not None
        assert "Missing or invalid ATR" in reason

        # Verify statistics
        stats = cost_filter.get_stats()
        assert stats["rejected_missing_atr"] == 1

    def test_rejection_with_zero_atr(self):
        """Test signal rejected when ATR is zero."""
        config = CostFilterConfig()
        cost_filter = CostFilter(config)
        signal = self._create_signal()

        indicators = {"atr": 0.0}
        price = 70000.0

        passed, reason = cost_filter.check_signal(signal, indicators, price)

        assert passed is False
        assert "Missing or invalid ATR" in reason

        stats = cost_filter.get_stats()
        assert stats["rejected_missing_atr"] == 1

    def test_rejection_with_negative_atr(self):
        """Test signal rejected when ATR is negative."""
        config = CostFilterConfig()
        cost_filter = CostFilter(config)
        signal = self._create_signal()

        indicators = {"atr": -100.0}
        price = 70000.0

        passed, reason = cost_filter.check_signal(signal, indicators, price)

        assert passed is False
        assert "Missing or invalid ATR" in reason

        stats = cost_filter.get_stats()
        assert stats["rejected_missing_atr"] == 1

    def test_rejection_with_zero_price(self):
        """Test signal rejected when price is zero."""
        config = CostFilterConfig()
        cost_filter = CostFilter(config)
        signal = self._create_signal()

        indicators = {"atr": 1000.0}
        price = 0.0

        passed, reason = cost_filter.check_signal(signal, indicators, price)

        assert passed is False
        assert "Invalid price" in reason

        stats = cost_filter.get_stats()
        assert stats["rejected_invalid_price"] == 1

    def test_rejection_with_negative_price(self):
        """Test signal rejected when price is negative."""
        config = CostFilterConfig()
        cost_filter = CostFilter(config)
        signal = self._create_signal()

        indicators = {"atr": 1000.0}
        price = -70000.0

        passed, reason = cost_filter.check_signal(signal, indicators, price)

        assert passed is False
        assert "Invalid price" in reason

        stats = cost_filter.get_stats()
        assert stats["rejected_invalid_price"] == 1

    def test_edge_ratio_calculation_accuracy(self):
        """Test edge ratio calculation matches expected formula."""
        config = CostFilterConfig(
            min_atr_cost_ratio=1.0,
            commission_rate=0.003,
            slippage_bps=1.5,
        )
        cost_filter = CostFilter(config)
        signal = self._create_signal()

        # Given: ATR = 500, Price = 100000
        indicators = {"atr": 500.0}
        price = 100000.0

        # Expected calculation:
        # expected_move = 500 / 100000 = 0.005 (0.5%)
        # round_trip_cost = 0.003 + 0.00015 = 0.00315 (0.315%)
        # edge_ratio = 0.005 / 0.00315 ≈ 1.587

        passed, reason = cost_filter.check_signal(signal, indicators, price)

        assert passed is True  # 1.587 > 1.0
        stats = cost_filter.get_stats()
        assert stats["avg_edge_ratio"] == pytest.approx(1.587, rel=0.01)

    def test_statistics_tracking_multiple_checks(self):
        """Test statistics tracking across multiple signal checks."""
        config = CostFilterConfig(min_atr_cost_ratio=1.5)
        cost_filter = CostFilter(config)

        # Check 1: PASS (high ATR)
        signal1 = self._create_signal("005930")
        cost_filter.check_signal(signal1, {"atr": 1000.0}, 70000.0)

        # Check 2: REJECT (low ATR)
        signal2 = self._create_signal("035720")
        cost_filter.check_signal(signal2, {"atr": 100.0}, 70000.0)

        # Check 3: PASS (high ATR)
        signal3 = self._create_signal("005380")
        cost_filter.check_signal(signal3, {"atr": 1500.0}, 70000.0)

        # Check 4: REJECT (missing ATR)
        signal4 = self._create_signal("000660")
        cost_filter.check_signal(signal4, {}, 70000.0)

        stats = cost_filter.get_stats()
        assert stats["total_checks"] == 4
        assert stats["passed"] == 2
        assert stats["rejected_insufficient_edge"] == 1
        assert stats["rejected_missing_atr"] == 1
        assert stats["pass_rate"] == 0.5

    def test_average_edge_ratio_calculation(self):
        """Test average edge ratio is calculated correctly."""
        config = CostFilterConfig(min_atr_cost_ratio=0.5)  # Low threshold to pass all
        cost_filter = CostFilter(config)

        # Check 1: edge_ratio ≈ 4.54 (ATR=1000, price=70000)
        signal1 = self._create_signal()
        cost_filter.check_signal(signal1, {"atr": 1000.0}, 70000.0)

        # Check 2: edge_ratio ≈ 0.45 (ATR=100, price=70000)
        signal2 = self._create_signal()
        cost_filter.check_signal(signal2, {"atr": 100.0}, 70000.0)

        stats = cost_filter.get_stats()
        # Average should be approximately (4.54 + 0.45) / 2 ≈ 2.5
        assert stats["avg_edge_ratio"] > 2.0
        assert stats["avg_edge_ratio"] < 3.0

    def test_get_stats_structure(self):
        """Test get_stats returns all required fields."""
        config = CostFilterConfig()
        cost_filter = CostFilter(config)

        stats = cost_filter.get_stats()

        required_fields = [
            "total_checks",
            "passed",
            "rejected_insufficient_edge",
            "rejected_missing_atr",
            "rejected_invalid_price",
            "avg_edge_ratio",
            "pass_rate",
        ]

        for field in required_fields:
            assert field in stats

    def test_pass_rate_calculation(self):
        """Test pass_rate is calculated correctly."""
        config = CostFilterConfig(min_atr_cost_ratio=1.5)
        cost_filter = CostFilter(config)

        # 3 passes, 1 reject
        for i in range(3):
            signal = self._create_signal(f"00593{i}")
            cost_filter.check_signal(signal, {"atr": 1000.0}, 70000.0)

        signal = self._create_signal("035720")
        cost_filter.check_signal(signal, {"atr": 100.0}, 70000.0)

        stats = cost_filter.get_stats()
        assert stats["pass_rate"] == 0.75

    def test_pass_rate_zero_checks(self):
        """Test pass_rate is 0.0 when no checks performed."""
        config = CostFilterConfig()
        cost_filter = CostFilter(config)

        stats = cost_filter.get_stats()
        assert stats["pass_rate"] == 0.0

    def test_reset_stats(self):
        """Test reset_stats clears all counters."""
        config = CostFilterConfig()
        cost_filter = CostFilter(config)

        # Generate some statistics
        signal = self._create_signal()
        cost_filter.check_signal(signal, {"atr": 1000.0}, 70000.0)
        cost_filter.check_signal(signal, {"atr": 100.0}, 70000.0)

        # Verify stats are non-zero
        stats_before = cost_filter.get_stats()
        assert stats_before["total_checks"] > 0

        # Reset
        cost_filter.reset_stats()

        # Verify all stats are zero
        stats_after = cost_filter.get_stats()
        assert stats_after["total_checks"] == 0
        assert stats_after["passed"] == 0
        assert stats_after["rejected_insufficient_edge"] == 0
        assert stats_after["rejected_missing_atr"] == 0
        assert stats_after["rejected_invalid_price"] == 0
        assert stats_after["avg_edge_ratio"] == 0.0

    def test_boundary_edge_ratio_exactly_at_threshold(self):
        """Test signal at exact threshold boundary."""
        config = CostFilterConfig(
            min_atr_cost_ratio=2.0,
            commission_rate=0.003,
            slippage_bps=1.5,
        )
        cost_filter = CostFilter(config)

        # Calculate ATR that gives exactly 2.0 edge ratio
        # round_trip_cost = 0.00315
        # edge_ratio = 2.0 → expected_move = 2.0 * 0.00315 = 0.0063
        # For price = 100000, ATR = 0.0063 * 100000 = 630
        signal = self._create_signal()
        indicators = {"atr": 630.0}
        price = 100000.0

        passed, reason = cost_filter.check_signal(signal, indicators, price)

        # Should pass (edge_ratio == threshold is acceptable)
        assert passed is True

    def test_multiple_signals_same_code(self):
        """Test filter can handle multiple signals for same stock code."""
        config = CostFilterConfig(min_atr_cost_ratio=1.5)
        cost_filter = CostFilter(config)

        # Same code, different ATR values
        signal1 = self._create_signal("005930")
        cost_filter.check_signal(signal1, {"atr": 2000.0}, 70000.0)

        signal2 = self._create_signal("005930")
        cost_filter.check_signal(signal2, {"atr": 100.0}, 70000.0)

        stats = cost_filter.get_stats()
        assert stats["total_checks"] == 2

    def test_different_price_levels(self):
        """Test filter works correctly across different price ranges."""
        config = CostFilterConfig(min_atr_cost_ratio=1.5)
        cost_filter = CostFilter(config)

        # Low price stock (ATR should be proportionally smaller)
        signal_low = self._create_signal("A123456")
        passed_low, _ = cost_filter.check_signal(
            signal_low, {"atr": 10.0}, 1000.0  # 1% move
        )

        # High price stock (ATR can be larger)
        signal_high = self._create_signal("005930")
        passed_high, _ = cost_filter.check_signal(
            signal_high, {"atr": 1000.0}, 100000.0  # 1% move
        )

        # Both should have similar edge ratios and pass
        assert passed_low is True
        assert passed_high is True

    def test_futures_typical_values(self):
        """Test with typical futures contract values."""
        config = CostFilterConfig(
            min_atr_cost_ratio=1.5,
            commission_rate=0.00002,  # Futures have lower commission
            slippage_bps=0.5,
        )
        cost_filter = CostFilter(config)

        # KOSPI200 futures typical values
        signal = Signal(
            code="101W06",
            name="KOSPI200선물",
            signal_type=SignalType.ENTRY,
            strategy="test_futures",
            price=370.0,
        )

        # ATR ≈ 2.0 points
        indicators = {"atr": 2.0}
        price = 370.0

        passed, reason = cost_filter.check_signal(signal, indicators, price)

        # Should pass with low costs
        assert passed is True
