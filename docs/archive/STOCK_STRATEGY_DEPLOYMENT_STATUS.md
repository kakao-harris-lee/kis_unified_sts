# Stock Strategy Deployment Status - Quick Reference

**Last Updated:** 2026-03-06
**Task:** 007-stock-strategy-redesign-trend-pullback-momentum-br

---

## Current Deployment Status

### Production Status: PENDING VALIDATION

| Strategy | Development | Unit Tests | Backtest | Paper Trading | Production |
|----------|-------------|------------|----------|---------------|------------|
| **trend_pullback** | ✓ Complete | ✓ Passing | ⏳ Pending | ⏳ Pending | ⏳ Blocked |
| **momentum_breakout** | ✓ Complete | ✓ Passing | ⏳ Pending | ⏳ Pending | ⏳ Blocked |

### Legacy Strategies: DISABLED

| Strategy | Status | Reason |
|----------|--------|--------|
| bb_reversion | DISABLED | Negative Sharpe, replaced by trend_pullback |
| opening_volume_surge | DISABLED | Negative Sharpe, no daily context |
| volume_accumulation | DISABLED | Negative Sharpe, replaced by momentum_breakout |
| williams_r | DISABLED | Negative Sharpe |

---

## Quick Actions

### For Developers

**Run Unit Tests:**
```bash
pytest tests/unit/strategy/test_trend_pullback_entry.py \
       tests/unit/strategy/test_momentum_breakout_entry.py -v
```

**Run Backtests:**
```bash
# trend_pullback
python3 scripts/run_trend_pullback_backtest.py --mode clickhouse --symbol 005930 --days 180

# momentum_breakout
python3 scripts/run_momentum_breakout_backtest.py --mode clickhouse --symbol 005930 --days 180
```

**Validate Results:**
```bash
python3 scripts/validate_backtest_results.py \
    --trend-pullback output/backtests/trend_pullback/results.json \
    --momentum-breakout output/backtests/momentum_breakout/results.json
```

### For Operators

**Start Paper Trading:**
```bash
# trend_pullback
./scripts/start_trend_pullback_paper.sh

# momentum_breakout
./scripts/start_momentum_breakout_paper.sh
```

**Monitor Daily:**
```bash
./scripts/monitor_paper_trading.sh --save
```

**Check Status:**
```bash
python -m cli.main paper status
```

### For Analysts

**Review Performance:**
- Backtest results: `docs/BACKTEST_PERFORMANCE_REVIEW.md`
- Paper trading results: `output/monitoring/daily_snapshots.jsonl`
- Validation summary: `docs/STOCK_STRATEGY_VALIDATION_SUMMARY.md`

---

## Validation Checklist

### Phase 1: Backtest Validation

- [ ] Data collected (6+ months, multiple symbols)
- [ ] Backtests executed (trend_pullback + momentum_breakout)
- [ ] Sharpe ratio > 1.0 achieved (both strategies)
- [ ] Results documented in BACKTEST_PERFORMANCE_REVIEW.md
- [ ] Acceptance criteria met

### Phase 2: Paper Trading Validation

- [ ] Daily scanner verified and running
- [ ] Paper trading started (both strategies)
- [ ] Daily monitoring active (20+ days)
- [ ] Positive cumulative P&L achieved
- [ ] No runtime errors or crashes
- [ ] Results documented in STOCK_STRATEGY_VALIDATION_SUMMARY.md

### Phase 3: Production Deployment

- [ ] All validations passed
- [ ] Deployment decision made
- [ ] Production configs updated (`enabled: true`)
- [ ] Legacy strategies fully decommissioned
- [ ] Production monitoring active

---

## Contact & Escalation

**Documentation:**
- Full validation summary: `docs/STOCK_STRATEGY_VALIDATION_SUMMARY.md`
- Backtest guides: `scripts/TREND_PULLBACK_BACKTEST_GUIDE.md`, `scripts/MOMENTUM_BREAKOUT_BACKTEST_GUIDE.md`
- Paper trading guide: `docs/PAPER_TRADING_MONITORING_GUIDE.md`

**Issue Tracking:**
- Task branch: `auto-claude/007-stock-strategy-redesign-trend-pullback-momentum-br`
- Spec: `.auto-claude/specs/007-stock-strategy-redesign-trend-pullback-momentum-br/spec.md`

**Logs & Monitoring:**
- Paper trading logs: `logs/paper_trading.log`
- Monitoring output: `output/monitoring/`
- MLflow tracking: (configure MLFLOW_TRACKING_URI)

---

## Timeline

| Milestone | Target Date | Status | Blocker |
|-----------|-------------|--------|---------|
| Code Complete | 2026-03-05 | ✓ Done | - |
| Unit Tests | 2026-03-06 | ✓ Done | - |
| Infrastructure | 2026-03-06 | ✓ Done | - |
| Environment Setup | TBD | ⏳ Pending | Python 3.11+, ClickHouse, Redis |
| Backtest Execution | TBD | ⏳ Pending | Environment setup |
| Paper Trading Start | TBD | ⏳ Pending | Backtest validation |
| 20-Day Monitoring | TBD + 4 weeks | ⏳ Pending | Paper trading start |
| Production Deploy | TBD | ⏳ Pending | All validations |

---

## Key Metrics to Watch

### Backtest Acceptance Criteria

| Metric | Target | trend_pullback | momentum_breakout |
|--------|--------|----------------|-------------------|
| Sharpe Ratio | > 1.0 | TBD | TBD |
| Net Return | > 0% | TBD | TBD |
| Max Drawdown | < 15% | TBD | TBD |

### Paper Trading Acceptance Criteria

| Metric | Target | trend_pullback | momentum_breakout |
|--------|--------|----------------|-------------------|
| Trading Days | ≥ 20 | TBD | TBD |
| Cumulative P&L | > 0 KRW | TBD | TBD |
| Runtime Errors | 0 | TBD | TBD |
| Signal Generation | > 0/day | TBD | TBD |

---

**Next Actions:**
1. Set up Python 3.11+ environment with dependencies
2. Verify ClickHouse has 6+ months of stock data
3. Execute backtests and validate Sharpe > 1.0
4. If validation passes, deploy to paper trading
5. Monitor for 20+ trading days
6. Make production deployment decision

**For Latest Status:** See `docs/STOCK_STRATEGY_VALIDATION_SUMMARY.md`
