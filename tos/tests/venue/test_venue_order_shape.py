"""order_shape_admissible — venue-admissibility of the exact order shape (design #19 §5.3; VTG-EV-004).

Band / tick / lot / qty / order-type / TIF are checked with NO permissive rounding; all bounds
are injected (nothing hardcoded); silent rounding => INADMISSIBLE; missing/invalid bound =>
UNKNOWN. This is venue-admissibility, distinct from ioc intent-conformance (§3.5 핵심 판정 (a)).

Regime tag: predicate / model substrate only; VTG-EV-004 NOT_IMPLEMENTED (`/3` + Broker
residue); EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from tos.venue import OrderAdmissibilityResult, order_shape_admissible

from ._venue_strategies import clean_shape, clean_shape_constraints


def test_venue_valid_shape_is_admissible_positive_side() -> None:
    """(§12 canary b) A shape inside every band / tick / lot / enum set is ADMISSIBLE."""
    assert (
        order_shape_admissible(clean_shape(), clean_shape_constraints())
        is OrderAdmissibilityResult.ADMISSIBLE
    )


def test_price_out_of_band_is_inadmissible() -> None:
    """(§12 line 299) A price outside the injected band is INADMISSIBLE."""
    below = clean_shape().model_copy(update={"price": 95})
    above = clean_shape().model_copy(update={"price": 205})
    assert (
        order_shape_admissible(below, clean_shape_constraints())
        is OrderAdmissibilityResult.INADMISSIBLE
    )
    assert (
        order_shape_admissible(above, clean_shape_constraints())
        is OrderAdmissibilityResult.INADMISSIBLE
    )


def test_invalid_tick_is_inadmissible() -> None:
    """(§12 line 299) A price off the injected tick grid is INADMISSIBLE."""
    off_tick = clean_shape().model_copy(update={"price": 103})  # 103 - 100 = 3, tick=5
    assert (
        order_shape_admissible(off_tick, clean_shape_constraints())
        is OrderAdmissibilityResult.INADMISSIBLE
    )


def test_odd_lot_is_inadmissible() -> None:
    """(§12 line 299) An odd-lot quantity (off the injected lot) is INADMISSIBLE."""
    odd = clean_shape().model_copy(update={"quantity": 15})  # lot=10
    assert (
        order_shape_admissible(odd, clean_shape_constraints())
        is OrderAdmissibilityResult.INADMISSIBLE
    )


def test_quantity_out_of_range_is_inadmissible() -> None:
    """(§12) A quantity below min or above max is INADMISSIBLE."""
    below = clean_shape().model_copy(update={"quantity": 0})
    above = clean_shape().model_copy(update={"quantity": 110})
    assert (
        order_shape_admissible(below, clean_shape_constraints())
        is OrderAdmissibilityResult.INADMISSIBLE
    )
    assert (
        order_shape_admissible(above, clean_shape_constraints())
        is OrderAdmissibilityResult.INADMISSIBLE
    )


def test_unsupported_order_type_or_tif_is_inadmissible() -> None:
    """(§12) An order type / TIF / side / position-effect not in the allowed set is INADMISSIBLE."""
    for field, value in (
        ("order_type", "STOP"),
        ("tif", "GTC"),
        ("side", "SHORT"),
        ("position_effect", "FLIP"),
    ):
        bad = clean_shape().model_copy(update={field: value})
        assert (
            order_shape_admissible(bad, clean_shape_constraints())
            is OrderAdmissibilityResult.INADMISSIBLE
        )


def test_silent_rounding_is_inadmissible() -> None:
    """(§12 line 309 / VTG-AC-004 line 617) A silently-rounded shape must fail."""
    for rounded in (True, None):
        shape = clean_shape().model_copy(update={"silently_rounded": rounded})
        assert (
            order_shape_admissible(shape, clean_shape_constraints())
            is OrderAdmissibilityResult.INADMISSIBLE
        )


def test_missing_injected_bound_is_unknown() -> None:
    """(§8 line 245) A missing injected band / tick / lot => UNKNOWN, never a permissive default."""
    no_band = clean_shape_constraints().model_copy(update={"price_max": None})
    assert (
        order_shape_admissible(clean_shape(), no_band)
        is OrderAdmissibilityResult.UNKNOWN
    )


def test_zero_tick_or_lot_is_unknown_not_a_divisor() -> None:
    """(§8.0) An invalid (zero) injected tick / lot is UNKNOWN, not a division error."""
    zero_tick = clean_shape_constraints().model_copy(update={"tick_size": 0})
    zero_lot = clean_shape_constraints().model_copy(update={"lot_size": 0})
    assert (
        order_shape_admissible(clean_shape(), zero_tick)
        is OrderAdmissibilityResult.UNKNOWN
    )
    assert (
        order_shape_admissible(clean_shape(), zero_lot)
        is OrderAdmissibilityResult.UNKNOWN
    )


def test_empty_allowed_set_is_unknown() -> None:
    """(§4.7 ∅) An empty allowed order-type set admits nothing => UNKNOWN (fail-closed)."""
    empty = clean_shape_constraints().model_copy(
        update={"allowed_order_types": frozenset()}
    )
    assert (
        order_shape_admissible(clean_shape(), empty) is OrderAdmissibilityResult.UNKNOWN
    )


def test_none_shape_or_constraints_is_unknown() -> None:
    """(∅) A None shape / constraints is UNKNOWN."""
    assert (
        order_shape_admissible(None, clean_shape_constraints())
        is OrderAdmissibilityResult.UNKNOWN
    )
    assert (
        order_shape_admissible(clean_shape(), None) is OrderAdmissibilityResult.UNKNOWN
    )


@given(price=st.integers(min_value=0, max_value=400))
def test_property_price_admissible_iff_in_band_and_on_tick(price: int) -> None:
    """(property) A price is ADMISSIBLE only when inside [100,200] and on the tick=5 grid."""
    constraints = clean_shape_constraints()  # band [100,200], tick 5
    shape = clean_shape().model_copy(update={"price": price})
    result = order_shape_admissible(shape, constraints)
    in_band_on_tick = 100 <= price <= 200 and (price - 100) % 5 == 0
    if in_band_on_tick:
        assert result is OrderAdmissibilityResult.ADMISSIBLE
    else:
        assert result is OrderAdmissibilityResult.INADMISSIBLE
