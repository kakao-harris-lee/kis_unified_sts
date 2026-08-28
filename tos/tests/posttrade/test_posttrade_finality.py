"""§5.1 finality-dimension orthogonality + obligation-leg set completeness (PTF-EV-001).

The property IMPLEMENTATION-PLAN-002 line 221 names explicitly. Both directions of every
guard (design #24 §4.1 / §5.1 canaries):

* **guard fires** — an ``ORDER_FQP``-only proof map makes none of the other nine dimensions
  final; an empty map or an absent claim is ``False``; a ``None`` / ``False`` / truthy
  non-``bool`` entry is not proof;
* **legitimate pass** — a dimension carrying its own proof is final, and proving it changes
  **nothing** about any other dimension.

Non-implication is asserted structurally as well as behaviourally: the verdict for a claimed
dimension is invariant under **every** rearrangement of the other nine entries, which is only
possible if the function never reads them.

[PTF-EV-001 coordinate; ``/2``, ``/3``, and ``+Broker`` remain open. Closing PTF-EV = 0.]
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from tos.posttrade import (
    FQP_DOES_NOT_PROVE,
    FinalityDimensionKind,
    ObligationLegDirection,
    finality_dimensions_orthogonal,
    obligation_leg_set_complete,
)

from ._posttrade_strategies import (
    FINALITY_DIMENSIONS,
    LEG_DIRECTION_SETS,
    MAGNITUDE_SLOT,
    PROOF_MAPS,
    proof_map_only,
)

_ALL_DIMENSIONS = list(FinalityDimensionKind)


# --- §5.1 finality_dimensions_orthogonal -------------------------------------


@pytest.mark.parametrize("dimension", _ALL_DIMENSIONS)
def test_a_dimension_with_its_own_proof_is_final(
    dimension: FinalityDimensionKind,
) -> None:
    """(positive side) Each of the ten dimensions is final on its own proof — and only it."""
    proof_map = proof_map_only(dimension)
    assert finality_dimensions_orthogonal(dimension, proof_map) is True
    for other in _ALL_DIMENSIONS:
        if other is dimension:
            continue
        assert finality_dimensions_orthogonal(other, proof_map) is False


def test_order_fqp_proves_none_of_the_six_things_section_12_lists() -> None:
    """(§12 line 340-345 / §1 line 23) An FQP-only map leaves all six items unproven.

    "Final Quantity Proof establishes only final cumulative filled quantity and zero
    remaining executable quantity ... It does not prove any post-trade obligation final."
    """
    fqp_only = proof_map_only(FinalityDimensionKind.ORDER_FQP)
    assert (
        finality_dimensions_orthogonal(FinalityDimensionKind.ORDER_FQP, fqp_only)
        is True
    )
    for anchor, description, dimension in FQP_DOES_NOT_PROVE:
        assert (
            finality_dimensions_orthogonal(dimension, fqp_only) is False
        ), f"§12 line {anchor} ({description}) was implied by ORDER_FQP"


@given(claimed=FINALITY_DIMENSIONS, proof_map=PROOF_MAPS)
def test_verdict_is_exactly_the_claimed_entry_being_true(
    claimed: FinalityDimensionKind, proof_map: dict[FinalityDimensionKind, bool | None]
) -> None:
    """(§5.1 M1) The single-sentence proposition, over arbitrary maps."""
    expected = bool(proof_map) and proof_map.get(claimed) is True
    assert finality_dimensions_orthogonal(claimed, proof_map) is expected


@given(
    claimed=FINALITY_DIMENSIONS,
    claimed_proof=st.sampled_from([True, False, None]),
    others=st.dictionaries(
        FINALITY_DIMENSIONS, st.sampled_from([True, False, None]), max_size=10
    ),
)
def test_other_dimensions_cannot_influence_the_verdict(
    claimed: FinalityDimensionKind,
    claimed_proof: bool | None,
    others: dict[FinalityDimensionKind, bool | None],
) -> None:
    """(PTF-INV-002 structural) Rearranging the other nine entries changes nothing.

    This is the non-implication proof: if any other dimension's proof could reach the
    verdict, some rearrangement would flip it.
    """
    proof_map = {**others, claimed: claimed_proof}
    baseline = finality_dimensions_orthogonal(claimed, proof_map)
    all_others_true = dict.fromkeys(FinalityDimensionKind, True)
    all_others_true[claimed] = claimed_proof
    all_others_false = dict.fromkeys(FinalityDimensionKind, False)
    all_others_false[claimed] = claimed_proof
    assert finality_dimensions_orthogonal(claimed, all_others_true) is baseline
    assert finality_dimensions_orthogonal(claimed, all_others_false) is baseline


def test_empty_proof_map_is_false_not_vacuously_true() -> None:
    """(∅ guard, §4.8 row 2) "No dimension has any proof" never reads as "the claim holds"."""
    assert finality_dimensions_orthogonal(FinalityDimensionKind.SETTLEMENT, {}) is False


def test_absent_claim_is_false() -> None:
    """(∅ guard) Nothing claimed, nothing proven — even with a fully proven map."""
    assert (
        finality_dimensions_orthogonal(None, dict.fromkeys(FinalityDimensionKind, True))
        is False
    )


@pytest.mark.parametrize("forged", [1, "yes", [1], "True", 0, "", []])
def test_a_truthy_or_falsy_non_bool_entry_is_not_proof(forged: object) -> None:
    """(polarity) The entry is gated ``is True`` — a forged value is not proof either way."""
    proof_map = {FinalityDimensionKind.SETTLEMENT: forged}
    assert (
        finality_dimensions_orthogonal(FinalityDimensionKind.SETTLEMENT, proof_map)  # type: ignore[arg-type]
        is False
    )


def test_all_unknown_map_proves_nothing() -> None:
    """(PTF-INV-006) UNKNOWN is the default; a map of ``None`` proves no dimension."""
    unknown_map: dict[FinalityDimensionKind, bool | None] = dict.fromkeys(
        FinalityDimensionKind
    )
    for member in FinalityDimensionKind:
        assert finality_dimensions_orthogonal(member, unknown_map) is False


# --- §5.1 obligation_leg_set_complete ----------------------------------------


def test_complete_leg_set_passes() -> None:
    """(positive side) Required ⊆ present with concrete magnitudes ⇒ complete."""
    required = frozenset({ObligationLegDirection.DEBIT, ObligationLegDirection.CREDIT})
    present = frozenset(ObligationLegDirection)
    magnitudes = {member: Decimal("1.00") for member in ObligationLegDirection}
    assert obligation_leg_set_complete(required, present, magnitudes) is True


def test_empty_required_set_is_false_not_vacuously_true() -> None:
    """(∅ guard, §4.8 row 1; the #21 C1 lesson) ``∅ <= present`` must not certify anything."""
    magnitudes = {member: Decimal("1.00") for member in ObligationLegDirection}
    assert (
        obligation_leg_set_complete(
            frozenset(), frozenset(ObligationLegDirection), magnitudes
        )
        is False
    )


def test_missing_leg_is_incomplete() -> None:
    """(guard fires) A required leg absent from ``present`` ⇒ incomplete."""
    required = frozenset({ObligationLegDirection.DEBIT, ObligationLegDirection.CREDIT})
    present = frozenset({ObligationLegDirection.DEBIT})
    magnitudes = {member: Decimal("1.00") for member in ObligationLegDirection}
    assert obligation_leg_set_complete(required, present, magnitudes) is False


def test_present_leg_with_unknown_magnitude_is_incomplete() -> None:
    """(§13 line 355) An enumerated leg with a ``None`` magnitude proves no size."""
    required = frozenset({ObligationLegDirection.DEBIT})
    present = frozenset({ObligationLegDirection.DEBIT})
    assert (
        obligation_leg_set_complete(
            required, present, {ObligationLegDirection.DEBIT: None}
        )
        is False
    )


def test_negative_magnitude_is_a_sign_error() -> None:
    """(gross axis) A magnitude carries no sign — the direction does."""
    required = frozenset({ObligationLegDirection.DEBIT})
    present = frozenset({ObligationLegDirection.DEBIT})
    assert (
        obligation_leg_set_complete(
            required, present, {ObligationLegDirection.DEBIT: Decimal("-1.00")}
        )
        is False
    )


def test_zero_magnitude_is_accepted_as_a_declared_gross_value() -> None:
    """(positive side) A *declared* zero leg is concrete; an *absent* one is not.

    §13 line 355 distinguishes them precisely: "a missing line item **or zero estimate** is
    not proof of zero" governs the monetary-leg conservatism predicate, while set
    completeness asks only whether every applicable leg was enumerated with a concrete gross
    value.
    """
    required = frozenset({ObligationLegDirection.CONTINGENT})
    present = frozenset({ObligationLegDirection.CONTINGENT})
    assert (
        obligation_leg_set_complete(
            required, present, {ObligationLegDirection.CONTINGENT: Decimal("0")}
        )
        is True
    )


@given(
    required=LEG_DIRECTION_SETS,
    present=LEG_DIRECTION_SETS,
    magnitude=MAGNITUDE_SLOT,
)
def test_completeness_is_never_true_without_a_requirement(
    required: frozenset[ObligationLegDirection],
    present: frozenset[ObligationLegDirection],
    magnitude: Decimal | None,
) -> None:
    """(∅ / fail-closed) An empty requirement is never complete, whatever else holds."""
    magnitudes = dict.fromkeys(ObligationLegDirection, magnitude)
    verdict = obligation_leg_set_complete(required, present, magnitudes)
    if not required:
        assert verdict is False
    if verdict is True:
        assert required <= present
        assert magnitude is not None and magnitude >= 0
