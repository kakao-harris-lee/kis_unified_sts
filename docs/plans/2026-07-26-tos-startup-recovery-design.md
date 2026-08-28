# 설계 문서 #17 — Safe Startup·Recovery Barrier·Conservative Resume 계약 (2026-07-26, v1.1)

> **문서 번호 규약(2026-07-26)**: 병렬 세션 B가 ADR-002-022(Action-Flow Budgeting — AFG)를 **설계 문서 #16**
> 으로 비준·INDEX 등록했다(`docs/plans/2026-07-26-tos-action-flow-budgeting-design.md`). 번호 충돌 회피로 본
> SBR(ADR-002-017) 문서는 **설계 문서 #17**이다. **#16 AFG는 비준본이며 `tos/src/tos/afg/` 구현도 완료**
> (v1.1 MAJOR-2 정정 — 저작 중 세션 B가 착지)됐으나, **sibling-edge-0 규율에 따라 import가 아닌 injection
> slot으로만 소비**한다 — SBR §19 retry containment·SBR-EV-006 retry 좌표가 AFG rate/budget과
> 인접하는 지점(§3.5)에서만 참조하고, ADR-002-022 원문(SBR ADR §13 obligation 11 line 364·§28 item 15 line 709)이
> 규범 앵커다.

> **문서 성격 (규범성 선언)**: 본 문서는 ADR-002-017(Safe Startup, Recovery Barrier, and Conservative
> Resume Coordination — 이하 **SBR**)을 Phase 1(EV-L1) 설계 계약으로 실현하는 **비규범 설계 문서**다.
> GOV-001의 세 거버넌스 행위(비준 / ADR acceptance / live authorization) 중 **어느 것도 수행하지 않는다**.
> tos-spec의 ADR·RFC·VER·register·profile 어떤 상태도 변경하지 않고, 어떤 SBR-EV 항목도
> `NOT_IMPLEMENTED`에서 이동시키지 않는다. **비준 기록 = "2026-07-26 운영자 위임 자동 비준(v1.1)"**(§10.1 —
> 독립 비평 리뷰 REVISE[CRITICAL 0·MAJOR 2·MINOR 5]의 minimal edit set 전량 반영 후 위임 집행; 판단 지점:
> `tos.sbr` 명명·edge 0·obligation-graph 폐포 로컬 저작[공유 커널 명시]·readiness≠re-arm 채택).
> 앵커는 ADR-002-017 자체 시리즈 **SBR-INV-001..014(§6)·SBR-AC-001..012(§25)·SBR-EV-001..012(register)**
> 이며 **새 INV/AC/EV 시리즈를 창작하지 않는다**(§0.4f — #12/#13/#14/#15 동형). 인용은 verbatim + ADR
> line 병기, 코드 seam은 file:line 실측(phantom 금지 — #15 MAJOR-1 교훈: 필드가 어느 클래스 소유인지까지
> 확인). broker-agnostic — KIS 등 특정 broker 고유사항은 본 문서에 넣지 않고 capability class로만 표현한다.

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. **패키지 위치·명명 `tos/src/tos/sbr/`** (register family/prefix `SBR` 직접 명명; 대안 비교 §0.4a).
2. **EV 분류 — core 5행 / predicate-only 7행 / 닫는 SBR-EV = 0건**(§1). core 5 = {SBR-EV-004·006·007·
   009·012}(전부 `EV-L1/3`), predicate-only 7 = {001·002·003·005·008·010·011}(최소 ≥ L2, ±Security/
   Broker). **"EV-L1-complete 주장 금지"** 규율 태그(§1).
3. **중심 데이터 모델 8종**(§2): `RecoveryTrigger`·`RecoveryBarrierState`·`RecoverySession`(§10 상태기계)·
   `RecoveryGeneration`(=`tos.ordering` REUSE)·`RecoveryInventoryCut`(§12)·`RecoveryObligation`+
   `RecoveryObligationGraph`(§13)·`RecoveryEvidencePackage`(§9/§16)·`RecoveryReadinessDecision`(§16, all-false
   authority) + readiness expiry/invalidation(§18).
4. **중심 fail-closed 술어**(§4·§5·§6): core L1 슬라이스 7종(§5) + predicate-only 7종(§6). 전부 순수 함수 —
   permissive 기본값 부재·vacuous 부재·truthy-sentinel 구조 봉인.
5. **소유권/seam 분할표**(§3.5): 인접 8패키지(orthostate·recon·rcl·protective·spg·authority·liveauth·iap)와의
   경계를 **코드 실측 slot**으로 고정. 특히 (i) orthostate `reconstruct_conservative` 재저작 금지, (ii) iap
   `invalidation_closure` **동형성 판정 = 로컬 저작(PROMOTE 기각·import 기각)**, (iii) liveauth/authority re-arm은
   SBR readiness의 **하류 소비자**(SBR은 생산자), (iv) authority `GenerationVector.recovery_generation` **좌표
   소유**.
6. **truthy 구조 봉인 선제**(§4.7): 결정 enum `__bool__ ⇒ TypeError`·`is X` 소비 계약·∅ 양방향·집합 비교
   양방향·금지 동사 canary·all-false authority.
7. **firewall 준수**(§0.3): sibling edge **0 권장**(대안 typed-enum-reuse 1~3 edge 비교 §0.4c) + §7.1
   import-closure 검증 + §7.2 run manifest.
8. **bounds 주입 + Phase-0 이관 목록**(§8·§9.2): SBR-owned 신규 profile 키 **0건**(전부 실재·null/PROPOSED).

### 0.2 하지 않는 것 (경계·NO 목록)

- **어떤 SBR-EV도 닫지 않는다**(core 5조차 `/3` 통합·독립 리뷰 잔여; predicate-only 7은 최소 ≥ L2). Owner/
  Reviewer는 register상 TBD. authoring ≠ acceptance(VER-002-001 §5 "Registration is not execution").
- **capacity 변이·quarantine·release 미결정** — RCL only(ADR-002-002/012; SBR-INV-010 line 182). SBR은
  evidence-bound request만.
- **per-field reconciliation confidence·Final Quantity Proof 미결정** — ADR-002-004/006(SBR ADR §4 line 89).
  SBR는 recon 결과를 **소비**하되 confidence를 declare하지 않는다(§7 line 210).
- **protective classification·capacity·replacement·broker transmission 미결정** — ADR-002-001/011/013(SBR ADR §4
  line 91). recovery/operator label은 아무 권한도 못 만든다(§7 line 212).
- **human approval·Live Authorization·currentness·egress permission 미결정** — ADR-002-007/013/015/024(SBR ADR §4
  line 92). readiness는 이들의 **입력**이지 permission이 아니다(SBR-INV-003 line 154).
- **safety-configuration activation 미결정** — ADR-002-014/spg(SBR ADR §4 line 93). readiness는 status만 기록.
- **evidence custody·deterministic replay ENGINE 미결정** — ADR-002-016/evidence(SBR ADR §4 line 94). SBR는 레코드
  substrate만 저작; replay는 하류.
- **concrete workflow·consensus·storage·broker-query·deployment 제품 미결정**(SBR ADR §4 line 95). 전부 주입/런타임.
- **numeric recovery bounds 미승인**(SBR ADR §4 line 96 "belong in the Verification Profile"). 전부 Phase-0
  Bounds-Approver(§8·§9.2).
- **ADR-002-022(AFG) 재저작·인용 금지(세션 B 소관)** — SBR ADR §13 obligation 11(line 364)·§28 item 15(line
  709)의 **ADR 원문만** 인용하고, 세션 B의 AFG 설계 문서는 인용하지 않는다. AFG 좌표는 §13 obligation의 주입
  slot으로만 참조.

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

`tos.sbr` 모델은 다음만 import한다:

- **서드파티**: `pydantic`(frozen 모델)·`pytest`/`hypothesis`(테스트만). **`numpy`/`pandas`/`pyyaml` 미import** —
  recovery 판정은 StrEnum·boolean·집합/그래프 논리이고 모든 bound·age·registry·graph 값은 주입 파라미터이며 YAML
  파싱은 하네스(설계 #3) 소관(closure 최소화 — #12–#15 §0.3 동형).
- **tos 자기 자신**: `tos.canonical`(`FrozenModel` `_base.py:73`·`DigestBoundArtifact` `_base.py:98`·
  `IndependentIdArtifact` `_base.py:328`·`classify_record_pair` `record_pair.py:52`·`RecordPairKind`
  `record_pair.py:31` — §20 restore-branch conflict 탐지·`ArtifactStatus` `_base.py:58`·
  `EVL1ProvisionalCanonicalizer` `canonicalization.py:173`)·`tos.ordering`(`Ordering`·`OrderingEvent`·
  `compare_order` `__init__.py:19` — **Recovery Generation monotonic 순서**; 실측 `ordering/_ordering.py:38`
  `from tos.canonical import FrozenModel`만 의존이라 core)·`tos.sbr.*`.
- **미import(직접·전이 모두) — 17 형제 tos 패키지(실재 16 + `tos.venue` 미구현)**: **`tos.afg`(v1.1 MAJOR-1
  정정 — 세션 B 구현 완료된 최인접 형제, 누락은 sbr→afg edge의 유일 가드 구멍이었음)**·`tos.are`·
  `tos.authority`·`tos.brokercap`·`tos.capsule`·
  `tos.dsl`·`tos.evidence`·`tos.iap`·`tos.ioc`·`tos.liveauth`·`tos.orthostate`·`tos.protective`·`tos.rcl`·
  `tos.recon`·`tos.spg`·`tos.time`·`tos.venue`(미구현). **전부 produced/consumed scalar·bool·enum-token·
  verdict·digest로만 참조**(§3.4/§3.5). **sibling edge 0 권장·PROMOTE 0건**(대안: recon `FieldConfidenceClass`·
  orthostate `KnowledgeState`·rcl `CapacityState` typed-reuse 1~3 edge — §0.4c 운영자 판단 지점).
- **`shared.config` 절대 금지**(설계 #1 §6.1, `.importlinter`): `shared.config.__init__`이 `shared.config.secrets`
  (→ `os.environ`)를 무조건 전이 import한다. `tos.sbr`는 어떤 `shared.*`도 필요로 하지 않는 순수 커널이다.
- **금지(직접·전이)**: `shared.execution`·`shared.kis`·`shared.streaming`·`shared.llm`·`shared.storage`·
  `shared.backtest`·`shared.config.secrets`·`services.*`·`cli.*`(`.importlinter`
  `[importlinter:contract:tos-operational-firewall]` type=forbidden·source_modules=`tos` 실측 — forbidden set).
- **firewall 구조 확인(실측)**: `.importlinter`는 `type=forbidden·source_modules=tos` 단일 계약이며 `layered`가
  아니다 — intra-tos sibling→sibling edge는 구조적으로 금지되지 않고 설계 #1 §3.2의 "자기 자신 `tos.*`" 허용
  조항이 이를 커버한다. **신규 패키지 `tos.sbr`는 firewall 도구 무수정 자동 포섭**된다(forbidden 계약이
  source=tos 전체를 덮으므로). **본 문서는 sibling edge 0을 설계 규율로 삼되**(§0.4c), IAP(#15) 선례의 edge 0을
  **소비자 규모가 큰 SBR에도 유지 가능**함을 liveauth 소비 패턴(injected bool)으로 입증한다.
- 이 배제를 능동 강제하는 것이 §7.1 import-closure 검증 테스트다(`import tos.sbr` closure에 금지·`shared.config`·
  `os.environ`·numpy/pandas/yaml·**16개 형제 tos 패키지 전부** 부재 assert; **`tos.canonical`·`tos.ordering`만
  존재 허용**). required check(`tos-firewall`, `tools/tos_firewall_check.py` layer-① AST + `.importlinter`
  layer-② 전이)와 함께 green이어야 성립.

### 0.4 REUSE / import / 경계 결정 요지 (핵심 아키텍처)

**(a) 패키지 위치·명명 = `tos/src/tos/sbr/`.** register domain(EVIDENCE-REGISTER-002.md line 228) "**Safe
Startup and Recovery Barrier**"·prefix `SBR`(`SBR-EV`/`SBR-AC`/`SBR-INV`)를 직접 명명. 명명 대안 비교(#15 §0.4a
형식):

- **`tos.recovery`(runner-up·verbose·과대·토큰 오염)**: 명료하나 (i) **verbose(8자)**로 terse 3-letter 관행
  (rcl/spg/dsl/are/ioc/iap)과 어긋남, (ii) **"recovery" 토큰이 tos 전역에서 이미 cross-cutting**임 — authority
  `GenerationVector.recovery_generation`(`authority/state.py:50`)·`recovery_generation_revives_nothing`이
  **authority(`predicates.py:787`)·time·rcl(`predicates.py:802`; docstring `:26`) 3곳에 replica로 존재**하므로 `tos.recovery`
  패키지는 "recovery = 이 패키지"라는 **거짓 소유 인상**을 준다(실제로 recovery_generation 좌표는 authority가
  carry, revival 술어는 4개 도메인이 각자 소유). (iii) ADR 제목의 **"startup"·"barrier"·"resume" 3축을 이름에서
  누락**. **§10.2 판단 지점의 defensible 차선**.
- **`tos.startup`(기각·부분)**: cold-start만 명명. ADR은 **reconnect·failover·restore·incident recovery·resume**이
  본체이고(§1 line 15·§4 line 74·SBR-AC-001 line 638) startup은 트리거의 하나일 뿐이다. register domain "Safe
  Startup **and Recovery Barrier**"의 후반부를 누락.
- **`tos.barrier`(기각·기전 명명·collision)**: Recovery Barrier 기전만 명명하며 session(§10)·inventory(§12)·
  obligation(§13)·readiness(§16) 모델을 누락. 또한 **"barrier"는 동시성 프리미티브(CyclicBarrier 등) 일반 용어**라
  safety-recovery 도메인에서 오독 위험. barrier state(§9)는 4-값 enum 중 하나이지 패키지 전체가 아니다.
- **`tos.resume`(기각·부분)**: Conservative Resume만 명명. inventory cut·obligation graph·reconciliation
  convergence(§12–§14)라는 **대량 machinery를 누락**한다 — resume은 readiness 이후의 handoff 국면일 뿐.
- **선택(권장) `tos.sbr`**: **register domain "Safe Startup and Recovery Barrier"·prefix `SBR`**를 직접 명명,
  terse 3-letter로 `tos.rcl`/`tos.spg`/`tos.dsl`/`tos.are`/`tos.ioc`/`tos.iap` 관행 정합, ADR 제목·EV/AC/INV 시리즈
  전체와 1:1. **코드 토큰 충돌 0**(실측: `ls -d sbr recovery startup barrier resume` → 부재; `recovery_generation`·
  `recovery_coordinator_evidence_complete`·`recovery_current`·`recovery_readiness_enlarged`는 전부 **scalar
  필드명**이지 패키지가 아니다 — #15의 `approval_identity` 동형 판정). **오독 위험**: `sbr`은 트레이딩/소프트웨어
  일반 약어 충돌이 약하다(SBR = 흔히 "Small Business" 등 무관 도메인). 완화: package docstring 1행("Safe Startup /
  Recovery Barrier / Conservative Resume — ADR-002-017; recovery_generation 좌표는 authority가 carry"). **§10.2
  운영자 판단 지점**: `tos.sbr`(register-prefix 충실·오독 경미) vs `tos.recovery`(명료·verbose·토큰 오염). 내부
  module(`_base.py`·`vocabulary.py`·`records.py`·`predicates.py`·`state.py`)은 rcl/are/spg/ioc/iap 선례 동형.

**(b) sbr = orchestration 소유, per-field/per-dimension 판정은 형제 소유 (중심 결정·코드 실측).** SBR는
**dataflow상 recovery orchestrator**다 — orthostate(state reconstruction)·recon(field confidence)·rcl(capacity
union/partition)·protective(HALT dominance)의 **결과를 fold**하여 obligation graph를 닫고 readiness를 발행하되,
그 **per-dimension/per-field 판정 자체는 재저작하지 않는다**. #15 IAP가 "approval gate이지 economic-effect
producer가 아니다"라고 자리매김한 것과 동형으로, **SBR은 recovery orchestrator이지 reconciliation/capacity/
protective 판정자가 아니다**. 이것이 §3.5 소유권 분할의 축이며, 위반 시 권위 중복(#8 lesson).

- SBR가 **소유**: RecoverySession 상태기계·RecoveryInventoryCut 완전성·RecoveryObligationGraph 폐포·
  RecoveryReadinessDecision·barrier/trigger 모델·scope-expansion closure(§8)·readiness-invalidation closure(§18)·
  recovery-of-recovery(§19)·`recovery_generation` 좌표 **의미/fencing**(authority는 carry만, §3.5).
- SBR가 **소비**(형제 결과 주입): orthostate `reconstruct_conservative`(per-dimension conservative restart)·recon
  `classify_field`/`FieldConfidenceClass`(per-field)·rcl fence/committed-prefix/`partition_verdict`/
  `credible_union_capacity`/`QUARANTINED_UNKNOWN`·protective `dominating_halt_or_incident`/
  `ProtectiveOwnership.SAFETY_OWNED`·authority/time/rcl/spg `*_revives_nothing`(replica 선례).
- SBR가 **생산**(하류 형제가 scalar로 소비): `recovery_coordinator_evidence_complete`(→ authority
  `_REARM_PREREQUISITES` item 12, `is True` 소비 `predicates.py:769`)·`recovery_current`(→ liveauth
  `state.py:139`)·`recovery_readiness_enlarged`(→ liveauth `state.py:208`)·`recovery_generation`(→ authority
  `GenerationVector` `state.py:50` reference 좌표).

**(c) sibling edge 0 권장 vs typed-enum-reuse 1~3 edge (중심 판단 지점·#14/#15 distinction).** SBR는 형제
**결과**를 대량 소비하므로 edge 결정이 #15보다 미묘하다. 두 대안:

- **권장: edge 0 (result injection).** 모든 형제 상호작용을 **주입된 bool/verdict/opaque enum-token(str)** 으로
  받는다. 근거: **liveauth 실측 선례** — liveauth는 protective 결과 `protective_coverage_valid`를 **import 없이**
  injected bool로 소비한다(protective `predicates.py:27` "`reserve_sufficiency` (== the produced
  `protective_coverage_valid`) fills liveauth `ContinuousValidityInputs.protective_coverage_valid`
  (`liveauth/state.py:138`)"). 즉 **소비자 규모가 큰 패키지도 injection으로 edge 0 유지 가능**함이 이미 배포
  코드로 입증됨. 런타임 Recovery Coordinator가 형제 술어를 호출하고 그 결과를 SBR 순수 모델에 주입하며, SBR
  술어는 주입 scalar 위에서 fold한다.
- **대안: typed-enum-reuse (1~3 edge).** RecoveryInventoryCut/obligation 결과를 recon `FieldConfidenceClass`·
  orthostate `KnowledgeState`·rcl `CapacityState`의 **typed enum**으로 저장. 장점: 컴파일타임 타입 안전·token
  drift 방지. 단점: **1~3 sibling edge 추가**(closure 확대)·형제 enum 변경에 SBR 결합. 완화: 이 세 enum은 전부
  **canonical-only leaf**(recon/orthostate/rcl → canonical 단방향)라 edge 추가 시에도 closure는 얕다.
- **기각 근거(edge 0 권장)**: (i) firewall sibling-edge-0 규율(#15 §3) 유지, (ii) SBR obligation 결과는 대부분
  **bool**(obligation satisfied 여부)이라 typed enum이 불요, (iii) 형제 enum이 필요한 지점(confidence class·
  knowledge state)은 **런타임 EV-L2/L3 reconciliation 국면**이지 L1 obligation-graph 폐포가 아니다(§6.5). **§10.2
  운영자 판단 지점**: edge 0(권장·liveauth 선례) vs typed-reuse(타입 안전·1~3 edge). 리뷰어 공격 지점(§10.2 (iii)):
  "opaque token injection이 실 의존을 은폐한다" — 반론은 §7.1 seam cross-check가 token↔형제 enum 정합을 test로
  강제함(§7.2).

**(d) iap `invalidation_closure` 동형성 판정 — 로컬 저작(PROMOTE 기각·import 기각) [중심 아키텍처 판정].**
SBR §8 scope-expansion과 §18 readiness-invalidation은 iap `invalidation_closure`(`iap/predicates.py:347`)와
**구조적으로 동형**이다(순수 그래프 도달성·불확정 edge 확장·empty⇒{trigger}·proven-disconnect 제외). 실측 대조:

| SBR 조항 | 연산 | iap `invalidation_closure` 대응 | 동형? |
|---|---|---|---|
| §8 scope expansion(line 240 "included unless isolation is positively proven"·"Unknown dependency mapping expands to the containing account or broader Safety Cell") | 트리거 scope에서 dependency graph 도달성 폐포; unknown edge ⇒ 확장 | `uncertain` adjacency 확장(`predicates.py:397-400` "불확정 edge => 확장")·proven-disconnect 제외(`predicates.py:368`) | **동형(reachability set)** |
| §18 readiness invalidation(line 453-463 "material change to … invalidates … advances or closes the barrier") | material change ⇒ 영향받는 readiness 폐포 | invalidation 도달성(`predicates.py:353` "§14 / IAP-INV-008") — **의미 도메인까지 동일**(invalidation) | **동형(reachability set)** |
| §13 obligation graph(line 372 "Missing or cyclic obligation dependencies make the session NOT_READY") | prerequisite DAG **완전성 + acyclicity** 검사 | (해당 없음 — iap는 reachability **집합** 반환, DAG-validity **bool** 아님) | **비동형(반환형 상이)** |

**판정: `tos.sbr`에 로컬 저작하고 iap `invalidation_closure`를 규율 선례로 상속(import 금지·PROMOTE 기각).**

- **import 기각**: `sbr → iap` 형제 edge는 firewall sibling-edge-0 규율(§0.3) 위반. iap는 SBR와 대략 형제 층
  (iap=승인 gate·SBR=recovery orchestrator; 둘 다 liveauth 상류). 형제의 도메인 술어를 구조 재사용 위해 import하는
  것은 firewall이 억제하는 결합.
- **PROMOTE 기각**: 순수 그래프 폐포를 중립 shared 모듈(예 `tos.graph`)로 승격하려면 (i) **이미 비준된 iap 코드를
  touch**하여 import를 재배선해야 함(비준 아티팩트 변경 — 강한 정당화 필요), (ii) `canonical`(digest)·`ordering`
  (append-only 순서)은 graph reachability의 자연스러운 집이 아니라 **신규 중립 모듈 창설**이 필요한데 이는 한 ADR이
  단독 결정하기엔 과한 아키텍처 확장, (iii) 대상은 ~15줄 표준 반복 DFS.
- **로컬 저작 정당화(코드 선례)**: **본 코드베이스의 확립된 관행이 REPLICATE-WITH-NOTE**임 —
  `recovery_generation_revives_nothing`이 **authority(`predicates.py:787`)·time·rcl(`predicates.py:802`; docstring `:26`) 3곳에
  각자 replica**로 존재하며 각 docstring이 "isomorphic to the Trustworthy Time / RCL …"로 상호 참조한다
  (`authority/predicates.py:801` verbatim "isomorphic to the Trustworthy Time / RCL
  `recovery_generation_revives_nothing`"). 즉 순수 술어의 도메인 간 공유는 **코드 공유가 아니라 복제 + 동형 주석**이
  established pattern이다. SBR의 closure도 이 pattern을 따른다.
- **비동형 부분(§13)**: obligation-graph 폐포는 **DAG 완전성+acyclicity bool**이지 reachability 집합이 아니므로
  iap 재사용은 **범주 오류**(반환형 상이). §13은 별도 술어 `obligation_graph_closed`로 저작(§5.2).
- **domain-rule 차이(§8)**: §8은 "unknown ⇒ **containing account/broader Safety Cell로 확장**"이라는 **scope-
  widening 규칙**을 추가로 가진다 — iap의 순수 reachability를 넘는다. 따라서 literally 같은 함수가 아니다.
- **DRY 보존(discipline 수준)**: 동형성은 **property-test 계약 수준**에서 강제한다(§7) — iap와 sbr의 closure는
  **동일 폐포 공리**(trigger∈closure·monotone·불확정 edge 확장·empty⇒{trigger}·proven-disconnect 제외)를 각자
  만족해야 하며, 이를 공유 property 계약으로 회귀한다. 코드가 아니라 규율을 DRY한다. **§10.2 운영자 판단 지점**:
  로컬 저작(권장·replica 선례) vs PROMOTE(신규 중립 모듈·iap touch). 리뷰어 공격 지점(§10.2 (ii)): "iap
  `invalidation_closure` 중복 = DRY 위반".

**(e) `recovery_generation` 좌표 소유 (authority가 carry, SBR이 fence 의미 소유).** authority
`GenerationVector`(`authority/state.py:29`)는 `recovery_generation`(line 50)을 **reference-only scalar**로
carry한다 — docstring 실측(`state.py:42-43`): "Only `safety_authority_epoch` is authority-owned / fenced here;
the rest are **reference-only scalars** (their owning ADR fences them)." ⇒ **`recovery_generation`의 owning
ADR = ADR-002-017**이므로 **SBR이 그 fence 의미를 소유**하고 authority는 non-collapsing 좌표로 실을 뿐이다.
같은 벡터의 `restore_generation`(line 49, §20 restore와 공동)·`process_generation`(line 52, §8 process-suspension
트리거)도 동일. **§4.3 non-collapse canary 상속**(authority `predicates.py` "substituting one coordinate's value
for another never satisfies a fence") — SBR도 recovery_generation을 다른 좌표로 대체하면 fence 불성립을 보존.

**(f) 앵커 규약 — SBR-INV/AC/EV 앵커, 새 시리즈 창작 금지.** **실측**: ADR-002-017은 자체 시리즈
**`SBR-INV-001..014`(§6 line 146–200, 14종)·`SBR-AC-001..012`(§25 line 636–649, 12종)·`SBR-EV-001..012`
(EVIDENCE-REGISTER-002.md line 228–239, 12행)를 정의**한다. §25 preamble(line 634 verbatim): "The following
cases are mandatory and **map one-to-one to `SBR-EV-001` through `SBR-EV-012`**. Written cases are not completed
evidence." ⇒ 본 계약은 모델 불변식·술어를 **`SBR-INV-###` / `SBR-AC-###` / `SBR-EV-###` / §-clause /
`SAFE-###`(§26 traceability line 655–666)**에 앵커하고 **새 시리즈를 창작하지 않는다**. #12–#15 동형.

**(g) SBR-EV = core 5 + predicate-only 7, 닫는 SBR-EV = 0건.** register 실측(§1): **5행(004·006·007·009·012)이
`EV-L1/3`**(core L1 슬라이스), 7행(001·002·003·005·008·010·011)은 최소 `EV-L2`. ⇒ §1 분류는 **core(L1 슬라이스
5) / predicate-only(7) / not-Phase-1 좌표** 3분류(task 지시 count와 일치). **닫는 SBR-EV = 0건** — L1 슬라이스
저작은 EV closure가 아니다(`/3`·`+Security`·`+Broker` 통합·독립 리뷰 잔여). **truthy-sentinel 규율(#14 M1 교훈을
처음부터)**: barrier/readiness/session 결정 enum(`RecoveryBarrierState`·`ReadinessVerdict`·`SessionState`)이 전부
non-empty StrEnum이므로 **소비 게이트는 `verdict is ReadinessVerdict.READY` 명시 비교**(truthy 금지)를 §4.7·§5에
계약화하고 **`__bool__ ⇒ TypeError` 구조 봉인**을 처음부터 채택한다. self-consistency는 finishing 전 pass에서 대조.

---

## 1. 범위 매핑 — ADR-002-017 조항별 EV-L1 도달성 (닫는 SBR-EV 0건)

EV-level 정의(VER-002-001): **EV-L1 = Model and Property Verification**(state-machine exploration, model
checking, property-based testing, deterministic simulation). **EV-L2 = Component Fault Test**, **EV-L3 =
Integration/Adversarial**, **+Security = independent security-boundary assessment**(identity/credential/
authorization/fencing/bypass), **+Broker = broker-integration**. Phase 1은 EV-L1만이다.

> **결정적 사실 1 — SBR-EV ↔ SBR-AC 1:1, 최소 레벨 실측**: `SBR-EV-001..012`(EVIDENCE-REGISTER-002.md line
> 228–239 / `.csv` line 197–208)는 ADR §25 `SBR-AC-001..012`(line 636–649)와 제목·번호가 **1:1**(§25 line 634
> verbatim "map one-to-one to `SBR-EV-001` through `SBR-EV-012`"). register 최소 레벨 실측 histogram:
> **`EV-L1/3` ×5**(004·006·007·009·012) · **`EV-L2/3` ×1**(001) · **`EV-L2/3+Security` ×5**(002·003·008·010·
> 011) · **`EV-L2/3+Broker` ×1**(005). ⇒ **`EV-L1` 슬라이스 보유 5행 = core tier**(task 지시 "core 5"와 일치),
> **부재 7행(최소 ≥ L2) = predicate-only substrate**. +Security 5/12·+Broker 1/12.
>
> **결정적 사실 2 — authoring ≠ acceptance(닫는 SBR-EV = 0건)**: Phase 1은 각 SBR-EV의 **L1-decidable
> predicate/model substrate**를 저작하나 **어떤 SBR-EV도 닫지 않는다.** (a) core 5행조차 `/3` 잔여(integration/
> adversarial fault test), (b) 7행은 최소 ≥ L2 이며 5행은 +Security(독립 보안-경계 평가)·1행은 +Broker, (c)
> VER-002-001 §5 "Registration is not execution"·ADR §25 line 634 "Written cases are not completed evidence"·§28
> line 704 item 10. ⇒ **"EV-L1-complete 주장 금지"**(#12–#15 §1 규율 상속). Owner/Reviewer는 register상 TBD.

**규율 태그(모든 주장에 부착)**: "**predicate/model substrate only; SBR-EV-001..012 전부 NOT_IMPLEMENTED — core
5행은 `/3` 통합·adversarial·독립 리뷰 대기, predicate-only 7행은 EV-L2/L3 fault injection·adversarial·+Security(5)·
+Broker(1) evidence 대기. EV-L1-complete 주장 금지.**"

**SBR-EV core 5행 ↔ AC ↔ ADR 조항 매핑(실측)**:

| SBR-EV | register 제목(verbatim, md line) | 최소 레벨 | SBR-AC(1:1) | ADR 조항 앵커 | L1 substrate 술어(§5) |
|---|---|---|---|---|---|
| **004** | Complete Recovery Inventory and Obligation Closure (231) | `EV-L1/3` | AC-004(line 641 "omission creates NOT_READY") | §12 inventory·§13 obligation graph·SBR-INV-005(line 162) | `recovery_inventory_complete`·`obligation_graph_closed`·`recovery_scope_closure`(§5.1/§5.2/§5.3) |
| **006** | UNKNOWN Conflict Gap Timeout and Retry Containment (233) | `EV-L1/3` | AC-006(line 643) | §14 convergence·§19 retry·SBR-INV-006/012(line 166/190) | `unknown_stays_conservative`·`timeout_is_restrictive`(§5.4) |
| **007** | Restricted Readiness Dependency Isolation (234) | `EV-L1/3` | AC-007(line 644) | §17 partial recovery·§16·SBR-INV-008(line 174) | `restricted_isolation_proven`(§5.5) |
| **009** | Readiness Invalidation Before Authority and Egress (236) | `EV-L1/3` | AC-009(line 646) | §18 continuous invalidation·SBR-INV-011(line 186) | `readiness_invalidated_by_change`(§5.6) |
| **012** | Recovery Completion Non-Revival and Replay (239) | `EV-L1/3` | AC-012(line 649) | §21 handoff·§19·SBR-INV-014(line 198) | `recovery_completion_revives_nothing`(§5.7) |

**ADR-002-017 조항 → Phase-1 분류(core / predicate-only / not-Phase-1[형제 소유·런타임 이연])**:

| ADR 조항 | 요지 | Phase-1 분류 | L1 substrate / 소유 (근거) | SBR-EV |
|---|---|---|---|---|
| **§12** (line 316–335) | Recovery Inventory Cut — bounded·versioned·conservative | **core (L1 슬라이스)** | `recovery_inventory_complete`(§5.1) — SBR-INV-005/007. 필수 dependency 결측/unbounded ⇒ NOT_READY(line 164). "equality between two reads does not prove …"(line 333)는 broker 부분 +Broker(SBR-EV-005). `/3` 잔여. | **004** |
| **§13** (line 339–374) | Recovery Obligation Graph — 폐포·acyclicity | **core (L1 슬라이스)** | `obligation_graph_closed`(§5.2)·`recovery_scope_closure`(§5.3) — SBR-INV-005. missing/cyclic ⇒ NOT_READY(line 372); self-satisfy 금지(line 372). §8 scope-expansion(line 240). `/3` 잔여. | **004** |
| **§14/§19** (line 378–393·469–486) | Convergence·UNKNOWN·timeout·retry | **core (L1 슬라이스)** | `unknown_stays_conservative`·`timeout_is_restrictive`(§5.4) — SBR-INV-006/012. repeated identical UNKNOWN ↛ known(line 393); timeout no fallback(line 478); retry never resets uncertainty(line 486). broker convergence는 +Broker. `/3` 잔여. | **006** |
| **§17** (line 434–447) | Partial recovery — proven isolation | **core (L1 슬라이스)** | `restricted_isolation_proven`(§5.5) — SBR-INV-008. 8조건 전부 positively proven일 때만 READY_RESTRICTED(line 436–445); shared unbounded ⇒ broader NOT_READY(line 447). `/3` 잔여. | **007** |
| **§18** (line 451–465) | Continuous invalidation·readiness expiry | **core (L1 슬라이스)** | `readiness_invalidated_by_change`(§5.6) — SBR-INV-011. material change ⇒ invalidation 폐포 ⇒ barrier advance before authority(line 463); MAX age 초과/newer generation ⇒ 사용 불가(line 463). `/3` 잔여. | **009** |
| **§21/§19** (line 507–539·469–486) | Non-revival·re-arm handoff | **core (L1 슬라이스)** | `recovery_completion_revives_nothing`(§5.7) — SBR-INV-014. completion/health/evidence-repair/replay-match/human-ack ↛ revive(line 198·200); fresh governed re-arm 필수. authority/time/rcl/spg replica 동형. `/3` 잔여. | **012** |
| **§8/§9** (line 224–274) | Closed startup·barrier·fresh live-arming | **predicate-only** | `start_closed`(§6.1) — SBR-INV-001/002. barrier CLOSED 시작·new-risk denied(line 146–148). barrier ordering·fresh chain 강제는 EV-L2 component fault. 최소 `EV-L2/3`. | **001** |
| **§9** (line 246–274) | Recovery Generation propagation·stale egress reject | **predicate-only** | `stale_generation_rejected_at_egress`(§6.2) — SBR-INV-004. older-generation/unverifiable ⇒ deny(line 268). 실 egress 강제·active currentness(ADR-002-024)는 +Security. 최소 `EV-L2/3+Security`. | **002** |
| **§11** (line 299–311) | Competing recovery owner fencing | **predicate-only** | `competing_owner_fenced`(§6.3) — SBR-INV-004. stale/minority/restored/partitioned reject(line 304). 실 owner-epoch·quorum·split-brain은 +Security 런타임(line 305). 최소 `EV-L2/3+Security`. | **003** |
| **§12/§14** (line 333·387) | Non-atomic broker inventory conservatism | **predicate-only** | `non_atomic_broker_conservative`(§6.4) — SBR-INV-007. 1 query/flat/cache/absent-page/ACK ↛ completeness(line 170·172); bounded convergence(line 333). broker 의미는 +Broker(line 387). 최소 `EV-L2/3+Broker`. | **005** |
| **§15** (line 397–408) | HALT dominance·evidence failure·protective continuity | **predicate-only** | `halt_dominates_recovery`(§6.5) — SBR-INV-009. HALT 지배·ambiguous⇒applied(line 408); safety-owned protection no-cancel(line 406). 실 emergency latch·evidence journal은 +Security. 최소 `EV-L2/3+Security`. | **008** |
| **§20** (line 490–503) | Restore conflict·worst-credible union | **predicate-only** | `restore_worst_credible_union`(§6.6) — SBR-INV-013. all branches 보존(line 496); recency/backup/wall-clock ↛ 선택(line 497·503); rcl `credible_union_capacity` 소비. 실 predecessor fencing은 +Security(line 495). 최소 `EV-L2/3+Security`. | **010** |
| **§7/§21** (line 204–220·509–526) | Authority separation·forced-ready denial | **predicate-only** | `recovery_authority_separated`(§6.7) — SBR-INV-003/010. all-false authority; forced-ready reject(line 483); capacity mutate/live-auth/classify/transmit/clear-HALT 불가(line 517–526). bypass·SoD는 +Security. 최소 `EV-L2/3+Security`. | **011** |
| **§5** (line 100–140) | Definitions — 10 vocabulary | **core substrate(분산)** | 8-모델·`RecoveryBarrierState`/`SessionState`/`ReadinessVerdict`/`ObligationResult` 어휘(§2). policy governance는 spg/ADR-002-014(§8 line 112). | 001–012 공통 |
| **§9 egress·§11 owner-epoch·§12 broker-query·§14 field convergence·§20 predecessor fencing·§22 evidence** | active currentness·quorum consensus·broker page/cursor·source corroboration·DR fencing·replay | **not-Phase-1 (런타임 EV-L2/L3·+Security/+Broker)** | ADR-002-024 Currentness Vector(§9 line 272)·ADR-002-012 SCL owner-epoch(§11 line 311)·broker protocol(§27 q4)·recon/ADR-002-006(§14 line 380)·ADR-002-016 replay(§22)·failure-domain(§27 q9). sbr는 순수 술어·모델만. | 002/003/005/010/011 (런타임) |
| **§27 open questions·§4 non-scope** (line 670–688·87–96) | Recovery Barrier Policy schema·trigger classifier·obligation registry·numeric bound·human class | **not-Phase-1 (Phase-0/INSTANCE)** | 제품·알고리즘·수치·human class(ADR-002-015)는 §9.2 Phase-0. 전부 주입. | — |

---

## 2. 데이터 모델 계약

**표현 원칙**: 모든 아티팩트는 **pydantic v2 frozen 모델**(`ConfigDict(frozen=True, extra="forbid")`, canonical
`FrozenModel` `_base.py:73` 상속). 어휘는 **StrEnum**(non-empty value·`__bool__ ⇒ TypeError` 봉인 §4.7). numeric
bound 부재(전부 주입 opaque param §8). id·digest 분류는 §2.1.

### 2.1 digest-bound / value / reference 분류 (총괄)

| 아티팩트 | 분류 | id⊥digest? | 근거 |
|---|---|---|---|
| `RecoveryReadinessDecision` | **`IndependentIdArtifact`** (id⊥digest) | **예** | §16 line 416 "decision identity, canonical digest, issuer" — issuer가 decision_id 발급·canonical digest 별도. same-id/diff-bytes(readiness substitution·stale decision replay §22 line 554) 탐지에 `classify_record_pair`(`RecordPairKind.CRITICAL_CONFLICT`) 필요. are `AggregateRiskDecision`(`are/records.py:451`)·iap `IndependentApprovalDecision`(#15 §0.4d) 동형. |
| `RecoveryEvidencePackage` | **`IndependentIdArtifact`** (id⊥digest) | **예** | §9 line 134 "immutable canonical manifest"·§16 line 416 "Package … digests". session이 package_id 발급·canonical manifest digest 별도. package substitution 탐지. |
| `RecoveryInventoryCut` | **`DigestBoundArtifact`** (id=f(digest)) | 아니오 | §5.7 line 126–128 "bounded, versioned set … conservative evidence". content-addressed — 동일 revision-set/observation ⇒ 동일 cut(§12 digest binding). |
| `RecoveryObligation` | **`DigestBoundArtifact`** | 아니오 | §5.8 line 130 "one mandatory, typed predicate with owner, scope, evidence rule". content-addressed obligation spec. |
| `RecoverySession` | **`IndependentIdArtifact`** (id⊥digest) | **예** | §5.4 line 114 "immutable-identity workflow instance". transition log는 append-only(§10 line 293). "Retry creates a new session identity"(line 293) — id는 발급, transition-prefix digest 별도. |
| `RecoveryGeneration` | **`tos.ordering` REUSE** | — | §5.5 line 118–120 "monotonic generation that fences". `tos.ordering.Ordering`/`compare_order`(`__init__.py:19`)로 monotonic 순서(newer invalidates older, line 120). §2.2. |
| `RecoveryTrigger` | **`DigestBoundArtifact`** | 아니오 | §5.1 line 104·§9 line 261 "unique trigger identity and conservative initial scope". content-addressed trigger. |
| `RecoveryBarrierState` | **StrEnum(어휘)** | — | §9 line 250–255 4-값. §2.2. |

### 2.2 어휘 (verbatim 전사 — 차원 비붕괴)

**(1) `RecoveryBarrierState`** — §9 line 250–255 verbatim 4-값: `CLOSED_NON_LIVE`·`CLOSED_RECOVERY`·
`CLOSED_CONTAINED`·`CLOSED_HALTED`. ADR line 257 verbatim: "These names describe new-risk **denial context**, not
permission. **No barrier state alone permits live transmission**." ⇒ **enum 어느 값도 truthy 소비 불가** —
`__bool__ ⇒ TypeError` 봉인(§4.7). barrier 값은 **denial-context 라벨**이지 authority가 아니다(§0.1.6).

**(2) `SessionState`** — §10 line 280–291 verbatim 전이 노드: `TRIGGERED`·`FENCING`·`INVENTORYING`·`RECONCILING`·
`VALIDATING`·`DECISION_CANDIDATE`·`READY`·`READY_RESTRICTED`·`NOT_READY`·`INVALIDATED`·`ABORTED`·`EXPIRED`·
`SUPERSEDED`. 전이표는 §2.2(3)·§4.2. line 293 verbatim: "`ABORTED`, `INVALIDATED`, `EXPIRED`, `SUPERSEDED`, and
`NOT_READY` **cannot transition to a ready state**." (terminal non-revival).

**(3) 세션 전이표(§10 line 281–291 verbatim 전사 — arrow table, #12 spg 선례 동형)**:

```text
TRIGGERED -> FENCING -> INVENTORYING -> RECONCILING -> VALIDATING -> DECISION_CANDIDATE
DECISION_CANDIDATE -> {READY | READY_RESTRICTED | NOT_READY}
{TRIGGERED..DECISION_CANDIDATE} -> {INVALIDATED | ABORTED | SUPERSEDED}
{READY, READY_RESTRICTED}       -> {INVALIDATED | EXPIRED | SUPERSEDED}
```

`_SESSION_TRANSITIONS: frozenset[tuple[SessionState, SessionState]]`로 저작(spg `_ENVELOPE_TRANSITIONS`
`predicates.py:78` 동형). **terminal 집합**({`NOT_READY`·`INVALIDATED`·`ABORTED`·`EXPIRED`·`SUPERSEDED`})은
**ready로의 outgoing arrow 없음**(line 293 non-revival). 미등재 쌍은 전부 `False`(fail-closed 순수 set membership).

**(4) `ReadinessVerdict`** — §16 line 419 verbatim 3-값: `READY`·`READY_RESTRICTED`·`NOT_READY`. line 426 "`READY`
requires all obligations for the exact requested scope to pass with no blocking Critical hazard"·line 430
"`NOT_READY` … cannot be manually promoted; a new session and evidence package are required." **차원 비붕괴 주의**:
`ReadinessVerdict.NOT_READY` ≠ `SessionState.NOT_READY`가 아니라 **동일 개념의 두 표현**(session terminal이자
decision verdict) — 본 계약은 **decision verdict를 `ReadinessVerdict`로, session 상태를 `SessionState`로 분리**하고
런타임이 둘을 함께 commit한다(readiness는 session의 산출, §16). `__bool__ ⇒ TypeError` 봉인.

**(5) `ObligationResult`** — §13 line 346 "acceptable result classes"·§14 line 384 "terminal confidence/result": 
`SATISFIED`·`FAILED`·`UNKNOWN`·`TIMED_OUT`·`CONFLICTED`·`MISSING_SOURCE`. **`SATISFIED`만 obligation을 통과**시키며
(`is ObligationResult.SATISFIED` §4.7) 나머지는 전부 non-satisfied(conservative). recon `FieldConfidenceClass`
(UNKNOWN/SINGLE_SOURCE/CORROBORATED/CONFLICTED/STALE)와 **혼동 금지** — `ObligationResult`는 obligation 수준,
`FieldConfidenceClass`는 recon field 수준(§3.5). SBR는 recon 결과를 obligation 결과로 **fold**하되 재정의하지 않음.

**(6) `RecoveryMode`** — §15 line 397–404: `RECOVERY`(new risk prohibited)·`CONTAINED`·`HALTED`(§9 barrier
context와 정합). `TriggerClass`(§8 line 226–238의 트리거 taxonomy)는 **주입 enum-token**(classifier는 Phase-0 §27
q1 — SBR는 분류 결과만 소비, 재분류 안 함).

### 2.3 아티팩트 covered + self-exclusion (설계 #4 §3.3 상속)

`RecoveryEvidencePackage`·`RecoveryReadinessDecision`은 자신의 canonical digest를 covered-set에서 **제외**한다
(self-reference paradox 회피, canonical `IndependentIdArtifact` 규약). `RecoveryInventoryCut`이 binding하는 revision/
observation digest 집합은 cut 자신의 digest를 제외한 **입력 아티팩트 digest만** 포함. §20 restore 시 conflicting
branch는 **전부 covered**(worst-credible union, line 496)이되 어느 하나도 self-authority가 되지 않음(§6.6).

### 2.4 핵심 모델 필드 골격 (§ref·형제 seam 표기)

- **`RecoveryInventoryCut`**(§12 line 318–331): `session_id`·`recovery_generation`·`scope_digest`·`trigger_digest`·
  `policy_digest`·`dependency_graph_digest`(line 320)·`time_start`/`time_end`/`time_uncertainty`(line 321, **주입
  opaque** — clock 미접근 §8)·`rcl_committed_revision`/`writer_epoch`/`restore_generation`/`state_digest`/
  `open_allocations`(line 322, **rcl 주입 scalar** §3.5)·`authority_epoch`/`currentness`/`halt_generation`(line
  323)·intent/attempt/order/fill/cancel/replace/FQP lineage(line 323–324, **orthostate/recon 주입**)·position/
  balance/margin/collateral(line 325)·external/non-trade(line 326)·protective(line 327, **protective 주입**)·
  profile/broker/software/schema/identity/credential/route(line 328)·source-continuity/page-cursor/evidence-
  confidence/gaps(line 329)·CII/Context-Generation(line 330, **capsule 주입**)·**`observed_events`**(line 331,
  cut 중 전 event)·**`unobserved_window_assumptions`/`max_adverse_bounds`/`required_repeat_observations`**(line
  332). **완전성 술어는 §5.1** — 한 필드라도 결측/unbounded ⇒ NOT_READY.
- **`RecoveryObligation`**(§13 line 343–350): `obligation_id`·`obligation_type`·`owner`·`scope`·`hazard`·
  `priority`(line 343)·**`prerequisite_ids: frozenset[str]`**(line 344, 폐포 입력)·`source_digests`(line 344)·
  `input_evidence_digests`/`inventory_cut_position`(line 345)·`proof_rule_digest`/`conservative_bound`/
  `acceptable_results: frozenset[ObligationResult]`(line 346)·`invalidation_conditions`/`max_age`(line 347)·
  `failure_response`/`timeout_response`/`conflict_response`/`missing_source_response`(line 348)·`scope_restriction`/
  `residual_risk`(line 349)·`result: ObligationResult`·`evidence_records`/`independent_review_required: bool`(line
  350). **폐포·acyclicity 술어는 §5.2**.
- **`RecoveryReadinessDecision`**(§16 line 416–424): `decision_id`⊥`canonical_digest`·`issuer`·`session_id`·
  `recovery_generation`·`policy_digest`·`scope`·`requested_rearm_scope`(line 416)·`package_digest`/
  `inventory_cut_digest`(line 417)·`obligation_set_digest`/`all_results`(line 418)·**`verdict: ReadinessVerdict`**
  (line 419)·`max_safe_scope`/`excluded_scopes: frozenset`(line 420)·전 UNKNOWN/external/non-trade/protective/…/
  residual state(line 421)·`issue_time`/`max_age`/`expiry`/`invalidation_conditions`(line 422)·generation
  vector(line 423, RCL/authority/HALT/profile/broker/deployment/release/post-trade/egress/evidence/human — **전부
  주입 scalar**)·**`authority_effect: RecoveryAuthorityEffect`(all-false, line 424 explicit no-authority)**. §6.7.

---

## 3. canonical / ordering REUSE + sibling edge 0 + 형제 경계

### 3.1 canonical REUSE

`tos.canonical`에서 REUSE(실측 slot): `FrozenModel`(`_base.py:73`)·`DigestBoundArtifact`(`_base.py:98`,
inventory/obligation/trigger)·`IndependentIdArtifact`(`_base.py:328`, session/package/decision — id⊥digest)·
`classify_record_pair`(`record_pair.py:52`)+`RecordPairKind`(`record_pair.py:31`, §20 restore-branch conflict·
readiness substitution 탐지)·`ArtifactStatus`(`_base.py:58`)·`EVL1ProvisionalCanonicalizer`(`canonicalization.py:173`,
잠정 canonical form — 프로덕션 schema는 Phase-0 §9.2). **`IdDerivedArtifact` 미채택**(대부분 — decision/package/
session은 발급 identity ⊥ digest; inventory/obligation/trigger만 content-addressed).

### 3.2 ordering REUSE (Recovery Generation monotonic 순서)

`tos.ordering`에서 REUSE: `Ordering`·`OrderingEvent`·`compare_order`(`__init__.py:19`). **Recovery Generation**
(§5.5 line 118–120 "monotonic generation … A newer generation invalidates every older in-progress or terminal
readiness artifact")은 append-only monotonic 순서 — `compare_order`로 "newer invalidates older" 판정(§6.2
stale-generation-reject·§6.3 owner fencing). 실측: `ordering/_ordering.py:38` `from tos.canonical import
FrozenModel`만 의존이라 core(sibling edge 무증가). authority `GenerationVector.recovery_generation`(int scalar,
`state.py:50`)은 이 순서의 **투영 좌표**(§0.4e).

### 3.3 REUSE 요약 표

| REUSE 대상 | 출처 | 용도(§ref) | edge |
|---|---|---|---|
| `FrozenModel`·`DigestBoundArtifact`·`IndependentIdArtifact`·`classify_record_pair`·`ArtifactStatus`·`EVL1ProvisionalCanonicalizer` | `tos.canonical` | 8-모델 base·§20 conflict 탐지 | core(단방향) |
| `Ordering`·`compare_order` | `tos.ordering` | Recovery Generation monotonic(§6.2/§6.3) | core(단방향) |
| **(형제 타입 REUSE 0건)** | — | 전 형제 상호작용 = injected scalar/bool/enum-token/verdict(§3.4) | **sibling edge 0** |

### 3.4 형제 경계 — scalar·bool·enum-token·verdict seam (edge 0, 코드 실측)

SBR는 recovery orchestrator로서 **형제 결과를 대량 소비**하나, liveauth 선례(injected bool)로 **edge 0**을
유지한다. 각 seam은 **런타임 Recovery Coordinator가 형제 술어를 호출 → 결과를 SBR 순수 모델에 주입**하는 형태
(sibling 서사 아님 — #10 MAJOR 교훈. 전 slot file:line 실측):

| SBR 소비/생산 (§ref) | 타입 | 상대 (이미 비준·구현) | signature(실측) |
|---|---|---|---|
| orthostate `reconstruct_conservative`(per-dimension conservative restart) **소비** | `CompositeState`→`CompositeState`(주입 결과) | orthostate `reconstruct_conservative`(`predicates.py`, `def reconstruct_conservative(pre: CompositeState) -> CompositeState`) | Knowledge codomain **structurally excludes `RECONCILED`**(`predicates.py:23-24`, STATE-EV-004 substrate) — 재구성은 절대 "proven reconciled" 산출 안 함; SBR은 §14 RECONCILING 시 이 결과를 obligation 입력으로 fold(§3.5) |
| recon `classify_field`/`FieldConfidenceClass` **소비** | enum-token(주입) | recon `classify_field`(`predicates.py:107`)→`FieldConfidenceClass`(UNKNOWN/SINGLE_SOURCE/CORROBORATED/CONFLICTED/STALE) | §14 line 380 "ADR-002-006 Reconciliation Service results remain authoritative for confidence"; SBR는 per-field 결과를 obligation 결과로 fold·**no-blend**(recon `predicates.py:10-11` "no numeric confidence score") |
| rcl fence/committed-prefix/`partition_verdict`/`credible_union_capacity`/`QUARANTINED_UNKNOWN` **소비** | scalar/verdict/enum(주입) | rcl `partition_verdict`(`predicates.py:711`)·`credible_union_capacity`(`predicates.py:739`)·`CapacityState.QUARANTINED_UNKNOWN`(`vocabulary.py:29`, rank 8 `predicates.py:434`)·fence(`predicates.py:515-550` restore_generation/writer_epoch) | §13 obligation 2(RCL committed prefix line 356)·§20 worst-credible union(line 498) 소비; capacity mutate는 **rcl only**(SBR-INV-010) |
| protective `dominating_halt_or_incident`/`ProtectiveOwnership.SAFETY_OWNED` **소비** | bool/enum(주입) | protective `dominating_halt_or_incident`(`records.py:202`, admissibility는 `predicates.py:395` `is False`)·`ProtectiveOwnership.SAFETY_OWNED`(`predicates.py:570`) | §15 HALT 지배·safety-owned no-cancel(line 406) 소비; classification은 **protective only** |
| authority/time/rcl/spg `*_revives_nothing` **선례 상속(replica)** | (술어 pattern) | authority `recovery_generation_revives_nothing`(`predicates.py:787`, 무조건 `True`)·rcl(`predicates.py:802`; docstring `:26`)·time·spg `rollback_revives_nothing`(`__init__.py:90`)·`expiry_revives_nothing`(`:81`) | §21/§19 non-revival(§5.7)은 이 replica pattern으로 로컬 저작(§0.4d) |
| `recovery_coordinator_evidence_complete` **생산**(→ re-arm 소비) | `bool`(scalar) | authority `_REARM_PREREQUISITES` item 12(`predicates.py:108`)·field `state.py:133`·소비 `getattr(checklist, name) is True`(`predicates.py:769`) | §21 handoff — SBR readiness가 이 bool 생산, authority/liveauth re-arm이 **`is True`로 소비**(§3.5) |
| `recovery_current`·`recovery_readiness_enlarged` **생산**(→ liveauth 소비) | `bool|None`(scalar) | liveauth `recovery_current`(`state.py:139`)·`recovery_readiness_enlarged`(`state.py:208`) | §18 continuous validity·in-place expansion; liveauth가 injected bool로 소비(edge 0 선례) |
| `recovery_generation` **생산/좌표 소유**(→ authority carry) | `int`(scalar) | authority `GenerationVector.recovery_generation`(`state.py:50`, reference-only — `state.py:42-43` "their owning ADR fences them") | §0.4e — SBR이 fence 의미 소유, authority carry |
| capsule/CII `DecisionContextCapsule`·`CriticalInputSnapshot` **소비** | `str`(id/digest, 주입) | capsule `DecisionContextCapsule`(`capsule.py:170`)·`CriticalInputSnapshot`(`snapshot.py:96`) | §13 obligation 7(CII line 360)·§12 line 330 inventory binding(id+digest scalar) |
| AFG(ADR-002-022, #16 세션 B) rate/budget/permit **injection slot** | `tos/src/tos/afg/` 구현 완료(비준 2026-07-26) — **그래도 주입 slot**(edge 0) | ADR-002-022 원문(SBR ADR §13 obligation 11 line 364·§28 item 15 line 709) | §19 retry containment·SBR-EV-006 retry 좌표가 AFG budget과 인접; **구현 실재하나 sibling-edge-0 규율로 import 아닌 injection 소비**(v1.1 MAJOR-2 정정; §0.2·§3.5) |

### 3.5 소유권 분할표 — sbr가 소유 / 형제에서 소비·생산 (본 문서 최대 함정 지대, #11–#15 §3.5 상속)

> **소유권 분할 명시(#8·#11–#15 교훈 — cross-section 혼동 선제 봉합)**: ADR-002-017은 **recovery barrier·session·
> inventory cut·obligation graph·readiness decision·invalidation orchestration**만 결정하며(§4 line 74–85)
> **state reconstruction(orthostate)·per-field confidence(recon/ADR-002-006)·capacity mutation(rcl)·protective
> classification(protective)·re-arm checklist(authority/liveauth)·Live Authorization(liveauth)·final egress
> (ADR-002-013)·human approval(ADR-002-015)·evidence replay engine(ADR-002-016)를 소유하지 않는다**. 함정: SBR이
> orthostate의 state 재구성·recon의 confidence·rcl의 capacity·authority의 re-arm checklist를 재저작하면 권위
> 중복(#8 lesson). 아래 표가 경계를 코드 실측으로 고정한다.

| ADR 조항/개념 | sbr 소유 (Phase 1) | 형제 소유 (재저작 금지) | seam 방향(실측) |
|---|---|---|---|
| §10 Recovery Session | `RecoverySession`·`SessionState`·`_SESSION_TRANSITIONS`(§2.2) | (session 상태기계는 SBR 고유) | session은 SBR 발행; transition append-only(§4.2) |
| §12 Inventory Cut 완전성 | `RecoveryInventoryCut`·`recovery_inventory_complete`(§5.1) | 각 필드 값의 **판정**은 형제 소유(orthostate state·recon confidence·rcl capacity) | SBR은 완전성(결측 여부)만; 값 판정은 주입 결과 |
| §13 Obligation Graph 폐포 | `RecoveryObligationGraph`·`obligation_graph_closed`·`recovery_scope_closure`(§5.2/§5.3) | obligation의 **owner**는 형제(line 343 "owner"); obligation **result**는 형제 술어 산출 | SBR은 graph 완전성+acyclicity; per-obligation 판정은 주입 |
| §14 state reconstruction | (미소유 — orthostate 소유) | **orthostate `reconstruct_conservative`(`predicates.py`, codomain excludes RECONCILED)** | SBR RECONCILING이 orthostate 결과를 obligation 입력으로 fold; **재구성 재저작 금지**(§3.4) |
| §14 per-field confidence | (미소유 — recon 소유) | **recon `classify_field`/`FieldConfidenceClass`(`predicates.py:107`)** | SBR convergence(§5.4)가 recon 결과 fold·**no-blend**; confidence declare 금지(line 380) |
| §8/§18 scope/invalidation closure | `recovery_scope_closure`·`readiness_invalidated_by_change`(§5.3/§5.6) — **로컬 저작** | (iap `invalidation_closure`는 규율 선례이지 소유 아님·**import 금지**) | 순수 그래프 도달성; iap 동형 규율 상속(§0.4d) |
| §12 committed prefix·§20 union | (미소유 — rcl 소유) | **rcl fence/`credible_union_capacity`(`predicates.py:739`)/`partition_verdict`(`:711`)/`QUARANTINED_UNKNOWN`** | SBR은 rcl verdict 소비; capacity mutate/release는 **rcl only**(SBR-INV-010 line 182) |
| §15 HALT dominance | `halt_dominates_recovery`(§6.5) — 순수 술어 계약 | **protective `dominating_halt_or_incident`(`records.py:202`)·Cancellation Arbiter(ADR-002-011)** | SBR은 HALT 지배 술어; classification/cancel은 protective |
| §16 readiness decision | `RecoveryReadinessDecision`·`ReadinessVerdict`·all-false authority(§2.4/§6.7) | (readiness는 SBR 고유·**non-authorizing** line 424) | SBR 발행; authority는 아님(SBR-INV-003) |
| §21 re-arm checklist | (미소유 — authority/liveauth 소유) | **authority `_REARM_PREREQUISITES`(14-item, `predicates.py:96`)·liveauth `rearm_admissible`** | SBR은 `recovery_coordinator_evidence_complete` bool **생산**; re-arm은 하류가 `is True` 소비(§3.4) |
| §21 Live Authorization | (미소유 — liveauth 소유) | **liveauth `LiveAuthorization`(`records.py:112`)** | readiness → re-arm request → approval → live auth(handoff 순서 line 528–537); SBR은 첫 단계만 |
| §20 restore/non-revival | `restore_worst_credible_union`·`recovery_completion_revives_nothing`(§6.6/§5.7) | spg `rollback_revives_nothing`/`rollback_requires_new_generation`(`__init__.py:89-90`) **선례** | SBR replica 저작(§0.4d); restore-generation fence는 rcl(spg `records.py:286`) |
| §22 evidence | (레코드 substrate만) | **ADR-002-016 evidence replay ENGINE·custody** | SBR은 decision/package/session 레코드; replay는 하류 |
| §19 retry / AFG budget | `timeout_is_restrictive`(§5.4) — retry never resets uncertainty | **AFG(ADR-002-022, #16 세션 B) rate/budget/permit** — 구현 완료·injection slot | §13 obligation 11 주입 slot(line 364); **구현 실재하나 edge-0 규율로 injection 소비**(v1.1) |

> **핵심 판정 1 — `ObligationResult` ≠ recon `FieldConfidenceClass`(차원 비붕괴 봉합)**: SBR obligation은 **satisfied
> 여부**(`SATISFIED`/`FAILED`/`UNKNOWN`/…)를 판정하고, recon field는 **confidence class**(CORROBORATED/CONFLICTED/…)를
> 판정한다. SBR은 recon field 결과를 obligation 입력으로 **fold**하되(§5.4) — 예: 어떤 field가 `CONFLICTED`면 그
> field에 걸린 obligation은 `SATISFIED` 불가 — **재정의하지 않는다**. 이 구분을 흐리면 "SBR이 confidence를 계산한다"는
> **오판**(권위 중복 §14 line 380). 리뷰어 공격 지점 §10.2 (iv).

> **핵심 판정 2 — SBR readiness는 re-arm의 전제 생산자이지 re-arm이 아니다(§21 handoff 경계)**: authority
> `_REARM_PREREQUISITES`(14-item)의 item 12 `recovery_coordinator_evidence_complete`(`predicates.py:108`)를 SBR
> readiness가 **생산**하고, 나머지 13 environmental prerequisite 중 다수(`account_wide_reconciliation_complete`·
> `unknown_orders_resolved`·`unattributed_external_activity_resolved`·`risk_capacity_ledger_consistency_verified`·
> `protective_leases_reconciled`·`stale_epochs_fenced`)도 SBR obligation 결과가 **feed**한다(§13 obligation 1–6).
> 그러나 **re-arm admissibility 판정 자체는 authority/liveauth 소유**(`getattr(checklist, name) is True for name in
> _REARM_PREREQUISITES` `predicates.py:769`) — SBR은 checklist를 재저작하지 않는다. handoff 순서(§21 line 528–537):
> `readiness → exact re-arm request → human quorum → new Live Auth → new capability → egress`. **각 단계가 current
> Recovery Generation 재검증**(line 539); SBR readiness는 **첫 입력**이지 permission이 아니다(SBR-INV-003·-014).
> **`recovery_coordinator_evidence_complete=True` 조차 re-arm을 자동화하지 않는다** — 그것은 14개 중 하나일 뿐이고
> `fresh_live_authorization_issued`·`explicit_human_dual_control_complete`가 남는다(SBR-INV-014 line 198 "fresh
> governed re-arm is mandatory"). 리뷰어 공격 지점 §10.2 (v).

> **핵심 판정 3 — `recovery_generation` 좌표 소유(authority carry vs SBR fence)**: authority
> `GenerationVector.recovery_generation`(`state.py:50`)은 **reference-only scalar**(`state.py:42-43` "the rest are
> reference-only scalars … their owning ADR fences them"). ⇒ **SBR이 fence 의미를 소유**(§9 egress rejection·§18
> invalidation), authority는 non-collapsing 좌표로 carry만. §4.3 canary 상속 — recovery_generation을 다른 좌표
> (safety_authority_epoch 등)로 대체하면 fence 불성립. **누가 recovery_generation을 advance하는가**: §7 line 208
> "Safety Control Plane ordered recovery namespace"(ADR-002-012 SCL 별도 non-capacity namespace, §11 line 311) —
> SBR은 그 순서 substrate를 **소비**(ordering REUSE)하되 SCL commit 자체는 런타임(§9.2). 리뷰어 공격 지점 §10.2 (vi).

---

## 4. 불변식

모두 frozen 모델 구성-불변식(구성 실패) 또는 순수 술어(property)로 실현한다. **앵커는 SBR-INV-001..014(§6)·
SBR-AC-001..012(§25)·§-clause·SAFE-###**이며 **새 시리즈를 창작하지 않는다**(§0.4f). **fail-closed discipline**:
미증명/결측/None/stale/unknown/unbounded/conflicting에 대한 술어는 절대 vacuous permissive/READY가 되지 않으며,
READY 자격은 *양성 증명*을 요구하고, 각 가드에 **both-ways canary**(가드 발화 + 정당 통과 미차단)를 붙인다.

### 4.1 complete inventory·obligation closure 중앙 불변식 (core — ADR §12/§13; SBR-INV-005; SBR-AC-004)

**중앙 결정**: `recovery_inventory_complete` ∧ `obligation_graph_closed`는 §12 line 318–331 전 dependency가
present ∧ bounded ∧ 각 obligation의 prerequisite가 present(dangling 부재) ∧ acyclic ∧ 각 obligation result가
terminal-conservative일 때만 READY 후보. SBR-INV-005 line 162 verbatim: "Recovery cannot be ready while any
required order, attempt, fill, position, capacity, external, non-trade, protective, broker, or evidence dependency
is **omitted or unbounded**." 실현(구조적):

1. **permissive 기본값 부재**: §12 전 필드가 완비될 때만 통과. 한 필드라도 absent/None/unbounded/stale ⇒ **불완전
   ⇒ NOT_READY**(§13 line 372 "Missing or cyclic obligation dependencies make the session NOT_READY"; SBR-AC-004
   line 641 "omission creates NOT_READY"). "assume-complete" 경로 부재(#6 fail-open 교훈).
2. **폐포·acyclicity(§13 line 372)**: obligation prerequisite 그래프는 (a) 모든 prerequisite_id가 obligation set에
   존재(dangling ⇒ NOT_READY), (b) cycle 부재(topological sort 성공), (c) 각 obligation `result ∈ acceptable_results`
   ∧ terminal. **self-satisfy 금지**(line 372 "An obligation cannot be marked satisfied by its own proposing
   component where independent evidence is required") — `independent_review_required=True`인 obligation은 proposing
   owner가 satisfied 처리 못 함.
3. **scope expansion(§8 line 240)**: `recovery_scope_closure`가 dependency graph에서 trigger scope의 도달성 폐포를
   계산 — unknown edge ⇒ **containing account/broader Safety Cell로 확장**(line 240 "Unknown dependency mapping
   expands"), isolation positively proven인 edge만 제외(line 242 "narrow only after evidence proves").

**canary(both-ways)**: (a) 필수 dependency 하나 결측·prerequisite dangling·cycle 주입·obligation result=UNKNOWN
⇒ NOT_READY(가드 발화; SBR-AC-004); (b) 전 §12 dependency present·bounded·prerequisite 완비·acyclic·전 result
SATISFIED ⇒ READY 후보(양성 side — 정당한 완비 recovery를 막지 않음). **∅ 양방향**: 빈 obligation set은 "nothing to
prove" 아님 — 최소 obligation set(§13 line 352–370, 17항)이 강제되므로 빈 set ⇒ 불완전(§4.7).

### 4.2 session 상태기계 중앙 불변식 (core substrate — ADR §10; SBR-INV-013)

**중앙 결정**: `_SESSION_TRANSITIONS`(§2.2(3))는 §10 line 281–291 arrow만 허용. line 293 verbatim: "`ABORTED`,
`INVALIDATED`, `EXPIRED`, `SUPERSEDED`, and `NOT_READY` cannot transition to a ready state." 실현:

1. **monotonic append-only(§10 line 293)**: 전이는 append-only·authenticated·current Recovery Generation binding.
   terminal 집합은 outgoing arrow 없음(순수 set membership; 미등재 쌍 `False`).
2. **retry = 새 session identity(§10 line 293)**: "Retry creates a new session identity." old session의 상태를
   재활성화하지 않음(§5.7 non-revival과 정합).
3. **economic effect survives(SBR-INV-013 line 194)**: "Session completion, cancellation, timeout, failover,
   decision expiry, evidence expiry, or restore never expires orders, attempts, exposure, UNKNOWN, or capacity
   commitments." session terminal ↛ economic lifetime 종료(§6.6).

**canary(both-ways)**: (a) `NOT_READY -> READY`·`ABORTED -> READY` 시도 ⇒ `False`(가드 발화); (b) `TRIGGERED ->
FENCING -> … -> DECISION_CANDIDATE -> READY` 정당 경로 ⇒ 통과(양성 side).

### 4.3 recovery generation fencing 중앙 불변식 (core+predicate — ADR §9/§11; SBR-INV-004; SBR-AC-002/003)

**중앙 결정**: `stale_generation_rejected_at_egress`(§6.2)·`competing_owner_fenced`(§6.3)는 current Recovery
Generation을 **active하게** 확립하지 못하면 deny. SBR-INV-004 line 158–160 verbatim: "Only the current fenced
Recovery Coordinator generation may publish a candidate decision; stale, minority, restored, duplicated, or
resumed workers grant nothing. … Cache TTL, process health, heartbeat, eventual delivery, or last-observed state
cannot prove currentness; inability to actively establish current state at authority issuance or final egress is
**denial**." 실현:

1. **좌표 non-collapse(§0.4e canary)**: `recovery_generation`을 다른 generation 좌표로 대체해도 fence 불성립
   (authority `predicates.py` "substituting one coordinate's value for another never satisfies a fence" 상속).
2. **active currentness(line 160·270)**: cache/TTL/heartbeat/absence ↛ currentness. `compare_order`로 older-
   generation reject(§6.2). 실 active currentness 프로토콜은 ADR-002-024(런타임 +Security §6.2).
3. **one current owner(§11 line 303–304)**: overlapping scope는 한 owner만; stale/minority/restored/partitioned
   reject(line 304). owner-epoch fencing 실 구현은 ADR-002-012 SCL(런타임 §9.2).

**canary(both-ways)**: (a) older generation·좌표 치환·unverifiable current ⇒ reject(가드 발화; SBR-AC-002); (b)
current fenced generation·verified ⇒ 통과. 집합 양방향(§4.7): stale owner 결측 검사 + spurious owner(다른 scope) 검사.

### 4.4 restricted isolation 중앙 불변식 (core — ADR §17; SBR-INV-008; SBR-AC-007)

**중앙 결정**: `restricted_isolation_proven`(§5.5)은 §17 line 436–445 **8조건 전부 positively proven**일 때만
READY_RESTRICTED. SBR-INV-008 line 174 verbatim: "READY_RESTRICTED cannot exclude unresolved shared capacity,
aggregate limits, broker sessions, credentials, routes, protective dependencies, or common failure domains." 실현:

1. **8조건 전수 양성(§17 line 438–445)**: distinct Capacity Domain·broker session/credential/route isolation·
   margin/collateral safe·no protective boundary crossing·config/authority/time/deployment compatible·external/
   non-trade unmappable·final egress가 exact scope 강제 가능·Hard Safety Envelope 만족. 하나라도 미증명 ⇒ broader
   NOT_READY.
2. **negative 증거 불충분(§17 line 447)**: "Logical strategy separation, different UI labels, separate recovery
   tickets, distinct process instances, or unused nominal capacity do not prove isolation." — label/ticket/instance는
   isolation 아님(§4.7 금지 동사 `assume-isolated`).
3. **not weaker proof(§16 line 428)**: "It is not a weaker proof level for included scope." — included scope는 full
   proof, excluded는 new-risk denied.

**canary(both-ways)**: (a) shared capacity unbounded·label만으로 isolation 주장 ⇒ broader NOT_READY(가드 발화;
SBR-AC-007); (b) 8조건 전수 양성 ⇒ READY_RESTRICTED(양성 side — 정당 격리를 막지 않음).

### 4.5 continuous invalidation 중앙 불변식 (core — ADR §18; SBR-INV-011; SBR-AC-009)

**중앙 결정**: `readiness_invalidated_by_change`(§5.6)는 §18 line 453–461 material change 집합 중 하나라도 발생 시
영향받는 readiness의 invalidation 폐포를 계산해 **barrier advance before authority/egress**. SBR-INV-011 line 186
verbatim: "Any relevant state, evidence, generation, policy, configuration, identity, broker, route, credential,
time, protection, or scope change invalidates the affected readiness decision **before future authority issuance**."
실현:

1. **material change 폐포(§18 line 453–461)**: trigger/scope/graph/policy/inventory·RCL·broker·non-trade·authority/
   HALT/time/profile·protection·evidence 변경 → `readiness_invalidated_by_change`가 iap-동형 도달성 폐포로 영향
   readiness 전부 포착(§0.4d·§5.6).
2. **expiry restrictive(§18 line 463)**: cached readiness는 `MAX_recovery_readiness_age` 초과 또는 newer generation
   관측 시 사용 불가; "Expiry is restrictive and does not affect economic lifetime." (§6.6).
3. **incident handoff(§18 line 465)**: ADR-002-027 Incident Recovery Handoff Package는 current session이 exact
   package digest+scope를 **명시 수락**할 때만 obligation 이전; 행정적 incident closure ↛ barrier open. (§9.2 —
   handoff bound `B_incident_handoff_to_recovery_barrier` line 443).

**canary(both-ways)**: (a) post-cut fill·profile change·newer generation ⇒ 영향 readiness invalidated(가드 발화;
SBR-AC-009); (b) 무변경 window ⇒ readiness 유효(양성 side, max-age 내). ∅ 양방향: 빈 change-set ⇒ 최소 폐포
{trigger}(§4.7).

### 4.6 non-revival + economic-continuity + all-false authority 불변식 (core+predicate — ADR §21/§19/§20/§7)

**중앙 결정**: `recovery_completion_revives_nothing`(§5.7, 무조건 True)·`restore_worst_credible_union`(§6.6)·
`recovery_authority_separated`(§6.7, all-false). SBR-INV-014 line 198 verbatim: "Recovery completion, health
restoration, human acknowledgement, replay match, or evidence repair never revives prior authority; fresh governed
re-arm is mandatory." SBR-INV-003 line 154 verbatim: "No Recovery Session, package, obligation result, readiness
decision, operator action, health result, or replay result creates capacity, Live Authorization, capability,
protective classification, broker transmission, or re-arm permission." 실현:

1. **non-revival 무조건(§21 line 526·§19 line 486)**: 5 revival vector(completion/health/evidence-repair/replay-
   match/human-ack) 전부 ↛ revive. `recovery_completion_revives_nothing`은 **revival path의 구조적 부재를 문서화**
   (authority `predicates.py:801` replica pattern — 무조건 `True`).
2. **all-false authority(SBR-INV-003)**: `RecoveryAuthorityEffect`는 전 필드 `False`(capacity/live-auth/capability/
   protective/transmission/re-arm 전부 불가). rcl `AllFalseAuthority`(`_base.py:55`) 동형. **`__bool__ ⇒ TypeError`
   불요**(bool 필드 집합이지 verdict enum 아님) — 대신 각 필드가 `False` 상수임을 구성-불변식으로 봉인.
3. **economic continuity(SBR-INV-013 line 194·§20 line 498)**: restore worst-credible union은 all branches 보존·
   worst credible economic union 계산(rcl `credible_union_capacity` 소비); recency/backup/wall-clock ↛ branch 선택
   (line 497·503).

**canary(both-ways)**: (a) generation N+1 후 old capability revive 시도·operator forced-ready·replay-match ⇒
차단(가드 발화; SBR-AC-011/012); (b) fresh governed re-arm chain ⇒ 새 authority(양성 side, SBR 밖).

### 4.7 ∅-공허 fail-closed + truthy-sentinel 소비 계약 (양방향 명시 — #10/#12 ∅-void·#14 M1 truthy-sentinel 교훈)

**(가) ∅-공허 양방향**: 빈 입력의 **모든 방향**을 명문화한다. SBR 금지 동사(§6·SBR-INV): **assume-complete/
snapshot-optimism**(SBR-INV-005/007)·**promote-UNKNOWN/timeout-fallback**(SBR-INV-006/012·§14 line 393)·
**assume-isolated/label-as-proof**(SBR-INV-008·§17 line 447)·**mutate/release-capacity**(SBR-INV-010)·**clear-HALT/
downgrade-HALT**(SBR-INV-009·§15 line 408)·**expire-economic-effect**(SBR-INV-013)·**revive/auto-re-arm**
(SBR-INV-014)·**infer-currentness-from-absence**(SBR-INV-004·§9 line 270)·**select-branch-by-recency**(§20 line 497).

| 빈 입력 | 금지 방향(vacuous permissive 차단) | 허용 방향(양성 side) | 근거 |
|---|---|---|---|
| **결측/unbounded required inventory 필드** | 결측/unbounded ⇒ 불완전 ⇒ NOT_READY | 전 §12 dependency present·bounded ⇒ complete | §13 line 372·SBR-AC-004 line 641 "omission creates NOT_READY" |
| **빈 obligation set** | 빈 set ⇒ "nothing to prove" 아님 ⇒ 최소 17항 obligation 강제 미충족 ⇒ NOT_READY | 17항 완비·acyclic·전 SATISFIED ⇒ 폐포 성립 | §13 line 352–370 minimum obligation set |
| **빈 dependency graph의 scope closure** | 빈 그래프 ⇒ 최소 폐포={trigger}·unknown edge⇒확장 | 완비 그래프 ⇒ 정확 도달성 폐포 | §8 line 240·iap `invalidation_closure` 동형(§0.4d) |
| **빈 change-set의 invalidation** | 빈 change ⇒ 최소 폐포={trigger}(trigger는 항상 자기 폐포) | material change ⇒ 영향 readiness 폐포 | §18 line 463·iap `predicates.py:366-367` 동형 |
| **UNKNOWN result + available capacity** | UNKNOWN + capacity ⇒ 여전히 차단(offset/release 금지) | 전 obligation SATISFIED + current binding ⇒ READY | §14 line 386 "all potentially-live quantities remain capacity-covered"·SBR-INV-006 |
| **재발행/replay 후 old decision 참조** | recovery/replay-match ⇒ revive 안 됨 | fresh chain + governed re-arm ⇒ 새 authority | §21 line 526·SBR-INV-014 line 198 |

**양방향 규율**: 각 빈-입력 가드는 (a) 금지 방향(가드 발화 canary)과 (b) 허용 방향(정당 통과 canary)을 **둘 다**
property로 검증(§7). vacuous-READY도 vacuous-NOT_READY(정당 recovery를 막음)도 결함이다 — 전자는 안전 위반,
후자는 가용성 위반(#12 both-ways 교훈). **양방향 집합 비교(#14 MAJOR-1 교훈)**: `obligation_graph_closed`(§5.2)·
`recovery_scope_closure`(§5.3)·`readiness_invalidated_by_change`(§5.6)의 집합 비교는 **양방향** — 결측(prerequisite
dangling·dependent 탈출)과 잉여/치환(spurious node·다른 scope) 모두 검사. **과대 주장 금지**: `extra="forbid"`는
모델 필드 unknown/duplicate만 차단하며 obligation/dependency 튜플의 excess/치환은 구조 술어가 잡는다고 정확히
서술(§2 — extra="forbid"가 튜플 excess를 막는다고 주장하지 않음).

**(나) truthy-sentinel 소비 계약(#14 M1 교훈을 처음부터 — 임계)**: bool 아닌 안전 술어의 소비를 명문화한다.

- **`ReadinessVerdict` 반환 술어**(readiness 발행): `READY`/`READY_RESTRICTED`/`NOT_READY`는 **모두 non-empty
  StrEnum**이라 `if verdict:`·`if verdict == True:`면 `NOT_READY`가 **truthy로 fail-open**(catastrophic — 미준비를
  준비로 오독). ⇒ **구조적 봉인(#14 M1을 처음부터)**: `ReadinessVerdict`는 **`__bool__`가 `TypeError`를 raise하는
  truthy-불가 타입**으로 저작 — 미래 소비자(liveauth re-arm)의 `if verdict:` 오용이 침묵 통과가 아니라 **런타임
  오류로 즉시 노출**. 보조로 **소비 게이트 계약: `verdict is ReadinessVerdict.READY`(명시 positive equality)만
  통과**(READY_RESTRICTED는 별도 격리 검증 후 §5.5). bare bool 반환 금지.
- **`SessionState`·`RecoveryBarrierState`·`ObligationResult` 반환 술어**: 전부 non-empty StrEnum — 동일 `__bool__
  ⇒ TypeError` 봉인. barrier state는 특히 위험(§2.2(1) line 257 "No barrier state alone permits") — `CLOSED_*`
  어느 값도 truthy 소비 시 permission 오독; 봉인으로 차단. obligation 소비 게이트 `result is ObligationResult.
  SATISFIED`.
- **`bool|None` 반환 술어**(`start_closed`·`competing_owner_fenced`·`halt_dominates_recovery`·
  `recovery_authority_separated` 등): `None`(미판정)은 falsy지만 **`is True` 명시 비교**로 소비(`is not True ⇒
  reject`) — spg `semantic_validation`(`predicates.py:466` `is not True⇒reject`)·protective `dominating_halt_or_incident`
  (`predicates.py:395` `is False`) 동형. `if x:` truthy 금지.
- **`recovery_completion_revives_nothing`**(무조건 `True` 반환): 이는 non-revival을 **문서화**하는 술어라 `True`가
  안전값 — 단 소비자는 여전히 `is True`로 소비(다른 술어와 계약 일관). authority replica(`predicates.py:787` `del
  … return True`) 동형.
- **canary**: 각 술어에 대해 (i) 안전값 아닌 반환(`NOT_READY`/`FAILED`/`None`/`False`)이 truthy/falsy edge에서
  **게이트가 reject함을 assert**, (ii) 안전값(`READY`/`SATISFIED`/`True`)만 통과 assert, (iii) **구조 봉인 회귀**:
  `bool(r)`이 `ReadinessVerdict`·`SessionState`·`RecoveryBarrierState`·`ObligationResult` 각 값에 대해 `TypeError`를
  raise함을 assert(+`is` 비교는 정상 양성측). 이 계약은 §5·§6 전 술어에 부착되고 §7 property·seam test로 회귀.

---

## 5. core 술어 — inventory/obligation/scope/convergence/isolation/invalidation/non-revival (SBR-EV-004/006/007/009/012 substrate, L1 슬라이스)

**핵심 난제**: recovery orchestration을 **순수 함수**로 저작하되, (i) policy·source·graph·capability·age bound를
**주입 판정/파라미터**로 두어 하드코딩·registry를 배제하고(§8), (ii) fail-closed(§4)를 **구조로** 지키며(permissive
기본·vacuous 부재·truthy-sentinel 봉합), (iii) 형제 판정(orthostate/recon/rcl/protective)을 **소비**하되 재저작하지
않는다(§3.5). 각 술어는 §1 core 5행(SBR-EV-004/006/007/009/012)의 L1 슬라이스를 저작하나 **어떤 SBR-EV도 닫지
않는다**(`/3` 잔여).

### 5.1 recovery_inventory_complete (§12; SBR-EV-004 substrate, core L1 슬라이스)

`recovery_inventory_complete(cut: RecoveryInventoryCut, policy: RecoveryBarrierPolicy) -> bool`:

- **complete only when**: §12 line 318–331 전 required dependency가 present ∧ non-None ∧ bounded(unobserved-window
  이 `max_adverse_bounds`로 bounded)일 때만 `True`. 한 필드라도 absent/None/unbounded/stale ⇒ `False`(불완전 ⇒
  NOT_READY). SBR-INV-005 line 162 앵커.
- **conservative evidence(§12 line 128)**: cut은 "conservative evidence, not an assertion that external state was
  atomically frozen." — `observed_events`(line 331) 전수 + `unobserved_window_assumptions`(line 332) present 필수.
  flat snapshot·missing ACK·cache agreement는 completeness 불성립(line 172, +Broker 부분은 §6.4).
- **monotonic clock 비교 금지(§12 line 335)**: "Issuer and consumer monotonic clocks across continuity identities
  are never directly compared. A time-ambiguous cut remains non-permissive." — time_uncertainty가 ambiguous ⇒
  `False`.
- **canary(both-ways)**: (a) required order/attempt/protective 필드 결측·unbounded window·ambiguous time ⇒
  incomplete(가드 발화; SBR-AC-004); (b) 전 §12 dependency present·bounded·observed_events 완비 ⇒ complete(양성 side).
- **미소유(§3.5)**: 각 필드 **값의 판정**(orthostate state·recon confidence·rcl capacity)은 형제 소유 — 이 술어는
  **완전성(결측/unbounded 여부)만** 판정.

### 5.2 obligation_graph_closed (§13; SBR-EV-004 substrate, core L1 슬라이스)

`obligation_graph_closed(obligations: frozenset[RecoveryObligation]) -> bool`:

- **closed only when**: (a) 모든 `prerequisite_ids`가 obligation set 내 존재(dangling 부재), (b) cycle 부재
  (topological sort 성공 — deterministic simulation), (c) 각 obligation `result ∈ acceptable_results` ∧ terminal,
  (d) 최소 obligation set(§13 line 352–370, 17항) 전부 present, (e) `independent_review_required=True` obligation은
  proposing owner가 satisfied 처리 안 함(self-satisfy 금지 line 372).
- **missing/cyclic ⇒ NOT_READY(§13 line 372)**: verbatim "Missing or cyclic obligation dependencies make the
  session NOT_READY." dangling prerequisite 또는 cycle ⇒ `False`.
- **DAG-validity bool(iap 비동형·§0.4d)**: 반환형은 **bool**(완전성+acyclicity 판정)이지 iap `invalidation_closure`의
  reachability **집합**이 아니다 — iap 재사용은 범주 오류. topological-sort 기반 acyclicity + prerequisite-존재 검사는
  로컬 저작.
- **canary(both-ways)**: (a) prerequisite dangling·cycle 주입·17항 중 결번·self-satisfy ⇒ not closed(가드 발화;
  SBR-AC-004); (b) 17항 완비·acyclic·전 result SATISFIED·independent review 충족 ⇒ closed(양성 side). **양방향 집합
  비교**: 결측 prerequisite + spurious obligation 둘 다 검사(§4.7).

### 5.3 recovery_scope_closure (§8; SBR-EV-004/007 substrate, core L1 슬라이스)

> **공유 폐포 커널(v1.1 MINOR-5)**: §5.3과 §5.6은 시그니처·폐포 공리가 동일하므로 **단일 intra-package
> private 커널 `_reachability_closure`를 공유**해 구현한다(패키지-내 drift 방지 — §0.4d의 cross-package
> 우려를 intra-package에도 적용). §7 하네스는 iap `invalidation_closure`·§5.3·§5.6 세 구현을 **공유 폐포
> property 계약**(단조성·불확정⇒확장·cycle 종결·∅⇒최소폐포)으로 함께 회귀한다.

`recovery_scope_closure(graph: Mapping[str, frozenset[str]], trigger: str, *, unproven: Mapping[str,
frozenset[str]] | None = None) -> frozenset[str]`:

- **§8 line 240 verbatim**: "Scope SHALL be computed from a versioned dependency graph. If an account shares
  [aggregate capacity, broker session, credential, route, …] with the trigger, the shared dependency is included
  **unless isolation is positively proven**. **Unknown dependency mapping expands to the containing account or
  broader Safety Cell**." 실현: 트리거에서 dependency graph 도달성 폐포; **`unproven`(isolation 미증명) adjacency는
  확장**(iap `invalidation_closure`의 `uncertain` 확장 `predicates.py:397-400` 동형 규율 — 로컬 저작 §0.4d).
- **fail-closed 확장(§8 line 242)**: "A trigger may narrow only after evidence proves the unaffected dependency
  closure. Operator selection, strategy ownership, organizational boundaries, or service labels are not isolation
  proof." — proven-disconnected node만 제외; 나머지 unknown ⇒ 확장(broader scope).
- **empty ⇒ {trigger}(§4.7)**: 빈 그래프 ⇒ 최소 폐포 {trigger}(trigger는 항상 자기 폐포; iap `predicates.py:366-367`
  동형).
- **canary(both-ways)**: (a) unknown edge ⇒ 확장(broader account 포함)·label만으로 narrow 시도 ⇒ 확장 유지(가드
  발화); (b) positively proven disconnected node ⇒ 제외(양성 side — 과잉 확장 아님). **양방향 집합**: 탈출 node(under-
  expand) + spurious node(over-expand) 둘 다 검사.

### 5.4 unknown_stays_conservative + timeout_is_restrictive (§14/§19; SBR-EV-006 substrate, core L1 슬라이스)

`unknown_stays_conservative(field_results: Mapping[str, ObligationResult], prior: Mapping[str, ObligationResult])
-> bool` · `timeout_is_restrictive(elapsed: bool, converged: bool, obligation_set_size_before: int,
obligation_set_size_after: int) -> bool`:

- **repeated UNKNOWN ↛ known(§14 line 393)**: verbatim "Repeated identical unknown observations do not convert
  UNKNOWN into known state." — 동일 UNKNOWN 재관측이 `SATISFIED`로 승격 못 함(`unknown_stays_conservative`는 prior가
  UNKNOWN이고 새 관측도 identical UNKNOWN이면 여전히 non-satisfied).
- **timeout no fallback(§14 line 393·§19 line 478)**: "If convergence cannot be proven within
  `B_startup_reconciliation`, the bound is an operational target and escalation trigger, **not permission**. The
  barrier stays closed." + §19 line 478 "Inventory observations never converge | NOT_READY; escalate; **no timeout
  fallback**." — `timeout_is_restrictive`는 elapsed ∧ ¬converged ⇒ NOT_READY이고 **obligation set을 축소하지 않음**
  (SBR-INV-012 line 190 "never reduces the obligation set": `obligation_set_size_after ≥ before` 강제).
- **retry never resets(§19 line 486)**: "Retry never resets elapsed uncertainty, replenishes protective capacity,
  releases UNKNOWN, or reuses prior approval." — retry는 새 attributable attempt(§4.2)이되 uncertainty 시계 reset
  안 함.
- **convergence 요건(§14 line 382–391)**: every required field terminal ∧ no hidden conflict(no blended score)∧ all
  potentially-live capacity-covered ∧ mutually consistent under worst credible union ∧ no later invalidation
  trigger. **no-blend**(recon `predicates.py:10-11` 동형) — SBR은 field 결과를 **fold**하되 평균/blend 안 함.
- **canary(both-ways)**: (a) 동일 UNKNOWN 재관측 ⇒ non-satisfied·timeout ⇒ NOT_READY·obligation set 축소 시도 ⇒
  reject(가드 발화; SBR-AC-006); (b) 전 field terminal-SATISFIED·converged ⇒ 통과(양성 side).

### 5.5 restricted_isolation_proven (§17; SBR-EV-007 substrate, core L1 슬라이스)

`restricted_isolation_proven(candidate_scope: RecoveryScope, isolation_facts: IsolationFacts) -> bool`:

- **8조건 전수 양성(§17 line 438–445)**: (1) distinct RCL Capacity Domain 또는 conservative aggregate allocation
  cross-scope headroom reuse 방지, (2) broker session/credential/route/rate-limit/account-semantics 격리, (3)
  margin/collateral/cash/settlement/financing/concentration/portfolio-risk safe under unresolved max, (4) no
  protective order/lease/resource/Cancellation-Arbiter/replacement crossing boundary, (5) config/authority/time/
  evidence/deployment/identity/failure-domain compatible·current, (6) external/manual·non-trade unmappable into
  candidate, (7) final egress가 exact restricted scope·current Recovery Generation 강제 가능, (8) Hard Safety
  Envelope satisfied under union of resolved+unresolved. **하나라도 미증명 ⇒ `False`**(broader NOT_READY).
- **label≠proof(§17 line 447)**: `IsolationFacts`의 각 조건은 positive proof flag(`bool|None`) — `None`/`False` ⇒
  미증명. logical separation/UI label/ticket/instance/unused capacity는 flag를 `True`로 만들지 못함(주입 시 fail-
  closed).
- **canary(both-ways)**: (a) 8조건 중 하나 `None`·shared capacity unbounded ⇒ not proven(가드 발화; SBR-AC-007);
  (b) 8조건 전수 `True` ⇒ proven(양성 side — 정당 격리 허용). ∅ 양방향: 빈 isolation_facts ⇒ 전 조건 미증명 ⇒ `False`.

### 5.6 readiness_invalidated_by_change (§18; SBR-EV-009 substrate, core L1 슬라이스)

`readiness_invalidated_by_change(dep_graph: Mapping[str, frozenset[str]], change_triggers: frozenset[str], *,
unproven: Mapping[str, frozenset[str]] | None = None) -> frozenset[str]`:

- **§18 line 453–461 material change 폐포**: change trigger 집합에서 영향받는 readiness 도달성 폐포(iap
  `invalidation_closure` 동형 규율 — 로컬 저작 §0.4d). 반환은 invalidated readiness/scope 집합.
- **invalidation before authority(§18 line 463)**: "Invalidation advances or closes the barrier for affected scope
  **before a later Live Authorization may be issued**." — 폐포에 든 readiness는 authority 발급 전 무효(§4.5).
- **cached beyond max/newer generation ⇒ 무효(§18 line 463)**: "A consumer cannot continue using a cached readiness
  decision beyond `MAX_recovery_readiness_age` or after a newer generation is observed." — age param 주입(§8).
- **empty change ⇒ {trigger}(§4.7)**: 빈 change-set ⇒ 최소 폐포(trigger 자기 포함); unproven edge ⇒ 확장.
- **canary(both-ways)**: (a) post-cut fill·profile change·newer generation ⇒ 영향 readiness 폐포에 포함(가드 발화;
  SBR-AC-009); (b) 무관 무변경 ⇒ 폐포 밖(양성 side — 정당 readiness 유지, max-age 내). **양방향 집합**: 탈출(under-
  invalidate) + spurious(over-invalidate) 둘 다.

### 5.7 recovery_completion_revives_nothing (§21/§19/§20; SBR-EV-012 substrate, core L1 슬라이스)

`recovery_completion_revives_nothing(*, completion_signal, health_recovered, evidence_repaired, replay_matched,
human_acknowledged, prior_authority) -> bool`:

- **무조건 `True`(§21 line 526·SBR-INV-014 line 198)**: 5 revival vector(completion/health/evidence-repair/replay-
  match/human-ack) 어느 것도 prior authority를 revive 안 함. **모델은 revival path를 제공하지 않으며 이 술어가 그
  부재를 문서화·고정**(authority `recovery_generation_revives_nothing` `predicates.py:787-820` replica pattern —
  `del … ; return True`). SBR ADR §1 line 27 verbatim: "Recovery completion, service health, connectivity
  restoration, operator acknowledgement, evidence repair, replay match, or human approval **never restores prior
  authority**."
- **fresh governed re-arm 필수(line 200)**: "fresh governed re-arm is mandatory." — re-arm은 완전한 ADR-002-007/015
  workflow(handoff §21) 통해 새 Live Authorization·per-action capability 생성; SBR readiness는 첫 입력만(§3.5 핵심
  판정 2).
- **replay ≠ prevention(§23.10 line 604)**: "reconstruction cannot retroactively make a permissive start or broker
  effect safe." — replay-match가 readiness를 repair 못 함.
- **canary(both-ways)**: (i) 5 vector 각각 True로 주입해도 `recovery_completion_revives_nothing`은 `True`(revive
  없음) assert; (ii) **구조 회귀**: 모델에 generation-increase → authority-restoration 매핑 operation이 **부재**함을
  assert(authority replica 동형). 양성 side는 SBR 밖(fresh re-arm chain).

---

## 6. predicate-only 술어 — start-closed·egress-fence·owner-fence·broker-conservatism·HALT·restore·authority-separation (SBR-EV-001/002/003/005/008/010/011 substrate, 최소 ≥ L2·닫지 않음)

이 7 술어는 predicate-only substrate다 — **어떤 SBR-EV도 닫지 않으며**(최소 ≥ L2·5행 +Security·1행 +Broker),
L1 슬라이스는 **순수 술어 계약**만 저작하고 실 enforcement(active currentness·owner-epoch·broker 통합·emergency
latch·predecessor fencing·SoD)는 EV-L2/L3 런타임·+Security/+Broker다.

### 6.1 start_closed (§8/§9; SBR-EV-001 substrate, predicate-only, 최소 EV-L2/3)

`start_closed(barrier: RecoveryBarrierState, live_arming_chain_complete: bool | None) -> bool`:

- **§1 line 15·SBR-INV-001 line 146**: "Every Safety Cell begins with new-risk authority denied until a current
  recovery barrier and the separate complete live-arming chain are positively satisfied." — barrier가 `CLOSED_*`
  이고 live-arming chain이 positively complete가 아니면 new-risk denied. barrier 시작값 = `CLOSED_NON_LIVE`(§9).
- **barrier ≠ permission(§9 line 257)**: 어느 barrier state도 live transmission 허용 안 함 — `start_closed`는
  denial 여부만; fresh live-arming chain(§21 handoff)은 별도.
- **predicate-only 경계**: barrier ordering 강제·fresh chain enforce는 EV-L2 component fault(§1). L1은 "closed
  시작·chain 미완 ⇒ denied" 술어 계약만.
- **canary(both-ways)**: (a) barrier CLOSED·chain `None`/`False` ⇒ denied(가드 발화; SBR-AC-001 line 638 "no
  new-risk first byte before a complete fresh live-arming chain"); (b) barrier + chain positively complete ⇒
  new-risk 가능(양성 side, SBR 밖 re-arm).

### 6.2 stale_generation_rejected_at_egress (§9; SBR-EV-002 substrate, predicate-only, 최소 EV-L2/3+Security)

`stale_generation_rejected_at_egress(request_generation: int | None, current_generation: int | None,
current_actively_established: bool | None) -> bool`:

- **§9 line 268 verbatim**: "Final egress SHALL reject any new-risk request when the current Recovery Generation
  cannot be positively verified, the request references an older generation, the barrier is closed, or readiness is
  absent/invalid." — older `compare_order`(§3.2)·unverifiable current ⇒ reject.
- **active currentness(§9 line 270·SBR-INV-004 line 160)**: cache/TTL/heartbeat/service-health/absence ↛
  currentness. `current_actively_established is not True ⇒ reject`. 좌표 non-collapse(§4.3).
- **ADR-002-024 위임(§9 line 272)**: 실 currentness 메커니즘은 ADR-002-024 Safety Currentness Vector(런타임
  +Security) — "Recovery Generation and barrier/readiness floors are dimensions in the exact Safety Currentness
  Vector." L1은 순서 비교·active-establish 요구 술어만.
- **canary(both-ways)**: (a) older generation·좌표 치환·`current_actively_established=None` ⇒ reject(가드 발화;
  SBR-AC-002); (b) current·actively-established·verified ⇒ 통과(양성 side).

### 6.3 competing_owner_fenced (§11; SBR-EV-003 substrate, predicate-only, 최소 EV-L2/3+Security)

`competing_owner_fenced(owner_epoch: int | None, current_owner_epoch: int | None, owner_status: OwnerStatus) ->
bool`:

- **§11 line 303–304**: "only one current owner may advance a session or publish a decision for overlapping scope;
  minority, stale, paused, restored, removed, or partitioned owners are rejected." — `owner_status ∈ {MINORITY,
  STALE, PAUSED, RESTORED, REMOVED, PARTITIONED}` ⇒ reject.
- **weak fencing 불충분(§11 line 305)**: "leader election, database primary status, lock TTL, cache ownership,
  heartbeat health, or broker reachability alone is insufficient fencing." — 이들만으로 current owner 인정 안 함.
- **unavailable former owner(§11 line 309·§19 line 482)**: "an unavailable former owner remains potentially active
  until fenced at every decision consumer." — 도달 불가 former owner ⇒ potentially active ⇒ overlapping readiness
  deny.
- **predicate-only 경계**: 실 owner-epoch·quorum topology·split-brain은 ADR-002-012 SCL 런타임 +Security(§11 line
  311). L1은 owner-status 기반 fence 술어만.
- **canary(both-ways)**: (a) minority/stale/restored/partitioned owner·heartbeat-only ⇒ reject(가드 발화;
  SBR-AC-003); (b) single current fenced owner ⇒ 통과(양성 side). 집합 양방향: overlapping scope 검사 + disjoint
  scope 허용(§11 line 306 "concurrent non-overlapping sessions permitted only when … proven disjoint").

### 6.4 non_atomic_broker_conservative (§12/§14; SBR-EV-005 substrate, predicate-only, 최소 EV-L2/3+Broker)

`non_atomic_broker_conservative(reads: BrokerReadSequence, intervening_events: frozenset[str]) -> bool`:

- **no snapshot optimism(SBR-INV-007 line 170)**: "One broker query, flat position, cache agreement, absent page
  result, missing ACK, or cancel ACK cannot establish completeness, non-acceptance, Final Quantity Proof, or
  capacity release." — single read/flat/absent-page ⇒ conservative 유지.
- **equality ≠ proof(§12 line 333)**: "Equality between two reads does not prove that an unobservable event did not
  occur." — 두 read 동일해도 intervening event 가능성 ⇒ bounded convergence 필요(re-read until field-specific proof
  stable 또는 NOT_READY).
- **미소유(§3.5)**: Final Quantity Proof·per-field confidence는 recon/ADR-002-006/004 소유(+Broker) — SBR은
  "single read ↛ completeness" conservatism 술어만. 실 broker page/cursor 프로토콜은 §27 q4 런타임.
- **canary(both-ways)**: (a) single read·flat·absent-page·cancel-ACK만으로 completeness/release 주장 ⇒ conservative
  차단(가드 발화; SBR-AC-005); (b) bounded convergence(re-read + intervening events 반영)로 stable proof ⇒ 통과(양성
  side, +Broker 런타임).

### 6.5 halt_dominates_recovery (§15; SBR-EV-008 substrate, predicate-only, 최소 EV-L2/3+Security)

`halt_dominates_recovery(halt_applied: bool | None, dominating_halt_or_incident: bool | None,
safety_owned_protection_present: bool | None) -> bool`:

- **HALT 지배(SBR-INV-009 line 178·§15 line 408)**: "Recovery cannot clear, outrank, defer, or reinterpret HALT."
  + "Recovery cannot downgrade `HALTED` to `RECOVERY`, clear a local deny latch, or schedule an automatic
  transition. Where HALT application is ambiguous, treat it as applied until reconciled under fresh governance." —
  `halt_applied`가 ambiguous(`None`) ⇒ **applied로 처리**(fail-closed).
- **protective continuity(§15 line 406)**: "Existing safety-owned protection SHALL NOT be cancelled for cleanup,
  session reset, deployment convenience, or to obtain a clean snapshot." — `safety_owned_protection_present=True`
  이면 recovery cleanup이 cancel 못 함(protective `ProtectiveOwnership.SAFETY_OWNED` `predicates.py:570` 소비).
- **evidence failure ↛ block restriction(SBR-AC-008 line 645)**: "evidence/journal failure does not block
  restriction." — evidence 실패해도 HALT/denial은 진행.
- **미소유(§3.5)**: HALT downgrade 판정·Cancellation Arbiter·emergency latch는 protective/ADR-002-011/015 소유
  (+Security). SBR은 "HALT 지배·ambiguous⇒applied·safety-owned no-cancel" 술어만.
- **canary(both-ways)**: (a) HALT ambiguous ⇒ applied·recovery가 safety-owned protection cancel 시도 ⇒ 차단(가드
  발화; SBR-AC-008); (b) HALT 명시 미적용·non-safety-owned cleanup ⇒ 허용(양성 side).

### 6.6 restore_worst_credible_union (§20; SBR-EV-010 substrate, predicate-only, 최소 EV-L2/3+Security)

`restore_worst_credible_union(branches: frozenset[str], selection_basis: SelectionBasis | None,
credible_union: object) -> bool`:

- **all branches 보존(§20 line 496)**: "compute the worst credible union of economic effects and capacity
  consumption." + line 497 "select no branch by recency label, backup success, administrator choice, or wall-clock
  timestamp alone." — `selection_basis ∈ {RECENCY, BACKUP_SUCCESS, ADMIN_CHOICE, WALL_CLOCK}` ⇒ reject(단일 basis로
  branch 선택 금지).
- **rcl union 소비(§3.5)**: worst-credible economic union은 rcl `credible_union_capacity`(`predicates.py:739`) 결과
  소비 — "credible_union_capacity requires at least one reconstructable history"(`predicates.py:770`). SBR은 capacity
  union 산술을 재저작하지 않음(rcl only).
- **older backup ≠ authority(§20 line 503)**: "An older backup may be recovery input but cannot become authority
  merely because it is available. Missing acknowledged commits, unverifiable fencing, or unresolved conflicting
  history keeps the affected scope non-live." — conflicting history 존재 ⇒ non-live.
- **conflict 탐지(§2.1)**: 복수 branch same-id/diff-bytes는 canonical `classify_record_pair`(`RecordPairKind.
  CRITICAL_CONFLICT`) 소비.
- **canary(both-ways)**: (a) recency/backup/wall-clock로 branch 선택·conflicting history 무시 ⇒ reject(가드 발화;
  SBR-AC-010); (b) all branches worst-credible union·predecessor fencing 증명 ⇒ 통과(양성 side, +Security 런타임).

### 6.7 recovery_authority_separated (§7/§21; SBR-EV-011 substrate, predicate-only, 최소 EV-L2/3+Security)

`recovery_authority_separated(effect: RecoveryAuthorityEffect, forced_ready_requested: bool | None) -> bool`:

- **all-false authority(SBR-INV-003 line 154)**: `RecoveryAuthorityEffect` 전 필드 `False`(creates_capacity·
  issues_live_auth·issues_capability·classifies_protective·transmits_broker·grants_rearm 전부 `False`). rcl
  `AllFalseAuthority`(`_base.py:55`) 동형 — 구성-불변식으로 봉인(어느 필드도 `True` 불가).
- **forced-ready reject(§19 line 483·§21 line 517–526)**: "Operator requests forced ready | reject; operator may
  HALT or request governed containment only." + §21 human "SHALL NOT: mark obligations satisfied without their
  proof rule; … waive UNKNOWN into new-risk permission; mutate/release RCL capacity; clear HALT or stale fencing
  through recovery UI; convert READY or READY_RESTRICTED into Live Authorization." — `forced_ready_requested=True`
  ⇒ reject(readiness는 human이 promote 불가).
- **RCL only(SBR-INV-010 line 182)**: "The Recovery Coordinator may submit evidence-bound requests but only the RCL
  may mutate, quarantine, import, transfer, or release capacity." — SBR은 evidence-bound request만; mutate는 rcl.
- **미소유(§3.5)**: 실 SoD·bypass path·common-effective-control(§7 line 220)는 +Security 런타임. L1은 all-false·
  forced-ready-reject 술어만.
- **canary(both-ways)**: (a) forced-ready·recovery가 capacity mutate/live-auth/classify/transmit/clear-HALT 시도 ⇒
  차단(가드 발화; SBR-AC-011); (b) evidence-bound request(RCL 위임)·governed containment 요청 ⇒ 허용(양성 side).
  **all-false 회귀**: `RecoveryAuthorityEffect`의 어느 필드도 `True`로 구성 불가함을 assert(rcl 동형).

---

## 7. property-test 하네스 타깃

§1 분류에 정렬한다. **닫는 SBR-EV = 0건** — 어떤 test-target도 SBR-EV closure·acceptance를 주장하지 않는다(규율
태그 부착). 각 술어에 **both-ways canary**(§4·§5·§6)·**truthy-sentinel canary**(§4.7)·**fixture clean-vs-illegal
정합**(#8 교훈)을 건다.

- **core(L1 슬라이스, SBR-EV-004/006/007/009/012 substrate)**: `recovery_inventory_complete`(§5.1);
  `obligation_graph_closed`(§5.2); `recovery_scope_closure`(§5.3); `unknown_stays_conservative`+
  `timeout_is_restrictive`(§5.4); `restricted_isolation_proven`(§5.5); `readiness_invalidated_by_change`(§5.6);
  `recovery_completion_revives_nothing`(§5.7). **scope/invalidation-closure property(노다지)**: hypothesis로 무작위
  dependency 그래프 + trigger 생성 → 폐포가 도달 가능한 전 dependent 포함(no escape) + unproven edge ⇒ 확장(broader
  scope) + positively-disconnected는 미포함(both-ways) + empty⇒{trigger}. **obligation-graph property(노다지)**:
  무작위 obligation set → dangling prerequisite ⇒ not-closed·cycle ⇒ not-closed(topological)·17항 완비+acyclic ⇒
  closed. **timeout property**: elapsed ∧ ¬converged ⇒ NOT_READY ∧ obligation-set 크기 비감소(SBR-INV-012).
- **predicate-only(SBR-EV-001/002/003/005/008/010/011 substrate, EV 미주장)**: `start_closed`(§6.1);
  `stale_generation_rejected_at_egress`(§6.2, `compare_order` 기반 순서); `competing_owner_fenced`(§6.3);
  `non_atomic_broker_conservative`(§6.4); `halt_dominates_recovery`(§6.5); `restore_worst_credible_union`(§6.6);
  `recovery_authority_separated`(§6.7, all-false 회귀).
- **세션 상태기계 property(노다지, §4.2)**: hypothesis로 무작위 (state, next_state) 시퀀스 생성 → `_SESSION_TRANSITIONS`
  arrow만 허용·terminal({NOT_READY·INVALIDATED·ABORTED·EXPIRED·SUPERSEDED})⇒ready 불가·retry⇒새 identity(spg
  `_ENVELOPE_TRANSITIONS` property 동형).
- **truthy-sentinel 회귀(§4.7, MANDATED)**: `ReadinessVerdict`·`SessionState`·`RecoveryBarrierState`·`ObligationResult`
  반환 술어에 대해 (i) `NOT_READY`/`FAILED`/`CLOSED_*`가 truthy임을 assert, (ii) `is READY`/`is SATISFIED` 게이트가
  그 외를 reject함을 assert(`if verdict:` 대비 회귀), (iii) **구조 봉인 회귀**: `bool(ReadinessVerdict.*)`·
  `bool(RecoveryBarrierState.*)` 등이 `TypeError`를 raise함을 assert. **이 회귀가 #14 M1 truthy-sentinel 교훈의
  처음부터 능동 봉합**이다(특히 barrier state는 §9 line 257 "No barrier state alone permits" 때문에 임계).
- **seam cross-check(test-only, MANDATED §3.4)**: `test_seam_orthostate`(SBR RECONCILING이 orthostate
  `reconstruct_conservative` 결과 fold·codomain excludes RECONCILED `predicates.py:23-24`)·`test_seam_recon`(SBR
  convergence가 recon `FieldConfidenceClass` fold·no-blend `predicates.py:10-11`·`ObligationResult`≠
  `FieldConfidenceClass` §3.5)·`test_seam_rcl`(§20 union이 rcl `credible_union_capacity` `predicates.py:739` 소비·
  capacity mutate는 rcl only)·`test_seam_protective`(§15가 protective `dominating_halt_or_incident` `records.py:202`
  소비)·`test_seam_authority`(SBR `recovery_coordinator_evidence_complete` 생산 = authority `_REARM_PREREQUISITES`
  item 12 `predicates.py:108`·`recovery_generation` = authority `GenerationVector` `state.py:50` reference 좌표)·
  `test_seam_liveauth`(SBR readiness 생산 = liveauth `recovery_current` `state.py:139`/`recovery_readiness_enlarged`
  `state.py:208` 소비). 테스트 import는 package closure에 불계상(§7.1).
- **∅-공허 회귀(양방향, §4.7)**: 결측/unbounded inventory ⇒ 불완전; 빈 obligation set ⇒ 17항 미충족 NOT_READY; 빈
  dependency 그래프 ⇒ 최소 폐포·unproven⇒확장; UNKNOWN+capacity ⇒ 차단; **동시에** 각 완비 입력의 정당 통과 canary.

### 7.1 import-closure 검증 테스트 (설계 #4 §7.1·#12–#15 §7.1 상속)

`import tos.sbr` 후 `sys.modules` closure에 **금지 집합 부재 assert**: `shared.config`·`os.environ` 흔적·`numpy`/
`pandas`/`yaml`·**`tos.are`·`tos.authority`·`tos.brokercap`·`tos.capsule`·`tos.dsl`·`tos.evidence`·`tos.iap`·
`tos.ioc`·`tos.liveauth`·`tos.orthostate`·`tos.protective`·`tos.rcl`·`tos.recon`·`tos.spg`·`tos.time`·**`tos.afg`**(v1.1
MAJOR-1 — 최인접 실재 형제)·`tos.venue`**
(17 형제 전부 — 실재 16 + venue 미구현) 부재; **`tos.canonical`·`tos.ordering`만 존재 허용**(sibling edge 0 — §0.4c). required check
(`tos-firewall`, `tools/tos_firewall_check.py` layer-① AST + `.importlinter` layer-② 전이)와 함께 green이어야 §0.3
선언이 능동 성립. **주의**: iap `invalidation_closure` 동형 규율을 상속하되(§0.4d) `tos.iap` **부재**를 assert —
로컬 저작이지 import가 아님을 이 테스트가 강제.

### 7.2 run manifest 정렬 (설계 #1 §5.1 7항목)

(1) 목적: sbr Phase-1(EV-L1) 순수 모델+property test. (2) 명령: `pytest tos/tests/sbr/ -v`. (3) 격리: hermetic
(`.env` 비주입·clock 미접근·네트워크 없음 — recovery 판정의 hidden-input 부재·§8 clock 미접근·§5.1 monotonic clock
비교 금지와 정합). (4) 결정론: hypothesis 시드 고정·`EVL1ProvisionalCanonicalizer` 고정·enum StrEnum 고정·
`compare_order` 결정론. (5) 산출물: property test 결과(EV closure 아님 — 규율 태그). (6) 게이트: `tos-firewall`
required green. (7) 비-acceptance: 어떤 SBR-EV도 닫지 않음(§0.2·VER-002-001 §5).

---

## 8. bounds 주입 + Phase-0

**§8.0 sbr 모델 구조에 numeric bound 부재**: 전부 enum(`ReadinessVerdict`/`SessionState`/`RecoveryBarrierState`/
`ObligationResult`)·boolean·집합/그래프 논리·주입 opaque age/generation param. ADR §4 non-scope line 96 "approved
numeric recovery bounds, which belong in the Verification Profile and Recovery Barrier Policy"는 수치를 **명시 배제**
한다 — 전부 **Safety/Verification Profile INSTANCE 측정값**이며 주입 opaque param으로만 담는다. 값 부재 ⇒ fail-
closed(§4·§5.6 age param). 값 승인은 Bounds-Approver 게이트(§9.2).

**§8.1 Verification-Profile 키 실측(#13 MAJOR-2 규율 — `measurement_source`·`failure_response` 전수 확인)**: ADR §27
q12(line 685)가 요하는 수치 및 VERIFICATION-PROFILE-002.yaml 키 상태(전수 grep):

- **trigger→barrier(§8/§9)**: `B_recovery_trigger_to_barrier`(line 205, `value_ms: null` — "APPROVE after trigger
  classification and ordered barrier commit are implemented", `measurement_source:
  recovery_trigger_barrier_commit_and_local_fence_trace`, **`failure_response: HARD_FENCE_AND_HALT`** line 211,
  rationale "ADR-002-017 §§8-9") — **이미 존재**.
- **barrier→egress(§9/§18)**: `B_recovery_barrier_to_egress`(line 212, `null` — "APPROVE after Recovery Generation
  distribution and egress rejection are implemented", `measurement_source:
  recovery_generation_and_egress_boundary_trace`, "ADR-002-017 §§9, 18") — **이미 존재**.
- **startup reconciliation(§14)**: `B_startup_reconciliation`(line 198, **PROPOSED 60s operational target**,
  rationale line 202 "No new risk before reconciliation completes (hard gate). 60s is an operational target;
  exceeding it triggers escalation, **not relaxation of the gate**", `measurement_source: recovery_coordinator_log`)
  — **이미 존재**. §14 line 393·§5.4와 정합(timeout no fallback).
- **readiness age(§16/§18)**: `MAX_recovery_readiness_age_ms`(line 708, `null` — "APPROVE per recovery scope;
  expiry or unknown age denies later authority issuance") — **이미 존재**. §5.6과 정합.
- **process suspension trigger(§8)**: `MAX_process_suspension_ms`(line 701, **2000 PROPOSED** — "a process
  suspended longer than this is fenced on resume") — **이미 존재**. §8 line 228 "process suspension beyond bound"
  트리거·§0.4e `process_generation` 좌표와 정합.
- **incident handoff→barrier(§18)**: `B_incident_handoff_to_recovery_barrier`(line 443, MEASURE — "committed
  incident recovery-handoff intent to exact package acceptance by a current Recovery Session behind a closed
  Recovery Barrier; incomplete handoff transfers no obligation", **`failure_response: CLOSE_BARRIER_AND_HALT`** line
  449) + `MAX_incident_recovery_handoff_age_ms`(line 735, `null` — "stale handoff transfers no obligation and keeps
  the barrier closed") — **이미 존재**. §18 line 465와 정합.
- **policy artifact pin(§5.3)**: `recovery_barrier_policy_id`/`recovery_barrier_policy_generation`/
  `recovery_barrier_policy_digest`(line 46–48, TBD/null/TBD) — Recovery Barrier Policy 아티팩트의 test-harness pin
  (§5.2 governance는 spg/§27 q1).
- **결론(over-claim 봉합·#10 lesson)**: ADR §27 q12가 요구하는 SBR-owned 6 bound(trigger-to-barrier·barrier-to-
  egress·startup-reconciliation·readiness-age·process-suspension·incident-handoff) + handoff-age가 **전부 실재**하고
  전부 null/PROPOSED(미승인) + 3 policy-pin 실재. ⇒ **candidate 신규 키 = 0건**(#10/#13/#15 "0 누락" 동형). 이는
  결함이 아니라 **Phase-0 Bounds-Approver 승인 항목**이다 — sbr는 이 값들을 신뢰하지 않으며(VP status PROPOSED·
  unapproved bound은 approved bound 아님, VER-002-001 §6) 전 수치를 fail-closed로 처리(§4·§5.4·§5.6).

**§8.2 upstream generation-vector 합성(런타임·not-Phase-1)**: §16 readiness decision의 generation vector(line 423)는
sbr-owned `recovery_generation`뿐 아니라 upstream generation(RCL writer/restore·authority epoch·HALT·profile·broker·
deployment·ADR-002-029 Release·ADR-002-030 Post-Trade·egress·evidence·human)을 **합성 binding**한다 — 전부 형제
ADR 소유·주입 scalar. Phase-1 sbr는 이 합성을 **강제하지 않고**(런타임 §6.2) readiness/inventory record에 각 upstream
좌표를 scalar로 binding할 뿐이다(§2.4). 합성 강제·currentness 검사는 EV-L3 final-egress·ADR-002-024 런타임.

**§8.3 self-referential 주의(경미)**: sbr가 소비하는 Recovery Barrier Policy(§5.3)는 spg Safety Config Bundle
governance 대상(§8 line 112 "separately governed artifact")이며 VP가 policy id/generation/digest를 pin(line 46–48).
#12(spg) self-reference paradox와 달리 sbr는 **policy의 소비자**일 뿐(governance 주체는 spg)이라 layering 단순 — sbr는
VP를 import·파싱하지 않고(YAML은 하네스 #3) policy 좌표를 주입 scalar로만 담는다. VP status PROPOSED ⇒ 전 수치 불신.

---

## 9. 후속 작업 · Phase-0 인간 게이트 이관 항목

### 9.1 후속 구현 작업 (본 계약 위에서)

1. `tos/src/tos/sbr/` 5-module 저작(`_base.py` all-false `RecoveryAuthorityEffect` shim·`vocabulary.py`[
   `RecoveryBarrierState`·`SessionState`·`ReadinessVerdict`·`ObligationResult`·`RecoveryMode`·전이표]·`records.py`
   [8-모델]·`predicates.py`[core 7 + predicate-only 7]·`state.py`[session 상태·주입 입력]) + `tos/tests/sbr/`
   property test(§7) + seam cross-check(§3.4) + import-closure(§7.1) + truthy-sentinel 구조 봉인 회귀(§4.7).
2. core 술어 7종(§5) + predicate-only 술어 7종(§6) + 8-아티팩트·all-false `RecoveryAuthorityEffect`·enum 어휘(§2)
   구현. **sibling edge 0 유지**(§0.4c) — 어떤 형제 타입도 REUSE·import 하지 않음(형제 결과는 injected scalar/bool/
   enum-token/verdict). iap `invalidation_closure`는 **로컬 재저작**(import 금지·§0.4d).
3. 미래 caller 런타임(Recovery Coordinator / Safety Control Plane)이 sbr 산출(session·inventory·obligation graph·
   package·readiness)을 소비자(authority/liveauth re-arm·final-egress·SCL barrier commit)로 배선(§3.4; Phase 1 밖·
   EV-L2/L3). **형제 술어 호출→결과 주입**은 런타임 orchestrator 몫(§0.4c) — sbr 순수 모델은 주입 위 fold만.

### 9.2 Phase-0 인간 게이트로 넘기는 항목 (본 계약이 결정하지 않음)

ADR §27 Open Implementation Questions(14항)·§28 Approval Gate(19조건)에서 Phase-1 밖으로 이연:

1. **Recovery Barrier Policy schema·dependency graph·trigger classifier·obligation registry**(§27 q1·§28 item 1) —
   canonical semantic form(§3.1 EVL1ProvisionalCanonicalizer는 잠정). `TriggerClass` 분류기는 주입(§2.2(6)).
2. **ADR-002-012 ordered namespace·owner-epoch·quorum topology·Commit Proof(Recovery Generation fencing)**(§27
   q2·§11·§28 item 3) — stale owner/competing coordinator fence 런타임(§6.3은 owner-status 술어만).
3. **모든 Live Auth issuer·ADR-002-013 final egress의 current Recovery Generation 획득(permissive cache 없이)**(§27
   q3·§9·§28 item 8) — ADR-002-024 Currentness Vector 런타임(§6.2는 술어 계약만).
4. **broker query/event/page/cursor 프로토콜(conservative Inventory Cut)**(§27 q4·§12·§28 item 4) — first
   account/broker scope의 non-atomic convergence 런타임 +Broker(§6.4는 conservatism 술어만).
5. **어느 dependency가 partial recovery 허용**(§27 q5·§17·§28 item 6) — account/Capacity Domain/session/credential/
   route/margin/protection/failure-domain isolation 판정(§5.5는 8조건 구조 슬라이스만).
6. **source-independent corroboration·repeat-observation 규칙(per-field convergence)**(§27 q6·§14) — 각 required
   field의 field-specific proof 규칙(recon/ADR-002-006 소유·§5.4는 no-blend fold만).
7. **RCL 명령(evidence-bound quarantine/import/release)**(§27 q7·§13 obligation 2·§28 item 5) — recovery가 capacity
   authority 없이 request만(SBR-INV-010·§6.7).
8. **durable workflow engine·package signer·schema registry·evidence path·notification**(§27 q8·§28 item 9) — 제품
   선택(§2.1 레코드 substrate만 Phase-1).
9. **Human Authority Policy roles(residual-risk review·later re-arm, recovery proof owner 아님)**(§27 q9·§21·§28
   item 8) — human class 결정(ADR-002-015; §21 line 517–526 SHALL NOT). human이 automated proof 대체 불가(§0.2).
10. **barrier close·local deny latch·HALT·evidence emergency journal·hard egress fence 합성(control-plane loss)**
    (§27 q10·§9/§15·§28 item 7) — +Security 런타임(§6.1/§6.5는 술어만).
11. **DR 절차(predecessor writer/egress/broker-session/credential/recovery-owner fencing 증명)**(§27 q11·§20·§28
    item 7) — +Security(§6.6은 branch-선택-금지·union-소비 술어만).
12. **numeric bounds 승인**(§27 q12·§28 item 17) — `B_recovery_trigger_to_barrier`·`B_recovery_barrier_to_egress`·
    `B_startup_reconciliation`·`MAX_recovery_readiness_age_ms`·`MAX_process_suspension_ms`·
    `B_incident_handoff_to_recovery_barrier`+`MAX_incident_recovery_handoff_age_ms`(§8.1 **전부 실재·null/PROPOSED**)의
    Bounds-Approver 승인 + concurrency/partition/restore/compromise/fault-injection 측정(§28 item 17). **candidate
    신규 키 0건.**
13. **ADR-002-018 CII obligations current before readiness**(§27 q13·§13 obligation 7·§28 item 11) — capsule/
    snapshot/context-generation/correction/common-mode/invalidation(§2.4 capsule 주입 slot).
14. **ADR-002-023 IAP obligations inventoried before readiness**(§27 q14·§28 item 16) — Trading Approval Policy/
    Generation·request/decision/consumption/Intent lineage·writer fence(§13 obligation 3의 all-intents에 포함; iap는
    이미 배포 #15 — SBR은 그 결과를 obligation 입력으로 소비, iap import 아님 §0.4d).
15. **downstream cross-ADR recovery obligations(VTG/IOC/ARE/AFG)**(§13 obligation 8–11 line 361–364·§28 items
    12–15) — ADR-002-019/020/021/**022(AFG, #16 세션 B)**의 policy/generation·snapshot·decision·invalidation·
    non-revival이 recovery obligation. **AFG는 §13 obligation 11(line 364) 주입 slot·문서-수준 인접(§3.5)** — 세션 B
    구현 완료 후 obligation 결과 배선(**afg 구현은 실재하나 obligation 배선은 EV-L2/L3 런타임 대기 — Phase-1은
    slot만**; v1.1 MAJOR-2 근거 교체: "코드 부재"가 아니라 런타임 배선 이연).
16. **ADR-002-016 ERI evidence custody/replay(recovery artifacts)**(§22·§28 item 9) — replay ENGINE(§2.3 레코드
    substrate만 Phase-1).
17. **ADR-002-024 CUR Currentness Vector 통합**(§9 line 272) — Recovery Generation·barrier/readiness floor를
    Currentness Vector 차원으로·Egress Currentness Proof(§6.2 술어만).
18. **ARCHITECTURE-GATE-STATUS 명시 acceptance 결정**(§28 item 19) — 실행된 SBR-EV-001..012 + cross-system
    evidence(CII/VTG/IOC/ARE/AFG/IAP/RCLP/EGRESS/HAG/ERI/TIME/SA/RC, §28 items 10–16) + 독립 리뷰
    (Independent-Safety-Reviewer 하드 배제).

---

## 10. 개정 로그 + 비준 체크리스트

### 10.1 개정 로그

- **v1.0 (2026-07-26) — 초안, 독립 비평 리뷰 대기.** ADR-002-017(SBR)을 Phase 1(EV-L1) 설계 계약으로 실현. 문서
  번호 **#17**(병렬 세션 B의 ADR-002-022 AFG가 #16 선점, 문서 번호 규약 절). 패키지 `tos.sbr`(대안 `tos.recovery`
  [명료·verbose·토큰 오염 — recovery_generation cross-cutting] runner-up, `tos.startup`[부분]·`tos.barrier`[기전·
  동시성 용어 collision]·`tos.resume`[부분] 기각, §0.4a). 8-아티팩트(`RecoveryTrigger`·`RecoveryBarrierState`·
  `RecoverySession`·`RecoveryGeneration`[=`tos.ordering` REUSE]·`RecoveryInventoryCut`·`RecoveryObligation`+
  `RecoveryObligationGraph`·`RecoveryEvidencePackage`·`RecoveryReadinessDecision`) + all-false
  `RecoveryAuthorityEffect`(§2). EV 분류: **core 5행(SBR-EV-004/006/007/009/012, 전부 `EV-L1/3`) / predicate-only
  7행(001/002/003/005/008/010/011, 최소 ≥ L2·+Security 5·+Broker 1) / not-Phase-1 — 닫는 SBR-EV = 0건**(§1). seam:
  **orthostate/recon/rcl/protective/authority/liveauth/spg scalar·bool·enum-token·verdict producer/consumer +
  sibling edge 0건(대안 typed-enum-reuse 1~3 edge §0.4c), PROMOTE 0**(코드 실측: orthostate `reconstruct_conservative`
  `predicates.py:23-24`, recon `classify_field` `predicates.py:107`·no-blend `:10-11`, rcl `credible_union_capacity`
  `predicates.py:739`·`partition_verdict` `:711`·`QUARANTINED_UNKNOWN` `vocabulary.py:29`, protective
  `dominating_halt_or_incident` `records.py:202`·`predicates.py:395`, authority `_REARM_PREREQUISITES`
  `predicates.py:96/108`·`is True` `:769`·`GenerationVector.recovery_generation` `state.py:50/42-43`·
  `recovery_generation_revives_nothing` `:787`, liveauth `recovery_current` `state.py:139`·`recovery_readiness_enlarged`
  `:208`, spg `rollback_revives_nothing` `__init__.py:90`, §3.4). **핵심 아키텍처 판정**: (i) **sbr = recovery
  orchestrator, per-dimension/per-field 판정은 형제 소유**(§3.5) — state reconstruction=orthostate·confidence=recon·
  capacity=rcl·HALT dominance=protective·re-arm checklist=authority/liveauth·live-auth=liveauth; sbr는 session/
  inventory/obligation-graph/readiness/invalidation orchestration만. (ii) **iap `invalidation_closure` 동형성 =
  로컬 저작(import 기각·PROMOTE 기각)**(§0.4d) — 근거: firewall sibling-edge-0·`recovery_generation_revives_nothing`이
  authority/time/rcl **3 replica**로 존재하는 established REPLICATE-WITH-NOTE 관행·§8 unknown-widen 도메인 규칙 추가·
  §13은 DAG-validity bool로 iap reachability와 **비동형(반환형 상이)**·PROMOTE는 iap touch+신규 중립 모듈 필요; DRY는
  property-test 계약 수준에서 보존. (iii) **§21 handoff — SBR readiness는 re-arm 전제 생산자**(§3.5 핵심 판정 2):
  `recovery_coordinator_evidence_complete` 생산(authority `_REARM_PREREQUISITES` item 12), re-arm admissibility는
  authority/liveauth 소유·`is True` 소비; readiness는 첫 입력이지 permission 아님(SBR-INV-003/014). (iv)
  **`recovery_generation` 좌표 소유**(§3.5 핵심 판정 3): authority가 reference-only carry(`state.py:42-43`)·SBR이
  fence 의미 소유·SCL commit은 런타임. (v) **truthy-sentinel 구조 봉인을 처음부터**(#14 M1 선제): `ReadinessVerdict`·
  `SessionState`·`RecoveryBarrierState`·`ObligationResult`는 `__bool__ ⇒ TypeError` ⇒ 소비 게이트 `is READY`/`is
  SATISFIED`·`bool|None`은 `is True`(§4.7) — barrier state는 §9 line 257 "No barrier state alone permits" 때문에
  임계. 중심 fail-closed 술어: `recovery_inventory_complete`(§12 완전·결측⇒NOT_READY)·`obligation_graph_closed`
  (폐포·acyclicity·missing/cyclic⇒NOT_READY)·`recovery_scope_closure`(§8 도달성·unknown⇒확장)·
  `unknown_stays_conservative`+`timeout_is_restrictive`(repeated UNKNOWN↛known·timeout no-fallback·obligation set
  비감소)·`restricted_isolation_proven`(§17 8조건 전수 양성·label≠proof)·`readiness_invalidated_by_change`(material
  change 폐포·before authority)·`recovery_completion_revives_nothing`(무조건 True·5 revival vector)(§5). predicate-
  only 7종(§6). **∅-공허 양방향**(결측 inventory·빈 obligation set[17항]·빈 dependency 폐포·UNKNOWN+capacity — 금지+
  허용 둘 다, §4.7). 앵커: SBR-INV-001..014·SBR-AC-001..012·SBR-EV-001..012(§0.4f). **bounds 실측**: SBR-owned 6
  profile 키(line 205·212·198·708·701·443) + handoff-age(735) + 3 policy-pin(46–48) 전부 실재·null/PROPOSED
  (candidate 신규 키 0건, §8.1). 선제 봉합: fail-open(§4.1/§5.1)·∅-공허 양방향(§4.7)·under-realization(전용 술어는
  실재하는 형제 seam에만·orthostate reconstruction·recon confidence는 정직 이연)·phantom 타입 0(전 인용 grep 실측·
  필드-클래스 소유까지 확인 #15 M1 교훈)·verbatim+line·차원 비붕괴(§2.2 (5)·§3.5 — `ObligationResult`≠
  `FieldConfidenceClass`)·**truthy-sentinel 구조 봉인(#14 M1 선제)**·**과대 주장 금지(extra="forbid"는 모델 필드
  수준만)**. **어떤 EV도 닫지 않음·acceptance 미선언·비준 기록 = "2026-07-26 운영자 위임 자동 비준(v1.1)".**

- **v1.1 (2026-07-26) — 독립 비평 리뷰 REVISE(CRITICAL 0·MAJOR 2·MINOR 5·NIT 1) 반영, forward-only(오케스트
  레이터 직접 적용).** **MAJOR-1**: firewall 배제 목록에 실재 최인접 형제 **`tos.afg` 추가**(§0.3·§7.1 — 세션 B가
  저작 중 구현 완료[3252 LOC]한 레이스로 누락; sbr→afg edge의 유일 가드 구멍이었음; 카운트 17=실재 16+venue).
  **MAJOR-2**: "AFG 코드 부재" 사실 주장 정정(헤더·§3.4 ×2·§9.2 item 15·§10.2) — 구현 실재하나 **sibling-edge-0
  규율로 injection 소비 유지**(설계 결론 불변); §9.2 이연 근거를 "코드 부재"→"EV-L2/L3 런타임 배선 대기"로 교체.
  **MINOR-1~4**: rcl `recovery_generation_revives_nothing` `:802`(docstring `:26` 병기)·§7:208(Safety Control
  Plane namespace — §9:262 오귀속 정정)·§14:386·spg `:78`. **MINOR-5**: §5.3/§5.6 **공유 폐포 커널
  `_reachability_closure` 명시** + §7 공유 property 계약(iap·§5.3·§5.6 3-구현 회귀). 리뷰어 검증 확인: 3-replica
  선례 실재(authority:787·time:499·rcl:802)·6개 아키텍처 판정 전부 방어 가능·SBR-INV verbatim 정확.

### 10.2 비준 체크리스트 (운영자 · 독립 리뷰어 확인 사항)

1. **패키지 명명** `tos.sbr`(Safe Startup and Recovery Barrier) 승인 — **또는 `tos.recovery`**(명료·verbose·토큰
   오염). **[운영자 판단 지점]**: `sbr` register-prefix 충실(`SBR-EV`/`AC`/`INV` 1:1)·terse 관행·오독 경미이나
   `sbr` 약어 자체가 opaque한지 vs `tos.recovery`가 `recovery_generation`(authority carry)·`*_revives_nothing`(3
   replica)와 토큰 오염하는지. naming은 load-bearing 아님(설계 #1 line 164). `tos.startup`/`tos.barrier`/`tos.resume`
   기각 근거 검토(§0.4a).
2. **iap `invalidation_closure` 동형성 판정(§0.4d — 최대 아키텍처 공격 지점)**: **로컬 저작(import 기각·PROMOTE
   기각)**이 정확한지 vs (a) `sbr → iap` import로 재사용, (b) 순수 그래프 폐포를 `tos.graph` 중립 모듈로 PROMOTE.
   **[운영자 판단 지점]**: DRY 순수주의자는 "iap `invalidation_closure`(`predicates.py:347`) 중복 = DRY 위반"을
   공격할 것. 반론 검토: (i) `recovery_generation_revives_nothing`이 authority(`predicates.py:787`)/time/rcl
   (`predicates.py:26`) **3 replica**로 존재하는 established 관행, (ii) firewall sibling-edge-0, (iii) §8
   unknown-widen 도메인 규칙 추가로 literally 다른 함수, (iv) §13은 DAG-validity **bool**로 reachability **집합**과
   비동형, (v) PROMOTE는 비준된 iap touch + 신규 중립 모듈 창설 필요. 리뷰어: iap `predicates.py:347-401` 폐포
   알고리즘과 §5.3/§5.6 동형 규율 대조.
3. **sibling edge 0 vs typed-enum-reuse(§0.4c)**: edge 0(injected scalar/bool/enum-token, liveauth
   `protective_coverage_valid` 선례)이 정확한지 vs recon `FieldConfidenceClass`·orthostate `KnowledgeState`·rcl
   `CapacityState` typed-reuse(1~3 edge, 타입 안전). **[운영자 판단 지점]**: opaque token injection이 실 의존 은폐인지
   (반론: §7.1 seam cross-check가 token↔형제 enum 정합 강제). 리뷰어: liveauth `state.py:138-139` injected-bool 패턴이
   SBR 규모에도 유지 가능한지 검증.
4. **`ObligationResult` ≠ recon `FieldConfidenceClass`(§3.5 핵심 판정 1)**: SBR이 obligation-satisfied 여부만 판정하고
   recon이 confidence class를 판정하는 경계가 정확한지 — SBR이 confidence를 재계산하면 권위 중복(§14 line 380).
   리뷰어: recon `predicates.py:10-11` no-blend·`:107` classify_field 소유 확인.
5. **§21 handoff — readiness ≠ re-arm(§3.5 핵심 판정 2)**: SBR readiness가 `recovery_coordinator_evidence_complete`
   **생산자**이고 re-arm admissibility(authority `_REARM_PREREQUISITES` `predicates.py:96`·`is True` `:769`)가 하류
   소유인 경계가 정확한지. **[리뷰어 공격]**: "readiness=True면 re-arm 자동 아닌가?" — 반론: 14항 중 하나일 뿐·
   `fresh_live_authorization_issued`·`explicit_human_dual_control_complete` 남음·SBR-INV-014 line 198 "fresh governed
   re-arm is mandatory". 리뷰어: authority `predicates.py:96-111` 14-item·item 12 확인.
6. **`recovery_generation` 좌표 소유(§3.5 핵심 판정 3·§0.4e)**: authority `GenerationVector.recovery_generation`
   (`state.py:50`)이 reference-only(`state.py:42-43` "their owning ADR fences them")이고 SBR이 fence 의미 소유·SCL이
   commit인 경계가 정확한지. **[리뷰어 공격]**: "recovery_generation을 누가 advance/fence하나 — authority인가 sbr인가?"
   — 반론: authority carry·SBR fence 의미·SCL(ADR-002-012 §11 line 311) commit. §4.3 non-collapse canary.
7. **orthostate reconstruction 경계(§3.4/§3.5)**: SBR §14 RECONCILING이 orthostate `reconstruct_conservative`
   (`predicates.py:23-24`, codomain excludes RECONCILED)를 **소비**하되 재저작 안 하는 경계. **[리뷰어 공격]**: "SBR
   §14 reconciliation이 orthostate와 겹친다 — 권위 중복?" — 반론: orthostate=per-dimension 재구성 소유, SBR=obligation
   orchestration; SBR은 재구성 결과를 obligation 입력으로 fold.
8. **§13 obligation-graph 폐포 설계(§5.2·SBR-EV-004)**: DAG 완전성+acyclicity(dangling⇒NOT_READY·cycle⇒NOT_READY·
   self-satisfy 금지·17항 minimum set)가 §13 line 372·§28 item 5와 정합하는지. iap reachability와 **반환형 상이**
   (bool vs 집합)임을 리뷰어가 확인. §8 scope-expansion closure(§5.3, unknown⇒확장)는 iap `uncertain` 확장 동형.
9. **READY_RESTRICTED isolation(§5.5·§17·SBR-EV-007)**: 8조건 전수 positive proof·"unless positively proven" fail-
   closed default·label≠proof(§17 line 447)가 정확한지. **[리뷰어 공격]**: shared dependency의 fail-open 탈출 경로.
10. **non-revival 완전성(§5.7·SBR-EV-012)**: `recovery_completion_revives_nothing`이 5 revival vector(completion/
    health/evidence-repair/replay-match/human-ack) 전수 커버하고 authority/time/rcl/spg replica 동형인지(무조건 True·
    revival path 구조적 부재). 리뷰어: authority `predicates.py:787-820` 대조.
11. **truthy-sentinel 구조 봉인(§4.7)**: `ReadinessVerdict`·`SessionState`·`RecoveryBarrierState`·`ObligationResult`
    `__bool__⇒TypeError`가 §7 회귀로 강제되는지 — 특히 barrier state(§9 line 257 "No barrier state alone permits")·
    `NOT_READY` truthy fail-open 방지.
12. **bounds·Phase-0(§8.1·§9.2)**: SBR-owned 6 bound + handoff-age + 3 policy-pin **전부 실재·null/PROPOSED**(candidate
    신규 키 0건) 확인 + `MAX_process_suspension_ms=2000 PROPOSED`(§8 process-suspension 트리거)·
    `B_startup_reconciliation` 60s "not relaxation of the gate"(line 202) 확인. AFG(#16) injection-slot 소비(구현
    실재·edge 0 유지, v1.1)
    이연(§9.2 item 15) 확인.

