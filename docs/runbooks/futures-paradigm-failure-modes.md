# Futures Failure Modes

## Fill Logging Or Ledger Failure

Symptoms:

- fills appear in broker/mock execution but are missing from dashboard history
- RuntimeLedger warnings in service logs

Checks:

```bash
redis-cli -n 1 ping
ls -lh data/runtime/*/runtime.db
python scripts/analysis/futures_session_health_report.py --days 1
```

Resolution:

- stop the trader profile if live risk is unclear
- verify broker/KIS account state
- inspect or restore the SQLite RuntimeLedger file
- restart only after ledger write checks pass

## Market Data Stale Or Missing

Symptoms:

- prewarm returns empty frames
- backtests have no bars for expected symbols
- signal generation logs missing recent candles

Checks:

```bash
sts data validate-parquet --root data/market
python scripts/analysis/check_futures_backfill_integrity.py
```

Resolution:

- rerun the Parquet backfill for missing futures symbols/dates
- check KIS API credentials and rate-limit errors
- verify partition paths under `data/market/futures`

## News Or Scoring Lag

Checks:

```bash
redis-cli -n 1 xinfo stream news:raw
redis-cli -n 1 xinfo stream news:scored
```

Resolution:

- restart the affected collector/scorer service
- check Redis DB 1 connectivity
- review API keys and upstream HTTP failures
