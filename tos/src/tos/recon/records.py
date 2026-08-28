"""Recon value models + the append-only reconciliation assessment (design #9 §2).

Every artifact is a **pydantic v2 frozen model** (``ConfigDict(frozen=True,
extra="forbid")`` via :class:`~tos.recon._base.FrozenModel`): frozen is the record-
level realization of append-only (ADR-002-006 §13 auditable / reproducible; §15
replayable) — there is **no** update / delete / mutate method on any model (design #9
§2.0). The confidence of a field is exactly a :class:`FieldConfidence` — a class + a
:class:`ConservativeBound` (lower / upper) — never a numeric score / midpoint / blended
scalar (design #9 §4.1; ADR §5 line 86).

Spec terms = code terms (boundary design #1 §2.4). Numeric bounds use the promoted
core :data:`~tos.canonical.CanonicalDecimal` (design #9 §0.4c) so ``1.0`` and ``1.00``
share one record digest — the PROMOTE regression lock, now against ``tos.canonical``.

Pure module: ``pydantic`` + stdlib (``decimal``) + ``tos.canonical`` + ``tos.recon``
only; no ``shared.*``, no sibling ``tos.*`` (design #9 §0.3).
"""

from __future__ import annotations

from typing import ClassVar

from tos.canonical import CanonicalDecimal
from tos.recon._base import FrozenModel, IndependentIdArtifact
from tos.recon.vocabulary import FieldConfidenceClass, SafetyRelevantField


class ConservativeBound(FrozenModel):
    """A field's risk-usable conservative bound (ADR §5 line 82-86; design #9 §4.3).

    ``lower`` / ``upper`` are :data:`~tos.canonical.CanonicalDecimal` or ``None``.
    **``None`` means unbounded-conservative** — ``upper=None`` is "adverse quantity may
    be arbitrarily large" (``+inf`` — the maximum adverse exposure) and ``lower=None`` is
    "may be arbitrarily small" (``-inf``). So ``None`` is the **widest / most
    conservative** value on that side (design #9 §2.2). There is deliberately **no**
    point-estimate / midpoint / score field — only the lower/upper pair (design #9 §4.1;
    ADR §5 line 86 "never a midpoint, average, or blended score").

    The direction rule (ADR §5 line 84-86): risk decisions use the **upper** bound for
    any adverse quantity (potential exposure, remaining executable quantity, external
    activity); the **lower** bound only where a lower value cannot understate risk.
    """

    lower: CanonicalDecimal | None = None
    upper: CanonicalDecimal | None = None

    def covers(self, other: ConservativeBound) -> bool:
        """Whether this envelope is at least as wide as ``other`` (``self ⊇ other``).

        With ``None`` = unbounded (``upper=None`` is ``+inf``, ``lower=None`` is
        ``-inf``): ``self`` covers ``other`` iff ``self.upper >= other.upper`` and
        ``self.lower <= other.lower`` under that extended order. Used by the
        widen-only / no-narrow-without-proof discipline (design #9 §4.3) and the
        merge-union ``⊇`` property (design #9 §4.1 / §5.2).

        Args:
            other: The bound to test for containment.

        Returns:
            ``True`` iff ``self`` is at least as wide (conservative) as ``other``.
        """
        # upper: self.upper (None=+inf) must be >= other.upper (None=+inf).
        if self.upper is not None:
            if other.upper is None or self.upper < other.upper:
                return False
        # lower: self.lower (None=-inf) must be <= other.lower (None=-inf).
        if self.lower is not None:
            if other.lower is None or self.lower > other.lower:
                return False
        return True


class FreshnessMarker(FrozenModel):
    """Injected freshness / time-confidence marker (ADR §7 line 103; design #9 §3.5/§6.3).

    Recon does **not** import ``tos.time`` and reads no clock (design #9 §3.5): freshness
    is carried as injected flags plus a time-service generation scalar (isomorphic to how
    orthostate / rcl defer time). Every flag is ``bool | None`` / ``int | None`` and
    **fail-closed** — any ``None`` makes :func:`tos.recon.predicates.freshness_ok` return
    ``False`` (design #9 §6.3 "None ⇒ fail-closed").

    Attributes:
        fresh_within_horizon: Evidence is within the approved freshness horizon (the
            numeric horizon itself is a Verification Profile value — injected, never
            hardcoded). ``None`` / ``False`` => aged / not fresh.
        time_confidence_held: Trustworthy-time confidence is currently held (e.g.
            clock drift within ``MAX_clock_drift_ppm``). ``None`` / ``False`` => time
            confidence lost => all time-dependent freshness fails closed (ADR §7 line 103).
        time_generation: The current time-service generation. A time service that
            restarts advances this; an old marker anchored at a prior generation does
            **not** auto-refresh merely because time recovers (ADR RECON-EV-004).
        anchored_generation: The time-service generation this marker was anchored at.
            Freshness requires ``anchored_generation == time_generation`` (both non-None).
    """

    fresh_within_horizon: bool | None = None
    time_confidence_held: bool | None = None
    time_generation: int | None = None
    anchored_generation: int | None = None


class FieldConfidence(FrozenModel):
    """Per-field confidence value (ADR §1 line 15-22; design #9 §2.2 item 4).

    The per-field structure ADR §1 mandates carrying for each safety-relevant field: a
    confidence class, a risk-usable conservative bound, the contributing evidence-path
    provenance references (scalars — evidence records are referenced, never imported;
    design #9 §3.5), and a freshness marker. There is **no** numeric confidence score
    field (design #9 §4.1 — no blended release).
    """

    field: SafetyRelevantField | None = None
    confidence_class: FieldConfidenceClass | None = None
    bound: ConservativeBound = ConservativeBound()
    contributing_path_refs: tuple[str, ...] = ()
    freshness_marker: FreshnessMarker = FreshnessMarker()


class FieldReconciliationAssessment(IndependentIdArtifact):
    """An append-only reconciliation-run assessment (ADR §1/§13/§15; design #9 §2.1/§2.3).

    A digest-bound :class:`~tos.canonical.IndependentIdArtifact` with an independent,
    service-assigned ``assessment_id`` (``id != f(digest)``, design #9 §3.1) so a
    same-id / different-bytes forgery or re-submission is a detectable
    ``classify_record_pair`` ``CRITICAL_CONFLICT``. Reconciliation runs repeatedly and a
    field's confidence transitions as evidence accrues (e.g. ``SINGLE_SOURCE`` ->
    ``CORROBORATED``, or ``CORROBORATED`` -> ``CONFLICTED``); a legitimate re-assessment is
    a **new** record with a **fresh** ``assessment_id`` (append-only, never in-place
    mutation — design #9 §2.3), so re-evaluation is never mis-flagged as a critical
    conflict.

    ``_REQUIRED_COVERED`` lists **structural identity / scope / version** fields only
    (design #9 §2.2 item 6). Numeric magnitudes live inside ``field_confidences`` and are
    excluded, so an assessment is ISSUED-reachable under Phase-1 null bounds (the rcl
    ``records.py`` discipline); a missing magnitude fails closed at the consuming
    predicate (design #9 §6.1). ``assessment_revision`` is self-excluded from the digest
    preimage — it is set by the owning ledger at placement (the rcl
    ``current_reservation_revision`` precedent; design #9 §2.3) and carries the
    append-only ``tos.ordering`` order.
    """

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

    # ---- Layer-0 identity (independent; excluded from the digest, §3.1) --------
    assessment_id: str | None = None

    # ---- Layer-1 covered content (ADR §1 "for each safety-relevant field") ----
    scope_ref: str | None = None
    field_confidences: tuple[FieldConfidence, ...] = ()
    state_model_version: str | None = None
    trustworthy_time_snapshot_ref: str | None = None

    # ---- ledger-placement (self-excluded from the digest, §2.3) ----
    assessment_revision: int | None = None
