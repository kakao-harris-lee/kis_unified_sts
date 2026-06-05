from unittest.mock import AsyncMock

import fakeredis.aioredis
import pytest

from shared.news.base import NewsItem
from shared.news.publisher import NewsArchiveNoopWriter, NewsStreamPublisher


def _item(news_id="x"):
    return NewsItem(
        news_id=news_id,
        source="yonhap",
        published_at_ms=1_000_000,
        received_at_ms=1_000_100,
        title="T",
        body="B",
        url="u",
        source_version="yonhap-v1",
        lang="ko",
        keywords=["kw1"],
    )


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis()


@pytest.mark.asyncio
async def test_publisher_xadd_produces_entry(redis):
    pub = NewsStreamPublisher(redis, stream="stream:news.raw", maxlen=100)
    await pub.publish(_item("a"))
    entries = await redis.xrange("stream:news.raw")
    assert len(entries) == 1
    msg_id, fields = entries[0]
    # Redis returns bytes by default
    assert fields[b"news_id"] == b"a"
    assert fields[b"source"] == b"yonhap"


@pytest.mark.asyncio
async def test_publisher_serializes_keywords_as_json(redis):
    pub = NewsStreamPublisher(redis, stream="stream:news.raw", maxlen=100)
    await pub.publish(_item("a"))
    entries = await redis.xrange("stream:news.raw")
    fields = entries[0][1]
    assert b"keywords_json" in fields
    assert fields[b"keywords_json"] == b'["kw1"]'


@pytest.mark.asyncio
async def test_publisher_respects_maxlen(redis):
    pub = NewsStreamPublisher(redis, stream="stream:news.raw", maxlen=2)
    for i in range(5):
        await pub.publish(_item(f"id_{i}"))
    entries = await redis.xrange("stream:news.raw")
    assert len(entries) <= 2


@pytest.mark.asyncio
async def test_publisher_sets_stream_ttl(redis):
    """Project Redis TTL policy: every XADD must be followed by expire(key, 86400)."""
    pub = NewsStreamPublisher(redis, stream="stream:news.raw", maxlen=100)
    await pub.publish(_item("a"))
    ttl = await redis.ttl("stream:news.raw")
    assert 0 < ttl <= 86400


@pytest.mark.asyncio
async def test_publisher_also_publishes_to_pubsub_channel(redis):
    """Forecasting EventImpactScorer subscribes to the ``news:raw`` pubsub
    channel — without this fan-out Setup C never sees event_scores rows.
    Regression for the 2026-05-28 Setup C-zero-signals discovery.
    """
    pubsub = redis.pubsub()
    await pubsub.subscribe("news:raw")
    # Drain the subscribe confirmation message
    await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)

    pub = NewsStreamPublisher(redis, stream="stream:news.raw", maxlen=100)
    await pub.publish(_item("a"))

    msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
    assert msg is not None and msg["type"] == "message"
    data = msg["data"]
    if isinstance(data, bytes):
        data = data.decode()
    # _item() yields title="T", body="B" — both must reach scorer
    assert "T" in data
    assert "B" in data
    await pubsub.unsubscribe("news:raw")
    await pubsub.close()


@pytest.mark.asyncio
async def test_archive_writer_noops_on_batch_size():
    archive_client = AsyncMock()
    writer = NewsArchiveNoopWriter(
        archive_client, batch_size=3, flush_interval_seconds=60
    )
    await writer.enqueue(_item("a"))
    await writer.enqueue(_item("b"))
    archive_client.execute.assert_not_awaited()
    await writer.enqueue(_item("c"))
    archive_client.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_archive_writer_noop_when_disabled():
    writer = NewsArchiveNoopWriter(None, batch_size=1, flush_interval_seconds=60)
    await writer.enqueue(_item("disabled"))
    await writer.flush()


@pytest.mark.asyncio
async def test_archive_writer_flush_explicit_noops():
    archive_client = AsyncMock()
    writer = NewsArchiveNoopWriter(
        archive_client, batch_size=100, flush_interval_seconds=60
    )
    await writer.enqueue(_item("a"))
    await writer.flush()
    archive_client.execute.assert_not_awaited()
