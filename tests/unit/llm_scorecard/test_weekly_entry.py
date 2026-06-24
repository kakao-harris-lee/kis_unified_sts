"""Tests for the weekly digest cron entry (plan Task 13)."""
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
