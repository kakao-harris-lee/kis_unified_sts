"""Time Health Snapshot element schemas (time design §2.2, §2.5, §2.6, §4.7).

Authored from ADR-002-008 §5/§7/§8/§12/§15 prose (ADR §8 leaves the array/element
schemas empty). Every element is a ``tos.canonical.FrozenModel``. All time values
are **opaque injected coordinates** — no model here reads a real clock
(``time``/``datetime``/``monotonic`` are firewall-forbidden; time design §0.3/§3).
No threshold is hard-coded; every bound is an injected slot (time design §8).

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only.
"""

from __future__ import annotations

from pydantic import model_validator

from tos.canonical import ArtifactIntegrityError, FrozenModel


class AllFalseAuthority(FrozenModel):
    """Authority block: every declared boolean flag forced ``false`` (§6; §14.1 line 348).

    The time-local realization of the design #4 §4.6 ``_all_authority_false``
    pattern (``tos.evidence`` is not importable here — time design §0.3): a Time
    Health Snapshot "SHALL NOT issue live authority or classify economic risk", so
    any ``True`` authority flag makes the artifact unconstructable. The full "no
    authority path" proof is EV-L2/L3; this is the flag invariant only.
    """

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
    """Two-sided reference-frame uncertainty interval (time design §2.6, gap 3).

    ``lo``/``hi`` are **reference / trustworthy-time frame** values — ADR §10
    priority-4 "corroborated source event time within its uncertainty" (line
    251-256), anchored to reference time so a **cross-continuity comparison is
    meaningful**. This is a *different coordinate system* from the per-continuity
    ``local_monotonic_value`` (ADR §10 priority-3; §4.1 "SHALL NOT be compared
    across process or host identities").

    A single scalar ``uncertainty_ms`` cannot express an asymmetric or one-sided-
    unknown interval, so safety decisions use this interval, never a scalar (time
    design §2.6). Either endpoint ``None`` means that side is **unbounded =
    UNKNOWN** (fail-closed): UNKNOWN is not zero (§9 line 241/243; §18 line 443).

    The monotonic coordinate MUST NEVER be placed on ``lo``/``hi`` — doing so
    would feed the un-guarded cross-continuity interval branch of
    ``tos.ordering.compare_order`` and silently violate the §8 non-subtraction
    rule (time design MAJOR-1). [TIME-AC-004, TIME-AC-007; SAFE-031, SAFE-035]
    """

    lo: int | None = None
    hi: int | None = None


class TimeContinuityIdentity(FrozenModel):
    """Time continuity identity binding (ADR §5 line 111-126).

    All fields are opaque injected values (no clock read). A process restart /
    host reboot / monotonic reset / discontinuity / unbounded suspension /
    identity change invalidates every local anchor that cannot be proven
    continuous across it (§5 line 124; ``tos.time.predicates.anchor_valid``).
    ``monotonic_anchor_value`` is a **required injected field** — the model has no
    path that reconstructs it from a wall clock (§5 line 126). [TIME-AC-001,
    TIME-AC-004, TIME-AC-005; SAFE-035, SAFE-048]
    """

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
    """A single per-continuity monotonic reading (time design §3, §4.1).

    ``monotonic_continuity_id`` + ``local_monotonic_value`` are opaque injected
    coordinates. Elapsed is only defined **within** one continuity; a cross-
    continuity subtraction is never performed (time design §3(1);
    ``elapsed_within_continuity``). [TIME-AC-004; SAFE-031, SAFE-035]
    """

    monotonic_continuity_id: str | None = None
    local_monotonic_value: int | None = None


class ReferenceSource(FrozenModel):
    """A corroborating reference source (ADR §8 line 199-200; §4.3; §7; §15).

    Sources sharing a ``common_mode_group`` (one clock / network / hypervisor /
    sync-daemon) are **not counted independently** — they collapse to one
    contribution (§7 line 184; ``independent_reference_count``). ``quality`` is an
    opaque injected grade, not a closed set: broker/deployment grades are Phase-0
    profile extensions (time design §2.5 A); an unregistered value is fail-closed.
    All per-source bounds are injected (``None`` = unbounded = UNKNOWN).
    [TIME-AC-003; SAFE-031, SAFE-035]
    """

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
    """Injected magnitude-bound bundle for a snapshot (ADR §8 line 200).

    Each is ``int | None`` (injected); ``None`` = unestablished = UNKNOWN,
    consumed fail-closed by the freshness/ordering predicates (time design §2.6,
    §8). No threshold is hard-coded here.
    """

    offset_bound_ms: int | None = None
    drift_bound_ppm: int | None = None
    uncertainty_bound_ms: int | None = None
    source_disagreement_bound_ms: int | None = None


class SuspensionStatus(FrozenModel):
    """Recorded process-suspension status (ADR §5 line 124; §11.2 line 277).

    ``suspension_ms`` is the observed suspension magnitude (injected); ``None``
    means unknown/unbounded, which the anchor-validity predicate treats as invalid
    (fail-closed). The ``MAX_process_suspension_ms`` bound is injected at the
    predicate call, not stored here.
    """

    suspended: bool = False
    suspension_ms: int | None = None


class DiscontinuityStatus(FrozenModel):
    """Recorded monotonic-discontinuity status (ADR §5 line 124; §13 line 333-335)."""

    discontinuity_detected: bool = False
    monotonic_reset: bool = False


class SessionContext(FrozenModel):
    """Trading-session context (ADR §4.7 line 103-105; §12 line 319).

    **Broker-agnostic**: tz/calendar identities/versions, phase, an injected
    ``is_open`` determination from the calendar, and the session ``boundary_value``
    (a reference-frame coordinate). No market hours are hard-coded (time design
    §4.7). The ``session_open_positively`` predicate denies unless the session is
    positively open with clean epistemics and the boundary is outside the
    uncertainty interval. [TIME-AC-008; SAFE-050]
    """

    tz_id: str | None = None
    tz_db_version: str | None = None
    trading_calendar_version: str | None = None
    phase: str | None = None
    is_open: bool = False
    tz_version_conflict: bool = False
    boundary_value: int | None = None


class ConsumerReceiptAnchor(FrozenModel):
    """A consumer's own receipt anchor for a cross-continuity snapshot (ADR §8 line 212-220).

    Records the consumer's **own** monotonic continuity + value at receipt so age
    is accrued in the consumer's own continuity (subtraction allowed only there),
    never by subtracting an issuer monotonic value from a consumer clock (§8 line
    220). [TIME-AC-010; SAFE-031, SAFE-035]
    """

    consumer_monotonic_continuity_id: str | None = None
    consumer_local_monotonic_value_at_receipt: int | None = None
