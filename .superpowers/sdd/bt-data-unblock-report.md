# Futures Backtest Macro-Context Unblock Report

**Date**: 2026-06-21  
**Branch**: `feat/futures-backtest-macro-context`  
**Script**: `scripts/analysis/backtest_macro_setup_ac.py`

---

## Feasibility Assessment

### macro_overnight (SP500)
**FEASIBLE.** yfinance provides S&P 500 daily close history back to 2025-07-01 and beyond, covering the full holdout span (2025-07 to 2026-04, 201 trading days). **100% macro coverage** achieved.

LookaheadGuard compliance: KR session date T maps to the US close of T-1 (last available US trading day strictly before T). The US close (~22:00 KST on T-1) precedes the KR open (09:00 KST on T) by ~11 hours — no look-ahead.

### LLM market context
**NOT REPLAYABLE** from historical files. `output/llm/unified_data_*.json` files (378 entries covering 2026-01 to 2026-06) contain `direction`/`confidence` fields from the nightly LLM briefing, but NOT in the `overall_signal`/`regime` schema that `shared/strategy/entry/setup_adapters.py` consumes (`SetupAEntryAdapter`/`SetupCEntryAdapter`). The adapter expects `MarketContextLLM.overall_signal` (e.g. `"STRONG_BEARISH"`) and `regime` fields, which were never persisted in the JSON output.

**Decision**: Run with `llm_tuning.enabled=False` (the Pydantic default). This is the deterministic **indicator+macro core** of Setup A/C — the most honest backtest possible without fabricating LLM scores. Clearly labeled in all output.

---

## What Was Built

`scripts/analysis/backtest_macro_setup_ac.py` — a self-contained harness that:

1. Backfills SP500 daily close/change_pct via yfinance (`build_sp500_daily_snapshots`)
2. Builds a `macro_provider(date) -> MacroSnapshot` callable that feeds `MarketContextReplay`
3. Runs `MarketContextReplay` + **real `SetupAGapReversion`** (from `config/decision_engine.yaml`)
4. Collects one Setup A entry per day (matching live behavior)
5. Simulates both **TrackAExit** (tuned trail_atr_mult=1.5, trail_activate=2.0) and **SetupTargetExit** (fixed stop from config)
6. Reports per-arm metrics with holdout split
7. Applies `min_volume=30` to suppress phantom bars (2-4 volume ticks that cause >2% fake moves)

Setup C entries are 0 because no real scheduled-event calendar is available in the backtest. This is a known limitation, not a code bug.

---

## Data Quality Note

The training data (2025-07-01 to 2026-01-14) contains ~52% sparse/phantom bars (volume ≤ 4), which the MarketContextReplay `min_volume=30` filter removes. After filtering, 1.7% of remaining bars still move >2% in the training period (vs 0.2% in holdout). The holdout data is substantially cleaner. Results from the training period should be interpreted cautiously; holdout results are more reliable.

---

## Re-Validation Results: TrackAExit vs SetupTargetExit on Real Setup A Signals

**Data**: `data/kospi200f_1m_ch_101S6000.csv` (101S6000 continuous futures, 2025-07-01 to 2026-04-23)  
**Setup A config**: min_sp500_gap=0.3%, min_kr_gap=0.2%, retrace=[0.20,0.70], time=[10,120]min  
**Split**: 2/3 train (2025-07-01 to 2026-01-14, 134 days), 1/3 holdout (2026-01-15 to 2026-04-23, 67 days)

### TRAIN (in-sample, 134 days)

| Metric | TrackAExit (1.5/2.0) | SetupTargetExit |
|--------|---------------------|-----------------|
| Trades | 18 | 18 |
| Win Rate | 50.0% | **66.7%** |
| Avg Return | -0.025% | **+0.493%** |
| Total PnL (pts) | -1.65 | **+42.65** |
| Total PnL (KRW) | -82,500 | **+2,132,500** |
| Sharpe | -1.181 | **+6.248** |
| MDD | 4.92% | 7.22% |
| Median Hold | 22.5 min | 13.5 min |
| Dominant exit | trail_stop (17/18) | target_reached (11/18) |

### HOLDOUT (out-of-sample, 67 days)

| Metric | TrackAExit (1.5/2.0) | SetupTargetExit |
|--------|---------------------|-----------------|
| Trades | 18 | 18 |
| Win Rate | **61.1%** | 44.4% |
| Avg Return | -0.090% | +0.003% |
| Total PnL (pts) | -13.05 | **+3.00** |
| Total PnL (KRW) | -652,500 | **+150,000** |
| Sharpe | -1.344 | **+0.056** |
| MDD | **16.67%** | 9.83% |
| Median Hold | 33.5 min | 13.0 min |
| Dominant exit | trail_stop (13), catastrophic (5) | stop_loss (10), target (8) |

---

## Key Findings

### 1. Real Setup A fires — blocker is resolved
The macro context path is working. Real `SetupAGapReversion` generates 18 trades in the holdout period vs. 0 without macro context. The gap reversion setup has adequate signal frequency for analysis.

### 2. TrackAExit (1.5/2.0) underperforms SetupTargetExit on REAL Setup A signals

This **contradicts the proxy backtest verdict** and constitutes a significant new finding:

- **Holdout**: TrackA Sharpe = -1.344 vs Target Sharpe = +0.056 (delta = -1.40). PnL delta = -16 pts.
- **Train**: TrackA Sharpe = -1.181 vs Target = +6.248 (delta = -7.43). PnL delta = -44 pts.

The trailing stop at 1.5×ATR activate=2.0 fires too early on mean-reverting Setup A moves:
- TrackA exits in median 22.5–33.5 min; Target exits in 13–13.5 min (target hit).
- TrackA median give-back = 0.37–0.62%: the trail fires, giving back gains.
- TrackA 5 catastrophic stops in holdout (vs 0 in Target): some moves that appear to reverse briefly hit catastrophic_stop=6.0×ATR.

### 3. The 1.5/2.0 tuning was optimized on the PROXY harness

The proxy backtest synthesized entries with **relaxed thresholds** (retrace [10-85%, gap ≥0.1%]) and matched the structural pattern — but not the exact signal timing of real Setup A. Real Setup A fires a narrower retrace band ([20-70%]) with tighter conditions. The exit behavior on real signals differs from the proxy population.

### 4. Setup C: 0 trades (calendar required)

Setup C (`SetupCEventReaction.check()`) requires `scheduled_events` with impact-tier ≤ 2 within the last 720 minutes. Without a real event calendar (e.g. US economic calendar: CPI, FOMC, NFP), Setup C cannot fire. To unblock Setup C backtesting, the operator must provide historical scheduled events (CSV/JSON) aligned to the dataset span.

---

## Recommendations

1. **Revisit TrackAExit parameters on real signals**: On mean-reverting Setup A, fixed-target exit (SetupTargetExit) outperforms the ATR trail. The 1.5/2.0 tuning may be better suited for trend-following positions than gap-reversion. Consider:
   - Tighter gap-fill target (SetupTargetExit already uses `target_gap_fill_ratio=0.9×ATR` from config)
   - Or a hybrid: SetupTargetExit for Setup A, TrackAExit for Setup C breakouts
2. **Setup C unblock path**: Provide a CSV of historical economic events (US/KR) covering the dataset span. `MarketContextReplay` already accepts `scheduled_events` via the `ScheduledEvent` dataclass.
3. **Data quality**: Regenerate the training parquet from the live mini futures feed rather than the 101S6000 stitched CSV, or raise the `min_volume` threshold further for train period analysis.

---

## Files

- Harness: `/home/deploy/project/kis_unified_sts/scripts/analysis/backtest_macro_setup_ac.py`
- JSON output: `/home/deploy/project/kis_unified_sts/.superpowers/sdd/bt-data-unblock-report-macro.json`
