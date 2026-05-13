"""Publish VolForecast / EventScore to Redis + ClickHouse."""
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
    """Redis (pub/sub + SET with TTL) + ClickHouse persistence.

    All publish methods are non-raising — infrastructure failures are
    logged and forecast generation continues.
    """

    def __init__(self, redis: Any, clickhouse: Any, vol_ttl_s: int = 120):
        self._redis = redis
        self._ch = clickhouse
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
        # 2. ClickHouse persist
        try:
            self._ch.execute(
                "INSERT INTO kospi.vol_forecasts "
                "(asof, horizon_minutes, forecast_pct, forecast_atr_equivalent, "
                "regime_percentile, model_version) VALUES",
                [
                    (
                        vf.asof,
                        vf.horizon_minutes,
                        vf.forecast_pct,
                        vf.forecast_atr_equivalent,
                        vf.regime_percentile,
                        vf.model_version,
                    )
                ],
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("ClickHouse vol_forecasts insert failed: %s", e)

    def publish_event_score(self, es: EventScore) -> None:
        # 1. Redis publish
        try:
            self._redis.publish(_EVENT_CHANNEL, es.to_json())
        except Exception as e:  # noqa: BLE001
            logger.warning("Redis publish %s failed: %s", _EVENT_CHANNEL, e)
        # 2. Redis SET latest (fallback path)
        try:
            self._redis.set(
                _EVENT_LATEST_KEY, es.to_json(), ex=es.ttl_minutes * 60
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Redis SET %s failed: %s", _EVENT_LATEST_KEY, e)
        # 3. ClickHouse persist
        try:
            source_value = 1 if es.source == "rule" else 2
            self._ch.execute(
                "INSERT INTO kospi.event_scores "
                "(asof, event_type, impact_score, source, ttl_minutes, raw_text_hash) "
                "VALUES",
                [
                    (
                        es.asof,
                        es.event_type,
                        int(es.impact_score),
                        source_value,
                        es.ttl_minutes,
                        b"\x00" * 16,  # placeholder
                    )
                ],
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("ClickHouse event_scores insert failed: %s", e)
