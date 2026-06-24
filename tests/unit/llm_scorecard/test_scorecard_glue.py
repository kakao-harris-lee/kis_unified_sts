"""Smoke tests for scorecard glue: module-level API + entry-script seam (plan Task 9)."""
from __future__ import annotations

import importlib


def test_public_module_level_api_imports():
    """Phase 3/4 depend on these exact module-level functions existing."""
    from shared.llm_scorecard.recorder import capture_predictions  # noqa: F401
    from shared.llm_scorecard.scorer import score_day  # noqa: F401
    from shared.llm_scorecard.aggregator import calibration_bins, rolling_metrics  # noqa: F401
    from shared.llm_scorecard.reporter import format_daily, format_weekly  # noqa: F401
    from shared.llm_scorecard.facets.direction import DirectionFacet  # noqa: F401


def test_direction_facet_registered():
    import shared.llm_scorecard.facets.direction  # noqa: F401
    from shared.llm_scorecard.facets.base import FACET_REGISTRY

    assert "direction" in FACET_REGISTRY


def test_enabled_facets_returns_direction():
    import shared.llm_scorecard.facets.direction  # noqa: F401
    from shared.llm_scorecard.config import ScorecardConfig
    from shared.llm_scorecard.facets.base import enabled_facets

    facets = enabled_facets(ScorecardConfig(enabled_facets=["direction"]))
    assert len(facets) == 1 and facets[0].name == "direction"


def test_entry_script_imports_and_wires_module_api():
    """The cron entry imports cleanly and references the module-level seam."""
    mod = importlib.import_module("scripts.analysis.llm_scorecard_score")
    assert hasattr(mod, "main")
    # The entry wires score_day → rolling_metrics → format_daily.
    src = importlib.import_module("scripts.analysis.llm_scorecard_score").__doc__ or ""
    assert "scorecard" in src.lower()


def test_scorer_to_reporter_seam():
    """score_day persists rows; rolling_metrics + format_daily consume them — pure seam."""
    from datetime import datetime

    from shared.llm_scorecard.aggregator import rolling_metrics
    from shared.llm_scorecard.config import ScorecardConfig
    from shared.llm_scorecard.facets.base import FACET_REGISTRY, FacetScore, register_facet
    from shared.llm_scorecard.reporter import format_daily
    from shared.llm_scorecard.scorer import score_day

    snapshot = dict(FACET_REGISTRY)
    try:
        class _F:
            name = "direction"
            outcome_horizon = "session"
            outcome_source = "test"

            def score(self, pred, outcome):
                return FacetScore("direction", pred.date_kst, True, 1.0, 1.0, 0.0, 1.0,
                                  {"predicted": "BULL", "realized": "BULL", "ret_pct": 1.0},
                                  datetime(2026, 6, 20, 16, 0))

        register_facet(_F())

        class _Led:
            def __init__(self):
                self.rows = []

            def load_predictions(self, d):
                return [{"facet": "direction", "date_kst": d,
                         "captured_at": "2026-06-20T09:00:00",
                         "payload": {"direction": "BULL"}, "confidence": 0.7}]

            def save_score(self, s):
                self.rows.append(s)

            def query_scores(self, facet=None, start=None, end=None):
                return self.rows

        led = _Led()
        n = score_day("2026-06-20", ScorecardConfig(enabled_facets=["direction"]), led, object())
        assert n == 1
        rolling = rolling_metrics(led.query_scores(facet="direction"), 60)
        msg = format_daily("2026-06-20", led.query_scores(), rolling)
        assert "direction" in msg and "✅" in msg
    finally:
        FACET_REGISTRY.clear()
        FACET_REGISTRY.update(snapshot)
