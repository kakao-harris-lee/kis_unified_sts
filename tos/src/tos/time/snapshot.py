"""Time Health Snapshot artifact (time design §2.1, gap 1 + gap 6a)."""

from __future__ import annotations

from typing import ClassVar

from tos.canonical import DigestBoundArtifact
from tos.time.domains import HealthState, ReasonCode
from tos.time.elements import (
    Bounds,
    DiscontinuityStatus,
    EvaluatedMonotonicAnchor,
    ReferenceSource,
    SuspensionStatus,
    TimeAuthorityEffect,
    TimeContinuityIdentity,
)


class TimeHealthSnapshot(DigestBoundArtifact):
    """An immutable Time Health Snapshot (time design §2.1; ADR §8 line 190-206)."""

    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "health_state",
        "time_continuity_identity.host_or_runtime_id",
        "time_continuity_identity.boot_id",
        "time_continuity_identity.process_id",
        "time_continuity_identity.monotonic_anchor_id",
        "time_continuity_identity.monotonic_anchor_value",
        "time_continuity_identity.tts_generation",
        "evaluated_monotonic_anchor.monotonic_anchor_id",
        "evaluated_monotonic_anchor.monotonic_anchor_value",
        "issuer_continuity_id",
        "issue_monotonic_value",
        "tz_db_version",
        "trading_calendar_version",
        "verification_profile_version",
        "safety_profile_version",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "health_state",
            "time_continuity_identity",
            "evaluated_monotonic_anchor",
            "wall_clock_observation",
            "reference_sources",
            "bounds",
            "suspension_status",
            "discontinuity_status",
            "tz_db_version",
            "trading_calendar_version",
            "issuer_continuity_id",
            "issue_monotonic_value",
            "maximum_consumer_age_ms",
            "verification_profile_version",
            "safety_profile_version",
            "reason_codes",
            "authority_effect",
        }
    )

    snapshot_id: str | None = None
    generation: int | None = None

    health_state: HealthState = HealthState.UNINITIALIZED
    time_continuity_identity: TimeContinuityIdentity = TimeContinuityIdentity()
    evaluated_monotonic_anchor: EvaluatedMonotonicAnchor = EvaluatedMonotonicAnchor()
    wall_clock_observation: int | None = None
    reference_sources: tuple[ReferenceSource, ...] = ()
    bounds: Bounds = Bounds()
    suspension_status: SuspensionStatus = SuspensionStatus()
    discontinuity_status: DiscontinuityStatus = DiscontinuityStatus()
    tz_db_version: str | None = None
    trading_calendar_version: str | None = None
    issuer_continuity_id: str | None = None
    issue_monotonic_value: int | None = None
    maximum_consumer_age_ms: int | None = None
    verification_profile_version: str | None = None
    safety_profile_version: str | None = None
    reason_codes: tuple[ReasonCode, ...] = ()
    authority_effect: TimeAuthorityEffect = TimeAuthorityEffect()
