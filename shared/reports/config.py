"""Configuration for the unified feedback report engine (Phase 6A).

Loads ``config/feedback_reports.yaml``. All judgment thresholds from the
design doc §8.2 (60% backtest ratio, 3/6/12-month checkpoints, 3-year Track A
deferral) live here — nothing is hardcoded in the engine.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field

from shared.config.base import ServiceConfigBase
from shared.config.loader import ConfigNotFoundError


class FeedbackRedisConfig(BaseModel):
    """Redis freshness-pointer contract (files remain the source of truth).

    ``latest_ttl_seconds`` defaults to 8 days: the weekly cadence (7 days)
    plus one day of scheduler slack. Expiry loses nothing — the report files
    are the durable record; the hash only tells the 6B UI what is fresh.
    """

    latest_key: str = Field(default="portfolio:feedback:latest")
    latest_ttl_seconds: int = Field(default=691200, gt=0)


class FeedbackAlertsConfig(BaseModel):
    """One Telegram headline per generated report (existing notifier)."""

    enabled: bool = Field(default=True)
    domain: str = Field(default="briefing")


class FeedbackMonthlyConfig(BaseModel):
    """Monthly-section knobs (Market Risk Score close-row columns)."""

    risk_band_column: str = Field(default="risk_band")
    risk_score_column: str = Field(default="risk_score")


class TrackBQuarterlyConfig(BaseModel):
    """§8.2 Track B material: rolling realized vs backtest expectation."""

    rolling_months: int = Field(default=6, gt=0)
    backtest_ratio: float = Field(default=0.6, gt=0.0, le=1.0)
    experiment_reports_dir: str = Field(default="reports/stock_experiment")


class TrackCQuarterlyConfig(BaseModel):
    """§8.2 Track C material: breakeven / EV-positive checkpoints."""

    breakeven_months: int = Field(default=3, gt=0)
    ev_checkpoint_months: int = Field(default=6, gt=0)
    ev_final_months: int = Field(default=12, gt=0)


class TrackAQuarterlyConfig(BaseModel):
    """§8.2 Track A material: KOSPI-proxy benchmark, 3-year deferral."""

    benchmark_column: str = Field(default="k200_close")
    min_history_years: int = Field(default=3, gt=0)


class FeedbackQuarterlyConfig(BaseModel):
    """Quarterly §8.2 judgment-material parameters (per track)."""

    track_b: TrackBQuarterlyConfig = Field(default_factory=TrackBQuarterlyConfig)
    track_c: TrackCQuarterlyConfig = Field(default_factory=TrackCQuarterlyConfig)
    track_a: TrackAQuarterlyConfig = Field(default_factory=TrackAQuarterlyConfig)


class FeedbackReportsConfig(ServiceConfigBase):
    """Top-level config loaded from ``config/feedback_reports.yaml``."""

    _default_config_file: ClassVar[str] = "feedback_reports.yaml"

    reports_root: str = Field(default="reports/feedback")
    redis: FeedbackRedisConfig = Field(default_factory=FeedbackRedisConfig)
    alerts: FeedbackAlertsConfig = Field(default_factory=FeedbackAlertsConfig)
    monthly: FeedbackMonthlyConfig = Field(default_factory=FeedbackMonthlyConfig)
    quarterly: FeedbackQuarterlyConfig = Field(default_factory=FeedbackQuarterlyConfig)

    @classmethod
    def load_or_default(cls, path: str | None = None) -> FeedbackReportsConfig:
        """Load from YAML when available, otherwise return validated defaults."""
        try:
            return cls.from_yaml(path)
        except ConfigNotFoundError:
            return cls()
