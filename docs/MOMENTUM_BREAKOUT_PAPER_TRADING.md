# momentum_breakout Paper Trading Guide

## Overview

This guide covers starting, monitoring, and managing paper trading for the `momentum_breakout` stock strategy.

**Strategy Summary:**
- **Type:** Multi-timeframe momentum breakout with volume surge confirmation
- **Entry:** Breakout detection + RVOL > 1.6 + accumulation score >= 40
- **Trend Mode:** Relaxed thresholds in BULL regime + EMA pullback entries (5/20/60)
- **Exit:** ATR dynamic trailing stop (2.0x stop, 2.0x trail activation, 1.5x trail)
- **Position Size:** 3M KRW per position
- **Max Positions:** 8 concurrent
- **Time Filters:** Skip first 10min and last 10min of market

## Quick Start

### Method 1: Using Helper Script (Recommended)

```bash
# Start paper trading with default settings
./scripts/start_momentum_breakout_paper.sh
```

The script will:
1. Check all prerequisites (Redis, ClickHouse, .env)
2. Verify strategy config is enabled
3. Check for daily indicators in Redis
4. Start paper trading with default capital (30M KRW) and max positions (8)
5. Display real-time logs

### Method 2: Direct CLI Command

```bash
# Basic usage
python -m cli.main paper start \
    --strategy momentum_breakout \
    --asset stock

# Custom capital and positions
python -m cli.main paper start \
    --strategy momentum_breakout \
    --asset stock \
    --capital 50000000 \
    --max-positions 10
```

## Prerequisites

### Required Services

1. **Redis** (DB 1)
   ```bash
   # Start via Docker
   docker-compose up -d redis

   # Verify
   redis-cli -n 1 ping
   # Expected: PONG
   ```

2. **ClickHouse**
   ```bash
   # Start via Docker
   docker-compose up -d clickhouse

   # Verify
   clickhouse-client --query "SELECT 1"
   # Expected: 1
   ```

3. **Daily Indicator Scanner** (Highly Recommended)
   ```bash
   # Verify cron job is configured
   crontab -l | grep daily_indicator_scanner
   # Expected: 50 8 * * 1-5 .../daily_indicator_scanner.sh

   # Verify Redis has daily data
   redis-cli -n 1 EXISTS system:daily_indicators:latest
   # Expected: 1

   # Manual run (if cron not set up)
   ./scripts/cron/daily_indicator_scanner.sh
   ```

### Configuration

1. **Environment Variables** (`.env`)
   ```bash
   # KIS API credentials (stock account)
   KIS_STOCK_APP_KEY=your_app_key
   KIS_STOCK_APP_SECRET=your_app_secret
   KIS_STOCK_ACCOUNT_NO=your_account_no
   KIS_STOCK_MARKET=mock  # or 'real' for live

   # Infrastructure
   CLICKHOUSE_HOST=localhost
   CLICKHOUSE_PORT=9000
   REDIS_HOST=localhost
   REDIS_PORT=6379

   # Optional: Telegram notifications
   TELEGRAM_STOCK_BOT_TOKEN=your_token
   TELEGRAM_STOCK_CHAT_ID=your_chat_id
   ```

2. **Strategy Config** (`config/strategies/stock/momentum_breakout.yaml`)
   ```yaml
   strategy:
     name: momentum_breakout
     enabled: true  # Must be true
     # ... rest of config
   ```

## Monitoring

### Check Status

```bash
# View current status
python -m cli.main paper status

# Expected output:
# Paper Trading Status:
# ----------------------------------------
#   Running: True
#   Positions: 5
#   Total P&L: 342,000 KRW
```

### View Trade History

```bash
# Last 10 trades (default)
python -m cli.main paper history

# Last 50 trades
python -m cli.main paper history --limit 50

# JSON format
python -m cli.main paper history --format json
```

### Real-time Logs

Paper trading logs are output to console in real-time:

```
[2026-03-06 09:25:12] Signal Generated: 005930 (Samsung Electronics)
  Direction: LONG
  Confidence: 0.92
  Entry Price: 72,100 KRW
  Stop Loss: 70,650 KRW
  Reason: Breakout + RVOL 2.3 + accumulation score 65
  Regime: BULL (trend mode active)

[2026-03-06 11:45:30] Signal Generated: 000660 (SK Hynix)
  Direction: LONG
  Confidence: 0.88
  Entry Price: 147,500 KRW
  Stop Loss: 144,550 KRW
  Reason: EMA pullback (5/20/60) + RVOL 1.9
  Regime: BULL (trend mode active)

[2026-03-06 14:15:45] Position Closed: 373220 (LG Energy Solution)
  Entry: 485,000 KRW @ 2026-03-05 10:30
  Exit: 492,300 KRW @ 2026-03-06 14:15
  P&L: +7,300 KRW (+1.5%)
  Duration: 1d 3h 45m
  Reason: ATR trailing stop triggered
```

### Dashboard (Optional)

If the dashboard API is running:

```bash
# Start dashboard
python -m services.dashboard.app

# Access at http://localhost:5080
# View real-time positions, P&L chart, trade log
```

## Expected Behavior

### Signal Generation

**Entry Signals (Momentum Breakout):**

**Standard Mode:**
- Breakout detection (price > recent high)
- RVOL > 1.6 (volume surge confirmation)
- Accumulation score >= 40 (screener filter)
- Breakout buffer: 3% above high (reduces false breakouts)
- Intrabar breakout: Enabled with 5% reclaim threshold

**Trend Mode (BULL/BULL_STRONG/BULL_MODERATE/SIDEWAYS_UP):**
- Relaxed RVOL threshold: 1.0 (vs 1.6 in standard mode)
- Relaxed breakout buffer: 0% (immediate breakouts allowed)
- EMA pullback entries: Price touches EMA(5/20/60) + RSI > 40
- Faster signal cooldown: 60s (vs 120s in standard mode)
- Extended hold period: up to 15 days (vs 8 days in standard mode)

**Entry Frequency:**
- 2-5 signals per day (across all symbols in watchlist)
- Higher frequency in BULL regime (trend mode)
- Lower frequency in BEAR/SIDEWAYS regime (standard mode only)
- More signals in volatile markets with strong momentum

**Exit Signals:**
- ATR trailing stop: Activates at 2.0 ATR profit, trails at 1.5 ATR distance
- Hard stop: 2.0 ATR below entry (tighter than trend_pullback)
- Momentum decay exit: Enabled (closes on momentum reversal)
- Max hold: 8 days (standard mode), 15 days (trend mode)

### Position Management

**Entry:**
- Fixed 3M KRW per position (from config)
- Max 8 concurrent positions
- New signals ignored if at max positions
- 120-second cooldown between signals for same symbol (60s in trend mode)

**Exit:**
- ATR dynamic trailing stop (primary)
- Hard stop loss at 2.0 ATR (backup)
- Momentum decay detection (optional)
- Max hold period enforcement (8-15 days)
- No EOD forced liquidation (intraday parameter is false)

### Performance Expectations

Based on backtest results and strategy design (Optuna-optimized parameters):

**Metrics (Indicative):**
- Sharpe Ratio: > 1.0 (target: 1.2-1.8)
- Win Rate: 50-60%
- Average Win: 2-4%
- Average Loss: 1.0-2.0%
- Hold Time: 2-5 days (momentum trades)
- Trade Frequency: 8-15 trades/week (across 8 positions)

**P&L Pattern:**
- Quick wins from successful breakouts (1-3 days)
- Larger wins from extended trends in BULL regime (5-15 days)
- Controlled losses via tight ATR stops (2.0x vs 3.5x for pullback)
- Expect 3-4 winning days, 1 losing day per week
- Higher win rate in BULL regime (trend mode)

## Troubleshooting

### No Signals Generated

**Check 1: Daily Scanner Running**
```bash
# Verify Redis has daily data
redis-cli -n 1 GET system:daily_indicators:latest | jq '.computed_at'

# If missing or stale, run scanner manually
./scripts/cron/daily_indicator_scanner.sh
```

**Check 2: Watchlist Population**
```bash
# Verify symbols in watchlist
redis-cli -n 1 GET system:daily_indicators:latest | jq '.symbols | length'
# Expected: 20-30 symbols

# Check accumulation scores
redis-cli -n 1 GET system:daily_indicators:latest | jq '.symbols[].accumulation_score'
# Expected: Some symbols with score >= 40
```

**Check 3: Market Hours**
```bash
# Strategy only trades during market hours (09:00-15:30 KST)
# Skips first 10min (09:00-09:10) and last 10min (15:20-15:30)
# Active window: 09:10-15:20 KST
```

**Check 4: RVOL Threshold**
```bash
# Breakouts require RVOL > 1.6 (or > 1.0 in trend mode)
# In low-volume periods, signals are rare
# Check real-time RVOL in logs
# If consistently below threshold, market is quiet (expected)
```

**Check 5: Regime Classification**
```bash
# Standard mode: All regimes
# Trend mode: Only BULL/BULL_STRONG/BULL_MODERATE/SIDEWAYS_UP
# In BEAR regime, only standard breakouts (fewer signals)
# Check daily scanner regime for each symbol
```

### Too Many Signals (Position Limit Hit Frequently)

**Adjustment 1: Increase Max Positions**
```bash
# Edit config or use CLI parameter
python -m cli.main paper start \
    --strategy momentum_breakout \
    --asset stock \
    --max-positions 12
```

**Adjustment 2: Increase Confidence Threshold**
```bash
# Edit config/strategies/stock/momentum_breakout.yaml
# Add minimum confidence filter in position sizer
# Or tighten entry criteria (higher RVOL, higher accumulation score)
```

**Adjustment 3: Increase Signal Cooldown**
```bash
# Edit config entry params
signal_cooldown_seconds: 180  # Increase from 120
trend_signal_cooldown_seconds: 90  # Increase from 60
```

### Positions Not Closing

**Check 1: Exit Strategy Config**
```bash
# Verify atr_dynamic exit is configured
grep -A 10 "exit:" config/strategies/stock/momentum_breakout.yaml
# Expected: type: atr_dynamic
```

**Check 2: ATR Trailing Stop Status**
```bash
# Check position metadata in logs
# Trailing stop activates at 2.0 ATR profit
# If position hasn't reached +2.0 ATR, trailing not yet active
# Hard stop at -2.0 ATR will trigger if losing
```

**Check 3: Max Hold Period**
```bash
# Standard mode: 8 days max hold
# Trend mode: 15 days max hold
# Position should auto-close at max_hold_days
# Check position age in logs
```

**Check 4: Momentum Decay Exit**
```bash
# momentum_decay_exit: true in config
# Positions close when momentum reverses (even if profitable)
# Check if momentum indicators are updating
```

### High Loss Rate

**Diagnosis 1: Check Market Regime**
```bash
# Breakout strategy performs best in BULL regime (trend mode)
# In BEAR/SIDEWAYS regime, fewer signals and lower win rate expected
# Check daily scanner regime classification
# Consider disabling strategy in prolonged BEAR markets
```

**Diagnosis 2: False Breakouts**
```bash
# If win rate < 40%, breakouts may be failing quickly
# Consider:
# - Higher breakout_buffer_pct (e.g., 0.05 instead of 0.03)
# - Higher RVOL threshold (e.g., 2.0 instead of 1.6)
# - Higher accumulation_score_min (e.g., 50 instead of 40)
# - Disable intrabar_breakout_enabled
```

**Diagnosis 3: Slippage**
```bash
# Paper trading simulates 0.5% round-trip costs
# Real slippage on breakouts can be higher (momentum attracts buyers)
# Filter watchlist to high-liquidity stocks only (top 20)
# Consider reducing position size to improve fill quality
```

**Diagnosis 4: Parameter Tuning**
```bash
# Run Optuna optimization with recent data
python -m cli.main optimize \
    --strategy momentum_breakout \
    --asset stock \
    --trials 100

# Key parameters to tune:
# - breakout_buffer_pct (range: 0.0-0.10)
# - rvol_threshold (range: 1.2-2.5)
# - accumulation_score_min (range: 30-60)
# - stop_atr_multiplier (range: 1.5-3.0)
# - trail_atr_multiplier (range: 1.0-2.5)
```

### Trend Mode Not Activating

**Check 1: Regime Classification**
```bash
# Verify symbols have BULL regime in daily scanner
redis-cli -n 1 GET system:daily_indicators:latest | \
    jq '.symbols[] | select(.regime | contains("BULL"))'

# If no BULL symbols, trend mode won't activate (expected)
```

**Check 2: Config Enabled**
```bash
# Verify trend mode is enabled in config
grep "trend_mode_enabled" config/strategies/stock/momentum_breakout.yaml
# Expected: trend_mode_enabled: true

# Verify regimes list includes current market regime
grep "trend_mode_regimes" config/strategies/stock/momentum_breakout.yaml
# Expected: ["BULL", "BULL_STRONG", "BULL_MODERATE", "SIDEWAYS_UP"]
```

**Check 3: Logs**
```bash
# Trend mode signals should show in logs with marker
# Example: "Regime: BULL (trend mode active)"
# If missing, check MarketClassifier output in daily scanner
```

### Memory/Performance Issues

**Issue: High Memory Usage**
```bash
# Momentum strategy generates more signals than pullback
# With 8 positions, memory usage is higher
# For long runs (20+ days), consider periodic restarts
# Monitor RSS via: ps aux | grep "cli.main paper"
```

**Issue: Slow Signal Generation**
```bash
# Breakout detection requires recent high calculation
# Check ClickHouse query performance for bars_1m
# Ensure indexes exist on (symbol, timestamp)
# Consider data cleanup if table > 10M rows
```

## Stopping Paper Trading

### Graceful Stop

```bash
# In the terminal running paper trading, press Ctrl+C
# Engine will:
#   1. Stop accepting new signals
#   2. Close all open positions (simulated market orders)
#   3. Print performance summary
#   4. Save final state to Redis (if configured)
```

### Force Stop (API)

```bash
# If running via dashboard API
python -m cli.main paper stop
```

### View Final Summary

After stopping, the engine prints:

```
========================================
Paper Trading Summary
========================================
  Total Trades: 63
  Winning Trades: 38
  Win Rate: 60.3%
  Total P&L: 2,140,000 KRW
  Final Equity: 32,140,000 KRW
  Return: +7.13%
  Max Drawdown: -2.8%
  Sharpe Ratio: 1.58
```

## Integration with Validation Phase

This paper trading run is part of **Phase 2: Deployment Validation** (Subtask 2-3).

**Validation Requirements:**
- Run for **20+ trading days** (approximately 4 weeks)
- Target: **Positive cumulative P&L**
- Monitor: **No runtime errors or crashes**
- Verify: **Signal generation matches backtest expectations**
- Compare: **Performance vs trend_pullback strategy**

**Documentation:**
- Log all trades via `python -m cli.main paper history`
- Track daily P&L
- Note any anomalies or unexpected behavior
- Compare signal frequency, win rate, P&L patterns with trend_pullback
- After 20+ days, document results in `build-progress.txt`

**Next Steps (After 20+ Days):**
- Proceed to Subtask 2-4 (monitor both strategies for 20+ days total)
- Compare performance: momentum_breakout vs trend_pullback
- Analyze complementarity (do they trade different market conditions?)
- If both positive, move to Phase 3 (documentation & cleanup)
- If issues found, iterate on parameters or strategy logic

## Support

**Logs:** Console output (redirect to file if needed: `./script.sh > paper_trading.log 2>&1`)

**Issues:** Check `build-progress.txt` for known issues and resolutions

**Configuration:** `config/strategies/stock/momentum_breakout.yaml`

**Code:**
- Entry: `shared/strategy/entry/momentum_breakout.py`
- Exit: `shared/strategy/exit/atr_dynamic.py`
- Engine: `shared/paper/engine.py`
