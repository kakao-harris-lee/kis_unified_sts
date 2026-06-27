"""Tests for Korean-market identifier helpers."""

from shared.llm.identifiers import (
    calculate_isin_check_digit,
    krx_stock_code_to_isin,
    to_isin,
)


def test_calculate_isin_check_digit_known_example():
    # 삼성전자(005930) ISIN body -> check digit is known (KR7005930003)
    assert calculate_isin_check_digit("KR700593000") == "3"


def test_krx_stock_code_to_isin_known_example():
    assert krx_stock_code_to_isin("005930") == "KR7005930003"


def test_to_isin_accepts_isin_passthrough():
    assert to_isin("kr7005930003") == "KR7005930003"

