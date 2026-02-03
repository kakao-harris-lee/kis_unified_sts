"""Tests for LLMConfig parsing/loading."""

from shared.llm.config import LLMConfig


def test_llm_config_from_yaml_parses_stock_extensions(tmp_path):
    cfg_path = tmp_path / "llm.yaml"
    cfg_path.write_text(
        """
openai:
  model: "gpt-4o-mini"
stock:
  markets: ["KOSPI", "KOSDAQ"]
  volume_lookback_days: 15
  min_avg_volume: 12345
  blacklist: ["관리종목"]
  keyword_filter: ["상장폐지"]
  exclude_name_keywords: ["스팩"]
  exclude_preferred_shares: true
output:
  dir: "output/llm"
""".lstrip(),
        encoding="utf-8",
    )

    cfg = LLMConfig.from_yaml(cfg_path)
    assert cfg.stock_markets == ["KOSPI", "KOSDAQ"]
    assert cfg.stock_volume_lookback_days == 15
    assert cfg.stock_min_avg_volume == 12345
    assert cfg.stock_blacklist == ["관리종목"]
    assert cfg.stock_keyword_filter == ["상장폐지"]
    assert cfg.stock_exclude_name_keywords == ["스팩"]
    assert cfg.stock_exclude_preferred_shares is True

