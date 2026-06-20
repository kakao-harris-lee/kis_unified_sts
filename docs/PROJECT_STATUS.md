# Project Status - KIS Unified Trading Platform

**Last updated**: 2026-06-20

> Phased roadmap (Stock + Futures): [ROADMAP.md](ROADMAP.md) — authoritative.

## Current Runtime

- Frontend/API is consolidated behind Caddy. Default host entrypoint is
  `DASHBOARD_HOST_PORT=5080`, with `dashboard:8001` and
  `strategy-builder-ui:3100` kept internal.
- Stock paper flow uses the decoupled Compose pipeline:
  `stock-ingest` + `stock-pipeline`. The monolithic stock orchestrator is blocked
  after cutover with `STOCK_ORCHESTRATOR_ENABLED=false`.
- Futures primary strategy path is Setup A/C with LLM market context and
  explicit indicator/strategy-native exits. Decoupled futures services exist
  behind `futures-ingest`, `futures-pipeline`, and `futures-killswitch` profiles
  and should be cut over only through the F9 runbook.
- Scheduler/producers have been migrated into Compose profiles
  `scheduler` and `producers`.
- Dashboard `/experiments` now supports stock strategy experiment reports and
  on-demand jobs backed by `shared/backtest/experiment_runner.py`.

## Storage And Runtime Decisions

- Redis DB 1 is the runtime stream/state store.
- SQLite `RuntimeLedger` is the durable runtime ledger.
- Parquet/DuckDB is the historical market-data backend.
- ClickHouse is removed from active runtime, collection, backtest, and compose
  service paths.
- Futures ML/RL/TFT prediction paths have been removed. MLflow remains only as
  optional backtest/optimization experiment tracking.

## Active Strategies

Verified 2026-06-20 against `config/strategies/{stock,futures}/*.yaml` (`enabled` flag is the single source of truth).

| Asset | Strategy | Mode | Note |
|---|---|---|---|
| Stock | `momentum_breakout`, `pattern_pullback`, `williams_r` | Paper (enabled) | `momentum_breakout` re-enabled for paper observation (#443). Swing exits are signal-driven (three-stage); no blanket EOD liquidation. |
| Stock | `bb_reversion`, `opening_volume_surge`, `volume_accumulation`, `trend_pullback`, `vr_composite`, `technical_consensus`, `trend_continuation_vwap`, `daily_pullback`, `trix_golden` | Disabled | `enabled: false`. `technical_consensus` disabled after 0% win (2026-06-02); reactivation under review (see ROADMAP). |
| Futures | `setup_a_gap_reversion`, `setup_c_event_reaction` | Paper primary (enabled) | Setup A fires live signals; Setup C coded but ~0 signals (event sourcing sparse). Uses Setup target exits, LLM context/veto/risk hooks, live-mode guards. |
| Futures | `williams_r_15m`, `bb_reversion_15m`, `macd_ema_crossover_15m`, `momentum_breakout`, `trend_pullback`, `trix_golden` | Disabled | `enabled: false`. Trend strategies collapse in walk-forward; `bb_reversion_15m` disabled (triggered stock BEAR_EXIT, #479). |
| Futures | `llm_directed_indicator` | Deprecated | Not an active path without a separate redefinition gate. |

## Recent Decisions

**2026-06-20** - Documentation cleanup (this PR). Superseded RL/paradigm plans
and the synthetic-data stock validation summary were archived with SUPERSEDED
banners and de-indexed; a single authoritative [ROADMAP.md](ROADMAP.md) (Stock +
Futures) was added; `strategies.md` and Phase-5/Strategy-Lab/RegimeGate specs
were corrected for current state (no RL, no ClickHouse, Next.js UI).

**2026-06-17** - Documentation cleanup. `CLAUDE.md` was compacted, `AGENTS.md`
became a thin pointer, completed plan records moved to archive, and plan indexes
were refreshed.

**2026-06-14** - Stock experiment feature implemented. The runner, CLI,
scheduler entry, dashboard API, and `/experiments` UI are in place.

**2026-06-09** - Cron-to-Compose scheduler migration implemented. KIS one-shot
jobs run through the `scheduler` service and market-hours producers run through
the `producers` profile.

**2026-06-06 to 2026-06-08** - Stock and futures decoupled pipeline Compose
wiring and runbooks completed.

**2026-06-03** - ML/RL removal. `sts rl *`, `sts tft *`, `shared/ml/rl`,
`shared/ml/tft`, RL/TFT configs, RL shadow/counterfactual cron, and RL strategy
entry/exit components are removed.

**2026-06-03** - Runtime storage decoupling. Runtime writes default to Redis DB
1 + SQLite WAL, market-data collection/backtest/prewarm uses Parquet/DuckDB, and
default Python dependencies no longer include ClickHouse drivers.

## Open Validation

Full per-asset open list with owners/gates is in [ROADMAP.md](ROADMAP.md). Top items:

- **Stock:** HAR-RV log-RV transition (forecast model stale since 2026-05-31,
  daily refit failing — needs backtest + ~1wk shadow before cutover);
  `technical_consensus` reactivation decision (strong long-horizon backtest vs
  recent live loss); `momentum_breakout` redesign (retune still negative);
  Strategy Lab build-out. See
  [plans/2026-06-02-stock-reopt-har-rv-followups.md](plans/2026-06-02-stock-reopt-har-rv-followups.md).
- **Futures:** F9 decoupled cutover gates (shadow → Gate 2 → operator-gated
  cutover) before replacing the orchestrator path; Phase 5 Gate 1–3 to small
  live; Setup C activation (event-sourcing fix); kill-switch sentinel →
  shared-volume path (required before live).
- **Both:** Paper/live E2E smoke with Redis + SQLite only after each cutover;
  position-recovery drill after process restart; MLflow restart
  (`localhost:5000` down).
