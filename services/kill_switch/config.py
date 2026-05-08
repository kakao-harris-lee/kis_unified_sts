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


class KillSwitchConsumerConfig(ServiceConfigBase):
    """Config for the TradingOrchestrator kill-switch consumer loop.

    Loaded from ``config/kill_switch.yaml`` under the ``kill_switch_consumer``
    section.  The consumer polls a Redis sentinel key and calls
    ``PositionTracker.close_all()`` when a new kill-switch event is detected.

    Attributes:
        poll_interval_seconds: Cadence at which the orchestrator checks the
            sentinel key.  Must be low-frequency (default 5 s) so it does not
            interfere with the trading hot loop.
        sentinel_key: Redis key written by the kill-switch daemon on trip.
            Must match ``_FORCE_FLATTEN_KEY`` in ``services/kill_switch/main.py``.
        events_stream: Redis stream used as the authoritative event log.
            Must match ``_EVENTS_STREAM`` in ``services/kill_switch/main.py``.
        ignore_pre_startup_events: When ``True`` (default), the consumer
            initialises its last-seen event-id from the stream at startup so
            a sentinel/event written *before* this process started does NOT
            trigger a flatten.  Set ``False`` only in single-process testing.
    """

    _default_config_file: ClassVar[str] = "kill_switch.yaml"
    _default_section: ClassVar[str] = "kill_switch_consumer"

    poll_interval_seconds: float = Field(default=5.0, gt=0)
    sentinel_key: str = Field(default="kill_switch:force_flatten:requested")
    events_stream: str = Field(default="kill_switch:events")
    ignore_pre_startup_events: bool = Field(default=True)
