"""Two-tier news ID dedupe: in-process LRU + Redis SET with TTL."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any


class _LRU:
    def __init__(self, max_size: int):
        self.max_size = max_size
        self._d: OrderedDict[str, bool] = OrderedDict()

    def __contains__(self, key: str) -> bool:
        if key in self._d:
            self._d.move_to_end(key)
            return True
        return False

    def add(self, key: str) -> None:
        if key in self._d:
            self._d.move_to_end(key)
            return
        self._d[key] = True
        if len(self._d) > self.max_size:
            self._d.popitem(last=False)


class NewsDedupe:
    """Two-tier dedupe. Async-friendly (Redis async client)."""

    KEY_PREFIX = "news:seen:v1:"

    def __init__(self, redis: Any, memory_size: int = 20_000, ttl_days: int = 7):
        self.redis = redis
        self.memory = _LRU(memory_size)
        self.ttl_seconds = ttl_days * 86400

    async def is_duplicate(self, news_id: str) -> bool:
        if news_id in self.memory:
            return True
        exists = await self.redis.exists(self.KEY_PREFIX + news_id)
        if exists:
            self.memory.add(news_id)
            return True
        return False

    async def mark_seen(self, news_id: str) -> None:
        self.memory.add(news_id)
        await self.redis.set(self.KEY_PREFIX + news_id, "1", ex=self.ttl_seconds)
