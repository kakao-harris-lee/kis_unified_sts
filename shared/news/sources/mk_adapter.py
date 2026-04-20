"""Adapter over existing MKStockNewsCollector.

Strips keyword-sentiment outputs — Phase 2 LLM scorer replaces them.
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from shared.news.base import NewsItem, NewsSource

logger = logging.getLogger(__name__)


class MKNewsSourceAdapter(NewsSource):
    name = "mk"
    version = "mk-v1"
    poll_interval_seconds = 180

    def __init__(self, underlying: Any):
        self._underlying = underlying

    async def fetch(self) -> AsyncIterator[NewsItem]:
        try:
            raw_items = await self._underlying.fetch_market_news()
        except Exception:
            logger.exception("MK underlying failed")
            return

        now_ms = int(time.time() * 1000)
        for raw in raw_items:
            mk_id = raw.get("id")
            url = raw.get("url", "")
            if not mk_id and not url:
                continue
            news_id = (
                f"mk_{mk_id}"
                if mk_id
                else f"mk_{hashlib.sha256(url.encode()).hexdigest()[:16]}"
            )
            yield NewsItem(
                news_id=news_id,
                source=self.name,
                published_at_ms=raw.get("published_at_ms", now_ms),
                received_at_ms=now_ms,
                title=raw.get("title", ""),
                body=raw.get("content", ""),
                url=url,
                source_version=self.version,
                lang="ko",
                keywords=[],
            )
