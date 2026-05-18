# bb_reversion_15m — decisive robust-gate probe (2026-05-18)

Tool: `scripts/probe_bb_reversion_15m_gate.py`
Data: `data/kospi200f_1m_ch_101S6000.csv` → resampled 1m→15m
(5,615 15m bars, 2025-07-01 → 2026-04-23). Holdout split 2026-02-01,
min-trades 25. **Identical** `_rescoped_gate` / `_objective_value` /
holdout machinery as the run that deprecated `llm_directed_indicator`
→ apples-to-apples.

## Why this probe

Every prior KOSPI200-futures intraday signal failed WF/counterfactual
(`memory/futures_strategy_history.md`); the **lone exception** is
`bb_reversion_15m` at 15-min resampling (documented 2026-02 WF:
Train 5.16 → Test 3.84, −25.5% degradation). Operator-approved cheapest
decisive test: does even the historical WF-survivor clear the *re-scoped
robust* gate on *current* data? If not → "no robust futures intraday
edge" prior confirmed, option (a) dead. If yes → one viable signal
exists.

## Result — RE-SCOPED GATE: **PASS ✅** (decisively, broad basin)

| Gate component | `llm_directed` (deprecated) | **`bb_reversion_15m`** |
|---|---|---|
| (a) median valid TRAIN Sharpe / PF | −2.07 / 0.78 → FAIL | **+10.69 / 8.41 → PASS** |
| (b) robust basin (≥25%) | 12.5% (5/40) knife-edge | **100% (57/57) → PASS** |
| (c) selected-cfg OOS non-catastrophic | lucky single outlier | Sharpe 12.0 / PF 3.45 / 34 tr → PASS |

- Baseline (WF-optimal YAML params, 15m): Sharpe 8.21, PF 7.77,
  345 trades, win 57%, MDD 4.2%.
- 70 trials, 57 valid (≥25 trades, non-degenerate); **all 57**
  non-catastrophic — a broad robust basin, the opposite of
  `llm_directed`'s 1-of-39 knife-edge.
- Independently corroborated by the historical WF prior.

**This overturns the "no robust KOSPI200-futures intraday edge" prior.**
There is one — at the 15-min timeframe, exactly where history pointed.
A mean-reversion strategy robustly working on a documented
mean-reverting instrument is mechanistically coherent (not a curve-fit
coincidence).

## Mandatory caveats — "passes backtest gate" ≠ "deploy"

1. **Absolute returns/Sharpe are inflated** by the futures P&L-accounting
   artifact seen all session (+2238% baseline is fantasy; Sharpe 10–15
   is implausible in reality). Only the *relative robustness* (vs the
   same-engine `llm_directed` FAIL) and *sign/consistency* are
   trustworthy — NOT the magnitudes.
2. **Thin sample**: ~25–34 trades per window — the significance
   boundary the original 2026-02 analysis explicitly flagged.
3. Backtest on ~10 mo of 15m data with a documented 2025-H2 sparsity
   asymmetry. Real validation = **paper**, not backtest.
4. **No production 15m-resample wiring exists.** `mean_reversion`
   declares no timeframe-suffixed `required_indicators`; the probe
   resampled 1m→15m manually. Productionizing requires building that
   wiring (StreamingIndicatorEngine.MultiTimeframeAccumulator exists per
   the option-(a) research, but mean_reversion must declare/consume 15m
   bars, or a live resample step is added).

## Recommendation

`bb_reversion_15m` is the **one** candidate worth productionizing.
Next scoped step: design the 15m-resample wiring + a paper-validation
plan; keep `config/strategies/futures/bb_reversion_15m.yaml`
`enabled: false` until paper evidence + operator approval (Phase-5-style
gate). Do NOT infer deployability from these inflated backtest
magnitudes — the paper stage is the real bar.
