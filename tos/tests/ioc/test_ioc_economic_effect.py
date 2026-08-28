"""economic_effect_dominated + no_silent_widening (design #14 §5.5/§5.3; IOC-EV-006/004 substrate).

Committed-capacity dominance over the ``EconomicEffectEnvelope`` (rcl ``CapacityVector``), with
∅ both-ways (empty envelope / empty committed), the None-magnitude fail-closed, and the
forbidden-verb canaries (reduce / shrink — §13 line 343; widen / narrow — §11 line 303). Consume
gate is ``is True`` (§4.7). Closes no IOC-EV.
"""

from __future__ import annotations

from decimal import Decimal

from tos.ioc import (
    EconomicEffectEnvelope,
    economic_effect_dominated,
    no_silent_widening,
)
from tos.rcl import CapacityComponent, CapacityVector

from ._ioc_strategies import capacity_vector


def _vec(**dims: Decimal | None) -> CapacityVector:
    """Build an rcl CapacityVector from ``dimension=magnitude`` kwargs."""
    return CapacityVector(
        components=tuple(
            CapacityComponent(dimension_id=d, magnitude=m) for d, m in dims.items()
        )
    )


# ---------------------------------------------------------------------------
# dominance positive side (§5.5 / §13 / IOC-INV-005 line 173)
# ---------------------------------------------------------------------------


def test_committed_dominates_every_governed_dimension() -> None:
    """(canary +) Committed >= envelope on every governed dimension => dominated (True)."""
    envelope = _vec(notional=Decimal("10"), delta=Decimal("5"))
    committed = _vec(
        notional=Decimal("20"), delta=Decimal("5")
    )  # equal counts as dominate
    assert economic_effect_dominated(envelope, committed) is True


def test_envelope_type_is_rcl_capacity_vector() -> None:
    """(§0.4c) The predicate operates on the rcl CapacityVector type ioc REUSEs for the envelope."""
    assert EconomicEffectEnvelope is CapacityVector
    assert (
        economic_effect_dominated(
            capacity_vector(), capacity_vector(magnitude=Decimal("50"))
        )
        is True
    )


# ---------------------------------------------------------------------------
# dominance negative side — committed below envelope on any dimension
# ---------------------------------------------------------------------------


def test_committed_below_on_one_dimension_is_not_dominated() -> None:
    """(canary - 'reduce/shrink' §13 line 343) Committed below envelope on one dim => not-dominated."""
    envelope = _vec(notional=Decimal("10"), delta=Decimal("5"))
    committed = _vec(notional=Decimal("10"), delta=Decimal("4"))  # delta short
    assert economic_effect_dominated(envelope, committed) is False


def test_none_envelope_magnitude_is_not_dominated() -> None:
    """(fail-closed §4.3) A None (UNKNOWN) envelope magnitude => not-dominated (never assume-zero)."""
    envelope = _vec(notional=None)
    committed = _vec(notional=Decimal("100"))
    assert economic_effect_dominated(envelope, committed) is False


def test_none_committed_magnitude_is_not_dominated() -> None:
    """(fail-closed §4.3) A None (UNKNOWN) committed magnitude => not-dominated."""
    envelope = _vec(notional=Decimal("10"))
    committed = _vec(notional=None)
    assert economic_effect_dominated(envelope, committed) is False


def test_missing_committed_dimension_is_not_dominated() -> None:
    """(fail-closed) A governed dimension absent from committed => not-dominated."""
    envelope = _vec(notional=Decimal("10"), delta=Decimal("5"))
    committed = _vec(notional=Decimal("100"))  # delta absent
    assert economic_effect_dominated(envelope, committed) is False


# ---------------------------------------------------------------------------
# ∅ both-ways (§4.7) — empty envelope / empty committed
# ---------------------------------------------------------------------------


def test_empty_envelope_is_not_dominated() -> None:
    """(∅ §4.7) An empty envelope governs nothing — vacuous dominance is not dominance => False."""
    assert (
        economic_effect_dominated(CapacityVector(), _vec(notional=Decimal("100")))
        is False
    )


def test_empty_committed_is_not_dominated() -> None:
    """(∅ §4.7) An empty committed vector leaves every governed dimension None => not-dominated."""
    assert (
        economic_effect_dominated(_vec(notional=Decimal("10")), CapacityVector())
        is False
    )


def test_both_empty_is_not_dominated() -> None:
    """(∅ both-ways) Empty envelope AND empty committed => not-dominated (fail-closed both sides)."""
    assert economic_effect_dominated(CapacityVector(), CapacityVector()) is False


# ---------------------------------------------------------------------------
# no_silent_widening (§5.3 / §11 line 303 / IOC-INV-006)
# ---------------------------------------------------------------------------


def test_exact_bounded_and_all_gates_evaluated_passes() -> None:
    """(canary +) An exact bounded transformation inside the envelope, all gates evaluated => True."""
    assert (
        no_silent_widening(
            exact_bounded_within_envelope=True, every_dependent_gate_evaluated=True
        )
        is True
    )


def test_transformation_outside_envelope_is_rejected() -> None:
    """(canary - 'widen/narrow' §11 line 303) A transformation outside the envelope => False."""
    assert (
        no_silent_widening(
            exact_bounded_within_envelope=False, every_dependent_gate_evaluated=True
        )
        is False
    )


def test_gate_not_evaluated_is_rejected() -> None:
    """(canary -) A dependent gate that did not evaluate the choice set => False."""
    assert (
        no_silent_widening(
            exact_bounded_within_envelope=True, every_dependent_gate_evaluated=False
        )
        is False
    )


def test_unknown_transformation_fails_closed() -> None:
    """(fail-closed) An unknown (None) transformation status => False (even risk-reducing rounding)."""
    assert (
        no_silent_widening(
            exact_bounded_within_envelope=None, every_dependent_gate_evaluated=True
        )
        is False
    )
