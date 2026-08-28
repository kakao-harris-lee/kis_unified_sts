# 설계 문서 #19 — Venue·Session·Tradability·Broker Constraint Gate 계약 (2026-07-26, v1.1)

> **문서 번호 규약(2026-07-26)**: 병렬 세션이 ADR-002-022(Action-Flow Budgeting — AFG)를 **설계 문서 #16**,
> ADR-002-017(Safe Startup·Recovery Barrier — SBR)을 **설계 문서 #17**로 비준·INDEX 등록했다. 본 ADR-002-019
> (Venue·Session·Tradability·Broker Constraint Gate — 이하 **VTG**) 문서는 **설계 문서 #19**이다(#18 =
> 세션 B의 Protective Replacement[ADR-002-011] 선점 — 병렬 세션 번호 규약). **#16 AFG·#17
> SBR 모두 비준본이며 `tos/src/tos/afg/`·`tos/src/tos/sbr/` 구현도 착지**했으나, sibling-edge-0 규율에 따라
> VTG는 이들을 import가 아닌 **injection slot으로만** 참조하고 ADR-002-019 원문을 규범 앵커로 삼는다.

> **문서 성격 (규범성 선언)**: 본 문서는 ADR-002-019(VTG)를 Phase 1(EV-L1) 설계 계약으로 실현하는 **비규범 설계
> 문서**다. GOV-001의 세 거버넌스 행위(비준 / ADR acceptance / live authorization) 중 **어느 것도 수행하지
> 않는다**. tos-spec의 ADR·RFC·VER·register·profile 어떤 상태도 변경하지 않고, 어떤 VTG-EV 항목도
> `NOT_IMPLEMENTED`에서 이동시키지 않는다. **비준 기록 = "2026-07-26 운영자 위임 자동 비준(v1.1)"**(§10.1 —
> 독립 비평 리뷰 REVISE[CRITICAL 0·MAJOR 0·MINOR 4·NIT — 전부 인용-충실도, 아키텍처 무결]의 minimal edit set
> 전량 반영 후 위임 집행; 판단 지점: `tos.venue` 명명·edge 0[time.SessionContext REUSE 기각]·SessionPhase
> 주입 token+admitting-set·ActionClass closed StrEnum 채택). 앵커는
> ADR-002-019 자체 시리즈 **VTG-INV-001..014(§6)·VTG-AC-001..012(§27)·VTG-EV-001..012(register)** 이며 **새
> INV/AC/EV 시리즈를 창작하지 않는다**(§0.4f — #12–#17 동형). 인용은 verbatim + ADR line 병기, 코드 seam은
> file:line 실측(phantom 금지 — #15 MAJOR-1 교훈: 필드가 어느 클래스 소유인지까지 확인). **broker-agnostic** —
> KIS 등 특정 broker 고유사항은 본 문서에 넣지 않고 capability class로만 표현한다(§13이 broker constraint를
> 다루므로 특히 임계; tos-spec broker-agnostic 규율).

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. **패키지 위치·명명 `tos/src/tos/venue/`** (선점 사실 반영 — 대안 `tos.vtg` 비교 §0.4a). 코드 실측: 형제
   3곳이 이미 `tos.venue`(sbr/iap import-closure)·`venue_*`(ioc/iap 필드)를 선점했다.
2. **EV 분류 — core 4행 / predicate-only 8행 / 닫는 VTG-EV = 0건**(§1). core 4 = {VTG-EV-001·003·004·006}
   (전부 `EV-L1/3` 슬라이스 보유), predicate-only 8 = {002·005·007·008·009·010·011·012}(최소 ≥ L2). +Security
   6행(003·006·007·010·011·012)·+Broker 6행(001·002·004·005·008·009). **"EV-L1-complete 주장 금지"** 규율 태그(§1).
3. **중심 데이터 모델 9종**(§2): `VenueConstraintPolicy`·`VenueConstraintSnapshot`·`OrderAdmissibilityDecision`
   (셋 다 `IndependentIdArtifact` — capsule Ref 실측)·`ConstraintGeneration`(=`tos.ordering` REUSE)·
   `OrderAdmissibilityResult`(StrEnum·truthy 봉인 — `dsl.AdmissibilityResult`와 **명명 충돌 회피** §0.4d)·
   `TradabilityState`(per-action StrEnum·truthy 봉인)·`ActionClass`(**closed StrEnum** — ADR §11 line 283–289
   taxonomy가 고정 열거["At minimum … SHALL distinguish"]이므로 SessionPhase와 달리 policy-open이 아님; v1.1 M4
   판정)·`SessionPhase`(**주입 opaque token** — hardcoded enum 금지
   §2.2)·`ConstraintDependencyClosure`+`MaterialConstraintChange`(reachability 폐포)·`VenueGateAuthorityEffect`
   (all-false — ioc `AllFalseConstructionAuthority` 동형).
4. **중심 fail-closed 술어**(§4·§5·§6): core L1 슬라이스 4군(§5) + predicate-only 8군(§6). 전부 순수 함수 —
   permissive 기본값 부재·vacuous 부재·truthy-sentinel 구조 봉인. **중심 술어 = `session_phase_admits`**(미열거
   세션 상태 ⇒ 거래 불가; VTG-EV-001 노른자, §5.1).
5. **소유권/seam 분할표**(§3.5): 인접 형제와의 경계를 **코드 실측 slot**으로 고정. 특히 (i) **ioc 경계** — ioc §11/§12
   (intent-conformance)와 VTG §11/§12(venue-admissibility)는 **같은 필드의 다른 판정**(§3.5 분할표); ioc는 VTG
   `OrderAdmissibilityDecision` digest를 `venue_admissibility_decision_digest`(`ioc/records.py:414`)로 소비, VTG는
   ioc candidate `CanonicalBrokerCommand` digest를 소비(양방향 digest·edge 0). (ii) **brokercap 경계** — brokercap은
   evidence-backed **ceiling**(ADR-002-004), VTG는 그 ceiling 내부의 **current admissibility**; VTG는 promote 불가
   (VTG-INV-006). (iii) **spg 경계** — spg가 `VENUE_CONSTRAINT_POLICY` **activation** 소유(`spg/vocabulary.py:205`),
   VTG는 policy **content** 소유. (iv) **capsule 경계** — capsule이 3-Ref 소유(`capsule/capsule.py:130-150`), VTG가
   full 아티팩트 소유. (v) **iap 경계** — iap가 `venue_snapshot_digest`/`venue_admissibility_decision_digest`
   (`iap/records.py:256-257`) 소비, VTG 상류; admissibility ≠ approval. (vi) **time 경계** — time.SessionContext는
   calendar-expectation, VTG SessionPhase는 authoritative-current(§0.4c REUSE 기각).
6. **truthy 구조 봉인 선제**(§4.7): 결정 enum `__bool__ ⇒ TypeError`(#14 M1 선제)·`is X` 소비 계약·∅ 양방향·집합
   양방향·금지 동사 canary·all-false authority. **`OrderAdmissibilityResult`는 4-값**이라 ioc 3-값보다 봉인이 더
   임계(§0.4d — `RESTRICTED_PROTECTIVE_ONLY`가 truthy fail-open 시 protective-only를 full-permission으로 오독).
7. **firewall 준수**(§0.3): sibling edge **0**(대안 time.SessionContext REUSE 1 edge 비교 §0.4c) + §7.1
   **allowlist** import-closure 검증(`tos.* closure ⊆ {tos.canonical, tos.ordering, tos.venue}` — sbr 선례
   `sbr/__init__.py:47-48`) + §7.2 run manifest.
8. **bounds 주입 + Phase-0 이관 목록**(§8·§9.2): VTG-owned profile 키 **신규 0건**(3 B_venue_*·2 MAX_·3 policy-pin
   전부 실재·null/TBD; §8.1). tick/lot 등 **숫자 하드코딩 0**(전부 주입).

### 0.2 하지 않는 것 (경계·NO 목록)

- **어떤 VTG-EV도 닫지 않는다**(core 4조차 `/3`·+Broker/+Security 통합·독립 리뷰 잔여; predicate-only 8은 최소 ≥
  L2). Owner/Reviewer는 register상 TBD. authoring ≠ acceptance(VER-002-001 §5 "Registration is not execution";
  ADR §27 line 651 "Written cases are not completed evidence").
- **capacity 변이·commit·release 미결정** — RCL/ARE only(ADR-002-002/012; VTG-INV-011 line 189·§7 line 216).
  VTG는 admissibility fact만 생산하고 capacity를 소비/생산하지 않는다.
- **approval 미결정** — IAP/ADR-002-023 only(§7 line 215·§30 item 12 line 707). admissibility는 approval의 **한
  입력**이지 approval이 아니다(§1 line 23 "An Order Admissibility Decision is a safety fact, not permission").
- **intent-order conformance·candidate command 구성 미결정** — IOC/ADR-002-020 only(§4 non-scope line 95·§14 line
  331). VTG는 ioc candidate `CanonicalBrokerCommand`를 **소비**해 admissibility를 평가하되 command를 구성하지 않는다.
- **broker capability semantics·Final Quantity Proof 미결정** — ADR-002-004 only(§4 non-scope line 95·§13 line
  323). VTG는 Broker Capability Profile을 **ceiling scalar로 소비**하되 promote 불가(VTG-INV-006 line 169).
- **Critical Input provenance·Decision Context 구성 미결정** — capsule/ADR-002-018 only(§4 non-scope line 96·§9
  line 251). VTG는 CII provenance를 snapshot에 **binding**하되 CII를 구성하지 않는다.
- **trustworthy-time 구현 미결정** — time/ADR-002-008 only(§4 non-scope line 97·§10 line 271). VTG는 time evidence를
  **소비**하되 clock을 구현하지 않는다.
- **corporate-action·non-trade transition 미결정** — ADR-002-010 only(§4 non-scope line 98·§11 line 293).
- **protective replacement workflow 미결정** — ADR-002-011 only(§4 non-scope line 99·§19 line 433).
- **human approval·config activation·Live Authorization·re-arm 미결정** — ADR-002-015/014/007/017 only(§4 non-scope
  line 101). VTG는 이들의 입력이지 permission이 아니다(§1 line 21).
- **active currentness 메커니즘 미결정** — ADR-002-024 only(§17 line 388·ADR §1 line 35). VTG §17은 순서·능동
  확립 요구 술어만; 실 Currentness Vector는 런타임 +Security.
- **concrete venue calendar·feed·broker·margin·borrow·rule-engine 제품 미결정**(§4 non-scope line 102). 전부 주입/런타임.
- **numeric freshness·detection·invalidation·propagation bound 미승인**(§4 non-scope line 103 "require approved
  policy and Verification Profile values"). 전부 Phase-0 Bounds-Approver(§8·§9.2).
- **dsl 정적-DSL admissibility 재저작 금지** — `dsl.AdmissibilityResult`/`dsl.AdmissibilityVerdict`
  (`dsl/evidence.py:58`·`dsl/admissibility.py`)는 **ADR-DEV-001 정적 Strategy-DSL** 도메인이지 ADR-002-019 venue
  도메인이 **아니다**(§0.4d — 명명 충돌 회피·차원 비붕괴).

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

`tos.venue` 모델은 다음만 import한다:

- **서드파티**: `pydantic`(frozen 모델)·`pytest`/`hypothesis`(테스트만). **`numpy`/`pandas`/`pyyaml` 미import** —
  admissibility 판정은 StrEnum·boolean·집합/그래프 논리이고 모든 bound·age·tick/lot·band·registry 값은 주입
  파라미터이며 YAML 파싱은 하네스(설계 #3) 소관(closure 최소화 — #12–#17 §0.3 동형).
- **tos 자기 자신**: `tos.canonical`(`FrozenModel` `_base.py:73`·`IndependentIdArtifact` `_base.py:328`[3 core
  아티팩트]·`DigestBoundArtifact` `_base.py:98`·`classify_record_pair` `record_pair.py:52`+`RecordPairKind`
  `record_pair.py:31`[§14 substitution·§18 conflict 탐지]·`ArtifactStatus` `_base.py:58`·
  `EVL1ProvisionalCanonicalizer` `canonicalization.py:173`)·`tos.ordering`(`Ordering`·`OrderingEvent`·
  `compare_order` `__init__.py:19` — **Constraint Generation monotonic 순서**; 실측 `ordering/_ordering.py:38`
  `from tos.canonical import FrozenModel`만 의존이라 core)·`tos.venue.*`.
- **미import(직접·전이 모두) — 17 형제 tos 패키지(전부 실재)**: `tos.afg`·`tos.are`·`tos.authority`·
  `tos.brokercap`·`tos.capsule`·`tos.dsl`·`tos.evidence`·`tos.iap`·`tos.ioc`·`tos.liveauth`·`tos.orthostate`·
  `tos.protective`·`tos.rcl`·`tos.recon`·`tos.sbr`·`tos.spg`·`tos.time`. **`tos.afg`·`tos.sbr`는 최근 착지한
  최인접 형제**로 명시 포함(#17 MAJOR-1 교훈 — afg 누락이 sbr→afg edge의 유일 가드 구멍이었음). **전부
  produced/consumed scalar·bool·enum-token·verdict·digest로만 참조**(§3.4/§3.5). **sibling edge 0 권장**(대안
  time.SessionContext typed-reuse 1 edge — §0.4c).
- **형제 카운트 실측(honest)**: `ls tos/src/tos/` → 19 패키지(afg·are·authority·brokercap·**canonical**·capsule·
  dsl·evidence·iap·ioc·liveauth·**ordering**·orthostate·protective·rcl·recon·sbr·spg·time). `tos.venue`는 신규
  생성(20번째, 현재 부재). ⇒ **형제(배제) = 19 − canonical − ordering = 17**(task 지시의 "18"과 1 차이 — 근거:
  ls 실측; venue 자신은 self로 목록 제외). **정확 카운트는 non-load-bearing**: §7.1이 **allowlist**
  (`closure ⊆ {canonical, ordering, venue}`)이므로 카운트 오차·미래 신규 형제 모두 자동 배제된다(sbr
  `__init__.py:47-48` "any future sibling are all excluded by the §7.1 allowlist closure test" 선례).
- **`shared.config` 절대 금지**(설계 #1 §6.1, `.importlinter`): `shared.config.__init__`이 `shared.config.secrets`
  (→ `os.environ`)를 무조건 전이 import한다. `tos.venue`는 어떤 `shared.*`도 필요로 하지 않는 순수 커널이다.
- **금지(직접·전이)**: `shared.execution`·`shared.kis`·`shared.streaming`·`shared.llm`·`shared.storage`·
  `shared.backtest`·`shared.config.secrets`·`services.*`·`cli.*`(`.importlinter`
  `[importlinter:contract:tos-operational-firewall]` type=forbidden·source_modules=`tos` 실측 — forbidden set).
- **firewall 구조 확인(실측·#17 상속)**: `.importlinter`는 `type=forbidden·source_modules=tos` 단일 계약이며
  `layered`가 아니다 — intra-tos sibling→sibling edge는 구조적으로 금지되지 않고 설계 #1 §3.2의 "자기 자신
  `tos.*`" 허용 조항이 이를 커버한다. **신규 패키지 `tos.venue`는 firewall 도구 무수정 자동 포섭**된다(forbidden
  계약이 source=tos 전체를 덮으므로). 본 문서는 sibling edge 0을 설계 규율로 삼고(§0.4c), §7.1 allowlist가 이를
  능동 강제한다.

### 0.4 REUSE / import / 경계 결정 요지 (핵심 아키텍처)

**(a) 패키지 명명 = `tos.venue` (선점 사실 반영·`tos.vtg` 대안 비교).** 이 문서의 **최대 명명 판단 지점**이다.
두 대안:

- **선택(권장) `tos.venue`** — 근거 3중:
  1. **코드 선점(ratified 아티팩트 3곳)**: (i) ioc `OrderConformanceProof.venue_admissibility_decision_digest`
     (`ioc/records.py:414`·`_COVERED_FIELDS` `records.py:391`), (ii) iap `ProposalApprovalRequest.venue_snapshot_digest`·
     `venue_admissibility_decision_digest`(`iap/records.py:256-257`), (iii) sbr·iap import-closure가 이미
     `tos.venue`를 형제로 열거(`iap/__init__.py:49` "``tos.venue``"; sbr는 allowlist(⊆{canonical,ordering,sbr})라
     명시 열거 없이 자동 배제 — v1.1 M2 정정). ⇒ 도메인 토큰 `venue_*`가 이미
     **머지된 코드에 고정**돼 있고, 패키지명 `tos.venue`가 이 seam 필드 prefix와 정합. `tos.vtg`는 `venue_*`
     필드가 `tos.vtg` 아티팩트를 가리키는 **영구 명명 drift**를 남긴다.
  2. **descriptive-name 관행(실측)**: register prefix ≠ 패키지명이 **이미 다수**다 — orthostate=`STATE-EV`·
     liveauth=`REARM-EV`·authority=`SA-EV`·brokercap=`BC-EV`·capsule=`CII-EV`·rcl=`RC-EV`·protective=`PR-EV`·
     evidence=`ERI-EV`(register 실측). ⇒ "패키지 = lowercase(register prefix)"는 **관행이 아니다**; 도메인 head-noun
     기반 descriptive 명명(`tos.venue`)이 절반 이상의 선례와 정합. VTG의 head-noun은 register domain "**Venue** and
     Tradability Gate"·핵심 아티팩트 "**Venue** Constraint Policy/Snapshot"의 "venue".
  3. **capsule Ref 선점(아티팩트명 확정)**: `capsule/capsule.py:130-150`이 `VenueConstraintPolicyRef`·
     `VenueConstraintSnapshotRef`·`OrderAdmissibilityDecisionRef`를 이미 정의 ⇒ full 아티팩트명은 `Venue*`이며
     `tos.venue`가 자연스러운 집.
- **runner-up `tos.vtg`(defensible·차선)** — register series prefix `VTG`(VTG-EV/INV/AC) 1:1·terse 3-letter
  (rcl/spg/dsl/are/ioc/iap/sbr/afg 정합). 기각 근거: (i) `venue_*` seam 토큰과 drift, (ii) capsule `Venue*Ref`와 약한
  불일치, (iii) descriptive 관행상 필수 아님. **에라타 판정(중심 논증)**: `tos.vtg` 채택 시 기존 문서(#15 iap·#17
  sbr)의 배제 목록에 열거된 `tos.venue`(미구현)가 **영구 phantom**이 되고 `tos.vtg` 추가 에라타가 필요한가? →
  **부분적으로만**. 기존 §7.1 테스트가 **allowlist**(`closure ⊆ {canonical, ordering, self}`)라면(sbr 확정·
  `__init__.py:47-48`) 신규 형제는 **이름 불문 자동 배제**되므로 **enforcement 에라타는 불요**; 남는 것은 illustrative
  prose의 `tos.venue`→`tos.vtg` 문서-위생 정정뿐이다. **핵심 논증(task 요구)**: **배제 목록의 규율은 "실재 형제
  전부"**이므로, `tos.venue`든 `tos.vtg`든 **구현 착지 시 모든 형제 allowlist에 신규 형제로 자동 포섭**되는 것은
  동일하다(allowlist는 self만 확장, 형제는 추가하지 않음). 따라서 "신규 형제 추가 부담"은 두 명명에서 **대칭**이고,
  비대칭은 오직 (i) `venue_*` 코드 토큰 정합과 (ii) 기존 prose phantom 회피뿐 — 둘 다 `tos.venue`를 지지. **§10.2
  운영자 판단 지점**: `tos.venue`(선점·seam 정합·phantom 0) vs `tos.vtg`(register-prefix 충실). 내부 module
  (`_base.py`·`vocabulary.py`·`records.py`·`predicates.py`·`state.py`)은 ioc/iap/sbr 선례 동형.

**(b) VTG = admissibility gate 소유, conformance/capacity/approval/capability는 형제 소유 (중심 결정·코드 실측).**
VTG는 **dataflow상 order-admissibility gate**다 — ioc candidate command·brokercap ceiling·capsule CII·time
session·spg policy-activation을 **소비**하여 exact order shape의 admissibility를 판정하되, 그 **conformance(ioc)·
capacity(rcl/are)·approval(iap)·capability semantics(brokercap)·currentness(ADR-002-024)·authority(authority/
liveauth) 판정 자체는 재저작하지 않는다**. #14 IOC가 "intent-order conformance이지 admissibility가 아니다"(#14 §0.4
line 139-141)라고 자리매김한 것과 **정확히 대칭**으로, **VTG는 venue-constraint admissibility이지 conformance/
capacity/approval이 아니다**(ADR §1 line 21-25). 이것이 §3.5 소유권 분할의 축이며, 위반 시 권위 중복(#8 lesson).

- VTG가 **소유**: `VenueConstraintPolicy` content(§8)·`VenueConstraintSnapshot`(§9-13 evaluation)·
  `OrderAdmissibilityDecision`(§14 exact shape 판정)·`SessionPhase` authoritative 판정(§10)·per-action
  `TradabilityState`(§11)·order-shape venue-admissibility(§12)·`constraint_generation` **의미/fencing**(§18; ordering는
  carry)·material-change invalidation 폐포(§18)·final-egress currentness **요구 술어**(§17, 메커니즘은 ADR-002-024).
- VTG가 **소비**(형제 결과 주입 scalar/digest): ioc candidate `CanonicalBrokerCommand` id/digest(§14)·brokercap
  `BrokerCapabilityProfile` version/digest(ceiling, §13)·capsule `DecisionContextCapsule`/`CriticalInputSnapshot`
  digest(§9/§14)·time `SessionContext`/time-health(§10)·spg VENUE_CONSTRAINT_POLICY activation/generation(§8)·recon
  conflict-conservatism(§13)·protective classification(§19).
- VTG가 **생산**(하류 형제가 scalar로 소비): `OrderAdmissibilityDecision` digest(→ ioc `OrderConformanceProof.
  venue_admissibility_decision_digest` `records.py:414`)·`VenueConstraintSnapshot` digest·decision digest(→ iap
  `ProposalApprovalRequest` `records.py:256-257`)·3-Ref(→ capsule `DecisionContextCapsule` `capsule.py:242-244`).

**(c) sibling edge 0 권장 vs time.SessionContext typed-reuse 1 edge (중심 판단 지점·#14/#15 distinction).** VTG는
형제 **결과**를 대량 소비하나 iap(#15)/sbr(#17)와 동형으로 **edge 0**을 권장한다. 유일한 edge-1 후보는 §10 session
phase다:

- **권장: edge 0 (result/digest injection).** 모든 형제 상호작용을 **주입된 scalar·digest·bool·verdict·opaque
  enum-token(str)** 으로 받는다. 근거: iap(edge 0, `__init__.py` "REUSES no sibling type")·sbr(edge 0)의 배포
  선례. VTG의 아티팩트는 전부 `tos.canonical`(base)+`tos.ordering`(generation) 위에 로컬 저작되고 형제는 digest로만
  참조된다.
- **대안: time.SessionContext REUSE (1 edge).** VTG `SessionPhase`를 time `SessionContext`(`time/elements.py:177`,
  `phase: str | None`·tz/calendar·`is_open`·`session_open_positively`)의 typed field로 저장. **기각(중심 논증)**:
  time.SessionContext는 **broker-agnostic calendar-expectation**(`elements.py:180` "tz/calendar identities/versions,
  phase, an injected ``is_open`` determination from the calendar")이지 **authoritative current phase가 아니다**. VTG
  §10 line 269 verbatim: "Scheduled time SHALL NOT be used as the sole proof of phase when unscheduled closure,
  delayed open, auction extension, volatility interruption, halt, suspension, or venue incident is credible." ⇒
  VTG-INV-002(line 153 "Calendar time … never proves order-specific tradability")가 정확히 이 REUSE를 **금지**한다 —
  calendar phase를 admissibility phase로 채택하면 INV-002 위반. VTG는 time.SessionContext를 **한 evidence 입력**으로
  소비(digest scalar)하되 자신의 authoritative `SessionPhase`를 **별도 생산**한다. edge 0 유지. **§10.2 판단 지점**:
  edge 0(권장·INV-002 정합) vs time REUSE(타입 안전·INV-002 위반 위험). 리뷰어 공격 지점(§10.2): "VTG SessionPhase가
  time.SessionContext.phase를 중복한다" — 반론: 의미 도메인 상이(calendar-expectation vs authoritative-current)이고
  INV-002가 동일시를 금지.

**(d) `OrderAdmissibilityResult` 명명 — `dsl.AdmissibilityResult`와 충돌 회피 (중심 판정·차원 비붕괴·phantom 규율).**
**실측 충돌**: `dsl.AdmissibilityResult`(`dsl/evidence.py:58`, `IndependentIdArtifact`)·`dsl.AdmissibilityVerdict`
(`dsl/admissibility.py`, `dsl/__init__.py:79`)가 **이미 존재**하나, 이는 **ADR-DEV-001 정적 Strategy-DSL** 도메인
(`dsl/evidence.py:1` "Enforcement-evidence records … ADR-DEV-001 §8"; `CandidateProgram`을 embed하고 `analyze`로
verdict 재도출)이지 **ADR-002-019 venue-constraint 도메인이 아니다**. ADR §5.4(line 123)는 결과값을 "``ADMISSIBLE``,
``RESTRICTED_PROTECTIVE_ONLY``, ``INADMISSIBLE``, or ``UNKNOWN``"로 정의한다. **판정**: VTG의 결과 enum을
**`OrderAdmissibilityResult`**(아티팩트 `OrderAdmissibilityDecision`의 result)로 명명해 `dsl.AdmissibilityResult`
(record)·`dsl.AdmissibilityVerdict`(dsl enum)와 **명명·의미 모두 분리**한다. dsl "admissibility"(정적 프로그램
admission)와 VTG "admissibility"(venue order admission)는 **동음이의**이며 §3.5에서 명시 분리. **REUSE 금지**: dsl
타입을 import하면 (i) firewall sibling-edge, (ii) ADR-DEV vs ADR-002 도메인 혼동(차원 비붕괴 위반)이므로 로컬 저작.

**(e) `constraint_generation` 좌표 소유 (ordering가 순서, VTG가 fence 의미).** `VenueConstraintSnapshot`은
`constraint_generation`(capsule `VenueConstraintSnapshotRef.constraint_generation` `capsule.py:142` 실측)을
carry한다. ADR §5.3(line 117-119) "**Constraint Generation** — A monotonic restrictive generation for one
constraint domain. A newer halt, suspension, restriction, source discontinuity, account restriction, or policy
generation fences older decisions for future new-risk transmission." ⇒ **VTG가 fence 의미를 소유**(§18
invalidation·§17 egress rejection), `tos.ordering`은 monotonic 순서 substrate만 제공(REUSE·§3.2). policy는
별도 `policy_generation`(`VenueConstraintPolicyRef.policy_generation` `capsule.py:134`) — spg governance 소관(§8).
**non-collapse canary 상속**(#17 §4.3): constraint_generation을 policy_generation 등 다른 generation 좌표로 대체하면
fence 불성립을 보존(§4.3).

**(f) 앵커 규약 — VTG-INV/AC/EV 앵커, 새 시리즈 창작 금지.** **실측**: ADR-002-019는 자체 시리즈
**`VTG-INV-001..014`(§6 line 149-203, 14종)·`VTG-AC-001..012`(§27 line 603-649, 12종)·`VTG-EV-001..012`
(EVIDENCE-REGISTER-002.csv line 221-232, 12행)를 정의**한다. §27 preamble(line 651 verbatim): "Each case maps
one-to-one to ``VTG-EV-001`` through ``VTG-EV-012`` … Written cases are not completed evidence." ⇒ 본 계약은 모델
불변식·술어를 **`VTG-INV-###` / `VTG-AC-###` / `VTG-EV-###` / §-clause / `SAFE-###`(§28 traceability line
657-669)**에 앵커하고 **새 시리즈를 창작하지 않는다**. #12–#17 동형.

**(g) VTG-EV = core 4 + predicate-only 8, 닫는 VTG-EV = 0건.** register 실측(§1): **4행(001·003·004·006)이
`EV-L1/3` 슬라이스 보유**(core L1), 8행(002·005·007·008·009·010·011·012)은 최소 `EV-L2`. ⇒ §1 분류는 **core(L1
슬라이스 4) / predicate-only(8) / not-Phase-1** 3분류(task 지시 count와 일치). **닫는 VTG-EV = 0건** — L1 슬라이스
저작은 EV closure가 아니다(`/3`·`+Security`·`+Broker` 통합·독립 리뷰 잔여). **truthy-sentinel 규율(#14 M1 교훈을
처음부터)**: `OrderAdmissibilityResult`·`TradabilityState`가 non-empty StrEnum이므로 **소비 게이트는
`result is OrderAdmissibilityResult.ADMISSIBLE` 명시 비교**(truthy 금지)를 §4.7·§5에 계약화하고 **`__bool__ ⇒
TypeError` 구조 봉인**을 처음부터 채택한다(ioc `ConformanceResult` `vocabulary.py:63` 동형).

---

## 1. 범위 매핑 — ADR-002-019 조항별 EV-L1 도달성 (닫는 VTG-EV 0건)

EV-level 정의(VER-002-001): **EV-L1 = Model and Property Verification**(state-machine exploration, model
checking, property-based testing, deterministic simulation). **EV-L2 = Component Fault Test**, **EV-L3 =
Integration/Adversarial**, **+Security = independent security-boundary assessment**(identity/credential/
authorization/fencing/bypass), **+Broker = broker-integration**. Phase 1은 EV-L1만이다.

> **결정적 사실 1 — VTG-EV ↔ VTG-AC 1:1, 최소 레벨 실측**: `VTG-EV-001..012`(EVIDENCE-REGISTER-002.csv line
> 221-232)는 ADR §27 `VTG-AC-001..012`(line 603-649)와 제목·번호가 **1:1**(§27 line 651 verbatim "Each case maps
> one-to-one to ``VTG-EV-001`` through ``VTG-EV-012``"). register 최소 레벨 실측 histogram:
> **`EV-L1/3+Broker` ×2**(001·004) · **`EV-L1/3+Security` ×2**(003·006) · **`EV-L2/3+Broker` ×4**(002·005·008·
> 009) · **`EV-L2/3+Security` ×4**(007·010·011·012). ⇒ **`EV-L1` 슬라이스 보유 4행 = core tier**(task 지시
> "core 4"와 일치), **부재 8행(최소 ≥ L2) = predicate-only substrate**. **+Security 6/12**(003·006·007·010·011·
> 012)·**+Broker 6/12**(001·002·004·005·008·009). **broker_capability_profile_version 컬럼 = `N/A` 2행**(006·011,
> csv line 226·231) — 006(Exact Decision Binding·순수 canonical/digest binding)·011(Authority Separation·순수
> authority-separation)은 broker-capability 의존이 **구조적으로 없어** N/A(나머지 Security 행 003·007·010·012는
> broker-cap TBD). 이 비대칭은 §3.5 brokercap 경계와 정합(006/011은 brokercap ceiling과 무관).
>
> **결정적 사실 2 — authoring ≠ acceptance(닫는 VTG-EV = 0건)**: Phase 1은 각 VTG-EV의 **L1-decidable
> predicate/model substrate**를 저작하나 **어떤 VTG-EV도 닫지 않는다.** (a) core 4행조차 `/3` 잔여(integration/
> adversarial fault test)·2행 +Broker(001·004)·2행 +Security(003·006), (b) 8행은 최소 ≥ L2, (c) VER-002-001 §5
> "Registration is not execution"·ADR §27 line 651 "Written cases are not completed evidence"·§30 line 705 item
> 10. ⇒ **"EV-L1-complete 주장 금지"**(#12–#17 §1 규율 상속). Owner/Reviewer는 register상 TBD·status
> NOT_IMPLEMENTED(csv 전 12행).

**규율 태그(모든 주장에 부착)**: "**predicate/model substrate only; VTG-EV-001..012 전부 NOT_IMPLEMENTED — core
4행(001·003·004·006)은 `/3`·+Broker(001·004)·+Security(003·006) 통합·adversarial·독립 리뷰 대기, predicate-only
8행은 EV-L2/L3 fault injection·adversarial·+Security(4)·+Broker(4) evidence 대기. EV-L1-complete 주장 금지.**"

**VTG-EV core 4행 ↔ AC ↔ ADR 조항 매핑(실측)**:

| VTG-EV | register 제목(verbatim, csv line) | 최소 레벨 | VTG-AC(1:1) | ADR 조항 앵커 | L1 substrate 술어(§5) |
|---|---|---|---|---|---|
| **001** | Closed Exceptional and Phase-Transition Sessions (221) | `EV-L1/3+Broker` | AC-001(line 603) | §10 venue/session·VTG-INV-002(line 153) | `session_phase_admits`(§5.1 — 미열거 phase ⇒ 거래 불가) |
| **003** | Exact Instrument Contract Account and Route (223) | `EV-L1/3+Security` | AC-003(line 611) | §11 instrument/tradability·VTG-INV-004(line 161) | `exact_instrument_route_bound`(§5.2 — alias/route 치환 거부) |
| **004** | Price Tick Lot Quantity and Order Shape (224) | `EV-L1/3+Broker` | AC-004(line 615) | §12 price/qty/shape·VTG-INV-004 | `order_shape_admissible`(§5.3 — permissive rounding 금지) |
| **006** | Exact Decision Binding and Substitution Resistance (226) | `EV-L1/3+Security` | AC-006(line 623) | §14 snapshot/decision·§16 binding·VTG-INV-004 | `decision_binding_exact`+`no_decision_union`(§5.4) |

**ADR-002-019 조항 → Phase-1 분류(core / predicate-only / not-Phase-1[형제 소유·런타임 이연])**:

| ADR 조항 | 요지 | Phase-1 분류 | L1 substrate / 소유 (근거) | VTG-EV |
|---|---|---|---|---|
| **§10** (line 267-275) | Venue/session state·exceptional phase | **core (L1 슬라이스)** | `session_phase_admits`(§5.1) — VTG-INV-002. 관측 phase-token ∉ policy admitting-set(exact action) ⇒ INADMISSIBLE/UNKNOWN(line 269 unscheduled closure); continuous-approved order ↛ auction/halt 재사용(line 273). broker 부분 +Broker(VTG-EV-001). `/3` 잔여. | **001** |
| **§11** (line 279-293) | Instrument/contract/tradability·exact route | **core (L1 슬라이스)** | `exact_instrument_route_bound`(§5.2) — VTG-INV-004. canonical identity + 전 routing-relevant alias/segment/contract-month/account/env/route binding(line 281); alias 치환 거부(§14 line 613 AC-003 "Every mismatch must be rejected"). +Security(VTG-EV-003). `/3` 잔여. | **003** |
| **§12** (line 297-311) | Price/tick/lot/qty/order-shape 정합(venue-admissibility) | **core (L1 슬라이스)** | `order_shape_admissible`(§5.3) — VTG-INV-004. price band/tick/lot/qty/order-type/TIF를 permissive rounding 없이 검증(line 299); rounding이 shape 변경 시 새 decision 필요(line 309). **ioc §12 conformance와 경계**(§3.5 — 같은 필드·다른 판정). +Broker(VTG-EV-004). `/3` 잔여. | **004** |
| **§14/§16** (line 329-345·361-377) | Exact snapshot/decision binding·substitution 저항 | **core (L1 슬라이스)** | `decision_binding_exact`+`no_decision_union`(§5.4) — VTG-INV-004. canonical digest가 전 decision-affecting 필드 cover(line 343); patch/partial-refresh/union/widen 금지(line 343); 한 필드 mutate ⇒ chain reject(§16 line 377·AC-006 line 623). +Security(VTG-EV-006). `/3` 잔여. | **006** |
| **§10** (line 267-275) | Halt/suspension/tradability conflict | **predicate-only** | `tradability_conflict_unknown`(§6.1) — VTG-INV-005. 상충 venue/broker/quote/calendar ⇒ UNKNOWN(line 275 "majority or newest-arrival selection is not automatically authoritative"). 실 conflict resolution·broker probe는 +Broker. 최소 `EV-L2/3+Broker`. | **002** |
| **§13** (line 315-325) | Account/margin/borrow/settlement eligibility | **predicate-only** | `account_constraint_conservative`(§6.2) — VTG-INV-005. margin/borrow/eligibility는 stale balance/prior order/absence-of-error에서 추론 불가(line 319); 상충 evidence conservative(ADR-002-006). 실 broker/margin query는 +Broker. 최소 `EV-L2/3+Broker`. | **005** |
| **§17** (line 381-398) | Active final-egress currentness·invalidation race | **predicate-only** | `egress_currentness_active`+`stale_decision_rejected_at_egress`(§6.3) — VTG-INV-010. cache/TTL/heartbeat/absence ↛ currentness(line 394); race unprovable ⇒ potentially-live containment(line 396). 실 active currentness는 ADR-002-024 +Security. 최소 `EV-L2/3+Security`. | **007** |
| **§11/§19** (line 283-291·418-431) | Exit/reduce-only/cancel/reversal | **predicate-only** | `exit_not_assumed_admissible`(§6.4) — VTG-INV-003. exit/reduce-only/cancel/replace 독립 제약·INADMISSIBLE/UNKNOWN 가능(line 157); reduce-only가 reversal 위험(line 285). broker 의미는 +Broker. 최소 `EV-L2/3+Broker`. | **008** |
| **§19** (line 418-433) | Protective/replacement constraints | **predicate-only** | `protective_label_no_bypass`(§6.5) — VTG-INV-007. protective는 exact current admissibility + 별도 classification/authority + 전 intermediate effect capacity 필요(line 175); label ↛ bypass(line 173). 실 replacement·partition-lease는 +Broker(ADR-002-011/001). 최소 `EV-L2/3+Broker`. | **009** |
| **§9/§15** (line 249-263·349-357) | Source/policy/capability/common-mode drift | **predicate-only** | `common_mode_reduces_scope`+`unknown_continuity_invalidates`(§6.6) — VTG-INV-005/006. shared dependency ≠ independent corroboration(line 353); unknown continuity ⇒ 영향 future decision 무효(line 263). 실 failure-domain·security는 +Security. 최소 `EV-L2/3+Security`. | **010** |
| **§7** (line 207-223) | Authority separation·bypass 저항 | **predicate-only** | `gate_authority_separated`(§6.7, all-false) — VTG-INV-011. gate는 approve/mutate-capacity/issue-authority/classify-protection/transmit/clear-HALT/re-arm 불가(line 189-191); live credential/route 미보유(line 223). bypass·SoD는 +Security. **broker-cap N/A**(csv line 231). 최소 `EV-L2/3+Security`. | **011** |
| **§22** (line 461-475) | Recovery/reopen/non-revival | **predicate-only** | `reopen_revives_nothing`(§6.8) — VTG-INV-013. reopen/halt-release/reconnect/restart/failover/clock-recovery ↛ revive old decision/authority(line 197·473); fresh decision+chain 필수(line 471). 실 recovery workflow는 sbr/ADR-002-017 +Security. 최소 `EV-L2/3+Security`. | **012** |
| **§5** (line 107-144) | Definitions — 9 vocabulary | **core substrate(분산)** | 9-모델·`OrderAdmissibilityResult`/`TradabilityState`/`SessionPhase` 어휘(§2). policy governance는 spg/ADR-002-014(§8 line 243). | 001-012 공통 |
| **§17 active currentness·§18 propagation·§20 broker responses·§21 partition** | active currentness·invalidation distribution·broker ambiguity·control-plane partition | **not-Phase-1 (런타임 EV-L2/L3·+Security/+Broker)** | ADR-002-024 Currentness Vector(§17 line 388·ADR §1 line 35)·§18 propagation bound(§27 q12)·ADR-002-004 broker semantics(§20)·§21 partition(§27 q10). venue는 순수 술어·모델만. | 002/005/007/010/012 (런타임) |
| **§8 policy schema·§27 open questions·§4 non-scope** (line 227-245·673-688·92-103) | Venue Constraint Policy schema·source contracts·numeric bound·human class | **not-Phase-1 (Phase-0/INSTANCE)** | 제품·source·수치·human class는 §9.2 Phase-0. 전부 주입. | — |

---

## 2. 데이터 모델 계약

**표현 원칙**: 모든 아티팩트는 **pydantic v2 frozen 모델**(`ConfigDict(frozen=True, extra="forbid")`, canonical
`FrozenModel` `_base.py:73` 상속). 어휘는 **StrEnum**(non-empty value·`__bool__ ⇒ TypeError` 봉인 §4.7). numeric
bound·tick/lot/band 값 부재(전부 주입 opaque param §8). id·digest 분류는 §2.1.

### 2.1 digest-bound / value / reference 분류 (총괄 — capsule Ref 실측으로 확정)

> **결정적 실측**: 3 core 아티팩트의 identity shape는 **추측이 아니라 capsule Ref가 이미 확정**했다 —
> `capsule/capsule.py:130-150`. 본 계약은 그 shape를 따른다(#15 M1 교훈 — 필드-클래스 소유 확인).

| 아티팩트 | 분류 | id⊥digest? | 근거(코드+ADR) |
|---|---|---|---|
| `VenueConstraintPolicy` | **`IndependentIdArtifact`** (id⊥digest) + `policy_generation` | **예** | capsule `VenueConstraintPolicyRef` = {`policy_id`, `policy_generation`, `canonical_digest`}(`capsule.py:130-135`). §5.1 line 111 "immutable, authenticated, separately governed"; §14 line 335 "policy identity, version, generation, digest, approval state". activation은 spg(§8·§3.5). same-id/diff-bytes(policy 위조·rollback) ⇒ `classify_record_pair` `CRITICAL_CONFLICT`(§18). |
| `VenueConstraintSnapshot` | **`IndependentIdArtifact`** (id⊥digest) + `constraint_generation` | **예** | capsule `VenueConstraintSnapshotRef` = {`snapshot_id`, `constraint_generation`, `canonical_digest`}(`capsule.py:138-143`). §5.2 line 115 "immutable, time- and scope-bounded evaluation … grants no authority". snapshot_id⊥digest ⇒ snapshot substitution 탐지(VTG-EV-006). |
| `OrderAdmissibilityDecision` | **`IndependentIdArtifact`** (id⊥digest) | **예** | capsule `OrderAdmissibilityDecisionRef` = {`decision_id`, `canonical_digest`}(`capsule.py:146-150`). §5.4 line 121 "immutable canonical result for one exact broker-request shape". **중심 아티팩트** — ioc `OrderConformanceProof`(`records.py`)·iap `IndependentApprovalDecision` 동형(id⊥digest, substitution 저항 VTG-EV-006). |
| `ConstraintGeneration` | **`tos.ordering` REUSE** | — | §5.3 line 117-119 "monotonic restrictive generation … fences older decisions". `tos.ordering.Ordering`/`compare_order`(`__init__.py:19`)로 monotonic 순서(§3.2). snapshot의 `constraint_generation` int 좌표(§0.4e). |
| `OrderAdmissibilityResult` | **StrEnum(어휘·truthy 봉인)** | — | §5.4 line 123 4-값. §2.2(1). |
| `TradabilityState` | **StrEnum(어휘·truthy 봉인)** | — | §5.6 line 131. §2.2(2). |
| `SessionPhase` | **주입 opaque token(str)** | — | §5.5 line 127 "Names are policy-defined" ⇒ hardcoded enum 금지. §2.2(3). |
| `VenueGateAuthorityEffect` | **all-false FrozenModel** | — | §7 line 213·§14 line 341 "explicit non-authorizing flags"·VTG-INV-011. ioc `AllFalseConstructionAuthority`(`_base.py:54`) 동형. §2.2(4). |

### 2.2 어휘 (verbatim 전사 — 차원 비붕괴 + truthy 봉인)

**(1) `OrderAdmissibilityResult`** — §5.4 line 123 verbatim 4-값: `ADMISSIBLE`·`RESTRICTED_PROTECTIVE_ONLY`·
`INADMISSIBLE`·`UNKNOWN`. ADR §1 line 23 verbatim: "``ADMISSIBLE`` means **only** that the exact order shape passed
the declared constraint checks at the decision point. It does not mean the order is economically safe, approved,
capacity-covered, currently authorized, accepted by the broker, filled, or capable of reducing exposure." ⇒
**`ADMISSIBLE`만 ordinary pass**. `RESTRICTED_PROTECTIVE_ONLY`는 §1 line 29·§19 line 426 "only a separately
authorized exact action whose current restrictive-path constraints are positively proven may proceed" — **ordinary
new risk 불가·별도 protective authority 필요**. **truthy-sentinel 구조 봉인(#14 M1 선제·본 도메인에서 더 임계)**:
4-값 전부 non-empty StrEnum이라 `if result:`/`bool(result)`면 `INADMISSIBLE`·`UNKNOWN`뿐 아니라
**`RESTRICTED_PROTECTIVE_ONLY`까지 truthy**로 읽혀 **protective-only를 full-permission으로 오독**하는 catastrophic
fail-open. ⇒ `__bool__ ⇒ TypeError` 봉인(ioc `ConformanceResult.__bool__` `vocabulary.py:63` 동형). **소비 게이트:
`result is OrderAdmissibilityResult.ADMISSIBLE`(ordinary)**; `RESTRICTED_PROTECTIVE_ONLY`는 별도 protective 검증
게이트(§6.5) 통과 시에만. `INADMISSIBLE`/`UNKNOWN`은 denial.

**(2) `TradabilityState`** — §5.6 line 131 verbatim: "`TRADABLE` is not a global instrument boolean." §11 line
283-291은 exact action별 tradability를 요구하므로 `TradabilityState`는 **per-action 판정 dimension**이다(new
long/short·increase/decrease/close/reversal·cancel/amend/replace/reduce-only·protective/emergency·routing
alternative — line 285-289). 값 집합은 최소 {`TRADABLE`, `NOT_TRADABLE`, `RESTRICTED`, `UNKNOWN`}(정확 열거는 §5.2에서
policy-bound). **truthy 봉인**(`TRADABLE`만 pass; `__bool__ ⇒ TypeError`; 소비 `is TradabilityState.TRADABLE`). §11
line 291 verbatim: "An instrument may be quoteable but not orderable, sellable but not shortable, cancellable but not
replaceable … A global ``tradable=true`` field is insufficient." ⇒ 단일 bool 금지·per-action verdict.

**(3) `SessionPhase` — 주입 opaque token(hardcoded enum 금지·중심 판정)**. §5.5 line 127 verbatim: "such as closed,
pre-open, opening auction, continuous trading, volatility interruption, halt, reopening auction, closing auction,
post-close, or approved after-hours phase. **Names are policy-defined** and never imply permission by themselves." ⇒
phase 이름 집합은 **policy가 정의하는 open set**이므로 **hardcoded closed StrEnum은 (i) "names are policy-defined"
위반·(ii) 숫자/문자열 하드코딩 금지 규율 위반**. **판정**: `SessionPhase`는 **주입 opaque token(str)**; policy가
action-class별 **admitting phase-token set**을 제공하고, VTG 술어는 `observed_phase_token ∈
policy.admitting_phases(action)` 여부만 판정(§5.1). **fail-closed 메커니즘**(enum truthy-seal과 다름): 관측 token이
policy known-admitting-set에 **부재**(미열거 exceptional session·unknown token) ⇒ **restrictive**(§8 line 245
"unsupported enum … produces ``UNKNOWN`` or ``INADMISSIBLE``, never a permissive default"). 이것이 VTG-EV-001
"Closed Exceptional and Phase-Transition Sessions"의 노른자다. time.SessionContext.phase(calendar-expectation)와
**혼동 금지**(§0.4c — authoritative-current ≠ calendar).

**(4) `VenueGateAuthorityEffect`** — §7 line 213·§14 line 341 "explicit non-authorizing flags"·VTG-INV-011 line 189.
전 필드 `False`(approves·mutates_capacity·issues_authority·classifies_protection·transmits·clears_halt·rearms 전부
`False`). ioc `AllFalseConstructionAuthority`(`_base.py:54`, `model_validator` "any ``True`` flag makes the artifact
unconstructable" `_base.py:60`; 클래스 `:54`·validator `:74` — v1.1 M3 통일)·rcl `AllFalseAuthority`·are `AllFalseAggregateAuthority` **동형** — **로컬 저작**(cross
-sibling import 아님; ioc `_base.py:18-19` 선례 "authored locally, fresh"). 구성-불변식으로 봉인 + defence-in-depth
술어 `gate_grants_no_authority`(§6.7, `model_construct` escape hatch 대비 — ioc `_base.py:66-70` 동형).

**(5) `ConstraintClass` (주입 enum-token)** — §8 line 229-241의 constraint 분류(session-phase·instrument/contract·
price/tick/lot/qty·order-type/TIF·account/margin/borrow/settlement·broker-capability). policy가 정의하는 open set
이므로 **주입 enum-token**(classifier·precedence는 Phase-0 §27 q2). VTG는 분류 결과만 소비, 재분류 안 함(§5.4
material-change 판정은 policy가 소유 — §14 line 345 "The policy, not a proposer or consumer, determines materiality").

### 2.3 아티팩트 covered + self-exclusion (설계 #4 §3.3 상속)

`VenueConstraintSnapshot`·`OrderAdmissibilityDecision`은 자신의 canonical digest를 covered-set에서 **제외**한다
(self-reference paradox 회피, canonical `IndependentIdArtifact` 규약; ioc `OrderConformanceProof._COVERED_FIELDS`
`records.py:391` 동형 — id 필드 제외). decision이 binding하는 candidate-command·snapshot·capsule·brokercap·are·rcl
digest는 decision 자신의 digest를 제외한 **입력 아티팩트 digest만** 포함. `required_authority_scope`류 mandatory
필드는 missing/empty ⇒ UNKNOWN/INADMISSIBLE(ioc `records.py:374` "missing/empty scope means ``UNKNOWN`` …, **never**
zero/wildcard" 동형·§4.7).

### 2.4 핵심 모델 필드 골격 (§ref·형제 seam·capsule Ref 정합)

- **`VenueConstraintPolicy`**(§8 line 229-241): `policy_id`⊥`canonical_digest`·`policy_generation`(capsule Ref
  정합)·scope(environment/broker/account/venue/market-segment/product/instrument/contract, line 231)·source
  identities/continuity/schema/mapping/unit/scale/time-req(line 232)·session-phase state machine/holidays/auctions/
  halts/reopen/after-hours(line 233)·instrument listing/suspension/expiration/roll/settlement/corp-action(line 234)·
  price bands/limits/tick tables/quantity/lot/rounding(line 235, **전부 주입 값**)·sides/position-effects/order-types/
  TIF/routing/amend-cancel(line 236)·account permissions/borrow/margin/currency/settlement(line 237)·broker-capability
  prereq(line 238, **brokercap 주입**)·independent-validation/common-mode(line 239)·decision fields/max-age/dependency
  closure/invalidation rules(line 240)·conservative failure response/protective-only/evidence class/live scope(line
  241). **activation은 spg 소관**(§8 line 243·§3.5) — VTG는 content author. 완전성/미열거 처리는 §5.1.
- **`VenueConstraintSnapshot`**(§9-13·§14 line 336-338): `snapshot_id`⊥`canonical_digest`·`constraint_generation`
  (capsule Ref 정합)·policy id/version/generation/digest(line 336, **주입**)·source continuity/observation/mapping/
  schema/time-health/consistency-cut identities(line 337, **capsule/time 주입**)·venue/market-segment/instrument/
  contract/session-phase/account/margin/borrow/settlement facts(line 338)·**per-action `TradabilityState` map**(§11)·
  uncertainty/max-age/invalidation predicates/dependency closure(line 339)·CII/Context-Generation binding(line 336,
  **capsule 주입**). §5.2 "binds Critical Input provenance and uncertainty but **grants no authority**".
- **`OrderAdmissibilityDecision`**(§14 line 331-341): `decision_id`⊥`canonical_digest`·policy id/version/generation/
  digest·Constraint Generation·Decision Context Capsule id/digest(line 333, **capsule 주입**)·source continuity/
  observation/mapping/consistency-cut(line 334)·**exact broker/env/account/venue/market-segment/instrument/contract/
  side/position-effect/action-class/quantity/price-instruction/order-type/TIF/session-phase/routing**(line 335)·**exact
  candidate `CanonicalBrokerCommand` id/digest + Order Construction Policy/Generation**(line 336, **ioc 주입 §3.5**)·
  price/tick/lot/margin/borrow/settlement/account/broker-capability facts(line 337, **brokercap 주입**)·**`result:
  OrderAdmissibilityResult`·failed/unknown predicates·uncertainty·max-age·issue/expiry evidence·invalidation
  predicates·dependency closure**(line 338)·evaluator identity/build/config/deployment/evidence generations(line
  339)·**`authority_effect: VenueGateAuthorityEffect`(all-false, line 340 explicit)**. §14 line 342-343 "canonical
  digest SHALL cover all fields that can change the decision or economic effect … cannot be patched, partially
  refreshed, unioned, widened, or silently recomputed"(§5.4).

---

## 3. canonical / ordering REUSE + sibling edge 0 + 형제 경계

### 3.1 canonical REUSE

`tos.canonical`에서 REUSE(실측 slot): `FrozenModel`(`_base.py:73`)·`IndependentIdArtifact`(`_base.py:328`, policy/
snapshot/decision 3 core — id⊥digest)·`DigestBoundArtifact`(`_base.py:98`, 필요 시 content-addressed 보조 record)·
`classify_record_pair`(`record_pair.py:52`)+`RecordPairKind`(`record_pair.py:31`, §14 decision/snapshot substitution·
§18 correction/conflict 탐지)·`ArtifactStatus`(`_base.py:58`)·`EVL1ProvisionalCanonicalizer`(`canonicalization.py:173`,
잠정 canonical form — 프로덕션 schema는 Phase-0 §9.2). all-false authority(`VenueGateAuthorityEffect`)는 canonical에
없으므로 **로컬 저작**(ioc `_base.py:16-19`·rcl `AllFalseAuthority` 선례 — import 아님).

### 3.2 ordering REUSE (Constraint Generation monotonic 순서)

`tos.ordering`에서 REUSE: `Ordering`·`OrderingEvent`·`compare_order`(`__init__.py:19`). **Constraint Generation**
(§5.3 line 117-119 "monotonic restrictive generation … A newer halt, suspension, restriction, source discontinuity,
account restriction, or policy generation fences older decisions")은 append-only monotonic 순서 — `compare_order`로
"newer fences older" 판정(§6.3 stale-decision-reject·§18 invalidation). 실측: `ordering/_ordering.py:38`
`from tos.canonical import FrozenModel`만 의존이라 core(sibling edge 무증가). **fence 의미는 VTG 소유·ordering는
순서 substrate만**(§0.4e).

### 3.3 REUSE 요약 표

| REUSE 대상 | 출처 | 용도(§ref) | edge |
|---|---|---|---|
| `FrozenModel`·`IndependentIdArtifact`·`DigestBoundArtifact`·`classify_record_pair`·`ArtifactStatus`·`EVL1ProvisionalCanonicalizer` | `tos.canonical` | 3 core 아티팩트 base·§14/§18 conflict 탐지 | core(단방향) |
| `Ordering`·`compare_order` | `tos.ordering` | Constraint Generation monotonic(§6.3/§18) | core(단방향) |
| **(형제 타입 REUSE 0건)** | — | 전 형제 상호작용 = injected scalar/bool/enum-token/verdict/digest(§3.4) | **sibling edge 0** |

### 3.4 형제 경계 — scalar·bool·enum-token·verdict·digest seam (edge 0, 코드 실측)

VTG는 order-admissibility gate로서 **형제 결과를 대량 소비/생산**하나, iap(#15)/sbr(#17) 선례(edge 0)로 유지한다.
각 seam은 **런타임 Venue Constraint Gate가 형제 술어를 호출/형제 아티팩트를 digest로 참조 → 결과를 VTG 순수 모델에
주입**하는 형태(sibling 서사 아님 — #10 MAJOR 교훈. 전 slot file:line 실측):

| VTG 소비/생산 (§ref) | 타입 | 상대 (이미 비준·구현) | signature/slot(실측) |
|---|---|---|---|
| ioc candidate `CanonicalBrokerCommand` **소비** | `str`(id/digest, 주입) | ioc `CanonicalBrokerCommand`(ADR-002-020; ioc `records.py`) | §14 line 336 "exact candidate Canonical Broker Command identity/digest" — VTG가 admissibility를 이 candidate에 평가; ioc는 상류(command 구성), VTG는 그 command의 venue-admissibility 판정 |
| `OrderAdmissibilityDecision` digest **생산**(→ ioc 소비) | `str`(digest) | ioc `OrderConformanceProof.venue_admissibility_decision_digest`(`ioc/records.py:414`·`_COVERED_FIELDS` `:391`) | §16 line 368 "candidate Canonical Broker Command and later Order Conformance Proof" — ioc proof가 VTG decision digest binding; **양방향 digest·edge 0**(acyclic §3.5 (c)) |
| `VenueConstraintSnapshot`·`OrderAdmissibilityDecision` digest **생산**(→ iap 소비) | `str`(digest) | iap `ProposalApprovalRequest.venue_snapshot_digest`·`venue_admissibility_decision_digest`(`iap/records.py:256-257`·`predicates.py:151-152`) | §16 line 364-366 approval binding; iap가 VTG 두 digest 소비; **admissibility ≠ approval**(§30 item 12) |
| 3-Ref **생산**(→ capsule 소비) | Ref{id/gen/digest}(주입 scalar) | capsule `DecisionContextCapsule.venue_constraint_policy`/`venue_constraint_snapshot`/`order_admissibility_decision`(`capsule/capsule.py:242-244`, `*Ref` `:130-150`) | §9 line 251 CII·§14 line 333 Capsule binding; capsule가 VTG 3-Ref carry(id/gen/digest scalar) |
| brokercap `BrokerCapabilityProfile` **소비**(ceiling) | `str`/`int`(version/digest, 주입) | brokercap `BrokerCapabilityProfile`·`MARKET_INSTRUMENT_CONSTRAINTS`(`brokercap/vocabulary.py:86`)·version scalar(`predicates.py:277`) | §13 line 323 "required ceiling … cannot be promoted by the Gate"(VTG-INV-006); VTG는 ceiling scalar 소비·promote 불가 |
| spg VENUE_CONSTRAINT_POLICY activation/generation **소비** | verdict/int(주입) | spg `GovernedProfileClass.VENUE_CONSTRAINT_POLICY`(`spg/vocabulary.py:205`)·activation verdict | §8 line 243 "Policy activation follows ADR-002-014" — spg가 activation 소유, VTG는 content author·activation verdict 소비 |
| time `SessionContext`/time-health **소비**(phase evidence) | digest/scalar(주입) | time `SessionContext`(`time/elements.py:177`, `phase: str\|None`·`session_open_positively`)·`TRADING_SESSION`/`BROKER_VENUE` domain(`domains.py:34/30` — v1.1 NIT 순서 정정) | §10 line 271 "trustworthy time and Constraint Generation … follow ADR-002-008"; VTG는 time evidence 소비·**authoritative phase 별도 생산**(§0.4c REUSE 기각) |
| recon conflict-conservatism **소비** | verdict/enum-token(주입) | recon `classify_field`/`FieldConfidenceClass`(ADR-002-006) | §13 line 319 "Conflicting … evidence remains conservative under ADR-002-006"; VTG는 recon 결과 fold·재정의 안 함 |
| protective classification **소비** | bool/enum(주입) | protective `ProtectiveOwnership`(`protective/vocabulary.py:60` — v1.1 M1 재귀속)·`dominating_halt_or_incident`(`protective/records.py:202`, 소비 `predicates.py:395`) | §19 line 433 "ADR-002-011 governs protective replacement"; VTG는 classification 소비·label ↛ bypass(VTG-INV-007) |
| authority/liveauth/are/rcl **생산**(admissibility 입력) | `str`(digest, 주입) | authority `SafetyAuthority`·liveauth `LiveAuthorization`·are `AggregateRiskDecision`·rcl commitment | §16 line 363-373 binding chain; VTG decision은 이들의 **한 입력**이지 authority/capacity/approval 아님 |
| sbr recovery obligation **생산**(admissibility 입력) | `str`(digest, 주입) | sbr `RecoveryObligation`(ADR-002-017 §22) | §22 line 469 "fresh … Order Admissibility Decision"; VTG decision이 sbr recovery obligation 입력·reopen ↛ revive(VTG-INV-013) |
| afg rate/session/budget **소비**(constraint class) | scalar/enum-token(주입) | afg(ADR-002-022, #16); `ACTION_FLOW_POLICY`(`spg/vocabulary.py`) | §13 line 325 "Rate, session, credential, and connection budgets are **constraints, not reserved protective capacity**"; VTG는 budget을 constraint-class scalar로 소비 |
| dsl(정적 DSL admissibility) **경계·비상호작용** | — | `dsl.AdmissibilityResult`/`AdmissibilityVerdict`(`dsl/evidence.py:58`·`dsl/admissibility.py`) | **동음이의·다른 도메인**(ADR-DEV-001 정적 프로그램 vs ADR-002-019 venue order); REUSE·import 금지(§0.4d) |

### 3.5 소유권 분할표 — venue가 소유 / 형제에서 소비·생산 (본 문서 최대 함정 지대, #11-#17 §3.5 상속)

> **소유권 분할 명시(#8·#11-#17 교훈 — cross-section 혼동 선제 봉합)**: ADR-002-019는 **venue constraint policy
> content·snapshot·order-admissibility decision·session-phase authoritative 판정·per-action tradability·order-shape
> venue-admissibility·constraint-generation fence·material-change invalidation·final-egress currentness 요구**만
> 결정하며(§4 line 81-90) **intent-order conformance(ioc)·candidate command 구성(ioc/ADR-002-020)·capacity mutation
> (rcl/are)·approval(iap)·broker capability semantics(brokercap/ADR-002-004)·CII 구성(capsule/ADR-002-018)·time 구현
> (time/ADR-002-008)·active currentness 메커니즘(ADR-002-024)·protective classification(protective/ADR-002-011)·human
> approval(ADR-002-015)·Live Authorization(liveauth/ADR-002-007)·recovery workflow(sbr/ADR-002-017)를 소유하지
> 않는다**. 함정: VTG가 ioc의 conformance·rcl의 capacity·iap의 approval·brokercap의 capability semantics를 재저작하면
> 권위 중복(#8 lesson). 아래 표가 경계를 코드 실측으로 고정한다.

| ADR 조항/개념 | venue 소유 (Phase 1) | 형제 소유 (재저작 금지) | seam 방향(실측) |
|---|---|---|---|
| **§8 Policy content** | `VenueConstraintPolicy` schema/content(§2.4) | policy **activation/generation/supersession**은 spg(`GovernedProfileClass.VENUE_CONSTRAINT_POLICY` `spg/vocabulary.py:205`; ADR-002-014) | VTG=content author; spg=activation authority; VTG는 activation verdict 주입 소비(§8 line 243) |
| **§10 Session Phase(authoritative)** | `SessionPhase` authoritative 판정·`session_phase_admits`(§5.1) | **calendar-expectation phase는 time**(`SessionContext.phase` `time/elements.py:191`; ADR-002-008) | VTG는 time.SessionContext를 evidence로 소비·**authoritative phase 별도 생산**; calendar ↛ admissibility(VTG-INV-002·§0.4c) |
| **§11 Tradability(per-action)** | `TradabilityState` per-action(§2.2(2))·`exact_instrument_route_bound`(§5.2) | **order lifecycle state는 orthostate**(`vocabulary.py:95` "broker-side order lifecycle … only from broker/venue evidence") | VTG=admissibility(보낼 수 있나); orthostate=lifecycle(살아있나); 다른 축·digest seam |
| **§12 price/qty/shape(venue-admissibility)** | `order_shape_admissible`(§5.3) — band/tick/lot/qty를 **venue 제약**으로 검증 | **intent-conformance는 ioc**(§11/§12 — command가 approved Intent에 부합하나) | **같은 필드·다른 판정**(핵심 판정 (a)); ioc candidate command 소비·VTG decision digest 생산 |
| **§13 broker constraint(current admissibility)** | current order admissibility within ceiling | **capability semantics·assurance는 brokercap**(`BrokerCapabilityProfile`; ADR-002-004 BC-EV) | brokercap=evidenced ceiling(broker가 뭘 할 수 있나); VTG=ceiling 내 current admissibility; promote 불가(VTG-INV-006) |
| **§13 account/margin/borrow/settlement** | account constraint conservatism(§6.2) | **per-field confidence는 recon**(ADR-002-006)·post-trade finality는 ADR-002-030 | VTG는 recon/PTOL 결과 소비·conservative fold(line 319·321); confidence 재계산 안 함 |
| **§14 candidate command** | admissibility 평가(§5.3) | **candidate `CanonicalBrokerCommand` 구성은 ioc**(ADR-002-020) | VTG는 candidate id/digest 소비(line 336); command 구성 안 함(§4 non-scope line 95) |
| **§14 CII/Capsule** | snapshot에 CII provenance binding(§2.4) | **CII/Capsule 구성은 capsule**(ADR-002-018; `capsule.py`) | capsule=구성 owner + 3-Ref carry(`capsule.py:242-244`); VTG=full 아티팩트 owner |
| **§14/§16 exact decision binding** | `decision_binding_exact`·`no_decision_union`(§5.4)·`OrderAdmissibilityDecision` | (binding chain 소비자는 iap/authority/liveauth/egress) | VTG decision digest → iap `records.py:256-257`·ioc `records.py:414`; 각 소비자가 mismatch reject(§16 line 377) |
| **§16 approval** | (미소유 — iap 소유) | **independent approval은 iap**(`IndependentApprovalDecision`; ADR-002-023) | VTG는 snapshot/decision digest 생산; iap가 approval request에 binding; **admissibility ≠ approval**(§1 line 21·§30 item 12) |
| **§16 capacity commit/release** | (미소유 — rcl/are 소유) | **capacity mutation은 RCL·aggregate는 ARE**(§7 line 216; ADR-002-002/012) | VTG는 admissibility fact만; decision expiry ↛ capacity release(§16 line 375·VTG-INV-009/012) |
| **§17 final-egress currentness** | currentness **요구 술어**(§6.3, active establish 요구) | **active currentness 메커니즘은 ADR-002-024·final egress enforcement는 ADR-002-013** | VTG는 순서·능동-확립 요구 술어(L1); Currentness Vector·egress enforce는 런타임(+Security) |
| **§18 constraint generation fence·invalidation** | `constraint_generation` fence 의미·material-change 폐포(§4.5) | `tos.ordering` monotonic 순서 substrate만(carry) | VTG가 fence 의미 소유·ordering는 순서(§0.4e); non-collapse canary(§4.3) |
| **§19 protective** | protective label ↛ admissibility bypass 술어(§6.5) | **classification/replacement은 protective**(ADR-002-011)·partition-lease는 ADR-002-001 §9(line 431) | VTG=admissibility 술어; protective=classification/capacity; label ↛ bypass(VTG-INV-007) |
| **§22 recovery/reopen** | `reopen_revives_nothing`(§6.8)·fresh decision | **recovery workflow는 sbr**(ADR-002-017 §22) | VTG decision이 sbr recovery obligation 입력(line 469); reopen ↛ revive(VTG-INV-013 ~ sbr non-revival) |

> **핵심 판정 (a) — ioc §12 conformance ≠ VTG §12 admissibility(같은 필드·다른 판정·본 문서 최대 아키텍처 공격
> 지점)**: **price/quantity/side/order-type/TIF는 두 gate가 모두 본다.** ioc §11/§12(`OrderConformanceProof`)는
> "이 candidate `CanonicalBrokerCommand`가 **approved Intent에 정확히 부합하나**"(substitution 없음·exact direction/
> qty/price-as-intended)를 판정하고, VTG §11/§12(`OrderAdmissibilityDecision`)는 "이 exact shape가 **venue에서 지금
> admissible한가**"(price band 내·valid tick·valid lot·이 session phase에서 지원되는 order type)를 판정한다. **예시**:
> price=X가 Intent에 CONFORMANT(ioc — 승인된 값과 일치)이면서 동시에 INADMISSIBLE(VTG — 현재 dynamic band/tick
> 위반)일 수 있다. 두 gate 독립. ADR §12 line 309 verbatim: "Rounding that changes price, quantity, direction, risk,
> or authorized economic effect creates a new broker-request shape and requires a new exact decision and any affected
> approval, capacity, authority, capability, and proof artifacts." ⇒ shape 변경 시 **새 candidate command(ioc) AND 새
> admissibility decision(VTG) 둘 다** 필요. 코드 실측 seam: ioc `OrderConformanceProof`가 VTG
> `venue_admissibility_decision_digest`(`records.py:414`)를 binding하되 admissibility를 평가하지 않음(#14 §0.4 line
> 139-141 "IOC는 Order Admissibility Decision을 proof에 digest scalar로 주입 소비하되 admissibility를 평가하지
> 않는다"). **리뷰어 공격 지점(§10.2)**: "ioc와 VTG가 price/qty를 둘 다 검사 = 중복" — 반론: 판정 대상이 다르다
> (intent-fidelity vs venue-admissibility); §12 line 311 "Broker-side validation is defense in depth"의 다층 방어.

> **핵심 판정 (b) — brokercap ceiling ≠ VTG admissibility(경계 판정·코드 실측)**: brokercap(ADR-002-004)은 broker가
> **무엇을 할 수 있나**(evidenced capability·assurance level·`MARKET_INSTRUMENT_CONSTRAINTS` `brokercap/vocabulary.py:86`)를
> 소유하고, VTG는 그 **ceiling 내부에서 이 exact order가 지금 admissible한가**를 판정한다. ADR §13 line 323 verbatim:
> "``BEST_EFFORT``, ``UNAVAILABLE``, expired, contradictory, or insufficiently evidenced capability cannot be promoted
> by the Gate." + VTG-INV-006 line 169-171 "The active Broker Capability Profile may reduce or prohibit scope. It never
> proves current venue state and cannot expand policy, authorization, capacity, or Hard Safety Envelope limits." ⇒ VTG는
> brokercap version/digest를 **ceiling scalar로 소비**(reduce-only 방향)·**promote 불가**. **리뷰어 공격 지점
> (§10.2)**: "VTG가 broker constraint(§13)를 다루니 brokercap과 중복" — 반론: brokercap=capability semantics(broker
> CAN), VTG=current venue admissibility(venue ALLOWS now); VTG는 semantics 재저작 안 하고 ceiling으로만 소비.
> **broker-agnostic 준수**: §13 broker 제약은 capability-class 언어로만 표현(KIS 등 특정 broker 값 부재).

> **핵심 판정 (c) — acyclic seam(정확형)**: ioc↔VTG는 **양방향 digest 참조**이나 **import cycle 부재**다.
> artifact-level dataflow: ioc candidate `CanonicalBrokerCommand` → VTG `OrderAdmissibilityDecision`(candidate digest
> 소비) → ioc `OrderConformanceProof`(decision digest 소비). 각 단계가 **이전 아티팩트의 digest만** 참조하는
> append-only 순서라 순환 없음. package-level: ioc는 VTG import 안 함(digest scalar 소비)·VTG는 ioc import 안 함
> (candidate digest scalar 소비) ⇒ **양방향 sibling edge 0**. #14 ioc가 "ioc↛venue"(#14 §3.4 line 540)를 이미
> 확정했으므로 VTG↛ioc만 본 계약이 추가 확정.

---

## 4. 불변식

모두 frozen 모델 구성-불변식(구성 실패) 또는 순수 술어(property)로 실현한다. **앵커는 VTG-INV-001..014(§6)·
VTG-AC-001..012(§27)·§-clause·SAFE-###**이며 **새 시리즈를 창작하지 않는다**(§0.4f). **fail-closed discipline**:
미증명/결측/None/stale/unknown/unenumerated/conflicting에 대한 술어는 절대 vacuous permissive/ADMISSIBLE가 되지
않으며, ADMISSIBLE 자격은 *양성 증명*을 요구하고, 각 가드에 **both-ways canary**(가드 발화 + 정당 통과 미차단)를 붙인다.

### 4.1 exact admissibility 중앙 불변식 (core — ADR §14; VTG-INV-001/004; VTG-AC-006)

**중앙 결정**: `OrderAdmissibilityDecision.result = ADMISSIBLE`는 §14 line 331-341 전 constraint predicate가 exact
shape·phase·account·source-continuity에 대해 **양성 통과**할 때만 발행된다. VTG-INV-001 line 149-151 verbatim: "No
broker-directed action is eligible for transmission without an exact Order Admissibility Decision for its complete
order shape and scope." 실현(구조적):

1. **permissive 기본값 부재**: 전 required predicate가 양성일 때만 ADMISSIBLE. 하나라도 fail/unknown/missing ⇒
   INADMISSIBLE/UNKNOWN(§8 line 245 "Missing policy coverage, unsupported enum, ambiguous precedence, unapproved
   source, or unknown materiality produces ``UNKNOWN`` or ``INADMISSIBLE``, never a permissive default"). "assume
   -admissible" 경로 부재(#6 fail-open 교훈).
2. **truthy-sentinel 봉인(§4.7)**: `OrderAdmissibilityResult.__bool__ ⇒ TypeError` — `if result:`이 INADMISSIBLE/
   UNKNOWN/**RESTRICTED_PROTECTIVE_ONLY**를 truthy로 오독하는 fail-open 차단. 소비 게이트 `result is
   OrderAdmissibilityResult.ADMISSIBLE`.
3. **exact binding(§16 line 363)**: decision id/digest는 proposal·approval·intent·candidate command·capacity·
   authority·capability·Commit Proof·egress 전 단계에 **동일 identity로** binding; mutation은 새 chain(VTG-INV-004
   line 161-163 "mutation requires a new chain").

**canary(both-ways)**: (a) 한 predicate fail·unknown phase·missing source ⇒ INADMISSIBLE/UNKNOWN(가드 발화;
VTG-AC-006); (b) 전 predicate 양성·exact binding 완비 ⇒ ADMISSIBLE(양성 side — 정당 order를 막지 않음). **∅ 양방향**:
빈 required-predicate set은 "nothing to check" 아님 — policy 최소 constraint set(§8)이 강제되므로 빈 set ⇒ 불완전(§4.7).

### 4.2 tradability-not-inferred 중앙 불변식 (core+predicate — ADR §10/§11; VTG-INV-002; VTG-AC-001/002)

**중앙 결정**: `session_phase_admits`(§5.1)·`tradability_conflict_unknown`(§6.1)은 calendar/quote/trade/connectivity
/login/health/absence로부터 tradability를 **추론하지 않는다**. VTG-INV-002 line 153-155 verbatim: "Calendar time,
quote flow, recent trades, connectivity, login, broker health, or absence of a restriction event never proves
order-specific tradability." 실현:

1. **관측 phase-token 검증(§10 line 269)**: observed phase ∉ policy admitting-set(exact action) 또는 unknown token ⇒
   restrictive; scheduled time만으로 phase 증명 금지(unscheduled closure/delayed open/auction extension/volatility
   interruption/halt/suspension/incident credible 시).
2. **conflict ⇒ UNKNOWN(§10 line 275)**: 상충 venue/broker/quote/calendar 관측 ⇒ UNKNOWN(policy-defined resolution
   전까지); "majority or newest-arrival selection is not automatically authoritative".
3. **observed OPEN/RESUMED = input(§10 line 275)**: source state는 입력이지 permission 아님.

**canary(both-ways)**: (a) unenumerated phase·상충 관측·quote-implies-tradable 시도 ⇒ restrictive/UNKNOWN(가드 발화;
VTG-AC-001/002); (b) policy admitting-set 내 phase·무상충 관측 ⇒ 통과(양성 side). **집합 양방향**: unknown token 탈출
검사 + spurious admitting(다른 action의 phase) 검사.

### 4.3 constraint-generation fencing 중앙 불변식 (core+predicate — ADR §17/§18; VTG-INV-008/010; VTG-AC-007)

**중앙 결정**: `stale_decision_rejected_at_egress`·`egress_currentness_active`(§6.3)는 current Constraint Generation을
**active하게** 확립하지 못하면 deny. VTG-INV-010 line 185-187 verbatim: "No new-risk broker byte is sent unless the
exact decision and current policy, generation, phase, tradability, broker capability, age, scope, and invalidation
status are positively established at the irreversible boundary." 실현:

1. **좌표 non-collapse(§0.4e canary)**: `constraint_generation`을 `policy_generation` 등 다른 generation 좌표로
   대체해도 fence 불성립(authority `predicates.py` "substituting one coordinate's value for another never satisfies a
   fence" 선례 상속).
2. **active currentness(§17 line 394)**: "Cached permissive state, TTL, schedule, heartbeat, service health, broker
   connectivity, last-known generation, eventual consistency, or absence of a halt/restriction event SHALL NOT
   establish currentness." `current_actively_established is not True ⇒ reject`. `compare_order`로 older-generation
   reject(§3.2).
3. **material change fences future(§18 line 404)**: material constraint change ⇒ newer restrictive generation ⇒ 영향
   dependency closure 전부 invalidate(§4.5); 단 economic effect는 불소멸(§4.4).

**canary(both-ways)**: (a) older generation·좌표 치환·`current_actively_established=None`·cache-implies-current ⇒
reject(가드 발화; VTG-AC-007); (b) current·actively-established·verified ⇒ 통과(양성 side).

### 4.4 economic-effect-outlives-artifacts 중앙 불변식 (core+predicate — ADR §18; VTG-INV-009/012)

**중앙 결정**: decision/policy/session/borrow/margin/constraint expiry·invalidation은 order/fill/exposure/settlement
obligation/UNKNOWN state/capacity commitment를 **소멸시키지 않는다**. VTG-INV-009 line 181-183 verbatim: "Decision,
policy, session, borrow, margin, or constraint expiry/invalidation never expires orders, fills, exposure, settlement
obligations, UNKNOWN state, or capacity commitments." + VTG-INV-012 line 193-195 "Where constraint uncertainty can
hide an existing or potentially-live effect, its worst credible effect remains capacity-consuming and cannot create
permission." 실현:

1. **artifact expiry ≠ economic release(§18 line 414)**: "Constraint expiry or invalidation never expires an order,
   fill, exposure, UNKNOWN state, settlement obligation, or capacity commitment already capable of economic effect."
   ⇒ decision expiry는 future new-risk 사용만 제한·capacity release는 rcl only(§3.5).
2. **UNKNOWN consumes conservatively(VTG-INV-012)**: constraint uncertainty가 potentially-live effect를 숨길 수 있으면
   worst credible effect는 capacity-consuming 유지·permission 생성 안 함(§19 line 424).

**canary(both-ways)**: (a) decision expiry로 capacity release 시도·UNKNOWN을 headroom으로 전환 시도 ⇒ 차단(가드
발화); (b) fresh decision + 정당 chain ⇒ 새 admissibility(양성 side, VTG 밖 rcl). **∅ 양방향**: UNKNOWN + available
capacity ⇒ 여전히 차단(offset/release 금지).

### 4.5 continuous-invalidation 중앙 불변식 (core+predicate — ADR §18; VTG-INV-008; VTG-AC-007)

**중앙 결정**: `material_change_closure`(§5.4 보조)는 §18 line 404-410 material change 집합 중 하나라도 발생 시 영향
dependency closure를 계산해 **approval/authority/egress 전 invalidate**. VTG-INV-008 line 177-179 verbatim: "A
material constraint change fences affected unconsumed decisions and downstream permission before future new-risk
send." 실현:

1. **material change 폐포(§18 line 404-410)**: unscheduled closure/halt/suspension·listing/contract/tick/lot/band/
   order-type change·account/borrow/margin/settlement change·broker capability degradation·source correction/
   discontinuity → reachability 폐포(§5.4). **§5.8 line 139 "Unknown materiality is material"** — 미상 materiality ⇒
   material로 처리(fail-closed).
2. **invalidation reach(§18 line 412)**: "Invalidation SHALL reach approval, authority issuance, unconsumed
   capabilities, and every final egress within approved bounds. Failure to prove complete propagation expands
   containment to the complete possibly affected scope." — propagation 미증명 ⇒ containment 확장.
3. **empty change ⇒ {trigger}(§4.7)**: 빈 change-set ⇒ 최소 폐포(trigger 자기 포함); unknown edge ⇒ 확장.

**canary(both-ways)**: (a) band change·halt·newer generation ⇒ 영향 decision 폐포에 포함(가드 발화; VTG-AC-007);
(b) 무관 무변경 ⇒ 폐포 밖(양성 side, max-age 내). **양방향 집합**: 탈출(under-invalidate) + spurious(over-invalidate).

### 4.6 gate-has-no-authority + reopen-non-revival 불변식 (predicate — ADR §7/§22; VTG-INV-011/013; VTG-AC-011/012)

**중앙 결정**: `gate_authority_separated`(§6.7, all-false)·`reopen_revives_nothing`(§6.8, 무조건 True). VTG-INV-011
line 189-191 verbatim: "Constraint evaluation cannot approve, mutate capacity, issue authority, classify protection,
transmit, clear HALT, or re-arm." VTG-INV-013 line 197-199 verbatim: "Venue reopen, halt release, account
restoration, reconnect, restart, failover, clock recovery, or constraint-service recovery cannot revive a previous
decision or authority." 실현:

1. **all-false authority(VTG-INV-011)**: `VenueGateAuthorityEffect` 전 필드 `False`. ioc `AllFalseConstructionAuthority`
   (클래스 `_base.py:54`·`model_validator` `:74` — v1.1 M3) 동형 — 어느 필드도 `True` 구성 불가 + defence-in-depth 술어(§6.7).
2. **reopen ↛ revive(§22 line 473)**: "Venue reopen, halt release, next-session arrival, broker reconnect, margin
   restoration, account unlock, borrow restoration, replay match, or successful reconciliation is a recovery input
   only. It cannot move live scope to active, reactivate an old decision, or create authority automatically." —
   `reopen_revives_nothing`은 revival path의 구조적 부재를 문서화(무조건 True; authority `recovery_generation_revives_
   nothing` `predicates.py:787` replica pattern).
3. **no credential/route(§7 line 223)**: "The Venue Constraint Gate SHALL NOT hold a usable live broker credential,
   signer, session, or broker-order route merely because it queries broker or venue constraints."

**canary(both-ways)**: (a) gate가 capacity mutate/authority issue/transmit 시도·reopen 후 old decision revive 시도 ⇒
차단(가드 발화; VTG-AC-011/012); (b) fresh decision + governed chain ⇒ 새 admissibility(양성 side, VTG 밖).
**all-false 회귀**: `VenueGateAuthorityEffect`의 어느 필드도 `True` 구성 불가 assert(ioc 동형).

### 4.7 ∅-공허 fail-closed + truthy-sentinel 소비 계약 (양방향 명시 — #10/#12 ∅-void·#14 M1 truthy-sentinel 교훈)

**(가) ∅-공허 양방향**: 빈 입력의 **모든 방향**을 명문화한다. VTG 금지 동사(§6·VTG-INV): **infer-tradability**
(VTG-INV-002)·**assume-exit-executable**(VTG-INV-003·§1 line 25)·**promote-capability**(VTG-INV-006)·**bypass-via
-protective-label**(VTG-INV-007·§19 line 173)·**mutate/release-capacity**(VTG-INV-011)·**expire-economic-effect**
(VTG-INV-009)·**offset-UNKNOWN-into-permission**(VTG-INV-012)·**infer-currentness-from-cache/absence**(VTG-INV-010·
§17 line 394)·**revive-on-reopen**(VTG-INV-013)·**permissive-rounding/substitution**(§12 line 299·§14 line 343)·
**calendar-proves-open**(§10 line 269·§25.1 line 527).

| 빈 입력 | 금지 방향(vacuous permissive 차단) | 허용 방향(양성 side) | 근거 |
|---|---|---|---|
| **관측 phase-token ∉ policy admitting-set** | unenumerated/unknown phase ⇒ INADMISSIBLE/UNKNOWN | policy admitting-set 내 phase ⇒ admits(exact action) | §8 line 245·VTG-AC-001·VTG-INV-002 |
| **빈 required-constraint set** | 빈 set ⇒ "nothing to check" 아님 ⇒ policy 최소 constraint 미충족 ⇒ 불완전 | policy 최소 constraint 완비·전 양성 ⇒ ADMISSIBLE 후보 | §8 line 229-241 minimum policy declaration |
| **빈 dependency graph의 material-change 폐포** | 빈 change ⇒ 최소 폐포={trigger}·unknown edge⇒확장 | 완비 그래프 ⇒ 정확 도달성 폐포 | §18 line 412·§5.8 "Unknown materiality is material" |
| **missing/empty required_authority_scope** | missing/empty scope ⇒ UNKNOWN/INADMISSIBLE(never wildcard) | 명시 scope ⇒ 정확 admissibility | ioc `records.py:374` 동형·§4.7 |
| **UNKNOWN result + available capacity** | UNKNOWN + capacity ⇒ 여전히 차단(offset/release 금지) | 전 predicate ADMISSIBLE + current binding ⇒ ADMISSIBLE | §19 line 424·VTG-INV-012 |
| **reopen/reconnect 후 old decision 참조** | reopen/reconnect ⇒ revive 안 됨 | fresh decision + governed chain ⇒ 새 admissibility | §22 line 473·VTG-INV-013 |

**양방향 규율**: 각 빈-입력 가드는 (a) 금지 방향(가드 발화 canary)과 (b) 허용 방향(정당 통과 canary)을 **둘 다**
property로 검증(§7). vacuous-ADMISSIBLE(안전 위반)도 vacuous-INADMISSIBLE(가용성 위반·정당 order 차단)도 결함이다
(#12 both-ways 교훈). **양방향 집합 비교(#14 MAJOR-1 교훈)**: `material_change_closure`(§5.4)·`exact_instrument_route_
bound`(§5.2)의 집합 비교는 **양방향** — 결측(dependent 탈출·routing 필드 누락)과 잉여/치환(spurious node·alias
치환) 모두 검사. **과대 주장 금지**: `extra="forbid"`는 모델 필드 unknown/duplicate만 차단하며 constraint/routing
튜플의 excess/치환은 구조 술어가 잡는다고 정확히 서술(§2 — extra="forbid"가 튜플 excess를 막는다고 주장하지 않음).

**(나) truthy-sentinel 소비 계약(#14 M1 교훈을 처음부터 — 임계)**: bool 아닌 안전 술어의 소비를 명문화한다.

- **`OrderAdmissibilityResult` 반환 술어**(decision 발행): `ADMISSIBLE`/`RESTRICTED_PROTECTIVE_ONLY`/`INADMISSIBLE`/
  `UNKNOWN`는 **모두 non-empty StrEnum**이라 `if result:`·`if result == True:`면 `INADMISSIBLE`/`UNKNOWN`뿐 아니라
  **`RESTRICTED_PROTECTIVE_ONLY`까지 truthy로 fail-open**(catastrophic — protective-only를 full-permission으로 오독;
  ioc 3-값보다 위험). ⇒ **구조적 봉인(#14 M1을 처음부터)**: `OrderAdmissibilityResult`는 **`__bool__`가 `TypeError`를
  raise하는 truthy-불가 타입**(ioc `ConformanceResult.__bool__` `vocabulary.py:63` 동형). 소비 게이트 계약:
  `result is OrderAdmissibilityResult.ADMISSIBLE`(ordinary 통과)만; `RESTRICTED_PROTECTIVE_ONLY`는 별도 protective
  검증 게이트(§6.5) 통과 시에만. bare bool 반환 금지.
- **`TradabilityState` 반환 술어**: non-empty StrEnum — 동일 `__bool__ ⇒ TypeError` 봉인. 소비 게이트 `state is
  TradabilityState.TRADABLE`. §11 line 291 "A global ``tradable=true`` field is insufficient" — 단일 bool 금지.
- **`SessionPhase`(주입 opaque token)**: enum 아님(policy-defined open set·§2.2(3)) — truthy 봉인 대신 **membership
  검증**(observed ∈ policy admitting-set)이 fail-closed 메커니즘; token 자체는 str이라 `if phase:`이 의미 없음(비어
  있지 않은 token은 항상 truthy) — 그래서 phase는 **절대 truthy로 소비하지 않고** 항상 admitting-set membership으로만
  판정(§5.1). 이 구분이 §2.2(3) 판정의 핵심.
- **`bool|None` 반환 술어**(`exit_not_assumed_admissible`·`gate_authority_separated`·`egress_currentness_active` 등):
  `None`(미판정)은 falsy지만 **`is True` 명시 비교**로 소비(`is not True ⇒ reject`) — spg `semantic_validation`
  (`predicates.py:466` `is not True⇒reject`)·protective `dominating_halt_or_incident`(`predicates.py:395` `is False`)
  동형. `if x:` truthy 금지.
- **`reopen_revives_nothing`**(무조건 `True` 반환): non-revival을 **문서화**하는 술어라 `True`가 안전값 — 단 소비자는
  여전히 `is True`로 소비(계약 일관). authority replica(`predicates.py:787` `del … return True`) 동형.
- **canary**: 각 술어에 (i) 안전값 아닌 반환(`INADMISSIBLE`/`RESTRICTED_PROTECTIVE_ONLY`/`NOT_TRADABLE`/`None`/`False`)이
  truthy/falsy edge에서 **게이트가 reject함을 assert**, (ii) 안전값(`ADMISSIBLE`/`TRADABLE`/`True`)만 통과 assert,
  (iii) **구조 봉인 회귀**: `bool(r)`이 `OrderAdmissibilityResult`·`TradabilityState` 각 값에 대해 `TypeError`를
  raise함을 assert(+`is` 비교는 정상 양성측). 이 계약은 §5·§6 전 술어에 부착되고 §7 property·seam test로 회귀.

---

## 5. core 술어 — session-phase/instrument-route/order-shape/decision-binding (VTG-EV-001/003/004/006 substrate, L1 슬라이스)

**핵심 난제**: venue-constraint admissibility를 **순수 함수**로 저작하되, (i) policy·phase-set·tick/lot/band·source·
age bound를 **주입 판정/파라미터**로 두어 하드코딩·registry를 배제하고(§8), (ii) fail-closed(§4)를 **구조로** 지키며
(permissive 기본·vacuous 부재·truthy-sentinel 봉합), (iii) 형제 판정(ioc conformance·brokercap capability·capsule
CII·time)을 **소비**하되 재저작하지 않는다(§3.5). 각 술어는 §1 core 4행(VTG-EV-001/003/004/006)의 L1 슬라이스를
저작하나 **어떤 VTG-EV도 닫지 않는다**(`/3`·+Broker/+Security 잔여).

### 5.1 session_phase_admits (§10; VTG-EV-001 substrate, core L1 슬라이스 — 중심 fail-closed 술어)

`session_phase_admits(observed_phase: str | None, action: ActionClass, snapshot: VenueConstraintSnapshot, policy:
VenueConstraintPolicy) -> OrderAdmissibilityResult`:

- **admitting-set membership(§10 line 273)**: observed phase-token이 policy가 이 exact action에 대해 선언한
  **admitting phase-set**에 속할 때만 통과 후보. ADR §10 line 273 verbatim: "An order approved for continuous trading
  cannot be reused in an opening auction, volatility auction, reopening auction, closing auction, after-hours session,
  or next trading day unless the policy proves identical semantics and a fresh exact decision is issued." ⇒ phase A의
  decision을 phase B에서 재사용 불가.
- **unenumerated/unknown ⇒ restrictive(§8 line 245·§10 line 269)**: observed_phase가 `None`·policy known-set 부재·
  scheduled-time만으로 추론된 경우 ⇒ INADMISSIBLE/UNKNOWN(불허). VTG-INV-002 앵커 — calendar/quote ↛ phase.
- **scheduled-time not sole proof(§10 line 269)**: unscheduled closure/delayed open/auction extension/volatility
  interruption/halt/suspension/incident credible 시 scheduled phase 단독 사용 금지.
- **hardcoded enum 부재(§2.2(3))**: phase 이름은 주입 token; 술어는 policy admitting-set membership만 계산(숫자/문자열
  하드코딩 0).
- **canary(both-ways)**: (a) unenumerated phase·calendar-only phase·phase A decision을 phase B 재사용 ⇒ INADMISSIBLE/
  UNKNOWN(가드 발화; VTG-AC-001); (b) policy admitting-set 내 phase·fresh decision ⇒ ADMISSIBLE 후보(양성 side —
  정당 continuous-trading order를 막지 않음). **∅ 양방향**: 빈 admitting-set ⇒ 전 phase 불허(vacuous admit 아님).
- **미소유(§3.5)**: calendar-expectation phase 판정은 time.SessionContext 소유 — 이 술어는 **authoritative
  admissibility**만; time evidence는 주입.

### 5.2 exact_instrument_route_bound (§11; VTG-EV-003 substrate, core L1 슬라이스, +Security)

`exact_instrument_route_bound(decision: OrderAdmissibilityDecision, candidate_fields: InstrumentRouteFields) -> bool`:

- **canonical identity + 전 routing 필드(§11 line 281)**: canonical instrument identity·routing-relevant alias·venue
  listing·market segment·contract month·product type·currency·multiplier·expiration·exercise/assignment·settlement
  method·account mapping이 **전부 exact match**일 때만 `True`. 하나라도 mismatch/missing ⇒ `False`.
- **alias/substitute 거부(§27 AC-003 line 613)**: "Substitute symbol alias, market segment, contract month, account,
  environment, or broker route. Every mismatch must be rejected through final egress." — alias·default-account·
  "primary"-venue·front-month substitute ⇒ reject(ioc §10 alias-거부 `#14 §5` 동형 규율).
- **canary(both-ways)**: (a) symbol alias·contract-month/account/env/route 치환 ⇒ reject(가드 발화; VTG-AC-003);
  (b) 전 필드 exact match ⇒ 통과(양성 side). **양방향 집합**: 결측 routing 필드(under) + spurious alias(over) 둘 다.
- **미소유(§3.5)**: candidate command 구성은 ioc; 이 술어는 decision이 binding한 identity/route가 candidate와 exact
  일치하는지만.

### 5.3 order_shape_admissible (§12; VTG-EV-004 substrate, core L1 슬라이스 — ioc 경계)

`order_shape_admissible(shape: OrderShapeFields, constraints: VenueShapeConstraints) -> OrderAdmissibilityResult`:

- **permissive rounding 금지(§12 line 299)**: price representation/currency/unit/scale/sign/precision·static/dynamic
  price limits/collar/auction range·tick table/boundary·quantity unit/lot/min/max/step/notional/odd-lot/fractional·
  side/direction/position-effect/reduce-only·order-type/pricing-instruction/TIF/expiry/trigger/peg/routing·cancel/
  amend/replace restriction을 **permissive rounding·substitution 없이** 검증. 하나라도 위반 ⇒ INADMISSIBLE.
- **rounding ⇒ new shape(§12 line 309)**: shape를 바꾸는 rounding은 새 broker-request shape ⇒ 새 decision + 영향
  downstream 재실행(§3.5 핵심 판정 (a)). silent normalization/widening ⇒ INADMISSIBLE(VTG-AC-004 line 617 "Silent
  normalization or widening must fail").
- **tick/lot/band 값 주입(§2.1·§8)**: 모든 수치는 `constraints`(policy 주입); 하드코딩 0.
- **broker validation = defense in depth(§12 line 311)**: "Expected rejection does not authorize sending a known
  -invalid or unproven order." — broker가 reject할 것이라는 기대가 send 정당화 못 함.
- **ioc 경계(§3.5 핵심 판정 (a))**: 이 술어는 **venue-admissibility**(band/tick/lot 위반 여부)만; **intent-conformance**
  (command가 approved Intent에 부합하나)는 ioc §12 소유. 같은 필드·다른 판정.
- **canary(both-ways)**: (a) band 초과·invalid tick·odd-lot·unsupported order-type·silent rounding ⇒ INADMISSIBLE
  (가드 발화; VTG-AC-004); (b) 전 shape 필드 venue-valid ⇒ ADMISSIBLE 후보(양성 side).

### 5.4 decision_binding_exact + no_decision_union + material_change_closure (§14/§16/§18; VTG-EV-006 substrate, core L1, +Security)

`decision_binding_exact(chain: BindingChain) -> bool` · `no_decision_union(decisions: frozenset[...]) -> bool` ·
`material_change_closure(dep_graph: Mapping[str, frozenset[str]], change_triggers: frozenset[str], *, unproven:
Mapping[str, frozenset[str]] | None = None) -> frozenset[str]`:

- **canonical digest cover(§14 line 342)**: "The canonical digest SHALL cover all fields that can change the decision
  or economic effect." — decision digest가 전 decision-affecting 필드 포함(§2.3 covered-set).
- **no patch/union/widen(§14 line 343)**: "Decisions cannot be patched, partially refreshed, unioned, widened, or
  silently recomputed. Any material field change creates a new Snapshot or decision and repeats every affected
  downstream gate." — `no_decision_union`은 복수 decision을 union/widen하는 경로 부재를 assert.
- **exact binding chain(§16 line 363-373)**: decision id/digest가 proposal·approval·intent·candidate command·capacity
  ·authority·capability·Commit Proof·egress 전 단계에 동일 identity로 binding; 소비자는 missing/mismatched/stale/
  wrong-scope/superseded/invalidated/unverifiable binding ⇒ reject(§16 line 377). same-id/diff-bytes ⇒
  `classify_record_pair` `CRITICAL_CONFLICT`(§2.1).
- **material change 폐포(§18)**: `material_change_closure`는 change trigger에서 영향 dependency 도달성 폐포(iap
  `invalidation_closure` **동형 규율 — 로컬 저작·import 금지**, #17 §0.4d 상속: 순수 그래프 reachability·unknown edge
  ⇒ 확장·empty⇒{trigger}·proven-disconnect 제외). §5.8 line 139 "Unknown materiality is material" ⇒ 미상 ⇒ 포함.
- **canary(both-ways)**: (a) decision/capsule/approval/intent/candidate 한 필드 mutate·decision union 시도·material
  change 후 stale decision 사용 ⇒ reject(가드 발화; VTG-AC-006); (b) exact 일치 chain·무변경 window(max-age 내) ⇒
  통과(양성 side). **양방향 집합**: material change 탈출(under) + spurious invalidation(over).
- **공유 폐포 커널(#17 MINOR-5 상속)**: `material_change_closure`가 iap `invalidation_closure`(`iap/predicates.py`)·
  sbr `_reachability_closure`와 **동일 폐포 공리**(trigger∈closure·monotone·불확정 edge 확장·empty⇒{trigger}·proven
  -disconnect 제외)를 만족하므로 §7 하네스가 **공유 property 계약**으로 함께 회귀(코드가 아니라 규율을 DRY — import
  금지). 반환형은 reachability **집합**(iap 동형; sbr `obligation_graph_closed`의 bool과는 비동형).

---

## 6. predicate-only 술어 — conflict/account/currentness/exit/protective/common-mode/authority/reopen (VTG-EV-002/005/007/008/009/010/011/012 substrate, 최소 ≥ L2·닫지 않음)

이 8 술어는 predicate-only substrate다 — **어떤 VTG-EV도 닫지 않으며**(최소 ≥ L2·+Security 4·+Broker 4), L1
슬라이스는 **순수 술어 계약**만 저작하고 실 enforcement(active currentness·broker probe·margin query·common-mode
failure-domain·SoD·recovery workflow)는 EV-L2/L3 런타임·+Security/+Broker다.

### 6.1 tradability_conflict_unknown (§10; VTG-EV-002 substrate, predicate-only, 최소 EV-L2/3+Broker)

`tradability_conflict_unknown(observations: frozenset[SourceObservation], resolution: PolicyResolution | None) ->
OrderAdmissibilityResult`:

- **conflict ⇒ UNKNOWN(§10 line 275)**: 상충 venue/broker/quote/calendar 관측 ⇒ policy-defined resolution 전까지
  UNKNOWN; "majority or newest-arrival selection is not automatically authoritative." 다수결/최신-도착 자동 선택 금지.
- **quote/trade ↛ tradable(§25.2 line 531)**: "Market data can continue while order entry is halted, restricted,
  stale, or account-ineligible." — quote flow가 tradability 증명 못 함.
- **predicate-only 경계**: 실 conflict resolution·broker probe는 +Broker 런타임. L1은 "conflict ⇒ UNKNOWN·majority
  금지" 술어만.
- **canary(both-ways)**: (a) 상충 관측·majority 선택 시도·quote-implies-tradable ⇒ UNKNOWN(가드 발화; VTG-AC-002);
  (b) 무상충·policy resolution 통과 ⇒ 판정 가능(양성 side, +Broker 런타임).

### 6.2 account_constraint_conservative (§13; VTG-EV-005 substrate, predicate-only, 최소 EV-L2/3+Broker)

`account_constraint_conservative(facts: AccountMarginFacts, prior: AccountMarginFacts | None) -> bool`:

- **not inferred(§13 line 319)**: "Margin, buying power, borrow availability, or account eligibility is not inferred
  from a stale balance, a previous successful order, or the absence of a broker error." — stale balance/prior order/
  absence-of-error ⇒ headroom 생성 금지.
- **conflict conservative(§13 line 319·ADR-002-006)**: 상충 account/order/fill/position/margin/borrow/settlement
  evidence ⇒ conservative(recon 소비). post-trade finality(ADR-002-030): fill/FQP/flat/statement/scheduled-date/PTOL
  ↛ eligibility(§13 line 321); missing/stale ⇒ UNKNOWN/INADMISSIBLE.
- **미소유(§3.5)**: per-field confidence는 recon·finality는 ADR-002-030 — 이 술어는 "stale ↛ headroom" conservatism만.
- **canary(both-ways)**: (a) stale balance·prior-order·absence-of-error로 headroom 주장 ⇒ 차단(가드 발화; VTG-AC-005);
  (b) fresh corroborated facts ⇒ 통과(양성 side, +Broker).

### 6.3 egress_currentness_active + stale_decision_rejected_at_egress (§17; VTG-EV-007 substrate, predicate-only, 최소 EV-L2/3+Security)

`egress_currentness_active(current_actively_established: bool | None, request_generation: int | None,
current_generation: int | None) -> bool` · `stale_decision_rejected_at_egress(...) -> bool`:

- **active establish 요구(§17 line 383-394)**: final egress는 exact decision + current policy/generation/phase/
  tradability/broker-capability/age/scope/invalidation을 **능동 확립**해야 send; cache/TTL/schedule/heartbeat/health/
  connectivity/last-known/eventual-consistency/absence ↛ currentness ⇒ `current_actively_established is not True ⇒
  reject`.
- **send-race bound(§17 line 396)**: final currentness와 first broker byte 사이 race unprovable ⇒ potentially-live·전
  credible effect capacity-covered·blind retry 금지; "Missing ACK is not proof of non-acceptance. Cancel ACK is not
  Final Quantity Proof."
- **좌표 non-collapse(§4.3)**: `constraint_generation`을 다른 좌표로 대체 시 fence 불성립.
- **predicate-only 경계**: 실 active currentness는 ADR-002-024 Currentness Vector 런타임 +Security(§17 line 388). L1은
  순서 비교·active-establish 요구 술어만.
- **canary(both-ways)**: (a) cache-implies-current·older generation·race unprovable ⇒ reject/contain(가드 발화;
  VTG-AC-007); (b) actively-established·current·verified ⇒ 통과(양성 side).

### 6.4 exit_not_assumed_admissible (§11/§19; VTG-EV-008 substrate, predicate-only, 최소 EV-L2/3+Broker)

`exit_not_assumed_admissible(action: ActionClass, tradability: TradabilityState) -> bool`:

- **exit 독립 제약(VTG-INV-003 line 157)**: "Exit, reduce-only, cancel, replacement, and protective actions are
  independently constrained and may be ``INADMISSIBLE`` or ``UNKNOWN``." — exit/reduce-only/cancel/replace를 자동
  executable로 가정 금지.
- **reduce-only reversal 위험(§11 line 285·§25.4 line 539)**: "They can be unsupported, reverse exposure, cross zero,
  violate account/venue rules, or fail while protection is removed." — reduce-only가 reversal/zero-cross 가능.
- **no blind retry(§25.8 line 555)**: reject/missing-ACK 후 retry는 원 attempt가 accepted/partial 가능성으로 금지.
- **미소유(§3.5)**: Final Quantity Proof·broker 의미는 ADR-002-004(+Broker). L1은 "exit ↛ assumed-admissible" 술어만.
- **canary(both-ways)**: (a) exit/reduce-only/cancel을 admissible로 가정·blind retry ⇒ 차단(가드 발화; VTG-AC-008);
  (b) exit action의 exact admissibility 양성 증명 ⇒ 통과(양성 side, +Broker).

### 6.5 protective_label_no_bypass (§19; VTG-EV-009 substrate, predicate-only, 최소 EV-L2/3+Broker)

`protective_label_no_bypass(label_is_protective: bool | None, exact_admissibility: OrderAdmissibilityResult,
separate_protective_authority: bool | None, intermediate_effects_capacity_covered: bool | None) -> bool`:

- **label ↛ bypass(VTG-INV-007 line 173-175)**: "Protective or containment use requires exact current admissibility,
  separate protective classification and authority, and conservative capacity for every credible intermediate
  effect." — protective label만으로 constraint bypass 금지.
- **RESTRICTED_PROTECTIVE_ONLY 경계(§1 line 29·§19 line 426)**: protective action은 (i) exact current admissibility
  (RESTRICTED_PROTECTIVE_ONLY 포함) + (ii) 별도 protective classification/authority(protective 소유) + (iii) 전
  credible intermediate/reversal effect capacity-covered(rcl 소유) 셋 다 양성일 때만. "Priority is not reserved
  protective capacity."
- **partition-lease(§19 line 431)**: Safety Control Plane partition 시 degraded Protective Lease의 pre-proven scope·
  staleness tolerance 내에서만 overlap-first/add-only protective 가능(ADR-002-001 §9 소유). cancellation-involving
  replacement는 partition 중 inadmissible.
- **미소유(§3.5)**: classification/replacement은 protective(ADR-002-011)·capacity는 rcl. L1은 "label ↛ bypass·3조건
  요구" 술어만.
- **canary(both-ways)**: (a) protective label로 INADMISSIBLE bypass·separate authority 없이 진행 ⇒ 차단(가드 발화;
  VTG-AC-009); (b) 3조건 전수 양성 ⇒ RESTRICTED_PROTECTIVE_ONLY 경로 허용(양성 side, +Broker 런타임).

### 6.6 common_mode_reduces_scope + unknown_continuity_invalidates (§9/§15; VTG-EV-010 substrate, predicate-only, 최소 EV-L2/3+Security)

`common_mode_reduces_scope(shared_dependencies: frozenset[str], independent_corroboration: bool | None) -> bool` ·
`unknown_continuity_invalidates(continuity: SourceContinuity) -> bool`:

- **shared ≠ independent(§15 line 353)**: "Two services that consume the same corrupted dependency do not provide
  independent corroboration." — shared venue feed/broker endpoint/calendar/mapping/margin lib/cache/parser/credential/
  network/region/deployment/rule-engine는 common-mode ⇒ independence 불성립.
- **corroboration 부재 ⇒ scope 축소(§15 line 355)**: SAFE-034 requires separate residual-risk approval·additional
  checks·explicit failure-domain disclosure·reduced/prohibited live scope; proposer/Gate/adapter/owner는 self-except
  불가.
- **unknown continuity ⇒ invalidate(§9 line 263)**: restart/reconnect/endpoint-or-credential substitution/sequence
  reset/rollback/failover/missed-page/stale-cache/unverifiable continuity ⇒ 새 continuity identity 또는 explicit
  gap; unknown continuity ⇒ 영향 future decision 무효.
- **predicate-only 경계**: 실 failure-domain allocation·security-boundary는 +Security 런타임(§27 q10). L1은 "shared ↛
  independent·unknown continuity ⇒ invalidate" 술어만.
- **canary(both-ways)**: (a) shared dependency를 independent corroboration으로 주장·unknown continuity 무시 ⇒ scope
  축소/invalidate(가드 발화; VTG-AC-010); (b) 진정 disjoint failure-domain corroboration ⇒ 통과(양성 side, +Security).

### 6.7 gate_authority_separated (§7; VTG-EV-011 substrate, predicate-only, 최소 EV-L2/3+Security, broker-cap N/A)

`gate_authority_separated(effect: VenueGateAuthorityEffect, holds_live_credential: bool | None) -> bool`:

- **all-false authority(VTG-INV-011 line 189)**: `VenueGateAuthorityEffect` 전 필드 `False`(approves·mutates_capacity·
  issues_authority·classifies_protection·transmits·clears_halt·rearms). ioc `AllFalseConstructionAuthority`(`_base.py:74`)
  동형 — 구성-불변식(어느 필드도 `True` 불가) + defence-in-depth 술어(`model_construct` escape hatch 대비, ioc
  `_base.py:66-70` 동형).
- **no credential/route(§7 line 223)**: gate는 usable live broker credential/signer/session/broker-order route 미보유.
  combined read/trade credential은 ADR-002-013 confinement(§24 line 521) — order endpoint deny-by-default.
- **bypass 저항(§27 AC-011 line 645)**: direct capacity mutation·authority issuance·protective self-label·human
  override·stale decision replay·direct broker route·portal fallback 전부 denied+alerted.
- **미소유(§3.5)**: 실 SoD·bypass path·common-effective-control은 +Security 런타임. L1은 all-false·no-credential 술어만.
- **canary(both-ways)**: (a) gate가 capacity mutate/authority issue/protective classify/transmit/clear-HALT/re-arm
  시도·live credential 보유 주장 ⇒ 차단(가드 발화; VTG-AC-011); (b) admissibility fact 생산(권한 없음) ⇒ 허용(양성
  side). **all-false 회귀**: `VenueGateAuthorityEffect` 어느 필드도 `True` 구성 불가 assert(ioc 동형).

### 6.8 reopen_revives_nothing (§22; VTG-EV-012 substrate, predicate-only, 최소 EV-L2/3+Security)

`reopen_revives_nothing(*, venue_reopened, halt_released, reconnected, restarted, failed_over, clock_recovered,
constraint_service_recovered, prior_decision) -> bool`:

- **무조건 `True`(§22 line 473·VTG-INV-013 line 197)**: reopen/halt-release/next-session/reconnect/margin-restoration/
  account-unlock/borrow-restoration/replay-match/reconciliation은 recovery **input only** — old decision/authority
  revive 불가. 모델은 revival path를 제공하지 않으며 이 술어가 그 부재를 문서화·고정(authority
  `recovery_generation_revives_nothing` `predicates.py:787` replica pattern — `del … return True`).
- **fresh decision + chain 필수(§22 line 471·§1 line 37)**: "A fresh decision and the complete governed authorization
  chain are required. No automatic re-arm is permitted." — recovery는 sbr/ADR-002-017 workflow 통해 fresh chain.
- **미소유(§3.5)**: recovery workflow는 sbr; VTG decision은 sbr recovery obligation 입력(§3.4). L1은 "reopen ↛ revive"
  술어만.
- **canary(both-ways)**: (i) 7 revival vector 각각 True 주입해도 `reopen_revives_nothing`은 `True`(revive 없음) assert;
  (ii) **구조 회귀**: 모델에 reopen → old-decision-restoration 매핑 operation이 **부재**함을 assert(authority replica
  동형). 양성 side는 VTG 밖(fresh decision chain).

---

## 7. property-test 하네스 타깃

§1 분류에 정렬한다. **닫는 VTG-EV = 0건** — 어떤 test-target도 VTG-EV closure·acceptance를 주장하지 않는다(규율
태그 부착). 각 술어에 **both-ways canary**(§4·§5·§6)·**truthy-sentinel canary**(§4.7)·**fixture clean-vs-illegal
정합**(#8 교훈)을 건다.

- **core(L1 슬라이스, VTG-EV-001/003/004/006 substrate)**: `session_phase_admits`(§5.1); `exact_instrument_route_bound`
  (§5.2); `order_shape_admissible`(§5.3); `decision_binding_exact`+`no_decision_union`+`material_change_closure`(§5.4).
  **session-phase property(노다지)**: hypothesis로 무작위 phase-token + policy admitting-set + action 생성 → set 내
  ⇒ admit 후보·set 외/unknown ⇒ restrictive·phase A decision을 phase B 재사용 불가·빈 admitting-set ⇒ 전 불허(both-
  ways). **order-shape property**: 무작위 price/tick/lot/qty → band 위반/invalid-tick/odd-lot/silent-rounding ⇒
  INADMISSIBLE·전 venue-valid ⇒ ADMISSIBLE 후보. **material-change-closure property(노다지)**: 무작위 dependency
  그래프 + change trigger → 폐포가 영향 dependent 전부 포함(no escape) + unknown edge ⇒ 확장 + proven-disconnect
  미포함(both-ways) + empty⇒{trigger}(iap `invalidation_closure`·sbr `_reachability_closure` **공유 폐포 property
  계약**으로 함께 회귀 — #17 MINOR-5 상속).
- **predicate-only(VTG-EV-002/005/007/008/009/010/011/012 substrate, EV 미주장)**: `tradability_conflict_unknown`
  (§6.1); `account_constraint_conservative`(§6.2); `egress_currentness_active`+`stale_decision_rejected_at_egress`
  (§6.3, `compare_order` 기반 순서); `exit_not_assumed_admissible`(§6.4); `protective_label_no_bypass`(§6.5);
  `common_mode_reduces_scope`+`unknown_continuity_invalidates`(§6.6); `gate_authority_separated`(§6.7, all-false
  회귀); `reopen_revives_nothing`(§6.8, 무조건 True·revival-path 부재 회귀).
- **truthy-sentinel 회귀(§4.7, MANDATED)**: `OrderAdmissibilityResult`·`TradabilityState` 반환 술어에 대해 (i)
  `INADMISSIBLE`/`RESTRICTED_PROTECTIVE_ONLY`/`UNKNOWN`/`NOT_TRADABLE`가 truthy임을 assert, (ii) `is ADMISSIBLE`/`is
  TRADABLE` 게이트가 그 외를 reject함을 assert(`if result:` 대비 회귀 — 특히 `RESTRICTED_PROTECTIVE_ONLY` truthy
  fail-open 방지), (iii) **구조 봉인 회귀**: `bool(OrderAdmissibilityResult.*)`·`bool(TradabilityState.*)`이
  `TypeError`를 raise함을 assert. **이 회귀가 #14 M1 truthy-sentinel 교훈의 처음부터 능동 봉합**이다(ioc
  `ConformanceResult` `vocabulary.py:63` 동형·4-값이라 더 임계). **SessionPhase는 enum 아님** — truthy 봉인 대신
  membership 회귀(observed ∉ admitting-set ⇒ restrictive; phase를 truthy로 소비하는 코드 부재 assert).
- **seam cross-check(test-only, MANDATED §3.4)**: `test_seam_ioc`(VTG decision digest = ioc `OrderConformanceProof.
  venue_admissibility_decision_digest` `records.py:414`·VTG가 ioc candidate command digest 소비·양방향 acyclic)·
  `test_seam_iap`(VTG snapshot/decision digest = iap `records.py:256-257` 소비·admissibility≠approval)·`test_seam_capsule`
  (VTG 3-Ref = capsule `capsule.py:242-244`·shape 정합 `capsule.py:130-150`)·`test_seam_brokercap`(VTG가 brokercap
  version/digest ceiling 소비·promote 불가)·`test_seam_spg`(VTG policy가 spg `VENUE_CONSTRAINT_POLICY` `vocabulary.py:205`
  activation 소비)·`test_seam_time`(VTG가 time.SessionContext evidence 소비·authoritative phase 별도 생산·REUSE 아님).
  테스트 import는 package closure에 불계상(§7.1).
- **∅-공허 회귀(양방향, §4.7)**: unenumerated phase ⇒ restrictive; 빈 constraint set ⇒ 불완전; 빈 dependency 그래프
  ⇒ 최소 폐포·unknown⇒확장; UNKNOWN+capacity ⇒ 차단; missing scope ⇒ never-wildcard; **동시에** 각 완비 입력의 정당
  통과 canary.

### 7.1 import-closure 검증 테스트 (설계 #4 §7.1·#12-#17 §7.1 상속·allowlist 형식)

`import tos.venue` 후 `sys.modules` closure를 **allowlist로 검증**: `tos.* closure ⊆ {tos.canonical, tos.ordering,
tos.venue}`(sbr `__init__.py:47-48` 선례 "any future sibling are all excluded by the §7.1 allowlist closure test" —
denylist 열거가 아니라 subset 검증이라 **미래 신규 형제·카운트 오차 자동 배제**). 추가로 금지 집합 부재 assert:
`shared.config`·`os.environ` 흔적·`numpy`/`pandas`/`yaml`·**17 형제 tos 패키지 전부**(afg·are·authority·brokercap·
capsule·dsl·evidence·iap·ioc·liveauth·orthostate·protective·rcl·recon·sbr·spg·time — **`tos.afg`·`tos.sbr` 명시
포함**, #17 MAJOR-1 교훈) 부재; **`tos.canonical`·`tos.ordering`만 존재 허용**(sibling edge 0 — §0.4c). required
check(`tos-firewall`, `tools/tos_firewall_check.py` layer-① AST + `.importlinter` layer-② 전이)와 함께 green이어야
§0.3 선언이 능동 성립. **주의**: iap `invalidation_closure` 동형 규율을 상속하되(§5.4) `tos.iap` **부재**를 assert —
로컬 저작이지 import가 아님을 이 테스트가 강제. **dsl 부재도 assert**(§0.4d — `dsl.AdmissibilityResult` REUSE 금지).

### 7.2 run manifest 정렬 (설계 #1 §5.1 7항목)

(1) 목적: venue Phase-1(EV-L1) 순수 모델+property test. (2) 명령: `pytest tos/tests/venue/ -v`(실행:
`PYTHONPATH=tos/src .venv/bin/python -m pytest tos/tests/venue/ -v` — pyenv은 mypy 전용). (3) 격리: hermetic(`.env`
비주입·clock 미접근·네트워크 없음 — admissibility 판정의 hidden-input 부재·§10 monotonic clock 비교 금지와 정합).
(4) 결정론: hypothesis 시드 고정·`EVL1ProvisionalCanonicalizer` 고정·StrEnum 고정·`compare_order` 결정론. (5)
산출물: property test 결과(EV closure 아님 — 규율 태그). (6) 게이트: `tos-firewall` required green. (7) 비-acceptance:
어떤 VTG-EV도 닫지 않음(§0.2·VER-002-001 §5).

---

## 8. bounds 주입 + Phase-0

**§8.0 venue 모델 구조에 numeric·tick/lot/band 값 부재**: 전부 enum(`OrderAdmissibilityResult`/`TradabilityState`)·
boolean·집합/그래프 논리·주입 opaque param(age/generation/tick/lot/band/notional/step). ADR §4 non-scope line 103
"numeric freshness, detection, invalidation, or propagation bounds, which require approved policy and Verification
Profile values"는 수치를 **명시 배제**한다 — 전부 **Safety/Verification Profile INSTANCE 측정값**이며 주입 opaque
param으로만 담는다. 값 부재 ⇒ fail-closed(§4·§5). 값 승인은 Phase-0 Bounds-Approver 게이트(§9.2). **tick/lot/band는
policy content(§2.4 `VenueConstraintPolicy`) 주입**이지 코드 상수 아님 — 하드코딩 0.

**§8.1 Verification-Profile 키 실측(#13 MAJOR-2 규율 — `measurement_source`·`failure_response` 전수 확인)**: ADR §27
q12(line 686)가 요하는 수치 및 VERIFICATION-PROFILE-002.yaml 키 상태(전수 grep):

- **constraint loss detect(§9-13/§18)**: `B_venue_constraint_loss_detect`(line 240, `value_ms: null` — "APPROVE per
  venue, session, account, and constraint-source class", `measurement_source:
  venue_constraint_source_and_generation_trace`, rationale line 244 "venue/session/tradability, account, margin,
  borrow, settlement, broker-capability, or source-continuity loss to a committed restrictive Constraint Generation
  for the complete affected scope (ADR-002-019 §§9-13, 18)") — **이미 존재**. §4.5·§6.6과 정합.
- **invalid→authority(§16-18)**: `B_venue_constraint_invalid_to_authority`(line 247, `null` — "APPROVE after
  Constraint Generation distribution to approval and authority issuers is implemented", `measurement_source:
  constraint_generation_approval_and_authority_trace`, **`failure_response: HALT_OR_CONTAIN`** line 253, "§§16-18") —
  **이미 존재**. §4.5 invalidation-before-authority와 정합.
- **invalid→egress(§17)**: `B_venue_constraint_invalid_to_egress`(line 254, `null` — "APPROVE after active
  final-egress constraint currentness is implemented", `measurement_source:
  constraint_generation_invalidation_and_egress_boundary_trace`, **`failure_response: HALT`** line 260, "§17") —
  **이미 존재**. §6.3 egress currentness와 정합.
- **snapshot age(§14/§18)**: `MAX_venue_constraint_snapshot_age_ms`(line 711, `null` — "APPROVE per venue/session/
  account/action scope; unknown age denies dependent new risk") — **이미 존재**. §5.1·§4.3과 정합(unknown age ⇒ deny).
- **decision age(§14)**: `MAX_order_admissibility_decision_age_ms`(line 712, `null` — "APPROVE per exact order/action
  class; expiry never expires economic effect") — **이미 존재**. §4.4 economic-effect-outlives-artifacts와 정합.
- **policy artifact pin(§2.4)**: `venue_constraint_policy_id`/`venue_constraint_policy_generation`/
  `venue_constraint_policy_digest`(line 52-54, TBD/null/TBD) — Venue Constraint Policy 아티팩트의 test-harness pin
  (§8 governance는 spg/§27 q1).
- **결론(over-claim 봉합·#10 lesson)**: ADR §27 q12가 요구하는 VTG-owned 3 detection/propagation bound(loss-detect·
  invalid-to-authority·invalid-to-egress) + 2 age(snapshot·decision) + 3 policy-pin이 **전부 실재**하고 전부 null/TBD
  (미승인). ⇒ **candidate 신규 키 = 0건**(#10/#13/#15/#17 "0 누락" 동형). 이는 결함이 아니라 **Phase-0 Bounds-Approver
  승인 항목**이다 — venue는 이 값들을 신뢰하지 않으며(VP status null/TBD·unapproved bound은 approved bound 아님,
  VER-002-001 §6) 전 수치를 fail-closed로 처리(§4·§5).

**§8.2 upstream generation 합성(런타임·not-Phase-1)**: `OrderAdmissibilityDecision`은 constraint_generation뿐 아니라
upstream generation(policy·broker-capability·authority-epoch·HALT·deployment·config·evidence)을 **binding**한다 —
전부 형제 ADR 소유·주입 scalar. Phase-1 venue는 이 합성 currentness 검사를 **강제하지 않고**(런타임 §6.3) decision
record에 각 upstream 좌표를 scalar로 binding할 뿐이다(§2.4). 합성 강제·active currentness는 EV-L3 final-egress·
ADR-002-024 런타임.

**§8.3 policy self-reference 주의(경미)**: venue가 소유하는 `VenueConstraintPolicy`는 spg Safety Config governance
대상(§8 line 243)이며 VP가 policy id/generation/digest를 pin(line 52-54). venue는 **policy content author**이자 spg
activation의 **소비자**라 layering 단순 — venue는 VP를 import·파싱하지 않고(YAML은 하네스 #3) policy 좌표를 주입
scalar로만 담는다. VP status null/TBD ⇒ 전 수치 불신.

---

## 9. 후속 작업 · Phase-0 인간 게이트 이관 항목

### 9.1 후속 구현 작업 (본 계약 위에서)

1. `tos/src/tos/venue/` 5-module 저작(`_base.py` all-false `VenueGateAuthorityEffect` shim + `model_validator` +
   defence-in-depth·`vocabulary.py`[`OrderAdmissibilityResult`·`TradabilityState`·`ConstraintClass`·`ActionClass`·
   truthy 봉인]·`records.py`[3 core 아티팩트 + snapshot/decision field 골격]·`predicates.py`[core 4군 + predicate-only
   8군]·`state.py`[SessionPhase 주입 token 처리·admitting-set membership·주입 입력]) + `tos/tests/venue/` property
   test(§7) + seam cross-check(§3.4) + import-closure(§7.1 allowlist) + truthy-sentinel 구조 봉인 회귀(§4.7).
2. core 술어 4군(§5) + predicate-only 술어 8군(§6) + 3-아티팩트·all-false `VenueGateAuthorityEffect`·enum 어휘(§2)
   구현. **sibling edge 0 유지**(§0.4c) — 어떤 형제 타입도 REUSE·import 하지 않음(형제 결과는 injected scalar/bool/
   enum-token/verdict/digest). iap `invalidation_closure`는 **로컬 재저작**(import 금지·§5.4 공유 폐포 property 계약).
   `dsl.AdmissibilityResult` REUSE 금지(§0.4d).
3. 미래 caller 런타임(Venue Constraint Gate)이 venue 산출(policy·snapshot·decision·3-Ref)을 소비자(ioc proof·iap
   approval·capsule capsule·final-egress)로 배선(§3.4; Phase 1 밖·EV-L2/L3). **형제 술어 호출→결과 주입**은 런타임
   gate 몫(§0.4c) — venue 순수 모델은 주입 위 판정만.

### 9.2 Phase-0 인간 게이트로 넘기는 항목 (본 계약이 결정하지 않음)

ADR §27 Open Implementation Questions(12항)·§30 Approval Gate(14조건)에서 Phase-1 밖으로 이연:

1. **approved venue/broker/reference/calendar/account/margin/borrow/settlement/corp-action sources per scope**(§27
   q1·§30 item 2) — source contract·security review(§9 line 259 "Source names do not establish authority; policy
   decides precedence and corroboration").
2. **Session Phase·exceptional venue-state precedence 모델링(cross-venue/segment)**(§27 q2·§10) — phase state
   machine·precedence는 policy 소유(§2.2(3) SessionPhase 주입 token); classifier는 Phase-0.
3. **canonical instrument/contract/account/position-effect/order-type/TIF/routing schema**(§27 q3·§11) — canonical
   semantic form(§3.1 `EVL1ProvisionalCanonicalizer`는 잠정).
4. **dynamic price band/tick table/lot rule/reference price/auction/effective-time transition atomic 표현**(§27 q4·
   §12) — tick/lot/band 값·atomic transition은 policy content 주입(§2.4·§8.0); §5.3은 permissive-rounding-금지 술어만.
5. **broker/account query product-permission/margin/collateral/borrow/locate/settlement/restriction evidence + assurance
   level**(§27 q5·§13·§30 item 2) — broker probe·assurance는 +Broker 런타임(§6.2는 conservatism 술어만).
6. **independent validation where venue/broker exposes only one authoritative source**(§27 q6·§15·§30 item 8) —
   common-mode·residual-risk·failure-domain은 +Security(§6.6은 shared≠independent 술어만).
7. **Constraint Generation·dependency-graph substrate for fencing stale policy/evaluators/approvals/authorities/
   egress**(§27 q7·§18·§30 item 3) — ordered namespace·owner-epoch·Commit Proof는 ADR-002-012 SCL 런타임(§4.3은
   순서·non-collapse 술어만).
8. **final egress active currentness (no permissive cache·no circular dep·no unfenced check-then-send)**(§27 q8·§17·
   §30 item 5) — ADR-002-024 Currentness Vector 런타임 +Security(§6.3은 active-establish 요구 술어만).
9. **close/reduce-only/cancellation/replacement/protective 모델링 when venue/broker supports partial semantics**(§27
   q9·§19·§30 item 7) — protective replacement·partition-lease는 ADR-002-011/001(§6.4/§6.5는 assumption-금지 술어만).
10. **failure-domain allocation preventing one mapping/rule-engine/admin/credential/route/clock/deployment from
    corrupting both decision and independent validation**(§27 q10·§24·§30 item 8) — +Security 런타임(§6.6은 common
    -mode 술어만).
11. **accepted-but-inadmissible broker outcome·venue correction·post-send rule change 격리·reconcile**(§27 q11·§20·
    §30 item 11) — broker semantics는 ADR-002-004(+Broker); §6.1은 conflict⇒UNKNOWN 술어만.
12. **numeric bounds 승인**(§27 q12·§30 item 9) — `B_venue_constraint_loss_detect`·`B_venue_constraint_invalid_to_
    authority`·`B_venue_constraint_invalid_to_egress`·`MAX_venue_constraint_snapshot_age_ms`·`MAX_order_admissibility_
    decision_age_ms`(§8.1 **전부 실재·null/TBD**)의 Bounds-Approver 승인 + fault-injection 측정(§30 item 9). **candidate
    신규 키 0건.**
13. **ADR-002-020 IOC candidate command·conformance-proof binding (decision order shape 보존·no circular·no downstream
    mutation) + applicable IOC evidence**(§30 item 11) — ioc는 이미 배포 #14 — venue decision digest를 ioc proof가
    소비(§3.4; venue는 ioc import 아님·§0.4d).
14. **ADR-002-023 IAP binds exact Snapshot/Decision + complete order shape into single-use approval/Intent lineage
    without converting admissibility into approval + applicable IAP evidence**(§30 item 12) — iap는 이미 배포 #15 —
    venue snapshot/decision digest를 iap가 소비(`records.py:256-257`; venue는 iap import 아님).
15. **downstream cross-ADR recovery obligations(sbr §22)**(§30 item 12 — SBR 관점) — venue policy/generation·snapshot·
    decision·invalidation·non-revival이 sbr recovery obligation(§3.4; sbr는 이미 배포 #17 — obligation 결과 배선은
    EV-L2/L3 런타임).
16. **ADR-002-016 ERI evidence custody/replay(venue artifacts)**(§23·§30 item 10) — replay ENGINE(§2.3 레코드
    substrate만 Phase-1).
17. **ADR-002-024 CUR Currentness Vector 통합**(§17 line 388) — Constraint Generation·session/tradability/account/
    broker floor를 Currentness Vector 차원으로·final-egress currentness(§6.3 술어만).
18. **ARCHITECTURE-GATE-STATUS 명시 acceptance 결정**(§30 item 14) — 실행된 VTG-EV-001..012 + cross-system evidence
    (IOC/IAP/CII/SBR/BC/RC/SA/TIME 등, §30 items 10-13) + 독립 리뷰(Independent-Safety-Reviewer 하드 배제).

---

## 10. 개정 로그 + 비준 체크리스트

### 10.1 개정 로그

- **v1.0 (2026-07-26) — 초안, 독립 비평 리뷰 대기.** ADR-002-019(VTG)를 Phase 1(EV-L1) 설계 계약으로 실현. 문서
  번호 **#19**(#16 AFG·#17 SBR·#18 PR[세션 B] 이후). 패키지 **`tos.venue`**(대안 `tos.vtg`[register-prefix 충실] runner-up; 근거:
  `venue_*` seam 토큰 선점[ioc `records.py:414`·iap `records.py:256-257`]·capsule `Venue*Ref`[`capsule.py:130-150`]·
  iap import-closure `tos.venue` 열거(sbr는 allowlist 자동 배제 — v1.1 M2)·descriptive-name 관행[orthostate=STATE·liveauth=REARM·authority=SA·
  brokercap=BC·capsule=CII·rcl=RC·protective=PR·evidence=ERI], §0.4a). 9-모델(`VenueConstraintPolicy`·
  `VenueConstraintSnapshot`·`OrderAdmissibilityDecision`[셋 다 `IndependentIdArtifact` — capsule Ref 실측]·
  `ConstraintGeneration`[=`tos.ordering` REUSE]·`OrderAdmissibilityResult`[truthy 봉인·`dsl.AdmissibilityResult` 충돌
  회피]·`TradabilityState`·`SessionPhase`[주입 opaque token]·`ConstraintDependencyClosure`+`MaterialConstraintChange`·
  all-false `VenueGateAuthorityEffect`)(§2). EV 분류: **core 4행(VTG-EV-001/003/004/006, 전부 `EV-L1/3` 슬라이스) /
  predicate-only 8행(002/005/007/008/009/010/011/012, 최소 ≥ L2·+Security 6·+Broker 6) / not-Phase-1 — 닫는 VTG-EV
  = 0건**(§1). seam: **ioc/brokercap/spg/capsule/iap/time/recon/protective/sbr/afg/rcl/are/authority/liveauth scalar·
  bool·enum-token·verdict·digest producer/consumer + sibling edge 0건(대안 time.SessionContext REUSE 1 edge §0.4c),
  PROMOTE 0**(코드 실측: ioc `records.py:414`·`vocabulary.py:63` ConformanceResult truthy-seal·all-false[클래스
  `_base.py:54`·validator `:74`],
  iap `records.py:256-257`·`predicates.py:151-152`, capsule `capsule.py:130-150/242-244`, brokercap `vocabulary.py:86`·
  `predicates.py:277`, spg `vocabulary.py:205`, time `elements.py:177/191`·`domains.py:30/34`, dsl `evidence.py:58`,
  §3.4). **핵심 아키텍처 판정**: (i) **venue = order-admissibility gate, conformance/capacity/approval/capability는
  형제 소유**(§3.5) — conformance=ioc·capacity=rcl/are·approval=iap·capability semantics=brokercap·CII=capsule·time
  =time·currentness=ADR-002-024·authority=authority/liveauth; venue는 policy content/snapshot/decision/session-phase/
  order-shape admissibility만. (ii) **ioc §12 conformance ≠ VTG §12 admissibility(같은 필드·다른 판정)**(§3.5 핵심
  판정 (a)) — price=X가 CONFORMANT(ioc)이면서 INADMISSIBLE(VTG) 가능; shape 변경 ⇒ 새 candidate command(ioc) AND
  새 decision(VTG); ioc `venue_admissibility_decision_digest` `records.py:414` 소비·venue candidate command digest
  소비·**양방향 acyclic edge 0**. (iii) **brokercap ceiling ≠ VTG admissibility**(§3.5 핵심 판정 (b)) — brokercap=
  broker CAN(capability semantics), venue=venue ALLOWS now(current admissibility); promote 불가(VTG-INV-006);
  broker-agnostic 준수. (iv) **`OrderAdmissibilityResult` 명명 충돌 회피**(§0.4d) — `dsl.AdmissibilityResult`
  (`dsl/evidence.py:58`, ADR-DEV-001 정적 프로그램)와 동음이의·다른 도메인이므로 로컬 저작·REUSE 금지. (v)
  **SessionPhase = 주입 opaque token**(§2.2(3)) — "names are policy-defined"(§5.5 line 127) + 하드코딩 금지 ⇒
  hardcoded enum 금지; fail-closed는 admitting-set membership(unenumerated ⇒ restrictive·VTG-EV-001 노른자). (vi)
  **truthy-sentinel 구조 봉인을 처음부터**(#14 M1 선제·4-값이라 더 임계): `OrderAdmissibilityResult`·`TradabilityState`는
  `__bool__ ⇒ TypeError` ⇒ 소비 게이트 `is ADMISSIBLE`/`is TRADABLE`·`bool|None`은 `is True`(§4.7) —
  `RESTRICTED_PROTECTIVE_ONLY` truthy fail-open(protective-only를 full-permission 오독) 방지가 핵심. 중심 fail-closed
  술어: `session_phase_admits`(§5.1 — 미열거 phase ⇒ 거래 불가)·`exact_instrument_route_bound`(§5.2)·
  `order_shape_admissible`(§5.3 — permissive rounding 금지)·`decision_binding_exact`+`no_decision_union`+
  `material_change_closure`(§5.4). predicate-only 8군(§6). **∅-공허 양방향**(unenumerated phase·빈 constraint set·빈
  dependency 폐포·UNKNOWN+capacity·missing scope — 금지+허용 둘 다, §4.7). 앵커: VTG-INV-001..014·VTG-AC-001..012·
  VTG-EV-001..012(§0.4f). **bounds 실측**: VTG-owned 3 detection/propagation bound(line 240·247·254) + 2 age(711·712)
  + 3 policy-pin(52-54) 전부 실재·null/TBD(candidate 신규 키 0건, §8.1). 선제 봉합: fail-open(§4.1/§5.1)·∅-공허 양방향
  (§4.7)·under-realization(전용 술어는 실재 형제 seam에만·conformance/capacity/approval은 정직 이연)·**phantom 타입
  0**(전 인용 grep 실측·필드-클래스 소유까지 확인 #15 M1 교훈 — capsule Ref·ioc/iap 필드·dsl 충돌 전부 실측)·verbatim
  +line·**차원 비붕괴**(§2.2·§3.5 — `OrderAdmissibilityResult`≠`dsl.AdmissibilityResult`·VTG admissibility≠ioc
  conformance≠brokercap capability≠time calendar-phase)·**truthy-sentinel 구조 봉인(#14 M1 선제)**·**과대 주장 금지**
  (extra="forbid"는 모델 필드 수준만). **어떤 EV도 닫지 않음·acceptance 미선언·비준 기록 = "2026-07-26 운영자
  위임 자동 비준(v1.1)"** (구:"v1.0 초안 — 독립 비평
  리뷰 대기".**

- **v1.1 (2026-07-26) — 독립 비평 리뷰 REVISE(CRITICAL 0·MAJOR 0·MINOR 4·NIT 2 — 전부 인용-충실도, 아키텍처
  무결) 반영, forward-only(오케스트레이터 직접 적용).** **M1**: `ProtectiveOwnership` 파일 재귀속
  (`protective/vocabulary.py:60`; `dominating_halt_or_incident`는 `records.py:202`·소비 `predicates.py:395`).
  **M2**: "sbr가 tos.venue 열거" 거짓 정정(sbr는 allowlist 자동 배제 — iap `__init__.py:49` 열거만 유지).
  **M3**: ioc all-false 인용 통일(클래스 `_base.py:54`·validator `:74`·도크스트링 `:60`/`:66-72`) ×5곳.
  **M4**: `ActionClass` = closed StrEnum 판정 추가(ADR §11:283–289 고정 taxonomy — SessionPhase와 달리
  policy-open 아님). **NIT**: time domains `34/30` 순서. 리뷰어 검증 확인: ~45건 인용 실측·register 12행·
  VP 8키 정확·firewall allowlist가 미래 형제(`tos.pr` 등) 자동 배제(#17 교훈 구조적 대응)·verbatim 문자 일치.
  아키텍처(9-모델·edge 0·ioc/brokercap 경계·truthy 봉인) 불변.

### 10.2 비준 체크리스트 (운영자 · 독립 리뷰어 확인 사항)

1. **패키지 명명** `tos.venue`(선점·seam 정합·phantom 0) 승인 — **또는 `tos.vtg`**(register-prefix VTG 충실).
   **[운영자 판단 지점]**: `venue`가 (i) `venue_*` seam 토큰(ioc `records.py:414`·iap `records.py:256-257`)·capsule
   `Venue*Ref`(`capsule.py:130-150`)와 정합하고 (ii) 기존 #15/#17 배제 목록의 `tos.venue`를 phantom 없이 실체화하는지
   vs `vtg`가 register series prefix와 1:1인지. **에라타 판정**: `vtg` 채택 시 §7.1 allowlist(`⊆ {canonical, ordering,
   self}`)라 enforcement 에라타 불요이나 illustrative prose 정정 + `venue_*` 코드 토큰 drift 발생; 배제 목록 규율은
   "실재 형제 전부"라 신규 형제 추가는 두 명명에서 대칭(§0.4a). naming은 load-bearing 아님.
2. **ioc §12 conformance ≠ VTG §12 admissibility(§3.5 핵심 판정 (a) — 최대 아키텍처 공격 지점)**: 같은 필드(price/
   qty/side/order-type)를 두 gate가 검사하는 것이 **중복이 아니라 다층 방어**(intent-fidelity vs venue-admissibility)
   인지. **[리뷰어 공격]**: "ioc·VTG price/qty 검사 중복 = DRY 위반" — 반론: 판정 대상 상이·§12 line 311 "defense in
   depth"·shape 변경 ⇒ 양쪽 새 아티팩트(line 309). 리뷰어: ioc `OrderConformanceProof.venue_admissibility_decision_
   digest` `records.py:414`가 admissibility를 **소비**하되 평가 안 함(#14 §0.4 line 139-141) 확인.
3. **brokercap ceiling ≠ VTG admissibility(§3.5 핵심 판정 (b))**: brokercap=capability semantics(broker CAN)·
   VTG=current admissibility(venue ALLOWS now) 경계가 정확한지·promote 불가(VTG-INV-006)·broker-agnostic 준수(§13이
   broker 제약을 capability-class로만 표현·KIS 값 부재)인지. **[리뷰어 공격]**: "VTG §13이 broker 제약을 다루니
   brokercap 재저작" — 반론: ceiling scalar 소비만·semantics 재저작 안 함. 리뷰어: brokercap `vocabulary.py:86`
   `MARKET_INSTRUMENT_CONSTRAINTS`·`predicates.py:277` version scalar 소유 확인.
4. **`OrderAdmissibilityResult` 명명 충돌 회피(§0.4d)**: `dsl.AdmissibilityResult`(`dsl/evidence.py:58`,
   `IndependentIdArtifact`·ADR-DEV-001 정적 프로그램)·`dsl.AdmissibilityVerdict`와 동음이의·다른 도메인임을 확인하고
   VTG 결과 enum을 `OrderAdmissibilityResult`로 분리·dsl REUSE 금지가 정확한지. **[리뷰어 공격]**: "이미 dsl에
   AdmissibilityResult 있으니 REUSE" — 반론: 도메인 상이(정적 DSL admission vs venue order admission)·차원 비붕괴.
5. **SessionPhase 주입 token vs hardcoded enum(§2.2(3)·§5.1)**: "Names are policy-defined"(§5.5 line 127) + 하드코딩
   금지 ⇒ 주입 opaque token이 정확한지 vs 편의상 closed StrEnum. **[리뷰어 공격]**: "phase가 enum이 아니면 타입
   안전성 상실" — 반론: policy-defined open set이라 enum은 ADR 위반·fail-closed는 admitting-set membership(unenumerated
   ⇒ restrictive)이 오히려 더 강함. 리뷰어: time `elements.py:191` `phase: str|None`(injected) 선례 확인.
6. **truthy-sentinel 구조 봉인(§4.7·§2.2(1))**: `OrderAdmissibilityResult`(4-값)·`TradabilityState` `__bool__⇒TypeError`가
   §7 회귀로 강제되는지 — 특히 **`RESTRICTED_PROTECTIVE_ONLY` truthy fail-open**(protective-only를 full-permission
   오독) 방지. 리뷰어: ioc `ConformanceResult.__bool__` `vocabulary.py:63`(3-값) 대비 4-값 임계성 확인.
7. **sibling edge 0 vs time.SessionContext REUSE(§0.4c)**: edge 0(injected digest/scalar, iap/sbr 선례)이 정확한지 vs
   time `SessionContext` typed-reuse(1 edge). **[운영자 판단 지점]**: time REUSE가 VTG-INV-002(calendar ↛ tradability)
   를 위반하는지(calendar-expectation phase를 admissibility phase로 채택). 리뷰어: time `elements.py:180` broker
   -agnostic calendar-expectation vs VTG authoritative-current 의미 도메인 대조.
8. **acyclic seam(§3.5 핵심 판정 (c))**: ioc↔VTG 양방향 digest 참조가 import cycle 없이 성립하는지(candidate command
   → decision → conformance proof append-only). 리뷰어: #14 §3.4 line 540 "ioc↛venue" + 본 계약 "venue↛ioc" 대조.
9. **all-false `VenueGateAuthorityEffect`(§6.7·§4.6·VTG-INV-011)**: 전 필드 `False`·`model_validator` 봉인·defence-in
   -depth 술어(`model_construct` 대비)가 ioc `AllFalseConstructionAuthority`(클래스 `_base.py:54`·validator `:74`·
   도크스트링 `:60`/`:66-72` — v1.1 M3 통일) 동형인지·gate가
   live credential/route 미보유(§7 line 223)인지. **[리뷰어 공격]**: gate가 admissibility로 permission 생성하는 경로.
10. **material_change_closure 공유 폐포(§5.4·#17 MINOR-5)**: iap `invalidation_closure`·sbr `_reachability_closure`와
    동일 폐포 공리(trigger∈closure·monotone·불확정⇒확장·empty⇒{trigger}·proven-disconnect 제외)를 **로컬 저작**(import
    금지)으로 만족하고 §7 공유 property 계약으로 회귀하는지. **[리뷰어 공격]**: "iap 폐포 중복 = DRY 위반" — 반론:
    firewall sibling-edge-0·코드가 아니라 규율을 DRY(#17 §0.4d 선례).
11. **EV 분류·닫는 VTG-EV 0건(§1)**: core 4(001/003/004/006 전부 `EV-L1/3` 슬라이스)·predicate-only 8·+Security 6·
    +Broker 6·broker-cap N/A 2행(006/011)이 register(csv line 221-232) 실측과 일치하고 **어떤 EV도 닫지 않음**·
    "EV-L1-complete 주장 금지" 태그 부착 확인.
12. **bounds·Phase-0(§8.1·§9.2)**: VTG-owned 3 detection/propagation bound(line 240·247·254) + 2 age(711·712) + 3
    policy-pin(52-54) **전부 실재·null/TBD**(candidate 신규 키 0건) 확인 + tick/lot/band는 policy content 주입(하드코딩
    0) 확인.
13. **phantom 0·필드-클래스 소유(§10.1)**: 전 인용 타입이 실재하고(capsule Ref·ioc/iap 필드·spg enum·time SessionContext
    ·dsl 충돌 grep 실측) 필드가 어느 클래스 소유인지까지 확인(#15 M1 교훈)했는지. 리뷰어: `VenueConstraintPolicy`/
    `Snapshot`/`OrderAdmissibilityDecision` full 아티팩트는 greenfield(capsule은 `*Ref`만 보유)임 확인.

---







