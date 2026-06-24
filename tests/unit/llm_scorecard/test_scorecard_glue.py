"""Smoke tests for scorecard glue imports and registry wiring."""
from __future__ import annotations

import pytest


def test_imports_no_error():
    from shared.llm_scorecard.recorder import PredictionRecorder  # noqa: F401
    from shared.llm_scorecard.scorer import DayScorer  # noqa: F401
    from shared.llm_scorecard.aggregator import RollingAggregator  # noqa: F401
    from shared.llm_scorecard.reporter import DailyScorecardReporter  # noqa: F401
    from shared.llm_scorecard.facets.direction import DirectionFacet  # noqa: F401


def test_direction_facet_registered():
    import shared.llm_scorecard.facets.direction  # noqa: F401
    from shared.llm_scorecard.facets.base import FACET_REGISTRY

    assert "direction" in FACET_REGISTRY


def test_direction_facet_is_instance():
    import shared.llm_scorecard.facets.direction  # noqa: F401
    from shared.llm_scorecard.facets.base import FACET_REGISTRY
    from shared.llm_scorecard.facets.direction import DirectionFacet

    assert isinstance(FACET_REGISTRY["direction"], DirectionFacet)


def test_enabled_facets_returns_direction():
    import shared.llm_scorecard.facets.direction  # noqa: F401
    from shared.llm_scorecard.config import ScorecardConfig
    from shared.llm_scorecard.facets.base import enabled_facets

    cfg = ScorecardConfig(enabled_facets=["direction"])
    facets = enabled_facets(cfg)
    assert len(facets) == 1
    assert facets[0].name == "direction"
