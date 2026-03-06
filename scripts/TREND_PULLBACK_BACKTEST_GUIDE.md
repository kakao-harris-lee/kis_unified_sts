# Trend Pullback Strategy Backtest Guide

## Overview

This guide covers running and validating the `trend_pullback` strategy backtest for **Subtask 1-3** of the stock strategy redesign task.

## Acceptance Criteria

The backtest must demonstrate:

1. **Sharpe Ratio > 1.0** after 0.5% round-trip costs
2. **Positive net returns**
3. **Reasonable number of trades** (not overfitting - typically 5 to N/20 trades where N is total bars)
4. **MLflow tracking logs saved** (if MLflow is configured)

## Prerequisites

### 1. Environment Setup

**Python Requirements:**
- Python 3.11+ (project requirement)
- Dependencies installed:
  ```bash
  pip install -e ".[dev]"
  ```

**Infrastructure:**
- ClickHouse running (for real data mode)
- Redis running (optional, for MLflow)
- MLflow tracking server (optional)

### 2. Data Availability

**Option A: ClickHouse Data (Recommended)**

Verify 6+ months of data is available:
```bash
python3 scripts/verify_backtest_data.py
```

If data is insufficient, collect it:
```bash
# Full collection (6 months for 30 symbols)
python -m cli.main stock-backfill run --days 180

# Quick test (7 days, specific symbols)
python -m cli.main stock-backfill run --days 7 -c 005930 -c 000660
```

**Option B: CSV Data**

Prepare a CSV file with columns:
- `datetime` (timestamp)
- `code` (stock symbol)
- `open`, `high`, `low`, `close`, `volume`

**Option C: Synthetic Data**

For testing only - generates artificial data that mimics real market behavior.

## Running the Backtest

### Method 1: Standalone Script (Recommended)

```bash
# With ClickHouse data (6 months, Samsung Electronics)
python3 scripts/run_trend_pullback_backtest.py \
    --mode clickhouse \
    --symbol 005930 \
    --days 180 \
    --output-dir ./output/backtests/trend_pullback

# With CSV data
python3 scripts/run_trend_pullback_backtest.py \
    --mode csv \
    --data ./data/samsung_6mo.csv \
    --output-dir ./output/backtests/trend_pullback

# With synthetic data (for testing only)
python3 scripts/run_trend_pullback_backtest.py \
    --mode synthetic \
    --days 180 \
    --output-dir ./output/backtests/trend_pullback
```

### Method 2: CLI Command

```bash
# Using the main CLI
python -m cli.main backtest run \
    --strategy trend_pullback \
    --asset stock \
    --data ./data/backtest.csv
```

### Method 3: Batch Script (Multiple Symbols)

```bash
# Run backtest for all collected symbols
python scripts/analysis/backtest_all_strategies.py \
    --asset-class stock \
    --strategies trend_pullback \
    --limit 10 \
    --output-dir ./output/backtest_batch
```

## Expected Output

### Console Output

```
================================================================================
Backtest Results - trend_pullback
================================================================================
Period: 2025-09-05 09:00:00 to 2026-03-05 15:00:00 (181 days)
Total Bars: 46,800

Initial Capital: $10,000,000
Final Capital:   $10,850,000
Total Return:    $850,000 (8.50%)

Sharpe Ratio:    1.45 ✓
Max Drawdown:    -5.20%
Calmar Ratio:    1.63

Total Trades:    42
Win Rate:        57.1%
Winning Trades:  24
Losing Trades:   18

Validation:
  ✓ Sharpe > 1.0:      True
  ✓ Positive Returns:  True
  ✓ Reasonable Trades: True
================================================================================
```

### Output Files

```
output/backtests/trend_pullback/
├── trend_pullback_results.json      # Full metrics in JSON
├── trend_pullback_trades.csv        # All trades with entry/exit details
└── trend_pullback_equity.csv        # Equity curve over time
```

### Results JSON Structure

```json
{
  "strategy": "trend_pullback",
  "symbol": "005930",
  "start_date": "2025-09-05 09:00:00",
  "end_date": "2026-03-05 15:00:00",
  "total_bars": 46800,
  "duration_days": 181,

  "initial_capital": 10000000,
  "final_capital": 10850000,
  "total_return": 850000,
  "total_return_pct": 8.5,
  "sharpe_ratio": 1.45,
  "max_drawdown_pct": -5.2,
  "calmar_ratio": 1.63,

  "total_trades": 42,
  "winning_trades": 24,
  "losing_trades": 18,
  "win_rate": 57.1,

  "passes_sharpe_criteria": true,
  "passes_return_criteria": true,
  "has_reasonable_trades": true
}
```

## Validation Checklist

After running the backtest, verify:

- [ ] **Data Quality**
  - [ ] 6+ months of data (180+ days)
  - [ ] 30,000+ minute bars
  - [ ] No major data gaps

- [ ] **Performance Metrics**
  - [ ] Sharpe Ratio > 1.0 ✓
  - [ ] Total Return > 0% ✓
  - [ ] Max Drawdown reasonable (< 20%)
  - [ ] Calmar Ratio > 1.0 (if available)

- [ ] **Trade Statistics**
  - [ ] Total trades between 5 and N/20 (not overfitting)
  - [ ] Win rate between 40-70% (realistic)
  - [ ] Average win > average loss (positive expectancy)
  - [ ] No excessive trading (< 5 trades/day)

- [ ] **Risk Management**
  - [ ] Stop losses being triggered (ATR-based)
  - [ ] No runaway losses (max single loss < 5%)
  - [ ] Position sizing working correctly

- [ ] **Output Files**
  - [ ] Results JSON saved with all metrics
  - [ ] Trades CSV contains all trades
  - [ ] Equity curve CSV shows progression

- [ ] **MLflow Tracking** (if enabled)
  - [ ] Run logged in MLflow
  - [ ] Metrics saved
  - [ ] Parameters captured
  - [ ] Artifacts stored

## Troubleshooting

### Issue: No ClickHouse Data

**Error:** `No data found for symbol 005930`

**Solution:**
```bash
# Check data availability
python3 scripts/verify_backtest_data.py

# Collect data if needed
python -m cli.main stock-backfill run --days 180 -c 005930
```

### Issue: Python Module Not Found

**Error:** `ModuleNotFoundError: No module named 'click'`

**Solution:**
```bash
# Install dependencies
pip install -e ".[dev]"

# Or use virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Issue: Python Version Mismatch

**Error:** `requires-python = ">=3.11"`

**Solution:**
```bash
# Check Python version
python3 --version

# Use Docker if system Python is too old
docker-compose run --rm app python3 scripts/run_trend_pullback_backtest.py --mode synthetic
```

### Issue: ClickHouse Connection Error

**Error:** `Cannot connect to ClickHouse`

**Solution:**
```bash
# Check ClickHouse is running
docker ps | grep clickhouse

# Start infrastructure
docker-compose up -d clickhouse redis

# Test connection
clickhouse-client --query "SELECT 1"
```

### Issue: Insufficient Data (<6 months)

**Warning:** `Data duration is only 45 days`

**Impact:** Results may not be statistically significant

**Solution:**
- Collect more data: `python -m cli.main stock-backfill run --days 180`
- Or use multiple symbols and aggregate results

### Issue: Poor Performance (Sharpe < 1.0)

**Analysis Steps:**
1. Check data quality - any gaps or errors?
2. Review trade details - what's causing losses?
3. Verify strategy parameters match config
4. Check if costs are too high (0.5% round-trip assumed)
5. Consider parameter optimization

**Parameter Tuning:**
```bash
# Run optimization to find better parameters
python -m cli.main optimize \
    --strategy trend_pullback \
    --asset stock \
    --data ./data/backtest.csv \
    --trials 100
```

## Next Steps

After successful backtest validation:

1. **Document Results**
   - Save metrics to task notes
   - Update build-progress.txt
   - Commit results to Git (JSON files only, not large CSVs)

2. **Proceed to Subtask 1-4**
   - Run momentum_breakout backtest
   - Compare performance with trend_pullback
   - Verify both meet criteria

3. **Prepare for Paper Trading**
   - Ensure daily scanner cron is running
   - Configure paper trading environment
   - Start monitoring

## References

- **Strategy Config:** `config/strategies/stock/trend_pullback.yaml`
- **Entry Strategy:** `shared/strategy/entry/trend_pullback.py`
- **Exit Strategy:** `shared/strategy/exit/atr_dynamic.py`
- **Backtest Engine:** `shared/backtest/engine.py`
- **CLI Commands:** `cli/main.py`

## Questions?

If you encounter issues not covered here:

1. Check build-progress.txt for known environment issues
2. Review CLAUDE.md for project architecture
3. Check GitHub Actions CI logs if tests pass there
4. Consult with team lead if persistent blockers
