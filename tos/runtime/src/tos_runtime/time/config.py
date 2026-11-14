"""Trustworthy Time runtime config loader (slice plan §1 item 4)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from tos_runtime._named_tbd import reject_named_tbd

__all__ = ["TimeConfigError", "TrustworthyTimeConfig", "load_time_config"]


class TimeConfigError(Exception):
    """Raised when the Trustworthy Time config is missing, malformed, or"""


_BOUND_KEYS: tuple[str, ...] = (
    "MAX_time_source_precision_ms",
    "MAX_time_transport_and_queue_uncertainty_ms",
    "MAX_time_conservative_freshness_age_ms",
    "MAX_future_timestamp_tolerance_ms",
    "MAX_process_suspension_ms",
    "MAX_time_source_disagreement_ms",
    "MIN_time_independent_reference_count",
    "MAX_clock_domain_conversion_uncertainty_ms",
    "MAX_send_result_wait_ms",
    "MAX_critical_input_consumer_receipt_age_ms",
    "MAX_time_source_sequence_gap_ms",
)

_VERSION_KEYS: tuple[str, ...] = (
    "tz_db_version",
    "trading_calendar_version",
    "verification_profile_version",
    "safety_profile_version",
)

_OPERATIONAL_INT_KEYS: tuple[str, ...] = ("time_health_snapshot_heartbeat_ms",)

_STRICTLY_POSITIVE_KEYS: frozenset[str] = frozenset({"MAX_send_result_wait_ms"})

_BOUND_FIELD_BY_KEY: dict[str, str] = {
    "MAX_time_source_precision_ms": "max_time_source_precision_ms",
    "MAX_time_transport_and_queue_uncertainty_ms": (
        "max_time_transport_and_queue_uncertainty_ms"
    ),
    "MAX_time_conservative_freshness_age_ms": "max_time_conservative_freshness_age_ms",
    "MAX_future_timestamp_tolerance_ms": "max_future_timestamp_tolerance_ms",
    "MAX_process_suspension_ms": "max_process_suspension_ms",
    "MAX_time_source_disagreement_ms": "max_time_source_disagreement_ms",
    "MIN_time_independent_reference_count": "min_time_independent_reference_count",
    "MAX_clock_domain_conversion_uncertainty_ms": (
        "max_clock_domain_conversion_uncertainty_ms"
    ),
    "MAX_send_result_wait_ms": "max_send_result_wait_ms",
    "MAX_critical_input_consumer_receipt_age_ms": (
        "max_critical_input_consumer_receipt_age_ms"
    ),
    "MAX_time_source_sequence_gap_ms": "max_time_source_sequence_gap_ms",
}


@dataclass(frozen=True)
class TrustworthyTimeConfig:
    """Fully-valued Trustworthy Time runtime configuration."""

    max_time_source_precision_ms: int
    max_time_transport_and_queue_uncertainty_ms: int
    max_time_conservative_freshness_age_ms: int
    max_future_timestamp_tolerance_ms: int
    max_process_suspension_ms: int
    max_time_source_disagreement_ms: int
    min_time_independent_reference_count: int
    max_clock_domain_conversion_uncertainty_ms: int
    max_send_result_wait_ms: int
    max_critical_input_consumer_receipt_age_ms: int
    max_time_source_sequence_gap_ms: int
    tz_db_version: str
    trading_calendar_version: str
    verification_profile_version: str
    safety_profile_version: str
    time_health_snapshot_heartbeat_ms: int


def _require_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise TimeConfigError(f"time config file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TimeConfigError(f"time config file could not be read: {path}") from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise TimeConfigError(f"time config file is not valid YAML: {path}") from exc
    if not isinstance(raw, dict):
        raise TimeConfigError(
            f"time config file must be a top-level mapping: {path} (got {type(raw)!r})"
        )
    return raw


def _resolve_bounds(raw: dict[str, Any]) -> dict[str, Any]:
    missing = [key for key in _BOUND_KEYS if key not in raw]
    if missing:
        raise TimeConfigError(f"time config missing required keys: {missing}")
    unfilled = [key for key in _BOUND_KEYS if raw[key] is None]
    if unfilled:
        raise TimeConfigError(
            "time config has unfilled (named-TBD) keys — fail-closed at "
            f"startup until a Bounds-Approver decision fills them: {unfilled}"
        )
    resolved: dict[str, Any] = {}
    for key in _BOUND_KEYS:
        value = raw[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise TimeConfigError(
                f"time config key {key!r} must be a non-negative int (got {value!r})"
            )
        if key in _STRICTLY_POSITIVE_KEYS:
            if value <= 0:
                raise TimeConfigError(
                    f"time config key {key!r} must be a positive int (got {value!r}) — a "
                    "zero wait bound is not a shorter wait, it is a silently-disabled send "
                    "boundary (independent review finding #16)"
                )
        elif value < 0:
            raise TimeConfigError(
                f"time config key {key!r} must be non-negative (got {value!r})"
            )
        resolved[_BOUND_FIELD_BY_KEY[key]] = value
    return resolved


def _resolve_operational(raw: dict[str, Any]) -> dict[str, Any]:
    """Resolve :data:`_OPERATIONAL_INT_KEYS`, fail-closed on the same three failures the"""
    missing = [key for key in _OPERATIONAL_INT_KEYS if key not in raw]
    if missing:
        raise TimeConfigError(f"time config missing required keys: {missing}")
    resolved: dict[str, Any] = {}
    for key in _OPERATIONAL_INT_KEYS:
        value = raw[key]
        if value is None:
            raise TimeConfigError(
                "time config has unfilled (named-TBD) keys — fail-closed at startup "
                f"until an operator decision fills them: [{key!r}]"
            )
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise TimeConfigError(
                f"time config key {key!r} must be a positive int (got {value!r})"
            )
        resolved[key] = value
    return resolved


def _resolve_versions(raw: dict[str, Any]) -> dict[str, Any]:
    missing = [key for key in _VERSION_KEYS if key not in raw]
    if missing:
        raise TimeConfigError(f"time config missing required keys: {missing}")
    resolved: dict[str, Any] = {}
    for key in _VERSION_KEYS:
        value = raw[key]
        if not isinstance(value, str) or not value.strip():
            raise TimeConfigError(
                f"time config key {key!r} must be a non-blank string (got {value!r})"
            )
        reject_named_tbd(
            value, field=key, context="time config", error_cls=TimeConfigError
        )
        resolved[key] = value
    return resolved


def load_time_config(path: Path) -> TrustworthyTimeConfig:
    """Load + validate a Trustworthy Time config file, fail-closed."""
    raw = _require_mapping(path)
    bounds = _resolve_bounds(raw)
    versions = _resolve_versions(raw)
    operational = _resolve_operational(raw)
    return TrustworthyTimeConfig(**bounds, **versions, **operational)
