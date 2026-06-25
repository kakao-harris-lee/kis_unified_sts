# Futures daily/swing CTA momentum (THESIS B) — DATA-BLOCKED

- **Date:** 2026-06-25
- **Author:** backtest-engineer (R&D, isolated branch `feat/futures-cta-swing`)
- **Status:** **NO-SHIP — DATA-BLOCKED.** No strategy code is merged.
- **Symbol:** `101S6000` (continuous near-month KOSPI200 future)
- **Reproduce:** `.venv/bin/python scripts/analysis/cta_daily_data_probe.py`

## 1. Thesis under test

Daily/swing **time-series momentum** (managed-futures / CTA style): hold KOSPI200
futures across **days** in a confirmed trend regime, long/short symmetric, with
volatility-targeted sizing and a trailing exit. This is a **different timeframe**
than the already-falsified *intraday* trend-following (closed PR #529 ORB +
macd_ema/williams_r/momentum; doc `2026-06-25-futures-trend-day-strategy.md`).
Daily-bar momentum is a classic global index-futures edge and directly targets
the semiconductor-led secular trend, so it was worth a genuine, untested look.

The crux question — *does multi-day momentum persist in KOSPI200 index
futures?* — **cannot be answered with the data on hand.** Data availability was
the first gate, and it fails.

## 2. Data-availability gate (the binding constraint)

### 2.1 No daily futures partition exists

The Parquet store (`shared/storage/market_data_store.py`, root `data/market`) has:

| Asset | Timeframes present |
|-------|--------------------|
| stock | `daily/` + `minute/` |
| **futures** | **`minute/` ONLY** |

There is **no `daily` futures partition**. Daily bars must be *resampled* from
minute bars, so the daily history can be no longer than the minute history — and
is only as clean as the minute feed.

### 2.2 Resampled daily span and quality (`101S6000`)

Resampling all `101S6000` minute bars to KST-session daily OHLCV:

```
calendar span          : 2025-07-01  ->  2026-06-25   (~12 months)
calendar business-days : 258
trading sessions        : 244
  healthy (>= 300 min-bars/session): 106
  thin    (<  300 min-bars/session): 138
longest contiguous healthy run     : 31 sessions (2026-03-03 -> 2026-04-14)
```

Monthly health (a session needs ~390 one-minute bars for a full 09:00–15:45 KST
regular session; `<300` is thin/unreliable):

| Month | sessions | healthy | median bars |
|-------|---------:|--------:|------------:|
| 2025-07 | 23 | 0 | 67 |
| 2025-08 | 20 | 0 | 89 |
| 2025-09 | 22 | 0 | 131 |
| 2025-10 | 18 | 3 | 216 |
| 2025-11 | 20 | 2 | 251 |
| 2025-12 | 22 | 15 | 411 |
| 2026-01 | 21 | 18 | 411 |
| 2026-02 | 17 | 17 | 411 |
| 2026-03 | 21 | 21 | 411 |
| 2026-04 | 22 | 18 | 411 |
| 2026-05 | 19 | 8 | 203 |
| 2026-06 | 19 | 4 | 203 |

Only **Dec 2025 → Apr 2026** is densely healthy (~89 sessions). This matches the
known clean-window finding for the minute feed (`backtest-data-coverage-2026-06`,
`futures-minute-backfill-resilience`): the WS/REST feed only stabilized in
Dec 2025, and May–Jun 2026 degraded again.

### 2.3 Daily OHLC quality within the clean window is still poor

Even restricted to the Dec2025–Apr2026 healthy sessions, the resampled **daily**
bars are not trustworthy for a daily-bar strategy:

- Intraday range distribution (clean window): median 2.65%, but **5 sessions at
  8.7%–17.7%** range (e.g. 2026-03-10 at 17.66%). Day-over-day close returns
  include an **11.4% single-day move**. For a daily momentum signal that is
  noise, not regime.
- The session price *level* drifts ~420 (Jul 2025) → ~1380 (Jun 2026), a ~3.3×
  rise. This is either a genuine (violent) semis-led bull or residual phantom-
  track / OHLC-merge contamination of the kind `futures-minute-ohlc-dedup-fix`
  (PR #516) fixed only for *minute* bars over a 40-day window. **Either way it
  does not unblock the thesis** — a daily momentum model needs a longer, cleaner,
  level-verified series than exists here. (Not adjudicated; flagged for
  data-engineer / a vetted daily-settlement source.)

## 3. Why walk-forward is impossible (arithmetic, not opinion)

A daily TS-momentum strategy needs a lookback (typically 20–60 trading days) just
to emit its **first** signal, then post-warmup days to accumulate trades, then
that repeated across multiple folds with an out-of-sample holdout.

| Lookback | Post-warmup sessions within the longest clean run (31) |
|---------:|-------------------------------------------------------:|
| 20d | 11 |
| 40d | **−9** (cannot emit a single OOS signal) |
| 60d | **−29** |

- Total healthy daily sessions, even **non-contiguous**: **106**.
- Longest **contiguous** clean run: **31** sessions (~6 weeks).
- Standard CTA walk-forward needs roughly **≥750 daily bars (3y)** for even three
  folds; **≥1250 (5y)** is typical. We have, at best, ~one quarter of usable,
  partly-contaminated data, and not even contiguously.

A single fold with a 40-day lookback produces a **negative** number of
out-of-sample sessions. There is no honest WF to run. Any per-fold Sharpe/MDD I
could print would be a fabrication on thin data, which the task explicitly
forbids.

## 4. Verdict — DATA-BLOCKED (not ship, not no-ship)

- This is distinct from THESIS A (intraday trend, *falsified* on adequate data).
  THESIS B is **untested** — the hypothesis "multi-day momentum persists in
  KOSPI200 futures" remains **open**, because the local data cannot test it.
- **Recommendation:** do **not** implement a standalone daily CTA-momentum
  strategy now. No strategy/registry/config code is added in this PR.

## 5. What would unblock it (handoff)

1. **Vetted daily-settlement KOSPI200 futures history** (continuous/back-adjusted
   near-month, ≥3–5y, exchange settlement prices — not minute resamples) loaded
   into a real `data/market/futures/daily/` partition. KRX publishes daily
   futures settlement; KIS daily-candle endpoints exist for futures. This is a
   **data-engineer** task, not a strategy task.
2. **Level/roll verification** of the existing series (adjudicate the 420→1380
   drift: real bull vs. contamination), so any daily bars are trustworthy.
3. Once ≥3y clean daily bars exist, re-run the WF harness
   (`scripts/analysis/orb_trend_day_walkforward.py`, adapted to daily cadence —
   mind the `DecisionCadenceGate` / `mtf_base` footgun that silently yields
   phantom 0-trade results) with a Donchian/MA-cross/TS-momentum signal +
   vol-target sizing + trailing exit, long/short symmetric, plus EOD-proxy PnL
   counterfactual for the gate.

## 6. Artifacts in this PR

- `scripts/analysis/cta_daily_data_probe.py` — reusable, hermetic data-
  availability probe (span / health / clean-run / level-drift). Re-runnable as
  the gate before any future daily-futures R&D.
- `tests/unit/analysis/test_cta_daily_data_probe.py` — hermetic unit tests on a
  synthetic minute fixture (no real data, no network).
- This document.

No trading code, config, or registry entry is added. `enabled: false` is moot —
there is nothing to enable.
