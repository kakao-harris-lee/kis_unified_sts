# LLM-primary 의사결정 + RL 축소 통합 계획

**Status**: v2 — 운영자 §7 결정 반영 완료, Phase 0 착수 가능
**Created**: 2026-05-03
**Updated**: 2026-05-03 (운영자 결정 반영, v1 → v2)
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

운영자 §7-1 결정: **권한 범위 모두 부여** — threshold + veto + size scaling을 모두 LLM이 행사 가능. 단, 안전상 Phase 1 안에서 1.1 → 1.2 → 1.3 순서로 점진 도입.

| 단계 | LLM 출력 | 의사결정 영향 | 운영자 권한 |
|------|---------|--------------|-----------|
| 현재 (주식) | universe quality score (배치) | fusion_ranker 0.35 가중 | 기존 |
| 현재 (선물) | premarket/intraday/close briefing | 사람만 봄, 시스템 직접 사용 X | 기존 |
| **Phase 1.1** | `MarketContext.regime/risk_score/risk_mode` 1h 갱신 | Setup A/C **threshold 동적 조정** | ✅ |
| **Phase 1.2** | LLM-기반 setup confidence override | `risk_filter`의 `block` 결정에 LLM **veto 권한** | ✅ |
| **Phase 1.3** | LLM-기반 size scaler | `llm_adaptive_sizer` 선물 적용 | ✅ |

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

### Phase 1 — LLM 컨텍스트 → Setup A/C 직접 주입 (3–4주, 1.1 → 1.2 → 1.3 순서)

**목표**: LLM `MarketContext`를 Setup A/C 규칙의 threshold/필터/사이즈에 연결.
운영자 §7-1: 권한 모두 부여. 안전상 점진 도입.
운영자 §7-2: 갱신 주기 **1h**. on-demand 추가 갱신은 Setup signal 발생 시에만.

#### Phase 1.1 — Threshold tuning (1주)
- [ ] `services/trading/llm_context_provider.py` — `asset_class="futures"` 분기 추가
- [ ] `services/decision_engine/main.py`에 `LLMContextProvider("futures")` 주입
- [ ] LLM 컨텍스트 갱신 주기 **1h** + Setup signal trigger 시 on-demand
- [ ] Setup A (gap reversion):
  - `risk_mode == RISK_OFF` + `risk_score > 75` → entry confidence threshold ×1.3
  - `regime IN [BEAR_STRONG, BEAR_MODERATE]` → long-bias 차단, short-only
- [ ] Setup C (volatility breakout):
  - `regime == BULL_STRONG` + `risk_mode == RISK_ON` → ATR breakout multiplier ↓ (관대)
- [ ] `config/strategies/futures/setup_a.yaml`, `setup_c.yaml` 신규
- [ ] 단위 테스트: LLM 부재 fallback, regime별 threshold 조정, `confidence < 0.3` skip

#### Phase 1.2 — Veto 권한 (1주)
- [ ] `services/risk_filter/main.py` — LLM veto 입력 추가
  - `MarketContext.confidence ≥ 0.6` AND (`overall_signal == STRONG_BEARISH` for long entry / `STRONG_BULLISH` for short entry) → setup signal `block` with `skip_reason=llm_veto`
  - veto는 entry만, exit/stop은 LLM이 막을 수 없음 (안전)
- [ ] `signals_all`에 `executed=0 + skip_reason=llm_veto`로 기록 (counterfactual 측정용)
- [ ] 단위 테스트: veto 발화 조건, exit는 veto 대상 아님

#### Phase 1.3 — Size scaling (1주)
- [ ] `shared/strategy/position/llm_adaptive_sizer.py`를 선물 신호 경로에 연결
  - `risk_score ≤ 30` → quantity ×1.0 (만점)
  - `30 < risk_score ≤ 60` → quantity ×0.7
  - `60 < risk_score ≤ 80` → quantity ×0.4
  - `risk_score > 80` → quantity ×0 (entry skip, exit/stop은 정상)
- [ ] Phase 5 ladder caps(`futures_live.max_position_size_contracts`)는 항상 우선 — LLM size는 그 안에서만
- [ ] 단위 테스트: ladder cap이 LLM scale을 압도하는 케이스, scale 0일 때 entry skip

#### Phase 1 종합 paper validation (1주)
- [ ] paper 1주 후 측정 지표:
  - Setup A/C signal/day vs LLM regime 정합성
  - LLM-veto signals의 counterfactual PnL (실행분과 비교)
  - Size scaling이 적용된 trades 평균 손실 vs 미적용 케이스 (synthetic)

**Exit**: paper에서 Setup A 일 평균 ≥ 1 trade, Setup C 주 평균 ≥ 1 trade. LLM-veto된 신호의 counterfactual PnL이 실행분보다 통계적으로 나쁘지 않음. Size scaling이 평균 trade PnL을 악화시키지 않음.

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

### Phase 3 — Phase 5 Gate 2/3 (운영자 영역, 빠른 진입 정책)

**목표**: 운영자 게이트 통과 후 실거래 1계약 진입.
운영자 §7-5 결정: **빠르게 진입** — Phase 2(RL shadow 강등)와 **병행** 진행. Phase 1.1 완료 + paper 1주 안정성 확인 후 즉시 Gate 2 운영자 영역 시작.

| 트랙 | 시작 시점 | 종료 조건 |
|------|---------|---------|
| Track A — 운영자 게이트 | Phase 1.1 완료 + paper 1주 | Gate 3 14일 통과 |
| Track B — 엔지니어링 (Phase 1.2/1.3, Phase 2) | 동일 시점, 병렬 | Phase 2 exit |

#### Track A 작업 (운영자 + 엔지니어링 보조)
- [ ] **즉시 시작**: `futures-legal-review.md` §1–6 운영자 작성 (KIS counsel/세무사) — PR #158이 정비한 항목 그대로 채움
- [ ] KIS Real-account API smoke test (production TR ID, balance, WebSocket on real)
- [ ] 증거금 입금 (≈ 2M KRW)
- [ ] position-recovery 드릴 (Redis 키 인위 삭제 → sentinel/Telegram 발생 검증)
- [ ] systemd 4개 unit production install (`kis-decision-engine`, `kis-risk-filter`, `kis-order-router`, `kis-kill-switch`)
- [ ] `config/futures_live.yaml::enabled: true` 플립 (운영자 명시 액션, 위 모두 완료 후)
- [ ] Gate 3: 1계약 × 14일 (`docs/runbooks/phase5-verification.md` §Gate 3)

**Exit**: 14일 Gate 3 조건 충족 + 운영자 서면 승인.

**병행 안전장치**: Track B의 Phase 1.2/1.3이 Track A의 Gate 3 윈도우 중 발생할 수 있음 — Gate 3 14일 측정 윈도우 동안 LLM 권한 확장(veto/size)을 새로 활성화하지 않음. Phase 1.2/1.3은 paper에서만 검증 후 Gate 4로 도입.

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

## 7. 운영자 결정 (2026-05-03 확정)

| # | 항목 | 결정 | 본 계획 반영 |
|---|------|------|------------|
| 1 | LLM 의사결정 권한 범위 | **모두** (threshold + veto + size) | §2.3, Phase 1.1 → 1.2 → 1.3 점진 도입 |
| 2 | LLM 컨텍스트 갱신 주기 | **1h** (+ Setup signal trigger 시 on-demand) | Phase 1.1 작업 항목 |
| 3 | RL shadow 보존 기간 | **6개월** | §5 위험 완화 + Phase 2 |
| 4 | Phase 4 RL aux 활성화 조건 | **v2 계획 그대로** (EV+ 3개월, Setup별 trade ≥ 50) | Phase 4 |
| 5 | Gate 2/3 진입 시점 | **빠르게 진입** — Phase 2와 병행 | Phase 3 Track A/B 분리 |

---

## 8. 작업 분해 (Phase 1 상세)

Phase 1만 사전 분해. Phase 2/3은 Phase 1 결과 보고 다시 분해.

### Phase 1.1 — Threshold tuning (1주)
- **1.1-a** (1일): `services/trading/llm_context_provider.py` — `asset_class="futures"` 분기 + 선물 prompt template (`config/llm.yaml`)
- **1.1-b** (2일): `LLMContextPublisher` 1h 갱신 주기 + Setup signal on-demand trigger
- **1.1-c** (2일): `services/decision_engine/main.py` — `LLMContextProvider("futures")` 주입 + Setup A 분기에 regime/risk_score 기반 threshold scaling
- **1.1-d** (1일): Setup C 분기 (동일 구조)
- **1.1-e** (1일): `config/strategies/futures/setup_a.yaml`, `setup_c.yaml` 신규 + 단위 테스트 (LLM 부재 fallback, regime별 조정, `confidence < 0.3` skip)

### Phase 1.2 — Veto 권한 (1주)
- **1.2-a** (2일): `services/risk_filter/main.py` — LLM veto 입력 + entry-only 가드 (exit/stop은 veto 대상 아님)
- **1.2-b** (1일): `signals_all.executed=0 + skip_reason=llm_veto` 기록 + 테이블 마이그레이션 (필요 시)
- **1.2-c** (1일): Telegram alert (veto 발화 시 — 운영자 가시성)
- **1.2-d** (1일): 단위/통합 테스트

### Phase 1.3 — Size scaling (1주)
- **1.3-a** (2일): `shared/strategy/position/llm_adaptive_sizer.py` 선물 신호 경로 연결
- **1.3-b** (1일): Phase 5 ladder cap 우선순위 보장 (`futures_live.max_position_size_contracts`가 항상 hard cap)
- **1.3-c** (1일): 단위 테스트 (ladder cap 우선, scale 0 → entry skip)

### Phase 1 종합 (1주)
- **paper validation**: 1주 paper 가동 후 측정 지표 수집
- **graceful degradation 검증**: LLM API 인위 중단 → safe defaults 동작
- **Grafana panel 추가**: "LLM regime distribution" + "Setup signals by regime" + "Veto rate" + "Size scale factor"
- **Telegram alert**: LLM context staleness > 30min, veto 발화

**Phase 1 총 ~4주** (1.1-1.3 병렬 가능 영역 있어 단축 여지 있음).

### Phase 3 Track A 동시 시작 작업 (운영자 + 엔지니어링 보조)
Phase 1.1 완료 + paper 1주 안정성 확인 즉시 (운영자 §7-5 결정):
- 운영자: `futures-legal-review.md` §1–6 작성 (KIS counsel/세무사)
- 엔지니어링: KIS Real-account smoke test 스크립트 + position-recovery drill 스크립트 정비
- 운영자: 증거금 입금 + commission rate 갱신
- 엔지니어링: systemd 4개 unit 배포 패키지 (production install 안내 문서)
- 운영자: `config/futures_live.yaml::enabled: true` 플립 + Gate 3 14일 모니터링

---

## 9. 추적

| 일자 | 변경 |
|------|------|
| 2026-05-03 | v1 초안 작성 |
| 2026-05-03 | **v2** — 운영자 §7 결정 5건 반영. Phase 1을 1.1/1.2/1.3 분해, Phase 3을 Phase 2와 병행 Track A/B 분리 |
| TBD | Phase 0 시작 (PR #159 머지 후) |
| TBD | Phase 1.1 시작 + Phase 3 Track A 동시 출발 |
