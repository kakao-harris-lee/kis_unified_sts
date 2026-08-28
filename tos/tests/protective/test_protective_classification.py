"""Protective action classification purity + both-ways (design #11 §4.3/§5.3).

The classifier reads only injected conservative aggregate-risk comparisons — a strategy label
is structurally absent from its input models (ADR §6 line 249 non-authoritative). final >=
current or worst-intermediate > no-action => RISK_INCREASING_DENIED; an unbounded credible
space => UNKNOWN_CONSERVATIVE; only a positively-proven move => PROTECTIVE_PROVEN. None of
these closes an EV item (FD-EV-001 / ARE-EV-010 / PR-EV-005 are EV-L2+; design #11 §1).
"""

from __future__ import annotations

from decimal import Decimal

from tos.protective import (
    AggregateRiskComparison,
    IntermediateStateWitness,
    ProtectiveActionOutcome,
    protective_classification,
    protective_classification_present,
)

from ._protective_strategies import proven_comparison, proven_intermediate

# ---------------------------------------------------------------------------
# Purity — strategy label is not an input (§4.3)
# ---------------------------------------------------------------------------

_FORBIDDEN_LABEL_FIELDS = (
    "strategy_flag",
    "sell_direction",
    "exit_name",
    "reduce_intent",
    "operator_description",
    "correlation",
)


def test_classification_inputs_carry_no_strategy_label() -> None:
    """(§4.3) The classifier's input models expose NO strategy-label field (non-authoritative)."""
    for model in (AggregateRiskComparison, IntermediateStateWitness):
        for banned in _FORBIDDEN_LABEL_FIELDS:
            assert (
                banned not in model.model_fields
            ), f"{model.__name__}.{banned} present"


# ---------------------------------------------------------------------------
# both-ways
# ---------------------------------------------------------------------------


def test_proven_move_is_protective_proven() -> None:
    """(§5.3 canary b) final < current ∧ worst <= no-action ∧ bounded ∧ within envelope => PROVEN."""
    outcome = protective_classification(
        proven_comparison(), proven_intermediate(), envelope_within_hard=True
    )
    assert outcome is ProtectiveActionOutcome.PROTECTIVE_PROVEN
    assert (
        protective_classification_present(
            proven_comparison(), proven_intermediate(), envelope_within_hard=True
        )
        is True
    )


def test_final_not_below_current_is_denied() -> None:
    """(§5.3 canary a) final >= current => RISK_INCREASING_DENIED (label cannot override)."""
    comparison = proven_comparison(
        final_conservative_risk=Decimal("5.0"), current_conservative_risk=Decimal("5.0")
    )
    outcome = protective_classification(
        comparison, proven_intermediate(), envelope_within_hard=True
    )
    assert outcome is ProtectiveActionOutcome.RISK_INCREASING_DENIED
    assert (
        protective_classification_present(
            comparison, proven_intermediate(), envelope_within_hard=True
        )
        is False
    )


def test_worst_intermediate_above_no_action_is_denied() -> None:
    """(§5.3 canary a) worst-intermediate > no-action => RISK_INCREASING_DENIED."""
    intermediate = proven_intermediate(worst_intermediate_risk=Decimal("6.0"))
    outcome = protective_classification(
        proven_comparison(), intermediate, envelope_within_hard=True
    )
    assert outcome is ProtectiveActionOutcome.RISK_INCREASING_DENIED


def test_intermediate_increases_exceedance_is_denied() -> None:
    """(§6.2) A credible intermediate that increases exceedance => RISK_INCREASING_DENIED."""
    intermediate = proven_intermediate(
        no_credible_intermediate_increases_exceedance=None
    )
    outcome = protective_classification(
        proven_comparison(), intermediate, envelope_within_hard=True
    )
    assert outcome is ProtectiveActionOutcome.RISK_INCREASING_DENIED


def test_unbounded_credible_space_is_unknown() -> None:
    """(§6.2 line 277 canary a) An unbounded credible state space => UNKNOWN_CONSERVATIVE."""
    for bounded in (False, None):
        intermediate = proven_intermediate(credible_space_bounded=bounded)
        outcome = protective_classification(
            proven_comparison(), intermediate, envelope_within_hard=True
        )
        assert outcome is ProtectiveActionOutcome.UNKNOWN_CONSERVATIVE


def test_none_magnitude_is_denied_not_proven() -> None:
    """(§5.3) Any None aggregate-risk magnitude => RISK_INCREASING_DENIED (cannot prove)."""
    comparison = proven_comparison(final_conservative_risk=None)
    outcome = protective_classification(
        comparison, proven_intermediate(), envelope_within_hard=True
    )
    assert outcome is ProtectiveActionOutcome.RISK_INCREASING_DENIED


def test_outside_hard_envelope_is_denied_in_normal_regime() -> None:
    """(§6.1) In the normal regime, final outside the Hard Safety Envelope => denied."""
    for envelope in (False, None):
        outcome = protective_classification(
            proven_comparison(), proven_intermediate(), envelope_within_hard=envelope
        )
        assert outcome is ProtectiveActionOutcome.RISK_INCREASING_DENIED


def test_already_exceeded_regime_allows_non_worsening_return() -> None:
    """(§6.1 line 263) In the already-exceeded regime, a non-worsening return is PROVEN."""
    comparison = proven_comparison(
        already_exceeded_regime=True,
        final_conservative_risk=Decimal("5.0"),
        current_conservative_risk=Decimal("5.0"),
    )
    # No within-envelope requirement in the already-exceeded regime — a single action need
    # not restore the full envelope, only avoid worsening + not increase exceedance.
    outcome = protective_classification(
        comparison, proven_intermediate(), envelope_within_hard=None
    )
    assert outcome is ProtectiveActionOutcome.PROTECTIVE_PROVEN


def test_already_exceeded_regime_worsening_is_denied() -> None:
    """(§6.1 line 263) In the already-exceeded regime, a worsening move is still denied."""
    comparison = proven_comparison(
        already_exceeded_regime=True,
        final_conservative_risk=Decimal("6.0"),
        current_conservative_risk=Decimal("5.0"),
    )
    outcome = protective_classification(
        comparison, proven_intermediate(), envelope_within_hard=None
    )
    assert outcome is ProtectiveActionOutcome.RISK_INCREASING_DENIED
