"""Active Currentness, Revocation, and Final-Egress Admission Fencing pure models + predicates (Phase 1, EV-L1).

Realizes the ADR-002-024 (Active Currentness, Revocation, and Final-Egress Admission Fencing —
"CUR") part of IMPLEMENTATION-PLAN-002 §4 Phase 1 (EV-L1), per the ratified design contract
``docs/plans/2026-07-26-tos-currentness-fencing-design.md`` (v1.1, operator-delegated auto-ratified
2026-07-27). It authors the **complete-vector aggregation + currentness structural / coordinate
model** — the Safety Currentness Vector completeness (every mandated dimension present + positively
established + one revision + policy complete + no placeholder), the Egress Currentness Proof
structure + admissibility, the Restrictive Fence Record monotonic floor advance, the per-dimension
floor / reconcile substrate, and the not-Phase-1 thin race / partition properties — over four
digest-bound artifacts plus injected value models (design #23 §2).

**This is the series' currentness *aggregator*; the two maximum risks are opposite (design #23
§0.1/§1).** (1) **over-realization**: the per-send §13 transaction, the §11 fence commit / deny-first
sequence, the §14 claim/fence/first-byte race, the §15 partition / quorum, the latch enforcement, and
the §18 wall-clock age are **all L2+ / runtime / +Security**. (2) **duplication**: the ~20 dimension
owners' business content is **never** re-decided — cur consumes each owner verdict / generation /
digest and judges only present / floor / revision / structure (§1 line 21 verbatim: "a currentness
sequencer ... does not invent facts, decide business safety, mutate capacity, issue Live
Authorization, classify protection, or transmit").

**CUR = complete-vector aggregator; venue / iap / capsule = per-decision leaf (design #23 §0.4b — the
key architecture decision, witnessed by sibling code).** venue ``__init__.py:17`` "active currentness
is ADR-002-024-owned"; egress ``predicates.py:13`` "venue / iap / capsule own their per-decision
egress-currentness and CUR (not landed) owns the complete-vector aggregation". Each per-decision leaf
(venue ``egress_currentness_active`` / iap ``active_egress_currentness`` / capsule
``egress_currentness_ok``) owns **one** dimension; the completeness axis (every dimension present +
single revision + policy complete) is the aggregator's own — a per-decision leaf structurally
**cannot** detect an unrepresented dimension, a mixed revision, or a policy under-declaration (§0.4b).

**Local Restrictive Latch stays egress-owned; the QCC stays egress-owned (design #23 §0.4c/d).** cur
re-authors **no** egress ``RestrictiveLatchState`` / ``monotonic_denial_no_revival`` (the latch state
machine + monotonic resolver is inside the Final Egress Trust Boundary = ADR-002-013) — it consumes
the resolved latch as an injected ``local_latch_clear`` bool. cur re-authors **no** egress
``QuorumCommitCertificate`` — the QCC carries this package's ``egress_currentness_proof_id`` as a
bound claim (egress → cur consumption, never the reverse). Currentness (an ordering-revision identity,
§5.4) is a **different axis** from time freshness (wall-clock age) — cur is **clock-free** (§0.4e).

This package is **pure, non-transmitting, non-mutating, and clock-free** (design #23 §0.2/§4.1): it
has **no** send / transmit / sign / claim / mutate / reserve / release / approve / arm / clear-latch
method — the structural absence of a transmit / mutate method is this package's identity (§4.1
constructive-absence canary; the void-canary tests assert it). It **cannot** approve, mutate or
release capacity, issue authority / capability, classify protection, transmit, clear a HALT, or
re-arm (all-false :class:`~tos.cur._base.AllFalseCurrentnessAuthority`, CUR-INV-005). A positive
result comes only from positive proof, everything else is denial (design #23 §4.3 — the polarity seal
against the #22 MAJOR-2 fail-open lesson).

It imports only ``pydantic`` + stdlib + ``tos.canonical`` (the digest substrate +
``IndependentIdArtifact`` + ``classify_record_pair`` + ``CanonicalDecimal``) + ``tos.ordering``
(append-only generation order). It imports **no** sibling — every sibling, landed or future
(``tos.rlp`` / ``tos.wdr`` / ``tos.sir`` / ``tos.stm`` / ``tos.sci`` / ``tos.posttrade`` — all landed since, all still excluded) is excluded by the
§7.1 **allowlist** closure test (``tos.*`` closure ⊆ {``tos.canonical``, ``tos.ordering``,
``tos.cur``}) — **sibling edge 0** (design #23 §0.3/§3.4). **PROMOTE 0** — the digest / ordering
substrate is already core.

Identity is **independent, not** ``f(digest)`` for all four artifacts (design #23 §2.1/§3.1): each is
an immutable issued record; a same-id / different-bytes forgery, re-issue, or replay is a detectable
``classify_record_pair`` ``CRITICAL_CONFLICT`` (CUR-EV-001/004).

**Completion discipline (design #23 §1).** ``CUR-EV-001..012`` are all NOT_IMPLEMENTED. One row (001
Complete Exact Vector) carries an ``EV-L1`` slice (core, ``EV-L1/3`` — the series' thinnest core
tier); nine are predicate-only (≥ ``EV-L2``); two (005 Claim/Fence/First-Byte Race, 006 Partition)
are not-Phase-1 (``EV-L3+Security``). Phase 1 authors the L1-decidable structural / coordinate
substrate and closes **no** CUR-EV — even the core row carries ``/3`` (integration / adversarial)
residue (authoring is not evidence, VER-002-001 §5; ADR §25 line 556 "Written cases are not completed
evidence"; §28 line 665 "Authorship ... does not satisfy this gate"). Tag for any claim: "structural
/ coordinate / completeness predicate substrate only; CUR-EV-001..012 remain NOT_IMPLEMENTED pending
EV-L2/L3 integration, adversarial, +Security, and +Broker evidence; **EV-L1-complete claim
forbidden**; dimension owner logic / per-send transaction / fence commit / latch enforcement /
wall-clock age are re-authored / runtime / +Security; L1 is present / floor / revision / structure
only."

Public surface groups by module:

* :mod:`tos.cur.vocabulary` — the CUR-axis StrEnums (truthy-untestable ``ProofResult`` /
  ``CurrentnessAdmission`` + closed structural ``DimensionKey``) + the ``MANDATED_DIMENSION_FLOOR``.
* :mod:`tos.cur.records` — the four digest-bound artifacts + the all-false ``AllFalseCurrentnessAuthority``.
* :mod:`tos.cur.state` — the injected value / input models + the ``tos.ordering`` generation REUSE.
* :mod:`tos.cur.predicates` — the core §5 ``vector_complete`` yolk + supporting + the predicate-only
  §6 substrate + the not-Phase-1 §6b thin models.
"""

from __future__ import annotations

from tos.cur._base import (
    AllFalseCurrentnessAuthority,
    ArtifactIntegrityError,
    ArtifactStatus,
    CanonicalDecimal,
    IndependentIdArtifact,
    RecordPairKind,
    classify_record_pair,
)
from tos.cur.predicates import (
    all_false_currentness_authority,
    all_floors_met,
    broker_reachable_not_authority,
    conflicting_owner_restricts,
    dimension_positively_established,
    expiry_denies_future_use_only,
    fence_advances_floor,
    multi_domain_no_union,
    no_forbidden_placeholder,
    parent_child_floor_monotone,
    policy_covers_mandated_dimensions,
    proof_admissible,
    proof_structurally_complete,
    protective_label_not_authority,
    race_order_admissible,
    recovery_revives_nothing,
    restrictive_floor_reconciled,
    restrictive_union_scope,
    single_revision_consistent,
    unknown_preserves_capacity,
    vector_complete,
)
from tos.cur.records import (
    CurrentnessPolicy,
    EgressCurrentnessProof,
    RestrictiveFenceRecord,
    SafetyCurrentnessVector,
)
from tos.cur.state import (
    CurrentnessDimension,
    CurrentnessRevision,
    DomainProof,
    EgressProofCoordinateSet,
    OwnerSubmission,
    TrialClaims,
    floor_strictly_advances,
)
from tos.cur.vocabulary import (
    CONDITIONAL_DIMENSION_KEYS,
    MANDATED_DIMENSION_FLOOR,
    CurrentnessAdmission,
    DimensionKey,
    ProofResult,
)

__all__ = [
    # base (reused core + cur-local all-false authority)
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "CanonicalDecimal",
    "IndependentIdArtifact",
    "RecordPairKind",
    "classify_record_pair",
    "AllFalseCurrentnessAuthority",
    # vocabulary
    "ProofResult",
    "CurrentnessAdmission",
    "DimensionKey",
    "CONDITIONAL_DIMENSION_KEYS",
    "MANDATED_DIMENSION_FLOOR",
    # records — the four digest-bound artifacts
    "SafetyCurrentnessVector",
    "EgressCurrentnessProof",
    "RestrictiveFenceRecord",
    "CurrentnessPolicy",
    # state — injected value / input models + ordering REUSE
    "CurrentnessRevision",
    "CurrentnessDimension",
    "EgressProofCoordinateSet",
    "TrialClaims",
    "OwnerSubmission",
    "DomainProof",
    "floor_strictly_advances",
    # core §5 predicates — vector_complete yolk + supporting
    "vector_complete",
    "dimension_positively_established",
    "single_revision_consistent",
    "no_forbidden_placeholder",
    "policy_covers_mandated_dimensions",
    # predicate-only §6 substrate
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
    # not-Phase-1 thin model §6b
    "race_order_admissible",
    "broker_reachable_not_authority",
]
