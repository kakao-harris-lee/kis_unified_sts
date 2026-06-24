"""Tests for the reporter (plan Task 8) — pure format_daily / format_weekly."""
from __future__ import annotations

from shared.llm_scorecard.reporter import format_daily, format_weekly


def _score_row(facet="direction", correct=True, edge=1.2, predicted="BULL", realized="BULL", ret=1.2):
    return {
        "facet": facet,
        "correct": correct,
        "edge": edge,
        "detail": {"predicted": predicted, "realized": realized, "ret_pct": ret},
    }


def test_daily_shows_per_facet_result_and_rolling():
    # Ported from plan Task 8.
    rows = [_score_row()]
    msg = format_daily("2026-06-25", rows, {"hit_rate": 0.55, "n_scored": 20, "mean_edge": 0.3})
    assert "direction" in msg
    assert "✅" in msg
    assert "1.2" in msg
    assert "55" in msg


def test_daily_contains_date():
    msg = format_daily("2026-06-20", [_score_row()], {"hit_rate": 0.5, "n_scored": 1, "mean_edge": 0.0})
    assert "2026-06-20" in msg


def test_daily_incorrect_shows_cross():
    msg = format_daily("2026-06-20", [_score_row(correct=False, edge=-1.0)], {})
    assert "❌" in msg


def test_daily_unscorable_shows_white_circle():
    rows = [_score_row(correct=None, edge=0.0, predicted="BULL", realized="?")]
    msg = format_daily("2026-06-20", rows, {})
    assert "⚪" in msg
    assert "❌" not in msg


def test_daily_empty_scores_still_renders_rolling():
    msg = format_daily("2026-06-20", [], {"hit_rate": None, "n_scored": 0, "mean_edge": 0.0})
    assert "2026-06-20" in msg
    assert "n/a" in msg  # hit_rate None → n/a


def test_daily_rolling_none_hit_rate():
    msg = format_daily("2026-06-20", [_score_row()], {"hit_rate": None, "n_scored": 0, "mean_edge": 0.0})
    assert "n/a" in msg


def test_weekly_contains_window_and_facets():
    by_facet = {
        "direction": {"hit_rate": 0.6, "mean_edge": 0.4, "econ_proxy_sum": 5.2, "n_scored": 30},
    }
    msg = format_weekly(60, by_facet)
    assert "60" in msg
    assert "direction" in msg
    assert "유용" in msg  # mean_edge > 0 and hit_rate > 0.5


def test_weekly_marks_unproven():
    by_facet = {
        "direction": {"hit_rate": 0.4, "mean_edge": -0.1, "econ_proxy_sum": -1.0, "n_scored": 30},
    }
    msg = format_weekly(60, by_facet)
    assert "미입증" in msg


def test_weekly_handles_none_hit_rate():
    by_facet = {"direction": {"hit_rate": None, "mean_edge": 0.0, "econ_proxy_sum": 0.0, "n_scored": 0}}
    msg = format_weekly(60, by_facet)
    assert "n/a" in msg
    assert "미입증" in msg
