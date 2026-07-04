# Gate B (ADX) — Regime-Detector Canonical-Wilder Characterization

- Date: 2026-07-04
- Owner: regime-gate-analyst
- Scope: `shared/regime/adaptive_detector.py::AdaptiveRegimeDetector._calc_adx`
  (candidate delegates to canonical `shared.indicators.reference.ADXCalculator`).
- Environment: worktrees `kis_wt/gate-b-adx` (candidate, `044ef629`) vs
  `kis_wt/baseline-main` (`7ed66a42`). Shared `data/market` Parquet store, project
  `.venv`. Paper-only R&D gate — **no live trading impact assessed as long as the
  detector stays opt-in** (see §6).
- **VERDICT: PASS — merge the canonical calc, KEEP thresholds `25/20`. No config
  diff required.** (Details + why NOT "pass-with-retune" in §7.)

---

## 0. TL;DR

| Question | Finding |
|---|---|
| Is the ADX shift a clean ~2× up? | **No.** The `15.87 → 31.63` figure is a single synthetic-fixture artifact. On broad real data the canonical ADX is on average **LOWER** than the old single-bar DX (median paired ratio ≈ **0.77**). |
| Does the change over-classify "strong trend"? | **No — the opposite.** Trend-label share is flat-to-lower (stock-daily 58.3%→52.8%; futures-minute +0.9pp). The feared "everything reads strong-trend" does not occur. |
| Do thresholds need retuning? | **No.** A full (strong,weak) grid sweep on the candidate ADX cannot recover baseline labels (best gain ~1pp); `25/20` are the textbook Wilder lines and fit the canonical distribution. |
| Does the change degrade EOD-proxy PnL? | **No.** Head-to-head gate ON/OFF is neutral-to-slightly-better for the candidate; retuned thresholds are indistinguishable. |
| Live blast radius today | **Zero** — `regime_detection_mode` defaults `"simple"`, `backtest.regime_detection_enabled` defaults `False`; no shipped config enables either. Opt-in only. |

---

## 1. What actually changed

The only non-test diff (verified `git diff 7ed66a42 044ef629`) is `_calc_adx`.
Classification logic (`_classify_regime`) is **byte-identical** between worktrees,
so every per-bar input to the classifier is identical **except `adx`**. This
isolates the entire label shift to the ADX calc.

- **Baseline `_calc_adx`** returns a single **last-bar DX**: `np.maximum(H−Hp,0)` /
  `np.maximum(Lp−L,0)` (never zeroes the smaller move → directional-movement rule
  missing), **simple** rolling-mean DI smoothing, and **no** final DX→ADX Wilder
  smoothing. It is "ADX" in name only.
- **Candidate `_calc_adx`** delegates to `ADXCalculator.calculate_last` — textbook
  Wilder DMI + DX + final Wilder smoothing of DX → ADX.

Consequence: the old value is an **instantaneous, unsmoothed** oscillator (0–100,
fat-tailed); the new value is a **smoothed** trend-strength index (lower mean,
compressed tail). This shape difference — not a scale multiplier — drives
everything below.

### The "~2× (15.87 → 31.63)" claim is a single-sample artifact

`tests/unit/indicators/test_reference.py` builds one deterministic synthetic
series (`volume = 2000 + 900·|sin(i/2.5)| + 15·i`, a smooth trending sinusoid). On
that **one** series' last bar: old DX `= 15.873272`, canonical ADX `= 31.634448`.
That is a momentary last-bar DX pullback inside a strong smoothed trend — it does
**not** generalize to a distribution. Measured over tens of thousands of real
bars, the mean relationship **reverses** (§2). The handoff's premise ("scale
roughly doubles → everything reads strong trend") is therefore **refuted on real
data**.

---

## 2. Deliverable 1 — Baseline vs candidate ADX distribution (real data)

Method: run the **real** `AdaptiveRegimeDetector.detect()` bar-by-bar with a
rolling **100-bar** window (matches runtime `deque(maxlen=100)` in the backtest
adapter and `get_recent_candles(limit=100)` in the orchestrator), config loaded
from `ml/regime_adaptive.yaml` via `from_yaml_dict` (so `strong=25, weak=20,
atr_high=0.02, atr_low=0.005, min_bars=60`). Harness run once per worktree;
per-bar `adx` extracted from `signal.indicators`.

| Dataset | bars | ADX mean (base→cand) | median | p75 | p90 | max | mean ratio | **median paired ratio** |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| **Stock daily** (29 liquid, full hist) | 18,992 | **33.22 → 24.65** | 30.16→22.35 | 48.76→30.41 | 65.29→39.40 | 100.0→68.95 | 0.742 | **0.766** |
| **Futures minute** (101S6000, Dec25–Apr26) | 38,122 | **33.03 → 25.12** | 28.92→22.07 | 48.48→31.16 | 67.60→41.80 | 100.0→90.14 | 0.761 | **0.783** |
| **Stock minute** (15 liquid, May–Jun26) | 172,834 | **34.54 → 25.51** | 29.41→23.65 | 53.82→33.69 | 79.31→45.63 | 100.0→100.0 | 0.738 | **0.711** |

All three datasets agree: **median paired ratio 0.71–0.78 — the canonical ADX is
~25% *lower* on average**, not ~2× higher.

Findings:
- The canonical (candidate) ADX is **lower on average** and has a **much thinner
  tail** (p90 ~40 vs ~66; max 69–90 vs pinned 100) — exactly what Wilder smoothing
  does to an unsmoothed DX. **Ratio ≈ 0.76, not ~2.0.**
- The per-bar *mean* ratio is meaningless (base DX → 0 on flat bars blows up the
  quotient; futures-minute mean ratio printed as ~5.7e10). The robust statistic is
  the **median paired ratio ≈ 0.77** and the quantile table above.
- Port validation: a vectorized re-implementation of `_classify_regime` reproduces
  the detector's own labels at **100.00%** for both arms — the classifier port
  used for the sweep (§4) is exact.

---

## 3. Deliverable 2 — Regime label distribution shift (current thresholds 25/20)

Labels: TB=TRENDING_BULL, TBr=TRENDING_BEAR, VS=VOLATILE_SIDEWAYS,
CS=CALM_SIDEWAYS, MR=MEAN_REVERTING. Trend share = TB+TBr.

**Stock daily** (18,992 bars):

| arm | TB | TBr | VS | CS | MR | **trend share** |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 34.8% | 23.5% | 18.7% | 19.7% | 3.3% | **58.3%** |
| candidate | 36.3% | 16.5% | 28.1% | 17.4% | 1.7% | **52.8%** |
| Δ | +1.5 | **−7.0** | **+9.4** | −2.3 | −1.6 | **−5.5pp** |

L1 divergence (Σ|Δ|) = **21.7pp**; per-bar agreement = **70.3%**.

**Futures minute** (38,122 bars):

| arm | TB | TBr | VS | CS | MR | **trend share** |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 2.8% | 2.6% | 1.5% | 91.5% | 1.6% | **5.4%** |
| candidate | 3.2% | 3.1% | 1.4% | 90.5% | 1.8% | **6.3%** |
| Δ | +0.4 | +0.5 | −0.1 | −1.0 | +0.2 | **+0.9pp** |

L1 divergence = **2.3pp**; per-bar agreement = **96.6%**.

**Stock minute** (172,834 bars):

| arm | TB | TBr | VS | CS | MR | **trend share** |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 5.3% | 4.9% | 0.0% | 88.4% | 1.3% | **10.2%** |
| candidate | 6.2% | 5.5% | 0.0% | 86.8% | 1.5% | **11.7%** |
| Δ | +0.9 | +0.6 | 0.0 | −1.6 | +0.2 | **+1.5pp** |

L1 divergence = **3.3pp**; per-bar agreement = **95.7%**. (Same story as futures
minute: the volatility branch dominates the 1-minute path, ADX barely
participates, change nearly inert.)

Interpretation:
- **Direction of the shift refutes the danger.** The feared failure mode
  ("over-classify strong trend") does **not** happen. On daily, trend share
  *falls* (−5.5pp); on futures-minute it barely moves (+0.9pp).
- **Mechanism (daily):** the old DX runs hot → more bars clear `adx>25` → more
  ADX-driven trend votes AND stronger trend reinforcement in ties. The smoother,
  lower canonical ADX cedes those ties to the volatility branch
  (`atr_ratio>0.02 → VOLATILE_SIDEWAYS`), so VS gains +9.4pp and TBr loses −7.0pp.
- **Mechanism (futures-minute):** 1-minute `atr_ratio` is almost always `<0.005`,
  so the **volatility branch dominates** and pins ~91% CALM_SIDEWAYS regardless of
  ADX. The ADX metric barely participates → the change is nearly inert on the
  actual live futures timeframe.

---

## 4. Deliverable 3 — Threshold retuning

Objective: find `(adx_strong_trend, adx_weak_trend)` on the **candidate** ADX that
best restores the **baseline label distribution / intent**. Method: exhaustive
grid `strong ∈ [26,60]`, `weak ∈ [15, strong)` step 0.5, re-running the exact
classifier port on candidate metrics; score = maximize per-bar agreement with
baseline, tie-break minimize distribution-L1.

| Dataset | best (strong/weak) | agreement (was @25/20) | L1 (was) | retuned trend share (base) |
|---|---|---|---|---|
| Stock daily | 26.0 / 25.0 | 71.6% (70.3%) | 21.9pp (21.7pp) | 50.3% (58.3%) |
| Futures minute | 26.0 / 19.5 | 96.7% (96.6%) | 2.5pp (2.3pp) | 6.4% (5.4%) |
| Stock minute | 58.0 / 16.5 | 95.9% (95.7%) | 3.4pp (3.3pp) | 11.3% (10.2%) |

**Retuning is ineffective and unnecessary:**
- The best grid point improves agreement by only **~1pp** and produces
  **degenerate** near-collapsed bands (e.g. `26/25`). There is **no** ADX
  threshold that recovers the baseline daily distribution, because the divergence
  is a **shape** change (smoothing removes DX's fat tail and reshuffles the
  classifier's tie-breaks), not a linear **scale** shift a threshold can undo.
- A "scale-by-ratio" reference (`strong=19/weak=15`, i.e. `25·0.76`) makes daily
  **worse** (L1 25.0pp, trend share overshoots to 66.5%) — confirming there is no
  clean rescaling.
- Independently of the buggy baseline, `25/20` are the **textbook Wilder** strong/
  weak lines, and the canonical ADX distribution (median ~22, p75 ~30) sits
  sensibly around them. Keeping `25/20` is the principled choice, and is *more*
  correct than before (the old thresholds were never re-derived for the hot DX).

**Recommendation: no change.** `adx_period=14`, `adx_strong_trend=25`,
`adx_weak_trend=20`, `very_strong_trend=40` all stay. No `regime_adaptive.yaml`
edit is applied in the candidate worktree.

---

## 5. Deliverable 4 — Head-to-head + counterfactual EOD-proxy PnL

Strategy-agnostic regime-gate methodology. Signal = generic mean-reversion proxy
(per-symbol 20-bar z-score of close; `z ≤ −1` → long, `z ≥ +1` → short,
long/short symmetric). EOD-proxy return = signed return from entry close to the
**session-end** close (minute) / next-bar close (daily). **Gate ON** = take the
signal only when regime ∈ {VS, CS, MR} (range-favorable); **Gate OFF** = take all
signals (the counterfactual "no gate"). Δ(on−off) > 0 means the regime filter is
removing losing MR entries. The metric of interest for Gate B is the **cross-arm
differential** (baseline vs candidate vs retuned), which isolates the ADX effect.

**Stock daily** (avg = mean signed EOD-proxy % per trade):

| arm | gateOFF n / avg | gateON n / avg | blocked n / avg | Δ(on−off) |
|---|---|---|---|---|
| baseline | 9514 / +0.0442% | 3051 / +0.0095% | 6463 / +0.0606% | −0.0348% |
| candidate 25/20 | 9514 / +0.0442% | 4132 / +0.0406% | 5382 / +0.0471% | −0.0037% |
| candidate retuned 26/25 | 9514 / +0.0442% | 4340 / +0.0394% | 5174 / +0.0483% | −0.0048% |

**Futures minute:**

| arm | gateOFF n / avg | gateON n / avg | blocked n / avg | Δ(on−off) |
|---|---|---|---|---|
| baseline | 20380 / +0.0768% | 19221 / +0.0682% | 1159 / +0.2189% | −0.0086% |
| candidate 25/20 | 20380 / +0.0768% | 19115 / +0.0687% | 1265 / +0.1989% | −0.0081% |
| candidate retuned 26/20 | 20380 / +0.0768% | 19102 / +0.0705% | 1278 / +0.1705% | −0.0063% |

**Stock minute** (May–Jun 2026 was a MR-unfriendly / declining window for these
names → the proxy is net-negative, so the range-gate genuinely *adds* value here —
a useful stress case):

| arm | gateOFF n / avg | gateON n / avg | blocked n / avg | Δ(on−off) |
|---|---|---|---|---|
| baseline | 78955 / −0.0346% | 68361 / −0.0232% | 10594 / −0.1077% | **+0.0113%** |
| candidate 25/20 | 78955 / −0.0346% | 68173 / −0.0192% | 10782 / −0.1315% | **+0.0153%** |
| candidate retuned 58/16 | 78955 / −0.0346% | 68229 / −0.0225% | 10726 / −0.1112% | +0.0120% |

Here the gate's value (Δ on−off > 0) is **largest for the candidate** (+0.0153% vs
baseline +0.0113%): the canonical labels block a *cleaner* set of losers
(blocked avg −0.13% vs −0.11%). The change **improves** the gate on this dataset.

Findings:
- **No degradation from the candidate.** On stock daily the candidate's gate keeps
  *more* profitable MR entries (gateON avg +0.041% vs baseline +0.010%; blocks
  5,382 vs 6,463) → the canonical labels are **less trigger-happy at blocking**
  and the gated strategy is *better*, not worse. On futures minute all arms sit
  within noise (Δ on−off −0.0086% vs −0.0081%).
- **Retuned ≈ candidate.** The optional retune moves nothing economically
  meaningful — further evidence a threshold change is not warranted.
- Note: Δ(on−off) is mildly negative for this particular MR proxy (blocking
  trend-regime dips removes some winners). That is a property of the *proxy*, not
  of the ADX change; the Gate-B signal is the **cross-arm** comparison, which is
  neutral-to-favorable for the candidate in every cell.

---

## 6. Scope, wiring, and current live blast radius

- **Backtest path** (`shared/backtest/adapter.py`, `daily_adapter.py`) gated by
  `backtest.regime_detection_enabled` — **grep of `config/` returns nothing** →
  `False` everywhere → dormant.
- **Live orchestrator path** (`services/trading/orchestrator.py:263`) gated by
  `regime_detection_mode == "adaptive"` — default is **`"simple"`**
  (`runtime_config.py:188`); no shipped config sets `adaptive` → dormant.
- When enabled, the orchestrator regime uses **minute** bars
  (`_get_recent_bars_for_regime` → `get_recent_candles(limit=100)`), where the
  shift is small. The single live behavioral hook is the **stock long-entry block
  on "BEAR" regime** (`orchestrator.py:4996`); on minute bars TRENDING_BEAR shifts
  by <1pp, and futures skip the BEAR block entirely (bidirectional). So even fully
  enabled, the live effect is marginal.
- **Out of scope (untouched):** the duplicate `_calc_adx` at
  `services/trading/indicator_engine.py:1694` (strategy-level `adx` indicator key).
  The parity tests confirm that **runtime** `_calc_adx` is *already* canonical
  Wilder (31.72 on the fixture); after this change the detector converges to it
  (31.63), so runtime and detector are now consistent. No change needed there.

---

## 7. Deliverable 5 — Verdict

**PASS.** Merge the canonical-Wilder delegation. **Keep** thresholds at
`adx_strong_trend=25`, `adx_weak_trend=20`, `adx_period=14`.

Config diff to apply: **none.** (`config/ml/regime_adaptive.yaml` unchanged.)

Why not PASS-WITH-RETUNE:
1. The retune premise (ADX ~2× up → raise thresholds) is **empirically false** —
   canonical ADX is *lower* on real data (§2).
2. No ADX threshold recovers the baseline label distribution; the divergence is a
   shape change, and the best grid point is a degenerate ~1pp improvement (§4).
3. `25/20` are the correct Wilder lines for the canonical ADX and fit its
   distribution.
4. EOD-proxy PnL is neutral-to-better for the candidate; retuned ≈ candidate (§5).

Because the retune would be at best cosmetic and at worst harmful (any
threshold that raises daily trend-share back toward 58% pushes the futures path
and violates textbook semantics), the gate ships the calc **as-is with unchanged
thresholds**.

Residual watch items (non-blocking):
- If a future config sets `regime_detection_mode: adaptive` for **stocks**, re-run
  the stock-minute head-to-head (the BEAR-block hook is the only live lever).
- The daily backtest label mix genuinely changes (L1 21.7pp); any *future*
  strategy that turns on `backtest.regime_detection_enabled` should be
  (re-)optimized against the canonical labels, not the old ones.

---

## 8. Reproduction

```
# harness (run once per worktree; PYTHONPATH selects baseline vs candidate calc)
cd <worktree> && PYTHONPATH=<worktree> /home/deploy/project/kis_unified_sts/.venv/bin/python \
  scratchpad/harness_adx.py --asset stock --timeframe daily --symbols <29 liquid> --out <out.parquet>
# analysis (ports classifier, sweeps thresholds, EOD-proxy PnL)
PYTHONPATH=<candidate> python scratchpad/analyze.py --base <base.parquet> --cand <cand.parquet> \
  --timeframe daily --name STOCK_DAILY
```

Scripts: `scratchpad/harness_adx.py`, `scratchpad/analyze.py` (session scratchpad).
Datasets: 29 liquid KOSPI symbols (deep daily history); 101S6000 futures minute
Dec 2025–Apr 2026 (project-memory "reliable" window); 15 liquid stocks minute
May–Jun 2026. Symbols/ranges chosen for actual data coverage; no symbols dropped
in the curated runs.

### Stock minute (corroborating, live-affecting stock timeframe)

Completed: 15 liquid stocks, May–Jun 2026, 172,834 bars. Fully corroborates the
daily + futures results — ADX ratio 0.71 (canonical lower), label L1 3.3pp /
95.7% agreement (near-inert, volatility branch dominates), no effective retune
(best 58/16.5 = +0.2pp), and the EOD-proxy gate is **improved** by the candidate
(Δ on−off +0.0153% vs baseline +0.0113%). Tables in §2/§3/§5.

Data-hygiene caveat (non-material): the stock-minute set contains **2** duplicate
`(symbol, ts)` echo bars (0.0012%), which cross-join to 4 extra merge rows and a
few spurious `mfi` mismatches in the alignment check. Stock-daily and
futures-minute had **zero** duplicate keys (exact `max|Δ|=0` alignment). The 2-row
artifact has no bearing on any distributional or PnL conclusion.
