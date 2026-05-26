"""Naver Search API news source for pre-market market/theme context."""

from __future__ import annotations

import hashlib
import html
import json
import logging
import re
import time
from collections.abc import AsyncIterator
from email.utils import parsedate_to_datetime
from typing import Any

import aiohttp

from shared.news.base import NewsItem, NewsSource

logger = logging.getLogger(__name__)

_USER_AGENT = "kis-unified-sts-news-collector/1.0"
_TAG_RE = re.compile(r"<[^>]+>")


class NaverNewsSearchSource(NewsSource):
    name = "naver_search"
    version = "naver-search-v1"
    poll_interval_seconds = 300

    def __init__(
        self,
        *,
        session: aiohttp.ClientSession,
        client_id: str,
        client_secret: str,
        endpoint: str = "https://openapi.naver.com/v1/search/news.json",
        queries: list[str] | None = None,
        display: int = 10,
        sort: str = "date",
        poll_interval_seconds: int | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._session = session
        self._client_id = client_id.strip()
        self._client_secret = client_secret.strip()
        self._endpoint = endpoint
        self._queries = [q.strip() for q in queries or [] if q.strip()]
        self._display = max(1, min(int(display), 100))
        self._sort = sort if sort in {"sim", "date"} else "date"
        self._timeout = timeout
        self.poll_interval_seconds = poll_interval_seconds or self.poll_interval_seconds

    async def fetch(self) -> AsyncIterator[NewsItem]:
        if not self._client_id or not self._client_secret:
            logger.warning("naver search credentials missing")
            return
        if not self._queries:
            logger.warning("naver search queries missing")
            return

        received_ts_ms = int(time.time() * 1000)
        for query in self._queries:
            payload = await self._fetch_query(query)
            if not payload:
                continue
            for raw_item in payload.get("items", []):
                item = _article_to_news_item(raw_item, query, received_ts_ms)
                if item is not None:
                    yield item

    async def _fetch_query(self, query: str) -> dict[str, Any] | None:
        try:
            async with self._session.get(
                self._endpoint,
                params={
                    "query": query,
                    "display": str(self._display),
                    "start": "1",
                    "sort": self._sort,
                },
                headers={
                    "User-Agent": _USER_AGENT,
                    "X-Naver-Client-Id": self._client_id,
                    "X-Naver-Client-Secret": self._client_secret,
                },
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as resp:
                if resp.status == 429:
                    logger.warning("naver search rate limited query=%s", query)
                    return None
                if resp.status in (401, 403):
                    logger.warning(
                        "naver search authentication failed: http %s", resp.status
                    )
                    return None
                if resp.status != 200:
                    logger.warning("naver search http %s query=%s", resp.status, query)
                    return None
                text = await resp.text()
        except TimeoutError:
            logger.warning("naver search fetch timeout query=%s", query)
            return None
        except Exception:
            logger.exception("naver search fetch failed query=%s", query)
            return None

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("naver search invalid json response: %s", text[:160])
            return None
        return payload if isinstance(payload, dict) else None


def _article_to_news_item(
    article: Any,
    query: str,
    received_ts_ms: int,
) -> NewsItem | None:
    if not isinstance(article, dict):
        return None

    title = _clean_text(article.get("title", ""))
    url = str(article.get("originallink") or article.get("link") or "").strip()
    if not title or not url:
        return None

    link = str(article.get("link") or "").strip()
    description = _clean_text(article.get("description", ""))
    pub_ts_s = _parse_pub_date(str(article.get("pubDate", "")))
    return NewsItem(
        news_id=f"{NaverNewsSearchSource.name}_{_digest(url or link or title)}",
        source=NaverNewsSearchSource.name,
        published_at_ms=int(pub_ts_s * 1000) if pub_ts_s else received_ts_ms,
        received_at_ms=received_ts_ms,
        title=title,
        body=description,
        url=url,
        source_version=NaverNewsSearchSource.version,
        lang="ko",
        keywords=[query],
    )


def _clean_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    return _TAG_RE.sub("", text).strip()


def _parse_pub_date(raw: str) -> float:
    if not raw:
        return 0.0
    try:
        return parsedate_to_datetime(raw).timestamp()
    except (TypeError, ValueError):
        return 0.0


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]
