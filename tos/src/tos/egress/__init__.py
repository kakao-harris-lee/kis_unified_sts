"""Egress Gateway, Credential, Route, and Commit-Proof Security pure models + predicates (Phase 1, EV-L1)."""

from __future__ import annotations

from tos.egress._base import (
    AllFalseEgressAuthority,
    ArtifactIntegrityError,
    ArtifactStatus,
    CanonicalDecimal,
    IndependentIdArtifact,
    RecordPairKind,
    classify_record_pair,
)
from tos.egress.predicates import (
    capability_and_permit_single_use,
    credential_route_authority_disjoint,
    egress_generation_monotonic,
    evidence_receipt_is_not_quorum_proof,
    exact_binding_holds,
    monotonic_denial_no_revival,
    quorum_commit_certificate_structurally_complete,
    quorum_coordinates_current,
    quorum_threshold_structurally_met,
    replay_or_substitution_detected,
    stale_principal_structurally_rejected,
)
from tos.egress.records import (
    ActiveEgressPrincipalSet,
    EgressGeneration,
    EgressRequestRecord,
    QuorumCommitCertificate,
    ReplayObservation,
)
from tos.egress.state import (
    ClaimObservation,
    CommitProofCoordinates,
    CredentialRouteInventoryEntry,
    EgressCoordinateSet,
    EgressEvent,
    EgressPrincipal,
    SignerCoordinate,
    TrialClaims,
    generation_monotone,
)
from tos.egress.vocabulary import (
    CommitProofValidity,
    EgressAdmission,
    RestrictiveLatchState,
    SignerRole,
)

__all__ = [
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "CanonicalDecimal",
    "IndependentIdArtifact",
    "RecordPairKind",
    "classify_record_pair",
    "AllFalseEgressAuthority",
    "EgressAdmission",
    "CommitProofValidity",
    "RestrictiveLatchState",
    "SignerRole",
    "QuorumCommitCertificate",
    "EgressRequestRecord",
    "EgressGeneration",
    "ActiveEgressPrincipalSet",
    "ReplayObservation",
    "SignerCoordinate",
    "EgressCoordinateSet",
    "CredentialRouteInventoryEntry",
    "CommitProofCoordinates",
    "TrialClaims",
    "EgressPrincipal",
    "ClaimObservation",
    "EgressEvent",
    "generation_monotone",
    "quorum_commit_certificate_structurally_complete",
    "quorum_coordinates_current",
    "quorum_threshold_structurally_met",
    "evidence_receipt_is_not_quorum_proof",
    "replay_or_substitution_detected",
    "capability_and_permit_single_use",
    "exact_binding_holds",
    "credential_route_authority_disjoint",
    "egress_generation_monotonic",
    "stale_principal_structurally_rejected",
    "monotonic_denial_no_revival",
]
