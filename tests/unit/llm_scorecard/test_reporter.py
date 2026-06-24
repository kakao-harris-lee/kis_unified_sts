"""Tests for DailyScorecardReporter."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from shared.llm_scorecard.aggregator import RollingAggregator
from shared.llm_scorecard.config import ScorecardConfig
from shared.llm_scorecard.reporter import DailyScorecardReporter


def _score_row(facet="direction", correct=True, actual="BULL", ret=0.3):
    return {
        "facet": facet,
        "date_kst": "2026-06-20",
        "correct": correct,
        "value": 1.0 if correct else 0.0,
        "economic_proxy": ret,
        "baseline_value": 1.0 / 3.0,
        "edge": (1.0 if correct else 0.0) - 1.0 / 3.0,
        "detail": {"predicted": "BULL", "actual": actual, "return_pct": ret},
        "scored_at": "2026-06-20T16:00:00",
    }


def _pred_row(facet="direction", direction="BULL"):
    return {
        "facet": facet,
        "date_kst": "2026-06-20",
        "captured_at": "2026-06-20T09:00:00",
        "payload": {"direction": direction, "overall_signal": "상승"},
        "payload_json": '{}',
        "confidence": 0.7,
        "created_at": "2026-06-20T09:00:00",
    }


class FakeLedger:
    def __init__(self, preds=None, scores=None):
        self._preds = preds or []
        self._scores = scores or []

    def load_predictions(self, date_kst):
        return [p for p in self._preds if p["date_kst"] == date_kst]

    def query_scores(self, facet=None, start=None, end=None):
        rows = self._scores
        if facet:
            rows = [r for r in rows if r["facet"] == facet]
        if start:
            rows = [r for r in rows if r["date_kst"] >= start]
        if end:
            rows = [r for r in rows if r["date_kst"] <= end]
        return rows


def _make_reporter(preds=None, scores=None, windows=None):
    cfg = ScorecardConfig(
        enabled_facets=["direction"],
        rolling_windows=windows or [20, 60],
    )
    ledger = FakeLedger(preds=preds, scores=scores)
    agg = RollingAggregator(cfg, ledger)
    return DailyScorecardReporter(cfg, agg, ledger)


def test_format_daily_contains_date():
    reporter = _make_reporter(
        preds=[_pred_row()],
        scores=[_score_row()],
    )
    result = reporter.format_daily(date(2026, 6, 20))
    assert "2026-06-20" in result


def test_format_daily_contains_facet_name():
    reporter = _make_reporter(
        preds=[_pred_row()],
        scores=[_score_row()],
    )
    result = reporter.format_daily(date(2026, 6, 20))
    assert "direction" in result


def test_format_daily_correct_shows_check_emoji():
    reporter = _make_reporter(
        preds=[_pred_row()],
        scores=[_score_row(correct=True, actual="BULL")],
    )
    result = reporter.format_daily(date(2026, 6, 20))
    assert "✅" in result


def test_format_daily_incorrect_shows_cross_emoji():
    reporter = _make_reporter(
        preds=[_pred_row()],
        scores=[_score_row(correct=False, actual="BEAR")],
    )
    result = reporter.format_daily(date(2026, 6, 20))
    assert "❌" in result


def test_format_daily_no_predictions():
    reporter = _make_reporter(preds=[], scores=[])
    result = reporter.format_daily(date(2026, 6, 20))
    assert "2026-06-20" in result
    assert "예측 없음" in result


def test_format_daily_unscored_prediction():
    reporter = _make_reporter(preds=[_pred_row()], scores=[])
    result = reporter.format_daily(date(2026, 6, 20))
    assert "미채점" in result


def test_format_daily_rolling_windows_shown_when_data():
    # Add enough scores that rolling_metrics returns n>0
    scores = [_score_row()]
    reporter = _make_reporter(
        preds=[_pred_row()],
        scores=scores,
        windows=[20],
    )
    result = reporter.format_daily(date(2026, 6, 20))
    assert "20일 정확도" in result


def test_format_weekly_contains_window_labels():
    reporter = _make_reporter(preds=[], scores=[], windows=[20, 60])
    result = reporter.format_weekly(date(2026, 6, 20))
    assert "20일" in result
    assert "60일" in result


def test_format_weekly_contains_date_range():
    reporter = _make_reporter(preds=[], scores=[])
    result = reporter.format_weekly(date(2026, 6, 20))
    assert "2026-06-13" in result
    assert "2026-06-20" in result


def test_format_weekly_contains_facet():
    reporter = _make_reporter(preds=[], scores=[])
    result = reporter.format_weekly(date(2026, 6, 20))
    assert "direction" in result
