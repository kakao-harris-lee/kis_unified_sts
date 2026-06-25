"""Characterization tests for LLMConfig YAML loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.config.loader import ConfigLoader
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


@pytest.fixture()
def _restore_config_loader_dir() -> None:
    previous = ConfigLoader.get_config_dir()
    try:
        yield
    finally:
        ConfigLoader.set_config_dir(previous)


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


def test_from_yaml_loads_relative_path_through_config_loader(
    tmp_path: Path,
    _restore_config_loader_dir: None,
) -> None:
    ConfigLoader.set_config_dir(tmp_path)
    _write_yaml(
        tmp_path / "llm.yaml",
        """
llm:
  provider: "claude"
claude:
  api_key: "relative-claude-key"
  model: "claude-3-5-sonnet-latest"
output:
  dir: "output/relative"
""",
    )

    cfg = LLMConfig.from_yaml("llm.yaml")

    assert cfg.llm_provider == "claude"
    assert cfg.api_key == "relative-claude-key"
    assert cfg.model == "claude-3-5-sonnet-latest"
    assert cfg.output_dir == "output/relative"


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


def test_from_yaml_uses_legacy_futures_analysis_when_futures_missing(
    tmp_path: Path,
) -> None:
    cfg_path = tmp_path / "legacy_futures_llm.yaml"
    _write_yaml(
        cfg_path,
        """
futures_analysis:
  prompt_addendum: "legacy futures context"
  weight_global: 0.40
  weight_flow: 0.25
  weight_technical: 0.20
  weight_event: 0.15
  tick_stream: "stream:futures.ticks"
  tick_lookback_seconds: 900
  tick_max: 1234
  tick_symbol: "101V9000"
""",
    )

    cfg = LLMConfig.from_yaml(cfg_path)

    assert cfg.futures_prompt_addendum == "legacy futures context"
    assert cfg.futures_weight_global == 0.40
    assert cfg.futures_weight_flow == 0.25
    assert cfg.futures_weight_technical == 0.20
    assert cfg.futures_weight_event == 0.15
    assert cfg.futures_tick_stream == "stream:futures.ticks"
    assert cfg.futures_tick_lookback_seconds == 900
    assert cfg.futures_tick_max == 1234
    assert cfg.futures_tick_symbol == "101V9000"


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
