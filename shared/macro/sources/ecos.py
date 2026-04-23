"""한국은행 ECOS API — USD/KRW snapshot."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta

import aiohttp

from shared.macro.base import MacroSnapshot

logger = logging.getLogger(__name__)

# 731Y001 = 원/달러 환율, period D(daily)
_ECOS_URL = (
    "https://ecos.bok.or.kr/api/StatisticSearch/"
    "{api_key}/json/kr/1/2/731Y001/D/{start}/{end}/0000001"
)


class ECOSSource:
    def __init__(
        self, api_key: str, session: aiohttp.ClientSession, timeout: float = 10.0
    ):
        self._api_key = api_key
        self._session = session
        self._timeout = timeout

    async def fetch_fx_snapshot(self) -> MacroSnapshot:
        now = datetime.now(UTC)
        start = (now - timedelta(days=3)).strftime("%Y%m%d")
        end = now.strftime("%Y%m%d")
        url = _ECOS_URL.format(api_key=self._api_key, start=start, end=end)

        last = None
        prev = None
        try:
            async with self._session.get(
                url, timeout=aiohttp.ClientTimeout(total=self._timeout)
            ) as resp:
                if resp.status != 200:
                    logger.warning("ecos http %s", resp.status)
                    return _empty_fx()
                data = await resp.json()
            rows = data.get("StatisticSearch", {}).get("row", [])
            if len(rows) >= 2:
                last = float(rows[-1]["DATA_VALUE"])
                prev = float(rows[-2]["DATA_VALUE"])
            elif len(rows) == 1:
                last = float(rows[-1]["DATA_VALUE"])
        except Exception:
            logger.exception("ecos fetch failed")
            return _empty_fx()

        pct = None
        if last is not None and prev not in (None, 0):
            pct = (last - prev) / prev * 100.0

        return MacroSnapshot(
            ts_ms=int(time.time() * 1000),
            session="overnight_fx",
            usdkrw=last,
            usdkrw_change_pct=pct,
            collected_from=["ecos"],
        )


def _empty_fx() -> MacroSnapshot:
    return MacroSnapshot(
        ts_ms=int(time.time() * 1000),
        session="overnight_fx",
        collected_from=["ecos"],
    )
