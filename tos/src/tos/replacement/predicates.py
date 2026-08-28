"""replacement decision predicates — overlap-first, partial-fill, cancel-first, mode.

Pure, fail-closed decision rules over injected frozen models (design #18 §0.2/§4.4):
``tos.replacement`` is **not** a capacity ledger, **not** a Cancellation Arbiter, **not**
a broker-capability judge, and **not** an egress. The capacity arithmetic, serialization,
and the atomic replacement-reservation commit are rcl-owned (ADR-002-011 §1 line 21 "The
Risk Capacity Ledger is the sole authority that reserves, commits, remaps, and releases
capacity"; §9 line 231); the Cancellation Arbiter and the partition-time lease
admissibility are protective-owned (§5 line 139 "ADR-002-001 owns this rule"); the
cancel-ACK-is-not-a-Final-Quantity-Proof L1 rule is afg-owned; the Final Quantity Proof
rules and the five replace/amend semantics are brokercap / evidence-owned (§4.6 line 99,
§6.1 line 147); the order and transmission-attempt state machines are orthostate-owned;
HALT precedence is authority-owned; recovery is recon-owned; and the aggregate-risk
projection is are-owned. This module **consumes every one of those as an injected
produced bool / token / magnitude and re-authors none of them** (design #18 §0.2/§3.5).

What it *does* author is the replacement **decision layer**: overlap-first reservation
completeness + structural no-netting + sequencing, partial-fill re-evaluation
completeness + no-hiding-clamp + egress disposition, the cancel-first 8-condition
admission gate, and mode admissibility. There is no "assume-covered" / "assume-complete"
/ "assume-admissible" path anywhere: a permissive result comes only from **positive
conjunction identity**, and the residual branch of every dispatch is restrictive (design
#18 §4.1 — the structural seal against the #6 fail-open REJECT and the #16 CRITICAL
"GRANT must not be the fall-through residue" lesson).

**Polarity discipline (design #18 §0.1(j) / §10.2(10) — the v1.1 C1 lesson).**

* ``ReplacementOutcome`` and the injected protective ``Admissibility`` verdict are truthy
  ``StrEnum``s, so every gate is an **identity** test
  (``is ReplacementOutcome.REPLACEMENT_ADMISSIBLE`` / ``== ADMISSIBILITY_ADMISSIBLE``
  against the single admitted token), never ``if outcome:``.
* **Positive-polarity** ``bool | None`` (safe value ``True``:
  ``within_hard_envelope``, ``new_protection_sufficiency_current``,
  ``protective_classification_present``, ``cancellation_admissible``,
  ``leg_admissibility``, ``fill_recognized``, ``economic_effect_persists``) is gated with
  ``is True``.
* **Negative-polarity** ``bool | None`` (safe value ``False``:
  ``hides_uncovered_or_reversing``, ``material_change``, ``expired``,
  ``became_risk_increasing``, ``bound_exceeded``,
  ``economic_effect_release_claimed``) is gated with ``is False`` **only**. ``is not
  True`` is *forbidden* on a negative-polarity field because a ``None`` would pass it —
  the exact v1.0 fail-open. A §7 source-level property asserts the absence of that shape.
* **no-netting is not a flag at all**: it is derived structurally from coexisting
  non-negative magnitudes (:func:`netting_absent`), so no polarity can be forged.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` (via the records) only; **no
sibling** ``tos.*`` (sibling edge 0, design #18 §0.3/§0.4b), no ``shared.*``.
"""

from __future__ import annotations

from collections.abc import Iterable

from tos.canonical import CanonicalDecimal
from tos.replacement.records import (
    CancelFirstConditions,
    OverlapReservationClaim,
)
from tos.replacement.vocabulary import (
    ADMISSIBILITY_ADMISSIBLE,
    CANCEL_FIRST_ADMISSION_CONDITIONS,
    NO_NETTING_MAGNITUDE_KINDS,
    CredibleIntermediateOutcomeKind,
    ReevaluationTargetKind,
    ReplacementMode,
    ReplacementOutcome,
)

__all__ = [
    # §5.1 overlap-first (PR-EV-001 substrate, core L1 slice)
    "netting_absent",
    "overlap_first_reservation_complete",
    "overlap_first_sequencing_valid",
    "overlap_first_reservation_outcome",
    "reversal_bounded_outcome",
    # §5.2 partial fill (PR-EV-005 substrate, core L1 slice)
    "partial_fill_reevaluation_complete",
    "no_hiding_clamp",
    "partial_fill_egress_disposition",
    # §6.1 cancel-first admission gate (PR-EV-002 substrate, predicate-only)
    "cancel_first_admission_gate",
    "cancel_first_admission_outcome",
    # §5.3 mode admissibility + §8 HALT precedence
    "replacement_mode_admissible",
    "halt_precedence_disposition",
    # §3.4 injected partition coordinate (PR-EV-010, consumed)
    "partition_replacement_admissible",
]

#: The single ``CANCEL_FIRST_ADMISSION_CONDITIONS`` universe as a set, precomputed so the
#: gate compares against a fixed 8-name contract rather than an ad-hoc literal.
_CANCEL_FIRST_REQUIRED_NAMES: frozenset[str] = frozenset(
    CANCEL_FIRST_ADMISSION_CONDITIONS
)


# ===========================================================================
# §5.1 overlap-first reservation completeness + no-netting + sequencing
# (ADR §6.2 line 153-159 / §9 line 229-248; PR-EV-001; PR-AC-001)
# ===========================================================================


def netting_absent(claim: OverlapReservationClaim | None) -> bool:
    """Whether no netting was applied — derived **structurally** (design #18 §0.4d/M6).

    ADR §20.2 line 443: "Simultaneous fills can over-close or reverse exposure", so an
    overlap-first reservation SHALL count the old order **and** the new order, never the
    net of the two. This predicate proves that structurally rather than trusting a
    caller-supplied ``netting_applied`` flag (whose ``None`` was the v1.0 fail-open):

    ``True`` **only** when all three
    :data:`~tos.replacement.vocabulary.NO_NETTING_MAGNITUDE_KINDS` magnitudes —
    ``OLD_ORDER_REMAINING_EXECUTABLE``, ``NEW_ORDER_REMAINING_EXECUTABLE``, and
    ``SIMULTANEOUS_OLD_AND_NEW_FILLS`` — are **present (not ``None``), finite, and
    non-negative** in the claim. Netting offsets the old against the new, which erases or
    reduces one of the first two; their coexistence beside a non-negative
    simultaneous-fill magnitude therefore makes netting structurally impossible. Any
    ``None`` (UNKNOWN, never zero) or negative magnitude ⇒ ``False`` (netting suspected /
    unproven ⇒ fail closed).

    ``tos.replacement`` does **not** sum these magnitudes: the dimension-wise summation
    and the hard-envelope enforcement are rcl-owned (``aggregate_usage``
    ``vector.py:103`` / ``effective_limit`` ``vector.py:139``), and the resulting double
    count is the conservative requirement, not a defect (§0.4d). [SAFE-002; SAFE-004;
    SAFE-013]

    **Guarantee scope**: this is a *signature* detector — it proves that netting **cannot
    have been applied** to the claim's shape (a flag is unforgeable because there is no
    flag), not that the magnitudes are numerically correct. Accounting accuracy of the
    values themselves is evidence / runtime territory (ADR-002-006, §18 line 410
    "Evidence Is Not Authority"), never this predicate's.

    Args:
        claim: The injected overlap-first reservation claim (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff no-netting is structurally proven.
    """
    if claim is None:
        return False
    for kind in NO_NETTING_MAGNITUDE_KINDS:
        magnitude = claim.magnitude_of(kind)
        if magnitude is None:
            return False
        if not magnitude.is_finite():
            return False
        if magnitude < 0:
            return False
    return True


def overlap_first_reservation_complete(
    claim: OverlapReservationClaim | None,
    required_outcomes: frozenset[CredibleIntermediateOutcomeKind],
    *,
    within_hard_envelope: bool | None,
) -> bool:
    """Whether an overlap-first reservation is complete (ADR §6.2/§9; PR-EV-001).

    §6.2 line 157: before transmission overlap-first "requires capacity for the worst
    credible simultaneous executions and broker resources for both orders". §9 line 233:
    the reservation "SHALL include **at least**" the nine credible intermediate outcomes;
    line 231: "an outcome not bounded by these is treated conservatively as UNKNOWN".

    ``True`` **only** as one positive conjunction (no fall-through ``return True``):

    * the claim exists;
    * ``required_outcomes`` is **non-empty** — an empty universe proves nothing, so it can
      never certify completeness vacuously (design #18 §4.7 row 1);
    * ``required_outcomes <= claim.reserved_outcome_kinds`` (every required outcome is
      reserved; a missing one leaves an unbounded outcome);
    * :func:`netting_absent` holds structurally;
    * ``within_hard_envelope is True`` — the **injected rcl verdict**
      ``aggregate_usage <= effective_limit`` (positive polarity; ``None`` ⇒ UNKNOWN ⇒
      ``False``). ``tos.replacement`` performs no capacity arithmetic (design #18
      §0.2/§0.4c), so PR-AC-001's "prevents unbounded reversal" means *the structurally
      double-counted reservation stays under the envelope rcl enforces*.

    [SAFE-002 hard envelope; SAFE-004; SAFE-013 aggregate risk]

    Args:
        claim: The injected overlap-first reservation claim.
        required_outcomes: The required credible-intermediate-outcome universe (normally
            :data:`~tos.replacement.vocabulary.REQUIRED_CREDIBLE_INTERMEDIATE_OUTCOMES`).
        within_hard_envelope: The injected rcl hard-envelope verdict.

    Returns:
        ``True`` iff the reservation is positively proven complete.
    """
    return (
        claim is not None
        and len(required_outcomes) > 0
        and required_outcomes <= claim.reserved_outcome_kinds
        and netting_absent(claim)
        and within_hard_envelope is True
    )


def overlap_first_sequencing_valid(
    *,
    new_protection_sufficiency_current: bool | None,
    protective_classification_present: bool | None,
    cancellation_admissible: bool | None,
    leg_admissibility: bool | None,
) -> bool:
    """Whether the old order may be cancelled yet (ADR §6.2 line 159; PR-EV-001).

    §6.2 line 159 verbatim: "The old order SHALL NOT be cancelled until the new Protection
    Sufficiency Proof is current and the Cancellation Arbiter determines that removal will
    not reduce required protection." The **four-conjunct** realization (design #18 §5.1,
    v1.1 C2 + M1) — all four are **positive polarity, ``is True`` only**:

    (i)   ``new_protection_sufficiency_current`` — the §10 line 254-263 **per-field**
          Protection Sufficiency Proof, produced by evidence (ADR-002-006) plus brokercap
          ``broker_capability_sufficient`` (``predicates.py:206``). §1 line 34: a new
          protective order "does not count as effective protection merely because a
          request was emitted or transport ACK was received" — its identity, quantity,
          side, price / trigger semantics, remaining quantity, venue state, broker
          capability, and relation to current exposure (8 fields) must be **positively
          established**; §10 line 267: a stale or contradicted proof does **not** remain
          sufficient by inertia. PR-EV-006 coordinate, ``+Broker`` deferred.
    (ii)  ``protective_classification_present`` — protective ``predicates.py:309``, whose
          proposition is "``PROTECTIVE_PROVEN`` via conservative **aggregate-risk**
          analysis". That is a **different axis** from (i)'s per-field sufficiency, so it
          is a **separate conjunct**, not a substitute (the v1.1 C2 category error, which
          in v1.0 let an aggregate-risk classification stand in for a per-field proof).
    (iii) ``cancellation_admissible`` — the protective Cancellation Arbiter verdict
          (``predicates.py:523``), which already encodes §11.4 line 506 "a submitted /
          transmitted / acknowledged replacement gets **no** optimistic protection
          credit". Consumed, never re-authored (design #18 §0.2/§3.5).
    (iv)  ``leg_admissibility`` — the current **exact** ADR-002-019 Order Admissibility
          Decision for this leg (§5 line 139 (B)); missing or unknown ⇒ the leg SHALL NOT
          proceed. The caller maps that to
          :attr:`~tos.replacement.vocabulary.ReplacementOutcome.REPLACEMENT_TRAPPED` via
          :func:`overlap_first_reservation_outcome`.

    Any conjunct that is not the singleton ``True`` ⇒ ``False`` ⇒ the old order stays.
    **Direction check (§4.5).** This is the *new -> old* rule; :func:`cancel_first_admission_gate`
    is the opposite *old -> new* rule. Confusing them is a fail-open defect.
    [SAFE-002; SAFE-021; SAFE-023]

    Args:
        new_protection_sufficiency_current: §10 per-field sufficiency proof currentness.
        protective_classification_present: protective aggregate-risk classification.
        cancellation_admissible: protective Cancellation Arbiter verdict.
        leg_admissibility: current exact ADR-002-019 leg admissibility.

    Returns:
        ``True`` iff all four are positively current.
    """
    return (
        new_protection_sufficiency_current is True
        and protective_classification_present is True
        and cancellation_admissible is True
        and leg_admissibility is True
    )


def overlap_first_reservation_outcome(
    claim: OverlapReservationClaim | None,
    required_outcomes: frozenset[CredibleIntermediateOutcomeKind],
    *,
    within_hard_envelope: bool | None,
    leg_admissibility: bool | None,
) -> ReplacementOutcome:
    """Resolve an overlap-first reservation to an outcome (design #18 §4.7 rows 1/9).

    The ∅ / trapped dispositions the bool-valued
    :func:`overlap_first_reservation_complete` cannot express:

    * an **empty** required-outcome universe, or an absent / empty claim, means the
      credible state space is not bounded ⇒ ``REPLACEMENT_UNKNOWN`` (§9 line 231 "treated
      conservatively as UNKNOWN"). ∅ is never "no risk";
    * a leg without current exact ADR-002-019 admissibility ⇒ ``REPLACEMENT_TRAPPED``
      (§5 line 139 (B): such a leg "SHALL NOT proceed"; the exposure stays conservatively
      covered but untransmittable);
    * ``REPLACEMENT_ADMISSIBLE`` is reached **only** through the positive
      :func:`overlap_first_reservation_complete` conjunction — everything else is
      ``REPLACEMENT_DENIED`` (the restrictive residue, #16 CRITICAL lesson).

    Args:
        claim: The injected overlap-first reservation claim.
        required_outcomes: The required credible-intermediate-outcome universe.
        within_hard_envelope: The injected rcl hard-envelope verdict.
        leg_admissibility: Current exact ADR-002-019 leg admissibility.

    Returns:
        The conservative :class:`~tos.replacement.vocabulary.ReplacementOutcome`.
    """
    if len(required_outcomes) == 0:
        return ReplacementOutcome.REPLACEMENT_UNKNOWN
    if claim is None or len(claim.reserved_outcome_kinds) == 0:
        return ReplacementOutcome.REPLACEMENT_UNKNOWN
    if leg_admissibility is not True:
        return ReplacementOutcome.REPLACEMENT_TRAPPED
    if (
        overlap_first_reservation_complete(
            claim, required_outcomes, within_hard_envelope=within_hard_envelope
        )
        is True
    ):
        return ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    return ReplacementOutcome.REPLACEMENT_DENIED


def reversal_bounded_outcome(
    *,
    aggregate_risk_magnitude: CanonicalDecimal | None,
    hard_envelope_limit: CanonicalDecimal | None,
    within_hard_envelope: bool | None,
) -> ReplacementOutcome:
    """Whether the doubly-counted reservation stays bounded (PR-AC-001; §4.7 row 5).

    PR-AC-001 requires overlap-first to "prevent unbounded reversal". The aggregate-risk
    projection over the credible state space is **are-owned** (ADR-002-021) and the
    dimension-wise summation / envelope is **rcl-owned**; this predicate only *compares*
    the injected magnitudes and propagates UNKNOWN (design #18 §0.2 — comparison is not
    capacity arithmetic):

    * either magnitude ``None`` ⇒ ``REPLACEMENT_UNKNOWN`` (rcl ``aggregate_usage``
      propagates ``None`` the same way; §5.3 UNKNOWN is never a soft pass);
    * ``within_hard_envelope`` not positively ``True`` ⇒ ``REPLACEMENT_DENIED``;
    * ``REPLACEMENT_ADMISSIBLE`` only from the positive comparison
      ``aggregate_risk_magnitude <= hard_envelope_limit``.

    Args:
        aggregate_risk_magnitude: The injected are aggregate-risk projection.
        hard_envelope_limit: The injected hard-envelope bound.
        within_hard_envelope: The injected rcl verdict.

    Returns:
        The conservative :class:`~tos.replacement.vocabulary.ReplacementOutcome`.
    """
    if aggregate_risk_magnitude is None or hard_envelope_limit is None:
        return ReplacementOutcome.REPLACEMENT_UNKNOWN
    if not aggregate_risk_magnitude.is_finite() or not hard_envelope_limit.is_finite():
        return ReplacementOutcome.REPLACEMENT_UNKNOWN
    if within_hard_envelope is not True:
        return ReplacementOutcome.REPLACEMENT_DENIED
    if aggregate_risk_magnitude <= hard_envelope_limit:
        return ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    return ReplacementOutcome.REPLACEMENT_DENIED


# ===========================================================================
# §5.2 partial-fill re-evaluation completeness + no-hiding-clamp
# (ADR §12 line 289-302; PR-EV-005; PR-AC-005)
# ===========================================================================


def partial_fill_reevaluation_complete(
    reevaluated: frozenset[ReevaluationTargetKind],
    required_targets: frozenset[ReevaluationTargetKind],
    *,
    fill_recognized: bool | None,
) -> bool:
    """Whether a fill triggered the full atomic re-evaluation (ADR §12; PR-EV-005).

    §12 line 291 verbatim: "Every fill or recognized exposure change invalidates stale
    quantity calculations and triggers **atomic** re-evaluation of" the six §12 line
    292-298 targets. ``True`` **only** as one positive conjunction:

    * ``fill_recognized is True`` (positive polarity — an unrecognized or unknown fill
      cannot certify that a re-evaluation happened);
    * ``required_targets`` is **non-empty** — an empty target universe would certify
      completeness vacuously (design #18 §4.7 row 2);
    * ``required_targets <= reevaluated`` — a missing target leaves a stale quantity
      calculation in place, so partial re-evaluation is ``False``, never a soft pass.

    [SAFE-023 partial fills; SAFE-025 asynchronous outcomes]

    Args:
        reevaluated: The targets actually re-evaluated.
        required_targets: The required universe (normally
            :data:`~tos.replacement.vocabulary.REQUIRED_REEVALUATION_TARGETS`).
        fill_recognized: Whether the fill / exposure change was recognized.

    Returns:
        ``True`` iff the atomic re-evaluation is positively proven complete.
    """
    return (
        fill_recognized is True
        and len(required_targets) > 0
        and required_targets <= reevaluated
    )


def no_hiding_clamp(
    *,
    clamp_applied: bool | None,
    hides_uncovered_or_reversing: bool | None,
) -> bool:
    """Whether rounding / clamping hides no quantity (ADR §12 line 302; PR-EV-005).

    §12 line 302 verbatim: a quantity "SHALL NOT be rounded or clamped in a way that
    **hides uncovered or reversing quantity**"; lot-size, fractional, multiplier, and
    instrument constraints require "explicit conservative treatment".

    ``hides_uncovered_or_reversing`` is a **negative-polarity** flag (safe value
    ``False``), so the gate is ``is False`` **only**: an unknown (``None``) hiding status
    is *not* a pass. Writing ``is not False`` ⇒ ``False`` would be equivalent; writing
    ``is not True`` would let ``None`` through and is the exact v1.0 fail-open shape this
    package forbids (design #18 §0.1(j); a §7 source property asserts its absence).

    ``clamp_applied`` is the §12 **coordinate** the record retains for evidence, and it is
    deliberately **not** a gate: a clamp that hides nothing is permitted, and a clamp that
    was never applied still has to assert that nothing is hidden. Reading the contract
    literally keeps the rule about *hiding*, not about *clamping*; a §7 canary asserts the
    verdict is invariant across ``True`` / ``False`` / ``None`` values of this argument so
    the choice cannot silently drift.

    Args:
        clamp_applied: Whether a rounding / clamp was applied (retained coordinate).
        hides_uncovered_or_reversing: Whether it hides uncovered or reversing quantity.

    Returns:
        ``True`` iff hiding is positively excluded.
    """
    return hides_uncovered_or_reversing is False


def partial_fill_egress_disposition(
    *,
    became_risk_increasing: bool | None,
    already_transmitted: bool | None,
) -> ReplacementOutcome:
    """Egress disposition after a partial fill (ADR §12 line 300; PR-EV-005).

    §12 line 300: if the re-evaluation shows the pending replacement became
    risk-increasing, egress is **denied or contained**.

    ``became_risk_increasing`` is a **negative-polarity** flag (safe value ``False``):
    only a positive ``is False`` reaches the permissive
    ``REPLACEMENT_ADMISSIBLE`` identity. ``None`` (unknown) is treated **as
    risk-increasing** — never waved through (``is not True`` is forbidden here).

    ``already_transmitted`` decides *which* restrictive outcome applies, and it too fails
    closed: only a positive ``is False`` (proven not transmitted) yields
    ``REPLACEMENT_DENIED`` (block the egress). ``True`` **or unknown** yields
    ``REPLACEMENT_CONTAINED`` — if it may already be on the wire, denial alone is
    insufficient and §17 containment applies (retain or escalate the safest existing
    protection, block new risk, preserve capacity, escalate). Containment is the heavier
    response, so the unknown case takes it.

    [SAFE-023; SAFE-025]

    Args:
        became_risk_increasing: Whether re-evaluation showed a risk-increasing change.
        already_transmitted: Whether the replacement was already transmitted.

    Returns:
        ``REPLACEMENT_ADMISSIBLE`` only from a proven non-risk-increasing change;
        otherwise ``REPLACEMENT_DENIED`` / ``REPLACEMENT_CONTAINED``.
    """
    if became_risk_increasing is False:
        return ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    if already_transmitted is False:
        return ReplacementOutcome.REPLACEMENT_DENIED
    return ReplacementOutcome.REPLACEMENT_CONTAINED


# ===========================================================================
# §6.1 cancel-first admission gate (ADR §6.3 line 161-176; PR-EV-002)
# ===========================================================================


def cancel_first_admission_gate(
    conditions: CancelFirstConditions | None,
    *,
    leg_admissibility: bool | None,
) -> bool:
    """The cancel-first admission gate (ADR §6.3 line 166-176; PR-EV-002).

    §6.3 line 163: cancel-first removes the old protection **before** the new is
    established (the *old -> new* direction — the exact opposite of
    :func:`overlap_first_sequencing_valid`, design #18 §4.5), which "creates or may create
    a Protection Gap" (line 165). It "MAY be authorized only when **all** of the
    following hold" (the eight line 166-174 preconditions), and "If any condition is
    unknown, cancel-first replacement is **denied**" (line 176).

    ``True`` **only** as one positive conjunction:

    * ``conditions`` exists — an absent condition set is the ∅ case and can never admit
      vacuously (design #18 §4.7 row 3);
    * ``conditions.positively_proven() == CANCEL_FIRST_ADMISSION_CONDITIONS`` — the set of
      conditions proven ``True`` equals the **full 8-name universe**. An all-``None``
      instance proves ∅, which is not the universe, so it denies; a truthy non-``bool``
      forged past the annotation is not ``True`` and so is not proof;
    * ``leg_admissibility is True`` — the **ninth conjunct** (design #18 §4.3 M1-②):
      cancel-first is a cancellation-involving leg, and §5 line 139 (B) says "a
      cancellation-involving replacement leg outside that scope ... SHALL NOT proceed".
      The caller maps a failure here to ``REPLACEMENT_TRAPPED`` via
      :func:`cancel_first_admission_outcome`.

    The eight conditions' *sources* are sibling-owned and injected — protective
    ``cancellation_admissible`` (``predicates.py:523``), brokercap ``rate_admission_ok``
    (``predicates.py:437``), the ADR-002-008 trustworthy-time basis, the rcl commit and
    envelope verdicts, and the authority / egress approval. This gate **adds** the
    replacement-mode conjunction; it does not re-implement the Cancellation Arbiter
    (design #18 §0.2/§3.5). **Minimum ``EV-L2/3`` — this closes no PR-EV.**
    [SAFE-011 cancellation non-bypass; SAFE-040; SAFE-043 exit unavailability]

    Args:
        conditions: The injected 8-condition value model (``None`` ⇒ denied).
        leg_admissibility: Current exact ADR-002-019 leg admissibility.

    Returns:
        ``True`` iff all eight conditions plus the leg slot are positively proven.
    """
    return (
        conditions is not None
        and conditions.positively_proven() == _CANCEL_FIRST_REQUIRED_NAMES
        and leg_admissibility is True
    )


def cancel_first_admission_outcome(
    conditions: CancelFirstConditions | None,
    *,
    leg_admissibility: bool | None,
) -> ReplacementOutcome:
    """Resolve the cancel-first gate to an outcome (design #18 §4.3 / §4.7 rows 3/9).

    * ``leg_admissibility`` not positively ``True`` ⇒ ``REPLACEMENT_TRAPPED`` (§5 line
      139 (B)) — checked first, because an inadmissible leg cannot proceed regardless of
      how well the other eight conditions are proven;
    * all eight conditions positively proven (with an admissible leg) ⇒
      ``REPLACEMENT_ADMISSIBLE`` (positive identity);
    * anything else — including the ∅ / all-unknown condition set ⇒
      ``REPLACEMENT_DENIED`` (§6.3 line 176).

    Args:
        conditions: The injected 8-condition value model.
        leg_admissibility: Current exact ADR-002-019 leg admissibility.

    Returns:
        The conservative :class:`~tos.replacement.vocabulary.ReplacementOutcome`.
    """
    if leg_admissibility is not True:
        return ReplacementOutcome.REPLACEMENT_TRAPPED
    if cancel_first_admission_gate(conditions, leg_admissibility=leg_admissibility):
        return ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    return ReplacementOutcome.REPLACEMENT_DENIED


# ===========================================================================
# §5.3 mode admissibility + §8 HALT precedence
# ===========================================================================


def replacement_mode_admissible(
    mode: ReplacementMode,
    *,
    atomic_proven: bool | None,
    overlap_reservation_complete: bool | None,
    overlap_sequencing_valid: bool | None,
    cancel_first_gate_passed: bool | None,
    leg_admissibilities: frozenset[bool],
    bound_exceeded: bool | None,
) -> ReplacementOutcome:
    """Whether a replacement mode is admissible (ADR §6 / §15 line 351; design #18 §5.3).

    Each mode's **direction-specific** premises are checked as a **separate positive
    conjunction** (design #18 §4.5 truth table); a mode is never promoted by
    fall-through, and an unrecognized ``mode`` value resolves to the restrictive
    ``REPLACEMENT_UNKNOWN`` rather than to an admissible residue (#16 CRITICAL lesson).

    Gate order:

    1. **bound exceeded ⇒ containment.** §15 line 351 lists three ``SHALL NOT``s when a
       gap / overlap / proof / containment bound is exceeded: the runtime SHALL NOT
       extend authority, SHALL NOT widen capacity, and SHALL NOT declare the replacement
       complete. ``bound_exceeded`` is a **negative-polarity** flag (safe value
       ``False``), so only a positive ``is False`` proceeds; ``True`` *and unknown* ⇒
       ``REPLACEMENT_CONTAINED``. Containment precedes everything else because it is the
       heaviest required response.
    2. **every leg admissible.** The mode composition point (design #18 §5.3 M1):
       ``leg_admissibilities`` must be **non-empty** and every member must be the
       singleton ``True`` (§5 line 139 (B)). An empty set is the ∅ case — no leg proven
       admissible is not "all legs admissible" — and any non-``True`` member ⇒
       ``REPLACEMENT_TRAPPED``.
    3. **per-mode premises** (identity dispatch, ADR §6):
       ``BROKER_PROVEN_ATOMIC`` requires ``atomic_proven is True`` — §6.1 line 147 the
       active Broker Capability Profile must prove the exact semantics by executed
       evidence; line 149 a method name or happy path is **not** proof; line 151 unproven
       ⇒ non-atomic. ``OVERLAP_FIRST`` requires ``overlap_reservation_complete is True``
       **and** ``overlap_sequencing_valid is True`` (§6.2). ``CANCEL_FIRST`` requires
       ``cancel_first_gate_passed is True`` (§6.3). ``NO_SAFE_MODE`` ⇒
       ``REPLACEMENT_CONTAINED`` — §6.4 line 180 "retain or escalate the safest existing
       protection, block new risk, preserve capacity, and enter containment".

    **HALT is composed, not embedded.** The signature is fixed by design #18 §5.3 (G5,
    "완결 signature") and carries no HALT input; §8 line 225 precedence is applied by the
    caller through :func:`halt_precedence_disposition` **before** this predicate. See
    that function for the both-ways blind-cancel canary.

    [SAFE-002; SAFE-004; SAFE-011; SAFE-013]

    Args:
        mode: The replacement mode under consideration.
        atomic_proven: brokercap-proven atomic replace semantics (§6.1).
        overlap_reservation_complete: The §5.1 completeness result.
        overlap_sequencing_valid: The §5.1 sequencing result.
        cancel_first_gate_passed: The §6.1 gate result.
        leg_admissibilities: Per-leg ADR-002-019 admissibility flags.
        bound_exceeded: Whether a §15 bound was exceeded (negative polarity).

    Returns:
        The conservative :class:`~tos.replacement.vocabulary.ReplacementOutcome`.
    """
    if bound_exceeded is not False:
        return ReplacementOutcome.REPLACEMENT_CONTAINED
    if not _all_positively_true(leg_admissibilities):
        return ReplacementOutcome.REPLACEMENT_TRAPPED
    if mode is ReplacementMode.BROKER_PROVEN_ATOMIC:
        if atomic_proven is True:
            return ReplacementOutcome.REPLACEMENT_ADMISSIBLE
        return ReplacementOutcome.REPLACEMENT_DENIED
    if mode is ReplacementMode.OVERLAP_FIRST:
        if overlap_reservation_complete is True and overlap_sequencing_valid is True:
            return ReplacementOutcome.REPLACEMENT_ADMISSIBLE
        return ReplacementOutcome.REPLACEMENT_DENIED
    if mode is ReplacementMode.CANCEL_FIRST:
        if cancel_first_gate_passed is True:
            return ReplacementOutcome.REPLACEMENT_ADMISSIBLE
        return ReplacementOutcome.REPLACEMENT_DENIED
    if mode is ReplacementMode.NO_SAFE_MODE:
        return ReplacementOutcome.REPLACEMENT_CONTAINED
    return ReplacementOutcome.REPLACEMENT_UNKNOWN


def halt_precedence_disposition(
    *,
    halt_active: bool | None,
    halt_compatible_protective_or_containment: bool | None,
    protection_necessary_for_existing_exposure: bool | None,
    cancellation_admissible: bool | None,
) -> ReplacementOutcome:
    """HALT precedence over replacement initiation (ADR §8 line 225; PR-EV-011, Gap-7).

    §8 line 225 verbatim: "HALT dominates ordinary replacement initiation. Only a
    HALT-compatible protective or containment workflow ... MAY proceed. A protective
    order already necessary to contain existing exposure SHALL not be **blindly
    cancelled**."

    The precedence *enforcement* is authority-owned (``AuthorityState.HALTED`` /
    ``PRECEDENCE_RANK`` / ``restrictive_dominates``) and the blind-cancel prohibition is
    protective-owned (``cancellation_admissible`` ``predicates.py:523``): both arrive here
    as injected bools and neither is re-authored (design #18 §0.2/§3.5). This predicate
    only lands the **PR-side disposition** so that ``tos.replacement`` can never *emit* a
    blind cancel during a HALT:

    * ``halt_active is False`` ⇒ ``REPLACEMENT_ADMISSIBLE`` — HALT does not apply and the
      ordinary mode gate decides (positive identity; a ``None`` HALT state is unknown and
      therefore **not** cleared);
    * HALT active or unknown, and the protective order is (or may be) necessary to contain
      existing exposure while the Cancellation Arbiter has not positively admitted the
      removal ⇒ ``REPLACEMENT_TRAPPED``: the protection is retained, untransmittable, and
      **not** blindly cancelled;
    * otherwise ⇒ ``REPLACEMENT_ADMISSIBLE`` only for a **positively** HALT-compatible
      protective / containment workflow; anything else ⇒ ``REPLACEMENT_CONTAINED``
      (ordinary replacement initiation is blocked).

    The composition with :func:`replacement_mode_admissible` is the caller's: HALT first,
    mode second, and the more restrictive of the two governs.

    Args:
        halt_active: Injected authority HALT state (positive polarity: only ``False``
            clears it).
        halt_compatible_protective_or_containment: Whether the workflow is positively
            HALT-compatible.
        protection_necessary_for_existing_exposure: Whether the protective order is
            already necessary to contain existing exposure (negative polarity: only a
            positive ``False`` says it is not).
        cancellation_admissible: The protective Cancellation Arbiter verdict.

    Returns:
        The conservative :class:`~tos.replacement.vocabulary.ReplacementOutcome`.
    """
    if halt_active is False:
        return ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    if (
        protection_necessary_for_existing_exposure is not False
        and cancellation_admissible is not True
    ):
        return ReplacementOutcome.REPLACEMENT_TRAPPED
    if halt_compatible_protective_or_containment is True:
        return ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    return ReplacementOutcome.REPLACEMENT_CONTAINED


# ===========================================================================
# §3.4 injected partition coordinate (PR-EV-010 — consumed, never re-authored)
# ===========================================================================


def partition_replacement_admissible(
    partition_lease_verdict: str | None,
    *,
    mode: ReplacementMode,
) -> bool:
    """Whether a replacement leg may proceed during a partition (ADR §5 line 139 (C)).

    §5 line 139 (C): the partition-time lease-admissibility rule is **owned by
    ADR-002-001** — protective ``partition_lease_admissible`` (``predicates.py:460``)
    returns the 3-token ``Admissibility`` StrEnum (``ADMISSIBLE`` / ``TRAPPED`` /
    ``PROHIBITED``). ``tos.replacement`` re-authors none of it; it consumes the verdict
    token (sibling edge 0, so the token crosses the seam as a bare string).

    **Every** ``Admissibility`` member is truthy, so a bare truthiness gate would admit
    ``TRAPPED`` and ``PROHIBITED``: the gate is an equality against the single
    :data:`~tos.replacement.vocabulary.ADMISSIBILITY_ADMISSIBLE` token, and ``None`` /
    ``TRAPPED`` / ``PROHIBITED`` all deny (design #18 §4.7 row 11).

    The mode is also checked: only the *add-only* direction has a partition-lease
    counterpart (:func:`~tos.replacement.vocabulary.protective_action_kind_token`
    maps ``OVERLAP_FIRST -> OVERLAP_FIRST_ADD_ONLY``). ``CANCEL_FIRST`` during a
    partition is a removal outside the pre-proven scope and is refused here regardless of
    the verdict token (§9 line 448 as quoted by protective: cancel-first / removal /
    weakening is ``TRAPPED``), as are the two modes with no lease counterpart.

    Args:
        partition_lease_verdict: The injected protective ``Admissibility`` token.
        mode: The replacement mode requesting the partition-time lease.

    Returns:
        ``True`` iff the verdict is ``ADMISSIBLE`` for an add-only overlap-first leg.
    """
    return (
        mode is ReplacementMode.OVERLAP_FIRST
        and partition_lease_verdict == ADMISSIBILITY_ADMISSIBLE
    )


def _all_positively_true(flags: Iterable[bool | None]) -> bool:
    """Whether every flag is the singleton ``True`` **and** the iterable is non-empty.

    A shared helper for the ∅-void discipline: ``all(...)`` over an empty iterable is
    vacuously ``True``, which is exactly the fail-open shape design #18 §4.7 forbids.

    Args:
        flags: The injected flags.

    Returns:
        ``True`` iff at least one flag exists and all of them are ``True``.
    """
    materialized = tuple(flags)
    return len(materialized) > 0 and all(flag is True for flag in materialized)
