"""Protective-Replacement vocabulary — the replacement-axis StrEnums (design #18 §2.2).

Spec terms = code terms (design #18 §2; boundary design #1 §2.4). The five enums are
authored **verbatim** from ADR-002-011 (§6 replacement modes, §5 workflow lifecycle, §9
credible intermediate outcomes, §12 re-evaluation targets) plus the local
:class:`ReplacementOutcome` result. Item counts are transcribed against the ADR line
ranges and are re-asserted by a §7 property test (the #16 M4 truncated-transcription
lesson): §6 = 4 modes, §5 line 124-135 = 7 + 2 workflow states, §9 line 234-243 = **9**
credible intermediate outcomes, §12 line 292-298 = **6** re-evaluation targets.

**Coordinate non-collapse (design #18 §2.2-5 — this module is the canonical home of the
rule).** These are the **replacement-workflow / replacement-intermediate** axes. They
are distinct coordinate systems from:

* protective ``ProtectiveActionKind`` (``vocabulary.py:180``) — the *partition-time
  lease-admissibility* axis. Its ``OVERLAP_FIRST_ADD_ONLY`` / ``CANCEL_FIRST_OR_REMOVAL``
  tokens overlap ours in wording, never in type;
* protective ``Admissibility`` (``vocabulary.py:118``) — the lease/cancellation verdict
  axis (its ``TRAPPED`` is **not** our ``REPLACEMENT_TRAPPED``);
* rcl ``CapacityState`` (``vocabulary.py:15``, ``TRAPPED_CONSUMED`` ``:30``) and
  ``CapacityVector.dimension_id`` (``vector.py:74``) — the economic capacity axis;
* are ``RiskDimensionKind`` — the aggregate-risk axis;
* orthostate ``BrokerOrderState`` / ``TransmissionAttemptState``
  (``vocabulary.py:92`` / ``:61``) — the order / attempt axes.

Token overlap is intentional (the ADR uses the same words on several axes), so
coordinate non-collapse rests on **distinct types + non-import**: ``tos.replacement``
imports **none** of those siblings (sibling edge 0, design #18 §0.4b/§0.4c), so a value
from one axis can never be coerced onto another. Where a sibling token must nonetheless
be *recognized* (an injected verdict crosses the seam as a bare string / StrEnum member),
this module fixes the token as a **local constant** and a §7 seam test locks it against
the real sibling member (the afg ``ADMISSIBILITY_ADMISSIBLE`` precedent).

This module names **no** concrete broker (broker-agnostic — project memory
``tos-spec-broker-agnostic``; design #18 §0.1) and hardcodes **no** numeric gap,
overlap, timing, exposure, or aggregate-risk bound (ADR §15 line 353 "Numeric values
remain unapproved until human approval and executed evidence are recorded"): every such
value is an injected ``CanonicalDecimal`` parameter (design #18 §8). An enum member is a
structural axis, never a limit.

Pure module: stdlib only; no ``shared.*``, no sibling ``tos.*`` (design #18 §0.3).
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "ReplacementMode",
    "ReplacementWorkflowState",
    "CredibleIntermediateOutcomeKind",
    "ReevaluationTargetKind",
    "ReplacementOutcome",
    "REQUIRED_CREDIBLE_INTERMEDIATE_OUTCOMES",
    "REQUIRED_REEVALUATION_TARGETS",
    "NO_NETTING_MAGNITUDE_KINDS",
    "CANCEL_FIRST_ADMISSION_CONDITIONS",
    "PROTECTION_SUFFICIENCY_FIELDS",
    "WORKFLOW_LIFECYCLE_ORDER",
    "WORKFLOW_NON_LINEAR_STATES",
    "ORTHOGONAL_WORKFLOW_AXES",
    "ADMISSIBILITY_ADMISSIBLE",
    "ORDER_ADMISSIBILITY_ADMISSIBLE",
    "PROTECTIVE_ACTION_KIND_OVERLAP_FIRST_ADD_ONLY",
    "PROTECTIVE_ACTION_KIND_CANCEL_FIRST_OR_REMOVAL",
    "BROKER_ORDER_STATE_CANCELLED",
    "BROKER_ORDER_STATE_UNKNOWN",
    "ATTEMPT_STATE_SENT_UNCONFIRMED",
    "REPLACE_SEMANTICS_ATOMIC_REPLACE",
    "protective_action_kind_token",
]


class ReplacementMode(StrEnum):
    """The 4 replacement modes (ADR-002-011 §6 line 143-181 verbatim; count = 4).

    ::

        BROKER_PROVEN_ATOMIC   §6.1 line 145 — only when the active Broker Capability
                               Profile proves the exact semantics by executed evidence
        OVERLAP_FIRST          §6.2 line 153 — new protection established before the old
                               is removed (preferred)
        CANCEL_FIRST           §6.3 line 161 — old protection removed before the new is
                               established; creates a Protection Gap; 8-condition gate
        NO_SAFE_MODE           §6.4 line 178 — all three are unsafe: replacement is
                               unavailable, retain the safest protection and contain

    **Direction polarity (design #18 §4.5 truth table — the #16 C1 direction-inversion
    lesson).** ``OVERLAP_FIRST`` is *new -> old* (no Protection Gap, Protection Overlap
    risk) and ``CANCEL_FIRST`` is *old -> new* (Protection Gap risk, no overlap): they
    are **opposite-direction rules** and confusing them is a fail-open defect. The
    per-mode premises are therefore checked as **separate positive conjunctions** in
    :func:`~tos.replacement.predicates.replacement_mode_admissible`; a mode is never
    promoted by fall-through.

    **Coordinate non-collapse (§2.2-5).** This is the *general replacement-workflow mode*
    axis. protective ``ProtectiveActionKind.{OVERLAP_FIRST_ADD_ONLY,
    CANCEL_FIRST_OR_REMOVAL}`` (``vocabulary.py:180``) is the *partition-time
    lease-admissibility* axis — a different type with overlapping wording.
    :func:`protective_action_kind_token` maps ours onto that axis's **token** (never onto
    its type) so a partition verdict can be requested without importing the sibling.

    **Truthy-sentinel seal (§2.2 / §0.1(j)).** Every ``StrEnum`` member — including
    ``NO_SAFE_MODE`` — is *truthy*, so a consuming gate SHALL test
    ``mode is ReplacementMode.OVERLAP_FIRST`` (identity); a bare ``if mode:`` would let
    ``NO_SAFE_MODE`` through.
    """

    BROKER_PROVEN_ATOMIC = "BROKER_PROVEN_ATOMIC"
    OVERLAP_FIRST = "OVERLAP_FIRST"
    CANCEL_FIRST = "CANCEL_FIRST"
    NO_SAFE_MODE = "NO_SAFE_MODE"


class ReplacementWorkflowState(StrEnum):
    """The 7 + 2 replacement workflow states (ADR-002-011 §5 line 124-135; count = 9).

    §5 line 124-135 verbatim lifecycle::

        PLANNED  ->  CAPACITY_COMMITTED  ->  FIRST_LEG_SENT  ->  INTERMEDIATE_STATE
                 ->  NEW_PROTECTION_PROVEN  ->  OLD_FINALITY_PENDING  ->  COMPLETED
        Any state            ->  FAILED_CONTAINED
        Any uncertain state  ->  RECOVERY_REQUIRED

    §5 line 137 verbatim: "**No lifecycle label by itself authorizes capacity release or
    removal of protection.**" §5 line 139: "No lifecycle label or 'protective'
    classification proves that cancel, amend, replace, reduce-only, or new protection is
    executable." ⇒ a workflow state is a **non-authoritative coordinate**; the
    type-level seal is the all-false
    :class:`~tos.replacement.records.ReplacementAuthorityEffect` (design #18 §4.4/§5.3).

    **Transition validity is NOT Phase-1 (design #18 §5.3, Open Q3).** Phase 1 authors
    the *vocabulary* + label-grants-nothing + the §5 line 107 no-collapse structure only.
    Whether ``CAPACITY_COMMITTED -> FIRST_LEG_SENT`` may occur depends on the rcl
    capacity commit, the orthostate attempt state, and per-leg ADR-002-019
    admissibility — all runtime gates (EV-L3) — exactly as orthostate owns
    ``attempt_transition_allowed``. There is deliberately **no** transition predicate in
    this package, and nothing here *sets* a state.

    **Orthogonality (§5 line 107).** This workflow axis SHALL NOT collapse order state,
    transmission state, knowledge confidence, capacity state, and protection state into
    one enum; :data:`ORTHOGONAL_WORKFLOW_AXES` names the five axes that
    :class:`~tos.replacement.records.ReplacementWorkflowRecord` keeps as **separate
    fields**.
    """

    PLANNED = "PLANNED"
    CAPACITY_COMMITTED = "CAPACITY_COMMITTED"
    FIRST_LEG_SENT = "FIRST_LEG_SENT"
    INTERMEDIATE_STATE = "INTERMEDIATE_STATE"
    NEW_PROTECTION_PROVEN = "NEW_PROTECTION_PROVEN"
    OLD_FINALITY_PENDING = "OLD_FINALITY_PENDING"
    COMPLETED = "COMPLETED"
    FAILED_CONTAINED = "FAILED_CONTAINED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


class CredibleIntermediateOutcomeKind(StrEnum):
    """The 9 credible intermediate outcomes (ADR-002-011 §9 line 234-243; count = 9).

    §9 line 233 verbatim: the reservation "SHALL include **at least**" these outcomes —
    so the set is the **mode-independent common minimum** (design #18 §4.5 M2), never a
    per-mode subset. §9 line 231: "the Risk Capacity Ledger SHALL atomically commit
    capacity for the maximum aggregate risk over all credible intermediate outcomes";
    "an outcome not bounded by these is treated conservatively as UNKNOWN".

    Verbatim §9 phrases::

        CURRENT_EXPOSURE_UNPROTECTED         "current exposure without sufficient protection"
        OLD_ORDER_REMAINING_EXECUTABLE       "old-order remaining executable quantity"
        NEW_ORDER_REMAINING_EXECUTABLE       "new-order remaining executable quantity"
        SIMULTANEOUS_OLD_AND_NEW_FILLS       "simultaneous old and new fills"
        PARTIAL_FILLS_EVERY_ORDERING         "partial fills in every relevant ordering"
        OVER_CLOSE_AND_REVERSAL              "over-close and reversal exposure"
        TEMPORARY_LOSS_OF_PROTECTION         "temporary loss of trigger, price, or venue
                                              protection"
        COMMISSION_MARGIN_MARKET_BOUNDS      "commissions, margin, multiplier, currency,
                                              and market-movement bounds"
        BROKER_SCARCITY_PREVENTS_PROTECTION  "broker order-count, cancel, and rate-limit
                                              scarcity where it can prevent protection"

    **Coordinate non-collapse (§2.2-5).** This is the *replacement-intermediate* axis.
    The aggregate-risk magnitudes over it are are-owned (ADR-002-021) and the
    dimension-wise summation / hard-envelope enforcement is rcl-owned (ADR-002-002);
    ``tos.replacement`` judges **set completeness** and the structural
    :func:`~tos.replacement.predicates.netting_absent` derivation only (design #18
    §0.4d).
    """

    CURRENT_EXPOSURE_UNPROTECTED = "CURRENT_EXPOSURE_UNPROTECTED"
    OLD_ORDER_REMAINING_EXECUTABLE = "OLD_ORDER_REMAINING_EXECUTABLE"
    NEW_ORDER_REMAINING_EXECUTABLE = "NEW_ORDER_REMAINING_EXECUTABLE"
    SIMULTANEOUS_OLD_AND_NEW_FILLS = "SIMULTANEOUS_OLD_AND_NEW_FILLS"
    PARTIAL_FILLS_EVERY_ORDERING = "PARTIAL_FILLS_EVERY_ORDERING"
    OVER_CLOSE_AND_REVERSAL = "OVER_CLOSE_AND_REVERSAL"
    TEMPORARY_LOSS_OF_PROTECTION = "TEMPORARY_LOSS_OF_PROTECTION"
    COMMISSION_MARGIN_MARKET_BOUNDS = "COMMISSION_MARGIN_MARKET_BOUNDS"
    BROKER_SCARCITY_PREVENTS_PROTECTION = "BROKER_SCARCITY_PREVENTS_PROTECTION"


class ReevaluationTargetKind(StrEnum):
    """The 6 partial-fill re-evaluation targets (ADR §12 line 292-298; count = 6).

    §12 line 291 verbatim: "Every fill or recognized exposure change invalidates stale
    quantity calculations and triggers **atomic** re-evaluation of" — all six, never a
    subset. Verbatim §12 phrases::

        REMAINING_PROTECTIVE_OBLIGATION   "the remaining protective obligation"
        OLD_AND_NEW_EXECUTABLE_QUANTITIES "old and new executable quantities"
        OVERLAP_AND_GAP_RISK              "overlap and gap risk"
        CAPACITY_COMMITMENTS              "capacity commitments"
        CANCELLATION_AUTHORIZATION        "cancellation authorization"
        PENDING_TRANSMISSION_CONFORMANCE  "whether any pending transmission remains
                                           conformant"

    A missing target leaves a **stale quantity calculation** in place, so an incomplete
    re-evaluation set is ``False`` — never a soft pass (design #18 §4.2).
    """

    REMAINING_PROTECTIVE_OBLIGATION = "REMAINING_PROTECTIVE_OBLIGATION"
    OLD_AND_NEW_EXECUTABLE_QUANTITIES = "OLD_AND_NEW_EXECUTABLE_QUANTITIES"
    OVERLAP_AND_GAP_RISK = "OVERLAP_AND_GAP_RISK"
    CAPACITY_COMMITMENTS = "CAPACITY_COMMITMENTS"
    CANCELLATION_AUTHORIZATION = "CANCELLATION_AUTHORIZATION"
    PENDING_TRANSMISSION_CONFORMANCE = "PENDING_TRANSMISSION_CONFORMANCE"


class ReplacementOutcome(StrEnum):
    """The 5 local replacement decision results (design #18 §2.2-5; count = 5).

    ::

        REPLACEMENT_ADMISSIBLE  overlap-first complete + sequencing valid, or the
                                cancel-first 8-condition gate passed, or a proven atomic
                                replace — reached **only** by positive conjunction
        REPLACEMENT_DENIED      §6.3 line 176 "cancel-first replacement is denied";
                                §12 line 300 a risk-increasing change denies egress
        REPLACEMENT_CONTAINED   §6.4 line 180 / §17 — no safe mode, a deviation, or an
                                exceeded bound: retain or escalate the safest existing
                                protection, block new risk, preserve capacity, contain
        REPLACEMENT_TRAPPED     §5 line 139 (B) — a leg without current exact
                                ADR-002-019 admissibility (or outside the partition
                                scope) SHALL NOT proceed; the exposure stays
                                conservatively covered but untransmittable
        REPLACEMENT_UNKNOWN     §9 line 231 — the credible state space is not bounded
                                (∅ inputs, ``None`` magnitudes): conservatively UNKNOWN

    **No "assume-admissible" path (design #18 §4 / #16 CRITICAL lesson).**
    ``REPLACEMENT_ADMISSIBLE`` is never the *residual* branch of a gate: every producer
    in :mod:`tos.replacement.predicates` reaches it through an explicit positive
    identity test, and the residual branch of every dispatch is a restrictive member.

    **Truthy-sentinel seal (§2.2 / §0.1(j)).** Every member is a truthy ``StrEnum``, so
    ``DENIED`` / ``CONTAINED`` / ``TRAPPED`` / ``UNKNOWN`` would all pass a bare
    ``if outcome:``. A consuming gate SHALL test
    ``outcome is ReplacementOutcome.REPLACEMENT_ADMISSIBLE`` (identity).

    **Coordinate non-collapse (§2.2-5).** ``REPLACEMENT_TRAPPED`` is the *replacement
    outcome* axis; it is a **different type** from protective ``Admissibility.TRAPPED``
    (``vocabulary.py:138``, the lease-admissibility axis) and from rcl
    ``CapacityState.TRAPPED_CONSUMED`` (``vocabulary.py:30``, the capacity axis).
    ``tos.replacement`` re-authors neither — it consumes their verdicts as injected
    coordinates. ``REPLACEMENT_TRAPPED`` (covered, untransmittable, no further action)
    is also distinct from ``REPLACEMENT_CONTAINED`` (an active containment response).
    """

    REPLACEMENT_ADMISSIBLE = "REPLACEMENT_ADMISSIBLE"
    REPLACEMENT_DENIED = "REPLACEMENT_DENIED"
    REPLACEMENT_CONTAINED = "REPLACEMENT_CONTAINED"
    REPLACEMENT_TRAPPED = "REPLACEMENT_TRAPPED"
    REPLACEMENT_UNKNOWN = "REPLACEMENT_UNKNOWN"


#: The §9 line 233 "**at least**" minimum universe an overlap-first reservation must
#: cover — **mode-independent** (design #18 §4.5 M2). ``required <= reserved`` is the
#: completeness test in
#: :func:`~tos.replacement.predicates.overlap_first_reservation_complete`; an
#: unenumerated outcome is conservatively UNKNOWN (§9 line 231), never "no risk".
REQUIRED_CREDIBLE_INTERMEDIATE_OUTCOMES: frozenset[CredibleIntermediateOutcomeKind] = (
    frozenset(CredibleIntermediateOutcomeKind)
)

#: The §12 line 292-298 minimum universe every fill / recognized exposure change must
#: atomically re-evaluate.
REQUIRED_REEVALUATION_TARGETS: frozenset[ReevaluationTargetKind] = frozenset(
    ReevaluationTargetKind
)

#: The three outcome kinds whose **separate, non-negative, concurrently-present**
#: magnitudes structurally prove that no netting was applied (design #18 §0.4d / §4.1(2)
#: / §5.1, review prescription (b)). Netting offsets the old order against the new, which
#: erases or reduces one of the first two; their coexistence beside a non-negative
#: simultaneous-fill magnitude therefore makes netting **structurally impossible** — a
#: property a caller cannot forge with a flag (the v1.0 injected-``netting_applied``
#: fail-open is removed at the source). Declaration order is the §9 line 234-243 order.
NO_NETTING_MAGNITUDE_KINDS: tuple[CredibleIntermediateOutcomeKind, ...] = (
    CredibleIntermediateOutcomeKind.OLD_ORDER_REMAINING_EXECUTABLE,
    CredibleIntermediateOutcomeKind.NEW_ORDER_REMAINING_EXECUTABLE,
    CredibleIntermediateOutcomeKind.SIMULTANEOUS_OLD_AND_NEW_FILLS,
)

#: The 8 cancel-first preconditions, ADR §6.3 line 166-174 verbatim, in ADR declaration
#: order (count = 8). §6.3 line 176: "If any condition is unknown, cancel-first
#: replacement is denied" — so the gate requires **all eight positively proven**, and a
#: condition set that does not equal this universe is a denial, never a vacuous pass
#: (design #18 §4.3/§6.1). Each name is a field of
#: :class:`~tos.replacement.records.CancelFirstConditions`.
CANCEL_FIRST_ADMISSION_CONDITIONS: tuple[str, ...] = (
    # line 167 — "no safer proven replacement mode is available"
    "no_safer_proven_mode_available",
    # line 168 — "the active Safety Profile explicitly permits the mode for the scope"
    "safety_profile_permits_mode_for_scope",
    # line 169 — "the gap's worst credible exposure is within the aggregate hard envelope"
    "gap_worst_exposure_within_hard_envelope",
    # line 170 — "capacity for unprotected risk, late old-order fills, and the new order
    #             is committed in advance"
    "capacity_committed_in_advance",
    # line 171 — "an approved maximum gap bound and a containment action exist"
    "approved_max_gap_bound_and_containment_exist",
    # line 172 — "the necessary broker session, route, rate-limit, and order capacity are
    #             positively available or conservatively accounted"
    "broker_resources_available_or_accounted",
    # line 173 — "the current time basis is trustworthy"
    "time_basis_trustworthy",
    # line 174 — "the action has current Safety Authority and final egress approval"
    "current_authority_and_egress_approval",
)

#: The 8 axes ADR §1 line 34 requires to be **positively established** before a new
#: protective order counts as effective protection (count = 8, verbatim order):
#: "A new protective order does not count as effective protection merely because a request
#: was emitted or transport ACK was received. Its identity, quantity, side, price or
#: trigger semantics, remaining quantity, venue state, broker capability, and relation to
#: current exposure SHALL be positively established within approved freshness and
#: confidence bounds."
#:
#: **Transcription only — this is NOT a producer** (design #18 §4.6a / §6.3). The §10 line
#: 254-263 per-field Protection Sufficiency Proof is produced by evidence (ADR-002-006)
#: plus brokercap ``broker_capability_sufficient`` and is a minimum ``EV-L3+Broker``
#: coordinate (PR-EV-006, closing nothing). ``tos.replacement`` consumes a single injected
#: ``new_protection_sufficiency_current`` bool and derives it from nothing; this tuple
#: exists so the ADR item count stays cross-checkable (§10.2(12)) and so a reader can see
#: what the producer owes — never so that a caller can assemble the proof here.
PROTECTION_SUFFICIENCY_FIELDS: tuple[str, ...] = (
    "identity",
    "quantity",
    "side",
    "price_or_trigger_semantics",
    "remaining_quantity",
    "venue_state",
    "broker_capability",
    "relation_to_current_exposure",
)

#: The §5 line 124-135 linear lifecycle (7 states) in ADR declaration order. A
#: **structural transcription**, never a transition table: transition validity is not
#: Phase-1 (design #18 §5.3, Open Q3).
WORKFLOW_LIFECYCLE_ORDER: tuple[ReplacementWorkflowState, ...] = (
    ReplacementWorkflowState.PLANNED,
    ReplacementWorkflowState.CAPACITY_COMMITTED,
    ReplacementWorkflowState.FIRST_LEG_SENT,
    ReplacementWorkflowState.INTERMEDIATE_STATE,
    ReplacementWorkflowState.NEW_PROTECTION_PROVEN,
    ReplacementWorkflowState.OLD_FINALITY_PENDING,
    ReplacementWorkflowState.COMPLETED,
)

#: The 2 non-linear §5 line 134-135 states ("Any state" / "Any uncertain state").
WORKFLOW_NON_LINEAR_STATES: tuple[ReplacementWorkflowState, ...] = (
    ReplacementWorkflowState.FAILED_CONTAINED,
    ReplacementWorkflowState.RECOVERY_REQUIRED,
)

#: The 5 axes §5 line 107 forbids collapsing into one enum: "SHALL NOT collapse order
#: state, transmission state, knowledge confidence, capacity state, and protection state
#: into one enum". :class:`~tos.replacement.records.ReplacementWorkflowRecord` keeps one
#: **separate field per axis**, and a §7 property asserts the field set is complete.
ORTHOGONAL_WORKFLOW_AXES: tuple[str, ...] = (
    "broker_order_state",
    "transmission_attempt_state",
    "knowledge_confidence",
    "capacity_state",
    "protection_state",
)

# ---------------------------------------------------------------------------
# Injected sibling-coordinate tokens (design #18 §3.4 — token, never type)
# ---------------------------------------------------------------------------
# ``tos.replacement`` holds sibling edge 0, so a verdict arriving from a sibling crosses
# the seam as a bare token. Each constant below is the *token* of a real sibling member;
# a §7 seam test imports the sibling **in the test only** and asserts the token still
# equals the live member (drift lock — the afg ``ADMISSIBILITY_ADMISSIBLE`` precedent).

#: protective ``Admissibility.ADMISSIBLE`` (``vocabulary.py:137``). ``TRAPPED`` /
#: ``PROHIBITED`` are equally truthy, so the gate is an equality against **this token
#: only** (design #18 §4.7 / §3.4).
ADMISSIBILITY_ADMISSIBLE = "ADMISSIBLE"

#: venue ``OrderAdmissibilityResult.ADMISSIBLE`` (ADR-002-019 §5.4 line 123; design #19).
#:
#: **The folding rule for the ``leg_admissibility`` slot (design #18 v1.2 errata, §3.4).**
#: The real ADR-002-019 producer returns a **four**-token, truthy-untestable StrEnum
#: (``ADMISSIBLE`` / ``RESTRICTED_PROTECTIVE_ONLY`` / ``INADMISSIBLE`` / ``UNKNOWN``;
#: ``bool()`` raises ``TypeError``), while this package's slot is ``bool | None``. The
#: **caller** folds, and folds conservatively: ``True`` **only** when the verdict is
#: ``result is OrderAdmissibilityResult.ADMISSIBLE``; the other three tokens and ``None``
#: all fold to not-``True`` and therefore fail closed here.
#:
#: ``RESTRICTED_PROTECTIVE_ONLY`` deliberately folds to ``False`` on the **direct** path:
#: it permits no ordinary new risk (ADR-002-019 §1 line 29 / §19 line 426). A
#: protective-labelled leg may still proceed under it, but only through the **venue-owned**
#: ``protective_label_no_bypass`` (``venue/predicates.py:599``) whose four-condition
#: ``bool`` the caller then supplies to this slot. ``tos.replacement`` never re-decides
#: that — it consumes the produced bool (sibling edge 0; design #18 §0.2/§3.5).
ORDER_ADMISSIBILITY_ADMISSIBLE = "ADMISSIBLE"

#: protective ``ProtectiveActionKind.OVERLAP_FIRST_ADD_ONLY`` (``vocabulary.py:180``).
PROTECTIVE_ACTION_KIND_OVERLAP_FIRST_ADD_ONLY = "OVERLAP_FIRST_ADD_ONLY"

#: protective ``ProtectiveActionKind.CANCEL_FIRST_OR_REMOVAL`` (``vocabulary.py:180``).
PROTECTIVE_ACTION_KIND_CANCEL_FIRST_OR_REMOVAL = "CANCEL_FIRST_OR_REMOVAL"

#: orthostate ``BrokerOrderState.CANCELLED`` (``vocabulary.py:115``). §7 line 103-104:
#: "a later valid fill SHALL be accepted even after a locally observed ``CANCELLED``" —
#: so this token never terminates the exposure by itself (ADR-002-011 §11 / §4.6).
BROKER_ORDER_STATE_CANCELLED = "CANCELLED"

#: orthostate ``BrokerOrderState.UNKNOWN`` (``vocabulary.py:118``) — capacity-consuming,
#: never "safe to retry".
BROKER_ORDER_STATE_UNKNOWN = "UNKNOWN"

#: orthostate ``TransmissionAttemptState.SENT_UNCONFIRMED`` (``vocabulary.py:86``) — a
#: missing ACK leaves the attempt **potentially live** (ADR-002-011 §14; PR-EV-003).
ATTEMPT_STATE_SENT_UNCONFIRMED = "SENT_UNCONFIRMED"

#: brokercap ``ReplaceSemantics.ATOMIC_REPLACE`` (``vocabulary.py:207``, ADR-002-004
#: §8.8). §6.1 line 149: a method name or a happy path is **not** proof of atomicity;
#: unproven ⇒ non-atomic (line 151).
REPLACE_SEMANTICS_ATOMIC_REPLACE = "ATOMIC_REPLACE"


def protective_action_kind_token(mode: ReplacementMode) -> str | None:
    """Map a replacement mode onto the protective action-kind **token** (§3.4 seam).

    During a partition the protective ``partition_lease_admissible`` predicate
    (``predicates.py:460``) is asked for a verdict about a
    ``ProtectiveActionKind``. ``tos.replacement`` cannot import that enum (sibling edge
    0), so it emits the *token* a caller passes across the seam. Only the two
    directional modes have a partition-lease counterpart:
    ``OVERLAP_FIRST -> OVERLAP_FIRST_ADD_ONLY`` and
    ``CANCEL_FIRST -> CANCEL_FIRST_OR_REMOVAL`` (ADR §5 line 139 (C): "ADR-002-001 owns
    this rule").

    ``BROKER_PROVEN_ATOMIC`` and ``NO_SAFE_MODE`` map to ``None``: neither is a
    partition-time lease action, and a ``None`` is **restrictive** at the caller (there
    is no lease action to admit), never a wildcard.

    Args:
        mode: The replacement mode to map.

    Returns:
        The protective action-kind token, or ``None`` when the mode has no
        partition-lease counterpart.
    """
    if mode is ReplacementMode.OVERLAP_FIRST:
        return PROTECTIVE_ACTION_KIND_OVERLAP_FIRST_ADD_ONLY
    if mode is ReplacementMode.CANCEL_FIRST:
        return PROTECTIVE_ACTION_KIND_CANCEL_FIRST_OR_REMOVAL
    return None
