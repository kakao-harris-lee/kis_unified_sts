"""Generic RSS news source for official public feeds."""

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

_USER_AGENT = "kis-unified-sts-news-collector/1.0"


class GenericRSSSource(NewsSource):
    """Wrap a single official RSS feed as a ``NewsSource``."""

    version = "rss-v1"
    poll_interval_seconds = 180

    def __init__(
        self,
        *,
        session: aiohttp.ClientSession,
        name: str,
        rss_url: str,
        lang: str,
        version: str | None = None,
        poll_interval_seconds: int | None = None,
        timeout: float = 10.0,
    ):
        self.name = name
        self.version = version or f"{name}-rss-v1"
        self.poll_interval_seconds = poll_interval_seconds or self.poll_interval_seconds
        self._session = session
        self._rss_url = rss_url
        self._lang = lang
        self._timeout = timeout

    async def fetch(self) -> AsyncIterator[NewsItem]:
        try:
            async with self._session.get(
                self._rss_url,
                headers={"User-Agent": _USER_AGENT},
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as resp:
                if resp.status != 200:
                    logger.warning("%s rss http %s", self.name, resp.status)
                    return
                body = await resp.read()
        except TimeoutError:
            logger.warning("%s rss fetch timeout", self.name)
            return
        except Exception:
            logger.exception("%s rss fetch failed", self.name)
            return

        parsed = feedparser.parse(body)
        for entry in parsed.entries:
            url = entry.get("link", "")
            if not url:
                continue
            digest = hashlib.sha256(url.encode()).hexdigest()[:16]
            published_ts_s = _parse_rss_date(
                entry.get("published", "") or entry.get("updated", "")
            )
            received_ts_ms = int(time.time() * 1000)
            yield NewsItem(
                news_id=f"{self.name}_{digest}",
                source=self.name,
                published_at_ms=(
                    int(published_ts_s * 1000) if published_ts_s else received_ts_ms
                ),
                received_at_ms=received_ts_ms,
                title=entry.get("title", ""),
                body=entry.get("description", "") or entry.get("summary", ""),
                url=url,
                source_version=self.version,
                lang=self._lang,
                keywords=[],
            )


def _parse_rss_date(raw: str) -> float:
    if not raw:
        return 0.0
    try:
        return parsedate_to_datetime(raw).timestamp()
    except (TypeError, ValueError):
        return 0.0
