# Project Status — KIS Unified Trading Platform

**Last updated**: 2026-06-03

## Current Phase

Runtime storage decoupling and ML/RL removal are active on PR #402.

- ClickHouse is being demoted from runtime prerequisite to optional research/mirror backend.
- SQLite `RuntimeLedger` is the default durable runtime ledger.
- Futures ML/RL prediction paths have been removed; futures work now uses LLM market context plus explicit indicator/strategy-native rules.

## Active Strategies

| Asset | Strategy | Mode | Note |
|-------|----------|------|------|
| Stock | `bb_reversion`, `opening_volume_surge`, `volume_accumulation` | Paper | Stock swing exits remain signal-driven; no blanket EOD liquidation. |
| Futures | `setup_a_gap_reversion`, `setup_c_event_reaction` | Paper, primary | Uses `setup_target_exit` and LLM context/veto/risk hooks. |
| Futures | `williams_r_15m`, `bb_reversion_15m` | Candidate | Indicator-based candidates for intraday/swing expansion. |
| Futures | `llm_directed_indicator` | Deprecated | Not an active path without a separate redefinition gate. |

## Recent Decisions

**2026-06-03** — ML/RL removal. `sts rl *`, `sts tft *`, `shared/ml/rl`, `shared/ml/tft`, RL/TFT configs, RL shadow/counterfactual cron, and RL strategy entry/exit components are removed. MLflow remains only as optional backtest/optimization experiment tracking.

**2026-06-03** — Runtime storage decoupling. Runtime writes default to Redis DB 1 + SQLite WAL. ClickHouse remains optional for research exports and mirrored analytics.

## Open Validation

- Paper/live E2E smoke with Redis + SQLite only.
- Position recovery drill after process restart.
- Full backtest/tier runner parity on Parquet/DuckDB source.
- PR #402 checks after the final ML/RL cleanup commit.
