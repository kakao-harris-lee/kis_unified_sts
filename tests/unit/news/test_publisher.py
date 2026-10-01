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


def _as_bytes(value):
    """Stream ids come back as ``bytes`` from a default client and ``str`` from a
    ``decode_responses=True`` one — normalize so the comparison does not depend on it.
    """
    return value.encode() if isinstance(value, str) else value


_MAXLEN = 2
#: Comfortably more than one radix node (100 entries), so trimming is guaranteed to have
#: something whole to drop — see :func:`test_publisher_respects_maxlen`.
_WELL_OVER_ONE_NODE = 300


@pytest.mark.asyncio
async def test_publisher_respects_maxlen(redis):
    """The stream is trimmed, and the oldest entries are the ones that go.

    ⚠ This deliberately does NOT assert ``XLEN <= maxlen``. The publisher calls
    ``xadd(..., maxlen=..., approximate=True)`` (``shared/news/publisher.py``), and
    ``MAXLEN ~`` is explicitly not a hard cap in Redis: it drops whole radix-tree nodes
    (~100 entries each) and stops, so a stream can legitimately sit well above ``maxlen``.
    The old assertion (``<= 2`` after 5 publishes) only ever passed because fakeredis
    below 2.39 emulated EXACT trimming; 2.39.0 fixed that to match Redis and the
    assertion started failing. The library became more faithful — the test was asserting a
    guarantee production does not have, so nothing downstream may rely on ``maxlen`` as a
    hard bound on this stream.

    What IS guaranteed, and what this pins: trimming happens at all, it never goes below
    ``maxlen``, and it removes from the head. A publisher that stopped passing ``maxlen``
    would leave all 300 entries and fail the upper bound here, so the regression the old
    test caught is still caught.

    An exact bound is not asserted anywhere, because reaching it would mean
    ``approximate=False``, which is a production change (and a real cost — exact trimming
    is why Redis offers the ``~`` form). If the news stream ever needs a hard cap, that is
    a deliberate decision in the publisher, with this test updated alongside it.
    """
    pub = NewsStreamPublisher(redis, stream="stream:news.raw", maxlen=_MAXLEN)
    published = [
        await pub.publish(_item(f"id_{i}")) for i in range(_WELL_OVER_ONE_NODE)
    ]
    first_id = _as_bytes(published[0])

    entries = await redis.xrange("stream:news.raw")

    # Trimming happened, and never below maxlen.
    assert _MAXLEN <= len(entries) < _WELL_OVER_ONE_NODE
    # It came off the head: the first entry published is gone.
    assert entries[0][0] != first_id
    assert first_id not in {entry_id for entry_id, _ in entries}
    # The newest entry is never trimmed.
    assert entries[-1][1][b"news_id"] == f"id_{_WELL_OVER_ONE_NODE - 1}".encode()


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
