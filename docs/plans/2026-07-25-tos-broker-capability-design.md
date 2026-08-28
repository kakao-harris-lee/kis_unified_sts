# 설계 문서 #10 — Broker Capability Requirements·Fallbacks 계약 (2026-07-25, v1.1)

> **문서 번호 규약**: #1 경계·import-firewall, #2 Decision Context Capsule, #4 Evidence
> Store, #5 Risk Capacity Ledger(RCL), #6 Safety Authority, #7 Live Authorization, #8
> Orthogonal Trading State, #9 Evidence·Reconciliation Confidence가 이미 존재한다(#3은
> folded; Trustworthy Time·DSL은 병렬 트랙 A/C로 완료). **#10 = 본 Broker Capability
> Requirements·Fallbacks 문서**이며 **ADR-002-004**를 실현한다. broker가 실제로 보증하는
> 것을 **버전 있는 evidence-backed Broker Capability Profile**로 표현하고, 그 Profile 위에서
> **capability 결핍이 live scope를 축소·금지**하는 술어(admissibility·fallback·version
> enforcement·drift·environment binding·Final Quantity Proof recipe)의 **순수·비전송·결정적
> 데이터 모델 + hypothesis property test**를 그린필드 `tos/src/tos/brokercap/`에 저작한다.
>
> **문서 지위**: kis_unified_sts 프로젝트 측 설계 계약. tos-spec에 대해 **non-normative**이며
> 스펙 텍스트(RFC/ADR/템플릿/프로파일)를 **변경하지 않는다.** **broker-agnostic 원칙(project
> memory `tos-spec-broker-agnostic`)**: 본 문서의 규범 텍스트는 **어떤 구체 broker(KIS 포함)도
> 명명하지 않는다.** Profile은 capability-**CLASS** 모델이며, 특정 broker의 실제 capability 값·
> 배치는 구현 트랙의 **non-normative Broker Capability Profile INSTANCE**(ADR-002-004 §21) 소관
> 이다. §13.15 composed-consequence도 capability-class 언어로만 표현한다(ADR line 798).
>
> **선행 문서(의존)**:
> - [설계 #1 — `tos/` 경계 & import-firewall 계약 (v2, 운영자 비준)](2026-07-20-tos-boundary-and-import-firewall-design.md).
>   본 계약의 모든 모델은 §2.4 레이아웃(전용 top-level 패키지)에 놓이고 §3.2 허용목록 안에서만
>   의존한다(§0.3). line 164 "naming은 load-bearing이 아니다 — 내부 세분화는 후속 설계 문서가
>   정의한다"에 따라 본 문서가 `tos.brokercap` 패키지 내부를 정의한다.
> - [설계 #4 — Evidence Store 계약 (v1.1, 비준·구현됨)](2026-07-20-tos-evidence-store-design.md)
>   + 코드 `tos/src/tos/canonical/`. **canonicalization/digest-binding substrate(`tos.canonical`)·
>   `FrozenModel`·`DigestBoundArtifact`·`IndependentIdArtifact`(이미 core)·`classify_record_pair`
>   (이미 core)·`ArtifactStatus`·**이미 core로 PROMOTE된 `CanonicalDecimal`**(설계 #9 §0.4c 실행
>   완료 — `tos/src/tos/canonical/__init__.py:56` 실측)를 REUSE**한다(재정의 금지). Profile의
>   `id=f(digest)` **미채택** 결정을 동형 상속한다(§2.1/§3.1).
> - [설계 #5 — Risk Capacity Ledger 계약 (v1.1, 비준)](2026-07-21-tos-risk-capacity-ledger-design.md)
>   + 코드 `tos/src/tos/rcl/`. rcl `INV-007`(`transition_allowed`의 `RELEASED` ← `FINAL_QUANTITY_
>   PROOF` cause only, `predicates.py:467`)은 본 문서가 정의하는 **Final Quantity Proof recipe의
>   최종 하류 소비자**다. brokercap은 `fqp_adequate` bool을 **생산**하고 rcl은 그것을(recon/
>   orthostate 경유) **소비**한다 — **직접 seam 아님·직접 edge 없음**(§3.4).
> - [설계 #7 — Live Authorization 계약 (v1.x, 비준·구현됨)](2026-07-25-tos-live-authorization-design.md)
>   + 코드 `tos/src/tos/liveauth/`. **본 문서의 중심 seam 하나**(§0.4b/§3.4): liveauth는 이미
>   `broker_capability_sufficient`(continuous-validity 10조건 中, `state.py:136`·`predicates.py:94`)·
>   `broker_capability_current`(re-arm variant 13전제 中, `predicates.py:137`)·`broker_capability_added`
>   (§14.1 expansion 10플래그 中, `state.py:206`·`predicates.py:152`)를 **주입 `bool|None`**으로,
>   `broker_capability_profile_version`을 **주입 `str|None` scalar**(`records.py:124`)로 **선언해
>   두었다.** brokercap은 그 플래그들의 **상류 producer**다 — **brokercap은 liveauth를 import하지
>   않고, liveauth도 brokercap을 import하지 않는다**(#9 recon→orthostate produced-bool seam과 동형).
> - [설계 #8 — Orthogonal Trading State 계약 (v1.1, 비준·구현됨)](2026-07-25-tos-orthogonal-state-design.md)
>   + 코드 `tos/src/tos/orthostate/`. **중심 seam 둘**(§0.4b/§3.4): (i) orthostate `BrokerOrderState`
>   (ADR-002-005 §7)는 "**established only from broker/venue evidence under Broker Capability Profile
>   (ADR-002-004); no internal component sets from assumption**"(#8 설계 line 414–415, ADR-002-005 §7
>   line 104)이며, orthostate `conservative_direction_ok(BROKER_ORDER, UNKNOWN→definite, basis)`
>   (`predicates.py:302`)의 "under profile" evidence 조건을 **enum-basis**
>   (`ConservatismBasis.BROKER_EVIDENCE_UNDER_PROFILE`, `vocabulary.py:211`; 주입 `bool|None` 아님)로 소비한다
>   (caller가 brokercap bool을 basis로 매핑 — §3.4; 명명은 #8 설계 line 791에서 상속하되 본 문서는 구현
>   실측명으로 정정); (ii)
>   `KnowledgeState → RECONCILED`는 "positive corroborating evidence + **FQP where broker involved
>   (ADR-002-004)**"(#8 설계 line 756)를 요구한다. brokercap은 이 둘의 상류 producer다 — **어느
>   방향 edge도 없음**.
> - [설계 #9 — Evidence·Reconciliation Confidence 계약 (v1.2, 비준·구현됨)](2026-07-25-tos-reconciliation-confidence-design.md)
>   + 코드 `tos/src/tos/recon/`. **중심 seam 하나**(§0.4b/§3.4): recon `ReleaseProofInputs.final_
>   quantity_proof_token: bool|None`(+Broker 이연)은 recon이 **주입 opaque token**으로만 담고, #9
>   §9.2 item 4가 그 **양성 proof 내용을 ADR-002-004(본 문서)로 명시 이연**했다("capacity-releasing
>   field의 FQP token의 양성 proof 내용(late-fill/correction semantics 포함)은 Broker Capability
>   Profile 소관"). brokercap이 그 token 내용을 **소유·정의**하고 `fqp_adequate` bool을 생산하며
>   recon이 소비한다 — **어느 방향 edge도 없음**. recon이 per-field conflict/negative-evidence/
>   conservative-bound 산술을 소유하고(broker-agnostic), brokercap은 그 산술에 **입력되는 broker-
>   semantics 판정**(cancel-ack≠FQP·absence=weak-negative·position≠truth)을 소유한다 — 소유권 분할
>   명시(§3.5, #8 C1 교훈 선제 봉합).
>
> **규범 원천**: `ADR-002-004` — Broker Capability Requirements and Fallbacks (Status: **Proposed**,
> **Version 0.2**, **1423 line**, Decision Type: Safety-Critical Architecture Decision). **Amends**
> RFC-002 Broker Adapter/reconciliation/execution/live-scope semantics(ADR line 10). **Depends On**
> RFC-000; RFC-001 **SAFE-020/021/024/025/033/040/043**; ADR-002-001 v0.2·ADR-002-002·ADR-002-003
> (ADR line 11). 매핑 대상 EV: `verification/EVIDENCE-REGISTER-002.md`의 **`BC-EV-001..022`(line
> 59–80 실측, 전부 `NOT_IMPLEMENTED`)**. 앵커: **`BC-INV-001..012`(§6)·`BC-AC-001..022`(§25)·
> `BC-EV-001..022`·§-clause·`SAFE-020/021/024/025/033/040/043`**. ADR-002-006(#9)과 **달리**
> ADR-002-004는 **자체 INV 시리즈(BC-INV-001..012)를 정의한다** — 따라서 본 문서는 그 BC-INV에
> 앵커하고 **새 INV 시리즈를 창작하지 않는다**(§0.4f; #6/#8이 자체 INV에 앵커한 것과 동형, #9가
> INV 부재로 AC/EV에만 앵커한 것과 대비).
>
> **비준 기록**: **2026-07-25 운영자 비준(v1.1) — §10.2 판단 지점 승인(seam plain-bool decoupled·BC-EV-020
> not-Phase-1 좌표 분류).** (v1.0 초안 → 독립 비평 리뷰 **REVISE**
> [CRITICAL 0·MAJOR 2·MINOR 2] 반영: MAJOR-1 orthostate BROKER_ORDER seam 실측 정정[`conservative_direction_ok`
> enum-basis]·MAJOR-2 §8 broker-INSTANCE 키 완전 재열거·MINOR-1 ADR line 범위·MINOR-2 conformance-class
> producer; fail-open·cross-section 모순·소유권 중복은 리뷰에서 부재 판정, 아키텍처 핵심 결정 불변; 상세
> §10.1 v1.1.) 효력: `tos/src/tos/brokercap/` Phase 1(EV-L1) 순수·비전송 모델 + property test 착수
> (`tos.canonical`·`tos.ordering` REUSE, **sibling edge 0건, PROMOTE 0건**). **BC-EV 0건 완결** —
> acceptance 주장 없음; §9.2 Phase-0 항목은 별도 게이트 유지. ADR acceptance는 오직 *실행된*
> evidence로만 온다(project memory `tos-spec-rfc-authoring-track`; ADR §30 Approval Gate·VER-002-001
> §5 "Registration is not execution. A written test is not evidence").
>
> **리뷰 이력(선제 봉합 defect class)**: 직전 시리즈 REJECT/REVISE — #6 v1.0 **REJECTED**(fail-open
> seam), #7 v1.0 **REVISE**(SAFE under-realization), #8 v1.0 **REJECT**(cross-section 모순: representability
> 를 coupling-cleanliness와 혼동 — C1); #6/#7/#9 세 건 모두 비준 후 transcription 에라타(부등호 방향·
> 필드명·class gloss)를 요했다. 본 문서가 **선제 봉합**한 defect class: (a) **§1 core-tier over-claim
> 방지** — BC-EV는 register 최소 레벨에 **EV-L1 슬라이스가 0건**(22행 전부 EV-L2+)이므로 #8의 "core
> tier 존재"가 아니라 **Time/#6/#7/#9의 "0건 완결" shape**다(§1 결정적 사실 1); (b) **fail-open seam
> 방지(#6 REJECT 교훈)** — 중앙 불변식이 *본질적으로* fail-closed(missing/unknown/contradictory/
> expired/unsupported ⇒ reduce/prohibit, ADR line 32)이므로, 이를 **구조로** 실현: `Admissibility`에
> "assume-admissible" 생성 경로 부재, 모든 producer가 **양성 증명에서만 `True`**·나머지 전부 restrictive,
> 각 가드에 both-ways canary(§4·§5·§6); (c) **fixture clean-vs-illegal 정합(#8 REJECT 교훈)** — property
> fixture 내부 정합 규율(§7): "VERIFIED로 선언된 declaration은 실제 evidence_reference를 보유", "undeclared
> dimension fixture는 진짜 부재(≠ `UNKNOWN`으로 선언)"; (d) **cross-section self-consistency pass** —
> §1 분류 ↔ §5/§6 술어 ↔ §7 test-target를 finishing 전 대조(C1 lesson); (e) **verbatim 전사**(§5.3
> 상태·§8 차원·§8.3 ack·§8.8 replace·§9 assurance·§10 class·§15.3 prohibited proofs — 에라타 defect
> class 방지); (f) **broker-agnostic** — 규범 텍스트에 구체 broker 부재. 수용 서명 게이트는 IMPLEMENTATION-
> PLAN-002 §3 하드 배제(Independent-Safety-Reviewer는 본 문서의 저자/통합자여서는 안 됨)를 따른다.

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. ADR-002-004 조항별 **Phase 1(EV-L1) 도달성 경계**(§1). `BC-EV-001..022`의 **predicate-only /
   not-Phase-1** **2분류**(NO core tier). **결정적 사실: BC-EV 22행 모두 register 최소 레벨이 EV-L2
   이상**(001·002·006·007·008·009·010·011·012·013·014·017 = `EV-L3/5`; 004·005·016·018·019 =
   `EV-L3`; 015·020 = `EV-L3+Security`; 021 = `EV-L2/3`; 022 = `EV-L2`; 003 = `Profile-dependent`;
   전부 `NOT_IMPLEMENTED`, line 59–80 실측)이라 **EV-L1 슬라이스가 0건**이다 — #8/RCL의 core-tier shape가
   **아니라** Time·#6·#7·#9의 **"EV 0건 완결"** shape다. **닫는 BC-EV = 0건**("EV-L1-complete 주장
   금지" 규율).
2. **Broker Capability Profile의 데이터 모델 계약**(§2): 버전 있는 digest-bound `BrokerCapabilityProfile`
   (IndependentIdArtifact) — `ProfileKey`(§7.1 10좌표 verbatim) + `ProfileVersion`(§7.2 7필드 verbatim) +
   **`tuple[CapabilityDeclaration]`**(차원별 선언) + `ConformanceClass`(§10) + `LiveScope`(§5.10/§21) +
   `tuple[FinalQuantityProofRule]`(§15). 어휘: `CapabilityDimension`(§8 **17종** verbatim)·`CapabilityStatus`
   (§5.3 **7종** verbatim)·`AssuranceLevel`(§9 **5종**)·`ConformanceClass`(§10 **4종**)·`AssuranceSource`
   (§5.4 **8종**)·`AcknowledgementState`(§8.3 **6종** verbatim)·`ReplaceSemantics`(§8.8 **5종** verbatim)·
   `Admissibility`(로컬 3종: ADMISSIBLE/REDUCED/PROHIBITED — ADR line 32 "reduce live scope or prohibit").
3. **missing/contradictory ⇒ reduce/prohibit 중앙 불변식**(§4.1, 중앙 — ADR line 32·gate-status line 133·
   BC-INV-001/008/010): `capability_admissible(profile, action_class, required) -> Admissibility`가 중앙
   술어다. **UNKNOWN/undeclared 차원 ⇒ most-restrictive(PROHIBITED)**(BC-INV-001 "not present and current
   ⇒ treated as unavailable"); **CONTRADICTORY/EXPIRED/UNSUPPORTED ⇒ PROHIBITED**; **VERIFIED 및 명시
   승인된 VERIFIED_WITH_RESTRICTION만 authorize**(§5.3 line 146 verbatim). "pick-the-permissive" 경로가
   **구조적으로 부재**하다.
4. **fallback 단조-restrictive 계약**(§4.2/§5.3, ADR §13): missing capability의 승인된 fallback chain은
   순수 술어로 실현하되 **fallback은 절대 capability를 INCREASE하지 않는다**(no fallback ⇒ PROHIBITED;
   fallback ⇒ REDUCED 또는 restricted-live만). ADR line 34 "explicit, conservative, measurable"·§13
   전체·§23.9 "Unsupported Capability with No Scope Reduction 기각".
5. **profile version enforcement 술어**(§6.1, BC-EV-021/BC-AC-021 substrate, BC-INV-008): stale/mismatched/
   expired profile version ⇒ **deny**(§7.2·§19 line 996 "capability has not degraded since authorization"·
   §22 "API version changes ⇒ suspend reliance"). 이 술어가 liveauth `broker_capability_current`·
   `broker_capability_sufficient`의 상류 producer다(§3.4 produced-bool seam).
6. **capability drift 술어**(§6.2, BC-EV-016/BC-AC-016 substrate, BC-INV-008, ADR §20): 관측 behavior가
   declared profile과 모순 ⇒ `drift_detected` ⇒ 영향 차원 **`CONTRADICTORY`로 restrict**(§20.2). **drift는
   절대 widen하지 않는다**(`apply_drift`는 status를 restrictive 방향으로만 이동 — never permissive; §7.5
   "safer interpretation"·§20.2 "deny affected live actions").
7. **Final Quantity Proof recipe 술어**(§6.3, §15 substrate, recon token producer): `fqp_adequate(rule,
   evidence_bundle) -> bool` — §15.3 **prohibited proofs**(cancel acknowledgement·one open-order query
   omission·local timeout·strategy cancellation intent·process restart·account position matching an
   expected value·operator assertion without broker evidence, **verbatim**) ⇒ **not adequate**; §15.2
   required result(final cumulative filled quantity ∧ zero remaining executable quantity ∧ correction/
   bust/late-event 처리 ∧ evidence provenance ∧ valid window) 충족 시에만 adequate. 이 bool이 recon
   `final_quantity_proof_token`·orthostate `RECONCILED`·rcl INV-007이 (caller 경유) 소비하는 값이다(§3.4).
8. **environment / credential-scope 좌표 모델**(§6.4, BC-EV-020/015 not-Phase-1 좌표, BC-INV-009): Profile은
   environment·credential_scope를 좌표로 담고(§7.1·§18), `environment_binding_ok`가 **cross-environment
   inheritance를 거부**(BC-INV-009 line 223 "Sandbox or paper capability evidence SHALL NOT automatically
   establish live capability"). **런타임 fencing/isolation enforcement(bypass 저항·물리 endpoint 격리)는
   +Security(ADR-002-013) 이연** — 좌표만 선언, 결정 술어 미완결(§1 not-Phase-1 분류).
9. **brokercap ↔ liveauth/orthostate/recon 경계(중심 아키텍처)**: brokercap은 **sibling edge 0건**을 유지
   한다(§0.4b/§3.4). brokercap은 admissibility·version·drift·FQP **bool을 생산**하고 liveauth/orthostate/
   recon은 그것을 **이미 선언한 주입 `bool|None`/`str|None` 플래그**로 소비한다(compose seam은 caller/미래
   Broker Adapter 런타임 소관). `tos.liveauth`·`tos.orthostate`·`tos.recon`·`tos.rcl`·`tos.evidence`·
   `tos.capsule`·`tos.time`·`tos.authority`·`tos.dsl` **미import** — brokercap은 `tos.canonical`·
   `tos.ordering`(둘 다 core)만 import한다(§0.3). **PROMOTE 0건**(CanonicalDecimal 이미 core).
10. **fail-closed 규율 + named canary**(§4·§5·§6): undeclared 차원 ⇒ most-restrictive; None/UNKNOWN ⇒
    PROHIBITED; contradictory ⇒ PROHIBITED(never pick-permissive); drift ⇒ restrict-only; fallback
    monotone-restrictive; cancel-ack≠FQP; cross-environment evidence ⇒ binding False; 각 가드에 both-ways
    canary.
11. **property-test 하네스 타깃**(§7, §1 분류 정렬 — 전부 predicate/coordinate substrate, 닫는 EV 0건) +
    import-closure 검증(§7.1) + run manifest 7항목(§7.2) + fixture clean-vs-illegal 정합 규율(#8 교훈).
12. **bounds 주입 계약 + 누락 프로파일 키 Phase-0**(§8): 실측 결과 **확정 신규 누락 distinct 키 0건**
    (ADR-002-004이 요하는 수치 — rate-limit budget·admission ceiling·polling detection bound·late-event/
    correction window·evidence-freshness/revalidation horizon — 은 전부 **broker-specific Profile INSTANCE
    측정값**이며 ADR §4 line 111–114가 명시 배제; Verification-Profile 측 broker 관련 키는 이미 존재·기계상)
    + broker-agnostic 이연 명시.

### 0.2 하지 않는 것 (경계·NO 목록)

- **ADR/스펙 비준·acceptance·restricted-live·production 어느 것도 승인하지 않는다.** ADR §30 Approval
  Gate("may move from Proposed to Accepted only when ... the profile schema and governance are implemented;
  at least one broker-specific profile is completed ... all Critical acceptance criteria pass"), line 1410
  "Until then, broker integrations remain paper, shadow, or explicitly non-production." ADR acceptance는
  오직 *실행된* evidence로만 온다.
- **Broker Adapter(런타임 egress 강제)를 구현하지 않는다.** ADR §19(Broker Adapter Enforcement)·§27
  (Implementation Constraints)는 **런타임 adapter**를 규정한다(transmit·retry·egress reject·evidence
  capture). Phase 1 brokercap은 Profile **데이터 모델 + 결정 술어**만 저작하며 **전송·재시도·egress 강제·
  evidence emit을 수행하지 않는다.** brokercap은 결정 bool을 **반환**할 뿐, 미래 Broker Adapter(런타임,
  EV-L3)가 그것을 enforce한다(#9 recon이 release proof bool만 생산·capacity 미release한 것과 동형·§4.5).
  **패키지 명명 `tos.broker` 기각**의 근거이기도 하다(§0.4a — operational client/adapter 함의 회피).
- **한 broker의 최종 capability 값·배치·conformance class 할당을 결정하지 않는다.** ADR §4 line 109–114
  ("does not decide: one broker's final capability values; exact polling intervals; exact request quotas;
  exact supported instrument list; ...")·line 118 "Those values belong in broker-specific Capability
  Profiles and Verification Profiles." brokercap은 **capability-CLASS 모델**만 저작하고, 특정 broker의
  status/level/값은 **non-normative Profile INSTANCE**(ADR §21, 구현 트랙) 소관이다. §13.15 composed-
  consequence class도 **broker 무명 capability-class 언어**로만 담는다(ADR line 798). broker-agnostic
  (project memory).
- **evidence persistence·custody·integrity·replay 메커니즘을 구현하지 않는다.** ADR §28 item 10/12
  (ADR-002-016 interface)·§30("ADR-002-016 ... durably retained and replayable"). BC-EV-022 Broker
  Evidence Replay의 **replay ENGINE은 ADR-002-016** 소관 — Phase 1은 결정을 재구성 가능케 하는 **frozen
  digest-bound Profile/decision 레코드 모델**만 담는다(§1 BC-EV-022 substrate). evidence 참조는 scalar
  (evidence_id/gen/digest)로만.
- **broker-side security enforcement(egress bypass 저항·credential 물리 fencing·network route isolation)를
  구현하지 않는다.** ADR §18(Session and Credential Architecture)·BC-AC-015/020은 **+Security 런타임**
  (ADR-002-013 Egress Gateway)이다. Phase 1은 environment/credential-scope **좌표만** 선언(§6.4); bypass·
  물리 격리 결정은 not-Phase-1(§1 BC-EV-015/020 분류).
- **numeric tolerance·rate quota·polling interval·detection bound·freshness horizon을 승인하지 않는다.**
  ADR §4 line 110–113·§16.2·§17.1. Phase 1은 전부 **주입 파라미터/flag**로 담고 **어떤 숫자도 하드코딩하지
  않는다**(CLAUDE.md). 값 부재 ⇒ fail-closed(§4.1). 값 승인은 Bounds-Approver 게이트(§8·§9.2).
- **aggregate KnowledgeState roll-up·per-action reconciliation·capacity mutation을 수행하지 않는다.**
  KnowledgeState 전이는 orthostate(#8) 소관, per-field confidence/conflict 산술은 recon(#9) 소관, capacity
  release는 rcl(#5) INV-007 소관 — brokercap은 각각에 **produced-bool로만** 공급한다(§3.4/§3.5). ADR §17.5
  line 947 "the active Broker Capability Profile supplies evidence and constraints but creates no action-flow
  capacity"의 정신 동형.
- **action-flow/rate accounting(ADR-002-022)·venue admissibility(ADR-002-019)·command construction
  (ADR-002-020)을 결정하지 않는다.** ADR §8.17 line 510–512·§17.5 line 947은 Profile을 이들의 **ceiling/
  input**으로만 둔다("A Capability Profile does not prove ... or create permission ... does not construct
  or authorize a command"). brokercap은 capability **evidence/constraint**만 제공한다.

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

brokercap 모델은 다음만 import한다:

- 서드파티: `pydantic`(frozen 모델), `pytest`·`hypothesis`(테스트만). **`numpy`/`pandas`/`pyyaml`도
  import하지 않는다** — capability는 StrEnum·boolean·집합 논리, 수치는 `Decimal`(`CanonicalDecimal`)
  산술뿐이라 수치 백엔드가 불필요하고, 모든 bound·quota·horizon은 주입 파라미터이며 YAML 파싱은 하네스
  (설계 #3) 소관이다(closure 최소화 — #5/#7/#8/#9 §0.3 동형).
- tos 자기 자신: `tos.canonical`(FrozenModel·DigestBoundArtifact·**이미 core인 IndependentIdArtifact**·
  **이미 core인 classify_record_pair**·`RecordPairKind`·`ArtifactStatus`·**이미 core인 `CanonicalDecimal`**
  — `__init__.py:47–64` 실측 §3.1), `tos.ordering`(profile-version append-only 순서 — §3.2), `tos.brokercap.*`.
  **`tos.liveauth`·`tos.orthostate`·`tos.recon`·`tos.rcl`·`tos.evidence`·`tos.capsule`·`tos.time`·
  `tos.authority`·`tos.dsl`을 import하지 않는다**(형제/상하류; scalar·주입 좌표·produced-bool로만 참조 —
  §3.4/§3.5).
- **`shared.config` 절대 금지**(설계 #1 §6.1, `.importlinter`): `shared.config.__init__`이
  `shared.config.secrets`(→ `os.environ`)를 무조건 전이 import한다. brokercap은 어떤 `shared.*`도 필요로
  하지 않는 순수 커널이다.
- **금지(직접·전이 모두)**: `shared.execution`, `shared.kis`, `shared.streaming`, `shared.llm`,
  `shared.storage`, `shared.backtest`, `services.*`, `cli.*`(설계 #1 §2.3; `.importlinter` forbidden set
  실측: `[importlinter:contract:tos-operational-firewall]` type=forbidden, source=tos).
- **firewall 구조 확인(실측)**: `.importlinter`는 **`forbidden` 계약 단일**(type=forbidden)이며 **`layered`
  계약이 아니다** — intra-tos sibling→sibling edge는 구조적으로 금지되지 않고 설계 #1 §3.2의 "자기 자신
  `tos.*`" 허용 조항이 이를 커버한다(#7·#8·#9 실측 결론 상속). 본 문서는 그럼에도 **sibling edge 0건**을
  **설계 규율**로 유지한다(§0.4b) — firewall 하드 규칙이 아니라 결합-최소화 주석이다.
- 이 배제를 능동 강제하는 것이 §7.1 import-closure 검증 테스트다(`import tos.brokercap` closure에 금지·
  `shared.config`·`os.environ`·numpy/pandas/yaml·**`tos.liveauth`·`tos.orthostate`·`tos.recon`·`tos.rcl`·
  `tos.evidence`·`tos.capsule`·`tos.time`·`tos.authority`·`tos.dsl`** 부재 assert; **`tos.canonical`·
  `tos.ordering`은 존재 허용**). required check(`tos-firewall`, `tools/tos_firewall_check.py` layer-① AST +
  `.importlinter` layer-② 전이 방어)와 함께 green이어야 본 선언이 능동 성립한다.

### 0.4 REUSE / import / 경계 결정 요지 (핵심 아키텍처)

**(a) 패키지 위치·명명 = `tos/src/tos/brokercap/`.** ADR-002-004는 "Broker Capability Profile"(§5.1)을
세우고 그 위에서 admissibility/fallback을 결정한다. 명명 대안 비교:

- **`tos.broker`(기각)**: **operational broker client/adapter로 오독**된다 — ADR §19/§27은 런타임 Broker
  Adapter(전송·egress 강제)를 별도로 규정하며, 본 Phase-1 모델은 그 adapter가 **아니라** adapter가 소비하는
  **capability Profile + 결정 술어**다(§0.2). `tos.broker`는 미래에 실제 broker 클라이언트가 놓일 이름과도
  충돌 소지가 있다.
- **`tos.capability`(기각)**: 지나치게 generic("무엇의 capability?"). liveauth의 continuous-validity·
  RCL capacity 등 다른 "capability" 개념과 혼동.
- **`tos.brokerprofile`(기각)**: 정확하나 verbose하고 terse 명명 관행(canonical/capsule/orthostate/rcl/
  recon/liveauth/authority/evidence/ordering/time/dsl)과 어긋난다.
- **선택 `tos.brokercap`**: **register prefix `BC`(=Broker Capability, `BC-EV`/`BC-AC`/`BC-INV`)·ADR §5.1
  "Broker Capability Profile"** 를 직접 명명, terse, operational-client 함의 회피. naming은 load-bearing이
  아니다(설계 #1 line 164) — 운영자 치환 가능; **load-bearing은 layering**(brokercap → canonical·ordering
  한 방향; liveauth·orthostate·recon·rcl·evidence·capsule·time·authority·dsl과 형제/상하류, **edge 0건**).
  내부 module(`vocabulary.py`·`records.py`·`predicates.py`·`_base.py`)은 liveauth/orthostate/rcl 선례 동형
  이며 **충돌 없음**(실측: `tos/src/tos/brokercap` 및 하위 부재 — §0 파일트리 확인).

**(b) brokercap = produced-bool producer, sibling edge 0건 (중심 결정).** brokercap은 세 소비자(liveauth·
orthostate·recon)와 한 하류 종단(rcl)의 **상류**다 — capability 결정 bool을 생산하고 그들은 **이미 선언한
주입 플래그**로 소비한다. 대안 비교(#9 §0.4b 형식):

- **대안 A — brokercap이 소비자(liveauth/orthostate/recon)를 import**: brokercap이 각 소비자의 typed 필드를
  참조해 "이 Profile이 이 전이/authorization을 허용" 류 술어를 노출. **기각**: (i) **backwards edge** —
  brokercap은 dataflow상 세 소비자의 **상류**(capability 판정을 생산 → 소비)인데 상류가 하류를 import하는
  것은 부자연스럽다. (ii) 세 개의 cross-sibling edge를 한 번에 만든다(시리즈가 최소화하려는 것). (iii)
  **cycle 위험**: 지금은 소비자들이 brokercap을 import하지 않아 acyclic이나, 누군가 소비자에서 brokercap
  status enum을 참조하면 즉시 cycle. (iv) 소비자들은 **이미** capability 조건을 주입 좌표로 봉인해 두었다 —
  liveauth 3종(`state.py:136` 등)·recon `final_quantity_proof_token`·orthostate `KnowledgeState`→`RECONCILED`은
  주입 `bool|None`, **orthostate BROKER_ORDER 차원만 enum-basis**(`conservative_direction_ok`, `predicates.py:302`)
  이며 caller가 매핑한다(§3.4) — typed target으로 바꿀 이유가 없다.
- **대안 B — 소비자가 brokercap을 import(방향 정합이나 세 edge 신설)**: liveauth/orthostate/recon이
  brokercap producer를 직접 호출. **기각**: 세 소비자 전부 **이미 비준·구현**됐고 capability 조건을 주입
  좌표(`bool|None` 또는 orthostate BROKER_ORDER의 enum-basis)로 두는 것으로 봉인됐다. 지금 세 곳을 brokercap 의존으로 바꾸면 세 ratified 패키지를 동시 접촉하며
  세 edge를 신설한다 — 과침습·비권장.
- **선택 — decoupled, plain-bool producer(edge 0건)**: brokercap은 **자신의 capability 어휘·Profile 모델·
  결정 술어**를 저작하고, 그 출력은 **plain `bool`/`str`**로 세 소비자가 **이미 선언한 주입 signature와 타입
  일치**한다(전부 `bool|None`/`str|None`·fail-closed). composition(brokercap 출력 → 소비자 주입 플래그)은
  **caller(미래 Broker Adapter/Reconciliation Service 런타임) 소관**이며 Phase 1 밖이다. 근거: (i) #9가
  recon→orthostate/rcl seam을 produced-bool로 봉인한 결정과 **완전 동형** — 일관성. (ii) edge 0건 —
  #9보다도 넓은 3-소비자 seam을 edge 없이 봉인. (iii) cycle 원천 차단. (iv) **compose seam-sealing**: 타입
  일치 + fail-closed 정합으로 seam이 조립되며, **test-only** 모듈이 brokercap·(각 소비자)를 **둘 다 import**해
  polarity·fail-closed를 대조할 수 있다(테스트 import는 §7.1 package closure에 계상되지 않음). **운영자 판단
  지점(§10.2)**: seam을 plain-bool decoupled(권장)로 둘지 대안 B(소비자 측 세 edge)로 갈지 — **decoupled
  권장**(edge·cycle 회피, #9 정합).

**(c) REUSE + PROMOTE 0건.** `BrokerCapabilityProfile`은 `tos.canonical.IndependentIdArtifact`(id⊥digest;
`_base.py:328`)·`DigestBoundArtifact`(digest 검증 `canonical_digest == H_ver(canonicalize(covered))`,
`_base.py:98`)를 REUSE한다. `CanonicalDecimal`은 **#9 §0.4c 실행으로 이미 `tos.canonical`에 존재**
(`__init__.py:56` 실측)하므로 quantity/price bound에 **추가 PROMOTE 없이** REUSE한다. classify_record_pair·
Ordering도 이미 core. ⇒ **PROMOTE = 0건, sibling edge = 0건**(#9가 CanonicalDecimal 1건 PROMOTE를 요한
것과 달리 본 문서는 그 후속이라 PROMOTE 부담이 없다). 기대치(orchestrator brief) "sibling edge 0, PROMOTE
0" 성립.

**(d) `id=f(digest)` 미채택 (canonical REUSE).** Profile은 **거버넌스-할당 identity**(profile version·
approver, §7.2)를 가지며, same-id/diff-bytes(위조·재제출·contradictory 재발행) 탐지에 `classify_record_pair`
(이미 core, `record_pair.py:52`, `RecordPairKind.CRITICAL_CONFLICT`)를 쓰려면 id⊥digest여야 한다(설계 #4·
#5·#6·#7·#8·#9 §3.1과 완전 동형; capsule의 content-addressed `id=f(digest)`와 정반대). ⇒ `IndependentIdArtifact`
채택, `IdDerivedArtifact` 미채택. `tos.brokercap._base`는 liveauth/orthostate 동형의 thin re-export shim.

**(e) `tos.evidence`·`tos.capsule`·`tos.time`·`tos.rcl`·`tos.authority`·`tos.dsl` 미import(형제/상하류).**
- **`tos.evidence` 미import(layering)**: brokercap은 **decision-side 상류**이고 evidence store는 **하류
  투영**이다. broker evidence의 retention·gap-check·replay는 **ADR-002-016** 소관(§0.2). evidence는 scalar
  (evidence_id/gen/digest) 참조로만 담는다. BC-EV-022 replay ENGINE 미소유.
- **`tos.capsule` 미import(다른 축)**: capsule `FieldState`(per-field **context** freshness, ADR-002-018)는
  Decision Context Capsule의 축이고, brokercap `CapabilityStatus`는 **broker capability 축**이다 — 별개
  좌표계. 토큰 겹침 없음(`VERIFIED`/`CONTRADICTORY` 등은 capsule/orthostate/recon에 부재)이라 #9식 축 붕괴
  위험은 낮으나, 별개 타입으로 로컬 저작하고 import하지 않는다.
- **`tos.time` 미import**: evidence freshness/expiry horizon·detection bound·revalidation interval = Profile
  INSTANCE + Verification Profile 소관(ADR §4·§16.2·§20.3)이므로 주입 opaque flag/scalar로만 담는다(rcl·
  orthostate·recon이 time 미import한 선례 동형).
- **`tos.rcl` 미import(하류 종단)**: rcl INV-007은 FQP recipe의 최종 소비자이나 brokercap→rcl은 **직접 seam이
  아니다** — 체인은 brokercap `fqp_adequate` → (caller) → recon `final_quantity_proof_token` → (caller) →
  rcl `transition_allowed(FINAL_QUANTITY_PROOF)`이며 전부 주입으로 매개된다. CanonicalDecimal은 canonical
  에서(§0.4c) — rcl 도달 불필요.
- **`tos.authority`·`tos.dsl` 미import**: Safety Authority capability(§19 line 989)·strategy DSL은 별개
  소관; authority-epoch currentness는 profile version currentness와 별개 축(주입 scalar 참조).

**(f) 불변식 명명 규약 — BC-INV 앵커, 새 INV 시리즈 창작 금지.** **실측**: ADR-002-004는 **자체 INV 시리즈
`BC-INV-001..012`(§6 line 189–236)를 정의한다.** ⇒ 본 계약은 모델 불변식을 **`BC-INV-001..012` / `BC-AC-001..022`
(§25) / `BC-EV-001..022` / §-clause / `SAFE-020/021/024/025/033/040/043`(Depends-On line 11)**에 앵커하고
**새 INV 시리즈를 창작하지 않는다**. 이는 #6(SA-INV)·#8(자체 dimension INV) 앵커와 동형이며, **#9가 INV
부재로 AC/EV에만 앵커한 것과는 상황이 다르다**(ADR-002-006엔 자체 INV가 없었음 — #9 §0.4f 실측; ADR-002-004엔
있음). self-consistency 최우선.

**(g) BC-EV = "0건 완결" shape (Time/#6/#7/#9-형; #8/RCL과 정반대).** #8은 STATE-EV-001(`EV-L1/2`)·STATE-EV-003
(`EV-L1/3`)이 register 최소 레벨에 EV-L1 슬라이스를 가져 **core tier**가 있었다. 본 문서의 BC-EV는 **22행 모두
최소 레벨 EV-L2 이상**(§1 실측)이라 **EV-L1 슬라이스가 0건**이다 — 따라서 §1 분류는 **core tier 없이
predicate-only / not-Phase-1 2분류**이고 "**BC-EV 0건 완결**"이다. 이 판정은 §1·§5·§6·§7 전체에 걸쳐 **일관**
해야 하며(어떤 §7 test-target도 core-tier나 BC-EV closure를 주장하지 않음 — #8 C1 lesson 선제 봉합), finishing
전 self-consistency pass에서 대조한다.

---

## 1. 범위 매핑 — ADR-002-004 조항별 EV-L1 도달성 (BC-EV 0건 완결)

EV-level 정의(VER-002-001): **EV-L1 = Model and Property Verification**(state-machine exploration, model
checking, property-based testing, deterministic simulation). **EV-L2 = Component Fault Test**, **EV-L3 =
Integration/Adversarial**, **/5 = System/Chaos**, **+Broker = Broker Capability Profile evidence**,
**+Security = security enforcement**. Phase 1은 EV-L1만이다.

> **결정적 사실 1 — core tier 부재("0건 완결" shape; #8/RCL과 정반대)**: `BC-EV-001..022`(register line
> 59–80 실측)의 **register 최소 레벨은 22행 모두 EV-L2 이상**이다(EV-L3/5 = {001·002·006·007·008·009·010·
> 011·012·013·014·017}; EV-L3 = {004·005·016·018·019}; EV-L3+Security = {015·020}; EV-L2/3 = {021};
> EV-L2 = {022}; Profile-dependent = {003}). ⇒ **EV-L1 슬라이스가 0건**이므로 #8(STATE-EV-001=`EV-L1/2`
> core tier)·#5(RCLP-EV core)와 **다르고**, Time "TIME-EV 0건"·#6 "SA-EV 0건"·#7 "REARM-EV 0건"·#9
> "RECON-EV 0건"과 **같은 "0건 완결" shape**다. 분류는 **predicate-only / not-Phase-1 2분류**(NO core tier).
>
> **결정적 사실 2 — authoring ≠ acceptance(닫는 BC-EV = 0건)**: Phase 1은 각 BC-EV의 **L1-decidable
> predicate/model substrate**(admissibility·fallback·version·drift·FQP-recipe·negative-evidence·좌표)를
> 저작하나 **어떤 BC-EV도 닫지 않는다.** (a) 최소 레벨이 EV-L2/L3(+Broker/+Security/Profile-dependent)이라
> fault injection·adversarial·chaos·broker-profile·security evidence가 필요하고, (b) VER-002-001 §5
> ("Registration is not execution. A written test is not evidence")·ADR §30 Approval Gate — 실행·아티팩트·
> 독립 리뷰가 필요하다. ⇒ **"EV-L1-complete 주장 금지"**(설계 #2·#4·Time·#5·#6·#7·#8·#9 §1 규율 상속).
> Owner/Reviewer는 register상 TBD.

**BC-EV ↔ BC-AC 1:1 대응**(실측): register `BC-EV-NNN`은 ADR §25 `BC-AC-NNN`과 제목·번호가 1:1이다
(예: BC-EV-001 "Broker Identity and Attribution" ↔ BC-AC-001 "Identity and Attribution"; BC-EV-022
"Broker Evidence Replay" ↔ BC-AC-022 "Evidence Replay"). 아래 표는 register 제목·최소 레벨·ADR 근거를
verbatim 인용한다.

| BC-EV | 제목(register) | 최소 (line) | Phase-1 분류 | L1 predicate/model substrate (닫지 않음) | ADR 근거 |
|---|---|---|---|---|---|
| **-001** | Broker Identity and Attribution | `EV-L3/5` (59) | **predicate-only** | `deterministic_attribution_available` vs 강제 containment fallback: order-identity 차원이 client-id echo/query·broker-id attribution을 증명하지 않으면 **ambiguous candidate ⇒ unattributed/contained**(time·price·qty·side match 단독 ⇒ deterministic 아님). concurrent/manual/ambiguous injection = EV-L3/5. | BC-AC-001, §5.5, §8.1, §13.1, §14 |
| **-002** | Lost Broker Acknowledgement | `EV-L3/5` (60) | **predicate-only** | `uncertain_send_policy`: idempotency 미증명 시 outcome-unknown ⇒ **no blind retry·no capacity release·no assume-rejection·UNKNOWN 유지(timeout 미release)**. ACK drop 자체는 전송(EV-L3/5). | BC-AC-002, BC-INV-002/003, §12.4, §1 line 43 |
| **-003** | Duplicate Submission | `Profile-dependent` (61) | **predicate-only** | `same_order_retry_allowed`: profile이 exact identity+window의 **deterministic idempotency를 증명**할 때만 network resend 허용; 아니면 **거부**. tier가 profile-dependent인 이유(idempotency 차원 status). idempotency 실증/adversarial = ≥EV-L2. | BC-AC-003, BC-INV-002, §8.2, §12.5 |
| **-004** | Fill Before Acknowledgement | `EV-L3` (62) | **predicate-only** | acknowledgement-semantics ladder(`AcknowledgementState` 6종) + fill-ordering 규칙: fills-may-precede-ack flag ⇒ fill을 idempotent 처리·**state-order로 reject 금지**. fault injection = EV-L3. | BC-AC-004, §8.3, §8.4, §22 |
| **-005** | Duplicate and Out-of-Order Fills | `EV-L3` (63) | **predicate-only** | fill-event 차원 모델(sequence·cumulative-vs-incremental·replay) + dedup-by-verified-identity 규칙(중복/재정렬 ⇒ cumulative 정확·double transfer 금지). replay/reorder injection = EV-L3. | BC-AC-005, §8.4, §22 |
| **-006** | Query Omission | `EV-L3/5` (64) | **predicate-only** | open-order-query 차원 모델 + **weak-negative 규칙**: 한 query/page/session/stream 부재는 FQP·release proof **아님**(no capacity release). recon(#9) negative-evidence 산술의 broker-semantics 입력. hide-then-reappear injection = EV-L3/5. | BC-AC-006, BC-INV-004, §8.5, §13.5 |
| **-007** | Cancel Crossing Fill | `EV-L3/5` (65) | **predicate-only** | cancellation 차원 모델 + **cancel-ack≠FQP 규칙**(crossing fill 가능·remaining 잔량 potentially-live 유지·late-event window). recon FQP token·§15.3 prohibited proof #1. concurrent fill injection = EV-L3/5. | BC-AC-007, BC-INV-005, §8.7, §13.6, §15.3 |
| **-008** | Late Fill and Correction | `EV-L3/5` (66) | **predicate-only** | late-event-window 술어: within-window ⇒ accept, beyond-window ⇒ **drift/contain**(profile 저하). window 값은 profile INSTANCE 주입. within/beyond injection = EV-L3/5. | BC-AC-008, §8.7, §13.6, §15.2/§15.4 |
| **-009** | Replace Semantics | `EV-L3/5` (67) | **predicate-only** | `ReplaceSemantics` 5종 분류 + overlap/gap 술어: non-atomic ⇒ overlap capacity 예약 또는 protection-gap을 unprotected risk로 표현·**둘 다 envelope 초과 시 fail-closed**. atomic/non-atomic path injection = EV-L3/5. | BC-AC-009, §8.8, §13.7 |
| **-010** | Reduce-Only or Exit Reversal | `EV-L3/5` (68) | **predicate-only** | reduce-only 차원 + target-position fallback 술어: reduce-only 미보장 시 target semantics·pending exit 포함·conservative 확인 position으로 cap·**position/pending 너무 불확실하면 autonomous exit 금지(reversal 방지)**. race injection = EV-L3/5. | BC-AC-010, §8.9, §13.8 |
| **-011** | External Activity Detection | `EV-L3/5` (69) | **predicate-only** | external-detection-bound 좌표(`B_external_detect`/`B_external_contain` 주입) + `missed_bound ⇒ deny-new-risk` 술어 + worst-credible-undetected sizing. 기존 `B_external_activity_detect` 키(§8). manual/3rd-party injection = EV-L3/5. | BC-AC-011, BC-INV-006, §16, §13.9 |
| **-012** | Polling Under Rate Pressure | `EV-L3/5` (70) | **predicate-only** | rate-class 모델 + admission-control 술어: ordinary traffic은 protective/reconciliation headroom 아래로 throttle; 미달 ⇒ deny-new-risk. saturation은 전송(EV-L3/5). | BC-AC-012, BC-INV-011, §17.1/§17.2, §13.4 |
| **-013** | Protective Request Under Saturation | `EV-L3/5` (71) | **predicate-only** | honest-guarantee 술어: shared global limit ⇒ protective capacity를 **`PRIORITIZED_ONLY`/`BEST_EFFORT`로만 분류(physical reserve 주장 금지)**. **§13.15 composed-consequence class**(단일 serialized 채널 ∧ no revocation ∧ shared global limit ⇒ partition-time HALT+escalation ⇒ CLASS-C/D 또는 scope 축소) 술어의 근거. saturation injection = EV-L3/5. | BC-AC-013, BC-INV-007, §17.3, §13.10, **§13.15** |
| **-014** | Session Failure and Reconnect | `EV-L3/5` (72) | **predicate-only** | session-model 차원 + identity-across-reconnect 술어: reconnect가 identity semantics를 바꾸면 **profile 무효화·revalidate까지 no retry**. reconnect-during-uncertainty injection = EV-L3/5. | BC-AC-014, §8.14, §22 |
| **-015** | Broker Credential Fencing | `EV-L3+Security` (73) | **not-Phase-1 (좌표 선언)** | Phase-1은 credential-scope/egress-fencing/revocation-latency **좌표만** 선언(§18.2 모델·§13.12 fallback 술어). **정의적 증거(BC-AC-015 stale identity가 final egress bypass 불가)는 +Security 런타임(ADR-002-013)** — L1 결정 술어 미완결. | BC-AC-015, BC-INV-010, §18.2, §13.12 |
| **-016** | Capability Drift | `EV-L3` (74) | **predicate-only** | `drift_detected(declared, observed)` + `apply_drift`(restrict-only): 관측 모순 ⇒ 차원 `CONTRADICTORY`·deny·contain·**never widen**. **중앙 Phase-1 술어.** contradiction injection = EV-L3. | BC-AC-016, BC-INV-008, §20, §7.5 |
| **-017** | Pagination and History Window | `EV-L3/5` (75) | **predicate-only** | pagination/history-window 좌표 모델(truncation·retention·omission bound = safety input). page-boundary/day-transition injection = EV-L3/5. | BC-AC-017, BC-INV-011, §8.5, §8.6 |
| **-018** | Position and Margin Conflict | `EV-L3` (76) | **predicate-only** | **position≠truth 규칙**(§23.4): 상충 position/fill/margin ⇒ conservative bound·contain(broker position을 absolute truth로 취급 금지). conservative-bound 산술 자체는 recon(#9) 소유 — brokercap은 "position≠truth" broker-semantics 판정만 공급. conflict injection = EV-L3. | BC-AC-018, §8.10, §22, §23.4 |
| **-019** | Corporate/Administrative Change | `EV-L3` (77) | **predicate-only** | corporate-event 좌표 + `authority_blocked_until_remap` 술어: non-trade quantity/identity change ⇒ remap·revaluation 완료까지 live authority 차단. non-trade injection = EV-L3. | BC-AC-019, §8.12, §13.13 |
| **-020** | Environment Isolation | `EV-L3+Security` (78) | **not-Phase-1 (좌표 선언)** | Phase-1은 environment/mode **좌표만** 선언(§7.1·§18.4); `environment_binding_ok`의 **cross-environment inheritance 거부(BC-INV-009)는 §5 admissibility에 실현**되나, **정의적 증거(BC-AC-020 test 자격이 live 제출 불가)는 물리 endpoint/route/account 격리 = +Security 런타임** — L1 결정 술어 미완결. | BC-AC-020, BC-INV-009, §18.4, §13.14 |
| **-021** | Profile Version Enforcement | `EV-L2/3` (79) | **predicate-only** | `profile_version_current(active, presented, expiry)`: stale/mismatched/expired ⇒ **deny**. **중앙 Phase-1 술어**·liveauth `broker_capability_current`/`broker_capability_sufficient` producer(§3.4). stale-version injection = EV-L2/3. | BC-AC-021, BC-INV-008, §7.2, §19 |
| **-022** | Broker Evidence Replay | `EV-L2` (80) | **predicate-only (model)** | frozen digest-bound append-only **Profile/decision 레코드 모델**(각 결정·fallback·FQP 결론을 durable evidence에서 재구성 가능케 함). **replay ENGINE 자체는 ADR-002-016**(not-Phase-1 mechanism) — Phase-1은 재구성 substrate 모델만. reconstruct injection = EV-L2. | BC-AC-022, §21, §27 |

**Phase-1 분류 요약**: **predicate-only(EV 주장 금지)** = {BC-EV-001..014, 016, 017, 018, 019, 021, 022}
**(20건)**. **not-Phase-1(좌표 선언·결정 술어 +Security 이연)** = {**BC-EV-015, BC-EV-020**}**(2건)**.
**core(L1 슬라이스)** = **{ } (없음 — BC-EV는 EV-L1 슬라이스 0건, §0.4g).** **닫는 BC-EV = 0건 완결.**
(20 + 2 = 22, self-consistency 확인.)

> **분류 판단의 대안 판독 인정(reviewer 판단 여지)**: BC-EV-020은 cross-environment-inheritance 거부
> (BC-INV-009)가 **L1-decidable** 술어(§5.3 admissibility가 environment 불일치 evidence를 거부)이므로
> **predicate-only로 읽을 여지**가 있다. 본 문서는 BC-EV-020/015의 **정의적 acceptance 증거(BC-AC-015/020)가
> +Security 런타임(bypass 저항·물리 격리)**이라는 점을 근거로 **not-Phase-1(좌표 선언)로 분류**한다. 이
> 구분은 **safety-neutral**하다: 어느 분류든 (i) Phase 1은 BC-EV를 0건 닫고, (ii) 좌표 default가 fail-closed
> (environment/credential 미선언·불일치 ⇒ admissibility PROHIBITED, §4.1)라 미완결 enforcement가 자동으로
> permissive해지지 않는다. **[운영자/리뷰어 판단 지점 §10.2]**. #9 [m4] "대안 판독 인정" 패턴 동형.

> **규율 태그(모든 주장에 부착)**: "**predicate/coordinate substrate only; BC-EV-001..022 전부
> NOT_IMPLEMENTED — EV-L2/L3(+Broker/+Security/Profile-dependent) fault injection·adversarial·chaos·
> broker-profile·security evidence 대기. core tier 없음(EV-L1 슬라이스 0건). EV-L1-complete 주장 금지.**"
>
> **ADR-002-004 조항 → 모델 산출물 매핑**: §5.1–§5.10 정의 → §2 어휘·모델; §6 BC-INV-001..012 → §4 불변식;
> §7 Profile identity/governance → §2 `BrokerCapabilityProfile`·§6.1 version enforcement; §8 차원 → §2
> `CapabilityDimension` 17종·§8.3 `AcknowledgementState`·§8.8 `ReplaceSemantics`; §9 assurance → §2
> `AssuranceLevel`; §10 conformance → §2 `ConformanceClass`; §11 minimum gates → §5.2 admissibility gate;
> §12.4/§12.5 uncertain-send/retry → §5.4; §13 fallback matrix → §5.3 `fallback_admissible`·§13.15 → §6.5;
> §15 FQP → §6.3 `fqp_adequate`; §16 external detection → §5.5·§8 bounds; §17 rate/protective → §5.6·§6.5;
> §18 credential/environment → §6.4(좌표); §19 adapter enforcement → §0.2(런타임 이연)·§3.4(produced-bool);
> §20 drift → §6.2; §21 template → §2·§8(broker-agnostic 이연); §25 BC-AC-* → §7 하네스.

---

## 2. 데이터 모델 계약

**표현 원칙**: 모든 아티팩트는 **pydantic v2 frozen 모델**(`ConfigDict(frozen=True, extra="forbid")`,
`tos.canonical.FrozenModel` REUSE — `_base.py:73` 실측)로 저작한다. frozen은 append-only(ADR §21 auditable·
§27 replayable)의 레코드 수준 실현이며 **모델에는 update/delete 연산이 존재하지 않는다**(설계 #4 §2.0 규율
상속). enum 값·필드명은 ADR §5–§10의 용어를 **verbatim**으로 쓴다(스펙 용어 = 코드 용어, 설계 #1 §2.4;
에라타 defect class 선제 방지).

### 2.0 소유권 골격 — brokercap은 canonical의 하류, liveauth/orthostate/recon의 upstream-형제, rcl의 upstream 종단

brokercap이 **소유·저작하는 것**: capability 어휘(`CapabilityDimension`·`CapabilityStatus`·`AssuranceLevel`·
`ConformanceClass`·`AssuranceSource`·`AcknowledgementState`·`ReplaceSemantics`) + `BrokerCapabilityProfile`
digest-bound 레코드 + `CapabilityDeclaration`·`ProfileKey`·`ProfileVersion`·`LiveScope`·`FinalQuantityProofRule`
value + admissibility/fallback/version/drift/FQP/environment **술어**. **소유하지 않는 것**: 런타임 egress
enforcement(Broker Adapter, ADR §19/§27) · 한 broker의 값·class 할당(Profile INSTANCE, ADR §21) · evidence
retention/replay engine(ADR-002-016, scalar 참조만) · aggregate KnowledgeState 전이(orthostate, produced-bool)
· per-field conflict/bound 산술(recon) · capacity mutation(rcl INV-007) · numeric quota/horizon(Profile
INSTANCE + Verification Profile, 주입).

### 2.1 digest-bound / plain-frozen / value / reference 분류 (총괄)

| 아티팩트 | 종류 | id 필드(독립) | digest 필드 | covered / 내용 |
|---|---|---|---|---|
| `BrokerCapabilityProfile` (§5.1; §7; §21 template) | **IndependentIdArtifact + 독립 id** | `profile_id`(+`profile_version`) | `canonical_digest` | `ProfileKey`(§7.1) + `ProfileVersion`(§7.2) + `tuple[CapabilityDeclaration]` + `ConformanceClass` + `LiveScope` + `tuple[FinalQuantityProofRule]` + evidence-package 참조 scalar |
| `CapabilityDeclaration` (§5.2; §21 Capability Matrix) | **plain FrozenModel(value)** | — | — | `dimension: CapabilityDimension`·`status: CapabilityStatus`·`assurance_level: AssuranceLevel`·`evidence_reference`(scalar)·`restriction: str\|None`·`fallback_reference: str\|None`·`assurance_sources: tuple[AssuranceSource,...]` |
| `ProfileKey` (§7.1) | **plain FrozenModel(value)** | — | — | 10좌표 verbatim(§2.2-(6)) |
| `ProfileVersion` (§7.2) | **plain FrozenModel(value)** | — | — | 7필드 verbatim(§2.2-(7)) |
| `LiveScope` (§5.10; §21 Live Scope) | **plain FrozenModel(value)** | — | — | account/instrument/order-type/qty·risk limit/session/action-class/mode 좌표(§5.10 line 183 verbatim) |
| `FinalQuantityProofRule` (§15) | **plain FrozenModel(value)** | — | — | `order_type`·required-result flags(§15.2)·`prohibited_proofs: frozenset[ProhibitedProof]`(§15.3 verbatim)·late-event/correction 규칙 marker·stronger-proof marker(§15.4) |
| 주입 입력 `RequiredCapabilitySet`·`ObservedBehavior`·`BrokerEvidenceRef`·`PresentedProfileVersion` | **plain FrozenModel(injected)** | — | — | action-class별 required 차원 집합·drift 관측·evidence scalar·제시 버전 scalar |
| `CapabilityDimension`·`CapabilityStatus`·`AssuranceLevel`·`ConformanceClass`·`AssuranceSource`·`AcknowledgementState`·`ReplaceSemantics`·`Admissibility`·`ProhibitedProof` | **StrEnum(로컬 값 타입)** | — | — | (Profile/declaration/술어의 covered·산출 원소) |
| `CanonicalDecimal` (qty/price bound) | **REUSE core `tos.canonical`**(이미 존재) | — | — | (§0.4c — PROMOTE 불필요) |
| evidence / profile-version 참조 블록 | **plain FrozenModel(참조)** | id+generation+digest scalar | — | tos 미소유(ADR-002-016/021) |

> **`IdDerivedArtifact` 채택 아티팩트 = 0건. PROMOTE = 0건**(records substrate·CanonicalDecimal 전부 이미
> core). `BrokerCapabilityProfile`은 거버넌스-할당 profile identity(§7.2)를 가진다 — same-id/diff-bytes
> 위조·contradictory 재발행 탐지(`classify_record_pair`)에 id⊥digest 필수 ⇒ `IndependentIdArtifact`(이미
> core) 상속. `tos.brokercap._base`는 liveauth/orthostate 동형의 thin re-export shim(신규 형제 edge 없음).

### 2.2 어휘 (verbatim 전사 — 에라타 defect class 주의)

> **전사 규율**: 아래 enum 값·순서는 ADR 원문에서 **verbatim**이며, StrEnum 값 문자열은 스펙 토큰을 그대로
> 쓴다(설계 #1 §2.4). 각 블록 옆에 ADR line 실측을 병기한다.

**(1) `CapabilityStatus`(StrEnum) — ADR §5.3 (line 136–144), 7종 verbatim:**

```text
VERIFIED
VERIFIED_WITH_RESTRICTION
DOCUMENTED_NOT_VERIFIED
UNSUPPORTED
CONTRADICTORY
UNKNOWN
EXPIRED
```

§5.3 line 146 verbatim: "**Only `VERIFIED` and explicitly approved `VERIFIED_WITH_RESTRICTION` may authorize
live behavior.**" ⇒ §5.2 admissibility에서 **이 둘만 authorize**, 나머지 5종(DOCUMENTED_NOT_VERIFIED·
UNSUPPORTED·CONTRADICTORY·UNKNOWN·EXPIRED) 및 **미선언(undeclared) 차원**(BC-INV-001)은 restrictive.

**(2) `CapabilityDimension`(StrEnum) — ADR §8 (line 293–512), 17종 verbatim(§8.1–§8.17 제목):**

```text
ORDER_IDENTITY                    (§8.1  Order Identity)
SUBMISSION_IDEMPOTENCY            (§8.2  Submission Idempotency)
ACKNOWLEDGEMENT_SEMANTICS         (§8.3  Acknowledgement Semantics)
FILL_EVENTS                       (§8.4  Fill Events)
OPEN_ORDER_QUERY                  (§8.5  Open-Order Query)
ORDER_HISTORY_QUERY               (§8.6  Order-History Query)
CANCELLATION                      (§8.7  Cancellation)
REPLACE_OR_AMEND                  (§8.8  Replace or Amend)
REDUCE_ONLY                       (§8.9  Reduce-Only or Close-Only)
POSITIONS_BALANCES_MARGIN         (§8.10 Positions, Balances, and Margin)
ACCOUNT_EVENT_PUSH                (§8.11 Account Event Push)
CORPORATE_ADMINISTRATIVE_EVENTS   (§8.12 Corporate and Administrative Events)
RATE_LIMITS                       (§8.13 Rate Limits)
SESSION_CONNECTION_MODEL          (§8.14 Session and Connection Model)
CREDENTIALS_AUTHORIZATION         (§8.15 Credentials and Authorization)
BROKER_TIME                       (§8.16 Broker Time)
MARKET_INSTRUMENT_CONSTRAINTS     (§8.17 Market and Instrument Constraints)
```

**차원 수 = 17.** 각 차원은 `CapabilityDeclaration` 한 건으로 status·assurance·evidence·restriction·fallback을
담는다. **미선언 차원 ⇒ BC-INV-001("A broker property that is not present and current in the approved
Capability Profile SHALL be treated as unavailable", line 191) ⇒ most-restrictive**(§4.1). 차원 목록은
"required for the action class"에 대한 필요집합을 `RequiredCapabilitySet`(주입)이 지정하며, brokercap은 특정
action이 어떤 차원을 요구하는지 **하드코딩하지 않는다**(주입 — §11 minimum-live-gates도 profile/scope별).

**(3) `AssuranceLevel`(StrEnum) — ADR §9 (line 516–540), 5종 verbatim:**

```text
LEVEL_0_UNKNOWN                    (Level 0 — Unknown; live use prohibited)
LEVEL_1_DOCUMENTED                 (Level 1 — Documented; not operationally verified)
LEVEL_2_CONTROLLED_TEST_VERIFIED   (Level 2 — sandbox/controlled)
LEVEL_3_RESTRICTED_PRODUCTION      (Level 3 — controlled production, bounded risk)
LEVEL_4_CONTINUOUSLY_MONITORED     (Level 4 — verified + continuous drift check)
```

§9 line 540 verbatim: "Safety-critical live scope normally requires **Level 3 or Level 4** for the dimensions
it relies upon." ⇒ §5.2 admissibility는 required-level(주입 per scope)에 대해 `assurance_level >= required`를
검사하며 **required-level 미지정 ⇒ fail-closed(최고 요구로 취급)**.

**(4) `ConformanceClass`(StrEnum) — ADR §10 (line 544–584), 4종 verbatim:**

```text
CLASS_A_DETERMINISTIC_LIVE          (§10 CLASS-A — Deterministic Live)
CLASS_B_RESTRICTED_SERIALIZED_LIVE  (§10 CLASS-B — Restricted Serialized Live)
CLASS_C_PROTECTIVE_SUPERVISED_ONLY  (§10 CLASS-C — Protective or Supervised Only)
CLASS_D_NON_LIVE                    (§10 CLASS-D — Non-Live)
```

§10 line 546 verbatim: "Conformance classes summarize but do **not** replace dimension-level decisions."
§10 line 584 verbatim: "**A class cannot override a failed mandatory dimension.**" ⇒ §5.2 admissibility는
conformance class를 **요약 라벨로만** 취급하고 **차원 수준 판정을 우선**한다(class가 permissive해도 실패한
mandatory 차원이 있으면 PROHIBITED — canary §4.1). §11 minimum-live-gate 미달 ⇒ CLASS-D(line 607).

**(5) `AcknowledgementState`(StrEnum) — ADR §8.3 (line 322–329), 6종 verbatim:**

```text
TRANSPORT_RECEIVED
BROKER_RECEIVED
VALIDATED
ACCEPTED
WORKING
REJECTED
```

§8.3 line 331 verbatim: "**If one response code combines these states, the weakest safe interpretation
applies.**" ⇒ ack 매핑 술어는 결합 코드에 대해 **weakest state**를 반환(BC-EV-004 substrate). `ReplaceSemantics`
(StrEnum) — ADR §8.8 (line 386–391), 5종 verbatim:

```text
ATOMIC_REPLACE
CANCEL_THEN_NEW
NEW_THEN_CANCEL
BROKER_UNSPECIFIED
UNSUPPORTED
```

§8.8 line 394 "The profile SHALL define overlap and protection-gap behavior." ⇒ non-atomic(CANCEL_THEN_NEW·
NEW_THEN_CANCEL·BROKER_UNSPECIFIED·UNSUPPORTED) ⇒ §13.7 fallback(overlap 예약 또는 gap을 unprotected로;
BC-EV-009).

**(6) `ProfileKey`(FrozenModel) — ADR §7.1 (line 245–256), 10좌표 verbatim:**

```text
broker_id
api_product
api_version
environment
account_type
market
instrument_class
order_type
session_type
credential_scope
```

§7.1 line 258 "Broader profiles are permitted only when evidence proves semantic equivalence across the
broader scope." ⇒ Phase 1은 key를 **좌표로만** 담고 broadening 판정은 주입 evidence(미증명 ⇒ 좁은 scope).

**(7) `ProfileVersion`(FrozenModel) — ADR §7.2 (line 264–270), 7필드 verbatim:**

```text
immutable profile version
effective date
evidence package version
approver identity
expiration or revalidation date
superseded version link
change reason
```

⇒ 필드명: `profile_version`(immutable)·`effective_date`·`evidence_package_version`·`approver_identity`·
`expiration_or_revalidation_date`·`superseded_version_link`·`change_reason`. 전부 covered(digest preimage);
`profile_version`은 `profile_id`와 함께 독립 identity(§2.1). 날짜/시각은 **주입 scalar**(clock 미접근 — §3.5).

**(8) `AssuranceSource`(StrEnum) — ADR §5.4 (line 150–159), 8종:** official specification · broker
contractual statement · controlled sandbox test · controlled production probe · fault-injection result ·
observed live evidence · broker support confirmation · independent operational review. (declaration의
`assurance_sources`; sandbox-only sources는 §13.14로 live 미승격 — BC-INV-009.)

**(9) `Admissibility`(StrEnum, 로컬 3종) — ADR line 32 "reduce live scope or prohibit" 실현:**

```text
ADMISSIBLE    (all required dimensions VERIFIED/approved-restriction, level 충족, version current, no drift/contradiction)
REDUCED       (일부 결핍이나 승인된 fallback으로 restricted-live 가능 — smaller scope)
PROHIBITED    (missing/unknown/contradictory/expired/unsupported 또는 fallback 부재 — 해당 action 금지)
```

`Admissibility`에는 **"assume-admissible" 기본 생성 경로가 없다** — 술어만 산출(§4.1 fail-open 봉합). `ProhibitedProof`
(StrEnum) — ADR §15.3 (line 857–863), 7종 verbatim(§6.3):

```text
CANCEL_ACKNOWLEDGEMENT
ONE_OPEN_ORDER_QUERY_OMISSION
LOCAL_TIMEOUT
STRATEGY_CANCELLATION_INTENT
PROCESS_RESTART
ACCOUNT_POSITION_MATCHING_EXPECTED_VALUE
OPERATOR_ASSERTION_WITHOUT_BROKER_EVIDENCE
```

### 2.3 `BrokerCapabilityProfile` covered + self-exclusion (설계 #4 §3.3 상속)

covered(Layer-1) = `ProfileKey`(10) + `ProfileVersion`(7) + `tuple[CapabilityDeclaration]`(정렬) +
`ConformanceClass` + `LiveScope` + `tuple[FinalQuantityProofRule]`(정렬) + evidence-package 참조 scalar.
preimage 제외: `profile_id`·`canonical_digest`·`canonicalization_version`·`status`(ArtifactStatus lifecycle
마커)·파생 역참조. **TBD/null이 covered에 하나라도 있으면 pre-issuance(status=DRAFT), digest 불가**
(`_base.py:174` 부근·IndependentIdArtifact `_require_independent_id_when_issued` `_base.py:351`). `profile_id`
⊥ `canonical_digest`(§3.1).

> **핵심 설계 결정 — profile은 immutable version별 append-only(#7/#8 lifecycle-out-of-collision 상속)**:
> profile은 시간에 따라 **재발행**된다(§7.2 superseded link·§7.4 change control·§20.3 EXPIRED→revalidate).
> 만약 하나의 stable id에 mutable 선언을 담으면 정당한 revalidation(예: DOCUMENTED_NOT_VERIFIED→VERIFIED)이
> same-id/diff-bytes `CRITICAL_CONFLICT`로 **오탐**된다. ⇒ **각 profile version은 fresh `profile_id`(또는
> (profile_id, profile_version) 복합 독립 identity)를 가진 immutable 레코드**다. same identity + diff bytes
> ⇒ `CRITICAL_CONFLICT`(위조·재발행 위조만); 정당한 개정 ⇒ **새 version(superseded_version_link로 연결)**.
> version 순서는 `tos.ordering`(§3.2)로 담는다. **CONTRADICTORY status**(§7.5)는 declaration status로
> 표현하지 last-write-wins로 덮지 않는다.

---

## 3. canonical / ordering REUSE + liveauth/orthostate/recon(produced-bool seam) + rcl/evidence/capsule/time 경계

### 3.1 canonical REUSE + `id=f(digest)` 미채택 (설계 #4·#5·#6·#7·#8·#9 §3.1 상속)

`BrokerCapabilityProfile`은 `tos.canonical.IndependentIdArtifact`(`_base.py:328`)·`DigestBoundArtifact`
(digest 검증 `canonical_digest == H_ver(canonicalize(covered))`, `_base.py:98`)를 REUSE한다. canonicalizer는
`tos.canonical` registry + `EVL1ProvisionalCanonicalizer`(`ev-l1-provisional-0`) REUSE, **신규 canonicalizer
없음**(프로덕션 canonical form은 Phase-0, §9.2). qty/price bound는 **이미 core인 `CanonicalDecimal`**
(`__init__.py:56` 실측) REUSE — `1.0` vs `1.00`의 digest drift 차단(bare `Decimal` 금지). **`id=f(digest)`
(`IdDerivedArtifact`) 미채택**: §2.1 근거(거버넌스-할당 profile identity + same-id/diff-bytes 위조·재발행
위조 탐지 — `classify_record_pair`, `record_pair.py:52`, `RecordPairKind.CRITICAL_CONFLICT`). **PROMOTE = 0건**
(IndependentIdArtifact·classify_record_pair·CanonicalDecimal 전부 이미 core — #9가 CanonicalDecimal 1건을
PROMOTE 완료했기에 본 문서는 후속으로서 PROMOTE 부담 없음).

### 3.2 ordering REUSE (profile version append-only 순서)

profile version의 append-only 순서(§7.2 superseded link·§7.4 change control)는 신규 저작하지 않고
`tos.ordering`(Trustworthy Time 설계 §5로 PROMOTE 완료; 코드 `tos/src/tos/ordering/`, `__init__.py` 실측:
`Ordering`·`OrderingEvent`·`compare_order`, `tos.canonical`만 의존)를 REUSE한다. `profile_version` 순서·
supersession chain을 담는다. **wall clock은 순서를 만들지 않는다**(`tos.ordering` 규율) — brokercap은 clock을
읽지 않는다(§3.5). light REUSE(core 의존, 신규 edge 아님).

### 3.3 REUSE 요약 표

| substrate | 결정 | 근거 |
|---|---|---|
| `FrozenModel`·`DigestBoundArtifact`·`IndependentIdArtifact`·`ArtifactStatus` | **REUSE(core `tos.canonical`)** | §3.1; 신규 없음 |
| `classify_record_pair`·`RecordPairKind` | **REUSE(core, 이미 PROMOTE됨)** | §3.1; same-id/diff-bytes·contradictory 재발행 |
| `CanonicalDecimal`(+`_normalize_decimal`) | **REUSE(core, #9가 이미 PROMOTE)** | §3.1; qty/price bound·PROMOTE 불필요 |
| `Ordering`·`OrderingEvent`·`compare_order` | **REUSE(core `tos.ordering`)** | §3.2; profile version 순서 |
| capability 어휘·Profile 모델·admissibility/fallback/version/drift/FQP 술어 | **로컬 저작** | §0.4a/§2.2; ADR §5–§15 verbatim·decision-side |
| liveauth `broker_capability_*`·orthostate `BrokerOrderState` basis·recon `final_quantity_proof_token` | **미소유 — produced-bool/scalar로만 공급** | §3.4; 3-소비자 seam |
| Broker Adapter enforcement·broker 값/class 할당·evidence replay engine·numeric quota/horizon | **미소유 — 런타임/INSTANCE/ADR-002-016/Profile 이연** | §3.5; ADR §19·§21·§28·§4 |
| PROMOTE | **0건** | §3.1 |
| sibling edge | **0건** | §3.4 |

### 3.4 liveauth / orthostate / recon 경계 — produced-bool seam, sibling edge 0건 (중심 결정)

**(a) brokercap = produced-bool producer(§0.4b).** brokercap은 세 소비자를 **import하지 않고**, 그들이 소비할
**plain bool/scalar**를 생산한다. seam 계약(compose) — **소비자는 전부 이미 비준·구현됨**:

| brokercap 산출 (§5/§6) | 타입 | 소비처 (이미 비준·구현) | 소비 signature(실측) |
|---|---|---|---|
| `broker_capability_sufficient(profile, requested_scope)` | `bool` | liveauth continuous-validity | `broker_capability_sufficient: bool\|None`(`liveauth/state.py:136`; `_INJECTED_CONTINUOUS_CONDITIONS` `predicates.py:94`; None/False⇒invalid) |
| `profile_version_current(...)` ⇒ `broker_capability_current` | `bool` | liveauth re-arm variant 전제 | `broker_capability_current`(`liveauth/predicates.py:137`; `_VARIANT_ENVIRONMENTAL_PREREQUISITES`) |
| `broker_capability_added(profile, delta_scope)` | `bool` | liveauth §14.1 in-place expansion | `broker_capability_added: bool\|None`(`liveauth/state.py:206`; `_PROPORTIONAL_EXPANSION_FLAGS` `predicates.py:152`) |
| `active_profile_version(profile)` | `str` | liveauth authorization record | `broker_capability_profile_version: str\|None`(`liveauth/records.py:124`) — **scalar** |
| `active_conformance_class(profile)` | `str` | liveauth authorization record | `broker_conformance_class: str\|None`(`liveauth/records.py:125`) — **scalar (MINOR-2)** |
| `fqp_adequate(rule, evidence_bundle)` | `bool` | recon `ReleaseProofInputs.final_quantity_proof_token` **및** orthostate `KnowledgeState`→`RECONCILED` | `final_quantity_proof_token: bool\|None`(recon §6.1, +Broker 이연; #9 §9.2 item 4가 내용을 ADR-002-004로 이연) **및** `final_quantity_proof_where_broker_involved: bool\|None`(`orthostate/predicates.py:503`, `knowledge_transition_allowed`; recon `predicates.py:331` docstring 확증) — **둘 다 진짜 `bool\|None`** |
| `broker_evidence_admissible_under_profile(profile, evidence_ref)` | `bool` → **enum-basis 매핑** | orthostate BROKER_ORDER 차원 `conservative_direction_ok(BROKER_ORDER, UNKNOWN→definite, basis)`(`orthostate/predicates.py:302`; `basis: ConservatismBasis\|TransitionCause\|None` `:306`) | **주입 `bool\|None` 아님 — enum-basis(실측 정정).** caller가 bool을 basis로 매핑: `True` ⇒ `ConservatismBasis.BROKER_EVIDENCE_UNDER_PROFILE`(strong, `vocabulary.py:211`·`WEAK_BASES` 비포함) + actor `TransitionAuthority.BROKER_ADAPTER_EVIDENCE`(`vocabulary.py:187`); `False`/`None` ⇒ `None`/weak ⇒ 감소 차단 fail-closed(`predicates.py:352–355`) |

- **타입 정합 + fail-closed 정합(두 소비 형태 구분 — MAJOR-1 정정)**: brokercap 산출은 전부 `bool`/`str`
  (bool은 양성 증명에서만 `True`). 소비 형태는 **두 종류**다: **(A) 진짜 주입 `bool|None`** — liveauth 3종
  (`broker_capability_sufficient` `state.py:136`·`broker_capability_current` `predicates.py:137`·
  `broker_capability_added` `state.py:206`) + recon `final_quantity_proof_token`(§6.1) + orthostate
  `KnowledgeState`→`RECONCILED`의 `final_quantity_proof_where_broker_involved`(`orthostate/predicates.py:503`),
  전부 `None`/`False` ⇒ invalid/거부(fail-closed); + str scalar 2종(`broker_capability_profile_version`
  `records.py:124`·`broker_conformance_class` `records.py:125`). **(B) enum-basis(orthostate BROKER_ORDER
  차원만)** — `conservative_direction_ok`은 주입 `bool|None`이 아니라 `basis: ConservatismBasis|TransitionCause|
  None`(`predicates.py:306`)을 받으므로, **caller가 brokercap `broker_evidence_admissible_under_profile: bool`을
  basis로 매핑한다**: `True` ⇒ `ConservatismBasis.BROKER_EVIDENCE_UNDER_PROFILE`(strong basis; `WEAK_BASES`
  비포함이라 UNKNOWN→definite 감소를 허용), `False`/`None` ⇒ `None`(또는 임의 weak basis) ⇒ 감소 차단
  (`predicates.py:352–355`). **양쪽 형태 모두 fail-closed 보존** — (A)는 None/False⇒거부, (B)는 None/weak⇒
  감소 차단. **polarity 봉합(#6 fail-open REJECT 교훈)**: producer는 결코 "미판정 ⇒ True/strong-basis"로 새지
  않는다(§4.1). (A) 실측 확인: liveauth `predicates.py:88` 주석·recon `predicates.py:331` docstring
  ("orthostate consumes as ... `final_quantity_proof_where_broker_involved`"); (B) 실측 확인:
  `orthostate/predicates.py:302/306/352–355`·`vocabulary.py:187/211`. **이 (B) caller-매핑 명세가
  `test_seam_orthostate.py`(§9.1)를 실현 가능하게 한다.**
- **composition(런타임 배선) = caller 소관**: brokercap 산출 bool을 소비자 주입 플래그로 배선하는 **런타임**은
  **미래 Broker Adapter/Live-Authorization/Reconciliation Service**(EV-L3)가 한다. Phase 1은 #9의 seam 이연과
  **동형으로 런타임 배선을 이연**한다.
- **seam cross-check = MANDATED(test-only)**: Phase 1은 **test-only** 모듈(`tos/tests/brokercap/test_seam_
  liveauth.py`·`test_seam_orthostate.py`·`test_seam_recon.py` 류)에서 brokercap·(각 소비자)를 **둘 다 import**해
  brokercap 산출 bool의 **의미·polarity·fail-closed 거동**이 소비 signature 기대와 **일치함을 assert한다**
  (예: brokercap `broker_capability_sufficient`=False ⇒ liveauth continuous-validity 실패측; `fqp_adequate`=True ⇒
  recon `final_quantity_proof_token`=True로 release-proof 가능측; `broker_evidence_admissible_under_profile`=False ⇒
  orthostate BROKER_ORDER `UNKNOWN`→definite 거부측). **이 테스트는 package edge가 아니다** — 테스트 import는
  §7.1 `import tos.brokercap` package-closure에 **계상되지 않으므로** brokercap 런타임 패키지의 sibling-edge-0건은
  유지된다(#9 v1.1 강화 동형).
- **cycle 부재**: brokercap↛{liveauth,orthostate,recon,rcl} ∧ 그들↛brokercap(전부 capability 조건을 주입
  flag로 소비). CanonicalDecimal은 canonical에서(§3.1). acyclic 명백.

**(b) brokercap은 authorize/transmit/release하지 않는다(ADR §19/§27·§17.5 line 947).** brokercap은 결정
**bool만** 생산하고 egress transmit·capacity mutation·authorization issue 메서드가 **부재**하다(§4.5). 소비
authority(Broker Adapter/liveauth/rcl/orthostate)가 실제 action을 gate한다 — "the active Broker Capability
Profile supplies evidence and constraints but **creates no action-flow capacity**"(§17.5 line 947).

**(c) 운영자 판단 지점**: seam을 **plain-bool decoupled(edge 0건)**로 둘지 대안 B(소비자 측 세 edge)로 갈지 —
decoupled 권장(§0.4b; edge·cycle 회피, #9 정합).

### 3.5 rcl / evidence / capsule / time / authority / dsl 경계 — 형제/상하류, scalar·주입 좌표만, import 금지

§0.4e대로: **`tos.rcl` 미import**(FQP recipe의 최종 소비자이나 brokercap→rcl은 직접 seam 아님 — 체인
`fqp_adequate`→recon→rcl INV-007가 주입 매개; CanonicalDecimal은 canonical에서). **`tos.evidence` 미import**
(brokercap = decision-side 상류; evidence store = 하류 투영 — layering 역전 금지; retention/replay engine은
ADR-002-016); evidence는 scalar(evidence_id/gen/digest) 참조. **`tos.capsule` 미import**(`FieldState`는
per-field context freshness 축 — capability status 축과 별개). **`tos.time` 미import**(evidence freshness/
expiry horizon·detection bound·revalidation interval = Profile INSTANCE + Verification Profile 소관(ADR §4·
§16.2·§20.3)이므로 **주입 opaque flag**(`fresh_within_horizon: bool|None`·`version_not_expired: bool|None`,
None⇒보수) + `time_generation: int|None`/`profile_effective_marker` scalar로만 담음; rcl·orthostate·recon이
time 미import한 선례 동형). **`tos.authority`·`tos.dsl` 미import**(Safety Authority capability §19 line 989는
authority 소관·주입 scalar; strategy DSL 무관). §7.1 import-closure가 이 부재를 assert한다.

> **소유권 분할 명시(#8 C1 교훈 — cross-section 혼동 선제 봉합)**: BC-EV-006(query omission)·-007(cancel
> crossing)·-018(position/margin conflict)는 recon(#9)의 negative-evidence·FQP·conflict/`merge_conservative`
> 술어와 **인접**한다. 소유권 경계: **recon이 generic per-field confidence/conflict/conservative-bound 산술을
> 소유**(broker-agnostic)하고, **brokercap은 그 산술에 입력되는 broker-semantics 판정을 소유**한다 — "이
> cancel-ack은 FQP가 아니다"(§15.3)·"이 query 부재는 weak-negative다"(§13.5)·"이 broker position은 truth가
> 아니다"(§23.4). brokercap은 conservative-bound **수치 병합을 하지 않는다**(recon 소관); recon은 broker의
> FQP **내용을 정의하지 않는다**(brokercap 소관, #9 §9.2 item 4). 두 문서가 **같은 현상을 다른 좌표에서**
> 다루므로 중복·모순이 아니다(§4.4 좌표 비붕괴).

---

## 4. 불변식

모두 frozen 모델 구성-불변식(구성 실패) 또는 순수 술어(property)로 실현한다. **앵커는 BC-INV-001..012(§6)·
BC-AC-001..022(§25)·§-clause·SAFE-###**이며 **새 INV 시리즈를 창작하지 않는다**(§0.4f). **fail-closed
discipline**: 미선언/미증명/모순/만료에 대한 술어는 절대 vacuous ADMISSIBLE/True가 되지 않으며, live 허용은
*양성 증명*을 요구하고, 각 가드에 **both-ways canary**(가드가 실제로 발화함)를 붙인다.

### 4.1 missing/contradictory ⇒ reduce/prohibit 중앙 불변식 (중앙 — ADR line 32; gate-status line 133; BC-INV-001/005/008/010)

**중앙 결정**: "broker capability가 없거나·모르거나·모순이거나·만료거나·미검증이면 live scope를 줄이거나 해당
action을 금지한다." ADR §1 line 32 verbatim: "Missing, unknown, contradictory, expired, or unverified
capability evidence SHALL reduce live scope or prohibit the affected action." gate-status line 133: "missing
or contradictory broker capability reduces or prohibits live scope." 실현(구조적 3중):

1. **`Admissibility`에 permissive 기본값 부재**: `capability_admissible(...)`는 오직 **양성 조건 전부 충족**
   시에만 `ADMISSIBLE`을 반환한다 — required 차원이 전부 `VERIFIED`(또는 명시 승인된 `VERIFIED_WITH_RESTRICTION`,
   §5.3 line 146) ∧ assurance level 충족(§9 line 540) ∧ version current(§6.1) ∧ no drift/contradiction(§6.2).
   **하나라도 미달 ⇒ `REDUCED`(승인 fallback 존재 시) 또는 `PROHIBITED`.** "assume-admissible" 생성자·기본
   True 경로가 **존재하지 않는다**(#6 fail-open REJECT 교훈의 구조적 봉합).
2. **미선언 차원 = unavailable(BC-INV-001)**: `RequiredCapabilitySet`이 요구하는 차원이 profile의 declaration
   tuple에 **부재**하면 `UNKNOWN`과 동일하게 취급(most-restrictive) — line 191 "not present and current ...
   SHALL be treated as unavailable". declaration 조회는 **부재 ⇒ None ⇒ PROHIBITED**이며 "없으니 통과" 경로가
   없다.
3. **contradictory ⇒ never pick-permissive(BC-INV-005·§7.5)**: 한 차원에 status가 상충(예: 문서=VERIFIED,
   관측=UNSUPPORTED)하면 `CONTRADICTORY`로 표기하고 **safer interpretation을 적용·차단**한다(§7.5 line 289
   "applies the safer interpretation and blocks affected actions until resolved"). 두 선언 중 permissive한
   쪽을 고르는 경로가 부재.

**canary(both-ways)**: (a) 미선언/UNKNOWN/EXPIRED/UNSUPPORTED/CONTRADICTORY 차원이 required set에 있으면
`capability_admissible` = `PROHIBITED`(가드 발화; 절대 vacuous ADMISSIBLE 아님); (b) required 차원 전부
VERIFIED ∧ level 충족 ∧ current ∧ no-drift ⇒ `ADMISSIBLE`(양성 side — 가드가 정당한 통과를 막지 않음).
conformance class canary(§10 line 584): class=CLASS_A이나 mandatory 차원 하나가 UNSUPPORTED ⇒ 여전히
`PROHIBITED`(class가 override 못 함).

### 4.2 fallback 단조-restrictive 불변식 (ADR line 34; §13; §23.9; BC-AC-*)

- **fallback은 capability를 INCREASE하지 않는다**: `fallback_admissible(declaration, approved_fallback)`은
  결핍 차원의 승인된 fallback이 **더 보수적인 동작(작은 scope·serialize·contain·prohibit)**일 때만 True.
  fallback이 원래 없던 capability를 부여하는(widen) 입력 ⇒ **거부**. ADR line 34 "explicit, conservative,
  measurable, and tied to the affected authority and risk scope"·§23.9 line 1159 "Unsupported Capability
  with No Scope Reduction ... Rejected".
- **no fallback ⇒ PROHIBITED**: 결핍 차원에 승인된 fallback chain이 없으면 `REDUCED` 불가·`PROHIBITED`.
- **canary(both-ways)**: (a) capability를 늘리는 fallback 입력 ⇒ False(가드 발화); (b) 정당한 보수 fallback
  (예: §13.1 internal-attempt-id + serialize + contain) ⇒ True(REDUCED 경로 성립). §13.15 composed-consequence는
  §6.5에서 별도(fallback 합성이 protective envelope를 더 줄일 수 있음).

### 4.3 drift restrict-only 불변식 (ADR §20; §7.5; BC-INV-008; BC-EV-016)

- **drift는 restrict만, widen 없음**: `apply_drift(declaration, observed)`는 관측 모순 시 status를 **restrictive
  방향으로만** 이동(→ `CONTRADICTORY`)하고 assurance level을 낮춘다 — 절대 status를 permissive하게(예:
  UNKNOWN→VERIFIED) 올리지 않는다. §20.2 line 1022–1027 "mark affected dimension CONTRADICTORY; deny affected
  live actions; preserve potentially-live capacity; contain or halt". EXPIRED(§20.3)도 동일(evidence 만료 ⇒
  EXPIRED until revalidated).
- **canary(both-ways)**: (a) declared VERIFIED + observed duplicate-order-despite-idempotency ⇒ `drift_detected`
  True ⇒ `apply_drift` status=CONTRADICTORY(가드 발화); (b) observed가 declared와 일치 ⇒ drift False(정상
  side, 불필요 restrict 없음). widen 시도(observed가 "더 좋다") ⇒ status 상향 **불가**(구조적).

### 4.4 좌표 비붕괴 (capability status ≠ knowledge ≠ context freshness ≠ confidence)

- **별개 축**: brokercap `CapabilityStatus`(broker capability 축) / orthostate `KnowledgeState`(per-action
  aggregate) / capsule `FieldState`(per-field context freshness) / recon `FieldConfidenceClass`(per-field
  evidence confidence). brokercap 토큰(VERIFIED/CONTRADICTORY/EXPIRED/UNKNOWN/UNSUPPORTED/...)은 다른 세 축과
  **대부분 겹치지 않으나**(`UNKNOWN`은 orthostate BrokerOrderState·recon에도 존재), **별개 타입**이다.
- **비붕괴 성립 방식**: (i) **타입 구분**(별개 StrEnum 클래스) + (ii) **미import**(brokercap은 orthostate/
  capsule/recon을 import하지 않아 swap 자체가 원천 차단). canary: document-level 회귀로 `CapabilityStatus.UNKNOWN
  is not KnowledgeState.UNKNOWN`(둘 다 import하는 test-only 모듈에서 타입 identity). `CapabilityStatus`에
  `RECONCILED`/`VALID` 등 타 축 토큰 부재 회귀.
- **좌표 비붕괴 = §3.5 소유권 분할의 근거**: brokercap capability status는 "broker가 무엇을 보증하는가"이고,
  recon confidence는 "이 evidence를 얼마나 믿는가"이며, orthostate knowledge는 "이 action을 아는가"다 — 셋을
  한 필드에 담으면 축 붕괴(#6 §4.7·#8 §0.4e·#9 §4.2 상속).

### 4.5 representation ≠ enforcement (ADR §19/§27; §17.5 line 947)

`BrokerCapabilityProfile`·declaration·admissibility/version/drift/FQP bool은 **비전송·비-enforcing
representation**이다 — "order-identity VERIFIED" 기록이 order를 전송하거나 capacity를 release하지 않는다.
ADR §19은 **Broker Adapter**(런타임)가 enforce하고, §17.5 line 947 "supplies evidence and constraints but
creates no action-flow capacity", §27 line 1331 "prevent generic strategy code from invoking unprofiled
broker behavior"(런타임 egress). ⇒ brokercap에 **egress transmit·capacity mutate·authorization issue·
KnowledgeState set 메서드가 부재**(구성적 부재 — 설계 #9 representation≠mutation 정신 동형). brokercap은
결정 bool을 **반환**할 뿐 소유 authority가 enforce한다. 이 불변식이 evidence(하류 투영)·rcl·liveauth·
orthostate 미import(§3.5)의 근거이기도 하다.

### 4.6 uncertain-send / no-blind-retry 불변식 (ADR §1 line 36–43; §12.4/§12.5; BC-INV-002/003; SAFE-*)

- **uncertain transmission은 blindly retry되지 않는다(BC-INV-002)**: deterministic idempotency 또는 동등
  proof가 없으면 outcome-unknown transmission을 **새 broker order로 재시도 금지**(§12.4 line 640 "NO blind
  retry"). `same_order_retry_allowed`는 profile이 **exact identity+window의 idempotency를 증명**할 때만 True
  (§12.5).
- **unknown send는 potentially-live로 유지(BC-INV-003)**: ACK 상실은 rejection 증명이 아니다 — reservation·
  potentially-live quantity는 evidence로 해소될 때까지 유지(§1 line 39/42; line 43 "unresolved ambiguity
  remains UNKNOWN and cannot be released by timeout"). `uncertain_send_policy`는 {no-retry, no-capacity-release,
  no-assume-rejection, no-new-conflicting-in-containment, start-reconciliation, enter-UNKNOWN/CONTAINED}를
  순수 산출(§12.4 line 640–646 verbatim ladder).
- **canary(both-ways)**: (a) idempotency 미증명 + outcome-unknown ⇒ retry 거부·release 거부·UNKNOWN 유지
  (가드 발화; timeout으로 release 시도 ⇒ 여전히 거부); (b) idempotency 증명(exact identity+window) ⇒
  `same_order_retry_allowed` True(양성 side). BC-INV-004(weak negative): 한 query/page/stream 부재 ⇒ FQP 아님
  (§6.3와 연결).

### 4.7 append-only + same-id/diff-bytes 충돌 (§7.2/§7.5; §21; §2.3)

모델에 update/delete 연산 부재(§2.0). profile revalidation·개정은 새 version(새 identity)의 append로 표현
(superseded_version_link). same profile identity + diff canonical digest ⇒ `classify_record_pair` =
`CRITICAL_CONFLICT`(위조·재발행 위조만 — contain 양쪽 보존, no last-write-wins). CONTRADICTORY status(§7.5)는
declaration 값으로 표현. property: id⊥digest이므로 CRITICAL_CONFLICT reachable(가드 발화); id=f(digest)면
unreachable임을 회귀로 고정(§3.1).

---

## 5. capability-admissibility · fallback · uncertain-send 술어 세부 (BC-EV-001/002/003/009/010/011/012/013 substrate)

**핵심 난제**: `capability_admissible`을 **순수 함수**로 저작하되, (i) required 차원 집합·required assurance
level·approved fallback·idempotency 증명을 **주입 판정/파라미터**로 두어 하드코딩 수치·broker 값을 배제하고
(§8), (ii) **fail-closed(§4.1)를 구조로** 지키며(permissive 기본 부재), (iii) 미선언·UNKNOWN·모순·만료를
**most-restrictive**로 처리한다.

### 5.1 capability_admissible (§5.2/§11; ADR line 32 — 중앙 술어, BC-EV-001 substrate)

`capability_admissible(profile, action_class, required: RequiredCapabilitySet) -> Admissibility`:

| 입력 조건 | 산출 | 근거 |
|---|---|---|
| required 차원 전부 present ∧ status ∈ {VERIFIED, 승인된 VERIFIED_WITH_RESTRICTION} ∧ assurance_level ≥ required_level ∧ version current(§6.1) ∧ no drift/contradiction(§6.2) | `ADMISSIBLE` | §5.3 line 146; §9 line 540; BC-INV-008 |
| 결핍 차원이 있으나 **전부** 승인된 conservative fallback 보유(§5.3) ∧ fallback이 capability를 widen 안 함 | `REDUCED` | ADR line 45; §13 |
| required 차원 하나라도 미선언/UNKNOWN/EXPIRED/UNSUPPORTED/CONTRADICTORY ∧ 승인 fallback 부재 | `PROHIBITED` | BC-INV-001/005/008; §23.9 |
| §11 minimum-live-gate 미정의(주입 gate-set 미충족) | `PROHIBITED`(해당 scope CLASS-D) | §11 line 607 |

- **required는 주입**: 어떤 action_class가 어떤 차원·assurance level을 요구하는지는 `RequiredCapabilitySet`
  (주입)으로 온다 — brokercap은 하드코딩하지 않는다(§8). **required 미지정 ⇒ fail-closed**(전 차원 필요·
  최고 level로 취급).
- **status 게이트**: `VERIFIED` 및 **명시 승인된** `VERIFIED_WITH_RESTRICTION`만 authorize(§5.3 line 146
  verbatim). `VERIFIED_WITH_RESTRICTION`의 "명시 승인"은 declaration의 `restriction` + 주입 approval flag로
  판정(미승인 ⇒ 미달).
- **fail-closed**: 판정 불가·주입 flag None ⇒ 보수(PROHIBITED 쪽), 절대 ADMISSIBLE로 승격 안 함.
- **canary(BC-EV-001)**: (a) order-identity 차원 UNKNOWN + concurrent 후보 다수 ⇒ deterministic attribution
  미성립 ⇒ 해당 action PROHIBITED(ambiguous ⇒ unattributed/contained; §13.1·§14.2); (b) order-identity
  VERIFIED(client-id echo+query) ⇒ deterministic attribution 성립측.

### 5.2 broker_capability_sufficient / broker_capability_added (liveauth producer — BC-EV-021 계열, §3.4)

- `broker_capability_sufficient(profile, requested_scope) -> bool` := `capability_admissible(profile,
  requested_scope.action_classes, required) == ADMISSIBLE`. requested scope에 대해 REDUCED/PROHIBITED는 전부
  **not-sufficient(False)**다(요청 scope 그대로는 불충분). 이 bool이 liveauth `broker_capability_sufficient`
  (continuous-validity 10조건 중, `state.py:136`)를 채운다.
- `broker_capability_added(profile, delta_scope) -> bool`: §14.1 in-place expansion의 **enlarged scope**에
  대한 required 차원이 **현 profile에서 전부 VERIFIED** ∧ delta가 envelope 확대 없음일 때만 True(liveauth
  `broker_capability_added`, `state.py:206`). 확대 scope의 결핍 차원 ⇒ False.
- **fail-closed**: 어느 쪽도 미판정 ⇒ False(소비측 None/False⇒invalid와 정합, §3.4).

### 5.3 fallback_admissible — 단조-restrictive (§13 fallback matrix, BC-EV-002/009/010 substrate)

`fallback_admissible(declaration, approved_fallback: FallbackSpec) -> bool`: 결핍 차원의 승인 fallback이
**보수적**(작은 scope·serialize·contain·prohibit)일 때만 True. §13 매트릭스의 per-dimension fallback을 순수
술어로:

| 결핍 차원(§13.x) | 승인 fallback 요건(요약, verbatim 근거) | monotone 방향 |
|---|---|---|
| §13.1 no client-order-id | internal attempt id·no blind retry·serialize unresolved·query all evidence·ambiguous⇒unattributed·full reservation·contain | scope↓·contain |
| §13.3 no proven idempotency | no resend after uncertainty·new attempt only after non-acceptance proven·preserve reservation | retry 금지 |
| §13.4 no real-time fill push | bounded polling(reserved budget)·smaller limits·no release until polled final·degrade if bound missed | limit↓ |
| §13.6 weak cancel ack | remaining potentially-live·final cumulative+zero-remaining 확립·late-event window·late fills 처리 | release 지연 |
| §13.7 non-atomic replace | overlap capacity 예약 또는 gap을 unprotected로·둘 다 envelope 초과 시 fail-closed | reserve↑ / fail-closed |
| §13.8 no reduce-only | target-position semantics·pending exit 포함·conservative cap·너무 불확실하면 autonomous exit 금지 | exit 제한 |
| §13.10 shared global rate | protective를 PRIORITIZED_ONLY/BEST_EFFORT로만·ordinary admission 하향·degrade before headroom exhausted | reserve 주장↓ |
| §13.11 single session/HOL | bounded request duration·isolate local queues·reduce live scope if protective latency unbounded | scope↓ |
| §13.12 no rapid revocation | fenced egress 강제·no direct credentials in workers·offline protective ownership 금지 | offline authority↓ |
| §13.13 no corporate-action feed | independent reference·pre-session identity/qty checks·contain on unexplained remap·prohibit live until revaluation | authority 차단 |

- **canary(both-ways)**: (a) fallback이 결핍 capability를 **부여(widen)** ⇒ False(§4.2 가드 발화); (b)
  §13.1식 보수 fallback ⇒ True(REDUCED 경로). **no fallback ⇒ REDUCED 불가·PROHIBITED**.
- **fallback도 authorize하지 않는다**: fallback은 REDUCED(restricted-live) 최댓값이며, restricted-live 승인
  자체는 주입(independent safety review, ADR line 45·§7.3) — brokercap이 자체 승격하지 않는다(§4.1).

### 5.4 uncertain_send_policy / same_order_retry_allowed (§12.4/§12.5, BC-EV-002/003 substrate)

- `uncertain_send_policy(idempotency_proven: bool|None, ...) -> UncertainSendVerdict`: idempotency 미증명 +
  outcome-unknown ⇒ **{no_retry, no_capacity_release, no_assume_rejection, no_new_conflicting_in_containment,
  start_reconciliation, enter_unknown_or_contained}** 전부 산출(§12.4 line 640–646 ladder verbatim). 모든
  플래그가 restrictive이며 permissive 조합이 부재.
- `same_order_retry_allowed(profile, request_identity, retry_window) -> bool`: profile의 SUBMISSION_IDEMPOTENCY
  차원이 **exact identity+window의 deterministic idempotency를 VERIFIED**로 증명할 때만 True(§12.5 line 650
  "only when the profile proves deterministic idempotency for the exact request identity and retry window";
  line 652 "verify that retry cannot create a second broker order"). 미증명/UNKNOWN ⇒ False.
- **canary(both-ways)**: (a) idempotency UNKNOWN ⇒ retry False·policy 전부 restrictive(timeout으로 release
  시도해도 거부 — line 43); (b) idempotency VERIFIED(exact id+window) ⇒ retry True(양성 side).

### 5.5 external-detection / rate-admission 술어 (§16/§17, BC-EV-011/012 substrate)

- `external_detection_ok(detect_bound: int|None, contain_bound: int|None, observed_latency: int|None) -> bool`:
  주입 `B_external_detect`/`B_external_contain`(§16.2 line 889–890 `B_external_detect`/`B_external_contain`;
  기존 `B_external_activity_detect`/`B_external_activity_contain` 키, §8) 대비 observed가 bound 내일 때만 True.
  **missed bound ⇒ deny new risk**(§16.3 line 907–910; BC-INV-006). bound None ⇒ fail-closed.
- `rate_admission_ok(ordinary_below_ceiling: bool|None, protective_headroom_reserved: bool|None) -> bool`:
  ordinary traffic이 protective/reconciliation headroom **아래**로 admit될 때만 True(§17.2 line 926–933).
  **canary**: ordinary가 protective headroom을 잠식 ⇒ False(§17.2 가드). rate-recovery bound = 주입
  `B_rate_limit_recovery`[604, §8] (broker-INSTANCE, 하드코딩 없음).
- **query-omission weak-negative bound(BC-EV-006·BC-INV-004·§13.5)**: open-order query 부재를 non-existence로
  취급하지 않는 convergence window는 주입 `B_broker_query_consistency`[597, rationale "absence within it is not
  proof of non-existence (ADR-002-004)", §8]; window 내 부재 ⇒ weak-negative(confidence만 낮춤·terminal/release
  확립 불가), window None ⇒ fail-closed. brokercap은 이 bound를 **주입**으로만 담고 값을 하드코딩하지 않는다.

---

## 6. version-enforcement · drift · environment · FQP · composed-consequence 술어 세부 (BC-EV-021/016/020/015/007/013 substrate)

### 6.1 profile_version_current — version enforcement (BC-EV-021/BC-AC-021 substrate, BC-INV-008, §7.2/§19)

`profile_version_current(active_version: str|None, presented_version: str|None, not_expired: bool|None,
degraded_since_authorization: bool|None) -> bool`: **전부 양성**일 때만 True — active와 presented가 **일치**
∧ `not_expired`(§7.2 expiration/revalidation date 미도과, 주입) ∧ **`degraded_since_authorization`가 False**
(§19 line 996 "capability has not degraded since authorization"). 아래는 전부 **deny**:

- presented ≠ active(stale/mismatched) — §22 "API version changes ⇒ suspend reliance pending profile review"·
  §7.4 change control;
- `not_expired` False/None — §20.3 EXPIRED(evidence 만료 ⇒ revalidate까지);
- `degraded_since_authorization` True/None — BC-INV-008(capability degradation ⇒ block until re-approved).

이 bool이 **liveauth `broker_capability_current`**(re-arm variant 전제, `predicates.py:137`)의 상류이며,
`active_profile_version(profile) -> str`이 **liveauth `broker_capability_profile_version`**(`records.py:124`)를
채운다(§3.4). **canary(both-ways)**: (a) presented가 stale/expired/degraded ⇒ False(가드 발화; BC-AC-021
"stale or expired profile version ⇒ Broker Adapter must reject"); (b) 일치·미만료·미저하 ⇒ True(양성 side).

### 6.2 drift_detected / apply_drift — capability drift (BC-EV-016/BC-AC-016 substrate, §20, BC-INV-008)

- `drift_detected(declaration: CapabilityDeclaration, observed: ObservedBehavior) -> bool`: 관측이 declared
  차원 semantics와 모순이면 True. §20.1 line 1006–1016의 모순 목록(주입 관측 flag): duplicate order despite
  declared idempotency · event before states declared impossible · missing sequence · late fill beyond
  approved window · query omission beyond measured bound · unexpected rate limit · session behavior change ·
  unknown status code · unit/multiplier mismatch.
- `apply_drift(declaration, observed) -> CapabilityDeclaration`: drift 시 status를 **`CONTRADICTORY`로**
  (restrictive) 이동하고 assurance level을 낮춘다 — §20.2 line 1022 "mark affected dimension CONTRADICTORY".
  **restrict-only 불변식(§4.3)**: status/level을 permissive 방향으로 올리는 분기가 **부재**하다.
- **canary(both-ways)**: (a) declared VERIFIED + observed duplicate-despite-idempotency ⇒ `drift_detected`
  True ⇒ status CONTRADICTORY(가드 발화·deny affected live actions §20.2); (b) observed가 declared와 일치 ⇒
  False(정상 side·불필요 restrict 없음). widen 시도(observed "더 좋음") ⇒ 상향 **불가**(구조적). late-fill
  beyond-window(BC-EV-008)는 drift의 한 관측으로 흡수.

### 6.3 fqp_adequate — Final Quantity Proof recipe (BC-EV-007 계열·§15 substrate, recon token producer)

`fqp_adequate(rule: FinalQuantityProofRule, evidence_bundle) -> bool`: 아래를 **전부** 충족할 때만 True.
§15.2 required result(line 843–851 verbatim): broker order identity(또는 bounded unattributed effect) ∧
**final cumulative filled quantity** ∧ **zero remaining executable quantity** ∧ corrections/busts/late-events
treatment ∧ evidence source provenance ∧ valid history/query window(**주입 `B_final_quantity_proof`[569, §8]
FQP window** + late-event window **주입 `B_late_fill_observation`[576, §8]**; 값 하드코딩 없음) ∧
ordering/waiting rule. 그리고 §15.3
**prohibited proofs(line 857–863 verbatim)** 중 하나라도 유일 근거이면 **False**:

```text
cancel acknowledgement                          (§15.3; BC-INV-004/005)
one open-order query omission                   (§15.3; BC-INV-004)
local timeout                                   (§15.3; §1 line 43)
strategy cancellation intent                    (§15.3)
process restart                                 (§15.3)
account position matching an expected value     (§15.3; §23.4)
operator assertion without broker evidence      (§15.3)
```

§15.4(line 865–867): stronger broker-specific terminal event은 profile이 "no crossing fill or correction can
later change final quantity"를 **명시**하거나 bounded correction handling을 정의할 때만 accept — 이 조건도
`rule`의 주입 marker로 판정(미명시 ⇒ 불충분). 이 bool이 **recon `final_quantity_proof_token`**(§6.1, +Broker
이연)·orthostate `RECONCILED`(§8 line 140 "FQP where broker involved")·rcl INV-007(release ← FINAL_QUANTITY_PROOF)의
상류다(§3.4). **canary(both-ways)**: (a) cancel-ack만 ⇒ False; one-query-omission만 ⇒ False; position-match만 ⇒
False(각 prohibited proof 가드 발화); (b) final-cumulative+zero-remaining+corroborated provenance+valid window ⇒
True(양성 side). **brokercap은 conservative-bound 수치 병합을 하지 않는다**(recon 소관, §3.5) — FQP **충족 여부
bool**만 산출.

### 6.4 environment_binding_ok / credential-scope 좌표 (BC-EV-020/015 좌표, BC-INV-009, §18)

- `environment_binding_ok(evidence_environment: str|None, scope_environment: str|None, inherited: bool|None)
  -> bool`: evidence environment == scope environment ∧ `inherited`가 False(cross-environment inheritance
  아님)일 때만 True. **BC-INV-009(line 223 verbatim "Sandbox or paper capability evidence SHALL NOT
  automatically establish live capability")**·§13.14(sandbox/production divergence: "do not inherit capability
  status across environments")·§18.4(test/live distinct·non-interchangeable). 이 술어는 §5.1 admissibility에
  **결합**되어 environment 불일치 evidence를 거부한다.
- **credential-scope 좌표(§18.2)**: Profile은 credential_scope(§7.1)·read/trade 분리·revocation 동작·
  emergency disable(§18.5)을 **좌표로만** 담는다. `credential_scope_declared_ok`는 요청 scope ⊆ 선언 scope를
  **좌표 수준**에서 확인하나, **stale identity가 egress를 bypass하지 못함(BC-AC-015)의 런타임 증명은
  +Security(ADR-002-013)** — Phase 1 미완결(§1 BC-EV-015 not-Phase-1).
- **not-Phase-1 경계 명시**: BC-EV-015/020의 정의적 acceptance(bypass 저항·물리 endpoint/route/account 격리)는
  런타임 security enforcement다. Phase 1은 좌표 선언 + environment-inheritance 거부 술어까지이며 **결정 술어를
  닫지 않는다**(§1 분류·§0.2). **canary**: cross-environment evidence(sandbox evidence로 live scope) ⇒
  `environment_binding_ok` False(BC-INV-009 가드); same-environment + not-inherited ⇒ True.

### 6.5 partition_protective_class — §13.15 composed-consequence (BC-EV-013/016 coverage, no new EV)

§13.15(v0.2 추가)는 **composed fallback**이다: 세 차원이 동시에 약할 때 protective envelope가 더 붕괴한다.
brokercap은 이를 **capability-class 순수 술어**로 담는다(broker 무명 — ADR line 798):

- `partition_protective_class(profile) -> bool`: profile이 **{단일 serialized/HOL-blocking 채널(§13.11) ∧
  broker-side 즉시 session/credential revocation 부재(§13.12) ∧ shared global account rate limit(§13.10)}**을
  **동시** 만족하면 True(이 class 판정은 세 declaration의 status·fallback으로 순수 결정).
- `partition_class_scope_ok(profile, live_scope) -> bool`: 위 class이면 live_scope가 **unattended partition-time
  autonomous protection에 의존하지 않도록 축소**됐거나 profile이 **CLASS-C/CLASS-D**여야 True(§13.15 line 796
  "SHALL either reduce live scope ... or be classified CLASS-C / CLASS-D"). class이면서 scope 미축소 ∧
  CLASS-A/B ⇒ **False(PROHIBITED 유발)**.
- **broker-agnostic**: 이 술어는 §13.11/§13.12/§13.10 차원 status만 읽으며 **어떤 broker도 명명하지 않는다**
  (ADR line 798 "names no concrete broker"). 특정 broker의 class 포함 여부는 Profile INSTANCE 소관(§9.2).
  **register 영향 없음**(gate-status line 307: BC-EV-016/FD-EV-008/VTG-EV-010 coverage 내, no new EV).
- **canary(both-ways)**: (a) 세 차원 동시 약함 + CLASS-A + scope 미축소 ⇒ `partition_class_scope_ok` False
  (가드 발화); (b) 동일 class이나 CLASS-C 또는 scope 축소 ⇒ True(§13.15 준수측).

---

## 7. property-test 하네스 타깃

§1 분류에 정렬 — **전부 predicate/coordinate substrate, 닫는 BC-EV = 0건**(core tier 없음, §0.4g). property는
required-set·assurance-level·fallback·idempotency·bound·환경 flag를 **hypothesis 생성 주입값**으로 다뤄 "임의
유효 주입 하 보수적 성립"을 검증(특정 broker 값·수치 비의존, 하드코딩 없음 — §8).

> **fixture clean-vs-illegal 정합 규율(#8 REJECT 교훈 선제 봉합)**: property fixture는 **내부 정합**이어야
> 한다 — (i) `VERIFIED`로 선언된 declaration은 실제 `evidence_reference`·`assurance_level`을 보유(빈 evidence로
> VERIFIED는 illegal fixture); (ii) **undeclared** dimension fixture는 declaration tuple에서 **진짜 부재**
> (≠ `status=UNKNOWN`으로 선언된 것 — 둘은 §4.1에서 동일 취급이나 fixture 의미가 다르므로 구분해 생성);
> (iii) CONTRADICTORY fixture는 실제 상충 관측 쌍을 가짐. #8이 "fixtures declared both clean and illegal"로
> REJECT된 것을 방지.

| family | Phase-1 타깃 | substrate / 근거 |
|---|---|---|
| profile canonicalization + digest 검증 | **REUSE 설계 #4 must-pass suite**(`tos.canonical`) | §2.3·§3.1; frozen digest 일관성 |
| **capability_admissible 중앙 fail-closed** | **predicate** | §5.1; BC-EV-001. 미선언/UNKNOWN/EXPIRED/UNSUPPORTED/CONTRADICTORY ⇒ PROHIBITED; 전부 VERIFIED∧level∧current∧no-drift ⇒ ADMISSIBLE(both-ways); class가 실패 mandatory 차원 override 못 함(§10 line 584 canary) |
| status 게이트(VERIFIED/VWR만 authorize) | **predicate** | §5.1; §5.3 line 146. 5종 non-authorizing status ⇒ 미달; 미승인 VERIFIED_WITH_RESTRICTION ⇒ 미달 |
| **fallback 단조-restrictive** | **predicate** | §5.3; BC-EV-002/009/010. widen fallback ⇒ False; 보수 fallback ⇒ REDUCED; no fallback ⇒ PROHIBITED(both-ways) |
| uncertain_send / same_order_retry | **predicate** | §5.4; BC-EV-002/003. idempotency UNKNOWN ⇒ retry 거부·release 거부·UNKNOWN 유지(timeout 무효); VERIFIED exact id+window ⇒ retry 허용(both-ways) |
| external_detection / rate_admission | **predicate** | §5.5; BC-EV-011/012. missed bound ⇒ deny new risk; ordinary가 protective headroom 잠식 ⇒ False; bound None ⇒ fail-closed |
| **profile_version_current** | **predicate** | §6.1; BC-EV-021. stale/mismatched/expired/degraded ⇒ deny; 일치·미만료·미저하 ⇒ True(both-ways) |
| **drift_detected / apply_drift restrict-only** | **predicate** | §6.2; BC-EV-016. 모순 관측 ⇒ CONTRADICTORY; 일치 ⇒ no-drift; **widen 시도 불가**(구조) |
| **fqp_adequate (§15.3 prohibited proofs)** | **predicate** | §6.3; BC-EV-007. cancel-ack/one-omission/timeout/restart/position-match/operator-assertion 단독 ⇒ False; final-cumulative+zero-remaining+provenance+window ⇒ True(both-ways) |
| environment_binding_ok | **predicate** | §6.4; BC-EV-020. cross-environment evidence ⇒ False; same-environment not-inherited ⇒ True(both-ways) |
| **partition_protective_class (§13.15)** | **predicate** | §6.5; BC-EV-013/016. 세 차원 동시 약함 + CLASS-A + scope 미축소 ⇒ scope_ok False; CLASS-C/scope 축소 ⇒ True; broker 무명 |
| representation ≠ enforcement | **구성적 부재** | §4.5. egress-transmit·capacity-mutate·authorization-issue·KnowledgeState-set 메서드 **부재** |
| append-only + same-id/diff-bytes | **REUSE core `classify_record_pair`** | §4.7; CRITICAL_CONFLICT reachable(id⊥digest) — 재발행 위조 탐지 |
| 좌표 비붕괴 (4-axis) | **타입 identity 회귀(test-only)** | §4.4. `CapabilityStatus.UNKNOWN is not KnowledgeState.UNKNOWN`; RECONCILED ∉ CapabilityStatus |
| **seam cross-check (MANDATED, test-only)** | **cross-import 정합 회귀(test-only, NOT package edge)** | §3.4. brokercap 산출 bool(`broker_capability_sufficient`/`fqp_adequate`/`broker_evidence_admissible_under_profile`)의 polarity·fail-closed가 liveauth(`state.py:136`)·recon(`final_quantity_proof_token`)·orthostate(RECONCILED `final_quantity_proof_where_broker_involved` `predicates.py:503` + BROKER_ORDER enum-basis `conservative_direction_ok` `predicates.py:302`) 기대와 일치; §7.1 closure 무영향(test import) |

- **predicate-only** = {BC-EV-001..014, 016, 017, 018, 019, 021, 022}(20건; §1 요약과 동일 집합) +
  **좌표 선언(not-Phase-1)** = {BC-EV-015, 020}(2건). **core(L1 슬라이스)** = **{ } 없음.** **닫는 BC-EV =
  0건**(§1 규율). (env_binding_ok 행은 BC-EV-020의 BC-INV-009 좌표/inheritance 술어이며 BC-EV-020을 닫지
  않는다 — §1 후단 대안 판독 주석 정합.) required-set·level·fallback·idempotency·bound·환경 flag는
  hypothesis 주입, 하드코딩·broker 값 없음(§8).
- **self-consistency 규율(C1 lesson)**: 위 어떤 family도 "BC-EV core tier"·"BC-EV closure"를 주장하지 **않는다**
  — 전부 predicate/coordinate substrate이며 §1 "0건 완결"·§5/§6 술어 정의와 정합한다(finishing 전 대조 완료 —
  §10.1).

### 7.1 import-closure 검증 테스트 (설계 #4 §7.1·#6·#7·#8·#9 §7.1 상속)

서브프로세스에서 `import tos.brokercap`(및 `tos.canonical`·`tos.ordering`)만 한 뒤 `sys.modules`를 검사해 assert:
(1) 설계 #1 §2.3 금지 패키지 부재; (2) **`shared.config`·`shared.config.secrets` 부재**(전이 유입 런타임
포착); (3) `os.environ`/`os.getenv` 미참조; (4) **`numpy`·`pandas`·`yaml`(pyyaml) 부재**(bound/quota/flag
주입·YAML은 하네스 소관, §0.3); (5) **`tos.liveauth`·`tos.orthostate`·`tos.recon`·`tos.rcl`·`tos.evidence`·
`tos.capsule`·`tos.time`·`tos.authority`·`tos.dsl` 부재**(§3.4/§3.5 — 형제/상하류; produced-bool·scalar·주입
좌표로만 참조); (6) **`tos.canonical`·`tos.ordering` 존재 허용**(§3.1/§3.2 — core, sibling edge 아님).
required check(`tos-firewall`, `tools/tos_firewall_check.py` layer-① AST + `.importlinter` layer-② 전이 방어)와
함께 green이어야 §0.3 준수 선언이 능동 성립한다.

### 7.2 run manifest 정렬 (설계 #1 §5.1 7항목)

brokercap 전용 템플릿은 없으므로 설계 #1 §5.1 규율을 REUSE한다. evidence를 산출하는 모든 property-test run은:
(1) git commit digest + `tos` 버전; (2) 인터프리터 + 고정 의존성 버전(pydantic/hypothesis); (3) 실행 환경;
(4) 하네스 git digest; (5) **property-test seed**(hypothesis seed/derandomize, append-only); (6) **소비 설정
아티팩트 digest**(주입 required-set/assurance-level/fallback/bound/환경 프로파일 + `canonicalization_version` +
`tos.ordering` primitive 버전 + `CanonicalDecimal` 포함 `tos.canonical` 버전); (7) 산출 아티팩트 sha256.
(VER-002-001 §2.3 재현성·§9.1 seed·§9.2 digest의 EV-L1 부분집합.)

---

## 8. bounds 주입 + 누락 프로파일 키 Phase-0

`VERIFICATION-PROFILE-002.yaml`은 전체 `status: PROPOSED` 계열(배너 line 14 "Values below marked MEASURE are
deliberately left null pending broker-specific measurement"). ADR §4 line 110–113은 exact polling intervals·
request quotas·instrument list를 **본 ADR에서 배제**하고 broker-specific Profile/Verification Profile로 위임한다.

- **결정**: ADR-002-004 관련 수치(rate-limit budget·ordinary admission ceiling·polling detection bound·
  late-event/correction window·evidence-freshness/expiry·revalidation interval)는 **주입 policy 파라미터**로만
  들어온다. **어떤 숫자도·어떤 broker 값도 하드코딩하지 않는다**(CLAUDE.md·broker-agnostic). 값 누락 ⇒
  fail-closed(§4.1 미선언⇒PROHIBITED; §5.5 bound None⇒restrictive; §6.1 not_expired None⇒deny).

- **실측 확인(evidence-based) — 프로파일에 존재하는 broker-capability 관련 키**(**MAJOR-2 보완: v1.0 grep이
  560–610 블록을 누락**했음을 인정; 아래는 `measurement_source: broker_capability_profile` **완전 재열거** +
  ADR-002-004 명시 태깅 키, 키 명·line은 YAML 직접 인용):
  - `broker_capability_profiles: []`[26]: 승인 Broker Capability Profile **링크(identity)** — 수치 아님.
  - `B_external_activity_detect`[184]: `broker_capability_profile`·MEASURE. **ADR §16.2 `B_external_detect`와
    동일 키**(+`B_external_activity_contain`[191, source=reconciliation_log]). ⇒ BC-EV-011 기존 키 —
    **#8/#9 이미 계상, 재계상 없음**.
  - **`B_broker_query_consistency`[597]**: `broker_capability_profile`·rationale[601] **"absence within it is
    not proof of non-existence (ADR-002-004)"** — **ADR-002-004 명시 태깅**. ⇒ **weak-negative/query-omission
    bound**(BC-EV-006·BC-INV-004·§5.5·§13.5)의 기존 주입 키. `failure_response: CONSERVATIVE_UNKNOWN`.
  - **`B_final_quantity_proof`[569]**: `broker_capability_profile`·rationale[573] "Time within which Final
    Quantity Proof (final filled qty + zero remaining) can be established ... drives ... RELEASE_PENDING_PROOF".
    ⇒ **§6.3 `fqp_adequate`의 valid history/query window**(§15.2)의 기존 주입 키. `failure_response:
    QUARANTINE_UNKNOWN`.
  - **`B_late_fill_observation`[576]**: `broker_capability_profile`·rationale[580] "Maximum credible interval in
    which a late fill may still arrive after a claimed terminal state". ⇒ **§6.2 drift(late fill beyond window)·
    §6.3 late-event 처리**(BC-EV-008)의 기존 주입 키. `failure_response: PROFILE_CONTRADICTORY`.
  - **`B_rate_limit_recovery`[604]**: `broker_capability_profile`·rationale[608] "Recovery time after hitting
    the applicable broker account or session rate limit; protective/reconciliation traffic budget must survive
    this". ⇒ **§5.5 rate-admission·§6.5 §13.10**(BC-EV-012/013)의 기존 주입 키.
  - `B_protective_request_complete`[590]: `broker_capability_profile`·protective 완료 시간(ADR-002-001 §12) —
    §6.5 관여, 기존 키.
  - `B_startup_reconciliation`[198]·`B_capability_claim_to_send`[163, source=egress_journal_and_broker_transport_trace]·
    `B_egress_hard_fence`[170, ADR-002-013 +Security]·`B_venue_constraint_loss_detect`[240, ADR-002-019]: 기존 키,
    brokercap 미소유 또는 재계상 없음(§6.4 not-Phase-1 / 런타임 egress).

- **누락 distinct 키 (Phase-0 Bounds-Approver 플래그)**: 실측 대조 결과 —
  1. **구조 조항(capability status·admissibility·fallback·version·drift·FQP recipe·conformance class)에는
     numeric bound 부재** — 전부 enum·boolean·집합 논리·Decimal 산술이라 승인할 숫자가 없다.
  2. **ADR-002-004이 도입하는 수치 의존은 전부 broker-specific Profile INSTANCE 측정값**이다(rate quota·polling
     interval·late-event window·evidence expiry — ADR §4 line 110–113·§16.2·§17.1·§20.3이 명시 배제·위임).
     이들은 **Verification-Profile의 distinct 신규 키가 아니라 Broker Capability Profile INSTANCE**(ADR §21,
     구현 트랙, broker-agnostic)의 값이며, brokercap 규범 텍스트는 이를 **주입 opaque flag/scalar**로만 담고
     특정 키·값을 mandate하지 않는다.
  3. **기존 broker-관련 Verification-Profile 키**(위 완전 열거: `B_external_activity_detect`/`_contain`·
     `B_broker_query_consistency`·`B_final_quantity_proof`·`B_late_fill_observation`·`B_rate_limit_recovery`·
     `B_protective_request_complete`·`B_startup_reconciliation`·`B_capability_claim_to_send`·`B_egress_hard_fence`·
     `B_venue_constraint_loss_detect`)는 **전부 이미 존재·기계상**(대부분 `measurement_source:
     broker_capability_profile` = broker-specific INSTANCE 측정값)이며 #5–#9가 계상했다 — **재계상 없음**(중복
     계상 회피, 설계 #4/#5/#6/#7/#8/#9 §8 규율 동형). ⇒ **MAJOR-2 보완은 "확정 신규 누락 distinct 키 0건"
     결론을 유지·오히려 강화**한다(누락된 것처럼 보였던 키들이 실은 이미 존재하는 broker-INSTANCE 주입 키였음).

  ⇒ **확정 신규 누락 distinct 키 0건 + Phase-0 candidate 1군**(ADR-002-004 broker-capability-INSTANCE bound
  family = rate/admission budget · polling detection bound · late-event/correction window · evidence-freshness/
  expiry/revalidation — 전부 Profile INSTANCE 측정값, ADR §4/§16.2/§17.1/§20.3 위임). Phase 1은 전부 **주입
  opaque flag/파라미터**(§3.5)로 담는다. 값·키 승인은 Bounds-Approver 게이트(Live-Armer와 분리 — IMPLEMENTATION-
  PLAN §3)의 소관이다. **이 구분은 safety-neutral**하다: 값 부재/`None` ⇒ restrictive(§4.1/§5.5/§6.1)라
  미승인 bound가 자동으로 permissive해지지 않는다. [SAFE-025 conservative 정합; broker-agnostic]

---

## 9. 후속 작업 · Phase-0 인간 게이트 이관 항목

### 9.1 후속 구현 작업 (본 계약 위에서)

- **`tos/src/tos/brokercap/` 모델·술어·property·import-closure 테스트 저작**(§2–§7): 설계 #3(EV-L1 하네스)이
  property suite를 실행. `tos.canonical`(digest+id+classify+CanonicalDecimal) + `tos.ordering`(순서) REUSE,
  **신규 canonicalizer/ordering 없음, PROMOTE 0건, sibling edge 0건**(liveauth/orthostate/recon/rcl/evidence/
  capsule/time/authority/dsl 미import).
- **의존 방향**: brokercap ⟸ `tos.canonical`·`tos.ordering`(둘 다 core). acyclic 확인: canonical·ordering은
  brokercap 미참조.
- **compose seam(§3.4): 런타임 배선 이연 + test-only cross-check MANDATED**: brokercap 산출 bool
  (`broker_capability_sufficient`·`broker_capability_current`·`broker_capability_added`·`fqp_adequate`·
  `broker_evidence_admissible_under_profile`)을 liveauth 주입 조건·recon `final_quantity_proof_token`·orthostate
  `KnowledgeState`→`RECONCILED`의 `final_quantity_proof_where_broker_involved`(bool|None)·**orthostate BROKER_ORDER
  차원 `conservative_direction_ok` basis(caller가 bool→`ConservatismBasis.BROKER_EVIDENCE_UNDER_PROFILE` 매핑,
  §3.4)**로 배선하는 **런타임**은 **미래 Broker Adapter/Live-Authorization/Reconciliation Service**
  (EV-L3) 소관. 단 Phase 1은 **test-only cross-import 모듈**(brokercap·각 소비자 둘 다 import; polarity·
  fail-closed 정합 assert — 특히 `test_seam_orthostate.py`는 `broker_evidence_admissible_under_profile`=True ⇒
  `ConservatismBasis.BROKER_EVIDENCE_UNDER_PROFILE`(strong)·False/None ⇒ 감소 차단(`predicates.py:352–355`)의
  caller-매핑을 assert)을 **작성한다**(§3.4/§7). **이 test는 package edge가 아니다**(테스트 import는 §7.1
  closure 무영향; brokercap 런타임 sibling-edge-0건 유지).

### 9.2 Phase-0 인간 게이트로 넘기는 항목 (본 계약이 결정하지 않음)

1. **seam decoupled 유지(§0.4b/§3.4)**: brokercap↔{liveauth,orthostate,recon} seam을 plain-bool decoupled로
   둘지 대안 B(소비자 측 세 edge)로 갈지. **decoupled 권장**(edge·cycle 회피).
2. **프로덕션 canonical serialization·digest 알고리즘 선택**(설계 #4 §9.2 item 1과 동일 게이트):
   `ev-l1-provisional-0`·sha256은 비프로덕션.
3. **Broker Capability Profile INSTANCE bound family 값·키 승인**(§8; ADR §4/§16.2/§17.1/§20.3): rate/admission
   budget·polling detection bound·late-event/correction window·evidence-freshness/expiry/revalidation의 값 —
   Bounds-Approver ≠ Live-Armer. 기존 `B_external_activity_detect`/`_contain`·`B_egress_hard_fence` cross-ref.
   **broker-specific·broker-agnostic 규범 텍스트 밖.**
4. **한 broker의 실제 capability 값·status·assurance·conformance class 할당**(ADR §21 Profile INSTANCE): 특정
   broker(KIS 등)의 order-identity/idempotency/ack/fill/cancel/replace/rate/session/credential 실측·분류는
   **non-normative Broker Capability Profile INSTANCE**(구현 트랙) 소관 — brokercap은 capability-CLASS 모델만.
   §13.15 partition-protective-class에 특정 broker가 포함되는지 여부도 INSTANCE 판정.
5. **Broker Adapter 런타임 enforcement**(ADR §19/§27): egress reject·retry·containment·evidence capture·
   unprofiled-behavior 차단은 런타임(EV-L3) — Phase 1은 결정 bool만(§0.2/§4.5).
6. **broker evidence persistence·custody·integrity·replay engine**(ADR-002-016): BC-EV-022 replay 메커니즘 —
   Phase 1은 재구성 substrate 모델만; Evidence Store를 capability authority로 만들지 않음.
7. **+Security 런타임(BC-EV-015/020)**(ADR-002-013): credential fencing bypass 저항·environment 물리
   endpoint/route/account 격리·egress hard-fence — Phase 1은 좌표 + environment-inheritance 거부 술어만(§6.4).
8. **VER-002-001 §25 BC-AC-001..022 실행 evidence + 독립 리뷰**(저자 배제 — IMPLEMENTATION-PLAN §3).
   **닫는 BC-EV 0건이므로 acceptance 서명 없음** — EV-L2/L3(+Broker/+Security/Profile-dependent) fault
   injection·adversarial·chaos·broker-profile·security evidence는 Phase B.
9. **required-capability-set / minimum-live-gate 정의**(§11): 어떤 action_class가 어떤 차원·assurance level·
   minimum gate를 요구하는지의 승인된 매핑은 profile/scope별 주입 — Phase 1은 하드코딩하지 않고 hypothesis
   주입으로 property 검증(§5.1/§7).
10. **conformance class 승인 + restricted-live scope 승인**(ADR §7.3·§10·line 45): profile activation·
    independent safety review·CLASS 할당은 인간 게이트 — brokercap은 자체 승격하지 않음(§4.1/§5.3).
11. **cross-package 좌표 조정 의무(coordination)**: `CapabilityStatus`와 orthostate `KnowledgeState`/recon
    `FieldConfidenceClass`/capsule `FieldState`를 **동시에 담는 FUTURE 패키지**는 이들을 반드시 별개 typed
    필드로 유지(공유 raw-string slot 금지 — `UNKNOWN` 토큰 overlap이 StrEnum coercion으로 축 붕괴 재발). 본
    계약은 네 축을 import하지 않아 자체로는 안전하나, 좌표 overlap의 출처이므로 명시(#9 [m3] 동형).

---

## 10. 개정 로그 + 비준 체크리스트

### 10.1 개정 로그

- 2026-07-25: **v1.0 초안 최초 작성.** ADR-002-004 EV-L1 실현 계약. 설계 #1(경계·firewall)·#2(주입 flag·좌표
  어휘)·#4(canonical substrate + id⊥digest)·#5(rcl INV-007 FQP 소비자)·#7(**liveauth broker_capability_*
  producer seam**)·#8(**orthostate BrokerOrderState/RECONCILED producer seam**)·#9(**recon FQP token
  producer seam**·produced-bool 선례·bounds under-report 규율·좌표 비붕괴)에 정렬. 주요 결정:
  (§0.4a) 전용 패키지 `tos/src/tos/brokercap/`(`tos.broker`[operational-client 함의]·`tos.capability`[generic]·
  `tos.brokerprofile`[verbose] 기각 — register prefix `BC`·ADR §5.1 "Broker Capability Profile" 앵커);
  (§0.4b/§3.4) **brokercap = plain-bool producer, sibling edge 0건** — brokercap이 liveauth
  `broker_capability_sufficient`/`_current`/`_added`·orthostate BROKER_ORDER basis·recon `final_quantity_proof_
  token`의 상류 producer(세 소비자 전부 이미 주입 flag로 봉인·#9 §9.2 item 4가 FQP 내용을 ADR-002-004로 이연);
  대안 A(소비자 import·backwards edge)·B(소비자 측 세 edge 신설) 기각; (§0.4c/§3.1) **PROMOTE 0건**(CanonicalDecimal
  #9가 이미 PROMOTE), **sibling edge 0건**; (§0.4d/§3.1) canonical REUSE + `id=f(digest)` 미채택(거버넌스-할당
  identity + same-id/diff-bytes·재발행 위조 탐지); (§0.4e/§3.5) rcl(하류 종단·주입 매개)·evidence(하류 투영·
  layering)·capsule(다른 축)·time(freshness 주입)·authority/dsl **미import**; (§0.4f) **BC-INV-001..012 앵커·
  새 INV 시리즈 창작 금지**(ADR-002-004는 #9와 달리 자체 INV 보유 — 실측); (§0.4g/§1) **BC-EV "0건 완결" shape**
  (register 최소 레벨 22행 전부 EV-L2+ — EV-L1 슬라이스 0건 — #8/RCL core-tier와 **정반대**·Time/#6/#7/#9 동형;
  predicate-only 20 / not-Phase-1 2 [BC-EV-015/020 +Security 좌표], core tier 없음) but **닫는 BC-EV 0건**
  (authoring≠evidence); (§2) `BrokerCapabilityProfile` = IndependentId + 독립 id, `CapabilityDeclaration`
  per-dimension, append-only version; (§2.2) capability 어휘(status 7·**dimension 17**·assurance 5·class 4·
  ack 6·replace 5·profile-key 10·profile-version 7·prohibited-proof 7) **verbatim 전사**; (§4.1) **missing/
  contradictory ⇒ reduce/prohibit 중앙 불변식**(Admissibility permissive 기본 부재·미선언=unavailable·
  never-pick-permissive — fail-open 구조적 봉합); (§4.2) fallback 단조-restrictive; (§4.3) drift restrict-only;
  (§4.4) 4-axis 좌표 비붕괴; (§4.5) representation≠enforcement(egress/mutate 메서드 부재); (§4.6) uncertain-send/
  no-blind-retry; (§5) capability_admissible·fallback_admissible·uncertain_send·external/rate; (§6)
  profile_version_current·drift(restrict-only)·fqp_adequate(§15.3 prohibited proofs verbatim)·environment_binding·
  **§13.15 partition-protective-class**(broker-agnostic); (§8) **확정 신규 누락 키 0건**(broker 수치는 Profile
  INSTANCE·ADR §4 배제; 기존 broker-키 재계상 없음). **선제 fail-open/defect 봉합**: 중앙 불변식을 구조로(#6
  REJECT)·core-tier over-claim 방지(§1 #8과 정반대 판정)·fixture clean-vs-illegal 정합 규율(#8 REJECT)·cross-
  section self-consistency pass(§1↔§5/§6↔§7 대조 완료 — C1 lesson)·enum verbatim 전사(에라타 defect class)·
  broker-agnostic(규범 텍스트 broker 무명). 이후 독립 비평 리뷰 대기.
- 2026-07-25: **v1.1 — 독립 비평 리뷰 REVISE 반영(CRITICAL 0·MAJOR 2·MINOR 2; forward-only).** 리뷰는
  fail-open 재발·cross-section 모순·소유권 중복 **전부 부재** 판정, enum 전사·register tier·liveauth/recon/rcl/
  canonical 코드 인용 **전부 정확** 확인. 4건 반영: **[MAJOR-1]** orthostate BROKER_ORDER seam 실측 정정 —
  `conservative_direction_allowed`는 코드에 부재, 실제는 `conservative_direction_ok`(`orthostate/predicates.py:302`,
  `basis: ConservatismBasis|TransitionCause|None` `:306`)이며 seam은 주입 `bool|None`이 **아니라 enum-basis**
  (`ConservatismBasis.BROKER_EVIDENCE_UNDER_PROFILE` strong `vocabulary.py:211`·actor `BROKER_ADAPTER_EVIDENCE`
  `:187`·None/weak ⇒ 감소 차단 `:352–355`); caller가 brokercap bool→basis 매핑(선행 #8 항목·§0.4b(iv)/(대안 B)·
  §3.4 표/bullet·§7 seam-row·§9.1·§10.2 정정). **오명명은 비준된 #8 설계 line 791에서 상속** — 본 문서는 구현
  실측명으로 정정(#8 문서 자체 에라타 여부는 운영자 판단; 본 개정은 #8 미접촉). "세 소비자 전부 주입 bool|None"
  총괄 주장을 한정: liveauth 3종 + recon `final_quantity_proof_token` + orthostate RECONCILED
  `final_quantity_proof_where_broker_involved`(`predicates.py:503`)만 진짜 bool|None(+scalar 2종), orthostate
  BROKER_ORDER만 enum-basis. **[MAJOR-2]** §8 기존-키 열거 보완 — v1.0 grep이 프로파일 560–610 블록을 누락;
  `measurement_source: broker_capability_profile` 완전 재열거(`B_broker_query_consistency`[597, rationale가
  ADR-002-004 명시 태깅]·`B_final_quantity_proof`[569]·`B_late_fill_observation`[576]·`B_rate_limit_recovery`[604]·
  `B_protective_request_complete`[590] 추가) + §5.5(query weak-negative·rate)·§6.3(FQP/late-event window) 주입
  배선 명시; **"확정 신규 누락 distinct 키 0건" 결론 유지·강화**. **[MINOR-1]** ADR list-block line 범위 정정
  (§15.3 prohibited proofs 855→857-863·§16.2 B_external 888→889-890·§16.3 missed-bound 906→907-910; 내용 정확·
  범위만). **[MINOR-2]** §3.4에 liveauth `broker_conformance_class`(`records.py:125`) producer(brokercap
  `ConformanceClass` scalar) 병기. 아키텍처 핵심(패키지·produced-value seam·sibling edge 0·PROMOTE 0·id⊥digest·
  BC-EV 0건 완결 shape·BC-INV 앵커·중앙 fail-closed 불변식·transcription)은 **v1.0 그대로**. 2026-07-25 운영자
  비준 대기.

### 10.2 비준 체크리스트 (운영자 · 독립 리뷰어 확인 사항)

- [ ] §0.2 NO 목록(ADR/acceptance 미승인·Broker Adapter 런타임 미구현·broker 값/class 미결정·evidence replay
      engine·+Security 런타임·numeric quota/horizon·aggregate roll-up·capacity mutation·**닫는 BC-EV 0건**)과
      §0.3 firewall 준수(numpy/pandas/pyyaml·shared.config·**liveauth/orthostate/recon/rcl/evidence/capsule/
      time/authority/dsl 배제, canonical·ordering만 허용**; `.importlinter`는 forbidden 계약뿐 — intra-tos edge
      firewall-clean이나 본 문서는 sibling edge 0건을 설계 규율로 유지)에 동의.
- [ ] §0.4a 전용 패키지 `tos/src/tos/brokercap/`(`tos.broker`[operational-client]·`tos.capability`·
      `tos.brokerprofile` 기각; naming 비-load-bearing) 채택에 동의.
- [ ] **§0.4b/§3.4 brokercap = produced-value producer, sibling edge 0건**(liveauth `broker_capability_sufficient`/
      `_current`/`_added`[`state.py:136`/`predicates.py:94/137/152`] + scalar `broker_capability_profile_version`/
      **`broker_conformance_class`**[`records.py:124/125`] + recon `final_quantity_proof_token`[#9 §6.1/§9.2 item 4] +
      orthostate RECONCILED `final_quantity_proof_where_broker_involved`[`predicates.py:503`]은 주입 `bool|None`;
      **orthostate BROKER_ORDER 차원만 enum-basis** `conservative_direction_ok`[`predicates.py:302`; caller가 bool→
      `ConservatismBasis.BROKER_EVIDENCE_UNDER_PROFILE` 매핑, §3.4]의 상류 producer; composition=caller 소관;
      대안 A/B 기각·cycle 회피; **test-only cross-check MANDATED**)에 동의. **[운영자 판단 지점: produced-value
      decoupled(권장) vs 대안 B 소비자 측 세 edge(비권장)]**
- [ ] **§0.4c/§3.1 PROMOTE 0건·sibling edge 0건**(CanonicalDecimal·IndependentId·classify_record_pair·Ordering
      전부 이미 core — #9가 CanonicalDecimal 1건 PROMOTE 완료했기에 본 문서 PROMOTE 부담 없음)에 동의.
- [ ] §0.4d/§3.1 canonical REUSE + `id=f(digest)` 미채택(거버넌스-할당 profile identity + same-id/diff-bytes·
      재발행 위조 탐지 `classify_record_pair`)에 동의.
- [ ] §0.4e/§3.5 rcl(하류 종단·직접 seam 아님)·evidence(하류 투영·layering)·capsule(다른 축)·time(freshness
      주입)·authority/dsl **미import** + **§3.5 소유권 분할**(recon이 generic conflict/bound 산술 소유·brokercap이
      broker-semantics 판정 소유 — cancel-ack≠FQP·absence=weak-negative·position≠truth; C1 혼동 방지)에 동의.
- [ ] **§0.4f BC-INV-001..012 앵커·새 INV 시리즈 창작 금지**(ADR-002-004는 #9와 달리 자체 INV 보유 — 실측 §6
      line 189–236)에 동의.
- [ ] **§0.4g/§1 BC-EV "0건 완결" shape**(register 최소 레벨 22행 전부 EV-L2+ [line 59–80 실측] — **EV-L1 슬라이스
      0건, core tier 없음** — #8/RCL과 정반대·Time/#6/#7/#9 동형) + **authoring이 BC-EV를 닫지 않음**(VER §5·ADR
      §30) + predicate-only 20(001..014,016,017,018,019,021,022)/not-Phase-1 2(015,020 +Security 좌표) + "EV-L1-complete 주장
      금지"에 동의. **[리뷰어 판단 지점: BC-EV-020을 predicate-only로 읽을 대안(BC-INV-009 L1 술어) 인정 —
      safety-neutral, §1 후단]**
- [ ] §2 데이터 모델(`BrokerCapabilityProfile` = IndependentId + 독립 id·append-only version; `CapabilityDeclaration`
      per-dimension) + §2.2 어휘 **verbatim 전사**(status 7·**dimension 17**·assurance 5·conformance 4·ack 6·
      replace 5·profile-key 10·profile-version 7·prohibited-proof 7)에 동의.
- [ ] **§4.1 missing/contradictory ⇒ reduce/prohibit 중앙 불변식**(ADR line 32·gate-status line 133;
      `Admissibility` permissive 기본 부재·미선언=unavailable[BC-INV-001]·never-pick-permissive[BC-INV-005]·
      class가 실패 mandatory 차원 override 못 함[§10 line 584] — fail-open 구조적 봉합) + §4.2 fallback 단조-
      restrictive + §4.3 drift restrict-only + §4.4 4-axis 좌표 비붕괴 + §4.5 representation≠enforcement(egress/
      mutate 메서드 부재) + §4.6 uncertain-send/no-blind-retry(BC-INV-002/003, timeout 무효)에 동의.
- [ ] §5 capability_admissible(VERIFIED/승인 VWR만 authorize·미선언/UNKNOWN/EXPIRED/UNSUPPORTED/CONTRADICTORY ⇒
      PROHIBITED·required 주입) + §5.3 fallback_admissible(§13 매트릭스·widen 금지·no-fallback⇒PROHIBITED) +
      §5.4 uncertain_send/same_order_retry(idempotency VERIFIED exact id+window만 retry) + §5.5 external/rate에
      동의.
- [ ] §6 **profile_version_current**(stale/expired/degraded ⇒ deny·liveauth producer) + **drift**(모순⇒
      CONTRADICTORY·restrict-only) + **fqp_adequate**(§15.3 prohibited proofs 7종 verbatim ⇒ not adequate·recon
      token producer) + environment_binding(BC-INV-009 cross-environment 거부) + **§13.15 partition-protective-
      class**(broker-agnostic·CLASS-C/D 또는 scope 축소 강제·no new EV)에 동의.
- [ ] §7 하네스 타깃(**전부 predicate/coordinate substrate·닫는 BC-EV 0건·core tier 없음**; both-ways canary;
      **fixture clean-vs-illegal 정합 규율**[#8 교훈]; **seam cross-check MANDATED test-only·NOT package edge**;
      "EV-L1-complete 주장 금지"; **§1↔§5/§6↔§7 self-consistency 대조 완료 — C1 lesson**), §7.1 import-closure
      (liveauth/orthostate/recon/rcl/evidence/capsule/time/authority/dsl 부재 + canonical/ordering 허용), §7.2
      run manifest 7항목에 동의.
- [ ] §8 bounds 주입 + **확정 신규 누락 distinct 키 0건**(ADR-002-004 수치는 broker-specific Profile INSTANCE
      측정값·ADR §4 line 110–113 배제·§21 위임; 기존 `B_external_activity_detect`/`_contain`·`B_egress_hard_fence`·
      `B_capability_claim_to_send`·`B_venue_constraint_loss_detect` 재계상 없음; fail-closed 주입 default라
      safety-neutral·broker-agnostic)에 동의.
- [ ] §9.2 Phase-0 이관 **11항목**(seam decoupled·프로덕션 canon·Profile INSTANCE bound family·broker 값/class
      할당·Broker Adapter 런타임·evidence replay engine·+Security 런타임·독립 리뷰어·required-set/gate 정의·
      conformance/restricted-live 승인·cross-package 좌표 조정)을 별도 게이트로 유지에 동의.
- [ ] 명명 규약(§0.4f): 모델 불변식을 **BC-INV-001..012 / BC-AC-001..022 / BC-EV-001..022 / §-clause /
      SAFE-020/021/024/025/033/040/043**에 앵커하고 **새 INV 시리즈를 창작하지 않음**(ADR-002-004 자체 INV 보유 —
      실측)에 동의.

비준 시 효력: IMPLEMENTATION-PLAN-002 §4 Phase 1의 ADR-002-004 부분을 `tos/src/tos/brokercap/`에 순수·비전송
모델 + property test로 작성 착수 승인(`tos.canonical`·`tos.ordering` REUSE, **sibling edge 0건, PROMOTE 0건**,
produced-bool seam은 caller/integration 이연 + test-only cross-check MANDATED). §9.2 Phase-0 11항목과 bounds
승인·독립 리뷰어 지정, Phase B(Broker Adapter 런타임·broker 값/class·evidence replay·+Security·+Broker) 전체는
별도 게이트로 남는다. **닫는 BC-EV 0건 — acceptance 주장 없음.**
