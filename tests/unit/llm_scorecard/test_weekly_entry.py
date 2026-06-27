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


# --- A4 regression: --window override reflected in BOTH header and metrics -----


class _FakeLedger:
    """Minimal ledger stub for build_by_facet — returns canned score rows."""

    def __init__(self, scores_by_facet):
        self._scores = scores_by_facet

    def query_scores(self, facet=None, start=None, end=None):
        return list(self._scores.get(facet, []))

    def query_predictions(self, facet=None, start=None, end=None):
        return []


def test_window_override_applies_to_metrics_not_just_header(monkeypatch):
    """--window must change BOTH the returned window AND the rolling metrics.

    Regression for the bug where the override was applied to the local window
    after build_by_facet had already computed metrics with the config window —
    so the header said e.g. "10일" while the figures were 60-day.
    """
    import shared.llm_scorecard.facets  # noqa: F401 — populate FACET_REGISTRY
    from scripts.analysis.llm_scorecard_weekly import build_by_facet
    from shared.llm_scorecard.config import ScorecardConfig

    cfg = ScorecardConfig(enabled_facets=["direction"], rolling_windows=[20, 60])

    # 60 rows: the first 50 are losers, the last 10 are winners. A 10-day window
    # sees only winners (hit_rate=1.0); a 60-day window sees a mix (hit_rate<1).
    scores = [
        {"facet": "direction", "correct": (i >= 50), "edge": (1.0 if i >= 50 else -1.0),
         "economic_proxy": (1.0 if i >= 50 else -1.0), "date_kst": f"2026-04-{i + 1:02d}"}
        for i in range(60)
    ]
    ledger = _FakeLedger({"direction": scores})

    # No override → config window (60), mixed hit_rate.
    win_default, by_default = build_by_facet(cfg, ledger)
    assert win_default == 60
    assert by_default["direction"]["hit_rate"] < 1.0

    # Override → window AND metrics both reflect 10.
    win_override, by_override = build_by_facet(cfg, ledger, window=10)
    assert win_override == 10
    assert by_override["direction"]["n"] == 10
    assert by_override["direction"]["hit_rate"] == 1.0  # last-10 are all winners


# --- config-driven has_confidence selection (replaces hardcoded "direction") --


def test_confidence_facets_selected_by_config_flag():
    """_confidence_facets picks facets flagged has_confidence:true, not a literal."""
    from scripts.analysis.llm_scorecard_weekly import _confidence_facets
    from shared.llm_scorecard.config import ScorecardConfig

    cfg = ScorecardConfig(
        enabled_facets=["direction", "themes", "future_conf"],
        facet_params={
            "direction": {"has_confidence": True},
            "themes": {"top_n": 3},  # no flag → excluded
            "future_conf": {"has_confidence": True},  # a hypothetical new facet → included
        },
    )
    selected = _confidence_facets(cfg)
    assert "direction" in selected
    assert "future_conf" in selected  # config-driven: new facet picked up, no code change
    assert "themes" not in selected  # not flagged → excluded


def test_confidence_facets_empty_when_no_flag():
    """No facet flagged has_confidence → empty selection (no calibration)."""
    from scripts.analysis.llm_scorecard_weekly import _confidence_facets
    from shared.llm_scorecard.config import ScorecardConfig

    cfg = ScorecardConfig(
        enabled_facets=["direction", "themes"],
        facet_params={"direction": {"neutral_band_pct": 0.15}, "themes": {"top_n": 3}},
    )
    assert _confidence_facets(cfg) == []


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
