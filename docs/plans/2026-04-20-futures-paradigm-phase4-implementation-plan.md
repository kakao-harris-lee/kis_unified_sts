# Futures Paradigm — Phase 4 Execution — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** activate the real-time pipeline (decision_engine daemon → risk_filter daemon → order_router daemon → KIS paper broker), add Passive-Maker limit execution with pseudo-OCO, log every fill with slippage, and install a 6-condition automated kill switch. Close the signal → paper-fill loop that Phase 3 only drove in-memory.

**Architecture:** 4 new long-running services (`services/{decision_engine, risk_filter, order_router, kill_switch}/main.py`), V3 ClickHouse migration (`kospi.order_fills`), `shared/execution/executor.py` gains `place_passive_limit_futures()`, `shared/paper/broker.py` gains pseudo-OCO watcher. All services use `ServiceConfigBase` + Prometheus + systemd + graceful-shutdown on SIGTERM. Market orders permitted only for: `signal.valid_until` expiry force-close, session-end force-close (15:10 KST), kill-switch force-flat. Everything else passive limit.

**Tech Stack:** Python 3.11+, asyncio, `redis.asyncio` (consumer groups), `aiochclient`, `pydantic v2`, `pytest` + `pytest-asyncio` + `fakeredis`. Reuses Phase 1-3 shared modules; no new heavy deps.

**Parent spec:** `docs/plans/2026-04-20-futures-paradigm-phase4-execution.md`
**Depends on:** Phase 3 merged (all done: PRs #125/126/127/128/129).
**Blocks:** Phase 5 rollout.

---

## File Structure

**Create (new files):**

```
infra/clickhouse/migrations/
└── V3__create_order_fills.sql

shared/execution/
├── fill_logger.py                      # stream:order.fill + CH batched writer
├── passive_maker.py                    # place_passive_limit_futures + _wait_for_fill
├── pseudo_oco.py                       # PseudoOCO + watcher tasks
├── force_close.py                      # valid_until / EOD / kill-switch paths
└── order_result.py                     # OrderResult + enums

shared/paper/
└── oco_broker_shim.py                  # VirtualBroker extension for stop orders

shared/risk/
└── runtime_state.py                    # Redis-backed mutating RiskState (Phase 3's
                                        # RiskStateSnapshot was immutable; daemon needs writes)

services/
├── decision_engine/main.py             # MarketContext → Setup.check() per bar → stream:signal.candidate
├── risk_filter/main.py                 # consumer group; RiskFilterLayer → stream:signal.final
├── order_router/main.py                # consumer group; passive_maker + pseudo_oco
└── kill_switch/main.py                 # 6-condition monitor + force-flat + systemd stop

config/
├── execution.yaml                      # MODIFY: add order_router section
├── kill_switch.yaml                    # 6 conditions + check interval
└── decision_engine_runtime.yaml        # MODIFY: add daemon cadence + stream names

deploy/systemd/
├── kis-decision-engine.service
├── kis-risk-filter.service
├── kis-order-router.service
└── kis-kill-switch.service

scripts/
└── kill_switch_clear.sh                # manual recovery

jobs/
└── weekly_edge_review.py               # Mon 05:00 KST cron — spec §5.3

docs/runbooks/
├── phase4-verification.md              # 2-week paper gate checklist
└── futures-paradigm-failure-modes.md   # spec §9 deliverable

tests/unit/execution/
├── test_passive_maker.py
├── test_pseudo_oco.py
├── test_force_close.py
└── test_fill_logger.py

tests/unit/paper/
└── test_oco_broker_shim.py

tests/unit/services/
├── test_decision_engine_main.py
├── test_risk_filter_main.py
├── test_order_router_main.py
└── test_kill_switch_main.py

tests/integration/
├── test_signal_to_fill_e2e.py          # decision_engine → filter → router → paper broker → CH
└── test_kill_switch_drill.py           # exercise each of 6 trigger conditions
```

**Modify (existing files):**

- `shared/execution/executor.py` — add `place_passive_limit_futures()` + keep existing market path (`ORD_DVSN_CD="02"`) for force-close callers
- `shared/paper/broker.py` — add stop-order simulation + OCO watcher hook
- `services/monitoring/metrics.py` — append 8 Phase-4 metric families
- `shared/risk/state.py` — add mutating `RiskState.record_trade()` etc. for daemon (currently snapshot only)

---

## Conventions Reminder (applies to all tasks)

- **Feature branch:** `feat/futures-paradigm-phase4`. Never commit to main.
- **Test runner:** `source .venv/bin/activate && pytest ...` — not system pytest.
- **Redis DB 1** always. Every XADD followed by `expire(stream, 86400)`.
- **ClickHouse writes:** `.replace(tzinfo=None)` before `DateTime64('UTC')`, publishers **re-raise on CH failure** (no silent swallow — lessons from PRs #126/127/128).
- **Format/lint:** `black <modified>`, `ruff check --fix <modified>`. Never `black .` on the tree.
- **ServiceConfigBase** for every new config class. No plain `BaseModel` for top-level service configs.
- **No dead YAML:** every config key added must be loaded by at least one runtime caller in this same PR (PR #128 finding).
- **Graceful shutdown:** every daemon handles SIGTERM → flush → close resources (Phase 1/2 pattern).
- **Kill-switch respects:** `rl_mppo` must keep running on its own account — do not touch `services/trading/orchestrator.py`.

---

## Task 1: Scaffold + V3 migration

**Files:**
- Create: `infra/clickhouse/migrations/V3__create_order_fills.sql`
- Create: `tests/unit/migrations/test_v3_migration.py`
- Branch: `feat/futures-paradigm-phase4` from main.

- [ ] **Step 1** Branch + test (schema existence + expected columns per spec §5.1).
- [ ] **Step 2** Run — expect FAIL.
- [ ] **Step 3** Write SQL verbatim from spec §5.1.
- [ ] **Step 4** Apply via `python scripts/migrations/apply_clickhouse_migrations.py` and verify with `DESC kospi.order_fills`.
- [ ] **Step 5** Commit: `feat(infra): V3 migration — kospi.order_fills`.

---

## Task 2: `shared/execution/order_result.py`

Tiny frozen dataclass returned by the execution layer.

- [ ] **Step 1** Test: `OrderResult.filled(...)`, `OrderResult.missed(reason=...)`, state fields.
- [ ] **Step 2** Implement `OrderResult` + `OrderState` enum (FILLED, MISSED, CANCELLED, ERROR).
- [ ] **Step 3** Commit: `feat(execution): OrderResult dataclass`.

---

## Task 3: `shared/execution/fill_logger.py`

Mirrors Phase 2's `ScoredPublisher` + Phase 3's `SignalsAllWriter` pattern.

- [ ] **Step 1** Test with `fakeredis` + `AsyncMock` CH:
  - XADD to `stream:order.fill` with expire(86400)
  - Batch INSERT into `kospi.order_fills` (batch_size=10)
  - Re-raises on CH failure (pattern from PR #126/127)
- [ ] **Step 2** Implement `FillLogger` with `log_fill()` + `flush()`.
- [ ] **Step 3** Commit: `feat(execution): FillLogger — stream:order.fill + CH writer`.

---

## Task 4: Mini-tick math utilities

Extract from spec §3.3:
- `_round_to_tick(price, tick_size) -> float` — float-safe double-round
- `_compute_slippage_ticks(requested, filled, direction, tick_size) -> float` — sign convention per direction

- [ ] **Step 1** Tests: boundary (exactly on tick), off-tick rounding, long +slip / short -slip.
- [ ] **Step 2** Put in `shared/execution/tick_math.py`. **Important:** `executor.py:803`'s `/ 0.05` hardcoding is F200-only — replace with `spec.tick_size_points` via `tick_math._compute_slippage_ticks`.
- [ ] **Step 3** Grep `0.05` in `shared/execution/` — only docstrings/comments remain.
- [ ] **Step 4** Commit: `refactor(execution): tick math utilities — remove /0.05 hardcoding`.

---

## Task 5: `shared/execution/passive_maker.py`

Spec §3.2 `place_passive_limit_futures()`.

- [ ] **Step 1** Tests (mock KIS client):
  - Happy path: bid/ask lookup → limit order → wait for fill → log fill
  - Timeout: `_wait_for_fill` returns None → cancel → `OrderResult.missed("passive_not_filled")`
  - Slippage calculation integrated
- [ ] **Step 2** Implement. Reuses tick_math from Task 4 + FillLogger from Task 3.
- [ ] **Step 3** Commit: `feat(execution): passive limit + timeout-then-cancel`.

---

## Task 6: `shared/paper/oco_broker_shim.py` — stop order simulation

`VirtualBroker` currently single-order only. Extend to simulate stop orders in paper.

- [ ] **Step 1** Tests: stop-loss only fires when price crosses trigger, no otherwise.
- [ ] **Step 2** Implement `OCOBrokerShim` that wraps `VirtualBroker` + stores pending stop orders in a local dict, ticks on each market-data update.
- [ ] **Step 3** Commit: `feat(paper): stop order simulation shim for pseudo-OCO`.

---

## Task 7: `shared/execution/pseudo_oco.py`

Spec §4.2. Registers stop + target, watcher cancels the other side when one fills.

- [ ] **Step 1** Integration test: fill entry → register bracket → stop hits → target cancelled. And reverse: target hits → stop cancelled.
- [ ] **Step 2** Implement `PseudoOCO` class + `OCOHandle` + watcher via `asyncio.create_task`.
- [ ] **Step 3** Commit: `feat(execution): PseudoOCO bracket + watcher`.

---

## Task 8: `shared/execution/force_close.py`

Spec §4.3 — the three whitelisted market-order conditions.

- [ ] **Step 1** Tests: `valid_until` expired → market close; `now >= 15:10 KST` → all positions closed; `kill_switch_event` → immediate force-flat.
- [ ] **Step 2** Implement with clear pre-conditions in each path.
- [ ] **Step 3** Commit: `feat(execution): force-close paths — valid_until, EOD, kill-switch`.

---

## Task 9: `shared/risk/runtime_state.py`

`RiskStateSnapshot` from Phase 3 is immutable (read-only snapshot for filter evaluation). Daemon needs mutating ops: `record_trade`, `record_loss`, `reset_daily`, etc.

- [ ] **Step 1** Tests: round-trip through Redis (uses existing `RiskState` from Phase 3 for persistence), pnl accumulation, consecutive-loss counter, daily reset at 09:00 KST.
- [ ] **Step 2** Implement. Persist via the existing `risk:state:futures` HASH.
- [ ] **Step 3** Commit: `feat(risk): runtime mutating state for Phase 4 daemons`.

---

## Task 10: `services/decision_engine/main.py`

Per-minute daemon — builds `MarketContext` from live market data + runs Setup A/C per bar.

- [ ] **Step 1** Integration test with `fakeredis`:
  - Seed a minute bar into a synthetic live feed shim
  - Setup A fires at the right moment
  - `stream:signal.candidate` receives the XADD
- [ ] **Step 2** Implement. `MarketContextReplay.iter_contexts()` is backtest-oriented — new `LiveMarketContextBuilder` reuses its precompute helpers but pulls from Redis/KIS live feed.
- [ ] **Step 3** Commit: `feat(services): decision_engine daemon — 1-min MarketContext replay`.

---

## Task 11: `services/risk_filter/main.py`

Consumer-group daemon on `stream:signal.candidate`. Applies `RiskFilterLayer.from_config()` + runtime providers (ATR, spread, open-position).

- [ ] **Step 1** Integration test: pass + reject cases, `signals_all` write for both, XADD to `stream:signal.final` on pass.
- [ ] **Step 2** Implement. Mirrors Phase 2's `NewsScorerDaemon` consumer-group pattern (XREADGROUP + XACK).
- [ ] **Step 3** Commit: `feat(services): risk_filter daemon — consumer group + signals_all writer`.

---

## Task 12: `services/order_router/main.py`

Consumer on `stream:signal.final`. Routes to passive_maker, sets up pseudo-OCO, logs fills.

- [ ] **Step 1** End-to-end integration: signal → place_passive_limit → fill → OCO register. Use `AsyncMock` KIS + `VirtualBroker` via `OCOBrokerShim`.
- [ ] **Step 2** Implement.
- [ ] **Step 3** Commit: `feat(services): order_router daemon — passive limit + OCO`.

---

## Task 13: `services/kill_switch/main.py` + config

Spec §6. 6 conditions, check every 30s (YAML), on trigger: shutdown order_router + force-flat + Telegram + systemd stop.

- [ ] **Step 1** Write `config/kill_switch.yaml` verbatim from spec §6.1.
- [ ] **Step 2** Write drill-test fixtures (6 trigger scenarios).
- [ ] **Step 3** Implement `KillSwitchDaemon` + `KillCondition` ABC with 6 concrete conditions (DailyLossCondition, WeeklyLossCondition, ConsecutiveLossesCondition, ApiErrorRateCondition, NewsPipelineLagCondition, ClickHouseInsertFailCondition).
- [ ] **Step 4** `tests/integration/test_kill_switch_drill.py` — all 6 trigger conditions cause: (a) stream:risk.event emit, (b) shutdown signal to order_router, (c) force-flat, (d) telegram, (e) systemd stop (we mock systemd).
- [ ] **Step 5** Commit.

---

## Task 14: Prometheus metrics (spec §7.1)

- [ ] Append 8 metric families + helpers to `services/monitoring/metrics.py`, per Phase 2/3 pattern.
- [ ] Unit test.
- [ ] Commit: `feat(monitoring): Phase 4 order/fill/slippage/kill-switch metrics`.

---

## Task 15: Weekly Edge Review cron (spec §5.3)

`jobs/weekly_edge_review.py` — Setup A/C per-week stats + alerts. Cron wrapper in `scripts/cron/weekly_edge_review.sh`.

- [ ] Test the SQL query against a seeded test fixture CH.
- [ ] Telegram alert plumbing via `shared/notification/telegram.py` (reuse).
- [ ] Commit.

---

## Task 16: systemd units + deploy scripts

Per Phase 1/2 pattern: 4 systemd units + crontab installer (for weekly_edge_review).

- [ ] Write `.service` files for all 4 daemons. Each has `After=redis-server.service` + kis-news-collector (for `rl_mppo` unaffected).
- [ ] Commit.

---

## Task 17: `shared/execution/executor.py` — append `place_passive_limit_futures`

Glue that wires passive_maker + fill_logger + OCO. Keep existing market path intact for force-close callers.

- [ ] Integration test exercising the full path through the method.
- [ ] Commit: `feat(execution): executor.place_passive_limit_futures integration`.

---

## Task 18: End-to-end integration test

`tests/integration/test_signal_to_fill_e2e.py`:

1. Seed a `stream:signal.final` message
2. `OrderRouterDaemon.run()` briefly
3. Assert `stream:order.fill` has the expected entry
4. Assert `kospi.order_fills` row matches (via `AsyncMock.execute.call_args`)
5. Assert OCO registered and cancels on stop hit

- [ ] Commit.

---

## Task 19: Runbook + failure-mode doc

- `docs/runbooks/phase4-verification.md` — 2-week gate checklist per spec §9
- `docs/runbooks/futures-paradigm-failure-modes.md` — 5-10 known failure modes + recovery steps
- Commit.

---

## Task 20: Full sweep + push + draft PR

- [ ] **Step 1** `pytest tests/ -v` — full sweep, >= 80% coverage on all Phase 4 new modules
- [ ] **Step 2** `black <modified> && ruff check --fix <modified>`
- [ ] **Step 3** Push + draft PR with body linking spec §9 gate items
- [ ] **Step 4** Merge gated on:
    - 2 weeks paper uptime
    - `systemctl show kis-{decision_engine,risk_filter,order_router,kill_switch} -p NRestarts` = 0
    - `SELECT count() FROM kospi.order_fills WHERE filled_at >= now() - INTERVAL 14 DAY` >= 20
    - `SELECT avg(slippage_ticks) FROM kospi.order_fills WHERE ...` ≤ 0.4
    - Kill switch drill test green
    - Weekly Edge Review report reviewed
    - Backtest vs paper PnL divergence < 20%
    - `rl_mppo` unaffected (no regression in its own operational dashboard)

---

## Self-Review

**Spec coverage (phase4-execution.md §2–§9):**

| Spec item | Task |
|-----------|------|
| V3 `order_fills` migration | 1 |
| `OrderResult` + `FillLogger` | 2, 3 |
| Tick math (remove `/0.05`) | 4 |
| Passive Maker | 5 |
| Stop-order paper shim + Pseudo-OCO | 6, 7 |
| Force-close (3 whitelisted cases) | 8 |
| Mutating `RiskState` | 9 |
| 4 daemons | 10, 11, 12, 13 |
| Prometheus | 14 |
| Weekly Edge Review | 15 |
| systemd + deploy | 16 |
| `executor.place_passive_limit_futures` | 17 |
| Signal→Fill e2e | 18 |
| Runbook + failure modes | 19 |
| Gate sweep + PR | 20 |

operational dashboard `futures-execution` dashboard (spec §7.2) intentionally NOT in this plan — low-code-risk ops artifact composed during the 2-week paper window.

**Carried-forward lessons from Phase 1-3:**

- ClickHouseConfig.from_env(database="kospi") explicit pass-through (Task 10/11/12/13)
- tz-strip before DateTime64 writes (Task 3)
- Re-raise on CH failure (Task 3)
- await redis.expire(stream, 86400) after every XADD (Task 3, 10, 11, 12)
- ServiceConfigBase for every new service config (Tasks 10-13)
- Format/lint modified files only (global convention)
- No dead YAML (PR #128 lesson — every config key must have a loader in this PR)

**Type consistency:**
- `OrderResult` (Task 2) is the return type of all execution layer methods — single source.
- `Signal` (from Phase 3) flows from `stream:signal.final` through `order_router` unchanged.
- `TradeRecord` from Phase 3 is backtest-only — Phase 4 writes directly to `kospi.order_fills` via `FillLogger`.
- `RiskStateSnapshot` (Phase 3, immutable) is constructed on every filter evaluation; `RiskState` (Task 9) is the mutating sibling.

**Risks flagged + mitigations:**

- KIS API rate limit during heavy signal bursts → `order_router` respects existing `_RateLimiter` in `shared/kis/`.
- Pseudo-OCO race: stop + target fill in same bar. `PseudoOCO` watcher picks first-seen, cancels second atomically. Spec says "loss wins on ties" — preserved.
- `rl_mppo` double-entry: `risk_filter` has `OpenPositionFilter` that reads `rl_mppo`'s Redis state (same `trading:futures:positions` HASH) + Phase 4 own state. One `has_open_position_provider` queries both.
- systemd restart without clearing kill-switch state: `kill_switch` writes a sentinel file that `order_router` checks on startup. If present, refuses to start.

**Placeholder scan:**
- No TBDs. Every task has concrete files to create + test structure.
- Weekly Edge Review SQL uses spec §5.3 as-is but extracted to a separate file so operators can edit without rebuilding.

---

## Execution Handoff

Two execution options (Phase 1/2/3 pattern):

1. **Subagent-Driven (recommended)** — one fresh subagent per task, 20 tasks total. Phase 4 is the largest phase yet; checkpoint after groups {1-4}, {5-9}, {10-13}, {14-20}.
2. **Inline** — `superpowers:executing-plans`; checkpoint every 4 tasks.

Run `/review` (Momus) on this plan before starting if you want critic pass on the daemon boundaries / kill switch drill coverage.

**Pre-start checklist:**
- [ ] Confirm Phase 3 gate is closed (or explicitly waived by user for code-parallel development)
- [ ] Verify `rl_mppo` account + keys are separate from Phase 4 paper account (avoid double-entry)
- [ ] Telegram bot token + chat id configured for kill-switch alerts (`TELEGRAM_FUTURES_*`)
- [ ] Test KIS paper account accessible via `KIS_FUTURES_MARKET=mock` or equivalent — spec says paper; validate.
