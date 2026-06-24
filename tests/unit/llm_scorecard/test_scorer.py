"""Tests for DayScorer."""
from __future__ import annotations

from datetime import date, datetime

import pytest

from shared.llm_scorecard.config import ScorecardConfig
from shared.llm_scorecard.facets.base import (
    FACET_REGISTRY,
    FacetPrediction,
    FacetScore,
    register_facet,
)
from shared.llm_scorecard.scorer import DayScorer


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
        return 1.0 / 3.0


def _pred_row(facet_name="test_facet", date_kst="2026-06-20"):
    return {
        "facet": facet_name,
        "date_kst": date_kst,
        "captured_at": "2026-06-20T09:00:00",
        "payload": {"direction": "BULL"},
        "payload_json": '{"direction": "BULL"}',
        "confidence": 0.7,
        "created_at": "2026-06-20T09:00:00",
    }


def _make_score(facet="test_facet", date_kst="2026-06-20"):
    return FacetScore(
        facet=facet,
        date_kst=date_kst,
        correct=True,
        value=1.0,
        economic_proxy=0.5,
        baseline_value=1.0 / 3.0,
        edge=1.0 - 1.0 / 3.0,
        detail={"predicted": "BULL", "actual": "BULL", "return_pct": 0.5},
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


def test_score_day_returns_scores_and_saves(registry_snapshot):
    score = _make_score()
    facet = FakeScoringFacet("test_facet", score_return=score)
    register_facet(facet)

    ledger = FakeLedger(predictions=[_pred_row()])
    scorer = DayScorer(ScorecardConfig(), ledger, FakeOutcome())
    scores = scorer.score_day(date(2026, 6, 20))

    assert len(scores) == 1
    assert scores[0] is score
    assert len(ledger.saved_scores) == 1
    assert ledger.saved_scores[0]["facet"] == "test_facet"


def test_score_day_skips_none_score(registry_snapshot):
    facet = FakeScoringFacet("test_facet_none", score_return=None)
    register_facet(facet)

    ledger = FakeLedger(predictions=[_pred_row(facet_name="test_facet_none")])
    scorer = DayScorer(ScorecardConfig(), ledger, FakeOutcome())
    scores = scorer.score_day(date(2026, 6, 20))

    assert scores == []
    assert ledger.saved_scores == []


def test_score_day_skips_unknown_facet(registry_snapshot):
    """A pred row with a facet name not in registry is skipped gracefully."""
    ledger = FakeLedger(predictions=[_pred_row(facet_name="unknown_facet_xyz")])
    scorer = DayScorer(ScorecardConfig(), ledger, FakeOutcome())
    scores = scorer.score_day(date(2026, 6, 20))

    assert scores == []


def test_score_day_swallows_score_exception(registry_snapshot):
    class ErrorFacet:
        name = "error_facet"
        outcome_horizon = "session"
        outcome_source = "test"

        def score(self, pred, outcome):
            raise RuntimeError("score error")

        def baseline(self, pred, mkt):
            return 1.0 / 3.0

    register_facet(ErrorFacet())
    good_score = _make_score(facet="good_facet")
    good_facet = FakeScoringFacet("good_facet", score_return=good_score)
    register_facet(good_facet)

    ledger = FakeLedger(predictions=[
        _pred_row(facet_name="error_facet"),
        _pred_row(facet_name="good_facet"),
    ])
    scorer = DayScorer(ScorecardConfig(), ledger, FakeOutcome())
    scores = scorer.score_day(date(2026, 6, 20))

    # error_facet raised, good_facet still ran
    assert len(scores) == 1
    assert scores[0].facet == "good_facet"


def test_score_day_scored_at_isoformat(registry_snapshot):
    score = _make_score()
    facet = FakeScoringFacet("iso_facet", score_return=score)
    register_facet(facet)

    ledger = FakeLedger(predictions=[_pred_row(facet_name="iso_facet")])
    scorer = DayScorer(ScorecardConfig(), ledger, FakeOutcome())
    scorer.score_day(date(2026, 6, 20))

    saved = ledger.saved_scores[0]
    assert saved["scored_at"] == "2026-06-20T16:00:00"
