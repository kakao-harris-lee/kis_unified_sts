"""cur currentness predicates (design #23 §5/§6/§6b) — pure, fail-closed."""

from __future__ import annotations

from collections.abc import Sequence

from tos.cur._base import AllFalseCurrentnessAuthority
from tos.cur.records import (
    CurrentnessPolicy,
    EgressCurrentnessProof,
    RestrictiveFenceRecord,
    SafetyCurrentnessVector,
)
from tos.cur.state import (
    CurrentnessDimension,
    DomainProof,
    OwnerSubmission,
    floor_strictly_advances,
)
from tos.cur.vocabulary import (
    MANDATED_DIMENSION_FLOOR,
    DimensionKey,
    ProofResult,
)

__all__ = [
    "vector_complete",
    "dimension_positively_established",
    "single_revision_consistent",
    "no_forbidden_placeholder",
    "policy_covers_mandated_dimensions",
    "all_floors_met",
    "restrictive_floor_reconciled",
    "conflicting_owner_restricts",
    "restrictive_union_scope",
    "fence_advances_floor",
    "proof_structurally_complete",
    "proof_admissible",
    "multi_domain_no_union",
    "parent_child_floor_monotone",
    "protective_label_not_authority",
    "expiry_denies_future_use_only",
    "unknown_preserves_capacity",
    "recovery_revives_nothing",
    "all_false_currentness_authority",
    "race_order_admissible",
    "broker_reachable_not_authority",
    "obligation_preserved",
]

_FORBIDDEN_PLACEHOLDERS: frozenset[str] = frozenset(
    {
        "latest",
        "LATEST",
        "*",
        "?",
        "null-as-current",
        "NULL_AS_CURRENT",
        "current",
        "CURRENT",
        "@current",
        "inherit",
        "fallback",
    }
)


def dimension_positively_established(dimension: CurrentnessDimension | None) -> bool:
    """Whether a vector dimension is present and positively established (§5.2; CUR-EV-001 substrate)."""
    if dimension is None:
        return False
    if dimension.positively_established is not True:
        return False
    return not (
        dimension.dimension_key is None
        or dimension.owner_identity is None
        or dimension.bound_generation is None
        or dimension.bound_digest is None
        or dimension.at_revision is None
    )


def single_revision_consistent(vector: SafetyCurrentnessVector | None) -> bool:
    """Whether every dimension sits at the vector's single Currentness Revision (§5.3; CUR-EV-001)."""
    if vector is None or vector.currentness_revision is None:
        return False
    for dimension in vector.dimensions:
        if (
            dimension.at_revision is None
            or dimension.at_revision != vector.currentness_revision
        ):
            return False
    return True


def no_forbidden_placeholder(vector: SafetyCurrentnessVector | None) -> bool:
    """Whether no dimension uses a forbidden placeholder / wildcard sentinel (§5.4; CUR-EV-001)."""
    if vector is None:
        return False
    for dimension in vector.dimensions:
        for value in (dimension.bound_digest, dimension.bound_generation):
            if isinstance(value, str) and value in _FORBIDDEN_PLACEHOLDERS:
                return False
    return True


def policy_covers_mandated_dimensions(
    policy: CurrentnessPolicy | None,
    mandated: frozenset[DimensionKey],
) -> bool:
    """Whether the policy declares at least every mandated dimension (§5.5; under-declaration seal)."""
    if policy is None:
        return False
    if not mandated:
        return False
    return mandated <= policy.required_dimensions


def vector_complete(
    vector: SafetyCurrentnessVector | None,
    policy: CurrentnessPolicy | None,
    mandated: frozenset[DimensionKey],
) -> bool:
    """The yolk: whether a Safety Currentness Vector is complete (§5.1; CUR-EV-001 substrate — NOT closed)."""
    if vector is None or policy is None:
        return False
    effective_mandated = MANDATED_DIMENSION_FLOOR | frozenset(mandated)
    if not policy.required_dimensions:
        return False
    if not vector.dimensions:
        return False
    if not policy_covers_mandated_dimensions(policy, effective_mandated):
        return False
    established_keys = {
        dimension.dimension_key
        for dimension in vector.dimensions
        if dimension_positively_established(dimension)
    }
    if not policy.required_dimensions <= established_keys:
        return False
    if not single_revision_consistent(vector):
        return False
    return no_forbidden_placeholder(vector)


def restrictive_floor_reconciled(floors: Sequence[int | None]) -> int | None:
    """Reconcile many floor entries for one dimension to the MAX (most restrictive) (§6.2; MAJOR-1)."""
    if not floors:
        return None
    if any(floor is None for floor in floors):
        return None
    return max(floor for floor in floors if floor is not None)


def all_floors_met(dimensions: Sequence[CurrentnessDimension]) -> bool:
    """Whether every dimension's bound generation meets its restrictive floor (§6.1; CUR-EV-002)."""
    if not dimensions:
        return False
    for dimension in dimensions:
        if dimension.bound_generation is None or dimension.restrictive_floor is None:
            return False
        if dimension.bound_generation < dimension.restrictive_floor:
            return False
    return True


def conflicting_owner_restricts(submissions: Sequence[OwnerSubmission]) -> bool:
    """Whether any owner submission forces a restrictive closure (§6.3; CUR-EV-002/007 substrate)."""
    for submission in submissions:
        if (
            submission.is_conflicting is not False
            or submission.is_fork is not False
            or submission.sequence_regression is not False
            or submission.missing_predecessor is not False
            or submission.unverifiable_scope is not False
        ):
            return True
    return False


def restrictive_union_scope(submissions: Sequence[OwnerSubmission]) -> frozenset[str]:
    """The restrictive closure over the UNION of the credible restrictive scopes (§6.3; MAJOR-1)."""
    scope: set[str] = set()
    for submission in submissions:
        if (
            submission.is_conflicting is not False
            or submission.is_fork is not False
            or submission.sequence_regression is not False
            or submission.missing_predecessor is not False
            or submission.unverifiable_scope is not False
        ):
            scope.update(submission.affected_scope)
    return frozenset(scope)


def fence_advances_floor(record: RestrictiveFenceRecord | None) -> bool:
    """Whether a fence monotonically advances its floor or is terminal (§6.4; CUR-EV-002/003 substrate)."""
    if record is None:
        return False
    if record.terminal_denial is True:
        return True
    return floor_strictly_advances(record.predecessor_floor, record.advanced_floor)


def proof_structurally_complete(proof: EgressCurrentnessProof | None) -> bool:
    """Whether an Egress Currentness Proof carries a structurally complete §12 claim set (§6.5)."""
    if proof is None:
        return False
    if proof.missing_required_fields():
        return False
    if not proof.bound_generations:
        return False
    if proof.egress_coordinates is None:
        return False
    return not (
        proof.capability_claim_command is None or proof.send_started_revision is None
    )


def proof_admissible(proof: EgressCurrentnessProof | None) -> bool:
    """Whether an Egress Currentness Proof is admissible for one send (§6.6; CUR-EV-004 substrate)."""
    if not proof_structurally_complete(proof):
        return False
    assert proof is not None
    if proof.result is not ProofResult.CURRENT:
        return False
    if proof.single_use_consumed is not False:
        return False
    if proof.is_expired is not False:
        return False
    return proof.egress_coordinates.local_latch_clear is True


def multi_domain_no_union(domain_proofs: Sequence[DomainProof]) -> bool:
    """Whether independent per-domain proofs are all CURRENT — never unioned (§6.7; CUR-EV-008)."""
    if not domain_proofs:
        return False
    for domain_proof in domain_proofs:
        if domain_proof.domain is None:
            return False
        if domain_proof.result is not ProofResult.CURRENT:
            return False
    return True


def parent_child_floor_monotone(
    child_generation: int | None,
    parent_floor: int | None,
) -> bool:
    """Whether a child generation is not stale against a restrictive parent floor (§6.8; CUR-EV-008)."""
    if child_generation is None or parent_floor is None:
        return False
    return child_generation >= parent_floor


def protective_label_not_authority(label: str | None = None) -> bool:
    """Whether a protective label can ever confer currentness authority (§6.9; CUR-EV-011 substrate)."""
    del label
    return False


def expiry_denies_future_use_only(is_expired: bool | None) -> bool:
    """Whether an expired proof denies future use while capacity stays intact (§6.10; CUR-EV-010)."""
    return is_expired is not False


def unknown_preserves_capacity(
    currentness_known: bool | None,
    worst_credible_capacity: int | None,
) -> int | None:
    """The worst-credible capacity obligation an UNKNOWN currentness preserves (§6.11; CUR-EV-010)."""
    if currentness_known is True:
        return None
    return worst_credible_capacity


def recovery_revives_nothing(
    is_recovery_event: bool | None,
    latch_clear: bool | None,
) -> bool:
    """Whether a recovery event may revive currentness or clear a latch (§6.12; CUR-EV-012 substrate)."""
    if is_recovery_event is True:
        return False
    return latch_clear is True


def all_false_currentness_authority(
    authority: AllFalseCurrentnessAuthority | None,
) -> bool:
    """Whether an authority block confers nothing — every flag ``False`` (§6.13; CUR-EV-009 substrate)."""
    if authority is None:
        return False
    return all(
        getattr(authority, name) is False for name in type(authority).model_fields
    )


def race_order_admissible(
    claim_before_fence: bool | None,
    fence_before_first_byte: bool | None,
) -> bool:
    """Thin race-order model: whether a claim/fence/first-byte order is admissible (§6b; CUR-EV-005)."""
    if claim_before_fence is not True:
        return False
    return fence_before_first_byte is False


def broker_reachable_not_authority(broker_reachable: bool | None = None) -> bool:
    """Whether broker reachability can substitute for authority under partition (§6b; CUR-EV-006)."""
    del broker_reachable
    return False


def obligation_preserved(
    obligation: int | None,
    reservation_state: str | None,
    *,
    capacity_consuming_states: frozenset[str],
    magnitude_unknown: bool,
) -> bool:
    """Whether an rcl reservation state still honors a preserved capacity obligation (§1.3)."""
    if magnitude_unknown:
        return False
    if obligation is None:
        return True
    if reservation_state is None:
        return False
    return reservation_state in capacity_consuming_states
