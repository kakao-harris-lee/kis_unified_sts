# Futures Approach ③ — Regime/Event Gate (Design)

**Status:** Design — awaiting user review before plan
**Date:** 2026-05-21
**Author:** brainstorming session (operator: chihunlee)
**Builds on:** `docs/superpowers/specs/2026-05-19-futures-rlmppo-replacement-indicator-research-design.md` (the P0+P1 spec, §9 trigger fired); `reports/optuna/WILLIAMS_R_15M_GATE.md` (the terminal FAIL on `williams_r_15m`); origin/main `739728c`.

---

## 1. Goal

Decisively answer one question on KOSPI200 futures using **only already-persisted data** (no new infra):

> Does conditioning a gate-surviving baseline (`bb_reversion_15m`) on a **regime / event gate** built from `vol_forecasts` + `event_scores` + the existing daily `macro_history` materially improve out-of-sample Sharpe at the same robustness level, judged by the re-scoped §6 gate?

PASS → P2-③ (apply the survived gate to Setup A/C). FAIL → P3-③ trigger (tick-orderbook microstructure, originally §3 ②; requires new persistence — explicitly out of scope here).

## 2. Non-negotiable constraint (canonical, from spec 2026-05-19 §9)

> "If futures signal work resumes, start from *different information* (not re-tuning this ensemble) and gate any candidate on the re-scoped robust-non-catastrophic bar."

This spec is that next step. The information used here — minute-level realized-vol regime percentiles (HAR-RV) and event impact scores — is **not derived from price indicators**; it satisfies the §9 mandate. Robust §7 gate (median valid-trial Sharpe ≥ 0 / PF ≥ 1.0; ≥25 % basin; OOS non-catastrophic) is reused **verbatim** from `shared/backtest/robust_gate.py` (merged in P0+P1).

## 3. Re-scoping of "Approach ③" — be explicit

The 2026-05-19 spec §3 named Approach ③ as "microstructure / cross-asset pivot (tick-direction / flow imbalance, overnight S&P / USDKRW / cash-futures basis)." A data-inventory pass (2026-05-21) surfaced a sharper picture and re-scopes the *first* deliverable of Approach ③ while preserving the original framing as later triggered phases:

- **Microstructure (tick / L5 orderbook)** is parsed live for futures (`shared/kis/websocket.py` channels `H0IFASP0`/`H0IFCNT0`) but **never persisted**. The `tick_data` table schema exists in `shared/db/client.py` SCHEMAS but **no writer code path uses it**. Stocks lack even the L5 subscription. So tick-microstructure is a *forward-only-from-zero* infra build — months of collection before a first gate test, against a thin theoretical edge made thinner by the 0.026 % round-trip futures cost model. **Defer (= P3-③ trigger).**
- **Cash-futures basis** needs minute-level KOSPI200 spot index + interest rate + dividend yield. KRX Open API gives the spot index only **daily**; rates and dividends are **not plumbed**. Multi-week (likely months) data procurement. **Defer (= a sibling later phase).**
- **What *is* B-state (already-persisted-historical) and qualifies as "different information"** under §9: `vol_forecasts` (HAR-RV per-minute: `forecast_pct`, `regime_percentile`, `forecast_atr_equivalent`, `model_version`; writer: `services/forecasting/main.py` + `shared/forecasting/forecast_publisher.py`); `event_scores` (per-event `impact_score`, `event_type`, `source`); the daily overnight macro series Setup A already pulls (`shared/backtest/macro_history.py`, yfinance). These are minute-level regime / event annotations *not derived from price indicators*. They are the highest-leverage, lowest-cost realization of §9's intent.

**Therefore** P1 of Approach ③ is the **regime / event gate** built on those tables. The microstructure / basis variants remain documented and trigger-gated.

## 4. Approaches reviewed

**① Regime / event gate as a meta-layer over gate-surviving baselines — SELECTED.** B-state data; backtest-ready today; composable with bb_reversion_15m (already paper-passing) and any future candidate; FAIL-fast; in spirit and letter of §9.

**② Tick / orderbook microstructure persistence + flow-imbalance candidates — DEFERRED** (was §3 ②). Forward-only from zero, multi-week infra, slippage realism hurts tick-frequency edges. Recorded with explicit trigger: ① FAILs and operator chooses to invest.

**③' Cash-futures basis + cross-asset minute-level — DEFERRED** (was §3 ③). Months of data sourcing, requires paid feeds. Trigger: both ① and ② fail or operator pivot.

## 5. Architecture

Same phased FAIL-fast shape as the P0+P1 program:

```
P0-③  Data coverage audit (and optional historical recompute)
       └─ Verify vol_forecasts / event_scores coverage of the gate-test window
P1-③  RegimeGate + decisive gate test (THIS spec's deliverable)
       ├─ shared/strategy/gates/regime_gate.py  (pure filter)
       ├─ backtest-adapter hook (block → signal.NEUTRAL, never-raise)
       ├─ gate runner extended with --gate flag (DRY off Task-4 CLI)
       └─ run gate on bb_reversion_15m + RegimeGate; record verdict
                │  (only if PASS):
P2-③  Apply the survived gate to Setup A/C  (trigger-gated)
P3-③  Tick/orderbook microstructure (was §3 ②)  (FAIL trigger)
P4-③  Cash-futures basis / cross-asset minute (was §3 ③)  (later trigger)
```

P0+P1 is the fully-specified first deliverable (~1 week). P2/P3/P4 are recorded with explicit triggers (§9), not built here.

## 6. Components & boundaries

| # | Component | Responsibility | Depends on |
|---|---|---|---|
| C1 | `scripts/audit_forecast_coverage.py` (small CLI) | Query `vol_forecasts` + `event_scores` over a window; print coverage % + gaps | ClickHouse (existing) |
| C2 | HAR-RV historical recompute *(only if C1 finds material gaps)* | Recompute realized-vol regimes post-hoc from `minute_candles` using the same HAR-RV math; write into `vol_forecasts` with a `model_version` distinguishing "historical_recompute" from "live_publish" | `shared/forecasting/` math |
| C3 | `shared/strategy/gates/regime_gate.py` (NEW module path / boundary) | Pure `RegimeGate.allow(ts, asset, ctx) → (bool, reason)`; reads vol_forecasts / event_scores / macro_history; config-driven thresholds | C1 (data presence) |
| C4 | Backtest adapter hook | When a strategy emits an entry signal, query the gate; on block, return signal with `signal_direction=NEUTRAL` + reason — strategy logic untouched, only the entry is muted. Minimal, single-arrow change | C3 |
| C5 | Gate-runner extension | Extend `scripts/gate_futures_strategy.py` (or thin sibling): `--gate <yaml>` flag that activates C4. Reuses the same robust §7 evaluation (P0+P1 DRY) | Task-4 CLI, C3, C4 |
| C6 | Decisive gate test + verdict | Run baseline `bb_reversion_15m` and gated `bb_reversion_15m + RegimeGate` through the same robust gate; record terminal verdict in `reports/optuna/BB_REVERSION_15M_REGIME_GATE.md` | C5 |

**No live-trading wiring in this spec.** The gate is paper-only / backtest-only here; live application is P2-③, behind a separate operator sign-off.

## 7. Data flow

- **Backtest:** `minute_candles → strategy.generate() → entry_signal → RegimeGate.allow(ts, asset, ctx)` reads `vol_forecasts` row at `ts` + `event_scores` rows within ± `event_window_minutes` + macro_history row for the session date. If block → `signal_direction = NEUTRAL` (entry suppressed, exits unchanged). Engine simulates as usual.
- **Look-ahead safety:** all three inputs are timestamped at-or-before the bar; gate must enforce `vol_forecasts.asof <= ts` and `event_scores.asof <= ts` (the same closed-bar discipline as `mtf_base_<tf>`/`DecisionCadenceGate`).
- **Live:** unchanged (P2-③ task).

## 8. The universal bar — robust §7 + a head-to-head delta

Every candidate clears the re-scoped §6 gate (verbatim from P0+P1):

- (a) median valid-trial train Sharpe ≥ 0 & PF ≥ 1.0
- (b) ≥ 25 % of valid trials clear (a)
- (c) selected cfg OOS Sharpe ≥ 0 & PF ≥ 1.0 & MDD ≤ 25 % & return ≥ 0

**Plus an honest head-to-head:** `bb_reversion_15m` already passed the bare gate. The gated variant must **strictly improve OOS Sharpe by ≥ δ AND not worsen MDD** vs the baseline at the same trial budget. Operator sets δ (suggested default 0.5 Sharpe units; CLI-configurable). A gate that merely matches baseline is a FAIL — the cost-of-complexity must earn its keep.

A FAIL at §7 or at the head-to-head is **terminal** for this gate variant (recorded as reproducible negative evidence, mirroring the RL_mppo / llm_directed_indicator / williams_r_15m precedents) and fires the §9 trigger to Approach ② (tick microstructure).

## 9. Error handling & safety

- **Missing inputs degrade to PERMISSIVE pass-through, not block.** If `vol_forecasts` row is absent for a `ts` (forecaster wasn't live), the gate must **allow** the signal, not suppress it. Otherwise missing data confounds the head-to-head: a gate that "improves" Sharpe by silently dropping all trades on uncovered days is fraudulent. C1's coverage audit must establish gate-applicability before the gate test runs; gaps shrink the test window, not the trade count.
- **Look-ahead guard active:** the existing `BacktestConfig.lookahead_guard_mode = "assert"` (CLAUDE.md C1) extends naturally to gate inputs.
- **No live flags touched:** `futures_live.enabled` stays `false`; Redis `futures:live:suspended` stays set. `bb_reversion_15m.yaml` stays paper-only.
- **`historical_recompute` model_version isolation:** if C2 runs, those rows are tagged with a distinct `model_version` so we can never accidentally claim a backtest "saw" a live-emitted forecast it didn't. The head-to-head must use one mode consistently (live-only vs recompute), explicitly named in the verdict report.

## 10. Phase scope & triggers (§9 fulfillment table)

| Trigger | → Phase |
|---|---|
| P1 PASS (gate adds ≥ δ Sharpe over bb_reversion_15m at same robustness) | P2-③ (apply to Setup A/C) |
| P1 FAIL (gate doesn't materially help, or it degrades robustness) | P3-③ (tick microstructure — was §3 ② / new spec) |
| P2-③ PASS in paper observation | Operationalize live (separate operator-owned step) |
| P3-③ FAIL or operator pivot | P4-③ (cash-futures basis / cross-asset minute, new spec) |

The first plan covers P0-③ + P1-③ only. P2/P3/P4 are *not* built here.

## 11. Testing & validation

- C1 (audit): unit test on a synthetic ClickHouse fixture (or mocked client) verifying coverage % math and gap reporting.
- C2 (recompute): a regression test that the historical HAR-RV implementation reproduces a known fixture window byte-for-byte under a fixed seed/inputs; `model_version` flag set correctly.
- C3 (gate): unit tests — block when `regime_percentile > threshold`; block when an `event_score > threshold` falls inside ± `event_window_minutes`; allow when inputs absent (PERMISSIVE degrade); look-ahead guard rejects any row with `asof > ts`.
- C4 (adapter hook): integration test — gated bar suppresses entry but leaves exit logic untouched; ungated bar passes through unchanged.
- C5 (runner): smoke that `--gate <yaml>` end-to-ends `bb_reversion_15m` over a tiny synthetic df.
- C6: actual gate run + verdict report transcribed from the real log (no fabrication, per the integrity rules of T6 in P0+P1).
- Existing suites stay green (P0+P1 is reused verbatim — no edits to `robust_gate.py`, `gate_futures_strategy.py` core, or `bb_reversion_15m`).

## 12. Open items for the implementation plan

- C1 SQL: exact query against `vol_forecasts` / `event_scores`; window definition; coverage threshold for "no recompute needed."
- C2 decision: do we need it? (Depends on C1 coverage result for the gate-test window.) If yes, the exact HAR-RV math reference and the `model_version` string.
- `RegimeGate` config schema: `regime_percentile_max`, `impact_score_max`, `event_window_minutes`, `require_overnight_us_direction` (boolean + alignment rule), `permissive_on_missing` (default true).
- δ (head-to-head Sharpe margin) default and operator override CLI flag.
- The exact `--gate` flag surface for the gate runner.
- bb_reversion_15m gate-test window: which OOS split (likely 2026-02-01 mirroring P0+P1) and trial count.

---

## 13. Plan-time corrections (2026-05-21, from code extraction)

Discovered while extracting exact code shapes for the plan; folded in so the plan is factually grounded. Cf. yesterday's §12.

1. **The "block" path is `SignalType.HOLD`, NOT `signal_direction = NEUTRAL`.** `shared/backtest/engine.py:36-41` defines `SignalType{HOLD, BUY, SELL}`; there is no NEUTRAL. `signal_direction` (`"long"`/`"short"`) lives in `signal.metadata`, not as a top-level field on `Signal`. The §7 wording is amended: *block → force `signal = SignalType.HOLD` before the BUY/SELL dispatch.*
2. **The gate-injection point is the ENGINE, not the adapter.** `shared/backtest/engine.py:326` calls `signal = self.strategy.on_bar(bar)`; the BUY/SELL dispatch follows at 331–360. Injecting the gate here keeps it strategy-agnostic (applies to ANY strategy without touching adapter or strategy code), simpler, and DRY. C4 in §6 is amended accordingly.
3. **`forecast_pct` is annualized percent** (e.g. `30` means 30%), not a fraction or unit-pct. `shared/forecasting/volatility_har_rv.py:140`: `forecast_pct = sqrt(pred_rv * 252) * 100`. **`regime_percentile` is the empirical CDF position scaled 0–100** (line 149: `(self._rv_history < pred_rv).mean() * 100`). Gate thresholds in `regime_gate_default.yaml` use these natural units (e.g. `regime_percentile_max: 80.0` = block when predicted RV exceeds the 80th percentile of in-fit daily RV history).
4. **`MacroSnapshot.sp500_change_pct` is a percentage, no precomputed direction.** Direction must be derived via `math.copysign(1.0, sp500_change_pct)` (same pattern Setup A uses at `shared/decision/setups/gap_reversion.py:133`).
5. **`vol_forecasts` TTL is 90 DAY** (`infra/clickhouse/migrations/V6__forecast_tables.sql`). For any backtest window older than ~90 days, live-emitted vol_forecasts have been TTL-evicted → C2 (historical HAR-RV recompute) is **required**, not optional, for the bb_reversion_15m gate-test data range (2025-07-01 → 2026-04-23). The recompute writes rows with `model_version = "har_rv_v1_recompute"`, distinct from live `"har_rv_v1"` (§9 isolation rule preserved).
6. **DDL location** for `vol_forecasts` / `event_scores` is `infra/clickhouse/migrations/V6__forecast_tables.sql`, **not** `shared/db/client.py::SCHEMAS`. The plan's table-existence assumptions reference the migration file.

Outside the spec: **the daily RV input the HAR-RV `fit()` expects is a `pd.Series` keyed by date** (`shared/forecasting/volatility_har_rv.py:59`), constructible from `kospi.kospi200f_1m` minute candles via `shared.forecasting.realized_variance.daily_rv_series(...)` (cf. `scripts/forecasting/refit_har_rv.py:52-65`). The plan's recompute task wires this end-to-end.

---

*Brainstorm note: per operator standing instruction this session, scoping calls — re-scoping Approach ③'s first deliverable from the original §3 tick/basis examples to the available-B-state regime/event gate; deferring ②/③' as triggered later phases; mandating head-to-head over baseline; permissive degrade on missing data — were made without one-at-a-time Q&A. Operator redirects at this spec-review gate.*
