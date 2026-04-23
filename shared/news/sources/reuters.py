"""Reuters Korea business RSS source (English content)."""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import AsyncIterator
from email.utils import parsedate_to_datetime

import aiohttp
import feedparser

from shared.news.base import NewsItem, NewsSource

logger = logging.getLogger(__name__)


class ReutersRSSSource(NewsSource):
    name = "reuters"
    version = "reuters-v1"
    poll_interval_seconds = 120

    def __init__(
        self, session: aiohttp.ClientSession, rss_url: str, timeout: float = 10.0
    ):
        self._session = session
        self._rss_url = rss_url
        self._timeout = timeout

    async def fetch(self) -> AsyncIterator[NewsItem]:
        try:
            async with self._session.get(
                self._rss_url,
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as resp:
                if resp.status != 200:
                    logger.warning("reuters http %s", resp.status)
                    return
                body = await resp.read()
        except Exception:
            logger.exception("reuters fetch failed")
            return

        parsed = feedparser.parse(body)
        for entry in parsed.entries:
            url = entry.get("link", "")
            if not url:
                continue
            digest = hashlib.sha256(url.encode()).hexdigest()[:16]
            published_ts_s = _parse_rss_date(entry.get("published", ""))
            received_ts_ms = int(time.time() * 1000)
            yield NewsItem(
                news_id=f"reuters_{digest}",
                source=self.name,
                published_at_ms=(
                    int(published_ts_s * 1000) if published_ts_s else received_ts_ms
                ),
                received_at_ms=received_ts_ms,
                title=entry.get("title", ""),
                body=entry.get("description", ""),
                url=url,
                source_version=self.version,
                lang="en",
                keywords=[],
            )


def _parse_rss_date(raw: str) -> float:
    if not raw:
        return 0.0
    try:
        return parsedate_to_datetime(raw).timestamp()
    except (TypeError, ValueError):
        return 0.0
