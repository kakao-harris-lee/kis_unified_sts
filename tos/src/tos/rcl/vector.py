"""Capacity Vector + dimension descriptor + benefit proof (ADR-002-002 §6)."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from tos.canonical import CanonicalDecimal
from tos.rcl._base import FrozenModel

__all__ = [
    "CanonicalDecimal",
    "DimensionDescriptor",
    "CapacityComponent",
    "CapacityVector",
    "aggregate_usage",
    "effective_limit",
    "BenefitClaim",
    "BenefitProof",
]


class DimensionDescriptor(FrozenModel):
    """Per-dimension descriptor (ADR-002-002 §6.1 line 240-248)."""

    unit: str | None = None
    sign_convention: str | None = None
    aggregation_scope: str | None = None
    limit_source: str | None = None
    conservative_valuation_rule: str | None = None
    uncertainty_treatment: str | None = None
    evidence_freshness_requirement: str | None = None


class CapacityComponent(FrozenModel):
    """One dimension's magnitude within a Capacity Vector (ADR-002-002 §6.1)."""

    dimension_id: str | None = None
    magnitude: CanonicalDecimal | None = None
    unit: str | None = None
    scale: str | None = None
    descriptor: DimensionDescriptor = DimensionDescriptor()


class CapacityVector(FrozenModel):
    """A Capacity Vector over named dimensions (ADR-002-002 §6.1 line 218-248)."""

    components: tuple[CapacityComponent, ...] = ()

    def magnitude(self, dimension_id: str) -> Decimal | None:
        """Return the magnitude for ``dimension_id`` (``None`` if absent/UNKNOWN)."""
        for component in self.components:
            if component.dimension_id == dimension_id:
                return component.magnitude
        return None

    def declares(self, dimension_id: str) -> bool:
        """Whether ``dimension_id`` appears among the components at all."""
        return any(c.dimension_id == dimension_id for c in self.components)

    def dimension_ids(self) -> tuple[str, ...]:
        """The declared dimension ids, in component order (duplicates preserved)."""
        return tuple(
            c.dimension_id for c in self.components if c.dimension_id is not None
        )


def aggregate_usage(vectors: Sequence[CapacityVector]) -> CapacityVector:
    """Sum a sequence of Capacity Vectors dimension-wise (INV-001 aggregate usage)."""
    order: list[str] = []
    for vector in vectors:
        for dim in vector.dimension_ids():
            if dim not in order:
                order.append(dim)
    components: list[CapacityComponent] = []
    for dim in order:
        total: Decimal | None = Decimal(0)
        for vector in vectors:
            if not vector.declares(dim):
                continue
            magnitude = vector.magnitude(dim)
            if magnitude is None:
                total = None
                break
            total = total + magnitude  # type: ignore[operator]
        components.append(CapacityComponent(dimension_id=dim, magnitude=total))
    return CapacityVector(components=tuple(components))


def effective_limit(hard: CapacityVector, runtime: CapacityVector) -> CapacityVector:
    """Return ``EffectiveLimit[c] = min(Hard[c], Runtime[c])`` (INV-001 line 127-150)."""
    dims: list[str] = []
    for vector in (hard, runtime):
        for dim in vector.dimension_ids():
            if dim not in dims:
                dims.append(dim)
    components: list[CapacityComponent] = []
    for dim in dims:
        h = hard.magnitude(dim)
        r = runtime.magnitude(dim)
        limit = None if (h is None or r is None) else min(h, r)
        components.append(CapacityComponent(dimension_id=dim, magnitude=limit))
    return CapacityVector(components=tuple(components))


class BenefitClaim(FrozenModel):
    """A claimed netting / hedge / diversification / correlation benefit (§5.1/§6.3)."""

    kind: str | None = None
    reduction: CapacityVector = CapacityVector()


class BenefitProof(FrozenModel):
    """A positive proof token authorizing a benefit reduction (§5.1 rule 2, §6.5)."""

    broker_profile_proven: bool = False
    scope_proven: bool = False
    proof_reference: str | None = None

    def is_positive(self) -> bool:
        """Whether this is a positive proof token (both scope + profile proven)."""
        return self.broker_profile_proven and self.scope_proven
