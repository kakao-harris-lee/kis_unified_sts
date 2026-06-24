"""Tests for on-entry daily-coverage backfill queue + worker."""

from __future__ import annotations

import asyncio

import fakeredis
import pytest

from shared.collector.historical import coverage as cov
from shared.collector.historical.coverage import (
    PENDING_KEY,
    CoverageConfig,
    enqueue_symbols,
    ensure_daily_coverage,
)


@pytest.fixture
def redis_client():
    return fakeredis.FakeStrictRedis(decode_responses=True)


class _FakeStore:
    """Returns a configured daily-bar count per code; mutable for deepen sim."""

    def __init__(self, depths: dict[str, int]):
        self._depths = dict(depths)

    def get_daily_bars(self, code, **_kw):
        import pandas as pd

        n = self._depths.get(code, 0)
        return pd.DataFrame({"datetime": list(range(n)), "close": [1.0] * n})


def _cfg(**kw) -> CoverageConfig:
    base = {
        "enabled": True,
        "min_daily_bars": 200,
        "backfill_days": 400,
        "max_per_cycle": 8,
        "throttle_seconds": 0.0,
        "redis_ttl_seconds": 3600,
    }
    base.update(kw)
    return CoverageConfig(**base)


def test_enqueue_adds_new_codes(redis_client):
    added = enqueue_symbols(
        ["005930", "000660", "005930"], redis_client=redis_client, config=_cfg()
    )
    assert added == 2  # dedup
    assert redis_client.smembers(PENDING_KEY) == {"005930", "000660"}
    assert redis_client.ttl(PENDING_KEY) > 0


def test_enqueue_disabled_is_noop(redis_client):
    added = enqueue_symbols(
        ["005930"], redis_client=redis_client, config=_cfg(enabled=False)
    )
    assert added == 0
    assert not redis_client.exists(PENDING_KEY)


def test_ensure_skips_already_deep_and_clears_queue(monkeypatch, redis_client):
    redis_client.sadd(PENDING_KEY, "005930")
    store = _FakeStore({"005930": 300})  # already deep

    called = {"n": 0}

    async def fake_collect(**kwargs):
        called["n"] += 1
        raise AssertionError("must not backfill an already-deep symbol")

    monkeypatch.setattr(cov, "collect_stock_daily_parquet", fake_collect, raising=False)
    monkeypatch.setattr(
        "shared.collector.historical.parquet_backfill.collect_stock_daily_parquet",
        fake_collect,
    )

    summary = asyncio.run(
        ensure_daily_coverage(redis_client=redis_client, store=store, config=_cfg())
    )

    assert called["n"] == 0
    assert summary["already_deep"] == 1
    assert summary["deepened"] == 0
    # Idempotent: deep symbol is removed from the pending queue.
    assert redis_client.smembers(PENDING_KEY) == set()


def test_ensure_deepens_shallow_symbol(monkeypatch, redis_client):
    redis_client.sadd(PENDING_KEY, "080220")
    store = _FakeStore({"080220": 116})  # shallow

    class _Result:
        rows = 180

    async def fake_collect(*, codes, days, **kwargs):
        assert codes == ["080220"]
        assert days == 400
        store._depths["080220"] = 299  # simulate deepening
        return _Result()

    monkeypatch.setattr(
        "shared.collector.historical.parquet_backfill.collect_stock_daily_parquet",
        fake_collect,
    )

    summary = asyncio.run(
        ensure_daily_coverage(redis_client=redis_client, store=store, config=_cfg())
    )

    assert summary["deepened"] == 1
    assert summary["failed"] == 0
    assert redis_client.smembers(PENDING_KEY) == set()


def test_ensure_batches_and_requeues_overflow(monkeypatch, redis_client):
    codes = [f"{i:06d}" for i in range(5)]
    redis_client.sadd(PENDING_KEY, *codes)
    store = _FakeStore(dict.fromkeys(codes, 50))  # all shallow

    processed: list[str] = []

    async def fake_collect(*, codes, days, **kwargs):
        processed.extend(codes)
        for c in codes:
            store._depths[c] = 250
        return type("R", (), {"rows": 250})()

    monkeypatch.setattr(
        "shared.collector.historical.parquet_backfill.collect_stock_daily_parquet",
        fake_collect,
    )

    summary = asyncio.run(
        ensure_daily_coverage(
            redis_client=redis_client, store=store, config=_cfg(max_per_cycle=2)
        )
    )

    assert summary["deepened"] == 2
    assert len(processed) == 2  # bounded by max_per_cycle
    assert summary["requeued"] == 3
    # The 3 not-yet-processed shallow codes remain queued.
    assert len(redis_client.smembers(PENDING_KEY)) == 3


def test_ensure_one_failure_does_not_block_others(monkeypatch, redis_client):
    redis_client.sadd(PENDING_KEY, "AAA", "BBB")
    store = _FakeStore({"AAA": 50, "BBB": 50})

    async def fake_collect(*, codes, days, **kwargs):
        if codes == ["AAA"]:
            raise RuntimeError("transient KIS error")
        store._depths[codes[0]] = 250
        return type("R", (), {"rows": 250})()

    monkeypatch.setattr(
        "shared.collector.historical.parquet_backfill.collect_stock_daily_parquet",
        fake_collect,
    )

    summary = asyncio.run(
        ensure_daily_coverage(redis_client=redis_client, store=store, config=_cfg())
    )

    assert summary["deepened"] == 1  # BBB succeeded
    assert summary["failed"] == 1  # AAA failed
    # Failed (transient) symbol stays queued for retry; succeeded one is cleared.
    pending = redis_client.smembers(PENDING_KEY)
    assert "AAA" in pending
    assert "BBB" not in pending


def test_ensure_explicit_codes_skips_queue(monkeypatch, redis_client):
    store = _FakeStore({"005930": 50})

    async def fake_collect(*, codes, days, **kwargs):
        store._depths[codes[0]] = 250
        return type("R", (), {"rows": 250})()

    monkeypatch.setattr(
        "shared.collector.historical.parquet_backfill.collect_stock_daily_parquet",
        fake_collect,
    )

    summary = asyncio.run(
        ensure_daily_coverage(
            codes=["005930"], redis_client=redis_client, store=store, config=_cfg()
        )
    )
    assert summary["deepened"] == 1
    # Explicit-codes mode must not touch the Redis queue.
    assert not redis_client.exists(PENDING_KEY)


def test_config_env_override(monkeypatch):
    monkeypatch.setenv("STOCK_COVERAGE_MIN_DAILY_BARS", "150")
    monkeypatch.setenv("STOCK_COVERAGE_MAX_PER_CYCLE", "3")
    monkeypatch.setenv("STOCK_COVERAGE_ENABLED", "false")
    cfg = CoverageConfig.load()
    assert cfg.min_daily_bars == 150
    assert cfg.max_per_cycle == 3
    assert cfg.enabled is False
