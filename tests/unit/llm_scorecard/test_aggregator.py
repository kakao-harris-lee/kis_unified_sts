"""Tests for the aggregator (plan Task 7) — pure rolling_metrics / calibration_bins."""
from __future__ import annotations

from shared.llm_scorecard.aggregator import calibration_bins, rolling_metrics


def test_rolling_metrics_ignores_unscorable():
    # Ported verbatim from plan Task 7.
    scores = [
        {"correct": True, "edge": 1.0, "economic_proxy": 1.0},
        {"correct": None, "edge": 0.0, "economic_proxy": 0.0},
        {"correct": False, "edge": -0.5, "economic_proxy": -0.5},
    ]
    m = rolling_metrics(scores, window=60)
    assert m["n"] == 3
    assert m["n_scored"] == 2
    assert m["hit_rate"] == 0.5
    assert round(m["mean_edge"], 3) == round((1.0 - 0.5 + 0.0) / 3, 3)  # edge over ALL rows
    assert round(m["econ_proxy_sum"], 2) == 0.5


def test_rolling_metrics_empty():
    m = rolling_metrics([], window=30)
    assert m == {"n": 0, "n_scored": 0, "hit_rate": None, "mean_edge": 0.0, "econ_proxy_sum": 0.0}


def test_rolling_metrics_all_unscorable_hit_rate_none():
    scores = [{"correct": None, "edge": 0.0, "economic_proxy": 0.0}]
    m = rolling_metrics(scores, window=30)
    assert m["n_scored"] == 0
    assert m["hit_rate"] is None


def test_rolling_metrics_respects_window():
    scores = [{"correct": i % 2 == 0, "edge": 0.0, "economic_proxy": 0.0} for i in range(10)]
    m = rolling_metrics(scores, window=3)
    assert m["n"] == 3  # only the last 3 rows


def test_calibration_bins_group_by_confidence():
    # Ported from plan Task 7.
    scores = [{"date_kst": "d1", "correct": True}, {"date_kst": "d2", "correct": False}]
    conf = {"d1": 0.9, "d2": 0.4}
    bins = calibration_bins(scores, conf)
    assert any(b["lo"] <= 0.9 < b["hi"] and b["hit_rate"] == 1.0 for b in bins)
    assert any(b["lo"] <= 0.4 < b["hi"] and b["hit_rate"] == 0.0 for b in bins)


def test_calibration_bins_excludes_unscorable_and_missing_conf():
    scores = [
        {"date_kst": "d1", "correct": None},   # unscorable
        {"date_kst": "d2", "correct": True},   # no conf entry
    ]
    bins = calibration_bins(scores, {})
    assert all(b["n"] == 0 and b["hit_rate"] is None for b in bins)


def test_calibration_bins_count_default_five():
    assert len(calibration_bins([], {})) == 5
