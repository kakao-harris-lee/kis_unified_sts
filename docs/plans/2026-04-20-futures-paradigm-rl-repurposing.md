# RL 재활용 — 메인에서 보조 필터로 전환

**Status:** Draft (Phase 5 이후 활성화)
**Parent:** `docs/plans/2026-04-20-futures-paradigm-master.md`
**Target branch:** `feat/futures-paradigm-rl-repurpose`
**Depends on:** Phase 5 Gate 3 통과 + 3개월 EV+ 유지
**Blocks:** (최종 cleanup)

---

## 1. 목표

Phase 5에서 규칙 기반 시스템이 안정되면, 기존 `rl_mppo` 모델을 버리지 않고 **진입 적합성 보조 필터** 로 재활용한다. 원본 지침서 §11에서 제시한 방향을 실행 가능한 단계로 상세화.

**중요 원칙:**
- `rl_mppo`가 **주된 의사결정자** 였던 과거 구조는 단계적으로 폐지한다
- 전환 시점은 **규칙 시스템 3개월 이상 EV+** 검증 이후
- 최초 3개월은 **shadow-log only** (실제 거래 영향 없음)
- A/B 비교로 RL이 실제 EV를 높이는지 증명한 뒤 활성화

---

## 2. 전제 조건 (활성화 게이트)

모두 만족해야 본 작업 착수:

- [ ] Phase 5 Gate 3 통과 (1계약 실전 2주)
- [ ] 누적 3개월 규칙 시스템 EV+ 유지
- [ ] 규칙 시스템 Sharpe ≥ 1.5
- [ ] 평균 슬리피지 ≤ 0.4 tick
- [ ] `rl_mppo` 현재 운용 버전 기록 (성능 snapshot for baseline)

미달 시 본 spec 착수 연기 (대기 상태).

---

## 3. 새 역할 정의

### 3.1 기존 RL 아키텍처

```
MarketContext → RL policy (Maskable PPO) → {LONG_ENTRY, LONG_EXIT, SHORT_ENTRY, SHORT_EXIT, HOLD}
```

5개 액션 직접 결정 = 메인 trader.

### 3.2 새 역할

```
Setup A/C 시그널 + 리스크 필터 통과 → RL auxiliary filter → {PASS, SKIP}
```

**RL은 진입 여부 2지 선택만** 담당. 방향/가격/타겟은 규칙 엔진이 결정.

### 3.3 State / Action / Reward

```python
# State (규칙 시그널 + 시장 상태 특징 ≈ 20차원)
state = {
    # 시그널 정보
    "setup_type_onehot": [A, C],
    "signal_confidence": float,
    "signal_direction": {+1, -1},
    "entry_vs_vwap": float,           # (entry - vwap) / atr
    "stop_distance_atr": float,

    # 시장 상태
    "current_vol_pct": float,
    "atr_ratio_to_90p": float,
    "time_of_day_normalized": float,  # 0~1 (09:00 → 15:20)
    "minutes_since_macro_event": float | None,

    # 포트폴리오 상태
    "recent_5d_winrate": float,
    "current_daily_pnl_pct": float,
    "consecutive_losses": int,
}

# Action
action = {0: PASS, 1: SKIP}

# Reward (진입 결정 후 실제 tick PnL)
reward = realized_ticks_after_fees   # tick 단위, +/-
```

### 3.4 학습 데이터

- **요건:** 실제 규칙 시스템이 생성한 최소 **3개월 × 모든 시그널** (실행 + skip 모두) + 사후 PnL
- Phase 5 기간 축적된 `signals_all` + `order_fills` join
- 실행된 시그널 → 실제 PnL
- Skip된 시그널 → counterfactual PnL (백테스트로 추정, 노이즈 표시)

**데이터 부족 위험:** 3개월에 Setup별 ~30~60 trades 예상. 6개월 축적 대기 권장.

---

## 4. 구현 단계

### 4.1 Stage 1 — Shadow Log Only (≥ 3개월)

- 기존 `rl_mppo`를 그대로 재학습하지 않고, **신규 어택셔너리 필터 모델**(작은 MLP 또는 LightGBM)을 학습
- 학습은 오프라인 (배치)
- 실시간: 시그널이 risk_filter 통과하면 **fallback PASS** + RL prediction을 `signals_all.rl_aux_prediction` 컬럼에 로깅만
- 실제 거래에는 RL 영향 없음

### 4.2 Stage 2 — A/B 비교

- 3개월 shadow log 후 분석:
  - RL이 PASS한 시그널의 평균 PnL
  - RL이 SKIP했지만 실행된 시그널의 평균 PnL
  - RL을 따랐다면 EV 개선 여부
- 비교 결과 **EV +0.2 tick 이상** 개선 시 Stage 3 진행
- 개선 없으면 RL 보조 필터 도입 무기한 연기

### 4.3 Stage 3 — 조건부 활성화

- `config/rl_auxiliary.yaml`에 `enabled: true` + `confidence_threshold: 0.6`
- RL prediction `P(PASS) < 0.6`인 시그널만 skip
- 1주 단위 효과 측정, 음의 효과 시 즉시 비활성화

### 4.4 Stage 4 — 기존 `rl_mppo` 메인 운용 폐지

- Phase 5의 `rl_mppo` 병행 paper가 3개월 이상 신 시스템 대비 underperform 시점에 메인 운용 중단
- 모델 자산 (best_model.zip, scaler) 아카이브 (`models/futures/rl/archive/` 이동)
- cron 제거

---

## 5. 기존 학습 파이프라인 재활용

`shared/ml/rl/env.py`, `trainer.py`는 **유지**. 새 MLP 필터 학습은 별도 경로:

```
shared/ml/auxiliary_filter/
├── __init__.py
├── dataset.py         # signals_all + order_fills join
├── features.py        # 20차원 state 추출
├── model.py           # PyTorch MLP or LightGBM wrapper
├── trainer.py         # 오프라인 학습
└── predictor.py       # 실시간 추론 (risk_filter 내 호출)
```

**중요:** Maskable PPO를 PASS/SKIP 2지 선택으로 retrain하는 것은 비효율. 2지 선택은 작은 MLP/GBM이 적합.

---

## 6. 모니터링 (Stage 1-2)

### 6.1 ClickHouse 컬럼 추가

```sql
ALTER TABLE kospi.signals_all
  ADD COLUMN rl_aux_prediction Nullable(Float32),
  ADD COLUMN rl_aux_decision LowCardinality(String) DEFAULT '';
```

### 6.2 Prometheus

```
rl_aux_prediction_histogram       Histogram
rl_aux_agreement_rate             Gauge (PASS 정답률 proxy)
rl_aux_skipped_pnl                Gauge (skip했으면 어땠을지 EV)
```

### 6.3 Grafana (RL Aux 대시보드)

- PASS / SKIP 분포
- 매일 shadow A/B EV 비교
- 모델 drift (prediction distribution over time)

---

## 7. RL 재학습 금지 목록 (기존 메모리 유지)

메모리 기록에 따르면:
- SAC 재학습 불필요 (2회 완료, MPPO 미달)
- DT 재학습 불필요 (MPPO expert 모방 — 원본 초과 불가)
- TFT RL 통합 불가
- HMM Multi-Agent 보류 (데이터 부족)
- Hierarchical RL 보류 (max_contracts=1 무의미)

**본 spec은 위 금지 사항을 변경하지 않는다.** 보조 필터는 **새로운 작은 모델** (MLP/GBM)이며 기존 RL 재학습이 아님.

---

## 8. 완료 게이트

본 spec의 "완료" = Stage 3 활성화 성공 or Stage 2에서 비활성 결정 문서화:

- **활성화 경로:** Stage 3 1개월 운영 + A/B에서 +0.2 tick EV 개선 유지
- **비활성화 경로:** Stage 2에서 개선 없음 문서화 → `disabled.md` 추가 → 6개월 후 재시도 검토

---

## 9. 명시적 비범위

- 기존 `rl_mppo` MPPO 재학습 (메모리 금지 사항 준수)
- 주식 RL 확장 (선물 전용)
- 계층적 RL 보조 필터 (현재 단일 계약, 무의미)
- 메인 trader 역할 부활 (단방향 전환 — 돌아가지 않음)

---

## 10. Pre-implementation review (2026-04-25)

Phase 3 구현 + Optuna 튜닝 결과를 반영한 본 spec의 risks/assumptions 점검:

### 10.1 Setup C 데이터 부족 위험 (HIGH)

§3.4는 "3개월에 Setup별 ~30-60 trades 예상"이라 가정하지만, 실측 Phase 3
데이터로 추정하면:

- Setup A (tuned): 160 trades / 296일 ≈ **~16/month**  → 3개월 ~48 trades ✓
- Setup C (tuned): 9 trades / 296일 ≈ **~0.9/month** → 3개월 ~3 trades ✗

Setup C는 샘플이 극단적으로 적어 MLP 필터 학습 불가능. 다음 중 하나 필요:

- **(권장)** Setup A 전용 RL aux로 시작, Setup C는 규칙 + 수동 검토만
- Setup C를 학습 제외하고 무조건 PASS시키는 pass-through 경로 명시
- Setup C 활성화를 6-12개월 축적 후로 연기

§2 활성화 게이트에 **"Setup별 trade 수 ≥ 50"** 조건 추가 권장.

### 10.2 Counterfactual PnL은 이미 기록됨 (opportunity)

§3.4 "Skip된 시그널 → counterfactual PnL (백테스트로 추정, 노이즈 표시)"를
복잡하게 만들 필요 없음. Phase 3의 `signals_all`은 이미:

- `executed=0` + `skip_reason`으로 **filter-rejected 시그널을 모두 기록**
- `TradeRecord`는 simulated fill을 실행함 — fill이 없더라도 stop/target
  hypothetical 계산은 harness에서 이미 한다

**단순화 제안:** RL aux dataset = `signals_all JOIN order_fills` ON
signal_id. skip된 시그널의 counterfactual은 harness replay로 재계산
(yfinance macro + phantom-filtered CH data로 bit-exact 재현 가능).
`signals_all.rl_aux_prediction` 컬럼 추가만으로 충분.

### 10.3 런타임 feature 생성 경로 미명시 (MEDIUM)

§3.3 state에 포함된 다음 필드들은 **어디서 어떻게 계산되는지 미지정**:

| Feature | 어디서 오는가 | Phase 현재 상태 |
|---------|-------------|----------------|
| `recent_5d_winrate` | 롤링 5-day PnL window | **미구현** — Phase 4에 `jobs/weekly_edge_review.py`가 유사 쿼리 있으나 실시간용 아님 |
| `current_daily_pnl_pct` | `RiskState.daily_pnl_krw / account_equity_krw` | ✅ Phase 3 완료 |
| `consecutive_losses` | `RiskState.consecutive_losses` | ✅ Phase 3 완료 |
| `minutes_since_macro_event` | `MarketContext.find_recent_event()` 역산 | ✅ 가능하나 Phase 4에서 helper 필요 |

**권장:** §4.1 Stage 1 시작 전에 `shared/ml/auxiliary_filter/features.py`에
각 필드의 source-of-truth를 명시 + Phase 4 runtime에 필요한 feature
producer를 등록한다.

### 10.4 Fallback behavior 미지정 (HIGH for production safety)

§4.1은 "실시간: 시그널이 risk_filter 통과하면 **fallback PASS** + RL
prediction 로깅"이라 하나 **RL 모델 inference 실패 시**(모델 파일 missing,
GPU 없음, torch import error 등) 동작이 명시되지 않음. 다음 추가 권장:

> **Fallback rule (inference failure):** if `predictor.predict()` raises
> or times out (>50 ms), log `rl_aux_decision = "error_pass"` and let
> the signal through. Never block on a broken auxiliary filter.

### 10.5 Stage 3 활성화 임계값이 하드코딩 후보 (LOW)

§4.3 `confidence_threshold: 0.6` — YAML인 건 맞지만, 단일 threshold는
too coarse. Setup별로 다를 수 있으니:

```yaml
# config/rl_auxiliary.yaml
rl_auxiliary:
  enabled: true
  per_setup_threshold:
    A_gap_reversion: 0.60
    C_event_reaction: 0.75      # Setup C는 샘플 적어 보수적
```

### 10.6 ClickHouse 마이그레이션 V-number 지정 (LOW)

§6.1 `ALTER TABLE kospi.signals_all` 추가 컬럼 2개. 현재 V1(Phase 1) +
V2(Phase 2 news_scored). Phase 4가 V3(order_fills), RL spec는 **V5 혹은
V6**로 번호 할당 필요 (Phase 4/5가 V3/V4 점유).

### 10.7 Stage 4 gate 기준 미정의 (MEDIUM)

§4.4 "Phase 5의 rl_mppo 병행 paper가 3개월 이상 신 시스템 대비
underperform 시점" — metric 미정. 다음 기준 제안:

```
rl_mppo가 3개월 누적 rolling window에서
  (a) Sharpe이 규칙 시스템 대비 < 70%  AND
  (b) MDD가 규칙 시스템 대비 > 130%
두 조건 모두 만족할 때 메인 운용 중단.
단일 조건만 만족 시 추가 1개월 관찰 연장.
```

### 10.8 완료 게이트 조건 업데이트 권장

§8 "완료" 정의에 다음 추가:

- **비활성화 경로 시한:** Stage 2 개선 없음 결론 나면 `disabled.md` +
  **6개월 후 재시도 cron으로 자동 대기 리마인더** (기다리지 않으면 잊음)

### 10.9 의존성 timeline

Master plan 기준 RL spec 착수 가능 시점:

- Phase 4 완료 (Week 6) + Phase 5 Gate 3 (Week 7-9) + 3개월 EV+
- **= 현 시점 + 약 5-6개월 (2026-09 이후)**
- Setup C 데이터 축적 (§10.1)을 반영하면 **2026-12 이후**가 현실적

---

**리뷰 요약:** spec 자체는 잘 구성돼 있음. 주요 보강 포인트는 (a) Setup C
데이터 부족 대응, (b) 런타임 feature producer 명시, (c) inference failure
fallback rule. Stage 1 착수 전 §10.1-§10.4 반영한 v2 draft 권장.
