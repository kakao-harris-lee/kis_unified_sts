# trend_pullback Paper Trading Guide

> **ARCHIVED 2026-06-22:** `trend_pullback` is disabled in the current stock
> strategy config. This guide is retained only as a historical paper-trading
> procedure. Use [ROADMAP.md](../ROADMAP.md) for the current strategy state.

## Overview

This guide covers starting, monitoring, and managing paper trading for the `trend_pullback` stock strategy.

**Strategy Summary:**
- **Type:** Multi-timeframe trend-following with pullback entries
- **Entry:** Bollinger Band lower touch + RSI oversold OR Williams %R reversal
- **Exit:** ATR dynamic trailing stop (3.5x stop, 2.0x trail)
- **Position Size:** 1M KRW per position
- **Max Positions:** 5 concurrent
- **Time Filters:** Skip first 30min and last 15min of market

## Quick Start

### Method 1: Using Helper Script (Recommended)

```bash
# Start paper trading with default settings
./scripts/start_trend_pullback_paper.sh
```

The script will:
1. Check all prerequisites (Redis DB 1, Parquet market data, .env)
2. Verify strategy config is enabled
3. Check for daily indicators in Redis
4. Start paper trading with default capital (10M KRW) and max positions (5)
5. Display real-time logs

### Method 2: Direct CLI Command

```bash
# Basic usage
python -m cli.main paper start \
    --strategy trend_pullback \
    --asset stock

# Custom capital and positions
python -m cli.main paper start \
    --strategy trend_pullback \
    --asset stock \
    --capital 50000000 \
    --max-positions 8
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

2. **Parquet market data**
   ```bash
   # Verify
   sts data validate-parquet --root data/market
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
   REDIS_DB=1
   RUNTIME_STORAGE_BACKEND=sqlite
   RUNTIME_STORAGE_SQLITE_PATH=data/runtime/paper/runtime.db
   MARKET_DATA_SOURCE=parquet
   MARKET_DATA_PARQUET_ROOT=data/market
   REDIS_HOST=localhost
   REDIS_PORT=6379

   # Optional: Telegram notifications
   TELEGRAM_STOCK_BOT_TOKEN=your_token
   TELEGRAM_STOCK_CHAT_ID=your_chat_id
   ```

2. **Strategy Config** (`config/strategies/stock/trend_pullback.yaml`)
   ```yaml
   strategy:
     name: trend_pullback
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
#   Positions: 3
#   Total P&L: 125,000 KRW
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
[2026-03-06 09:15:32] Signal Generated: 005930 (Samsung Electronics)
  Direction: LONG
  Confidence: 0.87
  Entry Price: 71,500 KRW
  Stop Loss: 68,900 KRW
  Reason: BB lower touch + RSI oversold (32.5)

[2026-03-06 14:23:15] Position Closed: 000660 (SK Hynix)
  Entry: 145,000 KRW @ 2026-03-05 10:15
  Exit: 148,200 KRW @ 2026-03-06 14:23
  P&L: +3,200 KRW (+2.2%)
  Duration: 1d 4h 8m
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

**Entry Signals** (Pullback on Trending Stocks):
- Daily trend context from scanner (SMA filters)
- Intraday pullback to BB lower band
- RSI < 34 OR Williams %R reversal (-80 → -65)
- Volume > average
- Minimum ATR/cost ratio (quality filter)

**Entry Frequency:**
- 1-3 signals per day (across all symbols in watchlist)
- More signals in volatile/trending markets
- Fewer signals in sideways/choppy markets

**Exit Signals:**
- ATR trailing stop: Activates at 1.0 ATR profit, trails at 2.0 ATR distance
- Hard stop: 3.5 ATR below entry (safety net)
- Position holds until trailing stop triggered (no EOD forced close)

### Position Management

**Entry:**
- Fixed 1M KRW per position (from config)
- Max 5 concurrent positions
- New signals ignored if at max positions
- 120-second cooldown between signals for same symbol

**Exit:**
- ATR dynamic trailing stop (primary)
- Hard stop loss at 3.5 ATR (backup)
- No EOD forced liquidation (swing trading allowed)

### Performance Expectations

Based on backtest results and strategy design:

**Metrics (Indicative, from Optuna optimization):**
- Sharpe Ratio: > 1.0 (target: 1.2-1.6)
- Win Rate: 50-60%
- Average Win: 2-4%
- Average Loss: 1.5-2.5%
- Hold Time: 1-3 days (swing trades)
- Trade Frequency: 5-10 trades/week (across 5 positions)

**P&L Pattern:**
- Small consistent wins from successful pullbacks
- Occasional larger wins from trending moves
- Controlled losses via ATR stops
- Expect 2-3 winning days, 1-2 losing days per week

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

# If 0, scanner failed. Check logs.
```

**Check 3: Market Hours**
```bash
# Strategy only trades during market hours (09:00-15:30 KST)
# Skips first 30min (09:00-09:30) and last 15min (15:15-15:30)
# Active window: 09:30-15:15 KST
```

**Check 4: Market Conditions**
```bash
# Pullback strategy requires trending markets
# In sideways/choppy markets, signals are rare (by design)
# Check daily scanner for BULL regime symbols
```

### Positions Not Closing

**Check 1: Exit Strategy Config**
```bash
# Verify atr_dynamic exit is configured
grep -A 10 "exit:" config/strategies/stock/trend_pullback.yaml
# Expected: type: atr_dynamic
```

**Check 2: ATR Trailing Stop Status**
```bash
# Check position metadata in logs
# Trailing stop activates at 1.0 ATR profit
# If position hasn't reached +1.0 ATR, trailing not yet active
```

**Check 3: Hard Stop Distance**
```bash
# Hard stop is at 3.5 ATR below entry (wide for trend-following)
# Position may be in drawdown but not yet hitting stop
# This is expected behavior for swing trades
```

### High Loss Rate

**Diagnosis 1: Check Market Regime**
```bash
# Pullback strategy performs best in BULL regime
# In BEAR regime, reduce position size or disable strategy
# Check daily scanner regime classification
```

**Diagnosis 2: Slippage**
```bash
# Paper trading simulates 0.5% round-trip costs
# Real slippage may be higher in low-liquidity symbols
# Filter watchlist to high-liquidity stocks only
```

**Diagnosis 3: Parameter Tuning**
```bash
# If win rate < 40%, consider:
# - Tighter RSI threshold (e.g., 30 instead of 34)
# - Wider BB touch buffer (e.g., 1.02 instead of 1.01)
# - Longer signal cooldown (e.g., 180s instead of 120s)

# Run Optuna optimization:
python -m cli.main optimize \
    --strategy trend_pullback \
    --asset stock \
    --trials 100
```

### Memory/Performance Issues

**Issue: High Memory Usage**
```bash
# Check position tracker cache
# Paper engine keeps full trade history in memory
# For long runs (20+ days), consider periodic restarts
```

**Issue: Slow Signal Generation**
```bash
# Check Parquet dataset size and DuckDB query path
sts data validate-parquet --root data/market
# Consider partition cleanup if data/market grows unexpectedly
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
  Total Trades: 47
  Winning Trades: 28
  Win Rate: 59.6%
  Total P&L: 1,245,000 KRW
  Final Equity: 11,245,000 KRW
  Return: +12.45%
  Max Drawdown: -3.2%
  Sharpe Ratio: 1.42
```

## Integration with Validation Phase

This paper trading run is part of **Phase 2: Deployment Validation** (Subtask 2-2).

**Validation Requirements:**
- Run for **20+ trading days** (approximately 4 weeks)
- Target: **Positive cumulative P&L**
- Monitor: **No runtime errors or crashes**
- Verify: **Signal generation matches backtest expectations**

**Documentation:**
- Log all trades via `python -m cli.main paper history`
- Track daily P&L
- Note any anomalies or unexpected behavior
- After 20+ days, document results in `build-progress.txt`

**Next Steps (After 20+ Days):**
- Proceed to Subtask 2-3 (momentum_breakout paper trading)
- Compare performance between trend_pullback and momentum_breakout
- If both positive, move to Phase 3 (documentation & cleanup)
- If issues found, iterate on parameters or strategy logic

## Support

**Logs:** Console output (redirect to file if needed: `./script.sh > paper_trading.log 2>&1`)

**Issues:** Check `build-progress.txt` for known issues and resolutions

**Configuration:** `config/strategies/stock/trend_pullback.yaml`

**Code:**
- Entry: `shared/strategy/entry/trend_pullback.py`
- Exit: `shared/strategy/exit/atr_dynamic.py`
- Engine: `shared/paper/engine.py`
