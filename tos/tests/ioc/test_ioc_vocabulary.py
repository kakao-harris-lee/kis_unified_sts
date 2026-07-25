"""Vocabulary verbatim-transcription + coordinate non-collapse (design #14 §2.2/§2.3).

The enums are the ADR-002-020 §10-§16 axis terms verbatim; the conformance axis is a distinct
coordinate system from the rcl / are / brokercap / orthostate axes (token overlap is intentional,
non-collapse rests on distinct types + non-import).
"""

from __future__ import annotations

from tos.ioc import (
    ConformanceAxis,
    ConformanceResult,
    MutationClass,
    OrderTypeKind,
    PositionEffectKind,
    QuantityUnitKind,
)


def test_conformance_result_values_verbatim() -> None:
    """(§2.2(1) / §14 line 372) Exactly CONFORMANT / NON_CONFORMANT / UNKNOWN."""
    assert {r.value for r in ConformanceResult} == {
        "CONFORMANT",
        "NON_CONFORMANT",
        "UNKNOWN",
    }


def test_position_effect_values_verbatim() -> None:
    """(§2.2(3) / §11 line 294-296) Exactly OPEN / CLOSE / REDUCE_ONLY."""
    assert {k.value for k in PositionEffectKind} == {"OPEN", "CLOSE", "REDUCE_ONLY"}


def test_order_type_values_verbatim() -> None:
    """(§2.2(4) / §12 line 313) The nine order-type kinds verbatim."""
    assert {k.value for k in OrderTypeKind} == {
        "MARKET",
        "LIMIT",
        "STOP",
        "STOP_LIMIT",
        "PEG",
        "AUCTION",
        "DISCRETIONARY",
        "CONDITIONAL",
        "BROKER_SPECIFIC",
    }


def test_quantity_unit_values_verbatim() -> None:
    """(§2.2(5) / §11 line 297) The nine quantity-unit kinds verbatim."""
    assert {k.value for k in QuantityUnitKind} == {
        "SHARES",
        "LOTS",
        "CONTRACTS",
        "BASE_UNIT",
        "QUOTE_UNIT",
        "NOMINAL",
        "NOTIONAL",
        "FACE_VALUE",
        "FRACTIONAL",
    }


def test_mutation_class_values() -> None:
    """(§2.2(6) / §16 line 427-437) The eight mutation classes (NEW / SPLIT_CHILD design-derived)."""
    assert {m.value for m in MutationClass} == {
        "NEW",
        "RETRY",
        "CANCEL",
        "AMEND",
        "REPLACE",
        "SPLIT_CHILD",
        "AGGREGATE",
        "EXERCISE",
    }


def test_conformance_axis_covers_all_three_clause_groups() -> None:
    """(§2.2(2)) The axis enum carries the §10 identity, §11 direction/quantity, §12 price/mode axes."""
    names = {a.value for a in ConformanceAxis}
    # §10 identity
    for axis in ("ENVIRONMENT", "BROKER", "ACCOUNT", "VENUE", "INSTRUMENT", "ROUTE"):
        assert axis in names
    # §11 direction + quantity (direction / side / position-effect are independent axes)
    for axis in (
        "DIRECTION",
        "SIDE",
        "POSITION_EFFECT",
        "QUANTITY",
        "UNIT",
        "MULTIPLIER",
    ):
        assert axis in names
    # §12 price / order-type / mode
    for axis in (
        "PRICE",
        "ORDER_TYPE",
        "TIF",
        "EXPIRATION",
        "REDUCE_ONLY",
        "POST_ONLY",
        "MODE",
    ):
        assert axis in names


def test_conformance_axis_is_distinct_type_from_rcl_dimension() -> None:
    """(§2.3 non-collapse) A ConformanceAxis is not an rcl / are coordinate — a distinct StrEnum."""
    from tos.are import RiskDimensionKind
    from tos.rcl import DimensionDescriptor

    assert ConformanceAxis is not RiskDimensionKind
    assert ConformanceAxis is not DimensionDescriptor
    # A shared token ("INSTRUMENT" / "ACCOUNT") lives on distinct types — never coercible.
    assert ConformanceAxis.INSTRUMENT.value == "INSTRUMENT"
    assert not isinstance(ConformanceAxis.INSTRUMENT, RiskDimensionKind)
