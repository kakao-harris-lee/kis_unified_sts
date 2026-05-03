# LLM-primary 의사결정 + RL 축소 통합 계획

**Status**: Draft v1 — 운영자 검토 필요
**Created**: 2026-05-03
**Author**: 엔지니어링 (운영자 결정 반영)
**Parent**: `docs/plans/2026-04-20-futures-paradigm-master.md`
**Related**:
- `docs/plans/2026-04-20-futures-paradigm-rl-repurposing-v2.md` (선행 계획 — RL→aux 필터)
- `docs/plans/2026-04-20-futures-paradigm-phase5-rollout.md` (Phase 5 paradigm 활성화 게이트)
- `docs/runbooks/futures-legal-review.md` (Gate 2 운영자 체크리스트)

**Target branch**: `feat/llm-primary-rl-minimization` (작업 시점 분기)

---

## 1. 결정 배경

### 1.1 현재 상태 (2026-05-03 기준)

| 영역 | 상태 |
|------|------|
| 선물 메인 운용 | `rl_mppo` 단독 (`config/strategies/futures/rl_mppo.yaml::enabled: true`) — 13개 RL 프로파일 중 1개만 활성 |
| 선물 RL 거래 실적 | **2026-04-15 마지막** 이후 18일간 0건 (tz 버그, PR #159에서 수정 중) |
| Apr 1–15 RL 220+건 | **모두 ~-1 tick 손실**. 모델이 1분 안에 즉시 청산 → 슬리피지/수수료가 가격 변동 초과 |
| Phase 5 paradigm Setup A/C | 코드는 작성 완료(`services/decision_engine/`, `risk_filter/`, `order_router/`), 가동은 Gate 2 미통과로 paper-only |
| LLM 인프라 | `shared/llm/` 14개 모듈 + `MarketContext` + `LLMContextProvider` + `fusion_ranker` (주식) + premarket/intraday/close briefing — 충실히 구비됨 |
| LLM 의사결정 직접 관여 | 주식 universe 가중(0.35) + 일부 entry 전략 컨텍스트 + position sizer 일부 |
| RL→aux 계획 (v2) | 작성됨, 활성화 전제: Phase 5 Gate 3 통과 + 3개월 EV+ + Setup별 trade ≥ 50 |

### 1.2 운영자 결정 (2026-05-03)

> **선물 RL 모델 활용은 축소하고 LLM을 메인으로 활용**

**해석 (이 계획서가 채택하는 정의)**:
- "RL 메인 → LLM 메인": **메인 의사결정 레이어를 RL에서 LLM-스코어 가중 규칙(rule + LLM-augmented)으로 전환**
- "RL 축소": RL은 **선택적 aux 필터로만 잔존**(v2 계획), 또는 **shadow-only**로 강등
- 현 상태(RL 단독 100%)에서 → 최종 상태(LLM-augmented rules 메인 + RL 보조)로 단계적 이동

### 1.3 결정 근거

1. **RL 실증 부진**: Apr 1–15 220+ trades 모두 마이크로 손실 — 모델이 가격 변동을 충분히 capture 하지 못하고 비용에 잡힘
2. **LLM 인프라 성숙**: 14개 모듈 + briefing 3종 + scoring/regime/sentiment 등 의사결정 보조 가능 출력이 이미 갖춰짐
3. **RL 학습 데이터 한계**: 선물 연결선물(101S6000) ~98K bars로 학습, mini 도메인 mismatch 흔적 — 추가 학습보다 RL 의존을 낮추는 것이 운영 안정성에 유리
4. **Phase 5 paradigm 정합**: Setup A(gap reversion)/Setup C(volatility breakout)는 **규칙 기반 + 시장컨텍스트 의존**이라 LLM 보강과 자연스럽게 결합

---

## 2. 목표 상태

### 2.1 선물 메인 의사결정 레이어 (목표)

```
규칙 기반 Setup A/C
  + LLMContextProvider 컨텍스트 (regime/risk_mode/risk_score/sector_rotation)
  + LLM-augmented threshold tuning (예: BEAR + risk_score > 70 → Setup C threshold ↑)
  → primary entry signal
  → risk_filter (기존 Phase 5 코드 그대로)
  → [optional] RL aux PASS/SKIP filter (v2 계획대로 shadow → 활성)
  → order_router
```

### 2.2 RL 위치 변동

| 시점 | 역할 | 활성화 |
|------|------|--------|
| 현재 | 선물 메인 의사결정자 (5-action) | `enabled: true` |
| **Phase A (4–6주)** | shadow-only — 거래 미참여, 신호만 로깅 비교 | `enabled: false`, paper logging만 |
| **Phase B (3개월 후)** | 보조 필터 (v2 계획 §3.2) — Setup signal에 PASS/SKIP | enable trigger: v2 §2 게이트 |
| **장기 (6개월+)** | (조건부) 폐지 또는 재학습 | 운영자 결정 |

### 2.3 LLM 의사결정 관여 확장

| 단계 | LLM 출력 | 의사결정 영향 |
|------|---------|--------------|
| 현재 (주식) | universe quality score (배치) | fusion_ranker 0.35 가중 |
| 현재 (선물) | premarket/intraday/close briefing | 사람만 봄, 시스템 직접 사용 X |
| **Phase 1 (목표)** | `MarketContext.regime/risk_score/risk_mode` 정기 갱신 | Setup A/C **threshold 동적 조정** + RL action mask 보조 |
| **Phase 2** | LLM-기반 setup confidence override | risk_filter `block` 결정에 LLM veto 권한 |
| **Phase 3** | LLM-기반 size scaler | `llm_adaptive_sizer` 선물 적용 |

---

## 3. 진행 중 작업과의 정합

### 3.1 머지 대기 PR

| PR | 내용 | 이 계획과 관계 |
|----|------|-------------|
| **#158** `chore/phase5-gate2-prep` | Gate-2 사전 정비 (EOD 표기, night session, rl_trades TTL, TR ID 외부화) | **블록 안함** — Gate 2 운영자 체크리스트 사전 정비. LLM 전환과 독립 |
| **#159** `fix/paper-tz-aware-hot-path` | tz-naive→aware 핫패스 수정 + retry exc_info | **선행 필수** — 이 fix가 머지되어야 paper validation 데이터(LLM/RL 비교용)가 의미 있음 |

→ 두 PR 모두 **머지 진행**. 본 계획은 **PR #159 머지 + 1주 paper validation 후** 착수.

### 3.2 기존 v2 계획과의 합치

`2026-04-20-futures-paradigm-rl-repurposing-v2.md`이 이미 "RL → 보조 필터" 방향을 정의해 둠. 본 계획은 v2를 **선택적으로 강등**한 것:

| v2 가정 | 본 계획 변경 |
|--------|-------------|
| 메인 = Setup A/C 규칙 시스템(Gate 3 통과 후) | **메인 = LLM-augmented Setup A/C** (LLM 컨텍스트가 threshold/사이즈에 직접 영향) |
| RL = aux 필터 (Setup signal에 PASS/SKIP) | 동일 (v2 §3.2 그대로) |
| 활성화 조건: Setup별 trade ≥ 50 | 동일 |
| 활성화 시점: 3개월 EV+ | **2개월로 단축 가능** (LLM 컨텍스트 조기 도입으로 Setup 품질 향상 시) |

→ v2를 **정신적으로는 계승, 활성화 조건은 LLM 보강을 변수로 추가**.

---

## 4. 단계별 마이그레이션

### Phase 0 — 사전 정비 (1–2주, **PR #158 + #159 머지 후 즉시**)

**목표**: 안전한 paper validation 가능 상태 회복

- [ ] PR #159 머지 → 다음 평일 paper 가동
- [ ] 1주 paper 데이터로 검증:
  - `kospi.rl_trades`에 정상 거래 다시 발생
  - `pipeline.with_retry` 경고 0
  - `signals_all` (Phase 5 paradigm 코드)에 setup signal 발생 여부 (paper-only)
- [ ] PR #158 머지 (Gate 2 사전 정비) → 운영자 legal-review.md 검토 가능 상태
- [ ] **결정 분기**: paper RL 1주 결과가 여전히 -1 tick loss 패턴 반복이면 → Phase 1을 앞당김

**Exit**: paper validation 데이터 클린 + 운영자가 Phase 1 착수 승인.

### Phase 1 — LLM 컨텍스트 → Setup A/C 직접 주입 (2–3주)

**목표**: LLM `MarketContext`를 Setup A/C 규칙의 threshold/필터에 연결

- [ ] `services/decision_engine/main.py`에 `LLMContextProvider("futures")` 주입 (현재 stock만 사용)
- [ ] Setup A (gap reversion):
  - `risk_mode == RISK_OFF` + `risk_score > 75` → entry confidence threshold ×1.3
  - `regime IN [BEAR_STRONG, BEAR_MODERATE]` → long-bias 차단, short-only
- [ ] Setup C (volatility breakout):
  - `regime == BULL_STRONG` + `risk_mode == RISK_ON` → ATR breakout multiplier ↓ (관대)
  - `confidence < 0.4` (LLM 자체 신뢰도) → setup C signal pass-through 무시
- [ ] `config/strategies/futures/setup_a.yaml`, `setup_c.yaml` 신규 (Setup별 LLM-aware threshold 값)
- [ ] 신규 단위 테스트:
  - LLM 컨텍스트 부재 시 fallback (graceful degradation)
  - regime별 threshold 조정 작동
  - `MarketContext.confidence < 0.3`이면 LLM override skip

**측정 지표**:
- Setup A/C signal/day vs LLM 컨텍스트 정합성
- LLM-veto된 signal의 counterfactual PnL (`signals_all.executed=0` + `skip_reason=llm_veto`)

**Exit**: paper에서 Setup A 일 평균 ≥ 1 trade, Setup C 주 평균 ≥ 1 trade. LLM-veto된 신호의 counterfactual PnL이 실행분보다 통계적으로 나쁘지 않음.

### Phase 2 — RL 메인 → shadow 강등 (1주)

**목표**: RL을 의사결정 경로에서 제거, 비교용 로그로만 보존

- [ ] `config/strategies/futures/rl_mppo.yaml::enabled: false`
- [ ] 신규 `services/trading/rl_shadow_logger.py`:
  - 모든 tick에서 RL inference 실행
  - 결과를 `kospi.rl_shadow_predictions` (신규 테이블, V6 마이그레이션) 기록
  - 실제 주문은 발생시키지 않음
- [ ] Setup A/C 메인 활성: `services/decision_engine/main.py` paper-mode 가동
- [ ] Grafana 대시보드 추가:
  - "Setup A/C signals/day" vs "RL shadow LONG/SHORT/HOLD distribution"
  - LLM regime → setup conversion rate

**Exit**: Phase 5 Gate 1 게이트(2주 paper extension) Setup A/C 기반으로 누적, RL 매매 0건 확인.

### Phase 3 — Phase 5 Gate 2/3 (운영자 영역, 2–6주)

**목표**: 운영자 게이트 통과 후 실거래 1계약 진입

- [ ] PR #158이 정비한 `futures-legal-review.md` §1–6 운영자 작성 (KIS counsel/세무사)
- [ ] `config/futures_live.yaml::enabled: true` 플립 (운영자 명시 액션)
- [ ] systemd 4개 unit production install
- [ ] Gate 3: 1계약 × 14일 검증 (`docs/runbooks/phase5-verification.md` §Gate 3)

**Exit**: 14일 Gate 3 조건 충족 + 운영자 서면 승인.

### Phase 4 — RL aux 필터 활성화 검토 (Phase 3 후 +3개월)

**목표**: v2 계획(`rl-repurposing-v2`)의 활성화 게이트 도달 여부 확인

- [ ] `signals_all`에 Setup A 누적 trade ≥ 50 확인
- [ ] 3개월 누적 EV+, Sharpe ≥ 1.5 확인
- [ ] Setup별 RL aux PASS rate / 실효 PnL counterfactual 측정 (v2 §10.2)
- [ ] 만족 시 → v2 계획대로 RL aux 필터 활성화 (shadow→paper→live)
- [ ] 미만족 시 → RL 폐지(또는 재학습) 운영자 결정

---

## 5. 위험과 완화책

| 위험 | 영향 | 완화 |
|------|------|------|
| **LLM 호출 latency** (수 초) | tick 단위(1분) 의사결정 부적합 | LLM 컨텍스트는 **15분/1시간 갱신**, tick에서는 **Redis 캐시된 MarketContext** 읽기. 절대 인라인 호출 금지 |
| **LLM 호출 비용** | API 비용 증가 | (a) `prompt_cache_enabled: true` 활용, (b) MarketContext 갱신 주기 1시간 기본, (c) 한 prompt 당 token 한도 |
| **LLM 환각 / 형식 오류** | 잘못된 regime → 잘못된 threshold | `strict_json_schema: true` 검증 + 파싱 실패 시 직전 Redis snapshot 재사용. 30분 이상 갱신 실패 시 fallback (fixed defaults), Telegram 알림 |
| **RL 폐지 후 재학습 불가** | 모델 자산 손실 | Phase 2의 shadow logger 유지 — 인퍼런스 결과는 6개월간 보관, 재학습 시 reference 사용 |
| **LLM 컨텍스트 stale** (예: API 다운) | regime 정보 없이 거래 | `MarketContext.confidence < 0.3` 자동 감지 → 그날 신규 진입 정지(safe-by-default), 보유 포지션은 기존 룰대로 청산 |
| **Setup C 저빈도** (Phase 3 §10.1: ~0.9 trade/mo) | trade 수 부족 → 통계적 검증 어려움 | v2 계획대로 **Setup A 단독 시작**, Setup C는 RL aux 활성화 대기 경로 |
| **운영자 게이트 미통과** | Phase 3 진입 막힘 | Phase 0–2는 게이트와 독립 — paper-only 검증으로 가치 입증 후 운영자에게 결정 자료 제공 |

---

## 6. 측정 지표 (KPI)

각 Phase 종료 시 운영자 보고 항목:

### Phase 1 종료
- Setup A daily signal/day rate (LLM-aware vs LLM-blind 비교)
- LLM threshold-tuning이 적용된 trades 비율
- Counterfactual PnL: LLM-veto vs LLM-pass 신호의 paper 결과

### Phase 2 종료
- RL shadow vs Setup A/C 신호 일치률 (action ↔ direction)
- RL이 "거부"했을 trade가 Setup이 채택한 결과 → 평균 PnL
- 시스템 안정성: pipeline retry 경고/일

### Phase 3 (Gate 3) 종료
- 14일 누적 PnL > 슬리피지+수수료
- 일일 MDD -3% 위반 0
- API error rate < 2%
- 평균 슬리피지 ≤ 0.4 ticks

---

## 7. 결정 필요 사항 (운영자)

이 계획서를 작업으로 진입시키기 전 운영자 답변 필요:

1. **LLM 의사결정 권한 범위**:
   - (a) threshold 조정만 — 안전, 보수적
   - (b) (a) + setup signal veto — 중간
   - (c) (b) + size scaling — 적극
   - 본 계획은 **(a) → (b) → (c) 점진 도입**을 가정. 동의?

2. **Phase 1 LLM 컨텍스트 갱신 주기**:
   - 1시간 (현재 intraday refresh와 동일, 비용 ↓)
   - 15분 (좀 더 반응성, 비용 ↑)
   - 본 계획은 **1시간 기본 + Setup signal 발생 시 on-demand 추가 갱신** 가정. 동의?

3. **RL shadow 보존 기간**:
   - 3개월 / 6개월 / 영구. 본 계획은 **6개월** 가정.

4. **Phase 4 RL aux 활성화 조건**:
   - v2 계획 그대로(EV+ 3개월) / 단축(2개월) / 단축 + LLM-aware 변수 추가
   - 본 계획은 **v2 그대로**.

5. **Phase 5 Gate 2/3 진입 시기 결정권**:
   - Phase 0–2 결과를 보고 운영자가 결정
   - 자동 trigger 없음 — 사람-결정 게이트

---

## 8. 작업 분해 (Phase 1 상세)

Phase 1만 사전 분해 (Phase 2+는 Phase 1 결과 보고 다시 분해):

### 1.1 LLMContextProvider 선물 도입 (3일)
- `services/trading/llm_context_provider.py` — `asset_class="futures"` 분기 추가
- `config/llm.yaml` 선물 전용 prompt template
- 단위 테스트

### 1.2 Setup A LLM-aware threshold (5일)
- `services/decision_engine/main.py` — Setup A 분기에 MarketContext 주입
- `config/strategies/futures/setup_a.yaml` 신규 (LLM-aware threshold 값)
- regime/risk_score 기반 threshold scaling
- 통합 테스트 (LLM mock + Setup signal generation)

### 1.3 Setup C LLM-aware threshold (5일)
- 1.2와 동일 구조, Setup C 분기

### 1.4 graceful degradation + 모니터링 (3일)
- LLM stale → safe defaults
- Grafana panel: "LLM regime distribution" + "Setup signals by regime"
- Telegram alert: LLM context staleness > 30min

### 1.5 paper validation (5일)
- 1주 paper 가동 후 측정 지표 수집
- 운영자 보고

**Phase 1 총 ~3주** (병렬 가능 영역 있어 단축 여지 있음).

---

## 9. 추적

| 일자 | 변경 |
|------|------|
| 2026-05-03 | v1 초안 작성 (이 문서) |
| TBD | 운영자 §7 결정 → v2 |
| TBD | Phase 0 시작 (PR #159 머지 후) |
