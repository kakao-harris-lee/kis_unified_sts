# Stock Intraday Symbol Prewarm Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Warm the decoupled stock daemon's indicator engine for intraday-added universe symbols (parquet→KIS REST, rate-limit guarded) so LLM/screener event-driven picks become tradeable instead of permanently `is_warm()==False`.

**Architecture:** Extract the orchestrator's proven per-symbol 3-tier prewarm into one shared async helper `shared/streaming/candle_warmup.py::warmup_engine` (parquet minute + REST minute + daily seed). `StockStrategyDaemon` calls it warmth-based on every universe refresh (prewarm any `not is_warm` symbol, capped per cycle). `main.py` wires the helper as the daemon's `prewarm_fn` and uses it for the startup seed too; the orchestrator is refactored to call the shared helper (DRY).

**Tech Stack:** Python 3.12, asyncio, pytest, `StreamingIndicatorEngine`, `ParquetMarketDataStore`, `KisClient`, `ConfigLoader`.

**Branch:** `feat/stock-intraday-prewarm` (already created; spec committed at `docs/superpowers/specs/2026-06-22-stock-intraday-prewarm-design.md`).

## Global Constraints

- Config-driven only: all thresholds/limits in `config/stock_prewarm.yaml`, none hardcoded in code branches.
- KST for any session/trading logic; prewarm timestamps use epoch/UTC date-bounds (tz-agnostic) — do not introduce new KST↔UTC comparisons.
- Redis DB 1; any new Redis keys need TTLs (this plan adds none).
- Paper-only via config; code default conservative, paper YAML enables `rest_enabled`.
- No regression: every prewarm path is best-effort — any failure returns "nothing seeded" and the symbol warms from live ticks exactly as today.
- IP-ban guard: REST only when parquet misses AND `not kis_client.is_rate_limited`; `asyncio.sleep(0.3)` pacing; ≤ `max_prewarm_per_cycle` REST calls per refresh; 5s per-call timeout. REST one-shot, never WS reconnection.
- DRY: orchestrator and daemon share one `warmup_engine`. YAGNI. TDD. Frequent commits.
- Use the venv: run tests with `.venv/bin/pytest`.

## File Structure

- `shared/streaming/candle_warmup.py` (NEW) — `StockPrewarmConfig` dataclass + `warmup_engine()` async helper + `WarmupResult`. One responsibility: warm one symbol from the best available source.
- `config/stock_prewarm.yaml` (NEW) — prewarm config section.
- `services/stock_strategy/daemon.py` (MODIFY) — accept `prewarm_fn`+`max_prewarm_per_cycle`; async `_apply_watchlist`; new `_prewarm_cold()`.
- `services/stock_strategy/main.py` (MODIFY) — build `kis_client`, `prewarm_fn` closure, unify startup seed, pass config-derived knobs.
- `services/trading/orchestrator.py` (MODIFY) — `_prewarm_symbols` per-symbol body delegates to `warmup_engine` (DRY).
- Tests under `tests/unit/streaming/`, `tests/unit/stock_strategy/`, existing orchestrator prewarm tests.

---

### Task 1: `StockPrewarmConfig` + `config/stock_prewarm.yaml`

**Files:**
- Create: `shared/streaming/candle_warmup.py` (config dataclass only in this task)
- Create: `config/stock_prewarm.yaml`
- Test: `tests/unit/streaming/test_candle_warmup_config.py`

**Interfaces:**
- Produces: `StockPrewarmConfig` frozen dataclass with fields `rest_enabled: bool=False`, `parquet_minute_limit: int=120`, `daily_limit: int=252`, `rest_count: int=30`, `min_candles: int=20`, `max_prewarm_per_cycle: int=5`, `minute_lookback_days: int=5`, `daily_lookback_days: int=400`; classmethod `load() -> StockPrewarmConfig` (defaults on any failure), reading `config/stock_prewarm.yaml` section `stock_prewarm`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/streaming/test_candle_warmup_config.py
from shared.streaming.candle_warmup import StockPrewarmConfig


def test_defaults_are_conservative():
    c = StockPrewarmConfig()
    assert c.rest_enabled is False
    assert c.parquet_minute_limit == 120
    assert c.daily_limit == 252
    assert c.rest_count == 30
    assert c.min_candles == 20
    assert c.max_prewarm_per_cycle == 5
    assert c.minute_lookback_days == 5
    assert c.daily_lookback_days == 400


def test_load_returns_defaults_when_section_missing(monkeypatch):
    from shared.config import loader as loader_mod

    monkeypatch.setattr(loader_mod.ConfigLoader, "load", staticmethod(lambda _f: {}))
    c = StockPrewarmConfig.load()
    assert c.rest_enabled is False


def test_load_reads_overrides(monkeypatch):
    from shared.config import loader as loader_mod

    monkeypatch.setattr(
        loader_mod.ConfigLoader,
        "load",
        staticmethod(
            lambda _f: {"stock_prewarm": {"rest_enabled": True, "max_prewarm_per_cycle": 3}}
        ),
    )
    c = StockPrewarmConfig.load()
    assert c.rest_enabled is True
    assert c.max_prewarm_per_cycle == 3
    assert c.daily_limit == 252  # untouched default
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/streaming/test_candle_warmup_config.py -v`
Expected: FAIL with `ModuleNotFoundError`/`ImportError: cannot import name 'StockPrewarmConfig'`.

- [ ] **Step 3: Write minimal implementation**

```python
# shared/streaming/candle_warmup.py
"""Shared per-symbol indicator-engine warmup (parquet → KIS REST + daily seed).

Used by the decoupled stock daemon (intraday universe-add) and the orchestrator
(startup prewarm). Best-effort: any failure seeds nothing and the symbol warms
from live ticks. REST is rate-limit guarded — see StockPrewarmConfig.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_CONFIG_FILE = "stock_prewarm.yaml"
_CONFIG_SECTION = "stock_prewarm"


@dataclass(frozen=True)
class StockPrewarmConfig:
    rest_enabled: bool = False
    parquet_minute_limit: int = 120
    daily_limit: int = 252
    rest_count: int = 30
    min_candles: int = 20
    max_prewarm_per_cycle: int = 5
    minute_lookback_days: int = 5
    daily_lookback_days: int = 400

    @classmethod
    def load(cls) -> "StockPrewarmConfig":
        try:
            from shared.config.loader import ConfigLoader

            raw = ConfigLoader.load(_CONFIG_FILE).get(_CONFIG_SECTION, {})
            return cls(
                rest_enabled=bool(raw.get("rest_enabled", cls.rest_enabled)),
                parquet_minute_limit=int(
                    raw.get("parquet_minute_limit", cls.parquet_minute_limit)
                ),
                daily_limit=int(raw.get("daily_limit", cls.daily_limit)),
                rest_count=int(raw.get("rest_count", cls.rest_count)),
                min_candles=int(raw.get("min_candles", cls.min_candles)),
                max_prewarm_per_cycle=int(
                    raw.get("max_prewarm_per_cycle", cls.max_prewarm_per_cycle)
                ),
                minute_lookback_days=int(
                    raw.get("minute_lookback_days", cls.minute_lookback_days)
                ),
                daily_lookback_days=int(
                    raw.get("daily_lookback_days", cls.daily_lookback_days)
                ),
            )
        except Exception:
            logger.warning("stock_prewarm.yaml load failed; using defaults")
            return cls()
```

```yaml
# config/stock_prewarm.yaml
stock_prewarm:
  rest_enabled: false        # KIS REST minute backfill tier (paper env enables it)
  parquet_minute_limit: 120  # most-recent 1-min bars seeded from parquet
  daily_limit: 252           # ~1y daily bars seeded for daily indicators
  rest_count: 30             # KIS stock minute API returns ~30 for current session
  min_candles: 20            # WARN threshold for under-initialised symbols
  max_prewarm_per_cycle: 5   # bound REST calls per universe refresh
  minute_lookback_days: 5    # parquet minute start-bound window
  daily_lookback_days: 400   # parquet daily start-bound window (covers 252 trading days)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/streaming/test_candle_warmup_config.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add shared/streaming/candle_warmup.py config/stock_prewarm.yaml tests/unit/streaming/test_candle_warmup_config.py
git commit -m "feat(stock-prewarm): StockPrewarmConfig + config/stock_prewarm.yaml"
```

---

### Task 2: `warmup_engine` shared helper (parquet → REST + daily seed, guarded)

**Files:**
- Modify: `shared/streaming/candle_warmup.py` (add `WarmupResult` + `warmup_engine`)
- Test: `tests/unit/streaming/test_candle_warmup.py`

**Interfaces:**
- Consumes: `StockPrewarmConfig` (Task 1). `engine` exposes `is_warm(symbol)->bool`, `seed_candles(symbol, list[dict])`, `seed_daily_candles(symbol, list[dict])`. `store` exposes `get_minute_bars(symbol, start=, limit=)` / `get_daily_bars(symbol, start=, limit=)` returning a pandas-like DataFrame (`len()`, `.iloc[-n:]`, `.iterrows()`, row `["open"/"high"/"low"/"close"/"volume"]`). `kis_client` exposes `is_rate_limited: bool` and `async get_minute_bars(symbol, count) -> list[dict]`.
- Produces: `WarmupResult(minute_seeded: int, daily_seeded: int, source: str)` where `source ∈ {"parquet","rest","none"}`; `async def warmup_engine(engine, symbol, *, store=None, kis_client=None, config=None) -> WarmupResult`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/streaming/test_candle_warmup.py
import pytest

from shared.streaming.candle_warmup import StockPrewarmConfig, warmup_engine


class _Engine:
    def __init__(self, warm=()):
        self._warm = set(warm)
        self.seeded = {}
        self.daily = {}

    def is_warm(self, s):
        return s in self._warm

    def seed_candles(self, s, candles, minute=None):
        self.seeded[s] = candles

    def seed_daily_candles(self, s, candles):
        self.daily[s] = candles


class _Row(dict):
    pass


class _DF:
    """Minimal DataFrame stand-in: list of dict rows."""

    def __init__(self, rows):
        self._rows = rows

    def __len__(self):
        return len(self._rows)

    @property
    def iloc(self):
        outer = self

        class _ILoc:
            def __getitem__(self, sl):
                return _DF(outer._rows[sl])

        return _ILoc()

    def iterrows(self):
        for i, r in enumerate(self._rows):
            yield i, r


def _bars(n, base=100.0):
    return [
        {"open": base, "high": base + 1, "low": base - 1, "close": base, "volume": 10}
        for _ in range(n)
    ]


class _Store:
    def __init__(self, minute=None, daily=None):
        self._minute = minute
        self._daily = daily

    def get_minute_bars(self, s, start=None, limit=None):
        return _DF(self._minute) if self._minute is not None else _DF([])

    def get_daily_bars(self, s, start=None, limit=None):
        return _DF(self._daily) if self._daily is not None else _DF([])


class _Kis:
    def __init__(self, rate_limited=False, rest_bars=None):
        self.is_rate_limited = rate_limited
        self._rest = rest_bars
        self.calls = 0

    async def get_minute_bars(self, s, count=30):
        self.calls += 1
        return list(self._rest or [])


@pytest.mark.asyncio
async def test_parquet_hit_seeds_minute_and_daily_no_rest():
    eng = _Engine()
    kis = _Kis(rest_bars=_bars(30))
    store = _Store(minute=_bars(120), daily=_bars(252))
    cfg = StockPrewarmConfig(rest_enabled=True)
    res = await warmup_engine(eng, "005930", store=store, kis_client=kis, config=cfg)
    assert res.source == "parquet"
    assert res.minute_seeded == 120
    assert res.daily_seeded == 252
    assert kis.calls == 0  # parquet hit → no REST
    assert "005930" in eng.seeded and "005930" in eng.daily


@pytest.mark.asyncio
async def test_parquet_miss_falls_back_to_rest():
    eng = _Engine()
    kis = _Kis(rest_bars=_bars(30))
    store = _Store(minute=[], daily=_bars(252))
    cfg = StockPrewarmConfig(rest_enabled=True)
    res = await warmup_engine(eng, "123456", store=store, kis_client=kis, config=cfg)
    assert res.source == "rest"
    assert res.minute_seeded == 30
    assert kis.calls == 1
    assert eng.daily["123456"]  # daily still seeded from parquet


@pytest.mark.asyncio
async def test_rest_skipped_when_rate_limited():
    eng = _Engine()
    kis = _Kis(rate_limited=True, rest_bars=_bars(30))
    store = _Store(minute=[], daily=[])
    cfg = StockPrewarmConfig(rest_enabled=True)
    res = await warmup_engine(eng, "123456", store=store, kis_client=kis, config=cfg)
    assert res.source == "none"
    assert res.minute_seeded == 0
    assert kis.calls == 0  # rate limited → no REST call (IP-ban guard)


@pytest.mark.asyncio
async def test_rest_skipped_when_disabled():
    eng = _Engine()
    kis = _Kis(rest_bars=_bars(30))
    store = _Store(minute=[], daily=[])
    cfg = StockPrewarmConfig(rest_enabled=False)
    res = await warmup_engine(eng, "123456", store=store, kis_client=kis, config=cfg)
    assert res.source == "none"
    assert kis.calls == 0


@pytest.mark.asyncio
async def test_already_warm_is_noop():
    eng = _Engine(warm=("005930",))
    kis = _Kis(rest_bars=_bars(30))
    store = _Store(minute=_bars(120))
    res = await warmup_engine(
        eng, "005930", store=store, kis_client=kis, config=StockPrewarmConfig()
    )
    assert res.source == "none"
    assert res.minute_seeded == 0
    assert "005930" not in eng.seeded


@pytest.mark.asyncio
async def test_exception_is_best_effort():
    class _Boom:
        def get_minute_bars(self, *a, **k):
            raise RuntimeError("parquet down")

        def get_daily_bars(self, *a, **k):
            raise RuntimeError("parquet down")

    eng = _Engine()
    res = await warmup_engine(
        eng, "x", store=_Boom(), kis_client=None, config=StockPrewarmConfig()
    )
    assert res.source == "none"
    assert res.minute_seeded == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/streaming/test_candle_warmup.py -v`
Expected: FAIL with `ImportError: cannot import name 'warmup_engine'`.

- [ ] **Step 3: Write minimal implementation**

Append to `shared/streaming/candle_warmup.py`:

```python
import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any, NamedTuple


class WarmupResult(NamedTuple):
    minute_seeded: int
    daily_seeded: int
    source: str  # "parquet" | "rest" | "none"


def _df_tail_to_candles(df: Any, tail: int) -> list[dict]:
    """Convert the most-recent ``tail`` rows of a bars DataFrame to seed dicts."""
    if df is None or len(df) == 0:
        return []
    df = df.iloc[-tail:]
    return [
        {
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "volume": float(r.get("volume", 0) or 0),
        }
        for _, r in df.iterrows()
    ]


def _seed_daily(engine: Any, store: Any, symbol: str, cfg: "StockPrewarmConfig") -> int:
    """Best-effort daily-candle seed (for daily RSI/SMA/MACD indicators)."""
    if store is None:
        return 0
    try:
        start = (datetime.now(UTC) - timedelta(days=cfg.daily_lookback_days)).date().isoformat()
        df = store.get_daily_bars(symbol, start=start)
        candles = _df_tail_to_candles(df, cfg.daily_limit)
        if candles:
            engine.seed_daily_candles(symbol, candles)
        return len(candles)
    except Exception:
        logger.warning("daily prewarm read failed for %s", symbol)
        return 0


async def warmup_engine(
    engine: Any,
    symbol: str,
    *,
    store: Any | None = None,
    kis_client: Any | None = None,
    config: "StockPrewarmConfig | None" = None,
) -> WarmupResult:
    """Warm one symbol: parquet minute → KIS REST minute (guarded), plus daily seed.

    Best-effort and idempotent: already-warm symbols and all failures return
    ``WarmupResult(0, 0, "none")`` and the symbol warms from live ticks.
    """
    cfg = config or StockPrewarmConfig()
    try:
        if engine.is_warm(symbol):
            return WarmupResult(0, 0, "none")
    except Exception:
        return WarmupResult(0, 0, "none")

    minute_seeded = 0
    source = "none"

    # Tier 1: parquet minute bars (no rate limit).
    try:
        if store is not None:
            start = (
                datetime.now(UTC) - timedelta(days=cfg.minute_lookback_days)
            ).date().isoformat()
            candles = _df_tail_to_candles(
                store.get_minute_bars(symbol, start=start), cfg.parquet_minute_limit
            )
            if candles:
                engine.seed_candles(symbol, candles)
                minute_seeded = len(candles)
                source = "parquet"
    except Exception:
        logger.warning("parquet minute prewarm failed for %s", symbol)

    # Tier 2: KIS REST minute bars (only on parquet miss; rate-limit guarded).
    if minute_seeded == 0 and cfg.rest_enabled and kis_client is not None:
        try:
            if getattr(kis_client, "is_rate_limited", False):
                logger.debug("prewarm %s: skip KIS REST (rate limited)", symbol)
            else:
                candles = await asyncio.wait_for(
                    kis_client.get_minute_bars(symbol, count=cfg.rest_count),
                    timeout=5.0,
                )
                await asyncio.sleep(0.3)  # rate-limit pacing
                if candles:
                    engine.seed_candles(symbol, list(candles))
                    minute_seeded = len(candles)
                    source = "rest"
        except Exception:
            logger.warning("KIS REST prewarm failed for %s", symbol)

    if 0 < minute_seeded < cfg.min_candles:
        logger.warning(
            "prewarm %s: only %d minute candles (source=%s); under-initialised",
            symbol,
            minute_seeded,
            source,
        )

    daily_seeded = _seed_daily(engine, store, symbol, cfg)
    return WarmupResult(minute_seeded, daily_seeded, source)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/streaming/test_candle_warmup.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add shared/streaming/candle_warmup.py tests/unit/streaming/test_candle_warmup.py
git commit -m "feat(stock-prewarm): warmup_engine shared helper (parquet→REST + daily, guarded)"
```

---

### Task 3: Daemon warmth-based prewarm on universe refresh

**Files:**
- Modify: `services/stock_strategy/daemon.py` (`__init__`, `_apply_watchlist`, new `_prewarm_cold`, `_refresh_loop` await)
- Test: `tests/unit/stock_strategy/test_daemon.py` (append cases)

**Interfaces:**
- Consumes: an injected `prewarm_fn: Callable[[str], Awaitable[Any]]` (one symbol per call) and `max_prewarm_per_cycle: int`.
- Produces: daemon prewarms `not is_warm` universe symbols (≤ cap) each refresh; no behavior change to `evaluate_once`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/unit/stock_strategy/test_daemon.py
import pytest


@pytest.mark.asyncio
async def test_apply_watchlist_prewarms_only_cold_symbols(monkeypatch):
    calls = []

    async def _prewarm(symbol):
        calls.append(symbol)

    # engine warm for 005930 only; universe will add 000660 + 005930
    daemon = _daemon(
        engine=_FakeEngine(warm=("005930",)),
        prewarm_fn=_prewarm,
        max_prewarm_per_cycle=5,
    )
    await daemon._apply_watchlist(["005930", "000660"])
    assert calls == ["000660"]  # warm 005930 skipped; only cold prewarmed


@pytest.mark.asyncio
async def test_prewarm_respects_per_cycle_cap():
    calls = []

    async def _prewarm(symbol):
        calls.append(symbol)

    daemon = _daemon(
        engine=_FakeEngine(warm=()),  # all cold
        prewarm_fn=_prewarm,
        max_prewarm_per_cycle=2,
    )
    await daemon._apply_watchlist(["a", "b", "c", "d"])
    assert len(calls) == 2  # capped; remainder retried next refresh (still cold)


@pytest.mark.asyncio
async def test_apply_watchlist_without_prewarm_fn_is_noop():
    daemon = _daemon(engine=_FakeEngine(warm=()), prewarm_fn=None)
    await daemon._apply_watchlist(["a", "b"])  # must not raise
    assert daemon._universe == ["a", "b"]
```

Note: `_daemon(**kw)` must forward `prewarm_fn`/`max_prewarm_per_cycle`. The existing helper passes `**kw` into `StockStrategyDaemon(...)`, so no helper change is needed once the constructor accepts them.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/stock_strategy/test_daemon.py -k prewarm -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'prewarm_fn'` (and `_apply_watchlist` not awaitable).

- [ ] **Step 3: Write minimal implementation**

In `services/stock_strategy/daemon.py`:

Add imports near the top (`Awaitable` to the typing import):
```python
from collections.abc import Awaitable, Callable
```

Extend `__init__` signature (add params after `regime_config`) and store them:
```python
        regime_config: StockRegimeConfig | None = None,
        prewarm_fn: Callable[[str], Awaitable[Any]] | None = None,
        max_prewarm_per_cycle: int = 5,
    ) -> None:
        ...
        self._regime_config = regime_config
        self._prewarm_fn = prewarm_fn
        self._max_prewarm_per_cycle = max_prewarm_per_cycle
```

Replace the existing `_apply_watchlist` with an async version + `_prewarm_cold`:
```python
    async def _apply_watchlist(self, raw: Any) -> None:
        codes = parse_watchlist_codes(raw, max_symbols=self._max_symbols)
        if not codes:
            return  # keep prior universe
        self._universe = codes
        self.feed.update_symbols(codes)
        await self._prewarm_cold()

    async def _prewarm_cold(self) -> None:
        """Warm universe symbols that are not yet warm (≤ cap per cycle).

        Warmth-based, not membership-based: this naturally covers newly-added
        symbols and earlier REST-missed/over-cap ones (they stay cold and are
        retried next refresh until warm or dropped from the universe).
        """
        if self._prewarm_fn is None:
            return
        cold = [s for s in self._universe if not self.engine.is_warm(s)]
        for symbol in cold[: self._max_prewarm_per_cycle]:
            try:
                await self._prewarm_fn(symbol)
            except Exception:
                logger.exception("prewarm failed symbol=%s", symbol)
```

Update `_refresh_loop` to await the now-async call:
```python
            if self._watchlist_reader is not None:
                try:
                    await self._apply_watchlist(self._watchlist_reader())
                except Exception:
                    logger.exception("watchlist refresh failed; keeping prior universe")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/stock_strategy/test_daemon.py -v`
Expected: PASS (existing daemon tests + 3 new). If any existing test called `_apply_watchlist(...)` synchronously, update it to `await`.

- [ ] **Step 5: Commit**

```bash
git add services/stock_strategy/daemon.py tests/unit/stock_strategy/test_daemon.py
git commit -m "feat(stock-prewarm): daemon warmth-based prewarm on universe refresh"
```

---

### Task 4: Wire `prewarm_fn` + unify startup seed in `main.py`

**Files:**
- Modify: `services/stock_strategy/main.py:140-200`
- Test: `tests/unit/stock_strategy/test_main.py` (append)

**Interfaces:**
- Consumes: `warmup_engine` (Task 2), `StockPrewarmConfig` (Task 1), daemon `prewarm_fn`/`max_prewarm_per_cycle` (Task 3).
- Produces: `build_prewarm_fn(engine, store, kis_client, cfg) -> Callable[[str], Awaitable[WarmupResult]]` (factored out so it is unit-testable); daemon constructed with it.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/unit/stock_strategy/test_main.py
import pytest


@pytest.mark.asyncio
async def test_build_prewarm_fn_calls_warmup_engine(monkeypatch):
    from services.stock_strategy import main as main_mod
    from shared.streaming.candle_warmup import StockPrewarmConfig, WarmupResult

    seen = {}

    async def _fake_warmup(engine, symbol, *, store, kis_client, config):
        seen["symbol"] = symbol
        seen["config"] = config
        return WarmupResult(120, 252, "parquet")

    monkeypatch.setattr(main_mod, "warmup_engine", _fake_warmup)
    fn = main_mod.build_prewarm_fn(
        engine=object(), store=object(), kis_client=object(),
        cfg=StockPrewarmConfig(rest_enabled=True),
    )
    res = await fn("000660")
    assert seen["symbol"] == "000660"
    assert seen["config"].rest_enabled is True
    assert res.source == "parquet"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/stock_strategy/test_main.py -k prewarm -v`
Expected: FAIL with `AttributeError: module ... has no attribute 'build_prewarm_fn'`.

- [ ] **Step 3: Write minimal implementation**

In `services/stock_strategy/main.py`:

Add import:
```python
from shared.streaming.candle_warmup import StockPrewarmConfig, warmup_engine
```

Add the factory (module level):
```python
def build_prewarm_fn(*, engine, store, kis_client, cfg):
    """Return an async ``prewarm_fn(symbol)`` bound to engine/store/kis_client/cfg."""

    async def _prewarm(symbol: str):
        return await warmup_engine(
            engine, symbol, store=store, kis_client=kis_client, config=cfg
        )

    return _prewarm
```

In the async `main()` wiring (replace the startup seed loop at ~178-181 and the daemon construction ~188-200). First build the KIS client (real key already required for stock market data) and config:
```python
    from shared.kis.client import KisClient  # if not already imported

    prewarm_cfg = StockPrewarmConfig.load()
    kis_client = KisClient()  # follows existing KIS client construction in this repo
    prewarm_fn = build_prewarm_fn(
        engine=engine, store=store, kis_client=kis_client, cfg=prewarm_cfg
    )

    # Startup seed via the same path (unifies startup + intraday prewarm).
    initial_codes = parse_watchlist_codes(_watchlist_reader(), max_symbols=_max_symbols)
    for sym in initial_codes:
        await prewarm_fn(sym)
```

Then pass into the daemon:
```python
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
        regime_config=regime_config,
        prewarm_fn=prewarm_fn,
        max_prewarm_per_cycle=prewarm_cfg.max_prewarm_per_cycle,
    )
```

Note for implementer: construct `KisClient` exactly as the repo's other stock services do (check `services/screener.py` / existing `KisClient()` usage for required args/singleton). If a shared KIS client accessor exists, prefer it. The startup seed is now `async` — it already runs inside `main()`'s event loop.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/stock_strategy/test_main.py -v`
Expected: PASS (existing + new).

- [ ] **Step 5: Commit**

```bash
git add services/stock_strategy/main.py tests/unit/stock_strategy/test_main.py
git commit -m "feat(stock-prewarm): wire prewarm_fn + unify startup seed in stock-strategy main"
```

---

### Task 5: Orchestrator DRY refactor to use `warmup_engine`

**Files:**
- Modify: `services/trading/orchestrator.py` (`_prewarm_symbols` per-symbol body)
- Test: existing orchestrator prewarm tests (no new test; this is a no-behavior-change refactor verified green)

**Interfaces:**
- Consumes: `warmup_engine` (Task 2).
- Produces: orchestrator's per-symbol parquet→REST+daily seeding delegated to the shared helper; the Redis candle-cache tier-0 (`_load_candle_cache_from_redis`) and metrics/logging stay in the orchestrator.

- [ ] **Step 1: Locate the existing test**

Run: `.venv/bin/pytest -k "prewarm" tests/unit/trading -v 2>&1 | tail -20` (and `grep -rln "_prewarm_symbols\|prewarm" tests/`).
Expected: identify the orchestrator prewarm test(s); confirm they pass on the current branch BEFORE refactor.

- [ ] **Step 2: Refactor the per-symbol body**

Replace the per-symbol parquet→REST block inside `_prewarm_symbols` (orchestrator.py ~3828-3866, the `for symbol in symbols:` loop body up to the daily-seed) with a call to the shared helper, mapping orchestrator config to `StockPrewarmConfig`:

```python
from shared.streaming.candle_warmup import StockPrewarmConfig, warmup_engine

...
        parquet_limit = 700 if self.config.asset_class == "futures" else 120
        cfg = StockPrewarmConfig(
            rest_enabled=True,
            parquet_minute_limit=parquet_limit,
            rest_count=120,
            min_candles=warmup_min_candles,
        )
        for symbol in symbols:
            if symbol not in set(self.config.symbols):
                continue
            try:
                res = await warmup_engine(
                    self._indicator_engine, symbol,
                    store=self._market_data_store, kis_client=self._kis_client,
                    config=cfg,
                )
                if res.source == "parquet":
                    parquet_hits += 1
                elif res.source == "rest":
                    kis_hits += 1
                if res.daily_seeded:
                    daily_parquet_hits += 1
                if res.minute_seeded == 0:
                    self._warmup_miss_count += 1
                    self._metrics.record_warmup_miss()
            except Exception as e:
                logger.warning(f"Prewarm failed for {symbol}: {e}")
```

Keep the tier-0 `redis_hits = await self._load_candle_cache_from_redis()` call before the loop and the final summary log. Implementer: confirm the orchestrator's store attribute name (`self._market_data_store` or equivalent) and that `warmup_engine`'s daily seed (`get_daily_bars`) matches the orchestrator's prior `_fetch_daily_candles_from_market_data_store(limit=252)`; if the futures path must NOT seed daily, gate `seed_daily` by asset class (add a `seed_daily: bool = True` kwarg to `warmup_engine` and pass `self.config.asset_class == "stock"`).

- [ ] **Step 3: Run the existing prewarm tests**

Run: `.venv/bin/pytest -k "prewarm" tests/unit/trading -v`
Expected: PASS (same as before refactor — no behavior change).

- [ ] **Step 4: Run the broader orchestrator unit tests**

Run: `.venv/bin/pytest tests/unit/trading -q`
Expected: PASS (no regressions).

- [ ] **Step 5: Commit**

```bash
git add services/trading/orchestrator.py shared/streaming/candle_warmup.py
git commit -m "refactor(prewarm): orchestrator delegates per-symbol warmup to shared helper (DRY)"
```

---

### Task 6: Full-suite regression + paper config enable

**Files:**
- Modify: paper env config to enable `rest_enabled` (operator-applied; document the key)
- Test: full unit suite

**Interfaces:** none (verification + rollout doc).

- [ ] **Step 1: Run the full relevant suites**

Run: `.venv/bin/pytest tests/unit/streaming tests/unit/stock_strategy tests/unit/trading -q`
Expected: PASS (all).

- [ ] **Step 2: Lint/type**

Run: `ruff check shared/streaming/candle_warmup.py services/stock_strategy/daemon.py services/stock_strategy/main.py && black --check shared/streaming/candle_warmup.py services/stock_strategy/`
Expected: clean.

- [ ] **Step 3: Document paper enablement**

Add to the PR description (and `docs/runbooks` if present) that the paper stack enables REST prewarm by setting `stock_prewarm.rest_enabled: true` in the paper-mounted `config/stock_prewarm.yaml`, deployed via `docker compose --env-file .env.paper build stock-strategy && ... up -d --no-deps stock-strategy` (never `down`).

- [ ] **Step 4: Commit (if any doc/config changes)**

```bash
git add -A && git commit -m "chore(stock-prewarm): full-suite regression green + paper enablement note"
```

---

## Self-Review

**Spec coverage:**
- 3-tier prewarm (cache→parquet→REST) → Task 2 (parquet+REST) + Task 5 (orchestrator keeps Redis tier-0). ✓
- Warmth-based trigger on universe refresh → Task 3. ✓
- Shared helper / DRY extraction + orchestrator refactor → Task 2 + Task 5. ✓
- Config-driven (`StockPrewarmConfig` + yaml, paper override) → Task 1 + Task 6. ✓
- REST guards (rate-limit short-circuit, sleep, per-cycle cap, timeout) → Task 2 (short-circuit/sleep/timeout) + Task 3 (cap). ✓
- Daily seed for indicators → Task 2 `_seed_daily`. ✓
- Best-effort / no-regression → Task 2 exception handling + Task 5 green tests. ✓
- Observability → folded into Task 2/Task 5 logging + orchestrator metrics (existing `record_warmup_miss`); dedicated Prometheus counters from the spec are OPTIONAL and deferred (YAGNI — existing warmup-miss metric + logs cover the need; add counters only if observation shows a gap).

**Placeholder scan:** No TBD/TODO; every code step has concrete code. Two implementer notes (KisClient construction in Task 4; orchestrator store attr name + futures daily gating in Task 5) point at exact files to confirm a name — these are verification pointers, not missing logic.

**Type consistency:** `warmup_engine(engine, symbol, *, store, kis_client, config) -> WarmupResult` used identically in Tasks 2/4/5. `StockPrewarmConfig` fields consistent across Tasks 1/2/4/5. `prewarm_fn: Callable[[str], Awaitable]` consistent across Tasks 3/4. `WarmupResult(minute_seeded, daily_seeded, source)` consistent.

**Deviation note:** Spec listed dedicated `stock_prewarm_*` Prometheus counters; plan defers them (reuses existing `record_warmup_miss` + logs) per YAGNI. Flag for the reviewer.
