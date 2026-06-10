"""BEAR_REGIMES single source (#459): membership, helper, enum coherence."""

from __future__ import annotations

import pytest

from shared.strategy.market_classifier import (
    BEAR_REGIMES,
    MarketClassifier,
    MarketState,
    is_bear_regime,
)


@pytest.mark.parametrize("regime", BEAR_REGIMES)
def test_is_bear_regime_true_for_bear_values(regime: str) -> None:
    assert is_bear_regime(regime)


@pytest.mark.parametrize(
    "regime", ["BULL_STRONG", "SIDEWAYS_DOWN", "UNKNOWN", "", None]
)
def test_is_bear_regime_false_otherwise(regime: str | None) -> None:
    assert not is_bear_regime(regime)


def test_bear_regimes_matches_classifier_is_bearish() -> None:
    """String membership and enum-based is_bearish must never diverge.

    Plain "BEAR" is the one extra string value (orchestrator avg-change
    warmup fallback produces it; classify() never does).
    """
    classifier = MarketClassifier()
    enum_bears = {s.value for s in MarketState if classifier.is_bearish(s)}
    assert set(BEAR_REGIMES) == enum_bears | {"BEAR"}


def test_classify_outputs_are_covered_by_bear_regimes() -> None:
    """Every bear classification classify() can produce is in BEAR_REGIMES."""
    classifier = MarketClassifier()
    assert classifier.classify(mfi=20.0, adx=0.0).value in BEAR_REGIMES  # BEAR_STRONG
    assert classifier.classify(mfi=38.0, adx=0.0).value in BEAR_REGIMES  # BEAR_MODERATE
    assert classifier.classify(mfi=55.0, adx=0.0).value not in BEAR_REGIMES
