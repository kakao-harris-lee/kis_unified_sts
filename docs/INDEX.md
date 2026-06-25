# Documentation Index

Last updated: 2026-06-25 (Workbench UI/UX QA evidence added).

Top-level `docs/` index.  For plans see [plans/INDEX.md](plans/INDEX.md);
for runbooks see [README.md § 운영 런북](../README.md#운영-런북-runbooks).

For "what's the project doing right now?" → [PROJECT_STATUS.md](PROJECT_STATUS.md).
For "where is each asset headed (phased)?" → **[ROADMAP.md](ROADMAP.md)** — the
authoritative Stock + Futures roadmap that supersedes scattered plan docs.

---

## 📊 Project status

| Doc | Use |
|-----|-----|
| [ROADMAP.md](ROADMAP.md) | **Authoritative phased roadmap (Stock + Futures).** North Star, phase tables, current state, open next-steps. Supersedes scattered plan docs. |
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | 60-second dashboard — current phase, active strategies, automation schedule, blocking risks. |

## 📐 Architecture & API

| Doc | Use |
|-----|-----|
| [api.md](api.md) | API surface reference. |
| [ports.md](ports.md) | Host port ownership: Caddy 5080 only; service ports stay internal. |
| [strategies.md](strategies.md) | 설정 기반 전략 시스템 가이드 — YAML 정의, 레지스트리 패턴. |
| [config_patterns.md](config_patterns.md) | `ServiceConfigBase` 기반 통합 설정 패턴. |
| [deployment.md](deployment.md) | 플랫폼 배포 가이드. |
| [runtime_storage_architecture.md](runtime_storage_architecture.md) | Redis Streams + SQLite runtime ledger + Parquet/DuckDB market-data store 설계, ClickHouse removal policy. |
| [exception_hierarchy.md](exception_hierarchy.md) | Typed exception hierarchy — broad `except Exception` 제거 정책. |
| [error_handling_guide.md](error_handling_guide.md) | 에러 핸들링 베스트 프랙티스 + recovery 전략. |
| [TLS_SETUP.md](TLS_SETUP.md) | Redis, reverse proxy, external API TLS 가이드. |
| [performance_slas.md](performance_slas.md) | 성능 SLA 정의 (지연, 처리량, 가용성). |

## 🎯 Strategy & paper trading

| Doc | Use |
|-----|-----|
| [BACKTEST_RESULTS_INTERPRETATION_GUIDE.md](BACKTEST_RESULTS_INTERPRETATION_GUIDE.md) | 백테스트 지표 해석 가이드. 현재 전략/런타임 상태는 ROADMAP 기준. |
| [runbooks/stock-pipeline-cutover-m5d.md](runbooks/stock-pipeline-cutover-m5d.md) | 현재 stock decoupled paper pipeline cutover/runbook. |
| [runbooks/futures-pipeline-cutover-f9.md](runbooks/futures-pipeline-cutover-f9.md) | futures decoupled pipeline F-9 shadow/cutover runbook. |
| [plans/2026-06-22-quant-ops-workbench-uiux.md](plans/2026-06-22-quant-ops-workbench-uiux.md) | Quant Ops Workbench UI/UX 계획 — cockpit, signal trace, risk, backtest-vs-paper, promotion gates. |
| [plans/2026-06-02-stock-reopt-har-rv-followups.md](plans/2026-06-02-stock-reopt-har-rv-followups.md) | 현재 stock HAR-RV/strategy reactivation follow-up. |

## ⚙️ Operations

| Doc | Use |
|-----|-----|
| [DAILY_SCANNER_VERIFICATION.md](DAILY_SCANNER_VERIFICATION.md) | `scripts/daily_indicator_scanner.py` 검증 절차. |
| [CI_PARALLEL_NOTES.md](CI_PARALLEL_NOTES.md) | `pytest-xdist` 병렬 실행 (#399로 CI 활성화: 병렬 패스 + `serial` 마커 직렬 패스) + parallel-unsafe 테스트 목록. |
| [testing/quant-ops-workbench-2026-06-25.md](testing/quant-ops-workbench-2026-06-25.md) | Quant Ops Workbench desktop/mobile Playwright fallback screenshot QA evidence. |

## 📁 Sub-directories

| Path | 내용 |
|------|------|
| [plans/](plans/) | Current/reference/archive plan 분류 → [plans/INDEX.md](plans/INDEX.md) |
| [superpowers/plans/](superpowers/plans/) | Completed generated implementation plans → [superpowers/plans/INDEX.md](superpowers/plans/INDEX.md) |
| [superpowers/specs/](superpowers/specs/) | Design specs paired with generated implementation plans |
| [runbooks/](runbooks/) | 운영 런북 → [README.md § 운영 런북](../README.md#운영-런북-runbooks) |
| [testing/](testing/) | Current QA evidence and screenshot artifacts |
| [archive/](archive/) | 시간 의존적 stale snapshot 보존 (정보 보존 목적) |

## ⚪ Archive — completed-snapshot 보존

| Doc | Era |
|-----|-----|
| [archive/HYBRID_PIPELINE_TRUST_STATUS.md](archive/HYBRID_PIPELINE_TRUST_STATUS.md) | 2026-03-12 — 하이브리드 파이프라인 신뢰 상태 스냅샷 (점-시간 기록) |
| [archive/STOCK_STRATEGY_DEPLOYMENT_STATUS.md](archive/STOCK_STRATEGY_DEPLOYMENT_STATUS.md) | 2026-03-09 — 주식 전략 배포 상태 스냅샷 (이미 다른 전략으로 진화) |
| [archive/STOCK_STRATEGY_VALIDATION_SUMMARY.md](archive/STOCK_STRATEGY_VALIDATION_SUMMARY.md) | 2026-03-06 — 합성 데이터 기반 주식 전략 검증 요약 (현재 활성 상태와 불일치; archived 2026-06-20). 현재 상태는 [ROADMAP.md](ROADMAP.md) + [PROJECT_STATUS.md](PROJECT_STATUS.md). |
| [archive/BACKTEST_PERFORMANCE_REVIEW.md](archive/BACKTEST_PERFORMANCE_REVIEW.md) | 2026-03-05 — trend_pullback/momentum_breakout validation placeholder; archived 2026-06-22. |
| [archive/PAPER_TRADING_MONITORING_GUIDE.md](archive/PAPER_TRADING_MONITORING_GUIDE.md) | 2026-03 — pre-decoupled 20-day paper validation guide; archived 2026-06-22. |
| [archive/TREND_PULLBACK_PAPER_TRADING.md](archive/TREND_PULLBACK_PAPER_TRADING.md) | 2026-03 — disabled strategy paper guide; archived 2026-06-22. |
| [archive/MOMENTUM_BREAKOUT_PAPER_TRADING.md](archive/MOMENTUM_BREAKOUT_PAPER_TRADING.md) | 2026-03 — pre-decoupled per-strategy paper guide; archived 2026-06-22. |
| [archive/operations/crontab.md](archive/operations/crontab.md) | Historical host-crontab registration reference; Compose scheduler/producers supersede it. |
| [archive/runbooks/paper-docker-cutover.md](archive/runbooks/paper-docker-cutover.md) | 2026-06-08 host-cron → Compose cutover snapshot; superseded by current stock/futures/scheduler runbooks. |
| [archive/runbooks/paper-trading-docker.md](archive/runbooks/paper-trading-docker.md) | Historical monolithic-orchestrator Compose paper runbook; superseded by decoupled pipeline runbooks. |
| [archive/verification/](archive/verification/) | 2026-03 — 완료된 migration/security/performance 검증 스냅샷 |

## How to add a new doc

1. 새 doc은 top-level `docs/` 또는 적절한 sub-directory에 배치.
2. **카테고리 의도가 분명**한 경우 (operations / architecture 등): 본 INDEX 표에 한 줄 추가.
3. **시간 의존적 status snapshot** (e.g., "2026-03-09 기준 배포 상태"): 일정 시간 후 stale → 인용이 끊긴 것이 확인되면 `archive/`로 `git mv`.
4. PROJECT_STATUS.md는 살아있는 dashboard로 계속 갱신 (절대 archive 금지).
