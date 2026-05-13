"""Forecast-aware paradigm: HAR-RV volatility + hybrid event scoring."""
from shared.forecasting.client import ForecastClient
from shared.forecasting.config import (
    EventScorerConfig,
    ForecastingConfig,
    HARRVConfig,
)
from shared.forecasting.event_impact_scorer import EventImpactScorer
from shared.forecasting.event_taxonomy import EventTaxonomy, TaxonomyEntry
from shared.forecasting.forecast_publisher import ForecastPublisher
from shared.forecasting.llm_event_scorer import LLMScorerClient, OpenAIEventScorer
from shared.forecasting.models import EventScore, VolForecast
from shared.forecasting.realized_variance import (
    compute_intraday_realized_variance,
    daily_rv_series,
    resample_to_5min,
)
from shared.forecasting.volatility_har_rv import (
    HARRVCoefficients,
    VolatilityForecaster,
)

__all__ = [
    "ForecastClient",
    "ForecastPublisher",
    "ForecastingConfig",
    "HARRVConfig",
    "EventScorerConfig",
    "EventImpactScorer",
    "EventTaxonomy",
    "TaxonomyEntry",
    "LLMScorerClient",
    "OpenAIEventScorer",
    "EventScore",
    "VolForecast",
    "HARRVCoefficients",
    "VolatilityForecaster",
    "compute_intraday_realized_variance",
    "daily_rv_series",
    "resample_to_5min",
]
