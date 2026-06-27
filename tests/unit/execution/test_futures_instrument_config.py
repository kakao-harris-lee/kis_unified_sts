"""Tests for shared futures instrument selection."""

from __future__ import annotations

from datetime import date

from shared.execution.futures_instrument import (
    DEFAULT_FUTURES_PRODUCT,
    FuturesInstrumentConfig,
    normalize_futures_product,
    resolve_futures_instrument_from_env,
)


def test_default_product_is_mini_front_month(monkeypatch):
    monkeypatch.delenv("FUTURES_TRADING_PRODUCT", raising=False)
    monkeypatch.delenv("FUTURES_STRATEGY_SYMBOL", raising=False)

    instrument = resolve_futures_instrument_from_env(target_date=date(2026, 3, 1))

    assert instrument == FuturesInstrumentConfig(
        symbol="A05603",
        product=DEFAULT_FUTURES_PRODUCT,
        source="FUTURES_TRADING_PRODUCT",
    )


def test_kospi200_product_selects_full_size_front_month(monkeypatch):
    monkeypatch.setenv("FUTURES_TRADING_PRODUCT", "KOSPI200")
    monkeypatch.delenv("FUTURES_STRATEGY_SYMBOL", raising=False)

    instrument = resolve_futures_instrument_from_env(target_date=date(2026, 3, 1))

    assert instrument.symbol == "A01603"
    assert instrument.product == "kospi200"
    assert instrument.source == "FUTURES_TRADING_PRODUCT"


def test_invalid_product_falls_back_to_mini(monkeypatch):
    monkeypatch.setenv("FUTURES_TRADING_PRODUCT", "nikkei")
    monkeypatch.delenv("FUTURES_STRATEGY_SYMBOL", raising=False)

    instrument = resolve_futures_instrument_from_env(target_date=date(2026, 3, 1))

    assert instrument.symbol == "A05603"
    assert instrument.product == "mini"


def test_explicit_strategy_symbol_overrides_front_month(monkeypatch):
    monkeypatch.setenv("FUTURES_TRADING_PRODUCT", "mini")
    monkeypatch.setenv("FUTURES_STRATEGY_SYMBOL", "A01603")

    instrument = resolve_futures_instrument_from_env(target_date=date(2026, 3, 1))

    assert instrument.symbol == "A01603"
    assert instrument.product == "mini"
    assert instrument.source == "FUTURES_STRATEGY_SYMBOL"


def test_normalize_futures_product_is_case_insensitive():
    assert normalize_futures_product(" KOSPI200 ") == "kospi200"
    assert normalize_futures_product(" mini ") == "mini"
    assert normalize_futures_product("") == "mini"
    assert normalize_futures_product(None) == "mini"
