"""Unit tests for TradingStatePublisher position snapshot behavior."""

from __future__ import annotations

from datetime import datetime

from shared.models.position import Position, PositionSide
from shared.streaming import trading_state
from shared.streaming.trading_state import TradingStatePublisher


class _FakePipeline:
    def __init__(self, redis_client: _FakeRedis) -> None:
        self._redis = redis_client
        self._ops: list[tuple] = []

    def delete(self, key: str):
        self._ops.append(("delete", key))
        return self

    def hset(self, key: str, *args, **kwargs):
        self._ops.append(("hset", key, args, kwargs))
        return self

    def expire(self, key: str, ttl: int):
        self._ops.append(("expire", key, ttl))
        return self

    def execute(self):
        for op in self._ops:
            kind = op[0]
            if kind == "delete":
                _, key = op
                self._redis._hashes.pop(key, None)
            elif kind == "hset":
                _, key, args, kwargs = op
                mapping = kwargs.get("mapping")
                if mapping is not None:
                    bucket = self._redis._hashes.setdefault(key, {})
                    bucket.update(mapping)
                elif len(args) == 2:
                    field, value = args
                    bucket = self._redis._hashes.setdefault(key, {})
                    bucket[str(field)] = str(value)
            elif kind == "expire":
                # TTL behavior is not relevant for these tests.
                pass
        return []


class _FakeRedis:
    def __init__(self) -> None:
        self._hashes: dict[str, dict[str, str]] = {}

    def pipeline(self, transaction: bool = False):
        _ = transaction
        return _FakePipeline(self)

    def hgetall(self, key: str) -> dict[str, str]:
        return dict(self._hashes.get(key, {}))


def _make_position(position_id: str) -> Position:
    return Position(
        id=position_id,
        code="A05603",
        name="KOSPI200선물",
        side=PositionSide.SHORT,
        quantity=1,
        entry_price=800.0,
        entry_time=datetime.now(),
        current_price=798.0,
        strategy="rl_mppo",
    )


def test_publish_positions_update_replaces_stale_positions(monkeypatch):
    fake_redis = _FakeRedis()
    key = "trading:futures:positions"
    fake_redis._hashes[key] = {"stale-id": '{"id":"stale-id"}'}

    monkeypatch.setattr(trading_state, "_get_redis", lambda: fake_redis)
    publisher = TradingStatePublisher("futures")

    publisher.publish_positions_update([_make_position("new-id")], throttle=0.0)

    stored = fake_redis.hgetall(key)
    assert set(stored.keys()) == {"new-id"}


def test_publish_positions_update_empty_snapshot_clears_hash(monkeypatch):
    fake_redis = _FakeRedis()
    key = "trading:futures:positions"
    fake_redis._hashes[key] = {"stale-id": '{"id":"stale-id"}'}

    monkeypatch.setattr(trading_state, "_get_redis", lambda: fake_redis)
    publisher = TradingStatePublisher("futures")

    publisher.publish_positions_update([], throttle=0.0)

    assert fake_redis.hgetall(key) == {}
