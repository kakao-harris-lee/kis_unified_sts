"""Recon injected predicate-input models (design #9 §2.1, §2.2, §5-§6).

Plain frozen models carrying the **injected** inputs the pure recon predicates fold
over (design #9 §0.2: everything is a pure function over injected state — no clock
reads, no egress, no persistence). Independence, agreement tolerance, the Final Quantity
Proof token, and freshness are all injected judgments (their numeric backing —
independence-degree-by-hazard, agreement tolerance, freshness horizon — belongs to the
Verification Profile, never hardcoded; design #9 §8). Every optional flag is
``bool | None`` and **fail-closed**: ``None`` is treated conservatively (not-independent /
not-agreeing / not-proven), so a missing judgment can never lift a field to
``CORROBORATED`` or authorize a release (design #9 §4.4/§5.1/§6.1).

Pure module: ``pydantic`` + stdlib + ``tos.recon`` only; no ``shared.*``, no sibling
``tos.*`` (design #9 §0.3).
"""

from __future__ import annotations

from tos.recon._base import FrozenModel
from tos.recon.records import ConservativeBound, FreshnessMarker
from tos.recon.vocabulary import SafetyRelevantField


class EvidencePathObservation(FrozenModel):
    """One evidence path's assertion about one field (ADR §6 line 92; design #9 §2.2 item 5).

    The unit :func:`tos.recon.predicates.classify_field` folds. A Corroborating Evidence
    Path is "one sufficiently independent from another that a single defect is not
    expected to corrupt both in the same way" (ADR §6 line 92) — independence is the
    **injected** ``independence_class`` judgment (hazard-scaled per ADR §6 line 95, a
    Verification Profile number), not computed here. Paths sharing an
    ``independence_class`` are **common-mode** (shared parser / source / clock / transport)
    and cannot corroborate each other (RECON-EV-001).

    Attributes:
        field: The safety-relevant field this observation concerns.
        source_ref: A scalar reference to the underlying evidence record
            (evidence_id / generation / digest) — the evidence class is never imported
            (design #9 §3.5).
        independence_class: The injected independence judgment. Free-form (not a closed
            vocabulary — independence is hazard-scaled and injected): two observations
            with the **same** non-``None`` class are common-mode; ``None`` is fail-closed
            (not independent). Distinct non-``None`` classes are sufficiently independent.
        asserted_bound: The conservative bound this path asserts for the field.
        agrees_within_tolerance: Whether this path agrees with the others within the
            approved (injected) tolerance. ``None`` / ``False`` => treated as not agreeing
            (fail-closed — design #9 §5.1).
        is_absence: Whether this is a **negative** (absence) observation — absent from one
            query / page / session / stream. An absence may lower confidence but SHALL NOT
            establish ``NONE`` / ``CANCELLED`` / ``released``, narrow a bound, or produce a
            release proof (ADR §7 line 102; design #9 §5.3). ``True`` => this path is not
            usable positive evidence.
        freshness_marker: The injected freshness / time-confidence marker for this path.
    """

    field: SafetyRelevantField | None = None
    source_ref: str | None = None
    independence_class: str | None = None
    asserted_bound: ConservativeBound = ConservativeBound()
    agrees_within_tolerance: bool | None = None
    is_absence: bool = False
    freshness_marker: FreshnessMarker = FreshnessMarker()


class ReleaseProofInputs(FrozenModel):
    """Injected side-conditions for the field release proof rule (ADR §8; design #9 §6.1).

    The non-confidence inputs the §8 proof rule needs beyond a field's
    :class:`~tos.recon.records.FieldConfidence`: the broker's Final Quantity Proof token
    and the freshness marker. Both are injected and fail-closed.

    Attributes:
        final_quantity_proof_token: The broker's Final Quantity Proof, as an **opaque
            injected bool** (its content — including late-fill / correction semantics — is
            the approved Broker Capability Profile's concern, ADR-002-004; +Broker
            deferred, design #9 §6.1). Required only for capacity-releasing fields.
            ``None`` / ``False`` => not proven => release fails closed.
        freshness: The freshness / time-confidence marker evaluated by
            :func:`tos.recon.predicates.freshness_ok` (design #9 §6.3).
    """

    final_quantity_proof_token: bool | None = None
    freshness: FreshnessMarker = FreshnessMarker()
