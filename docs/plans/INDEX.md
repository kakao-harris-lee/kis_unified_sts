# Plans Index

Last updated: 2026-07-04.

This index separates plans that still affect operational decisions from completed
implementation records. For the current runtime snapshot, start with
[../PROJECT_STATUS.md](../PROJECT_STATUS.md). **The authoritative phased roadmap
(Cross-Asset + Stock + Futures) is [../ROADMAP.md](../ROADMAP.md)** — it supersedes
the scattered plan docs for "where is each asset headed".

## Active

| Plan | Status |
|---|---|
| [2026-07-04-runtime-refactoring-roadmap.md](2026-07-04-runtime-refactoring-roadmap.md) | **Runtime refactoring and event-driven roadmap** — additive Interface/Decorator/Factory plan to reduce coupling and agent context cost; runtime large-file split priority 3 completed in `83e94681`; remaining active scope covers setup-adapter split, registry/factory split, orchestrator decomposition, and safe futures monolith -> F-9 event-driven transition. |
| [2026-07-02-unified-investment-system-roadmap.md](2026-07-02-unified-investment-system-roadmap.md) | **Cross-asset unified investment system roadmap** — maps [통합_투자_시스템_전략_설계서.md](../통합_투자_시스템_전략_설계서.md) onto the current codebase: Market Risk Score (0–100) from futures market structure (foreign flow/OI/program/basis) + macro, unified regime engine, integrated MDD circuit breaker, hedge advisor, `/market` dashboard, Track A ledger. **Phases P0–P6 code merged 2026-07-03 (risk gates shadow-default); stays Active for the operator gates (backfill/enforce flips/drill/holdings) and open items O11–O17.** |
| [2026-06-22-quant-ops-workbench-uiux.md](2026-06-22-quant-ops-workbench-uiux.md) | Active UI/UX roadmap for Quant Ops Workbench: P0 cockpit, signal trace, risk/exposure, backtest-vs-paper comparator; structured for multi-agent implementation lanes. |
| [2026-06-02-stock-reopt-har-rv-followups.md](2026-06-02-stock-reopt-har-rv-followups.md) | Open domain follow-up recommendations: HAR-RV log-RV validation, stock strategy reactivation decisions, MLflow ops. |

## Current Decisions And Reference

| Plan | Use Today |
|---|---|
| [2026-06-03-ml-rl-removal-llm-indicator-futures.md](2026-06-03-ml-rl-removal-llm-indicator-futures.md) | Current futures decision: ML/RL/TFT runtime paths removed; futures work uses Setup A/C, LLM context, and explicit indicators/rules. |
| [2026-06-03-runtime-storage-decoupling-implementation.md](2026-06-03-runtime-storage-decoupling-implementation.md) | Current storage decision: Redis DB 1 + SQLite runtime ledger + Parquet/DuckDB market data; ClickHouse removed from active runtime paths. |
| [2026-04-20-futures-paradigm-phase5-rollout.md](2026-04-20-futures-paradigm-phase5-rollout.md) | Futures live rollout Gate 1–4 procedure (still valid) + rollback policy; RL/systemd/ClickHouse references are historical (see top note in the doc). |
| [2026-05-26-strategy-lab-extension-design.md](2026-05-26-strategy-lab-extension-design.md) | Strategy Lab product direction (active); many pieces now exist in `strategy-builder-ui/`, dashboard APIs, and experiment runner. UI is Next.js, not Vite. |

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
| [2026-02-20-position-recovery-design.md](2026-02-20-position-recovery-design.md) | Position recovery and restart design. |
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
| [archive/2026-04-15-paper-trading-quality-recovery.md](archive/2026-04-15-paper-trading-quality-recovery.md) | Historical paper-quality investigation; RL/ClickHouse sections obsolete after 2026-06-03 removals. |
| [archive/2026-04-20-futures-trading-change-paradagms.md](archive/2026-04-20-futures-trading-change-paradagms.md) | Original futures paradigm brief; superseded by Setup A/C + LLM-context roadmap and current rollout gates. |

### Historical / Archived — superseded 2026-06-20 (DO NOT REFERENCE for current work)

These plans were moved to `archive/` on 2026-06-20 with a SUPERSEDED banner.
They are kept for audit trail only. Use the replacement docs instead.

| Archived plan | Replaced by |
|---|---|
| [archive/2026-04-20-futures-paradigm-master.md](archive/2026-04-20-futures-paradigm-master.md) | [2026-06-03-ml-rl-removal-llm-indicator-futures.md](2026-06-03-ml-rl-removal-llm-indicator-futures.md) + [../ROADMAP.md](../ROADMAP.md). Phase 5 *procedure* remains live in [2026-04-20-futures-paradigm-phase5-rollout.md](2026-04-20-futures-paradigm-phase5-rollout.md). |
| [archive/2026-05-03-llm-primary-rl-minimization.md](archive/2026-05-03-llm-primary-rl-minimization.md) | [2026-06-03-ml-rl-removal-llm-indicator-futures.md](2026-06-03-ml-rl-removal-llm-indicator-futures.md). LLM-primary cutover audit trail. |
| [archive/2026-04-20-futures-paradigm-rl-repurposing.md](archive/2026-04-20-futures-paradigm-rl-repurposing.md) | RL removed 2026-06-03 → [2026-06-03-ml-rl-removal-llm-indicator-futures.md](2026-06-03-ml-rl-removal-llm-indicator-futures.md). |
| [archive/2026-04-20-futures-paradigm-rl-repurposing-v2.md](archive/2026-04-20-futures-paradigm-rl-repurposing-v2.md) | RL removed 2026-06-03 → [2026-06-03-ml-rl-removal-llm-indicator-futures.md](2026-06-03-ml-rl-removal-llm-indicator-futures.md). |
| [archive/2026-04-15-rl-retraining-data-refresh.md](archive/2026-04-15-rl-retraining-data-refresh.md) | RL removed 2026-06-03; do not resume retraining without explicit operator reversal. |
| [archive/2026-02-26-stock-strategy-redesign.md](archive/2026-02-26-stock-strategy-redesign.md) | ClickHouse-era; data layer obsolete (now Parquet/DuckDB). Current: [../ROADMAP.md](../ROADMAP.md) + [../PROJECT_STATUS.md](../PROJECT_STATUS.md). |

> The synthetic-data stock validation summary
> [`../archive/STOCK_STRATEGY_VALIDATION_SUMMARY.md`](../archive/STOCK_STRATEGY_VALIDATION_SUMMARY.md)
> was also archived 2026-06-20 (it is a top-level doc, not a plan).

Older archived plans remain in the same folder for historical context.

## Adding A Plan

1. Add new plans at `docs/plans/2026-MM-DD-<slug>.md`.
2. Put the new plan in **Active** while work is underway or operator decisions
   remain open.
3. Move completed implementation records to `archive/` once the current docs or
   code no longer need them as a top-level operational reference.
