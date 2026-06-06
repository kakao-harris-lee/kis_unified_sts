"""Pure parsers + dashboard dict builders for the stock monitor bridge.

Translates the decoupled daemon stream records (order.fill.stock.* /
signal.final.stock.*) into the dashboard-native dict shapes the React Cockpit
reads via TradingStateReader (mirrors TradingStatePublisher._serialize_*).
No Redis / I/O — pure functions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def _s(fields: dict[bytes, bytes], key: str) -> str:
    raw = fields.get(key.encode(), b"")
    return raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)


def _ms_to_iso(ms: str) -> str:
    """Epoch-ms string -> tz-aware ISO; empty/invalid -> current UTC."""
    if not ms:
        return datetime.now(UTC).isoformat()
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=UTC).isoformat()
    except (TypeError, ValueError):
        return datetime.now(UTC).isoformat()


def parse_fill(fields: dict[bytes, bytes]) -> dict[str, Any]:
    """Parse an order.fill.stock.* record (FillLogger schema)."""
    return {
        "signal_id": _s(fields, "signal_id"),
        "order_id": _s(fields, "order_id"),
        "code": _s(fields, "symbol"),
        "side": _s(fields, "side"),
        "filled_price": float(_s(fields, "filled_price") or 0.0),
        "quantity": int(float(_s(fields, "quantity") or 0)),
        "trade_role": _s(fields, "trade_role"),
        "filled_at_ms": _s(fields, "filled_at_ms"),
    }


def parse_final_signal(fields: dict[bytes, bytes]) -> dict[str, Any]:
    """Parse a signal.final.stock.* record (M4-P candidate + M4-R fields)."""
    return {
        "signal_id": _s(fields, "signal_id"),
        "code": _s(fields, "code"),
        "name": _s(fields, "name"),
        "strategy": _s(fields, "strategy"),
        "direction": _s(fields, "direction") or "long",
        "price": float(_s(fields, "price") or 0.0),
        "confidence": float(_s(fields, "confidence") or 0.0),
        "generated_at_ms": _s(fields, "generated_at_ms"),
    }


def build_position_dict(
    fill: dict[str, Any], meta: dict[str, Any], *, fee_rate: float
) -> dict[str, Any]:
    """Dashboard open-position dict (mirrors TradingStatePublisher._serialize_position)."""
    code = fill["code"]
    entry = fill["filled_price"]
    return {
        "id": code,
        "code": code,
        "name": meta.get("name", ""),
        "side": "long",
        "quantity": fill["quantity"],
        "entry_price": entry,
        "current_price": entry,
        "unrealized_pnl": 0.0,
        "pnl_pct": 0.0,
        "entry_time": _ms_to_iso(fill["filled_at_ms"]),
        "strategy": meta.get("strategy", ""),
        "state": "survival",
        "highest_price": entry,
        "lowest_price": entry,
        "fee_rate": fee_rate,
        "stop_price": None,
        "client_order_id": fill["signal_id"],
    }


def build_trade_dict(
    entry: dict[str, Any], exit_fill: dict[str, Any], *, pnl: float, fee_rate: float
) -> dict[str, Any]:
    """Dashboard closed-trade dict (mirrors _serialize_closed_position)."""
    ep = float(entry["entry_price"])
    xp = float(exit_fill["filled_price"])
    qty = exit_fill["quantity"]
    pnl_pct = ((xp - ep) / ep * 100) if ep else 0.0
    return {
        "id": exit_fill["order_id"] or exit_fill["signal_id"],
        "symbol": entry["code"],
        "name": entry.get("name", ""),
        "side": "long",
        "quantity": qty,
        "entry_price": ep,
        "exit_price": xp,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "strategy": entry.get("strategy", ""),
        "entry_time": entry.get("entry_time", ""),
        "exit_time": _ms_to_iso(exit_fill["filled_at_ms"]),
        "exit_reason": "exit",  # fill schema carries no exit reason (spec §5.6)
    }


def build_signal_dict(sig: dict[str, Any]) -> dict[str, Any]:
    """Dashboard signal dict (mirrors TradingStatePublisher.publish_signal data)."""
    return {
        "id": sig["signal_id"],
        "symbol": sig["code"],
        "name": sig["name"],
        "side": sig["direction"],
        "signal_type": sig["direction"],
        "strategy": sig["strategy"],
        "price": sig["price"],
        "confidence": sig["confidence"],
        "timestamp": _ms_to_iso(sig["generated_at_ms"]),
        "executed": True,
        "reason": "",
        "stage": "",
    }
