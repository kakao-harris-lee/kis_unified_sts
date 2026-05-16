# LLM-Directed Indicator Strategy (Futures) — Design

**Date**: 2026-05-16
**Status**: Design (approved) → implementation plan pending
**Context**: RL_mppo deprecated (master plan v4.11). Futures needs an
indicator-based primary strategy. Currently only `williams_r_15m` exists
(enabled=false, unprofitable at defaults). This spec designs a single
composite strategy where an LLM provides periodic directional bias and a
fast multi-indicator suite executes entry/exit timing within that bias —
succeeding RL_mppo's hierarchical (high-level direction / low-level
execution) role.

Related: `docs/plans/2026-05-03-llm-primary-rl-minimization.md` v4.11,
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
  infrastructure. The Sharpe gate is on this floor. Live LLM bias only
  *removes* wrong-direction trades (an added filter), so passing the
  indicators-only floor is a reasonable live safety floor.
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
- Optuna over: family weights + entry_threshold + bias_confidence_min +
  per-family params.
- Costs: `futures_contract_spec` (1 tick slippage, ~0.3 bps) — same as
  the backtest engine / counterfactual.
- **Sharpe gate (proposed)**: net-of-cost **Sharpe > 1.0 AND PF > 1.2
  AND MDD reasonable** as the pass floor (report williams_r_15m Sharpe
  -5.81 and deprecated RL_mppo eval Sharpe ~3.19 as reference lines).
  **Operator sets the final bar.**

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
