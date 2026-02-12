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


def test_llm_config_from_yaml_supports_claude_provider(tmp_path):
    cfg_path = tmp_path / "llm.yaml"
    cfg_path.write_text(
        """
llm:
  provider: "claude"
  strict_json_schema: true
  prompt_cache_enabled: true
  prompt_cache_ttl_seconds: 1234
  prompt_cache_prefix: "llm:test_cache"
  batch_size: 7
claude:
  model: "claude-3-5-haiku-latest"
  max_tokens: 777
  temperature: 0.1
""".lstrip(),
        encoding="utf-8",
    )

    cfg = LLMConfig.from_yaml(cfg_path)
    assert cfg.llm_provider == "claude"
    assert cfg.model == "claude-3-5-haiku-latest"
    assert cfg.max_tokens == 777
    assert cfg.temperature == 0.1
    assert cfg.llm_strict_json_schema is True
    assert cfg.llm_prompt_cache_enabled is True
    assert cfg.llm_prompt_cache_ttl_seconds == 1234
    assert cfg.llm_prompt_cache_prefix == "llm:test_cache"
    assert cfg.llm_batch_size == 7


def test_llm_config_from_env_provider_switch(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anth-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("LLM_PROMPT_CACHE_ENABLED", "false")
    monkeypatch.setenv("LLM_BATCH_SIZE", "13")

    cfg = LLMConfig.from_env()
    assert cfg.llm_provider == "claude"
    assert cfg.api_key == "anth-key"
    assert cfg.model == "claude-3-5-haiku-latest"
    assert cfg.llm_prompt_cache_enabled is False
    assert cfg.llm_batch_size == 13
