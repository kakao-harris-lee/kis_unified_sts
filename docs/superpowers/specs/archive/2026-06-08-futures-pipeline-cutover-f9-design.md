# F-9 — Futures Decoupled Pipeline: Cutover Runbook + Dormant Compose Wiring

**Date:** 2026-06-08
**Status:** Approved (operator chose "런북 + dormant compose 배선")
**Scope:** Single subsystem — `docker-compose.yml` (dormant futures pipeline profiles) +
`.env.{paper,live}.example` (mode knobs) + a cutover runbook + a compose-shape test.

This is the **autonomous** half of F-9. The **operator** half — actually flipping
to live (Phase-5 Gate 1–3 + written approval, `futures_live.enabled: true`, deleting
`futures:live:suspended`, starting the live profiles) — is documented in the runbook
but NOT performed here.

---

## Background

F-1..F-8 (PRs #424–#431) made the decoupled futures daemon chain fully functional
end-to-end in shadow/live with a double-trade guard, but **dormant**: the daemons are
not registered in `docker-compose.yml` and their mode env vars are unset. Today
futures trades only via the in-process `TradingOrchestrator` (`trader-futures`).

The chain (verified read-only, 2026-06-08):

| Daemon | Module | Mode env | Values | Feed | Needs |
|---|---|---|---|---|---|
| decision_engine | `services.decision_engine.main` | `FUTURES_STRATEGY_DAEMON` | off/shadow/live (def off) | consumes `raw_data` (StreamConsumerFeed) | redis, `FUTURES_STRATEGY_SYMBOL` |
| risk_filter | `services.risk_filter.main` | `FUTURES_RISK_FILTER` | off/shadow/live (def off) | consumes `signal.candidate.futures[.shadow]` | redis |
| order_router | `services.order_router.main` | `FUTURES_ORDER_ROUTER` | **off/paper/live** (def off) | **self-feeds** own KIS futures WS (always real) | redis, KIS futures creds |
| futures_monitor | `services.futures_monitor.main` | `FUTURES_MONITOR_DAEMON` | off/shadow/live (def off) | consumes `raw_data` + fill/final streams | redis, Telegram (live) |
| kill_switch | `services.kill_switch.main` | **config-only** (`kill_switch.yaml::enabled`, def true) | live-only | none (runtime state) | redis, Telegram |
| market_ingest (futures) | `services.market_ingest.main` | `INGEST_ASSET=futures` | — | owns KIS futures WS → publishes `raw_data` | redis, KIS futures creds |

Key facts that shape the design:

1. **Mode asymmetry:** decision/risk/monitor take `shadow|live`; order_router takes
   `paper|live` (paper → `.shadow` streams). So a single verbatim mode knob can't
   cover all four — order_router needs its own.
2. **Shadow reuses the orchestrator's `raw_data`.** `TradingOrchestrator` already
   publishes futures ticks to `raw_data` via `TickStreamPublisher`
   (`orchestrator.py:1835`). So during shadow validation the decoupled consumers read
   the orchestrator's stream — **no separate futures-ingest is needed in shadow**
   (mirrors stock M5d Gate 1). futures-ingest is only for cutover, when `trader-futures`
   stops owning the WS.
3. **kill_switch is config-gated and live-only.** It reads the *live* `risk:state:futures`
   and sends *real* futures Telegram, so it must be isolated from shadow runs → its own
   profile.
4. **Dual-WS caveat.** order_router self-feeds a real KIS futures WS even in paper mode.
   During shadow that is a 2nd futures WS alongside the orchestrator's (= 2 concurrent on
   one KIS account); at cutover it's futures-ingest's WS + order_router's WS (= 2). KIS
   per-account WS limits must be verified — documented as an operator pre-flight item.

---

## Design

### Compose profiles (mirror stock's `stock-ingest` / `stock-pipeline`)

- **`futures-ingest`** — `futures-market-ingest` only. The KIS futures WS owner /
  `raw_data` producer for the **cutover** (not started in shadow).
- **`futures-pipeline`** — `futures-decision-engine`, `futures-risk-filter`,
  `futures-order-router`, `futures-monitor`. The chain; mode via env (shadow default).
- **`futures-killswitch`** — `futures-kill-switch` only. Live-only safety daemon,
  brought up at cutover after verifying `kill_switch.yaml`.

All services are profile-gated → **dormant** until a profile is explicitly passed to
`docker compose up`. No live behavior changes; fully reversible (`docker compose stop`
/ remove the services).

### Mode knobs

- **`FUTURES_PIPELINE_MODE`** (default `shadow`) → drives `FUTURES_STRATEGY_DAEMON`,
  `FUTURES_RISK_FILTER`, `FUTURES_MONITOR_DAEMON` (all accept `shadow|live`).
- **`FUTURES_ORDER_ROUTER_MODE`** (default `paper`) → drives `FUTURES_ORDER_ROUTER`
  (accepts `paper|live`). Separate because of the mode asymmetry.
- **`FUTURES_STRATEGY_SYMBOL`** (default empty) → decision_engine's KOSPI200 mini
  front-month code; required for shadow/live, must match the ingest/orchestrator symbol.
  Empty default keeps the dormant service harmless (it would error only if started
  without a symbol).
- Minor knobs with safe defaults: `FUTURES_TICK_STREAM` (`raw_data`),
  `FUTURES_MONITOR_STATUS_INTERVAL` (`5`), `FUTURES_INGEST_REFRESH_SECONDS` (`3600`),
  `KIS_FUTURES_EQUITY_KRW` (`100000000`).

Cutover = set `FUTURES_PIPELINE_MODE=live` **and** `FUTURES_ORDER_ROUTER_MODE=live`,
`FUTURES_ORCHESTRATOR_ENABLED=false` on `trader-futures` (the F-8 double-trade guard),
and bring up all three profiles. The runbook lists the exact two-knob command.

### Shared anchor

Rename the generic `x-stock-pipeline-service` anchor to **`x-pipeline-service`** and
repoint both the stock and the new futures pipeline services. The anchor carries no
stock-specific content (build/restart/volumes/depends-on-redis/networks/logging), so
this is a pure DRY rename — `docker compose config` output is byte-identical for the
stock services (validated). Avoids duplicating ~15 lines per the project's DRY rule.

### Env env-vars passed per service

- ingest: `*redis-runtime-env`, `*runtime-storage-env`, `*kis-runtime-env` +
  `INGEST_ASSET=futures`, `INGEST_REFRESH_SECONDS`.
- decision_engine: `*redis-runtime-env`, `*runtime-storage-env` +
  `FUTURES_STRATEGY_DAEMON`, `FUTURES_STRATEGY_SYMBOL`, `FUTURES_TICK_STREAM`.
- risk_filter: `*redis-runtime-env`, `*runtime-storage-env` + `FUTURES_RISK_FILTER`.
- order_router: `*redis-runtime-env`, `*runtime-storage-env`, `*kis-runtime-env` +
  `FUTURES_ORDER_ROUTER` (needs KIS creds — self-feeds real WS).
- futures_monitor: `*redis-runtime-env`, `*runtime-storage-env`, `*alert-runtime-env` +
  `FUTURES_MONITOR_DAEMON`, `FUTURES_MONITOR_STATUS_INTERVAL`, `FUTURES_TICK_STREAM`.
- kill_switch: `*redis-runtime-env`, `*runtime-storage-env`, `*alert-runtime-env` +
  `KIS_FUTURES_EQUITY_KRW`.

### Runbook

`docs/runbooks/futures-pipeline-cutover-f9.md`, mirroring
`docs/runbooks/stock-pipeline-cutover-m5d.md`:
- Profiles overview + the dormant principle.
- Gate 0 prerequisites (env files, redis/dashboard up, trader-futures running, modes default).
- Gate 1 shadow validation (≥3–5 trading days): start **futures-pipeline only** (reuse
  orchestrator `raw_data`), verify `.shadow` dashboard keys / no backlog / no restart
  loop; dual-WS caveat.
- Gate 2 operator approval **+ Phase-5 Gate 1–3 + written approval** (hard prerequisite,
  cross-link `docs/runbooks/phase5-verification.md`).
- Cutover sequence (off-hours): flatten/clear paper state → stop `trader-futures` →
  set `FUTURES_ORCHESTRATOR_ENABLED=false` → (live only) `futures_live.enabled: true` +
  `redis-cli -n 1 del futures:live:suspended` → start `futures-ingest` +
  `futures-pipeline` (live) + `futures-killswitch` → post-cutover verify → first session
  observation.
- Rollback triggers + rollback (stop futures profiles, re-enable orchestrator via
  `FUTURES_ORCHESTRATOR_ENABLED=true`, restart `trader-futures`).
- Notes: positions keys (`futures:monitor:positions`, `risk:state:futures[:shadow]`,
  `trading:futures:*[:shadow]`), the F-8 double-trade guard, the dual-WS caveat,
  kill_switch config gating, and that automated verify/rollback scripts are a follow-up.

### Tests

Extend `tests/unit/test_compose_runtime_env.py`:
- `test_futures_pipeline_compose_services_are_profile_gated` — mirror the stock test:
  assert each futures service's profile, command, redis dependency, and mode env
  interpolation (`${FUTURES_PIPELINE_MODE:-shadow}` / `${FUTURES_ORDER_ROUTER_MODE:-paper}`),
  ingest `INGEST_ASSET=futures` + KIS creds, order_router KIS creds, monitor Telegram,
  kill_switch profile + Telegram.
- Extend `test_paper_and_live_env_templates_separate_kis_markets` to assert
  `FUTURES_PIPELINE_MODE=shadow`, `FUTURES_ORDER_ROUTER_MODE=paper`,
  `FUTURES_STRATEGY_SYMBOL` present in both templates.

The `test` job (yaml.safe_load based) is the merge gate. `docker compose config -q`
is run locally as a sanity check (docker not guaranteed in CI).

---

## Real-money safety

- Every new service is **profile-gated and dormant** — `docker compose up` without the
  new profiles starts nothing new. The operator's running stack is unaffected.
- Defaults are the **safe** end: pipeline `shadow`, order_router `paper` (synthetic fills,
  structurally no real orders per F-3), kill_switch isolated in its own profile.
- Going live requires the operator to (a) flip two mode knobs to `live`, (b) flip the F-8
  `FUTURES_ORCHESTRATOR_ENABLED=false` guard, (c) flip `futures_live.enabled: true` and
  clear `futures:live:suspended`, and (d) pass Phase-5 Gate 1–3 + written approval. No
  single change here can start live futures trading.
- The anchor rename is a byte-identical YAML refactor (no behavior change).

## Out of scope

- No code changes to any daemon (they're already complete from F-1..F-8).
- No automated futures cutover verify/rollback scripts (stock has them; a futures
  port is a documented follow-up — the runbook uses inline commands).
- No change to the stock pipeline behavior (anchor rename is byte-identical).
- Performing the actual cutover (operator-gated).
