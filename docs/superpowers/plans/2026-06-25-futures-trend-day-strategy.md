# Futures Trend-Day Strategy — Research, Design, and Validation

Status: **[NEEDS-VALIDATION]** — prototype + walk-forward evidence pending review.
Author: strategy-architect
Date: 2026-06-25
Branch: `feat/futures-trend-day-strategy`
Asset: KOSPI200 futures (backtest symbol `101S6000`, trade `A05xxx`), paper-only.

---

## 1. Problem statement

On 2026-06-25 the KOSPI cash index surged ~+3% in a domestic intraday **trend** day.
The futures book made **0 trades**:

- `setup_a_gap_reversion` rejected `sp500_gap_below_min(0.10<0.3)` — US overnight was
  flat, so there was no overnight gap to fade.
- `setup_c_event_reaction` rejected `no_event_in_window` — no scheduled macro event.

Both live setups are **mean-reversion / event** strategies. Neither targets a
domestic intraday trend that originates *after* the open with no overnight gap and no
scheduled catalyst. On such days the book captures nothing.

The gap in the portfolio is real: there is **no strategy whose edge is a sustained
intraday directional move**.

## 2. The hard constraint (why naive trend-following is banned)

This is not a greenfield problem. Prior futures trend strategies **all failed
walk-forward**:

| Strategy | WF outcome |
|----------|-----------|
| `macd_ema_crossover` | ~ -106% recent |
| `williams_r` (as trend) | ~ -14 |
| `momentum` | bankrupt |

Root cause (validated repeatedly in this repo): **intraday KOSPI200 futures are
predominantly mean-reverting.** Most days are chop. A trend-follower that takes a
breakout every day bleeds on the many chop days (whipsaw: buy the breakout, price
reverts, stop out; repeat). The rare strong-trend day's gains do not pay for the
steady chop-day losses.

**Therefore the design thesis cannot be "follow trends." It must be: stay flat on
chop days, and only arm directional entries on the rare days that are confirmed to be
trending.** The GATE — what keeps us flat on chop days — is the entire ballgame. A
strategy that cannot demonstrate it avoids the chop-day bleed is not worth shipping.

## 3. Research — candidate approaches

### 3.1 Regime-gated directional entry (chosen family)

Idea: compute a *trend-confirmation* signal and only allow entries when it fires.
The question is **what makes a robust gate**. Options surveyed:

- **MFI regime label (BULL_STRONG / BEAR_STRONG).** Available live and in backtest
  via `MarketClassifier` (the adapter injects `market_state` into `EntryContext`).
  *Weakness:* MFI is a bounded oscillator centered at 50; its "strong" thresholds
  (≥49 / <34) flicker intrabar and do not distinguish a *persistent directional drift*
  from a volatile-but-flat day. Used **alone** it is a weak gate. Used as **one of
  several confirmations** it adds value (it captures money-flow direction).

- **Realized-trend / efficiency filter.** The crux. A genuine trend day has high
  *directional efficiency*: net displacement is large relative to the path length
  travelled. Chop days have low efficiency (lots of motion, little net move). This is
  exactly the discriminator we need and it is **not** something a price oscillator
  captures. Concretely:
  - **Opening-range displacement**: after an opening window (e.g. first 30–60 min),
    measure how far price has moved from the day's open in ATR units. A real trend day
    establishes a directional bias early.
  - **Trend efficiency ratio (Kaufman ER)** over a rolling window:
    `|close_t − close_{t−n}| / Σ|close_i − close_{i−1}|`. ER → 1 means clean trend,
    ER → 0 means chop. This is the single most direct "is today trending?" measure.
  - **Vol-expansion gate**: trend days expand range (ATR rising, bar ranges above a
    rolling baseline). Chop days are range-bound. Gating on vol-expansion filters out
    the low-energy days where breakouts fail.

- **Daily directional bias (LLM).** `trading:futures:daily_bias` would give a
  once-a-day long/short/flat call. *Currently null* (separate investigation) so it
  **cannot be the primary gate today**. We keep an optional hook but the gate must
  stand on price/vol structure alone.

### 3.2 Opening-range breakout + trend confirmation (chosen mechanism)

Opening-range breakout (ORB) is the canonical trend-day entry: define the high/low of
an opening window, enter on a *confirmed* break of that range in the break direction.
On its own ORB is a naive breakout (it triggers every day, including chop days where
the break fails). **ORB only survives when it is gated** by trend-confirmation
(efficiency + vol-expansion + direction agreement). That combination is the design.

### 3.3 Momentum gated by daily bias

Rejected as primary: daily bias is null today, and pure momentum gated only by a
direction label is what already failed WF. Folded in as an *optional* alignment
confirmation (when bias is available it must agree; when null it is permissive).

## 4. Chosen design — `orb_trend_day`

A registry strategy composed of a new entry + reused/extended exit, **long/short
symmetric**, config-driven, KST-native, paper-only, `enabled: false` by default.

### 4.1 Entry: `OpeningRangeBreakoutTrendEntry`

Per closed decision-bar (cadence-gated to N-minute bars), in order — **every gate
must pass**; any failure → no signal (records a reject reason for observability):

1. **Session-time gate (KST).**
   - Only after the opening range is fully formed:
     `minutes_since_open >= opening_range_minutes` (default 30).
   - No new entries after `no_entry_after_minutes` (default 300 = 14:00 KST) — late
     trends have insufficient runway and risk holding into the close.

2. **Opening-range construction.** Track per-day `or_high` / `or_low` over the first
   `opening_range_minutes` from 09:00 KST. Frozen once the window closes. (Computed
   incrementally from the bar stream — no look-ahead.)

3. **Vol-expansion gate (energy filter).** Require the opening-range height to be a
   real move, not noise: `(or_high − or_low) >= min_or_atr_mult * atr`. Days that open
   dead-flat are skipped. Also require current `atr` (normalized) above
   `min_atr_norm` so we are not trading a comatose session.

4. **Trend-efficiency gate (the crux).** Compute Kaufman efficiency ratio over the
   last `efficiency_window` bars. Require `ER >= min_efficiency` (default 0.35). This
   is what keeps us flat on chop days: a choppy session cannot clear the ER bar even
   if price pokes through the opening range. **This is the gate whose job is to reject
   the many chop days that killed prior trend strategies.**

5. **Breakout trigger + direction.**
   - Long: `close > or_high + breakout_buffer_atr_mult * atr`.
   - Short: `close < or_low − breakout_buffer_atr_mult * atr`.
   - The buffer requires a *decisive* break (filters marginal pokes).

6. **Direction-agreement confirmations (must all agree with the break direction):**
   - **MFI regime**: long requires `market_state` not in `long_blocked_states`
     (default the two BEAR states); short requires not in `short_blocked_states`
     (default the two BULL states). I.e. do not fade money-flow.
   - **MACD slope**: long requires `macd_hist > 0`; short requires `macd_hist < 0`.
   - **Daily bias (optional)**: if `daily_bias_filter_enabled` and a non-flat bias is
     present in `trading:futures:daily_bias`, it must match; if null/flat → permissive
     (does not block) so the strategy is usable today.

7. **One-entry-per-day-per-direction** guard (avoid re-entering the same broken range
   repeatedly → the whipsaw failure mode).

On fire, emit a `Signal` with `signal_direction`, `stop_loss` / `take_profit` derived
from ATR (see exit), `entry_atr`, and confidence scaled by ER and break decisiveness.

### 4.2 Exit: `TrendTrailExit` (extends the ATR-trailing pattern)

A trend strategy must **let winners run** (the whole point is the rare big day) while
cutting losers fast. Symmetric long/short. Priority cascade:

1. **Catastrophic / hard stop**: `stop_atr_mult * entry_atr` from entry (default 1.5).
2. **Breakeven ratchet**: once `+1.0 * entry_atr` in favor, move stop to entry.
3. **ATR trailing stop**: once `trail_activation_atr` reached, trail by
   `trail_atr_mult * atr` from the best price (high since entry for long, low for
   short). This is what captures the trend-day runner.
4. **EOD flatten (KST)**: futures are intraday; flatten by `eod_flatten_time`
   (default 15:15 KST). This is futures-only and does **not** violate the stock
   no-blanket-EOD rule (that rule is stock-only; futures are intraday by nature and
   already day-bounded via `close_on_day_change` in the engine).

For the **backtest** we can also enforce the same stop/trailing/EOD via the engine's
`RiskConfig` (`use_atr_stop`, `trailing_stop_*`, `force_close_time`,
`close_on_day_change`) to keep the harness simple and the exit honest; the registry
`TrendTrailExit` is the live path and is unit-tested directly.

### 4.3 Position sizing

`fixed` sizer with 1 contract for paper (or `fixed_fractional_futures` if risk-scaled
sizing is desired later). Paper-only; no live sizing decisions in this PR.

### 4.4 Why this *should* survive WF where naive trend died

The failure mode of prior trend strategies was **chop-day bleed**. This design
attacks it on three independent axes that all must agree before a single contract is
risked:

1. **Trend-efficiency gate (ER ≥ threshold)** — directly measures "is the path
   directional?" Chop days fail here regardless of price level. This is the axis that
   prior MACD/Williams trend strategies *lacked entirely* — they entered on an
   oscillator cross with no chop filter.
2. **Vol-expansion gate** — a breakout into a contracting/flat range is the textbook
   false breakout; we require the opening range itself to be a real ATR-scaled move
   and ATR to be alive.
3. **Decisive break + direction agreement (MFI + MACD slope, optional bias)** —
   removes marginal pokes and counter-flow entries.

Plus a structural guard (one entry per direction per day) that caps the whipsaw count
that bankrupted `momentum`.

**The honest risk:** triple-gating may make the strategy trade so rarely that the
sample is tiny and the edge unprovable, or the gates may not generalize across folds.
That is exactly what the walk-forward must reveal. If WF shows negative or
statistically-empty OOS, **the recommendation is do-not-ship** and the rigorous
negative result stands as the deliverable. We do not dress up a loser.

## 5. Config schema (`config/strategies/futures/orb_trend_day.yaml`)

```yaml
strategy:
  name: orb_trend_day
  asset_class: futures
  enabled: false            # paper-only, opt-in; never auto-enabled
  timeframe: "5min"
  description: Regime/efficiency-gated opening-range breakout trend-day capture.
  entry:
    type: orb_trend_day
    params:
      timeframe_minutes: 5
      opening_range_minutes: 30
      no_entry_after_minutes: 300        # 14:00 KST
      min_or_atr_mult: 0.8               # opening-range height >= 0.8 ATR
      min_atr_norm: 0.0008               # session must be alive
      efficiency_window: 12              # ~60 min on 5m bars
      min_efficiency: 0.35               # Kaufman ER gate (the crux)
      breakout_buffer_atr_mult: 0.25
      use_mfi_gate: true
      long_blocked_states: ["BEAR_STRONG", "BEAR_MODERATE"]
      short_blocked_states: ["BULL_STRONG", "BULL_MODERATE"]
      use_macd_slope_gate: true
      daily_bias_filter_enabled: false   # null today; permissive hook
      market_open_hour: 9
      market_open_minute: 0
      allow_short: true                  # long/short symmetry
  exit:
    type: trend_trail_exit
    params:
      atr_period: 14
      stop_atr_mult: 1.5
      breakeven_activation_atr: 1.0
      trail_activation_atr: 1.5
      trail_atr_mult: 2.0
      eod_flatten_enabled: true
      eod_flatten_hour: 15
      eod_flatten_minute: 15
  position:
    type: fixed
    params:
      fixed_quantity: 1
      max_positions: 1
```

## 6. Validation plan

- **Hermetic unit tests**: chop session → no entry (ER gate rejects); clean trend
  session → entry fires in correct direction; long/short symmetry; vol-expansion
  reject; one-entry-per-direction guard; exit trailing/EOD symmetry.
- **Backtest** `101S6000` minute data, **clean window Dec 2025–Apr 2026** only.
- **Walk-forward**: rolling IS/OOS folds (e.g. 2-month IS / 1-month OOS) across the
  window. Per-fold Sharpe, MDD, win-rate, trades. Promotion gate idea:
  OOS Sharpe ≥ 0.5 × IS Sharpe AND OOS not net-negative across folds.
- Artifacts (numbers, per-fold table) appended to **Section 7** below.

## 7. Results

Validation harness: `scripts/analysis/orb_trend_day_walkforward.py` (same path the
live registry uses: `BacktestStrategyAdapter` → `BacktestEngine`). Data: 101S6000
minute bars, **38,181 bars over 102 trading days, Dec 2025 – Apr 2026** (clean
window). Engine risk layer disabled; stops/trailing/EOD come from `TrendTrailExit`;
`close_on_day_change=True` (intraday futures). Point value 50,000 KRW.

### 7.0 Wiring note (a bug that was caught, not papered over)

The first run produced **0 trades**. Diagnosis showed `generate()` was never called:
a `timeframe_minutes>1` strategy is silently never evaluated unless
`required_indicators` declares an `mtf_base_{N}m` key (the `DecisionCadenceGate`
queries a timeframe the engine never built → permanent HOLD). Fixed by declaring
`mtf_base_5m` (the williams_r convention). After the fix the strategy trades ~1×/day
bidirectionally. **This matters: a 0-trade result would have been a false negative.**
The numbers below are from the *working* strategy.

### 7.1 Full-window backtest (Dec 2025 – Apr 2026)

| Variant | Trades | Return | Sharpe | MDD | Win-rate |
|---------|-------:|-------:|-------:|----:|---------:|
| both sides | 93 | +0.57% | +0.48 | 1.51% | 36.6% |
| long-only  | 55 | +0.20% | +0.32 | — | 34.5% |
| short-only | 38 | +0.37% | +0.58 | — | — |

Exit mix (both sides): 49 trailing-stop, 44 hard-stop. Both directions trade — the
long/short symmetry is intact. Marginally positive, but economically thin.

### 7.2 Walk-forward (rolling, IS=2mo / OOS=1mo)

| Fold | IS window | IS Sharpe | IS trades | OOS window | OOS return | OOS Sharpe | OOS win | OOS trades |
|------|-----------|----------:|----------:|------------|-----------:|-----------:|--------:|-----------:|
| 1 | Dec–Jan | +1.32 | 36 | Feb | −0.54% | −2.66 | 33.3% | 18 |
| 2 | Jan–Feb | +0.95 | 40 | Mar | −0.35% | −1.20 | 42.9% | 21 |
| 3 | Feb–Mar | −0.18 | 39 | Apr | +0.84% | +3.33 | 47.1% | 17 |

**Aggregate OOS: net −0.06%, mean Sharpe −0.18, positive folds 1/3, 56 OOS trades.**

The signature is textbook overfitting: folds 1–2 have *good* in-sample Sharpe
(+1.32, +0.95) that **inverts** out-of-sample (−2.66, −1.20). Fold 3 is the mirror
(bad IS, good OOS) — i.e. the IS→OOS relationship is noise, not a transferable edge.

### 7.3 Parameter-sensitivity sweep (OOS robustness)

To rule out "wrong knob," the gate/exit params were swept (OOS aggregate):

| Sweep | Best OOS net | Best mean Sharpe | Notes |
|-------|-------------:|-----------------:|-------|
| `min_efficiency` 0.25/0.35/0.45/0.55 | +0.07% (0.25) | +0.16 (0.25) | tightening the GATE makes it **worse** (0.55 → −1.20%) |
| `breakout_buffer_atr_mult` 0.0/0.25/0.5 | −1.18% | −1.46 | no setting positive |
| `trail_atr_mult` 1.5/2.0/3.0 | −1.09% | −1.36 | no setting positive |
| `no_entry_after_minutes` 180/240/300 | (all ≤ break-even) | — | runway does not help |
| long-only / short-only | −0.02% / — | −0.26 | neither side carries it |

**The crux gate does not work as theorized.** If the efficiency gate isolated a
profitable trend-day subset, tightening `min_efficiency` would *improve* OOS. It does
the opposite. The best OOS result across the entire sweep (+0.07% net, Sharpe +0.16
over 5 months) is economically indistinguishable from zero before realistic costs.

## 8. Ship / No-ship recommendation

**NO-SHIP.** Recommendation: do not enable `orb_trend_day` for paper promotion.

Rationale — the strategy fails the paper-promotion gate on the only metric that
matters (out-of-sample robustness):

- OOS net ≈ 0% / slightly negative; mean OOS Sharpe −0.18; majority of folds losing.
- Strong IS Sharpe that inverts OOS = overfitting, not edge.
- The result is **robust across the full parameter sweep** — it is not a tuning
  artifact. Tightening the central efficiency gate makes OOS worse, falsifying the
  design thesis that the gate isolates profitable trend days.
- This reproduces the established repo finding: intraday KOSPI200 futures are
  predominantly mean-reverting; even a triple-gated (efficiency + vol-expansion +
  direction-agreement) opening-range breakout cannot extract a durable directional
  edge. The 2026-06-25 trend day is real, but such days are too rare and too hard to
  pre-identify intraday for a breakout to pay for the chop-day bleed across folds.

**What is worth keeping** (the deliverable is not wasted):

1. The negative result itself — a rigorous, reproducible confirmation that gated
   trend-following still fails WF here, with the harness to re-test future variants.
2. The reusable machinery: `TrendTrailExit` (a clean long/short ATR-trailing +
   breakeven + intraday-EOD exit) is generally useful and well-tested; the Kaufman
   efficiency-ratio gate and ORB construction are reusable building blocks.
3. The wiring lesson (`timeframe_minutes` ⇒ `mtf_base_{N}m` required key) is captured.

**If revisited**, the more promising direction is not "trade the trend day" but
"size/relax mean-reversion on confirmed trend regimes" — i.e. feed the
efficiency/regime signal into the *existing* Setup A/C as a context modifier rather
than building a standalone breakout. That keeps the mean-reversion edge that actually
works while not fading the rare strong-trend day. This is a separate piece of work and
is NOT part of this PR.

The code ships **disabled** (`enabled: false`) and behind the registry as a tested,
documented building block; it must not be promoted to paper on these numbers.
