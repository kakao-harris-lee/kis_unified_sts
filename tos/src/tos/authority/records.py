"""Safety Authority ledger-citizen records (ADR-002-003 §9, §10, §14.2, §19)."""

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
    """Safety Authority Capability (ADR-002-003 §9 line 311-360)."""

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

    capability_id: str | None = None

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
    """Authority Epoch Transition Record (ADR-002-003 §10 line 370-408; §19 line 711-729)."""

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
            return self
        if self.new_epoch <= self.old_epoch:
            raise ArtifactIntegrityError(
                f"epoch transition must strictly increase (old_epoch={self.old_epoch}, "
                f"new_epoch={self.new_epoch}) — epoch reuse/reset/wraparound is "
                "prohibited (ADR-002-003 §5.2/§10.5)"
            )
        return self

    @property
    def issued_old_epoch(self) -> int:
        """The ISSUED-only ``old_epoch``, narrowed to a concrete ``int`` (§3.2)."""
        if self.old_epoch is None:
            raise ArtifactIntegrityError(
                "AuthorityEpochTransitionRecord.issued_old_epoch called on a "
                "DRAFT (or otherwise epoch-less) record — this accessor is "
                "ISSUED-only; call it only past .issue()/§3.2 completeness, "
                "never on a DRAFT instance"
            )
        return self.old_epoch

    @property
    def issued_new_epoch(self) -> int:
        """The ISSUED-only ``new_epoch`` — see :attr:`issued_old_epoch`."""
        if self.new_epoch is None:
            raise ArtifactIntegrityError(
                "AuthorityEpochTransitionRecord.issued_new_epoch called on a "
                "DRAFT (or otherwise epoch-less) record — this accessor is "
                "ISSUED-only; call it only past .issue()/§3.2 completeness, "
                "never on a DRAFT instance"
            )
        return self.new_epoch


class DegradedLeaseOwnershipRecord(IndependentIdArtifact):
    """Degraded Lease Ownership Record (ADR-002-003 §14.2 line 545-556)."""

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
