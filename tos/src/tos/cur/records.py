"""cur digest-bound artifacts — the four currentness ledger citizens (design #23 §2)."""

from __future__ import annotations

from typing import ClassVar

from tos.cur._base import AllFalseCurrentnessAuthority, IndependentIdArtifact
from tos.cur.state import (
    CurrentnessDimension,
    CurrentnessRevision,
    EgressProofCoordinateSet,
    TrialClaims,
)
from tos.cur.vocabulary import DimensionKey, ProofResult

__all__ = [
    "SafetyCurrentnessVector",
    "EgressCurrentnessProof",
    "RestrictiveFenceRecord",
    "CurrentnessPolicy",
    "AllFalseCurrentnessAuthority",
]


class CurrentnessPolicy(IndependentIdArtifact):
    """The governed Currentness Policy content model (ADR-002-024 §5.1/§8; design #23 §2.4)."""

    _ID_FIELD: ClassVar[str] = "policy_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "policy_id",
        "policy_generation",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "policy_generation",
            "policy_digest",
            "required_dimensions",
            "compatibility_manifest_digest",
            "authority_effect",
        }
    )

    policy_id: str | None = None
    policy_generation: int | None = None
    policy_digest: str | None = None
    required_dimensions: frozenset[DimensionKey] = frozenset()
    compatibility_manifest_digest: str | None = None
    authority_effect: AllFalseCurrentnessAuthority = AllFalseCurrentnessAuthority()


class SafetyCurrentnessVector(IndependentIdArtifact):
    """The complete action-scoped Safety Currentness Vector (ADR-002-024 §9; design #23 §2.4)."""

    _ID_FIELD: ClassVar[str] = "vector_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "vector_id",
        "currentness_revision",
        "policy_id",
        "policy_generation",
        "vector_digest",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "currentness_revision",
            "vector_digest",
            "policy_id",
            "policy_generation",
            "policy_digest",
            "compatibility_manifest_digest",
            "environment",
            "safety_cell",
            "capacity_domain",
            "account",
            "portfolio",
            "strategy",
            "venue",
            "session",
            "instrument",
            "action_class",
            "route_scope",
            "dimensions",
            "trial_claims",
            "authority_effect",
        }
    )

    vector_id: str | None = None
    currentness_revision: CurrentnessRevision | None = None
    vector_digest: str | None = None
    policy_id: str | None = None
    policy_generation: int | None = None
    policy_digest: str | None = None
    compatibility_manifest_digest: str | None = None

    environment: str | None = None
    safety_cell: str | None = None
    capacity_domain: str | None = None
    account: str | None = None
    portfolio: str | None = None
    strategy: str | None = None
    venue: str | None = None
    session: str | None = None
    instrument: str | None = None
    action_class: str | None = None
    route_scope: str | None = None

    dimensions: tuple[CurrentnessDimension, ...] = ()
    trial_claims: TrialClaims | None = None
    authority_effect: AllFalseCurrentnessAuthority = AllFalseCurrentnessAuthority()


class EgressCurrentnessProof(IndependentIdArtifact):
    """A single-use Egress Currentness Proof conformance fact (ADR-002-024 §12; design #23 §2.4)."""

    _ID_FIELD: ClassVar[str] = "proof_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "proof_id",
        "nonce",
        "vector_id",
        "vector_digest",
        "committed_revision",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "nonce",
            "issue_revision",
            "expiry_evidence",
            "vector_id",
            "vector_digest",
            "committed_revision",
            "bound_generations",
            "restrictive_floors",
            "capability_claim_command",
            "claim_committed_result",
            "send_started_revision",
            "max_claim_to_send_bound_ms",
            "result",
            "trial_claims",
            "authority_effect",
        }
    )

    proof_id: str | None = None
    nonce: str | None = None
    single_use_consumed: bool | None = None
    issue_revision: CurrentnessRevision | None = None
    expiry_evidence: str | None = None
    is_expired: bool | None = None

    vector_id: str | None = None
    vector_digest: str | None = None
    committed_revision: CurrentnessRevision | None = None
    bound_generations: tuple[int, ...] = ()
    restrictive_floors: tuple[int, ...] = ()
    egress_coordinates: EgressProofCoordinateSet = EgressProofCoordinateSet()
    trial_claims: TrialClaims | None = None

    capability_claim_command: str | None = None
    claim_committed_result: str | None = None
    send_started_revision: CurrentnessRevision | None = None
    max_claim_to_send_bound_ms: int | None = None

    result: ProofResult | None = None
    authority_effect: AllFalseCurrentnessAuthority = AllFalseCurrentnessAuthority()


class RestrictiveFenceRecord(IndependentIdArtifact):
    """One monotonic restrictive-floor advance (ADR-002-024 §5.5/§11; design #23 §2.4)."""

    _ID_FIELD: ClassVar[str] = "fence_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "fence_id",
        "owner_identity",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "owner_identity",
            "affected_scope",
            "predecessor_floor",
            "advanced_floor",
            "terminal_denial",
            "fence_digest",
            "authority_effect",
        }
    )

    fence_id: str | None = None
    owner_identity: str | None = None
    affected_scope: frozenset[str] = frozenset()
    predecessor_floor: int | None = None
    advanced_floor: int | None = None
    terminal_denial: bool | None = None
    fence_digest: str | None = None
    authority_effect: AllFalseCurrentnessAuthority = AllFalseCurrentnessAuthority()
