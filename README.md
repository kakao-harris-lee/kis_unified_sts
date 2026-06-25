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

From a fresh `git clone`, pick whichever path fits the machine — all three give a
working dev/test environment with no manual Redis or dependency wrangling.

### Option A — Dev Container / Codespaces (zero local setup)

Nothing required but Docker (local) or a browser (Codespaces). The container
ships Python 3.11, Node, a throwaway Redis at `localhost:6379`, and all `.[dev]`
dependencies pre-installed.

- **VS Code:** open the folder → "Reopen in Container".
- **GitHub Codespaces:** "Code ▸ Codespaces ▸ Create codespace".

Then `pytest tests/unit -q` or `make help`. Config lives in `.devcontainer/`.

### Option B — Docker only (no host Python)

Run the full test suite in a container that mirrors CI — the only requirement is
Docker:

```bash
make test-docker
# = docker compose --profile test run --build --rm tests
```

### Option C — Host (Python 3.11)

```bash
make setup          # python -m pip install -e ".[dev]"  (no .env — see note below)
make test-unit      # fast unit subset, non-serial (needs Redis at localhost:6379)
make test           # full suite (needs a Redis at localhost:6379)
```

For a zero-setup run with no host Python or Redis, use Option B (`make test-docker`).

> **Run tests without a `.env`.** The suite is meant to run hermetically (like
> CI). A `.env` copied from `.env.example` sets production-leaning values
> (`DASHBOARD_REQUIRE_AUTH=true`, `REDIS_HOST=redis`) that `conftest`/`cli.main`
> load and that break unit tests. Create a `.env` (via `make env`) only when you
> need real KIS credentials for live/data runs.

Run `make help` for the full target list (lint, fmt, typecheck, up/down, ui).

### Requirements

- Docker and Docker Compose — sufficient on their own for Options A and B
- Python 3.11+ and a local Redis — only for Option C (host) workflows
- Node.js/npm — only for host frontend development (bundled in the Dev Container)

### Manual backend setup (equivalent to `make setup`)

```bash
git clone https://github.com/kakao-harris-lee/kis-unified-sts.git
cd kis-unified-sts

python -m venv venv
source venv/bin/activate

pip install -e ".[dev]"
cp .env.example .env   # only for live/data — see the test note above
```

Fill `.env` with KIS credentials before running trading or data-collection paths.
The test and Dev Container paths do **not** need (and should not have) a `.env`.

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
| [stock-pipeline-cutover-m5d.md](docs/runbooks/stock-pipeline-cutover-m5d.md) | Stock decoupled pipeline cutover/rollback |
| [futures-pipeline-cutover-f9.md](docs/runbooks/futures-pipeline-cutover-f9.md) | Futures decoupled pipeline cutover |
| [ops-readiness-checks.md](docs/runbooks/ops-readiness-checks.md) | Offline readiness checks for common post-cutover gates |
| [har-rv-log-rv-validation.md](docs/runbooks/har-rv-log-rv-validation.md) | HAR-RV raw-vs-log validation before forecast config cutover |
| [setup-c-event-score-observation.md](docs/runbooks/setup-c-event-score-observation.md) | Setup C event-score history readiness observation |
| [stock-strategy-reactivation.md](docs/runbooks/stock-strategy-reactivation.md) | Stock strategy evidence review before reactivation |
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
