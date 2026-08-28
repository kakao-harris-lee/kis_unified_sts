"""Post-Trade Economic Obligations and Finality — pure models + predicates (Phase 1, EV-L1).

Realizes the ADR-002-030 (Post-Trade Economic Obligations, Settlement Finality, and
Conservative Account-State Governance — "PTF") part of IMPLEMENTATION-PLAN-002 §4 Phase 1
(EV-L1), per the ratified design contract
``docs/plans/2026-07-27-tos-post-trade-design.md`` (v1.1, operator-ratified 2026-07-27). It
authors the post-trade **decision layer** — finality-dimension orthogonality, obligation-leg
set completeness, fill-to-obligation commit idempotency, no-favourable-default (absence is
not zero, netting needs positive proof, a missing counterleg is adverse), collateral
conservation and cash-kind non-substitution, event-state-is-not-obligation-finality,
statement coverage completeness and source independence, finality-proof class specificity /
non-transferability / currency, the finality-grants-nothing seal, and the single
:class:`PostTradeDisposition` producer — over a four-artifact digest-bound data model.

It is a **decision kernel, not a ledger, not a projector, not an arbiter, not a fence, and
not an egress** (design #24 §0.2). Every one of the following is sibling-owned and **consumed
as an injected produced bool / token / magnitude, never re-authored**:

* capacity reservation, commit, transfer, quarantine, and release arithmetic — **rcl**
  (ADR-002-002/012; §1 line 21 verbatim "The Risk Capacity Ledger remains the sole capacity
  mutation and serialization authority ... an obligation compiler, Reconciliation Service,
  PTOL, position or cash projection, statement processor, evidence service, recovery
  workflow, operator, or finality proof SHALL NOT create, change, quarantine, transfer,
  remap, or release capacity"; PTF-INV-008). rcl's ``TransitionCause.FINAL_QUANTITY_PROOF``
  is the **order-capacity** proof-gated release, **not** post-trade finality (§1 line 23);
* the aggregate-risk projection over the credible state space and the netting **benefit** —
  **are** (ADR-002-021; it already owns ``SETTLEMENT_CASH_CURRENCY``,
  ``MARGIN_COLLATERAL_BORROW_FX_SETTLE_ASSIGN``, ``MISSING_ACK_RECEIPT_AMBIGUITY``, and
  ``BenefitKind.NETTING``, which is why this package projects no risk);
* per-field evidence confidence and contradiction status — **recon** (ADR-002-006; §11).
  PTF-INV-005 fixes the boundary: a "confidence score ... cannot replace exact per-field
  proof", so **confidence (recon) and finality (here) are different propositions**;
* broker / clearing / custodian / banking capability and Final-Quantity-Proof adequacy —
  **brokercap** (ADR-002-018). The ``+Broker`` premise on **all twelve** PTF-EV rows
  discharges through brokercap injection; this package is broker-agnostic and names no
  broker, clearing house, custodian, or bank;
* the non-trade event and transformation identity plus the event workflow lifecycle —
  **nontrade** (ADR-002-010). ADR-002-010 §16 line 309 and ADR-002-030 §17 line 414 are a
  **mutual** deferral: nontrade owns the event side, this package owns "the resulting
  obligation legs and their finality". "lifecycle" and "leg" appear on both axes and mean
  different things;
* external economic instruction transmission and the final egress boundary — **egress**
  (ADR-002-013; §1 line 31 / PTF-INV-016 "PTOL ... SHALL NOT hold a usable external-economic
  credential and route");
* post-trade currentness fencing — **cur** (ADR-002-024; it already owns
  ``DimensionKey.POST_TRADE``); the order / transmission / knowledge state axes —
  **orthostate** (ADR-002-005; §10 line 303-310); authority invalidation and
  no-automatic-re-arm — **authority** / **liveauth** (§22); recovery inventory — **sbr**
  (§24); trustworthy time — **time** (§22); evidence custody and replay — ADR-002-016
  runtime (§24 line 548: a successful replay "is not executed verification evidence").

This package is **pure, non-transmitting, non-enforcing, and clock-free** (design #24
§0.2/§4.4): frozen pydantic models over injected state plus conservative fail-closed
predicates. It **cannot** transmit, mutate or release capacity, make cash available, prove
legal title, or grant permission — it produces decision bools, an
:class:`ObligationCommitOutcome`, a :class:`PostTradeDisposition`, and forward-only records;
the owning runtime (a future PTOL serializer / rcl capacity commit / are risk projection /
cur-egress currentness fence) enforces them. There is no "assume-complete" / "assume-final" /
"assume-independent" path: ``POST_TRADE_ADMISSIBLE`` / ``COMMITTED_ONCE`` / ``True`` comes
only from a positive conjunction identity, and the residual branch of every dispatch is
restrictive (design #24 §4 — the seal against the #6 fail-open REJECT and the #16 CRITICAL
"a GRANT must not be the fall-through residue" lesson).

**Finality proves the LEG, not the CONSEQUENCE.** The most load-bearing safety property of
ADR-002-030 (§10 line 312 verbatim "No lifecycle state creates capacity release, available
cash, legal title, or permission") is realized twice over: by the all-false
:class:`AllFalsePostTradeConsequence`, whose every flag is unconstructable as ``True``, and —
more strongly — by the **structural absence** of any field or predicate that could perform a
release, hold a credential, name a route, or send. A §7 property asserts those phantom names
stay absent.

**Polarity discipline (design #24 §0.1(11)).** :class:`PostTradeDisposition` and
:class:`ObligationCommitOutcome` are **truthy-untestable** (``__bool__`` raises
``TypeError``), so a consuming gate SHALL test
``disposition is PostTradeDisposition.POST_TRADE_ADMISSIBLE`` (identity). An injected sibling
verdict crosses the seam as a bare **token** compared against a local constant (the recon
``FieldConfidenceClass``, the nontrade ``NonTradeEventWorkflowState``, the cur
``CurrentnessAdmission``), never as an imported type — all **19** such tokens are drift-locked
individually by the §7 seam tests. Positive-polarity ``bool | None`` premises are gated
``is True`` only. **Phase-1 posttrade has zero negative-polarity fields** (honest disclosure,
design #24 §7): no-netting is derived structurally from two coexisting non-negative gross
magnitudes, collateral conservation from a magnitude sum, history preservation from the
positive ``original_retained``, and a capacity release or external send is *unrepresentable*.

It imports only ``pydantic`` + stdlib + ``tos.canonical`` (``FrozenModel`` /
``DigestBoundArtifact`` / ``IndependentIdArtifact`` / ``CanonicalDecimal`` /
``classify_record_pair`` / ``RecordPairKind``) + ``tos.ordering`` (append-only Post-Trade
Obligation Generation order). It imports **no sibling at all** — **sibling edge 0, PROMOTE 0**
(design #24 §0.4b/§0.4c; notably the rcl ``CapacityVector``, are ``ProjectedCell``, and recon
``FieldConfidence`` REUSE was considered and **rejected**, because the Phase-1 decision is
set / non-implication / idempotency / conservation logic that needs no vector, cell, or
confidence type, and a posttrade-local risk axis would collide with the are / rcl / recon
namespaces). The §7.1 **allowlist** import-closure test asserts the ``tos.*`` closure ⊆
{``tos.canonical``, ``tos.ordering``, ``tos.posttrade``} and stays robust as new siblings
land.

Identity is **independent, not** ``f(digest)`` (design #24 §3.1/§0.4f): each obligation
version, finality proof, coverage manifest, and break record is an immutable record, and
**two** identity axes stay forgery-detectable — a same **primary** id / different-bytes pair
is a ``classify_record_pair`` ``CRITICAL_CONFLICT``, and a same **idempotency key** /
different-bytes pair is a ``DIVERGENT_EMISSION``. Both fold to ``REJECTED_CONFLICT``: contain
both, no last-write-wins, never a silent double-commit.

**Discipline tag (design #24 §1 / the ratified document-wide tag).** *Predicate / coordinate
substrate only; PTF-EV-001..012 are all ``NOT_IMPLEMENTED``. The five rows that hold an
``EV-L1`` slice at all (001 Fill/FQP vs Post-Trade Obligation Separation, 002
Fee/Tax/Interest/Financing Legs and Corrections, 004
Margin/Collateral/Encumbrance/Haircut/Double-Use, 006
Exercise/Assignment/Delivery/Corporate-Action Obligations, 008 Statement Coverage,
Provenance, Conflict/Common-Mode) hold only that slice and still await their ``/2`` and
``/3`` integration, ``+Broker`` evidence on all twelve rows, ``+Security`` boundary
assessment on 008, and independent review; the other seven rows (003, 005, 007, 009, 010,
011, 012) hold no ``EV-L1`` slice at all and are vocabulary substrate or deferred entirely.*
**No EV-L1-complete claim. Closing PTF-EV = 0.** Authoring is not acceptance: acceptance
comes only from registered, executed, retained, and independently reviewed evidence under
VER-002-001 §5 ("Registration is not execution"; ADR §27 line 633 "Written cases define
obligations only. They are not completed evidence"; ADR §30 line 738 "This ADR authorizes
architecture and implementation planning only"). Nothing here authorizes restricted-live or
production operation, capacity release, external economic transmission, scope promotion, or
automatic re-arm.
"""

from __future__ import annotations

from tos.posttrade._base import (
    AllFalsePostTradeConsequence,
    ArtifactIntegrityError,
    ArtifactStatus,
    DigestBoundArtifact,
    FrozenModel,
    IndependentIdArtifact,
)
from tos.posttrade.predicates import (
    DISPOSITION_CONJUNCTS,
    VOID_TABLE_ROWS,
    absence_is_negative_evidence_only,
    cash_kind_matches_requirement,
    collateral_no_double_use,
    event_state_not_obligation_finality,
    finality_dimensions_orthogonal,
    finality_proof_class_specific,
    finality_proof_current,
    finality_proof_non_transferable,
    margin_collateral_states_distinct,
    missing_counterleg_is_adverse,
    monetary_leg_conservative,
    netting_requires_positive_proof,
    obligation_commit_idempotent,
    obligation_leg_set_complete,
    obligation_legs_from_event_complete,
    post_trade_consequence_all_false,
    post_trade_disposition,
    statement_coverage_complete,
    statement_sources_independent,
)
from tos.posttrade.records import (
    STATEMENT_COVERAGE_SET_AXES,
    CollateralAllocation,
    EconomicObligationRecord,
    MonetaryLeg,
    ObligationLeg,
    ObligationLegScope,
    PostTradeBreakRecord,
    PostTradeFinalityProof,
    StatementCoverageManifest,
)
from tos.posttrade.state import (
    finality_proof_generation_append_only,
    finality_proof_generation_order,
    obligation_axes_not_collapsed,
    obligation_generation_append_only,
    obligation_generation_order,
    statement_manifest_generation_append_only,
    statement_manifest_generation_order,
)
from tos.posttrade.vocabulary import (
    ADVERSE_SCENARIO_MARGIN_COLLATERAL_BORROW_FX_SETTLE_ASSIGN,
    ADVERSE_SCENARIO_MISSING_ACK_RECEIPT_AMBIGUITY,
    BENEFIT_KIND_NETTING,
    BROKER_FQP_ADEQUACY_PRODUCER,
    CAPABILITY_STATUS_VERIFIED,
    CAPACITY_STATE_QUARANTINED_UNKNOWN,
    CAPACITY_STATE_TRAPPED_CONSUMED,
    COMMIT_PROOF_VALIDITY_VALID,
    CURRENTNESS_ADMISSION_ADMIT,
    CURRENTNESS_DIMENSION_POST_TRADE,
    EGRESS_ADMISSION_ADMIT,
    EVENT_OBLIGATION_LEG_MINIMUM_SET,
    EVENT_STATE_TOKENS_THAT_PROVE_NO_FINALITY,
    FIELD_CONFIDENCE_CONFLICTED,
    FIELD_CONFIDENCE_CORROBORATED,
    FIELD_CONFIDENCE_UNKNOWN,
    FQP_DOES_NOT_PROVE,
    FRESHNESS_VERDICT_FRESH,
    INJECTED_SIBLING_TOKENS,
    NONTRADE_EVENT_STATE_APPLIED_LOCAL,
    NONTRADE_EVENT_STATE_RECONCILED,
    OBLIGATION_LIFECYCLE_BRANCH,
    OBLIGATION_LIFECYCLE_LINEAR,
    OBLIGATION_RECORD_FIELD_GROUPS,
    OPPOSITE_DIRECTION_PAIRS,
    ORTHOGONAL_POST_TRADE_AXES,
    PROHIBITED_VERBS,
    PTF_INVARIANT_REALIZATION,
    REJECTED_ALTERNATIVE_REALIZATION,
    RISK_DIMENSION_SETTLEMENT_CASH_CURRENCY,
    TRANSITION_CAUSE_FINAL_QUANTITY_PROOF,
    CashKind,
    EventObligationLegKind,
    FinalityDimensionKind,
    MarginCollateralState,
    ObligationCommitOutcome,
    ObligationLegDirection,
    PostTradeDisposition,
    PostTradeObligationLifecycleState,
    StatementClass,
)

__all__ = [
    # base substrate (re-exported from tos.canonical; PROMOTE 0)
    "AllFalsePostTradeConsequence",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "DigestBoundArtifact",
    "FrozenModel",
    "IndependentIdArtifact",
    # vocabulary — the 9 posttrade StrEnums (§2.2)
    "PostTradeObligationLifecycleState",
    "FinalityDimensionKind",
    "ObligationLegDirection",
    "CashKind",
    "MarginCollateralState",
    "StatementClass",
    "EventObligationLegKind",
    "ObligationCommitOutcome",
    "PostTradeDisposition",
    # vocabulary — structural universes + transcription tables
    "OBLIGATION_LIFECYCLE_LINEAR",
    "OBLIGATION_LIFECYCLE_BRANCH",
    "EVENT_OBLIGATION_LEG_MINIMUM_SET",
    "OPPOSITE_DIRECTION_PAIRS",
    "ORTHOGONAL_POST_TRADE_AXES",
    "FQP_DOES_NOT_PROVE",
    "OBLIGATION_RECORD_FIELD_GROUPS",
    "PTF_INVARIANT_REALIZATION",
    "REJECTED_ALTERNATIVE_REALIZATION",
    "PROHIBITED_VERBS",
    # vocabulary — the 19 injected sibling-coordinate tokens (§3.4)
    "TRANSITION_CAUSE_FINAL_QUANTITY_PROOF",
    "CAPACITY_STATE_TRAPPED_CONSUMED",
    "CAPACITY_STATE_QUARANTINED_UNKNOWN",
    "RISK_DIMENSION_SETTLEMENT_CASH_CURRENCY",
    "ADVERSE_SCENARIO_MARGIN_COLLATERAL_BORROW_FX_SETTLE_ASSIGN",
    "ADVERSE_SCENARIO_MISSING_ACK_RECEIPT_AMBIGUITY",
    "BENEFIT_KIND_NETTING",
    "FIELD_CONFIDENCE_CORROBORATED",
    "FIELD_CONFIDENCE_UNKNOWN",
    "FIELD_CONFIDENCE_CONFLICTED",
    "CAPABILITY_STATUS_VERIFIED",
    "BROKER_FQP_ADEQUACY_PRODUCER",
    "NONTRADE_EVENT_STATE_APPLIED_LOCAL",
    "NONTRADE_EVENT_STATE_RECONCILED",
    "EGRESS_ADMISSION_ADMIT",
    "COMMIT_PROOF_VALIDITY_VALID",
    "FRESHNESS_VERDICT_FRESH",
    "CURRENTNESS_DIMENSION_POST_TRADE",
    "CURRENTNESS_ADMISSION_ADMIT",
    "INJECTED_SIBLING_TOKENS",
    "EVENT_STATE_TOKENS_THAT_PROVE_NO_FINALITY",
    # records — values + the 4 digest-bound artifacts (§2.1)
    "ObligationLegScope",
    "ObligationLeg",
    "MonetaryLeg",
    "CollateralAllocation",
    "EconomicObligationRecord",
    "PostTradeFinalityProof",
    "StatementCoverageManifest",
    "PostTradeBreakRecord",
    "STATEMENT_COVERAGE_SET_AXES",
    # predicates — §5.1 finality orthogonality + leg completeness (PTF-EV-001)
    "finality_dimensions_orthogonal",
    "obligation_leg_set_complete",
    # predicates — §5.2 fill-to-obligation commit idempotency (PTF-EV-001)
    "obligation_commit_idempotent",
    # predicates — §5.3 no-favourable-default (PTF-EV-002)
    "monetary_leg_conservative",
    "netting_requires_positive_proof",
    "missing_counterleg_is_adverse",
    # predicates — §5.4 collateral / margin / cash (PTF-EV-004)
    "collateral_no_double_use",
    "margin_collateral_states_distinct",
    "cash_kind_matches_requirement",
    # predicates — §5.5 event obligation legs + event-state non-implication (PTF-EV-006)
    "obligation_legs_from_event_complete",
    "event_state_not_obligation_finality",
    # predicates — §5.6 statement coverage / independence / absence (PTF-EV-008)
    "statement_coverage_complete",
    "statement_sources_independent",
    "absence_is_negative_evidence_only",
    # predicates — §5.7 finality proof + finality-grants-nothing
    "finality_proof_class_specific",
    "finality_proof_non_transferable",
    "finality_proof_current",
    "post_trade_consequence_all_false",
    # predicates — §5.8 the sole disposition producer (C1)
    "post_trade_disposition",
    "DISPOSITION_CONJUNCTS",
    "VOID_TABLE_ROWS",
    # state — §2.2-1 orthogonality + §3.2 append-only generation order (3 series)
    "obligation_axes_not_collapsed",
    "obligation_generation_order",
    "obligation_generation_append_only",
    "finality_proof_generation_order",
    "finality_proof_generation_append_only",
    "statement_manifest_generation_order",
    "statement_manifest_generation_append_only",
]
