# Hybrid Learning Data Pipeline Plan

## 목적

`deep-research-report.md`를 바탕으로 **실제 KOSPI200 선물 데이터 + 생성 데이터 + 해외 지수선물 패턴 전이 데이터**를 통합한 학습용 데이터 파이프라인을 구축한다. 최종 목표는 다음 3가지다.

1. **시장 비정상성(non-stationarity)** 에 대응 가능한 학습 데이터 확보
2. 기존 `rl_mppo` 학습 파이프라인에 **생성 데이터 기반 추가 학습**을 연결
3. 실제 보유 KOSPI 데이터 대비 **성능 개선 여부를 정량 검증**

이 문서는 구현 순서가 아니라, **phase별 개발/검증이 가능한 실행 계획서**다.

---

## 설계 원칙

- **Configuration-driven only**
  - 혼합 비율, 시나리오 비중, jump 강도, 변동성 스케일 등 모든 값은 YAML로 관리한다.
- **실거래 holdout 우선**
  - 생성 데이터는 train/augmentation 전용으로 사용하고, 최종 검증은 반드시 real KOSPI holdout 구간에서 수행한다.
- **기존 RL 경로 재사용**
  - 기준 진입점은 `scripts/training/train_rl.py`, `config/ml/rl_mppo.yaml`, `shared/ml/rl/trainer.py`, `shared/ml/rl/evaluator.py`를 사용한다.
- **데이터 lineage 추적**
  - 모든 dataset artifact에 source, regime, generator version, calibration version, seed를 남긴다.
- **과최적화 방지**
  - synthetic 성능이 좋아도 real holdout / stress holdout / rolling evaluation이 개선되지 않으면 채택하지 않는다.

---

## 현재 기준점 (Existing Anchors)

현재 리포지토리에는 아래 자산이 이미 존재하므로 새 파이프라인은 이를 확장하는 형태로 설계한다.

- RL 학습 진입점: `scripts/training/train_rl.py`
- RL 설정: `config/ml/rl_mppo.yaml`
- RL 비교 리포트: `scripts/training/compare_rl_algos.py`
- 자동 재학습 파이프라인: `shared/ml/rl/retraining_pipeline.py`
- RL 평가기: `shared/ml/rl/evaluator.py`
- RL feature 계산기: `shared/ml/rl/features.py`
- 연구 입력 문서: `deep-research-report.md`

즉, 신규 구현은 **새로운 실험 코드의 난립**이 아니라, 기존 RL 학습/평가 체인에 dataset source를 추가하는 방식으로 진행한다.

---

## 목표 아키텍처

```text
Real KOSPI Data  ─┐
                  ├─> Regime Tagger ─┐
US Futures Data  ─┤                  │
JP Futures Data  ─┘                  ├─> Pattern Transfer / Calibration ─┐
Synthetic Generator (GARCH + Jump) ──┘                                     │
                                                                           ├─> Hybrid Dataset Builder
Real Extreme Windows / Stress Windows ──────────────────────────────────────┘
                                                                                  │
                                                                                  ├─> RL Train Dataset
                                                                                  ├─> RL Validation Dataset
                                                                                  └─> Real-only Holdout Dataset

Hybrid Dataset -> existing RL feature pipeline -> `rl_mppo` retraining -> evaluation/comparison
```

---

## 제안 디렉토리/파일 구조

### 신규 설정 파일

- `config/ml/synthetic_data.yaml`
  - 생성기 파라미터, jump, intraday seasonality, seed, scenario weights
- `config/ml/cross_market_transfer.yaml`
  - 미국/일본 선물 데이터 매핑 규칙, scaling, volatility normalization, session mapping
- `config/ml/hybrid_dataset.yaml`
  - real/synthetic/transfer 데이터 혼합 비율, split 정책, validation holdout 정책
- `config/ml/rl_mppo_synthetic_finetune.yaml`
  - 기존 `rl_mppo`를 상속/복제해 hybrid dataset 학습 설정 추가

### 신규 Python 모듈

- `shared/ml/data/regime_labeler.py`
  - bull/bear/sideways/high-vol/crash/rebound/gap/open-drive 등 regime 태깅
- `shared/ml/data/synthetic/generator.py`
  - GJR-GARCH/Student-t/jump 기반 synthetic return generator
- `shared/ml/data/synthetic/intraday.py`
  - 장중 U-shape volatility/volume profile 반영
- `shared/ml/data/synthetic/ohlcv_builder.py`
  - return path -> OHLCV 변환
- `shared/ml/data/transfer/cross_market_adapter.py`
  - US/JP futures 패턴을 KOSPI200-like distribution으로 스케일 조정
- `shared/ml/data/calibration/kospi_calibrator.py`
  - KOSPI target stylized facts에 맞는 calibration 모듈
- `shared/ml/data/hybrid_dataset_builder.py`
  - source 병합, tagging, split, artifact 저장
- `shared/ml/data/validation/stylized_facts.py`
  - ACF, volatility clustering, tail index, jump frequency, intraday curve 검증
- `shared/ml/data/validation/dataset_quality.py`
  - OHLCV 무결성, duplication, monotonicity, volume anomalies 검사

### 신규 스크립트

- `scripts/training/build_real_regime_catalog.py`
- `scripts/training/build_synthetic_dataset.py`
- `scripts/training/build_transfer_dataset.py`
- `scripts/training/build_hybrid_rl_dataset.py`
- `scripts/training/train_rl_hybrid.py`
- `scripts/training/evaluate_rl_hybrid.py`
- `scripts/training/ablation_hybrid_components.py`

### 테스트

- `tests/unit/ml/data/test_regime_labeler.py`
- `tests/unit/ml/data/test_synthetic_generator.py`
- `tests/unit/ml/data/test_cross_market_adapter.py`
- `tests/unit/ml/data/test_hybrid_dataset_builder.py`
- `tests/integration/ml/test_hybrid_rl_training.py`
- `tests/integration/ml/test_hybrid_dataset_materialization.py`

---

## Phase 0 — Baseline 고정 및 실험 규약 수립

### 목표

현재 `rl_mppo` 기준 성능과 데이터 경로를 고정해 이후 모든 비교의 기준점으로 삼는다.

### 구현 작업

- `scripts/training/train_rl.py`의 현재 data split, scaler fit, feature 계산 흐름을 문서화
- baseline 실험 메타데이터 표준 정의
  - train period
  - test period
  - symbol
  - feature version
  - reward version
  - slippage setting
- 결과 저장 규칙 정의
  - `artifacts/rl/hybrid/{run_id}/...`
- 비교 metric 확정
  - Sharpe
  - total return
  - max drawdown
  - win rate
  - RR ratio
  - total trades
  - regime별 성능

### 산출물

- baseline metrics snapshot
- baseline config snapshot
- experiment naming convention 문서화

### 검증

- `scripts/training/compare_rl_algos.py`로 baseline MPPO 성능 재현
- 최소 1회 동일 설정 재실행 시 결과 drift가 허용 범위 내인지 확인

### 완료 기준

- 이후 phase의 모든 결과가 baseline 대비 비교 가능해야 한다.

---

## Phase 1 — Real KOSPI 데이터 정제 및 Regime Catalog 구축

### 목표

실제 KOSPI200 선물 데이터를 단순 학습 원천이 아니라, **regime reference library**로 재구성한다.

### 구현 작업

- 기존 ClickHouse source(`kospi.kospi200f_1m`, `101S6000`)에서 학습 대상 기간 적재
- 분봉 데이터 품질 검사 강화
  - duplicate datetime
  - non-monotonic timestamp
  - zero-volume with price move
  - 장 시작/종료 missing bar
- regime labeler 구현
  - market trend: bull / bear / sideways
  - volatility state: low / normal / high / shock
  - event windows: crash / rebound / melt-up / opening-drive / gap-down / squeeze
- rolling window 기반 regime metadata 저장
- 실제 extreme 구간 라이브러리 구성
  - 급락일
  - 급반등일
  - 단기 과열 추세일
  - 장중 변동성 급증 구간

### 산출물

- `artifacts/datasets/regime_catalog/*.parquet`
- `artifacts/datasets/regime_catalog/summary.json`
- phase 1 validation report

### 검증

- 수동 샘플링으로 regime label 정성 검토
- regime별 bar/day count, return distribution, realized vol 비교
- 추세/변동성 라벨이 눈으로 봐도 납득 가능한지 차트 spot-check

### 완료 기준

- synthetic/transfer 데이터가 **무엇을 닮아야 하는지** 정의한 reference catalog가 준비되어야 한다.

---

## Phase 2 — Synthetic KOSPI-like Generator 1차 구현

### 목표

`deep-research-report.md`의 모델을 바탕으로 KOSPI-like 1분봉 synthetic OHLCV generator를 만든다.

### 구현 작업

- return generator 구현
  - GJR-GARCH 또는 EGARCH-style volatility
  - Student-t innovations
  - jump mixture
- intraday profile 구현
  - volatility U-shape
  - volume U-shape
  - lunch-time liquidity drop 반영 여부 옵션화
- OHLCV builder 구현
  - return path -> open/high/low/close
  - volume profile + burst + shock 연계
- scenario preset 지원
  - `normal_trend`
  - `sideways_chop`
  - `crash_day`
  - `panic_rebound`
  - `melt_up`
  - `gap_and_fade`
  - `volatility_cluster`
- seed 고정 및 재현성 보장

### 산출물

- synthetic parquet dataset
- scenario별 summary statistics
- seed/revision metadata

### 검증

- OHLCV 구조 검증
  - `low <= min(open, close) <= high`
  - negative volume 금지
  - timestamp monotonicity
- stylized facts 검증
  - fat tail
  - volatility clustering
  - leverage effect 근사
  - intraday volatility curve
- 실제 KOSPI와 1차 통계 비교
  - return std
  - kurtosis
  - autocorrelation of absolute returns
  - jump frequency

### 완료 기준

- synthetic 데이터가 “그럴듯한 가짜 차트” 수준이 아니라, **실제 KOSPI의 기본 stylized facts**를 재현해야 한다.

---

## Phase 3 — KOSPI Calibration 및 Stress Scenario 확장

### 목표

synthetic generator를 KOSPI200 데이터에 정렬(calibration)하고, 실데이터에 드문 극단 시나리오를 의도적으로 보강한다.

### 구현 작업

- calibration target 정의
  - daily/intraday realized vol distribution
  - tail quantiles
  - drawdown depth / duration
  - rebound speed
  - volume spike intensity
- parameter search / calibration 루프 구현
- regime-conditioned synthetic generation 지원
  - bull-high-momentum
  - bear-panic
  - mean-reverting chop
  - low-vol compression -> breakout
- rare-event oversampling 정책 정의
  - crash/rebound/jump day 비중 상향
  - but validation holdout은 real-only 유지
- scenario bank 버전 관리

### 산출물

- calibrated synthetic config
- stress scenario library
- calibration scorecard

### 검증

- KS distance / Wasserstein distance 등 분포 유사도 측정
- regime별 통계 유사도 측정
- 특정 시나리오(급락/급반등/급등 추세)에 대해 사람이 차트를 보고 납득 가능한지 review

### 완료 기준

- synthetic 데이터가 KOSPI-like일 뿐 아니라, **훈련에 의미 있는 극단 상황을 충분히 포함**해야 한다.

---

## Phase 4 — 미국/일본 선물 패턴 전이 데이터 구축

### 목표

미국 및 일본 지수선물 데이터의 유용한 구조적 패턴을 가져오되, 이를 그대로 쓰지 않고 **KOSPI200-like feature space**로 변환한다.

### 구현 작업

- 대상 데이터 선정
  - 미국: S&P500, Nasdaq, 혹은 미니 지수선물 계열
  - 일본: Nikkei 225 선물 계열
- 세션/타임존 정규화
- price level 제거 후 패턴 중심 변환
  - return normalization
  - volatility normalization
  - volume percentile normalization
- KOSPI mapping layer 구현
  - KOSPI intraday profile로 재가중
  - KOSPI jump frequency / noise scale에 맞게 변형
  - 과도한 해외 market microstructure artifact 제거
- regime transfer tagging
  - 해외 급락/반등 패턴을 KOSPI crisis-style sample로 변환
  - 해외 trend persistence를 KOSPI-like duration으로 리샘플

### 산출물

- transfer dataset parquet
- source-to-target mapping report
- 변환 전/후 통계 비교표

### 검증

- 원본 해외 데이터와 변환 후 데이터의 분포 차이 측정
- KOSPI reference catalog와의 근접도 측정
- 한국장 구조와 맞지 않는 artifact 존재 여부 점검
  - 비현실적인 overnight gap 비중
  - 거래시간 mismatch
  - 비정상적 volume seasonality

### 완료 기준

- transfer dataset은 “해외 데이터를 섞었다”가 아니라, **KOSPI 학습에 도움 되는 패턴 augmentation source**여야 한다.

---

## Phase 5 — Hybrid Dataset Builder 구현

### 목표

real + synthetic + transfer 데이터를 단일 RL 학습용 dataset으로 materialize한다.

### 구현 작업

- hybrid dataset schema 정의
  - `source_type`: real / synthetic / transfer
  - `source_market`: kospi / us / jp / synthetic
  - `regime_label`
  - `scenario_id`
  - `generator_version`
  - `calibration_version`
- mixing policy 구현
  - example: train = 50% real + 30% synthetic + 20% transfer
  - regime imbalance 보정 옵션
  - curriculum mode 지원
    - pretrain on synthetic/transfer
    - finetune on recent real KOSPI
- split policy 구현
  - train: hybrid
  - validation: hybrid + partial real
  - final test: real-only out-of-time holdout
  - stress test: extreme real windows only
- artifact 저장
  - parquet + manifest JSON
  - feature-ready numpy/day arrays optional export

### 산출물

- hybrid train/validation/test manifests
- dataset profile report
- feature-ready serialized arrays (optional)

### 검증

- leakage 검사
  - 동일 day/window가 train/test 양쪽에 없는지
- source/regime mixing 비율 검증
- feature 계산 가능 여부 확인 (`RLFeatureCalculator` 호환)
- day-wise split이 기존 `train_rl.py`와 충돌 없는지 확인

### 완료 기준

- 기존 RL 파이프라인이 dataset source만 바꿔도 hybrid 데이터를 읽어 학습 가능해야 한다.

---

## Phase 6 — RL MPPO Hybrid Pretrain / Finetune 경로 구현

### 목표

기존 `rl_mppo`를 hybrid dataset으로 추가 학습하고, real-only baseline과 비교 가능한 실험 체계를 만든다.

### 구현 작업

- `train_rl.py` 확장 또는 `train_rl_hybrid.py` 추가
  - ClickHouse 직접 로드 외에 manifest/parquet dataset 로드 지원
- 학습 모드 지원
  - `real_only`
  - `synthetic_pretrain_then_real_finetune`
  - `hybrid_joint_training`
  - `transfer_plus_real`
- config 확장
  - dataset source path
  - stage-wise timesteps
  - phase transition rule
  - source weighting schedule
- 모델/스케일러 저장 규칙 통일
- 기존 `shared/ml/rl/retraining_pipeline.py` 와의 연결 포인트 설계
  - 향후 자동 재학습 시 hybrid dataset 사용 가능하도록 추상화

### 실험 매트릭스

최소 아래 실험군을 비교한다.

1. **Baseline**: real-only MPPO
2. **Synthetic pretrain + real finetune**
3. **Hybrid joint training**
4. **Transfer + real**
5. **Synthetic + transfer + real**

### 산출물

- 학습된 모델 아티팩트
- scaler/manifest/model card
- experiment summary table

### 검증

- 학습이 정상 수렴하는지 확인
- action distribution collapse 여부 점검
- train vs validation divergence 점검
- 동일 evaluation set에서 baseline 대비 성능 비교

### 완료 기준

- hybrid 경로가 단지 학습 완료가 아니라, baseline 대비 장점/약점이 명확히 보이는 수준까지 정리되어야 한다.

---

## Phase 7 — 평가, Ablation, 채택 기준 확정

### 목표

어떤 데이터 소스 조합이 실제로 도움이 되는지 분해해서 검증하고, 운영 채택 기준을 확정한다.

### 구현 작업

- 평가 세트 구성
  - out-of-time real holdout
  - crisis windows
  - melt-up / rebound / sideways window
- ablation study 수행
  - without synthetic
  - without transfer
  - without stress oversampling
  - without finetune stage
- regime별 성능 리포트 추가
- champion/challenger 기준 정의
  - Sharpe improvement minimum
  - MDD deterioration cap
  - minimum trade count
  - regime robustness threshold

### 산출물

- comparison report
- ablation report
- 운영 채택 decision memo

### 검증

- `scripts/training/compare_rl_algos.py` 기반 비교표 생성
- 필요 시 `shared/ml/rl/champion_challenger.py` 기준으로 승격 판단
- hidden overfit 징후 확인
  - real holdout underperformance
  - 특정 regime에만 과도하게 최적화
  - trade frequency 붕괴

### 완료 기준

- “synthetic을 넣으니 좋아 보인다”가 아니라, **실제 KOSPI 미래 구간에서도 더 견고하다**는 근거가 있어야 한다.

---

## Phase 8 — 운영화 준비 (선택)

### 목표

성능 개선이 확인되면 재학습/리포팅 체인에 hybrid dataset 빌드 단계를 편입한다.

### 구현 작업

- retraining pipeline 앞단에 dataset build stage 추가
- artifacts/manifest/version 관리 자동화
- MLflow logging 항목 확대
  - dataset composition
  - scenario weights
  - calibration scores
- 실패 시 rollback 기준 정리

### 산출물

- automated retraining runbook
- 운영용 config
- 장애 대응 체크리스트

### 검증

- 샘플 재학습 파이프라인 dry-run
- artifact lineage 추적 가능 여부 확인

### 완료 기준

- 수동 실험 단계를 넘어 반복 가능한 운영 워크플로우가 되어야 한다.

---

## 핵심 검증 프레임

### 1. 데이터 품질 검증

모든 source에 대해 아래를 공통 검증한다.

- timestamp monotonicity
- duplicate row absence
- OHLC consistency
- non-negative volume
- 장 세션 일관성
- 결측치 / 이상치 비율

### 2. Stylized Facts 검증

synthetic/transfer 데이터는 최소 아래 항목에서 real KOSPI와 비교한다.

- return distribution skew/kurtosis
- fat-tail intensity
- volatility clustering
- leverage effect
- jump frequency and magnitude
- intraday volatility curve
- intraday volume curve
- drawdown depth / recovery speed

### 3. 학습 적합성 검증

- `RLFeatureCalculator` 계산 가능 여부
- feature NaN ratio
- scaling 안정성
- day-wise segmentation integrity

### 4. 모델 성능 검증

- total return
- Sharpe ratio
- max drawdown
- win rate
- RR ratio
- trade count
- regime-specific performance
- out-of-time robustness

---

## 절대 지켜야 할 비교 규칙

1. **최종 채택 판단은 real-only holdout 기준**으로 한다.
2. synthetic/transfer 데이터는 validation 개선이 아니라 **generalization 개선**을 만들어야 한다.
3. stress scenario 성능이 좋아도 normal real holdout이 악화되면 채택하지 않는다.
4. baseline보다 수익은 높지만 MDD가 과도하게 악화되면 탈락한다.
5. 특정 regime에서만 성능이 좋아지는 경우 운영 채택 전 별도 risk note를 남긴다.

---

## 우선 구현 순서

실행 효율을 고려한 추천 순서는 아래와 같다.

1. Phase 0 — baseline 고정
2. Phase 1 — real regime catalog
3. Phase 2 — synthetic generator 1차
4. Phase 5 — hybrid dataset builder 최소 버전
5. Phase 6 — RL MPPO hybrid pretrain/finetune
6. Phase 3 — calibration/stress 확장
7. Phase 4 — US/JP transfer dataset
8. Phase 7 — ablation / 채택 판단
9. Phase 8 — 운영화

이 순서를 쓰는 이유는, **먼저 synthetic-only 최소 실험 루프를 닫아야** 이후 cross-market transfer의 효과도 분리해서 볼 수 있기 때문이다.

---

## 1차 구현 범위 (MVP)

처음부터 모든 것을 만들지 말고, 아래 범위를 MVP로 본다.

- real regime catalog
- synthetic generator v1
- hybrid dataset builder v1
- `rl_mppo` synthetic pretrain + real finetune
- baseline vs hybrid comparison report

즉, **MVP는 “생성 데이터를 섞어 RL MPPO를 추가 학습하고 real holdout에서 baseline과 비교”까지**다.
미국/일본 패턴 전이는 MVP 이후 확장 phase로 두는 것이 안전하다.

---

## Phase별 체크리스트 요약

| Phase | 핵심 결과 | 검증 기준 |
|---|---|---|
| 0 | baseline 고정 | 현재 MPPO 성능 재현 |
| 1 | real regime catalog | 라벨/통계 spot-check 통과 |
| 2 | synthetic generator v1 | stylized facts 유사성 확보 |
| 3 | calibrated stress library | extreme scenario 커버리지 확보 |
| 4 | US/JP transfer dataset | KOSPI-like 변환 품질 통과 |
| 5 | hybrid dataset manifest | leakage 없이 RL 입력 가능 |
| 6 | hybrid-trained MPPO | baseline과 공정 비교 가능 |
| 7 | ablation/comparison report | real holdout robustness 입증 |
| 8 | 운영화 | 재현 가능한 자동 파이프라인 |

---

## 최종 성공 기준

이 프로젝트는 아래 조건을 만족할 때 성공으로 본다.

- hybrid dataset이 기존 RL 학습 경로에 자연스럽게 연결된다.
- 생성 데이터가 실제 KOSPI stylized facts와 충분히 유사하다.
- stress/rebound/melt-up 등 희귀 시나리오 대응 학습이 가능하다.
- `rl_mppo`가 real-only baseline 대비 **real holdout에서 더 견고한 성능**을 보인다.
- 실험 결과와 dataset lineage가 추적 가능하다.

---

## 다음 실행 권장

바로 구현에 들어갈 때는 아래 순서로 시작한다.

1. `config/ml/synthetic_data.yaml` 초안 작성
2. `shared/ml/data/regime_labeler.py` 구현
3. `shared/ml/data/synthetic/generator.py` + `ohlcv_builder.py` 구현
4. `scripts/training/build_hybrid_rl_dataset.py` 최소 버전 구현
5. `scripts/training/train_rl_hybrid.py`에서 baseline vs synthetic-pretrain 비교 시작

작게 시작해서, 차트를 속이는 generator가 아니라 **모델을 강하게 만드는 dataset**을 만드는 쪽으로 가야 한다. 금융 데이터는 늘 겉보기보다 교활하니까요.
