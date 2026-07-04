"""Setup A/C signals_all row helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

# Futures Setup A/C strategy -> kospi.signals_all.setup_type code. Only these
# two are persisted to signals_all (the Phase 2 verification gates count
# setup_type IN ('A','C')); other strategies are not written.
SETUP_TYPE_BY_STRATEGY = {
    "setup_a_gap_reversion": "A",
    "setup_c_event_reaction": "C",
}

# Column order matches shared/backtest/signals_writer.py (Phase 5 risk_filter).
SIGNALS_ALL_INSERT_SQL = (
    "INSERT INTO kospi.signals_all "
    "(signal_id, generated_at, setup_type, direction, entry_price, stop_loss, "
    "take_profit, confidence, executed, skip_reason, reason_tags) VALUES"
)


def build_signals_all_row(
    signal: Any,
    direction: str,
    entry_price: float,
    executed: bool,
) -> tuple | None:
    """Build a ``kospi.signals_all`` row tuple for a Setup A/C signal."""
    setup_type = SETUP_TYPE_BY_STRATEGY.get(getattr(signal, "strategy", "") or "")
    if setup_type is None:
        return None

    generated_at = getattr(signal, "timestamp", None) or datetime.now(UTC)
    if generated_at.tzinfo is not None:
        # DateTime64(3,'UTC') expects naive UTC (see signals_writer.py).
        generated_at = generated_at.astimezone(UTC).replace(tzinfo=None)

    metadata = getattr(signal, "metadata", {}) or {}
    if not isinstance(metadata, dict):
        metadata = {}

    return (
        str(uuid.uuid4()),
        generated_at,
        setup_type,
        direction or "long",
        float(entry_price or getattr(signal, "price", 0) or 0),
        float(metadata.get("stop_loss", 0) or 0),
        float(metadata.get("take_profit", 0) or 0),
        float(getattr(signal, "confidence", 0) or 0),
        1 if executed else 0,
        "",
        [],
    )
