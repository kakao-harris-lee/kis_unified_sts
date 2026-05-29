---
name: trading-harness
description: "KIS Unified Trading Platform 통합 오케스트레이터. 지표 전략 개발, RegimeGate 검증, 노코드 빌더, Paper→Live 승격, 코드 유지보수, 운영/모니터링. 전문가 풀에서 적절한 에이전트를 선택하여 라우팅한다."
---

# Trading Harness — 통합 전문가 풀 오케스트레이터

KIS Unified Trading Platform의 전략 개발, RegimeGate 검증, 전략 승격, 코드 유지보수, 운영/모니터링을 포괄하는 전문가 팀을 조율한다.
운영 1차 방향은 **지표 기반 전략(Williams %R/RSI/MACD) + RegimeGate + Setup A/C**이며,
RL_mppo는 deprecate(2026-05-15)되어 재학습 옵션으로만 보존된다.

## 전문가 풀 (13명)

### 전략 개발 팀
| 에이전트 | 전문 영역 | 트리거 키워드 |
|---------|----------|-------------|
| `strategy-architect` | 전략 설계/구현 | 새 전략, 진입/청산 로직, YAML 설정, 레지스트리 |
| `indicator-specialist` | 지표 시그널 리서치 | 지표, Williams %R, RSI, MACD, StochRSI, consensus, RL 재학습 |
| `regime-gate-analyst` | RegimeGate 검증 | RegimeGate, 레짐, head-to-head, counterfactual, 게이트 |
| `strategy-builder` | 노코드 빌더 | builder, 빌더, builder_v1, 노코드, 빌더 UI |
| `backtest-engineer` | 백테스트/최적화 | 백테스트, Optuna, MLflow, 성과 분석, holdout |

### 전략/모델 승격 팀
| 에이전트 | 전문 영역 | 트리거 키워드 |
|---------|----------|-------------|
| `model-evaluator` | 전략/모델 평가/비교 | 평가, 비교, A/B, 승격 판정, Sharpe |
| `model-deployer` | 배포/승격/롤백 | 배포, deploy, Paper→Live, Phase 5 게이트, 롤백 |

### 코드 유지보수 팀
| 에이전트 | 전문 영역 | 트리거 키워드 |
|---------|----------|-------------|
| `code-reviewer` | 코드 리뷰/컨벤션 | 리뷰, 컨벤션, PR, 보안, 패턴 준수 |
| `test-engineer` | 테스트 작성/실행 | 테스트, pytest, 커버리지, 단위 테스트 |
| `refactorer` | 리팩토링/DRY | 중복 제거, DRY, config 추출, 정리 |

### 운영/모니터링 팀
| 에이전트 | 전문 영역 | 트리거 키워드 |
|---------|----------|-------------|
| `ops-monitor` | 시스템 모니터링/성능 | 헬스체크, 상태, 성능, 모니터링, 리소스 |
| `incident-responder` | 장애 대응/복구 | 장애, 에러, 크래시, 끊김, 복구 |
| `alert-manager` | 알림/Cron 관리 | Telegram, 알림, Cron, 브리핑, 알림 규칙 |

## 도메인별 서브 오케스트레이터

복잡한 도메인 작업은 전용 오케스트레이터 스킬이 관리:

| 스킬 | 패턴 | 담당 에이전트 | 용도 |
|------|------|-------------|------|
| `strategy-lab` | 파이프라인 (1차) | indicator-specialist → strategy-architect → backtest-engineer → regime-gate-analyst → model-evaluator → model-deployer | 운영 전략 개발 수명주기 |
| `ops-harness` | 전문가 풀 | ops-monitor, incident-responder, alert-manager | 운영/모니터링 |
| `rl-pipeline` | 파이프라인 (DEPRECATED) | indicator-specialist(보조) → model-evaluator → model-deployer | RL 재학습 전용 (운영 경로 아님) |

## 라우팅 규칙

### 1차: 도메인 판별
```
전략/지표/게이트/빌더/백테스트 관련 → 전략 개발 팀 (→ strategy-lab 스킬)
전략 평가/승격/배포 관련          → 전략/모델 승격 팀 (→ strategy-lab Phase 4-5)
코드 리뷰/테스트/정리             → 코드 유지보수 팀
시스템/장애/알림 관련             → 운영/모니터링 팀 (→ ops-harness 스킬)
RL 재학습/복귀 검토 (명시적)      → rl-pipeline 스킬 (DEPRECATED, 예외적)
```

### 2차: 전문가 선택
키워드 매칭으로 가장 적합한 전문가 1명 또는 파이프라인 선택.

```
"BB 기반 새 전략 만들어줘"            → strategy-architect
"RL 대체할 지표 리서치해줘"           → indicator-specialist
"이 전략에 RegimeGate 적용해서 검증"  → regime-gate-analyst
"빌더에서 만든 전략 paper에 올려줘"    → strategy-builder
"bb_reversion 백테스트 돌려줘"        → backtest-engineer
"현재 전략이랑 새 전략 비교해줘"        → model-evaluator
"이 전략 Live로 승격해줘"             → model-deployer
"지표 전략 새로 만들고 승격까지"       → strategy-lab (풀 파이프라인)
"이 PR 리뷰해줘"                     → code-reviewer
"three_stage 테스트 작성해줘"         → test-engineer
"중복 코드 정리해줘"                  → refactorer
"시스템 상태 확인해줘"                → ops-monitor
"WebSocket 끊겼어"                   → incident-responder
"Telegram 알림 설정해줘"             → alert-manager
"전체 헬스체크"                      → ops-harness
"RL 모델 재학습 검토" (예외)          → rl-pipeline (DEPRECATED)
```

## 복합 작업 워크플로우

### 신규 지표 전략 개발 → 승격 (strategy-lab 위임)
```
Phase 1: indicator-specialist + strategy-architect → 지표 시그널 설계/조립
Phase 2: backtest-engineer → 백테스트 + Optuna (holdout 분리)
Phase 3: regime-gate-analyst → RegimeGate head-to-head + counterfactual
Phase 4: model-evaluator → 종합 승격 판정
Phase 5: model-deployer → Phase 5 Gate 1–3 + 운영자 승인 → Paper→Live
```

### 새 전략 추가 (간이 파이프라인)
```
Phase 1: strategy-architect → 전략 설계/구현
Phase 2: test-engineer → 테스트 작성 (병렬 가능)
Phase 3: backtest-engineer → 백테스트 실행
Phase 4: code-reviewer → 최종 리뷰
```

### 코드 품질 개선
```
Phase 1: code-reviewer → 이슈 식별
Phase 2: refactorer + test-engineer (병렬) → 수정 + 테스트 보강
Phase 3: code-reviewer → 재리뷰
```

### 장애 대응 (ops-harness 위임)
```
Phase 1: ops-monitor → 이상 감지
Phase 2: incident-responder → 진단 + 복구
Phase 3: alert-manager → 알림 발송
Phase 4: ops-monitor → 복구 후 재검증
```

### 병렬 실행 (팬아웃)
```
"전략 구현하고 테스트도 작성해줘"
→ strategy-architect + test-engineer (병렬)

"코드 리뷰하고 리팩토링 대상 찾아줘"
→ code-reviewer + refactorer (병렬)

"헬스체크하고 알림 상태도 확인해줘"
→ ops-monitor + alert-manager (병렬)
```

## 사용법

이 스킬은 자동으로 적용됩니다. 사용자의 요청을 분석하여:

1. **도메인 판별** → 해당 팀 식별
2. **전문가 선택** → 키워드 매칭으로 에이전트 선택
3. **단일/복합/파이프라인 판단** → 적절한 실행 방식 결정
4. **Agent 도구 호출** → `.claude/agents/{name}.md` 참조하여 위임
5. 결과를 사용자에게 보고

## 품질 게이트

모든 전략 개발 작업 완료 시:
1. `.venv/bin/pytest tests/ -v` 통과
2. `black . && ruff check .` 통과
3. CLAUDE.md 규칙 준수 (하드코딩 금지, DRY, Strategy Pattern, KST, Look-ahead 금지)
4. YAML config 존재 및 유효성
5. DEPRECATED 전략(`rl_mppo`, `llm_directed_indicator`) 미사용

전략 Paper→Live 승격 시:
1. 종합 승격 판정 PASS (model-evaluator)
2. RegimeGate head-to-head PASS + counterfactual 음수 아님 (해당 시)
3. Phase 5 Gate 1–3 통과 + 운영자 서면 승인
4. `config/futures_live.yaml::enabled` + Redis `futures:live:suspended` 절차
5. 안전장치 동작 확인 (hard stop, EOD close)
