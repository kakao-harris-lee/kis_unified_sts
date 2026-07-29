"""Restricted-Live Verification, Progressive Scope Promotion, and Production Authorization Governance
(ADR-002-025 — "RLP") pure models + predicates (Phase 1, EV-L1).

Realizes the ADR-002-025 (Restricted-Live Verification, Progressive Scope Promotion, and Production
Authorization Governance — "RLP") part of IMPLEMENTATION-PLAN-002 §4 Phase 1 (EV-L1), per the ratified
design contract ``docs/plans/2026-07-27-tos-restricted-live-design.md`` (v1.1, operator-delegated
auto-ratified 2026-07-27). It authors the **restricted-live trial content model + completeness /
subset / separation substrate** — the Exact Trial Plan exact-scope completeness (RLP-EV-001), the
Trial Evidence Package completeness + negative-result retention (RLP-EV-005), the coverage
non-extrapolation subset (RLP-EV-006), and the gate-status separation (RLP-EV-012) — over five
digest-bound artifacts plus injected value models (design #25 §2).

**This is the series' restricted-live trial *content owner* and *deferee* (design #25 §0.1/§0.4b — the
key architecture decision, witnessed by sibling code).** egress (``state.py:196``) and cur
(``state.py:140``) carry the restricted-live trial claim group as an opaque optional scalar group and
**defer its content validation to RLP by name** (``tos.rlp``). rlp is the **upstream content
producer**; egress / cur are downstream consumers — so rlp imports **neither** (a cycle) and
re-authors **no** boundary seal. The two maximum risks are opposite (design #25 §1): (1)
**over-realization** — the §13 per-action egress binding, the §15 abort race, the §10
worst-credible-effect computation, the §18-§19 independent review / promotion approval / production
authorization, and the §16 evidence assembly integrity are **all human / runtime / +Security /
+Broker / sibling-owned**, never L1; (2) **duplication** — the egress QCC / cur dimension / hag quorum
/ evidence SegmentCommitmentScheme / rcl CapacityVector / liveauth Live Authorization / spg activation
are **all injected-consumed**, re-authored not at all (§3.5).

This package is **pure, non-transmitting, non-mutating, and clock-free** (design #25 §0.2/§4.1): it
has **no** send / transmit / sign / arm / approve / authorize / promote / mutate / reserve / release
/ clear-halt method — the structural absence of a transmit / mutate / approve method is this
package's identity (§4.1 constructive-absence canary; the void-canary tests assert it). It **cannot**
create or release capacity, classify or create protection, issue Live Authorization or capability,
transmit, clear a HALT, re-arm, or grant broker permission (all-false
:class:`~tos.rlp._base.AllFalseTrialAuthority`, RLP-INV-001). A positive result comes only from
positive proof, everything else is denial (design #25 §4.3 — the polarity seal against the #22
MAJOR-2 fail-open lesson; §4.4 — the reconcile seal against the #22 MAJOR-1 union lesson).

It imports only ``pydantic`` + stdlib + ``tos.canonical`` (the digest substrate +
``IndependentIdArtifact`` + ``classify_record_pair`` + ``CanonicalDecimal``) + ``tos.ordering``
(append-only generation order). It imports **no** sibling — every sibling, landed or future
(``tos.wdr`` / ``tos.sir`` / ``tos.stm`` / ``tos.sci`` / ``tos.posttrade`` — all landed since, all still excluded), is excluded by the §7.1
**allowlist** closure test (``tos.*`` closure ⊆ {``tos.canonical``, ``tos.ordering``, ``tos.rlp``}) —
**sibling edge 0** (design #25 §0.3/§3.4). **PROMOTE 0** — the digest / ordering substrate is already
core.

Identity is **independent, not** ``f(digest)`` for all five artifacts (design #25 §2.1/§3.1): each is
an immutable issued record; a same-id / different-bytes forgery, re-issue, or replay is a detectable
``classify_record_pair`` ``CRITICAL_CONFLICT`` (RLP-EV-001/007).

**Completion discipline (design #25 §1).** ``RLP-EV-001..012`` are all NOT_IMPLEMENTED. Four rows
(001 Exact Pre-Registered Scope / 005 Evidence Completeness and Negative-Result Retention / 006
Coverage and Non-Extrapolation / 012 Gate Honesty and Status Separation) carry an ``EV-L1`` slice
(core, ``EV-L1/3`` — the governance sextet's highest L1 accessibility); seven are predicate-only
(≥ ``EV-L2``, +Security / +Broker); one (004 Abort Dominance and Race) is not-Phase-1
(``EV-L3+Security``). Phase 1 authors the L1-decidable structural / completeness substrate and closes
**no** RLP-EV — even the core rows carry ``/3`` (integration / adversarial) residue (authoring is not
evidence, VER-002-001 §5; ADR §26 line 632 "Written cases are not completed evidence"; §29 line 747
"Authorship ... does not satisfy these gates"). Tag for any claim: "structural / completeness /
subset / separation predicate substrate only; RLP-EV-001..012 remain NOT_IMPLEMENTED pending EV-L2/L3
integration, adversarial, +Security, and +Broker evidence; **EV-L1-complete claim forbidden**; trial
execution / per-action egress binding / worst-credible-effect computation / independent review /
promotion approval / evidence assembly integrity are re-authored / runtime / human / +Security; L1 is
plan / package / coverage / gate structural judgement only."

Public surface groups by module:

* :mod:`tos.rlp.vocabulary` — the RLP-axis StrEnums (truthy-untestable ``PlanResult`` /
  ``PromotionResult`` / ``TrialRunState`` / ``CoverageVerdict`` + closed structural ``ScopeDimension``
  / ``EvidenceClass``) + the mandated floors.
* :mod:`tos.rlp.records` — the five digest-bound artifacts + the all-false ``AllFalseTrialAuthority``.
* :mod:`tos.rlp.state` — the injected value / input models + the ``tos.ordering`` generation REUSE.
* :mod:`tos.rlp.predicates` — the four yolk predicates + supporting + the predicate-only §6 substrate
  + the not-Phase-1 §6b thin abort-order model.
"""

from __future__ import annotations

from tos.rlp._base import (
    AllFalseTrialAuthority,
    ArtifactIntegrityError,
    ArtifactStatus,
    CanonicalDecimal,
    IndependentIdArtifact,
    RecordPairKind,
    classify_record_pair,
)
from tos.rlp.predicates import (
    abort_precedes_action,
    action_potentially_live,
    all_false_trial_authority,
    baseline_digests_bound,
    coverage_supports_claim,
    demotion_not_rearm,
    economic_effect_persists,
    evidence_package_complete,
    expiry_denies_future_use_only,
    gate_status_separated,
    monitoring_not_preventive,
    negative_results_retained,
    no_selective_reporting,
    no_status_implication,
    no_union_coverage,
    no_wildcard_scope,
    plan_result_admissible,
    plan_scope_exact_and_complete,
    promotion_progressive_single_use,
    readiness_not_authority,
    recovery_revives_nothing,
    trial_budget_is_not_capacity,
    trial_claims_complete,
    trial_status_waives_no_gate,
)
from tos.rlp.records import (
    ExactTrialPlan,
    ProductionScopePromotionDecision,
    TrialEvidencePackage,
    TrialPolicy,
    TrialRun,
)
from tos.rlp.state import (
    WILDCARD_METACHARACTERS,
    WILDCARD_SENTINELS,
    CoverageClaim,
    GateStatusLadder,
    TrialBudget,
    TrialClaimGroup,
    TrialScope,
    is_wildcard_value,
    promotion_generation_advances,
)
from tos.rlp.vocabulary import (
    MANDATED_EVIDENCE_FLOOR,
    MANDATED_SCOPE_FLOOR,
    NEGATIVE_RESULT_CLASSES,
    CoverageVerdict,
    EvidenceClass,
    PlanResult,
    PromotionResult,
    ScopeDimension,
    TrialRunState,
)

__all__ = [
    # base (reused core + rlp-local all-false authority)
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "CanonicalDecimal",
    "IndependentIdArtifact",
    "RecordPairKind",
    "classify_record_pair",
    "AllFalseTrialAuthority",
    # vocabulary
    "PlanResult",
    "PromotionResult",
    "TrialRunState",
    "CoverageVerdict",
    "ScopeDimension",
    "EvidenceClass",
    "MANDATED_SCOPE_FLOOR",
    "MANDATED_EVIDENCE_FLOOR",
    "NEGATIVE_RESULT_CLASSES",
    # records — the five digest-bound artifacts
    "TrialPolicy",
    "ExactTrialPlan",
    "TrialRun",
    "TrialEvidencePackage",
    "ProductionScopePromotionDecision",
    # state — injected value / input models + ordering REUSE
    "TrialScope",
    "TrialBudget",
    "CoverageClaim",
    "GateStatusLadder",
    "TrialClaimGroup",
    "WILDCARD_SENTINELS",
    "WILDCARD_METACHARACTERS",
    "is_wildcard_value",
    "promotion_generation_advances",
    # core §5 predicates — the four yolk + supporting
    "plan_result_admissible",
    "no_wildcard_scope",
    "baseline_digests_bound",
    "plan_scope_exact_and_complete",
    "trial_claims_complete",
    "negative_results_retained",
    "no_selective_reporting",
    "evidence_package_complete",
    "coverage_supports_claim",
    "no_union_coverage",
    "no_status_implication",
    "readiness_not_authority",
    "gate_status_separated",
    # predicate-only §6 substrate
    "trial_budget_is_not_capacity",
    "trial_status_waives_no_gate",
    "promotion_progressive_single_use",
    "all_false_trial_authority",
    "expiry_denies_future_use_only",
    "economic_effect_persists",
    "recovery_revives_nothing",
    "monitoring_not_preventive",
    "demotion_not_rearm",
    # not-Phase-1 thin model §6b
    "abort_precedes_action",
    "action_potentially_live",
]
