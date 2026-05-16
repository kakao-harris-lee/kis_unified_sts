# llm_directed_indicator — Optuna tuning findings (2026-05-16/17)

Tool: `scripts/optimize_llm_directed_indicator.py`
Data: `data/kospi200f_1m_ch_101S6000.csv` (51,396 bars, 2025-07-01 → 2026-04-23)
Backtest path mirrors `cli/main.py::backtest_run` futures exactly
(`BacktestConfig.futures(10_000_000, point_value=50_000)`), FLAT-bias
indicators-only floor (spec §4(a)). §6 gate = Sharpe>1.0 AND PF>1.2.

## Runs

| Run | Sharpe | PF | Trades | Win | Ret | MDD | Note |
|---|---|---|---|---|---|---|---|
| Baseline (untuned YAML) | −6.85 | 0.28 | 14 | — | −37.7% | 41.5% | floor |
| Full-history, no floor (84 tr) | 9.69 | 3.88 | 127 | 70.9% | +444% | 14.6% | in-sample overfit |
| OOS train, no floor (66 tr) | 7.25 | 4.37 | **8** | 75.0% | +7.6% | 9.2% | degenerate (8 trades) |
| OOS test, no floor | 5.06 | 4.56 | 19 | 52.6% | +37% | 5.3% | "pass" but noise |
| OOS train, min-trades=50 (67 tr) | 1.42 | 1.21 | 90 | 37.8% | +15.8% | 27.6% | realistic, marginal |
| **OOS test, min-trades=50** | **8.63** | **4.08** | 106 | 40.6% | +199% | 7.1% | gate-pass BUT untrustworthy |

## Conclusion: gate technically PASSES, but DO NOT ACTIVATE

The numeric §6 gate passes out-of-sample, yet the result is **not a
trustworthy edge** and must not gate activation:

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
