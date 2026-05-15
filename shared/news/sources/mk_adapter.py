"""Adapter over existing MKStockNewsCollector.

Strips keyword-sentiment outputs — Phase 2 LLM scorer replaces them.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections.abc import AsyncIterator
from inspect import isawaitable
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
            raw_items = await self._fetch_raw_items()
        except Exception:
            logger.exception("MK underlying failed")
            return

        now_ms = int(time.time() * 1000)
        for raw in raw_items:
            mk_id = raw.get("id")
            url = raw.get("url", "") or raw.get("link", "")
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
                body=raw.get("content", "") or raw.get("summary", ""),
                url=url,
                source_version=self.version,
                lang="ko",
                keywords=[],
            )

    async def _fetch_raw_items(self) -> list[dict[str, Any]]:
        fetch_market_news = getattr(self._underlying, "fetch_market_news", None)
        if callable(fetch_market_news):
            result = fetch_market_news()
            if isawaitable(result):
                result = await result
            return _extract_items(result)

        collect = getattr(self._underlying, "collect", None)
        if callable(collect):
            result = await asyncio.to_thread(collect)
            return _extract_items(result)

        get_market_news = getattr(self._underlying, "_get_market_news", None)
        if callable(get_market_news):
            result = await asyncio.to_thread(get_market_news)
            return _extract_items(result)

        raise AttributeError("MK underlying has no supported news fetch method")


def _extract_items(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        raw = raw.get("market_news", [])
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]
