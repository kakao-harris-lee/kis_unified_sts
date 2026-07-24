"""Safety Authority ledger-citizen records (ADR-002-003 §9, §10, §14.2, §19).

Every record is a digest-bound :class:`~tos.authority._base.IndependentIdArtifact`
with an independent, service-assigned identity (``id != f(digest)``, §3.1) so an
append-only ledger can represent and detect a same-id / different-content forgery /
replay (§18.3 line 701-703; §9.3) as a ``classify_record_pair`` CRITICAL_CONFLICT.
There is **no** update / delete / mutate method on any record — a lifecycle change is
expressed by appending a new record (append-only, §2.0/§19). ``covered`` is the
Layer-1 digest preimage; identity outputs, ``status``, and meta are self-excluded
(§3.3). ``_REQUIRED_COVERED`` lists **structural identity / scope / version / epoch**
fields only — numeric bounds are excluded so a capability is ISSUED-reachable under
Phase-1 null profile bounds (§2.2); a missing numeric claim fails closed at the
consuming validity predicate instead (§5.2 numeric-claim precondition).

The lease record's local monotonic anchor REUSEs ``tos.time.TimeContinuityIdentity``
(the ratified first sibling→sibling edge — design §0.4b/§3.4); RCL capacity artifacts
are referenced only as scalars (``referenced_capacity_lease_id`` etc. — ``tos.rcl`` is
NOT imported, §0.3/§3.3).

Spec terms = code terms (boundary design #1 §2.4).

Pure module: ``pydantic`` + stdlib + ``tos.authority`` + ``tos.time`` only; no
``shared.*``, no ``tos.rcl`` / ``tos.capsule`` / ``tos.evidence`` (design §0.3).
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import model_validator

from tos.authority._base import (
    ArtifactIntegrityError,
    ArtifactStatus,
    AuthorityEffect,
    IndependentIdArtifact,
)
from tos.authority.state import CurrentnessWitness
from tos.authority.vocabulary import AuthorityTransitionReason, CapabilityType
from tos.time import TimeContinuityIdentity


class SafetyAuthorityCapability(IndependentIdArtifact):
    """Safety Authority Capability (ADR-002-003 §9 line 311-360).

    ``capability_id`` is independent of ``canonical_digest`` (§3.1) so a same-id /
    different-bytes capability is a detectable Critical conflict (§18.3 replay / §9.3
    single-use forgery). The ``nonce`` is covered (single-use / replay identity, §9.3).
    ``authority_effect`` is all-false: holding or signing a capability is **not**
    current authority (§1 line 17; §5.3 line 121 "a signature alone is not Current
    Epoch Proof"). The numeric claims (``maximum_quantity`` /
    ``maximum_risk_vector_effect_or_reservation_identity``) are covered but NOT required
    for ISSUED (§2.2) — they are enforced fail-closed at consumption by
    ``permissive_capability_valid`` (§5.2 numeric-claim precondition). ``integrity_evidence``
    carries structure only; MAC / signature verification is deferred (§9.2 (f);
    SA-EV-012 not-Phase-1).
    """

    _ID_FIELD: ClassVar[str] = "capability_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "capability_type",
        "issuer_identity",
        "authority_domain",
        "safety_authority_epoch",
        "subject_service_identity",
        "environment_and_mode",
        "account_scope",
        "permitted_action_class",
        "issue_sequence",
        "hard_safety_envelope_version",
        "runtime_safety_profile_version",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "capability_type",
            "issuer_identity",
            "authority_domain",
            "safety_authority_epoch",
            "subject_service_identity",
            "environment_and_mode",
            "account_scope",
            "instrument_or_class_scope",
            "permitted_action_class",
            "maximum_quantity",
            "maximum_risk_vector_effect_or_reservation_identity",
            "hard_safety_envelope_version",
            "runtime_safety_profile_version",
            "issue_sequence",
            "validity_rule",
            "use_semantics",
            "parent_authorization_or_protective_lease_identity",
            "integrity_evidence",
            "nonce",
            "authority_effect",
        }
    )

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    capability_id: str | None = None

    # ---- Layer-1 covered claims (ADR-002-003 §9.1 line 313-335) ----
    capability_type: CapabilityType | None = None
    issuer_identity: str | None = None
    authority_domain: str | None = None
    safety_authority_epoch: int | None = None
    subject_service_identity: str | None = None
    environment_and_mode: str | None = None
    account_scope: str | None = None
    instrument_or_class_scope: str | None = None
    permitted_action_class: str | None = None
    maximum_quantity: int | None = None
    maximum_risk_vector_effect_or_reservation_identity: str | None = None
    hard_safety_envelope_version: str | None = None
    runtime_safety_profile_version: str | None = None
    issue_sequence: int | None = None
    validity_rule: str | None = None
    use_semantics: str | None = None
    parent_authorization_or_protective_lease_identity: str | None = None
    integrity_evidence: str | None = None
    nonce: str | None = None
    authority_effect: AuthorityEffect = AuthorityEffect()


class AuthorityEpochTransitionRecord(IndependentIdArtifact):
    """Authority Epoch Transition Record (ADR-002-003 §10 line 370-408; §19 line 711-729).

    An element of the append-only audit sequence. Its covered content is the §19 audit
    field set. The epoch is **strictly increasing** (``new_epoch > old_epoch``, §5.2
    line 113; §10.5 "reuse, reset, or wraparound is prohibited") — enforced at
    construction, so a record decreasing / reusing an epoch is unconstructable. The
    model provides **no** operation reconstructing an epoch from an event-stream maximum
    (§10.4 line 402-404 constructive absence). ``capability_digest`` /
    ``capability_type`` are the §19 "capability digest and type" audit pair.
    """

    _ID_FIELD: ClassVar[str] = "transition_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "authority_domain",
        "old_epoch",
        "new_epoch",
        "leader_identity",
        "transition_reason",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "authority_domain",
            "old_epoch",
            "new_epoch",
            "leader_identity",
            "transition_reason",
            "currentness_witness",
            "capability_digest",
            "capability_type",
            "subject_identity",
            "scope",
            "issue_and_validation_evidence",
            "fencing_result",
            "egress_acceptance_or_rejection",
            "safer_state_precedence_applied",
            "operator_approvals",
            "rearm_prerequisites_and_outcome",
            "local_monotonic_anchor_evidence",
        }
    )

    transition_id: str | None = None

    authority_domain: str | None = None
    old_epoch: int | None = None
    new_epoch: int | None = None
    leader_identity: str | None = None
    transition_reason: AuthorityTransitionReason | None = None
    currentness_witness: CurrentnessWitness = CurrentnessWitness()
    capability_digest: str | None = None
    capability_type: CapabilityType | None = None
    subject_identity: str | None = None
    scope: str | None = None
    issue_and_validation_evidence: str | None = None
    fencing_result: str | None = None
    egress_acceptance_or_rejection: str | None = None
    safer_state_precedence_applied: str | None = None
    operator_approvals: tuple[str, ...] = ()
    rearm_prerequisites_and_outcome: str | None = None
    local_monotonic_anchor_evidence: str | None = None

    @model_validator(mode="after")
    def _epoch_strictly_increasing(self) -> AuthorityEpochTransitionRecord:
        """Reject a non-increasing epoch transition (§5.2/§10.5 — no reuse/reset/wraparound)."""
        if self.status == ArtifactStatus.DRAFT:
            return self
        if self.old_epoch is None or self.new_epoch is None:
            return self  # required-covered guard handles missing epochs at issuance
        if self.new_epoch <= self.old_epoch:
            raise ArtifactIntegrityError(
                f"epoch transition must strictly increase (old_epoch={self.old_epoch}, "
                f"new_epoch={self.new_epoch}) — epoch reuse/reset/wraparound is "
                "prohibited (ADR-002-003 §5.2/§10.5)"
            )
        return self


class DegradedLeaseOwnershipRecord(IndependentIdArtifact):
    """Degraded Lease Ownership Record (ADR-002-003 §14.2 line 545-556).

    The authority / ownership-side record the execution-side owner durably associates
    with a degraded protective lease on receipt — conceptually distinct from RCL's
    capacity-side ``ProtectiveLease`` (which it references only by scalar id / digest,
    ``tos.rcl`` not imported, §2.4). ``local_monotonic_anchor`` REUSEs
    ``tos.time.TimeContinuityIdentity`` (§3.4). The exclusivity coordinates are
    ``(exclusive_scope, referenced_capacity_lease_id)`` keyed by ``lease_ownership_id``
    (SA-INV-006, §6.1). ``approved_maximum_duration`` is a covered numeric bound but is
    NOT required for ISSUED (§2.2); ``drift_and_suspension_assumptions`` is a scalar
    reference to the approved-assumptions profile (the actual bounds are injected at the
    validity predicate, §8), not a hard-coded number.
    """

    _ID_FIELD: ClassVar[str] = "lease_ownership_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "receipt_process_identity",
        "host_or_runtime_identity",
        "safety_authority_epoch",
        "capability_digest",
        "exclusive_scope",
        "referenced_capacity_lease_id",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "receipt_process_identity",
            "host_or_runtime_identity",
            "local_monotonic_anchor",
            "approved_maximum_duration",
            "drift_and_suspension_assumptions",
            "safety_authority_epoch",
            "capability_digest",
            "exclusive_scope",
            "current_owner_identity",
            "referenced_capacity_lease_id",
            "referenced_protective_pool_identity",
        }
    )

    lease_ownership_id: str | None = None

    receipt_process_identity: str | None = None
    host_or_runtime_identity: str | None = None
    local_monotonic_anchor: TimeContinuityIdentity = TimeContinuityIdentity()
    approved_maximum_duration: int | None = None
    drift_and_suspension_assumptions: str | None = None
    safety_authority_epoch: int | None = None
    capability_digest: str | None = None
    exclusive_scope: str | None = None
    current_owner_identity: str | None = None
    referenced_capacity_lease_id: str | None = None
    referenced_protective_pool_identity: str | None = None
