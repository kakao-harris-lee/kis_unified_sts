"""Tests for futures contract code generation and front-month detection."""

from datetime import date

from shared.collector.historical.futures import (
    get_expiry_date,
    get_front_month_code,
)


class TestGetFrontMonthCode:
    """Tests for get_front_month_code() auto-detection logic."""

    def test_before_expiry_returns_current_month(self):
        """Before the 2nd Thursday, front month is current month."""
        # 2026-03-01 is well before Mar expiry (2nd Thu = Mar 12)
        code = get_front_month_code(product="kospi200", target_date=date(2026, 3, 1))
        assert code == "A01603"

    def test_on_expiry_returns_current_month(self):
        """On expiry day itself, contract is still active (target <= expiry)."""
        expiry = get_expiry_date(2026, 3)  # 2nd Thursday of March 2026
        code = get_front_month_code(product="kospi200", target_date=expiry)
        assert code == "A01603"

    def test_after_expiry_rolls_to_next_quarter(self):
        """After expiry, should roll to next quarterly contract."""
        expiry = get_expiry_date(2026, 3)
        day_after = date(expiry.year, expiry.month, expiry.day + 1)
        code = get_front_month_code(product="kospi200", target_date=day_after)
        assert code == "A01606"

    def test_december_rollover_to_next_year_march(self):
        """After December expiry, should roll to March of next year."""
        expiry = get_expiry_date(2026, 12)
        day_after = date(expiry.year, expiry.month, expiry.day + 1)
        code = get_front_month_code(product="kospi200", target_date=day_after)
        assert code == "A01703"

    def test_mini_product_uses_correct_prefix(self):
        """Mini KOSPI200 uses A05 prefix instead of A01."""
        code = get_front_month_code(product="mini", target_date=date(2026, 3, 1))
        assert code.startswith("A05")
        assert code == "A05603"

    def test_kospi200_product_uses_correct_prefix(self):
        """Full-size KOSPI200 uses A01 prefix."""
        code = get_front_month_code(product="kospi200", target_date=date(2026, 3, 1))
        assert code.startswith("A01")

    def test_default_product_is_kospi200(self):
        """Default product should be kospi200 (A01 prefix)."""
        code = get_front_month_code(target_date=date(2026, 3, 1))
        assert code.startswith("A01")

    def test_mid_month_before_expiry(self):
        """A date mid-month but before 2nd Thursday stays in current month."""
        # March 2026: 2nd Thursday is Mar 12. Mar 10 is before expiry.
        code = get_front_month_code(product="kospi200", target_date=date(2026, 3, 10))
        assert code == "A01603"

    def test_mid_month_after_expiry(self):
        """A date mid-month but after 2nd Thursday rolls to next quarter."""
        # March 2026: 2nd Thursday is Mar 12. Mar 15 is after expiry.
        code = get_front_month_code(product="kospi200", target_date=date(2026, 3, 15))
        assert code == "A01606"
