"""afg action-flow decision predicates + the produced-seam producers (design #16 §5/§6)."""

from __future__ import annotations

from collections.abc import Sequence

from tos.afg.records import (
    ActionAmplificationEnvelope,
    ActionCause,
    ActionFlowDecision,
    ActionFlowGovernorEffect,
    ActionFlowPolicy,
    ActionFlowStateSnapshot,
    ActionFlowVector,
    ObservedAmplification,
    ProtectiveFlowReserveClaim,
)
from tos.afg.vocabulary import (
    ADMISSIBILITY_ADMISSIBLE,
    ATTEMPT_STATE_SEND_FAILED_PROVEN,
    BROKER_ORDER_STATE_UNKNOWN,
    RESERVED_GUARANTEE_TOKENS,
    ActionClassKind,
    ActionFlowResult,
    ActionFlowScopeKind,
    DocumentedScopeStatus,
    broadest_scope,
    is_action_flow_dimension_id,
    most_conservative_action_class,
    narrowest_scope,
)
from tos.canonical import CanonicalizationScheme
from tos.rcl import CapacityVector, aggregate_usage, effective_limit

__all__ = [
    "scope_graph_complete",
    "shared_limit_conservative",
    "envelope_not_enlarged",
    "amplification_bounded",
    "cause_lineage_complete",
    "changed_command_is_new_action",
    "headroom_within_limits",
    "atomic_economic_flow_coverage",
    "action_flow_decision",
    "no_blind_retry",
    "cancel_ack_not_final_quantity_proof",
    "oscillation_bounded",
    "action_class_conservative",
    "reserve_exclusive",
    "priority_is_not_reserve",
    "partition_lease_exclusive",
    "governor_grants_no_authority",
    "decision_content_ref",
    "applicable_action_flow_scopes_of",
    "action_flow_vector_of",
]


def scope_graph_complete(
    snapshot: ActionFlowStateSnapshot | None,
    required_scopes: frozenset[ActionFlowScopeKind],
    *,
    producer_self_declared_scope: bool | None,
) -> bool:
    """Whether the scope graph is complete over every applicable shared scope (§10)."""
    if snapshot is None:
        return False
    if not required_scopes:
        return False
    if producer_self_declared_scope is not False:
        return False
    covered = frozenset(snapshot.covered_scopes)
    if not required_scopes <= covered:
        return False
    for scope in required_scopes:
        evidence = snapshot.independence_for(scope)
        if evidence is None or not evidence.is_independent():
            return False
    return True


def shared_limit_conservative(
    documented_scope_status: DocumentedScopeStatus | str | None,
    claimed_scope: ActionFlowScopeKind | None,
    credible_containing_scopes: frozenset[ActionFlowScopeKind],
    independence_evidence: bool | None,
) -> ActionFlowScopeKind | ActionFlowResult:
    """The conservative scope a shared limit is enforced over (design #16 §5.1, C1)."""
    if not credible_containing_scopes:
        return ActionFlowResult.UNKNOWN

    if documented_scope_status is not DocumentedScopeStatus.VERIFIED_COMPLETE:
        widest = broadest_scope(credible_containing_scopes)
        return widest if widest is not None else ActionFlowResult.UNKNOWN

    if independence_evidence is not True:
        smallest = narrowest_scope(credible_containing_scopes)
        return smallest if smallest is not None else ActionFlowResult.UNKNOWN

    if claimed_scope is None:
        return ActionFlowResult.UNKNOWN
    return claimed_scope


def envelope_not_enlarged(
    *,
    requested_limit: CapacityVector,
    injected_envelope_max: CapacityVector | None,
    limit_source_is_injected_envelope: bool | None,
) -> bool:
    """Whether the admission limit does not enlarge the Hard Safety Envelope (§8 line 248)."""
    if injected_envelope_max is None:
        return False
    if limit_source_is_injected_envelope is not True:
        return False
    for component in requested_limit.components:
        dimension = component.dimension_id
        if not is_action_flow_dimension_id(dimension):
            return False
        requested = component.magnitude
        if requested is None:
            return False
        envelope_max = injected_envelope_max.magnitude(dimension)  # type: ignore[arg-type]
        if envelope_max is None:
            return False
        if requested > envelope_max:
            return False
    return True


_AMPLIFICATION_AXES: tuple[tuple[str, str], ...] = (
    ("max_fan_out", "fan_out"),
    ("max_depth", "depth"),
    ("max_attempts", "attempts"),
    ("max_mutations", "mutations"),
    ("max_queries", "queries"),
    ("max_queue_depth", "queue_depth"),
    ("max_in_flight", "in_flight"),
    ("max_elapsed_monotonic", "elapsed_monotonic"),
    ("max_duplicate_redelivery_expansion", "duplicate_redelivery_expansion"),
    (
        "max_failover_reconnect_replay_expansion",
        "failover_reconnect_replay_expansion",
    ),
    ("max_amplification_per_cause", "amplification_per_cause"),
)


def amplification_bounded(
    envelope: ActionAmplificationEnvelope | None,
    observed: ObservedAmplification | None,
) -> bool:
    """Whether every amplification axis stays within its injected bound (§11; AFG-INV-002)."""
    if envelope is None or observed is None:
        return False
    if observed.duplicate_event_created_new_allowance is not False:
        return False
    if observed.envelope_reset_on_duplicate is not False:
        return False
    if observed.concurrent_consumers_share_one_envelope is not True:
        return False
    for bound_field, observed_field in _AMPLIFICATION_AXES:
        bound = getattr(envelope, bound_field)
        count = getattr(observed, observed_field)
        if bound is None or count is None:
            return False
        if count > bound:
            return False
    return True


def cause_lineage_complete(cause: ActionCause | None) -> bool:
    """Whether the cause carries a root identity and a complete parent lineage (§11:284)."""
    if cause is None:
        return False
    if cause.root_cause_identity is None or cause.root_cause_identity == "TBD":
        return False
    if not cause.parent_lineage:
        return False
    if cause.lineage_attested is not True:
        return False
    if cause.cyclic is not False:
        return False
    if cause.forked_beyond_bound is not False:
        return False
    return cause.inconsistent is False


def changed_command_is_new_action(
    *,
    command_changed: bool | None,
    fresh_cause_and_artifacts: bool | None,
) -> bool:
    """Whether a changed command was treated as a **new** action (§11 line 294; AFG-AC-002)."""
    if command_changed is False:
        return True
    if command_changed is not True:
        return False
    return fresh_cause_and_artifacts is True


def headroom_within_limits(
    usage_vectors: Sequence[CapacityVector],
    hard_limit: CapacityVector | None,
    runtime_limit: CapacityVector | None,
) -> ActionFlowResult:
    """Whether aggregate action-flow usage stays within the effective limit (§13 item 6)."""
    if not usage_vectors:
        return ActionFlowResult.UNKNOWN
    if hard_limit is None or runtime_limit is None:
        return ActionFlowResult.UNKNOWN

    usage = aggregate_usage(list(usage_vectors))
    limits = effective_limit(hard_limit, runtime_limit)
    dimension_ids = usage.dimension_ids()
    if not dimension_ids:
        return ActionFlowResult.UNKNOWN

    verdict = ActionFlowResult.GRANT
    for dimension in dimension_ids:
        if not is_action_flow_dimension_id(dimension):
            return ActionFlowResult.UNKNOWN
        used = usage.magnitude(dimension)
        limit = limits.magnitude(dimension)
        if used is None or limit is None:
            return ActionFlowResult.UNKNOWN
        if used > limit:
            verdict = ActionFlowResult.DENY
    return verdict


def atomic_economic_flow_coverage(
    economic_ref: str | None,
    flow_vector: ActionFlowVector | None,
    *,
    committed_flow_vectors: Sequence[CapacityVector] = (),
    hard_limit: CapacityVector | None = None,
    runtime_limit: CapacityVector | None = None,
    economic_commitment_exclusive: bool | None = None,
    flow_commitment_exclusive: bool | None = None,
) -> ActionFlowResult:
    """Whether economic **and** action-flow coverage are both established (AFG-INV-005)."""
    if economic_ref is None or economic_ref == "TBD":
        return ActionFlowResult.UNKNOWN
    if flow_vector is None or not flow_vector.dimension_ids():
        return ActionFlowResult.UNKNOWN
    if economic_commitment_exclusive is not True:
        return ActionFlowResult.UNKNOWN
    if flow_commitment_exclusive is not True:
        return ActionFlowResult.UNKNOWN
    return headroom_within_limits(
        [*committed_flow_vectors, flow_vector], hard_limit, runtime_limit
    )


def _decide_action_flow_result(
    *,
    coverage: ActionFlowResult,
    scope_complete: bool,
    lineage_complete: bool,
    amplification_ok: bool,
    envelope_ok: bool,
    generation_current: bool,
    applicable_action_flow_scopes: tuple[str, ...],
) -> ActionFlowResult:
    """The pure GRANT / DENY / UNKNOWN verdict (§5.3/§13); restrictive-by-default."""
    if scope_complete is not True:
        return ActionFlowResult.UNKNOWN
    if lineage_complete is not True:
        return ActionFlowResult.UNKNOWN
    if amplification_ok is not True:
        return ActionFlowResult.UNKNOWN
    if generation_current is not True:
        return ActionFlowResult.UNKNOWN
    if coverage is ActionFlowResult.UNKNOWN:
        return ActionFlowResult.UNKNOWN
    if not applicable_action_flow_scopes:
        return ActionFlowResult.DENY
    if envelope_ok is not True:
        return ActionFlowResult.DENY
    if coverage is ActionFlowResult.DENY:
        return ActionFlowResult.DENY
    if coverage is not ActionFlowResult.GRANT:
        return ActionFlowResult.UNKNOWN
    return ActionFlowResult.GRANT


def action_flow_decision(
    *,
    coverage: ActionFlowResult,
    scope_complete: bool,
    lineage_complete: bool,
    amplification_ok: bool,
    envelope_ok: bool,
    generation_current: bool,
    applicable_action_flow_scopes: tuple[str, ...],
    decision_id: str,
    decision_generation: int,
    scheme: CanonicalizationScheme,
    policy: ActionFlowPolicy | None = None,
    snapshot: ActionFlowStateSnapshot | None = None,
    action_class: ActionClassKind | None = None,
    action_flow_vector: ActionFlowVector | None = None,
    decision_effective_limit: ActionFlowVector | None = None,
    command_identity: str | None = None,
    command_digest: str | None = None,
    cause_digest: str | None = None,
    lineage_digest: str | None = None,
    amplification_envelope_digest: str | None = None,
    protective_classification_digest: str | None = None,
) -> ActionFlowDecision:
    """Decide GRANT / DENY / UNKNOWN and issue the forward-only decision (§5.4 / §13)."""
    result = _decide_action_flow_result(
        coverage=coverage,
        scope_complete=scope_complete,
        lineage_complete=lineage_complete,
        amplification_ok=amplification_ok,
        envelope_ok=envelope_ok,
        generation_current=generation_current,
        applicable_action_flow_scopes=applicable_action_flow_scopes,
    )
    decision = ActionFlowDecision.issue(
        scheme=scheme,
        decision_id=decision_id,
        decision_generation=decision_generation,
        result=result,
        policy_digest=policy.canonical_digest if policy is not None else None,
        policy_generation=policy.policy_generation if policy is not None else None,
        snapshot_digest=snapshot.canonical_digest if snapshot is not None else None,
        cause_digest=cause_digest,
        lineage_digest=lineage_digest,
        command_identity=command_identity,
        command_digest=command_digest,
        action_class=action_class,
        applicable_action_flow_scopes=applicable_action_flow_scopes,
        action_flow_vector=(
            action_flow_vector if action_flow_vector is not None else ActionFlowVector()
        ),
        effective_limit=(
            decision_effective_limit
            if decision_effective_limit is not None
            else ActionFlowVector()
        ),
        amplification_envelope_digest=amplification_envelope_digest,
        protective_classification_digest=protective_classification_digest,
    )
    assert isinstance(decision, ActionFlowDecision)
    return decision


def no_blind_retry(
    attempt_state: str | None,
    broker_order_state: str | None,
    idempotency_proven: bool | None,
    budget_remaining: int | None,
    *,
    complete_evidence_capability_coverage_authority: bool | None = None,
    blind_failover_attempted: bool | None = None,
    retry_count: int | None = None,
    elapsed_ms: int | None = None,
    backoff_ms: int | None = None,
    repeated_identical_response: bool | None = None,
) -> bool:
    """Whether a **governed** (non-blind) retry is admissible (§14; AFG-INV-008)."""
    del retry_count, elapsed_ms, backoff_ms, repeated_identical_response

    if attempt_state != ATTEMPT_STATE_SEND_FAILED_PROVEN:
        return False
    if broker_order_state is None or broker_order_state == BROKER_ORDER_STATE_UNKNOWN:
        return False
    if idempotency_proven is not True:
        return False
    if budget_remaining is None or budget_remaining <= 0:
        return False
    if complete_evidence_capability_coverage_authority is not True:
        return False
    return blind_failover_attempted is False


def cancel_ack_not_final_quantity_proof(
    broker_order_state: str | None,
    *,
    final_quantity_proof_present: bool | None,
    original_and_replacement_covered: bool | None,
    capacity_release_claimed: bool | None = None,
    replacement_reuse_claimed: bool | None = None,
    retry_claimed: bool | None = None,
) -> bool:
    """Whether the cancel-ACK-is-not-a-Final-Quantity-Proof rule holds (§15; AFG-INV-009)."""
    if broker_order_state is None:
        return False
    if original_and_replacement_covered is not True:
        return False
    claims = (capacity_release_claimed, replacement_reuse_claimed, retry_claimed)
    if any(claim is not False for claim in claims):
        return final_quantity_proof_present is True
    return True


def oscillation_bounded(
    cause: ActionCause | None,
    envelope: ActionAmplificationEnvelope | None,
    observed: ObservedAmplification | None,
    *,
    new_cause_created_for_budget_reset: bool | None,
    reserve_present: bool | None,
) -> bool:
    """Whether cancel/submit oscillation stays bounded (§15 line 360-362; AFG-INV-009)."""
    if cause is None or envelope is None or observed is None:
        return False
    if new_cause_created_for_budget_reset is not False:
        return False
    if not cause_lineage_complete(cause):
        return False
    if not amplification_bounded(envelope, observed):
        return False
    return reserve_present is True


def action_class_conservative(
    claimed_class: ActionClassKind | None,
    applicable_classes: frozenset[ActionClassKind],
    vector: CapacityVector | None = None,
) -> ActionClassKind | ActionFlowResult:
    """The governing action class when classifications conflict (§9 line 268)."""
    if not applicable_classes:
        return ActionFlowResult.UNKNOWN
    if vector is not None:
        for dimension in vector.dimension_ids():
            if not is_action_flow_dimension_id(dimension):
                return ActionFlowResult.UNKNOWN
    candidates = set(applicable_classes)
    if claimed_class is not None:
        candidates.add(claimed_class)
    governing = most_conservative_action_class(candidates)
    return governing if governing is not None else ActionFlowResult.UNKNOWN


def reserve_exclusive(
    claim: ProtectiveFlowReserveClaim | None,
    is_reserved: bool | None,
    *,
    normal_traffic_borrowed: bool | None,
    normal_traffic_consumed: bool | None,
    relabelled_as_normal: bool | None,
    repay_reserve_later_claimed: bool | None,
) -> bool:
    """Whether the protective flow reserve is exclusively preserved (§16; AFG-INV-006)."""
    if claim is None:
        return False
    if not is_action_flow_dimension_id(claim.dimension_id):
        return False
    magnitude = claim.reserved_magnitude
    if magnitude is None or not magnitude.is_finite():
        return False
    if is_reserved is not True:
        return False
    if normal_traffic_borrowed is not False:
        return False
    if normal_traffic_consumed is not False:
        return False
    if relabelled_as_normal is not False:
        return False
    return repay_reserve_later_claimed is False


def priority_is_not_reserve(
    guarantee_level_token: str | None,
    *,
    exclusive_capacity_present: bool | None,
    high_priority_queue: bool | None = None,
) -> bool:
    """Whether a declared guarantee is backed by **exclusive capacity** (§16 line 372)."""
    del high_priority_queue
    if guarantee_level_token is None:
        return False
    if guarantee_level_token not in RESERVED_GUARANTEE_TOKENS:
        return False
    return exclusive_capacity_present is True


def partition_lease_exclusive(
    lease_admissible: str | None,
    remaining_budget: int | None,
    monotonic_continuity_id: str | None,
    *,
    reference_continuity_id: str | None,
    new_normal_permit_during_partition: bool | None,
    lease_refilled_remotely_or_by_wall_clock: bool | None,
    exclusivity_retained: bool | None,
    stale_writer_hard_fenced: bool | None,
) -> bool:
    """Whether a partition-time protective lease may still be consumed (§20; AFG-EV-010)."""
    if lease_admissible != ADMISSIBILITY_ADMISSIBLE:
        return False
    if remaining_budget is None or remaining_budget <= 0:
        return False
    if monotonic_continuity_id is None or reference_continuity_id is None:
        return False
    if monotonic_continuity_id != reference_continuity_id:
        return False
    if new_normal_permit_during_partition is not False:
        return False
    if lease_refilled_remotely_or_by_wall_clock is not False:
        return False
    if exclusivity_retained is not True:
        return False
    return stale_writer_hard_fenced is True


def governor_grants_no_authority(effect: ActionFlowGovernorEffect) -> bool:
    """Whether the governor effect grants nothing (§7 line 220/229; AFG-INV-011)."""
    declared = type(effect).model_fields
    if not declared:
        return False
    return all(getattr(effect, name) is False for name in declared)


def decision_content_ref(
    decision: ActionFlowDecision,
) -> tuple[str | None, int | None, str | None]:
    """The forward-only ``(decision_id, decision_generation, canonical_digest)`` (§3.4)."""
    return (
        decision.decision_id,
        decision.decision_generation,
        decision.canonical_digest,
    )


def applicable_action_flow_scopes_of(decision: ActionFlowDecision) -> tuple[str, ...]:
    """The exact action-flow scopes the decision applies to (rcl seam, §3.4)."""
    return decision.applicable_action_flow_scopes


def action_flow_vector_of(decision: ActionFlowDecision) -> ActionFlowVector:
    """The decided action-flow vector — the rcl ``CapacityVector`` type (§3.4 / §0.4c)."""
    return decision.action_flow_vector
