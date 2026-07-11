"""P5-3: stock-chain LeverageFilter provider wiring (_build_leverage_provider).

Reuses the existing M4 ``stock_daemon_positions_key`` hash (records carry
``entry_price`` / ``quantity``) and ``StockRiskConfig.account_equity_krw`` — no
new Redis key. The stock hash has no ``current_price``, so ``entry_price`` is
mapped into the filter's ``current_price`` slot (entry-notional leverage). The
provider is fail-open: a malformed record is dropped and a Redis error returns
``None``.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import fakeredis
import pytest

import services.stock_risk_filter.main as m

_KEY = "stock:m4:positions"


def _cfg(*, enabled: bool, equity: int = 10_000_000) -> SimpleNamespace:
    return SimpleNamespace(
        leverage=SimpleNamespace(enabled=enabled, mode="shadow"),
        account_equity_krw=equity,
    )


@pytest.fixture
def sync_redis():
    return fakeredis.FakeStrictRedis(decode_responses=True)


def test_disabled_returns_none(sync_redis) -> None:
    """Default (leverage.enabled=False) → no provider (filter never built)."""
    assert m._build_leverage_provider(_cfg(enabled=False), sync_redis, _KEY) is None


def test_no_leverage_attr_returns_none(sync_redis) -> None:
    cfg = SimpleNamespace(account_equity_krw=10_000_000)
    assert m._build_leverage_provider(cfg, sync_redis, _KEY) is None


def test_reads_and_normalizes_positions_hash(sync_redis) -> None:
    sync_redis.hset(
        _KEY,
        "A005930",
        json.dumps({"code": "A005930", "quantity": 10, "entry_price": 5000.0}),
    )
    sync_redis.hset(
        _KEY,
        "A000660",
        json.dumps({"code": "A000660", "quantity": 2, "entry_price": 3000.0}),
    )
    provider = m._build_leverage_provider(_cfg(enabled=True), sync_redis, _KEY)
    assert provider is not None
    snap = provider()
    assert snap is not None
    assert snap["equity_krw"] == 10_000_000
    by_code = {p["code"]: p for p in snap["positions"]}
    # entry_price is mapped into the current_price slot (entry-notional leverage).
    assert by_code["A005930"] == {
        "code": "A005930",
        "quantity": 10,
        "current_price": 5000.0,
    }
    assert by_code["A000660"]["current_price"] == 3000.0


def test_empty_hash_returns_empty_book(sync_redis) -> None:
    provider = m._build_leverage_provider(_cfg(enabled=True), sync_redis, _KEY)
    assert provider is not None
    assert provider() == {"positions": [], "equity_krw": 10_000_000}


def test_malformed_record_is_dropped(sync_redis) -> None:
    """A record missing entry_price drops out (fail-open, understates leverage)
    rather than poisoning the whole read — same lenience as core_correlation."""
    sync_redis.hset(
        _KEY,
        "A005930",
        json.dumps({"code": "A005930", "quantity": 10, "entry_price": 5000.0}),
    )
    sync_redis.hset(_KEY, "BAD", json.dumps({"code": "BAD", "quantity": 1}))  # no price
    sync_redis.hset(_KEY, "NOTJSON", "{not-json")
    provider = m._build_leverage_provider(_cfg(enabled=True), sync_redis, _KEY)
    snap = provider()
    assert snap is not None
    codes = {p["code"] for p in snap["positions"]}
    assert codes == {"A005930"}


def test_redis_error_fails_open() -> None:
    """A sync client whose hgetall raises → provider returns None (no raise)."""

    class _BoomRedis:
        def hgetall(self, _key):
            raise RuntimeError("redis down")

    provider = m._build_leverage_provider(_cfg(enabled=True), _BoomRedis(), _KEY)
    assert provider is not None
    assert provider() is None
