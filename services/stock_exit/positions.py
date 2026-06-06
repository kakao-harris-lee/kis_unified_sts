"""Codec between the M4-O position hash record and a `Position`.

M4-O (services/stock_order_router) writes ``trading:stock:positions`` hash:
field = code, value = JSON ``{code, entry_price, quantity, opened_at_ms, state,
signal_id}``. M4-X reconstructs a `Position`, restores the running extremes
(``high_water``/``low_water``) it persists each cycle, and skips foreign records
(the orchestrator's PositionTracker uses ``entry_time``, not ``opened_at_ms``).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from shared.models.position import Position, PositionSide, PositionState

_STATE_BY_VALUE = {s.value: s for s in PositionState}


def parse_position_record(value: Any) -> dict[str, Any] | None:
    """Decode a hash value to a dict, or None for unusable/foreign records.

    Returns None unless the record carries the M4-O signature field
    ``opened_at_ms`` (and ``code``) — this skips the orchestrator's
    ``entry_time``-keyed entries that may share the same hash during the
    strangler period.
    """
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", errors="replace")
    try:
        rec = json.loads(value)
    except (TypeError, ValueError):
        return None
    if not isinstance(rec, dict) or "opened_at_ms" not in rec or "code" not in rec:
        return None
    return rec


def position_from_record(rec: dict[str, Any], *, fee_rate: float) -> Position:
    """Build a LONG `Position` from an M4-O record (+ persisted high/low if present)."""
    opened_ms = int(rec["opened_at_ms"])
    entry_time = datetime.fromtimestamp(opened_ms / 1000, tz=UTC)
    state = _STATE_BY_VALUE.get(
        str(rec.get("state", "survival")).lower(), PositionState.SURVIVAL
    )
    pos = Position(
        id=str(rec.get("signal_id") or rec["code"]),
        code=str(rec["code"]),
        name=str(rec.get("name", "")),
        side=PositionSide.LONG,
        quantity=int(rec["quantity"]),
        entry_price=float(rec["entry_price"]),
        entry_time=entry_time,
        state=state,
        fee_rate=fee_rate,
    )
    # __post_init__ seeds high/low to entry; restore persisted extremes if any.
    if rec.get("high_water") is not None:
        pos.highest_price = float(rec["high_water"])
    if rec.get("low_water") is not None:
        pos.lowest_price = float(rec["low_water"])
    return pos


def record_with_high_water(rec: dict[str, Any], pos: Position) -> str:
    """Re-serialize the record with the position's running extremes (restart recovery)."""
    return json.dumps(
        {**rec, "high_water": pos.highest_price, "low_water": pos.lowest_price}
    )
