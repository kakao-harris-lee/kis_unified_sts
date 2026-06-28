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


def test_resolved_futures_product_requires_matching_slippage_tick(monkeypatch):
    monkeypatch.setenv("FUTURES_TRADING_PRODUCT", "kospi200")
    monkeypatch.setenv("FUTURES_SLIPPAGE_TICK_SIZE", "0.02")

    from shared.execution.futures_instrument import (
        validate_futures_runtime_product_contract,
    )

    result = validate_futures_runtime_product_contract()

    assert result.ok is False
    assert result.product == "kospi200"
    assert result.expected_tick_size == 0.05
    assert result.actual_tick_size == 0.02
    assert "FUTURES_SLIPPAGE_TICK_SIZE=0.05" in result.message


def test_resolved_mini_product_accepts_default_slippage_tick(monkeypatch):
    monkeypatch.setenv("FUTURES_TRADING_PRODUCT", "mini")
    monkeypatch.delenv("FUTURES_SLIPPAGE_TICK_SIZE", raising=False)

    from shared.execution.futures_instrument import (
        validate_futures_runtime_product_contract,
    )

    result = validate_futures_runtime_product_contract()

    assert result.ok is True
    assert result.product == "mini"
    assert result.expected_tick_size == 0.02


def test_resolved_product_rejects_malformed_slippage_tick(monkeypatch):
    monkeypatch.setenv("FUTURES_TRADING_PRODUCT", "mini")
    monkeypatch.setenv("FUTURES_SLIPPAGE_TICK_SIZE", "abc")

    from shared.execution.futures_instrument import (
        validate_futures_runtime_product_contract,
    )

    result = validate_futures_runtime_product_contract()

    assert result.ok is False
    assert result.product == "mini"
    assert result.expected_tick_size == 0.02
    assert result.actual_tick_size == 0.02
    assert "invalid FUTURES_SLIPPAGE_TICK_SIZE='abc'" in result.message


def test_resolved_product_rejects_explicit_full_size_symbol_with_mini_contract(
    monkeypatch,
):
    monkeypatch.setenv("FUTURES_TRADING_PRODUCT", "mini")
    monkeypatch.setenv("FUTURES_SLIPPAGE_TICK_SIZE", "0.02")
    monkeypatch.setenv("FUTURES_STRATEGY_SYMBOL", "A01603")

    from shared.execution.futures_instrument import (
        validate_futures_runtime_product_contract,
    )

    result = validate_futures_runtime_product_contract()

    assert result.ok is False
    assert result.product == "mini"
    assert result.expected_tick_size == 0.02
    assert result.actual_tick_size == 0.02
    assert "FUTURES_STRATEGY_SYMBOL=A01603" in result.message
    assert "requires product=kospi200" in result.message


def test_resolved_product_rejects_numeric_full_size_symbol_with_mini_contract(
    monkeypatch,
):
    monkeypatch.setenv("FUTURES_TRADING_PRODUCT", "mini")
    monkeypatch.setenv("FUTURES_SLIPPAGE_TICK_SIZE", "0.02")
    monkeypatch.setenv("FUTURES_STRATEGY_SYMBOL", "101W09")

    from shared.execution.futures_instrument import (
        validate_futures_runtime_product_contract,
    )

    result = validate_futures_runtime_product_contract()

    assert result.ok is False
    assert result.product == "mini"
    assert result.expected_tick_size == 0.02
    assert result.actual_tick_size == 0.02
    assert "FUTURES_STRATEGY_SYMBOL=101W09" in result.message
    assert "requires product=kospi200" in result.message


def test_resolved_product_rejects_explicit_mini_symbol_with_full_size_contract(
    monkeypatch,
):
    monkeypatch.setenv("FUTURES_TRADING_PRODUCT", "kospi200")
    monkeypatch.setenv("FUTURES_SLIPPAGE_TICK_SIZE", "0.05")
    monkeypatch.setenv("FUTURES_STRATEGY_SYMBOL", "A05603")

    from shared.execution.futures_instrument import (
        validate_futures_runtime_product_contract,
    )

    result = validate_futures_runtime_product_contract()

    assert result.ok is False
    assert result.product == "kospi200"
    assert result.expected_tick_size == 0.05
    assert result.actual_tick_size == 0.05
    assert "FUTURES_STRATEGY_SYMBOL=A05603" in result.message
    assert "requires product=mini" in result.message


def test_resolved_product_allows_unknown_explicit_symbol_prefix(monkeypatch):
    monkeypatch.setenv("FUTURES_TRADING_PRODUCT", "mini")
    monkeypatch.setenv("FUTURES_SLIPPAGE_TICK_SIZE", "0.02")
    monkeypatch.setenv("FUTURES_STRATEGY_SYMBOL", "ZZ9999")

    from shared.execution.futures_instrument import (
        validate_futures_runtime_product_contract,
    )

    result = validate_futures_runtime_product_contract()

    assert result.ok is True
    assert result.product == "mini"
    assert result.symbol == "ZZ9999"
    assert result.symbol_source == "FUTURES_STRATEGY_SYMBOL"
    assert result.message == "futures product contract ok"
