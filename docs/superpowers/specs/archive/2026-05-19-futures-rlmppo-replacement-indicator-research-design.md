# Futures RL_mppo Replacement — Indicator Research Program (Design)

**Status:** Design — awaiting user review before plan
**Date:** 2026-05-19
**Author:** brainstorming session (operator: chihunlee)
**Supersedes nothing. Builds on:** `docs/superpowers/specs/2026-05-16-llm-directed-indicator-futures-design.md` (§8 deprecation), `docs/superpowers/specs/2026-05-15-williams-r-futures-design.md`, the bb_reversion_15m productionization (origin/main `cd0944d`, PR #328).

---

## 1. Goal

Find and validate a *trustworthy* futures entry/exit signal to replace the deprecated `rl_mppo` (and the deprecated `llm_directed_indicator`) — using LLM-directed entry plus market-responsive exit assistance — **without repeating the informational mistake that killed the prior archetype**. The deliverable of this spec's first phase is infrastructure + a decisive gate-based research harness, not a pre-chosen strategy.

## 2. Non-negotiable constraint (canonical)

`2026-05-16-llm-directed-indicator-futures-design.md` §8 (deprecation, 2026-05-17):

> "The strategy must NOT be set `enabled: true` without a *new* spec that addresses the **informational bottleneck** (different indicators / multi-timeframe / microstructure) and **re-clears the re-scoped §6 gate from scratch**. … If futures signal work resumes, start from *different information* (not re-tuning this ensemble) and gate any candidate on the re-scoped robust-non-catastrophic bar."

This document is that new spec. Root cause of the prior FAIL was **informational** (the RSI/Williams/MACD/EMA family on **1-min** KOSPI200 futures has no robust generalizable directional edge), proven on three independent lines (re-scoped gate FAIL, LLM-bias ceiling bracket, per-family-params probe). Re-tuning, hard-masking, and scorer-shape knobs are all ruled out.

Two facts make the problem tractable:

1. **Timeframe is a proven different-information axis for this instrument.** `bb_reversion_15m` cleared the re-scoped robust §6 gate at **15-min** (Sharpe 5.35 walk-forward) and is in paper this session, where the same family at 1-min failed. The closed-bar `mtf_base_<tf>` MTF contract built for it is reusable.
2. **"LLM-directed" cannot be honestly backtested today.** LLM `market_context` is never persisted (overwriting 24h-TTL Redis key only; research crons emit Telegram only). Spec §4(b) replay was *impossible* for the prior work. This is the highest-leverage blocker and it is fixable infrastructure, not curve-fitting.

## 3. Approaches reviewed

**① Different-information, gate-first phased program — SELECTED.** Phased, FAIL-fast; every candidate gated by the existing re-scoped robust bar from scratch. Highest upfront infra cost, slowest to a shippable strategy, but the only path that yields trustworthy results and obeys the canonical mandate.

**② williams_r-family 1-min ensemble + LLM hard-mask — REJECTED (anti-pattern).** Structurally identical to the deprecated `llm_directed_indicator` (same families, 1-min, hard-mask). FINDINGS already proved this fails on informational grounds. Documented here so it is not re-attempted; evidence: `reports/optuna/FINDINGS.md`, prior spec §6.1/§8.

**③ Microstructure / cross-asset pivot — DEFERRED (triggered later phase).** Genuinely new signal classes (tick-direction/flow imbalance, overnight S&P / USDKRW / cash-futures basis). Highest information potential but no futures orderbook plumbing exists, public depth is sparse, longest horizon. Recorded as Path-N with a trigger (§9), mirroring how the prior spec recorded its Paths B/C.

## 4. Architecture

A **research program**, not a single-strategy build: four phases P0 → P3, each an independently shippable, gate-validated unit. The program reuses existing assets and adds the minimum new surface.

```
P0  Infra (unblocks honest evaluation)
     └─ llm_market_context durable persistence (ClickHouse write-through)
        (ATR-in-backtest fix removed from P1 scope — see §12 correction 2)
            │
P1  Decisive research (cheap, FAIL-fast)
     ├─ generalize _rescoped_gate → any futures strategy (CLI)
     └─ run candidates through the robust gate:
        williams_r_15m (already scaffolded, never validated) + 2–3
        orthogonal-information candidates (15m timeframe axis)
            │  (only gate survivors proceed)
P2  LLM-directed entry on survivors
     └─ Setup A/C LLM-tuning/veto adapter pattern (NOT hard-mask);
        contribution judged by P0 replay + paper A/B, never the FLAT floor
            │
P3  Market-agility exit-assist on survivors
     └─ composite: ATR-dynamic trail + momentum_decay + volume-accel,
        validated only with the P0 ATR fix in place
```

**Reused:** `scripts/optimize_llm_directed_indicator.py::_rescoped_gate`; the `mtf_base_<tf>` closed-bar MTF contract (`shared/indicators/contracts.py`, `services/trading/indicator_engine.py`); the Setup A/C LLM-tuning/veto adapter (`shared/strategy/entry/setup_adapters.py`); `BacktestConfig.futures(10_000_000, point_value=50_000)`.

**Added:** one ClickHouse table + one publisher write-through + one reader; one ATR-plumbing fix; one generalized gate-runner CLI; per surviving candidate a config YAML (`enabled:false` until its own gate passes).

## 5. Components & boundaries (each testable in isolation)

| # | Component | Responsibility | Depends on |
|---|---|---|---|
| C1 | `llm_market_context` ClickHouse table + reader | Durable, append-only history of LLM context for replay | ClickHouse (native 9000) |
| C2 | `LLMContextPublisher` write-through | On each publish: Redis (as today) **and** append to C1 | C1; existing publisher |
| C3 | ~~ATR-in-backtest fix~~ | **Removed from P1 scope** (§12 correction 2): not a defect for the non-`ohlcv` williams_r family; only relevant to `ohlcv`-declaring (deprecated) strategies | — |
| C4 | `shared/backtest/robust_gate.py` + `scripts/gate_futures_strategy.py` | Extract `_rescoped_gate`/`_objective_value` into a shared module (DRY); generalized robust-gate CLI runnable for *any* futures strategy YAML | `_rescoped_gate`, BacktestEngine |
| C5a | williams_r true-15m wiring | `timeframe_minutes` param on williams_r → `momentum_<tf>m` + `mtf_base_<tf>m` + `DecisionCadenceGate` (bb_reversion_15m parity pattern); fix `williams_r_15m.yaml` | mtf contract |
| C5b | Candidate entry configs | `williams_r_15m` (now genuinely 15m), `enabled:false`; further orthogonal candidates deferred behind the C5/C4 gate verdict (§12 correction 3) | C5a, C4 |
| C6 | LLM-tuning adapter reuse (P2) | Wrap gate-surviving entry with confidence-scale + regime-gate + veto | C1/C2 for honest eval |
| C7 | Composite agile-exit (P3) | ATR-dynamic trail + momentum_decay + volume-accel responsiveness | C3 (else unvalidated) |

Boundary test for each: *what does it do / how is it used / what does it depend on* — all answerable without reading internals.

## 6. Data flow

- **Live (unchanged behavior + write-through):** `LLMContextPublisher` → Redis `trading:{asset}:market_context` (24h TTL, as today) **and** append row to ClickHouse `llm_market_context`. Redis remains the runtime read path; ClickHouse is the historical record. No backfill — history accrues from cutover forward (the prior work's gap is closed *going forward*, not retroactively; this is acceptable because P1 uses the FLAT-floor CSV path and P2 replay only needs forward history once survivors exist).
- **P1 backtest (FLAT-floor):** `gate_futures_strategy.py` → `BacktestEngine` over `data/kospi200f_1m_ch_101S6000.csv`, mask forced FLAT, identical cost model to CLI/counterfactual. No look-ahead — the closed-bar `mtf_base_<tf>` contract already guarantees decisions use only closed N-min bars.
- **P2 LLM A/B:** replay persisted `llm_market_context` rows aligned to bar timestamps for survivors only; also a live paper A/B (LLM-on vs LLM-off) since replay history is forward-only.

## 7. The universal bar — re-scoped robust §6 gate

Every candidate, every phase, clears this *from scratch* (no exceptions, no "close enough"):

- **(a)** median valid trial (cleared the mandatory min-trades floor, not NaN/degenerate) on train: `Sharpe ≥ 0 AND PF ≥ 1.0`;
- **(b)** broad basin: `≥ 25%` of valid trials clear (a);
- **(c)** selected config out-of-sample (held-out split): `Sharpe ≥ 0 AND PF ≥ 1.0 AND MDD ≤ 25% AND return ≥ 0`.

Thresholds CLI-configurable; **operator sets the final bar**. A min-trades floor (default 50) is mandatory (prevents the low-trade Sharpe degeneracy documented in FINDINGS). Implemented today in `scripts/optimize_llm_directed_indicator.py::_rescoped_gate`; C4 generalizes it to any strategy YAML. A gate FAIL is **terminal** for that candidate and is recorded as reproducible negative evidence (the RL_mppo / llm_directed_indicator precedent — code/config retained, `enabled:false`, FINDINGS appended).

## 8. Error handling & safety

- **LLM-absent path:** degrades to a true **FLAT / no-trade** fallback, *not* an indicator-only floor. The prior work empirically falsified the "indicators-only floor is a reasonable safety net" assumption (§6.1: floor lost money across ~87% of its parameter space). No strategy in this program may rely on a FLAT-bias indicator floor as its safety net.
- **Live gate untouched:** all candidates are paper-only; `config/futures_live.yaml::enabled` stays `false` and Redis `futures:live:suspended` stays set. No phase of this program flips live trading.
- **Setup A/C unaffected:** the program only *adds* (new table, new CLI, new disabled configs) + two surgical fixes (C2 write-through is additive; C3 only populates an indicator that should already be populated). Existing williams_r / Setup A/C / orchestrator / scheduled-events suites must stay green.
- **Gate FAIL is success of the method:** the program's value is a *trustworthy verdict*, including a well-evidenced "no candidate survives" — that is an acceptable, documented outcome (it is what correctly retired RL_mppo and llm_directed_indicator).

## 9. Phase scope & evolution triggers

**Fully specified first deliverable: P0 + P1.** These are non-speculative, non-curve-fittable, and decisively answer "is there a different-information futures edge that clears the robust bar?" P2/P3 and Approach ③ are recorded with explicit trigger conditions:

| Trigger | → Phase |
|---|---|
| P1 yields ≥1 gate-surviving candidate | P2 (LLM-directed entry on survivor) |
| P2 survivor passes paper Sharpe review | P3 (agile exit-assist) |
| P1 yields **zero** survivors after the timeframe axis is exhausted | Approach ③ (microstructure/cross-asset) — new spec |
| Multi-contract operation / RL re-evaluation needed | hierarchical low-level slot (prior spec Path C) |

P2/P3 are *not* built until their trigger fires (YAGNI — same discipline as the prior spec's Path B/C `mask_mode` switch-only boundary).

## 10. Testing & validation

- Robust §6 gate is the bar for every candidate, from scratch (§7).
- C1/C2 (persistence): unit test write-through (Redis + ClickHouse both written; ClickHouse failure must NOT break the live Redis path — best-effort append, logged); integration test round-trip (publish → read back from ClickHouse).
- C3 (ATR fix): regression test proving ATR is non-zero in the backtest adapter path and an ATR-based exit actually fires in a crafted scenario (guards the documented `atr=0.0000` defect).
- C4 (gate CLI): runs `williams_r_15m` end-to-end and prints a PASS/FAIL verdict identical in form to the existing tool.
- Existing suites: williams_r / Setup A/C / orchestrator / scheduled_events / bb_reversion_15m parity stay green.
- P2 LLM contribution: judged by replay + paper A/B, never inferred from the FLAT floor (the explicit lesson of §6.1).

## 11. Open items for the implementation plan

- `llm_market_context` table DDL: columns (`ts DateTime64`, `asset LowCardinality(String)`, `overall_signal String`, `confidence Float64`, `regime String`, `raw JSON/String`), `ORDER BY (asset, ts)`, TTL/retention policy, MergeTree engine choice.
- Exact write-through insertion point in `LLMContextPublisher` and the best-effort/failure-isolation contract (ClickHouse down must not stall the live publisher).
- ATR-in-backtest root cause: where the backtest adapter drops ATR vs. live `IndicatorEngine`, and the minimal fix.
- `gate_futures_strategy.py` CLI surface: `--strategy <yaml> --data <csv> --trials --holdout-split --min-trades --thresholds`; reuse `_rescoped_gate` verbatim.
- Orthogonal-information candidate slate for P1 beyond `williams_r_15m` (15m RSI/MACD-divergence, multi-TF confirmation ensemble) — exact configs.
- Branching/rollout: feature branches only (never `main`/`runtime/main-current`); each surviving candidate flips `enabled:true` *paper-only* exactly as bb_reversion_15m did, gated on its own §7 pass + operator sign-off.

---

## 12. Plan-time corrections (2026-05-19, from code extraction)

Discovered while extracting exact code shapes for the implementation plan; folded in so the plan is factually grounded.

1. **`config/strategies/futures/williams_r_15m.yaml` is cosmetically "15m" only.** It has no `timeframe`/`timeframe_minutes` and no `strategy.backtest` section. Consequently the backtest adapter's `DecisionCadenceGate` is constructed with `timeframe_minutes=0` (no-op → decides every 1-min bar) and no `mtf_base_<tf>` resampling occurs. williams_r reads Williams %R from the `momentum_5m` bundle and `bb_middle` from 1-min BB. **Gating it as-is would merely reproduce the documented 1-min family FAIL.** Therefore P1 must first *wire williams_r to a genuine 15m contract* (new component C5a) — mirroring the `momentum_<tf>`/`mtf_base_<tf>` + `DecisionCadenceGate` pattern productionized this session for bb_reversion_15m — before it is gate-eligible. This strengthens, not weakens, the §2(1) timeframe thesis: it makes the thesis *testable* for this family.

2. **The "ATR-in-backtest" fix (former C3 / FINDINGS lever 3) does not apply to the williams_r family.** williams_r's `required_indicators` do not include `ohlcv`, so `IndicatorContract.needs_ohlcv` is False, `get_rl_features` is never consulted, and both backtest and live use the same raw `_calc_atr_raw` (present once ≥15 1-min candles exist). The `atr=0.0000` symptom in FINDINGS was specific to `ohlcv`-declaring strategies (the deprecated RL / llm_directed_indicator, where normalized `atr` collides with base `atr` and is demoted to `rl_atr`). Building an ATR-plumbing fix in P1 would be YAGNI — nothing in P1 uses it. **Removed from P1 scope**; recorded here as a finding. If a future `ohlcv`-declaring candidate is pursued, the fix is the raw-vs-normalized `atr`/`rl_atr` key collision in `shared/indicators/resolver.py`, not a generic "ATR is zero" bug.

3. **Orthogonal-candidate build is deferred behind the first gate verdict (FAIL-fast).** The spec listed "2–3 orthogonal candidates". Per the spec's own §9 trigger table and YAGNI, building *new* indicator strategies before williams_r-15m's gate result is speculative. P1's decisive candidate is **williams_r at a true 15m** (the one the operator named: "지금은 williams_r 하나가 있어"). If it PASSes → P2. If it FAILs after the 15m-timeframe axis is genuinely exercised → the price-indicator timeframe axis on this family is exhausted → Approach ③ (new spec). No additional candidate strategies are built in P1.

These corrections keep P0+P1 honest and decisive without expanding scope.

---

*Brainstorm note: per operator standing instruction this session, scoping calls (phased program, P0+P1 as the specified deliverable, ② rejected / ③ deferred, the three §12 corrections) were made without one-at-a-time Q&A; the operator redirects at the spec-review gate.*
