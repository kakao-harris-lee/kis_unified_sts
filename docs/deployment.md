# Deployment Guide

KIS Unified STS is deployed through Docker Compose. Caddy is the single
host-published web entrypoint; service ports stay internal unless a runbook says
otherwise.

## Prerequisites

| Requirement | Minimum |
|---|---|
| Python | 3.11 |
| Docker | 24.0 |
| Docker Compose | 2.20 |
| Redis | 7.x |

Host resources: 2 CPU / 4 GB RAM minimum, 4 CPU / 8 GB RAM recommended.

## Port Policy

See [ports.md](ports.md) for the canonical port allocation.

| Port | Owner | Exposure |
|---:|---|---|
| `${DASHBOARD_HOST_PORT:-5081}` | Caddy | Host-published dashboard/UI/API/WebSocket entrypoint |
| `8001` | `dashboard` | Docker-network internal FastAPI API/metrics |
| `3100` | `strategy-builder-ui` | Docker-network internal Next.js app |
| `6379` | Redis | Internal or host-local, depending on env/runbook |
| `9090` | Prometheus | Host-local or internal monitoring, depending on env/runbook |

Do not publish the old `services/api` `:8000` gateway. It has been consolidated
into `services/dashboard`.

## Environment

```bash
cp .env.example .env
chmod 600 .env
```

Fill the KIS credentials and runtime settings before starting trading services.
Do not commit filled env files or `.kis_token_*`.

Important defaults:

```bash
REDIS_URL=redis://localhost:6379/1
DASHBOARD_HOST_PORT=5081
```

`DASHBOARD_HOST_PORT` is the host side of the Caddy mapping. Caddy still listens
on container port `5080` internally.

## Base Stack

```bash
docker compose up -d redis dashboard strategy-builder-ui caddy stream-exporter prometheus
```

Verify:

```bash
docker compose ps
curl -f "http://localhost:${DASHBOARD_HOST_PORT:-5081}/health"
```

## Stock Paper Runtime

Shadow validation:

```bash
docker compose --env-file .env.paper --profile stock-pipeline up -d \
  stock-strategy stock-risk-filter stock-order-router stock-exit stock-monitor
python -m scripts.ops.stock_cutover_verify --mode shadow
```

Live decoupled stock paper cutover:

```bash
STOCK_PIPELINE_MODE=live \
STOCK_ORCHESTRATOR_ENABLED=false \
docker compose --env-file .env.paper \
  --profile stock-ingest --profile stock-pipeline up -d \
  stock-market-ingest stock-strategy stock-risk-filter stock-order-router \
  stock-exit stock-monitor
python -m scripts.ops.stock_cutover_verify --mode live
```

Runbook: [runbooks/stock-pipeline-cutover-m5d.md](runbooks/stock-pipeline-cutover-m5d.md).

## Futures Runtime

Default futures operation remains Setup A/C with explicit live-mode guards. The
decoupled futures pipeline is profile-gated and should be cut over only through
the F9 runbook.

Shadow:

```bash
FUTURES_PIPELINE_MODE=shadow \
FUTURES_ORDER_ROUTER_MODE=paper \
docker compose --env-file .env.paper --profile futures-pipeline up -d \
  futures-decision-engine futures-risk-filter futures-order-router futures-monitor
```

Cutover runbook: [runbooks/futures-pipeline-cutover-f9.md](runbooks/futures-pipeline-cutover-f9.md).

## Scheduler And Producers

KIS one-shot jobs run through the Compose `scheduler` profile using
`deploy/scheduler.crontab` and supercronic. Market-hours producer daemons run
through the `producers` profile.

```bash
docker compose --env-file .env.paper --profile scheduler up -d scheduler
docker compose --env-file .env.paper --profile producers up -d screener fusion-ranker
```

Runbook: [runbooks/cron-to-compose-cutover.md](runbooks/cron-to-compose-cutover.md).

## Monitoring

- Dashboard/UI/API: `http://localhost:${DASHBOARD_HOST_PORT:-5081}`
- Prometheus: `http://localhost:9090` when exposed by the selected env/profile.
- Metrics route: Caddy proxies dashboard metrics through the unified web entry.

Use:

```bash
docker compose logs -f dashboard
docker compose logs -f scheduler
docker compose logs -f stream-exporter
```

## Security Checklist

- [ ] Filled `.env*` files are not committed.
- [ ] `API_KEY` is set when dashboard API auth is enabled.
- [ ] Redis uses DB 1 for this project.
- [ ] Runtime services bind only required host ports.
- [ ] Real-money futures uses `config/futures_live.yaml::enabled=true` only after
      the relevant runbook gates pass.
- [ ] LIVE code is promoted through validated tags per
      [runbooks/paper-live-code-separation.md](runbooks/paper-live-code-separation.md).

## Useful Commands

```bash
docker compose config
docker compose ps
docker compose logs -f
docker compose down
pytest tests/ -v --cov=shared --cov=services --cov=domains
```
