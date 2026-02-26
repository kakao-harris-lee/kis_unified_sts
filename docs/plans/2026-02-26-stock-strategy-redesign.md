# Stock Strategy Redesign — Absolute Return

**Date**: 2026-02-26
**Goal**: 비용 후 양(+) 절대수익 달성 (Sharpe > 1.0)

---

## Problem Statement

4개 active stock strategy 모두 비용 후 양(+) 수익을 내지 못함:

| Strategy | Trades | avg Return | avg Sharpe |
|----------|--------|-----------|------------|
| bb_reversion | 142 | -0.09% | +0.52 |
| volume_accumulation | 277 | +0.40% | -14.43 |
| opening_volume_surge | 244 | +0.00% | -0.78 |
| williams_r | 62 | -0.02% | +0.86 |

### Root Causes

1. **Screener-Strategy Mismatch**: Screener supplies momentum leaders; strategies are mean-reversion/oversold → buying "already moved" stocks.
2. **20-min Warmup Tax**: New symbols need 20 candles before indicators ready; screener rotates every second → opportunity window closed.
3. **Shallow Indicator Stack**: BB, RSI, Williams %R are correlated price oscillators — no independent signal diversity.
4. **No Multi-Timeframe Context**: Intraday oscillators fire without daily trend confirmation → pure noise trading.
5. **Cost Blindness**: Round-trip cost ~0.50%; average returns 0.00~0.40% → costs eat all gains.

---

## Solution: A+B Hybrid Redesign

### Architecture Overview

```
Phase 1: Infrastructure (Static Universe + Preload)
  ┌─────────────────────────────────────────────┐
  │ Daily Candles (ClickHouse) ← pykrx (16:00)  │
  │ Pre-market Scanner (08:30) → Watchlist       │
  │ Minute Preload (08:40) → Indicators Ready    │
  │ WebSocket Subscribe (08:50) → Live Feed      │
  └─────────────────────────────────────────────┘

Phase 2: Strategy (Multi-Timeframe + Cost-Aware)
  ┌─────────────────────────────────────────────┐
  │ Layer 1: Daily Filter → "Buy candidate?"     │
  │ Layer 2: Intraday Trigger → "Enter now?"     │
  │ Minimum Edge Filter → "Worth the cost?"      │
  │ ATR Dynamic Stops → "When to exit?"          │
  └─────────────────────────────────────────────┘
```

---

## Phase 1: Static Universe + Preload

### 1.1 Daily Candles Table

ClickHouse `market.daily_candles`:

```sql
CREATE TABLE market.daily_candles (
    symbol String,
    date Date,
    open Float64,
    high Float64,
    low Float64,
    close Float64,
    volume UInt64,
    change_pct Float64
) ENGINE = ReplacingMergeTree()
ORDER BY (symbol, date);
```

- Source: pykrx batch (cron 16:00 daily)
- Initial backfill: 1 year for KOSPI200 + KOSDAQ top 100
- Schema matches existing `market.minute_candles` conventions

### 1.2 Pre-market Daily Scanner

New service: `services/daily_scanner.py`

- Runs at 08:30 KST
- Reads `market.daily_candles` for all tracked symbols
- Applies Layer 1 filters (per strategy type)
- Outputs `system:daily_watchlist:latest` (Redis, JSON: `{strategy: [symbols]}`)
- Max watchlist size: 50 symbols (within WebSocket 40-symbol cap with buffer)

### 1.3 Static Universe Manager

Replace dynamic screener-driven universe in orchestrator:

- `_universe_refresh_loop()` → reads `system:daily_watchlist:latest` once at startup
- No 30-second refresh, no retention window, no eviction logic needed
- Universe fixed for the trading day
- Screener/fusion_ranker continue running as auxiliary signals (dip_candidates, LLM scores)

### 1.4 Full Preload

- 08:40: Load all watchlist symbols' minute candles from ClickHouse
- 08:50: All symbols `is_warm() = True`
- 09:00: Immediate signal evaluation — zero warmup

---

## Phase 2: Multi-Timeframe Strategies

### 2.1 Strategy Consolidation: 4 → 2

#### Strategy 1: `trend_pullback` (Trend Following + Pullback Entry)

**Daily Filter (Layer 1)**:
- `close > SMA(20)` — price above 20-day moving average
- `RSI(14) daily < 45` — pullback (not overbought)
- `volume_ma(20) > threshold` — sufficient liquidity
- `close > SMA(20) * 0.95` — not too far below trend (max 5% deviation)

**Intraday Trigger (Layer 2)**:
- BB lower touch or Williams %R oversold reversal (-80 → -70)
- RSI(14) intraday < 35 and turning up
- Volume confirm: current volume >= volume_ma

**Exit**:
- Stop loss: `entry - ATR(14) * 2.5` (dynamic, adapts to volatility)
- Trailing stop: activates at +ATR(14), trails at 2× ATR
- Daily trend break: if daily close < SMA(20) → next-day exit
- No fixed time cut — exit driven by trend and ATR

**Config (YAML)**:
```yaml
strategy:
  name: trend_pullback
  asset_class: stock
  enabled: true
  entry:
    type: trend_pullback
    params:
      # Layer 1 (Daily)
      daily_sma_period: 20
      daily_rsi_max: 45
      daily_trend_deviation_pct: 5.0
      # Layer 2 (Intraday)
      bb_period: 20
      bb_std: 2.0
      rsi_oversold: 35
      williams_r_oversold: -80
      williams_r_reversal: -70
      volume_threshold: 1.0
      # Cost filter
      min_atr_cost_ratio: 2.0
  exit:
    type: atr_dynamic
    params:
      atr_period: 14
      stop_atr_multiplier: 2.5
      trail_activation_atr: 1.0
      trail_atr_multiplier: 2.0
      daily_trend_exit: true
      daily_sma_period: 20
```

#### Strategy 2: `momentum_breakout` (Accumulation → Breakout)

**Daily Filter (Layer 1)**:
- `close > high_20 * 0.95` — near 20-day high (within 5%)
- Volume increasing trend: `volume_ma(5) > volume_ma(20) * 1.2`
- Not overextended: `close < SMA(20) * 1.15` (max 15% above mean)

**Intraday Trigger (Layer 2)**:
- Price breaks above `high_20` (daily)
- RVOL >= 1.5
- Accumulation score >= 60 (from overnight scan, if available)

**Exit**:
- Stop loss: `entry - ATR(14) * 1.5` (tighter than trend_pullback)
- Trailing stop: activates at +ATR(14) * 0.5, trails at 1.5× ATR
- Momentum decay: retracement > ATR(14) + negative volume velocity
- Max hold: 5 trading days

**Config (YAML)**:
```yaml
strategy:
  name: momentum_breakout
  asset_class: stock
  enabled: true
  entry:
    type: momentum_breakout
    params:
      # Layer 1 (Daily)
      daily_high_period: 20
      daily_proximity_pct: 5.0
      daily_volume_trend_ratio: 1.2
      daily_max_extension_pct: 15.0
      # Layer 2 (Intraday)
      breakout_buffer_pct: 0.1
      rvol_threshold: 1.5
      accumulation_score_min: 60
      # Cost filter
      min_atr_cost_ratio: 2.0
  exit:
    type: atr_dynamic
    params:
      atr_period: 14
      stop_atr_multiplier: 1.5
      trail_activation_atr: 0.5
      trail_atr_multiplier: 1.5
      momentum_decay_exit: true
      max_hold_days: 5
```

### 2.2 Minimum Edge Filter

Applied to all entries before execution:

```python
atr_pct = ATR(14) / close
round_trip_cost = 0.005  # 0.50%
min_ratio = config.min_atr_cost_ratio  # default 2.0

if atr_pct < round_trip_cost * min_ratio:
    skip  # Expected move doesn't justify cost
```

### 2.3 ATR Dynamic Exit (`atr_dynamic`)

New unified exit strategy replacing fixed % stops:

Priority:
1. Hard stop: `entry ± ATR × stop_multiplier` (direction-aware)
2. Daily trend break: close below daily SMA(20) → signal exit
3. Momentum decay: retracement > 1 ATR + negative volume (for breakout)
4. Trailing stop: activates at profit > ATR × trail_activation, trails at ATR × trail_multiplier
5. Max hold days (breakout only)
6. EOD: not applied by default (swing strategy)

---

## Existing Strategy Disposition

| Strategy | Action | Reason |
|----------|--------|--------|
| `bb_reversion` | Absorbed into `trend_pullback` | BB + RSI logic reused with daily context |
| `williams_r` | Absorbed into `trend_pullback` | Williams %R reversal as additional trigger |
| `volume_accumulation` | Absorbed into `momentum_breakout` | Volume + breakout logic reused |
| `opening_volume_surge` | Disabled | Pure intraday without daily context; cost-disadvantaged |
| `trix_golden` | Already disabled | Kept disabled |

Existing strategy code/configs remain in codebase (disabled) for reference.

---

## Backtest Validation Plan

**Data**:
- 50 symbols (KOSPI200 top by liquidity)
- 3-month minute candles (ClickHouse)
- 1-year daily candles (pykrx backfill)
- Cost: 0.50% round-trip

**Success Criteria**:
| Metric | trend_pullback | momentum_breakout |
|--------|---------------|-------------------|
| Sharpe | > 1.0 | > 1.0 |
| Win Rate | > 40% | > 35% |
| avg Return | > 0.3% per trade | > 0.5% per trade |
| Positive Sharpe Symbols | > 60% (30/50) | > 50% (25/50) |
| Max Drawdown | < -5% | < -5% |

---

## Implementation Sequence

### Phase 1: Infrastructure (Week 1-2)
1. ClickHouse `market.daily_candles` table + pykrx backfill script
2. `DailyScanner` service (pre-market watchlist generation)
3. Orchestrator static universe mode (replace dynamic screener-driven)
4. Full preload pipeline (ClickHouse → indicators ready by 08:50)
5. A/B comparison: existing strategies on new universe vs old

### Phase 2: Strategies (Week 3-4)
6. `trend_pullback` entry + config
7. `momentum_breakout` entry + config
8. `atr_dynamic` exit (unified ATR-based exit)
9. Minimum edge filter integration
10. 50-symbol backtest validation
11. Paper trading deployment

---

## Risk Mitigation

- **Data quality**: pykrx daily candles cross-validated against ClickHouse minute candle OHLCV aggregation
- **Overfitting**: Walk-forward validation (train on 2 months, test on 1 month)
- **Portfolio risk**: Max 5 concurrent positions, max 10% per symbol, -5% drawdown halt
- **Graceful degradation**: If daily scanner fails, fallback to existing screener-based universe
