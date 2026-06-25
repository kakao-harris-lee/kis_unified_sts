# Performance Service Level Agreements (SLAs)

**Version:** 2.0
**Last Updated:** 2026-06-25
**Status:** Current

This document tracks current runtime performance targets for the KIS Unified STS
stack. RL/TFT runtime paths and ClickHouse are retired; their old SLA reference
is archived at
[`archive/performance_slas-rl-era.md`](archive/performance_slas-rl-era.md).

## Component SLAs

| Component | Target | Warning | Critical | Notes |
|-----------|--------|---------|----------|-------|
| WebSocket market-data ingest | p95 processing latency below measured baseline x 1.2 | p95 > baseline x 1.2 for 5 min | p99 > baseline x 1.5 for 2 min | Applies to stock and futures feeds. |
| Redis runtime streams/state | DB 1 only; p99 ops latency below measured baseline x 1.2 | p99 > baseline x 1.2 | write/read failure or DB mismatch | New Redis keys require TTLs unless explicitly persistent. |
| Parquet/DuckDB market data | 1-day query p95 < 500 ms; 30-day query p95 < 1000 ms | 1-day > 600 ms or 30-day > 1200 ms | 1-day > 750 ms or 30-day > 1500 ms | Applies to warmup, backtest, and research reads. |
| Runtime ledger SQLite WAL | reads/writes complete within dashboard refresh budget | repeated lock contention | write failure or WAL unavailable | Used for order/fill/position/trade evidence. |
| Trading orchestrator cycle | cycle time below measured baseline x 1.2 | cycle > baseline x 1.2 | cycle > baseline x 1.5 or missed session window | Futures monolith remains active unless F9 cutover is complete. |
| Decoupled stock pipeline | ingest -> strategy -> risk -> order path remains fresh within operator dashboard freshness windows | stale stage warning | missing stage data or blocked stream | Standard stock paper path is Compose `stock-ingest` + `stock-pipeline`. |
| Dashboard API | operator endpoints respond within 10 s timeout | repeated 5xx or timeout warning | `/health` failure | Caddy host port defaults to `5081` for paper/local; dashboard `8001` is internal. |
| Scheduler one-shot jobs | scheduled KST jobs complete before dependent next step | delayed or missing report | job failure affecting next session readiness | Source of truth: `deploy/scheduler.crontab`. |

## Regression Checks

Use the existing targeted performance and smoke suites:

```bash
pytest tests/performance/ -v
python scripts/performance/check_regression.py \
  --baseline tests/performance/baselines.json \
  --current tests/performance/baselines.json
npm --prefix strategy-builder-ui run build
npm --prefix strategy-builder-ui run lint
```

## Monitoring Notes

- Prometheus metrics should focus on websocket throughput/latency, Redis ops,
  dashboard route latency, orchestrator cycle time, stream freshness, and
  scheduler job success.
- ClickHouse metrics are historical only.
- RL/TFT inference latency metrics are historical only and must not be used as
  live runtime acceptance criteria.

## Maintenance

Update this document when active runtime surfaces change. Keep historical,
point-in-time SLA snapshots in `docs/archive/`.
