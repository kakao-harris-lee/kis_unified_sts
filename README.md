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
- **Trading runtime**: the TOS kernel (`tos/`) and its CP-3 tenant sessions.
  Futures tenants are synthetic (they send nothing); the stock tenant sends to
  the KIS **mock** account only.
- **Removed paths**: the legacy stock and futures runtimes — the orchestrator,
  the decoupled stock/futures services, the strategy registry roster, the
  backtest/optimize/mlflow CLI groups and the futures ML/RL/TFT code — are gone
  (`docs/plans/2026-11-07-legacy-removal-plan.md`, L1–L6). They last existed at
  tag `legacy-final` (`6fc17c0f8d25`).
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

The default stack is five services: `dashboard`, `strategy-builder-ui`,
`caddy`, `redis`, `prometheus`. The stock/futures pipeline profiles went with
the legacy runtime (`docs/plans/2026-11-07-legacy-removal-plan.md`); the only
remaining profile is `test`:

```bash
docker compose --profile test run --rm tests
```

### Access URLs

- Dashboard/UI/API: `http://localhost:${DASHBOARD_HOST_PORT:-5081}`
- Caddy listens on container port `5080`; `DASHBOARD_HOST_PORT` is the host side.
- Internal only: `dashboard:8001`, `strategy-builder-ui:3100`.

## Common Commands

```bash
# CLI help. `sts tos` is the only command group — the backtest/optimize/mlflow/
# collect/trade/paper groups went with the legacy runtime
# (docs/plans/2026-11-07-legacy-removal-plan.md, L3).
sts --help

# One-page operator status board (sessions, clean-day streaks)
sts tos status

# Tests and checks
pytest tests/ -q
ruff check .
black --check .
mypy shared/ --ignore-missing-imports --no-error-summary

# TOS checkers (what CI gates on)
python tools/tos_firewall_check.py
# `lint-imports` as CI runs it (.github/workflows/tos-firewall.yml): plain, after
# an editable install of the root project and tos/runtime. Without that install
# the contracts' root packages do not resolve; a local shortcut is
# `PYTHONPATH=.:tos/src:tos/runtime/src lint-imports`, which is NOT what gates.
lint-imports
```

Frontend:

```bash
cd strategy-builder-ui
npm run dev
npm run build
npm run lint
npm test
```

## Project Structure

```text
tos/                 TOS kernel + tos_runtime shell (see tos/CLAUDE.md)
tools/tos_*          CP-3 producer, Setup D witness, firewall/digest/size checkers
tools/broker_probes/ KIS capability probes (GET reads; order probes interlocked)
shared/              what the surviving roots import — replay/decision/indicators,
                     KIS auth, config, storage, risk primitives, LLM
services/dashboard/  FastAPI app: /api/tos/*, /health, OpenAPI docs
strategy-builder-ui/ Next.js frontend: the /tos operator page and the /api proxy
config/              tos_runtime tenant trees, tos_* gates, KIS/execution/risk/
                     storage/streaming settings, one Setup D strategy YAML
cli/main.py          sts entrypoint (`sts tos` only)
scripts/             scripts/tos/ tenant rendering + the Setup D walk-forward
tests/               unit, integration, and tool tests
docs/                architecture, plans, runbooks, broker profiles
```

## Strategy Notes

- There is no strategy registry roster any more: L6 deleted every
  `shared/strategy/entry/*` module, so `EntryRegistry` is empty and
  `StrategyFactory` can build nothing. A strategy is Tenant Content (DSL +
  profile) under `config/tos_runtime/`, executed by the TOS kernel.
- `config/strategies/futures/setup_d_vwap_reversion.yaml` is the one strategy
  YAML left — it is the frozen legacy Setup D witness's input and is read by
  `tools/tos_cp3/produce_fields.py`.
- New thresholds, risk knobs, symbols, and feature flags should be added to
  config files, not hardcoded.
- Futures strategies must support long and short symmetry.

## Runbooks

`docs/runbooks/` 전체가 여기 올라온다. 새 런북을 추가하면 이 표에도 등재한다 —
등재되지 않은 런북은 필요한 순간에 발견되지 않는다. 레거시 런타임 시절의 런북
(stock/futures 파이프라인 · phase1–5 검증 · cutover)은 2026-11-13 에 지웠다
(`docs/plans/2026-11-13-tos-code-halving-plan.md` §S3); 내용은 git 이력에 있다.

### tos kernel / runtime

| Runbook | Use |
|---|---|
| [tos-rcl-schema-migration.md](docs/runbooks/tos-rcl-schema-migration.md) | RCL sqlite schema v1→v2 migration ordering, backup-before-migrate, rollback scope |
| [tos-kis-mock-transport.md](docs/runbooks/tos-kis-mock-transport.md) | `--transport kis-mock` wiring, custody, and non-live admission |
| [tos-paper-boot.md](docs/runbooks/tos-paper-boot.md) | TOS paper **운영** 런북 — 상주 세션(start/stop·cron) · CP-3 tenant 세션(genesis·band·롤) · 콜드 백업 시간 관계 · 아침 결말 표 · digest 재도출 |
| [tos-paper-boot-history.md](docs/runbooks/tos-paper-boot-history.md) | 위 런북의 **이력** — 1회성 부팅 절차(§1–§6) · `migrate` v1→v2(§4-A) · 2026-09-24 실측 차단(§5) · 드라이런(§7.9) · 닫힌/열린 질문(§7.10). 절 번호는 운영 런북과 같다 |
| [tos-evidence-cold-backup.md](docs/runbooks/tos-evidence-cold-backup.md) | TOS 증거 콜드 백업 — 설정 기반 `cold-backup` 하위 명령(자동 세대 · xz · 되읽기 검증 · JSON 보고서 · 용량 바닥) · KST cron 한 줄 · 거부 대응표. **아무것도 지우지 않고 보존 손잡이도 없다**(파기는 트랙 B) |
| [tos-paper-projection-connection.md](docs/runbooks/tos-paper-projection-connection.md) | CP-1 operator projection 출력 연결 — host wrapper/driver 좌표, 전용 0700 디렉터리, 읽기 전용 **디렉터리** mount(파일 단독 bind 금지), scratch 격리, 복구 절차 |
| [kis-capability-probes.md](docs/runbooks/kis-capability-probes.md) | KIS broker capability probes (P0-2 / T2) — measurement only, approval is human |

### 코드·설정이 근거로 인용하는 기록

| Runbook | Use |
|---|---|
| [futures-legal-review.md](docs/runbooks/futures-legal-review.md) | `shared/execution/tr_ids.py` · `tools/broker_probes/probes_real.py` 가 인용하는 TR id 감사 기록 |
| [market-structure-policy.md](docs/runbooks/market-structure-policy.md) | `config/market_schedule.yaml` 의 세션 창 정책 — `probes_real_order.py` 가 그 설정을 읽는다 |

## Documentation

- [CLAUDE.md](CLAUDE.md) - compact operational rules for coding agents
- [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) - current status snapshot
- [docs/INDEX.md](docs/INDEX.md) - documentation index
- [docs/plans/INDEX.md](docs/plans/INDEX.md) - current/reference/archive plan map
- [docs/ports.md](docs/ports.md) - host port policy

## Safety

This system is for research and controlled paper/live validation. Real-money use
requires explicit operator approval, validated code, live-mode guards, and the
appropriate runbook gate.
