"""Tests for the scorer (plan Task 7) — module-level score_day."""
from __future__ import annotations

from datetime import datetime

import pytest

from shared.llm_scorecard.config import ScorecardConfig
from shared.llm_scorecard.facets.base import (
    FACET_REGISTRY,
    FacetScore,
    register_facet,
)
from shared.llm_scorecard.scorer import score_day


@pytest.fixture
def registry_snapshot():
    snapshot = dict(FACET_REGISTRY)
    yield
    FACET_REGISTRY.clear()
    FACET_REGISTRY.update(snapshot)


class FakeScoringFacet:
    def __init__(self, name, score_return):
        self.name = name
        self.outcome_horizon = "session"
        self.outcome_source = "test"
        self._score_return = score_return

    def score(self, pred, outcome):
        return self._score_return

    def baseline(self, pred, mkt):
        return 0.0


def _pred_row(facet_name="test_facet", date_kst="2026-06-20"):
    return {
        "facet": facet_name,
        "date_kst": date_kst,
        "captured_at": "2026-06-20T09:00:00",
        "payload": {"direction": "BULL"},
        "confidence": 0.7,
    }


def _score(facet="test_facet", correct=True, date_kst="2026-06-20"):
    return FacetScore(
        facet=facet,
        date_kst=date_kst,
        correct=correct,
        value=0.5,
        economic_proxy=0.5,
        baseline_value=0.0,
        edge=0.5,
        detail={"predicted": "BULL", "realized": "BULL", "ret_pct": 0.5},
        scored_at=datetime(2026, 6, 20, 16, 0, 0),
    )


def _unscorable(facet="test_facet", date_kst="2026-06-20"):
    return FacetScore(
        facet=facet,
        date_kst=date_kst,
        correct=None,
        value=0.0,
        economic_proxy=0.0,
        baseline_value=0.0,
        edge=0.0,
        detail={"reason": "no_outcome_data"},
        scored_at=datetime(2026, 6, 20, 16, 0, 0),
    )


class FakeLedger:
    def __init__(self, predictions=None):
        self._predictions = predictions or []
        self.saved_scores = []

    def load_predictions(self, date_str):
        return [p for p in self._predictions if p["date_kst"] == date_str]

    def save_score(self, s):
        self.saved_scores.append(s)


class FakeOutcome:
    pass


def test_score_day_writes_score_per_facet(registry_snapshot):
    register_facet(FakeScoringFacet("direction", score_return=_score("direction")))
    led = FakeLedger(predictions=[_pred_row("direction")])
    n = score_day("2026-06-20", ScorecardConfig(enabled_facets=["direction"]), led, FakeOutcome())
    assert n == 1
    assert led.saved_scores[0]["facet"] == "direction"
    assert led.saved_scores[0]["correct"] is True


def test_score_day_persists_unscorable_with_correct_none(registry_snapshot):
    register_facet(FakeScoringFacet("direction", score_return=_unscorable("direction")))
    led = FakeLedger(predictions=[_pred_row("direction")])
    n = score_day("2026-06-20", ScorecardConfig(enabled_facets=["direction"]), led, FakeOutcome())
    assert n == 1  # persisted, not skipped
    assert len(led.saved_scores) == 1
    assert led.saved_scores[0]["correct"] is None


def test_score_day_filters_by_enabled_facets(registry_snapshot):
    """A facet that has a stored prediction but is NOT enabled must not be scored."""
    register_facet(FakeScoringFacet("direction", score_return=_score("direction")))
    register_facet(FakeScoringFacet("themes", score_return=_score("themes")))
    led = FakeLedger(predictions=[_pred_row("direction"), _pred_row("themes")])
    n = score_day("2026-06-20", ScorecardConfig(enabled_facets=["direction"]), led, FakeOutcome())
    assert n == 1
    assert {s["facet"] for s in led.saved_scores} == {"direction"}


def test_score_day_skips_facet_with_no_prediction(registry_snapshot):
    register_facet(FakeScoringFacet("direction", score_return=_score("direction")))
    led = FakeLedger(predictions=[])
    n = score_day("2026-06-20", ScorecardConfig(enabled_facets=["direction"]), led, FakeOutcome())
    assert n == 0
    assert led.saved_scores == []


def test_score_day_swallows_score_exception(registry_snapshot):
    class ErrorFacet:
        name = "direction"
        outcome_horizon = "session"
        outcome_source = "test"

        def score(self, pred, outcome):
            raise RuntimeError("score error")

        def baseline(self, pred, mkt):
            return 0.0

    register_facet(ErrorFacet())
    led = FakeLedger(predictions=[_pred_row("direction")])
    n = score_day("2026-06-20", ScorecardConfig(enabled_facets=["direction"]), led, FakeOutcome())
    assert n == 0  # raised, swallowed


def test_score_day_scored_at_isoformat(registry_snapshot):
    register_facet(FakeScoringFacet("direction", score_return=_score("direction")))
    led = FakeLedger(predictions=[_pred_row("direction")])
    score_day("2026-06-20", ScorecardConfig(enabled_facets=["direction"]), led, FakeOutcome())
    assert led.saved_scores[0]["scored_at"] == "2026-06-20T16:00:00"
