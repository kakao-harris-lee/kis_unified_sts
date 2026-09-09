# TOS Phase 4 잔여 계획 — Broker Capability Scope 분해(작업 2) · INSTANCE 소비 · 17항목 6/12 stand-in 대체(작업 5) · G-4 · 종료 조건 배터리

- **상위**: 개발계획 `docs/plans/2026-08-11-tos-completion-development-plan.md` §5(승인된 파생 라우팅 행렬 — 슬라이스 #1 계획 §3-A · 운영자 승인 2026-09-08) · §6 Phase 4 작업 2·3(데이터)·4·5 + 종료 조건 5항 · 슬라이스 #1/#2 계획 · SendSeal 계획 §6.3 잔여(G-4 · R2).
- **선행**: Phase 3 완료(`5802daab`) · 브랜치 `feat/tos-phase4-scopes` 는 `feat/tos-phase3-event-core` 위 스택(스택 PR 은 운영자 수동).
- **저작**: 세션 모델 단독 · **권한 부여 0 · EV 행 상태 변경 0 · 실 브로커 transport 0(합성 유지) · 라이브 권한 0 · P0-2 는 열린 채**.

## 0. 서베이 실측 (2026-09-09 · `5802daab` · 커널/런타임 스위트 green)

| 항목 | 실측 |
|---|---|
| Phase 4 착지 | 작업 1(`brokercap/routing.py` 5축·`CapabilityTuple`·닫힌 whitelist·규칙 4 타입 봉인) · 작업 3 **스키마**(`ProvenanceClass`·`CapabilityProvenance`·`ProbeManifest`) · 작업 6(`egressgw/seal.py` SendSeal) · 작업 7(adapter 1 outbound→1 result negative-grep) |
| Phase 4 미착지 | 작업 2(KIS profile 스코프 분해) · 작업 3 **데이터**(provenance 결속) · 작업 4(P0-2 10키) · 작업 5(17항목 stand-in/deferred 대체) |
| 17항목 현황 | Realize 6(1·2·11·13·16·17) 실 · Provisional 5 중 **3·14·15 는 Phase 2 실 producer**(`CurrentnessAssembler`·IAP stage·`ActionFlowGovernor`) · **6·12 는 운영자 attestation**(`compose/_egress_attestations.py` — 「Phase 4 (P0-2 approved Profile INSTANCE) replaces」 명시) · Deferred 6(4·5·7·8·9·10)은 `NON_BROKER_SYNTHETIC`→N/A, 그 외 UNKNOWN→deny. 4·5 는 런타임 소유자 후보 존재(`tos_runtime/authority/epoch.py` · 커널 `liveauth`) · **7~10 은 런타임 owner 없음(Phase 5 작업 4 소관)** |
| KIS INSTANCE | `docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml` 4,789행 · YAML 2문서(`MOCK_VTS` `KIS-BCP-MOCK-VTS-DRAFT-0001` · `REAL_PROD` `KIS-BCP-REAL-PROD-DRAFT-0001`) · `status: DRAFT` · `approvers: []` · VERIFIED 0 · 각 블록에 `_model_view`(records.py 대응) 병기 · **코드 소비자 0**(런타임 어디도 로드하지 않음) |
| P0-2 10키 | 판본 2종(런북 `docs/runbooks/kis-capability-probes.md` §4.1 — 혼용 금지) · 후보값 3 · 무근거 3(P-8 재실행 5회 대기) · 미실행 1(P-EXT) · 프로브 신설 2(N-19→P-CA) — **전부 운영자 실행(모의 운영 서버)** · `tools/bcp_digest.py` 준비 완료 |
| G-4 | `compose/_wiring.py` `f"synthetic-paper-{environment_label}"` 리터럴 3곳(transport principal · inventory entry) + R2 부팅 거부(`_refuse_active_principal_matching_transport_identity`)가 같은 리터럴을 재생성 |
| 종료 조건 배터리 | 폴백 뮤테이션은 커널 routing 테스트(M1~M3)뿐 · read-only principal→order endpoint 도달 불가는 커널 술어만(런타임 배터리 0) · «config/env 만으로 futures REAL order capability 생성 불가»는 런타임 설정 층 테스트 0 |
| 크기 register | `_wiring.py` 1205 등재(`decomposition_order: 30`) · `egressgw/gateway.py` 2007 등재 · `compose/context.py` 647(미등재·여유) |

## 1. 범위

| 포함 | 제외 (이유) |
|---|---|
| **작업 2** 스코프 4종(`REAL_READ` · `MOCK_STOCK_ORDER` · `SYNTHETIC_FUTURES_ORDER` · `REAL_ORDER`)의 런타임 설정 인스턴스 + 로더 + 커널 `CapabilityTuple`/`routing_admissibility` 결속 · **G-4** transport 정체성·credential-route inventory 를 스코프에서 파생 · **INSTANCE 소비**(draft YAML → 커널 `BrokerCapabilityProfile`) · **작업 3 데이터 절반**(`assurance_sources` → `ProvenanceClass` 결속) · **작업 5 중 6·12**(attestation → 스코프/INSTANCE 파생) · **종료 조건 1~4 배터리** | **작업 4**(P0-2 10키 — 모의 운영 서버 프로브 재실행·Bounds-Approver 기입 = 운영자 레인, §6) · **작업 5 중 deferred 7~10**(envelope/deviation/incident/monitoring 런타임 owner = Phase 5 작업 4) · **deferred 4·5**(§5 웨이브 3 — 웨이브 2 재심 후 착수 여부 결정) · **KIS MOCK transport**(실 I/O 어댑터 — 종료 조건 5 의 전제이나 credential·모의 서버 필요, 별도 계획) · item 16 latch/capacity attestation(Phase 5 명시) · 17 currentness 차원 attestation(Phase 5 명시) |

**정직 귀결**: 종료 조건 5(«broker-consuming mock 경로가 17항목 verify 와 durable evidence 를 통과»)는 이 계획으로 **닫히지 않는다** — 7~10 의 owner 가 Phase 5 이고 KIS MOCK transport 가 없다. 개발계획 Phase 4/5 순서상의 의존 역전(Phase 4 종료 조건이 Phase 5 산출물을 요구)을 §7 에 운영자 확인 지점으로 등재한다.

## 2. 결정

1. **스코프는 런타임 설정 인스턴스, 커널에 KIS 문자열 0.** `tos/runtime/config/broker_scopes.example.yaml` + 로더 `tos_runtime/brokercap/scopes.py`. 각 scope 레코드(frozen dataclass): `name` · `capability_tuples: tuple[CapabilityTuple, ...]`(로더가 커널 **validated 생성** — 규칙 4 로 `BROKER_PRODUCTION`×주문×`FUTURES` 는 설정으로도 생성 불가 = 로더 예외 = 종료 조건 3) · `profile_key: ProfileKey`(10좌표) · `principal_class: {READ, ORDER, SYNTHETIC}` · `principal: str`(`{environment_label}` 치환은 기존 `_egress_coordinates` 와 동일 규칙) · `endpoint_class: {NONE, BROKER_GET, BROKER_ORDER, SYNTHETIC}` · `allowed_methods: tuple[str,...]` · `admissibility: Admissibility`(로더가 `routing_admissibility` 로 스탬프 · 주입 `profile_evidence_ok` 는 스코프 설정의 `profile_evidence_ok: bool|null`) · `provenance: tuple[CapabilityProvenance, ...]`(작업 3 데이터 — `CONTROLLED_GET_PROBE` 는 `ProbeManifest` 필수 · 그 외 None 필수, 커널 validator 그대로).
   - `REAL_ORDER` 스코프는 **등재는 되나 항상 PROHIBITED**(STOCK — 승인 행렬 밖 · FUTURES — 생성 불가). «영구 차단»을 설정 표면에서 가시화하되 어떤 경로도 열지 않는다. 로더는 PROHIBITED 스코프에 `endpoint_class != NONE` 이면 거부하지 않는다(사실 등재) — 대신 **소비자가 없다**는 것을 negative-grep 으로 고정(§4 EC-1).
   - **principal 분리**: READ 와 ORDER principal 이 같으면 로드 거부(커널 `credential_principal_separation_ok`). SYNTHETIC principal 이 다른 클래스와 같아도 거부. `egress_coordinates.active_principal` 과 어떤 scope principal 이 같아도 거부(R2 일반화 — 리터럴 비교를 스코프 비교로 대체).
   - 로더는 `os.environ` 을 읽지 않는다(negative-grep) · 기존 `_egress_coordinates.py` 의 named-TBD null → 부팅 거부 규율 동일.
2. **G-4 는 스코프에서 파생.** `_wiring.py` 의 `TransportNature(principal=f"synthetic-paper-{env}", …)` 와 `CredentialRouteInventoryEntry` 두 건을 `scopes.transport_nature(active_scope)` / `scopes.credential_route_inventory(active_principal)` 파생으로 대체. 활성 스코프는 `compose_paper_runtime` 이 설정 `active_scope: SYNTHETIC_FUTURES_ORDER` 로 지정(named-TBD). `reaches_broker`/`credential_bearing`/`route_bearing`/`risk_relevant_live` 는 `endpoint_class`·`principal_class` 에서 **구조 파생**(SYNTHETIC ⇒ 전부 False · BROKER_* ⇒ True/True/True · risk_relevant_live 는 `authorization_class is REAL_ORDER` 일 때만 True). R2 부팅 거부는 리터럴 재생성 대신 활성 스코프 principal 과 비교. `_wiring.py` 실측은 **감소**해야 하며(리터럴 3곳 + R2 헬퍼 이관) register 값 갱신은 오케스트레이터가 한다.
3. **INSTANCE 소비** — `tos_runtime/brokercap/instance.py`: draft YAML 의 문서 중 활성 스코프 `profile_key.environment` 와 `profile_identity.environment` 가 일치하는 문서를 골라 **`_model_view` 만** 읽어(템플릿 키 ≠ 모델 키 — 메모 §6 divergence 는 인스턴스 저작 소관, 로더가 «수리»하지 않는다) `BrokerCapabilityProfile` 커널 레코드로 구성한다. `status: DRAFT` ∧ `approvers: []` ⇒ `profile_version_current(...) is False`(승인 없음 = 비현행 — 커널 술어 인자로 주입, 로더가 판정하지 않음). 목적은 `capability_admissible` 이 **실 INSTANCE** 에 대해 판정하게 하는 것 — VERIFIED 0 이므로 broker-reaching 은 PROHIBITED 로 **정직하게 deny**. YAML 은 `docs/broker-profiles/` 에 그대로(비규범 위치 불변 · 이동 금지) — 로더는 경로를 설정(`instance_path`)으로 받는다. 파싱은 PyYAML(런타임 기존 의존) · 자작 파서 0.
4. **작업 5 — 6·12 파생**(`compose/context.py`): 
   - item 6 `account_instrument_action_allowed` ← 활성 스코프 `admissibility is ADMISSIBLE` ∧ `endpoint_binding_from_profile_ok(tuple, profile_key, environment_binding=설정, asset_binding=설정)`(binding map 은 `broker_scopes.yaml` 의 `bindings` 블록 — 커널 상수 아님). None 은 없다: 파생 결과는 항상 bool.
   - item 12 `broker_constraint_generation_current` ← `endpoint_class is NONE`(합성 — 정의상 stale 할 broker generation 이 없음 · 사유 문자열 기록) ⇒ True · 그 외 ⇒ `profile_version_current(instance_profile, …)`(DRAFT ⇒ False ⇒ UNKNOWN ⇒ deny).
   - **잔존 attestation 3**: `venue_session_account_facts_current`(venue/session 런타임 owner 부재 — Phase 5) · `restrictive_latch_state` · `worst_credible_capacity`(Phase 5 명시). `_egress_attestations.py` 는 2필드 제거 + docstring 의 「Phase 4 replaces」 문장을 착지 기록으로 갱신. 예시 YAML 2키 삭제.
   - `SendBoundaryContext`·gateway **커널 diff 0** — 파생값이 기존 필드로 들어간다(reason 문자열의 «⚠ provisional stand-in» 은 커널 소관이라 이 계획에서 건드리지 않는다 · §7 운영자 확인).
5. **종료 조건 배터리**(§4) 는 런타임 테스트 + negative-grep + 뮤테이션 실증으로 고정한다. 값형 문턱 0 — 전부 구조.

## 3. 기각 대안

- 커널 `brokercap` 에 scope enum/KIS 스코프 추가 → 브로커 명 커널 유입(`tos-spec-broker-agnostic` · 슬라이스 #1 결정 2 위반).
- draft YAML 을 `tos/runtime/config/` 로 복사·이동 → INSTANCE 는 비규범 단일 원천(`docs/broker-profiles/`)이며 복제는 drift 원천 · 경로 주입으로 충분.
- 템플릿 키를 직접 파싱해 records 로 «수리» → 메모 §6 divergence 의 처분은 인스턴스 저작 행위(P0-2 트랙) · 로더가 값을 발명하게 된다.
- attestation 유지 + 문서만 갱신 → `_egress_attestations.py` 자체가 「Phase 4 replaces」 를 명시 · 파생 가능한 값을 attestation 으로 두는 것은 슬라이스 #3 리뷰가 거부한 fail-open 관용구.
- 리터럴 3곳만 `egress_coordinates.yaml` 키로 옮기고 스코프 없이 G-4 종결 → transport 정체성이 스코프와 분리돼 §5.3 «endpoint 선택은 승인된 exact tuple 로» 를 설정 층에서 위반.
- deferred 4·5 를 이번 웨이브에 → `gateway.py` 2007 등재 한계 + 커널 필드 추가 필요 · 웨이브 2 재심 후 별도 판단(§5 웨이브 3).

## 4. 종료 조건 대응 (개발계획 Phase 4 · 5항)

| # | 개발계획 종료 조건 | 이 계획의 실증 | 상태 목표 |
|---|---|---|---|
| EC-1 | `MOCK_ORDER → REAL_ORDER` 폴백 mutation 전부 검출 | 런타임 `resolve_scope(requested: CapabilityTuple) -> ScopeResolution{scope|None, disposition: {ADMITTED, UNSUPPORTED_DENY, PROHIBITED}}` — 요청 tuple 과 **정확히 같은** tuple 을 가진 scope 만 ADMITTED · `BROKER_SIMULATION`×`FUTURES` 주문은 scope 부재 ⇒ `UNSUPPORTED_DENY`(재작성 0). 뮤테이션 M-A(resolver 가 환경 축을 `BROKER_PRODUCTION` 으로 바꿔 재조회) ⇒ red · negative-grep: `tos_runtime/brokercap` 에 `model_copy(update=`·`model_construct(` 0 · `PROHIBITED` scope 의 소비자 0(`scope.endpoint_class` 를 읽는 호출처 허용목록) | 충족 |
| EC-2 | read-only principal 로 order endpoint 도달 불가 | `credential_route_inventory(active_principal)` 파생: READ 스코프 principal 은 `broker_route=True, usable_credential=True` 이나 **ORDER 스코프에 등재되지 않음** · 게이트웨이 e2e: `egress_coordinates.active_principal` 을 READ principal 로 두면 부팅 거부(결정 1 principal 분리) · 커널 `verify_send_boundary` 에 READ principal 로 claim 시 DENIED(기존 커널 술어 · 런타임 테스트로 하중 확인) | 충족 |
| EC-3 | futures REAL order capability 가 config/env 변경만으로 생성되지 않음 | 설정에 `BROKER_PRODUCTION`×`ORDER_SEND`×`FUTURES` 를 쓰면 로더가 커널 `ValidationError` 를 `BrokerScopeConfigError` 로 감싸 **부팅 거부** · `os.environ`/`getenv` negative-grep 0 · 뮤테이션 M-B(로더가 `model_construct` 로 우회) ⇒ negative-grep red | 충족 |
| EC-4 | MOCK 미지원 조건도 evidence/provenance 가진 read/probe 로 측정 가능 | `REAL_READ` 스코프에 `CONTROLLED_GET_PROBE` provenance(`ProbeManifest(emits_orders=False, …)` 결속) 등재 · `provenance_admits_claim(prov, MEASUREMENT)` 양성 · 같은 provenance 로 `REAL_ORDER` claim 은 음성(커널 구조) · `MOCK_STOCK_ORDER` 스코프는 REDUCED(`profile_evidence_ok: null` ⇒ 비양성) | 충족(스키마+데이터 · 실 프로브 값은 작업 4) |
| EC-5 | broker-consuming mock 경로가 17항목 verify + durable evidence 통과 | **미충족 등재** — 차단 사유: deferred 7~10 owner 부재(Phase 5 작업 4) · KIS MOCK transport 부재(별도 계획) · INSTANCE VERIFIED 0(작업 4 운영자 레인). 이 계획이 하는 것: broker-reaching 스코프로 e2e 를 돌리면 item 6 이 INSTANCE 기반 PROHIBITED 로 **정직 deny** 되는 것을 테스트로 고정(«통과» 위조 불가) | 미충족(§7) |

## 5. 웨이브 · 레인 (파일 소유 1레인 · 공유 파일은 오케스트레이터)

**웨이브 1** (병렬 · 서로의 파일 무접촉)
- **레인 A — 스코프 + G-4** (`executor`/sonnet): 신설 `tos_runtime/brokercap/__init__.py` · `scopes.py` · `tos/runtime/config/broker_scopes.example.yaml` · 테스트 `tos/runtime/tests/brokercap/test_scopes.py` · **`_wiring.py`/`root.py`/`_types.py` 편집은 레인 A 만**(G-4 파생 결선 · `compose_paper_runtime` 이 `broker_scopes.yaml` 로드 · `ComposedRuntime` 에 `scopes` 노출) · 컴포즈 픽스처(`tests/compose/_fixtures.py`)에 예시 설정 채움 · 기존 e2e green 유지.
- **레인 C — INSTANCE 로더** (`executor`/sonnet): 신설 `tos_runtime/brokercap/instance.py`(패키지 `__init__.py` 는 레인 A 소유 — 레인 C 는 모듈만 · 재-export 는 오케스트레이터가 웨이브 말미에) · 테스트 `tos/runtime/tests/brokercap/test_instance.py`(픽스처는 **실 draft YAML 을 읽는다** — 경로는 repo 상대 · hermetic 가드는 읽기 허용) · `capability_admissible(instance, …)` 가 어떤 required set 에도 PROHIBITED 임을 실증 · 두 문서 모두 로드 · `_model_view` 부재 블록은 로드 거부(값 발명 0) · draft YAML **byte 불변**.

**웨이브 2** (레인 A·C 착지 + 오케스트레이터 재-export 후)
- **레인 D — 6/12 파생 + 배터리 + 문서** (`executor`/sonnet): `compose/context.py`(파생) · `_egress_attestations.py`(2필드 제거) · `egress_attestations.example.yaml` · `tests/brokercap/test_exit_conditions.py`(EC-1~4) · `tests/compose/test_egress_attestations.py` 갱신 · 뮤테이션 M-A/M-B 실측 기록(임시 패치 → red → 복원) · 컴포즈 e2e 에서 broker-reaching 스코프 활성화 시 item 6 PROHIBITED deny 실증(EC-5 정직성).
- 독립 리뷰(Claude 측 `code-reviewer` · 저작자 분리) → 처분 → 재심 approve.

**웨이브 3** (조건부 · 재심 후 운영자 확인) — deferred 4·5 실체화: 커널 `SendBoundaryContext` 에 `safety_authority_epoch_current`·`live_scope_valid` 2필드 + `_deferred_item_verdict` 주입 분기(NON_BROKER_SYNTHETIC→N/A 불변 · True 만 SATISFIED · None→UNKNOWN) · 런타임 `authority/epoch.py`·`liveauth` 파생. `gateway.py` 등재 한계 상 신설 모듈 분리 필요 — 착수 시 별도 절로 개정.

## 6. 운영자 레인 (이 계획이 대행하지 않음)

- **작업 4**: P-8 재실행 5회 · N-15 · P-EXT · N-16 · P-BAL · N-19→P-CA(모의 운영 서버 · 런북 §5) → fold → Bounds-Approver 10키 기입(판본 명시) → `tools/bcp_digest.py` 3필드 → `approvers` 기입 = P0-2 종결. 선물 실체결 필요 bound 는 mock-derived(P-R5 영구 차단).
- 이 계획의 INSTANCE 로더는 위 기입이 들어오면 **코드 변경 없이** `profile_version_current`/VERIFIED 차원이 바뀐다 — 그것이 로더를 지금 두는 이유.

## 7. 운영자 확인 지점

1. **Phase 4/5 의존 역전**: 종료 조건 5 는 Phase 5 작업 4(안전 메시 런타임)와 KIS MOCK transport 없이는 닫히지 않는다. 처분 안: (a) 종료 조건 5 를 «Phase 5 착지 후 재판정» 으로 개발계획 §6 에 주석 · (b) Phase 4 를 «구조 완결·EC-5 이월» 로 종결 선언 · (c) KIS MOCK transport 를 Phase 4 후속 슬라이스로 별도 계획. **권고 (a)+(c)**.
2. 커널 gateway reason 문자열의 «⚠ provisional stand-in»(item 6·12)은 파생값이 들어와도 그대로다 — 문언 갱신은 커널 라운드(별도)에서. 이번 계획은 커널 diff 0.
3. `REAL_ORDER` 스코프를 설정에 **등재**(항상 PROHIBITED)하는 것 — 가시성 목적. 등재 자체를 원치 않으면 스코프 3종으로 축소(로더 변경 없이 예시 YAML 만).

## 8. 종료 조건 (이 계획)

- 런타임 `tos/runtime/tests` + 커널 `tos/tests` green · ruff/black/mypy 0 · `tools/tos_size_budget.py --check` 0(`_wiring.py` 감소 재등재) · firewall PASS · `tools/tos_completion_status.py --check` 불변.
- EC-1~EC-4 테스트 green + 뮤테이션 M-A/M-B red 실측 기록 · EC-5 미충족 등재 · EV 상태 변경 0 · draft YAML byte 불변 · 커널 diff 0.
- `_egress_attestations` 잔존 3필드 각각 소유 phase 명시.

## 9. 실행 결과·독립 리뷰 처분 (2026-09-09 · 브랜치 `feat/tos-phase4-scopes` · Phase 3 `5802daab` 위 스택)

### 9.1 착지

| 커밋 | 레인 | 내용 |
|---|---|---|
| `7cb53142` | — | 이 계획 |
| `464ca681` | A | `tos_runtime.brokercap.scopes`(639행) + `broker_scopes.example.yaml`(4 스코프 · binding 표) + G-4: `_wiring.py` 리터럴 3곳·R2 헬퍼 제거 → `transport_nature`/`credential_route_inventory`/`refuse_principal_collision` 파생(1205→1189) · `ComposedRuntime.scopes` · 40 tests(M-A 뮤테이션 + 5축 전수 sweep) |
| `3cfc76e5` | C | `tos_runtime.brokercap.instance`(609행): draft YAML `_model_view` 만 → 커널 `BrokerCapabilityProfile`(DRAFT · `conformance_class=None` — `_model_view` 에 없음) · AssuranceSource→ProvenanceClass 닫힌 표(OFFICIAL_* → OFFICIAL_DOCUMENT · 측정형 5종 unmapped) · MOCK_VTS 17/17 선언·VERIFIED 0 · `capability_admissible` PROHIBITED(version_current 강제 True 도) · 24 tests · YAML sha256 불변 |
| `196bd3fb` | D | `brokercap/derive.py` item 6/12 파생 · 스코프 `instance`/`required_capability_set` 블록 + `instance_path` · `load_instance_document(environment)` · `_egress_attestations` 2필드 퇴역(잔존 키 = 부팅 거부) · `_boot_integrity` 가 `broker_scopes.yaml`·INSTANCE digest 기록 · EC-1~EC-4 green · EC-5 정직성 테스트 · M-C · 796 |
| `8f096700` | E | 독립 리뷰 처분 §9.3 · 809 |

**서베이 정정(실측)**: ① 슬라이스 #1 계획 문언과 달리 커널 `routing_admissibility` 는 `profile_evidence_ok is True` 만 REDUCED — 출하 예시의 `MOCK_STOCK_ORDER`(`null`)는 **PROHIBITED**(정직 · P0-2 증거 0). ② `CapabilityDimension` 에 `CANCELLATION_FINALITY` 없음 → `required_capability_set` 은 `CANCELLATION`. ③ **EC-5 에서 발견**: broker-reaching 활성 스코프는 게이트웨이 이전에 Phase 3 웨이브 2 B-R 의 Coordinator 양성 게이트(`live_scope_authorized` · NOT_AUTHORIZED 자세)가 `LIVE_SCOPE_NOT_AUTHORIZED` 로 step 1 전에 정지시킨다 — 파생 필드의 하중은 커널 `verify_send_boundary` 직접 구동 테스트로 실증(item 6 DENIED[VERIFIED 0] · 12 UNKNOWN · deferred 6 전부 UNKNOWN · NOT_APPLICABLE 0). ④ 종료 조건 항목: 레인 A 보고 47 tests 는 실측 40(보고 과대 · 코드 무관).

### 9.2 발견 (운영자 항목)

- **REAL_PROD INSTANCE 문서의 `profile_identity._model_view`·`live_scope._model_view` 부재**(draft YAML 2번째 문서). 로더는 값을 발명하지 않고 `[doc 1].profile_identity` 를 지목해 거부 — 예상 실패로 핀. MOCK_VTS 문서는 완전. **인스턴스 저작 행위(P0-2 트랙)** 로 annotation 보강 필요 · 이 계획은 YAML byte 불변.
- KIS INSTANCE 는 주식·지수선물을 **하나의 `instrument_class`** 로 선언 → KIS 스코프에서 binding 검사의 asset 축은 판별력이 없다(INSTANCE 형상 · 로더 결함 아님 · 예시 YAML 주석 기록).
- `degraded_since_authorization` 은 권한 부여 행위 이전엔 알 수 없어 예시 `null`(=deny) — P0-2 승인 시 운영자 attestation.

### 9.3 독립 리뷰 (Claude 측 `code-reviewer` 레인 · 저작자 분리 · 대상 `7cb53142..196bd3fb`)

1차 **needs-attention** · 비협상 위반 0 · MEDIUM 5 · LOW 4 · 뮤테이션 M1 4 red · M2 5 · M3 2 · M4 5 · M5 직접 프로브 flip · **M6 0 red** · M7 14 red.

| # | 심각도 | 지적 | 처분(`8f096700`) |
|---|---|---|---|
| F1 | MEDIUM | inventory `inside_boundary=True` 리터럴 → `credential_route_authority_disjoint` 설정으로 반증 불가(M7 14 red = 하중) | 스코프 필수 필드 `inside_boundary`(null 거부) → 파생 · `false` 시 술어 flip 테스트 |
| F2 | MEDIUM | principal 분리가 클래스 간만 — 같은 클래스(MOCK/REAL order) 동일 principal 허용 | 서로 다른 스코프 principal 동일 = 전부 로드 거부(READ/ORDER 쌍은 커널 술어 앵커 유지) |
| F3 | MEDIUM | `resolve_scope` 첫 일치 우선 — 중복 tuple 이 YAML 순서로 승격 가능 | 스코프 간 중복 tuple 로드 거부(유일성 로더 보장) |
| F4 | MEDIUM | 합성 profile_key 가 KIS `instrument_class` 문자열 차용 · 전역 `asset_binding` STOCK/FUTURES 동일 문자열 | 스코프별 binding 오버라이드(합성 = `SYNTHETIC_FUTURES`) · KIS 단일 instrument class 는 INSTANCE 형상으로 주석 기록 · M5 테스트 핀 |
| F5 | MEDIUM | `instance_version_current` 가 `degraded_since_authorization=None` 고정 → 항상 False · approvers 게이트 사문(M6 0) | 스코프 `instance.degraded_since_authorization`(null=deny) attested 입력으로 커널 4인자 정직 공급 · M6 red |
| F6 | LOW | 비문자열 principal → 맨 `AttributeError` · binding 값 비문자열 통과 | `BrokerScopeConfigError` 로 수렴 |
| F7 | LOW | 크기 register 노트 1189 표기 stale(실 1197) | 노트 정정(오케스트레이터) |
| F8 | LOW | 테스트 이름 `item6_true` 가 `is False` 단언 | 개명 |
| F9 | LOW | INSTANCE 4,789행 부팅당 2회 파싱 | 1회 로드 → `_BootResult.instance_document` 스레딩 |

리뷰어 자기 표기: 컨텍스트 독립은 성립하나 저작자와 같은 모델 계열(계보 독립 제한) — 2026-09-04 지시대로 코드는 Claude 측 심판.

### 9.4 재심 (같은 리뷰어 · 대상 `196bd3fb..8f096700`)

**needs-attention** — F1~F9 **전건 동작으로 종결**(리뷰어 자체 프로브 재실행: F1 `inside_boundary:false` 로 `credential_route_authority_disjoint` True→False flip · 게이트웨이 자기 principal 엔트리의 리터럴 True 는 `usable_credential=False, broker_route=False` 라 우회 후보 불가로 정당 · F2/F3 로드 거부 · F4 전역 표 변조는 합성 item 6 불변·스코프 오버라이드 변조는 flip · F5 `null` deny·False 기본 경로 0 · F6~F9). 뮤테이션: M5 13 red · M6 1 red · M7 1 red · M-deg(degraded None 재고정) 1 red.

신규 1건 **MEDIUM** — `_check_instance_bindings` 가 F4 오버라이드 이후에도 **전역** `environment_binding` 을 검증(item 6 은 스코프 자체 표로 결속): REAL_READ 에 `BROKER_PRODUCTION→SYNTHETIC` 오버라이드 + `instance.environment: REAL_PROD` 가 로드 통과 · item 6 True(경로 개방은 0 — `capability_admissible` VERIFIED 0 deny). → **`758b8a15`**: 검사가 `scope.environment_binding` 을 읽도록 수정 · RED 테스트가 프로브를 재현(수정 전 «DID NOT RAISE») · 합의하는 오버라이드는 로드 유지. 런타임 **811**.

### 9.5 최종 (2026-09-09)

리뷰어 종결 확인 **approve**(`758b8a15` — 프로브 재실행: 불일치 오버라이드는 REAL_READ 를 지목해 거부 · 합의 오버라이드는 로드·스코프 자체 표로 해석 · 합성 baseline item 6 True 불변 · 신규 발견 0 · 비협상 위반 0). 최종 tip `758b8a15` · 런타임 **811 passed** · 커널 **9405 passed**(커널 diff 0) · ruff/black/mypy 0 · 크기 예산 PASS(37) · firewall PASS · lint-imports 3/3 · draft YAML sha256 불변 · EV 상태 변경 0.

**§8 종료 조건 판정**: 스위트·린트·예산·firewall 충족 · EC-1~EC-4 green + 뮤테이션(M-A·M-B·M-C·M5·M6·M7·M-deg) red 실증 · EC-5 미충족 등재(§4) · `_egress_attestations` 잔존 3필드 Phase 5 명시 · 커널 diff 0 — **이 계획 종결**. Phase 4 자체는 §1 정직 귀결대로 미완(작업 4 운영자 레인 · deferred 4·5 웨이브 3 조건부 · 7~10 Phase 5 · KIS MOCK transport 별도 계획). push/PR 은 운영자 수동(Phase 3 브랜치 위 스택).

**운영자 확인 대기(§7 + §9.2)**: ① Phase 4/5 의존 역전 처분(권고 (a)+(c)) ② 커널 reason 문언 «⚠ provisional stand-in»(item 6·12) 갱신은 커널 라운드 ③ `REAL_ORDER` 스코프 등재 유지 여부 ④ REAL_PROD INSTANCE `_model_view` annotation 보강(인스턴스 저작) ⑤ 웨이브 3(deferred 4·5 실체화) 착수 여부.
