# tests/unit/llm_scorecard/test_registry.py
from shared.llm_scorecard.facets.base import (
    register_facet, enabled_facets, FACET_REGISTRY, FacetScore)
from shared.llm_scorecard.config import ScorecardConfig


class _Dummy:
    name = "dummy"; outcome_horizon = "same_session"; outcome_source = "stock_daily"
    def capture(self, ctx): return None
    def score(self, pred, mkt): ...
    def baseline(self, pred, mkt): return 0.0


def test_register_and_filter_by_config():
    register_facet(_Dummy())
    assert "dummy" in FACET_REGISTRY
    cfg = ScorecardConfig(enabled_facets=["dummy"])
    assert [f.name for f in enabled_facets(cfg)] == ["dummy"]
    cfg2 = ScorecardConfig(enabled_facets=["other"])
    assert enabled_facets(cfg2) == []
