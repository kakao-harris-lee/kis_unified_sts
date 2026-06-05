# Daily Indicator Scanner Verification Guide

## Overview

The daily indicator scanner (`scripts/daily_indicator_scanner.py`) is a critical component for paper trading strategies. It pre-computes daily indicators (SMA, RSI, ATR, Highest High) before market open and publishes them to Redis for consumption by the `TradingOrchestrator`.

**Schedule:** 08:50 KST daily (Mon-Fri), 20 minutes before market open at 09:00 KST

**Redis Key:** `system:daily_indicators:latest`

**TTL:** 24 hours

## Quick Verification

Run the automated verification script:

```bash
./scripts/verify_daily_scanner_cron.sh
```

This checks:
- ✓ Cron script files exist
- ✓ Crontab configuration (08:50 KST, Mon-Fri)
- ✓ Redis connectivity
- ✓ Redis key exists and has data
- ✓ Data freshness (< 24 hours)
- ✓ Scanner script syntax
- ✓ Environment variables

## Manual Verification Steps

### 1. Verify Crontab Configuration

**Check if cron job is scheduled:**

```bash
crontab -l | grep daily_indicator_scanner
```

**Expected output:**

```
50 8 * * 1-5 /home/deploy/project/kis_unified_sts/scripts/cron/daily_indicator_scanner.sh
```

**If not found, add to crontab:**

```bash
crontab -e
```

Add the following line:

```
50 8 * * 1-5 /path/to/project/kis_unified_sts/scripts/cron/daily_indicator_scanner.sh
```

**Important:**
- Replace `/path/to/project` with your actual project path
- Use absolute paths (not relative)
- Ensure the shell script is executable: `chmod +x scripts/cron/daily_indicator_scanner.sh`

### 2. Verify Redis Key Exists

**Check if Redis is running:**

```bash
redis-cli -h localhost -p 6379 -n 1 ping
```

Expected: `PONG`

**Check if key exists:**

```bash
redis-cli -h localhost -p 6379 -n 1 EXISTS system:daily_indicators:latest
```

Expected: `1` (exists) or `0` (does not exist)

**View key data:**

```bash
redis-cli -h localhost -p 6379 -n 1 GET system:daily_indicators:latest | jq .
```

**Expected structure:**

```json
{
  "indicators": {
    "005930": {
      "daily_sma_200": 70000.0,
      "daily_sma_20": 72000.0,
      "daily_sma_60": 71000.0,
      "daily_sma_60_prev": 70500.0,
      "daily_rsi_5": 55.3,
      "daily_atr": 2500.0,
      "daily_highest_high": 74000.0,
      "daily_close": 72500.0,
      "daily_closes": [70000, 70500, 71000, ...],
      "daily_volumes": [10000000, 12000000, 11500000, ...]
    },
    "000660": { ... },
    ...
  },
  "computed_at": "2026-03-06T08:50:15.123456",
  "symbol_count": 30
}
```

**Check data freshness:**

```bash
redis-cli -h localhost -p 6379 -n 1 GET system:daily_indicators:latest | \
  jq -r '.computed_at'
```

Should be within the last 24 hours.

**Check TTL:**

```bash
redis-cli -h localhost -p 6379 -n 1 TTL system:daily_indicators:latest
```

Expected: Positive number (seconds until expiration), ideally close to 86400 (24 hours) if recently computed.

### 3. Manual Scanner Execution

**Test the scanner manually:**

```bash
cd /path/to/project/kis_unified_sts
source .venv/bin/activate
source .env
python scripts/daily_indicator_scanner.py
```

**Expected output:**

```
2026-03-06 08:50:15 [INFO] daily_indicator_scanner: Computing daily indicators for 30 symbols (last 250 days)
2026-03-06 08:50:16 [INFO] daily_indicator_scanner: Loaded 250 daily candles for 005930
2026-03-06 08:50:16 [INFO] daily_indicator_scanner: Loaded 250 daily candles for 000660
...
2026-03-06 08:50:20 [INFO] daily_indicator_scanner: Published daily indicators for 30 symbols to Redis (system:daily_indicators:latest)
2026-03-06 08:50:20 [INFO] daily_indicator_scanner: Success: 30, Errors: 0
```

**With custom symbols:**

```bash
python scripts/daily_indicator_scanner.py --symbols 005930,000660,373220
```

### 4. Verify Cron Job Logs

**Check system logs for cron execution:**

On macOS:
```bash
log show --predicate 'process == "cron"' --last 1h | grep daily-indicator-scanner
```

On Linux (systemd):
```bash
journalctl -t daily-indicator-scanner --since "1 day ago"
```

On Linux (syslog):
```bash
grep daily-indicator-scanner /var/log/syslog
```

**Expected log entries (daily at 08:50):**

```
Mar  6 08:50:15 hostname daily-indicator-scanner[12345]: Computing daily indicators for 30 symbols
Mar  6 08:50:20 hostname daily-indicator-scanner[12345]: Published daily indicators for 30 symbols to Redis
```

### 5. Verify Data Quality

**Check symbol coverage:**

```bash
redis-cli -h localhost -p 6379 -n 1 GET system:daily_indicators:latest | \
  jq -r '.indicators | keys | length'
```

Expected: At least 20-30 symbols

**Check specific symbol data:**

```bash
redis-cli -h localhost -p 6379 -n 1 GET system:daily_indicators:latest | \
  jq -r '.indicators["005930"]'
```

Verify all fields are present and non-null.

**Validate indicators are reasonable:**

```bash
redis-cli -h localhost -p 6379 -n 1 GET system:daily_indicators:latest | \
  jq -r '.indicators["005930"] | "SMA200: \(.daily_sma_200), RSI: \(.daily_rsi_5), ATR: \(.daily_atr)"'
```

## Troubleshooting

### Issue: Cron job not executing

**Check crontab syntax:**
```bash
crontab -l
```

**Verify cron service is running:**
```bash
# macOS
sudo launchctl list | grep cron

# Linux
sudo systemctl status cron
```

**Check script permissions:**
```bash
ls -la scripts/cron/daily_indicator_scanner.sh
# Should show: -rwxr-xr-x (executable)
```

**Test script manually:**
```bash
./scripts/cron/daily_indicator_scanner.sh
```

### Issue: Redis key not populated

**Verify Redis is running:**
```bash
docker ps | grep redis
# or
redis-cli ping
```

**Start Redis if not running:**
```bash
docker-compose up -d redis
```

**Check scanner errors:**
```bash
python scripts/daily_indicator_scanner.py 2>&1 | tee scanner_debug.log
```

**Common errors:**
- Parquet market data missing → Run backfill: `python -m cli.main stock-backfill run --days 250`
- No daily candle data → Validate data: `sts data validate-parquet --root data/market`
- Redis connection refused → Check REDIS_HOST, REDIS_PORT in .env

### Issue: Stale data (> 24 hours old)

**Check cron job is running:**
```bash
crontab -l | grep daily_indicator_scanner
```

**Check recent cron logs:**
```bash
journalctl -t daily-indicator-scanner --since "2 days ago"
```

**Force manual update:**
```bash
source .venv/bin/activate && source .env
python scripts/daily_indicator_scanner.py
```

**Verify update:**
```bash
redis-cli -h localhost -p 6379 -n 1 GET system:daily_indicators:latest | \
  jq -r '.computed_at'
```

### Issue: Low symbol count

**Check Parquet data availability:**
```bash
python scripts/verify_backtest_data.py
```

**Run daily candle backfill:**
```bash
python -m cli.main backfill daily --days 250
```

**Specify symbols manually:**
```bash
python scripts/daily_indicator_scanner.py --symbols 005930,000660,373220,207940,005380
```

## Integration with Paper Trading

The `TradingOrchestrator` consumes this data during startup and intraday:

**Startup (pre-market):**
- Orchestrator reads `system:daily_indicators:latest` from Redis
- Populates `MarketDataProvider.daily_watchlist` dict
- Strategies use this for daily context filters

**Strategy Usage Example (trend_pullback):**

```python
# Check if symbol is in watchlist
if symbol not in self.daily_watchlist:
    return None

# Get daily indicators
daily_data = self.daily_watchlist[symbol]

# Apply daily trend filter
if market_data.close < daily_data["daily_sma_200"]:
    return None  # Skip if below 200-day SMA
```

**Monitoring:**

```bash
# Check orchestrator logs for watchlist loading
tail -f logs/orchestrator.log | grep daily_watchlist

# Expected:
# [INFO] Loaded 30 symbols from daily_watchlist
```

## Acceptance Criteria Checklist

- [ ] Cron job scheduled at 08:50 KST daily (Mon-Fri)
- [ ] Redis key `system:daily_indicators:latest` exists
- [ ] Data is fresh (computed_at within last 24 hours)
- [ ] Symbol count ≥ 20
- [ ] All required fields present (SMA, RSI, ATR, etc.)
- [ ] TTL is set to 24 hours (86400 seconds)
- [ ] Scanner executes successfully without errors
- [ ] Orchestrator can load data from Redis

## References

- Scanner implementation: `scripts/daily_indicator_scanner.py`
- Cron script: `scripts/cron/daily_indicator_scanner.sh`
- Verification script: `scripts/verify_daily_scanner_cron.sh`
- Orchestrator integration: `services/trading/orchestrator.py`
- Strategy usage: `shared/strategy/entry/trend_pullback.py`
