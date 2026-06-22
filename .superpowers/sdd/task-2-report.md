# Task 2 Report: `warmup_engine` shared helper

## Status: DONE

## TDD Evidence

### RED (Step 2)
Command: `.venv/bin/pytest tests/unit/streaming/test_candle_warmup.py -v`
```
collected 0 items / 1 error
ImportError: cannot import name 'warmup_engine' from 'shared.streaming.candle_warmup'
```

### GREEN (Step 4)
Command: `.venv/bin/pytest tests/unit/streaming/test_candle_warmup.py -v`
```
collected 6 items
tests/unit/streaming/test_candle_warmup.py ......   [100%]
6 passed in 0.78s
```

## Commits
- `fc123e9` feat(stock-prewarm): warmup_engine shared helper (parquet→REST + daily, guarded)

## Files Changed

1. `shared/streaming/candle_warmup.py` — appended `WarmupResult`, `_df_tail_to_candles`, `_seed_daily`, and async `warmup_engine`; added imports (`asyncio`, `datetime`, `UTC`, `timedelta`, `Any`, `NamedTuple`). `StockPrewarmConfig` untouched.
2. `tests/unit/streaming/test_candle_warmup.py` — new test file, 6 async tests covering: parquet hit, parquet miss→REST, rate-limited skip, rest_enabled=False skip, already-warm noop, exception best-effort.

## Self-Review

**Correctness:**
- Tier 1 (parquet) → Tier 2 (REST, rate-limit guarded) → daily seed flow matches spec
- IP-ban guard: REST only when `minute_seeded == 0 AND cfg.rest_enabled AND kis_client is not None AND not is_rate_limited`
- `asyncio.wait_for(..., timeout=5.0)` wraps REST call (one-shot, never a loop)
- `asyncio.sleep(0.3)` pacing immediately after successful REST call
- Already-warm short-circuits before any I/O
- All exceptions caught at all levels; never raises out of `warmup_engine`
- Returns `WarmupResult(0, 0, "none")` on any failure/noop path

**Config-driven:**
- All limits (`parquet_minute_limit`, `daily_limit`, `rest_count`, `min_candles`, `minute_lookback_days`, `daily_lookback_days`) read from `StockPrewarmConfig`; zero hardcoded thresholds in new code

**KST rule:**
- Date-bound computation uses UTC only for lookback window (`datetime.now(UTC) - timedelta(days=...)`) — no KST↔UTC trading-logic comparisons; compliant per project rules

**DRY:**
- `_df_tail_to_candles` shared by both minute and daily paths

## Concerns

None. Implementation is a verbatim match to the brief's spec. All 6 tests pass.

## Report Path
`/home/deploy/project/kis_unified_sts/.superpowers/sdd/task-2-report.md`
