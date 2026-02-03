"""Tests for negative screening helpers."""

from shared.llm.config import LLMConfig
from shared.llm.llm_analyzer import UnifiedTradingAnalyzer


def test_name_exclusion_preferred_share(tmp_path):
    cfg = LLMConfig(output_dir=str(tmp_path))
    analyzer = UnifiedTradingAnalyzer(config=cfg)

    reasons = analyzer._name_exclusion_reasons("삼성전자우")
    assert "preferred_share" in reasons


def test_name_exclusion_keyword(tmp_path):
    cfg = LLMConfig(output_dir=str(tmp_path), stock_exclude_name_keywords=["스팩"])
    analyzer = UnifiedTradingAnalyzer(config=cfg)

    reasons = analyzer._name_exclusion_reasons("ABC스팩1호")
    assert reasons == ["name_keyword:스팩"]


def test_name_exclusion_allows_normal_name(tmp_path):
    cfg = LLMConfig(output_dir=str(tmp_path))
    analyzer = UnifiedTradingAnalyzer(config=cfg)

    assert analyzer._name_exclusion_reasons("삼성전자") == []

