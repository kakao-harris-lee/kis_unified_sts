"""Pure Safety Authority predicates (design §5, §6; ADR-002-003 §5-§17)."""

from __future__ import annotations

from collections.abc import Sequence

from tos.authority._base import ArtifactStatus, AuthorityEffect
from tos.authority.records import (
    DegradedLeaseOwnershipRecord,
    SafetyAuthorityCapability,
)
from tos.authority.state import (
    AuthorityEpochState,
    CapabilityValidityInputs,
    CurrentnessWitness,
    LeaseReassignmentInputs,
    PartitionAuthorityVerdict,
    RearmChecklist,
    RearmVerdict,
)
from tos.authority.vocabulary import (
    PRECEDENCE_RANK,
    RESTRICTIVE_DOMINATING_TYPES,
    AuthorityState,
    CapabilityType,
)
from tos.time import (
    HealthState,
    TimeContinuityIdentity,
    anchor_valid,
    conservative_usable_lifetime,
)

_ISSUER_KEY_VALID = "valid"

_NOT_REVOKED = "not_revoked"

_DEGRADED_PROTECTIVE_RANK: int = PRECEDENCE_RANK[AuthorityState.DEGRADED_PROTECTIVE]

_HALT_DENIED_TYPES: frozenset[CapabilityType] = frozenset(
    {
        CapabilityType.NORMAL_RISK_INCREASING,
        CapabilityType.REARM,
        CapabilityType.LIMIT_ACTIVATION,
    }
)

_REARM_PREREQUISITES: tuple[str, ...] = (
    "trustworthy_time_restored",
    "current_epoch_established",
    "stale_epochs_fenced",
    "account_wide_reconciliation_complete",
    "unknown_orders_resolved",
    "unattributed_external_activity_resolved",
    "risk_capacity_ledger_consistency_verified",
    "protective_leases_reconciled",
    "hard_and_runtime_versions_verified",
    "broker_capability_current",
    "no_unresolved_critical_alert",
    "recovery_coordinator_evidence_complete",
    "fresh_live_authorization_issued",
    "explicit_human_dual_control_complete",
)


def authority_epoch_current(
    claimed_epoch: int | None,
    authority_domain: str | None,
    state: AuthorityEpochState,
) -> bool:
    """Whether a claimed epoch is current for its domain (§5.1; SA-INV-001/002)."""
    if (
        claimed_epoch is None
        or authority_domain is None
        or state.authority_domain is None
        or state.current_epoch_floor is None
    ):
        return False
    if authority_domain != state.authority_domain:
        return False
    return claimed_epoch >= state.current_epoch_floor


def authority_epoch_fenced(
    claimed_epoch: int | None,
    authority_domain: str | None,
    state: AuthorityEpochState,
) -> bool:
    """Whether a claimed epoch is FENCED (the negation of :func:`authority_epoch_current`)."""
    return not authority_epoch_current(claimed_epoch, authority_domain, state)


def currentness_admissible(witness: CurrentnessWitness) -> bool:
    """Whether an online currentness witness is admissible (§5.4; §12.1/§12.2)."""
    if not witness.present:
        return False
    if witness.within_containment_bound is not True:
        return False
    return not witness.conflicting


def permissive_capability_valid(
    capability: SafetyAuthorityCapability,
    state: AuthorityEpochState,
    inputs: CapabilityValidityInputs,
    lease_ok: bool,
) -> bool:
    """Whether an execution path may accept a permissive capability (§5.2; §1 line 17-24)."""
    if capability.status == ArtifactStatus.DRAFT:
        return False
    if capability.missing_required_fields():
        return False

    if (
        capability.maximum_quantity is None
        or capability.maximum_risk_vector_effect_or_reservation_identity is None
    ):
        return False

    if inputs.issuer_key_status != _ISSUER_KEY_VALID:
        return False

    if not authority_epoch_current(
        capability.safety_authority_epoch, capability.authority_domain, state
    ):
        return False

    if inputs.environment_and_mode_matches is not True:
        return False

    if capability.capability_type == CapabilityType.DEGRADED_PROTECTIVE:
        if not lease_ok:
            return False
    elif not currentness_admissible(inputs.currentness):
        return False

    if inputs.consumed is not False:
        return False
    if inputs.superseded is not False:
        return False
    if inputs.revocation_status != _NOT_REVOKED:
        return False
    return not inputs.dominating_restriction


def is_restrictive_dominating_type(capability_type: CapabilityType | None) -> bool:
    """Whether a capability type dominates any permissive grant (§5.3; §7 line 239-242)."""
    return capability_type in RESTRICTIVE_DOMINATING_TYPES


def restrictive_dominates(
    current_state: AuthorityState,
    outstanding: Sequence[SafetyAuthorityCapability] = (),
) -> bool:
    """Whether a restrictive state / capability dominates any permissive grant (§5.3)."""
    if PRECEDENCE_RANK[current_state] >= _DEGRADED_PROTECTIVE_RANK:
        return True
    return any(is_restrictive_dominating_type(c.capability_type) for c in outstanding)


def safer_transition_allowed(
    from_state: AuthorityState, to_state: AuthorityState
) -> bool:
    """Whether a safer-state (or equal) transition is allowed (§5.3; §7 line 237-239)."""
    return PRECEDENCE_RANK[to_state] >= PRECEDENCE_RANK[from_state]


def permissive_transition_allowed(
    from_state: AuthorityState,
    to_state: AuthorityState,
    epoch_current: bool | None,
) -> bool:
    """Whether a permissive (less-safe) transition is allowed (§5.3; §7 line 239)."""
    if PRECEDENCE_RANK[to_state] >= PRECEDENCE_RANK[from_state]:
        return True
    return epoch_current is True


def restrictive_may_apply_when_stale(
    *, authentic: bool | None, cannot_enlarge: bool | None
) -> bool:
    """Whether a stale but authentic restrictive message may be applied (§5.3; §16.2)."""
    return authentic is True and cannot_enlarge is True


def halt_denies(capability_type: CapabilityType) -> bool:
    """Whether HALT denies a capability type (§5.5; §16.3 line 634-641)."""
    return capability_type in _HALT_DENIED_TYPES


def lease_scope_exclusive(
    claimant_ownership_id: str | None,
    owner_records: Sequence[DegradedLeaseOwnershipRecord],
) -> bool:
    """Whether the claimant is the sole owner of its scope + capacity (§6.1; SA-INV-006)."""
    if claimant_ownership_id is None:
        return False
    claimant = next(
        (r for r in owner_records if r.lease_ownership_id == claimant_ownership_id),
        None,
    )
    if claimant is None:
        return False
    if (
        claimant.exclusive_scope is None
        or claimant.referenced_capacity_lease_id is None
    ):
        return False
    key = (claimant.exclusive_scope, claimant.referenced_capacity_lease_id)
    owners_of_key = [
        r
        for r in owner_records
        if (r.exclusive_scope, r.referenced_capacity_lease_id) == key
    ]
    return len(owners_of_key) == 1


def overlapping_reassignment_forbidden(inputs: LeaseReassignmentInputs) -> bool:
    """Whether overlapping-scope reassignment is FORBIDDEN (§6.2; SA-INV-007; §14.5)."""
    return not (
        inputs.hard_fence_proven is True or inputs.lease_expiry_fence_elapsed is True
    )


def degraded_lease_valid(
    lease_ownership: DegradedLeaseOwnershipRecord,
    owner_registry_view: Sequence[DegradedLeaseOwnershipRecord],
    *,
    protective_classification_present: bool | None,
    broker_capability_permits: bool | None,
    dominating_state: AuthorityState,
    health_state: HealthState,
    continuity_now: TimeContinuityIdentity,
    suspension_ms: int | None,
    max_suspension_ms: int | None,
    issued_lifetime: int | None,
    elapsed_monotonic: int | None,
    source_transport_uncertainty: int | None,
    max_drift_error: int | None,
    suspension_uncertainty: int | None,
    safety_margin: int | None,
) -> bool:
    """Whether a degraded protective lease is valid for a new action (§6.3; §13.2)."""
    if protective_classification_present is not True:
        return False
    if (
        lease_ownership.referenced_capacity_lease_id is None
        or lease_ownership.referenced_protective_pool_identity is None
    ):
        return False
    if (
        lease_ownership.status == ArtifactStatus.DRAFT
        or lease_ownership.canonical_digest is None
    ):
        return False
    if (
        conservative_usable_lifetime(
            issued_lifetime=issued_lifetime,
            elapsed_monotonic=elapsed_monotonic,
            source_transport_uncertainty=source_transport_uncertainty,
            max_drift_error=max_drift_error,
            suspension_uncertainty=suspension_uncertainty,
            safety_margin=safety_margin,
        )
        is None
    ):
        return False
    if not anchor_valid(
        continuity_now,
        lease_ownership.local_monotonic_anchor,
        suspension_ms=suspension_ms,
        max_suspension_ms=max_suspension_ms,
    ):
        return False
    if not lease_scope_exclusive(
        lease_ownership.lease_ownership_id, owner_registry_view
    ):
        return False
    if broker_capability_permits is not True:
        return False
    if PRECEDENCE_RANK[dominating_state] > _DEGRADED_PROTECTIVE_RANK:
        return False
    return health_state in {HealthState.DEGRADED_HOLDOVER, HealthState.TRUSTED}


def degraded_lease_invalidated(
    lease_ownership: DegradedLeaseOwnershipRecord,
    owner_registry_view: Sequence[DegradedLeaseOwnershipRecord],
    *,
    continuity_now: TimeContinuityIdentity,
    suspension_ms: int | None,
    max_suspension_ms: int | None,
    issued_lifetime: int | None,
    elapsed_monotonic: int | None,
    source_transport_uncertainty: int | None,
    max_drift_error: int | None,
    suspension_uncertainty: int | None,
    safety_margin: int | None,
    protective_capacity_exhausted: bool | None,
    hard_envelope_incompatible: bool | None,
    broker_profile_revoked: bool | None,
    dominating_state: AuthorityState,
) -> bool:
    """Whether a degraded lease is invalidated for new actions (§6.4; §14.4 line 563-576)."""
    if not anchor_valid(
        continuity_now,
        lease_ownership.local_monotonic_anchor,
        suspension_ms=suspension_ms,
        max_suspension_ms=max_suspension_ms,
    ):
        return True
    if (
        conservative_usable_lifetime(
            issued_lifetime=issued_lifetime,
            elapsed_monotonic=elapsed_monotonic,
            source_transport_uncertainty=source_transport_uncertainty,
            max_drift_error=max_drift_error,
            suspension_uncertainty=suspension_uncertainty,
            safety_margin=safety_margin,
        )
        is None
    ):
        return True
    if not lease_scope_exclusive(
        lease_ownership.lease_ownership_id, owner_registry_view
    ):
        return True
    if protective_capacity_exhausted is not False:
        return True
    if hard_envelope_incompatible is not False:
        return True
    if broker_profile_revoked is not False:
        return True
    return PRECEDENCE_RANK[dominating_state] > _DEGRADED_PROTECTIVE_RANK


def partition_authority_verdict(
    control_plane_verifiable: bool | None,
) -> PartitionAuthorityVerdict:
    """The per-action verdict when the safety control plane is (un)verifiable (§6.5; §13.1)."""
    denied = control_plane_verifiable is None or control_plane_verifiable is False
    return PartitionAuthorityVerdict(
        new_normal_risk_increasing_denied=denied,
        new_aggregate_capacity_commitment_denied=denied,
        normal_capability_renewal_denied=denied,
        live_rearm_denied=denied,
        limit_enlargement_denied=denied,
        automatic_rearm_denied=True,
    )


def rearm_gate(checklist: RearmChecklist) -> RearmVerdict:
    """The non-authorizing re-arm gate (§6.6; §17.1/§17.2; SA-INV-013/014)."""
    all_prerequisites = all(
        getattr(checklist, name) is True for name in _REARM_PREREQUISITES
    )
    separation_of_duties = (
        checklist.limit_enlarger_principal is not None
        and checklist.armer_principal is not None
        and checklist.limit_enlarger_principal != checklist.armer_principal
    )
    return RearmVerdict(
        armable=all_prerequisites and separation_of_duties,
        authority_effect=AuthorityEffect(),
    )


def recovery_generation_revives_nothing(
    *,
    invalidated_under_generation: int | None,
    new_generation: int | None,
) -> bool:
    """Whether a new generation revives an earlier invalidation — never (§4.4; SA-INV-011)."""
    del invalidated_under_generation, new_generation
    return True
