# Task A Report: `seed_daily` flag for `warmup_engine`

## Status
COMPLETE

## Changes

### `shared/streaming/candle_warmup.py`
- Added `seed_daily: bool = True` keyword param to `warmup_engine` signature (line ~112).
- Line 172: `daily_seeded = _seed_daily(...) if seed_daily else 0`
- No other logic changed. `_seed_daily` itself is untouched. `WarmupResult` shape unchanged.
- Existing callers (stock daemon, stock-strategy startup) pass no `seed_daily` arg, so they get default `True` — zero behavior change.

### `tests/unit/streaming/test_candle_warmup.py`
Two new tests appended:
- `test_seed_daily_false_skips_daily_seeding` — asserts `eng.daily` not populated, `daily_seeded==0`, minute seeding still occurs.
- `test_seed_daily_true_default_still_seeds_daily` — regression guard for default behavior.

## Test Result
8 passed, 0 failed (all pre-existing tests pass unmodified).
