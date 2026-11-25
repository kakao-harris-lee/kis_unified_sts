"""egress injected inputs + value models + monotonic-generation ordering REUSE (design #22 §2.4/§3.2)."""

from __future__ import annotations

from typing import ClassVar

from tos.egress._base import FrozenModel
from tos.egress.vocabulary import SignerRole
from tos.ordering import Ordering, OrderingEvent, compare_order

__all__ = [
    "SignerCoordinate",
    "EgressCoordinateSet",
    "CredentialRouteInventoryEntry",
    "CommitProofCoordinates",
    "TrialClaims",
    "EgressPrincipal",
    "ClaimObservation",
    "EgressEvent",
    "generation_monotone",
]


class SignerCoordinate(FrozenModel):
    """One quorum signer coordinate (ADR-002-013 §11.1 line 325; design #22 §2.4)."""

    signer_identity: str | None = None
    signer_role: SignerRole | None = None
    eligible_verified: bool | None = None
    signature_verified: bool | None = None


class EgressCoordinateSet(FrozenModel):
    """The exact-binding egress coordinate set (ADR-002-013 §11.2 step 18 / §12; design #22 §2.4)."""

    endpoint: str | None = None
    account: str | None = None
    environment: str | None = None
    action: str | None = None
    method: str | None = None
    route_identity: str | None = None
    credential_generation: int | None = None
    broker_session_generation: int | None = None
    egress_generation: int | None = None
    active_principal: str | None = None

    COORDINATES: ClassVar[tuple[str, ...]] = (
        "endpoint",
        "account",
        "environment",
        "action",
        "method",
        "route_identity",
        "credential_generation",
        "broker_session_generation",
        "egress_generation",
        "active_principal",
    )


class CredentialRouteInventoryEntry(FrozenModel):
    """One credential-route inventory entry (ADR-002-013 §6/§9/§10; design #22 §2.4/§6.1)."""

    principal: str | None = None
    usable_credential: bool | None = None
    broker_route: bool | None = None
    inside_boundary: bool | None = None


class CommitProofCoordinates(FrozenModel):
    """The injected current committed commit-proof coordinates (design #22 §2.4/§5.2)."""

    cluster_identity: str | None = None
    capacity_domain: str | None = None
    membership_generation: int | None = None
    restore_generation: int | None = None
    writer_epoch: int | None = None
    committed_revision: int | None = None
    canonical_command_digest: str | None = None
    resulting_state_digest: str | None = None
    egress_generation: int | None = None
    credential_generation: int | None = None
    broker_session_generation: int | None = None
    route_policy_generation: int | None = None
    trust_bundle_generation: int | None = None

    COORDINATES: ClassVar[tuple[str, ...]] = (
        "cluster_identity",
        "capacity_domain",
        "membership_generation",
        "restore_generation",
        "writer_epoch",
        "committed_revision",
        "canonical_command_digest",
        "resulting_state_digest",
        "egress_generation",
        "credential_generation",
        "broker_session_generation",
        "route_policy_generation",
        "trust_bundle_generation",
    )


class TrialClaims(FrozenModel):
    """The conditional restricted-live trial claim group (ADR-002-013 §11.1 line 308; design #22 §2.4)."""

    trial_policy_generation: int | None = None
    trial_plan_generation: int | None = None
    trial_run_generation: int | None = None
    promotion_generation: int | None = None
    remaining_envelope: str | None = None
    abort_generation: int | None = None

    REQUIRED_SCALARS: ClassVar[tuple[str, ...]] = (
        "trial_policy_generation",
        "trial_plan_generation",
        "trial_run_generation",
        "promotion_generation",
        "remaining_envelope",
        "abort_generation",
    )

    def is_complete(self) -> bool:
        """Whether every conditional trial scalar is concrete (design #22 §2.3)."""
        return all(getattr(self, name) is not None for name in self.REQUIRED_SCALARS)


class EgressPrincipal(FrozenModel):
    """One active egress principal (ADR-002-013 §8 line 223-231; design #22 §2.4)."""

    workload_identity: str | None = None
    deployment_digest: str | None = None
    artifact_digest: str | None = None
    config_digest: str | None = None
    env_digest: str | None = None
    credential_generation: int | None = None
    broker_session_generation: int | None = None
    route_policy_generation: int | None = None
    trust_bundle_generation: int | None = None
    active: bool | None = None
    expired: bool | None = None


class ClaimObservation(FrozenModel):
    """One prior capability / permit nonce claim (ADR-002-013 §11.2 step 17; design #22 §2.4/§5.6)."""

    nonce: str | None = None
    principal: str | None = None
    request_digest: str | None = None


class EgressEvent(FrozenModel):
    """One injected egress state-machine event (ADR-002-013 §13; design #22 §2.4/§6b.3)."""

    event_kind: str | None = None
    restrictive: bool | None = None


def generation_monotone(earlier: OrderingEvent, later: OrderingEvent) -> bool:
    """Whether ``earlier`` strictly precedes ``later`` in append-only order (§3.2 / §4.5)."""
    return compare_order(earlier, later) is Ordering.BEFORE
