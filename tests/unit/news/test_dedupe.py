import fakeredis.aioredis
import pytest

from shared.news.dedupe import NewsDedupe


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis()


@pytest.mark.asyncio
async def test_new_id_is_not_duplicate(redis):
    d = NewsDedupe(redis, memory_size=10, ttl_days=1)
    assert await d.is_duplicate("dart_001") is False


@pytest.mark.asyncio
async def test_marked_id_is_duplicate_via_memory(redis):
    d = NewsDedupe(redis, memory_size=10, ttl_days=1)
    await d.mark_seen("dart_001")
    assert await d.is_duplicate("dart_001") is True


@pytest.mark.asyncio
async def test_duplicate_via_redis_when_memory_evicted(redis):
    d = NewsDedupe(redis, memory_size=2, ttl_days=1)
    await d.mark_seen("a")
    await d.mark_seen("b")
    await d.mark_seen("c")  # evicts "a" from memory
    assert "a" not in d.memory
    # Still duplicate because redis persists it
    assert await d.is_duplicate("a") is True


@pytest.mark.asyncio
async def test_ttl_set_on_redis_key(redis):
    d = NewsDedupe(redis, memory_size=10, ttl_days=7)
    await d.mark_seen("x")
    ttl = await redis.ttl("news:seen:v1:x")
    # ttl > 0 means expiration is set
    assert 0 < ttl <= 7 * 86400
