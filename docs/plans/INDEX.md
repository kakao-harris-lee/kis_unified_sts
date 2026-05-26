# Plans Index

Last updated: 2026-05-26 (after Strategy Lab extension design).

This index categorizes plans by **status** so a returning operator/engineer
can quickly find what's still operative vs what's historical reference.

For an even higher-level "what's the project doing right now?" snapshot,
see [../PROJECT_STATUS.md](../PROJECT_STATUS.md).

---

## 🟢 Active — under active execution

The current master plan + the documents it directly references for
ongoing Phase 2 / Phase 5 work.

| Plan | Status |
|------|--------|
| [2026-05-03-llm-primary-rl-minimization.md](2026-05-03-llm-primary-rl-minimization.md) | **Master plan, v4.0** — Phase 2 cutover READY (2026-05-11). |
| [2026-04-20-futures-paradigm-master.md](2026-04-20-futures-paradigm-master.md) | Parent of the LLM-primary plan. Defines the futures paradigm rollout. |
| [2026-04-20-futures-paradigm-phase5-rollout.md](2026-04-20-futures-paradigm-phase5-rollout.md) | Phase 5 Gate 1–4 rollout spec — referenced by 7 docs / runbooks. |
| [2026-04-20-futures-paradigm-rl-repurposing-v2.md](2026-04-20-futures-paradigm-rl-repurposing-v2.md) | RL "auxiliary filter" v2 strategy — selectively superseded by the LLM-primary plan but still authoritative for the auxiliary-RL direction. |
| [2026-05-26-strategy-lab-extension-design.md](2026-05-26-strategy-lab-extension-design.md) | Visual Strategy Lab redesign: UI-built strategies, generated signals, and paper buy/sell execution. |

## 🟡 Reference — completed but still cited

Phase 1–4 specs are implemented; their verification gates are referenced
by `docs/runbooks/phase[1-4]-verification.md`.

| Plan | Use today |
|------|-----------|
| [2026-04-20-futures-paradigm-phase1-data-infra.md](2026-04-20-futures-paradigm-phase1-data-infra.md) | Spec backing `runbooks/phase1-verification.md`. |
| [2026-04-20-futures-paradigm-phase2-scoring.md](2026-04-20-futures-paradigm-phase2-scoring.md) | Spec backing `runbooks/phase2-verification.md`. |
| [2026-04-20-futures-paradigm-phase3-decision-engine.md](2026-04-20-futures-paradigm-phase3-decision-engine.md) | Spec backing `runbooks/phase3-verification.md`. |
| [2026-04-20-futures-paradigm-phase4-execution.md](2026-04-20-futures-paradigm-phase4-execution.md) | Spec backing `runbooks/phase4-verification.md`. |
| [2026-04-20-futures-paradigm-rl-repurposing.md](2026-04-20-futures-paradigm-rl-repurposing.md) | rl-repurposing v1 — superseded by v2 but still cited from v2 / master for historical context. |
| [2026-04-20-futures-trading-change-paradagms.md](2026-04-20-futures-trading-change-paradagms.md) | Original paradigm-change brief; cited from the Phase 1 plan. |
| [2026-04-20-futures-paradigm-phase1-implementation-plan.md](2026-04-20-futures-paradigm-phase1-implementation-plan.md) | Phase 1 implementation breakdown. |
| [2026-04-20-futures-paradigm-phase2-implementation-plan.md](2026-04-20-futures-paradigm-phase2-implementation-plan.md) | Phase 2 implementation breakdown. |
| [2026-04-20-futures-paradigm-phase3-implementation-plan.md](2026-04-20-futures-paradigm-phase3-implementation-plan.md) | Phase 3 implementation breakdown. |
| [2026-04-20-futures-paradigm-phase4-implementation-plan.md](2026-04-20-futures-paradigm-phase4-implementation-plan.md) | Phase 4 implementation breakdown. |
| [2026-04-20-futures-paradigm-phase5-implementation-plan.md](2026-04-20-futures-paradigm-phase5-implementation-plan.md) | Phase 5 implementation breakdown. |
| [2026-04-15-rl-retraining-data-refresh.md](2026-04-15-rl-retraining-data-refresh.md) | RL retraining pipeline data-refresh spec — pipeline still in production. |
| [2026-04-15-paper-trading-quality-recovery.md](2026-04-15-paper-trading-quality-recovery.md) | Paper-trading quality fixes — most landed; cited from runbooks. |
| [2026-02-20-position-recovery-design.md](2026-02-20-position-recovery-design.md) | Position-recovery sentinel/restart design — still authoritative. |
| [2026-02-26-stock-strategy-redesign.md](2026-02-26-stock-strategy-redesign.md) | Stock-side BB / vr_composite redesign cited by impl docs. |
| [2026-03-02-momentum-breakout-trend-mode-design.md](2026-03-02-momentum-breakout-trend-mode-design.md) | Stock momentum_breakout trend-mode design. |
| [VR_Trading_Strategy_Design_Spec.md](VR_Trading_Strategy_Design_Spec.md) | VR composite stock strategy spec. |

## ⚪ Archive — completed and no longer cited

Moved under [archive/](archive/) in PR #203. Read-only history; safe to
ignore unless you need historical context for a specific change.

| Plan | Era |
|------|-----|
| [archive/2026-01-20-migration-phase1-critical-components.md](archive/2026-01-20-migration-phase1-critical-components.md) | Jan 2026 — initial migration phase 1 |
| [archive/2026-01-20-migration-phase2-trading-engines.md](archive/2026-01-20-migration-phase2-trading-engines.md) | Jan 2026 — migration phase 2 |
| [archive/2026-01-20-migration-phase3-operations.md](archive/2026-01-20-migration-phase3-operations.md) | Jan 2026 — migration phase 3 |
| [archive/2026-01-20-migration-phase4-dashboard-strategies.md](archive/2026-01-20-migration-phase4-dashboard-strategies.md) | Jan 2026 — migration phase 4 |
| [archive/2026-01-21-multi-review-remediation.md](archive/2026-01-21-multi-review-remediation.md) | Jan 2026 — multi-review remediation |
| [archive/2026-01-22-migration-phase5-deployment.md](archive/2026-01-22-migration-phase5-deployment.md) | Jan 2026 — migration phase 5 (initial, since superseded by 2026-04-20 phase 5) |
| [archive/2026-01-22-orchestrator-wiring-design.md](archive/2026-01-22-orchestrator-wiring-design.md) | Jan 2026 — orchestrator wiring design |
| [archive/2026-01-22-rate-limiter-design.md](archive/2026-01-22-rate-limiter-design.md) | Jan 2026 — KIS rate limiter design |
| [archive/2026-01-23-code-review-improvements.md](archive/2026-01-23-code-review-improvements.md) | Jan 2026 — code-review improvements (multi-phase task list) |
| [archive/2026-02-17-bb-reversion-swing-redesign.md](archive/2026-02-17-bb-reversion-swing-redesign.md) | Feb 2026 — BB reversion swing redesign |
| [archive/2026-02-17-opening-volume-surge-data-pipeline.md](archive/2026-02-17-opening-volume-surge-data-pipeline.md) | Feb 2026 — OVS data pipeline |
| [archive/2026-02-17-volume-accumulation-data-pipeline.md](archive/2026-02-17-volume-accumulation-data-pipeline.md) | Feb 2026 — volume accumulation data pipeline |
| [archive/2026-02-21-broker-position-verification-design.md](archive/2026-02-21-broker-position-verification-design.md) | Feb 2026 — broker position verification |
| [archive/2026-02-22-position-robustness-improvements.md](archive/2026-02-22-position-robustness-improvements.md) | Feb 2026 — position robustness |
| [archive/2026-02-23-stock-backtest-infra-design.md](archive/2026-02-23-stock-backtest-infra-design.md) | Feb 2026 — stock backtest infra design |
| [archive/2026-02-23-stock-backtest-infra-plan.md](archive/2026-02-23-stock-backtest-infra-plan.md) | Feb 2026 — stock backtest infra plan |
| [archive/2026-02-24-bb-reversion-performance-analysis.md](archive/2026-02-24-bb-reversion-performance-analysis.md) | Feb 2026 — BB reversion perf analysis |
| [archive/2026-02-26-stock-strategy-redesign-impl.md](archive/2026-02-26-stock-strategy-redesign-impl.md) | Feb 2026 — stock strategy redesign impl (companion to the still-cited design doc) |
| [archive/2026-03-02-momentum-breakout-trend-mode.md](archive/2026-03-02-momentum-breakout-trend-mode.md) | Mar 2026 — momentum_breakout trend-mode rollout (companion to design) |
| [archive/2026-03-10-dashboard-unification-design.md](archive/2026-03-10-dashboard-unification-design.md) | Mar 2026 — dashboard unification |
| [archive/2026-04-14-paper-trading-db-integrity.md](archive/2026-04-14-paper-trading-db-integrity.md) | Apr 2026 — paper trading DB integrity |
| [archive/2026-04-15-ops-hardening-and-polish.md](archive/2026-04-15-ops-hardening-and-polish.md) | Apr 2026 — ops hardening & polish |

## How to add a new plan

1. New plans go at the top level (`docs/plans/2026-MM-DD-<slug>.md`).
2. Once a plan's work is fully merged AND no other doc/code references it,
   move it to `archive/` with `git mv` (preserves history) and update this
   index in the same PR.
3. Use this categorization when deciding:
   - **Active** = under execution; expect more PR work.
   - **Reference** = done but cited from current docs/code (don't archive).
   - **Archive** = done AND not cited from anywhere active.
