# Plans Index

Last updated: 2026-06-17.

This index separates plans that still affect operational decisions from completed
implementation records. For the current runtime snapshot, start with
[../PROJECT_STATUS.md](../PROJECT_STATUS.md).

## Active

| Plan | Status |
|---|---|
| [2026-06-02-stock-reopt-har-rv-followups.md](2026-06-02-stock-reopt-har-rv-followups.md) | Open domain follow-up recommendations: HAR-RV log-RV validation, stock strategy reactivation decisions, MLflow ops. |

## Current Decisions And Reference

| Plan | Use Today |
|---|---|
| [2026-06-03-ml-rl-removal-llm-indicator-futures.md](2026-06-03-ml-rl-removal-llm-indicator-futures.md) | Current futures decision: ML/RL/TFT runtime paths removed; futures work uses Setup A/C, LLM context, and explicit indicators/rules. |
| [2026-06-03-runtime-storage-decoupling-implementation.md](2026-06-03-runtime-storage-decoupling-implementation.md) | Current storage decision: Redis DB 1 + SQLite runtime ledger + Parquet/DuckDB market data; ClickHouse removed from active runtime paths. |
| [2026-04-20-futures-paradigm-phase5-rollout.md](2026-04-20-futures-paradigm-phase5-rollout.md) | Futures live rollout gates and rollback policy; referenced by futures runbooks and live guards. |
| [2026-04-20-futures-paradigm-master.md](2026-04-20-futures-paradigm-master.md) | Parent futures roadmap. Historical RL statements are superseded by the 2026-06-03 removal decision. |
| [2026-05-03-llm-primary-rl-minimization.md](2026-05-03-llm-primary-rl-minimization.md) | Historical LLM-primary cutover record; superseded for future work by the 2026-06-03 removal decision. |
| [2026-05-26-strategy-lab-extension-design.md](2026-05-26-strategy-lab-extension-design.md) | Strategy Lab product direction; many pieces now exist in `strategy-builder-ui/`, dashboard APIs, and experiment runner. |

## Historical Reference Still Cited

| Plan | Why It Remains Top-Level |
|---|---|
| [2026-04-20-futures-paradigm-phase1-data-infra.md](2026-04-20-futures-paradigm-phase1-data-infra.md) | Spec backing Phase 1 verification/runbook references. |
| [2026-04-20-futures-paradigm-phase2-scoring.md](2026-04-20-futures-paradigm-phase2-scoring.md) | Spec backing Phase 2 scoring and verification references. |
| [2026-04-20-futures-paradigm-phase3-decision-engine.md](2026-04-20-futures-paradigm-phase3-decision-engine.md) | Spec backing decision-engine config and verification references. |
| [2026-04-20-futures-paradigm-phase4-execution.md](2026-04-20-futures-paradigm-phase4-execution.md) | Spec backing execution, kill-switch, weekly edge review, and verification references. |
| [2026-04-20-futures-paradigm-phase1-implementation-plan.md](2026-04-20-futures-paradigm-phase1-implementation-plan.md) | Phase 1 implementation breakdown. |
| [2026-04-20-futures-paradigm-phase2-implementation-plan.md](2026-04-20-futures-paradigm-phase2-implementation-plan.md) | Phase 2 implementation breakdown. |
| [2026-04-20-futures-paradigm-phase3-implementation-plan.md](2026-04-20-futures-paradigm-phase3-implementation-plan.md) | Phase 3 implementation breakdown. |
| [2026-04-20-futures-paradigm-phase4-implementation-plan.md](2026-04-20-futures-paradigm-phase4-implementation-plan.md) | Phase 4 implementation breakdown. |
| [2026-04-20-futures-paradigm-phase5-implementation-plan.md](2026-04-20-futures-paradigm-phase5-implementation-plan.md) | Phase 5 implementation breakdown; cited by live-mode guard code. |
| [2026-04-20-futures-trading-change-paradagms.md](2026-04-20-futures-trading-change-paradagms.md) | Original futures paradigm-change brief. |
| [2026-04-20-futures-paradigm-rl-repurposing.md](2026-04-20-futures-paradigm-rl-repurposing.md) | Historical v1 RL repurposing proposal; superseded by ML/RL removal. |
| [2026-04-20-futures-paradigm-rl-repurposing-v2.md](2026-04-20-futures-paradigm-rl-repurposing-v2.md) | Historical v2 RL repurposing proposal; superseded by ML/RL removal. |
| [2026-04-15-rl-retraining-data-refresh.md](2026-04-15-rl-retraining-data-refresh.md) | Historical RL retraining plan; do not resume without explicit operator reversal. |
| [2026-04-15-paper-trading-quality-recovery.md](2026-04-15-paper-trading-quality-recovery.md) | Paper-trading quality fixes and investigation record. |
| [2026-02-20-position-recovery-design.md](2026-02-20-position-recovery-design.md) | Position recovery and restart design. |
| [2026-02-26-stock-strategy-redesign.md](2026-02-26-stock-strategy-redesign.md) | Stock-side BB/VR redesign reference. |
| [2026-03-02-momentum-breakout-trend-mode-design.md](2026-03-02-momentum-breakout-trend-mode-design.md) | Stock momentum_breakout trend-mode design. |
| [VR_Trading_Strategy_Design_Spec.md](VR_Trading_Strategy_Design_Spec.md) | VR composite stock strategy spec. |

## Archive

Completed implementation records live under [archive/](archive/). Recent moves:

| Plan | Completion Record |
|---|---|
| [archive/2026-05-28-vite-dashboard-to-nextjs-migration.md](archive/2026-05-28-vite-dashboard-to-nextjs-migration.md) | Next.js-only frontend migration completed 2026-05-31. |
| [archive/2026-06-01-improve-ux.md](archive/2026-06-01-improve-ux.md) | Original builder-funnel UX prompt, superseded by the implemented superpowers spec/plan. |
| [archive/2026-06-06-compose-pipeline-services.md](archive/2026-06-06-compose-pipeline-services.md) | Stock pipeline Compose profile migration implemented. |
| [archive/2026-06-09-cron-to-compose-scheduler.md](archive/2026-06-09-cron-to-compose-scheduler.md) | Scheduler/producers Compose migration implemented. |
| [archive/2026-06-14-stock-strategy-experiment-backtest.md](archive/2026-06-14-stock-strategy-experiment-backtest.md) | Stock experiment runner/API/UI/scheduler implemented. |

Older archived plans remain in the same folder for historical context.

## Adding A Plan

1. Add new plans at `docs/plans/2026-MM-DD-<slug>.md`.
2. Put the new plan in **Active** while work is underway or operator decisions
   remain open.
3. Move completed implementation records to `archive/` once the current docs or
   code no longer need them as a top-level operational reference.
