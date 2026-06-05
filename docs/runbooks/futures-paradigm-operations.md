# Futures Operations Runbook

## Daily Checks

- Redis DB 1 responds: `redis-cli -n 1 ping`
- Runtime ledger path exists for the environment.
- Parquet futures dataset validates: `sts data validate-parquet --root data/market`
- Trading profile is enabled only when intentionally running the trader service.
- Live trader requires both `KIS_REAL_TRADING=true` and
  `TRADING_LIVE_CONFIRM=I_UNDERSTAND_LIVE_TRADING`.

## Position Close Check

Use the runtime ledger or broker/KIS account state as the source of truth.

```bash
sts trade status --asset futures --paper
python scripts/analysis/futures_session_health_report.py --days 1
```

All futures positions should be closed before the configured EOD close window
unless an explicit strategy exception is active.

## Storage Policy

Futures collection and backtesting use Parquet files. Paper/live fills and
position snapshots use SQLite RuntimeLedger. Do not add a server database as a
normal operations prerequisite.
