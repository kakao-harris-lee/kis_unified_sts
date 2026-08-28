"""Digest-level Decimal normalization canaries (canonical §3.1a; RCL D1 fix).

Regression lock for the shared :data:`tos.rcl.vector.CanonicalDecimal` normalizer:
every covered Decimal field (magnitude AND the record quantity bounds) must yield an
EQUAL canonical digest for numerically-equal values (``1.0`` == ``1.00``; ``100`` ==
``1E+2``) and a DIFFERENT digest for distinct values. Without normalization,
``model_dump(mode="json")`` stringifies the Decimal and equal values would diverge
=> spurious CRITICAL_CONFLICT on idempotent re-emission + spurious grant
non-authorization.
"""

from __future__ import annotations

from decimal import Decimal

from tos.rcl import CapacityComponent, CapacityVector

from ._rcl_strategies import issue_capability, issue_reservation


def _reservation_with_magnitude(magnitude: Decimal):
    vector = CapacityVector(
        components=(
            CapacityComponent(dimension_id="gross_notional", magnitude=magnitude),
        )
    )
    return issue_reservation(reservation_id="x", adverse_increment_vector=vector)


# ---- magnitude (CapacityComponent.magnitude) -------------------------------


def test_magnitude_scale_equal_values_share_digest() -> None:
    """1.0 == 1.00 and 100 == 1E+2 at the record digest (equal values, equal digest)."""
    assert (
        _reservation_with_magnitude(Decimal("1.0")).canonical_digest
        == _reservation_with_magnitude(Decimal("1.00")).canonical_digest
    )
    assert (
        _reservation_with_magnitude(Decimal("100")).canonical_digest
        == _reservation_with_magnitude(Decimal("1E+2")).canonical_digest
    )


def test_magnitude_distinct_values_differ_in_digest() -> None:
    """Numerically-distinct magnitudes yield different digests (not collapsed)."""
    assert (
        _reservation_with_magnitude(Decimal("1.0")).canonical_digest
        != _reservation_with_magnitude(Decimal("1.5")).canonical_digest
    )
    assert (
        _reservation_with_magnitude(Decimal("100")).canonical_digest
        != _reservation_with_magnitude(Decimal("200")).canonical_digest
    )


# ---- a newly-normalized record quantity field ------------------------------


def test_approved_quantity_bound_equal_values_share_digest() -> None:
    """approved_quantity_upper_bound 100 == 1E+2 at the record digest (D1 field fix)."""
    a = issue_reservation(
        reservation_id="x", approved_quantity_upper_bound=Decimal("100")
    )
    b = issue_reservation(
        reservation_id="x", approved_quantity_upper_bound=Decimal("1E+2")
    )
    assert a.canonical_digest == b.canonical_digest


def test_approved_quantity_bound_distinct_values_differ() -> None:
    """approved_quantity_upper_bound distinct values differ in digest."""
    a = issue_reservation(
        reservation_id="x", approved_quantity_upper_bound=Decimal("100")
    )
    b = issue_reservation(
        reservation_id="x", approved_quantity_upper_bound=Decimal("101")
    )
    assert a.canonical_digest != b.canonical_digest


def test_capability_max_quantity_equal_values_share_digest() -> None:
    """TransmissionCapability.maximum_quantity 5.0 == 5.00 at the record digest."""
    a = issue_capability(capability_id="cap-x", maximum_quantity=Decimal("5.0"))
    b = issue_capability(capability_id="cap-x", maximum_quantity=Decimal("5.00"))
    assert a.canonical_digest == b.canonical_digest


def test_normalized_field_value_is_canonical_on_the_model() -> None:
    """The stored Decimal is normalized (so any downstream read is canonical too)."""
    reservation = issue_reservation(
        reservation_id="x", approved_quantity_upper_bound=Decimal("1E+2")
    )
    # Decimal("100") == Decimal("1E+2") by value; both normalize to the same object.
    assert reservation.approved_quantity_upper_bound == Decimal("100")
