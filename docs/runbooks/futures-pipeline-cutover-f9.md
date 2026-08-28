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

**INERT-GATE CAVEAT — read before interpreting any Gate 1 pass rate.** Several
filters in the decoupled chain cannot reject anything as shipped (see Gate 1b).
A shadow chain containing structurally-inert gates produces an **inflated** pass
rate. "No volatility or spread rejections in N trading days" is *not* evidence
those controls work — it is exactly what you would observe if they are unable to
fire. Read every Gate 1 rejection count against the Gate 1b inventory before
quoting it in the Gate 2 approval. The same applies to the direction-parity
check above: the orchestrator is enforcing gates the shadow chain is not, so a
shadow entry the orchestrator declined may be a real control divergence rather
than fill noise.

**DUAL-WS CAVEAT.** `futures-order-router` self-feeds a real KIS futures WebSocket
even in paper mode (KIS 모의투자 serves no futures realtime feed). During shadow
that is a 2nd futures WS alongside the orchestrator's = 2 concurrent on one KIS
account. Confirm KIS allows this for your account, or run shadow in a window where
`trader-futures` is paused. If order_router logs WS connect/auth failures, this is
the likely cause.

## Gate 1b — Control Parity (blocks Gate 2 approval)

Cutover does not only move controls between processes. The monolith never builds
a `RiskFilterLayer` — **0 references** under `services/trading/` — it implements
its futures controls in its own code. The decoupled chain builds the layer at
`services/risk_filter/main.py:453` but supplies only some of its providers, and
`RiskFilterLayer.from_config` substitutes a **silent no-op stub** for every
provider omitted (`shared/risk/layer.py:199` / `:214` / `:223`; stub bodies at
`:211` / `:220` / `:233`). A stubbed filter is still constructed and still sits
in the chain — it simply passes every signal. None of the three carries an
`enabled` or `mode` flag, so from the outside it reads as permanently armed.

So a working control can be retired at cutover and replaced by a counterpart
that is structurally unable to fire. Work the inventory below, then sign it off
**before** Gate 2 approval.

### Inventory

Re-verify every row against the code before signing (see "Re-verifying this
inventory"). Line numbers here are as of `26fc52b0` and will drift.

| Control | Monolith (`trader-futures`, today) | Decoupled (post-F-9) | Status |
|---|---|---|---|
| Duplicate entry, per symbol | `can_open_position(signal.code)` — `orchestrator.py:5445`, def `position_tracker.py:166-178`, cap `max_positions_per_symbol = 1` (`position_models.py:40`, a dataclass default the orchestrator never overrides) | `OpenPositionFilter` (`layer.py:257`, check `open_position.py:103`) — provider wired at `risk_filter/main.py:456`, `HEXISTS futures:monitor:positions` (`risk_filter/main.py:64`), fail-closed on Redis error | **present** — wired in `26fc52b0` |
| Duplicate entry, global count | `can_open_position()` — `orchestrator.py:4976`, cap summed from per-strategy sizer limits (`orchestrator.py:900-907`) | `ConcurrentPositionsFilter`, built only when `concurrent_positions.enabled` (`layer.py:283`); no count provider is passed at `risk_filter/main.py:453`, so it fails open (`layer.py:306`) | **unwired — cannot fire** |
| Spread | `FuturesSlippageController` gate at `slippage_control.py:360`; `max_spread_ticks: 1` (`execution.yaml:200`), `enabled: true` (`execution.yaml:196`) | `SpreadFilter` (`layer.py:253`, compare `spread.py:94`), threshold `max_spread_ticks: 2` (`risk.yaml:21`); `current_spread_provider` not passed → stub returns `0.0` (`layer.py:220`) | **unwired — cannot fire** |
| Order-book depth | `slippage_control.py:369`, `min_depth_multiplier: 3.0` (`execution.yaml:201`) | none | **absent** |
| Volatility spike | cooldown armed on every tick (`slippage_control.py:294`, fed by `orchestrator.py:1136`), enforced at entry (`slippage_control.py:341`) | `VolatilityFilter` (`layer.py:252`, compare `volatility.py:102`) — `current_atr_provider` stubbed to `0.0` (`layer.py:211`) **and** the other side of the comparison, `RiskStateSnapshot.atr_90th_percentile`, defaults `0.0` (`state.py:43`) with no production writer | **unwired on both sides — cannot fire** |
| Stale signal | `slippage_control.py:322`, `max_signal_age_seconds: 2.0` (`execution.yaml:207`) | none | **absent** |
| Intraday blackout windows | `slippage_control.py:336`, `blocked_time_windows` 08:45–08:50 / 15:40–15:45 (`execution.yaml:222`) | `TradingHoursFilter` enforces session windows only (`risk.yaml:84`); the blackouts have no counterpart | **partial** |
| Daily trade ceiling | none on this path | `DailyTradeCountFilter` (`layer.py:251`, compare `daily_trade_count.py:68`), `max_daily_trades: 3` (`risk.yaml:6`) | **present** — see caveat below |

The five order-book rows (spread, depth, volatility, stale signal, blackout
windows) all reach the monolith through one call site: `_submit_entry_order`
dispatches futures entries to `_submit_futures_entry_with_slippage_control`
(`orchestrator.py:5575-5580`), which calls `evaluate_entry`
(`orchestrator.py:5636`) and aborts the entry on a `block` decision
(`orchestrator.py:5657`). Stopping `trader-futures` removes all five at once.
The duplicate-entry rows are separate — they gate inside `_execute_entry`
(`orchestrator.py:5445`) and in signal generation (`:4976`).

Guards outside this table, because they survive the cutover rather than being
replaced by it: the kill-switch sentinel (`order_router/main.py:189-190`,
checked at `:195` and per loop at `:254`; path passed unconditionally at
`:834`), `LiveModeGuard.is_live_suspended` (`:437`), the symbol lock (`:448`)
and `position_size_cap` (`:465`). See the consequence section for which of them
are in force in which mode.

**Qualifications that change what these rows mean:**

- **The monolith's spread threshold is 1 tick in live, 6 in paper.**
  `paper_override.enabled: true` (`execution.yaml:233`) replaces
  `max_spread_ticks` with `${FUTURES_PAPER_MAX_SPREAD_TICKS:6}`
  (`execution.yaml:235`) whenever `config.paper_trading` is set
  (`orchestrator.py:702`). A paper cutover therefore retires a 6-tick gate, a
  live cutover a 1-tick gate.
- **`DailyTradeCountFilter` counts closed round-trips, not entries.**
  `daily_trade_count` is incremented only by `RuntimeRiskState.record_trade`,
  whose sole futures caller is `PseudoOCO` on an exit fill
  (`pseudo_oco.py:284`). Positions opened and held leave the counter at 0. It
  bounds how many *completed* trades a day can produce; it is not a
  duplicate-entry guard and should not be recorded as one.
- **The order_router's own caps are live-only.** `position_size_cap`
  (`order_router/main.py:465`), `daily_trade_cap` (`:475`), symbol lock
  (`:448`) and the live-suspend check (`:437`) are all conditioned on
  `live_mode_guard is not None`, and paper mode sets `guard_for_daemon = None`
  (`order_router/main.py:784`). In a **paper** cutover none of the four is in
  force. Their values, when live, come from `config/futures_live.yaml`:
  `max_position_size_contracts: 1` (`:26`), `max_daily_trades: 2` (`:27`),
  `symbol_lock_enabled: true` (`:28`).
- **`services/order_router` does not gate on slippage.** It computes
  `slippage_ticks` (`order_router/main.py:384`) and passes it to `log_fill`
  (`:400`). There is no branch on the value — it is reporting only, and is not a
  replacement for the monolith's entry-side spread gate.
- **`FuturesSlippageController` has exactly one consumer outside its own
  package:** `services/trading/orchestrator.py:718`. (`shared/execution/__init__.py:6`
  re-exports it; nothing else imports it.) Stopping `trader-futures` removes the
  only process that runs it.
- **Other filters in the chain are inert for unrelated reasons** —
  `MarginGateFilter` fails open while the `futures_margin_risk` publisher is
  dormant (`layer.py:350`), `LeverageFilter` is inert without a snapshot
  provider (`layer.py:387`). They are not parity gaps, but they do inflate the
  Gate 1 pass rate the same way.

### Consequence of cutting over with the gaps open

Concretely, at the moment `trader-futures` stops:

- **Spread control stops working.** Entries are no longer rejected on a wide
  book. `SpreadFilter` remains in the chain and passes every signal, because its
  provider reports a constant `0.0` spread.
- **Volatility control stops working.** No cooldown after a price spike.
  `VolatilityFilter` cannot reject even if someone wires the ATR provider alone —
  with `atr_90th_percentile` at `0.0`, a real ATR makes *every* signal satisfy
  `atr > 0.0` and rejects everything, halting all trading. Any fix must land a
  production writer for `atr_90th_percentile` in the same change
  (`layer.py:201-208`).
- **Depth and stale-signal checks disappear entirely.** No counterpart exists.
- **Blackout windows shrink** to session windows; the open/close blackouts go
  away.

What still bounds the damage: the kill-switch sentinel and
`DailyTradeCountFilter` (3 closed round-trips/day) in **both** modes; plus
`live_mode_guard`, the symbol lock and `position_size_cap` in **live only**, per
the qualification above. In a paper cutover the bound is the kill switch and the
daily count, and nothing else.

Note what that set does *not* include: nothing left in the chain inspects the
order book before an entry. A wide-spread or spiking market is entered at full
size until the daily count fills — and `position_size_cap` caps quantity rather
than rejecting the signal (`order_router/main.py:465` reassigns `quantity`; it
does not skip), so it limits size, not frequency.

### Operator sign-off (required before Gate 2)

Every row not marked **present** must be explicitly resolved. Record, per row,
one of:

- **CLOSED** — commit SHA of the wiring, plus the shadow evidence showing the
  filter actually rejecting something. A filter that has never rejected in
  shadow has not been demonstrated to work.
- **ACCEPTED** — named operator, date, and the rationale for carrying the gap
  into live, including what bounds the exposure in the meantime.

A gap silently carried forward is the failure this gate exists to prevent. An
inventory row left blank blocks Gate 2; it does not default to accepted.

```text
Gate 1b control parity — F-9
Inventory re-verified on:            (date)  by: (operator)
Verification method:                 (log grep / kwarg dump / pytest — see below)
Duplicate entry, global count:       CLOSED @ ______  | ACCEPTED by ______ because ______
Spread:                              CLOSED @ ______  | ACCEPTED by ______ because ______
Order-book depth:                    CLOSED @ ______  | ACCEPTED by ______ because ______
Volatility spike:                    CLOSED @ ______  | ACCEPTED by ______ because ______
Stale signal:                        CLOSED @ ______  | ACCEPTED by ______ because ______
Intraday blackout windows:           CLOSED @ ______  | ACCEPTED by ______ because ______
Paper vs live spread threshold understood (1 tick live / 6 paper):  yes / no
Live-only nature of the order_router caps understood:               yes / no
```

### Re-verifying this inventory

The table above rots — line numbers move and providers get wired. Re-derive it
rather than trusting it. In order of authority:

1. **Runtime, authoritative.** Every unwired provider announces itself at daemon
   startup. Grep the risk_filter log for the word `inert`; each line names the
   filter that cannot fire. An empty result means nothing is inert — which is
   also the only way this section can be retired.

   ```bash
   docker compose --env-file .env.paper logs futures-risk-filter | grep -i inert
   ```

2. **Source, shows what is actually passed.** Dump the production
   `from_config` call and compare its kwargs against the provider parameters the
   builder accepts:

   ```bash
   sed -n '/RiskFilterLayer.from_config(/,/^    )/p' services/risk_filter/main.py
   grep -n '_provider' shared/risk/layer.py | sed -n '1,12p'
   ```

3. **Test, behavioural.** A regression guard executes the real `_build_and_run`
   wiring of each daemon, captures the kwargs it passes, and exercises the
   captured provider against a fake Redis — so removing a provider from a
   production call site fails the suite:

   ```bash
   .venv/bin/python -m pytest tests/unit/risk/test_provider_wiring.py -q
   ```

   Extend that file when a gap is closed; a newly wired provider without a
   corresponding assertion there can silently regress.

## Gate 2 — Operator Approval + Phase-5

Record the date and a one-line shadow validation summary before proceeding.

**HARD PREREQUISITE:** the Gate 1b control-parity inventory is re-verified and
signed off, with every non-parity row marked CLOSED or ACCEPTED.

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
