# Paper-Readiness: trader-futures + Observability (Increment 1) — Design

**Status:** Approved (design) — 2026-06-07
**Scope:** Enable a docker-compose paper-trading run of BOTH stock + futures via the (proven) orchestrator path, and add bottleneck + recovery observability (logs + Prometheus metrics) so each module's latency and recovery behavior is visible during the multi-day run. Increment 2 (futures WS auto-reconnect) is a separate PR.

---

## 1. Problem

Paper trading runs via `TradingOrchestrator` (`sts trade start --asset {stock|futures} --paper`), but:
1. **Compose runs one asset.** The `trader` service runs a single `TRADING_ASSET_CLASS` (default stock); there is no way to run stock AND futures paper together via docker-compose.
2. **Observability gaps.** There is no single trading cycle — two concurrent cadences run: `_market_data_loop` (~2s) and `TradingPipeline` (4 stage loops: regime 60s / entry 1s / monitoring 0.1s / exit 0.5s). Per-stage latency IS computed (`pipeline.py:322`) but only kept as a hidden in-memory average — never logged or exported. The `trading_order_latency_ms` / `trading_signal_latency_ms` histograms exist but are never fed (`record_signal` always passes `latency_ms=0`). Recovery events are partly silent: stock WS reconnect logs exist but there's no counter; the rate-limiter logs cooldown *entry* but recovery (`reset_backoff`) is silent; redis errors in hot paths are swallowed without `record_error`. So an operator cannot see where time goes (bottleneck) or how often/when the system recovers.

(Pre-flight already confirmed: compose config valid; KIS stock+futures creds set; `STOCK_/FUTURES_ORCHESTRATOR_ENABLED` absent → default true → orchestrator path allowed for both; `TRADING_MODE` default paper.)

## 2. Goal

(a) A `trader-futures` compose service so stock + futures paper run side by side via the orchestrator. (b) High-value, low-overhead instrumentation — **logs AND Prometheus metrics** — for **bottleneck** (per-stage + order latency) and **recovery** (WS disconnect/reconnect, rate-limit cooldown enter/exit, redis errors). Additive only; no behavior change to trading logic.

## 3. Approach (decided)

- **paper/live = compose STACK distinction (operator clarification).** The docker-compose daemon split is **live-trading vs paper-trading** (e.g. a `kis_paper` project vs a `kis_live` project), driven by `TRADING_MODE`/`KIS_REAL_TRADING` env at the stack level. The **asset** (stock/futures) is a within-stack split. So `trader-futures` pins only `TRADING_ASSET_CLASS=futures` and inherits `TRADING_MODE`/`KIS_REAL_TRADING` from the stack — the **same service definition serves the paper stack (paper fills) and the live stack (real orders)**. We do NOT hardcode paper.
- **Compose:** add `trader-futures` (mirror `trader`, asset-pinned to futures, mode via env), keep `trader` for stock. Document the launch (paper stack today; same compose, live env later).
- **Observability — metrics-primary, logs only at genuine gaps (operator clarification: don't add logs where existing ones already suffice).** Extend `services/monitoring/metrics.py` (already scraped by prometheus + dashboard `/metrics`) as the primary observability. Add NEW log lines ONLY where there is no existing log AND it's high-value: (a) pipeline **slow-stage WARNING** (threshold-gated, rare — no per-stage log exists), (b) rate-limit **recovery/exit INFO** (`reset_backoff` is silent today). Do NOT add per-exec DEBUG logs, and do NOT duplicate already-present logs (market-data fetch, staleness warns, feed drops, stock-WS reconnect INFO, rate-limit *enter* WARN, position-recovery count, failover recovery — all already logged → metrics only).
- **Futures WS auto-reconnect is Increment 2** — here we only add the disconnect *counter* (the existing "Connection closed" log already covers the log side); the orchestrator already warns on staleness + auto-liquidates stale positions, so the gap is observable day-1.

## 4. Design

### 4.1 Compose: `trader-futures`

Add a service mirroring `trader` (`docker-compose.yml`), in profile `trading`, **asset-pinned to futures, mode inherited from the stack** (so the same definition serves the paper stack and the live stack):
```yaml
  trader-futures:
    build: { context: ., dockerfile: Dockerfile }
    container_name: ${COMPOSE_PROJECT_NAME:-kis}-trader-futures
    restart: unless-stopped
    profiles: ["trading"]
    command: ["bash", "scripts/docker/trading_loop_entrypoint.sh"]
    extra_hosts: ["host.docker.internal:host-gateway"]
    environment:
      <<: [*redis-runtime-env, *runtime-storage-env]
      # identical KIS_* / TELEGRAM_* / OPENAI_API_KEY block as `trader`,
      # incl. KIS_REAL_TRADING / KIS_FUTURES_MARKET (stack-level paper/live).
      TRADING_MODE: "${TRADING_MODE:-paper}"          # paper/live = STACK env (NOT hardcoded)
      TRADING_ASSET_CLASS: "futures"                  # asset-pinned (the only diff vs `trader`)
      TRADING_STRATEGY: "${FUTURES_TRADING_STRATEGY:-}"
      TRADING_INITIAL_CAPITAL: "${TRADING_INITIAL_CAPITAL:-10000000}"
      TRADING_RUN_MODE: "${TRADING_RUN_MODE:-daemon}"
    volumes: [ ... same as trader ... ]
    depends_on: { redis: { condition: service_healthy } }
    networks: [trading-network]
    logging: { driver: json-file, options: { max-size: 10m, max-file: 3 } }
```
`trader` stays the stock daemon (`TRADING_ASSET_CLASS: "${TRADING_ASSET_CLASS:-stock}"` unchanged). **paper vs live is the stack distinction** (a paper-stack run sets `TRADING_MODE=paper`/`KIS_REAL_TRADING=false`; the live stack sets `TRADING_MODE=live`/`KIS_REAL_TRADING=true`) — the same `trader`+`trader-futures` services run in either. Operator launches both assets in a stack: `docker compose --profile trading up -d trader trader-futures`. Both require `*_ORCHESTRATOR_ENABLED` true (default). Short ops note (`docs/runbooks/`): the launch command + paper/live = which stack/env, stock=mock data, futures=real data + (paper) VirtualBroker fills.

### 4.2 Bottleneck — pipeline stage latency (metric + slow-stage WARN)

`services/trading/pipeline.py` already computes `latency = (monotonic()-start)*1000` per handler exec (~line 312-326). Add at that point:
- **Metric (primary):** `trading_pipeline_stage_latency_ms` Histogram, label `stage` (regime/entry/monitoring/exit), observed every exec. Defined in `metrics.py`; best-effort via the metrics collector. Buckets tuned to the cadences (e.g. 1,5,10,25,50,100,250,500,1000,2500 ms).
- **New log (gap):** WARNING `stage %s slow: %.0fms (interval %.0fms)` when `latency > slow_factor × interval_ms` (stage falling behind its cadence; `slow_factor` default 1.0). **No per-exec DEBUG log** (operator directive — metric covers the normal-case trend).

### 4.3 Bottleneck — activate order latency (metric only)

`services/trading/orchestrator.py` `_execute_entry` (~6556, around `_submit_entry_order`) and `_execute_exit` (~7362): bracket the order submit with `monotonic()` → `latency_ms`; call the existing `self._metrics.record_order_latency(latency_ms)` (`metrics.py:419`, feeds the dormant `trading_order_latency_ms`) and pass the real `latency_ms` into the existing `record_signal(...)` calls (~6586, 7099) so `trading_signal_latency_ms` populates too. **No new log** (the histogram + Grafana alerting covers slow orders; no order-latency log exists to duplicate, and the operator asked not to add logs where the metric suffices). No change to order logic/return values.

### 4.4 Recovery — WS disconnect/reconnect (metric counters only)

New counters in `metrics.py`: `trading_ws_reconnect_total{feed}`, `trading_ws_disconnect_total{feed}`. **No new logs** — stock reconnect already logs INFO (`stock_feed.py:486`) and futures already logs "Connection closed" (`websocket.py:614`); we only add the counters so reconnect/disconnect *rates* are visible over the run.
- **Stock** (`shared/kis/stock_feed.py`): `record_ws_reconnect("stock")` at reconnect-success (~:486); `record_ws_disconnect("stock")` at `_on_close` (~:439).
- **Futures** (`shared/kis/websocket.py` `_on_close` ~:614 / `_run_websocket` exit ~:574, used by `futures_feed.py`): `record_ws_disconnect("futures")`. (The reconnect FIX + its counter on success = Increment 2.)
Counters reached via the metrics collector (`get_metrics_collector()`), guarded so a missing collector never breaks the feed/WS thread (best-effort).

### 4.5 Recovery — rate-limit cooldown enter/exit (counter + the one missing log)

`shared/kis/client.py` `_RateLimiter`:
- Enter (penalty ~:100-127) **already logs WARNING** — add only a `trading_rate_limit_penalty_total` Counter increment (best-effort).
- Exit (`reset_backoff` ~:129-132) is **silent today** — add the **one genuinely-missing log**: INFO `Rate limit recovered after N penalties` when it clears a nonzero `consecutive` (+ optional gauge `trading_rate_limit_penalized` 0/1). Logs are the must-have here (the recovery event is otherwise invisible); metric best-effort.

### 4.6 Recovery — redis error counting (metric only)

`services/trading/orchestrator.py` hot-path redis catch sites (candle-cache save ~:6238-6240 silent `pass`; market-data refresh ~:5140 generic WARN): add `self._metrics.record_error("redis")` (`metrics.py:437`, feeds `trading_errors_total{component}`) so the silent/grep-only failures become a visible counter. **No new log** (market-data refresh already WARNs; the candle-cache silent skip becomes visible via the metric — operator directive to prefer metric over a new log line).

### 4.7 New/activated metric inventory (`services/monitoring/metrics.py`)

- ADD: `trading_pipeline_stage_latency_ms` (Histogram, label `stage`) + `record_pipeline_stage_latency(stage, ms)`.
- ADD: `trading_ws_reconnect_total{feed}` + `trading_ws_disconnect_total{feed}` + `record_ws_reconnect(feed)` / `record_ws_disconnect(feed)`.
- ADD: `trading_rate_limit_penalty_total` (Counter) + optional `trading_rate_limit_penalized` (Gauge) + `record_rate_limit_penalty()` / `set_rate_limit_penalized(bool)`.
- ACTIVATE: `record_order_latency` + real `record_signal(latency_ms=...)` (no new metric).
- REUSE: `record_error("redis")` (no new metric).

## 5. Safety / overhead

- **Additive only** — no change to trading decisions, order logic, stream names, or daemon behavior. All instrumentation is timing/logging/metrics around existing calls.
- **Low overhead** — `monotonic()` + a histogram observe per stage/order is µs; DEBUG logs are off at prod INFO level; WARN/INFO recovery logs are rare events. Monitoring stage runs at 0.1s — its DEBUG log/observe is fine (DEBUG off in prod).
- **Best-effort metrics** — every metric call is guarded (missing/None collector never breaks the hot path or the WS thread).
- **Both assets covered** — pipeline/orchestrator/client instrumentation is shared by stock + futures; WS instrumentation is per-feed (stock_feed vs futures websocket).

## 6. Testing

- **metrics.py:** new metric/record-method unit tests (`tests/unit/monitoring/...`): each new metric defined + record method increments/observes (use the prometheus client registry or the collector's test hooks).
- **pipeline.py:** stage-latency observe + slow-stage WARN fires above threshold (inject a slow handler; assert the metric observed + a WARNING logged via caplog).
- **orchestrator order latency:** assert `record_order_latency` called with a positive latency on an entry/exit (unbound-method + fake-self, or the existing orchestrator test harness) — or at minimum a focused test that the execute path passes a real latency to `record_signal`.
- **client.py rate limiter:** `reset_backoff` after penalties logs the recovery INFO + increments the penalty counter on penalty (caplog + metric).
- **stock_feed / futures websocket:** disconnect/reconnect paths call the counters (mock collector) + futures disconnect logs the WARNING.
- **compose:** `docker compose --profile trading config` renders with `trader` + `trader-futures`; `trader-futures` pinned to futures + paper (assert via the rendered config in a test or a documented manual check).
- Full CI-parity gate; mypy on changed `shared/`/`services/monitoring/`; ruff/black.

## 7. Out of scope

- **Futures WS auto-reconnect** (Increment 2) — here only the disconnect *visibility*.
- Decoupled-daemon instrumentation (orchestrator paper path only).
- Grafana dashboards / alerts (metrics are exposed; dashboards are an ops follow-up).
- Changing cadences/thresholds of the existing staleness/feed-drop warns (already done).

## 8. Acceptance criteria

1. `docker compose --profile trading config` includes `trader` (stock) + `trader-futures` (asset-pinned futures, mode via `TRADING_MODE`/`KIS_REAL_TRADING`); the same services run in the paper stack and the live stack (paper/live = stack-level env, not hardcoded).
2. Per-stage pipeline latency is exported as `trading_pipeline_stage_latency_ms{stage}`; a slow-stage WARNING fires above the threshold (the only new bottleneck log).
3. Order latency populates `trading_order_latency_ms` + `trading_signal_latency_ms` (activated; metric only).
4. `trading_ws_{disconnect,reconnect}_total{feed}` counters increment for stock + futures (no new logs — existing connect/close logs suffice).
5. Rate-limit cooldown enter increments `trading_rate_limit_penalty_total`; exit emits the one new INFO recovery log (silent before); redis hot-path errors feed `trading_errors_total{component="redis"}` (no new log).
6. **New log lines = exactly two** (pipeline slow-stage WARN, rate-limit recovery INFO); everything else is metrics. Additive only (no trading-logic change); all metric calls best-effort; tests per §6; full gate green; mypy/ruff/black clean.
