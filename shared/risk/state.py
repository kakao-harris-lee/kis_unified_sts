"""Redis-backed risk state persistence for intraday trading sessions.

Provides ``RiskStateSnapshot`` (mutable dataclass) and ``RiskState``
(Redis HASH writer/reader) for Phase 3 risk filter infrastructure.

Key: ``risk:state:{asset_class}`` — Redis HASH with 24-hour TTL.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskStateSnapshot:
    """Mutable snapshot of intraday risk metrics.

    All fields default to zero; populated by ``RiskState.load()`` and
    written back via ``RiskState.save()``.

    Attributes:
        daily_pnl_krw: Realised + unrealised daily P&L in KRW.
        weekly_pnl_krw: Rolling weekly P&L in KRW.
        consecutive_losses: Number of consecutive losing trades.
        daily_trade_count: Number of trades executed today.
        atr_90th_percentile: 90th-percentile ATR value (used by VolatilityFilter).
    """

    daily_pnl_krw: float = 0.0
    weekly_pnl_krw: float = 0.0
    consecutive_losses: int = 0
    daily_trade_count: int = 0
    atr_90th_percentile: float = 0.0


# Internal mapping: field name -> (hash-field name, type converter)
_FIELD_MAP: dict[str, type] = {
    "daily_pnl_krw": float,
    "weekly_pnl_krw": float,
    "consecutive_losses": int,
    "daily_trade_count": int,
    "atr_90th_percentile": float,
}


class RiskState:
    """Redis-backed risk state store for a single asset class.

    Reads and writes a ``RiskStateSnapshot`` as a Redis HASH at
    ``risk:state:{asset_class}``.  A 24-hour TTL is refreshed on
    every ``save()`` call.

    Args:
        redis: An async Redis client (e.g. ``redis.asyncio.Redis`` or
            ``fakeredis.aioredis.FakeRedis``).
        asset_class: Asset class identifier, e.g. ``"futures"`` or ``"stock"``.
        key: Override the Redis key.  Defaults to ``risk:state:{asset_class}``.
        ttl_seconds: TTL applied after each write.  Defaults to 86400 (24 h).
    """

    def __init__(
        self,
        redis,
        asset_class: str,
        key: str | None = None,
        ttl_seconds: int = 86400,
    ) -> None:
        self._redis = redis
        self._asset_class = asset_class
        self._key = key if key is not None else f"risk:state:{asset_class}"
        self._ttl = ttl_seconds

    async def load(self) -> RiskStateSnapshot:
        """Load snapshot from Redis.

        Returns:
            A ``RiskStateSnapshot`` populated from the Redis HASH, or a
            zero-initialised snapshot when the key is absent.
        """
        raw: dict = await self._redis.hgetall(self._key)
        if not raw:
            return RiskStateSnapshot()

        kwargs: dict = {}
        for field_name, converter in _FIELD_MAP.items():
            raw_val = raw.get(field_name) or raw.get(field_name.encode())
            if raw_val is not None:
                if isinstance(raw_val, (bytes, bytearray)):
                    raw_val = raw_val.decode()
                kwargs[field_name] = converter(raw_val)

        return RiskStateSnapshot(**kwargs)

    async def save(self, snapshot: RiskStateSnapshot) -> None:
        """Persist snapshot to Redis with TTL refresh.

        Writes all ``RiskStateSnapshot`` fields to the Redis HASH via
        ``HSET`` and then sets a ``TTL`` of ``ttl_seconds``.

        Args:
            snapshot: The snapshot to persist.
        """
        mapping: dict[str, str] = {
            field_name: str(getattr(snapshot, field_name)) for field_name in _FIELD_MAP
        }
        await self._redis.hset(self._key, mapping=mapping)
        await self._redis.expire(self._key, self._ttl)
