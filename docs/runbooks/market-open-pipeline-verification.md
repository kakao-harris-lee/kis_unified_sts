# Market Open Pipeline Verification

## Pre-Open

```bash
docker compose config --services
redis-cli -n 1 ping
sts data validate-parquet --root data/market
```

Expected:

- default compose services do not include a server database
- Redis DB 1 returns `PONG`
- Parquet validation succeeds or reports only known missing symbols

## Runtime Startup

Paper:

```bash
docker compose --env-file .env.paper.example --profile trading config --services
```

Live:

```bash
TRADING_LIVE_CONFIRM=I_UNDERSTAND_LIVE_TRADING \
  docker compose --env-file .env.live.example --profile trading config --services
```

Do not start live trading unless the account, market, and confirmation token are
intentional.

## Signal And Trade Checks

```bash
redis-cli -n 1 xinfo stream trading:signals
sts trade status --asset stock --paper
python scripts/analysis/stock_paper_daily_verification.py --no-telegram --print-json
```

Dashboard trades and stats should read Redis/RuntimeLedger state. If a signal is
visible but no trade row appears, inspect order-router logs and the SQLite
RuntimeLedger before restarting.

## Close Checks

```bash
sts trade status --asset stock --paper
python scripts/analysis/futures_session_health_report.py --days 1
```

Use broker/KIS account state as the live source of truth and RuntimeLedger for
local audit history.
