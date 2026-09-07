"""Trustworthy Time runtime config loader (slice plan §1 item 4).

Loads ``tos/runtime/config/time.example.yaml`` (or an operator-approved copy):
the VER-002 profile keys' NAMES are fixed here exactly as marketfeed's own
consumption site names them (``tos/src/tos/marketfeed/__init__.py`` module
docstring's "VER-002-KEYS" line), so a Bounds-Approver decision recorded for
one consumer of a given key applies unambiguously to this one too — never a
locally-invented synonym. Every key's example value is ``null`` (named-TBD);
loading a config with any key missing or still ``null`` is a fail-closed
startup rejection (:class:`TimeConfigError`), per CLAUDE.md's non-negotiable
"configuration-driven only, no hardcoded thresholds" rule and slice plan §0
("값은 named-TBD 허용... 부재 시 기동 거부").
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

__all__ = ["TimeConfigError", "TrustworthyTimeConfig", "load_time_config"]


class TimeConfigError(Exception):
    """Raised when the Trustworthy Time config is missing, malformed, or
    carries an unfilled (missing/null) required key — fail-closed at load."""


#: VER-002 profile keys (integer, millisecond- or count-denominated bounds).
#: Names are load-bearing: reused verbatim at every consumption site (see the
#: module docstring). Do not rename without a Bounds-Approver / design-doc
#: revision, mirroring ``tos.marketfeed``'s own discipline for these keys.
_BOUND_KEYS: tuple[str, ...] = (
    "MAX_time_source_precision_ms",
    "MAX_time_transport_and_queue_uncertainty_ms",
    "MAX_time_conservative_freshness_age_ms",
    "MAX_future_timestamp_tolerance_ms",
    "MAX_process_suspension_ms",
    "MAX_time_source_disagreement_ms",
    "MIN_time_independent_reference_count",
)

#: Non-bound identity/version strings the service needs to issue a
#: required-covered ``TimeHealthSnapshot`` (``tos/src/tos/time/snapshot.py``
#: ``_REQUIRED_COVERED``: ``tz_db_version``, ``trading_calendar_version``,
#: ``verification_profile_version``, ``safety_profile_version``). These are
#: not VER-002 bounds (no threshold to approve), but they are still
#: configuration, not a code constant (CLAUDE.md "configuration-driven only"),
#: and still fail-closed when unfilled — an ISSUED snapshot without them is
#: unconstructable anyway (the kernel's own digest-identity guard), so
#: rejecting at config-load time surfaces the same fact earlier and louder.
_VERSION_KEYS: tuple[str, ...] = (
    "tz_db_version",
    "trading_calendar_version",
    "verification_profile_version",
    "safety_profile_version",
)

#: VER-002 key name -> :class:`TrustworthyTimeConfig` field name.
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
}


@dataclass(frozen=True)
class TrustworthyTimeConfig:
    """Fully-valued Trustworthy Time runtime configuration.

    Every field is concrete (never ``None``) by construction —
    :func:`load_time_config` is the only constructor path and it raises
    :class:`TimeConfigError` rather than ever building one with a gap.
    """

    max_time_source_precision_ms: int
    max_time_transport_and_queue_uncertainty_ms: int
    max_time_conservative_freshness_age_ms: int
    max_future_timestamp_tolerance_ms: int
    max_process_suspension_ms: int
    max_time_source_disagreement_ms: int
    min_time_independent_reference_count: int
    tz_db_version: str
    trading_calendar_version: str
    verification_profile_version: str
    safety_profile_version: str


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
        if value < 0:
            raise TimeConfigError(
                f"time config key {key!r} must be non-negative (got {value!r})"
            )
        resolved[_BOUND_FIELD_BY_KEY[key]] = value
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
        resolved[key] = value
    return resolved


def load_time_config(path: Path) -> TrustworthyTimeConfig:
    """Load + validate a Trustworthy Time config file, fail-closed.

    Args:
        path: Path to a YAML file shaped like
            ``tos/runtime/config/time.example.yaml``.

    Returns:
        A fully-valued :class:`TrustworthyTimeConfig`.

    Raises:
        TimeConfigError: The file is missing/unreadable/not valid YAML/not a
            mapping, a required key is missing, a required key is still
            ``null`` (named-TBD), or a value fails its type/sign check.
    """
    raw = _require_mapping(path)
    bounds = _resolve_bounds(raw)
    versions = _resolve_versions(raw)
    return TrustworthyTimeConfig(**bounds, **versions)
