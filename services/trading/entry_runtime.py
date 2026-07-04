"""Pure entry-admission helpers for the trading orchestrator."""

from __future__ import annotations

from typing import Any


def entry_signal_priority(signal: Any) -> tuple[float, float, str, str]:
    """Sort key for deterministic stock entry admission."""
    metadata = getattr(signal, "metadata", {}) or {}
    if not isinstance(metadata, dict):
        metadata = {}
    raw_priority = metadata.get("entry_priority", metadata.get("pattern_priority"))
    if raw_priority is None:
        priority = 1_000_000.0
    else:
        try:
            priority = float(raw_priority)
        except (TypeError, ValueError):
            priority = 1_000_000.0
    try:
        confidence = float(getattr(signal, "confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    return (
        priority,
        -confidence,
        str(getattr(signal, "strategy", "") or ""),
        str(getattr(signal, "code", "") or ""),
    )


def prioritize_entry_signals(signals: list[Any]) -> list[Any]:
    """Return signals ordered by explicit priority, preserving singleton identity."""
    if len(signals) <= 1:
        return signals
    return sorted(signals, key=entry_signal_priority)
