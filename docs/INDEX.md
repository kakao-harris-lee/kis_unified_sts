# Documentation Index

Last updated: 2026-11-08 (legacy runtime removal L1–L6).

> **2026-11-12 — 미참조 과거 문서 정리.** 저장소 어디에서도 참조하지 않는 과거
> 문서를 삭제했다. 내용은 git 이력에 그대로 남아 있다:
> `git log --diff-filter=D -- docs/`.

> **The legacy trading runtime no longer exists.** Removal plan:
> [plans/2026-11-07-legacy-removal-plan.md](plans/2026-11-07-legacy-removal-plan.md);
> the code last existed at tag `legacy-final` (`6fc17c0f8d25`). Documents below
> that describe the stock/futures pipelines, the orchestrator, the strategy
> registry roster or the `sts backtest`/`optimize`/`mlflow` commands are
> **historical records**, whether or not they sit under `archive/`. Current
> state: [PROJECT_STATUS.md](PROJECT_STATUS.md) § Legacy runtime removed.

Top-level `docs/` index.  For plans see [plans/INDEX.md](plans/INDEX.md);
for runbooks see [README.md § Runbooks](../README.md#runbooks).

For "what's the project doing right now?" → [PROJECT_STATUS.md](PROJECT_STATUS.md).
For "where is each asset headed (phased)?" → **[ROADMAP.md](ROADMAP.md)** — the
authoritative Stock + Futures strategy roadmap. TOS product integration and
legacy retirement sequencing use the [TOS integration plan](plans/2026-10-06-tos-control-plane-and-first-tenant-plan.md).

---

## 📊 Project status

| Doc | Use |
|-----|-----|
| [ROADMAP.md](ROADMAP.md) | **Authoritative phased roadmap (Cross-Asset + Stock + Futures).** North Star, phase tables, current state, open next-steps. Supersedes scattered plan docs. |
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | 60-second dashboard — current phase, active strategies, automation schedule, blocking risks. |
| [investigations/2026-06-28-quant-system-gap-research.md](investigations/2026-06-28-quant-system-gap-research.md) | Current gap research split by KOSPI 200 futures and stock trading; includes ATS/session/product governance findings. |

## 📐 Architecture & API

| Doc | Use |
|-----|-----|
| [architecture/tos-system-context.md](architecture/tos-system-context.md) | TOS 공식 계층·책임·허용 의존 방향 정본. |
| [architecture/tos-public-interfaces.md](architecture/tos-public-interfaces.md) | 외부 조회/CLI 계약과 런타임 내부 포트, 현재 구현과 후속 명령 경계. |
| [migration/legacy-disposition.md](migration/legacy-disposition.md) | 기존 migration 정본을 참조하는 기능별 유지·이관·폐기 및 전환/롤백 조건. |
| [plans/2026-10-06-tos-control-plane-and-first-tenant-plan.md](plans/2026-10-06-tos-control-plane-and-first-tenant-plan.md) | CP-0 문서 정리 → 조회 UI → 명령 설계 → 첫 paper tenant → scope별 축소. |
| [ports.md](ports.md) | Host port ownership: Caddy host 5081, internal service ports stay private. |
| [strategies.md](strategies.md) | 설정 기반 전략 시스템 가이드 — YAML 정의, 레지스트리 패턴. |
| [runtime_storage_architecture.md](runtime_storage_architecture.md) | Redis Streams + SQLite runtime ledger + Parquet/DuckDB market-data store 설계, ClickHouse removal policy. |
| [performance_slas.md](performance_slas.md) | Current runtime performance SLAs (Redis/SQLite/Parquet/DuckDB/dashboard/scheduler). |

## 🎯 Strategy & paper trading

| Doc | Use |
|-----|-----|
| [BACKTEST_RESULTS_INTERPRETATION_GUIDE.md](BACKTEST_RESULTS_INTERPRETATION_GUIDE.md) | 백테스트 지표 해석 가이드. 현재 전략/런타임 상태는 ROADMAP 기준. |
| 운영 런북 전체 | → [README.md § Runbooks](../README.md#runbooks) — 런북 색인은 README 하나가 정본이다 |

## ⚙️ Operations

| Doc | Use |
|-----|-----|
| [DAILY_SCANNER_VERIFICATION.md](DAILY_SCANNER_VERIFICATION.md) | `scripts/daily_indicator_scanner.py` 검증 절차. |
| 운영 런북 전체 | → [README.md § Runbooks](../README.md#runbooks) — 런북 색인은 README 하나가 정본이다 |
| [CI_PARALLEL_NOTES.md](CI_PARALLEL_NOTES.md) | `pytest-xdist` 병렬 실행 (#399로 CI 활성화: 병렬 패스 + `serial` 마커 직렬 패스) + parallel-unsafe 테스트 목록. |
| [testing/2026-10-06-tos-control-plane.md](testing/2026-10-06-tos-control-plane.md) | CP-1 조회 UI·nullable 계약·로컬 검증과 운영 연결 미완 항목. |
| [testing/quant-gap-execution-2026-06-28.md](testing/quant-gap-execution-2026-06-28.md) | Final QA evidence for the 2026-06-28 quant gap expert-lane execution bundle. |

## 📁 Sub-directories

| Path | 내용 |
|------|------|
| [plans/](plans/) | Current/reference/archive plan 분류 → [plans/INDEX.md](plans/INDEX.md) |
| [superpowers/plans/](superpowers/plans/) | Active generated implementation plans only → [superpowers/plans/INDEX.md](superpowers/plans/INDEX.md) |
| [superpowers/specs/](superpowers/specs/) | Active design specs only; completed design rationale is under `superpowers/specs/archive/` |
| [runbooks/](runbooks/) | 운영 런북 → [README.md § Runbooks](../README.md#runbooks) |
| [testing/](testing/) | Current QA evidence and screenshot artifacts |
| [archive/](archive/) | 시간 의존적 stale snapshot 보존 (정보 보존 목적) |

## ⚪ Archive — completed-snapshot 보존

| Doc | Era |
|-----|-----|
| [archive/operations/crontab.md](archive/operations/crontab.md) | Historical host-crontab registration reference; Compose scheduler/producers supersede it. |
| [plans/archive/](plans/archive/) | Historical plan/spec records that should not be loaded for current roadmap decisions by default. |

## How to add a new doc

1. 새 doc은 top-level `docs/` 또는 적절한 sub-directory에 배치.
2. **카테고리 의도가 분명**한 경우 (operations / architecture 등): 본 INDEX 표에 한 줄 추가.
3. **시간 의존적 status snapshot** (e.g., "2026-03-09 기준 배포 상태"): 일정 시간 후 stale → 인용이 끊긴 것이 확인되면 `archive/`로 `git mv`.
4. PROJECT_STATUS.md는 살아있는 dashboard로 계속 갱신 (절대 archive 금지).
