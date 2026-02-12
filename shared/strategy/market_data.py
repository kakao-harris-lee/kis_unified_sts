"""Shared helpers for strategy market-data access."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def get_symbol_snapshot(market_data: dict[str, Any], code: str) -> dict[str, Any]:
    """Return per-symbol snapshot from market_data (code -> dict).

    Supports a temporary legacy fallback where `market_data` itself is already a
    single-symbol payload.
    """
    symbol_data = market_data.get(code)
    if isinstance(symbol_data, dict):
        return symbol_data

    if isinstance(symbol_data, (int, float)):
        price = float(symbol_data)
        if price > 0:
            return {"close": price, "price": price}

    # Legacy fallback: root-level single-symbol dict.
    if "close" in market_data or "price" in market_data:
        logger.debug("Legacy market_data payload detected for code=%s", code)
        return market_data

    return {}


def get_price_from_snapshot(snapshot: dict[str, Any]) -> float | None:
    """Extract current price from snapshot."""
    for key in ("close", "price", "current_price"):
        value = snapshot.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    return None


def get_numeric_field(snapshot: dict[str, Any], key: str, default: float = 0.0) -> float:
    """Extract numeric field from snapshot."""
    value = snapshot.get(key, default)
    if isinstance(value, (int, float)):
        return float(value)
    return float(default)
