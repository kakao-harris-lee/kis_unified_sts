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
- `FUTURES_ORDER_ROUTER_FEED` (default `stream`): where order_router gets its
  prices (`stream` | `ws`). `stream` consumes `FUTURES_TICK_STREAM` (default
  `raw_data`) and opens no KIS WebSocket, so the router can run beside
  `trader-futures`; `ws` self-feeds and must not. See the feed-source note in
  Gate 1. An unrecognised value aborts startup.
- `FUTURES_ROUTER_MAX_QUOTE_AGE_SECONDS` (default `10`): the router gate rejects
  a book whose own `quote_ts` is older than this with `quote_stale` (0 disables),
  and startup seeding skips entries past the same bound. Router-only — it feeds
  `futures_slippage_control.order_router_max_quote_age_seconds`, which the
  monolith ignores. Applies in both feed modes.
- `FUTURES_ROUTER_SLIPPAGE_GATE` (default `true`): the send-time gate's own
  rollback switch (`futures_slippage_control.order_router_gate`). Seeding stays
  age-bounded even with the gate off.
- `FUTURES_ORDER_ROUTER_SEED_COUNT` (default `50`): how deep into the stream tail
  to look at startup. Search depth, not an age bound.
- Stream names: producers publish to `MONITOR_FUTURES_TICK_STREAM`, consumers
  read `FUTURES_TICK_STREAM`. Both default to `raw_data` and a unit test pins the
  two defaults together — they must name the same stream.
- `FUTURES_TRADING_PRODUCT` (default `mini`): futures front-month product
  (`mini` | `kospi200`). All decoupled futures services and the orchestrator
  resolve the same current contract through `shared.execution.futures_instrument`.
- `FUTURES_STRATEGY_SYMBOL`: optional explicit contract-code override. Leave it
  empty for automatic quarterly rollover; set it only when deliberately pinning
  shadow/live to a specific contract. If set, it must match what ingest publishes.
- **Setup roster and parameters are not env knobs.** `futures-decision-engine`
  builds its roster from `config/strategies/futures/*.yaml`: `strategy.enabled`
  selects which setups run, `strategy.entry.params` supplies every threshold
  (`services/decision_engine/main.py::_build_setups`). These are the SAME files
  the orchestrator's Setup adapters read, so shadow and paper run one operating
  point. `config/decision_engine.yaml` holds no setup parameters — only this
  daemon's `market_risk_gate` wiring. Changing a threshold means editing the
  strategy file and restarting the daemon; the startup log prints the roster and
  each setup's parameters (`decision_engine setups: [...]`).
- `FUTURES_DECISION_ENGINE_SETUPS` (default empty): optional comma-separated
  subset of registry names (e.g. `setup_d_vwap_reversion`) that narrows the
  DECOUPLED roster only. Empty = every setup whose `strategy.enabled` is true.
  Use it to stop a setup in shadow without flipping `strategy.enabled`, which is
  shared with `trader-futures` and would also stop that setup in paper.

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
- **order_router is stream-fed and opened no KIS WebSocket** — the check that
  keeps it from evicting `trader-futures` from the account's single futures WS:

  ```bash
  docker compose --env-file .env.paper logs futures-order-router \
    | grep -E "order_router feed=" | tail -1          # expect: feed=stream stream=raw_data
  docker compose --env-file .env.paper logs futures-order-router \
    | grep -cE "\[KIS WS\]|Approval key obtained"    # expect: 0
  ```

- **`raw_data` carries the top of book** — both producers merge it into the
  trade tick they publish; without it the slippage gate has nothing to evaluate
  and blocks everything with `orderbook_unavailable`:

  ```bash
  redis-cli -p 6379 -n 1 xrevrange raw_data + - COUNT 1 \
    | grep -E "bid_price_1|ask_price_1|quote_ts"
  ```

  `quote_ts` is the book's own event time. A `raw_data` tail where `timestamp`
  keeps advancing while `quote_ts` does not is a frozen orderbook feed, and the
  router will be rejecting entries with `quote_stale` — that is the gate working,
  not a market condition.

- `trader-futures` kept its WS through the shadow day: no reconnect storm and no
  `raw_data` gap while the router was up.
- Sanity: compare shadow decisions with the orchestrator's paper trades for
  **direction**, not exact fill parity.
- Setup D reaches the shadow stream. `setup_d_vwap_reversion` is the setup that
  actually trades in paper (2026-09-08: 20 orchestrator fills, all Setup D,
  while Setup A was `outside_time_window` all day), so a Gate 1 day with no
  Setup D candidate proves nothing about direction parity:

  ```bash
  redis-cli -p 6379 -n 1 xrevrange signal.candidate.futures.shadow + - COUNT 50 \
    | grep -c D_vwap_reversion
  ```

  Note the naming split: the stream carries `setup_type=D_vwap_reversion`
  (`A_gap_reversion` / `C_event_reaction` for the others), while the registry,
  the strategy file and the eval rows below use `setup_d_vwap_reversion`.
- Per-setup evaluations accumulate, so "0 candidates" is distinguishable from
  "never evaluated". Outside live mode the daemon writes to its OWN `:shadow`
  keys — `trader-futures`' Setup adapters are writing the unsuffixed keys at the
  same time, and sharing them would let each producer overwrite the other's row:

  ```bash
  # the decoupled daemon's rows (only a live-mode daemon writes the unsuffixed keys)
  redis-cli -p 6379 -n 1 hgetall trading:futures:setup_eval:shadow
  redis-cli -p 6379 -n 1 lrange \
    trading:futures:setup_eval:history:shadow:$(TZ=Asia/Seoul date +%F) 0 -1
  ```

  (Redis KEYS take a colon `:shadow` suffix in this repo, like
  `risk:state:futures:shadow`; STREAMS take a dotted `.shadow`, like
  `signal.candidate.futures.shadow`. The two are not the same convention.)

  The check is only meaningful because the two producers are separated: the
  orchestrator never writes the `:shadow` keys, so a `setup_d_vwap_reversion`
  row **there** is proof the daemon evaluated Setup D. Compare against the
  orchestrator's own rows (`trading:futures:setup_eval`, unsuffixed) to see the
  two runtimes' reasons side by side. After a live cutover the daemon writes the
  unsuffixed keys (`FUTURES_PIPELINE_MODE=live`), by which point
  `trader-futures` is stopped.

  **Read the hash DURING the session.** It holds the latest state, not a log, so
  an off-session `HGETALL` shows either the last in-session evaluation or the
  `no_market_context` rows the daemon keeps writing while the feed is quiet. The
  per-day history list is the record to read afterwards.

  If the shadow hash has no Setup D row at all, the daemon is not evaluating it:
  check the startup roster line (`decision_engine setups: [...]`).
- **Known limitation — the engine's VWAP is not a KRX-session VWAP.** The
  streaming engine's VWAP accumulator is keyed on the UTC calendar date
  (`shared/indicators/streaming/engine.py`), so its buckets do not line up with
  the 08:45–15:45 KST session. Three consequences, only the first of which is
  visible in the eval rows:
  - **Cold start** (a daemon restart before the first candle completes):
    `ctx.vwap` is 0, and the daemon records `reject: no_vwap` for Setup D while
    Setup A/C keep running. Parquet warm-up does not seed the calculator
    (`seed_candles` never feeds it). These rows are not a Setup D defect and do
    not count as evaluated bars.
  - **00:00 UTC = 09:00 KST boundary, mid-session**: `add_tick` resets the
    accumulator and adds the new tick in the same call, so vwap is immediately
    non-zero but degenerate — it equals that one candle's close, giving z ≈ 0.
    Setup D then rejects with an ordinary `not_extreme(...)`, NOT `no_vwap`.
    This is silent: nothing in the chain flags it. Treat Setup D evaluations in
    the first few minutes after 09:00 KST as low-information.
  - **08:45–09:00 KST**: the UTC date is still yesterday's, so vwap carries over
    the previous bucket's accumulation rather than starting fresh at the open.

  Fixing this means changing the engine's session anchor, which is deliberately
  out of scope for the F-9 port; record it here so a Gate 1 reader does not read
  these rows as Setup D behaviour.

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

**FEED SOURCE — stream by default, `ws` is opt-in.** KIS serves **one** futures
WebSocket per account: measured 2026-09-07/08, the second connection is dropped
and, on 09-08 08:45–09:15, the orchestrator lost `raw_data` for 25 minutes until
`futures-order-router` was stopped. `FUTURES_ORDER_ROUTER_FEED` (default
`stream`) therefore has the router consume the `raw_data` ticks
`trader-futures` already publishes — no KIS connection of its own — so Gate 1
runs the router **alongside** the orchestrator, which is what makes a
`slippage_gate` rejection observable at all.

`FUTURES_ORDER_ROUTER_FEED=ws` restores the old self-fed path. It **MUST NOT**
run while `trader-futures` (or `futures-market-ingest`) owns the account's
futures WS — use it only in a window where the other WS owner is stopped. An
unrecognised value is fatal at startup by design.

**Both producers publish on TRADE ticks.** The futures feed delivers orderbook
(H0IFASP0) and trade (H0IFCNT0) ticks on separate channels and only the trade
tick reaches a tick callback, so `trader-futures` and `futures-market-ingest`
each merge the feed's cached top of book into the tick they republish
(`orderbook_publish_fields`). Two consequences for reading Gate 1 numbers:

- **A book can freeze while trades keep printing.** H0IFASP0 going quiet while
  H0IFCNT0 continues is a real state the feed already models
  (`_log_orderbook_staleness`), and the cached book is never age-expired — so
  the producer merges a frozen bid/ask onto a fresh trade every ~0.2s. Each
  entry therefore carries two times: `timestamp` (the trade print) and
  `quote_ts` (that book's own event time). Everything bounding quote freshness
  reads `quote_ts`; reading `timestamp` would report age≈0 for a dead book
  forever. The router blocks on
  `futures_slippage_control.order_router_max_quote_age_seconds` (default 10s,
  `FUTURES_ROUTER_MAX_QUOTE_AGE_SECONDS`, 0 disables) with reason
  `quote_stale:<age>` — a router-only key the monolith ignores, like
  `order_router_gate`. It bounds the same quantity in `ws` mode, where the WS
  feed's own orderbook cache supplies that time. Publishing on orderbook ticks
  would shrink the stale window; that is a documented follow-up (design §8).
  `quote_stale` counts toward `slippage_blocked_count`, so read it in Gate 1 as
  a data-availability reject, not a market reject.
- **Cross-asset availability depends on the producer.** `trader-futures` passes
  its `cross_asset.reference_symbol` to the WS feed as an auxiliary subscription
  and republishes every tick it receives, so **pre-cutover the reference symbol
  IS on the stream** and the cross-asset check works in stream mode.
  `futures-market-ingest` subscribes only its trading symbol, so **after the
  cutover it is not**, and the gate would block every entry with
  `cross_asset_unavailable`. Paper is unaffected either way (`paper_override`
  sets `cross_asset.enabled: false`). The router logs a check-this WARNING at
  startup when cross-asset is on in stream mode; verify the symbol is on
  `raw_data`, disable cross-asset, or run `ws` in an exclusive window.

On restart the router seeds its cache from the tail of the stream
(`XREVRANGE`, `FUTURES_ORDER_ROUTER_SEED_COUNT`, default 50) so the first signal
after a restart is not blocked on `orderbook_unavailable`. The count bounds how
deep to look for this symbol, not the seeded book's age: entries apply
oldest-first, so the newest always wins. Age is bounded separately — seeding
skips anything older than the quote-age knob, so a restart during a halt or on a
day-old stream seeds nothing rather than relying on the gate to reject it
afterwards.

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
| Duplicate entry, global count | `can_open_position()` — `orchestrator.py:4976`, cap summed from per-strategy sizer limits (`orchestrator.py:900-907`) | `ConcurrentPositionsFilter` with `open_positions_count_provider` (HLEN `futures:monitor:positions`, `services/risk_filter/main.py::_build_open_positions_count_provider`), `concurrent_positions.enabled: true` cap 11 | wired 2026-09-07 (plan 2026-09-07-f9-gate1b-control-parity-closure) — shadow rejection evidence pending |
| Spread | `FuturesSlippageController` gate at `slippage_control.py:360`; `max_spread_ticks: 1` (`execution.yaml:200`), `enabled: true` (`execution.yaml:196`) | order_router pre-send `FuturesSlippageController` (plan 2026-09-07-f9-gate1b-control-parity-closure §2-B) — shadow rejection evidence pending | wired 2026-09-07 (plan 2026-09-07-f9-gate1b-control-parity-closure) — shadow rejection evidence pending |
| Order-book depth | `slippage_control.py:369`, `min_depth_multiplier: 3.0` (`execution.yaml:201`) | order_router pre-send `FuturesSlippageController` (plan 2026-09-07-f9-gate1b-control-parity-closure §2-B) — shadow rejection evidence pending | wired 2026-09-07 (plan 2026-09-07-f9-gate1b-control-parity-closure) — shadow rejection evidence pending |
| Volatility spike | cooldown armed on every tick (`slippage_control.py:294`, fed by `orchestrator.py:1136`), enforced at entry (`slippage_control.py:341`) | order_router pre-send `FuturesSlippageController` (plan 2026-09-07-f9-gate1b-control-parity-closure §2-B) — shadow rejection evidence pending | wired 2026-09-07 (plan 2026-09-07-f9-gate1b-control-parity-closure) — shadow rejection evidence pending |
| Stale signal | `slippage_control.py:322`, `max_signal_age_seconds: 2.0` (`execution.yaml:207`) | order_router pre-send `FuturesSlippageController` (plan 2026-09-07-f9-gate1b-control-parity-closure §2-B) — shadow rejection evidence pending | wired 2026-09-07 (plan 2026-09-07-f9-gate1b-control-parity-closure) — shadow rejection evidence pending |
| Intraday blackout windows | `slippage_control.py:336`, `blocked_time_windows` 08:45–08:50 / 15:40–15:45 (`execution.yaml:222`) | order_router pre-send `FuturesSlippageController` (plan 2026-09-07-f9-gate1b-control-parity-closure §2-B) — shadow rejection evidence pending | wired 2026-09-07 (plan 2026-09-07-f9-gate1b-control-parity-closure) — shadow rejection evidence pending |
| Daily trade ceiling | none on this path | `DailyTradeCountFilter` (`layer.py:251`, compare `daily_trade_count.py:68`), `max_daily_trades: 3` (`risk.yaml:6`) | **present** — see caveat below |
| Exit semantics (holding period / EOD flatten) | `setup_target_exit` honours the signal's stop/target and adds an EOD close at 15:15 KST (`config/strategies/futures/setup_*.yaml` `exit.params.eod_close_*`); no TTL-driven close | PseudoOCO force-closes the position at `signal.valid_until` (`shared/execution/pseudo_oco.py::check_expiry`, called from `order_router/main.py`), i.e. `signal_ttl_minutes` becomes a HOLDING cap — 10 min for Setup A/D, 30 for C. No EOD flatten exists anywhere in the decoupled chain | **intentional deviation candidate** — operator disposition required |
| Post-exit re-entry cooldown | `services/trading/reentry_guard.py`, per-strategy cooldown after an exit (orchestrator-only) | none — no per-strategy cooldown in the decoupled chain (`ConsecutiveLossFilter` is a different control: it counts losses, it does not space re-entries) | **intentional deviation candidate** — operator disposition required |
| Setup D adapter-layer entry gates | `shared/strategy/entry/setup_d_adapter.py`: the `short_blocked_regimes: ["BULL_STRONG"]` direction block (PR #559, `setup_d_vwap_reversion.yaml`) — the only one in force. The file's `regime_gate` block is `enabled: false`, and Setup D's adapter carries no LLM tuning/veto and no daily-bias filter | none — the daemon calls the Setup CORE (`shared/decision/setups/vwap_reversion.py`) directly, so the adapter layer does not travel with the cutover | **intentional deviation** — operator decision ② 2026-09-09: not ported; observed via setup_eval |
| Setup A `regime_gate` | `shared/strategy/gates/regime_gate.py` via the Setup A adapter; `regime_gate.enabled: true` in `config/strategies/futures/setup_a_gap_reversion.yaml` (activated 2026-05-23, PR #330 follow-up). Blocks entries on the live HAR-RV / event-impact regime | none — same reason as the Setup D row above | **OPEN** — needs operator disposition (decision ② covered Setup D only) |

Note on the two rows above: decision ② was taken about Setup D's direction
block. Setup A's `regime_gate` is a DIFFERENT control, it is switched on in
production today, and no decision has been recorded for it — it is listed
separately so Gate 2 cannot read the Setup D disposition as covering it.

Rationale for the Setup D disposition: the decoupled chain deliberately has ONE
entry gate (`market_risk_gate`), and re-implementing the adapter gates in the
daemon would duplicate a control layer rather than move it. The exposure is
bounded by observation instead: every Setup D fire is recorded on
`trading:futures:setup_eval:shadow` with its direction, so a shadow session shows
whether the monolith's `BULL_STRONG` block would have suppressed any SHORT fades
at all. If it would, the right home for the control is the `market_risk_gate`
reaction matrix (which already answers per-side), not a second copy of the
adapter.

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

- **The volatility row spans a different amount of wall clock in each runtime
  — operator decision.** `volatility.window_ticks: 20` counts TICKS, not
  seconds. The monolith registers every raw WS trade tick, while the decoupled
  router registers what reaches it through `raw_data`, which the publisher
  throttles to `futures_min_interval_seconds` (0.2s) and conflates further when
  a flush batch collapses to the newest tick per symbol. The same 20-tick window
  therefore covers a longer, and a load-dependent, stretch of the session in the
  decoupled chain, so its spike detector reacts to a slower move than the
  monolith's. Not a defect of either, but the two are not the same control:
  before Gate 2, either tune `window_ticks` for the decoupled runtime or record
  the acceptance explicitly. Nothing in the shadow numbers reveals this on its
  own — a lower volatility-cooldown count reads as a calmer market.
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
- **The two "intentional deviation candidates" are not wiring gaps.** They are
  behaviour differences the F-9 port deliberately did not close (plan
  2026-09-08-setup-d-decoupled-port §8), recorded here so they are disposed of
  rather than discovered after cutover:
  - *Exit semantics.* Setup D's `signal_ttl_minutes: 10` is an ENTRY validity
    window in the setup's own semantics and in the backtest; PseudoOCO reads the
    resulting `valid_until` as a deadline and flattens the position there. On
    2026-09-08 most orchestrator Setup D round-trips ran longer than 10 minutes
    (12:14→12:27, 13:55→14:05), so shadow and paper can agree on direction and
    still diverge on P&L. Conversely nothing in the decoupled chain flattens at
    15:15 KST, so a position opened late can be carried into the close.
  - *Re-entry cooldown.* Setup D fires throughout the session and was the
    strategy behind the 2026-07-07 churn episode (13 consecutive dip-buys, 11
    stop-outs); the orchestrator's re-entry guard is what bounds that, and it
    does not travel with the cutover. Watch the shadow stream for repeated
    same-direction candidates on one symbol before signing this off.
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
Exit semantics (TTL force-close, no EOD flatten):  CLOSED @ ______  | ACCEPTED by ______ because ______
Post-exit re-entry cooldown absent:  CLOSED @ ______  | ACCEPTED by ______ because ______
Setup D adapter direction block (BULL_STRONG short) not ported:
                                     CLOSED @ ______  | ACCEPTED by ______ because ______
Setup A regime_gate (enabled in monolith) not ported:
                                     CLOSED @ ______  | ACCEPTED by ______ because ______
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

   **Note (plan 2026-09-07-f9-gate1b-control-parity-closure §2-E):** the
   spread/depth/volatility/stale-signal/blackout parity path does not run
   through `risk_filter` — it is the order_router pre-send
   `FuturesSlippageController` gate (§2-B). `risk_filter`'s own
   `SpreadFilter`/`VolatilityFilter` `inert` log lines are therefore
   **expected to keep appearing** and are not a regression; they are not this
   closure's path. Verify parity instead from the order_router startup log
   line `Futures slippage control enabled (paper|live)` and its
   `slippage_gate: blocked` warning log lines on rejection:

   ```bash
   docker compose --env-file .env.paper logs futures-order-router | grep "slippage_gate: blocked"
   ```

   `slippage_blocked_count` is a plain in-process instance attribute with no
   exporter (no Prometheus metric, no log line carrying its running value) —
   it is useful for an interactive/debugger inspection of a live daemon, not
   for `docker compose logs` grepping.

   **Deliberate divergences from the monolith (not parity gaps):**

   1. **Stale-signal polarity is inverted, on purpose, stricter.** The
      decoupled order_router blocks fail-**closed** when `signal.generated_at`
      is missing (`order_router/main.py:491-501`, reason
      `signal_timestamp_missing`), whereas the monolith is fail-**open** on a
      non-`datetime` timestamp — it falls back to `datetime.now(UTC)`, i.e.
      always fresh, and lets the entry through
      (`services/trading/orchestrator.py:5805-5809`). This is not a gap to
      close; the decoupled chain is already the stricter of the two.
   2. **Per-strategy position cap has no decoupled counterpart, and is outside
      Gate 1b's inventory.** The monolith additionally caps open positions
      *per strategy* (`orchestrator.py:5666-5680`: rejects once
      `current_count >= strategy_max` for that one strategy), on top of the
      per-symbol and global-count caps this gate already tracks.
      `ConcurrentPositionsFilter` only enforces total/per-asset-class caps —
      it has no per-strategy dimension — so the decoupled chain stays more
      permissive on this one axis even after §2-C's global-count wiring.
      Left for the operator to accept explicitly at Gate 2 or open as a
      follow-up; it was never in the six-row inventory above.
      **Disposition (2026-09-07, measured):** vacuous under the current
      decoupled deployment. `futures-order-router` subscribes exactly one
      instrument (`resolve_futures_instrument_from_env()` →
      `update_symbols([symbol])`, `services/order_router/main.py`) and
      `decision_engine` decides for that same single symbol, while the
      per-symbol duplicate guard (`OpenPositionFilter`, HEXISTS on
      `futures:monitor:positions`) already caps open positions at 1 per
      symbol. With one symbol, any per-strategy cap ≥ 1 cannot reject
      anything the per-symbol guard has not already rejected. The gap becomes
      real only if the decoupled chain is extended to multiple instruments;
      re-open it in that design, not here. No code added on purpose.
   3. **Legacy operator CLIs hardened independently of cutover (branch
      `feat/f9-legacy-route-hardening`).** LEGACY-006/007 in
      `tos-spec/src/MIGRATION-CONFORMANCE-REGISTER.md` recorded that
      `scripts/trading/flatten_all.py` and `recover_positions.py` built a
      **real** KIS client when `KIS_FUTURES_MARKET` was unset, and that the
      recovery sentinel had no consumer. Both are closed in that branch: an
      unset `KIS_FUTURES_MARKET` aborts (no default in either direction —
      note this variable selects the market-DATA endpoint only; the paper
      server sets it to `real` on purpose because the KIS virtual server has
      no futures feed), real-money sends are gated on the executor trading
      mode (`TRADING_MODE` / `FUTURES_EXECUTOR_TRADING_MODE`) and need
      `--live --confirm`, and order_router refuses to start or continue while
      `kill_switch.recovery_sentinel_path` (under the mounted
      `/app/data/runtime`, same convention as the kill-switch sentinel)
      exists.

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

**HARD PREREQUISITE (live only):** `risk:state:futures*` in the live stack's
Redis is empty before the first live order (Cutover Sequence step 1). The O13
paper writer shares the unsuffixed key with the live kill_switch.

## Cutover Sequence (Run Off-Hours)

1. Flatten and clear disposable state:

   ```bash
   python scripts/trading/flatten_all.py --asset futures        # optional
   docker compose --env-file .env.paper --profile trading stop trader-futures
   # paper — host Redis (db 1, no auth). For live, target the live stack's Redis.
   redis-cli -p 6379 -n 1 del futures:monitor:positions trading:futures:positions risk:state:futures
   # O13 (2026-09-06): the monolithic paper orchestrator now writes the
   # UNSUFFIXED risk:state:futures hash (same key kill_switch reads), and its
   # period counters (daily/weekly/monthly PnL, consecutive losses) persist
   # until the period rolls over. Purge every variant so paper-accumulated
   # losses can never seed a live kill-switch decision. Review the keys first.
   # These two lines also use the PAPER target (-p 6379 -n 1); at the live
   # cutover run them against the LIVE stack's Redis (see "Redis access" above)
   # — purging paper's copy does nothing for a live kill_switch.
   redis-cli -p 6379 -n 1 --scan --pattern 'risk:state:futures*'
   redis-cli -p 6379 -n 1 --scan --pattern 'risk:state:futures*' | xargs -r redis-cli -p 6379 -n 1 del
   ```

   The purge is mandatory before the **live** cutover (Gate 2 checklist): the
   live kill_switch reads `risk:state:futures` verbatim, and a monthly counter
   carried over from paper would be evaluated against live thresholds.

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
  (shadow run writes the `:shadow` variant; isolated from live). Since O13
  (2026-09-06, PR #646) the monolithic `trader-futures` paper path also writes
  the unsuffixed key (gate `risk_state.monolithic_writer_enabled`), so in paper
  the unsuffixed hash holds paper PnL — purge it at cutover (step 1 above).
- `trading:futures:*[:shadow]` are the dashboard-native keys owned by
  `TradingStatePublisher`.
- The F-8 `FUTURES_ORCHESTRATOR_ENABLED` guard (`cli/main.py`, default `true`)
  prevents orchestrator↔decoupled double-trading. Set it to `false` at cutover,
  `true` at rollback.
- **One futures WS per KIS account** (see Gate 1): order_router defaults to
  `FUTURES_ORDER_ROUTER_FEED=stream` and opens none, so it may run beside
  `trader-futures`. `ws` mode and `futures-market-ingest` each open one — never
  run either while `trader-futures` owns the WS.
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
