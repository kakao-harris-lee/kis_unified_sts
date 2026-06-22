# Futures Backfill Resilience + Minute Quality Gate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Stop the ~70% futures-minute parquet loss: make the REST backfill retry paginated 500s, throttle to KIS limits, refuse to lock partial days as `success`, and add a futures-minute coverage gate so future shortfalls alert instead of going silent.

**Architecture:** Root cause (data-engineer diagnosis, 2026-06-22): KIS returns HTTP 500 on backward-pagination minute requests; `fetch_minute_async` breaks on the first 500 so only page 1 (102 bars = KIS per-call max) survives; the day is then marked `success` and `resume` skips it forever; the backfill runs at 20 rps / 10 concurrent (>> KIS 5 rps), triggering the 500 cascade; and there is no futures-minute quality gate so the loss is silent. Trading is unaffected (orchestrator trades via WS); only the historical parquet (backtest/experiment input) degrades.

**Tech Stack:** Python 3.12, asyncio, pytest, KIS REST (`inquire_time_fuopchartprice`, 102 rows/call + `FID_INPUT_HOUR_1` cursor).

**Branch:** `fix/futures-backfill-resilience`.

## Global Constraints
- Config-driven: throttle rps/concurrency + completeness thresholds + quality-gate expectations in config/env, not hardcoded literals where a knob makes sense.
- KST trading/session logic; KIS minute history capped ~30 days (heal only recovers ~last 30d).
- Best-effort + idempotent: a transient 500 must retry then, if still failing, mark the day FAILED (so resume re-attempts) — never silently lock a partial day as success.
- No regression: changes touch the shared backfill hot path (`shared/collector/historical/`); every change is TDD'd; existing collector tests stay green.
- Redis DB1; KST; DRY; YAGNI; frequent commits; `.venv/bin/pytest`. Feature branch only.

## File Structure / anchors (verified 2026-06-22)
- `shared/collector/historical/backfill.py` — `fetch_minute_async` (`def` at :223); pagination loop with break-on-`rt_cd!=0` at :328-329 (+ breaks :321/326/333/337/343/348); `_semaphore = asyncio.Semaphore(10)` :204; `_rate_limiter = RateLimiter(20)` :213.
- `shared/collector/historical/parquet_backfill.py` — `_write_minute_tasks` mark_success on partial (:280-345); `ParquetBackfillState.is_completed/mark_success` (:71-130).
- `shared/collector/historical/daily_quality.py` + `config/daily_data_quality.yaml` — stock-daily only; NO futures-minute coverage gate.
- `shared/collector/historical/futures.py` — `get_front_month_code` (roll is correct; do NOT touch).

---

### Task 1: Retry paginated 500 / transient errors in `fetch_minute_async`

**Files:** Modify `shared/collector/historical/backfill.py` (`fetch_minute_async` pagination loop). Test: `tests/unit/collector/` (locate the existing backfill test; create `test_backfill_minute_pagination.py` if none).

**Interfaces:** Produces: pagination loop retries a page on HTTP 500 / `rt_cd != "0"` up to `page_max_retries` (default 3) with backoff before breaking; a genuinely empty/last page still terminates cleanly. Mirror the page-1 `max_retries` logic that already wraps the first request.

- [ ] **Step 1: failing test** — drive `fetch_minute_async` (or its page-fetch helper) with a stubbed KIS client whose page-2 call returns HTTP 500 twice then 200 with rows; assert all pages are collected (not truncated at 102). Also a test where 500 persists → loop breaks after `page_max_retries` and returns the pages gathered so far (does NOT raise). Use the repo's existing async-test + KIS-client-double conventions (read the existing collector tests first).
- [ ] **Step 2: run → FAIL** (`.venv/bin/pytest <test> -v`).
- [ ] **Step 3: implement** — extract the page fetch into a retry wrapper: on 500/`rt_cd!=0`/timeout, `await asyncio.sleep(backoff)` and retry up to `page_max_retries`; only `break` after exhausting retries. Keep the existing terminal conditions (empty page, cursor non-advance) intact. `page_max_retries` + backoff are module constants or config (no magic literals inline).
- [ ] **Step 4: run → PASS.**
- [ ] **Step 5: commit** `fix(backfill): retry paginated 500/transient before breaking (futures minute)`.

---

### Task 2: Throttle backfill to KIS limits (configurable)

**Files:** Modify `shared/collector/historical/backfill.py` (`_semaphore` :204, `_rate_limiter` :213). Test: same area.

**Interfaces:** Produces: rps and concurrency read from env/config (defaults **rps=5, concurrency=3**, matching the orchestrator KIS client's 5 req/s) instead of hardcoded `RateLimiter(20)`/`Semaphore(10)`. Env names e.g. `BACKFILL_RPS` / `BACKFILL_CONCURRENCY` (follow existing env-naming convention in this module).

- [ ] **Step 1: failing test** — assert the rate limiter/semaphore are constructed from the config/env values (inject a config or monkeypatch env; assert the effective limit). 
- [ ] **Step 2: run → FAIL.**
- [ ] **Step 3: implement** — replace the literals with config/env reads (default 5 / 3); keep a single source of truth. Document why (KIS 5 rps; bursting at 20 triggered the 500 cascade).
- [ ] **Step 4: run → PASS.**
- [ ] **Step 5: commit** `fix(backfill): throttle to KIS 5rps/3-concurrent (configurable) to cut 500 cascade`.

---

### Task 3: Completeness gate — don't mark a short day `success`

**Files:** Modify `shared/collector/historical/parquet_backfill.py` (`_write_minute_tasks` :280-345; `mark_success`/`is_completed` :71-130). Test: `tests/unit/collector/` backfill-state test.

**Interfaces:** Produces: before `mark_success` for a full trading day, require `rows >= expected_min_bars` (full regular session ≈ ~360 1-min bars for the mini; allow a tolerance + a half-day/holiday rule via the trading calendar). Below threshold → `mark_failed` so `resume` re-attempts. Expected-bar threshold + tolerance are config-driven.

- [ ] **Step 1: failing test** — given a day that wrote 102 rows (< expected), assert the state is `failed` (not `success`) so `is_completed()` is False and a resume run re-attempts; given a full ~360-row day, assert `success`. Cover a half-day (early close) so it isn't falsely failed.
- [ ] **Step 2: run → FAIL.**
- [ ] **Step 3: implement** — add the completeness check keyed to the trading-calendar expected bars (reuse existing market-calendar/half-day helpers; don't hardcode 360 blindly). 
- [ ] **Step 4: run → PASS.**
- [ ] **Step 5: commit** `fix(backfill): mark short futures-minute days failed, not success (self-heal resume)`.

---

### Task 4: Futures-minute coverage quality gate

**Files:** Extend `shared/collector/historical/daily_quality.py` + `config/daily_data_quality.yaml` (add a futures-minute section), OR add a post-backfill verifier alongside the scheduler's existing stock verification. Test: `tests/unit/collector/`.

**Interfaces:** Produces: a per-day futures-minute coverage assertion for the active mini front-month — if bars < expected (calendar-aware), emit a WARNING/Telegram alert (reuse the existing notifier_for_domain path) and surface it (so a 70% shortfall is never silent again). Config-driven thresholds.

- [ ] **Step 1: failing test** — coverage check returns OK for a full day, FLAGS (and would alert) for a 102/360 day; calendar-aware (half-days not flagged).
- [ ] **Step 2: run → FAIL.**
- [ ] **Step 3: implement** — add the futures-minute coverage gate mirroring the stock-daily quality pattern; wire the alert via the existing notification path (briefing/ops domain). Keep it read-only on data (reporting/alert, not mutating parquet).
- [ ] **Step 4: run → PASS.**
- [ ] **Step 5: commit** `feat(data-quality): futures-minute coverage gate (alert on shortfall)`.

---

### Task 5: Full regression + heal note

- [ ] **Step 1:** `.venv/bin/pytest -n auto -m "not serial" -q` + `.venv/bin/pytest -m "serial" -q` — both exit 0 (the backfill changes touch shared collector code; run the full suite per the Component-B lesson).
- [ ] **Step 2:** ruff + black --check on changed files.
- [ ] **Step 3:** Document the one-time HEAL (operator, post-merge): `python -m cli.main backfill run --days 30 --no-resume` (or clear the partial `(code, trade_date)` rows from the state DB), recovering ~last 30 days only (KIS limit). Note May–Jun beyond 30d is permanently lost.
- [ ] **Step 4:** Commit any cleanup; controller runs final whole-branch review.

---

## Self-Review
**Coverage:** pagination-500 retry → T1; throttle → T2; completeness gate → T3; quality gate (#2) → T4; regression+heal → T5. All diagnosis fixes covered.
**No-placeholders:** Tasks reference exact files/anchors; "locate the existing test" pointers require the implementer to find the real collector test path at execution (not invent it) — concrete, not vague. Implementers read the actual pagination code (anchors given) before editing.
**Risk note for executor:** shared backfill hot path — keep terminal pagination conditions intact (only add retry-before-break), don't change `get_front_month_code` (roll is correct), and run the FULL suite in T5.
