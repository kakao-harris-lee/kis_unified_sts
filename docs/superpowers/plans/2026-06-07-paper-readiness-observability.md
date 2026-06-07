# Paper-Readiness: trader-futures + Observability (Increment 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add a `trader-futures` docker-compose service (paper/live via stack env) so stock + futures paper run together via the orchestrator, and add **metrics-primary** observability (bottleneck: pipeline stage latency + order latency; recovery: WS disconnect/reconnect counters, rate-limit cooldown, redis errors) with **exactly two new log lines** (pipeline slow-stage WARN, rate-limit recovery INFO).

**Architecture:** Additive instrumentation around the existing orchestrator/pipeline (shared by stock+futures). Metrics extend `services/monitoring/metrics.py` (scraped by prometheus + dashboard `/metrics`). paper/live = compose-stack distinction (`TRADING_MODE`/`KIS_REAL_TRADING`), not hardcoded.

**Tech Stack:** Python 3.11+, prometheus_client, Docker Compose, pytest.

**Spec:** `docs/superpowers/specs/2026-06-07-paper-readiness-observability-design.md`

**Worktree:** `/tmp/obs-impl` (branch `feat/paper-readiness-observability`). venv: `/home/deploy/project/kis_unified_sts/.venv/bin/{pytest,black,ruff,mypy}` from `cd /tmp/obs-impl`.

**GIT HYGIENE (critical):** NEVER `git stash`/`pop`/`apply`/`drop` (repo-global; corrupts operator stash). `git add <paths>` + `git commit` only. Stay in `/tmp/obs-impl`.

**Constraints:** Additive only — no trading-logic change. All metric calls **best-effort** (a missing/None collector must never break the hot path or a WS thread). Add NO logs beyond the two named. Do NOT touch the decoupled daemons.

**Out of scope:** futures WS auto-reconnect (Increment 2); per-exec DEBUG logs; Grafana dashboards.

---

## File Structure
- Modify: `docker-compose.yml` (add `trader-futures`)
- Create: `docs/runbooks/paper-trading-docker.md` (short ops note)
- Modify: `services/monitoring/metrics.py` (new metric defs + record methods)
- Modify: `services/trading/pipeline.py` (stage-latency observe + slow WARN)
- Modify: `services/trading/orchestrator.py` (order-latency activation + redis record_error)
- Modify: `shared/kis/stock_feed.py`, `shared/kis/websocket.py` (WS counters)
- Modify: `shared/kis/client.py` (rate-limit recovery log + penalty counter)
- Create/extend tests under `tests/unit/monitoring/`, `tests/unit/trading/`, `tests/unit/`(kis)

---

## Task 1: docker-compose `trader-futures` + ops note

**Files:** Modify `docker-compose.yml`; Create `docs/runbooks/paper-trading-docker.md`.

- [ ] **Step 1: Add the service**

In `docker-compose.yml`, after the `trader` service block (before `dashboard`), add `trader-futures` — an exact mirror of `trader` with the SAME `environment` block, except `TRADING_ASSET_CLASS: "futures"` (pinned) and `container_name: ${COMPOSE_PROJECT_NAME:-kis}-trader-futures`. Read the current `trader` block (lines ~32-77) and copy it verbatim, changing only those two lines. Keep `TRADING_MODE: "${TRADING_MODE:-paper}"`, `KIS_REAL_TRADING: "${KIS_REAL_TRADING:-false}"`, `KIS_FUTURES_MARKET: "${KIS_FUTURES_MARKET:-real}"` (paper/live is the stack env — do NOT hardcode). Keep the same `volumes`, `depends_on`, `networks`, `logging`, `profiles: ["trading"]`, `extra_hosts`. Optionally set `TRADING_STRATEGY: "${FUTURES_TRADING_STRATEGY:-}"` so stock/futures can have different strategies; if simpler, keep `${TRADING_STRATEGY:-}` like `trader`.

- [ ] **Step 2: Validate the rendered config**

Run: `cd /tmp/obs-impl && docker compose --profile trading config --services` → must list both `trader` and `trader-futures`.
Run: `docker compose --profile trading config 2>&1 | grep -A2 "TRADING_ASSET_CLASS" | head` → confirm `trader-futures` has `futures` and `trader` has stock (default).
(Read-only config render — does NOT start/stop anything.)

- [ ] **Step 3: Ops note**

Create `docs/runbooks/paper-trading-docker.md` documenting: paper/live = compose STACK (`TRADING_MODE`/`KIS_REAL_TRADING` + `COMPOSE_PROJECT_NAME` e.g. `kis_paper` vs `kis_live`); launch both assets: `docker compose --profile trading up -d trader trader-futures`; stock=mock data (`KIS_STOCK_MARKET=mock`), futures=real data + (paper) VirtualBroker fills (`KIS_FUTURES_MARKET=real`, paper via `TRADING_MODE=paper`); requires `STOCK_ORCHESTRATOR_ENABLED`/`FUTURES_ORCHESTRATOR_ENABLED` true (default); observability: `/metrics` (dashboard) + prometheus, key metrics `trading_pipeline_stage_latency_ms`, `trading_order_latency_ms`, `trading_ws_{disconnect,reconnect}_total`, `trading_rate_limit_penalty_total`, `trading_errors_total`.

- [ ] **Step 4: Commit**
```bash
cd /tmp/obs-impl
git add docker-compose.yml docs/runbooks/paper-trading-docker.md
git commit -m "feat(obs): trader-futures compose service (paper/live via stack env) + ops note"
git rev-parse HEAD
```

---

## Task 2: metrics.py — new metric defs + record methods

**Files:** Modify `services/monitoring/metrics.py`; Test `tests/unit/monitoring/test_observability_metrics.py` (create; check existing `tests/unit/monitoring/` layout first).

- [ ] **Step 1: Write failing tests**

Create `tests/unit/monitoring/test_observability_metrics.py`:
```python
"""Increment-1 observability metrics: definitions + record methods."""

from __future__ import annotations

from services.monitoring.metrics import MetricsCollector


def _c() -> MetricsCollector:
    return MetricsCollector()


def test_record_pipeline_stage_latency_does_not_raise() -> None:
    c = _c()
    c.record_pipeline_stage_latency("entry", 12.5)  # must not raise (best-effort)


def test_record_ws_reconnect_and_disconnect() -> None:
    c = _c()
    c.record_ws_reconnect("stock")
    c.record_ws_disconnect("futures")  # must not raise


def test_record_rate_limit_penalty() -> None:
    c = _c()
    c.record_rate_limit_penalty()  # must not raise


def test_record_order_latency_observes() -> None:
    c = _c()
    c.record_order_latency(42.0)  # already exists; smoke that it runs
```
(If `MetricsCollector()` needs args, inspect its `__init__` and adapt — these are smoke tests that the new methods exist + are exception-safe; assert via the prometheus registry value only if the existing monitoring tests show a pattern for it.)

- [ ] **Step 2: Run → FAIL** (`AttributeError` on the new methods).
Run: `cd /tmp/obs-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/monitoring/test_observability_metrics.py -q`

- [ ] **Step 3: Add metric definitions** — in `MetricsCollector.__init__`, in the `if HAS_PROMETHEUS:` block where the other histograms are defined (after `self.prom_order_latency = ...`, ~line 322), add:
```python
        self.prom_pipeline_stage_latency = Histogram(
            "trading_pipeline_stage_latency_ms",
            "Pipeline stage handler latency in ms",
            ["stage"],
            buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500],
        )
        self.prom_ws_reconnect_total = Counter(
            "trading_ws_reconnect_total",
            "WebSocket feed reconnect successes",
            ["feed"],
        )
        self.prom_ws_disconnect_total = Counter(
            "trading_ws_disconnect_total",
            "WebSocket feed disconnects",
            ["feed"],
        )
        self.prom_rate_limit_penalty_total = Counter(
            "trading_rate_limit_penalty_total",
            "KIS rate-limit penalty events (EGW00201 backoff)",
        )
```
(Confirm `Counter`/`Histogram` are imported at the top of the file — they are, since other counters/histograms exist.)

- [ ] **Step 4: Add record methods** — near `record_order_latency`/`record_error` (~line 419-440), add (each guarded by `HAS_PROMETHEUS`, exception-safe):
```python
    def record_pipeline_stage_latency(self, stage: str, latency_ms: float) -> None:
        """Pipeline stage handler latency (best-effort)."""
        if HAS_PROMETHEUS:
            self.prom_pipeline_stage_latency.labels(stage=stage).observe(latency_ms)

    def record_ws_reconnect(self, feed: str) -> None:
        """WS feed reconnect success (best-effort)."""
        if HAS_PROMETHEUS:
            self.prom_ws_reconnect_total.labels(feed=feed).inc()

    def record_ws_disconnect(self, feed: str) -> None:
        """WS feed disconnect (best-effort)."""
        if HAS_PROMETHEUS:
            self.prom_ws_disconnect_total.labels(feed=feed).inc()

    def record_rate_limit_penalty(self) -> None:
        """KIS rate-limit penalty event (best-effort)."""
        if HAS_PROMETHEUS:
            self.prom_rate_limit_penalty_total.inc()
```

- [ ] **Step 5: Run → PASS**; black + ruff + mypy(`services/monitoring/metrics.py`) + commit
```bash
cd /tmp/obs-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/monitoring/test_observability_metrics.py tests/unit/monitoring/ -q
/home/deploy/project/kis_unified_sts/.venv/bin/black services/monitoring/metrics.py tests/unit/monitoring/test_observability_metrics.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix services/monitoring/metrics.py tests/unit/monitoring/test_observability_metrics.py
/home/deploy/project/kis_unified_sts/.venv/bin/mypy services/monitoring/metrics.py 2>&1 | tail -3
git add services/monitoring/metrics.py tests/unit/monitoring/test_observability_metrics.py
git commit -m "feat(obs): pipeline-stage-latency histogram + ws/rate-limit counters"
git rev-parse HEAD
```
NOTE: prometheus default registry raises "Duplicated timeseries" if `MetricsCollector()` is constructed twice in one process (tests). If the existing monitoring tests hit this, follow their pattern (they likely use a fresh `CollectorRegistry` or a module singleton) — adapt the test to construct one collector or reuse `get_metrics_collector()`.

---

## Task 3: bottleneck wiring — pipeline stage latency + order latency

**Files:** Modify `services/trading/pipeline.py`, `services/trading/orchestrator.py`; Test `tests/unit/trading/...`.

- [ ] **Step 1: Pipeline stage latency (observe + slow-WARN)**

In `services/trading/pipeline.py::_run_stage_loop`, right after `latency = (time.monotonic() - start_time) * 1000` (in the success branch, after `metrics.total_latency_ms += latency`), add a best-effort metric observe + a threshold WARN:
```python
                _observe_stage_latency(stage.value, latency, interval)
```
And add a module-level helper (top of file, after imports + `logger`):
```python
_SLOW_STAGE_FACTOR = 1.0  # WARN when a stage exec exceeds factor × its interval


def _observe_stage_latency(stage: str, latency_ms: float, interval_s: float) -> None:
    """Best-effort: export stage latency + WARN when a stage falls behind cadence."""
    try:
        from services.monitoring.metrics import get_metrics_collector

        get_metrics_collector().record_pipeline_stage_latency(stage, latency_ms)
    except Exception:  # noqa: BLE001 — observability must never break the loop
        pass
    if latency_ms > interval_s * 1000 * _SLOW_STAGE_FACTOR:
        logger.warning(
            "stage %s slow: %.0fms (interval %.0fms)",
            stage,
            latency_ms,
            interval_s * 1000,
        )
```

- [ ] **Step 2: Test the pipeline instrumentation**

Add a unit test (`tests/unit/trading/test_pipeline_stage_latency.py`): call `_observe_stage_latency("entry", 9999.0, 1.0)` and assert a WARNING is logged (caplog) and it does not raise; call with a fast latency (`5.0, 1.0`) and assert NO warning. (Pure helper test — no full pipeline needed.)

- [ ] **Step 3: Activate order latency**

In `services/trading/orchestrator.py`: read `_execute_entry` (~6479-6605) and `_execute_exit` (~7362) and the `record_signal(...)` call sites (~6586, 7099). Bracket the actual order submit (`_submit_entry_order` / `_submit_exit_order`) with `t0 = time.monotonic()` … `order_latency_ms = (time.monotonic() - t0) * 1000`, then call `self._metrics.record_order_latency(order_latency_ms)` (guard `if self._metrics:`) and pass `latency_ms=order_latency_ms` into the corresponding `record_signal(...)`. Confirm `time` is imported (it is — `monotonic` used elsewhere). Do NOT change order placement logic or return values; only measure + record. If the `record_signal` signature/positional args make passing `latency_ms` awkward, inspect `metrics.py:372 record_signal(...)` for the keyword name and use it.

- [ ] **Step 4: Test order-latency activation**

Add/extend a focused test that an entry (or exit) execution calls `record_order_latency` with a positive value and passes a positive `latency_ms` to `record_signal`. Use the existing orchestrator test harness pattern (unbound method + fake `self` with a mock `_metrics`, mirroring `tests/unit/trading/test_orchestrator_*` if present). If wiring a full execute path is too heavy, at minimum assert the bracket helper records a positive latency via a mock collector.

- [ ] **Step 5: Run + format + commit**
```bash
cd /tmp/obs-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/trading/ -q
/home/deploy/project/kis_unified_sts/.venv/bin/black services/trading/pipeline.py services/trading/orchestrator.py tests/unit/trading/test_pipeline_stage_latency.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix services/trading/pipeline.py services/trading/orchestrator.py tests/unit/trading/test_pipeline_stage_latency.py
git add services/trading/pipeline.py services/trading/orchestrator.py tests/unit/trading/
git commit -m "feat(obs): pipeline stage-latency + activate order-latency metrics (+slow-stage WARN)"
git rev-parse HEAD
```

---

## Task 4: recovery wiring — WS counters, rate-limit recovery, redis errors

**Files:** Modify `shared/kis/stock_feed.py`, `shared/kis/websocket.py`, `shared/kis/client.py`, `services/trading/orchestrator.py`; Test `tests/unit/...`.

- [ ] **Step 1: WS counters (best-effort, no new logs)**

A best-effort helper (define once, e.g. in each feed module or reuse): `try: get_metrics_collector().record_ws_disconnect(feed) except Exception: pass`.
- `shared/kis/stock_feed.py`: at reconnect-success (~:486, after the existing INFO log) → `record_ws_reconnect("stock")`; at `_on_close` (~:439) → `record_ws_disconnect("stock")`.
- `shared/kis/websocket.py`: at `_on_close` (~:614) and/or `_run_websocket` exit (~:574) → `record_ws_disconnect("futures")`. (This adapter drives the futures feed; the disconnect counter makes the no-reconnect gap visible. The reconnect counter for futures comes in Increment 2.)
All wrapped so a missing collector never breaks the WS thread. No new log lines (existing connect/close logs suffice).

- [ ] **Step 2: Rate-limit recovery log + penalty counter**

In `shared/kis/client.py::_RateLimiter`:
- In `penalty()` (~:100-127), after the existing WARNING, add a best-effort `record_rate_limit_penalty()` (lazy guarded import + try/except).
- In `reset_backoff()` (~:129-132): capture the pre-reset `consecutive`; if it was > 0, add the ONE new log: `logger.info("Rate limit recovered after %d penalties", prev_consecutive)` before/after zeroing. (Optional gauge omitted — keep minimal.)
Use a lazy local import for the metrics collector to avoid any import-time coupling from `shared/kis/`; wrap in try/except.

- [ ] **Step 3: Redis error counting (metric only)**

In `services/trading/orchestrator.py`: at the candle-cache save catch site (~:6238-6240, the silent `pass`) and the market-data refresh catch (~:5140), add `self._metrics.record_error("redis")` (guard `if self._metrics:`). No new log (market-data refresh already WARNs; candle-cache becomes visible via the metric). Read the exact except blocks and insert the record_error call inside them.

- [ ] **Step 4: Tests**

- `tests/unit/` (kis): a test that `_RateLimiter.reset_backoff()` after a `penalty()` (consecutive>0) logs the recovery INFO (caplog) and that `penalty()`/`reset_backoff()` don't raise when no collector. (Construct `_RateLimiter` directly.)
- WS: a focused test (or extend existing feed tests) that the disconnect/reconnect paths call the collector counters via a patched `get_metrics_collector` (assert called with the right feed) and never raise when the collector is absent.
- redis: assert the orchestrator catch sites call `record_error("redis")` (mock `_metrics`) — or at minimum that the helper is invoked; if wiring the full path is heavy, a targeted test of the except block via the harness.

- [ ] **Step 5: Run + format + mypy + commit**
```bash
cd /tmp/obs-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/ -k "rate_limit or stock_feed or websocket or kis_client or orchestrator" -q
/home/deploy/project/kis_unified_sts/.venv/bin/black shared/kis/stock_feed.py shared/kis/websocket.py shared/kis/client.py services/trading/orchestrator.py tests/
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix shared/kis/stock_feed.py shared/kis/websocket.py shared/kis/client.py services/trading/orchestrator.py tests/
/home/deploy/project/kis_unified_sts/.venv/bin/mypy shared/kis/client.py 2>&1 | tail -3
git add shared/kis/stock_feed.py shared/kis/websocket.py shared/kis/client.py services/trading/orchestrator.py tests/
git commit -m "feat(obs): WS disconnect/reconnect counters + rate-limit recovery log + redis error metric"
git rev-parse HEAD
```

---

## Task 5: full gate + PR

- [ ] **Step 1: Targeted + regression**
```bash
cd /tmp/obs-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/monitoring/ tests/unit/trading/ -q
```

- [ ] **Step 2: Full gate (CI parity) + mypy**
```bash
cd /tmp/obs-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -m "not serial" -n auto -q --ignore=tests/performance -p no:randomly 2>&1 | grep -E "FAILED|ERROR|passed|failed" | tail -15
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -m serial -q 2>&1 | grep -E "FAILED|ERROR|passed|failed" | tail -6
/home/deploy/project/kis_unified_sts/.venv/bin/mypy services/monitoring/metrics.py services/trading/pipeline.py shared/kis/client.py 2>&1 | tail -6
```
Expected: green; mypy no new errors. (Known pre-existing local xdist flake: `test_handles_arbitrary_dicts`/`test_entry_path_100_symbols` — confirm any failure is NOT an obs test; CI is the gate.)

- [ ] **Step 3: docker compose config sanity**
```bash
cd /tmp/obs-impl && docker compose --profile trading config --services 2>&1 | grep -E "trader($|-futures)"
```
Expected: both `trader` and `trader-futures`.

- [ ] **Step 4: Push + PR**
```bash
cd /tmp/obs-impl
git push -u origin feat/paper-readiness-observability
gh pr create --base main --head feat/paper-readiness-observability \
  --title "feat(obs): trader-futures compose + paper-readiness observability (metrics + 2 logs)" \
  --body "$(cat <<'EOF'
## What
(1) A `trader-futures` docker-compose service so stock + futures paper run together via the
orchestrator; (2) metrics-primary observability for **bottleneck** (pipeline stage latency, order
latency) and **recovery** (WS disconnect/reconnect, rate-limit cooldown, redis errors), with exactly
**two new log lines** (pipeline slow-stage WARN, rate-limit recovery INFO).

## Why
Paper trading starts tomorrow (stock + futures). The compose `trader` ran only one asset; and there
was no per-stage/order latency visibility (the histograms existed but were never fed; the pipeline
computed stage latency only as a hidden average), and recovery events were partly silent
(rate-limit *recovery* unlogged; redis hot-path errors swallowed; no WS reconnect/disconnect counters).

## Compose (paper/live = STACK distinction)
`trader-futures` is **asset-pinned to futures**; paper vs live comes from the stack env
(`TRADING_MODE`/`KIS_REAL_TRADING`, e.g. `kis_paper` vs `kis_live` project) — the same service runs in
either stack. `trader` stays the stock daemon. Launch both: `docker compose --profile trading up -d
trader trader-futures`. Ops note: `docs/runbooks/paper-trading-docker.md`.

## Observability (metrics-primary; logs only where genuinely missing)
- **Bottleneck:** `trading_pipeline_stage_latency_ms{stage}` (new histogram, observed per stage exec)
  + slow-stage WARN; **activated** `trading_order_latency_ms` + `trading_signal_latency_ms` (were
  defined-but-never-fed) by recording the real submit latency.
- **Recovery:** `trading_ws_{disconnect,reconnect}_total{feed}` counters (stock + futures);
  `trading_rate_limit_penalty_total` + the one new INFO log on rate-limit *recovery* (silent before);
  `trading_errors_total{component="redis"}` on hot-path redis failures.
- **Exactly two new log lines** (operator directive: don't add logs where existing ones suffice).
- Additive only — no trading-logic change; every metric call is best-effort (a missing collector
  never breaks the hot path or a WS thread).

## Scope
Futures WS auto-reconnect is a separate PR (Increment 2) — here only the disconnect counter makes the
gap visible (the orchestrator already warns on staleness + auto-liquidates stale positions).

## How tested
metrics record-method smoke + exception-safety; pipeline slow-stage WARN threshold; order-latency
activation; rate-limit recovery log; WS/redis best-effort counters. Full gate green; mypy/ruff/black
clean.

Spec: `docs/superpowers/specs/2026-06-07-paper-readiness-observability-design.md`
Plan: `docs/superpowers/plans/2026-06-07-paper-readiness-observability.md`

## Follow-up
Increment 2: futures WS exponential-backoff auto-reconnect (mirror stock_feed) + its reconnect counter.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 5: Run code review** — `/code-review` on the PR.

---

## Self-Review (plan vs spec)
**Coverage:** §4.1 compose → Task 1; §4.7 metric defs/methods → Task 2; §4.2 pipeline latency + §4.3 order latency → Task 3; §4.4 WS counters + §4.5 rate-limit + §4.6 redis → Task 4; §6 testing → Tasks 2-4; §8 acceptance → all. ✓
**Two-new-logs invariant:** only the pipeline slow-stage WARN (Task 3) and rate-limit recovery INFO (Task 4) add log lines; everything else is metrics. ✓
**Best-effort:** every collector call is guarded (try/except or `if self._metrics:`); WS/rate-limiter use lazy guarded imports so `shared/kis` never breaks on a missing collector. ✓
**Placeholder scan:** complete code for metrics defs/methods, compose service shape, and the pipeline helper; the orchestrator/feed/client wiring steps give exact anchors + the lines to add and instruct reading the surrounding except/log blocks (not guessing). ✓
**paper/live:** `trader-futures` pins only the asset; `TRADING_MODE`/`KIS_REAL_TRADING` from stack env. ✓