"""Metric synchronization helpers for the trading orchestrator."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def sync_open_positions_metric(metrics: Any, position_tracker: Any) -> int | None:
    """Synchronize the open-position gauge from tracker state."""
    if metrics is None or position_tracker is None:
        return None

    positions = getattr(position_tracker, "positions", None)
    if not isinstance(positions, Iterable):
        open_positions = 0
    else:
        open_positions = sum(
            1 for position in positions if getattr(position, "is_open", True)
        )

    open_positions = max(0, open_positions)
    metrics.record_position_change(open_positions)
    return open_positions
