# Futures daily/swing CTA momentum (THESIS B) — VALIDATED, NO-SHIP (standalone)

- **Date:** 2026-06-25 (design) / 2026-06-26 (walk-forward on 16y KRX data)
- **Author:** strategy-architect (R&D, isolated branch `feat/futures-cta-swing-strategy`)
- **Status:** **NO-SHIP as a standalone strategy.** Code is implemented,
  registered, `enabled: false`, paper-only. The thesis is now **tested** (not
  data-blocked): the edge is **real but regime-concentrated and too weak to ship
  alone.** A conditional, regime-gated variant is a possible follow-up.
- **Symbol:** `krx_kospi200f_continuous` (KRX daily settlement, continuous
  front-month, 2010-06-30 .. 2026-06-25, 3,933 bars, multi-regime).
- **Reproduce:** `.venv/bin/python scripts/analysis/cta_daily_walkforward.py`

## 1. Thesis under test

Daily/swing **time-series momentum** (managed-futures / CTA style): hold KOSPI200
futures across **days** in a confirmed trend regime, long/short symmetric, with
volatility-targeted sizing and a trailing exit. This is a **different timeframe**
than the already-falsified *intraday* trend-following (closed PR #529/#530 ORB +
macd_ema/williams_r/momentum). Daily-bar momentum is a classic global
index-futures edge, so it was worth a genuine, untested look.

The 2026-06-25 verdict was **DATA-BLOCKED** (no real daily partition; the
minute-resample was a thin, partly-contaminated ~3-month window). That gate is
now **lifted**: PR #536 loaded a 16-year KRX **daily settlement** series. This
document replaces the DATA-BLOCKED verdict with a real multi-regime
walk-forward.

## 2. Data + the unadjusted-series (roll) caveat

`krx_kospi200f_continuous` is **RAW volume-weighted front-month, NOT
back-adjusted**. At quarterly rolls (2nd Thursday of Mar/Jun/Sep/Dec) the
settlement level steps by the carry spread. Left unhandled, a roll step injects a
spurious single-day return that a momentum lookback would read as trend.

**How we handle it (two layers, both reusing the same primitive):**

1. **Signal layer** — `roll_aware_log_returns()` zeroes the per-day log-return on
   any quarterly roll day before it enters the momentum sum; the entry also
   **blocks roll days as entry days**. (`is_quarterly_roll_day` = 2nd Thursday of
   Mar/Jun/Sep/Dec; verified to yield exactly 4 roll days/year × 17 years.)
2. **PnL layer** — the backtest marks held positions on **roll-aware**
   log-returns, and a trade spanning a roll books the roll-neutralised "fair"
   path, never the carry step. A real position rolls at ~zero cost; it does not
   capture the gap.

Empirically the KOSPI200 roll is small (mean |ret| on expiry days 1.02% vs 0.89%
baseline — low-dividend index basis), but the neutralisation makes the result
**roll-robust by construction** rather than by luck. Look-ahead safety is
enforced with `LookaheadGuard(ASSERT)`: at decision day `i` the strategy sees
only bars `≤ i`, and fills happen at day `i+1` open.

## 3. Strategy design (implemented)

Long/short symmetric, config-driven, daily cadence. Three registry components:

- **Entry** `cta_momentum` (`shared/strategy/entry/cta_momentum.py`):
  roll-aware **TS-momentum sign** over a lookback (default 60d) **AND** an
  **MA-cross regime** confirmation (fast 20 / slow 100 SMA). Both must agree on
  direction. ATR (Wilder, 20d) sets the initial protective stop. Self-contained
  (`required_indicators == []`) — avoids the daily-cadence `mtf_base`/`momentum_`
  phantom-requirement footgun. Roll days are blocked as entry days.
- **Exit** `cta_momentum_exit` (`shared/strategy/exit/cta_momentum_exit.py`):
  precedence **catastrophic backstop (5 ATR) → ATR chandelier trail
  (4 ATR, activates at 1 ATR profit) → momentum flip → time cap (60 trading
  days)**. Long/short symmetric. **No EOD liquidation** — this is a swing exit.
- **Sizer** `volatility_target_futures`
  (`shared/strategy/position/sizers.py`): contracts scaled so ex-ante annualised
  vol ≈ target (15%); `size = clamp(round(equity·target_vol /
  (ann_vol·price·point_value)), min, max)`. Falls back to ATR-implied vol.

Config: `config/strategies/futures/cta_momentum.yaml` (`enabled: false`).

## 4. Walk-forward — 16 years, 12 folds (IS=3y / OOS=1y rolling)

Costs: commission 0.003%/leg + 1 tick slippage/leg. Single causal pass; OOS
folds attributed by entry day.

### Full window (2010-2026, single pass, all 131 trades)

| Metric | Value |
|---|---|
| Trades (L / S) | 131 (76 / 55) |
| Win rate | 47.3% |
| Total PnL | **+1011.95 pts (+50.6M KRW)** |
| Sharpe (per-trade) | +2.78 |
| **Sharpe (daily equity)** | **+0.59** |
| Long / Short PnL | **+1051.7 / −39.7 pts** (shorts are a net drag over 16y) |

### Honest OOS — concatenated non-overlapping out-of-sample folds

| Metric | Value |
|---|---|
| Trades | 96 |
| Win rate | 47.9% |
| Total PnL | **+165.06 pts (+8.25M KRW)** |
| Sharpe (per-trade) | +1.43 |
| MDD | 4.71M KRW |
| OOS-profitable folds | **7 / 12** |
| Both sides profitable (OOS) | **Yes** (L +139.0 / S +26.1) |

Per-fold OOS (daily-equity Sharpe shown — note **6 of 12 folds negative**):

```
 2013-06..2014-06  n=8   tot=-27.1  shD=-1.24
 2014-06..2015-06  n=8   tot= +5.5  shD=-0.15
 2015-06..2016-06  n=9   tot=-47.8  shD=-1.12   (China shock — worst fold)
 2016-06..2017-06  n=7   tot=+47.5  shD=+2.22
 2017-06..2018-06  n=7   tot=+45.6  shD=+0.52
 2018-06..2019-06  n=6   tot=-16.7  shD=-0.47
 2019-06..2020-06  n=11  tot=-14.4  shD=-0.94
 2020-06..2021-06  n=6   tot=+78.2  shD=+2.04   (COVID trend)
 2021-06..2022-06  n=7   tot=+64.5  shD=+1.15   (2022 bear — shorts work)
 2022-06..2023-06  n=9   tot=-25.5  shD=-0.89
 2023-06..2024-06  n=11  tot=+30.5  shD=+0.80
 2024-06..2025-06  n=7   tot=+24.6  shD=-0.19
```

### Regime-by-regime (the decisive read)

| Regime | n | win% | PnL (pts) | shD |
|---|---:|---:|---:|---:|
| 2011 EU crisis | 13 | 38.5 | **−52.4** | −1.34 |
| 2012-2014 range | 24 | 33.3 | **−107.3** | −0.66 |
| 2015-2016 China | 18 | 22.2 | **−42.1** | −0.69 |
| 2017 semis bull | 7 | 100.0 | +70.2 | +1.85 |
| 2018 selloff | 6 | 66.7 | +29.1 | +0.89 |
| 2019 recovery | 7 | 42.9 | −4.3 | −0.61 |
| 2020 COVID | 10 | 40.0 | +59.5 | +0.27 |
| 2021 post-COVID | 7 | 57.1 | +12.5 | +0.21 |
| 2022 bear | 8 | 37.5 | +16.2 | +0.64 |
| 2023 rate hikes | 10 | 60.0 | +10.2 | +0.38 |
| 2024 AI bull | 9 | 44.4 | +21.3 | +0.53 |
| **2025-2026 AI bull** | 11 | 81.8 | **+983.5** | +2.14 |

**The headline edge is one regime.** Excluding 2025-2026, the strategy nets
**+12.9 pts over 14 years** — indistinguishable from zero. The 2025-2026 AI bull
alone is **99%** of the full-window PnL. This is the textbook CTA profile:
trend-following pays in strongly-trending regimes (2025-26, 2020 COVID, 2022
bear, 2018 selloff) and bleeds in ranging/choppy regimes (2012-14, 2015-16,
2011).

## 5. Sensitivity (defaults are NOT a curve-fit point)

OOS total stays positive and 7-9/12 folds profitable across the whole grid:

| Sweep | OOS total (pts) / profitable folds |
|---|---|
| momentum lookback 20 / 40 / 60 / 90 / 120 | +191 / +229 / +165 / +105 / +77 (8/8/7/7/7) |
| slippage 0 / 1 / 2 / 3 ticks | +170 / +165 / +160 / +155 (low-turnover → cost-robust) |
| MA filter off (pure TS-mom) | +121 (7/12) |
| trail 2 / 4 / 6 ATR | +153 / +165 / +158 (8/7/7) |
| ma_slow 50 / 100 / 150 / 200 | +156 / +165 / +206 / +225 (8/7/9/8) |

The edge is **robust to costs and parameters** (so it is real, not noise) but
**modest in absolute terms** and **concentrated in one regime**.

## 6. Verdict — NO-SHIP (standalone)

**Do NOT ship `cta_momentum` as a standalone always-on strategy.** Evidence:

- Daily-equity Sharpe is only **+0.59 full-window / weak per-fold** (6/12 OOS
  folds negative). That is not a tradeable standalone Sharpe.
- **99% of the PnL is a single regime (2025-2026).** Basing a ship decision on
  one regime is exactly the curve-fit trap the task forbids — strip it and the
  strategy is flat across 14 years.
- Shorts net **−40 pts over 16y** (the index drifts up; short momentum mostly
  pays only in the 2022 bear). Long/short symmetry is preserved in code (correct
  for a futures strategy) but the short side carries little standalone edge here.

This is a **rigorous negative across 16 years** — a definitive, valuable answer,
the same class of result as the intraday-trend falsification, but for a genuinely
different (daily) timeframe.

**Possible follow-up (NOT this PR):** a **regime-gated** variant — only enable
the CTA in a confirmed trending macro regime (ADX / realised-trend filter or the
HAR-RV RegimeGate), sized small as a diversifier alongside the mean-reverting
Setup A/C/D. The full-window +1012 pts shows the upside *when the regime is
right*; the job of any ship-candidate is to be flat (not bleeding) the rest of
the time. That requires its own walk-forward and is left as a conditional-ship
investigation, mirroring Setup D's path.

## 7. Artifacts

- `shared/strategy/entry/cta_momentum.py` — entry (TS-mom + MA-cross, roll-aware).
- `shared/strategy/exit/cta_momentum_exit.py` — exit (trail/flip/time/catastrophic).
- `shared/strategy/position/sizers.py` — `VolatilityTargetFuturesSizer` (+config).
- `config/strategies/futures/cta_momentum.yaml` — `enabled: false`, paper-only.
- `scripts/analysis/cta_daily_walkforward.py` — reproducible 16y WF harness.
- Tests: `tests/unit/strategy/entry/test_cta_momentum.py`,
  `tests/unit/strategy/exit/test_cta_momentum_exit.py`,
  `tests/unit/strategy/position/test_volatility_target_futures_sizer.py`,
  `tests/unit/strategy/test_cta_momentum_registry.py` (+ registry builtin guard).

The strategy is registered and YAML-buildable but `enabled: false`. No runtime is
wired; no container is touched. To revisit, build the regime-gated variant and
re-run the harness.
