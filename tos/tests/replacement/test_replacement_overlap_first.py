"""Core §5.1 overlap-first properties — completeness, no-netting, 4-input sequencing.

PR-EV-001 **substrate** (ADR §6.2 / §9; PR-AC-001). **Discipline tag**: this is the
``EV-L1`` slice only — the ``/3`` integration-fault and adversarial-interleaving overlay
plus independent review remain open, so **no PR-EV is closed here** and no EV-L1-complete
claim is made (design #18 §1).

Both-ways coverage (design #18 §4.1 canary): every guard is exercised in its **firing**
direction (a missing outcome, a ``None`` / negative magnitude, an unproven envelope, an
uncurrent conjunct) *and* in its **passing** direction (a genuinely complete reservation
with all four conjuncts current must not be blocked). A vacuous block is a defect too.
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st
from tos.replacement import (
    CredibleIntermediateOutcomeKind,
    OverlapReservationClaim,
    ReplacementOutcome,
    netting_absent,
    overlap_first_reservation_complete,
    overlap_first_reservation_outcome,
    overlap_first_sequencing_valid,
    reversal_bounded_outcome,
)

from ._replacement_strategies import (
    ALL_OUTCOMES,
    FINITE_NEGATIVE,
    FINITE_NON_NEGATIVE,
    MAGNITUDE_SLOT,
    NETTING_KINDS,
    OUTCOME_SETS,
    TRIBOOL,
    TRUTHY_NON_BOOL,
    clean_claim,
    clean_magnitudes,
    clean_sequencing_inputs,
)

# ===========================================================================
# (ii) structural no-netting — the v1.1 M6 prescription (b)
# ===========================================================================


@given(old=MAGNITUDE_SLOT, new=MAGNITUDE_SLOT, simultaneous=MAGNITUDE_SLOT)
def test_no_netting_holds_iff_all_three_magnitudes_coexist_non_negative(
    old: Decimal | None, new: Decimal | None, simultaneous: Decimal | None
) -> None:
    """(§0.4d/M6) ``netting_absent`` ⇔ the three slots are present **and** non-negative.

    The strategy deliberately draws ``None`` / negative / non-negative for each slot, so
    the ∅ and negative branches are genuinely exercised (the #10 lesson).
    """
    claim = clean_claim(
        magnitudes=clean_magnitudes(
            OLD_ORDER_REMAINING_EXECUTABLE=old,
            NEW_ORDER_REMAINING_EXECUTABLE=new,
            SIMULTANEOUS_OLD_AND_NEW_FILLS=simultaneous,
        )
    )
    expected = all(
        value is not None and value >= 0 for value in (old, new, simultaneous)
    )
    assert netting_absent(claim) is expected


@given(kind=st.sampled_from(list(NETTING_KINDS)))
def test_dropping_any_single_netting_slot_breaks_the_structural_proof(
    kind: CredibleIntermediateOutcomeKind,
) -> None:
    """(guard fires) Netting erases one magnitude — dropping any one slot ⇒ ``False``."""
    magnitudes = dict(clean_magnitudes())
    magnitudes[kind] = None
    assert netting_absent(clean_claim(magnitudes=magnitudes)) is False


@given(kind=st.sampled_from(list(NETTING_KINDS)), negative=FINITE_NEGATIVE)
def test_a_negative_magnitude_is_netting_suspicion(
    kind: CredibleIntermediateOutcomeKind, negative: Decimal
) -> None:
    """(guard fires) A negative magnitude is an offset, i.e. netting ⇒ ``False``."""
    magnitudes = dict(clean_magnitudes())
    magnitudes[kind] = negative
    assert netting_absent(clean_claim(magnitudes=magnitudes)) is False


def test_empty_magnitude_map_and_absent_claim_both_fail_closed() -> None:
    """(∅ both ways) No magnitudes at all, and no claim at all, prove nothing."""
    assert netting_absent(clean_claim(magnitudes={})) is False
    assert netting_absent(None) is False
    # ...and the clean fixture is genuinely provable (no vacuous block).
    assert netting_absent(clean_claim()) is True


@given(old=FINITE_NON_NEGATIVE, new=FINITE_NON_NEGATIVE, both=FINITE_NON_NEGATIVE)
def test_zero_is_a_legitimate_non_negative_magnitude(
    old: Decimal, new: Decimal, both: Decimal
) -> None:
    """(passing side) Non-negative includes zero — a zero remaining quantity is *known*.

    ``None`` means UNKNOWN and fails closed; ``0`` means "known to be zero" and is a
    perfectly good reservation slot. Conflating the two would be a vacuous block.
    """
    claim = clean_claim(
        magnitudes=clean_magnitudes(
            OLD_ORDER_REMAINING_EXECUTABLE=old,
            NEW_ORDER_REMAINING_EXECUTABLE=new,
            SIMULTANEOUS_OLD_AND_NEW_FILLS=both,
        )
    )
    assert netting_absent(claim) is True


def test_no_netting_cannot_be_forged_by_an_extra_field() -> None:
    """(anti-forgery) There is no ``netting_applied`` flag to set — the v1.0 fail-open.

    ``extra="forbid"`` means a caller cannot smuggle one in either, so the only way to
    make ``netting_absent`` true is to actually supply the three coexisting magnitudes.
    """
    assert "netting_applied" not in OverlapReservationClaim.model_fields
    try:
        OverlapReservationClaim(netting_applied=True)  # type: ignore[call-arg]
    except Exception:  # noqa: BLE001 — pydantic ValidationError; the point is rejection
        pass
    else:  # pragma: no cover - only reached if the seal regressed
        raise AssertionError("a forged netting flag was accepted")


# ===========================================================================
# (i) reservation completeness — required ⊆ reserved
# ===========================================================================


@given(reserved=OUTCOME_SETS)
def test_completeness_holds_iff_every_required_outcome_is_reserved(
    reserved: frozenset[CredibleIntermediateOutcomeKind],
) -> None:
    """(§9 line 233-243) Completeness ⇔ ``required <= reserved``; a gap is ``False``."""
    claim = clean_claim(reserved_outcome_kinds=reserved)
    result = overlap_first_reservation_complete(
        claim, ALL_OUTCOMES, within_hard_envelope=True
    )
    assert result is (reserved >= ALL_OUTCOMES)


@given(missing=st.sampled_from(list(CredibleIntermediateOutcomeKind)))
def test_dropping_any_single_outcome_makes_the_reservation_incomplete(
    missing: CredibleIntermediateOutcomeKind,
) -> None:
    """(guard fires, all 9) Each of the nine outcomes is individually load-bearing."""
    claim = clean_claim(reserved_outcome_kinds=ALL_OUTCOMES - {missing})
    assert (
        overlap_first_reservation_complete(
            claim, ALL_OUTCOMES, within_hard_envelope=True
        )
        is False
    )


def test_a_genuinely_complete_reservation_passes() -> None:
    """(passing side) The clean fixture is admissible — no vacuous block."""
    assert (
        overlap_first_reservation_complete(
            clean_claim(), ALL_OUTCOMES, within_hard_envelope=True
        )
        is True
    )


@given(envelope=TRIBOOL)
def test_hard_envelope_verdict_is_positive_polarity(envelope: bool | None) -> None:
    """(§5.1 reversal-bounded) Only ``within_hard_envelope is True`` passes; ``None`` denies."""
    result = overlap_first_reservation_complete(
        clean_claim(), ALL_OUTCOMES, within_hard_envelope=envelope
    )
    assert result is (envelope is True)


@given(forged=st.sampled_from(TRUTHY_NON_BOOL))
def test_a_truthy_non_bool_envelope_verdict_never_passes(forged: object) -> None:
    """(polarity) ``1`` / ``"UNKNOWN"`` / ``[1]`` are truthy but are not ``True``."""
    assert (
        overlap_first_reservation_complete(
            clean_claim(),
            ALL_OUTCOMES,
            within_hard_envelope=forged,  # type: ignore[arg-type]
        )
        is False
    )


def test_completeness_requires_a_claim_and_a_non_empty_required_universe() -> None:
    """(∅ both ways) No claim / an empty required universe cannot certify completeness."""
    assert (
        overlap_first_reservation_complete(
            None, ALL_OUTCOMES, within_hard_envelope=True
        )
        is False
    )
    assert (
        overlap_first_reservation_complete(
            clean_claim(), frozenset(), within_hard_envelope=True
        )
        is False
    ), "an empty required universe would certify completeness vacuously"


# ===========================================================================
# (iii) sequencing — the 4-input truth table (v1.1 C2 + M1)
# ===========================================================================


@given(
    sufficiency=TRIBOOL,
    classification=TRIBOOL,
    arbiter=TRIBOOL,
    leg=TRIBOOL,
)
def test_sequencing_is_the_conjunction_of_four_positive_conjuncts(
    sufficiency: bool | None,
    classification: bool | None,
    arbiter: bool | None,
    leg: bool | None,
) -> None:
    """(§6.2 line 159, C2/M1) All four ``is True`` — the full 3^4 tri-bool table.

    ``new_protection_sufficiency_current`` (§10 per-field proof) and
    ``protective_classification_present`` (aggregate-risk axis) are **separate**
    conjuncts: the v1.1 C2 correction of a v1.0 category error in which the latter was
    used to source the former.
    """
    result = overlap_first_sequencing_valid(
        new_protection_sufficiency_current=sufficiency,
        protective_classification_present=classification,
        cancellation_admissible=arbiter,
        leg_admissibility=leg,
    )
    assert result is (
        sufficiency is True
        and classification is True
        and arbiter is True
        and leg is True
    )


@given(
    conjunct=st.sampled_from(
        [
            "new_protection_sufficiency_current",
            "protective_classification_present",
            "cancellation_admissible",
            "leg_admissibility",
        ]
    ),
    broken=st.sampled_from([False, None]),
)
def test_cancel_before_proven_canary_each_conjunct_alone_blocks_the_cancel(
    conjunct: str, broken: bool | None
) -> None:
    """(named canary: cancel-old-before-new-proven) Causal isolation, one input flipped."""
    inputs = clean_sequencing_inputs(**{conjunct: broken})
    assert overlap_first_sequencing_valid(**inputs) is False
    # ...and restoring only that one input restores the pass (no vacuous block).
    assert overlap_first_sequencing_valid(**clean_sequencing_inputs()) is True


@given(forged=st.sampled_from(TRUTHY_NON_BOOL))
def test_ack_as_effective_protection_canary_a_truthy_sufficiency_never_passes(
    forged: object,
) -> None:
    """(named canary: ACK-as-effective-protection, §1 line 34 / §4.6a).

    "A new protective order does not count as effective protection merely because a
    request was emitted or transport ACK was received." A producer that stuffs a truthy
    token (an ACK payload, a ``1``, a non-empty list) into the sufficiency slot must not
    be able to cancel the old order.
    """
    inputs = clean_sequencing_inputs(new_protection_sufficiency_current=forged)
    assert overlap_first_sequencing_valid(**inputs) is False


def test_sufficiency_and_classification_are_not_interchangeable() -> None:
    """(C2 regression) An aggregate-risk classification cannot stand in for a field proof.

    v1.0 sourced the §10 per-field Protection Sufficiency Proof from protective's
    aggregate-risk ``protective_classification_present``. If they were interchangeable,
    proving only one of them would suffice — this asserts it does not.
    """
    only_classification = clean_sequencing_inputs(
        new_protection_sufficiency_current=None
    )
    only_sufficiency = clean_sequencing_inputs(protective_classification_present=None)
    assert overlap_first_sequencing_valid(**only_classification) is False
    assert overlap_first_sequencing_valid(**only_sufficiency) is False


# ===========================================================================
# Outcome resolution — ∅ ⇒ UNKNOWN, leg ⇒ TRAPPED, positive ⇒ ADMISSIBLE
# ===========================================================================


def test_empty_required_universe_resolves_to_unknown_not_to_admissible() -> None:
    """(§4.7 row 1) ∅ outcomes ⇒ conservatively ``REPLACEMENT_UNKNOWN`` (§9 line 231)."""
    assert (
        overlap_first_reservation_outcome(
            clean_claim(),
            frozenset(),
            within_hard_envelope=True,
            leg_admissibility=True,
        )
        is ReplacementOutcome.REPLACEMENT_UNKNOWN
    )


def test_absent_or_empty_claim_resolves_to_unknown() -> None:
    """(§4.7 row 1) No claim / an empty reservation cannot bound the state space."""
    for claim in (None, clean_claim(reserved_outcome_kinds=frozenset())):
        assert (
            overlap_first_reservation_outcome(
                claim,
                ALL_OUTCOMES,
                within_hard_envelope=True,
                leg_admissibility=True,
            )
            is ReplacementOutcome.REPLACEMENT_UNKNOWN
        )


@given(leg=st.sampled_from([False, None]))
def test_a_leg_without_current_admissibility_is_trapped(leg: bool | None) -> None:
    """(§4.7 row 9 / §5 line 139 (B)) Missing -019 admissibility ⇒ ``REPLACEMENT_TRAPPED``."""
    assert (
        overlap_first_reservation_outcome(
            clean_claim(),
            ALL_OUTCOMES,
            within_hard_envelope=True,
            leg_admissibility=leg,
        )
        is ReplacementOutcome.REPLACEMENT_TRAPPED
    )


def test_a_complete_reservation_with_an_admissible_leg_is_admissible() -> None:
    """(passing side, PR-AC-001) The genuinely clean case reaches ADMISSIBLE."""
    assert (
        overlap_first_reservation_outcome(
            clean_claim(),
            ALL_OUTCOMES,
            within_hard_envelope=True,
            leg_admissibility=True,
        )
        is ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    )


@given(reserved=OUTCOME_SETS, envelope=TRIBOOL, leg=TRIBOOL)
def test_admissible_is_never_the_residual_branch(
    reserved: frozenset[CredibleIntermediateOutcomeKind],
    envelope: bool | None,
    leg: bool | None,
) -> None:
    """(#16 CRITICAL) ADMISSIBLE only when the positive conjunction genuinely holds."""
    claim = clean_claim(reserved_outcome_kinds=reserved)
    outcome = overlap_first_reservation_outcome(
        claim, ALL_OUTCOMES, within_hard_envelope=envelope, leg_admissibility=leg
    )
    if outcome is ReplacementOutcome.REPLACEMENT_ADMISSIBLE:
        assert reserved >= ALL_OUTCOMES
        assert envelope is True
        assert leg is True
        assert netting_absent(claim) is True


# ===========================================================================
# reversal-bounded comparison (§4.7 row 5 — ``None`` magnitude ⇒ UNKNOWN)
# ===========================================================================


@given(
    risk=st.one_of(st.none(), FINITE_NON_NEGATIVE),
    limit=st.one_of(st.none(), FINITE_NON_NEGATIVE),
)
def test_a_none_magnitude_or_limit_propagates_unknown(
    risk: Decimal | None, limit: Decimal | None
) -> None:
    """(§4.7 row 5) ``None`` ⇒ ``REPLACEMENT_UNKNOWN`` — rcl propagates ``None`` likewise."""
    outcome = reversal_bounded_outcome(
        aggregate_risk_magnitude=risk,
        hard_envelope_limit=limit,
        within_hard_envelope=True,
    )
    if risk is None or limit is None:
        assert outcome is ReplacementOutcome.REPLACEMENT_UNKNOWN
    else:
        assert outcome is not ReplacementOutcome.REPLACEMENT_UNKNOWN


def test_reversal_bounded_both_ways() -> None:
    """(both ways) Over the envelope denies; under it with a positive verdict admits."""
    assert (
        reversal_bounded_outcome(
            aggregate_risk_magnitude=Decimal("101"),
            hard_envelope_limit=Decimal("100"),
            within_hard_envelope=True,
        )
        is ReplacementOutcome.REPLACEMENT_DENIED
    )
    assert (
        reversal_bounded_outcome(
            aggregate_risk_magnitude=Decimal("12"),
            hard_envelope_limit=Decimal("100"),
            within_hard_envelope=True,
        )
        is ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    )
    # An unproven rcl verdict denies even when the numbers look fine.
    assert (
        reversal_bounded_outcome(
            aggregate_risk_magnitude=Decimal("12"),
            hard_envelope_limit=Decimal("100"),
            within_hard_envelope=None,
        )
        is ReplacementOutcome.REPLACEMENT_DENIED
    )


def test_a_nan_or_infinite_magnitude_is_unknown_not_a_comparison() -> None:
    """(§3.1 reachable guard) NaN / infinity in the comparison ⇒ ``REPLACEMENT_UNKNOWN``.

    ``CanonicalDecimal`` makes a NaN / infinity **unconstructable inside a model**, so the
    equivalent guard in :func:`netting_absent` is unreachable defence-in-depth. This one is
    **not**: ``reversal_bounded_outcome`` takes bare injected magnitudes, so a caller (or a
    non-model producer such as an rcl aggregate that a future runtime forwards directly)
    can hand it a NaN. NaN breaks the comparison contract outright — ``NaN <= x`` is
    ``False`` for every ``x``, which would silently read as "over the envelope" in one
    direction and could read as "within" if the operands were reordered. It must be
    UNKNOWN, never a comparison result.
    """
    for bad in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")):
        assert (
            reversal_bounded_outcome(
                aggregate_risk_magnitude=bad,
                hard_envelope_limit=Decimal("100"),
                within_hard_envelope=True,
            )
            is ReplacementOutcome.REPLACEMENT_UNKNOWN
        ), f"aggregate risk {bad} must be UNKNOWN, not a comparison"
        assert (
            reversal_bounded_outcome(
                aggregate_risk_magnitude=Decimal("12"),
                hard_envelope_limit=bad,
                within_hard_envelope=True,
            )
            is ReplacementOutcome.REPLACEMENT_UNKNOWN
        ), f"envelope limit {bad} must be UNKNOWN, not a comparison"
    # Causal isolation: with both operands finite the comparison is performed again.
    assert (
        reversal_bounded_outcome(
            aggregate_risk_magnitude=Decimal("12"),
            hard_envelope_limit=Decimal("100"),
            within_hard_envelope=True,
        )
        is ReplacementOutcome.REPLACEMENT_ADMISSIBLE
    )
