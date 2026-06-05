"""Fan-out ScoredItem to Redis stream."""

from __future__ import annotations

import json
import logging
from typing import Any

from shared.scoring.base import ScoredItem

logger = logging.getLogger(__name__)

_STREAM_TTL_SECONDS = 86400  # Project Redis TTL policy — stream keys 24 h


class ScoredPublisher:
    """Fan-out a :class:`ScoredItem` to Redis XADD.

    Args:
        redis: ``redis.asyncio`` (or fakeredis) connection.
        archive_client: Ignored legacy archive hook.
        stream: Target Redis stream key (e.g. ``stream:news.scored``).
        maxlen: ``MAXLEN ~`` cap passed to ``XADD`` to bound stream size.
        archive_batch_size: Ignored legacy batch size.
    """

    def __init__(
        self,
        *,
        redis: Any,
        archive_client: Any | None = None,
        stream: str,
        maxlen: int,
        archive_batch_size: int = 20,
        **legacy_kwargs: Any,
    ) -> None:
        self.redis = redis
        self.stream = stream
        self.maxlen = maxlen
        _ = archive_client, archive_batch_size, legacy_kwargs

    async def publish(self, item: ScoredItem) -> None:
        """Write *item* to the Redis stream and refresh its TTL."""
        fields: dict[str, str] = {
            "news_id": item.news_id,
            "scorer_version": item.scorer_version,
            "scored_at_ms": str(item.scored_at_ms),
            "category": item.category,
            "sentiment": str(item.sentiment),
            "impact_score": str(item.impact_score),
            "direction_bias": item.direction_bias,
            "confidence": str(item.confidence),
            "keywords_json": json.dumps(item.keywords, ensure_ascii=False),
            "reasoning": item.reasoning,
            "raw_ref": item.raw_ref,
            "raw_source": item.raw_source,
            "raw_title": item.raw_title,
            "raw_url": item.raw_url,
            "raw_published_at_ms": str(item.raw_published_at_ms),
            "raw_keywords_json": json.dumps(item.raw_keywords, ensure_ascii=False),
        }
        await self.redis.xadd(self.stream, fields, maxlen=self.maxlen, approximate=True)
        # Mandatory TTL refresh after every write (project Redis TTL policy).
        await self.redis.expire(self.stream, _STREAM_TTL_SECONDS)

    async def flush(self) -> None:
        """Compatibility no-op."""
        return None
