"""StockStrategyDaemon: per-symbol context build + publish; universe refresh."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from services.stock_strategy.daemon import StockStrategyDaemon
from shared.models.signal import Signal


class _FakeEngine:
    def __init__(self, warm=("005930",)):
        self._warm = set(warm)

    def is_warm(self, symbol):
        return symbol in self._warm


class _FakeResolver:
    def collect_entry_indicators(self, _symbol):
        return {"rsi": 30.0, "atr": 100.0}


class _FakeFeed:
    def __init__(self):
        self.symbols = []
        self.started = False
        self.stopped = False

    def update_symbols(self, codes):
        self.symbols = list(codes)

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    async def get_current_price(self, _symbol):
        return {"code": _symbol, "close": 71000.0, "timestamp": 1.0}


class _FakeManager:
    def __init__(self, fire_for=("005930",)):
        self._fire = set(fire_for)

    async def check_entries(self, context):
        code = context.market_data.get("code")
        if code in self._fire:
            return [
                Signal(code=code, strategy="williams_r", price=71000.0, confidence=0.6)
            ]
        return []


class _FakeRedis:
    def __init__(self):
        self.added = []

    async def xadd(self, stream, fields, **_kw):
        self.added.append((stream, fields))

    async def expire(self, *_a, **_k):
        return True


def _daemon(**kw):
    defaults = {
        "redis": _FakeRedis(),
        "feed": _FakeFeed(),
        "engine": _FakeEngine(),
        "resolver": _FakeResolver(),
        "manager": _FakeManager(),
        "candidate_stream": "signal.candidate.stock.shadow",
        "candidate_maxlen": 10_000,
        "now_fn": lambda: datetime(2026, 6, 5, 0, 30, tzinfo=UTC),
    }
    defaults.update(kw)
    return StockStrategyDaemon(**defaults)


@pytest.mark.asyncio
async def test_evaluate_once_publishes_candidate_for_warm_firing_symbol():
    redis = _FakeRedis()
    d = _daemon(redis=redis)
    d._universe = ["005930", "000660"]  # 000660 not warm
    await d.evaluate_once()
    assert len(redis.added) == 1
    stream, fields = redis.added[0]
    assert stream == "signal.candidate.stock.shadow"
    assert fields["code"] == "005930" and "signal_id" in fields


@pytest.mark.asyncio
async def test_not_warm_symbol_is_skipped():
    redis = _FakeRedis()
    d = _daemon(redis=redis, engine=_FakeEngine(warm=()))  # nothing warm
    d._universe = ["005930"]
    await d.evaluate_once()
    assert redis.added == []


@pytest.mark.asyncio
async def test_per_symbol_failure_isolated():
    class _BoomManager:
        async def check_entries(self, context):
            if context.market_data.get("code") == "005930":
                raise RuntimeError("boom")
            return [
                Signal(code=context.market_data.get("code"), strategy="s", price=1.0)
            ]

    redis = _FakeRedis()
    d = _daemon(
        redis=redis,
        manager=_BoomManager(),
        engine=_FakeEngine(warm=("005930", "000660")),
    )
    d._universe = ["005930", "000660"]
    await d.evaluate_once()  # must not raise
    # 000660 still published despite 005930 raising
    assert any(f["code"] == "000660" for _s, f in redis.added)


def test_refresh_universe_updates_feed():
    feed = _FakeFeed()
    d = _daemon(feed=feed)
    import json

    d._apply_watchlist(json.dumps({"strategies": {"w": ["005930", "000660"]}}))
    assert set(feed.symbols) == {"005930", "000660"}
    assert set(d._universe) == {"005930", "000660"}


@pytest.mark.asyncio
async def test_run_start_stop_lifecycle():
    """run() calls feed.start(), runs the loops, exits promptly on stop(), calls feed.stop()."""
    import asyncio
    import json

    feed = _FakeFeed()
    d = _daemon(
        feed=feed,
        eval_interval_seconds=0.01,
        universe_refresh_seconds=0.01,
        watchlist_reader=lambda: json.dumps({"strategies": {"w": ["005930"]}}),
    )
    # empty universe so evaluate_once is a no-op (no manager calls needed)
    d._universe = []

    task = asyncio.create_task(d.run())
    await asyncio.sleep(0.05)  # let eval + refresh loops tick a couple times
    await d.stop()
    await asyncio.wait_for(
        task, timeout=1.0
    )  # must return promptly — proves interruptible sleeps

    assert feed.started is True, "run() must call feed.start()"
    assert feed.stopped is True, "run() finally block must call feed.stop()"
