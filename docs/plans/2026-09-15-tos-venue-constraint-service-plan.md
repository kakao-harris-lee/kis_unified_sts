# TOS venue constraint 서비스 웨이브 계획 — 발행 아티팩트 3 의 소유 분리 · Order Construction Policy 비준 경로 · `run` 차단 (a) 해소

- **상위**: 운영 결선 웨이브 계획 §6 ⑤(`run` 해소 순서 — 운영자 선택 2026-09-15: **(a) venue constraint 서비스 + Order Construction Policy 비준(spec 선행)** 부터) · Phase 5 계획 §11 처분(결정 18 «spec 편집은 별도 PR») · RFC-002 §9.1:553-554(Order Construction Policy governance supplies rules · Venue Constraint Gate 는 비권한 결정을 «생산», 게이트웨이는 «집행») · ADR-002-019 §5.1/§5.2/§5.4·§8·§9·§14 · ADR-002-020 §5.2·§9 · ADR-002-014 §7·§13(활성화) · DR-0001(단일 운영자 변형).
- **선행**: 운영 결선 웨이브 MERGED → main `dbdef60e`. 서베이 `scratchpad/vc-survey-runtime.md`(2026-09-13 · `file:line`) + 세션 모델 직접 대조(spec·커널·컴포즈 · 아래 §0).
- **저작**: 세션 모델 단독 · **커널 diff 0** · 권한 부여 0 · 실 브로커 송신 0 · EV 상태 변경 0 · bound 문서 무접촉 · **spec 편집은 별도 PR(레인 S, 템플릿 + 결정 기록만 · RFC/ADR 본문 무접촉)**.
- **브랜치**: 레인 S `docs/tos-spec-ocp-vcp-templates` · 런타임 `feat/tos-venue-constraint-service`(워크트리 `../kis_unified_sts-venue`).

## 0. 서베이 실측 (요지)

| 항목 | 실측 | 함의 |
|---|---|---|
| 발행 아티팩트 3 | `ConstructionConfig.venue_policy/venue_snapshot/venue_decision`(`_types.py:140-143`) 은 픽스처가 `.issue()` 로 손 발행(`tests/compose/_fixtures.py:432-471`) · `venue_decision` 은 **상수 `ADMISSIBLE`**(`:461-471`) · 소비: step 3 `VenuePhaseStage`(`_venue_phase.py:78-90` 매 호출 `VenueConstraintStage` 재구성) · item 11 `ComposeContextResolver.venue_*`(`context.py:435-437, 851-853` **부팅 시 고정 필드**) · 게이트웨이 item 11 은 «현재 fold ∧ 결속 decision.result is ADMISSIBLE»(`gateway.py:690-740`) | decision 이 상수라 item 11 의 «결속 decision 도 admit» 검사는 **공허**(M6 계열) · snapshot 의 `observed_session_phase` 는 픽스처 상수인데 step 3 는 별도 phase reader 를 씀(둘의 불일치는 fold 가 `observed_phase` 인자만 읽어 가려짐) |
| 커널 정의 | `VenueConstraintPolicy`(`venue/records.py:354-417` · «Policy activation is spg-owned · venue is the content author») · `VenueConstraintSnapshot`(`:420-477` · 평가 · 권한 0) · `OrderAdmissibilityDecision`(`:480-559` · 정확한 shape 1건의 결과 · `_COVERED_FIELDS` 20) · 판정은 `fold_venue_admissibility`(`egressgw/construction.py:865-917` = `session_phase_admits` ∧ `order_shape_admissible` · any-restriction-wins) · `IndependentIdArtifact.issue(scheme, **content)` 로 실 digest 발행(`canonical/_base.py:226-262`) | **정책 = 거버넌스 문서(운영자 저작+활성화) · 스냅샷/결정 = 서비스 발행 · 판정 = 커널 fold 만** — 런타임은 어느 판정도 저작하지 않는다 |
| spec | ADR-002-019 §8(정책이 선언할 것: scope · 원천 · phase 규칙 · **tick 표·lot·band** · 허용 side/type/TIF · «Policy activation follows ADR-002-014») · §9(제약 사실은 Critical Input · «A calendar is a baseline expectation … None alone proves current admissibility unless the active policy explicitly defines the fact, source semantics, bound») · §14(decision 이 결속할 것: policy id/gen/digest · Constraint Generation · capsule · candidate command id/digest · brokercap ceiling · route 필드 · result · failed/unknown) · ADR-002-020 §5.2(OCP = «immutable, authenticated, separately governed artifact») · §9(선언 항목 · 컴파일러 결정론) · 둘 다 **Status: Proposed**(ADR 수용은 실행 증거로만 — 비준 대상은 ADR 이 아니라 **정책 인스턴스**) · 템플릿: `verification/` 87종 중 **`VENUE-CONSTRAINT-POLICY`·`ORDER-CONSTRUCTION-POLICY`·`VENUE-CONSTRAINT-SNAPSHOT`·`ORDER-ADMISSIBILITY-DECISION` 템플릿 4종 이미 존재**(shape canon · 규칙은 자유 리스트 · 커널 Phase-1 레코드보다 넓음) · 결정 기록 형식 `decision-records/DR-0001` · Broker Capability Profile INSTANCE 는 tos-spec 밖(`docs/broker-profiles/` · `_model_view` 규율 `brokercap/instance.py`) | spec 측 저작물 = **DR-0002 만**(인스턴스 배치·활성화·v1 커버리지 결정 · 템플릿 무접촉) · 인스턴스 파일 = 템플릿 형상 + `_model_view`(커널 필드) + `_runtime`(런타임 전용) — brokercap INSTANCE 관용구 |
| OCP 좌표 | `_wiring.py:536-540` 리터럴 `policy_id="compose-ocp", policy_version="ocp-v1", policy_generation=1` → `construct_candidate_command` 가 이 3좌표로 `OrderConstructionPolicy.issue(...)`(`construction.py:638-644` · signer/approval/evidence **None**) → `CandidateConstruction.policy` · 커널 시그니처는 좌표 3개만 받음 | 로더가 실 좌표를 공급 · **v1 OCP 레코드 covered 내용 = id/version/generation**(signer 등은 커널 경로가 못 받음 → 커널 라운드 #4 후보) · 로더 발행 digest == 커널 발행 digest 를 `classify_record_pair` 로 핀 |
| 활성화 | `safety_activation.yaml` → spg `ActivationRecord`(`spg/records.py:520-560` · `bundle_digest`·`scope`·`approval_ids`) · `BundleMemberRef{kind, member_id, generation, digest, resolved, immutable}`(`:117-137`) · `BundleMemberKind.VENUE_CONSTRAINT_POLICY/ORDER_CONSTRUCTION_POLICY`(`spg/vocabulary.py:215-216`) · 런타임 `SafetyProfileService` 는 `members=()` 로 번들 구성(`safety/profile.py:313`) | 활성화 = 기존 활성화 문서에 `members:` 항목 추가 + 정확 일치 검사(커널 `BundleMemberRef` 모델 재사용) · ADR-014 §13 10단계 전체가 아니라 기존 서비스와 같은 수준(문서+digest 일치) — 정직하게 공시 |
| 세션·brokercap | `SessionFactsOwner.phase_for_step3`(tick generation 캐시 · `calendar/owner.py`) · `boot.instance_document`(`profile` 은 **DRAFT** → `canonical_digest` None · `profile_version` «0.1.0-draft») · route 좌표: `egress_coordinates.yaml`(`route_identity`·`endpoint`) · P0-2: `price_band_tick_lot_and_quantity_semantics: UNKNOWN`(프로파일 초안 `:2364,:4427` · 가격제한폭·호가단위 조회 0건 · 틱은 로컬 설정 `config/execution.yaml` 이었음 `:864`) | 스냅샷 phase = 실 관측 · brokercap digest None(초안) 정직 · **price band 원천 없음** → 실 배포 정책의 `price_min/max` 는 null → 커널 `order_shape_admissible` UNKNOWN(§5 정직 상태) |
| 크기 | `_wiring.py` 1118(등재 예외 · 상한) · `context.py` 885 · `cli.py` 905 · `_types.py` 603 · `_venue_phase.py` 115 | 새 모듈로 착지 · `_wiring.py` 는 순증 0 이하 |
| 테스트 | `_fixtures.py::construction_config()`(`:501-518`) · `_symmetry_fixtures.py:281-297`(NEW_SHORT 미러) · `conftest.py::config_dir` 가 yaml 21종 저작(`:65-445`) · `EXPECTED_CODE_DIGEST = observe_source_tree_digest()` | conftest 에 정책 yaml 2 + 활성화 `members:` 추가 · 미러 픽스처 동시 개정 |

## 1. 목표 · 범위 · 비범위

**목표**: `run` 차단 (a) — «`ConstructionConfig` 의 발행 아티팩트 3 은 픽스처만 발행» — 를 **소유 분리**로 닫는다: 정책은 거버넌스 문서(로더 + 활성화 일치), 스냅샷·결정은 런타임 서비스가 **커널 fold 만으로** 발행, OCP 좌표는 비준된 인스턴스에서 로드. 게이트웨이 item 11 의 «결속 decision 도 admit» 검사가 실값이 된다.

**범위**: (S) spec 템플릿 2 + DR-0002 · (a) `tos_runtime/venue/{config,activation,service}.py` · (b) 컴포즈 결선(`_venue_wiring.py` 신설 · `_venue_phase.py` 삭제 · `_wiring.py` 리터럴 제거 · `context.py` 고정 필드 → 단계 읽기 · `_types.py` `ConstructionConfig` 축소 · `root.py` 순서 · `cli.py` `print-policy-digests` + 차단 목록 개정) · (c) 문서(config README · INDEX · 본 계획 §7) · 실파일 제안표(§6 ②).

**비범위**: 커널 편집(라운드 #4 후보만 등재) · price band/tradability 실 원천(broker 조회 · marketfeed 기준가 — 별도 웨이브) · `run` 의 나머지 차단((a′) envelope/price/order_shape 원천 · (b) 리스크 제공자 · (c) 틱 원천) · 투영(projection) 필드군 추가 · 프론트 · Phase 5 §11 결정 18 의 spec 편집(OPERATOR-001 owner · KRX INSTANCE 등재 — 별도 PR 유지).

## 2. 결정

1. **소유 분리(세 아티팩트).** `VenueConstraintPolicy` = `venue_constraint_policy.yaml`(운영자 저작) → `tos_runtime/venue/config.py::load_venue_constraint_policy` 가 커널 `.issue(scheme, …)` 로 **실 digest** 발행(ISSUED · 좌표 `policy_id`/`policy_generation` 필수). `VenueConstraintSnapshot` = `venue/service.py::VenueConstraintService.snapshot()` 이 **tick generation 당 1회** 발행(phase 변화 시 재발행 · 같은 tick 재발행 0). `OrderAdmissibilityDecision` = `VenueConstraintService.decide(...)` 가 **attempt 당 1회**, `result = fold_venue_admissibility(...)`(커널) 로 발행. **런타임은 어느 판정도 저작하지 않는다** — `OrderAdmissibilityResult` 값을 만드는 코드는 커널 fold 호출 한 곳(AST 핀: `tos_runtime` 안에서 `OrderAdmissibilityResult.<X>` 를 **생성 인자로** 쓰는 곳 0 · 비교 `is` 만).
2. **스냅샷 내용(필드별 원천 공시).** `observed_session_phase` = `SessionFactsOwner.phase_for_step3()`(step 3 와 **같은** reader) · `policy_id/generation/digest` = 로드된 정책 실값 · `constraint_generation` = **내구 단조**: 부팅 시 evidence 저장소의 기존 `VENUE_SNAPSHOT_ISSUED` 행 수를 기저로 발행마다 +1(append-only 라 재시작 후에도 단조 · 복원은 W4 규칙대로 non-live) · `action_tradability` = `()`(원천 없음 — fold 는 이 맵을 읽지 않으므로 팬텀 0 · 후속 broker 조회 원천) · `critical_input_snapshot_digest` = None(capsule 은 `CapsuleStandInDigest` stand-in) · `source_continuity_id` = None(원천 없음) · `max_age` = None(신선도는 tick generation 재발행으로 담보 · 커널 Phase 1 null). 각 None 은 evidence `VENUE_SNAPSHOT_ISSUED` 페이로드에 `absent_fields` 로 열거.
3. **결정 내용.** `result`·`failed_predicates`·`unknown_predicates` = 커널 fold 의 두 sub-result(`session_phase_admits`/`order_shape_admissible` 를 각각 호출해 이름 기록 · 최종 result 는 `fold_venue_admissibility` 값과 **동일해야** 함 — 테스트 핀) · `candidate_command_id/digest` = step 2 `OrderConstructionStage.construction.command` 실값(step 2 → 3 순서라 항상 존재 · 없으면 None + UNKNOWN 아님: fold 는 shape 로 판정하므로 결과는 그대로, 결속만 None 으로 공시) · `snapshot_id/digest` · `policy_*` 실값 · `decision_context_capsule_*` None(stand-in) · `broker_capability_profile_version` = `instance_document.profile.profile_version` 실값 · `_digest` = `profile.canonical_digest`(DRAFT ⇒ None · 절대 문자열 발명 0) · `bound_instrument_route` = 정책 `scope` 블록 ∧ 구성 좌표(§2.5 교차검사 뒤 채움 · `contract_month/expiration/multiplier/settlement_method` 는 None — 계약월 정체성 부재는 W5 §6 ⑧ 그대로) · `action_class`·`observed_session_phase` 실값 · `authority_effect` 기본(all-false). `decision_id` = `vdec-<env>-<n>`(n = 기존 `ORDER_ADMISSIBILITY_DECISION_ISSUED` 행 수 + 1 · 내구 유일).
4. **step 3 결선(두 번 fold).** `compose/_venue_wiring.py::VenueServiceStage.__call__(request)`: ① `snapshot = service.snapshot()` ② `stage0 = VenueConstraintStage(decision=None, …)` 호출 → `resolved_shape`(커널의 value-view 투영 — 사적 속성 접근 0 · 로직 복제 0) ③ `decision = service.decide(action_class, shape=stage0.resolved_shape, candidate_command=construction_stage.construction.command)` ④ `stage = VenueConstraintStage(decision=decision, …)` 반환 verdict. 순수·결정론이라 두 fold 는 같은 값(테스트 핀). `resolved_shape`/`shape_constraints`/`last_snapshot`/`last_decision`/`policy` 노출. `_venue_phase.py` 삭제.
5. **`ConstructionConfig` 축소 + 정책 scope 교차검사.** 삭제: `venue_policy`·`venue_snapshot`·`venue_decision`·`venue_shape_constraints`·`venue_constraint`(뒤 둘은 정책 `shape_constraints` + yaml `quantity_unit` 에서 `VenueQuantityConstraint` 로 **파생** — 중복 타이핑 0). 잔존: `account`·`instrument`·`envelope`·`price`·`order_shape`·`action_class`·`instrument_class`·`outbound_side`·`price_field_key`·`shape_price_field_key`. 부팅 교차검사(`VenuePolicyScopeMismatch` 거부): `policy.scope.{instrument, account, environment, instrument_class}` == 구성 좌표 · 정책 `admitting_phase_rules` 의 모든 phase 토큰 ∈ `calendar.yaml` 이 그 instrument_class 에 선언한 토큰 집합(캘린더가 만들 수 없는 토큰만 admit 하는 정책 = 공허 admit → 거부).
6. **Order Construction Policy 비준 경로.** (S) tos-spec: `decision-records/DR-0002-Order-Construction-and-Venue-Constraint-Policy-Instance-Ratification.md`(System Owner 결정: 인스턴스는 기존 템플릿 `VENUE-CONSTRAINT-POLICY-template.yaml`/`ORDER-CONSTRUCTION-POLICY-template.yaml` 의 형상을 따르되 tos-spec 밖 `config/tos_runtime/<env>/` 에 두고 `_model_view`/`_runtime` 블록으로 커널·런타임 값을 싣는다(brokercap INSTANCE 관용구) · `status: ISSUED` 만 로드(DRAFT 거부) · 활성화 = ADR-002-014 Activation Record `members:` 정확 일치 + DR-0001 단일 운영자 변형 · v1 커버리지: OCP covered = id/version/generation, 나머지 ADR-020 §9 항목·템플릿 규칙 리스트는 데이터로만 보존(런타임 해석 0) 또는 TBD → 커널 UNKNOWN · 런타임은 미활성 정책으로 부팅 금지) · `SUMMARY.md` 항목 · `tos_spec_status.py --check` 통과 · 템플릿·RFC·ADR 본문 무접촉. (런타임) `order_construction_policy.yaml` → `load_order_construction_policy` → `OrderConstructionPolicy.issue(policy_id, policy_generation, policy_version)`(**signer/approval/evidence_package_ref 는 None** — 커널 `construct_candidate_command` 가 좌표 3만 받아 자체 발행하므로 로더 digest == 커널 digest 여야 `classify_record_pair` 충돌 0 · 테스트 핀 · 커널 라운드 #4 후보 «정책 레코드 자체를 인자로») · 비covered 교차검사: `canonicalization_version` == 컴포즈 scheme version · `wire_codec`: transport kis-mock 이면 `kind: kis-order-cash-v1` + `wire_fields` == `KIS_ORDER_CASH_WIRE_FIELDS` 정확 일치, synthetic 이면 `null` 만 허용 · `_wiring.py:536-540` 리터럴 → 로드 좌표(grep 핀: `compose-ocp`·`ocp-v1` 0). `intent_id/envelope_id/command_id/generation` 리터럴은 (a′) 잔존 — 차단 목록에 정직 등재.
7. **활성화 일치.** `safety_activation.yaml` 에 `members:`(명시 리스트 · `[]` 허용 = 아무것도 활성 아님 → 두 정책 모두 미활성 → 부팅 거부) · 항목은 커널 `BundleMemberRef` 필드 그대로(`kind`·`member_id`·`generation`·`digest`·`resolved`·`immutable`) · `venue/activation.py::require_member_activated(members, kind, member_id, generation, digest)` = `kind is X` ∧ 3좌표 정확 일치 ∧ `resolved is True` ∧ `immutable is True`, 아니면 `PolicyNotActivated` 부팅 거부. 운영자가 digest 를 알 수 있도록 CLI `print-policy-digests --config-dir`(두 정책 로드 → id/generation/digest 표준출력 · 저장소 0 · `print-digests` 관용구). 기존 `SafetyProfileService` 의 번들(`members=()`)은 **무접촉**(activation_atomic 의미 불변).
8. **evidence.** `VENUE_POLICY_BOUND`(부팅 1회: policy id/gen/digest · 활성 member digest · `null_shape_bounds` 열거) · `ORDER_CONSTRUCTION_POLICY_BOUND`(부팅 1회) · `VENUE_SNAPSHOT_ISSUED`(변화 시만) · `ORDER_ADMISSIBILITY_DECISION_ISSUED`(attempt 당 · id/digest/result/failed/unknown/candidate digest/snapshot id). 런타임 문자열 상수(커널 `EvidenceKind` 무접촉 · `SESSION_FACTS_*` 관용구).
9. **컴포즈 순서(`root.py`).** `_boot_services` 뒤 · `build_session_facts_owner` 뒤 · `_build_construction_stages` **앞**에 `build_venue_service(config_dir, scheme, session_phase_reader, tick_generation_reader(late cell 공유), evidence_store, environment_label, construction, instance_document, egress_coordinates, transport_kind)` → 정책 2 로드 · 활성화 검사 · scope 교차검사 · 서비스 구성. `_build_construction_stages(construction, session_phase_reader, venue_service, ocp)` 가 step 2 에 OCP 좌표·파생 `VenueQuantityConstraint` 를, step 3 에 `VenueServiceStage` 를 준다. `ComposedRuntime.venue: VenueConstraintService` 노출. `context.py`: `venue_snapshot/venue_policy/venue_decision` 고정 필드 3 삭제 → `self.venue_stage.last_snapshot/.policy/.last_decision`(attempt 단위 실값). item 11 은 이제 «현재 fold ∧ 이번 attempt 에 발행된 decision 의 result».
10. **`run` 차단 목록 개정(코드 0 · 문언).** (a) 발행 아티팩트 3 → **해소**(본 웨이브) · 신설 (a′) `ConstructionConfig` 잔존 입력 3 의 원천: `envelope`(승인된 Intent — IAP 흐름) · `price`(marketfeed) · `order_shape`(전략 제안) + `_wiring.py` intent/envelope/command id 리터럴 · (b)(c) 불변. `cli.py` docstring + 본 계획 §7 + `config/tos_runtime/README.md`.

## 3. 기각 대안

| 대안 | 기각 사유 |
|---|---|
| YAML → 스냅샷/결정 로더(«설정에서 발행») | 운영 결선 계획 §3 그대로 — 설정이 판정을 저작. 결정 `result` 를 파일이 들면 item 11 은 영원히 공허 |
| 런타임이 tradability/price band 를 캘린더·로컬 상수로 «추정» | ADR-019 §9 «calendar is a baseline expectation … none alone proves current admissibility» · VTG-INV-002 · P0-2 가 원천 0 을 실측(가격제한폭 조회 0건). None 으로 두고 커널이 UNKNOWN 을 내는 것이 정직 |
| `VenueConstraintStage` 를 한 번만 만들고 decision 을 나중에 꽂기 | 사적 속성 쓰기(KR3 에서 이미 퇴출한 shim). 두 번 fold 가 순수·결정론이라 비용만 든다 |
| OCP 레코드에 signer/approval 을 채우고 커널 발행과 다른 digest 를 허용 | 같은 id·다른 bytes = 커널이 `CRITICAL_CONFLICT` 로 정의한 위조 형상. 커널 시그니처 변경(라운드 #4)까지는 좌표 3 만 |
| `SafetyConfigurationBundle.members` 에 두 정책을 넣어 `bundle_complete` 재사용 | 기존 `SafetyProfileService` 의 `activation_atomic`/`units_compatible` 입력을 바꿔 안전 프로파일 판정에 부수효과. 별도 정확 일치 검사(커널 `BundleMemberRef` 모델만 재사용)가 최소 |
| ADR-002-019/020 을 Ratified 로 올리기 | ADR 수용은 실행 증거로만(운영자 지시). 비준 대상은 정책 **인스턴스**(DR-0002) |
| 실 배포 정책 파일을 이번 웨이브에 값과 함께 착지 | tick/lot/qty 는 로컬 설정 출처(등급 C) · band 는 원천 0. 값 채택은 운영자 결정(§6 ②) — 캘린더와 같은 절차 |
| 투영에 venue 필드군 추가 | 대시보드 스키마 변경 · 본 웨이브 목적 밖(후속 1줄) |

## 4. 레인 · 파일 소유권 · 순서

| 레인 | 파일(소유) | 결정 | 순서 |
|---|---|---|---|
| **S**(세션 모델 · spec PR) | `tos-spec/src/decision-records/DR-0002-….md` · `tos-spec/src/SUMMARY.md`(템플릿 4종은 기존 그대로 · 무접촉) | 6 | **선행**(머지 후 런타임 착수 가능 · 병렬 저작은 허용) |
| **a**(executor) | `tos/runtime/src/tos_runtime/venue/{__init__,config,activation,service}.py` · `tos/runtime/tests/venue/*` | 1·2·3·7·8 | S 와 병렬 |
| **b**(executor) | `compose/_venue_wiring.py`(신설) · `compose/_venue_phase.py`(삭제) · `compose/_wiring.py` · `compose/context.py` · `compose/_types.py` · `compose/root.py` · `compose/cli.py` · `tests/compose/{_fixtures,_symmetry_fixtures,conftest,test_compose_root,test_symmetry*}.py` · `config/tos_size_budget.yaml`(드리프트만) | 4·5·6·7·9·10 | a 착지 뒤 |
| **c**(세션 모델) | `config/tos_runtime/README.md` · `docs/plans/INDEX.md` · 본 계획 §7 | 10 | b 뒤 |
| 리뷰 | `code-reviewer`(sonnet · 저자 아님) · **뮤테이션 실행표 필수** | §5 | 각 PR |

레인 a/b 공통 규율: `shared.*` 0 · 서드파티 0 · `os.environ`/`subprocess`/`importlib.import_module` 0(방화벽은 tests 도 스캔) · 모듈 ≤1000/함수 ≤100(분할 우선 · 등재는 가시성) · 극성 `is True`/`is False` · 사실에 원천이 없으면 None(발명 0) · 커널 객체 사적 속성 접근 0 · 공유 파일은 헝크 스테이징 + pathspec 없는 커밋.

### 4.1 레인 a 인터페이스(계획 고정 · b 가 이 시그니처에 결선)

```python
# tos_runtime/venue/config.py
VENUE_POLICY_CONFIG_NAME = "venue_constraint_policy.yaml"
ORDER_CONSTRUCTION_POLICY_CONFIG_NAME = "order_construction_policy.yaml"
class VenuePolicyConfigError(RuntimeError): ...
@dataclass(frozen=True)
class VenuePolicyScope: environment; broker; account; venue; market_segment; product_type; instrument; instrument_class; currency: str | None; quantity_unit: QuantityUnitKind
@dataclass(frozen=True)
class LoadedVenuePolicy: policy: VenueConstraintPolicy; scope: VenuePolicyScope; quantity_constraint: VenueQuantityConstraint; null_shape_bounds: tuple[str, ...]
def load_venue_constraint_policy(path: Path, *, scheme: CanonicalizationScheme) -> LoadedVenuePolicy
@dataclass(frozen=True)
class LoadedOrderConstructionPolicy: policy: OrderConstructionPolicy; canonicalization_version: str; wire_codec_kind: str | None; wire_fields: frozenset[str]
def load_order_construction_policy(path: Path, *, scheme: CanonicalizationScheme) -> LoadedOrderConstructionPolicy

# tos_runtime/venue/activation.py
class PolicyNotActivated(RuntimeError): ...
def load_activation_members(activation_path: Path) -> tuple[BundleMemberRef, ...]   # `members:` 명시 리스트 · 누락/None ⇒ 오류
def require_member_activated(members, *, kind: BundleMemberKind, member_id: str, generation: int, digest: str) -> BundleMemberRef

# tos_runtime/venue/service.py
VENUE_POLICY_BOUND_KIND / VENUE_SNAPSHOT_ISSUED_KIND / ORDER_ADMISSIBILITY_DECISION_ISSUED_KIND / ORDER_CONSTRUCTION_POLICY_BOUND_KIND
class VenueConstraintService:
    def __init__(self, *, loaded_policy: LoadedVenuePolicy, scheme, session_phase_reader: Callable[[], str | None],
                 tick_generation_reader: Callable[[], int | None], evidence_store: SqliteEvidenceStore, environment_label: str,
                 route_fields: InstrumentRouteFields, broker_capability_profile_version: str | None, broker_capability_profile_digest: str | None) -> None
    policy: VenueConstraintPolicy; shape_constraints: VenueShapeConstraints; quantity_constraint: VenueQuantityConstraint
    def snapshot(self) -> VenueConstraintSnapshot          # tick generation 캐시 · phase 변화 시 재발행 · 변화 시 evidence
    def decide(self, *, action_class: ActionClass, shape: OrderShapeFields | None, candidate_command: CanonicalBrokerCommand | None) -> OrderAdmissibilityDecision
    last_snapshot: VenueConstraintSnapshot | None; last_decision: OrderAdmissibilityDecision | None
```

`venue_constraint_policy.yaml` = `VENUE-CONSTRAINT-POLICY-template.yaml` 인스턴스: 템플릿 키 전부 존재(`artifact_type`·`schema_version "1.0-DRAFT"` 일치 · `status: ISSUED` 만 로드 · `policy_id`/`policy_generation` 최상위 스칼라 · `canonical_digest` 는 `TBD`(로더 산출) 또는 산출값과 정확 일치 · `scope` 의 `environments/brokers/accounts/venues/market_segments/instruments` 는 **각 1항목**(단일 live scope) · 규칙 리스트는 데이터로만 보존) + `_model_view{admitting_phase_rules[{action, admitting_phases[]}], required_constraint_classes[], shape_constraints{price_min,price_max,tick_size,lot_size,min_quantity,max_quantity,allowed_order_types[],allowed_tifs[],allowed_sides[],allowed_position_effects[]}, dependency_closure{edges[]}}`(수치 null 허용 = 원천 없음 · 커널 UNKNOWN · `null_shape_bounds` 공시 · `admitting_phase_rules[*].action ⊆ scope.action_classes` 아니면 거부) + `_runtime{instrument_class, quantity_unit, currency}`. 커널 `scope` 문자열은 여섯 좌표에서 결정론적으로 파생. `order_construction_policy.yaml` = `ORDER-CONSTRUCTION-POLICY-template.yaml` 인스턴스: 같은 최상위 규칙(+`construction_generation` 데이터 보존) + `_model_view{policy_generation(최상위와 일치), policy_version}` + `_runtime{canonicalization_version(== scheme version), wire_codec: null | {kind, wire_fields[]}}`.

## 5. 종료 조건 · 실증 · 뮤테이션

- 실증(레인 b e2e · 실 커널 fold): (1) 정책 yaml 2 + `members:` 로 부팅 → `VENUE_POLICY_BOUND`·`ORDER_CONSTRUCTION_POLICY_BOUND` 각 1 · step 3 ADMIT · item 11 SATISFIED · decision.result 가 fold 와 동일 · `decision.candidate_command_digest == construction.command.canonical_digest` (2) 같은 tick 두 attempt → 스냅샷 evidence 1 · decision evidence 2 · `constraint_generation` 불변 (3) `FixedWallClockReference` 로 CLOSED 위상 → decision INADMISSIBLE · step 3 DENY · item 11 미도달(step 3 에서 정지) (4) 재부팅 → `constraint_generation` 이 직전 값보다 큼 (5) `print-policy-digests` 출력 digest == `VENUE_POLICY_BOUND` 페이로드 digest (6) 미러(NEW_SHORT) 구성에서 decision 필드가 side/action 외 동일 (7) `run` 여전히 파싱 전용 + 개정 차단 목록.
- **뮤테이션 실행표(리뷰어가 실행 · 첫 판정에 필수)**:

| # | 뮤테이션 | 기대(RED) |
|---|---|---|
| M1 | 정책 `admitting_phase_rules` 에서 구성 action 항목 삭제 | `session_phase_admits` INADMISSIBLE → step 3 DENY(허용 기본값 0) |
| M2 | `members:` 의 정책 digest 1자 변경 / `resolved: false` / `members: []` | `PolicyNotActivated` 부팅 거부(3 케이스) |
| M3 | `VenueConstraintService.decide` 가 fold 대신 `OrderAdmissibilityResult.ADMISSIBLE` 상수 반환 | «decision.result == fold» 핀 + CLOSED 시나리오 red · AST 핀(런타임에서 `OrderAdmissibilityResult.<X>` 생성 인자 0) red |
| M4 | `_wiring.py` 에 `policy_id="compose-ocp"` 복원 | grep 핀 red · `construction.policy.canonical_digest != loaded.policy.canonical_digest` 핀 red |
| M5 | 스냅샷을 매 호출 재발행(캐시 제거) | «같은 tick evidence 1» red |
| M6 | decision 의 `candidate_command_digest` 를 None 고정 | 결속 핀 red |
| M7 | brokercap digest 를 `"draft"` 문자열로 발명 | `broker_capability_profile_digest is None`(DRAFT) 핀 red |
| M8 | `constraint_generation` 기저를 0 고정(evidence 미판독) | 재부팅 단조 핀 red |
| M9 | `ConstructionConfig` 에 `venue_decision` 필드 복원 + 소비 | AST 핀(`.issue` 호출: `VenueConstraintSnapshot`/`OrderAdmissibilityDecision` 는 `venue/service.py` 만 · `VenueConstraintPolicy`/`OrderConstructionPolicy` 는 `venue/config.py` 만) red |
| M10 | 정책 phase 토큰을 캘린더에 없는 `"OPEN_X"` 로 | scope 교차검사 부팅 거부 red |
| M11 | OCP `wire_codec: null` + `--transport kis-mock` | 부팅 거부 red · synthetic 이면 통과 |
| M12 | `context.py` 에서 `last_decision` 대신 부팅 시 첫 decision 을 캐시 | CLOSED→OPEN 두 tick 시나리오에서 item 11 이 옛 decision 을 읽음 → 핀 red |

- 검증 명령: `PYTHONPATH=tos/runtime/src:tos/src .venv/bin/python -m pytest tos/runtime/tests -q` · 커널 `tos/tests` 불변(diff 0) · `python tools/tos_firewall_check.py && lint-imports` · `python tools/tos_size_budget.py --check` · `python tools/tos_spec_status.py --check`(레인 S) · `ruff check` · `mypy`. `pytest | tail` 금지(pipefail 또는 출력 파일 인용).
- 정직 상태(예상): 실 KRX 배포 정책은 `price_min/max` 원천 0 → `order_shape_admissible` UNKNOWN → step 3 UNKNOWN(송신 0) — **이 웨이브는 서비스를 세우지만 실배포 admissibility 는 band 원천 웨이브까지 UNKNOWN**. tradability 맵 빈 값 · capsule/continuity None · brokercap digest None(초안) · OCP signer/approval 미결속(라운드 #4) · `run` 은 (a′)(b)(c) 로 계속 차단.

## 6. 운영자 확인

1. **DR-0002 수용**: 레인 S PR 머지 = System Owner 수용(DR-0001 관용구 · Status 는 PR 에서 `Proposed` → 머지 시 `Accepted` 로 전환 여부 회신).
2. **실 배포 정책 값(캘린더와 같은 절차 · 표 단위 채택/수정/보류)** — 채택 시 `config/tos_runtime/paper/{venue_constraint_policy,order_construction_policy}.yaml` 실파일 착지(후속 커밋):

| 키 | 제안값(krx-index-futures · KOSPI200) | 출처·등급 |
|---|---|---|
| `tick_size` | `5`(가격 ×100 정수 스케일 · 0.05pt) | `config/execution.yaml:286`(로컬 설정 · C) + P0-2 호가단위 서버측 검증 관측(초안 `:853-868`) |
| `lot_size`/`min_quantity` | `1`/`1` | 선물 계약 단위(공식 명세 · B) |
| `max_quantity` | **보류** | 계좌·상품별 broker 한도 조회 0건 → null(커널 UNKNOWN) |
| `price_min`/`price_max` | **보류(null)** | 가격제한폭 원천 0(P0-2 UNKNOWN) → band 원천 웨이브 |
| `allowed_order_types`/`tifs` | `[LIMIT]`/`[DAY]` | INSTANCE 초안 `order_type: LIMIT` · TIF 집합 N-17(`{"0","3","4"}` 중 DAY 매핑은 OCP 결정) |
| `allowed_sides`/`position_effects` | `[BUY, SELL]`/`[OPEN, CLOSE]` | 대칭 규칙(장·단 동등) |
| `admitting_phase_rules` | `NEW_LONG/NEW_SHORT/CLOSE: [REGULAR]`(캘린더 토큰 그대로) | `calendar.yaml` 선언 토큰 |
| OCP `policy_id/version/generation` | `ocp-paper-krx-futures` / `1.0.0` / `1` | 신규 |
| OCP `wire_codec` | synthetic: `null` · kis-mock: `kis-order-cash-v1` + 9 필드 | `codec.py:96-108` |
3. **활성화 `members:` 기입은 운영자 수동**(`print-policy-digests` 출력 → `safety_activation.yaml`) — 캘린더 digest 관용구와 동일.
4. 커널 라운드 #4 후보 등재 여부: `construct_candidate_command(policy: OrderConstructionPolicy)`(signer/approval/evidence 결속) · `VenueShapeConstraints` 가격대별 tick **표**(주식) · 계약월 정체성.
5. band/tradability 원천 웨이브 순서: broker 조회(P-CA 관용구 · GET-only) vs marketfeed 기준가 — (b)(c) 와 함께 다음 결정.

## 7. 착지 기록

(레인 착지 후 기입)
