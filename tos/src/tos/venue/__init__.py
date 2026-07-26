"""Venue / Session / Tradability / Broker-Constraint Gate pure models + predicates (Phase 1, EV-L1).

Realizes the ADR-002-019 (Venue, Session, Tradability, and Broker Constraint Gate — "VTG")
part of IMPLEMENTATION-PLAN-002 §4 Phase 1 (EV-L1), per the ratified design contract
``docs/plans/2026-07-26-tos-venue-tradability-design.md`` (v1.1, operator-delegated auto-ratified
2026-07-26). It authors the **order-admissibility decision rules** — session-phase admission,
exact instrument / route binding, order-shape venue-admissibility, exact decision binding + no
union, material-change invalidation closure, tradability-conflict conservatism, account /
margin conservatism, active final-egress currentness, exit non-assumption, protective
no-bypass, common-mode / continuity, all-false authority separation, and non-revival — over a
nine-model data substrate (design #19 §2).

VTG is an **order-admissibility gate, not a conformance / capacity / approval / capability
judge** (design #19 §0.4b/§3.5): intent-order conformance is ioc-owned, candidate command
construction is ioc-owned, capacity mutation is rcl/are-owned, approval is iap-owned, broker
capability semantics are brokercap-owned, CII construction is capsule-owned, trustworthy time
is time-owned, active currentness is ADR-002-024-owned, and protective classification is
protective-owned. VTG **consumes** every one of those as an **injected produced scalar / bool /
enum-token / verdict / digest** and re-authors none of them. It owns only the venue constraint
policy content, the snapshot, the order-admissibility decision, the authoritative session-phase
judgement, per-action tradability, order-shape venue-admissibility, the ``constraint_generation``
fence *meaning* (ordering carries the scalar, §0.4e), and the material-change invalidation
closure.

This package is **pure, non-transmitting, non-enforcing, and clock-free** (design #19
§0.2/§4.6): frozen pydantic models over injected state plus conservative fail-closed predicates.
It **cannot** transmit, mutate capacity, approve, issue authority, classify protection, clear a
HALT, or re-arm — it produces decision **results** / verdicts / scalars and forward record
artifacts; the owning runtime (a future Venue Constraint Gate / final-egress service) enforces
them. There is no "assume-admissible" / "infer-tradability" / "promote-capability" /
"bypass-via-protective-label" / "revive-on-reopen" path: a positive result comes only from
positive proof, everything else is ``INADMISSIBLE`` / ``UNKNOWN`` / ``False`` (design #19 §4.1 —
the structural seal against the #6 fail-open lesson).

**Truthy-sentinel discipline (design #19 §2.2(1)/§4.7 — #14 M1 adopted from the start, more
critical here).** ``OrderAdmissibilityResult`` (4-value) and ``TradabilityState`` are
**truthy-untestable** ``StrEnum``s (``__bool__`` raises ``TypeError``), so a consumer's
``if result:`` misuse raises rather than reading ``INADMISSIBLE`` / ``UNKNOWN`` / ``NOT_TRADABLE``
— or, catastrophically, ``RESTRICTED_PROTECTIVE_ONLY`` (reading protective-only as full
permission, §0.4d) — as truthy. The mandated gates are ``result is
OrderAdmissibilityResult.ADMISSIBLE`` / ``state is TradabilityState.TRADABLE``, and ``bool | None``
flags use ``is True`` / ``is not True``. ``SessionPhase`` is an **injected opaque token** (not an
enum — "Names are policy-defined", §5.5 line 127 / §2.2(3)): it is never consumed by truthiness,
only by admitting-set membership (:func:`~tos.venue.state.session_phase_admits`). ``ActionClass``
is a **closed** ``StrEnum`` (ADR §11 line 283-289 fixed taxonomy — v1.1 M4).

It imports only ``pydantic`` + stdlib + ``tos.canonical`` (the digest substrate +
``IndependentIdArtifact`` + ``classify_record_pair``) + ``tos.ordering`` (append-only
Constraint-Generation order). It imports **no** sibling — ``tos.afg`` / ``tos.are`` /
``tos.authority`` / ``tos.brokercap`` / ``tos.capsule`` / ``tos.dsl`` / ``tos.evidence`` /
``tos.iap`` / ``tos.ioc`` / ``tos.liveauth`` / ``tos.orthostate`` / ``tos.protective`` /
``tos.rcl`` / ``tos.recon`` / ``tos.sbr`` / ``tos.spg`` / ``tos.time`` and any future sibling
(``tos.pr`` etc.) are all excluded by the §7.1 **allowlist** closure test (``tos.*`` closure ⊆
{``tos.canonical``, ``tos.ordering``, ``tos.venue``}) — **sibling edge 0** (design #19
§0.3/§0.4c). The iap ``invalidation_closure`` / sbr ``_reachability_closure`` isomorphism is
**re-authored locally** (:func:`~tos.venue.predicates.material_change_closure` /
``_reachability_closure``), never imported (PROMOTE and import both rejected — design #19 §0.4d;
DRY preserved at the property-test-contract level). The ``dsl.AdmissibilityResult`` homonym is
**not** reused (a different domain — ADR-DEV-001 static-program admission, §0.4d). **PROMOTE 0**
— the digest / ordering substrate is already core.

Identity is **independent, not** ``f(digest)`` for policy / snapshot / decision (design #19
§2.1/§3.1): each is an immutable issued record whose identity shape matches the capsule
``VenueConstraintPolicyRef`` / ``VenueConstraintSnapshotRef`` / ``OrderAdmissibilityDecisionRef``
(``capsule.py:130-150``); a same-id / different-bytes forgery, re-issue, contradiction
(substitution §14 / §22), or replay is a detectable ``classify_record_pair``
``CRITICAL_CONFLICT``.

**Completion discipline (design #19 §1).** ``VTG-EV-001..012`` are all predicate / model
substrate. Four rows (001 / 003 / 004 / 006) carry an ``EV-L1`` slice in EVIDENCE-REGISTER-002;
the other eight (002 / 005 / 007 / 008 / 009 / 010 / 011 / 012) are minimum ``EV-L2``
(+Security ×6, +Broker ×6 across the register). Phase 1 authors the L1-decidable substrate and
closes **no** VTG-EV item — even the four carry ``/3`` residue plus +Broker (001 / 004) /
+Security (003 / 006) (authoring is not evidence, VER-002-001 §5; ADR §27 line 651 "Written
cases are not completed evidence"). Tag for any claim: "predicate / model substrate only;
VTG-EV-001..012 remain NOT_IMPLEMENTED pending EV-L2/L3 fault injection, adversarial, +Security,
and +Broker evidence; **EV-L1-complete claim forbidden**; no ADR acceptance, restricted-live, or
production is authorized."

Public surface groups by module:

* :mod:`tos.venue.vocabulary` — the venue-axis StrEnums (truthy-untestable decision enums +
  closed ``ActionClass`` + injected ``ConstraintClass`` token).
* :mod:`tos.venue.records` — the nine models (policy / snapshot / decision + injected inputs +
  the dependency-closure substrate) + the all-false authority effect.
* :mod:`tos.venue.predicates` — the core §5.2-§5.4 + predicate-only §6.1-§6.8 decision rules +
  the shared reachability closure kernel.
* :mod:`tos.venue.state` — the §5.1 central ``session_phase_admits`` predicate + the
  ``tos.ordering`` Constraint-Generation REUSE + the produced seam scalars.
"""

from __future__ import annotations

from tos.ordering import Ordering, OrderingEvent, compare_order
from tos.venue._base import (
    ArtifactIntegrityError,
    ArtifactStatus,
    RecordPairKind,
    VenueGateAuthorityEffect,
    classify_record_pair,
)
from tos.venue.predicates import (
    account_constraint_conservative,
    common_mode_reduces_scope,
    decision_binding_exact,
    egress_currentness_active,
    exact_instrument_route_bound,
    exit_not_assumed_admissible,
    gate_authority_separated,
    material_change_closure,
    no_decision_union,
    order_shape_admissible,
    protective_label_no_bypass,
    reopen_revives_nothing,
    stale_decision_rejected_at_egress,
    tradability_conflict_unknown,
    unknown_continuity_invalidates,
)
from tos.venue.records import (
    AccountMarginFacts,
    ActionPhaseAdmission,
    ActionTradability,
    BindingChain,
    ConstraintDependencyClosure,
    DependencyEdge,
    InstrumentRouteFields,
    MaterialConstraintChange,
    OrderAdmissibilityDecision,
    OrderShapeFields,
    PolicyResolution,
    SourceContinuity,
    SourceObservation,
    StageBinding,
    VenueConstraintPolicy,
    VenueConstraintSnapshot,
    VenueShapeConstraints,
)
from tos.venue.state import (
    constraint_generation_monotone,
    order_admissibility_decision_ref_coordinates,
    session_phase_admits,
    venue_admissibility_decision_digest_of,
    venue_constraint_policy_ref_coordinates,
    venue_constraint_snapshot_ref_coordinates,
    venue_snapshot_digest_of,
)
from tos.venue.vocabulary import (
    ActionClass,
    ConstraintClass,
    OrderAdmissibilityResult,
    TradabilityState,
)

__all__ = [
    # base (reused core + venue-local all-false authority)
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "RecordPairKind",
    "classify_record_pair",
    "VenueGateAuthorityEffect",
    # ordering (reused core — append-only Constraint Generation order)
    "Ordering",
    "OrderingEvent",
    "compare_order",
    # vocabulary
    "OrderAdmissibilityResult",
    "TradabilityState",
    "ActionClass",
    "ConstraintClass",
    # records — the nine models + injected inputs
    "VenueConstraintPolicy",
    "VenueConstraintSnapshot",
    "OrderAdmissibilityDecision",
    "InstrumentRouteFields",
    "OrderShapeFields",
    "VenueShapeConstraints",
    "StageBinding",
    "BindingChain",
    "SourceObservation",
    "PolicyResolution",
    "AccountMarginFacts",
    "SourceContinuity",
    "ActionPhaseAdmission",
    "ActionTradability",
    "DependencyEdge",
    "ConstraintDependencyClosure",
    "MaterialConstraintChange",
    # core §5 predicates
    "exact_instrument_route_bound",
    "order_shape_admissible",
    "decision_binding_exact",
    "no_decision_union",
    "material_change_closure",
    # predicate-only §6 predicates
    "tradability_conflict_unknown",
    "account_constraint_conservative",
    "egress_currentness_active",
    "stale_decision_rejected_at_egress",
    "exit_not_assumed_admissible",
    "protective_label_no_bypass",
    "common_mode_reduces_scope",
    "unknown_continuity_invalidates",
    "gate_authority_separated",
    "reopen_revives_nothing",
    # state — §5.1 central predicate + ordering REUSE + produced seam scalars
    "session_phase_admits",
    "constraint_generation_monotone",
    "venue_admissibility_decision_digest_of",
    "venue_snapshot_digest_of",
    "venue_constraint_policy_ref_coordinates",
    "venue_constraint_snapshot_ref_coordinates",
    "order_admissibility_decision_ref_coordinates",
]
