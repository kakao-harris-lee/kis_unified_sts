# Compose Pipeline Services Migration

- Date: 2026-06-06
- Status: Implementation plan
- Scope: stock decoupled pipeline + compose runbooks. Futures runtime code is out of scope because a separate futures branch is active.

## Goal

Use Docker Compose as the single operational surface for paper/live services.
Host `systemd` units remain historical scaffolding only; operator runbooks should not
require `systemctl` for stock pipeline startup, cutover, rollback, or health checks.

## Branch And Worktree Isolation

This work is implemented on:

- Branch: `feat/compose-pipeline-services`
- Worktree: `/tmp/compose-pipeline-services`

The existing futures worktree `/tmp/f7-impl` (`feat/orchestrator-futures-live-guard`)
is not touched. This branch avoids futures runtime code changes and only adds common
compose environment wiring that is safe for the stock pipeline migration.

## Target Compose Profiles

| Profile | Service(s) | Role |
|---|---|---|
| base | `redis`, `dashboard`, `strategy-builder-ui`, `caddy`, `forecasting`, `stream-exporter` | runtime infra, UI, metrics |
| `trading` | `trader` | legacy monolithic `sts trade start` loop |
| `stock-pipeline` | `stock-strategy`, `stock-risk-filter`, `stock-order-router`, `stock-exit`, `stock-monitor` | decoupled stock M4/M5 daemons |
| `stock-ingest` | `stock-market-ingest` | KIS stock WebSocket owner, tick producer |

`stock-market-ingest` is intentionally not part of `stock-pipeline`. During shadow
validation the existing orchestrator/trader may still own the KIS WebSocket feed and
publish `market:ticks`; enabling ingest at the same time would create duplicate KIS
WebSocket subscriptions. Live decoupled cutover must stop the monolithic stock trader
before starting `stock-market-ingest`.

## Operating Model

Shadow validation:

```bash
docker compose --env-file .env.paper --profile trading up -d trader
docker compose --env-file .env.paper --profile stock-pipeline up -d \
  stock-strategy stock-risk-filter stock-order-router stock-exit stock-monitor
python -m scripts.ops.stock_cutover_verify --mode shadow
```

Live decoupled stock paper cutover:

```bash
docker compose --env-file .env.paper --profile trading stop trader
STOCK_PIPELINE_MODE=live \
  docker compose --env-file .env.paper \
    --profile stock-ingest --profile stock-pipeline up -d \
    stock-market-ingest stock-strategy stock-risk-filter stock-order-router \
    stock-exit stock-monitor
python -m scripts.ops.stock_cutover_verify --mode live
```

Rollback:

```bash
COMPOSE_ENV_FILE=/home/deploy/project/kis_unified_sts/.env.paper \
  bash scripts/ops/stock_cutover_rollback.sh --dry-run
COMPOSE_ENV_FILE=/home/deploy/project/kis_unified_sts/.env.paper \
  bash scripts/ops/stock_cutover_rollback.sh
```

## Implementation Tasks

1. Add compose services for the stock decoupled pipeline.
2. Keep market ingest in a separate profile to prevent accidental dual WebSocket use.
3. Add KIS stock-specific env variables to paper/live templates.
4. Convert stock M5d runbook and rollback script from `systemctl` to `docker compose`.
5. Add compose unit tests that lock the stock pipeline service/profile contract.
6. Verify rendered compose config for paper profiles and run focused tests.

## Non-goals

- Futures daemon migration or futures live-guard changes.
- Removing `deploy/systemd/` files in this branch; they can be deleted after the
  compose runbooks have replaced all active operator references.
- Changing trading logic, signal schemas, risk filters, or order execution.

