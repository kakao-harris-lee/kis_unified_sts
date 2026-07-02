"""Pure parsers + dashboard dict builders for the stock monitor bridge.

Translates the decoupled daemon stream records (order.fill.stock.* /
signal.final.stock.*) into the dashboard-native dict shapes the React Cockpit
reads via TradingStateReader (mirrors TradingStatePublisher._serialize_*).
No Redis / I/O — pure functions.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any


def _s(fields: dict[bytes, bytes], key: str) -> str:
    raw = fields.get(key.encode(), b"")
    return raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)


def _gate_from_metadata(raw: str) -> dict[str, Any] | None:
    """Extract ``market_risk_gate`` from an M4-P ``metadata_json`` field.

    The stock lane carries the gate trace inside the signal metadata
    (roadmap Phase 2C fixed key contract). None for absent/malformed
    metadata or a missing/non-dict gate key — passthrough only.
    """
    if not raw:
        return None
    try:
        metadata = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(metadata, dict):
        return None
    gate = metadata.get("market_risk_gate")
    return gate if isinstance(gate, dict) else None


def _ms_to_iso(ms: str) -> str:
    """Epoch-ms string -> tz-aware ISO; empty/invalid -> current UTC.

    The empty/invalid -> ``datetime.now(UTC)`` fallback intentionally matches
    ``_tz_aware_iso(None)`` in ``shared/streaming/trading_state.py`` — do not
    "fix" it to epoch-zero.
    """
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
        # Market-risk gate trace from the M4-P metadata (roadmap Phase 2C).
        # Passthrough-only: None on pre-gate records.
        "market_risk_gate": _gate_from_metadata(_s(fields, "metadata_json")),
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
    entry: dict[str, Any], exit_fill: dict[str, Any], *, pnl: float
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
    data = {
        "id": sig["signal_id"],
        "symbol": sig["code"],
        "name": sig["name"],
        # signal.final.stock.shadow records are risk-passed entry candidates;
        # mirror the orchestrator's convention (side/signal_type = "entry"/"exit",
        # NOT long/short) so M5a signals render identically on the Cockpit.
        "side": "entry",
        "signal_type": "entry",
        "strategy": sig["strategy"],
        "price": sig["price"],
        "confidence": sig["confidence"],
        "timestamp": _ms_to_iso(sig["generated_at_ms"]),
        "executed": True,
        "reason": "",
        "stage": "",
    }
    gate = sig.get("market_risk_gate")
    if isinstance(gate, dict):
        # Fixed key contract: the /signals trace lane resolves the gate from
        # the top-level ``market_risk_gate`` key first. Attached only when
        # present so pre-gate records keep their exact legacy shape.
        data["market_risk_gate"] = gate
    return data
