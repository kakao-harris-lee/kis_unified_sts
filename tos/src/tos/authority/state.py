"""Authority predicate-input / output state models (ADR-002-003 §5, §12-§14, §17)."""

from __future__ import annotations

from tos.authority._base import AuthorityEffect, FrozenModel


class AuthorityEpochState(FrozenModel):
    """The per-domain current accepted epoch floor (ADR-002-003 §5.1/§5.2/§8.2)."""

    authority_domain: str | None = None
    current_epoch_floor: int | None = None


class GenerationVector(FrozenModel):
    """Non-collapsing generation-coordinate vector (design §4.7; ADR-002-003 §27 OQ2)."""

    safety_authority_epoch: int | None = None
    writer_epoch: int | None = None
    membership_generation: int | None = None
    restore_generation: int | None = None
    recovery_generation: int | None = None
    time_health_generation: int | None = None
    process_generation: int | None = None
    hard_safety_envelope_generation: int | None = None
    runtime_safety_profile_generation: int | None = None


class CurrentnessWitness(FrozenModel):
    """An online currentness witness (ADR-002-003 §12.1 line 454-456; §9.4)."""

    present: bool = False
    within_containment_bound: bool | None = None
    witness_source: str | None = None
    conflicting: bool = False


class CapabilityValidityInputs(FrozenModel):
    """Injected inputs the 6-part validity predicate folds (ADR-002-003 §1; §9.4; §18)."""

    currentness: CurrentnessWitness = CurrentnessWitness()
    revocation_status: str | None = None
    superseded: bool | None = None
    consumed: bool | None = None
    issuer_key_status: str | None = None
    environment_and_mode_matches: bool | None = None
    dominating_restriction: bool = False


class LeaseReassignmentInputs(FrozenModel):
    """Injected inputs the overlapping-reassignment predicate folds (ADR-002-003 §14.5)."""

    prior_owner_scope: str | None = None
    hard_fence_proven: bool | None = None
    lease_expiry_fence_elapsed: bool | None = None


class RearmChecklist(FrozenModel):
    """The 14 re-arm prerequisites + dual-control principals (ADR-002-003 §17.1/§17.2)."""

    trustworthy_time_restored: bool | None = None
    current_epoch_established: bool | None = None
    stale_epochs_fenced: bool | None = None
    account_wide_reconciliation_complete: bool | None = None
    unknown_orders_resolved: bool | None = None
    unattributed_external_activity_resolved: bool | None = None
    risk_capacity_ledger_consistency_verified: bool | None = None
    protective_leases_reconciled: bool | None = None
    hard_and_runtime_versions_verified: bool | None = None
    broker_capability_current: bool | None = None
    no_unresolved_critical_alert: bool | None = None
    recovery_coordinator_evidence_complete: bool | None = None
    fresh_live_authorization_issued: bool | None = None
    explicit_human_dual_control_complete: bool | None = None

    limit_enlarger_principal: str | None = None
    armer_principal: str | None = None


class PartitionAuthorityVerdict(FrozenModel):
    """Per-action allow/preserve verdict under an unverifiable control plane (§13.1)."""

    new_normal_risk_increasing_denied: bool
    new_aggregate_capacity_commitment_denied: bool
    normal_capability_renewal_denied: bool
    live_rearm_denied: bool
    limit_enlargement_denied: bool
    automatic_rearm_denied: bool
    existing_orders_preserved: bool = True
    existing_fills_preserved: bool = True
    existing_positions_preserved: bool = True
    existing_reservations_preserved: bool = True


class RearmVerdict(FrozenModel):
    """The result of the re-arm gate (ADR-002-003 §17.1; §8.4)."""

    armable: bool
    authority_effect: AuthorityEffect = AuthorityEffect()
