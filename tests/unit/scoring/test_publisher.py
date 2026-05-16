"""Tests for shared/scoring/publisher.py — ScoredPublisher fan-out."""

from unittest.mock import AsyncMock

import fakeredis.aioredis
import pytest

from shared.scoring.base import ScoredItem
from shared.scoring.publisher import ScoredPublisher

_STREAM = "stream:news.scored"
_STREAM_TTL_SECONDS = 86400


def _item(news_id: str = "n1") -> ScoredItem:
    return ScoredItem(
        news_id=news_id,
        scorer_version="gpt-4o-mini-v1",
        scored_at_ms=1_700_000_000_000,
        category="macro_us",
        sentiment=0.5,
        impact_score=0.8,
        direction_bias="long",
        confidence=0.85,
        keywords=["fomc"],
        reasoning="hawkish",
        raw_source="marketaux",
        raw_title="Samsung headline",
        raw_url="https://example.com/news",
        raw_published_at_ms=1_700_000_000_000,
        raw_keywords=["005930.KS", "삼성전자"],
    )


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis()


@pytest.mark.asyncio
async def test_publish_writes_to_stream(redis):
    ch = AsyncMock()
    pub = ScoredPublisher(
        redis=redis,
        ch_client=ch,
        stream=_STREAM,
        maxlen=100,
    )
    await pub.publish(_item("a"))
    entries = await redis.xrange(_STREAM)
    assert len(entries) == 1
    assert entries[0][1][b"news_id"] == b"a"
    assert entries[0][1][b"category"] == b"macro_us"
    assert entries[0][1][b"raw_source"] == b"marketaux"
    assert entries[0][1][b"raw_title"] == b"Samsung headline"


@pytest.mark.asyncio
async def test_publish_batches_ch_writes(redis):
    ch = AsyncMock()
    pub = ScoredPublisher(
        redis=redis,
        ch_client=ch,
        stream=_STREAM,
        maxlen=100,
        ch_batch_size=2,
    )
    await pub.publish(_item("a"))
    ch.execute.assert_not_awaited()
    await pub.publish(_item("b"))
    ch.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_publish_flush_on_stop(redis):
    ch = AsyncMock()
    pub = ScoredPublisher(
        redis=redis,
        ch_client=ch,
        stream=_STREAM,
        maxlen=100,
        ch_batch_size=10,
    )
    await pub.publish(_item("a"))
    await pub.flush()
    ch.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_stream_has_ttl_after_publish(redis):
    """After publish, the stream key must carry a TTL (Redis TTL policy)."""
    ch = AsyncMock()
    pub = ScoredPublisher(
        redis=redis,
        ch_client=ch,
        stream=_STREAM,
        maxlen=100,
    )
    await pub.publish(_item("ttl_check"))
    ttl = await redis.ttl(_STREAM)
    assert (
        0 < ttl <= _STREAM_TTL_SECONDS
    ), f"Expected TTL in (0, {_STREAM_TTL_SECONDS}], got {ttl}"


@pytest.mark.asyncio
async def test_flush_noop_when_buffer_empty(redis):
    """flush() on an empty buffer must not call ch.execute."""
    ch = AsyncMock()
    pub = ScoredPublisher(
        redis=redis,
        ch_client=ch,
        stream=_STREAM,
        maxlen=100,
    )
    await pub.flush()
    ch.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_ch_execute_called_with_correct_fields(redis):
    """CH row must include scored_at as naive datetime (no tz info)."""
    from datetime import datetime

    ch = AsyncMock()
    pub = ScoredPublisher(
        redis=redis,
        ch_client=ch,
        stream=_STREAM,
        maxlen=100,
        ch_batch_size=1,
    )
    item = _item("tz_check")
    await pub.publish(item)

    ch.execute.assert_awaited_once()
    call_args = ch.execute.call_args
    rows = call_args[0][1]  # positional arg: rows list
    assert len(rows) == 1
    row = rows[0]
    # scored_at must be a naive datetime (no tzinfo)
    scored_at = row[2]
    assert isinstance(scored_at, datetime)
    assert scored_at.tzinfo is None, "scored_at must be tz-naive for aiochclient"


@pytest.mark.asyncio
async def test_stream_fields_are_scalar_strings(redis):
    """All stream fields must be plain strings (not JSON blobs for scalar values)."""
    ch = AsyncMock()
    pub = ScoredPublisher(
        redis=redis,
        ch_client=ch,
        stream=_STREAM,
        maxlen=100,
    )
    await pub.publish(_item("fields_check"))
    entries = await redis.xrange(_STREAM)
    fields = entries[0][1]
    # scalar numeric fields must be parseable
    assert float(fields[b"sentiment"]) == 0.5
    assert float(fields[b"impact_score"]) == 0.8
    assert float(fields[b"confidence"]) == 0.85
    # keywords stored as JSON
    import json

    assert json.loads(fields[b"keywords_json"]) == ["fomc"]
    assert json.loads(fields[b"raw_keywords_json"]) == ["005930.KS", "삼성전자"]


@pytest.mark.asyncio
async def test_flush_reraises_clickhouse_failure(redis):
    """CH failures MUST propagate so the daemon leaves the source message pending.

    The consumer-group invariant (see services/news_scorer/main.py module
    docstring "Publisher failure → NO XACK") only holds if publish()/flush()
    actually raise on CH errors. Swallowing would cause XADD-succeeded +
    CH-failed + XACK → unrecoverable Redis/CH split-brain.
    """
    ch = AsyncMock()
    ch.execute.side_effect = RuntimeError("clickhouse down")
    pub = ScoredPublisher(
        redis=redis,
        ch_client=ch,
        stream=_STREAM,
        maxlen=100,
        ch_batch_size=1,
    )
    with pytest.raises(RuntimeError, match="clickhouse down"):
        await pub.publish(_item("ch_fail"))


@pytest.mark.asyncio
async def test_explicit_flush_reraises_clickhouse_failure(redis):
    ch = AsyncMock()
    pub = ScoredPublisher(
        redis=redis,
        ch_client=ch,
        stream=_STREAM,
        maxlen=100,
        ch_batch_size=10,  # no auto-flush
    )
    await pub.publish(_item("a"))
    ch.execute.side_effect = RuntimeError("clickhouse down")
    with pytest.raises(RuntimeError, match="clickhouse down"):
        await pub.flush()
