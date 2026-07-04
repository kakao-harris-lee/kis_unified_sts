"""Helper functions for runtime ledger persistence."""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _value(value: Any) -> Any:
    """Convert common runtime values to SQLite/JSON-friendly values."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return _json_safe(asdict(value))
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump())
    return value


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return _value(value)


def _as_mapping(record: Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(record, Mapping):
        data = dict(record)
    elif is_dataclass(record) and not isinstance(record, type):
        data = asdict(record)
    elif hasattr(record, "model_dump"):
        data = record.model_dump()
    else:
        data = {
            key: getattr(record, key)
            for key in dir(record)
            if not key.startswith("_") and not callable(getattr(record, key))
        }

    safe_data = _json_safe(data)
    if not isinstance(safe_data, dict):
        return {}
    data = safe_data

    # Preserve common computed properties from Position-like objects.
    for attr in ("profit_pct", "profit_rate", "unrealized_pnl"):
        if attr not in data and hasattr(record, attr):
            with suppress(Exception):
                data[attr] = _json_safe(getattr(record, attr))
    return data


def _coalesce(data: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = data.get(key)
        if value is not None and value != "":
            return value
    return default


def _record_id(data: Mapping[str, Any], prefix: str, *keys: str) -> str:
    value = _coalesce(data, "id", *keys)
    if value is not None:
        return str(value)
    return f"{prefix}_{uuid.uuid4().hex}"


def _resolve_track_id(data: Mapping[str, Any], track_id: str | None) -> str | None:
    """Resolve the row track tag: explicit argument wins over payload key."""
    resolved = track_id if track_id is not None else _coalesce(data, "track_id")
    return str(resolved) if resolved is not None else None


def _json_payload(data: Mapping[str, Any]) -> str:
    return json.dumps(_json_safe(data), ensure_ascii=False, sort_keys=True)


def _pnl(data: Mapping[str, Any]) -> float | None:
    value = _coalesce(data, "pnl", "realized_pnl", "unrealized_pnl")
    if value is not None:
        return float(value)

    entry_price = _coalesce(data, "entry_price")
    exit_price = _coalesce(data, "exit_price")
    quantity = _coalesce(data, "quantity")
    if entry_price is None or exit_price is None or quantity is None:
        return None

    side = str(_coalesce(data, "side", default="long")).lower()
    if side == "short":
        return (float(entry_price) - float(exit_price)) * int(quantity)
    return (float(exit_price) - float(entry_price)) * int(quantity)


def _pnl_pct(data: Mapping[str, Any], pnl: float | None) -> float | None:
    value = _coalesce(data, "pnl_pct", "profit_pct")
    if value is not None:
        return float(value)
    if pnl is None:
        return None
    entry_price = _coalesce(data, "entry_price")
    quantity = _coalesce(data, "quantity")
    if entry_price is None or quantity is None:
        return None
    notional = max(float(entry_price) * int(quantity), 1e-9)
    return (pnl / notional) * 100.0


def _hold_seconds(data: Mapping[str, Any]) -> int | None:
    value = _coalesce(data, "hold_seconds", "hold_duration_seconds")
    if value is not None:
        return int(float(value))

    entry_time = _coalesce(data, "entry_time", "entry_date")
    exit_time = _coalesce(data, "exit_time", "exit_date")
    if not isinstance(entry_time, str) or not isinstance(exit_time, str):
        return None
    try:
        entry = datetime.fromisoformat(entry_time)
        exit_ = datetime.fromisoformat(exit_time)
    except ValueError:
        return None
    return max(int((exit_ - entry).total_seconds()), 0)
