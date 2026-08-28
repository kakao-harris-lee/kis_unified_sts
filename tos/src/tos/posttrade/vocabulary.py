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
    # the 9 vocabulary enums (§2.2)
    "PostTradeObligationLifecycleState",
    "FinalityDimensionKind",
    "ObligationLegDirection",
    "CashKind",
    "MarginCollateralState",
    "StatementClass",
    "EventObligationLegKind",
    "ObligationCommitOutcome",
    "PostTradeDisposition",
    # structural universes + transcription tables
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
    # injected sibling-coordinate tokens (§3.4) — 19, individually counted
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
]


class _NonTruthyStrEnum(StrEnum):
    """A ``StrEnum`` that is deliberately **not truthy-testable** (design #24 §2.2-8).

    Every member is a non-empty string, so a bare ``if result:`` / ``bool(result)`` would
    read a denial member (``POST_TRADE_TRAPPED`` / ``POST_TRADE_BLOCK_NEW_RISK`` /
    ``REJECTED_CONFLICT`` ...) as truthy — a silent fail-open that reads "blocked" as
    "admitted". :meth:`__bool__` therefore raises ``TypeError`` on every member, so the
    misuse surfaces as a loud runtime error rather than a silent pass. Consumers MUST use
    the explicit positive-identity gate (``x is ENUM.SAFE_VALUE``). Isomorphic to the
    nontrade ``_NonTruthyStrEnum`` (``nontrade/vocabulary.py:95``), the venue
    ``OrderAdmissibilityResult`` seal (``venue/vocabulary.py:56``), and the iap
    ``_NonTruthyStrEnum`` (``iap/vocabulary.py:50``); authored **locally-fresh** here
    (sibling edge 0 — design #24 §0.4b). ``is`` identity, ``.value``, hashing, set
    membership, and ``model_dump`` are all unaffected (none calls ``__bool__``).
    """

    def __bool__(self) -> bool:
        """Reject truthiness testing outright (truthy-sentinel seal, design #24 §2.2-8).

        Raises:
            TypeError: always — the enum is not truthy-testable. Use the explicit
                positive identity gate (e.g.
                ``disposition is PostTradeDisposition.POST_TRADE_ADMISSIBLE``;
                ``outcome is ObligationCommitOutcome.COMMITTED_ONCE``); a bare
                ``if disposition:`` would fail open on the truthy denial strings.
        """
        raise TypeError(
            f"{type(self).__name__} is not truthy-testable — use an explicit positive "
            "identity gate (e.g. "
            "`disposition is PostTradeDisposition.POST_TRADE_ADMISSIBLE`; "
            "`outcome is ObligationCommitOutcome.COMMITTED_ONCE`) per the truthy-sentinel "
            "seal (design #24 §2.2-8/§4). Every denial member is a non-empty string and a "
            "bare `if result:` would read a block / rejection as permission."
        )


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


class CashKind(StrEnum):
    """The 6 non-substitutable cash kinds (ADR §6 PTF-INV-010 line 188; count = 6).

    PTF-INV-010 line 188 verbatim: "Ledger cash, pending cash, settled cash, withdrawable
    cash, buying power, and collateral-eligible cash remain distinct" and "**cannot be
    silently substituted**" (individually counted: 6). §14 line 375: sale proceeds, expected
    dividends, pending FX, receivables, and buying power are **not** settled reusable cash.
    §25.4 rejects "Buying power is available cash" outright — realized here as a **type
    distinction**, so a substitution is a mismatch rather than an accounting opinion
    (:func:`~tos.posttrade.predicates.cash_kind_matches_requirement`).

    **Substrate boundary (honest disclosure, design #24 §1/§6.1).** The vocabulary and the
    non-substitution structure are the EV-L1 slice; the **proof** of settlement completion
    and cash availability — the buying-power-to-withdrawable transition — is PTF-EV-003
    ``EV-L2/3+Broker`` and is **not** authored here. Phase 1 keeps availability UNKNOWN and
    lets :func:`~tos.posttrade.predicates.post_trade_disposition` land on
    ``POST_TRADE_TRAPPED``.
    """

    LEDGER_CASH = "LEDGER_CASH"
    PENDING_CASH = "PENDING_CASH"
    SETTLED_CASH = "SETTLED_CASH"
    WITHDRAWABLE_CASH = "WITHDRAWABLE_CASH"
    BUYING_POWER = "BUYING_POWER"
    COLLATERAL_ELIGIBLE_CASH = "COLLATERAL_ELIGIBLE_CASH"


class MarginCollateralState(StrEnum):
    """The 8 margin / collateral states (ADR §15 line 385 verbatim; count = 8).

    §15 line 385 verbatim enumerates "a margin observation, margin call, collateral request,
    instruction acknowledgement, pledged collateral, accepted collateral, available excess,
    and confirmed release" (individually counted: 8) and states "**No one state implies
    another**".

    §15 line 386 verbatim (PTF-INV-011): "The same collateral unit SHALL NOT be counted as
    both free and encumbered, pledged to two obligations, or reusable before confirmed
    release" — realized as a **conservation** check over
    :class:`~tos.posttrade.records.CollateralAllocation` magnitudes
    (:func:`~tos.posttrade.predicates.collateral_no_double_use`), never as a flag. §15 line
    387: a broker-favourable margin / buying-power / collateral figure is a Critical Input
    and a **ceiling**, not an unconditional proof — it arrives as an injected coordinate
    (brokercap ``POSITIONS_BALANCES_MARGIN``) and is never re-decided here.

    :attr:`CONFIRMED_RELEASE` is the **only** state that permits a unit to be re-allocated,
    which is why it is the positive premise the reuse check demands rather than a
    ``not_yet_released`` negative flag.
    """

    MARGIN_OBSERVATION = "MARGIN_OBSERVATION"
    MARGIN_CALL = "MARGIN_CALL"
    COLLATERAL_REQUEST = "COLLATERAL_REQUEST"
    INSTRUCTION_ACKNOWLEDGEMENT = "INSTRUCTION_ACKNOWLEDGEMENT"
    PLEDGED_COLLATERAL = "PLEDGED_COLLATERAL"
    ACCEPTED_COLLATERAL = "ACCEPTED_COLLATERAL"
    AVAILABLE_EXCESS = "AVAILABLE_EXCESS"
    CONFIRMED_RELEASE = "CONFIRMED_RELEASE"


class StatementClass(StrEnum):
    """The 3 statement classes (ADR §19 line 442; count = 3).

    §19 line 442 requires the "preliminary/final classification, restatement" to be carried
    explicitly; the three members are ``PRELIMINARY``, ``FINAL``, and ``REVISED``. §19 line
    448 verbatim: being "``FINAL``, contractual, signed, or independently delivered does not
    make it unconditional truth outside the approved proof recipe" — so ``FINAL`` here is a
    **classification coordinate**, never a permission, and
    :func:`~tos.posttrade.predicates.statement_coverage_complete` still demands the full
    coverage conjunction on top of it.

    A ``PRELIMINARY`` manifest can never be complete coverage (§19 line 450): it is by
    construction subject to restatement.
    """

    PRELIMINARY = "PRELIMINARY"
    FINAL = "FINAL"
    REVISED = "REVISED"


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


class ObligationCommitOutcome(_NonTruthyStrEnum):
    """The 6 fill-to-obligation commit outcomes (design #24 §2.2-6; count = 6).

    ::

        COMMITTED_ONCE        lineage present + original retained + ``prior is None``
                              (the first commit — the classify **pre-gate**, §5.2):
                              obligation effect count -> 1
        IDEMPOTENT_REPLAY     ``RecordPairKind.IDEMPOTENT_DUP`` (same primary *or*
                              idempotency id, same canonical bytes): a harmless re-apply
                              of a late fill, effect count unchanged (§12 line 347)
        REJECTED_CONFLICT     **both** forgery axes fold here — ``CRITICAL_CONFLICT``
                              (same **primary** id, different bytes: obligation forgery)
                              and ``DIVERGENT_EMISSION`` (same **idempotency** id,
                              different bytes: two different fills claiming one commit
                              key). Contain both, no last-write-wins merge, never a silent
                              double-commit
        REJECTED_NO_LINEAGE   a record that claims to correct something carries no
                              ``supersedes_ref`` — §20 line 460 forbids relabelling
        REJECTED_OVERWRITE    the original version was not retained — §11 line 330 / §20
                              line 460 forbid destructive rewrite
        REJECTED_UNKNOWN      ``DISTINCT`` (the prior shares neither identity axis — a
                              caller selection-contract violation) or ``NOT_COMPARABLE``
                              (a pre-issuance null digest): undecidable ⇒ fail closed

    **Only ``COMMITTED_ONCE`` increases the obligation effect count**, and it is reached only
    through the positive pre-gate conjunction — never as a dispatch residue (design #24 §4.6;
    the #16 CRITICAL "a GRANT must not be the fall-through residue" lesson). A late fill
    re-applied N >= 2 times therefore yields exactly **one** economic effect (§12 line 347).

    **Coordinate non-collapse (§2.2-6 / §0.4e).** :attr:`IDEMPOTENT_REPLAY` is the
    *fill-to-obligation-commit* axis. It is a **different type and a different proposition**
    from iap ``ConsumptionOutcome.IDEMPOTENT_REPLAY`` (``iap/vocabulary.py:165``,
    authorization-token single-use consumption), rcl ``ApplyReason.IDEMPOTENT_REPLAY``
    (capacity-command), and nontrade ``CorrectionReversalOutcome.IDEMPOTENT_REPLAY``
    (economic-event application). All four are independent downstreams of canonical
    ``classify_record_pair``; ``tos.posttrade`` imports none of those siblings (phantom edge
    blocked, design #24 §0.4e).

    **Truthy-sentinel seal.** Every member is a non-empty string, so ``if outcome:`` would
    read ``REJECTED_CONFLICT`` as truthy. Truthy-untestable (``__bool__`` raises); the
    mandated consume gate is ``outcome is ObligationCommitOutcome.COMMITTED_ONCE`` (or
    ``is IDEMPOTENT_REPLAY``).
    """

    COMMITTED_ONCE = "COMMITTED_ONCE"
    IDEMPOTENT_REPLAY = "IDEMPOTENT_REPLAY"
    REJECTED_CONFLICT = "REJECTED_CONFLICT"
    REJECTED_NO_LINEAGE = "REJECTED_NO_LINEAGE"
    REJECTED_OVERWRITE = "REJECTED_OVERWRITE"
    REJECTED_UNKNOWN = "REJECTED_UNKNOWN"


class PostTradeDisposition(_NonTruthyStrEnum):
    """The 5 post-trade dispositions (design #24 §2.2-8; count = 5).

    ::

        POST_TRADE_ADMISSIBLE          every obligation leg complete, finality proven where
                                       required, no break, no conflict, no double-use —
                                       reached **only** by the §5.8 positive conjunction of
                                       all sixteen bools plus an accepted commit outcome, a
                                       CORROBORATED field confidence, and a positively
                                       proven availability; never by fall-through
        POST_TRADE_BLOCK_NEW_RISK      §1 line 25 / PTF-INV-006 — an UNKNOWN post-trade
                                       state "consumes conservative capacity and blocks
                                       affected new risk"
        POST_TRADE_QUARANTINED_UNKNOWN PTF-INV-006 — unattributable or undecidable
                                       post-trade state; capacity-consuming, never "no risk"
        POST_TRADE_TRAPPED             §14 line 373 trapped cash / §18 line 430 "asset ...
                                       SHALL NOT disappear" — an identified, bounded
                                       exposure that cannot be exited
        POST_TRADE_CONFLICTED          §20 — a break, contradicted evidence, a contained
                                       record-pair conflict, a common-mode statement source,
                                       a collateral double-use, or a non-class-specific /
                                       transferred finality proof

    :func:`~tos.posttrade.predicates.post_trade_disposition` is the **sole producer**
    (design #24 §5.8 C1): every one of the twenty-two §4.8 void-table rows folds through it,
    so there is no ownerless "handled elsewhere" path. Its five ranks are a **total order** —
    ``CONFLICTED`` > ``QUARANTINED_UNKNOWN`` > ``TRAPPED`` > ``BLOCK_NEW_RISK`` >
    ``ADMISSIBLE`` — so a simultaneous conflict / quarantine / trap always returns the **most
    conservative** member. The rank rationale (design #24 §5.8 Q2): a ``CONFLICTED`` state is
    an *active contradiction* (contain both, no merge) and is the most severe; a
    ``QUARANTINED_UNKNOWN`` state is unattributable and expands conservatism across the whole
    greatest-credible dependency closure (**unbounded** scope); a ``TRAPPED`` state is an
    identified and **bounded** exposure — the wider-scope constraint dominates the narrower.

    **A disposition grants nothing** (§10 line 312 / §4.7): even ``POST_TRADE_ADMISSIBLE``
    releases no capacity, makes no cash available, proves no title, grants no permission, and
    transmits nothing — the consuming runtime (rcl capacity commit / transfer, are risk
    projection, cur / egress currentness fence) enforces.

    **Truthy-sentinel seal.** All five members are non-empty strings, so ``if disposition:``
    would read ``POST_TRADE_TRAPPED`` as permission. Truthy-untestable (``__bool__`` raises);
    the mandated consume gate is
    ``disposition is PostTradeDisposition.POST_TRADE_ADMISSIBLE``.
    """

    POST_TRADE_ADMISSIBLE = "POST_TRADE_ADMISSIBLE"
    POST_TRADE_BLOCK_NEW_RISK = "POST_TRADE_BLOCK_NEW_RISK"
    POST_TRADE_QUARANTINED_UNKNOWN = "POST_TRADE_QUARANTINED_UNKNOWN"
    POST_TRADE_TRAPPED = "POST_TRADE_TRAPPED"
    POST_TRADE_CONFLICTED = "POST_TRADE_CONFLICTED"


# ---------------------------------------------------------------------------
# Structural universes + transcription tables
# ---------------------------------------------------------------------------

#: The §10 line 287-296 linear lifecycle (8 states) in ADR declaration order. A
#: **structural transcription**, never a transition table: transition validity is not
#: Phase-1 (design #24 §2.2-1).
OBLIGATION_LIFECYCLE_LINEAR: tuple[PostTradeObligationLifecycleState, ...] = (
    PostTradeObligationLifecycleState.POTENTIAL,
    PostTradeObligationLifecycleState.RECOGNIZED,
    PostTradeObligationLifecycleState.DUE,
    PostTradeObligationLifecycleState.IN_FLIGHT,
    PostTradeObligationLifecycleState.PARTIALLY_SATISFIED,
    PostTradeObligationLifecycleState.SATISFIED_PENDING_FINALITY,
    PostTradeObligationLifecycleState.FINALITY_PROVEN,
    PostTradeObligationLifecycleState.CLOSED,
)

#: The 4 non-linear §10 line 298-301 states ("Any state ->").
OBLIGATION_LIFECYCLE_BRANCH: tuple[PostTradeObligationLifecycleState, ...] = (
    PostTradeObligationLifecycleState.BREAK_OPEN,
    PostTradeObligationLifecycleState.CORRECTION_PENDING,
    PostTradeObligationLifecycleState.FAILED_OR_TRAPPED,
    PostTradeObligationLifecycleState.SUPERSEDED,
)

#: The §17 line 416 nine-leg universe. A *convenience* universe for callers and tests,
#: **not** a required set: the required subset is event-class-parametric and is injected
#: into :func:`~tos.posttrade.predicates.obligation_legs_from_event_complete`, which fails
#: closed on an **empty** required set (design #24 §5.5) rather than defaulting to this one.
EVENT_OBLIGATION_LEG_MINIMUM_SET: frozenset[EventObligationLegKind] = frozenset(
    EventObligationLegKind
)

#: Truth-table A polarity pairs (design #24 §4.5-A / §2.2-3): the **3** opposite-direction
#: obligation-leg pairs, each listed in both orders (6 ordered pairs). Netting an uncertain
#: member of a pair against its opposite is the PTF-INV-007 fail-open; a counterleg is a
#: counterleg only when it is the *opposite* direction of the declared leg
#: (:func:`~tos.posttrade.predicates.missing_counterleg_is_adverse`).
OPPOSITE_DIRECTION_PAIRS: frozenset[
    tuple[ObligationLegDirection, ObligationLegDirection]
] = frozenset(
    {
        (ObligationLegDirection.DEBIT, ObligationLegDirection.CREDIT),
        (ObligationLegDirection.CREDIT, ObligationLegDirection.DEBIT),
        (ObligationLegDirection.DELIVERY, ObligationLegDirection.RECEIPT),
        (ObligationLegDirection.RECEIPT, ObligationLegDirection.DELIVERY),
        (ObligationLegDirection.ENCUMBRANCE, ObligationLegDirection.RELEASE),
        (ObligationLegDirection.RELEASE, ObligationLegDirection.ENCUMBRANCE),
    }
)

#: The 5 axes ADR §10 line 303-310 requires the obligation-lifecycle state to stay
#: **orthogonal** to (the orthostate coordinate system, ADR-002-005).
#: :class:`~tos.posttrade.records.EconomicObligationRecord` keeps one **separate injected
#: field** per axis (each carrying a sibling-owned token this package consumes and never
#: sets), and a §7 property asserts the field set is complete and disjoint from
#: ``lifecycle_state`` — the posttrade-owned **sixth** coordinate.
ORTHOGONAL_POST_TRADE_AXES: tuple[str, ...] = (
    "order_state",
    "knowledge_state",
    "capacity_state",
    "authority_state",
    "evidence_confidence_state",
)

#: ADR §12 line 340-345 — the **6** things a Final Quantity Proof explicitly "does not
#: prove", each paired with the :class:`FinalityDimensionKind` that owns it. Transcription
#: only (design #24 §2.2-7): a §7 property asserts the count is 6 and that
#: :func:`~tos.posttrade.predicates.finality_dimensions_orthogonal` leaves every one of them
#: UNKNOWN when only ``ORDER_FQP`` carries a proof.
#:
#: The ADR line is carried as a **string anchor, never a number**: it is a citation
#: coordinate, not a quantity, and keeping it non-numeric leaves the §8.0 "no numeric literal
#: other than the structural 0 / 1" source scan at full strength (a scanner that had to
#: whitelist citation numbers could be talked into whitelisting a policy bound).
FQP_DOES_NOT_PROVE: tuple[tuple[str, str, FinalityDimensionKind], ...] = (
    (
        "340-345",
        "trade capture free from later bust or correction",
        FinalityDimensionKind.TRADE_CAPTURE,
    ),
    ("340-345", "cash or securities settled", FinalityDimensionKind.SETTLEMENT),
    (
        "340-345",
        "proceeds withdrawable or collateral-eligible",
        FinalityDimensionKind.CASH_AVAILABILITY,
    ),
    (
        "340-345",
        "fees, tax, interest, or financing final",
        FinalityDimensionKind.FEE_FINALITY,
    ),
    (
        "340-345",
        "borrow or delivery obligations discharged",
        FinalityDimensionKind.BORROW_DISCHARGE,
    ),
    ("340-345", "custody or legal title final", FinalityDimensionKind.CUSTODY_TITLE),
)

#: ADR §9 line 268-275 — the **8** content groups every Economic Obligation Record "SHALL
#: contain" (line 266 ⇒ a **non-closed minimum set**). Each entry is
#: ``(adr_line, realizing field names)`` on
#: :class:`~tos.posttrade.records.EconomicObligationRecord`. **Transcription only — this is
#: not a producer** (design #24 §2.2-7): group (7)'s per-field confidence is recon-owned and
#: group (8)'s capacity binding is rcl-owned; both are injected coordinates. It exists so
#: the ADR item count stays cross-checkable and so a reader can see what each producer owes.
#: The ADR line is a **string anchor, never a number** (see :data:`FQP_DOES_NOT_PROVE`).
OBLIGATION_RECORD_FIELD_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    # 1 — obligation identity / type / version / digest / status / generation. The PRIMARY
    #     identity axis is the independent ``obligation_id`` (CRITICAL_CONFLICT target).
    (
        "268",
        (
            "obligation_id",
            "obligation_type",
            "obligation_version",
            "obligation_generation",
        ),
    ),
    # 2 — causal source event identities and digests
    ("269", ("source_event_ids", "source_event_digests")),
    # 3 — account / entity / venue / settlement-location scopes, each kept SEPARATE
    (
        "270",
        (
            "account_scope",
            "subaccount_scope",
            "legal_entity_scope",
            "beneficial_owner_scope",
            "broker_scope",
            "clearing_member_scope",
            "custodian_scope",
            "bank_scope",
            "venue_scope",
            "settlement_location_scope",
        ),
    ),
    # 4 — instrument / amount / basis / rounding descriptors
    (
        "271",
        (
            "instrument_identity",
            "asset_identity",
            "currency",
            "quantity",
            "amount",
            "unit_spec",
            "sign_convention",
            "multiplier",
            "price_basis",
            "fx_basis",
            "rounding_rule",
            "tolerance",
        ),
    ),
    # 5 — the ten dates, kept SEPARATE (collapsing them loses the settlement calendar)
    (
        "272",
        (
            "trade_date",
            "record_date",
            "ex_date",
            "due_date",
            "value_date",
            "settlement_date",
            "recall_date",
            "delivery_date",
            "payable_date",
            "observation_date",
        ),
    ),
    # 6 — the eight legs (ObligationLegDirection) and their magnitudes
    ("273", ("legs", "leg_magnitudes")),
    # 7 — source-continuity / statement / correction bindings + confidence + bound
    (
        "274",
        (
            "source_continuity_id",
            "statement_bindings",
            "correction_bindings",
            "per_field_confidence",
            "conservative_bound",
        ),
    ),
    # 8 — lifecycle / finality / break / supersession / invalidation / capacity / evidence
    (
        "275",
        (
            "lifecycle_state",
            "finality_proof_refs",
            "break_refs",
            "supersedes_ref",
            "invalidation_refs",
            "capacity_bindings",
            "evidence_bindings",
        ),
    ),
)

#: ADR §6 — the **18** ``PTF-INV-001..018`` invariants with their Phase-1 realization
#: (design #24 §4.0; **no unowned invariant**). Each entry is
#: ``(invariant_id, proposition, phase_1_realization)``. Transcription only; a §7 property
#: asserts the count is 18 and that every named predicate exists. ``"structural absence"``
#: means the invariant is realized by there being **no field and no predicate** that could
#: express the prohibited act — the strongest available realization.
PTF_INVARIANT_REALIZATION: tuple[tuple[str, str, str], ...] = (
    ("PTF-INV-001", "complete exact obligation set", "obligation_leg_set_complete"),
    (
        "PTF-INV-002",
        "finality dimensions do not imply one another",
        "finality_dimensions_orthogonal",
    ),
    ("PTF-INV-003", "identity and lineage exact", "EconomicObligationRecord"),
    ("PTF-INV-004", "absence is not finality", "monetary_leg_conservative"),
    (
        "PTF-INV-005",
        "finality proof is class-specific",
        "finality_proof_class_specific",
    ),
    ("PTF-INV-006", "UNKNOWN is restrictive", "post_trade_disposition"),
    ("PTF-INV-007", "no unproven netting or reuse", "netting_requires_positive_proof"),
    ("PTF-INV-008", "the RCL is the sole capacity authority", "structural absence"),
    (
        "PTF-INV-009",
        "obligation transition transfers, not releases",
        "post_trade_consequence_all_false",
    ),
    ("PTF-INV-010", "cash semantics exact", "cash_kind_matches_requirement"),
    ("PTF-INV-011", "collateral encumbrance conserved", "collateral_no_double_use"),
    (
        "PTF-INV-012",
        "borrow lifecycle exact",
        "vocabulary substrate (PTF-EV-005 EV-L2/3)",
    ),
    ("PTF-INV-013", "correction reopens affected finality", "finality_proof_current"),
    (
        "PTF-INV-014",
        "statement coverage and independence proven",
        "statement_coverage_complete",
    ),
    (
        "PTF-INV-015",
        "active generation negative gate",
        "generation-monotone order (EV-L2/3 fence)",
    ),
    ("PTF-INV-016", "external economic egress non-bypassable", "structural absence"),
    (
        "PTF-INV-017",
        "economic effect outlives artifacts",
        "post_trade_consequence_all_false",
    ),
    (
        "PTF-INV-018",
        "evidence and recovery do not revive",
        "frozen record (PTF-EV-012 EV-L2/3)",
    ),
)

#: ADR §25 — the **12** rejected alternatives (25.1-25.12) with the structural realization
#: that makes each unconstructable or fail-closed (design #24 §4.9; **no unowned
#: alternative**). Each entry is ``(section, rejected_claim, structural_realization)``.
#: Transcription only; a §7 property asserts the count is 12.
REJECTED_ALTERNATIVE_REALIZATION: tuple[tuple[str, str, str], ...] = (
    (
        "25.1",
        "FQP means the trade is economically final",
        "finality_dimensions_orthogonal",
    ),
    (
        "25.2",
        "the broker statement is the ledger of truth",
        "statement_coverage_complete",
    ),
    (
        "25.3",
        "a flat position releases all capacity",
        "post_trade_consequence_all_false",
    ),
    ("25.4", "buying power is available cash", "cash_kind_matches_requirement"),
    (
        "25.5",
        "pending receivables may fund payables",
        "netting_requires_positive_proof",
    ),
    (
        "25.6",
        "a transfer acknowledgement proves legal title",
        "CUSTODY_TITLE non-implication",
    ),
    (
        "25.7",
        "no recall or assignment notice means none exists",
        "event_state_not_obligation_finality",
    ),
    ("25.8", "corrections may update the old row in place", "REJECTED_OVERWRITE"),
    (
        "25.9",
        "the PTOL may release capacity once finality is proven",
        "structural absence",
    ),
    ("25.10", "operations may directly send instructions", "structural absence"),
    ("25.11", "priority creates protective settlement capacity", "structural absence"),
    (
        "25.12",
        "recovery, replay, or a clean statement restores authority",
        "post_trade_consequence_all_false",
    ),
)

#: The **15** prohibited verbs swept from ADR §1-§24 (design #24 §4.8). Each is realized
#: either by a fail-closed predicate branch or — more strongly — by the **structural
#: absence** of any field or predicate that could express it
#: (``release-capacity-on-finality`` and ``transmit-external-economic-instruction`` are
#: unconstructable, not merely rejected). Transcription only; a §7 property asserts the
#: count.
PROHIBITED_VERBS: tuple[str, ...] = (
    "treat-FQP-as-post-trade-final",  # §12 · §23 · PTF-INV-002
    "treat-absence-as-zero-or-final",  # §13 line 355 · PTF-INV-004
    "net-unproven-receivable-against-payable",  # PTF-INV-007 · §25.5
    "construct-favorable-local-counterleg",  # §9 line 279
    "substitute-cash-kind",  # PTF-INV-010 · §25.4
    "double-use-collateral",  # §15 line 386 · PTF-INV-011
    "treat-event-state-as-obligation-final",  # §17 line 418
    "treat-statement-absence-as-negative-evidence-without-coverage",  # §19 line 448
    "treat-common-mode-as-independent",  # §19 line 445 · PTF-INV-014
    "release-capacity-on-finality",  # §10 line 312 · §21 line 492 · PTF-INV-008/009
    "transmit-external-economic-instruction",  # §1 line 31 · PTF-INV-016
    "transfer-finality-proof-across-leg",  # §11 line 328
    "destructive-overwrite-history",  # §11 line 330 · §20 line 460
    "double-commit-fill",  # §12 line 336 · §4.6
    "revive-on-recovery-or-replay",  # §24 line 552 · PTF-INV-018
)


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

#: (1) rcl ``TransitionCause.FINAL_QUANTITY_PROOF`` (``rcl/vocabulary.py:94``) — the
#: **order-capacity** proof-gated release cause. It is emphatically **not** post-trade
#: finality: ADR-002-030 §1 line 23 "Final Quantity Proof establishes only final cumulative
#: filled quantity and zero remaining executable quantity ... It does not prove any
#: post-trade obligation final." Consumed as a coordinate; never re-decided here.
TRANSITION_CAUSE_FINAL_QUANTITY_PROOF = "FINAL_QUANTITY_PROOF"

#: (2) rcl ``CapacityState.TRAPPED_CONSUMED`` (``rcl/vocabulary.py:30``) — the *capacity*
#: axis counterpart of :attr:`PostTradeDisposition.POST_TRADE_TRAPPED`. Different types.
CAPACITY_STATE_TRAPPED_CONSUMED = "TRAPPED_CONSUMED"

#: (3) rcl ``CapacityState.QUARANTINED_UNKNOWN`` (``rcl/vocabulary.py:29``) — the *capacity*
#: axis counterpart of :attr:`PostTradeDisposition.POST_TRADE_QUARANTINED_UNKNOWN`.
CAPACITY_STATE_QUARANTINED_UNKNOWN = "QUARANTINED_UNKNOWN"

#: (4) are ``RiskDimensionKind.SETTLEMENT_CASH_CURRENCY`` (``are/vocabulary.py:65``) — are
#: already owns settlement / cash / currency as a first-class **aggregate-risk** dimension,
#: which is precisely why this package projects no risk (design #24 §0.4c/§0.4d).
RISK_DIMENSION_SETTLEMENT_CASH_CURRENCY = "SETTLEMENT_CASH_CURRENCY"

#: (5) are ``AdverseScenarioKind.MARGIN_COLLATERAL_BORROW_FX_SETTLE_ASSIGN``
#: (``are/vocabulary.py:112``) — the aggregate-risk scenario over the same economic surface.
ADVERSE_SCENARIO_MARGIN_COLLATERAL_BORROW_FX_SETTLE_ASSIGN = (
    "MARGIN_COLLATERAL_BORROW_FX_SETTLE_ASSIGN"
)

#: (6) are ``AdverseScenarioKind.MISSING_ACK_RECEIPT_AMBIGUITY`` (``are/vocabulary.py:108``)
#: — the missing-acknowledgement ambiguity scenario (are-owned risk; PTF only enumerates the
#: obligation set that feeds it).
ADVERSE_SCENARIO_MISSING_ACK_RECEIPT_AMBIGUITY = "MISSING_ACK_RECEIPT_AMBIGUITY"

#: (7) are ``BenefitKind.NETTING`` (``are/vocabulary.py:131``) — the **aggregate-risk**
#: netting *benefit*, a different proposition from this package's obligation-leg
#: **no-netting** (receivable and payable stay gross) and from nontrade's
#: transition-envelope no-netting: three separate axes (design #24 §0.4d/§3.5).
BENEFIT_KIND_NETTING = "NETTING"

#: (8) recon ``FieldConfidenceClass.CORROBORATED`` (``recon/vocabulary.py:26``) — the only
#: per-field grade that satisfies the §5.8 positive conjunction. It is a **necessary input**
#: to finality, never a substitute for it (PTF-INV-005: a confidence score "cannot replace
#: exact per-field proof").
FIELD_CONFIDENCE_CORROBORATED = "CORROBORATED"

#: (9) recon ``FieldConfidenceClass.UNKNOWN`` — 0 usable evidence paths ⇒ quarantine.
FIELD_CONFIDENCE_UNKNOWN = "UNKNOWN"

#: (10) recon ``FieldConfidenceClass.CONFLICTED`` — independent paths disagree ⇒ conflicted.
FIELD_CONFIDENCE_CONFLICTED = "CONFLICTED"

#: (11) brokercap ``CapabilityStatus.VERIFIED`` (``brokercap/vocabulary.py:29``) — the only
#: capability status that discharges a ``+Broker`` premise. This package judges **no** broker
#: capability (broker-agnostic); it consumes the verdict.
CAPABILITY_STATUS_VERIFIED = "VERIFIED"

#: (12) brokercap ``fqp_adequate`` (``brokercap/predicates.py:595``) — the **name** of the
#: sibling producer whose ``bool`` output crosses this seam. Unlike the other eighteen
#: coordinates the injected value is a plain ``bool``, not a token, so the drift lock is on
#: the producer's *existence and callability* rather than on a string value; the §7 seam test
#: asserts ``callable(getattr(tos.brokercap, BROKER_FQP_ADEQUACY_PRODUCER))``.
BROKER_FQP_ADEQUACY_PRODUCER = "fqp_adequate"

#: (13) nontrade ``NonTradeEventWorkflowState.APPLIED_LOCAL`` (``nontrade/vocabulary.py:165``)
#: — ADR §17 line 418 verbatim: "An ADR-002-010 event state such as ``APPLIED_LOCAL`` or
#: ``RECONCILED`` does not prove its resulting obligations final."
NONTRADE_EVENT_STATE_APPLIED_LOCAL = "APPLIED_LOCAL"

#: (14) nontrade ``NonTradeEventWorkflowState.RECONCILED`` — same §17 line 418 non-implication.
#: Note it is **also** distinct from orthostate ``KnowledgeState.RECONCILED`` (§2.2-6).
NONTRADE_EVENT_STATE_RECONCILED = "RECONCILED"

#: (15) egress ``EgressAdmission.ADMIT`` (``egress/vocabulary.py``) — the final-egress
#: admission this package **never** produces: §1 line 31 / PTF-INV-016 forbid the PTOL from
#: holding a usable external-economic credential and route.
EGRESS_ADMISSION_ADMIT = "ADMIT"

#: (16) egress ``CommitProofValidity.VALID`` — the egress commit-proof verdict, consumed as
#: a coordinate for the EV-L2/3 runtime; no Phase-1 predicate reads it.
COMMIT_PROOF_VALIDITY_VALID = "VALID"

#: (17) time ``FreshnessVerdict.FRESH`` (``time/domains.py:66``) — the only verdict that
#: establishes an effective-time window. This package is **clock-free**: every age and
#: timing bound is a null VP-002 key (design #24 §8.1) and every freshness verdict is
#: injected.
FRESHNESS_VERDICT_FRESH = "FRESH"

#: (18) cur ``DimensionKey.POST_TRADE`` (``cur/vocabulary.py:146``) — cur already owns the
#: post-trade **currentness** dimension, so this package supplies only the §8.1 identity
#: coordinates (policy id / generation / digest) and never fences (design #24 §6.5).
CURRENTNESS_DIMENSION_POST_TRADE = "POST_TRADE"

#: (19) cur ``CurrentnessAdmission.ADMIT`` (``cur/vocabulary.py:113``) — the currentness
#: admission cur produces and this package consumes; the fencing runtime is PTF-EV-010
#: ``EV-L2/3+Security``.
CURRENTNESS_ADMISSION_ADMIT = "ADMIT"

#: All **19** injected sibling coordinates, in the design #24 §3.4 declaration order, each
#: paired with its owning sibling package. A §7 property asserts the count is 19 and the
#: seam tests lock every entry against the live sibling member (the #21 MINOR-1 lesson —
#: individual counting is mandatory, an aggregate "all locked" claim is not).
INJECTED_SIBLING_TOKENS: tuple[tuple[str, str], ...] = (
    ("rcl", TRANSITION_CAUSE_FINAL_QUANTITY_PROOF),
    ("rcl", CAPACITY_STATE_TRAPPED_CONSUMED),
    ("rcl", CAPACITY_STATE_QUARANTINED_UNKNOWN),
    ("are", RISK_DIMENSION_SETTLEMENT_CASH_CURRENCY),
    ("are", ADVERSE_SCENARIO_MARGIN_COLLATERAL_BORROW_FX_SETTLE_ASSIGN),
    ("are", ADVERSE_SCENARIO_MISSING_ACK_RECEIPT_AMBIGUITY),
    ("are", BENEFIT_KIND_NETTING),
    ("recon", FIELD_CONFIDENCE_CORROBORATED),
    ("recon", FIELD_CONFIDENCE_UNKNOWN),
    ("recon", FIELD_CONFIDENCE_CONFLICTED),
    ("brokercap", CAPABILITY_STATUS_VERIFIED),
    ("brokercap", BROKER_FQP_ADEQUACY_PRODUCER),
    ("nontrade", NONTRADE_EVENT_STATE_APPLIED_LOCAL),
    ("nontrade", NONTRADE_EVENT_STATE_RECONCILED),
    ("egress", EGRESS_ADMISSION_ADMIT),
    ("egress", COMMIT_PROOF_VALIDITY_VALID),
    ("time", FRESHNESS_VERDICT_FRESH),
    ("cur", CURRENTNESS_DIMENSION_POST_TRADE),
    ("cur", CURRENTNESS_ADMISSION_ADMIT),
)

#: The two nontrade event-workflow tokens ADR §17 line 418 names explicitly as **not**
#: proving obligation finality. They exist so a test can exercise exactly the tokens the ADR
#: calls out; :func:`~tos.posttrade.predicates.event_state_not_obligation_finality`
#: deliberately **does not read** the token at all, which is the strongest possible
#: realization of the non-implication (design #24 §5.5).
EVENT_STATE_TOKENS_THAT_PROVE_NO_FINALITY: tuple[str, ...] = (
    NONTRADE_EVENT_STATE_APPLIED_LOCAL,
    NONTRADE_EVENT_STATE_RECONCILED,
)
