"""Recon value models + the append-only reconciliation assessment (design #9 §2)."""

from __future__ import annotations

from typing import ClassVar

from tos.canonical import CanonicalDecimal
from tos.recon._base import FrozenModel, IndependentIdArtifact
from tos.recon.vocabulary import FieldConfidenceClass, SafetyRelevantField


class ConservativeBound(FrozenModel):
    """A field's risk-usable conservative bound (ADR §5 line 82-86; design #9 §4.3)."""

    lower: CanonicalDecimal | None = None
    upper: CanonicalDecimal | None = None

    def covers(self, other: ConservativeBound) -> bool:
        """Whether this envelope is at least as wide as ``other`` (``self ⊇ other``)."""
        if self.upper is not None:
            if other.upper is None or self.upper < other.upper:
                return False
        if self.lower is not None:
            if other.lower is None or self.lower > other.lower:
                return False
        return True


class FreshnessMarker(FrozenModel):
    """Injected freshness / time-confidence marker (ADR §7 line 103; design #9 §3.5/§6.3)."""

    fresh_within_horizon: bool | None = None
    time_confidence_held: bool | None = None
    time_generation: int | None = None
    anchored_generation: int | None = None


class FieldConfidence(FrozenModel):
    """Per-field confidence value (ADR §1 line 15-22; design #9 §2.2 item 4)."""

    field: SafetyRelevantField | None = None
    confidence_class: FieldConfidenceClass | None = None
    bound: ConservativeBound = ConservativeBound()
    contributing_path_refs: tuple[str, ...] = ()
    freshness_marker: FreshnessMarker = FreshnessMarker()


class FieldReconciliationAssessment(IndependentIdArtifact):
    """An append-only reconciliation-run assessment (ADR §1/§13/§15; design #9 §2.1/§2.3)."""

    _ID_FIELD: ClassVar[str] = "assessment_id"
    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        "scope_ref",
        "state_model_version",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "scope_ref",
            "field_confidences",
            "state_model_version",
            "trustworthy_time_snapshot_ref",
        }
    )

    assessment_id: str | None = None

    scope_ref: str | None = None
    field_confidences: tuple[FieldConfidence, ...] = ()
    state_model_version: str | None = None
    trustworthy_time_snapshot_ref: str | None = None

    assessment_revision: int | None = None
