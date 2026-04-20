"""End-to-end: inject a fake source → daemon publishes to Redis + CH."""

import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import fakeredis.aioredis
import pytest

from services.news_collector.main import NewsCollectorDaemon
from shared.news.base import NewsItem, NewsSource


class _FakeSource(NewsSource):
    name = "fake"
    version = "fake-v1"
    poll_interval_seconds = 1

    def __init__(self, items: list[NewsItem]):
        self._items = items
        self._served = False

    async def fetch(self) -> AsyncIterator[NewsItem]:
        # serve once, then nothing (simulate empty poll cycles)
        if self._served:
            return
        self._served = True
        for it in self._items:
            yield it


def _item(news_id: str) -> NewsItem:
    return NewsItem(
        news_id=news_id,
        source="fake",
        published_at_ms=1_000_000,
        received_at_ms=1_000_100,
        title="t",
        body="b",
        url="u",
        source_version="fake-v1",
        lang="ko",
        keywords=[],
    )


@pytest.mark.asyncio
async def test_daemon_publishes_and_writes(tmp_path):
    redis = fakeredis.aioredis.FakeRedis()
    ch = AsyncMock()
    source = _FakeSource(items=[_item("a"), _item("b"), _item("a")])  # dup "a"

    daemon = NewsCollectorDaemon(
        redis=redis,
        ch_client=ch,
        sources=[source],
        stream="stream:news.raw",
        stream_maxlen=100,
        dedupe_memory=100,
        dedupe_ttl_days=1,
        ch_batch_size=2,
        ch_flush_interval=60,
        body_truncate_chars=1000,
    )

    task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.5)  # let one cycle run
    await daemon.stop()
    await task

    entries = await redis.xrange("stream:news.raw")
    ids_in_stream = [e[1][b"news_id"] for e in entries]
    assert b"a" in ids_in_stream
    assert b"b" in ids_in_stream
    # duplicate "a" should not appear twice
    assert ids_in_stream.count(b"a") == 1

    # CH batch flush triggered (2 rows = batch_size=2)
    assert ch.execute.await_count >= 1
