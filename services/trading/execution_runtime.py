"""Small execution-runtime owner helpers for the trading orchestrator."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any


def finalize_entry_execution_metadata(
    *,
    signal: Any,
    fill_price: float,
    is_short: bool,
    execution_meta: dict[str, Any],
    tick_size: float = 0.02,
) -> dict[str, Any]:
    """Finalize entry execution metadata without mutating the source mapping."""
    meta = dict(execution_meta)
    signal_price = float(signal.price)
    submit_price = float(meta.get("submit_price", signal_price) or signal_price)
    fill_price = float(fill_price)

    meta["signal_price"] = signal_price
    meta["submit_price"] = submit_price
    meta["fill_price"] = fill_price

    try:
        from shared.execution.slippage_control import compute_adverse_slippage_ticks
    except ImportError:
        return meta

    slippage_ticks = compute_adverse_slippage_ticks(
        signal_price=signal_price,
        fill_price=fill_price,
        is_buy=(not is_short),
        tick_size=tick_size,
    )
    meta["slippage_ticks"] = float(slippage_ticks)
    meta["slippage_tick_size"] = tick_size
    return meta


def record_mock_mirror_result(
    position: Any,
    stats: MutableMapping[str, int],
    label: str,
    result: dict[str, Any] | None,
) -> None:
    """Record normalized mock-mirror metadata and increment outcome stats."""
    normalized = dict(result or {})
    if "success" not in normalized:
        normalized["success"] = False
        normalized.setdefault("message", "mock_mirror_no_result")
    normalized.setdefault("skipped", False)

    metadata = position.metadata if isinstance(position.metadata, dict) else {}
    metadata = dict(metadata)
    mirror_meta = metadata.get("mock_mirror")
    mirror_meta = {} if not isinstance(mirror_meta, dict) else dict(mirror_meta)
    mirror_meta[label] = normalized
    metadata["mock_mirror"] = mirror_meta
    position.metadata = metadata

    if normalized.get("skipped"):
        outcome = "skipped"
    elif normalized.get("success"):
        outcome = "success"
    else:
        outcome = "failed"
    key = f"{label}_{outcome}"
    stats[key] = int(stats.get(key, 0)) + 1


def mock_mirror_exit_should_skip(position: Any) -> bool:
    """Return true when exit mirroring should be skipped after entry failure."""
    metadata = position.metadata if isinstance(position.metadata, dict) else {}
    mirror_meta = metadata.get("mock_mirror")
    if not isinstance(mirror_meta, dict):
        return False
    entry_result = mirror_meta.get("entry")
    if not isinstance(entry_result, dict):
        return False
    return entry_result.get("success") is False
