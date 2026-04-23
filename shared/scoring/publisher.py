"""Fan-out ScoredItem → Redis stream + ClickHouse batch."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from shared.scoring.base import ScoredItem

logger = logging.getLogger(__name__)

_STREAM_TTL_SECONDS = 86400  # Project Redis TTL policy — stream keys 24 h

_CH_INSERT = (
    "INSERT INTO kospi.news_scored "
    "(news_id, scorer_version, scored_at, category, sentiment, impact_score, "
    "direction_bias, confidence, keywords, reasoning) VALUES"
)


class ScoredPublisher:
    """Fan-out a :class:`ScoredItem` to Redis XADD and a ClickHouse batch buffer.

    Args:
        redis: ``redis.asyncio`` (or fakeredis) connection.
        ch_client: ``aiochclient`` :class:`AsyncClickHouseClient` instance.
        stream: Target Redis stream key (e.g. ``stream:news.scored``).
        maxlen: ``MAXLEN ~`` cap passed to ``XADD`` to bound stream size.
        ch_batch_size: Number of rows to accumulate before flushing to CH.
    """

    def __init__(
        self,
        *,
        redis: Any,
        ch_client: Any,
        stream: str,
        maxlen: int,
        ch_batch_size: int = 20,
    ) -> None:
        self.redis = redis
        self.ch = ch_client
        self.stream = stream
        self.maxlen = maxlen
        self.ch_batch_size = ch_batch_size
        self._buffer: list[tuple] = []
        self._lock = asyncio.Lock()

    async def publish(self, item: ScoredItem) -> None:
        """Write *item* to the Redis stream and enqueue for CH batch insert.

        The Redis TTL policy requires ``expire`` after every ``XADD``.
        The ClickHouse ``scored_at`` is written as a **tz-naive** datetime so
        that ``aiochclient`` serialises it as ``YYYY-MM-DD HH:MM:SS`` — the
        format accepted by ``DateTime64(3, 'UTC')``.
        """
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
        }
        await self.redis.xadd(self.stream, fields, maxlen=self.maxlen, approximate=True)
        # Mandatory TTL refresh after every write (project Redis TTL policy).
        await self.redis.expire(self.stream, _STREAM_TTL_SECONDS)

        # ClickHouse row — scored_at must be tz-naive (aiochclient constraint).
        scored_at = datetime.fromtimestamp(item.scored_at_ms / 1000, tz=UTC).replace(
            tzinfo=None
        )

        row = (
            item.news_id,
            item.scorer_version,
            scored_at,
            item.category,
            item.sentiment,
            item.impact_score,
            item.direction_bias,
            item.confidence,
            item.keywords,
            item.reasoning,
        )
        async with self._lock:
            self._buffer.append(row)
            should_flush = len(self._buffer) >= self.ch_batch_size

        if should_flush:
            await self.flush()

    async def flush(self) -> None:
        """Flush any buffered rows to ClickHouse immediately."""
        async with self._lock:
            if not self._buffer:
                return
            rows = self._buffer
            self._buffer = []
        try:
            await self.ch.execute(_CH_INSERT, rows)
        except Exception:
            logger.exception("news_scored flush failed; dropping %d rows", len(rows))
