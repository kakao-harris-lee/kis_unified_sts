# Backtest Performance Review
## Stock Strategy Redesign - Validation Results

**Task:** 007-stock-strategy-redesign-trend-pullback-momentum-br
**Date:** 2026-03-05
**Review Status:** ⏳ AWAITING BACKTEST EXECUTION

---

## Executive Summary

This document tracks the backtest validation results for the two new stock strategies:
- `trend_pullback`: Daily SMA filter + intraday BB/Williams trigger + ATR dynamic exit
- `momentum_breakout`: Daily high proximity + volume trend + breakout trigger + ATR exit

**Acceptance Criteria:** Both strategies must achieve Sharpe Ratio > 1.0 after 0.5% round-trip costs on 6+ months of data.

---

## Status Overview

| Strategy | Backtest Status | Sharpe Ratio | Net Return | Trades | Acceptance |
|----------|----------------|--------------|------------|--------|------------|
| **trend_pullback** | ⏳ Pending | TBD | TBD | TBD | ⏳ Pending |
| **momentum_breakout** | ⏳ Pending | TBD | TBD | TBD | ⏳ Pending |

**Overall Status:** Infrastructure ready, awaiting execution

---

## 1. trend_pullback Strategy

### Configuration
- **Entry Logic:** BB lower touch + RSI < 34 OR Williams %R reversal
- **Exit Logic:** ATR dynamic trailing stop (3.5x stop, 2.0x trail)
- **Position Size:** Fixed 1M KRW per position
- **Max Positions:** 5
- **Time Filter:** Skip first 30min and last 15min
- **Cooldown:** 120 seconds

### Backtest Results

#### Performance Metrics
```
Status: ⏳ AWAITING EXECUTION

Expected after execution:
- Total Return: __%
- Sharpe Ratio: __
- Max Drawdown: __%
- Win Rate: __%
- Calmar Ratio: __
```

#### Trade Statistics
```
- Total Trades: __
- Winning Trades: __
- Losing Trades: __
- Average Win: __%
- Average Loss: __%
- Profit Factor: __
```

#### Risk Metrics
```
- Max Drawdown: __%
- Max Consecutive Losses: __
- Average Holding Period: __ bars
- Round-trip Cost Applied: 0.5%
```

#### Acceptance Criteria Checklist
- [ ] **Sharpe Ratio > 1.0** - Actual: TBD
- [ ] **Positive Net Returns** - Actual: TBD
- [ ] **Reasonable Trade Count** (5 ≤ trades ≤ bars/20) - Actual: TBD
- [ ] **0.5% Round-trip Costs Applied** - Verified: TBD
- [ ] **MLflow Tracking Logged** - Verified: TBD

### Analysis & Findings

**Strengths:**
- TBD after execution

**Weaknesses:**
- TBD after execution

**Observations:**
- TBD after execution

### Tuning Opportunities

If Sharpe < 1.0, consider:
1. **Entry Thresholds:** Adjust RSI threshold (current: 34) or Williams threshold
2. **Exit Parameters:** Tune ATR multipliers (stop: 3.5x, trail: 2.0x)
3. **Time Filters:** Modify skip periods (current: first 30min, last 15min)
4. **Position Sizing:** Test dynamic sizing vs fixed
5. **Cooldown Period:** Adjust 120s cooldown for optimal signal spacing

---

## 2. momentum_breakout Strategy

### Configuration
- **Entry Logic:** Breakout detection + RVOL > 1.6 + accumulation score ≥ 40
- **Trend Mode:** Relaxed thresholds in BULL + EMA pullback (5/20/60)
- **Exit Logic:** ATR dynamic (2.0x stop, 2.0x trail activation, 1.5x trail distance)
- **Position Size:** Fixed 3M KRW per position
- **Max Positions:** 8
- **Time Filter:** Skip first 10min and last 10min
- **Cooldown:** 120 seconds

### Backtest Results

#### Performance Metrics
```
Status: ⏳ AWAITING EXECUTION

Expected after execution:
- Total Return: __%
- Sharpe Ratio: __
- Max Drawdown: __%
- Win Rate: __%
- Calmar Ratio: __
```

#### Trade Statistics
```
- Total Trades: __
- Winning Trades: __
- Losing Trades: __
- Average Win: __%
- Average Loss: __%
- Profit Factor: __
```

#### Risk Metrics
```
- Max Drawdown: __%
- Max Consecutive Losses: __
- Average Holding Period: __ bars
- Round-trip Cost Applied: 0.5%
```

#### Acceptance Criteria Checklist
- [ ] **Sharpe Ratio > 1.0** - Actual: TBD
- [ ] **Positive Net Returns** - Actual: TBD
- [ ] **Reasonable Trade Count** (5 ≤ trades ≤ bars/20) - Actual: TBD
- [ ] **0.5% Round-trip Costs Applied** - Verified: TBD
- [ ] **MLflow Tracking Logged** - Verified: TBD

### Analysis & Findings

**Strengths:**
- TBD after execution

**Weaknesses:**
- TBD after execution

**Observations:**
- TBD after execution

### Tuning Opportunities

If Sharpe < 1.0, consider:
1. **Entry Thresholds:** Adjust RVOL threshold (current: 1.6) or accumulation score (40)
2. **Breakout Detection:** Tune breakout sensitivity and confirmation bars
3. **Exit Parameters:** Adjust ATR multipliers (stop: 2.0x, trail activation: 2.0x, trail distance: 1.5x)
4. **Trend Mode:** Modify EMA periods (current: 5/20/60) or BULL regime filters
5. **Position Sizing:** Test portfolio heat vs fixed sizing
6. **Time Filters:** Adjust skip periods (current: first 10min, last 10min)

---

## Comparative Analysis

### Strategy Comparison

| Metric | trend_pullback | momentum_breakout | Winner |
|--------|----------------|-------------------|--------|
| **Sharpe Ratio** | TBD | TBD | TBD |
| **Total Return** | TBD | TBD | TBD |
| **Max Drawdown** | TBD | TBD | TBD |
| **Win Rate** | TBD | TBD | TBD |
| **Profit Factor** | TBD | TBD | TBD |
| **Avg Trade Duration** | TBD | TBD | TBD |

### Strategy Characteristics

**trend_pullback:**
- Philosophy: Mean reversion with trend filter
- Entry: Pullbacks to support levels
- Best Market: Ranging with clear support/resistance
- Risk Profile: Lower position size (1M), more conservative

**momentum_breakout:**
- Philosophy: Momentum continuation
- Entry: Breakouts with volume confirmation
- Best Market: Trending with strong directional moves
- Risk Profile: Higher position size (3M), more aggressive

### Complementarity

The two strategies are designed to complement each other:
- **trend_pullback** captures reversals and oversold bounces
- **momentum_breakout** captures breakouts and continuation moves
- Together they should provide diversification across market regimes

---

## Data Quality Assessment

### Data Coverage
```
Symbol: __ (primary test symbol, e.g., 005930)
Start Date: ____-__-__
End Date: ____-__-__
Total Bars: ______
Trading Days: ___ days (__ months)
Data Completeness: ___%
```

### Data Quality Checks
- [ ] No gaps > 5 consecutive bars
- [ ] Volume data present and non-zero
- [ ] OHLC relationships valid (O,C within H,L)
- [ ] No extreme outliers (circuit breakers handled)
- [ ] Minimum 6 months of data confirmed

---

## Execution Details

### Environment
- Python Version: 3.11+
- Data Source: Parquet market data (`data/market`)
- Backtest Engine: `shared/backtest/engine.py`
- MLflow Tracking: Enabled/Disabled

### Commands Used

**trend_pullback:**
```bash
python3 scripts/run_trend_pullback_backtest.py \
    --mode parquet \
    --symbol 005930 \
    --days 180 \
    --output-dir ./output/backtests/trend_pullback
```

**momentum_breakout:**
```bash
python3 scripts/run_momentum_breakout_backtest.py \
    --mode parquet \
    --symbol 005930 \
    --days 180 \
    --output-dir ./output/backtests/momentum_breakout
```

**Validation:**
```bash
python3 scripts/validate_backtest_results.py \
    --trend-pullback output/backtests/trend_pullback/results.json \
    --momentum-breakout output/backtests/momentum_breakout/results.json \
    --show-details
```

### Output Files
- `output/backtests/trend_pullback/results.json` - Performance metrics
- `output/backtests/trend_pullback/trades.csv` - Trade log
- `output/backtests/trend_pullback/equity_curve.csv` - Equity curve
- `output/backtests/momentum_breakout/results.json` - Performance metrics
- `output/backtests/momentum_breakout/trades.csv` - Trade log
- `output/backtests/momentum_breakout/equity_curve.csv` - Equity curve

---

## Recommendations

### If Both Strategies Pass (Sharpe > 1.0)

**Action:** Proceed to Phase 2 - Paper Trading Deployment

1. **Enable Strategies in Production Config**
   ```yaml
   # config/strategies/stock/trend_pullback.yaml
   enabled: true

   # config/strategies/stock/momentum_breakout.yaml
   enabled: true
   ```

2. **Start Paper Trading** (Subtask 2-2, 2-3)
   ```bash
   python -m cli.main paper start --strategy trend_pullback --asset stock
   python -m cli.main paper start --strategy momentum_breakout --asset stock
   ```

3. **Monitor for 20+ Trading Days** (Subtask 2-4)
   - Track daily P&L via CLI or dashboard
   - Verify signal generation matches expectations
   - Watch for runtime errors or crashes

4. **Disable Old Strategies** (Subtask 3-1)
   - Confirm bb_reversion, opening_volume_surge, volume_accumulation, williams_r remain disabled

### If One or Both Strategies Fail (Sharpe ≤ 1.0)

**Action:** Investigate and Optimize

#### Investigation Steps

1. **Review Trade Log**
   - Check `trades.csv` for patterns in losses
   - Identify if losses cluster in specific market conditions
   - Look for entry/exit timing issues

2. **Analyze Equity Curve**
   - Check for long drawdown periods
   - Identify regime changes that affected performance
   - Look for parameter sensitivity

3. **Check Data Quality**
   - Verify no gaps or anomalies in test period
   - Confirm symbol had sufficient liquidity
   - Check if test period was representative

#### Optimization Approaches

**Option A: Parameter Tuning (Recommended First)**

Use Optuna to re-optimize strategy parameters:

```bash
# trend_pullback optimization
python -m cli.main optimize \
    --strategy trend_pullback \
    --asset stock \
    --data output/backtests/trend_pullback/data.csv \
    --trials 100 \
    --metric sharpe_ratio

# momentum_breakout optimization
python -m cli.main optimize \
    --strategy momentum_breakout \
    --asset stock \
    --data output/backtests/momentum_breakout/data.csv \
    --trials 100 \
    --metric sharpe_ratio
```

**Option B: Strategy Logic Refinement**

1. Review entry conditions - too loose or too tight?
2. Review exit logic - stops too tight or too loose?
3. Consider adding additional filters (regime, volatility, etc.)
4. Review position sizing - fixed vs dynamic

**Option C: Alternative Data Period**

- Test on different 6-month periods
- Check if results are period-specific
- Consider walk-forward analysis

### If Critical Issues Found

**Blockers that require code changes:**
- Strategy logic bugs (implement and retest)
- Missing filters or edge cases (add and retest)
- Configuration errors (fix and retest)

---

## Next Steps

### Current Status (2026-03-05)

**AWAITING BACKTEST EXECUTION**

The infrastructure for running backtests is complete:
- ✅ Backtest execution scripts created
- ✅ Validation script created
- ✅ Performance review template created
- ✅ Output directories prepared
- ⏳ Python environment setup required
- ⏳ Parquet data verification needed
- ⏳ Actual backtest execution pending

### Immediate Actions Required

**To Execute Backtests:**

1. **Option A: Use GitHub Actions CI (RECOMMENDED)**
   ```bash
   git add docs/BACKTEST_PERFORMANCE_REVIEW.md scripts/validate_backtest_results.py
   git commit -m "feat: add backtest validation infrastructure"
   git push -u origin auto-claude/007-stock-strategy-redesign-trend-pullback-momentum-br
   ```
   - CI has proper Python 3.11 environment
   - All dependencies available
   - Can use synthetic data for validation

2. **Option B: Local Execution** (when environment ready)
   ```bash
   # Verify data
   python3 scripts/verify_backtest_data.py

   # Run backtests
   python3 scripts/run_trend_pullback_backtest.py --mode parquet --symbol 005930 --days 180
   python3 scripts/run_momentum_breakout_backtest.py --mode parquet --symbol 005930 --days 180

   # Validate results
   python3 scripts/validate_backtest_results.py \
       --trend-pullback output/backtests/trend_pullback/results.json \
       --momentum-breakout output/backtests/momentum_breakout/results.json \
       --show-details
   ```

3. **Update This Document**
   - Fill in TBD sections with actual results
   - Complete checklists
   - Add analysis and findings
   - Make recommendations

### Phase 2 Preparation

While awaiting backtest results, prepare for paper trading:
- [ ] Verify daily scanner cron job is running (Subtask 2-1)
- [ ] Review paper trading infrastructure
- [ ] Prepare monitoring dashboard
- [ ] Set up alerting for strategy signals

---

## Appendix

### Acceptance Criteria Matrix

| Criterion | Threshold | trend_pullback | momentum_breakout |
|-----------|-----------|----------------|-------------------|
| Sharpe Ratio | > 1.0 | TBD | TBD |
| Net Returns | > 0% | TBD | TBD |
| Trade Count | 5 to bars/20 | TBD | TBD |
| Round-trip Costs | 0.5% | TBD | TBD |
| MLflow Logs | Saved | TBD | TBD |

### Reference Links

- **Spec:** `.auto-claude/specs/007-stock-strategy-redesign-trend-pullback-momentum-br/spec.md`
- **Implementation Plan:** `.auto-claude/specs/007-stock-strategy-redesign-trend-pullback-momentum-br/implementation_plan.json`
- **Build Progress:** `.auto-claude/specs/007-stock-strategy-redesign-trend-pullback-momentum-br/build-progress.txt`

### Strategy Code Locations

- **trend_pullback Entry:** `shared/strategy/entry/trend_pullback.py`
- **momentum_breakout Entry:** `shared/strategy/entry/momentum_breakout.py`
- **atr_dynamic Exit:** `shared/strategy/exit/atr_dynamic.py`
- **trend_pullback Config:** `config/strategies/stock/trend_pullback.yaml`
- **momentum_breakout Config:** `config/strategies/stock/momentum_breakout.yaml`

### Related Documentation

- **Backtest Guides:**
  - `scripts/TREND_PULLBACK_BACKTEST_GUIDE.md`
  - `scripts/MOMENTUM_BREAKOUT_BACKTEST_GUIDE.md`
  - `scripts/prepare_backtest_data.md`

- **Execution Summaries:**
  - `scripts/BACKTEST_EXECUTION_SUMMARY.md`
  - `scripts/MOMENTUM_BACKTEST_EXECUTION_SUMMARY.md`

---

**Document Status:** Template created, awaiting backtest execution
**Last Updated:** 2026-03-05
**Next Review:** After backtest execution completes
