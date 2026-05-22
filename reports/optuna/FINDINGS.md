# llm_directed_indicator — Optuna tuning findings (2026-05-16/17)

> **⛔ DECISION 2026-05-17: DEPRECATED — do not activate.** No robust
> standalone edge on KOSPI200 1-min futures; re-scoped §6 gate FAIL on
> three independent lines (gate / ceiling bracket / per-family probe).
> `enabled: false` permanent, no tuned params applied. Canonical
> rationale: design spec §8. Code/tests retained for reference only.

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

---

## LLM-bias contribution evaluation (2026-05-17) — replay BLOCKED → ceiling bracket → **NO-GO**

**Replay is impossible.** Historical LLM `market_context` was never
persisted: it lives only in a single overwriting Redis key
`trading:{asset}:market_context` (24h TTL); no ClickHouse table; LLM
cron scripts emit Telegram only. Zero context history exists for
2025-07→2026-04 — spec §4(b) "replay logged context" cannot be done.

**Instead: ceiling bracket** (`scripts/bracket_llm_bias_ceiling.py`) —
force the mask per run over the full range and measure the *maximum*
any directional-bias layer could add. A perfect look-ahead ORACLE mask
is the unreachable upper bound.

| Config | Mode | Sharpe | PF | Trades | Ret | Verdict |
|---|---|---|---|---|---|---|
| default | FLAT | −6.85 | 0.28 | 14 | −37.7% | catastrophic |
| default | ORACLE | 13.25 | inf | **4** | +4.6% | **INSUFFICIENT-TRADES** |
| rescoped (overfit) | FLAT | 5.54 | 2.42 | 182 | +185% | comfortable¹ |
| rescoped (overfit) | ORACLE | 8.42 | 7.79 | 116 | +283% | comfortable¹ |

¹ `rescoped.yaml` is the single knife-edge config the **re-scoped gate
already FAILED** (median valid trial −2.07; 1/40 non-catastrophic). Its
"comfortable" numbers are overfitting artifacts.

**Decision: NO-GO on investing weeks in live LLM-context collection.**
Rationale:
- On any *robust* parameterization the floor has no edge (re-scoped gate
  FAIL) and at sensible/default params the ensemble barely trades →
  even a *perfect* mask is economically negligible (4 trades, +4.6%/10mo).
  A directional mask only ever *subtracts* trades; it cannot manufacture
  an edge from a floor that lacks one.
- The only config where the bracket "looks good" is the known
  non-generalizing curve-fit, and there **FLAT is already comfortable
  without any bias** — so the bias layer is not what carries the result.
- **Bracket ⊥ gate**: a bracket is only decision-meaningful on a config
  that PASSES the re-scoped gate. None does.

**Real bottleneck:** the indicator ensemble has no robust standalone
edge — not the missing LLM bias. Pursue that (per-family scorer params,
different indicator set, or rethink the strategy) *before* any LLM-bias
data-collection investment. `config/strategies/futures/llm_directed_
indicator.yaml` remains `enabled: false`, no tuned params applied.

---

## Per-family-params decisive probe (2026-05-17) — lever **DEAD**

Spike: exposed 3 highest-leverage scorer-shape knobs (`mom_rsi_pivot`,
`trend_spread_saturation`, `trend_adx_full`) on `LLMDirectedIndicatorConfig`
+ 2 scorers + optimizer search space (backward-compatible; defaults ==
old constants; all 35 scorer/entry unit tests green). Re-scoped-gate run
(70 trials, holdout 2026-02-01, min-trades 50; now 13 dims).

| Re-scoped gate | Prior 10-dim | Probe 13-dim (+3 family knobs) |
|---|---|---|
| (a) median valid TRAIN Sharpe / PF | −2.07 / 0.78 | **−5.36 / 0.50** |
| (b) robust basin | 12.5% (5/40) | **0.0% (0/36)** |
| best-train cfg TRAIN Sharpe | +2.14 | **−0.25** |
| verdict | FAIL | **FAIL (worse)** |

Adding scorer-shape dimensions **collapsed the robust basin to zero** and
worsened the median. Confirms the scope prediction exactly: mapping/
normalization knobs add overfit surface, not information — Optuna fits
the train window's noise harder, degrading the whole distribution.

**Lever DEAD. Do NOT do the full ~12-knob build.** The spike code is
retained as reproducible negative evidence only; the new params are inert
by default and must NOT be tuned/activated.

### Synthesis — three independent lines converge

1. Replay: impossible (LLM context never persisted).
2. Ceiling bracket: a *perfect* look-ahead mask can't rescue the floor at
   robust params (4 trades / +4.6% per 10mo); only the overfit config
   "looks good".
3. Per-family probe: adding scorer tuning makes robustness *worse*
   (basin 12.5% → 0%).

**Conclusion:** `llm_directed_indicator`'s indicator ensemble has **no
robust standalone edge** on KOSPI200 1-min futures, and neither bias-
masking nor scorer-shape tuning fixes that — the bottleneck is
informational (the chosen indicators/timeframe lack a robust
generalizable directional signal for this instrument). Honest remaining
options: (a) *different information* (different indicators / multi-
timeframe / microstructure features — IndicatorEngine work, still
speculative) or (b) **accept the archetype is not viable here** and
formalize "do not pursue activation" (mirrors the RL_mppo arc). The
strategy already sits `enabled: false`; no tuned params ever applied.

---

## williams_r_15m — robust §6 gate (2026-05-19): FAIL (terminal)

`>>> RE-SCOPED GATE: FAIL (a=False b=False c=False | median_sharpe=nan basin=0.0% n_valid=0)`

Genuine-15m williams_r (timeframe_minutes:15, momentum_15m + mtf_base_15m), 70
Optuna trials on `101S6000`, holdout 2026-02-01, min-trades 50. **Zero** valid
(non-sentinel) trials — strictly worse than llm_directed_indicator (basin 12.5%).
best train value -10.0 (min-trades sentinel); selected-cfg OOS Sharpe -15.22 /
PF 0.00 / MDD 56.73% / ret -52.79% / 6 trades. Terminal per spec §8;
`williams_r_15m.yaml` stays `enabled:false`. The price-indicator timeframe axis
on the williams_r family is exhausted for KOSPI200 futures → spec
`docs/superpowers/specs/2026-05-19-futures-rlmppo-replacement-indicator-research-design.md`
§9 trigger to Approach ③ (microstructure / cross-asset, new spec). Tool:
`scripts/gate_futures_strategy.py` (shared.backtest.robust_gate). Full report:
`reports/optuna/WILLIAMS_R_15M_GATE.md`.

---

## bb_reversion_15m × RegimeGate — head-to-head (2026-05-21): BLOCKED (data-infrastructure)

T7 head-to-head NOT executed. The gate's data sources can't supply meaningful
inputs over the test window: `kospi.vol_forecasts` is empty for 2026-02-01..04-24
(TTL eviction); the historical HAR-RV recompute (`scripts/forecasting/recompute_har_rv_historical.py`)
cannot fit because the source `kospi.kospi200f_1m` minute-bar table has chronic
outlier corruption (23/152 days > 5× median daily-RV; max ≈ 161× median →
implied annualized vol ≈ 1258%, physically impossible). `kospi.event_scores`
has zero rows for all time. **Approach ③ P1 cannot be decided until the
`kospi200f_1m` data quality is investigated** — chiefly Aug 5, Sep 25/30,
Oct 10/27/30, Nov 13/14/21 in 2025. Full report:
`reports/optuna/BB_REVERSION_15M_REGIME_GATE.md`. P0+P1 infrastructure
(audit, recompute, RegimeGate, engine hook, gate runner, configs) is built
and tested (152 unit tests pass) and remains ready to use once the data
layer is repaired.

---

## bb_reversion_15m × RegimeGate — head-to-head (2026-05-22): FAIL (Δ=0.000; degenerate regime labels)

`>>> HEAD-TO-HEAD: FAIL (Δsharpe=0.000 vs δ=0.5 | gated_rescoped_pass=True)`

T7 re-run via the Path A pivot (A01603-only CSV; HAR-RV fits cleanly
R²_in=0.255 / R²_oos=0.115). 70+70 trials, 0 failures, baseline rescoped
gate PASS (median 7.14, basin 100%, n_valid=48). Baseline OOS Sharpe
11.76 — strong; gated OOS bit-for-bit identical → Δ=0.000.

Root cause is upstream-of-gate, in `VolatilityForecaster.forecast()`:
`self._latest_components` is frozen at `fit()` time and reused by every
subsequent `forecast(asof, ...)` call → all 1,887 OOS regime_percentile
labels = 34.03 exactly (constant). No threshold can make the gate fire
meaningfully on a constant input. The gate's design is therefore NOT
honestly evaluated by this run; a recompute-rolling-components fix is
required before a real head-to-head verdict is possible. Full report:
`reports/optuna/BB_REVERSION_15M_REGIME_GATE.md`. P0+P1+Path-A
infrastructure (audit, recompute, RegimeGate, engine hook, gate runner,
configs, clean-CSV builder) is built and tested; only `VolatilityForecaster`'s
rolling-components semantics for one-shot historical replay are missing.

---

## bb_reversion_15m × RegimeGate — head-to-head (2026-05-22 edition 3): PASS (Δ=+3.26)

`>>> HEAD-TO-HEAD: PASS (Δsharpe=3.260 vs δ=0.5 | gated_rescoped_pass=True)`

Third edition (BLOCKED → FAIL Δ=0 → PASS Δ=+3.26). T11 rolling-components
Locus 2 fix + T12 threshold tighten 80→60 unlocked the verdict.

Baseline OOS Sharpe 11.76 → Gated OOS Sharpe 15.02 (Δ=+3.26, well above δ=0.5).
MDD identical (13.50%). Both arms' rescoped §6 gates PASS (baseline median
7.14, basin 100%). 140 trials, 0 failures. Recompute now produces 19 distinct
regime_percentile values (vs constant 34.03 yesterday); 16.9% of OOS bars
above the tightened threshold → gate fires often enough to materially affect
the strategy. Spec §10 P2-③ trigger fires (apply to Setup A/C, new spec).
Caveats: ~30-day OOS is short; threshold tightened after seeing label
distribution; gated study's best_params not separately logged; forecast_pct
calibration looks ~3× too high (separate concern, doesn't affect this gate).
Full report: `reports/optuna/BB_REVERSION_15M_REGIME_GATE.md` (edition 3).
