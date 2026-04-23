"""News stream publisher (Redis XADD) + ClickHouse batched writer."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from shared.news.base import NewsItem

logger = logging.getLogger(__name__)


_STREAM_TTL_SECONDS = 86400  # Project Redis TTL policy (memory: stream keys 24h)


class NewsStreamPublisher:
    """Minimal publisher targeting stream:news.raw.

    Does NOT reuse shared.streaming.publisher.StreamPublisher because that
    one is sync and uses a global correlation-id tracer — not needed here.
    """

    def __init__(self, redis: Any, stream: str, maxlen: int):
        self.redis = redis
        self.stream = stream
        self.maxlen = maxlen

    async def publish(self, item: NewsItem, max_body_chars: int = 2000) -> str:
        payload = item.to_stream_dict(max_body_chars=max_body_chars)
        # Redis XADD requires scalar values; serialize lists as JSON
        fields: dict[str, str] = {}
        for k, v in payload.items():
            if isinstance(v, (list, dict)):
                fields[f"{k}_json"] = json.dumps(v, ensure_ascii=False)
            else:
                fields[k] = str(v) if v is not None else ""
        msg_id = await self.redis.xadd(
            self.stream, fields, maxlen=self.maxlen, approximate=True
        )
        await self.redis.expire(self.stream, _STREAM_TTL_SECONDS)
        return msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)


class ClickHouseNewsWriter:
    """Batches inserts into kospi.news_raw."""

    _INSERT_SQL = (
        "INSERT INTO kospi.news_raw "
        "(news_id, source, published_at, received_at, title, body, url, "
        "source_version, lang, keywords) VALUES"
    )

    def __init__(
        self, ch_client: Any, batch_size: int = 50, flush_interval_seconds: int = 10
    ):
        self.ch = ch_client
        self.batch_size = batch_size
        self.flush_interval = flush_interval_seconds
        self._buffer: list[tuple] = []
        self._lock = asyncio.Lock()

    async def enqueue(self, item: NewsItem) -> None:
        row = (
            item.news_id,
            item.source,
            datetime.fromtimestamp(item.published_at_ms / 1000, tz=UTC).replace(
                tzinfo=None
            ),
            datetime.fromtimestamp(item.received_at_ms / 1000, tz=UTC).replace(
                tzinfo=None
            ),
            item.title,
            item.body,
            item.url,
            item.source_version,
            item.lang,
            item.keywords,
        )
        async with self._lock:
            self._buffer.append(row)
            should_flush = len(self._buffer) >= self.batch_size
        if should_flush:
            await self.flush()

    async def flush(self) -> None:
        async with self._lock:
            if not self._buffer:
                return
            rows = self._buffer
            self._buffer = []
        try:
            await self.ch.execute(self._INSERT_SQL, rows)
        except Exception:
            logger.exception("CH flush failed; dropping %d rows", len(rows))

    async def run_periodic_flush(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self.flush_interval)
            except TimeoutError:
                await self.flush()
        await self.flush()
