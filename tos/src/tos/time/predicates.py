"""Pure trustworthy-time predicates (time design §3, §4, §6; EV-L1 substrate)."""

from __future__ import annotations

from collections.abc import Sequence

from tos.time.domains import FreshnessVerdict, HealthState
from tos.time.elements import (
    ConsumerReceiptAnchor,
    MonotonicReading,
    ReferenceSource,
    SessionContext,
    TimeContinuityIdentity,
    UncertaintyInterval,
)
from tos.time.snapshot import TimeHealthSnapshot


def elapsed_within_continuity(a: MonotonicReading, b: MonotonicReading) -> int | None:
    """Elapsed ``b - a`` only within one monotonic continuity, else ``None`` (§3(1))."""
    if a.monotonic_continuity_id is None or b.monotonic_continuity_id is None:
        return None
    if a.monotonic_continuity_id != b.monotonic_continuity_id:
        return None
    if a.local_monotonic_value is None or b.local_monotonic_value is None:
        return None
    return b.local_monotonic_value - a.local_monotonic_value


def anchor_valid(
    continuity_now: TimeContinuityIdentity,
    anchor: TimeContinuityIdentity,
    *,
    suspension_ms: int | None,
    max_suspension_ms: int | None,
) -> bool:
    """Whether an anchor is still valid across ``now`` (§3(2); ADR §5 line 124)."""
    for field in ("host_or_runtime_id", "boot_id", "process_id", "monotonic_anchor_id"):
        now_v = getattr(continuity_now, field)
        anc_v = getattr(anchor, field)
        if now_v is None or anc_v is None or now_v != anc_v:
            return False
    now_value = continuity_now.monotonic_anchor_value
    anchor_value = anchor.monotonic_anchor_value
    if now_value is None or anchor_value is None:
        return False
    if now_value < anchor_value:
        return False
    if suspension_ms is None or max_suspension_ms is None:
        return False
    return suspension_ms <= max_suspension_ms


def conservative_usable_lifetime(
    *,
    issued_lifetime: int | None,
    elapsed_monotonic: int | None,
    source_transport_uncertainty: int | None,
    max_drift_error: int | None,
    suspension_uncertainty: int | None,
    safety_margin: int | None,
) -> int | None:
    """Conservative remaining usable lifetime (§3(3); ADR §11.2 line 283-294)."""
    terms = (
        issued_lifetime,
        elapsed_monotonic,
        source_transport_uncertainty,
        max_drift_error,
        suspension_uncertainty,
        safety_margin,
    )
    if any(term is None for term in terms):
        return None
    if any(term < 0 for term in terms):  # type: ignore[operator]
        return None
    result = (
        issued_lifetime  # type: ignore[operator]
        - elapsed_monotonic
        - source_transport_uncertainty
        - max_drift_error
        - suspension_uncertainty
        - safety_margin
    )
    if result <= 0:
        return None
    return result


def effective_snapshot_age_bound(
    snapshot: TimeHealthSnapshot,
    consumer_receipt_anchor: ConsumerReceiptAnchor,
    *,
    issuer_signed_age: int | None,
    issuer_age_uncertainty: int | None,
    transport_bound: int | None,
    queue_bound: int | None,
    conversion_bound: int | None,
    consumer_elapsed_since_receipt: int | None,
    consumer_anchor_valid: bool,
) -> int | None:
    """Effective cross-continuity snapshot age bound via the §8 5-step path (§3(4))."""
    del snapshot
    if not consumer_anchor_valid:
        return None
    if consumer_receipt_anchor.consumer_monotonic_continuity_id is None:
        return None
    additive_terms = (
        issuer_signed_age,
        issuer_age_uncertainty,
        transport_bound,
        queue_bound,
        conversion_bound,
        consumer_elapsed_since_receipt,
    )
    if any(term is None for term in additive_terms):
        return None
    if any(term < 0 for term in additive_terms):  # type: ignore[operator]
        return None
    return sum(additive_terms)  # type: ignore[arg-type]


def snapshot_age_admissible(
    age_bound: int | None, maximum_consumer_age_ms: int | None
) -> bool:
    """Whether a snapshot age bound is admissible (§3(4)(v); ADR §8 line 210)."""
    if age_bound is None or maximum_consumer_age_ms is None:
        return False
    return age_bound <= maximum_consumer_age_ms


def effective_snapshot_age_bound_from_continuity(
    snapshot: TimeHealthSnapshot,
    consumer_receipt_anchor: ConsumerReceiptAnchor,
    *,
    consumer_continuity_now: TimeContinuityIdentity,
    consumer_anchor: TimeContinuityIdentity,
    suspension_ms: int | None,
    max_suspension_ms: int | None,
    issuer_signed_age: int | None,
    issuer_age_uncertainty: int | None,
    transport_bound: int | None,
    queue_bound: int | None,
    conversion_bound: int | None,
    consumer_elapsed_since_receipt: int | None,
) -> int | None:
    """Compose ``anchor_valid`` with ``effective_snapshot_age_bound`` (MEDIUM-2, v1.2)."""
    valid = anchor_valid(
        consumer_continuity_now,
        consumer_anchor,
        suspension_ms=suspension_ms,
        max_suspension_ms=max_suspension_ms,
    )
    return effective_snapshot_age_bound(
        snapshot,
        consumer_receipt_anchor,
        issuer_signed_age=issuer_signed_age,
        issuer_age_uncertainty=issuer_age_uncertainty,
        transport_bound=transport_bound,
        queue_bound=queue_bound,
        conversion_bound=conversion_bound,
        consumer_elapsed_since_receipt=consumer_elapsed_since_receipt,
        consumer_anchor_valid=valid,
    )


def freshness_verdict(
    *,
    source_age: int | None,
    delay_bounds: Sequence[int | None],
    max_age_bound: int | None,
    future_tolerance: int | None,
) -> FreshnessVerdict:
    """Conservative freshness verdict (§4; ADR §9 line 241-243; §18 line 443)."""
    if source_age is None:
        return FreshnessVerdict.UNKNOWN
    if future_tolerance is not None and future_tolerance < 0:
        return FreshnessVerdict.UNKNOWN
    if any(bound is not None and bound < 0 for bound in delay_bounds):
        return FreshnessVerdict.UNKNOWN
    if max_age_bound is not None and max_age_bound < 0:
        return FreshnessVerdict.UNKNOWN
    if source_age < 0:
        if future_tolerance is None:
            return FreshnessVerdict.CONFLICTED
        if -source_age > future_tolerance:
            return FreshnessVerdict.CONFLICTED
    if any(bound is None for bound in delay_bounds):
        return FreshnessVerdict.UNKNOWN
    if max_age_bound is None:
        return FreshnessVerdict.UNKNOWN
    if source_age < 0:
        return FreshnessVerdict.FRESH
    total_age = source_age + sum(bound for bound in delay_bounds)  # type: ignore[misc]
    if total_age > max_age_bound:
        return FreshnessVerdict.STALE
    return FreshnessVerdict.FRESH


_ALLOWED_TRANSITIONS: frozenset[tuple[HealthState, HealthState]] = frozenset(
    {
        (HealthState.UNINITIALIZED, HealthState.SYNCHRONIZING),
        (HealthState.SYNCHRONIZING, HealthState.TRUSTED),
        (HealthState.TRUSTED, HealthState.DEGRADED_HOLDOVER),
        (HealthState.TRUSTED, HealthState.UNTRUSTED),
        (HealthState.DEGRADED_HOLDOVER, HealthState.UNTRUSTED),
        (HealthState.DEGRADED_HOLDOVER, HealthState.SYNCHRONIZING),
        (HealthState.UNTRUSTED, HealthState.SYNCHRONIZING),
    }
)


def health_transition_allowed(from_state: HealthState, to_state: HealthState) -> bool:
    """Whether a health-state transition is one of the 7 permitted (§6 line 134-145)."""
    return (from_state, to_state) in _ALLOWED_TRANSITIONS


def transition_to_trusted_requires_new_generation(
    from_generation: int | None, to_generation: int | None
) -> bool:
    """Whether a return to TRUSTED carries a strictly-new generation (§6.4; §16 line 401)."""
    if from_generation is None or to_generation is None:
        return False
    return to_generation > from_generation


def recovery_generation_revives_nothing(
    *, invalidated_under_generation: int | None, new_generation: int | None
) -> bool:
    """Whether a new generation revives an earlier invalidation — never (§6.4; §16 line 406-409)."""
    del invalidated_under_generation, new_generation
    return True


def state_permits_new_normal_risk(state: HealthState) -> bool:
    """Whether a health state permits **new normal risk** — TRUSTED only (§6.1-6.3)."""
    return state is HealthState.TRUSTED


def snapshot_grants_no_authority(snapshot: TimeHealthSnapshot) -> bool:
    """Whether the snapshot grants no authority (§6; §14.1 line 348)."""
    authority = snapshot.authority_effect
    return not any(
        getattr(authority, name) is True for name in type(authority).model_fields
    )


def session_open_positively(
    session_ctx: SessionContext, uncertainty_interval: UncertaintyInterval
) -> bool:
    """Whether a trading session is **positively** open (§12 line 319)."""
    if not session_ctx.is_open:
        return False
    if session_ctx.phase is None:
        return False
    if session_ctx.trading_calendar_version is None:
        return False
    if session_ctx.tz_version_conflict:
        return False
    if uncertainty_interval.lo is None or uncertainty_interval.hi is None:
        return False
    boundary = session_ctx.boundary_value
    return not (
        boundary is not None
        and uncertainty_interval.lo <= boundary <= uncertainty_interval.hi
    )


def snapshot_consumer_binding_ok(
    snapshot: TimeHealthSnapshot,
    *,
    expected_snapshot_id: str,
    expected_canonical_digest: str,
    expected_generation: int | None = None,
    expected_verification_profile_version: str | None = None,
    expected_safety_profile_version: str | None = None,
) -> bool:
    """Whether a snapshot matches the consumer's ``(id, generation, digest)`` binding (§7; §8 line 208)."""
    if snapshot.snapshot_id != expected_snapshot_id:
        return False
    if snapshot.canonical_digest != expected_canonical_digest:
        return False
    if expected_generation is not None and snapshot.generation != expected_generation:
        return False
    if (
        expected_verification_profile_version is not None
        and snapshot.verification_profile_version
        != expected_verification_profile_version
    ):
        return False
    return not (
        expected_safety_profile_version is not None
        and snapshot.safety_profile_version != expected_safety_profile_version
    )


def independent_reference_count(sources: Sequence[ReferenceSource]) -> int:
    """Count independent reference contributions, collapsing common-mode (§7 line 184)."""
    seen_groups: set[str] = set()
    count = 0
    for source in sources:
        group = source.common_mode_group
        if group is None:
            count += 1
        elif group not in seen_groups:
            seen_groups.add(group)
            count += 1
    return count


def source_disagreement_within_bound(
    disagreement_ms: int | None, tolerance_ms: int | None
) -> bool:
    """Whether inter-source disagreement is within the injected tolerance (§7 line 184)."""
    if disagreement_ms is None or tolerance_ms is None:
        return False
    return disagreement_ms <= tolerance_ms
