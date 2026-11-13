"""Post-trade vocabulary — the nine posttrade-axis StrEnums (design #24 §2.2).

Spec terms = code terms (design #24 §2; boundary design #1 §2.4). The enums are authored
**verbatim** from ADR-002-030 (§10 obligation lifecycle, §6 PTF-INV-002 finality
dimensions, §5.3/§9 leg directions, §6 PTF-INV-010 cash kinds, §15 margin/collateral
states, §19 statement classes, §17 event obligation legs) plus the two posttrade-local
results (:class:`ObligationCommitOutcome`, :class:`PostTradeDisposition`). Item counts are
transcribed against the ADR line ranges and re-asserted by a §7 property test (the #16 M4
truncated-transcription lesson, series discipline 2 — count cross-checks are exhaustive):
§10 line 287-301 = 8 + 4 = **12** lifecycle states, §6 PTF-INV-002 line 156 = **10**
finality dimensions, §5.3 line 116 / §9 line 273 = **8** leg directions, §6 PTF-INV-010
line 188 = **6** cash kinds, §15 line 385 = **8** margin / collateral states, §19 line 442 =
**3** statement classes, §17 line 416 = **9** event obligation legs, **6** commit outcomes,
**5** dispositions.

**Coordinate non-collapse (design #24 §2.2-6 — this module is the canonical home of the
rule).** These are the **post-trade obligation / finality / statement** axes. They are
distinct coordinate systems from:

* orthostate ``IntentState.CLOSED`` (``vocabulary.py:32``) and ``KnowledgeState.RECONCILED``
  (``:121``) — the intent / knowledge axes. Our
  :attr:`PostTradeObligationLifecycleState.CLOSED` and
  :attr:`PostTradeObligationLifecycleState.FINALITY_PROVEN` overlap them in wording, never
  in type: ADR §10 line 305 keeps the obligation-lifecycle axis "orthogonal to ADR-002-006
  Knowledge/Evidence State", so it is a **sixth** axis beside orthostate's five;
* rcl ``CapacityState`` (``vocabulary.py:29/30``) and ``TransitionCause.FINAL_QUANTITY_PROOF``
  (``:94``) — the economic capacity axis. rcl's Final Quantity Proof is the **proof-gated
  release of order capacity**; our :attr:`FinalityDimensionKind.ORDER_FQP` is one of **ten**
  post-trade dimensions and implies none of the other nine (§1 line 23 "It does not prove
  any post-trade obligation final");
* recon ``FieldConfidenceClass`` (``vocabulary.py:26``) — the per-field **evidence
  confidence** axis. PTF-INV-005: a "confidence score ... cannot replace exact per-field
  proof", so confidence (recon) and finality (this package) are **different propositions**;
* are ``RiskDimensionKind`` / ``AdverseScenarioKind`` / ``BenefitKind.NETTING``
  (``vocabulary.py:61/65/112/131``) — the aggregate-risk axis. are's netting **benefit** is
  not our obligation-leg **no-netting** (receivable and payable stay gross), and neither is
  nontrade's transition-envelope no-netting: **three different propositions** (§0.4d);
* nontrade ``NonTradeEventWorkflowState`` (``vocabulary.py:165``) and
  ``CredibleTransitionLegKind`` (``:213``) — the non-trade **event** axis. ADR-002-010 §16
  line 309 and ADR-002-030 §17 line 414 are **mutual** deferrals: nontrade owns event and
  transformation identity plus the event workflow lifecycle, this package owns the
  resulting obligation legs, the obligation lifecycle, and their finality. "lifecycle" and
  "leg" appear on both axes and mean different things;
* iap ``ConsumptionOutcome.IDEMPOTENT_REPLAY`` (``vocabulary.py:165``, authorization-token
  single-use), rcl ``ApplyReason.IDEMPOTENT_REPLAY`` (capacity-command), and nontrade
  ``CorrectionReversalOutcome.IDEMPOTENT_REPLAY`` (economic-event application) — **different
  propositions** from our fill-to-obligation-commit
  :attr:`ObligationCommitOutcome.IDEMPOTENT_REPLAY` (design #24 §0.4e). The four are
  independent downstreams of the one canonical ``classify_record_pair`` primitive and never
  import each other.

Token overlap is intentional (the ADR uses the same words on several axes), so coordinate
non-collapse rests on **distinct types + non-import**: ``tos.posttrade`` imports **none** of
those siblings (sibling edge 0, design #24 §0.4b/§0.4c), so a value from one axis can never
be coerced onto another. Where a sibling token must nonetheless be *recognized* (an injected
verdict crosses the seam as a bare string / StrEnum member), this module fixes the token as
a **local constant** and a §7 seam test locks it against the real sibling member (the
nontrade ``ORDER_ADMISSIBILITY_ADMISSIBLE`` / egress ``CommitProofValidity`` precedent).

This module names **no** concrete broker, clearing house, custodian, or bank
(broker-agnostic — project memory ``tos-spec-broker-agnostic``; design #24 §0.1; this ADR
carries ``+Broker`` on **all twelve** of its evidence rows, so the discipline is enforced
especially strictly here) and hardcodes **no** numeric amount, ratio, haircut, timing, or
age bound (ADR §29 Q9/Q10 leave every numeric bound an Open Question and all 19 VP-002 PTF
keys are ``null`` / ``TBD``): every such value is an injected ``CanonicalDecimal`` or plain
generation ``int`` parameter (design #24 §8). An enum member is a structural axis, never a
limit.

**Discipline tag (design #24 §1).** *Predicate / coordinate substrate only. Closing
PTF-EV = 0; no EV-L1-complete claim.*

Pure module: stdlib only; no ``shared.*``, no sibling ``tos.*`` (design #24 §0.3).
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "EventObligationLegKind",
    "FinalityDimensionKind",
    "ObligationLegDirection",
    "PostTradeObligationLifecycleState",
]


class PostTradeObligationLifecycleState(StrEnum):
    """The 8 + 4 obligation lifecycle states (ADR §10 line 287-301 verbatim; count = 12).

    §10 line 287-301 verbatim lifecycle::

        POTENTIAL -> RECOGNIZED -> DUE -> IN_FLIGHT -> PARTIALLY_SATISFIED
                  -> SATISFIED_PENDING_FINALITY -> FINALITY_PROVEN -> CLOSED
        Any state -> BREAK_OPEN
        Any state -> CORRECTION_PENDING
        Any state -> FAILED_OR_TRAPPED
        Any state -> SUPERSEDED

    §10 line 312 verbatim: "``SATISFIED_PENDING_FINALITY`` is not final. ``FINALITY_PROVEN``
    proves only the exact declared leg and proof class. ``CLOSED`` preserves immutable
    lineage and can be superseded by a later correction without destructive overwrite. **No
    lifecycle state creates capacity release, available cash, legal title, or permission.**"
    ⇒ a lifecycle state is a **non-authoritative coordinate**; the type-level seal is the
    all-false :class:`~tos.posttrade._base.AllFalsePostTradeConsequence` (design #24
    §4.7/§5.7).

    **Transition validity is NOT Phase-1 (design #24 §2.2-1).** Phase 1 authors the
    *vocabulary* + finality-grants-nothing + the §10 line 303-310 orthogonality structure
    only. Whether ``SATISFIED_PENDING_FINALITY -> FINALITY_PROVEN`` may occur depends on the
    rcl capacity state, the recon field confidence, the field-specific finality proof, and
    the statement coverage — all runtime gates (EV-L2/L3). There is deliberately **no**
    transition predicate in this package, and nothing here *sets* a state.

    **Orthogonality (§10 line 303-310).** This axis is a **sixth** coordinate beside the
    orthostate order / transmission / knowledge / capacity / authority axes, "orthogonal to
    ADR-002-006 Knowledge/Evidence State"; :data:`ORTHOGONAL_POST_TRADE_AXES` names the five
    axes that :class:`~tos.posttrade.records.EconomicObligationRecord` keeps as **separate
    injected fields**. ``CLOSED`` here is the *obligation* axis and is **not** orthostate
    ``IntentState.CLOSED`` (``orthostate/vocabulary.py:32``); ``FINALITY_PROVEN`` is **not**
    orthostate ``KnowledgeState.RECONCILED`` (``:121``) and **not** nontrade
    ``NonTradeEventWorkflowState.RECONCILED`` (``nontrade/vocabulary.py:165``).
    """

    # linear (8) — §10 line 287-296
    POTENTIAL = "POTENTIAL"
    RECOGNIZED = "RECOGNIZED"
    DUE = "DUE"
    IN_FLIGHT = "IN_FLIGHT"
    PARTIALLY_SATISFIED = "PARTIALLY_SATISFIED"
    SATISFIED_PENDING_FINALITY = "SATISFIED_PENDING_FINALITY"
    FINALITY_PROVEN = "FINALITY_PROVEN"
    CLOSED = "CLOSED"
    # branch (4) — §10 line 298-301 ("Any state ->")
    BREAK_OPEN = "BREAK_OPEN"
    CORRECTION_PENDING = "CORRECTION_PENDING"
    FAILED_OR_TRAPPED = "FAILED_OR_TRAPPED"
    SUPERSEDED = "SUPERSEDED"


class FinalityDimensionKind(StrEnum):
    """The 10 orthogonal finality dimensions (ADR §6 PTF-INV-002 line 156; count = 10).

    PTF-INV-002 line 156 verbatim enumerates "Order FQP, trade capture, instruction
    acceptance, settlement, cash availability, collateral eligibility, custody title, fee
    finality, borrow discharge, and corporate-action finality" and states that they "**do
    not imply one another**". Each member with its ADR anchor::

        ORDER_FQP                  §12 line 338 — broker-order final cumulative filled
                                   quantity + zero remaining executable quantity
        TRADE_CAPTURE              §12 line 341 — trade capture free from later bust /
                                   correction
        INSTRUCTION_ACCEPTANCE     §14 line 366 — settlement-instruction acceptance
        SETTLEMENT                 §14 — settlement completion
        CASH_AVAILABILITY          §14 line 370 — withdrawable / available cash
        COLLATERAL_ELIGIBILITY     §15 — collateral eligibility
        CUSTODY_TITLE              §18 line 428 — custody / legal-title finality
        FEE_FINALITY               §13 — fee / tax / interest / financing finality
        BORROW_DISCHARGE           §16 — borrow discharge
        CORPORATE_ACTION_FINALITY  §17 — corporate-action finality

    **A dimension is enum membership, never a boolean.** Whether a dimension is proven is
    carried per-dimension by a :class:`~tos.posttrade.records.PostTradeFinalityProof` and an
    injected ``dimension_proof_present`` map; UNKNOWN is the default (PTF-INV-006), and §5.10
    line 144 forbids a "universal trade-level boolean". The ten-way non-implication is the
    core of PTF-EV-001 (§4.1/§5.1) and is realized **structurally**:
    :func:`~tos.posttrade.predicates.finality_dimensions_orthogonal` reads **only** the
    claimed dimension's own proof entry, so no other dimension's proof has a path to the
    verdict.

    The six §12 line 340-345 "It does not prove:" items are transcribed in
    :data:`FQP_DOES_NOT_PROVE`. ``ORDER_FQP`` PROVEN therefore leaves the other **nine**
    dimensions UNKNOWN (§1 line 23 "It does not prove any post-trade obligation final").

    **Closed against the ADR enumeration, not against the world (design #24 §10.4 G1).** The
    ten are PTF-INV-002 verbatim; a broker- or custody-specific dimension (a banking-rail
    settlement, say) would be added only through the Phase-0 finality-recipe approval (ADR
    §29 Q3), and the structural non-implication is unchanged by any such addition. Phase 1
    anchors exactly on the ADR enumeration and invents nothing.
    """

    ORDER_FQP = "ORDER_FQP"
    TRADE_CAPTURE = "TRADE_CAPTURE"
    INSTRUCTION_ACCEPTANCE = "INSTRUCTION_ACCEPTANCE"
    SETTLEMENT = "SETTLEMENT"
    CASH_AVAILABILITY = "CASH_AVAILABILITY"
    COLLATERAL_ELIGIBILITY = "COLLATERAL_ELIGIBILITY"
    CUSTODY_TITLE = "CUSTODY_TITLE"
    FEE_FINALITY = "FEE_FINALITY"
    BORROW_DISCHARGE = "BORROW_DISCHARGE"
    CORPORATE_ACTION_FINALITY = "CORPORATE_ACTION_FINALITY"


class ObligationLegDirection(StrEnum):
    """The 8 obligation-leg directions (ADR §5.3 line 116 / §9 line 273; count = 8).

    §5.3 line 116 verbatim: an obligation's exact leg set covers its "debit, credit,
    delivery, receipt, encumbrance, release, return, and contingent effect" (individually
    counted: 8).

    **Polarity axis (design #24 §4.5-A).** ``DEBIT`` (payable) ↔ ``CREDIT`` (receivable),
    ``DELIVERY`` ↔ ``RECEIPT``, and ``ENCUMBRANCE`` ↔ ``RELEASE`` are opposite-direction
    pairs (:data:`OPPOSITE_DIRECTION_PAIRS`), and netting an *uncertain* receivable against
    a payable is precisely the fail-open PTF-INV-007 forbids ("uncertain receivable does not
    fund a payable"; §25.5 rejected "Pending receivables may fund payables").

    **Netting is derived structurally, never declared (design #24 §0.4d).** There is no
    ``netted`` / ``offset`` flag anywhere: a netting is valid only when both legs coexist as
    **present, non-negative gross magnitudes** in the **same scope** with an injected
    enforceable-netting proof (:func:`~tos.posttrade.predicates
    .netting_requires_positive_proof`). A caller cannot forge it with a boolean because
    there is no boolean to forge — the absence of netting is proven by the two magnitudes
    still standing side by side.

    **Coordinate non-collapse (§2.2-6).** This is the *obligation* axis. It is not the
    nontrade transition axis (``CredibleTransitionLegKind``, whose "leg" is a credible
    economic **state** during an event), not the are aggregate-risk axis
    (``RiskDimensionKind`` / ``BenefitKind.NETTING``), and not the rcl capacity axis
    (``CapacityVector`` dimensions).
    """

    DEBIT = "DEBIT"
    CREDIT = "CREDIT"
    DELIVERY = "DELIVERY"
    RECEIPT = "RECEIPT"
    ENCUMBRANCE = "ENCUMBRANCE"
    RELEASE = "RELEASE"
    RETURN = "RETURN"
    CONTINGENT = "CONTINGENT"


class EventObligationLegKind(StrEnum):
    """The 9 event-obligation leg kinds (ADR §17 line 416 verbatim; count = 9).

    §17 line 416 verbatim: an exercise / assignment / expiry / delivery / cash-settlement /
    conversion / redemption / distribution / tender / rights / corporate-action event "SHALL
    model every credible **asset, cash, fee, tax, financing, margin, borrow, custody, and
    delivery** leg" (individually counted: 9).

    **A different axis from :class:`ObligationLegDirection` (design #24 §2.2-5b).** This
    enum is the leg **type** — *what the obligation is about* — whereas a direction is that
    leg's **sign** (payable / receivable, delivery / receipt). The two are composed on
    :class:`~tos.posttrade.records.ObligationLeg`, never fused.

    Authored as an enum rather than a bare ``frozenset[str]`` precisely so the nine members
    are **drift-locked** by a §7 value-binding property (design #24 m6): a typo in a caller's
    required-subset string can no longer silently shrink the completeness requirement.
    The applicable subset is **event-class-parametric** and is injected into
    :func:`~tos.posttrade.predicates.obligation_legs_from_event_complete`, which fails closed
    on an **empty** required set rather than defaulting to
    :data:`EVENT_OBLIGATION_LEG_MINIMUM_SET`.
    """

    ASSET = "ASSET"
    CASH = "CASH"
    FEE = "FEE"
    TAX = "TAX"
    FINANCING = "FINANCING"
    MARGIN = "MARGIN"
    BORROW = "BORROW"
    CUSTODY = "CUSTODY"
    DELIVERY = "DELIVERY"


# ---------------------------------------------------------------------------
# Structural universes + transcription tables
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Injected sibling-coordinate tokens (design #24 §3.4 — token, never type)
# ---------------------------------------------------------------------------
# ``tos.posttrade`` holds sibling edge 0, so a verdict arriving from a sibling crosses the
# seam as a bare token. Each constant below is the *token* of a real sibling member; a §7
# seam test imports the sibling **in the test only** and asserts the token still equals the
# live member (drift lock — the nontrade / afg / replacement ``ADMISSIBILITY_ADMISSIBLE``
# precedent). All **19** are individually counted in :data:`INJECTED_SIBLING_TOKENS` (the
# #21 MINOR-1 "13 listed, 1 missing" lesson). A token is compared with ``==`` (a ``StrEnum``
# member equals its value); ``is`` identity is reserved for this package's **own** enums, and
# ``bool(token)`` is never used — a real producer's ``__bool__`` may raise and even a bare
# string would be truthy.
