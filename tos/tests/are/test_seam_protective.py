"""MANDATED test-only seam cross-check: are <-> protective (design #13 §3.4/§5.3).

are does NOT import ``tos.protective`` at runtime (the import-closure test asserts its
absence); this file imports **both** as a **test** to lock the #11 OQ3 magnitude seam. The
central ownership fact: **are produces** the conservative magnitudes; **protective compares**
them (it never computes them). These tests prove (a) the produced-magnitude signatures /
polarity match the protective ``AggregateRiskComparison`` / ``IntermediateStateWitness``
injected slots, (b) a ``None`` magnitude fails the classifier closed, and (c) causal isolation
— flipping a single are-produced value flips the ``protective_classification`` outcome.

A test-only cross-import is NOT a runtime package edge (design #13 §3.4/§7.1).
"""

from __future__ import annotations

from decimal import Decimal

from tos.are import (
    already_exceeded_regime,
    cancellation_worsens_aggregate,
    continued_existence_worsens_aggregate,
    credible_space_bounded,
    current_conservative_risk,
    final_conservative_risk,
    no_action_risk,
    no_credible_intermediate_increases_exceedance,
    worst_intermediate_risk,
)
from tos.protective import (
    AggregateRiskComparison,
    IntermediateStateWitness,
    ProtectiveActionOutcome,
    ProtectiveOwnership,
    cancellation_admissible,
    protective_classification,
)

from ._are_strategies import cancellation_inputs, clean_cell


def _comparison(cells) -> AggregateRiskComparison:
    """Fill the protective comparison from are-produced magnitudes (signature parity)."""
    return AggregateRiskComparison(
        final_conservative_risk=final_conservative_risk(cells),
        current_conservative_risk=current_conservative_risk(cells),
        no_action_risk=no_action_risk(cells),
        already_exceeded_regime=already_exceeded_regime(cells),
    )


def _witness(cells) -> IntermediateStateWitness:
    """Fill the protective witness from are-produced magnitudes (signature parity)."""
    return IntermediateStateWitness(
        worst_intermediate_risk=worst_intermediate_risk(cells),
        credible_space_bounded=credible_space_bounded(cells),
        no_credible_intermediate_increases_exceedance=(
            no_credible_intermediate_increases_exceedance(cells)
        ),
    )


def test_are_magnitudes_fill_protective_slots_and_prove() -> None:
    """(seam +) A clean cell (final 10 < current 15, worst 9 <= no_action 12) => PROTECTIVE_PROVEN."""
    cells = (clean_cell(),)
    outcome = protective_classification(
        _comparison(cells), _witness(cells), envelope_within_hard=True
    )
    assert outcome is ProtectiveActionOutcome.PROTECTIVE_PROVEN


def test_causal_isolation_flip_final_reverses_outcome() -> None:
    """(causal isolation) Flipping only ``final_conservative_risk`` above current reverses the outcome."""
    base = (clean_cell(),)
    assert (
        protective_classification(
            _comparison(base), _witness(base), envelope_within_hard=True
        )
        is ProtectiveActionOutcome.PROTECTIVE_PROVEN
    )
    # flip ONE are-produced value: final now ABOVE current (a risk-increasing action).
    flipped = (clean_cell(final_conservative_risk=Decimal("99")),)
    assert (
        protective_classification(
            _comparison(flipped), _witness(flipped), envelope_within_hard=True
        )
        is ProtectiveActionOutcome.RISK_INCREASING_DENIED
    )


def test_none_magnitude_fails_classifier_closed() -> None:
    """(fail-closed parity §5.3) A None are magnitude => RISK_INCREASING_DENIED (predicates.py:289-290)."""
    cells = (clean_cell(final_conservative_risk=None),)
    assert final_conservative_risk(cells) is None
    outcome = protective_classification(
        _comparison(cells), _witness(cells), envelope_within_hard=True
    )
    assert outcome is ProtectiveActionOutcome.RISK_INCREASING_DENIED


def test_unbounded_credible_space_is_unknown_conservative() -> None:
    """(§6.2 line 277 parity) An unbounded credible space => UNKNOWN_CONSERVATIVE, not excluded."""
    cells = (clean_cell(credible_space_bounded=None),)
    assert credible_space_bounded(cells) is None
    outcome = protective_classification(
        _comparison(cells), _witness(cells), envelope_within_hard=True
    )
    assert outcome is ProtectiveActionOutcome.UNKNOWN_CONSERVATIVE


def test_cancellation_flags_feed_cancellation_arbiter() -> None:
    """(seam) are cancellation flags feed protective ``cancellation_admissible`` (polarity)."""
    inputs = cancellation_inputs()  # continued 20 > baseline 10; post 5 < baseline 10
    continued = continued_existence_worsens_aggregate(inputs)
    cancel = cancellation_worsens_aggregate(inputs)
    # SAFETY_OWNED: continued existence worsens + controller authorizes => cancellable.
    assert (
        cancellation_admissible(
            ProtectiveOwnership.SAFETY_OWNED,
            protection_no_longer_required=None,
            within_hard_envelope=None,
            equivalent_replacement_live=None,
            continued_existence_worsens_aggregate=continued,
            controller_authorizes_removal=True,
            cancellation_worsens_aggregate=cancel,
        )
        is True
    )
    # ordinary order: only a positive False on cancellation_worsens_aggregate permits.
    assert (
        cancellation_admissible(
            ProtectiveOwnership.STRATEGY_OWNED,
            protection_no_longer_required=None,
            within_hard_envelope=None,
            equivalent_replacement_live=None,
            continued_existence_worsens_aggregate=continued,
            controller_authorizes_removal=None,
            cancellation_worsens_aggregate=cancel,
        )
        is True
    )


def test_none_cancellation_flag_fails_closed_downstream() -> None:
    """(fail-closed) A None cancellation flag denies ordinary cancellation (protective restrictive)."""
    from tos.are import CancellationRiskInputs

    inputs = CancellationRiskInputs(baseline_no_action_risk=None)
    assert cancellation_worsens_aggregate(inputs) is None
    assert (
        cancellation_admissible(
            ProtectiveOwnership.STRATEGY_OWNED,
            protection_no_longer_required=None,
            within_hard_envelope=None,
            equivalent_replacement_live=None,
            continued_existence_worsens_aggregate=None,
            controller_authorizes_removal=None,
            cancellation_worsens_aggregate=cancellation_worsens_aggregate(inputs),
        )
        is False
    )
