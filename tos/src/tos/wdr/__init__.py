"""Safety-Waiver, Deviation, and Residual-Risk Governance (ADR-002-026 — "WDR") pure models +
predicates (Phase 1, EV-L1).

Realizes the ADR-002-026 (Safety Waiver, Deviation, and Residual-Risk Governance — "WDR") part of
IMPLEMENTATION-PLAN-002 §4 Phase 1 (EV-L1), per the ratified design contract
``docs/plans/2026-07-27-tos-safety-waiver-design.md`` (v1.1, operator-delegated auto-ratified
2026-07-27). It authors the **boundary / scope / UNKNOWN / status / set / gate structural substrate** —
the Non-Waivable Boundary denial (WDR-EV-001), the exact-scope + dependency-closure completeness
(WDR-EV-002), the UNKNOWN confinement (WDR-EV-007), the evidence-status honesty (WDR-EV-010), and the
combined-set no-union + gate separation (WDR-EV-012) — over five digest-bound artifacts plus injected
value models (design #26 §2).

**This is the series' safety-deviation governance *greenfield content owner*, with NO inbound deferee
(design #26 §0.1/§0.4b — the key architecture decision, the maximum contrast with RLP).** RLP (#25) was
a *deferee* — egress / cur carried the restricted-live trial claim and deferred its content validation
to ``tos.rlp`` **by name**. **WDR has zero inbound deferral seam** (grep-witnessed, §0.4b): no landed
sibling defers deviation content to ``tos.wdr``. The name ``tos.wdr`` is fixed only by two firewall
*exclusion*-list comments (``cur/__init__.py:51`` / ``rlp/__init__.py:39`` enumerate the then-future sibling
``tos.wdr`` as auto-excluded), so **naming is a *weaker* soft load-bearing than RLP's** — a different
name would not orphan any functional reference, only make those list comments imprecise (§0.4a). WDR's
``Deviation Generation`` coordinates are destined to flow downstream into the cur Safety Currentness
Vector (§14), but cur does not yet own that dimension. The two maximum risks are opposite (design #26
§1): (1) **over-realization** — the §12 independent effective-person review / quorum, the §14 per-action
final-egress currentness binding, the §14 revocation send-race, the §11 worst-credible-effect
computation, the §11 compensating-control effectiveness verification, the §13 break-before-make
activation, the §8/§11 Hard Safety Envelope containment, the §19 evidence assembly integrity, and the §7
Live Authorization issuance are **all human / runtime / +Security / +Broker / sibling-owned**, never L1;
(2) **duplication** — the spg Hard Safety Envelope / ``residual_risk_ceiling`` / activation, hag
effective-principal / quorum, rcl ``CapacityVector`` / worst-credible-effect, egress final-egress, cur
Safety Currentness Vector, evidence custody, liveauth Live Authorization, iap single-use shape, and
authority epoch / non-revival are **all injected-consumed**, re-authored not at all (§3.5).

This package is **pure, non-transmitting, non-mutating, and clock-free** (design #26 §0.2/§4.1): it has
**no** send / transmit / sign / arm / approve / authorize / activate / mutate / reserve / release /
clear-halt method — the structural absence of a transmit / mutate / approve method is this package's
identity (§4.1 constructive-absence canary; the void-canary tests assert it). It **cannot** create or
release capacity, classify or create protection, create Safety Authority, issue Live Authorization or
capability, transmit, clear a HALT, create production scope, re-arm, or grant broker permission
(all-false :class:`~tos.wdr._base.AllFalseDeviationAuthority`, WDR-INV-001). A positive result comes
only from positive proof, everything else is denial (design #26 §4.3 — the polarity seal against the
#18/#22 MAJOR-2 fail-open lesson; §4.4 — the reconcile seal against the #22 MAJOR-1 union lesson, with
the §13 line 364 explicit-empty set kept valid, v1.1 MAJOR-1).

It imports only ``pydantic`` + stdlib + ``tos.canonical`` (the digest substrate +
``IndependentIdArtifact`` + ``classify_record_pair`` + ``CanonicalDecimal``) + ``tos.ordering``
(append-only generation order). It imports **no** sibling — every sibling, landed or future
(``tos.sir`` / ``tos.stm`` / ``tos.sci`` / ``tos.posttrade`` — all landed since, all still excluded), is excluded by the §7.1 **allowlist** closure
test (``tos.*`` closure ⊆ {``tos.canonical``, ``tos.ordering``, ``tos.wdr``}) — **sibling edge 0**
(design #26 §0.3/§3.4). **rcl edge 0** in particular: WDR does no capacity arithmetic (worst-credible
effect is an injected opaque coordinate, not a ``CapacityVector`` type), so unlike are / ioc / afg it
takes **no** rcl edge (§0.4g). **PROMOTE 0** — the digest / ordering substrate is already core.

Identity is **independent, not** ``f(digest)`` for all five artifacts (design #26 §2.1/§3.1): each is an
immutable issued record; a same-id / different-**covered**-bytes forgery, re-issue, or replay is a
detectable ``classify_record_pair`` ``CRITICAL_CONFLICT`` (WDR-EV-001/012).

**Completion discipline (design #26 §1).** ``WDR-EV-001..012`` are all NOT_IMPLEMENTED. Five rows carry
an ``EV-L1`` slice (core — the governance sextet's joint-highest L1 accessibility): 001 Non-Waivable
Boundary (``EV-L1/3+Security``), 002 Exact Scope and Dependency Closure (``EV-L1/3``), 007 UNKNOWN /
Capacity / Protective Confinement (``EV-L1/3+Broker``), 010 Evidence and Status Honesty (``EV-L1/3``),
012 Combined Deviations and Gate Separation (``EV-L1/3+Security``). **Unlike RLP's core rows (all pure
``EV-L1/3``), three of WDR's core rows (001 / 007 / 012) carry a residual ``+Security`` / ``+Broker``
tag** — the L1 slice exists but the row's closing is Phase-1-out. Six rows are predicate-only (≥
``EV-L2``, +Security / +Broker); one (006 Currentness / Revocation / Send Race) is not-Phase-1
(``EV-L3+Security``). Phase 1 authors the L1-decidable structural substrate and closes **no** WDR-EV —
even the core rows carry ``/3`` (integration / adversarial) residue (authoring is not evidence,
VER-002-001 §5; ADR §25 line 639 "Written cases are not completed evidence"; §28 line 754 "Authorship
... does not satisfy these gates"). Tag for any claim: "boundary / scope / UNKNOWN / status / set / gate
predicate substrate only; WDR-EV-001..012 remain NOT_IMPLEMENTED pending EV-L2/L3 integration,
adversarial, +Security, and +Broker evidence; **EV-L1-complete claim forbidden**; independent review /
quorum / per-action egress binding / worst-credible-effect computation / break-before-make activation /
compensating-control effectiveness / Live Authorization issuance are re-authored / runtime / human /
+Security / +Broker; L1 is boundary / scope / UNKNOWN / status / set / gate structural judgement only."

Public surface groups by module:

* :mod:`tos.wdr.vocabulary` — the WDR-axis StrEnums (truthy-untestable ``DecisionResult`` /
  ``NonWaivableClassification`` / ``RequestState`` / ``ActiveDeviationState`` / ``WaivedEvidenceStatus``
  + closed structural ``ScopeDimension`` / ``CompensatingControlKind``) + the mandated floors.
* :mod:`tos.wdr.records` — the five digest-bound artifacts + the all-false
  ``AllFalseDeviationAuthority``.
* :mod:`tos.wdr.state` — the injected value / input models + the ``tos.ordering`` generation REUSE.
* :mod:`tos.wdr.predicates` — the five yolk predicates + supporting + the predicate-only §6 substrate +
  the not-Phase-1 §6b thin revocation send-race model.
"""

from __future__ import annotations

from tos.wdr._base import (
    AllFalseDeviationAuthority,
    ArtifactIntegrityError,
    ArtifactStatus,
    CanonicalDecimal,
    IndependentIdArtifact,
    RecordPairKind,
    classify_record_pair,
)
from tos.wdr.predicates import (
    all_false_deviation_authority,
    approval_is_not_verification,
    attempt_potentially_live,
    boundary_denies_non_waivable,
    boundary_is_union_only,
    break_glass_no_authority,
    broker_finality_unchanged,
    budget_is_not_capacity,
    classification_admissible,
    combined_set_no_permissive_union,
    compensating_control_not_observation,
    dependency_closure_complete,
    deviation_service_no_route,
    deviation_single_use_non_authorizing,
    economic_effect_persists,
    evidence_status_honest,
    expiry_recovery_revives_nothing,
    gate_states_separated,
    independent_effective_person_approval,
    no_scope_drift,
    no_status_implication,
    no_wildcard_scope,
    omitted_deviation_invalidates,
    protective_label_no_bypass,
    readiness_not_authority,
    revocation_dominates_send,
    scope_exact_and_complete,
    unknown_denies_and_confines,
    unresolved_is_non_waivable,
)
from tos.wdr.records import (
    ActiveDeviationSet,
    ResidualRiskAcceptanceRecord,
    SafetyDeviationDecision,
    SafetyDeviationPolicy,
    SafetyDeviationRequest,
)
from tos.wdr.state import (
    WILDCARD_METACHARACTERS,
    WILDCARD_SENTINELS,
    CompensatingControl,
    DeviationClassification,
    DeviationDependencyClosure,
    DeviationScope,
    GateSeparationLadder,
    NonWaivableBoundaryAnchor,
    WaivedEvidenceItem,
    deviation_generation_advances,
    is_wildcard_value,
)
from tos.wdr.vocabulary import (
    MANDATED_SCOPE_FLOOR,
    MEASURED_FAILURE_STATUSES,
    ActiveDeviationState,
    CompensatingControlKind,
    DecisionResult,
    NonWaivableClassification,
    RequestState,
    ScopeDimension,
    WaivedEvidenceStatus,
)

__all__ = [
    # base (reused core + wdr-local all-false authority)
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "CanonicalDecimal",
    "IndependentIdArtifact",
    "RecordPairKind",
    "classify_record_pair",
    "AllFalseDeviationAuthority",
    # vocabulary
    "DecisionResult",
    "NonWaivableClassification",
    "RequestState",
    "ActiveDeviationState",
    "WaivedEvidenceStatus",
    "ScopeDimension",
    "CompensatingControlKind",
    "MANDATED_SCOPE_FLOOR",
    "MEASURED_FAILURE_STATUSES",
    # records — the five digest-bound artifacts
    "SafetyDeviationPolicy",
    "SafetyDeviationRequest",
    "SafetyDeviationDecision",
    "ResidualRiskAcceptanceRecord",
    "ActiveDeviationSet",
    # state — injected value / input models + ordering REUSE
    "DeviationScope",
    "CompensatingControl",
    "DeviationDependencyClosure",
    "NonWaivableBoundaryAnchor",
    "WaivedEvidenceItem",
    "GateSeparationLadder",
    "DeviationClassification",
    "WILDCARD_SENTINELS",
    "WILDCARD_METACHARACTERS",
    "is_wildcard_value",
    "deviation_generation_advances",
    # core §5 predicates — the five yolk + supporting
    "boundary_denies_non_waivable",
    "classification_admissible",
    "boundary_is_union_only",
    "unresolved_is_non_waivable",
    "scope_exact_and_complete",
    "no_wildcard_scope",
    "no_scope_drift",
    "dependency_closure_complete",
    "unknown_denies_and_confines",
    "budget_is_not_capacity",
    "protective_label_no_bypass",
    "evidence_status_honest",
    "approval_is_not_verification",
    "combined_set_no_permissive_union",
    "omitted_deviation_invalidates",
    "gate_states_separated",
    "no_status_implication",
    "readiness_not_authority",
    # predicate-only §6 substrate
    "all_false_deviation_authority",
    "compensating_control_not_observation",
    "independent_effective_person_approval",
    "deviation_single_use_non_authorizing",
    "broker_finality_unchanged",
    "economic_effect_persists",
    "expiry_recovery_revives_nothing",
    "break_glass_no_authority",
    "deviation_service_no_route",
    # not-Phase-1 thin model §6b
    "revocation_dominates_send",
    "attempt_potentially_live",
]
