"""Data-freshness writer — round-trip against the dashboard health parser.

Verifies the S2 fix. ``DataFreshnessTracker`` writes
``trading:{asset}:data_freshness`` in the exact schema that
``services/dashboard/routes/health.py::get_data_freshness`` parses back
(``symbol_count`` / ``fresh_count`` / ``last_tick_s``), with a TTL, and using a
naive (KST) ``checked_at``.
"""

from __future__ import annotations

import json
from datetime import datetime

import fakeredis
import pytest

from shared.streaming.data_freshness import DataFreshnessTracker


@pytest.fixture
def fake_redis():
    return fakeredis.FakeStrictRedis(decode_responses=True)


def test_build_snapshot_counts_fresh_and_last_tick():
    tracker = DataFreshnessTracker("stock", window_seconds=60.0)
    now = 1000.0
    tracker.record_tick("A", now=now - 5)  # fresh (<=60s)
    tracker.record_tick("B", now=now - 120)  # stale (>60s)
    snap = tracker.build_snapshot(["A", "B", "C"], now=now)
    assert snap["symbol_count"] == 3
    assert snap["fresh_count"] == 1
    assert snap["last_tick_s"] == 5  # age of the freshest tick (A @ now-5)
    assert snap["asset_class"] == "stock"


def test_rotated_out_symbols_are_pruned():
    """Symbols that leave the universe are dropped from _last_tick; output unchanged.

    Guards the unbounded-growth risk on rotating feeds (screener / intraday
    dynamic mode churn through many codes a day).
    """
    tracker = DataFreshnessTracker("stock", window_seconds=60.0)
    now = 1000.0
    tracker.record_tick("A", now=now - 5)
    tracker.record_tick("B", now=now - 5)
    tracker.record_tick("C", now=now - 5)

    # Universe rotates so only A remains subscribed.
    snap = tracker.build_snapshot(["A"], now=now)
    assert snap["symbol_count"] == 1
    assert snap["fresh_count"] == 1
    assert snap["last_tick_s"] == 5

    # B and C were pruned from the in-memory map (bounded memory).
    assert set(tracker._last_tick.keys()) == {"A"}

    # A subsequent snapshot for the same universe is unchanged (no corruption).
    snap2 = tracker.build_snapshot(["A"], now=now)
    assert snap2["symbol_count"] == snap["symbol_count"]
    assert snap2["fresh_count"] == snap["fresh_count"]
    assert snap2["last_tick_s"] == snap["last_tick_s"]


def test_no_ticks_reports_no_data_sentinel():
    tracker = DataFreshnessTracker("stock")
    snap = tracker.build_snapshot(["A", "B"], now=1000.0)
    assert snap["symbol_count"] == 2
    assert snap["fresh_count"] == 0
    assert snap["last_tick_s"] == -1  # matches health.py's "no data" sentinel


def test_checked_at_is_naive_kst():
    """checked_at must be naive (container TZ=Asia/Seoul), never tz-aware UTC."""
    snap = DataFreshnessTracker("stock").build_snapshot([], now=1000.0)
    assert datetime.fromisoformat(snap["checked_at"]).tzinfo is None


def test_write_snapshot_sets_key_with_ttl(fake_redis):
    tracker = DataFreshnessTracker("stock", ttl_seconds=1234)
    tracker.record_tick("A", now=1000.0)
    tracker.write_snapshot(["A"], now=1002.0, redis_client=fake_redis)

    key = "trading:stock:data_freshness"
    raw = fake_redis.get(key)
    assert raw is not None
    assert json.loads(raw)["fresh_count"] == 1
    ttl = fake_redis.ttl(key)
    assert 0 < ttl <= 1234  # TTL is required (CLAUDE.md)


def test_unsupported_asset_is_not_written(fake_redis):
    tracker = DataFreshnessTracker("crypto")
    assert tracker.write_snapshot(["A"], now=1000.0, redis_client=fake_redis) is None
    assert fake_redis.get("trading:crypto:data_freshness") is None


def test_write_snapshot_swallows_redis_error():
    class _BoomRedis:
        def set(self, *_a, **_k):
            raise RuntimeError("redis down")

    tracker = DataFreshnessTracker("stock")
    tracker.record_tick("A", now=1000.0)
    # Best-effort: must return None rather than raise.
    assert tracker.write_snapshot(["A"], now=1001.0, redis_client=_BoomRedis()) is None


@pytest.mark.asyncio
async def test_roundtrip_through_health_endpoint(fake_redis, monkeypatch):
    """The snapshot the tracker writes parses cleanly through get_data_freshness."""
    from services.dashboard.routes import health

    tracker = DataFreshnessTracker("stock", window_seconds=60.0)
    now = 5000.0
    tracker.record_tick("A", now=now - 3)  # fresh
    tracker.record_tick("B", now=now - 10)  # fresh
    tracker.record_tick("C", now=now - 200)  # stale
    tracker.write_snapshot(["A", "B", "C"], now=now, redis_client=fake_redis)

    monkeypatch.setattr(health, "_get_redis_client", lambda: fake_redis)
    result = await health.get_data_freshness(asset_class="stock")

    sources = result["sources"]
    assert len(sources) == 1
    src = sources[0]
    assert src["asset_class"] == "stock"
    assert src["symbol_count"] == 3
    assert src["fresh_count"] == 2
    assert src["last_tick_s"] == 3
    assert src["fresh_ratio"] == pytest.approx(2 / 3, abs=1e-4)
