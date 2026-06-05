"""Configuration model for the NewsScorerDaemon.

Uses ServiceConfigBase for standard YAML + env-var loading.
Nested sections (_ScorerSection, _BudgetSection, _FallbackSection) are
plain pydantic.BaseModel because they are sub-dicts, not top-level services.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field

from shared.config.base import ServiceConfigBase


class _ScorerSection(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    version: str = "gpt-4o-mini-v1"
    temperature: float = 0.0
    max_tokens: int = 250
    timeout_seconds: float = 5.0
    retries: int = 2
    api_key_env: str = "OPENAI_API_KEY"


class _BudgetSection(BaseModel):
    daily_usd_limit: float = 5.0
    alert_threshold_pct: float = 0.8
    key_prefix: str = "scorer:cost"


class _FallbackSection(BaseModel):
    on_timeout: str = "neutral"
    on_json_error: str = "neutral"
    on_budget_exceeded: str = "skip"


class NewsScorerConfig(ServiceConfigBase):
    """Top-level config for the news scoring service.

    Loaded from ``config/news_scoring.yaml`` under the ``news_scorer`` section.

    Environment variable overrides use the prefix ``NEWS_SCORER_``.
    Nested sections (scorer / budget / fallback) cannot be overridden
    via env vars individually — patch the YAML or pass keyword args.
    """

    _default_config_file: ClassVar[str] = "news_scoring.yaml"
    _default_section: ClassVar[str] = "news_scorer"
    _env_prefix: ClassVar[str] = "NEWS_SCORER_"

    consumer_group: str = "news_scorer-v1"
    worker_id_prefix: str = "scorer"
    batch_size: int = 10
    xread_block_ms: int = 5000
    input_stream: str = "stream:news.raw"
    output_stream: str = "stream:news.scored"
    output_stream_maxlen: int = 100_000
    archive_batch_size: int = 20
    archive_flush_interval_seconds: int = 10
    body_truncate_chars: int = 2000
    scorer: _ScorerSection = Field(default_factory=_ScorerSection)
    budget: _BudgetSection = Field(default_factory=_BudgetSection)
    fallback: _FallbackSection = Field(default_factory=_FallbackSection)
