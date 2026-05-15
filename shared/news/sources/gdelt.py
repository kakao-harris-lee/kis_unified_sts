"""Limited GDELT DOC API source for global market-moving headlines."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import aiohttp

from shared.news.base import NewsItem, NewsSource

logger = logging.getLogger(__name__)

_USER_AGENT = "kis-unified-sts-news-collector/1.0"


class GDELTNewsSource(NewsSource):
    name = "gdelt"
    version = "gdelt-doc-v1"
    poll_interval_seconds = 600

    def __init__(
        self,
        *,
        session: aiohttp.ClientSession,
        query: str,
        max_records: int = 20,
        timespan: str = "6h",
        sort: str = "datedesc",
        poll_interval_seconds: int | None = None,
        timeout: float = 20.0,
    ):
        self._session = session
        self._query = _normalize_query(query)
        self._max_records = max(1, min(max_records, 100))
        self._timespan = timespan
        self._sort = sort
        self._timeout = timeout
        self.poll_interval_seconds = poll_interval_seconds or self.poll_interval_seconds

    async def fetch(self) -> AsyncIterator[NewsItem]:
        params = {
            "query": self._query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": str(self._max_records),
            "timespan": self._timespan,
            "sort": self._sort,
        }
        try:
            async with self._session.get(
                "https://api.gdeltproject.org/api/v2/doc/doc",
                params=params,
                headers={"User-Agent": _USER_AGENT},
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as resp:
                if resp.status == 429:
                    logger.warning("gdelt rate limited")
                    return
                if resp.status != 200:
                    logger.warning("gdelt http %s", resp.status)
                    return
                text = await resp.text()
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    logger.warning("gdelt invalid json response: %s", text[:160])
                    return
        except TimeoutError:
            logger.warning("gdelt fetch timeout")
            return
        except Exception:
            logger.exception("gdelt fetch failed")
            return

        received_ts_ms = int(time.time() * 1000)
        for article in payload.get("articles", []):
            url = article.get("url", "")
            title = article.get("title", "")
            if not url or not title:
                continue
            digest = hashlib.sha256(url.encode()).hexdigest()[:16]
            published_ts_s = _parse_gdelt_date(article.get("seendate", ""))
            domain = article.get("domain", "")
            source_country = article.get("sourcecountry", "")
            body = " ".join(
                part
                for part in (
                    title,
                    f"domain={domain}" if domain else "",
                    f"source_country={source_country}" if source_country else "",
                )
                if part
            )
            yield NewsItem(
                news_id=f"gdelt_{digest}",
                source=self.name,
                published_at_ms=(
                    int(published_ts_s * 1000) if published_ts_s else received_ts_ms
                ),
                received_at_ms=received_ts_ms,
                title=title,
                body=body,
                url=url,
                source_version=self.version,
                lang=article.get("language", "") or "unknown",
                keywords=[kw for kw in ("gdelt", domain) if kw],
            )


def _parse_gdelt_date(raw: str) -> float:
    if not raw:
        return 0.0
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=UTC).timestamp()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _normalize_query(query: str) -> str:
    normalized = query.strip()
    if " OR " in normalized and not normalized.startswith("("):
        return f"({normalized})"
    return normalized
