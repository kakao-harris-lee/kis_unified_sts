"""Pure execution helper functions used by the trading orchestrator."""

from __future__ import annotations

from typing import Any


def normalize_entry_order_result(result: Any) -> tuple[bool, float, int, str]:
    """Normalize legacy/new entry-order return tuples."""
    if not isinstance(result, tuple):
        raise ValueError(f"Unexpected entry order result type: {type(result)}")
    if len(result) == 4:
        is_filled, fill_price, filled_qty, venue = result
        return bool(is_filled), float(fill_price), int(filled_qty), str(venue)
    if len(result) == 3:
        is_filled, fill_price, filled_qty = result
        return bool(is_filled), float(fill_price), int(filled_qty), "KRX"
    raise ValueError(f"Unexpected entry order result length: {len(result)}")


def get_signal_direction(signal: Any) -> str:
    """Extract normalized signal direction from metadata."""
    metadata = getattr(signal, "metadata", {}) or {}
    if not isinstance(metadata, dict):
        return "long"
    direction = metadata.get("signal_direction") or metadata.get("direction") or "long"
    direction = str(direction).strip().lower()
    return "short" if direction == "short" else "long"
