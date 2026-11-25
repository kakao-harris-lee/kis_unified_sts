"""Recon injected predicate-input models (design #9 §2.1, §2.2, §5-§6)."""

from __future__ import annotations

from tos.recon._base import FrozenModel
from tos.recon.records import ConservativeBound, FreshnessMarker
from tos.recon.vocabulary import SafetyRelevantField


class EvidencePathObservation(FrozenModel):
    """One evidence path's assertion about one field (ADR §6 line 92; design #9 §2.2 item 5)."""

    field: SafetyRelevantField | None = None
    source_ref: str | None = None
    independence_class: str | None = None
    asserted_bound: ConservativeBound = ConservativeBound()
    agrees_within_tolerance: bool | None = None
    is_absence: bool = False
    freshness_marker: FreshnessMarker = FreshnessMarker()


class ReleaseProofInputs(FrozenModel):
    """Injected side-conditions for the field release proof rule (ADR §8; design #9 §6.1)."""

    final_quantity_proof_token: bool | None = None
    freshness: FreshnessMarker = FreshnessMarker()
