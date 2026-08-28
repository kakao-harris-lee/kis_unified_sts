"""posttrade decision predicates — the 19 pure, fail-closed post-trade rules (§5).

Pure, fail-closed decision rules over injected frozen models (design #24 §0.2/§4.4):
``tos.posttrade`` is **not** a capacity ledger, **not** an aggregate-risk projector, **not**
a per-field evidence classifier, **not** a broker-capability arbiter, **not** a non-trade
event identifier, **not** a currentness fence, and **not** an egress. The capacity
reservation, commit, transfer, quarantine, and release arithmetic is rcl-owned (ADR-002-030
§1 line 21 verbatim "The Risk Capacity Ledger remains the sole capacity mutation and
serialization authority ... an obligation compiler, Reconciliation Service, PTOL, position
or cash projection, statement processor, evidence service, recovery workflow, operator, or
finality proof SHALL NOT create, change, quarantine, transfer, remap, or release capacity";
PTF-INV-008); the aggregate-risk projection and the netting **benefit** are are-owned (§21;
``BenefitKind.NETTING``); the per-field evidence confidence is recon-owned (§11;
PTF-INV-005 "confidence score ... cannot replace exact per-field proof"); broker / clearing
/ custodian / banking capability and Final-Quantity-Proof adequacy are brokercap-owned (the
``+Broker`` premise on **all twelve** PTF-EV rows); the non-trade event and transformation
identity plus the event workflow lifecycle are nontrade-owned (ADR-002-010 §16 line 309 ↔
ADR-002-030 §17 line 414, a **mutual** deferral); currentness fencing is cur-owned
(``DimensionKey.POST_TRADE``); external economic transmission is egress-owned (§1 line 31;
PTF-INV-016); the order / knowledge state axes are orthostate-owned (§10 line 303-310);
authority re-arm is authority / liveauth-owned (§22); recovery is sbr-owned (§24); and
trustworthy time is time-owned (§22). This module **consumes every one of those as an
injected produced bool / token / magnitude and re-authors none of them** (design #24
§0.2/§3.5).

What it *does* author is the post-trade **decision layer**: finality-dimension
orthogonality, obligation-leg set completeness, fill-to-obligation commit idempotency,
no-favourable-default (absence is not zero, netting needs positive proof, a missing
counterleg is adverse), collateral conservation and cash-kind non-substitution,
event-state-is-not-obligation-finality, statement coverage completeness and source
independence, finality-proof class specificity / non-transferability / currency, the
finality-grants-nothing seal, and the single
:class:`~tos.posttrade.vocabulary.PostTradeDisposition` producer. There is no
"assume-complete" / "assume-final" / "assume-independent" path anywhere: a permissive result
comes only from **positive conjunction identity**, and the residual branch of every dispatch
is restrictive (design #24 §4 — the structural seal against the #6 fail-open REJECT and the
#16 CRITICAL "a GRANT must not be the fall-through residue" lesson).

**Polarity discipline (design #24 §0.1(11) — the #18 / #21 v1.1 lessons).**

* :class:`~tos.posttrade.vocabulary.PostTradeDisposition` and
  :class:`~tos.posttrade.vocabulary.ObligationCommitOutcome` are **truthy-untestable**
  (``__bool__`` raises), so every gate is an **identity** test
  (``is PostTradeDisposition.POST_TRADE_ADMISSIBLE``), never ``if disposition:``.
* An injected **sibling token** (the recon ``FieldConfidenceClass``, the nontrade
  ``NonTradeEventWorkflowState``, the cur ``CurrentnessAdmission``) crosses the seam as a
  bare string and is compared with ``==`` against a **local constant** — never with
  ``bool(token)``, and never against an imported type (sibling edge 0).
* **Positive-polarity** ``bool | None`` (safe value ``True``: ``original_retained``,
  ``same_scope``, ``enforceable_netting_proof``, ``counterleg_positively_established``,
  ``dimension_proof_present[*]``, ``line_item_absent``, ``coverage_complete``,
  ``correction_semantics_support``, ``source_capability_supports``, ``booked_zero``,
  ``availability_proven``, and every one of the sixteen
  :func:`post_trade_disposition` conjuncts) is gated with ``is True`` **only**, so a
  ``None`` and a truthy non-``bool`` both fail closed.
* **Negative-polarity** ``bool | None`` (safe value ``False``) would be gated with ``is
  False`` **only** (``is not True`` is forbidden *there* because a ``None`` would pass it) —
  but **Phase-1 posttrade has zero negative-polarity fields** (design #24 §7, honest
  disclosure): no-netting is a structural coexistence of two gross magnitudes, collateral
  conservation is a magnitude sum, history preservation is the positive
  ``original_retained``, and a capacity release / external send is unrepresentable. A §7
  property asserts the phantom names stay absent from the models.
* The one place ``is not True`` appears is inside :func:`post_trade_disposition`'s **denial**
  ranks, where it makes a ``None`` fall to the *more* conservative member. Using it to
  **permit** anything is what the series discipline forbids, and it is used to permit
  nothing here.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` only; **no sibling** ``tos.*``
(sibling edge 0, design #24 §0.3/§0.4b), no ``shared.*``.

**Discipline tag (design #24 §1).** *Predicate / coordinate substrate only. Closing
PTF-EV = 0; no EV-L1-complete claim.*
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from tos.canonical import CanonicalDecimal, RecordPairKind, classify_record_pair
from tos.posttrade._base import AllFalsePostTradeConsequence
from tos.posttrade.records import (
    STATEMENT_COVERAGE_SET_AXES,
    CollateralAllocation,
    EconomicObligationRecord,
    MonetaryLeg,
    ObligationLeg,
    ObligationLegScope,
    PostTradeFinalityProof,
    StatementCoverageManifest,
)
from tos.posttrade.vocabulary import (
    FIELD_CONFIDENCE_CONFLICTED,
    FIELD_CONFIDENCE_CORROBORATED,
    FIELD_CONFIDENCE_UNKNOWN,
    OPPOSITE_DIRECTION_PAIRS,
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
    # §5.1 finality orthogonality + obligation-leg completeness (PTF-EV-001 substrate)
    "finality_dimensions_orthogonal",
    "obligation_leg_set_complete",
    # §5.2 fill-to-obligation commit idempotency (PTF-EV-001 substrate)
    "obligation_commit_idempotent",
    # §5.3 no-favourable-default (PTF-EV-002 substrate)
    "monetary_leg_conservative",
    "netting_requires_positive_proof",
    "missing_counterleg_is_adverse",
    # §5.4 collateral / margin / cash (PTF-EV-004 substrate)
    "collateral_no_double_use",
    "margin_collateral_states_distinct",
    "cash_kind_matches_requirement",
    # §5.5 event obligation legs + event-state non-implication (PTF-EV-006 substrate)
    "obligation_legs_from_event_complete",
    "event_state_not_obligation_finality",
    # §5.6 statement coverage / independence / absence (PTF-EV-008 substrate)
    "statement_coverage_complete",
    "statement_sources_independent",
    "absence_is_negative_evidence_only",
    # §5.7 finality proof + finality-grants-nothing (core substrate)
    "finality_proof_class_specific",
    "finality_proof_non_transferable",
    "finality_proof_current",
    "post_trade_consequence_all_false",
    # §5.8 the single disposition producer (core substrate, C1)
    "post_trade_disposition",
    # §4.8 <-> §5.8 traceability data
    "DISPOSITION_CONJUNCTS",
    "VOID_TABLE_ROWS",
]


#: The **exhaustive** ``RecordPairKind`` -> :class:`ObligationCommitOutcome` mapping
#: (design #24 §4.6 truth table; the #21 C2 defect was an inverted / incomplete mapping).
#: All **five** canonical members are bound explicitly — a §7 property asserts
#: ``set(_RECORD_PAIR_OUTCOME) == set(RecordPairKind)``, so a future canonical member
#: cannot silently fall through to a permissive default.
#:
#: * ``IDEMPOTENT_DUP`` (``canonical/record_pair.py:94``/``:101``) — same primary **or**
#:   idempotency id with the **same** canonical bytes: a harmless late-fill re-apply
#:   (obligation effect + 0; §12 line 347).
#: * ``CRITICAL_CONFLICT`` (``:96``) — same **primary** id, **different** bytes: obligation
#:   forgery / a contradictory obligation. Contain both, never last-write-wins (``:68``).
#: * ``DIVERGENT_EMISSION`` (``:103``) — same **idempotency** id, **different** bytes: two
#:   different fills claiming one commit key. **Also** contained — the two forgery axes are
#:   distinct kinds that fold to one rejection, and neither is ever double-committed.
#: * ``DISTINCT`` (``:105``) — the prior shares neither identity axis, so it is not the
#:   prior at all: a violation of the :func:`obligation_commit_idempotent` prior-selection
#:   contract ⇒ undecidable ⇒ fail closed.
#: * ``NOT_COMPARABLE`` (``:87``) — at least one record is pre-issuance (null digest) ⇒
#:   not a ledger citizen ⇒ undecidable ⇒ fail closed.
_RECORD_PAIR_OUTCOME: Mapping[RecordPairKind, ObligationCommitOutcome] = {
    RecordPairKind.IDEMPOTENT_DUP: ObligationCommitOutcome.IDEMPOTENT_REPLAY,
    RecordPairKind.CRITICAL_CONFLICT: ObligationCommitOutcome.REJECTED_CONFLICT,
    RecordPairKind.DIVERGENT_EMISSION: ObligationCommitOutcome.REJECTED_CONFLICT,
    RecordPairKind.DISTINCT: ObligationCommitOutcome.REJECTED_UNKNOWN,
    RecordPairKind.NOT_COMPARABLE: ObligationCommitOutcome.REJECTED_UNKNOWN,
}

#: The **only** commit outcomes that satisfy the §5.8 positive conjunction: a legitimately
#: committed first fill and a harmless idempotent late-fill replay. Every ``REJECTED_*``
#: member is excluded, and the check is an identity membership test — never ``if outcome:``
#: (which would read a rejection as permission).
_ACCEPTABLE_COMMIT_OUTCOMES: frozenset[ObligationCommitOutcome] = frozenset(
    {
        ObligationCommitOutcome.COMMITTED_ONCE,
        ObligationCommitOutcome.IDEMPOTENT_REPLAY,
    }
)

#: The two :class:`~tos.posttrade.vocabulary.StatementClass` members that can carry complete
#: coverage. ``PRELIMINARY`` is excluded by construction (§19 line 450: it is subject to
#: restatement), and a ``None`` class is an undeclared classification ⇒ fail closed.
_COVERAGE_BEARING_STATEMENT_CLASSES: frozenset[StatementClass] = frozenset(
    {StatementClass.FINAL, StatementClass.REVISED}
)

#: The **16** positive-polarity bool conjuncts of :func:`post_trade_disposition`, in
#: signature order (design #24 §5.8 C1). Each maps 1:1 onto a §4.8 void-table row
#: (:data:`VOID_TABLE_ROWS`), and a §7 property asserts the correspondence in **both**
#: directions — the C1 fail-open (a conjunct that exists in the table but not in the
#: conjunction) cannot recur silently.
DISPOSITION_CONJUNCTS: tuple[str, ...] = (
    "leg_set_complete",
    "finality_orthogonal",
    "monetary_conservative",
    "netting_proof_ok",
    "counterleg_established",
    "collateral_conserved",
    "event_state_not_final_ok",
    "statement_coverage_ok",
    "sources_independent",
    "proof_non_transferable",
    "margin_states_distinct",
    "cash_kind_ok",
    "event_legs_complete",
    "absence_gate_ok",
    "proof_class_specific",
    "proof_current",
)

#: The **22** rows of the design #24 §4.8 ∅-void table, each as
#: ``(row_number, input_name, expected_disposition_value)``. ``input_name`` is either one of
#: the sixteen :data:`DISPOSITION_CONJUNCTS`, one of the three non-bool injections
#: (``commit_outcome`` / ``field_confidence`` / ``availability_proven``), or the string
#: ``"structural absence"`` for row 15, whose prohibition has **no** input at all — a
#: capacity release or an external send is unrepresentable, so no value can move the
#: disposition (design #24 §4.8 row 15, PTF-INV-008/016). Row 15's expected verdict is
#: therefore the sentinel ``"INVARIANT"`` rather than a disposition member: the §4.8 cell
#: reads "disposition unchanged — no state can raise it", and writing a member there would
#: falsely suggest some input drives it.
#:
#: The row number is a **string label, never a number**, for the same reason the ADR line
#: anchors are (design #24 §8.0: the numeric-literal source scan stays absolute).
VOID_TABLE_ROWS: tuple[tuple[str, str, str], ...] = (
    ("1", "leg_set_complete", PostTradeDisposition.POST_TRADE_BLOCK_NEW_RISK.value),
    ("2", "finality_orthogonal", PostTradeDisposition.POST_TRADE_BLOCK_NEW_RISK.value),
    (
        "3",
        "monetary_conservative",
        PostTradeDisposition.POST_TRADE_BLOCK_NEW_RISK.value,
    ),
    ("4", "netting_proof_ok", PostTradeDisposition.POST_TRADE_BLOCK_NEW_RISK.value),
    (
        "5",
        "counterleg_established",
        PostTradeDisposition.POST_TRADE_BLOCK_NEW_RISK.value,
    ),
    ("6", "collateral_conserved", PostTradeDisposition.POST_TRADE_CONFLICTED.value),
    (
        "7",
        "event_state_not_final_ok",
        PostTradeDisposition.POST_TRADE_BLOCK_NEW_RISK.value,
    ),
    (
        "8",
        "statement_coverage_ok",
        PostTradeDisposition.POST_TRADE_BLOCK_NEW_RISK.value,
    ),
    ("9", "sources_independent", PostTradeDisposition.POST_TRADE_CONFLICTED.value),
    ("10", "proof_non_transferable", PostTradeDisposition.POST_TRADE_CONFLICTED.value),
    ("11", "commit_outcome", PostTradeDisposition.POST_TRADE_CONFLICTED.value),
    ("12", "commit_outcome", PostTradeDisposition.POST_TRADE_CONFLICTED.value),
    (
        "13",
        "commit_outcome",
        PostTradeDisposition.POST_TRADE_QUARANTINED_UNKNOWN.value,
    ),
    (
        "14",
        "field_confidence",
        PostTradeDisposition.POST_TRADE_QUARANTINED_UNKNOWN.value,
    ),
    ("15", "structural absence", "INVARIANT"),
    ("16", "availability_proven", PostTradeDisposition.POST_TRADE_TRAPPED.value),
    (
        "17",
        "margin_states_distinct",
        PostTradeDisposition.POST_TRADE_BLOCK_NEW_RISK.value,
    ),
    ("18", "cash_kind_ok", PostTradeDisposition.POST_TRADE_BLOCK_NEW_RISK.value),
    ("19", "event_legs_complete", PostTradeDisposition.POST_TRADE_BLOCK_NEW_RISK.value),
    ("20", "absence_gate_ok", PostTradeDisposition.POST_TRADE_BLOCK_NEW_RISK.value),
    ("21", "proof_class_specific", PostTradeDisposition.POST_TRADE_CONFLICTED.value),
    ("22", "proof_current", PostTradeDisposition.POST_TRADE_BLOCK_NEW_RISK.value),
)


# ===========================================================================
# Shared fail-closed helpers
# ===========================================================================


def _is_present_non_negative(magnitude: CanonicalDecimal | None) -> bool:
    """Whether a magnitude is present, finite, and non-negative (fail-closed helper).

    ``None`` is UNKNOWN — **never zero** (§13 line 355 "A missing line item or zero estimate
    is not proof of zero") — a non-finite value is unconstructable content that must not
    reach a comparison, and a negative magnitude on a *gross* obligation / collateral axis is
    a sign error (a direction carries the sign, a magnitude does not). All three are
    ``False``.

    Args:
        magnitude: The injected magnitude.

    Returns:
        ``True`` iff the magnitude is present, finite, and ``>= 0``.
    """
    if magnitude is None:
        return False
    if not magnitude.is_finite():
        return False
    return magnitude >= 0


def _scope_fully_specified(scope: ObligationLegScope | None) -> bool:
    """Whether every one of the six §11 line 328 scope components is concrete.

    A scope with an absent component describes a **set** of legs, and a proof over a set is
    exactly the union §11 line 328 ("non-transferable and non-unionable") forbids. So an
    under-specified scope is not a weaker proof — it is no proof at all.

    Args:
        scope: The scope tuple to check (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff leg, account, currency, value date, source revision, and finality class
        are all present (and the string components non-empty).
    """
    if scope is None:
        return False
    if scope.leg is None or scope.finality_class is None:
        return False
    return all(
        bool(component)
        for component in (
            scope.account,
            scope.currency,
            scope.value_date,
            scope.source_revision,
        )
    )


def _claims_correction(record: EconomicObligationRecord) -> bool:
    """Whether a record claims to correct an earlier obligation version (§20 line 460).

    §20 line 460 forbids relabelling: a component "SHALL NOT destructively rewrite" history,
    and a correction must be a **linked** new version. A record claims to be a correction
    when it either carries §9 line 274 correction bindings or declares a lifecycle state that
    only a correction reaches (``CORRECTION_PENDING`` / ``SUPERSEDED``). Such a record owes a
    ``supersedes_ref``; without one it is an unexplained change wearing a correction label,
    which :func:`obligation_commit_idempotent` rejects as ``REJECTED_NO_LINEAGE``.

    An *original* obligation claims nothing and is unaffected — which is why the lineage gate
    is conditional rather than universal: making ``supersedes_ref`` mandatory for every record
    would make the first commit unconstructable and the guard vacuous.

    Args:
        record: The incoming obligation record.

    Returns:
        ``True`` iff the record claims correction lineage.
    """
    if record.correction_bindings:
        return True
    return record.lifecycle_state in (
        PostTradeObligationLifecycleState.CORRECTION_PENDING,
        PostTradeObligationLifecycleState.SUPERSEDED,
    )


# ===========================================================================
# §5.1 finality-dimension orthogonality + obligation-leg set completeness
# (ADR §12 / §9; PTF-EV-001 substrate, core L1 slice; PTF-INV-001/002; PTF-AC-001)
# ===========================================================================


def finality_dimensions_orthogonal(
    claimed_final_dimension: FinalityDimensionKind | None,
    dimension_proof_present: Mapping[FinalityDimensionKind, bool | None],
) -> bool:
    """Whether the claimed finality dimension rests on **its own** proof (PTF-INV-002).

    PTF-INV-002 line 156 verbatim: the ten dimensions — "Order FQP, trade capture,
    instruction acceptance, settlement, cash availability, collateral eligibility, custody
    title, fee finality, borrow discharge, and corporate-action finality" — "**do not imply
    one another**". §1 line 23 verbatim: "Final Quantity Proof establishes only final
    cumulative filled quantity and zero remaining executable quantity ... **It does not prove
    any post-trade obligation final.**" §12 line 340-345 lists the **six** things it
    explicitly does not prove (:data:`~tos.posttrade.vocabulary.FQP_DOES_NOT_PROVE`).

    **The proposition, in one sentence (design #24 §5.1 M1):** *the claimed dimension is
    final only by its own dimension-specific proof, and no other dimension's proof is
    consulted at all.*

    Non-implication is therefore **structural, not enforced**: the function reads exactly one
    entry of ``dimension_proof_present`` — the claimed one — so ``ORDER_FQP`` PROVEN has no
    code path by which it could make ``SETTLEMENT``, ``CASH_AVAILABILITY``,
    ``FEE_FINALITY``, ``CUSTODY_TITLE``, or ``BORROW_DISCHARGE`` final. There is no
    implication table to get wrong and no aggregate "all final" promotion to fall through
    into (§5.10 line 144 forbids a "universal trade-level boolean"; PTF-INV-005 forbids a
    global ``SETTLED`` / ``CLOSED`` standing in for per-field proof).

    **∅ structural guard (design #24 §5.1 M1 / §4.8 row 2).** An absent claim or an **empty**
    proof map is ``False``: an empty map is "no dimension has any proof", which must never
    read as "the claim holds vacuously". Every dimension defaults to UNKNOWN (PTF-INV-006).
    The guard is written explicitly even though ``Mapping.get`` would also return ``None`` on
    an empty map, because it states the ∅ rule as a **standing invariant** rather than as a
    consequence of one lookup: a later edit that introduced a default (``get(claimed, True)``,
    a ``defaultdict``, or an injected mapping with its own fallback) would otherwise turn the
    vacuous case permissive with no line to review.

    **Positive polarity.** The per-dimension entry is gated ``is True`` only, so ``None``
    (never asserted) and ``False`` (asserted absent) are both not-proven, and a truthy
    non-``bool`` forged past the annotation is not proof either.

    This predicate proves finality of a **leg dimension**, never a consequence: even a
    ``True`` here releases no capacity and makes no cash available (§10 line 312, sealed by
    :func:`post_trade_consequence_all_false`).
    [PTF-EV-001 coordinate; the ``/2``, ``/3``, and ``+Broker`` stages remain open.]
    [SAFE-004; SAFE-020; SAFE-021]

    Args:
        claimed_final_dimension: The dimension whose finality is being claimed (``None`` ⇒
            ``False``: nothing is claimed, so nothing is proven).
        dimension_proof_present: The injected per-dimension proof presence map (**positive**
            polarity ``bool | None``). An empty map ⇒ ``False``.

    Returns:
        ``True`` iff the claimed dimension carries its own positive proof.
    """
    if claimed_final_dimension is None or not dimension_proof_present:
        return False
    return dimension_proof_present.get(claimed_final_dimension) is True


def obligation_leg_set_complete(
    required_legs: frozenset[ObligationLegDirection],
    present_legs: frozenset[ObligationLegDirection],
    leg_magnitudes: Mapping[ObligationLegDirection, CanonicalDecimal | None],
) -> bool:
    """Whether the obligation's exact leg set is complete (ADR §9; PTF-INV-001).

    §9 line 273 requires the record to carry its exact "debit, credit, delivery, receipt,
    encumbrance, release, return, and contingent" legs, and §9 line 279 requires the
    **greatest credible adverse union** where a balanced pair cannot be positively
    established. Completeness is therefore a two-part judgment: every *applicable* leg is
    present, **and** each one carries a concrete gross magnitude — an enumerated leg with an
    UNKNOWN magnitude proves nothing about the obligation's size.

    **∅ structural guard (design #24 §5.1; the #21 C1 lesson).** An **empty**
    ``required_legs`` set is ``False``, never a vacuous ``True``: ``∅ <= present`` holds for
    every possible ``present``, so an empty requirement would certify any obligation as
    complete. An empty requirement is not "no risk" — it is "we do not know what must be
    proven". The isomorphic sibling proposition is rcl's ``credible_union_capacity``
    (``rcl/predicates.py:739``), whose empty input raises ``ValueError``; this package
    expresses the same fail-closed rule as ``False``.

    The *applicable* subset is obligation-class-parametric and is **injected** by the caller;
    this package deliberately publishes no default required set, because defaulting to the
    full eight-member universe would silently redefine every caller's obligation.
    [PTF-EV-001 coordinate; the ``/2``, ``/3``, and ``+Broker`` stages remain open.]
    [SAFE-012; SAFE-013]

    Args:
        required_legs: The applicable leg directions (**injected**; empty ⇒ ``False``).
        present_legs: The leg directions actually enumerated on the obligation.
        leg_magnitudes: The per-direction gross magnitudes (``None`` is UNKNOWN, never zero).

    Returns:
        ``True`` iff every required leg is present with a concrete, finite, non-negative
        magnitude.
    """
    if not required_legs:
        return False
    if not required_legs <= present_legs:
        return False
    return all(
        _is_present_non_negative(leg_magnitudes.get(leg)) for leg in required_legs
    )


# ===========================================================================
# §5.2 fill-to-obligation commit idempotency
# (ADR §12 line 336/347; PTF-EV-001 substrate, core L1 slice; PTF-AC-001)
# ===========================================================================


def obligation_commit_idempotent(
    incoming: EconomicObligationRecord | None,
    prior: EconomicObligationRecord | None,
    original_retained: bool | None,
) -> ObligationCommitOutcome:
    """Classify a fill-to-obligation commit (ADR §12 line 336/347; PTF-EV-001).

    §12 line 336 verbatim: "The fill-to-obligation commit SHALL be idempotent and causally
    linked to the originating Intent, attempt, broker order, fill revision, position
    transfer, and RCL allocation." §12 line 347: a fill discovered **after** a claimed
    terminal outcome is applied idempotently, creating or correcting obligations, advancing
    generation, and preserving capacity. §11 line 330 / §20 line 460 forbid destructive
    rewrite; §20 line 460 forbids relabelling an unexplained change as a correction.

    **The prior-selection contract (design #24 §5.2 M7) — verbatim.** ``prior`` = *the record
    sharing incoming's **primary obligation identity**; failing that, the record sharing its
    **idempotency key**; failing both, ``None``.* This two-axis selection extends the
    single-axis nontrade precedent (``nontrade/predicates.py:526``, "the record sharing
    incoming's idempotency key") and blocks **two** misreadings that a single axis would
    leave open:

    * a **key-only** selection would let a same-primary-id / different-key forgery arrive
      with ``prior is None``, land on ``COMMITTED_ONCE``, and thereby **bypass**
      ``CRITICAL_CONFLICT``;
    * a **primary-only** selection would **miss** ``DIVERGENT_EMISSION`` entirely, because a
      same-key / different-primary-id forgery shares no primary id.

    ``classify_record_pair`` compares **both** axes (four positional arguments plus two
    keyword-only idempotency ids, ``canonical/record_pair.py:52``), so the one selected prior
    folds each forgery into its own exact kind. ``DISTINCT`` therefore arises **only** when
    the caller violates this contract by passing a prior that shares neither axis, and it
    fails closed as ``REJECTED_UNKNOWN``.

    **Four pre-gates, then the canonical classifier** (design #24 §4.6, in order):

    1. no ``incoming`` at all ⇒ ``REJECTED_UNKNOWN`` (nothing to decide, fail closed);
    2. the record **claims a correction** (:func:`_claims_correction`) but carries no
       ``supersedes_ref`` ⇒ ``REJECTED_NO_LINEAGE`` (§20 line 460 no-relabel);
    3. ``original_retained is not True`` ⇒ ``REJECTED_OVERWRITE`` (§11 line 330 / §20 line
       460). The flag is **positive polarity**: ``None`` (unknown) and ``False``
       (overwritten) both reject, and a truthy non-``bool`` forged past the annotation is not
       proof;
    4. ``prior is None`` ⇒ **``COMMITTED_ONCE``** — the legitimate *first* commit. This branch
       must precede the classifier: with no prior there is no pair to classify, and routing it
       through ``classify_record_pair`` would return ``NOT_COMPARABLE`` and reject every
       legitimate first commit forever (the #21 C2 defect — an outcome that was structurally
       unreachable).

    Then the **exhaustive** ``classify_record_pair`` mapping
    (:data:`_RECORD_PAIR_OUTCOME`)::

        IDEMPOTENT_DUP     -> IDEMPOTENT_REPLAY   (effect + 0, harmless late-fill re-apply)
        CRITICAL_CONFLICT  -> REJECTED_CONFLICT   (same PRIMARY id, different bytes)
        DIVERGENT_EMISSION -> REJECTED_CONFLICT   (same IDEMPOTENCY key, different bytes)
        DISTINCT           -> REJECTED_UNKNOWN
        NOT_COMPARABLE     -> REJECTED_UNKNOWN

    **Only ``COMMITTED_ONCE`` increases the obligation effect count** (design #24 §4.6): a
    late fill applied N >= 2 times yields ``COMMITTED_ONCE`` once and ``IDEMPOTENT_REPLAY``
    thereafter, so the cumulative effect count is exactly 1 (§12 line 347 harmlessness). The
    **two** forgery axes are distinct canonical kinds and both fold to ``REJECTED_CONFLICT``:
    both records are preserved, there is no last-write-wins merge
    (``canonical/record_pair.py:68``), and neither is ever silently double-committed.

    **Anchored directly on the canonical primitive** (design #24 §0.4e): iap
    ``ConsumptionOutcome.IDEMPOTENT_REPLAY`` (authorization-token single-use), rcl
    ``ApplyReason.IDEMPOTENT_REPLAY`` (capacity-command), and nontrade
    ``CorrectionReversalOutcome.IDEMPOTENT_REPLAY`` (economic-event application) are
    **different propositions** on different axes, so no sibling is imported or consumed — the
    phantom edge is blocked at the source. The rcl capacity commit / transfer that follows an
    accepted outcome is likewise rcl's, not this predicate's (§1 line 21, PTF-INV-008).
    [PTF-EV-001 coordinate; the ``/2``, ``/3``, and ``+Broker`` stages remain open.]
    [SAFE-020; SAFE-051; SAFE-052]

    Args:
        incoming: The incoming obligation record produced from a fill.
        prior: The record selected by the two-axis contract above, or ``None`` for the first
            commit in the series.
        original_retained: Whether the prior version is retained append-only (**positive
            polarity**: only ``True`` passes).

    Returns:
        The :class:`~tos.posttrade.vocabulary.ObligationCommitOutcome`.
    """
    if incoming is None:
        return ObligationCommitOutcome.REJECTED_UNKNOWN
    if _claims_correction(incoming) and incoming.supersedes_ref is None:
        return ObligationCommitOutcome.REJECTED_NO_LINEAGE
    if original_retained is not True:
        return ObligationCommitOutcome.REJECTED_OVERWRITE
    if prior is None:
        return ObligationCommitOutcome.COMMITTED_ONCE
    kind = classify_record_pair(
        incoming.obligation_id,
        incoming.canonical_digest,
        prior.obligation_id,
        prior.canonical_digest,
        a_idempotency_id=incoming.idempotency_key,
        b_idempotency_id=prior.idempotency_key,
    )
    # Exhaustive by construction (a §7 property locks the mapping against RecordPairKind);
    # the ``.get`` default is a defence-in-depth restrictive residue for a future member.
    return _RECORD_PAIR_OUTCOME.get(kind, ObligationCommitOutcome.REJECTED_UNKNOWN)


# ===========================================================================
# §5.3 no-favourable-default — monetary, netting, counterleg
# (ADR §13 / §9 line 279; PTF-EV-002 substrate, core L1 slice; PTF-INV-004/007)
# ===========================================================================


def monetary_leg_conservative(leg: MonetaryLeg | None) -> bool:
    """Whether a fee / tax / interest / financing leg is conservatively stated (§13).

    §13 line 355 verbatim: "**A missing line item or zero estimate is not proof of zero.**"
    "Estimated or accrued amounts remain distinct from broker-booked and legally final
    amounts", and a favourable rebate or credit does not offset a confirmed adverse
    obligation without exact enforceable netting proof.

    The conjunction (all positive, no fall-through):

    * the amount is **present**, finite, and non-negative — ``None`` is UNKNOWN and
      greatest-credible, **never** a favourable zero (§4.8 row 3);
    * the amount **status** is explicitly declared (the estimated / accrued / broker-booked /
      legally-final distinction §13 line 355 demands). An undeclared status collapses the
      three into one and is rejected;
    * a **zero** amount is accepted only as a *positively booked* zero: ``booked_zero is
      True`` **and** the injected recon confidence is ``CORROBORATED``. A confidence grade is
      a **necessary input** to that zero proof and never a substitute for finality
      (PTF-INV-005).

    The offset prohibition needs no branch here: there is no ``offset`` / ``netted`` field on
    :class:`~tos.posttrade.records.MonetaryLeg`, so a favourable amount cannot be applied to
    an adverse one inside this model at all — the netting question is
    :func:`netting_requires_positive_proof`'s, and it demands positive proof.
    [PTF-EV-002 coordinate; the ``/2``, ``/3``, and ``+Broker`` stages remain open.]
    [SAFE-012; SAFE-013; SAFE-022]

    Args:
        leg: The monetary leg (``None`` ⇒ ``False``: an absent line item proves nothing).

    Returns:
        ``True`` iff the leg is present, finite, non-negative, explicitly classified, and —
        when zero — positively booked from a corroborated source.
    """
    if leg is None:
        return False
    amount = leg.amount
    if not _is_present_non_negative(amount):
        return False
    if not leg.amount_status:
        return False
    if amount == 0:
        return (
            leg.booked_zero is True
            and leg.source_confidence == FIELD_CONFIDENCE_CORROBORATED
        )
    return True


def netting_requires_positive_proof(
    receivable: ObligationLeg | None,
    payable: ObligationLeg | None,
    same_scope: bool | None,
    enforceable_netting_proof: bool | None,
) -> bool:
    """Whether a receivable may be netted against a payable (PTF-INV-007; §4.5-A).

    PTF-INV-007 verbatim: an uncertain receivable does not fund a payable, pending proceeds
    are not available cash, and an unproven offset creates no headroom. §14 line 377: two
    amounts "cannot be netted unless ... legal enforceability, operational finality, timing,
    amount, common-mode independence, and current availability" are established. §25.5
    rejects "Pending receivables may fund payables" outright.

    **Netting is derived, never declared (design #24 §0.4d).** There is no ``netted`` flag on
    any model, so a caller cannot assert an offset into existence. A netting is valid only
    when **all four** premises hold simultaneously:

    1. the receivable is a present, finite, non-negative **gross** ``CREDIT`` magnitude;
    2. the payable is a present, finite, non-negative **gross** ``DEBIT`` magnitude;
    3. ``same_scope is True`` — account, currency, value date, legal entity, and settlement
       system all match (§14 line 377);
    4. ``enforceable_netting_proof is True`` — the injected legal-enforceability proof.

    Because an offset can only be expressed by *erasing or reducing* one of the two
    magnitudes, requiring both to still stand side by side proves the absence of netting
    **structurally**: the failure mode is a missing magnitude, which is a ``None`` that fails
    closed, not a boolean that an ``is not True`` gate could wave through.

    **Honest disclosure (design #24 §10.4 G2).** Premises 3 and 4 arrive as **injected
    positive-polarity flags**; Phase 1 does not itself establish legal enforceability. What
    it does establish structurally is the gross coexistence, so a caller who forged
    ``enforceable_netting_proof=True`` would still have to produce two real gross magnitudes
    in one scope. The actual enforceability rule is a Phase-0 legal question (ADR §29 Q6) and
    the netting **benefit** on the aggregate-risk axis is are's ``BenefitKind.NETTING`` — a
    different proposition on a different axis (§3.5).

    Direction membership is checked with ``is`` identity against this package's **own** enum
    (never a token comparison), so a receivable declared ``DELIVERY`` or an unset direction
    is rejected rather than silently accepted.
    [PTF-EV-002 coordinate; the ``/2``, ``/3``, and ``+Broker`` stages remain open.]
    [SAFE-012; SAFE-013]

    Args:
        receivable: The ``CREDIT`` leg (``None`` ⇒ ``False`` ⇒ both stay gross).
        payable: The ``DEBIT`` leg (``None`` ⇒ ``False`` ⇒ both stay gross).
        same_scope: Whether account / currency / value date / legal entity / settlement
            system all match (**positive polarity**).
        enforceable_netting_proof: The injected legal-enforceability proof (**positive
            polarity**).

    Returns:
        ``True`` iff the netting is valid; ``False`` means **both legs stay gross**.
    """
    if receivable is None or payable is None:
        return False
    if receivable.direction is not ObligationLegDirection.CREDIT:
        return False
    if payable.direction is not ObligationLegDirection.DEBIT:
        return False
    if not _is_present_non_negative(receivable.magnitude):
        return False
    if not _is_present_non_negative(payable.magnitude):
        return False
    return same_scope is True and enforceable_netting_proof is True


def missing_counterleg_is_adverse(
    declared_leg: ObligationLeg | None,
    counterleg: ObligationLeg | None,
    counterleg_positively_established: bool | None,
) -> bool:
    """Whether a missing counterleg must be treated as adverse (ADR §9 line 279).

    §9 line 279 verbatim: where a balanced accounting leg cannot be positively established,
    "the missing counterleg remains explicit and the greatest credible adverse union is
    used", and a consumer "SHALL NOT construct a local favourable balancing entry".

    **Polarity note.** This predicate is the *adversity* judgment, so ``True`` means "treat
    it as adverse" — the conservative answer. :func:`post_trade_disposition` consumes its
    logical complement as the ``counterleg_established`` conjunct, so the safe value there is
    still ``True`` and the polarity discipline is unbroken. The default direction is adverse:
    every failure to positively establish a balanced pair returns ``True``.

    A counterleg is only established when **all** of the following hold — an absent
    counterleg, an unproven one, an UNKNOWN magnitude, an undirected one, and one pointing
    the *same* way as the declared leg are all adverse:

    * the declared leg exists and carries a direction;
    * the counterleg exists, carries a present finite non-negative gross magnitude, and its
      direction is the declared leg's **opposite**
      (:data:`~tos.posttrade.vocabulary.OPPOSITE_DIRECTION_PAIRS`: ``DEBIT``/``CREDIT``,
      ``DELIVERY``/``RECEIPT``, ``ENCUMBRANCE``/``RELEASE``). A "counterleg" in the same
      direction is not a balance, it is a second exposure;
    * ``counterleg_positively_established is True`` (**positive polarity**).

    The "local favourable balancing entry" prohibition needs no branch: there is no field or
    predicate anywhere in this package by which a consumer could synthesize one (design #24
    §4.3-3 — structural absence).
    [PTF-EV-002 coordinate; the ``/2``, ``/3``, and ``+Broker`` stages remain open.]
    [SAFE-012; SAFE-022]

    Args:
        declared_leg: The leg whose counterpart is in question (``None`` ⇒ adverse).
        counterleg: The claimed balancing leg (``None`` ⇒ adverse).
        counterleg_positively_established: The injected positive establishment proof
            (**positive polarity**).

    Returns:
        ``True`` iff the missing / unproven counterleg must be carried as adverse.
    """
    if declared_leg is None or declared_leg.direction is None:
        return True
    if counterleg is None or counterleg.direction is None:
        return True
    if (declared_leg.direction, counterleg.direction) not in OPPOSITE_DIRECTION_PAIRS:
        return True
    if not _is_present_non_negative(counterleg.magnitude):
        return True
    return counterleg_positively_established is not True


# ===========================================================================
# §5.4 collateral conservation, margin-state non-implication, cash-kind identity
# (ADR §15 / §14; PTF-EV-004 substrate, core L1 slice; PTF-INV-010/011)
# ===========================================================================


def collateral_no_double_use(
    allocations: Sequence[CollateralAllocation],
) -> bool:
    """Whether collateral encumbrance is conserved (ADR §15 line 386; PTF-INV-011).

    §15 line 386 verbatim: "The same collateral unit SHALL NOT be counted as both free and
    encumbered, pledged to two obligations, or reusable before confirmed release."

    Three prohibitions, all realized as **structure over magnitudes and identities** rather
    than flags (design #24 §5.4; the #18 / #21 structural-derivation precedent):

    1. **free XOR encumbered** — exactly one of the two magnitudes may be positive. Both
       positive is the double count the ADR names; both zero is an unaccounted unit, which is
       undecidable and therefore also rejected (a unit that is neither free nor encumbered
       has no provable allocation state);
    2. **one obligation per encumbrance** — more than one ``pledged_obligation_ids`` entry is
       the two-obligation pledge. An encumbered unit must name exactly one obligation and
       carry a positive pledged magnitude; a free unit must name none and pledge nothing;
    3. **no reuse before confirmed release** — a repeated ``unit_id`` is admitted only when
       the *earlier* allocation positively declares ``release_state is CONFIRMED_RELEASE``.
       The premise is positive: there is no ``not_yet_released`` flag to leave unset.

    Plus the conservation sum: ``pledged_magnitude <= available_magnitude`` on every
    allocation. No ratio, haircut, or eligibility percentage appears anywhere — every
    magnitude is injected (§8.0), and a broker's favourable collateral figure is a Critical
    Input **ceiling** (§15 line 387) consumed as a coordinate, never re-derived.

    **∅ structural guard (design #24 §5.4 / §4.8 row 1 isomorph).** An **empty** allocation
    sequence is ``False``: nothing was accounted, so conservation is unproven. "No collateral
    examined" must never read as "no double use".

    An unidentified unit (``unit_id`` absent or empty) is rejected: the reuse check groups on
    identity, so an anonymous allocation could evade it.
    [PTF-EV-004 coordinate; the ``/2``, ``/3``, and ``+Broker`` stages remain open.]
    [SAFE-013; SAFE-014; SAFE-024]

    Args:
        allocations: The observed collateral allocations, in claimed order (empty ⇒
            ``False``).

    Returns:
        ``True`` iff every allocation is exclusively free or encumbered, pledged to at most
        one obligation, within its available magnitude, and never reused before a confirmed
        release.
    """
    if not allocations:
        return False
    released_units: set[str] = set()
    seen_units: set[str] = set()
    for allocation in allocations:
        unit = allocation.unit_id
        if not unit:
            return False
        free = allocation.free_magnitude
        encumbered = allocation.encumbered_magnitude
        pledged = allocation.pledged_magnitude
        available = allocation.available_magnitude
        if free is None or encumbered is None or pledged is None or available is None:
            return False
        if not _is_present_non_negative(free):
            return False
        if not _is_present_non_negative(encumbered):
            return False
        if not _is_present_non_negative(pledged):
            return False
        if not _is_present_non_negative(available):
            return False
        # (1) free XOR encumbered — both positive is the double count, both zero is
        #     an unaccounted unit; either way the allocation state is not provable.
        if (free > 0) == (encumbered > 0):
            return False
        # (2) one obligation per encumbrance; a free unit pledges nothing.
        if encumbered > 0:
            if len(allocation.pledged_obligation_ids) != 1 or pledged <= 0:
                return False
        elif allocation.pledged_obligation_ids or pledged > 0:
            return False
        # conservation sum
        if pledged > available:
            return False
        # (3) reuse only after a positively declared confirmed release.
        if unit in seen_units and unit not in released_units:
            return False
        seen_units.add(unit)
        if allocation.release_state is MarginCollateralState.CONFIRMED_RELEASE:
            released_units.add(unit)
        else:
            released_units.discard(unit)
    return True


def margin_collateral_states_distinct(
    observed_state: MarginCollateralState | None,
    claimed_state: MarginCollateralState | None,
) -> bool:
    """Whether a margin / collateral claim rests on its own observation (§15 line 385).

    §15 line 385 verbatim: a margin observation, margin call, collateral request, instruction
    acknowledgement, pledged collateral, accepted collateral, available excess, and confirmed
    release are eight distinct states, and "**No one state implies another**".

    **Polarity (why identity, not inequality) — read this before changing the return.** The
    caller is asserting ``claimed_state`` on the strength of having observed
    ``observed_state``. There are exactly two cases:

    * ``observed is claimed`` — the claim *is* the observation, so no implication was
      performed and the non-implication invariant is respected ⇒ ``True``;
    * ``observed is not claimed`` — the claim can only have been reached **by implication
      from a different state**, which §15 line 385 forbids ⇒ ``False``.

    So the predicate is the identity ``observed is claimed``, exactly isomorphic to
    :func:`cash_kind_matches_requirement`. The name reads "the states are kept distinct":
    a ``False`` is the report that they were *not* kept distinct — that one was collapsed
    into the other. Design #24 §4.8 row 17 fixes the same two directions ("an implication
    attempt ⇒ ``False``"; "``observed_state`` does not imply ``claimed_state`` ⇒ distinct").

    A ``None`` on either side is an undeclared state and fails closed (a missing observation
    supports no claim, and a missing claim is nothing to support). Note that the ``is None``
    guard is load-bearing: without it two ``None`` states would satisfy ``observed is
    claimed`` and pass.

    The broker's favourable margin / buying-power / collateral figure is a Critical Input and
    a **ceiling**, not an unconditional proof (§15 line 387); it arrives as an injected
    brokercap coordinate and is never re-decided here.
    [PTF-EV-004 coordinate; the ``/2``, ``/3``, and ``+Broker`` stages remain open.]
    [SAFE-013; SAFE-014]

    Args:
        observed_state: The state actually observed (``None`` ⇒ ``False``).
        claimed_state: The state being asserted (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the claim is the observation itself — never an implication from another
        state.
    """
    if observed_state is None or claimed_state is None:
        return False
    return observed_state is claimed_state


def cash_kind_matches_requirement(
    requested: CashKind | None,
    available: CashKind | None,
) -> bool:
    """Whether the available cash kind satisfies the requested one (PTF-INV-010; §14).

    PTF-INV-010 line 188 verbatim: "Ledger cash, pending cash, settled cash, withdrawable
    cash, buying power, and collateral-eligible cash remain distinct" and "**cannot be
    silently substituted**". §14 line 375: sale proceeds, expected dividends, pending FX,
    receivables, and buying power are not settled reusable cash. §25.4 rejects "Buying power
    is available cash".

    The proposition is a **single identity**: the requirement is met only when the available
    kind *is* the requested kind. Offering ``BUYING_POWER`` where ``WITHDRAWABLE_CASH`` is
    required is precisely the §25.4 substitution and returns ``False``; **every** non-identity
    pair does, in both directions (there is no "close enough" ordering among the six kinds,
    and inventing one would be the substitution the invariant forbids).

    A ``None`` on either side fails closed — and the guard is load-bearing, since two
    ``None`` kinds would otherwise satisfy the identity.

    **Substrate boundary (honest disclosure, design #24 §5.4/§6.1).** The non-substitution
    *structure* is the EV-L1 slice. The **proof** that a given kind is actually available —
    the buying-power-to-withdrawable transition, settlement completion, partial settlement,
    failure handling — is PTF-EV-003 ``EV-L2/3+Broker`` and is **not** authored here. Phase 1
    keeps availability UNKNOWN, which is why an L1-only
    :func:`post_trade_disposition` lands on ``POST_TRADE_TRAPPED`` at best.
    [PTF-EV-004 coordinate; PTF-EV-003 availability proof deferred to ``EV-L2/3``.]
    [SAFE-010; SAFE-011]

    Args:
        requested: The cash kind the obligation requires (``None`` ⇒ ``False``).
        available: The cash kind actually available (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff ``requested`` and ``available`` are the same kind.
    """
    if requested is None or available is None:
        return False
    return requested is available


# ===========================================================================
# §5.5 event obligation legs + event-state non-implication
# (ADR §17; PTF-EV-006 substrate, core L1 slice; the nontrade ownership boundary)
# ===========================================================================


def obligation_legs_from_event_complete(
    event_leg_kinds_required: frozenset[EventObligationLegKind],
    present_obligation_legs: frozenset[EventObligationLegKind],
) -> bool:
    """Whether an event's resulting obligation legs are complete (ADR §17 line 416).

    §17 line 416 verbatim: an exercise / assignment / expiry / delivery / cash-settlement /
    conversion / redemption / distribution / tender / rights / corporate-action event "SHALL
    model every credible **asset, cash, fee, tax, financing, margin, borrow, custody, and
    delivery** leg" — the nine
    :class:`~tos.posttrade.vocabulary.EventObligationLegKind` members.

    **Ownership boundary (design #24 §3.5 — the largest one in this package).** ADR-002-010
    §16 line 309 and ADR-002-030 §17 line 414 are **mutual** deferrals: nontrade owns the
    non-trade **event** and transformation identity plus the event workflow lifecycle; this
    package owns the **resulting obligation legs** and their finality. The word "leg" appears
    on both axes and means different things — a nontrade ``CredibleTransitionLegKind`` is a
    credible economic *state during* an event, an :class:`~tos.posttrade.records.ObligationLeg`
    is an exact economic *effect with finality*. Nothing here re-classifies an event.

    **∅ structural guard (isomorphic to :func:`obligation_leg_set_complete`).** An **empty**
    required set is ``False``: ``∅ <= present`` would certify every event as fully modelled.
    The applicable subset is **event-class-parametric** and injected; this package publishes
    :data:`~tos.posttrade.vocabulary.EVENT_OBLIGATION_LEG_MINIMUM_SET` only as a convenience
    universe and never defaults to it.
    [PTF-EV-006 coordinate; the ``/2``, ``/3``, and ``+Broker`` stages remain open.]
    [SAFE-012; SAFE-013]

    Args:
        event_leg_kinds_required: The applicable leg kinds for this event class (**injected**;
            empty ⇒ ``False``).
        present_obligation_legs: The leg kinds actually modelled.

    Returns:
        ``True`` iff every required leg kind is present.
    """
    if not event_leg_kinds_required:
        return False
    return event_leg_kinds_required <= present_obligation_legs


def event_state_not_obligation_finality(
    nontrade_event_state: str | None,
    finality_proof_present: Mapping[FinalityDimensionKind, bool | None],
) -> bool:
    """Whether obligation finality rests on proof rather than an event state (§17 line 418).

    §17 line 418 verbatim: "**An ADR-002-010 event state such as ``APPLIED_LOCAL`` or
    ``RECONCILED`` does not prove its resulting obligations final.**" PTF-INV-004 adds that
    the absence of an exercise / assignment / delivery / corporate-action report by a local
    deadline is not proof that no obligation exists.

    **The event state is structurally unread.** ``nontrade_event_state`` is accepted so the
    nontrade coordinate travels with the decision for the consuming runtime, and it is then
    ``del``-ed: **no** value of it — ``APPLIED_LOCAL``, ``RECONCILED``, ``None``, or a forged
    token — can change this function's result. That is a stronger realization of the
    non-implication than any branch could be, because there is no branch to invert, and a §7
    property asserts the invariance across every token (the nontrade
    ``protective_action_may_proceed`` precedent, ``nontrade/predicates.py:721``).

    What the function *does* require is positive proof: at least one finality dimension must
    carry its own ``is True`` entry. An **empty** proof map, or a map in which no dimension is
    positively proven, is ``False`` — the ∅ guard that stops "no proof anywhere" from reading
    as "the event state did not overreach, so we are fine" (design #24 §4.8 row 7). As in
    :func:`finality_dimensions_orthogonal`, the emptiness check is written explicitly even
    though ``any(())`` is already ``False``: it states the ∅ rule as a standing invariant that
    a later edit cannot quietly default away.

    Which *particular* dimension a claim rests on is
    :func:`finality_dimensions_orthogonal`'s judgment; this predicate answers the separate
    question of whether the obligation's finality picture is proof-borne at all.
    [PTF-EV-006 coordinate; the ``/2``, ``/3``, and ``+Broker`` stages remain open.]
    [SAFE-004; SAFE-021]

    Args:
        nontrade_event_state: The injected nontrade ``NonTradeEventWorkflowState`` token.
            **Structurally inert** — carried for the consuming runtime only.
        finality_proof_present: The injected per-dimension proof presence map (**positive**
            polarity ``bool | None``). Empty or all-unproven ⇒ ``False``.

    Returns:
        ``True`` iff at least one finality dimension carries its own positive proof.
    """
    # Structurally inert (see above); a §7 property asserts the result is invariant under
    # every value of this argument, including the two tokens §17 line 418 names.
    del nontrade_event_state

    if not finality_proof_present:
        return False
    return any(proven is True for proven in finality_proof_present.values())


# ===========================================================================
# §5.6 statement coverage, source independence, absence-as-negative-evidence
# (ADR §19; PTF-EV-008 substrate, core L1 slice; +Security deferred; PTF-INV-014)
# ===========================================================================


def statement_coverage_complete(manifest: StatementCoverageManifest | None) -> bool:
    """Whether a statement's coverage is proven complete (ADR §19 line 443; PTF-INV-014).

    §19 line 443 requires exact coverage to be **proven**: every expected page, file,
    section, cursor, checksum, and record count received, no missing interval, and the
    revision, cutoff, and period boundary present. §19 line 450: a preliminary, truncated,
    stale, or conflicting statement is not complete coverage. §19 line 448: being ``FINAL``,
    contractual, signed, or independently delivered "does not make it unconditional truth
    outside the approved proof recipe" — so a ``FINAL`` class is a necessary coordinate, never
    a sufficient one, and the whole conjunction still has to hold.

    The conjunction (every element positive):

    * each of the five set axes (:data:`~tos.posttrade.records.STATEMENT_COVERAGE_SET_AXES`)
      satisfies ``expected <= received``. Iterating the data table rather than hand-rolling
      five comparisons means a later edit cannot silently drop an axis;
    * the **∅ structural guard**: at least one expected set is non-empty. A manifest that
      expects nothing proves nothing — ``∅ <= received`` holds trivially for all five axes,
      so an empty manifest would otherwise certify perfect coverage of nothing (design #24
      §4.8 row 8);
    * both record counts are present and **equal** (the sixth §19 line 443 axis);
    * ``missing_intervals`` is empty;
    * the source identity, period start, period end, revision, and cutoff are all present;
    * the statement class is ``FINAL`` or ``REVISED`` — ``PRELIMINARY`` is subject to
      restatement by construction (§19 line 450) and an undeclared class fails closed.

    **Staleness is deliberately not judged here.** ``MAX_statement_coverage_manifest_age_ms``
    (VP-002 line 749) is ``null`` with ``owner: TBD``, and this package is clock-free, so an
    age verdict is an injected EV-L2/3 coordinate (design #24 §8.1). Conflict likewise
    arrives through the record-pair outcome, not through this predicate.
    [PTF-EV-008 coordinate; the ``/2``, ``/3``, ``+Broker``, and ``+Security`` stages remain
    open.]
    [SAFE-022; SAFE-023]

    Args:
        manifest: The coverage manifest (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the manifest positively proves exact, complete, final-or-revised
        coverage.
    """
    if manifest is None:
        return False
    any_expected = False
    for expected_field, received_field in STATEMENT_COVERAGE_SET_AXES:
        expected: frozenset[str] = getattr(manifest, expected_field)
        received: frozenset[str] = getattr(manifest, received_field)
        if expected:
            any_expected = True
        if not expected <= received:
            return False
    if not any_expected:
        return False
    if manifest.expected_record_count is None or manifest.received_record_count is None:
        return False
    if manifest.expected_record_count != manifest.received_record_count:
        return False
    if manifest.missing_intervals:
        return False
    if not all(
        (
            manifest.source_identity,
            manifest.period_start,
            manifest.period_end,
            manifest.revision,
            manifest.cutoff,
        )
    ):
        return False
    return manifest.statement_class in _COVERAGE_BEARING_STATEMENT_CLASSES


def statement_sources_independent(
    source_a_shared_deps: frozenset[str],
    source_b_shared_deps: frozenset[str],
) -> bool:
    """Whether two statement sources are independent paths (§19 line 445; PTF-INV-014).

    §19 line 445 verbatim: a broker API plus that broker's statement, or a broker plus a
    custodian, that share "one book, parser, administrator, or transport" are **not**
    independent paths. Two sources corroborate only when their declared dependency sets are
    **disjoint**.

    **A different grain from recon's (design #24 §3.5).** recon's ``classify_field``
    common-mode rule (``recon/predicates.py:127``, RECON-EV-001: "common-mode paths (shared
    ``independence_class``) cannot corroborate each other") works at the **per-field** grain
    over an evidence-path independence class. This predicate works at the **statement-source**
    grain over the book / parser / administrator / transport set. Neither substitutes for the
    other, and this package re-authors neither: it consumes recon's field confidence as an
    injected token and owns only the source-grain disjointness.

    **∅ structural guard, both sides.** An **empty** dependency set is ``False``: a source
    that declares no dependencies has not been shown to be independent, it has merely not
    been described. ``∅.isdisjoint(anything)`` is ``True``, so without this guard an
    undeclared source would certify as independent of everything — the exact vacuous pass the
    invariant is about.

    **Honest disclosure (design #24 §10.4 G5).** Phase 1 owns the *structural* disjointness of
    two **declared** sets. Discovering a dependency a source failed to declare — a hidden
    shared transport, a shared upstream book — is the ``+Security`` boundary assessment of
    PTF-EV-008 and the Phase-0 common-mode rules (ADR §29 Q5), and is **not** claimed here.
    [PTF-EV-008 coordinate; the ``/2``, ``/3``, ``+Broker``, and ``+Security`` stages remain
    open.]
    [SAFE-022; SAFE-023]

    Args:
        source_a_shared_deps: The first source's declared book / parser / administrator /
            transport dependencies (empty ⇒ ``False``).
        source_b_shared_deps: The second source's declared dependencies (empty ⇒ ``False``).

    Returns:
        ``True`` iff both sets are non-empty and disjoint.
    """
    if not source_a_shared_deps or not source_b_shared_deps:
        return False
    return source_a_shared_deps.isdisjoint(source_b_shared_deps)


def absence_is_negative_evidence_only(
    line_item_absent: bool | None,
    coverage_complete: bool | None,
    correction_semantics_support: bool | None,
    source_capability_supports: bool | None,
) -> bool:
    """Whether a missing line item may be read as negative evidence (§19 line 448).

    §19 line 448 verbatim: the absence of a line item is negative evidence **only** where
    "exact coverage, **correction semantics**, and source capability positively support" that
    reading. PTF-INV-004 ("Absence Is Not Finality") adds that silence, a passed cutoff, a
    missing page, a flat position, and a missing acknowledgement never prove that an
    obligation does not exist.

    A four-way positive conjunction, every element ``is True``:

    * ``line_item_absent`` — the absence itself must be **proven**, not assumed. ``None``
      means "we do not know whether it is absent", so the antecedent fails and the answer is
      UNKNOWN (⇒ ``False``);
    * ``coverage_complete`` — the §19 line 443 exact coverage
      (:func:`statement_coverage_complete`'s verdict);
    * ``correction_semantics_support`` — the correction rules **actively** support "this
      line's absence means no obligation";
    * ``source_capability_supports`` — the source is capable of reporting the line at all
      (the brokercap coordinate).

    **Time is not a signal here (design #24 §5.6 M6).** An earlier draft gated this on a
    ``correction_horizon_passed`` flag; that is exactly the signal PTF-INV-004 forbids —
    "cutoff passage ... never proves that an obligation does not exist" (ADR line 164). What
    §19 line 448 requires is the positive support of **correction semantics**, not the
    passage of time, so the parameter is the semantics one and this package reads no clock.

    **Honest disclosure (design #24 §10.4 G3).** ``coverage_complete``,
    ``correction_semantics_support``, and ``source_capability_supports`` arrive as injected
    positive-polarity flags; Phase 1 gates them ``is True`` and defers their structural
    enforcement to the statement-pagination runtime (EV-L2/3) and the Phase-0 correction rules.
    [PTF-EV-008 coordinate; the ``/2``, ``/3``, ``+Broker``, and ``+Security`` stages remain
    open.]
    [SAFE-012; SAFE-022]

    Args:
        line_item_absent: Whether the line item is **proven** absent (``None`` ⇒ unknown ⇒
            ``False``).
        coverage_complete: The exact-coverage verdict (**positive polarity**).
        correction_semantics_support: Whether correction semantics positively support reading
            this absence as "no obligation" (**positive polarity**).
        source_capability_supports: Whether the source is capable of reporting the line
            (**positive polarity**).

    Returns:
        ``True`` iff all four premises are positively proven.
    """
    return (
        line_item_absent is True
        and coverage_complete is True
        and correction_semantics_support is True
        and source_capability_supports is True
    )


# ===========================================================================
# §5.7 finality proof class-specificity / non-transferability / currency
#      + finality-grants-nothing (ADR §11 / §10 line 312; core substrate)
# ===========================================================================


def finality_proof_class_specific(proof: PostTradeFinalityProof | None) -> bool:
    """Whether a finality proof is exact and class-specific (ADR §11 line 320-326).

    §11 line 320-326 requires a proof to bind the exact obligation identity, version, leg,
    scope, amount, account, currency, value date, generation, and finality class — **and what
    it does not prove**. PTF-INV-005 verbatim: "One global ``SETTLED``, ``CLOSED``,
    confidence score, statement flag, or operator decision cannot replace exact per-field
    proof."

    **The substitution is structurally impossible, not merely rejected.**
    :class:`~tos.posttrade.records.PostTradeFinalityProof` carries no
    ``global_settled_flag``, no ``confidence_score``, no ``statement_flag``, and no
    ``operator_decision`` field, so a global claim has no field to travel in. What such a
    "proof" looks like in practice is one with no ``finality_class``, no ``leg_scope``, and an
    empty ``does_not_prove`` — and this conjunction rejects it. A §7 property asserts the four
    phantom field names stay absent, so the absence cannot be undone by a later edit.

    The conjunction:

    * the obligation reference and version are present;
    * the ``leg_scope`` is **fully specified** — all six §11 line 328 components
      (:func:`_scope_fully_specified`). An under-specified scope covers a *set* of legs, and
      a proof over a set is the union §11 line 328 forbids;
    * the amount is a present, finite, non-negative magnitude;
    * the ``finality_class`` is present **and equals the scope's** finality class (an
      incoherent proof that claims one class while scoping another is rejected);
    * the ``bound_generation`` is present (the reopen coordinate,
      :func:`finality_proof_current`);
    * ``does_not_prove`` is **non-empty** — §11 line 320-326 makes the negative space part of
      the proof, and a proof that never declared its own limits is exactly how a
      single-dimension proof gets read as global finality.

    A failure here is a **contradiction**, not a mere gap: a global flag was offered in place
    of an exact proof, so :func:`post_trade_disposition` maps it to
    ``POST_TRADE_CONFLICTED`` (design #24 §4.8 row 21).
    [SAFE-005; SAFE-010; SAFE-011; SAFE-020]

    Args:
        proof: The finality proof (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff the proof binds an exact, coherent, self-limiting class-specific claim.
    """
    if proof is None:
        return False
    if not _scope_fully_specified(proof.leg_scope):
        return False
    if not proof.obligation_ref or not proof.obligation_version:
        return False
    if proof.finality_class is None:
        return False
    scope = proof.leg_scope
    if scope is None or proof.finality_class is not scope.finality_class:
        return False
    if proof.bound_generation is None:
        return False
    if not _is_present_non_negative(proof.amount):
        return False
    return bool(proof.does_not_prove)


def finality_proof_non_transferable(
    proof: PostTradeFinalityProof | None,
    target_leg_scope: ObligationLegScope | None,
    *,
    target_obligation_ref: str | None = None,
    target_obligation_version: str | None = None,
) -> bool:
    """Whether a finality proof applies to exactly this leg scope (§11 line 328; §11 line 320).

    §11 line 328 verbatim: a finality proof is "**non-transferable and non-unionable**" — the
    proof of one leg, account, currency, value date, source revision, or finality class SHALL
    NOT be patched onto or reused for another.

    The judgment is whole-scope structural equality: the proof's
    :class:`~tos.posttrade.records.ObligationLegScope` must equal ``target_leg_scope``
    component for component. Comparing the scope **as a value** rather than field by field is
    deliberate — a hand-rolled conjunction is exactly the thing a later edit shortens, and a
    shortened one is a transfer.

    Both scopes must additionally be **fully specified** (:func:`_scope_fully_specified`):
    two scopes that agree only because both leave the currency ``None`` have not been shown
    to be the same leg, they have been shown to be equally undescribed. Without that guard a
    pair of empty scopes would compare equal and certify a transfer of a proof about nothing
    onto anything.

    **The cross-obligation seal (design #24 v1.2 erratum; adversarial code review MAJOR).**
    The six §11 line 328 scope components name a *leg within an account, currency, value date,
    source revision, and finality class* — they do **not** name the obligation. Two distinct
    obligations can therefore legitimately share one scope tuple (the same account settling
    the same currency on the same value date), and a scope-only comparison would accept one
    obligation's proof as covering the other's identical leg. §11 line 320 requires the proof
    to bind the "exact obligation identity" and version, so when the caller supplies the
    target obligation's identity, it is compared as well.

    The two keyword arguments are **optional for backwards compatibility**: a caller that
    supplies neither gets the original scope-only comparison. Supplying either **narrows**
    the verdict and can only turn a ``True`` into a ``False`` — the conservative direction. A
    supplied identity that the proof does not carry (``proof.obligation_ref is None``) is a
    mismatch, so an unbound proof cannot be waved onto a named obligation.

    A failure here is a **contradiction** (a proof was reused across legs or across
    obligations), so :func:`post_trade_disposition` maps it to ``POST_TRADE_CONFLICTED``
    (design #24 §4.8 row 10).
    [SAFE-005; SAFE-020]

    Args:
        proof: The finality proof (``None`` ⇒ ``False``).
        target_leg_scope: The scope the caller wishes to apply it to (``None`` ⇒ ``False``).
        target_obligation_ref: The identity of the obligation the caller wishes to apply the
            proof to (§11 line 320). ``None`` ⇒ not compared (legacy scope-only behaviour).
        target_obligation_version: The version of that obligation. ``None`` ⇒ not compared.

    Returns:
        ``True`` iff the proof's fully-specified scope equals the fully-specified target and
        every supplied obligation identity component matches the proof's.
    """
    if proof is None or target_leg_scope is None:
        return False
    if not _scope_fully_specified(proof.leg_scope):
        return False
    if not _scope_fully_specified(target_leg_scope):
        return False
    if proof.leg_scope != target_leg_scope:
        return False
    if (
        target_obligation_ref is not None
        and proof.obligation_ref != target_obligation_ref
    ):
        return False
    return (
        target_obligation_version is None
        or proof.obligation_version == target_obligation_version
    )


def finality_proof_current(
    proof: PostTradeFinalityProof | None,
    active_generation: int | None,
) -> bool:
    """Whether a finality proof is still current (§11 line 330; PTF-INV-013).

    §11 line 330 verbatim: "A later correction supersedes the proof, **advances generation**
    ... it does not erase history." PTF-INV-013: a correction **reopens** the affected
    finality.

    So "finality is monotone" is emphatically **not** the naive "once proven, always proven"
    (design #24 §4.5-B, the ninth truth-table row). The four things that really are monotone
    are: the generation increases and never reverts; ``UNKNOWN -> PROVEN`` happens only
    through dimension-specific proof; history is append-only; and a ``PROVEN`` never implies a
    consequence. On top of those, a proof is **current** only while the generation it bound
    is still the active one — the moment a correction advances the generation, the earlier
    proof falls behind and finality reopens.

    A pure integer comparison, L1-decidable: the generation is a ``tos.ordering`` coordinate
    (design #24 §3.2), never a clock and never a duration, so no bound is consulted and none
    is hardcoded. An absent bound generation or an absent active generation is UNKNOWN and
    fails closed — a proof that never declared which generation it bound can never be shown to
    be current.
    [SAFE-020; SAFE-032; SAFE-033]

    Args:
        proof: The finality proof (``None`` ⇒ ``False``).
        active_generation: The current Post-Trade Obligation Generation (``None`` ⇒
            ``False``).

    Returns:
        ``True`` iff the proof's bound generation equals the active generation.
    """
    if proof is None or active_generation is None:
        return False
    if proof.bound_generation is None:
        return False
    return proof.bound_generation == active_generation


def post_trade_consequence_all_false(
    consequence: AllFalsePostTradeConsequence | None,
) -> bool:
    """Whether a post-trade artifact grants no consequence (§10 line 312; PTF-INV-009).

    §10 line 312 verbatim: "``SATISFIED_PENDING_FINALITY`` is not final. ``FINALITY_PROVEN``
    proves only the exact declared leg and proof class. ``CLOSED`` preserves immutable
    lineage and can be superseded by a later correction without destructive overwrite. **No
    lifecycle state creates capacity release, available cash, legal title, or permission.**"
    §1 line 27: a flat position, a closed order, a passed settlement date, a
    ``FINALITY_PROVEN`` artifact, a favourable receivable, and a statement balance none of
    them release capacity. §21 line 492: an obligation closure "may transfer consumption
    rather than release it" — and only the RCL may perform that transition (§1 line 21,
    PTF-INV-008). §1 line 31 / PTF-INV-016 add the egress seal.

    **Finality proves the LEG, not the CONSEQUENCE** — this predicate is the type-level
    statement of it. :class:`~tos.posttrade._base.AllFalsePostTradeConsequence` already
    rejects any ``True`` flag at construction, so on the normal validation path this is
    unconditionally ``True`` for every constructible block **and for every lifecycle state,
    including ``FINALITY_PROVEN``**. It exists as **defence in depth**: ``model_construct``
    skips validators, so a forged block can carry a ``True`` — or a truthy non-``bool`` such
    as ``1`` / ``"yes"`` / ``[1]``. The re-check therefore demands every declared flag be the
    singleton ``False``, so a truthy non-``bool`` is rejected too, a ``None`` block (nothing
    to prove) is ``False`` rather than a vacuous pass, and a **zero-field** block is ``False``
    as well — a block that declares no flag proves no absence of consequence (the #21 M26
    zero-field lesson).

    There is no positive side to canary here: no input makes a consequence ``True``, because
    no consequence is ever granted (design #24 §4.7 — isomorphic to the #18 §4.4 / #21 §4.4
    all-false blocks).
    [SAFE-010; SAFE-011; SAFE-014; SAFE-015]

    Args:
        consequence: The consequence block to re-check (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff every declared flag is the singleton ``False``.
    """
    if consequence is None:
        return False
    field_names = type(consequence).model_fields
    if not field_names:
        # A block that declares no flag proves nothing (∅-vacuous guard).
        return False
    return all(getattr(consequence, name, None) is False for name in field_names)


# ===========================================================================
# §5.8 the single PostTradeDisposition producer (design #24 C1)
# ===========================================================================


def post_trade_disposition(
    *,
    # -- §5.1 --
    leg_set_complete: bool,
    finality_orthogonal: bool,
    # -- §5.3 --
    monetary_conservative: bool,
    netting_proof_ok: bool,
    counterleg_established: bool,
    # -- §5.4 --
    collateral_conserved: bool,
    margin_states_distinct: bool,
    cash_kind_ok: bool,
    # -- §5.5 --
    event_legs_complete: bool,
    event_state_not_final_ok: bool,
    # -- §5.6 --
    statement_coverage_ok: bool,
    sources_independent: bool,
    absence_gate_ok: bool,
    # -- §5.7 --
    proof_class_specific: bool,
    proof_non_transferable: bool,
    proof_current: bool,
    # -- non-bool injections --
    commit_outcome: ObligationCommitOutcome | None,
    field_confidence: str | None,
    availability_proven: bool | None,
) -> PostTradeDisposition:
    """Fold every post-trade signal into one disposition (design #24 §5.8; **sole producer**).

    This is the **only** producer of
    :class:`~tos.posttrade.vocabulary.PostTradeDisposition` (design #24 C1): all
    **twenty-two** rows of the §4.8 void table fold through it, so no guard is left
    delegating to an ownerless "handled elsewhere" step. The signature takes **nineteen**
    inputs — the sixteen positive-polarity bool conjuncts of :data:`DISPOSITION_CONJUNCTS`
    plus ``commit_outcome``, ``field_confidence``, and ``availability_proven`` — because an
    earlier eight-input draft omitted nine of them and thereby allowed
    ``POST_TRADE_ADMISSIBLE`` while a statement common-mode (PTF-INV-014), a cross-leg proof
    reuse (§11 line 328), or a global-flag substitution (PTF-INV-005) stood unresolved. Every
    conjunct is now in the conjunction, and a §7 property asserts the 1:1 correspondence with
    :data:`VOID_TABLE_ROWS` in **both** directions.

    **Five ranks, a total order, first match wins** (most conservative first)::

        1  a collateral double-use, a common-mode statement source, a non-class-specific
           or transferred finality proof, a REJECTED_CONFLICT commit, or a CONFLICTED
           field confidence                                     -> POST_TRADE_CONFLICTED
        2  a REJECTED_UNKNOWN commit, or an UNKNOWN field
           confidence                                           -> POST_TRADE_QUARANTINED_UNKNOWN
        3  availability is not positively proven                -> POST_TRADE_TRAPPED
        5  every conjunct positively proven, the commit outcome
           accepted, the confidence CORROBORATED, and
           availability proven                                  -> POST_TRADE_ADMISSIBLE
        4  otherwise (the restrictive residue)                  -> POST_TRADE_BLOCK_NEW_RISK

    **Why that order (design #24 §5.8 Q2).** ``CONFLICTED`` is an *active contradiction* —
    two records or two sources assert incompatible things and both must be contained — and is
    the most severe. ``QUARANTINED_UNKNOWN`` is unattributable or undecidable, so conservatism
    must expand across the whole greatest-credible dependency closure: **unbounded** scope.
    ``TRAPPED`` is an identified, **bounded** exposure that merely cannot be exited. The
    wider-scope constraint dominates the narrower one, so contradiction > unbounded unknown >
    bounded trap > block > admissible.

    **Rank-1 and rank-3 denials use ``is not True`` deliberately.** In a denial branch that
    reading sends a ``None`` to the *more* conservative member, which is the safe direction.
    The series discipline forbids ``is not True`` where it would **permit**; the rank-5
    conjunction below therefore uses ``is True`` on every one of the sixteen conjuncts, so no
    ``None`` and no truthy non-``bool`` can reach ``POST_TRADE_ADMISSIBLE``.

    **``POST_TRADE_ADMISSIBLE`` is never a fall-through residue** (the #16 CRITICAL lesson):
    it is reached only by the positive conjunction of all sixteen bools **and**
    ``commit_outcome`` being ``COMMITTED_ONCE`` or ``IDEMPOTENT_REPLAY`` **and**
    ``field_confidence`` being exactly ``CORROBORATED`` **and** ``availability_proven is
    True``. The residue is ``POST_TRADE_BLOCK_NEW_RISK`` — the conservative member. A new
    signal added to this contract must be woven into the conjunction explicitly; until it is,
    its ``None`` default falls to rank 4 and blocks.

    **Honest disclosure — an L1-only caller can never reach ADMISSIBLE (design #24 §5.8).**
    ``availability_proven`` is a PTF-EV-003 / 007 ``EV-L2/3+Broker`` verdict that Phase 1 does
    not produce, so an L1-only fold always passes ``None`` and lands on
    ``POST_TRADE_TRAPPED`` at best. The ``POST_TRADE_ADMISSIBLE`` canary in §7 reaches it only
    with a simulated ``availability_proven=True``, and that is the honest reflection of "every
    L1 structural property can hold and the obligation still is not admissible without
    settlement availability".

    **A disposition grants nothing** (§10 line 312 / §4.7): even ``POST_TRADE_ADMISSIBLE``
    releases no capacity, makes no cash available, proves no title, grants no permission, and
    transmits nothing — the consuming rcl / are / cur / egress runtime enforces. Row 15 of the
    void table is exactly this: a capacity release or an external send has **no input** here,
    because it is structurally unrepresentable (PTF-INV-008/016), so nothing can move the
    disposition upward. The return value is truthy-untestable; the consume gate is
    ``disposition is PostTradeDisposition.POST_TRADE_ADMISSIBLE``.
    [Closing PTF-EV = 0; no EV-L1-complete claim.]
    [SAFE-004; SAFE-010; SAFE-011; SAFE-050]

    Args:
        leg_set_complete: :func:`obligation_leg_set_complete` output (§4.8 row 1).
        finality_orthogonal: :func:`finality_dimensions_orthogonal` output (row 2).
        monetary_conservative: :func:`monetary_leg_conservative` output (row 3).
        netting_proof_ok: :func:`netting_requires_positive_proof` output (row 4).
        counterleg_established: the **complement** of
            :func:`missing_counterleg_is_adverse` (row 5).
        collateral_conserved: :func:`collateral_no_double_use` output (row 6).
        margin_states_distinct: :func:`margin_collateral_states_distinct` output (row 17).
        cash_kind_ok: :func:`cash_kind_matches_requirement` output (row 18).
        event_legs_complete: :func:`obligation_legs_from_event_complete` output (row 19).
        event_state_not_final_ok: :func:`event_state_not_obligation_finality` output (row 7).
        statement_coverage_ok: :func:`statement_coverage_complete` output (row 8).
        sources_independent: :func:`statement_sources_independent` output (row 9).
        absence_gate_ok: :func:`absence_is_negative_evidence_only` output (row 20).
        proof_class_specific: :func:`finality_proof_class_specific` output (row 21).
        proof_non_transferable: :func:`finality_proof_non_transferable` output (row 10).
        proof_current: :func:`finality_proof_current` output (row 22).
        commit_outcome: :func:`obligation_commit_idempotent` output (rows 11-13).
        field_confidence: The injected recon ``FieldConfidenceClass`` **token** (row 14).
        availability_proven: The injected PTF-EV-003 / 007 settlement / discharge / title
            availability verdict (row 16). ``None`` in every L1-only fold.

    Returns:
        The :class:`~tos.posttrade.vocabulary.PostTradeDisposition`.
    """
    # --- rank 1: active contradiction --------------------------------------------
    if (
        collateral_conserved is not True
        or sources_independent is not True
        or proof_class_specific is not True
        or proof_non_transferable is not True
        or commit_outcome is ObligationCommitOutcome.REJECTED_CONFLICT
        or field_confidence == FIELD_CONFIDENCE_CONFLICTED
    ):
        return PostTradeDisposition.POST_TRADE_CONFLICTED

    # --- rank 2: unattributable / undecidable (unbounded scope) -------------------
    if (
        commit_outcome is ObligationCommitOutcome.REJECTED_UNKNOWN
        or field_confidence == FIELD_CONFIDENCE_UNKNOWN
    ):
        return PostTradeDisposition.POST_TRADE_QUARANTINED_UNKNOWN

    # --- rank 3: identified but unexitable exposure (bounded scope) ---------------
    if availability_proven is not True:
        return PostTradeDisposition.POST_TRADE_TRAPPED

    # --- rank 5: the positive conjunction (never a fall-through residue) ----------
    every_conjunct_proven = (
        leg_set_complete is True
        and finality_orthogonal is True
        and monetary_conservative is True
        and netting_proof_ok is True
        and counterleg_established is True
        and collateral_conserved is True
        and event_state_not_final_ok is True
        and statement_coverage_ok is True
        and sources_independent is True
        and proof_non_transferable is True
        and margin_states_distinct is True
        and cash_kind_ok is True
        and event_legs_complete is True
        and absence_gate_ok is True
        and proof_class_specific is True
        and proof_current is True
    )
    # Identity membership, never ``in``: ``ObligationCommitOutcome`` is a ``StrEnum``, so a
    # bare string ``"COMMITTED_ONCE"`` would satisfy a set ``in`` test by hashing equal. The
    # mandated gate for a result enum is a positive **identity** (design #24 §0.1(11)), and
    # applying it here is what makes a non-member value — a forged token, a raw string, a
    # ``None`` — unable to reach ``POST_TRADE_ADMISSIBLE`` by any route.
    commit_outcome_accepted = any(
        commit_outcome is accepted for accepted in _ACCEPTABLE_COMMIT_OUTCOMES
    )
    if (
        every_conjunct_proven
        and commit_outcome_accepted
        and field_confidence == FIELD_CONFIDENCE_CORROBORATED
        and availability_proven is True
    ):
        return PostTradeDisposition.POST_TRADE_ADMISSIBLE

    # --- rank 4: the restrictive residue ------------------------------------------
    return PostTradeDisposition.POST_TRADE_BLOCK_NEW_RISK
