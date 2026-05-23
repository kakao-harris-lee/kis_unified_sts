# RL 재활용 v2 — 메인에서 보조 필터로 전환

**Status:** Draft v2 (supersedes v1 §1-§9 + integrates v1 §10 review findings)
**Parent:** `docs/plans/2026-04-20-futures-paradigm-master.md`
**Predecessor:** `docs/plans/2026-04-20-futures-paradigm-rl-repurposing.md` (v1 + §10 review)
**Target branch:** `feat/futures-paradigm-rl-repurpose`
**Depends on:** Phase 5 Gate 3 통과 + 3개월 EV+ 유지 + Setup 별 trade 수 ≥ 50 (Setup C는 대기 경로)
**Blocks:** (최종 cleanup)

---

## What changed from v1

| 항목 | v1 | v2 | 이유 |
|------|----|----|------|
| 활성화 게이트에 Setup 별 trade 수 추가 | 없음 | **Setup A 필수 ≥ 50**, Setup C 대기 경로 | Phase 3 실측 — Setup C ~0.9 trade/mo (v1 §10.1) |
| Counterfactual PnL 재계산 방법 | 백테스트로 추정 (복잡) | **`signals_all` 그대로 join** — 이미 Phase 3 `executed=0` + `skip_reason` 기록됨 | v1 §10.2 opportunity |
| 런타임 feature producer 책임 | 미명시 | **§4 Feature Producer Registry** 명시 | v1 §10.3 |
| Inference 실패 fallback | 없음 | **error_pass + 50 ms timeout** 명시 | v1 §10.4 prod-safety |
| 활성화 threshold | 단일 0.6 | **Setup 별 threshold** (A=0.6, C=0.75) | v1 §10.5 |
| ClickHouse V-number | "V5 혹은 V6" | **V5** (Phase 4 = V3; V4 unclaimed after v1 review) | v1 §10.6 |
| Stage 4 deprecation gate | "underperform" 미정의 | **Sharpe < 70% AND MDD > 130% rolling 3-mo** | v1 §10.7 |
| 비활성화 경로 retry 리마인더 | 6개월 후 재시도만 언급 | **자동 cron 리마인더** + `disabled.md` 체크리스트 | v1 §10.8 |

---

## 1. 목표

Phase 5에서 규칙 기반 시스템이 안정되면, 기존 `rl_mppo` 모델을 버리지 않고 **진입 적합성 보조 필터**로 재활용한다.

**중요 원칙 (v1에서 유지):**
- `rl_mppo` 메인 의사결정자 구조는 단계적 폐지
- 전환 시점: **규칙 시스템 3개월 이상 EV+** 검증 이후
- 최초 3개월은 **shadow-log only**
- A/B로 EV 개선 증명 후 활성화

---

## 2. 전제 조건 (활성화 게이트) — **v2 강화**

모두 만족해야 본 작업 착수:

- [ ] Phase 5 Gate 3 통과 (1계약 실전 2주)
- [ ] 누적 3개월 규칙 시스템 EV+ 유지
- [ ] 규칙 시스템 Sharpe ≥ 1.5
- [ ] 평균 슬리피지 ≤ 0.4 tick
- [ ] `rl_mppo` 현재 운용 버전 snapshot 기록
- [ ] **`signals_all`에 Setup별 trades ≥ 50 누적** (v2 추가 — v1 §10.1)
  - Setup A ≥ 50: 학습 진행 가능
  - Setup A ≥ 50 + Setup C < 50: **Setup A 전용 aux** 로 시작, Setup C는 pass-through
  - Setup A < 50: 전체 대기

미달 시: 해당 Setup은 대기 상태. v1처럼 spec 자체가 대기되지 않고 **Setup별 독립 활성화**.

---

## 3. 새 역할 정의 (v1 §3 유지, §3.3 state 강화)

### 3.1 기존 RL 아키텍처 — 변경 없음

5개 액션 직접 결정 (v1 §3.1).

### 3.2 새 역할 — 변경 없음

Setup 시그널 + risk_filter 통과 → RL aux → {PASS, SKIP} (v1 §3.2).

### 3.3 State / Action / Reward — **feature producer 주석 추가**

```python
state = {
    # 시그널 정보 — Signal dataclass에서 직접 읽음
    "setup_type_onehot": [A, C],               # producer: Signal.setup_type
    "signal_confidence": float,                # producer: Signal.confidence
    "signal_direction": {+1, -1},              # producer: Signal.direction
    "entry_vs_vwap": float,                    # producer: MarketContext.vwap + Signal.entry_price (Phase 4 runtime ctx)
    "stop_distance_atr": float,                # producer: Signal.stop_loss + MarketContext.atr_14

    # 시장 상태 — MarketContext에서 직접 읽음 (Phase 3 있음)
    "current_vol_pct": float,                  # producer: computed from last_15min_high - last_15min_low vs price
    "atr_ratio_to_90p": float,                 # producer: MarketContext.atr_14 / atr_90th_percentile
    "time_of_day_normalized": float,           # producer: MarketContext.minutes_since_open() / 390 (6.5h session)
    "minutes_since_macro_event": float | None, # producer: MarketContext.find_recent_event(720).elapsed

    # 포트폴리오 상태 — NEW producer: RollingRiskMetrics
    "recent_5d_winrate": float,                # producer: RollingRiskMetrics (v2 Task 4.3 신규)
    "current_daily_pnl_pct": float,            # producer: RiskStateSnapshot.daily_pnl_krw / account_equity
    "consecutive_losses": int,                 # producer: RiskStateSnapshot.consecutive_losses
}

action = {0: PASS, 1: SKIP}
reward = realized_ticks_after_fees
```

**v2 §4.3 RollingRiskMetrics:** 실시간으로 5-day rolling win rate 계산하는 경량 서비스. ClickHouse `kospi.order_fills` 에서 매 1분 refresh하여 Redis `risk:rolling:recent_5d_winrate` 캐시.

### 3.4 학습 데이터 — **v2 단순화 (v1 §10.2)**

v1은 "Skip된 시그널 → counterfactual PnL (백테스트로 추정)"이라 복잡했다. **v2는 Phase 3 `signals_all`이 이미 모든 시그널을 기록하는 사실을 활용:**

```sql
-- RL aux dataset 생성 쿼리 (offline training)
SELECT
  s.signal_id,
  s.setup_type,
  s.direction,
  s.entry_price,
  s.stop_loss,
  s.take_profit,
  s.confidence,
  s.reason_tags,
  s.executed,
  s.skip_reason,
  o.filled_price,
  o.slippage_ticks,
  -- counterfactual PnL: harness replay of same MarketContext with force-execute=true
  -- saved to results/counterfactual/{signal_id}.json during training data prep
  cf.simulated_ticks,
  cf.simulated_exit_reason
FROM kospi.signals_all s
LEFT JOIN kospi.order_fills o ON s.signal_id = o.signal_id
LEFT JOIN counterfactual_table cf ON s.signal_id = cf.signal_id
WHERE s.generated_at >= now() - INTERVAL 6 MONTH
```

- Executed signals: `realized PnL = filled tick math` (Phase 4 slippage 포함)
- Skipped signals: `counterfactual PnL = harness replay` of the same MarketContext with `force_execute=True`. Harness is deterministic given clean data + macro history (Phase 3 yfinance provider).

**단순화:** counterfactual은 **offline training pipeline에서 재계산** — live path에 counterfactual 로직 불필요.

---

## 4. 구현 단계 — **v2 단계 4.3 Feature Producer Registry 추가**

### 4.1 Stage 1 — Shadow Log Only (≥ 3개월, v1 유지)

v1 §4.1 그대로. `rl_aux_prediction` 컬럼에 로깅.

### 4.2 Stage 2 — A/B 비교 (v1 유지, v2에서 threshold 명시)

A/B 결과 **Setup 별 EV +0.2 tick 이상 개선** 시 Stage 3. Setup A와 Setup C 독립 판정.

### 4.3 Feature Producer Registry (**NEW v2**)

Stage 1 착수 전 다음 3개 producer가 먼저 구현되어야 한다:

**(a) `shared/ml/auxiliary_filter/producers/signal_features.py`**
Signal + MarketContext에서 즉시 계산 가능한 8개 feature (§3.3 첫 2 그룹). Phase 3 데이터로 완결.

**(b) `shared/ml/auxiliary_filter/producers/risk_features.py`**
`RiskStateSnapshot`에서 직접 2개 (`current_daily_pnl_pct`, `consecutive_losses`). Phase 3 데이터로 완결.

**(c) `services/rolling_risk/main.py`** — **신규 데몬**
`recent_5d_winrate`를 매 1분 업데이트. Redis `risk:rolling:*` HASH에 캐시. Signal 평가 시 `risk_features.py`가 읽기.

#### 4.3.1 `rolling_risk` 데몬 ServiceConfigBase

```yaml
# config/rolling_risk.yaml
rolling_risk:
  refresh_interval_seconds: 60
  lookback_days: 5
  redis_key_prefix: "risk:rolling"
  ttl_seconds: 3600
```

### 4.4 Stage 3 — 조건부 활성화 (**v2 per-setup threshold**)

```yaml
# config/rl_auxiliary.yaml
rl_auxiliary:
  enabled: true
  per_setup_threshold:
    A_gap_reversion: 0.60
    C_event_reaction: 0.75    # 샘플 적어 보수적 (v1 §10.5)

  # Inference safety (v2, v1 §10.4)
  inference:
    timeout_ms: 50
    on_failure: "error_pass"   # "error_pass" | "error_skip"
    model_path: "models/futures/rl_aux/current.pkl"

  # Recovery mode
  disabled_marker: "config/rl_aux_disabled.flag"
```

**Fallback rule (v2 §10.4):**

```python
def should_pass(signal, state, ctx) -> bool:
    try:
        features = build_features(signal, state, ctx)
        proba = await asyncio.wait_for(
            predictor.predict_proba(features),
            timeout=cfg.inference.timeout_ms / 1000,
        )
        threshold = cfg.per_setup_threshold[signal.setup_type]
        decision = "PASS" if proba >= threshold else "SKIP"
    except (TimeoutError, Exception) as exc:
        logger.exception("RL aux inference failed; fallback=%s", cfg.inference.on_failure)
        decision = "PASS" if cfg.inference.on_failure == "error_pass" else "SKIP"
        metrics.record_rl_aux_inference_error(type(exc).__name__)
    # record prediction regardless of decision
    await log_prediction(signal, proba if 'proba' in dir() else None, decision)
    return decision == "PASS"
```

**기본은 `error_pass`** — broken aux가 규칙 시스템을 블록킹하지 않도록.

### 4.5 Stage 4 — 메인 `rl_mppo` 운용 폐지 (**v2 concrete gate**)

v1 §4.4의 모호한 "underperform"을 **측정 가능한 조건**으로:

```
3-month rolling window에서 다음 두 조건 모두 만족 시 `rl_mppo` 메인 운용 중단:
  (a) rl_mppo Sharpe / (Setup A+C Sharpe) < 0.70
  (b) rl_mppo MDD / (Setup A+C MDD) > 1.30

단일 조건만 만족 시 추가 1개월 관찰 연장.
```

측정 스크립트: `scripts/analysis/rl_vs_rules_comparison.py` (weekly Edge Review에 섹션 추가).

---

## 5. 기존 학습 파이프라인 재활용 — **v1 유지 + 파일 경로 업데이트**

```
shared/ml/auxiliary_filter/
├── __init__.py
├── producers/                   # NEW v2
│   ├── __init__.py
│   ├── signal_features.py
│   └── risk_features.py
├── dataset.py                   # signals_all + order_fills JOIN
├── counterfactual.py            # NEW v2 — offline harness replay for skipped signals
├── features.py                  # build 20-dim state from producers
├── model.py                     # PyTorch MLP or LightGBM wrapper
├── trainer.py                   # 오프라인 학습
└── predictor.py                 # 실시간 추론 (risk_filter에서 호출, Stage 1-3)

services/
├── rolling_risk/main.py         # NEW v2 — recent_5d_winrate producer daemon
└── rl_aux_trainer/main.py       # NEW v2 — offline retraining cron wrapper
```

---

## 6. 모니터링 — **v2 V-number fix (V5)**

### 6.1 ClickHouse 컬럼 추가 — **V5 migration (v1 §10.6)**

```sql
-- V5__add_rl_aux_to_signals_all.sql
ALTER TABLE kospi.signals_all
  ADD COLUMN rl_aux_prediction Nullable(Float32),
  ADD COLUMN rl_aux_decision LowCardinality(String) DEFAULT '';
```

**V-number 배정:**
- V1: Phase 1 (`news_raw`, `macro_overnight`, `signals_all`, ...)
- V2: Phase 2 (`news_scored`)
- V3: Phase 4 (`order_fills`)
- V4: (unclaimed — 예비)
- **V5: RL aux (이번 spec)**

### 6.2 Prometheus (v1 유지 + v2 inference 메트릭 추가)

```
rl_aux_prediction_histogram                        Histogram
rl_aux_agreement_rate                              Gauge
rl_aux_skipped_pnl                                 Gauge
rl_aux_inference_latency_ms{setup}                 Histogram   # v2
rl_aux_inference_error_total{exception_type}       Counter     # v2
rl_aux_fallback_pass_total{reason}                 Counter     # v2
```

### 6.3 operational dashboard — v1 유지

---

## 7. RL 재학습 금지 목록 — v1 §7 유지

v1 §7의 5개 금지 사항 그대로. 본 v2의 aux filter는 새로운 작은 MLP/GBM이며 기존 MPPO 재학습이 아님.

---

## 8. 완료 게이트 — **v2 대기 경로 구체화 (v1 §10.8)**

### 활성화 경로
- Stage 3 1개월 운영 + A/B에서 Setup 별 +0.2 tick EV 개선 유지

### 비활성화 경로 (**v2 cron 리마인더**)
- Stage 2에서 개선 없음 결론
- `docs/runbooks/rl-aux-disabled.md` 체크리스트 + 사유 기록
- **신규:** `scripts/cron/rl_aux_retry_reminder.sh` 6개월 주기 cron — Telegram으로 재시도 검토 알림
  ```
  0 6 1 */6 * scripts/cron/rl_aux_retry_reminder.sh
  ```

### Setup C 별도 경로 (**v2 신규 — v1 §10.1**)
- Setup A 활성화 + Setup C trade 수 < 50 → Setup C는 무조건 pass-through
- Setup C trade 수 ≥ 50 도달 시점에 Setup C 전용 aux 학습 검토 (별도 사이클)

---

## 9. 명시적 비범위 — v1 유지

- 기존 `rl_mppo` MPPO 재학습
- 주식 RL 확장
- 계층적 RL 보조 필터
- 메인 trader 역할 부활

---

## 10. 개방 이슈 / Follow-ups

### 10.1 Counterfactual 정확도

Offline harness replay는 yfinance 매크로 + clean CH 데이터로 결정적(deterministic)이지만, **실제 체결 시의 호가창 상태를 복원할 수 없다** (Phase 4 `order_fills`는 requested vs filled만 저장). Counterfactual PnL은 **stop/target 중 하나가 hit된다는 가정**만 쓴다. Execute 시의 실제 슬리피지와 차이 있을 수 있음.

**완화:** Training set을 executed signals 위주로 구성, skipped counterfactual은 weight를 낮게(0.3x) 주는 쪽 권장.

### 10.2 Setup C data-wait 지속 기간

Setup C는 현재 ~0.9 trades/month. trade 수 ≥ 50 도달까지 **~55개월 (4.5년)** 필요. 현실적으로는:
- Setup C 사양 확장 (window_minutes, 다른 이벤트 추가) — Phase 5 이후 별도 spec
- 아예 Setup C aux는 장기 대기 (v1 §10.1 보수적 경로)

본 v2는 **"Setup A aux 우선 + Setup C는 data 축적 대기"** 로 결정.

### 10.3 Model drift

MLP 학습 후 drift 모니터링 (prediction 분포, feature 분포). Weekly Edge Review에 섹션 추가.

---

**v2 요약:** v1 구조 유지하면서 Phase 3 실측 기반의 현실적인 data-volume 대응 + counterfactual 단순화 + production-grade inference fallback + per-setup threshold + concrete deprecation gate 추가. Stage 1 착수 조건은 여전히 Phase 5 Gate 3 통과 + 3개월 EV+이며, 최소 예상 착수 시점은 **2026-09 (Phase 5 Gate 3 완료 ~Week 9) + 3개월 = 2026-12**.
