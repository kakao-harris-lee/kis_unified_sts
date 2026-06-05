# Backtest Data Preparation Guide

## Overview

This guide provides instructions for preparing 6+ months of 1-minute OHLCV data required for strategy backtesting validation.

## Requirements

- **Minimum Duration**: 6 months of historical data
- **Minimum Symbols**: 10-20 representative stocks from DEFAULT_SYMBOLS list
- **Data Format**: 1-minute bars stored as Parquet under `data/market`
- **Target Symbols**: 30 stocks from STOCK_UNIVERSE (defined in `shared/collector/historical/stock.py`)

## DEFAULT_SYMBOLS List

The following 30 symbols should have data (from `scripts/daily_indicator_scanner.py`):

```python
DEFAULT_SYMBOLS = [
    # Top tier (대형주)
    "005930",  # 삼성전자
    "000660",  # SK하이닉스
    "373220",  # LG에너지솔루션
    "207940",  # 삼성바이오로직스
    "005380",  # 현대차
    "000270",  # 기아
    "068270",  # 셀트리온
    "035420",  # NAVER
    "105560",  # KB금융
    "055550",  # 신한지주

    # Mid tier (중형주)
    "006400",  # 삼성SDI
    "003670",  # 포스코퓨처엠
    "012330",  # 현대모비스
    "034730",  # SK
    "051910",  # LG화학
    "028260",  # 삼성물산
    "066570",  # LG전자
    "032830",  # 삼성생명
    "096770",  # SK이노베이션
    "003550",  # LG

    # Bottom tier (소형/테마주)
    "015760",  # 한국전력
    "034020",  # 두산에너빌리티
    "009150",  # 삼성전기
    "000810",  # 삼성화재
    "086790",  # 하나금융지주
    "010130",  # 고려아연
    "033780",  # KT&G
    "003490",  # 대한항공
    "011200",  # HMM
    "010950",  # S-Oil
]
```

## Step 1: Verify Existing Data

### Option A: Using Verification Script (Recommended)

```bash
# Run the verification script
python3 scripts/verify_backtest_data.py

# Expected output:
# ✅ PASS: 20+ symbols have 6+ months of data
#          (minimum required: 10 symbols)
```

### Option B: Manual Parquet Inspection

Inspect the Parquet dataset with DuckDB or `sts data validate-parquet`.

```sql
SELECT
    code,
    min(datetime) as first_date,
    max(datetime) as last_date,
    count() as row_count,
    dateDiff('day', min(datetime), max(datetime)) as days_span
FROM market.bars_1m
WHERE code IN (
    '005930', '000660', '373220', '207940', '005380',
    '000270', '068270', '035420', '105560', '055550'
)
GROUP BY code
ORDER BY code;
```

### Option C: Using CLI Status Command

```bash
# Check stock data collection status
python -m cli.main stock-backfill status --days 180

# Expected output shows:
# - Number of symbols with data
# - Date range for each symbol
# - Total rows collected
```

## Step 2: Collect Data (If Insufficient)

### Quick Collection (7 days)

For testing purposes or recent data:

```bash
python -m cli.main stock-backfill run --days 7
```

### Full Collection (6 months = 180 days)

For complete backtest validation:

```bash
# Collect 6 months for all STOCK_UNIVERSE symbols
python -m cli.main stock-backfill run --days 180

# This will:
# - Connect to KIS API
# - Collect minute bars for all 30 stocks
# - Store in Parquet market-data layout
# - Support resume on interruption
```

### Specific Symbols Collection

If only specific symbols need data:

```bash
# Collect for specific symbols
python -m cli.main stock-backfill run --days 180 \
    -c 005930 -c 000660 -c 373220 -c 207940 -c 005380

# Collect for top 10 symbols
python -m cli.main stock-backfill run --days 180 \
    -c 005930 -c 000660 -c 373220 -c 207940 -c 005380 \
    -c 000270 -c 068270 -c 035420 -c 105560 -c 055550
```

### Collection Notes

- **Rate Limits**: KIS API has rate limits. The collector handles this automatically with retries and backoff.
- **Resume Support**: Use `--no-resume` flag to force restart collection from scratch.
- **Time Window**: KIS API typically provides up to 180 days (6 months) of intraday data.
- **Trading Hours**: Only collects data during market hours (09:00-15:30 KST).

## Step 3: Verify Data Quality

After collection, verify data quality:

```bash
# Run verification script
python3 scripts/verify_backtest_data.py

# Expected checks:
# ✅ At least 10-20 symbols have data
# ✅ Each symbol has 6+ months (180+ days)
# ✅ Each symbol has reasonable row count (>20,000 bars)
# ✅ No gaps in critical trading days
```

## Expected Data Volumes

For 6 months of minute-bar data per symbol:

- **Trading Days**: ~120 days (excluding weekends/holidays)
- **Minutes per Day**: ~390 minutes (09:00-15:30)
- **Expected Rows per Symbol**: ~46,800 bars (120 days × 390 min)
- **Total Rows (30 symbols)**: ~1,404,000 bars

## Troubleshooting

### Issue: "No data found" for symbols

**Solution:**
```bash
# Validate Parquet data
sts data validate-parquet

# Start services if needed
docker-compose up -d redis

# Verify connection
python -m cli.main health
```

### Issue: "Insufficient data" (< 6 months)

**Solution:**
```bash
# Run full 180-day backfill
python -m cli.main stock-backfill run --days 180 --no-resume
```

### Issue: KIS API errors during collection

**Solution:**
```bash
# Check KIS credentials in .env
cat .env | grep KIS_

# Required variables:
# KIS_STOCK_APP_KEY=...
# KIS_STOCK_APP_SECRET=...
# KIS_STOCK_ACCOUNT_NO=...
# KIS_STOCK_MARKET=real  # or 'mock' for paper trading
```

### Issue: Rate limit errors (EGW00201)

**Solution:**
- The collector automatically handles rate limits with exponential backoff
- If persistent, reduce concurrency or wait for cooldown period
- KIS API resets limits every hour

## Database Schema

The `market.bars_1m` table schema:

```sql
CREATE TABLE market.bars_1m (
    code String,           -- Stock code (e.g., '005930')
    datetime DateTime64(3), -- Timestamp with milliseconds
    open Float64,          -- Open price
    high Float64,          -- High price
    low Float64,           -- Low price
    close Float64,         -- Close price
    volume UInt64,         -- Volume
    name String DEFAULT '' -- Stock name (optional)
) ENGINE = ReplacingMergeTree()
ORDER BY (code, datetime);
```

## Integration with Backtest Pipeline

Once data is verified, the backtest commands can use it:

```bash
# Run backtest for trend_pullback strategy
python -m cli.main backtest run \
    --strategy trend_pullback \
    --asset stock \
    --start 2025-09-01 \
    --end 2026-03-01

# Run backtest for momentum_breakout strategy
python -m cli.main backtest run \
    --strategy momentum_breakout \
    --asset stock \
    --start 2025-09-01 \
    --end 2026-03-01
```

## Automation

For ongoing data collection, set up daily cron job:

```bash
# Add to crontab (after market close at 15:40 KST)
40 15 * * 1-5 cd /path/to/project && python -m cli.main stock-backfill today
```

This ensures continuous data availability for backtesting and paper trading.

## Summary Checklist

- [ ] Parquet market-data dataset available
- [ ] KIS API credentials configured
- [ ] Verification script executed successfully
- [ ] At least 10-20 symbols have 6+ months of data
- [ ] Data quality verified (no major gaps)
- [ ] Ready for backtest validation (subtask-1-3 and subtask-1-4)

## Next Steps

After data preparation is complete:
1. **Subtask 1-3**: Run backtest for trend_pullback strategy
2. **Subtask 1-4**: Run backtest for momentum_breakout strategy
3. **Subtask 1-5**: Review and document performance metrics
