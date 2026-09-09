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

1. `EgressResultKind` 에 `CANCEL_ACK`·`EXPIRED` 추가(커널 어휘 확장 · ADR-002-005 §7 정합) — 승인 여부.
2. 이벤트 inbox 를 evidence 와 **별 sqlite 파일**로 두는 것(D3 실패 도메인 분리 준용) — 승인 여부.
3. 작업 4 를 «가격 계보 digest 봉인(커널)» 으로 축소하고 실 값 표면 어댑터는 Phase 4/7 로 — 승인 여부.
4. 신규 설정 키 5종(`max_send_result_wait_ms`·`replay_window_events`·`strategies/` 디렉터리·`backtest_calibration` 예산·`finality` 합성 정책) 의 named-TBD 값 결정은 착지 후.

## 7. 실행 결과·독립 리뷰 처분

(웨이브별 기입)
