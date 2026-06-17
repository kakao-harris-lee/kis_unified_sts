# Market Ingest Daemon (M1a) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone per-asset "market ingest" daemon whose ONLY job is to own a KIS price feed and republish every tick to the Redis tick stream (`market:ticks` / `raw_data`) — nothing else. Isolating the WebSocket reader into its own process is the load-bearing cut of M1: tick→stream latency becomes independent of indicator/strategy/order compute.

**Architecture:** `services/market_ingest/main.py` — `MarketIngestDaemon` owns an injected `feed` (a `KIS*PriceFeed`) + an injected `publisher` (`TickStreamPublisher`) + a `symbol_provider` (async callable returning the symbol list). It wires `feed.set_tick_callback(self._on_tick)` where `_on_tick` does ONLY `publisher.publish(asset, symbol, data)`, then drives a refresh loop that re-subscribes the feed when the universe changes. Reuses the existing `KIS*PriceFeed` (reconnect/decryption/parse/health) and `TickStreamPublisher` (throttle + async XADD worker) verbatim. `_build_and_run` wires the real feed/publisher/universe per `INGEST_ASSET=stock|futures`.

**Tech Stack:** Python 3.11 asyncio, `redis.asyncio` (universe reads), `KIS*PriceFeed`, `TickStreamPublisher`, pytest. No new deps.

**Spec:** `docs/superpowers/specs/2026-06-04-stream-pipeline-decoupling-design.md`. This is increment **M1a** (the ingest producer). The consumer side — `StreamConsumerFeed` (M1b) + the orchestrator per-asset flag cutover (M1c) — are separate plans. Design decision (locked 2026-06-04): the consumer (M1b) pushes per-tick to the indicator engine; that is out of scope here.

**Dual-run safety (READ):** Until M1c flips the orchestrator off its own feed, running this daemon AND the orchestrator simultaneously opens TWO KIS WebSocket connections for the same symbols. The systemd units this plan adds are delivered **disabled** — do NOT `systemctl enable` them until M1c. (Publishing to the same tick stream the orchestrator already publishes to is harmless; the double WS connection is the hazard.)

---

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `services/market_ingest/__init__.py` | Create | package marker (empty) |
| `services/market_ingest/main.py` | Create | `MarketIngestDaemon` + `_parse_trade_targets` + `_build_and_run`/`main` |
| `tests/unit/services/test_market_ingest.py` | Create | daemon wiring + universe-refresh + tick-republish + parse tests |
| `deploy/systemd/kis-market-ingest-stock.service` | Create | systemd unit (delivered disabled) |
| `deploy/systemd/kis-market-ingest-futures.service` | Create | systemd unit (delivered disabled) |

Run tests via the worktree using the main venv: `cd /tmp/m1a && /home/deploy/project/kis_unified_sts/.venv/bin/python -m pytest <path> -q`.

---

## Task 1: `MarketIngestDaemon` + `_parse_trade_targets` + unit tests

**Files:** Create `services/market_ingest/__init__.py`, `services/market_ingest/main.py` (daemon + parse helper only — the `_build_and_run` wiring is Task 2), `tests/unit/services/test_market_ingest.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/services/test_market_ingest.py` with EXACTLY this content:

```python
"""Unit tests for the market ingest daemon (feed → tick-stream republish)."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from services.market_ingest.main import MarketIngestDaemon, _parse_trade_targets


class FakeFeed:
    def __init__(self):
        self.callback = None
        self.symbol_calls: list[list[str]] = []
        self.started = 0
        self.stopped = 0

    def set_tick_callback(self, cb):
        self.callback = cb

    def update_symbols(self, symbols, *args, **kwargs):
        self.symbol_calls.append(list(symbols))

    async def start(self):
        self.started += 1

    async def stop(self):
        self.stopped += 1


class FakePublisher:
    def __init__(self):
        self.published: list[tuple[str, str, dict]] = []
        self.closed = 0

    def publish(self, asset, symbol, payload):
        self.published.append((asset, symbol, payload))

    def close(self, timeout: float = 2.0):
        self.closed += 1


def _provider(values: list[list[str]]):
    """Async symbol provider yielding each value once, then repeating the last."""
    state = {"i": 0}

    async def _p() -> list[str]:
        i = state["i"]
        if i < len(values):
            state["i"] = i + 1
            return values[i]
        return values[-1]

    return _p


def _daemon(feed, publisher, provider, *, asset="stock", restart=False, interval=0.02):
    return MarketIngestDaemon(
        asset=asset,
        feed=feed,
        publisher=publisher,
        symbol_provider=provider,
        refresh_interval_seconds=interval,
        restart_on_symbol_change=restart,
    )


async def _run_briefly(daemon, seconds=0.12):
    task = asyncio.create_task(daemon.run())
    await asyncio.sleep(seconds)
    await daemon.stop()
    await asyncio.wait_for(task, timeout=1.0)


@pytest.mark.asyncio
async def test_wires_callback_and_starts_feed():
    feed, pub = FakeFeed(), FakePublisher()
    await _run_briefly(_daemon(feed, pub, _provider([["A"]])))
    assert feed.callback is not None
    assert feed.symbol_calls[0] == ["A"]  # initial subscription
    assert feed.started == 1


@pytest.mark.asyncio
async def test_tick_is_republished_to_publisher():
    feed, pub = FakeFeed(), FakePublisher()
    await _run_briefly(_daemon(feed, pub, _provider([["A"]]), asset="futures"))
    # invoke the registered feed callback as the feed thread would
    feed.callback("A", {"close": 100.0}, datetime.now(UTC))
    assert pub.published == [("futures", "A", {"close": 100.0})]


@pytest.mark.asyncio
async def test_universe_change_updates_symbols_live_for_stock():
    feed, pub = FakeFeed(), FakePublisher()
    await _run_briefly(_daemon(feed, pub, _provider([["A"], ["A", "B"]]), restart=False))
    assert ["A", "B"] in feed.symbol_calls  # live re-subscribe
    assert feed.stopped == 1  # only the final shutdown stop (no restart)


@pytest.mark.asyncio
async def test_universe_change_restarts_feed_for_futures():
    feed, pub = FakeFeed(), FakePublisher()
    await _run_briefly(_daemon(feed, pub, _provider([["A"], ["B"]]), asset="futures", restart=True))
    assert ["B"] in feed.symbol_calls
    assert feed.started == 2  # initial + restart-on-change
    assert feed.stopped >= 1  # restart stop (+ final stop)


@pytest.mark.asyncio
async def test_stop_stops_feed_and_closes_publisher():
    feed, pub = FakeFeed(), FakePublisher()
    await _run_briefly(_daemon(feed, pub, _provider([["A"]])))
    assert feed.stopped >= 1
    assert pub.closed == 1


@pytest.mark.asyncio
async def test_symbol_provider_failure_keeps_current_symbols():
    feed, pub = FakeFeed(), FakePublisher()

    calls = {"n": 0}

    async def flaky() -> list[str]:
        calls["n"] += 1
        if calls["n"] == 1:
            return ["A"]
        raise RuntimeError("redis down")

    await _run_briefly(_daemon(feed, pub, flaky))
    # initial ["A"] applied; later failures do not crash or re-subscribe
    assert feed.symbol_calls == [["A"]]
    assert feed.started == 1


def test_parse_trade_targets_extracts_codes_capped():
    raw = '{"codes": ["005930", " 000660 ", "", "035720"], "names": {}}'
    assert _parse_trade_targets(raw, max_symbols=2) == ["005930", "000660"]


def test_parse_trade_targets_handles_none_and_bad_json():
    assert _parse_trade_targets(None, max_symbols=40) == []
    assert _parse_trade_targets("not json", max_symbols=40) == []
    assert _parse_trade_targets("{}", max_symbols=40) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /tmp/m1a && /home/deploy/project/kis_unified_sts/.venv/bin/python -m pytest tests/unit/services/test_market_ingest.py -q`
Expected: import error — `services.market_ingest.main` does not exist.

- [ ] **Step 3: Create the package marker**

Create `services/market_ingest/__init__.py` as an EMPTY file (0 bytes — matches `services/news_scorer/__init__.py`).

- [ ] **Step 4: Write the daemon + parse helper**

Create `services/market_ingest/main.py` with EXACTLY this content:

```python
"""Market ingest daemon — owns a KIS price feed and republishes every tick to the
Redis tick stream (``market:ticks`` / ``raw_data``) and NOTHING else.

Isolating the WebSocket reader in its own process keeps tick→stream latency
independent of downstream indicator/strategy/order compute (M1 of the
stream-pipeline-decoupling design). Per-asset: ``INGEST_ASSET=stock|futures``
selects the feed + symbol source in ``_build_and_run``.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

SymbolProvider = Callable[[], Awaitable[list[str]]]


def _parse_trade_targets(raw: str | None, max_symbols: int) -> list[str]:
    """Parse a ``system:trade_targets:latest`` payload into a capped code list.

    Payload shape: ``{"codes": [...], "names": {...}, "metadata": {...}}``.
    Returns ``[]`` on missing/invalid input so the daemon keeps its current
    subscription rather than crashing.
    """
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(payload, dict):
        return []
    codes = [str(c).strip() for c in payload.get("codes", []) if str(c).strip()]
    return codes[:max_symbols]


class MarketIngestDaemon:
    """Own a KIS price feed; republish each tick to the Redis tick stream.

    The tick callback does ONLY ``publisher.publish`` — no indicators, strategy,
    or orders — so the feed's frame-processing thread is never blocked by
    downstream compute.
    """

    def __init__(
        self,
        *,
        asset: str,
        feed: Any,
        publisher: Any,
        symbol_provider: SymbolProvider,
        refresh_interval_seconds: float,
        restart_on_symbol_change: bool = False,
    ) -> None:
        self.asset = asset
        self.feed = feed
        self.publisher = publisher
        self.symbol_provider = symbol_provider
        self.refresh_interval_seconds = refresh_interval_seconds
        self.restart_on_symbol_change = restart_on_symbol_change
        self._symbols: list[str] = []
        self._stop = asyncio.Event()

    def _on_tick(self, symbol: str, data: dict[str, Any], ts: datetime) -> None:
        # Hot path: republish only. (ts is part of the feed callback contract
        # but the tick stream carries its own timestamp in `data`.)
        self.publisher.publish(self.asset, symbol, data)

    async def _apply_symbols(self, symbols: list[str]) -> None:
        if self.restart_on_symbol_change:
            # Futures feed requires update_symbols BEFORE start(); restart on change.
            await self.feed.stop()
            self.feed.update_symbols(symbols)
            await self.feed.start()
        else:
            # Stock feed accepts live update_symbols (diffs sub/unsub internally).
            self.feed.update_symbols(symbols)
        self._symbols = symbols

    async def run(self) -> None:
        self.feed.set_tick_callback(self._on_tick)
        symbols = await self.symbol_provider()
        self._symbols = symbols
        self.feed.update_symbols(symbols)
        await self.feed.start()
        logger.info(
            "market-ingest started asset=%s symbols=%d", self.asset, len(symbols)
        )
        try:
            while not self._stop.is_set():
                try:
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=self.refresh_interval_seconds
                    )
                except TimeoutError:
                    pass
                if self._stop.is_set():
                    break
                try:
                    new_symbols = await self.symbol_provider()
                except Exception:
                    logger.exception(
                        "symbol_provider failed; keeping current symbols"
                    )
                    continue
                if new_symbols and new_symbols != self._symbols:
                    logger.info(
                        "universe change asset=%s %d→%d",
                        self.asset,
                        len(self._symbols),
                        len(new_symbols),
                    )
                    await self._apply_symbols(new_symbols)
        finally:
            await self.feed.stop()
            self.publisher.close()
            logger.info("market-ingest stopped asset=%s", self.asset)

    async def stop(self) -> None:
        self._stop.set()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd /tmp/m1a && /home/deploy/project/kis_unified_sts/.venv/bin/python -m pytest tests/unit/services/test_market_ingest.py -q`
Expected: 8 passed.

- [ ] **Step 6: Lint**

Run: `cd /tmp/m1a && /home/deploy/project/kis_unified_sts/.venv/bin/ruff check services/market_ingest/main.py tests/unit/services/test_market_ingest.py && /home/deploy/project/kis_unified_sts/.venv/bin/black --check services/market_ingest/main.py tests/unit/services/test_market_ingest.py`
Expected: clean. If `_on_tick`'s `ts`/`symbol` (when unused) trips `ARG002`, that's fine — they ARE used (`symbol` in publish); `ts` is unused → add `  # noqa: ARG002` on the `def _on_tick(` line only if ruff flags it. Run `black ...` to auto-format if needed.

- [ ] **Step 7: Commit**

```bash
cd /tmp/m1a
git add services/market_ingest/__init__.py services/market_ingest/main.py tests/unit/services/test_market_ingest.py
git commit -m "feat: add MarketIngestDaemon (feed → tick-stream republish, isolated WS reader)"
```

---

## Task 2: Real wiring (`_build_and_run`/`main`) + systemd units

`_build_and_run` is integration glue (real KIS feed + Redis), not unit-tested — like the other daemons' entrypoints. The testable parse logic is already covered (Task 1).

**Files:** Modify `services/market_ingest/main.py` (append `_build_and_run`/`main`/`__main__`); Create `deploy/systemd/kis-market-ingest-stock.service`, `deploy/systemd/kis-market-ingest-futures.service`.

- [ ] **Step 1: Append the entrypoint to `services/market_ingest/main.py`**

Append EXACTLY this to the end of `services/market_ingest/main.py`:

```python
async def _build_and_run() -> int:
    """Production entrypoint. INGEST_ASSET=stock|futures selects feed + universe."""
    import os
    import signal as signal_mod

    import redis.asyncio as aioredis

    from services.monitoring.tick_stream_publisher import (
        TickStreamPublisher,
        TickStreamPublisherConfig,
    )
    from shared.kis.auth import KISAuthConfig

    asset = os.environ.get("INGEST_ASSET", "").strip().lower()
    if asset not in ("stock", "futures"):
        logger.error("INGEST_ASSET must be 'stock' or 'futures' (got %r)", asset)
        return 64

    publisher = TickStreamPublisher(TickStreamPublisherConfig.from_env())

    if asset == "stock":
        from shared.kis.stock_feed import KISStockPriceFeed

        auth = KISAuthConfig(
            app_key=os.environ.get("KIS_STOCK_APP_KEY", ""),
            app_secret=os.environ.get("KIS_STOCK_APP_SECRET", ""),
            is_real=os.environ.get("KIS_STOCK_MARKET", "mock").lower() == "real",
        )
        feed: Any = KISStockPriceFeed(config=auth)
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
        redis_client = aioredis.from_url(redis_url)
        target_key = os.environ.get(
            "TRADE_TARGETS_LATEST_KEY", "system:trade_targets:latest"
        )
        max_symbols = int(os.environ.get("INGEST_MAX_SYMBOLS", "40"))

        async def symbol_provider() -> list[str]:
            raw = await redis_client.get(target_key)
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            return _parse_trade_targets(raw, max_symbols)

        refresh_interval = float(os.environ.get("INGEST_REFRESH_SECONDS", "30"))
        restart_on_change = False
        cleanup_redis = redis_client
    else:
        from shared.collector.historical.futures import get_front_month_code
        from shared.kis.futures_feed import KISFuturesPriceFeed

        auth = KISAuthConfig(
            app_key=os.environ.get("KIS_FUTURES_APP_KEY", ""),
            app_secret=os.environ.get("KIS_FUTURES_APP_SECRET", ""),
            is_real=os.environ.get("KIS_FUTURES_MARKET", "real").lower() == "real",
        )
        feed = KISFuturesPriceFeed(config=auth)

        async def symbol_provider() -> list[str]:
            return [get_front_month_code(product="mini")]

        # Re-resolve hourly so a quarterly rollover triggers a restart-on-change.
        refresh_interval = float(os.environ.get("INGEST_REFRESH_SECONDS", "3600"))
        restart_on_change = True
        cleanup_redis = None

    daemon = MarketIngestDaemon(
        asset=asset,
        feed=feed,
        publisher=publisher,
        symbol_provider=symbol_provider,
        refresh_interval_seconds=refresh_interval,
        restart_on_symbol_change=restart_on_change,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal_mod.SIGTERM, signal_mod.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    try:
        await daemon.run()
    finally:
        if cleanup_redis is not None:
            await cleanup_redis.aclose()
    return 0


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return asyncio.run(_build_and_run())


if __name__ == "__main__":
    import sys

    sys.exit(main())
```

- [ ] **Step 2: Verify the module still imports + tests still pass + lint**

Run:
```
cd /tmp/m1a
/home/deploy/project/kis_unified_sts/.venv/bin/python -c "import services.market_ingest.main as m; assert callable(m.main) and callable(m._build_and_run)"
/home/deploy/project/kis_unified_sts/.venv/bin/python -m pytest tests/unit/services/test_market_ingest.py -q
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check services/market_ingest/main.py
/home/deploy/project/kis_unified_sts/.venv/bin/black --check services/market_ingest/main.py
```
Expected: import OK, 8 passed, ruff clean, black clean. (If `cleanup_redis`/`auth`/`feed` type reassignment trips a ruff/mypy complaint, the `feed: Any` annotation on first assignment covers the branch reassignment.)

- [ ] **Step 3: Create the systemd units (delivered DISABLED)**

Create `deploy/systemd/kis-market-ingest-stock.service`:
```ini
[Unit]
Description=KIS Market Ingest — stock (WS feed → Redis tick stream market:ticks)
After=network-online.target redis.service
Wants=network-online.target

# WARNING (M1a): do NOT enable while the trading orchestrator still owns its own
# stock WS feed — that opens two KIS WebSocket connections for the same symbols.
# Enable only after M1c flips the orchestrator off its feed.

[Service]
Type=simple
User=deploy
WorkingDirectory=/home/deploy/project/kis_unified_sts
EnvironmentFile=/home/deploy/project/kis_unified_sts/.env
Environment=INGEST_ASSET=stock
ExecStart=/home/deploy/project/kis_unified_sts/.venv/bin/python -m services.market_ingest.main
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Create `deploy/systemd/kis-market-ingest-futures.service` (identical except Description/INGEST_ASSET):
```ini
[Unit]
Description=KIS Market Ingest — futures (WS feed → Redis tick stream raw_data)
After=network-online.target redis.service
Wants=network-online.target

# WARNING (M1a): do NOT enable while the trading orchestrator still owns its own
# futures WS feed — that opens two KIS WebSocket connections. Enable only after M1c.

[Service]
Type=simple
User=deploy
WorkingDirectory=/home/deploy/project/kis_unified_sts
EnvironmentFile=/home/deploy/project/kis_unified_sts/.env
Environment=INGEST_ASSET=futures
ExecStart=/home/deploy/project/kis_unified_sts/.venv/bin/python -m services.market_ingest.main
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 4: Commit**

```bash
cd /tmp/m1a
git add services/market_ingest/main.py deploy/systemd/kis-market-ingest-stock.service deploy/systemd/kis-market-ingest-futures.service
git commit -m "feat: market-ingest entrypoint (per-asset KIS feed wiring) + systemd units (disabled)"
```

---

## Self-Review (completed by plan author)

- **Spec coverage:** Implements the M1 ingest producer (spec §4.1 Ingest stage / §5 M1): a standalone process that does frame→XADD only, reusing `KIS*PriceFeed` + `TickStreamPublisher`. The consumer side (`StreamConsumerFeed`, M1b) and orchestrator cutover (M1c) are explicitly deferred — not gaps. The dual-run hazard is handled by shipping the systemd units disabled with an explicit warning.
- **Placeholder scan:** No TBD/TODO. The daemon, parse helper, full tests, the entrypoint, and both unit files are complete inline.
- **Type/name consistency:** `_on_tick(symbol, data, ts)` matches the feeds' `Callable[[str, dict, datetime], None]` callback contract (verified). `symbol_provider: () -> Awaitable[list[str]]`. `publisher.publish(asset, symbol, data)` + `publisher.close()` match `TickStreamPublisher` (no `start`/`flush` — worker starts in `__init__`, `close()` shuts down). `feed.update_symbols`/`set_tick_callback`/`start`/`stop` match both feeds. Futures `restart_on_symbol_change=True` honors the futures-feed "update before start" constraint; stock uses live `update_symbols`.
- **Verbatim-signature fidelity:** `KISAuthConfig(app_key, app_secret, is_real)`, `get_front_month_code(product="mini")`, `TickStreamPublisherConfig.from_env()`, the `system:trade_targets:latest` JSON shape (`payload["codes"]`), and the 30s stock refresh interval all match origin/main.
- **Test independence:** Task-1 tests use fakes (no KIS, no Redis) + pure-function parse tests — fully hermetic. `_build_and_run` (Task 2) is real glue, validated only by an import smoke check (the parse logic it relies on is unit-tested in Task 1), consistent with how news_scorer/risk_filter/order_router entrypoints are treated.
