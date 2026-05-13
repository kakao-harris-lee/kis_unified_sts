"""Setup A/C consumer wrapper — pulls VolForecast + EventScore from Redis."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from shared.forecasting.models import EventScore, VolForecast

logger = logging.getLogger(__name__)

_VOL_KEY = "forecast:vol:current"
_EVENT_LATEST_KEY = "forecast:event:latest"


class ForecastClient:
    """Consumer client for Setup A/C adapters.

    Pull-based: Setup A/C calls this on every entry check. Returns None
    on any failure (caller falls back to ATR).
    """

    def __init__(self, redis: Any, vol_max_age_s: int = 120):
        self._redis = redis
        self._vol_max_age_s = vol_max_age_s

    async def get_latest_vol_forecast(self) -> VolForecast | None:
        try:
            raw = self._redis.get(_VOL_KEY)
        except Exception as e:  # noqa: BLE001
            logger.debug("ForecastClient: redis GET failed: %s", e)
            return None
        if raw is None:
            return None
        try:
            vf = VolForecast.from_json(raw)
        except Exception as e:  # noqa: BLE001
            logger.warning("ForecastClient: malformed vol JSON: %s", e)
            return None
        if not vf.is_fresh(datetime.now(UTC), max_age_s=self._vol_max_age_s):
            return None
        return vf

    async def get_latest_event_score(self) -> EventScore | None:
        try:
            raw = self._redis.get(_EVENT_LATEST_KEY)
        except Exception as e:  # noqa: BLE001
            logger.debug("ForecastClient: redis GET event failed: %s", e)
            return None
        if raw is None:
            return None
        try:
            es = EventScore.from_json(raw)
        except Exception as e:  # noqa: BLE001
            logger.warning("ForecastClient: malformed event JSON: %s", e)
            return None
        if es.is_expired(datetime.now(UTC)):
            return None
        return es
