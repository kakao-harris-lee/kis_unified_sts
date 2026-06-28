"""Shared futures instrument selection.

All futures daemons should resolve their active contract through this module so
paper/live/shadow services do not drift on product or symbol selection.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

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


_PRODUCT_TICK_SIZE = {
    "mini": 0.02,
    "kospi200": 0.05,
}


def normalize_futures_product(value: str | None) -> str:
    """Normalize FUTURES_TRADING_PRODUCT with mini as the safe runtime default."""
    product = (value or DEFAULT_FUTURES_PRODUCT).strip().lower()
    if product not in SUPPORTED_FUTURES_PRODUCTS:
        return DEFAULT_FUTURES_PRODUCT
    return product


def _env_float(value: str | None, default: float) -> float:
    if value is None or not str(value).strip():
        return default
    try:
        return float(str(value).strip())
    except ValueError:
        return default


def validate_futures_runtime_product_contract(
    *,
    environ: Mapping[str, str] | None = None,
) -> FuturesProductContractValidation:
    env = os.environ if environ is None else environ
    product = normalize_futures_product(env.get("FUTURES_TRADING_PRODUCT"))
    expected_tick = _PRODUCT_TICK_SIZE[product]
    actual_tick = _env_float(env.get("FUTURES_SLIPPAGE_TICK_SIZE"), 0.02)
    ok = abs(actual_tick - expected_tick) < 1e-9
    message = (
        "futures product contract ok"
        if ok
        else (
            f"{product} requires FUTURES_SLIPPAGE_TICK_SIZE={expected_tick:.2f}; "
            f"got {actual_tick:.2f}"
        )
    )
    return FuturesProductContractValidation(
        ok=ok,
        product=product,
        expected_tick_size=expected_tick,
        actual_tick_size=actual_tick,
        message=message,
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
