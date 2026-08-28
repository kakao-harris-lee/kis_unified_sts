"""§5.3 no-favourable-default — absence, netting, and the missing counterleg (PTF-EV-002).

Truth table A of design #24 §4.5-A is exercised cell by cell (1 valid-netting cell, 3
gross / adverse cells), plus the §13 line 355 "a missing line item or zero estimate is not
proof of zero" rule and the §9 line 279 missing-counterleg rule. Both directions of every
guard:

* **guard fires** — a missing amount is UNKNOWN not zero; an unbooked zero is not a proven
  zero; a netting without both gross magnitudes, without one scope, or without an
  enforceable-netting proof leaves both legs gross; a missing, unproven, same-direction, or
  UNKNOWN-magnitude counterleg is adverse;
* **legitimate pass** — a positively booked zero from a corroborated source is a proven zero;
  two gross legs in one scope with a proof net; a positively established opposite counterleg
  balances.

[PTF-EV-002 coordinate; ``/2``, ``/3``, and ``+Broker`` remain open. Closing PTF-EV = 0.]
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given
from tos.posttrade import (
    ObligationLegDirection,
    missing_counterleg_is_adverse,
    monetary_leg_conservative,
    netting_requires_positive_proof,
)

from ._posttrade_strategies import (
    FORGED_FLAG,
    LEG_DIRECTIONS,
    MAGNITUDE_SLOT,
    TRIBOOL,
    clean_leg,
    clean_monetary_leg,
)

# --- §13 monetary_leg_conservative -------------------------------------------


def test_a_present_classified_amount_is_conservative() -> None:
    """(positive side) A present, finite, explicitly classified amount passes."""
    assert monetary_leg_conservative(clean_monetary_leg()) is True


def test_an_absent_leg_proves_nothing() -> None:
    """(§13 line 355) "A missing line item ... is not proof of zero"."""
    assert monetary_leg_conservative(None) is False


def test_an_absent_amount_is_unknown_not_zero() -> None:
    """(§13 line 355, §4.8 row 3) ``None`` is greatest-credible, never a favourable zero."""
    assert monetary_leg_conservative(clean_monetary_leg(amount=None)) is False


def test_an_unclassified_amount_is_rejected() -> None:
    """(§13 line 355) Estimated / accrued / broker-booked / legally-final must be explicit."""
    assert monetary_leg_conservative(clean_monetary_leg(amount_status=None)) is False
    assert monetary_leg_conservative(clean_monetary_leg(amount_status="")) is False


def test_a_negative_amount_is_a_sign_error() -> None:
    """(gross axis) A monetary magnitude carries no sign."""
    assert (
        monetary_leg_conservative(clean_monetary_leg(amount=Decimal("-1.00"))) is False
    )


def test_a_bare_zero_estimate_is_not_a_proven_zero() -> None:
    """(§13 line 355) "... or zero estimate is not proof of zero"."""
    assert (
        monetary_leg_conservative(
            clean_monetary_leg(amount=Decimal("0"), booked_zero=None)
        )
        is False
    )
    assert (
        monetary_leg_conservative(
            clean_monetary_leg(amount=Decimal("0"), booked_zero=False)
        )
        is False
    )


def test_a_booked_zero_from_a_corroborated_source_is_a_proven_zero() -> None:
    """(positive side) The one way a zero passes: positively booked **and** corroborated."""
    assert (
        monetary_leg_conservative(
            clean_monetary_leg(
                amount=Decimal("0"),
                booked_zero=True,
                source_confidence="CORROBORATED",
            )
        )
        is True
    )


@pytest.mark.parametrize(
    "confidence", ["UNKNOWN", "CONFLICTED", "SINGLE_SOURCE", "STALE", "", None]
)
def test_a_booked_zero_without_corroboration_is_not_proven(
    confidence: str | None,
) -> None:
    """(PTF-INV-005) Confidence is a **necessary input** to the zero proof, never optional.

    ``SINGLE_SOURCE`` and ``STALE`` are non-empty truthy strings and are **not** corroboration
    — a truthiness-based gate would have let them through.
    """
    assert (
        monetary_leg_conservative(
            clean_monetary_leg(
                amount=Decimal("0"), booked_zero=True, source_confidence=confidence
            )
        )
        is False
    )


def test_the_booked_zero_field_admits_no_non_boolean_forgery() -> None:
    """(polarity, model layer) ``booked_zero`` is a **field**, so the schema is the first gate.

    Unlike an injected function parameter, a model field is validated before the predicate
    ever sees it: a non-boolean token is rejected outright rather than silently read as
    truthy. The predicate's ``is True`` gate is then the second line of defence for values
    the schema does normalize.
    """
    with pytest.raises(ValueError, match="bool"):
        clean_monetary_leg(amount=Decimal("0"), booked_zero="definitely")
    with pytest.raises(ValueError, match="bool"):
        clean_monetary_leg(amount=Decimal("0"), booked_zero=[])


# --- §4.5-A truth table: netting_requires_positive_proof ---------------------


def _receivable(magnitude: Decimal | None = Decimal("5.00")) -> object:
    return clean_leg(ObligationLegDirection.CREDIT, magnitude)


def _payable(magnitude: Decimal | None = Decimal("3.00")) -> object:
    return clean_leg(ObligationLegDirection.DEBIT, magnitude)


def test_truth_table_a_row_1_both_gross_same_scope_with_proof_nets() -> None:
    """(row 1, valid cell) The **only** configuration in which a netting is valid."""
    assert (
        netting_requires_positive_proof(_receivable(), _payable(), True, True) is True
    )


def test_truth_table_a_row_2_missing_proof_leaves_both_gross() -> None:
    """(row 2, §25.5) An uncertain receivable does not fund a payable."""
    assert (
        netting_requires_positive_proof(_receivable(), _payable(), True, None) is False
    )
    assert (
        netting_requires_positive_proof(_receivable(), _payable(), True, False) is False
    )


def test_truth_table_a_row_3_different_scope_leaves_both_gross() -> None:
    """(row 3, §14 line 377) One scope is a premise, not a convenience."""
    assert (
        netting_requires_positive_proof(_receivable(), _payable(), None, True) is False
    )
    assert (
        netting_requires_positive_proof(_receivable(), _payable(), False, True) is False
    )


def test_truth_table_a_row_4_a_missing_leg_is_not_a_netting() -> None:
    """(row 4, §9 line 279) With one leg absent there is nothing to net against."""
    assert netting_requires_positive_proof(None, _payable(), True, True) is False
    assert netting_requires_positive_proof(_receivable(), None, True, True) is False


def test_an_unknown_magnitude_is_not_a_gross_leg() -> None:
    """(structural) The coexistence proof needs two **present** magnitudes."""
    assert (
        netting_requires_positive_proof(_receivable(None), _payable(), True, True)
        is False
    )
    assert (
        netting_requires_positive_proof(_receivable(), _payable(None), True, True)
        is False
    )


def test_a_negative_magnitude_is_not_a_gross_leg() -> None:
    """(gross axis) A netting cannot be manufactured by a negative magnitude."""
    assert (
        netting_requires_positive_proof(
            _receivable(Decimal("-5.00")), _payable(), True, True
        )
        is False
    )


@pytest.mark.parametrize(
    "direction",
    [
        member
        for member in ObligationLegDirection
        if member is not ObligationLegDirection.CREDIT
    ],
)
def test_only_a_credit_leg_can_be_the_receivable(
    direction: ObligationLegDirection,
) -> None:
    """(§2.2-3) The receivable slot is the ``CREDIT`` direction — identity, not a token."""
    assert (
        netting_requires_positive_proof(clean_leg(direction), _payable(), True, True)
        is False
    )


@pytest.mark.parametrize(
    "direction",
    [
        member
        for member in ObligationLegDirection
        if member is not ObligationLegDirection.DEBIT
    ],
)
def test_only_a_debit_leg_can_be_the_payable(direction: ObligationLegDirection) -> None:
    """(§2.2-3) The payable slot is the ``DEBIT`` direction."""
    assert (
        netting_requires_positive_proof(_receivable(), clean_leg(direction), True, True)
        is False
    )


@given(same_scope=FORGED_FLAG, proof=FORGED_FLAG)
def test_netting_needs_two_real_trues(same_scope: object, proof: object) -> None:
    """(polarity) Both premises are gated ``is True``; forged values pass neither."""
    verdict = netting_requires_positive_proof(
        _receivable(), _payable(), same_scope, proof  # type: ignore[arg-type]
    )
    assert verdict is (same_scope is True and proof is True)


# --- §9 line 279 missing_counterleg_is_adverse -------------------------------


def test_a_positively_established_opposite_counterleg_balances() -> None:
    """(positive side) The one way the adversity guard stands down."""
    assert (
        missing_counterleg_is_adverse(
            clean_leg(ObligationLegDirection.DEBIT),
            clean_leg(ObligationLegDirection.CREDIT),
            True,
        )
        is False
    )


def test_an_absent_counterleg_is_adverse() -> None:
    """(§9 line 279) "the missing counterleg remains explicit and the greatest credible
    adverse union is used"."""
    assert (
        missing_counterleg_is_adverse(
            clean_leg(ObligationLegDirection.DEBIT), None, True
        )
        is True
    )


def test_an_absent_declared_leg_is_adverse() -> None:
    """(fail-closed) Nothing declared ⇒ nothing balanced."""
    assert (
        missing_counterleg_is_adverse(
            None, clean_leg(ObligationLegDirection.CREDIT), True
        )
        is True
    )


@pytest.mark.parametrize("established", [False, None])
def test_an_unproven_counterleg_is_adverse(established: bool | None) -> None:
    """(polarity) Positive establishment is required; ``None`` is not establishment."""
    assert (
        missing_counterleg_is_adverse(
            clean_leg(ObligationLegDirection.DEBIT),
            clean_leg(ObligationLegDirection.CREDIT),
            established,
        )
        is True
    )


def test_a_same_direction_counterleg_is_not_a_balance() -> None:
    """(§4.5-A) Two legs pointing the same way are two exposures, not a balance."""
    assert (
        missing_counterleg_is_adverse(
            clean_leg(ObligationLegDirection.DEBIT),
            clean_leg(ObligationLegDirection.DEBIT),
            True,
        )
        is True
    )


@pytest.mark.parametrize(
    ("declared", "counter"),
    [
        (ObligationLegDirection.DEBIT, ObligationLegDirection.CREDIT),
        (ObligationLegDirection.CREDIT, ObligationLegDirection.DEBIT),
        (ObligationLegDirection.DELIVERY, ObligationLegDirection.RECEIPT),
        (ObligationLegDirection.RECEIPT, ObligationLegDirection.DELIVERY),
        (ObligationLegDirection.ENCUMBRANCE, ObligationLegDirection.RELEASE),
        (ObligationLegDirection.RELEASE, ObligationLegDirection.ENCUMBRANCE),
    ],
)
def test_all_three_opposite_pairs_balance_in_both_orders(
    declared: ObligationLegDirection, counter: ObligationLegDirection
) -> None:
    """(§4.5-A) DEBIT/CREDIT, DELIVERY/RECEIPT, ENCUMBRANCE/RELEASE, each way round."""
    assert (
        missing_counterleg_is_adverse(clean_leg(declared), clean_leg(counter), True)
        is False
    )


@pytest.mark.parametrize(
    "direction", [ObligationLegDirection.RETURN, ObligationLegDirection.CONTINGENT]
)
def test_directions_without_an_opposite_are_always_adverse(
    direction: ObligationLegDirection,
) -> None:
    """(§4.5-A) ``RETURN`` and ``CONTINGENT`` have no balancing counterpart."""
    for counter in ObligationLegDirection:
        assert (
            missing_counterleg_is_adverse(
                clean_leg(direction), clean_leg(counter), True
            )
            is True
        )


def test_an_unknown_counterleg_magnitude_is_adverse() -> None:
    """(§13 line 355) A counterleg with no magnitude establishes no balance."""
    assert (
        missing_counterleg_is_adverse(
            clean_leg(ObligationLegDirection.DEBIT),
            clean_leg(ObligationLegDirection.CREDIT, None),
            True,
        )
        is True
    )


@given(
    declared_direction=LEG_DIRECTIONS,
    counter_direction=LEG_DIRECTIONS,
    magnitude=MAGNITUDE_SLOT,
    established=TRIBOOL,
)
def test_adversity_is_the_default_direction(
    declared_direction: ObligationLegDirection,
    counter_direction: ObligationLegDirection,
    magnitude: Decimal | None,
    established: bool | None,
) -> None:
    """(fail-closed) A ``False`` (balanced) verdict implies the whole positive conjunction."""
    verdict = missing_counterleg_is_adverse(
        clean_leg(declared_direction),
        clean_leg(counter_direction, magnitude),
        established,
    )
    if verdict is False:
        assert established is True
        assert magnitude is not None and magnitude >= 0
        assert declared_direction is not counter_direction
