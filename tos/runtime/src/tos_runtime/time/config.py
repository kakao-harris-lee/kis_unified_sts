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
    # Kernel round #1 §2.2 (docs/plans/2026-09-08-tos-phase2-kernel-round-1-
    # commandtype-expiry-obligation-plan.md): the decision-expiry runtime
    # path needs a cross-continuity clock-domain-conversion bound for
    # tos.time.effective_snapshot_age_bound_from_continuity's
    # conversion_bound term. Named + coordinate-grounded, not invented here:
    # VERIFICATION-PROFILE-002.yaml:1070 already carries this exact key name
    # ("APPROVE per continuity-identity pair; a consumer not sharing the
    # issuer's continuity identity adds this bound instead of subtracting
    # clocks", APPROVED value 50) — reused verbatim, same VER-002-KEYS
    # convention tos.marketfeed/tos.backtest.resolver already document.
    "MAX_clock_domain_conversion_uncertainty_ms",
    # TOS Phase 3 Wave 1 Lane A-R (docs/plans/2026-09-09-tos-phase3-event-
    # core-plan.md §1.1): the wait bound tos_runtime.engine.driver.EngineDriver's
    # TimeoutInjector uses before treating a SENT_UNCONFIRMED hand-off with no
    # egress result as TIMEOUT (RFC-005 §11 "timeout = UNKNOWN, never
    # rejection"). No existing VERIFICATION-PROFILE-002 coordinate names this
    # exact bound (grepped 2026-09-09: no "result_wait"/"claim_to_send" key) —
    # unlike MAX_clock_domain_conversion_uncertainty_ms above, this is a new
    # named-TBD with no prior approved value to cite; a Bounds-Approver
    # decision fills it in before any deployment relies on timeout injection.
    "MAX_send_result_wait_ms",
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

#: Bound keys that must be strictly positive rather than merely non-negative (independent review
#: finding #16, 2026-09-09): ``MAX_send_result_wait_ms`` is the wait bound
#: :class:`~tos_runtime.engine.driver.EngineDriver`'s ``_TimeoutTracker`` uses before injecting a
#: synthetic ``TIMEOUT`` — a ``0`` value would time out every hand-off on the very next drain,
#: which is not a smaller wait, it is a silently-disabled send boundary, mirroring
#: ``replay_window_events``'s own "a zero/negative window is a disabled one" rule
#: (``tos_runtime.compose._engine_wiring._require_positive_int``). Every other bound key keeps
#: the plain non-negative rule below (deliberately not widened without a fresh review).
_STRICTLY_POSITIVE_KEYS: frozenset[str] = frozenset({"MAX_send_result_wait_ms"})

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
    "MAX_clock_domain_conversion_uncertainty_ms": (
        "max_clock_domain_conversion_uncertainty_ms"
    ),
    "MAX_send_result_wait_ms": "max_send_result_wait_ms",
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
    max_clock_domain_conversion_uncertainty_ms: int
    max_send_result_wait_ms: int
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
