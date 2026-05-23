"""Redis-backed live data source for RegimeGate (P2-③ T2).

Implements the same duck-typed interface RegimeGate expects:
  - latest_vol_at(ts) → (asof_naive, regime_percentile) | None
  - events_within(ts, window_min) → list[(asof_naive, impact_score)]
  - macro_for(date) → float | None   (always None in live; PERMISSIVE)

Vol reads from `forecast:vol:current` (the live ForecastPublisher's
60s-cadence write). Event reads do a low-volume CH SELECT (called once
per entry decision). PERMISSIVE on EVERY missing/stale/error path —
never propagates to the trading hot path.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from shared.forecasting.models import VolForecast
from shared.forecasting.vol_reader import VOL_REDIS_KEY  # canonical key

logger = logging.getLogger(__name__)

_DEFAULT_MAX_AGE_S = 120  # matches ForecastPublisher's Redis TTL


class LiveVolInputs:
    """Live (Redis + CH) inputs for RegimeGate."""

    def __init__(
        self,
        redis: Any,
        ch_client: Any,
        max_age_s: int = _DEFAULT_MAX_AGE_S,
    ):
        self._redis = redis
        self._ch = ch_client
        self._max_age_s = max_age_s

    def latest_vol_at(
        self, ts: dt.datetime  # noqa: ARG002
    ) -> tuple[dt.datetime, float] | None:
        try:
            blob = self._redis.get(VOL_REDIS_KEY)
        except Exception as e:  # noqa: BLE001 — hot path
            logger.debug("LiveVolInputs: redis GET failed: %s", e)
            return None
        if not blob:
            return None
        try:
            vf = VolForecast.from_json(blob)
        except Exception as e:  # noqa: BLE001
            logger.debug("LiveVolInputs: malformed vol JSON: %s", e)
            return None
        try:
            now = dt.datetime.now(dt.UTC)
            if not vf.is_fresh(now, max_age_s=self._max_age_s):
                return None
            asof_n = vf.asof.replace(tzinfo=None) if vf.asof.tzinfo else vf.asof
        except Exception as e:  # noqa: BLE001 — hot path
            logger.debug("LiveVolInputs: freshness check failed: %s", e)
            return None
        return (asof_n, float(vf.regime_percentile))

    def events_within(
        self, ts: dt.datetime, window_min: int
    ) -> list[tuple[dt.datetime, int]]:
        try:
            ts_n = ts.replace(tzinfo=None) if getattr(ts, "tzinfo", None) else ts
            lo = ts_n - dt.timedelta(minutes=window_min)
            hi = ts_n + dt.timedelta(minutes=window_min)
            rows = self._ch.execute(
                "SELECT asof, impact_score FROM kospi.event_scores "
                "WHERE asof >= %(lo)s AND asof <= %(hi)s ORDER BY asof",
                {"lo": lo, "hi": hi},
            )
        except Exception as e:  # noqa: BLE001
            logger.debug("LiveVolInputs: events_within CH failed: %s", e)
            return []
        return [
            (r[0].replace(tzinfo=None) if getattr(r[0], "tzinfo", None) else r[0],
             int(r[1]))
            for r in rows
            if r[0] is not None
        ]

    def macro_for(self, date: dt.date) -> float | None:  # noqa: ARG002
        """Live EntryContext has no macro_overnight field. RegimeGate's
        require_overnight_us_direction flag degrades PERMISSIVE when this
        returns None — that's the §9 design (never silently block on
        missing data). Setup A's own macro consumption is internal to its
        _build_market_context path and not visible here.
        """
        return None
