"""Negative evidence: omission is not proof of non-existence (§5.3; RECON-EV-002).

Absence (``is_absence=True``) may lower confidence but SHALL NOT establish
``NONE`` / ``CANCELLED`` / ``released``, narrow a bound, or produce a release proof
(ADR §7 line 102). Both-ways: real positive observations are still reflected.
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st
from tos.recon import (
    ConservativeBound,
    FieldConfidenceClass,
    SafetyRelevantField,
    classify_field,
    conservative_bound_of,
    field_reconciled_proof_ok,
    field_specific_release_proof_ok,
)

from ._recon_strategies import (
    bounds,
    field_confidence,
    fresh_marker,
    observation,
    observations,
    release_inputs,
)

_C = FieldConfidenceClass
_CAP = SafetyRelevantField.CUMULATIVE_FILLED_QUANTITY


def _b(lower, upper) -> ConservativeBound:
    return ConservativeBound(
        lower=None if lower is None else Decimal(lower),
        upper=None if upper is None else Decimal(upper),
    )


def test_absence_does_not_narrow_bound() -> None:
    """(§5.3) Adding an absence observation never narrows the positive conservative bound."""
    positive = (observation(asserted_bound=_b(10, 100)),)
    base = conservative_bound_of(positive)
    with_absence = conservative_bound_of(
        positive + (observation(is_absence=True, asserted_bound=_b(40, 60)),)
    )
    assert with_absence.covers(base)  # never narrower
    assert with_absence.lower == Decimal(10) and with_absence.upper == Decimal(100)


def test_absence_only_is_unknown_not_terminal() -> None:
    """(§5.3) Absence-only observations classify UNKNOWN — never a terminal / released signal."""
    obs = (
        observation(is_absence=True),
        observation(is_absence=True, independence_class="B"),
    )
    assert classify_field(obs, fresh_marker()) is _C.UNKNOWN


def test_absence_never_produces_release_proof() -> None:
    """(§5.3) A field whose confidence comes only from absence has no release proof."""
    # An UNKNOWN field (absence-only) can never be released.
    unknown_conf = field_confidence(field=_CAP, confidence_class=_C.UNKNOWN)
    assert (
        field_specific_release_proof_ok(_CAP, unknown_conf, release_inputs()) is False
    )
    assert field_reconciled_proof_ok(_CAP, unknown_conf, release_inputs()) is False


def test_absence_does_not_lift_single_source_to_corroborated() -> None:
    """(§5.3) One positive + one absence stays SINGLE_SOURCE (absence adds no independent path)."""
    obs = (
        observation(independence_class="A", agrees_within_tolerance=True),
        observation(
            independence_class="B", is_absence=True, agrees_within_tolerance=True
        ),
    )
    assert classify_field(obs, fresh_marker()) is _C.SINGLE_SOURCE


@given(
    obs=st.lists(observations(), min_size=0, max_size=5),
    extra_absence_bound=bounds(),
)
def test_adding_absence_never_narrows_property(obs: list, extra_absence_bound) -> None:
    """(property) Appending any absence observation never narrows the derived bound."""
    before = conservative_bound_of(tuple(obs))
    absence = observation(is_absence=True, asserted_bound=extra_absence_bound)
    after = conservative_bound_of(tuple(obs) + (absence,))
    assert after.covers(before)


@given(obs=st.lists(observations(), min_size=1, max_size=5))
def test_adding_absence_never_raises_class_property(obs: list) -> None:
    """(property) An absence observation never raises the confidence class to CORROBORATED."""
    absence = observation(
        is_absence=True, independence_class="Z", agrees_within_tolerance=True
    )
    before = classify_field(tuple(obs), fresh_marker())
    after = classify_field(tuple(obs) + (absence,), fresh_marker())
    # Absence is excluded from the usable set, so the classification is unchanged.
    assert after is before
