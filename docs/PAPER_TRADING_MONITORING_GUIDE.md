# Paper Trading Monitoring Guide (20+ Trading Days)

## Overview

This guide provides comprehensive instructions for monitoring paper trading performance of the **trend_pullback** and **momentum_breakout** strategies over a 20+ trading day validation period.

**Acceptance Criteria (from spec):**
1. ✓ Cumulative P&L is positive
2. ✓ Both strategies generating signals as expected
3. ✓ No runtime errors or crashes
4. ✓ Position management working correctly (entry/exit signals firing)

**Monitoring Duration:** Minimum 20 trading days (approximately 4-5 calendar weeks)

---

## Quick Start

### Daily Monitoring (5 minutes/day)

```bash
# Run daily monitoring script
./scripts/monitor_paper_trading.sh --save

# Review output and check:
# - Total P&L trend
# - Number of active positions
# - Recent trades
```

### Weekly Deep Dive (30 minutes/week)

```bash
# Get detailed trade history
python -m cli.main paper history --limit 100 > output/monitoring/weekly_$(date +%Y%m%d).txt

# Analyze performance metrics
python -m cli.main paper stats  # If available

# Check logs for errors
tail -100 logs/paper_trading.log  # If logging is configured
```

### Final Validation (After 20+ Days)

```bash
# Run validation script
python3 scripts/validate_20day_results.py \
    --min-days 20 \
    --output output/monitoring/final_validation.json

# Review results and recommendations
cat output/monitoring/final_validation.json
```

---

## Monitoring Infrastructure

### 1. Daily Monitoring Script

**Script:** `scripts/monitor_paper_trading.sh`

**Features:**
- Fetches current paper trading status
- Displays recent trades (last 20)
- Saves daily snapshots to JSONL file
- Generates human-readable summary

**Usage:**

```bash
# Basic monitoring (display only)
./scripts/monitor_paper_trading.sh

# Save daily snapshot
./scripts/monitor_paper_trading.sh --save

# Enable notifications (when implemented)
./scripts/monitor_paper_trading.sh --save --notify
```

**Output Files:**
- `output/monitoring/daily_snapshots.jsonl` - Daily performance snapshots
- `output/monitoring/monitoring_summary.txt` - Latest summary report

**Snapshot Format (JSONL):**
```json
{"timestamp":"2026-03-06T09:00:00Z","total_pnl":1250000,"positions":3,"running":"true"}
{"timestamp":"2026-03-07T09:00:00Z","total_pnl":1420000,"positions":2,"running":"true"}
```

---

### 2. Validation Script

**Script:** `scripts/validate_20day_results.py`

**Purpose:** Automated validation of all acceptance criteria after 20+ trading days.

**Usage:**

```bash
# Basic validation (20 days minimum)
python3 scripts/validate_20day_results.py

# Custom minimum days
python3 scripts/validate_20day_results.py --min-days 25

# Save results to file
python3 scripts/validate_20day_results.py --output results.json

# With trade history file
python3 scripts/validate_20day_results.py \
    --history-file output/monitoring/trade_history.txt \
    --output results.json
```

**Validation Checks:**
1. **Trading Days:** ≥20 unique trading days with data
2. **Cumulative P&L:** Total P&L > 0 KRW
3. **Signal Generation:** Both strategies active and generating trades
4. **Runtime Stability:** No long gaps indicating crashes
5. **Position Management:** Entry and exit signals firing correctly

**Exit Codes:**
- `0` - All criteria passed
- `1` - Some criteria failed or incomplete

---

## CLI Commands Reference

### Paper Trading Status

```bash
# Current status
python -m cli.main paper status

# Expected Output:
# Paper Trading Status:
# ----------------------------------------
#   Running: True
#   Strategies: trend_pullback, momentum_breakout
#   Positions: 3/13 (max 13 combined)
#   Total P&L: +1,250,000 KRW
#   Win Rate: 58.3%
#   Total Trades: 42
```

### Trade History

```bash
# Last 20 trades
python -m cli.main paper history --limit 20

# Last 100 trades (weekly review)
python -m cli.main paper history --limit 100

# Save to file
python -m cli.main paper history --limit 100 > trade_history.txt

# Filter by strategy (if supported)
python -m cli.main paper history --strategy trend_pullback
python -m cli.main paper history --strategy momentum_breakout
```

### Performance Statistics

```bash
# Overall statistics (if available)
python -m cli.main paper stats

# Per-strategy breakdown (if available)
python -m cli.main paper stats --strategy trend_pullback
python -m cli.main paper stats --strategy momentum_breakout
```

---

## Daily Monitoring Checklist

### Every Trading Day (09:00-09:30 KST)

- [ ] **Run Monitoring Script**
  ```bash
  ./scripts/monitor_paper_trading.sh --save
  ```

- [ ] **Check Key Metrics**
  - [ ] System is running (`Running: true`)
  - [ ] P&L direction (positive trend expected)
  - [ ] Number of active positions (0-13)
  - [ ] Recent trades executed (at least 1-2 per day expected)

- [ ] **Verify Strategy Activity**
  - [ ] trend_pullback: Pullback entries on BB lower touch
  - [ ] momentum_breakout: Breakout entries with RVOL confirmation

- [ ] **Look for Issues**
  - [ ] Error messages in output
  - [ ] Unusual position counts (e.g., 0 positions for multiple days)
  - [ ] No trades for extended period (>2 days concerning)

### Weekly Review (Every Friday or Weekend)

- [ ] **Generate Weekly Report**
  ```bash
  python -m cli.main paper history --limit 100 > weekly_report_$(date +%Y%m%d).txt
  ```

- [ ] **Analyze Performance**
  - [ ] Total P&L trend (should be gradually increasing)
  - [ ] Win rate (target: 50-60%)
  - [ ] Average trades per day (target: 2-4 combined)
  - [ ] Max drawdown (should be controlled by ATR stops)

- [ ] **Review Individual Trades**
  - [ ] Entry prices reasonable (no obvious slippage issues)
  - [ ] Exit prices following ATR dynamic rules
  - [ ] Stop losses triggered appropriately
  - [ ] Trailing stops activating as expected

- [ ] **Check Strategy Distribution**
  - [ ] Both strategies generating trades
  - [ ] Roughly balanced activity (momentum_breakout may be more active)

### Milestone Checks

**After 5 Days:**
- [ ] Verify both strategies have executed at least 1 trade each
- [ ] Confirm no crashes or long outages
- [ ] Check P&L is reasonable (may be positive or slightly negative)

**After 10 Days:**
- [ ] Mid-point review: P&L should show positive trend
- [ ] 20+ total trades expected
- [ ] No systematic issues observed

**After 15 Days:**
- [ ] Strong indication of final outcome
- [ ] 30+ total trades expected
- [ ] Prepare for final validation

**After 20+ Days:**
- [ ] Run final validation script
- [ ] Document results
- [ ] Make go/no-go decision for live trading

---

## Performance Expectations

### Combined Performance (Both Strategies)

| Metric | Target Range | Notes |
|--------|-------------|-------|
| **Cumulative P&L** | Positive | Main acceptance criterion |
| **Total Trades** | 40-80 | Over 20 trading days (2-4/day avg) |
| **Win Rate** | 50-60% | Realistic for these strategy types |
| **Max Drawdown** | < 5% | ATR stops should limit losses |
| **Daily Trade Frequency** | 2-4 trades | Combined across both strategies |

### Per-Strategy Breakdown

**trend_pullback:**
- Trade Frequency: 1-2 per day
- Entry: BB lower touch + RSI < 34 OR Williams reversal
- Average Hold Time: 2-6 hours (intraday)
- Expected Win Rate: 50-60%

**momentum_breakout:**
- Trade Frequency: 1-3 per day
- Entry: Breakout + RVOL > 1.6 + accumulation ≥ 40
- Average Hold Time: 1-4 hours (momentum)
- Expected Win Rate: 50-60%

### Warning Signs

**Red Flags (Investigate Immediately):**
- No trades for 3+ consecutive trading days
- Cumulative P&L declining sharply (> -3%)
- System showing `Running: false` repeatedly
- Position count stuck at 0 or max for extended period
- Error messages in logs

**Yellow Flags (Monitor Closely):**
- Win rate < 40% after 10+ trades
- Only one strategy generating trades
- P&L flat or slightly negative after 10+ days
- Higher than expected trade frequency (>6/day)

---

## Troubleshooting

### Issue: No Trades Being Generated

**Possible Causes:**
1. Daily scanner not running (watchlist empty)
2. Time filters too restrictive
3. Market conditions not meeting entry criteria
4. Redis not accessible

**Diagnostic Steps:**
```bash
# Check daily indicators
redis-cli -n 1 GET system:daily_indicators:latest

# Verify strategy configs enabled
grep "enabled:" config/strategies/stock/trend_pullback.yaml
grep "enabled:" config/strategies/stock/momentum_breakout.yaml

# Check paper trading logs
tail -100 logs/paper_trading.log
```

**Resolution:**
- Ensure daily scanner cron job is running (08:50 KST)
- Verify Redis is accessible
- Check strategy configs have `enabled: true`

---

### Issue: P&L Negative After 15+ Days

**Possible Causes:**
1. Strategy parameters need optimization
2. Market regime not suitable (e.g., choppy market)
3. Entry/exit logic issues
4. Excessive trading costs (slippage)

**Diagnostic Steps:**
```bash
# Review all trades
python -m cli.main paper history --limit 200

# Analyze win/loss distribution
# Look for patterns in losing trades
```

**Resolution:**
- Review backtest parameters vs. actual parameters
- Consider parameter optimization if win rate < 45%
- Check if market regime changed (daily scanner context)
- May need to refine entry filters or exit rules

---

### Issue: System Crashes or Stops

**Possible Causes:**
1. Unhandled exception in strategy code
2. Infrastructure issues (Redis down or Parquet/SQLite paths unavailable)
3. Network connectivity problems
4. Memory/resource exhaustion

**Diagnostic Steps:**
```bash
# Check if services running
redis-cli -n 1 ping
sts data validate-parquet --root data/market

# Review error logs
tail -200 logs/paper_trading.log | grep -i error

# Check system resources
top -l 1 | head -10
```

**Resolution:**
- Restart paper trading if needed
- Fix infrastructure issues
- Review code for unhandled exceptions
- Increase resource limits if needed

---

### Issue: Only One Strategy Active

**Possible Causes:**
1. One strategy config disabled
2. Daily scanner not providing data for one strategy's symbols
3. One strategy's entry conditions not being met

**Diagnostic Steps:**
```bash
# Verify both strategies enabled
grep "enabled:" config/strategies/stock/*.yaml

# Check trade history for strategy distribution
python -m cli.main paper history --limit 50 | grep -E "(trend_pullback|momentum_breakout)"

# Review daily scanner output
redis-cli -n 1 GET system:daily_indicators:latest | jq '.strategies'
```

**Resolution:**
- Ensure both configs have `enabled: true`
- Verify daily scanner is populating watchlist for both strategies
- Check if market conditions favor one strategy type

---

## Data Collection & Documentation

### Files to Preserve

**Essential:**
- `output/monitoring/daily_snapshots.jsonl` - Daily performance data
- `output/monitoring/final_validation.json` - Validation results
- Weekly trade history files

**Optional but Recommended:**
- `logs/paper_trading.log` - Detailed execution logs
- Screenshots of key metrics
- Performance charts (if dashboard available)

### Documentation Template

After 20+ days, document the results:

```markdown
# Paper Trading Results (trend_pullback + momentum_breakout)

## Period
- Start Date: YYYY-MM-DD
- End Date: YYYY-MM-DD
- Trading Days: XX days

## Performance Summary
- Initial Capital: 40,000,000 KRW (10M trend + 30M momentum)
- Final Capital: XX,XXX,XXX KRW
- Total P&L: +X,XXX,XXX KRW (+X.X%)
- Total Trades: XX
- Win Rate: XX.X%
- Max Drawdown: -X.X%

## Strategy Breakdown

### trend_pullback
- Trades: XX
- Win Rate: XX.X%
- P&L: +XXX,XXX KRW
- Avg Hold Time: X.X hours

### momentum_breakout
- Trades: XX
- Win Rate: XX.X%
- P&L: +XXX,XXX KRW
- Avg Hold Time: X.X hours

## Validation Results
- [ ] ✓ Cumulative P&L positive
- [ ] ✓ Both strategies generating signals
- [ ] ✓ No runtime errors
- [ ] ✓ Position management working

## Observations
- Key insights from the monitoring period
- Notable trades (best/worst)
- Market conditions during period
- Any issues encountered and resolved

## Recommendation
- [ ] Proceed to live trading (if all criteria met)
- [ ] Continue paper trading (if borderline)
- [ ] Optimize parameters (if criteria not met)
```

---

## Integration with Next Steps

### If Validation Passes (All Criteria Met)

1. **Update implementation_plan.json**
   - Mark subtask-2-4 as `completed`
   - Add completion timestamp

2. **Document Results**
   - Fill in performance review template
   - Save final validation results
   - Update build-progress.txt

3. **Proceed to Phase 3**
   - Subtask 3-1: Verify old strategies disabled
   - Subtask 3-2: Update strategy documentation

4. **Consider Live Deployment**
   - Review risk management settings
   - Start with small capital allocation
   - Gradual scaling based on performance

### If Validation Incomplete

1. **Continue Monitoring**
   - Extend monitoring period
   - Collect more trading days
   - Re-run validation weekly

2. **Investigate Issues**
   - Follow troubleshooting guide
   - Fix any identified problems
   - Restart monitoring period if major fixes made

3. **Consider Optimization**
   - If P&L negative: Parameter tuning
   - If no signals: Entry filter adjustment
   - If high drawdown: Exit rule tightening

---

## Automation Recommendations

### Cron Job for Daily Monitoring

Add to crontab for automated daily snapshots:

```bash
# Paper trading monitoring (09:00 KST daily, Mon-Fri)
0 9 * * 1-5 cd /path/to/project && ./scripts/monitor_paper_trading.sh --save >> logs/monitoring.log 2>&1
```

### Notification Integration (Future)

Integrate with Telegram for alerts:

```python
# In monitor_paper_trading.sh
from shared.notification.telegram import TelegramNotifier

notifier = TelegramNotifier(bot_token=..., chat_id=...)
notifier.send_message(f"Paper Trading Update: P&L {pnl:,} KRW, {positions} positions")
```

---

## Support & Resources

### Related Documentation
- `docs/TREND_PULLBACK_PAPER_TRADING.md` - trend_pullback setup guide
- `docs/MOMENTUM_BREAKOUT_PAPER_TRADING.md` - momentum_breakout setup guide
- `docs/DAILY_SCANNER_VERIFICATION.md` - Daily scanner troubleshooting

### CLI Help
```bash
python -m cli.main paper --help
python -m cli.main paper status --help
python -m cli.main paper history --help
```

### Project Documentation
- `CLAUDE.md` - Overall project architecture
- `config/strategies/stock/` - Strategy configurations

---

## Quick Reference

### Daily Commands
```bash
# Morning check (5 min)
./scripts/monitor_paper_trading.sh --save

# Quick status
python -m cli.main paper status
```

### Weekly Commands
```bash
# Detailed history
python -m cli.main paper history --limit 100 > weekly_$(date +%Y%m%d).txt

# Stats review
python -m cli.main paper stats
```

### Final Validation
```bash
# After 20+ days
python3 scripts/validate_20day_results.py --output final_validation.json
```

### Emergency Commands
```bash
# Restart paper trading
python -m cli.main paper stop
python -m cli.main paper start --strategy trend_pullback --asset stock
python -m cli.main paper start --strategy momentum_breakout --asset stock

# Check infrastructure
redis-cli -n 1 ping
sts data validate-parquet --root data/market
```

---

**Last Updated:** 2026-03-06
**Version:** 1.0
**Status:** Ready for use when paper trading is active
