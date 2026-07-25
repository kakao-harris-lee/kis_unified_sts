# 설계 문서 #15 — Independent Proposal Approval·Exact Decision Binding 계약 (2026-07-26, v1.1)

- **대상 ADR**: ADR-002-023 — Independent Proposal Approval, Exact-Decision Binding, and Consumption
  Fencing ("IAP"). 693줄. Status **Proposed** (v0.2).
- **자체 시리즈(실측·앵커)**: **IAP-INV-001..015**(§6 line 132–190, 15종)·**IAP-AC-001..012**(§25 line
  571–617, 12종)·**IAP-EV-001..012**(EVIDENCE-REGISTER-002 line 300–311, 12행). **새 시리즈 창작 금지**.
- **Depends On(ADR line 11)**: RFC-000; RFC-001 SAFE-001..004, SAFE-010..015, SAFE-020/021, SAFE-030..035,
  SAFE-040/041/043..048, SAFE-050..052; ADR-002-001 through ADR-002-022.
- **시리즈 선례(동형 유지)**: 설계 #14(Intent-to-Order Conformance, `tos.ioc`, v1.1 — **-020/-023 소유권
  분할이 이미 판정됨**, §3.5에서 상속)·#13(Aggregate Risk Projection, `tos.are`, v1.1)·#12(Safety Profile
  Governance, `tos.spg`, v1.1).
- **비준 상태**: **2026-07-26 운영자 위임 자동 비준(v1.1; 2026-07-25 지시 — 독립 비평 리뷰 REVISE[CRITICAL 0·
  MAJOR 1 phantom 인용·MINOR 5 라인 에라타]의 minimal edit set 전량 반영·오케스트레이터 검증 후 집행). §10.2
  판단 지점: `tos.iap` 명명·**sibling edge 0**(#14와 대조되는 distinction)·`ApprovalConsumptionRecord` IAP 소유·
  Request identity=IndependentId·`ApprovalResult.DENY`≠orthostate `IntentState.DENIED`(리뷰 완전 검증) 채택.
  효력: `tos/src/tos/iap/` Phase 1(EV-L1) 착수.** 본 문서는 어떤 IAP-EV·ADR acceptance·restricted-live·
  production도 승인하지 않는다(§0.2). §10.2 판단 지점(패키지 명명·`ProposalApprovalRequest` identity·
  `ApprovalConsumptionRecord` 소유·edge 0 vs CapacityVector REUSE)은 운영자·독립 리뷰어 확인 사항이다.
  효력 없음(리뷰 전).

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. ADR-002-023 조항별 **Phase 1(EV-L1) 도달성 경계**(§1). **core(L1 슬라이스) / predicate-only /
   not-Phase-1(형제 소유·런타임 이연) 3분류.** **결정적 사실(register 실측)**: `IAP-EV` 12행 중 **6행이
   register 최소 레벨에 `EV-L1` 슬라이스 보유**(core tier) = **001**(Complete Exact Request `EV-L1/3` line
   300)·**003**(Deterministic Restrictive Decision `EV-L1/3` line 302)·**004**(Exact Artifact and Scope
   Binding `EV-L1/3+Security` line 303)·**007**(Invalidation Dependency Closure `EV-L1/3` line 306)·**009**
   (UNKNOWN Protective and Human Confinement `EV-L1/3+Broker` line 308)·**011**(Economic Continuity and Broker
   Ambiguity `EV-L1/3+Broker` line 310). 나머지 **6행(002·005·006·008·010·012)은 전부 `EV-L2/3+Security`**
   (최소 ≥ L2, line 301/304/305/307/309/311). **orchestrator 사전 카운트 "core 6"은 실측과 일치**한다(#14와
   동형·정정 불요). 그러나 **닫는 IAP-EV = 0건**(L1 슬라이스 저작 ≠ EV closure: `/3`·`+Security`·`+Broker`
   잔여). "**EV-L1-complete 주장 금지**".
2. **중심 데이터 모델 계약**(§2): 전부 digest-bound인 `TradingApprovalPolicy`(§5.1/§8, spg-governed)·
   `ProposalApprovalRequest`(§5.3/§9)·`IndependentApprovalDecision`(§5.4/§11)·`ApprovalConsumptionRecord`
   (§5.5/§12) `IndependentIdArtifact` + `TradingApprovalGeneration`=`tos.ordering` REUSE(§5.2) + all-false
   `ApprovalAuthorityEffect`(§7/IAP-INV-005, `iap/_base.py` — 형제 per-package 관행). 어휘:
   **`ApprovalResult`(APPROVE/DENY/UNKNOWN — §1 line 17·§11 line 289; truthy-sentinel 임계)**·`ConsumptionStatus`
   (ELIGIBLE/CONSUMED — §12 single-use 상태기계)·`MaterialityVerdict`(MATERIAL/IMMATERIAL/UNKNOWN⇒MATERIAL —
   §5.7 line 126 "Unknown materiality is material"). **digest-bound 판정 근거 = §5.4 line 114 "signed or strongly
   bound"(§11 line 291 "signature or strong binding")·§9 line 240 "canonical digest"·§5.5 line 118
   "authoritative immutable proof"(v1.1 MINOR-2 정정).**
3. **complete exact request 중앙 불변식**(§4.1/§5.1, IAP-EV-001 substrate — §9·IAP-INV-001·IAP-AC-001):
   `request_is_complete(request) -> ApprovalResult`. **§9 line 238–251 전 필드**(request/proposer/scope/artifact
   digest/generation/independent-fact/validity/consumption/authority)가 present ∧ non-wildcard ∧ non-empty일
   때만 통과; **absent/empty/wildcard/unknown/stale/conflicting/unverifiable ⇒ 불완전 ⇒ APPROVE 불가**(§9 line
   253 verbatim). PROPOSAL-APPROVAL-REQUEST-template.yaml의 fail-closed 기본값(`required_scope_complete: false`
   L17·`action_class: UNKNOWN` L29·`operating_mode: UNKNOWN` L30·authority 10-flag all-false L72–82)이 앵커.
4. **deterministic restrictive decision 중앙 불변식**(§4.2/§5.2, IAP-EV-003 substrate — §11·IAP-INV-003·
   IAP-AC-003): `approval_decision(...) -> ApprovalResult`. **동일 (완비 input set + policy + generation) ⇒
   동일 result**; **missing/stale/conflicting/unverifiable/unsupported/unknown ⇒ DENY/UNKNOWN, never APPROVE**
   (§11 line 289·IAP-INV-003 line 142 verbatim). `APPROVE`는 non-authorizing business gate — 소비 자격만(§11
   line 294). `DENY` terminal-for-request·`UNKNOWN` 승격 불가(§11 line 296: repeated eval/timeout/majority/
   capacity/human-pref/prior-success/expected-rejection로 promote 불가). decision id⊥digest(재발행·substitution
   탐지). **`ApprovalResult`는 `__bool__` ⇒ TypeError 구조 봉인**(§4.7·#14 M1 선례를 **처음부터** 채택).
5. **exact binding chain 중앙 불변식**(§4.3/§5.3, IAP-EV-004 substrate — §13·IAP-INV-004·IAP-AC-004):
   `exact_binding_holds(chain) -> ApprovalResult`. **§13 line 328–342 체인**(Capsule → proposal → construction
   envelope → candidate command → venue snapshot/decision → ProposalApprovalRequest → IndependentApprovalDecision
   → ApprovalConsumptionRecord + immutable Intent → … → Order Conformance Proof)의 **인접 쌍 digest·identity
   참조가 전부 정합**할 때만 통과. account/instrument/direction/quantity/unit/price/Capsule/venue/construction/
   broker/route/environment/policy/generation/software/deployment **어느 substitution도 decision 무효화**(IAP-AC-004
   line 585). **양방향 집합 비교**(결측=binding 끊김·잉여/치환=다른 chain — #14 MAJOR-1 교훈).
6. **invalidation dependency closure 중앙 불변식**(§4.4/§5.4, IAP-EV-007 substrate — §14·IAP-INV-008·IAP-AC-007):
   `invalidation_closure(graph, trigger) -> frozenset[node]`. **§14 line 361 "complete dependency closure across
   requests, decisions, consumption records, Intents, risk/flow decisions, commitments, proofs, authorities,
   capabilities, pending attempts, egresses, and protection"**를 순수 그래프 도달성으로 계산. **부분 폐포 =
   fail-open**(dependent 탈출 = 안전 위반); **불확정 edge ⇒ 확장(reachable로 취급)**. `MaterialityVerdict`
   UNKNOWN⇒MATERIAL(§5.7 line 126). **absence of invalidation event ≠ currentness proof**(§14 line 365 verbatim).
7. **UNKNOWN confinement + economic continuity 중앙 불변식**(§4.5/§5.5/§5.6, IAP-EV-009/011 substrate — §16·§11·
   §19·IAP-INV-010/011·IAP-AC-009/011): `unknown_confines(...)`(UNKNOWN approval·input·common-mode·generation·
   consumption·invalidation 상태 ⇒ ordinary new risk 차단; **available capacity가 uncertainty를 permission으로
   전환 불가**, §16 line 391 verbatim·IAP-INV-010) ∧ `economic_effect_outlives(...)`(expiry/invalidation/denial/
   revocation/loss·missing-ACK·cancel-ACK가 order/exposure/UNKNOWN/capacity를 **erase·release 못 함**, §16 line
   397·§19 line 437·IAP-INV-011). human/protective label ≠ bypass(IAP-INV-013·§16 line 393).
8. **IAP ↔ dsl/capsule/ioc/venue/brokercap/spg/are/rcl/orthostate/liveauth 경계(중심 아키텍처)**: IAP는
   **sibling edge 0건** — closure = `tos.canonical` + `tos.ordering` + `tos.iap.*`(§0.4b/§0.3). IAP는
   dataflow상 **dsl `Proposal`·capsule Capsule/Snapshot·ioc `AuthorizedConstructionEnvelope`/`CanonicalBrokerCommand`·
   venue Order Admissibility Decision·brokercap `BrokerCapabilityProfile`·spg-governed policy의 하류**(전부
   digest/identity scalar로 주입 소비)이자 **orthostate PROPOSED→APPROVED transition·are `AggregateRiskDecision`·
   ioc `OrderConformanceProof`·liveauth `LiveAuthorization`의 상류**(승인 decision·consumption record identity를
   **하류 형제가 scalar로 참조**). **produced/consumed seam 전부 scalar·digest(edge 0)** — #14의 1 edge
   (`ioc→rcl CapacityVector`)와 대조되는 **본 문서의 distinction**(§0.4c). 코드 실측: ioc `ApprovedIntentContract.approval_identity`
   (`records.py:199`)·`AuthorizedConstructionEnvelope.approval_identity`(`:294`)·are `approval_identity`
   (`records.py:348`)·liveauth `approval_record_identity`(`records.py:112`)가 이미 IAP를 scalar로 참조.
   **단 ioc `OrderConformanceProof`(records.py:357)는 approval/consumption identity 필드를 아직 보유하지
   않음** — §13 line 346 proof-binding은 -023 하류 미래 배선(§9.2 item 14; v1.1 MAJOR-1 정정).
9. **-020/-023 소유권 분할 상속·정합**(§3.5, #14 §3.5 판정 상속): **§8 Approved Intent field set = -020**
   (ioc `ApprovedIntentContract` `records.py:142`) / **approval·registration = -023(본 문서)**(`IndependentApprovalDecision`·
   `ApprovalConsumptionRecord`·single-use consumption 판정) / **Proposal id scheme·PROPOSAL-APPROVAL-REQUEST
   어휘 = -020/-023 공동**(dsl `Proposal`이 anchor·IAP가 full request 소유). 코드 확증: ioc `records.py:154–155`
   "Independent Approval + immutable Intent Registration remain ADR-002-023 (IAP); this models the approved field
   set, not the registration". **orthostate 경계(본 문서 최대 함정 지대)**: **orthostate가 Intent 차원(IntentState
   전이·Intent Registry lifecycle) 소유**(`vocabulary.py:35–36` "owned by the Intent Registry"), **IAP는 승인
   decision·single-use consumption 판정·ConsumptionStatus 차원 소유**. `ApprovalResult.DENY` ≠ `IntentState.DENIED`
   (§3.5 핵심 판정).
10. **fail-closed 규율 + named both-ways canary + truthy-sentinel 소비 계약**(§4/§4.7): unknown/stale/conflicting/
    incomplete ⇒ denial(headroom 창조 금지); default/wildcard/substitute/union/widen/coerce ⇒ 거부; UNKNOWN
    승격·capacity offset ⇒ 거부; expiry ⇒ economic effect persists; recovery ⇒ non-revival; **∅ 양방향 명시**
    (빈 request 필드=APPROVE 불가·빈 의존 집합의 폐포=최소 폐포 or 확장·빈 scope=UNKNOWN[zero/wildcard 아님]).
    **`ApprovalResult`·`ConsumptionStatus`·`bool|None` 반환 술어는 소비 게이트의 `is ApprovalResult.APPROVE`/
    `is True` 명시 비교 계약을 §4.7에 명문화**(#14 truthy-sentinel 교훈을 처음부터 구조 봉인).
11. **property-test 하네스 타깃**(§7) + import-closure 검증(§7.1) + run manifest 7항목(§7.2) + fixture
    clean-vs-illegal 정합(#8 교훈) + seam cross-check(test-only, §3.4) + **invalidation-closure property**(도달성
    완전성·불확정⇒확장) + **single-use consumption 상태기계 property**(등록→소비→소진; 재사용⇒거부) + **truthy-sentinel
    구조 봉인 회귀**(§4.7).
12. **bounds 주입 계약 + Phase-0 이관**(§8): IAP 모델 구조에는 numeric bound 부재(전부 enum·boolean·집합·그래프
    논리·주입 opaque age param); ADR §27 q12가 요하는 수치(`B_approval_invalid_to_intent`·`B_approval_invalid_to_egress`·
    `B_approval_generation_fence`·`MAX_proposal_approval_request_age_ms`·`MAX_independent_approval_decision_age_ms`)는
    **VERIFICATION-PROFILE-002에 전부 실재**(§8.1 실측: line 303·310·317·721·722, 전부 `null`/MEASURE) + 3
    scope-pin(`trading_approval_policy_id/generation/digest` line 67–69)이며 **candidate 신규 키 0건**(#14형
    "0 누락"). 값 승인은 Bounds-Approver 게이트.

### 0.2 하지 않는 것 (경계·NO 목록)

- **ADR/스펙 비준·acceptance·restricted-live·production 어느 것도 승인하지 않는다.** ADR §28 line 679 verbatim
  "Authorship, schema drafting, `APPROVE` output, successful Intent creation, signatures, logs, written cases,
  registered evidence, or EV-L0 document review do not satisfy this gate. This ADR authorizes architecture and
  implementation planning only." **닫는 IAP-EV = 0건.**
- **Intent 상태 전이·Intent Registry lifecycle을 저작하지 않는다.** `PROPOSED → APPROVED → AUTHORIZED_FOR_CAPACITY
  → ACTIVE → CLOSED`·`APPROVED → DENIED` 전이는 **orthostate(ADR-002-005) 소유·구현**(`vocabulary.py:32` `IntentState`·
  `predicates.py:364` `_INTENT_TRANSITIONS`·`predicates.py:432` `intent_transition_allowed`). IAP는 승인 decision을
  **produce**하고, Intent Registry가 그것을 소비해 orthostate transition을 수행한다(§7 line 202 "Consume approval and
  register Intent | none | Intent Registry"). IAP는 `intent_identity`(`records.py:93`)·`IntentState`를 **scalar로만
  참조**하고 orthostate를 import하지 않는다(§3.4/§3.5).
- **capacity 산술(commit/consume/release·serialize)·aggregate risk projection·action-flow budgeting을 저작하지
  않는다.** capacity는 **rcl(ADR-002-002/012)**, risk projection은 **are(ADR-002-021)**, action-flow는 **ADR-002-022(AFG,
  병렬 세션 B 소관 — ADR 원문만 참조)** 소유. IAP-INV-005 line 150 verbatim "Approval cannot mutate capacity,
  create headroom, issue authority, classify protection, transmit, clear HALT, or re-arm." **`APPROVE`는
  `AUTHORIZED_FOR_CAPACITY`·capacity commitment·Live Authorization·capability issuance·transmission과 등가가 아니다**
  (§11 line 294). 이후 aggregate-risk·action-flow·RCL·conformance·authority·live-scope·capability·final-egress
  게이트는 독립적으로 필수(§1 line 21·§12 line 320).
- **independent recomputation의 실 강제·common-mode 격리를 저작하지 않는다(런타임/+Security).** §10 independent
  evaluation(별도 평가자·approved independent path·source/parser/mapping/library/model/cache/registry/admin/
  deployment/network/clock common-mode 격리)의 **실행**은 EV-L2/L3+Security 런타임이다(IAP-EV-002 predicate-only).
  Phase-1 IAP는 **구조적 L1 슬라이스**(proposer-only value ≠ independent·common-mode 선언 완비성)만 저작한다(§6.1).
- **Intent Registry의 linearizable serialization·writer-epoch fencing을 저작하지 않는다(런타임).** §12 line 316
  verbatim "The transaction SHALL be linearizable or equivalently fenced. A database uniqueness constraint without
  authoritative generation fencing is insufficient…" — 실 직렬화·writer fence는 EV-L2/L3+Security(IAP-EV-005/010
  predicate-only). Phase-1은 **single-use consumption 상태기계 모델**(등록→소비→소진; 재사용⇒거부)만 저작한다(§6.2).
- **final-egress active currentness의 실 강제·전송을 저작하지 않는다.** §15 final-egress verification·capability
  claim·`SEND_STARTED` ordering은 **ADR-002-013(Egress Gateway)·ADR-002-007(capability)·ADR-002-024(Currentness
  Vector) 런타임**이다(§1 line 29). IAP는 currentness 요구를 **술어로 명세**(cache/heartbeat/TTL/absence-of-event가
  currentness 아님)하되 wire 강제를 하지 않는다(§6.4).
- **TradingApprovalPolicy governance·activation을 저작하지 않는다.** policy는 **spg(ADR-002-014) governed member**
  (§8 line 232 "The policy is an immutable safety artifact under ADR-002-014")이다. IAP는 policy를 digest scalar로
  **참조·소비**(spg `BundleMemberKind` `vocabulary.py:180`의 한 member)하되 activation·거버넌스를 하지 않는다.
- **human dual-control·break-glass·protective classification을 저작하지 않는다.** human approval은 **ADR-002-015**,
  protective classification은 **ADR-002-001** 소유(§4 non-scope line 90). IAP-INV-013 line 182 "Human approval …
  or protective labels do not substitute for this approval." IAP는 label ≠ bypass만 술어화(§5.5).
- **canonical semantic FORM·schema·numeric type·registry·numeric/invalidation bound를 승인하지 않는다.** ADR §27
  q1–q3·q12·§4 non-scope line 92. canonical form은 `EVL1ProvisionalCanonicalizer` REUSE(잠정, §3.1); 프로덕션
  schema·evaluator·independent-source allocation·수치는 **Phase-0 §9.2**. 값 부재 ⇒ fail-closed.
- **evidence/replay ENGINE을 저작하지 않는다.** durable custody·isolated replay는 **ADR-002-016** 소유(§21 line
  467). IAP는 decision/consumption 레코드 substrate만 저작하며 evidence has no approval/transition/authority
  permission(§21 line 467·IAP-INV-015 line 190).

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

`tos.iap` 모델은 다음만 import한다:

- 서드파티: `pydantic`(frozen 모델), `pytest`·`hypothesis`(테스트만). **`numpy`/`pandas`/`pyyaml`도 import하지
  않는다** — 승인 결정 규칙은 StrEnum·boolean·집합/그래프 논리이고 모든 bound·age·registry·mapping 값은 주입
  파라미터이며 YAML 파싱은 하네스(설계 #3) 소관이다(closure 최소화 — #12–#14 §0.3 동형).
- tos 자기 자신: `tos.canonical`(`FrozenModel` `_base.py:73`·`DigestBoundArtifact` `_base.py:98`·`IndependentIdArtifact`
  `_base.py:328`·`IdDerivedArtifact` `_base.py:256`·`classify_record_pair` `record_pair.py:52`·`RecordPairKind`
  `record_pair.py:31`·`ArtifactStatus` `_base.py:58`·`EVL1ProvisionalCanonicalizer` `canonicalization.py:173`),
  `tos.ordering`(`Ordering`·`OrderingEvent`·`compare_order` `__init__.py:19` — Trading Approval Generation 순서;
  실측: `ordering/_ordering.py:38` `from tos.canonical import FrozenModel`만 의존이라 core), `tos.iap.*`.
  **`tos.dsl`·`tos.capsule`·`tos.ioc`·`tos.brokercap`·`tos.spg`·`tos.venue`(미구현)·`tos.are`·`tos.rcl`·
  `tos.orthostate`·`tos.liveauth`·`tos.authority`·`tos.time`·`tos.evidence`·`tos.protective`·`tos.recon`을
  import하지 않는다**(produced/consumed scalar·digest로만 참조 — §3.4/§3.5). **PROMOTE 0건. sibling edge 0건.**
- **`shared.config` 절대 금지**(설계 #1 §6.1, `.importlinter`): `shared.config.__init__`이 `shared.config.secrets`
  (→ `os.environ`)를 무조건 전이 import한다. `tos.iap`는 어떤 `shared.*`도 필요로 하지 않는 순수 커널이다.
- **금지(직접·전이 모두)**: `shared.execution`, `shared.kis`, `shared.streaming`, `shared.llm`, `shared.storage`,
  `shared.backtest`, `shared.config.secrets`, `services.*`, `cli.*`(`.importlinter`
  `[importlinter:contract:tos-operational-firewall]` type=forbidden·source_modules=`tos` 실측 — forbidden set).
- **firewall 구조 확인(실측)**: `.importlinter`는 `type=forbidden·source_modules=tos` 단일 계약이며 `layered`가
  아니다 — intra-tos sibling→sibling edge는 구조적으로 금지되지 않고 설계 #1 §3.2의 "자기 자신 `tos.*`" 허용
  조항이 이를 커버한다. **신규 패키지 `tos.iap`는 firewall 도구 무수정 자동 포섭**된다(forbidden 계약이
  source=tos 전체를 덮으므로). **본 문서는 sibling edge 0을 설계 규율로 삼는다** — 모든 형제 seam을
  produced/consumed scalar·digest(edge 0)로 유지한다(§0.4b; #12/#13/#14보다 엄격 — #14는 1 edge, IAP는 0 edge).
- 이 배제를 능동 강제하는 것이 §7.1 import-closure 검증 테스트다(`import tos.iap` closure에 금지·`shared.config`·
  `os.environ`·numpy/pandas/yaml·**15개 형제 tos 패키지 전부** 부재 assert; **`tos.canonical`·`tos.ordering`만
  존재 허용**). required check(`tos-firewall`, `tools/tos_firewall_check.py` layer-① AST + `.importlinter`
  layer-② 전이 방어)와 함께 green이어야 성립.

### 0.4 REUSE / import / 경계 결정 요지 (핵심 아키텍처)

**(a) 패키지 위치·명명 = `tos/src/tos/iap/`.** register domain(EVIDENCE-REGISTER-002 line 300) "**Independent
Proposal Approval**"·prefix `IAP`(`IAP-EV`/`IAP-AC`/`IAP-INV`)를 직접 명명. 명명 대안 비교(#14 §0.4a 형식):

- **`tos.approval`(runner-up·verbose·부분)**: 명료하나 (i) **"independent"·"exact binding"·"consumption fencing"을
  이름에서 누락**(ADR 제목 3축 중 1축만), (ii) **verbose(8자)**로 terse 3-letter 관행(rcl/spg/dsl/are/ioc)과
  어긋남, (iii) **human approval(ADR-002-015)과의 의미 혼동** 위험(IAP는 automated independent approval — §1
  line 17·§4 non-scope line 90에서 human 명시 배제), (iv) register prefix `IAP`와 불일치. **§10.2 판단 지점의
  defensible 차선**.
- **`tos.consumption`(기각·부분)**: §12 single-use consumption만 포섭하고 **request(§9)·decision(§11)·binding(§13)·
  invalidation(§14)을 누락**한다. register prefix 불일치.
- **`tos.intent`(하드 기각·collision)**: **orthostate Intent 차원**(`IntentState` `vocabulary.py:32`)·**ioc
  `ApprovedIntentContract`**(`records.py:142`)와 정면 충돌한다 — Intent state·field set은 orthostate·ioc 소유이고
  IAP는 그 소유자가 아니다. 권위 붕괴 위험. 하드 기각.
- **선택(권장) `tos.iap`**: **register domain "Independent Proposal Approval"·prefix `IAP`**를 직접 명명, terse
  3-letter로 `tos.rcl`/`tos.spg`/`tos.dsl`/`tos.are`/`tos.ioc` 관행 정합, ADR 제목·EV/AC/INV 시리즈 전체와 1:1.
  **오독 위험(#14 대비 경감)**: `ioc`는 트레이딩 도메인에서 Immediate-Or-Cancel(TIF)로 읽힐 강한 위험이 있었으나
  (#14 §0.4a), **`iap`는 이 도메인의 주문 용어가 아니다** — 소프트웨어 일반에서 In-App Purchase 연상이 가능하나
  트레이딩/세이프티 커널 문맥에서는 약하다. **코드 토큰 충돌 0**(실측: tos 내 `iap`/`approval`/`consumption`
  디렉터리·토큰 부재 — 기존 `approval_identity`/`approval_record_identity`/`human_approval` 등은 전부 **scalar
  필드명**이지 패키지가 아니다). 완화: package docstring 1행("Independent Proposal Approval — ADR-002-023; not
  human approval[ADR-002-015]")으로 봉합. **load-bearing은 layering**(iap → canonical·ordering 한 방향; 15개
  형제 전부 **produced/consumed scalar·digest seam·edge 0**). **§10.2 운영자 판단 지점**: `tos.iap`(register-prefix
  충실·오독 경미) vs `tos.approval`(명료·verbose·부분·human 혼동). 내부 module(`_base.py`·`vocabulary.py`·
  `records.py`·`predicates.py`·`state.py`)은 rcl/are/spg/ioc 선례 동형(ioc `__init__.py` 실측 구조).

**(b) iap = produced/consumed scalar·digest producer/consumer, sibling edge 0건 (중심 결정·#14와의 distinction·
코드 실측).** IAP는 **dataflow상 파이프라인 중앙**에 위치한다 — dsl/capsule/ioc/venue/brokercap/spg의 **하류**
(proposal·capsule·construction·admissibility·profile·policy 주입 소비)이자 orthostate/are/rcl/liveauth/egress의
**상류**(approval decision·consumption record identity를 하류 형제가 참조). #14의 ioc는 `EconomicEffectEnvelope`
타입 공유를 위해 `ioc→rcl CapacityVector` 1 edge가 필요했으나, **IAP는 어떤 형제 타입도 REUSE하지 않는다** —
승인 결정·소비·binding·invalidation은 전부 identity/digest/enum/집합/그래프 위 순수 판정이고 capacity vector
산술이 없다(§0.4c). **코드 실측 seam**(sibling 서사 아님 — #10 MAJOR 교훈):

| IAP 소비/생산 (§ref) | 타입 | 상대 (이미 비준·구현) | signature(실측) |
|---|---|---|---|
| dsl `Proposal`(the proposal being approved) 소비 | `str`(id)·`str`(digest) | dsl `Proposal`(`dsl/proposal.py:68`, `IdDerivedArtifact`·all-false authority·PROPOSAL-APPROVAL-REQUEST 어휘 anchor `proposal.py:7`) | `ProposalApprovalRequest`가 `proposal_id`+`proposal_digest` scalar로 §9 line 242 binding; dsl이 "an anchor, not a redefinition of ADR-002-020"(`proposal.py:7–8`)·approval downstream(`dsl/outcome.py:216`) |
| capsule `DecisionContextCapsule`·`CriticalInputSnapshot` 소비 | `str`(id)·`str`(digest) | capsule `DecisionContextCapsule`(`capsule/capsule.py:170`, IdDerived)·`CriticalInputSnapshot`(`snapshot.py:96`, IdDerived) | `ProposalApprovalRequest`가 capsule/snapshot id+digest binding(§9 line 244) |
| ioc `AuthorizedConstructionEnvelope`·`CanonicalBrokerCommand` 소비 | `str`(id)·`str`(digest) | ioc `AuthorizedConstructionEnvelope`(`ioc/records.py:215`)·`CanonicalBrokerCommand`(`records.py:301`) | `ProposalApprovalRequest`가 envelope/command id+digest binding(§9 line 245); ioc가 field set·candidate command 소유(§3.5) |
| ioc `ApprovedIntentContract`(approved Intent envelope 형태) 소비 | `str`(id)·`str`(digest) | ioc `ApprovedIntentContract`(`ioc/records.py:142`, IndependentId — "models the approved field set, not the registration" `records.py:154–155`) | `IndependentApprovalDecision`이 approved Intent envelope를 §11 line 288 binding·§12 line 309 "byte-for-byte or canonically equivalent" 비교(ioc가 -020 field set 소유·IAP가 approval/registration) |
| venue Order Admissibility Decision 소비 | `str`(id)·`str`(digest) | ADR-002-019(형제·미구현 시 주입 slot) | `ProposalApprovalRequest`가 venue snapshot+admissibility decision id+digest binding(§9 line 246) |
| brokercap `BrokerCapabilityProfile` 소비 | `str`(id/version/digest)·injected enum | brokercap `BrokerCapabilityProfile`(`brokercap/records.py:305`) | broker ambiguity(§16·IAP-EV-011)·capability는 injected result·profile digest binding(§9 line 247) |
| spg-governed `TradingApprovalPolicy` 소비 | `str`(id/generation/digest) | spg Safety Config Bundle governance(ADR-002-014·`BundleMemberKind` `spg/vocabulary.py:180`) | policy는 spg-governed member(§8 line 232); IAP가 digest 참조·spg가 거버넌스 |
| orthostate `intent_identity`·`IntentState` 소비 | `str|None`(scalar)·enum token | orthostate `intent_identity`(`orthostate/records.py:93`)·`IntentState`(`vocabulary.py:32`)·`intent_transition_allowed`(`predicates.py:432`) | consumption 시 `ApprovalConsumptionRecord`가 `intent_identity` scalar binding(§12 line 318); PROPOSED→APPROVED 전이는 orthostate 소유(§3.5) |
| `IndependentApprovalDecision`·`ApprovalConsumptionRecord` identity 생산 | `str`(id)·`str`(digest) | are `AggregateRiskDecision.approval_identity`(`are/records.py:348`)·ioc `ApprovedIntentContract.approval_identity`(`ioc/records.py:199`)·`AuthorizedConstructionEnvelope.approval_identity`(`:294`)·liveauth `LiveAuthorization.approval_record_identity`(`liveauth/records.py:112`) | 하류 형제가 IAP decision/consumption identity를 **scalar로 참조**; **`OrderConformanceProof`(:357)의 §13:346 proof-binding은 미래 배선**(§9.2 item 14, v1.1 MAJOR-1 정정); IAP는 그들을 import하지 않음 |

**(c) sibling edge 0 결정 (중심·#14와의 distinction).** #14 ioc는 §13 economic-effect dominance를 **타입 수준으로**
봉하려 `EconomicEffectEnvelope = rcl CapacityVector` REUSE(ioc→rcl 1 edge)를 채택했다. **IAP는 이 edge가 불요**하다:

- IAP의 core L1 술어(`request_is_complete`·`approval_decision`·`exact_binding_holds`·`invalidation_closure`·
  `unknown_confines`·`economic_effect_outlives`)는 **전부 identity/digest/enum/집합/그래프 위 순수 판정**이며
  **capacity vector 산술이 없다**. §9 "maximum Economic Effect Envelope"(line 243)는 request가 **binding하는
  아티팩트**이지 IAP가 계산하는 값이 아니다 — 다른 §9 아티팩트(capsule·envelope·command·venue snapshot)와
  **동일하게 identity+digest scalar로 참조**(§9 line 244–246 "identities and digests").
- §10 item 4 "independently recompute or verify … conservative economic-effect bounds applicable at approval"는
  **independent recomputation**이며 이는 **IAP-EV-002 predicate-only(EV-L2/3+Security)**의 런타임 몫이다 — L1
  슬라이스가 아니다(§6.1). recompute-and-compare를 하려면 CapacityVector 타입이 필요하나, Phase-1 L1은 recompute를
  하지 않고 digest binding만 한다.
- IAP-INV-010 "cannot be offset by unused capacity"(line 170)는 **부정 술어**(UNKNOWN ⇒ 차단, capacity와 무관)로,
  capacity를 **계산**하라는 요구가 아니라 capacity를 offset으로 **쓰지 말라**는 요구다 — 순수 논리 판정(§5.5).
- **기각 대안** (a) `EconomicEffectEnvelope`=rcl `CapacityVector` REUSE(ioc→iap→rcl 1 edge): independent
  economic-effect recomputation을 L1으로 끌어올리려면 필요하나 (i) recomputation은 +Security 런타임(IAP-EV-002),
  (ii) IAP는 economic-effect **producer가 아니라** approval **gate**다(ioc가 이미 envelope producer·are가 소비),
  (iii) 불필요한 edge는 closure 확대. **§10.2 운영자 판단 지점**: edge 0(권장·control-plane 커널) vs 1 edge
  (independent recompute를 L1화). 완화: §10 line 274 "Recalculation with the same corrupted implementation is not
  validation"·§10 item 6 common-mode 격리가 recomputation을 **런타임 독립 경로**로 명시(L1이 아님).

**(d) `IndependentIdArtifact` vs `IdDerivedArtifact` (canonical REUSE).** decision·consumption record·policy는
**거버넌스/발급 identity ⊥ digest**를 가져 same-id/diff-bytes(request/decision substitution·§18 line 419·중복
consumption) 탐지에 `classify_record_pair`(`RecordPairKind.CRITICAL_CONFLICT`)를 써야 하므로 **`IndependentIdArtifact`**
(id⊥digest)로 저작한다(are `AggregateRiskDecision` `records.py:451` decision_id ⊥ canonical digest 동형·task 지시
"ApprovalDecision id⊥digest"). **`ProposalApprovalRequest` identity는 §10.2 판단 지점**: (i) §9 line 255 "Any
field change creates a new identity" = content-addressed 의미(→ `IdDerivedArtifact`, dsl `Proposal` 동형), (ii)
그러나 proposer가 request를 생성하므로 proposer가 request_id를 선택하고 digest를 불일치시키는 substitution
탐지에는 `IndependentIdArtifact`가 유리(§18 line 419 "request/decision substitution"). **권장: `IndependentIdArtifact`**
(substitution 탐지 우위; template의 `request_id`·`nonce`·`canonical_digest` 3필드 분리 L3–6이 id=f(digest)가
아님을 시사) — content-addressed 대안도 defensible(§10.2). **참고**: 상류 dsl `Proposal`·capsule는 IdDerived
(`proposal.py:3–4`·`capsule.py:170`)이며 IAP는 이를 **재정의하지 않고 digest scalar로 참조**한다.

**(e) 형제 import·미import 근거(§3.5 소유권 분할 요지).**
- **`tos.orthostate` 미import(Intent 차원 상류·하류 = 상호 참조지만 edge 0)**: orthostate가 `IntentState` 전이·
  Intent Registry lifecycle 소유(`vocabulary.py:35–36`). IAP는 승인 decision·consumption 판정을 소유하고
  `intent_identity`/`IntentState`를 scalar로만 참조한다. **PROPOSED→APPROVED 전이는 orthostate `intent_transition_allowed`
  (`predicates.py:432`)가 소유** — IAP는 그 전이를 재저작하지 않는다(§3.5 핵심).
- **`tos.dsl` 미import(Proposal 상류·어휘 공동)**: dsl `Proposal`이 approved-대상 proposal이며 IAP는
  proposal_id/digest scalar로 §9 binding. PROPOSAL-APPROVAL-REQUEST-template.yaml 어휘는 **-020/-023 공동**
  (dsl가 lines 8–12/31–33/72–82 anchor·IAP가 full request 소유, §3.5).
- **`tos.ioc` 미import(construction 상류·field set -020)**: ioc가 `AuthorizedConstructionEnvelope`/`CanonicalBrokerCommand`/
  `ApprovedIntentContract` field set 소유(-020). IAP는 그 id+digest를 §9/§11/§12 binding하고 ioc는 IAP
  approval_identity를 scalar로 참조(`records.py:199`) — 양쪽 미import(acyclic).
- **`tos.capsule`·`tos.brokercap`·`tos.venue` 미import(입력 상류)**: capsule Capsule/Snapshot·brokercap profile·
  venue admissibility는 request의 주입 입력(§9)·injected result. digest/identity scalar만 소비.
- **`tos.are`·`tos.rcl`·`tos.liveauth` 미import(decision 하류)**: are/rcl/liveauth는 approval 하류(§13 chain)이며
  IAP decision/consumption identity를 scalar로 참조(are `records.py:348`·liveauth `records.py:112`). IAP는 그들을
  import하지 않는다(capacity·risk·authorization은 형제 소유).
- **`tos.spg`·`tos.authority`·`tos.time`·`tos.evidence`·`tos.protective`·`tos.recon` 미import**: spg가
  TradingApprovalPolicy 거버넌스(§8 line 232); authority/liveauth는 §7 하류; time validity는 주입 opaque flag(§19 —
  IAP는 clock 미접근); evidence replay engine은 ADR-002-016 하류(§21); protective는 ADR-002-001(§16 IAP는 label ≠
  bypass만); recon은 무관.

**(f) 앵커 규약 — IAP-INV/AC/EV 앵커, 새 시리즈 창작 금지.** **실측**: ADR-002-023은 **자체 시리즈 `IAP-INV-001..015`
(§6 line 132–190, 15종)·`IAP-AC-001..012`(§25 line 571–617, 12종)·`IAP-EV-001..012`(register line 300–311,
12행)를 정의한다.** ⇒ 본 계약은 모델 불변식·술어를 **`IAP-INV-###` / `IAP-AC-###` / `IAP-EV-###` / §-clause /
`SAFE-###`(§26 traceability line 623–636)**에 앵커하고 **새 INV/AC/EV 시리즈를 창작하지 않는다**. #12/#13/#14가
자체 INV에 앵커한 것과 동형. self-consistency 최우선.

**(g) IAP-EV = core tier(6행) + truthy-sentinel 규율, 닫는 IAP-EV = 0건.** register 실측: **6행(001·003·004·007·
009·011)이 최소 레벨에 `EV-L1` 슬라이스 보유**(§1 표), 6행(002·005·006·008·010·012)은 최소 `EV-L2`. ⇒ §1 분류는
**core(L1 슬라이스 6) / predicate-only(6) / not-Phase-1 3분류**(#14형·사전 카운트 6과 일치). **그러나 닫는
IAP-EV = 0건** — L1 슬라이스 저작은 EV closure가 아니다(`/3`·`+Security`·`+Broker` 통합·독립 리뷰 잔여).
**truthy-sentinel 규율(#14 M1 교훈을 처음부터)**: `approval_decision`·`consumption_transition`은 `ApprovalResult`/
`ConsumptionStatus`를 반환하고, `DENY`/`UNKNOWN`/`CONSUMED`가 truthy string이므로 **소비 게이트는 `result is
ApprovalResult.APPROVE` 명시 비교**(truthy 금지)를 §4.7·§5에 계약으로 명문화하며 **`ApprovalResult.__bool__` ⇒
TypeError 구조 봉인**을 처음부터 채택한다. 이 판정은 §1·§4·§5·§6·§7 전체에 **일관**해야 하며 finishing 전
self-consistency pass에서 대조한다.

---

## 1. 범위 매핑 — ADR-002-023 조항별 EV-L1 도달성 (닫는 IAP-EV 0건)

EV-level 정의(VER-002-001): **EV-L1 = Model and Property Verification**(state-machine exploration, model
checking, property-based testing, deterministic simulation). **EV-L2 = Component Fault Test**, **EV-L3 =
Integration/Adversarial**, **+Security = security enforcement**, **+Broker = broker-integration**. Phase 1은
EV-L1만이다.

> **결정적 사실 1 — IAP-EV ↔ IAP-AC 1:1, 최소 레벨 실측(사전 카운트 일치)**: `IAP-EV-001..012`(register line
> 300–311)는 ADR §25 `IAP-AC-001..012`(line 571–617)와 제목·번호가 **1:1**(§25 line 569 verbatim "The following
> cases are mandatory and map one-to-one to `IAP-EV-001` through `IAP-EV-012`"). register 최소 레벨 실측:
> **`EV-L1` 슬라이스 보유(6행)** = 001(`EV-L1/3` line 300)·003(`EV-L1/3` 302)·004(`EV-L1/3+Security` 303)·007
> (`EV-L1/3` 306)·009(`EV-L1/3+Broker` 308)·011(`EV-L1/3+Broker` 310); **`EV-L1` 슬라이스 부재(6행, 최소 ≥ L2)**
> = 002(`EV-L2/3+Security` 301)·005(`EV-L2/3+Security` 304)·006(`EV-L2/3+Security` 305)·008(`EV-L2/3+Security`
> 307)·010(`EV-L2/3+Security` 309)·012(`EV-L2/3+Security` 311). ⇒ **core tier 6행**(#14형; orchestrator 사전
> "core 6"과 **일치**), predicate-only substrate 6행.
>
> **결정적 사실 2 — authoring ≠ acceptance(닫는 IAP-EV = 0건)**: Phase 1은 각 IAP-EV의 **L1-decidable
> predicate/model substrate**를 저작하나 **어떤 IAP-EV도 닫지 않는다.** (a) core 6행조차 `/3`·`+Security`(004)·
> `+Broker`(009/011) 잔여(fault injection·adversarial·security 강제·broker 통합)가 남고, (b) 6행은 최소 ≥ L2,
> (c) VER-002-001 §5 "Registration is not execution"·ADR §25 line 569 "Written cases are not completed evidence"·
> §28 line 674 item 10. ⇒ **"EV-L1-complete 주장 금지"**(#12–#14 §1 규율 상속). Owner/Reviewer는 register상 TBD.

**규율 태그(모든 주장에 부착)**: "**predicate/model substrate only; IAP-EV-001..012 전부 NOT_IMPLEMENTED — core
6행은 `/3`·`+Security`·`+Broker` 통합·독립 리뷰 대기, predicate-only 6행은 EV-L2/L3 fault injection·adversarial·
+Security evidence 대기. EV-L1-complete 주장 금지.**"

**ADR-002-023 조항 → Phase-1 분류(core / predicate-only / not-Phase-1[형제 소유·런타임 이연])**:

| ADR 조항 | 요지 | Phase-1 분류 | L1 substrate / 소유 (근거) | IAP-EV |
|---|---|---|---|---|
| **§9** (line 238–255) | Proposal Approval Request — complete exact request | **core (L1 슬라이스)** | `request_is_complete`(§5.1) — IAP-INV-001. absent/empty/wildcard/unknown/stale/conflicting/unverifiable ⇒ APPROVE 불가(§9 line 253). template fail-closed 기본값 앵커. `/3` 잔여. | **001** |
| **§11** (line 282–298) | Decision semantics — deterministic restrictive | **core (L1 슬라이스)** | `approval_decision`(§5.2) — IAP-INV-003. missing/stale/conflicting/unverifiable/unsupported/unknown ⇒ DENY/UNKNOWN never APPROVE(line 289). id⊥digest. `ApprovalResult.__bool__⇒TypeError`. `/3` 잔여. | **003** |
| **§13** (line 326–346) | Exact binding through pipeline | **core (L1 슬라이스)** | `exact_binding_holds`(§5.3) — IAP-INV-004. chain 인접 쌍 digest 정합; 어느 substitution도 무효화(IAP-AC-004 line 585). parser-differential digest 강제는 +Security. `/3+Security` 잔여. | **004** |
| **§14** (line 350–365) | Invalidation·dependency closure | **core (L1 슬라이스)** | `invalidation_closure`(§5.4) — IAP-INV-008. 순수 그래프 도달성; 부분 폐포=fail-open; 불확정⇒확장; absence≠currentness(line 365). 실 propagation latency는 런타임. `/3` 잔여. | **007** |
| **§16** (line 389–397) | UNKNOWN·protective·human confinement | **core (L1 슬라이스)** | `unknown_confines`(§5.5) — IAP-INV-010/013. UNKNOWN+capacity/label/priority ⇒ 차단(line 391·393). broker ambiguity 통합은 +Broker. `/3+Broker` 잔여. | **009** |
| **§16/§11/§19** (line 397·437) | Economic continuity·broker ambiguity | **core (L1 슬라이스)** | `economic_effect_outlives`(§5.6) — IAP-INV-011. expiry/invalidation/denial·missing-ACK·cancel-ACK가 order/exposure/capacity erase·release 못 함(line 397·437). broker ACK 의미는 +Broker. `/3+Broker` 잔여. | **011** |
| **§10** (line 259–276) | Independent evaluation·common-mode | **predicate-only** | `independent_validation`+common-mode 선언 완비(§6.1) — IAP-INV-002. 실 recompute·source/parser/mapping/registry/admin common-mode 격리는 EV-L2 component-fault·+Security. 최소 `EV-L2/3+Security`. | **002** |
| **§12** (line 302–320) | Single-use serialized consumption | **predicate-only** | `consumption_transition` 상태기계(§6.2, state.py) — IAP-INV-006. 등록→소비→소진; 재사용⇒거부. 실 linearizable serialization·writer fence는 +Security 런타임(line 316). 최소 `EV-L2/3+Security`. | **005** |
| **§7/§13** (line 148·156·344) | No widening/union·authority escalation | **predicate-only** | `no_widening_no_union`+`approval_grants_no_authority` all-false(§6.3) — IAP-INV-005/007. union/widen/capacity/authority/transmit/HALT/re-arm 불가. bypass는 +Security 런타임. 최소 `EV-L2/3+Security`. | **006** |
| **§15** (line 369–385) | Active final-egress currentness | **predicate-only** | `active_egress_currentness`(§6.4) — IAP-INV-009. cache/TTL/heartbeat/absence≠currentness(line 381). 실 egress 강제·capability claim은 ADR-002-013/007/024 런타임. 최소 `EV-L2/3+Security`. | **008** |
| **§17** (line 401–409) | Concurrency·partition·stale-writer fencing | **predicate-only** | `stale_generation_fenced`+conflicting⇒UNKNOWN(§6.5) — IAP-INV-012. 실 partition·split-brain·writer-fence는 EV-L2/L3+Security. 최소 `EV-L2/3+Security`. | **010** |
| **§20** (line 441–447) | Recovery·non-revival | **predicate-only** | `recovery_revives_nothing`(§6.6) — IAP-INV-014. 무조건 True. Recovery Barrier(ADR-002-017)·re-arm workflow enforce는 런타임. 최소 `EV-L2/3+Security`. | **012** |
| **§5/§8** (line 96–128·216–232) | Definitions·Trading Approval Policy contract | **core substrate(분산)** | 4-아티팩트 모델·`ApprovalResult`/`ConsumptionStatus`/`MaterialityVerdict` 어휘(§2). policy governance는 spg(§8 line 232). | 001–011 공통 |
| **§8 governance·§10 recompute·§12 serialization·§15 egress·§17 partition·§18 security·§21 evidence** | policy activation·독립 recompute·linearizable Intent Registry·final-egress 강제·partition fence·security 강제·replay engine | **not-Phase-1 (런타임 EV-L2/L3·+Security)** | spg(ADR-002-014)·독립 source allocation(§27 q3·+Security)·Intent Registry storage/consensus(§27 q6)·ADR-002-013/007/024·failure-domain(§27 q9)·ADR-002-016. iap는 순수 술어·모델만. | 002/005/008/010/012 (런타임) |
| **§27 open questions·§4 non-scope** (line 640–657·85–92) | canonical schema·evaluator·registry·numeric/invalidation bound·human-approval class | **not-Phase-1 (Phase-0/INSTANCE)** | 제품·알고리즘·수치·human class(ADR-002-015)는 §9.2 Phase-0. 전부 주입. | — |

---

## 2. 데이터 모델 계약

**표현 원칙**: 모든 아티팩트는 **pydantic v2 frozen 모델**(`ConfigDict(frozen=True, extra="forbid")`,
`tos.canonical.FrozenModel` REUSE)로 저작한다. **[#14 MAJOR-1 교훈 — 과대 주장 금지]**: `extra="forbid"`는
**모델 필드** 수준의 unknown/duplicate만 차단하며(§9 line 255 "cannot be patched"·§8 canonical schema의 스키마
수준 실현), request가 binding하는 **아티팩트 튜플의 잉여/결측/치환**은 `request_is_complete`·`exact_binding_holds`의
**구조 가드**(§5.1/§5.3, 양방향 집합 비교)가 거부한다 — `extra="forbid"`가 튜플 수준 excess를 막는다고 **주장하지
않는다**. 모든 age·bound는 **주입 opaque param**(하드코딩 수치 0), materiality는 `MaterialityVerdict`(UNKNOWN⇒MATERIAL).

### 2.0 소유권 골격 — iap는 canonical·ordering의 하류, dsl/capsule/ioc/venue/brokercap/spg의 하류, orthostate/are/rcl/liveauth/egress의 상류

`tos.iap`는 `tos.canonical`·`tos.ordering`(둘 다 core)만 import한다(**sibling edge 0**). dataflow상 iap는
**dsl `Proposal`·capsule Capsule/Snapshot·ioc envelope/command/`ApprovedIntentContract`·venue admissibility·
brokercap profile·spg policy의 하류**(전부 digest/identity scalar로 주입 소비)이자 **orthostate PROPOSED→APPROVED
전이·are `AggregateRiskDecision`·ioc `OrderConformanceProof`·liveauth `LiveAuthorization`의 상류**(승인 decision·
consumption record identity를 하류 형제가 scalar로 참조). produced/consumed seam은 **전부 scalar·digest 주입
(edge 0)**으로 실현되며 어떤 형제 타입도 REUSE하지 않는다(§0.4c — #14와의 distinction).

### 2.1 digest-bound / value / reference 분류 (총괄)

| 모델 | 분류 | 근거 |
|---|---|---|
| `TradingApprovalPolicy`(§5.1/§8) | **digest-bound `IndependentIdArtifact`(spg-governed)** | §5.1 line 100 "governed immutable policy"; §8 line 232 "immutable safety artifact under ADR-002-014". IAP가 digest 참조·spg 소유(ioc `OrderConstructionPolicy` 동형). |
| `ProposalApprovalRequest`(§5.3/§9) | **digest-bound `IndependentIdArtifact`(§0.4d 판단 지점)** | §5.3 line 108 "immutable canonical request"; §9 line 240 "canonical digest"·line 255 "immutable … new identity". substitution 탐지(§18 line 419)에 id⊥digest 권장; content-addressed(IdDerived) 대안 defensible. |
| `IndependentApprovalDecision`(§5.4/§11) | **digest-bound `IndependentIdArtifact`** | §5.4 line 114 "immutable signed or strongly bound"; §11 line 291 "signature or strong binding". decision_id ⊥ digest(same-id/diff-bytes·contradictory decision 탐지; are `AggregateRiskDecision` `records.py:451` 동형). **`APPROVE` grants nothing**(§11 line 294). |
| `ApprovalConsumptionRecord`(§5.5/§12) | **digest-bound `IndependentIdArtifact`(-023 소유·§3.5)** | §5.5 line 118 "authoritative immutable proof"; §12 line 318 binds decision/request/Intent/policy-generation/writer-epoch/txn-revision/receipt-time/invalidation/result. **grants no downstream authority**(§12 line 318). |
| `TradingApprovalGeneration`(§5.2) | **REUSE `tos.ordering`** | §5.2 line 104 "A monotonic fenced generation"; §17 line 405 stale-writer fence. `Ordering`/`compare_order`(신규 저작 없음). |
| `ApprovalAuthorityEffect`(§7/IAP-INV-005) | **plain-frozen all-false(`iap/_base.py`)** | rcl `RclAuthorityEffect`(`rcl/authority.py:19`; base `AllFalseAuthority` `rcl/_base.py:55`)·are `AggregateRiskAuthorityEffect`(`are/records.py:83`)·ioc `AllFalseConstructionAuthority`(`ioc/_base.py:54`) 동형; 어떤 True도 unconstructable(approval≠authority, §7·IAP-INV-005 line 150). template authority 10-flag(L72–82)와 정합. |
| `ApprovalResult`/`ConsumptionStatus`/`MaterialityVerdict` | **StrEnum(어휘)** | §2.2 verbatim. `ApprovalResult`는 `__bool__⇒TypeError`(truthy-sentinel 봉인). |

> **핵심 설계 결정 — 아티팩트는 immutable generation별 append-only(#12/#13/#14 상속)**: Policy/Request/Decision/
> ConsumptionRecord는 시간에 따라 **재발행·supersede**된다(§11 line 298 "A corrected or newer result is a new
> decision and explicitly supersedes the prior decision without erasing its evidence"·§20 recovery→fresh chain).
> 하나의 stable id에 mutable 내용을 담으면 정당한 재발행이 same-id/diff-bytes `CRITICAL_CONFLICT`로 **오탐**된다.
> ⇒ **각 generation은 fresh id를 가진 immutable 레코드**다. same identity + diff canonical digest ⇒ `CRITICAL_CONFLICT`
> (위조·request/decision substitution만); 정당한 재발행 ⇒ **새 identity + supersede 링크**(§11 line 298). generation
> 순서는 `tos.ordering`(§3.2). **decision·consumption record는 forward-only**: 미래 aggregate-risk/authority/capability
> identity를 covered에 담지 않는다(§1 line 21 "later gates remain independently mandatory"·non-cyclic).

### 2.2 어휘 (verbatim 전사 — 에라타 defect class 주의)

**(1) `ApprovalResult`** — ADR §1 line 17 verbatim "The decision result is `APPROVE`, `DENY`, or `UNKNOWN`"·§11
line 289. 3종: `APPROVE`("the exact request is eligible to be consumed once by the Intent Registry while every
binding remains current"·"non-authorizing business gate", §1 line 21·§11 line 294)·`DENY`("terminal for the
request", §11 line 296)·`UNKNOWN`("restrictive and requires new evidence or a new request", §11 line 296).
**`APPROVE`만 소비 자격값**이며 `DENY`/`UNKNOWN`는 **모두 denial**(§11 line 289 "never `APPROVE`"). **truthy-sentinel
임계(§0.4g/§4.7)**: 셋 다 non-empty StrEnum이라 `if result:`면 `DENY`/`UNKNOWN`가 truthy로 **fail-open** —
**구조적 봉인(#14 M1을 처음부터)**: `ApprovalResult.__bool__`는 **`TypeError`를 raise**한다(truthy-불가 타입 —
`if result:`/`bool(result)` = 런타임 오류, 침묵 fail-open 원천 제거). 소비 게이트는 **`result is ApprovalResult.APPROVE`
명시 비교**(보조 계약).

**(2) `ConsumptionStatus`** — §12 single-use consumption(line 302–320)의 **decision-consumption 차원**(orthostate
Intent 차원과 직교·§3.5). 2종: `ELIGIBLE`(unconsumed·current APPROVE decision — §12 line 307 "unconsumed")·
`CONSUMED`(single-use spent — §12 line 312 "one Approval Consumption Record"). 전이 `ELIGIBLE → CONSUMED`는
**단 1회**(§12 line 313 "duplicate identical commands return the same record … reject conflicting commands";
IAP-INV-006 line 154 "at most one immutable Intent"). **`bool` 아님** — 소비 게이트는 `status is ConsumptionStatus.ELIGIBLE`
명시(§4.7). **주의(비붕괴)**: `ConsumptionStatus`(decision 소비 상태) ≠ orthostate `IntentState`(Intent lifecycle,
`vocabulary.py:32`) — 별개 차원·별개 소유(§3.5).

**(3) `MaterialityVerdict`** — §5.7 line 124–126 "Material Approval Change … Unknown materiality is material"·§8
line 230. 3종: `MATERIAL`·`IMMATERIAL`·`UNKNOWN`. **소비 규칙: `UNKNOWN ⇒ MATERIAL 취급`**(fail-closed — §5.7
line 126 verbatim "Unknown materiality is material"). materiality가 invalidation closure 진입 조건이며(§5.4),
policy-owned(§8 line 230 "The proposer, approval evaluator, Intent Registry, consumer, or operator cannot
self-exempt a field or dependency").

**(4) 좌표/차원 어휘(비붕괴, §2.3)**: iap `ApprovalResult`/`ConsumptionStatus`(승인·소비 차원) ≠ orthostate
`IntentState`/`StateDimension`(Intent lifecycle, `vocabulary.py:32/158`) ≠ ioc `ConformanceResult`(conformance)
≠ rcl `CapacityState`(capacity). 토큰 겹칠 수 있으나(예: "APPROVED"/"DENIED") **별개 타입**이다. **핵심 봉합**:
`ApprovalResult.DENY`(decision-result, request terminal — §11 line 296)와 orthostate `IntentState.DENIED`(Intent
상태, APPROVED에서 분기 — `vocabulary.py:57`·`predicates.py:368`)는 **의미가 다르다**(§3.5).

### 2.3 아티팩트 covered + self-exclusion (설계 #4 §3.3 상속)

covered(digest preimage) = 각 아티팩트의 구조적 identity/scope/version/generation/class + (Request) §9 전 binding
필드(proposer/scope/artifact id+digest/generation/independent-fact/validity/consumption/authority)의 presence·값 +
(Decision) request id+digest·policy/generation·result·reason codes·approved-Intent-envelope ref·validity·invalidation
generation + (ConsumptionRecord) decision/request/Intent/policy-generation/writer-epoch/txn-revision/receipt/invalidation/result.
preimage 제외: `*_id`·`canonical_digest`·`canonicalization_version`·`status`(ArtifactStatus)·파생 역참조. **`_REQUIRED_COVERED`는
structural identity/scope/version/class + §9 필수 필드 presence만**(injected age/bound magnitude 제외 — Phase-1 null
bound에서 ISSUED 도달 가능; missing magnitude는 consuming 술어에서 fail-closed, #12–#14 §2.3 규율 상속). **decision·
consumption record는 covered에 미래 aggregate-risk/authority/capability identity를 담지 않는다**(§1 line 21 later
gates independent·non-cyclic).

---

## 3. canonical / ordering REUSE + sibling edge 0 + 형제 경계

### 3.1 canonical REUSE + `IdDerivedArtifact` 미채택(대부분)

4-아티팩트는 `tos.canonical.IndependentIdArtifact`·`DigestBoundArtifact`를 REUSE한다(상류 dsl `Proposal`·capsule은
이미 `IdDerivedArtifact`, IAP는 digest 참조만). canonicalizer는 `tos.canonical` registry + `EVL1ProvisionalCanonicalizer`
(`ev-l1-provisional-0`, `canonicalization.py:173`) REUSE, **신규 canonicalizer 없음**(프로덕션 canonical schema는
Phase-0 §9.2 — ADR §27 q1·q8). same-id/diff-bytes(request/decision substitution·중복 consumption) 탐지는
`classify_record_pair`(`record_pair.py:52`)·`RecordPairKind.CRITICAL_CONFLICT`(`record_pair.py:31`) REUSE.
**PROMOTE = 0건**(IAP는 numeric 없음 — `CanonicalDecimal`도 불요).

### 3.2 ordering REUSE (Trading Approval Generation append-only 순서)

`TradingApprovalGeneration`(§5.2 line 104 "A monotonic fenced generation")의 append-only 순서는 신규 저작하지
않고 `tos.ordering`(`Ordering`·`OrderingEvent`·`compare_order` `__init__.py:19`; 실측 `ordering/_ordering.py:38`
canonical만 의존)를 REUSE한다. **wall clock은 순서를 만들지 않는다**(§19 line 433 "Cross-host monotonic values are
never directly subtracted"와 정합) — iap는 clock을 읽지 않는다(§3.4; time validity는 주입 flag). newer generation이
older unconsumed decision을 fence(§17 line 405 "Only the current fenced … writer")하는 것은 순수 순서 비교이며
fence enforcement 런타임(profile bound)은 not-Phase-1(§6.5). light REUSE(core 의존, 신규 edge 아님).

### 3.3 REUSE 요약 표

| substrate | 결정 | 근거 |
|---|---|---|
| `FrozenModel`·`DigestBoundArtifact`·`IndependentIdArtifact`·`ArtifactStatus` | **REUSE(core `tos.canonical`)** | §3.1; 신규 없음 |
| `classify_record_pair`·`RecordPairKind` | **REUSE(core)** | §3.1; same-id/diff-bytes·contradictory decision·substitution |
| `EVL1ProvisionalCanonicalizer` | **REUSE(core)** | §3.1; 프로덕션 canonical schema는 Phase-0(§27 q1) |
| `Ordering`·`OrderingEvent`·`compare_order` | **REUSE(core `tos.ordering`)** | §3.2; Trading Approval Generation 순서·stale-writer fence |
| 4-아티팩트·all-false authority·어휘·12 술어 | **로컬 저작** | §0.4a/§2; ADR §5–§20 verbatim·approval-side |
| dsl `Proposal`·capsule·ioc envelope/command/`ApprovedIntentContract`·venue admissibility·brokercap profile·spg policy·orthostate intent-id/state·are/liveauth downstream | **미소유 — scalar/digest로만 소비/생산** | §3.4; 15 형제 seam |
| Intent 상태 전이·capacity·risk projection·action-flow·final egress·numeric bound | **미소유 — orthostate/rcl/are/ADR-002-022/런타임/INSTANCE 이연** | §3.5 |
| PROMOTE | **0건** | §3.1 |
| sibling edge | **0건**(#14의 1 edge와 대조 — §0.4c) | §3.4 |

### 3.4 dsl / capsule / ioc / venue / brokercap / spg / orthostate / are / liveauth 경계 — scalar·digest seam(edge 0) (중심, 코드 실측)

**(a) iap = scalar/digest producer/consumer(§0.4b).** iap는 15 형제를 **import하지 않고** scalar·digest로 seam한다.
seam 계약(compose) — **상대는 전부 이미 비준·구현됨**(venue=ADR-002-019 미구현 시 주입 slot). 핵심 seam:

- **dsl(proposal 상류·어휘 공동)**: iap `ProposalApprovalRequest`가 dsl `Proposal`을 `proposal_id`+`proposal_digest`
  scalar로 §9 line 242 binding. dsl `Proposal`(`proposal.py:68`, IdDerived)은 이미 account/instrument/direction/
  position_effect/quantity_basis + capsule bind를 carry하며 vocabulary가 "`PROPOSAL-APPROVAL-REQUEST-template.yaml`
  — an anchor, not a redefinition of ADR-002-020"(`proposal.py:7–8`)라 명시하고 approval을 "downstream/runtime"으로
  이연(`dsl/outcome.py:216`) — **IAP가 full request contract의 소유자**(§3.5). iap는 Proposal을 import하지 않는다.
- **capsule(context 입력 상류)**: iap `ProposalApprovalRequest`가 capsule `DecisionContextCapsule`(`capsule.py:170`,
  IdDerived)·`CriticalInputSnapshot`(`snapshot.py:96`, IdDerived) id+digest를 §9 line 244 binding. dsl `Proposal`이
  이미 capsule bind.
- **ioc(construction 상류·field set -020)**: iap `ProposalApprovalRequest`가 ioc `AuthorizedConstructionEnvelope`
  (`ioc/records.py:215`)·`CanonicalBrokerCommand`(`records.py:301`) id+digest를 §9 line 245 binding하고,
  `IndependentApprovalDecision`이 ioc `ApprovedIntentContract`(`records.py:142`)의 approved-Intent-envelope를 §11
  line 288·§12 line 309 "byte-for-byte or canonically equivalent" 비교한다. ioc `records.py:154–155` "Independent
  Approval + immutable Intent Registration remain ADR-002-023 (IAP); this models the approved field set, not the
  registration" — **-020/-023 분할의 코드 확증**(§3.5). ioc는 IAP `approval_identity`를 scalar로 참조
  (`records.py:199/294`) — 양쪽 미import(acyclic).
- **venue(admissibility 상류)**: iap `ProposalApprovalRequest`가 Venue Constraint Snapshot·Order Admissibility
  Decision(ADR-002-019) id+digest를 §9 line 246 binding. 미구현이면 주입 slot(scalar).
- **brokercap(capability 상류)**: iap가 broker ambiguity(§16·IAP-EV-011)·capability를 **injected result**로 소비하고
  brokercap `BrokerCapabilityProfile`(`brokercap/records.py:305`) digest를 §9 line 247 binding.
- **spg(policy governance 상류)**: iap가 `TradingApprovalPolicy`를 spg-governed member(§8 line 232·`BundleMemberKind`
  `spg/vocabulary.py:180`)로 digest 참조·소비하되 governance/activation을 하지 않는다.
- **orthostate(Intent 차원 — 상호 참조·edge 0)**: iap `ApprovalConsumptionRecord`가 orthostate `intent_identity`
  (`orthostate/records.py:93`, `str|None`) scalar를 §12 line 318 binding. **PROPOSED→APPROVED 전이는 orthostate
  `intent_transition_allowed`(`predicates.py:432`)·`_INTENT_TRANSITIONS`(`predicates.py:364`) 소유** — iap는 그
  전이를 재저작하지 않고 `IntentState`(`vocabulary.py:32`) token을 scalar로 참조(§3.5).
- **are/liveauth(decision 하류)**: are `AggregateRiskDecision.approval_identity`(`are/records.py:348`)·liveauth
  `LiveAuthorization.approval_record_identity`(`liveauth/records.py:112`)·`LiveAuthorizationTransitionRecord.approval_record_id`
  (`records.py:214`)가 IAP decision/consumption identity를 **scalar로 참조**(§13 line 346 chain 하류). iap는
  are/liveauth를 import하지 않는다("approval ≠ authorization" `liveauth/records.py:188` 확증).

**(b) 타입 정합 + fail-closed 정합 + truthy-sentinel 봉합.** iap 소비 signature는 전부 `str|None`(id/digest)·
`bool|None`(injected capability)·enum token이라 `None`⇒fail-closed. iap 산출 `ApprovalResult`는 `APPROVE`만 소비
자격값 — **소비 게이트는 `is APPROVE` 명시 비교**(§4.7). **polarity 봉합(#6 fail-open REJECT 교훈)**: producer는
결코 "미판정 ⇒ APPROVE/True/ELIGIBLE"로 새지 않는다(§4.2). **truthy-sentinel 봉합(#14 M1을 처음부터)**: `ApprovalResult`
반환 술어의 소비 계약은 `if result:` 금지·`is APPROVE` 명시이며 `__bool__⇒TypeError` 구조 봉인.

**(c) composition(런타임 배선) = caller 소관**: iap decision/consumption record를 orthostate transition·are·rcl·
final-egress로 배선하는 **런타임**은 **미래 Independent Approval Service / Intent Registry 런타임**(EV-L2/L3)이
한다. Phase 1은 #12/#13/#14의 seam 이연과 **동형으로 런타임 배선을 이연**한다. 특히 §12 atomic transaction(IAP
consumability 판정 + orthostate PROPOSED→APPROVED 전이 + ConsumptionRecord write를 one linearizable txn)은 런타임
(§6.2).

**(d) seam cross-check = MANDATED(test-only)**: Phase 1은 **test-only** 모듈(`tos/tests/iap/test_seam_dsl.py`·
`test_seam_ioc.py`·`test_seam_orthostate.py`·`test_seam_capsule.py`)에서 iap·(각 상대)를 **둘 다 import**해 iap
산출/소비의 **타입·polarity·fail-closed**가 상대 signature 기대와 **일치함을 assert**한다(예: iap `ProposalApprovalRequest`
proposal ref = dsl `Proposal` `proposal_id`/digest; iap decision approved-envelope 비교 = ioc `ApprovedIntentContract`
scalar; iap `ApprovalConsumptionRecord` intent ref = orthostate `intent_identity`; PROPOSED→APPROVED 전이 판정은
orthostate `intent_transition_allowed`가 소유함을 assert — iap는 재저작 안 함). **이 테스트는 package edge가 아니다**
— 테스트 import는 §7.1 `import tos.iap` package-closure에 **계상되지 않으므로** 전 형제 seam의 edge-0은 유지된다
(#12/#13/#14 동형).

**(e) iap는 transition/mutate/transmit/issue하지 않는다(§7·IAP-INV-005).** iap는 결정 artifact(request·decision·
consumption record)만 생산하고 Intent 전이·capacity mutation·egress transmit·authority issue·live-scope set 메서드가
**부재**하다(§4.6). 소비 authority(orthostate transition·are decision·rcl commit·final egress)가 실제 action을
gate한다.

**(f) acyclic(정확형)**: iap↛{15 형제} ∧ 형제↛iap(하류 형제는 IAP identity를 **scalar로만** 참조 — ioc `records.py:199`·
are `records.py:348`·liveauth `records.py:112`; 상류 형제는 IAP가 **scalar로만** 소비). iap의 유일 import는
canonical·ordering(core). **sibling edge 0** — #14 ioc→rcl 1 edge와 대조되는 본 문서 distinction(§0.4c).

### 3.5 소유권 분할표 — iap가 소유 / 형제에서 소비·생산 (본 문서 최대 함정 지대, #11–#14 §3.5 상속)

> **소유권 분할 명시(#8·#11–#14 교훈 — cross-section 혼동 선제 봉합)**: ADR-002-023은 **automated independent
> proposal approval + exact-decision binding + single-use consumption fencing**만 결정하며(§4 line 74–83)
> **Intent 상태 전이(orthostate/ADR-002-005)·capacity(rcl)·aggregate risk(are)·action-flow(ADR-002-022 AFG)·
> venue admissibility(ADR-002-019)·broker capability(ADR-002-004)·final-egress 강제(ADR-002-013)·human approval
> (ADR-002-015)·evidence replay(ADR-002-016)를 소유하지 않는다**. 함정: iap가 orthostate의 Intent 전이·rcl의
> capacity·are의 risk decision을 재저작하면 권위 중복(#8 lesson). 아래 표가 경계를 코드 실측으로 고정한다.

| ADR 조항/개념 | iap 소유 (Phase 1) | 형제 소유 (재저작 금지) | seam 방향(실측) |
|---|---|---|---|
| §9 Proposal Approval Request | `ProposalApprovalRequest`(§5.3) — full request contract | dsl `Proposal` identity(`proposal.py:68`, IdDerived·PROPOSAL-APPROVAL-REQUEST anchor `proposal.py:7`) | dsl `Proposal` proposal_id/digest → iap binding(§9 line 242); 어휘 -020/-023 공동 |
| §11 Independent Approval Decision | `IndependentApprovalDecision`·`ApprovalResult`·`approval_decision`(§5.2) | (없음 — approval decision은 IAP 고유) | request id+digest → decision binding(§11 line 284); id⊥digest(§0.4d) |
| §8 Approved Intent field set | (미소유 — ioc가 -020 소유) | **ioc `ApprovedIntentContract`(`ioc/records.py:142`, -020)** | iap decision이 ioc approved-envelope를 §11 line 288 binding·§12 line 309 비교; ioc `records.py:154–155` 확증 |
| §12 single-use consumption 판정 | `ConsumptionStatus`·`consumption_transition`·`ApprovalConsumptionRecord`(§5.5/§6.2) | (decision-consumption 차원은 IAP 고유) | ConsumptionRecord가 decision/request/intent-id/writer-epoch binding(§12 line 318) |
| §12 Intent 상태 전이 (PROPOSED→APPROVED) | (미소유 — orthostate 소유) | **orthostate `IntentState`·`intent_transition_allowed`(`vocabulary.py:32`·`predicates.py:432`)** | iap consumability 판정 + orthostate 전이 = runtime atomic txn(§3.4 (c)); iap는 `intent_identity` scalar 참조 |
| §13 exact binding chain | `exact_binding_holds`(§5.3) — chain digest 정합 | chain 각 노드(capsule/proposal/ioc/venue/are/rcl/ioc-proof)는 형제 소유 | 전부 id+digest scalar → iap 판정; iap는 상대 미import |
| §14 invalidation closure | `invalidation_closure`·`MaterialityVerdict`(§5.4) — 순수 그래프 도달성 | 실 propagation·generation registry(§27 q5)는 런타임 | 그래프 노드는 주입 id 집합; 순수 폐포 계산 |
| §7/§13 no widening/union·authority | `no_widening_no_union`·`ApprovalAuthorityEffect` all-false(§6.3) | rcl `RclAuthorityEffect`(`rcl/authority.py:19`; base `AllFalseAuthority` `rcl/_base.py:55`)·final egress confinement(ADR-002-013) | iap all-false 생산; credential/route confinement 런타임 |
| §15 final-egress currentness | `active_egress_currentness`(§6.4) — 술어 계약만 | final egress 실 강제·capability claim·SEND_STARTED(ADR-002-013/007/024) | iap는 currentness 요구 명세; 강제·claim은 런타임 |
| §16 UNKNOWN/protective/human | `unknown_confines`(§5.5) — label≠bypass·capacity≠offset | human approval(ADR-002-015)·protective classification(ADR-002-001)·capacity(rcl) | iap는 label/priority/capacity가 permission 못 만듦 술어; classification은 protective |
| §16/§11 economic continuity | `economic_effect_outlives`(§5.6) | broker ACK/FQP 의미(ADR-002-004)·capacity release(rcl) | iap 술어; broker 의미·capacity는 형제 |
| §17 partition/stale-writer | `stale_generation_fenced`·conflicting⇒UNKNOWN(§6.5) | 실 partition·writer-fence·split-brain(런타임 EV-L2/L3) | iap 순수 순서 비교; enforcement 런타임 |
| §20 recovery/non-revival | `recovery_revives_nothing`(§6.6) | ADR-002-017 Recovery Barrier·re-arm workflow(런타임) | iap 술어; barrier enforce 런타임 |
| §21 evidence | (레코드 substrate만) | ADR-002-016 replay engine·custody | iap는 decision/consumption 레코드; replay는 하류 |

> **핵심 판정 1 — `ApprovalResult.DENY` ≠ orthostate `IntentState.DENIED`(본 문서 최대 리스크 봉합)**: orthostate는
> `PROPOSED → DENIED`를 **의도적으로 금지**한다(`predicates.py:440–458` "`PROPOSED -> DENIED` is NOT allowed";
> `DENIED` branches from `APPROVED` — `vocabulary.py:42–44`·`_INTENT_TRANSITIONS` `predicates.py:368`). 이는 IAP와
> **모순되지 않는다**: IAP `ApprovalResult.DENY`는 **decision-result**로 request에 대해 terminal이며(§11 line 296)
> **소비를 일으키지 않는다** ⇒ Intent는 그대로 `PROPOSED`에 머문다(전이 없음). orthostate `IntentState.DENIED`는
> **APPROVED 이후의 denial**(aggregate-risk/capacity가 approval 성공 후 거부 — `vocabulary.py:43` "Approval +
> Aggregate-Risk policy granted"의 실패 분기)이다. ⇒ **approval DENY는 orthostate 전이를 전혀 유발하지 않고**,
> orthostate DENIED는 IAP 밖(are/rcl 하류)에서 온다. 이 구분을 흐리면 "PROPOSED→DENIED가 필요하다"는 **오판**으로
> 이어진다(리뷰어 공격 지점 §10.2 (ii)).

> **핵심 판정 2 — `ApprovalConsumptionRecord` 소유(§10.2 판단 지점)**: §5.5는 이를 "the Intent Registry's
> authoritative immutable proof"(line 118)로 정의한다. **권장: IAP가 `ApprovalConsumptionRecord` 모델 + single-use
> consumption 판정(`consumption_transition`)을 소유**(ADR-002-023 §5.5/§12 계약 — -023 코히전 유지), orthostate가
> Intent 상태 전이(`StateTransitionRecord`·`intent_transition_allowed`)를 소유. 두 레코드는 `intent_identity`+
> `decision_id` scalar로 상호 참조하고 런타임 Intent Registry가 atomic txn으로 묶는다(§3.4 (c)). **대안(기각)**:
> orthostate가 ConsumptionRecord를 Intent Registry 모델의 일부로 소유 — -023 계약을 두 패키지로 쪼개 권위 분산.
> **§10.2 운영자 판단 지점**: IAP 소유(권장) vs orthostate 소유. orthostate가 `StateDimension`에서 Capacity를
> rcl.CapacityState로 위임하듯(`vocabulary.py:162`) decision-consumption 차원을 tos.iap `ConsumptionStatus`로
> 위임하는 cross-package dimension도 orthostate 측 선택으로 가능하나, 그것은 orthostate 결정이지 IAP 결정이 아니다
> (Phase-1 IAP는 edge 0·scalar 참조).

---

## 4. 불변식

모두 frozen 모델 구성-불변식(구성 실패) 또는 순수 술어(property)로 실현한다. **앵커는 IAP-INV-001..015(§6)·
IAP-AC-001..012(§25)·§-clause·SAFE-###**이며 **새 시리즈를 창작하지 않는다**(§0.4f). **fail-closed discipline**:
미증명/불일치/None/stale/unknown/incomplete에 대한 술어는 절대 vacuous permissive/APPROVE/ELIGIBLE가 되지 않으며,
소비 자격은 *양성 증명*을 요구하고, 각 가드에 **both-ways canary**(가드가 실제로 발화함 + 정당 통과를 막지 않음)를 붙인다.

### 4.1 complete exact request 중앙 불변식 (core — ADR §9; IAP-INV-001; IAP-AC-001)

**중앙 결정**: `request_is_complete`는 §9 line 238–251 전 binding 필드가 present ∧ non-wildcard ∧ non-empty ∧
non-stale ∧ non-conflicting일 때만 통과. IAP-INV-001 line 134 verbatim "Approval evaluates one complete immutable
request. Omission, wildcard, ambiguity, hidden default, substitution, union, patch, or partial refresh is not the
approved request." 실현(구조적):

1. **permissive 기본값 부재**: §9 전 필드(request identity/nonce/digest/predecessor/cause/generation·proposer·
   scope[env/cell/portfolio/account/instrument/contract/venue/broker/route/action-class/mode]·direction/position-effect/
   quantity/unit/multiplier/currency/price-constraints/expiration/max-envelope·capsule id+digest·construction envelope+
   command id+digest·venue snapshot+admissibility id+digest·전 governed policy id+digest·전 generation·required
   independent facts+validation paths+common-mode declarations+residual risks+scope reductions·validity+max-age+
   consumption rule+invalidation set·explicit no-authority declaration)가 완비될 때만 통과. 한 필드라도 absent/
   empty/wildcard/unknown/stale/conflicting/unverifiable ⇒ **불완전 ⇒ APPROVE 불가**(§9 line 253 verbatim "An
   absent, empty, wildcard, unknown, stale, conflicting, or unverifiable required scope or maximum is incomplete
   and cannot yield `APPROVE`"). "assume-complete" 경로 부재(#6 fail-open REJECT 교훈).
2. **immutable·no-patch(§9 line 255)**: "The request is immutable. Any field change creates a new identity and
   restarts approval. Requests cannot be patched, partially refreshed, intersected, unioned, or widened." ⇒ 필드
   변경 = 새 identity(재발행, §2.1). partial refresh/union/widen 시도 = 다른 request(정합 깨짐).
3. **template 앵커(실측)**: `PROPOSAL-APPROVAL-REQUEST-template.yaml`의 fail-closed 기본값(`required_scope_complete:
   false` L17·`action_class: UNKNOWN` L29·`operating_mode: UNKNOWN` L30·authority 10-flag all-false L72–82·
   `single_use: true`/`exact_intent_only: true` L70–71)이 완비-필요 구조의 verbatim 앵커.

**canary(both-ways)**: (a) 결측/빈/wildcard/UNKNOWN action-class/UNKNOWN mode 필드(IAP-AC-001)·`required_scope_complete=false`
⇒ 불완전(가드 발화; §25 IAP-AC-001 "cannot yield or preserve `APPROVE`"); (b) 전 §9 필드 present·non-wildcard·
정합 ⇒ complete(양성 side — 정당한 request를 막지 않음). **truthy-sentinel canary**: 불완전 판정이 `ApprovalResult`
(DENY/UNKNOWN)로 반환될 때 truthy임을 assert + `is APPROVE` 게이트가 이를 reject함을 assert(§4.7).

### 4.2 deterministic restrictive decision 중앙 불변식 (core — ADR §11; IAP-INV-003; IAP-AC-003)

**중앙 결정**: `approval_decision`은 동일 (완비 input set + policy + generation) ⇒ 동일 result. IAP-INV-003 line
142 verbatim "The same complete input set under one policy and generation yields one deterministic result.
Missing, stale, conflicting, unverifiable, unsupported, or unknown input yields `DENY` or `UNKNOWN`, never
`APPROVE`." 실현:

1. **결정론(순수 함수)**: `approval_decision(request, policy, generation, injected_facts) -> ApprovalResult`는
   순수 함수 — hidden clock/randomness/locale/env/mutable-cache/network/"latest"-registry/fallback 부재(§10 line
   274 "Recalculation with the same corrupted implementation is not validation"·§9 line 267 permissive rounding/
   coercion/fallback/hidden default 금지). 동일 입력 두 평가 ⇒ 동일 result.
2. **restrictive default(§11 line 289)**: missing/stale/conflicting/unverifiable/unsupported/unknown ⇒ DENY/UNKNOWN,
   **never APPROVE**. `APPROVE`는 non-authorizing business gate — "the exact request is eligible to be consumed
   once … while every binding remains current. It is not equivalent to `AUTHORIZED_FOR_CAPACITY`, capacity
   commitment, Live Authorization, capability issuance, or transmission"(§11 line 294).
3. **DENY terminal·UNKNOWN 승격 불가(§11 line 296)**: "`DENY` is terminal for the request. `UNKNOWN` is
   restrictive and requires new evidence or a new request; repeated evaluation, timeout, majority vote, unused
   capacity, human preference, prior success, or an expected broker rejection cannot promote it." ⇒ UNKNOWN을
   재평가/timeout/majority/capacity/human-pref/prior-success/expected-rejection로 APPROVE 전환 = 금지(§5.5·§6.5).
4. **id⊥digest·supersede(§11 line 298)**: decision는 편집 불가; corrected/newer = 새 decision + supersede(§2.1).
   same-id/diff-bytes ⇒ `CRITICAL_CONFLICT`(§3.1).

**canary(both-ways)**: (a) 동일 입력 두 평가의 result 불일치(비결정성 주입)·missing/stale/conflicting input이
APPROVE 산출(IAP-AC-003) ⇒ property 실패/거부(가드 발화; §25 IAP-AC-003 "without permissive fallback"); UNKNOWN을
majority/capacity로 promote 시도 ⇒ 거부; (b) 동일 완비 입력 ⇒ 동일 APPROVE(양성 side). **구조 봉인 canary**:
`bool(ApprovalResult.DENY/UNKNOWN/APPROVE)` ⇒ `TypeError`(§4.7).

### 4.3 exact binding chain 중앙 불변식 (core — ADR §13; IAP-INV-004; IAP-AC-004)

- **transitive digest 정합(IAP-INV-004 line 146)**: `exact_binding_holds(chain) -> ApprovalResult`는 §13 line
  328–342 체인의 **인접 쌍 id·digest 참조가 전부 정합**할 때만 통과 — "The decision binds the exact Capsule,
  proposal, construction envelope, candidate command, venue snapshot and decision, policies, generations, scope,
  software, deployment, environment, account, broker, route, and validity"(IAP-INV-004 line 146).
- **어느 substitution도 무효화(IAP-AC-004 line 585)**: "Account, instrument, direction, quantity, unit, price,
  Capsule, venue decision, construction, broker, route, environment, policy, generation, software, or deployment
  substitution invalidates the decision." ⇒ 한 노드라도 참조 불일치 ⇒ binding 끊김 ⇒ 무효.
- **no downstream widening(§13 line 344)**: "No downstream stage may use approval to widen, repair, reinterpret,
  refresh, or reconstruct a more favorable proposal. Later gates may only narrow or deny." ⇒ chain은 forward-only·
  narrow-or-deny.
- **proof binding(§13 line 346)**: "The Order Conformance Proof SHALL include the exact approval decision and
  consumption-record identities" — ioc proof가 IAP decision/consumption identity를 binding(**하류 미래 배선** —
  `OrderConformanceProof`[records.py:357]는 해당 필드를 아직 보유하지 않음, §9.2 item 14; 현행 코드 앵커는
  `ApprovedIntentContract.approval_identity`[:199] — v1.1 MAJOR-1 정정).
- **canary(both-ways)**: (a) chain 한 노드 substitution(account/venue/command/policy/generation)·결측 링크·잉여
  치환 링크(IAP-AC-004) ⇒ 무효(가드 발화·양방향 집합 비교 #14 MAJOR-1); (b) 전 노드 정합 ⇒ bound(양성 side).

### 4.4 invalidation dependency closure 중앙 불변식 (core — ADR §14; IAP-INV-008; IAP-AC-007)

- **complete closure(§14 line 361·IAP-INV-008 line 162)**: `invalidation_closure(graph, trigger) -> frozenset[node]`는
  material trigger에서 도달 가능한 **모든** dependent node를 계산 — "The system SHALL compute the complete
  dependency closure across requests, decisions, consumption records, Intents, risk/flow decisions, commitments,
  proofs, authorities, capabilities, pending attempts, egresses, and protection"(§14 line 361). 순수 그래프
  도달성(transitive reachability) — L1-decidable(deterministic simulation).
- **부분 폐포 = fail-open(catastrophic)**: 폐포가 한 dependent라도 누락하면 그 노드가 무효화를 탈출 ⇒ 안전 위반.
  **불확정 edge/unknown node ⇒ 확장(reachable로 취급)** — under-count 금지(#14 MAJOR-1 안전 방향). `MaterialityVerdict`
  UNKNOWN⇒MATERIAL(§5.7 line 126)이 진입 조건.
- **before/after consumption(§14 line 363)**: "Before consumption, invalidation makes the decision ineligible.
  After consumption but before future send, it denies dependent new-risk use." ⇒ 폐포는 unconsumed decision(ineligible)·
  consumed lineage(future-use block) 모두 덮되 economic effect는 보존(§5.6).
- **absence ≠ currentness(§14 line 365)**: "An invalidation event may be evidence, but absence of the event is not
  proof of currentness." ⇒ 무효화 이벤트 부재를 currentness로 추론 금지(§6.4와 정합).
- **canary(both-ways)**: (a) material trigger가 전 dependent closure에 도달(no escape)·불확정 edge ⇒ 확장·absence를
  currentness로 오인(IAP-AC-007) ⇒ 가드 발화(§25 IAP-AC-007 "blocks every affected future new-risk use"); (b)
  **증명된 disconnected node는 spurious 무효화 안 됨**(availability side — over-invalidation은 안전하나 가용성
  결함). tie-break 불확정 ⇒ 확장(안전 우선).

### 4.5 UNKNOWN confinement + no-widening + non-revival 불변식 (core+predicate 혼합 — ADR §16/§7/§20; IAP-INV-005/007/010/013/014)

- **UNKNOWN confinement(IAP-INV-010 line 170·§16 line 391)**: `unknown_confines(...)`는 UNKNOWN approval·input·
  common-mode·generation·consumption·invalidation 상태 ⇒ ordinary new risk 차단. verbatim "UNKNOWN approval, input,
  common-mode status, consumption state, or invalidation state blocks ordinary new risk and cannot be offset by
  unused capacity"(IAP-INV-010)·"Available RCL capacity cannot convert uncertainty into permission"(§16 line 391).
- **label/human ≠ bypass(IAP-INV-013 line 182·§16 line 393)**: "Human approval, emergency priority, exit, hedge,
  close, reduce-only, or protective labels do not substitute for this approval or create protective authority or
  reserve." ⇒ label/priority가 approval을 대체·protective reserve 창조 불가(§5.5).
- **no widening/union(IAP-INV-007 line 158)**: "A narrower decision, multiple decisions, or a later more favorable
  fact cannot be combined to approve broader or different scope." ⇒ union/widen 금지(§6.3).
- **all-false authority(IAP-INV-005 line 150·§7)**: `ApprovalAuthorityEffect`의 어떤 True도 unconstructable
  (rcl `RclAuthorityEffect` `authority.py:19`[base `AllFalseAuthority` `_base.py:55`]·are `AggregateRiskAuthorityEffect` `records.py:83`·ioc
  `AllFalseConstructionAuthority` `_base.py:54` 동형). "Approval cannot mutate capacity, create headroom, issue
  authority, classify protection, transmit, clear HALT, or re-arm"(IAP-INV-005 line 150). **canary**: `mutates_capacity=True`/
  `issues_authority=True` 구성 시도 ⇒ ValidationError.
- **non-revival(IAP-INV-014 line 186·§20 line 447)**: `recovery_revives_nothing(...)`는 **무조건 True** — "Restart,
  replay, restore, rollback, source recovery, approval-service recovery, or Intent Registry recovery cannot revive
  a decision, Intent permission, authority, or live state"(IAP-INV-014)·"There is no automatic re-arm"(§20 line
  447). spg `expiry_revives_nothing`·are `non_revival_holds`·ioc `recovery_revives_nothing` 동형(§6.6).

### 4.6 economic-continuity + all-false authority 불변식 (core+predicate — ADR §16/§19/§11/§7; IAP-INV-011/005)

- **economic-continuity(IAP-INV-011 line 174·§16 line 397·§19 line 437)**: `economic_effect_outlives(...)`는
  expiry/invalidation/consumption/revocation/loss of approval이 order/exposure/UNKNOWN/capacity를 **erase·release
  못 함**을 명문화. verbatim "Expiry, invalidation, consumption, revocation, or loss of approval never proves
  non-acceptance, final quantity, cancellation, zero exposure, or releasable capacity"(IAP-INV-011)·"Approval
  expiry, invalidation, revocation, denial, or service outage does not cancel broker state or release RCL
  capacity"(§16 line 397)·"Expiry prevents future consumption or send. It does not expire an Intent's history,
  broker effect, order, fill, exposure, UNKNOWN state, or capacity commitment"(§19 line 437).
- **broker ambiguity(§16 line 397)**: "Missing ACK is not proof of broker non-acceptance. Cancel ACK is not Final
  Quantity Proof." ⇒ missing-ACK ⇒ potentially-live·capacity-covered; cancel-ACK ≠ FQP(broker 의미는 +Broker·§5.6).
- **all-false authority(§4.5 참조)**: `ApprovalAuthorityEffect` all-false는 IAP가 approval을 economic authority로
  전환 못 함의 구조적 봉인(IAP-INV-005). **canary**: expired approval ⇒ future send 차단이나 capacity release 안 됨
  (가드 발화); missing ACK ⇒ potentially-live·capacity-covered(양성 side: 정당한 economic-continuity 보존).

### 4.7 ∅-공허 fail-closed + truthy-sentinel 소비 계약 (양방향 명시 — #10/#12 ∅-void·#14 M1 truthy-sentinel 교훈)

**(가) ∅-공허 양방향**: 빈 입력의 **모든 방향**을 명문화한다. IAP 금지 동사(§1·IAP-INV): **default/wildcard/
hidden-default**(IAP-INV-001)·**substitute/patch/union/widen**(IAP-INV-001/007)·**coerce/permissive-fallback**
(IAP-INV-003·§10 line 267)·**promote-UNKNOWN**(IAP-INV-010·§11 line 296)·**create-headroom/mutate-capacity/
issue-authority**(IAP-INV-005)·**expire/release-capacity**(IAP-INV-011)·**revive/re-arm**(IAP-INV-014)·**infer-currentness-from-absence**
(IAP-INV-009·§14 line 365·§15 line 381).

| 빈 입력 | 금지 방향(vacuous permissive 차단) | 허용 방향(양성 side) | 근거 |
|---|---|---|---|
| **absent/empty/wildcard required request 필드** | 결측/빈/wildcard ⇒ 불완전 ⇒ APPROVE 불가 | 전 §9 필드 present·non-wildcard ⇒ complete | §9 line 253 verbatim "is incomplete and cannot yield `APPROVE`" |
| **missing/empty required scope/maximum** | missing/empty/unknown ⇒ 불완전, **NEVER zero/wildcard/unconstrained** | exact bounded scope ⇒ eligible | §9 line 253; ioc §14 line 374 동형(required-authority-scope restrictive) |
| **빈 의존 집합의 invalidation closure** | 빈 그래프 ⇒ "nothing to invalidate" 아님 ⇒ 최소 폐포={trigger}·불확정⇒확장 | 완비 그래프 ⇒ 정확 도달성 폐포 | §14 line 361 "complete dependency closure"·line 365 absence≠currentness |
| **UNKNOWN result + available capacity** | UNKNOWN + capacity ⇒ 여전히 차단(offset 금지) | APPROVE + current binding ⇒ 소비 자격 | §16 line 391·IAP-INV-010 line 170 "cannot be offset by unused capacity" |
| **재발행/재평가 후 old decision 참조** | recovery/replay ⇒ revive 안 됨 | fresh chain + governed re-arm ⇒ 새 approval | §20 line 447·IAP-INV-014 line 186 |

**양방향 규율**: 각 빈-입력 가드는 (a) 금지 방향(가드 발화 canary)과 (b) 허용 방향(정당 통과 canary)을 **둘 다**
property로 검증한다(§7). vacuous-APPROVE도 vacuous-denial(정당 request를 막음)도 결함이다 — 전자는 안전 위반,
후자는 가용성 위반(#12 both-ways 교훈). **동사별 전용 canary**: default/wildcard/substitute(§5.1)·coerce(§5.2)·
union/widen(§6.3)·promote-UNKNOWN(§5.5)·headroom(§6.3)·expire(§5.6)·revive(§6.6)·infer-from-absence(§6.4) 각각
named canary. **양방향 집합 비교(#14 MAJOR-1 교훈)**: `exact_binding_holds`(§4.3)·`invalidation_closure`(§4.4)의
집합 비교는 **양방향** — 결측(binding 끊김·closure 탈출)과 잉여/치환(다른 chain·spurious node) 모두 검사. **과대
주장 금지**: `extra="forbid"`는 모델 필드 unknown/duplicate만 차단하며 아티팩트 튜플의 excess/치환은 구조 술어가
잡는다고 정확히 서술(§2.0 — extra="forbid"가 튜플 excess를 막는다고 주장하지 않음).

**(나) truthy-sentinel 소비 계약(#14 M1 교훈을 처음부터 — 임계)**: bool 아닌 안전 술어의 소비를 명문화한다.

- **`ApprovalResult` 반환 술어**(`approval_decision`·`request_is_complete`·`exact_binding_holds`): `APPROVE`/`DENY`/
  `UNKNOWN`는 **모두 non-empty StrEnum**이라 `if result:`·`if result == True:`면 `DENY`/`UNKNOWN`가 **truthy로
  fail-open**(catastrophic). ⇒ **구조적 봉인(#14 M1을 처음부터 채택 — 사후 리뷰 지적 전에)**: `ApprovalResult`는
  **`__bool__`가 `TypeError`를 raise하는 truthy-불가 타입**으로 저작한다 — 미래 소비자의 `if result:` 관용구 오용이
  침묵 통과가 아니라 **런타임 오류로 즉시 노출**된다(producer[iap] 범위 내 유일한 구조적 방어 — #14 교훈의 구조적
  상향). 보조로 **소비 게이트 계약: `result is ApprovalResult.APPROVE`(명시 positive equality)만 통과, 그 외 전부
  denial.** bare bool 반환 금지(§5).
- **`ConsumptionStatus` 반환 술어**(`consumption_transition`): `ELIGIBLE`/`CONSUMED`도 non-empty StrEnum — 소비
  게이트는 `status is ConsumptionStatus.ELIGIBLE` 명시(§6.2). `ApprovalResult`와 동일 `__bool__⇒TypeError` 봉인.
- **`bool|None` 반환 술어**(`no_widening_no_union`·`active_egress_currentness`·`stale_generation_fenced`·
  `recovery_revives_nothing` 등): `None`(미판정)은 falsy지만 **`is True` 명시 비교**로 소비(`is not True ⇒ reject`) —
  spg `semantic_validation` `predicates.py:466` `is not True⇒reject`·ioc `bool|None` `is True` 동형. `if x:` truthy 금지.
- **canary**: 각 술어에 대해 (i) 안전값이 아닌 반환(`DENY`/`UNKNOWN`/`CONSUMED`/`None`/`False`)이 truthy/falsy edge에서
  **게이트가 reject함을 assert**, (ii) 안전값(`APPROVE`/`ELIGIBLE`/`True`)만 통과함을 assert, (iii) **구조 봉인 회귀**:
  `bool(r)`이 `ApprovalResult`·`ConsumptionStatus` 각 값에 대해 `TypeError`를 raise함을 assert(+`is` 비교는 정상
  동작 양성측). 이 계약은 §5·§6 전 술어에 부착되고 §7 property·seam test로 회귀.

---

## 5. core 술어 — request/decision/binding/closure/UNKNOWN/continuity (IAP-EV-001/003/004/007/009/011 substrate, L1 슬라이스)

**핵심 난제**: 승인 gate를 **순수 함수**로 저작하되, (i) policy·source·registry·capability·age bound를 **주입
판정/파라미터**로 두어 하드코딩 값·registry를 배제하고(§8), (ii) fail-closed(§4)를 **구조로** 지키며(permissive
기본·vacuous 부재·truthy-sentinel 봉합), (iii) substitution/union/widen/coerce/promote를 **most-restrictive**로
처리한다. 각 술어는 §1 core 6행(IAP-EV-001/003/004/007/009/011)의 L1 슬라이스를 저작하나 **어떤 IAP-EV도 닫지
않는다**(`/3`·`+Security`·`+Broker` 잔여).

### 5.1 request_is_complete (§9; IAP-EV-001 substrate, core L1 슬라이스)

`request_is_complete(request: ProposalApprovalRequest, policy: TradingApprovalPolicy) -> ApprovalResult`:

- **complete only when**: §9 line 238–251 전 binding 필드(§4.1 목록)가 present ∧ non-wildcard ∧ non-empty ∧
  non-UNKNOWN(action-class/mode) ∧ `required_scope_complete=True`일 때만 통과 후보; 한 필드라도 absent/empty/
  wildcard/unknown/stale/conflicting/unverifiable ⇒ `DENY`/`UNKNOWN`(§9 line 253).
- **materiality policy-owned(§8 line 230)**: 어느 필드가 required인지는 policy 소유 — "The proposer, approval
  evaluator, Intent Registry, consumer, or operator cannot self-exempt a field or dependency. Unknown materiality
  is material." IAP는 policy가 선언한 required set을 주입받아 검사(self-exempt 경로 부재).
- **immutable(§9 line 255)**: 필드 변경 = 새 identity(재발행); patch/union/widen 시도 = 다른 request(§4.1).
- **반환·소비 계약**: `ApprovalResult`(bare bool 아님) — 소비 게이트는 `result is ApprovalResult.APPROVE`(§4.7).
- **canary(IAP-AC-001, both-ways)**: (a) omitted/defaulted/wildcard/ambiguous/partially-refreshed/patched/unioned/
  substituted 필드(IAP-AC-001)·`required_scope_complete=false`·`action_class=UNKNOWN` ⇒ 불완전(가드 발화; §25
  IAP-AC-001 "cannot yield or preserve `APPROVE`"); (b) 전 §9 필드 present·non-wildcard·정합 ⇒ complete(양성 side).

### 5.2 approval_decision — deterministic restrictive (§11; IAP-EV-003 substrate, core L1 슬라이스)

`approval_decision(request, policy, generation, injected_facts) -> ApprovalResult`:

- **결정론**: 동일 (완비 input set + policy + generation + injected facts) ⇒ 동일 result(§4.2 순수 함수·hidden-input
  부재). hypothesis property: 동일 입력 두 평가 ⇒ 동일 `ApprovalResult`.
- **restrictive default(§11 line 289·IAP-INV-003)**: missing/stale/conflicting/unverifiable/unsupported/unknown ⇒
  `DENY`/`UNKNOWN`, never `APPROVE`. `APPROVE`는 소비 자격만(§11 line 294 "non-authorizing business gate"·§1 line 21).
- **DENY terminal·UNKNOWN 승격 불가(§11 line 296)**: repeated eval/timeout/majority/capacity/human-pref/prior-success/
  expected-rejection로 UNKNOWN⇒APPROVE 전환 금지.
- **구조 봉인**: `ApprovalResult.__bool__ ⇒ TypeError`(§4.7·처음부터). 소비 게이트 `is APPROVE`.
- **canary(IAP-AC-003, both-ways)**: (a) 비결정 순서·missing/stale/conflicting/unsupported input이 APPROVE 산출·
  UNKNOWN을 majority/capacity/timeout으로 promote(IAP-AC-003) ⇒ property 실패/거부(가드 발화; §25 "without
  permissive fallback"); (b) 동일 완비 입력 ⇒ 동일 APPROVE(양성 side). **`1.0` vs `1.00` scale 이슈 없음**(IAP는
  numeric 없음).

### 5.3 exact_binding_holds (§13; IAP-EV-004 substrate, core L1 슬라이스)

`exact_binding_holds(request, decision, chain_refs) -> ApprovalResult`:

- **transitive digest 정합(§13 line 328–342·IAP-INV-004)**: 체인(Capsule → proposal → construction envelope →
  candidate command → venue snapshot/decision → request → decision → consumption record + Intent → … → conformance
  proof)의 **인접 쌍 id·digest 참조가 전부 정합**할 때만 통과. 각 노드의 (id, digest) scalar가 다음 노드가
  binding한 값과 exact 일치.
- **substitution 무효화(IAP-AC-004 line 585)**: account/instrument/direction/quantity/unit/price/Capsule/venue/
  construction/broker/route/environment/policy/generation/software/deployment 어느 substitution도 binding 끊김.
- **양방향 집합 비교(#14 MAJOR-1)**: 결측 링크(binding 끊김) ∧ 잉여/치환 링크(다른 chain) 모두 거부.
- **반환·소비 계약**: `ApprovalResult` — `is APPROVE` 명시(§4.7).
- **canary(IAP-AC-004, both-ways)**: (a) chain 한 노드 substitution·결측·잉여 치환(IAP-AC-004) ⇒ 무효(가드 발화;
  §25 "substitution invalidates the decision"); (b) 전 노드 정합 ⇒ bound(양성 side). **id⊥digest**(same-id/diff-bytes
  ⇒ `CRITICAL_CONFLICT`·§3.1).

### 5.4 invalidation_closure (§14; IAP-EV-007 substrate, core L1 슬라이스)

`invalidation_closure(graph: Mapping[node, frozenset[node]], trigger: node) -> frozenset[node]` (순수 그래프 도달성):

- **complete closure(§14 line 361·IAP-INV-008)**: trigger에서 도달 가능한 **모든** dependent node(requests/decisions/
  consumption records/Intents/risk-flow decisions/commitments/proofs/authorities/capabilities/pending attempts/
  egresses/protection)를 transitive reachability로 계산 — L1-decidable 순수 함수.
- **부분 폐포 = fail-open·불확정⇒확장**: 한 dependent라도 누락 = 탈출(안전 위반); unknown edge/node ⇒ **확장**
  (reachable로 취급, under-count 금지 #14 MAJOR-1). `MaterialityVerdict` UNKNOWN⇒MATERIAL(§5.7 line 126)이 진입.
- **before/after consumption(§14 line 363)**: unconsumed decision ⇒ ineligible; consumed lineage ⇒ future-use
  block(economic effect 보존·§5.6).
- **absence ≠ currentness(§14 line 365)**: 무효화 이벤트 부재를 currentness로 추론 금지.
- **canary(IAP-AC-007, both-ways)**: (a) trigger가 전 dependent에 도달(no escape)·불확정 edge⇒확장·absence를
  currentness로 오인(IAP-AC-007) ⇒ 가드 발화(§25 "blocks every affected future new-risk use … while retaining
  possible economic effect"); (b) 증명된 disconnected node는 미포함(availability side). **주의(honest boundary)**:
  실 material-invalidation-to-egress propagation latency(`B_approval_invalid_to_intent`·`_to_egress`)는 런타임
  측정(§8.1); L1은 폐포 **계산의 완전성·확장 규율**만.

### 5.5 unknown_confines (§16; IAP-EV-009 substrate, core L1 슬라이스)

`unknown_confines(approval_state, capacity_available, labels, priority) -> bool`(정합·`is True` 소비):

- **UNKNOWN 차단(§16 line 391·IAP-INV-010)**: UNKNOWN approval·request-completeness·independent-input·common-mode·
  generation·consumption·invalidation 상태 ⇒ ordinary new risk 차단. **available capacity가 uncertainty를
  permission으로 전환 불가**(§16 line 391 "Available RCL capacity cannot convert uncertainty into permission").
- **label/human/priority ≠ bypass(§16 line 393·IAP-INV-013)**: close/exit/hedge/cancel/reduce-only/emergency/
  high-priority label·human approval이 approval을 대체·protective classification·reserved capacity 창조 불가 —
  "A close, exit, hedge, cancel, reduce-only, emergency, or high-priority label must still pass the applicable …
  rules. Priority is not reserved protective capacity"(§16 line 393). protective classification은 ADR-002-001(§3.5).
- **protective path 별도(§16 line 395)**: "A separately pre-authorized protective path may operate only inside its
  exact exclusive lease … Uncertainty denies the protective send; it does not justify an ordinary fallback." ⇒
  uncertainty ⇒ ordinary fallback 금지(런타임 lease는 ADR-002-001/002).
- **canary(IAP-AC-009, both-ways)**: (a) UNKNOWN + available capacity·human preference·emergency/exit/hedge/protective
  label·priority(IAP-AC-009) ⇒ 차단(가드 발화; §25 "cannot create ordinary or protective permission"); (b) APPROVE +
  current binding ⇒ 소비 자격(양성 side). **not-Phase-1 명시**: broker ambiguity 통합(§5.6)·partition은 +Broker/런타임.

### 5.6 economic_effect_outlives (§16/§19/§11; IAP-EV-011 substrate, core L1 슬라이스)

`economic_effect_outlives(approval_lifecycle_event, order_state, capacity_commitment) -> bool`(정합·`is True` 소비):

- **continuity(IAP-INV-011 line 174·§16 line 397·§19 line 437)**: expiry/invalidation/consumption/revocation/loss·
  denial·service-outage가 order/fill/exposure/UNKNOWN/capacity를 **erase·release·cancel 못 함**. "Expiry, invalidation,
  consumption, revocation, or loss of approval never proves non-acceptance, final quantity, cancellation, zero
  exposure, or releasable capacity"(IAP-INV-011). newly denied/expired approval이 broker rejection·zero quantity를
  **retroactively 증명 못 함**.
- **broker ambiguity(§16 line 397)**: missing ACK ⇒ potentially-live·capacity-covered(not broker non-acceptance);
  cancel ACK ≠ Final Quantity Proof. **broker ACK/FQP 의미는 +Broker**(ADR-002-004·§3.5) — L1은 "approval
  lifecycle event ≠ economic-state change" 구조만.
- **expiry 반방향(§19 line 437)**: "Expiry prevents future consumption or send" — 미래 소비/전송은 차단(양성 side:
  approval은 실제로 만료·재사용 차단됨). 즉 continuity는 "capacity release 금지"이지 "expiry 무효"가 아니다.
- **canary(IAP-AC-011, both-ways)**: (a) expiry/invalidation/denial/missing-ACK/cancel-ACK/timeout/outage가
  order/exposure/UNKNOWN erase·capacity release(IAP-AC-011) ⇒ 거부(가드 발화; §25 "ambiguous sends remain
  potentially live"); (b) expired approval ⇒ future consumption 차단 ∧ capacity 보존(양성 side — 양방향: 차단은
  하되 release는 안 함).

---

## 6. predicate-only 술어 — independent-validation·single-use consumption·no-widening·egress-currentness·partition·recovery (IAP-EV-002/005/006/008/010/012 substrate, 최소 ≥ L2·닫지 않음)

각각 **L1-decidable substrate**를 저작하나 **어떤 IAP-EV도 닫지 않는다**(최소 ≥ L2·+Security 잔여).

### 6.1 independent_validation + common-mode 선언 완비 (§10; IAP-EV-002 substrate, predicate-only)

`independent_validation_declared(request, common_mode_declarations) -> bool` — §10 independent evaluation의
**구조적 L1 슬라이스만**. §10 line 274 verbatim "The proposer cannot select a more favorable independent source,
policy version, evaluator, fallback, or residual-risk disposition. Two services sharing the same effective failure
path do not create independence. Recalculation with the same corrupted implementation is not validation." L1은
**(i) proposer-produced value ≠ independent 표식**(IAP-INV-002 line 138 "not rely solely on proposer-produced or
common-mode-corrupted facts")·**(ii) common-mode declaration 완비성**(§9 line 249 required independent facts·
validation paths·common-mode declarations 필드가 present)만 구조적으로 검사. **실 recompute·source/parser/mapping/
library/model/cache/registry/admin/deployment/network/clock common-mode 격리**(§10 item 6)는 **EV-L2 component-fault·
+Security 런타임**(§27 q3/q4/q9). 최소 `EV-L2/3+Security`. **canary(IAP-AC-002)**: proposer-only value·shared
failure path 선언(IAP-AC-002) ⇒ common-mode(가드 발화; §25 "cannot masquerade as independent approval"); declared
independent path + 완비 common-mode 선언 ⇒ 통과. **not-Phase-1 명시**: recompute-and-compare는 런타임(§0.4c edge 0).

### 6.2 single-use consumption 상태기계 (§12; IAP-EV-005 substrate, predicate-only — state.py) [EV-L1 노른자]

`consumption_transition(decision, current_status: ConsumptionStatus, command) -> tuple[ConsumptionStatus,
ConsumptionOutcome]` (state.py — orthostate/ioc `state.py` 관행 동형):

- **상태기계 모델(등록→소비→소진)**: `ELIGIBLE`(unconsumed current APPROVE decision) → `CONSUMED`(single-use spent).
  전이 규칙(§12 line 306–314): (i) `ELIGIBLE` + decision `is APPROVE` + current/unexpired/unrevoked/unconsumed/
  compatible/in-scope(§12 line 307) + approved-Intent-envelope가 byte-for-byte/canonically-equivalent(§12 line 309)
  ⇒ `CONSUMED` + `ApprovalConsumptionRecord` + Intent 생성 요청; (ii) `CONSUMED` + **identical** command ⇒ **same
  record 반환**(idempotent duplicate, no new Intent — §12 line 313); (iii) `CONSUMED` + **conflicting** command ⇒
  **reject**(§12 line 313); (iv) 재사용(second consumption) ⇒ **reject**(single-use — IAP-INV-006 line 154 "at most
  one immutable Intent"). **state-machine exploration은 VER-002-001 EV-L1 정의**(model checking)라 L1-decidable.
- **orthostate 경계(§3.5 핵심)**: 이 상태기계는 **decision-consumption 차원**(IAP 소유)이며 **orthostate Intent
  차원(PROPOSED→APPROVED)과 직교**하다. IAP는 consumability를 판정하고, orthostate `intent_transition_allowed`
  (`predicates.py:432`)가 Intent 전이를 수행한다. 런타임 Intent Registry가 둘을 **atomic txn**으로 묶는다.
- **not-Phase-1(§12 line 316)**: "The transaction SHALL be linearizable or equivalently fenced. A database
  uniqueness constraint without authoritative generation fencing is insufficient if stale writers can still create
  an Intent or dependent effect." ⇒ 실 linearizable serialization·writer-epoch fence·concurrent-race 해소는 **EV-L2/
  L3+Security**(IAP-EV-005/010). Phase-1은 상태기계 **모델**(재사용⇒거부·duplicate⇒idempotent·conflict⇒reject)만.
- **single consumption ≠ single send(§12 line 320)**: "Single consumption is not a single-send promise and cannot
  be used to bypass attempt-level controls." ⇒ 소비된 Intent도 attempt별 aggregate-risk/action-flow/RCL/conformance/
  authority/egress 게이트 독립 필수(§1 line 21).
- **소비 계약**: `ConsumptionStatus.__bool__⇒TypeError`(§4.7); 게이트 `status is ConsumptionStatus.ELIGIBLE`.
- **canary(IAP-AC-005, both-ways)**: (a) concurrent/duplicate-conflicting/replayed/cross-scope/stale-writer
  consumption(IAP-AC-005) ⇒ 최대 1개 Intent·conflict reject·재사용 reject(가드 발화; §25 "at most one exact
  immutable Intent and one authoritative Consumption Record"); duplicate-**identical** ⇒ same record(idempotent);
  (b) 첫 `ELIGIBLE` + APPROVE + current ⇒ `CONSUMED` + 1 record(양성 side).

### 6.3 no_widening_no_union + all-false authority (§7/§13; IAP-EV-006 substrate, predicate-only)

`no_widening_no_union(decisions, requested_scope) -> bool` + `approval_grants_no_authority(effect: ApprovalAuthorityEffect)
-> bool`(all-false):

- **no union/widen(IAP-INV-007 line 158)**: "A narrower decision, multiple decisions, or a later more favorable
  fact cannot be combined to approve broader or different scope." ⇒ 여러 narrow decision을 union해 broader scope
  승인 불가; later favorable fact로 widen 불가.
- **all-false authority(IAP-INV-005 line 150·§7)**: `ApprovalAuthorityEffect`의 어떤 True도 unconstructable
  (mutate-capacity/create-headroom/issue-authority/classify-protection/transmit/clear-HALT/re-arm 전부 False).
  §7 line 202 "registry cannot invent, widen, or reevaluate a decision"·line 210 "SHALL NOT hold a usable live
  broker credential." **credential/route confinement·bypass 탐지는 +Security 런타임**(§18). 최소 `EV-L2/3+Security`.
- **canary(IAP-AC-006)**: union 2 narrow decision⇒broader·widen·capacity/headroom 전환·authority/capability issue·
  transmit·clear-HALT·re-arm 시도(IAP-AC-006) ⇒ 거부/ValidationError(가드 발화; §25 "cannot be unioned, widened,
  converted into capacity/headroom …"); all-false effect + single exact decision ⇒ 통과.

### 6.4 active_egress_currentness (§15; IAP-EV-008 substrate, predicate-only)

`active_egress_currentness(proof_inputs) -> bool` — §15 final-egress active currentness의 **술어 계약만**. §15 line
381 verbatim "Cached `APPROVED`, local Intent state, TTL, heartbeat, service health, last-known generation, prior
verification, eventual consistency, or absence of an invalidation event is not sufficient." L1은 **currentness가
active/bounded proof를 요구하고 cache/TTL/heartbeat/absence로 추론 불가**라는 **구조적 술어**(§14 line 365와 정합).
**실 final-egress 강제·capability claim·`SEND_STARTED` ordering·race 해소는 ADR-002-013/007/024 런타임**(§15 line
385·§1 line 29). §15 line 383 "Failure or ambiguity is denial." 최소 `EV-L2/3+Security`. **canary(IAP-AC-008)**:
cached/stale/invalidated/mismatched/unconsumed/multiply-consumed/wrong-Intent/absence-inferred lineage(IAP-AC-008)
⇒ 거부(가드 발화; §25 "cannot infer currentness from absence of events"); active bounded proof + single authoritative
consumption ⇒ 통과. **not-Phase-1**: wire 강제·capability claim은 런타임.

### 6.5 stale_generation_fenced + conflicting⇒UNKNOWN (§17; IAP-EV-010 substrate, predicate-only)

`stale_generation_fenced(committed_generation, writer_generation) -> bool` + `conflicting_evaluators_unknown(results)
-> ApprovalResult`:

- **stale fence(§17 line 405·IAP-INV-012 line 178)**: "Only the current fenced Intent Registry writer may consume a
  decision and create an Intent"·"Old policy, evaluator, approval, registry-writer, deployment, recovery, authority,
  and egress generations cannot decide, consume, or transmit after a newer applicable generation is committed"
  (IAP-INV-012). ⇒ older generation ⇒ fenced(순수 순서 비교 `tos.ordering`·§3.2).
- **conflicting⇒UNKNOWN(§17 line 403)**: "Concurrent approval evaluators may compute decisions only under one exact
  policy and generation; conflicting results are retained and make the request `UNKNOWN` until authoritatively
  resolved. Majority or newest-arrival selection is not automatically authoritative." ⇒ 상충 결과 ⇒ 둘 다 보존 +
  `UNKNOWN`(majority/newest 선택 금지).
- **not-Phase-1**: 실 partition·split-brain·writer-fence enforcement·broker-reachable partition(§17 line 409)은
  EV-L2/L3+Security. 최소 `EV-L2/3+Security`. **canary(IAP-AC-010)**: old evaluator/stale writer/rollback/split-brain이
  old generation으로 consume/transmit(IAP-AC-010) ⇒ fenced/UNKNOWN(가드 발화; §25 "cannot consume or transmit under
  an old generation"); conflicting evaluators ⇒ UNKNOWN(no majority); current fenced writer + single generation ⇒ 통과.

### 6.6 recovery_revives_nothing (§20; IAP-EV-012 substrate, predicate-only)

`recovery_revives_nothing(...)`는 **무조건 True**(§4.5·§20 line 447) — "Approval-service health, source recovery,
policy rollback, database restore, replay match, Intent Registry recovery, or broker reconnect does not revive
approval or live authority. Material recovery requires fresh generation fencing, current artifacts, new approval
where required, and the complete ADR-002-007/015 re-arm chain. There is no automatic re-arm"(§20 line 447). §20
line 445 "Restored requests, decisions, consumption records, and Intents are evidence only until their complete
current binding and authoritative history are proven." IAP-INV-015 line 190 "Documents, logs, signatures, audit,
replay, or successful prior decisions do not replace current enforcement at Intent registration and final egress."
spg `expiry_revives_nothing`·are `non_revival_holds`·ioc `recovery_revives_nothing` 동형. **Recovery Barrier
(ADR-002-017)·governed re-arm workflow enforce는 런타임**(§27 q11 인접). 최소 `EV-L2/3+Security`. **canary(IAP-AC-012,
both-ways)**: (a) restart/restore/replay-match/source-recovery/approval-recovery/Intent-Registry-recovery 후 old
decision auto-consume·revive·re-arm 시도(IAP-AC-012) ⇒ 거부(fresh chain + governed re-arm 요구, 가드 발화; §25
"cannot auto-consume, revive permission, or re-arm; evidence reconstructs without acting"); (b) fresh chain +
current artifacts + governed re-arm ⇒ 통과.

---

## 7. property-test 하네스 타깃

§1 분류에 정렬한다. **닫는 IAP-EV = 0건** — 어떤 test-target도 IAP-EV closure·acceptance를 주장하지 않는다(규율
태그 부착). 각 술어에 **both-ways canary**(§4·§5·§6)·**truthy-sentinel canary**(§4.7)·**fixture clean-vs-illegal
정합**(#8 교훈)을 건다.

- **core(L1 슬라이스, IAP-EV-001/003/004/007/009/011 substrate)**: `request_is_complete`(§5.1); `approval_decision`
  결정론+restrictive(§5.2); `exact_binding_holds`(§5.3); `invalidation_closure`(§5.4); `unknown_confines`(§5.5);
  `economic_effect_outlives`(§5.6). **invalidation-closure property(노다지)**: hypothesis로 무작위 의존 그래프 +
  trigger 생성 → 폐포가 도달 가능한 전 dependent를 포함(no escape) + 불확정 edge ⇒ 확장 + 증명된 disconnected는
  미포함(both-ways). **decision-determinism property**: 무작위 완비 request 생성 → 동일 입력 두 평가 digest/result
  동일 + missing/stale/conflicting ⇒ DENY/UNKNOWN.
- **predicate-only(IAP-EV-002/005/006/008/010/012 substrate, EV 미주장)**: `independent_validation_declared`(§6.1);
  **`consumption_transition` 상태기계 property(노다지)**: hypothesis로 무작위 (status, decision, command) 시퀀스
  생성 → 등록→소비→소진 불변식(재사용⇒거부·duplicate-identical⇒same-record·conflict⇒reject·최대 1 record) 검사
  (§6.2); `no_widening_no_union`+all-false(§6.3); `active_egress_currentness`(§6.4); `stale_generation_fenced`+
  conflicting⇒UNKNOWN(§6.5); `recovery_revives_nothing`(§6.6).
- **truthy-sentinel 회귀(§4.7, MANDATED)**: `ApprovalResult`·`ConsumptionStatus` 반환 술어에 대해 (i) `DENY`/
  `UNKNOWN`/`CONSUMED`가 truthy임을 assert, (ii) `is APPROVE`/`is ELIGIBLE` 게이트가 그 외를 reject함을 assert
  (`if result:` 대비 회귀), (iii) **구조 봉인 회귀**: `bool(ApprovalResult.*)`·`bool(ConsumptionStatus.*)`가
  `TypeError`를 raise함을 assert. **이 회귀가 #14 M1 truthy-sentinel 교훈의 처음부터 능동 봉합**이다.
- **seam cross-check(test-only, MANDATED §3.4)**: `test_seam_dsl`(iap `ProposalApprovalRequest` proposal ref = dsl
  `Proposal` `proposal_id`/digest `proposal.py:68`)·`test_seam_ioc`(iap decision approved-envelope 비교 = ioc
  `ApprovedIntentContract` scalar `ioc/records.py:142`·ioc가 IAP approval_identity 참조 `records.py:199`)·
  `test_seam_orthostate`(iap `ApprovalConsumptionRecord` intent ref = orthostate `intent_identity` `records.py:93`·
  PROPOSED→APPROVED 전이는 orthostate `intent_transition_allowed` `predicates.py:432` 소유·`ApprovalResult.DENY` ≠
  `IntentState.DENIED` §3.5)·`test_seam_capsule`(request capsule ref = `DecisionContextCapsule` `capsule.py:170`).
  테스트 import는 package closure에 불계상(§7.1).
- **∅-공허 회귀(양방향, §4.7)**: absent/wildcard request 필드 ⇒ 불완전; missing scope ⇒ UNKNOWN(zero/wildcard
  아님); 빈 의존 그래프 ⇒ 최소 폐포·불확정⇒확장; UNKNOWN+capacity ⇒ 차단; **동시에** 각 완비 입력의 정당 통과 canary.

### 7.1 import-closure 검증 테스트 (설계 #4 §7.1·#12–#14 §7.1 상속)

`import tos.iap` 후 `sys.modules` closure에 **금지 집합 부재 assert**: `shared.config`·`os.environ` 흔적·`numpy`/
`pandas`/`yaml`·**`tos.dsl`·`tos.capsule`·`tos.ioc`·`tos.brokercap`·`tos.spg`·`tos.venue`·`tos.are`·`tos.rcl`·
`tos.orthostate`·`tos.liveauth`·`tos.authority`·`tos.time`·`tos.evidence`·`tos.protective`·`tos.recon`**(15 형제
전부) 부재; **`tos.canonical`·`tos.ordering`만 존재 허용**(sibling edge 0 — #14의 rcl 허용과 대조). required check
(`tos-firewall`, `tools/tos_firewall_check.py` layer-① AST + `.importlinter` layer-② 전이)와 함께 green이어야 §0.3
선언이 능동 성립.

### 7.2 run manifest 정렬 (설계 #1 §5.1 7항목)

(1) 목적: iap Phase-1(EV-L1) 순수 모델+property test. (2) 명령: `pytest tos/tests/iap/ -v`. (3) 격리: hermetic
(`.env` 비주입·clock 미접근·네트워크 없음 — approval determinism의 hidden-input 부재 §4.2·§19 clock 미접근과 정합).
(4) 결정론: hypothesis 시드 고정·`EVL1ProvisionalCanonicalizer` 고정·enum StrEnum 고정. (5) 산출물: property test
결과(EV closure 아님 — 규율 태그). (6) 게이트: `tos-firewall` required green. (7) 비-acceptance: 어떤 IAP-EV도 닫지
않음(§0.2·VER-002-001 §5).

---

## 8. bounds 주입 + Phase-0

**§8.0 iap 모델 구조에 numeric bound 부재**: 전부 enum(`ApprovalResult`/`ConsumptionStatus`/`MaterialityVerdict`)·
boolean·집합/그래프 논리·주입 opaque age param. ADR §4 non-scope line 92 "numeric bounds, which remain Verification
Profile decisions"는 수치를 **명시 배제**한다 — 전부 **Safety/Verification Profile INSTANCE 측정값**이며 주입 opaque
param으로만 담는다. 값 부재 ⇒ fail-closed(§4·§19 line 435 "A future timestamp, negative age, missing time, clock
discontinuity, unknown transport, or untrusted Time Health is restrictive"). 값 승인은 Bounds-Approver 게이트(§9.2).

**§8.1 Verification-Profile 키 실측(#13 MAJOR-2 규율 — `measurement_source` 전수 확인)**: ADR §27 q12(line 655)가
요하는 수치 및 VERIFICATION-PROFILE-002.yaml 키 상태(전수 grep):
- **approval invalidation-to-Intent(§12/§14)**: `B_approval_invalid_to_intent`(line 303, `value_ms: null` MEASURE,
  `measurement_source: approval_generation_invalidation_decision_consumption_and_intent_registry_trace`,
  rationale "ADR-002-023 §§12, 14") — **이미 존재**.
- **approval invalidation-to-egress(§15)**: `B_approval_invalid_to_egress`(line 310, `null` MEASURE,
  `measurement_source: approval_generation_consumption_invalidation_and_egress_boundary_trace`, "ADR-002-023 §15")
  — **이미 존재**.
- **approval generation fence(§17)**: `B_approval_generation_fence`(line 317, `null` MEASURE,
  `measurement_source: trading_approval_generation_writer_fence_and_egress_trace`, "ADR-002-023 §17") — **이미 존재**.
- **proposal approval request age(§9/§19)**: `MAX_proposal_approval_request_age_ms`(line 721, `null` — "APPROVE per
  action class; stale or unknown request age denies approval and consumption") — **이미 존재**.
- **independent approval decision age(§11/§19)**: `MAX_independent_approval_decision_age_ms`(line 722, `null` —
  "APPROVE per exact request/Intent scope; expiry never expires economic effect") — **이미 존재**.
- **scope pin(§8)**: `trading_approval_policy_id/generation/digest`(line 67–69, TBD/null) — policy 아티팩트의
  test-harness pin.
- **결론(over-claim 봉합·#10 lesson)**: ADR §27 q12가 요구하는 IAP-owned 5 bound(invalid-to-intent·invalid-to-egress·
  generation-fence·request-age·decision-age)가 **전부 실재**하고 전부 null/MEASURE(미승인) + 3 scope-pin 실재.
  ⇒ **candidate 신규 키 = 0건**(#10/#13/#14 "0 누락" 동형; #12의 4-key 누락과 대조). 이는 결함이 아니라 **Phase-0
  Bounds-Approver 승인 항목**이다 — iap는 이 값들을 신뢰하지 않으며(VP status PROPOSED·unapproved bound은 approved
  bound 아님, VER-002-001 §6) 전 수치를 fail-closed로 처리(§4·§19).

**§8.2 self-referential 주의(경미)**: iap `TradingApprovalPolicy`는 spg Safety Configuration Bundle governance
대상(§8 line 232)이며 VP scope 블록이 policy id/generation/digest를 pin한다(line 67–69). #12(spg)가 다룬
self-reference paradox와 달리 iap는 **policy의 소비자**일 뿐(governance 주체는 spg)이라 layering이 단순하다 — iap는
VP를 import·파싱하지 않고(YAML은 하네스 #3), policy 좌표를 주입 scalar로만 담는다. VP status PROPOSED ⇒ 전 수치 불신.

**§8.3 upstream age bound 합성(런타임·not-Phase-1)**: §15 final-egress·§12 Intent registration은 iap-owned bound뿐
아니라 upstream age bound(`MAX_decision_context_age_ms` line 710·`MAX_critical_input_snapshot_age_ms` line 709·
`MAX_order_admissibility_decision_age_ms` line 712·`MAX_aggregate_risk_decision_age_ms` line 716)를 **합성 소비**한다
— 전부 형제 ADR 소유·실재·null. Phase-1 iap는 이 합성을 **강제하지 않고**(런타임 §6.4) request/decision/consumption
record에 각 upstream 아티팩트의 id+digest scalar를 binding할 뿐이다(§5.1/§5.3). 합성 강제·age 검사는 EV-L3
final-egress·Intent Registry 런타임.

---

## 9. 후속 작업 · Phase-0 인간 게이트 이관 항목

### 9.1 후속 구현 작업 (본 계약 위에서)

1. `tos/src/tos/iap/` 5-module 저작(`_base.py` all-false authority shim·`vocabulary.py`·`records.py`·`predicates.py`·
   `state.py`[consumption 상태기계]) + `tos/tests/iap/` property test(§7) + seam cross-check(§3.4) + import-closure
   (§7.1) + truthy-sentinel 구조 봉인 회귀(§4.7).
2. core 술어 6종(§5) + predicate-only 술어 6종(§6) + 4-아티팩트·all-false `ApprovalAuthorityEffect`·`ApprovalResult`/
   `ConsumptionStatus`/`MaterialityVerdict`(§2) 구현. **sibling edge 0 유지**(§0.4c) — 어떤 형제 타입도 REUSE·import
   하지 않음.
3. 미래 caller 런타임(Independent Approval Service / Intent Registry)이 iap 산출(request·decision·consumption record)을
   소비자(orthostate PROPOSED→APPROVED 전이·are·rcl·final-egress)로 배선(§3.4; Phase 1 밖·EV-L2/L3). **§12 atomic
   txn(IAP consumability + orthostate 전이 + record write)은 런타임 linearizable 구현**(§6.2).

### 9.2 Phase-0 인간 게이트로 넘기는 항목 (본 계약이 결정하지 않음)

ADR §27 Open Implementation Questions(12항)·§28 Approval Gate(13조건)에서 Phase-1 밖으로 이연:
1. **canonical TradingApprovalPolicy/ProposalApprovalRequest/IndependentApprovalDecision/ApprovalConsumptionRecord
   schema 선택**(§27 q1) — 프로덕션 canonical semantic form(§3.1 EVL1ProvisionalCanonicalizer는 잠정).
2. **policy language + deterministic evaluator/verifier(parser·semantic diversity)**(§27 q2) — 전부 주입; L1은
   `approval_decision` 순수 함수 계약만.
3. **independent source/transformation/mapping/registry/clock/administrative path**(§27 q3) — 각 safety-critical
   fact의 approved independent path(§6.1은 구조 슬라이스만).
4. **common-mode taxonomy + residual-risk process**(§27 q4·§10 item 6) — required scope reduction(+Security).
5. **monotonic Trading Approval Generation + invalidation graph fencing**(§27 q5·§17) — stale evaluator/writer/
   Intent/authority/egress fence 런타임(§6.5는 순서 비교만).
6. **Intent Registry storage/consensus/idempotency/writer-fence**(§27 q6·§12) — linearizable single-use consumption
   런타임(§6.2는 상태기계 모델만).
7. **active currentness protocol(no permissive cache/circular dependency)**(§27 q7·§15) — ADR-002-024 Currentness
   Vector 런타임(§6.4는 술어 계약만).
8. **signature/digest/canonicalization/compatibility/evidence-receipt format(substitution·parser-differential 저항)**
   (§27 q8·§18) — +Security.
9. **failure-domain separation**(§27 q9·§18) — proposer/approval/independent-input/policy-activation/Intent-Registry/
   RCL/authority/egress/evidence 분리(+Security).
10. **어느 approval class가 추가 ADR-002-015 human approval 요구**(§27 q10) — human approval이 automated validation
    대체 불가(§16·§0.2). Phase-0 human class 결정.
11. **correction/late-discovery dependency closure across consumed Intents/live attempts**(§27 q11·§14) — 폐포가
    already-consumed lineage·potentially-live attempt까지 bound(§5.4는 순수 도달성; 실 propagation은 런타임).
12. **numeric bounds 승인**(§27 q12·§28 item 11) — `B_approval_invalid_to_intent`·`B_approval_invalid_to_egress`·
    `B_approval_generation_fence`·`MAX_proposal_approval_request_age_ms`·`MAX_independent_approval_decision_age_ms`
    (§8.1 **전부 실재·null**)의 Bounds-Approver 승인 + concurrency/partition/rollback/compromise/recovery/fault-injection
    측정(§28 item 11). **candidate 신규 키 0건.**
13. **orthostate Intent Registry 런타임 배선**(§28 item 4/5) — PROPOSED→APPROVED atomic txn·`ApprovalConsumptionRecord`
    ↔ orthostate `StateTransitionRecord` 상호 참조(§3.5 핵심 판정 2). `ConsumptionStatus`의 orthostate cross-package
    dimension 위임 여부(§3.5)는 orthostate 측 후속 결정.
14. **ADR-002-020 IOC downstream binding(§13 chain)** — ioc `OrderConformanceProof`가 IAP decision/consumption
    identity를 binding(§13 line 346 — **미래 배선**, `OrderConformanceProof`는 해당 필드 미보유[v1.1 MAJOR-1
    정정]); dsl `Proposal` id scheme -020/-023 공동(#14 §3.5).
15. **ADR-002-013 final egress·ADR-002-007 capability·ADR-002-024 currentness 런타임**(§28 item 6) — active
    currentness proof·capability claim·SEND_STARTED.
16. **ADR-002-016 Evidence Integrity·Replay**(§21·§28) — replay ENGINE(§2.3 레코드 substrate만 Phase-1).
17. **ARCHITECTURE-GATE-STATUS 명시 acceptance 결정**(§28 item 13) — 실행된 IAP-EV-001..012 + cross-system evidence
    (CII/VTG/IOC/ARE/AFG/RCLP/EGRESS/HAG/ERI/SBR/TIME/SA/RC/BC, §28 item 10) + 독립 리뷰(Independent-Safety-Reviewer
    하드 배제).

---

## 10. 개정 로그 + 비준 체크리스트

### 10.1 개정 로그

- **v1.0 (2026-07-26) — 초안, 독립 비평 리뷰 대기.** ADR-002-023을 Phase 1(EV-L1) 설계 계약으로 실현. 패키지
  `tos.iap`(대안 `tos.approval`[명료·verbose·부분·human 혼동] runner-up, `tos.consumption`[부분]·`tos.intent`
  [collision — orthostate/ioc] 기각, §0.4a — **오독 위험 #14 ioc[Immediate-Or-Cancel] 대비 경감**). 4-아티팩트
  (`TradingApprovalPolicy`[spg-governed]·`ProposalApprovalRequest`·`IndependentApprovalDecision`·`ApprovalConsumptionRecord`
  digest-bound `IndependentIdArtifact` + `TradingApprovalGeneration`=`tos.ordering` REUSE) + all-false
  `ApprovalAuthorityEffect`(§2). EV 분류: **core 6행(IAP-EV-001/003/004/007/009/011, #14형·사전 카운트 6과 일치) /
  predicate-only 6행(002/005/006/008/010/012) / not-Phase-1(런타임·+Security·형제) — 닫는 IAP-EV = 0건**(§1). seam:
  **dsl/capsule/ioc/venue/brokercap/spg/orthostate/are/liveauth scalar·digest producer/consumer + sibling edge 0건
  (#14의 1 edge와 대조되는 distinction), PROMOTE 0**(코드 실측: dsl `proposal.py:68`·`7–8`, capsule `capsule.py:170`·
  `snapshot.py:96`, ioc `records.py:142`·`154–155`·`199`·`215`·`301`, orthostate `vocabulary.py:32`·`predicates.py:364/
  432`·`records.py:93`, are `records.py:348/451`, liveauth `records.py:112/188/214`, rcl `_base.py:55`, spg
  `vocabulary.py:180`, §3.4). **핵심 아키텍처 판정**: (i) **-020/-023 소유권 분할 상속·정합**(§3.5) — §8 field
  set=-020(ioc `ApprovedIntentContract`)·approval/registration=-023(본 문서)·Proposal id scheme·request 어휘=-020/
  -023 공동(ioc `records.py:154–155` 코드 확증). (ii) **orthostate 경계·`ApprovalResult.DENY` ≠ `IntentState.DENIED`**
  (§3.5 핵심 판정 1) — orthostate가 Intent 차원·PROPOSED→APPROVED 전이 소유(`predicates.py:432`), IAP는 승인
  decision·single-use consumption 판정·`ConsumptionStatus` 차원 소유; approval DENY는 orthostate 전이 미유발(Intent는
  PROPOSED 유지), orthostate DENIED는 APPROVED 이후(are/rcl 하류). (iii) **sibling edge 0**(§0.4c) — IAP는 control-plane
  gate이지 economic-effect producer가 아니므로 CapacityVector REUSE 불요(#14 ioc와의 distinction). (iv) **truthy-sentinel
  구조 봉인을 처음부터**(#14 M1 교훈 선제 채택): `ApprovalResult`(APPROVE/DENY/UNKNOWN)·`ConsumptionStatus`
  (ELIGIBLE/CONSUMED)는 `__bool__ ⇒ TypeError` truthy-불가 타입 ⇒ 소비 게이트 `is APPROVE`/`is ELIGIBLE`·`bool|None`은
  `is True`(§4.7). 중심 fail-closed 술어: `request_is_complete`(§9 완비·wildcard 거부)·`approval_decision`(결정론·
  restrictive·UNKNOWN 승격 불가)·`exact_binding_holds`(chain digest 정합·양방향)·`invalidation_closure`(complete
  도달성·불확정⇒확장·absence≠currentness)·`unknown_confines`(capacity offset 금지·label≠bypass)·`economic_effect_outlives`
  (expiry≠release)·`consumption_transition`(등록→소비→소진·재사용⇒거부)·`recovery_revives_nothing`(무조건 True)(§5/§6).
  **∅-공허 양방향**(빈 request 필드·빈 의존 폐포·missing scope[zero/wildcard 아님]·UNKNOWN+capacity — 금지+허용 둘 다,
  §4.7). 앵커: IAP-INV-001..015·IAP-AC-001..012·IAP-EV-001..012(§0.4f). **bounds 실측**: IAP-owned 5 profile 키
  (line 303·310·317·721·722) 전부 실재·null(candidate 신규 키 0건, §8.1). 선제 봉합: fail-open(§4.2/§5.2)·∅-공허
  양방향(§4.7)·under-realization(전용 술어는 실재하는 형제 seam에만·orthostate Intent 전이는 정직 이연)·phantom 타입 0
  (전 인용 grep 실측)·verbatim+line·차원 비붕괴(§2.2 (4) — `ApprovalResult.DENY`≠`IntentState.DENIED`)·**truthy-sentinel
  구조 봉인(#14 M1 선제)**·**과대 주장 금지(extra="forbid"는 모델 필드 수준만)**. **어떤 EV도 닫지 않음·acceptance
  미선언·비준 기록 = "2026-07-26 운영자 위임 자동 비준(v1.1)".**

- **v1.1 (2026-07-26) — 독립 비평 리뷰 REVISE(CRITICAL 0·MAJOR 1·MINOR 5·NIT 1) 반영, forward-only(오케스트
  레이터 직접 적용).** **MAJOR-1**: phantom 인용 정정 — `OrderConformanceProof.approval_identity`는 존재하지
  않음(실제는 `ApprovedIntentContract`[:199]·`AuthorizedConstructionEnvelope`[:294]의 필드; `OrderConformance
  Proof`[:357]는 해당 필드 미보유 — §13:346 proof-binding은 -023 하류 **미래 배선**으로 정정, "이미" over-claim
  제거[§0.4b·§3.4 표·§4.3·§9.2 item 14]). **MINOR-1~5**: `RclAuthorityEffect`→`rcl/authority.py:19`(base는
  `_base.py:55`)·§0.1.2 3중 라인(114/291·240·118)·§2.1 표(291·240)·`operating_mode` L30·`BundleMemberKind`
  `vocabulary.py:180`. **NIT**: capsule.py:170. 리뷰어 검증 확인: register core-6 EXACT·profile 5키+scope-pin
  전부 실재·**`ApprovalResult.DENY`≠`IntentState.DENIED` 경계 완전 검증**(최대 리스크 공격 실패)·orthostate
  전이 실측 일치·import-closure 형제 15종 완전·#14 교훈(양방향 집합·over-claim 금지·truthy 구조 봉인) 반영
  확인. 아키텍처(4-아티팩트·edge 0·-020/-023 분할) 불변.

### 10.2 비준 체크리스트 (운영자 · 독립 리뷰어 확인 사항)

1. **패키지 명명** `tos.iap`(Independent Proposal Approval) 승인 — **또는 `tos.approval`**(명료·verbose·부분·human
   혼동). **[운영자 판단 지점]**: `iap` register-prefix 충실(`IAP-EV`/`AC`/`INV` 1:1)·terse 관행·오독 경미(#14 ioc
   대비)가 defensible한지. naming은 load-bearing 아님(설계 #1 line 164). `tos.consumption`(부분)·`tos.intent`
   (orthostate/ioc collision) 기각 근거 검토(§0.4a).
2. **seam 결정·sibling edge 0**: dsl/capsule/ioc/venue/brokercap/spg/orthostate/are/liveauth scalar·digest 주입
   (edge 0) — §3.4/§0.4b. **[운영자 판단 지점]**: **sibling edge 0**(#14는 1 edge)이 정확한지 vs `EconomicEffectEnvelope`
   independent recompute를 위해 rcl `CapacityVector` REUSE(1 edge)가 필요한지(§0.4c). 리뷰어: dsl `proposal.py:68`·
   capsule `capsule.py:170`·ioc `records.py:142/199`·orthostate `records.py:93`·`predicates.py:432`·are `records.py:348`·
   liveauth `records.py:112` 인용 라인 검증(sibling 서사 아님).
3. **-020/-023 소유권 분할 상속(§3.5)**: §8 field set=-020(ioc `ApprovedIntentContract` `records.py:142/154–155`)·
   approval/registration=-023(본 문서)·Proposal id scheme·request 어휘=-020/-023 공동 분할이 #14 §3.5와 정합하는지
   재확인(권위 중복 방지 #8 교훈). ioc `records.py:154–155` "models the approved field set, not the registration"
   코드 확증.
4. **orthostate 경계·`ApprovalResult.DENY` ≠ `IntentState.DENIED`(§3.5 핵심 판정 1, 본 문서 최대 리스크)**: orthostate가
   Intent 차원·PROPOSED→APPROVED 전이 소유(`predicates.py:432`·`_INTENT_TRANSITIONS` `predicates.py:364`; PROPOSED→
   DENIED 금지 `predicates.py:440–458`)이고 IAP가 승인 decision·`ConsumptionStatus` 소유임이 정확한지. **approval
   DENY는 orthostate 전이 미유발(Intent PROPOSED 유지)·orthostate DENIED는 APPROVED 이후**라는 구분이 §11 line 296
   "DENY is terminal for the request"와 정합하는지 재확인. **[운영자 판단 지점]**: `ApprovalConsumptionRecord` 소유
   (IAP 권장 vs orthostate)(§3.5 핵심 판정 2).
5. **`ProposalApprovalRequest` identity(§0.4d)**: `IndependentIdArtifact`(권장·substitution 탐지·id⊥digest) vs
   `IdDerivedArtifact`(content-addressed·§9 line 255 "any field change = new identity"). **[운영자 판단 지점]**.
   decision·consumption record는 `IndependentIdArtifact`(are `records.py:451` 동형)임을 재확인.
6. **EV 분류·실측(§1)**: core 6(001/003/004/007/009/011) / predicate-only 6 / not-Phase-1 판정과 **닫는 IAP-EV = 0건**
   규율 확인. 사전 카운트 "core 6"이 register line 300–311(001/003/004/007/009/011 전부 `EV-L1/3` 접두)과 **일치**함을
   재확인, "EV-L1-complete 주장 금지"가 §1·§4·§5·§6·§7에 일관 부착됐는지 self-consistency pass.
7. **truthy-sentinel 구조 봉인(§4.7, #14 M1 선제 채택)**: `ApprovalResult`(APPROVE/DENY/UNKNOWN)·`ConsumptionStatus`
   (ELIGIBLE/CONSUMED)가 non-empty StrEnum이라 `if result:`가 fail-open임을 확인하고, **`__bool__ ⇒ TypeError` 구조
   봉인** + 소비 게이트 `result is ApprovalResult.APPROVE`(+`bool|None`은 `is True`)가 §5·§6 전 술어에 명문화·§7
   회귀됐는지 확인(spg `predicates.py:466` `is not True⇒reject` 선례 대조). **본 문서는 #14 사후 M1을 처음부터
   채택** — 이 선제성이 적절한지.
8. **single-use consumption 상태기계(§6.2)**: 등록→소비→소진(`ELIGIBLE→CONSUMED`; 재사용⇒거부·duplicate-identical⇒
   same-record·conflict⇒reject·최대 1 record)이 §12 line 306–314와 대조되고, 실 linearizable serialization·writer
   fence(§12 line 316)가 EV-L2/L3+Security로 정직 이연됐는지. state-machine exploration이 VER-002-001 EV-L1 정의에
   부합함을 확인. IAP-EV-005가 predicate-only(닫지 않음)임을 재확인.
9. **fail-closed·∅-공허 양방향(§4.7)**: absent request 필드⇒불완전·missing scope⇒UNKNOWN(zero/wildcard 아님)·빈 의존
   폐포⇒최소+확장·UNKNOWN+capacity⇒차단, **각각 금지+허용 canary 둘 다** 확인(#6 fail-open·#10/#12 ∅-void 교훈). 금지
   동사(default/wildcard/substitute/union/widen/coerce/promote-UNKNOWN/headroom/expire/revive/infer-from-absence)
   커버리지 대조. **양방향 집합 비교**(`exact_binding_holds`·`invalidation_closure` — 결측·잉여 모두, #14 MAJOR-1)와
   **과대 주장 금지**(extra="forbid"는 모델 필드만, 튜플 excess는 구조 술어 §2.0) 확인.
10. **invalidation closure(§5.4)**: complete 도달성·부분 폐포=fail-open·불확정⇒확장·absence≠currentness(§14 line 365)·
    `MaterialityVerdict` UNKNOWN⇒MATERIAL(§5.7 line 126)이 순수 L1 함수로 실현되고 실 propagation latency는 런타임
    (§8.1)임을 확인.
11. **소유권 분할(§3.5)**: IAP가 orthostate Intent 전이·rcl capacity(`grant_authorizes_exact_request`)·are risk
    projection·action-flow(ADR-002-022)·venue admissibility·final-egress를 **재저작하지 않음** 확인(#8·#11–#14 권위
    중복 교훈).
12. **실측-원천·phantom 0**: 전 인용 타입(`Proposal`·`DecisionContextCapsule`·`CriticalInputSnapshot`·`ApprovedIntentContract`·
    `AuthorizedConstructionEnvelope`·`CanonicalBrokerCommand`·`OrderConformanceProof`·`IntentState`·`intent_transition_allowed`·
    `intent_identity`·`AggregateRiskDecision`·`LiveAuthorization`·`RclAuthorityEffect`·`BundleMemberKind`·`BrokerCapabilityProfile`)이
    실코드에 존재함을 grep 재확인(#10 MAJOR phantom 교훈 — 인용 전 실측). IAP-INV(15)·IAP-AC(12)·IAP-EV(12) 수·seam
    라인이 원문/코드와 일치.
13. **bounds 실측(§8.1)**: IAP-owned 5 profile 키(`B_approval_invalid_to_intent` line 303·`B_approval_invalid_to_egress`
    line 310·`B_approval_generation_fence` line 317·`MAX_proposal_approval_request_age_ms` line 721·
    `MAX_independent_approval_decision_age_ms` line 722)가 **전부 실재·null**(candidate 신규 키 0건)임을
    `measurement_source` 전수 확인(over-claim 아님 — #10 lesson; #12 4-key 누락과 대조).
14. **broker-agnostic·숫자 하드코딩 0·firewall(§0.3)·verbatim 전사(§2.2)** 확인. `.importlinter` forbidden 계약이
    `tos.iap`를 무수정 자동 포섭(source=tos)함을 재확인. **ADR-002-022(AFG)는 병렬 세션 B 소관 — ADR 원문만 참조,
    세션 B 미비준 설계 문서 미인용** 확인.
15. **비-acceptance**: 어떤 IAP-EV/ADR acceptance·restricted-live·production도 선언 안 함(§0.2)·Independent-Safety-
    Reviewer 하드 배제 확인·비준 기록 = "2026-07-26 운영자 위임 자동 비준(v1.1)".

**독립 리뷰어 공격 지점(open questions)**: (i) **sibling edge 0** 판정이 정확한지 vs §10 item 4 independent
economic-effect recomputation을 위해 rcl `CapacityVector` REUSE(1 edge)가 L1에 필요한지 — 본 문서는 recompute를
+Security 런타임(IAP-EV-002)으로 이연하고 envelope를 digest scalar로만 binding(§0.4c). (ii) **`ApprovalResult.DENY`
≠ orthostate `IntentState.DENIED`**(§3.5 핵심 판정 1)가 정확한지 — approval DENY가 orthostate 전이를 미유발하고
(Intent PROPOSED 유지) orthostate가 PROPOSED→DENIED를 금지(`predicates.py:440–458`)하는 것과 정합하는지, 아니면
approval DENY도 어떤 orthostate 상태를 요구하는지. (iii) **`ApprovalConsumptionRecord` 소유**(§3.5 핵심 판정 2)를
IAP로 둔 판정이 정확한지 vs orthostate Intent Registry 모델의 일부여야 하는지(cross-package dimension 위임 §3.5).
(iv) **`ProposalApprovalRequest` identity**를 `IndependentIdArtifact`로 둔 것(§0.4d)이 정확한지 vs content-addressed
`IdDerivedArtifact`(§9 line 255)여야 하는지 — substitution 탐지 우위 vs dsl `Proposal` 동형. (v) **single-use
consumption 상태기계**(§6.2)를 predicate-only substrate로 저작하고 IAP-EV-005를 닫지 않은 경계가 정확한지 vs
상태기계 일부가 IAP-EV-005의 실질 L1 closure인지(#7 under-realization 인접). (vi) **`consumption_transition`의
orthostate Intent 전이와의 직교성**(§6.2)이 정확한지 vs decision-consumption을 orthostate `StateDimension`으로
편입해야 하는지(Capacity→rcl.CapacityState `vocabulary.py:162` 선례). (vii) **truthy-sentinel 구조 봉인을 처음부터
채택**(§4.7·#14 M1 선제)한 것이 과잉인지 적절인지 — `ApprovalResult`를 애초에 bool-불가 타입으로 설계하는 것이
producer 범위 내 유일 구조 방어라는 판정. (viii) **invalidation closure의 불확정⇒확장 규율**(§5.4)이 안전 방향인지
가용성을 과도히 해치는지(over-invalidation은 안전하나 정당 scope 차단) — tie-break 확장이 정확한지. (ix) core 6행이
실제로 전부 L1-decidable substrate를 갖는지(특히 004 `+Security`[parser-differential digest]·009/011 `+Broker`
[broker ambiguity/ACK 의미]의 L1 부분과 +overlay 분리가 정확한지). (x) **independent validation**(§6.1)을 "구조적
슬라이스(proposer-only≠independent·common-mode 선언 완비)"로만 L1화하고 실 recompute·common-mode 격리를 +Security
런타임 이연한 경계가 정확한지 vs 일부 common-mode 판정이 L1-decidable인지.

