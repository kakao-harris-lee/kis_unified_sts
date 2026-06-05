# Futures Rollback Runbook

## Immediate Stop

```bash
docker compose --profile trading stop trader
sts trade stop --asset futures
```

Confirm broker/KIS account state before assuming local state is final.

## State Verification

```bash
redis-cli -n 1 ping
sts trade status --asset futures --paper
python scripts/analysis/futures_session_health_report.py --days 1
sts data validate-parquet --root data/market
```

## Data Recovery

- Runtime records: restore or inspect the environment SQLite RuntimeLedger.
- Market data: restore Parquet snapshots under `data/market`.
- Redis state: rebuild from broker/KIS state and RuntimeLedger when needed.

Rollback is performed by reverting the deployment or branch, not by switching to
a hidden server database backend.
