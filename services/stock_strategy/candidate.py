"""Stock-native candidate serializer for signal.candidate.stock.

The orchestrator Signal (shared.models.signal.Signal) has no to_stream_dict;
stock has no entry-time stop/target (the three_stage exit owns stops), so the
futures 11-field decision schema is not reused. This emits a stock-native dict.
"""

from __future__ import annotations

import json
from datetime import UTC

from shared.models.signal import Signal


def stock_signal_to_stream_dict(signal: Signal, *, signal_id: str) -> dict[str, str]:
    """Flatten an orchestrator Signal into Redis XADD fields (all str)."""
    ts = signal.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    generated_ms = str(int(ts.timestamp() * 1000))
    metadata = signal.metadata if isinstance(signal.metadata, dict) else {}
    direction = str(
        metadata.get("signal_direction") or metadata.get("direction") or "long"
    )
    return {
        "signal_id": signal_id,
        "code": signal.code,
        "name": signal.name,
        "strategy": signal.strategy,
        "direction": direction,
        "price": str(signal.price),
        "quantity": str(signal.quantity),
        "confidence": str(signal.confidence),
        "generated_at_ms": generated_ms,
        "metadata_json": json.dumps(metadata, ensure_ascii=False, default=str),
    }
