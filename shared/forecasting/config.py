"""Forecasting service configuration (ServiceConfigBase pattern)."""
from typing import ClassVar

from pydantic import BaseModel, Field

from shared.config.base import ServiceConfigBase


class HARRVConfig(BaseModel):
    refit_hour_kst: int = Field(default=15, ge=0, le=23)
    refit_minute_kst: int = Field(default=35, ge=0, le=59)
    history_days: int = Field(default=60, ge=22)  # min for monthly RV component
    holdout_days: int = Field(default=7, ge=1)
    # Allow negative thresholds: real-market OOS R² over 7d hold-out is often
    # negative (HAR-RV is a weak short-horizon predictor outside high-vol
    # regimes), and the canary needs to operate even when the fit is poor.
    min_r2_oos: float = Field(default=0.10, ge=-1.0, le=1.0)
    consecutive_fail_disable_threshold: int = Field(default=7, ge=1)


class EventScorerConfig(BaseModel):
    default_ttl_minutes: int = Field(default=30, ge=1)
    rule_first: bool = Field(default=True)
    llm_fallback_enabled: bool = Field(default=True)
    neutral_score_on_failure: int = Field(default=50, ge=0, le=100)
    # Impact-score band edges for tier assignment (1=top, 3=minor):
    # score >= tier1_min_score → tier 1, >= tier2_min_score → tier 2, else 3.
    tier1_min_score: int = Field(default=75, ge=0, le=100)
    tier2_min_score: int = Field(default=50, ge=0, le=100)


class ForecastingConfig(ServiceConfigBase):
    _default_config_file: ClassVar[str] = "forecasting.yaml"
    _default_section: ClassVar[str] = "forecasting"
    _env_prefix: ClassVar[str] = "FORECASTING_"

    publisher_enabled: bool = Field(default=True)
    forecast_loop_interval_seconds: int = Field(default=60, ge=1)
    forecast_redis_ttl_seconds: int = Field(default=120, ge=2)
    horizon_minutes: int = Field(default=15, ge=1)

    har_rv: HARRVConfig = Field(default_factory=HARRVConfig)
    event_scorer: EventScorerConfig = Field(default_factory=EventScorerConfig)
