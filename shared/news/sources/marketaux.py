"""Marketaux financial news API source."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import aiohttp

from shared.news.base import NewsItem, NewsSource

logger = logging.getLogger(__name__)

_USER_AGENT = "kis-unified-sts-news-collector/1.0"


class MarketauxNewsSource(NewsSource):
    name = "marketaux"
    version = "marketaux-v1"
    poll_interval_seconds = 600

    def __init__(
        self,
        *,
        session: aiohttp.ClientSession,
        api_token: str,
        endpoint: str = "https://api.marketaux.com/v1/news/all",
        limit: int = 20,
        language: str = "en,ko",
        countries: str = "us,kr",
        symbols: str = "",
        entity_types: str = "equity,index",
        industries: str = "",
        search: str = "",
        domains: str = "",
        exclude_domains: str = "",
        filter_entities: bool = True,
        must_have_entities: bool = False,
        group_similar: bool = True,
        published_after_minutes: int = 720,
        poll_interval_seconds: int | None = None,
        timeout: float = 20.0,
    ):
        self._session = session
        self._api_token = api_token.strip()
        self._endpoint = endpoint
        self._limit = max(1, min(int(limit), 100))
        self._language = language.strip()
        self._countries = countries.strip()
        self._symbols = symbols.strip()
        self._entity_types = entity_types.strip()
        self._industries = industries.strip()
        self._search = search.strip()
        self._domains = domains.strip()
        self._exclude_domains = exclude_domains.strip()
        self._filter_entities = filter_entities
        self._must_have_entities = must_have_entities
        self._group_similar = group_similar
        self._published_after_minutes = max(0, int(published_after_minutes))
        self._timeout = timeout
        self.poll_interval_seconds = poll_interval_seconds or self.poll_interval_seconds

    async def fetch(self) -> AsyncIterator[NewsItem]:
        if not self._api_token:
            logger.warning("marketaux api token missing")
            return

        params = self._build_params()
        try:
            async with self._session.get(
                self._endpoint,
                params=params,
                headers={"User-Agent": _USER_AGENT},
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as resp:
                if resp.status == 429:
                    logger.warning("marketaux rate limited")
                    return
                if resp.status in (401, 403):
                    logger.warning(
                        "marketaux authentication failed: http %s", resp.status
                    )
                    return
                if resp.status != 200:
                    logger.warning("marketaux http %s", resp.status)
                    return
                text = await resp.text()
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    logger.warning("marketaux invalid json response: %s", text[:160])
                    return
        except TimeoutError:
            logger.warning("marketaux fetch timeout")
            return
        except Exception:
            logger.exception("marketaux fetch failed")
            return

        received_ts_ms = int(time.time() * 1000)
        for article in payload.get("data", []):
            item = _article_to_news_item(article, received_ts_ms)
            if item is not None:
                yield item

    def _build_params(self) -> dict[str, str]:
        params = {
            "api_token": self._api_token,
            "limit": str(self._limit),
            "filter_entities": _bool_param(self._filter_entities),
            "must_have_entities": _bool_param(self._must_have_entities),
            "group_similar": _bool_param(self._group_similar),
        }
        optional = {
            "language": self._language,
            "countries": self._countries,
            "symbols": self._symbols,
            "entity_types": self._entity_types,
            "industries": self._industries,
            "search": self._search,
            "domains": self._domains,
            "exclude_domains": self._exclude_domains,
        }
        params.update({k: v for k, v in optional.items() if v})
        if self._published_after_minutes > 0:
            cutoff = datetime.now(UTC) - timedelta(
                minutes=self._published_after_minutes
            )
            params["published_after"] = cutoff.strftime("%Y-%m-%dT%H:%M:%S")
        return params


def _article_to_news_item(
    article: Any,
    received_ts_ms: int,
) -> NewsItem | None:
    if not isinstance(article, dict):
        return None

    url = str(article.get("url", "")).strip()
    title = str(article.get("title", "")).strip()
    if not url or not title:
        return None

    raw_uuid = str(article.get("uuid", "")).strip()
    news_id = f"marketaux_{raw_uuid}" if raw_uuid else f"marketaux_{_digest(url)}"
    source_domain = str(article.get("source", "")).strip()
    entities = _as_dicts(article.get("entities"))
    entity_symbols = _entity_symbols(entities)
    body = _build_body(article, source_domain, entity_symbols)

    published_ts_s = _parse_marketaux_date(str(article.get("published_at", "")))
    return NewsItem(
        news_id=news_id,
        source=MarketauxNewsSource.name,
        published_at_ms=(
            int(published_ts_s * 1000) if published_ts_s else received_ts_ms
        ),
        received_at_ms=received_ts_ms,
        title=title,
        body=body,
        url=url,
        source_version=MarketauxNewsSource.version,
        lang=str(article.get("language", "")).strip() or "unknown",
        keywords=_keywords(article, source_domain, entity_symbols),
    )


def _build_body(
    article: dict[str, Any],
    source_domain: str,
    entity_symbols: list[str],
) -> str:
    parts = [
        str(article.get("description", "")).strip(),
        str(article.get("snippet", "")).strip(),
        f"source={source_domain}" if source_domain else "",
        f"symbols={','.join(entity_symbols)}" if entity_symbols else "",
    ]
    return " ".join(part for part in parts if part)


def _keywords(
    article: dict[str, Any],
    source_domain: str,
    entity_symbols: list[str],
) -> list[str]:
    values: list[str] = []
    raw_keywords = article.get("keywords", "")
    if isinstance(raw_keywords, str):
        values.extend(part.strip() for part in raw_keywords.split(","))
    elif isinstance(raw_keywords, list):
        values.extend(str(part).strip() for part in raw_keywords)
    values.extend(entity_symbols)
    if source_domain:
        values.append(source_domain)
    return [value for value in dict.fromkeys(values) if value]


def _entity_symbols(entities: list[dict[str, Any]]) -> list[str]:
    symbols = [str(entity.get("symbol", "")).strip() for entity in entities]
    return [symbol for symbol in dict.fromkeys(symbols) if symbol]


def _as_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _parse_marketaux_date(raw: str) -> float:
    if not raw:
        return 0.0
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _bool_param(value: bool) -> str:
    return "true" if value else "false"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]
