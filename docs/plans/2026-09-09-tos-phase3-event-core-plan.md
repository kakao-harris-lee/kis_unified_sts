# TOS Phase 3 계획 — 단일 이벤트 코어와 19-step 완성 (durable inbox·재생·결과 어휘·직렬화 admission·calibration)

- **상위**: 개발계획 §6 Phase 3(작업 1~6 · 종료 조건 4) · 설계 #31(이벤트 코어 · §9 «닫지 않음» 4·7·9·10) · 설계 #40(Phase 2 런타임) · 설계 #35(슬라이스 갭클로징 GAP-1~4).
- **선행**: Phase 2 런타임 슬라이스 #1~#3 + 커널 라운드 #1 + Phase 4 작업 6(SendSeal) — 브랜치 `feat/tos-phase3-event-core` 는 `feat/tos-phase4-send-seal` 위 스택.
- **저작**: 세션 모델 단독 · 권한 부여 없음 · EV 행 상태 변경 0 · 실 브로커 transport 0(합성) · 라이브 권한 0.
- **서베이 실측(2026-09-09 · `210cb80b`)**:
  - **작업 1 잔여는 작다**: compose 가 step 2·3·5·11(egressgw)·4(IAP)·6~10(risk)·13·14(currentness) 를 실 Stage 로 결선(Phase 2 종료 조건 «stand-in 0» 충족). 남은 것은 설계 #31 §9-10 «Coordinator positive 인증 게이트»(RFC-002 §10.7 «verify current Safety Authority · verify live authorization») — 커널 `engine` 에 결선 지점 없음(`authority_epoch_current`/`liveauth` grep 0).
  - **이벤트 유입·재생 부재**: `EngineCore.run(events)` 는 메모리 iterable(core.py:253) · 런타임 어디에도 `.run(`/`.handle(` 호출 0 — 이벤트는 테스트 픽스처(`compose/_fixtures.py:262-273`)가 직접 만든다. `EGRESS_RESULT` 재주입 경로도 런타임에 없음(게이트웨이 결과는 `SendHandoff` 즉시 반환 · 결과 이벤트는 백테스트 `GatewayResultReinjector` 만). 평가 재현 판정 `engine.sink.replay_result_for`·`PipelineResult.outcome_digest` 런타임 소비 0. durable 은 evidence store(해시체인·`replay()`·outbox D3)와 RCL 로그(`replay`·`verify_replay` 부팅 검증)뿐.
  - **결과 어휘**: `EgressResultKind` 6종(ACK/FULL_FILL/PARTIAL_FILL/REJECT/UNKNOWN/TIMEOUT) · `ProvisionalReservationLedger.apply_egress_result` 는 attempt 불일치·예약 부재를 **`ArtifactIntegrityError` 로 raise**(state.py:355-368) — 늦은/중복/고아 결과가 기록된 보수 이벤트가 아니라 크래시. cancel/replace/expired/late 없음. ADR-002-005 §6~§9 5차원(Intent·Attempt·BrokerOrder·Knowledge·Capacity)은 커널 `orthostate`(`may_transition`·`coupling_violations`·`reconstruct_conservative`)에 있으나 engine/runtime 소비 0. `posttrade.PostTradeFinalityProof`·`replacement` 소비 0. `release_admissible` 는 `finality_witness is True` 만 admit — 증인 생산자 없음.
  - **DSL admission**: `engine.admission.strategy_admissible` 은 in-process typed `AuthoredStrategy` 만(설계 #31 §3.5) · escape-checker `dsl.admissibility.analyze(CandidateProgram)` 는 미호출 · `AuthoredStrategy → CandidateProgram` lowering 부재 · `AdmissibilityResult` 에 strategy digest 결속 부재(G12) · YAML 전략 로더 부재(런타임은 `StrategyRegistry()` 빈 레지스트리 · 전략은 테스트가 주입).
  - **marketfeed**: 커널 `MarketFeedContextResolver`·`ContextValueView`·GAP-3(결정가=사이징가 계보) 착지. 런타임 marketfeed 어댑터(D-E2) 부재 — `DECISION_TICK` 의 Capsule 은 픽스처. outbound price 는 `outbound_binding_mismatch` 가 step-2 `QuantityDerivation` 과 동일성 검사(gateway.py:1333-) · `SendSeal` 이 그 값을 봉인. «결정가→사이징가→주문가» 계보 digest 는 결정가↔사이징가까지만.
  - **backtest**: `DeterministicFillModel`·`FillParameters.price_band_fraction`(합성 거부 밴드) 있음 · paper 관측 대비 calibration·deviation budget·expectancy 금지 게이트 부재 · 백테스트는 `EngineCore.run` 을 그대로 소비(driver.py:27-40 — 패리티의 구조적 전제 충족).
  - 크기 register: `engine/core.py`·`sequencer.py` 미등재(여유 확인 필요) · `_wiring.py` 1116 등재.

## 0. 공통 규율

이전 슬라이스 §0 전부 + 다음:
- **파일 소유 1레인**: `_wiring.py`·`root.py`·`_types.py` 는 웨이브당 한 레인만 편집. 공유 파일(`config/tos_size_budget.yaml`)은 `git add -p` 헝크 스테이징 + **pathspec 없는 커밋**.
- **커널 이벤트 어휘 확장은 열거 추가로만**(설계 #31 §2.2 «인터페이스 무변경») · 미지 kind 는 fail-closed 유지.
- **크래시는 이벤트가 아니다**: 런타임이 커널 예외를 삼켜 진행하면 결함. 늦은/중복/고아 결과는 커널이 **기록된 보수 결과**로 돌려주도록 커널을 고친다(런타임 try/except 금지).
- 수치(대기 상한·편차 예산·재생 창)는 전부 YAML named-TBD null → 부팅 거부 → 픽스처 공급. VERIFICATION-PROFILE-002 승인값이 있으면 좌표를 주석에 인용.
- 웨이브마다 독립 리뷰(Claude 측 `code-reviewer`) → 처분 → 재심. 다음 웨이브는 재심 approve 후.

## 1. 웨이브 1 — 슬라이스 A(durable inbox·드라이버·재생) ∥ 슬라이스 D(직렬화 admission)

### 1.1 슬라이스 A — `tos_runtime.engine` (작업 2 · 종료 조건 «replay digest 동일»·«결과 유실/지연/역전 ≠ blind resubmit»)

**커널(레인 A-K · `tos/src/tos/engine`)**
- `EngineEvent` 에 `event_id: str`(content-addressed · `derive_id("event", canonical_digest)`) 확정 — 이미 있으면 재사용(실측 후 보고).
- `ProvisionalReservationLedger.apply_egress_result` 의 두 raise(예약 부재 · attempt 불일치)를 **기록된 보수 결과**로: 반환형 `ResultApplication{applied: bool, disposition: ResultDisposition{APPLIED, ORPHAN_NO_RESERVATION, MISMATCHED_ATTEMPT, DUPLICATE}}` · `EngineCore._handle_egress_result` 는 non-APPLIED 를 `EvidenceKind.RESULT_UNMATCHED` 로 기록하고 **capacity 를 절대 완화하지 않는다**(ADR-002-002 §15.2 «later valid fill accepted», ADR-002-005 §7 «absence is not proof»). DUPLICATE 판정은 `(attempt_id, kind, filled, remaining, reference)` 동일성.
- 재생 판정 `engine.sink.replay_result_for` 는 그대로 재사용(REUSE) · `EventResult` 에 `outcome_digest` 노출 확인.

**런타임(레인 A-R · 신규 `tos_runtime/engine/`)**
- `SqliteEventInbox`(append-only sqlite WAL · 자체 파일 · 열: seq·event_id·kind·instrument·reference·payload_json·payload_digest·consumed_seq(evidence 영수증 seq)·consumed_at_generation) — `enqueue(EngineEvent) -> InboxReceipt` · `next_unconsumed()` · `mark_consumed(seq, evidence_seq)`. 중복 `event_id` 는 UNIQUE 로 거부(같은 바이트=같은 id 이므로 재시도 안전 · 다른 바이트 같은 id 는 구조상 불가).
- `EngineDriver`(단일 스레드 · 결정론): 루프 = `inbox.next_unconsumed()` → `core.handle(event)` → evidence `EVENT_CONSUMED{event_id, payload_digest, outcome_digest, halt_reason}` append → `inbox.mark_consumed`. **크래시 창 규칙**: evidence 에 `EVENT_CONSUMED(event_id)` 가 있고 inbox 미표시면 재기동 시 **재처리 없이** 표시만(멱등) · evidence 없으면 재처리(코어는 결정론이라 같은 outcome — 재생 검증이 이를 실증).
- `EGRESS_RESULT` 재주입: 게이트웨이 step 19 결과를 드라이버가 `EgressResultPayload` → `EngineEvent(EGRESS_RESULT)` 로 **inbox 에 enqueue**(같은 드라이버가 다음 턴에 소비 · 순서 = reference). 합성 transport 는 동기라 결과가 즉시 존재; 실 transport 의 «결과 미도착» 은 `TimeoutInjector`: time 서비스 단조 시계로 `max_send_result_wait_ms`(신규 time 키 · named-TBD null) 초과 시 `EGRESS_RESULT(kind=TIMEOUT)` 를 enqueue(RFC-005 §11 «timeout = UNKNOWN, never rejection»). 늦게 온 실제 결과는 커널 §1.1 의 DUPLICATE/APPLIED 규칙으로 처리(TIMEOUT 뒤 FILL 은 APPLIED — knowledge 갱신 · 자본 완화 없음).
- `replay_engine(inbox, evidence, compose_fn) -> ReplayVerdict`: 깨끗한 코어를 다시 조립해 inbox 를 순서대로 재소비하고 각 `outcome_digest` 를 evidence 의 기록과 `replay_result_for` 로 대조 · 불일치 ⇒ `record_halt`(기존 `_boot_integrity` 경로) · 부팅 시 `verify_rcl_log_or_halt` 뒤에 실행(`replay_window_events` 설정 키 · null 거부).
- compose: `ComposedRuntime` 에 `driver`·`inbox` 추가 · 기존 e2e 는 `driver.enqueue_and_run(event)` 로 전환(테스트가 코어를 직접 호출하는 경로 제거 — grep 0).
- 테스트(hermetic · RED 선행): enqueue 중복 거부 · 소비 순서 = seq · 크래시 창 3분기(마킹 전 죽음/후 죽음/evidence 전 죽음) 재기동 멱등 · TIMEOUT 후 FILL 도착 시 자본 불변·knowledge 갱신 · 역전 reference 이벤트 `EVENT_ORDER_REVERSED` 기록(기존 커널 규칙) · 재생 digest 동일(같은 inbox 두 번 재생) · 뮤테이션: 재생 비교 제거 red · 재처리 시 코어 결과 변조 red · 게이트웨이 결과를 inbox 우회로 코어에 직접 넣는 경로 grep 0 핀.

### 1.2 슬라이스 D — 직렬화 전략 admission (작업 3 전반 · 설계 #31 §9-4 · §3.5 D4)

**커널(레인 D-K · `tos/src/tos/dsl` · `tos/src/tos/engine/admission.py`)**
- `dsl.lowering.lower_strategy(strategy: AuthoredStrategy) -> CandidateProgram` — typed algebra 를 노드 그래프로 내림(전 노드 kind 는 `candidate.py` 닫힌 집합 안 · `iter_nodes` 로 escape-checker 가 검사 가능). 역방향(raising)은 만들지 않는다.
- `dsl.serialization.parse_strategy(mapping) -> AuthoredStrategy` — **pydantic 모델 검증만**(YAML 파싱은 런타임 · 커널은 dict 수용 · 미지 키 `extra="forbid"`) · 실패는 `StrategyParseError`.
- `AdmissibilityResult` 에 `strategy_id`·`strategy_digest` 결속(G12) — covered 집합에 추가하므로 기존 픽스처 digest 영향을 실측·보고 · `analyze_candidate(program, *, strategy_id, strategy_digest)`.
- `engine.admission.strategy_admissible` 확장: (i) 기존 typed AST walk(capsule-sourced compare ≥1) 유지 (ii) `lower_strategy` → `analyze` → `is_admissible` 게이트 추가(escape-checker 실호출 · 설계 #31 §3.5 «이연» 해소) (iii) 결과 `AdmissionResult` 에 `AdmissibilityResult` 결속. in-process typed 경로도 같은 게이트를 지난다(두 경로 동형).
- 테스트: 정상 전략 lowering 후 admissible · `candidate.py` escape 패밀리 각각을 lowering 결과에 주입(테스트 전용 `model_construct` 우회 캐너리 — WDR 2층 관용구)하면 inadmissible · parse 미지 키 거부 · digest 결속(같은 전략 두 번 = 같은 digest · 한 규칙 변경 = 다른 digest) · 뮤테이션: `analyze` 호출 제거 red.

**런타임(레인 D-R · 신규 `tos_runtime/strategy/`)**
- `load_strategies(config_dir/strategies/*.yaml) -> tuple[AuthoredStrategy, ...]`: yaml.safe_load → `parse_strategy` → `strategy_admissible` → `StrategyRegistry` 등록(inadmissible 은 **부팅 거부** · 이유 evidence `STRATEGY_REFUSED`) · 예시 `tos/runtime/config/strategies/example.strategy.yaml`(named-TBD 값 null · 픽스처가 실전략 공급) · `OPERATOR_ATTESTED_INPUTS` 에 전략 파일 digest 등재.
- compose: `StrategyRegistry()` 빈 생성 → 로더 결과로 대체(`registry` 주입 인자는 테스트 호환용으로 유지하되 파일이 있으면 파일이 우선 · 둘 다 있으면 거부).
- 테스트: YAML 정상/escape/미지 키 3분기 · 부팅 거부 · 기존 compose e2e 가 파일 전략으로 동작(픽스처 전환).

## 2. 웨이브 2 — 슬라이스 B(Coordinator 양성 게이트) ∥ 슬라이스 C(결과 어휘·orthostate·post-trade finality)

### 2.1 슬라이스 B — 작업 1 잔여 (설계 #31 §9-10)

- 커널: `engine.core.CoordinatorPreconditions(Protocol)`: `authority_epoch_current() -> bool | None` · `live_scope_authorized(transport_nature) -> bool | None` — `EngineCore(preconditions=...)` 필수 인자(기본 없음 · 백테스트 드라이버는 «합성 = 항상 non-live» 구현을 명시 주입). `_handle_decision_tick` 첫 단계에서 둘 다 `is True` 아니면 `EvidenceKind.COORDINATOR_PRECONDITION_REFUSED` + `HaltReason.AUTHORITY_NOT_CURRENT`/`LIVE_SCOPE_NOT_AUTHORIZED` 로 중단(step 1 이전 · 아무것도 소비 안 함). 19-step 순서·`INJECTED_STAGE_STEPS` 불변(ADR-002-002 §11 열거는 그대로 · 이 게이트는 RFC-002 §10.7 Coordinator 의무).
- 런타임: `authority_epoch_current` = `SafetyAuthorityEpochService.current_state()` + 커널 `tos.authority.authority_epoch_current(...)` · `live_scope_authorized` = 커널 `tos.liveauth` 술어(restricted-live `NOT_AUTHORIZED` 이므로 **합성 transport 만 True** · `TransportNature.reaches_broker` True 면 False — 실주문 경로 구조 차단 재확인).
- 테스트: epoch 미현행 ⇒ tick 거부·step 1 미실행 · `reaches_broker=True` transport ⇒ 거부 · 뮤테이션: 게이트 제거 red.

### 2.2 슬라이스 C — 작업 5 (partial fill·cancel/replace·no-ack UNKNOWN·timeout·late result → 어휘 + post-trade finality)

- 커널 어휘: `EgressResultKind` += `CANCEL_ACK`·`EXPIRED`(브로커 관측 · ADR-002-005 §7) — `_RESULT_TRANSITIONS`: `CANCEL_ACK` ⇒ knowledge 갱신 + capacity 는 최대 `RELEASE_PENDING_PROOF`(CPL-4 «cancel is not release») · `EXPIRED` 동일 · 둘 다 finality 증인 없이는 RELEASED 불가(기존 `release_admissible`).
- 커널 결합: 런타임 `tos_runtime/engine/orthostate_projection.py` — 각 `EGRESS_RESULT` 를 `orthostate.CompositeState` 전이로 투영하고 `may_transition`·`coupling_violations` 로 검증 · 위반 ⇒ evidence `COUPLING_VIOLATION` + `record_halt`(권위-투영 불일치 경보와 같은 부류). replace 는 `tos.replacement` 술어(`overlap_first_reservation_complete`·`cancel-first`)로 **새 attempt** 만 허용(기존 attempt 재사용 0 · RFC-005 §11 «retry is a new send»).
- post-trade finality: `tos_runtime/posttrade/finality.py` — `PostTradeFinalityProof` 생산자(합성 transport 의 FULL_FILL + `EconomicObligationRecord` 완결 ⇒ proof · `finality_dimensions_orthogonal`·`obligation_leg_set_complete` 통과 시만) → `release` 레인의 `finality_witness` 로 공급(현재 None). PARTIAL_FILL 은 proof 없음(잔량 live). 실 브로커 증거는 Phase 5(recon) — 합성 전용임을 도크스트링·§7 에 명시.
- 테스트: 결과 kind 별 capacity/knowledge 전이표 전수 · TIMEOUT→FILL·CANCEL_ACK→FILL(«cancel-crossing-fill») 보수 처리 · replace 는 새 attempt · finality proof 있을 때만 RELEASED · 뮤테이션: CPL-4 위반(cancel ⇒ RELEASED) red.

## 3. 웨이브 3 — 슬라이스 E(calibration) + 슬라이스 F(패리티·순서 뮤테이션 매트릭스)

### 3.1 슬라이스 E — 작업 6

- 커널 `backtest.calibration`: `FillDeviation{price_bps, fill_ratio, latency_bars}` · `calibration_within_budget(observed: tuple[FillDeviation,...], budget: DeviationBudget) -> CalibrationVerdict{WITHIN, EXCEEDED, INSUFFICIENT_OBSERVATIONS}` — 관측 0 ⇒ INSUFFICIENT(fail-closed) · `expectancy_claim_permitted(verdict) -> bool`(WITHIN 만 True) · `BacktestResult` 의 expectancy 필드는 permitted 아니면 `None` + `withheld_reason`.
- 런타임 `tos_runtime/backtest/calibration_report.py`: evidence store 의 `EGRESS_RESULT_RECORDED` 행(paper 합성 체결)과 같은 `(strategy_digest, capsule_digest)` 의 백테스트 fill 을 짝지어 `FillDeviation` 산출 · 예산은 `config/backtest_calibration.example.yaml`(named-TBD null).
- 테스트: 예산 내/초과/관측 부족 3분기 · expectancy 은닉 · 뮤테이션: 관측 0 을 WITHIN 으로 바꾸면 red.

### 3.2 슬라이스 F — 종료 조건 실증

- **19-step 순서 뮤테이션 매트릭스**(`tos/tests/engine/test_sequencer_mutation_matrix.py`): `COMMITMENT_FLOW_ORDER` 를 monkeypatch 로 (i) 인접 교환 13쌍 (ii) 각 step 누락 14 (iii) 각 step 중복 14 — 각 변형에서 `validate_stage_map`/시퀀서 핀/슬라이스 e2e 중 최소 1개가 red 임을 **테스트가 실행**해 «생존 0» 을 기계적으로 판정(외부 뮤테이션 도구 추가는 tos 의존성 allowlist 개정이라 기각 · §4).
- **백테스트=paper 패리티**: 같은 전략·같은 이벤트 열을 (a) 백테스트 드라이버 (b) compose 런타임 `EngineDriver` 로 돌려 `outcome_digest` 열 동일 — 차이는 EventSource/Transmit 주입뿐임을 실증(설계 #31 §12).
- **blind resubmit 0**: 결과 유실(TIMEOUT)·지연(TIMEOUT 후 FILL)·역전(reference 역행) 3시나리오에서 transport 호출 수 1 · 새 attempt 는 새 permit+proof 경유만.

## 4. 기각 대안

- **inbox 를 evidence store 같은 파일에**: 증거(append-only·해시체인)와 큐(소비 표시 UPDATE)의 실패 도메인 분리(D3) 위반. 별 파일 + 영수증 seq 결속.
- **비동기 이벤트 루프**: 설계 #31 §2.1 D5 기각 사유 그대로(결정론·재생·패리티).
- **늦은 결과를 런타임 try/except 로 처리**: 커널 raise 를 삼키면 «크래시=이벤트» 결함. 커널이 보수 결과를 돌려주도록 수정.
- **`mutmut` 등 외부 뮤테이션 도구**: tos 의존성 allowlist(설계 #1 §3.2) 개정 필요 · 매트릭스는 표준 pytest 로 표현 가능.
- **cancel/replace 를 기존 kind(REJECT/UNKNOWN)에 접기**: CPL-4·§15.2 를 표현 불가 · 열거 추가가 §2.2 규율.
- **실 브로커 결과로 finality proof**: Phase 5 recon 소관 · 이 Phase 는 합성 proof 만.
- **런타임 marketfeed 어댑터(D-E2) 를 이 Phase 에**: 작업 4 의 «lineage 강화» 는 커널 계약(결정가→사이징가→주문가 digest 사슬 · `SendSeal` 에 `price_lineage_digest` 결속)으로 이 Phase 에서 하되, 실 값 표면(KIS REAL read/기록 데이터) 어댑터는 Phase 4 작업 2(`REAL_READ` 스코프)·Phase 7 시나리오 소관 — 웨이브 2 슬라이스 C 에 «가격 계보 digest 봉인» 항목으로 축소 편입(운영자 확인 항목 ③).

## 5. 종료 조건 (= 개발계획 Phase 3)

- 순서 뮤테이션 매트릭스 생존 0(슬라이스 F 기계 판정) · 같은 Capsule/정책/seed replay digest 동일(슬라이스 A·F) · 백테스트와 paper 가 같은 코어·시퀀서(F 패리티) · 유실/지연/역전 ⇒ blind resubmit 0(A·C·F).
- 웨이브별 `tos/tests`·`tos/runtime/tests` green · mypy/ruff/black/firewall/lint-imports/budget/completion/spec/contract 통과 · 독립 리뷰 approve · 커널 diff 는 K 레인 커밋에만 · 신규 수치 리터럴 0.

## 6. 운영자 확인 항목

1. `EgressResultKind` 에 `CANCEL_ACK`·`EXPIRED` 추가(커널 어휘 확장 · ADR-002-005 §7 정합) — **승인 (2026-09-09)**.
2. 이벤트 inbox 를 evidence 와 **별 sqlite 파일**로 두는 것(D3 실패 도메인 분리 준용) — **승인 (2026-09-09)**.
3. 작업 4 를 «가격 계보 digest 봉인(커널)» 으로 축소하고 실 값 표면 어댑터는 Phase 4/7 로 — **승인 (2026-09-09)**.
4. 신규 설정 키 5종(`max_send_result_wait_ms`·`replay_window_events`·`strategies/` 디렉터리·`backtest_calibration` 예산·`finality` 합성 정책) 의 named-TBD 값 결정은 착지 후. — **승인 (2026-09-09 · «1,2,3,4 모두 비준»)**.

## 7. 실행 결과·독립 리뷰 처분

### 7.1 웨이브 1 착지 (2026-09-09 · 13커밋 `5768c6f2..1d58b02c` · 레인 4 병렬)

| 레인 | 커밋 | 내용 |
|---|---|---|
| A-K | `5768c6f2` `f299191a` `c4e52144` (+black `e9eb98be`) | `event_identity(event, *, scheme)`(필드 아님 — `EngineEvent` 는 scheme 없는 FrozenModel · 보고된 폴백) · `apply_egress_result -> ResultApplication{applied, disposition∈{APPLIED, ORPHAN_NO_RESERVATION, MISMATCHED_ATTEMPT, DUPLICATE}, projection}`(raise 제거 · non-APPLIED 는 `EvidenceKind/HaltReason.RESULT_UNMATCHED` · capacity/knowledge 불완화 · DUPLICATE 는 5튜플 구조 동일성) · 도달 불가 `HaltReason` 2종 제거(anti-phantom) · `EventResult.outcome_digest`(pipeline digest 재사용 · EGRESS_RESULT 는 None) · 결정론 카나리 |
| A-R | `d29492b2` `d11cbbd9` `911c4a0d` `52d4e971` | `tos_runtime.engine.inbox.SqliteEventInbox`(별 sqlite · event_id UNIQUE · 중복은 typed receipt) · `driver.EngineDriver`(런타임 유일 `core.handle` 호출점 · 크래시 창 3분기 멱등 · egress 결과 재주입 · `MAX_send_result_wait_ms` TIMEOUT 주입) · `replay.replay_engine`(커널 `replay_result_for` 재사용) · `compose/_engine_wiring.py` 분리 · `ComposedRuntime.inbox/driver` · 기존 compose e2e 무수정(`run_once` 가 드라이버 위임) · 핀 테스트 `test_no_direct_core_calls.py` |
| D-K | `a8418b0b` `9ab3f650` `49129e64` | `dsl.lowering.lower_strategy`(총함수 · 65 테스트) · `dsl.serialization.parse_strategy`(pydantic · `StrategyParseError` 경로) · `AdmissibilityResult.strategy_id/strategy_digest`(covered · 하드코딩 digest 단언 0 · dsl 파일 EVIDENCE-SURFACE-MAP 핀 0 실측 → 기존 클래스에 직접) · `strategy_admissible` 에 escape-checker 게이트(`AdmissionResult.admissibility_result`) · 설계 #31 §3.5 이연 해소 |
| D-R | `d338c59e` `1d58b02c` | `tos_runtime.strategy.loader.load_strategies`(파일 하나라도 불량이면 전체 거부 · null leaf 거부 · 빈 디렉터리 거부 · sha256) · `resolve.resolve_strategy_registry`(파일 소스 xor 주입 레지스트리 · 둘 다 ⇒ 거부 · `STRATEGY_REFUSED` 증거) · `OPERATOR_ATTESTED_INPUTS` 에 전략 파일 digest · compose 픽스처 파일 소스 전환 · YAML↔in-process 동형 교차 테스트 |

**보고된 편차·한계(전부 공개)**: ① replay 의 side-effect-free 재조립은 step 14 까지(`transmit=None`) — send 경계 포함 재생은 기록/재생 transport 부재(A-R 도크스트링) ② 부분 창(`window_events`) 재생은 창 밖 이벤트가 남긴 예약 때문에 false divergence 가능 — 전체 재생(None)이 안전(문서화) ③ 재생 검증은 `verify_rcl_log_or_halt` «직후» 가 아니라 엔진·게이트웨이·inbox 결선 후(순서 요건 «RCL 검증 뒤» 는 충족) ④ `EvaluationConfig.bindings` 는 모든 로드 전략에서 빈 값(bindings 설정 표면 부재 · 후속 웨이브) ⑤ 파일도 주입도 없으면 기존 빈 레지스트리 폴백 유지(compose 기본값 호환 — 리뷰 판정 요청: «전략 0 = 런타임 없음» 규칙과 충돌하는지) ⑥ `test_driver.py:171` 이 결정론 대조를 위해 `core.handle` 을 직접 1회 호출(핀 허용 범위 밖 · 리뷰 판정 요청).

**독립 실측(최종 트리 `1d58b02c`)**: runtime **539 passed** rc=0 · kernel **9236 passed** rc=0 · mypy 256/62 clean · ruff 0 · black 956 unchanged · firewall PASS · lint-imports 3 KEPT · budget 0 위반(31 등재 · `_wiring.py` 1116→1172) · completion GREEN · spec PASS · contract PASS · tos-spec/계약 문서 무편집 · 커널 diff 는 A-K/D-K 커밋에만.

### 7.2 웨이브 1 독립 리뷰 처분 (Claude 측 `code-reviewer` 레인 · 저작자와 분리 · 2026-09-09)

1차 verdict **needs-attention**(HIGH 4 · MEDIUM 6 · LOW 7) · 게이트 전부 재현 · 뮤테이션 M1~M10 생존 0(단 M1/M5/M6/M7 은 런타임 스위트가 못 봄 — #17) · 커널 diff 귀속 clean.

| # | 심각도 | 지적 | 처분 |
|---|---|---|---|
| 1 | HIGH | 재생이 `outcome_digest` None↔None(모든 EGRESS_RESULT)을 `INCONCLUSIVE`=divergence 로 판정 → 첫 send 후 재부팅 영구 실패(compose 프로브 실증) | 수용 — R2A-#1: None/None 은 «식별자 없음»(uncompared) · 비대칭·DIVERGED 만 divergence · EGRESS_RESULT 포함 재생 테스트 |
| 2 | HIGH | 재생 코어가 실 stage 를 받아 IAP 소비·ARE/AFG 결정·RCL append 를 재실행(증거 카운트 +2 실측) | 수용 — R2A-#2: 재생 코어는 부작용 0 stand-in stage(전 step UNKNOWN) · pipeline digest 는 flow 이전 산출임을 테스트로 실증 · 도크스트링 정정 |
| 3 | HIGH | `core.handle`~`EVENT_CONSUMED` 사이 크래시 → 재기동 시 같은 attempt 재전송(프로브: transport 2회) · 해당 테스트는 handle 을 호출조차 안 함 | 수용 — R2A-#3: write-ahead `EVENT_HANDLING_STARTED` 마커 · 마커 있고 CONSUMED 없으면 재처리 금지 + `HANDLING_INTERRUPTED_POSSIBLY_LIVE` · send 경계 증거가 있으면 `record_halt`. 잔여: 빈 인메모리 원장의 보수 재구성은 설계 #31 §9-7(Phase 5) |
| 4 | HIGH | REJECT→늦은 FULL_FILL · FULL_FILL→늦은 PARTIAL 이 `_store` 비회생 가드에서 raise(§15.2 «valid later fill accepted» 위반 · A-K-2 가 catch 제거) | 수용 — K2-#4: `ResultDisposition.NON_MONOTONIC_PROJECTION`(투영 불변 · 사실은 증거에 보존 · 해소는 recon/Phase 5) · raise 경로 0 |
| 5 | MEDIUM | `filled_quantity` 하향 역행이 APPLIED(4→1) | 수용 — K2-#5: `QUANTITY_REGRESSION` 비적용 처분 |
| 6 | MEDIUM | DUPLICATE 가 드라이버가 매번 새로 찍는 reference 를 포함해 실제 브로커 재전송을 못 잡음(§15.3 정체 아님) | 수용 — K2-#6: `broker_execution_id` 추가 · 서명에서 reference 제외 · 합성 transport 의 결정론 execution id 는 K2 보고 후 라우팅 |
| 7 | MEDIUM | 다른 attempt 의 결과가 타임아웃 감시를 지움(프로브: TIMEOUT 미주입) | 수용 — R2A-#7: APPLIED 이고 tracked attempt 일 때만 해제 |
| 8 | MEDIUM | 편차 ⑤ = fail-open: 소스 부재 시 빈 레지스트리 부팅(로더의 «전략 0 = 시작 안 함» 과 모순) | 수용 — R2D-#8: 부재 ⇒ 거부 · `allow_no_strategies=True` 명시 옵트아웃 + 증거 |
| 9 | MEDIUM | 편차 ④: `config` 소스 ref 가 빈 bindings 로 조용히 무력(UNKNOWN→False) — 권장 저작 형태가 정확히 no-op | 수용 — R2D-#9: lowering 으로 `config` ref 검출 시 로드 거부 · bindings 표면은 후속 웨이브 |
| 10 | MEDIUM | «typed algebra 는 escape 를 표현 못 한다» 거짓 — `Operand(ref=("ambient","now"))` 구성 가능 · 새 게이트가 실제로 잡음(웨이브 전 in-process 경로가 불안전했음) | 수용 — K2-#10: `Operand` 가 `ref[0]` 을 양성 검증 · 도크스트링 3곳 정정 · 두 게이트 구조 일치 |
| 11 | LOW | replay 도크스트링 None/None «trivially MATCH» 오기 | 수용 — R2A-#1 과 함께 |
| 12 | LOW | 로더 `*.yaml` 만 · `.yml` 조용히 무시 | 수용 — R2D-#12: `.yml` 포함 · 그 외 파일 존재 시 거부 |
| 13 | LOW | `_find_consumed_receipt` 선형 스캔 | 부분 수용 — R2A-#13: 신규 `EVENT_HANDLING_STARTED` 조회는 inbox 열로 O(1) · `EVENT_CONSUMED` 조회는 evidence `entries` 에 event_id 열이 필요해 이연(잔여 ② · 재심 N4 로 문언 정정) |
| 14 | LOW | `max_send_result_wait_ms=None` «fail-closed» 오기(실은 fail-silent) | 수용 — R2A-#14: 비옵션 + 문언 |
| 15 | LOW | 편차 ⑥: 직접 호출 허용이 파일 전체 | 수용 — R2A-#15: 마커 주석 1줄로 축소 |
| 16 | LOW | 두 bound 의 0 처리 불일치 | 수용 — R2A-#16: 양의 정수 규칙 통일 |
| 17 | LOW | 런타임 스위트가 커널 뮤테이션 4종에 눈멂 | 수용 — R2A-#17A(불일치 결과 e2e) · R2D-#17D(escape ref·미지 키·규칙 삭제 digest). 재심 N5: M6(escape-checker 게이트 제거)은 #10 이후 **런타임에서 구성 불가한 입력**이라 런타임 red 가 존재할 수 없음(YAML 은 파서에서 먼저 거부) — 커널 `model_construct`/lowering 우회 핀만이 그 게이트의 테스트다. 후속 라운드가 «없는 테스트» 를 찾지 않도록 여기 기록 |

**처분 착지(11커밋 `c923d15e..b59e7e4e`)**: K2-#4/#5 `c923d15e`(`NON_MONOTONIC_PROJECTION`·`QUANTITY_REGRESSION` — `_store` 전에 판정 · core 무변경) · K2-#6 `29774d88`(`EgressResultPayload.broker_execution_id` · 서명에서 reference 제외 · backtest anti-phantom 필드 집합 테스트 갱신) · K2-#10 `438b5def`(`Operand` 가 `ref[0]∈ADMISSIBLE_CONTEXT_SOURCES` 양성 검증 · pydantic 중첩 재검증으로 `model_construct` 우회 자체가 불가 → 2층 증명은 lowering monkeypatch) · K2-#6b `393f708f`(합성 transport 가 `syn-exec:{attempt}:{kind}` 결정론 id — 합성 정체성임을 명시 · §15.3) · R2D-#8/#12 `c3279fbc`(부재 ⇒ 거부 · `allow_no_strategies` 옵트아웃 + `STRATEGY_SOURCE_ABSENT_BY_OPERATOR_CHOICE` 증거 · `.yml` + stray 거부 · 폴백 의존 호출처 0) · R2D-#9/#17D `396b8972`(`config` ref + 빈 bindings ⇒ 로드 거부 · D-lane 런타임 단언 3) · R2A-#3 `9dd30561`(write-ahead `EVENT_HANDLING_STARTED` · 마커 有/CONSUMED 無 ⇒ 재처리 금지 + `HANDLING_INTERRUPTED_POSSIBLY_LIVE_SEND` halt · inbox 열로 O(1)) · R2A-#1/#11 `50ba0e7e`(None/None = uncompared) · R2A-#2 `f497104d`(`_ReplayStage` 부작용 0 · pipeline digest 가 flow 이전 산출임을 소스+테스트로 실증 · #1 만으로는 #2 미해결 실증) · R2A-#7/#14/#16 `fa21c3bd` · R2A-#13/#15/#17A `b59e7e4e`(`EVENT_CONSUMED` 선형 스캔은 evidence 테이블 열 필요 — 파일 소유 밖 · 공개 잔여).

**잔여(공개)**: ① 재기동 후 possibly-live attempt 의 인메모리 원장 보수 재구성 = 설계 #31 §9-7 / Phase 5 ② `EVENT_CONSUMED` 조회 인덱스는 evidence store 열 추가 필요(다음 웨이브) ③ 드라이버 커밋 분할이 `driver.py`/`inbox.py`/`test_driver.py` 를 #3 커밋에 함께 실음(시그니처 공유 · 메시지에 명시).

**독립 실측(최종 트리 `b59e7e4e`)**: runtime **556 passed** rc=0 · kernel **9266 passed** rc=0 · mypy 256/62 clean · ruff 0 · black 957 unchanged · firewall PASS · lint-imports 3 KEPT · budget 0 위반(31 등재) · completion GREEN · spec PASS · contract PASS · tos-spec/계약 문서 무편집 · 커널 편집 커밋 = K2 4건뿐(`git log -- tos/src/`).

### 7.3 웨이브 1 재심 (2026-09-09 · 같은 리뷰어)

verdict **approve** — 17건 중 15 완전 종결 · #13/#17 부분(정직 공개) · 프로브 재실행: 3부팅 통과(`total_compared=2 uncompared=1` — 비공허) · 재부팅 증거 delta 0(`RCL_APPEND` +1 은 writer-epoch fence, 빈 inbox 대조군으로 실증) · 크래시 후 재기동 send 0 + 이중 경로 HALT · rank/수량 역행 byte-identical · foreign 결과에도 TIMEOUT 주입 · 부재 거부/옵트아웃 증거 · `config` ref 거부가 파일+경로 명명 · `Operand` 이웃 5종 거부. 뮤테이션 21종 생존 2 — 둘 다 현 불변식 하 동치(M2: 마킹 누락은 다음 반복의 크래시 창 1 분기가 즉시 복구 · M20: attempt_id 검사는 APPLIED 가 포섭 · release 경로가 생기는 Phase 5 에 핀 필요). 커널 편집 4커밋 귀속 clean · 동결 표면 무편집 · 신규 리터럴/재시도/삼킴 0.

신규 관찰(LOW 5) 처분: **N1** 마커 기록 후 `core.handle` 전 크래시 ⇒ tick 이 `HANDLING_INTERRUPTED_POSSIBLY_LIVE` 로 소비 표시되며 영영 평가되지 않음(보수적이나 무음 · 이름도 «possibly live» 오기) → 웨이브 2 C-R: halt 사유 분리(`HANDLING_INTERRUPTED_NO_SEND_EVIDENCE`) + 비-halt 증거 행으로 가시화 · **N2** `remaining_quantity` 비회생 규칙 없음(4/6→4/60 APPLIED · 대칭 축소 방향이 비보수) → 웨이브 2 K: `QUANTITY_REGRESSION` 을 remaining 축소에도 적용 · **N3** `_send_evidence_exists_after` 가 event 가 아니라 `seq >` 로 조회 — 단일 스레드 드라이버 불변식에 의존 → 웨이브 2 C-R: 불변식 주석 + 동시성 핀 · **N4** §7.2 #13 행 과대 → 위 정정 · **N5** #17 잔여 사유 기록 → 위 정정.

**웨이브 1 종결 → 웨이브 2 착수(2026-09-09).**

### 7.4 웨이브 2 착지 (2026-09-09 · 9커밋 `c592c8a2..0c909e34` · 레인 3 병렬)

| 레인 | 커밋 | 내용 |
|---|---|---|
| K-W2 | `4d5d6424` `0e8af064` `9b18130d` | `CoordinatorPreconditions(Protocol)` + `EngineCore(preconditions=, transport_nature=)` 필수(순환 import 로 `TransportNatureLike` 구조 Protocol · 게이트는 `_handle_decision_tick` 최상단 · 양성 `is True` 중첩 — 엔진 폴라리티 캐너리 준수 · 백테스트는 `SyntheticNonLivePreconditions`(authority 주입 · `NonBrokerTransportNature`)) · `EgressResultKind` += `CANCEL_ACK`·`EXPIRED`(운영자 비준 ① · capacity 최대 `RELEASE_PENDING_PROOF` · cancel-crossing-fill 은 `NON_MONOTONIC_PROJECTION` 으로 사실 보존 — 실 RCL 의 §15.2 수용은 Phase 5) · N2 `QUANTITY_REGRESSION` 을 remaining 축에 확장(`_quantity_regressed` 분리) · `engine/orthostate_projection.py`(`result_transition_for` 8종 사상: CANCEL_ACK→`CANCEL_PENDING`(ADR-002-002 §16.2 문언) · attempt 는 `ACK_OBSERVED`(SUPERSEDED 는 다른 attempt 로의 대체) · Knowledge `RECONCILED` 는 어떤 결과도 주장 안 함) · `tos.engine` 폐쇄에 `tos.orthostate` 추가(역방향 불가 확인 · 형제 캐너리 4곳 갱신) · KW2-C3 내용은 C1/C2 에 흡수(별 커밋 없음) |
| B-R | `df77c147` `cd1de003` | `compose/_preconditions.py::RuntimeCoordinatorPreconditions`(epoch 는 `SafetyAuthorityEpochService.epoch_current` 위임 · live scope 는 커널 `liveauth.is_live`(현 NOT_AUTHORIZED 자세에서 구조적 False) ∧ `reaches_broker is False`) · `_ReplayPreconditions`(True/True · 재생은 같은 파이프라인 경로 비교) · 신규 `coordinator_preconditions.example.yaml`(«NOT_AUTHORIZED» 만 수용 · 좌표 비붕괴 원칙으로 별 파일) · `_engine_wiring.py` 두 `EngineCore(` 결선 · 테스트 픽스처 `_AlwaysPermissivePreconditions`(드라이버/재생 테스트 전용) |
| C-R | `c592c8a2` `028e45be` `9037d29f` `0c909e34` | N1: `HANDLING_INTERRUPTED_NO_SEND_EVIDENCE` + 비-halt `DECISION_TICK_DROPPED_ON_RECOVERY` 가시화 · N3: 불변식 주석 + `_draining` 재진입 가드(transmit 안에서 발화 — 시퀀서가 transmit 예외를 `TRANSMIT_RAISED` 로 접기 때문) · `OrthostateProjector`(APPLIED 결과만 · `coupling_violations` 위반 ⇒ 증거+halt · 3 고정 actor 로 `may_transition` 방어 · inbox `attempt_composites` 측 테이블 · 재기동 `reconstruct_conservative`) · `SyntheticFinalityProducer`(FULL_FILL 만 · `ORDER_FQP` 단일 차원 · `RECEIPT` 수량 leg — 가격 없음 정직 한계 · `finality.example.yaml` 4값 null) · `rcl/finality_witness.py`(`finality_witness_for` + `release_reservation` 시임 · **release 트리거 호출처는 런타임에 아직 0** — Phase 5) · CR-4: 드라이버 필수 인자화 + compose 결선 + e2e · **결선 중 실버그 2건 발견·수리**: ① 투영기가 `result_disposition` 을 안 봐 non-APPLIED 결과를 다른 attempt 에 오귀속 ② `coupling_violations` 를 부대조건 없이 호출해 CPL-6(authority epoch 현행)이 모든 hand-off 를 위반으로 판정 → `authority_epoch_current` 콜백을 투영기에 주입 |

**공개 잔여**: ① `finality_witness` 를 소비해 RELEASED 전이를 트리거하는 호출처 없음(Phase 5 release-trigger 레인 · 증거·측 테이블에 durable 보존까지가 이 웨이브) ② cancel-crossing-fill 의 실 수용(§15.2)은 권위 RCL 소관 ③ 크기 예외 +2(`_finalize` 101 · `wire_engine_and_driver` 103).

**독립 실측(최종 트리 `0c909e34`)**: runtime **614 passed** rc=0 · kernel **9327 passed** rc=0 · mypy 257/68 clean · ruff 0 · black 972 unchanged · firewall PASS · lint-imports 3 KEPT · budget 0 위반(33 등재) · completion GREEN · spec PASS · contract PASS · tos-spec/계약 문서 무편집 · 커널 편집 커밋 = K-W2 3건뿐.

### 7.5 웨이브 2 독립 리뷰 처분 (Claude 측 `code-reviewer` 레인 · 저작자와 분리 · 2026-09-09)

1차 verdict **needs-attention**(HIGH 2 · MEDIUM 6 · LOW 5) · 게이트 전부 재현 · 요청 뮤테이션 M1~M10 전부 red · 리뷰어 추가 M11(`reconstruct_conservative` 제거)·M12(소유권 검사 제거) **green** = #4/#5 근거 · 커널 귀속 clean · 무결함 렌즈: 게이트는 send 경계까지 실증 · `reaches_broker=None` 거부 · 결선 중 저작자 발견 버그 2건 공개 · finality 정직성 · 폐쇄 확장 5캐너리 문서화 · 8종 사상 결정 전부 스펙 문언 인용.

| # | 심각도 | 지적 | 처분 |
|---|---|---|---|
| 1 | HIGH | 게이트가 거부한 tick(receipt `outcome_digest=None`+halt) 을 재생이 True/True 전제조건으로 실행해 비대칭 divergence → 다음 부팅 영구 실패(compose 프로브 실증 · epoch 로그 sqlite 오류만으로도 도달) | 수용 — CR2-#1: halt 사유 있는 receipt 는 `uncompared`(사유 기록) · 사유 없는 비대칭은 여전히 divergence |
| 2 | HIGH | 적용된 UNKNOWN/TIMEOUT 마다 CPL-5 허위 critical halt — 엔진 투영이 `QUARANTINED_UNKNOWN` 을 표현 못 함(ADR-002-005 §7 «UNKNOWN forces QUARANTINED_UNKNOWN») · 기존 커널 테스트는 어떤 결과도 만들 수 없는 composite 를 손으로 저작 | **결정: 스펙 측이 옳다** — KW2b-#2: 투영에 `QUARANTINED_UNKNOWN`(POTENTIALLY_LIVE 보다 보수) + 닫힌 «격리 해소 edge»(양성 브로커 증거만 · §18.6/§15.2 · 해소≠회생) · 8종 sweep 테스트로 대체 |
| 3 | MEDIUM | 결합/소유권 «halt» 가 아무것도 막지 않음(소비자 0 · ADR-002-005 §10 «immediate new-risk halt») | 수용 — CR2-#3: durable new-risk 래치 · 이후 DECISION_TICK 거부(`NEW_RISK_HALTED_BY_COUPLING_VIOLATION`) · 결과는 계속 소비 · 해제는 Phase 5 |
| 4 | MEDIUM | `_check_ownership` 사문(고정 actor 로 2차원 무조건 True · attempt 는 prep 영역만 거부 가능) — M12 green | 수용 — CR2-#4: 동어반복 2건 제거 · attempt 영역 검사 유지 + 실패 가능한 테스트 |
| 5 | MEDIUM | `reconstruct_conservative` 무효과(기록 composite 는 매번 신규 파생) — M11 green · 도크스트링 «보수 재개» 과대 | 수용 — CR2-#5: 재개 composite 가 보수 prior 를 상속(불가하면 STOP·보고) |
| 6 | MEDIUM | FULL_FILL 한정이 생산자 분기뿐 · 커널 술어 3종은 PARTIAL 증거도 통과(M6) | 수용 — CR2-#6: `remaining_quantity == 0` 양성 전제 |
| 7 | MEDIUM | `authority_epoch_current` 가 floor 를 claim 으로 되먹여 `floor >= floor` 동어반복 — stale 감지 불가 · CPL-6 에 그대로 공급 · 읽기 2회 TOCTOU | 수용 — BR2-#7: compose 시 결속 epoch 를 claim 으로 · 단일 읽기 · 결선 도크스트링 정직화 |
| 8 | MEDIUM | cancel-crossing fill 에서 Broker Order 차원 미정정(§7 «corrected») | 수용 — CR2-#8: NON_MONOTONIC + FILL kind ⇒ broker 정정 · knowledge CONFLICTED · capacity 불변 |
| 9 | LOW | «nothing is consumed» 부정확(causal 좌표는 전진) | 수용 — KW2b-#9 문언 |
| 10 | LOW | `_quantity_regressed` 비대칭(4/6→6/5 총량 팽창 APPLIED) | 수용 — KW2b-#10: 첫 결과가 authorized_total 고정 · 이후 합 불변 |
| 11 | LOW | `CouplingSideConditions` 4필드 중 1개만 공급 — CPL-7 구조적 미평가 | 수용 — CR2-#11 도크스트링 |
| 12 | LOW | 작업트리 상태 서술 블록이 프로덕션 소스에 | 수용 — BR2-#12 삭제 |
| 13 | LOW | `RESULT_UNMATCHED` 증거에 수량 없음 | 수용 — KW2b-#13 |

**처분 착지(8커밋 `29bfb7dc..cbf9c4c3` · 레인 3 병렬 · 2026-09-09)**: BR2-#7/#12 `29bfb7dc`(compose 시 결속 epoch 를 `__init__` 에서 1회 포획 → `epoch_current(bound)` 단일 읽기 · STATUS 블록 삭제 · CPL-6 결선 도크스트링 정직화) · KW2b-#2 `f0dc8036`(`PROJECTION_ORDER` 말미 `QUARANTINED_UNKNOWN` — RCL `_CONSERVATISM_RANK` 최상위와 동형 · UNKNOWN/TIMEOUT 전이 명시 · 닫힌 `QUARANTINE_RESOLUTION_EDGES` ACK→POTENTIALLY_LIVE·PARTIAL→PARTIALLY_CONSUMED·FULL→POSITION_CONSUMED·REJECT/CANCEL_ACK/EXPIRED→RELEASE_PENDING_PROOF · UNKNOWN/TIMEOUT 반복은 격리 유지 · 8종 sweep 테스트로 손저작 composite 대체 · 레인 자체 TDD 가 `_store` 의 독립 비회생 가드를 적발 → `allow_quarantine_resolution` 면허 경로만 통과 · 기존 POTENTIALLY_LIVE 핀 5건 갱신) · KW2b-#9/#10 `070b54a2`(문언 정정 · `_last_reference` 전진 위치는 미이동(LOW · 순서 의미 변경이라 보고만) · 수량 불변식 «baseline 이후 filled+remaining 상수·filled 비감소·remaining 비증가» 를 `QUANTITY_REGRESSION` 에 편입 · P4 `4/6→6/5` 거부 · `_resolve_capacity_target` 분리로 예산 내) · KW2b-#13 `dd312a12`(`EngineEvidenceRecord` += `filled_quantity`/`remaining_quantity`/`broker_execution_id` · RESULT_UNMATCHED 와 EGRESS_RESULT_CONSUMED 양쪽) · CR2-#1 `c01c8306`(halt 사유 receipt ⇒ `uncompared` · compose 프로브가 리뷰의 «diverged for 1 of 1» 을 그대로 재현 후 green) · CR2-#6 `503387f7`(`remaining_quantity == 0 ∧ filled > 0` 양성 전제 · M6 재현 후 green) · CR2-#3/#4/#5/#8/#11 `aa7d6e37`(durable new-risk 래치 · 동어반복 소유권 검사 2건 제거 + attempt 영역 검사에 실패 가능 테스트 · 재개 시 Knowledge 만 첫 접촉에 보수 상속 — Attempt 는 양성 증거로 정당히 완화되므로 제외 · cancel-crossing FILL ⇒ broker FILLED 정정 + knowledge CONFLICTED — **CPL-3·CPL-5 를 정당히 발화**(원장/브로커 불일치가 사실이므로 억제하지 않음 · 래치 결합) · CPL-7 미평가 공개) · CR2-#3 `cbf9c4c3`(드라이버가 래치 소비 · DECISION_TICK 거부 `NEW_RISK_HALTED_BY_COUPLING_VIOLATION` · EGRESS_RESULT 는 계속 적용 · TIMEOUT 후 실결선 투영기의 COUPLING_VIOLATION 0 단언 = KW2b-#2 결합 실증). 처분 묶음은 파일 단위(orthostate_projection.py 재작성) — 5:1 대응 아님을 레인이 공개.

**최종 실측(워크트리 `cbf9c4c3` 격리 · 레인 D-R-3 WIP 와 분리)**: 커널 `9347 passed` · 런타임 `626 passed` · mypy 커널 257/런타임 68 clean · ruff/black clean · firewall PASS · lint-imports 3 kept/0 broken · 크기 예산 PASS(36 등록 · 신규 3: `replay_engine` 120·`SyntheticFinalityProducer.produce` 107·`EngineDriver._process_next` 121 · owner tos-runtime · expires 2026-12-31) · completion GREEN · spec PASS · contract PASS · `tos/src` 변경은 KW2b 3커밋에만 · tos-spec/계약 diff 0.

**잔여(공개)**: ① `_last_reference` 전진이 Coordinator 게이트 앞에 있음(LOW · 순서 의미 · 재심 판정 요청) ② cancel-crossing 정정이 CPL-3/CPL-5 를 발화해 래치가 걸림 — 해제는 Phase 5 ③ 웨이브 1 편차 ④(bindings 표면)는 레인 D-R-3 로 별도 진행 중(재심 범위 밖 · 착지 후 웨이브 3 리뷰에 편입).

### 7.6 웨이브 2 재심 (2026-09-09 · 같은 리뷰어 · 범위 `29bfb7dc..cbf9c4c3`) + 웨이브 1 편차 ④ 종결(D-R-3)

**재심 verdict: needs-attention.** 원 13건은 전부 종결(1차 생존 뮤테이션 M11·M12 모두 red · 16종 뮤테이션 생존 0 · 게이트 전부 독립 재현 · #9 `_last_reference` 전진 위치 «그대로 둔다» 판정 확정 · #8 «CPL-3/CPL-5 발화가 옳다» 도전 후 유지). 처분 2건이 같은 부류의 신규 결함을 도입 — 둘 다 end-to-end 실증:

| # | 심각도 | 지적 | 처분 |
|---|---|---|---|
| R1 | HIGH | #3 래치 사유 `NEW_RISK_HALTED_BY_COUPLING_VIOLATION` 가 `_PRE_PIPELINE_HALT_REASONS`(`replay.py:127-152`, 커널 enum 5종만) 에 없음 → 래치 거부 tick(`core.handle` 미호출 · `outcome_digest=None`) 을 재생이 전체 파이프라인으로 돌려 #1 과 동일한 비대칭 divergence → compose 프로브: cancel-crossing 체결 → 래치 → 다음 tick 거부 → 재부팅 «diverged for 1 of 3» 브릭 · 래치 해제 경로 0 | 수용 — CR3-R1: 사유 집합에 편입 · 상수 의미를 «파이프라인이 구조적으로 실행되지 않은 사유» 로 재정의(닫힌 집합 유지) · 단위 핀 + compose 재구성 테스트(리뷰 시나리오 그대로) |
| R2 | HIGH | `QUARANTINE_RESOLUTION_EDGES` 가 rank **하강**을 무제한 면허 — `_resolve_capacity_target`(`state.py:532-565`) 이 격리 전 rank 바닥 없이 표 목표를 반환 · 실증: FULL_FILL→POSITION_CONSUMED → TIMEOUT → ACK ⇒ POTENTIALLY_LIVE (filled=1 rem=0 기록 유지) · REJECT/PARTIAL 도 동일 · 실 드라이버+투영기에서 COUPLING_VIOLATION 0·래치 0·증거 0 = 완전 무음 · 수량 가드는 fill kind 만 잡음 | 수용 — KW2c-R2: 격리 진입 시 `pre_quarantine_capacity` 를 예약에 기록(첫 진입만) · 해소 목표 = max(격리 전 rank, 표 목표 rank) — «격리 탈출에는 증거가 필요» 는 탈출 면허이지 이미 증명된 정산의 되감기 면허가 아님 · 시퀀스 테스트 6종 · N2 의 표-멤버십 단언을 행동 테스트로 보강 |
| R3 | MEDIUM | 래치가 런타임 전역·단일·durable·해제 불가인데 #8 이 스펙상 «루틴» 브로커 경합(cancel-crossing · ADR-002-005 §7 / ADR-002-002 §15.2 «accepted»)에서 이를 발화 → 정상 경로의 영구 정지 · 정책 결정 필요 | **결정(세션)**: 래치는 유지(원장/브로커 불일치 = 미지 노출 · 새 위험 정지는 옳다) · 운영자 재무장을 **Phase 5 이연 대신 지금 착지** — CR3-R3: `SqliteEventInbox.clear_new_risk_halt(latched_evidence_seq, operator_attestation)`(seq 일치 시만 · stale clear 불가 · 빈 attestation 거부) · compose root 노출 · 해제 전 `NEW_RISK_HALT_CLEARED_BY_OPERATOR` 증거 선기록(seq·사유·attestation sha256) · 자동 해제 0 · **운영자 확인 항목 ⑤**: 이 정책(전역 래치 + 명시 재무장)을 승인하거나 대안(instrument 단위 래치 / 기록만·래치 없음)으로 변경 |
| R4 | LOW | 래치 순서 창: 위반 EGRESS_RESULT 보다 낮은 seq 의 DECISION_TICK 은 래치 생성 전에 처리(`driver.py:600-680` 구조 판독 · at-most-one 노출 보존 + 단일 InstrumentKey 로 현 구성에서는 도달 불가) | 수용 — CR3-R4 도크스트링(경계 잔여) · 둘째 instrument 또는 보존 완화 시 실결함 |
| 잔여 | — | 결속 epoch 를 compose 시 1회 포획 → epoch 전이 전에 구성된 런타임은 평생 거부(현 compose 는 `_boot_services` 에서 전이 후 `_finalize` — 도달 불가 · 거부는 uncompared 라 브릭 없음) — 구성 순서에 대한 신규 liveness 의존 | 수용 — CR3-R4: `_preconditions.py` 도크스트링 1문단 |

리뷰어 무결함 렌즈(발췌): #6 은 `_ELIGIBLE_KINDS` 를 테스트 안에서 넓혀도 전제가 잡는 캐너리 · #1 은 레인 자체 실측이 «모든 halt = uncompared» 초안의 false-green 을 적발해 좁힘 · #8 은 위반을 억제하지 않고 실 술어로 검증 · 1차 프로브 2건이 회귀 테스트로 출하.

**D-R-3 착지(3커밋 `61cc0688`·`5de238d3`·`e4793c32` · 웨이브 1 편차 ④ / #9 종결 · 2026-09-09)**: `tos_runtime/strategy/bindings.py`(`config_dir/strategy_bindings.yaml` · `strategies/` 형제 · 부재는 typed `present=False` · extra=forbid · null leaf 거부 · sha256) · `resolve.py` 5규칙 양성 판정(항목 부재 / 버전 불일치 / 미해소 경로 / 미사용 키=드리프트 / 고아 항목 — 전부 `_refuse` 경유 STRATEGY_REFUSED) · 커널 `EvaluationConfig.bindings` 는 평면 `dict[str, ScalarValue]` 이므로 YAML 도 평면(ref = `[config, key]` 뿐 · 커널 무확장) · 검출은 lowering 대신 typed policy 직접 순회(정확한 ref 경로 회수 · `tos.dsl.lowering/candidate` 의존 제거) · `_boot_integrity.record_operator_attested_inputs(loaded_bindings=)` 로 digest 합류 · `evaluate_policy` 로 규칙이 실제 발화함을 실증(#9 «inert strategy» 종결) · RED: 버전 검사 제거 ⇒ `test_version_mismatch_refuses_naming_both_values` 만 red(45 green) · `resolve_strategy_registry` 107→88(순수 추출) · `_wiring.py` 1203→1205 등록. **최종 실측(워크트리 `e4793c32` 격리)**: 커널 9347 · 런타임 644 · mypy 69 clean · ruff/black/firewall/lint-imports/예산(36)/completion 전부 PASS · `tos/src` diff 0. 독립 리뷰 레인 `review-dr3` 별도 진행(§7.7 에 기록).

### 7.7 재심 R1~R4 처분 착지 + D-R-3 리뷰·처분 착지 (2026-09-09 · `6a130f7c..e47a437e`)

**R1~R4 처분(레인 K-W2b · C-R2 병렬)**: KW2c-R2 `6a130f7c`(`ProvisionalReservation.pre_quarantine_capacity` — QUARANTINED_UNKNOWN 일 때만 non-None · 첫 진입에 기록·반복 TIMEOUT/UNKNOWN 은 덮지 않음·해소 시 소거 · `_resolve_capacity_target` 이 표 목표를 **최소값**으로 취급 = max(격리 전 rank, 표 목표) · RED 6 → GREEN · «바닥 제거» 뮤테이션 5건 red · 정직 보고: N2 의 표-멤버십 핀은 여전히 load-bearing — UNKNOWN/TIMEOUT 이 표에 추가되면 막을 독립 가드 없음) · CR3-R1 `b9e382af`(집합 `_PIPELINE_NEVER_RAN_HALT_REASONS` 로 개명·래치 사유 편입 · 단위 핀 + compose `TestRecomposeReplay` 재구성 테스트 — 리뷰 프로브 «diverged for 1 of 3» 를 RED 로 재현) · CR3-R3 `ad89d50f`+`8f44a852`(`SqliteEventInbox.clear_new_risk_halt(latched_evidence_seq, operator_attestation)` — seq 일치·attestation 비어있지 않음을 저장층에서도 재검증 · `ComposedRuntime.clear_new_risk_halt` 가 `NEW_RISK_HALT_CLEARED_BY_OPERATOR` 증거(seq·사유·attestation sha256)를 **해제 전** 기록 · 테스트 4: 올바른 seq ⇒ 다음 DECISION_TICK 진행+증거 / stale seq 거부·래치 유지·증거 0 / 빈·공백 attestation 거부 / 해제 후 재위반은 새 seq·옛 seq 로 해제 불가) · CR3-R4 = **`4b4aebdf`**(`driver.py::_process_next` 순서 창 잔여 + `_preconditions.py` 결속 epoch liveness 문단 + `_process_next` 예산 121→139 재등록).

**공유 인덱스 경합 4차(경위 기록 · 히스토리 무수정)**: C-R2 가 R4 헝크 3파일을 스테이징한 사이 D-R 이 pathspec 없는 커밋을 실행 → C-R2 의 내용이 D-R 메시지 «[D-R-3d-#1/#2]» 로 `4b4aebdf` 에 실림. 손실 0 · D-R 의 실제 #1/#2 는 `81563e91` 로 재착지(메시지에 경위) · 두 리뷰어가 tip 을 측정 중이라 rewrite 하지 않음. 확정 규칙: 전용 파일 = pathspec 커밋 · 공유 헝크 = `add -p` + 무pathspec 커밋을 **한 번에 한 레인**(오케스트레이터 직렬화) · 혼합 금지.

**D-R-3 독립 리뷰(`review-dr3` · 저작자와 분리)**: verdict needs-attention · 실결함 0 · 뮤테이션 12종 중 생존 1(i: `except` 에서 `StrategyBindingsLoadError` 제거 — 644 전부 green). MEDIUM 2: ① i 경로 미핀 ② `_config_ref_paths` 가 커널 `iter_outcome_gating_compares`/`operand_source` 를 손순회로 중복(DRY · 완전성이 도크스트링 주장) · LOW 5: ③ `.yaml`/`.yml` 같은 stem 이 bindings 항목 공유 ④ 비파일 소스 경로에서 bindings 파일 무시 ⑤ compose 테스트의 파일명 리터럴 ⑥ 맨 `("config",)` ref 미테스트(동작은 정확) ⑦ `_first_null_leaf` 사설 교차 임포트. 무결함 렌즈: inert-rule 종결이 load-bearing(뮤테이션 c) · 규칙 3 이 `resolve_operand` 를 단계별 미러 · 규칙 4 가 zero-ref 를 특례 없이 포섭 · 스칼라 충실도(0/1 이 bool 로 강제되지 않음) 확인.

**D-R-3d 처분(`81563e91` · `e47a437e`)**: ① 리뷰어 테스트 채택 — 뮤테이션 i killed ② 커널 열거자 위임 ③ `_refuse_stem_collisions`(둘 다 명명·증거) ④ **결정**: 비파일 경로의 bindings 파일 존재는 거부 — 주입 레지스트리 = «소스 하나만» 위반 · `allow_no_strategies` = 전 항목 고아 · 부재는 무영향 · `_resolve_injected_registry` 추출로 예산 내 ⑤ 상수 임포트 ⑥ 규칙 3 테스트 확장 ⑦ `first_null_leaf` 개명(`__all__` 밖).

**최종 실측(워크트리 `e47a437e` 격리)**: 커널 `9355 passed` · 런타임 `655 passed` · mypy 257/69 clean · ruff/black clean · firewall PASS · lint-imports 3/0 · 예산 PASS(36) · completion GREEN · spec PASS · contract PASS · `tos/src` 변경은 `6a130f7c` 에만 · spec/계약 diff 0. 재심 #2(`review-p3w2` · R1~R4) 와 D-R-3d 재심(`review-dr3`) 병렬 진행 중 — 결과는 §7.8.

### 7.8 재심 #2 approve + D-R-3d 재심 approve (2026-09-09) → 웨이브 3 착수

**웨이브 2 재심 #2(`review-p3w2` · R1~R4)**: **approve**. R1 compose 체인 재부팅 통과·래치가 재부팅을 생존 · R2 바닥이 8 시퀀스·24 스텝에서 불변식 유지(표 값 = 최소값이라 ACK 특례 없음) · R3 증거가 상태 변경에 선행·모든 거부 경로가 래치 유지+증거 0 · R4 `4b4aebdf` 는 도크스트링 2파일 + 정확한 예산 재등록(139=실측). N2 판정: **표-멤버십 핀 수용**(닫힌 선언 표·단일 소비자 — 우회 경로 없음 · 행동 테스트는 출하 코드로 작성 불가) + 권고: 두 이름의 부재 단언 대신 **파생 양성 불변식**(표 키 집합 = `EgressResultKind` − `_RESULT_TRANSITIONS` 목표가 QUARANTINED_UNKNOWN 인 kind) 으로 재서술해 어휘 성장에 닫히게. 신규 잔여 4(비차단): RR1 MEDIUM 저장층 attestation/seq 가드 미테스트(MR3c 생존 · 래퍼가 먼저 거르므로) · RR2 MEDIUM 문이 둘 — `inbox.clear_new_risk_halt` 직접 호출은 증거 0 으로 해제(올바른 seq 필요 · 드라이버 도크스트링에 공개) → `test_no_direct_core_calls.py` 식 기계 핀 · RR3 LOW 거부된 해제가 흔적 없음(`False` 4가지 사유 구분 불가) → 시도-거부 증거 행 또는 typed 사유 · RR4 LOW 해소 후 반복 TIMEOUT 은 DUPLICATE 서명 동일로 재격리 불가(UNKNOWN 은 가능 · 드라이버는 attempt 당 TIMEOUT 1회라 현 구성 도달 불가 · 서명에 해소 세대 반영은 이 웨이브 밖 — 기록만).

**D-R-3d 재심(`review-dr3`)**: **approve**. 뮤테이션 17종 생존 0(i·m·n·o·p 포함) · 7건 전부 행동 테스트로 종결 · 크기 예외 추가 0. 비차단 관찰: presence 검사 3중(`is_file`) — 디렉터리명 `strategy_bindings.yaml` 은 일관되게 «부재» · 주입 레지스트리 경로가 이제 파일 I/O(의도된 fail-closed 확장 · 계약 변경 공개). 프로세스: 리뷰어 둘이 같은 측정 워크트리를 써 상대 프로브가 섞임 → **리뷰어별 워크트리 분리**를 규율에 추가.

**착수(웨이브 3 · 병렬 5 + 후행 1)**: E-K(커널 calibration) · F-K(19-step 뮤테이션 매트릭스) · F-R(패리티 + blind resubmit 0) · CR4-RR(RR1/RR2/RR3 — 저장층 단위 테스트 2 · 직접 호출 기계 핀 · typed 거부 사유+시도-거부 증거) · KW2d-N2(파생 불변식 재서술) · E-R 은 `[E-K-done]` 후. 규율 추가: 전용 파일 = pathspec 커밋 · 공유 헝크 = 오케스트레이터 직렬화 · 리뷰어별 워크트리.

### 7.9 웨이브 3 착지 기록 (2026-09-09 · 진행 중 · `1fd45668..e23e9b68` 21커밋 · 레인 8)

**§3.1 정정(저작자)**: «`BacktestResult` 의 expectancy 필드» 는 오기 — D-E3 §1.2 B1 봉인(`PERFORMANCE_SURFACE_TOKENS` ∋ "expectancy" · 런 레코드 구성마다 `seal_performance_surface` · 거버넌스 테스트 `test_the_seal_catches_every_planted_performance_name["expectancy"]`)과 정면 충돌. E-K 가 STOP·에스컬레이션. **결정 (c)**: 클레임은 봉인된 런 레코드 밖의 별도 산출물(`ExpectancyClaim`) — 이름을 바꾼 필드도 성과 표면이므로 (b) 는 봉인 회피. `tos.backtest.calibration` 은 패키지 `__init__` 에서 재수출하지 않음(드리프트 캐너리 유지 · 핀 2). §3.1 의 «인접 교환 13쌍» 도 오기 — 19-step 은 18쌍. `EGRESS_RESULT_RECORDED` 는 실제 kind `EGRESS_RESULT_CONSUMED`. `fill_ratio` 는 몫이 아니라 shortfall magnitude(커널 프레이밍 승리 · E-R-3).

| 레인 | 커밋 | 내용 |
|---|---|---|
| KW2d-N2 | `1fd45668` | 격리 해소 표 = `EgressResultKind` − {QUARANTINED_UNKNOWN 목표 kind} 파생 불변식 + 값은 전부 격리 아래 rank |
| E-K | `3a8421ef` `7ecae367` | `backtest/calibration.py`: `FillDeviation`(None 차원 = 관측 불가 ≠ 0) · `DeviationBudget`(전 필드 필수) · `CalibrationVerdict` INSUFFICIENT>EXCEEDED>WITHIN · 관측 0 ⇒ INSUFFICIENT(min 0 이어도) · `ExpectancyClaim`/`claim_expectancy`(WITHIN 만 값) · 31 테스트 · 뮤테이션 2종 red · import-closure 캐너리 등록(공개 편차) |
| E-R | `8e29dfe8` `02f67546` `8fd81751` | `tos_runtime/backtest/{config,calibration_report}.py` · `backtest_calibration.example.yaml`(null) · `EGRESS_RESULT_CONSUMED` 행 ↔ `LocalFillRecord` 를 **attempt_id 단독**으로 짝짓기(양쪽 다 strategy_digest 부재 — 한계 공개) · evidence store 에 typed 읽기 API 부재 → `.connection` 직접(`backup.py` 선례) · payload 는 `{"payload","masked_keys"}` 래퍼(언랩 핀) · `price_bps`/`latency_bars` 항상 None ⇒ 현 런타임은 무조건 INSUFFICIENT(의도된 fail-closed · 가격 표면은 Phase 4/7) · 미짝 attempt 는 카운트만(뮤테이션 «0 편차로 계상» red) · 25 테스트 |
| F-K | `8c587cb9` `ffaafcb4` `c1ea8172` | `test_sequencer_mutation_matrix.py`: 56변형(교환 18·누락 19·중복 19) · 검출기 0 `validate_stage_map` 은 순서 불가시(호스팅 봉인만) · 검출기 1 ADR 앵커 · 검출기 2 `run_commitment_flow` 실행 지문(alias 6종 monkeypatch — `sequencer.SEQUENCED_STEPS` 패치 해제 시 39변형 무음 통과 실증) · 검출기 3 게이트웨이 실송신의 `record.step` 순서(step 15 = 순간 2회 multiplicity) · **생존 0 · 앵커 단독 잔여 12→4→0** · `omit_15` 는 구성 불가(UNREACHABLE) · 0.04s |
| F-R | `71a84b2d` `84bca014` `26d983e6` | 패리티: 같은 전략·같은 Capsule 을 `BacktestDriver` 와 `EngineDriver`+`SqliteEventInbox` 로 → `outcome_digest` 열 동일 · reference/time 은 covered 밖 · 결과 kind 불일치(FULL_FILL vs ACK double)가 None digest 에 가려져 있었음 → 양측 같은 `SyntheticPaperTransport`·같은 수량 주입으로 실일치 + 비공허 단언 · blind resubmit 3 시나리오(유실 TIMEOUT·지연 FULL_FILL·역전 NON_MONOTONIC) transport 호출 1 · 새 attempt 는 `ATTEMPT_REQUEST_CREATED`/`SEND_HANDED_OFF` 증거로 실증 · **발견**: `PROJECTION_ORDER` 에 RELEASED 없음 → 체결된 attempt 가 scope 슬롯 영구 점유 → 둘째 InstrumentKey 로 실증(Phase 5 release-trigger 게이트) |
| CR4 | `8383bd32` `3c08dc38` `afade82f` | RR1 저장층 단위 테스트(MR3c killed) · RR2 grep 핀(`inbox.clear_new_risk_halt(` 는 `compose/_types.py` 밖 금지) · RR3 `NewRiskHaltClearOutcome`{CLEARED,NO_LATCH,EMPTY_ATTESTATION,SEQ_MISMATCH,STORAGE_REFUSED} + 거부마다 `NEW_RISK_HALT_CLEAR_REFUSED` 증거 · 공개: RR1 커밋은 단독 임포트 불가(RR3 enum 의존 · bisect 주의) |
| KW3-RD | `783fadf0` | `EgressResultOutcome`(disposition·capacity·knowledge·수량·격리 전 상태) 정준 digest → `EventResult.outcome_digest` 가 결과 이벤트에도 실값(게이트 거부만 None) · 핀 1 반전(사유 기록) · 뮤테이션 «disposition 제거» red · **드러난 실결함 2**: (A) 재생이 `transmit=None` 코어라 원장이 다른 상태에서 결과 적용 → digest 불일치(런타임 4) (B) 패리티 결과 kind 불일치(1) |
| KW3-GW | `9de02dcc` | `GatewayEvidenceRecord.step: CommitmentStep` 전 기록 스탬프(`FIXED_KIND_STEPS` · SEND_SEALED = step 15 산출 · 열거 폐쇄 유지) · step 18 `NETWORK_CALL_ENTERED` write-ahead(`send_once` 직전 · M-K1/M-K2 핀 유지) · `_halt` 가 step 필수 인자(9 거부 지점) · «step 16»→17 문언 정정 2곳 · 예산 재등록 3(gateway 2007·`__call__` 283·records 1027) |
| CR5 | `a2b72a9a` `badbfaad` `3e2af6cf` `e23e9b68` | `RecordedTransmit`(증거의 SEND_HANDED_OFF 로 로컬 원장 효과만 재현 · 결손 시 `ReplayTransmitEvidenceMissing`) · transport/서비스 임포트 금지 AST 핀 · `RecordedStage` 가 `_ReplayStage`(전 step UNKNOWN → 예약 0 → ORPHAN) 대체: (event, step) 의 기록 verdict 재생 · 기록 거부는 거부로 · `RecordedTransmit` 은 `any_recorded_hand_off` 일 때만 · **발견(커널)**: per-step 증거에 `event_id` 없음(조우 순서 상관 — 창 절단 시 탈동조) · step 9/11 ADMIT 의 `bound_identity`/`bound_digest` 가 증거에 없어 attempt_id 재구성 불가 → compose 재생 테스트 3 `xfail(strict)` 사유 인용 · step 2~14 증거 충분성 표 작성 |

**마감 착지**: KW3-EV `b9447c9d`(`EngineEvidenceRecord` += `event_id`·`bound_identity`·`bound_digest` — covered 집합 없음(plain FrozenModel) · `run_commitment_flow(event_id=)` 가 ATTEMPT_REQUEST_CREATED/FLOW_STEP_ADMITTED/FLOW_HALTED/SEND_HANDED_OFF 전부에 스탬프 · `_bindings_from` 소비 필드 = 정확히 step 11 `bound_digest`·step 9 `bound_identity` · 뮤테이션 2종 red · `_halt` 11개 호출부를 `_stop` 클로저로 추출해 304→298(예산 재등록 `471fc336`)) · CR5-5/6 `48191e9e`·`e3c00a0c`(`RecordedStage` 가 `event_id` 상관 · encounter-order 폴백 삭제(KW3-EV 이전 행 = fail-closed) · step 9/11 bound 값 그대로 재구성 → step 12 가 라이브 attempt_id 도출 · `EventCorrelatingCore` 래퍼(`replay.py` 무수정 · `_engine_wiring` 경계 `cast`) · xfail 3 → XPASS(strict) 확인 후 마커 제거 · 창 절단(`window_events=1`) 정렬 · **변조 bound_identity ⇒ 후속 EGRESS_RESULT divergence** end-to-end 뮤테이션 착지 · `RecordedTransmit` 은 attempt_id 키 그대로 정확).

**최종 실측(워크트리 `e3c00a0c` 격리)**: 커널 `9405 passed` · 런타임 `699 passed`(xfail 0) · mypy 258/74 clean · ruff/black clean · firewall PASS · lint-imports 3/0 · 예산 PASS(37) · completion GREEN · spec PASS · contract PASS · `tos/src` 변경은 K 커밋 6개에만(`3a8421ef`·`7ecae367`·`783fadf0`·`9de02dcc`·`b9447c9d` + 테스트만인 `1fd45668`) · spec/계약 diff 0. 독립 리뷰 `review-p3w3`(전용 워크트리) 진행 중 — 결과는 §7.10.
