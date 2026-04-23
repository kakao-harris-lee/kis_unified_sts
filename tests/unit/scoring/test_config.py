"""Tests for NewsScorerConfig (Task 10).

Covers:
- Default construction (no YAML required)
- Loading from a YAML file with section extraction
- Nested section override propagation
- ClassVar metadata correctness
"""

from __future__ import annotations

import pytest

from shared.scoring.config import NewsScorerConfig


class TestConfigDefaults:
    """NewsScorerConfig can be constructed with no arguments."""

    def test_consumer_group_default(self) -> None:
        c = NewsScorerConfig()
        assert c.consumer_group == "news_scorer-v1"

    def test_scorer_model_default(self) -> None:
        c = NewsScorerConfig()
        assert c.scorer.model == "gpt-4o-mini"

    def test_budget_daily_usd_limit_default(self) -> None:
        c = NewsScorerConfig()
        assert c.budget.daily_usd_limit == 5.0

    def test_fallback_on_timeout_default(self) -> None:
        c = NewsScorerConfig()
        assert c.fallback.on_timeout == "neutral"

    def test_fallback_on_json_error_default(self) -> None:
        c = NewsScorerConfig()
        assert c.fallback.on_json_error == "neutral"

    def test_fallback_on_budget_exceeded_default(self) -> None:
        c = NewsScorerConfig()
        assert c.fallback.on_budget_exceeded == "skip"

    def test_batch_size_default(self) -> None:
        c = NewsScorerConfig()
        assert c.batch_size == 10

    def test_body_truncate_chars_default(self) -> None:
        c = NewsScorerConfig()
        assert c.body_truncate_chars == 2000

    def test_scorer_version_default(self) -> None:
        c = NewsScorerConfig()
        assert c.scorer.version == "gpt-4o-mini-v1"

    def test_scorer_retries_default(self) -> None:
        c = NewsScorerConfig()
        assert c.scorer.retries == 2


class TestClassVarMetadata:
    """ClassVar attributes must be set to the correct values."""

    def test_default_config_file(self) -> None:
        assert NewsScorerConfig._default_config_file == "news_scoring.yaml"

    def test_default_section(self) -> None:
        assert NewsScorerConfig._default_section == "news_scorer"

    def test_env_prefix(self) -> None:
        assert NewsScorerConfig._env_prefix == "NEWS_SCORER_"


class TestFromYaml:
    """NewsScorerConfig.from_yaml() extracts the news_scorer section."""

    def test_batch_size_override(self, tmp_path: pytest.FixtureDef) -> None:
        p = tmp_path / "news_scoring.yaml"
        p.write_text(
            "news_scorer:\n"
            "  batch_size: 25\n"
            "  scorer:\n"
            "    version: gpt-4o-mini-v2\n"
        )
        c = NewsScorerConfig.from_yaml(str(p))
        assert c.batch_size == 25

    def test_scorer_version_override(self, tmp_path: pytest.FixtureDef) -> None:
        p = tmp_path / "news_scoring.yaml"
        p.write_text(
            "news_scorer:\n"
            "  batch_size: 25\n"
            "  scorer:\n"
            "    version: gpt-4o-mini-v2\n"
        )
        c = NewsScorerConfig.from_yaml(str(p))
        assert c.scorer.version == "gpt-4o-mini-v2"

    def test_unspecified_fields_use_defaults(self, tmp_path: pytest.FixtureDef) -> None:
        p = tmp_path / "news_scoring.yaml"
        p.write_text("news_scorer:\n" "  batch_size: 25\n")
        c = NewsScorerConfig.from_yaml(str(p))
        # Unspecified fields must fall back to defaults
        assert c.consumer_group == "news_scorer-v1"
        assert c.scorer.model == "gpt-4o-mini"
        assert c.budget.daily_usd_limit == 5.0

    def test_fallback_section_override(self, tmp_path: pytest.FixtureDef) -> None:
        p = tmp_path / "news_scoring.yaml"
        p.write_text(
            "news_scorer:\n"
            "  fallback:\n"
            "    on_timeout: skip\n"
            "    on_json_error: skip\n"
            "    on_budget_exceeded: neutral\n"
        )
        c = NewsScorerConfig.from_yaml(str(p))
        assert c.fallback.on_timeout == "skip"
        assert c.fallback.on_json_error == "skip"
        assert c.fallback.on_budget_exceeded == "neutral"

    def test_loads_from_project_config_file(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """from_yaml() with no args resolves via ConfigLoader from project config/."""
        from pathlib import Path

        project_root = Path(__file__).parents[3]
        config_dir = project_root / "config"
        monkeypatch.setenv("KIS_CONFIG_DIR", str(config_dir))

        c = NewsScorerConfig.from_yaml()
        # Values must match config/news_scoring.yaml
        assert c.consumer_group == "news_scorer-v1"
        assert c.scorer.model == "gpt-4o-mini"
        assert c.budget.daily_usd_limit == 5.0
