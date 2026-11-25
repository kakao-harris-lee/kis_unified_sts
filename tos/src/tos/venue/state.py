"""venue session-phase decision + Constraint Generation order + produced seam scalars (design #19 §5.1/§3.4)."""

from __future__ import annotations

from tos.ordering import Ordering, OrderingEvent, compare_order
from tos.venue.records import (
    OrderAdmissibilityDecision,
    VenueConstraintPolicy,
    VenueConstraintSnapshot,
)
from tos.venue.vocabulary import ActionClass, OrderAdmissibilityResult

__all__ = [
    "session_phase_admits",
    "constraint_generation_monotone",
    "venue_admissibility_decision_digest_of",
    "venue_snapshot_digest_of",
    "venue_constraint_policy_ref_coordinates",
    "venue_constraint_snapshot_ref_coordinates",
    "order_admissibility_decision_ref_coordinates",
]


def session_phase_admits(
    observed_phase: str | None,
    action: ActionClass,
    snapshot: VenueConstraintSnapshot | None,
    policy: VenueConstraintPolicy | None,
) -> OrderAdmissibilityResult:
    """Whether the observed session phase admits the exact action (§10; VTG-INV-002; VTG-AC-001)."""
    if snapshot is None or policy is None:
        return OrderAdmissibilityResult.UNKNOWN
    if observed_phase is None:
        return OrderAdmissibilityResult.UNKNOWN
    admitting = policy.admitting_phases_for(action)
    if admitting is None:
        return OrderAdmissibilityResult.INADMISSIBLE
    if not admitting:
        return OrderAdmissibilityResult.INADMISSIBLE
    if observed_phase not in admitting:
        return OrderAdmissibilityResult.INADMISSIBLE
    return OrderAdmissibilityResult.ADMISSIBLE


def constraint_generation_monotone(
    earlier: OrderingEvent, later: OrderingEvent
) -> bool:
    """Whether ``earlier`` strictly precedes ``later`` in append-only order (§3.2 / §5.3)."""
    return compare_order(earlier, later) is Ordering.BEFORE


def venue_admissibility_decision_digest_of(
    decision: OrderAdmissibilityDecision | None,
) -> str | None:
    """Produce the Order Admissibility Decision digest for the ioc / iap seams (§3.4)."""
    if decision is None:
        return None
    return decision.canonical_digest


def venue_snapshot_digest_of(snapshot: VenueConstraintSnapshot | None) -> str | None:
    """Produce the Venue Constraint Snapshot digest for the iap seam (§3.4)."""
    if snapshot is None:
        return None
    return snapshot.canonical_digest


def venue_constraint_policy_ref_coordinates(
    policy: VenueConstraintPolicy | None,
) -> tuple[str | None, int | None, str | None]:
    """Produce the capsule ``VenueConstraintPolicyRef`` coordinates (§3.4)."""
    if policy is None:
        return (None, None, None)
    return (policy.policy_id, policy.policy_generation, policy.canonical_digest)


def venue_constraint_snapshot_ref_coordinates(
    snapshot: VenueConstraintSnapshot | None,
) -> tuple[str | None, int | None, str | None]:
    """Produce the capsule ``VenueConstraintSnapshotRef`` coordinates (§3.4)."""
    if snapshot is None:
        return (None, None, None)
    return (
        snapshot.snapshot_id,
        snapshot.constraint_generation,
        snapshot.canonical_digest,
    )


def order_admissibility_decision_ref_coordinates(
    decision: OrderAdmissibilityDecision | None,
) -> tuple[str | None, str | None]:
    """Produce the capsule ``OrderAdmissibilityDecisionRef`` coordinates (§3.4)."""
    if decision is None:
        return (None, None)
    return (decision.decision_id, decision.canonical_digest)
