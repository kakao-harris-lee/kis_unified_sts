---
name: rl-pipeline
description: "RL 모델 전체 수명주기 관리 파이프라인. 학습→평가→비교→배포 자동화. RL 모델 학습, 모델 비교, 모델 배포, Paper→Live 승격."
---

# RL Pipeline — RL 모델 수명주기 오케스트레이터

RL 모델의 전체 수명주기(학습→평가→비교→배포)를 관리하는 파이프라인 스킬.

## 전문가 구성

| 에이전트 | 파이프라인 역할 | 단계 |
|---------|---------------|------|
| `rl-specialist` | 모델 학습 (Flat/Hierarchical) | Phase 1 |
| `model-evaluator` | 성과 평가 및 모델 비교 | Phase 2-3 |
| `model-deployer` | Paper/Live 배포 및 버전 관리 | Phase 4 |

## 파이프라인

```
Phase 1: 학습              Phase 2: 평가              Phase 3: 비교              Phase 4: 배포
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  rl-specialist   │ →  │ model-evaluator  │ →  │ model-evaluator  │ →  │ model-deployer   │
│                  │    │                  │    │                  │    │                  │
│ - Flat MPPO      │    │ - Sharpe/MDD    │    │ - A/B 비교       │    │ - Paper 배포     │
│ - Hierarchical   │    │ - Win Rate      │    │ - Flat vs Hier   │    │ - 검증 (1주)     │
│ - Reward tuning  │    │ - 과적합 검증   │    │ - 승격 판정      │    │ - Live 승격      │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 시나리오별 워크플로우

### 1. 신규 모델 학습 → 배포 (풀 파이프라인)
```
rl-specialist: 학습 (train --algo mppo 또는 train-hierarchical)
    ↓
model-evaluator: 단일 모델 평가 (Sharpe, MDD, Win Rate)
    ↓
model-evaluator: 기존 운용 모델과 A/B 비교
    ↓ [승격 판정: PASS]
model-deployer: Paper 배포 → 1주 검증 → Live 승격
```

### 2. 모델 비교만 (학습 없이)
```
model-evaluator: 기존 모델 A vs 모델 B 비교
    ↓
model-evaluator: 승격 판정
    ↓ [PASS 시]
model-deployer: 배포
```

### 3. 긴급 롤백
```
model-deployer: 이전 모델로 롤백
    ↓
model-evaluator: 롤백 모델 성과 재확인
    ↓
ops-monitor: 롤백 후 성능 모니터링
```

### 4. 계층적 RL 실험
```
rl-specialist: directional + sequential 학습
    ↓ (병렬)
rl-specialist: risk_budget + joint 학습
    ↓
model-evaluator: 4개 조합 비교 (dir-seq, dir-joint, risk-seq, risk-joint)
    ↓
model-evaluator: 최적 조합 선정 + flat 대비 비교
    ↓ [승격 판정]
model-deployer: 배포
```

## 승격 기준 (게이트)

### Phase 2 → Phase 3 (평가 → 비교)
- Sharpe > 0.5
- Max DD < 10%
- 거래 횟수 > 50

### Phase 3 → Phase 4 (비교 → 배포)
- 기존 모델 대비 Sharpe 개선
- Max DD 악화 < 2%p
- 충분한 거래 횟수 (통계적 유의성)

### Phase 4 Paper → Live (배포 → 실전)
- Paper 1주 성과: Sharpe > 0.5
- Paper Max DD < 8%
- 안전장치(hard stop, EOD) 정상 동작 확인
- 체크리스트 전항목 PASS

## 사용 예시

```
"MPPO 모델 새로 학습하고 배포까지"
→ 풀 파이프라인 (Phase 1-4)

"현재 flat 모델이랑 hierarchical 비교해줘"
→ Phase 2-3 (model-evaluator만)

"이 모델 paper에 올려줘"
→ Phase 4 (model-deployer만)

"모델 문제 있어, 롤백해"
→ 긴급 롤백 시나리오
```
