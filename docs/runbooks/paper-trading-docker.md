# Paper Trading via Docker Compose (stock + futures)

Operator runbook for running **stock and futures paper trading together** through the
orchestrator using the docker-compose `trading` profile.

## paper/live is a STACK distinction (not hardcoded)

The `trader` (stock) and `trader-futures` services are **asset-pinned only**. Whether they
run paper or live comes entirely from the **stack environment**, never from the service
definition:

| Knob | Paper stack | Live stack |
|------|-------------|------------|
| `TRADING_MODE` | `paper` (default) | `live` |
| `KIS_REAL_TRADING` | `false` (default) | `true` |
| `COMPOSE_PROJECT_NAME` | e.g. `kis_paper` | e.g. `kis_live` |

The **same** `trader` + `trader-futures` service definitions run in either stack. Select the
stack via `COMPOSE_PROJECT_NAME` (and a stack-specific `.env`), so paper and live containers
stay isolated (`kis_paper-trader` vs `kis_live-trader`, separate Redis DBs, etc.).

> LIVE additionally runs from the verified-tag clone (`kis_unified_sts_live`) with the
> `live_preflight.sh` guardrail — see `docs/runbooks/paper-live-code-separation.md`. This note
> covers the compose-level paper launch.

## Services

| Service | Asset | container_name | Notes |
|---------|-------|----------------|-------|
| `trader` | `${TRADING_ASSET_CLASS:-stock}` (stock) | `${COMPOSE_PROJECT_NAME:-kis}-trader` | stock daemon |
| `trader-futures` | `futures` (pinned) | `${COMPOSE_PROJECT_NAME:-kis}-trader-futures` | futures daemon |

Both share the same `environment` block; `trader-futures` differs only in
`TRADING_ASSET_CLASS: "futures"` and its `container_name`. `trader-futures` reads its strategy
from `FUTURES_TRADING_STRATEGY` (falls back to the strategy registry default when unset).

## Launch (both assets)

```bash
# from the repo root, in the desired stack (e.g. paper)
docker compose --profile trading up -d trader trader-futures
```

Both daemons require their orchestrator path enabled (the default):

- `STOCK_ORCHESTRATOR_ENABLED` must be `true` (default) for `trader` to run stock.
- `FUTURES_ORCHESTRATOR_ENABLED` must be `true` (default) for `trader-futures` to run futures.

If either is set `false`, that asset is blocked (rollback flag — see project CLAUDE.md).

## Data sources & fills

- **Stock** (`trader`): mock market data (`KIS_STOCK_MARKET=mock`). Paper fills via the
  mock/paper engine.
- **Futures** (`trader-futures`): **real** market data (`KIS_FUTURES_MARKET=real`) for live
  ticks/orderbook, but in a paper stack (`TRADING_MODE=paper`/`KIS_REAL_TRADING=false`) orders
  are filled by the **VirtualBroker** — no real orders are sent. Real data + simulated fills is
  the intended futures paper configuration.

## Observability

Metrics are exposed by the dashboard (`/metrics`) and scraped by Prometheus (`prometheus`
service). Key metrics to watch during a paper run:

| Metric | Meaning |
|--------|---------|
| `trading_pipeline_stage_latency_ms{stage}` | Per-stage handler latency (bottleneck signal) |
| `trading_order_latency_ms` | Order submit round-trip latency |
| `trading_ws_disconnect_total{feed}` | WebSocket feed disconnects (recovery signal) |
| `trading_ws_reconnect_total{feed}` | WebSocket feed reconnect successes |
| `trading_rate_limit_penalty_total` | KIS rate-limit backoff (EGW00201) events |
| `trading_errors_total{component}` | Hot-path errors (e.g. `component="redis"`) |

Two new log lines accompany the metrics: a pipeline **slow-stage WARN** (stage exceeded its
cadence) and a **rate-limit recovery INFO** (cooldown cleared). Everything else is
metrics-only — check Prometheus / the dashboard rather than grepping logs.

## Quick checks

```bash
# both services present in the rendered config (read-only, starts nothing)
docker compose --profile trading config --services | grep -E 'trader($|-futures)'

# confirm asset pinning
docker compose --profile trading config | grep -A1 'container_name.*trader' 
```
