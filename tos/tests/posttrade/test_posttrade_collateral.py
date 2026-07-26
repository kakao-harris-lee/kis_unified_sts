"""§5.4 collateral conservation, margin-state non-implication, cash-kind identity (PTF-EV-004).

§15 line 386 names three prohibitions and each is exercised in **both** directions:

1. the same unit counted as both free and encumbered;
2. the same unit pledged to two obligations;
3. the same unit reused before a confirmed release.

Plus the conservation sum (pledged <= available), the ∅ guard on an empty allocation
sequence, the §15 line 385 eight-state non-implication over the **full 8x8 matrix**, and the
PTF-INV-010 six-kind cash identity over the **full 6x6 matrix** — every non-identity pair
``False`` in both directions.

[PTF-EV-004 coordinate; ``/2``, ``/3``, and ``+Broker`` remain open. PTF-EV-003 cash
**availability proof** is deferred to ``EV-L2/3``. Closing PTF-EV = 0.]
"""

from __future__ import annotations

import itertools
from decimal import Decimal

import pytest
from hypothesis import given
from tos.posttrade import (
    CashKind,
    CollateralAllocation,
    MarginCollateralState,
    cash_kind_matches_requirement,
    collateral_no_double_use,
    margin_collateral_states_distinct,
)

from ._posttrade_strategies import CASH_KINDS, MARGIN_STATES, clean_allocation

# --- §15 line 386 collateral_no_double_use -----------------------------------


def test_a_free_unit_ladder_is_conserved() -> None:
    """(positive side) Distinct free units, nothing pledged ⇒ conserved."""
    ladder = [clean_allocation("UNIT-1"), clean_allocation("UNIT-2")]
    assert collateral_no_double_use(ladder) is True


def test_an_encumbered_unit_pledged_to_one_obligation_is_conserved() -> None:
    """(positive side) Exactly one obligation, pledged within the available magnitude."""
    assert (
        collateral_no_double_use([clean_allocation("UNIT-1", encumbered=True)]) is True
    )


def test_empty_allocation_sequence_is_false_not_vacuously_true() -> None:
    """(∅ guard) "No collateral examined" never reads as "no double use"."""
    assert collateral_no_double_use([]) is False


def test_prohibition_one_free_and_encumbered_at_once() -> None:
    """(§15 line 386) "SHALL NOT be counted as both free and encumbered"."""
    both = clean_allocation(
        "UNIT-1",
        encumbered=True,
        free_magnitude=Decimal("5.00"),
    )
    assert collateral_no_double_use([both]) is False


def test_a_unit_that_is_neither_free_nor_encumbered_is_unaccounted() -> None:
    """(∅ within a unit) Both magnitudes zero ⇒ no provable allocation state."""
    unaccounted = clean_allocation(
        "UNIT-1",
        free_magnitude=Decimal("0"),
        encumbered_magnitude=Decimal("0"),
    )
    assert collateral_no_double_use([unaccounted]) is False


def test_prohibition_two_pledged_to_two_obligations() -> None:
    """(§15 line 386) "SHALL NOT be ... pledged to two obligations"."""
    double_pledged = clean_allocation(
        "UNIT-1", encumbered=True, pledged_obligation_ids=("OBL-1", "OBL-2")
    )
    assert collateral_no_double_use([double_pledged]) is False


def test_an_encumbered_unit_must_name_exactly_one_obligation() -> None:
    """(§15 line 386) An anonymous encumbrance cannot be shown to be single-use."""
    anonymous = clean_allocation("UNIT-1", encumbered=True, pledged_obligation_ids=())
    assert collateral_no_double_use([anonymous]) is False


def test_a_free_unit_must_pledge_nothing() -> None:
    """(§15 line 386) A pledge implies an encumbrance; a free unit carrying one is a
    double count in the other direction."""
    contradictory = clean_allocation(
        "UNIT-1", pledged_obligation_ids=("OBL-1",), pledged_magnitude=Decimal("1.00")
    )
    assert collateral_no_double_use([contradictory]) is False


def test_prohibition_three_reuse_before_confirmed_release() -> None:
    """(§15 line 386) "SHALL NOT be ... reusable before confirmed release"."""
    pledged = clean_allocation("UNIT-1", encumbered=True)
    reused = clean_allocation("UNIT-1", encumbered=True)
    assert collateral_no_double_use([pledged, reused]) is False


def test_reuse_after_a_positively_declared_confirmed_release_is_permitted() -> None:
    """(positive side) ``CONFIRMED_RELEASE`` is the positive premise that permits reuse."""
    released = clean_allocation(
        "UNIT-1", encumbered=True, release_state=MarginCollateralState.CONFIRMED_RELEASE
    )
    reused = clean_allocation("UNIT-1", encumbered=True)
    assert collateral_no_double_use([released, reused]) is True


@pytest.mark.parametrize(
    "state",
    [
        member
        for member in MarginCollateralState
        if member is not MarginCollateralState.CONFIRMED_RELEASE
    ],
)
def test_no_other_margin_state_permits_reuse(state: MarginCollateralState) -> None:
    """(§15 line 385) The other seven states do **not** imply a confirmed release."""
    pledged = clean_allocation("UNIT-1", encumbered=True, release_state=state)
    reused = clean_allocation("UNIT-1", encumbered=True)
    assert collateral_no_double_use([pledged, reused]) is False


def test_a_second_release_is_required_for_a_second_reuse() -> None:
    """(§15 line 386) One confirmed release permits one reuse, not an open licence."""
    released = clean_allocation(
        "UNIT-1", encumbered=True, release_state=MarginCollateralState.CONFIRMED_RELEASE
    )
    reused = clean_allocation("UNIT-1", encumbered=True)
    reused_again = clean_allocation("UNIT-1", encumbered=True)
    assert collateral_no_double_use([released, reused, reused_again]) is False


def test_conservation_sum_rejects_over_pledging() -> None:
    """(§15 line 386) The pledged magnitude must stay within the available magnitude."""
    over = clean_allocation(
        "UNIT-1",
        encumbered=True,
        pledged_magnitude=Decimal("20.00"),
        available_magnitude=Decimal("10.00"),
    )
    assert collateral_no_double_use([over]) is False


def test_pledging_exactly_the_available_magnitude_is_permitted() -> None:
    """(boundary, positive side) Equality is conservation, not a violation."""
    exact = clean_allocation(
        "UNIT-1",
        encumbered=True,
        pledged_magnitude=Decimal("10.00"),
        available_magnitude=Decimal("10.00"),
    )
    assert collateral_no_double_use([exact]) is True


@pytest.mark.parametrize(
    "field",
    [
        "free_magnitude",
        "encumbered_magnitude",
        "pledged_magnitude",
        "available_magnitude",
    ],
)
def test_an_unknown_magnitude_makes_conservation_unprovable(field: str) -> None:
    """(fail-closed) ``None`` is UNKNOWN — a conservation sum cannot be taken over it."""
    incomplete = clean_allocation("UNIT-1", encumbered=True, **{field: None})
    assert collateral_no_double_use([incomplete]) is False


@pytest.mark.parametrize("field", ["free_magnitude", "available_magnitude"])
def test_a_negative_magnitude_is_a_sign_error(field: str) -> None:
    """(gross axis) A collateral magnitude carries no sign."""
    signed = clean_allocation("UNIT-1", **{field: Decimal("-1.00")})
    assert collateral_no_double_use([signed]) is False


@pytest.mark.parametrize("unit_id", [None, ""])
def test_an_unidentified_unit_is_rejected(unit_id: str | None) -> None:
    """(structural) The reuse check groups on identity — an anonymous unit would evade it."""
    anonymous = CollateralAllocation(
        unit_id=unit_id,
        free_magnitude=Decimal("1.00"),
        encumbered_magnitude=Decimal("0"),
        pledged_magnitude=Decimal("0"),
        available_magnitude=Decimal("1.00"),
    )
    assert collateral_no_double_use([anonymous]) is False


def test_one_bad_allocation_condemns_the_whole_ladder() -> None:
    """(conservation) Conservation is a property of the set, not of the average member."""
    ladder = [
        clean_allocation("UNIT-1"),
        clean_allocation("UNIT-2", encumbered=True, free_magnitude=Decimal("5.00")),
        clean_allocation("UNIT-3"),
    ]
    assert collateral_no_double_use(ladder) is False


# --- §15 line 385 margin_collateral_states_distinct --------------------------


@pytest.mark.parametrize("state", list(MarginCollateralState))
def test_a_state_supports_only_the_claim_that_is_itself(
    state: MarginCollateralState,
) -> None:
    """(positive side) Claiming exactly what was observed performs no implication."""
    assert margin_collateral_states_distinct(state, state) is True


@pytest.mark.parametrize(
    ("observed", "claimed"),
    [
        pair
        for pair in itertools.product(MarginCollateralState, repeat=2)
        if pair[0] is not pair[1]
    ],
)
def test_no_state_implies_another_over_the_full_matrix(
    observed: MarginCollateralState, claimed: MarginCollateralState
) -> None:
    """(§15 line 385) "No one state implies another" — all 56 non-identity cells."""
    assert margin_collateral_states_distinct(observed, claimed) is False


def test_the_matrix_covers_all_sixty_four_cells() -> None:
    """(count cross-check) 8 identity cells + 56 non-identity cells = 8x8."""
    identity = sum(
        1
        for observed, claimed in itertools.product(MarginCollateralState, repeat=2)
        if observed is claimed
    )
    total = len(list(itertools.product(MarginCollateralState, repeat=2)))
    assert identity == 8
    assert total == 64


@pytest.mark.parametrize("state", list(MarginCollateralState))
def test_an_undeclared_state_supports_no_claim(state: MarginCollateralState) -> None:
    """(∅ guard) ``None`` on either side fails closed — and two ``None`` do **not** match."""
    assert margin_collateral_states_distinct(None, state) is False
    assert margin_collateral_states_distinct(state, None) is False
    assert margin_collateral_states_distinct(None, None) is False


@given(observed=MARGIN_STATES, claimed=MARGIN_STATES)
def test_margin_state_verdict_is_exactly_identity(
    observed: MarginCollateralState, claimed: MarginCollateralState
) -> None:
    """(§4.8 row 17) The verdict is the identity, over arbitrary pairs."""
    assert margin_collateral_states_distinct(observed, claimed) is (observed is claimed)


@pytest.mark.parametrize("state", list(MarginCollateralState))
def test_a_raw_string_margin_state_is_not_the_member(
    state: MarginCollateralState,
) -> None:
    """(review MINOR-4) The ``is`` hardening is locked: a bare token satisfies nothing.

    ``MarginCollateralState`` is a ``StrEnum``, so ``observed == claimed`` would accept a raw
    ``"PLEDGED_COLLATERAL"`` string as the member it names. The predicate uses ``is``, so a
    caller who lost the type on the way through a serialization boundary fails closed instead
    of quietly re-acquiring the claim.
    """
    raw = "".join(state.value)  # a distinct str object, never the interned member
    assert raw == state  # StrEnum equality — what an `==` gate would have accepted
    assert raw is not state
    assert margin_collateral_states_distinct(raw, state) is False  # type: ignore[arg-type]
    assert margin_collateral_states_distinct(state, raw) is False  # type: ignore[arg-type]
    # An untyped value on *both* sides degenerates to plain string identity, which returns
    # the correct answer for free (equal kinds ⇒ True, different kinds ⇒ False) and is
    # therefore not a hole; the hole an `==` gate would open is the mixed pair above, where
    # a lost type would silently re-acquire the member's claim.


# --- PTF-INV-010 cash_kind_matches_requirement -------------------------------


@pytest.mark.parametrize("kind", list(CashKind))
def test_a_cash_kind_satisfies_only_itself(kind: CashKind) -> None:
    """(positive side) The requirement is met when the available kind *is* the requested."""
    assert cash_kind_matches_requirement(kind, kind) is True


@pytest.mark.parametrize(
    ("requested", "available"),
    [pair for pair in itertools.product(CashKind, repeat=2) if pair[0] is not pair[1]],
)
def test_every_non_identity_pair_is_a_substitution(
    requested: CashKind, available: CashKind
) -> None:
    """(PTF-INV-010) All 30 non-identity cells, in both directions — no "close enough"."""
    assert cash_kind_matches_requirement(requested, available) is False


def test_buying_power_is_not_withdrawable_cash() -> None:
    """(§25.4) The rejected alternative, named explicitly, in both directions."""
    assert (
        cash_kind_matches_requirement(CashKind.WITHDRAWABLE_CASH, CashKind.BUYING_POWER)
        is False
    )
    assert (
        cash_kind_matches_requirement(CashKind.BUYING_POWER, CashKind.WITHDRAWABLE_CASH)
        is False
    )


def test_pending_cash_is_not_settled_cash() -> None:
    """(§14 line 375) Pending proceeds are not settled reusable cash."""
    assert (
        cash_kind_matches_requirement(CashKind.SETTLED_CASH, CashKind.PENDING_CASH)
        is False
    )


@pytest.mark.parametrize("kind", list(CashKind))
def test_an_undeclared_cash_kind_satisfies_nothing(kind: CashKind) -> None:
    """(∅ guard) ``None`` fails closed — and two ``None`` do **not** satisfy the identity."""
    assert cash_kind_matches_requirement(None, kind) is False
    assert cash_kind_matches_requirement(kind, None) is False
    assert cash_kind_matches_requirement(None, None) is False


@given(requested=CASH_KINDS, available=CASH_KINDS)
def test_cash_kind_verdict_is_exactly_identity(
    requested: CashKind, available: CashKind
) -> None:
    """(§4.8 row 18) The verdict is the identity, over arbitrary pairs."""
    assert cash_kind_matches_requirement(requested, available) is (
        requested is available
    )


@pytest.mark.parametrize("kind", list(CashKind))
def test_a_raw_string_cash_kind_is_not_the_member(kind: CashKind) -> None:
    """(review MINOR-4) The ``is`` hardening is locked: a bare token satisfies nothing.

    ``CashKind`` is a ``StrEnum``, so ``requested == available`` would let a raw
    ``"WITHDRAWABLE_CASH"`` string satisfy the requirement it names — the substitution
    PTF-INV-010 forbids, arriving through a lost type rather than through a wrong kind. The
    predicate uses ``is``, so the untyped value fails closed.
    """
    raw = "".join(kind.value)  # a distinct str object, never the interned member
    assert raw == kind  # StrEnum equality — what an `==` gate would have accepted
    assert raw is not kind
    assert cash_kind_matches_requirement(raw, kind) is False  # type: ignore[arg-type]
    assert cash_kind_matches_requirement(kind, raw) is False  # type: ignore[arg-type]
    # As above: two untyped values degenerate to string identity and stay correct; the mixed
    # pair is the one an `==` gate would have waved through.
