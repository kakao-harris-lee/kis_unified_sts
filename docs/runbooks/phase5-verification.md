# Phase 5 Verification

Phase 5 verifies paper/live readiness with Redis DB 1, SQLite RuntimeLedger, and
Parquet market data.

```bash
docker compose --env-file .env.paper.example config --services
docker compose --env-file .env.live.example config --services
redis-cli -n 1 ping
sts data validate-parquet --root data/market
```

Expected:

- default compose services do not include a server database
- paper/live configs render distinct runtime ledger paths
- dashboard and trading services use Redis DB 1
- backtest and prewarm paths use Parquet market data
