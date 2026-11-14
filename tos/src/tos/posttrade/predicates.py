"""posttrade decision predicates — the 19 pure, fail-closed post-trade rules (§5)."""

from __future__ import annotations

from collections.abc import Mapping

from tos.canonical import CanonicalDecimal
from tos.posttrade.records import (
    ObligationLegScope,
    PostTradeFinalityProof,
)
from tos.posttrade.vocabulary import (
    FinalityDimensionKind,
    ObligationLegDirection,
)

__all__ = [
    "finality_dimensions_orthogonal",
    "finality_proof_class_specific",
    "finality_proof_current",
    "finality_proof_non_transferable",
    "obligation_leg_set_complete",
]


def _is_present_non_negative(magnitude: CanonicalDecimal | None) -> bool:
    """Whether a magnitude is present, finite, and non-negative (fail-closed helper)."""
    if magnitude is None:
        return False
    if not magnitude.is_finite():
        return False
    return magnitude >= 0


def _scope_fully_specified(scope: ObligationLegScope | None) -> bool:
    """Whether every one of the six §11 line 328 scope components is concrete."""
    if scope is None:
        return False
    if scope.leg is None or scope.finality_class is None:
        return False
    return all(
        bool(component)
        for component in (
            scope.account,
            scope.currency,
            scope.value_date,
            scope.source_revision,
        )
    )


def finality_dimensions_orthogonal(
    claimed_final_dimension: FinalityDimensionKind | None,
    dimension_proof_present: Mapping[FinalityDimensionKind, bool | None],
) -> bool:
    """Whether the claimed finality dimension rests on **its own** proof (PTF-INV-002)."""
    if claimed_final_dimension is None or not dimension_proof_present:
        return False
    return dimension_proof_present.get(claimed_final_dimension) is True


def obligation_leg_set_complete(
    required_legs: frozenset[ObligationLegDirection],
    present_legs: frozenset[ObligationLegDirection],
    leg_magnitudes: Mapping[ObligationLegDirection, CanonicalDecimal | None],
) -> bool:
    """Whether the obligation's exact leg set is complete (ADR §9; PTF-INV-001)."""
    if not required_legs:
        return False
    if not required_legs <= present_legs:
        return False
    return all(
        _is_present_non_negative(leg_magnitudes.get(leg)) for leg in required_legs
    )


def finality_proof_class_specific(proof: PostTradeFinalityProof | None) -> bool:
    """Whether a finality proof is exact and class-specific (ADR §11 line 320-326)."""
    if proof is None:
        return False
    if not _scope_fully_specified(proof.leg_scope):
        return False
    if not proof.obligation_ref or not proof.obligation_version:
        return False
    if proof.finality_class is None:
        return False
    scope = proof.leg_scope
    if scope is None or proof.finality_class is not scope.finality_class:
        return False
    if proof.bound_generation is None:
        return False
    if not _is_present_non_negative(proof.amount):
        return False
    return bool(proof.does_not_prove)


def finality_proof_non_transferable(
    proof: PostTradeFinalityProof | None,
    target_leg_scope: ObligationLegScope | None,
    *,
    target_obligation_ref: str | None = None,
    target_obligation_version: str | None = None,
) -> bool:
    """Whether a finality proof applies to exactly this leg scope (§11 line 328; §11 line 320)."""
    if proof is None or target_leg_scope is None:
        return False
    if not _scope_fully_specified(proof.leg_scope):
        return False
    if not _scope_fully_specified(target_leg_scope):
        return False
    if proof.leg_scope != target_leg_scope:
        return False
    if (
        target_obligation_ref is not None
        and proof.obligation_ref != target_obligation_ref
    ):
        return False
    return (
        target_obligation_version is None
        or proof.obligation_version == target_obligation_version
    )


def finality_proof_current(
    proof: PostTradeFinalityProof | None,
    active_generation: int | None,
) -> bool:
    """Whether a finality proof is still current (§11 line 330; PTF-INV-013)."""
    if proof is None or active_generation is None:
        return False
    if proof.bound_generation is None:
        return False
    return proof.bound_generation == active_generation
