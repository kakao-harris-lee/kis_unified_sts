# Documentation Index

Last updated: 2026-06-06 (ClickHouse shutdown documentation cleanup).

Top-level `docs/` index.  For plans see [plans/INDEX.md](plans/INDEX.md);
for runbooks see [README.md § 운영 런북](../README.md#운영-런북-runbooks).

For "what's the project doing right now?" → [PROJECT_STATUS.md](PROJECT_STATUS.md).

---

## 📊 Project status

| Doc | Use |
|-----|-----|
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
| [BACKTEST_PERFORMANCE_REVIEW.md](BACKTEST_PERFORMANCE_REVIEW.md) | 백테스트 성능 리뷰. |
| [BACKTEST_RESULTS_INTERPRETATION_GUIDE.md](BACKTEST_RESULTS_INTERPRETATION_GUIDE.md) | 백테스트 결과 해석 + 배포 의사결정. |
| [STOCK_STRATEGY_VALIDATION_SUMMARY.md](STOCK_STRATEGY_VALIDATION_SUMMARY.md) | 주식 전략 검증 요약. |
| [PAPER_TRADING_MONITORING_GUIDE.md](PAPER_TRADING_MONITORING_GUIDE.md) | trend_pullback / momentum_breakout 20+ 거래일 검증 모니터링. |
| [TREND_PULLBACK_PAPER_TRADING.md](TREND_PULLBACK_PAPER_TRADING.md) | trend_pullback 페이퍼 트레이딩 운영. |
| [MOMENTUM_BREAKOUT_PAPER_TRADING.md](MOMENTUM_BREAKOUT_PAPER_TRADING.md) | momentum_breakout 페이퍼 트레이딩 운영. |

## ⚙️ Operations

| Doc | Use |
|-----|-----|
| [DAILY_SCANNER_VERIFICATION.md](DAILY_SCANNER_VERIFICATION.md) | `scripts/daily_indicator_scanner.py` 검증 절차. |
| [CI_PARALLEL_NOTES.md](CI_PARALLEL_NOTES.md) | `pytest-xdist` 병렬 실행 (#399로 CI 활성화: 병렬 패스 + `serial` 마커 직렬 패스) + parallel-unsafe 테스트 목록. |

## 📁 Sub-directories

| Path | 내용 |
|------|------|
| [plans/](plans/) | Master plan + active/reference/archive 분류 → [plans/INDEX.md](plans/INDEX.md) |
| [runbooks/](runbooks/) | 운영 런북 → [README.md § 운영 런북](../README.md#운영-런북-runbooks) |
| [archive/](archive/) | 시간 의존적 stale snapshot 보존 (정보 보존 목적) |

## ⚪ Archive — completed-snapshot 보존

| Doc | Era |
|-----|-----|
| [archive/HYBRID_PIPELINE_TRUST_STATUS.md](archive/HYBRID_PIPELINE_TRUST_STATUS.md) | 2026-03-12 — 하이브리드 파이프라인 신뢰 상태 스냅샷 (점-시간 기록) |
| [archive/STOCK_STRATEGY_DEPLOYMENT_STATUS.md](archive/STOCK_STRATEGY_DEPLOYMENT_STATUS.md) | 2026-03-09 — 주식 전략 배포 상태 스냅샷 (이미 다른 전략으로 진화) |
| [archive/verification/](archive/verification/) | 2026-03 — 완료된 migration/security/performance 검증 스냅샷 |

## How to add a new doc

1. 새 doc은 top-level `docs/` 또는 적절한 sub-directory에 배치.
2. **카테고리 의도가 분명**한 경우 (operations / architecture 등): 본 INDEX 표에 한 줄 추가.
3. **시간 의존적 status snapshot** (e.g., "2026-03-09 기준 배포 상태"): 일정 시간 후 stale → 인용이 끊긴 것이 확인되면 `archive/`로 `git mv`.
4. PROJECT_STATUS.md는 살아있는 dashboard로 계속 갱신 (절대 archive 금지).
