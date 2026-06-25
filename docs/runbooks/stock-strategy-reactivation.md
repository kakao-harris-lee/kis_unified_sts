# Stock Strategy Reactivation Readiness

This runbook supports review of `technical_consensus` and `momentum_breakout`
without changing trading behavior. The readiness report is advisory only: it
does not enable strategies, edit strategy YAML, or write runtime controls.

## Generate Report

Prepare offline evidence from backtest or paper observation:

```json
{
  "strategies": {
    "technical_consensus": {
      "sharpe": 1.1,
      "win_rate": 57.5,
      "max_drawdown_pct": 8.2,
      "trade_count": 42,
      "recent_loss_block": false
    },
    "momentum_breakout": {
      "sharpe": 0.4,
      "win_rate": 48.0,
      "max_drawdown_pct": 10.1,
      "trade_count": 35,
      "recent_loss_block": false
    }
  }
}
```

Run with explicit thresholds:

```bash
python -m scripts.ops.stock_strategy_readiness \
  --evidence /path/to/stock_strategy_evidence.json \
  --min-sharpe 0.8 \
  --min-win-rate 52 \
  --max-drawdown-pct 12 \
  --min-trade-count 30
```

Or put the same threshold keys in YAML and pass `--thresholds-yaml`.
Add `--strict` when using the report in automation; it exits nonzero if any
strategy is `blocked`.

## Status Meaning

- `ready_for_small_paper`: all gates passed; still requires human review before
  any config change.
- `observe_only`: evidence is real, but one or more threshold gates failed.
- `blocked`: evidence is missing, placeholder/TODO data was detected, metrics
  are invalid, or `recent_loss_block` is true.

## Required Evidence

Actual reactivation still requires current backtest and paper data. Placeholder
values such as `TODO`, `TBD`, empty strings, and `null` are blocked so a report
cannot pass on unfinished evidence.
