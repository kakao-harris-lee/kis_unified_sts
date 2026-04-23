"""Pluggable news source framework."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

_TRUNCATION_MARKER = "...[truncated]"


@dataclass(frozen=True)
class NewsItem:
    news_id: str
    source: str
    published_at_ms: int
    received_at_ms: int
    title: str
    body: str
    url: str
    source_version: str
    lang: str
    keywords: list[str] = field(default_factory=list)

    def to_stream_dict(self, max_body_chars: int = 2000) -> dict:
        body = self.body
        if len(body) > max_body_chars:
            body = body[:max_body_chars] + _TRUNCATION_MARKER
        return {
            "news_id": self.news_id,
            "source": self.source,
            "published_at_ms": self.published_at_ms,
            "received_at_ms": self.received_at_ms,
            "title": self.title,
            "body": body,
            "url": self.url,
            "source_version": self.source_version,
            "lang": self.lang,
            "keywords": self.keywords,
        }


class NewsSource(ABC):
    """Async source. Framework handles dedupe, publish, logging.

    Subclasses:
      - set class attributes: name, version, poll_interval_seconds
      - implement fetch() yielding NewsItem instances (dedup-naive).
    """

    name: str
    version: str
    poll_interval_seconds: int

    @abstractmethod
    async def fetch(self) -> AsyncIterator[NewsItem]:
        """Yield NewsItems from one polling cycle. Must be side-effect-free."""
        raise NotImplementedError
        yield  # pragma: no cover — makes this an async generator

    async def healthcheck(self) -> bool:
        """Override if source has a cheap readiness check. Default: True."""
        return True
