"""``fill_observer.yaml`` — the post-ACK fill observer's cadence, bounds, and sealed witness"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from tos_runtime._named_tbd import reject_named_tbd

__all__ = [
    "FILL_OBSERVER_CONFIG_NAME",
    "FillObserverConfig",
    "FillObserverConfigError",
    "load_fill_observer_config",
]

FILL_OBSERVER_CONFIG_NAME = "fill_observer.yaml"


class FillObserverConfigError(Exception):
    """``fill_observer.yaml`` is missing, malformed, or has a non-positive bound."""


@dataclass(frozen=True)
class FillObserverConfig:
    """The observer's cadence and bounds plus the witness fields it seals (module docstring)."""

    witness_fields: dict[str, Any]
    poll_interval_ms: int
    overdue_after_ms: int
    finality_retry_interval_ms: int
    prior_day_poll_interval_ms: int
    poll_deadline_ms: int
    witness_request_timeout_s: float
    release_snapshot_max_age_ms: int
    held_position_poll_interval_ms: int | None = None
    held_position_max_age_ms: int | None = None


_WITNESS_KEYS = (
    "balance_path",
    "balance_tr_id",
    "order_inquiry_path",
    "order_inquiry_tr_id",
    "max_pages",
)


def _positive_number(raw: dict[str, Any], key: str, path: Path) -> float:
    """A positive int or float (a timeout in seconds is not naturally an int)."""
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise FillObserverConfigError(
            f"{path}: {key!r} must be a positive number, got {value!r}"
        )
    return float(value)


def _positive_int(raw: dict[str, Any], key: str, path: Path) -> int:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise FillObserverConfigError(
            f"{path}: {key!r} must be a positive int, got {value!r}"
        )
    return value


def load_fill_observer_config(path: Path) -> FillObserverConfig:
    """Load ``fill_observer.yaml``, fail-closed."""
    if not path.is_file():
        raise FillObserverConfigError(f"fill observer config not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise FillObserverConfigError(f"{path}: unreadable ({exc})") from exc
    if not isinstance(raw, dict):
        raise FillObserverConfigError(f"{path}: must be a top-level mapping")
    held_keys = ("held_position_poll_interval_ms", "held_position_max_age_ms")
    if any(key in raw for key in held_keys) and not all(
        key in raw for key in held_keys
    ):
        raise FillObserverConfigError(
            f"{path}: held position bounds must be supplied together"
        )
    missing = [key for key in _WITNESS_KEYS if key not in raw]
    if missing:
        raise FillObserverConfigError(f"{path}: missing {missing}")
    for key in _WITNESS_KEYS:
        reject_named_tbd(
            raw[key], field=key, context=str(path), error_cls=FillObserverConfigError
        )
    return FillObserverConfig(
        witness_fields={key: raw[key] for key in _WITNESS_KEYS},
        poll_interval_ms=_positive_int(raw, "poll_interval_ms", path),
        overdue_after_ms=_positive_int(raw, "overdue_after_ms", path),
        finality_retry_interval_ms=_positive_int(
            raw, "finality_retry_interval_ms", path
        ),
        prior_day_poll_interval_ms=_positive_int(
            raw, "prior_day_poll_interval_ms", path
        ),
        poll_deadline_ms=_positive_int(raw, "poll_deadline_ms", path),
        witness_request_timeout_s=_positive_number(
            raw, "witness_request_timeout_s", path
        ),
        release_snapshot_max_age_ms=_positive_int(
            raw, "release_snapshot_max_age_ms", path
        ),
        held_position_poll_interval_ms=(
            _positive_int(raw, "held_position_poll_interval_ms", path)
            if "held_position_poll_interval_ms" in raw
            else None
        ),
        held_position_max_age_ms=(
            _positive_int(raw, "held_position_max_age_ms", path)
            if "held_position_max_age_ms" in raw
            else None
        ),
    )
