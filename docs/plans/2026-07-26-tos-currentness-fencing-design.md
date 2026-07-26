# 설계 문서 #23 — Active Currentness·Revocation·Egress Admission Fencing 계약 (2026-07-26, v1.1)

> ADR-002-024 (Active Currentness, Revocation, and Final-Egress Admission Fencing — "CUR")를
> Phase 1(EV-L1) 설계 계약으로 실현한다. **이 문서가 실현하는 것은 시리즈의 "집계자(aggregator)"**다:
> §9 Safety Currentness Vector는 environment·authority·profile·deviation·incident·monitoring·
> release·post-trade·time·recovery·context·constraint·construction·approval·risk·flow·egress-
> identity 등 **~20개 dependency 차원을 하나의 immutable 벡터로 집계**하고, 그 **완전성(completeness)**을
> 판정한다. 형제 패키지(venue·iap·capsule)는 각자 **자기 decision 한 차원의 egress-currentness
> 슬라이스만** 소유하고(코드 실측: venue `__init__.py:17` "active currentness is ADR-002-024-owned";
> egress `predicates.py:13` "venue / iap / capsule own their per-decision egress-currentness and CUR
> (not landed) owns the complete-vector aggregation"), **complete-vector 집계는 CUR 몫으로 이연**되어
> 있었다. 본 계약은 그 이연을 회수한다.
>
> **이 문서의 두 최대 위험은 서로 반대 방향이다.** (1) **over-realization**: per-send 트랜잭션·fence
> commit·claim/fence/first-byte race·partition·actual quorum·latch enforcement·wall-clock age를 L1으로
> 오주장하는 것 — 전부 L2+/런타임/+Security. (2) **duplication/over-reach**: ~20개 차원의 *비즈니스
> 내용*을 CUR가 재판정하는 것 — 각 차원 owner의 verdict/digest를 **주입 소비**만 하고 재저작하지
> 않는다(§1 line 21 verbatim: "A currentness sequencer validates and orders owner-issued facts; **it does
> not invent facts, decide business safety, mutate capacity, issue Live Authorization, classify
> protection, or transmit.**"). L1은 **차원 present 여부·generation floor `>=`·단일 revision 정합·proof
> 구조 완전성**만 판정한다.
>
> **비준 기록: 2026-07-27 운영자 위임 자동 비준(v1.1; 2026-07-25 지시 — 독립 비평 리뷰 REVISE[CRITICAL 0·
> MAJOR 3·MINOR 2]의 minimal edit set 전량 반영·오케스트레이터 검증 후 집행. v1.1: MAJOR-1 phantom
> `resolve_restrictive_latch`→실재 `monotonic_denial_no_revival`[egress predicates.py:519]·MAJOR-2
> `DimensionKey`에 `CONTEXT` 추가[§9:259가 Critical Input과 별개 차원으로 명시 — 누락 시 노른자
> `vector_complete`가 CONTEXT-결여 벡터를 공허 통과]·MAJOR-3 §6.6 음극성 `is not True`→`is False` ×2
> [#22 MAJOR-2 재발 봉인]·`mandated` floor 고정·§7.2 3-원천 정합 property. 판단 지점: `tos.cur` 명명·
> edge 0·라치 egress-소유 유지[리뷰 판정 "정직한 deferral"] 채택. 효력: `tos/src/tos/cur/` Phase 1
> 착수).** 본 문서는 GOV-001의 세 거버넌스 행위(비준 / ADR
> acceptance / live authorization) 중 어느 것도 수행하지 않는다. tos-spec을 수정하지 않으며 어떤
> CUR-EV/CUR-AC/acceptance/비준도 선언하지 않는다. 기존 `docs/plans/**` 무수정. 세션 B 미비준 문서
> 인용 없음.

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. **패키지 명명** `tos.cur`(register prefix `CUR` 소문자 1:1·terse-lowercase 관행; §0.4a). runner-up
   `tos.currentness`(기각·§10.1). naming은 load-bearing 아님(§7.1 allowlist가 미래 형제 자동 배제).
2. **핵심 아키텍처 판정 — CUR = complete-vector *집계자*·형제는 per-decision *leaf*.** 형제 코드가 스스로
   증언하는 이연을 회수한다(§0.4b·§3.5). venue `egress_currentness_active`·iap `active_egress_currentness`·
   capsule `egress_currentness_ok`는 **각자 자기 한 차원**의 currentness leaf; CUR `SafetyCurrentnessVector`는
   **전 차원 present + 단일 revision + floor**의 집계 완전성. **미표현 차원·mixed-revision·policy under-
   declaration은 어떤 leaf도 탐지 불가 — 집계자만 탐지**(§5.1 노른자·완전성의 환원 불가성).
3. **EV 3분류(행별 정직)** — **core(L1-floor) 1행 {CUR-EV-001 Complete Exact Vector `EV-L1/3`}**(**시리즈
   최소 core tier — #22의 2행보다 얇음**) / **predicate-only 9행 {002·003·004·007·008·009·010·011·012}**(전부
   `EV-L2/3±`) / **not-Phase-1 2행 {005 Claim/Fence/First-Byte Race·006 Partition `EV-L3+Security`}**. **닫는
   CUR-EV = 0건**(§1). "EV-L1-complete 주장 금지".
4. **중심 L1 술어(§5)** — `vector_complete`(노른자·CUR-EV-001) + 지지 술어 `dimension_positively_
   established`·`no_forbidden_placeholder`·`single_revision_consistent`·`policy_covers_mandated_dimensions`.
   전부 순수·fail-closed·전 차원 verdict/digest는 주입.
5. **over-realization + duplication 이중 경계 명시(§1·§6b·§6c)** — per-send transaction(§13)·fence commit·
   local deny sequence(§11)·claim/fence/first-byte race(§14)·partition/quorum(§15)·actual quorum
   consensus·latch enforcement·wall-clock age(`MAX_*_age_ms`)는 **전부 L2+/런타임/+Security**; ~20개 차원의
   비즈니스 내용은 **전부 형제 소유·주입 소비**. L1은 present/floor/revision/structure 판정만.
6. **소유권/seam 분할표(§3.5) — 본 문서 최대 함정.** venue/iap/capsule(per-decision leaf·소유)·egress
   (QCC + RestrictiveLatchState + 라치 resolver·소유)·authority(epoch floor·non-revival 선례)·time(freshness
   축·`freshness_verdict` 소유)·spg(bundle_complete 완전성 선례·profile generation 차원)·rcl(capacity/
   capability·commit-proof 좌표)·는 **CUR가 재저작하지 않는다**. **sibling edge 0**(§3.4).
7. **선제 봉합** — ∅ 양방향(policy·required set 부재 ⇒ deny)·집합 양방향(subset 검사 both-ways)·truthy-
   sentinel 구조 봉인(`__bool__ ⇒ TypeError`)·all-false currentness authority·malformed-model 자기방어
   (validator + 술어 2층·#20 상속)·**극성 규율 전 적용(음극성 `is not False`·양극성 `is not True`·#22
   MAJOR-2 재발 방지)**·**그룹 reconcile(전-entry 보수·MAX floor·#22 MAJOR-1 재발 방지)**·금지 동사 canary(§4).

### 0.2 하지 않는 것 (경계·NO 목록)

- **~20개 차원 owner 로직 재저작 금지(duplication 경계·본 문서 특유 최대 위험).** spg profile validity·
  are aggregate-risk decision·afg action-flow permit·iap approval consumption·ioc conformance·venue
  admissibility·capsule CII·liveauth Live Authorization·rcl capacity/capability·authority epoch·time
  freshness·029/030 governance generation을 **재판정하지 않는다** — 각 owner verdict/generation/digest를
  **주입 좌표**로만 소비(§1 line 21·§7 SoD).
- **per-send admission runtime 재구현 금지(over-realization 경계).** §13 8-step 트랜잭션·§11 fence commit +
  deny-first sequence·§14 race·§15 partition·§16 cross-domain barrier·§18 wall-clock age는 **전부 L2+/런타임**.
  L1은 **주입된 좌표 위의 순수 completeness/floor/structure** 술어만.
- **egress `RestrictiveLatchState` + `monotonic_denial_no_revival` 재저작 금지(§0.4d; v1.1 MAJOR-1 —
  "resolve_restrictive_latch"는 phantom, 실재 resolver는 `monotonic_denial_no_revival`).** Local Restrictive
  Latch의 **state machine + monotonic resolver는 egress(#22) 소유**(Final Egress Trust Boundary = ADR-002-013
  turf). CUR는 라치 상태를 **주입 `local_latch_clear: bool | None`(`is True`)로 소비**. CUR-EV-003(Independent
  Local Deny)은 `EV-L2/3+Security` = **L1 아님**.
- **egress `QuorumCommitCertificate` 재저작 금지(§0.4c).** QCC(quorum commitment aggregation)와 CUR
  `EgressCurrentnessProof`(currentness conformance)는 **다른 축**. QCC가 `egress_currentness_proof_id`를
  bound claim으로 **carry**(egress가 CUR 소비·역방향 아님).
- **actual quorum consensus·cryptographic signature·durability 검증 금지** — 전부 +Security(주입 verified-flag).
- **수치 하드코딩 금지(§8)** — `B_currentness_gap_to_local_deny`·`B_restrictive_fence_commit`·`B_currentness_
  fence_to_egress`·`B_currentness_proof_issue`·`B_currentness_generation_fence`·`MAX_egress_currentness_proof_
  age_ms`·`MAX_currentness_vector_age_ms` 전부 Profile INSTANCE 측정·주입(현재 전부 `null`).
- **미착지 상류 코드 인용 금지** — RLP(-025)·WDR(-026)·SIR(-027)·STM(-028)·SCI(-029)·PTF(-030) 미착지
  (`tos/src/tos/` 하 부재 실측). §9의 026/027/028/029/030 차원은 **ADR 원문만·verdict/generation 주입·코드
  인용 0**(phantom 봉합·§0.4f). 세션 B 미비준 문서 인용 없음.
- **EV/acceptance/비준 선언 금지.**(EV·acceptance 미선언; 문서 비준 자체는 운영자 위임 자동 비준 v1.1) tos-spec 수정 금지·
  기존 docs/plans 무수정.

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

`tos.cur`는 **순수 모델·술어 패키지**다: `pydantic` + stdlib + `tos.canonical`(digest substrate) +
`tos.ordering`(generation 순서)만 import. `shared.*`·`services.*`·`cli.*`·`numpy`/`pandas`/`yaml`·
`os.environ`·동적 escape(`exec`/`eval`/`importlib`/`__import__`) **전면 부재**. **형제 tos 패키지(rcl·ioc·
evidence·capsule·venue·iap·are·afg·sbr·hag·liveauth·protective·recon·brokercap·authority·orthostate·spg·
dsl·time·replacement·egress·nontrade + 미래 rlp/wdr/sir/stm/sci/ptf) 전부 import 부재** — 형제 상호작용은
**주입 scalar/digest/bool/verdict/enum-token**으로만(sibling edge 0·§3.4). clock·network·egress·persistence
미접근(§5.4 currentness revision은 ordering identity이지 wall-clock 아님 — CUR는 clock-free). `tos/tests/cur/
test_cur_import_closure.py`가 import-closure를 allowlist(`closure ⊆ {canonical, ordering, cur}`)로 강제하고
`tools/tos_firewall_check.py` required check와 함께 green이어야 본 선언이 능동 성립(§7.1).

### 0.4 REUSE / import / 경계 결정 요지 (핵심 아키텍처)

**(a) 패키지 명명 = `tos.cur` (register-prefix 1:1·저마찰).**

- **선택(권장) `tos.cur`** — 근거 3중:
  1. **register prefix 1:1**: 시리즈가 `CUR-INV`/`CUR-AC`/`CUR-EV`를 사용(register 실측 md line 312-323·
     csv line 281-292·ADR §6/§25). terse-lowercase 관행(rcl·spg·iap·hag·are·ioc·afg·sbr·egress — 전부
     register prefix lowercase)과 정합. `cur`는 register prefix를 그대로 소문자화한 head.
  2. **충돌 없음**: `cur`는 미점유(현 27패키지 실측 — afg·are·authority·brokercap·canonical·capsule·dsl·
     egress·evidence·hag·iap·ioc·liveauth·nontrade·ordering·orthostate·protective·rcl·recon·replacement·
     sbr·spg·time·venue).
  3. **seam 토큰 정합**: 도메인 아티팩트명이 이미 형제 코드에 고정 — venue/iap/capsule `egress_currentness_*`·
     egress `RestrictiveLatchState`·§11.1 QCC `egress_currentness_proof_id`. `tos.cur`가 이 앵커와 정합.
- **runner-up `tos.currentness`(기각)** — 근거: full-word 관행(liveauth·brokercap·orthostate·protective·
  replacement·nontrade)도 존재하나, register-prefix 1:1(egress/hag/sbr가 최근 선례)이 더 강한 최근
  관행이며 `cur`가 seam 토큰(`egress_currentness_proof_id`의 `cur` 접두 정합)과 맞다. **§10.1 운영자 판단
  지점**: `tos.cur` 채택.

**(b) CUR = complete-vector 집계자; venue/iap/capsule = per-decision leaf (본 문서 최대 판정·재저작 금지 경계).**
이것이 본 계약의 **핵심 아키텍처 결정**이며, **형제 코드가 스스로 CUR로 이연했음을 증언**한다.

- **결정적 코드 증언 3중(실측)**:
  1. venue `__init__.py:17` verbatim: "trustworthy time is time-owned, **active currentness is
     ADR-002-024-owned**, and protective classification is protective-owned. VTG **consumes** every one of
     those as an injected produced scalar / bool / enum-token / verdict / digest and **re-authors none** of
     them."
  2. egress `predicates.py:13` verbatim: "venue / iap / capsule own their per-decision egress-currentness
     and **CUR (not landed) owns the complete-vector aggregation** (§0.4f)."
  3. venue `predicates.py` `egress_currentness_active` docstring verbatim: "The active-currentness protocol is
     **ADR-002-024 runtime** (+Security, §6.3); L1 is the order-comparison + active-establish predicate only."
- **실측 사실(형제가 per-decision leaf를 이미 소유)**:
  - venue `egress_currentness_active(current_actively_established, request_generation, current_generation)`
    (`predicates.py:493`, VTG-EV-007·predicate-only §6.3) — **단일 Constraint Generation** currentness leaf
    (`current_actively_established is not True: return False` + `request_generation == current_generation`
    exact-equality — 자기 한 차원).
  - iap `active_egress_currentness(active_bounded_proof, inferred_from_absence, ...)`(`predicates.py:578`,
    IAP-EV-008·§6.4) — **단일 approval-consumption** currentness leaf(active bounded proof AND not
    inferred-from-absence).
  - capsule `egress_currentness_ok(...)`(`predicates.py:656`, CII-EV-009·§7) — **단일 capsule** currentness leaf.
- **⇒ CUR가 소유하는 잔여(형제가 이연한 것)** = **§9 complete-vector 집계 + 완전성 판정**:
  1. **§9 전 차원 present**(CUR-EV-001) — ~20개 §9-mandated 차원이 벡터에 **positively established**로 전부
     존재하는지. **미표현 차원 ⇒ incomplete ⇒ deny**(spg `bundle_complete`·hag unrepresented-principal
     동형·§5.1). **어떤 leaf도 미표현 차원을 탐지 불가**(각 leaf는 자기 차원만 봄) — 집계자만 가능.
  2. **§9 단일 revision 정합** — 전 차원이 벡터의 **한 Currentness Revision**에 있는지(§5.3 "at one
     Currentness Revision"·§9 line 266 "cannot use... mixed revisions"). **cross-dimension 판정 — leaf
     불가**(§5.3).
  3. **§8/§9 policy 완전성** — policy `required_dimensions ⊇ §9 mandated`(under-declaration 봉인·§8 "Unknown
     materiality is material"). **leaf 불가**.
  4. **§10 per-dimension floor** — `bound_generation >= restrictive_floor`(§10 line 278·predicate-only).
  5. **§12 EgressCurrentnessProof 구조**(CUR-EV-004·predicate-only) — proof가 §12 전 필수 claim carry.
- **재저작 금지 경계(엄격)**: CUR는 venue/iap/capsule의 per-decision currentness leaf를 **재저작·import하지
  않는다**. 각 leaf verdict(`positively_established: bool`)가 CUR 벡터의 **차원 좌표로 주입**된다(계층 병렬).
  **CUR-EV-001 L1 잔여 = 완전성(전 차원 present + 단일 revision + policy 완전 + no-placeholder)의 저작**이지
  차원 owner 로직 재구현이 아니다(§5.1). **리뷰어 공격 지점(§10.2-①)**: "CUR가 leaf를 단순 AND" — 반론:
  완전성은 leaf의 AND가 아님(미표현 차원·mixed-revision·policy under-declaration은 leaf-AND로 탐지 불가·집계
  고유 축·spg/hag 완전성 선례).

**(c) egress = QuorumCommitCertificate 소유; CUR = EgressCurrentnessProof 소유 (§11 vs §12 경계·재저작 금지).**
**실측 인접**: egress(#22, 착지)가 `QuorumCommitCertificate`(§11 aggregating 아티팩트)·`CommitProofValidity`
{VALID/INVALID/UNKNOWN}를 소유. §11(QCC)과 §12(ECP)가 "egress boundary proof"로 표면상 인접이라 **재저작 함정**.

- **판정: 축이 다르며 013이 024로 명시 이연**. ADR-002-013 §11.2 step 14 verbatim(egress 코드가 인용):
  "verify under **ADR-002-024** that one **complete Safety Currentness Vector** satisfies every restrictive
  floor... and that the local restrictive latch is positively established as `CLEAR`." ⇒ **013(egress)이
  024(CUR)의 complete-vector를 verify**하고, QCC §11.1이 `egress_currentness_proof_id`(024/CUR)를 bound
  claim으로 **carry**.
- **경계 분할**: **egress 소유** = QCC = *quorum commitment aggregation*(rcl commit-proof 좌표 + §11.1
  claim-set + egress generation + signer 좌표·result `CommitProofValidity`). **CUR 소유** = `EgressCurrentness
  Proof` = *currentness conformance fact*(complete vector가 전 restrictive floor + latch를 claim revision에서
  만족·result `ProofResult`{CURRENT/RESTRICTED/UNKNOWN}·§12). 두 축 직교. QCC가 ECP-id를 carry(egress→CUR
  소비·역방향 아님).
- **⇒ CUR는 QCC·`CommitProofValidity`를 재저작·import하지 않는다.** **리뷰어 공격 지점(§10.2-②)**: "ECP =
  QCC 중복" — 반론: QCC=quorum 커밋 축(013·result VALID/INVALID), ECP=currentness conformance 축(024·result
  CURRENT/RESTRICTED)·§11.2 step 14가 013→024 이연 **명시**·QCC가 ECP-id carry.

**(d) egress = Local Restrictive Latch state machine 소유; CUR = 라치 상태 주입 소비 (§5.7/§11 seam·재저작 금지).**
**실측 인접**: egress(#22)가 `RestrictiveLatchState{CLEAR, DENY_LATCHED}`(`vocabulary.py:119`, `__bool__ ⇒
TypeError`)·`monotonic_denial_no_revival(latch_state, injected_events)`(`predicates.py:519`, monotonic deny·`None ⇒
DENY_LATCHED`)를 소유. ADR-002-024 §5.7이 Local Restrictive Latch를 **CUR §5 Definitions에서 정의**(states
CLEAR/DENY_LATCHED/**UNKNOWN**)하여 **재저작 함정**이다.

- **판정: 정의는 CUR(§5.7), state machine + enforcement는 egress(013 Final Egress Trust Boundary)**. §5.7
  verbatim: "A monotonic fail-closed state **inside the Final Egress Trust Boundary**." Final Egress Trust
  Boundary = ADR-002-013 turf ⇒ **라치 state machine + monotonic resolver는 egress 소유**(#22 착지). CUR-EV-003
  (Independent Local Deny)은 `EV-L2/3+Security` = **L1 아님** ⇒ 라치는 **CUR L1 산출물이 아님**.
- **⇒ CUR는 `RestrictiveLatchState` enum·`monotonic_denial_no_revival`을 재저작·import하지 않는다.** CUR는
  라치 상태를 `EgressCurrentnessProof`의 **주입 좌표 `local_latch_clear: bool | None`(`is True` ⇒ CLEAR)**로
  소비(§5.7 "**positively established** `CLEAR`"·양극성). **seam note**: §5.7의 3-state(UNKNOWN 포함)는
  egress의 2-state + `None ⇒ DENY_LATCHED`(egress `predicates.py:530`)로 **행위적 등가**(UNKNOWN ⇒ deny =
  None ⇒ deny). egress 무수정. **리뷰어 공격 지점(§10.2-③)**: "CUR가 라치 재저작" — 반론: state machine =
  egress(enforcement boundary)·CUR는 주입 소비·CUR-EV-003 L2+·edge 0. **§10.1 운영자 판단 지점**: 라치
  소유를 egress에 두고 CUR가 소비(대안: CUR로 이관 — 기각 근거는 §5.7 "inside Final Egress Trust Boundary" +
  #22 착지).

**(e) authority = epoch floor + non-revival 선례; time = freshness 축 (generation 좌표 경계·재저작 금지).**

- **authority(ADR-002-003)**: `authority_epoch_current(claimed_epoch, domain, state)`(`predicates.py:119`,
  `claimed_epoch >= current_epoch_floor`·any-None fail-closed) — **generation floor `>=` 판정의 shape
  선례**. `recovery_generation_revives_nothing`(`predicates.py:787`) — **non-revival 선례**. **판정**: CUR
  `all_floors_met`은 이 **`>=` shape을 REUSE**(via `tos.ordering.compare_order`)하되, authority epoch은
  **CUR 벡터의 한 차원**(injected). authority는 leaf, CUR는 aggregate. CUR는 `authority_epoch_current`를
  재저작·import하지 않음. **리뷰어 공격 지점(§10.2-④)**: "floor_met = epoch_current 중복" — 반론: authority
  =authority-epoch 한 차원, CUR=전 차원 floor 집계·같은 shape 다른 scope.
- **time(ADR-002-008)**: `freshness_verdict(...)`(`predicates.py:375`, "UNKNOWN is not zero and not fresh") —
  **freshness(wall-clock age) 축 소유**. **판정: freshness ≠ currentness (본 문서 최대 축 함정)**. §5.4
  verbatim: "**Currentness Revision... is an ordering identity, not wall-clock time** and not proof that
  unobserved external facts do not exist." ⇒ **time = freshness(age·wall-clock), CUR = currentness(committed
  ordering revision floor)**. time의 Trustworthy Time generation은 **CUR 벡터의 한 차원**(injected). CUR가
  소유하는 `MAX_egress_currentness_proof_age_ms`·`MAX_currentness_vector_age_ms`(wall-clock age)는 **secondary
  belt-and-suspenders guard**로 **+Security/INSTANCE 이연**(clock 필요) — **primary L1 판정은 ordering-revision
  완전성**. **리뷰어 공격 지점(§10.2-⑤)**: "currentness = time freshness 중복" — 반론: §5.4가 currentness를
  wall-clock 아닌 ordering identity로 **명시 분리**·time gen은 CUR의 한 차원·age는 secondary +Security.

**(f) 미착지 상류 026/027/028/029/030 차원 (phantom 봉합).** **실측**: `tos/src/tos/` 하 rlp·wdr·sir·stm·
sci·ptf **부재**(ls 확인). §9가 Deviation(026)·Incident(027)·Monitoring(028)·Release(029)·Post-Trade(030)
generation을 벡터 차원으로 요구.

- **판정: CUR는 이들을 주입 generation/digest 좌표로만 소비.** ADR 원문(§9 line 253-257)만 참조하고 **코드
  인용 0**(미착지 — phantom 금지). §9 conditional 025(trial) 차원(line 258)도 **opaque optional scalar 필드군**
  으로 수용하고 내용 검증은 RLP(-025, 미착지) 이연(§9.2 item). **리뷰어 공격 지점(§10.2-⑥)**: "미착지 차원을
  substrate로 오인용" — 반론: ADR 원문만·코드 0·주입 좌표·§0.2 NO-list.

**(g) rcl·liveauth·spg·ioc·afg·are·brokercap·recon 경계 (전부 verdict 주입 소비·§3.5 표).**

- **rcl(ADR-002-002/012)**: capacity mutation·`TransmissionCapability`·`claim_capability`·commit-proof 좌표
  소유. §7 table verbatim: "Mutate capacity | none | **RCL only** | currentness components cannot reserve,
  transfer, quarantine, or release." ⇒ CUR는 capacity 불변·RCL commitment을 **주입 좌표**로 소비(§13 step 4).
- **spg(ADR-002-014)**: `bundle_complete`·`missing_config_denies`(`predicates.py:818/857`, "not
  bundle_complete") — **완전성 선례**. Currentness Policy 활성화는 spg/014-governed(§5.1·§8 line 241). CUR는
  policy **content model**(required_dimensions 선언)을 저작하고, **활성화/generation은 spg verdict 주입 소비**.
- **liveauth·ioc·afg·are·brokercap·recon**: Live Authorization·conformance·action-flow permit·aggregate-risk·
  broker profile·external-activity — 전부 형제 소유·CUR 벡터 차원으로 주입 소비(§3.5).

**(h) 앵커 규약 — CUR-INV/AC/EV 앵커, 새 시리즈 창작 금지.** **실측**: ADR-002-024는 자체 시리즈
**`CUR-INV-001..015`(§6 line 141-199, 15종)·`CUR-AC-001..012`(§25 line 558-604, 12종)·`CUR-EV-001..012`
(register csv line 281-292, 12행)**를 정의한다. §25 preamble(line 556 verbatim): "The following cases are
mandatory and **map one-to-one to `CUR-EV-001` through `CUR-EV-012`**. Written cases are not completed
evidence." 본 계약은 모델 불변식·술어를 **`CUR-INV-###`/`CUR-AC-###`/`CUR-EV-###`/§-clause/`SAFE-###`
(§26 traceability line 610-621)**에 앵커하고 **새 시리즈를 창작하지 않는다**. #12–#22 동형.

---

## 1. 범위 매핑 — ADR-002-024 조항별 EV-L1 도달성 (닫는 CUR-EV 0건)

EV-level 정의(VER-002-001): **EV-L1 = Model and Property Verification**(state-machine exploration, model
checking, property-based testing, deterministic simulation). **EV-L2 = Component Fault Test**, **EV-L3 =
Integration/Adversarial**, **+Security = 독립 security-boundary assessment**, **+Broker = broker-capability
실측**. Phase 1은 EV-L1만이다.

> **결정적 사실 1 — CUR-EV core 1행(시리즈 최소 core tier)**: register 실측 histogram(csv line 281-292):
> **core(L1-floor) 1행 = {001 Complete Exact Vector [`EV-L1/3`, csv:281]}**. **predicate-only(≥ L2) 9행 =
> {002 Restrictive Fence Dominance·003 Independent Local Deny·004 Per-Send Proof·007 Stale Generation·009
> Authority/Capacity Separation·012 Recovery/Non-Revival [`EV-L2/3+Security`]·008 Multi-Domain [`EV-L2/3`]·010
> UNKNOWN/Economic·011 Protective Confinement [`EV-L2/3+Broker`]}**. **not-Phase-1(L3+) 2행 = {005 Claim/Fence/
> First-Byte Race·006 Partition [`EV-L3+Security`]}**. **닫는 CUR-EV = 0건**. `EV-L1/3`(001)은 *staged* L1
> **및** L3을 모두 요구하므로 Phase-1 L1 모델·property test는 001을 **닫지 못한다**.
>
> **결정적 사실 2 — authoring ≠ acceptance (닫는 CUR-EV = 0건)**: (a) core 1행조차 `/3`(integration/
> adversarial) 잔여, (b) predicate-only 9행은 최소 ≥ L2, (c) not-Phase-1 2행은 L3+ 런타임, (d) VER-002-001 §5
> "Registration is not execution"·ADR §25 line 556 "Written cases are not completed evidence"·§28 line 665
> "Authorship... does not satisfy this gate". ⇒ **"EV-L1-complete 주장 금지"**(#12–#22 §1 규율 상속). Owner/
> Reviewer는 register상 TBD·status NOT_IMPLEMENTED(전 12행).

**규율 태그(모든 주장에 부착)**: "**structural/coordinate/completeness predicate substrate only; CUR-EV-001..012
전부 NOT_IMPLEMENTED — core 1행(001)은 `/3` 통합·adversarial 대기, predicate-only 9행은 component-fault
L2·+Security/+Broker 대기, not-Phase-1 2행(005·006)은 런타임 race/partition(+Security). EV-L1-complete 주장
금지·차원 owner 로직·per-send transaction·fence commit·latch enforcement·wall-clock age는 재저작/런타임/
+Security. L1은 present/floor/revision/structure 판정만.**"

**CUR-EV core 1행 ↔ AC(1:1) ↔ ADR 조항 매핑(실측)**:

| CUR-EV | register 제목(verbatim, csv line) | 최소 레벨 | CUR-AC(1:1) | ADR 조항 앵커 | L1 substrate 술어(§5) |
|---|---|---|---|---|---|
| **001** | Complete Exact Vector (281) | `EV-L1/3` | AC-001(§25) | §9 Vector Contract·CUR-INV-001 | `vector_complete`+`dimension_positively_established`+`single_revision_consistent`+`no_forbidden_placeholder`+`policy_covers_mandated_dimensions`(§5.1-5.5 — 노른자) |

**ADR-002-024 조항 → Phase-1 분류(core / predicate-only / not-Phase-1)**:

| ADR 조항 | 요지 | Phase-1 분류 | L1 substrate / 소유 (근거) | CUR-EV |
|---|---|---|---|---|
| **§9** (line 247-268) | complete action-scoped vector·전 차원 present·단일 revision·no-placeholder | **core (L1 슬라이스)** | `vector_complete`(§5.1) — 전 §9 차원 present + 단일 revision + policy 완전 + no wildcard/null-as-current/mixed. ~20개 차원 verdict/digest는 **주입 소비**(재저작 금지·§3.5). **완전성 = 집계 고유 축**(leaf-AND 불가·§0.4b). | **001** |
| **§8** (line 225-241) | Currentness Policy·dependency scope·materiality | **core 지지 (L1 슬라이스)** | `policy_covers_mandated_dimensions`(§5.5) — policy `required ⊇ §9 mandated`(under-declaration 봉인·"Unknown materiality is material"). policy 활성화는 spg/014 주입(§0.4g). | **001** |
| **§10** (line 273-280) | owner publication·generation floor·restrictive-only-sufficient | **predicate-only (≥ L2)** | `all_floors_met`(§6.1·`bound_generation >= restrictive_floor`·authority `>=` shape REUSE)+`restrictive_floor_reconciled`(§6.2·MAX floor·MAJOR-1)+`conflicting_owner_restricts`(§6.3·union scope). 실 owner-auth/ingress는 +Security. | **002** |
| **§11** (line 285-300) | restrictive fence commit·deny-first·local latch | **predicate-only (라치=egress 소유)** | `RestrictiveFenceRecord` model + floor advance(§6.4). 라치 state machine + deny-first sequence는 **egress 소유(#22)·CUR 주입 소비**(§0.4d). 실 fence commit는 런타임. | **002·003** |
| **§12** (line 305-318) | egress currentness proof 구조·single-use·CURRENT-only | **predicate-only (≥ L2)** | `proof_structurally_complete`(§6.5)+`proof_admissible`(§6.6·`result is CURRENT` + latch_clear + single-use). 실 per-send 트랜잭션은 §13 런타임·+Security. | **004** |
| **§13** (line 322-337) | normal per-send admission 8-step 트랜잭션 | **not-Phase-1 (런타임)** | linearizable transition(step 3-5)·claim+proof+SEND_STARTED atomic은 **런타임**. L1 model property 없음(순서 제약은 §6b 얇은 모델). | (런타임) |
| **§14** (line 341-352) | claim/fence/first-byte race·potentially-live | **not-Phase-1 (race timing)** | 순서 permutation model(§6b·FENCE<CLAIM deny 등). 실 race timing·`B_*` bound·no-blind-retry는 +Security. | **005** |
| **§15** (line 356-364) | partition·quorum·broker-reachable | **not-Phase-1 (런타임)** | broker-reachable ↛ authority model property(§6b). 실 quorum·partition은 +Security. | **006** |
| **§16** (line 368-378) | multi-domain·shared scope·no-union·parent/child | **predicate-only (reconcile)** | `multi_domain_no_union`(§6.7·독립 proof 미합집합)+`parent_child_floor_monotone`(§6.8). ordering REUSE. 실 cross-domain barrier는 런타임. | **008** |
| **§17** (line 383-393) | degraded protective·lease/reserve | **predicate-only (protective 경계)** | protective `ProtectiveLeaseAdmissibilityScope`+rcl reserve+authority lease-exclusivity **소유**(§0.4g). CUR는 verdict 주입·label≠authority(§6.9). `EV-L2/3+Broker`. | **011** |
| **§18** (line 397-408) | expiry/invalidation·economic continuity | **predicate-only (극성 봉합)** | `expiry_denies_future_use_only`(§6.10·`is_expired is True` ⇒ future deny, **capacity 불변**·CUR-INV-012)+`unknown_preserves_capacity`(§6.11). | **010** |
| **§19** (line 412-420) | failover/restore/recovery·non-revival | **predicate-only (non-revival)** | `recovery_revives_nothing`(§6.12·authority 선례 동형·restore ⇒ UNKNOWN + latch DENY). 실 hard-fence는 +Security. | **012** |
| **§7 SoD·§20 security·§21 evidence·§22 failure·§27 open Q·§28 gate** | authority 분리·security·evidence·수치·acceptance | **not-Phase-1 (Phase-0/INSTANCE·런타임)** | `all_false_currentness_authority`(§6.13·CUR-INV-005). 제품·수치·security review·acceptance는 §9.2 Phase-0. | **009** |

---

## 2. 데이터 모델 계약

### 2.1 digest-bound / value / reference 분류

| 분류 | 모델 | 근거 |
|---|---|---|
| **digest-bound `IndependentIdArtifact`** (id ⊥ digest) | `SafetyCurrentnessVector`(§9 집계 아티팩트)·`EgressCurrentnessProof`(§12 single-use proof)·`RestrictiveFenceRecord`(§5.5/§11 monotonic floor advance)·`CurrentnessPolicy`(§5.1/§8 governed policy) | append-only ledger citizen(§21 evidence·§9 line 264 "canonical vector digest and signature or equivalent integrity evidence"·§12 line 314 "proof identity, nonce, single-use state... integrity evidence"). same-id/different-bytes 위조/replay를 `classify_record_pair` CRITICAL_CONFLICT로 탐지(§3.1). id는 서비스 부여(≠ `f(digest)`). |
| **value (frozen, id 없음)** | `CurrentnessDimension`(dimension_key·owner·bound_generation·bound_digest·restrictive_floor·positively_established·at_revision — 벡터 차원 좌표)·`CurrentnessRevision`(§5.4 committed ordering identity·wall-clock 아님)·`EgressProofCoordinateSet`(주입된 egress-scope 좌표 mirror — principal/credential/route/session/`local_latch_clear` — 검증 대상, egress 재저작 아님) | id 미도출·mutate 없음. `EgressProofCoordinateSet`는 egress 소유 좌표를 **주입 입력**으로 받는 value(§0.4c/d). |
| **enum-token (`_NonTruthyStrEnum`)** | `ProofResult`{CURRENT/RESTRICTED/UNKNOWN}·`CurrentnessAdmission`{ADMIT/DENY} | 어휘(§2.2). `__bool__ ⇒ TypeError`(truthy 봉인). |
| **closed StrEnum (truthy-untestable 불요·구조 vocabulary)** | `DimensionKey`(§9 mandated 차원 catalogue — 구조 vocabulary, numeric 아님) | §9 열거 차원의 closed 식별자. **숫자 하드코딩 아님**(§8 — 구조 dimension key ≠ threshold/bound). |
| **reference (scalar/digest only, 주입)** | 전 차원 owner verdict/generation/digest: spg profile gen·authority epoch/revocation/HALT gen·liveauth Live Auth·time Trustworthy Time gen·recon·capsule Context gen·venue Constraint gen·ioc Construction gen + conformance·are Aggregate Risk gen·afg Action Flow gen + permit·iap Approval gen·rcl capacity commitment + `TransmissionCapability` + commit-proof 좌표·egress Egress Generation + principal/credential/route/session + `local_latch_clear` + `egress_currentness_proof_id`·**026/027/028/029/030 governance generation(미착지·주입)**·conditional **025 trial claims(미착지·주입)** | 형제 소유 — 주입 scalar/digest/verdict로만 참조(§3.4/§3.5). CUR는 이들을 저작·import하지 않음. **025/026/027/028/029/030은 미착지 — ADR 원문만·코드 인용 0(phantom 봉합·§0.4f).** |

### 2.2 어휘 (verbatim 전사 + truthy 봉인)

**(1) `ProofResult` (§12, non-truthy StrEnum — 핵심 truthy 봉인).** `CURRENT`·`RESTRICTED`·`UNKNOWN`.
**`_NonTruthyStrEnum` 로컬 재표현**(iap `vocabulary.py:50` 동형·**import 아님**·`__bool__ ⇒ TypeError`).
**근거**: §12 line 316 verbatim: "The proof result is `CURRENT`, `RESTRICTED`, or `UNKNOWN`. **Only
`CURRENT`**, together with every separately required authority and commitment, can satisfy this one
conformance check." `RESTRICTED`/`UNKNOWN`는 non-empty string이라 `if result:`가 **거부를 truthy로 오독하는
치명적 fail-open**(CUR-INV-011 line 183 "Unknown... blocks new risk"). 소비 게이트는 **`result is
ProofResult.CURRENT` 명시 비교 강제**(§4.7·§7 회귀). `CURRENT itself grants no authority`(§12 line 316 —
all-false·§6.13).

**(2) `CurrentnessAdmission` (§13 최종 verdict, non-truthy StrEnum).** `ADMIT`·`DENY`. **`_NonTruthyStrEnum`**.
`DENY`는 non-empty string ⇒ `if admission:` 오용이 fail-open. 소비: `admission is CurrentnessAdmission.ADMIT`
명시. currentness는 근본적으로 DENY-biased(CUR-INV-011·§CUR-INV-001 line 143 "partial... vectors are denial").

**(3) `DimensionKey` (§9, closed StrEnum — 구조 vocabulary).** §9 열거 차원의 식별자군: `ENVIRONMENT_SCOPE`·
`CURRENTNESS_POLICY`·`COMMIT_LOG`·`SAFETY_AUTHORITY`·`SAFETY_ENVELOPE_PROFILE`·`DEVIATION`·`INCIDENT`·
`MONITORING`·`RELEASE`·`POST_TRADE`·`TRUSTWORTHY_TIME`·`RECOVERY`·`CRITICAL_INPUT`·**`CONTEXT`**(capsule
CII 소유 — §9:259가 Critical Input과 **별개 차원**으로 명시·§26:617 traceability; v1.1 MAJOR-2 —
이 키 부재 시 CONTEXT-결여 벡터가 `vector_complete`를 공허 통과해 노른자가 봉하려는
unrepresented-dimension fail-open을 enum 스스로 발생시켰음)·`CONSTRAINT`·
`CONSTRUCTION`·`TRADING_APPROVAL`·`AGGREGATE_RISK`·`ACTION_FLOW`·`DECISION_PROOF_INTENT`·`EGRESS_IDENTITY`
(+ conditional `RESTRICTED_LIVE_TRIAL`). **truthy 봉인 불요**(비교 대상 아닌 key)이나 closed(§9는 "at least"
floor — policy가 확장 가능·§5.5). **숫자 하드코딩 아님**(§8): 이는 ADR §9가 열거한 **구조 차원 식별자**이지
threshold/bound가 아니다(ioc/spg가 field를 열거하는 것과 동형).

### 2.3 아티팩트 covered + self-exclusion + malformed-model 자기방어 (설계 #4 §3.3·#20 §2.3·#22 §2.3 상속)

- 모든 digest-bound 아티팩트는 `IndependentIdArtifact`(canonical `_base.py`)를 상속 — `_ID_FIELD`(독립 id·
  digest preimage self-exclusion)·`_COVERED_FIELDS`(digest cover)·`_REQUIRED_COVERED`(구조 identity 최소
  필수)를 선언(spg `records.py:344-345`·ioc `records.py:301/357`·rcl `records.py:428` 선례).
- **coordinate 비붕괴(설계 #4 §4.4)**: mutable lifecycle 좌표(proof `single_use_state`·라치 상태 주입값)는
  covered digest에 **미포함** — 정당한 전이가 digest를 바꿔 same-id/different-bytes CRITICAL_CONFLICT로
  오탐되지 않도록. 현재 상태는 술어에 주입·별도 append-only record.
- **malformed-model 자기방어(#20 교훈 — 처음부터)**: `SafetyCurrentnessVector` `model_validator`가 **불완전
  레코드와 "complete" 주장의 공존을 구조로 봉인**. `_REQUIRED_COVERED`(vector_id·currentness_revision·
  policy_id·policy_generation·vector_digest) 중 하나라도 `None`이면 **`ArtifactIntegrityError` at
  construction** — 즉 "완전"을 주장하면서 필수 identity가 비는 벡터는 **애초에 구성 불가**. `vector_complete`
  (§5.1)는 validator 통과 후에도 술어 층에서 재확인(defense-in-depth·`model_construct` 우회 대비). 동일하게
  `EgressCurrentnessProof._REQUIRED_COVERED`(proof_id·nonce·vector_id·vector_digest·committed_revision)·
  `AllFalseCurrentnessAuthority` any-True validator. **리뷰어 공격 지점(§10.2-⑦)**: `model_construct`로 필수
  None 벡터를 만들어 complete-flag를 truthy로 통과시키는 경로 → validator + 술어 2층 봉인.
- **`_REQUIRED_COVERED`는 구조 identity/generation/digest만** — 차원 수·quorum N·age 같은 numeric bound은
  제외(Phase-1 null profile 하에서 아티팩트 구성 가능하도록·§8); 누락 numeric claim은 fail-closed(§4.7).

### 2.4 핵심 모델 필드 골격 (§ref·형제 seam·all-false)

**`SafetyCurrentnessVector`(§9)** — 집계 아티팩트. 필드(전부 주입·검증 대상):
- **identity/revision**: `vector_id`(독립 id)·`currentness_revision: CurrentnessRevision`(§5.4 committed
  ordering identity)·`vector_digest`(canonical)·`policy_id`·`policy_generation`·`policy_digest`·
  `compatibility_manifest_digest`.
- **scope**(§9 line 249): `environment`·`safety_cell`·`capacity_domain`·`account`·`portfolio`·`strategy`·
  `venue`·`session`·`instrument`·`action_class`·`route_scope`.
- **dimensions**: `dimensions: tuple[CurrentnessDimension, ...]`(§9 line 250-262 전 차원 좌표 — spg/authority/
  time/recovery/**critical-input**/context/constraint/construction/approval/risk/flow/incident/monitoring/
  release/post-trade/deviation/egress-identity/decision-proof-intent — v1.1 MAJOR-2: §2.2 enum과 1:1 정합,
  critical-input과 context는 별개 차원). **각 차원 owner verdict/generation/digest는 주입**.
- **conditional trial**(§9 line 258): `trial_claims: TrialClaims | None`(opaque optional — 내용 검증 RLP/-025
  이연·§0.4f).
- **`authority_effect: AllFalseCurrentnessAuthority`**(§6.13 — 벡터는 검증 대상이지 authority 아님).
- `_REQUIRED_COVERED` = {vector_id·currentness_revision·policy_id·policy_generation·vector_digest}
  (malformed-model 봉인·§2.3).

**`CurrentnessDimension`(value·§9)**: `dimension_key: DimensionKey | None`·`owner_identity: str | None`·
`bound_generation: int | None`(ordering scalar)·`bound_digest: str | None`·`restrictive_floor: int | None`·
`positively_established: bool | None`(주입 — owner가 능동 확립·**양극성**·`None`/`False` ⇒ 미확립 ⇒
fail-closed·venue `current_actively_established is not True` 선례)·`at_revision: CurrentnessRevision | None`
(단일 revision 정합용). **`None` ⇒ 미확립 ⇒ 완전성 실패(§5.2)**.

**`EgressCurrentnessProof`(§12)** — single-use currentness conformance fact. 필드:
- `proof_id`·`nonce`·`single_use_consumed: bool | None`(**음극성**·`is True` ⇒ reject reuse)·`issue_revision`·
  `expiry_evidence`·`is_expired: bool | None`(**음극성**·`is not False` ⇒ future-use deny·§6.10).
- `vector_id`·`vector_digest`·`committed_revision`(§12 line 307).
- `bound_generations: tuple[...]`+`restrictive_floors: tuple[...]`(§12 line 308 전 owner generation + floor).
- `egress_coordinates: EgressProofCoordinateSet`(§12 line 310-311 — principal/deployment/credential/signer/
  route/endpoint/broker-session + `local_latch_clear: bool | None`·**양극성**·`is True` ⇒ CLEAR·egress 주입).
- conditional `trial_claims: TrialClaims | None`(§12 line 311).
- `capability_claim_command`+`claim_committed_result`(§12 line 312)·`send_started_revision`+`max_claim_to_send_
  bound_ms: int | None`(§12 line 313·**INSTANCE 주입**).
- `result: ProofResult`(§12 line 316)·`authority_effect: AllFalseCurrentnessAuthority`.
- `_REQUIRED_COVERED` = {proof_id·nonce·vector_id·vector_digest·committed_revision}.

**`RestrictiveFenceRecord`(§5.5/§11)** — monotonic floor advance(predicate-only substrate). 필드:
`fence_id`·`owner_identity`·`affected_scope: frozenset[str]`·`predecessor_floor: int | None`·
`advanced_floor: int | None`(§10 line 278 "advances a minimum accepted generation or terminal denial floor")·
`terminal_denial: bool | None`(**음극성**·`is True` ⇒ terminal)·`fence_digest`·`authority_effect`. 실 fence
commit는 런타임(§11).

**`CurrentnessPolicy`(§5.1/§8)** — governed policy content model. 필드: `policy_id`·`policy_generation`·
`policy_digest`·`required_dimensions: frozenset[DimensionKey]`(§8 dependency-scope closure 선언)·
`compatibility_manifest_digest`·`authority_effect`. **활성화는 spg/014 주입**(§0.4g).

**`AllFalseCurrentnessAuthority`(all-false·§6.13·CUR-INV-005/§7)**: `approves: bool = False`·`mutates_capacity:
bool = False`·`releases_capacity: bool = False`·`issues_authority: bool = False`·`issues_capability: bool =
False`·`classifies_protection: bool = False`·`transmits: bool = False`·`clears_halt: bool = False`·`re_arms:
bool = False`. `model_validator` any-True ⇒ `ArtifactIntegrityError`(rcl `AllFalseAuthority`·liveauth
`LiveAuthorizationEffect` `_base.py:75`·egress `AllFalseEgressAuthority` 동형·**로컬 재표현·import 아님**).
**근거**: §1 line 21·CUR-INV-005 line 159 verbatim: "Currentness sequencing and proof construction create
**no** approval, Intent, capacity, protection, Live Authorization, Transmission Capability, broker permission,
HALT clear, or re-arm authority."

---

## 3. canonical / ordering REUSE + sibling edge 0 + 형제 경계

### 3.1 canonical REUSE

`tos.canonical` **REUSE**(import): `IndependentIdArtifact`(id ⊥ digest base·`__init__.py:31`)·`classify_
record_pair`+`RecordPairKind`{CRITICAL_CONFLICT/IDEMPOTENT_REPLAY/...}(`__init__.py:43` — vector/proof/fence의
append-only 무결성·same-id/different-bytes 탐지)·`CanonicalDecimal`(effect envelope digest용)·`FrozenModel`·
`EVL1ProvisionalCanonicalizer`(digest 결정론). **canonical만이 base 의존**(rcl/ioc/evidence/capsule/egress
선례 동형). **주의**: proof replay-across-attempt 런타임 탐지는 +Security(CUR-EV-004/005) — L1은 `classify_
record_pair` 구조 분류만.

### 3.2 ordering REUSE (generation floor·currentness revision 순서)

`tos.ordering` **REUSE**(import·`__init__.py:24` `compare_order`): per-dimension generation floor 비교
(`bound_generation >= restrictive_floor`·§10)·currentness revision 순서(§5.4)·restrictive floor advance
(§10 monotonic)·parent/child floor(§16). authority `authority_epoch_current`(`>=` floor)·venue
`constraint_generation_monotone` 순서 REUSE 동형. **PROMOTE 0**(신규 core 승격 없음 — canonical/ordering이
충분). **currentness revision은 ordering identity이지 wall-clock 아님**(§5.4·§0.4e) — CUR는 clock-free.

### 3.3 REUSE 요약 표

| 대상 | 결정 | 근거 |
|---|---|---|
| `tos.canonical`(IndependentIdArtifact·classify_record_pair·CanonicalDecimal·FrozenModel·EVL1ProvisionalCanonicalizer) | **REUSE (import)** | base digest substrate·replay/substitution 구조 분류·전 시리즈 선례 |
| `tos.ordering`(compare_order·Ordering·OrderingEvent) | **REUSE (import)** | generation floor `>=`·revision 순서·monotonic floor advance·authority/venue 선례 |
| 형제 tos 패키지 전부(venue·iap·capsule·egress·spg·authority·time·rcl·ioc·afg·are·liveauth·protective·recon·brokercap·sbr·hag·orthostate·replacement·nontrade·dsl + 미래 rlp/wdr/sir/stm/sci/ptf) | **NO import (sibling edge 0)** | 형제 상호작용은 주입 scalar/digest/bool/verdict/enum-token으로만(§3.4) |
| `_NonTruthyStrEnum` | **로컬 재표현 (import 아님)** | iap `vocabulary.py:50` 선례 — 각 패키지 로컬 정의 |
| `AllFalse*Authority` | **로컬 재표현 (import 아님)** | rcl/liveauth/egress 선례 — 각 패키지 로컬 정의 |

### 3.4 sibling edge 0 정책

CUR는 **어떤 형제 tos 패키지도 import하지 않는다.** ~20개 차원 owner의 verdict/generation/digest는 전부
**주입 좌표**(scalar/digest/bool/verdict/enum-token). 이는 (a) 순환 방지(egress가 CUR를 소비하므로 CUR가
egress를 import하면 순환), (b) firewall allowlist(`closure ⊆ {canonical, ordering, cur}`·§7.1), (c) 계층
분리(각 owner가 leaf 산출 → CUR가 aggregate)를 강제한다. **PROMOTE 0**(canonical/ordering 외 신규 core 없음).

### 3.5 소유권 / seam 분할표 (본 문서 최대 함정 — 코드 실측)

| currentness 관련 아티팩트/술어 | 소유 (실측) | CUR 관계 (재저작 금지) |
|---|---|---|
| venue `egress_currentness_active`·`stale_decision_rejected_at_egress`(`predicates.py:493/529`, VTG-EV-007) | **venue** | venue = **단일 Constraint Generation** per-decision leaf. CUR = 그 leaf verdict를 **한 차원**으로 주입 소비·재저작 안 함 |
| iap `active_egress_currentness`(`predicates.py:578`, IAP-EV-008) | **iap** | iap = **단일 approval-consumption** leaf. CUR = 한 차원 주입 소비 |
| capsule `egress_currentness_ok`(`predicates.py:656`, CII-EV-009) | **capsule** | capsule = **단일 capsule** leaf. CUR = 한 차원 주입 소비 |
| **complete-vector 집계·완전성**(§9) | **CUR (신규)** | 전 차원 present + 단일 revision + policy 완전 — **leaf-AND로 탐지 불가·집계 고유 축**(§0.4b·형제 코드가 CUR로 이연 증언) |
| **EgressCurrentnessProof**(§12) | **CUR (신규)** | single-use currentness conformance fact(result CURRENT/RESTRICTED/UNKNOWN) |
| egress `QuorumCommitCertificate`·`CommitProofValidity`(§11 of 013) | **egress (#22)** | QCC = quorum commitment aggregation. **QCC가 `egress_currentness_proof_id`(CUR) carry**(egress→CUR 소비). CUR 재저작 안 함(§0.4c) |
| egress `RestrictiveLatchState`·`monotonic_denial_no_revival`(`vocabulary.py:119`/`predicates.py:519` — v1.1 MAJOR-1 정정) | **egress (#22)** | 라치 state machine + monotonic resolver(Final Egress Trust Boundary=013). CUR = `local_latch_clear` **주입 소비**·CUR-EV-003 L2+(§0.4d) |
| authority `authority_epoch_current`(`>=` floor)·`recovery_generation_revives_nothing`(`predicates.py:119/787`) | **authority** | generation floor `>=` **shape 선례**(compare_order REUSE)·non-revival 선례. authority epoch = CUR 한 차원(§0.4e) |
| time `freshness_verdict`(`predicates.py:375`) | **time** | time = **freshness(wall-clock age) 축**. CUR = **currentness(ordering revision) 축**(§5.4 명시 분리). time gen = CUR 한 차원(§0.4e) |
| spg `bundle_complete`·`missing_config_denies`(`predicates.py:818/857`) | **spg** | **완전성 선례**(`vector_complete` 동형). spg profile gen·Currentness Policy 활성화 = CUR 차원/주입(§0.4g) |
| hag `_graph_completely_resolved`·unrepresented-principal(`predicates.py:169/806`) | **hag** | **미표현-요소 ⇒ deny 선례**(unrepresented dimension ⇒ incomplete·§5.1 동형) |
| rcl capacity mutation·`TransmissionCapability`·commit-proof 좌표 | **rcl** | §7 "RCL only" capacity. CUR capacity 불변·주입 소비(§0.4g) |
| ~20개 차원 비즈니스 내용(spg profile·are risk·afg flow·iap approval·ioc conformance·venue admissibility·capsule CII·liveauth Live Auth·026-030 governance) | **각 형제 / 미착지 owner** | CUR = generation/digest 좌표 주입 소비·**비즈니스 내용 재판정 금지(duplication 경계·§0.2)** |

---

## 4. 술어 규율 (canary·극성·reconcile)

### 4.1 금지 동사 canary (`test_cur_void_canaries.py`)

CUR 모듈은 **순수·비전송·비변이·clock-free**임을 정적 회귀로 봉인한다: `tos/src/tos/cur/**`에 `send`/
`transmit`/`emit`/`sign`/`claim`(실행)·`mutate`/`reserve`/`release`/`transfer`/`quarantine`(capacity)·
`approve`/`arm`/`rearm`/`clear_halt`·`open`/`connect`/`socket`·`time.time`/`datetime.now`/`monotonic`
(clock)·`os.environ`·`exec`/`eval`/`importlib`/`__import__` 문자열이 **부재**함을 grep 회귀로 확인(egress
`test_egress_void_canaries.py` 동형). currentness sequencer가 fact를 invent/transmit하지 않음을 코드 수준에서
증언(§1 line 21).

### 4.2 truthy-sentinel 봉인 (`test_cur_truthy_sentinel.py`)

`ProofResult`·`CurrentnessAdmission`는 `_NonTruthyStrEnum`(`__bool__ ⇒ TypeError`). 회귀: 각 멤버에 `bool(x)`
가 `TypeError`; 소비 게이트는 `result is ProofResult.CURRENT`·`admission is CurrentnessAdmission.ADMIT` 명시
비교만 사용(`if result:` 부재 grep). `RESTRICTED`/`UNKNOWN`/`DENY`를 truthy로 오독하는 fail-open 방지.

### 4.3 극성 규율 (§4.7 — #22 MAJOR-2 재발 방지·전수 점검)

**핵심 교훈(#22 MAJOR-2)**: bool | None 필드에 `if field:`/`if not field:`를 쓰면 `None`이 극성에 따라
**fail-open**한다. 모든 필드는 **극성을 명시**하고 **`is True`/`is False`/`is not True`/`is not False`**로만
정규화한다. `None`은 **양쪽 극성 모두에서 UNKNOWN ⇒ deny**로 수렴하되, **clear시키는 명시값이 극성마다
다르다**.

| 필드 | 극성 | clear 조건 | deny 조건 | 정규화 | 근거 |
|---|---|---|---|---|---|
| `positively_established` | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny` | venue `current_actively_established is not True: return False` |
| `local_latch_clear` | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny` | §5.7 "**positively established** `CLEAR`" |
| `claim_committed` / `staging_complete` | **양극성** | `is True` | `is False` / `None` | `is not True ⇒ deny` | spg `staging_complete is not True` 선례 |
| `is_expired` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ future-use deny` (capacity 불변·§6.10) | §18·CUR-INV-012 |
| `is_revoked` / `terminal_denial` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny` | §10 restrictive-only-sufficient |
| `single_use_consumed` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ reject reuse` | §12 "consumed... proof is denial" |
| `inferred_from_absence` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny` | iap `inferred_from_absence`·§23.3 "absence of invalidation" ≠ current |
| `is_stale` / `is_conflicting` | **음극성** | `is False` | `is True` / `None` | `is not False ⇒ deny` | §10 line 280 conflicting ⇒ Currentness Gap |

**전수 점검 회귀(`test_cur_polarity.py`)**: 모든 음극성 필드에 대해 `None` 입력이 **restricted/deny로
수렴**함을 property test(hypothesis)로 확인 — `revoked=None`이 "not revoked"로 fail-open하는 #22 MAJOR-2를
구조적으로 봉인. 모든 양극성 필드에 대해 `None`/`False`가 deny로 수렴.

### 4.4 그룹 reconcile 규율 (#22 MAJOR-1 재발 방지 — 전-entry 보수)

**핵심 교훈(#22 MAJOR-1)**: 여러 entry가 한 그룹/scope/dimension에 매핑될 때 판정은 **첫-entry가 아니라
전-entry를 보수적으로 reconcile**해야 한다. CUR의 reconcile 지점:

- **`restrictive_floor_reconciled`(§6.2)**: 한 dimension에 여러 restrictive floor가 있으면 **MAX floor(가장
  restrictive)** 채택 — 첫 floor/최소 floor 아님(§10 "advances a minimum accepted... floor").
- **`multi_domain_no_union`(§6.7)**: 여러 도메인 proof를 **union하지 않음**(§16 line 376 "Independent
  per-domain proofs cannot be unioned"); 한 도메인이라도 restricted ⇒ 전체 restricted(any-restriction-wins).
- **`conflicting_owner_restricts`(§6.3)**: conflicting/fork/regression owner ⇒ **union scope + restrict**
  (§10 line 280 "restrictive closure over the **union** of credible scopes") — 첫 owner 채택 아님.

**회귀(`test_cur_reconcile.py`)**: entry 순서 permutation에 대해 verdict 불변(순서 독립) + 가장 restrictive
entry가 지배함을 property test로 확인.

---

## 5. 핵심 L1 술어 (§5 — vector_complete 노른자 + 지지)

> 전 술어 규율 태그: **completeness/coordinate predicate substrate only; CUR-EV-001 NOT_IMPLEMENTED
> (`EV-L1/3` — `/3` 통합·adversarial 대기). 차원 owner verdict/generation/digest는 전부 주입. L1은
> present/revision/policy/floor/structure 판정만.**

### 5.1 `vector_complete` (CUR-EV-001 노른자·§9)

**`mandated` floor 고정(v1.1 MINOR-1)**: `mandated` 파라미터는 자유 주입이 아니라 **전 non-conditional
`DimensionKey` 멤버(= §9 floor, CONTEXT 포함)를 기본 하한**으로 하며, caller는 이보다 좁힐 수 없다
(policy는 §9 위로 추가만 가능 — "at least" 방향; 좁힘 시도는 `policy_covers_mandated_dimensions` 위반).

**시그니처(계약)**: `vector_complete(vector: SafetyCurrentnessVector | None, policy: CurrentnessPolicy | None,
mandated: frozenset[DimensionKey]) -> bool`.

**판정(전부 AND·fail-closed)**:
1. **∅-seal 양방향**: `vector is None` 또는 `policy is None` 또는 `policy.required_dimensions` ∅ ⇒ `False`
   (**absent policy/required set에 대해 완전성을 vacuously 참으로 두지 않음**·§8 "Unknown materiality is
   material"). 동시에 `vector.dimensions` ∅인데 required 비어있지 않으면 ⇒ `False`.
2. **policy 완전(§5.5)**: `policy_covers_mandated_dimensions(policy, mandated)` — `policy.required_dimensions
   ⊇ mandated`(under-declaration 봉인). **집합 양방향**: mandated ⊄ required ⇒ deny(policy가 §9 floor 미달).
3. **전 차원 present + 확립**: `policy.required_dimensions ⊆ {d.dimension_key for d in vector.dimensions if
   dimension_positively_established(d)}`(§5.2). **미표현 required 차원 ⇒ incomplete ⇒ deny**(spg
   `bundle_complete`·hag unrepresented-principal 동형). **어떤 leaf도 이 판정 불가**(각 leaf는 자기 차원만).
4. **단일 revision 정합(§5.3)**: `single_revision_consistent(vector)` — 전 차원 `at_revision ==
   vector.currentness_revision`(§9 line 266 "cannot use... mixed revisions").
5. **no placeholder(§5.4)**: `no_forbidden_placeholder(vector)` — 어떤 차원도 `latest`/wildcard/null-as-
   current sentinel 미사용(§9 line 266).

**반환**: 위 전부 성립시에만 `True`. **완전성은 leaf verdict의 AND가 아니다** — (3)의 미표현 차원, (4)의
mixed-revision, (2)의 policy under-declaration은 **집계자만 탐지 가능한 고유 축**이다(§0.4b·리뷰어 공격
지점 §10.2-①의 airtight 반론). **CUR-EV-001을 닫지 않음**(`/3` 잔여).

### 5.2 `dimension_positively_established` (§9·양극성)

`dimension_positively_established(d: CurrentnessDimension | None) -> bool`: `d is None` ⇒ `False`;
`d.positively_established is not True` ⇒ `False`(양극성·absence ≠ current·venue 선례); `d.dimension_key`/
`d.owner_identity`/`d.bound_generation`/`d.bound_digest`/`d.at_revision` 중 `None` ⇒ `False`. 전부 present +
확립시에만 `True`. **owner 비즈니스 내용은 재판정 안 함**(positively_established는 주입 verdict·duplication
경계).

### 5.3 `single_revision_consistent` (§5.3/§9·mixed-revision 봉인)

`single_revision_consistent(vector) -> bool`: `vector.currentness_revision is None` ⇒ `False`; 전 차원
`d.at_revision == vector.currentness_revision`(compare_order equality) — 하나라도 불일치/`None` ⇒ `False`.
**cross-dimension 판정 — leaf 불가**(§0.4b).

### 5.4 `no_forbidden_placeholder` (§9 line 266·wildcard 봉인)

`no_forbidden_placeholder(vector) -> bool`: 어떤 차원의 `bound_generation`/`bound_digest`가 sentinel
(`"latest"`·`"*"`·null-as-current marker) ⇒ `False`. §9 line 266 verbatim: "A vector cannot use `latest`,
wildcards, null-as-current, implicit inheritance, silent fallback, or mixed revisions."

### 5.5 `policy_covers_mandated_dimensions` (§8·under-declaration 봉인)

`policy_covers_mandated_dimensions(policy, mandated) -> bool`: `policy is None` ⇒ `False`; `mandated ∅` ⇒
`False`(∅-seal); `mandated ⊆ policy.required_dimensions`(집합 양방향) — policy가 §9 mandated 차원을 하나라도
누락 ⇒ `False`(§8 "a producer, consumer, sequencer, operator, or egress cannot omit a dimension because it
expects the fact to be unchanged"). **policy 활성화 자체는 spg/014 주입**(§0.4g) — CUR는 content 완전성만.

---

## 6. predicate-only substrate (§6·§6b·§6c — 닫지 않음)

> 전 술어 규율 태그: **predicate substrate only; 해당 CUR-EV 전부 NOT_IMPLEMENTED (≥ L2 component-fault +
> +Security/+Broker 대기). L1-decidable 순수 판정을 저작하되 어떤 CUR-EV도 닫지 않는다.**

### 6.1 `all_floors_met` (§10·CUR-EV-002 substrate·authority `>=` shape REUSE)
per-dimension `bound_generation >= restrictive_floor`(compare_order). any-None ⇒ `False`. authority
`authority_epoch_current` shape REUSE(재저작 아님·§0.4e). **실 owner-auth/restriction-ingress는 +Security**.

### 6.2 `restrictive_floor_reconciled` (§10·MAJOR-1 reconcile)
한 dimension의 여러 floor entry ⇒ **MAX(가장 restrictive)** 채택(첫-entry 아님·§4.4). ∅ entry ⇒ deny.

### 6.3 `conflicting_owner_restricts` (§10 line 280·CUR-EV-002/007 substrate)
conflicting/fork/sequence-regression/missing-predecessor/unverifiable-scope ⇒ `True`(restrict) + **union
scope**(§4.4). "restrictive submission SHALL NOT be rejected merely because a permissive dependency... is
unavailable"(§10 line 276) — deny path independence는 §6c 런타임.

### 6.4 `RestrictiveFenceRecord` floor advance (§11·CUR-EV-002/003 substrate)
`fence_advances_floor(record) -> bool`: `advanced_floor > predecessor_floor`(monotonic·compare_order) 또는
`terminal_denial is True`. **라치 state machine + deny-first sequence는 egress 소유(#22)·주입 소비**(§0.4d).
실 fence commit는 런타임(§11 line 285-300).

### 6.5 `proof_structurally_complete` (§12·CUR-EV-004 substrate)
`EgressCurrentnessProof`의 §12 전 필수 claim(proof_id·nonce·vector_id·vector_digest·committed_revision·
bound_generations·egress_coordinates·capability_claim_command·send_started_revision) present ⇒ `True`. any-None
⇒ `False`. malformed-model validator + 술어 2층(§2.3).

### 6.6 `proof_admissible` (§12·CUR-EV-004 substrate·다중 fail-closed)
`proof_admissible(proof) -> bool`: `proof_structurally_complete(proof)` AND `proof.result is
ProofResult.CURRENT`(§12 "Only CURRENT") AND `proof.single_use_consumed is False`(음극성 — **명시
False에서만 admit**; v1.1 MAJOR-3: `is not True`는 None[소비 불명]을 admit하는 #22 MAJOR-2 재발이었음)
AND `proof.is_expired is False`(음극성·§6.10·§4.3 표와 정합) AND `proof.egress_coordinates.local_latch_clear is True`
(양극성·§5.7). 하나라도 실패 ⇒ deny. **실 per-send atomic transaction(§13)·wall-clock age(§18)는 런타임/
+Security**.

### 6.7 `multi_domain_no_union` (§16·CUR-EV-008 substrate·MAJOR-1)
독립 per-domain proof를 **union하지 않음**; 한 도메인이라도 non-CURRENT ⇒ 전체 deny(any-restriction-wins·
§4.4). unknown overlap ⇒ merge scope 또는 deny(§16 line 376). 실 cross-domain barrier serializability는 런타임.

### 6.8 `parent_child_floor_monotone` (§16·CUR-EV-008 substrate)
child generation이 restrictive parent floor advance 이후 current로 나타나지 않음(§16 line 378 "prevent a child
from appearing current after a restrictive parent floor advances"). `child_gen >= parent_floor` 위반 ⇒ deny.

### 6.9 `protective_label_not_authority` (§17·CUR-EV-011 substrate·protective 경계)
priority/emergency/close/hedge/exit/reduce-only/protective label은 **authority 아님**(§17 line 393). CUR는
protective lease-exclusivity verdict를 **주입 소비**(protective/rcl/authority 소유·§0.4g). `EV-L2/3+Broker`.

### 6.10 `expiry_denies_future_use_only` (§18·CUR-EV-010 substrate·극성 봉합)
`is_expired is not False` ⇒ **future-use deny**; **capacity/economic effect 불변**(CUR-INV-012 line 187
verbatim: "Expiry... cannot **erase an economic fact, release capacity, prove non-acceptance, or prove Final
Quantity**"). §18 line 399-406 전 항목: cancel/prove-cancellation/prove-non-acceptance/establish-Final-
Quantity/release-capacity/erase-position/authorize-retry **전부 금지**. **음극성 함정 봉합**: `is_expired`가
`None`이면 "not expired"로 fail-open하지 않고 **deny(is not False)**.

### 6.11 `unknown_preserves_capacity` (CUR-INV-011·CUR-EV-010 substrate)
unknown currentness/order/send/broker/exposure ⇒ new risk deny + **worst credible capacity obligation 보존**
(CUR-INV-011 line 183). missing-ACK ≠ non-acceptance·cancel-ACK ≠ Final Quantity(§14 line 350).

### 6.12 `recovery_revives_nothing` (§19·CUR-EV-012 substrate·authority 선례)
restart/reconnect/failover/restore/replay/quorum-recovery/time-recovery/health-restoration ⇒ **no revival**
(CUR-INV-014 line 195). restore ⇒ new Restore Generation·currentness `UNKNOWN`·latch `DENY_LATCHED`(§19 line
418). authority `recovery_generation_revives_nothing` 동형(재저작 아님·§0.4e). **no automatic re-arm**(§11
line 297·§1 line 31). 실 hard-fence는 +Security.

### 6.13 `all_false_currentness_authority` (§7/CUR-INV-005·CUR-EV-009 substrate)
`AllFalseCurrentnessAuthority` 전 필드 `is False` 확인 + model_validator any-True ⇒ `ArtifactIntegrityError`.
proof/vector/fence/policy 어느 것도 approve/mutate-capacity/release/issue-authority/issue-capability/classify-
protection/transmit/clear-HALT/re-arm 불가(§6.13 근거 §1 line 21·CUR-INV-005).

### 6b. not-Phase-1 얇은 모델 property (CUR-EV-005·006 — 닫지 않음·런타임)
- **claim/fence/first-byte race(§14·CUR-EV-005·`EV-L3+Security`)**: 순서 permutation model(`FENCE<CLAIM ⇒
  reject`·`CLAIM<FENCE<FIRST_BYTE ⇒ potentially-live+capacity-covered`·unknown ⇒ potentially-live·no-blind-
  retry). 실 race timing·`B_*` bound·detection intervals는 +Security 런타임.
- **partition/quorum(§15·CUR-EV-006·`EV-L3+Security`)**: broker-reachable ↛ normal-send model property
  (§15 line 358). 실 quorum·linearizable revision·partition healing은 +Security 런타임.

### 6c. 순수 런타임 (L1 model property 없음)
per-send 8-step atomic transaction(§13)·fence commit(§11)·deny path independence 실증(§CUR-INV-004)·first-byte
ordering 증명(§27.8)·hard-fence(§19)·wall-clock age(`MAX_*_age_ms`)·actual quorum consensus/durability. 전부
런타임/+Security — §9.2 Phase-0.

---

## 7. firewall allowlist + 회귀

### 7.1 import-closure allowlist (`test_cur_import_closure.py`)

`tos.cur`의 전이 import closure는 **`{canonical, ordering, cur}`에 국한**되어야 한다(egress
`test_egress_import_closure.py`·rcl `test_rcl_import_closure.py` 동형). `tools/tos_firewall_check.py`가
`shared.*`/`services.*`/`cli.*`/외부 수치 라이브러리/동적 escape/형제 tos 패키지 import를 **차단**. 이
required check가 green이어야 §0.3 firewall 선언이 능동 성립. **naming(§0.4a)은 load-bearing 아님** — 미래
형제 패키지는 allowlist가 자동 배제.

### 7.2 회귀 스위트 (예정 — `tos/tests/cur/`)

`test_cur_vector.py`(vector_complete 노른자·∅/미표현/mixed-revision/policy-under-declaration property·
**`DimensionKey` 집합 == §9-derived 집합 강제 property**[v1.1 — 이 회귀가 저작 시점에 있었다면 MAJOR-2
CONTEXT 누락이 즉시 발각됐을 것; §2.2↔§2.4↔§9 3-원천 정합])·
`test_cur_proof.py`(proof_admissible 다중 fail-closed)·`test_cur_polarity.py`(극성 전수·§4.3)·
`test_cur_reconcile.py`(그룹 reconcile 순서독립·§4.4)·`test_cur_truthy_sentinel.py`(§4.2)·`test_cur_void_
canaries.py`(§4.1)·`test_cur_authority.py`(all-false)·`test_cur_predicate_only.py`(§6 substrate)·
`test_seam_egress.py`+`test_seam_venue.py`(seam 소비 경계·§3.5)·`test_cur_import_closure.py`(§7.1).
**property-based(hypothesis)** 중심(EV-L1 = model/property).

---

## 8. 수치 → Phase-0 / INSTANCE (숫자 하드코딩 0)

CUR 소유 numeric은 **전부 Profile INSTANCE 측정·주입**(현재 전부 `null`·`VERIFICATION-PROFILE-002.yaml`
실측):

| 키 (VP line) | 소유 | 상태 | 근거 |
|---|---|---|---|
| `B_currentness_gap_to_local_deny`(324) | **CUR** | MEASURE·null | §§11,14 detection→DENY_LATCHED |
| `B_restrictive_fence_commit`(331) | **CUR** | MEASURE·null | §§10-11 owner restriction→committed fence |
| `B_currentness_fence_to_egress`(338) | **CUR** | MEASURE·null | §§11-15 fence→egress deny |
| `B_currentness_proof_issue`(345) | **CUR** | MEASURE·null | §§12-13 vector validate + proof create atomic |
| `B_currentness_generation_fence`(352) | **CUR** | MEASURE·null | §§15,19 new gen→predecessor 무능 증명 |
| `MAX_egress_currentness_proof_age_ms`(723) | **CUR** | APPROVE·null | #22 v1.1 MAJOR-2 확정 상속. per-send 새 proof 요구(wall-clock secondary·+Security·§0.4e) |
| `MAX_currentness_vector_age_ms`(724) | **CUR** | APPROVE·null | 완전 dependency scope별·stale vector age deny(wall-clock secondary) |

**주의**: `B_revocation_to_egress`(135)·`B_halt_to_egress`(142)는 **authority(ADR-002-007) 소유**이지 CUR
아님(seam 명확화). `MAX_normal_capability_age_ms`(697)은 capability(007/012) 좌표. CUR는 이들을 주입 소비.
**L1 아티팩트는 전 numeric이 `null`인 상태에서 구성 가능**해야 하며(§2.3 `_REQUIRED_COVERED` numeric 제외),
누락 numeric claim은 fail-closed(§4.7). broker proper noun/KIS 특정값 부재(broker-agnostic).

---

## 9. Phase-0 / not-Phase-1 체크리스트

### 9.1 Phase-1(EV-L1) 산출물 (본 계약이 실현 지침을 제공)
1. `tos.cur` 패키지(canonical/ordering만 의존·firewall green).
2. 모델: `SafetyCurrentnessVector`·`EgressCurrentnessProof`·`RestrictiveFenceRecord`·`CurrentnessPolicy`·
   `CurrentnessDimension`·`CurrentnessRevision`·`EgressProofCoordinateSet`·`AllFalseCurrentnessAuthority` +
   enum(`ProofResult`·`CurrentnessAdmission`·`DimensionKey`).
3. 노른자 술어 `vector_complete` + 지지(§5) + predicate-only substrate(§6) + 얇은 not-Phase-1 model(§6b).
4. malformed-model validator·truthy 봉인·극성·reconcile·all-false·canary 회귀(§4·§7.2).

### 9.2 Phase-0 / 미착지 / +Security / 런타임 (닫지 않음 — 17 항목)
1. Currentness Policy/Vector/Fence/Proof canonical schema **승인**(§28.1·거버넌스).
2. Currentness Ordering Domain + ADR-002-012 커플링(§28.2·**런타임**).
3. owner-authentication·canonicalization·dependency-registry·generation-floor·restriction-ingress 메커니즘(§27.3·**+Security**).
4. Local latch storage/enforcement(restart/sidecar/rotation/failover survival·§27.4·**egress 소유 런타임**).
5. per-send atomic transaction(vector validate + claim + proof + SEND_STARTED·§27.5·**런타임**).
6. cross-domain serializable barrier(§27.6·**런타임**).
7. restrictive signal 독립 delivery + anti-suppression/spoofing(§27.7·**+Security**).
8. first-byte ordering 증명 + queue/proxy/session flush 방지(§27.8·**런타임**).
9. failure-domain/identity allocation(§27.9·**+Security**).
10. degraded protective currentness subset per broker/lease(§27.10·**+Broker**).
11. restore/DR(floor/claim/latch/idempotency/obligation 보존·§27.11·**런타임**).
12. 7개 numeric bound 측정/승인(§8·**INSTANCE**).
13. 독립 security review(owner/sequencer compromise·parser differential·restrictive suppression/spoofing·proof replay/substitution·latch bypass·§28.12·**+Security**).
14. +Security assessment(002·003·004·005·006·007·009·012 — 8행)·+Broker(010·011 — 2행).
15. actual quorum consensus/durability·cryptographic integrity(주입 verified-flag·**+Security**).
16. conditional 025 trial 차원 내용 검증(RLP/-025 미착지 이연).
17. 026/027/028/029/030 governance generation 차원 owner 착지 후 실 좌표 배선(현재 주입 opaque·미착지).

**cross-EV 의존(§28.10)**: CUR-EV closure는 RCLP/EGRESS/SA/TIME/REARM/SBR/CII/VTG/IOC/ARE/AFG/IAP/ERI/FD/BC/
RC 및 025-030 evidence가 required level에서 pass해야 성립 — Phase-1 범위 밖.

---

## 10. 명명 결정 + 리뷰어 공격 지점

### 10.1 운영자 판단 지점
- **패키지 명명 `tos.cur`**(§0.4a) — register-prefix 1:1·seam 토큰 정합. runner-up `tos.currentness`(full-word
  관행) 기각. naming load-bearing 아님(§7.1).
- **Local Restrictive Latch 소유 = egress(소비)**(§0.4d) — 대안: CUR로 이관(기각 근거 §5.7 "inside Final
  Egress Trust Boundary" + #22 착지 + CUR-EV-003 L2+). **독립 리뷰어가 재검토할 지점**.

### 10.2 리뷰어 공격 지점 (선제 반론)
1. **"vector_complete = leaf verdict의 단순 AND"** — 반론: 완전성은 AND 아님. 미표현 차원(§5.1-3)·mixed-
   revision(§5.3)·policy under-declaration(§5.5)은 **각 leaf가 자기 차원만 보므로 탐지 불가·집계 고유
   축**(spg `bundle_complete`·hag unrepresented-principal 선례). 형제 코드가 CUR로 **이연 증언**(egress
   `predicates.py:13`).
2. **"EgressCurrentnessProof = egress QCC 중복"** — 반론: QCC=quorum 커밋 축(013·result VALID/INVALID),
   ECP=currentness conformance 축(024·result CURRENT/RESTRICTED)·§11.2 step 14가 013→024 이연 명시·QCC가
   ECP-id carry(§0.4c).
3. **"CUR가 라치 재저작"** — 반론: state machine=egress(Final Egress Trust Boundary·013)·CUR는 `local_latch_
   clear` 주입 소비·CUR-EV-003 L2+·edge 0(§0.4d).
4. **"all_floors_met = authority_epoch_current 중복"** — 반론: authority=authority-epoch 한 차원, CUR=전 차원
   floor 집계·같은 `>=` shape(compare_order REUSE) 다른 scope(§0.4e).
5. **"currentness = time freshness 중복"** — 반론: §5.4가 currentness를 wall-clock 아닌 ordering identity로
   명시 분리·time gen은 CUR 한 차원·age는 secondary +Security(§0.4e).
6. **"미착지 025-030 차원 phantom 인용"** — 반론: ADR 원문만·코드 인용 0·주입 opaque 좌표(§0.4f·§0.2).
7. **"model_construct로 malformed 벡터 통과"** — 반론: validator + 술어 2층 봉인(§2.3·#20 상속).
8. **"over-realization: per-send/fence/partition을 L1 주장"** — 반론: 닫는 CUR-EV 0·CUR-EV-005/006 not-Phase-1·
   §6c 순수 런타임 명시(§1·§9.2).
9. **"duplication: ~20개 차원 비즈니스 재판정"** — 반론: §1 line 21 "sequencer does not... decide business
   safety"·전 차원 verdict/digest 주입 소비·재저작 0(§0.2·§3.5).

---

## 11. 선제 defect-class 봉합 (전 시리즈 교훈)

| defect class | 출처 | CUR 봉합 |
|---|---|---|
| grep head 절단 카운트 오류 | #12 | register 전수 파싱(csv line 281-292 직접·§1) |
| under-realization(얇은 표면) | #7 | — (CUR는 반대 — over-realization 경계·§1) |
| truthy-sentinel fail-open | #13·#14 M1 | `_NonTruthyStrEnum` 처음부터(§2.2·§4.2) |
| ∅ 단방향 seal | #8·#15 | vector/policy/required ∅ 양방향(§5.1) |
| 집합 단방향 | #10 | required ⊇ mandated 양방향(§5.5) |
| malformed-model model_construct 우회 | #20 | validator + 술어 2층(§2.3) |
| 미표현 요소 vacuous pass | #20 미표현-principal | 미표현 차원 ⇒ incomplete(§5.1) |
| phantom id/코드 인용 | #17·#20 | 인용 전 grep·미착지 025-030 코드 0(§0.4f) |
| **극성 fail-open(revoked/expired/stale None)** | **#22 MAJOR-2** | **극성 전수 표 + None ⇒ deny 수렴 회귀(§4.3)** |
| **그룹 첫-entry 판정** | **#22 MAJOR-1** | **전-entry 보수 reconcile(MAX floor·any-restriction-wins·§4.4)** |
| 과대 주장(authoring=acceptance) | 전 시리즈 | 닫는 CUR-EV 0·"EV-L1-complete 주장 금지"(§1) |
| seam 재저작(currentness 중복) | #19·#22 | venue/iap/capsule/egress/authority/time 소유 실측·주입 소비(§3.5·§10.2) |

---

## 12. 요약

`tos.cur`는 시리즈의 **currentness 집계자**를 실현한다. 형제(venue·iap·capsule)가 각자 자기 한 차원의
per-decision currentness leaf를 소유하고 complete-vector 집계를 CUR로 이연했음을 **코드가 증언**한다(egress
`predicates.py:13`·venue `__init__.py:17`). 본 계약의 core는 **1행(CUR-EV-001 Complete Exact Vector·
`EV-L1/3`·시리즈 최소 core)**이며 노른자 술어 `vector_complete`(전 차원 present + 단일 revision + policy 완전 +
no-placeholder·∅/집합 양방향)로 저작한다. 완전성은 leaf-AND가 아닌 **집계 고유 축**(미표현 차원·mixed-
revision·under-declaration은 집계자만 탐지)이다. **닫는 CUR-EV = 0**(authoring ≠ acceptance). 두 최대 위험
(over-realization: 런타임을 L1 주장 / duplication: ~20 차원 재판정)을 §1·§6c·§3.5로 이중 봉합하고, #22
MAJOR-1(reconcile)·MAJOR-2(극성)를 §4.3-4.4로 선제 봉합한다.

**비준 기록: 2026-07-27 운영자 위임 자동 비준(v1.1 — REVISE minimal edit set 전량 반영 후 집행; 상세는
문서 헤더 비준 기록 블록).**
