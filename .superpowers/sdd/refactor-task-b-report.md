# Task B Refactor Report: `_prewarm_symbols` DRY delegation to `warmup_engine`

## Summary

Behaviour-preserving DRY refactor of `TradingOrchestrator._prewarm_symbols`
(`services/trading/orchestrator.py`) to delegate the per-symbol
parquet→KIS-REST→daily-seed logic to the shared `warmup_engine`
(`shared/streaming/candle_warmup.py`).

---

## What Changed

### `services/trading/orchestrator.py`

**New module-level imports (lines ~72-74):**
```python
from shared.storage.market_data_store import ParquetMarketDataStore
from shared.streaming.candle_warmup import StockPrewarmConfig, warmup_engine
```
Moved from lazy (inside-function) imports so `warmup_engine` lives in the
module namespace — required for `patch("services.trading.orchestrator.warmup_engine", ...)`
to work in tests.

**`_prewarm_symbols` per-symbol body replaced:**

Before: 40+ lines of manual parquet-fetch → rate-limit check → KIS-REST
fallback → `seed_candles` → miss-counting → daily-seed.

After: one `warmup_engine(...)` call per symbol; the returned `WarmupResult`
is translated back into existing counters:

| WarmupResult field | Orchestrator counter updated |
|---|---|
| `source == "parquet"` | `parquet_hits += 1` |
| `source == "rest"` | `kis_hits += 1` |
| `daily_seeded > 0` | `daily_parquet_hits += 1` |
| `minute_seeded == 0` | `_warmup_miss_count += 1` + `record_warmup_miss()` + WARNING |
| `0 < minute_seeded < min_candles` | `_warmup_miss_count += 1` + `record_warmup_miss()` + WARNING |

**`_fetch_candles_from_market_data_store` and
`_fetch_daily_candles_from_market_data_store`:** kept in place (not removed).
They are no longer called by `_prewarm_symbols` but:
- They still have at least one direct test exercising the exception-handling
  contract (parquet exception → WARNING not DEBUG).
- Removing them would enlarge the diff unnecessarily for a behaviour-
  preserving refactor.

**Tier-0 (Redis candle cache) preserved as-is:**
`_load_candle_cache_from_redis()` is called before the per-symbol loop — this
tier is not covered by `warmup_engine` and was not touched.

**Futures no-daily-seed preserved:**
```python
do_seed_daily = self.config.asset_class == "stock"
```
`warmup_engine` is called with `seed_daily=do_seed_daily`, so futures symbols
never trigger daily seeding — identical to the previous behaviour.

---

## Test Rework

### Why the original tests broke

The original `TestWarmupMissWarnings` tests patched the orchestrator's own
`_fetch_candles_from_market_data_store` and
`_fetch_daily_candles_from_market_data_store` methods.  After the refactor,
`_prewarm_symbols` no longer calls those methods — it calls `warmup_engine`
instead — so the mocks were never intercepted and the tests would fall through
to the real implementation (no store, no KIS client → AttributeError).

### New mock seam

All prewarm tests now patch at:
```
services.trading.orchestrator.warmup_engine
```
returning controlled `WarmupResult(minute_seeded, daily_seeded, source)` values.

### Why the tests still test real behaviour

| Original assertion | Still covered by new test? |
|---|---|
| 0 bars → `_warmup_miss_count == 1` + WARNING | ✓ `WarmupResult(0, 0, "none")` |
| < min_candles → miss + "under-initialised" WARNING | ✓ `WarmupResult(5, 0, "parquet")` with min=20 |
| ≥ min_candles → no miss | ✓ `WarmupResult(10, 0, "parquet")` with min=5 |
| 3 symbols → miss count == 3 | ✓ same assertion, same logic |
| `_fetch_candles_...` exception → WARNING | ✓ kept as direct-call test (method still exists) |

### Two new tests added

`test_redis_cache_tier_consulted_before_per_symbol_loop` — verifies ordering:
Redis must be called before `warmup_engine`.

`test_stock_gets_daily_seed_futures_does_not` — verifies `seed_daily=True`
for stock and `seed_daily=False` for futures by capturing the kwargs passed to
`warmup_engine`.

### Minimal orchestrator helper fix

Added `orch._kis_client = MagicMock()` to `_make_minimal_orchestrator`.
Even though `warmup_engine` is patched, Python evaluates all call arguments
before invoking the function — so `self._kis_client` would raise
`AttributeError` before the patch could intercept the call.

---

## Futures No-Daily-Seed Preserved

Verified by `test_stock_gets_daily_seed_futures_does_not`:
- `asset_class="stock"` → `seed_daily=True` passed to `warmup_engine` ✓
- `asset_class="futures"` → `seed_daily=False` passed to `warmup_engine` ✓

---

## Test Results

```
tests/unit/services/test_feed_observability.py  24/24 PASSED
tests/unit/trading/                            747 passed, 1 skipped
```

RED before test rework: 5 prewarm tests failed (wrong mock seam).
GREEN after: all 24 pass.

---

## Concerns / Follow-up

1. `_fetch_candles_from_market_data_store` and
   `_fetch_daily_candles_from_market_data_store` are now dead code in the
   orchestrator (only one test calls `_fetch_candles_...` directly to cover
   the exception-handling contract).  A follow-up cleanup PR could remove
   them — but that would require updating the exception-contract test too, and
   this refactor stayed deliberately narrow.

2. `warmup_engine`'s rate-limit behaviour differs slightly from the old code:
   the old code did an explicit `continue` (skip the symbol entirely) when
   `is_rate_limited and not parquet_hit`.  `warmup_engine` still skips the
   REST call but returns `WarmupResult(0, 0, "none")` — which causes the
   orchestrator to record a miss.  This is *strictly more visible*: a
   rate-limited symbol that can't get parquet data now shows up as a warmup
   miss, which is correct operational behaviour.

3. The `WarmupResult.daily_seeded` field is an `int` (count of daily candles),
   but the orchestrator only increments `daily_parquet_hits` if it is truthy
   (> 0).  This is consistent with existing behaviour.
