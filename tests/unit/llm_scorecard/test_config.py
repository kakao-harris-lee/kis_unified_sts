# tests/unit/llm_scorecard/test_config.py
from shared.llm_scorecard.config import ScorecardConfig


def test_loads_defaults_from_yaml():
    cfg = ScorecardConfig.from_yaml("config/llm_scorecard.yaml")
    assert "direction" in cfg.enabled_facets
    assert cfg.rolling_windows == [20, 60]
    assert cfg.telegram_domain == "briefing"
    assert cfg.facet_params["direction"]["symbol"] == "101S6000"

def test_missing_file_uses_safe_defaults():
    cfg = ScorecardConfig.from_yaml("/nonexistent.yaml")
    assert cfg.enabled_facets == ["direction"]
    assert cfg.report_daily is True
