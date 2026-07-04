# LLM-Directed Indicator Strategy (Futures) — Design

> ## ⛔ DEPRECATED 2026-05-17 — DO NOT ACTIVATE
> The strategy was built and evaluated. It has **no robust standalone
> edge** on KOSPI200 1-min futures and **fails the re-scoped §6 gate**.
> Activation is not pursued. `enabled: false` permanently; no tuned
> params were ever applied. Rationale + evidence: **§8** below and
> `reports/optuna/FINDINGS.md`. Code/tests retained for reference (the
> negative result is reproducible); this is NOT an activation path.

**Date**: 2026-05-16  ·  **Deprecated**: 2026-05-17
**Status**: ⛔ DEPRECATED (built, evaluated, no robust edge — see §8)
**Context**: RL_mppo deprecated (master plan v4.11). Futures needs an
indicator-based primary strategy. Currently only `williams_r_15m` exists
(enabled=false, unprofitable at defaults). This spec designs a single
composite strategy where an LLM provides periodic directional bias and a
fast multi-indicator suite executes entry/exit timing within that bias —
succeeding RL_mppo's hierarchical (high-level direction / low-level
execution) role.

Related: `docs/plans/archive/2026-05-03-llm-primary-rl-minimization.md` v4.11,
`2026-05-15-williams-r-futures-design.md`, PRs #249–#258 (this session's
forecasting/cache/Setup-A/C wiring fixes inform the failure-mode design).

---

## 1. Goal & Requirements

Replace RL_mppo's primary futures role with **one composite strategy**:

- **LLM-driven direction**: the LLM emits a periodic directional bias
  (`LONG_BIAS | SHORT_BIAS | FLAT`). Not per-tick (cost/latency) — it
  reuses the existing periodic LLM `market_context`.
- **Fast indicator execution**: a suite across 4 families generates the
  real-time (1-min) entry trigger and exit timing *within* the LLM bias —
  "the market's nimble movements" the operator asked for.
- **Single primary strategy** registered like RL_mppo; Setup A/C remain
  as sparse specialists alongside.
- Config-driven, registry pattern, futures data policy (101S6000
  train/backtest, A05xxx live), no hardcoding.
- Rollout: backtest Sharpe gate → paper-primary directly (no shadow
  stage — operator's accepted tradeoff).

Non-goals: live (real-money) activation (requires Phase 5 gates);
multi-contract sizing; RL retraining.

---

## 2. Architecture

```
LLM market_context (periodic publish, EXISTING)     Indicator engine (1-min, EXISTING)
  regime / overall_signal / confidence                momentum_5m / EMA·VWAP·TRIX·ADX
        │                                              / ATR·BB-width·HAR-RV / rvol·vel·accel
        ▼                                                        │
  [bias mapper]                                                  ▼
  overall_signal+confidence → {LONG_BIAS|SHORT_BIAS|FLAT}   [family scorers]
        │                                   3 directional → score ∈ [-1,+1]
        │                                   1 volatility  → regime mag ∈ [0,1]
        └──────────────────┬──────────────────────────────────────┘
                           ▼
                 [mask apply + weighted ensemble]
   LONG_BIAS → block short / SHORT_BIAS → block long / FLAT → both allowed
   ensemble = Σ(wᵢ·scoreᵢ) over 3 directional; vol regime raises threshold
   within allowed dir & |ensemble| ≥ eff_threshold → enter (sign=direction)
                           ▼
                 [composite exit] atr_dynamic|chandelier trail
                 + momentum_decay + HAR-RV-widened hard stop + EOD 15:15
```

**Load-bearing design decisions (informed by this session's 0-signal saga):**

1. **LLM input is already wired.** `strategy_manager.py` injects
   `context.market_context` (LLM `MarketContext`) on every entry cycle.
   Unlike Setup A's `macro_overnight` / Setup C's `scheduled_events`
   (which the orchestrator never injected — root cause of their 0
   signals), this strategy's LLM input needs **no new orchestrator
   wiring**. This eliminates the wiring-gap failure class at the source.
2. **LLM absent / low-confidence → FLAT, never no-trade.** If
   `market_context` is None, stale (older than a configurable TTL), or
   `confidence < bias_confidence_min`, the mask is FLAT (both directions
   allowed; indicators run standalone). The mask only *blocks* one
   direction when the LLM is *confident*. This deliberately avoids Setup
   A's `if ctx.macro_overnight is None: return None` structural-zero
   failure.
3. **The only hard gate is the directional mask** (and only under
   high-confidence LLM). All four indicator families vote softly within
   it — minimal structural-zero surface.
4. RL_mppo's hierarchical contract (high-level direction / low-level
   execution) is succeeded by LLM (high) + indicator ensemble (low).
   Setup A/C coexist as sparse specialists.

---

## 3. Components

| Component | Location | Single responsibility |
|---|---|---|
| `LLMDirectedIndicatorEntry` | `shared/strategy/entry/llm_directed_indicator.py` | Orchestrate: bias map → 4 scores → mask + weighted ensemble → Signal |
| `_map_llm_bias()` | same file (pure fn) | `market_context.overall_signal`+`confidence` → `LONG_BIAS\|SHORT_BIAS\|FLAT`; None/low-conf/stale → FLAT |
| 4 family scorers | `shared/strategy/signals/indicator_families.py` (new, DRY) | 3 directional `(indicators) → score ∈ [-1,+1]` + 1 volatility `(indicators) → regime magnitude ∈ [0,1]`; independently unit-testable |
| `LLMDirectedIndicatorExit` | `shared/strategy/exit/llm_directed_indicator_exit.py` | **Compose** existing exit primitives (do not reimplement) |
| `LLMDirectedIndicatorConfig` | same as entry (ConfigMixin) | family weights, entry_threshold, bias_confidence_min, per-family params, exit-composite params, `mask_mode: hard\|soft` |
| YAML | `config/strategies/futures/llm_directed_indicator.yaml` | `enabled: false` until backtest gate; all thresholds config-driven |
| Registry | `register_builtin_components()` | register entry + exit |

**4 family scorers (reuse existing engine outputs; minimal new compute).**
3 are *directional* (`→ [-1,+1]`, summed in the weighted ensemble); the
volatility family is a *non-directional regime magnitude* (`→ [0,1]`)
that modulates the ensemble threshold and exit width — it is never summed
into the directional ensemble:

- **Momentum-reversal** (directional): `momentum_5m` bundle (RSI,
  Williams %R, Stoch, MACD-hist) → overbought/oversold reversal score.
- **Trend/breakout** (directional): EMA, VWAP, TRIX, ADX, 15-min range →
  trend-alignment score.
- **Volume/microstructure** (directional): rvol, volume
  velocity/acceleration, VWAP deviation → nimble-flow score.
- **Volatility/regime** (modulator, non-directional): ATR, BB-width +
  **HAR-RV forecast** (`forecast:vol` Redis key, written by
  `forecast_publisher`) → regime magnitude that raises the effective
  entry threshold (high vol → more selective) and widens the exit stop.

**Dependency / degrade policy:**

- HAR-RV depends on the forecasting daemon (#249). Absent → volatility
  family weight 0, base ATR fallback for the exit. Never blocks entry.
- Any family input missing → that family contributes score 0 (not None,
  not block). Ensemble computes on available families.
- Isolation: each of the 4 scorers is a `(dict) → float` pure unit with
  its own tests; the entry strategy composes them.

---

## 4. Data Flow

**Entry (live/paper, 1-min cycle):**

1. Orchestrator entry loop builds `EntryContext{market_data, indicators
   (momentum_5m, ema, vwap, atr, bb, rvol, vel/accel — all existing),
   market_context (LLM, periodic)}` — existing path.
2. `strategy_manager` injects `context.market_context` (existing).
3. `LLMDirectedIndicatorEntry.generate()`:
   - ① `_map_llm_bias(market_context)` → MASK (None/low-conf/stale → FLAT)
   - ② HAR-RV: read `forecast:vol` Redis key (~60 s cache, mirrors the
     `read_latest_macro_snapshot` pattern; **no len()-based cache**)
   - ③ compute the 3 directional family scores + the volatility regime
     magnitude from `context.indicators`
   - ④ `ensemble = Σ wᵢ·scoreᵢ` over the **3 directional families**; the
     volatility regime magnitude raises the effective entry threshold
   - ⑤ apply MASK → allowed direction & `|ensemble| ≥ entry_threshold`
     → `direction = sign(ensemble)`
   - ⑥ emit `Signal(signal_direction, confidence = f(|ensemble|,
     llm_confidence), metadata={decision trace})`
4. `strategy_manager` aggregates → orchestrator paper order (existing).

**Exit (per-cycle, existing exit scan):** `LLMDirectedIndicatorExit`
instantiates sub-exits once (atr_dynamic|chandelier + momentum_decay) plus
a HAR-RV-widened hard stop + EOD 15:15; evaluates all per position and
fires the highest priority. Reuses existing `ExitContext`.

**Backtest (contract decision — approved):** the backtest engine replays
101S6000 bars; the 4 family scores are reconstructable from the seeded
indicator engine. There is **no live LLM in backtest**. Contract:

- **(a) FLAT-bias backtest** (the contract): mask is always FLAT
  (indicators-only, both directions). Measures the **conservative floor
  of the pure indicator suite's edge** — deterministic, zero LLM-replay
  infrastructure. The gate is on this floor. Live LLM bias only
  *removes* wrong-direction trades (an added filter), so passing the
  indicators-only floor was *assumed* to be a reasonable live safety
  floor. **⚠️ This assumption was empirically FALSIFIED on 2026-05-17 —
  see §6.1.** The floor loses money across ~92 % of its parameter space.
- (b) replay logged LLM `market_context` from ClickHouse — higher
  fidelity, documented as a **future upgrade** (depends on historical
  context persistence + alignment).
- (c) deterministic bias proxy — approximation risk; not chosen.

---

## 5. Error Handling (this session's failure modes designed out)

| Failure mode (origin) | Design response |
|---|---|
| LLM context absent/stale (Setup A `macro is None → return None`) | → **FLAT** (both dirs), not no-trade. TTL exceeded → FLAT |
| HAR-RV / `forecast:vol` absent (#249 forecasting dep) | volatility weight → 0, ATR fallback. No entry block. debug log |
| Indicator family input missing | that score = 0 contribution (not None / block). Ensemble continues |
| Cache staleness (#252) | engine already monotonic-counter-invalidated. New HAR-RV read uses a ~60 s cache only — **len()-based cache forbidden** |
| Adapter code contract (#257 williams_r `if not code`) | no hard-reject on empty code; require only `close > 0`, safe code default |
| Composite sub-exit raises | other sub-exits still evaluated. **hard-stop + EOD 15:15 are independent safety nets** the indicator/LLM path can never suppress (RL exit-safety invariant, CLAUDE.md) |
| Hot-path exception | bias mapper, HAR-RV read, 4 scorers all try/except → safe degrade (score 0 / FLAT); the entry loop never crashes |

**Observability (the debugging capability this session needed):** every
`generate()` logs a decision trace (`bias / per-family scores / ensemble /
threshold / mask outcome`) at INFO. The #256 monitor (orchestrator-log
Signal-cycle parser) + log funnel can then distinguish "0 signals (bug)"
from "no-setup day (correct)". `|ensemble| < threshold` no-entry is
**normal**, not an error — but visible in the trace.

Core principle: **the only hard gate is a high-confidence LLM directional
mask**; every other missing input / fault degrades to a *reduced* signal,
never to *zero* signals.

---

## 6. Testing & Validation

**Unit tests (isolation — each unit independently):**

- 4 family scorers: `(indicators) → [-1,+1]`, boundaries (missing → 0,
  overbought → negative, etc.) per family.
- `_map_llm_bias`: signal+confidence → LONG/SHORT/FLAT; None/low-conf/
  stale → FLAT.
- `entry.generate`: mask blocks counter-direction; FLAT allows both;
  threshold; degrade paths (LLM/family/HAR-RV absent); never-raise.
- `exit`: composite priority order; hard-stop/EOD independent safety
  nets; sub-exit exception isolation.
- config load + registry registration + **adapter code-injection
  regression** (guards the williams_r-class bug).

**Backtest gate (operator chose backtest → paper-primary, no shadow):**

- `data/kospi200f_1m_ch_101S6000.csv`, FLAT-bias contract
  (indicators-only floor).
- Optuna over: family weights + entry_threshold + per-family params.
  (`bias_confidence_min` is **excluded** — under the FLAT-bias backtest
  contract the mask is always FLAT, so it is provably a no-op in
  backtest. Tuning it wastes trials and distorts param-importance.)
- A **min-trades floor** on the optimization window is mandatory: with
  no floor, maximizing Sharpe "wins" by barely trading (e.g. 8 trades /
  7 months) — statistical noise, wildly unstable across windows.
- Costs: `futures_contract_spec` (1 tick slippage, ~0.3 bps) — same as
  the backtest engine / counterfactual.

- **Re-scoped gate (2026-05-17, operator-approved) — "robust
  non-catastrophic floor".** The original "best-trial Sharpe > 1.0 AND
  PF > 1.2" bar was **withdrawn**: it judged the *single best trial* by
  raw Sharpe, which an Optuna search will satisfy with a knife-edge
  curve-fit even when ~92 % of the parameter space loses money. The
  FLAT-bias path is a *safety floor*, not the alpha (the LLM directional
  bias is the alpha), so the bar is that the floor is **broadly
  non-catastrophic**, judged on the *distribution* of valid trials.
  PASS requires **all** of:
  - **(a)** the **median** valid trial (cleared the min-trades floor,
    not NaN/degenerate) is non-catastrophic on train:
    `Sharpe ≥ 0 AND PF ≥ 1.0`;
  - **(b)** a **broad basin**: `≥ 25 %` of valid trials clear (a)
    (kills single-lucky-trial acceptance);
  - **(c)** the selected config is non-catastrophic **out-of-sample**
    (held-out split): `Sharpe ≥ 0 AND PF ≥ 1.0 AND MDD ≤ 25 % AND
    return ≥ 0`.
  Reference lines: williams_r_15m Sharpe −5.81; deprecated RL_mppo eval
  Sharpe ~3.19. Thresholds are CLI-configurable; **operator sets the
  final bar**. Implemented in `scripts/optimize_llm_directed_indicator.py`
  (`_rescoped_gate`).

**Rollout:** `enabled: false` → backtest + Optuna → gate pass → flip
`enabled: true` paper-primary (Setup A/C coexist). No shadow stage.

**Validation observability:** the #256 monitor judges the next trading
week PASS (signals throughout) / FAIL (structural 0) → catches any
residual wiring/degrade defect immediately.

**Regression:** existing williams_r / orchestrator / Setup A/C / macro /
scheduled_events suites stay green (the strategy only adds; it does not
modify their paths).

**⚠️ Explicit residual risk (operator-accepted tradeoff):** skipping the
shadow PnL stage means the first real-money-equivalent evidence is
paper-primary itself. Passing the FLAT-bias backtest floor does not
guarantee LLM upside (it is only a conservative floor). The #256 monitor
+ weekly paper review are the sole post-hoc safety nets.

### 6.1 Empirical result (2026-05-17) — gate FAILED

Three Optuna runs on `101S6000` (84 + 66 + 67 trials), tool
`scripts/optimize_llm_directed_indicator.py`; full evidence in
`reports/optuna/FINDINGS.md`.

- No-floor runs exposed the low-trade-count Sharpe degeneracy (best:
  8 trades / 7 months). Min-trades floor added.
- **Re-scoped gate verdict: FAIL** (tool-printed, canonical run). With
  the floor: median valid trial train **Sharpe −2.07 / PF 0.78** →
  (a) FAIL; only **5/40 = 12.5 %** of valid trials are non-catastrophic
  → (b) FAIL (need ≥25 %). The selected config does pass OOS
  (8.68 / 3.49) — exactly the single-lucky-outlier the re-scoped gate is
  designed to reject. ~87 % of valid trials are money-losing on the
  floor. Verdict reproduced on two independent codebases
  (`runtime/main-current` median −2.25 / basin 7.9 %; `origin/main`
  median −2.07 / basin 12.5 %) — robust to codebase / trial count /
  seed-path.

**This empirically falsifies §4(a)'s assumption that "the
indicators-only floor is a reasonable live safety floor."** Without the
LLM bias the indicator suite is *actively unsafe*, not merely "not
alpha". Consequences for any future activation attempt:

1. Activation must **not** rely on the FLAT-bias path as a safety net.
   The LLM-absent degrade path should be re-examined — a true FLAT/
   no-trade fallback is safer than an indicator-driven one here.
2. The LLM-bias contribution must be evaluated **directly** (replay
   path (b), or a paper A/B), not inferred from the floor.
3. Structural levers before re-test: fix the ATR-in-backtest plumbing
   (`atr=0.0000` ⇒ exit is just the % stop, untested); rolling
   walk-forward (multi-window) for regime-stability; per-family scorer
   params (listed above, not yet exposed).

`config/strategies/futures/llm_directed_indicator.yaml` remains
`enabled: false` with **no tuned params applied**.

---

## 7. Evolution Paths (documented; phase 1 = Approach A only)

The operator asked for "various integration approaches reviewed". A is
implemented first; B and C are recorded with explicit trigger conditions.

**Path B — soft modulation (remove the hard mask).** Replace the
directional mask with continuous modulation:
`effective_score = ensemble × (1 + α·llm_confidence·dir_align)` — small
counter-direction trades allowed when the LLM is weakly confident.
*Trigger*: A's mask causes frequent 0-signal days in paper (#256
WARN/FAIL recurring) or the LLM bias proves over-conservative. *Benefit*:
near-elimination of structural-zero risk; continuous LLM influence.
*Cost*: more score-function parameters; re-Optuna. **Design hook**: ship
A with a `mask_mode: hard|soft` config switch (switch only — the soft
logic itself lands in phase B; YAGNI boundary).

**Path C — two-layer hierarchical (RL re-insertable).** LLM = high level
(15-min, direction + risk budget), indicator ensemble = low level (1-min
execution, risk-budget-driven sizing). Reuses the deprecated
`shared/ml/rl/hierarchical/` concepts + directional/risk_budget modes.
*Trigger*: multi-contract operation (currently 1-contract capped) or
re-evaluating RL as an alternative low-level agent. *Benefit*: same
hierarchical contract operators already know; a re-insertion slot for an
RL low-level. *Cost*: 15/1-min cadence coordination + the most
scaffolding → deferred until multi-contract.

**Evolution trigger summary:**

| Signal | → Path |
|---|---|
| Mask 0-signal excess (#256 FAIL recurring) / LLM over-conservative | B (soft) |
| Multi-contract transition / RL re-eval / risk-budget sizing needed | C (hierarchical) |
| A satisfies paper Sharpe | keep A |

---

## 8. Open Items for the Implementation Plan

- Exact per-family scorer formulas + normalization to [-1,+1].
- HAR-RV → effective-threshold modulation function shape.
- `confidence = f(|ensemble|, llm_confidence)` mapping.
- Composite-exit priority ordering vs the existing exit registry classes'
  own priorities.
- Optuna search space bounds + objective (Sharpe primary, PF/MDD
  constraints).
- Backtest harness wiring for the FLAT-bias contract (force mask=FLAT in
  backtest adapter path).

---

## 8. Deprecation (2026-05-17) — decision & rationale

**Decision:** `llm_directed_indicator` is **DEPRECATED**. It will not be
activated. `config/strategies/futures/llm_directed_indicator.yaml`
remains `enabled: false` permanently; no tuned parameters were ever
applied. Code, config, and tests are **retained** (not deleted) so the
negative result stays reproducible and as reference for any future
futures-signal work — mirroring the RL_mppo arc (deprecated 2026-05-15,
code retained for the retraining option).

**Why (three independent investigation lines converged):**

1. **Re-scoped §6 gate FAIL (§6.1).** The original "best-trial
   Sharpe>1.0/PF>1.2" bar was withdrawn (it rewards knife-edge
   curve-fits). Under the operator-approved *robust non-catastrophic*
   gate the FLAT-bias floor fails decisively: median valid trial
   Sharpe ≈ −2.07 / PF 0.78, only ~12.5 % of valid trials
   non-catastrophic. Reproduced on two independent codebases. The floor
   loses money across ~87 % of its parameter space — empirically
   falsifying §4(a)'s "reasonable live safety floor" assumption.
2. **LLM-bias ceiling bracket.** Historical LLM `market_context` was
   never persisted (overwriting 24h-TTL Redis key only) → spec §4(b)
   replay is impossible. The substitute ceiling test (force the mask;
   a perfect look-ahead ORACLE = the unreachable upper bound) shows even
   a *perfect* directional mask cannot rescue the floor at robust
   params (4 trades / +4.6 % per 10 mo); the only config where it
   "looks good" is the non-generalizing curve-fit, where FLAT is
   already comfortable *without* any bias.
3. **Per-family-params decisive probe.** Exposing scorer-shape knobs
   made robustness *worse* — basin 12.5 % → **0.0 %** (0/36 valid
   trials non-catastrophic), median Sharpe −2.07 → −5.36. Mapping/
   normalization knobs add overfit surface, not information.

**Root cause:** the bottleneck is *informational* — the chosen
indicator ensemble / 1-min timeframe does not contain a robust,
generalizable directional edge for KOSPI200 futures. Neither
LLM-bias masking nor parameter/shape tuning can manufacture an edge
that the base signal lacks.

**Operational status:**
- YAML `enabled: false` (permanent); registry registration retained.
- The strategy must NOT be set `enabled: true` without a *new* spec
  that addresses the informational bottleneck (different indicators /
  multi-timeframe / microstructure features) and re-clears the
  re-scoped §6 gate from scratch.
- Full evidence, tooling, and reproducible runs: PR #320 +
  `reports/optuna/FINDINGS.md`.

**If futures signal work resumes,** start from *different information*
(not re-tuning this ensemble) and gate any candidate on the re-scoped
robust-non-catastrophic bar (`scripts/optimize_llm_directed_indicator.py
::_rescoped_gate`), not raw best-trial Sharpe.
