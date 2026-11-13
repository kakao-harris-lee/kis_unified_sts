"""Time Health Snapshot element schemas (time design §2.2, §2.5, §2.6, §4.7)."""

from __future__ import annotations

from pydantic import model_validator

from tos.canonical import ArtifactIntegrityError, FrozenModel


class AllFalseAuthority(FrozenModel):
    """Authority block: every declared boolean flag forced ``false`` (§6; §14.1 line 348)."""

    @model_validator(mode="after")
    def _all_false(self) -> AllFalseAuthority:
        """Reject construction if any authority flag is ``True`` (SAFE-044)."""
        for name in type(self).model_fields:
            if getattr(self, name) is True:
                raise ArtifactIntegrityError(
                    f"{type(self).__name__}.{name} must be false "
                    "(a time snapshot is not authority — §14.1 line 348, SAFE-044)"
                )
        return self


class TimeAuthorityEffect(AllFalseAuthority):
    """Time Health Snapshot authority effect — all false (§6; time design §0.2)."""

    creates_authority: bool = False
    may_mutate_live_state: bool = False
    may_release_capacity: bool = False
    may_rearm: bool = False


class UncertaintyInterval(FrozenModel):
    """Two-sided reference-frame uncertainty interval (time design §2.6, gap 3)."""

    lo: int | None = None
    hi: int | None = None


class TimeContinuityIdentity(FrozenModel):
    """Time continuity identity binding (ADR §5 line 111-126)."""

    host_or_runtime_id: str | None = None
    boot_id: str | None = None
    process_id: str | None = None
    monotonic_anchor_id: str | None = None
    monotonic_anchor_value: int | None = None
    tts_generation: int | None = None
    active_reference_source_set: tuple[str, ...] = ()
    reference_path_id: str | None = None
    tz_db_version: str | None = None
    trading_calendar_version: str | None = None
    verification_profile_version: str | None = None


class EvaluatedMonotonicAnchor(FrozenModel):
    """The monotonic anchor evaluated for this snapshot (ADR §8 line 194-206)."""

    monotonic_anchor_id: str | None = None
    monotonic_anchor_value: int | None = None


class MonotonicReading(FrozenModel):
    """A single per-continuity monotonic reading (time design §3, §4.1)."""

    monotonic_continuity_id: str | None = None
    local_monotonic_value: int | None = None


class ReferenceSource(FrozenModel):
    """A corroborating reference source (ADR §8 line 199-200; §4.3; §7; §15)."""

    source_id: str | None = None
    path_id: str | None = None
    common_mode_group: str | None = None
    quality: str | None = None
    reachable: bool = False
    healthy: bool = False
    offset_bound_ms: int | None = None
    drift_bound_ppm: int | None = None
    uncertainty_bound_ms: int | None = None


class Bounds(FrozenModel):
    """Injected magnitude-bound bundle for a snapshot (ADR §8 line 200)."""

    offset_bound_ms: int | None = None
    drift_bound_ppm: int | None = None
    uncertainty_bound_ms: int | None = None
    source_disagreement_bound_ms: int | None = None


class SuspensionStatus(FrozenModel):
    """Recorded process-suspension status (ADR §5 line 124; §11.2 line 277)."""

    suspended: bool = False
    suspension_ms: int | None = None


class DiscontinuityStatus(FrozenModel):
    """Recorded monotonic-discontinuity status (ADR §5 line 124; §13 line 333-335)."""

    discontinuity_detected: bool = False
    monotonic_reset: bool = False


class SessionContext(FrozenModel):
    """Trading-session context (ADR §4.7 line 103-105; §12 line 319)."""

    tz_id: str | None = None
    tz_db_version: str | None = None
    trading_calendar_version: str | None = None
    phase: str | None = None
    is_open: bool = False
    tz_version_conflict: bool = False
    boundary_value: int | None = None


class ConsumerReceiptAnchor(FrozenModel):
    """A consumer's own receipt anchor for a cross-continuity snapshot (ADR §8 line 212-220)."""

    consumer_monotonic_continuity_id: str | None = None
    consumer_local_monotonic_value_at_receipt: int | None = None
