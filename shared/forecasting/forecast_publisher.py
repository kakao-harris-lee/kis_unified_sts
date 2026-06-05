"""Publish VolForecast / EventScore to Redis."""

from __future__ import annotations

import logging
import math
from typing import Any

from shared.forecasting.models import EventScore, VolForecast

logger = logging.getLogger(__name__)

_VOL_KEY = "forecast:vol:current"
_EVENT_LATEST_KEY = "forecast:event:latest"
_EVENT_CHANNEL = "forecasting:events"


class ForecastPublisher:
    """Redis pub/sub + SET with TTL.

    All publish methods are non-raising — infrastructure failures are
    logged and forecast generation continues.
    """

    def __init__(
        self,
        redis: Any,
        storage_client: Any | None = None,
        vol_ttl_s: int = 120,
        **legacy_kwargs: Any,
    ):
        # Legacy storage kwargs are ignored deliberately so forecast publishing
        # never performs DB writes.
        _ = storage_client, legacy_kwargs
        self._redis = redis
        self._vol_ttl_s = vol_ttl_s

    def publish_vol_forecast(self, vf: VolForecast) -> None:
        if not math.isfinite(vf.forecast_pct) or not math.isfinite(
            vf.forecast_atr_equivalent
        ):
            logger.warning("Skipping NaN/Inf vol forecast at %s", vf.asof)
            return
        # 1. Redis SET with TTL
        try:
            self._redis.set(_VOL_KEY, vf.to_json(), ex=self._vol_ttl_s)
        except Exception as e:  # noqa: BLE001
            logger.warning("Redis SET %s failed: %s", _VOL_KEY, e)

    def publish_event_score(self, es: EventScore) -> None:
        # 1. Redis publish
        try:
            self._redis.publish(_EVENT_CHANNEL, es.to_json())
        except Exception as e:  # noqa: BLE001
            logger.warning("Redis publish %s failed: %s", _EVENT_CHANNEL, e)
        # 2. Redis SET latest (fallback path)
        try:
            self._redis.set(_EVENT_LATEST_KEY, es.to_json(), ex=es.ttl_minutes * 60)
        except Exception as e:  # noqa: BLE001
            logger.warning("Redis SET %s failed: %s", _EVENT_LATEST_KEY, e)
