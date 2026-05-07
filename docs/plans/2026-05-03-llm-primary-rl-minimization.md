# LLM-primary 의사결정 + RL 축소 통합 계획

**Status**: v3.1 — code review 정정 패치 적용 (§8 1.2-a 타겟 정정, §3.1 PR #158 상태 정정, 명명/citation 일관성 수정)
**Created**: 2026-05-03
**Updated**:
- 2026-05-03 (v1 초안)
- 2026-05-03 (v2 — 운영자 §7 결정 5건 반영, Phase 1을 1.1/1.2/1.3 분해, Phase 3을 Phase 2와 병행)
- 2026-05-07 (v3 — 코드베이스 점검 결과 반영: §2.4 Adapter 통합 결정, §4 Phase 0 사전 정비 작업 추가, Phase 1.0 신설, §1.1 PR #159/#161/#162 머지 + paper validation 결과 반영)
- 2026-05-07 (**v3.1 — code review 피드백 반영**: §8 Phase 1.2-a를 strategy_manager로 정정 (§2.4 Adapter 결정 일관성), §3.1 PR #158 OPEN으로 정정, §1.3 모듈 수 정렬, §5 Setup C 출처 인용 정정, §2.2 Phase A/B → Phase 2/4 명명 정렬)

**Author**: 엔지니어링 (운영자 결정 반영)
**Parent**: `docs/plans/2026-04-20-futures-paradigm-master.md`
**Related**:
- `docs/plans/2026-04-20-futures-paradigm-rl-repurposing-v2.md` (선행 계획 — RL→aux 필터)
- `docs/plans/2026-04-20-futures-paradigm-phase5-rollout.md` (Phase 5 paradigm 활성화 게이트)
- `docs/runbooks/futures-legal-review.md` (Gate 2 운영자 체크리스트)

**Target branch**: `feat/llm-primary-rl-minimization` (작업 시점 분기)

---

## 1. 결정 배경

### 1.1 현재 상태 (2026-05-07 기준, v3)

| 영역 | 상태 |
|------|------|
| 선물 메인 운용 | `rl_mppo` 단독 (`config/strategies/futures/rl_mppo.yaml::enabled: true`) — 13개 RL 프로파일 중 1개만 활성 |
| 선물 RL 거래 실적 (Apr 15 ~ May 6) | **18일간 0건** — tz 버그(silent TypeError) → PR #159(c37214f) 수정 |
| 추가 회귀 발견·해결 | PR #161(4b7cf7f) `_is_trading_time` UTC→KST 변환 누락 / PR #162(2071b00) slippage 경로 `price_source_time` 누락 |
| 5/7 paper validation (3 fix 모두 적용) | 첫 30분에 entry signal 16건, 체결 2건. **둘 다 손실** (PnL -2.75 / -3.35, 평균 -0.265%) — Apr 1-15 패턴 그대로 재현 (1-2분 즉시 청산) |
| Apr 1–15 RL 220+건 + 5/7 추가 2건 | **모두 마이크로 손실**. 모델이 1분 안에 즉시 청산 → 슬리피지/수수료가 가격 변동 초과. 코드 버그가 아닌 모델 행동 문제 재확인 |
| Phase 5 paradigm Setup A/C | 코드 작성 완료(`services/decision_engine/`, `risk_filter/`, `order_router/`)이나 **`context_provider`가 stub** (None 반환) → 신호 0건 발생, paper도 미가동 |
| Kill switch | 6개 KillCondition 중 3개(api_error, news_lag, ch_insert_fail) stub. **`_force_flat_callback`가 no-op** (실제 flatten 미구현) |
| LLM 인프라 | `shared/llm/` 16개 모듈 + `MarketContext` + `LLMContextProvider` + `fusion_ranker` (주식) + premarket/intraday/close briefing + `LLMAdaptiveSizer` 등록 — **충실히 구비됨** |
| LLM 의사결정 직접 관여 | 주식 universe 가중(0.35) + `mean_reversion`의 단일 BEARISH 가드. **strategy_manager.py가 LLMContextProvider를 호출하나 의사결정 영향 없음(로깅만)** |
| 통합 아키텍처 갭 | **orchestrator(현재 RL 운용 경로)와 decision_engine 데몬(Phase 5 Setup A/C 경로)이 완전히 분리** — 둘이 만나는 지점 없음 (§2.4 결정으로 해결) |
| RL→aux 계획 (v2) | 작성됨, 활성화 전제: Phase 5 Gate 3 통과 + 3개월 EV+ + Setup별 trade ≥ 50 |

### 1.2 운영자 결정 (2026-05-03)

> **선물 RL 모델 활용은 축소하고 LLM을 메인으로 활용**

**해석 (이 계획서가 채택하는 정의)**:
- "RL 메인 → LLM 메인": **메인 의사결정 레이어를 RL에서 LLM-스코어 가중 규칙(rule + LLM-augmented)으로 전환**
- "RL 축소": RL은 **선택적 aux 필터로만 잔존**(v2 계획), 또는 **shadow-only**로 강등
- 현 상태(RL 단독 100%)에서 → 최종 상태(LLM-augmented rules 메인 + RL 보조)로 단계적 이동

### 1.3 결정 근거

1. **RL 실증 부진**: Apr 1–15 220+ trades 모두 마이크로 손실 — 모델이 가격 변동을 충분히 capture 하지 못하고 비용에 잡힘
2. **LLM 인프라 성숙**: 16+ 모듈 (`shared/llm/`) + briefing 3종 + scoring/regime/sentiment 등 의사결정 보조 가능 출력이 이미 갖춰짐
3. **RL 학습 데이터 한계**: 선물 연결선물(101S6000) ~98K bars로 학습, mini 도메인 mismatch 흔적 — 추가 학습보다 RL 의존을 낮추는 것이 운영 안정성에 유리
4. **Phase 5 paradigm 정합**: Setup A(gap reversion)/Setup C(volatility breakout)는 **규칙 기반 + 시장컨텍스트 의존**이라 LLM 보강과 자연스럽게 결합

---

## 2. 목표 상태

### 2.1 선물 메인 의사결정 레이어 (목표, v3)

본 계획의 통합 결정(§2.4)에 따라 Setup A/C는 **EntryRegistry adapter**로 등록되어 기존 orchestrator 파이프라인을 통과한다. Phase 5 standalone daemons(`decision_engine`/`risk_filter`/`order_router`)는 Phase 4(RL aux 활성화 검토 시점) 이후 별도 검토 — 본 계획서 범위 밖.

```
WebSocket tick (futures_feed.py, tz-aware UTC)
  → orchestrator._handle_entry()
    → strategy_manager.check_entries(EntryContext + market_context)
       ├─ SetupAEntryAdapter (gap reversion)        ← v3 신규
       │  + LLM threshold tuning (Phase 1.1)
       │  + LLM veto guard      (Phase 1.2)
       │  + LLM size scaling    (Phase 1.3)
       ├─ SetupCEventReactionAdapter (event)         ← v3 신규
       └─ RLMPPOEntry (shadow only, Phase 2~)
    → (entry guards: spread/staleness/price-deviation — 기존)
    → orchestrator._submit_entry_order()
       ├─ paper: VirtualBroker (현재 운용)
       └─ live:  OrderExecutor → KIS Real (Phase 3 Gate 3 후)
```

**핵심 차이 (v2 vs v3)**:
- v2: Setup A/C가 standalone `decision_engine` daemon에서 동작, Redis stream으로 risk_filter/order_router에 전달
- v3: Setup A/C가 EntryRegistry adapter로 orchestrator에 통합. **Phase 5 daemon 4개는 Phase 4까지 deferred** (paper-only 검증 → live 전환 시 재평가)

### 2.2 RL 위치 변동

§4의 Phase 0/1/2/3/4 numbering과 일치하도록 명명. Phase 2가 RL shadow 강등, Phase 4가 RL aux 활성화 검토.

| 시점 | 역할 | 활성화 |
|------|------|--------|
| 현재 | 선물 메인 의사결정자 (5-action) | `enabled: true` |
| **§4 Phase 2 (Phase 1 종료 후, 1주)** | shadow-only — 거래 미참여, 신호만 로깅 비교 | `enabled: true` + `shadow_mode: true`, paper logging만 |
| **§4 Phase 4 (Phase 3 종료 +3개월)** | 보조 필터 (v2 계획 §3.2) — Setup signal에 PASS/SKIP | enable trigger: v2 §2 게이트 (`signals_all` 누적 trade ≥ 50, 3개월 EV+) |
| **장기 (6개월+)** | (조건부) 폐지 또는 재학습 | 운영자 결정 (RL shadow 보존 기간 §7-3 결정 = 6개월) |

### 2.3 LLM 의사결정 관여 확장

운영자 §7-1 결정: **권한 범위 모두 부여** — threshold + veto + size scaling을 모두 LLM이 행사 가능. 단, 안전상 Phase 1 안에서 1.1 → 1.2 → 1.3 순서로 점진 도입.

| 단계 | LLM 출력 | 의사결정 영향 | 운영자 권한 |
|------|---------|--------------|-----------|
| 현재 (주식) | universe quality score (배치) | fusion_ranker 0.35 가중 | 기존 |
| 현재 (선물) | premarket/intraday/close briefing | 사람만 봄, 시스템 직접 사용 X | 기존 |
| **Phase 1.1** | `MarketContext.regime/risk_score/risk_mode` 1h 갱신 | Setup A/C **threshold 동적 조정** | ✅ |
| **Phase 1.2** | LLM-기반 setup confidence override | strategy_manager 단계에서 LLM **veto 권한** | ✅ |
| **Phase 1.3** | LLM-기반 size scaler | `llm_adaptive_sizer` 선물 적용 | ✅ |

### 2.4 통합 아키텍처 결정 (v3 신규)

**결정: Adapter 패턴(Option A)** — Setup A/C 로직을 `EntryRegistry`-호환 어댑터로 래핑하여 기존 orchestrator 파이프라인에 등록한다.

#### 2.4.1 검토한 옵션

| 옵션 | 설명 | 장 | 단 | 채택 |
|------|------|---|---|------|
| **A. Adapter 패턴** | `SetupAEntryAdapter(EntrySignalGenerator)`로 Setup을 EntryRegistry에 등록, 기존 orchestrator/strategy_manager 파이프라인 활용 | • 최소 변경 (3 파일)<br>• paper/live 통합 자연스러움<br>• shadow RL 공존 쉬움<br>• 단일 진입점 = 단일 테스트 경로 | • Phase 5 daemon 분산 아키텍처와 별도 진화 | ✅ |
| B. Stream Consumer | orchestrator가 decision_engine Redis stream 구독 | • Phase 5 spec 그대로 | • risk_filter/order_router 로직 중복<br>• paper 모드 분기 어려움<br>• 테스트 복잡 | ❌ |
| C. Hybrid | paper는 Adapter, live는 daemon | • 양방향 점진 가능 | • 두 코드 경로 유지 비용 | ❌ |

#### 2.4.2 채택 근거

1. **현재 orchestrator는 이미 LLMContextProvider를 호출**(`strategy_manager.py:341-350`) — 의사결정 미사용 상태일 뿐, 컨텍스트는 이미 EntryContext.market_context에 주입되고 있음. Adapter 패턴은 이 자산을 그대로 활용.
2. **기존 entry guards 재사용** — wide_spread / stale_signal / price_deviation 가드가 이미 5/7 paper에서 정상 작동 확인됨 (16건 entry signal → 11+3+1 가드 거부 + 2건 체결). Setup A/C도 동일 가드 통과 필요.
3. **paper-live 단일 경로** — 5/4-5/7 디버깅 과정에서 orchestrator 경로의 신뢰도가 검증됨(3개 fix 후 정상). Phase 5 daemons는 paper 모드에서 한 번도 실신호를 발화한 적 없음(stub context_provider).
4. **RL shadow 공존** — strategy_manager가 enabled=true 전략을 모두 호출하므로, RL은 별도 shadow 모드(§4.5)로 추가하면 자연스럽게 공존.
5. **Phase 5 daemon 코드는 폐기 아님** — Phase 4(+3개월) 시점 RL aux 결정 시점에서 standalone live deployment의 별도 검토 대상으로 유지. systemd 단위는 미설치 그대로.

#### 2.4.3 구체 구현 위치 (Phase 1.0)

| 변경 | 파일 |
|------|------|
| 신규 | `shared/strategy/entry/setup_adapters.py` — `SetupAEntryAdapter`, `SetupCEventReactionAdapter` (모두 `EntrySignalGenerator` 구현) |
| 수정 | `shared/strategy/registry.py::register_builtin_components()` — adapter 2개 등록 |
| 신규 | `config/strategies/futures/setup_a_gap_reversion.yaml` (`enabled: false` 초기) |
| 신규 | `config/strategies/futures/setup_c_event_reaction.yaml` (`enabled: false` 초기) |
| 추후 (Phase 2) | `config/strategies/futures/rl_mppo.yaml::enabled: false` (Setup A/C 활성화와 동시 토글) |

#### 2.4.4 컨텍스트 호환성

`Setup.check(MarketContext)` ↔ `EntrySignalGenerator.should_enter(EntryContext)` 매핑:

```python
# SetupAEntryAdapter.should_enter(context: EntryContext) → Signal | None
# 1. context.market_context (LLM regime/risk_mode/risk_score) 활용
# 2. context.market_data (price/spread/depth) → SetupContext용 변환
# 3. context.indicators (ATR, gap %) → SetupContext용 변환
# 4. setup.check(setup_context) 호출
# 5. 결과 Signal에 timestamp=context.timestamp(=tz-aware UTC) 보장 (PR #159 호환)
```

이 매핑은 `decision_engine/main.py`의 standalone context_provider와 **독립적**. 즉 §1.1에 기록된 "context_provider stub" 문제는 본 계획에서 우회됨 — orchestrator의 `LLMContextProvider`를 그대로 사용.

---

## 3. 진행 중 작업과의 정합

### 3.1 PR 상태 (v3.1 업데이트, 2026-05-07 기준)

| PR | 상태 | 내용 |
|----|------|------|
| **#158** `chore/phase5-gate2-prep` | OPEN | Gate-2 사전 정비 (EOD 표기, night session, rl_trades TTL, TR ID 외부화) — Phase 0.1에서 머지 진행 |
| **#159** `fix/paper-tz-aware-hot-path` | ✅ 5/4 머지 (c37214f) | tz-naive→aware 핫패스 수정 + retry exc_info |
| **#160** `docs/llm-primary-rl-minimization-plan` (이 문서) | OPEN | v3.1 갱신 중 |
| **#161** `fix/rl-mppo-utc-trading-time` | ✅ 5/6 머지 (4b7cf7f) | `_is_trading_time` / `_is_eod` UTC→KST 변환 누락 — PR #159 후 발견된 회귀 |
| **#162** `fix/futures-slippage-price-source-time` | ✅ 5/6 머지 (2071b00) | slippage 경로의 `price_source_time` 누락 — paper broker `missing_price_source_time` 거부 차단 해소 |

5/7 paper validation: 3개 머지 fix(#159/#161/#162)가 모두 작동 확인, 첫 거래 2건 발생(둘 다 손실, §1.1 기록). PR #158은 별도로 Phase 0.1에서 머지 후 운영자 legal-review.md 검토 가능 상태로 진입.

### 3.2 기존 v2 계획과의 합치

`2026-04-20-futures-paradigm-rl-repurposing-v2.md`이 이미 "RL → 보조 필터" 방향을 정의해 둠. 본 계획은 v2를 **선택적으로 강등**한 것:

| v2 가정 | 본 계획 변경 |
|--------|-------------|
| 메인 = Setup A/C 규칙 시스템(Gate 3 통과 후) | **메인 = LLM-augmented Setup A/C** (LLM 컨텍스트가 threshold/사이즈에 직접 영향) |
| Setup A/C 실행 위치 = standalone `decision_engine` daemon | **v3 변경**: orchestrator의 strategy_manager (EntryRegistry adapter, §2.4) |
| RL = aux 필터 (Setup signal에 PASS/SKIP) | 동일 (v2 §3.2 그대로) |
| 활성화 조건: Setup별 trade ≥ 50 | 동일 |
| 활성화 시점: 3개월 EV+ | **2개월로 단축 가능** (LLM 컨텍스트 조기 도입으로 Setup 품질 향상 시) |

→ v2를 **정신적으로 계승**하되, 실행 위치(orchestrator vs daemon)는 v3에서 변경. 활성화 조건은 LLM 보강을 변수로 추가.

---

## 4. 단계별 마이그레이션

### Phase 0 — 사전 정비 (v3 확장, ~1주)

**목표**: 안전한 LLM-primary 도입을 위한 인프라 갭 해소.

#### 0.1 데이터 검증 (5/4-7 완료분 + 잔여)
- [x] PR #159 머지 (5/4)
- [x] PR #161 머지 (5/6) — `_is_trading_time` UTC→KST 회귀 fix
- [x] PR #162 머지 (5/6) — slippage `price_source_time` 누락 fix
- [x] 5/7 paper validation: 3 fix 모두 정상 동작 + entry signal 16건 + 체결 2건 확인 (§1.1)
- [ ] 5/8–5/13 누적 paper 데이터: pipeline.with_retry 경고 0, RL signal/일 ≥ 1, 평균 PnL 추적

#### 0.2 Phase 5 인프라 갭 (Phase 1.2 활성화 전 필수)
**v2에서 누락된 안전 필수 항목 (코드베이스 점검 결과 반영)**:
- [ ] **kill_switch `_force_flat_callback` 실제 구현** (`services/kill_switch/main.py:287`)
  - 현재: 로깅만 하고 no-op
  - 변경: `PositionTracker`의 모든 오픈 포지션을 `OrderExecutor`(live) / `VirtualBroker`(paper) 통해 즉시 시장가 청산
  - 테스트: 모의 트리거 → flatten 실행 → Redis position HASH 빈 상태 검증
  - **block 조건**: 본 작업 미완료 시 Phase 1.2 (LLM veto) 활성화 금지 — veto가 잘못 발화해도 안전망이 있어야 함

#### 0.3 RL shadow 로깅 인프라 (Phase 2 활성화 전 필수)
- [ ] `shared/strategy/entry/rl_mppo.py::should_enter` — `shadow_mode` 옵션 추가
  - `shadow_mode=true`: signal 생성하되 `shadow=True` 메타 첨부, Signal 반환은 None (orchestrator는 무시)
  - signal payload는 별도 stream(`rl:shadow:predictions`) 또는 ClickHouse table(`kospi.rl_shadow_predictions`) 기록
- [ ] `kospi.rl_shadow_predictions` ClickHouse 마이그레이션 (V6) — schema: ts, symbol, action, confidence, masks, regime_at_decision, executed_setup_id (correlation), executed_pnl
- [ ] `services/trading/strategy_manager.py` — shadow strategy는 dedupe/min_confidence/parallel 기존 흐름과 동일하게 호출하되 결과 무시
- [ ] Grafana panel: "RL shadow vs Setup A/C signal 일치률"

#### 0.4 Kill switch 추가 conditions (Phase 3 Track A 시작 전 필수)
- [ ] `services/kill_switch/conditions.py` — 3개 stub 구현
  - `ApiErrorRateCondition`: `services/monitoring/metrics.py`의 `kis_api_error_total` Counter 기반, 5분 윈도우 error rate
  - `NewsPipelineLagCondition`: news ingestion lag (`shared/llm/data_classes.py` 의 `news_event_ts`)와 wall-clock 차이
  - `ClickHouseInsertFailCondition`: `services/trading/position_tracker.py`의 batch flush 실패 카운터
- [ ] 트리거 임계값을 `config/kill_switch.yaml`에 추가 (보수적 초기값)

**Exit**: 위 4개 sub-section 완료 + 운영자 Phase 1 착수 승인.

**참고**: 0.2/0.4는 paper에서도 손해 보지 않으므로 Phase 1 작업과 **병렬 가능**. 0.3은 Phase 2 직전에만 완료되면 됨.

### Phase 1 — LLM 컨텍스트 → Setup A/C 직접 주입 (4–5주, 1.0 → 1.1 → 1.2 → 1.3 순서)

**목표**: LLM `MarketContext`를 Setup A/C 규칙의 threshold/필터/사이즈에 연결.
운영자 §7-1: 권한 모두 부여. 안전상 점진 도입.
운영자 §7-2: 갱신 주기 **1h**. on-demand 추가 갱신은 Setup signal 발생 시에만.

#### Phase 1.0 — Setup A/C Adapter 구현 (1주, v3 신규)

**목표**: §2.4 결정에 따라 Setup A/C를 EntryRegistry로 등록, paper에서 신호 0건 → ≥1건/일 달성.

- [ ] `shared/strategy/entry/setup_adapters.py` 신규
  - `SetupAEntryAdapter(EntrySignalGenerator)` — `shared/decision/setups/gap_reversion.py::SetupAGapReversion` 래핑
  - `SetupCEventReactionAdapter(EntrySignalGenerator)` — `shared/decision/setups/event_reaction.py::SetupCEventReaction` 래핑
  - `EntryContext → SetupContext` 매핑 (price/spread/depth/ATR/regime/risk_mode 추출)
  - signal 생성 시 `signal.timestamp = context.timestamp` (tz-aware UTC, PR #159 호환) 보장
- [ ] `shared/strategy/registry.py::register_builtin_components()` — adapter 2개 등록
  - `EntryRegistry.register_class("setup_a_gap_reversion", SetupAEntryAdapter)`
  - `EntryRegistry.register_class("setup_c_event_reaction", SetupCEventReactionAdapter)`
- [ ] YAML 신규
  - `config/strategies/futures/setup_a_gap_reversion.yaml` (`enabled: false` 초기, params 그대로)
  - `config/strategies/futures/setup_c_event_reaction.yaml` (`enabled: false` 초기)
- [ ] 단위 테스트
  - Setup A trigger 조건 만족 시 adapter가 Signal 반환
  - signal.timestamp는 tz-aware UTC
  - `EntryContext.market_context = None` (LLM 부재) 시 Setup 자체 default로 동작 (Phase 1.1 LLM 적용 전)
- [ ] paper 활성화 검증 (1일)
  - Setup A YAML `enabled: true` 플립 → 1거래일 paper 가동 → 신호 ≥ 1건 발생 확인
  - 다시 `enabled: false`로 복귀 (Phase 1.1 작업 시점까지)

**Exit**: paper 1거래일에서 Setup A signal ≥ 1건, signal.timestamp tz 검증, 기존 entry guards(spread/staleness/price-deviation) 통과 확인.

#### Phase 1.1 — Threshold tuning (1주)

§2.4 결정에 따라 standalone `decision_engine/main.py`가 아닌 **adapter 내부**에 LLM threshold 로직을 둔다.

- [ ] `services/trading/llm_context_provider.py` — `asset_class="futures"` 분기 추가 (현재 stock 기본)
- [ ] LLM 컨텍스트 publisher 갱신 주기 **1h** (`config/llm.yaml::market_context_publisher.analysis_interval_minutes`) — 운영자 §7-2 결정. on-demand 갱신은 Setup signal 발생 직후 trigger
- [ ] `SetupAEntryAdapter.should_enter` 내부에서 `context.market_context` 활용:
  - `risk_mode == RISK_OFF` + `risk_score > 75` → entry confidence threshold ×1.3
  - `regime IN [BEAR_STRONG, BEAR_MODERATE]` → long-bias 차단, short-only
- [ ] `SetupCEventReactionAdapter.should_enter`:
  - `regime == BULL_STRONG` + `risk_mode == RISK_ON` → ATR breakout multiplier ↓ (관대)
- [ ] `setup_a_gap_reversion.yaml`, `setup_c_event_reaction.yaml`에 `llm_tuning` 섹션 추가 (모든 스케일 인자 config 기반)
- [ ] 단위 테스트: LLM 부재 fallback, regime별 threshold 조정, `confidence < 0.3` skip
- [ ] paper 가동: Setup A `enabled: true`로 플립 → 1주 paper

#### Phase 1.2 — Veto 권한 (1주, **block 조건: §4 Phase 0.2 kill_switch flatten 완료 필수**)

§2.4 결정에 따라 standalone `services/risk_filter/main.py`가 아닌 **strategy_manager 단계 또는 adapter 내부**에 LLM veto 가드를 둔다 (orchestrator 경로 단일 진입점 유지).

- [ ] `services/trading/strategy_manager.py::_apply_llm_veto()` 신규 (또는 adapter 내부에 직접):
  - `MarketContext.confidence ≥ 0.6` AND (`overall_signal == STRONG_BEARISH` for long entry / `STRONG_BULLISH` for short entry) → signal drop with `skip_reason=llm_veto`
  - veto는 entry만, exit/stop은 LLM이 막을 수 없음 (안전)
- [ ] veto된 signal은 `kospi.signals_all`에 `executed=0 + skip_reason=llm_veto`로 기록 (counterfactual 측정용). 본 테이블은 Phase 5 daemon 코드와 공유.
- [ ] Telegram alert: veto 발화 시 운영자 가시성
- [ ] 단위 테스트: veto 발화 조건, exit는 veto 대상 아님, confidence < 0.6 fallback

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

### Phase 2 — RL 메인 → shadow 강등 (1주, **block 조건: §4 Phase 0.3 RL shadow 로깅 인프라 완료 필수**)

**목표**: RL을 의사결정 경로에서 제거, 비교용 로그로만 보존.
운영자 §7-3 결정: shadow 보존 기간 **6개월**.

§2.4 결정에 따라 §4 Phase 0.3에서 구현한 `RLMPPOEntry::shadow_mode=true` 옵션을 활용한다 (별도 logger 클래스 추가 없이 entry 클래스 내장).

- [ ] `config/strategies/futures/rl_mppo.yaml`에 `shadow_mode: true` 추가 (`enabled: true` 유지)
  - 효과: strategy_manager가 호출하나 should_enter는 항상 None 반환, signal payload만 별도 stream/CH 기록
- [ ] Setup A/C 메인 활성: `setup_a_gap_reversion.yaml::enabled: true`, `setup_c_event_reaction.yaml::enabled: true`
- [ ] Grafana 대시보드 추가 (Phase 0.3에서 만들어둔 panel 확장):
  - "Setup A/C signals/day" vs "RL shadow LONG/SHORT/HOLD distribution"
  - LLM regime → setup conversion rate
  - **Counterfactual P&L**: RL이 LONG_ENTRY인데 Setup A가 발화 안 한 시점 / 그 반대 — paper 가격 추적

**Exit**: Phase 5 Gate 1 게이트(2주 paper extension) Setup A/C 기반으로 누적, RL 매매 0건 확인. shadow predictions ≥ 1k건 누적.

### Phase 3 — Phase 5 Gate 2/3 (운영자 영역, 빠른 진입 정책)

**목표**: 운영자 게이트 통과 후 실거래 1계약 진입.
운영자 §7-5 결정: **빠르게 진입** — Phase 2(RL shadow 강등)와 **병행** 진행. Phase 1.1 완료 + paper 1주 안정성 확인 후 즉시 Gate 2 운영자 영역 시작.

| 트랙 | 시작 시점 | 종료 조건 |
|------|---------|---------|
| Track A — 운영자 게이트 | Phase 1.1 완료 + paper 1주 | Gate 3 14일 통과 |
| Track B — 엔지니어링 (Phase 1.2/1.3, Phase 2) | 동일 시점, 병렬 | Phase 2 exit |

#### Track A 작업 (운영자 + 엔지니어링 보조)
**Block 조건**: §4 Phase 0.4 kill_switch 3 stub conditions(api_error/news_lag/ch_insert_fail) 구현 완료.

- [ ] **즉시 시작**: `futures-legal-review.md` §1–6 운영자 작성 (KIS counsel/세무사) — PR #158이 정비한 항목 그대로 채움
- [ ] KIS Real-account API smoke test (production TR ID, balance, WebSocket on real)
- [ ] 증거금 입금 (≈ 2M KRW)
- [ ] position-recovery 드릴 (Redis 키 인위 삭제 → sentinel/Telegram 발생 검증)
- [ ] **Phase 0.4 완료** — kill_switch 6 conditions 전체 동작 확인
- [ ] systemd unit 결정 (v3 변경): §2.4 Adapter 패턴 채택으로 **Phase 5 daemon 4개(`kis-decision-engine`, `kis-risk-filter`, `kis-order-router`, `kis-kill-switch`) 중 `kis-kill-switch`만 production install**. 나머지 3개는 미설치 — orchestrator 경로가 동일 책임 수행
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
| **Setup C 저빈도** (`rl-repurposing-v1.md` §10.1: ~0.9 trade/mo) | trade 수 부족 → 통계적 검증 어려움 | v2 계획대로 **Setup A 단독 시작**, Setup C는 RL aux 활성화 대기 경로 |
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

## 8. 작업 분해 (Phase 0 + Phase 1 상세, v3 갱신)

Phase 0/1만 사전 분해. Phase 2/3은 Phase 1 결과 보고 다시 분해.

### Phase 0 — 사전 정비 (1주, v3 신규)
- **0.1**: 5/8–5/13 paper 누적 데이터 모니터링 (자동, 작업 부담 0)
- **0.2-a** (2일): `services/kill_switch/main.py::_force_flat_callback` 실제 구현 — `PositionTracker.flatten_all()` 호출 + 결과 검증
- **0.2-b** (1일): 단위/통합 테스트 (모의 트리거 → flatten → Redis 빈 상태)
- **0.3-a** (2일): `RLMPPOEntry::shadow_mode` 옵션 추가 + signal payload 별도 기록 경로
- **0.3-b** (1일): ClickHouse `kospi.rl_shadow_predictions` 마이그레이션 (V6) + 단위 테스트
- **0.3-c** (1일): Grafana panel "RL shadow distribution"
- **0.4-a** (1일): `ApiErrorRateCondition` 구현 (5분 윈도우, error rate 임계)
- **0.4-b** (1일): `NewsPipelineLagCondition` 구현
- **0.4-c** (1일): `ClickHouseInsertFailCondition` 구현 + `config/kill_switch.yaml` 임계값 추가

총 **~10일 (병렬 가능)**. 0.2/0.4는 Phase 1 작업과 병렬 진행 가능.

### Phase 1.0 — Setup A/C Adapter (1주, v3 신규)
- **1.0-a** (2일): `shared/strategy/entry/setup_adapters.py` — `SetupAEntryAdapter`, `SetupCEventReactionAdapter` 작성 + EntryContext→SetupContext 매핑
- **1.0-b** (1일): `shared/strategy/registry.py::register_builtin_components()` — adapter 2개 등록
- **1.0-c** (1일): `config/strategies/futures/setup_a_gap_reversion.yaml`, `setup_c_event_reaction.yaml` 신규 (`enabled: false` 초기)
- **1.0-d** (2일): 단위 테스트 (adapter 매핑, signal.timestamp tz-aware, LLM 부재 fallback)
- **1.0-e** (1일): paper 1거래일 검증 (Setup A enabled=true → 신호 ≥ 1건 → enabled=false 복귀)

### Phase 1.1 — Threshold tuning (1주)
- **1.1-a** (1일): `services/trading/llm_context_provider.py` — `asset_class="futures"` 분기 + 선물 prompt template (`config/llm.yaml`)
- **1.1-b** (2일): `LLMContextPublisher` 1h 갱신 주기 (`market_context_publisher.analysis_interval_minutes: 60`) + Setup signal on-demand trigger 훅
- **1.1-c** (2일): `SetupAEntryAdapter` 내부에 regime/risk_score 기반 threshold scaling 로직 (config-driven)
- **1.1-d** (1일): `SetupCEventReactionAdapter` 동일 구조
- **1.1-e** (1일): `setup_a_gap_reversion.yaml`/`setup_c_event_reaction.yaml`에 `llm_tuning` 섹션 + 단위 테스트 (LLM 부재 fallback, regime별 조정, `confidence < 0.3` skip)

### Phase 1.2 — Veto 권한 (1주)
- **1.2-a** (2일): `services/trading/strategy_manager.py::_apply_llm_veto()` (또는 adapter 내부) — LLM veto 입력 + entry-only 가드 (exit/stop은 veto 대상 아님). §2.4 Adapter 패턴 결정에 따라 standalone `services/risk_filter/main.py`가 아닌 orchestrator 경로에 통합
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
| 2026-05-04 | PR #159 머지 (tz-aware 핫패스 fix) |
| 2026-05-06 | PR #161 머지 (`_is_trading_time` UTC→KST 회귀 fix), PR #162 머지 (slippage `price_source_time` 누락 fix) |
| 2026-05-07 | 5/7 paper validation: 3 fix 모두 작동, 2건 체결(둘 다 손실 -2.75/-3.35) — Apr 1-15 micro-loss 패턴 재확인 |
| 2026-05-07 | v3 — 코드베이스 점검 결과 반영. §2.4 통합 아키텍처(Adapter 패턴) 확정, §4 Phase 0 사전 정비(kill_switch flatten / 3 stub conditions / RL shadow logging) 추가, Phase 1.0(Adapter 구현) 신설, §8 작업분해 갱신. Phase 5 standalone daemons은 Phase 4까지 deferred |
| 2026-05-07 | **v3.1** — code review 피드백 5건 정정. §8 1.2-a 타겟을 `services/risk_filter/main.py`(잘못)에서 `services/trading/strategy_manager.py`로 정정 (§2.4 일관성). §3.1 PR #158 상태 ✅ → OPEN 정정. §1.3 모듈 수 14→16+ 정렬. §5 Setup C citation Phase 3 §10.1 → rl-repurposing-v1 §10.1. §2.2 Phase A/B → §4 Phase 2/4 명명 정렬 |
| TBD | Phase 0 사전 정비 시작 |
| TBD | Phase 1.0 (Adapter) → Phase 1.1 → 1.2 → 1.3 + Phase 3 Track A 병행 |
