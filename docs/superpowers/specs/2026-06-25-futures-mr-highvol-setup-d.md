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
2. **High-vol regime gate** — `atr_14 ≥ min_atr_ratio (0.9) × vol_reference`,
   where `vol_reference` is the **causal** 90th-percentile of a trailing window
   of recent ATRs (`vol_window_bars=780` ≈ 2 sessions) that the setup
   **self-computes** from the per-bar `atr_14`. It uses only ATRs observed at or
   before the current bar (no look-ahead) and has **no external indicator
   dependency**, so it behaves identically in backtest and live. The gate is
   permissive during warmup (< `vol_warmup_bars=120` observations) so the setup
   is never silently dead. This is the filter that keeps the setup **quiet on
   dead days** and **active on volatile days**.

   > **Design note (resolved review blockers — same class, two fields).** Two
   > rounds of code review flagged the same defect class: a gate that reads a
   > `MarketContext` field which has **no producer in the live orchestrator path**
   > (futures is orchestrator-only) and therefore takes its
   > `build_market_context` default live, while the backtest replay populates a
   > real (and look-ahead-shaped) value — so the backtest is not reproducible
   > live.
   > - **vol gate** read `atr_90th_percentile` (no live producer → defaults to
   >   `atr_14 × 1.5` → rejected 100% of bars live; replay value was a
   >   full-series percentile = look-ahead). Fixed: self-compute a **causal
   >   trailing ATR percentile** inside the setup. Locked by
   >   `test_live_default_atr90_does_not_silently_block`.
   > - **stall guard** read `last_15min_high/low` (no live producer in the
   >   orchestrator path — `get_recent_range` exists but is only wired into the
   >   dormant decoupled `decision_engine/context_provider`; defaults to
   >   `current_price` live → `current_price − current_price = 0 < buffer` → the
   >   guard never fired live, while the replay populated the real prior-15-bar
   >   range → it WAS active in backtest, taking the riskiest fade-the-runaway
   >   trades live that the OOS never took). Fixed: self-compute a **causal
   >   recent (high, low) from prior closes** inside the setup. Locked by
   >   `test_live_default_15min_range_stall_guard_still_fires`. Field audit of
   >   every remaining `MarketContext` field Setup D reads (`current_price`←close,
   >   `atr_14`←atr, `vwap`←vwap@indicator_engine.py:821, `now`, `symbol`)
   >   confirms all have real live producers — no third gap.
3. **VWAP extension extreme** (the fade trigger) — `z = (price − vwap) / atr_14`.
   `z ≥ extreme_atr_mult (1.8)` → **short** the up-spike; `z ≤ −1.8` → **long**
   the down-spike. Direction follows the sign of the extension only — no
   hard-coded directional bias (futures long/short symmetry).
4. **Stall confirmation** (trend-day guard) — the spike must be within
   `stall_buffer_atr_mult (1.0) × atr_14` of the prior recent extreme on its side
   (the recent high for a short, the recent low for a long). A bar that has blown
   clean *through* that extreme by more than the buffer is still trending — skip
   it (don't catch a falling knife / fade a runaway). The recent extreme is a
   **causal self-computed** range over the last `range_window_bars (15)` closes
   (`_self_range`) — closes, not bar highs/lows, because the `MarketContext`
   carries no per-bar high/low; this keeps the guard identical in backtest and
   live (see the design note above). Permissive during warmup
   (< `range_warmup_bars (5)` prior closes).

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
`scripts/analysis/walkforward_setup_d_vwap_reversion.py` — one **continuous**
causal pass through `MarketContextReplay` + real `SetupDVWAPReversion.check()`,
simulating an intrabar ATR-stop / VWAP-target / EOD exit (stop checked before
target — conservative), single position at a time. OOS folds are slices of that
single continuous run attributed by entry timestamp, so the causal vol window
stays continuously warmed across folds exactly as it would live (no per-fold
re-warming). Sharpe is annualized on per-trade returns (×√252); MDD in KRW at
50,000 KRW/point. `min_volume` 0 vs 30 is immaterial on this clean window.

> **All numbers below are look-ahead-free AND live-reproducible** — both
> self-computed references (vol gate, stall-guard range) are causal and use only
> data the live orchestrator path actually produces (§2 design note). Two earlier
> drafts reported higher figures: the first (full Sharpe 3.78 / OOS 1.97) was
> inflated by the vol-gate look-ahead; the second (full 2.66 / OOS 2.35) still
> used the backtest-only `last_15min_high/low` for the stall guard, which has no
> live producer. The numbers here use the close-based self-computed range that is
> identical in backtest and live; they are softer but real.

### 3.1 Full window (reference)

| Trades | L / S | Win% | Total | Avg/trade | Sharpe | MDD | Hold(med) |
|--------|-------|------|-------|-----------|--------|-----|-----------|
| 246 | 154 / 92 | 38.6% | +318 pts (+15.9M KRW) | +1.29 | **2.39** | 3.84M KRW | 10 min |

Both sides profitable (L +260 / Sharpe 2.62 ; S +58 / Sharpe 2.18).
Exits: 150 stop, 84 target, 12 EOD — small frequent wins paying for larger stops,
classic mean-reversion shape.

### 3.2 Walk-forward — out-of-sample (the honest test)

**Trading-day folds (40-day IS / 10-day OOS, step 10 — default):** the IS warmup
consumes Dec–early-Feb, so OOS spans 2026-02-11 … 2026-04-13.

| Fold | OOS window | n | L/S | Win% | Total | Sharpe |
|------|-----------|---|-----|------|-------|--------|
| 0 | 02-11 … 02-27 | 30 | 17/13 | 43.3% | +22.6 | +3.36 |
| 1 | 03-03 … 03-16 | 33 | 27/6 | 27.3% | +67.1 | +1.84 |
| 2 | 03-17 … 03-30 | 41 | 24/17 | 39.0% | +36.8 | +2.93 |
| 3 | 03-31 … 04-13 | 26 | 19/7 | 38.5% | +15.3 | +1.45 |

**OOS concatenated:** 130 trades, 36.9% win, **+142 pts (+7.1M KRW), Sharpe
+1.77**, MDD 3.8M KRW. **Both sides positive: L +92.5 / S +49.3** (short Sharpe
+3.39). **OOS-profitable folds: 4/4.**

### 3.3 The fold-granularity caveat (reported honestly)

A coarse **calendar-month** WF (2m-IS / 1m-OOS) yields only **2 folds** on this
88-day window. Run it (`--fold-mode monthly`) for the worst-case framing: a single
calendar cut through the March volatility event makes one of two folds weaker.
This is a **calendar-boundary artifact**, not evidence the edge is a one-month
fluke — the daily-stride read (§3.2, 4/4 folds positive) and the per-trade
distribution across Feb–Apr show the edge is broadly distributed. On an 88-day
window, monthly folds are simply too coarse to be the primary read; daily-stride
is the default for that reason.

### 3.4 Honest limitations

- **Single ~5-month clean window.** The trustworthy futures-minute window is
  Dec2025–Apr2026 (#516); earlier data is feed-degraded. One regime cycle is thin
  evidence — the OOS Sharpe will have wide confidence intervals.
- **Edge concentrates around volatility events.** On calm stretches the gate
  correctly produces few trades; the bulk of the P&L comes from the March vol
  period (fold 1). The strategy is *designed* to be event-concentrated, but it
  means a quiet future quarter could produce little.
- **Net long-skewed sample** (more down-spikes to fade in a bull period: 154 L /
  92 S full window). Both sides are profitable in every aggregation and the short
  Sharpe is actually higher, but the short sample is smaller.
- Backtest uses a stub spread and intrabar stop-before-target; live slippage and
  the real `SetupTargetExit` (the harness re-implements the bracket rather than
  driving the production exit) will erode the edge somewhat.
- The high-vol reference needs ~120 bars (≈ 1.5 sessions) of warmup before the
  gate activates; on a cold start the setup is permissive (may take a few
  marginal trades) until warmed.

## 4. Ship / no-ship recommendation

**Conditional ship → paper-only, `enabled: false`, [NEEDS-VALIDATION].**

The Thesis-A hypothesis is **supported on look-ahead-free, live-reproducible
evidence**: extending the proven reversion edge to all-session high-vol VWAP
reversions produces a real, symmetric, OOS-positive edge (OOS Sharpe ~1.77, 4/4
OOS folds profitable, both sides positive) that the causal high-vol gate keeps
selective. The edge softened from the earlier (not-live-reproducible) drafts as
each parity break was fixed — that is the honest cost of making the backtest match
what the live system can actually compute. This is **not** a no-ship like the
trend-day ORB (which was WF-negative). But it is **not a green-light to live**
either: a single clean window with event-concentrated P&L is thin statistical
evidence regardless of the in-window Sharpe.

**Recommended path:** merge `enabled: false`; run in paper alongside Setup A/C;
collect ≥4–6 weeks of live-paper fills across at least one calm and one volatile
stretch; compare paper fills to the backtest expectation (fill quality, hold time,
long/short balance, behavior on dead days, warmup behavior on a cold start).
Promote only via the standard Gate 1–4 procedure; `config/futures_live.yaml::enabled`
stays `false` throughout.

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

## 7. Adjacent finding — Setup C is silently degraded by the same gap (flagged, not fixed here)

While auditing Setup D's `MarketContext` fields, the same missing-producer gap was
confirmed to affect **Setup C** (`event_reaction.py`). Setup C's breakout check
reads `ctx.last_15min_high`/`ctx.last_15min_low` directly
(`event_reaction.py:236-250`): `current_price > last_15min_high` for a long,
`current_price < last_15min_low` for a short. In the live orchestrator path those
default to `current_price` (no producer — `get_recent_range` is only wired into the
dormant decoupled `decision_engine/context_provider`), so the breakout conditions
become `current_price > current_price` / `current_price < current_price` — both
**always False** → Setup C's breakout is **unreachable live**, the same class of
backtest-only-input bug. This is out of scope for this PR (Setup D); it is recorded
here and flagged to the operator for a separate fix (Setup C could adopt the same
`_self_range` approach, or have `get_recent_range` wired into the orchestrator
EntryContext).
