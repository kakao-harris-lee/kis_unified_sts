"""Independent Proposal Approval + Exact-Decision Binding + Consumption Fencing (Phase 1, EV-L1).

**NOT human approval** — ``tos.iap`` is Independent Proposal Approval (ADR-002-023); the ``iap``
token is a module path, never human dual-control approval (which is ADR-002-015; §0.2 / §4
non-scope). A human / emergency / protective label does **not** substitute for this automated
approval (IAP-INV-013 line 182).

Realizes the ADR-002-023 (Independent Proposal Approval, Exact-Decision Binding, and Consumption
Fencing — "IAP") part of IMPLEMENTATION-PLAN-002 §4 Phase 1 (EV-L1), per the ratified design
contract ``docs/plans/2026-07-26-tos-proposal-approval-design.md`` (v1.1). It authors the
**approval-decision rules** — complete-exact-request completeness, the deterministic-restrictive
decision, exact-binding-chain integrity, invalidation dependency-closure, UNKNOWN confinement,
economic-effect continuity, single-use consumption, no-widening / all-false authority separation,
independent-validation declaration, active egress-currentness, stale-generation fencing, and
non-revival — over a four-artifact digest-bound data model plus the ``tos.ordering`` Trading
Approval Generation. It is an **approval-decision kernel, not a serializer / signer / egress
engine** (design #15 §0.2): the production canonical form / policy language / evaluator / registry
/ numeric bounds are Phase-0 (§4 non-scope); every bound / age / registry / mapping value is
injected.

This package is **pure, non-transmitting, non-signing, and clock-free** (design #15 §0.2/§4.6):
frozen pydantic models over injected state + conservative fail-closed predicates. It **cannot**
transmit / serialize / sign / mutate capacity / issue authority / approve-side-effect / transition
an Intent — it produces a request, a decision, and a consumption record; the owning runtime (a
future Independent Approval Service / Intent Registry) consumes them, and orthostate owns the
Intent transition (§3.4/§3.5). There is no "assume-complete" / "assume-current" / "default /
wildcard / substitute / union / widen / coerce / promote-UNKNOWN" path: an ``APPROVE`` / ``True``
comes only from positive proof, everything else is ``DENY`` / ``UNKNOWN`` / ``False`` (design #15
§4.1/§4.2 — the structural seal against the #6 fail-open REJECT lesson).

**Truthy-sentinel structural seal (design #15 §2.2(1)/§4.7, #14 M1 adopted from the start):**
:class:`~tos.iap.vocabulary.ApprovalResult` / :class:`~tos.iap.vocabulary.ConsumptionStatus` /
:class:`~tos.iap.vocabulary.MaterialityVerdict` / :class:`~tos.iap.vocabulary.ConsumptionOutcome`
are *truthy-untestable* ``StrEnum``s — ``__bool__`` raises ``TypeError`` — so a consumer's ``if
result:`` misuse fails loud, not silently open on the truthy denial strings; the mandated consume
gate is the explicit positive-identity comparison (``result is ApprovalResult.APPROVE`` /
``status is ConsumptionStatus.ELIGIBLE``).

**The critical boundary (design #15 §3.5):** :attr:`~tos.iap.vocabulary.ApprovalResult.DENY` (a
decision-result, terminal *for the request*) is **not** orthostate ``IntentState.DENIED`` (an
Intent state after aggregate-risk/capacity denial). An approval ``DENY`` triggers **no** Intent
transition — the Intent stays ``PROPOSED`` (orthostate forbids ``PROPOSED -> DENIED``);
``IntentState.DENIED`` arises downstream (are/rcl). See ``tos/tests/iap/test_seam_orthostate.py``.

It imports only ``pydantic`` + stdlib + ``tos.canonical`` (the digest substrate +
``IndependentIdArtifact`` + ``classify_record_pair``) + ``tos.ordering`` (the Trading Approval
Generation order) — **sibling edge 0** (design #15 §0.4b/§0.4c): unlike the ioc ``ioc -> rcl``
``CapacityVector`` edge (#14, 1 edge), iap REUSES **no** sibling type. All fifteen siblings
(``tos.dsl`` / ``tos.capsule`` / ``tos.ioc`` / ``tos.brokercap`` / ``tos.spg`` / ``tos.venue`` /
``tos.are`` / ``tos.rcl`` / ``tos.orthostate`` / ``tos.liveauth`` / ``tos.authority`` /
``tos.time`` / ``tos.evidence`` / ``tos.protective`` / ``tos.recon``) are consumed / produced as
scalars / digests, so those edges stay 0. Actively verified by the §7.1 import-closure test in
``tos/tests/iap``. **PROMOTE 0건** — iap has no numeric, so not even ``CanonicalDecimal`` is used.

Identity is **independent, not** ``f(digest)`` (design #15 §3.1/§0.4d): each policy / request /
decision / consumption-record generation is an immutable record; a legitimate re-issuance is a new
independent id + supersede link, a same-id / different-bytes substitution is a detectable
``classify_record_pair`` ``CRITICAL_CONFLICT``.

**Completion discipline (design #15 §1):** ``IAP-EV-001..012`` — the six core rows
(001/003/004/007/009/011) carry an EV-L1 slice, the other six are EV-L2+, and even the six have
``/3`` / ``+Security`` / ``+Broker`` residue — Phase 1 authors the L1-decidable substrate and
closes **no** IAP-EV item (authoring is not evidence, VER-002-001 §5). Tag for any claim:
"predicate / model substrate only; IAP-EV-001..012 remain NOT_IMPLEMENTED pending EV-L2/L3 fault
injection, adversarial, +Security, and +Broker evidence; EV-L1-complete claim forbidden."

Public surface groups by module:

* :mod:`tos.iap.vocabulary` — the approval-axis StrEnums (all truthy-untestable).
* :mod:`tos.iap.records` — the four digest-bound artifacts + the all-false authority effect +
  the materiality value model.
* :mod:`tos.iap.predicates` — the core §5 request / decision / binding / closure / confinement
  rules + the predicate-only §6.1/§6.3/§6.4/§6.5 rules.
* :mod:`tos.iap.state` — the §6.2 single-use consumption state machine + the temporal §5.6/§6.6
  continuity / non-revival predicates + the §6.5 generation fence (``tos.ordering`` REUSE).
"""

from __future__ import annotations

from tos.canonical import RecordPairKind, classify_record_pair
from tos.iap._base import (
    AllFalseApprovalAuthority,
    ArtifactIntegrityError,
    ArtifactStatus,
    IndependentIdArtifact,
)
from tos.iap.predicates import (
    active_egress_currentness,
    approval_decision,
    approval_grants_no_authority,
    conflicting_evaluators_unknown,
    exact_binding_holds,
    independent_validation_declared,
    invalidation_closure,
    materiality_is_material,
    no_widening_no_union,
    request_is_complete,
    unknown_confines,
)
from tos.iap.records import (
    ApprovalAuthorityEffect,
    ApprovalConsumptionRecord,
    IndependentApprovalDecision,
    MaterialApprovalChange,
    ProposalApprovalRequest,
    TradingApprovalPolicy,
)
from tos.iap.state import (
    TradingApprovalGeneration,
    consumption_transition,
    economic_effect_outlives,
    recovery_revives_nothing,
    stale_generation_fenced,
)
from tos.iap.vocabulary import (
    ApprovalResult,
    ConsumptionOutcome,
    ConsumptionStatus,
    MaterialityVerdict,
)
from tos.ordering import Ordering, OrderingEvent, compare_order

__all__ = [
    # base (reused core + iap-local all-false authority)
    "AllFalseApprovalAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "IndependentIdArtifact",
    # canonical record-pair classifier (reused core — single-use duplicate/conflict)
    "RecordPairKind",
    "classify_record_pair",
    # ordering (reused core — Trading Approval Generation fence order)
    "Ordering",
    "OrderingEvent",
    "compare_order",
    "TradingApprovalGeneration",
    # vocabulary
    "ApprovalResult",
    "ConsumptionStatus",
    "MaterialityVerdict",
    "ConsumptionOutcome",
    # records
    "TradingApprovalPolicy",
    "ProposalApprovalRequest",
    "IndependentApprovalDecision",
    "ApprovalConsumptionRecord",
    "ApprovalAuthorityEffect",
    "MaterialApprovalChange",
    # core §5 predicates
    "request_is_complete",
    "approval_decision",
    "exact_binding_holds",
    "invalidation_closure",
    "materiality_is_material",
    "unknown_confines",
    # predicate-only §6 predicates
    "independent_validation_declared",
    "no_widening_no_union",
    "approval_grants_no_authority",
    "active_egress_currentness",
    "conflicting_evaluators_unknown",
    # state machine + temporal §5.6/§6.5/§6.6 predicates
    "consumption_transition",
    "economic_effect_outlives",
    "stale_generation_fenced",
    "recovery_revives_nothing",
]
