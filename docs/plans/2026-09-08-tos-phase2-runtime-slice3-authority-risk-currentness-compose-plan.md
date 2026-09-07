# TOS Phase 2 런타임 슬라이스 #3 — Safety Authority + IAP (순서 4) · ARA + AFG (순서 5) · currentness/quorum + release-admission (순서 6) · composition root

- **상위**: 설계 #40(운영자 비준 2026-09-08) §5 순서 4~6 · D1.1 «composition root 는 `tos_runtime.compose` 단 하나» · 개발계획 §6 Phase 2 종료 조건(«stand-in 없이 steps 4, 6~10, 13~14 실행 · kill -9/재기동 후 보수적 복구 · quorum/currentness 상실 시 신규 위험·send 거부 · 권위 상태와 운영자 투영 불일치 경보»)
- **선행 착지**: 슬라이스 #1(`ba7d438f`·`1872af9d`) · #2(`278062e3`·`42f8cbf5`·`95f5c880`) · 커널 포트 수정(선택지 (a) · 레인 O · 별 커밋)
- **저작**: 세션 모델 단독 · **권한 부여 없음** · EV 행 상태 변경 없음 · 실 브로커 transport 0(합성만)
- **서베이 실측(2026-09-08)**: `authority/iap/afg/are/cur/sci/liveauth` 는 Protocol 0 인 순수 레코드+술어 패키지 — 런타임은 **입력을 모아 술어를 호출**하고 결과를 `engine`/`rcl`/`egressgw` 심에 넣는다. 런타임이 채울 심: engine `Stage`(steps 4·6·7·8·9·10·13·14 — `standins.py` 대체) · `Transmit` · `EvidenceSink` · gateway `SendBoundaryContext` 의 provisional 필드(item 3·14·15; item 6·12 는 P0-2 프로파일 인스턴스 = Phase 4) · deferred item 4·5·7·8·9·10(safety-governance mesh = Phase 5 소관, 이 슬라이스 밖 · `UNKNOWN`→deny 유지).

## 0. 공통 규율

슬라이스 #1 §0 그대로 + 다음:
- **판정은 커널 술어만 한다.** 런타임 서비스에 «자체 비교로 admit» 하는 자리가 있으면 결함(슬라이스 #1 리뷰 기준).
- 권위를 만드는 모든 상태 전이(epoch·permit·approval consumption·capability nonce)는 **RCL `CommitLog` 항목**이다 — 메모리·별 파일 금지(ADR-002-012 :489 «every committed transition emits evidence» · IAP state.py:83 «linearizable transaction» · afg records.py:618 «rcl owns production»).
- 단일 노드 «quorum» = 자기 자신 + writer epoch. `R-RCL-F0` 가 이미 등재 — 각 서비스 docstring 이 그 행을 인용하고 **quorum 을 주장하지 않는다**(«QuorumCommitCertificate» 는 egress 소유 · 여기서는 단일 노드 인증서로 정직 표기).
- 모든 서비스는 `TrustworthyTimeService.current_snapshot()` 이 없거나 TRUSTED 가 아니면 새 위험을 admit 하지 않는다(`state_permits_new_normal_risk`).

## 1. 레인 P — `tos_runtime.authority` (순서 4: Safety Authority + IAP)

**소비(커널)**: `tos.authority` — `AuthorityEpochState`·`CurrentnessWitness`·`CapabilityValidityInputs`·`RearmChecklist` · 술어 `authority_epoch_current`/`authority_epoch_fenced`/`currentness_admissible`/`permissive_capability_valid` · 레코드 `SafetyAuthorityCapability`·`AuthorityEpochTransitionRecord`. `tos.iap` — `ProposalApprovalRequest`·`IndependentApprovalDecision`·`ApprovalConsumptionRecord`·`TradingApprovalPolicy` · `exact_binding_holds` · `consumption_transition` · `invalidation_closure`. `tos.engine.sequencer.Stage`·`StageRequest`·`StageVerdict`.

**산출물**
1. `tos_runtime/authority/epoch.py` — `SafetyAuthorityEpochService(log: SqliteCommitLog, time: TrustworthyTimeService, evidence)`: 권위 epoch 는 RCL 항목(`kind` = 기존 `CommandType` 중 적합한 것 — 없으면 보고)으로 발급/전이(`AuthorityEpochTransitionRecord` 를 payload 로) · `current_state() -> AuthorityEpochState` 는 `read_linearizable` 에서 파생(캐시 0) · **writer epoch 와 authority epoch 는 별 값**(설계 #40 v1.1 ②) · `witness() -> CurrentnessWitness` 는 time 스냅샷 TRUSTED + 마지막 선형화 읽기 나이 ≤ 설정 bound(`MAX_authority_currentness_containment_ms` — VER 키 이름 실측해 그대로 · null=named-TBD) 에서만 `present=True` · 온라인 검증 상실(스냅샷 만료·epoch 읽기 실패) 시 `present=False` → 커널 `currentness_admissible` 가 거부(ADR-002-003 :183).
2. `tos_runtime/authority/capability.py` — `capability_valid(cap: SafetyAuthorityCapability) -> bool` 는 `CapabilityValidityInputs` 를 RCL/커스터디/시간에서 모아 `permissive_capability_valid` 호출만.
3. `tos_runtime/authority/iap.py` — `IntentRegistry(log, evidence)`: `propose(request: ProposalApprovalRequest)`·`approve(decision: IndependentApprovalDecision)`·`consume(command_identity, command_digest)` — **한 RCL 트랜잭션**(`append_cas` 1회 = consumption 항목) 안에서 `exact_binding_holds` + `consumption_transition` 통과 시만 `ApprovalConsumptionRecord` 를 payload 로 append · 같은 approval 2회 소비 = 거부(로그가 강제 · 메모리 플래그 아님) · Phase 2 의 «독립 승인자» 는 **운영자 파일 승인**(custody 와 같은 0600 규율의 승인 파일 `approvals/<proposal_digest>.yaml` 을 읽어 `IndependentApprovalDecision` 을 구성 — 자동 승인 코드 0 · DR-0001 단일 운영자 변형 §17.1 인용).
4. `tos_runtime/authority/stages.py` — engine `Stage` 구현 `IndependentApprovalStage`(step 4): `StageRequest` 에서 proposal digest 를 읽어 registry 조회 → 커널 `StageVerdict`(ADMIT 는 consumption 성공 시만 · UNKNOWN/DENY 그대로) · gateway item 14 필드(`approval_consumed_for_this_intent`·`approval_intent_binding_digest`) 공급 함수.

**장애 계약**: 스냅샷 만료 → witness present=False → 모든 capability 무효 · epoch 읽기 실패 → UNKNOWN(admit 0) · 승인 2회 소비 거부 · 승인 파일 모드/라벨 위반 거부 · 재기동 후 소비 기록은 로그에서 복원(메모리 아님).

## 2. 레인 Q — `tos_runtime.risk` (순서 5: ARA + AFG · steps 6·7·8·9·10)

**소비(커널)**: `tos.are` — `AggregateRiskStateSnapshot`·`AdverseScenarioSet`·`ProjectedCell`·`AggregateRiskDecision` · `risk_decision`. `tos.afg` — `ActionFlowStateSnapshot`·`ActionFlowDecision`·`ActionFlowPermit`·`ScopeIndependenceEvidence`·`ActionCause`·`ActionAmplificationEnvelope` · afg 술어. `tos.rcl` — `CapacityVector`·`TransmissionCapability`·`CommittedReservation` · `SqliteCommitLog`·`ReservationProjectionReader`.

**산출물**
1. `tos_runtime/risk/aggregate.py` — `AggregateRiskService(projection, scenarios: AdverseScenarioSet(설정 주입 · 값 null=named-TBD → 서비스 기동 거부), evidence)`: `snapshot()` 은 RCL 투영에서 `AggregateRiskStateSnapshot` 을 **파생**(자체 합산 0 — `CapacityVector` 연산은 rcl 소유) · `decide(proposal) -> AggregateRiskDecision` 은 `risk_decision` 호출만 · 결정은 evidence 로 append(decision_id ⊥ digest).
2. `tos_runtime/risk/flow.py` — `ActionFlowGovernor(log, evidence, envelope: ActionAmplificationEnvelope(설정))`: `decide(cause: ActionCause, snapshot) -> ActionFlowDecision`(afg 술어) · **permit 발급 = RCL 항목**: `ActionFlowPermit` 을 `append_cas`(payload) 로 커밋 · `claim_nonce` 단일 사용은 로그의 `command_id` UNIQUE + 예약 전이로 강제 · `rcl_commitment_ref` = 그 항목 seq.
3. `tos_runtime/risk/ledger_stages.py` — engine `Stage` 구현: step 6 `AggregateRiskDecisionStage` · 7 `ActionFlowDecisionStage` · 8 `LedgerVerificationStage`(`read_linearizable` + `authority_epoch_fenced`-류 커널 술어로 예약 상태 검증) · 9 `AtomicCommitStage`(**예약 + permit 을 한 `apply_reservation_transition`/`append_cas` 트랜잭션**에서 — 두 항목이 필요하면 «원자성 부재» 를 정직 보고하고 단일 항목 payload 에 둘을 담는 설계로 · 절대 두 트랜잭션으로 나누지 않음) · 10 `CommitmentUnavailabilityStage`(로그 접근 불가/stale epoch → UNKNOWN · 신규 위험 0).
4. gateway item 15 필드(`action_flow_permit_identity`·`action_flow_commitment_current`) 공급 함수.

**장애 계약**: 로그 파일 불가 → steps 8~10 UNKNOWN · stale epoch → 커밋 거부 · 시나리오 설정 null → 기동 거부 · permit 2회 claim 거부 · 재기동 후 permit 상태는 replay 로만.

## 3. 레인 R — `tos_runtime.currentness` + `tos_runtime.release` (순서 6 · steps 13·14 · item 3)

**소비(커널)**: `tos.cur` — `SafetyCurrentnessVector`·`CurrentnessDimension`·`EgressCurrentnessProof`·`RestrictiveFenceRecord` · `proof_admissible`/`race_order_admissible`/`broker_reachable_not_authority`. `tos.sci` — `software_deployment_ok_verdict`·`RuntimeArtifactAttestation`·`ReleaseRestriction`·`AdmissionResult`. `tos.rcl` `TransmissionCapability`. `tos.workload.RuntimeIdentity`.

**산출물**
1. `tos_runtime/currentness/vector.py` — `CurrentnessAssembler(log, time, authority, risk)`: `SafetyCurrentnessVector` 를 각 소유자의 **현재 커밋 revision**(RCL seq · authority epoch · time generation · permit seq)에서 파생 · `restrictive_floors` 는 커널 규칙 · 단일 노드 인증서 `SingleNodeCommitCertificate{writer_epoch, seq, digest}` — «quorum 아님 · R-RCL-F0» docstring.
2. `tos_runtime/currentness/proof.py` — `issue_egress_currentness_proof(attempt) -> EgressCurrentnessProof`: `nonce` = `secrets.token_hex` · `committed_revision` = 발급 시 `read_linearizable().last_seq` · **발급 자체가 RCL 항목**(revocation 이 가능하려면 durable) · `proof_admissible` 로 자기 검증 후만 반환 · gateway item 16 입력.
3. `tos_runtime/currentness/stages.py` — step 13 `AttemptBindVerificationStage`(attempt ↔ 예약·permit·approval digest 결속을 `exact_binding_holds` 계열 커널 술어로) · step 14 `TransmissionCapabilityStage`(`TransmissionCapability{nonce, single_use}` 발급 = RCL 항목 · gateway 의 `capability_nonce` 로 전달) · item 3 `commitment_epoch_current` = `authority_epoch_current`(RCL 현재 epoch) 공급 함수.
4. `tos_runtime/release/admission.py` — `release_admission(identity: RuntimeIdentity, admission: AdmissionResult(설정 파일 · 운영자 서명 없는 Phase 2 는 «ADMIT 가 아닌 값이면 거부» 만), restriction: ReleaseRestriction(설정), currentness_current: bool) -> bool` 은 `software_deployment_ok_verdict` 호출만 · `RuntimeArtifactAttestation.matches` 는 `identity.code_digest` 와 설정의 기대 digest 비교(비교 자체는 커널 술어가 하면 그것을 쓰고, 없으면 «단순 동등 비교 = 런타임 입력 수집» 으로 docstring 명시).

**장애 계약**: 시간 스냅샷 비-TRUSTED → 벡터 발급 거부 · 발급 후 RCL revision 전진(revocation) → `proof_admissible` 거부 · nonce 재사용 거부(로그) · 기대 code_digest 불일치 → release 거부 · restriction 미해결 → 거부.

## 4. 레인 S — `tos_runtime.compose` (P·Q·R 착지 후 · 순차)

1. `tos_runtime/compose/root.py` — `compose_paper_runtime(config_dir: Path, data_dir: Path, custody_root: Path, environment_label: str) -> ComposedRuntime`: 유일한 결선 자리. 순서: custody → evidence store(FileKeyProvider) → emergency log → time service(start) → RCL log(acquire_epoch · generation seed) → authority epoch service → intent registry → risk services → currentness → release admission(거부 시 기동 중단) → engine `EngineCore(stages={4,6,7,8,9,10,13,14: 실제 Stage; 2,3,5,11: 커널 기존 구현}, ledger=projection 어댑터, transmit=gateway, sink=EngineEvidenceSinkAdapter)` → `BrokerEgressGateway(contexts=resolver, transport=SyntheticPaperTransport, sink=GatewayEvidenceSinkAdapter, ledger=…)`. **SendBoundaryContext resolver** 는 item 3·14·15·16 을 P/Q/R 공급 함수로 채우고 item 6·12 는 provisional 그대로(Phase 4) · deferred 6항목은 그대로.
2. `tos_runtime/compose/cli.py` — 인자 파싱만(`--config-dir --data-dir --custody-root --environment-label` · `os.environ` 0) · 실행은 `run_once(events)` 수준(데몬 루프는 Phase 5).
3. **런타임 e2e 테스트** `tos/runtime/tests/compose/`: 합성 이벤트 → 실제 서비스 체인 → 합성 transport 1회 hand-off → evidence store 와 RCL 로그에 항목 · **재기동(새 프로세스 아님 · 같은 경로 재compose) 후 replay digest 동일** · stand-in 0 실측(`StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL` 을 내는 stage 가 steps 4·6~10·13·14 에 없음) · 시간 스냅샷 비-TRUSTED 강제 시 send 0 · 로그 파일 제거 시 신규 위험 0 · 운영자 투영(`all_reservations`) 과 권위 로그 불일치 주입 시 evidence 에 경보 레코드.

## 5. 레인 간 계약

- P·Q·R 은 서로 파일 교집합 0 · 공통 의존은 슬라이스 #1/#2 공개 API 와 레인 O 의 `CapacityReservationTransition`(scope 필드 포함) 뿐. **서로의 패키지를 임포트하지 않는다** — 교차 입력은 S 가 결선하며 각 레인은 Protocol/콜러블 주입으로 받는다(예: R 의 `CurrentnessAssembler` 는 `authority_epoch_reader: Callable[[], AuthorityEpochState]` 를 받지 `tos_runtime.authority` 를 임포트하지 않는다).
- 새 `CommandType` 이 필요하면 커널 편집 대신 **보고**(kind 는 커널 어휘).
- 설정 키 이름은 VER-002 프로파일 키가 있으면 그대로, 없으면 `named-TBD` 로 예시 YAML 에 등재.

## 6. 종료 조건 (= 개발계획 Phase 2 종료 조건)

- steps 4·6~10·13~14 에서 `NON_AUTHORITATIVE_PROVISIONAL` 0(e2e 실측) · 재compose 후 replay digest 동일 · 비-TRUSTED/로그 불가 시 send 0 · 투영 불일치 경보 evidence
- 런타임 테스트 green · 커널 불변(레인 O 외) · mypy/방화벽/lint-imports/budget/Black/Ruff 0 · 독립 리뷰 approve
- 실 브로커 transport 0 · order 자격증명 0 · EV 상태 변경 0 · quorum 주장 0(R-RCL-F0 인용)
