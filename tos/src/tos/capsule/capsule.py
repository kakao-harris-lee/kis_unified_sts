"""Decision Context Capsule artifact (design §2.7).

Models ``DECISION-CONTEXT-CAPSULE-template.yaml`` (83 lines), classifying fields
into three layers (design §2.7):

* **Layer-0** — identity outputs, self-excluded from the digest (design §3.2):
  ``capsule_id``, ``canonical_digest``, ``status`` (+ the ``canonicalization_version``
  meta envelope).
* **Layer-1** — context identity, digest-covered (design §2.7 / §3.3): every
  field ADR §12 (line 317-326) enumerates.
* **Layer-2** — downstream back-references, self-excluded and **not populated in
  Phase 1** (design §2.7/§3.2/§4.3): ``venue_constraint_policy``,
  ``venue_constraint_snapshot``, ``order_admissibility_decision``, ``bindings``.
  They are declared (schema slots) but left ``None``; excluding them from the
  digest breaks the §4.3 circular-embedding at the source.

The layered issuance (design §4.3): the snapshot digest is computed first and
embedded via ``critical_input_snapshot`` (a one-way snapshot -> capsule DAG,
design §3.3), then the capsule digest/id is fixed without any downstream
dependency. Layer-2 authoritative back-references are Phase B (out of scope).

``authority.*`` is forced ``false`` (design §4.4). Pure module.
"""

from __future__ import annotations

from typing import ClassVar

from tos.capsule._base import (
    CapsuleAuthority,
    DigestBoundArtifact,
    FrozenModel,
    PolicyRef,
)

_CAPSULE_ARTIFACT_TYPE = "DECISION_CONTEXT_CAPSULE"
_CAPSULE_SCHEMA_VERSION = "1.0-DRAFT"
_CAPSULE_ID_PREFIX = "dcc"


class SnapshotRef(FrozenModel):
    """Content-addressed reference to a Critical Input Snapshot (template 12-14).

    The design §4.2 recompute path: the ``canonical_digest`` reaches the grounded
    observations / field evaluations; approvers follow this embedded reference
    rather than bypassing the capsule.
    """

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
    """Proposer-asserted safety facts (template lines 34-43).

    Neutral scalars only (design §0.3, §2.7 broker-agnostic). These are the
    *claims* compared against the snapshot-derived facts in approval (design
    §4.2 step 4); ``session_and_tradability`` is a Layer-1 fact (covered), so
    venue facts themselves are part of capsule identity (design §2.7 note).
    """

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
    """Independent-validation recompute surface (template lines 53-58).

    Exposes what must be independently recomputed and the common-mode
    dependencies that collapse corroboration independence (design §4.2, §5.2).
    """

    required: bool = True
    required_facts: tuple[str, ...] = ()
    approved_paths: tuple[str, ...] = ()
    common_mode_dependencies: tuple[str, ...] = ()
    residual_risk_ids: tuple[str, ...] = ()


class CapsuleValidity(FrozenModel):
    """Capsule validity block (template lines 59-65).

    ``issued_at`` is the capsule *wrap* time and is **not** the Validity Window
    anchor (design §6.2 — the anchor is the observation ``source_event_time``).
    """

    issued_at: int | None = None
    consumer_receipt_anchor: str | None = None
    maximum_age_ms: int | None = None
    expires_at: int | None = None
    invalidation_generation: int | None = None
    invalidation_conditions: tuple[str, ...] = ()


# --- Layer-2 downstream reference schemas (declared, unpopulated in Phase 1) ---


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
    """Layer-2 downstream binding identifiers (template lines 66-74).

    Forward references to downstream chain artifacts; Phase B authoritative
    binding is out of scope (design §4.3), so these stay ``None`` in Phase 1.
    """

    proposal_id: str | None = None
    approval_request_id: str | None = None
    intent_id: str | None = None
    capacity_request_id: str | None = None
    live_authorization_id: str | None = None
    transmission_capability_id: str | None = None
    commit_proof_id: str | None = None
    egress_request_digest: str | None = None


class DecisionContextCapsule(DigestBoundArtifact):
    """Immutable Decision Context Capsule (design §2.7).

    Content-addressed: ``capsule_id = f(canonical_digest)`` and the digest covers
    the Layer-1 set only; Layer-0 identity and Layer-2 downstream references are
    excluded (design §3.2). Construction verifies both invariants (design §4.1),
    so mutate / union / partial-refresh / digest-substitution are unconstructable
    (CII-EV-007 core). Use :meth:`issue` to construct an issued capsule.
    """

    _ID_FIELD: ClassVar[str] = "capsule_id"
    _ID_PREFIX: ClassVar[str] = _CAPSULE_ID_PREFIX
    # Safety-load-bearing covered fields that MUST be concrete to issue (design
    # §3.2). Derived from the ``DECISION-CONTEXT-CAPSULE-template.yaml`` markers:
    # every path below is ``TBD`` (must-fill) in the template, whereas fields left
    # ``null`` there (e.g. ``validity.*``, most ``generation_vector.*``,
    # ``safety_critical_facts.expiration``) are optional and NOT required. Only the
    # decision-/economic-effect-determining identity, policy, snapshot reference,
    # scope, and core safety facts gate issuance.
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

    # ---- Layer-0 identity output (self-excluded, §3.2) ----
    # canonical_digest / status / canonicalization_version inherited from
    # DigestBoundArtifact (shared Layer-0 + meta envelope).
    capsule_id: str | None = None

    # ---- Layer-1 covered context identity (ADR §12 line 317-326) ----
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

    # ---- Layer-2 downstream back-references (self-excluded; Phase 1 = None) ----
    venue_constraint_policy: VenueConstraintPolicyRef | None = None
    venue_constraint_snapshot: VenueConstraintSnapshotRef | None = None
    order_admissibility_decision: OrderAdmissibilityDecisionRef | None = None
    bindings: Bindings | None = None
