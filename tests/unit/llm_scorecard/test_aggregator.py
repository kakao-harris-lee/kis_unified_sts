"""Tests for RollingAggregator."""
from __future__ import annotations

import pytest

from shared.llm_scorecard.aggregator import RollingAggregator
from shared.llm_scorecard.config import ScorecardConfig


def _make_score_row(date_kst, correct, baseline=1.0 / 3.0, facet="direction"):
    return {
        "date_kst": date_kst,
        "facet": facet,
        "correct": correct,
        "value": 1.0 if correct else 0.0,
        "economic_proxy": 0.3,
        "baseline_value": baseline,
        "edge": (1.0 if correct else 0.0) - baseline,
        "detail": {},
        "scored_at": date_kst + "T16:00:00",
    }


def _pred_row(date_kst, confidence, facet="direction"):
    return {
        "date_kst": date_kst,
        "facet": facet,
        "captured_at": date_kst + "T09:00:00",
        "payload": {"direction": "BULL"},
        "payload_json": '{"direction": "BULL"}',
        "confidence": confidence,
        "created_at": date_kst + "T09:00:00",
    }


class FakeLedger:
    def __init__(self, scores=None, predictions=None):
        self._scores = scores or []
        self._predictions = predictions or []

    def query_scores(self, facet=None, start=None, end=None):
        rows = self._scores
        if facet:
            rows = [r for r in rows if r["facet"] == facet]
        if start:
            rows = [r for r in rows if r["date_kst"] >= start]
        if end:
            rows = [r for r in rows if r["date_kst"] <= end]
        return rows

    def load_predictions(self, date_kst):
        return [p for p in self._predictions if p["date_kst"] == date_kst]


def test_rolling_metrics_basic():
    scores = [
        _make_score_row("2026-06-20", correct=True),
        _make_score_row("2026-06-19", correct=False),
        _make_score_row("2026-06-18", correct=True),
    ]
    ledger = FakeLedger(scores=scores)
    agg = RollingAggregator(ScorecardConfig(), ledger)
    m = agg.rolling_metrics("direction", 30)

    assert m["n"] == 3
    assert m["correct"] == 2
    assert m["accuracy"] == pytest.approx(2 / 3)
    baseline = 1.0 / 3.0
    assert m["edge"] == pytest.approx(2 / 3 - baseline)


def test_rolling_metrics_empty():
    ledger = FakeLedger(scores=[])
    agg = RollingAggregator(ScorecardConfig(), ledger)
    m = agg.rolling_metrics("direction", 30)

    assert m == {"accuracy": 0.0, "edge": 0.0, "n": 0, "correct": 0}


def test_calibration_bins_groups_by_confidence():
    scores = [
        _make_score_row("2026-06-20", correct=True),
        _make_score_row("2026-06-19", correct=False),
    ]
    preds = [
        _pred_row("2026-06-20", confidence=0.9),   # high bin (bin 4: 0.8–1.0)
        _pred_row("2026-06-19", confidence=0.2),   # low bin (bin 1: 0.2–0.4)
    ]
    ledger = FakeLedger(scores=scores, predictions=preds)
    agg = RollingAggregator(ScorecardConfig(), ledger)
    cal = agg.calibration_bins("direction", n_bins=5)

    assert len(cal) >= 1
    high_bins = [b for b in cal if b["bin_low"] >= 0.8]
    low_bins = [b for b in cal if b["bin_low"] >= 0.2 and b["bin_low"] < 0.4]
    assert high_bins[0]["accuracy"] == 1.0   # 2026-06-20 correct=True at conf 0.9
    assert low_bins[0]["accuracy"] == 0.0    # 2026-06-19 correct=False at conf 0.2


def test_calibration_bins_returns_empty_when_no_data():
    ledger = FakeLedger(scores=[], predictions=[])
    agg = RollingAggregator(ScorecardConfig(), ledger)
    cal = agg.calibration_bins("direction")

    assert cal == []


def test_calibration_bins_skips_no_confidence():
    scores = [_make_score_row("2026-06-20", correct=True)]
    # pred has no confidence
    preds = [_pred_row("2026-06-20", confidence=None)]
    ledger = FakeLedger(scores=scores, predictions=preds)
    agg = RollingAggregator(ScorecardConfig(), ledger)
    cal = agg.calibration_bins("direction")

    assert cal == []
