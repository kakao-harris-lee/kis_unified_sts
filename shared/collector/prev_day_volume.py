"""Previous-day volume lookup via KRX Open API.

Provides a cache-backed helper that fetches previous trading day volumes
for a list of stock codes. Designed for use by the Screener at startup
so that ``opening_volume_surge`` can compare today's cumulative volume
against yesterday's total.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta
from datetime import time as dt_time

import requests

from shared.calendar import MarketCalendar

logger = logging.getLogger(__name__)
_CALENDAR = MarketCalendar()


def _get_krx_api_key() -> str:
    return os.getenv("KRX_API_KEY", "").strip()


def _krx_base_url() -> str:
    return os.getenv("KRX_BASE_URL", "https://data-dbg.krx.co.kr/svc/apis").rstrip("/")


def _parse_int(value: object) -> int:
    try:
        return int(float(str(value).replace(",", "").strip() or 0))
    except Exception:
        return 0


def _krx_request(endpoint: str, base_date: str) -> list[dict]:
    api_key = _get_krx_api_key()
    if not api_key:
        return []

    url = f"{_krx_base_url()}/{endpoint}"
    params = {"AUTH_KEY": api_key, "basDd": base_date}
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []

    if isinstance(payload, dict) and payload.get("respCode") in ("401", "403"):
        return []

    if isinstance(payload, dict):
        out = payload.get("OutBlock_1")
        if isinstance(out, list):
            return out
        out = payload.get("output")
        if isinstance(out, list):
            return out
    if isinstance(payload, list):
        return payload
    return []


def _fetch_market_volumes(market: str, base_date: str) -> dict[str, int]:
    endpoint = "sto/stk_bydd_trd" if market == "KOSPI" else "sto/ksq_bydd_trd"
    rows = _krx_request(endpoint, base_date)
    out: dict[str, int] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        code = str(item.get("ISU_CD", "")).strip()
        if not code:
            continue
        vol = _parse_int(item.get("ACC_TRDVOL", 0))
        if vol > 0:
            out[code] = vol
    return out


def _previous_date(date_str: str) -> str:
    return (datetime.strptime(date_str, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")


def _last_known_target_date() -> str:
    now = datetime.now()
    today = now.date()
    if now.time() < dt_time(18, 0):
        target = _CALENDAR.get_previous_market_day(today)
        return target.strftime("%Y%m%d")
    if _CALENDAR.is_market_day(today):
        return today.strftime("%Y%m%d")
    return _CALENDAR.get_previous_market_day(today).strftime("%Y%m%d")


def _get_krx_client() -> object | None:
    if not _get_krx_api_key():
        return None
    return object()


def _last_trading_date_str(client: object | None = None) -> str:
    """Return most recent date with market snapshots in ``YYYYMMDD`` format."""
    _ = client
    if not _get_krx_api_key():
        return (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    candidate = _last_known_target_date()
    for _ in range(7):
        if _fetch_market_volumes("KOSPI", candidate):
            return candidate
        candidate = _previous_date(candidate)
    return (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")


class PrevDayVolumeCache:
    """Caches previous-day volumes fetched from KRX Open API.

    Usage::

        cache = PrevDayVolumeCache()
        cache.warm_all()            # bulk-load KOSPI + KOSDAQ
        vol = cache.get("005930")   # 12_345_678
        cache.ensure(["005930", "000660"])  # lazy-fill missing codes
    """

    def __init__(self) -> None:
        self._volumes: dict[str, int] = {}
        self._date: str | None = None

    def warm_all(self) -> int:
        """Bulk-load previous-day volumes for all KOSPI + KOSDAQ stocks."""
        client = _get_krx_client()
        if client is None:
            logger.warning("KRX_API_KEY missing — prev_day_volume unavailable")
            return 0

        date = _last_trading_date_str(client)
        self._date = date
        before = len(self._volumes)

        for market in ("KOSPI", "KOSDAQ"):
            try:
                market_volumes = _fetch_market_volumes(market, date)
                for code, vol in market_volumes.items():
                    self._volumes[code] = int(vol)
            except Exception as e:
                logger.warning("Failed to load prev-day volumes for %s: %s", market, e)

        loaded = len(self._volumes) - before
        logger.info("PrevDayVolumeCache: loaded %d codes (date=%s)", loaded, date)
        return loaded

    async def warm_all_async(self) -> int:
        """Non-blocking version of warm_all() for async contexts."""
        return await asyncio.to_thread(self.warm_all)

    def get(self, code: str) -> int:
        """Return previous-day volume for *code*, or 0 if unknown."""
        return self._volumes.get(code, 0)

    async def ensure_async(self, codes: list[str]) -> int:
        """Non-blocking version of ensure() for async contexts."""
        return await asyncio.to_thread(self.ensure, codes)

    def ensure(self, codes: list[str]) -> int:
        """Lazy-fill any codes missing from the cache."""
        missing = [str(c) for c in codes if str(c) not in self._volumes]
        if not missing:
            return 0

        client = _get_krx_client()
        if client is None:
            return 0

        date = self._date or _last_trading_date_str(client)
        missing_set = set(missing)
        filled = 0

        for market in ("KOSPI", "KOSDAQ"):
            if not missing_set:
                break
            try:
                market_volumes = _fetch_market_volumes(market, date)
            except Exception:
                market_volumes = {}
            if not market_volumes:
                continue

            for code in list(missing_set):
                vol = market_volumes.get(code, 0)
                if vol > 0:
                    self._volumes[code] = vol
                    missing_set.remove(code)
                    filled += 1

        if filled:
            logger.debug("PrevDayVolumeCache: lazy-filled %d codes", filled)
        return filled

    def build_metadata(self, codes: list[str]) -> dict[str, dict[str, int]]:
        """Build per-symbol metadata dict for Redis payload.

        Returns ``{code: {"prev_day_volume": N}}`` for codes with data.
        """
        result: dict[str, dict[str, int]] = {}
        for code in codes:
            vol = self._volumes.get(code, 0)
            if vol > 0:
                result[code] = {"prev_day_volume": vol}
        return result

    @property
    def date(self) -> str | None:
        return self._date

    def __len__(self) -> int:
        return len(self._volumes)
