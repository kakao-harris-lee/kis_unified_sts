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


def normalize_futures_product(value: str | None) -> str:
    """Normalize FUTURES_TRADING_PRODUCT with mini as the safe runtime default."""
    product = (value or DEFAULT_FUTURES_PRODUCT).strip().lower()
    if product not in SUPPORTED_FUTURES_PRODUCTS:
        return DEFAULT_FUTURES_PRODUCT
    return product


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
