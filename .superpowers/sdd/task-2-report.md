# Task 2 Report — Throttle backfill to KIS limits (configurable)

## Status: DONE

## Change summary

- `shared/collector/historical/backfill.py` — replaced hardcoded `Semaphore(10)` / `RateLimiter(20)` in `_get_semaphore()` / `_get_rate_limiter()` with configurable reads from env vars `BACKFILL_CONCURRENCY` (default **3**) and `BACKFILL_RPS` (default **5**). Added inline comments explaining that 20 rps / 10-concurrent bursting was the root cause of KIS HTTP 500 cascade.
- `tests/unit/collector/test_backfill_throttle_config.py` — new TDD test file: asserts default concurrency=3/rps=5 and env-override BACKFILL_CONCURRENCY=4/BACKFILL_RPS=8 are reflected. Resets module-level singletons via monkeypatch between tests.

## Tests

- 2 new tests PASS (test_default_concurrency_and_rps, test_env_override_concurrency_and_rps)
- Full `tests/unit/collector/` suite: **39/39 PASS**, no regressions

## Concerns

None. The lazy-singleton structure and all call sites are unchanged. Singleton loop-rebind guard preserved.

---

# [Previous sprint] Task 2 Report — TrackAExit generator + entry_atr wiring

## Status: DONE_WITH_CONCERNS

## TDD RED → GREEN

### RED (Step 2b)
```
.venv/bin/pytest tests/unit/strategy/exit/test_track_a_exit.py::test_crash_guard_long_fires -x -v
FAILED — NotImplementedError (as expected)
```

### GREEN (Step 2e)
```
.venv/bin/pytest tests/unit/strategy/exit/test_track_a_exit.py -v
27 passed in 0.79s
```

Broader strategy suite: 604 passed, 31 warnings.

## Commits
- `ff1ea99` feat(futures): TrackAExit generator + entry_atr wiring

## Files Changed
1. `shared/strategy/exit/track_a_exit.py` — replaced stub with full generator: `should_exit`, `scan_positions`, `_check_position`, `_get_atr`, `_should_eod_close`, `_calc_profit_pct`, `_calc_profit_amount`, `_create_exit_signal`
2. `tests/unit/strategy/exit/test_track_a_exit.py` — appended 13 generator tests (27 total)
3. `shared/strategy/entry/setup_adapters.py` — added `entry_atr` parameter to `_decision_signal_to_orchestrator_signal`; both SetupA and SetupC call sites extract ATR from `context.market_data` and pass it; `entry_atr` added to the metadata dict
4. `services/trading/orchestrator.py:7093` — `"entry_atr"` added to the key list copied `signal_meta` → `pos_metadata`

## Exact Insertion Points

### setup_adapters.py
- `_decision_signal_to_orchestrator_signal` signature: added `entry_atr: float = 0.0`
- metadata dict (L515): `"entry_atr": entry_atr`
- SetupA call site (~L1179): added 11-line ATR-extraction block before the return
- SetupC call site (~L1447): identical ATR-extraction block before the return

### orchestrator.py
- L7093: inserted `"entry_atr",` between `"take_profit",` and `"exit_stop_atr_multiplier",`

## Concern: Brief Test Data Inconsistency

The brief's three catastrophic/beats-trail tests used `prev_price` values that caused the crash guard (p1, threshold = 3.5×ATR = 7) to fire instead of the intended catastrophic stop (p2). Specifically:

| Test | prev_price | close | tick-drop | crash threshold | Result |
|------|-----------|-------|-----------|-----------------|--------|
| test_catastrophic_stop_long | 99.0 | 88.0 | 11 | 7 | crash fires (wrong) |
| test_catastrophic_stop_short | 101.0 | 112.0 | 11 | 7 | crash fires (wrong) |
| test_catastrophic_beats_trail | 100.0 | 88.0 | 12 | 7 | crash fires (wrong) |

These tests were corrected to `prev_price=89.0/111.0/89.0` respectively (1pt tick move vs 12pt catastrophic from entry). The test intent is preserved: catastrophic = large loss from entry without a single-tick spike.

## Self-Review
- Long/short symmetry: crash, catastrophic, trail, EOD all tested both sides
- ATR fallback path: `_get_atr` tries snapshot keys first then `entry_atr` from metadata
- ATR=0 guard: `test_no_atr_skips_all_atr_exits` confirms all ATR exits skipped when atr=0
- `prev_price` updated before any return (prevents stale prev after early exit)
- No daily-bias filter added (Task 4 scope)
- No blanket EOD liquidation changes
- Config-driven (all thresholds in TrackAExitConfig)

## Report Path
`/home/deploy/project/kis_unified_sts/.superpowers/sdd/task-2-report.md`

---

## Review Fixes Applied (2026-06-21)

### Changes Made

**I1 — EOD fires when ATR=0 (new positive-path test)**
- Added `test_eod_fires_when_atr_zero` in `tests/unit/strategy/exit/test_track_a_exit.py`
- Monkeypatches `now_kst`, `is_trading_day_kst`, and `effective_close_time` in `shared.strategy.exit.track_a_exit` module namespace
- Fixed KST time: Monday 2026-06-22 15:20 KST (past 15:15 cutoff)
- Position has no `entry_atr` and snapshot `atr=0.0` — confirms ATR=0 guard skips only ATR exits, EOD still fires
- Asserts `reason == ExitReason.EOD_CLOSE` and `metadata["exit_type"] == "eod_close"`

**I2 — Deterministic entry_time in test fixtures**
- Replaced `datetime.now(UTC) - timedelta(minutes=30)` in `_long_position` and `_short_position` with `_FIXED_ENTRY_TIME = datetime(2026, 1, 1, tzinfo=UTC)`
- No assertions use `holding_minutes`, so fixed past time is safe

**M1 — Symmetric high_since_entry in _create_exit_signal**
- In `shared/strategy/exit/track_a_exit.py`, `_create_exit_signal` now passes:
  `high_since_entry = position.highest_price if position.side == PositionSide.LONG else position.lowest_price`
- SHORT positions now report the favorable extreme (lowest_price) rather than always highest_price

### Test Run
```
.venv/bin/pytest tests/unit/strategy/exit/test_track_a_exit.py -v
28 passed in 0.77s
```
