"""Shared builders for the Trustworthy Time property tests (time design §7).

Firewall-clean: imports only ``tos.canonical`` / ``tos.time`` (time design §0.3).
The ``issue_time_snapshot`` builder populates every required-covered field so a
"valid" fixture is genuinely issuable (not a coverage illusion).
"""

from __future__ import annotations

from typing import Any

from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.time import (
    EvaluatedMonotonicAnchor,
    HealthState,
    TimeContinuityIdentity,
    TimeHealthSnapshot,
)

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


def time_snapshot_required_kwargs(**overrides: Any) -> dict[str, Any]:
    """Return issuance kwargs with every required-covered field concrete."""
    base: dict[str, Any] = {
        "snapshot_id": "ths-1",
        "generation": 1,
        "health_state": HealthState.TRUSTED,
        "time_continuity_identity": TimeContinuityIdentity(
            host_or_runtime_id="host-1",
            boot_id="boot-1",
            process_id="proc-1",
            monotonic_anchor_id="anchor-1",
            monotonic_anchor_value=1000,
            tts_generation=1,
        ),
        "evaluated_monotonic_anchor": EvaluatedMonotonicAnchor(
            monotonic_anchor_id="anchor-1", monotonic_anchor_value=1000
        ),
        "issuer_continuity_id": "anchor-1",
        "issue_monotonic_value": 1000,
        "tz_db_version": "2026a",
        "trading_calendar_version": "cal-1",
        "verification_profile_version": "vp-0",
        "safety_profile_version": "sp-0",
    }
    base.update(overrides)
    return base


def issue_time_snapshot(**overrides: Any) -> TimeHealthSnapshot:
    """Issue a valid :class:`TimeHealthSnapshot` (all required fields populated)."""
    return TimeHealthSnapshot.issue(
        scheme=SCHEME, **time_snapshot_required_kwargs(**overrides)
    )
