# llm_directed_indicator — Optuna tuning findings (2026-05-16/17)

Tool: `scripts/optimize_llm_directed_indicator.py`
Data: `data/kospi200f_1m_ch_101S6000.csv` (51,396 bars, 2025-07-01 → 2026-04-23)
Backtest path mirrors `cli/main.py::backtest_run` futures exactly
(`BacktestConfig.futures(10_000_000, point_value=50_000)`), FLAT-bias
indicators-only floor (spec §4(a)).

## VERDICT — re-scoped §6 gate (2026-05-17, operator-approved): **FAIL ❌**

The original "best-trial Sharpe>1.0 & PF>1.2" bar was withdrawn (it
rewards knife-edge curve-fits). The re-scoped **robust non-catastrophic
floor** gate judges the *distribution* of valid trials:

Canonical run: `_rescoped` (70 trials, holdout split 2026-02-01,
min-trades=50), tool-printed verdict:

| Check | Requirement | Result | |
|---|---|---|---|
| (a) median valid trial, train | Sharpe ≥ 0 & PF ≥ 1.0 | **Sharpe −2.07 / PF 0.78** | FAIL |
| (b) broad basin | ≥ 25% of valid clear (a) | **5/40 = 12.5%** | FAIL |
| (c) selected cfg OOS | Sh≥0,PF≥1,MDD≤25,ret≥0 | 8.68/3.49/7.5%/+163% | pass¹ |

¹ (c) passes only because the *selected* config is the single lucky
outlier — exactly what (a)+(b) exist to reject. ~87% of valid trials
are money-losing on the floor.

**Robustness of the verdict:** reproduced on two independent codebases
(`runtime/main-current` hand-calc: median −2.25, basin 3/38=7.9%;
`origin/main` native tool run: median −2.07, basin 5/40=12.5%). Small
metric drift, identical decisive FAIL — the conclusion is not sensitive
to codebase, trial count, or seed-path.

**Implication:** spec §4(a)'s "indicators-only floor is a reasonable
live safety floor" is **empirically falsified** (see spec §6.1). The
floor is *actively unsafe* without the LLM bias — DO NOT ACTIVATE; YAML
stays `enabled: false`, no tuned params applied.

## Runs

| Run | Sharpe | PF | Trades | Win | Ret | MDD | Note |
|---|---|---|---|---|---|---|---|
| Baseline (untuned YAML) | −6.85 | 0.28 | 14 | — | −37.7% | 41.5% | floor |
| Full-history, no floor (84 tr) | 9.69 | 3.88 | 127 | 70.9% | +444% | 14.6% | in-sample overfit |
| OOS train, no floor (66 tr) | 7.25 | 4.37 | **8** | 75.0% | +7.6% | 9.2% | degenerate (8 trades) |
| OOS test, no floor | 5.06 | 4.56 | 19 | 52.6% | +37% | 5.3% | "pass" but noise |
| OOS train, min-trades=50 (67 tr) | 1.42 | 1.21 | 90 | 37.8% | +15.8% | 27.6% | realistic, marginal |
| **OOS test, min-trades=50** | **8.63** | **4.08** | 106 | 40.6% | +199% | 7.1% | gate-pass BUT untrustworthy |

## Supporting detail (why the re-scoped gate fails)

Under the *withdrawn* numeric bar the OOS number passed, yet the result
was never a trustworthy edge — the same evidence the re-scoped gate now
encodes formally:

1. **Knife-edge config, no robust basin.** With the min-trades floor,
   of 39 valid trials exactly ONE clears the gate (Sharpe 1.42); all
   others are Sharpe ≈ −0.0 … 0.4. The rest of the valid landscape is
   churn (453–1829 trades, Sharpe ≈ 0). A single fragile point is not
   an edge.
2. **In-sample edge is marginal once degeneracy removed.** Realistic
   train estimate: Sharpe 1.42, PF 1.21 (right on the 1.2 line),
   MDD 27.6%, win 37.8%. Weak.
3. **OOS ≫ TRAIN is a red flag, not a win.** Robust strategies degrade
   gracefully OOS; a 6× *improvement* (1.42→8.63) signals a favorable
   OOS regime + a data-quality asymmetry: 2025-H2 connected-future data
   is sparse (~4.2k bars/mo) vs dense OOS (~8k bars/mo).
4. **Parameter-importance unstable across all 3 independent runs**
   (w_momentum 0.49 → w_trend 0.61 → diffuse 0.25/0.24/0.18/0.17). No
   stable causal structure → window-specific curve-fit.
5. **ATR exit dims inert in backtest** (`atr=0.0000` throughout);
   stop-loss is the only effective exit. Tuned `atr_*` values are
   unvalidated and would behave differently live.
6. **Consistent with the design's own thesis** (spec §4(a)): the
   FLAT-bias indicators-only path is a *conservative floor*, not the
   alpha — the LLM directional bias is the intended edge. Gating
   activation on the floor being a great standalone strategy was the
   wrong test.

## Recommendation (operator decision — spec §6 "operator sets the bar")

- **Keep `enabled: false`; do NOT apply tuned params** (YAML untouched).
- The methodology fix (min-trades floor) is correct and is now in the
  tool — reusable for any futures strategy.
- Next levers, in order of leverage:
  1. **Re-scope the §6 gate** with the operator: the FLAT floor is not
     meant to carry alpha; a non-catastrophic floor (OOS Sharpe > 0,
     PF ≥ 1.0, bounded MDD) plus a separate LLM-bias evaluation is the
     methodologically sound bar, not Sharpe>1.0 on the floor alone.
  2. **Fix ATR-in-backtest plumbing** so the composite exit is actually
     exercised/validated before any activation.
  3. **Rolling walk-forward** (multiple windows) instead of one split,
     to measure regime-stability rather than one lucky OOS window.
  4. **Per-family scorer params** (spec §6 listed them; not yet exposed
     through `LLMDirectedIndicatorConfig`).
