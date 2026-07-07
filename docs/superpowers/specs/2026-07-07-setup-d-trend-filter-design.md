# Setup D Trend Filter — Design

- Date: 2026-07-07
- Status: implemented + validated — **ships OFF by default** (acceptance criteria
  for enabling NOT met on the available data; see Validation Results)
- Branch: `feat/setup-d-trend-filter`
- Owner: futures strategy

## Motivation

On 2026-07-07, KOSPI200 futures (`A01609`) fell −4.9% in a steady one-way
downtrend. `setup_d_vwap_reversion` (a VWAP mean-reversion setup) entered **long
13 straight times**, fading the down-move: 11 stop-losses, 2 targets, net
≈ −8.4 index points (−0.6%), win rate 15% (2/13).

Root cause: the setup has no effective trend-day shutoff on the counter-trend
side. Its existing trend guards — `stall_buffer` (15-bar range) and
`reversal_confirm` — operate on a ~15-minute window, too myopic to detect an
all-day one-way trend, so shallow dead-cat bounces repeatedly satisfy them.
`long_blocked_regimes` is empty and the MFI-based regime label whipsawed
(BULL_STRONG 184 / BEAR 180 across the day), so it cannot serve as a trend
filter.

The two winning longs occurred at the down-move's **climax** (10:40 and 14:28),
so a naive counter-trend block would also veto them. The design must block
*shallow dip-buys into a trend* while preserving *climactic mean-reversion
flushes*.

## Approach (selected: slope-gate + exhaustion exception)

Add a causal, self-computed **session-VWAP-slope trend gate** to
`SetupDVWAPReversion.check()`. Block a counter-trend fade when the trend is
strong, **unless** the VWAP stretch is climactic (a higher `z` bar than the
normal fade trigger).

Rejected alternatives:
- **Hard counter-trend block (no exception):** simplest, but sacrifices the
  climactic reversals that are the setup's actual edge.
- **Trend-scaled sizing:** softer, but adaptive sizing already halved size to
  0.5× today and the churn continued — a soft knob does not stop the bleed.

## Mechanism

All logic lives inside `SetupDVWAPReversion.check()`
(`shared/decision/setups/vwap_reversion.py`). No new market-view (`ctx`) fields,
so backtest and live behave identically.

### Trend metric (causal, session-anchored)

- New rolling deque `_vwap_window` (maxlen `trend_window_bars`, default 30) of
  session VWAP values.
- **Session reset** keyed on `ctx.now.date()` (KST-native; futures is day-only,
  so date boundary = session boundary). On a new date, clear `_vwap_window`
  before appending. This prevents the overnight gap from corrupting the slope.
- `trend_score = (vwap_now − vwap_oldest) / atr_14` — net VWAP drift over the
  window, in ATR units. The current VWAP is appended **after** the read
  (strictly causal, matching the existing ATR/close windows).
- Warmup: fewer than `trend_warmup_bars` (default 10) observations ⇒ gate is
  **permissive** (never silently dead).

### Gate logic (symmetric)

Applied after the fade direction is determined (step 4 in `check()`), before the
risk bracket:

```
counter_trend = (direction == "long"  and trend_score < 0) or \
                (direction == "short" and trend_score > 0)
if trend_filter_enabled and counter_trend and abs(trend_score) >= trend_block_threshold:
    if abs(z) >= against_trend_extreme_atr_mult:   # climax flush → allow (edge intact)
        pass
    else:
        return _reject(f"against_trend(score={trend_score:+.2f},z={z:+.2f})")
```

Long and short are exact mirrors (non-negotiable futures symmetry).

### Config fields

Added to `SetupDConfig` (`vwap_reversion.py`), mirrored in `SetupDEntryConfig`
(`setup_entry_configs.py`), passed through `setup_d_adapter.py`, and exposed in
`config/strategies/futures/setup_d_vwap_reversion.yaml`.

| field | default | meaning |
|---|---|---|
| `trend_filter_enabled` | `false` | master switch; ship OFF, enable only if validation passes |
| `trend_window_bars` | `30` | VWAP-drift lookback (~30 min) |
| `trend_warmup_bars` | `10` | permissive below this many observations |
| `trend_block_threshold` | `1.0` | block when \|VWAP drift\| ≥ this ×ATR over the window |
| `against_trend_extreme_atr_mult` | `2.6` | climax override; must be ≥ `extreme_atr_mult` (1.8) |

Validation: `against_trend_extreme_atr_mult >= extreme_atr_mult`.

### Observability

- Reject reason `against_trend(score=…,z=…)`.
- `last_signal_details` gains `trend_score`, `trend_window_count`,
  `against_trend_override` (bool), `trend_filter_active` (bool).

## Look-ahead safety

- `_vwap_window` is appended after being read (the score never includes the bar
  it gates), identical to `_vol_reference` / `_self_range`.
- Uses only `vwap`, `atr_14`, `current_price`, `minutes_since_open()`,
  `now.date()` — all live-safe fields with real producers in the orchestrator
  path. No reliance on `atr_90th_percentile` or `last_15min_high/low`.

## Validation plan (the ship gate)

1. **Unit tests (TDD first)** in `tests/` alongside the existing Setup D tests:
   - `trend_score` computation over a known VWAP path.
   - counter-trend shallow dip → blocked (`against_trend`).
   - counter-trend climax (`|z| ≥ against_trend_extreme_atr_mult`) → fires.
   - with-trend fade → never blocked by this gate.
   - warmup (< `trend_warmup_bars`) → permissive.
   - session reset: new `ctx.now.date()` clears the window.
   - long/short symmetry (mirror inputs → mirror outcome).
   - `trend_filter_enabled=false` ⇒ behavior byte-identical to current.

2. **Walk-forward** with `scripts/analysis/walkforward_setup_d_vwap_reversion.py`,
   baseline (filter off) vs filter on, clean window `2025-12-01 … 2026-04`,
   symbol `101S6000`, `--no-track`. Compare full-window Sharpe / return / MDD and
   per-fold OOS (trading-day folds).

3. **Acceptance criteria to enable in paper** (`trend_filter_enabled: true`):
   - (a) full-window Sharpe ≥ baseline (small give-back tolerated only if MDD
     clearly improves);
   - (b) counter-trend loss cluster / trend-day drawdown reduced;
   - (c) **both sides remain positive** (long and short);
   - (d) OOS profitable-fold count not worse than baseline.
   Tune `against_trend_extreme_atr_mult` so climactic reversals survive while
   shallow dips are cut. If criteria fail → land the mechanism **off-by-default**
   and document; do not enable.

4. **Supplementary sanity check:** replay the 2026-07-07 VWAP/price path and
   confirm the gate would have blocked the 11 losing dip-buys (illustrative, not
   part of the statistical ship gate — 07-07 is outside the trusted backtest
   window).

## Validation Results (2026-07-07)

Walk-forward via `walkforward_setup_d_vwap_reversion.py` (new `--trend-filter` +
threshold flags), clean `2025-12-01 … 2026-04-30` `101S6000` window, trading-day
folds (40d IS / 10d OOS / step 10). OOS = concatenated non-overlapping folds.

| config | full Sharpe | OOS Sharpe | OOS pts | OOS trades | both sides + |
|---|---|---|---|---|---|
| **baseline (off)** | 2.746 | **2.135** | +175.7 | 135 | yes (L+130.5 / S+45.2) |
| on, window30 block1.0 (defaults) | 2.621 | 1.921 | +155.3 | 131 | yes |
| on, block1.5 | 2.661 | 2.013 | +164.1 | 133 | yes |
| on, block2.5 / 3.0 | 2.749 | 2.135 | +175.7 | 135 | yes (blocks nothing) |
| on, window60/90 block1.0 | — | 1.894 | +152.6 | 130 | yes |

**Findings:**
1. **Any setting that actually blocks trades is a mild net negative on this
   window** (OOS Sharpe 1.89–2.01, −11 to −23 pts). Only `block_threshold ≥ 2.5`
   matches baseline — because at that level it blocks essentially nothing here.
2. **The window contains no one-way trend-day disaster** (it is the Dec–Apr bull
   period), so the filter's protective benefit **cannot be demonstrated
   in-sample**. It removes marginally-profitable counter-trend fades that, in a
   choppy-but-drifting bull, still mean-revert.
3. **The 07-07 grind is too slow for a 30-bar VWAP slope to catch cleanly.**
   Session VWAP drifted ≈ −0.11 pt/min; over 30 bars that is ≈ −3 pts / ATR ≈ 4
   → trend_score ≈ −0.8, right at the block threshold. Catching such a slow grind
   needs a longer window (which, per the sweep, costs *more* on normal days) or a
   different metric — a **price-below-VWAP persistence** measure would be far more
   sensitive to a persistent one-sided session than VWAP slope.

**Decision (matches the plan's fallback):** land the mechanism **off by default**
(`trend_filter_enabled: false`), fully tested and reproducible via the harness
flags. Do **not** enable. Next steps before any activation:
- Enable in **paper** (futures paper = zero real orders) to observe on live
  trend days and collect 07-07-class samples the backtest window lacks.
- With those samples, calibrate `trend_window_bars` / `trend_block_threshold`, or
  switch the metric to price-below-VWAP persistence (follow-up).

## Scope guard

This change is the trend filter only. Out of scope (separate follow-ups from the
same diagnosis):
- RC4: re-entry cooldown + per-day consecutive-loss stand-down.
- RC5: wire realized paper PnL into `risk:state:futures` so the daily-loss /
  consecutive-loss breaker can fire.
- RC3: opening-auction `wide_spread` guard tuning.

## Rollback

`trend_filter_enabled` ships `false`, so merging is behavior-neutral. Enabling is
a separate one-line YAML flip gated on the validation criteria above; rollback =
flip back to `false`.
