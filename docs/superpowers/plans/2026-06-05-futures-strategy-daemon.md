# Futures Strategy Daemon (M2+M3, shadow-first) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make the stubbed futures `decision_engine` emit real shadow signals by supplying a live `context_provider`: consume `raw_data` ticks into a daemon-local indicator engine (reuse M1b `StreamConsumerFeed`), build a `MarketContext` (new `FuturesContextProvider`), run the existing pure `SetupAGapReversion`/`SetupCEventReaction`, and XADD candidates to `signal.candidate.futures.shadow`. Default-off, no live impact.

**Architecture:** Reuse-first. `DecisionEngineDaemon` (timer loop) + `StreamConsumerFeed` (M1b) + Setup A/C (pure) are reused unchanged; the only new units are `FuturesContextProvider` (+ a 15-min range accessor on the indicator engine + a parquet daily reference). The entrypoint becomes flag-gated (`FUTURES_STRATEGY_DAEMON=off|shadow`).

**Tech stack:** Python 3.11, `redis.asyncio`, `StreamingIndicatorEngine`, `ParquetMarketDataStore`, pytest.

**Spec:** `docs/superpowers/specs/2026-06-05-futures-strategy-daemon-design.md`

**Environment:** Work in the worktree `/tmp/fsd` (branch `feat/futures-strategy-daemon`). The worktree has no `.venv`; run tests with:
```bash
cd /tmp/fsd && PYTHONPATH=/tmp/fsd /home/deploy/project/kis_unified_sts/.venv/bin/pytest <args> -p no:cacheprovider
```
Never touch the operator's main checkout or running services.

**Key verbatim facts the engineer needs:**
- `DecisionEngineDaemon(*, redis, setups, context_provider, candidate_stream, candidate_maxlen, tick_interval_seconds)` — loop: `ctx = await context_provider()`; if `None` sleep; else for each setup `setup.check(ctx)` → `_publish(signal)` (XADD `signal.to_stream_dict()` + `signal_id=uuid4().hex`, maxlen approximate, expire 86400s). UNCHANGED. (`services/decision_engine/main.py`)
- `MarketContext` fields (`shared/decision/context.py`): `now`(KST), `symbol`, `current_price`, `prev_close`, `today_open`, `vwap`, `atr_14`, `atr_90th_percentile`, `last_15min_high`, `last_15min_low`, `current_spread_ticks`, `macro_overnight`(MacroSnapshot|None), `scheduled_events`(list[ScheduledEvent]). Setups use only: `now`/`minutes_since_open`, `macro_overnight.sp500_change_pct`, `prev_close`, `today_open`, `current_price`, `atr_14`, `last_15min_high`, `last_15min_low`, `scheduled_events`. `vwap`/`atr_90th_percentile`/`current_spread_ticks` UNUSED → default.
- `StreamConsumerFeed(*, redis, stream, indicator_engine=None, tick_callback=None, stale_threshold_seconds=30.0, xread_block_ms=1000, xread_count=200)` — `start()`/`stop()`; pushes each tick to `indicator_engine.on_tick`. (M1b, `services/trading/stream_consumer_feed.py`)
- `StreamingIndicatorEngine(bb_period=20, bb_std=2.0, rsi_period=14, high_period=5, staleness_seconds=180.0, ema_periods=None, mtf_timeframes=None, mtf_maxlen=250, mtf_warmth_timeframe=None)`; `get_indicators(symbol)` returns dict incl. `result["atr"]`; `is_warm(symbol)`; `seed_candles(...)`; per-symbol `CandleAccumulator` (1-min `Candle` deque with `.high/.low/.open/.close`). (`services/trading/indicator_engine.py`)
- `read_latest_macro_snapshot(redis_client, stream, *, scan=200)` → `MacroSnapshot | None` with `.sp500_change_pct`; default stream `stream:macro.overnight`. (`shared/macro/base.py`, `shared/macro/config.py`)
- `load_scheduled_events(path)` → `list[ScheduledEvent]`; `config/scheduled_events.yaml` EXISTS.
- `ParquetMarketDataStore.get_daily_bars(symbol, start=None, end=None, limit=None)` → pandas DataFrame of daily bars (`shared/storage/market_data_store.py`); factory at line 399 (`ParquetMarketDataStore(market_config.parquet.root, asset_class="futures")`).
- risk_filter parse `_signal_from_stream_fields` reads exactly the 11 fields (`services/risk_filter/main.py:35-68`).
- async redis idiom: `import redis.asyncio as aioredis; aioredis.from_url(os.environ.get("REDIS_URL","redis://localhost:6379/1"))`.
- systemd template: `deploy/systemd/kis-risk-filter.service`.

---

## Task 1: 15-minute range accessor on the indicator engine

Setup C needs `last_15min_high`/`last_15min_low`. Nothing populates them today (orchestrator defaults to current_price → Setup C dormant). Add a public accessor computing them from the 1-min candle history.

**Files:**
- Modify: `services/trading/indicator_engine.py` (add method to `StreamingIndicatorEngine`)
- Test: `tests/unit/trading/test_indicator_15min_range.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/trading/test_indicator_15min_range.py`:

```python
"""15-minute high/low accessor for Setup C breakout."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from services.trading.indicator_engine import StreamingIndicatorEngine


def _feed_minute(engine, symbol, minute_idx, high, low, close):
    # one tick per minute; CandleAccumulator buckets by minute
    ts = datetime(2026, 6, 5, 9, 0, tzinfo=UTC) + timedelta(minutes=minute_idx)
    engine.on_tick(symbol, {"high": high, "low": low, "close": close, "volume": 1}, ts)


def test_recent_range_returns_max_high_min_low_over_window():
    eng = StreamingIndicatorEngine()
    # 20 one-minute candles; the last 15 span minutes 5..19
    for i in range(20):
        _feed_minute(eng, "A05", i, high=100 + i, low=50 + i, close=75 + i)
    rng = eng.get_recent_range("A05", minutes=15)
    assert rng is not None
    hi, lo = rng
    # last 15 closed candles → highs 105..119 (max 119-ish), lows 55..69 (min ~55)
    assert hi >= 118 and lo <= 56


def test_recent_range_none_when_no_candles():
    eng = StreamingIndicatorEngine()
    assert eng.get_recent_range("UNKNOWN", minutes=15) is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/unit/trading/test_indicator_15min_range.py -v`
Expected: FAIL — `AttributeError: 'StreamingIndicatorEngine' object has no attribute 'get_recent_range'`.

- [ ] **Step 3: Inspect the candle accumulator to use the real API**

Read `services/trading/indicator_engine.py` around `class CandleAccumulator` (line ~54) and `self._accumulators` (line ~254). Identify how to read the deque of completed `Candle` objects for a symbol (e.g. `self._accumulators[symbol]` and its candle deque attribute, plus how `get_indicator_features` reads `candles = ...`). Use that exact accessor in Step 4 (do not guess the attribute name — copy it from `get_indicator_features`'s candle-list retrieval).

- [ ] **Step 4: Implement `get_recent_range`**

Add to `StreamingIndicatorEngine` (mirror how `get_indicator_features` obtains `candles`):

```python
    def get_recent_range(
        self, symbol: str, minutes: int = 15
    ) -> tuple[float, float] | None:
        """Return (high, low) over the last ``minutes`` completed 1-min candles.

        Used for Setup C's 15-minute breakout range. Returns ``None`` when the
        symbol has no candle history yet.
        """
        candles = self._completed_candles(symbol)  # SAME accessor get_indicator_features uses
        if not candles:
            return None
        window = candles[-minutes:]
        return (max(c.high for c in window), min(c.low for c in window))
```

If a private accessor like `_completed_candles` does not already exist, replace that line with the exact in-line retrieval `get_indicator_features` uses (Step 3) — e.g. `acc = self._accumulators.get(symbol); candles = list(acc.candles) if acc else []`.

- [ ] **Step 5: Run to verify it passes**

Run: `pytest tests/unit/trading/test_indicator_15min_range.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add services/trading/indicator_engine.py tests/unit/trading/test_indicator_15min_range.py
git commit -m "feat: StreamingIndicatorEngine.get_recent_range (15-min high/low for Setup C)"
```

---

## Task 2: Parquet daily reference (prev_close / today_open)

The daemon has no `MarketDataProvider`. Provide `prev_close` (yesterday's daily close) from parquet and track `today_open` (open of today's first observed 1-min candle).

**Files:**
- Create: `services/decision_engine/daily_reference.py`
- Test: `tests/unit/decision_engine/test_daily_reference.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/decision_engine/test_daily_reference.py`:

```python
"""FuturesDailyReference — prev_close from parquet + today_open tracking."""
from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from services.decision_engine.daily_reference import FuturesDailyReference


class _FakeStore:
    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df

    def get_daily_bars(self, symbol, start=None, end=None, limit=None):
        return self._df


def test_prev_close_is_last_daily_close_before_today():
    df = pd.DataFrame(
        {"date": ["2026-06-03", "2026-06-04"], "close": [340.0, 351.5], "open": [338.0, 349.0]}
    )
    ref = FuturesDailyReference(store=_FakeStore(df), symbol="A05")
    assert ref.prev_close() == 351.5  # most recent daily close


def test_today_open_tracks_first_observed_price_of_day():
    ref = FuturesDailyReference(store=_FakeStore(pd.DataFrame()), symbol="A05")
    now = datetime(2026, 6, 5, 9, 0, tzinfo=UTC)
    ref.observe(price=352.0, now=now)
    ref.observe(price=353.0, now=now)  # later same day → today_open unchanged
    assert ref.today_open() == 352.0


def test_prev_close_zero_when_no_daily_bars():
    ref = FuturesDailyReference(store=_FakeStore(pd.DataFrame()), symbol="A05")
    assert ref.prev_close() == 0.0  # Setup A self-guards on prev_close<=0
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/unit/decision_engine/test_daily_reference.py -v`
Expected: FAIL — module `services.decision_engine.daily_reference` does not exist. (Create `tests/unit/decision_engine/__init__.py` if the package dir is new — check first; the repo uses namespace packages so it may not be needed.)

- [ ] **Step 3: Implement `FuturesDailyReference`**

Create `services/decision_engine/daily_reference.py`:

```python
"""Daily reference (prev_close / today_open) for the futures strategy daemon.

The daemon has no MarketDataProvider; prev_close comes from the parquet daily
bars and today_open is captured from the first observed price of the session.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any


class FuturesDailyReference:
    """Provide prev_close (parquet) + today_open (first observed tick)."""

    def __init__(self, *, store: Any, symbol: str) -> None:
        self._store = store
        self._symbol = symbol
        self._today_open: float | None = None
        self._today: date | None = None

    def prev_close(self) -> float:
        """Most recent daily close from parquet, or 0.0 if unavailable."""
        try:
            df = self._store.get_daily_bars(self._symbol, limit=2)
        except Exception:
            return 0.0
        if df is None or len(df) == 0 or "close" not in df.columns:
            return 0.0
        try:
            return float(df["close"].iloc[-1])
        except (TypeError, ValueError, IndexError):
            return 0.0

    def observe(self, *, price: float, now: datetime) -> None:
        """Record the session's first price as today_open (resets daily)."""
        d = now.date()
        if self._today != d:
            self._today = d
            self._today_open = price

    def today_open(self) -> float:
        """Today's session open (0.0 before the first observe())."""
        return self._today_open if self._today_open is not None else 0.0
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/unit/decision_engine/test_daily_reference.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add services/decision_engine/daily_reference.py tests/unit/decision_engine/test_daily_reference.py
git commit -m "feat: FuturesDailyReference (prev_close from parquet + today_open tracking)"
```

---

## Task 3: `FuturesContextProvider` (the core new unit)

Builds a `MarketContext` each poll from: daemon-local indicator engine + `FuturesDailyReference` + macro (Redis) + scheduled events (YAML). Returns `None` until the engine is warm.

**Files:**
- Create: `services/decision_engine/context_provider.py`
- Test: `tests/unit/decision_engine/test_context_provider.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/decision_engine/test_context_provider.py`:

```python
"""FuturesContextProvider — builds MarketContext from engine + macro + events."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from services.decision_engine.context_provider import FuturesContextProvider
from shared.decision.context import MarketContext, ScheduledEvent


class _FakeEngine:
    def __init__(self, *, warm=True, atr=2.0, price=352.0, rng=(360.0, 340.0)):
        self._warm, self._atr, self._price, self._rng = warm, atr, price, rng

    def is_warm(self, symbol):
        return self._warm

    def get_indicators(self, symbol):
        return {"close": self._price, "atr": self._atr}

    def get_recent_range(self, symbol, minutes=15):
        return self._rng


class _FakeDailyRef:
    def __init__(self):
        self.observed = []

    def prev_close(self):
        return 350.0

    def today_open(self):
        return 351.0

    def observe(self, *, price, now):
        self.observed.append((price, now))


class _Macro:
    sp500_change_pct = 0.8


@pytest.mark.asyncio
async def test_builds_market_context_when_warm():
    ev = [ScheduledEvent("e1", "FOMC", datetime(2026, 6, 5, 9, 5, tzinfo=UTC), 1)]
    p = FuturesContextProvider(
        engine=_FakeEngine(),
        daily_ref=_FakeDailyRef(),
        symbol="A05",
        macro_reader=lambda: _Macro(),
        events_provider=lambda: ev,
        now_fn=lambda: datetime(2026, 6, 5, 9, 10, tzinfo=UTC),
    )
    ctx = await p()
    assert isinstance(ctx, MarketContext)
    assert ctx.symbol == "A05"
    assert ctx.current_price == 352.0
    assert ctx.atr_14 == 2.0
    assert ctx.prev_close == 350.0 and ctx.today_open == 351.0
    assert ctx.last_15min_high == 360.0 and ctx.last_15min_low == 340.0
    assert ctx.macro_overnight.sp500_change_pct == 0.8
    assert ctx.scheduled_events == ev
    # unused fields defaulted, not crashing
    assert ctx.current_spread_ticks == 0.0


@pytest.mark.asyncio
async def test_returns_none_until_warm():
    p = FuturesContextProvider(
        engine=_FakeEngine(warm=False),
        daily_ref=_FakeDailyRef(),
        symbol="A05",
        macro_reader=lambda: None,
        events_provider=lambda: [],
        now_fn=lambda: datetime(2026, 6, 5, 9, 10, tzinfo=UTC),
    )
    assert await p() is None


@pytest.mark.asyncio
async def test_observes_price_for_today_open():
    ref = _FakeDailyRef()
    p = FuturesContextProvider(
        engine=_FakeEngine(price=352.0),
        daily_ref=ref,
        symbol="A05",
        macro_reader=lambda: None,
        events_provider=lambda: [],
        now_fn=lambda: datetime(2026, 6, 5, 9, 10, tzinfo=UTC),
    )
    await p()
    assert ref.observed and ref.observed[0][0] == 352.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/unit/decision_engine/test_context_provider.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `FuturesContextProvider`**

Create `services/decision_engine/context_provider.py`:

```python
"""FuturesContextProvider — the live MarketContext builder (replaces the stub).

Mirrors the field sources of shared/strategy/entry/setup_adapters._build_market_context
but pulls from a daemon-local indicator engine + parquet daily reference + Redis
macro + scheduled-events YAML (the inputs the Task-17 stub never supplied).
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from shared.decision.context import MarketContext, ScheduledEvent

logger = logging.getLogger(__name__)

_KST = ZoneInfo("Asia/Seoul")


class FuturesContextProvider:
    """Async callable returning a MarketContext (or None until warm)."""

    def __init__(
        self,
        *,
        engine: Any,
        daily_ref: Any,
        symbol: str,
        macro_reader: Callable[[], Any | None],
        events_provider: Callable[[], list[ScheduledEvent]],
        now_fn: Callable[[], datetime],
    ) -> None:
        self._engine = engine
        self._daily_ref = daily_ref
        self._symbol = symbol
        self._macro_reader = macro_reader
        self._events_provider = events_provider
        self._now_fn = now_fn

    async def __call__(self) -> MarketContext | None:
        symbol = self._symbol
        if not self._engine.is_warm(symbol):
            return None

        ind = self._engine.get_indicators(symbol) or {}
        current_price = float(ind.get("close", 0.0) or 0.0)
        if current_price <= 0.0:
            return None
        atr_14 = float(ind.get("atr", 0.0) or 0.0)

        now = self._now_fn()
        now_kst = now.astimezone(_KST) if now.tzinfo else now.replace(tzinfo=_KST)

        self._daily_ref.observe(price=current_price, now=now_kst)
        prev_close = float(self._daily_ref.prev_close())
        today_open = float(self._daily_ref.today_open())

        rng = self._engine.get_recent_range(symbol, minutes=15)
        last_15min_high, last_15min_low = rng if rng else (current_price, current_price)

        try:
            macro = self._macro_reader()
        except Exception:
            logger.exception("macro_reader failed; treating as no macro")
            macro = None
        try:
            events = self._events_provider()
        except Exception:
            logger.exception("events_provider failed; treating as no events")
            events = []

        return MarketContext(
            now=now_kst,
            symbol=symbol,
            current_price=current_price,
            prev_close=prev_close,
            today_open=today_open,
            vwap=0.0,  # unused by Setup A/C
            atr_14=atr_14,
            atr_90th_percentile=0.0,  # unused
            last_15min_high=float(last_15min_high),
            last_15min_low=float(last_15min_low),
            current_spread_ticks=0.0,  # unused; no orderbook in raw_data
            macro_overnight=macro,
            scheduled_events=list(events),
        )
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/unit/decision_engine/test_context_provider.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add services/decision_engine/context_provider.py tests/unit/decision_engine/test_context_provider.py
git commit -m "feat: FuturesContextProvider (live MarketContext from engine+macro+events)"
```

---

## Task 4: Flag-gated entrypoint wiring + candidate→risk_filter contract test

Make `_build_and_run` flag-aware: `off`/unset keeps the inert stub; `shadow` wires the indicator engine + `StreamConsumerFeed(raw_data)` + parquet warmup + `FuturesContextProvider`, publishing to `signal.candidate.futures.shadow`.

**Files:**
- Modify: `services/decision_engine/main.py`
- Test: `tests/unit/decision_engine/test_shadow_wiring.py`, `tests/unit/decision_engine/test_candidate_contract.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/decision_engine/test_candidate_contract.py` (locks the 11-field round-trip with risk_filter):

```python
"""A provider-built context → setup → candidate must parse in risk_filter."""
from __future__ import annotations

from datetime import UTC, datetime

from services.risk_filter.main import _signal_from_stream_fields
from shared.decision.context import MarketContext
from shared.decision.setups.gap_reversion import SetupAGapReversion


class _Macro:
    sp500_change_pct = 1.0


def test_setup_a_candidate_roundtrips_through_risk_filter_parser():
    # Build a context that makes Setup A fire (gap up + retrace in band)
    ctx = MarketContext(
        now=datetime(2026, 6, 5, 9, 30, tzinfo=UTC).astimezone(),
        symbol="A05",
        current_price=103.0,
        prev_close=100.0,
        today_open=105.0,  # +5% gap up
        vwap=0.0,
        atr_14=1.0,
        atr_90th_percentile=0.0,
        last_15min_high=0.0,
        last_15min_low=0.0,
        current_spread_ticks=0.0,
        macro_overnight=_Macro(),
        scheduled_events=[],
    )
    sig = SetupAGapReversion().check(ctx)
    assert sig is not None
    fields = sig.to_stream_dict()
    fields["signal_id"] = "deadbeef"
    # encode like Redis (bytes keys/values) then parse back
    encoded = {k.encode(): str(v).encode() for k, v in fields.items()}
    signal_id, parsed = _signal_from_stream_fields(encoded)
    assert signal_id == "deadbeef"
    assert parsed.setup_type == "A_gap_reversion"
    assert parsed.direction == sig.direction
    assert parsed.entry_price == sig.entry_price
```

Create `tests/unit/decision_engine/test_shadow_wiring.py`:

```python
"""Flag routing for the futures strategy daemon entrypoint."""
from __future__ import annotations

import services.decision_engine.main as dem


def test_resolve_candidate_stream_default_is_live_inert(monkeypatch):
    monkeypatch.delenv("FUTURES_STRATEGY_DAEMON", raising=False)
    assert dem._resolve_mode() == "off"


def test_resolve_candidate_stream_shadow(monkeypatch):
    monkeypatch.setenv("FUTURES_STRATEGY_DAEMON", "shadow")
    assert dem._resolve_mode() == "shadow"
    assert dem._candidate_stream_for("shadow") == "signal.candidate.futures.shadow"
    assert dem._candidate_stream_for("off") == "stream:signal.candidate"
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/unit/decision_engine/test_candidate_contract.py tests/unit/decision_engine/test_shadow_wiring.py -v`
Expected: contract test PASS already (pure setup + parser exist); wiring test FAIL — `_resolve_mode`/`_candidate_stream_for` don't exist. (If the gap-up math doesn't fire Setup A, adjust today_open/current_price so `retrace ∈ [0.30, 0.70]` of the default `SetupAConfig` — gap = 5, retrace = (105-103)/5 = 0.4 ✓.)

- [ ] **Step 3: Add the flag helpers + flag-aware `_build_and_run`**

In `services/decision_engine/main.py`, add module-level helpers (after the imports):

```python
def _resolve_mode() -> str:
    import os

    return os.getenv("FUTURES_STRATEGY_DAEMON", "off").strip().lower()


def _candidate_stream_for(mode: str) -> str:
    # shadow → separate stream (not consumed by risk_filter); off/live → real stream
    return (
        "signal.candidate.futures.shadow"
        if mode == "shadow"
        else "stream:signal.candidate"
    )
```

Then refactor `_build_and_run` to branch on the mode. Replace the body of `_build_and_run` (keep the stub branch intact for `off`):

```python
async def _build_and_run() -> int:
    import os
    import signal as signal_mod

    import redis.asyncio as aioredis

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
    redis_client = aioredis.from_url(redis_url)

    from shared.decision.setups.event_reaction import SetupCEventReaction
    from shared.decision.setups.gap_reversion import SetupAGapReversion

    setups = [SetupAGapReversion(), SetupCEventReaction()]
    mode = _resolve_mode()
    candidate_stream = _candidate_stream_for(mode)

    feed = None
    if mode == "shadow":
        context_provider, feed = await _build_shadow_context_provider(redis_client)
    else:
        async def _stub_context_provider():
            return None

        context_provider = _stub_context_provider

    daemon = DecisionEngineDaemon(
        redis=redis_client,
        setups=setups,
        context_provider=context_provider,
        candidate_stream=candidate_stream,
        candidate_maxlen=10_000,
        tick_interval_seconds=60.0,
    )

    loop = asyncio.get_running_loop()
    for sig in (signal_mod.SIGTERM, signal_mod.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    try:
        await daemon.run()
    finally:
        if feed is not None:
            await feed.stop()
        await redis_client.aclose()
    return 0
```

Add the shadow-wiring builder (new function in the same module):

```python
async def _build_shadow_context_provider(redis_client):
    """Wire indicator engine + StreamConsumerFeed(raw_data) + provider.

    Returns (context_provider, feed). The feed must be stopped on shutdown.
    """
    import os
    from datetime import UTC, datetime

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")

    from services.decision_engine.context_provider import FuturesContextProvider
    from services.decision_engine.daily_reference import FuturesDailyReference
    from services.trading.indicator_engine import StreamingIndicatorEngine
    from services.trading.stream_consumer_feed import StreamConsumerFeed
    from shared.decision.context import load_scheduled_events
    from shared.macro.base import read_latest_macro_snapshot
    from shared.storage.market_data_store import ParquetMarketDataStore
    from shared.storage.config import MarketDataConfig  # confirm exact import in plan-time

    symbol = os.environ.get("FUTURES_STRATEGY_SYMBOL", "").strip()
    if not symbol:
        # Reuse the orchestrator/ingest front-month resolution if available;
        # otherwise the operator sets FUTURES_STRATEGY_SYMBOL explicitly.
        raise RuntimeError("FUTURES_STRATEGY_SYMBOL must be set for shadow mode")

    engine = StreamingIndicatorEngine()

    # Cold-start warmup: seed 1-min bars from parquet (best-effort).
    store = ParquetMarketDataStore(
        MarketDataConfig.load_or_default().parquet.root, asset_class="futures"
    )
    _warmup_engine_from_parquet(engine, store, symbol)  # plan Task 6 helper

    feed = StreamConsumerFeed(
        redis=redis_client,
        stream=os.environ.get("FUTURES_TICK_STREAM", "raw_data"),
        indicator_engine=engine,
    )
    feed.update_symbols([symbol])
    await feed.start()

    daily_ref = FuturesDailyReference(store=store, symbol=symbol)
    macro_stream = os.environ.get("MACRO_OVERNIGHT_STREAM", "stream:macro.overnight")
    events_path = os.environ.get("SCHEDULED_EVENTS_PATH", "config/scheduled_events.yaml")

    # read_latest_macro_snapshot uses a SYNC redis client (xrevrange). Build a
    # dedicated sync client for macro reads (the daemon's main client is async).
    import redis as _redis_sync

    sync_redis = _redis_sync.Redis.from_url(redis_url, decode_responses=False)

    def _macro_reader():
        return read_latest_macro_snapshot(sync_redis, macro_stream)

    def _events_provider():
        try:
            return load_scheduled_events(events_path)
        except Exception:
            return []

    provider = FuturesContextProvider(
        engine=engine,
        daily_ref=daily_ref,
        symbol=symbol,
        macro_reader=_macro_reader,
        events_provider=_events_provider,
        now_fn=lambda: datetime.now(UTC),
    )
    return provider, feed
```

(Implementation note for the engineer: `read_latest_macro_snapshot` uses a **sync** redis client (`xrevrange`). Resolve the sync-vs-async mismatch during implementation — either build a small sync `redis.Redis.from_url` alongside the async one for macro reads, or read the macro stream once per minute via the async client's `xrevrange` and adapt. Pick the simplest; add a focused test for `_macro_reader`. Also confirm the exact `MarketDataConfig`/parquet-root import — grep `shared/storage/config.py` and `market_data_store.py:399`.)

- [ ] **Step 4: Run to verify they pass**

Run: `pytest tests/unit/decision_engine/ -v`
Expected: PASS (contract + wiring helpers green). The full `_build_and_run` is integration-tested in Task 5.

- [ ] **Step 5: Commit**

```bash
git add services/decision_engine/main.py tests/unit/decision_engine/test_shadow_wiring.py tests/unit/decision_engine/test_candidate_contract.py
git commit -m "feat: flag-gated futures strategy daemon entrypoint (off=stub, shadow=real)"
```

---

## Task 5: Integration test — raw_data → shadow candidate

End-to-end with fake redis: XADD futures ticks to `raw_data`, run the wired daemon for a few cycles, assert a candidate lands on `signal.candidate.futures.shadow`.

**Files:**
- Create: `tests/integration/test_futures_strategy_daemon_shadow.py`

- [ ] **Step 1: Write the test**

Create `tests/integration/test_futures_strategy_daemon_shadow.py` (reuse the fakeredis pattern from `tests/integration/test_signal_to_fill_e2e.py` — read it first for the exact fixture):

```python
"""Integration: raw_data ticks -> futures strategy daemon -> shadow candidate."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from services.decision_engine.main import DecisionEngineDaemon
from services.decision_engine.context_provider import FuturesContextProvider
from services.decision_engine.daily_reference import FuturesDailyReference
from services.trading.indicator_engine import StreamingIndicatorEngine
from services.trading.stream_consumer_feed import StreamConsumerFeed
from shared.decision.context import ScheduledEvent
from shared.decision.setups.event_reaction import SetupCEventReaction


class _Macro:
    sp500_change_pct = 1.0


class _Store:
    def get_daily_bars(self, symbol, start=None, end=None, limit=None):
        import pandas as pd
        return pd.DataFrame({"close": [100.0], "open": [100.0]})


@pytest.mark.asyncio
async def test_event_breakout_produces_shadow_candidate(fake_async_redis):
    # fake_async_redis: a fakeredis.aioredis.FakeRedis fixture (define in conftest
    # or reuse the e2e harness). Seed raw_data with a rising breakout series.
    symbol = "A05"
    base = datetime(2026, 6, 5, 9, 0, tzinfo=UTC)
    for i in range(40):
        await fake_async_redis.xadd(
            "raw_data",
            {
                "symbol": symbol,
                "code": symbol,
                "close": str(100.0 + i * 0.5),
                "high": str(100.0 + i * 0.5),
                "low": str(99.0 + i * 0.5),
                "volume": "1",
                "timestamp": str((base + timedelta(minutes=i)).timestamp()),
            },
        )

    engine = StreamingIndicatorEngine()
    feed = StreamConsumerFeed(redis=fake_async_redis, stream="raw_data", indicator_engine=engine)
    feed.update_symbols([symbol])
    await feed.start()
    await asyncio.sleep(0.2)  # let the feed drain the backlog into the engine

    # A tier-1 event 5 min ago so Setup C's window is open
    ev = [ScheduledEvent("e1", "FOMC", base + timedelta(minutes=35), 1)]
    provider = FuturesContextProvider(
        engine=engine,
        daily_ref=FuturesDailyReference(store=_Store(), symbol=symbol),
        symbol=symbol,
        macro_reader=lambda: _Macro(),
        events_provider=lambda: ev,
        now_fn=lambda: base + timedelta(minutes=39),
    )
    daemon = DecisionEngineDaemon(
        redis=fake_async_redis,
        setups=[SetupCEventReaction()],
        context_provider=provider,
        candidate_stream="signal.candidate.futures.shadow",
        candidate_maxlen=1000,
        tick_interval_seconds=0.01,
    )
    task = asyncio.create_task(daemon.run())
    await asyncio.sleep(0.2)
    await daemon.stop()
    await feed.stop()
    await asyncio.gather(task, return_exceptions=True)

    entries = await fake_async_redis.xrange("signal.candidate.futures.shadow")
    assert entries, "expected at least one shadow candidate"
    fields = entries[0][1]
    assert fields[b"setup_type"] == b"C_event_reaction"
    assert b"signal_id" in fields
```

(If no shared `fake_async_redis` fixture exists, add one to `tests/conftest.py` using `fakeredis.aioredis.FakeRedis()`; mirror whatever `test_signal_to_fill_e2e.py` uses. Tune the price series so the last price breaks just above the 15-min high within the `breakout_buffer_atr_mult` window — adjust increments if the assertion is flaky.)

- [ ] **Step 2: Run to verify it passes**

Run: `pytest tests/integration/test_futures_strategy_daemon_shadow.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_futures_strategy_daemon_shadow.py tests/conftest.py
git commit -m "test: integration raw_data -> futures strategy daemon -> shadow candidate"
```

---

## Task 6: Parquet warmup helper, config, systemd unit (disabled)

**Files:**
- Modify: `services/decision_engine/main.py` (add `_warmup_engine_from_parquet`)
- Create: `deploy/systemd/kis-futures-strategy-daemon.service`
- Test: `tests/unit/decision_engine/test_warmup.py`

- [ ] **Step 1: Write the warmup test**

Create `tests/unit/decision_engine/test_warmup.py`:

```python
"""Parquet warmup seeds the engine so it is warm without live ticks."""
from __future__ import annotations

import pandas as pd

from services.decision_engine.main import _warmup_engine_from_parquet
from services.trading.indicator_engine import StreamingIndicatorEngine


class _Store:
    def get_minute_bars(self, symbol, start=None, end=None, limit=None):
        import pandas as pd
        rows = [{"open": 100, "high": 101, "low": 99, "close": 100, "volume": 1} for _ in range(30)]
        return pd.DataFrame(rows)


def test_warmup_seeds_candles_into_engine():
    eng = StreamingIndicatorEngine()
    _warmup_engine_from_parquet(eng, _Store(), "A05")
    # 30 seeded 1-min bars ≥ bb_period(20) → warm
    assert eng.is_warm("A05") is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/unit/decision_engine/test_warmup.py -v`
Expected: FAIL — `_warmup_engine_from_parquet` undefined.

- [ ] **Step 3: Implement the warmup helper**

Confirmed against source: `ParquetMarketDataStore.get_minute_bars(symbol, start=None, end=None, limit=None)` (line 152) returns a DataFrame; `StreamingIndicatorEngine.seed_candles(symbol, candles, minute=None)` (line 407) takes `candles: list[dict]` with `open/high/low/close/volume`. Add to `services/decision_engine/main.py`:

```python
def _warmup_engine_from_parquet(engine, store, symbol: str, lookback_minutes: int = 240) -> None:
    """Seed the engine's 1-min candles from parquet so it is warm at startup.

    Best-effort: on any read error, the engine simply warms from live ticks.
    """
    try:
        df = store.get_minute_bars(symbol, limit=lookback_minutes)
    except Exception:
        logger.warning("parquet warmup read failed for %s; warming from live ticks", symbol)
        return
    if df is None or len(df) == 0:
        return
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/unit/decision_engine/test_warmup.py -v`
Expected: PASS.

- [ ] **Step 5: Create the disabled systemd unit**

Create `deploy/systemd/kis-futures-strategy-daemon.service`:

```ini
[Unit]
Description=KIS Futures Strategy Daemon (raw_data -> indicators + Setup A/C -> signal.candidate.futures.shadow)
After=network-online.target redis-server.service
Wants=network-online.target
Requires=redis-server.service

[Service]
Type=simple
User=deploy
WorkingDirectory=/home/deploy/project/kis_unified_sts
EnvironmentFile=/home/deploy/project/kis_unified_sts/.env
Environment=FUTURES_STRATEGY_DAEMON=shadow
ExecStart=/home/deploy/project/kis_unified_sts/.venv/bin/python -m services.decision_engine.main
Restart=on-failure
RestartSec=10s
TimeoutStopSec=30s
KillSignal=SIGTERM

# Delivered DISABLED. Enabling is an operator step (shadow validation gate).
# Do NOT enable while the orchestrator runs futures paper unless intentionally
# shadowing — the shadow stream is separate and not consumed by risk_filter.
[Install]
WantedBy=multi-user.target
```

- [ ] **Step 6: Commit**

```bash
git add services/decision_engine/main.py deploy/systemd/kis-futures-strategy-daemon.service tests/unit/decision_engine/test_warmup.py
git commit -m "feat: parquet warmup helper + disabled systemd unit for futures strategy daemon"
```

---

## Task 7: Full suite green + lint + PR

- [ ] **Step 1: Regression — decision_engine + trading unchanged when off**

Run: `pytest tests/unit/decision_engine/ tests/unit/trading/ -q -p no:cacheprovider`
Expected: PASS (existing `decision_engine` stub tests green; new tests green).

- [ ] **Step 2: Lint/format/type on touched files**

Run:
```bash
VENV=/home/deploy/project/kis_unified_sts/.venv
$VENV/bin/ruff check services/decision_engine/ services/trading/indicator_engine.py tests/unit/decision_engine/ tests/integration/test_futures_strategy_daemon_shadow.py
$VENV/bin/black services/decision_engine/ services/trading/indicator_engine.py tests/unit/decision_engine/ tests/integration/test_futures_strategy_daemon_shadow.py
$VENV/bin/mypy services/decision_engine/ --ignore-missing-imports || true
```
Fix ruff/black issues; amend commits.

- [ ] **Step 3: Full gate (CI parity)**

Run:
```bash
PYTHONPATH=/tmp/fsd $VENV/bin/pytest tests/ --ignore=tests/performance -n auto -m "not serial" -q -p no:cacheprovider
PYTHONPATH=/tmp/fsd $VENV/bin/pytest tests/ --ignore=tests/performance -m serial -q -p no:cacheprovider
```
Expected: both exit 0 (zero failures).

- [ ] **Step 4: Push + PR**

```bash
git push -u origin feat/futures-strategy-daemon
gh pr create --base main --head feat/futures-strategy-daemon \
  --title "feat: futures strategy daemon (M2+M3, shadow-first, default off)" \
  --body "$(cat <<'EOF'
## What
Supplies the real `context_provider` the stubbed `decision_engine` was missing,
turning it into the futures strategy daemon: `raw_data` ticks → daemon-local
indicator engine (reuse M1b StreamConsumerFeed) → `FuturesContextProvider` builds
`MarketContext` → pure Setup A/C → `signal.candidate.futures.shadow`. Default-off
(`FUTURES_STRATEGY_DAEMON=off`); systemd unit shipped disabled. Completes the
futures pub/sub vertical (ingest → strategy → risk → order) in shadow.

## Why
M2+M3 of the stream-pipeline decoupling: isolate the futures strategy stage off
the orchestrator loop + remove the decision_engine stub. Merge is inert
(default off); orchestrator futures paper path unchanged.

## Scope
Pure Setup A/C only — regime gate + LLM veto/tuning are orchestrator adapter-layer
(absent from the decision setups) and are deferred to a parity increment, along
with cutover. No orderbook needed (setups don't use spread).

## How tested
Unit (FuturesContextProvider, daily reference, 15-min range, flag routing,
candidate↔risk_filter contract), integration (raw_data → shadow candidate),
full `tests/` gate green, ruff/black clean.

Spec: `docs/superpowers/specs/2026-06-05-futures-strategy-daemon-design.md`
Plan: `docs/superpowers/plans/2026-06-05-futures-strategy-daemon.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review (plan vs spec)

- §3/§4 reuse-first (DecisionEngineDaemon + StreamConsumerFeed + new provider) → Tasks 3,4. ✓
- §5 MarketContext fields + defaults → Task 3 (`FuturesContextProvider`), Tasks 1–2 (15-min range, daily ref). ✓
- §6 pure Setup A/C, no regime/LLM → no adapter logic in any task. ✓
- §7 flag `off`(stub)/`shadow`(real) + separate shadow stream + disabled unit → Tasks 4,6. ✓
- §8 error handling: DecisionEngineDaemon taxonomy (unchanged) + fail-safe provider (`None` until warm; macro/events try/except) → Task 3. ✓
- §9 testing: provider unit + setup-parity contract + integration + regression → Tasks 3,4,5,7. ✓
- §12 acceptance: contract round-trip (Task 4), warm-gating (Task 3), inert-off (Task 4 wiring + Task 7 regression), disabled unit (Task 6). ✓
- **Open implementation confirmations flagged inline** (not placeholders — each names the exact source to read): candle accessor (Task 1 Step 3), `ParquetMarketDataStore` minute-read + `seed_candles` shape (Task 6 Step 3), sync-vs-async macro redis (Task 4 Step 3 note), `MarketDataConfig` parquet-root import (Task 4), front-month symbol resolution (env `FUTURES_STRATEGY_SYMBOL`). These are "read X then match" steps with a concrete fallback, per the codebase's own patterns.
- Type/name consistency: `FuturesContextProvider` / `FuturesDailyReference` / `get_recent_range` / `_resolve_mode` / `_candidate_stream_for` / `_build_shadow_context_provider` / `_warmup_engine_from_parquet` used identically across tasks. ✓
