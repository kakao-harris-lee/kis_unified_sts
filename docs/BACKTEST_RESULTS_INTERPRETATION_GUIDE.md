# Backtest Results Interpretation Guide

## How to Review and Act on Backtest Results

This guide provides step-by-step instructions for interpreting backtest results and making data-driven decisions about strategy deployment.

---

## Quick Start Checklist

Once backtest results are available:

1. **Run Automated Validation**
   ```bash
   python3 scripts/validate_backtest_results.py \
       --trend-pullback output/backtests/trend_pullback/results.json \
       --momentum-breakout output/backtests/momentum_breakout/results.json \
       --show-details
   ```

2. **Review Automated Report**
   - Check if all acceptance criteria passed (✓)
   - Note which criteria failed (✗)
   - Read overall recommendation

3. **Manual Deep Dive** (if criteria failed)
   - Review trade logs
   - Analyze equity curves
   - Identify patterns in losses

4. **Make Decision**
   - Pass → Proceed to paper trading
   - Fail → Optimize parameters or refine logic

---

## Understanding the Metrics

### Core Performance Metrics

#### 1. Sharpe Ratio (PRIMARY CRITERION)

**Definition:** Risk-adjusted return metric (return / volatility)

**Interpretation:**
- **> 2.0** - Excellent (institutional quality)
- **1.5 - 2.0** - Very Good (strong performance)
- **1.0 - 1.5** - Good (acceptable, meets criteria)
- **0.5 - 1.0** - Marginal (FAILS acceptance criteria)
- **< 0.5** - Poor (significant optimization needed)

**Why It Matters:**
- Measures return per unit of risk
- Accounts for volatility (important for intraday)
- Industry standard for strategy comparison

**What to Do:**
- **≥ 1.0:** Proceed to next validation step
- **< 1.0:** Investigate causes (see Diagnostic Process below)

#### 2. Total Return

**Definition:** Net profit/loss as percentage of initial capital

**Interpretation:**
- **Positive:** Strategy is profitable (meets criteria)
- **Negative:** Strategy loses money (FAILS)
- **Context Matters:** 5% over 6 months is decent, 50% is suspicious

**What to Watch:**
- Return should be positive after 0.5% round-trip costs
- Abnormally high returns (>30% over 6 months) may indicate:
  - Overfitting to test period
  - Unrealistic assumptions (slippage, fees)
  - Data quality issues

**What to Do:**
- **Positive & Reasonable:** ✓ Pass
- **Negative:** Investigate (see Diagnostic Process)
- **Too High:** Check for overfitting

#### 3. Maximum Drawdown

**Definition:** Largest peak-to-trough decline in equity

**Interpretation:**
- **< 5%** - Very Good (conservative)
- **5-10%** - Good (acceptable)
- **10-15%** - Moderate (watchful)
- **> 15%** - High (concerning for intraday)

**Why It Matters:**
- Indicates worst-case loss scenario
- Affects position sizing and risk management
- Psychological impact on live trading

**What to Do:**
- **< 10%:** ✓ Acceptable
- **> 10%:** Review stop-loss logic and position sizing

#### 4. Win Rate

**Definition:** Percentage of trades that are profitable

**Interpretation:**
- **> 60%** - High (good, but check profit factor)
- **50-60%** - Typical (expected for most strategies)
- **40-50%** - Low but OK (if avg win > avg loss)
- **< 40%** - Concerning (may be flawed logic)

**Context:**
- Win rate alone doesn't determine profitability
- Must be balanced with profit factor (avg win / avg loss)

**What to Do:**
- **≥ 50%:** ✓ Acceptable
- **< 50%:** Check if profit factor compensates (needs to be > 2.0)

#### 5. Profit Factor

**Definition:** Gross profit / Gross loss

**Interpretation:**
- **> 2.0** - Excellent
- **1.5 - 2.0** - Very Good
- **1.2 - 1.5** - Good
- **1.0 - 1.2** - Marginal
- **< 1.0** - Losing strategy

**Why It Matters:**
- Measures efficiency of wins vs losses
- Low win rate OK if profit factor high

**What to Do:**
- **> 1.5:** ✓ Strong
- **< 1.2:** Review exit logic (exits may be premature)

---

## Trade Statistics Analysis

### Trade Count

**Expected Range:** 5 to (num_bars / 20)

For 6 months of 1-minute data (~46,800 bars per symbol):
- **Minimum:** 5 trades (avoid overfitting)
- **Maximum:** ~2,340 trades (avoid over-trading)
- **Typical:** 50-200 trades (1-2 per week reasonable)

**Red Flags:**
- **< 5 trades:** Not enough data, strategy too selective
- **> bars/20:** Over-trading, likely false signals
- **All trades in one day:** Strategy may be exploiting anomaly

### Average Win vs Average Loss

**Ideal Ratio:** Avg Win / Avg Loss > 1.5

**Interpretations:**
- **Ratio > 2.0:** Excellent, letting winners run
- **Ratio 1.5-2.0:** Good, balanced
- **Ratio 1.0-1.5:** Marginal, exits may be premature
- **Ratio < 1.0:** Poor, cutting winners too early

**What to Do:**
- **> 1.5:** ✓ Good exit logic
- **< 1.5:** Review trail stop parameters (ATR multipliers)

### Maximum Consecutive Losses

**Interpretation:**
- **< 3:** Excellent
- **3-5:** Normal
- **6-10:** Concerning (may indicate regime blindness)
- **> 10:** Critical (strategy fails in certain conditions)

**What to Do:**
- **> 5:** Investigate time periods of losses
- Check if all losses occurred in specific market regime
- May need regime filter or circuit breaker

---

## Diagnostic Process

### If Sharpe Ratio < 1.0

**Step 1: Check Data Quality**
```bash
# Verify data completeness
python3 scripts/verify_backtest_data.py
```

Issues to look for:
- Gaps in data (missing bars)
- Abnormal price movements (data errors)
- Low liquidity periods (distorted signals)

**Step 2: Review Trade Log**

Open `output/backtests/{strategy}/trades.csv`

Questions to answer:
1. **Are losses clustered in time?**
   - If yes → Strategy fails in specific regime
   - Solution: Add regime filter or skip volatile periods

2. **Are losses clustered by symbol?**
   - If yes → Strategy doesn't work for certain stocks
   - Solution: Add stock selection criteria

3. **Are exits premature?**
   - Check if stops hit frequently
   - Solution: Widen stop multiplier or use time-based stops

4. **Are entries poor?**
   - Check if price immediately moves against position
   - Solution: Add confirmation bars or tighter filters

**Step 3: Analyze Equity Curve**

Open `output/backtests/{strategy}/equity_curve.csv` in spreadsheet

Patterns to identify:
- **Long flat periods:** Strategy not generating signals
- **Sharp drawdowns:** Stops not working or over-leveraged
- **Volatility spikes:** Strategy confused by market regime
- **Drift downward:** Slow bleed (death by 1000 cuts)

**Step 4: Parameter Sensitivity**

Test if small parameter changes drastically affect results:

```bash
# Re-run with slightly different parameters
# Example: Change RSI threshold from 34 to 30
```

If results change significantly:
- **Unstable:** Strategy is overfitted to exact parameters
- **Stable:** Strategy has robust logic, just needs tuning

### If Net Returns Negative

**Primary Causes:**

1. **Costs Too High**
   - Check: `total_costs` in results
   - Solution: Trade less frequently (increase cooldown)

2. **Poor Exit Logic**
   - Check: Avg loss > Avg win
   - Solution: Adjust stop-loss multipliers

3. **Wrong Market Regime**
   - Check: Did test period have trending vs ranging market?
   - Solution: Test on different period or add regime filter

4. **Entry Logic Flawed**
   - Check: Win rate < 40%
   - Solution: Tighten entry filters or add confirmation

### If Trade Count Outside Range

**Too Few Trades (< 5):**

Causes:
- Filters too restrictive
- Cooldown too long
- Entry conditions too specific

Solutions:
- Relax RSI/RVOL thresholds
- Reduce cooldown from 120s to 60s
- Check if watchlist filtering is too aggressive

**Too Many Trades (> bars/20):**

Causes:
- Filters too loose
- Generating signals on noise
- No cooldown or too short

Solutions:
- Tighten entry thresholds
- Add confirmation bars requirement
- Increase cooldown
- Add regime filter to skip choppy periods

---

## Decision Matrix

Based on validation results, follow this decision tree:

### Both Strategies Pass (Sharpe > 1.0)

**✅ GREEN LIGHT - Proceed to Paper Trading**

Actions:
1. Update `docs/BACKTEST_PERFORMANCE_REVIEW.md` with final metrics
2. Enable strategies in production config (`enabled: true`)
3. Start paper trading (Phase 2)
4. Monitor for 20+ trading days

### One Strategy Passes, One Fails

**🟡 YELLOW LIGHT - Partial Success**

Actions:
1. Deploy passing strategy to paper trading
2. Optimize failing strategy parameters
3. Re-run backtest on failing strategy
4. Document findings in performance review

Options for failing strategy:
- **Option A:** Re-optimize with Optuna (100+ trials)
- **Option B:** Refine entry/exit logic based on diagnostics
- **Option C:** Defer to post-paper-trading review

### Both Strategies Fail (Sharpe ≤ 1.0)

**🔴 RED LIGHT - Optimization Required**

**Do NOT proceed to paper trading yet.**

Actions:
1. Complete diagnostic process for both strategies
2. Identify root causes (data, logic, parameters)
3. Choose optimization approach:

**Option A: Parameter Optimization (Recommended)**

```bash
# Automated parameter search with Optuna
python -m cli.main optimize \
    --strategy trend_pullback \
    --asset stock \
    --data <path> \
    --trials 100 \
    --metric sharpe_ratio \
    --direction maximize
```

Run 100+ trials to find optimal parameters. Optuna will:
- Search parameter space intelligently
- Track best configurations
- Save results to MLflow

**Option B: Logic Refinement**

If diagnostics reveal fundamental issues:
1. Review strategy code (`shared/strategy/entry/*.py`)
2. Add missing filters or conditions
3. Update config with refined logic
4. Re-run backtest

**Option C: Alternative Approach**

If strategies are fundamentally flawed:
1. Consider different strategy types
2. Review original problem analysis
3. May need to redesign approach

---

## Parameter Tuning Guide

### trend_pullback Parameters

**Entry Tuning:**

| Parameter | Current | Range to Test | Impact |
|-----------|---------|---------------|--------|
| `rsi_threshold` | 34 | 25-40 | Lower = more signals |
| `williams_threshold` | -85 | -90 to -80 | Lower = fewer signals |
| `bb_std_dev` | 2.0 | 1.5-2.5 | Lower = more touches |

**Exit Tuning:**

| Parameter | Current | Range to Test | Impact |
|-----------|---------|---------------|--------|
| `stop_multiplier` | 3.5 | 2.0-5.0 | Higher = wider stops |
| `trail_multiplier` | 2.0 | 1.5-3.0 | Higher = trail later |
| `trail_distance` | 1.0 | 0.5-2.0 | Higher = wider trail |

**Filter Tuning:**

| Parameter | Current | Range to Test | Impact |
|-----------|---------|---------------|--------|
| `skip_first_mins` | 30 | 10-60 | Avoid open volatility |
| `skip_last_mins` | 15 | 10-30 | Avoid close uncertainty |
| `cooldown_seconds` | 120 | 60-300 | Trade frequency |

### momentum_breakout Parameters

**Entry Tuning:**

| Parameter | Current | Range to Test | Impact |
|-----------|---------|---------------|--------|
| `rvol_threshold` | 1.6 | 1.2-2.5 | Lower = more signals |
| `accumulation_score` | 40 | 30-60 | Lower = more signals |
| `breakout_pct` | 0.5 | 0.3-1.0 | Breakout sensitivity |

**Exit Tuning:**

| Parameter | Current | Range to Test | Impact |
|-----------|---------|---------------|--------|
| `stop_multiplier` | 2.0 | 1.5-3.0 | Higher = wider stops |
| `trail_activation` | 2.0 | 1.5-3.0 | When trail starts |
| `trail_distance` | 1.5 | 1.0-2.5 | Trail tightness |

**Trend Mode Tuning:**

| Parameter | Current | Range to Test | Impact |
|-----------|---------|---------------|--------|
| `ema_fast` | 5 | 3-10 | Pullback detection |
| `ema_mid` | 20 | 15-30 | Trend reference |
| `ema_slow` | 60 | 40-80 | Major trend |

---

## Optimization Workflow

### Using Optuna (Automated)

**Step 1: Prepare Data**
```bash
# Ensure Parquet has 6+ months of data
python3 scripts/verify_backtest_data.py
```

**Step 2: Run Optimization**
```bash
# trend_pullback
python -m cli.main optimize \
    --strategy trend_pullback \
    --asset stock \
    --data parquet \
    --symbol 005930 \
    --days 180 \
    --trials 100 \
    --metric sharpe_ratio \
    --direction maximize \
    --timeout 3600

# momentum_breakout
python -m cli.main optimize \
    --strategy momentum_breakout \
    --asset stock \
    --data parquet \
    --symbol 005930 \
    --days 180 \
    --trials 100 \
    --metric sharpe_ratio \
    --direction maximize \
    --timeout 3600
```

**Step 3: Review Results**
```bash
# View best parameters in MLflow UI
python -m cli.main mlflow ui

# Or check optimization logs
cat logs/optuna_trend_pullback.log
```

**Step 4: Update Config**

Copy best parameters to strategy YAML:

```yaml
# config/strategies/stock/trend_pullback.yaml
strategy:
  entry:
    params:
      rsi_threshold: 32  # Updated from 34
      # ... other optimized params
```

**Step 5: Validate**

Re-run backtest with optimized parameters:
```bash
python3 scripts/run_trend_pullback_backtest.py \
    --mode parquet \
    --symbol 005930 \
    --days 180
```

**Step 6: Confirm Improvement**
```bash
python3 scripts/validate_backtest_results.py \
    --strategy-name trend_pullback \
    --results output/backtests/trend_pullback/results.json
```

### Manual Tuning (Targeted)

If you know which parameter to adjust:

1. **Edit Config**
   ```bash
   vim config/strategies/stock/trend_pullback.yaml
   ```

2. **Run Single Backtest**
   ```bash
   python3 scripts/run_trend_pullback_backtest.py --mode parquet --symbol 005930 --days 180
   ```

3. **Compare Results**
   - Note Sharpe ratio change
   - Check if trade count changed
   - Review equity curve

4. **Iterate**
   - Adjust parameter incrementally
   - Re-run backtest
   - Track improvements

---

## Common Issues and Solutions

### Issue: Sharpe is 0.8 (close but not quite)

**Diagnosis:**
- Strategy is almost there
- Likely parameter tuning needed
- Not a fundamental flaw

**Solution:**
1. Run Optuna optimization (100 trials)
2. Focus on exit parameters (ATR multipliers)
3. Consider slightly looser entry filters

### Issue: Sharpe is 0.3 (far from target)

**Diagnosis:**
- Strategy has fundamental issues
- Parameters alone won't fix it
- Need logic review

**Solution:**
1. Review trade log for patterns
2. Check if entry timing is poor (price immediately moves against)
3. Check if exit timing is poor (stops hit frequently)
4. May need to add regime filter or refine entry conditions

### Issue: High Sharpe (2.5+) but few trades (< 10)

**Diagnosis:**
- Overfitting risk
- Not enough trades to be confident
- May not generalize to live trading

**Solution:**
1. Test on different time period (out-of-sample)
2. Relax entry filters to generate more signals
3. Consider if strategy is too selective

### Issue: Negative returns despite positive Sharpe

**Diagnosis:**
- Impossible mathematically (Sharpe formula requires positive numerator for positive ratio)
- Likely data or calculation error

**Solution:**
1. Check results JSON for errors
2. Re-run backtest
3. Verify cost calculation (0.5% applied correctly)

---

## Documentation Requirements

Once validation is complete, update the following:

### 1. Performance Review Document

File: `docs/BACKTEST_PERFORMANCE_REVIEW.md`

Fill in all TBD sections:
- Actual metric values
- Completed checklists
- Analysis & findings
- Recommendations

### 2. Build Progress

File: `.auto-claude/specs/007-.../build-progress.txt`

Add section:
```
## Subtask 1-5: Review backtest results (COMPLETED)

**Status:** COMPLETED
**Date:** ____-__-__

### Summary
Both strategies validated against acceptance criteria.

**trend_pullback:**
- Sharpe Ratio: __ (PASS/FAIL)
- Net Return: __% (PASS/FAIL)
- Trade Count: __ (PASS/FAIL)
- Overall: PASS/FAIL

**momentum_breakout:**
- Sharpe Ratio: __ (PASS/FAIL)
- Net Return: __% (PASS/FAIL)
- Trade Count: __ (PASS/FAIL)
- Overall: PASS/FAIL

### Decision
[Proceed to paper trading / Optimize parameters / Refine logic]

### Next Steps
[List specific actions based on results]
```

### 3. Implementation Plan

File: `.auto-claude/specs/007-.../implementation_plan.json`

Update subtask-1-5:
```json
{
  "id": "subtask-1-5",
  "status": "completed",
  "notes": "Validated both strategies. [PASS/FAIL summary]. [Next actions].",
  "updated_at": "____-__-__T__:__:__"
}
```

---

## Summary Checklist

Before marking subtask-1-5 complete:

- [ ] Backtest execution completed for both strategies
- [ ] Automated validation script run successfully
- [ ] Performance review document updated with actual metrics
- [ ] All acceptance criteria checkboxes marked (✓ or ✗)
- [ ] Analysis and findings documented
- [ ] Decision made (proceed/optimize/refine)
- [ ] Recommendations documented
- [ ] Build progress updated
- [ ] Implementation plan updated

**Only then:** Mark subtask-1-5 as completed and proceed to next phase.

---

## Quick Reference Commands

```bash
# Validate results (both strategies)
python3 scripts/validate_backtest_results.py \
    --trend-pullback output/backtests/trend_pullback/results.json \
    --momentum-breakout output/backtests/momentum_breakout/results.json \
    --show-details

# Validate single strategy
python3 scripts/validate_backtest_results.py \
    --strategy-name trend_pullback \
    --results output/backtests/trend_pullback/results.json \
    --show-details

# Re-run backtest (if needed)
python3 scripts/run_trend_pullback_backtest.py --mode parquet --symbol 005930 --days 180
python3 scripts/run_momentum_breakout_backtest.py --mode parquet --symbol 005930 --days 180

# Optimize parameters (if Sharpe < 1.0)
python -m cli.main optimize \
    --strategy trend_pullback --asset stock --data parquet \
    --symbol 005930 --days 180 --trials 100 --metric sharpe_ratio

# View trades
cat output/backtests/trend_pullback/trades.csv | column -t -s,

# Plot equity curve (if gnuplot available)
gnuplot -e "set datafile separator ','; plot 'output/backtests/trend_pullback/equity_curve.csv' using 1:2 with lines"
```

---

**Document Status:** Complete guide for results interpretation
**Last Updated:** 2026-03-05
