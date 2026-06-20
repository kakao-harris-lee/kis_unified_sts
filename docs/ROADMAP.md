# Roadmap — KIS Unified Trading Platform

> **Authoritative roadmap — supersedes scattered plan docs. Last updated 2026-06-20 KST.**

This is the single per-asset roadmap. For the live runtime snapshot see
[PROJECT_STATUS.md](PROJECT_STATUS.md); for the plan catalogue see
[plans/INDEX.md](plans/INDEX.md). Status legend: **done** ✅ · **in-progress** 🔄 ·
**planned** ⏳.

Trusted current sources cited below:
[PROJECT_STATUS.md](PROJECT_STATUS.md),
[plans/INDEX.md](plans/INDEX.md),
[plans/2026-06-03-ml-rl-removal-llm-indicator-futures.md](plans/2026-06-03-ml-rl-removal-llm-indicator-futures.md),
[runbooks/futures-pipeline-cutover-f9.md](runbooks/futures-pipeline-cutover-f9.md),
[runbooks/stock-pipeline-cutover-m5d.md](runbooks/stock-pipeline-cutover-m5d.md).

All times are KST (Asia/Seoul). Strategy `enabled` flags in
`config/strategies/{stock,futures}/*.yaml` are the single source of truth for
active/disabled state.

---

## Stock

### North Star

Cost-adjusted positive absolute return — after a ~0.50% round-trip cost,
Sharpe > 1.0 with positive monthly expected value — plus a visual **Strategy Lab**
that shortens the design → backtest → paper → feedback loop.

### Current operating state

- **Paper only.** No live trading: the real accounts lack margin/education
  approval. A real KIS key supplies market data; orders go through the
  `VirtualBroker` (`KIS_REAL_TRADING=false`).
- **Pipeline (decoupled Compose):** screener/universe → M4-P (strategy) →
  M4-R (risk) → M4-O (order) → M4-X (three-stage, signal-driven exit; **no
  blanket EOD liquidation**) → M5a (monitor). The monolithic stock orchestrator
  is blocked after cutover (`STOCK_ORCHESTRATOR_ENABLED=false`).
- **Enabled strategies (2026-06-20):** `momentum_breakout` (re-enabled for paper
  observation, #443), `pattern_pullback`, `williams_r`.
- **Disabled:** `bb_reversion`, `opening_volume_surge` (+variants),
  `volume_accumulation`, `trend_pullback`, `vr_composite`,
  `technical_consensus` (0% win 2026-06-02), `trend_continuation_vwap`,
  `daily_pullback`, `trix_golden`.

### Phases

| Phase / Milestone | Status | Gate / Owner |
|---|---|---|
| Decoupled Compose pipeline (M5d cutover: `stock-ingest` + 5 services; monolith blocked) | ✅ done | [runbooks/stock-pipeline-cutover-m5d.md](runbooks/stock-pipeline-cutover-m5d.md) |
| Host-cron → Compose scheduler/producers migration | ✅ done | operator |
| Bear-exit regime wiring (#458: M4-P publishes regime → M4-X bear-exit gate) | ✅ done | — |
| Experiment runner Phase 1–5 (#473–#477: `sts experiment run` + nightly 16:40 KST + `/api/experiments` + `/experiments` UI + 30-day minute backfill) | ✅ done | — |
| HAR-RV log-RV forecast transition | 🔄 in-progress | backtest + ~1wk shadow before cutover; forecast model stale since 2026-05-31, daily refit failing |
| `technical_consensus` reactivation | 🔄 in-progress | strong long-horizon backtest vs recent ~3wk live loss → regime-verify, then small |
| `momentum_breakout` redesign / retune | 🔄 in-progress | retune still negative (recent Sharpe ≈ −5.24); observe in paper |
| Strategy Lab Phase 1–7 (visual design → backtest → paper → feedback) | 🔄 in-progress | design done ([plans/2026-05-26-strategy-lab-extension-design.md](plans/2026-05-26-strategy-lab-extension-design.md)); build partial; UI is Next.js (`strategy-builder-ui/`) |
| Position-recovery drill + Redis/SQLite E2E smoke | ⏳ planned | after each cutover / process restart |
| MLflow restart (localhost:5000 down) | ⏳ planned | ops |
| Stock live trading | ⏳ planned (blocked) | requires margin/education approval on real accounts; separate promotion tier |

### Open next-steps

- Validate HAR-RV log-RV (backtest + 1-week shadow) before cutting the forecast
  model over; see
  [plans/2026-06-02-stock-reopt-har-rv-followups.md](plans/2026-06-02-stock-reopt-har-rv-followups.md).
- Decide `technical_consensus` reactivation after regime verification (small size first).
- Continue Strategy Lab build-out (signal → paper-order workflow is the center).
- Run the position-recovery drill and the Redis + SQLite E2E smoke.
- Restart MLflow for experiment tracking.

---

## Futures

### North Star

The **LLM interprets market context** (veto / risk-mode / size / threshold), and
an **indicator + rule strategy (Setup A/C) owns entry/exit timing**. Thresholds
live in YAML; runtime state is Redis DB 1 + the SQLite ledger. RL/TFT prediction
paths are removed and must not be reintroduced
([plans/2026-06-03-ml-rl-removal-llm-indicator-futures.md](plans/2026-06-03-ml-rl-removal-llm-indicator-futures.md)).

### Current operating state

- **Paper, live-gated.** Live is guarded by `config/futures_live.yaml::enabled`
  (= false) plus the Redis flag `futures:live:suspended`
  (`shared/execution/live_mode_guard.py`).
- Runs the monolithic `trader-futures` orchestrator. The decoupled chain is
  **dormant** (pre-F-9): profiles `futures-ingest`, `futures-pipeline`,
  `futures-killswitch` exist with a double-trade guard, but the daemons are not
  registered in the running Compose stack.
- **Enabled strategies (2026-06-20):** `setup_a_gap_reversion` (fires live
  signals), `setup_c_event_reaction` (coded but ~0 signals — event scores sparse).
- **Disabled / deprecated:** `williams_r_15m` (reference), `bb_reversion_15m`
  (disabled — triggered a stock BEAR_EXIT, #479), `macd_ema_crossover_15m`,
  `momentum_breakout`, `trend_pullback`, `trix_golden`; `llm_directed_indicator`
  deprecated. All trend strategies collapse in walk-forward (intraday futures are
  mean-reverting) — do not enable.

### Phases

| Phase / Milestone | Status | Gate / Owner |
|---|---|---|
| Phase 1–4 paradigm shift (data infra, scoring, decision engine, execution) | ✅ done | — |
| Phase 2 cutover (LLM-primary + Setup A/C; RL shadow → off, 2026-05-11) | ✅ done | — |
| RL/TFT fully removed (#402, 2026-06-03) | ✅ done | [plans/2026-06-03-ml-rl-removal-llm-indicator-futures.md](plans/2026-06-03-ml-rl-removal-llm-indicator-futures.md) |
| F-1..F-8 decoupled chain implemented + double-trade guard (#424–#431) | ✅ done | — |
| RegimeGate P2-③ injected (#330) | ✅ done | ClickHouse audit table best-effort → PERMISSIVE on miss (no behavior change) |
| Over-trading / fast stop-out fixes (#479) | ✅ done | — |
| Reject-reason observability (#483) + throttled setup-eval logging (#484) | ✅ done | — |
| F-9 shadow validation (Gate 1: `--profile futures-pipeline`, 3–5 trading days) | 🔄 in-progress | operator-gated; [runbooks/futures-pipeline-cutover-f9.md](runbooks/futures-pipeline-cutover-f9.md) |
| F-9 Gate 2 → decoupled cutover (replace orchestrator path) | ⏳ planned | operator written approval; `trader` flag false + daemon-mode env |
| Phase 5 Gate 1–3 → small live (100 signals + backtest ±20% + MDD/slippage + kill-switch drill) | ⏳ planned | [plans/2026-04-20-futures-paradigm-phase5-rollout.md](plans/2026-04-20-futures-paradigm-phase5-rollout.md) (procedure; RL/systemd/ClickHouse refs there are historical) |
| Setup C activation | ⏳ planned | needs event-sourcing fix (event scores currently empty) |
| Kill-switch sentinel → shared-volume path | ⏳ planned | required before live |
| Futures cutover verify/rollback automation script (stock analogue exists) | ⏳ planned | — |
| HAR-RV log-RV validation (futures side) | ⏳ planned | — |

### Open next-steps

- Run F-9 Gate 1 shadow (`docker compose --profile futures-pipeline ...`,
  3–5 trading days), then Gate 2, then operator-gated cutover —
  [runbooks/futures-pipeline-cutover-f9.md](runbooks/futures-pipeline-cutover-f9.md).
- Drive Phase 5 Gate 1–3 toward a small live allocation (procedure in the
  archived master is superseded; use the phase5-rollout doc's gate procedure).
- Fix event sourcing so Setup C produces signals, then evaluate.
- Move the kill-switch sentinel to a shared-volume path before any live run.
- Build the futures cutover verify/rollback automation script.
