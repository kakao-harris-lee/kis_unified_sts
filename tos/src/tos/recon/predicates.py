"""Pure recon predicates (design #9 §4, §5, §6)."""

from __future__ import annotations

from collections.abc import Sequence

from tos.recon.records import ConservativeBound, FieldConfidence, FreshnessMarker
from tos.recon.state import EvidencePathObservation, ReleaseProofInputs
from tos.recon.vocabulary import (
    CAPACITY_RELEASING_FIELDS,
    FieldConfidenceClass,
    SafetyRelevantField,
)


def freshness_ok(marker: FreshnessMarker) -> bool:
    """Whether a field's evidence is fresh under the approved bound (ADR §7 line 103)."""
    if marker.fresh_within_horizon is not True:
        return False
    if marker.time_confidence_held is not True:
        return False
    if marker.time_generation is None or marker.anchored_generation is None:
        return False
    return marker.time_generation == marker.anchored_generation


def freshness_lost(marker: FreshnessMarker) -> bool:
    """Whether freshness is lost — the negation of :func:`freshness_ok` (design #9 §3.4)."""
    return not freshness_ok(marker)


def classify_field(
    observations: Sequence[EvidencePathObservation],
    freshness_marker: FreshnessMarker,
) -> FieldConfidenceClass:
    """Classify a field's per-field evidence confidence (ADR §5 line 73-80; §6 line 92-95)."""
    usable = [o for o in observations if not o.is_absence]
    if not usable:
        return FieldConfidenceClass.UNKNOWN

    if len(usable) == 1:
        base = FieldConfidenceClass.SINGLE_SOURCE
    else:
        distinct_independent = {
            o.independence_class for o in usable if o.independence_class is not None
        }
        sufficiently_independent = len(distinct_independent) >= 2
        all_agree = all(o.agrees_within_tolerance is True for o in usable)
        any_disagreement = any(o.agrees_within_tolerance is False for o in usable)
        if sufficiently_independent and all_agree:
            base = FieldConfidenceClass.CORROBORATED
        elif sufficiently_independent and any_disagreement:
            base = FieldConfidenceClass.CONFLICTED
        else:
            base = FieldConfidenceClass.SINGLE_SOURCE

    if base is FieldConfidenceClass.CORROBORATED and freshness_lost(freshness_marker):
        return FieldConfidenceClass.STALE
    return base


def is_corroborated(
    observations: Sequence[EvidencePathObservation],
    freshness_marker: FreshnessMarker,
) -> bool:
    """Whether the field is ``CORROBORATED`` (``classify_field(...) is CORROBORATED``; §5.3)."""
    return (
        classify_field(observations, freshness_marker)
        is FieldConfidenceClass.CORROBORATED
    )


def is_conflicted(
    observations: Sequence[EvidencePathObservation],
    freshness_marker: FreshnessMarker,
) -> bool:
    """Whether the field is ``CONFLICTED`` (``classify_field(...) is CONFLICTED``; §5.3)."""
    return (
        classify_field(observations, freshness_marker)
        is FieldConfidenceClass.CONFLICTED
    )


def merge_conservative(*bounds: ConservativeBound) -> ConservativeBound:
    """Merge bounds into the **widest** (union) envelope — never an average (§5 line 82-86)."""
    if not bounds:
        return ConservativeBound()
    upper = (
        None
        if any(b.upper is None for b in bounds)
        else max(b.upper for b in bounds if b.upper is not None)
    )
    lower = (
        None
        if any(b.lower is None for b in bounds)
        else min(b.lower for b in bounds if b.lower is not None)
    )
    return ConservativeBound(lower=lower, upper=upper)


def conservative_bound_of(
    observations: Sequence[EvidencePathObservation],
) -> ConservativeBound:
    """The field's risk-usable conservative bound: the union of positive assertions (§5.2)."""
    positive = tuple(o.asserted_bound for o in observations if not o.is_absence)
    return merge_conservative(*positive)


def bound_narrowing_allowed(
    from_bound: ConservativeBound,
    to_bound: ConservativeBound,
    *,
    strong_basis: bool | None,
) -> bool:
    """Whether moving ``from_bound`` -> ``to_bound`` is permitted (ADR §8 line 121; §4.3)."""
    if to_bound.covers(from_bound):
        return True
    return strong_basis is True


def field_reconciled_proof_ok(
    field: SafetyRelevantField,
    confidence: FieldConfidence,
    inputs: ReleaseProofInputs,
) -> bool:
    """Whether a field satisfies its RECONCILED proof rule (ADR §8 line 112-118 verbatim)."""
    if confidence.field is not None and confidence.field is not field:
        return False
    if confidence.confidence_class is not FieldConfidenceClass.CORROBORATED:
        return False
    if (
        field in CAPACITY_RELEASING_FIELDS
        and inputs.final_quantity_proof_token is not True
    ):
        return False
    return freshness_ok(inputs.freshness)


def field_specific_release_proof_ok(
    field: SafetyRelevantField,
    confidence: FieldConfidence,
    inputs: ReleaseProofInputs,
) -> bool:
    """Whether a capacity-releasing field may authorize a release (ADR §8; RECON-EV-005)."""
    if field not in CAPACITY_RELEASING_FIELDS:
        return False
    return field_reconciled_proof_ok(field, confidence, inputs)


def any_field_conflicted(confidences: Sequence[FieldConfidence]) -> bool:
    """Whether any field in scope is ``CONFLICTED`` (design #9 §3.4 — CPL-5 antecedent)."""
    return any(
        c.confidence_class is FieldConfidenceClass.CONFLICTED for c in confidences
    )
