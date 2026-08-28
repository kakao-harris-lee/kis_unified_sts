"""afg temporal / lifecycle predicates — permit, refill, fence, currentness, non-revival.

The decision rules that concern **state over time** (design #16 §5.3 lifecycle / §5.4 /
§6.5 / §6.8):

* **permit lifecycle (§5.3 / §13 line 342)** — ``permit_single_use`` /
  ``permit_release_admissible``, plus the §12 trio ``queue_does_not_extend_validity`` /
  ``permit_not_merged`` / ``backlog_is_not_authority`` (M8);
* **time / refill / counter integrity (§5.4 / §18)** — ``refill_conservative`` and the
  separate generation fence ``generation_fenced`` (M6: AFG-INV-013 "Stale Generations Are
  Fenced" line 205 is a **different axis** from the AFG-INV-004 "replenishes" line 169 +
  AFG-INV-007 line 181 refill rule);
* **currentness / invalidation (§6.5 / §17 / §19)** — ``is_material`` (Gap-7 "Unknown
  materiality is material") and ``currentness_invalidation``;
* **non-revival + economic continuity (§6.8 / §22)** — ``non_revival_holds`` /
  ``economic_effect_persists`` / ``restart_counter_assumption_admissible``.

The append-only Action Flow Generation / decision / permit / snapshot order is **not**
re-authored: it REUSES ``tos.ordering`` (``Ordering`` / ``OrderingEvent`` /
``compare_order``, which depends only on ``tos.canonical``) — design #16 §3.2. **A wall
clock never orders and never manufactures headroom** (§17 line 391 "last-known generation
... is not proof"; §18 line 405 "Wall-clock movement ... cannot manufacture headroom"):
afg reads **no** clock at all; time validity, monotonic continuity, and snapshot age are
injected flags produced by ``tos.time``
(``elapsed_within_continuity`` ``predicates.py:73`` / ``snapshot_age_admissible`` ``:287``
/ ``recovery_generation_revives_nothing`` ``:499``; ``MonotonicReading`` "continuity
subtraction is never performed" ``elements.py:112``).

Pure module: ``pydantic`` + stdlib + ``tos.ordering`` + ``tos.canonical`` (via the
records) only; no ``shared.*``, no other sibling ``tos.*`` (design #16 §0.3).
"""

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
    # §5.3 permit lifecycle
    "permit_single_use",
    "permit_release_admissible",
    # §12 queue / merge / backlog (M8)
    "queue_does_not_extend_validity",
    "permit_not_merged",
    "backlog_is_not_authority",
    # §5.4 refill + generation fence
    "refill_conservative",
    "generation_fenced",
    "action_flow_generation_monotone",
    # §6.5 currentness / invalidation
    "is_material",
    "currentness_invalidation",
    # §6.8 non-revival + economic continuity
    "non_revival_holds",
    "economic_effect_persists",
    "restart_counter_assumption_admissible",
    # forward-only structural contract
    "decision_is_forward_only",
]

#: Commitment coordinates a **forward-only** decision must NOT carry (design #16 §2.3 /
#: §5.3): rcl charges ``bound_reservation_*`` post-commit (``authority.py:56-58``), so
#: their presence on a decision would make the pipeline cyclic — exactly what ADR §29 q2
#: requires the atomic economic + flow commit protocol to avoid. A structural, not
#: numeric, contract.
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


# ===========================================================================
# §5.3 — permit single-use lifecycle (§13 line 342; AFG-EV-007 substrate)
# ===========================================================================


def permit_single_use(
    permit: ActionFlowPermit | None,
    consumption: PermitConsumptionState | None = None,
) -> bool:
    """Whether the permit is an exact, single-use, still-consumable permit (§13 line 342).

    §13 line 342: a permit is exact and single-use and ends up **consumed or
    quarantined**. AFG-INV-003 line 165: one decision / permit binds one exact action
    identity, command, cause, lineage, scope, generation, and resource vector and "cannot
    be patched, unioned, widened, transplanted, or replayed". ``True`` **only** when:

    * the permit exists and is structurally complete (its ``_REQUIRED_COVERED`` identity
      fields — generation, command identity, claim nonce — are all concrete);
    * ``single_use is True`` (the rcl ``TransmissionCapability`` ``records.py:295-296``
      pattern);
    * the consumption state is **known** (a ``None`` state is UNKNOWN => not consumable)
      and reports ``claimed`` / ``ambiguous`` / ``lost`` / ``conflicting`` each positively
      ``False``.

    A replayed / re-used permit therefore fails on ``claimed``, and an ambiguous send
    (§17 line 395) fails on ``ambiguous`` — in both cases the permit stays consumed or
    quarantined, never re-consumable. The **atomic consume / quarantine transition** is rcl
    / egress runtime (EV-L2/L3, design #16 §0.4d); this predicate decides admissibility
    only and issues, claims, and transmits nothing (§4.6).

    Args:
        permit: The action flow permit (``None`` => ``False``).
        consumption: The observed consumption state (``None`` => ``False``, UNKNOWN).

    Returns:
        ``True`` iff the permit is exact, single-use, and still consumable.
    """
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
    """Whether an unused permit may be released (§13 line 342 — the "release" verb).

    §13 line 342: an unused permit may be released **only** on proof that it was "never
    claimed and cannot reach any broker path"; a claimed or ambiguous permit stays consumed
    or quarantined. ``True`` **only** when the permit and consumption state both exist,
    ``never_claimed_and_unreachable_proven is True``, and ``claimed`` / ``ambiguous`` /
    ``lost`` / ``conflicting`` are each positively ``False``. Any ``None`` fails closed.

    Note the §13 line 342 asymmetry that this predicate does **not** breach: releasing
    action-flow capacity never releases **economic** capacity, which has its own Final
    Quantity Proof rules (:func:`economic_effect_persists`).

    Args:
        permit: The action flow permit (``None`` => ``False``).
        consumption: The observed consumption state (``None`` => ``False``).

    Returns:
        ``True`` iff the unused permit may be released.
    """
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


# ===========================================================================
# §12 — queue does not extend validity / no merge / backlog is not authority (M8)
# ===========================================================================


def queue_does_not_extend_validity(
    queued_item_identity: str | None,
    prereq_generation: int | None,
    current_generation: int | None,
    *,
    silently_refreshed_in_queue: bool | None,
) -> bool:
    """Whether queueing left the item's prerequisites unextended (§12 line 311).

    §12 line 311 verbatim: "Queueing does not extend permit, authority, context,
    constraint, decision, capability, or policy validity. Work whose prerequisites expire
    in queue is denied and cannot be silently refreshed." ``True`` **only** when the
    queued item is identified (an unidentified / empty queue item is restrictive — design
    #16 §4.7), no silent in-queue refresh occurred (positively ``False``), and the
    prerequisite generation is still current (:func:`generation_fenced`).

    Args:
        queued_item_identity: The queued item's identity (``None`` => ``False``).
        prereq_generation: The generation the prerequisites were established under.
        current_generation: The current Action Flow Generation.
        silently_refreshed_in_queue: Must be positively ``False`` (§12 line 311).

    Returns:
        ``True`` iff queueing extended nothing and the prerequisites are still current.
    """
    if queued_item_identity is None or queued_item_identity == "TBD":
        return False
    if silently_refreshed_in_queue is not False:
        return False
    return generation_fenced(prereq_generation, current_generation)


def permit_not_merged(permits: Sequence[ActionFlowPermit]) -> bool:
    """Whether exactly one exact permit governs the action (§12 line 313; AFG-INV-003).

    §12 line 313: a scheduler "cannot merge permits". AFG-INV-003 line 165: a permit binds
    **one exact** action and cannot be patched, unioned, widened, transplanted, or
    replayed. ``True`` **only** when there is exactly one permit and it is structurally
    complete and single-use. An **empty** sequence is restrictive (no permit is not a
    permit — design #16 §4.7), and two or more permits are a merge attempt (the guard
    fires).

    Args:
        permits: The permits presented for one action (empty / >1 => ``False``).

    Returns:
        ``True`` iff exactly one exact, single-use permit governs the action.
    """
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
    """Whether the scheduler stayed inside its (non-authoritative) role (§12 line 313).

    §12 line 313 verbatim: a scheduler "cannot ... regenerate a command, or turn backlog
    into current authority". A scheduler may reorder **only** actions whose independent
    prerequisites are still valid. ``True`` **only** when:

    * ``independent_prereqs_valid is True`` (an unknown ``None`` fails closed — the
      scheduler may not assume validity);
    * ``command_regenerated`` is positively ``False``;
    * ``backlog_treated_as_authority`` is positively ``False``;
    * ``scheduler_reorder`` is a **known** ``bool`` — an unknown reorder status is
      UNKNOWN and fails closed.

    Args:
        scheduler_reorder: Whether a reorder occurred (``None`` => fail-closed).
        independent_prereqs_valid: Whether the independent prerequisites are still valid.
        command_regenerated: Must be positively ``False`` (§12 line 313).
        backlog_treated_as_authority: Must be positively ``False`` (§12 line 313).

    Returns:
        ``True`` iff the backlog created no authority and regenerated no command.
    """
    if independent_prereqs_valid is not True:
        return False
    if command_regenerated is not False:
        return False
    if backlog_treated_as_authority is not False:
        return False
    return isinstance(scheduler_reorder, bool)


# ===========================================================================
# §5.4 — refill integrity + generation fence (§18; AFG-EV-008 substrate)
# ===========================================================================


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
    """Whether an action-flow budget may be replenished at all (§18; AFG-INV-004/007).

    §18 line 404: **only** approved trustworthy time (ADR-002-008) plus committed RCL
    history may replenish. §18 line 405: wall-clock movement, clock recovery, restart,
    a broker timestamp, or a newly-healthy source "cannot manufacture headroom", and a
    negative age, future issue time, uncertainty, discontinuity, or unknown continuity
    clamps **toward restriction, never refill**. §18 line 403: "Monotonic values from
    different hosts or processes SHALL NOT be directly subtracted" — the time model
    performs the elapsed computation only *within* one continuity
    (``elapsed_within_continuity`` ``time/predicates.py:73``; ``MonotonicReading``
    "continuity subtraction is never performed" ``elements.py:112``), and afg only
    compares the continuity identifiers.

    Returns ``GRANT`` (a refill is permissible) **only** when every premise is positively
    proven. A basis that would manufacture headroom returns ``DENY`` (a positively refused
    refill); everything unproven returns ``UNKNOWN`` (restrictive, AFG-INV-007 line 181).
    afg reads **no** clock: ``time_valid`` / ``continuity_established`` /
    ``snapshot_age_admissible`` are injected ``tos.time`` results
    (``snapshot_age_admissible`` ``predicates.py:287``).

    ``age`` is an injected magnitude compared only against zero (a negative age is a
    restriction clamp); a NaN / infinity is already unconstructable as a
    :data:`~tos.canonical.CanonicalDecimal` model field, and a non-finite raw value is
    rejected here as well. No numeric bound is hardcoded — the age ceiling itself is the
    injected ``snapshot_age_admissible`` verdict (design #16 §8).

    Args:
        time_valid: Whether trustworthy time is valid (``None`` / ``False`` => ``UNKNOWN``).
        monotonic_continuity_id: The reading's monotonic continuity id.
        age: The injected age magnitude (``None`` / non-finite / negative => ``UNKNOWN``).
        reference_continuity_id: The consumer's continuity id (must match).
        rcl_committed_history_present: Whether committed RCL history is present.
        wall_clock_or_recovery_or_restart_basis: Must be positively ``False`` (§18:405).
        broker_timestamp_or_new_source_basis: Must be positively ``False`` (§18 line 405).
        continuity_established: Whether monotonic continuity is established.
        snapshot_age_admissible: The injected time ``snapshot_age_admissible`` result.

    Returns:
        ``GRANT`` iff a refill is permissible, ``DENY`` on a headroom-manufacturing basis,
        else ``UNKNOWN``.
    """
    # A basis that would manufacture headroom is a positive refusal, not an unknown.
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
        # Cross-continuity: no subtraction is performed at all (§18 line 403).
        return ActionFlowResult.UNKNOWN
    if snapshot_age_admissible is not True:
        return ActionFlowResult.UNKNOWN
    if age is None or not age.is_finite():
        return ActionFlowResult.UNKNOWN
    if age < 0:
        # Negative age / future issue time clamps toward restriction (§18 line 405).
        return ActionFlowResult.UNKNOWN
    return ActionFlowResult.GRANT


def generation_fenced(
    artifact_generation: int | None, current_generation: int | None
) -> bool:
    """Whether an artifact is on the **current** side of the generation fence (AFG-INV-013).

    AFG-INV-013 line 205 verbatim: "Stale policy, flow, writer, recovery, authority,
    capability, credential, session, route, and egress generations cannot allocate,
    consume, or transmit." ``True`` **only** when both generations are concrete and
    **equal**: a strictly older generation is stale (fenced), a strictly newer one is an
    unrecognized future generation, and a ``None`` on either side is UNKNOWN — all three
    fail closed. This is a **different axis** from the §18 refill rule (M6: AFG-INV-013 is
    generation fencing, the refill rule is AFG-INV-004 line 169 + AFG-INV-007 line 181).

    The Restrictive Fence Record, the Local Restrictive Latch, and the per-send generation
    ordering **mechanism** are ADR-002-024 runtime (design #16 §0.2 Gap-6); this predicate
    decides staleness purely and enforces nothing.

    Args:
        artifact_generation: The artifact's generation (``None`` => fenced).
        current_generation: The current Action Flow Generation (``None`` => fenced).

    Returns:
        ``True`` iff the artifact is current (not fenced).
    """
    if artifact_generation is None or current_generation is None:
        return False
    return artifact_generation == current_generation


def action_flow_generation_monotone(
    earlier: OrderingEvent, later: OrderingEvent
) -> bool:
    """Whether ``earlier`` strictly precedes ``later`` in append-only order (§3.2 / §5.2).

    REUSES ``tos.ordering.compare_order`` (no re-authored order) to check the monotonic
    Action Flow Generation order (§5.2 line 117 "A monotonic generation"). ``True``
    **only** when the order is unambiguously ``BEFORE``; an ``AMBIGUOUS`` / ``AFTER`` pair
    fails closed. A wall clock never orders (§17 line 391; §18 line 405) — afg reads no
    clock.

    Args:
        earlier: The earlier ordering event.
        later: The later ordering event.

    Returns:
        ``True`` iff ``earlier`` provably precedes ``later``.
    """
    return compare_order(earlier, later) is Ordering.BEFORE


# ===========================================================================
# §6.5 — currentness / invalidation (§17 / §19; AFG-EV-009 substrate)
# ===========================================================================


def is_material(
    change: MaterialChangeKind | str | None, materiality_known: bool | None
) -> bool:
    """Whether an observed change is **material** (§19 line 413; §5.10 line 149 — Gap-7).

    §5.10 line 149 verbatim: "Unknown materiality is material." So an unknown or
    undeclared materiality (``materiality_known`` not positively ``True``) makes the change
    material regardless of its kind, and an absent (``None``) change is material too — a
    component may not declare a change immaterial by omission (§8 line 248 "Omitted or
    unknown fields are restrictive"). When materiality **is** positively established, the
    §19 line 413 enumerated kinds are material and any other token is not.

    Args:
        change: The observed change kind (``None`` => material).
        materiality_known: Whether materiality is positively established (``None`` /
            ``False`` => material).

    Returns:
        ``True`` iff the change must be treated as material.
    """
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
    """Whether an affected unclaimed decision / permit MUST be invalidated (§17 / §19).

    §19 line 413: a material change to the policy, broker limit, constraint, session,
    credential, route, endpoint, scope graph, time health, queue / in-flight state, cause
    lineage, RCL state, protective reserve, capability, or consumer compatibility
    invalidates every affected unclaimed decision and permit. §17 line 391: a cache, TTL,
    heartbeat, service health, broker connection, prior success, queue position, or the
    **absence of an invalidation** is **not** a currentness proof — so currentness must be
    *positively* established, and its absence invalidates. §17 line 397: the final egress
    may **not** recalculate a favorable vector, widen the decision, invent a cause, or
    change the action class; an attempt (or an unknown status) invalidates.

    Returns ``True`` (must invalidate) whenever any premise is unproven, and ``False``
    (stays current) **only** when there is no material trigger, currentness is positively
    established, currentness does not rest on a cache alone, no egress widening /
    recalculation is claimed, and there is something to keep current (a ``None`` decision
    **and** ``None`` permit invalidate — nothing can be proven current). The **active**
    RCL / final-egress currentness enforcement, bounded by the injected profile values
    ``B_action_flow_invalid_to_rcl`` / ``B_action_flow_invalid_to_egress``, is runtime
    (design #16 §6.5).

    Args:
        triggers: The observed changes with their materiality status (empty is **not**
            proof of currentness — §17 line 391).
        decision: The unclaimed decision, if any.
        permit: The unclaimed permit, if any.
        currentness_positively_established: Positive currentness proof (``None`` /
            ``False`` => invalidate).
        cache_ttl_heartbeat_health_or_prior_success_only: Whether currentness rests only
            on a cache / TTL / heartbeat / health / prior success (=> invalidate).
        egress_recalculated_favorably_or_widened: Must be positively ``False`` (§17:397).
        egress_invented_cause_or_changed_action_class: Must be positively ``False``
            (§17 line 397).

    Returns:
        ``True`` iff the decision / permit must be invalidated.
    """
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


# ===========================================================================
# §6.8 — non-revival + economic continuity (§19 / §22; AFG-EV-012 substrate)
# ===========================================================================


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
    """Whether nothing revives a prior decision / permit / authority (§22; AFG-INV-014).

    AFG-INV-014 line 209 / §22 line 465 verbatim: no restart, rollback, restore, failover,
    reconnect, backoff expiry, queue drain, counter refill, broker-throttle recovery,
    matching replay, or improved health revives an old decision, permit, capability,
    budget, authority, or live scope; "No automatic re-arm is permitted" (§30 line 693).

    Realized as an **unconditional** ``True`` with every recovery input **accepted and
    discarded** (isomorphic to the are ``non_revival_holds`` / spg ``expiry_revives_
    nothing`` / time ``recovery_generation_revives_nothing`` ``predicates.py:499``): no
    recovery input can influence the answer because the answer never reads them. A lawful
    re-arm always requires a fresh artifact plus a governed decision, never a revival of
    the old one, and the Recovery Barrier (ADR-002-017) / governed re-arm workflow is
    runtime (design #16 §6.8).

    Returns:
        ``True`` — nothing revives a prior artifact (unconditionally).
    """
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
    """Whether a possible broker / economic effect still persists (§19 line 419; INV-012).

    AFG-INV-012 line 201 / §19 line 419: the expiry of a permit, decision, policy,
    authority, retry window, or queue item does **not** expire a possible broker or
    economic effect — a missing ACK leaves the attempt potentially live and a cancel ACK
    is insufficient (§14 line 350 / §15 line 358). §13 line 342: "Releasing action-flow
    capacity never releases economic capacity without its separate Final Quantity Proof
    rules." Returns ``True`` (the effect persists) unless a Final Quantity Proof is
    **positively present**; a ``None`` / ``False`` fails closed to persistence.

    Every expiry input is **accepted and discarded**: no expiry can influence the answer
    because the answer never reads it (the structural realization of "expiry never expires
    possible broker or economic effect").

    Args:
        final_quantity_proof_present: Whether a Final Quantity Proof is positively present
            (the only thing that ends persistence).
        permit_expired: Accepted and discarded (§19 line 419).
        decision_expired: Accepted and discarded (§19 line 419).
        policy_or_retry_window_expired: Accepted and discarded (§19 line 419).
        queue_item_expired: Accepted and discarded (§19 line 419).
        ack_missing: Accepted and discarded (a missing ACK never releases, §14 line 350).
        cancel_ack_observed: Accepted and discarded (a cancel ACK is not an FQP, §15:358).

    Returns:
        ``True`` iff the economic effect still persists.
    """
    del permit_expired, decision_expired, policy_or_retry_window_expired
    del queue_item_expired, ack_missing, cancel_ack_observed
    return final_quantity_proof_present is not True


def restart_counter_assumption_admissible(
    *,
    assumed_zero_counter: bool | None,
    assumed_empty_queue: bool | None,
    assumed_unused_permit: bool | None,
) -> bool:
    """Whether the restart made no forbidden zero-state assumption (§22 line 463).

    §22 line 463: on restart or restore a component may **not** assume a zero counter, an
    empty queue, or an unused permit — the surviving state is unknown and unknown is
    restrictive (AFG-INV-007 line 181). ``True`` **only** when all three assumptions are
    positively ``False``; any ``True`` (the assumption was made) or ``None`` (unknown)
    fails closed.

    Args:
        assumed_zero_counter: Whether a zero counter was assumed (must be ``False``).
        assumed_empty_queue: Whether an empty queue was assumed (must be ``False``).
        assumed_unused_permit: Whether an unused permit was assumed (must be ``False``).

    Returns:
        ``True`` iff no forbidden zero-state assumption was made.
    """
    return (
        assumed_zero_counter is False
        and assumed_empty_queue is False
        and assumed_unused_permit is False
    )


# ===========================================================================
# Forward-only structural contract (design #16 §2.3 / §5.3)
# ===========================================================================


def decision_is_forward_only(decision: ActionFlowDecision) -> bool:
    """Whether the decision binds no future commitment coordinate (§5.3; ADR §29 q2).

    A **structural** check: the decision model must carry **none** of the reservation /
    permit / claim coordinates rcl charges post-commit
    (``GrantDecisionRef.bound_reservation_*`` ``authority.py:56-58``). Their presence
    would make the economic + action-flow commit protocol cyclic — exactly the cycle ADR
    §29 q2 requires to be avoided. A subclass that reintroduces one is a cyclic-binding
    canary and fails.

    Args:
        decision: The action flow decision.

    Returns:
        ``True`` iff the decision carries no forward commitment coordinate.
    """
    return _FORWARD_ONLY_FORBIDDEN_FIELDS.isdisjoint(type(decision).model_fields)
