# Futures Backtest Macro-Context Unblock Report

**Date**: 2026-06-21  
**Branch**: `feat/futures-backtest-macro-context`  
**Script**: `scripts/analysis/backtest_macro_setup_ac.py`

---

## Feasibility Assessment

### macro_overnight (SP500)
**FEASIBLE.** yfinance provides S&P 500 daily close history for the full holdout span. Bar-density gating to healthy days (>=330 bars/day) still achieves 100% macro coverage (86/86 trading days in the clean Nov2025–Apr2026 window).

LookaheadGuard compliance: KR session date T maps to the US close of T-1 (last available US trading day strictly before T). The US close (~22:00 KST on T-1) precedes the KR open (09:00 KST on T) by ~11 hours — no look-ahead.

### LLM market context
**NOT REPLAYABLE** from historical files. `output/llm/unified_data_*.json` files contain `direction`/`confidence` from the nightly LLM briefing, NOT the `overall_signal`/`regime` schema that `shared/strategy/entry/setup_adapters.py` consumes. No direct replay possible. Ran with `llm_tuning.enabled=False` (the Pydantic default) — labeled "macro-only, LLM tuning excluded" throughout.

---

## Data Quality — Futures Minute Feed Degradation

A parallel data-quality audit (controller, 2026-06-21) confirmed severe bar degradation:

| Period | Bars/Day (avg) | Quality |
|--------|---------------|---------|
| Jul–Sep 2025 | 69–123 | Severely degraded — unusable |
| Oct 2025 | 208 | Degraded |
| Nov 2025 | 229 | Borderline |
| Dec 2025 | 335 | Healthy |
| Jan–Apr 2026 | 368–411 | Healthy |

Root cause: WS feed instability fixed by PR #491 (deployed 2026-06-21). May–Jun 2026 futures minute is a permanent hole (KIS REST history ~30 days).

**Enforcement**: the script's `--min-bars-per-day 330` flag (default) automatically drops degraded trading days before analysis. Applied to the CSV, this drops 115/201 calendar days, leaving the clean **Nov2025–Apr2026** window (86 healthy trading days).

---

## What Was Built

`scripts/analysis/backtest_macro_setup_ac.py` — a self-contained harness that:

1. Applies `--min-bars-per-day 330` bar-density gate to exclude degraded feed periods
2. Backfills S&P 500 daily close/change_pct via yfinance (`build_sp500_daily_snapshots`)
3. Builds a `macro_provider(date) -> MacroSnapshot` callable that feeds `MarketContextReplay`
4. Runs `MarketContextReplay` + **real `SetupAGapReversion`** (from `config/decision_engine.yaml`)
5. Collects one Setup A entry per day (matching live behavior)
6. Applies `min_volume=30` to suppress phantom 2-4 volume bars
7. Simulates both **TrackAExit** (tuned trail=1.5, activate=2.0) and **SetupTargetExit**
8. Reports per-arm metrics with configurable train/holdout split

Setup C entries are 0 because no real scheduled-event calendar is available. This is a known limitation, not a code defect.

---

## Re-Validation Results: Clean Window (Nov2025–Apr2026)

**Split**: train = Nov2025–Jan2026 (34 healthy days), holdout = Feb2026–Apr2026 (52 days)  
**Data**: after bar-density gate (>=330 bars/day) + min_volume=30  
**LLM context**: excluded (macro-only)

### TRAIN (Nov2025–Jan2026, 34 days, 6 Setup A trades)

| Metric | TrackAExit (1.5/2.0) | SetupTargetExit |
|--------|---------------------|-----------------|
| Trades | 6 | 6 |
| Win Rate | 66.7% | 66.7% |
| Avg Return | -0.009% | **+0.063%** |
| Total PnL (pts) | -0.80 | **+2.15** |
| Sharpe | -0.332 | **+2.404** |
| MDD | 2.90% | 2.20% |
| Median Hold | 32 min | 18 min |

### HOLDOUT (Feb2026–Apr2026, 52 days, 15 Setup A trades)

| Metric | TrackAExit (1.5/2.0) | SetupTargetExit |
|--------|---------------------|-----------------|
| Trades | 15 | 15 |
| Win Rate | 60.0% | 53.3% |
| Avg Return | -0.089% | **+0.098%** |
| Total PnL (pts) | -10.90 | **+13.40** |
| Total PnL (KRW) | -545,000 | **+670,000** |
| Sharpe | **-1.240** | **+2.016** |
| MDD | 16.60% | 9.38% |
| Median Hold | 30 min | 13 min |
| Exit breakdown | trail(11) + catastrophic(4) | target(8) + stop(7) |

---

## Key Findings

### 1. Real Setup A fires — blocker resolved
Real `SetupAGapReversion` generates 15 trades in the holdout period (52 days) vs 0 without macro context. Signal frequency: ~1 trade per 3.5 trading days.

### 2. TrackAExit (1.5/2.0) underperforms SetupTargetExit on REAL Setup A signals (CLEAN WINDOW)
Result is consistent across both the full dataset run and the healthy-window run:
- Holdout Sharpe: -1.24 (TrackA) vs +2.02 (Target). Delta = -3.26.
- Holdout PnL: -10.9 pts (TrackA) vs +13.4 pts (Target). Delta = -24.3 pts.
- TrackA MDD = 16.6% vs Target MDD = 9.4%.

This **reverses the proxy backtest verdict** that suggested TrackA outperforms.

### 3. Why the proxy result was wrong
The proxy harness synthesized entries with relaxed conditions (retrace [10-85%], gap ≥0.1%) capturing a much broader population. Real Setup A fires on a tight band (retrace [20-70%], sp500_gap ≥0.3%, kr_gap ≥0.3%, strict time window 10-90min). On the real signal population, gap-reversion trades snap back to target quickly (median 13 min via Target exit). The ATR trail at 1.5×ATR activates at 2.0×ATR profit, but by the time that threshold is reached, price is already near the target — the trail then gives back 0.40% median. The fixed-target exit avoids this entirely.

### 4. Catastrophic stops under TrackA
4/15 holdout trades exited via `catastrophic_stop` (6.0×ATR adverse move) under TrackA vs 0 under Target. This suggests trades where price reversed sharply while the trail was not yet activated (profit < 2.0×ATR), and the 1.5×ATR hard stop from the Setup A config didn't fire before the 6.0×ATR backstop did.

### 5. Setup C: 0 trades (calendar required)
`SetupCEventReaction.check()` requires `ScheduledEvent` objects with impact_tier ≤ 2 within the last 720 minutes. Without a real event calendar (US CPI/FOMC/NFP dates), Setup C cannot fire. Providing a historical CSV of economic events would unblock this.

---

## Recommendations

1. **Revert to SetupTargetExit for Setup A**: fixed gap-fill target + stop_atr_mult=1.5 outperforms TrackA (1.5/2.0) by Sharpe +3.26 in holdout. Rollback is a YAML flag: `exit.type: setup_target_exit` + `daily_bias_filter_enabled: false`.

2. **TrackA may fit Setup C breakout signals better** than gap-reversion. The trailing-exit logic is better suited to directional breakouts. Setup C real-signal validation requires an event calendar.

3. **Bar-density gate is now default** (`--min-bars-per-day 330`). All future runs on this dataset auto-exclude the degraded Jul–Oct 2025 window.

---

## Run Commands

```bash
# Clean-window run (recommended — excludes degraded Jul-Oct 2025):
.venv/bin/python scripts/analysis/backtest_macro_setup_ac.py \
  --min-volume 30 \
  --min-bars-per-day 330 \
  --holdout-split 2026-02-01

# Holdout-only:
.venv/bin/python scripts/analysis/backtest_macro_setup_ac.py \
  --min-volume 30 --min-bars-per-day 330 --holdout-split 2026-02-01 --holdout-only
```

---

## Files

- Harness: `/home/deploy/project/kis_unified_sts/scripts/analysis/backtest_macro_setup_ac.py`
- JSON output (clean window): `/home/deploy/project/kis_unified_sts/.superpowers/sdd/bt-data-unblock-report-macro-clean.json`
