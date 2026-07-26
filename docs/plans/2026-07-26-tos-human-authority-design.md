# 설계 문서 #20 — Human Safety Authority·Dual Control·Break-Glass 계약 (2026-07-26, v1.1)

> 본 문서는 **ADR-002-015 (Human Safety Authority, Dual Control, and Break-Glass
> Governance — "HAG")** 를 IMPLEMENTATION-PLAN-002 §4 Phase 1 (EV-L1) 순수 모델·술어
> 계약으로 실현하는 **저작 초안**이다. 규범 원천은 `tos-spec/src/part-1-foundation/
> ADR-002-015-Human-Safety-Authority-Dual-Control-and-Break-Glass-Governance.md`
> (794줄, v0.2, Proposed)와 `EVIDENCE-REGISTER-002.{md,csv}` (`HAG-EV-001..018`, 18행)와
> `VERIFICATION-PROFILE-002.yaml`이다. 구현 코드·tos-spec 수정·기존 docs/plans 수정은
> 본 태스크 범위 밖이다. **비준 상태: 2026-07-26 운영자 위임 자동 비준(v1.1; 2026-07-25 지시 —
> minimal edit set 전량 반영·오케스트레이터 검증 후 집행. 판단 지점: `tos.hag` 명명·edge 0·
> `unresolved_control` graph-level 전면-거부 + per-edge `resolved` 2층·liveauth/spg/iap 경계 채택.
> 효력: `tos/src/tos/hag/` Phase 1[EV-L1] 착수).** (개정 이력: v1.1 — 독립 비평
> REVISE[MAJOR 2·MINOR 2] 반영, §10.1 v1.1).**

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. **패키지 명명 `tos.hag`** (§0.4a) — register series prefix `HAG` 1:1·terse 3-letter
   관행(rcl/spg/dsl/are/ioc/iap/sbr/afg)·이미 머지된 seam 토큰(`human_authority_policy`·
   `effective_principal_graph`·`approval_set`)과 정합. venue(#19)와 달리 **경쟁 후보가 거의
   없는 저마찰 명명**.
2. **EV 분류 재실측(사전 지도 "9" 오산 정정)**: `HAG-EV-001..018` 18행 중 **core(L1-floor)
   8행 = {001·002·004·006·007·010·011·012}** / **predicate-only(≥ L2) 10행 =
   {003·005·008·009·013·014·015·016·017·018}**. **닫는 HAG-EV = 0건**·"EV-L1-complete 주장
   금지"(§1).
3. **인간 권위 일반 모델(general model) 소유 경계 vs liveauth re-arm 인스턴스 소비**(§0.4b·
   §3.5) — **본 문서 최대 판정**. HAG는 effective-principal graph·collapse·approval
   request/attestation/set·SoD·break-glass·HALT command·delegation·approval lifecycle의
   **일반 모델**을 소유하고, liveauth(#7)가 이미 소비한 **§17 re-arm 인스턴스**(dual-control
   consumption·SAFE-053 variant 7-control·13-환경 prerequisite)는 **재저작하지 않는다**.
4. **중심 모델·술어 골격**(§2·§4·§5·§6): effective-principal 동치류 collapse(순수 함수·
   보수적 병합)·`HumanApprovalRequest`/`HumanApprovalAttestation`/`HumanApprovalSet`
   (digest-bound)·quorum-independence 술어(collapse-before-count·중복 principal 거부·∅/1인
   거부)·SoD 술어·break-glass 방향 제한·HALT 무조건-restrictive 경로·approval lifecycle
   상태기계.
5. **선제 봉합**: #6 fail-open(all-false·`<= 1` vacuous-∅)·#12 ∅ 양방향·#13 truthy-sentinel
   구조 봉인·#14 집합 양방향·#15/#19 phantom(필드-클래스 소유 grep 실측)·#17 공유 커널/병렬
   레이스(allowlist)·과대 주장 금지.
6. **firewall §0.3**(allowlist `closure ⊆ {canonical, ordering, hag}`)·§7.1 import-closure·
   §7.2 run manifest·§8 bounds 주입(candidate 신규 VP 키 0건)·§9.2 Phase-0·§10.2 비준
   체크리스트.

### 0.2 하지 않는 것 (경계·NO 목록)

- **어떤 HAG-EV도 닫지 않는다.** Phase 1은 각 HAG-EV의 **L1-decidable predicate/model
   substrate**만 저작한다. `/3`(integration/adversarial)·`+Security`(identity/credential/
   authorization/fencing/bypass 독립 평가)는 EV-L2/L3 런타임이며 **독립 리뷰 잔여**(§1).
- **liveauth re-arm 인스턴스 재저작 금지**: `rearm_dual_control_satisfied`·
   `rearm_admissible`·`Safe053VariantAttestation`(7-control)·`_VARIANT_ENVIRONMENTAL_
   PREREQUISITES`(13항)·`ReArmPathKind`·`ReArmApprovalRecord`는 **liveauth 소유**(코드 실측
   §3.5). HAG는 이들의 **상류 provenance**(effective-principal distinctness의 *의미*)만
   소유.
- **spg break-glass action-token 재저작 금지**: `break_glass_confined`·`BreakGlassAction`·
   `BREAK_GLASS_ALLOWED_ACTIONS`는 **spg 소유**(ADR-002-014 §8·SPG-EV-009). HAG는 인간
   authority-class 방향(§7)과 spg가 **명시적으로 HAG에 이연한** effective-principal
   independence 부분만 소유(§0.4d — spg 코드가 직접 증언).
- **iap 자동 승인 축 재저작 금지**: `ProposalApprovalRequest`·`IndependentApprovalDecision`·
   `ApprovalConsumptionRecord`·`ApprovalResult`는 **iap 소유**(ADR-002-023 시스템 결정). HAG는
   **인간 principal attestation** 축(ADR §4 line 98 명시 분리)(§0.4e).
- **protective classification·capacity·Cancellation Arbiter·replacement 재저작 금지**: §16
   containment request의 실제 classification·capacity·replace 판정은 protective(ADR-002-001)·
   rcl(ADR-002-002)·replacement(ADR-002-011)·final egress(ADR-002-013) 소유. HAG는 "인간
   요청은 proposal이지 authority가 아니다"만 소유(§0.4d).
- **live authority·capacity·egress 미생성**: 어떤 HAG 아티팩트·술어도 capacity mutate·config
   activate·Live Authorization issue·deny latch clear·broker transmit·re-arm 불가(all-false
   `HumanAuthorityEffect`·HAG-INV-004).
- **numeric bound 하드코딩 0**: quorum N·cooling interval·session/approval/delegation age·
   HALT latency는 전부 주입 파라미터. 값 부재 ⇒ fail-closed(§8).
- **identity provider·authenticator·PKI·workflow product·operator UI·명명 인물/직함 미선정**
   (ADR §4 non-scope line 87-94; §9.2 Phase-0).
- **broker-agnostic**: §21 external manual/broker authority는 capability-class 언어로만.
   특정 broker(KIS 등) 값 부재.

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

`tos.hag` 모델은 다음만 import한다:

- **서드파티**: `pydantic`(frozen 모델)·`pytest`/`hypothesis`(테스트만). **`numpy`/`pandas`/
   `pyyaml` 미import** — human-authority 판정은 StrEnum·boolean·집합/그래프(동치류) 논리이고
   모든 quorum N·age·cooling·latency 값은 주입 파라미터이며 YAML 파싱은 하네스(설계 #3)
   소관(closure 최소화 — #12–#19 §0.3 동형).
- **tos 자기 자신**: `tos.canonical`(`FrozenModel` `_base.py:73`·`DigestBoundArtifact`
   `_base.py:98`·`IndependentIdArtifact` `_base.py:328`·`classify_record_pair`
   `record_pair.py:52` + `RecordPairKind` `record_pair.py:31`[§18 replay·§10 substitution
   탐지]·`ArtifactStatus` `_base.py:58`·`ArtifactIntegrityError` `_base.py:50`·
   `EVL1ProvisionalCanonicalizer` `canonicalization.py:173`)·`tos.ordering`(`Ordering`·
   `OrderingEvent`·`compare_order` — **approval lifecycle·graph/roster/policy generation
   monotonic 순서**; 실측 core)·`tos.hag.*`.
- **미import(직접·전이 모두) — 19 형제 tos 패키지(전부 실재)**: `tos.afg`·`tos.are`·
   `tos.authority`·`tos.brokercap`·`tos.capsule`·`tos.dsl`·`tos.evidence`·`tos.iap`·
   `tos.ioc`·`tos.liveauth`·`tos.orthostate`·`tos.protective`·`tos.rcl`·`tos.recon`·
   `tos.replacement`·`tos.sbr`·`tos.spg`·`tos.time`·`tos.venue`. **`tos.liveauth`·`tos.spg`·
   `tos.iap`·`tos.protective`·`tos.replacement`는 최인접 형제**로 명시 포함(#17 MAJOR-1 교훈 —
   최인접 형제 누락이 edge 유일 가드 구멍이었음). **전부 produced/consumed scalar·bool·
   enum-token·verdict·digest로만 참조**(§3.4/§3.5). **sibling edge 0 권장**(runner-up
   liveauth `ReArmPathKind` typed-reuse 1 edge — §0.4c).
- **형제 카운트 실측(honest)**: `ls tos/src/tos/` → **21 패키지**(afg·are·authority·
   brokercap·**canonical**·capsule·dsl·evidence·iap·ioc·liveauth·**ordering**·orthostate·
   protective·rcl·recon·replacement·sbr·spg·time·venue). `tos.hag`는 신규 생성(**22번째**,
   현재 부재). ⇒ **형제(배제) = 21 − canonical − ordering = 19**. **정확 카운트는
   non-load-bearing**: §7.1이 **allowlist**(`closure ⊆ {canonical, ordering, hag}`)이므로
   카운트 오차·미래 신규 형제 모두 자동 배제(sbr `__init__.py:47-48` "any future sibling are
   all excluded by the §7.1 allowlist closure test" 선례).
- **`shared.config` 절대 금지**(설계 #1 §6.1, `.importlinter`): `shared.config.__init__`이
   `shared.config.secrets`(→ `os.environ`)를 무조건 전이 import한다. `tos.hag`는 어떤
   `shared.*`도 필요로 하지 않는 순수 커널이다.
- **금지(직접·전이)**: `shared.execution`·`shared.kis`·`shared.streaming`·`shared.llm`·
   `shared.storage`·`shared.backtest`·`shared.config.secrets`·`services.*`·`cli.*`
   (`.importlinter` `[importlinter:contract:tos-operational-firewall]` type=forbidden·
   source_modules=`tos` 실측 — forbidden set).
- **firewall 구조 확인(실측·#17-#19 상속)**: `.importlinter`는 `type=forbidden·
   source_modules=tos` 단일 계약이며 `layered`가 아니다 — intra-tos sibling→sibling edge는
   구조적으로 금지되지 않고 설계 #1 §3.2의 "자기 자신 `tos.*`" 허용 조항이 이를 커버한다.
   **신규 패키지 `tos.hag`는 firewall 도구 무수정 자동 포섭**(forbidden 계약이 source=tos
   전체를 덮음). 본 문서는 sibling edge 0을 설계 규율로 삼고(§0.4c), §7.1 allowlist가 이를
   능동 강제한다.

### 0.4 REUSE / import / 경계 결정 요지 (핵심 아키텍처)

**(a) 패키지 명명 = `tos.hag` (저마찰·근거 3중).** venue(#19)가 `tos.venue` vs `tos.vtg`로
치열했던 것과 달리 HAG는 **경쟁이 약한 명명**이다.

- **선택(권장) `tos.hag`** — 근거 3중:
  1. **register prefix 1:1**: 시리즈가 `HAG-INV`/`HAG-AC`/`HAG-EV`를 사용(register 실측
     line 173-184·365-370·§26). terse 3-letter 관행(rcl·spg·dsl·are·ioc·iap·sbr·afg —
     전부 register prefix lowercase)과 정합.
  2. **seam 토큰 이미 머지(코드 실측)**: 도메인 아티팩트명이 **이미 형제 코드·VP에 고정**:
     evidence `replay.py:114` `human_authority_policy_digest`·`replay.py:115`
     `effective_principal_graph_digest`·`envelope.py:56` `effective_principal_id`·
     `envelope.py:93` `approval_set_id`; VP `human_authority_policy_id/generation/digest`
     (line 37-39)·`effective_principal_graph_id/generation/digest`(line 40-42). ⇒ HAG
     아티팩트명 **`HumanAuthorityPolicy`·`EffectivePrincipalGraph`·`HumanApprovalSet`**는 이
     evidence/VP 앵커(진짜 HAG 축)로 확정(venue `venue_*` seam 정합 동형); **`HumanApprovalRequest`·
     `HumanApprovalAttestation`은 seam 토큰이 아니라 register-prefix `HAG` + ADR §5.4/§5.5 정의로
     정박**(자동 축과 명명 분리·§0.4e). **주의(MAJOR-1)**: capsule `capsule.py:161`
     `approval_request_id`는 **iap 자동 파이프라인 체인(Bindings) 필드**(iap `ProposalApprovalRequest`
     `records.py:158` 소유)이지 HAG seam이 **아니다** — HAG 명명 근거에서 배제.
  3. **`tos.authority` 충돌 회피**: head-noun "authority"는 **이미 ADR-002-003 `tos.authority`
     점유**. "human authority"의 3-letter 축약 `hag`가 충돌 없는 유일 terse 선택.
- **runner-up `tos.humanauth`(defensible·차선)** — descriptive·명시적. 기각 근거: (i) terse
   3-letter 관행 이탈, (ii) register prefix `HAG`와 drift, (iii) 저마찰 명명에서 descriptive
   필요성 낮음. **§10.2 운영자 판단 지점**: `tos.hag`(register-prefix·terse·seam 정합) vs
   `tos.humanauth`(descriptive). 내부 module(`_base.py`·`vocabulary.py`·`records.py`·
   `predicates.py`·`state.py`)은 liveauth/iap/sbr/venue 선례 동형.

**(b) HAG = 인간 권위 일반 모델 소유; liveauth = §17 re-arm 인스턴스 소비 (본 문서 최대
판정·재저작 금지 경계).** 이것이 본 계약의 **핵심 아키텍처 결정**이다.

- **실측 사실(liveauth 코드)**: liveauth(#7, 2026-07-24 착지)는 ADR-002-007 §13/§17 re-arm의
   dual-control 소비를 **이미 실현**했다 — `ReArmApprovalRecord.approver_principals:
   tuple[str, ...]`(`records.py:216`)·`DualControlAttestation`(`state.py:168`: `armer_
   principal`·`limit_change_approver_principal`·`distinct_approver_count`·`path`·`variant`)·
   `rearm_dual_control_satisfied`(`predicates.py:492`)·`Safe053VariantAttestation`
   (`state.py:144`, 7-control)·`ReArmPathKind`(`vocabulary.py:41`, {QUORUM,
   GOVERNED_SINGLE_OPERATOR})·`_VARIANT_ENVIRONMENTAL_PREREQUISITES`(`predicates.py:127`,
   13항 + drift 회귀 테스트 `predicates.py:122-126`)·`_SAFE053_CONTROLS`(`predicates.py:104`,
   7항).
- **결정적 코드 증언(liveauth 스스로 HAG에 이연)**: `DualControlAttestation` 도크스트링
   (`state.py:172-175`) verbatim: "Principals are opaque identity coordinates (**distinctness
   only** — actual human authentication is **ADR-002-015 runtime**, REARM-EV-005 +Security
   not-Phase-1)." 그리고 `rearm_dual_control_satisfied` Path 1의 distinctness 판정은
   `limit_change_approver_principal != armer_principal and distinct_approver_count >= 2`
   (`predicates.py:523-527`) — **순수 문자열 부등호**다. **이 문자열 `!=`는 서로 다른 두
   식별자 문자열이 사실은 같은 자연인으로 붕괴하는 경우를 탐지할 수 없다.**
- **⇒ HAG가 소유하는 잔여(liveauth가 opaque string으로 이연한 것)**:
  1. **§8 Effective Principal Graph + collapse** — 계정/자격/장치/세션/서비스ID/복구경로/관리
     통제경로를 **하나의 자연인으로 붕괴**시키는 동치류 순수 함수. liveauth의 opaque `armer_
     principal`/`limit_change_approver_principal` **문자열에 의미를 부여**하는 상류 모델.
     liveauth `!=`는 두 계정의 한 사람을 놓치지만, HAG collapse는 잡는다. **HAG-EV-001, L1
     노른자.**
  2. **§9 Human Authority Policy·§10 request/attestation·§11 approval-set 검증·§12 SoD·§13
     delegation/roster·§15 HALT command·§16 break-glass·§18 lifecycle** — 인간-권위 일반
     모델. liveauth는 이 중 **아무것도** 모델링하지 않음(opaque string + pre-computed
     boolean만 소비).
- **재저작 금지 경계(엄격)**: HAG는 liveauth의 `rearm_dual_control_satisfied`·
   `rearm_admissible`·`Safe053VariantAttestation`·`_VARIANT_ENVIRONMENTAL_PREREQUISITES`·
   `_SAFE053_CONTROLS`·`ReArmApprovalRecord`를 **재저작하지 않는다**. 런타임에서 HAG의
   effective-principal collapse가 **먼저** 실행되어 "distinct effective principal count"를
   산출하고, 그 결과가 liveauth `DualControlAttestation.distinct_approver_count`로
   **주입**된다(계층 상하 관계). **HAG-EV-010(Dual-Control Re-arm) L1 잔여 = collapse-before-
   count의 *의미* 저작**이지 re-arm 소비 재구현이 아니다(§5.7).
- **drift 회귀 테스트 선례**: liveauth `_VARIANT_ENVIRONMENTAL_PREREQUISITES` drift test
   (`predicates.py:122-126` — 13항을 `authority._REARM_PREREQUISITES` 마이너스 SoD와 lock-step
   유지)는 **동일 리스트를 두 곳에서 재표현할 때** 적용한다. HAG는 liveauth의 7-control·
   13-prerequisite를 **재표현하지 않으므로** 리터럴 drift 테스트가 불요다 — 대신 HAG collapse와
   liveauth string-distinctness는 **다른 계층**이라 의미 drift는 §3.5 소유권 분할표로 봉인.
   만약 미래에 HAG가 이들 리스트를 참조할 필요가 생기면 **그때 drift-test 패턴을 적용**한다
   (선제 규율).

**(c) sibling edge 0 권장 vs liveauth `ReArmPathKind` typed-reuse 1 edge (중심 판단 지점).**
HAG는 형제 **결과**를 대량 소비하나 iap(#15)/sbr(#17)/venue(#19)와 동형으로 **edge 0**을
권장한다. 유일한 edge-1 후보는 re-arm path 어휘다:

- **권장: edge 0 (result/verdict/digest injection).** 모든 형제 상호작용을 **주입된 scalar·
   digest·bool·verdict·opaque enum-token(str)** 으로 받는다. 근거: iap(edge 0)·sbr(edge 0)·
   venue(edge 0)의 배포 선례. HAG 아티팩트는 전부 `tos.canonical`(base)+`tos.ordering`
   (generation) 위에 로컬 저작되고 형제는 digest/verdict로만 참조된다.
- **대안: liveauth `ReArmPathKind` REUSE (1 edge).** HAG의 approval-type이 re-arm일 때 QUORUM
   vs GOVERNED_SINGLE_OPERATOR path를 `ReArmPathKind`(`liveauth/vocabulary.py:41`) typed
   field로 저장. **기각(중심 논증)**: HAG의 approval-set 모델은 **path-agnostic**이다 —
   HAG는 "distinct effective principals ≥ policy quorum"를 판정하고, re-arm path의 QUORUM/
   variant **선택**은 liveauth re-arm 소비의 관심사다(§3.5). `ReArmPathKind`를 import하면
   (i) HAG→liveauth edge가 생기고, (ii) HAG approval-set이 re-arm 인스턴스에 결합되어 일반
   모델이 오염된다. **§10.2 판단 지점**: edge 0(권장·일반 모델 독립) vs liveauth REUSE(타입
   안전·인스턴스 결합). 리뷰어 공격 지점(§10.2): "HAG와 liveauth 둘 다 quorum/variant를
   말하니 중복" — 반론: 축이 다름(HAG=effective-principal distinctness의 *의미* 생산;
   liveauth=re-arm consumption의 path 선택·count 소비); §3.5 소유권 분할.

**(d) break-glass — spg 경계 (2대 판정·spg 코드가 직접 증언).** **실측 충돌 후보**: spg
(`tos.spg`, ADR-002-014 §8)가 `break_glass_confined`(`predicates.py:746`)·`BreakGlassAction`
(`vocabulary.py:236`)·`BREAK_GLASS_ALLOWED_ACTIONS = {HALT, RESTRICTIVE_OVERRIDE}`
(`vocabulary.py:258`)를 **이미 소유**한다(SPG-EV-009). HAG-EV-006도 "Break-Glass Directional
Confinement"이므로 **재저작 함정**이다.

- **판정: 축이 다르며 spg 코드가 HAG 잔여를 명시 이연**. `break_glass_confined` 도크스트링
   (`spg/predicates.py:755-758`) verbatim: "The effective-principal independence enforcement
   ('Splitting labels across roles while one principal controls all underlying credentials
   does not establish separation', §8 line 249) is **ADR-002-015 HAG-EV +Security —
   not-Phase-1**." ⇒ **spg 스스로 effective-principal independence 부분을 HAG로 이연**한다.
- **경계 분할(코드 실측)**:
  - **spg 소유**: break-glass **action-token**의 방향 제한(safety-config governance
     맥락). `action ∈ {HALT, RESTRICTIVE_OVERRIDE}` 2-token membership(ADR-002-014 §8).
  - **HAG 소유**: (i) spg가 명시 이연한 **effective-principal independence** enforcement
     (한 사람이 모든 자격을 통제하면 role 분리 무효 — §8 line 249, HAG collapse가 근거),
     (ii) **인간 authority-class 방향**(§7의 8-class taxonomy: HALT/NARROW/REQUEST_PROTECTIVE/
     APPROVE_*/CAPACITY_MUTATION/TRANSMIT)의 break-glass 제한(§16·HAG-INV-006), (iii) 인간
     containment request는 **proposal이지 authority가 아니다**(§16·HAG-INV-007 — protective
     classification·capacity·egress 필수).
- **⇒ HAG는 `break_glass_confined`/`BreakGlassAction`을 재저작·import하지 않는다.** HAG는
   자신의 §7 authority-class 어휘 위에 `break_glass_direction_restrictive` 술어를 로컬 저작
   (다른 taxonomy·다른 ADR 조항·다른 EV 행). safety-config를 건드리는 break-glass에는 spg
   confinement이 **다층 방어로 함께 적용**(venue의 ioc-conformance vs venue-admissibility
   defense-in-depth 동형). **리뷰어 공격 지점(§10.2)**: "HAG-EV-006가 SPG-EV-009를 재저작" —
   반론: spg 코드 `predicates.py:755-758`이 HAG 잔여를 **직접 이연**·다른 ADR clause
   (002-014 §8 vs 002-015 §16)·다른 vocabulary(2-token vs 8-class)·다른 register 행.

**(e) approval 어휘 — iap 경계 (자동 결정 vs 인간 attestation 축).** **실측 충돌 후보**: iap
(`tos.iap`, ADR-002-023)가 `ProposalApprovalRequest`·`IndependentApprovalDecision`·
`ApprovalConsumptionRecord`·`TradingApprovalPolicy`·`ApprovalResult`·`approval_decision`·
`exact_binding_holds`·`no_widening_no_union`·`approval_grants_no_authority`를 소유
(`iap/__init__.py:143-166`).

- **판정: 별개 축·ADR가 명시 분리**. ADR-002-015 §4 line 98 verbatim: "ADR-002-023 separately
   governs automated per-proposal independent approval... A Human Approval Set may approve
   governance, residual risk, or re-arm where policy requires, but it **cannot substitute**
   for the ADR-002-023 independent automated decision; conversely an automated `APPROVE`
   **cannot satisfy a human quorum**." ⇒ iap = **시스템 자동 결정**(per-proposal), HAG =
   **인간 principal attestation**. 두 축은 상호 대체 불가.
- **명명 규율(phantom·혼동 선제 봉합)**: HAG는 인간 축임을 **명명으로 명시**한다 —
   `HumanApprovalRequest`(≠ iap `ProposalApprovalRequest`)·`HumanApprovalAttestation`(iap엔
   부재 — 인간 개별 결정)·`HumanApprovalSet`(≠ iap `ApprovalConsumptionRecord`)·
   `AttestationDecision`{APPROVE/DENY/ABSTAIN}(≠ iap `ApprovalResult`). Python 네임스페이스
   (`tos.hag.*` vs `tos.iap.*`)가 리터럴 충돌은 막으나, **리뷰어 혼동 방지**를 위해 "Human"
   prefix로 축을 불가역 구분. iap `_NonTruthyStrEnum`(truthy 봉인·`vocabulary.py:50`)은
   **로컬 재표현**(import 아님 — 각 패키지 private base, ioc `ConformanceResult`·iap 4-enum
   동형; §2.2).
- **리뷰어 공격 지점(§10.2)**: "HAG와 iap의 approval-set·single-use consumption이 중복" —
   반론: 축이 다름(인간 quorum vs 자동 결정)·ADR §4 line 98 명시 분리·HAG는
   effective-principal collapse를 quorum 전에 적용하나 iap는 시스템 결정이라 principal 개념
   자체가 없음.

**(f) 앵커 규약 — HAG-INV/AC/EV 앵커, 새 시리즈 창작 금지.** **실측**: ADR-002-015는 자체
시리즈 **`HAG-INV-001..019`(§6 line 158-232, 19종)·`HAG-AC-001..012`(§26 line 700-711,
12종)·`HAG-EV-001..018`(register line 173-184·365-370, 18행)**를 정의한다. §26 preamble
(line 696 verbatim): "The following cases are mandatory and map one-to-one to `HAG-EV-001`
through `HAG-EV-012`. Written cases are not completed evidence." ⇒ **HAG-AC는 12행이며
HAG-EV-001..012에만 1:1 매핑**; HAG-EV-013..018(variant 계열)은 §17.1.6 evidence-debt로
§26 AC가 없다. **감사자 주의(MINOR-2)**: ADR §17.1.6(v0.2, line 505)은 "prospective
HAG-EV-013 and successors is **not** registered in EVIDENCE-REGISTER-002 in this wave"라
했으나 register가 013-018을 후행-등재(csv line 365-370, NOT_IMPLEMENTED) ⇒ **register
후행-갱신이 §17.1.6 문언을 supersede**(register authoritative)·013-018은 predicate-only
(≥ L2)로 실재(§1). 본 계약은 모델 불변식·술어를 **`HAG-INV-###`/`HAG-AC-###`/`HAG-EV-###`/
§-clause/`SAFE-###`(§27 traceability line 717-727)**에 앵커하고 **새 시리즈를 창작하지
않는다**. #12–#19 동형.

**(g) HAG-EV = core 8 + predicate-only 10, 닫는 HAG-EV = 0건 (재실측 정정).** **사전 지도가
"9"로 오산**했으나 register 재실측(§1)으로 **core(L1-floor) 8행 확정**. register 최소-레벨
histogram(line 173-184·365-370): **`EV-L1/3+Security` ×5**(001·002·004·006·010)·**`EV-L1/3`
×3**(007·011·012)·**`EV-L2/3+Security` ×10**(003·005·008·009·013·014·015·016·017·018). ⇒
**L1 슬라이스 보유 8행 = core**(task 재실측과 일치), **부재 10행(최소 ≥ L2) = predicate-only
substrate**. **닫는 HAG-EV = 0건** — L1 슬라이스 저작은 EV closure가 아니다(`/3`·`+Security`
통합·독립 리뷰 잔여). **truthy-sentinel 규율(#13·#14 M1 교훈을 처음부터)**: `AttestationDecision`
{APPROVE/DENY/ABSTAIN}·`ApprovalLifecycleState`가 non-empty StrEnum이므로 **소비 게이트는
`decision is AttestationDecision.APPROVE` 명시 비교**(truthy 금지)를 §4.7·§5에 계약화하고
**`__bool__ ⇒ TypeError` 구조 봉인**을 처음부터 채택(iap `_NonTruthyStrEnum`
`vocabulary.py:50` 동형; DENY/ABSTAIN truthy fail-open 방지가 핵심).

---

## 1. 범위 매핑 — ADR-002-015 조항별 EV-L1 도달성 (닫는 HAG-EV 0건)

EV-level 정의(VER-002-001): **EV-L1 = Model and Property Verification**(state-machine
exploration, model checking, property-based testing, deterministic simulation). **EV-L2 =
Component Fault Test**, **EV-L3 = Integration/Adversarial**, **+Security = independent
security-boundary assessment**(identity/credential/authorization/fencing/bypass). Phase 1은
EV-L1만이다.

> **결정적 사실 1 — HAG-EV core 8행 재실측(사전 지도 "9" 정정)**: register 실측 histogram:
> **core(L1 슬라이스 보유) 8행 = {001 Effective Principal Collapse [`EV-L1/3+Security`,
> csv:173]·002 Exact Approval Context Binding [`EV-L1/3+Security`, :174]·004 Approval Replay/
> Expiry/Revocation/Consumption [`EV-L1/3+Security`, :176]·006 Break-Glass Directional
> Confinement [`EV-L1/3+Security`, :178]·007 Human Protective Request Cannot Bypass Safety
> [`EV-L1/3`, :179]·010 Dual-Control Re-arm and Narrow Scope [`EV-L1/3+Security`, :182]·011
> Approval/Economic-State Continuity [`EV-L1/3`, :183]·012 Human Authority Replay [`EV-L1/3`,
> :184]}**. **predicate-only(≥ L2) 10행 = {003 SoD·005 Human HALT Availability·008 Delegation/
> Roster·009 Compromise Containment·013–017 Variant 계열·018 Operator Config/Authz Error
> — 전부 `EV-L2/3+Security`, csv:175/177/180/181/365-370}**. **+Security 15/18**(007·011·012만
> `EV-L*/3` — Security 미부착). **닫는 HAG-EV = 0건**.
>
> **결정적 사실 2 — authoring ≠ acceptance(닫는 HAG-EV = 0건)**: Phase 1은 각 HAG-EV의
> **L1-decidable predicate/model substrate**를 저작하나 **어떤 HAG-EV도 닫지 않는다.** (a)
> core 8행조차 `/3`(integration/adversarial) 잔여·5행 +Security(001·002·004·006·010), (b)
> 10행은 최소 ≥ L2, (c) VER-002-001 §5 "Registration is not execution"·ADR §26 line 696
> "Written cases are not completed evidence"·§29 line 766 item 8. ⇒ **"EV-L1-complete 주장
> 금지"**(#12–#19 §1 규율 상속). Owner/Reviewer는 register상 TBD·status NOT_IMPLEMENTED(전
> 18행).

**규율 태그(모든 주장에 부착)**: "**predicate/model substrate only; HAG-EV-001..018 전부
NOT_IMPLEMENTED — core 8행(001·002·004·006·007·010·011·012)은 `/3`·+Security(001·002·004·
006·010) 통합·adversarial·독립 리뷰 대기, predicate-only 10행은 EV-L2/L3 fault injection·
adversarial·+Security evidence 대기. EV-L1-complete 주장 금지.**"

**HAG-EV core 8행 ↔ AC(1:1) ↔ ADR 조항 매핑(실측)**:

| HAG-EV | register 제목(verbatim, csv line) | 최소 레벨 | HAG-AC(1:1) | ADR 조항 앵커 | L1 substrate 술어(§5) |
|---|---|---|---|---|---|
| **001** | Effective Principal Collapse and Quorum Independence (173) | `EV-L1/3+Security` | AC-001(line 700) | §8 graph/collapse·HAG-INV-001 | `effective_principal_collapse`+`quorum_independence_satisfied`(§5.1 — 노른자) |
| **002** | Exact Approval Context Binding (174) | `EV-L1/3+Security` | AC-002(line 701) | §10 request/attestation·HAG-INV-002/008 | `approval_binding_exact`+`material_change_invalidates`(§5.2) |
| **004** | Approval Replay, Expiry, Revocation, and Consumption (176) | `EV-L1/3+Security` | AC-004(line 703) | §11/§18 set validation·lifecycle·HAG-INV-004 | `approval_set_single_use`+`stale_replayed_rejected`(§5.3) |
| **006** | Break-Glass Directional Confinement (178) | `EV-L1/3+Security` | AC-006(line 705) | §7/§16 authority classes·HAG-INV-006 | `break_glass_direction_restrictive`(§5.4 — spg 경계) |
| **007** | Human Protective Request Cannot Bypass Safety (179) | `EV-L1/3` | AC-007(line 706) | §16 containment·HAG-INV-007 | `human_protective_request_proposal_only`(§5.5 — protective 경계) |
| **010** | Dual-Control Re-arm and Narrow Scope (182) | `EV-L1/3+Security` | AC-010(line 709) | §17 re-arm·HAG-INV-001/003 | `dual_control_effective_distinct`+`partial_rearm_scope_narrows`(§5.6 — liveauth 경계) |
| **011** | Approval and Economic-State Continuity and Non-Revival (183) | `EV-L1/3` | AC-011(line 710) | §18/§20·HAG-INV-012/014 | `approval_expiry_preserves_economic_effect`+`no_automatic_rearm`(§5.7) |
| **012** | Human Authority Replay and Evidence Completeness (184) | `EV-L1/3` | AC-012(line 711) | §22·HAG-INV(evidence) | `human_authority_replay_reconstructs`+all-false(§5.8) |

**ADR-002-015 조항 → Phase-1 분류(core / predicate-only / not-Phase-1)**:

| ADR 조항 | 요지 | Phase-1 분류 | L1 substrate / 소유 (근거) | HAG-EV |
|---|---|---|---|---|
| **§8** (line 253-272) | Effective Principal Graph·collapse·independence | **core (L1 슬라이스)** | `effective_principal_collapse`(§5.1) — 동치류 순수 함수·보수적 병합(unknown edge ⇒ 병합 ⇒ distinct 감소 ⇒ quorum fail-closed). liveauth string-`!=`가 못 잡는 same-person-multi-identity를 잡음. +Security(HAG-EV-001). `/3` 잔여. | **001** |
| **§10** (line 298-315) | Approval Request/Attestation exact binding | **core (L1 슬라이스)** | `approval_binding_exact`+`material_change_invalidates`(§5.2) — digest가 전 §10 bound context cover; 물질적 변경 ⇒ 무효(classify_record_pair CRITICAL_CONFLICT). +Security(HAG-EV-002). | **002** |
| **§11/§18** (line 318-338·509-526) | Approval Set validation·consumption·lifecycle | **core (L1 슬라이스)** | `approval_set_single_use`+`stale_replayed_rejected`(§5.3) — single-use 소비·stale/expired/revoked/superseded/broader/replayed 거부; REQUESTED→...→CONSUMED 상태기계. +Security(HAG-EV-004). | **004** |
| **§7/§16** (line 236-249·423-439) | Authority classes·break-glass 방향 | **core (L1 슬라이스)** | `break_glass_direction_restrictive`(§5.4) — break-glass ⊆ {HALT, NARROW, REQUEST_PROTECTIVE}; expand/transmit/re-arm 불가(HAG-INV-006). **spg action-token 경계**(§3.5). +Security(HAG-EV-006). | **006** |
| **§16** (line 423-439) | Human containment request = proposal | **core (L1 슬라이스)** | `human_protective_request_proposal_only`(§5.5) — 인간 label ↛ protective classification(protective seam)·↛ capacity·↛ egress(HAG-INV-007). **protective 경계**(§3.5). | **007** |
| **§17** (line 442-457) | Dual-control re-arm·narrow scope | **core (L1 슬라이스)** | `dual_control_effective_distinct`+`partial_rearm_scope_narrows`(§5.6) — collapse-before-count(≥2 distinct effective persons)·new ⊆ prior. **liveauth 경계**(§3.5 — HAG는 distinctness *의미*, liveauth는 count 소비). +Security(HAG-EV-010). | **010** |
| **§18/§20** (HAG-INV-012 line 202·HAG-INV-014 line 210·§18 line 524-526·§20 line 553) | Approval expiry ↛ economic effect·no auto re-arm | **core (L1 슬라이스)** | `approval_expiry_preserves_economic_effect`+`no_automatic_rearm`(§5.7) — expiry/revocation ↛ cancel/release/UNKNOWN/re-arm(HAG-INV-012); recovery ↛ auto re-arm(HAG-INV-014). liveauth `authorization_revived_by_nothing`·iap `economic_effect_outlives` 동형(인간 축). | **011** |
| **§22** (line 578-596) | Human authority replay·evidence completeness | **core (L1 슬라이스)** | `human_authority_replay_reconstructs`+evidence-is-not-authority all-false(§5.8) — digest-bound append-only 레코드·classify_record_pair replay 탐지; evidence ↛ enforcement(§22 line 596). | **012** |
| **§12** (line 341-359) | Separation of Duties (10 role-conflict) | **predicate-only** | `separation_of_duties_satisfied`(§6.1) — 10 금지 조합을 effective principal 위에 판정(HAG-INV-003). 실 identity/roster는 +Security. 최소 `EV-L2/3+Security`. | **003** |
| **§15/§20** (line 402-419·547-555) | Independent Human HALT availability·propagation | **predicate-only** | `human_halt_monotonic_restrictive`+`degraded_path_no_permissive`(§6.2) — HALT command 모델·monotonic-restrictive·degraded path는 permissive 불가(§15 line 417). 실 availability/propagation timing(B_human_halt_to_commit)은 +Security 런타임. 최소 `EV-L2/3+Security`. | **005** |
| **§13** (line 362-378) | Delegation/roster/recovery fencing | **predicate-only** | `delegation_bounded_nontransitive`(§6.3) — non-transitive·bounded·revocable·grantor 권한 초과 불가(HAG-INV-009). 실 roster/recovery 메커니즘은 +Security. 최소 `EV-L2/3+Security`. | **008** |
| **§19** (line 529-543) | Approver/workflow compromise containment | **predicate-only** | `compromise_fails_closed`(§6.4) — 의심 compromise ⇒ 영향 pending authority 무효·scope 제한·economic effect 보존(HAG-INV-010). 실 detection/reconciliation은 +Security. 최소 `EV-L2/3+Security`. | **009** |
| **§17.1** (line 459-505) | Governed Single-Operator Variant 계열 | **predicate-only (liveauth 소비 표면 중첩)** | 013 pre-approved non-ad-hoc·014 time-separated re-auth·015 independent attestation·016 external reviewer·017 variant cannot expand — **liveauth가 re-arm 소비 인스턴스 이미 실현**(`Safe053VariantAttestation` 7-control·`ReArmPathKind`). HAG 잔여 = §5.10-5.12 **general-model 정의**·HAG-INV-015..019(variant는 pre-approved policy 모델·non-ad-hoc 판정)·effective-principal collapse가 external reviewer의 operator-붕괴 판정(§17.1.4·HAG-INV-018)에 적용. 전부 `EV-L2/3+Security`. **정직한 L1 잔여 최소**(§6.5). | **013–017** |
| **§17.1** (line 459-505) | Operator config/authorization error fail-closed | **predicate-only** | `operator_config_authz_error_fail_closed`(§6.6) — variant 미선언·잘못 설정 ⇒ 거부(HAG-INV-015). 최소 `EV-L2/3+Security`. | **018** |
| **§5** (line 102-153) | Definitions — 12 vocabulary | **core substrate(분산)** | 12-정의·`AuthorityClass`/`AttestationDecision`/`ApprovalLifecycleState` 어휘(§2). policy governance는 spg/ADR-002-014(§9 line 292). | 001-012 공통 |
| **§9 policy content·§14 auth·§20 availability·§21 external·§28 open Q·§29 gate** | policy schema·인증·partition·external broker·수치·acceptance | **not-Phase-1 (Phase-0/INSTANCE·런타임)** | 제품·identity provider·수치·human class·external broker는 §9.2 Phase-0. §14 phishing-resistant auth·§21 broker path는 +Security/+Broker 런타임. 전부 주입. | 003/005/008/009 (런타임) |

---

## 2. 데이터 모델 계약

### 2.1 digest-bound / value / reference 분류

| 분류 | 모델 | 근거 |
|---|---|---|
| **digest-bound `IndependentIdArtifact`** (id ⊥ digest·§3.1) | `HumanAuthorityPolicy`·`EffectivePrincipalGraph`·`HumanApprovalRequest`·`HumanApprovalAttestation`·`HumanApprovalSet`·`ApprovalSetConsumptionRecord`·`HumanHaltCommand`·`HumanDelegationRecord` | append-only ledger citizen — same-id/different-bytes 위조/replay를 `classify_record_pair` CRITICAL_CONFLICT로 탐지(§5.2/§5.8; HAG-EV-002/004/012). id는 서비스 부여(≠ `f(digest)`), digest는 §10/§8/§13 immutable claim cover. |
| **value (frozen, id 없음)** | `EffectivePrincipalNode`·`EffectiveControlEdge`(그래프 원소)·`ApprovalScope`(7-차원 frozenset)·`RoleAssignment`·`AttestationInputs`(주입 상태) | id 미도출·mutate 없음. `ApprovalScope`는 liveauth `LiveAuthorizationScope`(`state.py:33`, 7-frozenset)와 **동형 로컬 저작**(축 다름 — human approval scope; import 아님). |
| **enum-token (StrEnum)** | `AuthorityClass`·`AuthorityDirection`(§7)·`AttestationDecision`(§18, non-truthy)·`ApprovalLifecycleState`(§18, non-truthy)·`ConflictRole`(§12) | 어휘(§2.2). |
| **reference (scalar/digest only)** | recovery generation(sbr)·capsule digest(capsule)·venue snapshot digest(venue)·candidate command digest(ioc)·Live Authorization scope(liveauth)·protective classification verdict(protective)·profile/envelope version(spg) | 형제 소유 — 주입 scalar/digest/verdict로만 참조(§3.4/§3.5). HAG는 이들을 저작·import하지 않음. |

### 2.2 어휘 (verbatim 전사 + truthy 봉인)

**(1) `AuthorityClass` / `AuthorityDirection` (§7 line 238-249, closed StrEnum — ADR 고정
표).** ADR §7의 8-class 권위 방향 표를 verbatim 전사:

- `AuthorityClass`: `HALT`·`NARROW`·`REQUEST_PROTECTIVE`·`APPROVE_PROFILE_OR_ENVELOPE`·
   `APPROVE_REARM`·`ACCEPT_RESIDUAL_RISK`·`CAPACITY_MUTATION`·`TRANSMIT`.
- `AuthorityDirection`(방향 축): `STRICTLY_RESTRICTIVE`(HALT)·`PROVEN_RESTRICTIVE`(NARROW)·
   `PROPOSAL_ONLY`(REQUEST_PROTECTIVE)·`MAY_INCREASE`(APPROVE_*/ACCEPT_RESIDUAL_RISK)·
   `ECONOMIC_AUTHORITY`(CAPACITY_MUTATION)·`IRREVERSIBLE_BOUNDARY`(TRANSMIT).
- **closed StrEnum 판정**: §7 표는 **고정 taxonomy**(ADR 조항이 8-class 열거)이므로 policy-open
   아님(venue `SessionPhase` open-token과 대비 — venue #19 §0.4d v1.1 M4 판정 동형). §7 line
   249 verbatim: "Any action whose direction cannot be proven is authority increasing." ⇒
   **`None`/미증명 방향 ⇒ MAY_INCREASE로 취급**(fail-closed default·§5.4).

**(2) `AttestationDecision` (§18 line 523, non-truthy StrEnum — 핵심 truthy 봉인).**
`APPROVE`·`DENY`·`ABSTAIN`. **`_NonTruthyStrEnum` 상속**(iap `vocabulary.py:50` 동형 로컬
재표현) — `__bool__ ⇒ TypeError`. **근거**: `DENY`/`ABSTAIN`은 non-empty string이라 `if
decision:` 오용이 **거부를 truthy로 오독하는 치명적 fail-open**(§10 line 314 "Silence,
timeout, absence, emoji, chat acknowledgement... is not approval"). 소비 게이트는 **`decision
is AttestationDecision.APPROVE` 명시 비교 강제**(§4.7·§7 회귀).

**(3) `ApprovalLifecycleState` (§18 line 511-518, non-truthy StrEnum).** `REQUESTED`·
`REVIEWABLE`·`ATTESTING`·`QUORUM_SATISFIED`·`CONSUMED`(진행)·`DENIED`·`EXPIRED`·`INVALIDATED`·
`REVOKED`·`SUPERSEDED`(터미널). **`_NonTruthyStrEnum`** — 터미널 상태 truthy fail-open 방지.
§18 line 521 verbatim: "Only `QUORUM_SATISFIED` may become `CONSUMED`... No terminal or
invalid state returns to a permissive state." 상태기계 arrow는 §5.3에서 술어로 판정(레코드는
판정 안 함 — liveauth `LiveAuthorizationTransitionRecord` 선례).

**(4) `ConflictRole` (§12 line 345-354, closed StrEnum).** SoD 판정 대상 role 열거:
`TRADING_PROPOSER`·`TRADE_APPROVER`·`ENVELOPE_PROFILE_AUTHOR`·`LIMIT_APPROVER`·`LIVE_ARMER`·
`EVIDENCE_PRODUCER`·`EVIDENCE_REVIEWER`·`RECOVERY_COORDINATOR`·`REARM_APPROVER`·
`POLICY_ADMIN`·`IDENTITY_ROSTER_ADMIN`·`CREDENTIAL_ROUTE_ADMIN`·`APPROVAL_SET_VERIFIER`·
`DOWNSTREAM_ISSUER`·`BREAK_GLASS_CUSTODIAN`·`BYPASS_APPROVER`(§12의 10 금지쌍이 참조하는
role). closed — §12는 최소 금지쌍을 고정 열거(policy가 추가 가능하나 최소는 waive 불가).

### 2.3 아티팩트 covered + self-exclusion (설계 #4 §3.3 상속)

- 모든 digest-bound 아티팩트는 `IndependentIdArtifact`(canonical `_base.py:328`)를 상속 —
   `_ID_FIELD`(독립 id·digest preimage에서 self-exclusion)·`_COVERED_FIELDS`(digest cover)·
   `_REQUIRED_COVERED`(구조 identity 최소 필수)를 선언(liveauth `records.py` 선례 동형).
- **coordinate 비붕괴(설계 #4 §4.4)**: mutable `ApprovalLifecycleState`는 아티팩트 covered
   digest에 **미포함** — 정당한 lifecycle 전이(예: `REVIEWABLE → ATTESTING`)가 digest를 바꿔
   same-id/different-bytes CRITICAL_CONFLICT로 오탐되지 않도록(liveauth `records.py:15-21`
   coordinate-non-collapse 선례). 현재 상태는 술어에 주입되고 별도 transition record로
   append-only 기록.
- `_REQUIRED_COVERED`는 **구조 identity/scope/generation** 필드만 — quorum N·age 같은 numeric
   bound은 제외(Phase-1 null profile 하에서 아티팩트가 구성 가능하도록); 누락 numeric claim은
   소비 술어에서 fail-closed(liveauth `records.py:9-13` 선례).

### 2.4 핵심 모델 필드 골격 (§ref·형제 seam·all-false)

> 필드는 **골격**이다(구현 시 §10/§8/§13 전 bound 필드 반영). 형제 소유 값은 전부 scalar/
> digest/verdict scalar. **extra="forbid"**(모델 필드 수준 과대 주장 금지).

- **`HumanAuthorityPolicy`** (§5.3·§9): `policy_id`(독립)·`policy_generation`(ordering)·roles·
   `quorum_by_approval_type`(주입 N)·independence_constraints·conflict_rules·scopes·
   `authentication_strength`·validity·delegation_rules·recovery_rules·emergency_rules·
   `human_authority_effect: HumanAuthorityEffect`(all-false). **spg governance 대상**(§9 line
   292 Critical artifact·ADR-002-014) — HAG는 content author, spg activation 소비자(§3.5).
- **`EffectivePrincipalGraph`** (§5.2·§8): `graph_id`·`graph_generation`(ordering)·
   `nodes: tuple[EffectivePrincipalNode, ...]`·`edges: tuple[EffectiveControlEdge, ...]`
   (control 관계: reset/impersonate/mint-credential/approve-as/change-role — 각 edge는
   `resolved: bool | None` 좌표 보유: `resolved is not True` ⇒ **control 가능으로 보수적 병합**
   [per-edge, fine-grained·§4.1])·`unresolved_control: bool | None`(**graph-level 완전성
   플래그**). **의미 택일(MAJOR-2)**: graph-level 플래그는 *어느* node/edge가 누락인지 식별
   불가 ⇒ per-edge 병합 불가능 ⇒ `True`/`None`(미증명/미완전) ⇒ **전면-거부**(graph 완전성
   미증명 ⇒ quorum/SoD/dual-control 판정 자체 거부; ADR §8:271 "incompletely resolved... is
   denial"). 2층: per-edge `resolved`(fine-grained 병합) + graph-level `unresolved_control`
   (coarse 전면-거부). evidence `effective_principal_graph_digest`(`replay.py:115`)로 하류 참조.
- **`HumanApprovalRequest`** (§5.4·§10): `request_id`·`request_type: AuthorityClass`·nonce·
   predecessor·creation_generation·`requested_action`·`maximum_authority: AuthorityClass`·
   `scope: ApprovalScope`·evidence_package_digest(sbr scalar)·artifact/generation set(전
   §10 line 306-308 digest scalar)·reason·requested_validity·consumption_rule·
   invalidation_conditions·`human_authority_effect`(all-false). **`HumanApprovalRequest`가
   capsule identity/digest를 bind**(ADR §10 line 306 "Decision Context Capsule identity and
   digest"·request→capsule 방향); capsule `approval_request_id`(`capsule.py:161`)는 iap 자동 축
   (Bindings) 소유이므로 HAG 하류 참조 **아님**(MAJOR-1 정정).
- **`HumanApprovalAttestation`** (§5.5·§10 line 312): `attestation_id`·`request_digest`
   (정확 바인딩)·`principal_id`·`effective_principal_graph_generation`·`role`·
   `decision: AttestationDecision`·reviewed_inputs·independent_recompute_result·
   authenticator_session_context·issue_time·expiry·signature_ref·`human_authority_effect`
   (all-false). **개별 인간 결정** — iap엔 부재(자동 결정 축).
- **`HumanApprovalSet`** (§5.6·§11): `set_id`·`attestations: tuple[HumanApprovalAttestation,
   ...]`·`policy_generation`·`graph_generation`·`bound_request_digest`·`human_authority_
   effect`(all-false — §5.6 "not Live Authorization and grants no broker or capacity
   authority"). evidence `approval_set_id`(`envelope.py:93`)로 하류 참조.
- **`ApprovalSetConsumptionRecord`** (§5.8·§11): `consumption_id`·`approval_set_digest`·
   `downstream_decision_ref`·`single_use: bool`·consumed_generation(ordering)·`human_
   authority_effect`(all-false). single-use 원자 소비(§5.3).
- **`HumanHaltCommand`** (§5.9·§15): `command_id`·`principal_id`·`scope: ApprovalScope`·
   environment·nonce·`policy_generation`·`session_generation`·`restrictive_generation`
   (ordering·monotonic)·trustworthy_time_generation·`human_authority_effect`(all-false ─
   **permissive 전부 false**; restrictive latch 설정은 정의된 효과이지 permissive 권위 아님).
- **`HumanDelegationRecord`** (§13): `delegation_id`·grantor_principal·delegate_principal·
   role·scope·validity·`transitive: bool`(기본 false)·revocation_generation·`human_
   authority_effect`(all-false).

**all-false `HumanAuthorityEffect`** (HAG-INV-004·§5 SoD·§16 — 로컬 저작, liveauth
`LiveAuthorizationEffect` `_base.py:75`·iap `ApprovalAuthorityEffect` 동형): 6 flag 전부
`False`·`model_validator(mode="after")`가 **any True ⇒ `ArtifactIntegrityError`**:
`mutates_capacity`·`activates_configuration`·`issues_live_authorization`·`clears_deny_latch`·
`transmits_to_broker`·`re_arms`. §4.3 defence-in-depth 술어로 `model_construct` 우회 대비.
**로컬 재표현 정당**(flag 이름이 human-authority 고유 — liveauth `_base.py:16-19` "flag names
differ, local re-expression justified" 선례; PROMOTE 아님).

---

## 3. canonical / ordering REUSE + sibling edge 0 + 형제 경계

### 3.1 canonical REUSE

`tos.canonical`에서 REUSE(재정의 금지·설계 #4 §0.4d): `FrozenModel`(`_base.py:73`)·
`DigestBoundArtifact`(`_base.py:98`)·`IndependentIdArtifact`(`_base.py:328` — 8 digest-bound
아티팩트 base)·`classify_record_pair`(`record_pair.py:52`)+`RecordPairKind`(`record_pair.py:31`
— {IDEMPOTENT_DUP·CRITICAL_CONFLICT·DIVERGENT_EMISSION·DISTINCT·NOT_COMPARABLE})·
`ArtifactStatus`(`_base.py:58`)·`ArtifactIntegrityError`(`_base.py:50`)·
`EVL1ProvisionalCanonicalizer`(`canonicalization.py:173`). **PROMOTE 0건** — 전부 이미 core.

### 3.2 ordering REUSE (approval lifecycle·generation monotonic 순서)

`tos.ordering`(`Ordering`·`OrderingEvent`·`compare_order`) REUSE — **approval set consumption
순서**(§11 line 333 "ordered through ADR-002-012 or a transactionally coupled linearizable
namespace")·graph/roster/policy generation monotonic 순서(§8/§13/§9)·restrictive HALT
generation(§15). ordering는 `from tos.canonical import FrozenModel`만 의존이라 core. **순서
substrate만 제공** — HAG가 generation의 *의미/fencing*(무효화·supersession) 소유(§4.5 non-
collapse canary).

### 3.3 REUSE 요약 표

| 대상 | REUSE 원천 | 용도 | edge |
|---|---|---|---|
| digest-bound base·conflict 탐지 | `tos.canonical` | 8 아티팩트·replay/forgery(HAG-EV-002/004/012) | core(직접) |
| monotonic 순서 | `tos.ordering` | lifecycle·generation·HALT 순서 | core(직접) |
| 형제 결과(liveauth/spg/iap/protective/replacement/authority/sbr/capsule/evidence/venue/ioc/brokercap/time) | — | scalar/bool/enum-token/verdict/digest 주입 | **sibling edge 0**(§3.4) |

### 3.4 형제 경계 — scalar·bool·enum-token·verdict·digest seam (edge 0, 코드 실측)

HAG는 형제 타입을 **import·REUSE 하지 않고** 결과만 주입받는다:

- **liveauth**(ADR-002-007): re-arm은 HAG approval-set을 소비 — HAG는 `distinct_effective_
   principal_count`(collapse 산출) verdict를 **생산**, liveauth `DualControlAttestation.
   distinct_approver_count`(`state.py:180`)가 소비. HAG는 liveauth import 안 함(§3.5 최대
   경계).
- **spg**(ADR-002-014): safety-config break-glass action-token confinement(`break_glass_
   confined` `predicates.py:746`)·policy activation verdict를 주입 소비. HAG는 spg import 안
   함(§0.4d).
- **iap**(ADR-002-023): 자동 per-proposal 결정 — 별개 축(§0.4e). HAG는 iap import 안 함.
- **protective**(ADR-002-001): `protective_classification`(`predicates.py:246`) verdict를
   주입 소비(§16 human containment). HAG는 protective import 안 함(§0.4d).
- **replacement**(ADR-002-011)·**rcl**(ADR-002-002): replace/capacity 판정 — HAG containment
   request의 하류. verdict scalar 주입.
- **authority**(ADR-002-003): `halt_denies`(`predicates.py:401`)·`restrictive_dominates`
   (`predicates.py:307`) HALT precedence를 개념 참조(HAG HALT command는 restrictive
   generation을 set; precedence는 authority 소유). HAG는 authority import 안 함.
- **sbr**(ADR-002-017): recovery generation/package/readiness digest 주입(§17 re-arm은 current
   recovery 필요). scalar.
- **capsule**(ADR-002-018)·**venue**(ADR-002-019)·**ioc**(ADR-002-020): approval이 binding하는
   capsule/venue/command digest 주입 소비(§10 line 306-308·ADR §1 line 30). scalar.
- **evidence**(ADR-002-016): HAG 아티팩트가 evidence store로 흘러 replay(§22) — evidence가 HAG
   digest를 carry(`replay.py:114-115`·`envelope.py:56/93`). HAG는 evidence import 안 함
   (evidence가 하류).
- **time**(ADR-002-008): trustworthy-time generation·freshness 주입(§14/§17.1.2 cooling). scalar.

### 3.5 소유권 분할표 — HAG가 소유 / 형제에서 소비·생산 (본 문서 최대 함정 지대, #11-#19 §3.5 상속)

> **소유권 분할 명시(#8·#11-#19 교훈 — cross-section 혼동 선제 봉합)**: ADR-002-015는 **인간
> 권위 일반 모델**(effective-principal identity·human authority policy·approval request/
> attestation/set/consumption·SoD·delegation·human HALT command·break-glass 방향·approval
> lifecycle·compromise 응답)만 결정하며(§4 line 75-85) **live authorization(liveauth)·re-arm
> 소비 인스턴스(liveauth)·safety-config break-glass token(spg)·자동 per-proposal 결정(iap)·
> protective classification/capacity(protective/rcl)·replace(replacement)·HALT precedence
> (authority)·recovery workflow(sbr)·capsule/venue/command 구성(capsule/venue/ioc)·evidence
> custody(evidence)·final egress(ADR-002-013)·currentness(ADR-002-024)를 소유하지 않는다**.
> 함정: HAG가 liveauth re-arm 소비·spg break-glass token·iap 자동 결정·protective
> classification을 재저작하면 권위 중복(#8 lesson). 아래 표가 경계를 코드 실측으로 고정한다.

| ADR 조항/개념 | HAG 소유 (Phase 1) | 형제 소유 (재저작 금지) | seam 방향(실측) |
|---|---|---|---|
| **§8 Effective Principal collapse** | `EffectivePrincipalGraph`·`effective_principal_collapse`(동치류 순수 함수·보수적 병합) | (없음 — HAG 고유 노른자) | HAG=collapse author; liveauth string-`!=`(`predicates.py:525`)가 못 잡는 same-person을 HAG가 잡아 count verdict 생산 |
| **§17 re-arm dual-control** | collapse-before-count의 **의미**·`dual_control_effective_distinct`(§5.6)·narrow-scope | **re-arm 소비 인스턴스는 liveauth**(`rearm_dual_control_satisfied` `predicates.py:492`·`Safe053VariantAttestation`·`ReArmPathKind`·13-prereq·7-control) | **본 문서 최대 경계**: HAG는 distinct effective principal count *생산*(collapse); liveauth는 그 count *소비*(re-arm). HAG↛liveauth·liveauth는 opaque string으로 HAG에 이연(`state.py:172-175`) |
| **§7/§16 break-glass 방향** | 인간 authority-class 방향 confinement(§7 8-class)·containment=proposal·effective-principal independence(spg가 명시 이연) | **safety-config action-token은 spg**(`break_glass_confined` `predicates.py:746`·`{HALT, RESTRICTIVE_OVERRIDE}` `vocabulary.py:258`) | **2대 경계**: spg=config action token(2); HAG=human authority-class direction(8)+spg가 `predicates.py:755-758`에서 HAG로 명시 이연한 independence. 다층 방어 |
| **§16 human containment** | 인간 요청은 proposal이지 authority 아님(§5.5) | **classification은 protective**(`protective_classification` `predicates.py:246`)·capacity는 rcl·replace는 replacement·transmit은 ADR-002-013 | HAG=proposal-only 술어; protective/rcl/replacement/egress=실 판정. label ↛ bypass(HAG-INV-007) |
| **§10/§11 approval** | `HumanApprovalRequest/Attestation/Set`·quorum-independence·single-use consumption(인간 축) | **자동 per-proposal 결정은 iap**(`IndependentApprovalDecision`·`ProposalApprovalRequest`; ADR-002-023) | **별개 축**(ADR §4 line 98): 인간 quorum ≠ 자동 결정; 상호 대체 불가. 명명 "Human" prefix로 구분 |
| **§12 Separation of Duties** | 인간 role-conflict 10 금지쌍(effective principal 위) | **capability-lease exclusivity는 authority**(`lease_scope_exclusive` `predicates.py:425`·SA-INV-006) | 다른 축: authority=`(scope, capacity_lease_id)` 유일성; HAG=human role 충돌. 재저작 아님 |
| **§15 Human HALT** | `HumanHaltCommand` 아티팩트·monotonic-restrictive 술어·degraded no-permissive | **HALT precedence/dominance는 authority**(`halt_denies` `predicates.py:401`·`restrictive_dominates`)·final egress latch는 ADR-002-013·deny-first 순서는 ADR-002-024 | HAG=human command author(restrictive generation set); authority=precedence; egress/ADR-002-024=enforce·순서(런타임) |
| **§9 policy governance** | `HumanAuthorityPolicy` content | **activation/generation/supersession은 spg**(ADR-002-014·§9 line 292 Critical artifact) | HAG=content author; spg=activation authority; HAG는 activation verdict 주입 소비 |
| **§17 recovery binding** | approval이 recovery generation binding | **recovery workflow는 sbr**(Recovery Barrier/Generation/Package/Readiness; ADR-002-017) | HAG는 sbr digest 주입 소비; human ↛ force READY(§28 q14) |
| **§10 context binding** | `approval_binding_exact`·전 bound context digest cover | **capsule/venue/command 구성은 capsule/venue/ioc** | HAG는 digest scalar 소비·binding만; 구성 안 함 |
| **§22 evidence** | replay 레코드 substrate(digest-bound append-only) | **custody/gap/replay ENGINE은 evidence**(ADR-002-016) | HAG=레코드 citizen; evidence=custody(HAG digest carry `replay.py:114-115`); evidence ↛ enforcement(§22 line 596) |

> **핵심 판정 (a) — HAG collapse ≠ liveauth string-distinctness(본 문서 최대 아키텍처 공격
> 지점)**: **두 곳 모두 "두 승인이 별개인가"를 본다.** liveauth `rearm_dual_control_satisfied`
> Path 1(`predicates.py:523-527`)은 `limit_change_approver_principal != armer_principal and
> distinct_approver_count >= 2` — **opaque 문자열 부등호 + 주입 count**로 판정하고, HAG §8
> `effective_principal_collapse`는 "두 식별자가 **같은 자연인으로 붕괴하는가**"(계정/자격/장치/
> 복구/관리 통제 동치류)를 판정한다. **예시**: `armer="alice-svc-01"`, `limit_change=
> "alice-svc-02"`가 liveauth `!=`엔 distinct(둘 다 alice의 서비스 계정이라도 문자열 다름)이나
> HAG collapse엔 **1 principal**(같은 alice가 둘 다 통제) ⇒ quorum 미충족. **런타임 계층**:
> HAG collapse가 **먼저** 실행 → distinct count 산출 → liveauth `distinct_approver_count`로
> 주입. liveauth 도크스트링(`state.py:172-175`)이 "actual human authentication is
> ADR-002-015 runtime"으로 이 이연을 **명시**. ⇒ HAG↛liveauth import·재저작 0. **리뷰어 공격
> 지점(§10.2)**: "HAG와 liveauth 둘 다 dual-control distinctness = 중복" — 반론: 판정 대상이
> 다르다(effective-person 동치류 *생산* vs opaque count *소비*); liveauth가 HAG에 명시 이연;
> §8 line 267 "Quorum evaluation SHALL collapse all nodes under common effective control
> before counting principals" ─ collapse는 HAG, count는 liveauth.
>
> **핵심 판정 (b) — HAG break-glass ≠ spg break-glass(spg 코드가 HAG 잔여 직접 증언)**: spg
> `break_glass_confined`(`predicates.py:746`)는 **safety-config action-token** {HALT,
> RESTRICTIVE_OVERRIDE}(ADR-002-014 §8·SPG-EV-009)를 소유하고, HAG는 **인간 authority-class
> 방향**(§7 8-class)의 break-glass 제한 + spg가 `predicates.py:755-758`에서 "**ADR-002-015
> HAG-EV +Security — not-Phase-1**"로 명시 이연한 **effective-principal independence**를
> 소유한다. **spg 코드 스스로 HAG를 owner로 지목** ─ 재저작 충돌 부재. safety-config를 건드리는
> break-glass에는 spg confinement이 다층 방어로 함께 적용(venue ioc/VTG defense-in-depth
> 동형). **리뷰어 공격 지점(§10.2)**: "HAG-EV-006가 SPG-EV-009 재저작" — 반론: spg
> `predicates.py:755-758` 명시 이연·다른 ADR clause·다른 vocabulary(2-token vs 8-class)·다른
> register 행.
>
> **핵심 판정 (c) — HAG human approval ≠ iap automated approval(ADR §4 명시 분리)**: iap
> `IndependentApprovalDecision`(`iap/__init__.py:145`)은 **시스템 자동 per-proposal 결정**,
> HAG `HumanApprovalAttestation`은 **인간 principal 인증 결정**. ADR §4 line 98 verbatim: "an
> automated `APPROVE` cannot satisfy a human quorum." 두 축은 principal 개념 유무부터 다르다
> (iap는 principal 없음·HAG는 effective-principal collapse 중심). 명명 "Human" prefix로 불가역
> 구분(§0.4e). **리뷰어 공격 지점(§10.2)**: "approval-set·single-use가 iap와 중복" — 반론: 축
> 분리·ADR §4 line 98·principal 개념 상이.

---

## 4. 불변식

> 앵커: HAG-INV-001..019(§6)·HAG-AC-001..012(§26)·HAG-EV-001..018(register). 각 술어는
> §-clause·INV·AC·EV·SAFE-###에 매핑(§27 traceability). **core = L1 슬라이스 저작**,
> **predicate-only = 술어만·EV 닫지 않음**.

### 4.1 effective-principal collapse 중앙 불변식 (YOLK — core; §8; HAG-INV-001; HAG-AC-001; HAG-EV-001)

**중앙 불변식**: 두 필수 인간 승인은 **두 개의 별개 effective 자연인**에서 와야 한다 — 계정·
세션·자격·장치·role label 두 개가 아니라(§8 line 267·HAG-INV-001). **collapse 순수 함수**:
`EffectivePrincipalGraph`의 control 관계(reset/impersonate/mint-credential/approve-as/
change-role)로 연결된 노드는 **하나의 effective principal로 붕괴**(동치류 = control 그래프의
연결 성분). quorum 판정은 **collapse 후 distinct 성분 수를 count**.

- **fail-closed 병합 방향(중심)**: control edge가 **UNKNOWN/미해소**면 **edge 존재로 보수적
   병합**(§8 line 271 "Unknown, stale, contradictory, or incompletely resolved effective-
   control state is denial for authority increase"). 병합 ⇒ distinct 성분 **감소** ⇒ quorum
   **더 어려움**(fail-closed). SoD(§4.x·§6.1)에서도 병합 ⇒ 같은 사람 ⇒ 충돌 더 많음
   (fail-closed). **양방향 동일 fail-closed** — "unknown ⇒ 같은 사람 가정"이 quorum·SoD 둘 다
   보수적.
- **미표현 principal 봉인(MAJOR-2·중심)**: 증언 principal이 graph node에 없으면 순진한
   연결성분 구현이 **고립 singleton class로 세어 quorum을 통과**시킨다(ADR §2:40 1순위 공격
   "one person approving twice through two accounts" 정확 통과). ⇒ **모든 증언 principal ∈
   `graph.nodes` AND `graph.unresolved_control is False` 필수**, 하나라도 미표현/미해소 ⇒
   **즉시 거부**(ADR §8:271 "incompletely resolved effective-control state is denial") —
   collapse 이전 게이트(§5.1 조건 (vii)).
- **∅/1인 거부(vacuous-∅ 봉인·#6 M1 교훈)**: quorum N ≥ 1에서 attestation ∅ ⇒ distinct 성분
   0 < N ⇒ 거부. 1 attestation ⇒ 1 성분 < 2(re-arm) ⇒ 거부. **`count >= N` 판정이 ∅에서
   vacuous-True 되지 않도록** N ≥ 1 강제(authority `lease_scope_exclusive`가 v1.0 `0 <= 1`
   vacuous-True fail-open을 non-empty로 봉한 `predicates.py:425` M1 선례 상속). policy
   quorum N=0은 **degenerate ⇒ 거부**(all-false authority — 인간 없이 authority 증가 불가).

### 4.2 exact approval context binding 중앙 불변식 (core; §10; HAG-INV-002/008; HAG-AC-002; HAG-EV-002)

모든 approval은 **하나의 정확한** request/scope/evidence generation/profile·envelope
generation/software·deployment identity/broker·egress context/reason/policy/validity를
binding(§10 line 300-310·HAG-INV-002). **물질적 변경 ⇒ 사전 미소비 approval 무효**(§1 line
30·HAG-INV-008): input·capsule·venue·intent·evidence·scope·digest·generation·software·
deployment·broker·credential·route·time·residual·policy 중 하나라도 변경 ⇒ 새 request+approval
필요. **탐지 메커니즘**: `HumanApprovalAttestation.request_digest`가 request 전 bound context를
cover ⇒ 변경 시 digest 불일치 ⇒ `classify_record_pair`가 same-id/different-bytes를
**CRITICAL_CONFLICT**로 탐지(canonical `record_pair.py`; HAG-EV-002 substrate).

### 4.3 approval-is-not-authority all-false 불변식 (core+predicate; §5·§16; HAG-INV-004; HAG-EV-004)

`HumanApprovalAttestation`/`Set`/`Request`/`HaltCommand`/`Delegation`의 `human_authority_
effect`는 **6 flag 전부 False**(§4.4 어휘). approval attestation/set은 capacity mutate·config
activate·Live Authorization issue·deny latch clear·broker transmit 불가(§5.6·HAG-INV-004).
any True ⇒ `ArtifactIntegrityError`(구성 불가). **fail-open 봉인(#6 REJECT 교훈)**: "assume-
authority" 경로 부재 — authority는 오직 positive proof(quorum + downstream issuer)에서만.
defence-in-depth: `model_construct`(validator 우회) 대비 소비 술어에서도 all-false 재확인
(protective `__init__` "no assume-admissible path anywhere" 동형).

### 4.4 break-glass directional confinement 불변식 (core; §7/§16; HAG-INV-006; HAG-AC-006; HAG-EV-006)

break-glass authority는 **restrictive-only**: `AuthorityClass ∈ {HALT, NARROW,
REQUEST_PROTECTIVE}`만(§7 표·§16 line 425). **불가**: create/restore/broaden/prolong new-risk
authority·auto-revert(HAG-INV-006)·general broker client/credential/signer/session/route 보유
(§16 line 425). **spg 경계**(§3.5 (b)): HAG는 authority-class 방향(8-class) 소유; spg는
config action-token(2) 소유. `break_glass_direction_restrictive`(§5.4)는 HAG §7 taxonomy 위
술어(spg `break_glass_confined` 재저작 아님).

### 4.5 approval/economic continuity + non-revival 불변식 (core+predicate; §18/§20; HAG-INV-012/014; HAG-AC-011; HAG-EV-011)

approval expiry/revocation/consumption은 **경제적 효과를 취소하지 않는다**(HAG-INV-012 line 202): order cancel·capacity release·UNKNOWN resolve·broker non-acceptance 증명·final
quantity 증명 불가. **recovery ↛ auto re-arm**(HAG-INV-014 line 210): 인간/자격/장치/IdP/
workflow/approval service/control plane 복구가 approval 재사용·live authority 자동 복원 불가.
`no_automatic_rearm`(§5.7)은 무조건 True(구조적 부재 — 어떤 recovery/timeout/restart flag도
admissibility로 전환 불가; liveauth `no_automatic_rearm` `predicates.py:606`·`authorization_
revived_by_nothing` `predicates.py:777` 동형·인간 축). **generation non-collapse canary**(§4.5
#17 상속): revocation/policy generation을 다른 generation 좌표로 대체하면 fencing 불성립을
보존.

### 4.6 HALT asymmetric + monotonic 불변식 (predicate; §15; HAG-INV-005/011; HAG-EV-005)

한 인증된 authorized 인간이 **proposer/strategy/dual-control quorum/live-arming service 없이**
restrictive HALT 가능(§15 line 406·HAG-INV-005). HALT command는 **monotonic restrictive**만
(§15 line 410)·economic effect 보존(§15 line 414)·degraded path(Safety Commit Log 불가)에서
**permissive command 절대 불가**(§15 line 417). duplicate HALT idempotent·ambiguous HALT ⇒
possibly-applied·re-arm 불가(§15 line 419). **비대칭**: authority 감소가 증가보다 쉬움(§1 line
26). authority `halt_denies`(`predicates.py:401`) precedence REUSE(개념)·HAG는 human command
아티팩트 소유. **availability/propagation timing(B_human_halt_to_commit)은 +Security 런타임**
(HAG-EV-005 L2) — L1 substrate는 command 모델·monotonicity·degraded-no-permissive 술어.

### 4.7 ∅-공허 fail-closed + truthy-sentinel 소비 계약 + 집합 양방향 (양방향 명시 — #12/#13/#14 교훈)

- **∅ 양방향(#12)**: (거부 방향) ∅ approval set ⇒ 0 distinct principal < N ⇒ authority
   불가; ∅ roster ⇒ quorum 불가(HALT는 §20 pre-provisioned authenticator degraded path);
   ∅ scope approval ⇒ 무엇도 승인 안 함(liveauth `scope_covers` ∅ ⇒ False 동형). (허용
   방향) ∅ scope는 **정당한 de-authorization/narrowing**(liveauth `partial_rearm_scope_
   narrows` Gap-2 동형 — `∅ ⊆ prior` True이나 이후 어떤 action도 cover 안 함). **양쪽 명시**.
- **집합 양방향(#14)**: effective-principal collapse는 **집합 위 연산**. (distinct 방향) 서로
   다른 자연인 집합 ⇒ count = |persons|. (병합 방향) 한 사람의 다중 신원 집합 ⇒ count = 1(≠
   |identities|). unknown control ⇒ 병합(fail-closed·§4.1). **`count >= N`이 ∅/1에서
   vacuous 안 되도록** non-empty + N ≥ 1 강제(authority `lease_scope_exclusive` M1 non-empty
   봉인 상속).
- **truthy-sentinel 구조 봉인(#13·#14 M1 — 처음부터)**: `AttestationDecision`{APPROVE/DENY/
   ABSTAIN}·`ApprovalLifecycleState`(터미널 5)는 `_NonTruthyStrEnum`(`__bool__ ⇒ TypeError`).
   소비 게이트는 **`decision is AttestationDecision.APPROVE`·`state is ApprovalLifecycleState.
   QUORUM_SATISFIED` 명시 비교**(bare `if decision:`/`if state:` 금지 — DENY/EXPIRED가
   non-empty string이라 truthy fail-open). `bool | None` 주입 조건은 `is True`(None=UNKNOWN=
   fail-closed). iap `_NonTruthyStrEnum`(`vocabulary.py:50`)·ioc `ConformanceResult`
   truthy-seal 동형. §7 회귀 강제.
- **금지 동사 canary(#5 상속)**: HAG 모델에 mutate/activate/issue/transmit/re-arm/clear-latch
   메서드 **구조적 부재**(constructive absence) — all-false + no-method가 fail-open 경로를
   구조로 봉인.

---

## 5. core 술어 — L1 슬라이스 (HAG-EV-001/002/004/006/007/010/011/012 substrate)

> 전부 **순수 함수·fail-closed**: ∅·missing/`None`·미증명 witness·unknown state ⇒ authority/
> coverage/quorum 불가. **어떤 HAG-EV도 닫지 않음**(규율 태그 §1).

### 5.1 `effective_principal_collapse` + `quorum_independence_satisfied` (§8/§11; HAG-EV-001 substrate, core L1 — 노른자·+Security)

- `effective_principal_collapse(graph, principal_ids) -> mapping[principal_id -> class_id]`:
   control 그래프의 연결 성분(union-find/BFS)으로 동치류 산출. **unknown edge ⇒ 보수적 병합**
   (§4.1). 순수·결정론(정렬된 노드 순회).
- `quorum_independence_satisfied(attestations, graph, quorum_n, required_roles) -> bool`:
   `True` **오직** (i) attestation 전부 `decision is AttestationDecision.APPROVE`, (ii)
   collapse 후 **distinct class ≥ quorum_n**, (iii) **중복 class 없음**(한 사람 두 번 count
   금지·§11 line 325 "reject duplicate natural persons"), (iv) required_roles 전부 distinct
   class로 cover, (v) quorum_n ≥ 1(degenerate N=0 거부·§4.1), (vi) graph_generation 현재,
   (vii) **모든 증언 principal ∈ `graph.nodes` AND `graph.unresolved_control is False`**
   (미표현/미해소 ⇒ 즉시 거부·ADR §8:271·MAJOR-2 — 미표현 principal을 고립 singleton으로 세어
   quorum 통과시키는 fail-open 봉인). **∅/1인/미표현/unknown ⇒ False**(§4.1 fail-closed). **liveauth string-`!=`가 못 잡는 same-person
   -multi-identity를 잡음**(§3.5 (a)). [HAG-AC-001; SAFE-050]

### 5.2 `approval_binding_exact` + `material_change_invalidates` (§10; HAG-EV-002 substrate, core L1, +Security)

- `approval_binding_exact(request, attestation) -> bool`: `attestation.request_digest ==
   request.canonical_digest` AND request가 §10 line 300-310 전 필드 cover AND
   attestation이 §10 line 312 전 필드 bind. missing/`None` ⇒ False.
- `material_change_invalidates(prior_request, current_context) -> bool`: bound context 중
   하나라도 변경 ⇒ True(무효). digest 재계산·불일치 탐지. **same-id/different-digest ⇒
   `classify_record_pair` CRITICAL_CONFLICT**(replay/substitution 저항). [HAG-AC-002;
   SAFE-045/046/047]

### 5.3 `approval_set_single_use` + `stale_replayed_rejected` (§11/§18; HAG-EV-004 substrate, core L1, +Security)

- `approval_set_single_use(consumption_record, prior_consumptions) -> bool`: single-use set은
   **한 번만** 소비(§5.8 "A single-use set cannot be consumed again"); `consumption_id` 미사용
   AND set_digest가 prior에 없음. 재소비 ⇒ False(§23 line 611 "Approval consumed twice ⇒
   reject").
- `stale_replayed_rejected(attestation_or_set, current) -> bool`: revoked/superseded/consumed/
   replayed/broader/stale/policy-mismatched ⇒ True(거부·§11 line 329). lifecycle 전이 legality:
   `ApprovalLifecycleState` arrow만 허용(§18 line 511-518; `QUORUM_SATISFIED → CONSUMED`만·
   터미널 무출구·permissive 복귀 없음). [HAG-AC-004; SAFE-035]

### 5.4 `break_glass_direction_restrictive` (§7/§16; HAG-EV-006 substrate, core L1, +Security — spg 경계)

`break_glass_direction_restrictive(authority_class) -> bool`: `True` **오직** `authority_
class ∈ {HALT, NARROW, REQUEST_PROTECTIVE}`(§7 표·§16 line 425). `APPROVE_*`·`ACCEPT_
RESIDUAL_RISK`·`CAPACITY_MUTATION`·`TRANSMIT`·`None`(미증명 방향 ⇒ MAY_INCREASE·§7 line 249)
⇒ False. **spg `break_glass_confined` 재저작 아님**(§3.5 (b) — 다른 taxonomy·spg가 HAG로
independence 명시 이연). auto-revert 불가(HAG-INV-006). [HAG-AC-006; SAFE-042]

### 5.5 `human_protective_request_proposal_only` (§16; HAG-EV-007 substrate, core L1 — protective 경계)

`human_protective_request_proposal_only(request, protective_classification_verdict,
capacity_verdict, egress_verdict) -> bool`: 인간 containment 요청은 **proposal** — `True`
(진행 가능) **오직** (i) `protective_classification_verdict is Admissibility.ADMISSIBLE`
(protective가 독립 분류·주입 verdict·§16 line 429), (ii) capacity가 RCL/exclusive sub-ledger
authorize(주입), (iii) egress가 exact current capability 검증(주입). **인간 label 자체는
protective classification 안 함**(HAG-INV-007·§16 line 438 "If the proposed action cannot be
proven protective, it is risk increasing"). missing verdict ⇒ False. **protective
`protective_classification` 재저작 아님**(§3.5 — verdict 주입 소비). [HAG-AC-007; SAFE-042]

### 5.6 `dual_control_effective_distinct` + `partial_rearm_scope_narrows` (§17; HAG-EV-010 substrate, core L1, +Security — liveauth 경계)

- `dual_control_effective_distinct(attestations, graph) -> bool`: re-arm quorum의
   **collapse-before-count** — `quorum_independence_satisfied(..., quorum_n=2, ...)`
   (§5.1) 재사용(§5.1 조건 (vii) node-membership·`unresolved_control` 전면-거부 게이트 상속·
   MAJOR-2). **≥ 2 distinct effective 자연인**(§17 line 444). external reviewer는
   collapse 후 operator와 다른 class여야 second principal 자격(§17.1.4·HAG-INV-018 — reviewer가
   operator로 붕괴하거나 graph 미표현이면 불인정). **liveauth 경계**(§3.5 (a)): HAG는 distinct count *생산*,
   liveauth `rearm_dual_control_satisfied`(`predicates.py:492`)가 *소비*. HAG↛liveauth.
- `partial_rearm_scope_narrows(prior_scope, new_scope) -> bool`: new ⊆ prior 전 차원(§17 line
   457 "Partial re-arm restores only the exact approved scope"). ∅ new ⇒ 정당한 full
   de-authorization(§4.7 Gap-2·liveauth `partial_rearm_scope_narrows` `predicates.py:649`
   동형). `None` 차원 ⇒ False. [HAG-AC-010; SAFE-053]

### 5.7 `approval_expiry_preserves_economic_effect` + `no_automatic_rearm` (§18/§20; HAG-INV-012/014; HAG-EV-011 substrate, core L1)

- `approval_expiry_preserves_economic_effect(expiry_event) -> bool`: 무조건 True — approval
   expiry/revocation/consumption ↛ order cancel·capacity release·UNKNOWN resolve·non-
   acceptance/final-quantity 증명(HAG-INV-012 line 202·§18 line 525). 구조적 부재(경제
   효과 변경 메서드 없음).
- `no_automatic_rearm(*, health_recovered, timeout_elapsed, reconciliation_completed,
   leader_elected, restart_completed) -> bool`: 무조건 True — 어떤 recovery/timeout/restart도
   auto re-arm 불가(HAG-INV-014 line 210). 구조적: 이 flag들이 admissibility로 전환되는
   경로 부재(liveauth `no_automatic_rearm` `predicates.py:606` 동형·인간 축). [HAG-AC-011;
   SAFE-045/046/047]

### 5.8 `human_authority_replay_reconstructs` + evidence-is-not-authority (§22; HAG-EV-012 substrate, core L1)

- HAG 아티팩트 8종은 digest-bound append-only ledger citizen — replay가 identity·effective
   control·policy·evidence review·approval·denial·HALT·consumption·compromise·external
   activity·re-arm을 **재구성**(§22 line 585·§26 AC-012). `classify_record_pair`가 replay/
   forgery(same-id/different-bytes ⇒ CRITICAL_CONFLICT) 탐지.
- **evidence ↛ authority**(§22 line 596 "Evidence and notification do not substitute for
   enforcement"): replay 레코드는 all-false `human_authority_effect` — 재구성이 authority
   재생성 불가. evidence store/replay는 human-approval/HALT/capacity/transmission authority
   미보유(§22 line 596). [HAG-AC-012; SAFE-051/052]

---

## 6. predicate-only 술어 — ≥ L2 (HAG-EV-003/005/008/009/013-018 substrate, 닫지 않음)

> **최소 ≥ L2** — L1-decidable predicate substrate를 저작하나 **EV를 닫지 않음**(fault
> injection·adversarial·+Security 독립 평가 잔여). liveauth 소비 표면 중첩은 정직하게 표기.

### 6.1 `separation_of_duties_satisfied` (§12; HAG-EV-003 substrate, predicate-only, 최소 EV-L2/3+Security)

`separation_of_duties_satisfied(role_assignment, graph) -> bool`: §12 line 345-354의 **10 금지
조합**(trading proposer ∧ trade approver·envelope/profile author ∧ sole approver·limit
approver ∧ sole armer·evidence producer ∧ reviewer·recovery coordinator ∧ sole re-arm
approver·policy admin ∧ beneficiary·roster admin ∧ all quorum members·credential admin ∧
sole approver·set verifier ∧ downstream issuer·break-glass custodian ∧ bypass approver)를
**effective principal 위**(collapse 후, §5.1 조건 (vii) node-membership·`unresolved_control`
전면-거부 게이트 상속·MAJOR-2 — role_assignment의 모든 principal ∈ `graph.nodes`·미표현/미해소
⇒ 거부)에 판정 — 한 effective 자연인이 금지쌍 양쪽을 보유하면
False(HAG-INV-003). automation은 human principal count 불가(§12 line 358). **authority
`lease_scope_exclusive` 재저작 아님**(§3.5 — capability-lease exclusivity ≠ human role
conflict). 실 identity/roster 검증은 +Security(HAG-EV-003 L2).

### 6.2 `human_halt_monotonic_restrictive` + `degraded_path_no_permissive` (§15/§20; HAG-EV-005 substrate, predicate-only, 최소 EV-L2/3+Security)

- `human_halt_monotonic_restrictive(command, prior_generation) -> bool`: HALT command는
   monotonic restrictive만(restrictive_generation 증가·permissive 불가·§15 line 410). duplicate
   idempotent·ambiguous ⇒ possibly-applied(§15 line 419).
- `degraded_path_no_permissive(command, safety_commit_log_available) -> bool`: Safety Commit
   Log 불가 시 restrictive local latch만 허용·**permissive command 절대 거부**(§15 line 417·
   §20 pre-provisioned authenticator는 finite restrictive만·§20 line 551). 실 availability/
   propagation(`B_human_halt_to_commit`·`B_halt_to_egress`)은 +Security 런타임(§8·HAG-EV-005
   L2).

### 6.3 `delegation_bounded_nontransitive` (§13; HAG-EV-008 substrate, predicate-only, 최소 EV-L2/3+Security)

`delegation_bounded_nontransitive(delegation, grantor_authority, graph) -> bool`: delegation은
one role/scope/env/purpose/validity·**non-transitive**(명시 허용 없으면)·grantor 권한 초과
불가·grantor+delegate가 같은 request에 independent count 불가(effective control 잔존 시)·roster/
role/employment 변경 시 무효(§13 line 364-378·HAG-INV-009). 실 roster/recovery 메커니즘은
+Security(HAG-EV-008 L2).

### 6.4 `compromise_fails_closed` (§19; HAG-EV-009 substrate, predicate-only, 최소 EV-L2/3+Security)

`compromise_fails_closed(compromise_event, affected_scope) -> bool`: 의심 compromise(approver/
authenticator/device/session/IdP/roster/signer/verifier/recovery/break-glass custody) ⇒ 영향
session/delegation/pending attestation/unconsumed set 무효·narrowest restriction·economic
effect 보존·fresh governed recovery 요구(§19 line 531-539·HAG-INV-010). 이미 소비된 approval도
compromise 후 safe 미보장 ⇒ 보수적 suspend(§19 line 541). unknown revocation scope ⇒ authority
증가 차단(§19 line 543). 실 detection/reconciliation은 +Security(HAG-EV-009 L2).

### 6.5 Governed Single-Operator Variant 계열 (§17.1; HAG-EV-013–017 substrate, predicate-only, 최소 EV-L2/3+Security — liveauth 소비 표면 중첩)

**정직한 L1 잔여 표기(과대 주장 금지)**: liveauth(#7)가 §17.1 re-arm **소비 인스턴스**를 이미
실현(`Safe053VariantAttestation` 7-control `state.py:144`·`_SAFE053_CONTROLS` `predicates.py:104`·
`ReArmPathKind` `vocabulary.py:41`·13-환경 prerequisite + drift 회귀 테스트). **HAG 잔여 =
general-model 정의**(§5.10-5.12·HAG-INV-015..019):

- **HAG-EV-013**(pre-approved non-ad-hoc·HAG-INV-015): variant는 approved policy가 exact
   scope로 사전 선언한 경우만·re-arm 시점 선택/확대 불가(§17.1.1). HAG `HumanAuthorityPolicy`가
   variant 선언을 content로 보유(spg activation) — 술어 `variant_pre_declared_exact_scope`.
- **HAG-EV-014**(time-separated re-auth·HAG-INV-016): 두 분리 인증 이벤트 + cooling interval
   (policy-owned·수치 미고정·§17.1.2). 술어는 두 이벤트 분리·cooling 경과 판정(수치 주입).
- **HAG-EV-015**(independent attestation·HAG-INV-017): non-authorizing block-only attestation
   (§17.1.3). **liveauth가 `independent_nonauthorizing_attestation_current` control로 이미
   소비** — HAG 잔여는 attestor가 human principal로 count 안 됨(§12·§8) 판정.
- **HAG-EV-016**(external reviewer·HAG-INV-018): reviewer가 operator로 collapse하면 불인정
   (§17.1.4). **HAG effective-principal collapse(§5.1)가 근거** — 이것이 HAG의 실질 L1 잔여.
- **HAG-EV-017**(variant cannot expand·HAG-INV-019): Non-Waivable Boundary(ADR-002-026)·
   break-glass·Hard Envelope·gate waive 불가·smallest scope delta(ADR-002-025 §5.11)만(§17.1.5).
   ADR-002-025/026은 미구현 상류 — scalar 참조(not-Phase-1).

전부 `EV-L2/3+Security` — **닫지 않음**. HAG는 liveauth 7-control/13-prereq **재저작 안 함**
(§0.4b·§3.5 — 필요 시 drift-test 패턴 적용).

### 6.6 `operator_config_authz_error_fail_closed` (§17.1; HAG-EV-018 substrate, predicate-only, 최소 EV-L2/3+Security)

`operator_config_authz_error_fail_closed(variant_declaration, current_scope) -> bool`: variant
미선언·잘못 설정·scope 불일치·authorization 오류 ⇒ 거부(§17.1.1 "Absence of a current, exact
declaration is denial"·HAG-INV-015). `None`/UNKNOWN ⇒ 거부. 실 config/authz 평가는 +Security
(HAG-EV-018 L2).

---

## 7. property-test 하네스 타깃

### 7.1 import-closure 검증 테스트 (설계 #4 §7.1·#12-#19 §7.1 상속·allowlist 형식)

`import tos.hag` 후 `sys.modules` closure를 **allowlist로 검증**: `tos.* closure ⊆
{tos.canonical, tos.ordering, tos.hag}`(sbr `__init__.py:47-48` 선례 — subset 검증이라 미래
신규 형제·카운트 오차 자동 배제). 추가로 금지 집합 부재 assert: `shared.config`·`os.environ`
흔적·`numpy`/`pandas`/`yaml`·**19 형제 tos 패키지 전부**(afg·are·authority·brokercap·capsule·
dsl·evidence·iap·ioc·**liveauth**·orthostate·**protective**·rcl·recon·**replacement**·sbr·
**spg**·time·venue — **`tos.liveauth`·`tos.spg`·`tos.iap`·`tos.protective` 명시 포함**, #17
MAJOR-1 교훈) 부재; **`tos.canonical`·`tos.ordering`만 존재 허용**(sibling edge 0 — §0.4c).
required check(`tos-firewall`, `tools/tos_firewall_check.py` layer-① AST + `.importlinter`
layer-② 전이)와 함께 green이어야 §0.3 선언 능동 성립. **주의**: liveauth `rearm_dual_control_
satisfied`·spg `break_glass_confined`·iap `IndependentApprovalDecision`·protective
`protective_classification` **부재**를 assert — 로컬 저작이지 import 아님을 이 테스트가 강제.

**property test 군(§5/§6 술어별)**: (1) collapse 결정론·보수적 병합·∅/1인 거부(§5.1
노른자·hypothesis 그래프 생성)·(2) binding exact·material change ⇒ CRITICAL_CONFLICT(§5.2)·
(3) single-use·stale/replayed 거부·lifecycle arrow(§5.3)·(4) break-glass 방향(§5.4)·(5)
protective proposal-only(§5.5)·(6) dual-control distinct·narrow(§5.6)·(7) economic continuity·
no auto re-arm(§5.7)·(8) replay 재구성·evidence-not-authority(§5.8)·(9) all-false 구성 거부
(§4.3 any-True ⇒ ArtifactIntegrityError)·(10) **truthy-sentinel 회귀**(`bool(AttestationDecision.
DENY)` ⇒ TypeError·§4.7)·(11) **attesting principal ∉ `graph.nodes` ⇒ False**(§5.1 (vii)·
MAJOR-2 미표현-principal fail-open 봉인)·(12) **`graph.unresolved_control is None/True` ⇒
deny**(graph-level 전면-거부·MAJOR-2)·(13) per-edge `resolved is not True` ⇒ 병합(distinct
감소 방향·§4.1).

### 7.2 run manifest 정렬 (설계 #1 §5.1 7항목)

(1) 목적: hag Phase-1(EV-L1) 순수 모델+property test. (2) 명령: `pytest tos/tests/hag/ -v`
(실행: `PYTHONPATH=tos/src .venv/bin/python -m pytest tos/tests/hag/ -v` — pyenv은 mypy
전용). (3) 격리: hermetic(`.env` 비주입·clock 미접근·네트워크 없음 — human authority 판정의
hidden-input 부재). (4) 결정론: hypothesis 시드 고정·`EVL1ProvisionalCanonicalizer` 고정·
StrEnum 고정·`compare_order` 결정론·collapse union-find 정렬 순회. (5) 산출물: property test
결과(EV closure 아님 — 규율 태그). (6) 게이트: `tos-firewall` required green. (7)
비-acceptance: 어떤 HAG-EV도 닫지 않음(§0.2·VER-002-001 §5).

---

## 8. bounds 주입 + Phase-0

**§8.0 hag 모델 구조에 numeric 값 부재**: quorum N·cooling interval·session/approval/
delegation age·HALT latency 전부 enum·boolean·집합/그래프 논리·주입 opaque param. ADR §28
q12(line 746)·§4 non-scope가 수치를 명시 배제 — 전부 Safety/Verification Profile INSTANCE
측정값. 값 부재 ⇒ fail-closed(§4·§5). 하드코딩 0.

**§8.1 Verification-Profile 키 실측(#13 MAJOR-2 규율 — 전수 grep)**: HAG-owned 키(전부 실재·
null/TBD·미승인):

- **`B_human_halt_to_commit`**(line 149, `value_ms: null` — "APPROVE after the independent
   human HALT ingress, local latch, and authoritative commit path are implemented",
   `measurement_source: human_halt_ingress_local_latch_and_safety_commit_log`, `failure_
   response: LATCH_LOCAL_HALT_AND_ESCALATE`, rationale line 153 "ADR-002-015 §15") — **실재**.
   §4.6·§6.2 정합.
- **`B_halt_to_egress`**(line 142, `null` — rationale line 146 "ADR-002-007 §§16-17;
   ADR-002-015 §15", `failure_response: HALT`) — **실재**. §4.6 정합.
- **`MAX_human_approval_age_ms`**(line 703, `null` — "APPROVE per approval type; stale or
   unknown age denies authority increase") — **실재**. §5.3 stale 거부와 정합.
- **`MAX_human_session_age_ms`**(line 704, `null` — "APPROVE per human authority direction;
   unknown age denies the command") — **실재**. §14/§6.2 정합.
- **`MAX_human_delegation_age_ms`**(line 705, `null` — "APPROVE per delegation policy; expiry
   never transfers or revives approval") — **실재**. §6.3 정합.
- **artifact pin**: `human_authority_policy_id/generation/digest`(line 37-39, TBD/null/TBD)·
   `effective_principal_graph_id/generation/digest`(line 40-42) — HAG 아티팩트 test-harness
   pin(§9 governance는 spg/§28 q3).
- **결론(over-claim 봉합·#10 lesson)**: ADR §28 q12·§29 item 14가 요구하는 HAG-owned 5 bound
   (2 HALT + 3 age) + 2 artifact-pin이 **전부 실재**·전부 null/TBD(미승인). ⇒ **candidate 신규
   키 = 0건**(#10/#13/#15/#17/#19 "0 누락" 동형). 결함 아님 — **Phase-0 Bounds-Approver 승인
   항목**. hag는 이 값들을 신뢰하지 않으며(VP status null/TBD·unapproved bound은 approved
   bound 아님, VER-002-001 §6) 전 수치를 fail-closed로 처리(§4·§5).

**§8.2 iap 키와 혼동 주의**: `MAX_proposal_approval_request_age_ms`(line 721)·`MAX_independent_
approval_decision_age_ms`(line 722)·`B_approval_invalid_to_intent/egress`(line 303/310)·
`B_approval_generation_fence`(line 317)·`trading_approval_policy_*`(line 67-69)는 **iap
소유**(ADR-002-023·자동 결정 축) — HAG 키 아님(§0.4e 축 분리). HAG age는 `MAX_human_*`
접두(line 703-705).

---

## 9. 후속 작업 · Phase-0 인간 게이트 이관 항목

### 9.1 후속 구현 작업 (본 계약 위에서)

1. `tos/src/tos/hag/` 5-module 저작(`_base.py` all-false `HumanAuthorityEffect` shim +
   `model_validator` + defence-in-depth·`vocabulary.py`[`AuthorityClass`·`AuthorityDirection`·
   `AttestationDecision`·`ApprovalLifecycleState`·`ConflictRole`·`_NonTruthyStrEnum` truthy
   봉인]·`records.py`[8 digest-bound 아티팩트]·`predicates.py`[core 8군 §5 + predicate-only
   §6]·`state.py`[`EffectivePrincipalNode`/`EffectiveControlEdge`/`ApprovalScope`/
   `RoleAssignment`/`AttestationInputs` 주입 입력]) + `tos/tests/hag/` property test(§7) +
   seam cross-check(§3.4) + import-closure(§7.1 allowlist) + truthy-sentinel 구조 봉인
   회귀(§4.7) + all-false any-True 거부 회귀(§4.3).
2. core 술어 8군(§5) + predicate-only 술어 8군(§6) + 8-아티팩트·all-false `HumanAuthorityEffect`·
   enum 어휘(§2) 구현. **sibling edge 0 유지**(§0.4c) — 어떤 형제 타입도 REUSE·import 안 함
   (형제 결과는 injected scalar/bool/enum-token/verdict/digest). liveauth `rearm_dual_control_
   satisfied`·spg `break_glass_confined`·iap `IndependentApprovalDecision`·protective
   `protective_classification` **재저작 금지·import 금지**(§7.1 부재 assert).
3. 미래 caller 런타임(Human Authority Service·Approval Verifier·HALT ingress)이 hag 산출
   (policy·graph·request·attestation·set·consumption·HALT command)을 소비자(liveauth re-arm·
   final egress·evidence store)로 배선(§3.4; Phase 1 밖·EV-L2/L3). **effective-principal
   collapse → distinct count → liveauth 주입**은 런타임 gate 몫(§3.5 (a)) — hag 순수 모델은
   주입 위 판정만.

### 9.2 Phase-0 인간 게이트로 넘기는 항목 (본 계약이 결정하지 않음)

ADR §28 Open Implementation Questions(15항)·§29 Approval Gate(16조건)에서 Phase-1 밖으로 이연:

1. **identity provider·natural-person proof·phishing-resistant authenticator·device
   attestation·recovery mechanism 선정**(§28 q1·§29 item 2) — 제품·security review(§14).
2. **Effective Principal Graph 구축/보호 시스템**(§28 q2) — 실 그래프 소스·관리 통제 경로
   inventory는 +Security 런타임(§5.1은 순수 collapse 술어만).
3. **Human Authority Policy quorum·mandatory-role matrix per decision**(§28 q3·§29 item 3) —
   quorum N·role matrix는 policy content 주입(§2.4·§8.0); spg governance(§9).
4. **조직 분리 필요 conflict**(§28 q4) — §12 최소 금지쌍 외 추가 조직 분리는 policy(§6.1은
   최소 10쌍 술어만).
5. **approval workflow·canonical attestation/signature format**(§28 q5·§29 item 1) — exact
   context binding·single-use는 §5.2/§5.3 술어; 서명 format은 Phase-0.
6. **ADR-002-012 namespace ordering approval set consumption**(§28 q6·§11 line 333) — ordered
   linearizable namespace는 SCL 런타임(§3.2는 순서 substrate만).
7. **delegation·temporary-role·employment-change·leave·succession policy**(§28 q7) — policy
   (§6.3은 non-transitive/bounded 술어만).
8. **pre-provisioned Human HALT authenticator·failure domain**(§28 q8·§29 item 4) — 실
   authenticator·failure-domain isolation은 +Security(§6.2는 degraded-no-permissive 술어만).
9. **direct restrictive egress latch 인증/bound/replay-protect/reconcile/revoke**(§28 q9·§29
   item 4) — ADR-002-013 final egress·ADR-002-024 deny-first 순서 런타임(§4.6은 monotonic
   술어만).
10. **human-requested containment pre-defined actions·external/manual broker governance**(§28
    q10·§29 item 5) — protective/replacement/ADR-002-013(§5.5는 proposal-only 술어만)·§21
    external broker는 +Broker.
11. **compromise scope·previously-consumed approval 즉시 suspend vs 협의 containment**(§28
    q11·§29 item 7) — +Security 런타임(§6.4는 fail-closed 술어만).
12. **numeric bounds 승인**(§28 q12·§29 item 14) — `B_human_halt_to_commit`·`B_halt_to_egress`·
    `MAX_human_approval_age_ms`·`MAX_human_session_age_ms`·`MAX_human_delegation_age_ms`(§8.1
    **전부 실재·null/TBD**)의 Bounds-Approver 승인 + fault-injection 측정. **candidate 신규 키
    0건.**
13. **ADR-002-016 ERI evidence custody/replay(human/break-glass 기록)**(§29 item 9) — replay
    ENGINE(§5.8 레코드 substrate만 Phase-1; evidence가 HAG digest carry `replay.py:114-115`).
14. **ADR-002-017 SBR Recovery Generation binding before consumption**(§28 q14·§29 item 10) —
    human ↛ force READY; sbr는 이미 배포 #17 — recovery digest 주입 소비(§3.4).
15. **ADR-002-018 CII·ADR-002-019 VTG·ADR-002-020 IOC exact binding before consumption**(§29
    item 11-13) — capsule/venue/ioc digest 주입 소비(§3.4; 전부 배포됨 — hag import 아님).
16. **ADR-002-024 CUR deny-first/monotonic/non-revival/claim-fence 순서(HALT ingress·egress
    latch)**(§29 preamble) — Currentness Vector 런타임 +Security(§4.6은 monotonic-restrictive
    술어만).
17. **ADR-002-025 RLP Progressive Promotion step·ADR-002-026 WDR Non-Waivable Boundary**(§17.1.5)
    — 미구현 상류 governance(survey line 482-483 HAG 의존) — scalar 참조(not-Phase-1).
18. **ARCHITECTURE-GATE-STATUS 명시 acceptance 결정**(§29 item 16) — 실행된 HAG-EV-001..012 +
    variant evidence-debt(013-018·§17.1.6) + cross-system evidence(SA/REARM/TIME/FD/RCLP/
    EGRESS/SPG/BC, §29 item 8) + 독립 리뷰(Independent-Safety-Reviewer 하드 배제).

---

## 10. 개정 로그 + 비준 체크리스트

### 10.1 개정 로그

- **v1.0 (2026-07-26) — 초안, 독립 비평 리뷰 대기.** ADR-002-015(HAG)를 Phase 1(EV-L1) 설계
  계약으로 실현. 문서 번호 **#20**(#19 VTG 이후). 패키지 **`tos.hag`**(runner-up
  `tos.humanauth`[descriptive]; 근거: register prefix HAG 1:1·terse 3-letter 관행·seam 토큰
  선점[evidence `replay.py:114-115`·`envelope.py:56/93`·VP line 37-42]·`tos.authority` 충돌
  회피, §0.4a). 8 digest-bound 아티팩트(`HumanAuthorityPolicy`·`EffectivePrincipalGraph`·
  `HumanApprovalRequest`·`HumanApprovalAttestation`·`HumanApprovalSet`·`ApprovalSetConsumption
  Record`·`HumanHaltCommand`·`HumanDelegationRecord`, 전부 `IndependentIdArtifact`)+enum 어휘
  (`AuthorityClass`/`AuthorityDirection`/`AttestationDecision`[non-truthy]/`ApprovalLifecycle
  State`[non-truthy]/`ConflictRole`)+all-false `HumanAuthorityEffect`(§2). **EV 분류 재실측
  (사전 지도 "9" 정정)**: **core 8행(HAG-EV-001/002/004/006/007/010/011/012, L1-floor) /
  predicate-only 10행(003/005/008/009/013-018, 최소 ≥ L2·+Security 15/18) / not-Phase-1 —
  닫는 HAG-EV = 0건**(§1). seam: **liveauth/spg/iap/protective/replacement/authority/sbr/
  capsule/venue/ioc/brokercap/time/evidence scalar·bool·enum-token·verdict·digest producer/
  consumer + sibling edge 0건(대안 liveauth `ReArmPathKind` REUSE 1 edge §0.4c), PROMOTE 0**
  (코드 실측: liveauth `records.py:216`·`state.py:168/172-175`·`predicates.py:492/523-527`,
  spg `predicates.py:746/755-758`·`vocabulary.py:236/258`, iap `__init__.py:143-166`·
  `vocabulary.py:50`, protective `predicates.py:246`, authority `predicates.py:401/425`,
  evidence `replay.py:114-115`·`envelope.py:56/93`, capsule `capsule.py:161/230`, §3.4).
  **핵심 아키텍처 판정**: (i) **HAG = 인간 권위 일반 모델 소유; liveauth = §17 re-arm 인스턴스
  소비**(§0.4b·§3.5 최대 경계) — HAG는 effective-principal graph/collapse·approval request/
  attestation/set·SoD·break-glass·HALT command·delegation·lifecycle 일반 모델; liveauth는
  re-arm dual-control 소비(opaque string distinctness + count)를 이미 실현·HAG가 collapse로
  distinct count *생산*·liveauth가 *소비*. (ii) **HAG collapse ≠ liveauth string-`!=`**(§3.5
  핵심 판정 (a)) — `alice-svc-01` ≠ `alice-svc-02`가 liveauth엔 distinct이나 HAG collapse엔
  1 principal; liveauth `state.py:172-175`이 "human authentication is ADR-002-015 runtime"
  명시 이연. (iii) **HAG break-glass ≠ spg break-glass**(§3.5 핵심 판정 (b)) — spg=config
  action-token(2), HAG=human authority-class direction(8)+spg가 `predicates.py:755-758`에서
  HAG로 명시 이연한 effective-principal independence; spg 코드가 직접 owner 지목. (iv) **HAG
  human approval ≠ iap automated approval**(§3.5 핵심 판정 (c)) — ADR §4 line 98 "automated
  APPROVE cannot satisfy a human quorum"; "Human" prefix 명명 구분. (v) **effective-principal
  collapse = 노른자**(§4.1·§5.1) — 동치류 순수 함수·보수적 병합(unknown edge ⇒ 병합 ⇒
  distinct 감소 ⇒ fail-closed 양방향[quorum·SoD]). 중심 fail-closed 술어: `effective_principal_
  collapse`+`quorum_independence_satisfied`(§5.1)·`approval_binding_exact`(§5.2)·`approval_set_
  single_use`(§5.3)·`break_glass_direction_restrictive`(§5.4)·`human_protective_request_
  proposal_only`(§5.5)·`dual_control_effective_distinct`(§5.6)·`no_automatic_rearm`(§5.7).
  predicate-only 8군(§6). **∅ 양방향**(∅ approval set·∅ roster·∅ scope de-authorization —
  거부+허용 둘 다, §4.7)·**집합 양방향**(distinct persons vs 한 사람 다중 신원, §4.7). 앵커:
  HAG-INV-001..019·HAG-AC-001..012·HAG-EV-001..018(§0.4f). **bounds 실측**: HAG-owned 5
  bound(2 HALT line 142/149 + 3 age line 703-705) + 2 artifact-pin(line 37-42) 전부 실재·
  null/TBD(candidate 신규 키 0건, §8.1). 선제 봉합: fail-open(all-false §4.3·vacuous-∅ §4.1
  authority `lease_scope_exclusive` M1 상속)·∅ 양방향(§4.7)·**truthy-sentinel 구조 봉인(#13/#14
  M1 선제 — `AttestationDecision`/`ApprovalLifecycleState` `__bool__ ⇒ TypeError`)**·집합
  양방향(§4.7)·under-realization(전용 술어는 실재 형제 seam에만·liveauth re-arm/spg token/iap
  자동결정/protective classification 정직 이연)·**phantom 타입 0**(전 인용 grep 실측·필드-클래스
  소유까지 #15 M1 교훈)·verbatim+line·**차원 비붕괴**(§2.2·§3.5 — HAG collapse≠liveauth
  distinctness·HAG break-glass≠spg token·HAG approval≠iap decision·HAG SoD≠authority
  lease-exclusivity)·**과대 주장 금지**(variant 계열 013-017의 liveauth 중첩 정직 표기·닫는 EV
  0·EV-L1-complete 금지). **어떤 EV도 닫지 않음·acceptance 미선언·비준 기록 = "v1.0 초안 —
  독립 비평 리뷰 대기".**

- **v1.1 (2026-07-26) — 독립 비평 리뷰 REVISE(CRITICAL 0·MAJOR 2·MINOR 2; ~40 앵커 전수 검증
  통과·phantom 0·경계 3건 전부 "형제 코드가 문서 편"·EV 분류 정확) 반영, forward-only(오케스트
  레이터 직접 적용).** **MAJOR-1**(capsule `approval_request_id` 오귀속 정정): `capsule.py:161`
  `approval_request_id`는 iap 자동 파이프라인 체인(Bindings·iap `ProposalApprovalRequest`
  `records.py:158` 소유)이지 HAG seam이 아님 — §0.4a point 2·§2.4에서 HAG 명명 근거/하류 참조에서
  제거, `HumanApprovalRequest`를 register-prefix `HAG`+ADR §5.4/§5.5+evidence envelope 앵커
  (`approval_set_id`·`human_authority_policy_digest`·`effective_principal_graph_digest`)로 재정박,
  HAG↔capsule은 "request가 capsule identity/digest bind"(ADR §10:306) 방향만. 자가당착(§4:98
  인간≠자동 축 핵심 판정과 충돌) 해소. **MAJOR-2**(collapse 노른자 미표현-principal fail-open
  봉인): §5.1/§5.6/§6.1에 조건 (vii) 추가 — **모든 증언 principal ∈ `graph.nodes` AND
  `unresolved_control is False`, 미표현/미해소 ⇒ 즉시 거부**(ADR §8:271; 순진한 연결성분이 미표현
  principal을 고립 singleton으로 세어 quorum 통과[ADR §2:40 1순위 공격] 봉인). §2.4
  `unresolved_control` 의미 **택일=graph-level 전면-거부**(graph-level 플래그는 어느 edge 누락인지
  식별 불가 ⇒ per-edge 병합 불가 ⇒ True/None은 판정 자체 거부)·per-edge `resolved` 좌표는
  fine-grained 병합용의 **2층** 확정. §7 property-test 3케이스 추가(미표현 principal·unresolved
  deny·per-edge 병합). **MINOR-1**(섹션-태그 5건, 라인 정확): §4.2 §10→§1(line 30 material
  change)·§4.5/§5.7 §12→HAG-INV-012(line 202)·§14→HAG-INV-014(line 210)·§2.2(2) §18→§10(line
  314)·§2.4/§3.5/§1 §9 line 291→292. **MINOR-2**: register(013-018 등재)가 ADR §17.1.6 "not
  registered in this wave" supersede 명시(§0.4f/§1). 아키텍처(패키지 `tos.hag`·EV core 8/
  predicate-only 10·경계 3건[liveauth·spg·iap]·effective-principal collapse 노른자·truthy 봉인·
  edge 0) 불변. **어떤 EV도 닫지 않음·acceptance 미선언.**

### 10.2 비준 체크리스트 (운영자 · 독립 리뷰어 확인 사항)

1. **패키지 명명** `tos.hag`(register-prefix·terse·seam 정합) 승인 — **또는 `tos.humanauth`**
   (descriptive). **[운영자 판단 지점]**: `hag`가 (i) register prefix HAG와 1:1이고 (ii)
   evidence/VP seam 토큰(`human_authority_policy`·`effective_principal_graph`·`approval_set`)과
   정합하며 (iii) `tos.authority`(002-003 점유) 충돌을 피하는지. naming은 load-bearing 아님
   (§7.1 allowlist가 미래 형제 자동 배제).
2. **HAG = 인간 권위 일반 모델 ≠ liveauth re-arm 인스턴스(§3.5 핵심 판정 (a) — 최대 아키텍처
   공격 지점)**: HAG가 effective-principal collapse로 distinct count *생산*, liveauth가 그
   count *소비*(re-arm)라는 계층 관계가 정확한지·HAG↛liveauth import 0·재저작 0인지. **[리뷰어
   공격]**: "HAG와 liveauth 둘 다 dual-control distinctness = 중복" — 반론: liveauth
   `state.py:172-175`이 "human authentication is ADR-002-015 runtime"으로 명시 이연·liveauth
   string-`!=`(`predicates.py:525`)는 same-person-multi-identity 못 잡음·§8 line 267 "collapse
   before counting". 리뷰어: liveauth `records.py:216` `approver_principals: tuple[str,...]`가
   opaque string임을 확인.
3. **HAG break-glass ≠ spg break-glass(§3.5 핵심 판정 (b))**: spg=config action-token(2)·
   HAG=human authority-class direction(8)+effective-principal independence 경계가 정확한지.
   **[리뷰어 공격]**: "HAG-EV-006가 SPG-EV-009 `break_glass_confined` 재저작" — 반론: spg
   `predicates.py:755-758`이 effective-principal independence를 "ADR-002-015 HAG-EV +Security
   — not-Phase-1"로 **직접 이연**·다른 ADR clause(002-014 §8 vs 002-015 §16)·다른 vocabulary.
   리뷰어: spg `vocabulary.py:258` `{HALT, RESTRICTIVE_OVERRIDE}` 2-token vs HAG §7 8-class
   대조.
4. **HAG human approval ≠ iap automated approval(§3.5 핵심 판정 (c))**: ADR §4 line 98
   "automated APPROVE cannot satisfy a human quorum" 축 분리가 정확한지·"Human" prefix 명명이
   iap `ProposalApprovalRequest`/`IndependentApprovalDecision`와 혼동 방지하는지. **[리뷰어
   공격]**: "approval-set·single-use가 iap 중복" — 반론: 인간 quorum(effective-principal
   collapse 중심) vs 자동 결정(principal 개념 없음)·ADR §4 명시 분리. **MAJOR-1 정정(v1.1)**:
   capsule `approval_request_id`(`capsule.py:161`)는 iap 자동 축(Bindings) 소유이지 HAG seam
   아님 — §0.4a/§2.4에서 HAG 명명 근거 배제·`HumanApprovalRequest`는 register-prefix+ADR §5.4로
   정박·HAG↔capsule은 request→capsule digest bind(§10:306) 방향만. 리뷰어: iap `records.py:158`
   `ProposalApprovalRequest`가 Bindings 체인 소유 확인.
5. **effective-principal collapse 노른자(§4.1·§5.1) + 미표현-principal 봉인(§5.1 (vii)·MAJOR-2)**:
   증언 principal ∈ `graph.nodes`·`unresolved_control is False` 게이트가 collapse 이전 필수인지
   (미표현 principal 고립 singleton fail-open·ADR §2:40 공격 봉인·ADR §8:271)·`unresolved_control`
   True/None ⇒ graph 완전성 미증명 ⇒ 전면-거부 택일이 per-edge `resolved`(fine)와 2층으로 정당한지.
   동치류 순수 함수·**unknown edge ⇒
   보수적 병합 ⇒ distinct 감소 ⇒ fail-closed**(quorum·SoD 양방향)가 정확한지·∅/1인 거부가
   vacuous-True(`0 >= N`?) 아닌지. **[리뷰어 공격]**: "unknown control ⇒ 병합"이 fail-open
   아닌가 — 반론: 병합은 distinct 감소 ⇒ quorum 더 어려움(fail-closed)·§8 line 271 "denial for
   authority increase". 리뷰어: authority `lease_scope_exclusive` v1.0 `0 <= 1` vacuous-∅
   fail-open을 non-empty로 봉한 `predicates.py:425` M1 선례가 HAG `count >= N`에 상속됐는지
   확인.
6. **truthy-sentinel 구조 봉인(§4.7·§2.2)**: `AttestationDecision`{APPROVE/DENY/ABSTAIN}·
   `ApprovalLifecycleState` `__bool__ ⇒ TypeError`가 §7 회귀로 강제되는지 — 특히 **DENY/ABSTAIN
   truthy fail-open**(거부를 승인으로 오독) 방지. 리뷰어: iap `_NonTruthyStrEnum`
   `vocabulary.py:50-77` 동형 확인.
7. **all-false `HumanAuthorityEffect`(§4.3·HAG-INV-004)**: 6 flag 전부 False·`model_validator`
   any-True ⇒ `ArtifactIntegrityError`·defence-in-depth(`model_construct` 대비)가 liveauth
   `LiveAuthorizationEffect`(`_base.py:75-92`)·iap `ApprovalAuthorityEffect` 동형인지·approval
   ↛ authority(§5.6). **[리뷰어 공격]**: approval attestation/set이 capacity/config/live-auth로
   authority 생성하는 경로.
8. **variant 계열 013-017 정직 표기(§6.5·과대 주장 금지)**: liveauth가 §17.1 re-arm 소비
   인스턴스(7-control/13-prereq/`ReArmPathKind`)를 이미 실현했고 HAG 잔여는 general-model
   정의(§5.10-5.12)·effective-principal collapse의 external-reviewer 판정(§17.1.4)뿐이라는 정직
   표기가 정확한지·HAG가 liveauth 7-control/13-prereq를 재저작 안 하는지(§0.4b·drift-test 패턴
   준비). 리뷰어: liveauth `_SAFE053_CONTROLS` `predicates.py:104`·`_VARIANT_ENVIRONMENTAL_
   PREREQUISITES` `predicates.py:127` + drift test `122-126` 소유 확인.
9. **sibling edge 0 vs liveauth `ReArmPathKind` REUSE(§0.4c)**: edge 0(injected verdict/
   digest, iap/sbr/venue 선례)이 정확한지 vs liveauth `ReArmPathKind`(1 edge). **[운영자 판단
   지점]**: HAG approval-set이 path-agnostic이라 edge 0이 일반 모델 독립성을 지키는지 vs
   `ReArmPathKind` REUSE가 인스턴스 결합을 초래하는지.
10. **∅ 양방향·집합 양방향(§4.7)**: ∅ approval set(거부)·∅ scope(정당 de-authorization)·한
    사람 다중 신원 collapse(count=1)·서로 다른 자연인(count=|persons|) 4방향이 전부 명시·회귀
    되는지. 리뷰어: liveauth `partial_rearm_scope_narrows` Gap-2(`predicates.py:663-666`) ∅
    narrowing 선례 대조.
11. **HAG-EV 재실측(§1)**: core 8행 {001·002·004·006·007·010·011·012}·predicate-only 10행이
    register(csv line 173-184·365-370)와 정확 일치하는지(사전 지도 "9" 정정)·닫는 HAG-EV 0·
    HAG-AC 12행(§26, EV-001..012에만 1:1)·HAG-INV 19종·HAG-EV 18행. 리뷰어: register 18행
    tier 직접 재실측.
12. **bounds 실측(§8.1)**: HAG-owned 5 bound + 2 pin 전부 실재·null/TBD·candidate 신규 키
    0건이 정확한지·iap 키(`MAX_proposal_approval_request_age_ms` 등)와 혼동 없는지(§8.2). 리뷰어:
    VP line 142/149/703-705/37-42 직접 grep.
13. **firewall allowlist(§7.1)**: `closure ⊆ {canonical, ordering, hag}`·liveauth/spg/iap/
    protective **부재 assert**(재저작이지 import 아님)·미래 형제 자동 배제가 정확한지.

---

> **비준 기록**: 2026-07-26 운영자 위임 자동 비준(v1.1) — 독립 비평 REVISE[MAJOR 2·MINOR 2]
> 반영·§10.1 v1.1). 본 문서는 tos-spec을 수정하지 않으며 어떤
> HAG-EV/acceptance도 선언하지 않는다(§0.2). 구현은 §9.1 순서로 별도 진행하며 적대적 코드
> 리뷰·게이트를 거친다.
