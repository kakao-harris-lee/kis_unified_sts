# Futures Strategy Improvement Roadmap

**Date:** 2026-07-06
**Basis:** the backtest re-examination (`docs/analysis/2026-07-06-futures-strategy-backtest-reexamination.md`) after fixing the setup-context KST timezone bug (PR #593), plus the accumulated futures R&D record.

## Governing constraints (non-negotiable)

- **Intraday KOSPI200 futures are mean-reverting.** Every trend / momentum / ORB / CTA / conviction-hold variant has been rigorously falsified (walk-forward). **Do not relitigate them.** Evidence: `reports/trend_following_attempt_2026-05-27.md`, `docs/superpowers/plans/archive/2026-06-25-futures-{trend-day-strategy,cta-swing-momentum,conviction-hold-strategy}.md`.
- **Futures are minute-only**, trustworthy window **Dec 2025 – Apr 2026** (~88 days, one regime) — thin evidence, wide CIs. No daily futures partition → longer-horizon strategies stay DATA-BLOCKED.
- **NO RL/TFT** (removed PR #402). LLM is veto / risk-mode / size-scaling / threshold-tuning / explainable note only; **final entry/exit timing must be reproducible indicators**. All thresholds in YAML; long/short symmetric.

## Where we actually are (from the re-examination)

- **Setup D (VWAP reversion)** — the one validated new edge. Authoritative walk-forward OOS **Sharpe +2.135, 135 trades, 4/4 OOS-profitable folds, symmetric**. Paper-active; live-dormant. Self-contained → CLI-backtestable.
- **Setup A (gap reversion)** — paper-active; standing evidence Sharpe ~5.12 (N=14) from a dedicated harness. **Un-evaluable via the CLI backtest** (needs macro-overnight injection).
- **Setup C (event reaction)** — paper-active but **~0 signals** (live producer gap + backtest event-injection gap).
- **bb_reversion_15m** — disabled; strong *in-sample* MR result (Sharpe 3.64, 185 trades) → a walk-forward candidate.
- Everything trend/momentum — confirmed negative. Do not revive.

---

## Prioritized plan

### P1 — Correctness & harness completeness (do first; restores trust)

1. **Backtest-harness input injection** (newly surfaced). `BacktestStrategyAdapter._context_metadata` (`shared/backtest/adapter.py:369-434`) injects only symbol/accumulation metadata, so **Setup A and Setup C cannot fire in the CLI backtest** (no `macro_overnight`, no `scheduled_events`). Inject both from historical sources (macro from `market_context_history` / overnight S&P feed; events from the scheduled-event store) so A/C become CLI-backtestable and comparable to Setup D. Until then, A/C evidence must come from their dedicated harnesses — say so explicitly wherever their numbers are quoted.
2. **Setup C live-producer bug.** `setup_context_builder.py:53-58` defaults `last_15min_high/low` → `current_price`; live has no orchestrator producer for the 15-min range, so the breakout is **unreachable live** (explains ~0 signals). Adopt Setup D's causal self-computed range, or wire `get_recent_range` into the orchestrator EntryContext. (Ref: prior fix pattern in the orchestrator 15min-range trap, #533/#537.)
3. **08:45 open-anchor re-validation of Setup A + Setup D.** Their headline numbers were computed at the **09:00** anchor; the regular session moved to **08:45** (2026-06-28, `docs/runbooks/market-structure-policy.md`). Re-run the dedicated walk-forwards at 08:45 before any promotion decision.

### P2 — Regime-condition the mean-reversion setups (the one real alpha lever)

The convergent recommendation of *both* the ORB and conviction-hold NO-SHIPs: **don't hold the trend day — instead feed a confirmed-strong-regime read into Setup A/C/D** to relax/size the mean-reversion or suppress counter-trend fades on strong-regime days. The **HAR-RV `RegimeGate` is already wired** (per-strategy YAML opt-in, `enabled: false`, reads `forecast:vol:current`, PERMISSIVE-on-miss, PASS Δ=+3.26 in a prior backtest). Validate per-setup via `scripts/gate_futures_strategy.py --head-to-head` (require ΔSharpe ≥ margin AND no MDD worsening AND re-scoped OOS pass) before enabling any gate. Keep `regime_detection_mode: adaptive` OFF (ADX thresholds DATA-BLOCKED, single-regime sample — `docs/analysis/2026-07-05-gate-b-regime-adx-characterization.md`).

### P3 — bb_reversion_15m walk-forward (new candidate, evidence-gated)

The sweep's strongest in-sample MR result besides Setup D. Run a rigorous walk-forward (`gate_futures_strategy.py --strategy bb_reversion_15m --space config/optuna/futures/... --holdout-split ...`). Watch the `mtf_base_15m` bucket (15m cadence). **Promote to paper only if it clears OOS** — in-sample MR over a single vol regime is exactly the curve-fit trap. If it fails walk-forward, keep it disabled and record the NO-SHIP.

### P4 — Evidence accumulation (thin-data reality)

Setup A/C/D have tiny N (14 / 7 / 135). Accumulate more clean minute windows and paper-trading data before any live promotion; monitor "why didn't futures trade today?" via the existing `trading:futures:setup_eval` reject-observation stream (`shared/strategy/entry/setup_eval_publisher.py`). LLM daily-bias validation stays forward-only (history starts June 2026).

### Out of scope / do-not-revive

Intraday trend-following, trend-day ORB, CTA daily/swing momentum, conviction-hold — all NO-SHIP with walk-forward evidence. Regime-gated CTA diversifier remains DATA-BLOCKED (no ≥3y daily futures partition). No RL/TFT.

---

## Sequencing

P1 is a prerequisite for trustworthy comparison and unblocks A/C. P2 is the primary alpha work and depends on P1.3 (correct anchor). P3 runs independently once the harness is trusted. Each item ships as its own PR with a walk-forward artifact (not an in-sample number) as its acceptance gate.
