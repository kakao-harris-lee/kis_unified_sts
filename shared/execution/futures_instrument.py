"""Shared futures instrument selection.

All futures daemons should resolve their active contract through this module so
paper/live/shadow services do not drift on product or symbol selection.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import NamedTuple

from shared.instruments.futures import get_front_month_code

DEFAULT_FUTURES_PRODUCT = "mini"
SUPPORTED_FUTURES_PRODUCTS = frozenset({"mini", "kospi200"})


@dataclass(frozen=True)
class FuturesInstrumentConfig:
    """Resolved futures instrument metadata."""

    symbol: str
    product: str
    source: str


@dataclass(frozen=True)
class FuturesProductContractValidation:
    ok: bool
    product: str
    expected_tick_size: float
    actual_tick_size: float
    message: str
    invalid_reasons: tuple[str, ...] = ()
    symbol: str | None = None
    symbol_source: str | None = None


_PRODUCT_TICK_SIZE = {
    "mini": 0.02,
    "kospi200": 0.05,
}

_SYMBOL_PREFIX_CONTRACTS = {
    "A01": ("kospi200", 0.05),
    "101": ("kospi200", 0.05),
    "A05": ("mini", 0.02),
}


class _ParsedTickSize(NamedTuple):
    value: float
    error: str | None = None


def normalize_futures_product(value: str | None) -> str:
    """Normalize FUTURES_TRADING_PRODUCT with mini as the safe runtime default."""
    product = (value or DEFAULT_FUTURES_PRODUCT).strip().lower()
    if product not in SUPPORTED_FUTURES_PRODUCTS:
        return DEFAULT_FUTURES_PRODUCT
    return product


def _env_tick_size(value: str | None, default: float) -> _ParsedTickSize:
    if value is None or not str(value).strip():
        return _ParsedTickSize(default)
    raw_value = str(value).strip()
    try:
        return _ParsedTickSize(float(raw_value))
    except ValueError:
        return _ParsedTickSize(
            default,
            f"invalid FUTURES_SLIPPAGE_TICK_SIZE={raw_value!r}",
        )


def _symbol_prefix_contract(symbol: str) -> tuple[str, float] | None:
    normalized_symbol = symbol.strip().upper()
    for prefix, contract in _SYMBOL_PREFIX_CONTRACTS.items():
        if normalized_symbol.startswith(prefix):
            return contract
    return None


def validate_futures_runtime_product_contract(
    *,
    environ: Mapping[str, str] | None = None,
) -> FuturesProductContractValidation:
    env = os.environ if environ is None else environ
    product = normalize_futures_product(env.get("FUTURES_TRADING_PRODUCT"))
    expected_tick = _PRODUCT_TICK_SIZE[product]
    parsed_tick = _env_tick_size(env.get("FUTURES_SLIPPAGE_TICK_SIZE"), 0.02)
    actual_tick = parsed_tick.value
    invalid_reasons: list[str] = []
    if parsed_tick.error is not None:
        invalid_reasons.append(parsed_tick.error)
    if abs(actual_tick - expected_tick) >= 1e-9:
        invalid_reasons.append(
            f"{product} requires FUTURES_SLIPPAGE_TICK_SIZE={expected_tick:.2f}; "
            f"got {actual_tick:.2f}"
        )
    explicit_symbol = (env.get("FUTURES_STRATEGY_SYMBOL") or "").strip()
    symbol_source = "FUTURES_STRATEGY_SYMBOL" if explicit_symbol else None
    symbol_contract = (
        _symbol_prefix_contract(explicit_symbol) if explicit_symbol else None
    )
    if symbol_contract is not None:
        symbol_product, symbol_tick = symbol_contract
        if product != symbol_product or abs(actual_tick - symbol_tick) >= 1e-9:
            invalid_reasons.append(
                f"FUTURES_STRATEGY_SYMBOL={explicit_symbol} requires "
                f"product={symbol_product} and "
                f"FUTURES_SLIPPAGE_TICK_SIZE={symbol_tick:.2f}; "
                f"got product={product} and FUTURES_SLIPPAGE_TICK_SIZE={actual_tick:.2f}"
            )
    ok = not invalid_reasons
    message = (
        "futures product contract ok"
        if ok
        else "; ".join(invalid_reasons)
    )
    return FuturesProductContractValidation(
        ok=ok,
        product=product,
        expected_tick_size=expected_tick,
        actual_tick_size=actual_tick,
        message=message,
        invalid_reasons=tuple(invalid_reasons),
        symbol=explicit_symbol or None,
        symbol_source=symbol_source,
    )


def resolve_futures_instrument_from_env(
    *,
    environ: Mapping[str, str] | None = None,
    target_date: date | None = None,
) -> FuturesInstrumentConfig:
    """Resolve the futures contract from env with an explicit symbol override."""
    env = os.environ if environ is None else environ
    product = normalize_futures_product(env.get("FUTURES_TRADING_PRODUCT"))
    explicit_symbol = (env.get("FUTURES_STRATEGY_SYMBOL") or "").strip()
    if explicit_symbol:
        return FuturesInstrumentConfig(
            symbol=explicit_symbol,
            product=product,
            source="FUTURES_STRATEGY_SYMBOL",
        )
    symbol = (
        get_front_month_code(product=product)
        if target_date is None
        else get_front_month_code(product=product, target_date=target_date)
    )
    return FuturesInstrumentConfig(
        symbol=symbol,
        product=product,
        source="FUTURES_TRADING_PRODUCT",
    )
