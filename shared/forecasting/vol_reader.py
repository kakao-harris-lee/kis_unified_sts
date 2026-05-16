"""Read the latest VolForecast from Redis (inverse of forecast_publisher).

Mirrors shared.macro.base.read_latest_macro_snapshot: never raises, returns
None on absent/garbage/redis-error so trading hot paths degrade gracefully.
"""
from __future__ import annotations

import logging
from typing import Any

from shared.forecasting.models import VolForecast

logger = logging.getLogger(__name__)

# Must match shared.forecasting.forecast_publisher._VOL_KEY.
_VOL_KEY = "forecast:vol:current"


def read_latest_vol_forecast(redis_client: Any) -> VolForecast | None:
    try:
        blob = redis_client.get(_VOL_KEY)
    except Exception as exc:  # noqa: BLE001 — hot path, never propagate
        logger.debug("vol forecast read failed: %s", exc)
        return None
    if not blob:
        return None
    try:
        return VolForecast.from_json(blob)
    except Exception as exc:  # noqa: BLE001
        logger.debug("vol forecast parse failed: %s", exc)
        return None
