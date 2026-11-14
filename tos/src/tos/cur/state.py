"""cur injected inputs + value models + generation-order ordering REUSE (design #23 §2.1/§3.2)."""

from __future__ import annotations

from tos.cur._base import FrozenModel
from tos.cur.vocabulary import DimensionKey, ProofResult
from tos.ordering import Ordering, OrderingEvent, compare_order

__all__ = [
    "CurrentnessRevision",
    "CurrentnessDimension",
    "EgressProofCoordinateSet",
    "TrialClaims",
    "OwnerSubmission",
    "DomainProof",
    "floor_strictly_advances",
]


class CurrentnessRevision(FrozenModel):
    """One committed Currentness Revision — an ordering identity (ADR-002-024 §5.4; design #23 §2.1)."""

    revision_id: str | None = None
    commit_index: int | None = None


class CurrentnessDimension(FrozenModel):
    """One Safety Currentness Vector dimension coordinate (ADR-002-024 §9; design #23 §2.1)."""

    dimension_key: DimensionKey | None = None
    owner_identity: str | None = None
    bound_generation: int | None = None
    bound_digest: str | None = None
    restrictive_floor: int | None = None
    positively_established: bool | None = None
    at_revision: CurrentnessRevision | None = None


class EgressProofCoordinateSet(FrozenModel):
    """The injected egress-scope coordinate mirror (ADR-002-024 §12 line 310-311; design #23 §2.1)."""

    principal: str | None = None
    deployment: str | None = None
    credential: str | None = None
    signer: str | None = None
    route: str | None = None
    endpoint: str | None = None
    broker_session: str | None = None
    local_latch_clear: bool | None = None


class TrialClaims(FrozenModel):
    """The conditional restricted-live trial claim group (ADR-002-024 §9:258 / §12; design #23 §2.1)."""

    trial_policy_generation: int | None = None
    trial_plan_generation: int | None = None
    trial_run_generation: int | None = None
    promotion_generation: int | None = None
    remaining_envelope: str | None = None
    abort_generation: int | None = None


class OwnerSubmission(FrozenModel):
    """One owner restriction submission (ADR-002-024 §10 line 280; design #23 §2.1/§6.3)."""

    owner_identity: str | None = None
    affected_scope: tuple[str, ...] = ()
    is_conflicting: bool | None = None
    is_fork: bool | None = None
    sequence_regression: bool | None = None
    missing_predecessor: bool | None = None
    unverifiable_scope: bool | None = None


class DomainProof(FrozenModel):
    """One independent per-domain currentness proof result (ADR-002-024 §16; design #23 §2.1/§6.7)."""

    domain: str | None = None
    result: ProofResult | None = None


def floor_strictly_advances(predecessor: int | None, advanced: int | None) -> bool:
    """Whether ``advanced`` strictly exceeds ``predecessor`` in append-only order (§3.2/§6.4)."""
    if predecessor is None or advanced is None:
        return False
    return (
        compare_order(
            OrderingEvent(quorum_commit_index=predecessor),
            OrderingEvent(quorum_commit_index=advanced),
        )
        is Ordering.BEFORE
    )
