# Orchestrator Stock Data-Source Cutover (M1c) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Behind a default-off per-asset flag (`STOCK_MARKET_DATA_SOURCE=stream`), make the trading orchestrator consume the Redis tick stream via `StreamConsumerFeed` instead of owning the KIS stock WebSocket feed — preserving the full per-tick processing (indicator + paper-broker mark-to-market) and the REST failover safety net.

**Architecture:** `StreamConsumerFeed` gains a `set_tick_callback` (mirroring the `KIS*PriceFeed` contract); the orchestrator wires its *existing* `_on_stock_tick` closure to whichever stock feed is active. On the stream path the orchestrator builds no KIS stock feed (no WS connection), skips constructing the tick-stream publisher (the M1a ingest daemon owns publishing, so the reused callback's publish no-ops), and starts/stops the stream feed via two small helpers. The flag is read in `_init_price_feeds`; stock-only (futures stays `websocket`). Default off → merging is operationally inert.

**Tech Stack:** Python 3.11, `redis.asyncio` (`aioredis.from_url`, DB 1), pytest (`pytest.mark.asyncio`), the existing `services/trading/orchestrator.py` + `services/trading/stream_consumer_feed.py`.

**Spec:** `docs/superpowers/specs/2026-06-04-orchestrator-stream-cutover-m1c-design.md`

**Environment:** Work in the existing worktree `/tmp/m1c` on branch `feat/orchestrator-stream-cutover-m1c`. The worktree has no `.venv` of its own (it's gitignored). Run tests with the repo venv while shadowing the editable install with the worktree code:
```bash
cd /tmp/m1c
PYTHONPATH=/tmp/m1c /home/deploy/project/kis_unified_sts/.venv/bin/pytest <args>
```
(Per-task `Run:` lines below abbreviate this as `pytest <args>` — always prefix `PYTHONPATH=/tmp/m1c /home/deploy/project/kis_unified_sts/.venv/bin/`.) Never touch the operator's main checkout or shared services.

**Key facts the engineer needs (verbatim from the current code):**
- `_on_stock_tick` (orchestrator.py:1789–1821) does 3 things per tick: indicator `on_tick` (with `set_volume_baseline` guard), `paper_broker.record_price_observation`, and `tick_stream_publisher.publish` (guarded by `if self._tick_stream_publisher:`).
- Init order: `_init_price_feeds` (1143) → `_init_data_provider` (1146) → `_init_tick_stream_publisher` (1149) → `_init_indicator_engine` (1155).
- `StreamConsumerFeed.__init__(*, redis, stream, indicator_engine=None, stale_threshold_seconds=30.0, xread_block_ms=1000, xread_count=200)`; `_apply_entry` caches the price then pushes to `indicator_engine` if set.
- Async-redis idiom used by every stream daemon: `import redis.asyncio as aioredis; aioredis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/1"))`.
- Orchestrator is directly constructible in tests: `TradingOrchestrator(TradingConfig.stock())`.

---

## Task 1: `StreamConsumerFeed.set_tick_callback`

Give the feed a tick callback (same contract as `KIS*PriceFeed.set_tick_callback`). When a callback is set, `_apply_entry` invokes it `(symbol, price_dict, datetime)` **instead of** the built-in indicator push (the callback owns all per-tick processing). No-callback behavior is unchanged.

**Files:**
- Modify: `services/trading/stream_consumer_feed.py`
- Test: `tests/unit/trading/test_stream_consumer_feed.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/trading/test_stream_consumer_feed.py` (the `_feed`, `_entry`, `FakeIndicatorEngine` helpers already exist at the top of the file):

```python
def test_set_tick_callback_invoked_instead_of_indicator_push():
    eng = FakeIndicatorEngine()
    feed = _feed(indicator_engine=eng)
    seen: list[tuple] = []
    feed.set_tick_callback(lambda symbol, price, ts: seen.append((symbol, price["close"], ts)))
    feed._apply_entry(_entry(symbol="005930", close="100.0", volume="500"))
    assert len(seen) == 1
    symbol, close, ts = seen[0]
    assert symbol == "005930" and close == 100.0
    assert isinstance(ts, datetime)
    # callback present => indicator engine is NOT pushed
    assert eng.on_tick_calls == []
    assert eng.baseline_calls == []
    # price cache is still updated
    assert feed._prices["005930"]["close"] == 100.0


def test_set_tick_callback_via_constructor():
    seen: list[str] = []
    feed = _feed(tick_callback=lambda s, p, ts: seen.append(s))
    feed._apply_entry(_entry(symbol="000660", close="50.0"))
    assert seen == ["000660"]


def test_no_callback_still_pushes_indicator():
    eng = FakeIndicatorEngine()
    feed = _feed(indicator_engine=eng)
    feed._apply_entry(_entry(symbol="005930", close="100.0", volume="500"))
    assert len(eng.on_tick_calls) == 1  # unchanged M1b behavior


def test_tick_callback_exception_is_swallowed():
    feed = _feed()
    def boom(symbol, price, ts):
        raise RuntimeError("callback blew up")
    feed.set_tick_callback(boom)
    # must not propagate out of _apply_entry
    feed._apply_entry(_entry(symbol="005930", close="100.0"))
    assert feed._prices["005930"]["close"] == 100.0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/unit/trading/test_stream_consumer_feed.py -k "callback" -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'tick_callback'` and `AttributeError: 'StreamConsumerFeed' object has no attribute 'set_tick_callback'`.

- [ ] **Step 3: Add the `Callable` import**

In `services/trading/stream_consumer_feed.py`, change the typing import line:

```python
from typing import Any
```
to:
```python
from collections.abc import Callable
from typing import Any
```

- [ ] **Step 4: Add the `tick_callback` constructor param + attribute**

In `StreamConsumerFeed.__init__`, change the signature and body. Replace:

```python
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
```
with:
```python
    def __init__(
        self,
        *,
        redis: Any,
        stream: str,
        indicator_engine: Any | None = None,
        tick_callback: Callable[[str, dict[str, Any], datetime], None] | None = None,
        stale_threshold_seconds: float = 30.0,
        xread_block_ms: int = 1000,
        xread_count: int = 200,
    ) -> None:
        self.redis = redis
        self.stream = stream
        self.indicator_engine = indicator_engine
        self._tick_callback = tick_callback
```

- [ ] **Step 5: Add the `set_tick_callback` method**

Insert this method immediately after `update_symbols` (right before `def _apply_entry`):

```python
    def set_tick_callback(
        self, callback: Callable[[str, dict[str, Any], datetime], None] | None
    ) -> None:
        """Register a per-tick callback (mirrors ``KIS*PriceFeed.set_tick_callback``).

        When set, each tick invokes ``callback(symbol, price_dict, ts)`` and the
        built-in indicator push is skipped — the callback owns per-tick processing.
        """
        self._tick_callback = callback
```

- [ ] **Step 6: Route `_apply_entry` through the callback when present**

Replace the tail of `_apply_entry`:

```python
        symbol, price = parsed
        self._prices[symbol] = price
        now = time.time()
        self._symbol_tick_ts[symbol] = now
        self._last_tick_ts = now
        if self.indicator_engine is not None:
            self._push_indicator(symbol, price)
```
with:
```python
        symbol, price = parsed
        self._prices[symbol] = price
        now = time.time()
        self._symbol_tick_ts[symbol] = now
        self._last_tick_ts = now
        if self._tick_callback is not None:
            ts = datetime.fromtimestamp(price.get("timestamp", time.time()), UTC)
            try:
                self._tick_callback(symbol, price, ts)
            except Exception:
                logger.exception("tick_callback failed symbol=%s", symbol)
        elif self.indicator_engine is not None:
            self._push_indicator(symbol, price)
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `pytest tests/unit/trading/test_stream_consumer_feed.py -v`
Expected: PASS (all new + all existing M1b tests).

- [ ] **Step 8: Commit**

```bash
git add services/trading/stream_consumer_feed.py tests/unit/trading/test_stream_consumer_feed.py
git commit -m "feat(m1c): StreamConsumerFeed.set_tick_callback (reuse orchestrator per-tick processing)"
```

---

## Task 2: `_init_price_feeds` stream branch + flag + attrs

Read `STOCK_MARKET_DATA_SOURCE`; on `stream` (stock only) build a `StreamConsumerFeed` backed by an async redis client and return it as the data source, building no KIS stock feed. Declare the two new attributes in `__init__` so every later reader is safe regardless of init order.

**Files:**
- Modify: `services/trading/orchestrator.py` (`__init__` ~887–906, `_init_price_feeds` 1326–1358, new helper `_load_stream_staleness_threshold`)
- Test: `tests/unit/trading/test_orchestrator_stream_cutover.py` (new file)

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/trading/test_orchestrator_stream_cutover.py`:

```python
"""M1c: STOCK_MARKET_DATA_SOURCE flag routing in the orchestrator."""

from __future__ import annotations

import pytest

from services.trading.orchestrator import TradingConfig, TradingOrchestrator
from services.trading.stream_consumer_feed import StreamConsumerFeed


def test_init_price_feeds_stream_branch_builds_stream_consumer_feed(monkeypatch):
    monkeypatch.setenv("STOCK_MARKET_DATA_SOURCE", "stream")
    orch = TradingOrchestrator(TradingConfig.stock())
    orch._kis_client = object()  # truthy → bypass the early return
    data_source = orch._init_price_feeds(object())  # truthy kis_config
    assert isinstance(data_source, StreamConsumerFeed)
    assert orch._stream_consumer_feed is data_source
    assert orch._stock_price_feed is None  # no KIS WebSocket feed
    assert orch._stream_redis is not None


def test_init_price_feeds_default_is_websocket(monkeypatch):
    monkeypatch.delenv("STOCK_MARKET_DATA_SOURCE", raising=False)
    monkeypatch.setattr(
        "shared.kis.stock_feed.KISStockPriceFeed", lambda config: object()
    )
    orch = TradingOrchestrator(TradingConfig.stock())
    orch._kis_client = object()
    data_source = orch._init_price_feeds(object())
    assert orch._stream_consumer_feed is None
    assert orch._stock_price_feed is data_source  # KIS feed path taken


def test_init_price_feeds_futures_ignores_stock_flag(monkeypatch):
    monkeypatch.setenv("STOCK_MARKET_DATA_SOURCE", "stream")
    monkeypatch.setattr(
        "shared.kis.futures_feed.KISFuturesPriceFeed", lambda config: object()
    )
    orch = TradingOrchestrator(TradingConfig.futures())
    orch._kis_client = object()
    data_source = orch._init_price_feeds(object())
    assert orch._stream_consumer_feed is None  # flag is stock-only
    assert orch._futures_price_feed is data_source


def test_stream_attrs_declared_after_construction():
    orch = TradingOrchestrator(TradingConfig.stock())
    assert orch._stream_consumer_feed is None
    assert orch._stream_redis is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/unit/trading/test_orchestrator_stream_cutover.py -v`
Expected: FAIL — `AttributeError: 'TradingOrchestrator' object has no attribute '_stream_consumer_feed'`.

- [ ] **Step 3: Declare the new attributes in `__init__`**

In `services/trading/orchestrator.py`, find the feed declarations in `__init__` (line 894):

```python
        self._futures_price_feed: Any | None = None
```
Insert immediately after it:
```python
        self._stream_consumer_feed: Any | None = None
        self._stream_redis: Any | None = None
```

- [ ] **Step 4: Add the staleness-threshold helper**

Insert this method immediately before `def _init_price_feeds` (line 1326):

```python
    def _load_stream_staleness_threshold(self) -> float:
        """Staleness threshold for the stream feed — mirror the failover config."""
        try:
            failover_cfg = ConfigLoader.load("streaming.yaml").get("failover", {})
            return float(failover_cfg.get("staleness_threshold_seconds", 30.0))
        except (
            InvalidConfigError,
            MissingConfigError,
            OSError,
            yaml.YAMLError,
            KeyError,
            TypeError,
            ValueError,
        ):
            return 30.0
```

- [ ] **Step 5: Add the attr resets + stream branch in `_init_price_feeds`**

Replace the head of `_init_price_feeds`:

```python
    def _init_price_feeds(self, kis_config) -> Any | None:
        """Initialize WebSocket Price Feeds"""
        self._stock_price_feed = None
        self._futures_price_feed = None
        data_source = None

        if not self._kis_client or not kis_config:
            return None

        if self.config.asset_class == "stock":
            try:
                from shared.kis.stock_feed import KISStockPriceFeed

                self._stock_price_feed = KISStockPriceFeed(
                    config=kis_config,
                )
                data_source = self._stock_price_feed
                logger.info("Stock WebSocket price feed initialized")
            except (NetworkError, WebSocketDisconnectError, ConfigurationError) as e:
                logger.warning(f"Stock WebSocket feed init failed: {e}")
        elif self.config.asset_class == "futures":
```
with:
```python
    def _init_price_feeds(self, kis_config) -> Any | None:
        """Initialize WebSocket Price Feeds"""
        self._stock_price_feed = None
        self._futures_price_feed = None
        self._stream_consumer_feed = None
        self._stream_redis = None
        data_source = None

        if not self._kis_client or not kis_config:
            return None

        if self.config.asset_class == "stock":
            source_mode = os.getenv("STOCK_MARKET_DATA_SOURCE", "websocket").strip().lower()
            if source_mode == "stream":
                import redis.asyncio as aioredis

                from services.trading.stream_consumer_feed import StreamConsumerFeed

                stream_name = os.getenv("MARKET_TICK_STREAM", "market:ticks")
                self._stream_redis = aioredis.from_url(
                    os.environ.get("REDIS_URL", "redis://localhost:6379/1")
                )
                self._stream_consumer_feed = StreamConsumerFeed(
                    redis=self._stream_redis,
                    stream=stream_name,
                    stale_threshold_seconds=self._load_stream_staleness_threshold(),
                )
                data_source = self._stream_consumer_feed
                logger.info(
                    "Stock data source = STREAM (%s); KIS WebSocket feed skipped",
                    stream_name,
                )
            else:
                try:
                    from shared.kis.stock_feed import KISStockPriceFeed

                    self._stock_price_feed = KISStockPriceFeed(
                        config=kis_config,
                    )
                    data_source = self._stock_price_feed
                    logger.info("Stock WebSocket price feed initialized")
                except (
                    NetworkError,
                    WebSocketDisconnectError,
                    ConfigurationError,
                ) as e:
                    logger.warning(f"Stock WebSocket feed init failed: {e}")
        elif self.config.asset_class == "futures":
```

(The `elif self.config.asset_class == "futures":` block below it is unchanged.)

- [ ] **Step 6: Run the tests to verify they pass**

Run: `pytest tests/unit/trading/test_orchestrator_stream_cutover.py -v`
Expected: PASS (4 tests).

- [ ] **Step 7: Commit**

```bash
git add services/trading/orchestrator.py tests/unit/trading/test_orchestrator_stream_cutover.py
git commit -m "feat(m1c): _init_price_feeds stream branch behind STOCK_MARKET_DATA_SOURCE"
```

---

## Task 3: Skip the tick-stream publisher on the stream path

On the stream path the M1a ingest daemon owns publishing. Leave `_tick_stream_publisher` `None` so the reused `_on_stock_tick`'s publish (guarded by `if self._tick_stream_publisher:`) no-ops — no double-publish, no separate branch.

**Files:**
- Modify: `services/trading/orchestrator.py` (`_init_tick_stream_publisher` 1453)
- Test: `tests/unit/trading/test_orchestrator_stream_cutover.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/trading/test_orchestrator_stream_cutover.py`:

```python
def test_tick_stream_publisher_skipped_on_stream_path():
    orch = TradingOrchestrator(TradingConfig.stock())
    orch._stream_consumer_feed = object()  # simulate active stream feed
    orch._init_tick_stream_publisher()
    assert orch._tick_stream_publisher is None


def test_tick_stream_publisher_built_on_websocket_path(monkeypatch):
    monkeypatch.setenv("TICK_STREAM_ENABLED", "false")  # config says disabled
    orch = TradingOrchestrator(TradingConfig.stock())
    orch._stream_consumer_feed = None
    orch._init_tick_stream_publisher()  # takes the normal (non-skip) path
    assert orch._tick_stream_publisher is None  # disabled-by-env, but path executed
```

- [ ] **Step 2: Run to verify the skip test fails**

Run: `pytest tests/unit/trading/test_orchestrator_stream_cutover.py -k tick_stream_publisher -v`
Expected: `test_tick_stream_publisher_skipped_on_stream_path` FAILS — the publisher init runs `TickStreamPublisherConfig.from_env()` and may set a non-None publisher (or raise), because the skip guard does not exist yet.

- [ ] **Step 3: Add the skip guard**

In `_init_tick_stream_publisher`, replace:

```python
    def _init_tick_stream_publisher(self) -> None:
        """Initialize optional Redis tick mirroring for monitoring."""
        try:
```
with:
```python
    def _init_tick_stream_publisher(self) -> None:
        """Initialize optional Redis tick mirroring for monitoring."""
        if self._stream_consumer_feed is not None:
            # Stream path: the market-ingest daemon owns publishing. Leave the
            # publisher None so the reused _on_stock_tick publish (guarded by
            # `if self._tick_stream_publisher:`) no-ops — no double-publish.
            self._tick_stream_publisher = None
            logger.info("Tick stream publisher skipped (stock data source = stream)")
            return
        try:
```

- [ ] **Step 4: Run to verify both tests pass**

Run: `pytest tests/unit/trading/test_orchestrator_stream_cutover.py -k tick_stream_publisher -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add services/trading/orchestrator.py tests/unit/trading/test_orchestrator_stream_cutover.py
git commit -m "feat(m1c): skip tick-stream publisher on stock stream path (no double-publish)"
```

---

## Task 4: Wire `_on_stock_tick` to the active stock feed

Generalize the `if self._stock_price_feed:` callback-wiring gate in `_init_indicator_engine` so the existing `_on_stock_tick` closure binds to whichever stock feed is active (`_stock_price_feed` or `_stream_consumer_feed`). The closure is unchanged — indicator + paper_broker preserved; publish gated off by Task 3.

**Files:**
- Modify: `services/trading/orchestrator.py` (`_init_indicator_engine`, lines 1786–1821)
- Test: `tests/unit/trading/test_orchestrator_stream_cutover.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/trading/test_orchestrator_stream_cutover.py`:

```python
class _RecordingFeed:
    """Stand-in for a stock feed that records its tick callback."""

    def __init__(self) -> None:
        self.callback = None

    def set_tick_callback(self, callback) -> None:
        self.callback = callback


def test_init_indicator_engine_wires_callback_to_stream_feed():
    orch = TradingOrchestrator(TradingConfig.stock())
    # Minimal state the wiring block reads at top level:
    orch._strategy_manager = None
    orch._stock_price_feed = None
    orch._futures_price_feed = None
    fake = _RecordingFeed()
    orch._stream_consumer_feed = fake

    orch._init_indicator_engine()

    assert fake.callback is not None  # _on_stock_tick bound to the stream feed
    assert callable(fake.callback)


def test_init_indicator_engine_wires_callback_to_ws_feed_when_present():
    orch = TradingOrchestrator(TradingConfig.stock())
    orch._strategy_manager = None
    orch._futures_price_feed = None
    orch._stream_consumer_feed = None
    fake = _RecordingFeed()
    orch._stock_price_feed = fake

    orch._init_indicator_engine()

    assert fake.callback is not None  # WS path unchanged
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/unit/trading/test_orchestrator_stream_cutover.py -k indicator_engine -v`
Expected: `test_init_indicator_engine_wires_callback_to_stream_feed` FAILS — `fake.callback is None` (current code only wires when `_stock_price_feed` is truthy).

- [ ] **Step 3: Generalize the wiring gate**

In `_init_indicator_engine`, replace:

```python
        # Hook stock WebSocket ticks into indicator engine and monitoring stream.
        if self._stock_price_feed:

            def _on_stock_tick(symbol: str, data: dict[str, Any], ts: datetime) -> None:
```
with:
```python
        # Hook stock ticks (WS feed or Redis stream feed) into the indicator
        # engine, paper broker, and (gated) monitoring stream.
        stock_feed = self._stock_price_feed or self._stream_consumer_feed
        if stock_feed:

            def _on_stock_tick(symbol: str, data: dict[str, Any], ts: datetime) -> None:
```

Then replace the wiring line at the end of that block:

```python
            self._stock_price_feed.set_tick_callback(_on_stock_tick)
```
with:
```python
            stock_feed.set_tick_callback(_on_stock_tick)
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/unit/trading/test_orchestrator_stream_cutover.py -k indicator_engine -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add services/trading/orchestrator.py tests/unit/trading/test_orchestrator_stream_cutover.py
git commit -m "feat(m1c): wire _on_stock_tick to active stock feed (stream or WS)"
```

---

## Task 5: Start/stop the stream feed in the market-data loop

Add two small helpers and call them additively from `_start_market_data_loop` / `_stop_market_data_loop`. The existing `_stock_price_feed` / `_futures_price_feed` blocks are untouched; on the websocket path the new code no-ops.

**Files:**
- Modify: `services/trading/orchestrator.py` (new helpers + 1-line calls in `_start_market_data_loop` 4332 and `_stop_market_data_loop` 4416)
- Test: `tests/unit/trading/test_orchestrator_stream_cutover.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/trading/test_orchestrator_stream_cutover.py`:

```python
class _FakeStreamFeed:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.symbols = None

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    def update_symbols(self, symbols) -> None:
        self.symbols = list(symbols)


class _FakeAsyncRedis:
    def __init__(self) -> None:
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_start_stream_consumer_feed_starts_and_subscribes():
    orch = TradingOrchestrator(TradingConfig.stock())
    orch.config.symbols = ["005930", "000660"]
    fake = _FakeStreamFeed()
    orch._stream_consumer_feed = fake
    await orch._start_stream_consumer_feed()
    assert fake.started is True
    assert fake.symbols == ["005930", "000660"]


@pytest.mark.asyncio
async def test_stop_stream_consumer_feed_stops_and_closes_redis():
    orch = TradingOrchestrator(TradingConfig.stock())
    fake = _FakeStreamFeed()
    redis = _FakeAsyncRedis()
    orch._stream_consumer_feed = fake
    orch._stream_redis = redis
    await orch._stop_stream_consumer_feed()
    assert fake.stopped is True
    assert redis.closed is True
    assert orch._stream_redis is None


@pytest.mark.asyncio
async def test_stream_feed_helpers_noop_when_absent():
    orch = TradingOrchestrator(TradingConfig.stock())
    orch._stream_consumer_feed = None
    orch._stream_redis = None
    await orch._start_stream_consumer_feed()  # no raise
    await orch._stop_stream_consumer_feed()  # no raise
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/unit/trading/test_orchestrator_stream_cutover.py -k stream_consumer_feed -v`
Expected: FAIL — `AttributeError: 'TradingOrchestrator' object has no attribute '_start_stream_consumer_feed'`.

- [ ] **Step 3: Add the two helper methods**

Insert these two methods immediately before `async def _start_market_data_loop` (line 4332):

```python
    async def _start_stream_consumer_feed(self) -> None:
        """Start the Redis stream consumer feed (M1c stream path) if active."""
        if not self._stream_consumer_feed:
            return
        await self._stream_consumer_feed.start()
        self._stream_consumer_feed.update_symbols(self.config.symbols)
        logger.info(
            "Stock stream-consumer feed started (%d symbols)",
            len(self.config.symbols or []),
        )

    async def _stop_stream_consumer_feed(self) -> None:
        """Stop the stream consumer feed and close its async redis client."""
        if not self._stream_consumer_feed:
            return
        try:
            await self._stream_consumer_feed.stop()
        finally:
            if self._stream_redis is not None:
                closer = getattr(self._stream_redis, "aclose", None) or (
                    self._stream_redis.close
                )
                await closer()
                self._stream_redis = None
```

- [ ] **Step 4: Call the start helper in `_start_market_data_loop`**

In `_start_market_data_loop`, find the end of the futures block (line 4377, the `self._futures_price_feed = None` inside the `except`). Immediately after the whole `if self._futures_price_feed:` block and before `if self._data_provider and self._data_provider_failover_enabled:` (line 4379), insert:

```python
        await self._start_stream_consumer_feed()
```

- [ ] **Step 5: Call the stop helper in `_stop_market_data_loop`**

In `_stop_market_data_loop`, find the end of the futures stop block (line 4448, the `logger.warning(f"Futures price feed stop error: {e}")`). Immediately after the whole `if self._futures_price_feed:` block and before `if self._universe_refresh_task:` (line 4450), insert:

```python
        await self._stop_stream_consumer_feed()
```

- [ ] **Step 6: Run to verify they pass**

Run: `pytest tests/unit/trading/test_orchestrator_stream_cutover.py -k stream_consumer_feed -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Run the whole new test file**

Run: `pytest tests/unit/trading/test_orchestrator_stream_cutover.py -v`
Expected: PASS (all tasks 2–5 tests).

- [ ] **Step 8: Commit**

```bash
git add services/trading/orchestrator.py tests/unit/trading/test_orchestrator_stream_cutover.py
git commit -m "feat(m1c): start/stop stream consumer feed in market-data loop"
```

---

## Task 6: Operator activation runbook

Document how an operator turns the stream path on, validates the SLO, and rolls back. Code-merge is inert (default off); this runbook is the activation gate.

**Files:**
- Create: `docs/runbooks/stock-stream-cutover.md`

- [ ] **Step 1: Write the runbook**

Create `docs/runbooks/stock-stream-cutover.md`:

```markdown
# Runbook — Stock Market-Data Stream Cutover (M1c)

Switch the stock orchestrator from owning the KIS WebSocket feed to consuming
the Redis tick stream published by the `kis-market-ingest-stock` daemon (M1a).
Flag: `STOCK_MARKET_DATA_SOURCE` (`websocket` default | `stream`). Stock only —
futures stays `websocket` (the tick stream carries no orderbook, which the
futures slippage controller requires).

## Preconditions

1. `kis-market-ingest-stock` (M1a) running and healthy:
   - `systemctl status kis-market-ingest-stock`
   - Redis: `redis-cli -n 1 XLEN market:ticks` rising during market hours.
2. No second WebSocket consumer for the same KIS stock account (the ingest
   daemon owns the WS connection; the orchestrator must NOT also connect).

## Activate

1. Set the flag for the stock orchestrator process/unit env:
   `STOCK_MARKET_DATA_SOURCE=stream`
   (also ensure `REDIS_URL` points at the right DB — paper `…/1` on 6381,
   live `…/1` on 6382, per the paper/live separation runbook).
2. Restart the stock orchestrator.
3. Confirm in logs: `Stock data source = STREAM (market:ticks); KIS WebSocket feed skipped`
   and `Stock stream-consumer feed started (N symbols)`.

## Validate the SLO

The goal is ingest latency independent of downstream compute load. Check:

- `market_data_staleness` p99 flat/improved vs the websocket baseline and not
  rising when indicator/strategy/LLM load spikes.
- tick→XADD latency (ingest side) stable.
- `trading_signal_latency_ms` unchanged or better.
- Positions/signals/fills appear normal vs the websocket baseline; paper PnL
  marks update per tick (paper_broker observations preserved).

## Rollback

1. Set `STOCK_MARKET_DATA_SOURCE=websocket` (or unset).
2. Restart the stock orchestrator. It rebuilds the KIS WebSocket feed; the
   stream feed and its async redis client are torn down on stop.

No data migration is involved — the flag flip is the whole switch.

## Notes

- If the ingest daemon dies/lags while `stream` is active, the orchestrator's
  `MarketDataProvider` failover degrades to KIS REST polling (the `_kis_client`
  is retained) rather than going dark.
- Futures cutover is a separate increment (needs an orderbook transport).
```

- [ ] **Step 2: Commit**

```bash
git add docs/runbooks/stock-stream-cutover.md
git commit -m "docs(m1c): operator runbook for stock stream cutover"
```

---

## Task 7: Full-suite green + lint

- [ ] **Step 1: Run the trading unit + the cross-daemon e2e to ensure no regression**

Run: `pytest tests/unit/trading/ tests/integration/test_orchestrator_lifecycle.py -q`
Expected: PASS (no regression in existing orchestrator/feed tests).

- [ ] **Step 2: Run lint + format on the touched files**

Run:
```bash
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check services/trading/orchestrator.py services/trading/stream_consumer_feed.py tests/unit/trading/test_orchestrator_stream_cutover.py
/home/deploy/project/kis_unified_sts/.venv/bin/black --check services/trading/orchestrator.py services/trading/stream_consumer_feed.py tests/unit/trading/test_orchestrator_stream_cutover.py
```
Expected: clean. If black reports changes, run without `--check` and amend the last commit.

- [ ] **Step 3: Run the full suite (merge gate parity)**

Run: `pytest tests/ -q -x`
Expected: PASS. (Mirrors the CI `test` gate, the sole merge gate.)

- [ ] **Step 4: Push and open the PR**

```bash
git push -u origin feat/orchestrator-stream-cutover-m1c
gh pr create --base main --head feat/orchestrator-stream-cutover-m1c \
  --title "feat(m1c): orchestrator stock data-source cutover (flag-gated, default off)" \
  --body "$(cat <<'EOF'
## What
Behind a default-off flag `STOCK_MARKET_DATA_SOURCE=stream` (stock only), the
orchestrator consumes the Redis tick stream via `StreamConsumerFeed` instead of
owning the KIS stock WebSocket feed. Reuses the existing `_on_stock_tick`
(indicator + paper-broker mark-to-market preserved); publish is owned by the
M1a ingest daemon. REST failover retained.

## Why
M1 of the stream-pipeline decoupling: isolate WS ingest latency from downstream
compute (indicator/strategy/LLM/order). Merge is operationally inert (default
`websocket`); operator activation is gated by `docs/runbooks/stock-stream-cutover.md`.

## How tested
- `StreamConsumerFeed.set_tick_callback` unit (callback replaces indicator push).
- Flag routing: stream branch builds `StreamConsumerFeed` + no KIS feed; default
  builds KIS feed; futures ignores the stock flag.
- Publisher skipped on stream path; `_on_stock_tick` wired to active feed;
  start/stop helpers start/stop feed + close async redis.
- Full `tests/` suite green; ruff + black clean.

## Scope
Stock only — futures stays `websocket` (tick stream has no orderbook). Enabling
the M1a ingest unit + flipping the flag is an operator step (runbook).

Spec: `docs/superpowers/specs/2026-06-04-orchestrator-stream-cutover-m1c-design.md`
Plan: `docs/superpowers/plans/archive/2026-06-04-orchestrator-stream-cutover-m1c.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review (plan vs spec)

- **§3.1 flag/data-source** → Task 2 (flag read, stream branch, async redis, attrs). ✓
- **§3.2 wire `_on_stock_tick`** → Task 4 (generalize gate, reuse closure). ✓
- **§3.3 start/stop lifecycle** → Task 5 (additive helpers + calls). ✓
- **§3.4 skip publisher** → Task 3. ✓
- **§1 per-tick (paper_broker) preserved** → Task 1 (`set_tick_callback`) + Task 4 (reuse closure). ✓
- **§4 REST fallback** → unchanged code (`_kis_client` retained, `get_health_status` already implemented); no task needed, asserted by leaving the failover path untouched. ✓
- **§6 activation runbook** → Task 6. ✓
- **§7 testing / §9 acceptance** → Tasks 1–5 tests + Task 7 full-suite/lint. ✓
- **Type consistency:** `set_tick_callback(callback)` / `_tick_callback` / `_stream_consumer_feed` / `_stream_redis` / `_load_stream_staleness_threshold` / `_start_stream_consumer_feed` / `_stop_stream_consumer_feed` used identically across tasks. ✓
- **No placeholders:** every code/test step shows full code + exact command + expected result. ✓
```
