"""KillSwitchConfig — ServiceConfigBase loader for ``config/kill_switch.yaml``.

Phase 4 Task 13 follow-up. The YAML existed since PR #134 but had no loader
(carried as sub-threshold debt across PRs #134/#135). This module closes the
"No dead YAML" gap explicitly called out in the Phase 4 plan's
*Conventions Reminder* (PR #128 lesson).
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field

from shared.config.base import ServiceConfigBase


class _ConditionToggle(BaseModel):
    enabled: bool = True
    limit_pct: float | None = None
    threshold: float | None = None


class _NewsPipelineLagToggle(_ConditionToggle):
    """News-pipeline lag condition with the source Redis stream key.

    The stream key was previously hardcoded inside
    ``_build_news_pipeline_lag_provider`` (CLAUDE.md "No Hardcoding" violation).
    Operators can now point the kill switch at a different ingest stream
    without code changes.
    """

    stream_key: str = Field(default="stream:news.raw")


class _ConditionsBlock(BaseModel):
    daily_loss: _ConditionToggle = Field(default_factory=_ConditionToggle)
    weekly_loss: _ConditionToggle = Field(default_factory=_ConditionToggle)
    consecutive_losses: _ConditionToggle = Field(default_factory=_ConditionToggle)
    api_error_rate_5min: _ConditionToggle = Field(default_factory=_ConditionToggle)
    news_pipeline_lag_seconds: _NewsPipelineLagToggle = Field(
        default_factory=_NewsPipelineLagToggle
    )
    clickhouse_insert_fail_rate: _ConditionToggle = Field(
        default_factory=_ConditionToggle
    )


class KillSwitchConfig(ServiceConfigBase):
    """Top-level config for the kill_switch daemon.

    Loaded from ``config/kill_switch.yaml`` under the ``kill_switch`` section.
    """

    _default_config_file: ClassVar[str] = "kill_switch.yaml"
    _default_section: ClassVar[str] = "kill_switch"

    enabled: bool = Field(default=True)
    check_interval_seconds: float = Field(default=30.0, gt=0)
    force_flat_on_trigger: bool = Field(default=True)
    sentinel_path: str = Field(default="/var/run/kis_kill_switch.tripped")
    conditions: _ConditionsBlock = Field(default_factory=_ConditionsBlock)
