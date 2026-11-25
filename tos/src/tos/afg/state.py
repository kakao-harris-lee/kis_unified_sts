"""afg temporal / lifecycle predicates — permit, refill, fence, currentness, non-revival."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from tos.afg.records import (
    ActionFlowDecision,
    ActionFlowPermit,
    CurrentnessTrigger,
    PermitConsumptionState,
)
from tos.afg.vocabulary import (
    MATERIAL_CHANGE_KINDS,
    ActionFlowResult,
    MaterialChangeKind,
)
from tos.ordering import Ordering, OrderingEvent, compare_order

__all__ = [
    "permit_single_use",
    "permit_release_admissible",
    "queue_does_not_extend_validity",
    "permit_not_merged",
    "backlog_is_not_authority",
    "refill_conservative",
    "generation_fenced",
    "action_flow_generation_monotone",
    "is_material",
    "currentness_invalidation",
    "non_revival_holds",
    "economic_effect_persists",
    "restart_counter_assumption_admissible",
    "decision_is_forward_only",
]

_FORWARD_ONLY_FORBIDDEN_FIELDS: frozenset[str] = frozenset(
    {
        "bound_reservation_revision",
        "bound_reservation_digest",
        "bound_generation",
        "reservation_id",
        "permit_id",
        "claim_nonce",
    }
)


def permit_single_use(
    permit: ActionFlowPermit | None,
    consumption: PermitConsumptionState | None = None,
) -> bool:
    """Whether the permit is an exact, single-use, still-consumable permit (§13 line 342)."""
    if permit is None:
        return False
    if permit.missing_required_fields():
        return False
    if permit.single_use is not True:
        return False
    if consumption is None:
        return False
    return (
        consumption.claimed is False
        and consumption.ambiguous is False
        and consumption.lost is False
        and consumption.conflicting is False
    )


def permit_release_admissible(
    permit: ActionFlowPermit | None,
    consumption: PermitConsumptionState | None,
) -> bool:
    """Whether an unused permit may be released (§13 line 342 — the "release" verb)."""
    if permit is None or consumption is None:
        return False
    if consumption.never_claimed_and_unreachable_proven is not True:
        return False
    return (
        consumption.claimed is False
        and consumption.ambiguous is False
        and consumption.lost is False
        and consumption.conflicting is False
    )


def queue_does_not_extend_validity(
    queued_item_identity: str | None,
    prereq_generation: int | None,
    current_generation: int | None,
    *,
    silently_refreshed_in_queue: bool | None,
) -> bool:
    """Whether queueing left the item's prerequisites unextended (§12 line 311)."""
    if queued_item_identity is None or queued_item_identity == "TBD":
        return False
    if silently_refreshed_in_queue is not False:
        return False
    return generation_fenced(prereq_generation, current_generation)


def permit_not_merged(permits: Sequence[ActionFlowPermit]) -> bool:
    """Whether exactly one exact permit governs the action (§12 line 313; AFG-INV-003)."""
    if len(permits) != 1:
        return False
    permit = permits[0]
    if permit.missing_required_fields():
        return False
    return permit.single_use is True


def backlog_is_not_authority(
    scheduler_reorder: bool | None,
    independent_prereqs_valid: bool | None,
    *,
    command_regenerated: bool | None = None,
    backlog_treated_as_authority: bool | None = None,
) -> bool:
    """Whether the scheduler stayed inside its (non-authoritative) role (§12 line 313)."""
    if independent_prereqs_valid is not True:
        return False
    if command_regenerated is not False:
        return False
    if backlog_treated_as_authority is not False:
        return False
    return isinstance(scheduler_reorder, bool)


def refill_conservative(
    time_valid: bool | None,
    monotonic_continuity_id: str | None,
    age: Decimal | None,
    *,
    reference_continuity_id: str | None,
    rcl_committed_history_present: bool | None,
    wall_clock_or_recovery_or_restart_basis: bool | None,
    broker_timestamp_or_new_source_basis: bool | None,
    continuity_established: bool | None,
    snapshot_age_admissible: bool | None,
) -> ActionFlowResult:
    """Whether an action-flow budget may be replenished at all (§18; AFG-INV-004/007)."""
    if wall_clock_or_recovery_or_restart_basis is not False:
        return ActionFlowResult.DENY
    if broker_timestamp_or_new_source_basis is not False:
        return ActionFlowResult.DENY

    if time_valid is not True:
        return ActionFlowResult.UNKNOWN
    if rcl_committed_history_present is not True:
        return ActionFlowResult.UNKNOWN
    if continuity_established is not True:
        return ActionFlowResult.UNKNOWN
    if monotonic_continuity_id is None or reference_continuity_id is None:
        return ActionFlowResult.UNKNOWN
    if monotonic_continuity_id != reference_continuity_id:
        return ActionFlowResult.UNKNOWN
    if snapshot_age_admissible is not True:
        return ActionFlowResult.UNKNOWN
    if age is None or not age.is_finite():
        return ActionFlowResult.UNKNOWN
    if age < 0:
        return ActionFlowResult.UNKNOWN
    return ActionFlowResult.GRANT


def generation_fenced(
    artifact_generation: int | None, current_generation: int | None
) -> bool:
    """Whether an artifact is on the **current** side of the generation fence (AFG-INV-013)."""
    if artifact_generation is None or current_generation is None:
        return False
    return artifact_generation == current_generation


def action_flow_generation_monotone(
    earlier: OrderingEvent, later: OrderingEvent
) -> bool:
    """Whether ``earlier`` strictly precedes ``later`` in append-only order (§3.2 / §5.2)."""
    return compare_order(earlier, later) is Ordering.BEFORE


def is_material(
    change: MaterialChangeKind | str | None, materiality_known: bool | None
) -> bool:
    """Whether an observed change is **material** (§19 line 413; §5.10 line 149 — Gap-7)."""
    if materiality_known is not True:
        return True
    if change is None:
        return True
    return change in MATERIAL_CHANGE_KINDS


def currentness_invalidation(
    triggers: Sequence[CurrentnessTrigger],
    decision: ActionFlowDecision | None,
    permit: ActionFlowPermit | None,
    *,
    currentness_positively_established: bool | None,
    cache_ttl_heartbeat_health_or_prior_success_only: bool | None,
    egress_recalculated_favorably_or_widened: bool | None = None,
    egress_invented_cause_or_changed_action_class: bool | None = None,
) -> bool:
    """Whether an affected unclaimed decision / permit MUST be invalidated (§17 / §19)."""
    if egress_recalculated_favorably_or_widened is not False:
        return True
    if egress_invented_cause_or_changed_action_class is not False:
        return True
    if decision is None and permit is None:
        return True
    for trigger in triggers:
        if is_material(trigger.kind, trigger.materiality_known):
            return True
    if cache_ttl_heartbeat_health_or_prior_success_only is not False:
        return True
    return currentness_positively_established is not True


def non_revival_holds(
    *,
    restart: bool | None = None,
    rollback_or_restore: bool | None = None,
    failover_or_reconnect: bool | None = None,
    backoff_expiry_or_queue_drain: bool | None = None,
    counter_refill_or_throttle_recovery: bool | None = None,
    matching_replay_or_improved_health: bool | None = None,
    recovery_generation_revives_nothing: bool | None = None,
) -> bool:
    """Whether nothing revives a prior decision / permit / authority (§22; AFG-INV-014)."""
    del restart, rollback_or_restore, failover_or_reconnect
    del backoff_expiry_or_queue_drain, counter_refill_or_throttle_recovery
    del matching_replay_or_improved_health, recovery_generation_revives_nothing
    return True


def economic_effect_persists(
    *,
    final_quantity_proof_present: bool | None,
    permit_expired: bool | None = None,
    decision_expired: bool | None = None,
    policy_or_retry_window_expired: bool | None = None,
    queue_item_expired: bool | None = None,
    ack_missing: bool | None = None,
    cancel_ack_observed: bool | None = None,
) -> bool:
    """Whether a possible broker / economic effect still persists (§19 line 419; INV-012)."""
    del permit_expired, decision_expired, policy_or_retry_window_expired
    del queue_item_expired, ack_missing, cancel_ack_observed
    return final_quantity_proof_present is not True


def restart_counter_assumption_admissible(
    *,
    assumed_zero_counter: bool | None,
    assumed_empty_queue: bool | None,
    assumed_unused_permit: bool | None,
) -> bool:
    """Whether the restart made no forbidden zero-state assumption (§22 line 463)."""
    return (
        assumed_zero_counter is False
        and assumed_empty_queue is False
        and assumed_unused_permit is False
    )


def decision_is_forward_only(decision: ActionFlowDecision) -> bool:
    """Whether the decision binds no future commitment coordinate (§5.3; ADR §29 q2)."""
    return _FORWARD_ONLY_FORBIDDEN_FIELDS.isdisjoint(type(decision).model_fields)
