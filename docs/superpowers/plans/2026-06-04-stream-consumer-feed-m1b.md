# StreamConsumerFeed (M1b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `StreamConsumerFeed` — a `MarketDataSource` backed by the Redis tick stream. It XREADs the ticks the M1a ingest daemon publishes, keeps an in-memory price cache, exposes `get_current_price` / `supports_instant_read` / `get_health_status`, and (when given an indicator engine) pushes each tick to it. This is the consumer the orchestrator will use in M1c instead of owning the KIS feed.

**Architecture:** `services/trading/stream_consumer_feed.py` — `StreamConsumerFeed` parses tick-stream entries (the inverse of `TickStreamPublisher._build_fields`) into the exact `get_current_price` dict shape the feeds return, caches them per symbol, and on each entry calls `indicator_engine.on_tick(symbol, price, ts)` (with the `set_volume_baseline` first-tick guard the orchestrator callback uses). A background asyncio task XREADs new entries. The class is a duck-typed drop-in for `MarketDataProvider`'s `data_source` (protocol requires only async `get_current_price`; `supports_instant_read` + `get_health_status` are optional hooks the provider/failover loop use via `getattr`/`hasattr`).

**Tech Stack:** Python 3.11 asyncio, `redis.asyncio` (XREAD), pytest + `fakeredis`. No new deps.

**Spec:** `docs/superpowers/specs/2026-06-04-stream-pipeline-decoupling-design.md`. Increment **M1b** (the consumer feed). The orchestrator per-asset flag cutover is **M1c**.

**Scope note — futures orderbook (affects M1c, not M1b):** The tick stream carries NO orderbook fields (`bid_price_1`/`ask_price_1`/`spread`); `TickStreamPublisher._build_fields` never writes them. The futures slippage controller (`config/execution.yaml::futures_slippage_control.enabled: true`) BLOCKS every futures entry when no orderbook is present. Therefore M1c will cut over **stock first** (stock reads no orderbook keys); futures stays on the in-proc feed until an orderbook transport exists (a later increment). `StreamConsumerFeed` is asset-agnostic — it surfaces whatever fields are in the stream — so this scoping decision lives in M1c, not here.

---

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `services/trading/stream_consumer_feed.py` | Create | `StreamConsumerFeed` + `_parse_entry_fields` |
| `tests/unit/trading/test_stream_consumer_feed.py` | Create | parse / cache / get_current_price / health / indicator-push / XREAD round-trip |

Run tests via the worktree using the main venv: `cd /tmp/m1b && /home/deploy/project/kis_unified_sts/.venv/bin/python -m pytest <path> -q`. `tests/unit/trading/` already exists (no new `__init__.py`).

---

## Task 1: `StreamConsumerFeed` core (parse + cache + protocol surface + indicator push)

The synchronous core — everything except the background XREAD loop (Task 2). Fully unit-testable via the `_apply_entry` seam (no Redis).

**Files:** Create `services/trading/stream_consumer_feed.py` (without `start`/`stop`/`_read_loop` — those are Task 2), `tests/unit/trading/test_stream_consumer_feed.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/trading/test_stream_consumer_feed.py` with EXACTLY this content:

```python
"""Tests for StreamConsumerFeed (Redis tick stream → price cache + indicator push)."""
from __future__ import annotations

from datetime import datetime

import pytest

from services.trading.stream_consumer_feed import (
    StreamConsumerFeed,
    _parse_entry_fields,
)


def _entry(**kw) -> dict[bytes, bytes]:
    return {k.encode(): str(v).encode() for k, v in kw.items()}


class FakeIndicatorEngine:
    def __init__(self):
        self._last_cumulative_volume: dict[str, float] = {}
        self.baseline_calls: list[tuple[str, float]] = []
        self.on_tick_calls: list[tuple[str, dict, object]] = []

    def set_volume_baseline(self, symbol: str, cumulative_volume: float) -> None:
        self.baseline_calls.append((symbol, cumulative_volume))
        self._last_cumulative_volume[symbol] = cumulative_volume

    def on_tick(self, symbol, price_data, timestamp=None):
        self.on_tick_calls.append((symbol, price_data, timestamp))


# -- parse helper --------------------------------------------------------- #

def test_parse_entry_extracts_price_shape():
    sym, price = _parse_entry_fields(
        _entry(symbol="005930", close="100.5", open="99", high="101", low="98",
               volume="1234", timestamp="1700000000.0")
    )
    assert sym == "005930"
    assert price["code"] == "005930"
    assert price["close"] == 100.5
    assert price["open"] == 99.0 and price["high"] == 101.0 and price["low"] == 98.0
    assert price["volume"] == 1234
    assert price["timestamp"] == 1700000000.0


def test_parse_entry_falls_back_to_price_and_current_price_keys():
    _, price = _parse_entry_fields(_entry(code="A01", current_price="50.0"))
    assert price["close"] == 50.0 and price["code"] == "A01"


def test_parse_entry_returns_none_on_missing_symbol_or_price():
    assert _parse_entry_fields(_entry(close="1.0")) is None  # no symbol/code
    assert _parse_entry_fields(_entry(symbol="X")) is None    # no price


def test_parse_entry_volume_is_cumulative_bool():
    _, price = _parse_entry_fields(_entry(symbol="X", close="1", volume_is_cumulative="true"))
    assert price["volume_is_cumulative"] is True


# -- cache + protocol surface -------------------------------------------- #

def _feed(**kw):
    return StreamConsumerFeed(redis=object(), stream="market:ticks", **kw)


@pytest.mark.asyncio
async def test_apply_entry_updates_cache_and_get_current_price():
    feed = _feed()
    feed._apply_entry(_entry(symbol="005930", close="100.0", volume="10"))
    got = await feed.get_current_price("005930")
    assert got["close"] == 100.0 and got["code"] == "005930"
    # returns a copy (mutating result must not corrupt the cache)
    got["close"] = -1
    assert (await feed.get_current_price("005930"))["close"] == 100.0


@pytest.mark.asyncio
async def test_get_current_price_missing_symbol_returns_empty():
    assert await _feed().get_current_price("nope") == {}


def test_supports_instant_read_is_true():
    assert _feed().supports_instant_read is True


def test_apply_entry_pushes_to_indicator_engine_with_baseline_guard():
    eng = FakeIndicatorEngine()
    feed = _feed(indicator_engine=eng)
    feed._apply_entry(_entry(symbol="005930", close="100.0", volume="500"))
    # first tick → baseline initialized, then on_tick
    assert eng.baseline_calls == [("005930", 500.0)]
    assert len(eng.on_tick_calls) == 1
    sym, price, ts = eng.on_tick_calls[0]
    assert sym == "005930" and price["close"] == 100.0
    assert isinstance(ts, datetime)
    # second tick → no second baseline (guard), another on_tick
    feed._apply_entry(_entry(symbol="005930", close="101.0", volume="600"))
    assert eng.baseline_calls == [("005930", 500.0)]
    assert len(eng.on_tick_calls) == 2


def test_update_symbols_sets_symbol_count():
    feed = _feed()
    feed.update_symbols(["A", "B", "C"])
    assert feed.get_health_status()["symbol_count"] == 3


# -- health -------------------------------------------------------------- #

def test_health_status_has_failover_keys_and_is_stale_before_ticks():
    feed = _feed(stale_threshold_seconds=30.0)
    h = feed.get_health_status()
    for key in ("running", "connected", "staleness_seconds", "fresh_symbol_count", "symbol_count"):
        assert key in h
    assert h["staleness_seconds"] is None  # no tick yet
    assert feed.is_healthy() is False       # not running


def test_is_healthy_true_when_running_and_fresh():
    feed = _feed(stale_threshold_seconds=30.0)
    feed._running = True
    feed._apply_entry(_entry(symbol="X", close="1.0"))
    assert feed.is_healthy() is True
    h = feed.get_health_status()
    assert h["fresh_symbol_count"] == 1
    assert h["staleness_seconds"] is not None and h["staleness_seconds"] < 30.0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /tmp/m1b && /home/deploy/project/kis_unified_sts/.venv/bin/python -m pytest tests/unit/trading/test_stream_consumer_feed.py -q`
Expected: import error — module missing.

- [ ] **Step 3: Write the core class (no read loop yet)**

Create `services/trading/stream_consumer_feed.py` with EXACTLY this content:

```python
"""StreamConsumerFeed — a MarketDataSource backed by the Redis tick stream.

Reads the ticks the market-ingest daemon publishes to ``market:ticks`` /
``raw_data``, keeps an in-memory price cache, and (when given an indicator
engine) pushes each tick to it — so the orchestrator can consume the tick
stream instead of owning the KIS WebSocket feed (M1c). Drop-in for
``MarketDataProvider``'s ``data_source``: implements ``get_current_price`` plus
the optional ``supports_instant_read`` / ``get_health_status`` hooks.
"""
from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


def _decode(value: Any) -> str | None:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return None if value is None else str(value)


def _parse_entry_fields(
    fields: dict[Any, Any],
) -> tuple[str, dict[str, Any]] | None:
    """Parse a tick-stream entry into ``(symbol, price_dict)``.

    Inverse of ``TickStreamPublisher._build_fields``: rebuilds the dict shape
    the KIS feeds' ``get_current_price`` returns (``code``/``close``/``open``/
    ``high``/``low``/``volume``/``timestamp`` + optional ``volume_is_cumulative``).
    Returns ``None`` when the entry has no usable symbol or price.
    """
    g: dict[str, str | None] = {}
    for raw_key, raw_value in fields.items():
        key = raw_key.decode() if isinstance(raw_key, bytes) else str(raw_key)
        g[key] = _decode(raw_value)

    symbol = g.get("symbol") or g.get("code")
    if not symbol:
        return None

    close_raw = g.get("close") or g.get("current_price") or g.get("price")
    if close_raw is None:
        return None
    try:
        close = float(close_raw)
    except (TypeError, ValueError):
        return None

    price: dict[str, Any] = {"code": symbol, "close": close}
    for key in ("open", "high", "low"):
        if g.get(key) is not None:
            try:
                price[key] = float(g[key])
            except (TypeError, ValueError):
                pass
    if g.get("volume") is not None:
        try:
            price["volume"] = int(float(g["volume"]))
        except (TypeError, ValueError):
            pass
    if g.get("volume_is_cumulative") is not None:
        price["volume_is_cumulative"] = str(g["volume_is_cumulative"]).lower() == "true"
    try:
        price["timestamp"] = float(g["timestamp"]) if g.get("timestamp") else time.time()
    except (TypeError, ValueError):
        price["timestamp"] = time.time()
    return symbol, price


class StreamConsumerFeed:
    """A ``MarketDataSource`` that mirrors the Redis tick stream in memory."""

    def __init__(
        self,
        *,
        redis: Any,
        stream: str,
        indicator_engine: Any | None = None,
        stale_threshold_seconds: float = 30.0,
        xread_block_ms: int = 1000,
        xread_count: int = 200,
    ) -> None:
        self.redis = redis
        self.stream = stream
        self.indicator_engine = indicator_engine
        self._stale_threshold = stale_threshold_seconds
        self.xread_block_ms = xread_block_ms
        self.xread_count = xread_count
        self._prices: dict[str, dict[str, Any]] = {}
        self._symbol_tick_ts: dict[str, float] = {}
        self._subscribed: set[str] = set()
        self._last_tick_ts: float | None = None
        self._last_id: str = "$"  # read only entries added after start()
        self._running = False

    # -- MarketDataSource surface ---------------------------------------- #

    @property
    def supports_instant_read(self) -> bool:
        return True

    async def get_current_price(self, symbol: str) -> dict[str, Any]:
        return dict(self._prices.get(symbol, {}))

    def update_symbols(self, symbols: list[str]) -> None:
        self._subscribed = set(symbols)

    # -- cache update + indicator push ----------------------------------- #

    def _apply_entry(self, fields: dict[Any, Any]) -> None:
        parsed = _parse_entry_fields(fields)
        if parsed is None:
            return
        symbol, price = parsed
        self._prices[symbol] = price
        now = time.time()
        self._symbol_tick_ts[symbol] = now
        self._last_tick_ts = now
        if self.indicator_engine is not None:
            self._push_indicator(symbol, price)

    def _push_indicator(self, symbol: str, price: dict[str, Any]) -> None:
        eng = self.indicator_engine
        try:
            raw_vol = float(price.get("volume", 0) or 0)
            seen = getattr(eng, "_last_cumulative_volume", None)
            if isinstance(seen, dict) and symbol not in seen:
                eng.set_volume_baseline(symbol, raw_vol)
            ts = datetime.fromtimestamp(price.get("timestamp", time.time()), UTC)
            eng.on_tick(symbol, price, ts)
        except Exception:
            logger.exception("indicator on_tick failed symbol=%s", symbol)

    # -- health (duck-typed hooks for the failover loop) ----------------- #

    def get_staleness_seconds(self) -> float | None:
        if self._last_tick_ts is None:
            return None
        return max(0.0, time.time() - self._last_tick_ts)

    def is_healthy(self) -> bool:
        if not self._running:
            return False
        staleness = self.get_staleness_seconds()
        return staleness is not None and staleness < self._stale_threshold

    def get_health_status(self) -> dict[str, Any]:
        now = time.time()
        fresh = sum(
            1 for ts in self._symbol_tick_ts.values() if now - ts < self._stale_threshold
        )
        return {
            "running": self._running,
            "connected": self._running,
            "staleness_seconds": self.get_staleness_seconds(),
            "symbol_count": len(self._subscribed) or len(self._symbol_tick_ts),
            "fresh_symbol_count": fresh,
            "stale_symbol_count": max(0, len(self._symbol_tick_ts) - fresh),
            "last_tick_ts": self._last_tick_ts,
            "is_healthy": self.is_healthy(),
        }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /tmp/m1b && /home/deploy/project/kis_unified_sts/.venv/bin/python -m pytest tests/unit/trading/test_stream_consumer_feed.py -q`
Expected: 12 passed.

- [ ] **Step 5: Lint**

Run: `cd /tmp/m1b && /home/deploy/project/kis_unified_sts/.venv/bin/ruff check services/trading/stream_consumer_feed.py tests/unit/trading/test_stream_consumer_feed.py && /home/deploy/project/kis_unified_sts/.venv/bin/black --check services/trading/stream_consumer_feed.py tests/unit/trading/test_stream_consumer_feed.py`
Expected: clean. (`FakeIndicatorEngine.on_tick`'s unused `timestamp` → add `  # noqa: ARG002` if ruff flags it. Run `black ...` to auto-format if needed.)

- [ ] **Step 6: Commit**

```bash
cd /tmp/m1b
git add services/trading/stream_consumer_feed.py tests/unit/trading/test_stream_consumer_feed.py
git commit -m "feat: add StreamConsumerFeed core (tick-stream cache + indicator push + health)"
```

---

## Task 2: Background XREAD reader (`start`/`stop`/`_read_loop`)

Adds the async background loop that XREADs new tick-stream entries and applies them via `_apply_entry`. Tested with `fakeredis` for a real XADD→XREAD round-trip.

**Files:** Modify `services/trading/stream_consumer_feed.py` (add the loop methods); Modify `tests/unit/trading/test_stream_consumer_feed.py` (append a round-trip test).

- [ ] **Step 1: Append the failing round-trip test**

Append EXACTLY this to the END of `tests/unit/trading/test_stream_consumer_feed.py`:

```python
@pytest.mark.asyncio
async def test_read_loop_consumes_xadded_ticks():
    import asyncio

    import fakeredis.aioredis

    redis = fakeredis.aioredis.FakeRedis()
    feed = StreamConsumerFeed(redis=redis, stream="market:ticks", xread_block_ms=20)
    await feed.start()
    try:
        await redis.xadd("market:ticks", {"symbol": "005930", "close": "123.0"})
        # poll until the reader applies it (or time out)
        for _ in range(50):
            if await feed.get_current_price("005930"):
                break
            await asyncio.sleep(0.02)
        got = await feed.get_current_price("005930")
        assert got["close"] == 123.0
        assert feed.is_healthy() is True
    finally:
        await feed.stop()
    assert feed._running is False
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd /tmp/m1b && /home/deploy/project/kis_unified_sts/.venv/bin/python -m pytest tests/unit/trading/test_stream_consumer_feed.py::test_read_loop_consumes_xadded_ticks -q`
Expected: FAIL — `StreamConsumerFeed` has no `start`/`stop`.

- [ ] **Step 3: Add the reader loop**

Add `import asyncio` to the imports at the top of `services/trading/stream_consumer_feed.py` (alongside `logging`/`time`), and add the `_task` field + the three methods. First, in `__init__`, add this line after `self._running = False`:

```python
        self._task: asyncio.Task[None] | None = None
```

Then append these three methods to the `StreamConsumerFeed` class (after `get_health_status`):

```python
    # -- background reader ----------------------------------------------- #

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._read_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _read_loop(self) -> None:
        while self._running:
            try:
                resp = await self.redis.xread(
                    {self.stream: self._last_id},
                    count=self.xread_count,
                    block=self.xread_block_ms,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("xread error; sleeping 0.5s")
                await asyncio.sleep(0.5)
                continue
            if not resp:
                continue
            for _stream, entries in resp:
                for entry_id, fields in entries:
                    self._last_id = (
                        entry_id.decode() if isinstance(entry_id, bytes) else str(entry_id)
                    )
                    self._apply_entry(fields)
```

- [ ] **Step 4: Run the whole test file**

Run: `cd /tmp/m1b && /home/deploy/project/kis_unified_sts/.venv/bin/python -m pytest tests/unit/trading/test_stream_consumer_feed.py -q`
Expected: 13 passed. + lint: `/home/deploy/project/kis_unified_sts/.venv/bin/ruff check services/trading/stream_consumer_feed.py && /home/deploy/project/kis_unified_sts/.venv/bin/black --check services/trading/stream_consumer_feed.py` → clean.

- [ ] **Step 5: Commit**

```bash
cd /tmp/m1b
git add services/trading/stream_consumer_feed.py tests/unit/trading/test_stream_consumer_feed.py
git commit -m "feat: StreamConsumerFeed background XREAD reader (start/stop/_read_loop)"
```

---

## Self-Review (completed by plan author)

- **Spec coverage:** Implements the M1 consumer feed (spec §4.1 / decision A: per-tick indicator push). `get_current_price` mirrors the KIS feeds' dict shape; `supports_instant_read=True`; `get_health_status` returns the exact keys the data_provider failover loop reads (`running`/`connected`/`staleness_seconds`/`fresh_symbol_count`/`symbol_count`). The orchestrator cutover (M1c) and the futures-orderbook transport are explicitly deferred — not gaps.
- **Placeholder scan:** No TBD/TODO. The class, parse helper, both test groups, and the reader loop are complete inline.
- **Type/name consistency:** `_parse_entry_fields(fields) -> (symbol, dict) | None`; `_apply_entry(fields)` (sync, the test seam); `get_current_price(symbol) -> dict` (async, the protocol method); `on_tick(symbol, price, ts)` matches `StreamingIndicatorEngine.on_tick(symbol, price_data, timestamp)` and the `set_volume_baseline(symbol, cumulative_volume)` first-tick guard mirrors the orchestrator callback. `_last_id="$"` reads only post-start entries; `_read_loop` advances it per entry.
- **Verbatim fidelity:** field parse-back inverts `_build_fields` (close/current_price/price → close; code; open/high/low; volume; volume_is_cumulative; timestamp). Health-key set matches `_check_data_source_health`'s reads. The duck-typed surface (only `get_current_price` required; `supports_instant_read`/`get_health_status` optional) matches the `MarketDataSource` protocol.
- **Test independence:** Task-1 tests drive `_apply_entry` directly + the protocol getters (no Redis). Task-2 uses `fakeredis.aioredis` for a real XADD→XREAD round-trip. All hermetic.
