"""Redis-backed daily USD cap for scoring costs."""

from __future__ import annotations

from datetime import datetime
from typing import Any


class BudgetExceeded(Exception):
    """Raised when a charge would push the daily total over the configured limit."""


class DailyBudget:
    """Tracks cumulative USD spend per day using Redis INCRBYFLOAT.

    Keys are namespaced by ``{key_prefix}:{YYYYMMDD}`` and expire after
    ``ttl_seconds`` (default 48 h) so stale counters are cleaned up
    automatically.

    Args:
        redis: An async Redis client (``redis.asyncio`` or ``fakeredis.aioredis``).
        daily_usd_limit: Maximum spend allowed per calendar day.
        key_prefix: Namespace for Redis keys. Defaults to ``"scorer:cost"``.
        ttl_seconds: TTL applied to each daily key. Defaults to 172800 (48 h).
    """

    def __init__(
        self,
        redis: Any,
        *,
        daily_usd_limit: float,
        key_prefix: str = "scorer:cost",
        ttl_seconds: int = 172_800,  # 48 h
    ) -> None:
        self.redis = redis
        self.limit = daily_usd_limit
        self.prefix = key_prefix
        self.ttl = ttl_seconds

    def _key(self, date: str | None = None) -> str:
        if date is None:
            date = datetime.utcnow().strftime("%Y%m%d")
        return f"{self.prefix}:{date}"

    async def used_today(self, *, date: str | None = None) -> float:
        """Return cumulative spend for *date* (YYYYMMDD). Returns 0.0 if key absent."""
        raw = await self.redis.get(self._key(date))
        return float(raw or 0.0)

    async def charge(self, cost_usd: float, *, date: str | None = None) -> float:
        """Increment the daily counter by *cost_usd* and refresh its TTL.

        Raises:
            BudgetExceeded: If the new running total exceeds :attr:`limit`.

        Returns:
            The new running total after the increment.
        """
        key = self._key(date)
        new_total = float(await self.redis.incrbyfloat(key, cost_usd))
        await self.redis.expire(key, self.ttl)
        if new_total > self.limit:
            raise BudgetExceeded(
                f"daily cap {self.limit} USD exceeded (used={new_total:.4f})"
            )
        return new_total
