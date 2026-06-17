# Project Status - KIS Unified Trading Platform

**Last updated**: 2026-06-17

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

| Asset | Strategy | Mode | Note |
|---|---|---|---|
| Stock | `bb_reversion`, `opening_volume_surge`, `volume_accumulation` | Paper/configured | Stock swing exits remain signal-driven; no blanket EOD liquidation. |
| Stock | registry strategies such as `pattern_pullback`, `williams_r`, `vr_composite`, `trend_pullback` | Experiment/backtest/paper candidates | Enabled status is controlled by each YAML config and experiment specs. |
| Futures | `setup_a_gap_reversion`, `setup_c_event_reaction` | Paper primary | Uses Setup target exits, LLM context/veto/risk hooks, and live-mode guards. |
| Futures | `williams_r_15m`, `bb_reversion_15m`, other indicator candidates | Candidate/reference | Use explicit validation gates before promotion. |
| Futures | `llm_directed_indicator` | Deprecated | Not an active path without a separate redefinition gate. |

## Recent Decisions

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

- HAR-RV log-RV follow-up and stock strategy reactivation decisions from
  [plans/2026-06-02-stock-reopt-har-rv-followups.md](plans/2026-06-02-stock-reopt-har-rv-followups.md).
- Paper/live E2E smoke with Redis + SQLite only after each cutover.
- Position recovery drill after process restart.
- Futures decoupled F9 cutover gates before replacing the orchestrator path.
