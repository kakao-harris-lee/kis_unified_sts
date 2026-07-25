"""Aggregate Risk Projection + Adverse-Scenario Evaluation pure models + predicates (Phase 1, EV-L1).

Realizes the ADR-002-021 (Aggregate Risk Projection, Adverse-Scenario Evaluation, and
Risk-Decision Integrity — "ARE") part of IMPLEMENTATION-PLAN-002 §4 Phase 1 (EV-L1), per the
ratified design contract ``docs/plans/2026-07-25-tos-aggregate-risk-projection-design.md``
(v1.1). It authors the **decision-integrity rules** — conservative projection / adverse-increment
dominance, no-unproven-benefit, numerical safety, decision integrity + non-cyclic forward-only
binding, currentness / invalidation, non-revival + economic continuity, and all-false authority
separation — over a four-artifact digest-bound data model. It is a **decision-integrity kernel,
not a numeric simulation engine** (design #13 §0.2): the concrete valuation / scenario /
correlation / solver models are Phase-0 (§4 non-scope); every magnitude / limit / floor / bound
is injected.

This package is **pure, non-transmitting, non-enforcing, and clock-free** (design #13
§0.2/§4.5): frozen pydantic models over injected state + conservative fail-closed predicates. It
**cannot** transmit / mutate capacity / issue authorization / commit a snapshot / re-arm — it
produces decision **bools** / scalars / a forward-only decision artifact; the owning runtime (a
future Aggregate Risk Authority / Snapshot Assembly / RCL-admission service) enforces them. There
is no "assume-zero" / "assume-within" / "assume-grant" path: ``GRANT`` / ``True`` comes only from
positive proof, everything else is ``UNKNOWN`` / ``DENY`` / ``False`` (design #13 §4.1 — the
structural seal against the #6 fail-open REJECT lesson).

It imports only ``pydantic`` + stdlib + ``tos.canonical`` (the digest substrate +
``IndependentIdArtifact`` + ``CanonicalDecimal`` + ``CanonicalizationScheme``) + ``tos.ordering``
(append-only generation / decision / snapshot order) + the rcl :class:`~tos.rcl.CapacityVector`
**type** for the final ``AdverseIncrement[s,d]`` (the single ``are -> rcl`` sibling edge, design
#13 §0.4c / MAJOR-1; rcl does not import are, so the edge is acyclic — the #8 orthostate -> rcl
precedent). It imports **none** of the other eleven siblings (``tos.protective`` / ``tos.spg`` /
``tos.liveauth`` / ``tos.authority`` / ``tos.time`` / ``tos.capsule`` / ``tos.evidence`` /
``tos.brokercap`` / ``tos.orthostate`` / ``tos.recon`` / ``tos.dsl``) — the protective magnitude /
rcl decision-content / spg step-7 / cancellation seams are all produced scalars / bools (design
#13 §3.4/§3.5 — those seam edges stay 0). Actively verified by the §7.1 import-closure test in
``tos/tests/are``. **PROMOTE 0건** — ``CanonicalDecimal`` is already core (design #9 §0.4c).

Identity is **independent, not** ``f(digest)`` (design #13 §3.1): each policy / snapshot /
scenario-set / decision generation is an immutable record; a legitimate revalidation /
supersession is a new independent id, a same-id / different-bytes re-issuance / contradictory
decision is a detectable ``classify_record_pair`` ``CRITICAL_CONFLICT``.

**Completion discipline (design #13 §1):** ``ARE-EV-001..012`` are all predicate / coordinate
substrate (5 rows — 001/002/003/004/006 — carry an EV-L1 slice; the other 7 are EV-L2+, and even
the 5 have ``/3`` / ``+Security`` / ``+Broker`` residue) — Phase 1 authors the L1-decidable
substrate and closes **no** ARE-EV item (authoring is not evidence, VER-002-001 §5). Tag for any
claim: "predicate / coordinate substrate only; ARE-EV-001..012 remain NOT_IMPLEMENTED pending
EV-L2/L3 fault injection, adversarial, +Security, and +Broker evidence; EV-L1-complete claim
forbidden."

Public surface groups by module:

* :mod:`tos.are.vocabulary` — the aggregate-risk-axis StrEnums.
* :mod:`tos.are.records` — the four digest-bound artifacts + value / injected-input models +
  all-false authority effect.
* :mod:`tos.are.predicates` — the core §5 + predicate-only §6.1/§6.2/§6.5/§6.7 decision rules +
  the produced protective-magnitude / cancellation / rcl / spg seam producers.
* :mod:`tos.are.state` — the temporal §6.3/§6.4/§6.6 predicates (concurrency, currentness,
  non-revival, economic continuity) + the ``tos.ordering`` REUSE.
"""

from __future__ import annotations

from tos.are._base import (
    AllFalseAggregateAuthority,
    ArtifactIntegrityError,
    ArtifactStatus,
    IndependentIdArtifact,
)
from tos.are.predicates import (
    adverse_increment,
    aggregate_effect_within,
    already_exceeded_regime,
    applicable_risk_scopes_of,
    benefit_admissible,
    cancellation_worsens_aggregate,
    continued_existence_worsens_aggregate,
    credible_space_bounded,
    current_conservative_risk,
    decision_content_ref,
    dimension_vector_integrity,
    envelope_bound_not_enlarged,
    exact_effect_snapshot_binding,
    final_conservative_risk,
    grant_identity_of,
    grants_no_authority,
    no_action_risk,
    no_credible_intermediate_increases_exceedance,
    numerical_determinism,
    numerical_safety,
    protective_creates_nothing,
    risk_decision,
    snapshot_scope_complete,
    valuation_conservative,
    worst_intermediate_risk,
)
from tos.are.records import (
    AdverseIncrementResult,
    AdverseScenarioSet,
    AggregateRiskAuthorityEffect,
    AggregateRiskDecision,
    AggregateRiskPolicy,
    AggregateRiskStateSnapshot,
    BenefitProof,
    CancellationRiskInputs,
    ProjectedCell,
    RiskDimensionDescriptor,
    ValuationInputs,
)
from tos.are.state import (
    concurrent_not_reservation,
    currentness_invalidation,
    decision_generation_monotone,
    economic_effect_persists,
    non_cyclic_binding,
    non_revival_holds,
)
from tos.are.vocabulary import (
    AdverseScenarioKind,
    BenefitKind,
    RiskDecisionResult,
    RiskDimensionKind,
    RiskScopeKind,
)
from tos.ordering import Ordering, OrderingEvent, compare_order

__all__ = [
    # base (reused core + are-local all-false authority)
    "AllFalseAggregateAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "IndependentIdArtifact",
    # ordering (reused core — append-only generation / decision / snapshot order)
    "Ordering",
    "OrderingEvent",
    "compare_order",
    # vocabulary
    "AdverseScenarioKind",
    "BenefitKind",
    "RiskDecisionResult",
    "RiskDimensionKind",
    "RiskScopeKind",
    # records
    "AdverseIncrementResult",
    "AdverseScenarioSet",
    "AggregateRiskAuthorityEffect",
    "AggregateRiskDecision",
    "AggregateRiskPolicy",
    "AggregateRiskStateSnapshot",
    "BenefitProof",
    "CancellationRiskInputs",
    "ProjectedCell",
    "RiskDimensionDescriptor",
    "ValuationInputs",
    # core §5 predicates
    "adverse_increment",
    "dimension_vector_integrity",
    "envelope_bound_not_enlarged",
    "exact_effect_snapshot_binding",
    "numerical_safety",
    "risk_decision",
    "snapshot_scope_complete",
    "valuation_conservative",
    # predicate-only §6 predicates
    "benefit_admissible",
    "concurrent_not_reservation",
    "currentness_invalidation",
    "decision_generation_monotone",
    "economic_effect_persists",
    "grants_no_authority",
    "non_cyclic_binding",
    "non_revival_holds",
    "numerical_determinism",
    "protective_creates_nothing",
    # produced protective magnitudes (§3.4)
    "already_exceeded_regime",
    "credible_space_bounded",
    "current_conservative_risk",
    "final_conservative_risk",
    "no_action_risk",
    "no_credible_intermediate_increases_exceedance",
    "worst_intermediate_risk",
    # produced cancellation-arbiter flags (§3.4)
    "cancellation_worsens_aggregate",
    "continued_existence_worsens_aggregate",
    # produced rcl seam (§3.4)
    "applicable_risk_scopes_of",
    "decision_content_ref",
    "grant_identity_of",
    # produced spg seam (§3.4)
    "aggregate_effect_within",
]
