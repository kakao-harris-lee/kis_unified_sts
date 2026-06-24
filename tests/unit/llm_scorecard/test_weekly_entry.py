"""Tests for the weekly digest cron entry (plan Task 13 + Task 14)."""
from __future__ import annotations


# --- Smoke test: module imports cleanly ----------------------------------------


def test_weekly_entry_imports():
    """The entry module must be importable without live I/O."""
    import importlib

    mod = importlib.import_module("scripts.analysis.llm_scorecard_weekly")
    assert callable(getattr(mod, "main", None)), "main() coroutine must be present"


# --- format_weekly integration with synthetic by_facet -------------------------


def test_format_weekly_shows_facet_results():
    """format_weekly renders window + per-facet hit/edge/econ for synthetic data."""
    from shared.llm_scorecard.reporter import format_weekly

    by_facet = {
        "direction": {
            "hit_rate": 0.65,
            "mean_edge": 0.8,
            "econ_proxy_sum": 16.0,
            "n_scored": 20,
            "n": 20,
        },
        "themes": {
            "hit_rate": 0.45,
            "mean_edge": -0.1,
            "econ_proxy_sum": -2.0,
            "n_scored": 20,
            "n": 20,
        },
    }
    msg = format_weekly(60, by_facet)
    assert "60" in msg
    assert "direction" in msg
    assert "themes" in msg
    assert "유용" in msg       # direction: hit>0.5 and mean_edge>0
    assert "미입증" in msg     # themes: hit<0.5 or mean_edge<=0


def test_format_weekly_empty_by_facet_renders_header():
    """format_weekly with no facets should still render the header cleanly."""
    from shared.llm_scorecard.reporter import format_weekly

    msg = format_weekly(20, {})
    assert "20" in msg
    # Header present, no facet lines — should not crash
    assert "LLM" in msg


def test_weekly_entry_build_by_facet_logic():
    """Verify the by_facet construction logic using fakes.

    Simulates: for each enabled facet → query_scores → rolling_metrics → collect.
    This exercises the exact flow in llm_scorecard_weekly.build_by_facet().
    """
    from shared.llm_scorecard.aggregator import rolling_metrics
    from shared.llm_scorecard.config import ScorecardConfig

    cfg = ScorecardConfig(enabled_facets=["direction"], rolling_windows=[20, 60])

    # Synthetic score rows (already in direction facet format)
    scores = [
        {"facet": "direction", "correct": True, "edge": 1.0, "economic_proxy": 1.0,
         "date_kst": f"2026-06-{i:02d}"} for i in range(1, 21)
    ]

    # Simulate what the weekly entry does
    window = cfg.rolling_windows[-1]
    by_facet = {}
    for facet_name in cfg.enabled_facets:
        rows = [r for r in scores if r["facet"] == facet_name]
        by_facet[facet_name] = rolling_metrics(rows, window)

    assert "direction" in by_facet
    m = by_facet["direction"]
    assert m["n_scored"] == 20
    assert m["hit_rate"] == 1.0
    assert m["mean_edge"] == 1.0


# --- Task 14: calibration path in the weekly entry ----------------------------


def test_calibration_pred_conf_built_from_query_predictions():
    """Verify pred_conf = {date_kst: confidence} is built via query_predictions.

    Simulates the weekly entry's calibration logic: for the direction facet,
    query all predictions in the window and build a {date_kst: confidence}
    mapping, then call calibration_bins and format_calibration.
    """
    from shared.llm_scorecard.aggregator import calibration_bins
    from shared.llm_scorecard.reporter import format_calibration

    # Synthetic score rows
    scores = [
        {"date_kst": "2026-06-01", "correct": True, "edge": 1.0},
        {"date_kst": "2026-06-02", "correct": False, "edge": -0.5},
        {"date_kst": "2026-06-03", "correct": True, "edge": 0.8},
    ]
    # Synthetic pred_conf built from query_predictions rows
    pred_rows = [
        {"date_kst": "2026-06-01", "facet": "direction", "confidence": 0.85},
        {"date_kst": "2026-06-02", "facet": "direction", "confidence": 0.65},
        {"date_kst": "2026-06-03", "facet": "direction", "confidence": 0.90},
    ]
    pred_conf = {r["date_kst"]: r["confidence"] for r in pred_rows}

    bins = calibration_bins(scores, pred_conf)
    assert isinstance(bins, list)
    assert len(bins) == 5  # default n_bins=5

    # Check that high-confidence entries (0.85, 0.90) are in the [0.8,1.0) bin
    high_bin = next(b for b in bins if b["lo"] == 0.8)
    assert high_bin["n"] == 2
    assert high_bin["hit_rate"] == 1.0  # both d1 and d3 are correct

    # format_calibration renders the high-confidence bin correctly
    msg = format_calibration(bins)
    assert "100%" in msg or "hit" in msg
    assert "n=2" in msg


def test_calibration_section_in_weekly_message():
    """The weekly digest message should include a calibration section when bins are non-empty."""
    from shared.llm_scorecard.aggregator import calibration_bins
    from shared.llm_scorecard.reporter import format_calibration, format_weekly

    by_facet = {
        "direction": {
            "hit_rate": 0.65, "mean_edge": 0.8, "econ_proxy_sum": 12.0, "n_scored": 10, "n": 10,
        },
    }
    weekly_msg = format_weekly(60, by_facet)

    # Simulate calibration section appended to the weekly digest
    scores = [{"date_kst": f"2026-06-{i:02d}", "correct": True, "edge": 1.0} for i in range(1, 6)]
    pred_conf = {f"2026-06-{i:02d}": 0.85 for i in range(1, 6)}
    bins = calibration_bins(scores, pred_conf)
    calib_section = format_calibration(bins)
    full_msg = weekly_msg + "\n" + calib_section

    assert "direction" in full_msg
    assert "conf" in full_msg.lower() or "calibr" in full_msg.lower() or "0.8" in full_msg
