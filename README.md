# KIS Unified Trading Platform

> 한국투자증권 API 기반 주식/선물 통합 단기매매 시스템

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

KIS Unified STS is a configuration-driven trading platform for Korean stocks and
KOSPI200 futures. It combines YAML-defined strategies, backtesting, paper/live
runtime services, Redis Streams, SQLite runtime ledgers, Parquet/DuckDB market
data, and a Next.js operator dashboard.

For the current operational snapshot, read [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md).
For the full documentation map, read [docs/INDEX.md](docs/INDEX.md).

## Current Runtime

- **Frontend/API**: Caddy is the only host web entrypoint. It routes the Next.js
  UI (`strategy-builder-ui`) and FastAPI dashboard API (`services/dashboard`).
- **Stock paper runtime**: decoupled Compose pipeline
  (`stock-ingest` + `stock-pipeline`) after M5d cutover.
- **Futures runtime**: Setup A/C with LLM market context and explicit
  indicator/strategy-native exits. Decoupled futures services are available via
  `futures-ingest`, `futures-pipeline`, and `futures-killswitch` profiles.
- **Removed paths**: futures ML/RL/TFT runtime code and old `sts rl *` /
  `sts tft *` commands are removed.
- **Storage**: Redis DB 1 for runtime streams/state, SQLite WAL for runtime
  ledger, Parquet/DuckDB for historical market data. ClickHouse is not an active
  runtime dependency.

## Quick Start

### Requirements

- Python 3.11+
- Redis
- Docker and Docker Compose
- Node.js/npm for frontend development

### Backend Setup

```bash
git clone https://github.com/kakao-harris-lee/kis-unified-sts.git
cd kis-unified-sts

python -m venv venv
source venv/bin/activate

pip install -e ".[dev]"
cp .env.example .env
```

Fill `.env` with KIS credentials before running trading or data-collection paths.

### Docker Stack

```bash
docker compose up -d
```

Useful profiles:

```bash
docker compose --profile stock-pipeline up -d
docker compose --profile stock-ingest --profile stock-pipeline up -d
docker compose --profile futures-pipeline up -d
docker compose --profile futures-ingest --profile futures-pipeline up -d
```

### Access URLs

- Dashboard/UI/API: `http://localhost:${DASHBOARD_HOST_PORT:-5080}`
- If a local env overrides `DASHBOARD_HOST_PORT=5081`, use `http://localhost:5081`.
- Internal only: `dashboard:8001`, `strategy-builder-ui:3100`.

## Common Commands

```bash
# CLI help
sts --help

# Backtest
sts backtest run --strategy bb_reversion --asset stock

# Parameter optimization
sts optimize --strategy bb_reversion --asset stock --metric sharpe_ratio --trials 100

# MLflow UI for backtest/optimization tracking
sts mlflow ui

# Tests and checks
pytest tests/ -v --cov=shared --cov=services --cov=domains
ruff check .
black --check .
mypy shared/ --ignore-missing-imports --no-error-summary
```

Frontend:

```bash
cd strategy-builder-ui
npm run dev
npm run build
npm run lint
```

## Project Structure

```text
shared/              reusable strategy, execution, risk, storage, streaming, model logic
services/            runtime apps and daemons
  dashboard/         FastAPI API, health, metrics, WebSocket routes
  trading/           monolithic trading orchestrator
  stock_*            decoupled stock pipeline services
  decision_engine/   futures decision producer
  risk_filter/       futures risk filter
  order_router/      futures paper/live router
  futures_monitor/   futures dashboard/alert bridge
strategy-builder-ui/ Next.js frontend: cockpit, builder, executor, experiments
config/              YAML configs for strategies, execution, risk, storage, infra
cli/main.py          sts command entrypoint
tests/               unit, integration, performance, and service tests
docs/                architecture, plans, runbooks, operations docs
```

## Strategy Notes

- Strategy implementations live under `shared/strategy/`.
- Strategy YAML lives under `config/strategies/{stock,futures}/`.
- New thresholds, risk knobs, symbols, and feature flags should be added to
  config files, not hardcoded.
- Stock swing positions must remain strategy-signal based; do not force blanket
  EOD liquidation.
- Futures strategies must support long and short symmetry.

## Runbooks

| Runbook | Use |
|---|---|
| [paper-trading-docker.md](docs/runbooks/paper-trading-docker.md) | Docker paper stack operation |
| [stock-pipeline-cutover-m5d.md](docs/runbooks/stock-pipeline-cutover-m5d.md) | Stock decoupled pipeline cutover/rollback |
| [futures-pipeline-cutover-f9.md](docs/runbooks/futures-pipeline-cutover-f9.md) | Futures decoupled pipeline cutover |
| [paper-live-code-separation.md](docs/runbooks/paper-live-code-separation.md) | Validated-code live clone and promotion |
| [futures-paradigm-operations.md](docs/runbooks/futures-paradigm-operations.md) | Futures daily operations checklist |
| [futures-paradigm-rollback.md](docs/runbooks/futures-paradigm-rollback.md) | Emergency futures rollback |

## Documentation

- [CLAUDE.md](CLAUDE.md) - compact operational rules for coding agents
- [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) - current status snapshot
- [docs/INDEX.md](docs/INDEX.md) - documentation index
- [docs/plans/INDEX.md](docs/plans/INDEX.md) - current/reference/archive plan map
- [docs/ports.md](docs/ports.md) - host port policy
- [docs/runtime_storage_architecture.md](docs/runtime_storage_architecture.md) - runtime storage design

## Safety

This system is for research and controlled paper/live validation. Real-money use
requires explicit operator approval, validated code, live-mode guards, and the
appropriate runbook gate.
