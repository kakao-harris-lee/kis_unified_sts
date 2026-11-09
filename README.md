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

# One-page operator status board (sessions, B3 verdicts, clean-day streaks)
sts tos status

# Tests and checks
pytest tests/ -q
ruff check .
black --check .
mypy shared/ --ignore-missing-imports --no-error-summary

# TOS checkers (what CI gates on)
python tools/tos_spec_status.py --check
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
tos-spec/            TOS spec corpus; tos-evidence/ its evidence
tools/tos_*          CP-3 producer, B3 witness, spec/firewall/status checkers
tools/broker_probes/ KIS capability probes (GET reads; order probes interlocked)
shared/              what the surviving roots import — replay/decision/indicators,
                     KIS auth+client, config, storage, risk primitives, LLM
services/dashboard/  FastAPI app: /api/tos/*, /health, OpenAPI docs
services/monitoring/ metrics/health helpers shared/kis imports lazily
strategy-builder-ui/ Next.js frontend: the /tos operator page and the /api proxy
config/              tos_runtime tenant trees, tos_* gates, KIS/execution/risk/
                     storage/streaming settings, one Setup D strategy YAML
cli/main.py          sts entrypoint (`sts tos` only)
scripts/             scripts/tos/ tenant rendering + the Setup D walk-forward
tests/               unit, integration, and tool tests
docs/                architecture, plans, runbooks, operations docs
```

## Strategy Notes

- There is no strategy registry roster any more: L6 deleted every
  `shared/strategy/entry/*` module, so `EntryRegistry` is empty and
  `StrategyFactory` can build nothing. A strategy is Tenant Content (DSL +
  profile) under `config/tos_runtime/`, executed by the TOS kernel.
- `config/strategies/futures/setup_d_vwap_reversion.yaml` is the one strategy
  YAML left — it is the CP-3 B3 witness's input and is read by
  `tools/tos_cp3/emit_legacy_decisions.py`.
- New thresholds, risk knobs, symbols, and feature flags should be added to
  config files, not hardcoded.
- Futures strategies must support long and short symmetry.

## Runbooks

`docs/runbooks/` 전체가 여기 올라온다. 새 런북을 추가하면 이 표에도 등재한다 —
등재되지 않은 런북은 필요한 순간에 발견되지 않는다.

### Stock

| Runbook | Use |
|---|---|
| [stock-pipeline-cutover-m5d.md](docs/runbooks/stock-pipeline-cutover-m5d.md) | **RETIRED** — the pipeline it cuts over was deleted (L1/L2/L6). History only |
| [stock-strategy-reactivation.md](docs/runbooks/stock-strategy-reactivation.md) | Stock strategy evidence review before reactivation |
| [bb-reversion-15m-paper.md](docs/runbooks/bb-reversion-15m-paper.md) | `bb_reversion_15m` paper validation — PAPER-ONLY, live flags must stay off |
| [stock-stream-cutover.md](docs/runbooks/stock-stream-cutover.md) | **RETIRED** — 플래그(`STOCK_MARKET_DATA_SOURCE`)를 읽던 `services/trading/market_data_bootstrap.py` 가 L2 에서 사라졌다. History only |

### Futures

| Runbook | Use |
|---|---|
| [futures-pipeline-cutover-f9.md](docs/runbooks/futures-pipeline-cutover-f9.md) | **RETIRED** — both sides of the cutover were deleted (L1/L2/L6). History only |
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
| [tos-paper-boot.md](docs/runbooks/tos-paper-boot.md) | TOS paper **운영** 런북 — 상주 세션(start/stop·cron) · CP-3 tenant 세션(genesis·band·롤) · 콜드 백업 시간 관계 · 아침 결말 표 · digest 재도출 |
| [tos-paper-boot-history.md](docs/runbooks/tos-paper-boot-history.md) | 위 런북의 **이력** — 1회성 부팅 절차(§1–§6) · `migrate` v1→v2(§4-A) · 2026-09-24 실측 차단(§5) · 드라이런(§7.9) · 닫힌/열린 질문(§7.10). 절 번호는 운영 런북과 같다 |
| [tos-evidence-cold-backup.md](docs/runbooks/tos-evidence-cold-backup.md) | TOS 증거 콜드 백업 — 설정 기반 `cold-backup` 하위 명령(자동 세대 · xz · 되읽기 검증 · JSON 보고서 · 용량 바닥) · KST cron 한 줄 · 거부 대응표. **아무것도 지우지 않고 보존 손잡이도 없다**(파기는 트랙 B) |
| [u17-prevention-control.md](docs/runbooks/u17-prevention-control.md) | U-17 예방 통제 — 아티팩트 countersign · main 착지 · 룰셋 필수 체크. **D0-A 착수 차단의 실제 해제 조건** |
| [tos-paper-projection-connection.md](docs/runbooks/tos-paper-projection-connection.md) | CP-1 operator projection 출력 연결 — host wrapper/driver 좌표, 전용 0700 디렉터리, 읽기 전용 **디렉터리** mount(파일 단독 bind 금지), scratch 격리, 복구 절차 |
| [kis-capability-probes.md](docs/runbooks/kis-capability-probes.md) | KIS broker capability probes (P0-2 / T2) — measurement only, approval is human |
| [2026-09-10-p02-probe-handover-paper-server.md](docs/runbooks/2026-09-10-p02-probe-handover-paper-server.md) | P0-2 probe handover to the paper server; `kis-capability-probes.md` is authoritative on conflict |
| [2026-09-23-tos-session-handoff-paper-server.md](docs/runbooks/2026-09-23-tos-session-handoff-paper-server.md) | tos 세션 핸드오프(2026-09-23) — mypy 래칫 3단계 완료 후 서버에서 이어갈 큐: `unused-ignore` 8건 결정 · 프로브 7건 · 운영자 결정 3건 · `run` 실부팅 아크; 측정 명령과 함정 요약 |
| [2026-10-06-tos-cp1-claude-handoff.md](docs/runbooks/2026-10-06-tos-cp1-claude-handoff.md) | CP-1 인계(2026-10-06, Codex → Claude) — #860~#864 병합·계층 명명·`/tos` 조회 화면·호스트 projection 배선·리뷰 상태·다음 paper 세션에서 확인할 넷과 분리한 후속 넷 |

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
| [paper-live-code-separation.md](docs/runbooks/paper-live-code-separation.md) | **RETIRED** — there is no live clone to promote to (L1–L6). History only |
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
