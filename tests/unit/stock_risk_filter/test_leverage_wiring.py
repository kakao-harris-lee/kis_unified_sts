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


def test_non_dict_json_record_drops_only_that_leg(sync_redis) -> None:
    """F2: a record that decodes to VALID but non-dict JSON (bare number / list /
    string) must drop ONLY that leg, not null the whole snapshot.

    ``record.get("code", code)`` is the first access, so before the
    ``isinstance(record, dict)`` guard a non-dict record raised AttributeError,
    which the per-leg ``except`` (KeyError/TypeError/ValueError/JSONDecodeError)
    does NOT catch → it escaped into ``leverage_provider._read``'s broad guard
    and nulled the WHOLE snapshot (violating "drop only the malformed leg" — the
    same lenience ``core_correlation`` applies)."""
    sync_redis.hset(
        _KEY,
        "A005930",
        json.dumps({"code": "A005930", "quantity": 10, "entry_price": 5000.0}),
    )
    sync_redis.hset(_KEY, "NUM", json.dumps(42))  # bare number
    sync_redis.hset(_KEY, "LIST", json.dumps([1, 2]))  # bare list
    sync_redis.hset(_KEY, "STR", json.dumps("oops"))  # bare string
    provider = m._build_leverage_provider(_cfg(enabled=True), sync_redis, _KEY)
    snap = provider()
    assert snap is not None  # whole snapshot preserved, not nulled
    assert {p["code"] for p in snap["positions"]} == {"A005930"}


def test_reads_order_router_write_schema_roundtrip(sync_redis) -> None:
    """F5 (#601 class): pin the read side to the order_router WRITE schema.

    ``services/stock_order_router/main.py`` (lines ~311-325) writes each open
    position as the dict mirrored below (code / name / entry_price / quantity /
    opened_at_ms / state / signal_id / strategy). The provider reads
    code / quantity / entry_price straight off it. This round-trip fails if the
    provider stops parsing that writer shape — e.g. a field rename drifts the two
    sides apart and silently zeroes leverage. (A shared schema constant would
    also catch a WRITER-side rename, but that is an order_router-scoped change;
    this read-side pin keeps the P5-3 scope contained while still failing loudly
    on read/write drift.)"""
    # Mirror services/stock_order_router/main.py:311-325 exactly.
    writer_record = {
        "code": "A005930",
        "name": "삼성전자",
        "entry_price": 71000.0,
        "quantity": 10,
        "opened_at_ms": 1_700_000_000_000,
        "state": "SURVIVAL",
        "signal_id": "sig-1",
        "strategy": "bb_reversion",
    }
    sync_redis.hset(_KEY, writer_record["code"], json.dumps(writer_record))
    provider = m._build_leverage_provider(_cfg(enabled=True), sync_redis, _KEY)
    snap = provider()
    assert snap is not None
    (leg,) = snap["positions"]
    # Only the three fields the filter needs; entry_price → current_price slot.
    assert leg == {"code": "A005930", "quantity": 10, "current_price": 71000.0}


def test_redis_error_fails_open() -> None:
    """A sync client whose hgetall raises → provider returns None (no raise)."""

    class _BoomRedis:
        def hgetall(self, _key):
            raise RuntimeError("redis down")

    provider = m._build_leverage_provider(_cfg(enabled=True), _BoomRedis(), _KEY)
    assert provider is not None
    assert provider() is None
