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

---

## De-risking checkpoint (2026-05-18) — live == probe bars: **MATCH ✅**

Before committing to the M–L Option-B build + 3–4mo paper, the single
load-bearing assumption was tested: do the *live* orchestrator path's
15m bars (`MultiTimeframeCandleAccumulator`,
services/trading/indicator_engine.py) equal the probe's offline
`_resample_15m` bars — the bars that actually passed the robust gate?

Tool: `scripts/derisk_live_vs_probe_15m.py` (feeds the 101S6000 1m CSV
bar-by-bar through the exact live accumulator class + flush; diffs
sequence-aligned vs `_resample_15m`).

Result: **5,615 / 5,615 = 100.000% bar-for-bar identical** (minute +
OHLCV within 1e-6), count match YES. The wall-clock 15-min `_get_bucket`
grid exactly reproduces pandas `resample("15min")` including
session-open and intraday-gap bins (the anticipated divergence did not
materialize — verified empirically, not by inspection).

**Risk #1 (the highest: live ≠ probe-bars → edge unvalidated) is
ELIMINATED.** The robust-gate result transfers to live bars; Option B
(reuse `MultiTimeframeCandleAccumulator` → 15m BB/RSI → `mean_reversion`,
closed-bars-only) is sound to proceed. Remaining items are the M–L build
and the ~3–4mo thin-sample paper duration (planning constraints, not
technical risks). Look-ahead (risk #2) is mitigable by closed-bar
discipline (the harness used only closed buckets + flush, never the
in-progress `_buffer`).

---

## T7 parity defect + decision-cadence resolution (2026-05-18)

The productionization parity gate (registered backtest path == the
probe that passed the robust gate) **FAILED**, catching a real
architectural defect: Option B (15m BB/RSI injected under plain keys,
engine still on 1m bars) makes the strategy DECIDE every 1 minute with
15m indicators → **1,584 trades**, not the **~345** of the gate-passing
strategy (probe ran the engine on 15m bars → one decision per 15m bar).
Pure-1m = 1,832. The de-risk checkpoint validated 15m *bar*
equivalence — necessary but **insufficient**; *decision-cadence*
equivalence was unvalidated and broken.

**Resolution (operator-approved):** a shared, look-ahead-safe
**decision-cadence gate** (`shared/strategy/decision_cadence.py`, plan
Task 6.5) throttles entry+exit to closed-15m-bar boundaries in BOTH the
backtest adapter and the live `StrategyManager` (DRY, backtest==live;
no-op when `timeframe_minutes ≤ 1`). Acceptance = the parity test
(`test_registered_backtest_matches_probe_15m_profile`) passes
(~345-trade regime).

**Accepted tradeoff (carried into the T8 runbook):** at 15m cadence,
stop-loss/exit is only checked once per closed 15m bar — a –4% stop can
overshoot intra-15m. This is an inherent property of the strategy that
*passed the robust gate* (the probe only ever saw 15m bars);
reproducing it is required for parity. Engine risk-net + EOD remain
independent safety nets; an intra-bar hard-stop is a documented future
enhancement, out of scope for parity.
