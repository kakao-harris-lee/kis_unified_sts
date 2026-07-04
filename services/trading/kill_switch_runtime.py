"""Kill-switch owner helpers for trading orchestrator compatibility runtime."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class KillSwitchRequest:
    event_id: str
    source: str
    reason: str
    dry_run: bool


def _as_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    text = str(value)
    return text if text else default


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return _as_text(value).strip().lower() in {"1", "true", "yes", "on"}


def _payload_get(payload: Mapping[Any, Any], name: str) -> Any:
    if name in payload:
        return payload[name]
    encoded = name.encode()
    if encoded in payload:
        return payload[encoded]
    return None


def parse_force_flatten_request(
    payload: Mapping[Any, Any] | None,
) -> KillSwitchRequest:
    """Parse stream/sentinel payload fields without triggering side effects."""
    payload = payload or {}
    return KillSwitchRequest(
        event_id=_as_text(_payload_get(payload, "event_id")),
        source=_as_text(_payload_get(payload, "source"), default="unknown"),
        reason=_as_text(_payload_get(payload, "reason"), default="force_flatten"),
        dry_run=_as_bool(_payload_get(payload, "dry_run")),
    )
