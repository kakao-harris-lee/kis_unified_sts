"""Decision Context Capsule artifact (design §2.7)."""

from __future__ import annotations

from typing import ClassVar

from tos.capsule._base import (
    CapsuleAuthority,
    FrozenModel,
    IdDerivedArtifact,
    PolicyRef,
)

_CAPSULE_ARTIFACT_TYPE = "DECISION_CONTEXT_CAPSULE"
_CAPSULE_SCHEMA_VERSION = "1.0-DRAFT"
_CAPSULE_ID_PREFIX = "dcc"


class SnapshotRef(FrozenModel):
    """Content-addressed reference to a Critical Input Snapshot (template 12-14)."""

    snapshot_id: str | None = None
    canonical_digest: str | None = None


class CapsuleScope(FrozenModel):
    """Capsule scope (template lines 26-33) — singular account/venue/instrument."""

    environment: str | None = None
    safety_cell: str | None = None
    account: str | None = None
    venue: str | None = None
    instrument: str | None = None
    decision_class: str | None = None
    requested_action_scope: str | None = None


class SafetyCriticalFacts(FrozenModel):
    """Proposer-asserted safety facts (template lines 34-43)."""

    account: str | None = None
    instrument: str | None = None
    direction: str | None = None
    quantity_basis: str | None = None
    unit: str | None = None
    price_and_order_constraints: tuple[str, ...] = ()
    exposure_effect: str | None = None
    session_and_tradability: str | None = None
    expiration: str | None = None


class GenerationVector(FrozenModel):
    """Governing-artifact generation vector (template lines 44-52)."""

    safety_configuration_generation: int | None = None
    broker_capability_profile_version: str | None = None
    time_health_generation: int | None = None
    recovery_generation: int | None = None
    authority_epoch: int | None = None
    deployment_generation: int | None = None
    identity_generation: int | None = None
    evidence_policy_generation: int | None = None


class IndependentValidation(FrozenModel):
    """Independent-validation recompute surface (template lines 53-58)."""

    required: bool = True
    required_facts: tuple[str, ...] = ()
    approved_paths: tuple[str, ...] = ()
    common_mode_dependencies: tuple[str, ...] = ()
    residual_risk_ids: tuple[str, ...] = ()


class CapsuleValidity(FrozenModel):
    """Capsule validity block (template lines 59-65)."""

    issued_at: int | None = None
    consumer_receipt_anchor: str | None = None
    maximum_age_ms: int | None = None
    expires_at: int | None = None
    invalidation_generation: int | None = None
    invalidation_conditions: tuple[str, ...] = ()


class VenueConstraintPolicyRef(FrozenModel):
    """Layer-2 venue-constraint-policy reference (template 15-18; ADR-002-019)."""

    policy_id: str | None = None
    policy_generation: int | None = None
    canonical_digest: str | None = None


class VenueConstraintSnapshotRef(FrozenModel):
    """Layer-2 venue-constraint-snapshot reference (template 19-22; ADR-002-019)."""

    snapshot_id: str | None = None
    constraint_generation: int | None = None
    canonical_digest: str | None = None


class OrderAdmissibilityDecisionRef(FrozenModel):
    """Layer-2 order-admissibility-decision reference (template 23-25)."""

    decision_id: str | None = None
    canonical_digest: str | None = None


class Bindings(FrozenModel):
    """Layer-2 downstream binding identifiers (template lines 66-74)."""

    proposal_id: str | None = None
    approval_request_id: str | None = None
    intent_id: str | None = None
    capacity_request_id: str | None = None
    live_authorization_id: str | None = None
    transmission_capability_id: str | None = None
    commit_proof_id: str | None = None
    egress_request_digest: str | None = None


class DecisionContextCapsule(IdDerivedArtifact):
    """Immutable Decision Context Capsule (design §2.7)."""

    _ID_FIELD: ClassVar[str] = "capsule_id"
    _ID_PREFIX: ClassVar[str] = _CAPSULE_ID_PREFIX
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "issuer_principal_id",
        "critical_input_policy.policy_id",
        "critical_input_policy.canonical_digest",
        "critical_input_snapshot.snapshot_id",
        "critical_input_snapshot.canonical_digest",
        "scope.environment",
        "scope.account",
        "scope.instrument",
        "scope.decision_class",
        "safety_critical_facts.account",
        "safety_critical_facts.instrument",
        "safety_critical_facts.direction",
        "safety_critical_facts.quantity_basis",
        "safety_critical_facts.unit",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "artifact_type",
            "schema_version",
            "issuer_principal_id",
            "critical_input_policy",
            "context_generation",
            "critical_input_snapshot",
            "scope",
            "safety_critical_facts",
            "generation_vector",
            "independent_validation",
            "validity",
            "authority",
        }
    )

    capsule_id: str | None = None

    artifact_type: str = _CAPSULE_ARTIFACT_TYPE
    schema_version: str = _CAPSULE_SCHEMA_VERSION
    issuer_principal_id: str | None = None
    critical_input_policy: PolicyRef = PolicyRef()
    context_generation: int | None = None
    critical_input_snapshot: SnapshotRef = SnapshotRef()
    scope: CapsuleScope = CapsuleScope()
    safety_critical_facts: SafetyCriticalFacts = SafetyCriticalFacts()
    generation_vector: GenerationVector = GenerationVector()
    independent_validation: IndependentValidation = IndependentValidation()
    validity: CapsuleValidity = CapsuleValidity()
    authority: CapsuleAuthority = CapsuleAuthority()

    venue_constraint_policy: VenueConstraintPolicyRef | None = None
    venue_constraint_snapshot: VenueConstraintSnapshotRef | None = None
    order_admissibility_decision: OrderAdmissibilityDecisionRef | None = None
    bindings: Bindings | None = None
