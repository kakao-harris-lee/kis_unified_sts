"""Tests for LLMConfig parsing/loading."""

from shared.llm.config import LLMConfig
from shared.llm.schema import normalize_scoring_payload


def test_llm_config_from_yaml_parses_stock_extensions(tmp_path):
    cfg_path = tmp_path / "llm.yaml"
    cfg_path.write_text(
        """
openai:
  model: "gpt-4o-mini"
stock:
  markets: ["KOSPI", "KOSDAQ"]
  volume_lookback_days: 15
  enable_kis_target_price: true
  target_lookback_days: 120
  score_weight_target_price: 0.07
  new_listing_min_days: 15
  new_listing_penalty: 0.6
  llm_scoring_enabled: false
  llm_scoring_model: "gpt-4o"
  llm_scoring_max_tokens: 300
  llm_scoring_temperature: 0.1
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
    assert cfg.stock_enable_kis_target_price is True
    assert cfg.stock_target_lookback_days == 120
    assert cfg.stock_score_weight_target_price == 0.07
    assert cfg.stock_blacklist == ["관리종목"]
    assert cfg.stock_keyword_filter == ["상장폐지"]
    assert cfg.stock_exclude_name_keywords == ["스팩"]
    assert cfg.stock_exclude_preferred_shares is True
    # New listing config
    assert cfg.stock_new_listing_min_days == 15
    assert cfg.stock_new_listing_penalty == 0.6
    # LLM scoring config
    assert cfg.stock_llm_scoring_enabled is False
    assert cfg.stock_llm_scoring_model == "gpt-4o"
    assert cfg.stock_llm_scoring_max_tokens == 300
    assert cfg.stock_llm_scoring_temperature == 0.1


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


def test_llm_config_defaults_new_listing():
    """Default values for new listing config."""
    cfg = LLMConfig()
    assert cfg.stock_new_listing_min_days == 20
    assert cfg.stock_new_listing_penalty == 0.7


def test_llm_config_defaults_llm_scoring():
    """Default values for LLM scoring config."""
    cfg = LLMConfig()
    assert cfg.stock_llm_scoring_enabled is True
    assert cfg.stock_llm_scoring_model == ""
    assert cfg.stock_llm_scoring_max_tokens == 500
    assert cfg.stock_llm_scoring_temperature == 0.2


# normalize_scoring_payload tests


def test_normalize_scoring_payload_defaults():
    """Empty dict → safe defaults."""
    result = normalize_scoring_payload({})
    assert result["confidence_factor"] == 1.0
    assert result["conviction"] == "medium"
    assert result["key_insight"] == ""
    assert result["risk_concern"] is None
    assert result["override_recommendation"] is None


def test_normalize_scoring_payload_clamps_confidence_factor():
    """confidence_factor clamped to [0.5, 1.5]."""
    assert (
        normalize_scoring_payload({"confidence_factor": 0.1})["confidence_factor"]
        == 0.5
    )
    assert (
        normalize_scoring_payload({"confidence_factor": 2.0})["confidence_factor"]
        == 1.5
    )
    assert (
        normalize_scoring_payload({"confidence_factor": 1.2})["confidence_factor"]
        == 1.2
    )


def test_normalize_scoring_payload_invalid_conviction():
    """Invalid conviction falls back to 'medium'."""
    assert (
        normalize_scoring_payload({"conviction": "INVALID"})["conviction"] == "medium"
    )
    assert normalize_scoring_payload({"conviction": "high"})["conviction"] == "high"
    assert normalize_scoring_payload({"conviction": "LOW"})["conviction"] == "low"


def test_normalize_scoring_payload_override():
    """Override recommendation validation."""
    assert (
        normalize_scoring_payload({"override_recommendation": "sell"})[
            "override_recommendation"
        ]
        == "sell"
    )
    assert (
        normalize_scoring_payload({"override_recommendation": "BUY"})[
            "override_recommendation"
        ]
        == "buy"
    )
    assert (
        normalize_scoring_payload({"override_recommendation": "invalid"})[
            "override_recommendation"
        ]
        is None
    )
    assert (
        normalize_scoring_payload({"override_recommendation": None})[
            "override_recommendation"
        ]
        is None
    )


def test_normalize_scoring_payload_truncates_strings():
    """key_insight and risk_concern truncated to 200 chars."""
    long_str = "x" * 300
    result = normalize_scoring_payload(
        {
            "key_insight": long_str,
            "risk_concern": long_str,
        }
    )
    assert len(result["key_insight"]) == 200
    assert len(result["risk_concern"]) == 200
