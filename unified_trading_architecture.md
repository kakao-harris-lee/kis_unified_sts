# Unified Trading Architecture

## Current Storage Decision

The runtime stack is Redis DB 1 + SQLite RuntimeLedger + Parquet/DuckDB market
data.

ClickHouse is not part of the active runtime, collection, backtest, or compose
service set. Do not add new order/fill/position, market-data, dashboard, or
prewarm paths that depend on it.

## Runtime Flow

```text
KIS REST/WebSocket
  -> trading services
  -> Redis Streams and Redis state
  -> SQLite RuntimeLedger
  -> dashboard/API views
```

Market-data flow:

```text
KIS historical collection
  -> ParquetMarketDataStore
  -> DuckDB queries for backtest/research/prewarm
```

## Storage Responsibilities

| Layer | Store | Responsibility |
| --- | --- | --- |
| Event bus | Redis Streams, DB 1 | ticks, signals, order/risk/news/scoring events |
| Runtime state | Redis DB 1 with TTL | current positions, latest context, kill-switch state |
| Runtime ledger | SQLite WAL | orders, fills, trades, position snapshots, risk events, audit history |
| Historical market data | Parquet + DuckDB | stock/futures bars for backtest, analysis, and warmup |
| Metrics | Prometheus | service metrics and alerting |

## Compose Model

Base compose starts application services, dashboard, Redis, Prometheus, and UI.
Trading loops are behind the `trading` profile. Optional research tooling such
as MLflow is behind the `research` profile.

Each environment uses a distinct compose project, host ports, Redis volume, and
SQLite ledger path. Redis still uses DB 1 inside each environment.

## Data Rules

- New stock and futures backfill writes directly to Parquet.
- Backtesting reads Parquet through `MarketDataStore`/DuckDB.
- Paper/live persistence writes to SQLite RuntimeLedger.
- Dashboard trades/stats read RuntimeLedger and Redis state.
- Configuration values live in YAML/env, not hardcoded thresholds or symbols.

## Operational Checks

```bash
docker compose config --services
redis-cli -n 1 ping
sts data validate-parquet --root data/market
sts --help
```

Expected default services do not include a server database service. If a command
or document requires a server database for normal paper/live/backtest work, it is
out of date and should be fixed.
