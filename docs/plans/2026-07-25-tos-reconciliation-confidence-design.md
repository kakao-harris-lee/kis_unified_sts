# 설계 문서 #9 — Evidence·Reconciliation Confidence 계약 (2026-07-25, v1.2)

> **문서 번호 규약**: #1 경계·import-firewall, #2 Decision Context Capsule, #4 Evidence
> Store, #5 Risk Capacity Ledger(RCL), #6 Safety Authority, #7 Live Authorization, #8
> Orthogonal Trading State가 이미 존재한다(#3은 folded). Trustworthy Time·DSL은 병렬
> 트랙(A/C)이었고 트랙 A는 완료됐다. **#9 = 본 Evidence·Reconciliation Confidence 문서**
> 이며 ADR-002-006을 실현한다. safety-relevant 상태를 **per-field evidence + conservative
> bound**로 표현하는 confidence 모델(corroboration·conflict·negative-evidence·freshness·
> field-specific release proof)의 **순수·비전송 데이터 모델 + hypothesis property test**를
> 그린필드 `tos/src/tos/recon/`에 저작한다.
>
> **문서 지위**: kis_unified_sts 프로젝트 측 설계 계약. tos-spec에 대해 **non-normative**이며
> 스펙 텍스트(RFC/ADR/템플릿/프로파일)를 **변경하지 않는다.** broker-agnostic 원칙(project
> memory `tos-spec-broker-agnostic`): KIS 등 특정 브로커 사실은 프로젝트 측 예시로만 등장하며
> 규범 주장이 아니다. per-field confidence·conservative bound·corroboration·conflict·
> freshness·release-proof 술어는 전부 broker-agnostic이며, 브로커의 Final Quantity Proof
> **내용**은 capability class(Broker Capability Profile, ADR-002-004)로만 표현하고 본
> 문서는 그 proof를 **주입 opaque token**으로만 담는다. 본 문서는 IMPLEMENTATION-PLAN-002
> §4 Phase 1(EV-L1)의 **ADR-002-006 부분**을 실현한다.
>
> **선행 문서(의존)**:
> - [설계 #1 — `tos/` 경계 & import-firewall 계약 (v2, 운영자 비준)](2026-07-20-tos-boundary-and-import-firewall-design.md).
>   본 계약의 모든 모델은 §2.4 레이아웃(전용 top-level 패키지)에 놓이고 §3.2 허용목록 안에서만
>   의존한다(§0.3). line 164 "naming은 load-bearing이 아니다 — 내부 세분화는 후속 설계 문서가
>   정의한다"에 따라 본 문서가 `tos.recon` 패키지 내부를 정의한다.
> - [설계 #4 — Evidence Store 계약 (v1.1, 비준·구현됨)](2026-07-20-tos-evidence-store-design.md)
>   + 코드 `tos/src/tos/canonical/`. **canonicalization/digest-binding substrate(`tos.canonical`)·
>   `DigestBoundArtifact`·`IndependentIdArtifact`(이미 core)·`classify_record_pair`(이미 core)·
>   `ArtifactStatus`를 REUSE**한다(재정의 금지). evidence의 `id=f(digest)` **미채택** 결정을
>   본 문서가 **동형으로 상속**한다(§2.1/§3.1). **`tos.evidence`(append-only 증거 ledger)는
>   import하지 않는다** — evidence store는 **하류 투영**이고 reconciliation confidence는 그
>   상류 decision-side 모델이다(§3.5, layering).
> - [설계 #5 — Risk Capacity Ledger 계약 (v1.1, 비준)](2026-07-21-tos-risk-capacity-ledger-design.md)
>   + 코드 `tos/src/tos/rcl/`. **rcl `ReservationRecord`가 이미 per-field conservative bound
>   필드**(`filled_quantity_lower_bound`·`filled_quantity_upper_bound`·
>   `remaining_executable_quantity_upper_bound`, `records.py:105–107`, 전부 `CanonicalDecimal|None`)
>   **를 담고 있고**, `transition_allowed`가 `RELEASED`를 `FINAL_QUANTITY_PROOF` cause에만 허용한다
>   (INV-007, `predicates.py:467–468`). ADR-002-006은 ADR-002-002 §22(Reconciliation Integration:
>   evidence model·conservative bound use·evidence conflict·negative evidence)를 **elaborate**한다.
>   본 문서의 **중심 결정 하나**가 이 경계다(§0.4c/§3.4): recon은 conservative bound에
>   `CanonicalDecimal`을 REUSE하되, **`CanonicalDecimal`을 `tos.canonical`로 PROMOTE**하여
>   recon↔rcl **sibling edge 없이** 담는다(대안·근거 §0.4c). recon은 capacity를 **release하지
>   않고**(ADR-002-006 §10 line 147 "cannot mutate capacity directly") release **proof bool**만
>   생산하며, rcl INV-007/orthostate CPL-2가 그것을 소비한다.
> - [설계 #8 — Orthogonal Trading State 계약 (v1.1, 비준·구현됨)](2026-07-25-tos-orthogonal-state-design.md)
>   + 코드 `tos/src/tos/orthostate/`. **본 문서의 중심 아키텍처 결정**이 이 경계다(§0.4b/§3.4):
>   orthostate `KnowledgeState`(ADR-002-005 §8 line 128 "Owned by the Reconciliation Service
>   (ADR-002-006 will define the confidence representation)")는 **per-action aggregate 좌표**이고,
>   `knowledge_transition_allowed`(`predicates.py:498–546`)는 `corroboration`·
>   `final_quantity_proof_where_broker_involved`·`freshness_lost`를 **주입 `bool|None` 플래그**로
>   소비한다(fail-closed). recon은 그 플래그의 **상류 producer**다 — **recon은 orthostate를
>   import하지 않고, orthostate도 recon을 import하지 않는다**(형제, 어느 방향 edge도 없음);
>   composition은 caller(미래 Reconciliation Service 런타임) 소관이다. 이는 #8이 이미 confidence를
>   주입 opaque flag로, time을 decoupled로 둔 결정과 **동형**이다.
> - [설계 — Trustworthy Time 모델 계약 (v1.1, 비준)](2026-07-21-tos-trustworthy-time-design.md)
>   + 코드 `tos/src/tos/time/`. freshness/time-confidence(ADR-002-006 §7 line 103)는 시간 모델에
>   의존하나 **numeric freshness horizon은 Verification Profile 소관**(ADR-002-006 §4 line 49·§14
>   line 186 "Numeric tolerances, freshness horizons, and detection bounds belong in the
>   Verification/Safety Profiles")이므로 Phase 1은 freshness를 **주입 opaque flag + time-generation
>   scalar**로만 담고 **`tos.time`을 import하지 않는다**(#8이 STALE freshness를 주입 flag로 둔 결정
>   동형; closure 최소화). 상세 §3.5.
>
> **규범 원천**: `ADR-002-006` — Evidence and Reconciliation Confidence Model (Status:
> **Proposed**, **202 line — 지금까지 중 최단**). **Amends** RFC-002 §15 State Authority and
> Reconciliation(confidence 모델을 normative하게 만듦 — ADR line 8). **Depends On** RFC-000
> constitutional safe state; RFC-001 **SAFE-022/023/024/025/030/031/034**; ADR-002-005(Knowledge
> dimension)·ADR-002-002(capacity coupling)·ADR-002-004(broker evidence + Final Quantity Proof)·
> ADR-002-003(time/authority currentness)(ADR line 9). 매핑 대상 EV:
> `verification/EVIDENCE-REGISTER-002.csv`의 **`RECON-EV-001..005`(line 96–100)**. **AC**:
> `AC-006-1..5`(§13 line 174–178). ADR-002-006은 **자체 INV 시리즈를 정의하지 않는다**(실측:
> `INV-` 2건은 전부 ADR-002-002 `INV-012` cross-cite — §0.4g). 앵커는 `AC-006-*`·`RECON-EV-###`·
> `§-clause`·`SAFE-*`뿐이다.
>
> **비준 기록**: **2026-07-25 운영자 비준(v1.1) — 효력 발생.** *(v1.2 = §1 -004 행 time-loss class
> gloss 에라타만 — `UNKNOWN`→`STALE`(구현·코드 리뷰 확정; ADR §7 line 103은 class 미지정·fail-closed만
> 요구, release는 §6.1 독립 게이트로 어느 class든 차단), 의미 변경 아님·비준 효력 유지; §10.1 v1.2.)* §10.2 판단 지점 3건 승인:
> **`CanonicalDecimal` PROMOTE(rcl→canonical)**(내부 import 사이트 2곳 갱신·courtesy shim·rcl suite
> 무회귀 의무) · **produced-bool seam**(sibling edge 0 + MANDATED test-only cross-check) ·
> **좌표 조정 의무 기록**(후속 설계의 별개 typed 필드 MUST). 효력: `tos/src/tos/recon/` Phase 1
> (EV-L1) 순수·비전송 모델 + property test 착수. **RECON-EV 0건 완결** — acceptance 주장 없음;
> §9.2 Phase-0 11항목은 별도 게이트 유지. 독립 비평 리뷰 **ACCEPT-WITH-MINOR**(CRITICAL 0 /
> MAJOR 0 / MINOR 5 — 전량 반영, §10.1).
> ADR acceptance는 오직 *실행된* evidence로만 온다(project memory `tos-spec-rfc-authoring-track`).
> **비준 시 효력 예정**: §10.2 판단 지점(특히 **`CanonicalDecimal`을 `tos.canonical`로 PROMOTE** ·
> recon↔orthostate/rcl **sibling edge 0건** 유지 · freshness 주입 결정) 승인 후 `tos/src/tos/recon/`
> Phase 1(EV-L1) 순수·비전송 모델 + property test 착수. **RECON-EV 0건 완결** — acceptance 주장
> 없음; §9.2 Phase-0 항목은 별도 게이트.
>
> **리뷰 이력**: **v1.1 — 독립 비평 리뷰 ACCEPT-WITH-MINOR 반영(CRITICAL 0 / MAJOR 0 / MINOR 5, 전량 반영
> §10.1; 리뷰어의 다섯 attack prediction 전부 반증 — transcription 13/13·bound 방향·seam signature line 일치·
> cross-section 정합·프로파일 키 line 정확).** 직전 시리즈 — #6 v1.0 **REJECTED**(fail-open
> seam), #7 v1.0 **REVISE**(SAFE-053 under-realization), #8 v1.0 **REJECT**(cross-section 모순:
> representability를 coupling-cleanliness와 혼동 — C1); #6/#7 두 건 모두 비준 후 transcription
> 에라타(부등호 방향·필드명)를 요했고, #8 구현은 MAJOR fix 1건(signature narrowing이 설계-지정
> region split을 drop)을 요했다. 본 문서가 **선제 봉합**한 defect class: (a) **§1 core-tier
> over-claim 방지** — RECON-EV는 register 최소 레벨에 **EV-L1 슬라이스가 0건**이므로 #8의 "core
> tier 존재(RCL-형)"이 아니라 **Time/#6/#7의 "0건 완결" shape**다(§1 결정적 사실 1 — #8과 정반대
> 판정, self-consistency 최우선); (b) **no-blended-release를 서술이 아니라 *구조적 표현 불가*로**
> 실현(numeric score 타입 부재·averaging 함수 부재 — §4.1); (c) **cross-section self-consistency
> pass**(§1 분류 ↔ §5/§6 술어 ↔ §7 test-target를 finishing 전에 대조 — C1 lesson); (d) confidence
> class·conservative bound·proof rule을 ADR §5/§8 **verbatim**으로 전사(에라타 defect class 방지).
> 수용 서명 게이트는 IMPLEMENTATION-PLAN-002 §3 하드 배제(Independent-Safety-Reviewer는 본 문서의
> 저자/통합자여서는 안 됨)를 따른다.

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. ADR-002-006 조항별 **Phase 1(EV-L1) 도달성 경계**(§1). `RECON-EV-001..005`의 **predicate-only /
   not-Phase-1** **2분류**(NO core tier). **결정적 사실: RECON-EV 다섯 행 모두 register 최소 레벨이
   EV-L2 이상**(001=`EV-L2/3`·002=`EV-L3`·003=`EV-L2/3`·004=`EV-L2/3`·005=`EV-L3+Broker`, 전부
   `Critical`·`NOT_IMPLEMENTED`, line 96–100 실측)이라 **EV-L1 슬라이스가 0건**이다 — 이는 #8/RCL의
   core-tier shape가 **아니라** Time·#6·#7의 **"EV 0건 완결"** shape다. **닫는 RECON-EV = 0건**
   ("EV-L1-complete 주장 금지" 규율; VER-002-001 §5 "written test is not evidence").
2. per-field confidence의 **데이터 모델 계약**(§2): 로컬 `FieldConfidenceClass`(5종 StrEnum, ADR §5
   line 73–80 verbatim) + 로컬 `SafetyRelevantField`(§5 line 57–67의 명명 필드, **"at least these"
   = 최소 집합·비폐쇄**) + `ConservativeBound`(lower/upper `CanonicalDecimal|None`, None⇒unbounded-
   conservative) + `FieldConfidence`(§1 line 15–22의 per-field 구조) + append-only digest-bound
   `FieldReconciliationAssessment`(IndependentIdArtifact) + 주입 입력 `EvidencePathObservation`·
   `ReleaseProofInputs`.
3. **no-blended-release 구조 불변식**(§4.1, 중앙): confidence는 **class(enum) + bounds**뿐이며 recon
   전체에 **numeric confidence score 타입이 존재하지 않고**, release·reconciliation 술어는 **per-field
   proof만** 입력받고 **blended-scalar 입력 경로·averaging 함수가 부재**하다 — "aggregate 점수가 높아서
   release"가 **구조적으로 표현 불가**다. ADR §1(line 15)·§5(line 86 "never a midpoint, average, or
   blended score")·§7(line 101)·§11(line 155)·ADR-002-002 §22.2를 타입 수준으로 실현.
4. **conservative bound 계약**(§4.3/§5.2): field별 upper(adverse quantity)·lower(understate 불가한
   경우만)의 방향 규칙(ADR §5 line 84–86 verbatim); **uncertainty ⇒ bound widen**; **bound는 양성
   증명 없이 narrow 불가**(ADR §8 line 121 "reducing conservatism requires stronger proof than
   increasing it"); **conflict ⇒ merge_conservative가 union으로 widen(never average)**; **None ⇒
   most-conservative(unbounded)**.
5. **corroboration·conflict·negative-evidence 술어**(§5, RECON-EV-001/002/003 substrate): Corroborating
   Evidence Path(§6 line 92) 정의 위 `classify_field`; **≥2 sufficiently-independent paths agree within
   tolerance ⇒ CORROBORATED**(§6 line 93); **single source / silence ⇒ release grade 도달 불가**(§5 line
   75·§6 line 94; SAFE-023); **query omission ≠ negative evidence**(§7 line 102 — absence는 confidence만
   낮추고 NONE/CANCELLED/released 확립·bound narrow 불가; RECON-EV-002). independence·tolerance는 **주입
   판정**(hazard 척도 — §6 line 95는 Verification Profile 수치).
6. **field-specific release proof 술어**(§6, RECON-EV-005 substrate): §8 line 112–118 generic contract를
   `field_reconciled_proof_ok`로 — capacity-releasing 필드(final filled quantity·remaining executable
   quantity)는 **CORROBORATED ∧ FQP(주입 token, +Broker 이연) ∧ freshness ∧ no unresolved conflict**;
   weaker evidence(cancel ACK·terminal-without-quantity·single-source·late correction) ⇒ not ok
   (RECON-EV-005 Expected). 이 bool이 orthostate `knowledge_transition_allowed`·CPL-2·rcl INV-007이
   소비하는 값이다(§3.4).
7. **freshness/time-confidence 술어**(§6.3, RECON-EV-004 substrate): `freshness_ok` — past horizon ⇒
   STALE; time confidence 상실 ⇒ fail closed; **time service가 new generation으로 복구돼도 old marker는
   auto-refresh되지 않는다**(§7 line 103; RECON-EV-004 Expected "do not become current merely because
   time service recovers"). **`tos.time` 미import** — 주입 opaque flag + `time_generation` scalar
   (#8 동형).
8. **recon↔orthostate/rcl 경계(중심 아키텍처)**: recon은 **sibling edge 0건**을 유지한다(§0.4b/§0.4c/§3.4).
   recon은 confidence class + bounds + **proof bool**을 생산하고 orthostate/rcl은 그것을 **주입 플래그**로
   소비한다(compose seam은 caller 소관). `CanonicalDecimal`은 **`tos.canonical`로 PROMOTE**하여 recon↔rcl
   edge 없이 REUSE한다(§0.4c). `tos.orthostate`·`tos.rcl`·`tos.time`·`tos.evidence`·`tos.capsule`·
   `tos.authority`·`tos.liveauth`·`tos.dsl` **미import** — recon은 `tos.canonical`·`tos.ordering`(둘 다
   core)만 import한다(§0.3).
9. **fail-closed 규율 + named canary**(§4·§5·§6): blended-score 경로 구조적 부재; **빈 evidence set ⇒
   UNKNOWN(no confidence, never vacuous)**; **conflicting ⇒ bound widen(never averaged)**; **single-source
   ⇒ below release grade(구조적)**; **omission ≠ negative(bound narrow·terminal 확립 불가)**; **None ⇒
   most-conservative**; 각 가드에 both-ways canary.
10. **property-test 하네스 타깃**(§7, §1 분류 정렬 — 전부 predicate substrate, 닫는 EV 0건) +
    import-closure 검증(§7.1) + run manifest 7항목(§7.2).
11. **bounds 주입 계약 + 누락 프로파일 키 Phase-0**(§8): 실측 결과 **확정 신규 누락 distinct 키 0건** +
    **#8이 flag한 knowledge/reconciliation-staleness candidate를 본 문서가 ADR-002-006 bound family로
    정밀화**(per-field freshness horizon · corroboration agreement tolerance · independence-degree-by-
    hazard — 전부 ADR §14 line 186이 Verification/Safety Profile로 위임; 신규 count 아님·#8 placeholder의
    refinement) — 기존 `MAX_clock_drift_ppm`·`B_external_activity_detect`·`MAX_currentness_vector_age_ms`
    재계상 없음.

### 0.2 하지 않는 것 (경계·NO 목록)

- **ADR/스펙 비준·acceptance·restricted-live·production 어느 것도 승인하지 않는다.** ADR-002-006
  §15(line 202) "authorizes design and implementation-planning work only; it does not authorize live
  trading." ADR acceptance는 오직 *실행된* evidence로만 온다.
- **evidence persistence·custody·integrity·replay를 구현하지 않는다.** ADR §4(line 49) "does not
  decide ... evidence persistence, custody, integrity, and replay (ADR-002-016)." Phase 1은 assessment
  **데이터 모델 + 술어**만 저작하며 실제 retention·gap-check·replay 메커니즘은 ADR-002-016 소관이다.
  Evidence Store를 reconciliation authority로 만들지 않는다(§15 line 198).
- **broker-specific Final Quantity Proof·evidence 내용을 결정하지 않는다.** ADR §4(line 49):
  broker-specific FQP·evidence semantics는 **ADR-002-004(Broker Capability Profile)** 소관이고 본
  모델에 **conform**할 뿐이다. Knowledge `RECONCILED`·release proof의 **양성 proof token**은 **주입
  opaque bool**로만 담는다(+Broker 이연 — §6.1). broker-agnostic: KIS 등은 예시일 뿐 capability class로만
  표현.
- **post-trade obligation lifecycle serialization·field-specific finality recipe를 결정하지 않는다.**
  ADR §4(line 49)·§5(line 69): PTOL 직렬화·field-specific finality는 **ADR-002-030** 소관이며,
  ADR-002-030은 recon의 per-field 결과를 **소비**할 뿐 재정의하지 않는다. recon은 PTOL 필드
  (`post_trade_obligation_identity_and_version` 등)의 confidence **모델**만 담고 finality recipe는 담지
  않는다.
- **numeric tolerance·freshness horizon·detection bound를 승인하지 않는다.** ADR §4(line 49)·§14(line
  186) "Numeric tolerances, freshness horizons, and detection bounds belong in the Verification/Safety
  Profiles, not this ADR." Phase 1은 전부 **주입 파라미터**로 담고 **어떤 숫자도 하드코딩하지 않는다**
  (CLAUDE.md). 값 승인은 Bounds-Approver 게이트(§8·§9.2).
- **trustworthy-time 메커니즘·authority epoch을 구현하지 않는다.** ADR §4(line 49): time 메커니즘은
  ADR-002-008/003 소관. freshness는 주입 flag(§3.5).
- **capacity를 직접 mutate하거나 Ledger를 overwrite하지 않는다.** ADR §10(line 147) "requests defined
  Ledger/capacity transitions through the owning authority; **it cannot mutate capacity directly**";
  §8(line 121) "SHALL NOT overwrite the Ledger with an optimistic snapshot or free capacity because one
  source omits an order." recon은 release **proof bool**을 생산할 뿐 capacity mutation 메서드가 **부재**
  하다(§4.7 representation≠mutation).
- **reconciliation trigger 스케줄·런타임 orchestration을 구현하지 않는다.** ADR §9(line 125–138)의
  트리거(startup/restart/reconnect·timeout·external activity·conflict·periodic·before-restore)는 **런타임
  orchestration**이다 — Phase 1은 clock을 읽지 않고 assessment **결과 모델**만 담는다(트리거 latency·
  external-activity detection은 EV-L2/3·기존 `B_external_activity_detect` 키). **닫는 RECON-EV 0건.**

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

recon 모델은 다음만 import한다:

- 서드파티: `pydantic`(frozen 모델), `pytest`·`hypothesis`(테스트만). **`numpy`/`pandas`/`pyyaml`도
  import하지 않는다** — confidence는 StrEnum·boolean·집합 논리, bound는 `Decimal`(`CanonicalDecimal`)
  산술뿐이라 수치 백엔드가 불필요하고, 모든 bound·tolerance·freshness horizon은 주입 파라미터이며 YAML
  파싱은 하네스(설계 #3) 소관이다(closure 최소화 — #5 §0.3·#7 §0.3·#8 §0.3 동형).
- tos 자기 자신: `tos.canonical`(FrozenModel·DigestBoundArtifact·**이미 core인 `IndependentIdArtifact`**·
  **이미 core인 `classify_record_pair`**·`RecordPairKind`·`ArtifactStatus` + **PROMOTE될 `CanonicalDecimal`**
  — §3.1/§0.4c), `tos.ordering`(assessment append-only 순서 — §3.2), `tos.recon.*`. **`tos.orthostate`·
  `tos.rcl`·`tos.time`·`tos.evidence`·`tos.capsule`·`tos.authority`·`tos.liveauth`·`tos.dsl`을 import하지
  않는다**(형제 또는 하류/상류; scalar·주입 좌표·produced-bool로만 참조 — §3.4/§3.5).
- **`shared.config` 절대 금지**(설계 #1 §6.1, `.importlinter`): `shared.config.__init__`이
  `shared.config.secrets`(→ `os.environ`)를 무조건 전이 import한다. recon은 애초에 어떤 `shared.*`도
  필요로 하지 않는 순수 커널이다.
- **금지(직접·전이 모두)**: `shared.execution`, `shared.kis`, `shared.streaming`, `shared.llm`,
  `shared.storage`, `shared.backtest`, `services.*`, `cli.*`(설계 #1 §2.3; `.importlinter` forbidden set).
- **firewall 구조 확인(실측)**: `.importlinter`는 **`forbidden` 계약**(`tos-operational-firewall`,
  `type = forbidden`; source=`tos`; forbidden={shared.execution/kis/streaming/llm/storage/backtest,
  shared.config.secrets, services, cli}) **뿐이며 `layered` 계약이 아니다** — intra-tos sibling→sibling
  edge는 구조적으로 금지되지 않고 설계 #1 §3.2의 "자기 자신 `tos.*`" 허용 조항이 이를 커버한다(#7·#8 실측
  결론 상속). 본 문서는 그럼에도 **sibling edge 0건**을 **설계 규율**로 유지한다(§0.4b/§0.4c) — firewall
  하드 규칙이 아니라 결합-최소화 주석이다.
- 이 배제를 능동 강제하는 것이 §7.1 import-closure 검증 테스트다(`import tos.recon` closure에 금지·
  `shared.config`·`os.environ`·numpy/pandas/yaml·**`tos.orthostate`·`tos.rcl`·`tos.time`·`tos.evidence`·
  `tos.capsule`·`tos.authority`·`tos.liveauth`·`tos.dsl`** 부재 assert; **`tos.canonical`·`tos.ordering`은
  존재 허용**). required check(`tos-firewall`, `tools/tos_firewall_check.py` layer-① AST + `.importlinter`
  layer-② 전이 방어)와 함께 green이어야 본 선언이 능동 성립한다.

### 0.4 REUSE / import / 경계 결정 요지 (핵심 아키텍처)

**(a) 패키지 위치·명명 = `tos/src/tos/recon/`.** ADR-002-006은 "Reconciliation Service"(§10 line 144)가
소유하는 reconciliation confidence 모델을 세운다. 명명 대안 비교:

- **`tos.confidence`(기각)**: "confidence"는 지나치게 generic하고, 본 모델은 *reconciliation* evidence
  confidence이지 임의 confidence가 아니다. capsule의 per-field context freshness(`FieldState`)와도 개념
  혼동을 부른다.
- **`tos.reconciliation`(기각)**: 정확하나 verbose하고 다른 tos 패키지(canonical/capsule/orthostate/rcl/
  liveauth/authority/evidence/ordering/time/dsl)의 terse 명명 관행과 어긋난다.
- **`tos.evidence`(불가)**: **이미 존재**한다(설계 #4 Evidence Store — append-only 증거 ledger). recon은
  그 하류 투영이 아니라 상류 decision-side 모델이므로 별개 패키지여야 한다(§3.5 layering).
- **선택 `tos.recon`**: **register prefix `RECON-EV`·ADR §10 "Reconciliation Service"·gate-status §2 line
  137 "reconciliation confidence"** 를 직접 명명, terse, evidence(store)와 명확 구분. naming은 load-bearing이
  아니다(설계 #1 line 164) — 운영자 치환 가능; **load-bearing은 layering**(recon → canonical·ordering 한
  방향; orthostate·rcl·time·evidence·capsule·authority·liveauth·dsl과 형제/상하류, **edge 0건**). 내부
  module(`vocabulary.py`·`records.py`·`state.py`·`predicates.py`·`_base.py`)은 rcl/orthostate 선례 동형이며
  **충돌 없음**(실측: `tos.recon` 및 하위 module 부재).

**(b) recon↔orthostate 경계 — sibling edge 미채택, recon = 주입-플래그 producer (중심 결정 #1).**
ADR-002-005 §8 line 128이 명시한다: Knowledge 차원은 "Owned by the Reconciliation Service (**ADR-002-006
will define the confidence representation**)." 즉 orthostate `KnowledgeState`(per-action aggregate 좌표,
7종)는 recon이 정의하는 confidence의 **소비자**다. #8은 이미 이 seam을 **주입 opaque flag**로 봉인했다:
`knowledge_transition_allowed(..., corroboration: bool|None, final_quantity_proof_where_broker_involved:
bool|None, freshness_lost: bool|None, quarantine_exit_evidence: bool|None)`(`orthostate/predicates.py:498–546`)
과 `CouplingSideConditions.final_quantity_proof`(CPL-2, `orthostate/state.py:44`)가 그 플래그들이다. 대안
비교(#8 §0.4b 형식):

- **대안 A — recon이 `tos.orthostate`를 import(네 번째 sibling→sibling edge)**: recon이 `KnowledgeState`를
  import해 "이 per-field confidence 집합이 aggregate `RECONCILED`를 허용" 류 술어를 typed로 노출. **기각**:
  (i) recon은 `KnowledgeState` **값을 조작하지 않는다** — proof **bool**을 생산할 뿐이고, aggregate 좌표의
  transition legality는 이미 orthostate `knowledge_transition_allowed`가 소유한다. 좌표 명명은 **cosmetic**
  이다. (ii) **backwards edge**: recon은 dataflow상 orthostate의 **상류**(confidence를 생산 → orthostate가
  소비)인데, 상류가 하류를 import하는 것은 부자연스럽다. (iii) 시리즈가 최소화하려는 cross-sibling edge를
  하나 더 늘린다(#8이 세 번째 edge를 운영자 판단 지점으로 flag). (iv) **cycle 위험**: 지금은 orthostate가
  recon을 import하지 않아 acyclic이나, 미래에 누군가 orthostate에서 recon confidence class를 참조하면 즉시
  cycle. **liveauth와 원칙적으로 다르지 않다** — #7 liveauth가 capacity 값을 추론하지 않고 reservation_id를
  불투명 link로만 담은 것과 동형(recon은 aggregate 좌표를 조작하지 않음).
- **대안 B — orthostate가 recon을 import(방향 역전)**: **불가**. orthostate는 이미 confidence를 주입 flag로
  두기로 비준됐고(#8 §0.4e), orthostate→recon이면 recon→(어떤 것도)와 무관히 orthostate가 confidence 계산에
  의존하게 돼 #8이 세운 layering(orthostate는 opaque flag만 소비)을 깬다. 또한 recon→orthostate가 나중에
  필요해지면 cycle.
- **선택 — decoupled, plain-bool producer(edge 0건)**: recon은 **자신의 per-field 어휘**(`FieldConfidenceClass`
  5종 — ADR §5 line 73–80, `KnowledgeState`와 **별개 축**)와 proof-rule 술어를 저작하고, 그 출력은 **plain
  `bool`**(`corroboration_established`·`field_reconciled_proof_ok`·`freshness_lost`·`any_field_conflicted`)로
  orthostate가 **이미 선언한 주입 signature와 타입 일치**한다(둘 다 `bool|None`·fail-closed). composition
  (recon 출력 → orthostate 주입 플래그)은 **caller(미래 Reconciliation Service 런타임) 소관**이며 Phase 1
  밖이다. 근거: (i) #8 자신이 이 seam을 주입 flag로, time을 decoupled로 봉인한 결정과 **완전 동형** — 일관성.
  (ii) edge 0건 — 시리즈가 최소화하려는 cross-sibling edge를 늘리지 않는다(#8보다 깨끗). (iii) cycle 원천적
  차단. (iv) **compose seam-sealing**: 타입 일치 + fail-closed 정합으로 seam이 조립된다 — 검증은 caller-side
  integration(EV-L2/3)에서 하거나, 원한다면 **test-only** 모듈이 recon·orthostate를 **둘 다 import**해 seam을
  대조할 수 있다(테스트 import는 firewall `import tos.recon` package closure에 계상되지 않음). Phase 1은 #8의
  time-seam 이연과 **동형으로 composition을 caller/integration으로 이연**한다(seam은 §3.4에 문서 계약으로 명시).
  **운영자 판단 지점(§10.2)**: seam을 (지금처럼) plain-bool decoupled로 둘지, 대안 A(네 번째 edge, typed
  target 명명)로 갈지 — **decoupled 권장**(edge·cycle 회피, #8 정합).

**(c) conservative bound 수치 타입 — `CanonicalDecimal`을 `tos.canonical`로 PROMOTE (중심 결정 #2).**
recon의 `ConservativeBound`(lower/upper)는 quantity(filled·remaining·position·cash/margin)라 `Decimal`이
필요하고, digest-bound `FieldReconciliationAssessment`의 covered 필드이므로 **`1.0` vs `1.00`가 digest에서
갈리는 gap을 막는** canonical Decimal이 필요하다(bare `Decimal` 금지 — `rcl/vector.py:47–49` "Use this — never
a bare Decimal — for any covered Decimal field"). 실측: `CanonicalDecimal`(`Annotated[Decimal,
BeforeValidator(_normalize_decimal)]`)은 **현재 `tos.rcl.vector:50`에 있으나 rcl `__all__`로 public 재노출되지
않고**, docstring이 스스로 "mirrors `tos.canonical` `_num_token`"·"canonical §3.1a"라 밝힌다 — 개념상
**canonical substrate**이며 rcl이 먼저 필요로 해 그곳에 착지했을 뿐이다(`_num_token`은 이미
`tos.canonical.canonicalization:78`). 대안 비교:

- **대안 A — recon이 `from tos.rcl.vector import CanonicalDecimal`(rcl 내부 module 도달)**: **기각**. (i)
  rcl `__all__` 미노출 private module에 도달 — fragile. (ii) recon→rcl **sibling edge** 생성(네 번째 cross-
  sibling edge). (iii) recon은 그 외 rcl 심볼(CapacityState·TransitionCause)이 **불필요**하므로 numeric
  primitive 하나 때문에 무거운 형제 의존을 지는 것은 과하다.
- **대안 B — recon이 로컬 canonical-Decimal 재정의**: **기각**. DRY 비협상 위반(CLAUDE.md) — canonical
  Decimal normalization 의미가 두 진리원이 되어 digest drift 위험(#8 §0.4b가 capacity lattice 재표현을 기각한
  것과 동일 근거).
- **대안 C — rcl `__init__`에 `CanonicalDecimal` additive public 재노출 후 recon이 `from tos.rcl import
  CanonicalDecimal`**(#8의 comparator additive 노출 형식): rcl module layout 무변경·최소 침습. 그러나 **여전히
  recon→rcl sibling edge**를 만들고, 의미상 numeric primitive가 recon→rcl 의존을 강제하는 것은 backwards다.
- **선택 — `CanonicalDecimal`(+ `_normalize_decimal`)을 `tos.rcl.vector`에서 `tos.canonical`로 PROMOTE**:
  깨끗한 shared-atom PROMOTE(#5의 ordering/classify PROMOTE 선례). `_normalize_decimal`은 stdlib(`Decimal`)
  + pydantic `BeforeValidator`만 쓰고 rcl 의존이 **전무**하다(순수 relocation). rcl은
  `from tos.canonical import CanonicalDecimal`로 재import(동작 보존; 필요 시 `rcl.vector`에 back-compat
  re-export). recon은 `from tos.canonical import CanonicalDecimal`. **결과: recon → `tos.canonical`만, rcl↔
  recon sibling edge 0건.** #8의 `CapacityState` 사례와 **정반대 판정**인 이유: `CapacityState`는
  `transition_allowed`·`_CONSERVATISM_RANK`·`CapacityVector` 전체에 **본질적으로 결부**돼 PROMOTE가 rcl을
  hollow-out하지만(#8 §0.4b 대안 C 기각), `CanonicalDecimal`은 **자기완결 numeric primitive**라 clean-atom
  PROMOTE다. **PROMOTE = 1건**(records substrate는 #5/#6 PROMOTE로 이미 core이므로 0건 — 순 합계 1). **운영자
  판단 지점(§10.2)**: PROMOTE는 ratified rcl 접촉(additive·behavior-preserving relocation)이므로 승인 필요.
  **Fallback**: PROMOTE 불허 시 대안 C(rcl additive 재노출 + recon→rcl edge)로 후퇴 — 이 경우 recon은 **네
  번째 cross-sibling edge**를 지며 §7.1 import-closure가 `tos.rcl` 존재를 허용 대상으로 기록한다(비권장 —
  edge-minimization 위배).

**(d) `tos.canonical` REUSE + `id=f(digest)` 미채택 + PROMOTE 1건.** `FieldReconciliationAssessment`는
`tos.canonical.IndependentIdArtifact`(id⊥digest; `_base.py:328`)·`DigestBoundArtifact`(digest 검증;
`_base.py:98`)를 REUSE한다. **`id=f(digest)`(`IdDerivedArtifact`) 미채택**: assessment는 서비스-할당
identity를 가지며(reconciliation run별), same-id/diff-bytes(위조·재제출) 탐지에 `classify_record_pair`(이미
core, `record_pair.py:52`, `CRITICAL_CONFLICT`)를 쓰려면 id⊥digest여야 한다(설계 #4·#5·#6·#7·#8 §3.1과 완전
동형; capsule의 content-addressed `id=f(digest)`와 정반대). **records substrate PROMOTE = 0건**
(IndependentIdArtifact·classify_record_pair 이미 core); **numeric substrate PROMOTE = 1건**(CanonicalDecimal
— §0.4c). `tos.recon._base`는 rcl/orthostate 동형의 thin re-export shim.

**(e) `tos.evidence`·`tos.capsule`·`tos.time`·`tos.authority`·`tos.liveauth` 미import(형제/상하류).**
- **`tos.evidence` 미import(layering)**: recon은 **decision-side 상류 confidence 모델**이고 evidence store는
  **하류 투영**(설계 #5 §3.1이 인용한 "evidence stores are downstream projections")이다. reconciliation이
  raw evidence를 retain·gap-check·replay하는 것은 **ADR-002-016** 소관이며(ADR §4 line 49·§14 line 186·§15
  line 198 "without making the Evidence Store a reconciliation authority"), 상류가 하류를 import하면 layering
  역전이다. ⇒ `EvidencePathObservation`은 evidence 레코드를 **scalar(evidence_id/generation/digest) 참조**로만
  담고 클래스를 import하지 않는다. **실측 확인**: `tos.evidence`에 confidence/per-field-class enum **부재**
  (reconcil 히트는 ledger gap 필드뿐).
- **`tos.capsule` 미import(다른 축 — 좌표 비붕괴)**: capsule `FieldState`(`INVALID>CONFLICTED>STALE>UNKNOWN>
  VALID`, `field_state.py:7`, ADR-002-018)는 **per-field context freshness** 축이고, orthostate
  `KnowledgeState`는 **per-action aggregate knowledge** 축이며, recon `FieldConfidenceClass`는 **per-field
  evidence confidence** 축이다 — **세 개의 별개 좌표계**다. 토큰 `UNKNOWN`/`CONFLICTED`/`STALE`을 공유하나
  재사용하면 축 붕괴다(#6 §4.7·#8 §0.4e coordinate non-collapse). ⇒ `FieldConfidenceClass`는 로컬 저작; canary:
  `FieldConfidenceClass.CONFLICTED` ≠ `KnowledgeState.CONFLICTED` ≠ `FieldState.CONFLICTED`. **주의**: #8의
  dimension-swap canary는 **전역 string 값 구분**에 의존했으나 recon 축은 다른 두 축과 **string 값을 공유**
  한다(의도 — ADR가 per-field·per-action 모두 `CONFLICTED`/`STALE` 사용); 따라서 recon의 non-collapse는
  전역-string이 아니라 **타입 구분 + 미import**로 성립하며(recon은 다른 두 축을 import하지 않아 swap 원천
  차단), canary는 document-level 회귀로 고정(§4.2).
- **`tos.time` 미import**: (0.1 item 7) freshness numeric horizon = Verification Profile 소관이므로 주입 flag +
  `time_generation` scalar(§3.5). rcl·orthostate가 time을 미import한 선례 동형.
- **`tos.authority`·`tos.liveauth` 미import**: Reconciliation Service의 Knowledge-소유권(ADR §10 line 144)은
  orthostate §12 ownership 표(`TransitionAuthority.RECONCILIATION_SERVICE` role label)의 소관이지 recon의
  것이 아니다 — recon은 confidence **계산**이며 transition authority enum이 불필요하다. authority-epoch
  currentness는 freshness의 일부로 주입 flag.

**(f) 불변식 명명 규약 — INV 시리즈 창작 금지.** **실측(grep)**: ADR-002-006은 **자체 INV 시리즈를 정의하지
않는다** — `AC-006-1..5`(§13)·`RECON-EV-001..005`만 가지고 `INV-` 2건은 전부 **ADR-002-002 `INV-012`
cross-cite**(§7 line 101·§8 line 121)다. ⇒ 본 계약은 모델 불변식·술어를 **`AC-006-1..5` / `RECON-EV-###` /
§-clause 번호 / `SAFE-###`(Depends-On line 9의 SAFE-022/023/024/025/030/031/034) / ADR-002-002 `INV-012`
cross-cite**에 앵커하고 **새 INV 시리즈를 창작하지 않는다**(#8 §0.4f와 동형 — #6이 SA-INV에 앵커한 것과 대비;
여기엔 앵커할 자체 INV가 없다).

**(g) RECON-EV = "0건 완결" shape (Time/#6/#7-형; #8/RCL과 정반대 — self-consistency 최우선).** #8은 STATE-EV-001
(`EV-L1/2`)·STATE-EV-003(`EV-L1/3`)이 register 최소 레벨에 EV-L1 슬라이스를 가져 **core tier**가 있었다. 본
문서의 RECON-EV는 **다섯 행 모두 최소 레벨 EV-L2 이상**(§1 실측)이라 **EV-L1 슬라이스가 0건**이다 — 따라서 §1
분류는 **core(L1 슬라이스) 없이 predicate-only / not-Phase-1 2분류**이고 "**RECON-EV 0건 완결**"이다. 이
판정은 §1·§5·§6·§7 전체에 걸쳐 **일관**해야 하며(어떤 §7 test-target도 core-tier나 RECON-EV closure를 주장하지
않음 — #8 C1 lesson 선제 봉합), finishing 전 self-consistency pass에서 대조한다.

---

## 1. 범위 매핑 — ADR-002-006 조항별 EV-L1 도달성 (RECON-EV 0건 완결)

EV-level 정의(VER-002-001): **EV-L1 = Model and Property Verification**(state-machine exploration, model
checking, property-based testing, deterministic simulation). **EV-L2 = Component Fault Test**, **EV-L3 =
Integration/Adversarial**, **+Broker = Broker Capability Profile evidence**. Phase 1은 EV-L1만이다.

> **결정적 사실 1 — core tier 부재("0건 완결" shape; #8/RCL과 정반대)**: `RECON-EV-001..005`(전부
> `Critical`, register line 96–100 실측)의 **register 최소 레벨은 다섯 행 모두 EV-L2 이상**이다
> (001=`EV-L2/3`·002=`EV-L3`·003=`EV-L2/3`·004=`EV-L2/3`·005=`EV-L3+Broker`). ⇒ **EV-L1 슬라이스가
> 0건**이므로 #8(STATE-EV-001=`EV-L1/2`·003=`EV-L1/3` core tier)·#5(RCLP-EV core)와 **다르고**, Time
> "TIME-EV 0건"·#6 "SA-EV 0건"·#7 "REARM-EV 0건"과 **같은 "0건 완결" shape**다. 분류는 **predicate-only /
> not-Phase-1 2분류**(NO core tier).
>
> **결정적 사실 2 — authoring ≠ acceptance(닫는 RECON-EV = 0건)**: Phase 1은 각 RECON-EV의 **L1-decidable
> predicate substrate**(빈-set⇒UNKNOWN·single-source⇒non-corroborated·conflict⇒widen·omission≠negative·
> freshness⇒STALE·field-specific proof bool)를 저작하나 **어떤 RECON-EV도 닫지 않는다.** (a) 최소 레벨이
> EV-L2/L3(+Broker)이라 fault injection·adversarial·broker-profile evidence가 필요하고, (b) VER-002-001 §5
> (ADR line 180 "Registration is not execution. A written test is not evidence") — 실행·아티팩트·독립
> 리뷰가 필요하다. ⇒ **"EV-L1-complete 주장 금지"**(설계 #2 §7·#4 §7·Time §1·#5 §1·#6 §1·#7 §1·#8 §1 규율
> 상속). Owner/Reviewer는 register상 TBD.

| RECON-EV | 제목 | register 최소 (line) | Phase-1 분류 | L1 predicate substrate (닫지 않음) | ADR 근거 |
|---|---|---|---|---|---|
| **-001** | Single Evidence-Path Corruption | `EV-L2/3` (96) | **predicate-only** | `classify_field`: 1 path 또는 **common-mode**(공유 parser/source/clock/transport로 sufficiently-independent 아님) ⇒ `CORROBORATED`/reconciled-proof **도달 불가**; 영향 필드는 conservative bound 유지·release 불가(§5.1/§6.1). **각 evidence-path 독립 corruption + common-mode corruption injection = EV-L2/3.** | AC-006-1 (174), §5 (73–80), §6 (92–95) |
| **-002** | Query Omission and Negative Evidence | `EV-L3` (97) | **predicate-only** | negative-evidence 술어: `is_absence` observation은 confidence만 낮추고 `NONE`/`CANCELLED`/`released` 확립·bound narrow·release-proof 생성 **불가**; 재출현 order의 economic effect 미폐기(§5.3). **hide-then-reappear across page/query/session/stream + pagination/history-window 변동 injection = EV-L3.** | AC-006-2 (175), §7 (102), ADR-002-002 §22.4 |
| **-003** | Conflicting Fill Quantity | `EV-L2/3` (98) | **predicate-only** | conflict ⇒ `CONFLICTED` + `merge_conservative`가 bound를 **union으로 widen(never average)**; (feeds) `QUARANTINED_UNKNOWN`; **no blended score·no preferred source**(§5.2/§5.3). **divergent cumulative-fill/remaining/position/correction from independent paths, multiple arrival orders injection = EV-L2/3.** | AC-006-3 (176), §5 (86), §7 (101), ADR-002-002 §22.2/22.3 |
| **-004** | Freshness and Time-Confidence Loss | `EV-L2/3` (99) | **predicate-only** | `freshness_ok`: past horizon ⇒ `STALE`; time confidence 상실 ⇒ fail closed — **[v1.2 에라타]** class는 `STALE`(v1.1 gloss `UNKNOWN`은 오기): previously-corroborated 필드의 time-loss는 "evidence는 있으나 time-신뢰 불가"이므로 `STALE`이 의미상 정확하고, ADR §7 line 103은 class를 지정하지 않고 fail-closed만 요구하며, release는 §6.1이 freshness를 독립 게이트하므로 어느 class든 차단(코드 리뷰 MINOR-2 확정); **new generation ⇒ old marker invalid(auto-refresh 불가)**(§6.3). **age past horizon + lose trustworthy time + restart receipt-anchor owner + restore time with new generation injection = EV-L2/3.** | AC-006-4 (177), §7 (103) |
| **-005** | Field-Specific Capacity Release Proof | `EV-L3+Broker` (100) | **predicate-only** | `field_reconciled_proof_ok`: capacity-releasing 필드(final filled qty·remaining executable qty)는 **CORROBORATED ∧ FQP(주입 token) ∧ freshness ∧ no-conflict**; weaker evidence(cancel ACK·terminal-without-qty·single-source·late correction) ⇒ **not ok**(§6.1/§6.2). **broker-profile-specific FQP content + cancel-ACK/terminal-status/single-source/late-correction sequence injection = EV-L3+Broker.** | AC-006-5 (178), §8 (112–121) |

**Phase-1 분류 요약**: **predicate-only(EV 주장 금지)** = {`RECON-EV-001`, `-002`, `-003`, `-004`, `-005`}
**(다섯 전부)**. **not-Phase-1** = **{ } (없음)** — 다섯 항목 모두 L1-decidable predicate substrate가
저작 가능하나 최소 레벨이 EV-L2+(005 +Broker)라 substrate만 저작하고 EV를 닫지 않는다. **core(L1 슬라이스)**
= **{ } (없음 — RECON-EV는 EV-L1 슬라이스 0건, §0.4g).** **닫는 RECON-EV = 0건 완결.**

> **규율 태그(모든 주장에 부착)**: "**predicate substrate only; RECON-EV-001..005 전부 NOT_IMPLEMENTED —
> EV-L2/L3(002=L3·005=L3+Broker) fault injection·adversarial·broker-profile evidence 대기. core tier
> 없음(EV-L1 슬라이스 0건). EV-L1-complete 주장 금지.**"
>
> **ADR-002-006 조항 → 모델 산출물 매핑**: §1 decision(per-field evidence·no blended) → §2·§4.1; §5
> per-field evidence(confidence class·conservative bound) → §2.2·§4.3·§5.1/§5.2; §6 corroboration/
> independence → §5.1/§5.3; §7 conflict/negative/freshness → §5.2/§5.3·§6.3; §8 proof rule → §6.1/§6.2;
> §9 triggers → §0.2(런타임 이연); §10 transition authority → §4.7(representation≠mutation, request-through-
> owner); §11 alternatives → §4.1(blended·broker-as-truth·midpoint·absence 기각을 구조로 실현); §13 AC-006-*
> → §7 하네스.

---

## 2. 데이터 모델 계약

**표현 원칙**: 모든 아티팩트는 **pydantic v2 frozen 모델**(`ConfigDict(frozen=True, extra="forbid")`,
`tos.canonical.FrozenModel` REUSE — `_base.py:73`)로 저작한다. frozen은 append-only(ADR §13 auditable·
reproducible; §15 replayable)의 레코드 수준 실현이며 **모델에는 update/delete 연산이 존재하지 않는다**(설계
#4 §2.0 규율 상속). enum 값·필드명은 ADR §5–§8의 용어를 그대로 쓴다(스펙 용어 = 코드 용어, 설계 #1 §2.4).

### 2.0 소유권 골격 — recon은 canonical의 하류, evidence/capsule의 상류-형제, orthostate/rcl의 upstream-형제

recon이 **소유·저작하는 것**은 per-field confidence 어휘(`FieldConfidenceClass`·`SafetyRelevantField`) +
`ConservativeBound`·`FieldConfidence` value + append-only `FieldReconciliationAssessment` 레코드 + corroboration/
conflict/negative-evidence/release-proof/freshness **술어**다. **소유하지 않는 것**: raw evidence retention·
custody·replay(ADR-002-016, scalar 참조만) · broker FQP 내용(ADR-002-004, 주입 token) · PTOL finality
recipe(ADR-002-030) · aggregate KnowledgeState transition(orthostate, produced-bool로만 공급) · capacity
mutation(rcl, release-proof bool로만 공급) · numeric horizon/tolerance(Verification Profile, 주입).

### 2.1 digest-bound / plain-frozen / value / reference 분류 (총괄)

| 아티팩트 | 종류 | id 필드(독립) | digest 필드 | covered / 내용 |
|---|---|---|---|---|
| `FieldReconciliationAssessment` (§1 line 15–24; §13 auditable) | **IndependentIdArtifact + 독립 id** | `assessment_id`(+`assessment_revision`) | `canonical_digest` | scope 참조(intent/reservation identity) + `tuple[FieldConfidence]` + version + trustworthy-time-snapshot 참조(§2.3) |
| `FieldConfidence` (§1 line 17–21의 per-field 구조) | **plain FrozenModel(value)** | — | — | `field`·`confidence_class`·`ConservativeBound`·contributing evidence-path 참조(provenance)·freshness marker |
| `ConservativeBound` (§5 line 82–86) | **plain FrozenModel(value)** | — | — | `lower: CanonicalDecimal\|None`·`upper: CanonicalDecimal\|None`(None⇒unbounded-conservative) |
| `EvidencePathObservation` (§6 line 92; 주입 입력) | **plain FrozenModel(injected)** | — | — | source 참조(evidence_id/gen/digest scalar)·independence-class(주입)·asserted `ConservativeBound`·freshness marker·`is_absence`(negative-evidence) |
| `ReleaseProofInputs` (§8; 주입 side-condition) | **plain FrozenModel(injected)** | — | — | `final_quantity_proof_token: bool\|None`(+Broker)·freshness flags·time-confidence·`time_generation` |
| `FieldConfidenceClass`·`SafetyRelevantField` (§5) | **StrEnum(로컬 값 타입)** | — | — | (assessment/observation의 covered 원소) |
| `CanonicalDecimal` (bound 수치) | **PROMOTE된 core `tos.canonical`** | — | — | (§0.4c — rcl에서 canonical로 이관 REUSE) |
| evidence / time-snapshot 참조 블록 | **plain FrozenModel(참조)** | id+generation+digest scalar | — | tos 미소유(ADR-002-016/004/008) |

> **`IdDerivedArtifact` 채택 아티팩트 = 0건. records substrate PROMOTE = 0건, numeric substrate PROMOTE
> = 1건(`CanonicalDecimal`, §0.4c).** `FieldReconciliationAssessment`는 reconciliation-run별 서비스-할당
> identity를 가진다 — same-id/diff-bytes 위조·재제출 탐지(`classify_record_pair`)에 id⊥digest 필수. ⇒
> `IndependentIdArtifact`(이미 core) 상속, `IdDerivedArtifact`(capsule 전용) 미채택. `tos.recon._base`는
> rcl/orthostate 동형의 thin re-export shim(신규 형제 edge 없음).

### 2.2 per-field 어휘 (verbatim 전사 — 에라타 defect class 주의)

> **전사 규율**: 아래 enum 값·설명은 ADR §5에서 **verbatim**이며, 다른 축(orthostate `KnowledgeState`·
> capsule `FieldState`)과 토큰을 공유하는 지점은 **별개 타입임을 명시**한다(#6/#7 비준후 에라타 defect
> class — 필드명·부등호 — 선제 방지).

**(1) `FieldConfidenceClass`(StrEnum) — ADR §5 (line 71–80), per-field evidence confidence 축.**
5종 verbatim(line 73–80):

```text
UNKNOWN        — no usable evidence; treat at maximum conservative bound
SINGLE_SOURCE  — one source only; usable only under a recorded, independently
                 accepted single-source residual (ADR-002-004; SAFE-023)
CORROBORATED   — >=2 sufficiently independent paths agree within tolerance
CONFLICTED     — independent paths disagree beyond tolerance
STALE          — previously sufficient, now older than the approved freshness bound
```

- **로컬 저작 근거(§0.4e, 좌표 비붕괴)**: `FieldConfidenceClass`는 **per-field evidence confidence** 축이며
  orthostate `KnowledgeState`(per-action aggregate: UNOBSERVED/CONSISTENT/CONFLICTED/RECONCILING/RECONCILED/
  QUARANTINED/STALE)·capsule `FieldState`(per-field context freshness: INVALID/CONFLICTED/STALE/UNKNOWN/VALID)와
  **별개 축**이다. `UNKNOWN`/`CONFLICTED`/`STALE` 토큰을 세 축이 공유하나(의도 — ADR가 per-field·per-action
  양쪽에서 사용) **재사용하면 축 붕괴**다. canary: `FieldConfidenceClass.CONFLICTED` ≠ `KnowledgeState.CONFLICTED`
  ≠ `FieldState.CONFLICTED`(§4.2). **주의**: `FieldConfidenceClass`에는 orthostate `RECONCILED`가 **없다** —
  per-field는 `CORROBORATED`까지가 최고 등급이고 aggregate `RECONCILED`는 orthostate 소관이다(§3.4 seam).
- **conservative bound 방향(§5 line 82–86 verbatim)**: risk decision은 field의 **conservative bound**를 쓴다 —
  upper bound for any adverse quantity(potential exposure·remaining executable quantity·external activity);
  lower bound only where a lower value cannot understate risk; **never a midpoint, average, or blended score**.
  (§4.3·§5.2에서 실현.)

**(2) `SafetyRelevantField`(StrEnum) — ADR §5 (line 55–67), "at least these" 최소 집합.** §5 line 55
"Reconciliation SHALL maintain independent evidence for **at least** these safety-relevant fields." ⇒ **비폐쇄
최소 집합**(over-claim 금지 — §5.4 규율과 동형). 명명 필드(line 57–67 verbatim, 2-column→pair 해석):

```text
order existence                                     broker order identity
cumulative filled quantity                          remaining executable quantity
position quantity                                   cash / margin / collateral
protective coverage                                 instrument identity
external / unattributed activity
post-trade obligation identity and version
settlement / cash availability / collateral eligibility
borrow / custody / transfer / legal-title state
statement coverage / break / correction / field-specific finality
```

- 첫 8개(order existence·broker order identity·cumulative filled quantity·remaining executable quantity·
  position quantity·cash/margin/collateral·protective coverage·instrument identity)는 **ADR-002-002 §22.1의
  8개 필드에 일대일 대응**한다(recon이 §22를 elaborate — 헤더). **주의(over-claim 방지)**: 대응이지 문자열
  동일이 아니다 — §22.1은 "broker-order existence"·"cumulative fill quantity"·"cash and margin"으로, ADR-002-006
  §5는 "order existence"·"cumulative filled quantity"·"cash / margin / collateral"로 미세 상이하게 표기한다
  (개념 일대일, 표기 ADR별). 나머지 5개(external/unattributed activity·PTOL identity/version·settlement·
  borrow/custody·statement coverage)는 recon이 confidence **모델**을 정의하되 finality recipe는 ADR-002-030
  소관(§0.2·§5 line 69).
- **capacity-releasing subset**(§8 line 114): `{cumulative filled quantity, remaining executable quantity}`
  — 이 두 필드의 RECONCILED proof rule만 FQP를 요구한다(§6.2).
- **비폐쇄 규율(over-claim 금지)**: `SafetyRelevantField`는 **ADR-002-006이 소유하는 명명 최소 집합**이며
  downstream ADR(002-030 등)이 확장할 수 있다. recon 술어는 **field-parametric**(집합이 닫혔다고 가정하지
  않음)이다. property는 명명 필드 각각을 회귀로 고정하되 "이것이 전체 legal 필드 집합"이라 주장하지 않는다.

**(3) `ConservativeBound`(plain FrozenModel value) — ADR §5 (line 82–86).**
`lower: CanonicalDecimal | None`, `upper: CanonicalDecimal | None`. **None ⇒ unbounded-conservative**:
`upper=None`은 "adverse quantity가 임의로 클 수 있음"(+∞ 최대 adverse)·`lower=None`은 "임의로 작을 수 있음"
(-∞ floor). 즉 None은 **가장 보수적(가장 넓은)** bound다(§4.3). **numeric score 필드 부재**(§4.1) — bound는
lower/upper Decimal 쌍뿐, 단일 점추정·평균·score가 없다.

**(4) `FieldConfidence`(plain FrozenModel value) — ADR §1 (line 15–22)의 per-field 구조.** field당:

- `field: SafetyRelevantField` — 대상 안전 필드.
- `confidence_class: FieldConfidenceClass` — §5 등급.
- `bound: ConservativeBound` — risk-usable conservative bound(§5 line 18).
- `contributing_path_refs: tuple[str, ...]` — 기여 evidence path + provenance 참조(§1 line 19, scalar — evidence
  클래스 미import, §3.5).
- `freshness_marker` — validity marker(§1 line 20, 주입 flag + `time_generation`; §6.3).
- **numeric confidence score 필드 없음**(§4.1 중앙 — no blended).

**(5) `EvidencePathObservation`(plain FrozenModel, 주입 입력) — ADR §6 (line 92).** 하나의 evidence path가
한 field에 대해 assert하는 관측(recon 술어가 fold하는 입력; #8 `CouplingSideConditions`가 주입 입력이었던 것과
동형):

- `field: SafetyRelevantField`.
- `source_ref: str | None` — evidence 레코드 scalar 참조(evidence_id/generation/digest; §3.5).
- `independence_class: str | None` — 이 path가 다른 path와 sufficiently independent한지의 **주입 판정**
  (§6 line 92 "single defect not expected to corrupt both in the same way"; 독립도는 hazard로 척도 — §6 line 95,
  Verification Profile 수치라 주입). common-mode(공유 parser/source/clock/transport)면 동일 independence-class로
  마킹돼 corroboration에 기여하지 못한다(RECON-EV-001).
- `asserted_bound: ConservativeBound` — 이 path가 assert하는 bound.
- `agrees_within_tolerance: bool | None` — 다른 path와 tolerance 내 일치 여부(§5 line 77; 주입 — tolerance는
  Verification Profile 수치). None ⇒ fail-closed(불일치 취급).
- `is_absence: bool` — 이 관측이 "이 query/page/session/stream에서 부재"인 negative evidence인지(§7 line 102).
  `True`면 confidence만 낮추고 terminal/released 확립·bound narrow 불가(§5.3).
- `freshness_marker` — 주입 freshness flag + `time_generation`.

**(6) `FieldReconciliationAssessment`(IndependentIdArtifact) — ADR §1/§13/§15.** reconciliation-run이 산출하는
append-only auditable 레코드:

- `assessment_id`(독립 id, ⊥digest) + `canonical_digest`.
- `scope_ref: str | None` — 대상 scope(intent identity / reservation identity 참조, scalar).
- `field_confidences: tuple[FieldConfidence, ...]` — per-field 결과(§1의 "for each safety-relevant field").
- `state_model_version` scalar + `trustworthy_time_snapshot_ref: str | None`(scalar) + `assessment_revision`
  (append-only 순서, §3.2).
- `_REQUIRED_COVERED`: 구조 identity/scope/version(numeric bound 아님 — Phase-1 null bound 하 ISSUED-reachable,
  rcl `records.py` 규율 동형; 누락 magnitude는 consuming 술어에서 fail-closed).

### 2.3 covered + self-exclusion (설계 #4 §3.3 상속)

`FieldReconciliationAssessment`의 covered(Layer-1) = scope_ref + field_confidences + version + time-snapshot
참조. preimage 제외: `assessment_id`·`canonical_digest`·`canonicalization_version`·`status`(ArtifactStatus
lifecycle 마커)·ledger 배치 시 결정되는 `assessment_revision`. **TBD/null이 covered에 하나라도 있으면
pre-issuance(status=DRAFT), digest 불가**(`_base.py:174` 부근). `assessment_id` ⊥ `canonical_digest`(§3.1).

> **핵심 설계 결정 — assessment는 append-only, 정정은 새 assessment(#8 §2.3 lifecycle-out-of-collision 상속)**:
> reconciliation은 트리거마다 반복 실행되며 per-field confidence는 evidence 축적에 따라 전이한다(예:
> `SINGLE_SOURCE`→`CORROBORATED`, 또는 `CORROBORATED`→`CONFLICTED`). 정당한 재평가를 same-id/diff-bytes
> `CRITICAL_CONFLICT`로 오탐하지 않도록 **각 reconciliation-run은 fresh `assessment_id`를 가진 immutable
> append-only 레코드**다. same `assessment_id` + diff bytes ⇒ `CRITICAL_CONFLICT`(위조·재제출만); 정당한
> 재평가 ⇒ **새 assessment(새 id)**. 순서는 `assessment_revision`(§3.2 ordering)로 담는다.

---

## 3. canonical / ordering REUSE + orthostate/rcl(produced-bool seam) + evidence/capsule/time 경계

### 3.1 canonical REUSE + `id=f(digest)` 미채택 (설계 #4·#5·#6·#7·#8 §3.1 상속)

`FieldReconciliationAssessment`는 `tos.canonical.IndependentIdArtifact`(`_base.py:328`)·`DigestBoundArtifact`
(digest 검증 `canonical_digest == H_ver(canonicalize(covered))`, `_base.py:98`)를 REUSE한다. canonicalizer는
`tos.canonical` registry + `EVL1ProvisionalCanonicalizer`(`ev-l1-provisional-0`) REUSE, **신규 canonicalizer
없음**(프로덕션 canonical form은 Phase-0, §9.2). **`id=f(digest)`(`IdDerivedArtifact`) 미채택**: §2.1 근거
(assessment는 서비스-할당 identity + same-id/diff-bytes 위조 탐지 — `classify_record_pair`, `record_pair.py:52`,
`RecordPairKind.CRITICAL_CONFLICT`). **records substrate PROMOTE = 0건**(IndependentIdArtifact·
classify_record_pair 이미 core). **numeric substrate PROMOTE = 1건**: **`CanonicalDecimal`(+ `_normalize_decimal`)
을 `tos.rcl.vector`에서 `tos.canonical`로 이관**(§0.4c) — `_num_token`(`canonicalization.py:78`)의 companion·
자기완결 primitive라 clean-atom PROMOTE.

### 3.2 ordering REUSE (assessment append-only 순서)

reconciliation assessment의 append-only 순서는 신규 저작하지 않고 `tos.ordering`(Trustworthy Time 설계 §5로
PROMOTE 완료; 코드 `tos/src/tos/ordering/`)의 `Ordering`·`OrderingEvent`·`compare_order`를 REUSE한다.
`assessment_revision`은 committed assessment 순서를 담는다. **wall clock은 순서를 만들지 않는다**(`tos.ordering`
규율) — recon은 clock을 읽지 않는다(§3.5). light REUSE(core 의존, 신규 edge 아님).

### 3.3 REUSE 요약 표

| substrate | 결정 | 근거 |
|---|---|---|
| `FrozenModel`·`DigestBoundArtifact`·`IndependentIdArtifact`·`ArtifactStatus` | **REUSE(core `tos.canonical`)** | §3.1; 신규 없음 |
| `classify_record_pair`·`RecordPairKind` | **REUSE(core, 이미 PROMOTE됨)** | §3.1; same-id/diff-bytes |
| `Ordering`·`OrderingEvent`·`compare_order` | **REUSE(core `tos.ordering`)** | §3.2; assessment 순서 |
| `CanonicalDecimal`(+`_normalize_decimal`) | **PROMOTE `tos.rcl.vector` → `tos.canonical` 후 REUSE** | §0.4c/§3.1; clean-atom, `_num_token` companion |
| `FieldConfidenceClass`·`SafetyRelevantField`·`ConservativeBound`·confidence 술어 | **로컬 저작** | §0.4e; ADR §5–§8 verbatim·decision-side |
| aggregate `KnowledgeState` transition·capacity release | **미소유 — produced-bool로만 공급** | §3.4; orthostate/rcl seam |
| raw evidence retention·broker FQP 내용·PTOL finality·numeric bound | **미소유 — scalar 참조·주입 token/flag** | §3.5; ADR-002-016/004/030/Profile |
| PROMOTE | **1건(`CanonicalDecimal`)** | §0.4c |

### 3.4 orthostate/rcl 경계 — produced-bool seam, sibling edge 0건 (중심 결정)

**(a) recon = 주입-플래그 producer(§0.4b).** recon은 `tos.orthostate`·`tos.rcl`을 **import하지 않고**, 그들이
소비할 **plain bool**을 생산한다. seam 계약(compose):

| recon 산출 (§6) | 타입 | 소비처 (이미 비준·구현) | 소비 signature |
|---|---|---|---|
| `field_reconciled_proof_ok(field, ...)` | `bool` | orthostate `knowledge_transition_allowed` | `corroboration: bool\|None` ∧ `final_quantity_proof_where_broker_involved: bool\|None`(`orthostate/predicates.py:502–503`) |
| `field_specific_release_proof_ok(field, ...)` | `bool` | orthostate CPL-2 · rcl INV-007 | `CouplingSideConditions.final_quantity_proof`(`orthostate/state.py:44`) · `transition_allowed(.., FINAL_QUANTITY_PROOF)`(`rcl/predicates.py:467`) |
| `freshness_lost(field, ...)` | `bool` | orthostate `knowledge_transition_allowed` | `freshness_lost: bool\|None`(`orthostate/predicates.py:504`) |
| `any_field_conflicted(scope)` | `bool` | (CPL-5 antecedent — Knowledge CONFLICTED) | orthostate coupling 입력 |

- **타입 정합 + fail-closed 정합**: recon 출력은 `bool`, 소비 signature는 `bool|None`(None⇒fail-closed). recon이
  판정 불가 시 caller가 `None`을 전달하거나 recon이 보수적 `False`를 반환하면 양쪽 모두 fail-closed다 — seam이
  **안전하게 조립**된다.
- **composition(런타임 배선) = caller 소관**: recon 출력 bool을 orthostate 주입 플래그로 배선하는 **런타임**은
  **미래 Reconciliation Service**(EV-L2/3)가 한다. Phase 1은 #8의 time-seam 이연과 **동형으로 런타임 배선을
  이연**한다.
- **seam cross-check = MANDATED(m2)**: 단, Phase 1은 **test-only** 모듈(`tos/tests/recon/test_seam_orthostate.py`
  류)에서 recon·orthostate를 **둘 다 import**해 recon 산출 bool의 **의미·polarity·fail-closed 거동**이 orthostate
  `knowledge_transition_allowed`의 주입-플래그 기대(`orthostate/predicates.py:502–504`: `corroboration` ∧
  `final_quantity_proof_where_broker_involved` ⇒ `RECONCILED`; `freshness_lost` ⇒ `STALE`)와 **일치함을 assert
  한다**(예: recon `field_reconciled_proof_ok`=True ⇒ orthostate가 `corroboration=True`·`fqp=True`로 RECONCILED
  전이 허용; recon `freshness_lost`=True ⇒ `freshness_lost=True`로 STALE 전이 허용; recon `any_field_conflicted`
  polarity). **이 테스트는 package edge가 아니다** — 테스트 import는 §7.1 `import tos.recon` package-closure에
  **계상되지 않으므로** recon 런타임 패키지의 sibling-edge-0건은 유지된다(#8이 seam을 이연만 한 것에서 한 걸음
  나아가 seam 정합을 능동 회귀로 고정 — v1.1 강화).
- **cycle 부재**: recon↛orthostate ∧ orthostate↛recon(#8은 confidence를 주입 flag로 소비). recon↛rcl(§0.4c
  PROMOTE로 CanonicalDecimal도 canonical에서). acyclic 명백.

**(b) recon은 capacity를 release하지 않는다(ADR §10 line 147).** recon은 release **proof bool**만 생산하고
capacity mutation 메서드가 **부재**하다(§4.7). rcl INV-007(`transition_allowed`의 `RELEASED` ← `FINAL_QUANTITY_
PROOF` cause only)이 그 bool을 소비해 실제 release를 gate한다 — recon "MAY provide evidence for a defined
capacity transition but SHALL NOT overwrite the Ledger ... or free capacity because one source omits an
order"(§8 line 121).

**(c) 운영자 판단 지점**: (i) recon↔orthostate seam을 **plain-bool decoupled(edge 0건)**로 둘지 대안 A(네 번째
edge)로 갈지 — decoupled 권장(§0.4b); (ii) `CanonicalDecimal` **PROMOTE `tos.canonical`** 승인 vs fallback
(rcl additive 재노출 + recon→rcl edge) — PROMOTE 권장(§0.4c). Fallback 채택 시 §7.1이 `tos.rcl` 존재를 허용
대상으로 기록하고 recon은 네 번째 sibling edge를 진다.

### 3.5 evidence / capsule / time / authority 경계 — 형제/상하류, scalar·주입 좌표만, import 금지

§0.4e대로: **`tos.evidence` 미import**(recon = decision-side 상류; evidence store = 하류 투영 — layering 역전
금지; retention/replay는 ADR-002-016); evidence path는 scalar(evidence_id/gen/digest) 참조. **`tos.capsule`
미import**(`FieldState`는 per-field context freshness 축 — recon per-field evidence confidence 축과 별개; 좌표
비붕괴). **`tos.time` 미import**(freshness numeric horizon = Verification Profile 소관(ADR §4 line 49·§14 line
186)이므로 **주입 opaque flag**(`fresh_within_horizon: bool|None`, None⇒STALE-보수) + `time_generation: int|None`
scalar로만 담음 — time service new-generation 복구 시 old marker 무효화(§6.3); rcl·orthostate가 time 미import한
선례 동형). **`tos.authority`·`tos.liveauth` 미import**(Reconciliation Service ownership은 orthostate §12 role
label; authority-epoch은 freshness 주입 flag). **`tos.orthostate`·`tos.rcl` 미import**(§3.4 produced-bool seam).
§7.1 import-closure가 이 부재를 assert한다.

---

## 4. 불변식

모두 frozen 모델 구성-불변식(구성 실패) 또는 순수 술어(property)로 실현한다. **fail-closed discipline**: 빈/
누락에 대한 술어는 절대 vacuous True/CORROBORATED/reconciled가 되지 않으며, 보수성은 *양성 증명*을 요구하고,
각 가드에 **negative/canary property**(가드가 실제로 발화함)를 붙인다.

### 4.1 no-blended-release 구조 불변식 (중앙 — ADR §1/§5/§7/§11; ADR-002-002 §22.2)

**중앙 결정**: "aggregate/blended confidence 점수가 acceptable해서 risk release/authorize"가 **구조적으로 표현
불가**하다. 실현(구조적 부재 3중):

1. **numeric confidence score 타입 부재**: recon 전체에 `score: float`·`confidence: float`·`aggregate_confidence()
   -> number` 같은 **수치 신뢰도 타입/함수가 존재하지 않는다.** confidence는 오직 `FieldConfidenceClass`(enum) +
   `ConservativeBound`(lower/upper Decimal 쌍)로만 표현된다. ADR §1 line 15 "not as a single blended confidence
   score"·§5 line 86 "never a midpoint, average, or blended score"·ADR-002-002 §22.2 "no optimistic midpoint or
   blended confidence score for release"를 타입 수준으로 실현.
2. **release/reconcile 술어는 per-field proof만 입력**: `field_reconciled_proof_ok`·`field_specific_release_proof_
   ok`는 **개별 field의 class·bound·proof token**만 받고, "여러 field를 하나의 수로 접는" 입력 경로가 **없다.**
   여러 field를 gate할 때도 **각 field를 개별 판정**(conjunction)하고, 한 field라도 미달이면 전체 미달 — 평균/
   가중합 부재.
3. **averaging 함수 부재, merge는 union만**: conflict 시 `merge_conservative`(§5.2)는 **가장 넓은 envelope
   (union)**를 산출하고 **midpoint/average를 산출하는 코드가 없다.**

**canary(both-ways, 구조적)**: (a) 시도 — "blended score로 release"를 표현하려면 존재하지 않는 타입/함수를
호출해야 하므로 **타입 에러**(구성 불가); (b) property — 임의 per-field confidence 집합에서 한 capacity-releasing
field가 CORROBORATED 미만이면 `field_specific_release_proof_ok`가 다른 field가 아무리 강해도 **False**(aggregate가
가려주지 못함, ADR §2 line 32 "release ... when the aggregate number looks acceptable while a specific field is
dangerously wrong" 방지).

### 4.2 좌표 비붕괴 (per-field evidence ≠ per-action knowledge ≠ context freshness) — #6 §4.7·#8 §0.4e 상속

- **세 별개 축**: recon `FieldConfidenceClass`(per-field evidence confidence) / orthostate `KnowledgeState`
  (per-action aggregate) / capsule `FieldState`(per-field context freshness). 공유 토큰(`UNKNOWN`/`CONFLICTED`/
  `STALE`)은 **의도**(ADR가 per-field·per-action에서 같은 단어 사용)이나 **별개 타입**이다.
- **비붕괴 성립 방식(주의 — #8과 다름)**: #8의 dimension-swap canary는 **전역 string 값 구분**에 의존했으나 recon
  축은 다른 두 축과 string 값을 **공유**한다. 따라서 recon의 비붕괴는 (i) **타입 구분**(별개 StrEnum 클래스) +
  (ii) **미import**(recon은 orthostate/capsule을 import하지 않아 swap 자체가 원천 차단)로 성립한다. canary:
  document-level 회귀로 `FieldConfidenceClass.CONFLICTED is not KnowledgeState.CONFLICTED`(타입 identity)를
  고정(둘 다 import하는 test-only 모듈에서). `FieldConfidenceClass`에 `RECONCILED` 부재(aggregate 전용)를 회귀.
- **미래 설계에 대한 coordination 의무(m3)**: recon이 토큰 overlap(`CONFLICTED`/`STALE`/`UNKNOWN`을 세 축이 공유)을
  도입하므로, **`KnowledgeState`/`FieldState`-typed 필드와 `FieldConfidenceClass`-typed 필드를 동시에 담는 FUTURE
  패키지는 이 둘을 반드시 별개 typed 필드로 유지**해야 한다(공유 raw-string slot 금지). raw `"CONFLICTED"`/
  `"STALE"`/`"UNKNOWN"`을 하나의 `str` slot에 담으면 StrEnum coercion이 그 값을 **어느 축으로든 받아들여** 축 붕괴가
  재발한다. 이는 recon이 여기 기록하는 **후속 설계에 대한 coordination 의무**다(본 계약은 세 축을 import하지 않아
  자체로는 안전하나, overlap의 출처이므로 명시).

### 4.3 conservative bound 단조성 — uncertainty widens, never narrows without proof (§5 line 82–86; §8 line 121)

- **방향 규칙(§5 line 84–86)**: adverse quantity는 **upper bound**; lower bound는 "a lower value cannot
  understate risk"인 경우만; **never midpoint/average/blended**.
- **widen 자유, narrow는 양성 증명 요구(§8 line 121 "reducing conservatism requires stronger proof than
  increasing it")**: `bound_narrowing_allowed(from_bound, to_bound, basis) -> bool` — to ⊆ from(narrow)은
  **strong basis**만 허용; widen(to ⊇ from)·hold는 임의 basis 허용; **basis None ⇒ fail-closed(narrow 불가)**.
  (#8 conservative-direction·rcl `transition_allowed` 정신 동형.)
- **uncertainty ⇒ widen**: `UNKNOWN`(no usable evidence) ⇒ **maximum conservative bound**(§5 line 74) =
  unbounded(upper=None, §2.2). conflict ⇒ merge union widen(§5.2).

### 4.4 empty/absence fail-closed — no vacuous confidence, omission ≠ negative (§5 line 74; §7 line 102; RECON-EV-002)

- **빈 evidence set ⇒ UNKNOWN**: 0 usable path ⇒ `classify_field` = `UNKNOWN`(max conservative bound), **절대
  vacuous `CORROBORATED`/reconciled-proof-ok 아님.** canary(both-ways): 빈 입력 ⇒ UNKNOWN(가드 발화); ≥2
  independent-agree ⇒ CORROBORATED(양성 side).
- **omission ≠ negative evidence**: `is_absence=True` observation은 confidence만 낮추고 **`NONE`/`CANCELLED`/
  `released` terminal 확립·bound narrow·release-proof 생성 불가**(§7 line 102; ADR-002-002 §22.4 "Order absence
  from one query, page, session, or event stream is not proof of non-existence"). canary: absence-only 입력 ⇒
  bound narrow 0·release-proof False·terminal 상태 미도달.

### 4.5 single-source ceiling — below release grade, 구조적 (§5 line 75; §6 line 94; SAFE-023)

- 1 path ⇒ `SINGLE_SOURCE`, **`CORROBORATED` 도달 불가**(source가 아무리 "confident"해도). CORROBORATED는
  **≥2 sufficiently-independent paths**를 요구하므로(§6 line 93) 1 path로는 술어상 도달 불가. release grade
  (§6.1 CORROBORATED 요구)에 미달. canary: 1 path ⇒ 절대 CORROBORATED 아님(both-ways: 2 independent ⇒ CORROBORATED).
- **"corroboration infeasible 단독 선언" 금지(§6 line 94 "A proposing component SHALL NOT unilaterally declare
  corroboration infeasible")**: recon에 "corroboration 불가하니 single-source를 release-grade로 승격" 경로가
  **부재**하다 — SINGLE_SOURCE residual 승인은 주입(recorded, independently reviewed, SAFE-023)이고 recon이
  자체 생성하지 않는다.

### 4.6 append-only + same-id/diff-bytes 충돌 (§13; §2.3)

모델에 update/delete 연산 부재(§2.0). assessment 재평가·정정은 새 assessment의 append로 표현. same
`assessment_id` + diff canonical digest ⇒ `classify_record_pair` = `CRITICAL_CONFLICT`(contain 양쪽 보존, no
last-write-wins). property: id⊥digest이므로 CRITICAL_CONFLICT reachable(가드 발화); id=f(digest)면 unreachable
임을 회귀로 고정(§3.1).

### 4.7 representation ≠ mutation (ADR §10 line 144–149; §8 line 121)

`FieldReconciliationAssessment`·confidence·bound·proof bool은 **비전송·비-mutating representation**이다 —
"filled quantity CORROBORATED" 기록이 capacity를 release하지 않는다. ADR §10 line 147 "requests defined
Ledger/capacity transitions through the owning authority; it cannot mutate capacity directly"; line 149 "SHALL
NOT release capacity or declare RECONCILED outside these rules." ⇒ recon에 **capacity mutate·Ledger overwrite·
aggregate-KnowledgeState set 메서드가 부재**(구성적 부재 — 설계 #5 capacity≠authority·#8 representation≠effect
정신 동형). recon은 proof bool을 **반환**할 뿐 소유 authority(RCL/orthostate)가 전이를 수행한다. 이 불변식이
evidence(하류 투영) 미import(§3.5)의 근거이기도 하다.

---

## 5. confidence 분류 · corroboration · conflict · negative-evidence 술어 세부 (RECON-EV-001/002/003 substrate)

**핵심 난제**: `classify_field`·`merge_conservative`를 **순수 함수**로 저작하되, (i) independence·tolerance를
**주입 판정**으로 두어 하드코딩 수치를 배제하고(§8), (ii) **no-blended(§4.1)를 구조로** 지키며, (iii) 빈·single·
absence를 **fail-closed**로 처리한다(§4.4/§4.5).

### 5.1 classify_field (§5 line 73–80; §6 line 92–95 — RECON-EV-001 substrate)

`classify_field(observations: tuple[EvidencePathObservation, ...], freshness_marker) -> FieldConfidenceClass`
(`freshness_marker`는 주입 — §2.2/§6.3; "previously sufficient" 전제는 caller가 이 marker로 공급):

| 입력 조건 | 산출 class | 근거 |
|---|---|---|
| usable path 0개 | `UNKNOWN`(max conservative bound) | §5 line 74; §4.4 |
| usable path 1개 | `SINGLE_SOURCE` | §5 line 75; §4.5(CORROBORATED 도달 불가) |
| ≥2 **sufficiently-independent**(distinct independence_class) 且 pairwise **agree within tolerance** (且 not aged) | `CORROBORATED` | §5 line 76·§6 line 93 |
| independent paths **disagree beyond tolerance** | `CONFLICTED` | §5 line 77·§7 line 101 |
| previously-sufficient field가 past freshness horizon(주입 `freshness_marker` aged) — **≥2-independent-agree여도 STALE이 CORROBORATED에 우선(m1)** | `STALE` | §5 line 78; §6.3 |

- **independence는 주입**(§6 line 92/95): 두 path의 "sufficiently independent"(single defect가 둘을 같은 방식으로
  corrupt하지 않음)는 `independence_class`로 주입되고, **hazard severity로 척도**(§6 line 95 — Verification
  Profile 수치)라 recon이 자체 계산하지 않는다. **common-mode**(공유 parser/source/clock/transport, RECON-EV-001
  injection)면 동일 independence_class ⇒ "≥2 distinct independent" 미충족 ⇒ CORROBORATED 불가.
- **tolerance는 주입**(§5 line 76): `agrees_within_tolerance` 플래그(pairwise). None ⇒ fail-closed(불일치 취급).
- **fail-closed**: 판정 불가·flag None ⇒ 보수 class(UNKNOWN/CONFLICTED 쪽), 절대 CORROBORATED로 승격 안 함.
- **canary(RECON-EV-001)**: 2 path이나 **동일 independence_class**(common-mode) ⇒ CORROBORATED 아님(단일/공통-모드
  corruption이 CORROBORATED 확립 불가 — VER §105 Expected).
- **STALE 우선순위 확정(m1)**: `classify_field`는 주입 `freshness_marker`를 소비하며 "previously sufficient" 전제는
  **caller가 그 marker로 공급**한다(§2.2·§6.3). observation이 동시에 **≥2-independent-agree AND aged**(marker가
  past-horizon)이면 **STALE이 CORROBORATED에 우선**한다(§5 line 78 "previously sufficient, now older than the
  approved freshness bound" — freshness 상실이 corroboration을 override; 구현 결정성을 위해 class precedence를
  STALE로 pin). **두 해석(STALE 우선 / CORROBORATED 우선) 중 어느 쪽이든 release는 fail-closed로 동일**하다 — §6.1
  proof rule이 corroboration과 **독립적으로** freshness를 요구하기 때문이다(ADR §8 line 117 verbatim "freshness
  within the approved bound; AND" — §6.1 verbatim 블록에 전사; §6.1 조건 (c) `freshness_ok(...)`) — aged field는
  어느 class든 release-proof를 통과하지 못한다. **canary(§7)**: aged + ≥2-independent-agree ⇒ `classify_field` =
  `STALE`(not CORROBORATED).

### 5.2 merge_conservative (§5 line 82–86; §7 line 101 — RECON-EV-003 substrate)

`merge_conservative(a: ConservativeBound, b: ConservativeBound) -> ConservativeBound`: **가장 넓은 envelope
(union)**:

- `upper = max(a.upper, b.upper)` — 단, **None이 지배**(None = +∞, 가장 adverse). 즉 어느 한쪽이 unbounded면 결과도
  unbounded.
- `lower = min(a.lower, b.lower)` — 단, **None이 지배**(None = -∞).
- **never average/midpoint**(§4.1/§5 line 86).

- **canary(RECON-EV-003)**: `merge_conservative(bound(100,100), bound(150,150))` ⇒ `upper=150, lower=100`
  (**not 125**). 즉 두 path가 filled=100 vs 150으로 conflict ⇒ conservative upper=150(max adverse), lower=100 —
  평균 125 아님. 이 field는 `CONFLICTED`가 되고 (feeds) Capacity `QUARANTINED_UNKNOWN`(§7 line 101; CPL-5). "no
  blended score or preferred source authorizes new risk"(VER §107 Expected).

### 5.3 corroboration / conflict / negative-evidence 술어 (§6·§7 — RECON-EV-002 substrate)

- `is_corroborated(field, observations) -> bool` = `classify_field(...) is CORROBORATED`.
- `is_conflicted(field, observations) -> bool` = `classify_field(...) is CONFLICTED`. conflict resolution은
  **evidence 요구, convenient-source 선택 금지**(§7 line 101; ADR-002-002 §12 INV-012) — recon에 "선호 source
  선택" 경로 부재.
- **negative-evidence 술어(RECON-EV-002)**: absence(`is_absence=True`) observation은 (i) confidence를 낮출 수
  있으나 (ii) **`NONE`/`CANCELLED`/`released` 확립 불가**, (iii) **bound narrow 불가**, (iv) **release-proof
  생성 불가**. `classify_field`는 absence-only 입력에서 `UNKNOWN`/기존-보다-낮은 class를 산출하되 terminal을
  산출하지 않는다. 재출현 order(later query/fill)의 economic effect는 미폐기(§7 line 102; VER §106 Expected
  "reappearing order is reconciled without discarding its economic effect"). **canary**: absence 관측 추가가
  bound를 좁히거나 release-proof를 True로 만들면 실패(both-ways: 실제 positive observation은 정상 반영).

### 5.4 결정되지 않은 field·조합 — over-claim 금지 (충분조건 아님)

`SafetyRelevantField`는 **"at least these" 최소 집합**이고(§2.2), confidence class 판정은 명명 필드에 대한
**필요조건**이다. recon은 (i) 필드 집합이 닫혔다고 주장하지 않고(downstream 확장 가능), (ii) `is_corroborated`가
"이 field가 안전하다"가 아니라 "이 field가 CORROBORATED class"만 주장한다(release 여부는 §6.1 proof rule의
추가 조건 — FQP·freshness·no-conflict — 을 요구). #8 §5.4 over-claim 금지와 동형.

---

## 6. field-specific release proof · freshness 술어 세부 (RECON-EV-005/004 substrate)

### 6.1 field_reconciled_proof_ok — §8 generic contract (RECON-EV-005 substrate)

`field_reconciled_proof_ok(field, confidence, inputs: ReleaseProofInputs) -> bool` — ADR §8 line 112–118
generic contract:

```text
RECONCILED(field) requires:            (ADR §8 line 112-118 verbatim)
  - corroborating evidence sufficient for the field's hazard severity; AND
  - for capacity-releasing fields (final filled quantity, remaining executable
    quantity): Final Quantity Proof per the approved Broker Capability Profile
    (ADR-002-004), including the broker's late-fill / correction semantics; AND
  - freshness within the approved bound; AND
  - no unresolved conflict on the same field.
```

- 조건 4개 conjunction, 각 fail-closed: (a) `confidence.confidence_class is CORROBORATED`(SINGLE_SOURCE/UNKNOWN/
  STALE/CONFLICTED ⇒ False); (b) field ∈ capacity-releasing subset이면 `inputs.final_quantity_proof_token is
  True`(None/False ⇒ False; **+Broker 이연** — token 내용은 ADR-002-004 Broker Capability Profile, recon은 주입
  bool만); (c) `freshness_ok(...)`(§6.3); (d) `not is_conflicted(field, ...)`. **어느 하나라도 None/False ⇒
  False(fail-closed).**
- **hazard-severity 척도**(§6 line 95): "sufficient for the field's hazard severity"의 독립도 요구는 주입
  (Verification Profile). Phase 1은 CORROBORATED를 최소 요구로 하고 hazard별 강화는 주입 파라미터.
- 이 bool이 orthostate `knowledge_transition_allowed(corroboration=..., final_quantity_proof_where_broker_
  involved=...)`이 소비하는 값이다(§3.4).

### 6.2 field_specific_release_proof_ok — capacity-releasing 특화 (RECON-EV-005)

`field_specific_release_proof_ok(field, confidence, inputs) -> bool`: capacity-releasing field(`{cumulative
filled quantity, remaining executable quantity}`, §8 line 114)에 대해 §6.1의 full conjunction(FQP 포함)을
요구한다. weaker evidence 열거(VER §109 injection — 전부 not ok):

| weaker evidence | 왜 not ok |
|---|---|
| cancel ACK | terminal 아님·FQP 아님(§8; CPL-4 cancel≠release) |
| terminal status without quantity | FQP(final cumulative filled quantity + zero remaining) 미충족 |
| single-source query | SINGLE_SOURCE ⇒ CORROBORATED 미달(§4.5) |
| late correction (pending) | unresolved conflict / freshness 미확정 |
| **complete broker-profile FQP** | **유일하게 ok**(VER §109 Expected "Only the complete field-specific proof permits ... release") |

- recon은 이 bool을 반환할 뿐 **release를 수행하지 않는다**(§4.7). rcl INV-007(`transition_allowed`의 RELEASED ←
  FINAL_QUANTITY_PROOF cause)·orthostate CPL-2(`side.final_quantity_proof`)가 소비. "all weaker evidence
  preserves conservative commitment"(VER §109).
- **canary(both-ways)**: complete FQP token + CORROBORATED + fresh + no-conflict ⇒ True; 위 weaker 각각(또는 임의
  조건 None) ⇒ False.

### 6.3 freshness_ok — freshness / time-confidence (RECON-EV-004 substrate)

`freshness_ok(inputs: ReleaseProofInputs, marker_generation: int | None) -> bool` — ADR §7 line 103:

- `inputs.fresh_within_horizon is True` 요구(past horizon ⇒ False ⇒ 해당 field `STALE`, new risk authorize 불가).
- **time confidence 상실 ⇒ fail closed**: `inputs.time_confidence_held is not True`(예: 주입된 clock-drift가
  `MAX_clock_drift_ppm` 초과 — §8) ⇒ False(모든 time-dependent freshness fails closed, §7 line 103).
- **new generation ⇒ old marker 무효(RECON-EV-004 Expected "do not become current merely because time service
  recovers")**: `marker_generation != inputs.time_generation`(time service가 restart 후 new generation으로
  복구) ⇒ old marker는 **auto-refresh되지 않음** ⇒ False(fresh evidence로 재확립 필요). #7/#8 epoch-generation
  무효화 패턴 동형.
- **None ⇒ fail-closed**(any flag None ⇒ False).
- **`tos.time` 미import**(§3.5) — 전부 주입. numeric horizon 하드코딩 없음(§8).
- **canary(both-ways)**: fresh+time-held+same-generation ⇒ True; aged/time-lost/generation-changed/any-None ⇒ False.

---

## 7. property-test 하네스 타깃

§1 분류에 정렬 — **전부 predicate substrate, 닫는 RECON-EV = 0건**(core tier 없음, §0.4g). property는 bound·
tolerance·independence·freshness를 **hypothesis 생성 주입값**으로 다뤄 "임의 유효 주입 하 보수적 성립"을 검증
(특정 값 비의존, 하드코딩 없음 — §8).

| family | Phase-1 타깃 | substrate / 근거 |
|---|---|---|
| assessment canonicalization + digest 검증 | **REUSE 설계 #4 must-pass suite**(`tos.canonical`) | §2.3·§3.1; frozen digest 일관성 |
| **no-blended-release 구조** | **구조적 부재 + property** | §4.1. numeric score 타입/averaging 함수 **부재**(구성 시 타입 에러); 한 capacity-releasing field CORROBORATED 미만 ⇒ `field_specific_release_proof_ok`=False(aggregate 미가림) |
| `classify_field` (빈/single/≥2-independent/conflict/stale) | **predicate** | §5.1; RECON-EV-001. 빈⇒UNKNOWN·1⇒SINGLE_SOURCE·2-independent-agree⇒CORROBORATED·common-mode⇒**not** CORROBORATED(both-ways) |
| **STALE 우선순위 (m1)** | **predicate** | §5.1; RECON-EV-004. aged(past-horizon 주입 `freshness_marker`) + ≥2-independent-agree ⇒ `classify_field`=`STALE`(**not** CORROBORATED); release는 §6.1 freshness_ok가 corroboration과 독립 gate라 어느 해석이든 fail-closed |
| `merge_conservative` (conflict widen) | **predicate** | §5.2; RECON-EV-003. union(max/min, None 지배)·**never average**(100∧150⇒upper 150 not 125) canary |
| negative-evidence (omission ≠ negative) | **predicate** | §5.3; RECON-EV-002. absence ⇒ bound narrow 0·terminal 미도달·release-proof False(both-ways: positive는 반영) |
| single-source ceiling | **predicate** | §4.5; RECON-EV-001. 1 path ⇒ **절대 CORROBORATED 아님**; corroboration-infeasible 자체 승격 경로 부재 |
| `field_reconciled_proof_ok` / `field_specific_release_proof_ok` | **predicate** | §6.1/§6.2; RECON-EV-005. CORROBORATED∧FQP∧fresh∧no-conflict ⇒ True; weaker(cancel-ACK·terminal-no-qty·single-source·late-correction·any-None) ⇒ False(both-ways) |
| `freshness_ok` (horizon/time-loss/new-generation) | **predicate** | §6.3; RECON-EV-004. aged/time-lost/generation-changed ⇒ False; fresh+held+same-gen ⇒ True(both-ways); time 복구가 auto-refresh 안 함 canary |
| conservative bound 단조성 | **predicate** | §4.3. widen 자유·narrow는 strong basis만·None basis ⇒ narrow 불가(fail-closed) |
| append-only + same-id/diff-bytes | **REUSE core `classify_record_pair`** | §4.6; CRITICAL_CONFLICT reachable(id⊥digest) |
| representation ≠ mutation | **구성적 부재** | §4.7. capacity-mutate·Ledger-overwrite·aggregate-KnowledgeState-set 메서드 **부재** |
| 좌표 비붕괴 (3-axis) | **타입 identity 회귀(test-only)** | §4.2. `FieldConfidenceClass.CONFLICTED is not KnowledgeState.CONFLICTED`; `RECONCILED` ∉ `FieldConfidenceClass` |
| **seam cross-check (MANDATED, test-only) (m2)** | **cross-import 정합 회귀(test-only, NOT package edge)** | §3.4/§9.1. recon 산출 bool(`field_reconciled_proof_ok`/`freshness_lost`/`any_field_conflicted`)의 polarity·fail-closed가 orthostate `knowledge_transition_allowed`(`orthostate/predicates.py:502–504`) 주입-플래그 기대와 일치; §7.1 closure 무영향(test import) |

- **predicate-only** = {RECON-EV-001..005} 전부. **core(L1 슬라이스)** = **{ } 없음.** **닫는 RECON-EV = 0건**
  (§1 규율). bound·tolerance·independence·freshness는 hypothesis 주입, 하드코딩 없음(§8).
- **self-consistency 규율(C1 lesson)**: 위 어떤 family도 "RECON-EV core tier"·"RECON-EV closure"를 주장하지
  **않는다** — 전부 predicate substrate이며 §1 "0건 완결"·§5/§6 술어 정의와 정합한다(finishing 전 대조 완료 —
  §10.1).

### 7.1 import-closure 검증 테스트 (설계 #4 §7.1·#6·#7·#8 §7.1 상속)

서브프로세스에서 `import tos.recon`(및 `tos.canonical`·`tos.ordering`)만 한 뒤 `sys.modules`를 검사해 assert:
(1) 설계 #1 §2.3 금지 패키지 부재; (2) **`shared.config`·`shared.config.secrets` 부재**(전이 유입 런타임
포착); (3) `os.environ`/`os.getenv` 미참조; (4) **`numpy`·`pandas`·`yaml`(pyyaml) 부재**(bound/tolerance 주입·
YAML은 하네스 소관, §0.3); (5) **`tos.orthostate`·`tos.rcl`·`tos.time`·`tos.evidence`·`tos.capsule`·
`tos.authority`·`tos.liveauth`·`tos.dsl` 부재**(§3.4/§3.5 — 형제/상하류; produced-bool·scalar·주입 좌표로만
참조); (6) **`tos.canonical`·`tos.ordering` 존재 허용**(§3.1/§3.2 — core, sibling edge 아님). **PROMOTE fallback
채택 시(§0.4c)에만** `tos.rcl` 존재를 허용 대상으로 추가 기록(네 번째 sibling edge). required check(`tos-firewall`)와
함께 green이어야 §0.3 준수 선언이 능동 성립한다.

### 7.2 run manifest 정렬 (설계 #1 §5.1 7항목)

recon 전용 템플릿은 없으므로 설계 #1 §5.1 규율을 REUSE한다. evidence를 산출하는 모든 property-test run은:
(1) git commit digest + `tos` 버전; (2) 인터프리터 + 고정 의존성 버전(pydantic/hypothesis); (3) 실행 환경;
(4) 하네스 git digest; (5) **property-test seed**(hypothesis seed/derandomize, append-only); (6) **소비 설정
아티팩트 digest**(주입 RECON bound/tolerance/independence/freshness 프로파일 + `canonicalization_version` +
`tos.ordering` primitive 버전 + PROMOTE된 `CanonicalDecimal`을 포함한 `tos.canonical` 버전); (7) 산출 아티팩트
sha256. (VER-002-001 §2.3 재현성·§9.1 seed·§9.2 digest의 EV-L1 부분집합.)

---

## 8. bounds 주입 + 누락 프로파일 키 Phase-0

`VERIFICATION-PROFILE-002.yaml`은 전체 `status: PROPOSED`·`approved_by: []`·`effective_from: null`(배너
"an unapproved or placeholder bound is not an approved bound"). ADR-002-006 §4(line 49)·§14(line 186) "Numeric
tolerances, freshness horizons, and detection bounds belong in the Verification/Safety Profiles, not this ADR."

- **결정**: RECON 관련 수치(per-field freshness horizon·corroboration agreement tolerance·independence-degree-
  by-hazard·external-activity detection·startup reconciliation)는 **주입 policy 파라미터**로만 들어온다. **어떤
  숫자도 하드코딩하지 않는다**(CLAUDE.md). 값 누락 ⇒ fail-closed(§4.4 flag None⇒restrictive; §6.3 freshness
  None⇒STALE-보수).

- **실측 확인(evidence-based) — 프로파일에 존재하는 RECON-관련 키**(grep, 키 명으로 인용·line은 non-template
  참고):
  - `MAX_clock_drift_ppm`[700]: `200` / PROPOSED, "beyond this, time confidence is lost -> fail closed
    (ADR-002-003)". ⇒ **RECON-EV-004 time-confidence-loss의 기존 키**(§6.3, 재계상 없음).
  - `B_external_activity_detect`[184]·`B_external_activity_contain`[191]·`B_startup_reconciliation`[198]·
    `B_non_trade_reconcile`[660]: external-activity 탐지·reconciliation 시작/완료·non-trade reconcile 타이밍
    (ADR-002-006/010/017 관여; **latency=런타임 EV-L2/3**, §0.2). ⇒ RECON trigger(§9) 소관, **재계상 없음**.
  - `MAX_currentness_vector_age_ms`[724]: `null`, "unknown or stale vector age denies admission" — currentness
    vector 신선도(#8이 knowledge/reconciliation-staleness의 nearest로 지목한 키).
  - `B_stale_epoch_reject`[177]: `0` / PROPOSED, epoch staleness(ADR-002-002 INV-008/ADR-002-003) — authority-
    epoch currentness(freshness 주입 flag 근거).

- **누락 distinct 키 (Phase-0 Bounds-Approver 플래그)**: 실측 대조 결과 —
  1. **구조 조항(confidence class·conservative bound·corroboration·conflict·negative-evidence·proof rule)에는
     numeric bound 부재** — 전부 enum·boolean·집합 논리·Decimal 산술이라 승인할 숫자가 없다. ADR-002-006이
     도입하는 수치 의존은 §4 line 49·§14 line 186이 Verification/Safety Profile로 위임한 **tolerance·freshness
     horizon·detection bound**뿐이다.
  2. **#8 flag의 정밀화(신규 count 아님)**: #8 §8은 "knowledge/reconciliation-staleness"를 **ADR-002-006-의존
     Phase-0 candidate**로 flag하며 dedicated 키 여부를 본 문서로 이관했다. 본 문서(ADR-002-006 소유)는 그
     placeholder를 **ADR-002-006 bound family로 정밀화**한다:
     - **per-field freshness horizon**(§5 line 78·§7 line 103 STALE bound) — field/hazard별 dedicated 키 vs
       기존 `MAX_currentness_vector_age_ms` 재사용 여부.
     - **corroboration agreement tolerance**(§5 line 76 "agree within tolerance") — 전용 키 부재.
     - **independence-degree-by-hazard**(§6 line 95 "independence SHALL scale with hazard severity") — 전용 키 부재.
     이는 **#8 candidate의 refinement이지 신규 count가 아니다**(중복 계상 회피 — 설계 #4/#5/#6/#7/#8 §8 규율
     동형). 키 명명·값은 ADR §14 line 186대로 프로파일 소관이며 특정 키 명을 mandate하지 않는다.

  ⇒ **확정 신규 누락 distinct 키 0건 + Phase-0 candidate 1군**(ADR-002-006 bound family = freshness horizon ·
  agreement tolerance · independence degree — #8 placeholder의 정밀화). 기존 `MAX_clock_drift_ppm`·
  `B_external_activity_detect`·`B_startup_reconciliation`·`MAX_currentness_vector_age_ms`는 **재계상 없음**.
  Phase 1은 전부 **주입 opaque flag/파라미터**(§3.5)로 담는다. 값·키 승인은 Bounds-Approver 게이트(Live-Armer와
  분리 — IMPLEMENTATION-PLAN §3)의 소관이다. **대안 판독 인정(m4)**: agreement-tolerance·independence-degree 키를
  "확정 누락(confirmed-missing)"으로 볼 여지도 있다(현 프로파일에 전용 키가 실제 부재) — 본 문서는 ADR §14 line 186이
  키 정의를 Profile에 위임하므로 **candidate-vs-confirmed를 Bounds-Approver 판단으로 남긴다**. **이 구분은
  safety-neutral**하다: 어느 쪽이든 Phase 1은 주입 default가 fail-closed(값 부재/`None` ⇒ restrictive — §4.4/§6.3)라
  미승인 bound가 자동으로 permissive해지지 않는다. [SAFE-030 conservative UNKNOWN 정합]

---

## 9. 후속 작업 · Phase-0 인간 게이트 이관 항목

### 9.1 후속 구현 작업 (본 계약 위에서)

- **`tos/src/tos/recon/` 모델·술어·property·import-closure 테스트 저작**(§2–§7): 설계 #3(EV-L1 하네스)이
  property suite를 실행. `tos.canonical`(digest+id+classify+**PROMOTE된 CanonicalDecimal**) + `tos.ordering`
  (순서) REUSE, 신규 canonicalizer/ordering 없음. **sibling edge 0건**(orthostate/rcl/time/evidence/capsule/
  authority/liveauth/dsl 미import).
- **`CanonicalDecimal`(+`_normalize_decimal`)을 `tos.rcl.vector` → `tos.canonical`로 PROMOTE(구현 선행 소단계 —
  §0.4c)**: 순수 relocation(동작 보존). **back-compat 명시(m5, 실측 검증)**: PROMOTE sub-step은 **두 내부 rcl
  import site를 `tos.canonical` source로 갱신 MUST** — (i) 정의 site `tos/src/tos/rcl/vector.py`(현재 `:50` 정의·
  `:82` `CapacityComponent.magnitude` 사용): 정의를 canonical로 옮기고 vector.py는 `from tos.canonical import
  CanonicalDecimal`로 전환(`:82` 사용 유지); (ii) `tos/src/tos/rcl/records.py:29`(`from tos.rcl.vector import
  CanonicalDecimal, CapacityVector`): `CanonicalDecimal`을 `tos.canonical`에서 source. `tos.canonical` `__all__`에
  추가. **`rcl.vector`의 `CanonicalDecimal` re-export는 courtesy shim일 뿐 load-bearing 경로가 아니다**(rcl 자체
  코드는 canonical을 쓴다). recon도 canonical에서 import. **`tos/tests/rcl/test_rcl_digest.py`는 무영향**(`:16`이
  `CapacityComponent`·`CapacityVector`만 import — `CanonicalDecimal`은 `CapacityComponent.magnitude` 경유 간접;
  `:3` docstring의 `tos.rcl.vector.CanonicalDecimal` 언급은 shim으로 유효 유지). **rcl 스위트는 무변경 green 유지
  MUST.** **ratified rcl 접촉이므로 운영자 승인(§10.2).** Fallback: 불허 시 rcl additive 재노출 + recon→rcl edge
  (네 번째 sibling edge — 비권장).
- **의존 방향**: recon ⟸ `tos.canonical`·`tos.ordering`(둘 다 core). recon은 orthostate/rcl/time/evidence/
  capsule/authority/liveauth/dsl을 import하지 않음(produced-bool·scalar·주입 좌표만). acyclic 확인: canonical·
  ordering은 recon 미참조.
- **compose seam(§3.4): 런타임 배선 이연 + test-only cross-check MANDATED(m2)**: recon 출력 bool
  (`field_reconciled_proof_ok`·`field_specific_release_proof_ok`·`freshness_lost`·`any_field_conflicted`)을
  orthostate `knowledge_transition_allowed`·CPL-2·rcl INV-007 주입 플래그로 배선하는 **런타임**은 **미래
  Reconciliation Service**(EV-L2/3) 소관. 단 Phase 1은 **test-only cross-import 모듈**(recon·orthostate 둘 다
  import; `orthostate/predicates.py:502–504` 기대와 recon bool의 polarity·fail-closed 정합을 assert)을 **작성한다**
  (§3.4/§7). **이 test는 package edge가 아니다**(테스트 import는 §7.1 `import tos.recon` closure 무영향; recon
  런타임 sibling-edge-0건 유지).

### 9.2 Phase-0 인간 게이트로 넘기는 항목 (본 계약이 결정하지 않음)

1. **`CanonicalDecimal` PROMOTE(`tos.rcl.vector`→`tos.canonical`) 승인 + recon↔orthostate seam decoupled 유지**
   (§0.4b/§0.4c/§3.4/§10.2). Fallback(recon→rcl edge) 여부.
2. **프로덕션 canonical serialization·digest 알고리즘 선택**(설계 #4 §9.2 item 1과 동일 게이트):
   `ev-l1-provisional-0`·sha256은 비프로덕션.
3. **RECON-EV bound family 값·키 승인**(§8; ADR §14 line 186): per-field freshness horizon·corroboration
   agreement tolerance·independence-degree-by-hazard의 dedicated 키 여부·값 — Bounds-Approver ≠ Live-Armer.
   기존 `MAX_currentness_vector_age_ms`·`MAX_clock_drift_ppm`·`B_external_activity_detect` cross-ref.
4. **broker-specific Final Quantity Proof·evidence 내용**(ADR-002-004): capacity-releasing field의 FQP token의
   *양성 proof 내용*(late-fill/correction semantics 포함)은 Broker Capability Profile(승인, broker-agnostic
   capability class) 소관 — §6.1/§6.2의 주입 token.
5. **evidence persistence·custody·integrity·replay**(ADR-002-016): reconciliation evidence의 retention·gap-
   check·replay 메커니즘 — Phase 1은 assessment 모델만; Evidence Store를 reconciliation authority로 만들지
   않음(§15 line 198).
6. **PTOL finality recipe·field-specific finality**(ADR-002-030): PTOL/settlement/borrow/statement 필드의
   finality recipe — recon은 confidence 모델만, recipe 미결정(§0.2).
7. **aggregate KnowledgeState transition 판정**(ADR-002-005/orthostate): per-field confidence → per-action
   `RECONCILED`/`CONFLICTED`/`QUARANTINED` roll-up의 transition legality는 orthostate 소관 — recon은 produced-bool
   공급만(§3.4).
8. **reconciliation trigger orchestration + external-activity detection 런타임**(ADR §9 line 125–138): 트리거
   스케줄·latency·detection bound는 EV-L2/3(기존 `B_external_activity_detect`·`B_startup_reconciliation` 키);
   Phase 1은 assessment 결과 모델만.
9. **authority epoch 메커니즘**(ADR-002-003): authority-epoch currentness는 freshness 주입 flag; 실제 epoch/
   egress currentness는 authority/liveauth 런타임.
10. **Independent-Safety-Reviewer 지정 + §7 EV-L1 evidence 수용 서명**(저자 배제 — IMPLEMENTATION-PLAN §3).
    **닫는 RECON-EV 0건이므로 acceptance 서명 없음** — EV-L2/L3(+Broker) fault injection·adversarial·broker-
    profile evidence는 Phase B.
11. **`freshness_marker`의 "aged" 공급 = caller-side precondition(integration-scope; 리뷰어 open question)**:
    §5.1의 STALE 판정(m1)은 "previously sufficient" 전제를 주입 `freshness_marker`로 받는다. 미래 Reconciliation
    Service 런타임은 **이전에 assess된(previously-assessed) field에 한해서만** "aged" marker를 공급해야 한다 —
    한 번도 관측되지 않은 field에 aged marker를 주면 `UNOBSERVED`/`UNKNOWN`이어야 할 것이 `STALE`로 오분류될 수
    있다(Phase 1은 fail-closed라 안전측이나 의미가 부정확). 이는 recon 순수 모델 밖의 **caller-side 계약**이며
    integration(EV-L2/3)에서 검증한다. Phase 1 property는 marker를 hypothesis 주입으로 다뤄 두 경우 모두 보수적
    성립을 확인한다.

---

## 10. 개정 로그 + 비준 체크리스트

### 10.1 개정 로그

- 2026-07-25: **v1.0 초안 최초 작성.** ADR-002-006 EV-L1 실현 계약. 설계 #1(경계·firewall)·#2(주입 flag·좌표
  어휘)·#4(canonical substrate + id⊥digest)·#5(rcl per-field bound 선례·CanonicalDecimal·INV-007)·#6(좌표 비붕괴)·
  #7(lifecycle-out-of-collision·sibling-edge 선례·주입 flag)·#8(**Knowledge 차원 소비자·produced-bool seam**·
  freshness 주입·bounds under-report 규율)에 정렬. 주요 결정: (§0.4a) 전용 패키지 `tos/src/tos/recon/`
  (`tos.confidence`/`tos.reconciliation` 기각, `tos.evidence`는 이미 존재하는 하류 store — register prefix
  `RECON-EV`·ADR §10 "Reconciliation Service" 앵커); (§0.4b/§3.4) **recon↔orthostate seam = plain-bool
  producer, sibling edge 0건** — recon이 orthostate `knowledge_transition_allowed`가 소비하는 corroboration/FQP/
  freshness 플래그의 상류 producer(ADR-002-005 §8 line 128 "ADR-002-006 will define the confidence
  representation"); 대안(recon→orthostate 네 번째 edge / orthostate→recon 역전) 기각(#8이 이미 주입 flag로
  봉인·edge/cycle 회피); (§0.4c/§3.4) **`CanonicalDecimal`을 `tos.canonical`로 PROMOTE**(clean-atom, `_num_token`
  companion) — recon↔rcl sibling edge 회피; 대안(rcl 내부 import / 로컬 재정의 / rcl additive 재노출+edge) 기각;
  **PROMOTE = 1건**(records substrate 0 + numeric substrate 1); #8의 CapacityState PROMOTE 기각과 정반대인 이유
  (CanonicalDecimal는 자기완결, CapacityState는 lattice 결부); (§0.4d/§3.1) canonical REUSE + `id=f(digest)`
  미채택; (§0.4e/§3.5) evidence(하류 투영·layering)·capsule(다른 축)·time(freshness 주입)·orthostate/rcl(produced-
  bool)·authority/liveauth(role) **미import**; (§0.4f) **INV 시리즈 창작 금지**(ADR엔 AC-006-*·RECON-EV만, INV-
  2건은 ADR-002-002 INV-012 cross-cite — 실측), RECON-EV/AC-006/§-clause/SAFE 앵커; (§0.4g/§1) **RECON-EV "0건
  완결" shape**(register 최소 레벨 다섯 행 전부 EV-L2+ — EV-L1 슬라이스 0건 — #8/RCL의 core-tier와 **정반대**·
  Time/#6/#7 동형; predicate-only/not-Phase-1 2분류, core tier 없음) but **닫는 RECON-EV 0건**(authoring≠evidence);
  (§2) `FieldReconciliationAssessment` = IndependentId+독립 id, per-field `FieldConfidence`(class+bound), append-
  only; (§2.2) confidence class(5종)·conservative bound·SafetyRelevantField("at least these" 비폐쇄)·proof rule
  **verbatim 전사**; (§4.1) **no-blended-release 구조 불변식**(중앙; numeric score 타입 부재·averaging 함수 부재·
  per-field-only 입력 — blended-release 구조적 표현 불가); (§4.2) 3-axis 좌표 비붕괴(FieldConfidenceClass ≠
  KnowledgeState ≠ FieldState; #8과 달리 string 공유라 타입+미import로 성립); (§4.3) conservative bound 단조성
  (widen 자유·narrow 양성 증명·None⇒unbounded); (§4.4/§4.5) empty⇒UNKNOWN·omission≠negative·single-source ceiling;
  (§4.7) representation≠mutation(capacity mutate 메서드 부재); (§5) classify_field·**merge_conservative union
  (never average)**·negative-evidence; (§6) field-specific release proof(FQP 주입·+Broker 이연)·freshness(new-
  generation 무효화, time 주입); (§8) **확정 신규 누락 키 0건 + #8 candidate를 RECON bound family로 정밀화**(중복
  계상 회피). **선제 fail-open 봉합**: no-blended를 구조로·core-tier over-claim 방지(§1 #8과 정반대 판정)·cross-
  section self-consistency pass(§1↔§5/§6↔§7 대조 완료 — C1 lesson)·confidence class/bound/proof rule verbatim
  전사(에라타 defect class). 이후 독립 비평 리뷰 대기.
- 2026-07-25: **v1.1 — 독립 비평 리뷰 ACCEPT-WITH-MINOR 반영(CRITICAL 0 / MAJOR 0 / MINOR 5).** 리뷰는 다섯
  attack prediction을 전부 **반증**했다(transcription 13/13 필드 검증·conservative bound 방향 정확·seam signature
  line 단위 일치·cross-section 정합·프로파일 키 line 정확). MINOR 5건 **전량 반영(forward-only)**: **[m1]** §5.1
  `classify_field`가 주입 `freshness_marker`를 소비하고 "previously sufficient"는 caller-side 공급임을 명시 +
  **STALE이 CORROBORATED에 우선**(aged ∧ ≥2-independent-agree ⇒ STALE)을 pin(§6.1 freshness_ok가 corroboration과
  독립 gate라 어느 해석이든 release fail-closed) + §7 canary row 추가. **[m2]** seam cross-check를 "원하면"에서
  **MANDATED test-only cross-import**로 격상(§3.4/§7/§9.1; recon·orthostate 둘 다 import해 bool polarity·fail-closed가
  `orthostate/predicates.py:502–504` 기대와 일치함을 assert — package edge 아님·§7.1 closure 무영향). **[m3]** §4.2에
  **cross-package coordination 의무** 추가(KnowledgeState/FieldState·FieldConfidenceClass를 동시 담는 미래 패키지는
  별개 typed 필드 유지 MUST — 공유 raw-string slot 금지, StrEnum coercion 축 붕괴 방지). **[m4]** §8에 대안 판독
  인정(agreement-tolerance·independence-degree를 confirmed-missing으로 볼 여지 — Bounds-Approver 판단; fail-closed
  주입 default라 safety-neutral). **[m5]** §9.1 PROMOTE back-compat 명시(rcl `vector.py:50/82`·`records.py:29` 두
  site를 canonical source로 갱신 MUST, `rcl.vector` re-export=courtesy shim; `test_rcl_digest.py:16` 무영향·rcl
  스위트 무변경 green). + §9.2에 리뷰어 open question(aged `freshness_marker`는 previously-assessed field에만 공급 —
  caller-side precondition, integration-scope) **item 11** 기록. 아키텍처 핵심(패키지·sibling-edge-0·CanonicalDecimal
  PROMOTE·id⊥digest·no-blended 구조·RECON-EV 0건 완결·transcription)은 **v1.0 그대로**. 2026-07-25
  운영자 비준(판단 지점 3건 승인).
- 2026-07-25: **v1.2 — §1 -004 행 time-loss class gloss 에라타(의미 변경 아님, 비준 효력 유지).**
  구현(`tos/src/tos/recon/predicates.py`)이 time-confidence 상실 시 would-be-CORROBORATED 필드를
  `STALE`로 pin(공개 편차 #5); 독립 코드 리뷰(**ACCEPT-WITH-MINOR, CRITICAL 0/MAJOR 0/fail-open 0**)가
  MINOR-2로 확정 — v1.1 §1 표의 `fail closed(UNKNOWN)` gloss는 오기(ADR §7 line 103은 class 미지정·
  fail-closed만 요구; previously-corroborated의 time-loss는 `STALE`이 의미상 정확; release는 §6.1이
  freshness를 corroboration과 독립 게이트하므로 어느 class든 차단 — 이중 게이트). 본 v1.2가 gloss를
  `STALE`로 정정. 코드 리뷰 MINOR-1(field/confidence 정합 가드 부재)은 **코드 측 수정**: `field_
  reconciled_proof_ok` 최상단에 defense-in-depth 가드(`confidence.field` 상이 ⇒ False) + mismatch
  canary 테스트 추가(pytest 1354). 그 외 조항·비준 효력(2026-07-25, v1.1) 불변.

### 10.2 비준 체크리스트 (운영자 · 독립 리뷰어 확인 사항)

- [ ] §0.2 NO 목록(evidence persistence·broker FQP 내용·PTOL finality·numeric bound·time 메커니즘·capacity
      mutation·trigger orchestration·**닫는 RECON-EV 0건**·bounds 미승인)과 §0.3 firewall 준수(numpy/pandas/
      pyyaml·shared.config·**orthostate/rcl/time/evidence/capsule/authority/liveauth/dsl 배제, canonical·
      ordering만 허용**; `.importlinter`는 forbidden 계약뿐 — intra-tos edge firewall-clean이나 본 문서는 sibling
      edge 0건을 설계 규율로 유지)에 동의.
- [ ] §0.4a 전용 패키지 `tos/src/tos/recon/`(`tos.confidence`/`tos.reconciliation`/`tos.evidence` 기각; naming
      비-load-bearing) 채택에 동의.
- [ ] **§0.4b/§3.4 recon↔orthostate seam = plain-bool producer, sibling edge 0건**(recon이 orthostate
      `knowledge_transition_allowed` corroboration/FQP/freshness 플래그의 상류 producer; ADR-002-005 §8 line 128
      정합; composition=caller 소관; 대안 A[네 번째 edge]·B[역전] 기각·cycle 회피)에 동의. **[운영자 판단 지점:
      plain-bool decoupled(권장) vs 대안 A 네 번째 sibling edge(typed target 명명 — 비권장)]**
- [ ] **§0.4c/§3.1 `CanonicalDecimal`(+`_normalize_decimal`) `tos.rcl.vector`→`tos.canonical` PROMOTE**(clean-
      atom, `_num_token` companion; recon↔rcl sibling edge 회피; PROMOTE=1; #8 CapacityState 기각과 정반대 근거;
      **[m5] back-compat: rcl `vector.py`(`:50`/`:82`)·`records.py:29` 두 site를 canonical source로 갱신 MUST,
      `rcl.vector` re-export=courtesy shim, `test_rcl_digest.py:16` 무영향·rcl 스위트 무변경 green**)에 동의.
      **[운영자 판단 지점: PROMOTE(권장, ratified rcl 접촉·behavior-preserving relocation) vs Fallback(rcl
      additive 재노출 + recon→rcl 네 번째 edge — 비권장)]**
- [ ] §0.4d/§3.1 canonical REUSE + `id=f(digest)` 미채택 + **records substrate PROMOTE 0건 / numeric substrate
      PROMOTE 1건**(IndependentId·classify_record_pair 이미 core)에 동의.
- [ ] §0.4e/§3.5 evidence(하류 투영·layering)·capsule(다른 축·좌표 비붕괴)·time(freshness 주입)·orthostate/rcl
      (produced-bool seam)·authority/liveauth(role) **미import** — recon = decision-side 상류 + **[m3] §4.2
      cross-package coordination 의무**(미래 패키지가 KnowledgeState/FieldState·FieldConfidenceClass 동시 담을 때
      별개 typed 필드 유지 MUST — 공유 raw-string slot 금지)에 동의.
- [ ] **§0.4g/§1 RECON-EV "0건 완결" shape**(register 최소 레벨 다섯 행 전부 EV-L2+ [001=L2/3·002=L3·003=L2/3·
      004=L2/3·005=L3+Broker, line 96–100 실측] — **EV-L1 슬라이스 0건, core tier 없음** — #8/RCL과 정반대·Time/#6/#7
      동형) + **authoring이 RECON-EV를 닫지 않음**(VER §5) + predicate-only(001..005 전부)/not-Phase-1(없음) +
      "EV-L1-complete 주장 금지"에 동의.
- [ ] §2 데이터 모델(`FieldConfidenceClass` 5종·`SafetyRelevantField` "at least these"·`ConservativeBound`·
      `FieldConfidence`; `FieldReconciliationAssessment` = **IndependentId + 독립 id**, `IdDerivedArtifact` 0건;
      **append-only + lifecycle-out-of-collision**)과 §2.2 confidence class/bound/proof rule **verbatim 전사**에
      동의.
- [ ] **§4.1 no-blended-release 구조 불변식**(중앙; numeric confidence score 타입 **부재**·averaging 함수 **부재**·
      release 술어 per-field-only 입력 — "aggregate 점수로 release"가 구조적 표현 불가; ADR §1/§5 line 86/§11·
      ADR-002-002 §22.2) + §4.2 3-axis 좌표 비붕괴(타입+미import) + §4.3 conservative bound 단조성(widen 자유·narrow
      양성 증명·None⇒unbounded) + §4.4 empty⇒UNKNOWN·omission≠negative + §4.5 single-source ceiling + §4.7
      representation≠mutation(capacity mutate 메서드 부재)에 동의.
- [ ] §5 classify_field(빈⇒UNKNOWN·single⇒SINGLE_SOURCE·≥2-independent-agree⇒CORROBORATED·common-mode⇒non-
      corroborated; independence/tolerance 주입; **[m1] 주입 `freshness_marker` 소비·"previously sufficient"
      caller-side·aged∧corroborated ⇒ STALE 우선·release는 §6.1 freshness_ok 독립 gate라 fail-closed**) + **§5.2
      merge_conservative union·never average**(100∧150⇒upper 150 not 125 canary) + §5.3 negative-evidence(absence⇒
      bound narrow/terminal/release-proof 불가) + §5.4 over-claim 금지에 동의.
- [ ] §6 **field_reconciled_proof_ok / field_specific_release_proof_ok**(CORROBORATED∧FQP[주입,+Broker 이연]∧
      fresh∧no-conflict; weaker evidence[cancel-ACK·terminal-no-qty·single-source·late-correction] ⇒ not ok;
      recon은 proof bool만·release 미수행 §4.7) + §6.3 freshness_ok(horizon/time-loss/**new-generation 무효화**;
      time 미import·주입)에 동의.
- [ ] §7 하네스 타깃(**전부 predicate substrate·닫는 RECON-EV 0건·core tier 없음**; no-blended 구조·classify·
      **[m1] STALE 우선순위 row**·merge-union·negative-evidence·single-source·release-proof·freshness·bound-단조·
      좌표 비붕괴·**[m2] seam cross-check(MANDATED test-only cross-import, NOT package edge)**; both-ways canary;
      "EV-L1-complete 주장 금지"; **§1↔§5/§6↔§7 self-consistency 대조 완료 — C1 lesson**), §7.1 import-closure
      (orthostate/rcl[PROMOTE 시]/time/evidence/capsule/authority/liveauth/dsl 부재 + canonical/ordering 허용),
      §7.2 run manifest 7항목에 동의.
- [ ] §8 bounds 주입 + **확정 신규 누락 distinct 키 0건 + Phase-0 candidate 1군**(RECON bound family = freshness
      horizon·agreement tolerance·independence degree — #8 knowledge/reconciliation-staleness candidate의 정밀화,
      신규 count 아님; 기존 `MAX_clock_drift_ppm`·`B_external_activity_detect`·`MAX_currentness_vector_age_ms`
      재계상 없음; ADR §14 line 186 프로파일 위임; **[m4] 대안 판독(agreement-tolerance·independence-degree를
      confirmed-missing으로 볼 여지)은 Bounds-Approver 판단·fail-closed 주입 default라 safety-neutral**)에 동의.
- [ ] §9.2 Phase-0 이관 **11항목**(PROMOTE+seam·프로덕션 canon·RECON bound family·broker FQP·evidence persistence·
      PTOL finality·aggregate KnowledgeState·trigger orchestration·authority epoch·독립 리뷰어·**[리뷰어 open Q]
      aged `freshness_marker`는 previously-assessed field에만 공급하는 caller-side precondition**)을 별도 게이트로
      유지에 동의.
- [ ] 명명 규약(§0.4f): 모델 불변식을 **AC-006-1..5 / RECON-EV-### / §-clause / SAFE-### / ADR-002-002 INV-012
      cross-cite**에 앵커하고 **새 INV 시리즈를 창작하지 않음**(ADR-002-006엔 자체 INV 부재 — 실측)에 동의.

비준 시 효력: IMPLEMENTATION-PLAN-002 §4 Phase 1의 ADR-002-006 부분을 `tos/src/tos/recon/`에 순수·비전송 모델 +
property test로 작성 착수 승인(`tos.canonical`·`tos.ordering` REUSE, **sibling edge 0건**, `CanonicalDecimal`
PROMOTE 1건, produced-bool seam은 caller/integration 이연 + test-only cross-check MANDATED). §9.2 Phase-0 11항목과
bounds 승인·독립 리뷰어 지정,
Phase B(evidence persistence·broker FQP·trigger orchestration·aggregate roll-up·+Broker) 전체는 별도 게이트로
남는다. **닫는 RECON-EV 0건 — acceptance 주장 없음.**
