"""Tests for the reporter (plan Task 8 / Task 14) — pure format_daily / format_weekly / format_calibration."""
from __future__ import annotations

from shared.llm_scorecard.reporter import format_daily, format_weekly, format_calibration


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


# --- format_calibration (Task 14) ---


def test_format_calibration_renders_bins():
    """Bins with data must show conf range, hit %, and count (plan Task 14)."""
    bins = [
        {"lo": 0.8, "hi": 1.0, "n": 12, "hit_rate": 0.70},
        {"lo": 0.6, "hi": 0.8, "n": 8,  "hit_rate": 0.55},
        {"lo": 0.4, "hi": 0.6, "n": 0,  "hit_rate": None},   # empty bin
        {"lo": 0.2, "hi": 0.4, "n": 0,  "hit_rate": None},
        {"lo": 0.0, "hi": 0.2, "n": 0,  "hit_rate": None},
    ]
    msg = format_calibration(bins)
    # High-confidence bin
    assert "0.8" in msg and "0.9" not in msg or "1.0" in msg   # range shown
    assert "70%" in msg
    assert "n=12" in msg
    # Medium-confidence bin
    assert "0.6" in msg
    assert "55%" in msg
    assert "n=8" in msg
    # Empty bins should be omitted or clearly marked
    assert "n=0" not in msg or "–" in msg or "n/a" in msg


def test_format_calibration_all_empty_returns_no_data():
    """When all bins are empty, the output must signal no calibration data."""
    bins = [
        {"lo": lo / 5, "hi": (lo + 1) / 5, "n": 0, "hit_rate": None}
        for lo in range(5)
    ]
    msg = format_calibration(bins)
    # Must not crash; should communicate absence
    assert msg  # non-empty string
    assert "n=0" not in msg or "no" in msg.lower() or "–" in msg or "n/a" in msg


def test_format_calibration_single_bin_renders():
    """Single populated bin should render correctly."""
    bins = [{"lo": 0.8, "hi": 1.0, "n": 5, "hit_rate": 0.80}]
    msg = format_calibration(bins)
    assert "80%" in msg
    assert "n=5" in msg
