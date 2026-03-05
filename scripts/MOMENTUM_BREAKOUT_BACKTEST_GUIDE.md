# Momentum Breakout Strategy Backtest Guide

## Overview

This guide provides comprehensive instructions for running backtests of the `momentum_breakout` strategy as part of Task 007 (Stock Strategy Redesign). The backtest validates the strategy meets acceptance criteria before paper trading deployment.

## Acceptance Criteria

The backtest must demonstrate:

1. **Sharpe Ratio > 1.0** after 0.5% round-trip costs
2. **Positive Net Returns** over the test period
3. **Reasonable Trade Count** (not overfitting: 5 ≤ trades ≤ N/20)
4. **MLflow Tracking Logs** saved (if MLflow is configured)

## Prerequisites

### Required Software
- Python 3.11+ (project requirement)
- Project dependencies installed: `pip install -e ".[dev]"`
- ClickHouse running (for real data testing)
- Redis running (for strategy context)

### Required Data
- 6+ months of 1-minute OHLCV data in ClickHouse `market.bars_1m`
- Data collection: `python -m cli.main stock-backfill run --days 180`
- Data verification: `python3 scripts/verify_backtest_data.py`

### Environment Variables
Ensure `.env` file is configured:
```bash
CLICKHOUSE_HOST=localhost
CLICKHOUSE_NATIVE_PORT=9000
CLICKHOUSE_STOCK_DATABASE=market
KIS_STOCK_APP_KEY=your_app_key
KIS_STOCK_APP_SECRET=your_app_secret
```

## Execution Methods

### Method 1: Standalone Script (Recommended)

The dedicated backtest script provides the most control and detailed output.

#### With ClickHouse Data (Production-Ready)
```bash
python3 scripts/run_momentum_breakout_backtest.py \
    --mode clickhouse \
    --symbol 005930 \
    --days 180 \
    --output-dir ./output/backtests/momentum_breakout
```

#### With CSV Data (Pre-Exported)
```bash
python3 scripts/run_momentum_breakout_backtest.py \
    --mode csv \
    --data ./data/samsung_6months.csv \
    --output-dir ./output/backtests/momentum_breakout
```

#### With Synthetic Data (Testing Only)
```bash
python3 scripts/run_momentum_breakout_backtest.py \
    --mode synthetic \
    --days 180 \
    --output-dir ./output/backtests/momentum_breakout
```

**Note:** Synthetic data is for infrastructure testing only. Results are not representative of real trading performance.

### Method 2: Via CLI Tool

Use the project's CLI for integration with MLflow tracking:

```bash
python -m cli.main backtest run \
    --strategy momentum_breakout \
    --asset stock \
    --data ./data/samsung_6months.csv
```

### Method 3: Batch Testing (Multiple Symbols)

Use the batch backtest script to test across multiple symbols:

```bash
python scripts/analysis/backtest_all_strategies.py \
    --asset-class stock \
    --strategies momentum_breakout \
    --limit 10 \
    --output-dir ./output/backtest_batch
```

## Expected Output

### Console Output

```
2026-03-05 13:30:00 - INFO - Loading data in clickhouse mode...
2026-03-05 13:30:01 - INFO - Running backtest for momentum_breakout
2026-03-05 13:30:01 - INFO - Data: 46800 bars from 2025-09-05 to 2026-03-05
2026-03-05 13:30:05 - INFO - Loaded strategy: momentum_breakout
================================================================================
Backtest Results - momentum_breakout
================================================================================
Period: 2025-09-05 09:00:00 to 2026-03-05 15:30:00 (180 days)
Total Bars: 46,800

Initial Capital: $10,000,000
Final Capital:   $10,850,000
Total Return:    $850,000 (8.50%)

Sharpe Ratio:    1.45 ✓
Max Drawdown:    7.30%
Calmar Ratio:    1.16

Total Trades:    42
Win Rate:        57.1%
Winning Trades:  24
Losing Trades:   18

Validation:
  ✓ Sharpe > 1.0:      True
  ✓ Positive Returns:  True
  ✓ Reasonable Trades: True
================================================================================
✓ All acceptance criteria met!
```

### Generated Files

In the output directory (`./output/backtests/momentum_breakout/`):

1. **momentum_breakout_results.json**
   - Complete performance metrics
   - Strategy parameters
   - Validation status

2. **momentum_breakout_trades.csv**
   - Individual trade records
   - Entry/exit timestamps
   - P&L per trade
   - Signal details

3. **momentum_breakout_equity.csv**
   - Equity curve data
   - Timestamp-indexed portfolio value
   - Drawdown tracking

## Strategy Parameters (from Config)

The backtest uses parameters from `config/strategies/stock/momentum_breakout.yaml`:

### Entry Logic
- **Breakout Detection:** Price breaks above recent high with buffer (3%)
- **Volume Confirmation:** RVOL > 1.6 (relative volume threshold)
- **Accumulation Score:** >= 40 (volume trend strength)
- **Time Filters:** Skip first 10min and last 10min of trading day
- **Signal Cooldown:** 120 seconds between entry signals
- **Intrabar Breakout:** Enabled with 5% reclaim threshold

### Trend Mode (Enhanced Entry)
- **Regimes:** BULL, BULL_STRONG, BULL_MODERATE, SIDEWAYS_UP
- **Relaxed RVOL:** 1.0 (vs 1.6 in normal mode)
- **EMA Pullback:** 5/20/60 period EMAs for pullback detection
- **RSI Filter:** >= 40.0 for trend confirmation

### Exit Logic (ATR Dynamic)
- **Stop Loss:** 2.0x ATR multiplier (wider stop for momentum)
- **Trail Activation:** 2.0x ATR profit required before trailing
- **Trail Distance:** 1.5x ATR trailing stop
- **Max Hold Days:** 8 days (exits stale positions)
- **Momentum Decay:** Enabled (exits on momentum exhaustion)

### Position Sizing
- **Order Amount:** 3M KRW per position
- **Max Positions:** 8 concurrent positions
- **Risk Management:** Stop loss at 2.0x ATR

## Validation Checklist

After running the backtest, verify:

- [ ] **Sharpe Ratio > 1.0** ✓
  - Check: `results["sharpe_ratio"] > 1.0`
  - Target: 1.2-1.8 range expected

- [ ] **Positive Returns** ✓
  - Check: `results["total_return_pct"] > 0`
  - Target: 5-15% over 6 months

- [ ] **Reasonable Trade Count** ✓
  - Check: `5 <= results["total_trades"] <= len(df) / 20`
  - Target: 1-2 trades per week per symbol

- [ ] **Win Rate** (Informational)
  - Expected: 50-60% for momentum strategy
  - Check: `results["win_rate"]`

- [ ] **Max Drawdown** (Informational)
  - Expected: < 10% with ATR stops
  - Check: `results["max_drawdown_pct"]`

- [ ] **MLflow Tracking**
  - If MLflow configured, check: `mlflow ui`
  - Experiment: "backtest"
  - Run name: "momentum_breakout_{timestamp}"

## Troubleshooting

### Issue: No Data Found

**Error:**
```
No data found for symbol 005930
```

**Solution:**
```bash
# Run data collection
python -m cli.main stock-backfill run --days 180 -c 005930

# Verify data availability
python3 scripts/verify_backtest_data.py
```

### Issue: Insufficient Data

**Error:**
```
Insufficient data: 800 bars (minimum 1000 required)
```

**Solution:**
- Increase collection period: `--days 200`
- Check data quality in ClickHouse
- Verify trading days vs calendar days

### Issue: Strategy Not Found

**Error:**
```
Failed to load strategy: 'momentum_breakout' not found in EntryRegistry
```

**Solution:**
```bash
# Verify strategy registration
python3 -c "from shared.strategy.registry import EntryRegistry; print(EntryRegistry.list_registered())"

# Check config file exists
ls -l config/strategies/stock/momentum_breakout.yaml
```

### Issue: Import Errors

**Error:**
```
ModuleNotFoundError: No module named 'clickhouse_driver'
```

**Solution:**
```bash
# Reinstall dependencies
pip install -e ".[dev]"

# Or use Docker
docker-compose run --rm app python3 scripts/run_momentum_breakout_backtest.py --mode synthetic
```

### Issue: Backtest Fails Criteria

**Scenario:** Sharpe ratio < 1.0 or negative returns

**Analysis Steps:**
1. Review trade log: `output/backtests/momentum_breakout/momentum_breakout_trades.csv`
2. Check parameter sensitivity
3. Verify data quality (outliers, gaps)
4. Consider parameter optimization: `python -m cli.main optimize --strategy momentum_breakout --trials 100`

## Integration with Paper Trading

Once backtest passes all criteria:

1. **Enable Paper Trading**
   ```bash
   # Edit config to enable
   vim config/strategies/stock/momentum_breakout.yaml
   # Set: enabled: true
   ```

2. **Start Paper Trading**
   ```bash
   python -m cli.main paper start --strategy momentum_breakout --asset stock
   ```

3. **Monitor Performance**
   ```bash
   # Check status
   python -m cli.main paper status

   # View recent trades
   python -m cli.main paper history --limit 20
   ```

4. **Track P&L (20+ Days)**
   - Monitor via dashboard or CLI
   - Compare paper performance vs backtest
   - Document cumulative P&L

## Performance Targets

Based on strategy design and Optuna optimization:

| Metric | Target Range | Notes |
|--------|--------------|-------|
| Sharpe Ratio | 1.2 - 1.8 | After 0.5% costs |
| Return (6mo) | 5% - 15% | After costs |
| Win Rate | 50% - 60% | Momentum strategy typical |
| Max Drawdown | < 10% | ATR-based risk control |
| Trade Frequency | 1-2/week | Per symbol |
| Avg Hold Time | 1-3 days | Momentum capture |

## Next Steps

1. **Run Backtest**
   ```bash
   python3 scripts/run_momentum_breakout_backtest.py --mode clickhouse --symbol 005930 --days 180
   ```

2. **Validate Results**
   - Check all acceptance criteria pass
   - Review JSON output
   - Analyze trade log

3. **Document Performance**
   - Save results to `output/backtests/momentum_breakout/`
   - Update subtask status in `implementation_plan.json`
   - Note any parameter tuning needed

4. **Proceed to Next Phase**
   - If passed: Move to Subtask 1-5 (results review)
   - If failed: Analyze and optimize parameters
   - Then: Phase 2 (Paper Trading Deployment)

## References

- Strategy Implementation: `shared/strategy/entry/momentum_breakout.py`
- Exit Strategy: `shared/strategy/exit/atr_dynamic.py`
- Config File: `config/strategies/stock/momentum_breakout.yaml`
- Backtest Engine: `shared/backtest/engine.py`
- Similar Script: `scripts/run_trend_pullback_backtest.py`
