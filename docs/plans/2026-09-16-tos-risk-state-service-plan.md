# TOS 리스크 상태 서비스 웨이브 계획 — `run` 차단 (b) 해소 · 포지션/주문 상태의 구조적 관측 · Aggregate Risk / Action Flow 정책 인스턴스

- **상위**: venue constraint 서비스 계획 §6 ④⑤(다음 웨이브 순서 — 운영자 선택 2026-09-16: **(b) 리스크 상태 서비스**) · 운영 결선 계획 §2.10 차단 목록 (b) «리스크 입력 제공자 2 의 프로덕션 원천 없음» · ADR-002-021(§5.3 State Snapshot · §9 결속 항목 · §12 공식 · ARE-INV-006 UNKNOWN 은 보수 소비) · ADR-002-022(§5.3 State Snapshot · §5.8 증폭 봉투 · §12 6 상태) · ADR-002-014(활성화) · DR-0002(인스턴스 배치·활성화 경로 — 본 웨이브가 ARE/AFG 정책으로 확장) · 설계 #13(`2026-07-25-tos-aggregate-risk-projection-design.md` §0.4e 소유 표) · 설계 #16(`2026-07-26-tos-action-flow-budgeting-design.md` §0.2 NO 목록).
- **선행**: venue 웨이브 완료(main `13667821`) · 실파일 PR #701(로더 scope TBD 거부 포함 — 본 웨이브 로더가 재사용). 서베이 `scratchpad/rs-survey-{runtime,spec}.md`(2026-09-16 · `file:line`).
- **저작**: 세션 모델 단독 · **커널 diff 0** · 권한 부여 0 · 실 브로커 송신 0 · bound 문서 무접촉 · spec 편집은 DR-0003 1건(별도 PR).
- **브랜치**: 레인 S `docs/tos-spec-dr-0003` · 런타임 `feat/tos-risk-state-service`(워크트리 `../kis_unified_sts-riskstate`).

## 0. 서베이 실측 (요지)

| 항목 | 실측 | 함의 |
|---|---|---|
| 판정 층 | `AggregateRiskService.decide`(`risk/aggregate.py:369-449`) = `snapshot → snapshot_scope_complete → adverse_increment → envelope_bound_not_enlarged → risk_decision` 1회 · `ActionFlowGovernor.decide`(`risk/flow.py:288-365`) = `scope_graph_complete → cause_lineage_complete → amplification_bounded → envelope_not_enlarged → atomic_economic_flow_coverage → action_flow_decision` 1회 · `Recording*` 래퍼(`compose/context.py:211-260`) · permit 은 RCL `command_id` UNIQUE 로 단일 사용(`flow.py:14-22`) | **판정은 전부 있다.** 없는 것은 입력 생산자 |
| 입력 원천 | `AggregateRiskDecisionInputs`(`aggregate.py:221-263` 15필드) · `ActionFlowDecisionInputs`(`flow.py:142-182` 27필드) · 프로덕션 호출부 **0**(`run` 은 `compose_paper_runtime` 미호출) · 테스트가 손으로 짓는 값: `tests/compose/test_compose_root.py:60-176` | 구조 파생 가능 필드 vs 정책 선언 필드 vs 원천 없는 필드를 갈라야 함(§2.1 표) |
| 이미 구조적 | `snapshot.consistency_cut_identity` = RCL 투영 last seq(`aggregate.py:302-367`) · `generation_current` = `tos.afg.generation_fenced(decision_generation, RCL tip)`(`_risk_attestations.py:271-291`) · 6 attestation 필드 `_restrictive_merge`(`_risk_attestations.py:195-209` · `numerically_safe`·`valuation_ok`·`all_fields_attributed`·`limit_source_is_injected_envelope`·`economic_commitment_exclusive`·`flow_commitment_exclusive`) | 재사용 · 재발명 0 |
| 원천 없는 필드 | `cells`(`ProjectedCell` 5 크기 전부 호출자) · `snapshot.conservative_current_usage` = 빈 `CapacityVector()`(«RCL 투영에 크기 없음» `aggregate.py:15-22`) · `cause`/`snapshot`/`observed_amplification`(afg) · `committed_flow_vectors`·`economic_ref`·digest 들 · `policy` 둘 다 None(발행된 인스턴스 0 · EVL3 PILOT `aggregate_risk_policy_id: null`) | 본 웨이브의 생산 대상 |
| 재사용 가능한 관측 원천 | `EvidenceReceiptReader.receipts(scope)` → `EgressReceiptObservation{attempt_id, account, instrument, egress_result_kind, filled_quantity, remaining_quantity, finality_proof_recorded}`(`recon/ports.py:142-162` · `EGRESS_RESULT_CONSUMED`/`RESULT_UNMATCHED` 행) · `WitnessSnapshot.positions/cash` 필드는 있으나 미채움(`ports.py:120-121`) · `SqliteEventInbox.unconsumed_count()`/`count()`/`last_composite`/`replay`(`engine/inbox.py`) · `SqliteCommitLog.reservation_rows()`/`command_id` 행(`rcl/log.py:564-684`) · `ReservationProjectionReader`(상태 enum · 크기 0/1 · `_safety_wiring.build_capacity_owner`) · `recovery/reconciliation.py` `event_id → attempt_id → reservation_id` 공식 · 단조/벽시계 `TrustworthyTimeService` · step 2 `CandidateConstruction.derivation`/`command`(수량 실값) · step 5 `EconomicEffectStage.envelope`(rcl `CapacityVector`) | 포지션 = **evidence 의 체결 합**(브로커 조회 0 · 단일 원천) · 동시성 = 인박스/attempt 관측 · 명령 효과 = 구성 실값 |
| 없는 것(정직) | 포지션/PnL/노출 원장 0 · 브로커 잔고/포지션 조회 0(P-BAL 은 레거시 프로브 · `tos_runtime` 밖) · 시나리오 셀 생성기 0 · 승인된 `risk.yaml`/`risk_attestations.yaml` 0(예시는 전부 null) · Adverse Scenario Set 실인스턴스 0(EVL3 PILOT 은 ARE 사용 명시 배제) · 시가 평가(마크) 원천 0 | 가치 평가 차원(GROSS/NET_NOTIONAL)은 불가 · **계약 수 차원**만 구조적 |
| 어휘 | `RiskDimensionKind` 11(`are/vocabulary.py:46-67` · `LONG_SHORT_DELTA_DIRECTIONAL` 포함) · `RiskScopeKind` 12 · `AdverseScenarioKind` 9 · `ProjectedCell` None 전파(`are/records.py:135-215`) · `adverse_increment` 는 셀 0/커버리지 미달/None 이면 UNKNOWN(`predicates.py:334-394`) · `risk_decision(policy=None 허용 · digest None)`(`:647-720`) · afg: `amplification_bounded(envelope, observed)` 양쪽 None ⇒ False · `concurrent_consumers_share_one_envelope is not True ⇒ False`(`afg/predicates.py:346-353`) · `cause_lineage_complete` = root 실값 ∧ `lineage_attested is True` ∧ `cyclic is False` ∧ `forked_beyond_bound is False` ∧ `inconsistent is False`(`:364-394`) · `scope_graph_complete(snapshot None ⇒ False)` · `atomic_economic_flow_coverage(economic_ref None/TBD ⇒ UNKNOWN)` | GRANT 도달 조건이 명확 · 각 bool 은 관측 또는 정책 선언이어야(리터럴 0) |
| 템플릿 | `AGGREGATE-RISK-POLICY`·`AGGREGATE-RISK-STATE-SNAPSHOT`·`AGGREGATE-RISK-DECISION`·`ADVERSE-SCENARIO-SET`·`ACTION-FLOW-POLICY`·`ACTION-FLOW-STATE-SNAPSHOT`·`ACTION-FLOW-DECISION`·`ACTION-FLOW-PERMIT` 전부 존재(`verification/`) · spg `BundleMemberKind.AGGREGATE_RISK_POLICY`/`ACTION_FLOW_POLICY`(`spg/vocabulary.py:217,219`) · 커널 `AggregateRiskPolicy{policy_id, policy_generation, policy_version, governed_dimensions, governed_scopes, signer_identity, approval_identity, evidence_package_ref}`(`are/records.py:304-352`) · `ActionFlowPolicy`(`afg/records.py:362`) | 인스턴스 = 템플릿 형상 + `_model_view`/`_runtime`(DR-0002 관용구 · venue 로더 재사용) |
| 픽스처 관용구 | ARE 차원 id `f"{scope}::{dimension}"` · AFG `"afg.ORDER"` · `safety_envelope.yaml` `governed_dimensions.envelope_max`(`tests/compose/conftest.py:182-215`) · `grant_shaped_*`(`tests/risk/conftest.py:236-370`) | 차원 id 규약을 정책 인스턴스가 선언 · HSE 와 일치 교차검사 |
| 크기 | `_wiring.py` 1122(등재) · `cli.py` 980 · `_dimension_readers.py` 885 · `context.py` 878 · `root.py` 449(`compose_paper_runtime` 311 등재) | 새 모듈로 · `cli.py` 문언만 |

## 1. 목표 · 범위 · 비범위

**목표**: 두 제공자를 런타임 서비스가 **구조적 관측 + 거버넌스 정책 인스턴스**로 공급해 `run` 차단 (b) 를 닫는다. 판정은 기존 커널 술어·서비스 그대로. 합성 paper e2e 에서 **step 6/7 GRANT 가 손으로 지은 리터럴 없이** 도달하고, 원천 없는 사실은 None 으로 남아 커널이 UNKNOWN 을 내는 것을 실증한다.

**범위**: (S) DR-0003(ARE/AFG 정책 인스턴스에 DR-0002 경로 확장 · 포지션 관측의 단일 원천 공시) · (a) `tos_runtime/riskstate/{policies,position,flow_observation}.py` · (b) `riskstate/service.py` + `compose/_riskstate_wiring.py` + `root.py`(제공자 인자 기본값 = 서비스) + e2e · (c) 문서(`cli.py` 차단 목록 (b)→해소 · README · INDEX · §7) · 실파일 제안표(§6 ②: `risk.yaml`·`aggregate_risk_policy.yaml`·`action_flow_policy.yaml`).

**비범위**: 커널 편집(포지션 술어 패키지는 라운드 #4 후보) · 브로커 잔고/포지션 조회 transport(P-BAL 결선 — 별도 웨이브) · 시가 평가/명목 차원 · marketfeed(틱 원천 (c)) · `envelope`/`price`/`order_shape` 원천((a′)) · 투영 필드군.

## 2. 결정

### 2.1 입력 필드별 원천 분류(정직 표 — 레인 a/b 는 이 표 밖의 값을 만들지 않는다)

| 필드 | 원천 | 방식 |
|---|---|---|
| ARE `required_scenario_kinds`·`required_scopes`·`applicable_risk_scopes`·`effective_limit`·`policy` | **정책 인스턴스** `aggregate_risk_policy.yaml`(템플릿 + `_model_view{policy_generation, policy_version, governed_dimensions[{dimension, scope, unit, limit_source, …}], governed_scopes[]}` + `_runtime{dimension_ids{…}, effective_limits{dimension_id: magnitude}, required_scenario_kinds[], required_scopes[], applicable_risk_scopes[]}`) → `AggregateRiskPolicy.issue(...)` 실 digest · 활성화 `members:` `AGGREGATE_RISK_POLICY` 정확 일치 | 거버넌스 문서 |
| ARE `injected_envelope_max` | 이미 로드된 Hard Safety Envelope 의 `governed_dimensions[dimension_id].envelope_max`(spg) — 정책의 `dimension_ids` 와 **일치 교차검사**(HSE 에 없는 차원을 정책이 통치하면 부팅 거부) | 구조 파생 |
| ARE `cells[*].max_credible_command_effect` | step 2 `CandidateConstruction.derivation` 의 산출 수량(계약 수 · `command` 실값) — attempt 당 | 구조 파생 |
| ARE `cells[*].conservative_current_usage` = `…_already_committed` | **포지션 관측**(§2.2): 내구 evidence 의 체결 합(확정) + 미확정 attempt 전량(보수) — 계약 수 · scope 별 | 구조 파생(단일 원천 공시) |
| ARE `cells[*].required_concurrent_overlap_effect` | in-flight attempt 들의 봉인 수량 합(§2.3 관측) | 구조 파생 |
| ARE `cells[*].effective_limit` | 정책 `effective_limits` | 거버넌스 문서 |
| ARE `grant_identity`·`effect_digest`·`lineage_ref` | attempt id · step 5 `EconomicEffectStage.envelope` 의 scheme digest · 인박스 event id | 구조 파생 |
| ARE 6 attestation(위 표 §0) | 기존 `risk_attestations.yaml` + `_restrictive_merge` **불변** | 운영자 확인(기존) |
| AFG `policy`·`required_scopes`·`applicable_action_flow_scopes`·`injected_envelope_max`·`hard_limit`·`runtime_limit`·`decision_effective_limit`·`scope_independence`(8 bool)·`action_class_map`·`concurrent_consumers_share_one_envelope`·`envelope_reset_on_duplicate`·`duplicate_event_created_new_allowance` | **정책 인스턴스** `action_flow_policy.yaml`(`_model_view{policy_generation, policy_version, …}` + `_runtime{flow_dimension_id, limits{…}, scope_independence{scope, 8 bool}, action_class_map{NEW_LONG: NORMAL_NEW_RISK, …}, deployment_facts{concurrent_consumers_share_one_envelope, envelope_reset_on_duplicate, duplicate_event_created_new_allowance}}`) · 활성화 `ACTION_FLOW_POLICY` | 거버넌스 문서 — **선언이지 관측이 아님**을 파일 헤더·evidence 에 공시 |
| AFG `cause` | 인박스: `root_cause_identity` = 이 attempt 를 낳은 event id · `parent_lineage` = (proposal id,) · `lineage_attested` = 내구 인박스에서 직접 읽었음(구조) · `cyclic` = root ∈ lineage 검사 · `forked_beyond_bound` = 같은 root 의 attempt 수 > 봉투 `max_attempts` · `inconsistent` = lineage 항목이 인박스/evidence 에 없음 · `command_identity/digest` = 구성 실값 | 구조 파생 |
| AFG `snapshot` | `ActionFlowStateSnapshot.issue(covered_scopes=정책, scope_independence=정책, consistency_cut_identity=RCL tip seq, snapshot_generation=RCL tip)` — attempt 당 발행 · evidence | 발행(정책 선언 + 구조 컷) |
| AFG `observed_amplification` | `fan_out` = 이 event 가 낳은 attempt 수 · `depth` = lineage 길이 · `attempts`/`mutations` = 같은 root 의 봉인된 attempt 수 · `queries` = 0 **구조 사실**(transport 에 조회 경로 없음 — AST 핀으로 고정 · 조회 경로가 생기면 핀이 깨져 재작업 강제) · `queue_depth` = `inbox.unconsumed_count()` · `in_flight` = 비종결 attempt 수 · `elapsed_monotonic` = 시간 서비스 단조 − root event 의 처리 시작 단조(`handling_started_receipt`) · `duplicate_redelivery_expansion` = 인박스 dedup 거부 수(KR3 서명 · API 없으면 evidence 행 계수) · `failover_reconnect_replay_expansion` = 복구 replay 수(W1 `RecoveryInputs`) · `amplification_per_cause` = attempts / 1 · 3 bool = 정책 선언 | 구조 파생 + 선언 |
| AFG `requested_limit`·`flow_vector` | `CapacityVector(flow_dimension_id, 1)` — 명령 1 = 브로커 변이 1(구조) | 구조 파생 |
| AFG `committed_flow_vectors` | RCL 로그의 미소비 permit 행 벡터(`flow.py` `build_permit` 행 형상 — 레인 a 실측) | 구조 파생 |
| AFG `economic_ref` | 이 attempt 의 경제 예약 정체성(`rcl/reservation_identity.py` 공식 — step 9 가 결속할 그 id · 레인 a 실측: step 7 시점에 결정 가능한지; 불가하면 None → UNKNOWN 공시) | 구조 파생/공시 |
| AFG `decision_generation` | RCL tip(`_rcl_tip_generation_provider` 공유 — `generation_fenced` 가 등식이므로 같은 원천) | 구조 파생 |
| AFG digest 들 | `command_digest` 구성 실값 · `cause_digest`/`lineage_digest`/`amplification_envelope_digest` = scheme digest(순수) · `protective_classification_digest` 기존 provider | 구조 파생 |

### 2.2 포지션 관측(`riskstate/position.py` · 순수 함수 + 읽기 어댑터)

- `PositionObservation{scope_key, confirmed_net: Decimal, unknown_buy: Decimal, unknown_sell: Decimal, in_flight_buy: Decimal, in_flight_sell: Decimal, attempts_seen: int, sources: ("evidence:EGRESS_RESULT_CONSUMED", "evidence:<seal kind>")}` — 계약 수 · 단일 원천(내구 evidence) · 브로커 증인 없음 → `all_fields_attributed` 는 기존 attestation 그대로(이 서비스가 True 를 만들지 않음).
- 확정 = `EgressReceiptObservation.filled_quantity` × side 부호(side/수량은 커널 게이트웨이의 **`SEND_SEALED`** evidence 행의 `send_seal.outbound_side/outbound_quantity` — `compose/_transport_wiring.py:344-383` 이 같은 행을 이미 읽음 · 레인 a 가 페이로드 형상 실측) · 미확정 = `RESULT_UNMATCHED`/결과 없음 attempt 의 봉인 수량 전량 · in-flight = 봉인됐고 종결 결과 없음.
- **보수 사용량**(순수 함수 `worst_credible_directional_usage`): `max(|confirmed_net + unknown_buy + in_flight_buy|, |confirmed_net − unknown_sell − in_flight_sell|)` — 미확정을 양 방향 최악으로. `conservative_current_usage` = 이 값 − in-flight 항(in-flight 는 `required_concurrent_overlap_effect` 로 별도) · property test: 미확정 추가는 사용량을 줄이지 못한다 · 대칭(long/short 미러).
- 이는 **관측 집계**이지 판정이 아니다(`SessionFactsOwner` 가 캘린더 데이터를 위상 토큰으로 읽는 것과 같은 층). 커널 `position` 술어 패키지는 라운드 #4 후보로 등재(§6 ④).

### 2.3 동시성 관측(`riskstate/flow_observation.py`)

인박스·evidence·RCL 읽기(원시 SQL 관용구 `ack.py`/`witness_synthetic.py`) → `FlowObservation{queue_depth, in_flight, attempts_for_cause, duplicates_rejected, replays, root_event_seq, handling_started_mono}` · 순수 변환 `to_observed_amplification(obs, policy_facts, elapsed)` · `to_action_cause(...)`.

### 2.4 서비스·결선

- `riskstate/service.py::RiskStateService(loaded_are_policy, loaded_afg_policy, hse_envelope, scenario_set(risk.yaml), position_reader, flow_reader, construction_stage_reader, effect_envelope_reader, rcl_tip_reader, time_service, evidence_store, scheme)` · `aggregate_inputs_for(request) -> AggregateRiskDecisionInputs | None` · `action_flow_inputs_for(request) -> ActionFlowDecisionInputs | None` · attempt 당 evidence `RISK_STATE_OBSERVED`(포지션 관측 + flow 관측 + absent_fields) · 부팅 evidence `AGGREGATE_RISK_POLICY_BOUND`/`ACTION_FLOW_POLICY_BOUND`.
- `compose/_riskstate_wiring.py::build_risk_state_service(...)` · `root.py`: `aggregate_risk_inputs_provider`/`action_flow_inputs_provider` 를 **`| None = None`** 으로 — None 이면 서비스 제공자(프로덕션 기본) · 명시 주입은 테스트 seam(유지) · 기존 `wrap_*` 래퍼는 그대로 서비스 출력을 감쌈(attestation 병합·`generation_current` 파생 불변).
- `ComposedRuntime.risk_state: RiskStateService`.

### 2.5 실파일·정책 인스턴스

- `risk.yaml`(AdverseScenarioSet + 증폭 봉투) 은 제안표 §2/§3(`2026-09-12-tos-operator-value-proposals.md`) 값으로 실파일 후보(§6 ②) · `aggregate_risk_policy.yaml`/`action_flow_policy.yaml` 인스턴스 값도 §6 ② 표 · 테스트는 픽스처 문서(`tests/riskstate/_documents.py`).
- 활성화: `safety_activation.yaml` `members:` 에 `AGGREGATE_RISK_POLICY`/`ACTION_FLOW_POLICY` 추가 · `print-policy-digests` 가 4 정책 digest 출력(확장).

### 2.6 `run` 차단 목록

(b) → **해소**(구조 관측 + 정책 인스턴스) · 신설 (b′): 포지션은 내구 evidence 단일 원천(브로커 증인 0 · 독립성 부재 → `all_fields_attributed` attestation 의존) · 명목/마진 차원 0(마크 원천 없음) · Adverse Scenario Set 실인스턴스는 운영자 채택 대기.

## 3. 기각 대안

| 대안 | 기각 사유 |
|---|---|
| 리터럴 `True` 로 3 bool·lineage_attested 채우기 | M6 계열 팬텀. 관측(구조) 또는 정책 선언(문서·evidence 공시)만 |
| 브로커 P-BAL 조회를 이 웨이브에 결선 | transport 에 조회 경로 0 · 레거시 프로브 코드 이식은 방화벽 위반 · 별도 웨이브 |
| GROSS/NET_NOTIONAL 차원 통치 | 마크 원천 0 → 전부 UNKNOWN 인 정책은 공허. 계약 수 차원만 정직 |
| 제공자 인자 삭제(서비스 강제) | 기존 e2e 의 시나리오 주입 seam 이 사라짐 · None 기본값이면 프로덕션은 서비스, 테스트는 선택 |
| `queries=0` 을 정책 선언으로 | 코드 구조 사실이므로 AST 핀이 더 강함(조회 경로 신설 시 강제 재작업) |

## 4. 레인 · 파일 소유권 · 순서

| 레인 | 파일 | 결정 | 순서 |
|---|---|---|---|
| S(세션 모델) | `tos-spec/src/decision-records/DR-0003-….md` · `SUMMARY.md` | 2.5 | 선행(병렬) |
| a(executor) | `tos_runtime/riskstate/{__init__,policies,position,flow_observation}.py` · `tests/riskstate/{_documents,conftest,test_policies,test_position,test_flow_observation,test_structural_pins}.py` | 2.1~2.3 | 먼저 |
| b(executor) | `riskstate/service.py` · `compose/_riskstate_wiring.py` · `root.py` · `_types.py` · `cli.py`(`print-policy-digests` 확장 + 차단 목록) · `tests/compose/{conftest,test_riskstate_wiring,test_compose_root}.py` · `config/tos_size_budget.yaml`(드리프트) | 2.4·2.6 | a 뒤 |
| c(세션 모델) | README · INDEX · §7 · 실파일(§6 ② 채택 시) | — | b 뒤 |
| 리뷰 | `code-reviewer`(sonnet) · 뮤테이션 표 필수 · **리뷰 중 레인 편집 지시 금지** | §5 | 각 PR |

규율은 venue 계획 §4 와 동일(방화벽·예산·극성·None·사적 속성 0·헝크 스테이징). 로더는 `tos_runtime/venue/_policy_primitives.py` 재사용(중복 0 · 필요 시 `_policy_primitives` 를 `tos_runtime/governance/` 로 승격은 **하지 않음** — import 만).

### 4.1 레인 a 인터페이스(고정)

```python
# riskstate/policies.py
AGGREGATE_RISK_POLICY_CONFIG_NAME = "aggregate_risk_policy.yaml"; ACTION_FLOW_POLICY_CONFIG_NAME = "action_flow_policy.yaml"
@dataclass(frozen=True) class LoadedAggregateRiskPolicy: policy: AggregateRiskPolicy; dimension_ids: Mapping[tuple[RiskScopeKind, RiskDimensionKind], str]; effective_limits: CapacityVector; required_scenario_kinds: frozenset[AdverseScenarioKind]; required_scopes: frozenset[RiskScopeKind]; applicable_risk_scopes: tuple[str, ...]; unit: str
def load_aggregate_risk_policy(path, *, scheme) -> LoadedAggregateRiskPolicy
@dataclass(frozen=True) class LoadedActionFlowPolicy: policy: ActionFlowPolicy; flow_dimension_id: str; limits: {hard_limit, runtime_limit, envelope_max, decision_effective_limit}: CapacityVector; scope_independence: ScopeIndependenceEvidence; covered_scopes: tuple[ActionFlowScopeKind, ...]; required_scopes: frozenset[ActionFlowScopeKind]; applicable_action_flow_scopes: tuple[str, ...]; action_class_map: Mapping[ActionClass, ActionClassKind]; deployment_facts: DeploymentFlowFacts(3 bool)
def load_action_flow_policy(path, *, scheme) -> LoadedActionFlowPolicy

# riskstate/position.py
@dataclass(frozen=True) class PositionObservation: ...(§2.2)
def worst_credible_directional_usage(obs) -> Decimal            # 순수
class EvidencePositionReader: def __init__(self, evidence_store, *, account, instrument); def observe(self) -> PositionObservation

# riskstate/flow_observation.py
@dataclass(frozen=True) class FlowObservation: ...(§2.3)
class InboxFlowReader: def __init__(self, inbox, evidence_store, rcl_log); def observe(self, *, root_event_id, attempt_id) -> FlowObservation
def to_observed_amplification(obs, facts: DeploymentFlowFacts, *, elapsed_monotonic: Decimal | None) -> ObservedAmplification
def to_action_cause(obs, *, root_event_id, proposal_id, command_identity, command_digest, max_attempts) -> ActionCause
```

## 5. 종료 조건 · 실증 · 뮤테이션

- 실증(레인 b e2e · 커널 판정 실호출): (1) 정책 2 + `members:` 로 부팅 → `*_POLICY_BOUND` 각 1 · 제공자 미주입 → 첫 attempt step 6 **GRANT**·step 7 **GRANT**(빈 evidence: 포지션 0 · 명령 효과 = 수량 · 한도 내) · `RISK_STATE_OBSERVED` 1 (2) 체결 evidence 를 심은 뒤(합성 transport 결과) 두 번째 attempt: `conservative_current_usage` 가 체결 합 · 한도 초과 시 step 6 **DENY** (3) `RESULT_UNMATCHED` attempt 1 심기 → 미확정 전량이 보수 사용량에 포함(GRANT→DENY 전환 경계 테스트) (4) 봉투 `max_in_flight` 1 에서 in-flight 1 이면 step 7 DENY (5) 정책 차원이 HSE 에 없음 → 부팅 거부 (6) `members:` 불일치 → 부팅 거부 (7) 미러(NEW_SHORT) 대칭: 포지션 부호만 반전 (8) 명시 주입 제공자는 그대로 동작(기존 e2e 불변) (9) `run` 파싱 전용 + 목록 (b)→(b′).
- 뮤테이션(리뷰어 실행): M1 `worst_credible_directional_usage` 가 미확정을 무시 → red · M2 `lineage_attested=True` 를 인박스 판독 없이 반환 → red(인박스에 없는 root 로 부팅한 attempt 는 `inconsistent`) · M3 `queries` 를 조회 경로 없이도 1 → AST 핀/red · M4 정책 `deployment_facts` 를 코드 상수로 대체 → grep/AST 핀 red · M5 `injected_envelope_max` 를 정책 한도로 대체(HSE 미참조) → HSE 불일치 부팅 테스트 red · M6 `committed_flow_vectors=()` 고정 → 실증 (4) red · M7 `economic_ref` 를 attempt id 문자열 상수로 → 결속 핀 red · M8 attestation 병합 우회(서비스가 `numerically_safe=True` 직접) → `_restrictive_merge` 경로 핀 red · M9 `decision_generation` 을 1 고정 → `generation_fenced` red · M10 `RISK_STATE_OBSERVED` 의 `absent_fields` 누락 → red · M11 provider None 기본에서 서비스 대신 예외 → 부팅 red · M12 포지션 판독 SQL kind 오타 → «빈 evidence = 0» 핀이 아닌 «심은 체결이 반영» 핀 red.
- 검증 명령·정직 상태: venue 계획 §5 와 동일 + `tests/risk` 불변. 예상 정직 상태: 포지션 단일 원천(브로커 증인 0) · 명목/마진 차원 0 · 실인스턴스 값 대기 · `run` 은 (a′)(c) + (b′) 로 계속 차단.

## 6. 운영자 확인

1. **DR-0003 수용**(머지 = 수용 · DR-0002 관용구).
2. **실파일 값(표 단위 채택/수정/보류)**: `risk.yaml` = 제안표 §3(`2026-09-12-tos-operator-value-proposals.md:44-51` 그대로): `max_amplification_per_cause` **3**(A · VER-002:1028) · `max_in_flight` **1** · `max_fan_out/max_depth/max_attempts/max_mutations` **4/3/2/3** · `max_queries/max_queue_depth` **8/8** · `max_elapsed_monotonic` **30000** · `max_duplicate_redelivery_expansion/max_failover_reconnect_replay_expansion` **1/1** · `scenario_set_id/scenario_set_generation/policy_binding_id` **`paper-adverse-set-1`/1/`paper-risk-policy-1`** · `covered_scenario_kinds`=`required_scenario_kinds`=**`[ADVERSE_PRICE_SLIPPAGE_GAP_VOL_LIQ]`**(생산자 있는 유일 종류 — 본 웨이브의 셀 생산자가 그 종류 1개를 채움; 다른 종류를 required 에 넣으면 정직하게 영구 UNKNOWN) · `max_queries 8` 은 봉투 상한이고 관측값은 구조적 0(§2.1) · `aggregate_risk_policy.yaml` = 차원 `INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL`(단위 CONTRACTS) 한도 **`1`**(paper · 계약 1 · 「실 선물 계좌 무입금」 규칙과 정합) · scope INSTRUMENT · 시나리오 커버리지 = `risk.yaml` 의 `required_scenario_kinds` · `action_flow_policy.yaml` = `afg.ORDER` 한도 hard/runtime/envelope **1** · scope_independence 8 bool(단일 계좌·단일 브로커·단일 라우트 배포 사실 — 선언) · `action_class_map` NEW_LONG/NEW_SHORT/INCREASE→NORMAL_NEW_RISK · DECREASE/CLOSE/REDUCE_ONLY→(커널 `ActionClassKind` 의 축소 클래스 — 레인 a 실측) · 3 deployment bool = (False, False, True).
3. `members:` 4 정책 digest 운영자 수동(`print-policy-digests`).
4. 커널 라운드 #4 후보 추가: `tos.position`(체결 합·보수 사용량 술어) · RCL 예약 행에 committed 벡터 영속(`aggregate.py:15-22` 가 지목).
5. 다음 웨이브 순서: (c) 틱 원천/marketfeed → (a′) envelope/price/order_shape → 브로커 증인(P-BAL) / band 원천.

## 7. 착지 기록

(레인 착지 후 기입)
