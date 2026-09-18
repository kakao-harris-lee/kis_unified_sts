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

- Dashboard/UI/API: `http://localhost:${DASHBOARD_HOST_PORT:-5081}`
- Caddy listens on container port `5080`; `DASHBOARD_HOST_PORT` is the host side.
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

`docs/runbooks/` 전체가 여기 올라온다. 새 런북을 추가하면 이 표에도 등재한다 —
등재되지 않은 런북은 필요한 순간에 발견되지 않는다.

### Stock

| Runbook | Use |
|---|---|
| [stock-pipeline-cutover-m5d.md](docs/runbooks/stock-pipeline-cutover-m5d.md) | Stock decoupled pipeline cutover/rollback |
| [stock-strategy-reactivation.md](docs/runbooks/stock-strategy-reactivation.md) | Stock strategy evidence review before reactivation |
| [bb-reversion-15m-paper.md](docs/runbooks/bb-reversion-15m-paper.md) | `bb_reversion_15m` paper validation — PAPER-ONLY, live flags must stay off |
| [stock-stream-cutover.md](docs/runbooks/stock-stream-cutover.md) | M1c — 모놀리식 orchestrator 의 시세 원천을 WebSocket ↔ Redis 틱 스트림으로 전환 (`STOCK_MARKET_DATA_SOURCE`). **표준 경로는 decoupled 파이프라인이라 평시에는 해당 없다**; `STOCK_ORCHESTRATOR_ENABLED=true` 롤백 시에만 쓴다. 플래그를 읽는 코드는 `services/trading/market_data_bootstrap.py:126` 에 살아 있다 |

### Futures

| Runbook | Use |
|---|---|
| [futures-pipeline-cutover-f9.md](docs/runbooks/futures-pipeline-cutover-f9.md) | Futures decoupled pipeline cutover |
| [futures-paradigm-operations.md](docs/runbooks/futures-paradigm-operations.md) | Futures daily operations checklist |
| [futures-paradigm-rollback.md](docs/runbooks/futures-paradigm-rollback.md) | Emergency futures rollback |
| [futures-paradigm-failure-modes.md](docs/runbooks/futures-paradigm-failure-modes.md) | Futures failure modes — symptoms and first response |
| [futures-legal-review.md](docs/runbooks/futures-legal-review.md) | Gate 2 legal/compliance review template — complete before any live flip |
| [setup-c-event-score-observation.md](docs/runbooks/setup-c-event-score-observation.md) | Setup C event-score history readiness observation |
| [regime-gate-paper-observation.md](docs/runbooks/regime-gate-paper-observation.md) | RegimeGate paper observation, activated per strategy |

### tos kernel / runtime

| Runbook | Use |
|---|---|
| [tos-rcl-schema-migration.md](docs/runbooks/tos-rcl-schema-migration.md) | RCL sqlite schema v1→v2 migration ordering, backup-before-migrate, rollback scope |
| [tos-kis-mock-transport.md](docs/runbooks/tos-kis-mock-transport.md) | `--transport kis-mock` wiring, custody, and non-live admission |
| [u17-prevention-control.md](docs/runbooks/u17-prevention-control.md) | U-17 예방 통제 — 아티팩트 countersign · main 착지 · 룰셋 필수 체크. **D0-A 착수 차단의 실제 해제 조건** |
| [kis-capability-probes.md](docs/runbooks/kis-capability-probes.md) | KIS broker capability probes (P0-2 / T2) — measurement only, approval is human |
| [2026-09-10-p02-probe-handover-paper-server.md](docs/runbooks/2026-09-10-p02-probe-handover-paper-server.md) | P0-2 probe handover to the paper server; `kis-capability-probes.md` is authoritative on conflict |

### Data, market structure, indicators

| Runbook | Use |
|---|---|
| [market-structure-policy.md](docs/runbooks/market-structure-policy.md) | Operator policy for stock ATS/SOR, futures sessions, KOSPI 200 product governance |
| [market-structure-krx-csv-backfill.md](docs/runbooks/market-structure-krx-csv-backfill.md) | Manual `foreign_futures` CSV backfill when the KIS feed has no history |
| [har-rv-log-rv-validation.md](docs/runbooks/har-rv-log-rv-validation.md) | HAR-RV raw-vs-log validation before forecast config cutover |
| [streaming-talib-convergence-gate.md](docs/runbooks/streaming-talib-convergence-gate.md) | Streaming indicator → TA-Lib convergence gate before a value-changing live change |

### Cross-cutting ops

| Runbook | Use |
|---|---|
| [ops-readiness-checks.md](docs/runbooks/ops-readiness-checks.md) | Offline readiness checks for common post-cutover gates |
| [market-open-pipeline-verification.md](docs/runbooks/market-open-pipeline-verification.md) | Pre-open and post-open pipeline verification |
| [paper-live-code-separation.md](docs/runbooks/paper-live-code-separation.md) | Validated-code live clone and promotion |
| [telegram-interactive-alerts.md](docs/runbooks/telegram-interactive-alerts.md) | Telegram approve/reject + close bot: config, rollout, rollback |
| [track-a-quarterly-rebalancing.md](docs/runbooks/track-a-quarterly-rebalancing.md) | Track A 분기 리밸런싱 체크리스트 (수동 트랙) |

### Staged verification

| Runbook | Use |
|---|---|
| [phase1-verification.md](docs/runbooks/phase1-verification.md) | Redis stream flow and file-based persistence |
| [phase2-verification.md](docs/runbooks/phase2-verification.md) | News/scoring/event flow without a server database |
| [phase3-verification.md](docs/runbooks/phase3-verification.md) | Futures market data and strategy gates against Parquet |
| [phase4-verification.md](docs/runbooks/phase4-verification.md) | Order fill logging and slippage analysis through `RuntimeLedger` |
| [phase5-verification.md](docs/runbooks/phase5-verification.md) | Paper/live readiness across Redis DB 1, SQLite ledger, Parquet |

### Historical — superseded, kept for reference

이 둘은 **현행 절차가 아니다.** 지우지 않고 남겨두되 그대로 따라 하지 말 것. 「비활성」과
「제거됨」은 다르다 — 플래그로 꺼져 있을 뿐 코드가 살아 있는 절차서는 여기 넣지 않는다.

| Runbook | Superseded by |
|---|---|
| [phase2-startup.md](docs/runbooks/phase2-startup.md) | 문서 자체가 Historical 선언 — RL-shadow 경로는 2026-06-03 제거됐다 |
| [cron-to-compose-cutover.md](docs/runbooks/cron-to-compose-cutover.md) | 호스트 crontab 철거는 완료됐다 (`docs/archive/operations/crontab.md`) — 스케줄은 Compose 소관 |

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
