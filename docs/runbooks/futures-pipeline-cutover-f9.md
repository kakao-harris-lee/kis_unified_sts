# Runbook: Futures Decoupled Pipeline Cutover (F-9, Compose)

Flip futures trading from the in-process `trader-futures` orchestrator loop to the
decoupled daemon chain: decision_engine → risk_filter → order_router →
futures_monitor (+ kill_switch for live). Operational risks: silent stop, double
trading, stale market data, and **dual KIS futures WebSocket** connections on one
account.

This runbook is the operator half of F-9. The compose wiring is dormant
(default-off profiles); going live is gated.

Spec: `docs/superpowers/specs/2026-06-08-futures-pipeline-cutover-f9-design.md`
Stock analogue: `docs/runbooks/stock-pipeline-cutover-m5d.md`
Phase-5 gates (HARD prerequisite for live): `docs/runbooks/phase5-verification.md`

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
- `FUTURES_STRATEGY_SYMBOL`: KOSPI200 mini front-month code (required for
  shadow/live; update at each quarterly rollover). Must match what the
  orchestrator / ingest publishes.

## Gate 0 — Prerequisites

- `.env.paper` / `.env.live` filled (copy from `.env.paper.example` /
  `.env.live.example`).
- Core stack up:
  `docker compose --env-file .env.paper up -d redis dashboard strategy-builder-ui caddy stream-exporter`.
- `trader-futures` running normally:
  `docker compose --env-file .env.paper --profile trading up -d trader-futures`.
- `FUTURES_PIPELINE_MODE=shadow` and `FUTURES_ORDER_ROUTER_MODE=paper` in the env
  file, or unset so compose defaults to shadow/paper.
- `FUTURES_STRATEGY_SYMBOL` set to the current KOSPI200 mini front-month code.
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
  `docker compose --env-file .env.paper exec -T redis sh -c 'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli -n 1 xlen signal.final.futures.shadow'`.
- No restart loop:
  `docker compose --env-file .env.paper ps futures-decision-engine futures-risk-filter futures-order-router futures-monitor`.
- Sanity: compare shadow decisions with the orchestrator's paper trades for
  **direction**, not exact fill parity.

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
   docker compose --env-file .env.paper exec -T redis sh -c \
     'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli -n 1 del futures:monitor:positions trading:futures:positions risk:state:futures'
   ```

2. Block the orchestrator futures path (F-8 double-trade guard). In the env file:

   ```bash
   FUTURES_ORCHESTRATOR_ENABLED=false
   ```

   This makes `sts trade start --asset futures` refuse, so `trader-futures` cannot
   re-trade alongside the decoupled chain.

3. **(live only)** Enable real order placement:

   - `config/futures_live.yaml::enabled: true`
   - `docker compose --env-file .env.live exec -T redis sh -c 'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli -n 1 del futures:live:suspended'`

   For a **paper** cutover, skip this step and keep `FUTURES_ORDER_ROUTER_MODE=paper`.

4. Start the decoupled chain + ingest (+ kill_switch for live):

   ```bash
   FUTURES_PIPELINE_MODE=live FUTURES_ORDER_ROUTER_MODE=live \
     docker compose --env-file .env.live \
       --profile futures-ingest --profile futures-pipeline --profile futures-killswitch up -d \
       futures-market-ingest futures-decision-engine futures-risk-filter \
       futures-order-router futures-monitor futures-kill-switch
   ```

   Paper cutover: use `--env-file .env.paper`, keep `FUTURES_ORDER_ROUTER_MODE=paper`,
   and omit `--profile futures-killswitch` / `futures-kill-switch`.

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
