# P2-③ — RegimeGate for Setup A/C + bb_reversion_15m (Live Paper) — Design

**Status:** Design — awaiting user review before plan
**Date:** 2026-05-22
**Author:** brainstorming session (operator: chihunlee)
**Builds on:** `docs/superpowers/specs/2026-05-21-futures-approach3-regime-gate-design.md` (the P0+P1 spec, §10 P2-③ trigger fired); PR e6cfa35 (Approach ③ P0+P1+Path A+T11+T12 merged, head-to-head PASS Δ=+3.26).

---

## 1. Goal

Apply the just-validated RegimeGate (PASS Δ=+3.26 on bb_reversion_15m backtest) to live paper trading on:

- **Setup A** (gap reversion) — primary validation target; fires regularly in paper today
- **Setup C** (event reaction) — wired but operationally dormant (event sourcing is sparse)
- **bb_reversion_15m** — bonus bundling (same adapter-layer wiring locus); makes the strategy that PASSed actually use the gate in live paper

Validation is via **live paper A/B with counterfactual logging** over ≥2 weeks per activated strategy. Backtest validation is intentionally NOT in scope (no backtest harness exists for Setup A/C, building one is multi-day, and the gate's design is already backtest-validated on bb_reversion_15m).

## 2. Non-negotiable constraints (canonical)

From the just-merged Approach ③ spec §10:

> "P1 PASS (gate adds ≥ δ Sharpe over bb_reversion_15m at same robustness) → P2-③ (apply to Setup A/C)"

Plus from yesterday's §13/§9 corrections (still binding):

- **Gate degrades to PERMISSIVE** on missing inputs (never silently blocks on data gaps).
- **No live-trading flags touched** — `futures_live.enabled` stays `false`, Redis `futures:live:suspended` stays set. The gate is paper-only; live live activation is a separate, much later operator decision.
- **Per-strategy opt-in only** — each strategy YAML gets `regime_gate.enabled: false` by default. Activation requires explicit operator YAML flip.

## 3. Re-scoping notes (explicit)

The literal §10 trigger says "apply to Setup A/C". Exploration revealed two facts that shape this spec's honest interpretation:

1. **Setup C effectively never fires in production today.** `config/scheduled_events.yaml` is manually curated and sparse; `event_scores` table has zero rows; `find_recent_event()` rarely returns a hit. Setup C will inherit the gate code via the same adapter-layer wiring as Setup A, but **the gate cannot produce meaningful operational evidence on Setup C until a separate event-sourcing fix lands** (out of scope here). Spec acknowledges this; operator-facing reporting flags Setup C signal counts.

2. **bb_reversion_15m's gate validation was backtest-only.** The PASS Δ=+3.26 verdict was a backtest head-to-head. The strategy is already in paper, but the gate isn't yet wired into the live entry path. Since bb_reversion_15m's `MeanReversionEntry` adapter sits at the same layer as Setup A/C's adapters, the same wiring pattern lights up live-gate behavior with one extra file edit. Bundle the bonus; the §10 trigger is satisfied for bb_reversion_15m too.

## 4. Approaches reviewed

**① Adapter-level wiring + live-paper A/B + counterfactual logging — SELECTED.** Cleanest hook (mirrors LLM-tuning/veto layer per-adapter). Aligns with existing forecasting infrastructure (`scripts/cron/forecasting.sh` keeps `_tick_forecast` writing `vol_forecasts` + `forecast:vol:current` Redis every ~60s). Weeks-not-days to a verdict; threshold transferability is empirical (a real operational concern).

**② Build a Setup A backtest harness first — REJECTED.** Multi-day investment (3-5 days). Setup A's signal logic is pattern-driven (overnight macro gap → retrace), not parameter-tuned; an Optuna head-to-head on Setup A adds less than it did for bb_reversion_15m (which had a 7-dim search space). Macro_history coverage uncertain offline. Doesn't actually de-risk ① meaningfully and delays evidence by a week.

**③ Skip Setup A/C entirely; only wire bb_reversion_15m's live gate — REJECTED.** Doesn't fulfill the literal §10 trigger; Setup A/C wiring deferred indefinitely. Bundling bb_reversion_15m INTO ① achieves the same win for free.

## 5. Architecture

Single-locus adapter integration: `RegimeGate` is injected at adapter construction (from per-strategy YAML config), consulted inside `generate()` AFTER existing LLM-tuning/veto logic but BEFORE the orchestrator Signal is returned. On block: return `None` (suppress entry, exits unchanged). On allow: pass-through. Every decision is logged best-effort to a new `regime_gate_decisions` ClickHouse table for weekly counterfactual review.

```
Strategy (Setup A / Setup C / bb_reversion_15m)
   │
   └─▶ Adapter.generate(EntryContext)
         │
         │   [existing] decision logic (gap detect / event window / BB-RSI)
         │   [existing] LLM tuning + veto
         │   [NEW]      gate.allow(ts, asset, signal_direction) → (bool, reason)
         │   [NEW]      log_decision(...)   (best-effort; PERMISSIVE on CH miss)
         │
         └─▶ return Signal | None
```

Reused (no changes): `RegimeGate` (P1-③ C3), the existing `forecast:vol:current` Redis publisher, the existing `event_scores` table, Setup A/C's existing LLM-tuning/veto code paths, the orchestrator's existing entry-execution.

Added: `LiveVolInputs` (Redis+CH-backed duck-typed source for `RegimeGate`), `regime_gate_decisions` ClickHouse table + writer, adapter integration at 3 sites, per-strategy YAML schema for `regime_gate`, weekly counterfactual analyzer.

## 6. Components & boundaries

| # | Component | Responsibility | Depends on |
|---|---|---|---|
| C1 | `LiveVolInputs` (NEW class in `shared/strategy/gates/live_inputs.py`) | Duck-typed source for `RegimeGate`: `latest_vol_at(ts)` reads `forecast:vol:current` from Redis (PERMISSIVE on miss); `events_within(ts, window)` reads `kospi.event_scores` via CH; `macro_for(date)` reads `MarketContext.macro_overnight` from the EntryContext. No backtest dependency. | Redis (live), CH (live), EntryContext |
| C2 | `regime_gate_decisions` CH table + `insert_regime_gate_decision()` | Best-effort append-only history of every gate decision (ts, strategy, signal_direction, allow, reason, regime_pct). Failure-isolated. | ClickHouse (existing pattern from `llm_market_context` write-through) |
| C3 | `SetupAEntryAdapter.generate()` integration | After LLM veto, before Signal return: call gate; on block, log+return None; on allow, log+return Signal | C1, C2 |
| C4 | `SetupCEntryAdapter.generate()` integration | Same as C3 (symmetric) | C1, C2 |
| C5 | `MeanReversionEntry.generate()` integration | Same as C3 (bb_reversion_15m bonus) | C1, C2 |
| C6 | Per-strategy YAML schema | `entry.params.regime_gate: {enabled: bool, regime_percentile_max: float, impact_score_max: int, event_window_minutes: int, require_overnight_us_direction: bool, permissive_on_missing: bool}`. Default `enabled: false`. Loader builds a `GateConfig` if enabled; otherwise no-op. | None |
| C7 | Weekly counterfactual analyzer | `scripts/analysis/regime_gate_counterfactual.py` — query `regime_gate_decisions` for last 7 days, group by strategy, report block rate + a P&L estimate (blocked-entries-look-back vs allowed-entries-actual). Telegram digest. | C2, Telegram, weekly cron |

Each unit is independently testable. Adapter-layer integration mirrors the existing LLM-tuning/veto pattern (same logical layer; same per-strategy YAML config locus).

## 7. Data flow (live)

```
Live tick → StrategyManager.check_entries(context)
                  │
                  ▼
        Adapter.generate(context):
           1. Existing decision logic produces decision_signal
           2. Existing LLM tuning/veto runs (may early-return None)
           3. NEW gate check:
                a. inputs = LiveVolInputs(redis, ch, context)
                b. allow, reason = gate.allow(ts, asset, signal_direction)
                c. insert_regime_gate_decision({ts, strategy, ...allow, reason})
                d. if not allow: return None    # block
           4. Return orchestrator Signal
                  │
                  ▼
        StrategyManager filters + orchestrator executes
```

**Critical:** the gate's data source is **Redis live** (`forecast:vol:current`), NOT the ClickHouse vol_forecasts replay path the backtest uses. This avoids a CH SELECT on every tick (hot path) and uses the already-published 60-second-cadence live value. The Redis key has 120s TTL — if it goes stale the gate degrades PERMISSIVE per §9. (Backtest-path `_CHInputs` is unchanged; that's offline-only.)

## 8. Validation criteria (weekly counterfactual review)

Pure live-paper A/B is not feasible (we have only one paper account per strategy). Instead, **counterfactual logging**:

- Every gate decision logged: `(ts, strategy, signal_direction, allow, reason, regime_pct, decision_signal_id)`.
- Weekly analyzer compares two cohorts over the past 7 days:
  - **Blocked** signals: simulate "what would the entry have done over a fixed forward-window" using subsequent realized price moves from `kospi200f_1m` (clean A01603 series where available).
  - **Allowed** signals: use the actual paper P&L from `rl_trades` / `swing_positions`.
- Telegram digest reports: block-rate %, mean blocked-signal-P&L vs allowed-signal-P&L, week-over-week trend, per-strategy breakdown.
- **Promotion gate (operator decision after ≥2 weeks):** if blocked-signal-mean-P&L < allowed-signal-mean-P&L AND block-rate is in a reasonable range (5-30%), the gate is adding value — keep enabled. Else: re-tune threshold or disable.

This is a deliberately *qualitative* gate (operator interprets the digest), not an automated PASS/FAIL bar — because the live-paper sample is too small for the rigorous robust §6 statistics used in backtest. A future bar can be defined once enough paper history accrues.

## 9. Error handling & safety

- **Gate degrade**: PERMISSIVE on any missing input (Redis vol stale/absent; event_scores query failure; macro_overnight absent). Same §9 discipline.
- **Best-effort decision logging**: `insert_regime_gate_decision()` is wrapped in broad try/except + `logger.warning(...)`; CH failure NEVER blocks the entry decision.
- **Default-off**: every strategy YAML defaults `regime_gate.enabled: false`. Activation per-strategy requires an explicit operator YAML edit (auditable in git).
- **No live-trading flag changes**: `futures_live.enabled` stays `false`; Redis `futures:live:suspended` stays set. This spec is paper-only.
- **Backtest path unchanged**: `_CHInputs` and the gate-runner CLI from P1-③ are unaffected. Backtest re-runs continue to produce the same results.
- **Setup C honest expectation**: with `event_scores` empty + `scheduled_events.yaml` sparse, Setup C will rarely emit decision_signals, so the gate's Setup C decision-count will be near-zero. Reported as a known limitation in the weekly digest.

## 10. Phase scope & triggers

This spec covers P2-③ — all six tasks ship in ONE plan (T1-T6 below). Operator activation (T7 — flipping `enabled: true` on Setup A's YAML and watching paper) is OUT of scope here (it's an operator runbook step gated by the spec being merged).

| Trigger | → Phase |
|---|---|
| P2-③ merged + Setup A activated for ≥2 weeks → mean-blocked-P&L < mean-allowed-P&L | Keep enabled; consider activating Setup C (if event-sourcing fixed) and bb_reversion_15m |
| Activation shows neutral / negative impact | Tune threshold per strategy (separate small follow-up); if still neutral after re-tune, disable |
| Setup C event-sourcing fix lands (separate spec) | Activate Setup C's gate; observe |
| Operator decides to move from paper to live (months out) | Separate operational decision; this spec doesn't enable it |

## 11. Testing

- C1 (`LiveVolInputs`): unit tests with mocked Redis + CH client (PERMISSIVE on miss; tz-naive normalization; happy path).
- C2 (decision-logger): unit test with mocked CH (best-effort failure isolation per `_append_market_context_history` pattern).
- C3/C4/C5 (adapter integration): 3 tests per adapter — gate-blocks-suppresses-signal; gate-allows-passthrough; missing-vol-permissive. 9 tests total. Use the existing forecast_integration unit-test mock pattern from `tests/unit/strategy/test_setup_a_forecast_integration.py`.
- C6 (config schema): unit test loading a YAML with `regime_gate.enabled: true` builds a valid `GateConfig`; `enabled: false` produces a no-op shim.
- C7 (counterfactual analyzer): unit test the cohort grouping + P&L estimate math; integration test deferred (script is invoked weekly by cron, not part of CI).
- Existing suites stay green (P0+P1 merged at e6cfa35 — 152+ tests; this spec only ADDS new units, no edits to existing test logic).

## 12. Open items for the implementation plan

- Exact `LiveVolInputs` Redis key access pattern (reuse `shared/forecasting/vol_reader.py::read_latest_vol_forecast`? or new helper).
- `regime_gate_decisions` table DDL + retention TTL (default 90 days, matching `vol_forecasts`).
- Per-strategy YAML schema validation (Pydantic model for `RegimeGateYAML`; auto-merge with `config/gates/regime_gate_default.yaml` for unspecified fields).
- The exact log-decision SQL + tuple shape (mirror `insert_llm_market_context` from P0).
- Counterfactual P&L lookback window (suggest: 15 minutes for blocked-entry simulation since bb_reversion_15m operates at 15m and Setup A/C are intraday).
- Telegram digest format (mirror existing weekly counterfactual cron at `scripts/cron/` if one exists; else new).
- Cron schedule for the weekly analyzer (suggest: Sunday 18:00 KST).

---

## 13. Plan-time corrections (2026-05-22, from exploration)

Discovered while mapping the live entry-signal flow; folded in so the plan is factually grounded.

1. **Live gate hook locus is the adapter, not StrategyManager.** Three options were considered (StrategyManager filter, adapter integration, orchestrator post-filter); the adapter is the cleanest because it sits at the same logical layer as the existing per-strategy LLM-tuning/veto logic — symmetric structure, same YAML config locus, no new pipeline abstraction needed.
2. **Live gate data source is Redis, not ClickHouse.** The backtest path uses `_CHInputs` (CH SELECT + bisect over a pre-loaded window). The live path uses `forecast:vol:current` Redis key directly (the same value the live `_tick_forecast` writes every 60s). This avoids CH-SELECT-on-every-tick latency and uses the data source Setup A/C's existing `forecast_integration` already consumes.
3. **Setup C operational evidence will be near-zero until a separate event-sourcing fix.** `event_scores` is empty for all time; `scheduled_events.yaml` is sparse and manually curated. Wiring lands for Setup C symmetrically with Setup A, but the spec's validation discipline (counterfactual digest) explicitly reports Setup C decision-count and flags low signal as expected-not-defect.
4. **bb_reversion_15m bundling is free.** `MeanReversionEntry.generate()` sits at the same adapter layer; one extra file edit + one extra YAML section activates the gate for bb_reversion_15m in live paper. Bundled into this spec rather than deferred to a separate scope.
5. **Backtest validation is NOT in scope.** No Setup A/C backtest harness exists; building one is 3-5 days; macro_overnight isn't replayed offline; `event_scores` is empty. Live paper + counterfactual digest is the substantive validation discipline for this spec, with the operator interpreting weekly evidence rather than a §6-style automated gate.
6. **Counterfactual review is qualitative, not a robust §6 bar.** Live-paper sample size is too small for the median-valid-trial / basin-fraction / OOS-non-catastrophic framework that worked for the bb_reversion_15m backtest. The operator reviews the weekly Telegram digest and decides; a quantitative bar can be defined once ≥3 months of paper data accrues.

These corrections shape the design without changing its goal.

---

*Brainstorm note: per operator standing instruction this session, scoping calls (adapter-layer hook; Setup A primary / Setup C wired-but-dormant; bb_reversion_15m bonus bundling; backtest-validation explicitly out of scope; qualitative counterfactual digest instead of robust §6 bar) were made without one-at-a-time Q&A. The operator redirects at this spec-review gate.*
