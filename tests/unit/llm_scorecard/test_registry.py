# tests/unit/llm_scorecard/test_registry.py
import pytest

from shared.llm_scorecard.facets.base import (
    register_facet, enabled_facets, FACET_REGISTRY, FacetScore)
from shared.llm_scorecard.config import ScorecardConfig


@pytest.fixture(autouse=True)
def _isolate_registry():
    """Snapshot/restore the global FACET_REGISTRY so test entries don't leak."""
    saved = dict(FACET_REGISTRY)
    try:
        yield
    finally:
        FACET_REGISTRY.clear()
        FACET_REGISTRY.update(saved)


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
