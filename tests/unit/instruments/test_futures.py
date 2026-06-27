"""Tests for neutral futures instrument contract-code helpers."""

from datetime import date

from shared.instruments.futures import get_expiry_date, get_front_month_code


def test_mini_front_month_uses_legacy_a05_prefix():
    code = get_front_month_code(product="mini", target_date=date(2026, 3, 1))
    assert code == "A05603"


def test_kospi200_rolls_after_expiry():
    expiry = get_expiry_date(2026, 3)
    day_after = date(expiry.year, expiry.month, expiry.day + 1)
    assert get_front_month_code(product="kospi200", target_date=day_after) == "A01606"
