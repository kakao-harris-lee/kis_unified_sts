"""Characterization tests for LLMConfig YAML loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.llm.config import LLMConfig


@pytest.fixture(autouse=True)
def _clear_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "ANTHROPIC_API_KEY",
        "KRX_API_KEY",
        "LLM_ANALYSIS_ENABLED",
        "LLM_BATCH_SIZE",
        "LLM_ENABLED",
        "LLM_FUTURES_TICK_LOOKBACK_SECONDS",
        "LLM_FUTURES_TICK_MAX",
        "LLM_FUTURES_TICK_STREAM",
        "LLM_FUTURES_TICK_SYMBOL",
        "LLM_MAX_TOKENS",
        "LLM_MODEL",
        "LLM_OUTPUT_DIR",
        "LLM_PROMPT_CACHE_ENABLED",
        "LLM_PROMPT_CACHE_PREFIX",
        "LLM_PROMPT_CACHE_TTL_SECONDS",
        "LLM_PROVIDER",
        "LLM_STOCK_MIN_PRICE",
        "LLM_STRICT_JSON_SCHEMA",
        "LLM_TEMPERATURE",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


def _write_yaml(path: Path, content: str) -> None:
    path.write_text(content.lstrip(), encoding="utf-8")


def test_from_yaml_loads_absolute_yaml_path(tmp_path: Path) -> None:
    cfg_path = tmp_path / "llm.yaml"
    _write_yaml(
        cfg_path,
        """
llm:
  provider: "openai"
openai:
  api_key: "yaml-openai-key"
  model: "gpt-4o"
  max_tokens: 321
  temperature: 0.15
output:
  dir: "output/absolute"
stock:
  markets: ["KOSPI", "KOSDAQ"]
futures:
  prompt_addendum: "absolute futures addendum"
krx_api:
  api_key: "yaml-krx-key"
  timeout_seconds: 12
""",
    )

    cfg = LLMConfig.from_yaml(str(cfg_path.resolve()))

    assert cfg.llm_provider == "openai"
    assert cfg.api_key == "yaml-openai-key"
    assert cfg.model == "gpt-4o"
    assert cfg.max_tokens == 321
    assert cfg.temperature == 0.15
    assert cfg.output_dir == "output/absolute"
    assert cfg.stock_markets == ["KOSPI", "KOSDAQ"]
    assert cfg.futures_prompt_addendum == "absolute futures addendum"
    assert cfg.krx_api_key == "yaml-krx-key"
    assert cfg.krx_timeout == 12


def test_from_yaml_uses_legacy_stock_screening_when_stock_missing(
    tmp_path: Path,
) -> None:
    cfg_path = tmp_path / "legacy_llm.yaml"
    _write_yaml(
        cfg_path,
        """
stock_screening:
  markets: ["KOSDAQ"]
  min_price: 2500
  final_selection: 9
  llm_scoring_enabled: false
""",
    )

    cfg = LLMConfig.from_yaml(cfg_path)

    assert cfg.stock_markets == ["KOSDAQ"]
    assert cfg.stock_min_price == 2500
    assert cfg.stock_final_selection == 9
    assert cfg.stock_llm_scoring_enabled is False


def test_from_yaml_applies_env_overrides_when_requested(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg_path = tmp_path / "llm.yaml"
    _write_yaml(
        cfg_path,
        """
output:
  dir: "output/yaml"
stock:
  min_price: 1000
""",
    )
    monkeypatch.setenv("LLM_OUTPUT_DIR", "output/env")
    monkeypatch.setenv("LLM_STOCK_MIN_PRICE", "4321")

    yaml_only = LLMConfig.from_yaml(cfg_path)
    overridden = LLMConfig.from_yaml(cfg_path, apply_env_overrides=True)

    assert yaml_only.output_dir == "output/yaml"
    assert yaml_only.stock_min_price == 1000
    assert overridden.output_dir == "output/env"
    assert overridden.stock_min_price == 4321
