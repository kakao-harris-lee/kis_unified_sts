"""News stream publisher (Redis XADD) plus optional ClickHouse mirror writer."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from shared.news.base import NewsItem

logger = logging.getLogger(__name__)


_STREAM_TTL_SECONDS = 86400  # Project Redis TTL policy (memory: stream keys 24h)


_PUBSUB_CHANNEL = "news:raw"  # consumed by forecasting EventImpactScorer
_PUBSUB_MAX_TEXT_CHARS = 1000  # cap pubsub payload independently of stream body


class NewsStreamPublisher:
    """Minimal publisher targeting stream:news.raw + news:raw pubsub.

    Does NOT reuse shared.streaming.publisher.StreamPublisher because that
    one is sync and uses a global correlation-id tracer — not needed here.

    Two outputs per news item:
      * Redis XADD to ``stream:news.raw`` — durable, consumed by archivers
        and replay tooling (24h TTL).
      * Redis PUBLISH to ``news:raw`` — ephemeral fan-out consumed by the
        forecasting EventImpactScorer (``services/forecasting/main.py``).
        Without this fan-out Setup C never sees ``event_scores`` rows and
        produces zero signals indefinitely (root cause discovered 2026-05-28).
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

        # Fan-out to pubsub for forecasting EventImpactScorer.
        # Body is intentionally separate from the stream payload — scorer only
        # needs short event text, not the full archive row.
        try:
            text = (item.title or "").strip()
            if item.body:
                text = f"{text} {item.body.strip()}" if text else item.body.strip()
            if text:
                await self.redis.publish(_PUBSUB_CHANNEL, text[:_PUBSUB_MAX_TEXT_CHARS])
        except Exception as e:  # noqa: BLE001 — pubsub fan-out is best-effort
            logger.warning("news:raw pubsub publish failed: %s", e)

        return msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id)


class ClickHouseNewsWriter:
    """Batches optional inserts into kospi.news_raw."""

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
        if self.ch is None or self.batch_size <= 0:
            return
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
        if self.ch is None:
            return
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
