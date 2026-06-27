"""FUTURES_TRADING_PRODUCT selects the futures front-month product.

`mini` (default) → KOSPI200 mini (A05…, live); `kospi200` → full F200 (A01…,
tighter spread for paper signal validation). See
`TradingConfig._get_futures_default_symbols`.
"""

from __future__ import annotations

import pytest

from services.trading.orchestrator import TradingConfig


def test_default_product_is_mini(monkeypatch):
    monkeypatch.delenv("FUTURES_TRADING_PRODUCT", raising=False)
    monkeypatch.delenv("FUTURES_STRATEGY_SYMBOL", raising=False)
    symbols = TradingConfig._get_futures_default_symbols()
    assert len(symbols) == 1
    assert symbols[0].startswith("A05")  # mini legacy prefix


def test_kospi200_product_selects_f200(monkeypatch):
    monkeypatch.setenv("FUTURES_TRADING_PRODUCT", "kospi200")
    monkeypatch.delenv("FUTURES_STRATEGY_SYMBOL", raising=False)
    symbols = TradingConfig._get_futures_default_symbols()
    assert len(symbols) == 1
    assert symbols[0].startswith("A01")  # full F200 legacy prefix


@pytest.mark.parametrize("bad", ["", "FULL", "kospi", "nikkei"])
def test_invalid_product_falls_back_to_mini(monkeypatch, bad):
    monkeypatch.setenv("FUTURES_TRADING_PRODUCT", bad)
    monkeypatch.delenv("FUTURES_STRATEGY_SYMBOL", raising=False)
    symbols = TradingConfig._get_futures_default_symbols()
    assert symbols[0].startswith("A05")


def test_product_is_case_insensitive(monkeypatch):
    monkeypatch.setenv("FUTURES_TRADING_PRODUCT", "KOSPI200")
    monkeypatch.delenv("FUTURES_STRATEGY_SYMBOL", raising=False)
    symbols = TradingConfig._get_futures_default_symbols()
    assert symbols[0].startswith("A01")
