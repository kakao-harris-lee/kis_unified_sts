"""Tests for shared/utils/calc.py - PnL and trading calculations."""

import pytest


class TestNormalizeSide:
    """normalize_side function tests"""

    def test_long_variations(self):
        """Test long side normalization"""
        from shared.utils.calc import normalize_side

        assert normalize_side("long") == "long"
        assert normalize_side("LONG") == "long"
        assert normalize_side("buy") == "long"
        assert normalize_side("BUY") == "long"

    def test_short_variations(self):
        """Test short side normalization"""
        from shared.utils.calc import normalize_side

        assert normalize_side("short") == "short"
        assert normalize_side("SHORT") == "short"
        assert normalize_side("sell") == "short"
        assert normalize_side("SELL") == "short"

    def test_invalid_side_raises(self):
        """Test invalid side raises ValueError"""
        from shared.utils.calc import normalize_side

        with pytest.raises(ValueError, match="Invalid side"):
            normalize_side("invalid")


class TestCalcProfitRate:
    """calc_profit_rate function tests"""

    def test_long_profit(self):
        """Test profit calculation for long position"""
        from shared.utils.calc import calc_profit_rate

        # 100 -> 105: 5% profit
        result = calc_profit_rate(100.0, 105.0, "long")
        assert result == pytest.approx(0.05)

    def test_long_loss(self):
        """Test loss calculation for long position"""
        from shared.utils.calc import calc_profit_rate

        # 100 -> 95: -5% loss
        result = calc_profit_rate(100.0, 95.0, "long")
        assert result == pytest.approx(-0.05)

    def test_short_profit(self):
        """Test profit calculation for short position"""
        from shared.utils.calc import calc_profit_rate

        # 100 -> 95: 5% profit for short
        result = calc_profit_rate(100.0, 95.0, "short")
        assert result == pytest.approx(0.05)

    def test_short_loss(self):
        """Test loss calculation for short position"""
        from shared.utils.calc import calc_profit_rate

        # 100 -> 105: -5% loss for short
        result = calc_profit_rate(100.0, 105.0, "short")
        assert result == pytest.approx(-0.05)

    def test_zero_entry_price(self):
        """Test with zero entry price returns 0"""
        from shared.utils.calc import calc_profit_rate

        result = calc_profit_rate(0.0, 105.0, "long")
        assert result == 0.0

    def test_negative_current_price(self):
        """Test with negative current price returns 0"""
        from shared.utils.calc import calc_profit_rate

        result = calc_profit_rate(100.0, -5.0, "long")
        assert result == 0.0


class TestCalcProfitPct:
    """calc_profit_pct function tests"""

    def test_conversion_to_percentage(self):
        """Test rate to percentage conversion"""
        from shared.utils.calc import calc_profit_pct

        # 5% profit should be 5.0
        result = calc_profit_pct(100.0, 105.0, "long")
        assert result == pytest.approx(5.0)


class TestCalcUnrealizedPnl:
    """calc_unrealized_pnl function tests"""

    def test_long_profit(self):
        """Test unrealized PnL for long profit"""
        from shared.utils.calc import calc_unrealized_pnl

        # (105 - 100) * 10 = 50
        result = calc_unrealized_pnl(100.0, 105.0, 10, "long")
        assert result == pytest.approx(50.0)

    def test_short_profit(self):
        """Test unrealized PnL for short profit"""
        from shared.utils.calc import calc_unrealized_pnl

        # (100 - 95) * 10 = 50
        result = calc_unrealized_pnl(100.0, 95.0, 10, "short")
        assert result == pytest.approx(50.0)

    def test_zero_quantity(self):
        """Test with zero quantity returns 0"""
        from shared.utils.calc import calc_unrealized_pnl

        result = calc_unrealized_pnl(100.0, 105.0, 0, "long")
        assert result == 0.0


class TestCalcRealizedPnl:
    """calc_realized_pnl function tests"""

    def test_with_fees(self):
        """Test realized PnL with fees"""
        from shared.utils.calc import calc_realized_pnl

        # Gross: (105 - 100) * 10 = 50
        # Entry fee: 100 * 10 * 0.0015 = 1.5
        # Exit fee: 105 * 10 * 0.0015 = 1.575
        # Net: 50 - 1.5 - 1.575 = 46.925
        result = calc_realized_pnl(100.0, 105.0, 10, "long", 0.003)
        assert result == pytest.approx(46.925)

    def test_without_fees(self):
        """Test realized PnL without fees"""
        from shared.utils.calc import calc_realized_pnl

        result = calc_realized_pnl(100.0, 105.0, 10, "long", 0.0)
        assert result == pytest.approx(50.0)


class TestCalcDropFromHigh:
    """calc_drop_from_high function tests"""

    def test_normal_drop(self):
        """Test drop percentage calculation"""
        from shared.utils.calc import calc_drop_from_high

        # 3% drop from 100 to 97
        result = calc_drop_from_high(97.0, 100.0)
        assert result == pytest.approx(3.0)

    def test_no_drop(self):
        """Test no drop (current >= highest)"""
        from shared.utils.calc import calc_drop_from_high

        result = calc_drop_from_high(100.0, 100.0)
        assert result == 0.0

    def test_current_above_highest(self):
        """Test current price above highest"""
        from shared.utils.calc import calc_drop_from_high

        result = calc_drop_from_high(105.0, 100.0)
        assert result == 0.0

    def test_zero_highest(self):
        """Test zero highest price returns 0"""
        from shared.utils.calc import calc_drop_from_high

        result = calc_drop_from_high(100.0, 0.0)
        assert result == 0.0


class TestCalcOrderQuantity:
    """calc_order_quantity function tests"""

    def test_normal_calculation(self):
        """Test normal quantity calculation"""
        from shared.utils.calc import calc_order_quantity

        # 1,000,000 / 50,000 = 20
        result = calc_order_quantity(1_000_000, 50_000)
        assert result == 20

    def test_capped_at_max(self):
        """Test quantity capped at max"""
        from shared.utils.calc import calc_order_quantity

        result = calc_order_quantity(1_000_000_000, 1, max_quantity=100)
        assert result == 100

    def test_zero_price(self):
        """Test zero price returns 0"""
        from shared.utils.calc import calc_order_quantity

        result = calc_order_quantity(1_000_000, 0)
        assert result == 0

    def test_zero_amount(self):
        """Test zero amount returns 0"""
        from shared.utils.calc import calc_order_quantity

        result = calc_order_quantity(0, 50_000)
        assert result == 0


class TestValidatePrice:
    """validate_price function tests"""

    def test_valid_price(self):
        """Test valid price returns True"""
        from shared.utils.calc import validate_price

        assert validate_price(100.0) is True
        assert validate_price(50000.0) is True

    def test_invalid_none(self):
        """Test None returns False"""
        from shared.utils.calc import validate_price

        assert validate_price(None) is False

    def test_invalid_negative(self):
        """Test negative returns False"""
        from shared.utils.calc import validate_price

        assert validate_price(-1.0) is False

    def test_out_of_range(self):
        """Test out of range returns False"""
        from shared.utils.calc import validate_price

        assert validate_price(100.0, min_price=200.0) is False
        assert validate_price(100.0, max_price=50.0) is False

    def test_boundary_exclusive(self):
        """Test boundary values are exclusive"""
        from shared.utils.calc import validate_price

        # min and max are exclusive
        assert validate_price(0.0, min_price=0.0) is False
        assert validate_price(100.0, max_price=100.0) is False
