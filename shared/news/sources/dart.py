"""DART 공시 source — adapts existing DARTDataCollector."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from datetime import UTC
from typing import Any

from shared.news.base import NewsItem, NewsSource

logger = logging.getLogger(__name__)


class DARTNewsSource(NewsSource):
    """Wraps shared.llm.collectors.DARTDataCollector for the streaming pipeline."""

    name = "dart"
    version = "dart-v1"
    poll_interval_seconds = 30

    def __init__(self, collector: Any):
        # `collector` exposes an async fetch_recent_filings() -> list[dict]
        self._collector = collector

    async def fetch(self) -> AsyncIterator[NewsItem]:
        try:
            filings = await self._collector.fetch_recent_filings()
        except Exception:
            logger.exception("DART fetch failed")
            return

        now_ms = int(time.time() * 1000)
        for f in filings:
            rcept_no = f.get("rcept_no")
            if not rcept_no:
                continue
            corp = f.get("corp_name", "")
            report = f.get("report_nm", "")
            published_ms = _parse_rcept_dt(f.get("rcept_dt"), fallback_ms=now_ms)
            yield NewsItem(
                news_id=f"dart_{rcept_no}",
                source=self.name,
                published_at_ms=published_ms,
                received_at_ms=now_ms,
                title=f"[DART] {corp} — {report}".strip(),
                body=f.get("report_nm", ""),
                url=f.get("url", ""),
                source_version=self.version,
                lang="ko",
                keywords=[corp] if corp else [],
            )


def _parse_rcept_dt(raw: Any, fallback_ms: int) -> int:
    if not raw or not isinstance(raw, str) or len(raw) < 8:
        return fallback_ms
    # YYYYMMDD — use 00:00 UTC of that day
    try:
        from datetime import datetime

        dt = datetime.strptime(raw[:8], "%Y%m%d").replace(tzinfo=UTC)
        return int(dt.timestamp() * 1000)
    except ValueError:
        return fallback_ms
