# 설계 문서 #11 — Degraded-Mode Protective Capacity 계약 (2026-07-25, v1.2)

> **문서 번호 규약**: #1 경계·import-firewall, #2 Decision Context Capsule, #4 Evidence
> Store, #5 Risk Capacity Ledger(RCL), #6 Safety Authority, #7 Live Authorization, #8
> Orthogonal Trading State, #9 Evidence·Reconciliation Confidence, #10 Broker Capability가 이미
> 존재한다(#3은 folded; Trustworthy Time·DSL은 병렬 트랙 A/C로 완료). **#11 = 본 Degraded-Mode
> Protective Capacity 문서**이며 **ADR-002-001**을 실현한다. "protective capacity가 어떤
> **resource domain**에 걸쳐 있고 각 domain이 어떤 **guarantee level**을 갖는지"의 **완전성**과,
> 그 위에서 **protective action classification·degraded-mode 전이·partition-time lease
> admissibility·protective ownership/cancellation·bounded retry**를 결정하는 술어의 **순수·비전송·
> 결정적 데이터 모델 + hypothesis property test**를 그린필드 `tos/src/tos/protective/`에 저작한다.
> **capacity 산술 자체는 저작하지 않는다** — 그것은 rcl(#5)이 이미 소유·구현했다(§3.5 소유권 분할).
>
> **문서 지위**: kis_unified_sts 프로젝트 측 설계 계약. tos-spec에 대해 **non-normative**이며
> 스펙 텍스트(RFC/ADR/템플릿/프로파일)를 **변경하지 않는다.** **broker-agnostic 원칙(project memory
> `tos-spec-broker-agnostic`)**: 본 문서의 규범 텍스트는 **어떤 구체 broker(KIS 포함)도 명명하지
> 않는다.** protective resource domain·guarantee level·classification·degraded-mode·lease
> admissibility 불변식은 전부 broker-agnostic이며, 브로커 제약은 capability class(Broker Capability
> Profile, #10)로만 표현한다.
>
> **선행 문서(의존)**:
> - [설계 #1 — `tos/` 경계 & import-firewall 계약 (v2, 운영자 비준)](2026-07-20-tos-boundary-and-import-firewall-design.md).
>   본 계약의 모든 모델은 §2.4 레이아웃(전용 top-level 패키지)에 놓이고 §3.2 허용목록 안에서만
>   의존한다(§0.3). line 164 "naming은 load-bearing이 아니다 — 내부 세분화는 후속 설계 문서가
>   정의한다"에 따라 본 문서가 `tos.protective` 패키지 내부를 정의한다.
> - [설계 #4 — Evidence Store 계약 (v1.1, 비준·구현됨)](2026-07-20-tos-evidence-store-design.md)
>   + 코드 `tos/src/tos/canonical/`. **canonicalization/digest-binding substrate(`tos.canonical`)·
>   `FrozenModel`(`_base.py:73`)·`DigestBoundArtifact`(`_base.py:98`)·`IndependentIdArtifact`
>   (`_base.py:328`, 이미 core)·`classify_record_pair`(`record_pair.py:52`, 이미 core)·
>   `RecordPairKind`(`record_pair.py:31`)·`ArtifactStatus`(`_base.py:58`)·**이미 core인
>   `CanonicalDecimal`**(`canonicalization.py:134`, export `__init__.py:56` 실측)를 REUSE**한다
>   (재정의 금지). `id=f(digest)` **미채택** 결정을 동형 상속한다(§2.1/§3.1).
> - [설계 #5 — Risk Capacity Ledger 계약 (v1.1, 비준)](2026-07-21-tos-risk-capacity-ledger-design.md)
>   + 코드 `tos/src/tos/rcl/`. **본 문서의 최대 소유권 인접 지대다.** rcl은 ADR-002-001 §12(Reserved
>   Capacity Commitment/Consumption)·§14(Risk-Capacity Accounting)·§15(Trapped Exposure)·§9의
>   capacity 소비 mechanics를 **이미 소유·구현**한다: `CapacityState` 9종(`vocabulary.py:23–31`,
>   `TRAPPED_CONSUMED`·`QUARANTINED_UNKNOWN`·`RELEASE_PENDING_PROOF`·`RELEASED` 포함)·`ProtectivePool`
>   (`records.py:315`, `removed_from_normal_headroom`·`borrowable_by_normal_strategy=False`)·
>   `ProtectiveLease`(`records.py:348`)·`transition_allowed(from_state,to_state,cause)`
>   (`predicates.py:438`; `RELEASED` ← `TransitionCause.FINAL_QUANTITY_PROOF` only, `predicates.py:468`)·
>   `partition_verdict(quorum_available: bool|None)`(`predicates.py:711`, `PartitionVerdict` `state.py:109`
>   의 `*_preserved`/`*_denied` 필드)·ADR-002-002 **INV-009 Protective Reserve Non-Borrowable**·
>   **INV-011 Trapped Non-Reducible**·INV-005/006/007/012 + ADR-002-012 RCLP-INV-006/008/009/011.
>   **protective는 이 capacity 산술을 재저작하지 않고 rcl 판정을 주입으로 소비한다**(§3.5). **`tos.rcl`
>   은 import하지 않는다**(형제; produced-bool/주입 좌표로만 — §3.4).
> - [설계 #6 — Safety Authority 계약 (v1.2, 비준·구현됨)](2026-07-23-tos-safety-authority-design.md)
>   + 코드 `tos/src/tos/authority/`. **본 문서의 두 번째 소유권 인접 지대다.** authority는 ADR-002-001
>   §8 degraded-mode의 **mode enum과 precedence를 이미 소유**한다: `AuthorityState`
>   = {`HALTED`,`CONTAINED`,`DEGRADED_PROTECTIVE`,`LIVE_RESTRICTED`,`LIVE_NORMAL`}(`vocabulary.py:47`
>   등)·`PRECEDENCE_RANK`(`vocabulary.py:54`: HALTED=4…LIVE_NORMAL=0)·`CapabilityType` 10종
>   (`DEGRADED_PROTECTIVE`·`PROTECTIVE_CANCEL_OR_REPLACE`·`CONTAIN`·`RECONCILIATION_ONLY` 포함,
>   `vocabulary.py:24–33`)·`RESTRICTIVE_DOMINATING_TYPES`(`vocabulary.py:64`)·`restrictive_dominates`·
>   `safer_transition_allowed`·`permissive_transition_allowed`·`lease_scope_exclusive`. **protective는
>   이 mode enum·precedence·exclusivity를 재저작하지 않는다**(권위 중복 배제). **중심 seam(§3.4)**:
>   authority의 `degraded_lease_valid`(`predicates.py:509`)는 이미 **`protective_classification_present:
>   bool|None`**(`predicates.py:513`)를 주입 소비하고, `degraded_lease_invalidated`(`predicates.py:626`)는
>   **`protective_capacity_exhausted: bool|None`**(`predicates.py:639`)를, `authority/state.py:129`는
>   **`protective_leases_reconciled: bool|None`**를 주입 소비한다 — protective가 이 셋의 **상류
>   producer**다. **`tos.authority`는 import하지 않는다**(형제; produced-bool/주입 좌표로만).
> - [설계 #7 — Live Authorization 계약 (비준·구현됨)](2026-07-25-tos-live-authorization-design.md)
>   + 코드 `tos/src/tos/liveauth/`. **중심 seam(§3.4)**: liveauth `continuous_validity`
>   (`predicates.py:193`)의 10조건 중 **`protective_coverage_valid: bool|None`**(`ContinuousValidityInputs`,
>   `state.py:138`)·§14.1 expansion의 **`protective_coverage_added: bool|None`**(`InPlaceExpansionInputs`,
>   `state.py:204`)·re-arm variant 전제 **`protective_leases_reconciled`**(`predicates.py:135`)를 이미
>   주입 소비한다 — protective가 상류 producer. **liveauth에 `degraded` 토큰 부재**(실측: 0건) — degraded
>   개념은 liveauth 소관이 아니다. **`tos.liveauth`는 import하지 않는다**(형제).
> - [설계 #8 — Orthogonal Trading State 계약 (비준·구현됨)](2026-07-25-tos-orthogonal-state-design.md)
>   + 코드 `tos/src/tos/orthostate/`. §11 protective ownership/cancellation의 order-state 축은
>   orthostate `BrokerOrderState`(`vocabulary.py:110–118`)·`KnowledgeState`(`RECONCILED` `vocabulary.py:153`)
>   소관이다. orthostate는 rcl `CapacityState`를 **import REUSE**한다(`vocabulary.py:6–8` 실측 — import-and-
>   compose 선례). protective는 cancellation-arbiter 술어에서 order-state를 **주입 좌표**로 소비한다.
>   **`tos.orthostate`는 import하지 않는다**(형제).
> - [설계 #10 — Broker Capability 계약 (v1.1, 비준)](2026-07-25-tos-broker-capability-design.md)
>   + 코드(예정) `tos/src/tos/brokercap/`. §6.2 Credible State Space·§4.2 broker capacity·§11.4 replacement
>   semantics는 Broker Capability Profile(#10) 소관이다. protective는 broker-semantics를 **주입 flag/좌표**
>   로만 소비한다(broker-agnostic). produced-bool seam·sibling edge 0·PROMOTE 0의 **직전 동형 선례**다.
>
> **규범 원천**: `ADR-002-001` — Degraded-Mode Protective Capacity (Status: **Proposed**, **Version 0.7
> Draft** [CORPUS-REVIEW-0001 Wave 8], **1132 line**, Decision Type: Safety-Critical Architecture Decision).
> Parent RFC-002; Governed-By RFC-000/001. Decision Drivers(§2): **SAFE-001/002/003/004/011/013/014/015/
> 021/024/025/035/040/041/043/044/048/050/051**(§22 Traceability). Depends-On(§23.3): RFC-000/001/002,
> ADR-002-002/003/004/005/008/011/019, VER-002-001. 매핑 대상 EV: `verification/EVIDENCE-REGISTER-002.md`의
> **`PRD-EV-001`(Protective-Resource-Domain Enumeration Completeness, `EV-L1/3+Broker`, line 396)·
> `PRD-EV-002`(Per-Resource Guarantee-Level Assignment Completeness, `EV-L1/3`, line 397)** — **2행뿐,
> 둘 다 `NOT_IMPLEMENTED`, 둘 다 최소 레벨에 EV-L1 슬라이스 보유**. §21 acceptance-criteria의 나머지
> 항목은 **타 ADR의 EV family**(RC-EV·SA-EV·PR-EV·ARE-EV·FD-EV·IOC-EV·RCLP-EV·AFG-EV·SPG-EV·BC-EV·
> VTG-EV·X-EV)에 바인딩된다(§1 실측).
>
> **앵커 — 자체 INV 시리즈 부재(실측 검증)**: ADR-002-001은 **자체 `PRD-INV`/`PRD-AC` 번호 시리즈를
> 정의하지 않는다.** §21 Acceptance Criteria는 **번호 없는 불릿**이며(review history의 "criterion #1/#11"은
> 비공식 서수), 잔존 토큰 "INV-015"·"INV-008"은 **타 ADR 교차참조**다(§8.5 line 393 "ADR-002-027
> SIR-INV-015"; VERIFICATION-PROFILE `B_stale_epoch_reject` "ADR-002-002 INV-008"). ⇒ **본 계약은
> `PRD-EV-001/002` · §21 acceptance-criteria(불릿, evidence-family 바인딩) · §-clause · `SAFE-###`
> (§22)에 앵커하고 새 INV 시리즈를 창작하지 않는다**(§0.4f). #9(ADR-002-006 자체 INV 부재로 AC/EV
> 앵커)와 동형이며, #6(자체 `SA-INV`)·#10(자체 `BC-INV`)이 자체 INV에 앵커한 것과는 상황이 다르다.
>
> **비준 기록**: **2026-07-25 운영자 비준(v1.1) — §10.2 판단 지점 승인(seam plain-bool decoupled).**
> *(v1.2 = 구현 커밋 `02de5c54`의 독립 적대적 코드 리뷰가 **"코드 결함 아님·설계-트랙 판단 지점"**으로
> 회부한 2건의 **처분 부기**만 — [D1] `mode_permits_protective` per-mode 표현력 ⇒ **현행 비준 signature
> 유지·의도적 이연**(§6.1), [D2] `retry_admissible`의 `unknown_outcome=None` 미차단 ⇒ **현행 유지**
> (duplicate-effect 게이트 선행 방어) + 회귀 보호 유지 의무(§6.4). **코드 무변경·의미 변경 아님**,
> 비준 효력 유지; §10.1 v1.2.)*
> (독립 비평 리뷰 **REVISE**[CRITICAL 0·MAJOR 1·MINOR 1·
> NIT 1] 반영: **MAJOR-1** `protective_leases_reconciled` 정의 술어 추가[§6.7, 선택지 (a); ADR §5/§16 근거]·
> **MINOR-1** §21 불릿 수 정정[10+9=19]; 60여 인용 전수·§8 키 15종·4개 실측-정정·seam 5슬롯·TRAPPED 좌표 분리·
> de-restriction 4조건·umbrella §21 19불릿 전수 매핑은 리뷰에서 정확 확인, 아키텍처 핵심 불변. 상세 §10.1 v1.1.)
> 효력:
> `tos/src/tos/protective/` Phase 1(EV-L1) 순수·비전송 모델 + property test 착수를 승인하며,
> `tos.canonical`·`tos.ordering` REUSE·**sibling edge 0건·PROMOTE 0건**·produced-bool seam(caller/런타임
> 이연)으로 진행한다. **PRD-EV 0건 완결** — acceptance·비준·restricted-live·production 어느 것도 선언·주장하지
> 않는다. ADR acceptance는 오직 *실행된* evidence로만 온다(project memory `tos-spec-rfc-authoring-track`;
> ADR §20 "written scenarios are verification requirements, not completed evidence"·§21 "Until those
> conditions are supported by completed evidence, this ADR remains `Proposed`"; VER-002-001 §5 "Registration
> is not execution. A written test is not evidence"). 수용 서명 게이트는 IMPLEMENTATION-PLAN-002 §3 하드
> 배제(Independent-Safety-Reviewer는 본 문서의 저자/통합자여서는 안 됨)를 따른다.
>
> **리뷰 이력(선제 봉합 defect class)**: 직전 시리즈 REJECT/REVISE — #6 v1.0 **REJECTED**(fail-open
> seam: §6.1/§6.3 exclusivity `≤1⇒True` vacuous-True, §5.2 조건 4), #7 v1.0 **REVISE**(SAFE
> under-realization), #8 v1.0 **REJECT**(cross-section 모순: representability를 coupling-cleanliness와
> 혼동 — C1), #10 v1.0 **REVISE**(MAJOR-1 orthostate seam 실측 오명명 — `conservative_direction_allowed`가
> 코드에 부재·실제 `conservative_direction_ok`; MAJOR-2 §8 bounds 불완전 열거). #6/#7/#9 세 건은 비준 후
> transcription 에라타(부등호 방향·필드명·class gloss)를 요했다. 본 문서가 **선제 봉합**한 defect class:
> (a) **§1 core-tier 판정** — PRD-EV 2행은 최소 레벨에 EV-L1 슬라이스 **보유**(#8/RCL형 core tier 존재)
> 이나 **닫는 PRD-EV = 0건**("/3"·"+Broker" 잔여; §1 결정적 사실 2). (b) **소유권 중복·권위 중복
> 구조적 배제(#8 C1·#10 OQ2 교훈)** — rcl capacity 산술·authority mode/precedence/exclusivity를 **코드로
> 실측**해 protective가 무엇을 소유/소비/생산하는지 §3.5 소유권 분할표로 고정(sibling 설계 서사가 아니라
> 실제 함수명·signature·라인 인용). (c) **fail-open seam 방지(#6 REJECT 교훈)** — 중앙 술어가 *본질적으로*
> fail-closed(미열거 domain⇒UNAVAILABLE·미할당 guarantee⇒최저·None⇒restrictive), permissive 기본 생성
> 경로 구조적 부재, 각 가드 both-ways canary(§4·§5·§6). (d) **fixture clean-vs-illegal 정합(#8 REJECT
> 교훈)**(§7). (e) **cross-section self-consistency pass**(§1↔§5/§6↔§7 대조). (f) **verbatim 전사 +
> ADR line 병기**(에라타 defect class 방지 — §2.2). (g) **실측-원천 결함 방지(#8 line 791→#10 상속 사건
> 교훈)** — 모든 seam을 **코드 실측 signature+라인**으로 인용하고, sibling 설계 서사가 코드와 어긋난
> 지점을 명시(§3.4 rcl `TransitionCause` [not `CapacityTransitionCause`]·rcl INV 귀속 정정·rcl
> `exclusiv*` 부재→authority 소재). (h) **에라타 관찰**(수정 아님) — VERIFICATION-PROFILE
> `B_rate_limit_recovery` rationale의 "ADR-002-001 §7.5"는 실존하지 않는 조항(§7은 무-하위절 —
> §8 에라타 관찰).

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. ADR-002-001 조항별 **Phase 1(EV-L1) 도달성 경계**(§1). **core(L1 슬라이스) / predicate-only /
   not-Phase-1(형제 소유·이연) 3분류.** **결정적 사실**: `PRD-EV-001`(`EV-L1/3+Broker`, line 396)·
   `PRD-EV-002`(`EV-L1/3`, line 397) **2행 모두 최소 레벨에 EV-L1 슬라이스 보유**(→ #8/RCL형 **core
   tier 존재**, #10/Time/#6/#7/#9의 "0건 완결" shape가 **아님**) — 그러나 **닫는 PRD-EV = 0건**(L1
   슬라이스 저작 ≠ EV closure: `/3`·`+Broker` 잔여가 남음; #8이 core tier를 가지면서도 0건 완결이었던
   것과 동형). "**EV-L1-complete 주장 금지**".
2. **protective resource domain enumeration + guarantee-level assignment 데이터 모델**(§2, **core**):
   버전 있는 digest-bound `ProtectiveCapacityProfile`(IndependentIdArtifact) — `tuple[ProtectiveResourceDomain
   Declaration]`(§4.6 7군 domain) + 각 declaration의 `GuaranteeLevel`(§3.1.4 5종 verbatim) 할당 +
   evidence 참조 scalar. 어휘: `ProtectiveResourceDomain`(§4.6 verbatim)·`GuaranteeLevel`(§3.1.4:
   `PHYSICALLY_RESERVED`/`LOGICALLY_RESERVED`/`PRIORITIZED_ONLY`/`BEST_EFFORT`/`UNAVAILABLE`)·
   `ProtectiveOwnership`(§3.1.6: `STRATEGY_OWNED`/`EXECUTION_OWNED`/`SAFETY_OWNED`/`OPERATOR_OWNED`)·
   `ProtectiveActionOutcome`(로컬 classification 결과)·`Admissibility`(로컬 3종).
3. **domain enumeration completeness 중앙 불변식**(§4.1, PRD-EV-001 substrate — ADR §4 line 158·§4.6
   line 205·line 217): `domain_enumeration_complete(declared, required) -> bool`. **required domain 미열거
   ⇒ 그 domain은 `UNAVAILABLE`로 취급(most-restrictive) ⇒ 불완전**(ADR line 158 "Protective capacity
   SHALL be defined across all resources whose exhaustion could prevent containment"). "assume-present"
   경로 **구조적 부재**.
4. **guarantee-level assignment completeness 중앙 불변식**(§4.2, PRD-EV-002 substrate — ADR §4.6 line
   215·217·§12.4): `guarantee_level_resolved(domain, assignment) -> GuaranteeLevel`. **미할당 ⇒ 최저
   보장(`UNAVAILABLE`)로 취급**; **`PRIORITIZED_ONLY`는 reserved로 취급 금지**(§3.1.4 line 144 "A
   prioritized resource is not a reserved resource"; §12.4 line 543 "Priority is not reservation");
   **reservation mechanism·failure independence가 실증되지 않으면 `guaranteed`로 기술 금지**(line 217).
5. **protective action classification 술어**(§5, predicate-only, §6 substrate, **produces
   `protective_classification_present`**): `protective_classification(...)` — §6.1 final-state test
   (final < current) ∧ §6.2 intermediate-state test(worst intermediate ≤ no-action ∧ no credible
   intermediate가 hard-limit exceedance 증가) ∧ credible-state-space bounded(else UNKNOWN). **strategy
   flag·sell direction·exit/hedge name·reduce-position intent는 비권위**(§6 line 249); **증명 불가 ⇒
   risk-increasing으로 분류·거부**(§6.2 line 279). 실제 aggregate-risk 수치는 **주입**(ARE/ADR-002-021 —
   protective는 비교 술어만).
6. **degraded-mode §8.5 de-restriction 술어**(§6.1, predicate-only, v0.7 U1 신규 normative decision):
   `derestriction_admissible(...)` — `CONTAINED`→`DEGRADED_PROTECTIVE`는 **not-automatic ∧ affirmative
   re-establishment ∧ explicit governed decision ∧ no dominating stronger restriction** 전부 성립할 때만.
   **elapsed time·reconnection·quiet time·cache agreement·absence of adverse signal ⇒ 유발 금지**(§8.5
   line 391); **임의 미성립/None ⇒ `CONTAINED` 유지(fail-closed)**. mode enum·precedence·거버넌스 결정은
   authority 소비(주입).
7. **partition-time lease-admissibility 술어**(§6.2, predicate-only, ADR line 448 "**ADR-002-001 owns
   this partition-time lease-admissibility rule**"): `partition_lease_admissible(...)` — pre-proven
   admissibility scope + staleness tolerance 내 **overlap-first/add-only는 허용**; **cancel-first(또는
   기존 protection 제거·약화)가 scope 밖·staleness 초과 ⇒ 금지 → trapped**(§9 line 448·§15). rcl
   `partition_verdict`·lease-validity는 주입 소비.
8. **protective ownership + cancellation-arbiter 술어**(§6.3, predicate-only, §11): `ProtectiveOwnership`
   enum(§3.1.6) + `cancellation_admissible(...)` — `SAFETY_OWNED` order는 (protection 불요 ∧ within
   envelope) ∨ (equivalent/stronger 확립) ∨ (계속 존재가 더 큰 aggregate risk ∧ controller authorize)
   에서만 취소(§11.1); **protective 평가가 ordinary cancellation에 선행**(§11.2); **cancel-ack ≠ FQP·
   제출/ack된 replacement에 optimistic credit 금지**(§11.4 line 506). order-state는 orthostate 주입 소비.
9. **bounded-retry 술어 + exhaustion**(§6.4, predicate-only, §13, **produces
   `protective_capacity_exhausted`**): `retry_admissible(...)` — bounded·policy-approved retry는 **중복
   경제효과 불가**일 때만(§13); **retry-budget exhaustion ⇒ containment trigger(Critical)**(§13 line 594);
   **UNKNOWN outcome + dedup 미증명 ⇒ no retry**(§14.4 line 639). preserve/potentially-live 산술은 rcl 소비.
10. **time-untrusted protective behavior 술어**(§6.5, predicate-only, §10) + **protective action envelope
    subordination 술어**(§6.6, predicate-only, §7) + **dynamic reserve sufficiency 술어**(§6.7, **produces
    `protective_coverage_valid`/`protective_leases_reconciled`**) + **multi-account minimum allocation
    술어**(§6.8, §12.6).
11. **protective ↔ rcl/authority/liveauth/orthostate 경계(중심 아키텍처)**: protective는 **sibling edge
    0건**을 유지한다(§0.4b/§3.4). protective는 classification·exhaustion·coverage·lease-reconciled
    **bool을 생산**하고 authority/liveauth가 **이미 선언한 주입 `bool|None` 슬롯**으로 소비한다(코드 실측:
    authority `predicates.py:513/639`·`state.py:129`, liveauth `state.py:138/204`·`predicates.py:135`).
    protective는 rcl `partition_verdict`·`CapacityState`(trapped) 및 authority `AuthorityState`/precedence를
    **주입 좌표**로 소비한다. `tos.rcl`·`tos.authority`·`tos.orthostate`·`tos.liveauth`·`tos.recon`·
    `tos.evidence`·`tos.capsule`·`tos.time`·`tos.dsl`·`tos.brokercap` **미import** — `tos.canonical`·
    `tos.ordering`(둘 다 core)만 import한다(§0.3). **PROMOTE 0건.**
12. **fail-closed 규율 + named canary**(§4·§5·§6): 미열거 domain⇒UNAVAILABLE; 미할당 guarantee⇒최저;
    PRIORITIZED_ONLY≠reserved; classification 증명 불가⇒risk-increasing; de-restriction 미성립⇒CONTAINED
    유지; cancel-first-outside-scope⇒trapped; cancel-ack≠FQP; time-untrusted⇒time-dependent authority
    무효; retry-budget 소진⇒containment; None⇒restrictive. 각 가드에 **both-ways canary**.
13. **property-test 하네스 타깃**(§7, §1 분류 정렬) + import-closure 검증(§7.1) + run manifest 7항목(§7.2)
    + fixture clean-vs-illegal 정합 규율(#8 교훈).
14. **bounds 주입 계약 + Phase-0 이관**(§8): protective decision 구조에는 numeric bound 부재(전부 enum·
    boolean·집합 논리·주입 Decimal); ADR-002-001이 도입하는 수치(reserved-protective minimum·dynamic
    reserve sufficiency threshold·retry budget·holdover·protection-gap/overlap window)는 **Safety Profile
    /Broker Capability Profile INSTANCE 측정값**이며 주입 opaque param으로만 담는다. **MAJOR-2 규율**:
    `measurement_source` 전수 확인 후 완전 열거(§8).

### 0.2 하지 않는 것 (경계·NO 목록)

- **ADR/스펙 비준·acceptance·restricted-live·production 어느 것도 승인하지 않는다.** ADR §20 line 973
  "These written scenarios are verification requirements, not completed evidence. ADR acceptance requires
  actual execution, retained raw artifacts, invariant evaluation, measured bounds, hashes, and independent
  review under VER-002-001"; §21 line 1006 "Until those conditions are supported by completed evidence,
  this ADR remains `Proposed`." **닫는 PRD-EV = 0건.**
- **capacity 산술(commit/consume/release·exclusive headroom·aggregate envelope·partition consumption)을
  저작하지 않는다.** 그것은 **rcl(#5, ADR-002-002/012)이 이미 소유·구현**했다 — `CapacityState`·
  `ProtectivePool`/`ProtectiveLease`·`transition_allowed`·`partition_verdict`·INV-009/011/005/006/007/012·
  sub-ledger no-enlarge/recycle/overlap. §12(Reserved Capacity Commitment/Consumption)·§14(Risk-Capacity
  Accounting)·§15(Trapped Exposure)의 **capacity 부분은 전부 rcl 소관**이다(§3.5). protective는 rcl 판정을
  **주입으로 소비**하고 재저작·중복 저작하지 않는다(CLAUDE.md DRY 비협상).
- **degraded-mode enum·precedence·restrictive dominance·lease exclusivity를 재저작하지 않는다.** 그것은
  **authority(#6, ADR-002-003)가 이미 소유·구현**했다 — `AuthorityState`·`PRECEDENCE_RANK`
  (`vocabulary.py:54`)·`restrictive_dominates`·`safer_transition_allowed`·`permissive_transition_allowed`·
  `lease_scope_exclusive`·`CapabilityType`. protective는 **권위 중복을 구조적으로 배제**하고 mode/precedence
  verdict를 주입 소비한다(§3.5). §5 Protective Action Controller의 **authorize·transmit·release는
  authority/egress 런타임**이며 protective는 classification **bool만 반환**한다(§4.5).
- **Protective Action Controller 런타임(transmit·retry·egress reject·evidence capture·capacity mutate)을
  구현하지 않는다.** ADR §5·§11·§13은 런타임 controller를 규정한다. Phase 1 protective는 결정 술어만
  저작하며 **전송·재시도·egress 강제·capacity mutate·evidence emit을 수행하지 않는다**(§4.5; #9 recon·#10
  brokercap이 bool만 생산·미enforce한 것과 동형).
- **aggregate risk 수치를 산출하지 않는다.** §6.3 risk dimensions의 실제 conservative aggregate-risk 값은
  **ARE(ADR-002-021, 미구현 tos 패키지)** 소관이며 protective는 그 값을 **주입**받아 §6.1/§6.2 비교 술어만
  적용한다. §6.2 Credible State Space(RFC-002 §3.1.17, ADR-002-004 Broker Capability Profile + ADR-002-021
  Adverse Scenario Set 경계)는 주입 flag(미경계 조합 ⇒ UNKNOWN).
- **replacement-gap·protection-gap 메커니즘을 결정하지 않는다.** §11.4 non-atomic replacement·Protection
  Gap은 **ADR-002-011(PR-EV)** 소관(§9 line 448 "ADR-002-011 §5 and ADR-002-019 §19 cross-reference it").
  protective는 partition-time lease-admissibility(overlap-first/cancel-first 판정)만 소유하고 gap 지속시간·
  atomic-replace semantics는 브로커/PR 이연.
- **Safety Profile envelope 값·guarantee-level 최소 예약치·재검증 정책을 승인하지 않는다.** protective
  action envelope 값(§7)·reserved protective minimum(§4.4/§12.1)·dynamic reserve threshold(§12.5)는
  **ADR-002-014 Safety Profile Governance + Verification Profile** 소관이며 protective는 **주입
  opaque param**으로만 담고 어떤 숫자도 하드코딩하지 않는다(§8·CLAUDE.md). 값 부재 ⇒ fail-closed.
- **evidence persistence·replay engine·+Security enforcement를 구현하지 않는다.** protective 결정의
  재구성 가능성(digest-bound frozen 레코드)만 담고 replay ENGINE은 ADR-002-016, egress bypass·물리 격리는
  ADR-002-013(+Security)이다(§9.2 Phase-0).

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

protective 모델은 다음만 import한다:

- 서드파티: `pydantic`(frozen 모델), `pytest`·`hypothesis`(테스트만). **`numpy`/`pandas`/`pyyaml`도
  import하지 않는다** — protective는 StrEnum·boolean·집합 논리이고, 수치는 `CanonicalDecimal` 산술뿐이라
  수치 백엔드 불필요하며, 모든 bound·threshold·window는 주입 파라미터이고 YAML 파싱은 하네스(설계 #3)
  소관이다(closure 최소화 — #5/#6/#7/#8/#9/#10 §0.3 동형).
- tos 자기 자신: `tos.canonical`(`FrozenModel`·`DigestBoundArtifact`·**이미 core인 `IndependentIdArtifact`**·
  **이미 core인 `classify_record_pair`**·`RecordPairKind`·`ArtifactStatus`·**이미 core인 `CanonicalDecimal`**
  — `__init__.py:45–64` 실측 §3.1), `tos.ordering`(profile-version append-only 순서 — §3.2), `tos.protective.*`.
  **`tos.rcl`·`tos.authority`·`tos.orthostate`·`tos.liveauth`·`tos.recon`·`tos.evidence`·`tos.capsule`·
  `tos.time`·`tos.dsl`·`tos.brokercap`을 import하지 않는다**(형제/상하류; produced-bool·scalar·주입 좌표로만
  참조 — §3.4/§3.5).
- **`shared.config` 절대 금지**(설계 #1 §6.1, `.importlinter`): `shared.config.__init__`이
  `shared.config.secrets`(→ `os.environ`)를 무조건 전이 import한다. protective는 어떤 `shared.*`도 필요로
  하지 않는 순수 커널이다.
- **금지(직접·전이 모두)**: `shared.execution`, `shared.kis`, `shared.streaming`, `shared.llm`,
  `shared.storage`, `shared.backtest`, `services.*`, `cli.*`(설계 #1 §2.3; `.importlinter` forbidden set).
- **firewall 구조 확인(실측·#10 §0.3 상속)**: `.importlinter`는 **`forbidden` 계약 단일**(type=forbidden,
  source=tos)이며 `layered` 계약이 아니다 — intra-tos sibling→sibling edge는 구조적으로 금지되지 않고 설계
  #1 §3.2의 "자기 자신 `tos.*`" 허용 조항이 이를 커버한다. **신규 패키지 `tos.protective`는 firewall 도구
  무수정 자동 포섭**된다(forbidden 계약이 source=tos 전체를 덮으므로 새 top-level 패키지도 즉시 강제 대상).
  본 문서는 그럼에도 **sibling edge 0건**을 **설계 규율**로 유지한다(§0.4b) — firewall 하드 규칙이 아니라
  결합-최소화 주석이다.
- 이 배제를 능동 강제하는 것이 §7.1 import-closure 검증 테스트다(`import tos.protective` closure에 금지·
  `shared.config`·`os.environ`·numpy/pandas/yaml·**`tos.rcl`·`tos.authority`·`tos.orthostate`·`tos.liveauth`·
  `tos.recon`·`tos.evidence`·`tos.capsule`·`tos.time`·`tos.dsl`·`tos.brokercap`** 부재 assert; **`tos.canonical`·
  `tos.ordering`은 존재 허용**). required check(`tos-firewall`, `tools/tos_firewall_check.py` layer-① AST +
  `.importlinter` layer-② 전이 방어)와 함께 green이어야 본 선언이 능동 성립한다.

### 0.4 REUSE / import / 경계 결정 요지 (핵심 아키텍처)

**(a) 패키지 위치·명명 = `tos/src/tos/protective/`.** ADR-002-001은 "Reserved **Protective** Capacity
Architecture"(§3)를 세우고 Protective Action Controller·Protective Lease·Protective Ownership·Protective
Resource Domain을 정의한다. 명명 대안 비교:

- **`tos.degraded`(기각)**: ADR 제목 "Degraded-Mode"를 직접 명명하나 **지나치게 좁다** — ADR은 `LIVE_NORMAL`
  상태의 reserve commitment(§12.1)도 포함하며 degraded 상태에 국한되지 않는다. 또한 degraded MODE enum은
  **이미 authority `AuthorityState`**(`DEGRADED_PROTECTIVE` 등) 소유라 명명 충돌 소지. operational 함의도 있다.
- **`tos.prd`(기각)**: register family prefix `PRD`(Protective Resource Domain) 직결이나 **cryptic**
  (`PRD`=product requirements doc 통용)하고, 패키지는 domain enumeration보다 넓다(classification·mode·
  cancellation·retry). rcl은 의미 있는 두문자(Risk Capacity Ledger)이나 `prd`는 그렇지 않다.
- **`tos.protcap`/`tos.protection`(기각)**: `protcap`은 rcl capacity와 개념 혼동, `protection`은 명사형이나
  ADR 토큰 다수가 형용사 "protective"(Protective Action/Lease/Ownership/Resource/Capacity)다.
- **선택 `tos.protective`**: **ADR §3 "Reserved Protective Capacity"·register domain "Protective Resource
  Domain"**을 직접 명명, terse, mode-국한 함의 회피. **경계 명시(중복 방지)**: rcl도 `ProtectivePool`/
  `ProtectiveLease`/`protective_ownership`(capacity 측), authority도 `DEGRADED_PROTECTIVE`/
  `PROTECTIVE_CANCEL_OR_REPLACE`(authority 측)를 갖는다 — `tos.protective`는 그 위의 **protective-DECISION
  layer**(domain enumeration·guarantee-level·classification·mode-semantics·cancellation-arbiter·
  partition-lease-admissibility)를 소유하며 capacity 산술·mode enum·authority-epoch을 **소유하지 않는다**
  (§3.5). **naming은 load-bearing이 아니다**(설계 #1 line 164) — 운영자 치환 가능; **load-bearing은
  layering**(protective → canonical·ordering 한 방향; rcl·authority·orthostate·liveauth·recon·brokercap과
  형제/상하류, **edge 0건**). 내부 module(`vocabulary.py`·`records.py`·`predicates.py`·`state.py`·`_base.py`)은
  rcl/authority/liveauth 선례 동형이며 **충돌 없음**(실측: `tos/src/tos/protective` 부재 확인).

**(b) protective = produced-bool producer, sibling edge 0건 (중심 결정).** protective는 두 소비자(authority·
liveauth)의 **상류**다 — protective 결정 bool을 생산하고 그들은 **이미 선언한 주입 `bool|None` 슬롯**으로
소비한다. **코드 실측 seam**(sibling 서사 아님):

- authority `degraded_lease_valid(..., protective_classification_present: bool|None, ...)`(`predicates.py:513`)
- authority `degraded_lease_invalidated(..., protective_capacity_exhausted: bool|None, ...)`(`predicates.py:639`)
- authority state `protective_leases_reconciled: bool|None`(`state.py:129`)
- liveauth `ContinuousValidityInputs.protective_coverage_valid: bool|None`(`state.py:138`)
- liveauth `InPlaceExpansionInputs.protective_coverage_added: bool|None`(`state.py:204`)
- liveauth re-arm variant 전제 `protective_leases_reconciled`(`predicates.py:135`)

대안 비교(#10 §0.4b 형식):

- **대안 A — protective가 소비자(authority/liveauth)를 import**: protective가 각 소비자 typed 필드를 참조.
  **기각**: (i) **backwards edge** — protective는 dataflow상 두 소비자의 **상류**(classification/coverage/
  exhaustion을 생산→소비)인데 상류가 하류를 import하면 부자연. (ii) 두 cross-sibling edge 신설. (iii)
  **cycle 위험**: 지금 authority/liveauth가 protective 미import라 acyclic이나 누군가 protective 토큰을
  참조하면 즉시 cycle. (iv) 소비자들은 **이미** protective 조건을 주입 `bool|None`으로 봉인해 두었다(실측).
- **대안 B — 소비자가 protective를 import(방향 정합이나 두 edge 신설)**: authority/liveauth가 protective
  producer를 직접 호출. **기각**: 두 소비자 전부 **이미 비준·구현**됐고 protective 조건을 주입 슬롯으로 봉인
  했다. 지금 두 곳을 protective 의존으로 바꾸면 두 ratified 패키지를 동시 접촉·두 edge 신설 — 과침습·비권장.
- **선택 — decoupled, plain-bool producer(edge 0건)**: protective는 **자신의 어휘·모델·결정 술어**를
  저작하고, 출력은 **plain `bool`/`str`**로 두 소비자가 **이미 선언한 주입 signature와 타입 일치**(전부
  `bool|None`·fail-closed). composition(protective 출력 → 소비자 주입 슬롯)은 **caller(미래 Protective
  Action Controller/Live-Authorization/Reconciliation Service 런타임) 소관**이며 Phase 1 밖이다. 근거:
  (i) #9(recon→orthostate/rcl)·#10(brokercap→liveauth/orthostate/recon)이 produced-bool로 봉인한 결정과
  **완전 동형** — 일관성. (ii) edge 0건. (iii) cycle 원천 차단. (iv) **compose seam-sealing**: 타입 일치 +
  fail-closed 정합으로 seam 조립, **test-only** 모듈이 protective·(각 소비자)를 **둘 다 import**해 polarity·
  fail-closed를 대조(테스트 import는 §7.1 package closure에 계상되지 않음). **운영자 판단 지점(§10.2)**:
  produced-bool decoupled(권장) vs 대안 B(소비자 측 edge). **consume 방향도 동일 규율**: protective 자신의
  술어(§6.1 de-restriction·§6.2 partition-lease·§6.3 cancellation·§6.7 trapped)가 필요로 하는 authority
  mode/precedence verdict·rcl partition/trapped verdict·orthostate order-state는 **주입 `bool|None`/scalar**로
  소비하고 `tos.authority`/`tos.rcl`/`tos.orthostate`를 import하지 않는다. **대안(§10.2)**: authority
  `AuthorityState`/`PRECEDENCE_RANK`/`restrictive_dominates`·rcl `CapacityState`를 **import-and-compose**
  (선례 #6 authority→time, orthostate→rcl `CapacityState` `vocabulary.py:6–8`)하면 mode/precedence 재표현
  없이 type-safe하나 두 sibling edge 신설 — **decoupled 권장**(#9/#10 정합·edge/cycle 회피).

**(c) REUSE + PROMOTE 0건.** `ProtectiveCapacityProfile`은 `tos.canonical.IndependentIdArtifact`(id⊥digest,
`_base.py:328`)·`DigestBoundArtifact`(`_base.py:98`)를 REUSE한다. `CanonicalDecimal`은 **이미 `tos.canonical`
에 존재**(`__init__.py:56`·정의 `canonicalization.py:134` 실측; #9 §0.4c가 이미 PROMOTE)하므로 envelope/
reserve magnitude bound에 **추가 PROMOTE 없이** REUSE한다. `classify_record_pair`(`record_pair.py:52`)·
`Ordering`/`OrderingEvent`/`compare_order`(`ordering/__init__.py`)도 이미 core. ⇒ **PROMOTE = 0건, sibling
edge = 0건**(#10과 동형 — 후속 문서로서 PROMOTE 부담 없음). 기대치(orchestrator brief) "sibling edge 0,
PROMOTE 0" 성립.

**(d) `id=f(digest)` 미채택 (canonical REUSE).** `ProtectiveCapacityProfile`은 **거버넌스-할당 identity**
(profile version·approver)를 가지며, same-id/diff-bytes(위조·재발행·contradictory 재발행) 탐지에
`classify_record_pair`(`record_pair.py:52`, `RecordPairKind.CRITICAL_CONFLICT` `record_pair.py:43`)를
쓰려면 id⊥digest여야 한다(설계 #4·#5·#6·#7·#8·#9·#10 §3.1과 완전 동형; capsule의 content-addressed
`id=f(digest)`와 정반대). ⇒ `IndependentIdArtifact` 채택, `IdDerivedArtifact`(`_base.py:256`) 미채택.
`tos.protective._base`는 rcl/authority/liveauth 동형의 thin re-export shim.

**(e) 형제/상하류 미import 근거(§3.5 소유권 분할 요지).**
- **`tos.rcl` 미import(capacity 하류 소비)**: rcl은 §12/§14/§15의 capacity 산술을 소유(§3.5). protective는
  reserve-sufficiency·exhaustion·trapped 판정에 필요한 rcl 값(protective_pool committed 여부·partition
  verdict·`CapacityState.TRAPPED_CONSUMED` 여부)을 **주입 bool/scalar**로만 소비. 재저작 금지(DRY).
- **`tos.authority` 미import(mode/precedence 상류 소비)**: authority는 `AuthorityState`·`PRECEDENCE_RANK`·
  restrictive dominance·lease exclusivity 소유. protective는 mode/dominating-restriction verdict를 주입
  소비하고 **mode enum을 재선언하지 않는다**(권위 중복 배제). protective는 authority가 소비할 classification/
  exhaustion/lease-reconciled **bool을 생산**(§3.4).
- **`tos.liveauth` 미import(re-arm 상류 소비)**: liveauth `continuous_validity`·re-arm 소유. protective는
  `protective_coverage_valid`/`protective_coverage_added`/`protective_leases_reconciled` **bool을 생산**;
  §16 recovery/re-arm 자체는 liveauth 소관(§3.5).
- **`tos.orthostate` 미import(order-state 축)**: §11 cancellation-arbiter의 order-state(BrokerOrderState·
  KnowledgeState)는 orthostate 축. protective는 주입 좌표로 소비(별개 타입, swap 원천 차단 — 좌표 비붕괴 §4.4).
- **`tos.evidence`·`tos.capsule`·`tos.time`·`tos.dsl`·`tos.recon`·`tos.brokercap` 미import**: evidence는
  하류 투영(layering 역전 금지)·scalar 참조만; capsule `FieldState`는 다른 축; time freshness/holdover는
  주입 opaque flag(§8; rcl/authority가 time을 주입/compose한 것과 구분 — protective는 time 산술 불요이므로
  #6식 import-and-compose조차 불요, 주입 flag로 충분); dsl 무관; recon per-field confidence는 다른 축;
  brokercap capability는 broker-agnostic 주입 flag.

**(f) 앵커 규약 — 새 INV 시리즈 창작 금지.** **실측**: ADR-002-001은 **자체 `PRD-INV`/`PRD-AC` 시리즈를
정의하지 않는다**(§21은 번호 없는 불릿; 잔존 "INV-###"은 전부 타 ADR 교차참조 — 상단 앵커 절). ⇒ 본 계약은
모델 불변식·술어를 **`PRD-EV-001/002` · §21 acceptance-criteria 불릿(evidence-family 바인딩으로 지시) ·
§-clause · `SAFE-###`(§22)**에 앵커하고 **새 INV 시리즈를 창작하지 않는다**. #9(ADR-002-006 자체 INV 부재)
동형; #6(`SA-INV`)·#10(`BC-INV`)이 자체 INV에 앵커한 것과는 상황이 다르다.

**(g) PRD-EV = core tier 존재 shape (#8/RCL형; #10/Time/#6/#7/#9의 "0건 완결"과 다름).** #10의 BC-EV는
22행 전부 최소 EV-L2+라 **EV-L1 슬라이스가 0건**("0건 완결")이었다. 본 문서의 PRD-EV는 **2행 모두 최소
레벨에 EV-L1 슬라이스 보유**(`EV-L1/3+Broker`·`EV-L1/3`, line 396–397 실측)라 **core tier가 존재**한다(#8
STATE-EV-001=`EV-L1/2`·#5 RCLP-EV-001=`EV-L1/3` 동형). ⇒ §1 분류는 **core(L1 슬라이스) / predicate-only /
not-Phase-1 3분류**다. **그러나 닫는 PRD-EV = 0건** — L1 슬라이스 저작은 EV closure가 아니다(`/3` 통합·
`+Broker` profile evidence·독립 리뷰 잔여; #8이 core tier를 가지면서도 0건 완결이었던 것과 동형). 이 판정은
§1·§4·§5·§7 전체에 **일관**해야 하며(어떤 §7 test-target도 PRD-EV closure를 주장하지 않음 — #8 C1 lesson
선제 봉합), finishing 전 self-consistency pass에서 대조한다.

---

## 1. 범위 매핑 — ADR-002-001 조항별 EV-L1 도달성 (닫는 PRD-EV 0건)

EV-level 정의(VER-002-001): **EV-L1 = Model and Property Verification**(state-machine exploration, model
checking, property-based testing, deterministic simulation). **EV-L2 = Component Fault Test**, **EV-L3 =
Integration/Adversarial**, **/5 = System/Chaos**, **+Broker = Broker Capability Profile evidence**,
**+Security = security enforcement**. Phase 1은 EV-L1만이다.

> **결정적 사실 1 — ADR-002-001은 umbrella ADR이다 (2 PRD-EV row + 흩어진 타-ADR evidence)**: ADR-002-001의
> §21 acceptance-criteria는 **10개 불릿(line 983–992) + 추가 9개 불릿(line 996–1004) = 총 19**인데, 그 중
> **genuinely-novel 두 항목만** 전용
> `PRD-EV` row를 얻는다 — `PRD-EV-001`(criterion #1, protective-resource-domain enumeration completeness,
> `EV-L1/3+Broker`)·`PRD-EV-002`(criterion #11 = 첫 그룹 10개 + 둘째 그룹 첫 불릿[line 996 "every protective
> resource assigned an evidenced guarantee level"], per-resource guarantee-level assignment completeness,
> `EV-L1/3`). **나머지 criteria는 전부 타 ADR의 EV family에 바인딩**된다(§21 verbatim 실측): normal-reserve
> non-consumption ⇒ `RC-EV-001`(rcl)·`X-EV-005`·`AFG-EV-001`·`RCLP-EV-004`; classification independence ⇒
> `FD-EV-001`·`ARE-EV-010`; partition ⇒ `SA-EV-003/004`(authority)·`RC-EV-012`·`X-EV-002/003`; exhaustion ⇒
> `PR-EV-007`·`FD-EV-010`·`AFG-EV-003`; partial-fill ⇒ `RC-EV-006`(rcl); trapped ⇒ `RC-EV-014`(rcl INV-011);
> no-label-bypass ⇒ `ARE-EV-001/010`·`IOC-EV-006`; aggregate commitment/consumption ⇒ `RCLP-EV-001/011`·
> `RC-EV-001`(rcl); duplicate-consumption/stale-owner ⇒ `RC-EV-002`·`SA-EV-006/007`(authority)·`RCLP-EV-003`;
> degraded lease validity ⇒ `SA-EV-004/005/006`(authority)·`RC-EV-013`·`X-EV-008`; intermediate-state proof ⇒
> `PR-EV-005`·`RC-EV-016`·`ARE-EV-003`; replacement-gap ⇒ `PR-EV-001/002/006/012`(ADR-002-011); cancellation
> ownership/arbitration ⇒ `PR-EV-011`·`X-EV-006`; common-mode broker ⇒ `BC-EV-016`·`FD-EV-008`·`VTG-EV-010`.
> **이 evidence-바인딩 지도가 §3.5 소유권 분할과 1:1 대응한다** — dedicated PRD row 2개 = protective가
> genuinely 소유하는 novel 부분(domain enumeration + guarantee-level); 타-ADR evidence로 바인딩된 항목 =
> 형제(rcl/authority/PR/ARE/FD/…)가 소유하거나 이연된 부분.
>
> **결정적 사실 2 — core tier 존재하나 닫는 PRD-EV = 0건**: `PRD-EV-001`(`EV-L1/3+Broker`, line 396)·
> `PRD-EV-002`(`EV-L1/3`, line 397)는 **최소 레벨에 EV-L1 슬라이스 보유** ⇒ **core tier 존재**(#8 STATE-EV-001
> `EV-L1/2`·#5 RCLP-EV-001 `EV-L1/3` 동형, #10 BC-EV "0건 완결"과는 다름 — §0.4g). 그러나 (a) `PRD-EV-001`은
> `+Broker`(broker별 protective resource domain 열거·BC-EV-013/021 지원)라 broker profile evidence 필요,
> `PRD-EV-002`는 `/3`(integration) 필요; (b) VER-002-001 §5 "Registration is not execution. A written test
> is not evidence"·ADR §20 line 973·§21 line 1006. ⇒ **어떤 PRD-EV도 닫지 않는다**("**EV-L1-complete 주장
> 금지**"; 설계 #2·#4·Time·#5·#6·#7·#8·#9·#10 §1 규율 상속). Owner/Reviewer는 register상 TBD.

**조항 → Phase-1 분류(core / predicate-only / not-Phase-1[형제 소유·이연])**:

| ADR-002-001 조항 | 요지 | Phase-1 분류 | L1 substrate / 소유 (근거) |
|---|---|---|---|
| **§4.1–4.5, §4.6** | Protective Capacity Domains + required resource dimensions 열거 | **core (L1 슬라이스)** | `ProtectiveResourceDomain` 열거 모델 + `domain_enumeration_complete` 술어(§4.1) — **PRD-EV-001 substrate**. 미열거⇒UNAVAILABLE. `+Broker`(broker별 domain)·`/3` 잔여로 **닫지 않음**. |
| **§4.6, §12.4, §3.1.4** | per-resource guarantee-level classification | **core (L1 슬라이스)** | `GuaranteeLevel` 5종 + `guarantee_level_resolved` 술어(§4.2) — **PRD-EV-002 substrate**. 미할당⇒UNAVAILABLE·PRIORITIZED≠reserved. `/3` 잔여로 **닫지 않음**. |
| **§6.1, §6.2, §6.3** | Protective action classification(final/intermediate-state test) | **predicate-only** | 비교 술어(§5; produces `protective_classification_present`). aggregate-risk 수치는 ARE(ADR-002-021) 주입. EV: `FD-EV-001`·`ARE-EV-010`·`PR-EV-005`(전부 EV-L2+, **닫지 않음**). |
| **§8.1–8.4, §8.3.1** | Degraded operation modes + CONTAINED emergency-action proof | **predicate-only** | per-mode 허용 술어·§8.3.1 reduce-only-by-construction 술어(§6.1). mode enum·precedence는 **authority 소유**(재저작 금지). EV: `SA-EV-*`(EV-L2+). |
| **§8.5** | CONTAINED→DEGRADED_PROTECTIVE de-restriction (v0.7 U1 신규) | **predicate-only** | fail-closed de-restriction 술어(§6.1). 거버넌스 결정은 authority 주입. EV: `SA-EV-*`·`FD-EV-*`(scenario-extension debt, gate-status §3.11). |
| **§9** (lease-admissibility) | partition-time overlap-first/cancel-first (ADR line 448 "ADR-002-001 owns") | **predicate-only** | `partition_lease_admissible` 술어(§6.2). rcl `partition_verdict`·lease-validity 주입. EV: `RC-EV-012`·`SA-EV-004`·`PR-EV-001/002`(EV-L2+). |
| **§10** | Behavior when time cannot be trusted | **predicate-only** | time-untrusted protective 술어(§6.5). time-trusted는 주입. EV: `SA-EV-011`·`TIME-EV-*`(EV-L2+). |
| **§11.1, §11.2, §11.3** | Protective ownership + Cancellation Arbiter | **predicate-only** | `ProtectiveOwnership` enum(§3.1.6) + `cancellation_admissible` 술어(§6.3). order-state는 orthostate 주입. EV: `PR-EV-011`·`X-EV-006`(EV-L2+). |
| **§13** | Capacity exhaustion + bounded retry | **predicate-only** | `retry_admissible` 술어(§6.4; produces `protective_capacity_exhausted`). preserve 산술은 rcl. EV: `PR-EV-007`·`FD-EV-010`·`AFG-EV-003`(EV-L2+). |
| **§7** | Protective Action Envelope subordination | **predicate-only** | `envelope_subordinate` 술어(§6.6). envelope 값은 ADR-002-014 주입. EV: `SPG-EV-001`(EV-L2+). |
| **§12.5, §12.6** | Dynamic reserve sufficiency + multi-account minimum | **predicate-only** | reserve-sufficiency 술어(§6.7; produces `protective_coverage_valid`) + minimum-allocation 술어(§6.8). threshold·arithmetic은 Safety Profile/rcl 주입. |
| **§12.1–12.3** | Reserved capacity commitment/consumption/exclusivity | **not-Phase-1 (rcl 소유)** | rcl `ProtectivePool`(`records.py:315`)·`ProtectiveLease`(`records.py:348`)·INV-009·sub-ledger(§5.5)·lease exclusivity(authority `lease_scope_exclusive`). protective 미소유. |
| **§14.1–14.5** | Risk-Capacity Accounting(persistence/FQP/partial-fill/UNKNOWN/margin) | **not-Phase-1 (rcl 소유)** | rcl INV-005/006/007·`transition_allowed(...,FINAL_QUANTITY_PROOF)`(`predicates.py:468`)·QUARANTINED_UNKNOWN. protective 미소유. |
| **§15** | Trapped exposure | **not-Phase-1 (rcl 소유)** | rcl INV-011 Trapped Non-Reducible·`CapacityState.TRAPPED_CONSUMED`(`vocabulary.py:30`)·`PartitionVerdict.trapped_preserved`(`state.py:128`). protective는 소비만(주입). |
| **§16** | Recovery/exit + re-arm | **not-Phase-1 (liveauth/rcl 소유)** | liveauth re-arm·`continuous_validity`; rcl reconciliation. protective는 `protective_coverage_valid` 등 producer(§6.7). |
| **§5** (controller authority) | Protective Action Controller authorize/transmit | **not-Phase-1 (런타임)** | authorize·transmit·release는 authority/egress 런타임(§4.5). protective는 classification bool만. |
| **§20 bounds, §11.4 gap** | timing bounds, protection-gap semantics | **not-Phase-1 (EV-L3/+Broker/ADR-002-011)** | `B_protective_request_*`·`B_protection_gap/overlap`은 broker/egress 런타임(§8). |

**Phase-1 분류 요약**: **core(L1 슬라이스)** = {**§4 domain enumeration [PRD-EV-001], §4.6/§12.4 guarantee-level
[PRD-EV-002]**} — **2개 PRD-EV의 L1 슬라이스뿐, 닫는 PRD-EV = 0건.** **predicate-only(EV 주장 금지)** =
{§6.1/6.2 classification, §8/8.3.1 modes, §8.5 de-restriction, §9 lease-admissibility, §10 time-untrusted,
§11 ownership/cancellation, §13 retry, §7 envelope, §12.5/12.6 sufficiency/allocation}. **not-Phase-1(형제
소유·이연)** = {§12/§14/§15 capacity → rcl, §16 → liveauth/rcl, §5 controller runtime, §20 bounds/§11.4 gap →
EV-L3/PR}. (self-consistency: core 2 + predicate-only 9군 + not-Phase-1 형제-이연 — §3.5 소유권 분할과 정합.)

> **규율 태그(모든 주장에 부착)**: "**core = PRD-EV-001/002의 L1 슬라이스뿐(‥`/3`·`+Broker` 잔존);
> predicate-only는 타-ADR EV family(전부 EV-L2+)의 substrate이며 어떤 EV도 닫지 않음; capacity/mode/precedence는
> rcl·authority 소유(재저작 금지). 닫는 PRD-EV = 0건. EV-L1-complete 주장 금지.**"

---

## 2. 데이터 모델 계약

**표현 원칙**: 모든 아티팩트는 **pydantic v2 frozen 모델**(`ConfigDict(frozen=True, extra="forbid")`,
`tos.canonical.FrozenModel` REUSE — `_base.py:73` 실측)로 저작한다. frozen은 append-only(ADR §18 "aggregate
commitment and partition-time consumption cannot create duplicate headroom"의 감사 정신·§21 evidence)의
레코드 수준 실현이며 **모델에는 update/delete 연산이 존재하지 않는다**(설계 #4 §2.0 규율 상속). enum 값·
필드명은 ADR §3.1·§4.6·§6·§8·§11의 용어를 **verbatim**으로 쓴다(스펙 용어 = 코드 용어, 설계 #1 §2.4;
에라타 defect class 선제 방지 — 각 블록에 ADR line 병기).

### 2.0 소유권 골격 — protective는 canonical의 하류, rcl/authority/liveauth/orthostate의 형제

protective가 **소유·저작하는 것**: protective 어휘(`ProtectiveResourceDomain`·`GuaranteeLevel`·
`ProtectiveOwnership`·`ProtectiveActionOutcome`·`Admissibility`) + `ProtectiveCapacityProfile` digest-bound
레코드(domain enumeration + guarantee-level assignment) + `ProtectiveActionEnvelope`·`ProtectiveLeaseAdmissibility
Scope` value + classification/de-restriction/lease-admissibility/cancellation/retry/time-untrusted/envelope/
sufficiency **술어**. **소유하지 않는 것**: capacity 산술(rcl — CapacityState·ProtectivePool/Lease·
transition_allowed·partition_verdict·INV-005/006/007/009/011/012·sub-ledger) · mode enum·precedence·restrictive
dominance·lease exclusivity(authority — AuthorityState·PRECEDENCE_RANK·restrictive_dominates·lease_scope_exclusive) ·
re-arm(liveauth) · order/knowledge state(orthostate) · aggregate-risk 수치(ARE/ADR-002-021) · envelope 값·
reserve 최소치(ADR-002-014 Safety Profile) · replacement-gap semantics(ADR-002-011) · broker capability
(brokercap/#10). 이 골격은 §3.5 소유권 분할표가 상술한다.

### 2.1 digest-bound / plain-frozen / value / reference 분류 (총괄)

| 아티팩트 | 종류 | id 필드(독립) | digest 필드 | covered / 내용 |
|---|---|---|---|---|
| `ProtectiveCapacityProfile` (§4.6; §12.4; §7) | **IndependentIdArtifact + 독립 id** | `profile_id`(+`profile_version`) | `canonical_digest` | `tuple[ProtectiveResourceDomainDeclaration]`(§4.6 domain별) + `ProtectiveActionEnvelope`(§7) + reserve-minimum 참조 scalar + evidence 참조 scalar |
| `ProtectiveResourceDomainDeclaration` (§4.6; §12.4) | **plain FrozenModel(value)** | — | — | `domain: ProtectiveResourceDomain`·`guarantee_level: GuaranteeLevel`·`reservation_mechanism_evidenced: bool`·`failure_independence_evidenced: bool`·`evidence_reference`(scalar)·`common_mode_note: str\|None` |
| `ProtectiveActionEnvelope` (§7 line 300–313) | **plain FrozenModel(value)** | — | — | permitted accounts/instruments/action-classes(집합) + max qty/notional/gross-increase/margin/action-rate/duration(`CanonicalDecimal\|None` 주입) + venue/order 제약 + evidence req + escalation marker |
| `ProtectiveLeaseAdmissibilityScope` (§3.1.2; §9) | **plain FrozenModel(value)** | — | — | pre-proven venue/session/account/instrument/order-shape space marker + `staleness_tolerance` 주입 scalar (ADR-002-019 Order Admissibility Decision 참조 scalar) |
| classification 입력 `AggregateRiskComparison`·`IntermediateStateWitness` | **plain FrozenModel(injected)** | — | — | `final_conservative_risk`·`current_conservative_risk`·`no_action_risk`·`worst_intermediate_risk`(주입 비교값, 부호/차원 좌표) + `credible_space_bounded: bool\|None`·hard-limit-exceedance 좌표 |
| de-restriction/lease/cancellation/retry 입력 | **plain FrozenModel(injected)** | — | — | authority mode/verdict·rcl partition/trapped verdict·orthostate order-state·time-trusted·budget scalar (전부 `bool\|None`/scalar) |
| `ProtectiveResourceDomain`·`GuaranteeLevel`·`ProtectiveOwnership`·`ProtectiveActionOutcome`·`Admissibility`·`DegradedModeTransition` | **StrEnum(로컬 값 타입)** | — | — | (profile/declaration/술어의 covered·산출 원소) |
| `CanonicalDecimal` (qty/notional/margin/reserve bound) | **REUSE core `tos.canonical`**(이미 존재) | — | — | (§0.4c — PROMOTE 불필요) |
| evidence / profile-version / rcl-capacity / authority-mode 참조 블록 | **plain FrozenModel(참조)** | id+generation+digest scalar | — | tos 미소유(rcl/authority/ADR-002-016/021) |

> **`IdDerivedArtifact` 채택 아티팩트 = 0건. PROMOTE = 0건**(records substrate·CanonicalDecimal 전부 이미
> core). `ProtectiveCapacityProfile`은 거버넌스-할당 profile identity를 가진다 — same-id/diff-bytes 위조·
> contradictory 재발행 탐지(`classify_record_pair` `record_pair.py:52`, `CRITICAL_CONFLICT` `record_pair.py:43`)에
> id⊥digest 필수 ⇒ `IndependentIdArtifact`(이미 core `_base.py:328`) 상속. `tos.protective._base`는
> rcl/authority/liveauth 동형의 thin re-export shim(신규 형제 edge 없음).

### 2.2 어휘 (verbatim 전사 — 에라타 defect class 주의)

> **전사 규율**: 아래 enum 값·순서는 ADR 원문에서 **verbatim**이며, StrEnum 값 문자열은 스펙 토큰을 그대로
> 쓴다(설계 #1 §2.4). 각 블록 옆에 ADR line 실측을 병기한다.

**(1) `GuaranteeLevel`(StrEnum) — ADR §3.1.4 (line 142), 5종 verbatim:**

```text
PHYSICALLY_RESERVED
LOGICALLY_RESERVED
PRIORITIZED_ONLY
BEST_EFFORT
UNAVAILABLE
```

§3.1.4 line 144 verbatim: "**A prioritized resource is not a reserved resource.**" §4.6 line 217 verbatim:
"A resource SHALL NOT be described as **guaranteed** unless its reservation mechanism and failure independence
have been demonstrated. **Priority is not reservation.**" §12.4(line 539–547) semantics: `PHYSICALLY_RESERVED`는
failure-independent partition(ordinary traffic 소비 불가), `LOGICALLY_RESERVED`는 lower-level dependency 공유
(common-mode 분석 필수), `PRIORITIZED_ONLY`는 "deprioritized but may already occupy or exhaust — SHALL NOT be
relied upon as guaranteed", `BEST_EFFORT`는 residual risk. ⇒ §4.2 `guarantee_level_resolved`는 **미할당 ⇒
`UNAVAILABLE`**(최저)로 취급하고 **PRIORITIZED_ONLY/BEST_EFFORT를 reserved로 승격하는 경로가 부재**.

**(2) `ProtectiveOwnership`(StrEnum) — ADR §3.1.6 (line 152), 4종 verbatim:**

```text
STRATEGY_OWNED
EXECUTION_OWNED
SAFETY_OWNED
OPERATOR_OWNED
```

§11.1 line 473–479: `SAFETY_OWNED` order는 strategy/ordinary execution cleanup으로 취소 불가; (protection 불요
∧ within Hard Safety Envelope) ∨ (equivalent/stronger 확립) ∨ (계속 존재가 더 큰 conservative aggregate risk
∧ Protective Action Controller authorize)에서만 취소. ⇒ §6.3 `cancellation_admissible` 술어의 좌표.

**(3) `ProtectiveResourceDomain`(StrEnum) — ADR §4.6 (line 205–213), 7군 verbatim:**

```text
EXECUTION_WORKERS_AND_QUEUES              (§4.6 "execution workers and request queues")
BROKER_API_RATE_SESSION_AND_ORDER_RATE    (§4.6 "broker/API request rate, broker session availability, and order-message rate")
AGGREGATE_RISK_MARGIN_COLLATERAL_RETRY    (§4.6 "aggregate risk capacity, margin, collateral, and protective retry budget")
NETWORK_AND_CONTROL_PATH                  (§4.6 "network and control path")
RECONCILIATION_AND_EVIDENCE_PERSISTENCE   (§4.6 "reconciliation and evidence-persistence capacity")
OPERATOR_EMERGENCY_PATH                   (§4.6 "operator emergency path")
TRUSTWORTHY_TIME_AND_PROTECTIVE_AUTHZ     (§4.6 "trustworthy-time and protective-authorization capability")
```

**required domain 수 = 7군.** ADR §4.6 line 205 "Reserved Protective Capacity SHALL be evaluated separately for
**at least**" — "at least"이므로 **required 집합은 주입 확장 가능**(broker/venue별 추가 domain은 Profile
INSTANCE·`+Broker`, PRD-EV-001의 `/3+Broker` 이유). protective는 이 7군을 **최소 required 집합**으로 열거하고,
**미열거 domain ⇒ UNAVAILABLE(§4.1)**. §4.1–4.5는 이 domain들의 세부(execution/broker-venue/risk/margin-
collateral/control)이며 §4.6이 통합 열거+guarantee classification을 명령한다.

**(4) `Admissibility`(StrEnum, 로컬 3종) — §9/§11/§13 술어 산출:**

```text
ADMISSIBLE     (overlap-first/add-only within pre-proven scope; 또는 cancellation 조건 충족)
TRAPPED        (cancel-first outside scope/past staleness — 전송 불가, 보수적 커버 유지 §9/§15)
PROHIBITED     (증명 불가·미열거·미할당·None — 해당 protective action 금지)
```

`Admissibility`에는 **"assume-admissible" 기본 생성 경로가 없다**(§4.1 fail-open 봉합). `TRAPPED`는 §9 line
448·§15 line 657–664의 "conservatively covered and trapped"를 표현한다(rcl `CapacityState.TRAPPED_CONSUMED`
capacity 측과 구분되는 **admissibility 판정**; protective는 rcl trapped state를 재저작하지 않고 admissibility만
산출 — §3.5).

**(5) `DegradedModeTransition`(StrEnum, 로컬) — §8.5 de-restriction 표현:**

```text
CONTAINED_TO_DEGRADED_PROTECTIVE   (§8.5 유일 governed de-restriction)
```

§8.5 line 381 verbatim: "The only de-restriction this ADR governs is `CONTAINED` → `DEGRADED_PROTECTIVE`". mode
값 자체(`CONTAINED`·`DEGRADED_PROTECTIVE`)는 **authority `AuthorityState` 소유**(§3.5); protective는 이 전이
**방향 marker + fail-closed 가드 술어**만 저작하고 mode enum을 재선언하지 않는다(권위 중복 배제 §0.4e).

**(6) `ProtectiveActionOutcome`(StrEnum, 로컬) — §6.1/§6.2 classification 산출:**

```text
PROTECTIVE_PROVEN          (final < current ∧ worst-intermediate ≤ no-action ∧ no exceedance 증가)
RISK_INCREASING_DENIED     (§6.2 line 279 "classified as risk increasing and denied in degraded mode")
UNKNOWN_CONSERVATIVE       (credible-state-space 미경계 ⇒ conservatively UNKNOWN, §6.2 line 277)
```

§6 line 247–249 verbatim: "Only the Protective Action Controller may classify an action as protective using
conservative aggregate-risk analysis. A strategy flag, sell direction, exit or hedge name, reduce-position
intent, operator description, or correlation with an existing position is **non-authoritative**." ⇒ §5
classification 술어는 strategy label을 입력으로 읽지 않는다(§4.5 representation≠authority 정신).

### 2.3 `ProtectiveCapacityProfile` covered + self-exclusion (설계 #4 §3.3 상속)

covered(Layer-1) = `tuple[ProtectiveResourceDomainDeclaration]`(domain별, 정렬) + `ProtectiveActionEnvelope` +
`ProtectiveLeaseAdmissibilityScope` marker + reserve-minimum 참조 scalar + evidence-package 참조 scalar.
preimage 제외: `profile_id`·`canonical_digest`·`canonicalization_version`·`status`(ArtifactStatus lifecycle
마커)·파생 역참조. **TBD/null이 covered에 하나라도 있으면 pre-issuance(status=DRAFT), digest 불가**
(`IndependentIdArtifact` issued-시 concrete-id 검증 `_base.py:328` 부근). `profile_id` ⊥ `canonical_digest`(§3.1).

> **핵심 설계 결정 — profile은 immutable version별 append-only(#7/#8/#10 lifecycle-out-of-collision 상속)**:
> profile은 재검증(evidence 만료→revalidate·guarantee-level 상향/하향)에 따라 **재발행**된다. 하나의 stable
> id에 mutable 선언을 담으면 정당한 revalidation이 same-id/diff-bytes `CRITICAL_CONFLICT`로 **오탐**된다. ⇒
> **각 profile version은 fresh `profile_id`(또는 (profile_id, profile_version) 복합 독립 identity)를 가진
> immutable 레코드**다. same identity + diff bytes ⇒ `CRITICAL_CONFLICT`(위조·재발행 위조만); 정당한 개정 ⇒
> **새 version**. version 순서는 `tos.ordering`(§3.2)로 담는다.

---

## 3. canonical / ordering REUSE + rcl/authority/liveauth/orthostate 경계 (produced-bool seam·소유권 분할)

### 3.1 canonical REUSE + `id=f(digest)` 미채택 (설계 #4·#5·#6·#7·#8·#9·#10 §3.1 상속)

`ProtectiveCapacityProfile`은 `tos.canonical.IndependentIdArtifact`(`_base.py:328`)·`DigestBoundArtifact`
(digest 검증 `canonical_digest == H_ver(canonicalize(covered))`, `_base.py:98`)를 REUSE한다. canonicalizer는
`tos.canonical` registry + `EVL1ProvisionalCanonicalizer`(`ev-l1-provisional-0`) REUSE, **신규 canonicalizer
없음**(프로덕션 canonical form은 Phase-0, §9.2). qty/notional/margin/reserve bound는 **이미 core인
`CanonicalDecimal`**(`canonicalization.py:134`, export `__init__.py:56` 실측) REUSE — `1.0` vs `1.00`의 digest
drift 차단(bare `Decimal` 금지). **`id=f(digest)`(`IdDerivedArtifact` `_base.py:256`) 미채택**: §2.1 근거(거버넌스-
할당 profile identity + same-id/diff-bytes 위조·재발행 탐지 — `classify_record_pair` `record_pair.py:52`,
`RecordPairKind.CRITICAL_CONFLICT` `record_pair.py:43`). **PROMOTE = 0건**(IndependentIdArtifact·
classify_record_pair·CanonicalDecimal 전부 이미 core — #9가 CanonicalDecimal, #6이 IndependentIdArtifact를
PROMOTE 완료했기에 본 문서는 후속으로서 PROMOTE 부담 없음).

### 3.2 ordering REUSE (profile version append-only 순서)

profile version의 append-only 순서(재발행·supersession)는 신규 저작하지 않고 `tos.ordering`(`Ordering`
`_ordering.py:41`·`OrderingEvent` `_ordering.py:49`·`compare_order` `_ordering.py:86`, `tos.canonical`만 의존)를
REUSE한다. **wall clock은 순서를 만들지 않는다**(`tos.ordering` 규율 `_ordering.py:22–24`) — protective는 clock을
읽지 않는다(§0.3; time freshness/holdover는 주입 opaque flag). light REUSE(core 의존, 신규 edge 아님).

### 3.3 REUSE 요약 표

| substrate | 결정 | 근거 |
|---|---|---|
| `FrozenModel`(`_base.py:73`)·`DigestBoundArtifact`(`_base.py:98`)·`IndependentIdArtifact`(`_base.py:328`)·`ArtifactStatus`(`_base.py:58`) | **REUSE(core `tos.canonical`)** | §3.1; 신규 없음 |
| `classify_record_pair`(`record_pair.py:52`)·`RecordPairKind`(`record_pair.py:31`) | **REUSE(core, 이미 PROMOTE됨)** | §3.1; same-id/diff-bytes·재발행 위조 |
| `CanonicalDecimal`(`canonicalization.py:134`) | **REUSE(core, #9가 이미 PROMOTE)** | §3.1; qty/notional/margin/reserve bound·PROMOTE 불필요 |
| `Ordering`/`OrderingEvent`/`compare_order`(`_ordering.py`) | **REUSE(core `tos.ordering`)** | §3.2; profile version 순서 |
| protective 어휘·Profile·envelope·classification/de-restriction/lease/cancellation/retry 술어 | **로컬 저작** | §0.4a/§2.2; ADR §3.1·§4.6·§6·§8·§9·§11·§13 verbatim·decision-side |
| authority `protective_classification_present`/`protective_capacity_exhausted`/`protective_leases_reconciled` · liveauth `protective_coverage_valid`/`protective_coverage_added` | **미소유 — produced-bool로만 공급** | §3.4; 2-소비자 seam |
| rcl `CapacityState`/`ProtectivePool`/`ProtectiveLease`/`partition_verdict`/INV-005..012 · authority `AuthorityState`/`PRECEDENCE_RANK`/`lease_scope_exclusive` · orthostate order-state | **미소유 — 주입 좌표로만 소비** | §3.5; capacity/mode/order-state 산술 재저작 금지 |
| PROMOTE | **0건** | §3.1 |
| sibling edge | **0건** | §3.4 |

### 3.4 authority / liveauth 경계 — produced-bool seam, sibling edge 0건 (중심 결정, 코드 실측)

**(a) protective = produced-bool producer(§0.4b).** protective는 두 소비자를 **import하지 않고**, 그들이
소비할 **plain bool**을 생산한다. seam 계약(compose) — **소비자는 전부 이미 비준·구현됨**:

| protective 산출 (§5/§6) | 타입 | 소비처 (이미 비준·구현) | 소비 signature(코드 실측) |
|---|---|---|---|
| `protective_classification(comparison, intermediate, envelope) → present` | `bool` | authority `degraded_lease_valid` 조건 1 | `protective_classification_present: bool\|None`(`authority/predicates.py:513`; #6 §6.3 조건 1 "protective classification(ADR-002-001 소관, 주입 flag) present") |
| `protective_capacity_exhausted(budget, domains) → bool` | `bool` | authority `degraded_lease_invalidated` | `protective_capacity_exhausted: bool\|None`(`authority/predicates.py:639`) |
| `protective_leases_reconciled(all_accounted, recon_current, no_conflicts) → bool` (**정의 §6.7**) | `bool` | authority state + liveauth re-arm 전제 | `protective_leases_reconciled: bool\|None`(`authority/state.py:129`; `liveauth/predicates.py:135` variant prereq string) |
| `protective_coverage_valid(profile, reserve_forecast) → bool` | `bool` | liveauth `continuous_validity` 10조건 中 | `protective_coverage_valid: bool\|None`(`liveauth/ContinuousValidityInputs`, `state.py:138`; `_INJECTED_CONTINUOUS_CONDITIONS` `predicates.py:96`) |
| `protective_coverage_added(profile, delta) → bool` | `bool` | liveauth §14.1 in-place expansion | `protective_coverage_added: bool\|None`(`liveauth/InPlaceExpansionInputs`, `state.py:204`; `_PROPORTIONAL_EXPANSION_FLAGS` `predicates.py:150`) |

- **타입 정합 + fail-closed 정합**: protective 산출은 전부 `bool`(양성 증명에서만 `True`). 소비 슬롯은 전부
  **진짜 주입 `bool|None`**(authority 3종·liveauth 2종, 전부 `None`/`False` ⇒ invalid/restrictive 측 —
  authority `degraded_lease_valid`는 protective_classification_present None⇒거부, liveauth `continuous_validity`는
  `all(getattr(inputs, name) is True ...)` `predicates.py:265–267`이라 None⇒False). **polarity 봉합(#6 fail-open
  REJECT 교훈)**: producer는 결코 "미판정 ⇒ True"로 새지 않는다(§4·§5·§6). **#10과 달리 orthostate BROKER_ORDER
  enum-basis 같은 예외 없음 — 5개 seam 전부 진짜 `bool|None`**(단순·일관). 실측 확인: authority
  `predicates.py:509–526`(degraded_lease_valid params)·`predicates.py:626–643`(degraded_lease_invalidated
  params)·`state.py:129`; liveauth `state.py:138/204`·`predicates.py:96/150/265–267`.
- **composition(런타임 배선) = caller 소관**: protective 산출 bool을 소비자 주입 슬롯으로 배선하는 **런타임**은
  **미래 Protective Action Controller/Live-Authorization/Reconciliation Service**(EV-L3)가 한다. Phase 1은 #9/#10의
  seam 이연과 **동형으로 런타임 배선을 이연**한다.
- **seam cross-check = MANDATED(test-only)**: Phase 1은 **test-only** 모듈(`tos/tests/protective/test_seam_
  authority.py`·`test_seam_liveauth.py`)에서 protective·(각 소비자)를 **둘 다 import**해 protective 산출 bool의
  **의미·polarity·fail-closed 거동**이 소비 signature 기대와 **일치함을 assert**한다(예: protective
  `protective_classification(...)`=False[증명 실패] ⇒ authority `degraded_lease_valid`의 조건 1 실패측;
  `protective_coverage_valid`=True ⇒ liveauth continuous-validity 통과측). **이 테스트는 package edge가
  아니다** — 테스트 import는 §7.1 `import tos.protective` package-closure에 **계상되지 않으므로** protective
  런타임 패키지의 sibling-edge-0건은 유지된다(#9 v1.1·#10 강화 동형).
- **cycle 부재**: protective↛{authority,liveauth,rcl,orthostate} ∧ 그들↛protective(전부 protective 조건을
  주입 flag로 소비·생산). CanonicalDecimal은 canonical에서. acyclic 명백.

**(b) protective는 authorize/transmit/release/mutate하지 않는다(§4.5·ADR §5 line 241).** protective는 결정
**bool/Admissibility만** 생산하고 egress transmit·capacity mutation·authorization issue·mode-set 메서드가
**부재**하다. 소비 authority(Protective Action Controller/authority/rcl/liveauth)가 실제 action을 gate한다 —
ADR §5 line 241 "It SHALL NOT enlarge aggregate authority, mutate the Risk Capacity Ledger outside its defined
transition interface, or transmit directly. The Broker Adapter / Broker Egress Gateway remains the final
transmission enforcement point."

**(c) 운영자 판단 지점**: seam을 **plain-bool decoupled(edge 0건)**로 둘지 대안 B(소비자 측 edge)로 갈지 —
decoupled 권장(§0.4b; edge·cycle 회피, #9/#10 정합).

### 3.5 소유권 분할표 — protective가 소유 / rcl·authority·liveauth·orthostate에서 소비·생산 (본 문서 최대 함정 지대)

> **선제 봉합(#8 C1·#10 OQ2 교훈)**: ADR-002-001 §12 Reserved Capacity·§14 Risk-Capacity Accounting은 rcl이
> **이미 소유·구현**한 capacity 산술과 인접하고, §8 Degraded Modes는 authority precedence/degraded-capability와,
> §11 Lifecycle은 orthostate order-state와, §9 Partition은 rcl `partition_verdict`와 인접한다. 아래 표는 각
> 조항을 **누가 소유하고 protective가 무엇을 소비(주입)/생산(produced-bool)하는지** 고정한다 — **중복 저작·
> 권위 중복을 구조적으로 배제**. 인용은 전부 **코드 실측 signature+라인**(sibling 설계 서사 아님 — #8 line 791
> 오명명 상속 사건 교훈).

| ADR-002-001 조항 | 소유 (코드 실측) | protective 처리 (소비/생산) |
|---|---|---|
| §4.1–4.5 protective domains(execution/broker/risk/margin/control) 열거 | **protective (신규)** | domain enumeration 모델 + `domain_enumeration_complete`(§4.1, PRD-EV-001) |
| §4.6/§12.4/§3.1.4 required dimensions + guarantee classification | **protective (신규)** | `GuaranteeLevel` 할당 모델 + `guarantee_level_resolved`(§4.2, PRD-EV-002) |
| §4.3 risk-capacity **reservation 산술** | **rcl** — `ProtectivePool`(`records.py:315`, `removed_from_normal_headroom`)·INV-009 Non-Borrowable | protective는 "risk-capacity=한 domain·guarantee=X"만 **선언**; 예약 산술 미소유(주입 소비) |
| §5 Protective Action Controller **authorize/transmit** | **authority + egress(런타임)** — ADR §5 line 241 | protective는 **classification bool 생산**(§3.4); authorize/transmit 미소유(§4.5) |
| §6.1/§6.2 final/intermediate classification 술어 | **protective (신규)** predicate-only | `protective_classification`(§5); **produces `protective_classification_present`** → `authority/predicates.py:513` |
| §6.3 risk dimensions **수치** | **ARE (ADR-002-021, 미구현 tos 패키지)** | protective는 **주입 aggregate-risk 비교**만; 수치 미산출(§0.2) |
| §7 protective action envelope subordination | **protective (신규)** predicate-only (envelope **값**은 ADR-002-014) | `envelope_subordinate`(§6.6); 값 주입 |
| §8 degraded modes **enum + precedence** | **authority** — `AuthorityState`(`vocabulary.py:47`)·`PRECEDENCE_RANK`(`vocabulary.py:54`)·`restrictive_dominates`·`CapabilityType`(`vocabulary.py:24–33`) | protective는 **재저작 금지**(권위 중복 배제); mode/dominating-restriction verdict 주입 소비 |
| §8.1–8.4 per-mode 허용 protective action | **protective (composition)** predicate-only | `mode_permits_protective`(§6.1); authority mode + §5 classification + §7 envelope 조합 |
| §8.3.1 CONTAINED emergency-action(reduce-only-by-construction) | **protective (신규)** predicate-only | `contained_emergency_admissible`(§6.1); pre-approved bounded set 주입 |
| §8.5 CONTAINED→DEGRADED_PROTECTIVE de-restriction (v0.7 U1) | **protective (신규 normative decision)** predicate-only | `derestriction_admissible`(§6.1); authority governed-decision·classifier-trust 주입; 거버넌스는 authority |
| §9 partition **capacity consumption mechanics** | **rcl** — `partition_verdict(quorum_available)`(`predicates.py:711`)·sub-ledger(§5.5)·`PartitionVerdict`(`state.py:109`) | protective는 verdict 주입 소비 |
| §9 partition-time **lease-admissibility**(overlap-first/cancel-first) | **protective (신규, ADR line 448 "ADR-002-001 owns")** predicate-only | `partition_lease_admissible`(§6.2); rcl partition/lease-validity + pre-proven-scope/staleness 주입 |
| §10 time-untrusted protective behavior | **protective (신규)** predicate-only (time 산술=`tos.time`) | `time_untrusted_protective_admissible`(§6.5); time-trusted 주입 |
| §11.1 protective ownership(enum) | **protective (신규)** | `ProtectiveOwnership`(§3.1.6 verbatim) |
| §11.2/11.3 Cancellation Arbiter | **protective (신규)** predicate-only | `cancellation_admissible`(§6.3); orthostate `BrokerOrderState`/`KnowledgeState` 주입 소비 |
| §11.4 protection gap / non-atomic replacement | **ADR-002-011 (PR-EV)** | protective 미소유(partition-lease-admissibility만 §9) |
| §12.1–12.3 reserved commitment/consumption/**exclusivity** | **rcl** (`ProtectivePool`/`ProtectiveLease` `records.py:315/348`, sub-ledger §5.5) + **authority** (`lease_scope_exclusive`; `exclusiv*`는 **rcl 부재**·authority 소재 — 실측 정정) | protective 미소유 |
| §12.4 guarantee levels + common modes | **protective** (어휘·assignment) + **rcl** (capacity 측) | protective가 `GuaranteeLevel` 어휘·완전성 소유(§4.2) |
| §12.5 dynamic reserve sufficiency | **protective (신규)** predicate-only (threshold=Safety Profile) | `reserve_sufficiency`(§6.7); **produces `protective_coverage_valid`** → `liveauth/state.py:138` |
| §12.6 multi-account minimum allocation | **protective (신규)** predicate-only (arithmetic=rcl) | `account_minimum_preserved`(§6.8) |
| §13 exhaustion + bounded retry | **protective (신규)** predicate-only + **rcl** (preserve=INV-005/012) | `retry_admissible`(§6.4); **produces `protective_capacity_exhausted`** → `authority/predicates.py:639` |
| §14.1–14.5 Risk-Capacity Accounting | **rcl** — INV-005/006/007·`transition_allowed(...,FINAL_QUANTITY_PROOF)`(`predicates.py:468`)·`QUARANTINED_UNKNOWN` | protective 미소유(전부 rcl) |
| §15 trapped exposure | **rcl** — INV-011 Trapped Non-Reducible·`TRAPPED_CONSUMED`(`vocabulary.py:30`)·`trapped_preserved`(`state.py:128`) | protective는 trapped verdict **소비만**(Admissibility.TRAPPED 산출 — capacity state 재저작 아님) |
| §16 recovery/exit + re-arm | **liveauth** (re-arm·`continuous_validity`) + **rcl** (reconciliation) | protective는 `protective_coverage_valid`/`protective_leases_reconciled` **생산**(§6.7) |

> **소유권 분할 명시(#8 C1·#10 §3.5 교훈 동형)**: §14(Risk-Capacity Accounting)·§15(Trapped)·§12.1–12.3
> (Reserved commitment/consumption/exclusivity)는 **거의 전부 rcl의 capacity 산술**이다 — protective는 이를
> **재저작하지 않는다**. §8(mode enum·precedence)은 **authority 소유** — protective는 mode를 **재선언하지
> 않는다**. protective가 genuinely 소유하는 것은 (i) domain enumeration + guarantee-level **완전성**(§4,
> PRD-EV-001/002 core), (ii) protective-action **classification 술어**(§6), (iii) degraded-mode **전이 가드**
> (§8.5 de-restriction·§8.3.1 emergency — mode enum이 아니라 전이 admissibility), (iv) partition-time
> **lease-admissibility**(§9, ADR가 명시 owns), (v) protective **ownership/cancellation-arbiter**(§11), (vi)
> **bounded-retry/exhaustion**(§13), (vii) time-untrusted·envelope·sufficiency 술어. 이 7 축은 **capacity
> 산술도 mode enum도 authority-epoch도 아니며**, rcl/authority가 **소비할 produced-bool** 또는 rcl/authority에서
> **소비하는 주입 verdict**로 seam이 봉인된다(§3.4). 같은 현상(예: trapped exposure)을 **다른 좌표**(rcl=capacity
> state, protective=admissibility 판정)에서 다루므로 중복·모순이 아니다(§4.4 좌표 비붕괴).

> **실측-원천 결함 방지 정정(#8 line 791→#10 상속 교훈)**: 본 표는 sibling 설계 서사가 아니라 **코드**로
> 검증했다. 정정 사항: (1) rcl transition cause enum은 **`TransitionCause`**(`vocabulary.py:79`)이며
> `CapacityTransitionCause`가 **아니다**; (2) rcl은 ADR-002-002(INV-### 시리즈: INV-009 Non-Borrowable·INV-011
> Trapped 등)와 **ADR-002-012**(RCLP-INV-### 시리즈: RCLP-INV-006/008/009/011)를 **둘 다** realize하므로
> "rcl INV-001..012 = ADR-002-002 시리즈"는 부정확(RCLP-INV-006은 ADR-002-012 §9 귀속 — 실측 3곳 일치;
> INV-002/003/005/010 토큰은 non-contiguous 부재); (3) `exclusiv*`는 **rcl에 부재**(0건)이고 lease
> exclusivity는 **authority `lease_scope_exclusive`** 소재; (4) rcl `RELEASED` 전이 cause는 **오직
> `FINAL_QUANTITY_PROOF`**(`predicates.py:468` `return cause is TransitionCause.FINAL_QUANTITY_PROOF`).

---

## 4. 불변식

모두 frozen 모델 구성-불변식(구성 실패) 또는 순수 술어(property)로 실현한다. **앵커는 PRD-EV-001/002·§21
acceptance-criteria(불릿)·§-clause·SAFE-###**이며 **새 INV 시리즈를 창작하지 않는다**(§0.4f). **fail-closed
discipline**: 미열거/미할당/미증명/None에 대한 술어는 절대 vacuous permissive/ADMISSIBLE가 되지 않으며, live
허용은 *양성 증명*을 요구하고, 각 가드에 **both-ways canary**(가드가 실제로 발화함 ∧ 정당한 통과를 막지 않음)를
붙인다.

### 4.1 domain enumeration completeness 중앙 불변식 (PRD-EV-001 substrate — ADR §4 line 158·§4.6 line 205/217)

**중앙 결정**: "protective capacity가 필요한 resource domain은 *전부* 열거돼야 하고, 미열거 domain은
`UNAVAILABLE`로 취급된다." ADR §4 line 158 verbatim: "Protective capacity SHALL be defined across **all
resources whose exhaustion could prevent containment**." 실현(구조적 3중):

1. **`domain_enumeration_complete(declared: frozenset[ProtectiveResourceDomain], required: frozenset[Protective
   ResourceDomain]) -> bool`**: `required ⊆ declared`일 때만 True. **required 미지정 ⇒ fail-closed**(전 7군
   최소 집합 §2.2-(3)으로 취급). "assume-present" 생성자·기본 True 경로가 **존재하지 않는다**.
2. **미열거 domain = UNAVAILABLE**: `guarantee_level_resolved`(§4.2)가 declaration tuple에서 domain 조회 시
   **부재 ⇒ `UNAVAILABLE`**(most-restrictive) — "없으니 통과" 경로 부재. (rcl `within_limits` missing-dim=
   restrictive `5.1` 규칙·#10 BC-INV-001 미선언=unavailable 정신 동형.)
3. **`+Broker` 확장은 required를 넓히기만 한다**(§2.2-(3) "at least"): broker/venue별 추가 domain은 required
   집합을 **확대**할 뿐 축소하지 않는다(주입; 미확대 ⇒ 최소 7군 유지). 넓어진 required에 대해 declared가 부족하면
   incomplete.

**canary(both-ways)**: (a) required의 한 domain이 declared에서 빠지면 `domain_enumeration_complete` = False
(가드 발화; 그 domain은 UNAVAILABLE로 취급); (b) required 전부 declared ⇒ True(양성 side — 정당한 완전 열거를
막지 않음). 빈 declared + 비어있지-않은 required ⇒ False(vacuous True 금지).

### 4.2 guarantee-level assignment completeness 중앙 불변식 (PRD-EV-002 substrate — ADR §4.6 line 215/217·§12.4)

**중앙 결정**: "열거된 각 domain은 evidenced guarantee level을 갖고, 미할당은 최저(`UNAVAILABLE`), priority는
reservation이 아니다." ADR §4.6 line 217 verbatim: "A resource SHALL NOT be described as guaranteed unless its
reservation mechanism and failure independence have been demonstrated. Priority is not reservation." 실현:

1. **`guarantee_level_resolved(domain, profile) -> GuaranteeLevel`**: profile declaration에서 domain의 assigned
   level 반환. **부재/None ⇒ `UNAVAILABLE`**(최저). 승격 경로 부재.
2. **`is_reserved_guarantee(level, declaration) -> bool`**: `PHYSICALLY_RESERVED`는 `declaration.
   failure_independence_evidenced == True`일 때만 reserved로 인정; `LOGICALLY_RESERVED`는 `reservation_
   mechanism_evidenced == True` + common-mode note 존재일 때만; **`PRIORITIZED_ONLY`/`BEST_EFFORT`/`UNAVAILABLE`은
   결코 reserved 아님**(§3.1.4 line 144·§12.4 line 543). evidence flag 부재 ⇒ **not reserved**(양성 증명 요구).
3. **`guaranteed_requires_demonstration`**: level이 `PHYSICALLY_RESERVED`/`LOGICALLY_RESERVED`로 선언됐으나
   `reservation_mechanism_evidenced`/`failure_independence_evidenced`가 False/None ⇒ **구성 실패 또는 resolved를
   `PRIORITIZED_ONLY` 이하로 강등**(ADR line 217 "SHALL NOT be described as guaranteed unless demonstrated").

**canary(both-ways)**: (a) domain에 guarantee 미할당 ⇒ resolved = `UNAVAILABLE`(가드 발화); PRIORITIZED_ONLY를
reserved로 쓰려는 입력 ⇒ `is_reserved_guarantee` False(§3.1.4 가드); PHYSICALLY_RESERVED 선언 + evidence flag
False ⇒ 강등/구성 실패(가드 발화); (b) PHYSICALLY_RESERVED + failure_independence_evidenced True ⇒ reserved 인정
(양성 side). **[SAFE-003 fail-closed; SAFE-015 exclusive commitment; SAFE-040 protective control in degraded]**

### 4.3 classification purity + strategy-label 비권위 (ADR §6 line 247–249; §4.5 정신)

- **classification은 strategy label을 읽지 않는다**: `protective_classification`(§5)의 입력은 **주입
  conservative aggregate-risk 비교값**(final/current/no-action/worst-intermediate)과 hard-limit-exceedance
  좌표·credible-space-bounded flag뿐이다 — `strategy_flag`·`sell_direction`·`exit_name`·`reduce_intent`·
  `operator_description`·`correlation`을 **입력 필드로 갖지 않는다**(ADR §6 line 249 "non-authoritative"의
  구성적 실현; 설계 #4 evidence≠authority 정신 동형).
- **증명 불가 ⇒ risk-increasing**: final<current(§6.1) ∧ worst-intermediate≤no-action(§6.2) ∧ no
  exceedance-increase를 **positively** 보일 수 없으면 `RISK_INCREASING_DENIED`(§6.2 line 279). credible-state-
  space 미경계 ⇒ `UNKNOWN_CONSERVATIVE`(§6.2 line 277 "treated conservatively as UNKNOWN, never silently
  excluded"). vacuous `PROTECTIVE_PROVEN` 경로 부재.
- **canary(both-ways)**: (a) strategy_flag=protective이나 final≥current ⇒ `RISK_INCREASING_DENIED`(label이
  override 못 함 — 가드 발화); (b) final<current ∧ worst-intermediate≤no-action ∧ bounded ⇒ `PROTECTIVE_PROVEN`
  (양성 side). **[SAFE-011 protective authority not strategy; SAFE-013 aggregate risk]**

### 4.4 좌표 비붕괴 (guarantee-level ≠ capacity-state ≠ authority-mode ≠ knowledge ≠ confidence)

- **별개 축**: protective `GuaranteeLevel`(reservation 보장 축) / rcl `CapacityState`(capacity 소비 축,
  `TRAPPED_CONSUMED` 등) / authority `AuthorityState`(system mode 축, `DEGRADED_PROTECTIVE` 등) / orthostate
  `KnowledgeState`(per-action aggregate) / recon `FieldConfidenceClass`(per-field evidence). protective 토큰
  (`PHYSICALLY_RESERVED`/`UNAVAILABLE`/`ADMISSIBLE`/`TRAPPED`/`PROTECTIVE_PROVEN`)은 다른 네 축과 **겹치지
  않는다**(`TRAPPED`는 rcl `TRAPPED_CONSUMED`와 어휘 근접하나 protective는 **admissibility 판정**, rcl은
  **capacity state** — 별개 타입).
- **비붕괴 성립 방식**: (i) **타입 구분**(별개 StrEnum 클래스) + (ii) **미import**(protective는 rcl/authority/
  orthostate/recon을 import하지 않아 swap 자체 원천 차단). canary: test-only 회귀로 `protective.Admissibility.TRAPPED
  is not rcl.CapacityState.TRAPPED_CONSUMED`; `DEGRADED_PROTECTIVE ∉ protective 어휘`(authority 소유).
- **좌표 비붕괴 = §3.5 소유권 분할의 근거**: "이 resource가 얼마나 보장되나"(protective guarantee) ≠ "이 capacity가
  얼마 소비됐나"(rcl state) ≠ "시스템이 어느 mode인가"(authority) — 셋을 한 필드에 담으면 축 붕괴(#6 §4.7·#8
  §0.4e·#9 §4.2·#10 §4.4 상속).

### 4.5 representation ≠ enforcement (ADR §5 line 241; §11.4 line 506)

`ProtectiveCapacityProfile`·declaration·classification/de-restriction/lease-admissibility/cancellation/retry
bool은 **비전송·비-enforcing representation**이다 — "domain X가 PHYSICALLY_RESERVED" 기록이 capacity를 예약하거나
order를 전송하지 않는다. ADR §5 line 241 "It SHALL NOT enlarge aggregate authority, mutate the Risk Capacity
Ledger outside its defined transition interface, or transmit directly"; §11.4 line 506 "A submitted, transmitted,
or acknowledged replacement order SHALL NOT receive optimistic protection credit." ⇒ protective에 **egress
transmit·capacity mutate·authorization issue·mode set·capacity release 메서드가 부재**(구성적 부재 — 설계 #9/#10
representation≠mutation 정신 동형). protective는 결정 bool/Admissibility를 **반환**할 뿐 소유 authority(rcl/
authority/Protective Action Controller 런타임)가 enforce한다. 이 불변식이 rcl/authority/liveauth/orthostate/
evidence 미import(§3.5)의 근거이기도 하다.

### 4.6 append-only + same-id/diff-bytes 충돌 (§2.3; §18)

모델에 update/delete 연산 부재(§2.0). profile revalidation·개정은 새 version(새 identity)의 append로 표현.
same profile identity + diff canonical digest ⇒ `classify_record_pair`(`record_pair.py:52`) = `CRITICAL_CONFLICT`
(`record_pair.py:43`; 위조·재발행 위조만 — contain 양쪽 보존, no last-write-wins). property: id⊥digest이므로
CRITICAL_CONFLICT reachable(가드 발화); id=f(digest)면 unreachable임을 회귀로 고정(§3.1). null digest(DRAFT) ⇒
`NOT_COMPARABLE`(`record_pair.py:49`, false conflict 방지). **[SAFE-050 safety configuration governance;
SAFE-051 decision/transition evidence]**

---

## 5. core 술어 — domain enumeration · guarantee-level · classification (PRD-EV-001/002 substrate + §6)

**핵심 난제**: PRD-EV-001/002의 **completeness**를 순수 함수로 저작하되, (i) required domain 집합·required
guarantee level·aggregate-risk 비교값을 **주입 판정/파라미터**로 두어 하드코딩 수치·broker 값을 배제하고(§8),
(ii) **fail-closed(§4.1/§4.2)를 구조로** 지키며(permissive 기본 부재), (iii) 미열거·미할당·미증명을
**most-restrictive**로 처리한다. **닫는 PRD-EV = 0건**(`/3`·`+Broker` 잔여 — §1).

### 5.1 domain enumeration completeness (§4.6; ADR line 158/205 — PRD-EV-001 substrate, core L1 슬라이스)

`domain_enumeration_complete(profile: ProtectiveCapacityProfile, required: frozenset[ProtectiveResourceDomain])
-> bool`:

| 입력 조건 | 산출 | 근거 |
|---|---|---|
| `required ⊆ {d.domain for d in profile.declarations}` ∧ required 비어있지-않음 | `True` | §4.6 line 205 "SHALL be evaluated separately for at least [7군]" |
| required의 한 domain이 declaration tuple에 부재 | `False`(그 domain은 §4.2에서 `UNAVAILABLE`) | ADR line 158·§4.1; #10 BC-INV-001 정신 |
| required 미지정(None) | 최소 7군(§2.2-(3))으로 취급 후 판정 | fail-closed(전 domain 필요) |

- **required는 주입 + 최소 하한**: 어떤 배치가 어떤 domain을 요구하는지는 주입되나, **하한은 §4.6의 7군**이며
  broker/venue별 domain은 required를 **확대**한다(§4.1 규칙 3; `+Broker`가 PRD-EV-001의 `/3+Broker`인 이유).
- **canary(PRD-EV-001)**: (a) OPERATOR_EMERGENCY_PATH 미선언 ⇒ complete False + 그 domain UNAVAILABLE(§4.2);
  (b) 7군 전부 선언 ⇒ complete True(양성 side). **닫지 않음**: broker별 domain 열거(+Broker)·integration(/3)
  잔여로 PRD-EV-001은 EV-L1으로 닫히지 않는다.

### 5.2 guarantee-level assignment completeness (§4.6/§12.4; ADR line 215/217 — PRD-EV-002 substrate, core L1 슬라이스)

`guarantee_level_resolved(domain, profile) -> GuaranteeLevel` + `is_reserved_guarantee(declaration) -> bool`
(§4.2 상술):

| 입력 조건 | 산출 | 근거 |
|---|---|---|
| domain의 declaration 존재 ∧ level 명시 ∧ 해당 evidence flag 충족 | 그 level (reserved면 `is_reserved_guarantee` True) | §4.6 line 215; §12.4 line 539–545 |
| domain declaration 부재 또는 level None | `UNAVAILABLE` | §4.2; line 217 |
| level=`PHYSICALLY_RESERVED` ∧ `failure_independence_evidenced=False/None` | 강등(`PRIORITIZED_ONLY` 이하) 또는 구성 실패 | line 217 "SHALL NOT be described as guaranteed unless demonstrated" |
| level=`PRIORITIZED_ONLY`/`BEST_EFFORT` | `is_reserved_guarantee` = **False**(항상) | §3.1.4 line 144; §12.4 line 543 |

- **guarantee_assignment_complete(profile, required) -> bool**: `domain_enumeration_complete`(§5.1) ∧ 모든
  declared domain이 `guarantee_level_resolved != UNAVAILABLE`(또는 UNAVAILABLE이 명시적 evidenced 선언)일 때만
  True. 미할당(암묵 UNAVAILABLE) domain 존재 ⇒ False. **canary(PRD-EV-002)**: (a) 한 domain guarantee 미할당 ⇒
  complete False + resolved UNAVAILABLE; PRIORITIZED_ONLY를 reserved 취급 시도 ⇒ `is_reserved_guarantee` False;
  (b) 전 domain evidenced level 할당 ⇒ complete True(양성 side). **닫지 않음**: integration(/3) 잔여.
- **common-mode honest 표현(§12.4 line 547)**: `LOGICALLY_RESERVED`는 `common_mode_note` 필드가 non-null일
  때만 인정(lower-level dependency 명시). single serialized session/global rate limit domain은 `PRIORITIZED_ONLY`/
  `BEST_EFFORT`로만 분류하고 "documented honestly" — #10 §6.5 partition-protective-class와 인접하나 protective는
  guarantee-level 축만(broker class 판정은 brokercap 주입).

### 5.3 protective action classification (§6.1/§6.2; ADR line 251–279 — produces `protective_classification_present`)

`protective_classification(comparison: AggregateRiskComparison, intermediate: IntermediateStateWitness, *,
envelope_within_hard: bool|None) -> ProtectiveActionOutcome`:

- **§6.1 final-state test(line 255–263)**: `comparison.final_conservative_risk < comparison.current_conservative
  _risk`(관련 risk dimension별) ∧ within Hard Safety Envelope. 이미-초과 regime(ADR-002-002 §23.2, 주입 flag)에서는
  "return-toward-envelope trajectory ∧ no exceedance 증가"로 완화(§6.1 line 263) — 단일 action이 full envelope
  복원할 필요 없음.
- **§6.2 intermediate-state test(line 265–279)**: 모든 credible partial-fill/ordering/leg-failure/late-fill/
  basis/liquidity/margin 조합에서 `intermediate.worst_intermediate_risk <= comparison.no_action_risk` ∧ **no
  credible intermediate가 hard-limit exceedance 증가**. **resolution horizon**(§6.2 line 277)은 주입(Safety
  Profile 소유, "no longer than the shortest interval sufficient"; 하드코딩 없음). **credible-state-space
  bounded**(RFC-002 §3.1.17: Broker Capability Profile + Adverse Scenario Set 경계, 주입 flag) — 미경계 조합 ⇒
  `UNKNOWN_CONSERVATIVE`(silent exclude 금지, line 277).
- 산출: 위 둘 다 positively 성립 ∧ bounded ⇒ `PROTECTIVE_PROVEN`; 성립 불가 ⇒ `RISK_INCREASING_DENIED`(line
  279 "classified as risk increasing and denied in degraded mode"); 미경계 ⇒ `UNKNOWN_CONSERVATIVE`. **이미-초과
  regime에서 non-worsening path도 증명 불가 ⇒ CONTAINED emergency-path(§8.3, §8.3.1)로 라우팅**(line 279) —
  §6.1 술어가 그 라우팅 flag를 산출.
- **produced-bool**: `protective_classification_present := (outcome == PROTECTIVE_PROVEN)` → authority
  `degraded_lease_valid` 조건 1(`predicates.py:513`). aggregate-risk 수치는 **주입**(ARE/ADR-002-021 — protective는
  비교만, 수치 미산출 §0.2).
- **canary(both-ways)**: (a) final≥current ⇒ RISK_INCREASING_DENIED; worst-intermediate>no-action ⇒
  RISK_INCREASING_DENIED; credible-space unbounded ⇒ UNKNOWN_CONSERVATIVE(각 가드 발화); strategy label만으로
  PROTECTIVE_PROVEN 불가(§4.3); (b) final<current ∧ worst-intermediate≤no-action ∧ bounded ∧ within envelope ⇒
  PROTECTIVE_PROVEN(양성 side). **[SAFE-004 hard envelope; SAFE-013 aggregate risk; SAFE-021 at-most-one effect;
  SAFE-025 partial/async fill]** EV: FD-EV-001·ARE-EV-010·PR-EV-005 substrate(전부 EV-L2+, **닫지 않음**).

---

## 6. predicate-only 술어 — degraded-mode·partition-lease·cancellation·retry·time·envelope·sufficiency

전부 predicate-only(EV 주장 금지; 타-ADR EV family substrate). property는 authority mode/precedence verdict·
rcl partition/trapped verdict·orthostate order-state·time-trusted·budget을 **hypothesis 생성 주입값**으로
다뤄 "임의 유효 주입 하 보수적 성립"을 검증(특정 값·mode enum 비의존, 하드코딩 없음 — §8).

### 6.1 degraded-mode 술어 — §8.5 de-restriction · §8.1–8.4 per-mode · §8.3.1 emergency (mode enum은 authority)

**mode enum·precedence는 authority 소유(§3.5) — protective는 전이 가드·per-mode 허용만 저작한다.**

- **`derestriction_admissible(inputs: DeRestrictionInputs) -> bool`(§8.5, v0.7 U1)**: `CONTAINED`→
  `DEGRADED_PROTECTIVE`는 다음이 **전부** 양성일 때만 True — (i) **not automatic**: `elapsed_time_only`·
  `connectivity_restored_only`·`quiet_time_only`·`cache_agreement_only`·`absence_of_adverse_signal_only` 중
  어느 것도 유일 근거 아님(§8.5 line 391 verbatim "Elapsed time, connectivity or session restoration, broker
  reconnection, quiet time, cache agreement, or the mere absence of new adverse signals SHALL NOT cause or
  contribute to this transition"); (ii) **affirmative re-establishment**: `reconciled_authoritative_state`(주입,
  orthostate RECONCILED) ∧ `safety_authority_current`(주입, authority) ∧ `hard_and_runtime_profile_valid`(주입)
  ∧ `critical_input_trust_restored`(주입, ADR-002-018) — cached/last-known-good/heartbeat 값은 미충족(line 402);
  (iii) **explicit governed decision**: `explicit_safety_authority_decision`(주입, authority restrictive-authority
  governance) — strategy/ordinary-execution/operator-convenience/readiness-inference 경로 아님(line 403–407);
  (iv) **no dominating stronger restriction**: `dominating_halt_or_incident == False`(주입, authority/ADR-002-027/
  015). **임의 미성립/None ⇒ False(CONTAINED 유지, fail-closed; line 389)**. de-restriction 후에도 모든 protective
  action은 §6.1/§6.2 proof에 여전히 종속(line 413 "restores its use, not any exemption from per-action proof");
  revocable(trust 재실패 ⇒ CONTAINED 복귀 §12.5).
  - **not a re-arm(line 383–386)**: 이 전이는 new-risk/live authority를 부여하지 않으므로 ADR-002-007 §12 re-arm
    workflow·§13 dual-control quorum을 **호출·충족하지 않는다** — protective는 liveauth re-arm을 건드리지 않고
    별개 술어로 저작(§3.5).
  - **canary(both-ways)**: (a) reconnection_only=True + 나머지 미성립 ⇒ False(가드 발화; "reconnect로 자동
    de-restrict" 차단); safety_authority_current=None ⇒ False; dominating_halt=True ⇒ False; (b) 네 조건 전부
    양성 + not-automatic ⇒ True(양성 side). **[SAFE-003; SAFE-041 Safety Authority governs; SAFE-044 no automatic
    re-arm]**
- **`mode_permits_protective(mode_rank: int|None, action: ProtectiveActionOutcome, envelope_ok: bool|None) ->
  bool`(§8.1–8.4)**: 주입 `mode_rank`(authority `PRECEDENCE_RANK` verdict)와 §5.3 classification·§6.6 envelope을
  조합해 per-mode 허용 판정(예: DEGRADED_PROTECTIVE는 cancellation·approved protective·reconciliation 허용, new
  risk-increasing 금지 §8.2). **mode enum 재선언 없음** — rank/verdict 주입. None ⇒ 보수(deny).
  > **[v1.2 부기 — 설계-트랙 판단 지점 D1 처분: 현행 비준 signature 유지(의도적 이연)]** 구현 커밋
  > `02de5c54`에 대한 **독립 적대적 코드 리뷰**가 본 술어의 **per-mode 표현력**을 *코드 결함이 아니라*
  > **설계-트랙 판단 지점**으로 회부했다. 실측: 구현
  > (`tos/src/tos/protective/predicates.py:398–426`)은 `mode_rank`를 **`None` 여부로만** 읽고
  > (`:422–423` `if mode_rank is None: return False`), 나머지 판정은 `envelope_ok is not True ⇒ False`
  > (`:424–425`)와 `action is ProtectiveActionOutcome.PROTECTIVE_PROVEN`(`:426`)이다 — 즉 rank 값 자체로는
  > §8.1–8.4의 **mode별 허용 집합 차등**(위 예시의 DEGRADED_PROTECTIVE vs 타 mode)을 구분하지 못한다.
  > **처분: 현행 비준 signature `(mode_rank: int|None, action, envelope_ok)` 유지 — 코드 무변경.**
  > 근거: 이 signature는 mode별 순위·임계를 **담지 않으므로**, 여기서 per-mode 구분을 강제하려면 mode
  > 순위/임계를 **본 패키지에 하드코딩**해야 하고 그것은 §0.4e authority-duplication 배제와 §3.5 소유권
  > 분할(“`PRECEDENCE_RANK`의 per-mode ordering·threshold는 **authority 소유**”; 본 절 "mode enum 재선언
  > 없음")을 정면으로 위반한다. 따라서 **per-mode 강제는 authority 하류 소관**이며, protective는 주입된
  > rank 좌표 위에서 fail-closed 합성만 수행한다(현행 거동이 계약대로다).
  > **향후 경로**: per-mode 구분이 *실제로* 필요해지면 **별도 설계 개정**으로 mode별 허용-집합 **주입
  > verdict**를 추가한다(하드코딩이 아니라 seam 확장) — **현 Phase-1 스코프 아님**, 본 항목을
  > **의도적 이연**으로 기록한다. 비준 효력(2026-07-25, v1.1)·§10.2 seam 판단 지점 승인 불변.
- **`contained_emergency_admissible(inputs) -> bool`(§8.3.1)**: CONTAINED에서 §6.2 fresh 계산에 **의존하지
  않고**, (i) `in_preapproved_bounded_set`(주입, Safety Profile) ∧ (ii) `reduce_only_by_construction`(모든 governed
  dimension에서 현 reconciled position 기준 — line 362) ∧ (iii) `within_bounded_emergency_envelope`(qty/notional/
  rate/duration/scope) ∧ (iv) `independently_authorized`(Safety Authority 또는 operator emergency path §23.2) ∧
  (v) §14.1–14.4 Potentially-Live/Final-Quantity rule 유지(주입, rcl)일 때만 True. **미성립 ⇒ trapped(§15)·escalate
  (§13; line 367)**. operator authorization은 unproven action을 protective로 만들지 않는다(line 364·§23.2).
  canary: reduce-only-by-construction 미성립 ⇒ False.

### 6.2 partition-time lease-admissibility (§9 line 448; ADR "ADR-002-001 owns this rule")

`partition_lease_admissible(action_kind: ProtectiveActionKind, scope: ProtectiveLeaseAdmissibilityScope, *,
within_pre_proven_scope: bool|None, staleness_ok: bool|None, lease_valid_for_new_transmission: bool|None,
partition_new_commitment_denied: bool|None) -> Admissibility`:

- **overlap-first/add-only(기존 protection 제거 없이 신규 protection 확립)**: `within_pre_proven_scope == True`
  ∧ `staleness_ok == True` ∧ `lease_valid_for_new_transmission == True`(주입, rcl lease-validity §9 line 433–446)
  ⇒ `ADMISSIBLE`(§9 line 448 "the lease MAY support overlap-first / add-only protective action").
- **cancel-first(또는 기존 protection 제거·감소·약화)**: pre-proven scope 밖 또는 staleness 초과 ⇒ current
  admissibility 확립 불가 ⇒ **`TRAPPED`**(§9 line 448 "SHALL NOT proceed under the lease during partition ...
  the exposure remains conservatively covered and trapped (§15) rather than transmitted on stale admissibility").
- **`partition_new_commitment_denied == True`이나 already-valid lease 소비**만 허용(§9 line 426·§12.2; new
  Aggregate Protective Commitment는 rcl `partition_verdict` `new_mutation_denied` 소관 — 주입). **임의 None ⇒
  보수(TRAPPED/PROHIBITED)**.
- **canary(both-ways)**: (a) cancel-first + within_pre_proven_scope=False ⇒ TRAPPED(가드 발화; stale admissibility
  전송 차단); staleness_ok=None ⇒ TRAPPED; lease_valid=None ⇒ PROHIBITED; (b) overlap-first + scope 내 + staleness
  ok + lease valid ⇒ ADMISSIBLE(양성 side). **[SAFE-024 external-state reconciliation; SAFE-035 trustworthy time;
  SAFE-048 partition-tolerant]** EV: RC-EV-012·SA-EV-004·PR-EV-001/002 substrate(EV-L2+, **닫지 않음**).

### 6.3 protective ownership + Cancellation Arbiter (§11.1–11.3)

`cancellation_admissible(ownership: ProtectiveOwnership, *, protection_no_longer_required: bool|None,
within_hard_envelope: bool|None, equivalent_replacement_live: bool|None, continued_existence_worsens_aggregate:
bool|None, controller_authorizes_removal: bool|None, cancellation_worsens_aggregate: bool|None) -> bool`:

- **`SAFETY_OWNED`(§11.1 line 475–479)**: (protection_no_longer_required ∧ within_hard_envelope) ∨
  (equivalent_replacement_live) ∨ (continued_existence_worsens_aggregate ∧ controller_authorizes_removal)일 때만
  cancellable. strategy/ordinary-execution cleanup으로 취소 불가(line 475). 세 disjunct 모두 미성립/None ⇒ **False**.
- **ordinary risk-increasing order(§11.3)**: risk-increasing ∧ no-longer-authorized ∧ `cancellation_worsens_
  aggregate == False`일 때만 Cancellation Arbiter 통과. **protective 평가가 ordinary cancellation에 선행**(§11.2
  line 487 "Protective evaluation SHALL precede ordinary strategy cancellation").
- **no optimistic credit(§11.4 line 506)**: `equivalent_replacement_live`는 **authoritatively confirmed live**
  일 때만 True(주입; submitted/transmitted/acknowledged replacement ⇒ optimistic credit 금지 — 주입 flag가
  "confirmed"를 요구). cancel-ack ≠ FQP(§14.2; rcl `transition_allowed(...,FINAL_QUANTITY_PROOF)` 소관 — protective는
  주입 소비).
- order-state(BrokerOrderState·KnowledgeState)는 **orthostate 주입 좌표**로 소비(§3.5; 미import).
- **canary(both-ways)**: (a) SAFETY_OWNED + 세 disjunct 미성립 ⇒ False(가드 발화; 무분별 취소 차단);
  equivalent_replacement가 submitted-but-unconfirmed ⇒ optimistic credit 없이 False; (b) equivalent_replacement_live=
  True(confirmed) ⇒ cancellable(양성 side). **[SAFE-002 no unmanaged exposure; SAFE-021]** EV: PR-EV-011·X-EV-006
  substrate(EV-L2+, **닫지 않음**).

### 6.4 bounded-retry + exhaustion (§13; produces `protective_capacity_exhausted`)

`retry_admissible(*, budget_remaining: int|None, duplicate_economic_effect_possible: bool|None, unknown_outcome:
bool|None, dedup_proven: bool|None) -> bool` + `protective_capacity_exhausted(domains, budgets) -> bool`:

- **bounded retry(§13 line 583–594)**: retry는 `budget_remaining > 0` ∧ `duplicate_economic_effect_possible ==
  False`일 때만 True(§13.3 "policy-approved retry where retry cannot create duplicate economic effect"). **UNKNOWN
  outcome + dedup 미증명 ⇒ no retry**(§14.4 line 639 "blind resubmission is prohibited"; unknown_outcome=True ∧
  dedup_proven≠True ⇒ False).
  > **[v1.2 부기 — 설계-트랙 판단 지점 D2 처분: 현행 유지 + 회귀 보호 유지 의무]** 같은 독립 적대적 코드
  > 리뷰(구현 커밋 `02de5c54`)가 `retry_admissible`의 **`unknown_outcome=None` 미차단**(unknown 여부 *자체*가
  > 미상일 때 §14.4 blind-resubmission 가드가 발화하지 않음)을 *코드 결함이 아니라* **설계-트랙 판단 지점**
  > 으로 회부했다. **처분: 현행 유지 — 코드 무변경.**
  > 근거(리뷰 확인): 구현(`tos/src/tos/protective/predicates.py:588–620`)에서 **duplicate-effect 게이트가
  > 선행 방어**한다 — `if duplicate_economic_effect_possible is not False: return False`(`:617–618`)가
  > unknown 분기 `return not (unknown_outcome is True and dedup_proven is not True)`(`:620`)보다 **앞에**
  > 놓여, "중복 경제효과 불가"가 **양성 `False`로 증명**되지 않는 한(`None` 포함 전부 차단) 어떤 retry도
  > 통과하지 못한다(budget 가드 `:615–616`도 선행). 따라서 `unknown_outcome=None`이 도달 가능한 유일한 경로는
  > **이미 duplicate 경제효과 불가가 증명된** 상태이고, 그 상태에서는 §14.4가 막으려는 위해(blind
  > resubmission에 의한 중복 경제효과)가 **구성적으로 성립하지 않는다**.
  > **유지 의무(회귀로 보호되어야 함)**: 이 방어는 (i) **게이트 순서**(duplicate 게이트가 unknown 분기에
  > 선행)와 (ii) **`is not False` 양성-증명 요구**(`None`을 permissive로 읽지 않음) 두 성질에 **전적으로
  > 의존**한다. 둘 중 하나라도 회귀하면 `unknown_outcome=None` 경로가 곧바로 fail-open이 되므로, 두 성질을
  > 고정하는 canary를 §7 하네스에 **유지**한다 — `duplicate_economic_effect_possible=None`(및 `True`)로 둔 채
  > `unknown_outcome`을 `True`/`False`/`None` 전 조합으로 훑어 `retry_admissible == False`임을 both-ways로
  > 고정(아래 canary 불릿의 확장). 이 유지 의무는 **처분의 일부**이며 임의 완화 대상이 아니다.
  > 비준 효력(2026-07-25, v1.1) 유지.
- **exhaustion ⇒ containment(§13 line 594)**: `protective_capacity_exhausted := any required domain UNAVAILABLE/
  unverifiable ∨ budget_remaining ≤ 0`(§13 line 578–579 "risk capacity, margin, broker quota or session, worker or
  queue, network path, trustworthy time, current Protective Lease, or reconciliation capability"). retry-budget
  exhaustion은 **그 자체가 containment trigger·Critical operational event**(line 594). **produces
  `protective_capacity_exhausted`** → authority `degraded_lease_invalidated`(`predicates.py:639`).
- preserve/potentially-live 산술은 **rcl 소관**(INV-005/012; §13.2 "preserve existing commitments and
  Potentially-Live Quantity" — protective는 주입 소비, 재저작 아님).
- **canary(both-ways)**: (a) budget_remaining=0 ⇒ retry False + exhausted True(containment 가드 발화);
  unknown_outcome=True ∧ dedup_proven=None ⇒ retry False; (b) budget>0 ∧ no-dup ∧ (not unknown ∨ dedup proven) ⇒
  retry True(양성 side). **[SAFE-014 bounded action rate; SAFE-021]** EV: PR-EV-007·FD-EV-010·AFG-EV-003
  substrate(EV-L2+, **닫지 않음**).

### 6.5 time-untrusted protective behavior (§10)

`time_untrusted_protective_admissible(action_kind: ProtectiveActionKind, *, time_trusted: bool|None,
nontime_dependent_emergency_rule: bool|None, cancellation_not_risk_increasing: bool|None) -> Admissibility`
(§10 line 455–463):

- `time_trusted == False/None` ⇒ time-dependent live/protective authorization **invalid**(§10 line 456–457);
  new protective order는 `nontime_dependent_emergency_rule == True`일 때만 허용(line 459); **cancellation of
  confirmed risk-increasing order는 `cancellation_not_risk_increasing == True`일 때 MAY 허용**(line 460); 그 외
  ⇒ PROHIBITED. `time_trusted == True` ⇒ 정상 경로(다른 술어로 위임).
- **unverified protective authorization은 permanently valid 아님**(§10 line 463) — 모델은 "time-untrusted 후
  authorization 영속" 연산 부재(구성적 부재; #6 no-grace 정신 동형).
- time freshness/holdover 산술은 **`tos.time` 소관** — protective는 `time_trusted` bool을 **주입** 소비(§0.4e;
  #6식 import-and-compose조차 불요 — protective는 time 좌표 계산이 없다).
- **canary(both-ways)**: (a) time_trusted=None + new protective order ⇒ PROHIBITED(가드 발화); (b)
  time_trusted=False + cancellation_not_risk_increasing=True ⇒ 취소 MAY 허용(양성 side, §10 line 460).
  **[SAFE-035 trustworthy time basis]**

### 6.6 protective action envelope subordination (§7)

`envelope_subordinate(protective: ProtectiveActionEnvelope, *, hard_envelope_bounds: HardEnvelopeRef) -> bool`:
protective envelope의 각 축(max qty/notional/gross-increase/margin/action-rate/duration)이 Hard Safety Envelope
대응 축 **이하**일 때만 True(§7 line 315 "The Protective Action Envelope SHALL remain subordinate to the Hard
Safety Envelope"). envelope 값은 **주입**(ADR-002-014 Safety Profile; CanonicalDecimal 비교, 하드코딩 없음). 축
누락/None ⇒ 보수(subordinate 증명 불가 ⇒ False). **canary**: protective max_qty > hard max_qty ⇒ False(가드
발화); 전 축 ≤ hard ⇒ True. **[SAFE-004 hard envelope; SAFE-050]**

### 6.7 dynamic reserve sufficiency + protective-lease reconciliation (§12.5/§5/§16; produces `protective_coverage_valid`/`protective_leases_reconciled`/`protective_coverage_added`)

`reserve_sufficiency(profile, *, forecast_capacity: dict[ProtectiveResourceDomain, CanonicalDecimal|None],
approved_minimum: dict[..., CanonicalDecimal|None]) -> bool`(§12.5 line 549–561):

- 각 required domain에서 `forecast_capacity[d] >= approved_minimum[d]`일 때만 sufficient. **forecast 또는 minimum
  None ⇒ 보수(insufficient)**. 미달 시 §12.5 ladder(`LIVE_RESTRICTED → DEGRADED_PROTECTIVE → CONTAINED → HALTED`,
  line 555–559)는 **authority mode 소관**(protective는 sufficiency bool만 생산, mode 전이 미소유 §3.5).
- **`protective_leases_reconciled(*, all_protective_leases_accounted: bool|None, reconciliation_evidence_current:
  bool|None, no_unresolved_protective_lease_conflicts: bool|None) -> bool`(MAJOR-1 반영 — 나머지 4 producer와
  동형 정의)**: **세 입력이 정확히 `True`일 때만 True(`:= all_protective_leases_accounted and reconciliation_
  evidence_current and no_unresolved_protective_lease_conflicts`), 임의 `None`/`False` ⇒ False(fail-closed)**.
  세 입력은 전부 **주입 verdict**(protective는 arithmetic 미소유 — §3.5): `all_protective_leases_accounted`
  (rcl `ProtectiveLease` 집계 — §5 line 238 "current protective capacity"·§16 line 675 "protective-capacity
  accounting is reconciled"; **rcl 소유**), `reconciliation_evidence_current`(recon(#9) reconciliation 신선도 —
  §12.3/§9 line 450 "enter reconciliation"; **recon 소유**), `no_unresolved_protective_lease_conflicts`
  (split-brain/overlapping lease 부재 — §12.3 Loss of Exclusivity; **authority `lease_scope_exclusive` verdict**).
  **ADR 근거(protective-side 판정 정당성 — MAJOR-1 선택지 (a))**: §5 line 229–241 "The Protective Action
  Controller SHALL verify: ... potentially live orders; ... current protective capacity" + "may consume only
  pre-committed capacity under a **valid Protective Lease**" — lease 유효성·capacity 정합 verify가 ADR 지정
  duty이고, §16 line 675가 "protective-capacity accounting is reconciled"를 degraded-exit 전제로 둔다. protective는
  그 **판정 roll-up**만 소유(arithmetic은 rcl/recon/authority 주입 — 소유권 불변). **canary(both-ways)**: (a)
  임의 입력 None/False ⇒ False(가드 발화; 미reconciled로 re-arm/coverage 차단); (b) 셋 다 True ⇒ True(양성
  side). **[SAFE-044 no automatic re-arm; SAFE-024 external-state reconciliation]**
- **produces**: `protective_coverage_valid := reserve_sufficiency(...)` → liveauth `continuous_validity`
  (`state.py:138`); `protective_leases_reconciled`(위 정의) → authority `state.py:129` + liveauth
  `predicates.py:135`; `protective_coverage_added` → liveauth `state.py:204`(§14.1 expansion; delta scope가
  envelope 확대 없이 sufficient일 때 True).
- threshold(approved_minimum)·forecast는 **주입**(Safety Profile/rcl; 하드코딩 없음 §8). **canary**: forecast<minimum
  ⇒ coverage_valid False(ladder 가드); forecast=None ⇒ False. **[SAFE-040 protective control in degraded;
  SAFE-015]**

### 6.8 multi-account minimum allocation (§12.6)

`account_minimum_preserved(allocations, *, per_account_minimum: dict[str, CanonicalDecimal|None], global_emergency
_pool: CanonicalDecimal|None) -> bool`(§12.6 line 565–574): 한 account의 소비가 다른 account의 minimum protected
allocation을 잠식하지 않고(line 571 "prevention of one account exhausting another account's minimum"), already-
trapped account와 still-protectable account를 분리 취급(line 573)할 때만 True. arithmetic(실제 vector 배분)은
**rcl 소관** — protective는 minimum-preservation **판정**만(survivability-based arbitration marker 주입). None ⇒
보수. **canary**: account A 소비가 account B minimum 침범 ⇒ False(가드 발화). **[SAFE-015 exclusive commitment]**

---

## 7. property-test 하네스 타깃

§1 분류에 정렬 — **core(PRD-EV-001/002 L1 슬라이스) / predicate-only(타-ADR EV substrate) / not-Phase-1(형제
소유)**, **닫는 PRD-EV = 0건**. property는 required-set·guarantee-level·aggregate-risk 비교값·mode/precedence
verdict·lease-validity·budget·time-trusted를 **hypothesis 생성 주입값**으로 다뤄 "임의 유효 주입 하 보수적
성립"을 검증(특정 값·mode enum·broker 값 비의존, 하드코딩 없음 — §8).

> **fixture clean-vs-illegal 정합 규율(#8 REJECT 교훈 선제 봉합)**: property fixture는 **내부 정합**이어야
> 한다 — (i) `PHYSICALLY_RESERVED`로 선언된 declaration은 실제 `failure_independence_evidenced=True` +
> `evidence_reference` 보유(빈 evidence로 PHYSICALLY_RESERVED는 illegal fixture); (ii) **undeclared** domain
> fixture는 declaration tuple에서 **진짜 부재**(≠ `guarantee_level=UNAVAILABLE`으로 명시 선언된 것 — 둘은 §4.2
> resolved에서 동일 UNAVAILABLE이나 fixture 의미가 다르므로 구분해 생성); (iii) `PROTECTIVE_PROVEN` fixture는
> 실제 final<current ∧ worst-intermediate≤no-action 비교값을 가짐(모순 비교값으로 PROVEN은 illegal). #8이
> "fixtures declared both clean and illegal"로 REJECT된 것을 방지.

| family | Phase-1 타깃 | substrate / 근거 |
|---|---|---|
| profile canonicalization + digest 검증 | **REUSE 설계 #4 must-pass suite**(`tos.canonical`) | §2.3·§3.1; frozen digest 일관성 |
| **domain_enumeration_complete** | **core (L1 슬라이스)** | §5.1; PRD-EV-001. 미열거⇒incomplete+UNAVAILABLE; 7군 전부⇒complete(both-ways). **닫지 않음**(+Broker//3) |
| **guarantee_level_resolved + is_reserved_guarantee** | **core (L1 슬라이스)** | §5.2; PRD-EV-002. 미할당⇒UNAVAILABLE; PRIORITIZED≠reserved; PHYSICALLY_RESERVED+no-evidence⇒강등(both-ways). **닫지 않음**(/3) |
| **protective_classification (final/intermediate)** | **predicate** | §5.3; FD-EV-001·ARE-EV-010·PR-EV-005. final≥current⇒DENIED; label override 불가; unbounded⇒UNKNOWN(both-ways) |
| **derestriction_admissible (§8.5)** | **predicate** | §6.1; SA-EV-*·FD-EV-*. reconnection-only⇒False; 네 조건⇒True(both-ways); not-a-re-arm |
| mode_permits_protective / contained_emergency_admissible | **predicate** | §6.1; SA-EV-*. reduce-only-by-construction 미성립⇒False |
| **partition_lease_admissible (§9)** | **predicate** | §6.2; RC-EV-012·SA-EV-004·PR-EV-001/002. cancel-first-outside-scope⇒TRAPPED; overlap-first-in-scope⇒ADMISSIBLE(both-ways) |
| **cancellation_admissible (§11)** | **predicate** | §6.3; PR-EV-011·X-EV-006. SAFETY_OWNED 세 disjunct 미성립⇒False; unconfirmed replacement⇒no credit(both-ways) |
| **retry_admissible + protective_capacity_exhausted (§13)** | **predicate** | §6.4; PR-EV-007·FD-EV-010·AFG-EV-003. budget=0⇒exhausted+containment; UNKNOWN+no-dedup⇒no retry(both-ways) |
| time_untrusted_protective_admissible (§10) | **predicate** | §6.5; SA-EV-011·TIME-EV-*. time_trusted None+new order⇒PROHIBITED; cancellation-not-risk⇒MAY(both-ways) |
| envelope_subordinate (§7) | **predicate** | §6.6; SPG-EV-001. protective>hard⇒False; 전 축≤hard⇒True(both-ways) |
| reserve_sufficiency + account_minimum_preserved (§12.5/12.6) | **predicate** | §6.7/§6.8; produces coverage bool. forecast<minimum⇒False; account 침범⇒False(both-ways) |
| representation ≠ enforcement | **구성적 부재** | §4.5. egress-transmit·capacity-mutate·authorization-issue·mode-set·capacity-release 메서드 **부재** |
| append-only + same-id/diff-bytes | **REUSE core `classify_record_pair`** | §4.6; CRITICAL_CONFLICT reachable(id⊥digest) — 재발행 위조 탐지 |
| 좌표 비붕괴 (5-axis) | **타입 identity 회귀(test-only)** | §4.4. `Admissibility.TRAPPED is not rcl.CapacityState.TRAPPED_CONSUMED`; DEGRADED_PROTECTIVE ∉ protective 어휘 |
| **seam cross-check (MANDATED, test-only)** | **cross-import 정합 회귀(test-only, NOT package edge)** | §3.4. protective 산출 bool(`protective_classification_present`/`protective_capacity_exhausted`/`protective_coverage_valid`/`protective_coverage_added`/`protective_leases_reconciled`)의 polarity·fail-closed가 authority(`predicates.py:513/639`·`state.py:129`)·liveauth(`state.py:138/204`·`predicates.py:135`) 기대와 일치; §7.1 closure 무영향 |

- **core(L1 슬라이스)** = {domain_enumeration_complete[PRD-EV-001], guarantee_level_resolved[PRD-EV-002]}
  (2건; §1 요약과 동일). **predicate-only** = {classification, de-restriction/mode/emergency, partition-lease,
  cancellation, retry/exhaustion, time-untrusted, envelope, sufficiency/allocation}. **닫는 PRD-EV = 0건**
  (§1 규율). required-set·guarantee-level·비교값·mode/precedence verdict·budget·time-trusted는 hypothesis 주입.
- **self-consistency 규율(C1 lesson)**: 위 어떤 family도 "PRD-EV closure"·"EV-L1-complete"를 주장하지 **않는다**
  — core 2건조차 `/3`·`+Broker` 잔여로 닫지 않고, predicate-only는 전부 타-ADR EV(EV-L2+) substrate이며 §1
  "닫는 PRD-EV 0건"·§4/§5/§6 술어 정의와 정합한다(finishing 전 대조 — §10.1).

### 7.1 import-closure 검증 테스트 (설계 #4 §7.1·#5·#6·#7·#8·#9·#10 §7.1 상속)

서브프로세스에서 `import tos.protective`(및 `tos.canonical`·`tos.ordering`)만 한 뒤 `sys.modules`를 검사해
assert: (1) 설계 #1 §2.3 금지 패키지 부재; (2) **`shared.config`·`shared.config.secrets` 부재**(전이 유입
런타임 포착); (3) `os.environ`/`os.getenv` 미참조; (4) **`numpy`·`pandas`·`yaml`(pyyaml) 부재**(bound/threshold/
flag 주입·YAML은 하네스 소관, §0.3); (5) **`tos.rcl`·`tos.authority`·`tos.orthostate`·`tos.liveauth`·
`tos.recon`·`tos.evidence`·`tos.capsule`·`tos.time`·`tos.dsl`·`tos.brokercap` 부재**(§3.4/§3.5 — 형제/상하류;
produced-bool·scalar·주입 좌표로만 참조); (6) **`tos.canonical`·`tos.ordering` 존재 허용**(§3.1/§3.2 — core,
sibling edge 아님). required check(`tos-firewall`, `tools/tos_firewall_check.py` layer-① AST + `.importlinter`
layer-② 전이 방어)와 함께 green이어야 §0.3 준수 선언이 능동 성립한다.

### 7.2 run manifest 정렬 (설계 #1 §5.1 7항목)

protective 전용 템플릿은 없으므로 설계 #1 §5.1 규율을 REUSE한다. evidence를 산출하는 모든 property-test run은:
(1) git commit digest + `tos` 버전; (2) 인터프리터 + 고정 의존성 버전(pydantic/hypothesis); (3) 실행 환경;
(4) 하네스 git digest; (5) **property-test seed**(hypothesis seed/derandomize, append-only); (6) **소비 설정
아티팩트 digest**(주입 required-domain-set/guarantee-level/aggregate-risk-comparison/reserve-minimum/envelope/
budget 프로파일 + `canonicalization_version` + `tos.ordering` primitive 버전 + `CanonicalDecimal` 포함
`tos.canonical` 버전); (7) 산출 아티팩트 sha256. (VER-002-001 §2.3 재현성·§9.1 seed·§9.2 digest의 EV-L1
부분집합.)

---

## 8. bounds 주입 + 누락 프로파일 키 Phase-0

`VERIFICATION-PROFILE-002.yaml`은 전체 `status: PROPOSED` 계열(배너 line 3–5 "an unapproved or placeholder
bound is not an approved bound"; line 14 "Values below marked MEASURE are deliberately left null pending
broker-specific measurement"). ADR §12.5 line 563 "Exact thresholds belong in the Safety Profile and
Verification Specification"·§7(envelope 값 Safety Profile)·§4.6(broker별 domain)은 수치를 **본 ADR에서 배제**하고
Safety Profile/Broker Capability Profile INSTANCE로 위임한다.

- **결정**: ADR-002-001 관련 수치(reserved-protective minimum·per-guarantee-level reserve·dynamic reserve
  sufficiency threshold·retry budget·envelope max·holdover·protection-gap/overlap window·operator escalation)는
  **주입 policy 파라미터**로만 들어온다. **어떤 숫자도·어떤 broker 값도 하드코딩하지 않는다**(CLAUDE.md·
  broker-agnostic). 값 누락 ⇒ fail-closed(§4.1 미열거⇒UNAVAILABLE; §5.2 미할당⇒UNAVAILABLE; §6.7 forecast/minimum
  None⇒insufficient; §6.2 staleness None⇒TRAPPED).

- **실측 확인(evidence-based) — 프로파일에 존재하는 protective/degraded/partition 관련 키**(**MAJOR-2 규율:
  `measurement_source` 전수 확인 + 완전 열거**; 키 명·line은 YAML 직접 인용):
  - **`B_protective_request_start`[583–589]**: `value_ms: 1000` / PROPOSED, `measurement_source:
    protective_controller_log`, `failure_response: CONTAIN`, rationale "degraded-mode entry to first bounded
    protective request ... using reserved protective capacity (ADR-002-001)". ⇒ **ADR-002-001 명시 태깅**. 그러나
    `measurement_source`가 **런타임 로그**(protective_controller_log)라 **EV-L1 미측정**(전송·타이밍 = EV-L3).
    Phase 1은 이 bound를 주입 param으로만.
  - **`B_protective_request_complete`[590–596]**: `value_ms: null`(MEASURE) / `broker_specific`,
    `measurement_source: broker_capability_profile`, rationale "informs protection-gap bounding (ADR-002-001
    §12)". ⇒ **broker-INSTANCE 측정값**(+Broker), 이연.
  - **`B_rate_limit_recovery`[604–610]**: `value_ms: null`(MEASURE) / `broker_specific`,
    `measurement_source: broker_capability_profile`, rationale "protective/reconciliation traffic budget must
    survive this (**ADR-002-001 §7.5**)". ⇒ **broker-INSTANCE**, §6.4 retry budget·§6.7 sufficiency 관여, 이연.
    **[§8 에라타 관찰]**: rationale의 "ADR-002-001 §7.5"는 **실존하지 않는 조항** — ADR §7(Protective Action
    Envelope)은 무-하위절이다(§7.1–§7.5 부재). 관련 rate/budget 내용은 §4.2 broker capacity·§12/§13에 있다.
    비-normative 관찰이며 본 문서는 스펙·프로파일을 수정하지 않는다.
  - **`B_protection_gap`[625–631]** / **`B_protection_overlap`[632–638]**: `null`(APPROVE) / `broker_specific`,
    `measurement_source: protective_replacement_and_broker_log`, `failure_response: CONTAIN`, rationale
    "(ADR-002-011)". ⇒ **ADR-002-011(PR) 소관**(§11.4·§9 overlap; protective는 partition-lease-admissibility
    판정만, gap 지속시간 미소유 §3.5), broker-INSTANCE 이연.
  - **`B_protective_replacement_contain`[639–645]**: `null` / hard_maximum, `measurement_source:
    protective_controller_ledger_and_egress_log`, `failure_response: HALT_OR_CONTAIN`, "(ADR-002-011)". ⇒
    ADR-002-011 런타임(egress), 이연.
  - **`MAX_degraded_lease_holdover_ms`[699]**: `5000` / PROPOSED, "max monotonic lifetime of a pre-issued
    degraded protective lease". ⇒ §9 lease·§6.2 partition-lease-admissibility 관여. 그러나 lease lifetime
    산술·monotonic 판정은 **authority `degraded_lease_valid`(time compose) 소관**(#6 §6.3); protective는 pre-proven-
    scope/staleness verdict만(주입). 기존 키·재계상 없음.
  - **`MAX_process_suspension_ms`[701]**: `2000` / PROPOSED, "process suspended longer ... fenced on resume".
    ⇒ §9 line 442 "no process restart that invalidates the lease" 관여이나 **authority/time fence 소관**(주입).
  - **`B_authority_partition_detect`[121–126]**: `2000` / hard_maximum, `measurement_source:
    harness_clock_on_execution_path`, `failure_response: CONTAIN`, "(ADR-002-003)". ⇒ **authority 소관**(§9
    partition detection); `measurement_source`가 harness_clock이라 EV-L1 미측정(런타임 타이밍).
  - **`B_operator_escalation`[667–673]**: `30000` / hard_maximum, `measurement_source: alerting_pipeline_log`,
    `failure_response: HALT`, "capacity exhaustion, trapped exposure, unresolved UNKNOWN". ⇒ §13 line 596·§15
    escalation 관여이나 **런타임 alerting**(EV-L3), 주입 param.
  - **`B_final_quantity_proof`[569–575]** / **`B_late_fill_observation`[576–582]**: `null` / `broker_specific`,
    `broker_capability_profile`, "(ADR-002-002 §16/§16.4)". ⇒ §14.2 FQP·late-fill = **rcl/broker 소관**(§3.5).
  - **`B_external_activity_detect`[184–190]** / **`_contain`[191–197]** / **`B_stale_epoch_reject`[177–183]**:
    §14 external activity·fence = rcl/authority 소관, protective 미소유.

- **누락 distinct 키 (Phase-0 Bounds-Approver 플래그)**: 실측 대조 결과 —
  1. **구조 조항(domain enumeration·guarantee-level·classification·Admissibility·ProtectiveOwnership·전이 가드)에는
     numeric bound 부재** — 전부 enum·boolean·집합 논리·주입 Decimal 비교라 승인할 숫자가 없다.
  2. **ADR-002-001이 도입하는 수치 의존**(reserved-protective minimum[§4.4/§12.1]·per-guarantee-level reserve
     [§4.6]·dynamic reserve sufficiency threshold[§12.5]·retry budget[§13]·envelope max[§7])은 전부
     **Safety Profile/Broker Capability Profile INSTANCE 측정값**이다(ADR §12.5 line 563·§7·§4.6 명시 위임).
     **Reserved Protective Capacity 최소치 전용 키 부재**는 **#5 §8이 이미 Phase-0로 플래그**(rcl 설계 "grep
     `protective_reserve|reserve_min|min_protective` 0건")했다 — **재계상·이중 카운트 없음**(설계 #4/#5/#6/#7/#8/
     #9/#10 §8 규율 동형). 본 문서가 **추가로** 표면화하는 candidate: (a) **per-guarantee-level reserve minimum**
     (§4.6 domain별·guarantee-level별 최소치 — 단일 `protective_reserve_min`이 아니라 domain×level matrix);
     (b) **dynamic reserve sufficiency threshold**(§12.5 forecast 대비 minimum); (c) **protective retry budget
     size**(§13 "explicitly reserved retry budget" 전용 키 부재). 셋 다 Safety-Profile-owned·주입 opaque param.
  3. **기존 protective-관련 Verification-Profile 키**(위 완전 열거: `B_protective_request_start/complete`·
     `B_rate_limit_recovery`·`B_protection_gap/overlap`·`B_protective_replacement_contain`·
     `MAX_degraded_lease_holdover_ms`·`MAX_process_suspension_ms`·`B_authority_partition_detect`·
     `B_operator_escalation`·`B_final_quantity_proof`·`B_late_fill_observation`)는 **전부 이미 존재·기계상**
     이며 #5–#10이 계상했거나 rcl/authority/PR/broker 소관이다 — **재계상 없음**.

  ⇒ **확정 신규 누락 distinct 키 = Phase-0 candidate 1군**(per-guarantee-level reserve minimum matrix ·
  dynamic reserve sufficiency threshold · protective retry budget — 전부 Safety Profile INSTANCE, ADR §12.5/§7/§13
  위임). Phase 1은 전부 **주입 opaque param**(§6.4/§6.7)으로 담는다. 값·키 승인은 **Bounds-Approver 게이트**
  (Live-Armer와 분리 — IMPLEMENTATION-PLAN §3) 소관이다. **이 구분은 safety-neutral**: 값 부재/`None` ⇒
  restrictive(§4.1/§4.2/§6.2/§6.7)라 미승인 bound가 자동으로 permissive해지지 않는다. **Reserved-Protective-minimum
  기본 키는 #5가 이미 플래그** — 이중 계상 회피. [SAFE-003/015/040 conservative 정합; broker-agnostic]

---

## 9. 후속 작업 · Phase-0 인간 게이트 이관 항목

### 9.1 후속 구현 작업 (본 계약 위에서)

- **`tos/src/tos/protective/` 모델·술어·property·import-closure 테스트 저작**(§2–§7): 설계 #3(EV-L1 하네스)이
  property suite를 실행. `tos.canonical`(digest+id+classify+CanonicalDecimal) + `tos.ordering`(순서) REUSE,
  **신규 canonicalizer/ordering 없음, PROMOTE 0건, sibling edge 0건**(rcl/authority/orthostate/liveauth/recon/
  evidence/capsule/time/dsl/brokercap 미import).
- **의존 방향**: protective ⟸ `tos.canonical`·`tos.ordering`(둘 다 core). acyclic 확인: canonical·ordering은
  protective 미참조.
- **compose seam(§3.4): 런타임 배선 이연 + test-only cross-check MANDATED**: protective 산출 bool
  (`protective_classification_present`·`protective_capacity_exhausted`·`protective_leases_reconciled`·
  `protective_coverage_valid`·`protective_coverage_added`)을 authority 주입 슬롯(`predicates.py:513/639`·
  `state.py:129`)·liveauth 주입 슬롯(`state.py:138/204`·`predicates.py:135`)으로 배선하는 **런타임**은 **미래
  Protective Action Controller/Live-Authorization/Reconciliation Service**(EV-L3) 소관. 단 Phase 1은 **test-only
  cross-import 모듈**(protective·각 소비자 둘 다 import; polarity·fail-closed 정합 assert)을 **작성한다**(§3.4/§7).
  **이 test는 package edge가 아니다**(테스트 import는 §7.1 closure 무영향; protective 런타임 sibling-edge-0건
  유지).
- **consume seam(§3.5): 주입 verdict**: protective 술어(§6.1 de-restriction·§6.2 partition-lease·§6.3
  cancellation·§6.4 retry·§6.7 sufficiency)가 소비하는 authority mode/precedence verdict·rcl partition/trapped
  verdict·orthostate order-state는 **주입 `bool|None`/scalar**로 받는다(import 없음). test-only 모듈이 rcl/
  authority verdict를 fixture로 주입해 protective 술어의 fail-closed를 검증.

### 9.2 Phase-0 인간 게이트로 넘기는 항목 (본 계약이 결정하지 않음)

1. **seam decoupled 유지(§0.4b/§3.4)**: protective↔{authority,liveauth} seam을 plain-bool decoupled로 둘지
   대안 B(소비자 측 edge)로 갈지; consume 방향(§3.5)을 주입-verdict(권장)로 둘지 import-and-compose(authority
   `AuthorityState`/`PRECEDENCE_RANK`·rcl `CapacityState` — 선례 #6/orthostate)로 갈지. **decoupled/주입 권장**
   (edge·cycle 회피, #9/#10 정합).
2. **프로덕션 canonical serialization·digest 알고리즘 선택**(설계 #4 §9.2 item 1과 동일 게이트):
   `ev-l1-provisional-0`·sha256은 비프로덕션.
3. **Safety Profile INSTANCE bound family 값·키 승인**(§8; ADR §12.5/§7/§13): **per-guarantee-level reserve
   minimum matrix(domain×level)** · **dynamic reserve sufficiency threshold** · **protective retry budget size**
   (전부 신규 candidate) + envelope max qty/notional/margin/rate/duration(§7). Bounds-Approver ≠ Live-Armer.
   **Reserved-Protective-minimum 기본 키는 #5 §9.2 item 1이 이미 플래그**(이중 계상 회피). broker-specific
   `B_protection_gap/overlap`·`B_protective_request_complete`·`B_rate_limit_recovery`는 broker-INSTANCE 이연.
4. **broker별 protective resource domain 열거(PRD-EV-001 `+Broker`)**(ADR §4.6 "at least"·Broker Capability
   Profile INSTANCE): 특정 broker/venue의 추가 protective domain·guarantee-level 실측·분류는 **non-normative
   Broker Capability Profile INSTANCE + Safety Profile INSTANCE**(구현 트랙) 소관 — protective는 domain-CLASS
   열거·완전성 술어만. §12.4 common-mode(single serialized session/global rate limit ⇒ PRIORITIZED_ONLY/
   BEST_EFFORT)의 특정 broker 포함 여부도 INSTANCE 판정(broker-agnostic).
5. **Protective Action Controller 런타임 enforcement**(ADR §5·§11·§13): authorize·transmit·egress reject·retry·
   containment·capacity mutate·evidence capture는 런타임(EV-L3) — Phase 1은 결정 bool/Admissibility만(§0.2/§4.5).
6. **aggregate-risk 수치 소스(ARE, ADR-002-021)**: §6.1/§6.2 classification이 소비하는 conservative aggregate-risk
   비교값은 ARE(미구현 tos 패키지) 소관 — protective는 비교 술어만. ARE 구현 시 produced-value seam 정합 필요.
7. **replacement-gap·protection-gap semantics(ADR-002-011)**: §11.4 non-atomic replacement·gap 지속시간·
   atomic-replace 판정은 PR-EV 소관 — protective는 §9 partition-lease-admissibility(overlap-first/cancel-first)만.
8. **+Security 런타임(egress bypass·물리 격리)** + **evidence persistence·replay engine(ADR-002-016)**: protective
   결정 재구성 substrate(frozen digest-bound 레코드)만 담고 replay ENGINE·bypass 저항은 이연.
9. **required-protective-domain-set / per-mode 허용 매핑 정의**(§4.6 "at least"·§8.1–8.4): 어떤 배치·mode가
   어떤 domain·protective-action-class를 요구/허용하는지의 승인된 매핑은 Safety Profile/scope별 주입 — Phase 1은
   하드코딩하지 않고 hypothesis 주입으로 property 검증(§5.1/§6.1).
10. **§8.3.1 pre-approved bounded emergency-action set + §6.2 resolution horizon + §8.5 classifier-trust 재확립
    기준**: CONTAINED emergency-action set·envelope 값·resolution horizon·de-restriction 거버넌스 기준은 Safety
    Profile/Safety Authority 소관(주입) — protective는 술어 구조만.
11. **VER-002-001 §21 acceptance-criteria 실행 evidence + 독립 리뷰**(저자 배제 — IMPLEMENTATION-PLAN §3).
    **닫는 PRD-EV 0건이므로 acceptance 서명 없음** — PRD-EV-001의 `+Broker`·PRD-EV-002의 `/3` + 타-ADR EV
    family(RC/SA/PR/ARE/FD/…, 전부 EV-L2+) fault injection·adversarial·chaos·broker-profile·security evidence는
    Phase B.
12. **cross-package 좌표 조정 의무(coordination)**: `GuaranteeLevel`(protective)과 rcl `CapacityState`·authority
    `AuthorityState`·orthostate `KnowledgeState`·recon `FieldConfidenceClass`를 **동시에 담는 FUTURE 패키지**는
    이들을 반드시 별개 typed 필드로 유지(공유 raw-string slot 금지 — 축 붕괴 재발 방지). 본 계약은 다섯 축을
    import하지 않아 자체로는 안전하나, 좌표 근접(`TRAPPED`↔`TRAPPED_CONSUMED`)의 출처이므로 명시(#9 [m3]·#10 동형).

---

## 10. 개정 로그 + 비준 체크리스트

### 10.1 개정 로그

- 2026-07-25: **v1.0 초안 최초 작성.** ADR-002-001 EV-L1 실현 계약. 설계 #1(경계·firewall)·#2(주입 flag·좌표
  어휘)·#4(canonical substrate + id⊥digest)·#5(**rcl capacity 소유권 인접 — §12/§14/§15 rcl 소유 실측**)·
  #6(**authority mode/precedence 소유권 인접 + produced-bool seam `protective_classification_present`/
  `protective_capacity_exhausted`/`protective_leases_reconciled` 실측**)·#7(**liveauth `protective_coverage_valid`/
  `protective_coverage_added` producer seam 실측**)·#8(orthostate order-state 축)·#9/#10(produced-bool 선례·
  bounds under-report 규율·좌표 비붕괴)에 정렬. 주요 결정: (§0.4a) 전용 패키지 `tos/src/tos/protective/`
  (`tos.degraded`[mode 국한·authority 충돌]·`tos.prd`[cryptic]·`tos.protcap`/`tos.protection` 기각 — ADR §3
  "Reserved Protective Capacity"·register domain "Protective Resource Domain" 앵커; naming 비-load-bearing);
  (§0.4b/§3.4) **protective = plain-bool producer, sibling edge 0건** — authority `degraded_lease_valid`
  (`predicates.py:513`)·`degraded_lease_invalidated`(`predicates.py:639`)·`state.py:129`·liveauth `state.py:138/204`·
  `predicates.py:135`의 상류 producer(두 소비자 전부 이미 주입 `bool|None` 슬롯으로 봉인); 대안 A(소비자 import·
  backwards edge)·B(소비자 측 edge 신설) 기각; consume 방향도 주입-verdict(§3.5); (§0.4c/§3.1) **PROMOTE 0건**·
  **sibling edge 0건**(CanonicalDecimal·IndependentId·classify·Ordering 전부 이미 core); (§0.4d/§3.1) canonical
  REUSE + `id=f(digest)` 미채택; (§0.4e/§3.5) rcl(capacity 산술)·authority(mode/precedence/exclusivity)·liveauth
  (re-arm)·orthostate(order-state)·evidence/capsule/time/dsl/recon/brokercap **미import**; (§0.4f) **새 INV
  시리즈 창작 금지**(ADR-002-001 자체 PRD-INV/PRD-AC 부재 실측 — #9 동형; PRD-EV/§21 불릿/§-clause/SAFE 앵커);
  (§0.4g/§1) **PRD-EV core tier 존재 shape**(2행 모두 최소 레벨 EV-L1 슬라이스 보유 — #8/RCL형·#10 "0건 완결"과
  다름) but **닫는 PRD-EV 0건**(authoring≠evidence, `/3`·`+Broker` 잔여); (§2) `ProtectiveCapacityProfile` =
  IndependentId + 독립 id·append-only version; (§2.2) 어휘(GuaranteeLevel 5·ProtectiveOwnership 4·domain 7군·
  Admissibility 3·outcome 3) **verbatim 전사** + ADR line 병기; (§3.5) **소유권 분할표**(중복 저작·권위 중복
  구조적 배제 — capacity=rcl·mode/precedence=authority·re-arm=liveauth·order-state=orthostate·risk-수치=ARE·
  envelope-값=SPG; protective는 domain-enum/guarantee-level/classification/de-restriction/lease-admissibility/
  cancellation/retry 7축만); (§4.1/§4.2) **domain-enumeration·guarantee-level completeness 중앙 불변식**
  (미열거⇒UNAVAILABLE·미할당⇒최저·PRIORITIZED≠reserved — fail-open 구조적 봉합); (§4.3) classification purity;
  (§4.4) 5-axis 좌표 비붕괴; (§4.5) representation≠enforcement; (§5) domain/guarantee/classification core 술어;
  (§6) de-restriction(§8.5 v0.7 U1)·partition-lease-admissibility(§9 ADR-owns)·cancellation-arbiter(§11)·
  retry/exhaustion(§13)·time-untrusted(§10)·envelope(§7)·sufficiency(§12.5); (§8) **확정 신규 누락 키 = Phase-0
  candidate 1군**(per-guarantee-level reserve minimum·dynamic sufficiency threshold·retry budget; reserved-
  minimum 기본은 #5 이미 플래그 — 이중 계상 회피). **선제 fail-open/defect 봉합**: 중앙 completeness 불변식을
  구조로(#6 REJECT)·core-tier 판정 정확(§1 #8/RCL형)·fixture clean-vs-illegal 정합 규율(#8 REJECT)·cross-section
  self-consistency pass(§1↔§5/§6↔§7 대조 완료 — C1 lesson)·enum verbatim 전사(에라타 defect class)·**실측-원천
  결함 방지**(rcl `TransitionCause`[not CapacityTransitionCause]·rcl INV 귀속 정정[ADR-002-002+012]·rcl
  `exclusiv*` 부재→authority 소재·RELEASED cause=FINAL_QUANTITY_PROOF — 전부 코드 실측 인용)·에라타 관찰
  (프로파일 "ADR-002-001 §7.5" 부재)·broker-agnostic(규범 텍스트 broker 무명). 이후 독립 비평 리뷰.
- 2026-07-25: **v1.1 — 독립 비평 리뷰 REVISE 반영(forward-only; CRITICAL 0·MAJOR 1·MINOR 1·NIT 1).** 리뷰는
  60여 인용 전수 검증 통과("시리즈 최고 인용 정확도")·§8 키 15종 완전(#10 MAJOR-2 미재발)·4개 실측-정정 코드
  정확·seam 5슬롯 실재·TRAPPED 좌표 분리 clean·de-restriction 4조건 1:1 정합·umbrella §21 19불릿 전수 매핑
  정합을 확인했고, 아키텍처 핵심 결정은 **전부 불변**. 2건 반영:
  - **[MAJOR-1]** `protective_leases_reconciled`가 5개 produced-bool 中 **유일하게 정의 술어 부재**(#7
    under-realization class — 나머지 4개[classification §5.3·exhausted §6.4·coverage_valid §6.7 `:=`·coverage_
    added §6.7]와 달리 입력·`:=`·fail-closed 규칙 전무, output 화살표만). **선택지 (a) 정의 술어 추가**: §6.7에
    나머지 4개와 **동형**의 conjunctive fail-closed 술어 `protective_leases_reconciled(all_protective_leases_
    accounted, reconciliation_evidence_current, no_unresolved_protective_lease_conflicts)` 저작 — 세 입력 전부
    `True`일 때만 True, 임의 None/False ⇒ False; 세 입력은 전부 **주입 verdict**(rcl lease 집계·recon 신선도·
    authority exclusivity — arithmetic 미소유, §3.5 소유권 불변). **ADR 근거**: §5 line 229–241이 Protective
    Action Controller에 "potentially live orders·current protective capacity" **verify** duty + "valid
    Protective Lease 하에서만 소비"를 명시하고, §16 line 675가 "protective-capacity accounting is reconciled"를
    degraded-exit 전제로 두므로 — protective-side **판정 roll-up**은 ADR 지정 duty다. **선택지 (b) producer
    주장 제거·재분류 기각**: ADR §5/§16이 이 verify를 Protective Action Controller에 **명시 부여**하므로 producer
    주장 제거는 ADR-지정 duty의 under-attribution이고, 소비 슬롯(authority `state.py:129`·liveauth
    `predicates.py:135`)이 protective-coverage-family bool을 기대하므로 recon/rcl 재분류는 seam 소비자 기대와
    어긋난다. 변경 위치: §0.1 item 10(정의 참조)·§1 §16행·§3.4 표(정의 §6.7 참조)·§6.7(정의 추가 + heading)·
    §7 하네스 표(§6.7 정의)·§10.2 seam 항목(5개 전부 정의 보유 명시).
  - **[MINOR-1]** §1 결정적 사실 1의 §21 불릿 수 정정: "11개 + 추가 10개" → **"10개(line 983–992) + 추가
    9개(line 996–1004) = 총 19"**(실측); criterion #11 = 첫 그룹 10개 + 둘째 그룹 첫 불릿(line 996 guarantee-
    level) 명시로 #1→PRD-EV-001·#11→PRD-EV-002 앵커 자기모순 제거(앵커 자체는 v1.0에서 이미 정확).
  - **[NIT]** 프로파일 키 라인 범위 1~2줄 하향 — 리뷰어 "키 라인 자체 정확, 정정 불요" 판정, **미조치**.
  아키텍처 핵심(패키지 `tos.protective`·§3.5 소유권 분할·produced-bool seam·sibling edge 0·PROMOTE 0·PRD-EV
  core-tier shape·PRD-EV/§21/§-clause/SAFE 앵커·중앙 completeness 불변식·verbatim 전사·4개 실측-정정)은
  **v1.0 그대로**. 운영자 비준 대기.
- 2026-07-26: **v1.2 — 설계-트랙 판단 지점 2건 처분 부기(코드 무변경·의미 변경 아님, 비준 효력 유지).**
  구현 커밋 `02de5c54`(Phase 1 EV-L1 protective 모델 + property test)에 대한 **독립 적대적 코드 리뷰**가
  **"코드 결함 아님"**으로 판정하되 계약 소관이라며 **설계 트랙으로 회부**한 2건을 처분·기록한다. 어느 것도
  코드를 바꾸지 않으며 규범 텍스트·EV 귀속(**닫는 PRD-EV 0건**)·아키텍처 핵심(§3.5 소유권 분할·produced-bool
  seam·sibling edge 0·PROMOTE 0)은 **전부 불변**:
  - **[D1] `mode_permits_protective` per-mode 표현력 ⇒ 현행 비준 signature 유지(의도적 이연).** 실측:
    `tos/src/tos/protective/predicates.py:398–426`이 `mode_rank`를 **`None` 여부로만** 판정
    (`:422–423`)하고 `envelope_ok is not True ⇒ False`(`:424–425`) + `action is PROTECTIVE_PROVEN`(`:426`)
    으로 닫으므로, §8.1–8.4의 **mode별 허용 차등**을 rank 위에서 구분하지 못한다. 처분 근거: 비준 signature
    `(mode_rank: int|None, action, envelope_ok)`에 mode별 순위·임계가 **없으므로** per-mode 구분을 여기서
    강제하려면 **하드코딩**이 필요하고, 이는 §0.4e authority-duplication 배제·§3.5(“`PRECEDENCE_RANK`의
    per-mode ordering·threshold는 authority 소유”)·§6.1 "mode enum 재선언 없음"을 위반한다 ⇒ **per-mode
    강제는 authority 하류 소관**. 향후 실제 필요가 발생하면 **별도 설계 개정**으로 mode별 허용-집합 **주입
    verdict**를 추가(하드코딩 아닌 seam 확장); **현 Phase-1 스코프 아님**. 기록 위치: §6.1.
  - **[D2] `retry_admissible`의 `unknown_outcome=None` 미차단 ⇒ 현행 유지(선행 방어 성립) + 회귀 보호 유지
    의무.** 실측: `predicates.py:588–620`에서 **duplicate-effect 게이트가 선행**한다 —
    `duplicate_economic_effect_possible is not False ⇒ False`(`:617–618`, `None`도 차단)가 unknown 분기
    (`:620`)보다 앞이고 budget 가드(`:615–616`)가 그보다 앞이다. 따라서 `unknown_outcome=None`이 도달 가능한
    유일한 상태는 **중복 경제효과 불가가 이미 양성 증명된** 상태이며, §14.4 line 639가 막는 위해가
    **구성적으로 성립하지 않는다**(리뷰 확인). **유지 의무**: 이 방어는 (i) 게이트 **순서**와 (ii)
    `is not False` **양성-증명 요구**에 의존하므로 두 성질을 고정하는 canary를 §7 하네스에 유지한다
    (`duplicate_economic_effect_possible=None`/`True` × `unknown_outcome` 전 조합 ⇒ `False`). 기록 위치: §6.4.
  비준 효력(2026-07-25, v1.1)·§10.2 판단 지점 승인 불변.

### 10.2 비준 체크리스트 (운영자 · 독립 리뷰어 확인 사항)

- [ ] §0.2 NO 목록(ADR/acceptance 미승인·capacity 산술[rcl] 미저작·mode enum[authority] 미재저작·Protective
      Action Controller 런타임 미구현·aggregate-risk 수치[ARE] 미산출·replacement-gap[PR] 미결정·Safety Profile
      값 미승인·evidence replay·+Security 미구현·**닫는 PRD-EV 0건**)과 §0.3 firewall 준수(numpy/pandas/pyyaml·
      shared.config·**rcl/authority/orthostate/liveauth/recon/evidence/capsule/time/dsl/brokercap 배제,
      canonical·ordering만 허용**; `.importlinter` forbidden 계약이 신규 패키지 자동 포섭)에 동의.
- [ ] §0.4a 전용 패키지 `tos/src/tos/protective/`(`tos.degraded`·`tos.prd`·`tos.protcap`·`tos.protection` 기각;
      naming 비-load-bearing; rcl/authority protective 토큰과 **DECISION-layer 경계** 명시)에 동의.
- [ ] **§0.4b/§3.4 protective = produced-value producer, sibling edge 0건**(authority `degraded_lease_valid`
      [`predicates.py:513` `protective_classification_present`]·`degraded_lease_invalidated`[`predicates.py:639`
      `protective_capacity_exhausted`]·`state.py:129`[`protective_leases_reconciled`]·liveauth `state.py:138`
      [`protective_coverage_valid`]·`state.py:204`[`protective_coverage_added`]의 상류 producer(**5개 전부 §5/§6
      정의 술어 보유 — MAJOR-1 반영으로 `protective_leases_reconciled`도 §6.7 conjunctive fail-closed 정의**);
      전부 진짜 `bool|None` 슬롯[#10 enum-basis 예외 없음]; composition=caller 소관; 대안 A/B 기각·cycle 회피; **test-only
      cross-check MANDATED**)에 동의. **[운영자 판단 지점: produced-value decoupled(권장) vs 대안 B 소비자 측
      edge; consume 방향 주입-verdict(권장) vs import-and-compose authority/rcl]**
- [ ] **§0.4c/§3.1 PROMOTE 0건·sibling edge 0건**(CanonicalDecimal·IndependentId·classify_record_pair·Ordering
      전부 이미 core — #9/#6이 PROMOTE 완료했기에 본 문서 PROMOTE 부담 없음)에 동의.
- [ ] §0.4d/§3.1 canonical REUSE + `id=f(digest)` 미채택(거버넌스-할당 profile identity + same-id/diff-bytes·
      재발행 위조 탐지 `classify_record_pair`)에 동의.
- [ ] **§0.4e/§3.5 소유권 분할표**(capacity 산술=rcl[`CapacityState`·`ProtectivePool`/`Lease`·`partition_verdict`·
      INV-005/006/007/009/011/012·sub-ledger] · mode enum/precedence/exclusivity=authority[`AuthorityState`·
      `PRECEDENCE_RANK` `vocabulary.py:54`·`lease_scope_exclusive`] · re-arm=liveauth · order-state=orthostate ·
      risk-수치=ARE · envelope-값=SPG; protective는 **domain-enum/guarantee-level/classification/de-restriction/
      lease-admissibility/cancellation/retry 7축만** — 중복 저작·권위 중복 구조적 배제)에 동의. **실측-원천 결함
      방지 정정**(rcl cause enum=`TransitionCause`·rcl INV=ADR-002-002+012·rcl `exclusiv*` 부재→authority·
      RELEASED cause=FINAL_QUANTITY_PROOF — 전부 코드 실측)에 동의.
- [ ] **§0.4f 새 INV 시리즈 창작 금지**(ADR-002-001 자체 PRD-INV/PRD-AC 부재 실측 — §21 불릿·잔존 "INV-###"은
      타 ADR 교차참조[§8.5 line 393 SIR-INV-015 등]; PRD-EV-001/002·§21 acceptance-criteria·§-clause·SAFE-### 앵커)에
      동의.
- [ ] **§0.4g/§1 PRD-EV core tier 존재 shape**(2행 모두 최소 레벨 EV-L1 슬라이스 보유 [`EV-L1/3+Broker`·
      `EV-L1/3`, line 396–397] — #8/RCL형·#10 "0건 완결"과 다름) + **닫는 PRD-EV 0건**(authoring≠evidence, VER §5·
      ADR §20/§21) + ADR-002-001 = umbrella ADR(§21 나머지 criteria는 타-ADR EV family 바인딩, §3.5 소유권 분할과
      1:1) + "EV-L1-complete 주장 금지"에 동의.
- [ ] §2 데이터 모델(`ProtectiveCapacityProfile` = IndependentId + 독립 id·append-only version) + §2.2 어휘
      **verbatim 전사**(GuaranteeLevel 5·ProtectiveOwnership 4·ProtectiveResourceDomain 7군·Admissibility 3·
      ProtectiveActionOutcome 3·DegradedModeTransition)에 동의.
- [ ] **§4.1 domain-enumeration completeness**(미열거⇒UNAVAILABLE·assume-present 부재 — PRD-EV-001) + **§4.2
      guarantee-level completeness**(미할당⇒UNAVAILABLE·PRIORITIZED≠reserved·guaranteed-requires-demonstration —
      PRD-EV-002) + §4.3 classification purity(strategy-label 비권위·증명불가⇒risk-increasing) + §4.4 5-axis
      좌표 비붕괴 + §4.5 representation≠enforcement(egress/mutate/mode-set 메서드 부재) + §4.6 append-only same-id/
      diff-bytes에 동의.
- [ ] §5 core 술어(domain_enumeration_complete·guarantee_level_resolved·is_reserved_guarantee·protective_
      classification[final<current ∧ intermediate≤no-action ∧ bounded]) — 전부 both-ways canary·닫지 않음에 동의.
- [ ] §6 predicate-only 술어(**§8.5 de-restriction**[not-automatic ∧ affirmative ∧ governed ∧ no-dominating ⇒
      CONTAINED 유지·not-a-re-arm]·**§9 partition-lease-admissibility**[cancel-first-outside-scope⇒TRAPPED·
      ADR-owns]·**§11 cancellation-arbiter**[SAFETY_OWNED 세 disjunct·cancel-ack≠FQP·no optimistic credit]·
      **§13 retry/exhaustion**[budget=0⇒containment·UNKNOWN+no-dedup⇒no-retry]·§10 time-untrusted·§7 envelope
      subordination·§12.5/12.6 sufficiency/allocation)에 동의.
- [ ] §7 하네스 타깃(**core 2[PRD-EV-001/002 L1 슬라이스]/predicate-only 9군·닫는 PRD-EV 0건**; both-ways canary;
      **fixture clean-vs-illegal 정합 규율**[#8 교훈]; **seam cross-check MANDATED test-only·NOT package edge**;
      "EV-L1-complete 주장 금지"; §1↔§5/§6↔§7 self-consistency 대조), §7.1 import-closure(rcl/authority/orthostate/
      liveauth/recon/evidence/capsule/time/dsl/brokercap 부재 + canonical/ordering 허용), §7.2 run manifest 7항목에
      동의.
- [ ] §8 bounds 주입 + **확정 신규 누락 distinct 키 = Phase-0 candidate 1군**(per-guarantee-level reserve
      minimum·dynamic sufficiency threshold·protective retry budget — Safety Profile INSTANCE·ADR §12.5/§7/§13
      위임; **Reserved-Protective-minimum 기본은 #5 이미 플래그 — 이중 계상 회피**; 기존 broker-키 재계상 없음;
      fail-closed 주입 default라 safety-neutral)에 동의. **§8 에라타 관찰**(프로파일 `B_rate_limit_recovery`
      rationale "ADR-002-001 §7.5"는 실존 조항 부재 — 비-normative 관찰, 스펙 미수정)에 동의.
- [ ] §9.2 Phase-0 이관 **12항목**(seam decoupled·프로덕션 canon·Safety Profile bound family·broker별 domain·
      Protective Action Controller 런타임·ARE risk-수치·replacement-gap[PR]·+Security/evidence-replay·required-
      domain/per-mode 매핑·emergency-set/horizon/de-restriction 기준·독립 리뷰어·cross-package 좌표 조정)을 별도
      게이트로 유지에 동의.
- [ ] 명명 규약(§0.4f): 모델 불변식을 **PRD-EV-001/002 · §21 acceptance-criteria(불릿) · §-clause ·
      SAFE-001/002/003/004/011/013/014/015/021/024/025/035/040/041/043/044/048/050/051**에 앵커하고 **새 INV
      시리즈를 창작하지 않음**(ADR-002-001 자체 INV 부재 — 실측)에 동의.

비준 시 효력: IMPLEMENTATION-PLAN-002 §4 Phase 1의 ADR-002-001 부분을 `tos/src/tos/protective/`에 순수·비전송
모델 + property test로 작성 착수 승인(`tos.canonical`·`tos.ordering` REUSE, **sibling edge 0건, PROMOTE 0건**,
produced-bool seam은 caller/integration 이연 + test-only cross-check MANDATED). §9.2 Phase-0 12항목과 bounds
승인·독립 리뷰어 지정, Phase B(Protective Action Controller 런타임·capacity 강제·broker profile·ARE·+Security·
+Broker) 전체는 별도 게이트로 남는다. **닫는 PRD-EV 0건 — acceptance 주장 없음.**
