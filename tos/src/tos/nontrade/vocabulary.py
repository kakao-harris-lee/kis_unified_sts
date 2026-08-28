"""Non-trade vocabulary — the seven nontrade-axis StrEnums (design #21 §2.2).

Spec terms = code terms (design #21 §2; boundary design #1 §2.4). The enums are authored
**verbatim** from ADR-002-010 (§4 event classes, §6 workflow lifecycle, §9 credible
transition legs, §11 transformation polarity) plus the two nontrade-local results
(:class:`CorrectionReversalOutcome`, :class:`NonTradeDisposition`). Item counts are
transcribed against the ADR line ranges and re-asserted by a §7 property test (the #16 M4
truncated-transcription lesson, series discipline 2 — count cross-checks are exhaustive):
§4 = **5** event classes, §6 line 127-140 = 8 + 3 = **11** workflow states, §9 line
185-194 = **10** credible transition legs, §11 = **2** split kinds, **3** transformation
directions, **6** correction outcomes, **5** dispositions.

**Coordinate non-collapse (design #21 §2.2-5 — this module is the canonical home of the
rule).** These are the **non-trade event / transition / transformation** axes. They are
distinct coordinate systems from:

* rcl ``CapacityState`` (``vocabulary.py:29/30``) — the economic capacity axis. Its
  ``QUARANTINED_UNKNOWN`` / ``TRAPPED_CONSUMED`` tokens overlap ours in wording, never in
  type;
* recon ``FieldConfidenceClass`` (``vocabulary.py:26``) — the per-field evidence axis;
* are ``RiskDimensionKind`` / ``AdverseScenarioKind`` (``vocabulary.py:64/65/115``) — the
  aggregate-risk axis;
* replacement ``CredibleIntermediateOutcomeKind`` (``vocabulary.py:158``) — the
  replacement-order axis (its ``PROTECTIVE_ORDER_GAP_OVERLAP`` counterpart is ours);
* orthostate ``KnowledgeState`` / ``BrokerOrderState`` (``vocabulary.py:121/92``) — the
  order / knowledge axes;
* iap ``ConsumptionOutcome.IDEMPOTENT_REPLAY`` (``vocabulary.py:165``, authorization-token
  single-use) and rcl ``ApplyReason.IDEMPOTENT_REPLAY`` (capacity-command) — **different
  propositions** from our economic-event-application
  :attr:`CorrectionReversalOutcome.IDEMPOTENT_REPLAY` (design #21 §0.4e). The three are
  independent downstreams of the one canonical ``classify_record_pair`` primitive and
  never import each other.

Token overlap is intentional (the ADR uses the same words on several axes), so coordinate
non-collapse rests on **distinct types + non-import**: ``tos.nontrade`` imports **none** of
those siblings (sibling edge 0, design #21 §0.4b/§0.4c), so a value from one axis can never
be coerced onto another. Where a sibling token must nonetheless be *recognized* (an
injected verdict crosses the seam as a bare string / StrEnum member), this module fixes the
token as a **local constant** and a §7 seam test locks it against the real sibling member
(the afg ``ADMISSIBILITY_ADMISSIBLE`` / replacement ``ORDER_ADMISSIBILITY_ADMISSIBLE``
precedent).

This module names **no** concrete broker (broker-agnostic — project memory
``tos-spec-broker-agnostic``; design #21 §0.1) and hardcodes **no** numeric ratio,
multiplier, timing, exposure, or aggregate-risk bound (ADR §25 line 493 leaves every
numeric bound an Open Question): every such value is an injected ``CanonicalDecimal``
parameter (design #21 §8). An enum member is a structural axis, never a limit; in
particular the split polarity algebra is the :class:`TransformationDirection` reciprocal
relation and **no split ratio (the "2" of a 2-for-1) appears anywhere**.

Pure module: stdlib only; no ``shared.*``, no sibling ``tos.*`` (design #21 §0.3).
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

__all__ = [
    # the 7 vocabulary enums (§2.2)
    "NonTradeEventClass",
    "NonTradeEventWorkflowState",
    "CredibleTransitionLegKind",
    "SplitTransformationKind",
    "TransformationDirection",
    "CorrectionReversalOutcome",
    "NonTradeDisposition",
    # structural universes + transcription tables
    "CREDIBLE_TRANSITION_LEG_MINIMUM_SET",
    "WORKFLOW_LINEAR_LIFECYCLE",
    "WORKFLOW_BRANCH_STATES",
    "ORTHOGONAL_EVENT_AXES",
    "RECIPROCAL_DIRECTION_PAIRS",
    "SPLIT_KIND_DIRECTIONS",
    "EVENT_IDENTITY_FIELD_GROUPS",
    "TRANSFORMATION_DISTINCTION_OWNERSHIP",
    "PROHIBITED_VERBS",
    # injected sibling-coordinate tokens (§3.4)
    "ORDER_ADMISSIBILITY_ADMISSIBLE",
    "ORDER_ADMISSIBILITY_RESTRICTED_PROTECTIVE_ONLY",
    "ORDER_ADMISSIBILITY_INADMISSIBLE",
    "ORDER_ADMISSIBILITY_UNKNOWN",
    "ORDINARY_NEW_RISK_ADMISSIBILITY_TOKENS",
    "FIELD_CONFIDENCE_CORROBORATED",
    "FIELD_CONFIDENCE_UNKNOWN",
    "FIELD_CONFIDENCE_CONFLICTED",
    "FRESHNESS_VERDICT_FRESH",
    "CAPACITY_STATE_TRAPPED_CONSUMED",
    "CAPACITY_STATE_QUARANTINED_UNKNOWN",
    "TRANSITION_CAUSE_RECOGNIZED_EXTERNAL_CHANGE",
    "ADVERSE_SCENARIO_EXTERNAL_TRAPPED_NONTRADE_CONCURRENT",
]


class _NonTruthyStrEnum(StrEnum):
    """A ``StrEnum`` that is deliberately **not truthy-testable** (design #21 §2.2-6).

    Every member is a non-empty string, so a bare ``if result:`` / ``bool(result)`` would
    read a denial member (``NONTRADE_TRAPPED`` / ``NONTRADE_BLOCK_NEW_RISK`` /
    ``REJECTED_CONFLICT`` ...) as truthy — a silent fail-open that reads "blocked" as
    "admitted". :meth:`__bool__` therefore raises ``TypeError`` on every member, so the
    misuse surfaces as a loud runtime error rather than a silent pass. Consumers MUST use
    the explicit positive-identity gate (``x is ENUM.SAFE_VALUE``). Isomorphic to the venue
    ``OrderAdmissibilityResult`` seal (``venue/vocabulary.py:56``) and the iap
    ``_NonTruthyStrEnum`` (``iap/vocabulary.py:50``); authored **locally-fresh** here
    (sibling edge 0 — design #21 §0.4b). ``is`` identity, ``.value``, hashing, set
    membership, and ``model_dump`` are all unaffected (none calls ``__bool__``).
    """

    def __bool__(self) -> bool:
        """Reject truthiness testing outright (truthy-sentinel seal, design #21 §2.2-6).

        Raises:
            TypeError: always — the enum is not truthy-testable. Use the explicit
                positive identity gate (e.g.
                ``disposition is NonTradeDisposition.NONTRADE_ADMISSIBLE``;
                ``outcome is CorrectionReversalOutcome.APPLIED_ONCE``); a bare
                ``if disposition:`` would fail open on the truthy denial strings.
        """
        raise TypeError(
            f"{type(self).__name__} is not truthy-testable — use an explicit positive "
            "identity gate (e.g. `disposition is NonTradeDisposition.NONTRADE_ADMISSIBLE`;"
            " `outcome is CorrectionReversalOutcome.APPLIED_ONCE`) per the truthy-sentinel"
            " seal (design #21 §2.2-6/§4). Every denial member is a non-empty string and a"
            " bare `if result:` would read a block / rejection as permission."
        )


class NonTradeEventClass(StrEnum):
    """The 5 non-trade event classes (ADR-002-010 §4 line 71-95 verbatim; count = 5).

    One member per ADR §4 subsection (§4.1-§4.5, a **closed** 5-way partition)::

        CORPORATE_ACTION        §4.1 line 73-75 — an issuer / exchange / clearing event
                                that transforms the instrument, entitlement, cash flow, or
                                holder obligation
        LIFECYCLE               §4.2 line 77-81 — expiry, exercise, assignment, delivery,
                                settlement, conversion, redemption, termination, rollover
                                (a strategy-initiated rollover *trade* is a trade, line 81)
        ADMINISTRATIVE_BROKER   §4.3 line 83-85 — transfer, journal, correction, bust
                                consequence, fee, tax, interest, collateral, margin, or
                                broker-applied adjustment
        INSTRUMENT_TRADABILITY  §4.4 line 87-89 — symbol, identifier, venue, contract-spec,
                                tick, lot, multiplier, currency, listing, delisting,
                                suspension, or session-eligibility change
        UNRECOGNIZED_EXTERNAL   §4.5 line 91-95 — not attributable with sufficient
                                confidence to a trade or a recognized event; line 95 makes
                                it ``QUARANTINED_UNKNOWN`` / ``TRAPPED_CONSUMED``
                                **capacity-consuming** (the rcl coordinate, injected)

    A class is a **structural axis, never a permission**: no member releases capacity or
    grants authority (§6 line 144; the all-false
    :class:`~tos.nontrade.records.NonTradeAuthorityEffect` is the type-level seal).
    ``UNRECOGNIZED_EXTERNAL`` in particular is the *most* conservative member — it consumes
    capacity — which is exactly why this enum is never truthy-tested.
    """

    CORPORATE_ACTION = "CORPORATE_ACTION"
    LIFECYCLE = "LIFECYCLE"
    ADMINISTRATIVE_BROKER = "ADMINISTRATIVE_BROKER"
    INSTRUMENT_TRADABILITY = "INSTRUMENT_TRADABILITY"
    UNRECOGNIZED_EXTERNAL = "UNRECOGNIZED_EXTERNAL"


class NonTradeEventWorkflowState(StrEnum):
    """The 8 + 3 non-trade workflow states (ADR §6 line 127-140; count = 11).

    §6 line 127-140 verbatim lifecycle::

        OBSERVED -> CORROBORATING -> VALIDATED -> TRANSITION_PREPARED -> EFFECT_PENDING
                 -> APPLIED_LOCAL -> RECONCILING -> RECONCILED
        Any state          ->  CONFLICTED
        Any state          ->  QUARANTINED_UNKNOWN
        Any applied state  ->  CORRECTION_PENDING

    §6 line 142 verbatim: "``APPLIED_LOCAL`` is not proof that the broker or venue applied
    the same effect." §6 line 143: "``RECONCILED`` requires evidence sufficient under
    ADR-002-006" (the recon coordinate, injected — never asserted here). §6 line 144
    verbatim: "**No workflow state by itself releases capacity, closes an instrument,
    proves final quantity, or grants authority.**" ⇒ a workflow state is a
    **non-authoritative coordinate**; the type-level seal is the all-false
    :class:`~tos.nontrade.records.NonTradeAuthorityEffect` (design #21 §4.4/§5.4).

    **Transition validity is NOT Phase-1 (design #21 §5.4).** Phase 1 authors the
    *vocabulary* + label-grants-nothing + the §6 line 123 orthogonality structure only.
    Whether ``VALIDATED -> TRANSITION_PREPARED`` may occur depends on the rcl capacity
    remap, the recon field confidence, the venue admissibility, and trustworthy time — all
    runtime gates (EV-L2/L3). There is deliberately **no** transition predicate in this
    package, and nothing here *sets* a state.

    **Orthogonality (§6 line 123).** This axis SHALL remain orthogonal to order, exposure,
    capacity, authority, and evidence-confidence state; :data:`ORTHOGONAL_EVENT_AXES` names
    the five axes that :class:`~tos.nontrade.records.NonTradeEventRecord` keeps as
    **separate injected fields**. ``QUARANTINED_UNKNOWN`` here is the *event* axis and is
    **not** rcl ``CapacityState.QUARANTINED_UNKNOWN`` (``vocabulary.py:29``).
    """

    # linear (8) — §6 line 127-134
    OBSERVED = "OBSERVED"
    CORROBORATING = "CORROBORATING"
    VALIDATED = "VALIDATED"
    TRANSITION_PREPARED = "TRANSITION_PREPARED"
    EFFECT_PENDING = "EFFECT_PENDING"
    APPLIED_LOCAL = "APPLIED_LOCAL"
    RECONCILING = "RECONCILING"
    RECONCILED = "RECONCILED"
    # branch (3) — §6 line 138-140
    CONFLICTED = "CONFLICTED"
    QUARANTINED_UNKNOWN = "QUARANTINED_UNKNOWN"
    CORRECTION_PENDING = "CORRECTION_PENDING"


class CredibleTransitionLegKind(StrEnum):
    """The 10 credible transition-envelope legs (ADR §9 line 185-194; count = 10).

    §9 line 181: the conservative transition envelope contains "all credible economic
    states during the event"; line 183: it "SHALL include **where applicable**" these legs
    — so the set is a **non-closed minimum set** (the recon ``SafetyRelevantField``
    precedent), never an exhaustive closure. The applicable subset is
    **event-class-parametric** and is injected by the caller into
    :func:`~tos.nontrade.predicates.transition_envelope_complete`; this package asserts no
    exhaustive-closure property over it (design #21 §2.2-3).

    Verbatim §9 phrases::

        PRE_EVENT_POSITION_AND_ORDER          line 185 "full pre-event position and order
                                              state"
        POST_EVENT_QUANTITY_INSTRUMENT_...    line 186 "every plausible post-event
                                              quantity, instrument, multiplier, currency,
                                              cash leg"
        OLD_AND_NEW_INSTRUMENT_BOTH           line 187 "both old and new instruments when
                                              identity transition is not final"
        FRACTIONAL_QUANTITY_AND_CASH_IN_LIEU  line 188 "fractional quantity and
                                              cash-in-lieu outcomes"
        EXERCISE_ASSIGNMENT_DELIVERY_...      line 189 "exercise, assignment, delivery,
                                              settlement, or conversion obligations"
        BROKER_OPEN_ORDER_CANCEL_ADJUST_...   line 190 "broker-side open-order
                                              cancellation, adjustment, duplication, or
                                              recreation"
        DELAYED_PARTIAL_REVERSED_CORRECTED... line 191 "delayed, partial, reversed, or
                                              corrected application"
        PRICE_MARGIN_SETTLEMENT_MARKET_...    line 192 "price, margin, settlement, and
                                              market-movement bounds"
        PROTECTIVE_ORDER_GAP_OVERLAP          line 193 "protective-order gaps and overlaps"
        SOURCE_DISAGREEMENT_AND_TIME_...      line 194 "source disagreement and time
                                              uncertainty"

    **Coordinate non-collapse (§2.2-5).** This is the *transition* axis. The aggregate-risk
    magnitudes over it are are-owned (ADR-002-021 ``worst_intermediate_risk``
    ``are/predicates.py:186``) and the dimension-wise union / hard-envelope enforcement is
    rcl-owned (``credible_union_capacity`` ``rcl/predicates.py:739``); ``tos.nontrade``
    judges **set completeness** and the structural
    :func:`~tos.nontrade.predicates.favorable_netting_absent` derivation only (design #21
    §0.4d). ``PROTECTIVE_ORDER_GAP_OVERLAP`` is a *transition leg*, **not** replacement
    ``CredibleIntermediateOutcomeKind`` (``replacement/vocabulary.py:158``).
    """

    PRE_EVENT_POSITION_AND_ORDER = "PRE_EVENT_POSITION_AND_ORDER"
    POST_EVENT_QUANTITY_INSTRUMENT_MULTIPLIER_CURRENCY_CASH = (
        "POST_EVENT_QUANTITY_INSTRUMENT_MULTIPLIER_CURRENCY_CASH"
    )
    OLD_AND_NEW_INSTRUMENT_BOTH = "OLD_AND_NEW_INSTRUMENT_BOTH"
    FRACTIONAL_QUANTITY_AND_CASH_IN_LIEU = "FRACTIONAL_QUANTITY_AND_CASH_IN_LIEU"
    EXERCISE_ASSIGNMENT_DELIVERY_SETTLEMENT_CONVERSION = (
        "EXERCISE_ASSIGNMENT_DELIVERY_SETTLEMENT_CONVERSION"
    )
    BROKER_OPEN_ORDER_CANCEL_ADJUST_DUPLICATE_RECREATE = (
        "BROKER_OPEN_ORDER_CANCEL_ADJUST_DUPLICATE_RECREATE"
    )
    DELAYED_PARTIAL_REVERSED_CORRECTED_APPLICATION = (
        "DELAYED_PARTIAL_REVERSED_CORRECTED_APPLICATION"
    )
    PRICE_MARGIN_SETTLEMENT_MARKET_MOVEMENT_BOUNDS = (
        "PRICE_MARGIN_SETTLEMENT_MARKET_MOVEMENT_BOUNDS"
    )
    PROTECTIVE_ORDER_GAP_OVERLAP = "PROTECTIVE_ORDER_GAP_OVERLAP"
    SOURCE_DISAGREEMENT_AND_TIME_UNCERTAINTY = (
        "SOURCE_DISAGREEMENT_AND_TIME_UNCERTAINTY"
    )


class SplitTransformationKind(StrEnum):
    """The 2 declared split kinds (ADR §11; count = 2; the NT-EV-001 L1 slice).

    ::

        FORWARD_SPLIT   quantity AMPLIFY  ·  price / cost basis ATTENUATE
        REVERSE_SPLIT   quantity ATTENUATE ·  price / cost basis AMPLIFY

    The two are **opposite-direction rules** and confusing them is a fail-open sign error
    (design #21 §4.5 — the #16 C1 direction-inversion lesson): modelling a forward split as
    (quantity ``ATTENUATE``, basis ``ATTENUATE``) *under*-estimates notional and loses
    risk. :data:`SPLIT_KIND_DIRECTIONS` is truth table B, and the declared kind is checked
    against the directions **derived** from the pre/post magnitudes (design #21 §2.2-4 M2)
    — a caller cannot forge the polarity with a flag because there is no polarity flag.

    A stock dividend is forward-like (§2 line 38 example, non-normative). The multi-leg
    merger / spin-off case (NT-EV-002) is **not** here: it is carried by the multi-leg
    :class:`~tos.nontrade.records.TransitionEnvelope` (§2.2-3).

    **No ratio is hardcoded.** The polarity algebra is the :class:`TransformationDirection`
    reciprocal relation over a three-way ``>`` / ``<`` / ``==`` comparison; the "2" of a
    2-for-1 appears nowhere in this package (design #21 §8.0).
    """

    FORWARD_SPLIT = "FORWARD_SPLIT"
    REVERSE_SPLIT = "REVERSE_SPLIT"


class TransformationDirection(StrEnum):
    """The 3 transformation directions (design #21 §2.2-4 polarity axis; count = 3).

    ::

        AMPLIFY    the post-event magnitude is greater than the pre-event magnitude
        ATTENUATE  the post-event magnitude is smaller than the pre-event magnitude
        IDENTITY   the two magnitudes are equal (a no-op transformation)

    A **nontrade-local** axis: the ADR states the polarity rule in prose, and this enum is
    the algebra that checks it (design #21 §4.5 truth table A). A direction is **derived**,
    never declared: :func:`~tos.nontrade.predicates.split_polarity_coherent` computes it
    from ``pre_quantity`` / ``post_quantity`` and ``pre_basis`` / ``post_basis`` by a
    multiplicative-identity comparison (design #21 §2.2-4 M2), so a mis-declared direction
    cannot pass the truth table — there is no ``direction`` field to mis-declare.

    :data:`RECIPROCAL_DIRECTION_PAIRS` is truth table A's three coherent cells; the other
    six of the 3x3 are sign errors or asymmetries and are rejected in **both** directions
    (an over-estimate is as much a mis-specification as an under-estimate).
    """

    AMPLIFY = "AMPLIFY"
    ATTENUATE = "ATTENUATE"
    IDENTITY = "IDENTITY"


class CorrectionReversalOutcome(_NonTruthyStrEnum):
    """The 6 correction / reversal outcomes (design #21 §2.2-5; count = 6).

    ::

        APPLIED_ONCE          lineage present + original retained + ``prior is None``
                              (the first correction — the classify **pre-gate**, §5.3):
                              economic effect count -> 1
        IDEMPOTENT_REPLAY     ``RecordPairKind.IDEMPOTENT_DUP`` (same primary *or*
                              idempotency id, same canonical bytes): a harmless re-apply,
                              effect count unchanged
        REJECTED_CONFLICT     **both** forgery axes fold here — ``CRITICAL_CONFLICT``
                              (same **primary** id, different bytes: record forgery) and
                              ``DIVERGENT_EMISSION`` (same **idempotency** id, different
                              bytes: two different corrections claiming one key). Contain
                              both, no last-write-wins merge, never a silent double-apply
        REJECTED_NO_LINEAGE   no ``supersedes_ref`` — ADR §16 line 311 forbids relabelling
                              "an unexplained position change as a correction merely to
                              make reconciliation pass"
        REJECTED_OVERWRITE    the original was not retained — ADR §10 line 219 "History
                              SHALL be corrected by new versioned facts, not destructive
                              overwrite"
        REJECTED_UNKNOWN      ``DISTINCT`` (the prior shares neither identity axis — a
                              caller contract violation) or ``NOT_COMPARABLE`` (a
                              pre-issuance null digest): undecidable ⇒ fail closed

    **Only ``APPLIED_ONCE`` increases the economic effect count**, and it is reached only
    through the positive pre-gate conjunction — never as a dispatch residue (design #21
    §4.6; the #16 CRITICAL "a GRANT must not be the fall-through residue" lesson).

    **Coordinate non-collapse (§2.2-5 / §0.4e).** :attr:`IDEMPOTENT_REPLAY` is the
    *economic-event-application* axis. It is a **different type and a different
    proposition** from iap ``ConsumptionOutcome.IDEMPOTENT_REPLAY``
    (``iap/vocabulary.py:165``, authorization-token single-use consumption) and rcl
    ``ApplyReason.IDEMPOTENT_REPLAY`` (capacity-command). All three are independent
    downstreams of canonical ``classify_record_pair``; ``tos.nontrade`` imports neither
    sibling (phantom edge blocked, design #21 §0.4e).

    **Truthy-sentinel seal.** Every member is a non-empty string, so ``if outcome:`` would
    read ``REJECTED_CONFLICT`` as truthy. Truthy-untestable (``__bool__`` raises); the
    mandated consume gate is ``outcome is CorrectionReversalOutcome.APPLIED_ONCE`` (or
    ``is IDEMPOTENT_REPLAY``).
    """

    APPLIED_ONCE = "APPLIED_ONCE"
    IDEMPOTENT_REPLAY = "IDEMPOTENT_REPLAY"
    REJECTED_CONFLICT = "REJECTED_CONFLICT"
    REJECTED_NO_LINEAGE = "REJECTED_NO_LINEAGE"
    REJECTED_OVERWRITE = "REJECTED_OVERWRITE"
    REJECTED_UNKNOWN = "REJECTED_UNKNOWN"


class NonTradeDisposition(_NonTruthyStrEnum):
    """The 5 non-trade dispositions (design #21 §2.2-6; count = 5).

    ::

        NONTRADE_ADMISSIBLE          every credible leg complete, polarity coherent,
                                     units / rounding explicit, residual conservative,
                                     evidence corroborated, and the venue decision is
                                     positively ``ADMISSIBLE`` — reached **only** by the
                                     §5.5 positive conjunction, never by fall-through
        NONTRADE_BLOCK_NEW_RISK      §1 line 26 "UNKNOWN consumes capacity and blocks new
                                     risk"; also the ``RESTRICTED_PROTECTIVE_ONLY`` landing
                                     (ordinary new risk barred, a separately authorized
                                     protective action may still proceed through the
                                     venue-owned ``protective_label_no_bypass``)
        NONTRADE_QUARANTINED_UNKNOWN §4.5 line 95 / §18 line 344 — unattributable or
                                     undecidable, capacity-consuming, never "no risk"
        NONTRADE_TRAPPED             §12 line 252 "inability to exit SHALL be represented
                                     as trapped exposure ... not zero risk"
        NONTRADE_CONFLICTED          §18 line 344 — contradicted evidence or a contained
                                     record-pair conflict

    :func:`~tos.nontrade.predicates.nontrade_disposition` is the **sole producer** (design
    #21 §5.5 C1): every row of the §4.7 void table folds through it, so there is no
    ownerless "handled elsewhere" path. Its five ranks are a **total order** —
    ``CONFLICTED`` > ``QUARANTINED_UNKNOWN`` > ``TRAPPED`` > ``BLOCK_NEW_RISK`` >
    ``ADMISSIBLE`` — so a simultaneous conflict / trap / incompleteness always returns the
    **most conservative** member.

    **A disposition grants nothing** (§6 line 144 / §4.4): even ``NONTRADE_ADMISSIBLE``
    releases no capacity, transmits nothing, and issues no admissibility — the consuming
    runtime (rcl remap-admission, venue invalidation, final egress) enforces.

    **Truthy-sentinel seal.** All five members are non-empty strings, so ``if disposition:``
    would read ``NONTRADE_TRAPPED`` as permission. Truthy-untestable (``__bool__`` raises);
    the mandated consume gate is
    ``disposition is NonTradeDisposition.NONTRADE_ADMISSIBLE``.
    """

    NONTRADE_ADMISSIBLE = "NONTRADE_ADMISSIBLE"
    NONTRADE_BLOCK_NEW_RISK = "NONTRADE_BLOCK_NEW_RISK"
    NONTRADE_QUARANTINED_UNKNOWN = "NONTRADE_QUARANTINED_UNKNOWN"
    NONTRADE_TRAPPED = "NONTRADE_TRAPPED"
    NONTRADE_CONFLICTED = "NONTRADE_CONFLICTED"


# ---------------------------------------------------------------------------
# Structural universes + transcription tables
# ---------------------------------------------------------------------------

#: The §9 line 183 "where applicable" **non-closed minimum** leg universe. It is a
#: *convenience* universe for callers and tests, **not** a required set: the required
#: subset is event-class-parametric and is injected into
#: :func:`~tos.nontrade.predicates.transition_envelope_complete`, which fails closed on an
#: **empty** required set (design #21 §5.1 C1) rather than defaulting to this one.
CREDIBLE_TRANSITION_LEG_MINIMUM_SET: frozenset[CredibleTransitionLegKind] = frozenset(
    CredibleTransitionLegKind
)

#: The §6 line 127-134 linear lifecycle (8 states) in ADR declaration order. A
#: **structural transcription**, never a transition table: transition validity is not
#: Phase-1 (design #21 §5.4).
WORKFLOW_LINEAR_LIFECYCLE: tuple[NonTradeEventWorkflowState, ...] = (
    NonTradeEventWorkflowState.OBSERVED,
    NonTradeEventWorkflowState.CORROBORATING,
    NonTradeEventWorkflowState.VALIDATED,
    NonTradeEventWorkflowState.TRANSITION_PREPARED,
    NonTradeEventWorkflowState.EFFECT_PENDING,
    NonTradeEventWorkflowState.APPLIED_LOCAL,
    NonTradeEventWorkflowState.RECONCILING,
    NonTradeEventWorkflowState.RECONCILED,
)

#: The 3 non-linear §6 line 138-140 states ("Any state" / "Any applied state").
WORKFLOW_BRANCH_STATES: tuple[NonTradeEventWorkflowState, ...] = (
    NonTradeEventWorkflowState.CONFLICTED,
    NonTradeEventWorkflowState.QUARANTINED_UNKNOWN,
    NonTradeEventWorkflowState.CORRECTION_PENDING,
)

#: The 5 axes ADR §6 line 123 requires the non-trade event state to stay **orthogonal**
#: to: "Non-trade event state SHALL remain orthogonal to order, exposure, capacity,
#: authority, and evidence-confidence state."
#: :class:`~tos.nontrade.records.NonTradeEventRecord` keeps one **separate injected field**
#: per axis (each carrying a sibling-owned token this package consumes and never sets), and
#: a §7 property asserts the field set is complete and disjoint from ``workflow_state``.
ORTHOGONAL_EVENT_AXES: tuple[str, ...] = (
    "order_state",
    "exposure_state",
    "capacity_state",
    "authority_state",
    "evidence_confidence_state",
)

#: Truth table A (design #21 §4.5): the **3** coherent ``(quantity, basis)`` direction
#: cells out of the 3x3 = 9. The other 6 are sign errors (both-amplify / both-attenuate) or
#: asymmetries (one axis moves, the other does not) and are rejected in **both**
#: directions — an over-estimate is as much a mis-specification as an under-estimate.
RECIPROCAL_DIRECTION_PAIRS: frozenset[
    tuple[TransformationDirection, TransformationDirection]
] = frozenset(
    {
        (TransformationDirection.AMPLIFY, TransformationDirection.ATTENUATE),
        (TransformationDirection.ATTENUATE, TransformationDirection.AMPLIFY),
        (TransformationDirection.IDENTITY, TransformationDirection.IDENTITY),
    }
)

#: Truth table B (design #21 §4.5): the ``(quantity, basis)`` directions each **declared**
#: :class:`SplitTransformationKind` requires. The declared kind is compared against the
#: directions **derived** from the pre/post magnitudes, so a ``REVERSE_SPLIT`` declared
#: over forward magnitudes is rejected (the M2 forgery canary). The identity no-op has no
#: declared kind and is handled by the ``kind is None`` row of
#: :func:`~tos.nontrade.predicates.split_polarity_coherent`.
SPLIT_KIND_DIRECTIONS: Mapping[
    SplitTransformationKind, tuple[TransformationDirection, TransformationDirection]
] = {
    SplitTransformationKind.FORWARD_SPLIT: (
        TransformationDirection.AMPLIFY,
        TransformationDirection.ATTENUATE,
    ),
    SplitTransformationKind.REVERSE_SPLIT: (
        TransformationDirection.ATTENUATE,
        TransformationDirection.AMPLIFY,
    ),
}

#: ADR §5 line 103-115 — the **13** identity items every non-trade event must carry
#: ("Every event SHALL have a durable Non-Trade Event ID and contain **at least**:", line
#: 101 ⇒ a **non-closed minimum set**). Each entry is ``(adr_line, realizing field names)``
#: on :class:`~tos.nontrade.records.NonTradeEventRecord`. **Transcription only — this is
#: not a producer** (design #21 §2.2-8): item 10 (per-field evidence confidence) is
#: recon-owned and item 11's profile versions are spg / brokercap / VP-002 injected. It
#: exists so the ADR item count stays cross-checkable and so a reader can see what each
#: producer owes.
#:
#: The ADR line is carried as a **string anchor, never a number**: it is a citation
#: coordinate, not a quantity, and keeping it non-numeric leaves the §8.0 "no numeric
#: literal other than the structural 0 / 1" source scan at full strength (a scanner that
#: had to whitelist citation numbers could be talked into whitelisting a policy bound).
EVENT_IDENTITY_FIELD_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    # 1 — event class and subtype
    ("103", ("event_class", "event_subtype")),
    # 2 — issuer / venue / broker / clearing / administrative source identities
    ("104", ("source_identities",)),
    # 3 — source event identifiers and versions (the PRIMARY identity axis is the
    #     independent ``event_id``; CRITICAL_CONFLICT target, §4.6)
    ("105", ("source_event_ids", "source_event_versions")),
    # 4 — announcement / observation / record / ex / effective / payable / settlement
    #     times, kept SEPARATE (§8 line 171 forbids collapsing them into one date)
    (
        "106",
        (
            "announcement_time",
            "observation_time",
            "record_time",
            "ex_time",
            "effective_time",
            "payable_time",
            "settlement_time",
        ),
    ),
    # 5 — affected account / portfolio / instrument / currency / broker scopes
    (
        "107",
        (
            "affected_account_scopes",
            "affected_portfolio_scopes",
            "affected_instrument_scopes",
            "affected_currency_scopes",
            "affected_broker_scopes",
        ),
    ),
    # 6 — old and new instrument identities (both retained, §12 line 248/250)
    ("108", ("old_instrument_identity", "new_instrument_identity")),
    # 7 — transformation legs / ratios / multipliers / prices / cash values / rounding
    ("109", ("transformation_spec", "transition_envelope")),
    # 8 — eligibility and election conditions (values only; transmitting is §15 line 299)
    ("110", ("eligibility_conditions", "election_conditions")),
    # 9 — broker-treatment profile and expected open-order behaviour (brokercap injected)
    ("111", ("broker_treatment_profile", "expected_open_order_behavior")),
    # 10 — evidence confidence and contradiction status PER FIELD (recon-owned, injected)
    ("112", ("per_field_confidence",)),
    # 11 — Safety / Broker-Capability / Verification profile, calendar, instrument-master
    (
        "113",
        (
            "safety_profile_version",
            "broker_capability_profile_version",
            "verification_profile_version",
            "calendar_version",
            "instrument_master_version",
        ),
    ),
    # 12 — workflow generation and idempotency key (the IDEMPOTENCY identity axis;
    #      DIVERGENT_EMISSION target, §4.6)
    ("114", ("workflow_generation", "idempotency_key")),
    # 13 — supersession / correction / reversal / lineage references
    ("115", ("supersedes_ref", "lineage_refs")),
)

#: ADR §11 line 231-236 — the **6** distinctions every transformation must keep, with the
#: Phase-1 ownership attribution (design #21 §2.2-7; **no unowned distinction**). Each
#: entry is ``(adr_line, distinction, owner)`` where ``owner`` is ``"nontrade"``,
#: ``"nontrade-partial"``, or the owning sibling package. Transcription only. The ADR line
#: is a **string anchor, never a number** (see
#: :data:`EVENT_IDENTITY_FIELD_GROUPS`) so the §8.0 numeric-literal scan stays absolute.
TRANSFORMATION_DISTINCTION_OWNERSHIP: tuple[tuple[str, str, str], ...] = (
    ("231", "position quantity vs executable order quantity", "nontrade"),
    ("232", "raw ratio vs broker-applied rounded quantity", "nontrade"),
    ("233", "fractional entitlement vs tradable whole quantity", "nontrade"),
    (
        "234",
        "reference price vs cost basis / settlement / trigger / limit price",
        "nontrade-partial",
    ),
    ("235", "instrument multiplier vs contract quantity", "venue"),
    ("236", "trade currency vs settlement / collateral / reporting currency", "venue"),
)

#: The **19** prohibited verbs swept from ADR §1-§22 (design #21 §4.7). Each is realized
#: either by a fail-closed predicate branch or — more strongly — by the **structural
#: absence** of any field or predicate that could express it (``release-on-transformation``
#: and ``update-capacity-independently`` are unconstructable, not merely rejected).
#: Transcription only; a §7 property asserts the count.
PROHIBITED_VERBS: tuple[str, ...] = (
    "fabricate-fill",  # §1 line 15 · §22.1
    "fold-into-correction",  # §1 line 15
    "net-favorable-against-adverse",  # §9 line 196 · §22.6
    "assume-equivalence-from-ratio",  # §11 line 238 · §22.5
    "same-direction-split-multiplier",  # §4.5 sign error
    "omit-units-or-rounding",  # §11 line 227
    "release-on-transformation",  # §10 line 221 · §1 line 28
    "relabel-unexplained-as-correction",  # §16 line 311
    "destructive-overwrite-history",  # §10 line 219
    "double-apply-correction",  # §4.6
    "update-capacity-independently",  # §10 line 217
    "treat-reference-data-as-mutation",  # §22.2
    "assume-broker-adjusts-correctly",  # §22.3
    "treat-expired-as-zero-risk",  # §12 line 252 · §22.4
    "silently-reassign-instrument",  # §12 line 250
    "skip-invalidation-on-material-change",  # §10 line 221
    "auto-re-arm-on-completion",  # §17 line 334 · §22.7
    "remove-UNKNOWN-by-operator-label",  # §18 line 351
    "collapse-effective-times",  # §8 line 171
)


# ---------------------------------------------------------------------------
# Injected sibling-coordinate tokens (design #21 §3.4 — token, never type)
# ---------------------------------------------------------------------------
# ``tos.nontrade`` holds sibling edge 0, so a verdict arriving from a sibling crosses the
# seam as a bare token. Each constant below is the *token* of a real sibling member; a §7
# seam test imports the sibling **in the test only** and asserts the token still equals the
# live member (drift lock — the afg / replacement ``ADMISSIBILITY_ADMISSIBLE`` precedent).
# A token is compared with ``==`` (a ``StrEnum`` member equals its value); ``is`` identity
# is reserved for this package's **own** enums, and ``bool(token)`` is never used — the
# real venue producer's ``__bool__`` raises, and even a bare string would be truthy.

#: venue ``OrderAdmissibilityResult.ADMISSIBLE`` (``venue/vocabulary.py:114``). The **only**
#: token that satisfies the ordinary new-risk conjunct (ADR-002-019 §1 line 23: ADMISSIBLE
#: means only that the exact shape passed the declared checks — nothing more).
ORDER_ADMISSIBILITY_ADMISSIBLE = "ADMISSIBLE"

#: venue ``OrderAdmissibilityResult.RESTRICTED_PROTECTIVE_ONLY`` (``vocabulary.py:115``).
#: Permits **no ordinary new risk** (ADR-002-019 §1 line 29 / §19 line 426), so it fails
#: the ordinary conjunct — but it is **not** trapped: a separately authorized protective
#: action may still proceed through the **venue-owned**
#: ``protective_label_no_bypass`` (``venue/predicates.py:599``), whose produced ``bool``
#: this package consumes as ``protective_action_may_proceed`` and never re-decides
#: (design #21 §3.4 M6 / §5.5).
ORDER_ADMISSIBILITY_RESTRICTED_PROTECTIVE_ONLY = "RESTRICTED_PROTECTIVE_ONLY"

#: venue ``OrderAdmissibilityResult.INADMISSIBLE`` (``vocabulary.py:116``) — denial ⇒ no
#: fresh exact decision ⇒ the exposure is **trapped**, not zero-risk (§12 line 252).
ORDER_ADMISSIBILITY_INADMISSIBLE = "INADMISSIBLE"

#: venue ``OrderAdmissibilityResult.UNKNOWN`` (``vocabulary.py:117``) — likewise trapped.
ORDER_ADMISSIBILITY_UNKNOWN = "UNKNOWN"

#: The **two** admissibility tokens that are not trapped (design #21 §5.5 rank 3 / §6.1
#: M6 three-way fold). Anything else — ``INADMISSIBLE``, ``UNKNOWN``, ``None``, **or an
#: unrecognized / forged token** — is trapped, unconditionally.
ORDINARY_NEW_RISK_ADMISSIBILITY_TOKENS: tuple[str, ...] = (
    ORDER_ADMISSIBILITY_ADMISSIBLE,
    ORDER_ADMISSIBILITY_RESTRICTED_PROTECTIVE_ONLY,
)

#: recon ``FieldConfidenceClass.CORROBORATED`` (``recon/vocabulary.py``) — the only
#: per-field grade that satisfies the §5.5 positive conjunction. ``SINGLE_SOURCE`` and
#: ``STALE`` are non-empty (truthy) strings and are **not** corroboration (§7 line 159
#: common-mode is not corroboration; §7 line 161 majority vote resolves nothing).
FIELD_CONFIDENCE_CORROBORATED = "CORROBORATED"

#: recon ``FieldConfidenceClass.UNKNOWN`` — 0 usable evidence paths ⇒ quarantine.
FIELD_CONFIDENCE_UNKNOWN = "UNKNOWN"

#: recon ``FieldConfidenceClass.CONFLICTED`` — independent paths disagree ⇒ conflicted.
FIELD_CONFIDENCE_CONFLICTED = "CONFLICTED"

#: time ``FreshnessVerdict.FRESH`` (``time/domains.py:66``) — the only verdict that
#: establishes an effective-time window; ``STALE`` / ``UNKNOWN`` / ``CONFLICTED`` are all
#: fail-closed (§8 line 173).
FRESHNESS_VERDICT_FRESH = "FRESH"

#: rcl ``CapacityState.TRAPPED_CONSUMED`` (``rcl/vocabulary.py:30``) — the *capacity* axis
#: counterpart of :attr:`NonTradeDisposition.NONTRADE_TRAPPED`. Different types (§2.2-5).
CAPACITY_STATE_TRAPPED_CONSUMED = "TRAPPED_CONSUMED"

#: rcl ``CapacityState.QUARANTINED_UNKNOWN`` (``rcl/vocabulary.py:29``) — the *capacity*
#: axis counterpart of :attr:`NonTradeEventWorkflowState.QUARANTINED_UNKNOWN`.
CAPACITY_STATE_QUARANTINED_UNKNOWN = "QUARANTINED_UNKNOWN"

#: rcl ``TransitionCause.RECOGNIZED_EXTERNAL_CHANGE`` (``rcl/vocabulary.py:92``) — the
#: capacity-transition **cause** a recognized non-trade change proposes. ADR §10 line 217:
#: the event processor "may propose a remap but SHALL NOT update capacity independently",
#: so this package emits the cause token and rcl performs the transition.
TRANSITION_CAUSE_RECOGNIZED_EXTERNAL_CHANGE = "RECOGNIZED_EXTERNAL_CHANGE"

#: are ``AdverseScenarioKind.EXTERNAL_TRAPPED_NONTRADE_CONCURRENT``
#: (``are/vocabulary.py:115``) — are already owns the concurrent non-trade trapped scenario
#: on the **aggregate-risk** axis, which is precisely why this package projects no risk
#: (design #21 §0.4c/§0.4d).
ADVERSE_SCENARIO_EXTERNAL_TRAPPED_NONTRADE_CONCURRENT = (
    "EXTERNAL_TRAPPED_NONTRADE_CONCURRENT"
)
