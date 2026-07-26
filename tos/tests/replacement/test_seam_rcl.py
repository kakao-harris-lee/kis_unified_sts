"""MANDATED test-only seam cross-check: replacement <-> rcl (design #18 §3.4(d)/§0.4c).

``tos.replacement`` does **not** import ``tos.rcl`` at runtime, and that is the *most
load-bearing* absence in the package: design #18 §0.4c considered the ``CapacityVector``
REUSE — which would have been the seventh ``* -> rcl`` sibling edge, after are / afg / ioc
— and **rejected** it. The Phase-1 decision is set / polarity / magnitude logic, needs no
vector type, and a replacement-local dimension axis would collide with the rcl / are
namespaces (design #18 §0.4c reasons (i)-(iv)). The §7.1 closure test asserts the absence;
this file asserts the **consequence**: the double-counting reconciliation still works
end-to-end with rcl on the other side of an injected verdict.

The §0.4d judgment being locked here: overlap-first counts the old order **and** the new
order, and rcl's ``aggregate_usage`` sums them dimension-wise. The double count is the
conservative requirement, not a defect (§20.2 line 443 "Simultaneous fills can over-close
or reverse exposure"). replacement owns *completeness + structural no-netting*; rcl owns
*summation + hard envelope*; are owns the aggregate-risk projection.

A test-only cross-import is **not** a runtime package edge (design #18 §3.4(d)/§7.1).
"""

from __future__ import annotations

from decimal import Decimal

from tos.rcl import (
    CapacityComponent,
    CapacityState,
    CapacityVector,
    aggregate_usage,
    effective_limit,
    partition_verdict,
)
from tos.replacement import (
    ReplacementOutcome,
    netting_absent,
    overlap_first_reservation_complete,
    reversal_bounded_outcome,
)

from ._replacement_strategies import ALL_OUTCOMES, clean_claim, clean_magnitudes

_DIMENSION = "economic-exposure-dimension-1"


def _vector(magnitude: Decimal | None) -> CapacityVector:
    """A one-dimension capacity vector on the injected economic dimension."""
    return CapacityVector(
        components=(CapacityComponent(dimension_id=_DIMENSION, magnitude=magnitude),)
    )


def _usage_of(*magnitudes: Decimal | None) -> Decimal | None:
    """Sum magnitudes through the **rcl** aggregation (replacement never sums)."""
    aggregate = aggregate_usage([_vector(magnitude) for magnitude in magnitudes])
    return aggregate.components[0].magnitude


# ---------------------------------------------------------------------------
# §0.4d — double counting is conservative, and rcl does the summation
# ---------------------------------------------------------------------------


def test_the_old_and_new_magnitudes_are_summed_by_rcl_not_netted() -> None:
    """(§0.4d / §20.2 line 443) Old + new + simultaneous is a **sum**, never an offset.

    replacement proves structurally that the three magnitudes coexist; rcl then adds them.
    A netting implementation would have produced ``max`` or a difference here.
    """
    old, new, simultaneous = Decimal("7"), Decimal("5"), Decimal("12")
    claim = clean_claim(
        magnitudes=clean_magnitudes(
            OLD_ORDER_REMAINING_EXECUTABLE=old,
            NEW_ORDER_REMAINING_EXECUTABLE=new,
            SIMULTANEOUS_OLD_AND_NEW_FILLS=simultaneous,
        )
    )
    assert netting_absent(claim) is True
    summed = _usage_of(old, new)
    assert summed == old + new
    assert summed > max(old, new), "a netted reservation would not exceed either leg"


def test_a_missing_magnitude_propagates_unknown_on_both_sides_of_the_seam() -> None:
    """(seam polarity) rcl propagates ``None``; replacement fails the structural proof.

    Causal isolation: one magnitude is knocked out and both sides flip together.
    """
    claim = clean_claim(
        magnitudes=clean_magnitudes(NEW_ORDER_REMAINING_EXECUTABLE=None)
    )
    assert netting_absent(claim) is False
    assert _usage_of(Decimal("7"), None) is None
    # ...and with the magnitude restored both sides are decidable again.
    assert netting_absent(clean_claim()) is True
    assert _usage_of(Decimal("7"), Decimal("5")) == Decimal("12")


def test_the_hard_envelope_verdict_comes_from_rcl_and_replacement_only_consumes_it() -> (
    None
):
    """(§0.4c) ``aggregate_usage <= effective_limit`` is rcl's; the bool is injected."""
    usage = aggregate_usage([_vector(Decimal("7")), _vector(Decimal("5"))])
    limit = effective_limit(_vector(Decimal("100")), _vector(Decimal("50")))
    usage_magnitude = usage.components[0].magnitude
    limit_magnitude = limit.components[0].magnitude
    assert limit_magnitude == Decimal(
        "50"
    ), "the runtime profile may reduce, never enlarge"
    within = usage_magnitude is not None and usage_magnitude <= limit_magnitude
    assert within is True

    assert (
        overlap_first_reservation_complete(
            clean_claim(), ALL_OUTCOMES, within_hard_envelope=within
        )
        is True
    )
    # Causal isolation: only the injected verdict flips.
    assert (
        overlap_first_reservation_complete(
            clean_claim(), ALL_OUTCOMES, within_hard_envelope=False
        )
        is False
    )


def test_an_unknown_effective_limit_propagates_unknown_into_the_comparison() -> None:
    """(§5.3 UNKNOWN propagation) A ``None`` limit is UNKNOWN, never an implicit pass."""
    limit = effective_limit(_vector(None), _vector(Decimal("50")))
    assert limit.components[0].magnitude is None
    assert (
        reversal_bounded_outcome(
            aggregate_risk_magnitude=Decimal("12"),
            hard_envelope_limit=limit.components[0].magnitude,
            within_hard_envelope=True,
        )
        is ReplacementOutcome.REPLACEMENT_UNKNOWN
    )


def test_an_over_envelope_double_count_denies() -> None:
    """(PR-AC-001 "prevents unbounded reversal") The conservative sum can exceed the limit.

    That is the whole point of refusing to net: a reservation that would have *looked*
    fine after netting is denied once both legs are counted.
    """
    usage = aggregate_usage([_vector(Decimal("40")), _vector(Decimal("40"))])
    limit = effective_limit(_vector(Decimal("100")), _vector(Decimal("50")))
    usage_magnitude = usage.components[0].magnitude
    limit_magnitude = limit.components[0].magnitude
    assert usage_magnitude == Decimal("80")
    assert usage_magnitude > limit_magnitude
    within = usage_magnitude <= limit_magnitude
    assert within is False
    assert (
        reversal_bounded_outcome(
            aggregate_risk_magnitude=usage_magnitude,
            hard_envelope_limit=limit_magnitude,
            within_hard_envelope=within,
        )
        is ReplacementOutcome.REPLACEMENT_DENIED
    )
    # Netting one leg away would have hidden the breach — which is why it is structurally
    # impossible on the replacement side.
    assert Decimal("40") <= limit_magnitude


# ---------------------------------------------------------------------------
# Ownership / non-collapse
# ---------------------------------------------------------------------------


def test_replacement_authors_no_capacity_arithmetic_or_state() -> None:  # noqa: D401
    """(§0.2) No vector, no summation, no capacity state on the replacement surface."""
    from tos import replacement as replacement_pkg

    for forbidden in (
        "CapacityVector",
        "CapacityComponent",
        "CapacityState",
        "aggregate_usage",
        "effective_limit",
        "partition_verdict",
        "commit_capacity",
        "release_capacity",
    ):
        assert not hasattr(replacement_pkg, forbidden), (
            f"{forbidden} is on the replacement surface — design #18 §0.4c REJECTED the "
            "CapacityVector REUSE and §0.2 assigns all capacity arithmetic to rcl"
        )


def test_the_replacement_outcome_axis_is_not_the_rcl_capacity_state_axis() -> None:
    """(§2.2-5) ``REPLACEMENT_TRAPPED`` is not ``TRAPPED_CONSUMED``."""
    assert set(ReplacementOutcome).isdisjoint(set(CapacityState))
    assert ReplacementOutcome.REPLACEMENT_TRAPPED is not CapacityState.TRAPPED_CONSUMED


def test_the_partition_verdict_preserves_every_capacity_class() -> None:
    """(§16 seam) Quorum loss neither creates nor releases capacity — rcl's judgment.

    replacement consumes the verdict as a coordinate; it never mutates capacity, so the
    preservation guarantees below are asserted on the rcl side only.
    """
    verdict = partition_verdict(None)
    assert verdict.capacity_release_denied is True
    assert verdict.trapped_preserved is True
    assert verdict.protective_preserved is True
    assert verdict.automatic_rearm_denied is True
