---
name: trading-harness
description: "KIS Unified Trading Platform 통합 오케스트레이터. 전략 개발, RL 모델 관리, 코드 유지보수, 운영/모니터링. 전문가 풀에서 적절한 에이전트를 선택하여 라우팅한다."
---

# Trading Harness — 통합 전문가 풀 오케스트레이터

KIS Unified Trading Platform의 전략 개발, RL 모델 관리, 코드 유지보수, 운영/모니터링을 포괄하는 전문가 팀을 조율한다.

## 전문가 풀 (11명)

### 전략 개발 팀
| 에이전트 | 전문 영역 | 트리거 키워드 |
|---------|----------|-------------|
| `strategy-architect` | 전략 설계/구현 | 새 전략, 진입/청산 로직, YAML 설정, 레지스트리 |
| `backtest-engineer` | 백테스트/최적화 | 백테스트, Optuna, MLflow, 성과 분석, 최적화 |
| `rl-specialist` | RL 학습/환경 설계 | RL 학습, MPPO, 환경, 보상, 계층적 RL |

### RL 모델 관리 팀
| 에이전트 | 전문 영역 | 트리거 키워드 |
|---------|----------|-------------|
| `rl-specialist` | 모델 학습 | RL 학습, train, 하이퍼파라미터 |
| `model-evaluator` | 모델 평가/비교 | 모델 평가, 비교, A/B, 승격 판정, Sharpe |
| `model-deployer` | 모델 배포/롤백 | 배포, deploy, Paper→Live, 롤백, 모델 경로 |

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
| `rl-pipeline` | 파이프라인 | rl-specialist → model-evaluator → model-deployer | RL 모델 수명주기 |
| `ops-harness` | 전문가 풀 | ops-monitor, incident-responder, alert-manager | 운영/모니터링 |

## 라우팅 규칙

### 1차: 도메인 판별
```
전략/백테스트/구현 관련 → 전략 개발 팀
RL 학습/평가/배포 관련 → RL 모델 관리 팀 (→ rl-pipeline 스킬)
코드 리뷰/테스트/정리 → 코드 유지보수 팀
시스템/장애/알림 관련 → 운영/모니터링 팀 (→ ops-harness 스킬)
```

### 2차: 전문가 선택
키워드 매칭으로 가장 적합한 전문가 1명 또는 파이프라인 선택.

```
"BB 기반 새 전략 만들어줘"           → strategy-architect
"bb_reversion 백테스트 돌려줘"       → backtest-engineer
"RL 모델 학습시켜"                   → rl-specialist
"현재 모델이랑 새 모델 비교해줘"       → model-evaluator
"이 모델 Paper에 올려줘"             → model-deployer
"모델 학습하고 배포까지"              → rl-pipeline (풀 파이프라인)
"이 PR 리뷰해줘"                    → code-reviewer
"three_stage 테스트 작성해줘"        → test-engineer
"중복 코드 정리해줘"                 → refactorer
"시스템 상태 확인해줘"               → ops-monitor
"WebSocket 끊겼어"                  → incident-responder
"Telegram 알림 설정해줘"            → alert-manager
"전체 헬스체크"                     → ops-harness
```

## 복합 작업 워크플로우

### 새 전략 추가 (전체 파이프라인)
```
Phase 1: strategy-architect → 전략 설계/구현
Phase 2: test-engineer → 테스트 작성 (병렬 가능)
Phase 3: backtest-engineer → 백테스트 실행
Phase 4: code-reviewer → 최종 리뷰
```

### RL 모델 개선 → 배포 (rl-pipeline 위임)
```
Phase 1: rl-specialist → 모델 학습
Phase 2: model-evaluator → 평가 + 비교
Phase 3: model-deployer → Paper 배포 → Live 승격
Phase 4: ops-monitor → 배포 후 성능 추적
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
1. `pytest tests/ -v` 통과
2. `black . && ruff check .` 통과
3. CLAUDE.md 규칙 준수 (하드코딩 금지, DRY, Strategy Pattern)
4. YAML config 존재 및 유효성

RL 모델 배포 시:
1. 승격 판정 PASS (model-evaluator)
2. Paper 1주 검증 통과
3. 안전장치 동작 확인 (hard stop, EOD close)
4. 배포 체크리스트 전항목 PASS
