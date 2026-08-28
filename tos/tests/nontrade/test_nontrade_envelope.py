"""§5.1 transition-envelope completeness + structural no-netting (NT-EV-002 substrate).

*Discipline tag: predicate / coordinate substrate only. NT-EV-002 is ``EV-L1/3`` — this
authors the L1 slice and closes **nothing**; the ``/3`` integration-fault and adversarial
interleaving evidence, the independent review, and the rcl / are runtime remain outstanding.
No EV-L1-complete claim.*

The two load-bearing properties are the **C1 ∅ structural guard** (an empty required-leg
set returns ``False`` inside the predicate, never delegated downstream) and the
**structural no-netting derivation** (two coexisting non-negative magnitudes, not a flag).
Both are checked in **both directions**: the guard fires on the illegal input *and* the
genuinely complete envelope passes (a vacuous block is as much a defect as a vacuous admit,
design #21 §4.7).
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st
from tos.nontrade import (
    CredibleTransitionLegKind,
    TransitionEnvelope,
    favorable_netting_absent,
    transition_envelope_complete,
)

from ._nontrade_strategies import (
    ALL_LEGS,
    FINITE_NON_NEGATIVE,
    LEG_SETS,
    MAGNITUDE_SLOT,
    clean_envelope,
)

# ---------------------------------------------------------------------------
# The C1 ∅ structural guard (design #21 §5.1)
# ---------------------------------------------------------------------------


def test_an_empty_required_leg_set_is_false_inside_the_predicate() -> None:
    """(C1 / §4.7 row 1) ∅ required legs is "we do not know what to prove", not "no risk".

    ``∅ <= anything`` is vacuously ``True``, so without the structural guard this predicate
    would certify a **completely empty** envelope as complete — the fail-open seam the
    series has rejected since #6 v1.0. The guard is the predicate's first line; nothing is
    delegated to a downstream "handled elsewhere" step.
    """
    assert transition_envelope_complete(clean_envelope(), frozenset()) is False
    # ...and it fires even for the emptiest possible envelope, where a vacuous ⊆ would have
    # been most tempting.
    assert transition_envelope_complete(TransitionEnvelope(), frozenset()) is False


def test_the_empty_guard_precedes_the_none_envelope_check() -> None:
    """(C1) ∅ required legs rejects even before there is an envelope to inspect."""
    assert transition_envelope_complete(None, frozenset()) is False


def test_a_none_envelope_is_false() -> None:
    """(fail-closed) No envelope proves no completeness."""
    assert transition_envelope_complete(None, ALL_LEGS) is False
    assert favorable_netting_absent(None) is False


# ---------------------------------------------------------------------------
# Completeness (§9 line 183)
# ---------------------------------------------------------------------------


def test_a_complete_envelope_passes_the_availability_side() -> None:
    """(both-ways, availability) All ten legs + coexisting exposures ⇒ ``True``."""
    assert transition_envelope_complete(clean_envelope(), ALL_LEGS) is True


@given(st.sampled_from(list(CredibleTransitionLegKind)))
def test_any_single_missing_leg_makes_the_envelope_incomplete(
    missing: CredibleTransitionLegKind,
) -> None:
    """(§9 line 183) A missing leg leaves an unenumerated credible state ⇒ ``False``.

    Exhaustive over all ten legs: no leg is privileged or silently optional.
    """
    legs = tuple(leg for leg in CredibleTransitionLegKind if leg is not missing)
    envelope = clean_envelope(present_legs=legs)
    assert transition_envelope_complete(envelope, ALL_LEGS) is False


@given(LEG_SETS, LEG_SETS)
def test_completeness_is_exactly_the_subset_relation_when_netting_is_absent(
    required: frozenset[CredibleTransitionLegKind],
    present: frozenset[CredibleTransitionLegKind],
) -> None:
    """(§9) With no-netting proven, completeness ⇔ ``required`` non-empty and ⊆ ``present``."""
    envelope = clean_envelope(present_legs=tuple(present))
    expected = bool(required) and required <= present
    assert transition_envelope_complete(envelope, required) is expected


def test_a_narrower_applicable_subset_is_the_callers_responsibility() -> None:
    """(§10.4 G1 honest disclosure) A non-empty but under-narrowed subset still passes.

    This is the acknowledged residual of a "where applicable" non-closed minimum set: the
    predicate enforces completeness **within** the injected subset and cannot know that the
    caller narrowed it wrongly. Phase 1 claims only the former; the event-class mapping that
    picks the subset is runtime (EV-L2/L3).
    """
    single = frozenset({CredibleTransitionLegKind.PRE_EVENT_POSITION_AND_ORDER})
    envelope = clean_envelope(present_legs=tuple(single))
    assert transition_envelope_complete(envelope, single) is True
    # ...but the ∅ end of that spectrum is still structurally blocked.
    assert transition_envelope_complete(envelope, frozenset()) is False


# ---------------------------------------------------------------------------
# Structural no-netting (§9 line 196 / §0.4d)
# ---------------------------------------------------------------------------


def test_both_exposures_present_and_non_negative_proves_no_netting() -> None:
    """(§0.4d, availability) Old and new coexist ⇒ netting is structurally impossible."""
    assert favorable_netting_absent(clean_envelope()) is True


@given(MAGNITUDE_SLOT, MAGNITUDE_SLOT)
def test_no_netting_holds_exactly_when_both_magnitudes_coexist_non_negative(
    pre: Decimal | None, post: Decimal | None
) -> None:
    """(§4.7 row 2) Any ``None`` or negative magnitude ⇒ netting unproven ⇒ ``False``."""
    envelope = clean_envelope(pre_event_exposure=pre, post_event_credible_exposure=post)
    expected = pre is not None and post is not None and pre >= 0 and post >= 0
    assert favorable_netting_absent(envelope) is expected


def test_netting_away_one_leg_is_caught() -> None:
    """(§9 line 196 canary) Offsetting the old against the new erases one magnitude.

    A netted accounting collapses the pair into a single number; the surviving shape is a
    ``None`` on one axis, which this predicate rejects. There is no ``netting_applied``
    flag to forge because there is no flag at all (design #21 M7).
    """
    netted_away_old = clean_envelope(pre_event_exposure=None)
    netted_away_new = clean_envelope(post_event_credible_exposure=None)
    assert favorable_netting_absent(netted_away_old) is False
    assert favorable_netting_absent(netted_away_new) is False
    assert transition_envelope_complete(netted_away_old, ALL_LEGS) is False
    assert transition_envelope_complete(netted_away_new, ALL_LEGS) is False


def test_a_negative_exposure_is_a_sign_error_not_a_credit() -> None:
    """(§4.7 row 2) A negative magnitude would let one leg cancel the other arithmetically."""
    assert favorable_netting_absent(
        clean_envelope(pre_event_exposure=Decimal("-1"))
    ) is (False)
    assert (
        favorable_netting_absent(
            clean_envelope(post_event_credible_exposure=Decimal("-1"))
        )
        is False
    )


def test_double_counting_old_and_new_is_the_conservative_requirement() -> None:
    """(§9 line 187 / §12 line 248) Both identities stay active — the sum is not this package's.

    The envelope deliberately carries both exposures side by side; ``tos.nontrade`` never
    adds them (rcl unions, are projects). The check here is that the shape survives, i.e.
    that neither magnitude is derived from the other.
    """
    envelope = clean_envelope(
        pre_event_exposure=Decimal("7"), post_event_credible_exposure=Decimal("5")
    )
    assert envelope.pre_event_exposure == Decimal("7")
    assert envelope.post_event_credible_exposure == Decimal("5")
    assert favorable_netting_absent(envelope) is True
    # the package exposes no summation of any kind
    from tos import nontrade as nontrade_pkg

    for forbidden in (
        "aggregate_usage",
        "credible_union_capacity",
        "worst_intermediate_risk",
        "effective_limit",
        "CapacityVector",
        "ProjectedCell",
    ):
        assert not hasattr(nontrade_pkg, forbidden)


# ---------------------------------------------------------------------------
# Completeness composes no-netting (no fall-through)
# ---------------------------------------------------------------------------


@given(FINITE_NON_NEGATIVE)
def test_completeness_requires_the_no_netting_conjunct_too(pre: Decimal) -> None:
    """(§4.1) A fully-legged envelope with a missing exposure is still incomplete.

    The conjunct is separate and mandatory: leg completeness must never promote an
    unproven-netting envelope by fall-through.
    """
    complete_legs_only = clean_envelope(
        pre_event_exposure=pre, post_event_credible_exposure=None
    )
    assert complete_legs_only.present_leg_set() == ALL_LEGS
    assert transition_envelope_complete(complete_legs_only, ALL_LEGS) is False
