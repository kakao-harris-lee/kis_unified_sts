# 설계 문서 #13 — Aggregate Risk Projection·Adverse Scenario Evaluation 계약 (2026-07-25, v1.1)

- **대상 ADR**: ADR-002-021 — Aggregate Risk Projection, Adverse-Scenario Evaluation, and Risk-Decision
  Integrity ("ARE"). 736줄. Status **Proposed**.
- **자체 시리즈(실측·앵커)**: **ARE-INV-001..014**(§6 line 150–206, 14종)·**ARE-AC-001..012**(§26 line
  628–676, 12종)·**ARE-EV-001..012**(EVIDENCE-REGISTER-002 line 276–287, 12행). **새 시리즈 창작 금지**.
- **Depends On(ADR line 9)**: RFC-000 constitutional safe state; RFC-001 SAFE-003/004/010–015/020/021/024/
  025/030/031/034/035/040/041/043/044/048/050/051/052; ADR-002-002 through ADR-002-020.
- **시리즈 선례(동형 유지)**: 설계 #12(Safety Profile Governance, `tos.spg`, v1.1)·설계 #11(Degraded-Mode
  Protective Capacity, `tos.protective`, v1.1).
- **비준 상태**: **2026-07-25 운영자 비준(v1.1) — §10.2 판단 지점 승인(are→rcl 단일 sibling edge
  [AdverseIncrement = rcl `CapacityVector` REUSE, ADR §2:47 타입 소유·#8 선례 동형]·produced-value seam
  decoupled).** 효력: `tos/src/tos/are/` Phase 1(EV-L1) 순수·비전송 모델 + property test 착수 승인.
  독립 비평 리뷰(REVISE: CRITICAL 0·MAJOR 1·MINOR 2·
  NIT 수건) forward-only 반영(§10.1). 본 문서는 어떤 ARE-EV·ADR acceptance·restricted-live·production도
  승인하지 않는다(§0.2).

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. ADR-002-021 조항별 **Phase 1(EV-L1) 도달성 경계**(§1). **core(L1 슬라이스) / predicate-only /
   not-Phase-1(형제 소유·런타임 이연) 3분류.** **결정적 사실(register 실측·정정)**: `ARE-EV` 12행 중
   **5행(001·002·003·004·006)이 register 최소 레벨에 `EV-L1` 슬라이스 보유**(#11형 core tier; #12의 8행
   최대판보다 작고 #10의 0행보다 큼). **orchestrator 사전 카운트 "6"은 실측 결과 "5"로 정정**한다(register
   line 276–287 전수: 005·007·008·009·010·011·012는 최소 `EV-L2` — §1 표). 그러나 **닫는 ARE-EV = 0건**
   (L1 슬라이스 저작 ≠ EV closure: `/3`·`+Security`·`+Broker` 잔여). "**EV-L1-complete 주장 금지**".
2. **4-아티팩트 데이터 모델**(§2, **core**): 전부 digest-bound `IndependentIdArtifact`인
   `AggregateRiskPolicy`(§5.1/§8)·`AggregateRiskStateSnapshot`(§5.3/§9)·`AdverseScenarioSet`(§5.4/§11)·
   `AggregateRiskDecision`(§5.5/§15) + per-cell `ProjectedCell`(§12)·`BenefitProof`(§13)·`RiskDimensionDescriptor`
   (§10)·all-false `AggregateRiskAuthorityEffect`(§7/§9-INV). 어휘: `RiskDecisionResult`(GRANT/DENY/UNKNOWN —
   §1 line 15·§5.5 line 132 verbatim)·`RiskDimensionKind`/`RiskScopeKind`(§10)·`AdverseScenarioKind`(§11)·
   `BenefitKind`(§13). **digest-bound 판정 근거 = §22 evidence 요구**(policy/scenario/snapshot/decision/vector/
   limit canonical 아티팩트 + digest, line 508) + §15 decision이 "canonical digest"를 binding(line 373).
3. **conservative projection / adverse-increment dominance 중앙 불변식**(§4.1/§5.3, ARE-EV-003 substrate —
   ADR §12 line 311–328·ARE-INV-003): `adverse_increment(cells) -> AdverseIncrementResult`. **모든 credible
   execution path·adverse intermediate state 포함**(full/partial fill prefix·overlap·reversal·missing ACK);
   **favorable final intent가 temporary/uncertain risk를 지우지 못함**(§12 line 328; ARE-INV-003 line 162);
   intended reduction이 requested increment을 음수로 만들지 못함(§12 line 328). **None/non-finite magnitude ⇒
   UNKNOWN/DENY**(§14; smaller vector 금지 §1 line 29).
4. **no-unproven-benefit 중앙 불변식**(§4.2/§6.1, ARE-EV-005 substrate — ADR §13·ARE-INV-005):
   `benefit_admissible(proof) -> bool`. **netting/hedge/diversification/collateral/margin-offset/liquidity/
   correlation benefit은 7 전제(§13 line 336–342) 전부 양성 증명 시에만** 적용; **missing/stale/conflicting/
   common-mode/unverifiable ⇒ zero benefit**(§13 line 344; ARE-INV-005 line 170). broker margin number·
   historical correlation·shared model output·human assertion은 증명 아님(§13 line 344).
5. **numerical safety 중앙 불변식**(§4.3/§5.5, ARE-EV-006/007 substrate — ADR §14 line 356–366·ARE-INV-008):
   NaN·infinity·overflow·underflow·negative-zero·precision-loss·non-convergence·unit-mismatch·incompatible
   schema·parser/library/model differential·nondeterministic ordering ⇒ **`UNKNOWN`/`DENY`, never a smaller
   vector**(§1 line 29). `CanonicalDecimal`(`is_finite`+scale-normalize) REUSE — **#12 NaN 구성-거부 선례
   동형**. fallback("return zero"/"use last value"/"skip failed scenario"/"accept optimizer incumbent"/"trust
   broker validation") **금지**(§14 line 365) unless 증명된 conservative upper bound.
6. **decision integrity + non-cyclic binding 불변식**(§4.6/§5.6, ARE-EV-002/008 substrate — ADR §15/§16·
   ARE-INV-002/006/009): `risk_decision(...) -> AggregateRiskDecision`. **projection 없이 결정 불가·requested
   increment > headroom ⇒ DENY·UNKNOWN state ⇒ UNKNOWN(conservative 소비·new risk 차단, ARE-INV-006 line
   173)**; **GRANT은 exact·closed·non-transferable**(§15 line 385)·빈 requested scope/vector ⇒ restrictive
   (zero/wildcard/unbounded 아님, §15 line 385); **두 decision union/reuse/patch 금지**(ARE-INV-002 line 158·
   §15 line 387). **non-cyclic**: decision은 미래 Capacity Commitment identity를 binding하지 않고
   {`decision_id`·`decision_generation`·`canonical_decision_digest`}만 forward-only 생산(§16 line 413) —
   **rcl `GrantDecisionRef`(`authority.py:53–55`)가 소비하고 `bound_reservation_*`는 rcl/conformance가 post-
   commit 충전**(코드 실측 §3.4). `AggregateRiskAuthorityEffect` all-false(GRANT ≠ capacity, ARE-INV-009 line
   185·§1 line 17; rcl `RclAuthorityEffect` `authority.py:19–36` 동형).
7. **economic-continuity·non-revival·protective 불변식**(§4.6/§6.6, ARE-EV-012/010 substrate — ADR §20/§21/
   §19·ARE-INV-011/012/013): `non_revival_holds(...)`(무조건 True — restart/restore/failover/recovery/
   reconciliation/replay/improved-inputs가 prior decision/grant/authority/live scope를 **revive 못 함**, §21
   line 488–500; spg `expiry_revives_nothing`·rcl `recovery_generation_revives_nothing` 동형) ∧
   `economic_effect_persists(...)`(missing ACK/cancel ACK/expiry가 capacity를 release 못 함, ARE-INV-011 line
   193; §20 line 480) ∧ `protective_creates_nothing(...)`(exit/reduce-only/emergency label이 capacity/
   feasibility/allocation 창조 못 함, ARE-INV-012 line 197; §19 line 470).
8. **currentness/invalidation·stale-evaluator 술어**(§6.4, ARE-EV-009 substrate — ADR §17/§18·ARE-INV-010):
   material change ⇒ affected unconsumed decision invalidate; **cached GRANT·TTL·heartbeat·health·last-known-
   generation·eventual-consistency·absence-of-invalidation ≠ currentness proof**(§17 line 440; ARE-INV-010
   line 190); stale generation/cut ⇒ fenced; race ⇒ potentially-live·capacity-covered·blind retry 금지(§17
   line 442).
9. **ARE ↔ protective/rcl/spg/orthostate/capsule/recon 경계(중심 아키텍처)**: ARE는 **sibling edge 1건(are→rcl,
   `CapacityVector` REUSE만)**을 유지한다(§0.4b/§0.4c v1.1/§3.4; #8 orthostate→rcl 선례 동형·실측 `orthostate/
   records.py:36`). ARE는 (i) protective가 소비하는 **conservative 비교 magnitude**(`AggregateRiskComparison`·
   `IntermediateStateWitness`, `records.py:136–168`)와 cancellation-arbiter 악화 flag(`predicates.py:529/531`),
   (ii) rcl `GrantDecisionRef` decision scalar(`authority.py:53–55`)·all-false authority block, (iii) spg
   semantic-validation step 7 `aggregate_effect_within`(`records.py:205`)을 **생산**하고, (iv) spg envelope/
   profile 상한(§8)·capsule snapshot validity(§9)·recon `ConservativeBound`(§9/§20)를 **주입 소비**한다.
   **rcl `CapacityVector`(최종 `AdverseIncrement[s,d]` 타입, ADR-002-002 소유)만 import하고 나머지 11 형제
   (protective/spg/liveauth/authority/time/capsule/evidence/brokercap/orthostate/recon/dsl)는 미import** —
   produced-scalar/bool로만 참조. `tos.are`는 `tos.canonical`·`tos.ordering`·`tos.rcl`(CapacityVector)만
   import한다(§0.3). **PROMOTE 0건. sibling edge 1건(are→rcl, rcl↛are 실측 acyclic).**
10. **fail-closed 규율 + named both-ways canary**(§4·§5·§6): 미증명 benefit ⇒ zero; None/non-finite ⇒
    UNKNOWN/DENY; increment>headroom ⇒ DENY; UNKNOWN state ⇒ restrictive; decision union/patch ⇒ 불가; 만료/
    복구 ⇒ non-revival; **빈 scenario set·빈 dimension set·빈 scope set ⇒ 보수적 UNKNOWN/DENY**(∅-공허, §4.7 —
    **양방향** 명시). 각 가드에 both-ways canary.
11. **property-test 하네스 타깃**(§7, §1 분류 정렬) + import-closure 검증(§7.1) + run manifest 7항목(§7.2) +
    fixture clean-vs-illegal 정합(#8 교훈) + seam cross-check(test-only, §3.4).
12. **bounds 주입 계약 + Phase-0 이관**(§8): ARE decision 구조에는 numeric bound 부재(전부 enum·boolean·집합
    논리·주입 `CanonicalDecimal`); ADR-002-021이 요하는 수치(invalidation-to-RCL·invalidation-to-egress·
    snapshot age·decision age)는 **VERIFICATION-PROFILE-002에 4키 전부 실재**(null/MEASURE — §8.1 실측)이며
    **candidate 신규 키 0건**(#10형 "0 누락"; #12의 4-key 누락과 대조). 값 승인은 Bounds-Approver 게이트.

### 0.2 하지 않는 것 (경계·NO 목록)

- **ADR/스펙 비준·acceptance·restricted-live·production 어느 것도 승인하지 않는다.** ADR §29 line 719
  "ADR-002-021 SHALL remain `Proposed` until all of the following are complete"·line 736 "This ADR authorizes
  architecture and implementation-planning work only. It grants no capacity, Accepted status, restricted-live
  readiness, production readiness, or live trading authority." **닫는 ARE-EV = 0건.**
- **capacity 산술(commit/consume/release·serialize·quarantine·transfer)을 저작하지 않는다.** 그것은
  **rcl(#5, ADR-002-002/012)이 이미 소유·구현**했다 — `CommittedReservation`(`state.py:48`)·`transition_allowed`
  (`predicates.py:438`)·`grant_authorizes_exact_request`(`predicates.py:575`). ADR §1 line 17 verbatim "Only the
  Risk Capacity Ledger may serialize and mutate capacity"·§7 line 217 "Evaluator … SHALL NOT mutate capacity".
  ARE는 decision scalar를 **생산**하고 rcl이 binding·serialize(§3.4). **단, 최종 `AdverseIncrement[s,d]`의
  타입은 rcl `CapacityVector`(`vector.py:74`, ADR-002-002 §6 소유)를 REUSE한다**(§0.4c v1.1 MAJOR-1 채택; are→rcl
  1 edge, rcl↛are 실측 acyclic·#8 orthostate→rcl 선례) — vector **타입**만 공유하고 commit/serialize/benefit
  산술은 여전히 rcl 소유(중간 `ProjectedCell`은 are-local).
- **final egress·Live Authorization·capability·Commit Proof를 저작하지 않는다.** ADR §16 line 408–410(Live
  Authorization / capability / Commit Proof / final-egress active-currentness)은 **ADR-002-007/013 런타임**이다.
  ADR §1 line 17 "Final egress remains the final transmission enforcement point." ARE는 결정 bool/scalar만
  반환하며 **전송·capability 발급을 하지 않는다**(§4.5; ARE-INV-014 line 205).
- **Hard Safety Envelope·Runtime Safety Profile 거버넌스를 재저작하지 않는다.** 그것은 **spg(#12, ADR-002-014)
  가 이미 소유·구현**했다 — `HardSafetyEnvelope`·`RuntimeSafetyProfile`·`profile_within_envelope`·
  `restrictive_override_admissible`. ADR §8 line 232 "Hard Safety Envelope and Runtime Safety Profile bindings"·
  §1 line 27 "The Runtime Safety Profile may narrow limits only." ARE는 envelope 상한을 **주입 소비**하고
  `aggregate_effect_within`(step 7)만 spg에 **생산**한다(§3.4). envelope enlarge 금지(ARE-INV-007 line 178).
- **protective classification·degraded-mode·cancellation arbiter·protective-lease를 재저작하지 않는다.** 그것은
  **protective(#11, ADR-002-001)가 이미 소유·구현**했다 — `protective_classification`(`predicates.py:246`)·
  `ProtectiveActionOutcome`. ARE는 그 classifier가 소비하는 **conservative aggregate-risk magnitude를 생산**
  하고 protective가 **비교**한다(§19 line 460–468; `records.py:139` "supplied by ARE … protective compares";
  design #11 §3.5). **이것이 #11 OQ3의 의존 구멍을 메우는 지점이다**(§3.4).
- **consistency-cut protocol·snapshot 조립 런타임·Aggregate Risk Generation fence enforcement·독립 verifier
  런타임을 구현하지 않는다.** ADR §9(snapshot 조립)·§18(stale-evaluator fence)·§23(independent verifier·
  common-mode)은 **EV-L2/L3 런타임**이다(§28 q3/q9). Phase 1 ARE는 결정 술어만 저작하며 **snapshot을 조립하지
  않고**(주입 소비) **generation을 fence 실행하지 않는다**(순수 동등/순서 검사만).
- **scenario/valuation/margin/liquidity/correlation의 수치 시뮬레이션·상관계수·시나리오 값을 산출하지 않는다.**
  ADR §4 non-scope line 107 "the concrete risk engine, optimization solver, scenario generator, numerical
  library"·§28 q4는 이를 **명시 배제**한다. **전부 주입 `CanonicalDecimal`/`bool`**이며 ARE는 projection 산술의
  **수치 엔진이 아니라 결정 무결성 규칙**(보수성·단조성·비순환·currentness·non-revival)만 저작한다.
- **numeric age·invalidation·execution bound를 승인하지 않는다.** ADR §4 non-scope line 108 "numeric age,
  invalidation, or execution bounds, which require an approved Verification Profile"·§28 q12. 전부 주입
  파라미터/`CanonicalDecimal`로 담고 **어떤 숫자도 하드코딩하지 않는다**(CLAUDE.md). 값 부재 ⇒ fail-closed. 값
  승인은 Bounds-Approver 게이트(§8·§9.2).
- **ADR-002-022 action-flow vector·permit(§29 item 13)·ADR-002-023 approval(§29 item 14)를 저작하지 않는다.**
  AFG(action-flow)·IAP(intent/approval)는 별도 ADR·EV family이며 rcl `GrantDecisionRef`는 "Aggregate Risk /
  **Action Flow** decision"을 공통 참조하나(`authority.py:40`) ARE는 aggregate-risk 축만 담는다.

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

`tos.are` 모델은 다음만 import한다:

- 서드파티: `pydantic`(frozen 모델), `pytest`·`hypothesis`(테스트만). **`numpy`/`pandas`/`pyyaml`도 import하지
  않는다** — projection 결정 규칙은 StrEnum·boolean·집합 논리이고 수치는 `CanonicalDecimal` 산술(비교·`is_finite`·
  scale-normalize)뿐이라 수치 백엔드 불필요하며, 모든 bound·scenario 값·상관계수·시나리오 magnitude는 주입
  파라미터이고 YAML 파싱은 하네스(설계 #3) 소관이다(closure 최소화 — #5–#12 §0.3 동형).
- tos 자기 자신: `tos.canonical`(`FrozenModel`·`DigestBoundArtifact`·**이미 core인 `IndependentIdArtifact`**·
  **이미 core인 `classify_record_pair`**·`RecordPairKind`·`ArtifactStatus`·**이미 core인 `CanonicalDecimal`**),
  `tos.ordering`(Aggregate Risk Generation·decision·snapshot append-only 순서 — §3.2), **`tos.rcl`(최종
  `AdverseIncrement[s,d]` 타입 `CapacityVector` REUSE만 — §0.4c v1.1; 실측: rcl closure = canonical+ordering+self,
  타 형제 미포함이라 are→rcl은 clean edge)**, `tos.are.*`. **`tos.protective`·`tos.spg`·`tos.liveauth`·
  `tos.authority`·`tos.time`·`tos.capsule`·`tos.evidence`·`tos.brokercap`·`tos.orthostate`·`tos.recon`·`tos.dsl`
  (11 형제)을 import하지 않는다**(produced-scalar/bool·주입 좌표로만 참조 — §3.4/§3.5). **PROMOTE 0건. sibling
  edge 1건(are→rcl).**
- **`shared.config` 절대 금지**(설계 #1 §6.1, `.importlinter`): `shared.config.__init__`이
  `shared.config.secrets`(→ `os.environ`)를 무조건 전이 import한다. `tos.are`는 어떤 `shared.*`도 필요로 하지
  않는 순수 커널이다.
- **금지(직접·전이 모두)**: `shared.execution`, `shared.kis`, `shared.streaming`, `shared.llm`, `shared.storage`,
  `shared.backtest`, `services.*`, `cli.*`(`.importlinter` forbidden set).
- **firewall 구조 확인(실측)**: `.importlinter`는 **`[importlinter:contract:tos-operational-firewall]` type=
  forbidden·source_modules=`tos`** 단일 계약이며(line 29–34 실측) `layered` 계약이 아니다 — intra-tos sibling→
  sibling edge는 구조적으로 금지되지 않고 설계 #1 §3.2의 "자기 자신 `tos.*`" 허용 조항이 이를 커버한다. **신규
  패키지 `tos.are`는 firewall 도구 무수정 자동 포섭**된다(forbidden 계약이 source=tos 전체를 덮으므로). **intra-
  tos sibling edge가 구조적으로 허용되므로 are→rcl(`CapacityVector` REUSE, §0.4c v1.1) edge는 firewall 위반이
  아니다**(#8 orthostate→rcl `orthostate/records.py:36` 동형 — 이미 존재). 본 문서는 그 외 **magnitude/decision
  seam을 produced-scalar/bool 주입(edge 0)**으로 유지하는 것을 **설계 규율**로 삼는다(§0.4b; #11/#12 동형; are의
  전체 sibling edge는 are→rcl 1건).
- 이 배제를 능동 강제하는 것이 §7.1 import-closure 검증 테스트다(`import tos.are` closure에 금지·`shared.config`·
  `os.environ`·numpy/pandas/yaml·**11개 형제 tos 패키지**(rcl 제외) 부재 assert; **`tos.canonical`·`tos.ordering`·
  `tos.rcl`은 존재 허용**). required check(`tos-firewall`, `tools/tos_firewall_check.py` layer-① AST +
  `.importlinter` layer-② 전이 방어)와 함께 green이어야 성립.

### 0.4 REUSE / import / 경계 결정 요지 (핵심 아키텍처)

**(a) 패키지 위치·명명 = `tos/src/tos/are/`.** register domain(EVIDENCE-REGISTER-002 line 276) "**Aggregate
Risk Evaluation**"·prefix `ARE`(`ARE-EV`/`ARE-AC`/`ARE-INV`)를 직접 명명. 명명 대안 비교(#12 §0.4a 형식):

- **`tos.riskproj`(risk projection)(기각·좁음)**: §12 projection 산술만 명명해 **지나치게 좁다** — ARE는
  projection뿐 아니라 **decision integrity(§15)·non-cyclic binding(§16)·currentness(§17)·non-revival(§21)**를
  포함하며(#11이 `tos.degraded`를 "좁다"로 기각·#12가 `tos.envelope`를 "좁다"로 기각한 것과 동형). verbose하고
  register prefix `ARE`와 어긋남.
- **`tos.aggrisk`/`tos.riskeval`(기각·비관행)**: 어색한 portmanteau이거나(aggrisk) register prefix와 불일치
  (riskeval). terse 명명 관행(canonical/capsule/rcl/recon/liveauth/dsl/brokercap/spg)과 어긋남.
- **`tos.risk`/`tos.projection`(기각·collision)**: `tos.risk`는 **rcl(Risk Capacity Ledger)** 및 도처의
  "risk" 토큰과 의미 충돌; `tos.projection`은 ADR §7 line 215 "Position/Order **Projection**"(snapshot 생산자,
  형제 소유)과 충돌·지나치게 generic. 하드 기각.
- **선택 `tos.are`**: **register domain "Aggregate Risk Evaluation"·prefix `ARE`**를 직접 명명, terse, ADR
  제목의 핵심(Aggregate Risk **E**valuation)을 포섭. 의미 있는 두문자로 `tos.rcl`(Risk Capacity Ledger)·
  `tos.spg`(Safety Profile Governance)·`tos.dsl`(Strategy DSL) 동형. **naming은 load-bearing이 아니다**(설계
  #1 line 164) — 운영자 치환 가능; **load-bearing은 layering**(are → canonical·ordering·**rcl(CapacityVector
  REUSE, §0.4c v1.1)** 한 방향; protective·spg·liveauth·authority·time·capsule·evidence·brokercap·orthostate·
  recon·dsl과 형제/상하류, **produced-scalar/bool seam·edge 0건**; rcl만 1 edge).
  주의(정직 이연): `are`는 영어 상용어("are")라 코드에서 `import tos.are as are`는 어색하나 `from tos.are import
  …`는 명확하고 3-letter 두문자는 rcl/spg/dsl 관행 정합. 실측: `tos/src/tos/are` 부재·`tos.are`/`tos.riskproj`/
  `tos.aggrisk` 토큰 tos 내 0건(충돌 없음). 내부 module(`vocabulary.py`·`records.py`·`predicates.py`·`state.py`·
  `_base.py`)은 rcl/spg/protective 선례 동형.

**(b) are = produced-scalar/bool producer, sibling edge 1건(are→rcl `CapacityVector`만) (중심 결정, 코드 실측).**
ARE는 **protective·rcl·spg·orthostate 4개 소비자의 상류**(또는 상호)이면서 **spg·capsule·recon 3개 생산자의
하류**다. produced-value seam은 전부 produced-scalar/bool 주입(edge 0)이고, **유일한 package edge는 최종
`AdverseIncrement[s,d]` 타입 공유를 위한 are→rcl `CapacityVector` REUSE**다(§0.4c v1.1 MAJOR-1). **코드 실측 seam**
(sibling 서사 아님 — #10 MAJOR-1 교훈):

| are 산출 (§5/§6) | 타입 | 소비처 (이미 비준·구현) | 소비 signature(실측) |
|---|---|---|---|
| conservative 비교 magnitude 4종 | `CanonicalDecimal\|None` | protective `protective_classification` | `AggregateRiskComparison.{final_conservative_risk, current_conservative_risk, no_action_risk}`·`already_exceeded_regime:bool\|None`(`protective/records.py:149–152`; None⇒`RISK_INCREASING_DENIED` `predicates.py:289–290`) |
| intermediate-state witness 3종 | `CanonicalDecimal\|None`·`bool\|None` | protective `protective_classification` §6.2 | `IntermediateStateWitness.{worst_intermediate_risk, credible_space_bounded, no_credible_intermediate_increases_exceedance}`(`protective/records.py:166–168`) |
| cancellation 악화 flag 2종 | `bool\|None` | protective cancellation arbiter | `continued_existence_worsens_aggregate`/`cancellation_worsens_aggregate`(`protective/predicates.py:529/531`; None⇒보수) |
| decision content ref 3종 | `str\|None`·`int\|None` | rcl `grant_authorizes_exact_request` | `GrantDecisionRef.{decision_id, decision_generation, canonical_decision_digest}`(`rcl/authority.py:53–55`); rcl이 `bound_reservation_revision/digest`·`bound_generation` post-commit 충전(`authority.py:56–58`) |
| grant identity·scope scalar | `str\|None`·`tuple[str,...]` | rcl CommitReservation covered | `aggregate_risk_authority_grant_identity`(`rcl/records.py:99`)·`applicable_risk_scopes`(`rcl/records.py:98`) |
| all-false authority block | (all-false) | rcl `RclAuthorityEffect` 동형 | `GrantDecisionRef.authority_effect`(`rcl/authority.py:59`; 어떤 True도 unconstructable `authority.py:25`) |
| `aggregate_effect_within` | `bool\|None` | spg `semantic_validation` step 7 | `SemanticValidationInputs.aggregate_effect_within`(`spg/records.py:205`; `predicates.py:466` `is not True⇒reject`) |

are가 **주입 소비**하는 상류(생산 아님·import 아님):

| 상류 산출 | are 소비(§5/§9) | 근거 |
|---|---|---|
| spg envelope/profile 상한·`aggregate_effect_within` 아님 | Hard Safety Envelope max(§8 dominance)·profile narrow-only | ADR §8 line 232·§1 line 27; spg `HardSafetyEnvelope` 상류 |
| capsule Decision Context validity | snapshot §9 Decision Context binding | ADR §9 line 255; capsule `aggregate_snapshot_validity`(`capsule/predicates.py:84`) 상류 |
| recon `ConservativeBound` | ConservativeCurrentUsage 입력(§9/§12) | ADR §9 line 249·§20; recon `ConservativeBound`(`recon/records.py:28`)·`merge_conservative`(`predicates.py:218`) 상류 |

대안 비교(#12 §0.4b 형식):

- **대안 A — are가 magnitude/decision 소비자(protective/spg/orthostate)를 import**: are가 각 소비자 typed 필드를
  참조. **기각**: (i) **backwards edge** — protective/orthostate는 dataflow상 are의 **하류**(are가 magnitude/
  decision 생산 → 소비)인데 상류가 하류를 import하면 방향 역전. (ii) **다수 ratified 패키지 접촉** — 세 소비자가
  전부 이미 비준·구현됨. (iii) 소비자들은 **이미** magnitude/decision을 주입 슬롯으로 봉인해 두었다(실측 —
  protective `records.py:139` "supplied by ARE (ADR-002-021, an unimplemented tos package)"라 명시 선언). **정정
  (v1.1 MINOR-1)**: 이 대안이 "cycle"이라는 v1.0 주장은 과장 — 소비자들은 are를 import하지 않으므로(주입 슬롯) are
  →소비자는 단일 방향 edge이며 import-graph상 cycle이 아니다. 기각 근거는 cycle이 아니라 **방향 역전 + 다수
  ratified 접촉**이다.
- **대안 B — magnitude/decision 소비자가 are를 import**: protective/spg/orthostate가 are를 직접 호출. **기각**:
  소비자 전부 **이미 비준·구현**됐고 magnitude/decision을 주입 슬롯으로 봉인했다. 지금 셋을 are 의존으로 바꾸면
  **다수 ratified 패키지 동시 접촉**(침습). **정정(v1.1 MINOR-1)**: spg↔are가 "cycle"이라는 v1.0 주장도 과장 —
  spg는 are를 import하지 않고(`records.py:205` `aggregate_effect_within: bool|None` 주입) are도 spg를 import하지
  않으므로(envelope 주입 소비) 어느 단일 방향 edge도 cycle이 아니다. 기각 근거는 cycle이 아니라 **다수 ratified
  접촉**이다.
- **선택 — magnitude/decision seam은 plain-scalar/bool 주입(edge 0), 최종 vector 타입만 are→rcl REUSE(1 edge)**:
  are는 **자신의 어휘·4-아티팩트 모델·결정 술어**를 저작하고, magnitude/decision 출력은 **plain `CanonicalDecimal`/
  `bool`/`str`/`int`**로 protective/spg/orthostate가 **이미 선언한 주입 signature와 타입 일치**(전부 `…|None`·
  fail-closed); 최종 `AdverseIncrement[s,d]`만 rcl `CapacityVector`를 REUSE한다(are→rcl 1 edge, §0.4c v1.1).
  근거: (i) #11(protective→2소비자)·#12(spg→7소비자)의 produced-bool/scalar 봉인과 **정합** — magnitude/decision은
  주입으로 유지. (ii) **acyclic 근거(정확형, v1.1 MINOR-1)**: are↔spg 양방향 value-flow(are가 envelope 소비 +
  `aggregate_effect_within` 생산)를 acyclic하게 하려면 **최소 한 방향이 주입**이어야 하고, **어느 ratified 측도
  접촉하지 않으려면 양방향 주입**이 권장이다 — 이것이 protective/spg/orthostate seam이 주입인 이유. are→rcl은
  **예외적 단일 edge**로 허용되며(rcl↛are 실측 acyclic·#8 orthostate→rcl 선례), "edge 0이 §16 non-cyclic의 유일
  실현"이라는 v1.0 주장은 **철회**한다(단일 방향 edge는 import-graph cycle이 아님). (iii) **compose seam-sealing**:
  타입 일치 + fail-closed 정합으로 seam 조립, **test-only** 모듈이 are·(각 소비자)를 **둘 다 import**해 polarity·
  fail-closed를 대조(테스트 import는 §7.1 package closure에 계상되지 않음). **운영자 판단 지점(§10.2)**: magnitude/
  decision seam decoupled(권장) + 최종 vector are→rcl REUSE(권장·§0.4c MAJOR-1) vs 자체 vector(§0.4c 기각 근거).

**(c) REUSE + PROMOTE 0건 + `AdverseIncrementVector` REUSE 결정 (v1.1 MAJOR-1 채택).** 4-아티팩트는
`tos.canonical.IndependentIdArtifact`(id⊥digest)·`DigestBoundArtifact`(digest 검증)를 REUSE한다. conservative
magnitude·projection cell·limit·headroom은 **이미 core인 `CanonicalDecimal`** REUSE(NaN/infinity 구성-거부·`1.0`
vs `1.00` digest drift 차단; bare `Decimal`/float 금지, §14 line 358) — **추가 PROMOTE 없음**. **핵심 결정 —
최종 `AdverseIncrement[s,d]`는 rcl `CapacityVector`(`vector.py:74`, ADR-002-002 §6)를 REUSE한다(are→rcl 1
edge)**: ADR §2 line 47·§16이 "ADR-002-002 defines the capacity vector, **Adverse Increment Vector**"라 명시하여
**AdverseIncrementVector의 타입 소유자는 ADR-002-002(rcl)**다 — are가 별도 vector를 재정의하면 ADR-002-002-소유
타입을 **중복 저작**하고 rcl commit 값(`CommitReservation.proposed_adverse_increment` `records.py:185`)과의 **좌표
붕괴**(§4.4) 위험을 만든다. ⇒ 최종 per-(scope,dimension) increment은 `CapacityVector`를 REUSE(타입 수준 dominance
봉인 — rcl이 commit하는 그 타입)하고, **중간 per-(scope,dimension,scenario) 표현 `ProjectedCell`은 are-local**
(rcl `CapacityVector`보다 richer, scenario 축 보유). **acyclic 실증**: rcl은 are를 import하지 않으므로(`rcl/
authority.py` `GrantDecisionRef`는 주입 `str|None`; grep 실측) are→rcl은 단일 방향 edge, cycle 아님 — ADR §16
non-cyclic은 이 edge를 금지하지 않는다(§16은 아티팩트 dependency 비순환이지 import edge 금지가 아님). 선례: #8이
orthostate→rcl edge(`orthostate/records.py:36` `from tos.rcl import CapacityState`)를 비준받음(동형). 완화:
ADR §16 line 415–422가 rcl commit-time 독립 한도 재검증(2차 게이트)을 요구.
**기각 대안 (v1.1 §10.1 기록)**: (b) **자체 vector(v1.0 결정)** — are가 `AdverseIncrementResult`(CanonicalDecimal
tuple)를 저작하고 rcl `CapacityVector`로의 축약을 미래 런타임(EV-L3)에 이연. **기각 근거**: (i) 축약 reducer가
Phase-1에 **미명세**이므로 v1.0이 주장한 "dominance under-count 0을 seam cross-check가 봉인"은 **존재하지 않는
reducer에 대한 assert 불가**(리뷰어 실증); (ii) ADR-002-002-소유 vector 타입 재정의 = 좌표 붕괴 위험. (c) **canonical
PROMOTE** — 무거움(현재 rcl+are만 필요), 기각. **운영자 판단 지점(§10.2)**: (a) REUSE(권장·채택) vs (b) 자체
vector(축약 reducer + property를 Phase-1 명세해야 함).

**(d) `id=f(digest)` 미채택 (canonical REUSE).** Policy·Snapshot·ScenarioSet·Decision은 **거버넌스/평가-할당
identity**(policy version/signer/approval §8; snapshot consistency-cut identity §9; decision issuer/issue-
evidence §15)를 가지며, same-id/diff-bytes(위조·재발행·contradictory decision) 탐지에 `classify_record_pair`
(`RecordPairKind.CRITICAL_CONFLICT`)를 쓰려면 id⊥digest여야 한다(#4–#12 §3.1 동형). ⇒ `IndependentIdArtifact`
채택, `IdDerivedArtifact`(capsule content-addressed) 미채택. **결정적 코드 증거**: rcl `GrantDecisionRef`가
`decision_id`(53)와 `canonical_decision_digest`(55)를 **별개 필드**로 담는다 — decision은 id⊥digest임을 소비 측이
이미 전제. 각 Generation은 immutable append-only 레코드이며 정당한 revalidation/supersession은 **새 generation**
(§5.4 line 128 "Absence from the set is not proof")이지 in-place mutation이 아니다. **`tos.are._base` 명확화
(v1.1 NIT)**: canonical 원시타입(`FrozenModel`·`DigestBoundArtifact`·`IndependentIdArtifact`·`CanonicalDecimal`)의
thin re-export이되, **all-false `AggregateRiskAuthorityEffect`의 베이스(all-false authority 계약)는 canonical에
없으므로 `tos.are._base`에서 로컬 fresh 정의**한다(rcl `_base.py:55` `AllFalseAuthority` 로컬 정의 동형 — are→rcl
edge가 있어도 이 계약은 재사용하지 않고 로컬 저작해 edge 목적을 `CapacityVector` 단일 용도로 유지). `CapacityVector`
자체는 rcl에서 REUSE(§0.4c).

**(e) 형제/상하류 import·미import 근거(§3.5 소유권 분할 요지).**
- **`tos.rcl` — `CapacityVector`만 import(v1.1 MAJOR-1; 유일 sibling edge)**: rcl이 §16 binding·capacity 산술·
  `transition_allowed`·`grant_authorizes_exact_request`를 소유. are는 최종 `AdverseIncrement[s,d]` **타입만**
  `CapacityVector`를 REUSE하고(§0.4c) decision scalar를 생산 → rcl `GrantDecisionRef`가 소비·bound_reservation
  post-commit 충전(non-cyclic, §16 line 413). capacity mutate·commit·serialize·benefit 산술은 여전히 rcl 소유
  (§1 line 17). rcl↛are 실측 acyclic.
- **`tos.protective` 미import(#11 OQ3 상류 공급)**: protective가 `protective_classification`·`ProtectiveAction
  Outcome`·cancellation arbiter를 소유. are는 그것들이 소비하는 conservative magnitude를 **생산**하고 classify/
  compare를 하지 않는다(§19 line 460; `records.py:139`).
- **`tos.spg` 미import(envelope 상류·`aggregate_effect_within` 하류 = 상호 value-flow)**: spg가 envelope/profile
  거버넌스를 소유. are는 envelope 상한을 **주입 소비**하고 step-7 bool을 **생산**한다. **양방향 value-flow를
  acyclic하게 하려면 최소 한 방향이 주입이어야 하고(spg↛are 실측·are↛spg), 어느 ratified 측도 접촉하지 않으려면
  양방향 주입이 권장**이다(v1.1 MINOR-1 정확형 — "edge-0이 §16 유일 실현"은 철회; 단일 방향 edge는 cycle 아님).
- **`tos.capsule`·`tos.recon` 미import(snapshot 입력 상류)**: capsule Decision Context validity·recon
  `ConservativeBound`는 are snapshot의 **주입 입력**이다(§9). are는 그 값을 소비하나 capsule/recon을 import하지
  않는다(layering 역전 금지·주입 매개). recon은 역으로 §20에서 RCL transition을 request하는 하류이기도 하다.
- **`tos.liveauth`·`tos.authority`·`tos.time`·`tos.evidence`·`tos.brokercap`·`tos.orthostate`·`tos.dsl`
  미import**: liveauth/authority는 aggregate-risk를 scalar로만 참조(`liveauth/predicates.py:756` "RCL's concern
  referenced only by scalar"); time validity·broker capability는 주입 opaque flag; evidence replay engine은
  ADR-002-016 하류; orthostate `AUTHORIZED_FOR_CAPACITY`(vocabulary.py:43–45)는 are grant를 **state 의미로**
  소비하나 orthostate records에 전용 are-bool 필드는 **부재**(§3.4 (d) — 정직: 전용 슬롯 아닌 state 전이 의존);
  brokercap/dsl 무관.

**(f) 앵커 규약 — ARE-INV/AC/EV 앵커, 새 시리즈 창작 금지.** **실측**: ADR-002-021은 **자체 시리즈 `ARE-INV-
001..014`(§6 line 150–206, 14종)·`ARE-AC-001..012`(§26 line 628–676, 12종)·`ARE-EV-001..012`(register line
276–287, 12행)를 정의한다.** ⇒ 본 계약은 모델 불변식·술어를 **`ARE-INV-###` / `ARE-AC-###` / `ARE-EV-###` /
§-clause / `SAFE-###`(§27 traceability line 682–692)**에 앵커하고 **새 INV/AC/EV 시리즈를 창작하지 않는다**.
이는 #6/#8/#10/#12가 자체 INV에 앵커한 것과 동형이다. self-consistency 최우선.

**(g) ARE-EV = #11형 core tier(5행) but 닫는 ARE-EV = 0건.** register 실측: **5행(001·002·003·004·006)이 최소
레벨에 `EV-L1` 슬라이스 보유**(§1 표), 7행(005·007·008·009·010·011·012)은 최소 `EV-L2`. ⇒ §1 분류는 **core(L1
슬라이스 5) / predicate-only(7) / not-Phase-1 3분류**(#11형). **그러나 닫는 ARE-EV = 0건** — L1 슬라이스 저작은
EV closure가 아니다(`/3`·`+Security`·`+Broker` 통합·독립 리뷰 잔여). 이 판정은 §1·§4·§5·§7 전체에 **일관**해야
하며(어떤 §7 test-target도 ARE-EV closure를 주장하지 않음 — #8 lesson 선제 봉합), finishing 전 self-consistency
pass에서 대조한다.

---

## 1. 범위 매핑 — ADR-002-021 조항별 EV-L1 도달성 (닫는 ARE-EV 0건)

EV-level 정의(VER-002-001): **EV-L1 = Model and Property Verification**(state-machine exploration, model
checking, property-based testing, deterministic simulation). **EV-L2 = Component Fault Test**, **EV-L3 =
Integration/Adversarial**, **+Security = security enforcement**, **+Broker = broker-integration**. Phase 1은
EV-L1만이다.

> **결정적 사실 1 — ARE-EV ↔ ARE-AC 1:1, 최소 레벨 실측(사전 카운트 정정)**: `ARE-EV-001..012`(register line
> 276–287)는 ADR §26 `ARE-AC-001..012`(line 628–676)와 제목·번호가 **1:1**(§26 line 676 verbatim "Each case
> maps one-to-one to `ARE-EV-001` through `ARE-EV-012`"). register 최소 레벨 실측:
> **`EV-L1` 슬라이스 보유(5행)** = 001(`EV-L1/3` line 276)·002(`EV-L1/3+Security` 277)·003(`EV-L1/3+Broker`
> 278)·004(`EV-L1/3` 279)·006(`EV-L1/3+Broker` 281); **`EV-L1` 슬라이스 부재(7행, 최소 ≥ L2)** = 005(`EV-L2/3+
> Security` 280)·007(`EV-L2/3+Security` 282)·008(`EV-L2/3` 283)·009(`EV-L2/3+Security` 284)·010(`EV-L2/3+
> Broker` 285)·011(`EV-L2/3+Security` 286)·012(`EV-L2/3+Security` 287). ⇒ **core tier 5행**(#11형; orchestrator
> 사전 "6"은 **5로 정정**), predicate-only substrate 7행.
>
> **결정적 사실 2 — authoring ≠ acceptance(닫는 ARE-EV = 0건)**: Phase 1은 각 ARE-EV의 **L1-decidable
> predicate/model substrate**를 저작하나 **어떤 ARE-EV도 닫지 않는다.** (a) core 5행조차 `/3`·`+Security`·
> `+Broker` 잔여(fault injection·adversarial·security·broker 통합)가 남고, (b) 7행은 최소 ≥ L2, (c) VER-002-001
> §5 "Registration is not execution"·ADR §26 line 676 "Written cases are not completed evidence"·§29 line 728
> item 8. ⇒ **"EV-L1-complete 주장 금지"**(#2–#12 §1 규율 상속). Owner/Reviewer는 register상 TBD.

**규율 태그(모든 주장에 부착)**: "**predicate/coordinate substrate only; ARE-EV-001..012 전부 NOT_IMPLEMENTED —
core 5행은 `/3`·`+Security`·`+Broker` 통합·독립 리뷰 대기, predicate-only 7행은 EV-L2/L3 fault injection·
adversarial·+Security·+Broker evidence 대기. EV-L1-complete 주장 금지.**"

**ADR-002-021 조항 → Phase-1 분류(core / predicate-only / not-Phase-1[형제 소유·런타임 이연])**:

| ADR 조항 | 요지 | Phase-1 분류 | L1 substrate / 소유 (근거) | ARE-EV |
|---|---|---|---|---|
| **§9** (line 249–262) | Aggregate State Snapshot 완전성·attribution | **core (L1 슬라이스)** | `snapshot_scope_complete`·conservative 포함(§5.1) — ARE-INV-001. snapshot **조립**은 런타임(주입 소비). `/3` 잔여. | **001** |
| **§16** (line 391–425) | Exact Effect Binding·non-cyclic RCL binding | **core (L1 슬라이스)** | `exact_effect_snapshot_binding`(§5.2, ARE-INV-002 no patch/union) + decision content ref 생산(§5.6). `+Security` 잔여. | **002** |
| **§11/§12** (line 287–328) | Adverse Scenario·Projected State·Adverse Increment | **core (L1 슬라이스)** | `adverse_increment`·conservative projection dominance(§5.3) — ARE-INV-003. **protective magnitude 생산**. scenario **값**은 주입. `/3+Broker` 잔여. | **003** |
| **§10** (line 266–283) | Risk Dimensions/Units/Scopes | **core (L1 슬라이스)** | `dimension_vector_integrity`·`RiskDimensionDescriptor`(§5.4) — ARE-INV-004. per-product 열거는 Phase-0. `/3` 잔여. | **004** |
| **§14** (line 350–366) | Valuation/Margin/Liquidity/Numerical Safety | **core (L1 슬라이스)** | `valuation_conservative`+`numerical_safety` L1(§5.5) — ARE-INV-008. NaN/overflow⇒UNKNOWN/DENY. broker margin은 주입 ceiling. `/3+Broker` 잔여. | **006** |
| **§13** (line 332–346) | Netting/Hedge/Correlation/Diversification | **predicate-only** | `benefit_admissible`(§6.1) — ARE-INV-005 (7 전제 양성 시에만). common-mode 독립·+Security는 런타임. 최소 `EV-L2/3+Security`. | **005** |
| **§14 numerical determinism** (line 356–366) | parser/library/model differential·non-convergence | **predicate-only** | `numerical_determinism`(§6.2) — differential/독립 재현은 EV-L2 component-fault·+Security. 006의 L1 넘어선 부분. 최소 `EV-L2/3+Security`. | **007** |
| **§18** (line 446–454) | Concurrency/Partition/Stale-Evaluator (concurrent grant·RCL serialization) | **predicate-only** | `non_cyclic_binding`·`concurrent_not_reservation`(§6.3) — headroom 관측≠예약. serialization은 rcl 런타임. 최소 `EV-L2/3`. | **008** |
| **§17** (line 428–442) | Invalidation·Active Currentness (final-egress) | **predicate-only** | `currentness_invalidation`(§6.4) — cache≠currentness. active RCL/egress currentness는 런타임(profile bound). 최소 `EV-L2/3+Security`. | **009** |
| **§19** (line 458–472) | Protective/Exit/Degraded Evaluation·Partition | **predicate-only** | `protective_creates_nothing`(§6.5) + protective magnitude 생산(§5.3 상호참조). partition/broker-alive는 런타임. 최소 `EV-L2/3+Broker`. | **010** |
| **§7/§23** (line 210–221·534–547) | Authority Separation·Security Bypass | **predicate-only** | `AggregateRiskAuthorityEffect` all-false(§6.7) — ARE-INV-009. evaluator↛live credential·egress bypass는 +Security 런타임. 최소 `EV-L2/3+Security`. | **011** |
| **§20/§21** (line 476–500) | Recovery·Economic Continuity·Non-Revival | **predicate-only** | `non_revival_holds`·`economic_effect_persists`(§6.6) — ARE-INV-011/013. Recovery Barrier(ADR-002-017)·re-arm 런타임. 최소 `EV-L2/3+Security`. | **012** |
| **§5/§8** (line 114–145·225–244) | Definitions·Aggregate Risk Policy Contract | **core substrate(분산)** | 4-아티팩트 모델·`RiskDecisionResult` 어휘(§2). policy는 spg Bundle member(§5.1). policy **값**은 주입. | 001–012 공통 |
| **§9 consistency-cut·§18 fence enforce·§23 verifier** | snapshot 조립·generation fence·독립 verifier 런타임 | **not-Phase-1 (런타임 EV-L2/L3)** | consistency-cut protocol(§28 q3)·stale-evaluator fence(§28 q9)·independent verifier·common-mode(§23). are는 순수 동등/순서 검사만. | 001/008/009 (런타임) |
| **§16 egress·Live Auth·capability** | Live Authorization·capability·Commit Proof·final egress | **not-Phase-1 (ADR-002-007/013)** | are는 결정 bool만. 전송·capability는 런타임(§0.2). | 002/009 (런타임) |
| **§4 non-scope** (line 107–108) | risk engine·solver·scenario generator·numeric library·bounds | **not-Phase-1 (Phase-0/INSTANCE)** | 제품·알고리즘·수치 선택은 §9.2 Phase-0. 전부 주입. | — |

---

## 2. 데이터 모델 계약

**표현 원칙**: 모든 아티팩트는 **pydantic v2 frozen 모델**(`ConfigDict(frozen=True, extra="forbid")`,
`tos.canonical.FrozenModel` REUSE)로 저작한다. `extra="forbid"`는 **§14 line 362 "reject unsupported or
silently dropped dimensions"·§9 line 262 "cannot declare a missing scope immaterial"의 스키마 수준 실현**이다
(unknown/silent-drop 차단). 모든 magnitude·limit·headroom은 **주입 `CanonicalDecimal|None`**(하드코딩 수치 0).

### 2.0 소유권 골격 — are는 canonical의 하류, 4개 형제(protective/rcl/spg/orthostate)의 상류/상호

`tos.are`는 `tos.canonical`·`tos.ordering`(둘 다 core)만 import한다. dataflow상 are는 **protective·rcl·spg
step-7·orthostate의 상류**(magnitude/decision/step-bool 생산)이자 **spg envelope·capsule·recon의 하류**(snapshot
입력 주입 소비)다. magnitude/decision seam은 **produced-scalar/bool 주입(edge 0)**으로 실현되고, **유일 package
edge는 최종 `AdverseIncrement[s,d]` 타입 공유를 위한 are→rcl `CapacityVector` REUSE**다(§0.4c v1.1; rcl↛are
acyclic). "package edge 어느 방향이든 cycle"이라는 v1.0 주장은 철회한다(MINOR-1 — 단일 방향 edge는 cycle 아님).

### 2.1 digest-bound / plain-frozen / value / reference 분류 (총괄)

| 모델 | 분류 | 근거 |
|---|---|---|
| `AggregateRiskPolicy`(§5.1/§8) | **digest-bound `IndependentIdArtifact`** | §8 line 229 "canonical digest, signer, approval"·§22 line 508; id⊥digest(governance identity·같은-id/diff-bytes 탐지). spg Safety Config Bundle member. |
| `AggregateRiskStateSnapshot`(§5.3/§9) | **digest-bound `IndependentIdArtifact`** | §15 line 375 "snapshot identity/cut/generations/digest"·§9 line 258; consistency-cut identity ⊥ digest. **grants no permission**(§5.3 line 124). |
| `AdverseScenarioSet`(§5.4/§11) | **digest-bound `IndependentIdArtifact`** | §15 line 376 "scenario set identity/generation/digest"; immutable policy-bound. **min-coverage floor**(§11 line 128/301 — 화이트리스트 아님; §4.7). |
| `AggregateRiskDecision`(§5.5/§15) | **digest-bound `IndependentIdArtifact`** | §15 line 373 "canonical digest"; **decision_id ⊥ canonical_decision_digest**(rcl `GrantDecisionRef` `authority.py:53/55` 별개 필드 실측). forward-only(§16). |
| `ProjectedCell`(§12) | **plain-frozen value** | §12 line 326 per-(scope,dimension,scenario) 기록(current/proposed/overlap/projected/limit/headroom/increment/pass). magnitude=`CanonicalDecimal`. |
| 최종 `AdverseIncrement[s,d]`(§12) | **REUSE rcl `CapacityVector`** | `AdverseIncrement[s,d]=max_q(...)`(§12 line 317). ADR-002-002 §6 소유 타입 REUSE(§0.4c v1.1 MAJOR-1; are→rcl edge). 중간 per-(s,d,q)는 `ProjectedCell`(are-local). |
| `BenefitProof`(§13) | **plain-frozen value(주입)** | §13 line 336–342 7 전제 flag. 미증명⇒zero(§6.1). |
| `RiskDimensionDescriptor`(§10) | **plain-frozen value** | §10 line 281 unit/sign/scope/limit-source/valuation/uncertainty/correlation/scenario/freshness. per-product 열거는 Phase-0. |
| `AggregateRiskAuthorityEffect`(§7/ARE-INV-009) | **plain-frozen all-false** | rcl `RclAuthorityEffect`(`authority.py:19–36`) 동형; 어떤 True도 unconstructable(GRANT≠capacity, §1 line 17). |
| `RiskDecisionResult`/`RiskDimensionKind`/`RiskScopeKind`/`AdverseScenarioKind`/`BenefitKind` | **StrEnum(어휘)** | §2.2 verbatim. |

### 2.2 어휘 (verbatim 전사 — 에라타 defect class 주의)

**(1) `RiskDecisionResult`** — ADR §1 line 15·§5.5 line 132 verbatim "a result of `GRANT`, `DENY`, or
`UNKNOWN`". 3종: `GRANT`("authorizes only an exact RCL allocation request; it creates no capacity and permits
no send", §5.5 line 132)·`DENY`·`UNKNOWN`. **UNKNOWN은 permissive 아님** — "consumes conservative capacity and
blocks new risk"(ARE-INV-006 line 173).

**(2) `RiskDimensionKind`** — §10 line 270–279 verbatim 열거를 어휘 값으로(구조적 kind만; magnitude는 주입):
`GROSS_NOTIONAL`·`NET_NOTIONAL`·`LONG_SHORT_DELTA_DIRECTIONAL`·`CONCENTRATION`(instrument/underlying/issuer/
sector/theme/strategy/venue/account/legal-portfolio/currency/global)·`LEVERAGE_MARGIN_COLLATERAL`·`LIQUIDITY_
IMPACT_SLIPPAGE_GAP`·`BASIS_CORRELATION_HEDGE_MISMATCH`·`OPTION_GREEKS_EXERCISE_ASSIGNMENT`·`SETTLEMENT_CASH_
CURRENCY`·`LOSS_DRAWDOWN_SURVIVAL`·`BROKER_ACTION_RATE_PROTECTIVE_RESERVE`. **cross-dimension conversion은
explicit·Critical Input**(§10 line 281 "cannot silently default"). **주의(에라타 봉합)**: 이 kind 목록은 ADR
§10의 **구조적 축**이며 구체 per-product dimension 집합은 Phase-0(§28 q2)이다 — kind를 하드 수치 limit과 혼동
금지.

**(3) `RiskScopeKind`** — §8 line 230·§10 verbatim: `ENVIRONMENT`·`SAFETY_CELL`·`LEGAL_PORTFOLIO`·`ACCOUNT`·
`STRATEGY`·`VENUE`·`INSTRUMENT`·`UNDERLYING`·`ISSUER`·`SECTOR_THEME`·`CURRENCY`·`GLOBAL`. **no lower-dimensional
projection may pass if an applicable higher-dimensional or cross-scope limit is unknown**(§10 line 283).

**(4) `AdverseScenarioKind`** — §11 line 291–299 verbatim "SHALL cover at least": `FILL_PREFIX_ORDERING`(full/
partial/out-of-order)·`OVERLAP_RETRY`(original/cancel/amend/replace/split-child)·`MISSING_ACK_RECEIPT_AMBIGUITY`·
`ZERO_CROSS_REVERSAL_REDUCE_ONLY_FAIL`·`ADVERSE_PRICE_SLIPPAGE_GAP_VOL_LIQ`·`CORRELATION_BASIS_HEDGE_VENUE`·
`MARGIN_COLLATERAL_BORROW_FX_SETTLE_ASSIGN`·`EXTERNAL_TRAPPED_NONTRADE_CONCURRENT`·`UNAVAILABLE_EXIT_RATELIMIT_
PARTITION_RECOVERY`. **min-coverage floor**(§4.7): "Absence from the set is not proof that a credible adverse
path can be ignored"(§5.4 line 128)·"Sampling, Monte Carlo count, … historical absence … cannot prove that an
omitted credible tail is harmless"(§11 line 301).

**(5) `BenefitKind`** — §13 verbatim: `NETTING`·`HEDGE`·`DIVERSIFICATION`·`COLLATERAL`·`MARGIN_OFFSET`·
`LIQUIDITY`·`CORRELATION`. 각 benefit은 §13 line 336–342 7 전제 양성 시에만(§6.1).

**(6) 좌표 어휘(비붕괴, §4.4)**: are `RiskDimensionKind`(risk 축) ≠ rcl `DimensionDescriptor`(capacity 축,
`vector.py:39`) ≠ spg `EnvelopeVersion`(safety-config 축) ≠ brokercap `ProfileVersion`(broker 축). 토큰 겹칠 수
있으나 별개 타입.

### 2.3 아티팩트 covered + self-exclusion (설계 #4 §3.3 상속)

covered(digest preimage) = 각 아티팩트의 구조적 identity/scope/version/generation/class + (Decision) bound
policy/snapshot/scenario/effect/context **digest scalar** + per-cell 좌표. preimage 제외: `*_id`·`canonical_
digest`·`canonicalization_version`·`status`(ArtifactStatus)·`*_order`(ledger placement)·파생 역참조. **`_REQUIRED_
COVERED`는 structural identity/scope/version/class만**(numeric magnitude 제외 — Phase-1 null bound에서 ISSUED
도달 가능; missing magnitude는 consuming 술어에서 fail-closed, brokercap `records.py:333`·#12 §2.3 규율 상속).

> **핵심 설계 결정 — 4-아티팩트는 immutable generation별 append-only(#10/#12 상속)**: Policy/Snapshot/ScenarioSet/
> Decision은 시간에 따라 **재발행**된다(§5.2 Aggregate Risk Generation·§21 recovery→new generation). 하나의
> stable id에 mutable 내용을 담으면 정당한 revalidation이 same-id/diff-bytes `CRITICAL_CONFLICT`로 **오탐**된다.
> ⇒ **각 generation은 fresh id를 가진 immutable 레코드**다. same identity + diff canonical digest ⇒
> `CRITICAL_CONFLICT`(위조·재발행 위조·contradictory decision만); 정당한 개정 ⇒ **새 generation**. generation
> 순서는 `tos.ordering`(§3.2). **Decision은 특히 forward-only**(§16 line 413): 미래 Capacity Commitment identity를
> covered에 담지 않는다(non-cyclic).

---

## 3. canonical / ordering REUSE + 4-소비자 produced-scalar seam + 형제 경계

### 3.1 canonical REUSE + `id=f(digest)` 미채택

4-아티팩트는 `tos.canonical.IndependentIdArtifact`·`DigestBoundArtifact`를 REUSE한다. canonicalizer는
`tos.canonical` registry + `EVL1ProvisionalCanonicalizer`(`ev-l1-provisional-0`) REUSE, **신규 canonicalizer
없음**(프로덕션 canonical semantic form은 Phase-0 §9.2 — ADR §28 q1·q7). magnitude·limit·headroom은 **이미
core인 `CanonicalDecimal`** REUSE(§14 line 358 "exact decimal/rational"·NaN/infinity 구성-거부). **`id=f(digest)`
미채택**(§0.4d 근거·rcl `GrantDecisionRef` 별개 필드 실측). **PROMOTE = 0건**.

### 3.2 ordering REUSE (Aggregate Risk Generation / decision / snapshot append-only 순서)

Aggregate Risk Generation(§5.2 line 120 "A monotonic generation")·decision·snapshot의 append-only 순서는 신규
저작하지 않고 `tos.ordering`(`Ordering`·`OrderingEvent`·`compare_order`, `tos.canonical`만 의존)를 REUSE한다.
**wall clock은 순서를 만들지 않는다**(§17 line 440 "TTL, cache age alone, heartbeat … is not currentness proof"·
§18 line 454 "No cache lifetime … is a fencing mechanism"와 정확히 정합) — are는 clock을 읽지 않는다(§3.5;
time validity는 주입 flag). `concurrent_not_reservation`(§6.3)은 순서 관측이 예약이 아님의 순수 술어이며 순서
자체는 `compare_order`가 담당. light REUSE(core 의존, 신규 edge 아님).

### 3.3 REUSE 요약 표

| substrate | 결정 | 근거 |
|---|---|---|
| `FrozenModel`·`DigestBoundArtifact`·`IndependentIdArtifact`·`ArtifactStatus` | **REUSE(core `tos.canonical`)** | §3.1; 신규 없음 |
| `classify_record_pair`·`RecordPairKind` | **REUSE(core)** | §3.1; same-id/diff-bytes·contradictory decision |
| `CanonicalDecimal` | **REUSE(core, #9 PROMOTE됨)** | §3.1/§4.3; magnitude·limit·NaN 구성-거부·PROMOTE 불필요 |
| `Ordering`·`OrderingEvent`·`compare_order` | **REUSE(core `tos.ordering`)** | §3.2; generation/decision/snapshot 순서 |
| 4-아티팩트·`ProjectedCell`·`BenefitProof`·11 결정 술어·어휘 | **로컬 저작** | §0.4a/§2; ADR §5–§21 verbatim·decision-side |
| rcl `CapacityVector`(`vector.py:74`) | **REUSE(are→rcl 1 edge; 최종 `AdverseIncrement[s,d]`)** | §0.4c v1.1 MAJOR-1; ADR-002-002 소유 타입·rcl↛are acyclic·#8 선례 |
| protective magnitude·rcl decision scalar·spg step-7 bool·all-false authority | **미소유 — produced-scalar/bool로만 공급** | §3.4; 4-소비자 seam |
| capacity 산술·envelope 거버넌스·protective classify·snapshot 조립·final egress·numeric bound | **미소유 — rcl/spg/protective/런타임/INSTANCE 이연** | §3.5 |
| PROMOTE | **0건** | §3.1 |
| sibling edge | **1건(are→rcl, `CapacityVector`)** | §3.4; #8 orthostate→rcl 선례 동형 |

### 3.4 protective / rcl / spg / orthostate 경계 — produced-scalar seam(edge 0) + are→rcl `CapacityVector` 1 edge (중심, 코드 실측)

**(a) are = produced-scalar/bool producer(§0.4b).** are는 4개 소비자를 **import하지 않고**, 그들이 소비할
**plain scalar/bool**을 생산한다. seam 계약(compose) — **소비자는 전부 이미 비준·구현됨**. 핵심 seam:

- **protective(#11 OQ3 구멍 충전)**: are가 `final_conservative_risk`/`current_conservative_risk`/`no_action_
  risk`(§12 projection 결과)·`worst_intermediate_risk`(§12 adverse intermediate)·`already_exceeded_regime`·
  `credible_space_bounded`·`no_credible_intermediate_increases_exceedance`를 생산 ⇒ protective `AggregateRisk
  Comparison`(`records.py:149–152`)·`IntermediateStateWitness`(`records.py:166–168`) 채움. protective
  `protective_classification`(`predicates.py:246`)이 **비교**해 `ProtectiveActionOutcome`(PROTECTIVE_PROVEN/
  RISK_INCREASING_DENIED/UNKNOWN_CONSERVATIVE) 산출. **any None magnitude ⇒ RISK_INCREASING_DENIED**(`predicates.
  py:289` 실측). cancellation-arbiter: are가 `continued_existence_worsens_aggregate`/`cancellation_worsens_
  aggregate`(`predicates.py:529/531`) 생산.
- **rcl(§16 non-cyclic binding)**: are가 `decision_id`/`decision_generation`/`canonical_decision_digest`(decision
  content ref)·all-false authority block 생산 ⇒ rcl `GrantDecisionRef`(`authority.py:53–55/59`) 채움. rcl
  `grant_authorizes_exact_request`(`predicates.py:575`)이 `bound_reservation_revision`/`bound_reservation_digest`/
  `bound_generation`(post-commit 충전)과 대조해 exact binding 검증. **are는 reservation 좌표를 생산하지 않음**
  (forward-only, §16 line 413 "The Aggregate Risk Decision does not bind a future Capacity Commitment identity")
  — **이것이 non-cyclic의 코드 실현**. grant identity·scope: `aggregate_risk_authority_grant_identity`(`rcl/
  records.py:99`)·`applicable_risk_scopes`(`rcl/records.py:98`).
- **spg(§8 상호·cycle 회피)**: are가 `aggregate_effect_within`(config 변경의 aggregate risk effect가 bound 내)
  생산 ⇒ spg `SemanticValidationInputs.aggregate_effect_within`(`records.py:205`) 채움. spg `semantic_validation`
  step 7(`predicates.py:466` `is not True⇒reject`). **동시에** are는 spg envelope 상한을 주입 소비(§8) —
  **둘 다 미import**가 acyclic 유지(§0.4b (ii)).
- **orthostate(state 의존, 전용 슬롯 아님·정직)**: orthostate `AUTHORIZED_FOR_CAPACITY`(`vocabulary.py:43–45`
  "Approval + Aggregate-Risk granted")는 are grant를 **state 전이 의미로** 전제하나(`predicates.py:367` APPROVED→
  AUTHORIZED_FOR_CAPACITY), orthostate records에 **전용 are-bool 필드는 부재**(실측). ⇒ 이 seam은 **문서화된
  state-의존**이지 전용 produced-value 슬롯이 아니다(정직 이연 — under-realization 봉합 #7/#11: 전용 슬롯이
  실재하는 protective/rcl/spg만 정의 술어를 부여하고, orthostate는 미래 런타임 배선으로 이연).

- **타입 정합 + fail-closed 정합**: are 산출은 전부 `CanonicalDecimal`/`bool`/`str`/`int`(bool은 양성 증명에서만
  True; magnitude는 양성 증명에서만 finite). 소비 signature는 전부 `…|None`(`None`⇒fail-closed)이라 are `None`/
  non-finite와 caller-supplied `None`이 둘 다 안전. **polarity 봉합(#6 fail-open REJECT 교훈)**: producer는 결코
  "미판정 ⇒ 작은 magnitude/True"로 새지 않는다(§4.1/§4.3).
- **composition(런타임 배선) = caller 소관**: are 산출을 소비자 주입 슬롯으로 배선하는 **런타임**은 **미래
  Aggregate Risk Authority / Snapshot Assembly / RCL-admission 런타임**(EV-L3)이 한다. Phase 1은 #11/#12의 seam
  이연과 **동형으로 런타임 배선을 이연**한다.
- **seam cross-check = MANDATED(test-only)**: Phase 1은 **test-only** 모듈(`tos/tests/are/test_seam_protective.py`·
  `test_seam_rcl.py`·`test_seam_spg.py`)에서 are·(각 소비자)를 **둘 다 import**해 are 산출의 **의미·polarity·
  fail-closed 거동**이 소비 signature 기대와 **일치함을 assert**한다(예: are `final_conservative_risk=None` ⇒
  protective `RISK_INCREASING_DENIED`; are decision digest 불일치 ⇒ rcl `grant_authorizes_exact_request=False`
  `predicates.py:599–614`; are `aggregate_effect_within=False` ⇒ spg reject `predicates.py:466`). **이 테스트는
  package edge가 아니다** — 테스트 import는 §7.1 `import tos.are` package-closure에 **계상되지 않으므로** magnitude/
  decision seam의 edge-0은 유지된다(#11/#12 동형). **dominance는 이제 타입 수준(v1.1 MAJOR-1)**: 최종
  `AdverseIncrement[s,d]`가 rcl `CapacityVector`를 REUSE하므로 rcl commit 타입과 동일 — 별도 축약 reducer·under-
  count 봉인이 불요(v1.0의 "미명세 reducer under-count 0 봉인" 주장 제거). seam test는 `CapacityVector` 좌표
  일치(are 생산 = rcl 소비 타입)만 회귀.
- **acyclic(v1.1 정확형)**: are→rcl 단일 edge(rcl↛are 실측)이며 are↛{protective,spg,orthostate,capsule,recon,…}
  ∧ 그들↛are. spg↔are 양방향 value-flow는 양쪽 미import(주입)로 acyclic; are→rcl은 단일 방향 edge로 acyclic
  (#8 orthostate→rcl 선례). "양쪽 미import가 유일 근거"는 spg seam에만 적용(rcl은 edge 허용).

**(b) are는 mutate/transmit/issue/activate하지 않는다(§1 line 17·§16 런타임·ARE-INV-014).** are는 결정 scalar/
bool만 생산하고 capacity mutation·egress transmit·capability issue·snapshot commit·live-scope set 메서드가
**부재**하다(§4.5). 소비 authority(rcl serialize·protective classify·final egress·Aggregate Risk Authority
런타임)가 실제 action을 gate한다.

**(c) 운영자 판단 지점**: magnitude/decision seam을 **plain-scalar 주입(edge 0)**으로 둘지 대안 B(소비자 측
edge; **cycle 아님** — v1.1 MINOR-1)로 갈지 — 주입 권장(§0.4b). 최종 `AdverseIncrement[s,d]`의 rcl `CapacityVector`
REUSE(are→rcl 1 edge) — **REUSE 채택**(§0.4c v1.1 MAJOR-1; 타입 수준 dominance·rcl↛are acyclic·#8 선례).

### 3.5 소유권 분할표 — are가 소유 / 형제에서 소비·생산 (본 문서 최대 함정 지대, #11/#12 §3.5 상속)

> **소유권 분할 명시(#8·#11·#12 교훈 — cross-section 혼동 선제 봉합)**: ADR-002-021은 **effect envelope와 RCL
> grant 사이의 평가 프로토콜**만 결정하며(§4 line 49) capacity serialization(rcl)·envelope governance(spg)·
> protective classification(protective)·snapshot assembly(런타임)·final egress(ADR-002-013)를 **소유하지 않는다**.
> 함정: are가 rcl의 `transition_allowed`·protective의 `protective_classification`·spg의 `profile_within_envelope`·
> capsule의 snapshot validity를 재저작하면 권위 중복(#8 lesson). 아래 표가 경계를 코드 실측으로 고정한다.

| ADR 조항/개념 | are 소유 (Phase 1) | 형제 소유 (재저작 금지) | seam 방향(실측) |
|---|---|---|---|
| §12 adverse increment | `adverse_increment`·`ProjectedCell`(중간 per-s,d,q)·최종 `AdverseIncrement[s,d]`=rcl `CapacityVector` REUSE(§5.3/§0.4c v1.1) | rcl commit/serialize/benefit 산술·`committed_usage`(`vector.py:74`·`predicates.py:177`) | are가 `CapacityVector` 생산 → rcl `proposed_adverse_increment`(`records.py:185`) 직접(타입 동일·축약 불요) |
| §16 RCL binding | decision content ref·all-false authority(§5.6) | rcl `grant_authorizes_exact_request`·`transition_allowed`·serialize(`predicates.py:575/438`) | are `decision_id/generation/digest` 생산 → rcl `GrantDecisionRef` 소비(`authority.py:53–55`); reservation 좌표는 rcl(non-cyclic) |
| §19 protective magnitude | conservative `final/current/no_action/worst` risk·flags 생산(§5.3) | protective `protective_classification`·`ProtectiveActionOutcome`(`predicates.py:246`) | are magnitude 생산 → protective `AggregateRiskComparison`/`IntermediateStateWitness` 소비(`records.py:149–168`) — **#11 OQ3 충전** |
| §8 envelope dominance | envelope 상한을 **주입 소비**(§5.5); `aggregate_effect_within` 생산 | spg `HardSafetyEnvelope`·`profile_within_envelope`·`restrictive_override_admissible`(spg 소유) | spg envelope → are 주입 소비(§8); are step-7 bool → spg 소비(`records.py:205`) — **상호·acyclic** |
| §9 snapshot 입력 | conservative current usage를 **주입 소비**·snapshot 모델 소유 | capsule Decision Context validity(`predicates.py:84`)·recon `ConservativeBound`(`records.py:29`)·snapshot **조립** 런타임 | capsule/recon → are 주입 소비; snapshot 조립은 런타임(§28 q3) |
| §14 numerical safety | `numerical_safety`·`CanonicalDecimal` finite 검사(§5.5) | (broker margin/buying-power는 주입 ceiling — §14 line 354) | are 순수 검사; broker 수치 주입 |
| §17 currentness | `currentness_invalidation` 술어(§6.4) | authority invalidation·time validity·final-egress active currentness 런타임 | are 순수 술어; enforcement 런타임(profile bound) |
| §18 stale-evaluator | `concurrent_not_reservation` 술어(§6.3) | rcl serialization·generation fence enforce(런타임) | are 순수 술어 + ordering REUSE |
| §21 non-revival | `non_revival_holds`·`economic_effect_persists`(§6.6) | ADR-002-017 Recovery Barrier·re-arm workflow(런타임) | are 술어; barrier enforce 런타임 |
| §7 authority separation | `AggregateRiskAuthorityEffect` all-false(§6.7) | rcl `RclAuthorityEffect`·final egress confinement(ADR-002-013) | are all-false 생산; egress confinement 런타임 |
| orthostate `AUTHORIZED_FOR_CAPACITY` | (grant 생산 — state 의미) | orthostate KnowledgeState 전이(`predicates.py:367`) | 전용 슬롯 부재 — 문서화된 state 의존(§3.4 (d)) |

---

## 4. 불변식

모두 frozen 모델 구성-불변식(구성 실패) 또는 순수 술어(property)로 실현한다. **앵커는 ARE-INV-001..014(§6)·
ARE-AC-001..012(§26)·§-clause·SAFE-###**이며 **새 시리즈를 창작하지 않는다**(§0.4f). **fail-closed discipline**:
미증명/초과/None/stale/expired에 대한 술어는 절대 vacuous permissive/작은 vector가 되지 않으며, live 허용은
*양성 증명*을 요구하고, 각 가드에 **both-ways canary**(가드가 실제로 발화함)를 붙인다.

### 4.1 conservative projection / adverse-increment 중앙 불변식 (중앙 — ADR §12 line 311–328; ARE-INV-003; §11)

**중앙 결정**: "Every credible execution path and adverse intermediate state is included; favorable final intent
never erases temporary or uncertain risk." ARE-INV-003 line 162 verbatim. §12 line 311–321 verbatim:
`ProjectedUsage[s,d,q] = ConservativeCurrentUsage + MaximumCredibleCommandEffect + RequiredConcurrentAndOverlap
Effect`; `AdverseIncrement[s,d] = max_q(ProjectedUsage - ConservativeCurrentUsageAlreadyCommitted)`. 실현(구조적):

1. **`adverse_increment`에 permissive 기본값 부재**: 오직 **모든 credible scenario q에 대해 projection cell이
   완비**되고 각 magnitude가 finite일 때만 결과 magnitude 산출. 하나라도 None/비완비 ⇒ 결과 `UNKNOWN`(§4.3).
   "assume-zero" 경로 부재(#6 fail-open REJECT 교훈).
2. **favorable intent가 increment을 음수로 못 만듦**: "An intended reduction cannot make the requested increment
   negative merely because the final target is smaller. Temporary overlap, reversal, protection loss, margin,
   liquidity, rate, and basis effects remain positive where credible"(§12 line 328). ⇒ `requested_increment =
   max(0, ...)` 아니라 **credible temporary effect를 항상 양성으로 보존**.
3. **component-wise subtraction 제약(§12 line 324)**: "permitted only when it cannot hide a joint, concentration,
   margin, convexity, liquidity, correlation, or scenario constraint." ⇒ joint constraint 존재 시 per-component
   축약 금지(cross-scope limit 보존).

**canary(both-ways)**: (a) 한 scenario q의 cell 누락/None magnitude ⇒ 결과 `UNKNOWN`(가드 발화); favorable
final < current이나 worst-intermediate > current ⇒ increment 양성 보존(§12 line 328 — 가드 발화); (b) 모든 q
완비·finite ∧ dominance 성립 ⇒ 결과 magnitude 산출(양성 side — 정당한 projection을 막지 않음).

### 4.2 no-unproven-benefit 중앙 불변식 (ADR §13 line 332–346; ARE-INV-005; ARE-EV-005)

- **미증명 ⇒ zero, permissive 기본 부재**: `benefit_admissible(proof: BenefitProof) -> bool`는 §13 line 336–342
  **7 전제 전부 양성**(exact identity/eligibility·current enforceable state+FQP·simultaneous availability·approved
  basis/correlation/liquidity/stress·margin recognition·**no undeclared common-mode**·complete adverse leg-
  failure scenario)일 때만 `True`. **하나라도 unknown ⇒ `False`(benefit removed/conservatively bounded)**(§13
  line 344; ARE-INV-005 line 170).
- **불충분 증거 명시 거부(§13 line 344)**: "A broker margin number, historical correlation, shared model output,
  recent co-movement, strategy label, or human assertion is not sufficient proof." ⇒ 이들 flag는 증명으로 계상
  불가.
- **hedge가 trapped exposure 못 지움(§13 line 346)**: "Hedge recognition SHALL never erase trapped exposure or
  capacity for a potentially live order whose terminal quantity is unproven. A future planned hedge or exit
  creates no present headroom."
- **canary(both-ways)**: (a) 7 전제 중 하나라도 None/False, 또는 broker-margin-only 근거 ⇒ `False`(benefit=zero,
  가드 발화; §26 ARE-AC-005); (b) 7 전제 전부 양성 증명 ⇒ `True`(양성 side). **∅ 봉합**: 빈 BenefitProof(전제
  미제시) ⇒ `False`(vacuous benefit 아님, §4.7).

### 4.3 numerical safety 중앙 불변식 (ADR §14 line 356–366; ARE-INV-008; ARE-EV-006/007)

- **None/non-finite ⇒ UNKNOWN/DENY, 작은 vector 금지**: `numerical_safety(...)`는 magnitude가 `CanonicalDecimal`
  finite(`is_finite`, NaN/infinity/negative-zero-ambiguity 아님)·unit 정합·overflow/underflow/precision-loss/
  non-convergence 부재일 때만 통과. **하나라도 위반 ⇒ `UNKNOWN`/`DENY`, never a smaller vector**(§1 line 29·§14
  line 359). `CanonicalDecimal` REUSE(구성 시 NaN/infinity 거부 — **#12 NaN 구성-거부 선례 동형**).
- **fallback 금지(§14 line 365)**: verbatim "'Return zero,' 'use last value,' 'skip failed scenario,' 'accept
  optimizer incumbent,' or 'trust broker validation' is prohibited unless an approved proof establishes it as
  the conservative upper bound for the exact scope." ⇒ 어떤 fallback도 conservative upper bound 증명 없이는
  거부.
- **deterministic ordering·canonical representation(§14 line 360)**: 비결정 순서·parser/library/model
  disagreement ⇒ UNKNOWN(§1 line 29). L1은 canonical representation·finite 검사; parser/library differential은
  EV-L2(§6.2, ARE-EV-007).
- **canary(both-ways)**: (a) NaN/infinity limit·unit mismatch·overflow ⇒ `UNKNOWN`/`DENY`(가드 발화; §26 ARE-AC-
  007 "No smaller permissive vector may result"); (b) 전 magnitude finite·unit 정합 ⇒ 통과(양성 side). **`1.0`
  vs `1.00`은 같은 canonical**(정상, scale-normalize).

### 4.4 좌표 비붕괴 (aggregate-risk ≠ capacity ≠ envelope ≠ broker ≠ time)

- **별개 축**: are `RiskDimensionKind`/`RiskScopeKind`(aggregate-risk 축) / rcl `DimensionDescriptor`·
  `CapacityVector`(capacity 축, `vector.py:39/74`) / spg `HardSafetyEnvelope` limit(safety-config 축) /
  brokercap `BrokerCapabilityProfile`(broker 축) / time snapshot(time 축). 토큰 겹칠 수 있으나(예: "dimension",
  "scope") **별개 타입**이다.
- **비붕괴 성립 방식**: (i) **타입 구분**(별개 FrozenModel/StrEnum) + (ii) **미import**(are는 rcl/spg/brokercap/
  time을 import하지 않아 swap 원천 차단). canary: `are.RiskDimensionKind is not rcl.DimensionDescriptor`(둘 다
  import하는 test-only 모듈에서 타입 identity 회귀).
- **최종 `AdverseIncrement[s,d]`는 rcl `CapacityVector` REUSE·중간 `ProjectedCell`은 are-local (v1.1 MAJOR-1)**:
  최종 per-(scope,dimension) increment은 rcl이 commit하는 그 타입(`CapacityVector`)과 **동일해야 dominance가
  성립**하므로 두 타입을 두면 오히려 좌표 붕괴 위험이다 — ⇒ 최종 vector는 `CapacityVector`를 REUSE(단일 타입,
  divergence-safe). 반면 **중간 per-(scope,dimension,scenario) 표현은 are-local `ProjectedCell`**(scenario 축
  보유·rcl `CapacityVector`보다 richer)이며 rcl `CapacityVector`와 별개다. commit/serialize/benefit 산술은 여전히
  rcl 소유(§3.5) — are는 REUSE한 타입으로 최종 increment을 담을 뿐 capacity를 mutate하지 않는다(§4.5).

### 4.5 representation ≠ enforcement (ADR §1 line 17; §16; ARE-INV-014 line 205)

`AggregateRiskDecision`·`GRANT`·projection cell·admissibility bool은 **비전송·비-enforcing representation**이다 —
"GRANT" 기록이 order를 전송하거나 capacity를 commit하거나 Live Authorization을 발급하지 않는다. ARE-INV-014 line
205 verbatim: "Logs, monitoring, audit, replay, broker acceptance, and post-trade reconciliation do not replace
pre-trade projection and exclusive commitment." §1 line 17 "A `GRANT` is not capacity, Live Authorization, a
Transmission Capability, or broker permission." ⇒ are에 **egress transmit·capacity mutate·capability issue·
snapshot commit·live-scope set 메서드가 부재**(구성적 부재). `AggregateRiskAuthorityEffect` all-false가 이를
타입 수준으로 봉인(§6.7).

### 4.6 non-cyclic binding + non-revival 불변식 (ADR §16/§21; ARE-INV-002/009/013)

- **non-cyclic(ARE-INV-002·§16 line 413)**: `risk_decision`은 미래 Capacity Commitment identity를 covered/binding에
  담지 않는다. decision은 forward-only content ref만 생산; rcl이 binding·reservation 좌표를 post-commit 채운다.
  두 decision union/reuse/patch 금지(§15 line 387 "Two decisions cannot be unioned … reused … or patched with a
  fresher field"). **canary**: decision A·B union 시도 ⇒ 구성 불가/거부(가드 발화); 정당한 단일 decision ⇒ 통과.
- **non-revival(ARE-INV-013·§21 line 488–500)**: `non_revival_holds(...)`는 **무조건 True** — restart/restore/
  failover/recovery/reconciliation/replay/improved-inputs가 prior decision/grant/authority/live scope를 revive
  **하지 않음**을 명문화(spg `expiry_revives_nothing`·liveauth `authorization_revived_by_nothing`·rcl `recovery_
  generation_revives_nothing` 동형). "No automatic re-arm is permitted"(§1 line 41·§21 line 500). **canary**:
  recovery 후 old decision 참조로 grant 시도 ⇒ 거부(fresh artifact + governed re-arm 요구, 가드 발화); fresh
  decision ⇒ 통과.
- **all-false authority(ARE-INV-009·§1 line 17)**: `AggregateRiskAuthorityEffect`의 어떤 True도 unconstructable
  (rcl `RclAuthorityEffect` `authority.py:25` 동형). **canary**: `creates_capacity=True` 구성 시도 ⇒ ValidationError.

### 4.7 ∅-공허 fail-closed (양방향 명시 — #10/#12 code-review MAJOR 교훈)

빈 입력의 **모든 방향**을 명문화한다(#12 교훈: 표의 방향이 하나뿐이면 불변식의 전 금지 동사와 대조해 커버리지
명시). ARE 금지 동사(§1·ARE-INV): **exclude**(§1 line 19)·**shrink**(§1 line 23·29)·**patch/widen/narrow/union/
substitute**(ARE-INV-002 line 158)·**enlarge**(ARE-INV-007 line 178)·**revive**(ARE-INV-013)·**release**(ARE-
INV-011)·**create**(ARE-INV-012).

| 빈 입력 | 금지 방향(vacuous permissive 차단) | 허용 방향(양성 side) | 근거 |
|---|---|---|---|
| **빈 AdverseScenarioSet** | 빈 set ⇒ "no adverse path" 아님 ⇒ max credible effect 확립 불가 ⇒ `UNKNOWN`/`DENY`(dominance 증명 불가) | 완비 approved set + 각 scenario cell finite ⇒ dominance 증명 가능 | §5.4 line 128·§11 line 301 (min-coverage floor) |
| **빈 dimension set** | 빈 governed dimension ⇒ "no risk" 아님 ⇒ Hard Envelope 증명 불가 ⇒ `UNKNOWN`/`DENY` | Hard Envelope·profile·instrument가 요하는 전 dimension 완비 ⇒ 평가 가능 | §10 line 268·§8 line 241 (spg 빈-envelope=allow-nothing 동형) |
| **빈 scope set** | 평가 scope 부재 ⇒ ARE-INV-001 aggregate 완전성 증명 불가 ⇒ fail-closed | 적용 가능한 전 scope(전략/계정/instrument/venue/…) 포함 ⇒ 평가 가능 | §9 line 262·ARE-INV-001 line 152 |
| **빈 BenefitProof** | 전제 미제시 ⇒ benefit=zero(§4.2) | 7 전제 전부 양성 ⇒ benefit 인정 | §13 line 344 |
| **None magnitude/limit** | None ⇒ `UNKNOWN`/`DENY`(§4.3)·(protective seam) `RISK_INCREASING_DENIED`(`predicates.py:289–290`) | finite magnitude + finite limit ⇒ 비교 가능 | §14; ARE-INV-006 line 173 |

**양방향 규율**: 각 빈-입력 가드는 (a) 금지 방향(가드 발화 canary)과 (b) 허용 방향(정당 통과 canary)을 **둘 다**
property로 검증한다(§7). vacuous-grant도 vacuous-block(정당 평가를 막음)도 결함이다 — 전자는 안전 위반, 후자는
가용성 위반(#12 both-ways 교훈).

**동사별 전용 canary 커버리지(v1.1 MINOR-2 — enlarge 봉합)**: 위 표의 금지 동사 중 **exclude**(§5.1 scope 누락)·
**shrink**(§5.3 favorable-intent 음수화)·**patch/union/substitute**(§5.2/§4.6 decision binding)·**revive**
(§6.6 non-revival)·**release**(§6.6 economic continuity)·**create**(§6.7 all-false)는 각 절에 전용 named
canary가 있다. v1.0에서 **enlarge**(ARE-INV-007)만 §8 주입 소비로 암묵 처리됐던 것을 정정해 **`envelope_bound_
not_enlarged` 전용 both-ways canary를 §5.6에 신설**했다(effective_limit > 주입 envelope max 또는 broker/model/
runtime 출처 ⇒ DENY; ≤ ∧ envelope 출처 ⇒ 통과) — 전 금지 동사가 전용 canary를 갖는다.

---

## 5. core 술어 — scope 완전성·exact binding·projection·dimension·valuation·decision·evidence (ARE-EV-001/002/003/004/006 substrate)

**핵심 난제**: aggregate projection의 보수성·단조성·비순환·numerical safety를 **순수 함수**로 저작하되, (i)
scenario 값·상관계수·valuation·margin을 **주입 판정/파라미터**로 두어 하드코딩 수치·수치 엔진을 배제하고(§8),
(ii) **fail-closed(§4)를 구조로** 지키며(permissive 기본·vacuous 부재), (iii) missing dimension·unproven benefit·
None magnitude·favorable intent를 **most-restrictive**로 처리한다.

### 5.1 snapshot scope 완전성 (§9; ARE-EV-001 substrate, core L1 슬라이스)

`snapshot_scope_complete(snapshot: AggregateRiskStateSnapshot|None, required_scopes: frozenset[RiskScopeKind],
inputs) -> bool`:

- `True` **only** when snapshot 존재 ∧ 모든 applicable strategy/account/instrument/venue/position/order/
  commitment/external-effect/EOR/settlement/cash/collateral/concurrent-action이 포함(§9 line 249–256·ARE-INV-001
  line 152) ∧ 각 field가 source/continuity/observation-time/unit/mapping/confidence/lineage 보유(§9 line 258).
- **omission ⇒ 거부**: "A proposer, evaluator shard, model, cache, or read replica cannot declare a missing scope
  immaterial"(§9 line 262). unknown applicability ⇒ 보수적 포함.
- **double-netting 방지(§9 line 260)**: 두 record가 같은 effect인지 증명 불가 ⇒ maximum credible aggregate 보존/
  new risk 차단; fill이 order usage를 position usage로 transfer함을 증명 ⇒ atomic ADR-002-002 전이(rcl, 영구
  double-count 아님).
- **canary(ARE-AC-001, both-ways)**: (a) 한 strategy/account/order/external-activity 누락 ⇒ `False`(§26 ARE-AC-001
  "must deny or conservatively include", 가드 발화); 빈 scope ⇒ `False`(§4.7); (b) 전 required scope + lineage
  완비 ⇒ `True`.

### 5.2 exact effect + snapshot binding (§16/§9; ARE-EV-002 substrate, core L1 슬라이스)

`exact_effect_snapshot_binding(decision_inputs) -> bool` ∧ decision content ref 생산:

- **one exact effect(ARE-INV-002 line 158)**: decision은 one exact current Economic Effect Envelope를 binding하고
  "cannot be patched, widened, narrowed, unioned, or substituted." snapshot/scenario/effect digest가 전부 정합
  (canonical digest 재계산 일치)일 때만 `True`.
- **substitute/replay 거부(§26 ARE-AC-002)**: snapshot/scenario/command/effect를 substitute/patch/union/partial-
  refresh/replay ⇒ `False`("No mixed decision may pass"). digest 불일치 ⇒ `False`(fail-closed).
- **decision content ref 생산(rcl seam)**: `decision_id`·`decision_generation`·`canonical_decision_digest`(§3.4)
  — rcl `GrantDecisionRef` 상류. **forward-only**: reservation 좌표 미포함(§16 line 413·§4.6).
- **canary(ARE-AC-002, both-ways)**: (a) effect envelope patch·snapshot replay·digest 불일치 ⇒ `False`(가드
  발화); (b) 단일 정합 digest 세트 ⇒ `True`.

### 5.3 conservative projection + adverse increment (+ protective magnitude 생산) (§11/§12; ARE-EV-003 substrate, core L1 슬라이스)

`adverse_increment(cells: tuple[ProjectedCell,...], scenario_set: AdverseScenarioSet|None) ->
AdverseIncrementResult`:

- **projection(§12 line 311–321)**: 각 (s,d,q)에 대해 `ProjectedUsage = ConservativeCurrentUsage + MaxCredible
  CommandEffect + RequiredConcurrentOverlapEffect`; `AdverseIncrement[s,d] = max_q(ProjectedUsage - Conservative
  CurrentUsageAlreadyCommitted)`. 각 magnitude는 주입 `CanonicalDecimal`(are는 산술 조합만, 수치 엔진 아님).
- **fail-closed(§4.1/§4.3)**: 한 scenario q cell 누락/None ⇒ 결과 `UNKNOWN`; favorable intent가 credible
  temporary effect(overlap/reversal/protection-loss)를 음수화 못 함(§12 line 328); joint constraint 존재 시
  component-wise 축약 금지(§12 line 324).
- **decision record(§12 line 326)**: current/proposed/overlap/projected/limit/headroom/requested-increment/pass를
  per-(scope,dimension,scenario)로 기록(`ProjectedCell`).
- **produces protective magnitude(#11 OQ3 seam, §3.4)**: projection 결과에서 `final_conservative_risk`(proposed
  action 후 최종)·`current_conservative_risk`·`no_action_risk`·`worst_intermediate_risk`(worst credible partial-
  fill/ordering/leg-failure/late-fill/basis/liquidity/margin intermediate, §6.2)·`already_exceeded_regime`·
  `credible_space_bounded`·`no_credible_intermediate_increases_exceedance`를 산출 ⇒ protective `AggregateRisk
  Comparison`/`IntermediateStateWitness` 채움. **None ⇒ 소비 측 `RISK_INCREASING_DENIED`**(fail-closed 정합,
  `protective/predicates.py:289–290`). credible-space unbounded ⇒ `credible_space_bounded=None/False`(§19 line 470
  "trapped exposure/containment, not permission").
- **canary(ARE-AC-003, both-ways)**: (a) 한 fill-prefix/overlap/reversal/missing-ACK ordering이 projected를 초과
  하나 favorable final이 이를 지움 ⇒ 결과가 여전히 worst 반영(가드 발화; §26 ARE-AC-003 "must dominate every
  credible path"); 빈 scenario set ⇒ `UNKNOWN`(§4.7); (b) 전 credible path 완비·finite·dominance 성립 ⇒ magnitude
  산출.

### 5.4 dimension / unit / scope / limit integrity (§10; ARE-EV-004 substrate, core L1 슬라이스)

`dimension_vector_integrity(descriptors, projected_cells, inputs) -> bool`:

- **explicit vector semantics(ARE-INV-004 line 166)**: 각 governed dimension이 exact unit/sign/scope/limit/
  valuation/aggregation/uncertainty/scenario semantics 보유(`RiskDimensionDescriptor`). scalar notional/model
  score/VaR point/broker margin/local pass flag가 vector 대체 불가(§1 line 21).
- **cross-dimension conversion explicit(§10 line 281)**: currency conversion·contract multiplier·price scale·
  option model·duration·beta/correlation·liquidity transformation은 Critical Input이며 silent default 불가 ⇒
  변환 계수 None ⇒ `False`(fail-closed).
- **no lower-projection pass(§10 line 283)**: applicable higher-dimensional/cross-scope limit이 unknown이면 lower
  projection 통과 불가 — "Local compliance never overrides unsafe aggregate state."
- **canary(ARE-AC-004, both-ways)**: (a) missing dimension·wrong unit/sign/scale·scope omission·limit substitution·
  scalar-collapse ⇒ `False`(§26 ARE-AC-004 "Every ambiguity must fail closed", 가드 발화); 빈 dimension set ⇒
  `False`(§4.7); (b) 전 dimension이 unit/sign/scope/limit 완비·변환 계수 present ⇒ `True`.

### 5.5 valuation + numerical safety (§14; ARE-EV-006 substrate, core L1 슬라이스)

`valuation_conservative(inputs) -> bool` ∧ `numerical_safety(magnitudes, units) -> RiskDecisionResult|bool`:

- **conservative valuation(§14 line 352)**: observation/executable/stress/liquidation/settlement/conversion
  price·stale/unknown을 구분; "A zero, negative, future, crossed, stale, or missing value is not automatically
  conservative." ⇒ 미구분 price ⇒ `False`.
- **broker margin은 ceiling·주입(§14 line 354)**: "Broker margin, buying power, and collateral figures are
  Critical Inputs and ceilings/observations, not proof that the local aggregate model may omit exposure. More
  restrictive local or broker constraints dominate. A favorable broker result cannot enlarge the Hard Safety
  Envelope." ⇒ broker 수치는 주입 upper-observation이며 local aggregate 생략 근거 불가.
- **numerical safety(§4.3)**: NaN/infinity/overflow/underflow/precision/non-convergence/unit-mismatch ⇒ `UNKNOWN`/
  `DENY`. `CanonicalDecimal` `is_finite` REUSE. fallback 금지(§14 line 365).
- **canary(ARE-AC-006/007, both-ways)**: (a) stale/zero/negative/future price·FX move·margin change·liquidity
  gap·option convexity·assignment·NaN/overflow ⇒ `False`/`UNKNOWN`(§26 ARE-AC-006 "Worst credible effect must
  remain bounded"·ARE-AC-007 "No smaller permissive vector", 가드 발화); (b) 전 price 구분·finite·unit 정합 ⇒
  통과.

### 5.6 risk decision integrity (+ rcl seam 생산) (§15/§16; ARE-EV-002/004 지원, core L1 슬라이스)

`risk_decision(policy, snapshot, scenario_set, effect, projection) -> AggregateRiskDecision`:

- **decision integrity(ARE-INV-006 line 173·§15)**: projection 완비 시에만 결정. requested increment > headroom ⇒
  `DENY`; UNKNOWN current/exposure/valuation/scenario/mapping ⇒ `UNKNOWN`(conservative 소비·new risk 차단, §1
  line 37). `GRANT`은 exact·closed·non-transferable(§15 line 385); 빈 requested scope/vector ⇒ restrictive(zero/
  wildcard/unbounded 아님, §15 line 385).
- **envelope-not-enlarged 전용 술어(ARE-INV-007 line 178·§4.7 enlarge 동사 봉합, v1.1 MINOR-2)**:
  `envelope_bound_not_enlarged(injected_envelope_max, decision_effective_limit, limit_source) -> bool` — 결정의
  effective_limit이 **주입된 Hard Safety Envelope max를 초과하지 않고** ∧ limit source가 runtime policy/strategy/
  human approval/broker result/model output이 **아니라** 주입 envelope일 때만 True. ARE-INV-007 line 178 verbatim
  "Neither runtime policy, strategy, human approval, broker result, nor model output may enlarge the Hard Safety
  Envelope or single-action bound." Runtime Safety Profile은 narrow-only(§1 line 27)이므로 profile 값도 envelope를
  확대 못 함(spg 소유; are는 주입 소비). **canary(both-ways)**: (a) effective_limit > 주입 envelope max, 또는
  limit이 broker/model/runtime 출처 ⇒ `False`/`DENY`(가드 발화 — enlarge 시도 차단); (b) effective_limit ≤ 주입
  envelope max ∧ 출처가 envelope ⇒ 통과(양성 side — 정당한 좁힘을 막지 않음).
- **produces rcl seam(§3.4)**: `RiskDecisionResult`(GRANT/DENY/UNKNOWN)·`decision_id`·`decision_generation`·
  `canonical_decision_digest`·`aggregate_risk_authority_grant_identity`·`applicable_risk_scopes`·all-false
  `AggregateRiskAuthorityEffect`. rcl `grant_authorizes_exact_request`(`predicates.py:575`)이 exact binding 검증;
  are는 reservation 좌표 미생산(§16 non-cyclic).
- **canary(ARE-AC-004/008, both-ways)**: (a) increment>headroom ⇒ `DENY`; UNKNOWN state에서 capacity 존재 ⇒
  여전히 `UNKNOWN`(§24.8 "Capacity coverage is necessary but not sufficient", 가드 발화); 빈 grant scope ⇒
  restrictive; (b) projection 완비·increment≤headroom·전 state known ⇒ `GRANT` 가능(양성 side).

### 5.7 evidence 재구성 substrate (§22; ARE-EV-001/002/003/004/006 공통)

- **frozen digest-bound 레코드**: `AggregateRiskPolicy`/`AggregateRiskStateSnapshot`/`AdverseScenarioSet`/
  `AggregateRiskDecision`/`ProjectedCell`/`BenefitProof` 각 결정을 durable evidence에서 재구성 가능케 함(§22
  line 508–515 canonical policy/scenario/snapshot/decision/vector/limit/dependency 아티팩트 + 모든 valuation/
  conversion/rounding/scenario/netting/uncertainty/numerical derivation). **replay ENGINE 자체는 ADR-002-016**
  (not-Phase-1). **Evidence Is Not Authority**(ARE-INV-014 line 205; §4.5). evidence 참조는 scalar(id/gen/digest).
- **canary**: id⊥digest이므로 same-id/diff-bytes decision ⇒ `classify_record_pair` `CRITICAL_CONFLICT`(위조·
  contradictory decision 탐지·양쪽 보존, no last-write-wins; §2.3).

---

## 6. predicate-only 술어 — benefit·numerical-determinism·concurrency·currentness·protective·non-revival·authority (ARE-EV-005/007/008/009/010/011/012 substrate, 최소 ≥ L2·닫지 않음)

각각 **L1-decidable substrate**를 저작하나 **어떤 ARE-EV도 닫지 않는다**(최소 ≥ L2·+Security/+Broker 잔여).

### 6.1 benefit admissibility (§13; ARE-EV-005 substrate, predicate-only)

`benefit_admissible(proof: BenefitProof) -> bool` — §4.2 중앙 불변식. 7 전제 전부 양성 시에만 `True`; 미증명/
common-mode/broker-margin-only ⇒ `False`. **+Security(common-mode 독립·shared-source)·런타임 correlation 산술은
not-Phase-1**(§28 q6/q8). 최소 `EV-L2/3+Security`.

### 6.2 numerical determinism / differential (§14; ARE-EV-007 substrate, predicate-only)

`numerical_determinism(...)` — §4.3의 L1(finite/canonical) 넘어선 **parser/library/model differential·비결정
ordering·non-convergence·독립 재현**. 006이 담는 L1 numerical-safety substrate 위에서 **differential은 EV-L2
component-fault·+Security**(malicious NaN/overflow input, §23 line 540). 최소 `EV-L2/3+Security`.

### 6.3 non-cyclic binding + concurrent-not-reservation (§16/§18; ARE-EV-008 substrate, predicate-only)

`non_cyclic_binding(decision) -> bool`(§4.6: decision이 미래 commitment 미binding·forward-only) ∧
`concurrent_not_reservation(...) -> bool`(§18 line 448 "Concurrent evaluations may observe the same headroom but
cannot reserve it. Only RCL serialization creates exclusive commitment"). **serialization·fence enforce는 rcl
런타임**(§28 q9). 최소 `EV-L2/3`.

### 6.4 currentness / invalidation (§17; ARE-EV-009 substrate, predicate-only)

`currentness_invalidation(triggers, decision) -> bool` — material change(§17 line 430–436: position/order/fill/
commitment/external/protective·effect/command/approval/venue/context/broker·price/vol/liq/corr/basis/FX/margin/
collateral/borrow/settle/CA·envelope/profile/policy/scenario/model/schema/mapping/library/build·source/time/
recovery/epoch/security) ⇒ affected unconsumed decision invalidate. **cache/TTL/heartbeat/health/last-known-
generation/eventual-consistency/absence-of-invalidation ≠ currentness**(§17 line 440). race ⇒ potentially-live·
covered·blind-retry 금지(§17 line 442). **active RCL/final-egress currentness enforcement은 런타임**(profile
bound B_aggregate_risk_invalid_to_rcl/egress). 최소 `EV-L2/3+Security`.

### 6.5 protective / exit / partition evaluation (§19; ARE-EV-010 substrate, predicate-only)

`protective_creates_nothing(...) -> bool`(§4.6·ARE-INV-012: exit/reduce-only/emergency label이 capacity/
feasibility/allocation/transmission 창조 못 함, §19 line 470) + **protective magnitude 생산은 §5.3에서 정의**
(protective seam producer — under-realization 봉합 #7/#11: 전용 슬롯이 실재하므로 §5.3이 정의 술어 부여, 여기서
상호참조). `RESTRICTED_PROTECTIVE_ONLY`/HALT ⇒ dimension 생략·headroom 발명 금지; feasibility/capacity unknown ⇒
trapped exposure/containment(§19 line 470). **partition/broker-alive·pre-committed protective lease는 런타임**
(ADR-002-001/002; #11 §6.2). 최소 `EV-L2/3+Broker`.

### 6.6 non-revival + economic continuity (§20/§21; ARE-EV-012 substrate, predicate-only)

`non_revival_holds(...)`(무조건 True — §4.6) ∧ `economic_effect_persists(...)`(missing ACK/timeout/cancel/
withdrawal/decision-expiry/policy-expiry/evaluator-failure가 committed/potentially-consumed capacity를 release
못 함, §20 line 480·ARE-INV-011 line 193; reconciliation은 defined RCL transition request 가능하나 decision
rewrite·UNKNOWN erase·capacity free 불가, §20 line 482; conflicting evidence ⇒ conservative 확대). **Recovery
Barrier(ADR-002-017)·governed re-arm workflow enforce는 런타임**(§21 line 498·§28). 최소 `EV-L2/3+Security`.

### 6.7 authority separation / all-false (§7/§23; ARE-EV-011 substrate, predicate-only)

`AggregateRiskAuthorityEffect` all-false(§4.6·ARE-INV-009: rcl `RclAuthorityEffect` 동형·어떤 True도
unconstructable) + `grants_no_authority(effect) -> bool`. §23 line 547 "The Aggregate Risk Authority SHALL NOT
hold or obtain a usable live-order credential, signer, broker session, or broker-order route." **evaluator↛live
credential·egress bypass·common-mode privilege path는 +Security 런타임**(ADR-002-013 confinement, §23). 최소
`EV-L2/3+Security`.

---

## 7. property-test 하네스 타깃

§1 분류에 정렬한다. **닫는 ARE-EV = 0건** — 어떤 test-target도 ARE-EV closure·acceptance를 주장하지 않는다
(규율 태그 부착). 각 술어에 **both-ways canary**(§4·§5·§6)와 **fixture clean-vs-illegal 정합**(#8 교훈)을 건다.

- **core(L1 슬라이스, ARE-EV-001/002/003/004/006 substrate)**: `snapshot_scope_complete`(§5.1); `exact_effect_
  snapshot_binding`+decision content ref(§5.2); `adverse_increment`+projection dominance+protective magnitude
  생산(§5.3); `dimension_vector_integrity`(§5.4); `valuation_conservative`+`numerical_safety`+`CanonicalDecimal`
  finite(§5.5); `risk_decision`+GRANT/DENY/UNKNOWN+all-false authority+`envelope_bound_not_enlarged`(§5.6,
  ARE-INV-007 enlarge canary); frozen digest-bound 레코드 재구성·
  `classify_record_pair` CRITICAL_CONFLICT(§5.7). hypothesis property: policy/snapshot/scenario/cell/magnitude를
  무작위 생성해 scope-완전성·exact-binding·projection-dominance·dimension-integrity·numerical-safety·decision-
  integrity 불변식을 검사.
- **predicate-only(ARE-EV-005/007/008/009/010/011/012 substrate, EV 미주장)**: `benefit_admissible`(§6.1);
  `numerical_determinism`(§6.2); `non_cyclic_binding`+`concurrent_not_reservation`(§6.3); `currentness_
  invalidation`(§6.4); `protective_creates_nothing`(§6.5); `non_revival_holds`+`economic_effect_persists`(§6.6);
  `grants_no_authority`+all-false(§6.7).
- **seam cross-check(test-only, MANDATED §3.4)**: `test_seam_protective`(are magnitude ↔ protective
  `AggregateRiskComparison`/`IntermediateStateWitness` polarity·None⇒`RISK_INCREASING_DENIED`)·`test_seam_rcl`
  (are decision ref ↔ rcl `grant_authorizes_exact_request` `predicates.py:599–614`·all-false ↔ `RclAuthorityEffect`·
  최종 `AdverseIncrement[s,d]` `CapacityVector` 좌표 일치)·`test_seam_spg`(are `aggregate_effect_within` ↔ spg `predicates.py:466`). 테스트
  import는 package closure에 불계상(§7.1).
- **∅-공허 회귀(양방향, §4.7)**: 빈 scenario set ⇒ `adverse_increment` `UNKNOWN`(non-vacuous); 빈 dimension set ⇒
  `dimension_vector_integrity` `False`; 빈 scope set ⇒ `snapshot_scope_complete` `False`; 빈 BenefitProof ⇒
  `benefit_admissible` `False`; **동시에** 각 완비 입력의 정당 통과 canary.

### 7.1 import-closure 검증 테스트 (설계 #4 §7.1·#5..#12 §7.1 상속)

`import tos.are` 후 `sys.modules` closure에 **금지 집합 부재 assert**: `shared.config`·`os.environ` 흔적·`numpy`/
`pandas`/`yaml`·**`tos.rcl`·`tos.protective`·`tos.spg`·`tos.liveauth`·`tos.authority`·`tos.time`·`tos.capsule`·
`tos.evidence`·`tos.brokercap`·`tos.orthostate`·`tos.recon`·`tos.dsl`** 부재; **`tos.canonical`·`tos.ordering`
존재 허용**. required check(`tos-firewall`, `tools/tos_firewall_check.py` layer-① AST + `.importlinter` layer-②
전이)와 함께 green이어야 §0.3 선언이 능동 성립.

### 7.2 run manifest 정렬 (설계 #1 §5.1 7항목)

(1) 목적: are Phase-1(EV-L1) 순수 모델+property test. (2) 명령: `pytest tos/tests/are/ -v`. (3) 격리:
hermetic(`.env` 비주입·clock 미접근·네트워크 없음). (4) 결정론: hypothesis 시드 고정·`CanonicalDecimal` scale-
normalize·NaN/infinity 구성-거부. (5) 산출물: property test 결과(EV closure 아님 — 규율 태그). (6) 게이트:
`tos-firewall` required green. (7) 비-acceptance: 어떤 ARE-EV도 닫지 않음(§0.2·VER-002-001 §5).

---

## 8. bounds 주입 + Phase-0

**§8.0 are decision 구조에 numeric bound 부재**: 전부 enum(`RiskDecisionResult`/`RiskDimensionKind`/`RiskScope
Kind`/`AdverseScenarioKind`/`BenefitKind`)·boolean·집합 논리·주입 `CanonicalDecimal`(magnitude·limit·headroom).
ADR §4 non-scope line 108 "numeric age, invalidation, or execution bounds"는 수치를 **명시 배제**한다 — 전부
**Safety/Verification Profile INSTANCE 측정값**이며 주입 opaque param으로만 담는다. 값 부재 ⇒ fail-closed(§4).
값 승인은 Bounds-Approver 게이트(§9.2).

**§8.1 Verification-Profile 키 실측(MAJOR-2 규율 — `measurement_source` 전수 확인)**: ADR-002-021이 요하는 수치
분류 및 VERIFICATION-PROFILE-002.yaml 키 상태(전수 grep):
- **invalidation-to-RCL(§16–18)**: `B_aggregate_risk_invalid_to_rcl`(line 268, `value_ms: null` MEASURE,
  `measurement_source: aggregate_risk_generation_decision_and_rcl_admission_trace`, `failure_response:
  STOP_NEW_RISK`) — **이미 존재**.
- **invalidation-to-egress(§17)**: `B_aggregate_risk_invalid_to_egress`(line 275, `value_ms: null` MEASURE,
  `measurement_source: aggregate_risk_generation_invalidation_and_egress_boundary_trace`, `failure_response:
  HALT`) — **이미 존재**.
- **snapshot age(§9)**: `MAX_aggregate_risk_state_snapshot_age_ms`(line 715, `null` — "APPROVE per aggregate
  scope; unknown age denies allocation and dependent new risk") — **이미 존재**.
- **decision age(§15/§17)**: `MAX_aggregate_risk_decision_age_ms`(line 716, `null` — "APPROVE per exact effect/
  allocation scope; expiry never expires economic effect") — **이미 존재**.
- **scope pin(§8/§11)**: `aggregate_risk_policy_id/generation/digest`(line 58–60)·`adverse_scenario_set_id/
  generation/digest`(line 61–63) — 전부 TBD/null(§5.1/§5.4 아티팩트의 test-harness pin).
- **결론(over-claim 봉합·#10 lesson)**: §29 item 9가 요구하는 4 bound(invalidation-to-RCL·invalidation-to-
  egress·snapshot age·decision age)가 **전부 실재**하고 전부 null/MEASURE(미승인). ⇒ **candidate 신규 키 = 0건**
  (#10 "0 누락" 동형; #12의 4-key 누락과 대조). 이는 결함이 아니라 **Phase-0 Bounds-Approver 승인 항목**이다 —
  are는 이 값들을 신뢰하지 않으며(VP status PROPOSED·unapproved bound은 approved bound 아님, VER-002-001 §6) 전
  수치를 fail-closed로 처리(§4).

**§8.2 self-referential 주의(경미)**: are `AggregateRiskPolicy`는 spg Safety Configuration Bundle member(§5.1)
이며 VP scope 블록이 policy/scenario id/generation/digest를 pin한다. #12(spg)가 다룬 self-reference paradox와
달리 are는 **Bundle의 member 하나**일 뿐(governance 주체 아님)이라 layering이 단순하다 — are는 VP를 import·파싱
하지 않고(YAML은 하네스 #3), policy/scenario 좌표를 주입 scalar로만 담는다. VP status PROPOSED ⇒ 전 수치 불신.

**§8.3 are↔spg generation-separation(런타임 acyclicity 종결·v1.1 NIT — open question (iii) 해소)**: are↔spg
상호 value-flow의 런타임 시간축 분리를 명시한다 — **are는 이미 활성화된 envelope generation `n`을 소비**(§8
dominance; 활성 envelope는 이미 spg가 commit)하고, **`aggregate_effect_within`은 아직 활성화 전인 제안 config
generation `n+1`의 aggregate risk effect에 관해 생산**한다(spg가 새 Bundle을 validate할 때 step 7로 소비). 즉
두 방향은 **서로 다른 generation을 참조**하므로 값-의존 cycle이 없다(are가 소비하는 `n`은 are가 생산하는 `n+1`
판정의 입력이 아니다). 이는 import-graph acyclicity(§0.4b·§3.4: 양쪽 미import)에 더해 **런타임 데이터 acyclicity**
까지 닫는다 — §16 non-cyclic pipeline이 결정-술어(Phase-1)와 런타임(EV-L3) 양 층에서 성립.

---

## 9. 후속 작업 · Phase-0 인간 게이트 이관 항목

### 9.1 후속 구현 작업 (본 계약 위에서)

1. `tos/src/tos/are/` 5-module 저작(`_base.py` shim·`vocabulary.py`·`records.py`·`predicates.py`·`state.py`)
   + `tos/tests/are/` property test(§7) + seam cross-check(§3.4) + import-closure(§7.1).
2. core 술어 7종(§5) + predicate-only 술어 7종(§6) + 4-아티팩트·`ProjectedCell`·`BenefitProof`·`RiskDimension
   Descriptor`·all-false authority(§2) 구현 + `AdverseScenarioKind`/`RiskDimensionKind` frozenset.
3. 미래 caller 런타임(Aggregate Risk Authority / Snapshot Assembly / RCL-admission)이 are 산출 magnitude/decision
   scalar·최종 `AdverseIncrement[s,d]`(`CapacityVector`)를 소비자(protective/spg/orthostate 주입 슬롯·rcl commit)로
   배선(§3.4; Phase 1 밖·EV-L3). **최종 vector는 `CapacityVector` REUSE라 축약 reducer 불요**(v1.1 MAJOR-1; §0.4c).

### 9.2 Phase-0 인간 게이트로 넘기는 항목 (본 계약이 결정하지 않음)

ADR §28 Open Implementation Questions(14항)·§29 Approval Gate(14조건)에서 Phase-1 밖으로 이연:
1. **canonical Policy/Snapshot/ScenarioSet/Decision schema 선택**(§28 q1) — 프로덕션 canonical semantic form
   (§3.1 EVL1ProvisionalCanonicalizer는 잠정).
2. **per-product/account-class dimension/unit/scope/dependency-closure/comparison 규칙**(§28 q2·q11) —
   `RiskDimensionKind`의 구체 열거·cross-dimension 비교(§5.4는 구조만).
3. **consistency-cut protocol(snapshot 조립)**(§28 q3) — RCL/broker-projection/reconciliation/account/Critical-
   Input across 완전 snapshot 런타임.
4. **valuation/stress/slippage/liquidity/vol/correlation/basis/FX/margin/collateral/settlement/option/assignment
   model 선택**(§28 q4) — 전부 주입(§4 non-scope).
5. **scenario add/prune/dominate/version/independent-review/invalidate**(§28 q5) — `AdverseScenarioSet` 진화
   (§5.4는 min-coverage floor만).
6. **netting/hedge/diversification/margin-offset/collateral/correlation benefit의 exact proof**(§28 q6·§13) —
   `BenefitProof` 7 전제의 런타임 증명(§6.1은 술어만).
7. **deterministic numeric/unit/solver/optimization/canonicalization/independent-verification 메커니즘**(§28 q7).
8. **common-mode separation**(§28 q8·§23) — sources/snapshots/models/schemas/mappings/libraries/evaluators/
   verifiers/administrators/deployments across(+Security).
9. **Aggregate Risk Generation + stale-evaluator fence substrate**(§28 q9·§18) — RCL·every final egress 도달
   런타임.
10. **RCL admission + final egress active decision currentness(cache/cycle 없이)**(§28 q10·§17) — 런타임.
11. **numeric bounds 승인**(§28 q12) — `B_aggregate_risk_invalid_to_rcl`·`B_aggregate_risk_invalid_to_egress`·
    `MAX_aggregate_risk_state_snapshot_age_ms`·`MAX_aggregate_risk_decision_age_ms`(§8.1 **전부 실재·null**)의
    Bounds-Approver 승인 + fault-injection 측정(§29 item 9). **candidate 신규 키 0건.**
12. **non-live broker/account/product combination**(§28 q13·§29 item 10) — bounded worst credible effect 불가
    조합.
13. **restricted-production evidence(model/sim/sandbox 넘어)**(§28 q14·§29 item 8) — ARE-EV-001..012 실행·독립
    리뷰.
14. **ADR-002-022 AFG binding(§29 item 13)·ADR-002-023 IAP upstream(§29 item 14)** — action-flow vector·permit·
    approval 결정의 same command/effect/risk-decision chain binding(각 ADR EV family).
15. **ADR-002-016 Evidence Integrity·Replay Capsule**(§22·§28) — replay ENGINE(§5.7 레코드 substrate만 Phase-1).
16. **ARCHITECTURE-GATE-STATUS 명시 acceptance 결정**(§29 item 12) — 실행된 ARE-EV-001..012 + cross-system
    evidence(RC/SPG/PRD/…) + 독립 리뷰(Independent-Safety-Reviewer 하드 배제, IMPLEMENTATION-PLAN-002 §3).

---

## 10. 개정 로그 + 비준 체크리스트

### 10.1 개정 로그

- **v1.1 (2026-07-25) — 독립 비평 리뷰 REVISE 반영(forward-only), 운영자 비준 대기.** CRITICAL 0·MAJOR 1·MINOR
  2·NIT 수건. 전 인용 실측 검증 통과(phantom 0·fail-open 0·EV over-claim 0·VP 4-키 실재·5행 정정 정확). 코어
  아키텍처(fail-closed 술어·4-아티팩트·EV 규율·∅-공허 양방향·#11 OQ3 충전·bounds 0-누락)는 정확 판정; seam
  vector 결정 1건·acyclicity 논증 1건의 과장을 최소 edit set으로 정정.
  - **MAJOR-1 (AdverseIncrementVector 자체-vector → REUSE 채택)**: v1.0은 rcl `CapacityVector` 미-REUSE(자체
    vector)를 결정하고 축약 reducer를 EV-L3로 이연하면서 "dominance under-count 0을 seam cross-check가 봉인"이라
    주장 — **존재하지 않는 reducer의 under-count-0은 Phase-1 assert 불가**(리뷰어 실증). 또한 v1.0의 암묵 전제
    "are→rcl은 cycle"은 오류(**rcl↛are 실측** — `rcl/authority.py` `GrantDecisionRef`는 주입 `str|None`; #8
    orthostate→rcl edge 선례 `orthostate/records.py:36`). **ADR 원문 대조 판정**: §2 line 47·§16이 "ADR-002-002
    defines the capacity vector, **Adverse Increment Vector**"라 명시 — vector 타입 소유자는 ADR-002-002(rcl)
    이므로 자체 vector는 소유 타입 **중복·좌표 붕괴 위험**. ⇒ **옵션 (a) REUSE 채택**: 최종 `AdverseIncrement[s,d]`
    =rcl `CapacityVector` REUSE(are→rcl 1 edge·**타입 수준 dominance 봉인**·축약 reducer 제거), 중간 `ProjectedCell`
    은 are-local. 전 출현 정정(§0.1/§0.2/§0.3/§0.4b/§0.4c/§0.4e/§2.0/§2.1/§3.3/§3.4/§3.5/§4.4/§7/§9.1). **기각 (b)
    자체 vector**: Phase-1 참조 reducer+property 명세 부담·좌표 붕괴 위험(§0.4c 기록). **sibling edge 0→1(are→rcl);
    PROMOTE 여전히 0**. 완화: ADR §16 line 415–422 rcl commit-time 2차 게이트.
  - **MINOR-1 (edge-0 "§16 유일 실현" 과장 철회)**: §0.4b(ii)·§2.0·§3.4·§0.4e의 "package edge 어느 방향이든
    cycle"·"edge-0은 §16 요구" 주장 철회 — 단일 방향 edge는 import-graph cycle이 아님(spg↛are 실측 `records.py:205`
    주입). 정확형: "양방향 value-flow(are↔spg)를 acyclic하게 하려면 최소 한 방향이 주입이어야 하고, 어느 ratified
    측도 접촉하지 않으려면 양방향 주입이 권장; are→rcl은 예외적 단일 edge(rcl↛are)". **§8.3 런타임 generation-
    separation**(are가 활성 gen n 소비 / 제안 gen n+1 판정 생산)으로 런타임 acyclicity까지 종결(OQ iii 해소).
  - **MINOR-2 (ARE-INV-007 enlarge 전용 canary 신설)**: §4.7 금지 동사 중 enlarge만 §8 주입 소비로 암묵 처리됐던
    것을 정정 — `envelope_bound_not_enlarged`(effective_limit > 주입 envelope max 또는 broker/model/runtime 출처
    ⇒ DENY) 전용 both-ways canary를 §5.6에 신설·§7 core·§4.7에 반영. 전 금지 동사가 전용 canary 보유.
  - **NIT**: §5.7 header에 ARE-EV-001 추가(snapshot 재구성 정합); §8.3 are↔spg generation-separation 문장 추가
    (OQ iii 해소); §0.4d `_base` shim 명확화(canonical 원시타입 re-export + all-false 베이스는 canonical에 없어
    로컬 fresh 정의, rcl `_base.py:55` `AllFalseAuthority` 동형); 라인 정정 recon `records.py:29→28`·protective
    `predicates.py:289→289–290`(None-check 289·`RISK_INCREASING_DENIED` return 290).
- **v1.0 (2026-07-25) — 초안, 독립 비평 리뷰 대기.** ADR-002-021을 Phase 1(EV-L1) 설계 계약으로 실현. 패키지
  `tos.are`(대안 `tos.riskproj`[좁음]·`tos.aggrisk`/`tos.riskeval`[비관행]·`tos.risk`/`tos.projection`[collision]
  기각, §0.4a). 4-아티팩트(`AggregateRiskPolicy`·`AggregateRiskStateSnapshot`·`AdverseScenarioSet`·`AggregateRisk
  Decision`, 전부 IndependentIdArtifact·digest-bound·generation-immutable append-only) + `ProjectedCell`·`Benefit
  Proof`·`RiskDimensionDescriptor`·all-false `AggregateRiskAuthorityEffect`(§2). EV 분류: **core 5행(ARE-EV-001·
  002·003·004·006, #11형 core tier) / predicate-only 7행(005·007·008·009·010·011·012) / not-Phase-1(런타임·
  +Security·+Broker·형제) — 닫는 ARE-EV = 0건**(§1). **실측-원천 정정**: orchestrator 사전 카운트 "L1 슬라이스
  6행" → register 실측 **5행**(005·007·008·009·010·011·012는 최소 EV-L2, §1 결정적 사실 1). seam: **protective/
  rcl/spg 3-소비자 produced-scalar/bool producer + orthostate state-의존, sibling edge 0 **[v1.1 MAJOR-1: are→rcl
  1 edge로 정정]**, PROMOTE 0**(코드 실측:
  protective `records.py:136–168`·`predicates.py:246/289/529/531`, rcl `authority.py:39/53–59`·`predicates.py:575`·
  `records.py:98–99/185`, spg `records.py:205`·`predicates.py:466`, orthostate `vocabulary.py:43–45`, §3.4).
  **핵심 아키텍처 판정**: are↔spg 상호 value-flow(are가 envelope 소비 + `aggregate_effect_within` 생산)는 **양쪽
  미import(edge-0)일 때만 acyclic** — edge-0은 관행 정합을 넘어 **ADR §16 non-cyclic의 유일 실현**(§0.4b (ii))
  **[v1.1 MINOR-1 철회: 단일 방향 edge는 import-graph cycle이 아니므로 "유일 실현"은 과장 — spg seam은 양방향
  주입, are→rcl은 허용 단일 edge]**.
  **#11 OQ3 충전**: are가 protective `AggregateRiskComparison`/`IntermediateStateWitness` magnitude를 생산(§3.4/
  §5.3) — protective가 "supplied by ARE (an unimplemented tos package)"로 대기하던 슬롯. **non-cyclic 코드 실현**:
  are decision은 forward-only content ref(`decision_id/generation/digest`)만 생산; rcl `GrantDecisionRef`가
  `bound_reservation_*`를 post-commit 충전(§16 line 413·§5.6). **`AdverseIncrementVector`→rcl `CapacityVector`
  미-REUSE 결정**(edge-0·자체 vector; 운영자 결정 지점, §0.4c) **[v1.1 MAJOR-1: REUSE 채택으로 정정 — rcl↛are
  acyclic·존재하지 않는 reducer under-count 봉인 불가]**. 중심 fail-closed 술어: `adverse_increment`(보수
  projection·favorable-intent 음수화 차단)·`benefit_admissible`(7 전제)·`numerical_safety`(NaN/overflow⇒UNKNOWN)·
  `risk_decision`(increment>headroom⇒DENY·UNKNOWN⇒restrictive)·`non_revival_holds`·`economic_effect_persists`(§5/
  §6). **∅-공허 양방향**(빈 scenario/dimension/scope/benefit — 금지 방향+허용 방향 둘 다, §4.7). 앵커: ARE-INV-
  001..014·ARE-AC-001..012·ARE-EV-001..012(§0.4f). **bounds 실측**: 4 profile 키 전부 실재·null(candidate 신규
  키 0건, §8.1). 선제 봉합: fail-open(§4.1/§4.3)·∅-공허 양방향(§4.7)·under-realization(protective/rcl/spg 전용
  슬롯엔 정의 술어·orthostate는 정직 state-의존 이연, §3.4)·phantom 타입 0(전 인용 grep 실측)·verbatim+line·
  좌표 비붕괴(§4.4). **어떤 EV도 닫지 않음·acceptance 미선언.**

### 10.2 비준 체크리스트 (운영자 · 독립 리뷰어 확인 사항)

1. **패키지 명명** `tos.are`(Aggregate Risk Evaluation) 승인 — 또는 대안(§0.4a에서 `riskproj`/`aggrisk`/`risk`/
   `projection` 기각 근거 검토; naming은 load-bearing 아님). "are=상용어" 우려 수용 여부.
2. **seam 결정**: magnitude/decision seam produced-scalar/bool 주입(edge 0) + 최종 vector are→rcl `CapacityVector`
   REUSE(1 edge, v1.1) — vs 대안 B(소비자 측 edge, 침습; **cycle 아님** — v1.1 MINOR-1 정정) — §3.4/§0.4b.
   **[운영자 판단 지점]**. protective/rcl/spg 슬롯이 실재함을 코드로 재확인(리뷰어: `protective/records.py:
   136–168`·`rcl/authority.py:39–59`·`spg/records.py:205` 인용 라인 검증 — sibling 서사 아님).
3. **`AdverseIncrementVector` 결정 (v1.1 MAJOR-1 채택)**: 최종 `AdverseIncrement[s,d]` = rcl `CapacityVector`
   REUSE(are→rcl 1 edge; rcl↛are 실측 acyclic·#8 orthostate→rcl 선례) — 자체 vector(기각·존재하지 않는 reducer
   under-count 봉인 불가)·canonical PROMOTE(기각·무거움) 근거 검토(§0.4c). **[운영자 판단 지점]**: REUSE(채택)
   승인 여부. 최종 vector 좌표가 rcl commit 타입(`proposed_adverse_increment`)과 **동일**함을 seam test로 확인
   (타입 수준 dominance — 별도 축약 reducer 불요). 중간 `ProjectedCell`은 are-local(scenario 축).
4. **EV 분류·실측 정정**: core 5 / predicate-only 7 / not-Phase-1 판정과 **닫는 ARE-EV = 0건** 규율 확인. 특히
   **사전 카운트 "6"→실측 "5"** 정정(005·007·008·009·010·011·012가 최소 EV-L2임을 register line 280–287로 재확인)이
   §1·§5·§6·§7에 일관한지·"EV-L1-complete 주장 금지"가 부착됐는지 self-consistency pass.
5. **non-cyclic 코드 실현(§5.6/§4.6)**: are decision이 forward-only(`decision_id/generation/digest`만)이고
   reservation 좌표(`bound_reservation_*`)를 생산하지 않아 rcl이 post-commit 충전함을 §16 line 413과 대조(리뷰어:
   `rcl/authority.py:53–58` 필드 분리 검증). **acyclic(v1.1 정확형)**: are→rcl 단일 edge(rcl↛are 실측)·are↔spg
   양방향 주입(양쪽 미import)·**§8.3 런타임 generation-separation**(gen n 소비 / n+1 판정 생산)까지 재확인(OQ
   iii 해소; "양쪽 미import가 §16 유일 실현"이라는 v1.0 과장은 §0.4b·§3.4에서 철회).
6. **소유권 분할(§3.5)**: are가 rcl capacity 산술(`CapacityVector`/`transition_allowed`)·protective classify
   (`protective_classification`)·spg envelope 거버넌스(`profile_within_envelope`)·capsule/recon snapshot 조립·
   final egress를 **재저작하지 않음** 확인(#8·#11·#12 권위 중복 교훈).
7. **#11 OQ3 충전(§3.4/§5.3)**: are가 protective `AggregateRiskComparison`(`records.py:149–152`)·`IntermediateState
   Witness`(`records.py:166–168`) magnitude를 생산하고 protective가 비교만 함(None⇒`RISK_INCREASING_DENIED`
   `predicates.py:289–290`) 확인.
8. **fail-closed·∅-공허 양방향(§4.7)**: 빈 scenario set⇒`UNKNOWN`·빈 dimension⇒`False`·빈 scope⇒`False`·빈
   benefit⇒`False`·None magnitude⇒UNKNOWN/`RISK_INCREASING_DENIED`, **각각 금지+허용 canary 둘 다** 확인(#6 fail-
   open·#10/#12 ∅-void 교훈). 금지 동사(exclude/shrink/patch/union/enlarge/revive/release/create) 커버리지 대조.
9. **numerical safety(§4.3/§5.5)**: NaN/infinity/overflow/unit-mismatch⇒UNKNOWN/DENY·`CanonicalDecimal` 구성-거부·
   fallback 금지(§14 line 365) 확인(#12 NaN 구성-거부 선례 대조).
10. **실측-원천·phantom 0**: 전 인용 타입(`AggregateRiskComparison`·`IntermediateStateWitness`·`GrantDecisionRef`·
    `RclAuthorityEffect`·`ProtectiveActionOutcome`·`aggregate_effect_within`·`AUTHORIZED_FOR_CAPACITY`)이 실코드에
    존재함을 grep 재확인(#10 MAJOR phantom 교훈 — 인용 전 실측). ARE-INV(14)·ARE-AC(12)·ARE-EV(12) 수·seam 라인이
    원문/코드와 일치.
11. **bounds 실측(§8.1)**: 4 profile 키(`B_aggregate_risk_invalid_to_rcl/egress`·`MAX_aggregate_risk_state_
    snapshot/decision_age_ms`)가 **전부 실재·null**(candidate 신규 키 0건)임을 `measurement_source` 전수 확인
    (over-claim 아님 — #10 lesson; #12 4-key 누락과 대조).
12. **broker-agnostic·숫자 하드코딩 0·firewall(§0.3)·verbatim 전사(§2.2)** 확인.
13. **비-acceptance**: 어떤 ARE-EV/ADR acceptance·restricted-live·production도 선언 안 함(§0.2)·Independent-
    Safety-Reviewer 하드 배제 확인·비준 기록 = "v1.1 개정 완료 — 운영자 비준 대기".
14. **[v1.1] MAJOR-1 self-consistency**: sibling edge 0→1(are→rcl) 정정이 §0.1/§0.2/§0.3/§0.4b–e/§2.0/§2.1/§3.3/
    §3.4/§3.5/§4.4/§7/§9.1 전체에 일관한지·rcl↛are 실측(`rcl/authority.py` 주입 `str|None`)·#8 orthostate→rcl
    선례(`orthostate/records.py:36`) 재확인. **[v1.1] MINOR-1**: "edge-0 = §16 유일 실현" 잔존 0건(§0.4b/§2.0/
    §3.4/§0.4e 철회). **[v1.1] MINOR-2**: `envelope_bound_not_enlarged`가 §5.6·§7·§4.7에 실재·전 금지 동사 canary
    커버리지. **[v1.1] NIT**: recon `records.py:28`·protective `predicates.py:289–290`·§5.7 ARE-EV-001·§8.3
    generation-separation 반영.

**독립 리뷰어 공격 지점(open questions)**: (i) **[v1.1 해소·잔여]** `AdverseIncrement[s,d]`=rcl `CapacityVector`
REUSE 채택(§0.4c MAJOR-1)으로 dominance는 타입 수준 봉인(축약 reducer 제거)됐다 — 잔여: 이 **단일 are→rcl edge**가
strict edge-0 규율 대비 수용 가능한지(#8 orthostate→rcl 선례로 정합 판단이나 운영자 확인 필요). (ii) orthostate
seam을 "전용 슬롯 없는 state-의존"으로 정직 이연(§3.4 (d))한 판정이 under-realization인지 정확인지(orthostate
records에 전용 are-bool을 신설해야 하는지). (iii) **[v1.1 해소]** are↔spg acyclic은 (a) import-graph(양쪽 미
import) + (b) **§8.3 런타임 generation-separation**(are가 활성 gen n 소비 / 제안 gen n+1 판정 생산 — 서로 다른
generation 참조라 값-cycle 없음) 두 층에서 종결. 잔여 검토: generation-separation 가정(n 소비 / n+1 생산)이 실제
런타임 순서와 일치하는지. (iv) core 5행이 실제로 전부 L1-decidable substrate를 갖는지(특히 ARE-EV-002
`+Security`·003/006 `+Broker`의 L1 부분과 +overlay 부분 분리가 정확한지). (v) `AggregateRiskStateSnapshot`을
are가 모델링하되 조립을 런타임 이연(§3.5)한 경계가 정확한지 vs snapshot 조립 술어 일부가 L1-decidable인지(#7
under-realization 인접). (vi) protective magnitude 생산을 §5.3(core)에 두고 §6.5(predicate-only ARE-EV-010)에서
상호참조한 배치가 정확한지 — protective 술어 자체는 이미 #11 구현이므로 are는 producer만 저작하는데, ARE-EV-010이
L2-floor인 것과 §5.3 core 배치가 모순 아닌지(판정: producer는 projection(§5.3 core L1)의 부산물이고 ARE-EV-010의
protective/partition **평가**가 L2 — 분리 정합).
