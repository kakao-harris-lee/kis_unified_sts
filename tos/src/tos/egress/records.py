"""egress digest-bound artifacts — the five egress-boundary ledger citizens (design #22 §2)."""

from __future__ import annotations

from typing import ClassVar

from pydantic import model_validator

from tos.egress._base import (
    AllFalseEgressAuthority,
    ArtifactIntegrityError,
    IndependentIdArtifact,
)
from tos.egress.state import EgressPrincipal, SignerCoordinate, TrialClaims

__all__ = [
    "QuorumCommitCertificate",
    "EgressRequestRecord",
    "EgressGeneration",
    "ActiveEgressPrincipalSet",
    "ReplayObservation",
    "AllFalseEgressAuthority",
]


class QuorumCommitCertificate(IndependentIdArtifact):
    """The egress-boundary Quorum Commit Certificate (ADR-002-013 §11.1; design #22 §2.4)."""

    _ID_FIELD: ClassVar[str] = "qcc_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "cluster_identity",
        "capacity_domain",
        "membership_generation",
        "restore_generation",
        "writer_epoch",
        "committed_revision",
        "canonical_command_digest",
        "resulting_state_digest",
        "egress_generation",
        "active_egress_principal",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "cluster_identity",
            "capacity_domain",
            "safety_cell",
            "membership_generation",
            "restore_generation",
            "writer_epoch",
            "committed_revision",
            "parent_revision",
            "command_identity",
            "canonical_command_digest",
            "resulting_state_digest",
            "egress_generation",
            "active_egress_principal",
            "credential_generation",
            "broker_session_generation",
            "route_policy_generation",
            "endpoint_policy_generation",
            "trust_bundle_generation",
            "recovery_evidence_package_digest",
            "decision_context_capsule_digest",
            "venue_admissibility_decision_digest",
            "canonical_broker_command_digest",
            "order_conformance_proof_digest",
            "aggregate_risk_decision_digest",
            "action_flow_decision_digest",
            "action_flow_permit_id",
            "approval_consumption_record_digest",
            "egress_currentness_proof_id",
            "release_artifact_attestation_digest",
            "post_trade_obligation_generation",
            "signer_coordinates",
            "capability_nonce",
            "action_flow_permit_nonce",
            "is_restricted_live_trial",
            "trial_claims",
            "authority_effect",
        }
    )

    qcc_id: str | None = None

    cluster_identity: str | None = None
    capacity_domain: str | None = None
    safety_cell: str | None = None
    membership_generation: int | None = None
    restore_generation: int | None = None
    writer_epoch: int | None = None
    committed_revision: int | None = None
    parent_revision: int | None = None
    command_identity: str | None = None
    canonical_command_digest: str | None = None
    resulting_state_digest: str | None = None

    egress_generation: int | None = None
    active_egress_principal: str | None = None
    credential_generation: int | None = None
    broker_session_generation: int | None = None
    route_policy_generation: int | None = None
    endpoint_policy_generation: int | None = None
    trust_bundle_generation: int | None = None

    recovery_evidence_package_digest: str | None = None
    decision_context_capsule_digest: str | None = None
    venue_admissibility_decision_digest: str | None = None
    canonical_broker_command_digest: str | None = None
    order_conformance_proof_digest: str | None = None
    aggregate_risk_decision_digest: str | None = None
    action_flow_decision_digest: str | None = None
    action_flow_permit_id: str | None = None
    approval_consumption_record_digest: str | None = None
    egress_currentness_proof_id: str | None = None
    release_artifact_attestation_digest: str | None = None
    post_trade_obligation_generation: int | None = None

    signer_coordinates: tuple[SignerCoordinate, ...] = ()
    capability_nonce: str | None = None
    action_flow_permit_nonce: str | None = None

    is_restricted_live_trial: bool = False
    trial_claims: TrialClaims | None = None

    authority_effect: AllFalseEgressAuthority = AllFalseEgressAuthority()

    @model_validator(mode="after")
    def _trial_claim_completeness(self) -> QuorumCommitCertificate:
        """A positively-claimed restricted-live trial cannot carry an incomplete trial group (§2.3)."""
        if self.is_restricted_live_trial is True:
            if self.trial_claims is None or not self.trial_claims.is_complete():
                raise ArtifactIntegrityError(
                    "QuorumCommitCertificate declares is_restricted_live_trial=True but carries an "
                    "incomplete trial claim group — a positively-claimed restricted-live trial "
                    "requires the full §11.1 line 308 Trial Policy / Plan / Run / Promotion "
                    "Generation, remaining envelope, and abort generation to be concrete "
                    "(malformed-model self-defence, design #22 §2.3 / ADR-002-013 §11.1)."
                )
        return self


class EgressRequestRecord(IndependentIdArtifact):
    """The exact outbound egress request (ADR-002-013 §12 line 365-367; design #22 §2.4)."""

    _ID_FIELD: ClassVar[str] = "request_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "request_bytes_digest",
        "endpoint",
        "account",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "request_bytes_digest",
            "canonical_command_digest",
            "endpoint",
            "account",
            "environment",
            "action",
            "method",
            "side",
            "quantity_digest",
            "route_identity",
            "credential_generation",
            "broker_session_generation",
            "egress_generation",
            "active_principal",
            "authority_effect",
        }
    )

    request_id: str | None = None
    request_bytes_digest: str | None = None
    canonical_command_digest: str | None = None
    endpoint: str | None = None
    account: str | None = None
    environment: str | None = None
    action: str | None = None
    method: str | None = None
    side: str | None = None
    quantity_digest: str | None = None
    route_identity: str | None = None
    credential_generation: int | None = None
    broker_session_generation: int | None = None
    egress_generation: int | None = None
    active_principal: str | None = None
    authority_effect: AllFalseEgressAuthority = AllFalseEgressAuthority()


class EgressGeneration(IndependentIdArtifact):
    """One monotonic Egress Generation (ADR-002-013 §8; design #22 §2.4)."""

    _ID_FIELD: ClassVar[str] = "generation_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("egress_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "egress_generation",
            "authority_effect",
        }
    )

    generation_id: str | None = None
    egress_generation: int | None = None
    authority_effect: AllFalseEgressAuthority = AllFalseEgressAuthority()


class ActiveEgressPrincipalSet(IndependentIdArtifact):
    """The committed active egress principal set (ADR-002-013 §8 line 223-231; design #22 §2.4)."""

    _ID_FIELD: ClassVar[str] = "set_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("egress_generation",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "egress_generation",
            "active_principals",
            "authority_effect",
        }
    )

    set_id: str | None = None
    egress_generation: int | None = None
    active_principals: tuple[EgressPrincipal, ...] = ()
    authority_effect: AllFalseEgressAuthority = AllFalseEgressAuthority()


class ReplayObservation(IndependentIdArtifact):
    """One replay / substitution observation (ADR-002-013 §11/§12; design #22 §2.4/§5.5)."""

    _ID_FIELD: ClassVar[str] = "observation_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = ("subject_identity",)
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "subject_identity",
            "bound_request_digest",
            "principal",
            "endpoint",
            "egress_generation",
            "authority_effect",
        }
    )

    observation_id: str | None = None
    subject_identity: str | None = None
    bound_request_digest: str | None = None
    principal: str | None = None
    endpoint: str | None = None
    egress_generation: int | None = None
    authority_effect: AllFalseEgressAuthority = AllFalseEgressAuthority()
