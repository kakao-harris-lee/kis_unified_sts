"""Futures monitor's private positions hash codec (F-5).

The decoupled futures chain has no positions hash, so the futures monitor owns
``futures:monitor:positions`` (field=symbol) for restart recovery: HSET on
entry, update high/low on MTM, HDEL on exit, recover on startup. Records require
``opened_at_ms`` + ``symbol`` so foreign (orchestrator) records are skipped.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_position_record(state: dict[str, Any]) -> str:
    """JSON-encode an open-position state dict for HSET."""
    return json.dumps(
        {
            "symbol": state["symbol"],
            "side": state["side"],
            "entry_price": float(state["entry_price"]),
            "quantity": int(state["quantity"]),
            "opened_at_ms": int(state.get("opened_at_ms", 0) or 0),
            "setup_type": state.get("setup_type", ""),
            "signal_id": state.get("signal_id", ""),
            "high_water": float(state.get("high_water", state["entry_price"])),
            "low_water": float(state.get("low_water", state["entry_price"])),
        }
    )


def parse_futures_position_record(value: bytes | str) -> dict[str, Any] | None:
    """Decode a hash value; return None for foreign/invalid records.

    Requires both ``opened_at_ms`` and ``symbol`` (skips orchestrator-style
    records that lack ``opened_at_ms``).
    """
    try:
        raw = value.decode() if isinstance(value, bytes) else value
        rec = json.loads(raw)
    except (ValueError, AttributeError):
        return None
    if not isinstance(rec, dict):
        return None
    if "opened_at_ms" not in rec or "symbol" not in rec:
        return None
    return rec
