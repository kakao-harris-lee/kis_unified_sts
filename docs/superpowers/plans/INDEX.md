# Superpowers Plans Index

Last updated: 2026-06-17.

`docs/superpowers/plans/` contains generated implementation plans. The completed
plans have been moved to [archive/](archive/) so this directory does not look
like an active backlog.

Use the paired design specs in `docs/superpowers/specs/` for design rationale,
and use `docs/runbooks/` for current operational procedures.

## Status

There are no active superpowers implementation plans at this level.

Completed records are retained under [archive/](archive/), including:

| Area | Archived Plans |
|---|---|
| Forecasting / LLM context | `2026-05-13-forecast-aware-paradigm`, `2026-06-06-llm-context-cron-m5b`, `2026-06-07-market-context-unify-f4` |
| Frontend / builder | `2026-05-31-nextjs-consolidation-cleanup`, `2026-06-01-futures-strategy-builder`, `2026-06-02-builder-funnel-redesign`, builder panel/template plans |
| Stock decoupled pipeline | M1/M4/M5 stock market ingest, strategy, risk/order, exit, monitor, stream cutover, orchestrator decommission plans |
| Futures decoupled pipeline | F1-F9 stream naming, decision producer, order router, market context, monitor, exit execution, live/orchestrator guards, WS reconnect, cutover plans |
| Historical strategy research | Williams %R / LLM-directed indicator / bb_reversion_15m / regime-gate research and productionization plans |

## Adding A New Superpowers Plan

1. Add new implementation plans at this level only while work is actively
   underway.
2. Link the design spec in `docs/superpowers/specs/`.
3. After implementation lands and runbooks/docs point at the current operating
   procedure, move the plan to `archive/` and update this index.
