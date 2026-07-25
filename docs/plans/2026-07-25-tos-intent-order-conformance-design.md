# 설계 문서 #14 — Intent-to-Order Conformance·Canonical Command Construction 계약 (2026-07-25, v1.1)

- **대상 ADR**: ADR-002-020 — Intent-to-Order Conformance, Canonical Command Construction, and
  Economic-Effect Fencing ("IOC"). 752줄. Status **Proposed**.
- **자체 시리즈(실측·앵커)**: **IOC-INV-001..014**(§6 line 155–209, 14종)·**IOC-AC-001..012**(§26 line
  645–691, 12종)·**IOC-EV-001..012**(EVIDENCE-REGISTER-002 line 264–275, 12행). **새 시리즈 창작 금지**.
- **Depends On(ADR line 9)**: RFC-000 constitutional safe state; RFC-001 SAFE-003/004/010/011/013–015/020/
  021/024/025/030–035/040/041/043/044/046/048/050/051/052; ADR-002-002 through ADR-002-019.
- **시리즈 선례(동형 유지)**: 설계 #13(Aggregate Risk Projection, `tos.are`, v1.1)·설계 #12(Safety Profile
  Governance, `tos.spg`, v1.1)·설계 #C(Strategy DSL, `tos.dsl`).
- **비준 상태**: **2026-07-26 운영자 위임 자동 비준(v1.1; 2026-07-25 운영자 지시 "남은 ADR 자동 비준 승인
  으로 계속 진행" — 독립 비평 리뷰 REVISE[CRITICAL 0·MAJOR 1·MINOR 4]의 minimal edit set 전량 반영·upgrade
  조건 충족을 오케스트레이터가 검증 후 집행). §10.2 판단 지점: `tos.ioc` 명명 채택(오독 우려 기록)·
  ioc→rcl `CapacityVector` REUSE(5번째 sibling edge, #13 동형)·truthy-sentinel **구조적 봉인 채택**(M1,
  `ConformanceResult.__bool__` ⇒ TypeError). 효력: `tos/src/tos/ioc/` Phase 1(EV-L1) 착수.** 본 문서는 어떤 IOC-EV·ADR acceptance·restricted-live·
  production도 승인하지 않는다(§0.2). 효력 없음(리뷰 전).

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. ADR-002-020 조항별 **Phase 1(EV-L1) 도달성 경계**(§1). **core(L1 슬라이스) / predicate-only /
   not-Phase-1(형제 소유·런타임 이연) 3분류.** **결정적 사실(register 실측)**: `IOC-EV` 12행 중 **6행
   (001–006)이 register 최소 레벨에 `EV-L1` 슬라이스 보유**(#12형 core tier). 6행(007–012)은 최소 `EV-L2`
   (§1 표; register line 264–275 전수). **orchestrator 사전 카운트 "6"은 실측과 일치**한다(#13의 6→5 정정과
   달리 IOC는 정정 불요 — 001·002·003·004·005·006 전부 `EV-L1/3` 접두). 그러나 **닫는 IOC-EV = 0건**(L1
   슬라이스 저작 ≠ EV closure: `/3`·`+Security`·`+Broker` 잔여). "**EV-L1-complete 주장 금지**".
2. **6-아티팩트 데이터 모델**(§2, **core**): 전부 digest-bound인 `ApprovedIntentContract`(§5.1/§8)·
   `AuthorizedConstructionEnvelope`(§5.3/§8)·`OrderConstructionPolicy`(§5.2/§9)·`CanonicalBrokerCommand`
   (§5.4/§14)·`OrderConformanceProof`(§5.6/§14) `IndependentIdArtifact` + **`EconomicEffectEnvelope`
   =rcl `CapacityVector` REUSE**(§5.5/§13 — 중심 결정, §0.4c) + all-false `OrderConstructionAuthorityEffect`
   (§7/IOC-INV-011). 어휘: `ConformanceResult`(CONFORMANT/NON_CONFORMANT/UNKNOWN — §14 line 372 verbatim;
   **truthy-sentinel 임계**)·`ConformanceAxis`(§10–§12 축)·`MutationClass`(§16)·`OrderTypeKind`/`QuantityUnitKind`
   (§11/§12). **digest-bound 판정 근거 = §22 evidence 요구**(policy/envelope/command/proof/effect canonical
   아티팩트 + digest, line 523) + §14 command "one canonical representation and digest"(line 129)·proof
   "canonical digest"(line 353).
3. **intent-command conformance 중앙 불변식**(§4.1/§5, IOC-EV-001..006 substrate — ADR §10–§12·IOC-INV-003/
   004): `command_conforms(intent, command, policy, envelope) -> ConformanceResult`. **§10–§12 전 축**
   (environment/broker/account/venue/instrument/contract/endpoint/route·direction/side/position-effect·
   quantity/unit/multiplier/currency/scale/sign·price/order-type/TIF/expiration/mode)이 authorized envelope
   안에서 **정확 일치**할 때만 `CONFORMANT`; 한 축이라도 불일치/alias/default/ambiguity/unknown ⇒
   `NON_CONFORMANT`/`UNKNOWN`(§10 line 284·§11 line 301·§12 line 321). **bare bool 반환 금지 — `ConformanceResult`
   enum 반환**이며 소비 게이트는 **`result is ConformanceResult.CONFORMANT` 명시 비교**(truthy 금지, §0.4g/§4.7).
4. **compiler determinism 중앙 property**(§4.2/§5.2, IOC-EV-003/007 substrate — ADR §9·IOC-INV-002):
   **동일 (완비 approved inputs + Construction Generation) ⇒ 동일 canonical command + 동일 digest, 아니면
   construction 실패**(§9 line 160–161 verbatim). 순수 함수: **hidden clock/randomness/locale/env/mutable-cache/
   unordered-map/float-variation/network/"latest"-registry/SDK-implicit-default 금지**(§9 line 268). construction
   failure ⇒ **denial**(§9 line 270 "must not 'best effort' … or fall back"). **EV-L1 property의 노다지** —
   `compile(x) == compile(x)` digest 동일성 + hermetic(clock/network 부재) + generation-fence.
5. **economic-effect fencing 중앙 불변식**(§4.3/§5.5, IOC-EV-006 substrate — ADR §13·IOC-INV-005):
   `economic_effect_dominated(envelope: CapacityVector, committed: CapacityVector) -> bool`. **committed
   capacity가 envelope의 모든 governed dimension을 dominate**할 때만 True(IOC-INV-005 line 173); **compiler confidence·
   expected rejection·protective label·human approval·historical behavior가 envelope를 축소 못 함**(IOC-INV-005
   line 173·§13 line 343). None/UNKNOWN magnitude ⇒ **not-dominated(fail-closed)**(rcl `CapacityVector` None 전파 REUSE). **capacity
   binding exact** — proof는 ledger mutation 요청 불가·미사용 theoretical capacity를 permission으로 취급 불가
   (§13 line 341).
6. **no-silent-widening/narrowing + mutation-fence 불변식**(§4.4/§4.5, IOC-EV-004/008 substrate — ADR §11/§15·
   IOC-INV-006/007): `no_silent_widening(...)`(mapping/rounding/split/aggregation/default/normalization이
   authorized meaning을 바꾸려면 exact bounded transformation이 envelope 안 ∧ 모든 dependent gate가 그것을
   평가, §11 line 303 — "risk-reducing rounding"도 fail-closed) ∧ `mutation_fence_holds(...)`(proof 발급 후
   economic/security 필드 불변; **actual-outbound 비교는 +Security 런타임**, §15/§17 — Phase-1은 구조적 불변성
   술어만).
7. **retry/mutation lineage + non-revival + all-false authority 불변식**(§4.6/§6, IOC-EV-009/011/012 substrate
   — ADR §16/§21/§7): `derived_command_conformance(parent, derived, mutation_class) -> ConformanceResult`
   (retry/cancel/amend/replace/split/aggregate는 자체 command·attempt identity·proof·capacity·authority 보유;
   UNKNOWN never blind resubmission, §16 line 431) ∧ `recovery_revives_nothing(...)`(무조건 True — §21 line
   515) ∧ `economic_effect_outlives(...)`(intent/policy/command/proof/capability expiry가 order/attempt/fill/
   exposure/UNKNOWN/capacity를 expire 못 함, IOC-INV-012 line 201) ∧ `construction_grants_no_authority(effect)`
   (all-false — IOC-INV-011 line 197).
8. **IOC ↔ dsl/are/rcl/capsule/orthostate/brokercap/spg/venue 경계(중심 아키텍처)**: IOC는 **sibling edge 1건
   (IOC→rcl, `CapacityVector` REUSE만)**을 유지한다(§0.4c/§3.4; #13 are→rcl 선례 동형·실측 `rcl` closure=
   canonical+ordering+self). IOC는 (i) dsl `Proposal`(immutable Intent proposal identity, `proposal.py:68`)를
   **digest scalar로 소비**(IOC-INV-001 — dsl이 §8 field set을 IOC로 이연, dsl 설계 line 571–572), (ii) are
   `AggregateRiskDecision`(`records.py:451`, decision_id/generation/digest)를 **proof에 digest scalar로 binding**
   (§14 line 369), (iii) `EconomicEffectEnvelope`를 rcl `CapacityVector`(`vector.py:74`) 타입으로 **생산**(are가
   MaximumCredibleCommandEffect로 소비·rcl이 dominating vector commit — §14 protocol line 389–393), (iv) capsule
   `DecisionContextCapsule`(`capsule.py:170`)·`CriticalInputSnapshot`(`snapshot.py:96`)·orthostate
   `intent_identity`(`records.py:93`)·brokercap `BrokerCapabilityProfile`(`records.py:305`)·spg-governed policy·
   venue Order Admissibility Decision을 **digest/identity scalar로 주입 소비**한다. **rcl `CapacityVector`만
   import하고 나머지 12 형제(are/dsl/capsule/orthostate/brokercap/spg/liveauth/authority/time/evidence/protective/
   recon)는 미import** — produced/consumed scalar·digest로만 참조. `tos.ioc`는 `tos.canonical`·`tos.ordering`·
   `tos.rcl`(CapacityVector)만 import한다(§0.3). **PROMOTE 0건. sibling edge 1건(IOC→rcl, rcl↛ioc 실측 acyclic).**
9. **fail-closed 규율 + named both-ways canary + truthy-sentinel 소비 계약**(§4): unknown/stale/conflicting/
   non-canonical ⇒ denial(headroom 창조 금지); alias/default/substitute ⇒ 거부; lossy coercion ⇒ 거부; envelope
   초과 ⇒ NON_CONFORMANT; expiry ⇒ economic effect persists; recovery ⇒ non-revival; **∅ 양방향 명시**(빈
   envelope=construction 불가·빈 axis=NON_CONFORMANT·빈 required-authority-scope=UNKNOWN[zero/wildcard 아님, §14
   line 374]). **`ConformanceResult`·`bool|None` 반환 술어는 소비 게이트의 `is CONFORMANT`/`is True` 명시 비교
   계약을 §4.7에 명문화**(#13 truthy-sentinel 교훈 — `NON_CONFORMANT`/`UNKNOWN`는 truthy string이라 `if result:`
   면 fail-open).
10. **property-test 하네스 타깃**(§7, §1 분류 정렬) + import-closure 검증(§7.1) + run manifest 7항목(§7.2) +
    fixture clean-vs-illegal 정합(#8 교훈) + seam cross-check(test-only, §3.4) + **compiler-determinism property**
    (digest 동일성·hermetic·generation-fence, §7).
11. **bounds 주입 계약 + Phase-0 이관**(§8): IOC 모델 구조에는 numeric bound 부재(전부 enum·boolean·집합 논리·
    주입 `CanonicalDecimal`); ADR §28 q12가 요하는 수치(proof invalidation-to-egress·command age·proof age·
    capability-claim-to-first-byte 합성)는 **VERIFICATION-PROFILE-002에 전부 실재**(§8.1 실측: `B_order_conformance_
    invalid_to_egress` line 261·`MAX_canonical_broker_command_age_ms` line 713·`MAX_order_conformance_proof_age_ms`
    line 714·합성용 `B_capability_claim_to_send` line 163[ADR-002-007 소유]) + 3 scope-pin(policy id/generation/
    digest, line 55–57)이며 **candidate 신규 키 0건**(#10/#13형 "0 누락"; #12 4-key 누락과 대조). 값 승인은
    Bounds-Approver 게이트.

### 0.2 하지 않는 것 (경계·NO 목록)

- **ADR/스펙 비준·acceptance·restricted-live·production 어느 것도 승인하지 않는다.** ADR §29 line 735
  "ADR-002-020 remains `Proposed` until all applicable conditions pass"·line 752 "This ADR authorizes
  architecture and implementation-planning work only. It creates no live trading authority and makes no
  verification-completion or live-readiness claim." **닫는 IOC-EV = 0건.**
- **actual outbound 직렬화·서명·wire 비교를 저작하지 않는다.** §15(serializer/signer/mutation fence)·§17(final-
  egress actual-outbound 비교)의 **런타임 강제**는 **ADR-002-013 Broker Egress Gateway 소유**(§7 line 224·§17
  line 445). ADR §5.9 line 147 "Actual Outbound Representation"은 the final bytes/headers/routing로 **런타임
  산물**이다. Phase-1 IOC는 canonical command의 **모델과 conformance 술어**만 저작하며 직렬화·서명·egress
  강제를 하지 않는다(§15 line 415 "the serializer SHALL produce…"은 런타임). actual-outbound equivalence는
  proof의 digest 참조로만 표현.
- **Live Authorization·Transmission Capability·Commit Proof·전송을 저작하지 않는다.** §14 protocol line 397–399
  (Live Authorization / Transmission Capability / Commit Proof / final-egress verification)은 **ADR-002-007/013
  런타임**이다. IOC-INV-011 line 197 "Order construction cannot … issue authority … transmit, clear HALT, or
  re-arm." compiler는 non-authorizing이며 `OrderConformanceProof`는 결정 artifact이지 전송 permission이 아니다
  (§14 line 376 "`CONFORMANT` grants no approval or authority").
- **capacity 산술(commit/consume/release·serialize)을 저작하지 않는다.** 그것은 **rcl(#5, ADR-002-002/012)이
  이미 소유·구현**했다 — `CommittedReservation`·`grant_authorizes_exact_request`(`predicates.py:575`). ADR §7
  line 221 "proof cannot create or release capacity"·§13 line 341 "The Order Construction Service cannot mutate
  the RCL." IOC는 `EconomicEffectEnvelope`(`CapacityVector`)를 **생산**하고 rcl이 dominating vector를 commit한다.
  **단, envelope의 타입은 rcl `CapacityVector`를 REUSE**(§0.4c; IOC→rcl 1 edge)해 dominance를 타입 수준으로
  봉인한다 — commit/serialize는 여전히 rcl 소유.
- **aggregate risk projection·adverse scenario 평가를 저작하지 않는다.** 그것은 **are(#13, ADR-002-021)가 이미
  소유·구현**했다 — `AggregateRiskDecision`·`adverse_increment`·`risk_decision`. ADR §14 line 369 "ADR-002-021
  Aggregate Risk … Decision"·line 391 "ADR-002-021 Aggregate Risk Decision over the exact envelope." IOC는
  envelope를 **생산**하고 are가 그것을 평가한다(ARE §5.2 `exact_effect_snapshot_binding`이 "one exact current
  Economic Effect Envelope"를 binding — ARE #13 §5.2). IOC의 proof는 are decision을 digest scalar로 **binding**
  하되(§14 line 369) are를 import하지 않는다(are decision ref는 scalar, §3.4).
- **Independent Approval·immutable Intent Registration을 저작하지 않는다.** §14 protocol line 387 "Independent
  Approval + immutable Intent Registration"은 **ADR-002-023(IAP) 소유**(§29 line 748 "ADR-002-023 exact request/
  decision/consumption/Intent lineage binds the unchanged proposal, envelope, candidate command, venue decision,
  and construction generation"). IOC는 candidate command를 **construction**하고, approval/registration은 IAP가
  bind한다. dsl `Proposal` id 유도 scheme·§8 field set 확정이 dsl에서 **ADR-002-020/023으로 이연**됐고(dsl 설계
  line 571–572) — 본 문서는 **§8 field set(§5.1 `ApprovedIntentContract`) = -020 소유·approval/registration =
  -023 소유**로 분할한다(§3.5).
- **venue/session/tradability admissibility·Order Admissibility Decision을 저작하지 않는다.** ADR §4 non-scope
  line 102 "current venue/session/tradability admissibility, which remains ADR-002-019." IOC는 Order Admissibility
  Decision을 proof에 digest scalar로 **주입 소비**(§14 line 385)하되 admissibility를 평가하지 않는다.
- **broker capability·Final Quantity Proof semantics를 저작하지 않는다.** ADR §4 non-scope line 104 "broker
  capability and Final Quantity Proof semantics, which remain ADR-002-004." IOC는 brokercap `BrokerCapabilityProfile`
  (deterministic idempotency·replace semantics·broker default invariance)을 **주입 소비**(§12 line 319·§16 line
  431)하되 capability를 재정의하지 않는다.
- **canonical semantic FORM·numeric type·registry·numeric/invalidation bound를 승인하지 않는다.** ADR §4 non-scope
  line 108–109·§28 q1–q3·q12. canonical form은 `EVL1ProvisionalCanonicalizer` REUSE(잠정, §3.1); 프로덕션 canonical
  scheme·account/instrument/route/tick/lot/multiplier registry·수치는 **Phase-0 §9.2**. 값 부재 ⇒ fail-closed.

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

`tos.ioc` 모델은 다음만 import한다:

- 서드파티: `pydantic`(frozen 모델), `pytest`·`hypothesis`(테스트만). **`numpy`/`pandas`/`pyyaml`도 import하지
  않는다** — conformance 결정 규칙은 StrEnum·boolean·집합 논리이고 수치는 `CanonicalDecimal`(비교·`is_finite`·
  scale-normalize)·`CapacityVector`(rcl REUSE) 산술뿐이며, 모든 bound·mapping·registry·multiplier 값은 주입
  파라미터이고 YAML 파싱은 하네스(설계 #3) 소관이다(closure 최소화 — #5–#13 §0.3 동형).
- tos 자기 자신: `tos.canonical`(`FrozenModel`·`DigestBoundArtifact`·`IndependentIdArtifact`·**이미 core인
  `IdDerivedArtifact`**·`classify_record_pair`·`RecordPairKind`·`ArtifactStatus`·**이미 core인 `CanonicalDecimal`**·
  `EVL1ProvisionalCanonicalizer`), `tos.ordering`(Construction Generation append-only 순서 — §3.2), **`tos.rcl`
  (`CapacityVector` REUSE만 — §0.4c; 실측: rcl closure = canonical+ordering+self, 타 형제 미포함이라 ioc→rcl은
  clean edge)**, `tos.ioc.*`. **`tos.are`·`tos.dsl`·`tos.capsule`·`tos.orthostate`·`tos.brokercap`·`tos.spg`·
  `tos.liveauth`·`tos.authority`·`tos.time`·`tos.evidence`·`tos.protective`·`tos.recon`(12 형제)을 import하지
  않는다**(produced/consumed scalar·digest로만 참조 — §3.4/§3.5). **PROMOTE 0건. sibling edge 1건(ioc→rcl).**
- **`shared.config` 절대 금지**(설계 #1 §6.1, `.importlinter`): `shared.config.__init__`이 `shared.config.secrets`
  (→ `os.environ`)를 무조건 전이 import한다. `tos.ioc`는 어떤 `shared.*`도 필요로 하지 않는 순수 커널이다.
- **금지(직접·전이 모두)**: `shared.execution`, `shared.kis`, `shared.streaming`, `shared.llm`, `shared.storage`,
  `shared.backtest`, `services.*`, `cli.*`(`.importlinter` forbidden set 실측 line 35–43).
- **firewall 구조 확인(실측)**: `.importlinter`는 **`[importlinter:contract:tos-operational-firewall]` type=
  forbidden·source_modules=`tos`** 단일 계약이며(line 29–43 실측) `layered` 계약이 아니다 — intra-tos sibling→
  sibling edge는 구조적으로 금지되지 않고 설계 #1 §3.2의 "자기 자신 `tos.*`" 허용 조항이 이를 커버한다. **신규
  패키지 `tos.ioc`는 firewall 도구 무수정 자동 포섭**된다(forbidden 계약이 source=tos 전체를 덮으므로). **intra-tos
  sibling edge가 구조적으로 허용되므로 ioc→rcl(`CapacityVector` REUSE, §0.4c) edge는 firewall 위반이 아니다**
  (#13 are→rcl `orthostate/records.py:36`·#8 선례 동형). 그 외 seam은 produced/consumed scalar·digest(edge 0)로
  유지하는 것을 **설계 규율**로 삼는다(§0.4b; ioc의 전체 sibling edge는 ioc→rcl 1건).
- 이 배제를 능동 강제하는 것이 §7.1 import-closure 검증 테스트다(`import tos.ioc` closure에 금지·`shared.config`·
  `os.environ`·numpy/pandas/yaml·**12개 형제 tos 패키지**(rcl 제외) 부재 assert; **`tos.canonical`·`tos.ordering`·
  `tos.rcl`은 존재 허용**). required check(`tos-firewall`, `tools/tos_firewall_check.py` layer-① AST +
  `.importlinter` layer-② 전이 방어)와 함께 green이어야 성립.

### 0.4 REUSE / import / 경계 결정 요지 (핵심 아키텍처)

**(a) 패키지 위치·명명 = `tos/src/tos/ioc/`.** register domain(EVIDENCE-REGISTER-002 line 264) "**Intent-to-Order
Conformance**"·prefix `IOC`(`IOC-EV`/`IOC-AC`/`IOC-INV`)를 직접 명명. 명명 대안 비교(#13 §0.4a 형식):

- **`tos.command`(기각·collision+generic)**: `CanonicalBrokerCommand`가 중심이나 "command"는 지나치게 generic
  하고 **rcl `CommitReservation`의 command 개념**(`rcl/predicates.py:367` `command.proposed_adverse_increment`)과
  의미 충돌한다. register prefix `IOC`와도 어긋남. 하드 기각.
- **`tos.construction`(기각·부분)**: §9 compiler determinism만 포섭하고 **conformance(§10–§12)·economic-effect
  fencing(§13)을 누락**한다 — ADR 제목의 3축 중 1축만. verbose(12자)하고 register prefix와 불일치.
- **`tos.conformance`(runner-up·비관행)**: 오독 위험 0이고 §10–§12 conformance를 포섭하나, (i) **construction
  (§9)·economic fencing(§13)을 이름에서 누락**(제목의 1/3만), (ii) **verbose(11자)**로 terse 3-letter 관행
  (rcl/spg/dsl/are)과 어긋남, (iii) register prefix `IOC`와 불일치. **§10.2 판단 지점의 defensible 차선**.
- **선택(권장·주의) `tos.ioc`**: **register domain "Intent-to-Order Conformance"·prefix `IOC`**를 직접 명명,
  terse 3-letter로 `tos.rcl`/`tos.spg`/`tos.dsl`/`tos.are` 관행 정합, ADR 제목·EV/AC/INV 시리즈 전체와 1:1.
  **정직한 우려(금융 오독)**: 트레이딩 코드베이스에서 `ioc`는 **Immediate-Or-Cancel**(TIF order type)로 읽힐
  강한 위험이 있다 — 이는 #13의 `are`("상용어") 우려보다 **더 무겁다**(are는 영어 단어일 뿐이나 ioc는 이 도메인의
  실제 주문 용어). 완화: (i) **naming은 load-bearing이 아니다**(설계 #1 line 164 — 운영자 치환 가능), (ii)
  **register prefix가 authoritative**하며 다른 이름은 직접-명명 관행(#13)을 깨고 IOC-EV/AC/INV와의 1:1을 흐린다,
  (iii) **코드 토큰 충돌 0**(실측: tos 내 `ioc`/`conformance`/`command`/`construction` 디렉터리·토큰 부재), (iv)
  package docstring 1행("Intent-to-Order Conformance — **not** Immediate-Or-Cancel; ADR-002-020")으로 오독 봉합,
  (v) `ConformanceResult.IOC_*` 같은 접두 없이 `tos.ioc`는 module path이지 order-type 값이 아니다. **load-bearing은
  layering**(ioc → canonical·ordering·rcl[CapacityVector REUSE] 한 방향; are·dsl·capsule·orthostate·brokercap·
  spg·… 형제/상하류, **produced/consumed scalar·digest seam·edge 0**; rcl만 1 edge). **§10.2 운영자 판단 지점**:
  `tos.ioc`(register-prefix 충실·오독 우려) vs `tos.conformance`(오독 0·verbose·부분·prefix 불일치). 내부 module
  (`vocabulary.py`·`records.py`·`predicates.py`·`state.py`·`_base.py`)은 rcl/are/spg 선례 동형.

**(b) ioc = produced/consumed scalar·digest producer/consumer, sibling edge 1건(ioc→rcl `CapacityVector`만)
(중심 결정, 코드 실측).** IOC는 **dataflow상 dsl/capsule/orthostate/brokercap/venue의 하류**(proposal·capsule·
intent-identity·profile·admissibility 주입 소비)이자 **are/rcl/liveauth/egress의 상류**(envelope 생산·proof
생산). produced/consumed value seam은 전부 scalar·digest 주입(edge 0)이고, **유일한 package edge는
`EconomicEffectEnvelope` 타입 공유를 위한 ioc→rcl `CapacityVector` REUSE**다(§0.4c). **코드 실측 seam**(sibling
서사 아님 — #10 MAJOR 교훈):

| IOC 소비/생산 (§ref) | 타입 | 상대 (이미 비준·구현) | signature(실측) |
|---|---|---|---|
| dsl `Proposal` (immutable Intent proposal identity) 소비 | `str`(id)·`str`(digest) | dsl `Proposal`(`dsl/proposal.py:68`, `IdDerivedArtifact`·all-false authority·capsule bind) | `ApprovedIntentContract`가 `proposal_id`+`proposal_digest` scalar로 IOC-INV-001 binding; dsl이 §8 field set을 IOC로 이연(dsl 설계 line 571–572) |
| are `AggregateRiskDecision` 소비 | `str|None`·`int|None` | are `AggregateRiskDecision`(`are/records.py:451`, decision_id `494`/decision_generation `497`/canonical digest) | `OrderConformanceProof`가 decision content ref를 digest scalar로 binding(§14 line 369); are↛ioc(are는 scalar만 노출) |
| `EconomicEffectEnvelope` 생산 | `CapacityVector`(REUSE) | rcl `CapacityVector`(`rcl/vector.py:74`)·are MaximumCredibleCommandEffect 소비·rcl commit | are가 envelope를 projection 입력으로 소비(§14 line 389)·rcl `proposed_adverse_increment`(`records.py:185`)와 동일 타입으로 dominance(§13 line 341) |
| capsule `DecisionContextCapsule`·`CriticalInputSnapshot` 소비 | `str`(id)·`str`(digest) | capsule `DecisionContextCapsule`(`capsule/capsule.py:170`)·`CriticalInputSnapshot`(`snapshot.py:96`) | `ApprovedIntentContract`가 capsule/snapshot digest binding(§8 line 241); dsl `Proposal`이 이미 capsule bind(`proposal.py:90–91`) |
| orthostate `intent_identity`·attempt dimension 소비 | `str|None`(scalar) | orthostate `intent_identity`(`records.py:93`)·`IntentState`/`TransmissionAttemptState`(`vocabulary.py:32/61`) | retry/attempt lineage(IOC-INV-008)는 `intent_identity`+attempt id scalar 참조; orthostate가 state dimension 소유(전용 슬롯 아님·§3.4 (d)) |
| brokercap `BrokerCapabilityProfile` 소비 | `str`(id/version/digest)·injected `bool`/enum | brokercap `BrokerCapabilityProfile`(`records.py:305`)·`ProfileVersion`(`records.py:71`)·`ReplaceSemantics`/`AcknowledgementState`(`vocabulary.py:202/178`) | broker default invariance(§12 line 319)·idempotency(§16 line 431)는 injected capability result; profile digest binding |
| venue Order Admissibility Decision 소비 | `str`(id/digest) | ADR-002-019(형제·미구현 시 주입 slot) | `OrderConformanceProof`가 admissibility decision digest binding(§14 line 385·§17 line 446) |
| spg-governed `OrderConstructionPolicy` | `str`(id/generation/digest) | spg Safety Config Bundle governance(ADR-002-014) | policy는 spg-governed member(§7 line 217); IOC가 digest로 참조·spg가 거버넌스 |

**(c) `EconomicEffectEnvelope` = rcl `CapacityVector` REUSE 결정 (중심·#13 MAJOR-1 동형).** ADR §13 line 329–339가
economic effect를 **per-(scope,dimension) conservative vector**(position delta·notional·leverage·margin·
concentration·liquidity·basis·settlement·partial-fill prefix·zero-cross·reversal·overlap·broker rounding)로
정의하고, IOC-INV-005 line 173이 "The committed capacity dominates every credible effect in the command's Economic Effect
Envelope"를 요구한다. **dominance가 타입 수준으로 성립하려면 envelope와 committed vector가 동일 좌표**여야 한다.
`AdverseIncrement`의 타입 소유자는 ADR-002-002(rcl `CapacityVector`)이고(#13 §0.4c 판정·ADR-002-021 §2:47 "ADR-
002-020 defines the exact command and its Economic Effect Envelope" — envelope는 IOC 소유이나 그 **좌표 타입**은
capacity 좌표), are #13이 이미 `AdverseIncrement[s,d]=CapacityVector` REUSE했으며 are가 IOC envelope를
MaximumCredibleCommandEffect로 소비한다. ⇒ **`EconomicEffectEnvelope`는 rcl `CapacityVector`를 REUSE**(ioc→rcl 1
edge·**타입 수준 dominance 봉인**·별도 축약 reducer 불요)하고 dominance 술어 `economic_effect_dominated`는
`CapacityVector` within-limit(`effective_limit` REUSE) 위에서 순수 판정한다. **acyclic 실증**: rcl은 ioc를
import하지 않으므로(실측: rcl closure=canonical+ordering+self) ioc→rcl은 단일 방향 edge, cycle 아님. 선례: #13
are→rcl(`are` 설계 §0.4c 비준)·#8 orthostate→rcl(`orthostate/records.py:36`). **기각 대안**: (b) **IOC 자체 vector**
— dominance를 rcl 런타임에 이연하고 proof에 claimed-dominance `bool`을 실으면 (i) 존재하지 않는 축약 reducer의
under-count-0을 Phase-1 assert 불가(#13 MAJOR-1 실증), (ii) claimed `bool`은 **truthy-sentinel + under-realization
함정**(§4.7), (iii) ADR-002-002 소유 vector 타입 재정의 = 좌표 붕괴 위험. (c) **canonical PROMOTE** — 무거움(현재
rcl+are+ioc만 필요), 기각. **§10.2 운영자 판단 지점**: (a) REUSE(권장·채택) vs (b) 자체 vector(reducer+property를
Phase-1 명세해야 함·truthy-sentinel 위험). 완화: ADR §14 line 404 "the RCL independently commits a vector that
covers the envelope"가 rcl commit-time 독립 재검증(2차 게이트·common-mode 분리 §23)을 보장.

**(d) `IndependentIdArtifact` vs `IdDerivedArtifact` 혼합 (canonical REUSE).** policy·envelope·command·proof·intent는
**거버넌스/발급 identity ⊥ digest**를 가져 same-id/diff-bytes(위조·재발행·contradictory proof) 탐지에
`classify_record_pair`(`RecordPairKind.CRITICAL_CONFLICT`)를 써야 하므로 대부분 `IndependentIdArtifact`(id⊥digest)로
저작한다(#4–#13 §3.1 동형). **예외 — dsl `Proposal`은 `IdDerivedArtifact`(content-addressed, `id=f(digest)`,
`dsl/proposal.py:3–4` 실측)**이며 IOC는 이를 **재정의하지 않고 digest scalar로 참조**한다(dsl 소유). `ApprovedIntentContract`의
`id=f(digest)` 여부는 **§10.2 판단 지점**: (i) approval/registration identity(IAP -023)를 bind하면
`IndependentIdArtifact`(id⊥digest — 위조 탐지), (ii) 순수 content-addressed 파생이면 `IdDerivedArtifact`. 권장:
**`IndependentIdArtifact`**(§8 line 236 "immutable Intent identity, version, digest, issuer, approval" — issuer/
approval은 governance identity로 digest와 독립; 재발행/substitution 탐지 필요). 각 Construction Generation은
immutable append-only 레코드이며 정당한 재컴파일은 **새 generation**(§5.7)이지 in-place mutation이 아니다.

**(e) 형제/상하류 import·미import 근거(§3.5 소유권 분할 요지).**
- **`tos.rcl` — `CapacityVector`만 import(유일 sibling edge)**: rcl이 capacity 산술·commit·`grant_authorizes_
  exact_request`·`proposed_adverse_increment`를 소유. IOC는 `EconomicEffectEnvelope` **타입만** `CapacityVector`를
  REUSE하고(§0.4c) dominance를 순수 판정(commit는 rcl). rcl↛ioc 실측 acyclic.
- **`tos.dsl` 미import(Proposal 상류 — §8 이연 착지)**: dsl `Proposal`이 immutable Intent proposal이며 IOC는
  proposal_id/digest scalar로 IOC-INV-001 binding. dsl이 "§8 field set은 downstream(ADR-002-020)"이라 명시(dsl
  설계 line 572·`proposal.py:6–9` "an anchor, not a redefinition of ADR-002-020")했으므로 **IOC가 §8 field set의
  착지점**이다. IOC는 `ApprovedIntentContract`(§8)를 저작하되 Proposal을 import하지 않는다(digest 참조).
- **`tos.are` 미import(envelope 하류·decision 상류 = 상호 value-flow)**: are가 aggregate risk projection을 소유.
  IOC는 `EconomicEffectEnvelope`(CapacityVector) **생산**(are가 MaximumCredibleCommandEffect로 소비)하고 are
  decision을 **digest scalar로 소비**(proof binding). 양방향 value-flow지만 **양쪽 미import**(are는 CapacityVector를
  이미 REUSE·IOC도 REUSE — 공유 타입은 rcl edge로 획득)로 acyclic. are decision ref는 scalar(are `records.py:494/497`).
- **`tos.capsule`·`tos.orthostate` 미import(Intent 입력 상류)**: capsule `DecisionContextCapsule`·`CriticalInput
  Snapshot`은 `ApprovedIntentContract`의 주입 입력(§8 line 241·이미 dsl Proposal이 bind). orthostate `intent_
  identity`·attempt state는 lineage scalar 참조(전용 슬롯 아님·§3.4 (d) — 정직 state-의존).
- **`tos.brokercap` 미import(capability 상류)**: brokercap `BrokerCapabilityProfile`이 broker default invariance·
  idempotency·replace semantics를 소유. IOC는 injected capability result(bool/enum)·profile digest만 소비(§12
  line 319·§16 line 431).
- **`tos.spg`·`tos.liveauth`·`tos.authority`·`tos.time`·`tos.evidence`·`tos.protective`·`tos.recon` 미import**:
  spg가 OrderConstructionPolicy를 거버넌스(§7 line 217 — IOC는 policy digest 참조); liveauth/authority는 §14
  protocol 하류(런타임); time validity는 주입 opaque flag(IOC는 clock 미접근); evidence replay engine은 ADR-002-016
  하류; protective classification은 ADR-002-001(§19 IOC는 label이 envelope bypass 못 함만 술어화); recon은 무관.

**(f) 앵커 규약 — IOC-INV/AC/EV 앵커, 새 시리즈 창작 금지.** **실측**: ADR-002-020은 **자체 시리즈 `IOC-INV-
001..014`(§6 line 155–209, 14종)·`IOC-AC-001..012`(§26 line 645–691, 12종)·`IOC-EV-001..012`(register line
264–275, 12행)를 정의한다.** ⇒ 본 계약은 모델 불변식·술어를 **`IOC-INV-###` / `IOC-AC-###` / `IOC-EV-###` /
§-clause / `SAFE-###`(§27 traceability line 699–711)**에 앵커하고 **새 INV/AC/EV 시리즈를 창작하지 않는다**. 이는
#6/#8/#10/#12/#13이 자체 INV에 앵커한 것과 동형이다. self-consistency 최우선.

**(g) IOC-EV = #12형 core tier(6행) + truthy-sentinel 규율, 닫는 IOC-EV = 0건.** register 실측: **6행(001·002·
003·004·005·006)이 최소 레벨에 `EV-L1` 슬라이스 보유**(§1 표), 6행(007·008·009·010·011·012)은 최소 `EV-L2`. ⇒ §1
분류는 **core(L1 슬라이스 6) / predicate-only(6) / not-Phase-1 3분류**(#12형·orchestrator 사전 카운트 6과 일치·
정정 불요). **그러나 닫는 IOC-EV = 0건** — L1 슬라이스 저작은 EV closure가 아니다(`/3`·`+Security`·`+Broker`
통합·독립 리뷰 잔여). **truthy-sentinel 규율(#13 신규 교훈)**: `command_conforms`·`derived_command_conformance`는
`ConformanceResult`(CONFORMANT/NON_CONFORMANT/UNKNOWN)를 반환하고, `NON_CONFORMANT`/`UNKNOWN`가 truthy string이므로
**소비 게이트는 `result is ConformanceResult.CONFORMANT` 명시 비교**(truthy 금지)를 §4.7·§5에 계약으로 명문화한다.
이 판정은 §1·§4·§5·§7 전체에 **일관**해야 하며(어떤 §7 test-target도 IOC-EV closure를 주장하지 않음), finishing 전
self-consistency pass에서 대조한다.

---

## 1. 범위 매핑 — ADR-002-020 조항별 EV-L1 도달성 (닫는 IOC-EV 0건)

EV-level 정의(VER-002-001): **EV-L1 = Model and Property Verification**(state-machine exploration, model
checking, property-based testing, deterministic simulation). **EV-L2 = Component Fault Test**, **EV-L3 =
Integration/Adversarial**, **+Security = security enforcement**, **+Broker = broker-integration**. Phase 1은
EV-L1만이다.

> **결정적 사실 1 — IOC-EV ↔ IOC-AC 1:1, 최소 레벨 실측(사전 카운트 일치)**: `IOC-EV-001..012`(register line
> 264–275)는 ADR §26 `IOC-AC-001..012`(line 645–691)와 제목·번호가 **1:1**(§26 line 693 verbatim "Each case
> maps one-to-one to `IOC-EV-001` through `IOC-EV-012`"). register 최소 레벨 실측:
> **`EV-L1` 슬라이스 보유(6행)** = 001(`EV-L1/3+Broker` line 264)·002(`EV-L1/3+Security` 265)·003(`EV-L1/3`
> 266)·004(`EV-L1/3+Broker` 267)·005(`EV-L1/3+Broker` 268)·006(`EV-L1/3` 269); **`EV-L1` 슬라이스 부재(6행,
> 최소 ≥ L2)** = 007(`EV-L2/3+Security` 270)·008(`EV-L2/3+Security` 271)·009(`EV-L2/3+Broker` 272)·010(`EV-L2/3+
> Broker` 273)·011(`EV-L2/3+Security` 274)·012(`EV-L2/3+Security` 275). ⇒ **core tier 6행**(#12형; orchestrator
> 사전 "6"과 **일치**, #13의 6→5 정정과 달리 정정 불요), predicate-only substrate 6행.
>
> **결정적 사실 2 — authoring ≠ acceptance(닫는 IOC-EV = 0건)**: Phase 1은 각 IOC-EV의 **L1-decidable
> predicate/model substrate**를 저작하나 **어떤 IOC-EV도 닫지 않는다.** (a) core 6행조차 `/3`·`+Broker`(001/004/
> 005)·`+Security`(002) 잔여(fault injection·adversarial·broker 통합·security 강제)가 남고, (b) 6행은 최소 ≥ L2,
> (c) VER-002-001 §5 "Registration is not execution"·ADR §26 line 693 "Written cases are not completed evidence"·
> §29 line 746 item 10. ⇒ **"EV-L1-complete 주장 금지"**(#2–#13 §1 규율 상속). Owner/Reviewer는 register상 TBD.

**규율 태그(모든 주장에 부착)**: "**predicate/model substrate only; IOC-EV-001..012 전부 NOT_IMPLEMENTED — core
6행은 `/3`·`+Broker`·`+Security` 통합·독립 리뷰 대기, predicate-only 6행은 EV-L2/L3 fault injection·adversarial·
+Security·+Broker evidence 대기. EV-L1-complete 주장 금지.**"

**ADR-002-020 조항 → Phase-1 분류(core / predicate-only / not-Phase-1[형제 소유·런타임 이연])**:

| ADR 조항 | 요지 | Phase-1 분류 | L1 substrate / 소유 (근거) | IOC-EV |
|---|---|---|---|---|
| **§11** (line 290–305) | Direction/Side/Position-Effect 정합 | **core (L1 슬라이스)** | `command_conforms` direction/side/position-effect 축(§5.1) — IOC-INV-004. signed-quantity≠side(§11 line 301). `/3+Broker` 잔여. | **001** |
| **§10** (line 274–286) | Identity/Account/Instrument/Contract/Environment/Route 정합 | **core (L1 슬라이스)** | `command_conforms` identity 축(§5.1) — IOC-INV-003. alias=data not authority(§10 line 284). alias 실 registry는 Phase-0. `/3+Security` 잔여. | **002** |
| **§11 numeric** (line 296–301) | Unit/Multiplier/Currency/Scale/Numeric Safety | **core (L1 슬라이스)** | `command_conforms` numeric 축 + `numerical_safety`(§5.2) — IOC-INV-004. NaN/overflow/negative-zero⇒거부(CanonicalDecimal). `/3` 잔여. | **003** |
| **§11 quantity** (line 299–305) | Quantity/Tick/Lot/Rounding | **core (L1 슬라이스)** | `command_conforms` quantity 축 + `no_silent_widening`(§5.3) — IOC-INV-006. risk-reducing rounding fail-closed(§11 line 303). tick/lot registry는 Phase-0. `/3+Broker` 잔여. | **004** |
| **§12** (line 309–323) | Price/Order-Type/TIF/Expiration/Flags/Mode | **core (L1 슬라이스)** | `command_conforms` price/order/mode 축(§5.4) — IOC-INV-004. "more likely to fill" not safety(§12 line 321). broker default invariance는 주입 capability. `/3+Broker` 잔여. | **005** |
| **§13** (line 327–345) | Economic Effect Envelope + Capacity Dominance | **core (L1 슬라이스)** | `economic_effect_dominated`(CapacityVector, §5.5) — IOC-INV-005. compiler confidence/label이 envelope 축소 못 함(§13 line 343). scenario 값은 주입. `/3` 잔여. | **006** |
| **§14/§15 canonicalization** (line 349–424) | Canonicalization·Parser Differential | **predicate-only** | canonicalization determinism + duplicate/unknown-field 거부(§6.1) — IOC-INV-002. parser differential·byte/semantic digest는 EV-L2 component-fault·+Security. 최소 `EV-L2/3+Security`. | **007** |
| **§15/§17** (line 410–459) | Post-Proof Mutation·Actual-Outbound Equivalence | **predicate-only** | `mutation_fence_holds`(구조적 불변성, §6.2) — IOC-INV-007. actual-outbound 비교·serializer/signer 강제는 +Security 런타임(ADR-002-013). 최소 `EV-L2/3+Security`. | **008** |
| **§16** (line 427–437) | Retry/Cancel/Amend/Replace/Split/Aggregate | **predicate-only** | `derived_command_conformance`+no-blind-retry(§6.3) — IOC-INV-008. broker deterministic idempotency·replace semantics는 +Broker(ADR-002-004). 최소 `EV-L2/3+Broker`. | **009** |
| **§19** (line 479–487) | Protective/Exit Construction | **predicate-only** | `protective_creates_nothing`(§6.4) — label/urgency가 envelope/admissibility/capacity bypass 못 함(§19 line 481). partition/broker-alive는 런타임. 최소 `EV-L2/3+Broker`. | **010** |
| **§7/§23** (line 213–228·547–563) | Authority Separation·Compiler Drift·Bypass | **predicate-only** | `construction_grants_no_authority` all-false(§6.5) — IOC-INV-011. compiler↛live credential/route(§7 line 228)·bypass는 +Security 런타임. 최소 `EV-L2/3+Security`. | **011** |
| **§20/§21** (line 491–515) | Restart/Restore/Recovery/Replay/Non-Revival | **predicate-only** | `recovery_revives_nothing`·`economic_effect_outlives`(§6.6) — IOC-INV-012/013. Recovery Barrier(ADR-002-017)·re-arm 런타임. 최소 `EV-L2/3+Security`. | **012** |
| **§5/§8/§9** (line 113–150·232–271) | Definitions·Approved Intent·Construction Policy·Compiler Determinism | **core substrate(분산)** | 6-아티팩트 모델·`ConformanceResult` 어휘(§2)·compiler determinism property(§5.2). policy 값·mapping은 주입. | 001–006 공통 |
| **§9 canonical FORM·§15 serializer·§17 egress enforce·§23 verifier** | canonical semantic form·직렬화·서명·egress 강제·독립 verifier 런타임 | **not-Phase-1 (런타임 EV-L2/L3·+Security)** | 프로덕션 canonical scheme(§28 q1)·serializer/signer(§28 q5)·final-egress 강제(§28 q5·ADR-002-013)·independent reproduction(§28 q4·q10·§23). ioc는 순수 동등/순서/구조 검사만. | 007/008/011 (런타임) |
| **§14 Live Auth·capability·Commit Proof** | Live Authorization·Transmission Capability·Commit Proof·전송 | **not-Phase-1 (ADR-002-007/013)** | ioc는 결정 artifact만. 전송·capability는 런타임(§0.2). | 008/011 (런타임) |
| **§16 broker idempotency/replace semantics** | deterministic idempotency·atomic replace scope | **not-Phase-1 (ADR-002-004 brokercap 런타임)** | broker capability semantics는 brokercap+broker 통합(§28 q7). ioc는 injected capability result 소비만. | 009 (broker) |
| **§4 non-scope** (line 108–109) | canonical form·numeric type·registry·numeric/invalidation bound | **not-Phase-1 (Phase-0/INSTANCE)** | 제품·알고리즘·수치 선택은 §9.2 Phase-0. 전부 주입. | — |

---

## 2. 데이터 모델 계약

**표현 원칙**: 모든 아티팩트는 **pydantic v2 frozen 모델**(`ConfigDict(frozen=True, extra="forbid")`,
`tos.canonical.FrozenModel` REUSE)로 저작한다. `extra="forbid"`는 **§14 line 406 "Unknown fields, duplicate
semantic fields, alternate encodings … are rejection"·§9 line 263 "duplicate-field rejection, unknown-field
handling"의 스키마 수준 실현**이다(unknown/duplicate 차단). 모든 multiplier·price scale·quantity·limit은 **주입
`CanonicalDecimal|None`**(하드코딩 수치 0), economic effect vector는 **rcl `CapacityVector` REUSE**(§0.4c).

### 2.0 소유권 골격 — ioc는 canonical의 하류, dsl/capsule/orthostate/brokercap/venue의 하류, are/rcl/egress의 상류

`tos.ioc`는 `tos.canonical`·`tos.ordering`(둘 다 core) + `tos.rcl`(`CapacityVector` 1 edge)만 import한다.
dataflow상 ioc는 **dsl `Proposal`·capsule·orthostate·brokercap·venue의 하류**(proposal/capsule/intent-identity/
profile/admissibility 주입 소비)이자 **are·rcl·liveauth·egress의 상류**(`EconomicEffectEnvelope` 생산·
`OrderConformanceProof` 생산). produced/consumed seam은 **scalar·digest 주입(edge 0)**으로 실현되고, **유일 package
edge는 `EconomicEffectEnvelope` 타입 공유를 위한 ioc→rcl `CapacityVector` REUSE**다(§0.4c; rcl↛ioc acyclic).

### 2.1 digest-bound / value / reference 분류 (총괄)

| 모델 | 분류 | 근거 |
|---|---|---|
| `ApprovedIntentContract`(§5.1/§8) | **digest-bound `IndependentIdArtifact`**(§0.4d 판단 지점) | §8 line 236 "immutable Intent identity, version, digest, issuer, approval"; issuer/approval=governance identity ⊥ digest(재발행·substitution 탐지). dsl `Proposal` digest를 IOC-INV-001로 binding. |
| `AuthorizedConstructionEnvelope`(§5.3/§8) | **digest-bound `IndependentIdArtifact`** | §5.3 line 125 "An absent or open-ended envelope permits no construction"; §8 line 243 "envelope identity/digest". closed set·permitted transformation. **부재/open ⇒ construction 불가**(§4.7). |
| `OrderConstructionPolicy`(§5.2/§9) | **digest-bound `IndependentIdArtifact`(spg-governed)** | §5.2 line 121 "immutable, authenticated, separately governed artifact"; §7 line 217 spg governance. IOC가 digest 참조·spg 소유. |
| `CanonicalBrokerCommand`(§5.4/§14) | **digest-bound `IndependentIdArtifact`** | §5.4 line 129 "one canonical representation and digest, complete field presence, explicit units and defaults, exact proposal lineage"; §14 line 353 "command identity … and digest". command_id ⊥ canonical digest(same-id/diff-bytes 탐지). **non-authorizing flags 명시**(§5.4 line 129·§14 line 359). |
| `EconomicEffectEnvelope`(§5.5/§13) | **REUSE rcl `CapacityVector`** | §13 line 329–339 per-(scope,dimension) conservative vector; ADR-002-002 소유 타입 REUSE(§0.4c; ioc→rcl edge). dominance=within-limit. |
| `OrderConformanceProof`(§5.6/§14) | **digest-bound `IndependentIdArtifact`** | §5.6 line 137 "immutable non-authorizing artifact"; §14 line 365 "proof … deterministic input and output digests"·line 372 result. are decision·rcl commitment·venue·brokercap ref는 digest scalar. |
| `ConstructionGeneration`(§5.7) | **REUSE `tos.ordering`** | §5.7 line 141 "A monotonic restrictive generation … A newer restrictive generation fences older unconsumed proofs". `Ordering`/`compare_order`. |
| `OrderConstructionAuthorityEffect`(§7/IOC-INV-011) | **plain-frozen all-false** | rcl `RclAuthorityEffect`(`authority.py:19–36`)·are `AggregateRiskAuthorityEffect`(`are/records.py:83`) 동형; 어떤 True도 unconstructable(compiler≠authority, §7 line 219·IOC-INV-011). |
| `MaterialCommandChange`(§5.8) | **plain-frozen value** | §5.8 line 145 "Unknown materiality is material" ⇒ 미상 materiality ⇒ material(fail-closed §4). |
| `ConformanceResult`/`ConformanceAxis`/`MutationClass`/`OrderTypeKind`/`QuantityUnitKind`/`PositionEffectKind` | **StrEnum(어휘)** | §2.2 verbatim. |

> **핵심 설계 결정 — 아티팩트는 immutable generation별 append-only(#10/#12/#13 상속)**: Policy/Envelope/Command/
> Proof는 시간에 따라 **재컴파일·재발행**된다(§5.7 Construction Generation·§21 recovery→fresh command/proof).
> 하나의 stable id에 mutable 내용을 담으면 정당한 재컴파일이 same-id/diff-bytes `CRITICAL_CONFLICT`로 **오탐**
> 된다. ⇒ **각 generation은 fresh id를 가진 immutable 레코드**다. same identity + diff canonical digest ⇒
> `CRITICAL_CONFLICT`(위조·contradictory proof만); 정당한 재컴파일 ⇒ **새 generation**. generation 순서는
> `tos.ordering`(§3.2). **command·proof는 forward-only**: 미래 Live Authorization/capability identity를 covered에
> 담지 않는다(§14 line 402 "No downstream artifact is permitted to rewrite the candidate"·non-cyclic).

### 2.2 어휘 (verbatim 전사 — 에라타 defect class 주의)

**(1) `ConformanceResult`** — ADR §14 line 372 verbatim "final result `CONFORMANT` or `NON_CONFORMANT`/`UNKNOWN`".
3종: `CONFORMANT`("grants no approval or authority … usable only as one current input", §14 line 376)·`NON_
CONFORMANT`·`UNKNOWN`. **`CONFORMANT`만 안전 통과값**이며 `NON_CONFORMANT`/`UNKNOWN`는 **모두 denial**(§14 line
374 "makes the proof `UNKNOWN` or `NON_CONFORMANT` and blocks authority issuance and transmission"). **truthy-
sentinel 임계(§0.4g/§4.7)**: 셋 다 non-empty StrEnum이라 `if result:`면 `NON_CONFORMANT`/`UNKNOWN`가 truthy로
**fail-open** — **구조적 봉인(v1.1 M1 채택)**: `ConformanceResult.__bool__`는 **`TypeError`를 raise**한다
(truthy-불가 타입 — `if result:`/`bool(result)` = 런타임 오류, 침묵 fail-open 원천 제거). 소비 게이트는
**`result is ConformanceResult.CONFORMANT` 명시 비교**(보조 계약).

**(2) `ConformanceAxis`** — §10 line 274–282·§11 line 292–299·§12 line 311–317 verbatim 축을 어휘 값으로(구조적
axis만; 실 registry 값은 주입): `ENVIRONMENT`·`LIVE_NONLIVE`·`BROKER`·`API_PRODUCT_VERSION`·`ACCOUNT`·`SUBACCOUNT`·
`PORTFOLIO`·`CUSTODY`·`VENUE`·`MARKET_SEGMENT`·`BOARD`·`ROUTE`·`ENDPOINT`·`SESSION_FAMILY`·`INSTRUMENT`·`BROKER_
SYMBOL`·`CONTRACT_MONTH`·`OPTION_SERIES`·`PRODUCT`·`SETTLEMENT`·`ACTION_CLASS`·`DIRECTION`·`SIDE`·`POSITION_EFFECT`·
`QUANTITY`·`UNIT`·`MULTIPLIER`·`CURRENCY`·`PRICE_SCALE`·`SIGN`·`PRICE`·`TRIGGER`·`ORDER_TYPE`·`TIF`·`EXPIRATION`·
`ROUTE_FLAGS`·`REDUCE_ONLY`·`POST_ONLY`·`MODE`. **cross-axis 변환(currency/multiplier/tick)은 explicit·policy-
bound**(§10 line 284 "must be policy-bound and produce one unambiguous mapping"·§11 line 301). **주의(에라타 봉합)**:
이 axis 목록은 ADR §10–§12의 **구조적 축**이며 구체 per-broker registry 값·mapping은 Phase-0(§28 q3)이다 — axis를
하드 registry 값과 혼동 금지.

**(3) `PositionEffectKind`** — §11 line 294–296 verbatim: `OPEN`·`CLOSE`·`REDUCE_ONLY`. §11 line 301 "Signed
quantity alone is insufficient when broker side and position effect are separate fields." ⇒ signed quantity가
side를 silent flip 못 함(§5.1 canary).

**(4) `OrderTypeKind`** — §12 line 313 verbatim "market, limit, stop, stop-limit, peg, auction, discretionary,
conditional, and broker-specific order type": `MARKET`·`LIMIT`·`STOP`·`STOP_LIMIT`·`PEG`·`AUCTION`·`DISCRETIONARY`·
`CONDITIONAL`·`BROKER_SPECIFIC`. price improvement/더 aggressive price/longer expiration/broader route는 **material
change**(§12 line 321 "'More likely to fill' is not a safety justification").

**(5) `QuantityUnitKind`** — §11 line 297 verbatim "shares, lots, contracts, base/quote units, nominal/notional,
face value, and fractional units": `SHARES`·`LOTS`·`CONTRACTS`·`BASE_UNIT`·`QUOTE_UNIT`·`NOMINAL`·`NOTIONAL`·`FACE_
VALUE`·`FRACTIONAL`. `abs`/clamp/cast/truncation/binary-float/scientific-notation/unitless transport 금지(§11 line
301) unless policy-approved.

**(6) `MutationClass`** — §16 line 427–437 앵커(v1.1 m1: `NEW`·`SPLIT_CHILD`는 설계 파생, exercise류는
IOC-INV-008·Decision §1 앵커 — "verbatim" 아님): `NEW`·`RETRY`·`CANCEL`·`AMEND`·`REPLACE`·`SPLIT_CHILD`·
`AGGREGATE`·`EXERCISE`. "Every broker mutation has its own command identity and proof"(§16 line 429). Aggregation은
default denied(§16 line 437·§24.8).

**(7) 좌표 어휘(비붕괴, §2.3)**: ioc `ConformanceAxis`(conformance 축) ≠ rcl `DimensionDescriptor`(capacity 축,
`vector.py:39`) ≠ are `RiskDimensionKind`(risk 축) ≠ brokercap `CapabilityDimension`(broker 축, `vocabulary.py:58`)
≠ orthostate `StateDimension`(state 축). 토큰 겹칠 수 있으나(예: "instrument", "account") **별개 타입**이다. **단
`EconomicEffectEnvelope`는 rcl `CapacityVector`를 REUSE**(§0.4c — 의도적 단일 타입, dominance 좌표 붕괴 방지).

### 2.3 아티팩트 covered + self-exclusion (설계 #4 §3.3 상속)

covered(digest preimage) = 각 아티팩트의 구조적 identity/scope/version/generation/class + (Command) 전 broker
mutation 필드의 semantic-type/unit/presence/value + (Proof) policy/envelope/command/effect/decision **digest
scalar** + 축별 conformance 결과. preimage 제외: `*_id`·`canonical_digest`·`canonicalization_version`·`status`
(ArtifactStatus)·`*_generation` placement·파생 역참조. **`_REQUIRED_COVERED`는 structural identity/scope/version/
class + 필수 축 presence만**(numeric magnitude 제외 — Phase-1 null bound에서 ISSUED 도달 가능; missing magnitude는
consuming 술어에서 fail-closed, #12/#13 §2.3 규율 상속). **command·proof는 covered에 미래 Live Auth/capability/
Commit Proof identity를 담지 않는다**(§14 line 402 non-cyclic — candidate는 approval/venue/capacity/authority를
require하지 않고 grant하지 않는다).

---

## 3. canonical / ordering REUSE + rcl `CapacityVector` 1 edge + 형제 경계

### 3.1 canonical REUSE + `IdDerivedArtifact` 미채택(대부분)

6-아티팩트는 `tos.canonical.IndependentIdArtifact`·`DigestBoundArtifact`를 REUSE한다(dsl `Proposal`은 이미
`IdDerivedArtifact`, IOC는 digest 참조만). canonicalizer는 `tos.canonical` registry + `EVL1ProvisionalCanonicalizer`
(`ev-l1-provisional-0`) REUSE, **신규 canonicalizer 없음**(프로덕션 canonical semantic form은 Phase-0 §9.2 — ADR
§28 q1). multiplier·price scale·quantity·limit은 **이미 core인 `CanonicalDecimal`** REUSE(§11 line 296 "exact
decimal"·§14 line 423 "numeric exponent variants … negative zero … SHALL fail closed"·NaN/infinity 구성-거부).
**PROMOTE = 0건**.

### 3.2 ordering REUSE (Construction Generation append-only 순서)

Construction Generation(§5.7 line 141 "A monotonic restrictive generation")의 append-only 순서는 신규 저작하지
않고 `tos.ordering`(`Ordering`·`OrderingEvent`·`compare_order`, `tos.canonical`만 의존)를 REUSE한다. **wall clock은
순서를 만들지 않는다**(§9 line 268 "Hidden clock reads … are prohibited"·§17 line 459 "Cached `CONFORMANT` … is
not current conformance proof"와 정합) — ioc는 clock을 읽지 않는다(§3.5; time validity는 주입 flag). newer
restrictive generation이 older unconsumed proof를 fence(§5.7 line 141)하는 것은 순수 순서 비교이며 fence
enforcement 런타임(profile bound)은 not-Phase-1. light REUSE(core 의존, 신규 edge 아님).

### 3.3 REUSE 요약 표

| substrate | 결정 | 근거 |
|---|---|---|
| `FrozenModel`·`DigestBoundArtifact`·`IndependentIdArtifact`·`ArtifactStatus` | **REUSE(core `tos.canonical`)** | §3.1; 신규 없음 |
| `classify_record_pair`·`RecordPairKind` | **REUSE(core)** | §3.1; same-id/diff-bytes·contradictory proof |
| `CanonicalDecimal` | **REUSE(core, #9 PROMOTE됨)** | §3.1; multiplier·price·quantity·NaN/negative-zero 구성-거부 |
| `EVL1ProvisionalCanonicalizer` | **REUSE(core)** | §3.1; 프로덕션 canonical form은 Phase-0(§28 q1) |
| `Ordering`·`OrderingEvent`·`compare_order` | **REUSE(core `tos.ordering`)** | §3.2; Construction Generation 순서·fence |
| rcl `CapacityVector`(`vector.py:74`) | **REUSE(ioc→rcl 1 edge; `EconomicEffectEnvelope`)** | §0.4c; ADR-002-002 소유 타입·rcl↛ioc acyclic·#13 are→rcl 선례·타입 수준 dominance |
| 6-아티팩트·all-false authority·어휘·10 conformance 술어 | **로컬 저작** | §0.4a/§2; ADR §5–§21 verbatim·construction-side |
| dsl `Proposal`·are decision·capsule·orthostate intent-id·brokercap profile·venue admissibility·spg policy | **미소유 — scalar/digest로만 소비/생산** | §3.4; 7 형제 seam |
| capacity commit/serialize·aggregate risk projection·approval/registration·serializer/signer·final egress·numeric bound | **미소유 — rcl/are/IAP/런타임/INSTANCE 이연** | §3.5 |
| PROMOTE | **0건** | §3.1 |
| sibling edge | **1건(ioc→rcl, `CapacityVector`)** | §3.4; #13 are→rcl 선례 동형 |

### 3.4 dsl / are / rcl / capsule / orthostate / brokercap / venue 경계 — scalar·digest seam(edge 0) + ioc→rcl 1 edge (중심, 코드 실측)

**(a) ioc = scalar/digest producer/consumer(§0.4b).** ioc는 7 형제를 (rcl 제외) **import하지 않고**, 그들과
**scalar·digest**로 seam한다. seam 계약(compose) — **상대는 전부 이미 비준·구현됨**(venue=ADR-002-019 미구현 시
주입 slot). 핵심 seam:

- **dsl(§8 field set 착지·상류)**: ioc `ApprovedIntentContract`가 dsl `Proposal`을 `proposal_id`+`proposal_digest`
  scalar로 IOC-INV-001 binding(§14 line 354 "exact immutable Intent proposal … references"). dsl `Proposal`
  (`proposal.py:68`)은 이미 account/instrument/direction/position_effect/quantity_basis + capsule bind(`90–91`)를
  carry하며 "an anchor, not a redefinition of ADR-002-020 … field set remains provisional/downstream"(`proposal.py:
  6–9`)라 명시 — **IOC가 §8 field set의 착지점**(dsl 설계 line 572). ioc는 Proposal을 import하지 않는다(digest
  참조).
- **are(§14 line 369 decision binding·상호)**: ioc `OrderConformanceProof`가 are `AggregateRiskDecision`을
  `decision_id`(`are/records.py:494`)/`decision_generation`(`497`)/canonical digest scalar로 binding. **동시에**
  ioc는 `EconomicEffectEnvelope`(CapacityVector)를 **생산**하고 are가 그것을 MaximumCredibleCommandEffect projection
  입력으로 소비(ARE #13 §5.2 "one exact current Economic Effect Envelope" binding). **양쪽 미import**(are decision
  ref는 scalar·envelope는 공유 CapacityVector 타입)라 acyclic.
- **rcl(§13 dominance·유일 edge)**: ioc가 `EconomicEffectEnvelope`=rcl `CapacityVector`로 생산 → rcl이
  `proposed_adverse_increment`(`records.py:185`)와 **동일 타입**으로 commit하고 dominating vector로 covers(§14 line
  404). ioc `economic_effect_dominated`는 within-limit 순수 판정(commit는 rcl `grant_authorizes_exact_request`
  `predicates.py:575`). **이것이 §13 dominance의 타입 수준 실현**(별도 축약 reducer 불요, §0.4c). rcl↛ioc 실측
  acyclic(rcl closure=canonical+ordering+self).
- **capsule/orthostate(Intent 입력 상류·state)**: ioc `ApprovedIntentContract`가 capsule `DecisionContextCapsule`
  (`capsule.py:170`)·`CriticalInputSnapshot`(`snapshot.py:96`) digest를 binding(§8 line 241; dsl Proposal이 이미
  bind). orthostate `intent_identity`(`records.py:93`)·`IntentState`/`TransmissionAttemptState`(`vocabulary.py:32/
  61`)는 retry/attempt lineage scalar 참조(IOC-INV-008) — **전용 슬롯 부재·문서화된 state 의존**(§3.4 (d), #13
  동형).
- **brokercap(capability 상류)**: ioc가 broker default invariance(§12 line 319 "current in the Broker Capability
  Profile")·deterministic idempotency(§16 line 431)를 **injected capability result(bool/enum)**로 소비하고 profile
  `ProfileVersion`(`records.py:71`) digest를 binding. brokercap `CapabilityDeclaration`(`records.py:90`)·`Replace
  Semantics`(`vocabulary.py:202`)는 brokercap 소유.
- **venue(§14 admissibility 상류)**: ioc `OrderConformanceProof`가 Order Admissibility Decision(ADR-002-019) digest를
  binding(§14 line 385·§17 line 446). ADR-002-019 미구현이면 주입 slot(scalar).

**(b) 타입 정합 + fail-closed 정합 + truthy-sentinel 봉합.** ioc 소비 signature는 전부 `str|None`(digest)·`bool|
None`(injected capability)·`CanonicalDecimal|None`(magnitude)이라 `None`⇒fail-closed. ioc 산출 `ConformanceResult`는
`CONFORMANT`만 안전값 — **소비 게이트는 `is CONFORMANT` 명시 비교**(§4.7). **polarity 봉합(#6 fail-open REJECT
교훈)**: producer는 결코 "미판정 ⇒ CONFORMANT/True/작은 vector"로 새지 않는다(§4.1/§4.3). **truthy-sentinel 봉합
(#13 교훈)**: `ConformanceResult` 반환 술어의 소비 계약은 `if result:` 금지·`is CONFORMANT` 명시.

**(c) composition(런타임 배선) = caller 소관**: ioc envelope/proof를 are/rcl/final-egress로 배선하는 **런타임**은
**미래 Construction Service / Egress Gateway 런타임**(EV-L3)이 한다. Phase 1은 #11/#12/#13의 seam 이연과 **동형으로
런타임 배선을 이연**한다.

**(d) seam cross-check = MANDATED(test-only)**: Phase 1은 **test-only** 모듈(`tos/tests/ioc/test_seam_rcl.py`·
`test_seam_are.py`·`test_seam_dsl.py`)에서 ioc·(각 상대)를 **둘 다 import**해 ioc 산출의 **타입·polarity·fail-
closed**가 상대 signature 기대와 **일치함을 assert**한다(예: ioc `EconomicEffectEnvelope` `CapacityVector` 좌표 =
rcl `proposed_adverse_increment` 좌표; ioc proof decision ref = are `AggregateRiskDecision` scalar; ioc
`ApprovedIntentContract` proposal ref = dsl `Proposal` `proposal_id`/digest). **이 테스트는 package edge가 아니다**
— 테스트 import는 §7.1 `import tos.ioc` package-closure에 **계상되지 않으므로** dsl/are/capsule/orthostate/
brokercap seam의 edge-0은 유지된다(#11/#12/#13 동형). **dominance는 타입 수준**(ioc `EconomicEffectEnvelope`가 rcl
`CapacityVector` REUSE) — seam test는 좌표 일치(ioc 생산 = rcl 소비 타입)만 회귀.

**(e) ioc는 mutate/transmit/issue/approve하지 않는다(§7 line 219·IOC-INV-011).** ioc는 결정 artifact(command·
proof·envelope)만 생산하고 capacity mutation·egress transmit·capability issue·approval·live-scope set 메서드가
**부재**하다(§4.6). 소비 authority(rcl serialize·are decision·IAP approval·final egress)가 실제 action을 gate한다.

**(f) acyclic(정확형)**: ioc→rcl 단일 edge(rcl↛ioc 실측)이며 ioc↛{are,dsl,capsule,orthostate,brokercap,spg,venue}
∧ 그들↛ioc(are/dsl은 상호 value-flow지만 양쪽 미import — 공유 CapacityVector는 rcl edge로 획득, decision/proposal은
scalar). "package edge 어느 방향이든 cycle"은 오류(단일 방향 edge는 import-graph cycle이 아님) — ioc→rcl은 허용
단일 edge(#13 are→rcl 선례).

### 3.5 소유권 분할표 — ioc가 소유 / 형제에서 소비·생산 (본 문서 최대 함정 지대, #11/#12/#13 §3.5 상속)

> **소유권 분할 명시(#8·#11·#12·#13 교훈 — cross-section 혼동 선제 봉합)**: ADR-002-020은 **approved Intent와
> broker command 사이의 deterministic compiler + conformance proof**만 결정하며(§4 line 87–96) capacity
> serialization(rcl)·aggregate risk projection(are)·approval/registration(IAP -023)·venue admissibility(ADR-002-
> 019)·broker capability(ADR-002-004)·serializer/signer/final-egress 강제(ADR-002-013)를 **소유하지 않는다**.
> 함정: ioc가 rcl의 capacity commit·are의 risk decision·IAP의 approval·venue의 admissibility·brokercap의
> capability를 재저작하면 권위 중복(#8 lesson). 아래 표가 경계를 코드 실측으로 고정한다.

| ADR 조항/개념 | ioc 소유 (Phase 1) | 형제 소유 (재저작 금지) | seam 방향(실측) |
|---|---|---|---|
| §8 Approved Intent field set | `ApprovedIntentContract`(§5.1) — dsl 이연 착지 | dsl `Proposal` identity(`proposal.py:68`, IdDerived)·IAP approval/registration(ADR-002-023) | dsl `Proposal` proposal_id/digest → ioc binding(IOC-INV-001); approval은 IAP(§14 line 387) |
| §9 compiler determinism | `compiler_deterministic` property·`OrderConstructionPolicy` 모델(§5.2) | spg policy governance(ADR-002-014 `SafetyConfigBundle`)·프로덕션 canonical form(Phase-0) | policy digest → ioc 참조; 거버넌스는 spg(§7 line 217) |
| §10–§12 conformance | `command_conforms`·`CanonicalBrokerCommand` 모델·`ConformanceResult`(§5.1/§5.4) | account/instrument/route/tick/lot/multiplier registry(Phase-0 §28 q3)·broker default(brokercap) | registry 값·capability는 주입; ioc는 순수 축 비교 |
| §13 economic effect + dominance | `EconomicEffectEnvelope`=rcl `CapacityVector` REUSE·`economic_effect_dominated`(§5.5/§0.4c) | rcl commit/serialize(`grant_authorizes_exact_request` `predicates.py:575`)·are projection(`adverse_increment`) | ioc가 `CapacityVector` 생산 → are 소비(MaxCredibleEffect)·rcl commit(`proposed_adverse_increment` `records.py:185`) |
| §14 proof binding | `OrderConformanceProof`(§5.6) — are decision·rcl commitment·venue·brokercap digest ref | are `AggregateRiskDecision`(`records.py:451`)·rcl commitment·venue admissibility·brokercap profile | 전부 digest scalar → ioc proof binding(§14 line 369); ioc는 상대 미import |
| §15 serializer/signer/mutation fence | `mutation_fence_holds` 구조적 불변성 술어(§6.2) | serializer/signer 강제·actual-outbound 비교(ADR-002-013 Egress Gateway) | ioc 순수 술어; actual-outbound 강제는 런타임(§17) |
| §16 retry/amend/replace lineage | `derived_command_conformance`·`MutationClass`(§6.3) | broker deterministic idempotency·replace semantics(brokercap `ReplaceSemantics` `vocabulary.py:202`) | ioc 순수 lineage 술어 + injected idempotency capability |
| §17 final-egress verification | (술어 계약만) | final egress 실 강제·capability claim·SEND_STARTED(ADR-002-013/007) | ioc는 proof 산출; egress 강제·claim은 런타임 |
| §19 protective construction | `protective_creates_nothing`(§6.4) | protective classification(ADR-002-001 `protective`)·degraded lease(ADR-002-002) | ioc는 label≠bypass 술어; classification은 protective |
| §7/§23 authority separation | `OrderConstructionAuthorityEffect` all-false(§6.5) | rcl `RclAuthorityEffect`·final egress confinement(ADR-002-013) | ioc all-false 생산; credential/route confinement 런타임 |
| §20/§21 recovery/non-revival | `recovery_revives_nothing`·`economic_effect_outlives`(§6.6) | ADR-002-017 Recovery Barrier·re-arm workflow(런타임) | ioc 술어; barrier enforce 런타임 |
| orthostate Intent/Attempt | (intent_identity/attempt scalar 참조) | orthostate `IntentState`/`TransmissionAttemptState` 전이(`vocabulary.py:32/61`) | 전용 슬롯 부재 — 문서화된 state 의존(§3.4 (d)) |

---

## 4. 불변식

모두 frozen 모델 구성-불변식(구성 실패) 또는 순수 술어(property)로 실현한다. **앵커는 IOC-INV-001..014(§6)·
IOC-AC-001..012(§26)·§-clause·SAFE-###**이며 **새 시리즈를 창작하지 않는다**(§0.4f). **fail-closed discipline**:
미증명/불일치/None/stale/unknown에 대한 술어는 절대 vacuous permissive/CONFORMANT/작은 vector가 되지 않으며, live
통과는 *양성 증명*을 요구하고, 각 가드에 **both-ways canary**(가드가 실제로 발화함 + 정당 통과를 막지 않음)를 붙인다.

### 4.1 intent-command conformance 중앙 불변식 (중앙 — ADR §10–§12; IOC-INV-003/004; IOC-AC-001/002/003/004/005)

**중앙 결정**: `command_conforms`는 §10–§12 전 축이 authorized envelope 안에서 **정확 일치**할 때만 `CONFORMANT`.
IOC-INV-003 line 165 verbatim "cannot be defaulted, aliased, or substituted outside the authorized envelope";
IOC-INV-004 line 169 "explicit and proven without lossy or ambiguous coercion". 실현(구조적):

1. **permissive 기본값 부재**: 오직 **모든 §10–§12 축이 present ∧ envelope-member ∧ 정확 일치**일 때만
   `CONFORMANT`. 한 축이라도 absent/alias/default/ambiguous/unknown ⇒ `NON_CONFORMANT`/`UNKNOWN`(§10 line 284
   "One-to-many or many-to-one ambiguity is denial"). "assume-match" 경로 부재(#6 fail-open REJECT 교훈).
2. **signed-quantity≠side**: "Signed quantity alone is insufficient when broker side and position effect are
   separate fields. A negative value cannot silently flip a side"(§11 line 301). ⇒ direction·side·position_effect는
   **독립 축**으로 각각 일치 검사(§5.1).
3. **alias=data not authority(§10 line 284)**: alias/default-account/"primary"-venue/front-month/case-fold/
   Unicode-normalize/suffix는 **policy-bound하여 one unambiguous mapping**일 때만 통과; 실 registry는 주입(Phase-0).
   미해결 mapping ⇒ `UNKNOWN`.

**canary(both-ways)**: (a) buy↔sell·open↔close·long↔short invert(IOC-AC-001)·default-account/symbol-alias/contract-
month/venue substitute(IOC-AC-002) ⇒ `NON_CONFORMANT`(가드 발화; §26 IOC-AC-001 "Every unintended effect must be
rejected"); 빈 축 집합 ⇒ `NON_CONFORMANT`(§4.7); (b) 전 축 present·envelope-member·정확 일치 ⇒ `CONFORMANT`(양성
side — 정당한 command를 막지 않음). **truthy-sentinel canary**: `NON_CONFORMANT`/`UNKNOWN`가 truthy임을 assert +
`is CONFORMANT` 게이트가 이를 reject함을 assert(§4.7).

### 4.2 compiler determinism 중앙 property (ADR §9; IOC-INV-002; IOC-EV-003/007 substrate)

**중앙 결정**(v1.1 NIT: digest-equality 하위 property 자체는 순수 함수의 near-tautology — 실제 load-bearing은
**hermetic**[clock/network 부재]·**denial-is-total**[fallback 부재]·**generation-fence**다): IOC-INV-002 line 161
verbatim "The same complete approved inputs and Construction
Generation produce the same canonical semantic command and digest, or construction fails." 실현(property):

1. **digest 동일성**: `compile(intent, policy, envelope, generation) -> command`는 순수 함수 — `compile(x)`를 두
   번 호출하면 **동일 canonical command + 동일 canonical digest**(byte-for-byte canonical form). hypothesis
   property: 무작위 valid 입력 x에 대해 `compile(x).canonical_digest == compile(x).canonical_digest`.
2. **hidden-input 부재(§9 line 268)**: verbatim "Hidden clock reads, randomness, locale, environment variables,
   mutable caches, unordered map iteration, platform floating-point variation, network lookup, 'latest' registry
   reads, or broker SDK implicit defaults are prohibited unless their exact value is already bound and
   canonicalized." ⇒ hermetic test(clock/network 부재)·`CanonicalDecimal`(float 배제)·정렬된 iteration.
3. **denial-is-total(§9 line 270)**: "Construction failure is denial. A compiler must not 'best effort' an
   unsupported field or fall back to a prior mapping." ⇒ 미지원 field ⇒ denial(fallback 부재).
4. **generation-fence(§5.7 line 141)**: newer restrictive Construction Generation ⇒ older unconsumed proof fenced
   (순수 순서 비교, §3.2; enforcement는 런타임).

**canary(both-ways)**: (a) 동일 입력 두 컴파일의 digest 불일치(비결정성 주입) ⇒ property 실패(가드 발화; §26
IOC-AC-003 "Construction must fail or remain exactly equivalent"); 미지원 field ⇒ denial(fallback 없음); (b) 동일
입력 ⇒ 동일 digest(양성 side). **주의**: Phase-1은 `EVL1ProvisionalCanonicalizer` + 모델 compiler로 **property
계약**을 검증하며 프로덕션 mappings/canonical scheme은 Phase-0 — 이 property가 실 compiler가 만족해야 할 **계약**을
확정한다(honest boundary).

### 4.3 economic-effect fencing + numerical safety 중앙 불변식 (ADR §13/§11; IOC-INV-005/004; IOC-EV-006/003)

- **committed dominance(IOC-INV-005 line 173)**: `economic_effect_dominated(envelope: CapacityVector, committed:
  CapacityVector) -> bool`는 verbatim "The committed capacity dominates every credible effect in the command's
  Economic Effect Envelope" — 모든 governed dimension에서 committed ≥ envelope일 때만 True. **None/UNKNOWN
  magnitude ⇒ not-dominated**(rcl `CapacityVector` None-전파 REUSE·`vector.py` UNKNOWN 소비). smaller vector 금지.
- **envelope 축소 불가(§13 line 343)**: verbatim "If exact broker interpretation is unknown, the envelope expands
  to the worst credible supported interpretation or the command is denied. Expected broker rejection, a protective
  label, human approval, or historical behavior cannot shrink it." ⇒ 이들 flag는 envelope 축소 근거 불가.
- **capacity exact·no ledger mutation(§13 line 341)**: "it cannot request a ledger mutation or treat unused
  theoretical capacity as permission." ⇒ ioc는 dominance 판정만·commit는 rcl(§3.5).
- **numerical safety(§11 line 301·§14 line 423)**: NaN/infinity/overflow/underflow/negative-zero/exponent-variant/
  precision-loss/unit-mismatch ⇒ 거부. `CanonicalDecimal` `is_finite` REUSE(구성 시 NaN/infinity 거부 — #12 NaN
  구성-거부 선례 동형). `abs`/clamp/cast/truncation/binary-float 금지 unless policy-approved(§11 line 301).
- **canary(both-ways)**: (a) envelope > committed(IOC-AC-006)·None magnitude·wrong-unit/multiplier/scale·NaN/
  overflow(IOC-AC-003) ⇒ not-dominated/거부(가드 발화; §26 IOC-AC-006 "The envelope must remain inside exact
  committed capacity"); (b) 전 dimension committed ≥ envelope·finite·unit 정합 ⇒ dominated(양성 side). **`1.0` vs
  `1.00`은 같은 canonical**(scale-normalize).

### 4.4 no-silent-widening/narrowing 불변식 (ADR §11; IOC-INV-006; IOC-EV-004)

- **exact bounded transformation only(§11 line 303·IOC-INV-006 line 177)**: `no_silent_widening(transformation,
  envelope, dependent_gates) -> bool`는 mapping/rounding/split/aggregation/default/normalization이 authorized
  meaning을 바꾸려면 **exact bounded transformation이 envelope 안 ∧ 모든 dependent gate가 그 choice set을 평가**
  했을 때만 True. IOC-INV-006 line 177 verbatim "No mapping, rounding, split, aggregation, default, or
  normalization changes authorized meaning unless the exact bounded transformation is inside the envelope and
  every dependent gate evaluated it."
- **risk-reducing rounding도 fail-closed(§11 line 303)**: "A smaller order still requires re-evaluation when it can
  leave protection insufficient, violate a minimum/lot constraint, change exposure direction, or alter approved
  economic effect." ⇒ 더 작은 quantity라도 envelope 밖이면 거부(§24.4 "Risk-Reducing Rounding Needs No Approval …
  Rejected").
- **canary(both-ways)**: (a) tick/lot rounding이 protection 제거·min/lot 위반·exposure 방향 변경(IOC-AC-004)·envelope
  밖 split partition ⇒ `False`(가드 발화; §26 IOC-AC-004 "Only exact authorized results may pass"); (b) envelope
  내 declared transformation ∧ dependent gate 평가 ⇒ 통과(양성 side).

### 4.5 mutation-fence 불변식 (ADR §15; IOC-INV-007; IOC-EV-008 — 구조적 부분만 L1)

- **post-proof 불변성(IOC-INV-007 line 181)**: `mutation_fence_holds`는 proof 발급 후 command의 economic/security
  필드가 불변임을 **구조적으로** 실현 — command·proof는 frozen(`extra="forbid"`)이라 post-proof mutation은 구성적
  불가; 새 mutation은 새 command identity + 새 proof(§16 line 429). **actual-outbound 비교(§15 line 418·§17 line
  452)는 +Security 런타임**(ADR-002-013 Egress Gateway) — Phase-1은 outbound digest 참조 계약만.
- **transport-only field(§15 line 421)**: timestamp/nonce/session-token은 policy가 "bound transport field"로 선언·
  economic-semantics/route-scope 무영향 증명·final 비교 포함 시에만 허용("'Excluded from digest' is not sufficient
  justification"). Phase-1은 이 선언 구조만 모델; 실 비교는 런타임.
- **canary(both-ways)**: (a) frozen command post-proof mutation 시도 ⇒ 구성 불가/ValidationError(가드 발화;
  IOC-AC-008); duplicate JSON key/FIX tag/alternate Unicode/negative-zero(§15 line 423) ⇒ fail-closed; (b) 정당한
  새 command+새 proof ⇒ 통과. **not-Phase-1 명시**: serializer/signer 실 강제·actual-outbound wire 비교는 §6.2에서
  런타임 이연.

### 4.6 non-revival + economic-continuity + all-false authority 불변식 (ADR §20/§21/§7; IOC-INV-011/012/013)

- **non-revival(IOC-INV-013·§21 line 515)**: `recovery_revives_nothing(...)`는 **무조건 True** — verbatim
  "Compiler, serializer, SDK, cache, signer, route, or service recovery cannot revive a prior proof, capability,
  command permission, or live scope." "Identical recompilation, replay equivalence, passing regression tests,
  broker reconnect, cache restore … cannot revive an old proof or authority"(§21 line 515). spg `expiry_revives_
  nothing`·are `non_revival_holds`·rcl `recovery_generation_revives_nothing` 동형. **canary**: recovery 후 old
  proof/command 참조로 send 시도 ⇒ 거부(fresh artifact + governed re-arm 요구, 가드 발화); fresh command/proof ⇒
  통과.
- **economic-continuity(IOC-INV-012·§18 line 475·§13 line 345)**: `economic_effect_outlives(...)`는 intent/policy/
  command/proof/capability expiry·invalidation이 order/attempt/fill/exposure/UNKNOWN/capacity를 **expire 못 함**을
  명문화(IOC-INV-012 line 201 verbatim "never expires orders, attempts, fills, exposure, UNKNOWN, or capacity
  commitments already capable of effect"). newly `NON_CONFORMANT`/invalidated proof가 broker rejection·zero
  quantity를 **retroactively 증명 못 함**(§18 line 475). **canary**: expired proof ⇒ send 차단이나 capacity release
  안 됨(가드 발화); missing ACK ⇒ potentially-live·capacity-covered.
- **all-false authority(IOC-INV-011·§7 line 219)**: `OrderConstructionAuthorityEffect`의 어떤 True도
  unconstructable(rcl `RclAuthorityEffect` `authority.py:25`·are `AggregateRiskAuthorityEffect` `records.py:83`
  동형). IOC-INV-011 line 197 "Order construction cannot approve, mutate capacity, issue authority, classify
  protection, choose permissive admissibility, transmit, clear HALT, or re-arm." **canary**: `can_transmit=True`
  구성 시도 ⇒ ValidationError.

### 4.7 ∅-공허 fail-closed + truthy-sentinel 소비 계약 (양방향 명시 — #10/#12 ∅-void·#13 truthy-sentinel 교훈)

**(가) ∅-공허 양방향**: 빈 입력의 **모든 방향**을 명문화한다. IOC 금지 동사(§1·IOC-INV): **default/alias/
substitute**(IOC-INV-003)·**coerce**(IOC-INV-004)·**reduce/shrink**(IOC-INV-005·§13 line 343)·**widen/narrow**
(IOC-INV-006)·**mutate**(IOC-INV-007)·**create headroom**(IOC-INV-009 line 189)·**expire**(IOC-INV-012)·**revive**
(IOC-INV-013).

| 빈 입력 | 금지 방향(vacuous permissive 차단) | 허용 방향(양성 side) | 근거 |
|---|---|---|---|
| **absent/open-ended `AuthorizedConstructionEnvelope`** | 부재/open ⇒ construction 불가(no member 증명 불가) ⇒ denial | closed 완비 envelope ⇒ member 판정 가능 | §5.3 line 125 verbatim "permits no construction"·§8 line 246 "Missing envelope fields are denial" |
| **빈 `ConformanceAxis` 집합** | 빈 축 ⇒ "no mismatch" 아님 ⇒ 정합 증명 불가 ⇒ `NON_CONFORMANT`/`UNKNOWN` | 전 §10–§12 축 present·일치 ⇒ `CONFORMANT` | §10 line 284·§11 line 301(ambiguity=denial) |
| **missing/empty required-authority-scope** | missing/empty/unknown ⇒ `UNKNOWN`/`NON_CONFORMANT`, **NEVER zero/wildcard/unconstrained** | exact bounded scope ⇒ proof usable | §14 line 374 verbatim "SHALL NOT mean zero required authority, wildcard authority, or an unconstrained command" |
| **빈 `EconomicEffectEnvelope`** | 빈 vector ⇒ "no effect" 아님 ⇒ dominance 증명 불가 ⇒ not-dominated | 완비 envelope + dominating committed ⇒ dominated | §13 line 329·line 343(unknown⇒expand or deny) |
| **None magnitude/multiplier** | None ⇒ 거부/`UNKNOWN`(§4.3) | finite magnitude + finite limit ⇒ 비교 가능 | §11 line 301·§14 line 423 |

**양방향 규율**: 각 빈-입력 가드는 (a) 금지 방향(가드 발화 canary)과 (b) 허용 방향(정당 통과 canary)을 **둘 다**
property로 검증한다(§7). vacuous-CONFORMANT도 vacuous-denial(정당 command를 막음)도 결함이다 — 전자는 안전 위반,
후자는 가용성 위반(#12 both-ways 교훈). **동사별 전용 canary**: default/alias/substitute(§5.1)·coerce(§5.2)·reduce/
shrink(§5.5)·widen/narrow(§5.3)·mutate(§6.2)·headroom(§6.5)·expire(§6.6)·revive(§6.6) 각각 named canary.

**(나) truthy-sentinel 소비 계약(#13 신규 교훈 — 임계)**: bool 아닌 안전 술어의 소비를 명문화한다.

- **`ConformanceResult` 반환 술어**(`command_conforms`·`derived_command_conformance`): `CONFORMANT`/`NON_
  CONFORMANT`/`UNKNOWN`는 **모두 non-empty StrEnum**이라 `if result:`·`if result == True:`면 `NON_CONFORMANT`/
  `UNKNOWN`가 **truthy로 fail-open**(catastrophic). ⇒ **구조적 봉인(v1.1 M1)**: `ConformanceResult`는
  **`__bool__`가 `TypeError`를 raise하는 truthy-불가 타입**으로 저작한다 — 미래 소비자의 `if result:` 관용구
  오용이 침묵 통과가 아니라 **런타임 오류로 즉시 노출**된다(산문 계약은 과거에 깨진 전력이 있는 반면 타입
  봉인은 producer[ioc] 범위 내 유일한 구조적 방어 — #13 교훈의 구조적 상향). 보조로 **소비 게이트 계약:
  `result is ConformanceResult.CONFORMANT`(명시 positive equality)만 통과, 그 외 전부 denial.** bare bool 반환
  금지(§5).
- **`bool|None` 반환 술어**(`economic_effect_dominated`·`no_silent_widening`·`mutation_fence_holds` 등): `None`
  (미판정)은 falsy지만 **`is True` 명시 비교**로 소비(`is not True ⇒ reject`) — spg `semantic_validation`
  step-7(`spg/predicates.py:466` `is not True⇒reject`)·#12 line 969–970 `is True` 동형. `if x:` truthy 금지.
- **canary**: 각 술어에 대해 (i) 안전값이 아닌 반환(`NON_CONFORMANT`/`UNKNOWN`/`None`/`False`)이 truthy/falsy
  edge에서 **게이트가 reject함을 assert**, (ii) 안전값(`CONFORMANT`/`True`)만 통과함을 assert, (iii) **구조
  봉인 회귀(v1.1 M1)**: `bool(r)`이 `ConformanceResult` 3값 각각에 대해 `TypeError`를 raise함을 assert(+`is`
  비교는 정상 동작 양성측). 이 계약은 §5·§6 전
  술어에 부착되고 §7 property·seam test로 회귀.

---

## 5. core 술어 — conformance·determinism·economic-fencing·no-widening (IOC-EV-001..006 substrate, L1 슬라이스)

**핵심 난제**: intent-to-command conformance를 **순수 함수**로 저작하되, (i) account/instrument/route/tick/lot/
multiplier registry·broker default를 **주입 판정/파라미터**로 두어 하드코딩 값·registry를 배제하고(§8), (ii)
fail-closed(§4)를 **구조로** 지키며(permissive 기본·vacuous 부재·truthy-sentinel 봉합), (iii) alias/default/lossy-
coercion/silent-rounding을 **most-restrictive**로 처리한다. 각 술어는 §1 core 6행(IOC-EV-001..006)의 L1 슬라이스를
저작하나 **어떤 IOC-EV도 닫지 않는다**(`/3`·`+Security`·`+Broker` 잔여).

### 5.1 identity·direction·position-effect conformance (§10/§11; IOC-EV-001/002 substrate, core L1 슬라이스)

`command_conforms(intent: ApprovedIntentContract, command: CanonicalBrokerCommand, policy:
OrderConstructionPolicy, envelope: AuthorizedConstructionEnvelope) -> ConformanceResult`:

- **`CONFORMANT` only when**: §10 identity 축(environment/live-nonlive/broker/API-version/account/subaccount/
  portfolio/custody·venue/market-segment/board/route/endpoint/session-family·instrument/broker-symbol/contract-
  month/option-series/product/currency/settlement·action-class) **전부** present ∧ envelope-member ∧ intent와
  정확 일치(§10 line 276–282) ∧ §11 direction/side/position_effect 독립 축 일치(§11 line 292–296).
- **alias/default/substitute 거부(§10 line 284)**: alias/default-account/"primary"-venue/front-month/case-fold/
  Unicode-normalize/suffix는 policy-bound one-unambiguous-mapping일 때만; one-to-many/many-to-one ⇒ `UNKNOWN`(denial
  unless 이미 approved). redirect/endpoint-discovery/SDK-env-selection/account-fallback/session-reuse는 proved
  destination 변경 불가(§10 line 286).
- **signed-quantity≠side(§11 line 301)**: direction·side·position_effect(`PositionEffectKind`)는 **독립 축** —
  negative value가 side를 silent flip 못 함(§4.1). 실 registry(account/instrument/route)는 **주입**(Phase-0 §28
  q3); ioc는 순수 축 비교.
- **반환·소비 계약**: `ConformanceResult`(bare bool 아님) — 소비 게이트는 `result is ConformanceResult.CONFORMANT`
  (§4.7 truthy-sentinel).
- **canary(IOC-AC-001/002, both-ways)**: (a) buy↔sell·open↔close·long↔short·reduce-only·zero-cross invert(IOC-AC-
  001) ⇒ `NON_CONFORMANT`; default-account/symbol-alias/contract-month/venue/env/endpoint/route substitute(IOC-AC-
  002) ⇒ `NON_CONFORMANT`; 빈 축 ⇒ `NON_CONFORMANT`(§4.7); (b) 전 축 일치·envelope-member ⇒ `CONFORMANT`.

### 5.2 compiler determinism + numerical safety (§9/§11; IOC-EV-**003 core 슬라이스** + 007 predicate-only에 공유되는 determinism substrate — v1.1 m4: 007은 core 아님)

`compiler_deterministic(inputs, generation) -> bool`(property) ∧ `numerical_safety(magnitudes, units) ->
ConformanceResult`:

- **determinism property(§4.2·IOC-INV-002)**: 동일 입력 두 컴파일 ⇒ 동일 canonical command + 동일 digest;
  hidden clock/random/locale/env/mutable-cache/unordered-map/float/network/"latest"-registry/SDK-default 부재(§9
  line 268). construction failure ⇒ denial(§9 line 270). `EVL1ProvisionalCanonicalizer` REUSE(프로덕션 form은
  Phase-0).
- **numerical safety(§11 line 296·§14 line 423)**: NaN/infinity/overflow/underflow/negative-zero/exponent-variant/
  precision-loss/unit-mismatch ⇒ `NON_CONFORMANT`/`UNKNOWN`, never smaller value. `CanonicalDecimal` `is_finite`
  REUSE. `abs`/clamp/cast/truncation/binary-float 금지 unless policy-approved(§11 line 301).
- **canary(IOC-AC-003, both-ways)**: (a) 비결정 순서·wrong multiplier/currency/scale/sign·NaN/overflow/negative-
  zero/locale-variation ⇒ digest 불일치/`NON_CONFORMANT`(가드 발화; §26 IOC-AC-003 "Construction must fail or
  remain exactly equivalent"); (b) 동일 입력·finite·unit 정합 ⇒ 동일 digest/`CONFORMANT`(양성 side).

### 5.3 quantity·tick·lot·rounding conformance + no-silent-widening (§11; IOC-EV-004 substrate, core L1 슬라이스)

`command_conforms` quantity 축 + `no_silent_widening(transformation, envelope, dependent_gates) -> bool`(§4.4):

- **quantity 축(§11 line 297–299)**: shares/lots/contracts/base-quote/nominal/notional/face-value/fractional
  (`QuantityUnitKind`)·min/max/step/precision/overflow/underflow/exact-rounding-result가 envelope 안 일치.
- **no-silent-widening/narrowing(§11 line 303·IOC-INV-006)**: rounding/split/aggregation 결과가 envelope 밖 ⇒
  거부. risk-reducing rounding도 protection 제거·min/lot 위반·exposure 방향 변경·approved effect 변경 시 재평가
  요구. split partition의 aggregate worst credible simultaneous effect가 same envelope + committed capacity 안일
  때만(§11 line 305). tick/lot registry는 **주입**(Phase-0).
- **canary(IOC-AC-004, both-ways)**: (a) min/max/step 위반·fractional/odd-lot·tick 경계·clamp/truncation·protection-
  제거 rounding·envelope-밖 split(IOC-AC-004) ⇒ `NON_CONFORMANT`/`False`(가드 발화; §26 "Only exact authorized
  results may pass"); (b) envelope-member exact rounding ∧ dependent gate 평가 ⇒ 통과.

### 5.4 price·order-type·TIF·expiration·mode conformance (§12; IOC-EV-005 substrate, core L1 슬라이스)

`command_conforms` price/order/mode 축:

- **preserve exact semantics(§12 line 311–317)**: order type(`OrderTypeKind`)·price/trigger/offset/collar/limit/
  scale/precision/tick·TIF/good-till/session-boundary/expiration/activation·route/venue-phase/participation/
  display/reduce-only/post-only/AON/min-qty·operating mode(live/restricted/degraded-protective/containment/
  simulation/test/paper)가 envelope 안 일치.
- **omission·default(§12 line 319)**: field omission은 policy가 broker default invariant·canonical-explicit·
  **current in Broker Capability Profile(주입)**·intent-identical 증명 시에만; 아니면 explicit 필수.
- **widening=material(§12 line 321)**: price improvement/더 aggressive price/longer expiration/different order type/
  broader route는 material change(exact bounded alternative approved + capacity/venue/protection 분석 시에만).
  "'More likely to fill' is not a safety justification." non-live command는 non-live env/route identity carry —
  mode flag만 바꿔 live로 전환 불가(§12 line 323).
- **canary(IOC-AC-005, both-ways)**: (a) price aggressiveness/trigger/order-type/TIF/expiry/route/reduce-post-only/
  auction/live-paper mode mutate(IOC-AC-005) ⇒ `NON_CONFORMANT`(가드 발화; §26 "Every widening or semantic
  mismatch must be denied"); (b) envelope-member exact semantics + capability-invariant default ⇒ `CONFORMANT`.

### 5.5 economic-effect envelope + capacity dominance (§13; IOC-EV-006 substrate, core L1 슬라이스)

`EconomicEffectEnvelope`(=rcl `CapacityVector` REUSE) 생산 ∧ `economic_effect_dominated(envelope, committed) ->
bool`:

- **conservative envelope(§13 line 329–339)**: per-(scope,dimension) conservative effect vector — position delta·
  gross/net notional·leverage·margin·concentration·liquidity·basis·settlement·max executable quantity·partial-fill
  prefix·zero-cross·reversal·amend/replace overlap·simultaneous split·reduce-only failure·broker rounding/fee/cash/
  conversion/exercise/assignment/delivery·existing potentially-live attempts. scenario 값·valuation은 **주입**(§4
  non-scope; are/rcl 좌표와 정합 — CapacityVector REUSE).
- **dominance(§13 line 341·IOC-INV-005)**: committed capacity가 모든 dimension에서 envelope를 dominate할 때만
  True. None/UNKNOWN ⇒ not-dominated(§4.3). compiler confidence/expected-rejection/protective-label/human-approval/
  historical-behavior가 envelope 축소 못 함(§13 line 343). unknown broker interpretation ⇒ worst credible로 expand
  or deny.
- **no ledger mutation(§13 line 341)**: ioc는 dominance 판정만; commit·serialize는 rcl(§3.5·§4.6). envelope는
  are가 MaximumCredibleCommandEffect로 소비(§3.4).
- **canary(IOC-AC-006, both-ways)**: (a) partial-fill/reversal/reduce-only-failure/broker-rounding/fees/simultaneous-
  split/replace-overlap이 committed 초과(IOC-AC-006)·None magnitude ⇒ not-dominated(가드 발화; §26 "The envelope
  must remain inside exact committed capacity"); 빈 envelope ⇒ not-dominated(§4.7); (b) 전 dimension committed ≥
  envelope·finite ⇒ dominated(양성 side).

### 5.6 canonical command + conformance proof integrity (§14; IOC-EV-001..006 공통, core L1 슬라이스)

`CanonicalBrokerCommand`·`OrderConformanceProof` frozen digest-bound 레코드:

- **command 완전성(§14 line 351–359)**: command identity/schema/canonicalization-version/Construction-Generation/
  digest + refs{Intent proposal, envelope, policy, broker profile, context} + 전 broker mutation 필드(explicit
  semantic type/unit/presence/value) + endpoint/method/route/session/idempotency/client-order-id + actual-outbound
  canonicalization rule + issue/max-age/invalidation/evidence + **explicit non-authorizing flags**. unknown/
  duplicate/alternate-encoding ⇒ rejection(§14 line 406 — `extra="forbid"` 실현, §2.1).
- **proof binding(§14 line 361–372)**: policy+envelope digest·compiler/dependency/schema/serializer/SDK/build/
  config/deployment/compatibility generation·deterministic input+output digest·field-by-field+semantic conformance·
  numeric derivation·economic-effect+capacity-dominance result·**ADR-002-021 are decision refs(digest scalar,
  §3.4)**·venue+brokercap refs·unknown/residual/expiry/invalidation·**final `ConformanceResult`**.
- **required-authority-scope restrictive(§14 line 374)**: mandatory·restrictive — missing/empty/unknown/stale/
  conflicting ⇒ `UNKNOWN`/`NON_CONFORMANT`, **NEVER zero/wildcard/unconstrained**(§4.7 ∅-void 대표 사례).
- **`CONFORMANT` grants nothing(§14 line 376)**: "usable only as one current input to separately owned capacity,
  authorization, capability, and final-egress enforcement." all-false authority(§6.5).
- **canary(both-ways)**: (a) same command_id + diff canonical digest ⇒ `classify_record_pair` `CRITICAL_CONFLICT`
  (위조·contradictory proof 탐지·양쪽 보존, no last-write-wins); missing required-authority-scope ⇒ `UNKNOWN`(zero/
  wildcard 아님); (b) 완비 command+proof·정합 digest ⇒ ISSUED. **id⊥digest**(§0.4d — 재발행/substitution 탐지).

---

## 6. predicate-only 술어 — canonicalization·mutation-fence·lineage·protective·authority·non-revival (IOC-EV-007..012 substrate, 최소 ≥ L2·닫지 않음)

각각 **L1-decidable substrate**를 저작하나 **어떤 IOC-EV도 닫지 않는다**(최소 ≥ L2·+Security/+Broker 잔여).

### 6.1 canonicalization determinism + parser-differential guard (§14/§15; IOC-EV-007 substrate, predicate-only)

`canonicalization_deterministic(command) -> bool` + duplicate/unknown-field 거부 — §4.2 determinism의 canonical-
representation 측면. §14 line 406 verbatim "Unknown fields, duplicate semantic fields, alternate encodings,
unbound headers, or ambiguous canonicalization are rejection. A byte digest alone is insufficient if two byte
sequences or parser behaviors can produce different broker meaning." §15 line 423 "Parameter pollution, duplicate
JSON keys, duplicate FIX tags, alternate Unicode forms, percent-encoding variants, numeric exponent variants,
NaN/infinity, negative zero, integer overflow, silent truncation, or parser differential SHALL fail closed." L1은
**canonical form 동일성 + duplicate/unknown 거부**(구조적, `extra="forbid"`); **parser differential·byte/semantic
digest 불일치·malicious encoding은 EV-L2 component-fault·+Security**(§23 line 555 shared-parser common mode). 최소
`EV-L2/3+Security`.

### 6.2 mutation-fence (post-proof + actual-outbound) (§15/§17; IOC-EV-008 substrate, predicate-only)

`mutation_fence_holds(command, proof) -> bool` — §4.5의 구조적 불변성(frozen command·post-proof mutation 구성-불가).
§15 line 414 "no economic- or security-relevant semantic field may change" after proof. **actual-outbound
equivalence(§15 line 418·§17 line 452 "verify the actual outbound representation and signer input are semantically
identical")는 +Security 런타임**(ADR-002-013 Egress Gateway·serializer/signer 강제·queue/proxy/SDK mutation 탐지).
Phase-1은 outbound canonicalization rule을 command에 **모델**하되 wire 비교를 하지 않는다(§0.2). 최소 `EV-L2/3+
Security`.

### 6.3 retry/amend/replace/split/aggregate lineage (§16; IOC-EV-009 substrate, predicate-only)

`derived_command_conformance(parent, derived, mutation_class: MutationClass) -> ConformanceResult` +
`no_blind_retry(...) -> bool`:

- **자체 identity+proof(§16 line 429)**: 모든 broker mutation은 자체 command identity+proof. same-command retry는
  **active Broker Capability Profile이 deterministic idempotency를 exact identity/scope로 증명**하고 original
  attempt state가 retry 허용·context/authority valid·capability workflow authorize일 때만; 아니면 UNKNOWN
  potentially-live·**no blind resubmission**(§16 line 431).
- **cancel≠FQP·amend/replace overlap(§16 line 433)**: cancel ACK is not Final Quantity Proof; amend/replace는 old/
  new command identity·capacity overlap·cancellation/protection·ADR-002-011 gap/overlap proof binding. split는 
  partition plan·aggregate bound·per-child identity·simultaneous-execution envelope·completion accounting(§16 line
  435). aggregation은 default denied(§16 line 437).
- **소비 계약**: `ConformanceResult` — `is CONFORMANT` 명시(§4.7). **broker deterministic idempotency·replace
  semantics는 injected(brokercap `ReplaceSemantics` `vocabulary.py:202`)·실 broker 통합은 +Broker**(ADR-002-004).
  최소 `EV-L2/3+Broker`.
- **canary(IOC-AC-009, both-ways)**: (a) missing ACK ⇒ blind resubmission 시도·changed retry payload·regenerate
  remaining quantity·duplicate split child·aggregate unrelated intent(IOC-AC-009) ⇒ `NON_CONFORMANT`/거부(가드
  발화; §26 "Identity, capacity, proof, and no-blind-retry rules must hold"); (b) capability-proven idempotency +
  valid attempt state ⇒ 통과.

### 6.4 protective/exit construction (§19; IOC-EV-010 substrate, predicate-only)

`protective_creates_nothing(action, envelope, admissibility, capacity) -> bool` — §19 line 481 verbatim
"Protective, reduction, cancel, or containment commands are not exempt." label/urgency/priority가 exact envelope/
admissibility/capacity/egress를 **bypass 못 함**(§19 line 483). compiler가 "make protection work"를 위해 order
type/price/route/side/quantity/position-effect/broker-flag를 변경 못 함 unless pre-authorized(§19 line 485). 실행
가능 conforming protective command 부재 ⇒ contain/HALT/escalate/preserve, "SHALL NOT fabricate a permissive
command, reuse stale proof, or call priority a reserve"(§19 line 487). **partition/broker-alive·pre-committed
protective lease는 런타임**(ADR-002-001/002). 최소 `EV-L2/3+Broker`. **canary**: protective label로 envelope 밖
order type/price 변경 시도(IOC-AC-010) ⇒ 거부(가드 발화; §26 "Label and priority must not bypass"); pre-authorized
envelope-member protective ⇒ 통과.

### 6.5 authority separation / all-false (§7/§23; IOC-EV-011 substrate, predicate-only)

`construction_grants_no_authority(effect: OrderConstructionAuthorityEffect) -> bool` + all-false(§4.6·IOC-INV-011:
어떤 True도 unconstructable). §7 line 228 verbatim "The compiler and its policy, schema, mapping, test, and
evidence identities SHALL NOT hold a usable live broker credential or broker-order route." §23 line 563 "No
compiler, mapping, registry, test, evidence, or replay principal may combine usable live-order authority with a
broker-order route." **compiler↛live-credential/route·egress bypass·common-mode privilege path는 +Security 런타임**
(ADR-002-013 confinement, §23). 최소 `EV-L2/3+Security`. **canary**: `can_transmit=True`/`can_issue_authority=True`
구성 시도 ⇒ ValidationError(가드 발화); all-false effect ⇒ 통과.

### 6.6 non-revival + economic continuity (§20/§21; IOC-EV-012 substrate, predicate-only)

`recovery_revives_nothing(...)`(무조건 True — §4.6·§21 line 515) ∧ `economic_effect_outlives(...)`(intent/policy/
command/proof/capability expiry·invalidation이 order/attempt/fill/exposure/UNKNOWN/capacity를 expire 못 함, §4.6·
IOC-INV-012 line 201·§18 line 475). restart/rollback/restore/failover/cache-warm/serializer-recovery/SDK-recovery/
broker-reconnect/replay/identical-recompilation cannot revive prior proof/capability/authority(§21 line 515). "No
automatic re-arm is permitted"(§21 line 515·§1 line 41). **Recovery Barrier(ADR-002-017)·governed re-arm workflow
enforce는 런타임**(§21 line 505·§28 q8). 최소 `EV-L2/3+Security`. **canary(IOC-AC-012, both-ways)**: (a) restart/
restore/identical-recompile/replay-match 후 old proof 재사용 시도(IOC-AC-012) ⇒ 거부(fresh artifact+governed re-arm
요구, 가드 발화; §26 "Fresh artifacts and governed re-arm are required without capacity release"); expired proof ⇒
send 차단이나 capacity release 안 됨; (b) fresh command/proof + governed re-arm ⇒ 통과.

---

## 7. property-test 하네스 타깃

§1 분류에 정렬한다. **닫는 IOC-EV = 0건** — 어떤 test-target도 IOC-EV closure·acceptance를 주장하지 않는다(규율
태그 부착). 각 술어에 **both-ways canary**(§4·§5·§6)·**truthy-sentinel canary**(§4.7)·**fixture clean-vs-illegal
정합**(#8 교훈)을 건다.

- **core(L1 슬라이스, IOC-EV-001..006 substrate)**: `command_conforms` identity/direction/position-effect 축
  (§5.1); `compiler_deterministic`+`numerical_safety`(§5.2); `command_conforms` quantity+`no_silent_widening`
  (§5.3); `command_conforms` price/order/mode 축(§5.4); `economic_effect_dominated`(CapacityVector)+envelope 생산
  (§5.5); `CanonicalBrokerCommand`/`OrderConformanceProof` 재구성·`classify_record_pair` CRITICAL_CONFLICT·
  required-authority-scope restrictive(§5.6). **compiler-determinism property(노다지)**: hypothesis로 valid
  input x 무작위 생성 → `compile(x).canonical_digest == compile(x).canonical_digest`(digest 동일성) + hermetic
  (clock/network 부재) + generation-fence(§4.2). conformance property: intent/command/policy/envelope 무작위 생성
  → 축별 정합·envelope-membership·numerical-safety·dominance 불변식 검사.
- **predicate-only(IOC-EV-007..012 substrate, EV 미주장)**: `canonicalization_deterministic`+duplicate/unknown
  거부(§6.1); `mutation_fence_holds`(§6.2); `derived_command_conformance`+`no_blind_retry`(§6.3);
  `protective_creates_nothing`(§6.4); `construction_grants_no_authority`+all-false(§6.5); `recovery_revives_
  nothing`+`economic_effect_outlives`(§6.6).
- **truthy-sentinel 회귀(§4.7, MANDATED)**: `ConformanceResult` 반환 술어에 대해 (i) `NON_CONFORMANT`/`UNKNOWN`가
  truthy임을 assert, (ii) `is CONFORMANT` 게이트가 그 둘을 reject함을 assert(`if result:` 대비 회귀); `bool|None`
  술어에 대해 `None`/`False`가 `is True` 게이트에서 reject됨을 assert. **이 회귀가 #13 truthy-sentinel 교훈의 능동
  봉합**이다.
- **seam cross-check(test-only, MANDATED §3.4)**: `test_seam_rcl`(ioc `EconomicEffectEnvelope` `CapacityVector`
  좌표 = rcl `proposed_adverse_increment` `records.py:185`)·`test_seam_are`(ioc proof decision ref = are
  `AggregateRiskDecision` scalar `are/records.py:494/497`)·`test_seam_dsl`(ioc `ApprovedIntentContract` proposal
  ref = dsl `Proposal` `proposal_id`/digest `dsl/proposal.py:68`). 테스트 import는 package closure에 불계상(§7.1).
- **∅-공허 회귀(양방향, §4.7)**: absent/open envelope ⇒ construction 불가; 빈 축 ⇒ `NON_CONFORMANT`; missing
  required-authority-scope ⇒ `UNKNOWN`(zero/wildcard 아님); 빈 envelope ⇒ not-dominated; **동시에** 각 완비 입력의
  정당 통과 canary.

### 7.1 import-closure 검증 테스트 (설계 #4 §7.1·#5..#13 §7.1 상속)

`import tos.ioc` 후 `sys.modules` closure에 **금지 집합 부재 assert**: `shared.config`·`os.environ` 흔적·`numpy`/
`pandas`/`yaml`·**`tos.are`·`tos.dsl`·`tos.capsule`·`tos.orthostate`·`tos.brokercap`·`tos.spg`·`tos.liveauth`·
`tos.authority`·`tos.time`·`tos.evidence`·`tos.protective`·`tos.recon`**(12 형제) 부재; **`tos.canonical`·
`tos.ordering`·`tos.rcl` 존재 허용**. required check(`tos-firewall`, `tools/tos_firewall_check.py` layer-① AST +
`.importlinter` layer-② 전이)와 함께 green이어야 §0.3 선언이 능동 성립.

### 7.2 run manifest 정렬 (설계 #1 §5.1 7항목)

(1) 목적: ioc Phase-1(EV-L1) 순수 모델+property test. (2) 명령: `pytest tos/tests/ioc/ -v`. (3) 격리:
hermetic(`.env` 비주입·clock 미접근·네트워크 없음 — compiler determinism의 hidden-input 부재 §4.2와 정합). (4)
결정론: hypothesis 시드 고정·`CanonicalDecimal` scale-normalize·NaN/infinity 구성-거부·`EVL1ProvisionalCanonicalizer`
고정. (5) 산출물: property test 결과(EV closure 아님 — 규율 태그). (6) 게이트: `tos-firewall` required green. (7)
비-acceptance: 어떤 IOC-EV도 닫지 않음(§0.2·VER-002-001 §5).

---

## 8. bounds 주입 + Phase-0

**§8.0 ioc 모델 구조에 numeric bound 부재**: 전부 enum(`ConformanceResult`/`ConformanceAxis`/`MutationClass`/
`OrderTypeKind`/`QuantityUnitKind`/`PositionEffectKind`)·boolean·집합 논리·주입 `CanonicalDecimal`(multiplier·
price·quantity·limit)·rcl `CapacityVector`(magnitude). ADR §4 non-scope line 109 "numeric age or invalidation
bounds, which require an approved Verification Profile"는 수치를 **명시 배제**한다 — 전부 **Safety/Verification
Profile INSTANCE 측정값**이며 주입 opaque param으로만 담는다. 값 부재 ⇒ fail-closed(§4). 값 승인은 Bounds-Approver
게이트(§9.2).

**§8.1 Verification-Profile 키 실측(#13 MAJOR-2 규율 — `measurement_source` 전수 확인)**: ADR §28 q12가 요하는
수치 분류 및 VERIFICATION-PROFILE-002.yaml 키 상태(전수 grep):
- **proof invalidation-to-egress(§17–18)**: `B_order_conformance_invalid_to_egress`(line 261, `value_ms: null`
  MEASURE, `measurement_source: construction_generation_proof_invalidation_and_egress_boundary_trace`,
  `failure_response: HALT`, rationale "ADR-002-020 §§17-18") — **이미 존재**.
- **canonical broker command age(§14)**: `MAX_canonical_broker_command_age_ms`(line 713, `null` — "APPROVE per
  broker/action scope; unknown age denies send and expiry never expires economic effect") — **이미 존재**.
- **order conformance proof age(§14/§17)**: `MAX_order_conformance_proof_age_ms`(line 714, `null` — "APPROVE per
  exact command; stale proof denies send and cannot release capacity") — **이미 존재**.
- **capability-claim-to-first-byte 합성(§17 line 454)**: `B_capability_claim_to_send`(line 163, `value_ms: null`,
  ADR-002-007 §§9.4-9.5) — **ADR-002-007 소유**(IOC는 합성 참조만; §17이 capability claim+SEND_STARTED을 ADR-002-
  007/024로 위임).
- **scope pin(§8/§9)**: `order_construction_policy_id/generation/digest`(line 55–57, TBD/null) — policy 아티팩트의
  test-harness pin.
- **결론(over-claim 봉합·#10 lesson)**: ADR §28 q12가 요구하는 IOC-owned 3 bound(proof invalidation-to-egress·
  command age·proof age)가 **전부 실재**하고 전부 null/MEASURE(미승인) + 합성용 capability-claim bound은 ADR-002-
  007 소유(실재). ⇒ **candidate 신규 키 = 0건**(#10/#13 "0 누락" 동형; #12의 4-key 누락과 대조). 이는 결함이 아니라
  **Phase-0 Bounds-Approver 승인 항목**이다 — ioc는 이 값들을 신뢰하지 않으며(VP status PROPOSED·unapproved bound은
  approved bound 아님, VER-002-001 §6) 전 수치를 fail-closed로 처리(§4).

**§8.2 self-referential 주의(경미)**: ioc `OrderConstructionPolicy`는 spg Safety Configuration Bundle governance
대상(§7 line 217)이며 VP scope 블록이 policy id/generation/digest를 pin한다(line 55–57). #12(spg)가 다룬 self-
reference paradox와 달리 ioc는 **policy의 소비자**일 뿐(governance 주체는 spg)이라 layering이 단순하다 — ioc는 VP를
import·파싱하지 않고(YAML은 하네스 #3), policy 좌표를 주입 scalar로만 담는다. VP status PROPOSED ⇒ 전 수치 불신.

**§8.3 upstream age bound 합성(런타임·not-Phase-1)**: §17 final-egress는 ioc-owned bound뿐 아니라 upstream age
bound(`MAX_decision_context_age_ms` line 710·`MAX_critical_input_snapshot_age_ms` line 709·`MAX_venue_constraint_
snapshot_age_ms` line 711·`MAX_order_admissibility_decision_age_ms` line 712·`MAX_aggregate_risk_state_snapshot_
age_ms` line 715·`MAX_aggregate_risk_decision_age_ms` line 716)를 **합성 소비**한다 — 전부 형제 ADR 소유·실재·null.
Phase-1 ioc는 이 합성을 **강제하지 않고**(런타임 §17) proof에 각 upstream 아티팩트의 digest scalar를 binding할
뿐이다(§5.6). 합성 강제·age 검사는 EV-L3 final-egress 런타임.

---

## 9. 후속 작업 · Phase-0 인간 게이트 이관 항목

### 9.1 후속 구현 작업 (본 계약 위에서)

1. `tos/src/tos/ioc/` 5-module 저작(`_base.py` shim·`vocabulary.py`·`records.py`·`predicates.py`·`state.py`)
   + `tos/tests/ioc/` property test(§7) + seam cross-check(§3.4) + import-closure(§7.1) + truthy-sentinel 회귀
   (§4.7).
2. core 술어 6종(§5) + predicate-only 술어 6종(§6) + 6-아티팩트·all-false authority·`ConformanceResult`/
   `ConformanceAxis`/`MutationClass`/`OrderTypeKind`/`QuantityUnitKind`/`PositionEffectKind`(§2) 구현. **`Economic
   EffectEnvelope`=rcl `CapacityVector` REUSE**(ioc→rcl 1 edge; §0.4c) — 별도 vector 타입 저작 금지.
3. 미래 caller 런타임(Order Construction Service / Broker Egress Gateway)이 ioc 산출(envelope=`CapacityVector`·
   proof·command)을 소비자(are MaximumCredibleCommandEffect·rcl commit·final-egress)로 배선(§3.4; Phase 1 밖·
   EV-L3). **envelope는 `CapacityVector` REUSE라 축약 reducer 불요**(#13 MAJOR-1 동형; §0.4c).

### 9.2 Phase-0 인간 게이트로 넘기는 항목 (본 계약이 결정하지 않음)

ADR §28 Open Implementation Questions(12항)·§29 Approval Gate(14조건)에서 Phase-1 밖으로 이연:
1. **canonical Intent/envelope/command/effect/proof schema 선택**(§28 q1) — 프로덕션 canonical semantic form
   (§3.1 EVL1ProvisionalCanonicalizer는 잠정).
2. **deterministic numeric type·rational/decimal library·unit system·overflow rule·canonicalization format**
   (§28 q2) — 전부 주입(§4 non-scope); `CanonicalDecimal`은 L1 대리.
3. **account/instrument/contract/symbol/route/price/tick/lot/multiplier/currency/position-effect registry**
   (§28 q3) — `ConformanceAxis`의 구체 registry 값(§5.1은 구조만).
4. **independent reproduction separation from compiler common mode**(§28 q4·§23) — schemas/generated-models/
   libraries/SDKs/administration across(+Security).
5. **final egress가 actual outbound을 observe·compare하는 방식**(§28 q5·§17) — SDK/signing/proxy/queue/session
   after의 wire 비교(ADR-002-013 런타임).
6. **transport-only field 판정**(§28 q6·§15) — non-economic/non-routing relevance의 독립 증명.
7. **broker별 deterministic split/aggregation/same-command-retry/cancel/amend/replace semantics**(§28 q7·§16) —
   brokercap+broker 통합(§6.3은 술어만).
8. **Construction Generation + stale-compiler/serializer/capability-issuer/egress fence substrate**(§28 q8·§18) —
   런타임 enforcement(§3.2는 순서 비교만).
9. **proof currentness without permissive cache or circular dependency at final egress**(§28 q9·§17) — 런타임.
10. **failure-domain allocation**(§28 q10·§23) — mapping/numeric/schema/compiler/serializer/SDK/signer/administrator
    defect가 construction·verification 양쪽을 속이지 못하게(+Security).
11. **broker-accepted but locally non-conforming command 격리·reconcile·incident**(§28 q11) — 런타임(§18 line 475).
12. **numeric bounds 승인**(§28 q12) — `B_order_conformance_invalid_to_egress`·`MAX_canonical_broker_command_age_ms`·
    `MAX_order_conformance_proof_age_ms`(§8.1 **전부 실재·null**)의 Bounds-Approver 승인 + fault-injection 측정
    (§29 item 9). **candidate 신규 키 0건.**
13. **ADR-002-023 IAP upstream(§29 item 12)** — Independent Approval + immutable Intent Registration이 unchanged
    proposal/envelope/candidate/venue-decision/construction-generation을 binding(IAP EV family). dsl `Proposal` id
    유도 scheme 확정(dsl 설계 line 571 — -020/-023 공동).
14. **ADR-002-021 ARE binding(§29 item 11)** — exact aggregate-risk decision/allocation currentness가 Economic
    Effect Envelope와 RCL commitment 사이 binding(ARE evidence, #13).
15. **ADR-002-013 final egress·ADR-002-007 capability·ADR-002-024 currentness 런타임**(§29 item 3·4·6) — serializer/
    signer/actual-outbound/capability-claim/SEND_STARTED.
16. **ADR-002-016 Evidence Integrity·Replay**(§22·§28) — replay ENGINE(§5.6 레코드 substrate만 Phase-1).
17. **ARCHITECTURE-GATE-STATUS 명시 acceptance 결정**(§29 item 14) — 실행된 IOC-EV-001..012 + cross-system evidence +
    독립 리뷰(Independent-Safety-Reviewer 하드 배제).

---

## 10. 개정 로그 + 비준 체크리스트

### 10.1 개정 로그

- **v1.0 (2026-07-25) — 초안, 독립 비평 리뷰 대기.** ADR-002-020을 Phase 1(EV-L1) 설계 계약으로 실현. 패키지
  `tos.ioc`(대안 `tos.command`[collision+generic]·`tos.construction`[부분] 기각, `tos.conformance`[오독0·verbose·
  부분·prefix불일치] runner-up, §0.4a — **Immediate-Or-Cancel 오독 우려 명시**). 6-아티팩트(`ApprovedIntentContract`·
  `AuthorizedConstructionEnvelope`·`OrderConstructionPolicy`·`CanonicalBrokerCommand`·`OrderConformanceProof`
  digest-bound + `EconomicEffectEnvelope`=rcl `CapacityVector` REUSE) + all-false `OrderConstructionAuthorityEffect`
  (§2). EV 분류: **core 6행(IOC-EV-001..006, #12형·사전 카운트 6과 일치·정정 불요) / predicate-only 6행(007..012)
  / not-Phase-1(런타임·+Security·+Broker·형제) — 닫는 IOC-EV = 0건**(§1). seam: **dsl/are/capsule/orthostate/
  brokercap/venue/spg scalar·digest producer/consumer + sibling edge 1건(ioc→rcl `CapacityVector` REUSE), PROMOTE
  0**(코드 실측: dsl `proposal.py:68`·`6–9`, are `records.py:451/494/497`, rcl `vector.py:74`·`records.py:185`·
  `predicates.py:575`, capsule `capsule.py:170`·`snapshot.py:96`, orthostate `records.py:93`·`vocabulary.py:32/61`,
  brokercap `records.py:305/71`·`vocabulary.py:202`, §3.4). **핵심 아키텍처 판정**: (i) **dsl §8 field set 이연의
  착지점** — dsl `Proposal`이 "an anchor, not a redefinition of ADR-002-020"(`proposal.py:6–9`)·dsl 설계 line 572가
  §8 field set을 -020으로 이연했으므로 `ApprovedIntentContract`(§5.1)가 착지점이고 approval/registration은 IAP(-023,
  §3.5). (ii) **`EconomicEffectEnvelope`=rcl `CapacityVector` REUSE**(#13 are→rcl 동형·타입 수준 dominance·rcl↛ioc
  acyclic·자체 vector는 존재하지 않는 reducer under-count 봉인 불가+truthy-sentinel 위험으로 기각, §0.4c). (iii)
  **truthy-sentinel 소비 계약**(#13 신규 교훈): `ConformanceResult`(CONFORMANT/NON_CONFORMANT/UNKNOWN)는 non-empty
  StrEnum이라 `if result:`면 fail-open ⇒ 소비 게이트 `is CONFORMANT` 명시 비교·`bool|None`은 `is True`(§4.7). 중심
  fail-closed 술어: `command_conforms`(축별 정확 일치·alias/default 거부)·`compiler_deterministic`(digest 동일성·
  hidden-input 부재)·`economic_effect_dominated`(committed dominance·None⇒not-dominated)·`no_silent_widening`(risk-
  reducing rounding fail-closed)·`derived_command_conformance`(no-blind-retry)·`recovery_revives_nothing`(§5/§6).
  **∅-공허 양방향**(absent envelope·빈 축·missing required-authority-scope[zero/wildcard 아님, §14 line 374]·빈
  envelope — 금지+허용 둘 다, §4.7). 앵커: IOC-INV-001..014·IOC-AC-001..012·IOC-EV-001..012(§0.4f). **bounds 실측**:
  IOC-owned 3 profile 키(`B_order_conformance_invalid_to_egress` line 261·`MAX_canonical_broker_command_age_ms`
  line 713·`MAX_order_conformance_proof_age_ms` line 714) 전부 실재·null(candidate 신규 키 0건, §8.1). 선제 봉합:
  fail-open(§4.1/§4.3)·∅-공허 양방향(§4.7)·under-realization(전용 슬롯 실재하는 rcl/are/dsl/capsule/brokercap에만
  정의 술어·orthostate는 정직 state-의존 이연, §3.4 (d))·phantom 타입 0(전 인용 grep 실측)·verbatim+line·좌표 비붕괴
  (§2.2 (7))·**truthy-sentinel 소비 계약**(#13 신규, §4.7). **어떤 EV도 닫지 않음·acceptance 미선언.**

- **v1.1 (2026-07-26) — 독립 비평 리뷰 REVISE(CRITICAL 0·MAJOR 1·MINOR 4·NIT 1) 반영, forward-only.**
  **M1(채택 — OQ iv 판정)**: `ConformanceResult` truthy-sentinel을 산문 소비 계약에서 **구조적 봉인으로 상향**
  — `__bool__` ⇒ `TypeError`(truthy-불가 타입; 미래 소비자의 `if result:` 오용이 침묵 fail-open 대신 런타임
  오류로 노출; producer 범위 내 유일한 구조적 방어), §2.2(1)/§4.7(나)/§7 canary(iii) 반영. **m1**: verbatim
  라인 에라타 7건 정정(dominance+compiler-confidence 인용 → IOC-INV-005 line 173[ADR 원문 재실측으로 리뷰어
  판정 확정]; MutationClass "verbatim" 딱지 완화; §5.7 141·§8 236·§14 365·§23 555). **m2**: `.importlinter`
  라인 29–43/35–43 정정. **m3**: `BrokerCapabilityProfile` 인용 records.py:305(class 정의 라인)로 통일.
  **m4**: §5.2 라벨 "003 core + 007 predicate-only 공유 substrate"로 명확화(007 core 오독 차단). **NIT**:
  digest-equality near-tautology 명시(load-bearing = hermetic·denial-is-total·generation-fence). 아키텍처
  핵심 결정(6-아티팩트·ioc→rcl CapacityVector REUSE·-020/-023 분할·edge/PROMOTE) 불변. 리뷰어 검증: register
  6행·profile 0 누락·phantom 0 — "측정 규율 시리즈 최상급".

### 10.2 비준 체크리스트 (운영자 · 독립 리뷰어 확인 사항)

1. **패키지 명명** `tos.ioc`(Intent-to-Order Conformance) 승인 — **또는 `tos.conformance`**(오독0·verbose·부분·
   prefix 불일치). **[운영자 판단 지점]**: `ioc`의 **Immediate-Or-Cancel(TIF) 금융 오독**이 register-prefix 충실
   (`IOC-EV`/`AC`/`INV` 1:1)·terse 관행보다 무거운지. naming은 load-bearing 아님(설계 #1 line 164 — 운영자 치환
   가능). `tos.command`(collision+generic)·`tos.construction`(부분) 기각 근거 검토(§0.4a).
2. **seam 결정**: dsl/are/capsule/orthostate/brokercap/venue/spg scalar·digest 주입(edge 0) + 최종
   `EconomicEffectEnvelope` ioc→rcl `CapacityVector` REUSE(1 edge) — §3.4/§0.4b/§0.4c. **[운영자 판단 지점]**.
   상대 슬롯 실재를 코드로 재확인(리뷰어: dsl `proposal.py:68`·are `records.py:451/494`·rcl `vector.py:74`·
   `records.py:185`·capsule `capsule.py:170` 인용 라인 검증 — sibling 서사 아님).
3. **`EconomicEffectEnvelope` 결정 (권장 채택)**: rcl `CapacityVector` REUSE(ioc→rcl 1 edge; rcl↛ioc 실측
   acyclic·#13 are→rcl 선례) — 자체 vector(기각·존재하지 않는 reducer under-count 봉인 불가+claimed-dominance-bool
   truthy-sentinel 위험)·canonical PROMOTE(기각·무거움) 근거 검토(§0.4c). **[운영자 판단 지점]**: REUSE 승인 여부.
   ioc envelope 좌표가 rcl commit 타입(`proposed_adverse_increment`)·are MaximumCredibleCommandEffect와 **동일**함을
   seam test로 확인(타입 수준 dominance — 축약 reducer 불요).
4. **`ApprovedIntentContract` identity 결정**: `IndependentIdArtifact`(권장·issuer/approval governance identity⊥
   digest·재발행 탐지) vs `IdDerivedArtifact`(content-addressed) — §0.4d. **[운영자 판단 지점]**. dsl `Proposal`은
   `IdDerivedArtifact`(재정의 금지·digest 참조)임을 재확인.
5. **dsl §8 이연 착지 판정(§3.5)**: dsl `Proposal`이 "an anchor, not a redefinition"(`proposal.py:6–9`)·dsl 설계
   line 572("ADR-002-020 §8 구체 field set 확정")·line 571("Proposal id 유도 → -020/-023")를 대조해 **§8 field
   set=-020(본 문서 `ApprovedIntentContract`)·approval/registration=-023(IAP)·Proposal id scheme=-020/-023 공동**
   분할이 정확한지 재확인(권위 중복 방지 #8 교훈).
6. **EV 분류·실측(§1)**: core 6 / predicate-only 6 / not-Phase-1 판정과 **닫는 IOC-EV = 0건** 규율 확인. 사전 카운트
   "6"이 register line 264–269(001–006 전부 `EV-L1/3` 접두)와 **일치**(정정 불요·#13의 6→5와 대조)함을 재확인,
   "EV-L1-complete 주장 금지"가 §1·§4·§5·§6·§7에 일관 부착됐는지 self-consistency pass.
7. **truthy-sentinel 소비 계약(§4.7, #13 신규 교훈)**: `ConformanceResult`(CONFORMANT/NON_CONFORMANT/UNKNOWN)가
   non-empty StrEnum이라 `if result:`가 fail-open임을 확인하고, 소비 게이트 계약 `result is ConformanceResult.
   CONFORMANT`(+`bool|None`은 `is True`)가 §5·§6 전 술어에 명문화·§7 회귀됐는지 확인(spg `predicates.py:466` `is
   not True⇒reject`·#12 line 969–970 `is True` 선례 대조). **본 문서 최대 신규 봉합 지점**.
8. **compiler-determinism property(§4.2/§5.2/§7)**: 동일 입력 ⇒ 동일 canonical digest·hidden-input 부재(clock/
   random/locale/env/float/network/latest-registry/SDK-default)·denial-is-total(fallback 없음)·generation-fence가
   hermetic property로 실현되고 IOC-INV-002 line 161과 대조되는지. `EVL1ProvisionalCanonicalizer` 잠정성 확인.
9. **fail-closed·∅-공허 양방향(§4.7)**: absent envelope⇒construction 불가·빈 축⇒`NON_CONFORMANT`·missing
   required-authority-scope⇒`UNKNOWN`(zero/wildcard 아님, §14 line 374)·빈 envelope⇒not-dominated·None magnitude⇒
   거부, **각각 금지+허용 canary 둘 다** 확인(#6 fail-open·#10/#12 ∅-void 교훈). 금지 동사(default/alias/substitute/
   coerce/reduce/widen/narrow/mutate/headroom/expire/revive) 커버리지 대조.
10. **economic-effect dominance·numerical safety(§4.3/§5.5)**: committed dominance·compiler-confidence/label이
    envelope 축소 못 함(§13 line 343)·NaN/overflow/negative-zero⇒거부·`CanonicalDecimal` 구성-거부(#12 NaN 선례
    대조) 확인.
11. **소유권 분할(§3.5)**: ioc가 rcl capacity commit(`grant_authorizes_exact_request`)·are risk projection
    (`adverse_increment`)·IAP approval·venue admissibility·brokercap capability·serializer/signer/final-egress를
    **재저작하지 않음** 확인(#8·#11·#12·#13 권위 중복 교훈).
12. **실측-원천·phantom 0**: 전 인용 타입(`Proposal`·`AggregateRiskDecision`·`CapacityVector`·`proposed_adverse_
    increment`·`GrantDecisionRef`·`DecisionContextCapsule`·`CriticalInputSnapshot`·`intent_identity`·`IntentState`·
    `TransmissionAttemptState`·`BrokerCapabilityProfile`·`ProfileVersion`·`ReplaceSemantics`)이 실코드에 존재함을
    grep 재확인(#10 MAJOR phantom 교훈 — 인용 전 실측). IOC-INV(14)·IOC-AC(12)·IOC-EV(12) 수·seam 라인이 원문/코드와
    일치.
13. **bounds 실측(§8.1)**: IOC-owned 3 profile 키(`B_order_conformance_invalid_to_egress` line 261·`MAX_canonical_
    broker_command_age_ms` line 713·`MAX_order_conformance_proof_age_ms` line 714)가 **전부 실재·null**(candidate
    신규 키 0건)임을 `measurement_source` 전수 확인(over-claim 아님 — #10 lesson; #12 4-key 누락과 대조). 합성용
    `B_capability_claim_to_send`(line 163)은 ADR-002-007 소유임을 재확인.
14. **broker-agnostic·숫자 하드코딩 0·firewall(§0.3)·verbatim 전사(§2.2)** 확인. `.importlinter` forbidden 계약이
    `tos.ioc`를 무수정 자동 포섭(source=tos)함을 재확인(line 29–43 실측).
15. **비-acceptance**: 어떤 IOC-EV/ADR acceptance·restricted-live·production도 선언 안 함(§0.2)·Independent-Safety-
    Reviewer 하드 배제 확인·비준 기록 = "2026-07-26 운영자 위임 자동 비준(v1.1)".

**독립 리뷰어 공격 지점(open questions)**: (i) **`EconomicEffectEnvelope`=rcl `CapacityVector` REUSE**가 §13
dominance를 타입 수준으로 봉인하는지 vs IOC가 자체 envelope 좌표를 두고 are/rcl 좌표와 정합해야 하는지(are가
MaximumCredibleCommandEffect로 소비하는 좌표가 실제로 `CapacityVector`인지 ARE #13 §5.2 재확인 — REUSE의 전제).
(ii) **dsl §8 이연 착지**를 `ApprovedIntentContract`(-020)로 둔 판정이 정확한지 vs `ApprovedIntentContract`가 dsl
`Proposal`의 superset이어야 하는지 아니면 digest 참조로 충분한지(§0.4d·§3.5 — approval/registration -023 경계와의
정합). (iii) **`tos.ioc` 명명**의 Immediate-Or-Cancel 오독이 수용 가능한지 vs `tos.conformance`(§0.4a). (iv)
**truthy-sentinel 소비 계약**을 설계 단계에 명문화한 것(§4.7)이 충분한지 vs `ConformanceResult`를 애초에 bool-불가
타입(예: `CONFORMANT`만 truthy가 아닌 sentinel)으로 설계해 구조적으로 봉해야 하는지 — #13 신규 교훈의 정확한 실현
지점. **[v1.1 판정: 구조적 봉인 채택 — `__bool__` ⇒ TypeError(리뷰 M1); 산문 계약은 보조]**. (v) core 6행이 실제로 전부 L1-decidable substrate를 갖는지(특히 001 `+Broker`·002 `+Security`의 L1 부분과
+overlay 분리·§10 alias registry의 Phase-0 경계가 정확한지). (vi) `mutation_fence_holds`(§6.2)를 "구조적 불변성
술어(frozen)"로 L1화하고 actual-outbound 비교를 런타임 이연한 경계가 정확한지 vs post-proof mutation 탐지 일부가
L1-decidable인지(#7 under-realization 인접). (vii) orthostate Intent/Attempt seam을 "전용 슬롯 없는 state-의존"으로
정직 이연(§3.4 (d))한 판정이 under-realization인지 정확인지(orthostate records에 전용 ioc-command 필드를 신설해야
하는지 — #13 orthostate 판정과 동일 구조). (viii) `compiler_deterministic` property를 `EVL1ProvisionalCanonicalizer`+
모델 compiler로 검증하는 것이 프로덕션 compiler 계약을 충분히 확정하는지 vs canonical scheme Phase-0 확정 전에는
property가 vacuous한지(§4.2 honest boundary).
