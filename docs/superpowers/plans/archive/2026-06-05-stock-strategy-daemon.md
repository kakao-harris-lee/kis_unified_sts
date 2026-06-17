# Stock Strategy Daemon (M4-P, shadow-first) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build the missing stock signal producer: a shadow-first daemon that consumes `market:ticks` into a daemon-local indicator engine (reuse M1b `StreamConsumerFeed`), refreshes a dynamic screener universe, builds an `EntryContext` per warm symbol on a decision cadence, runs the existing `StrategyManager.check_entries`, and publishes a stock-native candidate to `signal.candidate.stock.shadow`. Default-off, no live impact.

**Architecture:** Reuse-first. `StreamConsumerFeed` + `StreamingIndicatorEngine` + `StreamingIndicatorResolver` + `StrategyManager` (with enabled stock strategies) are reused. New: a `StockCandidate` serializer, a universe parser, the `StockStrategyDaemon` (decision loop + universe-refresh loop), a flag-gated entrypoint, a disabled systemd unit.

**Tech stack:** Python 3.11, `redis.asyncio` (+ a sync client for the watchlist read), pytest.

**Spec:** `docs/superpowers/specs/2026-06-05-stock-strategy-daemon-design.md` (NOTE: the spec mentions `system:trade_targets:latest`; the actual orchestrator universe key is `system:daily_watchlist:latest` — this plan uses the correct key.)

**Environment:** Work in the worktree `/tmp/ssd` (branch `feat/stock-strategy-daemon`). No `.venv` in the worktree; run tests with:
```bash
cd /tmp/ssd && PYTHONPATH=/tmp/ssd /home/deploy/project/kis_unified_sts/.venv/bin/pytest <args> -p no:cacheprovider
```
Never touch the operator's main checkout or running services.

**Key verbatim facts:**
- `EntryContext` (`shared/strategy/base.py:85-113`): dataclass fields `market_data: dict`, `indicators: dict`, `current_positions: list[Position]`, `timestamp: datetime`, `market_context: MarketContext|None`, `metadata: dict`.
- `StrategyManager.__init__(asset_class="stock", strategy_names=None, config=None, indicator_engine=None)` (`services/trading/strategy_manager.py:232`) — loads enabled strategies via `StrategyFactory.create_all(asset_class, enabled_only=True)`; builds its own `LLMContextProvider`. `async check_entries(context: EntryContext) -> list[Signal]` (`:444`). `required_indicators -> list[str]` property (`:437`). `set_indicator_engine(engine)` (`:356`).
- `StreamingIndicatorResolver(*, engine, required_keys)` (`shared/indicators/resolver.py:18`); `collect_entry_indicators(symbol) -> dict` (`:27`).
- orchestrator `Signal` (`shared/models/signal.py:64`): `code: str`, `name: str=""`, `signal_type: SignalType=ENTRY`, `strategy: str=""`, `price: float=0.0`, `quantity: int=0`, `confidence: float=0.5`, `timestamp: datetime`, `metadata: dict`. **No `to_stream_dict`** (this plan adds a serializer).
- Universe: orchestrator `_load_static_watchlist` (`:3191`) does `RedisClient.get_client().get("system:daily_watchlist:latest")` → `json.loads` → `payload["strategies"]` (dict of strategy→code-list) → union of codes; cap is the stock feed max (≤40, `streaming.yaml::stock_feed.max_symbols`).
- orchestrator per-symbol build (`:6095`): `EntryContext(market_data=enriched, indicators=resolver.collect_entry_indicators(symbol), current_positions=..., timestamp=now, metadata={...})` → `await strategy_manager.check_entries(context)`.
- `StreamConsumerFeed(*, redis, stream, indicator_engine=None, tick_callback=None, stale_threshold_seconds=30.0, xread_block_ms=1000, xread_count=200)`; `start()`/`stop()`/`update_symbols(list)`/`async get_current_price(symbol) -> dict`/`is_warm` via engine.
- Reuse templates from the merged futures daemon (#414): `services/decision_engine/main.py` (`_resolve_mode`/`_candidate_stream_for`/`_build_shadow_context_provider`/`_warmup_engine_from_parquet`, flag-gated `_build_and_run`, sync-redis macro pattern) and `deploy/systemd/kis-futures-strategy-daemon.service`.
- async redis: `import redis.asyncio as aioredis; aioredis.from_url(os.environ.get("REDIS_URL","redis://localhost:6379/1"))`. Sync (for watchlist): `redis.Redis.from_url(redis_url, decode_responses=True)` OR reuse `shared.streaming.client.RedisClient.get_client()`.

---

## Task 1: `StockCandidate` serializer

Serialize an orchestrator `Signal` to the stock-native candidate field dict for XADD.

**Files:**
- Create: `services/stock_strategy/__init__.py` (empty), `services/stock_strategy/candidate.py`
- Test: `tests/unit/stock_strategy/__init__.py` (match `tests/unit/decision_engine/` convention — it has `__init__.py`), `tests/unit/stock_strategy/test_candidate.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/stock_strategy/test_candidate.py`:

```python
"""Stock candidate serializer: orchestrator Signal -> stream field dict."""
from __future__ import annotations

import json
from datetime import UTC, datetime

from services.stock_strategy.candidate import stock_signal_to_stream_dict
from shared.models.signal import Signal, SignalType


def test_serializes_all_fields():
    sig = Signal(
        code="005930",
        name="Samsung",
        signal_type=SignalType.ENTRY,
        strategy="williams_r",
        price=71000.0,
        quantity=10,
        confidence=0.62,
        timestamp=datetime(2026, 6, 5, 0, 30, tzinfo=UTC),
        metadata={"signal_direction": "long", "atr": 120.0},
    )
    fields = stock_signal_to_stream_dict(sig, signal_id="abc123")
    assert fields["signal_id"] == "abc123"
    assert fields["code"] == "005930"
    assert fields["name"] == "Samsung"
    assert fields["strategy"] == "williams_r"
    assert fields["direction"] == "long"
    assert fields["price"] == "71000.0"
    assert fields["quantity"] == "10"
    assert fields["confidence"] == "0.62"
    assert fields["generated_at_ms"] == str(int(datetime(2026, 6, 5, 0, 30, tzinfo=UTC).timestamp() * 1000))
    assert json.loads(fields["metadata_json"])["atr"] == 120.0


def test_direction_defaults_to_long_when_absent():
    sig = Signal(code="000660", strategy="pattern_pullback", price=100.0, metadata={})
    fields = stock_signal_to_stream_dict(sig, signal_id="x")
    assert fields["direction"] == "long"


def test_naive_timestamp_treated_as_utc():
    sig = Signal(code="A", price=1.0, timestamp=datetime(2026, 6, 5, 0, 0))  # naive
    fields = stock_signal_to_stream_dict(sig, signal_id="x")
    assert fields["generated_at_ms"]  # non-empty, no crash
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/unit/stock_strategy/test_candidate.py -v`
Expected: FAIL — module `services.stock_strategy.candidate` does not exist.

- [ ] **Step 3: Implement the serializer**

Create `services/stock_strategy/candidate.py`:

```python
"""Stock-native candidate serializer for signal.candidate.stock.

The orchestrator Signal (shared.models.signal.Signal) has no to_stream_dict;
stock has no entry-time stop/target (the three_stage exit owns stops), so the
futures 11-field decision schema is not reused. This emits a stock-native dict.
"""
from __future__ import annotations

import json
from datetime import UTC

from shared.models.signal import Signal


def stock_signal_to_stream_dict(signal: Signal, *, signal_id: str) -> dict[str, str]:
    """Flatten an orchestrator Signal into Redis XADD fields (all str)."""
    ts = signal.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    generated_ms = str(int(ts.timestamp() * 1000))
    metadata = signal.metadata if isinstance(signal.metadata, dict) else {}
    direction = str(metadata.get("signal_direction") or metadata.get("direction") or "long")
    return {
        "signal_id": signal_id,
        "code": signal.code,
        "name": signal.name,
        "strategy": signal.strategy,
        "direction": direction,
        "price": str(signal.price),
        "quantity": str(signal.quantity),
        "confidence": str(signal.confidence),
        "generated_at_ms": generated_ms,
        "metadata_json": json.dumps(metadata, ensure_ascii=False, default=str),
    }
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/unit/stock_strategy/test_candidate.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add services/stock_strategy/__init__.py services/stock_strategy/candidate.py tests/unit/stock_strategy/
git commit -m "feat: stock candidate serializer (orchestrator Signal -> stream dict)"
```

---

## Task 2: Universe parser

Parse the daily-watchlist JSON into a capped code list (mirror the orchestrator's `_load_static_watchlist` parse).

**Files:**
- Create: `services/stock_strategy/universe.py`
- Test: `tests/unit/stock_strategy/test_universe.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/stock_strategy/test_universe.py`:

```python
"""Parse system:daily_watchlist:latest JSON -> capped code list."""
from __future__ import annotations

import json

from services.stock_strategy.universe import parse_watchlist_codes


def test_unions_codes_across_strategies():
    payload = json.dumps(
        {"strategies": {"williams_r": ["005930", "000660"], "pattern_pullback": ["000660", "035720"]}}
    )
    codes = parse_watchlist_codes(payload, max_symbols=40)
    assert set(codes) == {"005930", "000660", "035720"}


def test_caps_at_max_symbols():
    payload = json.dumps({"strategies": {"s": [f"{i:06d}" for i in range(50)]}})
    codes = parse_watchlist_codes(payload, max_symbols=40)
    assert len(codes) == 40


def test_none_or_malformed_returns_empty():
    assert parse_watchlist_codes(None, max_symbols=40) == []
    assert parse_watchlist_codes("not json", max_symbols=40) == []
    assert parse_watchlist_codes(json.dumps({"strategies": {}}), max_symbols=40) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/unit/stock_strategy/test_universe.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the parser**

Create `services/stock_strategy/universe.py`:

```python
"""Stock universe parsing from the daily-watchlist Redis payload.

Mirrors the orchestrator's _load_static_watchlist parse: union the code lists
under payload["strategies"], stripped + de-duplicated, capped at max_symbols.
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def parse_watchlist_codes(raw: Any, *, max_symbols: int) -> list[str]:
    """Parse the watchlist JSON string into a capped, ordered code list.

    Returns [] on None / malformed / empty (caller keeps the prior universe).
    """
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        logger.warning("watchlist payload is not valid JSON; keeping prior universe")
        return []
    strategies = payload.get("strategies", {}) if isinstance(payload, dict) else {}
    seen: dict[str, None] = {}  # ordered de-dup
    for strat_codes in strategies.values():
        if isinstance(strat_codes, list):
            for c in strat_codes:
                code = str(c).strip()
                if code:
                    seen.setdefault(code, None)
    return list(seen)[:max_symbols]
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/unit/stock_strategy/test_universe.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add services/stock_strategy/universe.py tests/unit/stock_strategy/test_universe.py
git commit -m "feat: stock universe parser (daily-watchlist JSON -> capped codes)"
```

---

## Task 3: `StockStrategyDaemon` (decision loop + universe-refresh loop)

The core: own the engine + feed + manager + resolver; refresh the universe; on a cadence, build an `EntryContext` per warm symbol and publish candidates.

**Files:**
- Create: `services/stock_strategy/daemon.py`
- Test: `tests/unit/stock_strategy/test_daemon.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/stock_strategy/test_daemon.py`:

```python
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
    def collect_entry_indicators(self, symbol):
        return {"rsi": 30.0, "atr": 100.0}


class _FakeFeed:
    def __init__(self):
        self.symbols = []

    def update_symbols(self, codes):
        self.symbols = list(codes)

    async def get_current_price(self, symbol):
        return {"code": symbol, "close": 71000.0, "timestamp": 1.0}


class _FakeManager:
    def __init__(self, fire_for=("005930",)):
        self._fire = set(fire_for)

    async def check_entries(self, context):
        code = context.market_data.get("code")
        if code in self._fire:
            return [Signal(code=code, strategy="williams_r", price=71000.0, confidence=0.6)]
        return []


class _FakeRedis:
    def __init__(self):
        self.added = []

    async def xadd(self, stream, fields, **kw):
        self.added.append((stream, fields))

    async def expire(self, *a, **k):
        return True


def _daemon(**kw):
    defaults = dict(
        redis=_FakeRedis(),
        feed=_FakeFeed(),
        engine=_FakeEngine(),
        resolver=_FakeResolver(),
        manager=_FakeManager(),
        candidate_stream="signal.candidate.stock.shadow",
        candidate_maxlen=10_000,
        now_fn=lambda: datetime(2026, 6, 5, 0, 30, tzinfo=UTC),
    )
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
            return [Signal(code=context.market_data.get("code"), strategy="s", price=1.0)]

    redis = _FakeRedis()
    d = _daemon(redis=redis, manager=_BoomManager(), engine=_FakeEngine(warm=("005930", "000660")))
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/unit/stock_strategy/test_daemon.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the daemon**

Create `services/stock_strategy/daemon.py`:

```python
"""StockStrategyDaemon — stock entry-candidate producer (shadow-first).

Owns a daemon-local indicator engine fed by market:ticks (StreamConsumerFeed),
a dynamic screener universe, and the existing StrategyManager. On a decision
cadence it builds an EntryContext per warm symbol and publishes the resulting
orchestrator Signals to signal.candidate.stock(.shadow).
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

from services.stock_strategy.candidate import stock_signal_to_stream_dict
from services.stock_strategy.universe import parse_watchlist_codes
from shared.strategy.base import EntryContext

logger = logging.getLogger(__name__)

_STREAM_TTL_SECONDS = 86400


class StockStrategyDaemon:
    def __init__(
        self,
        *,
        redis: Any,
        feed: Any,
        engine: Any,
        resolver: Any,
        manager: Any,
        candidate_stream: str,
        candidate_maxlen: int,
        now_fn: Callable[[], datetime],
        eval_interval_seconds: float = 60.0,
        universe_refresh_seconds: float = 30.0,
        max_symbols: int = 40,
        watchlist_reader: Callable[[], Any] | None = None,
    ) -> None:
        self.redis = redis
        self.feed = feed
        self.engine = engine
        self.resolver = resolver
        self.manager = manager
        self.candidate_stream = candidate_stream
        self.candidate_maxlen = candidate_maxlen
        self._now_fn = now_fn
        self._eval_interval = eval_interval_seconds
        self._universe_refresh = universe_refresh_seconds
        self._max_symbols = max_symbols
        self._watchlist_reader = watchlist_reader
        self._universe: list[str] = []
        self._stop = asyncio.Event()

    def _apply_watchlist(self, raw: Any) -> None:
        codes = parse_watchlist_codes(raw, max_symbols=self._max_symbols)
        if not codes:
            return  # keep prior universe
        self._universe = codes
        self.feed.update_symbols(codes)

    async def evaluate_once(self) -> int:
        """Build context + check_entries per warm symbol; publish. Returns #published."""
        published = 0
        now = self._now_fn()
        for symbol in list(self._universe):
            try:
                if not self.engine.is_warm(symbol):
                    continue
                market_data = await self.feed.get_current_price(symbol)
                if not market_data:
                    continue
                indicators = self.resolver.collect_entry_indicators(symbol)
                ctx = EntryContext(
                    market_data=market_data,
                    indicators=indicators,
                    current_positions=[],
                    timestamp=now,
                    metadata={"shadow": True},
                )
                signals = await self.manager.check_entries(ctx)
                for sig in signals or []:
                    await self._publish(sig)
                    published += 1
            except Exception:
                logger.exception("stock entry eval failed symbol=%s", symbol)
        return published

    async def _publish(self, signal) -> None:
        fields = stock_signal_to_stream_dict(signal, signal_id=uuid.uuid4().hex)
        await self.redis.xadd(
            self.candidate_stream, fields, maxlen=self.candidate_maxlen, approximate=True
        )
        await self.redis.expire(self.candidate_stream, _STREAM_TTL_SECONDS)

    async def _refresh_loop(self) -> None:
        while not self._stop.is_set():
            if self._watchlist_reader is not None:
                try:
                    self._apply_watchlist(self._watchlist_reader())
                except Exception:
                    logger.exception("watchlist refresh failed; keeping prior universe")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._universe_refresh)
            except asyncio.TimeoutError:
                pass

    async def run(self) -> None:
        await self.feed.start()
        refresh_task = asyncio.create_task(self._refresh_loop())
        try:
            while not self._stop.is_set():
                await self.evaluate_once()
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self._eval_interval)
                except asyncio.TimeoutError:
                    pass
        finally:
            refresh_task.cancel()
            await asyncio.gather(refresh_task, return_exceptions=True)
            await self.feed.stop()

    async def stop(self) -> None:
        self._stop.set()
```

- [ ] **Step 4: Run to verify they pass**

Run: `pytest tests/unit/stock_strategy/test_daemon.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add services/stock_strategy/daemon.py tests/unit/stock_strategy/test_daemon.py
git commit -m "feat: StockStrategyDaemon (per-symbol entry eval + universe refresh + publish)"
```

---

## Task 4: Flag-gated entrypoint + warmup + systemd unit

**Files:**
- Create: `services/stock_strategy/main.py`
- Create: `deploy/systemd/kis-stock-strategy-daemon.service`
- Test: `tests/unit/stock_strategy/test_main.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/stock_strategy/test_main.py`:

```python
"""Flag routing for the stock strategy daemon entrypoint."""
from __future__ import annotations

import services.stock_strategy.main as m


def test_resolve_mode_default_off(monkeypatch):
    monkeypatch.delenv("STOCK_STRATEGY_DAEMON", raising=False)
    assert m._resolve_mode() == "off"


def test_resolve_mode_shadow(monkeypatch):
    monkeypatch.setenv("STOCK_STRATEGY_DAEMON", "shadow")
    assert m._resolve_mode() == "shadow"
    assert m._candidate_stream_for("shadow") == "signal.candidate.stock.shadow"
    assert m._candidate_stream_for("off") == "signal.candidate.stock"
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/unit/stock_strategy/test_main.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the entrypoint**

Create `services/stock_strategy/main.py` (mirror `services/decision_engine/main.py`'s flag-gated `_build_and_run` + warmup; reuse the `_warmup_engine_from_parquet` helper pattern — read it from `services/decision_engine/main.py` and copy the equivalent here, using `asset_class="stock"` and `get_minute_bars` tail-slicing as fixed in #414):

```python
"""Stock strategy daemon entrypoint (flag-gated, shadow-first)."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


def _resolve_mode() -> str:
    return os.getenv("STOCK_STRATEGY_DAEMON", "off").strip().lower()


def _candidate_stream_for(mode: str) -> str:
    return (
        "signal.candidate.stock.shadow" if mode == "shadow" else "signal.candidate.stock"
    )


def _warmup_engine_from_parquet(
    engine: Any, store: Any, symbol: str, lookback_minutes: int = 240
) -> None:
    """Seed 1-min candles from the MOST RECENT parquet bars (ASC LIMIT takes the
    head, so fetch + tail — see #414). Best-effort."""
    try:
        df = store.get_minute_bars(symbol)
    except Exception:
        logger.warning("parquet warmup read failed for %s; warming from live ticks", symbol)
        return
    if df is None or len(df) == 0:
        return
    df = df.iloc[-lookback_minutes:]
    candles = [
        {
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "volume": float(r.get("volume", 0) or 0),
        }
        for _, r in df.iterrows()
    ]
    engine.seed_candles(symbol, candles)


async def _build_and_run() -> int:
    import signal as signal_mod

    import redis.asyncio as aioredis

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    redis_client = aioredis.from_url(redis_url)

    mode = _resolve_mode()
    candidate_stream = _candidate_stream_for(mode)

    if mode != "shadow":
        # off: inert. The systemd unit ships disabled; nothing runs.
        logger.info("STOCK_STRATEGY_DAEMON=%s (off) — daemon inert", mode)
        await redis_client.aclose()
        return 0

    from services.stock_strategy.daemon import StockStrategyDaemon
    from services.stock_strategy.universe import parse_watchlist_codes  # noqa: F401 (documented)
    from services.trading.indicator_engine import StreamingIndicatorEngine
    from services.trading.stream_consumer_feed import StreamConsumerFeed
    from shared.indicators.resolver import StreamingIndicatorResolver
    from shared.streaming.client import RedisClient
    from services.trading.strategy_manager import StrategyManager

    engine = StreamingIndicatorEngine()
    manager = StrategyManager(asset_class="stock", indicator_engine=engine)
    manager.set_indicator_engine(engine)
    resolver = StreamingIndicatorResolver(
        engine=engine, required_keys=tuple(manager.required_indicators)
    )
    feed = StreamConsumerFeed(
        redis=redis_client,
        stream=os.environ.get("STOCK_TICK_STREAM", "market:ticks"),
        indicator_engine=engine,
    )

    sync_redis = RedisClient.get_client()
    watchlist_key = os.environ.get("STOCK_WATCHLIST_KEY", "system:daily_watchlist:latest")

    def _watchlist_reader():
        return sync_redis.get(watchlist_key)

    daemon = StockStrategyDaemon(
        redis=redis_client,
        feed=feed,
        engine=engine,
        resolver=resolver,
        manager=manager,
        candidate_stream=candidate_stream,
        candidate_maxlen=10_000,
        now_fn=lambda: datetime.now(UTC),
        max_symbols=int(os.environ.get("STOCK_MAX_SYMBOLS", "40")),
        watchlist_reader=_watchlist_reader,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal_mod.SIGTERM, signal_mod.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    try:
        await daemon.run()
    finally:
        await redis_client.aclose()
    return 0


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    return asyncio.run(_build_and_run())


if __name__ == "__main__":
    import sys

    sys.exit(main())
```

(Implementation note: confirm `RedisClient.get_client()` returns a `decode_responses=True` client so `sync_redis.get(key)` yields a str for `parse_watchlist_codes` — check `shared/streaming/client.py`; if it returns bytes, decode in `_watchlist_reader`. Confirm `StrategyManager.required_indicators` is a property returning `list[str]`.)

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/unit/stock_strategy/test_main.py -v`
Expected: PASS (2 tests). (The shadow `_build_and_run` wiring is integration-tested in Task 5.)

- [ ] **Step 5: Create the disabled systemd unit**

Create `deploy/systemd/kis-stock-strategy-daemon.service`:

```ini
[Unit]
Description=KIS Stock Strategy Daemon (market:ticks -> indicators + strategies -> signal.candidate.stock.shadow)
After=network-online.target redis-server.service
Wants=network-online.target
Requires=redis-server.service

[Service]
Type=simple
User=deploy
WorkingDirectory=/home/deploy/project/kis_unified_sts
EnvironmentFile=/home/deploy/project/kis_unified_sts/.env
Environment=STOCK_STRATEGY_DAEMON=shadow
ExecStart=/home/deploy/project/kis_unified_sts/.venv/bin/python -m services.stock_strategy.main
Restart=on-failure
RestartSec=10s
TimeoutStopSec=30s
KillSignal=SIGTERM

# Delivered DISABLED. Enabling is an operator step (shadow validation gate).
[Install]
WantedBy=multi-user.target
```

- [ ] **Step 6: Commit**

```bash
git add services/stock_strategy/main.py deploy/systemd/kis-stock-strategy-daemon.service tests/unit/stock_strategy/test_main.py
git commit -m "feat: flag-gated stock strategy daemon entrypoint + warmup + disabled systemd unit"
```

---

## Task 5: Integration — market:ticks + watchlist → shadow candidate

**Files:**
- Create: `tests/integration/test_stock_strategy_daemon_shadow.py`

- [ ] **Step 1: Write the test**

Create `tests/integration/test_stock_strategy_daemon_shadow.py` (reuse the fakeredis FakeServer two-client pattern from `tests/integration/test_futures_strategy_daemon_shadow.py` — read it first):

```python
"""Integration: market:ticks + watchlist -> StockStrategyDaemon -> shadow candidate."""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest

from services.stock_strategy.daemon import StockStrategyDaemon
from services.trading.indicator_engine import StreamingIndicatorEngine
from services.trading.stream_consumer_feed import StreamConsumerFeed
from services.trading.strategy_manager import StrategyManager
from shared.indicators.resolver import StreamingIndicatorResolver


@pytest.mark.asyncio
async def test_warm_symbol_produces_shadow_candidate(fake_redis_pair):
    # fake_redis_pair: (ops_client, assert_client) sharing a FakeServer (mirror the
    # futures integration fixture). If none exists, build it inline with
    # fakeredis.aioredis.FakeServer() + two FakeRedis(server=..., db=1).
    redis_ops, redis_assert = fake_redis_pair
    symbol = "005930"
    base = datetime(2026, 6, 5, 0, 0, tzinfo=UTC)

    engine = StreamingIndicatorEngine()
    feed = StreamConsumerFeed(redis=redis_ops, stream="market:ticks", indicator_engine=engine)
    feed.update_symbols([symbol])
    await feed.start()

    # Seed enough 1-min ticks (via the assert client) to warm the engine.
    for i in range(30):
        await redis_assert.xadd(
            "market:ticks",
            {
                "symbol": symbol,
                "code": symbol,
                "close": str(71000.0 + i * 10),
                "high": str(71050.0 + i * 10),
                "low": str(70950.0 + i * 10),
                "volume": "100",
                "timestamp": str((base + timedelta(minutes=i)).timestamp()),
            },
        )
    await asyncio.sleep(0.2)  # drain into the engine
    assert engine.is_warm(symbol), "engine should be warm after 30 one-minute ticks"

    manager = StrategyManager(asset_class="stock", indicator_engine=engine)
    manager.set_indicator_engine(engine)
    resolver = StreamingIndicatorResolver(
        engine=engine, required_keys=tuple(manager.required_indicators)
    )
    daemon = StockStrategyDaemon(
        redis=redis_ops,
        feed=feed,
        engine=engine,
        resolver=resolver,
        manager=manager,
        candidate_stream="signal.candidate.stock.shadow",
        candidate_maxlen=1000,
        now_fn=lambda: base + timedelta(minutes=29),
        watchlist_reader=lambda: json.dumps({"strategies": {"w": [symbol]}}),
    )
    daemon._apply_watchlist(daemon._watchlist_reader())  # set universe
    await daemon.evaluate_once()
    await feed.stop()

    entries = await redis_assert.xrange("signal.candidate.stock.shadow")
    # A candidate is produced IFF an enabled stock strategy fires on this series.
    # If the enabled strategies don't fire on synthetic data, assert the pipeline
    # ran without error and the universe/warm path executed (engine warm + no raise).
    # Prefer tuning the tick series so williams_r/pattern_pullback fires; if that's
    # impractical for synthetic data, assert evaluate_once() returned an int and the
    # engine was warm (pipeline integrity), and leave a NOTE.
    assert isinstance(entries, list)
```

(NOTE for the engineer: enabled stock strategies (`williams_r`, `pattern_pullback`) may not fire on a simple monotonic synthetic series. First TRY to craft a tick series that fires `williams_r` (1-min oversold reversal + volume) and assert a real candidate on the shadow stream. If after reasonable effort no enabled strategy fires on synthetic data, fall back to asserting pipeline integrity — `await daemon.evaluate_once()` runs without error over a warm universe and returns an int — and add a clear NOTE comment that the strategy-firing path is covered by the unit tests with a fake manager. Do NOT assert a tautology silently. Add the `fake_redis_pair` fixture to `tests/conftest.py` if absent, mirroring the futures integration fixture.)

- [ ] **Step 2: Run + iterate**

Run: `pytest tests/integration/test_stock_strategy_daemon_shadow.py -v`
Tune until green + non-flaky (run 2-3×).

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_stock_strategy_daemon_shadow.py tests/conftest.py
git commit -m "test: integration market:ticks + watchlist -> stock strategy daemon -> shadow candidate"
```

---

## Task 6: Full gate + lint + PR

- [ ] **Step 1: Regression**

Run: `pytest tests/unit/stock_strategy/ tests/unit/trading/ -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 2: Lint/format/type**

Run:
```bash
VENV=/home/deploy/project/kis_unified_sts/.venv
$VENV/bin/ruff check services/stock_strategy/ tests/unit/stock_strategy/ tests/integration/test_stock_strategy_daemon_shadow.py
$VENV/bin/black services/stock_strategy/ tests/unit/stock_strategy/ tests/integration/test_stock_strategy_daemon_shadow.py
$VENV/bin/mypy services/stock_strategy/ --ignore-missing-imports --no-error-summary || true
```
Fix ruff/black; amend.

- [ ] **Step 3: Full gate (CI parity)**

Run:
```bash
PYTHONPATH=/tmp/ssd $VENV/bin/pytest tests/ --ignore=tests/performance -n auto -m "not serial" -q -p no:cacheprovider
PYTHONPATH=/tmp/ssd $VENV/bin/pytest tests/ --ignore=tests/performance -m serial -q -p no:cacheprovider
```
Expected: both exit 0.

- [ ] **Step 4: Push + PR**

```bash
git push -u origin feat/stock-strategy-daemon
gh pr create --base main --head feat/stock-strategy-daemon \
  --title "feat(m4-p): stock strategy daemon (producer, shadow-first, default off)" \
  --body "$(cat <<'EOF'
## What
The missing stock signal producer: a shadow-first daemon consuming `market:ticks`
into a daemon-local indicator engine (reuse M1b StreamConsumerFeed), refreshing a
dynamic screener universe (`system:daily_watchlist:latest`), building an
`EntryContext` per warm symbol on a decision cadence, running the existing
`StrategyManager.check_entries`, and publishing a stock-native candidate to
`signal.candidate.stock.shadow`. Default-off (`STOCK_STRATEGY_DAEMON=off`); systemd
unit disabled.

## Why
M4-P — the prerequisite for M4 (stock risk_filter/order_router generalization). The
stock risk/order daemons had no producer. Isolates the stock strategy stage off the
orchestrator loop. Merge is inert (default off); orchestrator stock path unchanged.

## Scope
Producer only. M4-R (risk_filter), M4-O (order_router + ATS), M4-X (three_stage exit
daemon), and cutover are later. Stock-native candidate schema (stock has no
entry-time stop/target). Enabled stock strategies (`williams_r`, `pattern_pullback`)
are self-contained (no adapter-layer LLM/regime gates).

## How tested
Unit (candidate serializer, universe parser, daemon eval/skip/isolation/refresh,
flag routing), integration (market:ticks + watchlist -> shadow candidate), full
`tests/` gate green, ruff/black clean.

Spec: `docs/superpowers/specs/2026-06-05-stock-strategy-daemon-design.md`
Plan: `docs/superpowers/plans/archive/2026-06-05-stock-strategy-daemon.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review (plan vs spec)

- §3/§4 reuse-first daemon (feed + engine + resolver + manager) → Task 3. ✓
- §5 stock-native schema → Task 1. ✓
- §6 dynamic universe + cadence + warm-gating + per-symbol EntryContext → Tasks 2, 3. ✓
- §7 flag off/shadow + disabled unit + separate shadow stream → Task 4. ✓
- §8 fail-safe per-symbol + universe tolerance → Task 3 (`evaluate_once` try/except, `_apply_watchlist` keep-prior). ✓
- §9 testing → Tasks 1-5 + Task 6 full gate. ✓
- §12 acceptance → Tasks 3 (consume/refresh/eval), 1 (serialize+signal_id), 3 (warm-gate/isolation), 4 (inert off + disabled unit). ✓
- **Plan-time confirmations flagged inline** (not placeholders): `RedisClient.get_client()` decode_responses (Task 4 note), `required_indicators` property (Task 4 note), integration strategy-firing vs pipeline-integrity (Task 5 NOTE), `_warmup_engine_from_parquet` copied from #414's fixed version.
- Type/name consistency: `StockStrategyDaemon` / `stock_signal_to_stream_dict` / `parse_watchlist_codes` / `_resolve_mode` / `_candidate_stream_for` / `evaluate_once` / `_apply_watchlist` used identically across tasks. ✓
