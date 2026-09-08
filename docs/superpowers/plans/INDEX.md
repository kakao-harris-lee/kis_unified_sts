# Superpowers Plans Index

Last updated: 2026-09-08.

`docs/superpowers/plans/` contains generated implementation plans that still
need active attention. Completed plans have been moved to [archive/](archive/)
so this directory does not look like an active backlog.

Use the paired active design specs in `docs/superpowers/specs/` for design
rationale. Completed specs are retained under `docs/superpowers/specs/archive/`,
and current operational procedures belong in `docs/runbooks/`.

## Status

Active plans:

| Date | Plan | Purpose |
|---|---|---|
| 2026-07-04 | [runtime refactoring next priorities](2026-07-04-runtime-refactoring-next-priorities.md) | P1/P2/P3 execution plan for remaining orchestrator slices, dashboard trades route split, CLI split, KIS/backfill cleanup, and large-test decomposition after `2140c9ed`. |
| 2026-07-04 | [orchestrator decomposition](2026-07-04-orchestrator-decomposition.md) | Facade-preserving decomposition plan for the monolithic trading orchestrator while F-9 remains the futures runtime replacement path. |
| 2026-06-28 | [quant system expert work allocation](2026-06-28-quant-system-expert-work-allocation.md) | Expert-lane execution plan for market-structure policy, KOSPI 200 futures, stock ATS/SOR, strategy evidence, Workbench transparency, and QA. |
| 2026-06-27 | [architecture audit parallel plan](2026-06-27-architecture-audit-parallel-plan.md) | Parallel read-only architecture audit of orchestrator, stock pipeline, futures pipeline, and shared streaming boundaries. |
| 2026-06-27 | [architecture hardening phase 1](2026-06-27-architecture-hardening-phase1.md) | Implementation plan for shared futures instrument resolution and a reusable multi-input Redis stream stage. |
| 2026-06-27 | [modularization phase 1](2026-06-27-modularization-phase1.md) | First low-risk module boundary extractions for instruments, dashboard asset helpers, frontend builder auto-conditions, and CLI data commands. |
| 2026-06-27 | [signals decision trace](2026-06-27-signals-decision-trace.md) | Read-only `/signals` transparency layer for LLM context, strategy inputs, lifecycle, scorecard evidence, and evidence gaps. |

Active design specs:

| Date | Spec | Purpose |
|---|---|---|
| 2026-07-04 | [orchestrator decomposition design](../specs/2026-07-04-orchestrator-decomposition-design.md) | Current facade-preserving orchestrator decomposition rationale. |
| 2026-06-27 | [signals decision trace design](../specs/2026-06-27-signals-decision-trace-design.md) | Current signal transparency and evidence model rationale. |

Completed records are retained under [archive/](archive/), including:

| Area | Archived Plans |
|---|---|
| Recent completed / reference plans | June 2026 track-a crashguard, stock prewarm/bear gate, GDELT source, LLM scorecard, code-quality cleanup, futures strategy research, theme leader universe, and stream processor audit logging plans |
| Forecasting / LLM context | `2026-05-13-forecast-aware-paradigm`, `2026-06-06-llm-context-cron-m5b`, `2026-06-07-market-context-unify-f4` |
| Frontend / builder | `2026-05-31-nextjs-consolidation-cleanup`, `2026-06-01-futures-strategy-builder`, `2026-06-02-builder-funnel-redesign`, builder panel/template plans |
| Stock decoupled pipeline | M1/M4/M5 stock market ingest, strategy, risk/order, exit, monitor, stream cutover, orchestrator decommission plans |
| Futures decoupled pipeline | F1-F9 stream naming, decision producer, order router, market context, monitor, exit execution, live/orchestrator guards, WS reconnect, cutover plans |
| Futures strategy R&D verdicts (2026-06-25) | [CTA swing momentum](archive/2026-06-25-futures-cta-swing-momentum.md) — **VALIDATED but NO-SHIP standalone**: edge is real but regime-concentrated and too weak alone; a regime-gated variant is a possible follow-up (PR #541). [Trend-day ORB](archive/2026-06-25-futures-trend-day-strategy.md) — **NO-SHIP**: walk-forward net-negative, OOS Sharpe −0.18, IS→OOS inversion = overfitting (PR #530). [Conviction-hold gate](archive/2026-06-25-futures-conviction-hold-strategy.md) — **NO-SHIP**: conjunction gate is anti-predictive, OOS 0% TP / −7.51% (PR #534). [mr-highvol Setup D spec](../specs/archive/2026-06-25-futures-mr-highvol-setup-d.md) — **SHIPPED to paper 2026-06-26** (PR #533), code live in main (`shared/decision/setups/vwap_reversion.py`, `shared/strategy/entry/setup_d_adapter.py`), `config/strategies/futures/setup_d_vwap_reversion.yaml` currently `enabled: true`. A follow-up risk mitigation, [Setup D trend filter design](../specs/2026-07-07-setup-d-trend-filter-design.md) (2026-07-07), found the reversion setup entering repeatedly against steady one-way trend days; the filter is implemented but **ships OFF by default** (enable acceptance criteria not met on available data). |
| Historical strategy research | Williams %R / LLM-directed indicator / bb_reversion_15m / regime-gate research and productionization plans |
| Completed specs | Historical design specs live in `../specs/archive/`; leave them out of default context unless auditing old design rationale. |

## Adding A New Superpowers Plan

1. Add new implementation plans at this level only while work is actively
   underway.
2. Link the design spec in `docs/superpowers/specs/`.
3. After implementation lands and runbooks/docs point at the current operating
   procedure, move the plan to `archive/` and update this index.
