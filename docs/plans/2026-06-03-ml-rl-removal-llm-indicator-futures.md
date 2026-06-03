# ML/RL Removal and LLM+Indicator Futures Plan

- 작성일: 2026-06-03
- 상태: Active decision
- 관련 문서:
  - [2026-05-03-llm-primary-rl-minimization.md](2026-05-03-llm-primary-rl-minimization.md)
  - [2026-06-03-runtime-storage-decoupling-implementation.md](2026-06-03-runtime-storage-decoupling-implementation.md)
  - [../runtime_storage_architecture.md](../runtime_storage_architecture.md)

## 결정

선물 runtime roadmap에서 ML/RL 예측 스택을 제거한다. 지금까지 투입한 학습, shadow, counterfactual, retraining 노력이 뉴스와 이벤트 변화에 뒤처지는 문제를 충분히 해결하지 못했다. 앞으로의 기본 방향은 LLM이 정보를 수집하고 시장 맥락을 추론하며, 실제 진입/청산 타이밍은 명시적 지표와 규칙 기반 전략이 담당하는 구조다.

이 결정은 다음 작업 방향을 supersede한다.

- `rl_mppo` 재학습 및 복귀 옵션 보존
- RL auxiliary filter 전환
- TFT/RL training loader 개선
- shadow/counterfactual 결과를 기반으로 한 RL 재활성화 gate

MLflow는 별도 제거 결정을 내리기 전까지 backtest/optimization 실험 추적용 선택 기능으로만 남긴다. ML/RL runtime 또는 training roadmap을 의미하지 않는다.

## 목표 상태

선물 intraday/swing trading은 아래 구조를 따른다.

1. LLM은 뉴스, 공시, macro event, 장중 regime, 변동성 환경, event risk를 수집하고 해석한다.
2. LLM 출력은 veto, risk mode, size scaling, threshold 조정, 설명 가능한 market note로 제한한다.
3. 진입/청산 trigger는 Williams %R, RSI, MACD, ATR, Bollinger Band, momentum decay, Setup A/C와 같은 명시적 지표/규칙이 담당한다.
4. 모든 threshold, 기간, risk 값은 YAML에서 관리한다.
5. paper/live 경로는 `TradingOrchestrator`와 runtime storage 기본값(Redis DB 1 + SQLite RuntimeLedger)을 사용한다.

LLM을 단독 가격 예측 모델처럼 사용하지 않는다. LLM의 역할은 "정보 수집과 맥락 판단"이고, 체결 가능한 신호의 최종 timing은 재현 가능한 지표/규칙이어야 한다.

## 유지

- Redis Streams, Redis DB 1 runtime state, TTL 정책
- SQLite `RuntimeLedger`
- `MarketDataStore`와 Parquet/DuckDB historical backend
- news/scoring/forecasting, `LLMContextPublisher`, LLM briefing
- `LLMAdaptiveSizer`, market context, risk mode, veto/threshold hooks
- indicator strategy registry와 backtest/optimization engine
- Setup A/C, Williams %R, BB/RSI/MACD, ATR/momentum based exits

## 제거 또는 이관

아래 항목은 active runtime/research roadmap에서 제거 대상이다.

- `sts rl *`, `sts tft *` runtime-facing commands
- `shared/ml/rl/`, `shared/ml/tft/`
- `scripts/training/`의 RL/TFT training paths
- `config/ml/rl_*`, `config/ml/tft.yaml`
- `shared/strategy/entry/rl_mppo.py`
- `shared/strategy/exit/rl_mppo_exit.py`
- `shared/strategy/rl_model_helpers.py`
- `config/strategies/futures/rl_mppo*.yaml`
- RL shadow logger, counterfactual cron, RL daily verification gates
- dashboard/API의 `rl` naming
- runtime storage acceptance의 ML/RL Parquet/DuckDB training support 항목

## 전략 마이그레이션

1. Setup A/C 설정에서 `rl_mppo_exit`를 제거하고 ATR, momentum decay, 또는 strategy-native exit로 교체한다.
2. 후보 futures strategy set은 다음을 기준으로 정리한다.
   - `setup_a_gap_reversion`
   - `setup_c_event_reaction`
   - `williams_r_15m`
   - `bb_reversion_15m`
   - `llm_directed_indicator` 계열은 과거 평가 실패 상태를 그대로 존중하며, 재활성화하려면 별도 재정의 gate가 필요하다.
3. LLM은 event/news/regime 기반의 veto, risk scaling, threshold tuning을 제공한다.
4. long/short symmetry는 유지한다.
5. 실전 전환은 기존 Phase 5 gate와 운영자 서면 승인 절차를 유지한다.

## 제거 단계

### Phase A — 문서 및 범위 고정

상태: completed, PR #402

- 이 문서를 active plan으로 등록한다.
- `CLAUDE.md`, plans index, runtime storage architecture의 ML/RL 보존 문구를 제거 방향으로 정렬한다.
- runtime storage checklist에서 ML/RL training loader 지원을 acceptance 밖으로 이관한다.

### Phase B — Runtime Strategy Migration

- 활성 futures config에서 `rl_mppo`와 `rl_mppo_exit` 참조를 제거한다.
- Setup A/C exit를 ATR/momentum/strategy-native exit로 바꾼다.
- dashboard/API label을 strategy-neutral naming으로 정리한다.
- paper smoke로 order/fill/position ledger durability를 확인한다.

### Phase C — CLI and Config Decommission

- `sts rl *`, `sts tft *` 명령을 제거하거나 archive-only로 숨긴다.
- `config/ml/`의 RL/TFT 설정을 제거하거나 archive로 이동한다.
- RL/TFT training scripts를 제거한다.

### Phase D — Code Deletion

- `shared/ml/rl/`, `shared/ml/tft/` 삭제.
- `RLMPPOEntry`, `RLMPPOExit`, `rl_model_helpers` 삭제.
- registry, tests, fixtures, cron, monitoring, runbooks의 RL/TFT 참조를 정리한다.

### Phase E — Verification and Cleanup

- default pytest가 ML/RL extra dependency 없이 통과한다.
- runtime-facing imports에서 `shared.ml` 참조가 없다.
- PR checks가 green이고 paper restart drill 결과를 runtime storage checklist에 반영한다.

## 완료 기준

- enabled futures strategy가 `rl_mppo` 또는 `rl_mppo_exit`를 참조하지 않는다.
- `sts --help`에 RL/TFT operational command가 노출되지 않는다.
- runtime-facing code가 `shared.ml`을 import하지 않는다.
- dashboard/API는 `rl` 전용 naming 없이 strategy-neutral 조회를 제공한다.
- default test/lint/type-check가 ML/RL optional dependency 없이 통과한다.
- runtime storage checklist는 backtest/research Parquet 지원만 추적하고, ML/RL training support를 미완료 runtime-storage gate로 남기지 않는다.

## 리스크와 완화

| 리스크 | 완화 |
|--------|------|
| Setup A/C가 아직 `rl_mppo_exit`에 의존 | Phase B에서 exit부터 교체하고 paper smoke로 검증 |
| ML/RL 삭제 중 테스트 fixture가 광범위하게 깨짐 | Phase C/D를 작게 나누고 registry/CLI/dashboard 순서로 제거 |
| 과거 성능 비교 자료 손실 | docs/archive 또는 git history를 보존하고 runtime path에서는 제거 |
| LLM 판단이 비결정적 | LLM은 veto/risk/threshold로 제한하고 최종 timing은 지표/규칙으로 고정 |
| 실전 감사 추적 약화 | RuntimeLedger와 signal_decisions/market_context_history에 LLM 판단 근거를 저장 |
