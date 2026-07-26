"""MANDATED test-only seam cross-check: nontrade <-> replacement / ADR-002-011 (§3.5).

This is the **mutually explicit boundary** design #21 §3.5 calls out as the one with the
highest duplication risk, because both packages talk about envelopes, legs, no-netting, and
capacity:

* ADR-002-011 §16 recovery step 5 (``ADR-002-011...md:367`` verbatim) — "**reconcile current
  exposure and recognized non-trade changes**" — defers the *recognized non-trade change*
  to ADR-002-010, i.e. **to this package**;
* ADR-002-010 §13 line 272 — "**If protective coverage must be changed, ADR-002-011 governs
  cancellation, replacement, gap, overlap, and capacity**" — defers the *protective-order
  mechanism* back to replacement.

Two explicit deferrals in opposite directions, so the overlap is **zero**. The split axis is
**causal**: nontrade owns the *cause* (a corporate action makes an open order wrong) and
replacement owns the *effect* (the cancel / replace mechanism that fixes it). NT-EV-006
(Broker Open-Order Adjustment) is the contact point and is ``EV-L3/5`` — **not authored
here**, consumed only.

The regression this file provides is a **no-re-authoring** assertion in both directions:
neither package exposes the other's judgment, and the structurally identical no-netting
derivations stay on their own coordinate systems.

A test-only cross-import is **not** a runtime package edge (design #21 §3.4(d)/§7.1).
"""

from __future__ import annotations

from decimal import Decimal

from tos.nontrade import (
    CredibleTransitionLegKind,
    TransitionEnvelope,
    favorable_netting_absent,
    transition_envelope_complete,
)
from tos.replacement import (
    REQUIRED_CREDIBLE_INTERMEDIATE_OUTCOMES,
    CredibleIntermediateOutcomeKind,
    OverlapReservationClaim,
    ReplacementOutcome,
    ReplacementWorkflowState,
    netting_absent,
    overlap_first_reservation_complete,
)

from ._nontrade_strategies import ALL_LEGS, clean_envelope

_NETTING_KINDS = (
    CredibleIntermediateOutcomeKind.OLD_ORDER_REMAINING_EXECUTABLE,
    CredibleIntermediateOutcomeKind.NEW_ORDER_REMAINING_EXECUTABLE,
    CredibleIntermediateOutcomeKind.SIMULTANEOUS_OLD_AND_NEW_FILLS,
)


def _claim(**magnitudes: Decimal | None) -> OverlapReservationClaim:
    """A replacement overlap-first claim covering all nine credible intermediate outcomes."""
    base = {kind: Decimal("1") for kind in _NETTING_KINDS}
    for name, value in magnitudes.items():
        base[CredibleIntermediateOutcomeKind[name]] = value
    return OverlapReservationClaim(
        claim_id="repl-claim-1",
        reserved_outcome_kinds=REQUIRED_CREDIBLE_INTERMEDIATE_OUTCOMES,
        magnitudes=base,
        within_hard_envelope=True,
    )


# ---------------------------------------------------------------------------
# The two explicit deferrals — zero overlap
# ---------------------------------------------------------------------------


def test_nontrade_authors_no_protective_replacement_mechanism() -> None:
    """(§13 line 272) Cancellation, replacement, gap, overlap, and capacity are ADR-002-011's."""
    from tos import nontrade as nontrade_pkg

    for forbidden in (
        "ReplacementMode",
        "ReplacementOutcome",
        "ReplacementWorkflowState",
        "CredibleIntermediateOutcomeKind",
        "OverlapReservationClaim",
        "overlap_first_reservation_complete",
        "overlap_first_sequencing_valid",
        "cancel_first_admission_gate",
        "replacement_mode_admissible",
        "netting_absent",
    ):
        assert not hasattr(nontrade_pkg, forbidden), (
            f"{forbidden} is replacement-owned — ADR-002-010 §13 line 272 defers the "
            "protective-coverage mechanism explicitly"
        )


def test_replacement_authors_no_non_trade_event_identity() -> None:
    """(ADR-002-011 §16 line 367) The recognized non-trade change is deferred back here."""
    from tos import replacement as replacement_pkg

    for forbidden in (
        "NonTradeEventClass",
        "NonTradeEventRecord",
        "NonTradeEventWorkflowState",
        "CredibleTransitionLegKind",
        "TransitionEnvelope",
        "SplitTransformationSpec",
        "SplitTransformationKind",
        "CorrectionReversalRecord",
        "correction_reversal_idempotent",
        "split_polarity_coherent",
        "transition_envelope_complete",
        "nontrade_disposition",
    ):
        assert not hasattr(replacement_pkg, forbidden), (
            f"{forbidden} is nontrade-owned — ADR-002-011 §16 line 367 defers the "
            "recognized non-trade change explicitly"
        )


# ---------------------------------------------------------------------------
# Coordinate non-collapse (§2.2-5) — the same words on two axes
# ---------------------------------------------------------------------------


def test_the_transition_leg_axis_is_not_the_replacement_intermediate_axis() -> None:
    """(§2.2-5) A transition leg and a credible intermediate outcome are different types.

    ``PROTECTIVE_ORDER_GAP_OVERLAP`` (ours, ADR-002-010 §9 line 193) names the same subject
    matter as replacement's gap / overlap outcomes, which is precisely why the types must
    stay apart: one is a transition-envelope leg, the other a replacement-order outcome.
    """
    assert set(CredibleTransitionLegKind).isdisjoint(
        set(CredibleIntermediateOutcomeKind)
    )
    assert CredibleTransitionLegKind.PROTECTIVE_ORDER_GAP_OVERLAP is not None
    assert len(CredibleTransitionLegKind) == 10
    assert len(CredibleIntermediateOutcomeKind) == 9


def test_the_two_result_axes_are_disjoint() -> None:
    """(§2.2-5) ``NONTRADE_TRAPPED`` is not ``REPLACEMENT_TRAPPED``."""
    from tos.nontrade import NonTradeDisposition

    assert set(NonTradeDisposition).isdisjoint(set(ReplacementOutcome))
    assert set(NonTradeDisposition).isdisjoint(set(ReplacementWorkflowState))


# ---------------------------------------------------------------------------
# Two structurally identical no-netting derivations on two coordinate systems
# ---------------------------------------------------------------------------


def test_both_packages_derive_no_netting_structurally_on_their_own_axis() -> None:
    """(§0.4d) The *discipline* is shared; the coordinates are not.

    replacement proves no-netting over three credible-intermediate-outcome magnitudes;
    nontrade proves it over the pre- and post-event exposures. Both refuse to accept a
    flag, and neither re-implements the other's set.
    """
    assert netting_absent(_claim()) is True
    assert favorable_netting_absent(clean_envelope()) is True
    # ...and both collapse the same way when a magnitude is knocked out
    assert netting_absent(_claim(OLD_ORDER_REMAINING_EXECUTABLE=None)) is False
    assert favorable_netting_absent(clean_envelope(pre_event_exposure=None)) is False


def test_both_packages_reject_an_empty_required_universe() -> None:
    """(§4.7 row 1 / design #18 §4.7 row 1) ∅ proves nothing on either side.

    The two guards were authored independently against the same lesson, and this asserts
    they did not drift apart.
    """
    assert (
        overlap_first_reservation_complete(
            _claim(), frozenset(), within_hard_envelope=True
        )
        is False
    )
    assert transition_envelope_complete(clean_envelope(), frozenset()) is False
    # availability side on both
    assert (
        overlap_first_reservation_complete(
            _claim(), REQUIRED_CREDIBLE_INTERMEDIATE_OUTCOMES, within_hard_envelope=True
        )
        is True
    )
    assert transition_envelope_complete(clean_envelope(), ALL_LEGS) is True


def test_the_causal_split_is_observable() -> None:
    """(§3.5 judgment 1) nontrade names the cause; replacement carries the effect.

    The nontrade envelope enumerates a ``PROTECTIVE_ORDER_GAP_OVERLAP`` **leg** (a credible
    economic state during the event), while replacement reserves capacity for the credible
    intermediate **outcomes** of the cancel / replace mechanism. Neither set is derivable
    from the other, which is what "zero overlap" means concretely.
    """
    envelope = TransitionEnvelope(
        present_legs=(CredibleTransitionLegKind.PROTECTIVE_ORDER_GAP_OVERLAP,),
        pre_event_exposure=Decimal("1"),
        post_event_credible_exposure=Decimal("1"),
    )
    assert (
        transition_envelope_complete(
            envelope,
            frozenset({CredibleTransitionLegKind.PROTECTIVE_ORDER_GAP_OVERLAP}),
        )
        is True
    )
    # the replacement side, meanwhile, needs its own nine-outcome reservation and knows
    # nothing about the leg above
    assert (
        overlap_first_reservation_complete(
            _claim(),
            frozenset({CredibleIntermediateOutcomeKind.TEMPORARY_LOSS_OF_PROTECTION}),
            within_hard_envelope=True,
        )
        is True
    )
