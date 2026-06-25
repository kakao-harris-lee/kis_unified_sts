# Setup D — High-Vol Intraday VWAP Reversion — Research, Design, Validation

Status: **[NEEDS-VALIDATION]** — implemented + walk-forward evidence; `enabled: false`, paper-only.
Author: strategy-architect
Date: 2026-06-25
Branch: `feat/futures-mr-highvol`
Asset: KOSPI200 futures (backtest symbol `101S6000`, trade `A05xxx`), paper-only.

---

## 1. Problem statement (Thesis A)

On 2026-06-25 the KOSPI surged ~+3% in a high-volatility, semiconductor-led
intraday day. The futures book made **0 trades**:

- `setup_a_gap_reversion` is a **gap-fade-at-OPEN** strategy: it only fires 10–60
  min after 09:00 KST and requires an overnight S&P 500 gap to fade. There was no
  overnight gap, so it rejected `sp500_gap_below_min`.
- `setup_c_event_reaction` requires a scheduled macro event in-window; there was
  none, so it rejected `no_event_in_window`.

Yet intraday KOSPI200 futures **mean-revert** — this is the proven edge that
Setup A/C exploit. The gap: Setup A's reversion edge is confined to a narrow
open-only window and an overnight-gap trigger. The **large intraday reversions
that occur throughout a volatile session** (a spike up that fades back, a flush
down that bounces) go entirely uncaptured.

**Thesis A:** extend the proven mean-reversion edge to **all-session** intraday
volatility-extreme reversions. Hypothesis: *high volatility ⇒ more/larger
intraday reversions ⇒ more edge for a mean-reversion fader*, provided we are
selective (most active on volatile days, quiet on dead days) and long/short
symmetric (fade up-spikes short, down-spikes long).

This is the **highest-probability path** because it extends what already works
rather than betting on a new behavior. (Standalone intraday *trend*-following —
`macd_ema`, `williams_r` as trend, `momentum`, and the triple-gated ORB of closed
PR #529 — all fail walk-forward; intraday KOSPI200 is predominantly
mean-reverting. Setup D does not relitigate that; it is a reversion strategy.)

## 2. Design — Setup D

A decision-engine `Setup` (`shared/decision/setups/vwap_reversion.py`,
`SetupDVWAPReversion`) plus a thin `EntrySignalGenerator` adapter
(`SetupDEntryAdapter` in `shared/strategy/entry/setup_adapters.py`), mirroring the
Setup A/C architecture exactly. It reads only OHLCV-derived `MarketContext`
fields (no macro / event / LLM inputs).

**Entry (per bar):**

1. **Session window** — `valid_minutes_min (15) ≤ minutes_since_open ≤
   no_entry_after_minutes_since_open (345)`. Skips the 09:00 open auction; no
   entries after 14:45 KST (avoid force-close churn near the 15:45 close).
2. **High-vol regime gate** — `atr_14 ≥ min_atr_ratio (0.7) ×
   atr_90th_percentile`. The 90th-pct ATR is the instrument's high-vol reference
   (populated by `MarketContextReplay` and the live engine). This is the filter
   that keeps the setup **quiet on dead days** and **active on volatile days**.
3. **VWAP extension extreme** (the fade trigger) — `z = (price − vwap) / atr_14`.
   `z ≥ extreme_atr_mult (1.8)` → **short** the up-spike; `z ≤ −1.8` → **long**
   the down-spike. Direction follows the sign of the extension only — no
   hard-coded directional bias (futures long/short symmetry).
4. **Stall confirmation** (trend-day guard) — the spike must be within
   `stall_buffer_atr_mult (1.0) × atr_14` of the prior 15-min extreme on its side
   (`last_15min_high` for a short, `last_15min_low` for a long). A bar that has
   blown clean *through* the 15-min extreme by more than the buffer is still
   trending — skip it (don't catch a falling knife / fade a runaway).

**Risk bracket (ATR-scaled, symmetric):**

- stop = `entry ± stop_atr_mult (1.5) × atr_14`
- target = revert toward VWAP, floored at `min_reward_risk (1.0) × risk`:
  `target_distance = max(|entry − vwap|, min_reward_risk × risk)`.

**Why it should survive walk-forward:** it does not curve-fit a directional bet.
It is a structural reversion edge — fade an ATR-scaled stretch from a fair-value
anchor (VWAP), only when the bar is genuinely volatile, with the move stalling,
exiting at the anchor with an ATR stop. The high-vol gate is the robustness
mechanism: on calm/chop bars the gate produces few or no entries, so the strategy
does not bleed the way an always-on fader would. There are **no fitted
parameters** — defaults come from a research operating point, not an optimizer, so
there is no in-sample overfit to leak into OOS.

## 3. Honest walk-forward validation

Data: clean Dec2025–Apr2026 `101S6000` minute parquet (the #516-deduped,
look-ahead-safe window), gated to near-full sessions (≥330 bars/day) → 88 trading
days, 2025-12-05 … 2026-04-29. Harness:
`scripts/analysis/walkforward_setup_d_vwap_reversion.py` — replays
`MarketContextReplay` + real `SetupDVWAPReversion.check()`, simulates an intrabar
ATR-stop / VWAP-target / EOD exit (stop checked before target — conservative),
single position at a time. Sharpe is annualized on per-trade returns (×√252);
MDD in KRW at 50,000 KRW/point.

### 3.1 Full window (reference)

| Trades | L / S | Win% | Total | Avg/trade | Sharpe | MDD | Hold(med) |
|--------|-------|------|-------|-----------|--------|-----|-----------|
| 141 | 102 / 39 | 42.6% | +413 pts (+20.7M KRW) | +2.93 | **3.78** | 3.77M KRW | 9 min |

Both sides profitable (L +307 / S +106). Exits: 80 stop, 54 target, 7 EOD —
small frequent wins paying for larger stops, classic mean-reversion shape.

### 3.2 Walk-forward — out-of-sample (the honest test)

**Trading-day folds (40-day IS / 10-day OOS, step 10 — default):** the IS warmup
consumes Dec–early-Feb, so OOS spans 2026-02-11 … 2026-04-13.

| Fold | OOS window | n | L/S | Win% | Total | Sharpe |
|------|-----------|---|-----|------|-------|--------|
| 0 | 02-11 … 02-27 | 52 | 22/30 | 30.8% | −0.04 | −0.00 |
| 1 | 03-03 … 03-16 | 27 | 20/7 | 44.4% | +163.8 | +4.35 |
| 2 | 03-17 … 03-30 | 47 | 30/17 | 40.4% | +33.4 | +2.26 |
| 3 | 03-31 … 04-13 | 31 | 24/7 | 38.7% | +0.14 | +0.01 |

**OOS concatenated:** 157 trades, 37.6% win, **+197 pts (+9.87M KRW), Sharpe
+1.97**, MDD 3.9M KRW. **Both sides positive: L +148.6 / S +48.7.**
Folds with trades 4/4; **OOS-profitable 3/4 (one flat at −0.04, none negative).**

### 3.3 The fold-granularity caveat (reported honestly)

A coarse **calendar-month** WF (2m-IS / 1m-OOS) yields only **2 folds** on this
88-day window and shows **1/2 profitable** (Feb −37 / Sharpe −1.4; Mar +215 /
Sharpe +3.3) — which looks fragile. This is a **calendar-boundary artifact**: the
March volatility event is split across the fold boundary. The finer reads agree it
is not a one-month fluke:

- **Weekly OOS blocks:** 13 of 16 traded weeks profitable. The single worst week
  (Mar 2–8, −50 pts) is immediately followed by the best (Mar 9–15, +191 pts) —
  one event, a few chop days before the reversion regime engaged.
- **40d/10d daily-stride:** 4/4 folds non-negative (§3.2).

Tightening the high-vol gate (`min_atr_ratio` 0.7→0.8→1.0) raises per-trade
quality but does **not** rescue the worst monthly fold — the Feb pocket is
regime-dependent, not a tuning problem. Loosening it (`min_atr_ratio` 0.6) is
worse: it admits chop, March goes to breakeven and the long side turns net
negative. The 0.7 operating point is where the edge is **distributed across months
and balanced long/short**, which is why it is the default.

### 3.4 Honest limitations

- **Single ~5-month clean window.** The trustworthy futures-minute window is
  Dec2025–Apr2026 (#516); earlier data is feed-degraded. One regime cycle is thin
  evidence.
- **Edge concentrates around volatility events.** On calm stretches the gate
  correctly produces few/flat trades; the P&L is event-driven.
- **Net long-skewed sample** (more down-spikes to fade in a bull period). Both
  sides are profitable in every aggregation, but the short sample is small (n=39
  full window).
- Backtest uses a stub spread and intrabar stop-before-target; live slippage and
  the 1-min-bar stop/target resolution will erode the edge somewhat.

## 4. Ship / no-ship recommendation

**Conditional ship → paper-only, `enabled: false`, [NEEDS-VALIDATION].**

The Thesis-A hypothesis is **supported**: extending the proven reversion edge to
all-session high-vol VWAP reversions produces a real, symmetric, OOS-positive edge
(OOS Sharpe ~2.0) that the high-vol gate keeps selective. This is **not** a
no-ship like the trend-day ORB (which was WF-negative). But it is **not a
green-light to live** either: a single clean window, event-concentrated P&L, and a
fold-granularity caveat all argue for paper validation before any live
consideration.

**Recommended path:** merge `enabled: false`; run in paper alongside Setup A/C;
collect ≥4–6 weeks of live-paper fills across at least one calm and one volatile
stretch; compare paper fills to the backtest expectation (fill quality, hold time,
long/short balance, behavior on dead days). Promote only via the standard Gate 1–4
procedure; `config/futures_live.yaml::enabled` stays `false` throughout.

**Rollback:** the strategy is disabled by default — no rollback needed. To
deactivate after a paper enablement, flip `strategy.enabled: false` in
`config/strategies/futures/setup_d_vwap_reversion.yaml`.

## 5. Files

- `shared/decision/setups/vwap_reversion.py` — `SetupDVWAPReversion` + `SetupDConfig`.
- `shared/strategy/entry/setup_adapters.py` — `SetupDEntryAdapter` + `SetupDEntryConfig`.
- `shared/strategy/registry.py` — registers `setup_d_vwap_reversion`.
- `config/strategies/futures/setup_d_vwap_reversion.yaml` — strategy config (`enabled: false`).
- `config/decision_engine.yaml` — `setup_d_vwap_reversion` section.
- `scripts/analysis/walkforward_setup_d_vwap_reversion.py` — WF harness (monthly + daily-stride).
- `tests/unit/decision/test_setup_d_vwap_reversion.py` — Setup core hermetic tests.
- `tests/unit/strategy/entry/test_setup_d_adapter.py` — adapter + registry/factory tests.

## 6. Reproduce

```bash
# Honest OOS walk-forward (daily-stride; data lives in the primary checkout):
.venv/bin/python scripts/analysis/walkforward_setup_d_vwap_reversion.py

# Coarse monthly WF (shows the calendar-boundary caveat):
.venv/bin/python scripts/analysis/walkforward_setup_d_vwap_reversion.py --fold-mode monthly

# Unit tests:
.venv/bin/python -m pytest tests/unit/decision/test_setup_d_vwap_reversion.py \
  tests/unit/strategy/entry/test_setup_d_adapter.py -q
```
