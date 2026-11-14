"""afg value models + injected inputs + the four digest-bound artifacts (design #16 §2)."""

from __future__ import annotations

from typing import ClassVar

from tos.afg._base import (
    AllFalseActionFlowAuthority,
    ArtifactIntegrityError,
    FrozenModel,
    IndependentIdArtifact,
)
from tos.afg.vocabulary import (
    ActionClassKind,
    ActionFlowDimensionKind,
    ActionFlowResult,
    ActionFlowScopeKind,
    MaterialChangeKind,
)
from tos.canonical import CanonicalDecimal
from tos.rcl import CapacityVector

__all__ = [
    "ActionFlowVector",
    "ActionFlowGovernorEffect",
    "ScopeIndependenceEvidence",
    "ActionCause",
    "ActionAmplificationEnvelope",
    "ObservedAmplification",
    "ProtectiveFlowReserveClaim",
    "PermitConsumptionState",
    "CurrentnessTrigger",
    "ActionFlowPolicy",
    "ActionFlowStateSnapshot",
    "ActionFlowDecision",
    "ActionFlowPermit",
]

ActionFlowVector = CapacityVector


class ActionFlowGovernorEffect(AllFalseActionFlowAuthority):
    """Authority effect of a governor decision / GRANT / permit — every flag false."""

    creates_capacity: bool = False
    mutates_budget: bool = False
    issues_authority: bool = False
    permits_transmission: bool = False
    holds_broker_credential: bool = False
    may_rearm: bool = False


class ScopeIndependenceEvidence(FrozenModel):
    """Per-scope independence evidence (ADR-002-022 §10 line 278)."""

    scope: ActionFlowScopeKind | None = None
    allocation_separated: bool | None = None
    refill_separated: bool | None = None
    broker_enforcement_separated: bool | None = None
    credential_session_state_separated: bool | None = None
    failure_domain_separated: bool | None = None
    final_route_separated: bool | None = None
    basis_is_local_counter_only: bool | None = None
    basis_is_scheduler_priority_only: bool | None = None

    _SEPARATION_AXES: ClassVar[tuple[str, ...]] = (
        "allocation_separated",
        "refill_separated",
        "broker_enforcement_separated",
        "credential_session_state_separated",
        "failure_domain_separated",
        "final_route_separated",
    )

    def is_independent(self) -> bool:
        """Whether this scope is positively evidenced as independent (§10 line 278)."""
        if self.basis_is_local_counter_only is not False:
            return False
        if self.basis_is_scheduler_priority_only is not False:
            return False
        return all(getattr(self, axis) is True for axis in type(self)._SEPARATION_AXES)


class ActionCause(FrozenModel):
    """One action's root cause + complete parent lineage (ADR-002-022 §5.7 line 135-137)."""

    root_cause_identity: str | None = None
    parent_lineage: tuple[str, ...] = ()
    lineage_attested: bool | None = None
    cyclic: bool | None = None
    forked_beyond_bound: bool | None = None
    inconsistent: bool | None = None
    command_identity: str | None = None
    command_digest: str | None = None
    duplicate_of_cause_identity: str | None = None


class ActionAmplificationEnvelope(FrozenModel):
    """The finite amplification bound per root cause (§5.8 line 139-141; §11 line 284-292)."""

    max_fan_out: int | None = None
    max_depth: int | None = None
    max_attempts: int | None = None
    max_mutations: int | None = None
    max_queries: int | None = None
    max_queue_depth: int | None = None
    max_in_flight: int | None = None
    max_elapsed_monotonic: CanonicalDecimal | None = None
    max_duplicate_redelivery_expansion: int | None = None
    max_failover_reconnect_replay_expansion: int | None = None
    max_amplification_per_cause: CanonicalDecimal | None = None

    def declares_every_bound(self) -> bool:
        """Whether every governed amplification axis carries a concrete injected bound."""
        return all(getattr(self, name) is not None for name in type(self).model_fields)


class ObservedAmplification(FrozenModel):
    """The observed amplification counts for one root cause (§11 line 284-296)."""

    fan_out: int | None = None
    depth: int | None = None
    attempts: int | None = None
    mutations: int | None = None
    queries: int | None = None
    queue_depth: int | None = None
    in_flight: int | None = None
    elapsed_monotonic: CanonicalDecimal | None = None
    duplicate_redelivery_expansion: int | None = None
    failover_reconnect_replay_expansion: int | None = None
    amplification_per_cause: CanonicalDecimal | None = None
    duplicate_event_created_new_allowance: bool | None = None
    envelope_reset_on_duplicate: bool | None = None
    concurrent_consumers_share_one_envelope: bool | None = None


class ProtectiveFlowReserveClaim(FrozenModel):
    """An exclusive protective flow reserve pre-commitment (§5.9 line 143-145; §16)."""

    dimension_id: str | None = None
    scope: ActionFlowScopeKind | None = None
    reserved_magnitude: CanonicalDecimal | None = None
    guarantee_level_token: str | None = None
    exclusive_capacity_present: bool | None = None
    high_priority_queue: bool | None = None


class PermitConsumptionState(FrozenModel):
    """The observed consumption state of one permit (§13 line 342)."""

    claimed: bool | None = None
    ambiguous: bool | None = None
    lost: bool | None = None
    conflicting: bool | None = None
    never_claimed_and_unreachable_proven: bool | None = None


class CurrentnessTrigger(FrozenModel):
    """One observed change evaluated for materiality (§19 line 413; §5.10 line 149)."""

    kind: MaterialChangeKind | str | None = None
    materiality_known: bool | None = None


class ActionFlowPolicy(IndependentIdArtifact):
    """An append-only, generation-immutable Action Flow Policy (§5.1 line 113; §8)."""

    _ID_FIELD: ClassVar[str] = "policy_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "policy_generation",
        "policy_version",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "policy_generation",
            "policy_version",
            "governed_dimensions",
            "governed_scopes",
            "governed_action_classes",
            "bundle_member_kind",
            "signer_identity",
            "approval_identity",
            "evidence_package_ref",
        }
    )

    policy_id: str | None = None

    policy_generation: int | None = None
    policy_version: str | None = None
    governed_dimensions: tuple[ActionFlowDimensionKind, ...] = ()
    governed_scopes: tuple[ActionFlowScopeKind, ...] = ()
    governed_action_classes: tuple[ActionClassKind, ...] = ()
    bundle_member_kind: str | None = None
    signer_identity: str | None = None
    approval_identity: str | None = None
    evidence_package_ref: str | None = None

    policy_order: int | None = None


class ActionFlowStateSnapshot(IndependentIdArtifact):
    """An append-only Action Flow State Snapshot (§5.3 line 119-121; §10; §12)."""

    _ID_FIELD: ClassVar[str] = "snapshot_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "snapshot_generation",
        "consistency_cut_identity",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "snapshot_generation",
            "consistency_cut_identity",
            "covered_scopes",
            "covered_dimension_ids",
            "scope_independence",
            "committed_usage",
            "hard_envelope_limit",
            "runtime_profile_limit",
            "committed_not_claimed",
            "claimed_without_proven_broker_byte",
            "broker_directed_writes_started",
            "acknowledged_or_unacknowledged",
            "queued_in_flight_throttled_rejected_timed_out_ambiguous",
            "reserved_exclusively_for_protection",
            "lineage_ref",
            "authority_effect",
        }
    )

    snapshot_id: str | None = None

    snapshot_generation: int | None = None
    consistency_cut_identity: str | None = None
    covered_scopes: tuple[ActionFlowScopeKind, ...] = ()
    covered_dimension_ids: tuple[str, ...] = ()
    scope_independence: tuple[ScopeIndependenceEvidence, ...] = ()
    committed_usage: ActionFlowVector = ActionFlowVector()
    hard_envelope_limit: ActionFlowVector = ActionFlowVector()
    runtime_profile_limit: ActionFlowVector = ActionFlowVector()
    committed_not_claimed: ActionFlowVector = ActionFlowVector()
    claimed_without_proven_broker_byte: ActionFlowVector = ActionFlowVector()
    broker_directed_writes_started: ActionFlowVector = ActionFlowVector()
    acknowledged_or_unacknowledged: ActionFlowVector = ActionFlowVector()
    queued_in_flight_throttled_rejected_timed_out_ambiguous: ActionFlowVector = (
        ActionFlowVector()
    )
    reserved_exclusively_for_protection: ActionFlowVector = ActionFlowVector()
    lineage_ref: str | None = None
    authority_effect: ActionFlowGovernorEffect = ActionFlowGovernorEffect()

    snapshot_order: int | None = None

    def covers(self, scope: ActionFlowScopeKind) -> bool:
        """Whether ``scope`` is among the snapshot's covered scopes (pure lookup)."""
        return scope in self.covered_scopes

    def independence_for(
        self, scope: ActionFlowScopeKind
    ) -> ScopeIndependenceEvidence | None:
        """The independence evidence for ``scope``, or ``None`` when absent (§10:278)."""
        for evidence in self.scope_independence:
            if evidence.scope is scope:
                return evidence
        return None


class ActionFlowDecision(IndependentIdArtifact):
    """An append-only, forward-only Action Flow Decision (§5.4 line 123-125; §13)."""

    _ID_FIELD: ClassVar[str] = "decision_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "decision_generation",
        "result",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "decision_generation",
            "result",
            "policy_digest",
            "policy_generation",
            "snapshot_digest",
            "cause_digest",
            "lineage_digest",
            "command_identity",
            "command_digest",
            "action_class",
            "applicable_action_flow_scopes",
            "action_flow_vector",
            "effective_limit",
            "amplification_envelope_digest",
            "protective_classification_digest",
            "authority_effect",
        }
    )

    decision_id: str | None = None

    decision_generation: int | None = None
    result: ActionFlowResult | None = None
    policy_digest: str | None = None
    policy_generation: int | None = None
    snapshot_digest: str | None = None
    cause_digest: str | None = None
    lineage_digest: str | None = None
    command_identity: str | None = None
    command_digest: str | None = None
    action_class: ActionClassKind | None = None
    applicable_action_flow_scopes: tuple[str, ...] = ()
    action_flow_vector: ActionFlowVector = ActionFlowVector()
    effective_limit: ActionFlowVector = ActionFlowVector()
    amplification_envelope_digest: str | None = None
    protective_classification_digest: str | None = None
    authority_effect: ActionFlowGovernorEffect = ActionFlowGovernorEffect()

    decision_order: int | None = None

    @property
    def issued_result(self) -> ActionFlowResult:
        """The ISSUED-only covered ``result``, narrowed to a concrete member (§5.4; §3.2)."""
        result = self.result
        if result is None:
            raise ArtifactIntegrityError(
                "ActionFlowDecision.issued_result called on a DRAFT (or otherwise "
                "result-less) decision — this accessor is ISSUED-only; call it "
                "only past .issue()/§3.2 completeness, never on a DRAFT instance"
            )
        return result


class ActionFlowPermit(IndependentIdArtifact):
    """An append-only, single-use Action Flow Permit (§5.5 line 127-129; §13 line 332-342)."""

    _ID_FIELD: ClassVar[str] = "permit_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "permit_generation",
        "command_identity",
        "claim_nonce",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "permit_generation",
            "rcl_commitment_ref",
            "writer_epoch",
            "revision",
            "command_identity",
            "policy_digest",
            "policy_generation",
            "snapshot_digest",
            "decision_digest",
            "cause_digest",
            "lineage_digest",
            "resource_vector",
            "ordinary_or_protective_dimension_mark",
            "protective_lease_proof",
            "reserve_proof",
            "consumer_identity",
            "claim_nonce",
            "single_use",
            "issue_anchor",
            "max_age_ms",
            "invalidation_generation",
            "economic_capacity_commitment_ref",
            "authority_effect",
        }
    )

    permit_id: str | None = None

    permit_generation: int | None = None
    rcl_commitment_ref: str | None = None
    writer_epoch: int | None = None
    revision: int | None = None
    command_identity: str | None = None
    policy_digest: str | None = None
    policy_generation: int | None = None
    snapshot_digest: str | None = None
    decision_digest: str | None = None
    cause_digest: str | None = None
    lineage_digest: str | None = None
    resource_vector: ActionFlowVector = ActionFlowVector()
    ordinary_or_protective_dimension_mark: str | None = None
    protective_lease_proof: str | None = None
    reserve_proof: str | None = None
    consumer_identity: str | None = None
    claim_nonce: str | None = None
    single_use: bool = True
    issue_anchor: str | None = None
    max_age_ms: int | None = None
    invalidation_generation: int | None = None
    economic_capacity_commitment_ref: str | None = None
    authority_effect: ActionFlowGovernorEffect = ActionFlowGovernorEffect()

    permit_order: int | None = None
