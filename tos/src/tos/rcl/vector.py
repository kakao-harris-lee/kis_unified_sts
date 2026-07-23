"""Capacity Vector + dimension descriptor + benefit proof (ADR-002-002 §6).

Risk capacity is a **vector**, not one scalar notional (§6.1 line 220). Arithmetic
is integer / :class:`~decimal.Decimal` only — no float accumulation, no ``numpy``
(RCL design §0.3 closure minimisation). A missing / ``None`` dimension magnitude is
**UNKNOWN** and propagates conservatively (fail-closed at the consuming predicate,
§5.3); it is never silently treated as ``0``.

Pure module: ``pydantic`` + stdlib (``decimal``) + ``tos.rcl._base`` only; no
``shared.*`` (RCL design §0.3).
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Annotated

from pydantic import BeforeValidator

from tos.rcl._base import FrozenModel


def _normalize_decimal(value: object) -> object:
    """Collapse numerically-equal Decimals to one canonical form (canonical §3.1a).

    ``model_dump(mode="json")`` serializes a ``Decimal`` to a *string* before it
    reaches the reused canonicalizer, so the canonicalizer's own ``_num_token``
    magnitude normalization never runs on a covered Decimal field. Normalizing at
    validation time (``1.0`` == ``1.00``; ``100`` == ``1E+2`` -> one value; ``-0`` /
    ``0E±n`` -> ``0``) restores that property at the record-digest level for **every**
    covered Decimal field: numerically-equal values yield equal digests, distinct
    values differ. Not a canonicalizer redefinition — it feeds the reused
    canonicalizer a canonical Decimal, mirroring ``tos.canonical`` ``_num_token``.

    Non-numeric / ``None`` input is returned unchanged so pydantic's own validation
    (or the ``| None`` union branch) still applies.
    """
    if not isinstance(value, (Decimal, int, float, str)) or isinstance(value, bool):
        return value
    dec = value if isinstance(value, Decimal) else Decimal(str(value))
    dec = dec.normalize()
    return Decimal(0) if dec == 0 else dec


#: A covered ``Decimal`` field canonicalized (normalized) at validation time so
#: numerically-equal magnitudes / bounds share one digest (canonical §3.1a). Use
#: this — never a bare ``Decimal`` — for any covered Decimal field, so a future field
#: cannot silently reintroduce the "1.0 != 1.00 at the digest" gap.
CanonicalDecimal = Annotated[Decimal, BeforeValidator(_normalize_decimal)]


class DimensionDescriptor(FrozenModel):
    """Per-dimension descriptor (ADR-002-002 §6.1 line 240-248).

    Every capacity dimension SHALL have these (line 242-248). All optional at the
    model level (Phase-1 bounds are injected / may be null, §8); a consuming
    predicate fails closed on a missing magnitude, not on a missing descriptor.
    """

    unit: str | None = None
    sign_convention: str | None = None
    aggregation_scope: str | None = None
    limit_source: str | None = None
    conservative_valuation_rule: str | None = None
    uncertainty_treatment: str | None = None
    evidence_freshness_requirement: str | None = None


class CapacityComponent(FrozenModel):
    """One dimension's magnitude within a Capacity Vector (ADR-002-002 §6.1).

    ``magnitude`` is a :class:`~decimal.Decimal` (canonicalized by
    ``tos.canonical`` ``_num_token`` when the enclosing record is digest-bound) or
    ``None`` for an UNKNOWN / unbounded dimension (INV-006 — UNKNOWN consumes
    capacity, so a ``None`` magnitude fails the within-limit check, §5.3). The
    ``scale`` / ``unit`` metadata stay distinct string fields (never folded into the
    magnitude — canonical §3.4 safety-significant-distinction preservation).
    """

    dimension_id: str | None = None
    magnitude: CanonicalDecimal | None = None
    unit: str | None = None
    scale: str | None = None
    descriptor: DimensionDescriptor = DimensionDescriptor()


class CapacityVector(FrozenModel):
    """A Capacity Vector over named dimensions (ADR-002-002 §6.1 line 218-248).

    Order-significant tuple of :class:`CapacityComponent`. A dimension not declared
    is absent (contributes nothing); a declared dimension with ``magnitude=None`` is
    UNKNOWN (capacity-consuming, §5.3). Used both as an adverse-increment / usage
    vector and — via :func:`effective_limit` — as an Effective Limit vector.
    """

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
    """Sum a sequence of Capacity Vectors dimension-wise (INV-001 aggregate usage).

    For each declared dimension the magnitudes are summed. If **any** contributing
    magnitude on a declared dimension is ``None`` (UNKNOWN), the aggregate for that
    dimension is ``None`` (UNKNOWN propagates — fail-closed, §5.3; INV-006). A
    dimension not declared by a vector contributes nothing to that dimension. Pure
    integer / ``Decimal`` arithmetic; no float, no ``numpy``.

    Args:
        vectors: The Capacity Vectors to aggregate (e.g. committed reservations).

    Returns:
        The dimension-wise aggregate Capacity Vector.
    """
    # Deterministic dimension order: first-seen across the input sequence.
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
                total = None  # UNKNOWN propagates conservatively (INV-006)
                break
            total = total + magnitude  # type: ignore[operator]
        components.append(CapacityComponent(dimension_id=dim, magnitude=total))
    return CapacityVector(components=tuple(components))


def effective_limit(hard: CapacityVector, runtime: CapacityVector) -> CapacityVector:
    """Return ``EffectiveLimit[c] = min(Hard[c], Runtime[c])`` (INV-001 line 127-150).

    "The Runtime Safety Profile may reduce but never enlarge the Hard Safety
    Envelope" (§5 line 150): each dimension's Effective Limit is the minimum of the
    Hard Envelope and Runtime Profile bound. A dimension missing (``None``) on
    either side yields ``None`` (UNKNOWN => fail-closed downstream, §5.3), never the
    other side's (potentially larger) value.

    Args:
        hard: The Hard Safety Envelope bound vector.
        runtime: The Runtime Safety Profile bound vector.

    Returns:
        The Effective Limit Capacity Vector.
    """
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
    """A claimed netting / hedge / diversification / correlation benefit (§5.1/§6.3).

    ``reduction`` is the per-dimension capacity reduction the claim asserts. The
    ``kind`` names the benefit category. A claim alone reduces nothing — it must be
    accompanied by a **positive** :class:`BenefitProof` (§5.1 rule 2).
    """

    kind: str | None = None
    reduction: CapacityVector = CapacityVector()


class BenefitProof(FrozenModel):
    """A positive proof token authorizing a benefit reduction (§5.1 rule 2, §6.5).

    A benefit reduces adverse capacity **only when positively proven** — the Broker
    Capability Profile proves the enforcement scope and behavior (§6.5 line 316) and
    the scope is proven. Absence of a proof (``proof=None`` at the call site) — or a
    proof that is not positive — reduces nothing (the "no-benefit flag absent" case
    is NOT a proof, RCL design §5.1 canary).
    """

    broker_profile_proven: bool = False
    scope_proven: bool = False
    proof_reference: str | None = None

    def is_positive(self) -> bool:
        """Whether this is a positive proof token (both scope + profile proven)."""
        return self.broker_profile_proven and self.scope_proven
