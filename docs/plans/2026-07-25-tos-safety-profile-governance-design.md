# 설계 문서 #12 — Hard Safety Envelope·Runtime Safety Profile Governance 계약 (2026-07-25, v1.1)

> **문서 번호 규약**: #1 경계·import-firewall, #2 Decision Context Capsule, #4 Evidence
> Store, #5 Risk Capacity Ledger(RCL), #6 Safety Authority, #7 Live Authorization, #8
> Orthogonal Trading State, #9 Evidence·Reconciliation Confidence, #10 Broker Capability,
> #11 Degraded-Mode Protective Capacity가 이미 존재한다(#3은 folded; Trustworthy Time·DSL은
> 병렬 트랙 A/C로 완료). **#12 = 본 Hard Safety Envelope·Runtime Safety Profile Governance
> 문서**이며 **ADR-002-014**를 실현한다. Safety Configuration을 **권위 경계**(ADR line 63
> "Configuration is an authority boundary, not an operational convenience")로 다루어,
> **불변·인증·content-addressed 이중 아티팩트**(Hard Safety Envelope = 최대 권위 상한 /
> Runtime Safety Profile = 그 상한 이하의 한 정확한 live scope 운영값)와 그 위에서
> **envelope dominance(non-silent expansion)·semantic validation(단위·수치·cross-field)·
> atomic mixed-generation activation·stale-base 직렬화·restrictive precedence·expiry
> non-revival·decision-replay substrate**를 결정하는 술어의 **순수·비전송·결정적 데이터 모델
> + hypothesis property test**를 그린필드 `tos/src/tos/spg/`에 저작한다. **live authority·
> capacity mutation·approval workflow·egress enforcement은 저작하지 않는다** — 그것은
> liveauth(#7)·rcl(#5)·authority(#6)·ADR-002-013/015 런타임 소관이다(§3.5 소유권 분할).
>
> **문서 지위**: kis_unified_sts 프로젝트 측 설계 계약. tos-spec에 대해 **non-normative**이며
> 스펙 텍스트(RFC/ADR/템플릿/프로파일)를 **변경하지 않는다.** **broker-agnostic 원칙(project
> memory `tos-spec-broker-agnostic`)**: 본 문서의 규범 텍스트는 **어떤 구체 broker(KIS 포함)도
> 명명하지 않는다.** Envelope/Profile은 governance-CLASS 모델이며, 특정 배치의 실제 값·한도·
> 승인자·broker scope는 구현 트랙의 **non-normative Safety Profile / Verification Profile
> INSTANCE**(ADR §4 non-scope line 98–101, §26 item 12) 소관이다. broker 제약은 capability
> class(Broker Capability Profile, #10)로만 표현한다.
>
> **선행 문서(의존)**:
> - [설계 #1 — `tos/` 경계 & import-firewall 계약 (v2, 운영자 비준)](2026-07-20-tos-boundary-and-import-firewall-design.md).
>   모든 모델은 §2.4 레이아웃(전용 top-level 패키지)에 놓이고 §3.2 허용목록 안에서만 의존한다(§0.3).
>   line 164 "naming은 load-bearing이 아니다 — 내부 세분화는 후속 설계 문서가 정의한다"에 따라
>   본 문서가 `tos.spg` 패키지 내부를 정의한다.
> - [설계 #4 — Evidence Store 계약 (v1.1, 비준·구현됨)](2026-07-20-tos-evidence-store-design.md)
>   + 코드 `tos/src/tos/canonical/`. **canonicalization/digest-binding substrate(`tos.canonical`)·
>   `FrozenModel`(`_base.py:73`)·`DigestBoundArtifact`(`_base.py:98`)·`IndependentIdArtifact`
>   (`_base.py:328`, 이미 core)·`classify_record_pair`(`record_pair.py:52`, 이미 core)·
>   `RecordPairKind`·`ArtifactStatus`(`_base.py:58`)·**이미 core인 `CanonicalDecimal`**
>   (`__init__.py:56`·정의 `canonicalization.py:134` 실측)를 REUSE**한다(재정의 금지).
>   Envelope/Profile의 `id=f(digest)` **미채택** 결정을 동형 상속한다(§2.1/§3.1).
> - [설계 #7 — Live Authorization 계약 (비준·구현됨)](2026-07-25-tos-live-authorization-design.md)
>   + 코드 `tos/src/tos/liveauth/`. **본 문서의 최대 소비자 지대다.** liveauth는 이미 ADR-002-014
>   소유 아티팩트를 참조하는 주입 슬롯을 **다수 선언해 두었다**: `LimitLayering`
>   (`state.py:69–89`)의 `runtime_safety_profile_limit`/`hard_safety_envelope_limit`(int,
>   `state.py:85–86`)·`runtime_safety_profile_version`/`hard_safety_envelope_version`(str,
>   `state.py:87–88`) — docstring `state.py:78–79` verbatim "The two profile limits reference
>   **ADR-002-014-owned artifacts** (`tos` does not author them)"; `ContinuousValidityInputs.
>   hard_and_runtime_versions_match: bool|None`(`state.py:135`; `_INJECTED_CONTINUOUS_CONDITIONS`
>   `predicates.py:93`); `Safe053VariantAttestation.hard_safety_envelope_not_expanded: bool|None`
>   (`state.py:164`; `_SAFE053_CONTROLS` `predicates.py:110`); `InPlaceExpansionInputs.
>   envelope_profile_covers_enlarged: bool|None`(`state.py:205`; `_PROPORTIONAL_EXPANSION_FLAGS`
>   `predicates.py:151`); `LiveAuthorization`의 covered `hard_safety_envelope_version`/
>   `runtime_safety_profile_version`/`configuration_digest`(`records.py:122–127`); liveauth 자체
>   `atomic_activation_ok(version_fully_active, mixed_versions_present, units_compatible,
>   envelope_bounded)`(`predicates.py:454–484`, REARM-AC-006 §6.2)·`layering_within_bounds`
>   (`predicates.py:417`). **spg가 이 슬롯들의 상류 producer**다 — spg는 liveauth를 import하지 않고
>   liveauth도 spg를 import하지 않는다(#10 brokercap→liveauth produced-bool seam과 동형).
> - [설계 #5 — Risk Capacity Ledger 계약 (v1.1, 비준)](2026-07-21-tos-risk-capacity-ledger-design.md)
>   + 코드 `tos/src/tos/rcl/`. **§19 Economic-State/Capacity Continuity의 소유 종단이다.** rcl은
>   §19가 요구하는 "생성 당시 envelope/profile generation을 보존"을 **이미 실현**한다: rcl 레코드
>   다수가 covered `hard_safety_envelope_version`/`runtime_safety_profile_version`(`records.py:101–102,
>   237–238, 306–307, 392–393`)·snapshot의 `profile_generation`/`hard_safety_envelope_generation`
>   (`records.py:469–470`)·**함수** `def effective_limit(hard, runtime) -> CapacityVector`(`vector.py:139`,
>   권위적 `min(Hard[c], Runtime[c])` 계산)를 가진다. **spg는 이 min 산술을 재저작하지 않고**(§0.2), envelope
>   상한·profile 운영값 **두 피연산자 scalar·generation·version·digest를 생산**하며 rcl `effective_limit`이
>   min을 수행·rcl 레코드가 보존한다. **`tos.rcl` 미import**(형제; §3.5).
> - [설계 #6 — Safety Authority 계약 (v1.2, 비준·구현됨)](2026-07-23-tos-safety-authority-design.md)
>   + 코드 `tos/src/tos/authority/`. **§8 SoD·§9 envelope activation-suspends-dependents의 인접
>   지대다.** authority는 covered `hard_safety_envelope_version`/`runtime_safety_profile_version`
>   (`records.py:113–114`)·`hard_safety_envelope_generation`/`runtime_safety_profile_generation`
>   (`state.py:53–54`)·invalidation 술어의 주입 `hard_envelope_incompatible: bool|None`
>   (`predicates.py:640`; `if hard_envelope_incompatible is not False: ...invalidated`
>   `predicates.py:701`)를 가진다. spg가 `envelope_incompatible` bool의 상류 producer다.
>   mode·precedence·epoch·re-arm gate은 **authority 소유**(재저작 금지). **`tos.authority` 미import**(형제).
> - [설계 #10 — Broker Capability 계약 (v1.1, 비준)](2026-07-25-tos-broker-capability-design.md)
>   + 코드 `tos/src/tos/brokercap/`. **§7 Canonical Artifact Contract + 버전 거버넌스의 가장 유사한
>   구현 선례다.** `BrokerCapabilityProfile(IndependentIdArtifact)`의 `ProfileKey`·`ProfileVersion`
>   (immutable version·`superseded_version_link`·`approver_identity`·`expiration_or_revalidation_date`,
>   ProfileVersion `records.py:71–88`; `ProfileKey` `records.py:48`)·append-only version-immutable 레코드·`profile_version_current`
>   (`predicates.py:465–498`) 패턴을 **이중 적용**(Envelope + Profile)한다. spg는 §16 consumer
>   compatibility drift에서 brokercap이 소유하는 broker/software drift를 **주입 좌표**로만 소비하고
>   재저작하지 않는다(§3.5). produced-bool seam·edge 0·PROMOTE 0의 직전 동형 선례. **`tos.brokercap`
>   미import**(형제).
> - [설계 #11 — Degraded-Mode Protective Capacity 계약 (v1.1, 비준)](2026-07-25-tos-degraded-mode-protective-capacity-design.md)
>   + 코드 `tos/src/tos/protective/`. **§7 Protective Action Envelope subordination의 인접 지대다.**
>   protective `HardEnvelopeRef`(`records.py:94` "An injected reference to the **ADR-002-014** Hard
>   Safety Envelope's per-axis maxima")·`envelope_subordinate`(`predicates.py:740`)는 spg가 소유하는
>   Hard Safety Envelope 상한을 **주입 참조**로 소비한다. spg는 그 상한 아티팩트를 소유·생산하고
>   protective는 자신의 envelope를 그 상한 이하로 종속시키는 술어만 소유한다(소유권 분할, §3.5).
>   **`tos.protective` 미import**(형제).
> - 인접 좌표 실측(전부 주입, 미import): time `safety_profile_version`/`verification_profile_version`
>   (snapshot covered `snapshot.py:140–141`·`predicates.py:618–673` expected-version 검사) — §18 expiry
>   좌표; capsule `safety_configuration_generation`/`broker_capability_profile_version`(`capsule.py:88–89`);
>   evidence replay `hard_safety_envelope_digest`/`runtime_safety_profile_digest`/`safety_configuration_
>   activation_record_digest`(`replay.py:111–113`)·`verification_profile_version`(`replay.py:122`)·gap
>   `profile_generations`(`gap.py:79`) — §21/SPG-EV-012 replay 좌표. **spg는 이 7개 형제 패키지가 이미
>   담아 둔 envelope/profile 좌표의 상류 origin이다**(§3.4, 코드 실측).
>
> **규범 원천**: `ADR-002-014` — Hard Safety Envelope and Runtime Safety Profile Governance
> (Status: **Proposed**, Date 2026-07-13, **706 line**, Decision Type: Safety-Critical
> Architecture Decision). **Refines** RFC-001 SAFE-003/004/050; RFC-002 §§9.1/10.12/10.18/19.3/28;
> ADR-002-007 §§4–6/10/12/25; ADR-002-009 §§10–12; ADR-002-012 §§5.4/10/15/20 (ADR line 8).
> **Depends On** RFC-000 constitutional safe state; RFC-001 **SAFE-003/004/010/011/013/035/041/
> 045/046/047/048/050/051/052**; ADR-002-001 through ADR-002-013 (ADR line 9). 매핑 대상 EV:
> `verification/EVIDENCE-REGISTER-002.md`의 **`SPG-EV-001..012`(line 186–197 실측, 전부
> `NOT_IMPLEMENTED`)**. 앵커: **`SPG-INV-001..014`(§6 line 151–206)·`SPG-AC-001..012`(§24 line
> 620–631)·`SPG-EV-001..012`·§-clause·`SAFE-003/004/010/011/013/035/041/045/046/047/048/050/051/052`
> (§25)**. ADR-002-014는 **자체 INV 시리즈 `SPG-INV-001..014`를 정의**하므로 본 문서는 그 SPG-INV에
> 앵커하고 **새 INV 시리즈를 창작하지 않는다**(§0.4f; #6 `SA-INV`·#8·#10 `BC-INV` 자체 INV 앵커와
> 동형, #9/#11이 INV 부재로 AC/EV에만 앵커한 것과 대비).
>
> **실측-원천 정정 1건(오케스트레이터 brief 대비)**: brief는 "§24 SPG-AC-001..008"로 지시했으나
> ADR §24는 **`SPG-AC-001..012`(12행, line 620–631 실측)**를 정의하며 `SPG-EV-001..012`와 **1:1
> 대응**한다(§24 line 616 "map one-to-one to `SPG-EV-001` through `SPG-EV-012`"). 본 문서는 실측값
> **012**를 채택한다(#10 MAJOR-2·#8 line 791 실측-원천 규율 — 상류 서술이 아니라 원문 라인).
>
> **비준 기록**: **2026-07-25 운영자 비준(v1.1) — §10.2 판단 지점 승인(seam produced-bool/scalar
> decoupled·MAJOR-3 선택지 (b) 대조표[포함 29·이연 7]).** 효력: `tos/src/tos/spg/` Phase 1(EV-L1)
> 순수·비전송 모델 + property test 착수 승인(`tos.canonical`·`tos.ordering` REUSE, sibling edge 0건,
> PROMOTE 0건). (v1.0 초안 → 독립 비평 리뷰 **REVISE**[CRITICAL 0·
> MAJOR 3·MINOR 2·NIT 2] 반영: MAJOR-1 phantom `EffectiveLimitVector`→함수 `effective_limit`(`vector.py:139`)+
> 소유권 정렬(spg는 두 피연산자 scalar만·min은 rcl)·MAJOR-2 protective `*_version` seam 오귀속 정정(records.py:277은
> 자체 identity)·MAJOR-3 `BundleMemberKind` "verbatim closed set" 철회+§5.3 line 119 36항 2열 대조표[선택지 b]·
> MINOR-1 `ChangeDirection.UNORDERABLE` enum 제거→reason·MINOR-2 activation seam 4-bool/내부 verdict 분리·NIT
> 2건 라인 정정[ProfileKey `records.py:48`·`_base.py:352`]; 상세 §10.1). 본 문서는 어떤 ADR/EV의 acceptance·비준·
> restricted-live·production도 선언·주장하지 않는다. **닫는 SPG-EV = 0건.** ADR acceptance는 오직
> *실행된* evidence로만 온다(project memory `tos-spec-rfc-authoring-track`; ADR §24 line 616
> "Written cases are not completed evidence"·§27 line 682 "SHALL remain **Proposed** until…"·line
> 706 "Authorship, signatures, successful parsing, repository merge, staged distribution, written
> acceptance cases, or document review do not satisfy this gate"; VER-002-001 §5 "Registration is
> not execution. A written test is not evidence"). 수용 서명 게이트는 IMPLEMENTATION-PLAN-002 §3
> 하드 배제(Independent-Safety-Reviewer는 본 문서의 저자/통합자여서는 안 됨)를 따른다.
>
> **리뷰 이력(선제 봉합 defect class)**: 직전 시리즈 REJECT/REVISE — #6 v1.0 **REJECTED**(fail-open
> seam: exclusivity `≤1⇒True` vacuous-True), #7 v1.0 **REVISE**(SAFE under-realization), #8 v1.0
> **REJECT**(cross-section 모순: representability를 coupling-cleanliness와 혼동 — C1), #10 v1.0
> **REVISE**(MAJOR-1 orthostate seam 실측 오명명; MAJOR-2 §8 bounds 불완전 열거), #11 v1.0 **REVISE**
> (MAJOR-1 thin-signature `protective_leases_reconciled` 정의 술어 추가; MINOR-1 §21 불릿 수 정정).
> #6/#7/#9 세 건은 비준 후 transcription 에라타를 요했다. 본 문서가 **선제 봉합**한 defect class:
> (a) **§1 core-tier 판정** — SPG-EV 12행 중 **8행(001–006·008·012)이 최소 레벨에 EV-L1 슬라이스
> 보유** ⇒ **시리즈 최대 core tier**(#8 1행·#5 core·#11 2행 대비 8행)이나 **닫는 SPG-EV = 0건**
> (`/2`·`/3`·`+Security` 잔여; §1 결정적 사실 2). (b) **소유권 중복·권위 중복 구조적 배제(#8 C1·#11
> §3.5 교훈)** — liveauth re-arm·rcl capacity·authority mode/epoch/SoD-epoch·time expiry 산술·evidence
> replay engine·ADR-002-015 effective-principal을 **코드로 실측**해 spg가 무엇을 소유/소비/생산하는지
> §3.5 소유권 분할표로 고정(실제 필드명·라인 인용). (c) **fail-open seam 방지(#6 REJECT 교훈)** — 중앙
> 술어가 *본질적으로* fail-closed(profile>envelope⇒거부·미증명 방향⇒AUTHORITY_INCREASING·빈 bundle⇒
> incomplete·mixed-generation⇒거부·stale-base⇒거부·expiry⇒non-revival·None⇒restrictive), permissive
> 기본 생성 경로 구조적 부재, 각 가드 both-ways canary(§4·§5·§6). (d) **∅-공허 fail-closed 명문화(#10
> code-review 교훈)** — completeness/validation 술어의 빈 컬렉션은 **most-restrictive**(빈 required
> bundle-member ⇒ 전 member 필요; 빈 governed-dimension ⇒ vacuous-dominant 금지; §4.1/§5.1/§5.2).
> (e) **thin-signature 주입 verdict 판단(#11 MINOR 교훈)** — semantic validation은 ADR §11 line 315
> "deterministic result and **reason set**"를 요구하므로 thin bool이 아니라 **rich `SemanticValidation
> Result`(valid + rejected_dimensions + reason_set)**로 저작한다(§5.2 근거 명시). (f) **fixture
> clean-vs-illegal 정합(#8 REJECT 교훈)**(§7). (g) **cross-section self-consistency pass**(§1↔§5/§6↔§7
> 대조). (h) **verbatim 전사 + ADR line 병기**(에라타 defect class 방지 — §2.2). (i) **self-referential
> Verification-Profile 신중 분석**(§8 — 이 ADR이 Safety-Profile 거버넌스 자체를 다루므로 프로파일
> 파일과의 관계가 self-referential).

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. ADR-002-014 조항별 **Phase 1(EV-L1) 도달성 경계**(§1). **core(L1 슬라이스) / predicate-only /
   not-Phase-1(형제 소유·런타임 이연) 3분류.** **결정적 사실**: `SPG-EV` 12행 중 **8행(001·002·003·
   004·005·006·008·012)이 register 최소 레벨에 EV-L1 슬라이스 보유** ⇒ **시리즈 최대 core tier**(#8/#5/
   #11 core-tier shape의 최대판; #10/Time/#6/#7/#9의 "0건 완결"과는 다름). 그러나 **닫는 SPG-EV = 0건**
   (L1 슬라이스 저작 ≠ EV closure: `/2`·`/3`·`+Security` 잔여). "**EV-L1-complete 주장 금지**".
2. **Hard Safety Envelope·Runtime Safety Profile 이중 아티팩트 데이터 모델**(§2, **core**): 버전 있는
   digest-bound `HardSafetyEnvelope`·`RuntimeSafetyProfile`(둘 다 IndependentIdArtifact) + closed
   `SafetyConfigurationBundle`(§5.3) + `ActivationRecord`(§5.7) + `ConsumerCompatibilityManifest`(§5.6).
   어휘: `EnvelopeState`(§12.1 9종 verbatim)·`ProfileState`(§12.2 11종 verbatim)·`ChangeDirection`
   (§5.9/§11 line 312: `RESTRICTIVE`/`PERMISSIVE`/`AUTHORITY_INCREASING` — 3종; 순서불가는 enum 값 아닌 `ValidationReason.UNORDERABLE_DIRECTION`, §2.2(3) v1.1 MINOR-1)·
   `BundleMemberKind`(§5.3 line 119 대조표 §2.2(4): 포함 29·이연 7)·`ValidationReason`(§11/§20 reject 사유 class)·`ActivationVerdict`
   (로컬 3종). Envelope/Profile version 좌표는 §7 canonical artifact contract verbatim(§2.2).
3. **envelope dominance / non-silent expansion 중앙 불변식**(§4.1, SPG-EV-001 substrate — ADR §1 line
   19–26·§6 SPG-INV-001/007·§9): `profile_within_envelope(envelope, profile) -> ValidationResult` ∧
   `envelope_expansion_enlarges_nothing(...) -> bool`. **profile 값이 envelope 초과 ⇒ 거부**(SPG-INV-001
   line 153 "No Runtime Safety Profile … may exceed, redefine, disable, omit, or reinterpret a Hard
   Safety Envelope constraint"); **envelope 미선언 dimension을 profile이 참조 ⇒ zero authority**(빈/
   미선언 ⇒ vacuous-dominant 금지, §4.1); **envelope expansion이 active profile을 자동 확대하지 않음**
   (SPG-INV-007 line 177; produces liveauth `hard_safety_envelope_not_expanded`).
4. **semantic validation 중앙 불변식 + rich verdict**(§4.2/§5.2, SPG-EV-002/003 substrate — ADR §11
   line 300–317): `semantic_validation(bundle) -> SemanticValidationResult`. **단위·multiplier·currency·
   sign·precision·rounding·overflow·underflow·NaN·infinity·boundary(§11 step 3 line 304)·cross-field
   (step 5)·authority-direction(step 11)·unknown/duplicate/deprecated/extension field(step 12) 결함 ⇒
   invalid**. §11 line 315 "deterministic result and **reason set**" ⇒ thin bool 아님 — `valid: bool`
   + `rejected_dimensions: frozenset` + `reason_set: frozenset[ValidationReason]`(#11 MINOR 교훈, §5.2).
   **순수 술어의 노다지**(step 3/4/5/11/12는 순수 L1; step 7/9/10은 ARE/rcl/time/bundle-member 주입).
5. **atomic mixed-generation activation 술어**(§5.3, SPG-EV-004 substrate — ADR §13·SPG-INV-005): **seam
   출력 = 4 개별 bool**(`version_fully_active`/`mixed_versions_present`/`units_compatible`/`envelope_bounded`),
   spg 내부 folded `activation_atomic(...) -> ActivationVerdict`는 SPG-EV-004 property 검증용(§5.3 이중-레이어,
   v1.1 MINOR-2) — **mixed generation / partial distribution / missing value / incompatible unit /
   unverifiable activation ⇒ 거부**(§13 line 385; SPG-INV-005 line 169 "Partial or mixed activation cannot
   create the union of permissions"). liveauth `atomic_activation_ok`(`predicates.py:454`)가 이 4 bool을 **fold**
   (소비 signature 불변, §3.4). quorum commit·staging 런타임은 이연(§13 line 379/383).
6. **concurrent / stale-base activation 술어**(§5.4, SPG-EV-005 substrate — ADR §15·SPG-INV-003):
   `activation_serializable(candidate, current_active) -> bool` — **predecessor generation ≠ current
   active generation(stale-base) ⇒ 거부**; **same predecessor + overlapping scope 두 활성화 ⇒ 하나만
   winner**(§15 line 417–422); **last-write-wins·partial field patch 부재**. append-only activation
   순서는 `tos.ordering` REUSE(§3.2). `latest`/local file/cache ≠ authority(SPG-INV-003 line 161).
7. **restrictive precedence + monotonicity 술어**(§5.5, SPG-EV-006 substrate — ADR §14·SPG-INV-008):
   `restrictive_override_admissible(...) -> bool` — **모든 credible dimension에서 deny/narrow만·어떤
   dimension도 확대 불가(§14 line 393)·auto-revert 금지(§14 line 402)·capacity/orders/exposure/UNKNOWN/
   protective 보존(§14 line 401)**; **monotonic 증명 불가 ⇒ AUTHORITY_INCREASING으로 분류·restrictive
   경로 거부**(§14 line 393; SPG-INV-008 line 181). economic continuity 수치는 rcl 주입(§19).
8. **expiry non-revival + non-permissive 술어**(§5.6, SPG-EV-008 substrate — ADR §18·SPG-INV-011/013):
   `expiry_suspends_new_risk(...) -> bool`(만료/time-unverifiable ⇒ future new-risk 중단) ∧
   `expiry_revives_nothing(...) -> bool`(무조건 True — 만료가 orders/capacity/economic effect/UNKNOWN
   해소·predecessor 복원·auto grace 확대·time-recovery re-arm을 **하지 않음**, §18 line 472–482;
   liveauth `authorization_revived_by_nothing`·rcl `recovery_generation_revives_nothing` 동형). time
   validity는 주입 flag(§3.5; spg는 time 산술 불요).
9. **decision-replay substrate**(§5.7, SPG-EV-012 substrate — ADR §21·SPG-INV-014): frozen digest-bound
   append-only `HardSafetyEnvelope`/`RuntimeSafetyProfile`/`SafetyConfigurationBundle`/`ActivationRecord`
   레코드 모델(각 artifact·approval·validation·activation·restriction 결정을 durable evidence에서
   재구성 가능케 함). **replay ENGINE 자체는 ADR-002-016**(not-Phase-1). **Evidence Is Not Authority**
   (SPG-INV-014 line 205; §4.5 representation≠enforcement). evidence 참조는 scalar(id/gen/digest).
10. **predicate-only 술어**(§6, 최소 레벨 ≥ L2·L1-decidable substrate 저작·EV 미완결): rollback=new-proposal
    non-revival(§6.1, SPG-EV-007); break-glass directional confinement(§6.2, SPG-EV-009); consumer
    compatibility manifest match(§6.3, SPG-EV-010); missing/contradictory containment(§6.4, SPG-EV-011).
    각각의 +Security/런타임/sibling 잔여는 not-Phase-1(§1).
11. **spg ↔ liveauth/authority/rcl/time/capsule/evidence/protective 경계(중심 아키텍처)**: spg는 **sibling
    edge 0건**을 유지한다(§0.4b/§3.4). spg는 envelope-dominance·version-match·not-expanded·covers-enlarged·
    envelope-incompatible **bool을 생산**하고 envelope/profile **version·limit·generation·digest scalar를
    생산**하며, **7개 형제 패키지가 이미 선언한 주입 슬롯**으로 소비한다(코드 실측: liveauth `state.py:85–88/
    135/164/205`·`records.py:122–127`, authority `records.py:113–114`·`state.py:53–54`·`predicates.py:640`,
    rcl `records.py:101–102/469–470`·`vector.py:139`, time `snapshot.py:140–141`, capsule
    `capsule.py:88–89`, evidence `replay.py:111–113`, protective `records.py:94`). `tos.liveauth`·
    `tos.authority`·`tos.rcl`·`tos.time`·`tos.capsule`·`tos.evidence`·`tos.protective`·`tos.brokercap`·
    `tos.orthostate`·`tos.recon`·`tos.dsl` **미import** — spg는 `tos.canonical`·`tos.ordering`(둘 다 core)만
    import한다(§0.3). **PROMOTE 0건.**
12. **fail-closed 규율 + named canary**(§4·§5·§6): profile>envelope⇒거부; envelope 미선언 dimension⇒zero
    authority; 미증명 방향⇒AUTHORITY_INCREASING; 빈 bundle-member set⇒전 member 필요(vacuous-complete
    금지); mixed-generation⇒거부; stale-base⇒거부; unknown/duplicate field⇒거부; restrictive 증명 불가⇒
    permissive 경로 거부; expiry⇒non-revival; None⇒restrictive. 각 가드에 **both-ways canary**.
13. **property-test 하네스 타깃**(§7, §1 분류 정렬) + import-closure 검증(§7.1) + run manifest 7항목(§7.2)
    + fixture clean-vs-illegal 정합 규율(#8 교훈).
14. **bounds 주입 계약 + Phase-0 이관 + self-referential Verification-Profile 분석**(§8): spg decision
    구조에는 numeric bound 부재(전부 enum·boolean·집합 논리·주입 `CanonicalDecimal`); ADR-002-014가 요하는
    수치(envelope/profile validity·review deadline·staging age·attestation age·restriction-propagation)는
    **Safety Profile/Verification Profile INSTANCE 측정값**이며 주입 opaque param으로만 담는다. **MAJOR-2
    규율**: `measurement_source` 전수 확인 후 완전 열거(§8).

### 0.2 하지 않는 것 (경계·NO 목록)

- **ADR/스펙 비준·acceptance·restricted-live·production 어느 것도 승인하지 않는다.** ADR §27 line 682
  "ADR-002-014 SHALL remain **Proposed** until all of the following are complete"·line 706 "Authorship…
  do not satisfy this gate. This ADR does not authorize acceptance, restricted-live operation, production
  operation, configuration-driven capacity mutation, or automatic re-arm." **닫는 SPG-EV = 0건.**
- **Live Authorization·re-arm·continuous-validity를 저작하지 않는다.** 그것은 **liveauth(#7, ADR-002-007)
  가 이미 소유·구현**했다 — `continuous_validity`·`rearm_admissible`·`layering_within_bounds`·
  `atomic_activation_ok`·`in_place_expansion_admissible`. spg는 그 술어들이 **소비하는** envelope/profile
  bool·scalar를 생산할 뿐, re-arm gate·arming 결정을 하지 않는다(§12.3 line 350 "Activation does not mean
  trading is live … ADR-002-007 Live Authorization remains a separate, fresh, revocable authority").
- **capacity 산술(commit/consume/release·aggregate envelope·effective-limit reduction·economic continuity
  mechanics)을 저작하지 않는다.** 그것은 **rcl(#5, ADR-002-002/012)이 이미 소유·구현**했다 —
  `def effective_limit(hard,runtime)`(함수, `vector.py:139`)·`transition_allowed`·generation 보존. §19는
  ADR line 492 verbatim "The Safety Profile Validator and configuration services SHALL NOT mutate, release,
  transfer, or synthesize RCL capacity." spg는 generation/version 좌표를 **생산**하고 rcl이 보존·소비(§3.5).
- **authority mode·precedence·epoch·SoD-epoch·re-arm gate·envelope-activation-suspension을 재저작하지
  않는다.** authority(#6, ADR-002-003)가 `AuthorityState`·`PRECEDENCE_RANK`·`hard_envelope_incompatible`
  invalidation·`*_generation` fence를 소유. §9 line 269 "Activation of any new Envelope Generation suspends
  dependent Runtime Safety Profiles and Live Authorizations until they are revalidated and explicitly
  re-armed" — 이 **suspension·re-arm은 authority/liveauth 런타임**이며 spg는 envelope generation advance
  bool·not-expanded bool만 생산(§3.4).
- **Safety Profile Validator 런타임·Configuration distribution service·quorum commit·staging·consumer
  attestation collection·egress enforcement을 구현하지 않는다.** ADR §13 line 379–383(quorum commit through
  Safety Commit Log·staging·attestation)·§16(distribution untrusted·consumer independent verify·final
  egress binding)은 **런타임**이다. Phase 1 spg는 결정 술어만 저작하며 **전송·활성화 commit·attestation
  수집·egress reject를 수행하지 않는다**(§4.5; ADR §1 line 40 "The Safety Profile Validator validates and
  attests configuration; it does not create capacity, issue Live Authorization, or transmit orders").
- **effective-principal independence·approval quorum·break-glass credential control·delegation을 결정하지
  않는다.** ADR §8 line 249 "Splitting labels across roles while one principal controls all underlying
  credentials does not establish separation"·§26 item 3(ADR-002-015 policies)는 **ADR-002-015 Human
  Authority Governance(HAG-EV) 런타임 +Security** 소관이다. spg는 §8 SoD 권한 **테이블 좌표**와 break-glass
  **directional confinement 술어**(break-glass는 HALT/restrictive만·확대/rearm/activate 금지, §8 line 251)만
  담고, effective-principal collapse 탐지는 not-Phase-1(§1 SPG-EV-009).
- **rollback/restore/DR 상태 복원·restore-generation fence enforcement·historical signature replay를
  구현하지 않는다.** ADR §17은 rollback을 "a new proposal, never a state reversal"(line 452)로 규정하고
  restore-generation advance는 **ADR-002-012**(rcl `restore_generation` `records.py:465`) 소관이다. spg는
  "rollback=new generation" 술어만 담고 restore-fence enforcement·+Security historical-signature는
  not-Phase-1(§1 SPG-EV-007).
- **evidence persistence·replay engine·+Security enforcement를 구현하지 않는다.** spg 결정의 재구성
  가능성(digest-bound frozen 레코드)만 담고 replay ENGINE은 ADR-002-016(evidence `replay.py`), egress
  bypass·물리 격리는 ADR-002-013(+Security)이다(§9.2 Phase-0).
- **numeric limit·validity interval·review deadline·staging/attestation age를 승인하지 않는다.** ADR §4
  non-scope line 98 "numeric safety limits"·§26 item 12. Phase 1은 전부 주입 파라미터/`CanonicalDecimal`로
  담고 **어떤 숫자도 하드코딩하지 않는다**(CLAUDE.md). 값 부재 ⇒ fail-closed. 값 승인은 Bounds-Approver
  게이트(§8·§9.2).

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

spg 모델은 다음만 import한다:

- 서드파티: `pydantic`(frozen 모델), `pytest`·`hypothesis`(테스트만). **`numpy`/`pandas`/`pyyaml`도
  import하지 않는다** — governance는 StrEnum·boolean·집합 논리이고, 수치는 `CanonicalDecimal` 산술뿐이라
  수치 백엔드 불필요하며, 모든 bound·threshold·interval은 주입 파라미터이고 YAML 파싱은 하네스(설계 #3)
  소관이다(closure 최소화 — #5/#6/#7/#8/#9/#10/#11 §0.3 동형).
- tos 자기 자신: `tos.canonical`(`FrozenModel`·`DigestBoundArtifact`·**이미 core인 `IndependentIdArtifact`**·
  **이미 core인 `classify_record_pair`**·`RecordPairKind`·`ArtifactStatus`·**이미 core인 `CanonicalDecimal`**
  — `__init__.py:45–64` 실측 §3.1), `tos.ordering`(activation-record/generation append-only 순서 — §3.2),
  `tos.spg.*`. **`tos.liveauth`·`tos.authority`·`tos.rcl`·`tos.time`·`tos.capsule`·`tos.evidence`·
  `tos.protective`·`tos.brokercap`·`tos.orthostate`·`tos.recon`·`tos.dsl`을 import하지 않는다**(형제/상하류;
  produced-bool·scalar·주입 좌표로만 참조 — §3.4/§3.5).
- **`shared.config` 절대 금지**(설계 #1 §6.1, `.importlinter`): `shared.config.__init__`이
  `shared.config.secrets`(→ `os.environ`)를 무조건 전이 import한다. spg는 어떤 `shared.*`도 필요로 하지
  않는 순수 커널이다. (명명 절 §0.4a에서 `tos.config` 기각의 부가 근거이기도 하다.)
- **금지(직접·전이 모두)**: `shared.execution`, `shared.kis`, `shared.streaming`, `shared.llm`,
  `shared.storage`, `shared.backtest`, `services.*`, `cli.*`(설계 #1 §2.3; `.importlinter` forbidden set).
- **firewall 구조 확인(실측·#10/#11 §0.3 상속)**: `.importlinter`는 **`forbidden` 계약 단일**(type=forbidden,
  source=tos)이며 `layered` 계약이 아니다 — intra-tos sibling→sibling edge는 구조적으로 금지되지 않고 설계
  #1 §3.2의 "자기 자신 `tos.*`" 허용 조항이 이를 커버한다. **신규 패키지 `tos.spg`는 firewall 도구 무수정
  자동 포섭**된다(forbidden 계약이 source=tos 전체를 덮으므로). 본 문서는 그럼에도 **sibling edge 0건**을
  **설계 규율**로 유지한다(§0.4b).
- 이 배제를 능동 강제하는 것이 §7.1 import-closure 검증 테스트다(`import tos.spg` closure에 금지·
  `shared.config`·`os.environ`·numpy/pandas/yaml·**`tos.liveauth`·`tos.authority`·`tos.rcl`·`tos.time`·
  `tos.capsule`·`tos.evidence`·`tos.protective`·`tos.brokercap`·`tos.orthostate`·`tos.recon`·`tos.dsl`**
  부재 assert; **`tos.canonical`·`tos.ordering`은 존재 허용**). required check(`tos-firewall`,
  `tools/tos_firewall_check.py` layer-① AST + `.importlinter` layer-② 전이 방어)와 함께 green이어야 성립.

### 0.4 REUSE / import / 경계 결정 요지 (핵심 아키텍처)

**(a) 패키지 위치·명명 = `tos/src/tos/spg/`.** ADR-002-014는 "Hard Safety Envelope and Runtime Safety
Profile **Governance**"를 세우고 그 위에서 activation/restriction/validation을 결정한다. 명명 대안 비교:

- **`tos.envelope`(기각·collision)**: Hard Safety Envelope만 명명해 **지나치게 좁다**(ADR는 Envelope와
  Profile을 **co-equal 이중 아티팩트**로 다룸 — #11이 `tos.degraded`를 "너무 좁다"로 기각한 것과 동형).
  게다가 **`envelope` 토큰은 이미 다중 충돌**한다(실측): evidence `SafetyEvidenceEnvelope`(`envelope.py`)·
  rcl "aggregate envelope"·protective `ProtectiveActionEnvelope`(`records.py:68`). 하드 기각.
- **`tos.safetyprofile`(기각)**: Runtime Safety Profile만 명명해 좁고(Envelope 배제) verbose하며 terse
  명명 관행(canonical/capsule/rcl/recon/liveauth/dsl/brokercap)과 어긋난다. `profile`은 brokercap의
  `BrokerCapabilityProfile`과도 혼동.
- **`tos.config`/`tos.safetyconfig`(기각·collision)**: ADR line 63 "Configuration is an authority boundary"
  를 명명하나 **`shared.config`(firewall 하드 금지)** 및 dsl `determinism.py`의 "versioned configuration"과
  충돌·오독 소지. 하드 기각.
- **`tos.governance`(기각)**: 지나치게 generic("무엇의 거버넌스?").
- **선택 `tos.spg`**: **register domain "Safety Profile Governance"·prefix `SPG`(`SPG-EV`/`SPG-AC`/
  `SPG-INV`)**를 직접 명명, terse, **Envelope+Profile 이중 아티팩트를 모두 포섭**(governance 층). 의미 있는
  두문자(Safety Profile Governance)로 `tos.rcl`(Risk Capacity Ledger)·`tos.dsl`(Strategy DSL) 동형이며,
  #11이 `tos.prd`를 기각한 이유("`PRD`=product requirements doc 통용, cryptic")와 달리 `SPG`는 강한 경쟁
  의미가 없고 패키지가 정확히 ADR 제목이다. **naming은 load-bearing이 아니다**(설계 #1 line 164) — 운영자
  치환 가능; **load-bearing은 layering**(spg → canonical·ordering 한 방향; liveauth·authority·rcl·time·
  capsule·evidence·protective·brokercap과 형제/상하류, **edge 0건**). 내부 module(`vocabulary.py`·
  `records.py`·`predicates.py`·`state.py`·`_base.py`)은 brokercap/liveauth/rcl 선례 동형이며 **충돌 없음**
  (실측: `tos/src/tos/spg` 부재 확인·`spg` 토큰 tos 내 0건).

**(b) spg = produced-bool/scalar producer, sibling edge 0건 (중심 결정, 코드 실측).** spg는 **7개 소비자
패키지의 상류**다 — envelope/profile 판정 bool·좌표를 생산하고 그들은 **이미 선언한 주입 슬롯**으로 소비한다.
**코드 실측 seam**(sibling 서사 아님 — #10 MAJOR-1 교훈):

| spg 산출 (§5/§6) | 타입 | 소비처 (이미 비준·구현) | 소비 signature(실측) |
|---|---|---|---|
| `hard_and_runtime_versions_match(...)` | `bool` | liveauth continuous-validity | `hard_and_runtime_versions_match: bool\|None`(`liveauth/state.py:135`; `_INJECTED_CONTINUOUS_CONDITIONS` `predicates.py:93`; None/False⇒invalid) |
| `envelope_not_expanded(...)` | `bool` | liveauth SAFE-053 variant | `hard_safety_envelope_not_expanded: bool\|None`(`liveauth/state.py:164`; `_SAFE053_CONTROLS` `predicates.py:110`) |
| `envelope_profile_covers_enlarged(...)` | `bool` | liveauth §14.1 expansion | `envelope_profile_covers_enlarged: bool\|None`(`liveauth/state.py:205`; `_PROPORTIONAL_EXPANSION_FLAGS` `predicates.py:151`) |
| atomic-activation **4 개별 bool** (seam 출력) | `bool`×4 | liveauth `atomic_activation_ok` (fold) | `version_fully_active`/`mixed_versions_present`/`units_compatible`/`envelope_bounded`(`liveauth/predicates.py:454–484`) — spg 내부 `activation_atomic→ActivationVerdict`와 별개(§5.3, 이중-레이어) |
| `envelope_incompatible(...)` | `bool` | authority invalidation | `hard_envelope_incompatible: bool\|None`(`authority/predicates.py:640`; `is not False⇒invalidated` `:701`) |
| `active_envelope_version`/`active_profile_version` | `str` | liveauth·authority·rcl·time covered | `hard_safety_envelope_version`/`runtime_safety_profile_version`(`liveauth/state.py:87–88`·`records.py:122–123`, `authority/records.py:113–114`, `rcl/records.py:101–102`), time `safety_profile_version`(`snapshot.py:141`) — **scalar** (protective는 여기 없음 — §4.4·v1.1 MAJOR-2: protective `records.py:277`은 자체 identity) |
| envelope 상한·profile 운영값 **두 피연산자 scalar**(min 미수행) | `CanonicalDecimal` | liveauth `LimitLayering`·rcl `effective_limit` | `runtime_safety_profile_limit`/`hard_safety_envelope_limit`(`liveauth/state.py:85–86`); 권위적 min은 rcl 함수 `effective_limit`(`vector.py:139`)이 수행 |
| `active_generation`/activation digest | `int`/`str` | authority·rcl·capsule·evidence covered | `hard_safety_envelope_generation`/`runtime_safety_profile_generation`(`authority/state.py:53–54`), `profile_generation`(`rcl/records.py:469`), `safety_configuration_generation`(`capsule/capsule.py:88`), `safety_configuration_activation_record_digest`(`evidence/replay.py:113`) |

대안 비교(#10 §0.4b 형식):

- **대안 A — spg가 소비자(liveauth/authority/rcl/…)를 import**: spg가 각 소비자 typed 필드를 참조.
  **기각**: (i) **backwards edge** — spg는 dataflow상 7개 소비자의 **상류**(envelope/profile 판정을 생산→
  소비)인데 상류가 하류를 import하면 부자연. (ii) **일곱** cross-sibling edge 신설(시리즈 최다). (iii)
  **cycle 위험**: 지금 acyclic이나 누군가 spg 토큰을 참조하면 즉시 cycle. (iv) 소비자들은 **이미** envelope/
  profile 조건을 주입 슬롯으로 봉인해 두었다(실측 — liveauth `state.py:78–79` docstring이 명시적으로
  "ADR-002-014-owned artifacts (`tos` does not author them)"라 선언).
- **대안 B — 소비자가 spg를 import(방향 정합이나 다수 edge 신설)**: liveauth/authority/rcl/… 이 spg를 직접
  호출. **기각**: 소비자 전부 **이미 비준·구현**됐고 envelope/profile 조건을 주입 슬롯으로 봉인했다. 지금
  일곱 곳을 spg 의존으로 바꾸면 **7개 ratified 패키지를 동시 접촉·7 edge 신설** — 시리즈 최대 침습·비권장.
- **선택 — decoupled, plain-bool/scalar producer(edge 0건)**: spg는 **자신의 어휘·이중 아티팩트 모델·결정
  술어**를 저작하고, 출력은 **plain `bool`/`str`/`int`/`CanonicalDecimal`**로 7개 소비자가 **이미 선언한
  주입 signature와 타입 일치**(전부 `bool|None`·`str|None`·`int|None`·fail-closed). composition(spg 출력 →
  소비자 주입 슬롯)은 **caller(미래 Safety Profile Validator/Configuration Distribution/Live-Authorization
  런타임) 소관**이며 Phase 1 밖이다. 근거: (i) #10(brokercap→3소비자)·#11(protective→2소비자)이 produced-bool로
  봉인한 결정과 **완전 동형** — 일관성. (ii) edge 0건 — 시리즈 최대 7-소비자 seam을 edge 없이 봉인.
  (iii) cycle 원천 차단. (iv) **compose seam-sealing**: 타입 일치 + fail-closed 정합으로 seam 조립, **test-only**
  모듈이 spg·(각 소비자)를 **둘 다 import**해 polarity·fail-closed를 대조(테스트 import는 §7.1 package
  closure에 계상되지 않음). **운영자 판단 지점(§10.2)**: produced-bool decoupled(권장) vs 대안 B(소비자 측
  7 edge). **decoupled 권장**(#10/#11 정합·edge/cycle 회피).

**(c) REUSE + PROMOTE 0건.** `HardSafetyEnvelope`·`RuntimeSafetyProfile`은 `tos.canonical.
IndependentIdArtifact`(id⊥digest, `_base.py:328`)·`DigestBoundArtifact`(digest 검증 `canonical_digest ==
H_ver(canonicalize(covered))`, `_base.py:98`)를 REUSE한다. `CanonicalDecimal`은 **이미 `tos.canonical`에
존재**(`__init__.py:56` 실측; #9가 이미 PROMOTE)하므로 envelope/profile numeric limit·§11 boundary
validation에 **추가 PROMOTE 없이** REUSE한다(`1.0` vs `1.00` digest drift 차단·bare `Decimal` 금지 —
§11 step 3 precision/rounding 요구 충족). `classify_record_pair`(`record_pair.py:52`)·`Ordering`/
`OrderingEvent`/`compare_order`(`ordering/_ordering.py`)도 이미 core. ⇒ **PROMOTE = 0건, sibling edge =
0건**(#10/#11과 동형 — 후속 문서로서 PROMOTE 부담 없음). 기대치(orchestrator brief) "sibling edge 0,
PROMOTE 0" 성립.

**(d) `id=f(digest)` 미채택 (canonical REUSE).** Envelope·Profile은 **거버넌스-할당 identity**(version·
approver·effective/expiration date, ADR §7 line 214–224)를 가지며, same-id/diff-bytes(위조·재발행·
contradictory 재발행) 탐지에 `classify_record_pair`(`record_pair.py:52`, `RecordPairKind.CRITICAL_CONFLICT`
`record_pair.py:43`)를 쓰려면 id⊥digest여야 한다(설계 #4·#5·#6·#7·#8·#9·#10·#11 §3.1과 완전 동형;
brokercap `BrokerCapabilityProfile`과 정확히 동형; capsule의 content-addressed `id=f(digest)`와 정반대). ⇒
`IndependentIdArtifact` 채택, `IdDerivedArtifact`(`_base.py:256`) 미채택. **각 Envelope/Profile
Generation은 immutable 레코드**이며 정당한 revalidation/supersession은 **새 generation**(새 id, ADR §5.4
line 123 "cannot be reused after rejection, revocation, rollback, restore, or supersession")이지 in-place
mutation이 아니다(brokercap `records.py:306–330` version-immutable append-only 동형). `tos.spg._base`는
rcl/authority/brokercap 동형의 thin re-export shim.

**(e) 형제/상하류 미import 근거(§3.5 소유권 분할 요지).**
- **`tos.liveauth` 미import(re-arm/arming 하류 소비)**: liveauth가 `continuous_validity`·`rearm_admissible`·
  `atomic_activation_ok`·`layering_within_bounds`를 소유. spg는 그것들이 소비할 envelope/profile bool·scalar를
  **생산**하고 arming·re-arm 결정을 하지 않는다(§12.3 activation≠arming).
- **`tos.rcl` 미import(capacity 하류 종단)**: rcl이 §19 capacity 산술·generation 보존·`effective_limit`(`vector.py:139`)
  를 소유. spg→rcl은 직접 seam 아님 — spg가 generation/version 좌표 생산 → rcl이 covered로 보존(주입 매개).
  capacity mutate 금지(§19 line 492).
- **`tos.authority` 미import(mode/epoch/SoD-epoch 인접)**: authority가 mode·precedence·epoch fence·
  `hard_envelope_incompatible` invalidation을 소유. spg는 `envelope_incompatible` bool·generation을 생산하고
  mode enum·epoch를 재선언하지 않는다(권위 중복 배제). §8 SoD **권한 테이블 좌표**는 담되 effective-principal
  independence enforcement은 authority/ADR-002-015 소관(§3.5).
- **`tos.time` 미import(§18 expiry)**: envelope/profile/approval/attestation validity·expiry는 ADR §18
  line 470 "SHALL use ADR-002-008 Trustworthy Time"이나 spg는 time 산술 불요이므로 **주입 opaque flag**
  (`time_verifiable: bool|None`·`not_expired: bool|None`, None⇒보수)로만 담는다(rcl·orthostate·recon·
  brokercap·protective가 time 미import한 선례 동형; #6식 import-and-compose조차 불요). time은 역으로
  `safety_profile_version`을 주입 소비(`snapshot.py:141`)하는 하류다.
- **`tos.capsule`·`tos.evidence`·`tos.protective`·`tos.brokercap`·`tos.orthostate`·`tos.recon`·`tos.dsl`
  미import**: evidence는 하류 투영(layering 역전 금지)·replay engine은 ADR-002-016·scalar 참조만; capsule
  `safety_configuration_generation`은 하류 좌표; protective `HardEnvelopeRef`는 spg envelope 상한의 주입
  소비자(하류); brokercap broker/software drift는 §16 consumer-compat과 인접하나 broker 축은 brokercap 소유
  (spg는 Consumer Compatibility Manifest match만); orthostate/recon/dsl 무관.

**(f) 앵커 규약 — SPG-INV 앵커, 새 INV 시리즈 창작 금지.** **실측**: ADR-002-014는 **자체 INV 시리즈
`SPG-INV-001..014`(§6 line 151–206, 14종)를 정의한다.** ⇒ 본 계약은 모델 불변식·술어를 **`SPG-INV-001..014` /
`SPG-AC-001..012`(§24 line 620–631) / `SPG-EV-001..012` / §-clause / `SAFE-003/004/010/011/013/035/041/
045/046/047/048/050/051/052`(§25 line 639–646)**에 앵커하고 **새 INV 시리즈를 창작하지 않는다**. 이는 #6
(`SA-INV`)·#8·#10(`BC-INV`)이 자체 INV에 앵커한 것과 동형이며, #9/#11이 INV 부재로 AC/EV에만 앵커한 것과는
상황이 다르다(ADR-002-006/001엔 자체 INV 부재; ADR-002-014엔 있음). self-consistency 최우선.

**(g) SPG-EV = 시리즈 최대 core tier(8행) but 닫는 SPG-EV = 0건.** #10 BC-EV는 22행 전부 EV-L2+라 "0건
완결"이었고, #11 PRD-EV는 2행이 core tier였다. 본 문서의 SPG-EV는 **8행(001·002·003·004·005·006·008·012)이
최소 레벨에 EV-L1 슬라이스 보유**(register line 186–197 실측)라 **시리즈 최대 core tier**다(#8 STATE-EV-001
`EV-L1/2` core·#5 RCLP-EV-001 `EV-L1/3` core 동형·최대판). ⇒ §1 분류는 **core(L1 슬라이스) / predicate-only /
not-Phase-1 3분류**(#11형). **그러나 닫는 SPG-EV = 0건** — L1 슬라이스 저작은 EV closure가 아니다(`/2`·`/3`·
`+Security` 통합·독립 리뷰 잔여; #8·#11이 core tier를 가지면서도 0건 완결이었던 것과 동형). 이 판정은 §1·§4·
§5·§7 전체에 **일관**해야 하며(어떤 §7 test-target도 SPG-EV closure를 주장하지 않음 — #8 C1 lesson 선제 봉합),
finishing 전 self-consistency pass에서 대조한다.

---

## 1. 범위 매핑 — ADR-002-014 조항별 EV-L1 도달성 (닫는 SPG-EV 0건)

EV-level 정의(VER-002-001): **EV-L1 = Model and Property Verification**(state-machine exploration, model
checking, property-based testing, deterministic simulation). **EV-L2 = Component Fault Test**, **EV-L3 =
Integration/Adversarial**, **/5 = System/Chaos**, **+Security = security enforcement**. Phase 1은 EV-L1만이다.

> **결정적 사실 1 — SPG-EV ↔ SPG-AC 1:1, 최소 레벨 실측**: `SPG-EV-001..012`(register line 186–197)는
> ADR §24 `SPG-AC-001..012`(line 620–631)와 제목·번호가 **1:1**(§24 line 616 verbatim "map one-to-one
> to `SPG-EV-001` through `SPG-EV-012`"). register 최소 레벨 실측:
> **EV-L1 슬라이스 보유(8행)** = 001(`EV-L1/3+Security` line 186)·002(`EV-L1/2` 187)·003(`EV-L1/2+Security`
> 188)·004(`EV-L1/3` 189)·005(`EV-L1/3` 190)·006(`EV-L1/3` 191)·008(`EV-L1/3` 193)·012(`EV-L1/3` 197);
> **EV-L1 슬라이스 부재(4행, 최소 ≥ L2)** = 007(`EV-L2/3+Security` 192)·009(`EV-L2/3+Security` 194)·010
> (`EV-L2/3` 195)·011(`EV-L2/3` 196). ⇒ **core tier 8행**(시리즈 최대), predicate-only substrate 4행.
>
> **결정적 사실 2 — authoring ≠ acceptance(닫는 SPG-EV = 0건)**: Phase 1은 각 SPG-EV의 **L1-decidable
> predicate/model substrate**를 저작하나 **어떤 SPG-EV도 닫지 않는다.** (a) core 8행조차 `/2`·`/3`·
> `+Security` 잔여(fault injection·adversarial·security evidence)가 남고, (b) 4행은 최소 ≥ L2, (c)
> VER-002-001 §5 "Registration is not execution"·ADR §24 line 616·§27 line 682/706. ⇒ **"EV-L1-complete
> 주장 금지"**(설계 #2·#4·Time·#5·#6·#7·#8·#9·#10·#11 §1 규율 상속). Owner/Reviewer는 register상 TBD.

**규율 태그(모든 주장에 부착)**: "**predicate/coordinate substrate only; SPG-EV-001..012 전부
NOT_IMPLEMENTED — core 8행은 `/2`·`/3`·`+Security` 통합·독립 리뷰 대기, predicate-only 4행은 EV-L2/L3
fault injection·adversarial·+Security evidence 대기. EV-L1-complete 주장 금지.**"

**ADR-002-014 조항 → Phase-1 분류(core / predicate-only / not-Phase-1[형제 소유·런타임 이연])**:

| ADR 조항 | 요지 | Phase-1 분류 | L1 substrate / 소유 (근거) | SPG-EV |
|---|---|---|---|---|
| **§7** (line 209–228) | Canonical Artifact Contract(type·schema·digest·version·references·validity) | **core (L1 슬라이스)** | `HardSafetyEnvelope`/`RuntimeSafetyProfile` digest-bound 모델 + `canonicalization_reproducible`·unknown-field 거부(§2/§5.2). canonical REUSE. `+Security` 잔여. | **003** |
| **§9** (line 257–273) | Envelope Governance + non-silent expansion | **core (L1 슬라이스)** | `profile_within_envelope`·`envelope_expansion_enlarges_nothing`(§4.1/§5.1) — **SPG-EV-001 substrate**. produces `hard_safety_envelope_not_expanded`. `/3+Security` 잔여. | **001** |
| **§10** (line 279–294) | Runtime Safety Profile Content(explicit·no wildcard) | **core (L1 슬라이스)** | Profile 모델 + wildcard/미선언 Critical field 거부(§2.3/§5.2). §11과 함께 SPG-EV-002/003. | **002/003** |
| **§11** (line 300–317) | Semantic Validation(units·numeric·cross-field·direction) | **core (L1 슬라이스)** | `semantic_validation → SemanticValidationResult`(§5.2) — **순수 술어 노다지**(step 3/4/5/11/12 순수 L1). step 7/9/10 주입. `/2` 잔여. | **002/003** |
| **§13** (line 370–387) | Atomic Activation(mixed-generation 금지) | **core (L1 슬라이스)** | `activation_atomic`(§5.3) — **SPG-EV-004 substrate**. quorum commit·staging·attestation collection은 런타임. `/3` 잔여. | **004** |
| **§15** (line 413–426) | Concurrency/Ordering(stale-base) | **core (L1 슬라이스)** | `activation_serializable`·`stale_base_rejected`(§5.4) — **SPG-EV-005 substrate**. `tos.ordering` REUSE. `/3` 잔여. | **005** |
| **§14** (line 393–407) | Restrictive Changes/Emergency Overrides | **core (L1 슬라이스)** | `restrictive_override_admissible`·`change_direction`(§5.5) — **SPG-EV-006 substrate**. economic continuity 수치는 rcl 주입. `/3` 잔여. | **006** |
| **§18** (line 470–482) | Expiry & Trustworthy Time | **core (L1 슬라이스)** | `expiry_suspends_new_risk`·`expiry_revives_nothing`(§5.6) — **SPG-EV-008 substrate**. time validity는 주입 flag. `/3` 잔여. | **008** |
| **§21** (line 522–539) | Evidence/Metrics/Alerts(replay 재구성) | **core (L1 슬라이스)** | frozen digest-bound append-only 레코드 substrate(§5.7) — **SPG-EV-012 substrate**. replay ENGINE은 ADR-002-016. `/3` 잔여. | **012** |
| **§17** (line 452–464) | Rollback/Restore/DR | **predicate-only** | `rollback_requires_new_generation`·non-revival 술어(§6.1). restore-generation fence는 **rcl `restore_generation`**(`records.py:465`)·+Security historical-signature 이연. 최소 `EV-L2/3+Security`. | **007** |
| **§8** (line 234–251) | Authority/SoD + break-glass | **predicate-only** | SoD 권한 테이블 좌표 + `break_glass_confined`(§6.2, break-glass는 HALT/restrictive만·확대/rearm 금지 line 251). effective-principal independence는 **ADR-002-015(HAG-EV)+Security** 이연. 최소 `EV-L2/3+Security`. | **009** |
| **§16** (line 432–446) | Distribution/Consumer Enforcement | **predicate-only** | `compatibility_manifest_matches`(§6.3, Consumer Compatibility Manifest §5.6 소유). software drift는 **ADR-002-029**·broker drift는 **brokercap #10** 이연. final-egress binding은 ADR-002-013 런타임. 최소 `EV-L2/3`. | **010** |
| **§20** (line 500–517) | Failure Modes(missing/contradictory containment) | **predicate-only** | `bundle_complete`·`missing_config_denies`(§6.4). "economic state 보수적 capacity-covered" 부분은 **rcl** 런타임 이연. 최소 `EV-L2/3`. | **011** |
| **§12** (line 323–364) | Lifecycle State Models | **core substrate(분산)** | `EnvelopeState`/`ProfileState` 전이 테이블 + `*_transition_allowed`(§2.2/§5) — non-revival 실현. §12.3 activation≠arming은 liveauth 소관. | 001–012 공통 |
| **§19** (line 488–494) | Economic-State/Capacity Continuity | **not-Phase-1 (rcl 소유)** | rcl generation 보존·capacity 산술·`effective_limit` min(`records.py:101–102/469`·`vector.py:139`). spg는 generation/version 좌표 + 두 피연산자 scalar **생산**만(min 미수행). capacity mutate 금지(line 492). | 006/011 (rcl) |
| **§13 quorum·§16 distribution·§16 egress** | Safety Commit Log commit·staging·attestation·egress | **not-Phase-1 (런타임)** | quorum commit(ADR-002-012)·distribution service·consumer attestation·final-egress(ADR-002-013). spg는 결정 bool만. | 004/005/010 (런타임) |
| **§8 effective-principal·§26 item 3** | 인간 authority·approval quorum·delegation·break-glass credential | **not-Phase-1 (ADR-002-015)** | HAG-EV(+Security) effective-principal collapse·credential control. spg는 SoD 테이블 좌표·directional confinement만. | 009 (HAG) |
| **§26 item 1/4/13** | canonical format·restrictive-comparison system·replay engine 선택 | **not-Phase-1 (Phase-0/ADR-002-016)** | 제품·알고리즘 선택은 §9.2 Phase-0. replay engine은 ADR-002-016. | — |

---

## 2. 데이터 모델 계약

**표현 원칙**: 모든 아티팩트는 **pydantic v2 frozen 모델**(`ConfigDict(frozen=True, extra="forbid")`,
`tos.canonical.FrozenModel` REUSE — `_base.py:73` 실측)로 저작한다. `extra="forbid"`는 **§7 line 226
"Unknown fields that can affect authority SHALL be rejected"·§11 step 12 "absence of a bypass through
omitted, unknown, deprecated, duplicated, or extension fields"의 스키마 수준 실현**이다(브레이스 없는
unknown field ⇒ 구성 실패). frozen은 append-only(§21 auditable·§5.4 no-reuse)의 레코드 수준 실현이며
**모델에는 update/delete 연산이 존재하지 않는다**(설계 #4 §2.0 규율 상속). enum 값·필드명은 ADR §5–§12의
용어를 **verbatim**으로 쓴다(스펙 용어 = 코드 용어, 설계 #1 §2.4; 에라타 defect class 선제 방지).

### 2.0 소유권 골격 — spg는 canonical의 하류, 7개 형제의 upstream

spg가 **소유·저작하는 것**: governance 어휘(`EnvelopeState`·`ProfileState`·`ChangeDirection`·
`BundleMemberKind`·`ValidationReason`·`ActivationVerdict`) + `HardSafetyEnvelope`·`RuntimeSafetyProfile`
digest-bound 레코드 + `SafetyConfigurationBundle`·`ActivationRecord`·`ConsumerCompatibilityManifest`·
governed-dimension limit value + envelope-dominance/semantic-validation/atomic-activation/stale-base/
restrictive-precedence/expiry/rollback/break-glass/compat-manifest/bundle-complete **술어**. **소유하지 않는
것**: Live Authorization·re-arm(liveauth) · capacity 산술·generation 보존 mechanics(rcl) · mode/precedence/
epoch/SoD-epoch(authority) · time expiry 산술(time) · evidence replay engine(ADR-002-016) · effective-principal/
approval workflow(ADR-002-015) · quorum commit·distribution·egress enforcement(런타임) · numeric limit/
validity(INSTANCE + Verification Profile, 주입).

### 2.1 digest-bound / plain-frozen / value / reference 분류 (총괄)

| 아티팩트 | 종류 | id 필드(독립) | digest 필드 | covered / 내용 |
|---|---|---|---|---|
| `HardSafetyEnvelope` (§5.1; §7; §9) | **IndependentIdArtifact + 독립 id** | `envelope_id`(+`envelope_generation`) | `canonical_digest` | mandatory dimensions·max authority limit·permitted scope·prohibited fallbacks·compatibility floors·residual-risk ceiling(§9 line 257–267) + version block(§7) + evidence 참조 scalar |
| `RuntimeSafetyProfile` (§5.2; §7; §10) | **IndependentIdArtifact + 독립 id** | `profile_id`(+`profile_generation`) | `canonical_digest` | one exact envelope id+generation(§10 line 281) + explicit scope·per-action/aggregate limit·permitted behaviors·fallback rules(≤ primary)·escalation/re-arm 조건(§10 line 279–292) + version block + evidence 참조 |
| `SafetyConfigurationBundle` (§5.3) | **IndependentIdArtifact** | `bundle_id`(+`bundle_generation`) | `canonical_digest` | Envelope + Profile + `tuple[BundleMemberRef]`(§2.2(4) 대조표 **포함 29항**: Broker Capability·Verification·Recovery Barrier·Critical Input·Venue·Order Construction·Aggregate Risk·Action Flow·Trading Approval·Currentness·Restricted-Live·Deviation·Incident·Monitoring·Software Release·Post-Trade Finality·Failure-Domain·time/calendar 등 — id/gen/digest scalar; **이연 7항은 Phase-0 주입 ref**) |
| `ActivationRecord` (§5.7) | **IndependentIdArtifact + 독립 id** | `activation_id` | `canonical_digest` | `profile_generation`·complete artifact digests·scope·approval ids·compatibility attestation refs·validity interval·`predecessor_generation`·restrictive-generation effects(§5.7 line 133–135). **grants no Live Authorization by itself**(line 135). |
| `ConsumerCompatibilityManifest` (§5.6) | **IndependentIdArtifact + 독립 id** | `manifest_id` | `canonical_digest` | consumer identity + exact schemas·fields·units·calculations·constraints·failure semantics 선언(§5.6 line 129–131) + Consumer Compatibility Manifest version |
| `GovernedDimensionLimit` (§9/§10) | **plain FrozenModel(value)** | — | — | `dimension: str`·`envelope_max: CanonicalDecimal\|None`·`profile_value: CanonicalDecimal\|None`·unit/multiplier/sign/precision/rounding/boundary 좌표(§7 line 217·§11 step 3) |
| `EnvelopeVersion`/`ProfileVersion` (§7) | **plain FrozenModel(value)** | — | — | version·effective date·evidence-package version·approver identity·expiration/revalidation date·superseded link·change classification(§7 line 214–224 verbatim) |
| 주입 입력 `ActivationInputs`·`RestrictiveOverrideInputs`·`ExpiryInputs`·`SemanticValidationInputs`·`CompatibilityQuery` | **plain FrozenModel(injected)** | — | — | mixed-generation flag·stale-base 좌표·time-verifiable flag·cross-field 판정·consumer identity 등(전부 `bool\|None`/scalar, fail-closed) |
| `EnvelopeState`·`ProfileState`·`ChangeDirection`·`BundleMemberKind`·`ValidationReason`·`ActivationVerdict` | **StrEnum(로컬 값 타입)** | — | — | (lifecycle·direction·member·reason·verdict 원소) |
| `CanonicalDecimal` (limit/boundary) | **REUSE core `tos.canonical`**(이미 존재) | — | — | (§0.4c — PROMOTE 불필요) |

> **`IdDerivedArtifact` 채택 아티팩트 = 0건. PROMOTE = 0건**(records substrate·CanonicalDecimal 전부 이미
> core). Envelope/Profile/Bundle/ActivationRecord/Manifest는 거버넌스-할당 identity(§7)를 가진다 —
> same-id/diff-bytes 위조·contradictory 재발행 탐지(`classify_record_pair`)에 id⊥digest 필수 ⇒
> `IndependentIdArtifact`(이미 core) 상속(brokercap `BrokerCapabilityProfile`과 정확히 동형). `tos.spg._base`
> 는 rcl/authority/brokercap 동형의 thin re-export shim(신규 형제 edge 없음).

### 2.2 어휘 (verbatim 전사 — 에라타 defect class 주의)

> **전사 규율**: 아래 enum 값·순서는 ADR 원문에서 **verbatim**이며, StrEnum 값 문자열은 스펙 토큰을 그대로
> 쓴다(설계 #1 §2.4). 각 블록 옆에 ADR line 실측을 병기한다.

**(1) `EnvelopeState`(StrEnum) — ADR §12.1 (line 325–332), 9종 verbatim:**

```text
DRAFT
VALIDATED
APPROVED
STAGED
ACTIVE
REJECTED         ({DRAFT, VALIDATED, APPROVED, STAGED} -> REJECTED)
RESTRICTED       (ACTIVE -> RESTRICTED)
SUPERSEDED       (ACTIVE -> SUPERSEDED)
REVOKED          (ACTIVE -> REVOKED)
```

§12.1 line 334 verbatim: "`SUPERSEDED`, `REVOKED`, or restored generations never return to `ACTIVE`." ⇒
전이 테이블 `_ENVELOPE_TRANSITIONS`(frozenset)에 terminal→ACTIVE 부재(non-revival; liveauth
`_LIVE_AUTHORIZATION_TRANSITIONS` `predicates.py:162` 동형).

**(2) `ProfileState`(StrEnum) — ADR §12.2 (line 338–346), 11종 verbatim:**

```text
DRAFT
VALIDATED
APPROVED
STAGED
ACTIVATION_READY
ACTIVE
REJECTED         ({DRAFT, VALIDATED, APPROVED, STAGED, ACTIVATION_READY} -> REJECTED)
SUSPENDED        (ACTIVE -> SUSPENDED)
SUPERSEDED       (ACTIVE -> SUPERSEDED)
REVOKED          (ACTIVE -> REVOKED)
EXPIRED          (ACTIVE -> EXPIRED)
```

§12.2 line 348 verbatim: "No transition from `SUSPENDED`, `SUPERSEDED`, `REVOKED`, or `EXPIRED` returns the
same Profile Generation to `ACTIVE`. Reuse of identical content still requires a new generation, current
validation, current approvals, activation, and re-arm." ⇒ non-revival + no-content-reuse.

**(3) `ChangeDirection`(StrEnum) — ADR §5.9 (line 141–145)·§11 step 11 (line 312)·§14, 3종 (v1.1 MINOR-1):**

```text
RESTRICTIVE            (모든 credible dimension에서 deny/narrow만 — §14 line 393)
PERMISSIVE             (한 credible interpretation이라도 확대 — §5.9 line 143)
AUTHORITY_INCREASING   (previously denied/more-constrained를 permit, 또는 순서 불가·미증명 — §5.9 line 143/145)
```

§5.9 line 145 verbatim: "**When monotonic direction cannot be proven, the change is authority increasing.**"
§11 line 317 verbatim: "If one dimension cannot be ordered conservatively, **the change is authority
increasing** and the scope remains non-live until independently resolved." ⇒ **"unorderable IS authority
increasing"이므로 `change_direction`은 `UNORDERABLE`을 별도 enum 값으로 반환하지 않고 순서불가·미증명을
`AUTHORITY_INCREASING`으로 접는다**. 순서불가 자체는 enum 값이 아니라 **`ValidationReason.UNORDERABLE_DIRECTION`
(§2.2(5))로만 reason_set에 실린다** — **v1.1 MINOR-1**: v1.0의 이중 표현(enum 값 `UNORDERABLE` + reason)을 제거해
소비자의 `direction == AUTHORITY_INCREASING` 검사가 별도 `UNORDERABLE` 값으로 우회되는 fail-open 인접성을
봉합한다(enum 제거가 ADR §11:317 "unorderable IS authority increasing"에 더 충실 — 근거 기록).

**(4) `BundleMemberKind`(StrEnum) — ADR §5.3 (line 117–119) 대조표 (v1.1 MAJOR-3: "verbatim closed set"
주장 철회).** **결정(선택지 b)**: ADR §5.3 line 119는 36개 항목의 산문 나열이며 "complete closed set"이라
서술하나, 그 중 **하위 generation·compatibility graph·runtime-attestation·referenced policy objects**는
**ADR-002-029/030 등이 소유하고 §27 item 18–19·§9.2 item 14로 Phase-0 bundle-binding에 이연**된다. Phase-1
`BundleMemberKind`는 **top-level 명명 아티팩트만** 모델링하고 나머지는 이연한다. 산문 나열은 v1.0에서 Release
Generation 등 6항 비대칭 누락을 낳았으므로(대칭 항목 Post-Trade Obligation Generation은 포함·Release
Generation만 탈락), line 119 **전 36항을 2열 대조표로 고정**해 누락을 구조적으로 불가능하게 한다:

| # | ADR §5.3 line 119 항목 (verbatim) | Phase-1 처리 |
|---|---|---|
| 1 | Hard Safety Envelope | **포함**(`BundleMemberKind` + 자체 아티팩트 §2.1) |
| 2 | Runtime Safety Profile | **포함**(+ 자체 아티팩트) |
| 3 | Broker Capability Profile | **포함**(BundleMemberRef; 축 brokercap #10) |
| 4 | Verification Profile | **포함**(BundleMemberRef; §8.2 self-ref) |
| 5 | Recovery Barrier Policy | **포함**(BundleMemberRef; ADR-002-017) |
| 6 | Critical Input Policy | **포함**(BundleMemberRef; ADR-002-018) |
| 7 | Venue Constraint Policy | **포함**(ADR-002-019) |
| 8 | Order Construction Policy | **포함**(ADR-002-020) |
| 9 | Aggregate Risk Policy | **포함**(ADR-002-021) |
| 10 | Adverse Scenario Set | **포함** |
| 11 | Action Flow Policy | **포함**(ADR-002-022) |
| 12 | Trading Approval Policy | **포함**(ADR-002-023) |
| 13 | Currentness Policy | **포함**(ADR-002-024) |
| 14 | Restricted-Live Trial Policy | **포함**(ADR-002-025) |
| 15 | Safety Deviation Policy | **포함**(ADR-002-026) |
| 16 | Active Deviation Set (empty or complete) | **포함**(explicit empty/complete) |
| 17 | Safety Incident Policy | **포함**(ADR-002-027) |
| 18 | Active Safety Incident Set (empty or complete) | **포함** |
| 19 | Safety Monitoring Policy | **포함**(ADR-002-028) |
| 20 | Critical Telemetry Manifest | **포함** |
| 21 | Monitor Coverage Manifest | **포함** |
| 22 | Software Release Policy | **포함**(ADR-002-029) |
| 23 | exact Admitted Release Set | **포함** |
| 24 | **Release Generation** | **이연**(ADR-002-029 하위 generation·§27 item 18·§9.2 item 14) |
| 25 | Release Artifact Manifest | **포함** |
| 26 | **compatibility graph** | **이연**(ADR-002-029·§9.2 item 14) |
| 27 | **runtime-attestation requirements** | **이연**(ADR-002-029·§9.2 item 14) |
| 28 | Post-Trade Finality Policy | **포함**(ADR-002-030) |
| 29 | **Post-Trade Obligation Generation** | **이연**(ADR-002-030 하위 generation·§27 item 19·§9.2 item 14; #24와 대칭) |
| 30 | complete Active Economic Obligation Set | **포함** |
| 31 | Statement Coverage Manifest | **포함** |
| 32 | **obligation/finality compatibility requirements** | **이연**(ADR-002-030·§9.2 item 14) |
| 33 | Failure-Domain Allocation Matrix | **포함**(ADR-002-009) |
| 34 | applicable time/calendar data | **포함** |
| 35 | **software compatibility manifests** | **이연**(§16 consumer-compat·§6.3·Phase-0) |
| 36 | **referenced policy objects** | **이연**(재귀 참조·§9.2 item 14) |

**포함 = 29항(Phase-1 `BundleMemberKind`) · 이연 = 7항(#24·26·27·29·32·35·36, Phase-0 bundle-binding).** 29+7=36
(line 119 전수 대조 — 비대칭·누락 구조적 불가). `bundle_complete`(§6.4)는 **포함 29항의 present·resolved·
immutable**을 검사하고 **이연 7항은 Phase-0 주입 ref**로 fold하며, **미열거·미해소 ⇒ 전 member 필요로 취급**
(§4.1 vacuous-complete 금지). SPG-INV-002(complete closed bundle)는 Phase-1에서 "29 modeled member + 7 Phase-0
injected ref 전부 resolved"로 실현되고 하나라도 미해소면 new-risk 부재.

**(5) `ValidationReason`(StrEnum, 로컬) — §11/§20 reject 사유 class:** `UNIT_OR_MULTIPLIER_MISMATCH`(§11
step 3·§20 line 505)·`SIGN_PRECISION_ROUNDING_DEFECT`(step 3)·`OVERFLOW_UNDERFLOW_NAN_INFINITY`(step 3)·
`CROSS_FIELD_CONSTRAINT_VIOLATION`(step 5)·`EXCEEDS_ENVELOPE`(step 6·§9)·`UNKNOWN_OR_DUPLICATE_FIELD`(step 12·
§20 line 504)·`SCHEMA_INCOMPLETE_OR_DOWNGRADE`(step 2·§24 SPG-AC-003)·`FLOATING_REFERENCE`(§7 line 219)·
`UNORDERABLE_DIRECTION`(step 11·line 317)·`CANONICAL_DIGEST_IRREPRODUCIBLE`(§7 line 228). (semantic
validation reason set의 원소; §5.2 rich verdict.)

**(6) `ActivationVerdict`(StrEnum, 로컬 3종) — §13 realization:**

```text
COMMITTABLE    (§13 모든 positive 조건 충족 — atomic single-generation, no mixed, compatible, envelope-bounded)
DENIED         (mixed generation / partial / incompatible / stale-base / unverifiable — §13 line 385/§15)
DEFERRED       (staging/attestation 미완 — 런타임 quorum commit 대기; not-live, §13 line 383)
```

`ActivationVerdict`에는 **"assume-committable" 기본 생성 경로가 없다** — 술어만 산출(§4.1 fail-open 봉합;
brokercap `Admissibility` 동형).

### 2.3 `HardSafetyEnvelope`/`RuntimeSafetyProfile` covered + self-exclusion (설계 #4 §3.3 상속)

covered(Layer-1) = version block(§7 verbatim) + governed-dimension limit tuple(정렬) + scope 좌표 +
(Profile) one exact envelope id+generation + permitted-behavior/fallback 좌표 + evidence-package 참조 scalar.
preimage 제외: `envelope_id`/`profile_id`·`canonical_digest`·`canonicalization_version`·`status`(ArtifactStatus
lifecycle 마커)·`*_order`(ledger placement)·파생 역참조. **TBD/null이 covered에 하나라도 있으면
pre-issuance(status=DRAFT), digest 불가**(`_base.py:181` DRAFT null-digest·`IndependentIdArtifact.
_require_independent_id_when_issued` `_base.py:352`). `envelope_id`/`profile_id` ⊥ `canonical_digest`(§3.1).
**`_REQUIRED_COVERED`는 structural identity/scope/version/class만**(numeric magnitude는 제외해 Phase-1 null
bound에서 ISSUED 도달 가능 — brokercap `records.py:333` 규율 상속; missing magnitude는 consuming 술어에서
fail-closed).

> **핵심 설계 결정 — Envelope/Profile은 immutable generation별 append-only(#10 brokercap 상속)**: Envelope/
> Profile은 시간에 따라 **재발행**된다(§5.4 Profile Generation·§9 line 269 envelope change→new generation·
> §12 supersession). 하나의 stable id에 mutable 내용을 담으면 정당한 revalidation이 same-id/diff-bytes
> `CRITICAL_CONFLICT`로 **오탐**된다. ⇒ **각 generation은 fresh id를 가진 immutable 레코드**다(§5.4 line
> 123 "cannot be reused after rejection, revocation, rollback, restore, or supersession"). same identity +
> diff bytes ⇒ `CRITICAL_CONFLICT`(위조·재발행 위조만); 정당한 개정 ⇒ **새 generation**(supersession link).
> generation 순서는 `tos.ordering`(§3.2). `RESTRICTED`/`SUPERSEDED` status(§12.1)는 state로 표현하지
> last-write-wins로 덮지 않는다.

---

## 3. canonical / ordering REUSE + 7-소비자 produced-bool seam + 형제 경계

### 3.1 canonical REUSE + `id=f(digest)` 미채택 (설계 #4·…·#11 §3.1 상속)

`HardSafetyEnvelope`·`RuntimeSafetyProfile`·`SafetyConfigurationBundle`·`ActivationRecord`·
`ConsumerCompatibilityManifest`는 `tos.canonical.IndependentIdArtifact`(`_base.py:328`)·`DigestBoundArtifact`
(`canonical_digest == H_ver(canonicalize(covered))`, `_base.py:98`)를 REUSE한다. canonicalizer는
`tos.canonical` registry + `EVL1ProvisionalCanonicalizer`(`ev-l1-provisional-0`) REUSE, **신규 canonicalizer
없음**(프로덕션 canonical semantic form은 Phase-0 §9.2 — ADR §26 item 1). numeric limit·§11 boundary는
**이미 core인 `CanonicalDecimal`**(`__init__.py:56`) REUSE — `1.0` vs `1.00`의 digest drift 차단(§11 step 3
precision/rounding; bare `Decimal` 금지). **`id=f(digest)`(`IdDerivedArtifact`) 미채택**: §2.1 근거(거버넌스-
할당 identity + same-id/diff-bytes 위조·재발행 탐지 — `classify_record_pair` `record_pair.py:52`). **PROMOTE
= 0건**.

### 3.2 ordering REUSE (activation-record / generation append-only 순서)

Profile/Envelope Generation·Activation Record의 append-only 순서(§15 line 413 "ordered against one exact
predecessor generation")는 신규 저작하지 않고 `tos.ordering`(`_ordering.py` 실측: `Ordering`·`OrderingEvent`·
`compare_order`, `tos.canonical`만 의존)를 REUSE한다. `OrderingEvent.quorum_commit_index`(`_ordering.py:67`)가
§13 line 379 "Safety Commit Log ordering"의 좌표다. **wall clock은 순서를 만들지 않는다**(`_ordering.py:24`
규율; SPG-INV-003 line 161 "`latest`, local file state, cache state, or deployment order is not authority"와
정확히 정합) — spg는 clock을 읽지 않는다(§3.5). `activation_serializable`(§5.4)은 `predecessor_generation`이
`current_active_generation`과 일치하는지의 **순수 동등 검사**이며, 순서 자체는 `compare_order`가 담당한다.
light REUSE(core 의존, 신규 edge 아님).

### 3.3 REUSE 요약 표

| substrate | 결정 | 근거 |
|---|---|---|
| `FrozenModel`·`DigestBoundArtifact`·`IndependentIdArtifact`·`ArtifactStatus` | **REUSE(core `tos.canonical`)** | §3.1; 신규 없음 |
| `classify_record_pair`·`RecordPairKind` | **REUSE(core, 이미 PROMOTE됨)** | §3.1; same-id/diff-bytes·contradictory 재발행 |
| `CanonicalDecimal` | **REUSE(core, #9가 이미 PROMOTE)** | §3.1; limit·§11 boundary·PROMOTE 불필요 |
| `Ordering`·`OrderingEvent`·`compare_order` | **REUSE(core `tos.ordering`)** | §3.2; generation/activation 순서·quorum_commit_index |
| governance 어휘·이중 아티팩트 모델·11 결정 술어 | **로컬 저작** | §0.4a/§2.2; ADR §5–§21 verbatim·decision-side |
| liveauth `hard_and_runtime_versions_match`·`*_not_expanded`·`*_covers_enlarged`·`atomic_activation_ok` 입력·authority `hard_envelope_incompatible`·`*_version`/`*_generation`/`*_limit` scalar | **미소유 — produced-bool/scalar로만 공급** | §3.4; 7-소비자 seam |
| Live Authorization·re-arm·capacity·mode/epoch/SoD-epoch·time expiry·replay engine·effective-principal·quorum·distribution·egress·numeric limit | **미소유 — 런타임/INSTANCE/ADR-002-012/013/015/016 이연** | §3.5 |
| PROMOTE | **0건** | §3.1 |
| sibling edge | **0건** | §3.4 |

### 3.4 liveauth / authority / rcl / time / capsule / evidence / protective 경계 — produced-bool seam, edge 0 (중심, 코드 실측)

**(a) spg = produced-bool/scalar producer(§0.4b).** spg는 7개 소비자를 **import하지 않고**, 그들이 소비할
**plain bool/scalar**를 생산한다. seam 계약(compose) — **소비자는 전부 이미 비준·구현됨**(§0.4b 표 참조).
핵심 3-bool seam:

- `hard_and_runtime_versions_match` = envelope·profile version이 activation record와 일치 ∧ mixed-generation
  부재 ⇒ liveauth `ContinuousValidityInputs`(`state.py:135`) 채움. **None/False⇒invalid**.
- `envelope_not_expanded` = envelope generation advance가 active profile을 확대하지 않음(§9 line 269·
  SPG-INV-007) ⇒ liveauth `Safe053VariantAttestation`(`state.py:164`) 채움.
- `envelope_profile_covers_enlarged` = delta scope가 현 envelope/profile로 전부 커버 ∧ envelope 미확대 ⇒
  liveauth `InPlaceExpansionInputs`(`state.py:205`) 채움.

scalar seam: `active_envelope_version`/`active_profile_version`(str) → liveauth/authority/rcl/time covered
`*_version`(v1.1 MAJOR-2: protective는 version scalar **미소비** — envelope 상한만 `HardEnvelopeRef`
`records.py:94`로 주입, §4.4); envelope 상한·profile 운영값 두 피연산자 scalar → liveauth `LimitLayering`·rcl `effective_limit`(min은 rcl 수행, `vector.py:139`);
`active_generation`/activation digest(int/str) → authority `*_generation`·rcl `profile_generation`·capsule
`safety_configuration_generation`·evidence `safety_configuration_activation_record_digest`.

- **타입 정합 + fail-closed 정합**: spg 산출은 전부 `bool`/`str`/`int`/`CanonicalDecimal`(bool은 양성 증명
  에서만 `True`). 소비 signature는 전부 `bool|None`/`str|None`/`int|None`(`None`⇒fail-closed)이라 spg `False`와
  caller-supplied `None`이 둘 다 안전. **polarity 봉합(#6 fail-open REJECT 교훈)**: producer는 결코 "미판정 ⇒
  True"로 새지 않는다(§4.1).
- **composition(런타임 배선) = caller 소관**: spg 산출 bool/scalar를 소비자 주입 슬롯으로 배선하는 **런타임**은
  **미래 Safety Profile Validator/Configuration Distribution/Live-Authorization Service**(EV-L3)가 한다. Phase
  1은 #10/#11의 seam 이연과 **동형으로 런타임 배선을 이연**한다.
- **seam cross-check = MANDATED(test-only)**: Phase 1은 **test-only** 모듈(`tos/tests/spg/test_seam_liveauth.py`·
  `test_seam_authority.py`·`test_seam_rcl.py` 류)에서 spg·(각 소비자)를 **둘 다 import**해 spg 산출의 **의미·
  polarity·fail-closed 거동**이 소비 signature 기대와 **일치함을 assert한다**(예: spg `envelope_not_expanded`
  =False ⇒ liveauth SAFE-053 variant 실패측; `hard_and_runtime_versions_match`=True ⇒ continuous-validity
  통과가능측; `envelope_incompatible`=True ⇒ authority invalidated측 `predicates.py:701`). **이 테스트는
  package edge가 아니다** — 테스트 import는 §7.1 `import tos.spg` package-closure에 **계상되지 않으므로**
  런타임 패키지의 sibling-edge-0건은 유지된다(#10 v1.1·#11 강화 동형).
- **cycle 부재**: spg↛{liveauth,authority,rcl,time,capsule,evidence,protective,brokercap} ∧ 그들↛spg. acyclic
  명백(그들은 envelope/profile 조건을 주입 좌표로 소비).

**(b) spg는 activate/authorize/transmit/release하지 않는다(ADR §1 line 40·§13/§16 런타임).** spg는 결정
**bool/scalar만** 생산하고 activation commit·egress transmit·capacity mutation·authorization issue·
KnowledgeState set 메서드가 **부재**하다(§4.5). 소비 authority(liveauth/rcl/authority/Safety Profile Validator
런타임)가 실제 action을 gate한다 — "The Safety Profile Validator validates and attests configuration; it does
not create capacity, issue Live Authorization, or transmit orders"(§1 line 40).

**(c) 운영자 판단 지점**: seam을 **plain-bool decoupled(edge 0건)**로 둘지 대안 B(소비자 측 7 edge)로 갈지 —
decoupled 권장(§0.4b; edge·cycle 회피, #10/#11 정합).

### 3.5 소유권 분할표 — spg가 소유 / 형제에서 소비·생산 (본 문서 최대 함정 지대, #11 §3.5 상속)

> **소유권 분할 명시(#8 C1·#11 §3.5 교훈 — cross-section 혼동 선제 봉합)**: ADR-002-014는 다른 모든 패키지가
> 소비하는 **주입 bounds의 거버넌스**다. 시리즈 전체가 "bound는 주입, 값 승인은 Bounds-Approver 게이트"
> 규율을 따라왔고(#5–#11 §8), **Safety Profile/Envelope이 바로 그 주입 값들의 canonical 운반 아티팩트**다.
> spg는 그 아티팩트와 거버넌스 술어를 소유하고, 값의 **수치 자체·capacity mutation·arming·approval workflow**는
> 소유하지 않는다. 함정: spg가 liveauth의 layering·rcl의 effective-limit·authority의 invalidation·time의
> expiry를 재저작하면 권위 중복(#8 C1). 아래 표가 경계를 코드 실측으로 고정한다.

| ADR 조항/개념 | spg 소유 (Phase 1) | 형제 소유 (재저작 금지) | seam 방향(실측) |
|---|---|---|---|
| §9 envelope dominance | `profile_within_envelope`·`envelope_not_expanded`(§5.1) | liveauth layering 검사(`layering_within_bounds` `predicates.py:417`) | spg 생산 bool → liveauth 소비(`state.py:164`) |
| §7 effective limit | envelope 상한·profile 운영값 두 피연산자 scalar 생산(**min 미수행**) | rcl 함수 `effective_limit` min 산술(`vector.py:139`)·liveauth `LimitLayering` 4-layer(`state.py:69–89`) | spg scalar → rcl `effective_limit`/liveauth 소비 |
| §11 semantic validation | `semantic_validation → result+reason`(§5.2) | (aggregate effect step 7 = ARE/rcl 주입; software step 8 = ADR-002-029) | spg 결과 bool → liveauth `units_compatible`(`predicates.py:458`) |
| §13 atomic activation | **seam 출력 = 4 개별 bool**; spg 내부 `activation_atomic→ActivationVerdict`는 SPG-EV-004 property용(§5.3 이중-레이어, v1.1 MINOR-2) | liveauth `atomic_activation_ok`(`predicates.py:454`, 4-bool fold)·quorum commit(ADR-002-012 런타임) | spg 생산 4 bool → liveauth fold 소비 |
| §14 restrictive | `restrictive_override_admissible`·`change_direction`(§5.5) | authority mode/precedence(`AuthorityState`)·rcl capacity 보존 | spg 방향 verdict → (caller) → authority/rcl |
| §15 stale-base | `activation_serializable`(§5.4) | ordering `compare_order`(REUSE)·quorum(ADR-002-012) | spg 동등 검사 + ordering REUSE |
| §18 expiry | `expiry_suspends_new_risk`·`expiry_revives_nothing`(§5.6) | time validity 산술(`snapshot.py:141`·`predicates.py:618–673`)·liveauth `authorization_revived_by_nothing` | spg 주입 time flag 소비; version scalar 생산 → time 소비 |
| §19 economic continuity | envelope/profile generation·version 좌표 **생산** | rcl generation 보존·capacity 산술·`effective_limit` min(`records.py:101–102/469`·`vector.py:139`; capacity mutate 금지 line 492) | spg scalar → rcl covered 보존 |
| §9 envelope incompatibility | `envelope_incompatible` bool 생산 | authority invalidation(`predicates.py:640/701`)·suspension·re-arm | spg bool → authority 소비 |
| §8 SoD | SoD 권한 테이블 좌표·`break_glass_confined`(§6.2) | authority epoch·ADR-002-015 effective-principal(HAG-EV +Security) | 좌표만; enforcement 이연 |
| §16 consumer compat | `compatibility_manifest_matches`(§6.3)·`ConsumerCompatibilityManifest` | brokercap broker drift(#10)·ADR-002-029 software·ADR-002-013 egress | spg match bool; broker/software 주입 |
| §17 rollback | `rollback_requires_new_generation`(§6.1) | rcl `restore_generation` fence(`records.py:465`)·+Security historical-signature | 술어만; restore-fence 이연 |
| §21 replay | frozen digest-bound 레코드 substrate(§5.7) | evidence replay engine(ADR-002-016, `replay.py`) | spg 레코드 → evidence 참조(`replay.py:113`) |

---

## 4. 불변식

모두 frozen 모델 구성-불변식(구성 실패) 또는 순수 술어(property)로 실현한다. **앵커는 SPG-INV-001..014(§6)·
SPG-AC-001..012(§24)·§-clause·SAFE-###**이며 **새 INV 시리즈를 창작하지 않는다**(§0.4f). **fail-closed
discipline**: 미증명/초과/mixed/stale/expired에 대한 술어는 절대 vacuous COMMITTABLE/True가 되지 않으며, live
허용은 *양성 증명*을 요구하고, 각 가드에 **both-ways canary**(가드가 실제로 발화함)를 붙인다.

### 4.1 envelope dominance / non-silent expansion 중앙 불변식 (중앙 — ADR §1 line 19–26; SPG-INV-001/007; §9)

**중앙 결정**: "Runtime Safety Profile은 Hard Safety Envelope constraint를 초과·재정의·비활성화·누락·재해석할
수 없다." ADR SPG-INV-001 line 153 verbatim. §1 line 21–26 verbatim: "`Transmission Capability <= Live
Authorization <= active Runtime Safety Profile <= active Hard Safety Envelope`". 실현(구조적 3중):

1. **`profile_within_envelope`에 permissive 기본값 부재**: 오직 **양성 조건 전부 충족**(profile 각 governed
   dimension value ≤ envelope max ∧ profile scope ⊆ envelope permitted scope ∧ profile이 참조하는 dimension이
   전부 envelope에 선언됨) 시에만 `valid=True`. **하나라도 초과/미선언 ⇒ reason_set에 `EXCEEDS_ENVELOPE`
   추가·invalid.** "assume-within" 생성 경로 부재(#6 fail-open REJECT 교훈).
2. **envelope 미선언 dimension = zero authority(vacuous-dominant 금지, ∅-공허 봉합 — #10 code-review 교훈)**:
   profile이 envelope에 **없는** dimension을 참조하면 그 dimension의 envelope max는 없음(None) ⇒ **초과로
   취급·거부**(§9 line 264 "prohibited fallbacks, implicit defaults, wildcard scope"). 빈 envelope-dimension
   set은 "모든 것 허용"이 아니라 "**아무 것도 허용 안 함**"으로 처리(brokercap 빈 required-set = all-17-highest
   동형).
3. **non-silent expansion(SPG-INV-007 line 177)**: `envelope_expansion_enlarges_nothing(old_env, new_env,
   active_profile) -> bool`은 envelope generation advance가 active profile 값을 **자동 확대하지 않음**을
   확인 — "An envelope expansion does not enlarge existing profiles automatically"(§9 line 269). 새 envelope가
   더 넓어도 active profile 값은 불변이어야 True; profile이 새 envelope의 넓은 상한을 자동 흡수하면 False.

**canary(both-ways)**: (a) profile.dimension_value > envelope.max ⇒ `valid=False`·reason `EXCEEDS_ENVELOPE`
(가드 발화); envelope 미선언 dimension 참조 ⇒ `valid=False`(vacuous-dominant 아님); (b) profile 각 값 ≤
envelope max ∧ scope ⊆ ∧ 전 dimension 선언 ⇒ `valid=True`(양성 side — 가드가 정당한 통과를 막지 않음).
envelope-expansion canary: old<new envelope + active profile 값 불변 ⇒ `enlarges_nothing=True`; profile 값이
새 상한으로 자동 상승 ⇒ False.

### 4.2 semantic validation 중앙 불변식 + rich verdict (ADR §11 line 300–317; SPG-INV-004; SPG-EV-002/003)

- **미증명/모순/미상 ⇒ invalid, permissive 기본 부재**: `semantic_validation(bundle) -> SemanticValidationResult`
  는 §11의 12 step 중 L1-decidable step(3 units/numeric/boundary·4 scope·5 cross-field·6 envelope 비교·11
  direction·12 unknown/duplicate field)을 순수 검사하고 sibling-의존 step(7 aggregate=ARE/rcl·8 software=
  ADR-002-029·9 bundle-member digest·10 time)을 **주입 결과로 fold**한다. **하나라도 미충족 ⇒ `valid=False`**
  이며 rejected dimension·reason이 결과에 담긴다.
- **rich verdict(#11 MINOR thin-signature 교훈)**: ADR §11 line 315 verbatim "Validation must produce a
  deterministic result **and reason set** for one exact bundle digest." ⇒ **thin bool이 아니라**
  `SemanticValidationResult(valid: bool, rejected_dimensions: frozenset[str], reason_set:
  frozenset[ValidationReason], bundle_digest: str|None)`. 설계 단계에서 명시적으로 rich verdict를 택한 근거:
  (i) ADR이 reason set을 요구, (ii) SPG-EV-002/003이 per-defect fail-closed를 검증하려면 어떤 dimension이
  왜 거부됐는지 재구성 가능해야 함(SPG-EV-012 replay), (iii) thin bool은 §20 failure-mode 표의 per-failure
  response를 표현 불가.
- **§11 step 3 numeric 노다지**: overflow/underflow/NaN/infinity/precision/rounding은 `CanonicalDecimal`
  (`is_finite` 검사 + scale-normalize) 순수 술어 — 가장 순수한 core L1. **canary**: `1.0`과 `1.00`은 같은
  digest(정상); NaN/infinity limit ⇒ reason `OVERFLOW_UNDERFLOW_NAN_INFINITY`·invalid(가드 발화).
- **canary(both-ways)**: (a) unit 누락/모순 cross-field/unknown field ⇒ `valid=False`·reason 집합 비어있지
  않음(가드 발화); (b) 전 step 충족 ⇒ `valid=True`·`reason_set=∅`(양성 side). **∅ 봉합**: 빈/absent bundle
  ⇒ `valid=False`(빈 입력이 vacuous valid가 되지 않음, §4.1).

### 4.3 atomic mixed-generation / stale-base 불변식 (ADR §13/§15; SPG-INV-003/005; SPG-EV-004/005)

- **mixed-generation ⇒ union 금지(SPG-INV-005 line 169)**: `activation_atomic`은 old·new field 조합이 어느
  완전 버전보다도 넓은 profile을 만들 수 없게 한다 — "Partial or mixed activation cannot create the union of
  permissions from old and new generations". 4-bool(version_fully_active ∧ ¬mixed_versions_present ∧
  units_compatible ∧ envelope_bounded) **전부 양성**일 때만 `COMMITTABLE`.
- **stale-base ⇒ 거부(SPG-INV-003 line 161)**: `activation_serializable`은 `candidate.predecessor_generation
  == current_active_generation`일 때만 True. same predecessor + overlapping scope 두 활성화 ⇒ 하나만 winner
  (§15 line 417); last-write-wins·partial field patch 부재(§15 line 419–420). `latest`/local/cache ≠ authority.
- **canary(both-ways)**: (a) mixed generation flag True ⇒ `DENIED`(가드 발화); stale predecessor(≠ current)
  ⇒ `activation_serializable=False`; (b) single-generation·predecessor==current ⇒ `COMMITTABLE`(양성 side).

### 4.4 좌표 비붕괴 (envelope/profile version ≠ broker profile version ≠ capacity generation ≠ time snapshot)

- **별개 축**: spg `EnvelopeVersion`/`ProfileVersion`(safety-config governance 축) / brokercap `ProfileVersion`
  (broker capability 축, `records.py:71`) / rcl generation(capacity 축) / time `safety_profile_version`
  (time-snapshot 축, `snapshot.py:141`). 토큰이 겹칠 수 있으나(예: "profile version") **별개 타입**이다.
- **비붕괴 성립 방식**: (i) **타입 구분**(별개 FrozenModel/StrEnum) + (ii) **미import**(spg는 brokercap/rcl/
  time을 import하지 않아 swap 원천 차단). canary: `spg.ProfileVersion is not brokercap.ProfileVersion`(둘 다
  import하는 test-only 모듈에서 타입 identity 회귀). **좌표 비붕괴 = §3.5 소유권 분할의 근거**(#10 §4.4·#11
  §4.4 상속).
- **spg version scalar ≠ 각 패키지 자체 artifact version (v1.1 MAJOR-2 자기범례·주의)**: 형제 패키지가 담는
  `*_version`은 두 종류다 — (i) **spg-축 좌표**(liveauth `hard_safety_envelope_version`/
  `runtime_safety_profile_version` `state.py:87–88`·authority `records.py:113–114`·rcl `records.py:101–102`·
  time `safety_profile_version` `snapshot.py:141` — spg가 상류 origin) vs (ii) **그 패키지 자신의 아티팩트
  identity**(protective `profile_version` `records.py:277`는 `ProtectiveCapacityProfile` 자체 version이지 spg
  좌표가 **아니며**, brokercap `ProfileVersion` `records.py:71`은 broker-capability 축). 이 둘을 혼동하면 좌표
  붕괴다 — 본 v1.0 §3.4 표가 protective를 spg-축 scalar 소비자로 오귀속한 것이 정확히 그 사례였고 v1.1이
  정정한다(protective 실제 seam은 `HardEnvelopeRef` per-axis 상한 주입 `records.py:94`·`envelope_subordinate`
  `predicates.py:740` — 상단 선행문서 절·§3.5에 이미 올바르게 서술). spg는 protective/brokercap을 import하지
  않으므로 그들의 자체 version을 spg 좌표로 흡수할 경로가 구조적으로 없다.

### 4.5 representation ≠ enforcement (ADR §1 line 40; §13/§16; SPG-INV-014 line 205)

`HardSafetyEnvelope`·`RuntimeSafetyProfile`·`ActivationRecord`·admissibility/validation/direction bool은
**비전송·비-enforcing representation**이다 — "profile ACTIVE" 기록이 order를 전송하거나 capacity를 release
하거나 Live Authorization을 발급하지 않는다. SPG-INV-014 line 205 verbatim: "Approval records, signatures,
logs, diffs, dashboards, review tickets, and replay evidence do not create activation, capacity, Live
Authorization, or transmission authority." §12.3 line 350–364: activation ≠ arming(Critical Input validity·
venue admissibility·conformance·aggregate risk·currentness·trial eligibility는 전부 독립 governed). ⇒ spg에
**egress transmit·capacity mutate·authorization issue·activation commit 메서드가 부재**(구성적 부재). spg는
결정 bool/scalar를 **반환**할 뿐 소유 authority가 enforce한다 — evidence(하류)·rcl·liveauth·authority
미import(§3.5)의 근거이기도 하다.

### 4.6 append-only + same-id/diff-bytes 충돌 (§5.4; §7.2; §12; §2.3)

모델에 update/delete 연산 부재(§2.0). Envelope/Profile revalidation·개정은 새 generation(새 id)의 append로
표현(supersession link). same identity + diff canonical digest ⇒ `classify_record_pair` = `CRITICAL_CONFLICT`
(위조·재발행 위조만 — contain 양쪽 보존, no last-write-wins). `RESTRICTED`/`SUPERSEDED` status(§12.1)는 state로
표현. property: id⊥digest이므로 CRITICAL_CONFLICT reachable(가드 발화); id=f(digest)면 unreachable임을 회귀로
고정(§3.1).

---

## 5. core 술어 — envelope dominance · semantic validation · atomic activation · stale-base · restrictive · expiry · replay (SPG-EV-001..006/008/012 substrate)

**핵심 난제**: 이중 아티팩트의 dominance·validation·activation을 **순수 함수**로 저작하되, (i) numeric limit·
approval·time-validity·aggregate-effect를 **주입 판정/파라미터**로 두어 하드코딩 수치를 배제하고(§8), (ii)
**fail-closed(§4)를 구조로** 지키며(permissive 기본·vacuous-dominant/complete 부재), (iii) mixed-generation·
stale-base·미증명 방향·만료를 **most-restrictive**로 처리한다.

### 5.1 envelope dominance (§9; SPG-EV-001 substrate, core L1 슬라이스)

`profile_within_envelope(envelope: HardSafetyEnvelope|None, profile: RuntimeSafetyProfile|None) ->
SemanticValidationResult` (또는 dominance 전용 `bool`+reason):

| 입력 조건 | 산출 | 근거 |
|---|---|---|
| envelope·profile 존재 ∧ profile 각 governed dimension value ≤ envelope max ∧ profile scope ⊆ envelope permitted scope ∧ profile 참조 dimension 전부 envelope 선언 ∧ profile의 envelope id+generation이 이 envelope와 일치 | `valid=True` | §1 line 21–26; SPG-INV-001; §10 line 281 |
| profile dimension value > envelope max, 또는 envelope 미선언 dimension 참조, 또는 scope ⊄ | `valid=False`·`EXCEEDS_ENVELOPE` | SPG-INV-001 line 153; §9 line 264 |
| envelope 또는 profile None, 또는 profile의 envelope id/generation 불일치 | `valid=False`(fail-closed) | §10 line 281 one exact envelope |

- **produces `envelope_not_expanded`**: `envelope_expansion_enlarges_nothing(old_env, new_env, active_profile)`
  — envelope generation advance 시 active profile 값 불변 ⇒ True(§9 line 269; SPG-INV-007). liveauth
  `hard_safety_envelope_not_expanded`(`state.py:164`) 상류.
- **produces `envelope_incompatible`**: `envelope_incompatible(active_env, presented_env_generation) -> bool`
  — presented generation이 active와 불일치/미상 ⇒ True(authority `predicates.py:640` 상류, `is not False⇒
  invalidated`). polarity: spg True ⇒ authority invalidated측(가드 발화).
- **canary(SPG-EV-001, both-ways)**: (a) envelope tightening/replacement 후 profile이 예전 넓은 값 유지 ⇒
  `profile_within_envelope`=invalid ∧ `envelope_not_expanded`가 prior arming 보존 거부(§24 SPG-AC-001 "cannot
  silently expand … or preserve prior live arming"); (b) profile ≤ envelope ∧ 정합 generation ⇒ valid.

### 5.2 semantic validation — rich verdict (§11; SPG-EV-002/003 substrate, core L1 슬라이스 — 순수 술어 노다지)

`semantic_validation(bundle: SafetyConfigurationBundle|None, inputs: SemanticValidationInputs) ->
SemanticValidationResult`:

- **순수 L1 step(spg 소유)**: step 3(units/multiplier/currency/sign/precision/rounding/overflow/underflow/
  NaN/infinity/boundary — `CanonicalDecimal` `is_finite`+scale-normalize)·step 4(scope 집합 membership)·
  step 5(cross-field constraint)·step 6(profile ≤ envelope — §5.1)·step 11(`change_direction`)·step 12
  (unknown/duplicate/deprecated/extension field — `extra="forbid"` + 명시 검사).
- **주입 fold step(형제 소유)**: step 1 signature/revocation(injected flag)·step 2 canonical reproducibility
  (canonical REUSE digest 재계산)·step 7 aggregate effect(ARE/ADR-002-021 주입)·step 8 software/deployment
  (ADR-002-029 주입)·step 9 bundle-member digest(주입 ref)·step 10 time validity(주입 flag).
- **rich verdict(§4.2)**: `SemanticValidationResult(valid, rejected_dimensions, reason_set, bundle_digest)`.
  §11 line 315 "deterministic result and reason set"·line 317 "If one dimension cannot be ordered
  conservatively, the change is authority increasing and the scope remains non-live". ⇒ `UNORDERABLE_DIRECTION`
  reason ⇒ `change_direction=AUTHORITY_INCREASING`·non-live(§2.2(3) v1.1 MINOR-1: enum 값 아닌 reason).
- **canary(SPG-EV-002/003, both-ways)**: (a) unit 누락(§20 line 505)·cross-field 모순·unknown field(§20
  line 504)·schema downgrade(SPG-AC-003) ⇒ `valid=False`·해당 reason(가드 발화; §24 SPG-AC-002/003 "fail
  closed before activation"·"cannot create permission"); (b) 전 step 충족 ⇒ valid·`reason_set=∅`. **∅ 봉합**:
  빈/absent bundle ⇒ `valid=False`(§4.2).

### 5.3 atomic mixed-generation activation (§13; SPG-EV-004 substrate, core L1 슬라이스)

`activation_atomic(inputs: ActivationInputs) -> ActivationVerdict`:

> **seam 출력 vs 내부 verdict (v1.1 MINOR-2)**: **spg의 seam 출력은 4 개별 bool**(`version_fully_active`/
> `mixed_versions_present`/`units_compatible`/`envelope_bounded`, `semantic_validation`·`profile_within_envelope`
> 에서 산출) — 기존 소비자 liveauth `atomic_activation_ok`(`predicates.py:454`)가 이 4 bool을 fold한다(소비
> signature 불변). **`activation_atomic → ActivationVerdict`는 spg 자신의 SPG-EV-004 property 검증용 내부
> 술어**(같은 4-조건을 COMMITTABLE/DENIED/DEFERRED로 fold) — liveauth fold와 **중복이 아니라 이중-레이어**
> (spg는 자체 fold를 property로 검증, liveauth는 re-arm gate용 fold). 소유권 경계는 §3.5 표에 정합.

- `COMMITTABLE` **only** when: `version_fully_active is True` ∧ `mixed_versions_present is False` ∧
  `units_compatible is True` ∧ `envelope_bounded is True`(§13; liveauth `atomic_activation_ok`
  `predicates.py:479–484` 4-조건 동형·spg가 상류 생산). 이 4-bool을 spg가 semantic_validation·
  profile_within_envelope에서 산출해 liveauth에 공급.
- `DENIED`: mixed generation / partial distribution / missing value / incompatible unit / unverifiable
  activation(§13 line 385 "If any consumer is absent, incompatible, stale, mixed, or unable to verify …
  remain denied. The system SHALL NOT combine old and new field values").
- `DEFERRED`: staging/attestation collection 미완(런타임 quorum commit 대기; §13 line 379/383 — spg는
  commit하지 않음, not-live).
- **canary(SPG-EV-004, both-ways)**: (a) mixed_versions_present=True ⇒ `DENIED`(가드 발화; §24 SPG-AC-004
  "cannot create a permissive union"); (b) 4-조건 전부 양성 ⇒ `COMMITTABLE`. **no-capacity-mutation**(§13
  line 387): activation record는 capacity를 mutate하지 않음(spg 메서드 부재, §4.5).

### 5.4 concurrent / stale-base activation (§15; SPG-EV-005 substrate, core L1 슬라이스; ordering REUSE)

`activation_serializable(candidate: ActivationRecord, current_active_generation: int|None) -> bool`:

- `True` **only** when `candidate.predecessor_generation is not None` ∧ `current_active_generation is not None`
  ∧ `candidate.predecessor_generation == current_active_generation`(§15 line 415–422 "reject two successful
  activations for the same predecessor …; stale-base approval or activation; last-write-wins merge").
- append-only 순서는 `tos.ordering.compare_order`(quorum_commit_index; §3.2). `latest`/local/cache ⇒ base
  좌표 None ⇒ fail-closed(SPG-INV-003 line 161).
- **canary(SPG-EV-005, both-ways)**: (a) predecessor ≠ current(stale-base) 또는 None ⇒ `False`(가드 발화;
  §24 SPG-AC-005 "serialize to one committed generation without last-write-wins"); (b) predecessor==current ⇒
  `True`(양성 side). disjoint scope 독립 활성화는 Failure-Domain 증명 주입(§15 line 424).

### 5.5 restrictive precedence + change direction (§14; SPG-EV-006 substrate, core L1 슬라이스)

`change_direction(old_bundle, new_bundle, inputs) -> ChangeDirection` ∧ `restrictive_override_admissible(...)
-> bool`:

- `change_direction`: 모든 credible dimension에서 deny/narrow만 ⇒ `RESTRICTIVE`; 한 dimension이라도 확대/
  previously-denied permit ⇒ `PERMISSIVE`/`AUTHORITY_INCREASING`; 한 dimension이라도 보수적 순서 불가·미증명 ⇒
  **`AUTHORITY_INCREASING`으로 접는다**(v1.1 MINOR-1: `UNORDERABLE`은 enum 값이 아니며 순서불가는
  `ValidationReason.UNORDERABLE_DIRECTION`으로 reason_set에만 실림 — §2.2(3); §5.9 line 145; §11 line 317).
- `restrictive_override_admissible`: `change_direction is RESTRICTIVE` ∧ auto-revert 부재 ∧ capacity/orders/
  exposure/UNKNOWN/protective 보존 flag 전부 True일 때만(§14 line 395–403). **nominal reduction이 unit/
  aggregation/scope-exclusion/fallback/protective-ownership/broker-capability/state-confidence/calculation
  semantics를 바꾸면 restrictive로 추정 금지**(§14 line 405 verbatim) ⇒ 그 경우 `change_direction`이
  `PERMISSIVE`/`AUTHORITY_INCREASING`을 반환하도록 입력 검사(순서불가·미증명은 `AUTHORITY_INCREASING`으로 접힘).
- **canary(SPG-EV-006, both-ways)**: (a) 한 dimension 확대 또는 unit 변경 동반 "reduction" ⇒
  `AUTHORITY_INCREASING`·override 거부(가드 발화; §24 SPG-AC-006 "within approved bounds while preserving …");
  (b) 순수 tightening ∧ 보존 flag 전부 True ⇒ admissible. economic continuity 수치(capacity 소비)는 rcl 주입
  (§19; spg는 방향 verdict만).

### 5.6 expiry non-revival (§18; SPG-EV-008 substrate, core L1 슬라이스)

`expiry_suspends_new_risk(not_expired: bool|None, time_verifiable: bool|None) -> bool`(만료/time-unverifiable
⇒ future new-risk 중단) ∧ `expiry_revives_nothing(...) -> bool`:

- `expiry_revives_nothing`은 **무조건 True**(liveauth `authorization_revived_by_nothing` `predicates.py:777`·
  rcl `recovery_generation_revives_nothing` 동형): 만료/invalidation이 orders 취소·capacity release·economic
  effect 만료·UNKNOWN 해소·predecessor profile 복원·auto grace 확대·time-recovery re-arm을 **하지 않음**
  (§18 line 472–482 verbatim 7-항목; SPG-INV-011/013). 모델에 만료→복원 매핑 연산 부재(구성적 부재).
- time validity는 **주입 flag**(§3.5; spg는 time 산술 불요) — `not_expired`/`time_verifiable` None ⇒ 보수
  (new-risk 중단).
- **canary(SPG-EV-008, both-ways)**: (a) expired profile 재활성 시도 ⇒ `expiry_suspends_new_risk`=True(new-risk
  거부)·`expiry_revives_nothing`=True(복원 없음)(가드 발화; §24 SPG-AC-008 "cannot restore authority or erase
  economic effect"); (b) not_expired ∧ time_verifiable ⇒ new-risk 중단 아님(양성 side, 단 활성화는 별도).

### 5.7 decision-replay substrate (§21; SPG-EV-012 substrate, core L1 슬라이스)

frozen digest-bound append-only `HardSafetyEnvelope`/`RuntimeSafetyProfile`/`SafetyConfigurationBundle`/
`ActivationRecord`/`ConsumerCompatibilityManifest` 레코드가 각 artifact byte·canonical semantic digest·approval
id·validation result+reason·activation record(predecessor·restrictive ordering)·consumer 결정을 durable
evidence에서 **재구성 가능**케 한다(§21 line 522–533 evidence 목록). **replay ENGINE 자체는 ADR-002-016**
(evidence `replay.py`, not-Phase-1) — Phase 1은 재구성 substrate 모델만(brokercap BC-EV-022 동형). evidence는
spg 레코드를 `safety_configuration_activation_record_digest`(`evidence/replay.py:113`) 등 scalar로 참조. **SPG-INV-014
(Evidence Is Not Authority)**: replay evidence가 activation/capacity/authority를 만들지 않음(§4.5).
- **canary(SPG-EV-012)**: replay가 envelope·profile·bundle·activation·restriction·consumer 결정·denial을
  재구성하되 evidence를 authority로 취급하지 않음(§24 SPG-AC-012 "without treating evidence as authority").

---

## 6. predicate-only 술어 — rollback · break-glass · consumer-compat · missing-config (SPG-EV-007/009/010/011 substrate, 최소 ≥ L2·닫지 않음)

> **분류 판단**: 이 4 술어는 register 최소 레벨이 EV-L2 이상(007/009 `+Security`, 010/011 `EV-L2/3`)이라 **L1
> 슬라이스 없음** — Phase 1은 L1-decidable substrate만 저작하고 **EV를 닫지 않는다**. 각 술어의 정의적 acceptance
> 증거(+Security enforcement·rollback DR·drift 런타임·economic containment)는 not-Phase-1(§1). #10 BC-EV-015/020
> "좌표 선언·+Security 이연"·#11 predicate-only 동형.

### 6.1 rollback = new proposal, non-revival (§17; SPG-EV-007 substrate, predicate-only)

`rollback_requires_new_generation(reused_artifact, current_schema_valid: bool|None, current_approval: bool|None)
-> bool`: 오래된 artifact 재사용은 **새 generation ∧ current 스키마/software/broker/time 검증 ∧ current approval
∧ break-before-make ∧ fresh re-arm**을 요구할 때만 True(§17 line 452–458). "Rollback is a new proposal, never
a state reversal"(line 452). restore-generation fence enforcement는 **rcl `restore_generation`**(`records.py:465`,
ADR-002-012)·+Security historical-signature replay는 not-Phase-1(§1). `rollback_revives_nothing`(무조건 True,
§5.6 동형).
- **canary(both-ways)**: (a) 오래된 broader profile을 그대로 복원 시도(새 generation·current 검증 없이) ⇒
  `False`(가드 발화; §24 SPG-AC-007 "cannot revive an old generation or approval"); (b) 새 generation +
  current 검증 + approval + re-arm ⇒ True(정당 경로).

### 6.2 break-glass directional confinement (§8; SPG-EV-009 substrate, predicate-only)

`break_glass_confined(action: str) -> bool`: break-glass authority는 **HALT 또는 proven Restrictive Override
만** 가능·envelope 확대/profile 확대/semantic validation waive/generation activate/re-arm **금지**(§8 line 251
verbatim). SoD 권한 **테이블 좌표**(§8 line 234–247 action↔required authority↔prohibited combination)를 담되,
effective-principal independence enforcement("Splitting labels across roles while one principal controls all
underlying credentials does not establish separation", line 249)는 **ADR-002-015 HAG-EV +Security** 이연(§1).
- **canary(both-ways)**: (a) break-glass가 envelope 확대/re-arm 시도 ⇒ `False`(거부; §24 SPG-AC-009 "cannot
  author, approve, activate, and arm an authority increase"); (b) break-glass HALT/restrictive ⇒ True(허용측).

### 6.3 consumer compatibility manifest match (§16; SPG-EV-010 substrate, predicate-only)

`compatibility_manifest_matches(manifest: ConsumerCompatibilityManifest|None, bundle_requirements) -> bool`:
consumer가 선언한 exact schema·field·unit·calculation·constraint·failure semantics가 bundle이 요구하는 것과
일치할 때만 True(§5.6·§16 line 434–436). 미상/불일치 ⇒ 거부(§16 line 442 "Cache miss … or inability to
establish currentness is denial"). software drift는 **ADR-002-029**·broker drift는 **brokercap #10**(주입)·
final-egress binding은 **ADR-002-013** 런타임 이연(§1).
- **canary(both-ways)**: (a) consumer가 새 field/unit 결여(incompatible) ⇒ `False`(§24 SPG-AC-010 "drift
  suspends affected authority and fails closed at egress"); (b) exact match ⇒ True. **∅ 봉합**: 빈 manifest ⇒
  `False`(vacuous-match 금지).

### 6.4 missing / contradictory configuration containment (§20; SPG-EV-011 substrate, predicate-only)

`bundle_complete(bundle: SafetyConfigurationBundle|None, required_members: frozenset[BundleMemberKind]) -> bool`
∧ `missing_config_denies(...) -> bool`: bundle이 §2.2(4) **포함 29 member**를 전부 present·resolved·immutable로(이연 7항은 Phase-0 주입 ref)
가질 때만 complete(SPG-INV-002 line 157 "No new-risk authority is created from a partial, unresolved, mutable,
or open-ended Safety Configuration Bundle"). **빈 required_members ⇒ 전 member 필요로 취급**(vacuous-complete
금지·∅ 봉합, §4.1; brokercap 빈 required-set 동형). "unresolved economic state remains conservatively
capacity-covered"(§20 line 513/§24 SPG-AC-011)는 **rcl** 런타임 이연(spg는 new-risk block bool만).
- **canary(both-ways)**: (a) member 하나 missing/contradictory/mutable ⇒ `bundle_complete=False`·new-risk
  거부(가드 발화; §24 SPG-AC-011 "blocks new risk"); (b) 전 member present·resolved·immutable ⇒ True(양성
  side, 단 활성화는 별도).

---

## 7. property-test 하네스 타깃

§1 분류에 정렬한다. **닫는 SPG-EV = 0건** — 어떤 test-target도 SPG-EV closure·acceptance를 주장하지 않는다
(규율 태그 부착). 각 술어에 **both-ways canary**(§4·§5·§6)와 **fixture clean-vs-illegal 정합**(#8 교훈)을 건다.

- **core(L1 슬라이스, SPG-EV-001..006/008/012 substrate)**: `profile_within_envelope`·`envelope_expansion_
  enlarges_nothing`·`envelope_incompatible`(§5.1); `semantic_validation`+reason-set·`CanonicalDecimal` boundary
  (§5.2); `activation_atomic`(§5.3); `activation_serializable`+ordering(§5.4); `change_direction`·
  `restrictive_override_admissible`(§5.5); `expiry_suspends_new_risk`·`expiry_revives_nothing`(§5.6);
  frozen digest-bound 레코드 재구성·`classify_record_pair` CRITICAL_CONFLICT(§5.7); `_ENVELOPE_TRANSITIONS`/
  `_PROFILE_TRANSITIONS` non-revival(§2.2). hypothesis property: envelope/profile/limit/generation을 무작위
  생성해 dominance·validation·atomicity·serializability·direction·non-revival 불변식을 검사.
- **predicate-only(SPG-EV-007/009/010/011 substrate, EV 미주장)**: `rollback_requires_new_generation`(§6.1);
  `break_glass_confined`(§6.2); `compatibility_manifest_matches`(§6.3); `bundle_complete`·`missing_config_denies`
  (§6.4).
- **seam cross-check(test-only, MANDATED §3.4)**: `test_seam_liveauth`(spg `hard_and_runtime_versions_match`/
  `envelope_not_expanded`/`envelope_profile_covers_enlarged`/`activation_atomic` 4-bool ↔ liveauth 소비
  signature polarity)·`test_seam_authority`(spg `envelope_incompatible` ↔ authority `predicates.py:701`)·
  `test_seam_rcl`(spg `active_generation`/`effective_limit` ↔ rcl 좌표). 테스트 import는 package closure에
  불계상(§7.1).
- **∅-공허 회귀(#10 교훈)**: 빈 governed-dimension set ⇒ `profile_within_envelope` vacuous-dominant 아님; 빈
  bundle-member set ⇒ `bundle_complete` 전-member-필요; 빈 required semantic step ⇒ vacuous-valid 아님.

### 7.1 import-closure 검증 테스트 (설계 #4 §7.1·#5..#11 §7.1 상속)

`import tos.spg` 후 `sys.modules` closure에 **금지 집합 부재 assert**: `shared.config`·`os.environ` 흔적·
`numpy`/`pandas`/`yaml`·**`tos.liveauth`·`tos.authority`·`tos.rcl`·`tos.time`·`tos.capsule`·`tos.evidence`·
`tos.protective`·`tos.brokercap`·`tos.orthostate`·`tos.recon`·`tos.dsl`** 부재; **`tos.canonical`·`tos.ordering`
존재 허용**. required check(`tos-firewall`, `tools/tos_firewall_check.py` layer-① AST + `.importlinter`
layer-② 전이)와 함께 green이어야 §0.3 선언이 능동 성립.

### 7.2 run manifest 정렬 (설계 #1 §5.1 7항목)

(1) 목적: spg Phase-1(EV-L1) 순수 모델+property test. (2) 명령: `pytest tos/tests/spg/ -v`. (3) 격리:
hermetic(`.env` 비주입·clock 미접근·네트워크 없음). (4) 결정론: hypothesis 시드 고정·`CanonicalDecimal`
scale-normalize. (5) 산출물: property test 결과(EV closure 아님 — 규율 태그). (6) 게이트: `tos-firewall`
required green. (7) 비-acceptance: 어떤 SPG-EV도 닫지 않음(§0.2·VER-002-001 §5).

---

## 8. bounds 주입 + Phase-0 + self-referential Verification-Profile 분석

**§8.0 spg decision 구조에 numeric bound 부재**: 전부 enum(`EnvelopeState`/`ProfileState`/`ChangeDirection`/
`ValidationReason`/`ActivationVerdict`/`BundleMemberKind`)·boolean·집합 논리·주입 `CanonicalDecimal`(limit·
boundary). ADR §4 non-scope line 98 "numeric safety limits"·§26 item 12는 수치를 **명시 배제**한다 — 전부
**Safety Profile/Verification Profile INSTANCE 측정값**이며 주입 opaque param으로만 담는다. 값 부재 ⇒
fail-closed(§4). 값 승인은 Bounds-Approver 게이트(§9.2).

**§8.1 Verification-Profile 키 실측(MAJOR-2 규율 — `measurement_source` 전수 확인)**: ADR-002-014가 요하는 수치
분류 및 프로파일 키 상태:
- **restriction-propagation(§14 line 399 "reach final egress within `B_risk_increase_revoke` plus
  `B_revocation_to_egress`")**: `B_risk_increase_revoke`(profile line 128, value 500 PROPOSED,
  `measurement_source: egress_decision_log`)·`B_revocation_to_egress`(line 135, null MEASURE,
  `authority_and_egress_generation_log`) — **이미 존재**(ADR-002-007/003과 공유; §14가 참조). 신규 키 불필요.
- **approval/attestation age(§8/§18)**: `MAX_human_approval_age_ms`(line 703)·`MAX_human_session_age_ms`(704)·
  `MAX_human_delegation_age_ms`(705)·`MAX_proposal_approval_request_age_ms`(721)·`MAX_independent_approval_
  decision_age_ms`(722)·`MAX_runtime_artifact_attestation_age_ms`(745) — **이미 존재**하나 **ADR-002-015/023/029
  소유**(spg 미소유; §3.5). spg는 이 age flag를 **주입 `bool|None`**로만 소비.
- **evidence persistence(§21)**: `B_evidence_persist`(674, null MEASURE) — 이미 존재(ADR-002-016 소유).
- **envelope/profile/bundle/activation-record VALIDITY interval·REVIEW deadline·STAGING age·compatibility-
  attestation age(§7 line 222 "validity start, expiry, review deadline"·§13 staging·§21 metric "staging age")**:
  **실측 결과 전용 키 부재**(profile `limits` 블록 line 696–751 전수 확인 — `MAX_safety_profile_validity_ms`·
  `MAX_envelope_review_interval_ms`·`MAX_activation_staging_age_ms`·`MAX_compatibility_attestation_age_ms`
  전부 **부재**). ⇒ **candidate Phase-0 신규 키 4종**(§9.2). #10이 "0건 누락"이었던 것과 달리 본 ADR은 validity/
  review/staging/attestation 수치를 §7/§13/§21에서 명시 요구하나 프로파일에 미키. 단 ADR §4/§26이 numeric을
  Phase-0로 명시 이연하므로 이는 결함이 아니라 **Phase-0 Bounds-Approver 작업 항목**이다(over-claim 아님).

**§8.2 self-referential Verification-Profile 분석(신중)**: 이 ADR은 **Safety Profile 거버넌스 그 자체**를
다루므로 `VERIFICATION-PROFILE-002.yaml`과의 관계가 self-referential하다. 실측 분석:
- **VP scope 블록(line 27–114)이 Safety Configuration Bundle(§5.3)의 manifestation이다**: VP `scope`는
  `hard_safety_envelope_id/version/generation/digest`(27–30)·`runtime_safety_profile_id/version/generation/
  digest`(31–34)·`safety_configuration_activation_record_id/digest`(35–36) 및 §5.3 closed member 전부(human
  authority·evidence integrity·recovery barrier·critical input·… post-trade)의 id/generation/digest 좌표를
  담는다(전부 TBD/null). 즉 **VP의 scope 블록 = spg가 모델링하는 Bundle의 test-harness 인스턴스 pin**이다.
- **self-reference의 해소(paradox 아님·layering)**: (i) §5.3 Bundle **member로 "Verification Profile"이 포함**
  된다(bundle이 VP를 담음). (ii) **동시에** VP scope가 Envelope/Profile/ActivationRecord를 pin한다(VP가 bundle
  좌표를 참조). 이는 순환이 아니라 **두 층**이다: VP scope 블록은 "어떤 envelope/profile/activation-record에
  대해 EV 테스트를 실행하는가"의 **test-binding**이고, `SafetyConfigurationBundle`은 **runtime authority artifact
  set**이다. spg는 runtime 아티팩트(§2)를 모델링하고, VP scope 블록은 특정 테스트 실행이 어느 generation을
  검증하는지 pin한다. Phase 1 spg는 VP를 **import·파싱하지 않는다**(YAML 파싱은 하네스 #3; §0.3) — VP 좌표는
  주입 scalar(bundle member ref)로만 담는다.
- **규율**: spg는 VP를 authority로 취급하지 않는다(SPG-INV-014). VP status는 `PROPOSED`(line 2·17–18
  "NOT APPROVED … MUST NOT be relied upon")이며 approved bound 부재 ⇒ 전 수치 fail-closed(§4; VER-002-001 §6
  "an unapproved or placeholder bound is not an approved bound"). ⇒ Phase 1은 어떤 VP 수치도 신뢰하지 않는다.

---

## 9. 후속 작업 · Phase-0 인간 게이트 이관 항목

### 9.1 후속 구현 작업 (본 계약 위에서)

1. `tos/src/tos/spg/` 5-module 저작(`_base.py` shim·`vocabulary.py`·`records.py`·`state.py`·`predicates.py`)
   + `tos/tests/spg/` property test(§7) + seam cross-check(§3.4) + import-closure(§7.1).
2. 11 결정 술어 구현(§5 core 8 + §6 predicate-only 4 중 §5.1이 2개 producer 포함) + `SemanticValidationResult`
   rich verdict(§5.2) + `_ENVELOPE_TRANSITIONS`/`_PROFILE_TRANSITIONS` frozenset(§2.2).
3. 미래 caller 런타임(Safety Profile Validator/Configuration Distribution/Live-Authorization)이 spg produced-
   bool/scalar를 소비자 주입 슬롯으로 배선(§3.4; Phase 1 밖·EV-L3).

### 9.2 Phase-0 인간 게이트로 넘기는 항목 (본 계약이 결정하지 않음)

ADR §26 Open Implementation Questions(21항)·§27 Approval Gate(21조건)에서 Phase-1 밖으로 이연:
1. **canonical artifact format·semantic-normalization algorithm 선택**(§26 item 1) — 프로덕션 canonical
   semantic digest form(§3.1 EVL1ProvisionalCanonicalizer는 잠정).
2. **signing·approval-workflow·registry·revocation 제품 선택**(§26 item 2·§27 item 1–2).
3. **ADR-002-015 effective-principal·approval quorum·break-glass·delegation policy**(§26 item 3·§27 item 3·
   HAG-EV; §6.2 enforcement 상류).
4. **deterministic restrictive-comparison system**(§26 item 4 — scalar/set/vector/conditional/fallback/time
   dimension; §5.5 `change_direction`의 런타임 완전판).
5. **Consumer Compatibility Manifest 생성·인증·mixed-version 검사**(§26 item 5·§16).
6. **ADR-002-012 command schema·namespace(Profile Generation commit)**(§26 item 6·§13/§15 quorum 런타임).
7. **per-Safety-Cell/scope 필수 attestation consumer 집합**(§26 item 7·§13).
8. **shared aggregate constraint 직렬화**(§26 item 8·§15 line 424).
9. **full re-arm vs scoped suspension/revalidation 매핑**(§26 item 9·§9 line 269).
10. **emergency envelope tightening·Restrictive Override distribution(impaired plane)**(§26 item 10·§14 line 407).
11. **DR 후 highest-committed-history retention·proof**(§26 item 11·§17 line 460–462).
12. **numeric validity/approval/restriction-propagation/review bounds 승인**(§26 item 12) — 특히 **candidate
    신규 키 4종**(`MAX_safety_profile_validity_ms`·`MAX_envelope_review_interval_ms`·`MAX_activation_staging_age_ms`·
    `MAX_compatibility_attestation_age_ms`, §8.1 실측 부재)의 Bounds-Approver 승인.
13. **ADR-002-016 Evidence Integrity·Replay Capsule**(§26 item 13·§21; replay engine — SPG-EV-012 런타임).
14. **§27 item 11–19 bundle-binding**(Recovery Barrier·Critical Input·Venue·Aggregate Risk·Action Flow·
    Trading Approval·Currentness·Software Release·Post-Trade Finality의 identity/generation/digest/compat/
    restrictive-invalidation을 closed bundle로 binding — 각 ADR의 EV family).
15. **ARCHITECTURE-GATE-STATUS 명시 acceptance 결정**(§27 item 21) — 실행된 SPG-EV-001..012 + REARM/FD/RCLP/
    EGRESS/SA/HAG/ERI/SBR/CII/VTG/ARE/AFG/IAP/CUR/SCI/PTF cross-system evidence + 독립 리뷰.

---

## 10. 개정 로그 + 비준 체크리스트

### 10.1 개정 로그

- **v1.1 (2026-07-25) — 독립 비평 리뷰 REVISE 반영(forward-only), 운영자 비준 대기.** CRITICAL 0·MAJOR 3·
  MINOR 2·NIT 2. 코어 아키텍처(fail-closed 술어·이중 아티팩트·edge-0·EV 규율·∅-공허 봉합·VP self-reference
  분석)·인용 대부분은 정확 판정; seam 표 2셀·"verbatim" 주장 1건의 #10/#8형 결함을 최소 edit set으로 정정.
  - **MAJOR-1 (phantom 타입 + 소유권 cross-section 모순)**: `EffectiveLimitVector`는 tos/src 0건(phantom) —
    실제는 **함수** `def effective_limit(hard, runtime) -> CapacityVector`(rcl `vector.py:139`; v1.0 인용 143은
    docstring 중간). 전 출현 치환(§0.1/§0.2/§0.4b/§1/§3.4/§3.5). **소유권 정렬**: §0.2대로 spg는 effective-limit
    min을 저작하지 않고 **envelope 상한·profile 운영값 두 피연산자 scalar만 생산**하며 권위적 min은 rcl
    `effective_limit`이 수행 — v1.0 §0.4b/§3.5의 "spg가 `effective_limit=min` 생산" 주장 제거(rcl 산술 중복 배제).
  - **MAJOR-2 (protective seam 오귀속 = 좌표 붕괴 자기범례)**: protective/records.py에 `hard_safety_envelope_
    version`/`runtime_safety_profile_version` 0건 — `records.py:277`은 **protective 자신의 `profile_version`**
    (자체 아티팩트 identity)이지 spg 축이 아님. §3.4 scalar-소비자 목록에서 protective **제거**; §4.4에 "spg
    version scalar ≠ 각 패키지 자체 artifact version" 주의 추가(이 오귀속이 정확히 좌표 붕괴 사례). protective
    실제 seam(`HardEnvelopeRef` `records.py:94`·`envelope_subordinate` `predicates.py:740`)은 선행문서 절·§3.5에
    이미 정확.
  - **MAJOR-3 ("verbatim closed set" 거짓 — 선택지 (b) 채택)**: ADR §5.3 line 119에 "Release Generation" 실재
    하나 v1.0 `BundleMemberKind`가 비대칭 탈락(대칭 항목 Post-Trade Obligation Generation은 포함). **선택지 (b)**:
    "verbatim closed set" 주장 **철회**하고, 하위 generation(Release Generation·Post-Trade Obligation Generation)·
    compatibility graph·runtime-attestation·obligation/finality compatibility·software compatibility manifests·
    referenced policy objects **7항을 ADR-002-029/030 등 Phase-0 bundle-binding(§27 item 18–19·§9.2 item 14)으로
    이연**하고 top-level 29항만 Phase-1 `BundleMemberKind`로 모델링. **§5.3 line 119 전 36항을 §2.2(4) 2열(포함
    29·이연 7) 대조표로 고정**(산문 나열 금지 — 비대칭·누락 구조적 불가). **근거**: 산문 나열이 v1.0 비대칭을
    낳았고, 하위 generation은 타 ADR 소유·Phase-0-bound라 Phase-1 enum 값으로 모델링하면 unmodeled ADR-002-029/030
    내부에 phantom 결합이 생김. `bundle_complete`(§6.4)·SPG-INV-002는 "29 modeled member + 7 Phase-0 injected ref
    전부 resolved"로 정합.
  - **MINOR-1**: `ChangeDirection`에서 `UNORDERABLE` enum 값 **제거**(4종→3종) — 순서불가·미증명은
    `AUTHORITY_INCREASING`으로 접히고(ADR §11:317 "unorderable IS authority increasing" 충실) 순서불가는
    `ValidationReason.UNORDERABLE_DIRECTION`으로만 reason_set에 실림(§2.2(3)/§5.5). 소비자 `direction ==
    AUTHORITY_INCREASING` 검사가 별도 `UNORDERABLE` 값으로 우회되는 fail-open 인접성 봉합(근거: enum 제거가 §11:317에
    더 충실).
  - **MINOR-2**: activation seam 출력 명세 분리 — **seam 출력 = 4 개별 bool**(liveauth `atomic_activation_ok`
    `predicates.py:454`가 fold, 소비 signature 불변), `activation_atomic → ActivationVerdict`는 **spg 자체
    SPG-EV-004 property 검증용 내부 술어**(이중-레이어, 중복 아님; §3.4/§3.5/§5.3).
  - **NIT**: brokercap `ProfileKey` `records.py:48`(v1.0 인용 71–88은 ProfileVersion 범위)·
    `_require_independent_id_when_issued` `_base.py:352`(v1.0 인용 351 off-by-one) 정정.
- **v1.0 (2026-07-25) — 초안, 독립 비평 리뷰 대기.** ADR-002-014를 Phase 1(EV-L1) 설계 계약으로 실현.
  패키지 `tos.spg`(대안 `tos.envelope`[collision]·`tos.safetyprofile`[좁음]·`tos.config`[collision] 기각,
  §0.4a). 이중 아티팩트(Hard Safety Envelope + Runtime Safety Profile, 둘 다 IndependentIdArtifact·digest-bound·
  generation-immutable append-only) + Bundle + ActivationRecord + ConsumerCompatibilityManifest(§2). EV 분류:
  **core 8행(SPG-EV-001·002·003·004·005·006·008·012, 시리즈 최대 core tier) / predicate-only 4행(007·009·010·
  011) / not-Phase-1(런타임·+Security·형제) — 닫는 SPG-EV = 0건**(§1). seam: **7-소비자 produced-bool/scalar
  producer, sibling edge 0, PROMOTE 0**(코드 실측: liveauth `state.py:85–88/135/164/205`·authority
  `predicates.py:640`·rcl `records.py:101–102/469`·`vector.py:139`·time `snapshot.py:141`·capsule
  `capsule.py:88`·evidence `replay.py:113`·protective `records.py:94`, §3.4). 중심 fail-closed 술어:
  `profile_within_envelope`·`semantic_validation`(rich verdict)·`activation_atomic`·`activation_serializable`·
  `restrictive_override_admissible`·`expiry_revives_nothing`(§5). 앵커: SPG-INV-001..014·SPG-AC-001..012·
  SPG-EV-001..012(§0.4f). **실측-원천 정정**: orchestrator brief "SPG-AC-001..008" → ADR 실측 **012**(§상단).
  선제 봉합: fail-open(§4.1)·∅-공허(§4.1/§5.1/§5.2/§6.3/§6.4)·thin-signature→rich verdict(§5.2)·verbatim+line·
  self-referential VP 분석(§8.2). **어떤 EV도 닫지 않음·acceptance 미선언.**

### 10.2 비준 체크리스트 (운영자 · 독립 리뷰어 확인 사항)

1. **패키지 명명** `tos.spg`(Safety Profile Governance) 승인 — 또는 대안(§0.4a에서 `envelope`/`safetyprofile`/
   `config` 기각 근거 검토; naming은 load-bearing 아님).
2. **seam 결정**: produced-bool/scalar decoupled(edge 0, 권장) vs 대안 B(7개 소비자 측 edge) — §3.4/§0.4b.
   **[운영자 판단 지점]**. 7개 소비자 슬롯이 실재함을 코드로 재확인(리뷰어: liveauth/authority/rcl/time/
   capsule/evidence/protective 인용 라인 검증 — sibling 서사 아님).
3. **EV 분류**: core 8 / predicate-only 4 / not-Phase-1 판정과 **닫는 SPG-EV = 0건** 규율 확인. core tier가
   8행이어도 "EV-L1-complete 주장 금지"가 §1·§5·§7에 일관한지 self-consistency pass.
4. **소유권 분할(§3.5)**: spg가 liveauth re-arm·rcl capacity·authority mode/epoch/SoD-epoch·time expiry 산술·
   evidence replay engine·ADR-002-015 effective-principal을 **재저작하지 않음** 확인(#8 C1·#11 권위 중복 교훈).
5. **rich verdict 판단(§5.2)**: `SemanticValidationResult`(reason set)가 thin bool 대신 채택된 근거(ADR §11
   line 315 요구)가 타당한지(#11 MINOR thin-signature 교훈).
6. **fail-closed·∅-공허**: `profile_within_envelope` vacuous-dominant 부재·`bundle_complete` 빈-set 전-member-
   필요·`semantic_validation` 빈-bundle invalid 확인(#6 fail-open·#10 ∅-void 교훈).
7. **실측-원천**: SPG-AC 수(012, brief 008 정정)·SPG-INV(14)·SPG-EV 최소 레벨(8행 L1)·seam 라인이 원문/코드와
   일치하는지(#10 MAJOR·#8 line 791 교훈).
8. **self-referential VP(§8.2)**: VP scope=Bundle manifestation·layering 해소·VP 미신뢰(PROPOSED) 분석 타당성.
9. **broker-agnostic·숫자 하드코딩 0·firewall(§0.3)·verbatim 전사(§2.2)** 확인.
10. **비-acceptance**: 어떤 SPG-EV/ADR acceptance·restricted-live·production도 선언 안 함(§0.2)·Independent-
    Safety-Reviewer 하드 배제(IMPLEMENTATION-PLAN-002 §3) 확인.
11. **[v1.1] MAJOR-1 소유권 정렬**: spg가 effective-limit **min을 재생산하지 않고** 두 피연산자 scalar(envelope
    상한·profile 운영값)만 생산하며 권위적 min은 rcl 함수 `effective_limit`(`vector.py:139`)이 수행함을 §0.2↔
    §0.4b↔§3.4↔§3.5 self-consistency 재확인(phantom `EffectiveLimitVector` 잔존 0건).
12. **[v1.1] MAJOR-2 좌표 비붕괴**: §3.4 scalar-소비자 목록에 protective 부재·§4.4 "spg version scalar ≠ 각
    패키지 자체 artifact version" 주의 확인(protective `records.py:277`=자체 identity, spg 축 아님). 형제 seam
    인용 라인이 코드와 일치하는지 전수 재검증(sibling 서사 아님 — #10 MAJOR 교훈).
13. **[v1.1] MAJOR-3 대조표 완전성 + 선택지 근거**: §2.2(4) 대조표가 ADR §5.3 line 119 **전 36항**을 포함(29)/
    이연(7)으로 전수 분류하는지·"verbatim closed set" 철회가 정당한지·`bundle_complete`·SPG-INV-002 정합 확인.
    **[운영자 판단 지점]** 선택지 **(a)**[36항 전부 enum 추가] 대신 **(b)**[top-level 29항만 모델링·하위
    generation 7항 Phase-0 이연]를 택한 근거(하위 generation은 ADR-002-029/030 소유·Phase-0-bound·§9.2 item 14)
    검토.

**독립 리뷰어 공격 지점(open questions)**: (i) 이중 아티팩트가 단일 `SafetyConfigurationBundle` 아래 Envelope/
Profile를 nested로 담을지 vs 별개 top-level 레코드로 둘지(§2.1 — 별개 채택; bundle은 참조 집합). (ii)
`change_direction`의 순서불가→`AUTHORITY_INCREASING` 접기(v1.1 MINOR-1: `UNORDERABLE` enum 값 제거·reason으로 이동)가 §11 line 317을 과·소 실현하는지(§5.5·§2.2(3)). (iii)
liveauth `atomic_activation_ok`(이미 구현)와 spg `activation_atomic`의 소유권 경계 — spg가 4-bool을 생산하고
liveauth가 fold하는 분할이 중복인지 정합인지(§3.5 표). (iv) §8.1 candidate 신규 키 4종이 진짜 누락인지 vs
기존 키로 커버되는지(over-claim 위험 — #10 lesson). (v) core tier 8행이 실제로 전부 L1-decidable substrate를
갖는지(특히 SPG-EV-001 `+Security`·SPG-EV-003 `+Security`의 L1 부분과 +Security 부분 분리가 정확한지).
