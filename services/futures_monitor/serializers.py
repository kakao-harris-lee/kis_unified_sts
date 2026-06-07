"""Pure parsers + dashboard dict builders for the futures monitor bridge.

Translates decoupled daemon stream records (order.fill.futures.* /
signal.final.futures.*) into the dashboard-native dict shapes the React Cockpit
reads via TradingStateReader. Side-aware, contract-multiplier PnL. No I/O.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def _s(fields: dict[bytes, bytes], key: str) -> str:
    raw = fields.get(key.encode(), b"")
    return raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)


def _ms_to_iso(ms: str) -> str:
    """Epoch-ms string -> tz-aware ISO; empty/invalid -> current UTC.

    The empty/invalid -> ``datetime.now(UTC)`` fallback intentionally matches
    ``_tz_aware_iso(None)`` in ``shared/streaming/trading_state.py``.
    """
    if not ms:
        return datetime.now(UTC).isoformat()
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=UTC).isoformat()
    except (TypeError, ValueError):
        return datetime.now(UTC).isoformat()


def parse_fill(fields: dict[bytes, bytes]) -> dict[str, Any]:
    """Parse an order.fill.futures.* record (FillLogger schema)."""
    return {
        "signal_id": _s(fields, "signal_id"),
        "order_id": _s(fields, "order_id"),
        "symbol": _s(fields, "symbol"),
        "side": _s(fields, "side") or "long",
        "filled_price": float(_s(fields, "filled_price") or 0.0),
        "quantity": int(float(_s(fields, "quantity") or 0)),
        "trade_role": _s(fields, "trade_role"),
        "filled_at_ms": _s(fields, "filled_at_ms"),
    }


def parse_final_signal(fields: dict[bytes, bytes]) -> dict[str, Any]:
    """Parse a signal.final.futures.* record (Signal.to_stream_dict schema)."""
    return {
        "signal_id": _s(fields, "signal_id"),
        "symbol": _s(fields, "symbol"),
        "setup_type": _s(fields, "setup_type"),
        "direction": _s(fields, "direction") or "long",
        "entry_price": float(_s(fields, "entry_price") or 0.0),
        "confidence": float(_s(fields, "confidence") or 0.0),
        "generated_at_ms": _s(fields, "generated_at_ms"),
    }


def build_position_dict(
    fill: dict[str, Any], meta: dict[str, Any], *, multiplier: float
) -> dict[str, Any]:
    """Dashboard open-position dict (mirrors _serialize_position), side-aware."""
    symbol = fill["symbol"]
    entry = fill["filled_price"]
    return {
        "id": symbol,
        "code": symbol,
        "name": "",
        "side": fill["side"],
        "quantity": fill["quantity"],
        "entry_price": entry,
        "current_price": entry,
        "unrealized_pnl": 0.0,
        "pnl_pct": 0.0,
        "entry_time": _ms_to_iso(fill["filled_at_ms"]),
        "strategy": meta.get("setup_type", ""),
        "state": "survival",
        "highest_price": entry,
        "lowest_price": entry,
        "fee_rate": 0.0,
        "stop_price": None,
        "client_order_id": fill["signal_id"],
    }


def build_trade_dict(
    entry: dict[str, Any], exit_fill: dict[str, Any], *, pnl: float
) -> dict[str, Any]:
    """Dashboard closed-trade dict (mirrors _serialize_closed_position), side-aware."""
    ep = float(entry["entry_price"])
    xp = float(exit_fill["filled_price"])
    qty = exit_fill["quantity"]
    side = entry.get("side", "long")
    if not ep:
        pnl_pct = 0.0
    elif side == "long":
        pnl_pct = (xp - ep) / ep * 100
    else:
        pnl_pct = (ep - xp) / ep * 100
    return {
        "id": exit_fill["order_id"] or exit_fill["signal_id"],
        "symbol": entry["symbol"],
        "name": entry.get("name", ""),
        "side": side,
        "quantity": qty,
        "entry_price": ep,
        "exit_price": xp,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "strategy": entry.get("setup_type", ""),
        "entry_time": entry.get("entry_time", ""),
        "exit_time": _ms_to_iso(exit_fill["filled_at_ms"]),
        "exit_reason": exit_fill["trade_role"],
    }


def build_signal_dict(sig: dict[str, Any]) -> dict[str, Any]:
    """Dashboard signal dict (mirrors orchestrator convention)."""
    return {
        "id": sig["signal_id"],
        "symbol": sig["symbol"],
        "name": "",
        "side": "entry",
        "signal_type": "entry",
        "strategy": sig["setup_type"],
        "price": sig["entry_price"],
        "confidence": sig["confidence"],
        "timestamp": _ms_to_iso(sig["generated_at_ms"]),
        "executed": True,
        "reason": "",
        "stage": "",
    }
