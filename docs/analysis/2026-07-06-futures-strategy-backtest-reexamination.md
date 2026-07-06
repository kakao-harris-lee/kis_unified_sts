# Futures Strategy Backtest Re-examination (post KST-timezone fix)

**Date:** 2026-07-06
**Trigger:** `setup_d_vwap_reversion` backtested as **0 trades** over 5 months. Root cause = a backtest-harness timezone bug (PR #593), not a strategy flaw.
**Harness:** `sts backtest run --asset futures --symbol 101S6000 --start 2025-12-01 --end 2026-04-23 --no-track` (continuous KOSPI200-mini series; `point_value=50_000`; MLflow off).

---

## The bug that invalidated prior setup backtests

`shared/strategy/entry/setup_context_builder.py` labeled a **naive** bar timestamp as **UTC**, then `astimezone(KST)` — adding **+9h**. Backtest bars are naive **KST** wall-clock (08:45–15:45), so a 09:10 bar became 18:10 → `MarketContext.minutes_since_open()=565` → every bar tripped the setups' time-window cutoff → **0 trades** for Setup A/C/D through the shared CLI/gate adapter path. Live was unaffected (orchestrator passes tz-aware UTC). Fixed in PR #593 (naive → KST).

**Consequence:** any prior CLI/gate-based reading of Setup A/C/D was untrustworthy. Setup D's real edge only ever appeared in its *dedicated* walk-forward script, which builds context directly and bypassed the bug.

---

## Sweep results (in-sample, post-fix)

> ⚠️ These are **single-pass in-window** backtests (no walk-forward, no OOS) over **one** ~88-day volatility regime, on a **leveraged** instrument (10M KRW capital × 50k point value → return% is highly geared). **Discount the Sharpes and ignore the return%** — the trustworthy metric is a walk-forward OOS Sharpe (see Setup D below). Use this table for *triage*, not verdicts.

| Strategy | enabled | trades | return% | win% | Sharpe | PF | read |
|---|---|---:|---:|---:|---:|---:|---|
| **setup_d_vwap_reversion** | paper | **305** | +28.4 | 49.2 | 4.42 | — | ✅ self-contained; **now backtestable**. Authoritative OOS below. |
| setup_a_gap_reversion | paper | **0** | 0 | — | 0 | — | ⚠️ harness gap, not a verdict — see below |
| setup_c_event_reaction | paper | **0** | 0 | — | 0 | — | ⚠️ harness gap, not a verdict — see below |
| bb_reversion_15m | off | 185 | +221 | 39.5 | 3.64 | — | mean-reversion; strong in-sample → **walk-forward candidate** |
| trix_golden | off | 61 | +28.1 | 44.3 | 1.69 | 1.34 | modest positive in-sample (history: trend NO-SHIP) |
| macd_ema_crossover_15m | off | 16 | +132 | 50.0 | 9.80 | — | **N=16 — untrustworthy** (small-N + 60m trend on an MR market) |
| williams_r_15m | off | 27 | −146 | 7.4 | −8.79 | — | trend entry — confirms fail |
| momentum_breakout | off | 23 | −112 | 30.4 | −6.50 | 0.17 | **NO-SHIP confirmed** (bankrupt) |
| trend_pullback | off | 0 | 0 | — | 0 | — | 0 signal in-window (pullback conditions unmet) |
| stochrsi_trend | off | 0 | 0 | — | 0 | — | 0 — needs `stochrsi_enabled` producer flag |

### Setup D — authoritative walk-forward (OOS)
`scripts/analysis/walkforward_setup_d_vwap_reversion.py` (calls `SetupDVWAPReversion.check()` directly — unaffected by the tz bug; 40d-IS / 10d-OOS daily-stride, Dec 2025–Apr 2026):

- **OOS concat: 135 trades, 40.7% win, Sharpe +2.135, +175.7 pts, 4/4 OOS-profitable folds, symmetric (L +130.5 / S +45.2 pts).**
- The gap vs the in-sample 4.42 is exactly the in-sample inflation this report warns about. This is the number to trust. (Consistent-in-spirit with the prior dedicated run's ~1.77; fold cuts differ.)

---

## Why Setup A and Setup C still show 0 trades (NOT strategy failures)

The tz fix un-tripped the time-window gate — Setup A's rejects now read real minutes (`0m`, `100m∉[10,60]`), not the impossible `565m`. But both setups then reject for **missing harness inputs the CLI adapter never injects**:

- **Setup A** needs an **overnight macro shock** (`min_sp500_gap_pct: 0.30`). `BacktestStrategyAdapter._context_metadata` injects symbol/accumulation metadata only — **no `macro_overnight`** — so the macro-confirmation gate can never fire. The stitched continuous series also has no genuine overnight gaps.
- **Setup C** needs `scheduled_events`; the adapter injects none → `find_recent_event()` returns None → the event gate never fires.

Their real evidence therefore lives in **dedicated harnesses** (Setup A base-rate report: Sharpe ~5.12, N=14; Setup C: N=7). Making them CLI-backtestable requires injecting macro/event context — a **harness-completeness** item on the roadmap, not a strategy fix.

---

## Takeaways

1. **Correctness restored** for the self-contained setup: Setup D is now backtestable via the CLI and its authoritative OOS Sharpe is **~2.1, 4/4 folds, symmetric** — a real, if thin-window, edge.
2. **Setup A/C are un-evaluable via the generic CLI** until the harness injects macro/event context; their standing evidence comes from dedicated harnesses.
3. **In-sample sweep confirms the mean-reversion thesis**: the MR entries (Setup D, bb_reversion) are positive in-sample; the trend/momentum entries (williams_r, momentum_breakout) are strongly negative. `bb_reversion_15m` (+221% / Sharpe 3.64 / 185 trades in-sample) is the one **new walk-forward candidate** worth a rigorous OOS pass — but in-sample MR over a single vol regime is precisely the curve-fit trap, so no conclusion without walk-forward.
4. **`macd` Sharpe 9.80 is noise** (N=16); do not act on it.

Full sweep log: `scratchpad/sweep_results.txt`; walk-forward JSON: `.superpowers/sdd/setup_d_walkforward.json`.
