"""Reconciliation Confidence pure data models + predicates (Phase 1, EV-L1).

Realizes the ADR-002-006 (Evidence and Reconciliation Confidence Model) part of
IMPLEMENTATION-PLAN-002 §4 Phase 1 (EV-L1), per the ratified design contract
``docs/plans/2026-07-25-tos-reconciliation-confidence-design.md`` (v1.1). It represents
safety-relevant state as **per-field evidence with conservative bounds** — a per-field
confidence class plus a lower/upper bound, never a single blended score — and authors the
corroboration / conflict / negative-evidence / freshness / field-specific-release-proof
predicates that gate whether a field's knowledge may become ``RECONCILED``.

This package is **pure, non-transmitting, and clock-free** (design #9 §0.2/§4.7): frozen
pydantic models over injected state + conservative fail-closed predicates. It **cannot
mutate capacity** — it produces confidence classes, conservative bounds, and release
**proof bools**; the owning authorities (rcl INV-007, orthostate CPL-2 /
``knowledge_transition_allowed``) consume those bools and perform the transitions
(ADR §10 line 147; design #9 §3.4/§4.7). No-blended-release is **structural**: there is no
numeric confidence-score type and no averaging function anywhere (design #9 §4.1).

It imports only ``pydantic`` + stdlib (incl. ``decimal``) + ``tos.canonical`` (the digest
substrate + ``IndependentIdArtifact`` + ``classify_record_pair`` + the promoted
``CanonicalDecimal``, design #9 §0.4c) + ``tos.ordering`` (append-only assessment order) —
no ``numpy`` / ``pandas`` / ``yaml``, no ``shared.*``, and — as the decision-side
**upstream** confidence model — **none** of its siblings ``tos.orthostate`` / ``tos.rcl`` /
``tos.time`` / ``tos.evidence`` / ``tos.capsule`` / ``tos.authority`` / ``tos.liveauth`` /
``tos.dsl`` (design #9 §0.3/§3.4/§3.5 — sibling edge 0; the evidence store is a downstream
projection, freshness / broker-FQP / authority-epoch are injected flags, aggregate
Knowledge transition is a produced-bool seam). Actively verified by the §7.1
import-closure test in ``tos/tests/recon``.

Identity is **independent, not** ``f(digest)`` (design #9 §3.1): a legitimate
re-assessment is a new ``assessment_id``; a same-id / different-bytes re-submission is a
detectable ``classify_record_pair`` ``CRITICAL_CONFLICT``.

**Completion discipline (design #9 §1):** ``RECON-EV-001..005`` are all predicate
substrate only (register minimum EV-L2+, ``-005`` +Broker) — there is **no** EV-L1 slice
and Phase 1 closes **no** RECON-EV item (authoring is not evidence, VER-002-001 §5). Tag
for any claim: "predicate substrate only; RECON-EV-001..005 remain NOT_IMPLEMENTED pending
EV-L2/L3 fault injection, adversarial, and broker-profile evidence; no core tier;
EV-L1-complete claim forbidden."
"""

from __future__ import annotations

from tos.ordering import Ordering, OrderingEvent, compare_order
from tos.recon._base import (
    ArtifactIntegrityError,
    ArtifactStatus,
    IndependentIdArtifact,
)
from tos.recon.predicates import (
    any_field_conflicted,
    bound_narrowing_allowed,
    classify_field,
    conservative_bound_of,
    field_reconciled_proof_ok,
    field_specific_release_proof_ok,
    freshness_lost,
    freshness_ok,
    is_conflicted,
    is_corroborated,
    merge_conservative,
)
from tos.recon.records import (
    ConservativeBound,
    FieldConfidence,
    FieldReconciliationAssessment,
    FreshnessMarker,
)
from tos.recon.state import EvidencePathObservation, ReleaseProofInputs
from tos.recon.vocabulary import (
    CAPACITY_RELEASING_FIELDS,
    FieldConfidenceClass,
    SafetyRelevantField,
)

__all__ = [
    # base
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "IndependentIdArtifact",
    # ordering (reused core — append-only assessment order)
    "Ordering",
    "OrderingEvent",
    "compare_order",
    # vocabulary
    "CAPACITY_RELEASING_FIELDS",
    "FieldConfidenceClass",
    "SafetyRelevantField",
    # records
    "ConservativeBound",
    "FieldConfidence",
    "FieldReconciliationAssessment",
    "FreshnessMarker",
    # state (injected inputs)
    "EvidencePathObservation",
    "ReleaseProofInputs",
    # predicates
    "any_field_conflicted",
    "bound_narrowing_allowed",
    "classify_field",
    "conservative_bound_of",
    "field_reconciled_proof_ok",
    "field_specific_release_proof_ok",
    "freshness_lost",
    "freshness_ok",
    "is_conflicted",
    "is_corroborated",
    "merge_conservative",
]
