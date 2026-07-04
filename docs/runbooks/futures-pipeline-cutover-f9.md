# Runbook: Futures Decoupled Pipeline Cutover (F-9, Compose)

Flip futures trading from the in-process `trader-futures` orchestrator loop to the
decoupled daemon chain: decision_engine → risk_filter → order_router →
futures_monitor (+ kill_switch for live). Operational risks: silent stop, double
trading, stale market data, and **dual KIS futures WebSocket** connections on one
account.

This runbook is the operator half of F-9. The compose wiring is dormant
(default-off profiles); going live is gated.

Spec: `docs/superpowers/specs/archive/2026-06-08-futures-pipeline-cutover-f9-design.md`
Stock analogue: `docs/runbooks/stock-pipeline-cutover-m5d.md`
Host-redis cutover analogue: `docs/runbooks/cron-to-compose-cutover.md`
Phase-5 gates (HARD prerequisite for live): `docs/runbooks/phase5-verification.md`

## Redis access (paper vs live)

The **paper** stack uses a **single host Redis** — `host.docker.internal:6379`,
**db 1**, **no password** (established by the 2026-06-09 cron→compose cutover).
There is **no `kis_paper-redis` container**: compose runs the stack with `--no-deps`
against host Redis (`.env.paper`: `REDIS_URL=redis://host.docker.internal:6379/1`,
`REDIS_PASSWORD=` empty). So in **paper**, run Redis commands **directly on the
host**, not via `docker compose exec redis`:

```bash
redis-cli -p 6379 -n 1 <cmd>          # paper — host Redis, db 1, no auth
```

The **live** stack is isolated from paper and its Redis topology differs (separate
clone/host per `docs/runbooks/paper-live-code-separation.md`). **Confirm the live
Redis (compose `redis` service vs host port) at the live cutover** and adjust the
`.env.live` examples below accordingly — the `docker compose --env-file .env.live
exec -T redis …` form only works if the live stack actually runs a compose `redis`
service. All commands target **db 1** (CLAUDE.md: Redis DB 1 전용).

## Compose Profiles

- `trading`: in-process orchestrator services (`trader`, `trader-futures`).
- `futures-pipeline`: `futures-decision-engine`, `futures-risk-filter`,
  `futures-order-router`, `futures-monitor`.
- `futures-ingest`: `futures-market-ingest`, the KIS futures WebSocket owner and
  `raw_data` producer.
- `futures-killswitch`: `futures-kill-switch`, the live-only safety daemon
  (config-gated by `config/kill_switch.yaml::enabled`).

`futures-market-ingest` is separate on purpose. **Do not run it while
`trader-futures` still owns the KIS futures WebSocket feed** — during shadow the
decoupled chain reuses the orchestrator's `raw_data` stream instead.

### Mode knobs

- `FUTURES_PIPELINE_MODE` (default `shadow`): drives decision_engine, risk_filter,
  futures_monitor (`shadow` | `live`).
- `FUTURES_ORDER_ROUTER_MODE` (default `paper`): drives order_router
  (`paper` | `live`). Separate knob — order_router uses `paper` (synthetic fills,
  `.shadow` streams) where the others use `shadow`.
- `FUTURES_TRADING_PRODUCT` (default `mini`): futures front-month product
  (`mini` | `kospi200`). All decoupled futures services and the orchestrator
  resolve the same current contract through `shared.execution.futures_instrument`.
- `FUTURES_STRATEGY_SYMBOL`: optional explicit contract-code override. Leave it
  empty for automatic quarterly rollover; set it only when deliberately pinning
  shadow/live to a specific contract. If set, it must match what ingest publishes.

## Gate 0 — Prerequisites

- `.env.paper` / `.env.live` filled (copy from `.env.paper.example` /
  `.env.live.example`).
- Core stack up (paper uses host Redis — do **not** start a compose `redis`):
  `docker compose --env-file .env.paper up -d dashboard strategy-builder-ui caddy stream-exporter`.
  (Confirm host Redis is reachable: `redis-cli -p 6379 -n 1 ping` → `PONG`.)
- `trader-futures` running normally:
  `docker compose --env-file .env.paper --profile trading up -d trader-futures`.
- `FUTURES_PIPELINE_MODE=shadow` and `FUTURES_ORDER_ROUTER_MODE=paper` in the env
  file, or unset so compose defaults to shadow/paper.
- `FUTURES_TRADING_PRODUCT=mini`, or unset to use the same default. Leave
  `FUTURES_STRATEGY_SYMBOL` empty unless the validation intentionally pins a
  specific contract.
- Review `config/kill_switch.yaml::enabled` (kill_switch is live-only; it is NOT
  started during shadow).

## Gate 1 — Shadow Validation (≥ 3–5 Trading Days)

Start the decoupled futures consumers **without** the ingest daemon — they reuse
the `raw_data` ticks the running `trader-futures` orchestrator already publishes:

```bash
docker compose --env-file .env.paper --profile futures-pipeline up -d \
  futures-decision-engine futures-risk-filter futures-order-router futures-monitor
```

Each trading day, verify:

- `:shadow` dashboard keys (`trading:futures:positions:shadow`,
  `trading:futures:trades:shadow`, `trading:futures:signals:shadow`) show decoupled
  signals/fills/positions.
- `risk:state:futures:shadow` populates (PseudoOCO is its only writer).
- No unbounded backlog on the shadow streams (`signal.candidate.futures.shadow`,
  `signal.final.futures.shadow`, `order.fill.futures.shadow`):
  `redis-cli -p 6379 -n 1 xlen signal.final.futures.shadow` (paper; host Redis).
- No restart loop:
  `docker compose --env-file .env.paper ps futures-decision-engine futures-risk-filter futures-order-router futures-monitor`.
- Sanity: compare shadow decisions with the orchestrator's paper trades for
  **direction**, not exact fill parity.

When running `scripts/ops/futures_cutover_verify.py --strict`, pass one or more
actual shadow-validation notes/logs with `--gate1-evidence`. The verifier only
does a simple file check: evidence files must be non-empty and must not still
contain obvious template markers such as `TODO`, `TBD`, or `placeholder`.
Include real trading dates and the observations above; automation cannot prove
multi-day shadow operation without operator-supplied evidence.

Optional bundle compiler: record the Gate 1 / Gate 2 / Phase 5 evidence metadata
in JSON or YAML and run:

```bash
python scripts/ops/futures_evidence_bundle.py path/to/f9-evidence.yaml --json --strict
```

The bundle validator rejects missing fields and placeholder values, then emits a
JSON report with `f9_gate1`, `f9_gate2`, and `phase5_small_live` sections. It
expects real values for `trading_dates`, restart/backlog/dashboard/direction
checks, kill-switch drill status, signal count, backtest tracking error,
drawdown/slippage checks, and `operator_approval_ref`. For Phase 5, the bundle
also enforces at least 100 signals and absolute backtest tracking error <= 20%.
Passing the bundle check does **not** replace the actual shadow logs, Phase-5
artifacts, or written operator approval.

**DUAL-WS CAVEAT.** `futures-order-router` self-feeds a real KIS futures WebSocket
even in paper mode (KIS 모의투자 serves no futures realtime feed). During shadow
that is a 2nd futures WS alongside the orchestrator's = 2 concurrent on one KIS
account. Confirm KIS allows this for your account, or run shadow in a window where
`trader-futures` is paused. If order_router logs WS connect/auth failures, this is
the likely cause.

## Gate 2 — Operator Approval + Phase-5

Record the date and a one-line shadow validation summary before proceeding.

**HARD PREREQUISITE:** Phase-5 Gate 1–3 + operator written approval per
`docs/runbooks/phase5-verification.md`. Do not run the live cutover without it.

## Cutover Sequence (Run Off-Hours)

1. Flatten and clear disposable state:

   ```bash
   python scripts/trading/flatten_all.py --asset futures        # optional
   docker compose --env-file .env.paper --profile trading stop trader-futures
   # paper — host Redis (db 1, no auth). For live, target the live stack's Redis.
   redis-cli -p 6379 -n 1 del futures:monitor:positions trading:futures:positions risk:state:futures
   ```

2. Block the orchestrator futures path (F-8 double-trade guard). In the env file:

   ```bash
   FUTURES_ORCHESTRATOR_ENABLED=false
   ```

   This makes `sts trade start --asset futures` refuse, so `trader-futures` cannot
   re-trade alongside the decoupled chain.

   ⚠️ Keep `trader-futures` **stopped** (from step 1). With the guard `false`, do
   **not** `up -d trader-futures` — the entrypoint's `sts trade start --asset
   futures` refuses and exits, and under `restart: unless-stopped` the container
   would restart-loop (same failure class as the 2026-06-09 after-close loop fixed
   in #450; see `docs/runbooks/cron-to-compose-cutover.md` appendix). Re-enable +
   restart it only on rollback.

3. **(live only)** Enable real order placement — **three** independent gates, all
   required (see "Live-path requirements" below for why):

   - `config/futures_live.yaml::enabled: true` (LiveModeGuard)
   - `docker compose --env-file .env.live exec -T redis sh -c 'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli -n 1 del futures:live:suspended'`
   - `FUTURES_EXECUTOR_TRADING_MODE=REAL` in `.env.live` (the OrderExecutor real/paper
     gate; default `PAPER` **silently simulates** even when the router is in live mode).

   For a **paper** cutover, skip this step and keep `FUTURES_ORDER_ROUTER_MODE=paper`
   and `FUTURES_EXECUTOR_TRADING_MODE=PAPER`.

4. Start the decoupled chain + ingest (+ kill_switch for live):

   ```bash
   FUTURES_PIPELINE_MODE=live FUTURES_ORDER_ROUTER_MODE=live FUTURES_EXECUTOR_TRADING_MODE=REAL \
     docker compose --env-file .env.live \
       --profile futures-ingest --profile futures-pipeline --profile futures-killswitch up -d \
       futures-market-ingest futures-decision-engine futures-risk-filter \
       futures-order-router futures-monitor futures-kill-switch
   ```

   Paper cutover: use `--env-file .env.paper`, keep `FUTURES_ORDER_ROUTER_MODE=paper`
   and `FUTURES_EXECUTOR_TRADING_MODE=PAPER`, and omit `--profile futures-killswitch` /
   `futures-kill-switch`.

5. Post-cutover verification:

   ```bash
   docker compose --env-file .env.live ps \
     futures-market-ingest futures-decision-engine futures-risk-filter \
     futures-order-router futures-monitor futures-kill-switch
   ```

   Unsuffixed dashboard keys (`trading:futures:*`) populate; `raw_data` is fresh.

6. First 09:00 KST session observation:

   - `raw_data` is fresh (futures-market-ingest publishing).
   - live dashboard keys show positions/fills/signals.
   - no restart loop or backlog growth.
   - exactly one KIS futures WS owner now (`futures-market-ingest`) plus
     order_router's — `trader-futures` is stopped.

## Rollback Triggers

Roll back if any of these happen: live verify fails, market data goes stale during
market hours, fills stop while final signals are present, stream backlog grows
without bound, a compose service restart-loops, or any KIS WS-conflict /
double-trade symptom appears.

## Rollback

```bash
docker compose --env-file .env.paper stop \
  futures-market-ingest futures-decision-engine futures-risk-filter \
  futures-order-router futures-monitor futures-kill-switch
```

Then re-enable the orchestrator futures path and restart it:

```bash
# in the env file:
FUTURES_ORCHESTRATOR_ENABLED=true
docker compose --env-file .env.paper --profile trading up -d trader-futures
```

For a **live** rollback also disable real orders:
`config/futures_live.yaml::enabled: false` (or
`redis-cli -n 1 set futures:live:suspended 1`).

## Live-path requirements (must verify before the live cutover)

The dormant/shadow wiring is safe by default. The **live** path has three
topology-specific requirements that the decoupled containers do NOT satisfy
automatically — verify each before going live:

1. **Executor real-order gate (`FUTURES_EXECUTOR_TRADING_MODE=REAL`).** In live router
   mode the order_router builds `OrderExecutor` from
   `config/execution.yaml::execution.trading_mode = ${TRADING_MODE:PAPER}`. The
   `futures-order-router` service maps its container `TRADING_MODE` from the dedicated
   `FUTURES_EXECUTOR_TRADING_MODE` knob (default `PAPER`). If left `PAPER`, the executor
   **silently simulates** orders even with `FUTURES_ORDER_ROUTER_MODE=live` +
   `futures_live.enabled=true`. Set `FUTURES_EXECUTOR_TRADING_MODE=REAL` (the executor
   enum is `PAPER|MOCK|REAL` — note this is a different value space from the orchestrator's
   `paper|live` `TRADING_MODE`). This is intentionally a separate knob so the stack-wide
   `TRADING_MODE=live` (orchestrator) does not accidentally arm the decoupled executor.

2. **kill_switch → order_router sentinel must be on a shared volume.** The order_router's
   only kill-switch interlock is the filesystem sentinel at
   `config/kill_switch.yaml::sentinel_path` (default
   `/app/data/runtime/kis_kill_switch.tripped`). The kill_switch daemon and
   order_router run in **separate containers**; container-local paths such as
   `/var/run` are not shared, so a trip written by `futures-kill-switch` would
   NOT be visible to `futures-order-router` and the "refuse to place new orders
   after a trip" interlock would be dead. Keep the sentinel under the shared
   `/app/data/runtime` mount (both containers mount host `./data/runtime` there),
   so both services see the same file.
   (The kill_switch's Telegram alert + Redis `kill_switch:events` stream + force-flatten
   Redis key fire regardless; only the order_router *file* interlock needs the shared path.
   Wiring order_router to also honor the Redis `kill_switch:force_flatten:requested` key is
   a documented follow-up.)

3. **Instrument resolution must match across services.** The default path is
   `FUTURES_TRADING_PRODUCT=mini` plus empty `FUTURES_STRATEGY_SYMBOL`, which
   auto-resolves the current front-month contract. If `FUTURES_STRATEGY_SYMBOL`
   is set, every futures service will use that explicit contract; confirm ingest,
   decision_engine, order_router, and futures_monitor are all reading the same
   symbol before promoting shadow evidence.

## Notes

- `futures:monitor:positions` is the futures_monitor working store
  (HSET/HDEL/recover on restart).
- `risk:state:futures[:shadow]` is the PseudoOCO realized-PnL / risk-counter store
  (shadow run writes the `:shadow` variant; isolated from live).
- `trading:futures:*[:shadow]` are the dashboard-native keys owned by
  `TradingStatePublisher`.
- The F-8 `FUTURES_ORCHESTRATOR_ENABLED` guard (`cli/main.py`, default `true`)
  prevents orchestrator↔decoupled double-trading. Set it to `false` at cutover,
  `true` at rollback.
- **Dual-WS caveat** (see Gate 1): order_router self-feeds a real KIS futures WS in
  both paper and live; futures-market-ingest owns a second. Never run
  futures-market-ingest while `trader-futures` owns the WS.
- kill_switch is config-gated (`config/kill_switch.yaml::enabled`) and live-only.
  It reads the live `risk:state:futures` and sends real futures Telegram — keep it
  out of shadow runs (its own `futures-killswitch` profile).
- The paper-grade halt for the decoupled futures pipeline is:

  ```bash
  docker compose --env-file .env.paper stop \
    futures-market-ingest futures-decision-engine futures-risk-filter \
    futures-order-router futures-monitor futures-kill-switch
  ```

- Follow-up: automated futures cutover verify/rollback scripts (the stock pipeline
  has `scripts/ops/stock_cutover_verify.py` + `scripts/ops/stock_cutover_rollback.sh`);
  a futures port is not yet written — this runbook uses inline commands.
