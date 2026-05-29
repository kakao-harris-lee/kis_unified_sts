---
name: strategy-lab
description: "운영 전략 개발 1차 파이프라인. 지표 시그널 설계→백테스트/최적화→RegimeGate 검증→builder 연결→counterfactual 검증→Paper→Live 승격. Setup A/C·Williams %R/RSI/MACD 등 지표 기반 전략."
---

# Strategy Lab — 운영 전략 개발 오케스트레이터

KIS Unified Trading Platform의 **1차 전략 개발 파이프라인** 스킬.
2026-05-15 RL_mppo deprecate 이후 운영 시그널은 지표 기반 + RegimeGate로 전환되었으며,
이 스킬이 신규 전략의 설계→검증→승격 전체 수명주기를 관리합니다.
(RL 재학습이 필요한 경우에만 `rl-pipeline` 스킬을 사용)

## 전문가 구성

| 에이전트 | 파이프라인 역할 | 단계 |
|---------|---------------|------|
| `indicator-specialist` | 지표 시그널 리서치/설계 (Williams %R/RSI/MACD) | Phase 1 |
| `strategy-architect` | Entry/Exit/Sizer 조립 + 레지스트리 등록 | Phase 1 |
| `backtest-engineer` | 백테스트 + Optuna 최적화 + holdout 분리 | Phase 2 |
| `regime-gate-analyst` | RegimeGate head-to-head + counterfactual 검증 | Phase 3 |
| `strategy-builder` | (선택) 노코드 빌더 전략 paper 연결 | Phase 1' |
| `model-evaluator` | 성과 평가 + 승격 판정 | Phase 4 |
| `model-deployer` | Phase 5 Paper→Live 승격 게이트 | Phase 5 |

## 파이프라인

```
Phase 1: 설계            Phase 2: 백테스트/최적화   Phase 3: 게이트 검증       Phase 4: 평가         Phase 5: 승격
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐   ┌──────────────┐   ┌──────────────┐
│ indicator-spec.  │   │ backtest-engineer│   │ regime-gate-     │   │ model-       │   │ model-       │
│ + strategy-arch. │ → │                  │ → │ analyst          │ → │ evaluator    │ → │ deployer     │
│                  │   │ - 백테스트       │   │ - head-to-head   │   │ - 종합 판정  │   │ - Gate 1–3   │
│ - 지표 시그널    │   │ - Optuna         │   │ - counterfactual │   │ - PASS/REJECT│   │ - Paper→Live │
│ - Entry/Exit     │   │ - holdout 분리   │   │ - regime 분포    │   │              │   │ - 운영자 승인│
└─────────────────┘   └─────────────────┘   └─────────────────┘   └──────────────┘   └──────────────┘
        ↑ (선택) strategy-builder: 노코드 빌더 → builder_v1 → paper
```

## 시나리오별 워크플로우

### 1. 신규 지표 전략 (풀 파이프라인)
```
indicator-specialist: RL 대체 지표 리서치 (Williams %R/RSI/MACD 등)
    ↓
strategy-architect: Entry/Exit/Sizer 조립 + YAML + 레지스트리 등록
    ↓
backtest-engineer: 백테스트 + Optuna (train/holdout 분리)
    ↓
regime-gate-analyst: RegimeGate head-to-head (Δ 양수 + 유의) + counterfactual
    ↓ [PASS]
model-evaluator: 종합 승격 판정 (Sharpe/MDD/승률/PF)
    ↓ [PASS]
model-deployer: Phase 5 Gate 1–3 + 운영자 서면 승인 → Paper→Live
```

### 2. RegimeGate 적용성 검증만
```
regime-gate-analyst: gate ON vs OFF head-to-head (holdout)
    ↓
backtest-engineer: holdout 백테스트 실행 지원
    ↓
model-evaluator: Δ 종합 판정
```

### 3. 노코드 빌더 전략 → paper
```
strategy-builder: BuilderState → builder_v1 entry/exit
    ↓
strategy-architect: 레지스트리/팩토리 정합
    ↓
backtest-engineer: paper 전 백테스트 검증
    ↓ [PASS]
model-deployer: paper 등록 (stock-only, Phase 1)
```

### 4. 기존 전략 최적화/개선
```
backtest-engineer: 현행 파라미터 성과 분석
    ↓
indicator-specialist / strategy-architect: 지표 필터/파라미터 개선
    ↓
backtest-engineer: 재최적화 (Optuna)
    ↓
model-evaluator: before/after 비교 판정
```

## 승격 기준 (게이트)

### Phase 2 → Phase 3 (백테스트 → 게이트)
- Sharpe > 0.5, Max DD < 10%, 거래 횟수 > 50
- holdout 성과가 train 대비 급락하지 않음 (과적합 경계)

### Phase 3 → Phase 4 (게이트 → 평가)
- RegimeGate head-to-head Δ(ON − OFF) 양수 + 통계적 유의
- counterfactual EOD-proxy PnL 음수 아님

### Phase 4 → Phase 5 (평가 → 승격)
- 다중 지표 종합 PASS (Sharpe + MDD + 승률 + PF)
- 슬리피지 반영 성과 유지

### Phase 5 Paper → Live (Phase 5 게이트)
- Gate 1 검증 + Gate 2 법무/세무 + Gate 3 운영자 서면 승인
- `config/futures_live.yaml::enabled` + Redis `futures:live:suspended` 절차
- Paper 성과: Sharpe > 0.5, MDD < 8%, 안전장치 정상

## 사용 예시

```
"RL 대체할 지표 전략 새로 만들어줘"
→ 풀 파이프라인 (Phase 1-5)

"이 전략에 RegimeGate 적용해서 효과 검증해줘"
→ Phase 3 (regime-gate-analyst + backtest-engineer)

"빌더에서 만든 전략 paper에 올려줘"
→ 시나리오 3 (strategy-builder)

"Setup C 파라미터 다시 최적화해줘"
→ 시나리오 4 (backtest-engineer + strategy-architect)
```

## 품질 게이트 (공통)
- **No Hardcoding**: 모든 파라미터는 YAML config
- **Look-ahead 금지 (C1)**: `LookaheadGuard` assert 모드
- **슬리피지 필수**: 백테스트/페이퍼 모두
- **KST 타임존**: 시간 필터 전 KST 변환
- **DEPRECATED 회피**: `rl_mppo`, `llm_directed_indicator`는 신규 설계 미사용
- **Live는 게이트 뒤**: 선물 live는 Phase 5 Gate 통과 + 운영자 승인 후에만
