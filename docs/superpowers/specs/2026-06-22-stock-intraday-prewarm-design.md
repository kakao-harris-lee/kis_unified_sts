# Stock Intraday Symbol Prewarm — Design Spec (Component B)

**Status:** Draft for review
**Date:** 2026-06-22
**Author:** Claude (with operator)
**Sibling (deferred):** Component A — per-symbol bear-gate override
(`docs/superpowers/specs/2026-06-22-stock-bear-gate-per-symbol-override-design.md`,
to be written after this ships). This spec is the FIRST sub-project and is
independently shippable.

## Goal

Make LLM/screener-discovered **intraday-added** stock symbols actually tradeable
in the decoupled stock pipeline by warming the indicator engine on universe
change (Redis candle cache → parquet → KIS REST), instead of warming only the
startup universe.

## Problem

`StockStrategyDaemon.evaluate_once` skips any symbol that is not warm:

```python
for symbol in list(self._universe):
    if not self.engine.is_warm(symbol):
        continue
```

The engine is seeded **only for the initial universe at startup**
(`services/stock_strategy/main.py:178-181` calls `warmup_engine_from_parquet`
once per initial code). When the screener adds a symbol mid-session via the
watchlist refresh (`StockStrategyDaemon._apply_watchlist` →
`feed.update_symbols`), nothing warms it. It then stays `is_warm() == False`
until enough **live** 1-min bars accumulate — which can take far longer than the
intraday opportunity that caused the LLM to surface it. Net effect: intraday
event-driven additions get no trading chance.

This is compounded by data coverage: minute parquet is healthy for only ~45
stock symbols, so the small-cap surges the screener surfaces (e.g. on
2026-06-22 한솔테크닉스 +21%, 제주반도체 +16%) frequently have **no parquet
history at all** → parquet-only prewarm would still leave them cold. A REST
backfill tier is required for the fix to be meaningful.

The monolithic orchestrator already solves this with a 3-tier prewarm
(`services/trading/orchestrator.py:3811 _prewarm_symbols`: Redis candle cache →
parquet → KIS REST `get_minute_bars`, with `is_rate_limited` short-circuit and
`asyncio.sleep(0.3)` pacing). The decoupled daemon simply never got the
equivalent. This spec ports that proven pattern (extracted to a shared helper —
DRY) and triggers it on universe change.

## Architecture

```
StockStrategyDaemon._refresh_loop (async)
  └─ _apply_watchlist(raw):                        # now async
       new_codes = parse(raw)
       self._universe = new_codes
       self.feed.update_symbols(new_codes)         # (unchanged) start streaming
       await self._prewarm_cold()                  # NEW: warm cold symbols

_prewarm_cold():
  cold = [s for s in self._universe if not engine.is_warm(s)]   # warmth-based
  for symbol in cold[:max_prewarm_per_cycle]:      # bounded REST load per cycle
     await prewarm_fn(symbol)                       # shared parquet→REST helper
  # leftover (> cap) and REST-misses naturally reappear in `cold` next cycle
```

**Targeting is warmth-based, not membership-based.** Each refresh prewarms
universe symbols where `not engine.is_warm(symbol)` (capped). This single rule
subsumes both "newly added this cycle" and "added earlier but REST-missed/
deferred" with no separate bookkeeping, and is naturally idempotent (warm
symbols drop out of `cold`).

A newly added symbol becomes warm within one refresh cycle (parquet/REST give
the historical baseline; live ticks from the feed then build today's bars), so
`evaluate_once` evaluates it on the next decision tick instead of skipping it.

## Components / file changes

### New: `shared/streaming/candle_warmup.py`
Extract the orchestrator's per-symbol 3-tier logic into one reusable async
helper (DRY — orchestrator refactored to call it):

```python
async def warmup_engine(
    engine: Any,
    symbol: str,
    *,
    store: Any | None = None,            # ParquetMarketDataStore (parquet tier)
    kis_client: Any | None = None,       # KisClient (REST tier)
    parquet_limit: int = 120,
    rest_count: int = 120,
    min_candles: int = 20,
    rest_enabled: bool = True,
) -> int:
    """Seed engine 1-min candles for one symbol. Returns #candles seeded (0 on miss).

    Priority: parquet (no rate limit) -> KIS REST (rate-limit guarded).
    Best-effort: any error returns 0 and the engine warms from live ticks
    (no regression vs today). Skips REST when kis_client.is_rate_limited.
    """
```

Behavior (mirrors `orchestrator._prewarm_symbols` per-symbol body):
- If `engine.is_warm(symbol)` → return 0 (skip; idempotent re-add safe).
- Parquet first via `store.get_minute_bars(symbol, start=...)`
  (reuse `warmup_engine_from_parquet`'s tail logic) → if candles, seed + return.
- Else, if `rest_enabled` and not `kis_client.is_rate_limited`:
  `await asyncio.wait_for(kis_client.get_minute_bars(symbol, count=rest_count), timeout=5.0)`
  then `await asyncio.sleep(0.3)` (rate-limit pacing) → seed + return.
- Else (rate limited / disabled / REST miss) → return 0.
- `len(candles) < min_candles` → log WARNING (under-initialised, not a hard miss).

`shared/streaming/parquet_warmup.py::warmup_engine_from_parquet` remains the
parquet tail-read primitive; `candle_warmup.warmup_engine` composes it + REST.

### Modify: `services/stock_strategy/daemon.py`
- `__init__`: add `prewarm_fn: Callable[[list[str]], Awaitable[None]] | None = None`
  and `max_prewarm_per_cycle: int = 5`.
- `_apply_watchlist` becomes `async` (it is awaited from the async
  `_refresh_loop`). After `self._universe = codes` and `feed.update_symbols`,
  call `await self._prewarm_cold()`.
- `_prewarm_cold()` (new): `cold = [s for s in self._universe if not
  self.engine.is_warm(s)]`; for the first `max_prewarm_per_cycle` of `cold`,
  `await self._prewarm_fn(symbol)`. No `added`/deferred bookkeeping — REST-missed
  and over-cap symbols stay in `cold` and are retried next cycle until warm or
  dropped from the universe. No-op when `prewarm_fn is None`.
- No change to `evaluate_once`'s `is_warm` gate — once warmed, it just works.

### Modify: `services/stock_strategy/main.py`
- Build `kis_client` (real KIS key — stock market data already requires it).
- Construct `prewarm_fn` closure:
  `async def _prewarm(codes): for c in codes: await warmup_engine(engine, c, store=store, kis_client=kis_client, **cfg)`.
- Replace the startup seed loop (178-181) to call the same `warmup_engine`
  (unify startup + intraday paths; remove the parquet-only divergence).

### Modify: `services/trading/orchestrator.py`
- Refactor `_prewarm_symbols` to call `candle_warmup.warmup_engine` per symbol
  (keep the batch Redis-cache preload `_load_candle_cache_from_redis` as the
  orchestrator's tier-0; the shared helper covers parquet+REST). DRY, no
  behavior change — covered by existing orchestrator prewarm tests.

## Config

New `config/stock_prewarm.yaml` (section `stock_prewarm`), loaded with
defaults-on-failure (same pattern as `StockRegimeConfig.load`):

```yaml
stock_prewarm:
  rest_enabled: true          # KIS REST backfill tier (paper)
  parquet_limit: 120          # bars read from parquet
  rest_count: 30              # KIS stock minute API returns ~30 for current session
  min_candles: 20             # warn threshold (matches feed warmup_min_candles)
  max_prewarm_per_cycle: 5    # bound REST calls per refresh cycle
  lookback_days: 5            # parquet start-bound window
```

A `StockPrewarmConfig` frozen dataclass mirrors `StockRegimeConfig`. Code
default for `rest_enabled` is conservative but the paper YAML enables it.
No hardcoded thresholds in code (CLAUDE.md config-driven rule).

## Error handling / safety (IP-ban history aware)

- **REST is throttled and bounded**, never a storm: per-symbol REST only when
  parquet misses AND `not kis_client.is_rate_limited`; `asyncio.sleep(0.3)`
  between calls; at most `max_prewarm_per_cycle` REST calls per refresh cycle;
  5s timeout per call. This is REST one-shot per symbol, not WS reconnection —
  categorically different from the 2026-06 WS over-connection incident.
- **Rate-limit short-circuit**: when the client is in penalty/cooldown, prewarm
  skips REST entirely this cycle and retries next cycle (no hammering).
- **Best-effort / no regression**: any parquet or REST failure returns 0 and
  the symbol warms from live ticks exactly as today.
- **Idempotent**: `is_warm` guard means re-adding an already-warm symbol is a
  no-op; safe under repeated refreshes.
- KIS minute REST returns ~30 bars (current session); symbols needing deeper
  history for some indicators still get those from the separate daily store +
  accumulating live bars — acceptable for intraday momentum strategies.

## Observability

- INFO: `prewarm <symbol>: <n> candles seeded (parquet|rest)` and
  `deferred <k> symbols (cap)`.
- Metrics (Prometheus, existing exporter): `stock_prewarm_seeded_total{source}`,
  `stock_prewarm_rest_skipped_total{reason}`, `stock_prewarm_deferred`.

## Testing

- `warmup_engine`: parquet-hit (no REST), parquet-miss→REST-hit, REST
  rate-limited→skip (no call), REST disabled→skip, already-warm→0, best-effort
  exception→0. Assert `seed_candles` called with expected candles; assert REST
  NOT called when rate-limited (fake client with `is_rate_limited=True`).
- daemon `_apply_watchlist`/`_prewarm_cold`: only **not-warm** universe symbols
  prewarmed (warm ones skipped); `max_prewarm_per_cycle` cap honored; a
  REST-missed symbol is retried next cycle (still in `cold`) until warm; no
  prewarm when `prewarm_fn` is None.
- config load: defaults on missing file; paper override (`rest_enabled: true`).
- orchestrator refactor: existing prewarm tests still green (DRY no-regression).

## Scope / out of scope

- **In:** decoupled stock daemon intraday prewarm (parquet + REST), shared
  helper extraction, config, orchestrator DRY refactor.
- **Out (this spec):** Component A bear-gate override (separate spec, ships
  next). Persisting today's intraday bars to parquet (EOD collection unchanged).
  Futures (orchestrator already has the 3-tier; only the shared extraction
  touches it). No new EOD liquidation; long-only preserved; Redis DB 1 + TTLs.

## Rollout

paper-only via config; code-default conservative, paper YAML enables
`rest_enabled`. Deploy = rebuild `stock-strategy` + `up -d --no-deps`
(never `down`). Observe prewarm metrics + that intraday-added symbols start
producing `signal.candidate.stock` evaluations.
