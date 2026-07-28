# 설계 문서 #29 — Software Supply-Chain Integrity / Release-Artifact Admission / Deployment Provenance Governance 계약 (ADR-002-029, EV-L1) (2026-07-28, v1.3)

> **v1.3 개정(2026-07-28, 최종 판정 ACCEPT-WITH-MINOR·비준 진행 가능·마이크로 개정).** 2-helper 분리
> 반론이 리뷰어 `_cmp`(`ordering/_ordering.py:77-83`·equal⇒None⇒AMBIGUOUS) 실측으로 UPHOLD(시리즈 모범).
> **MINOR-1**: §5.4 시그니처에 `release_artifact_manifest`+`manifest_resolved` 추가·item 11로
> `release_artifact_identity_exact` 명시 편입·계수 "5 노른자 + cross-cutting 5 + 지지 술어 3" 통일(§0.1-4·
> §6·§9.1·승인문). **MINOR-2**: BuildProvenance/RuntimeAttestation `result`(:8) → 불투명 `str | None`
> (admission 아님·§7:232 "attestation is a fact")·§2.2 AdmissionResult 매핑 admission-decision:8·admitted-
> set:9 한정. **canary(§6.3 i·j)**: floor equal-단락 이동·generation equal⇒True 뮤턴트로 2-helper 분리
> 회귀 고정. 아키텍처·골격·C1-C3·M1-M9·NEW-1~7 UPHOLD·무변경. 상세 §10.3.
>
> **v1.2 개정(2026-07-28, 델타 재검증 REVISE 반영 — v1.1 신규 유입 MAJOR 4·MINOR 3·(1b), 국소·기계적).**
> 아키텍처 7건·§2.4 골격·C1-C3·M1-M9는 UPHOLD(리뷰어가 M4·M5를 "처방 넘은 모범", C1 digest-binding을 "bool
> 처방보다 우수"로 기록). 반영 전 ordering/cur 코드 재실측(전건 확정). **NEW-1** §5.0에 ordering 헬퍼 2종
> 신설(`compare_order`는 `OrderingEvent` 전용·str 불가·`Ordering.AMBIGUOUS` 미매핑 fail-open — cur
> `floor_strictly_advances`(`state.py:190`) shape REUSE·int floor·AMBIGUOUS⇒deny)·§5.4 item4/item8·§5.6b
> 호출 사이트 치환·§6.3(h)·§3.5 int 정합. **NEW-2** §5.4 시그니처에 `target_scope`+`scope_resolved` 추가
> (item6 도달 가능). **NEW-3** §5.1 item2 mutable-name 게이트 회귀 복원(`is False` 실게이트). **NEW-4+1b**
> dead-row 7 해소(§5.5에 committed/current/compatibility_complete/restriction_state·§5.4에 decision current·
> 신규 `release_artifact_identity_exact`; compatibility는 bool 게이트로 §5.5 일원화). **NEW-5** §2.2 xref
> 정정. **NEW-6** BuildProvenance 골격 3필드 추가. **NEW-7** §5.3 "declared 축" 결정적 정의. §10.3 v1.2 로그.
>
> **v1.1 개정(2026-07-28, 독립 비평 리뷰 REJECT 반영 — CRITICAL 3·MAJOR 9·MINOR 7·Gap 6, 오케스트레이터
> 고하중 주장 전수 1차-소스 재확정·반론 0).** 결함은 전부 **모델층↔술어층 결합**(아키텍처 7건[edge 0·
> IndependentId 전수·spg seam·FD split·hag consumer·rcl edge 0·`tos.sci` 명명]은 리뷰어 전원 지지·유지).
> 모든 처방은 반영 전 **8 canonical 템플릿 + cur/posttrade/spg/dsl 코드 전수 재실측**(리뷰어 인용도 재검증).
> 핵심 반영: (C1) §5.4 ADMIT 게이트에 §15 step 7 restriction-floor(`current_release_restriction_floor`
> :27)·step 4-6 digest binding·independence result(:29) 편입·invented bool 제거; (C2) §5.5 ∅ admitted-set
> **deny로 전환**(공허-True 제거·§5.3과 통일·ADR explicit-empty 부재 negative-grep); (C3) phantom 필드 2건
> (`source_continuity_proven`·`predecessor_conflict_present`) → 템플릿 실명(`history_rewrite_detected`:33·
> `predecessor_release_generation`:25) 치환; (M1) §2.4 골격 21건 템플릿 실명 드리프트 정정; (M2)
> `AllFalseSupplyChainAuthority` 템플릿 실명 20필드+`creates_artifact_admission` 복원; (M3)
> `RuntimeArtifactAttestation` 골격 신설·"9 tos 모델(8 템플릿+ReleaseRestriction)" 통일; (M4) cur
> `RestrictiveFenceRecord`(records.py:315)/`fence_advances_floor`(predicates.py:415) 충돌 봉합; (M5)
> **"ptf 미착지" 거짓 정정 — posttrade 착지**(미착지=sir·stm 2건)·spg 7-item 이연 정확 인용; (M6) §5.6(e)
> 완전 시그니처; (M7) §5.0 극성표 실필드 재작성·tri-state/bool 이중표현 제거(ReproductionResult enum 폐기);
> (M8) §11 closure 17차원 전사; (M9) SupplyChainScope 9차원 전사. MINOR/Gap 전건 §10.3 로그.
>
> **문서 지위**: kis_unified_sts 프로젝트 측 설계 계약. tos-spec에 대해 **non-normative**이며 스펙
> 텍스트(RFC/ADR/템플릿/프로파일)를 **변경하지 않는다.** 본 문서는 ADR-002-029를 그린필드
> `tos/src/tos/sci/` 신규 패키지의 Phase 1(EV-L1) **순수·비전송 predicate/model substrate**로 실현하는
> 계약이다. 코드·git 커밋은 본 문서 범위 밖이다(비준 후 별도 단계). 이 문서 단계에서 **코드 작성 금지**.
>
> **비준 상태**: **2026-07-28 운영자 위임 자동 비준 대상(v1.1; 2026-07-25 표준지시 + 2026-07-28 병렬
> 세션 C 전담 배정).** 게이트: 저작 → 1차 심사 → 독립 비평 REJECT → **v1.1 개정(본 문서)** → 재심사 →
> 구현 → 적대적 코드 리뷰 → 게이트. 품질 파이프라인 전량 유지. 어떤 SCI-EV/SCI-AC/acceptance/비준도
> 선언하지 않는다.
>
> **broker-agnostic**(project memory `tos-spec-broker-agnostic`): source-revision·build-provenance·
> dependency-closure·release-artifact·admission-decision·release-generation·admitted-release-set·
> runtime-attestation·release-restriction 어휘·술어는 전부 broker-agnostic이다. broker 전송·route·
> Final Quantity Proof는 §23/§7에서 **capability class**로만 표현.
>
> **선행 문서(의존)**: [설계 #1 firewall](2026-07-20-tos-boundary-and-import-firewall-design.md)·
> [설계 #4 canonical](2026-07-20-tos-evidence-store-design.md)·[#25 RLP](2026-07-27-tos-release-promotion-design.md)
> (`is_wildcard_value` 비전수-정직 denylist·edge-0 선례)·[#26 WDR](2026-07-27-tos-safety-waiver-design.md)
> (greenfield content-owner + SoD 표 형식 최근접 선례)·[#27 FD](2026-07-27-tos-failure-domain-design.md)
> (anti-phantom §0.5·coordinate/governance split 선례).
>
> **규범 원천**: `ADR-002-029` (Status: **Proposed**, 658행). §30 line 658 "This ADR authorizes
> architecture and implementation planning only." 본 계약도 마찬가지다.

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. **패키지 명명 `tos.sci`**(register prefix `SCI` 1:1). **naming은 WDR보다 강한 soft load-bearing**:
   착지 형제 4개 `__init__.py`(`egress/__init__.py:65`·`cur/__init__.py:51`·`rlp/__init__.py:39`·
   `wdr/__init__.py:47`)와 4개 import-closure 테스트(`test_egress_import_closure.py:10`·
   `test_cur_import_closure.py:78,196`·`test_rlp_import_closure.py:82`·`test_wdr_import_closure.py:80`)
   = **총 8개 파일**이 `tos.sci`를 "not-landed upstream — excluded by construction"으로 명시 열거한다
   (firewall 배제 목록 명명·§0.4a). 운영자 사전 배정으로 `tos.sci` 확정.
2. **핵심 아키텍처 판정(리뷰어 전원 지지) — SCI = greenfield release-admission content 생산자 + 착지
   하류 소비자(spg) + 형제-이연 무거운 통합 레이어.** SCI는 착지한 하류 소비자(`spg/records.py:206`
   `software_deployment_ok: bool | None`)를 가진 생산자다. SCI가 소유하는 잔여 = **release-artifact
   admission 프로토콜 전체**. **형제 import 0(sibling edge 0·§3.4)**. authority/capacity/protection/
   config-activation/currentness/incident/egress/production-promotion/evidence/recovery/re-arm/
   effective-principal-collapse/restriction-floor-advance를 **재저작하지 않는다**(§3.5 SoD).
3. **EV 3분류(행별 정직)** — **core(L1 슬라이스) 4행 {001 `EV-L1/3+Security`·002 `EV-L1/2/3+Security`·
   003 `EV-L1/2/3+Security`·006 `EV-L1/3+Security`}** / **not-Phase-1 8행 {004·005·007·008·009·012
   `EV-L2/3+Security`·011 `EV-L2/3+Broker+Security`·010 `EV-L3+Security`}**. **닫는 SCI-EV = 0건**(§1).
   **register 12행 전수 `+Security`**(거버넌스 6부작 유일) — 어떤 SCI-EV도 코드만으로 닫히지 않으며
   Phase-1은 조직 security-boundary 게이트를 전혀 충족하지 않는다. "EV-L1-complete 주장 금지".
4. **중심 L1 술어(§5·5 노른자)** — `source_identity_exact_and_reviewed`·`provenance_is_not_admission`·
   `closure_complete_or_restrictive`·`admission_admits_only_positive`·`admitted_set_no_permissive_union`
   + **cross-cutting 구조 술어 5**(all-false·generation-monotonic/rollback·restriction-non-revival[floor
   advance는 cur 이연·§5.6c]·negative-gate·`software_deployment_ok_verdict` producer) + **지지 술어 3**
   (`mutable_name_is_not_identity`·`independence_unproven_is_common_mode`·`release_artifact_identity_exact`·
   MINOR-1). 전부 순수·
   fail-closed·전 owner verdict/generation/digest는 주입.
5. **over-realization + duplication 이중 경계(EGRESS #22 교훈).** 암호 서명 검증·reproducibility 바이트
   비교·scan 실행·SBOM 파싱·registry retrieval·runtime measurement·effective-principal collapse·
   capacity 산술·config activation·per-send currentness transaction·incident lifecycle·production
   promotion·evidence custody·recovery/re-arm·**restriction-floor advance(cur `fence_advances_floor`)**은
   전부 형제/런타임/+Security/+Broker-owned. L1은 admission 프로토콜의 **구조 완전성·양성 ADMIT·closure
   완전성·mutable-name 거부·generation monotone·restriction 비-소생·negative-gate·all-false authority**
   판정만.
6. **소유권/seam 분할표(§3.5) — 본 문서 최대 함정.** spg(`software_deployment_ok` 소비 + BundleMember
   7-item 이연)·failuredomain(supply-chain 좌표 4종·거버넌스 SCI 이연)·hag(effective-principal collapse
   일반 모델)·rcl(capacity)·egress(final-egress)·cur(Safety Currentness Vector + **`RestrictiveFenceRecord`/
   `fence_advances_floor`**·M4)·posttrade(**착지**·spg 7-item 중 -030 지분·M5)·protective/liveauth/
   authority/rlp/evidence/sbr(이연)·sir(미착지·조건부 seam)를 **SCI가 재저작하지 않는다**. dsl
   `AdmissibilityResult`는 **명제-동일성 비-seam**(disambiguation·§3.5).
7. **선제 봉합(§0.5)** — ∅ **양방향 deny 통일**(closure/lineage/admitted-set 부재 ⇒ restrictive·ADR
   explicit-empty 부재 negative-grep 확인·과잉봉합 아님·C2)·truthy-sentinel 봉인(`AdmissionResult`·
   `IndependenceResult` `__bool__⇒TypeError`)·ADMIT=양성 identity(AFG C1)·음극성 `is False`만·all-false
   supply-chain authority(템플릿 20필드·M2)·malformed-model 자기방어·anti-phantom·greatest-scope 극성
   일관성·mutable-name denylist 정규화+비전수 정직·**템플릿 실명 anchor-drift**(M1·§6.2).

### 0.2 하지 않는 것 (경계·NO 목록)

- **형제 소유 로직 재저작 금지(duplication 경계).** hag collapse/quorum·rcl `CapacityVector`/worst-
  credible-effect·spg Hard Safety Envelope/config activation·egress final-egress·cur Safety Currentness
  Vector completeness + **`fence_advances_floor` restriction-floor advance(M4)**·evidence custody·
  liveauth Live Authorization·authority epoch·rlp production-promotion·sbr Recovery Barrier를 **재판정
  하지 않는다** — 각 owner verdict/generation/digest를 **주입 좌표**로만 소비.
- **admission 실행·per-send enforcement runtime 재구현 금지(over-realization 경계).** §19 per-send
  active-currentness transaction·§14 restriction-vs-first-byte send race·§13 config activation·§17
  break-before-make·§12 independent reproduction·§18 runtime measurement은 전부 런타임/egress/spg/
  +Security/+Broker. L1은 **주입 verdict/digest 위의 순수 admission-구조/generation/restriction 판정**만.
- **암호·빌드·측정 로직 구현 금지(EGRESS #22 교훈).** ADMISSION-DECISION 템플릿은 검증 결과를 **digest
  binding**(`artifact_signature_and_key_status_digest`:19·`registry_custody_proof_digest`:20·
  `compatibility_graph_digest`:21·`scan_test_and_finding_evidence_digest`:22)로 담는다 — SCI는 이
  binding의 **present·concrete(구조 완전성)**만 판정하고 실제 서명 검증·바이트 비교·scan을 **하지
  않는다**(실 검증 결과는 +Security로 digest에 봉입·§5.4). invented bool verdict 저작 금지(C1-3·§2.4).
- **자체 artifact identity를 mutable name으로 표현 금지(SCI-INV-002).** tag/branch/path/`latest`는
  identity 아님 — RELEASE-ARTIFACT `mutable_tag_is_identity: false`(:51·음극성) + `is_mutable_name_
  notation`(§2.2·rlp shape)으로 봉인.
- **어떤 admission을 부여(grant)하지 않는다.** §1 line 21 "`ADMIT` means only that the exact artifact is
  eligible to be included in one new Admitted Release Set." SCI 술어는 *분류·fail-closed*만.
- **수치 하드코딩 금지(§8)** — 10 VP 키(§29 item 12) 전부 Profile INSTANCE 측정/승인·주입(현재 전부
  `null`·`owner: TBD`·§8).
- **미착지 상류 코드 인용 금지(정정)** — **sir(-027)·stm(-028) 미착지**(`ls tos/src/tos/{sir,stm}` ⇒
  부재). **-030 posttrade는 착지**(`tos/src/tos/posttrade/`·M5). §20의 incident(-027) generation 차원은
  **ADR 원문만·generation 주입·코드 인용 0**(phantom 봉합·§0.4f). 구현 시점 sir 착지 여부 재실측(조건부
  seam·§3.5).
- **EV/acceptance/비준 선언 금지.** tos-spec 수정 금지·기존 docs/plans 무수정. **어떤 SCI-EV도 닫지 않음**(§1).

### 0.3 firewall 준수 선언 (설계 #1 §3.2)

`tos.sci`는 **순수 모델·술어 패키지**다: `pydantic`(frozen) + stdlib + `tos.canonical` + `tos.ordering`만
import. `shared.*`·`services.*`·`cli.*`·`numpy`/`pandas`/`yaml`·`os.environ`·동적 escape 전면 부재.
**형제 tos 패키지(canonical·ordering 제외 전부 + posttrade[착지] + 미래 sir/stm) 전부 import 부재** —
형제 상호작용은 **주입 scalar/digest/bool/verdict/enum-token**으로만(sibling edge 0·§3.4).

- **firewall 구조(실측·2층)**: 층① AST gate(`tools/tos_firewall_check.py` §3.2 default-deny allowlist·
  "Changing the allowlist requires a PR editing that doc" line 422)·층② import-linter `[importlinter:
  contract:tos-operational-firewall]`(type=forbidden·source_modules=`tos`·transitive). SCI는 canonical/
  ordering(둘 다 `tos.*`)만 import하므로 **firewall 무수정 자동 포섭**(FD #27 §0.3 선례).
- **착지 회귀 무영향**: 착지 형제 8개 파일이 `tos.sci`를 "not-landed excluded"로 열거하나 그들이
  `tos.sci`를 import하지 않으므로 SCI 착지가 형제 테스트를 깨뜨리지 않는다(주석 문구만 사후 갱신 대상·§9.2).
- §6.1 import-closure 검증 테스트(allowlist 형식·저작-레벨 vars()+AST 스윕)가 §0.3을 능동 강제.

### 0.4 REUSE / import / 경계 결정 요지 (핵심 아키텍처·리뷰어 전원 지지)

**(a) 패키지 명명 = `tos.sci` (register-prefix 1:1·8개 파일 지명·WDR보다 강한 soft load-bearing).**
runner-up `tos.supplychain`(full-word)은 기각. **주의(M5)**: 8개 배제 목록은 `tos.ptf`(구 placeholder)도
열거하나 실제 착지 패키지는 `tos.posttrade`(§3.3) — 배제-목록 명명과 착지-명명이 불일치하는 선례가
이미 존재하므로 `tos.sci` 배제-목록 명명이 곧 착지-명명 확정은 아니다(운영자 확정 필요·§10.1).

**(b) SCI = greenfield release-admission content 생산자·착지 하류 소비자 보유 (본 문서 최대 판정).**
실측(inbound 이연 seam 0·outbound 소비 seam 2): (1) `spg/records.py:190,206` `software_deployment_ok`
produced-value seam(SCI producer·spg consumer·§3.5-1), (2) `spg/vocabulary.py:185-187` BundleMember
7-item 이연(§3.5-2·M5). failuredomain은 좌표만(§0.4d)·dsl은 분리 선언(§3.5 비-seam). ⇒ SCI는 순수
greenfield 생산자이되 착지 소비자(spg)를 가진다.

**(c) canonical `IndependentIdArtifact` REUSE — SCI ledger/manifest 전 아티팩트가 id ⊥ digest.**
**실측(정정·m4)**: 8 canonical schema 템플릿 전수가 **독립 `*_id` 필드 + `canonical_digest`를 별도
필드**로 보유(`policy_id`·`manifest_id`·`attestation_id`·`decision_id`·`release_set_id` ⊥ `canonical_
digest`·8/8). **주의**: digest 필드명은 전 템플릿 `canonical_digest`이고(`*_digest` 아님·M1), 일부는
`result: UNKNOWN`(admission-decision:8·admitted-set:9·provenance:8·runtime:8)·일부는 `semantic_result:
UNKNOWN`(source-revision:36·release-artifact:8)·policy는 result 필드 없음 — **"전수 result:UNKNOWN"은
거짓이므로 identity 근거에서 제외**하고 **독립 `*_id` ⊥ `canonical_digest` 8/8**만 근거로 삼는다. 독립
`*_id`가 별개 필드라는 것이 `IndependentIdArtifact`(id ⊥ digest·`_base.py:328`)의 구조 signature다(id를
`f(digest)`로 도출하는 `IdDerivedArtifact`는 별도 mutable `*_id`/`*_version`을 갖지 않음). ⇒ **전 SCI
아티팩트 = `IndependentIdArtifact`**(rcl/dsl/authority/evidence/rlp/egress/cur/wdr 선례). same-`decision_
id`/different-bytes 위조/replay를 `classify_record_pair` CRITICAL_CONFLICT로 탐지(§2.1·§3.1). artifact
실 바이트 digest(`artifact_content_digest`)는 tos 모델 아님(주입 opaque str).

**(d) failuredomain coordinate / SCI governance split (§3.5·재저작 금지).** FD(#27·착지)가 RFC-002
§24.1 supply-chain 좌표 4종(`SOURCE_REPOSITORY`·`BUILD_TOOLCHAIN`·`ARTIFACT_SIGNING`·`ARTIFACT_
REGISTRY`·`failuredomain/vocabulary.py:89-95`·`records.py:163`) 소유·governance는 SCI 이연(`vocabulary.py:59-60`).
**SCI는 FD 4 좌표를 import·재소유하지 않는다**(축 상이·negative-seam·§0.5-1).

**(e) hag effective-principal = 일반 모델 생산자·SCI = instance consumer (§3.5·SCI-INV-007).** SCI는
template `effective_principal_independence_result: UNKNOWN`(source-revision:23·admission-decision:29·
runtime `attestor_independence_result`:42) verdict를 **주입 소비**하고 "unproven independence ⇒
common-mode/restrictive" 구조 술어만(§5.1 지지). **hag `effective_principal_collapse` import·재저작
금지**(hag #20 liveauth 선례). 실 collapse는 hag verdict + +Security.

**(f) 미착지 상류 027(sir)·028(stm) 차원 (phantom 봉합·조건부 seam·M5 정정).** **실측**: `sir`·`stm`
부재·**`posttrade` 착지**. ADR §20 line 406 incident(-027) handoff 참조. **판정**: SCI는 incident
generation/digest를 주입 좌표로만 소비·**코드 인용 0**. 구현 시점 sir 착지 여부 디스크 재실측 — 착지 시
seam test(venue/PR #18 선례), 미착지 시 명시 이연 docstring. **sir 타입 import 금지**.

**(g) rcl edge 판정 = 0 (§7:235 "artifact lifecycle never writes capacity"·WDR #26 동형).** SCI는
capacity가 아니다 — §7 line 235·SCI-INV-001 line 155·§23 line 451 "RCL … sole capacity mutation."
worst-credible economic-effect envelope는 rcl이 나중에 소비할 **주입 opaque 좌표**(CapacityVector 타입
아님). **edge 0**(WDR·rlp·iap 선례).

**(h) canonical/ordering/all-false/mutable-name 경계 (verdict 주입 / shape REUSE·§3.5 표).**
canonical(REUSE)·ordering(REUSE·`compare_order`·PROMOTE 0)·`_NonTruthyStrEnum`(로컬 재표현)·
`AllFalseSupplyChainAuthority`(로컬 재표현·**템플릿 실명 20필드**·M2)·`is_mutable_name_notation`(로컬
재표현·rlp shape).

### 0.5 방법론 · anti-phantom 규율 · 시리즈 defect-class 선제 봉합 체크리스트

1. **anti-phantom(부재·존재 주장 모두 grep·FD #27·v1.1 강화).** 모든 인용은 grep/Read 실측 후 file:line.
   **부재 주장은 디렉토리 토큰 + ADR 번호 문자열 양쪽으로 grep**(M5 교훈 — "ptf 미착지"가 `posttrade`
   패키지명 미검색으로 거짓이었음). 본 문서 부재 주장 negative-grep: (i) **sir/stm 미착지**(`ls
   tos/src/tos/{sir,stm}` 부재·posttrade는 착지), (ii) SCI 새 VP 키 0(§8·10키 실재), (iii) dsl 비-소비
   (evidence.py:66 분리), (iv) SCI가 FD 좌표 미소유(FD vocabulary.py:89-95), (v) **SCI가 cur
   `RestrictiveFenceRecord`/`fence_advances_floor` 재저작 0**(cur records.py:315·predicates.py:415
   소유·M4), (vi) ADR에 "explicit empty Admitted Release Set" 부재(§5.9/§16/§11 grep 0·C2 근거).
2. **∅-vacuous 양방향 deny 통일(C2·WDR #26 역방향 교훈).** closure/lineage/admitted-set 부재 ⇒ **deny**.
   **ADR이 explicit-empty를 명시 허용하지 않음을 negative-grep 확인**(§5.9/§16/§11에 "explicit empty"
   부재) ⇒ **deny가 정답**(WDR과 반대 — WDR은 ADR이 explicit-empty를 §13에서 명시 허용했기에 과잉봉합이
   결함이었으나, SCI는 명시 부재라 deny가 정답·과잉봉합 아님). 근거: §1 line 17 "Missing, stale,
   conflicting, ambiguous, incompletely closed … grants zero eligibility"·§16 line 346 "Missing
   artifact … invalidates the set for the affected scope." §5.3/§5.5 동일 규칙.
3. **truthy-sentinel `is not True`(ARE #13).** tri-state StrEnum(UNKNOWN 포함) truthy — `__bool__⇒
   TypeError` 봉인 + `result is AdmissionResult.ADMIT` 명시 비교(§2.2·§4.2).
4. **ADMIT = 양성 identity(AFG C1 fall-through 금지).** `is ADMIT` 명시(§5.4).
5. **음극성 `is False`만(#18/#22/#23/#25).** 음극성 clear는 `is False`만·`is not True` 금지. 양극성
   allow `is True`. None 양쪽 deny(§5.0).
6. **enum 전 멤버 전수 매핑(NT #21).** `AdmissionResult`(3)·`IndependenceResult`(3)·`RecordPairKind`(5)
   전수 분기(§6).
7. **구조 파생 > 자기신고(#18/#21).** admission 완전성은 self-report bool이 아니라 **구조적 binding
   존재**로 판정(§5.4). phantom self-report bool 금지(C3 — `source_continuity_proven`·`predecessor_
   conflict_present` 폐기). malformed-model self-defense가 "ADMIT + incomplete binding" 공존 구성 불가(§2.3).
8. **denylist 정규화 + 비전수 정직화(RLP #25).** mutable-name denylist는 strip+casefold+메타문자 거부
   후에도 **신종 표기는 +Security/런타임 소유** 정직 명기(§2.2·§5.1).
9. **import-closure allowlist(AFG M9·denylist 금지)**(§6.1·§7).
10. **저작-레벨 잠금(FD #27·export 표면 아님)**: 서브모듈 vars()+AST 스윕(§6).
11. **뮤테이션 canary 실효성 의무(전 시리즈)**: both-ways canary + 극성/enum-swap/∅-반전/**tri-state→bool
    투영(M7)** 뮤턴트 KILLED + 등가-뮤턴트 전수 열거(PTF 선례·§6.3).
12. **인용-드리프트 방지**: 문서-내부 line 대신 안정 ADR 조항(§·SCI-INV-###·template field name) 앵커.
    형제 코드 인용은 committed file:line(v1.1 전수 재실측).
13. **greatest-credible-scope 극성 일관성(AFG C1).** "greatest credible scope"(§13:309)·"greatest
    credible dependency scope"(§1:29·§20:404)·"greatest credible dependency closure"(§20:404) — any-
    broaden-wins·smallest 반전 금지(§5.6 mandated drift).

---

## 1. 범위 매핑 — ADR-002-029 조항별 EV-L1 도달성 (닫는 SCI-EV 0건)

**EV-level 정의**(VER-002-001): EV-L1 = Model+Property·EV-L2 = Component Fault·EV-L3 = Integration/
Adversarial·+Security = 독립 security-boundary·+Broker = broker-capability. Phase 1은 EV-L1만.

> **결정적 사실 1 — core 4행**(Python csv 파싱): SCI-EV-001..012 전부 `Critical`·`NOT_IMPLEMENTED`.
> **core(L1) 4행 = {001 `EV-L1/3+Security`·002 `EV-L1/2/3+Security`·003 `EV-L1/2/3+Security`·006
> `EV-L1/3+Security`}**. **not-Phase-1 8행 = {004·005·007·008·009·012 `EV-L2/3+Security`·011
> `EV-L2/3+Broker+Security`·010 `EV-L3+Security`}**. **닫는 SCI-EV = 0건**. survey §4.5(line 366) 정합.
>
> **결정적 사실 2 — register 12행 전수 `+Security`**(거버넌스 6부작 유일): core 4행조차 전부 `+Security`
> 잔여 ⇒ **어떤 SCI-EV도 Phase-1(EV-L1)로 닫히지 않으며** 조직 security 게이트를 전혀 충족하지 않는다.
> 002·003은 추가 3단 staged `EV-L1/2/3`(L2 component-fault 잔여).
>
> **결정적 사실 3 — authoring ≠ acceptance**: §27 line 550 "Written cases define obligations only"·
> §30 line 658 "authorizes architecture and implementation planning only." ⇒ **"EV-L1-complete 주장 금지"**.

**규율 태그(모든 주장에 부착)**: "**release-admission predicate/model substrate only; SCI-EV-001..012
전부 NOT_IMPLEMENTED — core 4행은 `/3`+`+Security` 대기(002·003은 `/2` 추가). +Security 12/12 — 조직
게이트 전면 미충족. EV-L1-complete 주장 금지. effective-principal collapse·capacity 산술·config
activation·per-send egress binding·reproducibility 비교·runtime measurement·서명 검증·restriction-floor
advance(cur)는 재저작/런타임/인간/+Security/+Broker/형제-owned. L1은 admission-구조/generation/restriction
비-소생/mutable-name/all-false 구조 판정만.**"

**SCI-EV core 4행 ↔ AC(1:1·§27 preamble line 550) ↔ ADR 조항 매핑**:

| SCI-EV | register 제목 | 최소 레벨 | SCI-AC(§27) | ADR 앵커 | L1 substrate 술어(§5) |
|---|---|---|---|---|---|
| **001** | Source Identity and Review Integrity | `EV-L1/3+Security` | AC-001(:552) | §9·§15 step 2·SCI-INV-002/003/007 | `source_identity_exact_and_reviewed`(노른자 1) + `mutable_name_is_not_identity`·`independence_unproven_is_common_mode` |
| **002** | Build Isolation, Provenance, and Reproducibility | `EV-L1/2/3+Security` | AC-002(:556) | §10·§12·SCI-INV-004 | `provenance_is_not_admission`(노른자 2) |
| **003** | Dependency and Toolchain Closure | `EV-L1/2/3+Security` | AC-003(:560) | §11·SCI-INV-003/005 | `closure_complete_or_restrictive`(노른자 3) |
| **006** | Independent Admission and Compatibility | `EV-L1/3+Security` | AC-006(:572) | §15·§16·SCI-INV-006/009/011 | `admission_admits_only_positive`(노른자 4) + `admitted_set_no_permissive_union`(노른자 5) |

**ADR-002-029 조항 → Phase-1 분류(core / substrate / not-Phase-1)** — WDR §1 표 형식(생략 없이 전수):

| ADR §-clause | 요지 | Phase-1 분류 | 소유 (근거) | SCI-EV |
|---|---|---|---|---|
| **§1**(15-29) | content-addressed·generation-fenced·fail-closed·non-authorizing·ADMIT eligibility만·negative gate | substrate+경계 | §5 전 노른자 + cross-cutting | 전 SCI-EV |
| **§5.7**(127) | ADMIT/DENY/UNKNOWN single-use non-authorizing | **core** | `AdmissionResult`·`admission_admits_only_positive`(§5.4) | 006 |
| **§5.8**(131) | Release Generation monotonic·no reuse | substrate | `release_generation_monotonic`·`rollback_is_new_generation`(§5.6·ordering) | 006/009 |
| **§5.9**(135) | Admitted Release Set complete·no patch/union/widen | **core** | `admitted_set_no_permissive_union`(§5.5) | 006 |
| **§6** INV-001..016 | 16 invariant | substrate | §4 전사 + §5 술어 | 전 SCI-EV |
| **§7**(221-241) | authority ownership 17행 | not-Phase-1(형제) | 전 형제 이연(§3.5)·SCI는 all-false·negative-gate | 011 |
| **§8**(247-259) | Software Release Policy field group | substrate(shape) | `SoftwareReleasePolicy` shape(§2.4·§4.3)·활성화 spg/014 | 전 SCI-EV |
| **§9**(265-269) | source identity·effective-principal independence·continuity | **core** | `source_identity_exact_and_reviewed`(§5.1)·independence hag 주입 | 001 |
| **§10**(275-279) | build isolation·builder continuity | core·substrate | `provenance_is_not_admission`(§5.2)·실 isolation +L2/+Security | 002 |
| **§11**(285-289) | dependency/toolchain closure·missing/floating⇒restrictive | **core** | `closure_complete_or_restrictive`(§5.3·17차원 §4.9) | 003 |
| **§12**(295-299) | provenance·reproduction·output disagreement⇒UNKNOWN/DENY | core·substrate | `provenance_is_not_admission`(§5.2)·실 비교 주입·+L2 | 002 |
| **§13**(305-309) | signing·key·greatest credible scope restriction | not-Phase-1(+Security) | signer/key +Security(004)·restriction greatest-scope §5.6 | 004 |
| **§14**(315-319) | registry custody·retrieve by digest | not-Phase-1(+Security) | custody 주입 verdict·+Security(005) | 005 |
| **§15**(325-338) | admission 10 step·ADMIT/DENY/UNKNOWN | **core** | `admission_admits_only_positive`(§5.4)·10-step §4.4 anchor | 006 |
| **§16**(344-348) | Release Generation serialize·set complete·restriction floor advance | core·substrate | `admitted_set_no_permissive_union`(§5.5)·floor advance는 cur(§5.6c·M4) | 006/007 |
| **§17**(354-360) | deployment promotion·non-live·mixed-version | not-Phase-1(+Security/rlp) | production promotion rlp·mixed +Security(009) | 008/009 |
| **§18**(366-370) | runtime attestation·actual bytes match·drift⇒restriction | not-Phase-1(+Security) | attestation match 주입·+Security(008)·`software_deployment_ok_verdict`(§5.6e) | 008 |
| **§19**(376-389) | active currentness 8-item·negative gate | not-Phase-1(런타임/cur/egress) | per-send cur/egress·SCI `active_currentness_is_negative_gate`(§5.6d)·8-item §4.5 | 010 |
| **§20**(395-406) | restriction·incident handoff·greatest credible closure | not-Phase-1(cur/-027) | restriction floor advance cur·incident sir(미착지)·greatest-scope §5.6 | 010 |
| **§21**(412-425) | partition/failure 12행 | substrate(구조) | §4.6 전사 + §5 fail-closed 술어 | 010/011 |
| **§22**(433-439) | rollback/restore/hotfix = new gen·no revival | substrate | `rollback_is_new_generation`(§5.6·SCI-INV-012) | 009 |
| **§23**(445-451) | UNKNOWN·capacity·broker finality | not-Phase-1(+Broker/rcl) | capacity rcl(§0.4g·edge 0)·broker finality +Broker(011) | 011 |
| **§24**(457-469) | evidence·recovery·non-revival | not-Phase-1(evidence/sbr) | custody evidence·recovery sbr·SCI non-revival(§5.6) | 012 |
| **§25**(475-521) Rejected(12)/§26 | 구조 근거 | substrate | §5 술어가 §25.1/25.5/25.6/25.7/25.8/25.11/25.12 실현 | — |
| **§27** AC-001..012 | acceptance case | 경계 | §1 매핑(전부 이연·0 closure) | 전 SCI-EV |
| **§28/§29(12)/§30(14)** | 경계 | SAFE-### | §4·§8·§9·§10 | — |

**닫는 SCI-EV = 0건.**

---

## 2. 데이터 모델 계약 (identity 정책 · 어휘 · malformed-model 자기방어)

### 2.1 identity 분류 (digest-bound / value / enum-token / reference)

**핵심 판정(§0.4c)**: 8 canonical schema 템플릿 전수 독립 `*_id` ⊥ `canonical_digest` ⇒ **8 template-
backed 아티팩트 = `IndependentIdArtifact`** + **`ReleaseRestriction`(§5.11·ADR-§5.11-파생·canonical
템플릿 없음)** = **총 9 tos 모델**(M3 — ADR §30-1 "eight schemas"에 runtime-attestation 포함·
ReleaseRestriction 미포함).

| 분류 | 모델 | 근거 |
|---|---|---|
| **digest-bound `IndependentIdArtifact`**(`_base.py:328`) | `SoftwareReleasePolicy`(`policy_id`)·`SourceRevisionManifest`(`manifest_id`)·`DependencyToolchainClosureManifest`(`manifest_id`)·`BuildProvenanceAttestation`(`attestation_id`)·`ReleaseArtifactManifest`(`manifest_id`)·`ArtifactAdmissionDecision`(`decision_id`)·`AdmittedReleaseSet`(`release_set_id`)·`RuntimeArtifactAttestation`(`attestation_id`·M3) + `ReleaseRestriction`(독립 id·템플릿 없음) | 8 템플릿 독립 `*_id`+`canonical_digest` 별도(§0.4c). same-`*_id`/different-bytes를 `classify_record_pair` **CRITICAL_CONFLICT**로 탐지(§3.1). |
| **value (frozen, id 없음)** | `SupplyChainScope`(§4.10 9차원·runtime은 8)·`AdmissionBindingSet`(§15 step 1-7 digest binding view)·`DependencyClosureDigestSet`(§11 17차원·§4.9)·`SoftwareReleasePolicyFieldGroups`(§8 17 `*_policy_digest`+2 bound-set·§4.3) | id 미도출·mutate 없음. §4.3/§4.9/§4.10 손전사 anchor(§6.2 drift). |
| **enum-token (`_NonTruthyStrEnum`)** | `AdmissionResult`{ADMIT/DENY/UNKNOWN}·`IndependenceResult`{INDEPENDENT/COMMON_MODE/UNKNOWN} | 어휘(§2.2). `__bool__⇒TypeError`. **(M7: `ReproductionResult` 폐기 — 템플릿은 `reproducibility_requirement_satisfied: bool`·:46)** |
| **reference (scalar/digest, 주입)** | hag independence verdict·spg envelope + `software_deployment_ok` slot·rcl worst-effect(CapacityVector 아님·§0.4g)·egress final-egress negative-gate·cur Safety Currentness Vector gen + `fence_advances_floor` floor(M4)·evidence causal-chain/gap·liveauth·authority epoch·rlp promotion·sbr recovery·**Release Generation**(SCI 생산)·**027 incident gen**(미착지)·**030 posttrade obligation gen**(M5) | 형제/미착지 소유 — 주입 좌표로만(§3.4/§3.5). |

### 2.2 어휘 (verbatim 전사 + truthy 봉인)

**(1) `AdmissionResult` (§5.7 line 127·ADMIT 양성 identity).** `ADMIT`·`DENY`·`UNKNOWN`. `_NonTruthyStrEnum`
로컬 재표현(iap `ApprovalResult`·cur `ProofResult`·wdr `DecisionResult`·**import 아님**·`__bool__⇒
TypeError`). 근거: §5.7 line 127 "An immutable single-use non-authorizing result of `ADMIT`, `DENY`, or
`UNKNOWN`." 소비 게이트 **`result is AdmissionResult.ADMIT` 명시**(§4.2·ADMIT은 잔여 공간 아님·AFG C1).
템플릿 `result: UNKNOWN`(**admission-decision:8·admitted-set:9만 `AdmissionResult`·MINOR-2** — provenance:8·
runtime:8의 result는 admission 아님·§7 line 232 "attestation is a fact, not permission"·불투명 `str | None`).

**(2) `IndependenceResult` (§9·SCI-INV-007·hag 주입).** `INDEPENDENT`·`COMMON_MODE`·`UNKNOWN`.
`_NonTruthyStrEnum`. 근거: SCI-INV-007 line 179·§9 line 267 "does not prove independence when one person
controls the underlying accounts, recovery paths, automation, or signing identities"(m5 완전 인용).
템플릿 `effective_principal_independence_result: UNKNOWN`(source-revision:23·admission-decision:29)·
`attestor_independence_result: UNKNOWN`(runtime:42). 소비 게이트 `result is IndependenceResult.
INDEPENDENT` 명시·`COMMON_MODE`/`UNKNOWN`/None ⇒ restrictive(hag-owned·§0.4e).

**(mutable-name 헬퍼) `is_mutable_name_notation(value: str | None) -> bool` (SCI-INV-002·rlp shape·
비전수 정직).** tag/branch/path/`latest`/cache는 identity 아님(SCI-INV-002 line 159). rlp `is_wildcard_
value`(state.py:118·strip+casefold+`WILDCARD_METACHARACTERS`+비전수 honesty) shape **로컬 재표현**:
`strip().casefold()` 후 (a) 빈 문자열, (b) mutable-name sentinel(`latest`·`head`·`main`·`master`·
`stable`·`current`·`edge` casefold 멤버십), (c) glob/tag/path 메타문자(`*`·`?`·`:`·`/`·`@`) 포함 ⇒
`True`. **비전수 정직(RLP #25)**: catalogued sentinel·메타문자만·신종 표기·registry resolution은 +Security/
런타임 소유. `None` ⇒ `False`(absent). RELEASE-ARTIFACT `mutable_tag_is_identity: false`(:51·음극성)는
**`release_artifact_identity_exact`(§5.4·NEW-4c) 실소비처**(NEW-5 xref 정정 — 구 "§5.1"은 SourceRevision
단일 인자라 파손). SourceRevision digest는 §5.1 item 2 `is_mutable_name_notation` 게이트(NEW-3).

**truthy 봉인(§4.2)**: 두 enum 전 멤버 `bool(x)⇒TypeError`·`is <member>` 명시만(`if result:` 부재 grep).

### 2.3 아티팩트 covered + self-exclusion + malformed-model 자기방어 (설계 #4·#26 §2.3)

- 모든 digest-bound 아티팩트는 `IndependentIdArtifact`(`_base.py:328`) 상속 — `_ID_FIELD`·`_COVERED_
  FIELDS`·`_REQUIRED_COVERED` 선언(spg·ioc·rcl·egress·cur·rlp·wdr 선례).
- **coordinate 비붕괴(설계 #4 §4.4)**: mutable lifecycle 좌표(`consumed`/`consumption_permitted`/
  `current`·:39-41·주입 verdict·`status`)는 covered digest **미포함** — 정당 전이가 CRITICAL_CONFLICT
  오탐되지 않도록.
- **malformed-model 자기방어 — positive-ADMIT + incomplete-binding coexistence seal(RLP `ExactTrialPlan`·
  egress QCC·wdr 동형·본 문서 핵심 seal)**: `ArtifactAdmissionDecision` `model_validator`가 **불완전
  binding과 `result is ADMIT` 공존을 구조로 봉인**. `result is AdmissionResult.ADMIT`인데 §15 mandated
  binding(policy·`release_artifact_binding`·source-revision·closure·provenance·compatibility·target-
  scope·`predecessor_release_generation`·`current_release_restriction_floor`) 중 하나라도 `None`/`"TBD"`/
  mutable-name이면 **`ArtifactIntegrityError` at construction**. 동일하게 `AdmittedReleaseSet`(`complete
  is True` + set-digest 부재 ⇒ 불가)·`SourceRevisionManifest`(independence `INDEPENDENT` + reviewer-set
  digest 부재 ⇒ 불가). 술어 층 2층 재확인(`model_construct` 우회 대비). **리뷰어 공격 지점(§10.2-⑥)**.
- **`_REQUIRED_COVERED`는 구조 identity/generation/digest만** — numeric age(`age_within_approved_limit`·
  admission-decision:37·provenance:43·runtime:51의 `trustworthy_time_binding`)는 **numeric bound INSTANCE**
  이므로 제외(Phase-1 null profile 하 구성 가능·§8·Gap). 누락 numeric claim은 fail-closed(§4.2).

### 2.4 핵심 모델 필드 골격 (§ref·템플릿 실명·M1 전건 정정)

> **WDR MAJOR-1 방어(§6.2)**: 골격은 **key covered field + `_ID_FIELD` + `_REQUIRED_COVERED`**만 명시·
> **전 필드는 canonical 템플릿(`*-template.yaml`)을 SoT로** 참조·§6.2 anchor-drift가 모델 필드 ↔ 템플릿
> 필드 1:1 강제. **v1.1: 전 필드명을 템플릿 실명으로 실측 치환(M1)**.

**`SoftwareReleasePolicy`(§8)** — `_ID_FIELD="policy_id"`. covered key: `policy_id`·`policy_generation`·
`canonical_digest`(**M1 — `policy_digest` 아님**)·`predecessor_policy_digest`·`scope: SupplyChainScope`
(§4.10)·**17개 `*_policy_digest`**(§4.3·`source_review_policy_digest`:19 … `evidence_policy_digest`:35)·
`approved_bound_set_digest`(:40)·`approved_limit_set_digest`(:41)·`verification_profile_binding`·
`materiality_default`(:42)·disposition 3(:43-45)·`*_permitted` 6(:46-51·음극성)·`authority:
AllFalseSupplyChainAuthority`(`policy_active` variant·M2). 활성화 spg/014 주입(§8 line 259). `_REQUIRED_
COVERED={policy_id, policy_generation, canonical_digest}`.

**`ArtifactAdmissionDecision`(§5.7/§15)** — `_ID_FIELD="decision_id"`. covered key(템플릿 실명·M1):
`decision_id`·`decision_version`·`candidate_release_generation`(**int ordering scalar·NEW-1**)·`canonical_
digest`(**M1**)·`policy_binding`·`release_artifact_binding`(id/digest·**M1 — `..._manifest_binding` 아님**)·`source_revision_
manifest_digest`(:16)·`dependency_and_toolchain_closure_manifest_digest`(:17)·`build_provenance_
attestation_digest`(:18)·`artifact_signature_and_key_status_digest`(:19)·`registry_custody_proof_
digest`(:20)·`compatibility_graph_digest`(:21)·`scan_test_and_finding_evidence_digest`(:22)·`common_
mode_analysis_digest`(:23)·`target_scope_digest`(:24)·`predecessor_release_generation`(:25)·
`predecessor_release_generation`(:25·**int·NEW-1**)·`predecessor_admitted_release_set_digest`(:26)·
**`current_release_restriction_floor`(:27·C1-2·int ordering scalar·NEW-1)**·
`reviewer_effective_principal_set_digest`(:28)·`effective_principal_independence_result: IndependenceResult`
(:29·C1 note)·`decision_reason_set_digest`(:30)·`unresolved_condition_set_digest`(:31)·`trustworthy_
time_binding`(:32-37)·**4-field consumption**(`single_use_consumption_id`:38·`consumed`:39·`consumption_
permitted`:40·`current`:41·**M1 — `single_use_consumed` 단일 bool 아님**)·`result: AdmissionResult`(:8)·
`*_permitted` 4(:43-46·음극성)·`authority: AllFalseSupplyChainAuthority`(`creates_artifact_admission_
without_release_commit`+`commits_release_generation` variant·M2). `_REQUIRED_COVERED={decision_id,
decision_version, policy_binding.software_release_policy_id, release_artifact_binding.release_artifact_
manifest_id, target_scope_digest}`. **invented bool verdict(signature_verified 등) 제거(C1-3)** — 검증
결과는 digest binding으로 담기고 실 검증은 +Security. malformed-model validator: `result is ADMIT` +
mandated binding 누락 ⇒ error(§2.3).

**`AdmittedReleaseSet`(§5.9/§16)** — `_ID_FIELD="release_set_id"`. covered key(템플릿 실명·M1):
`release_set_id`·`release_generation`·`canonical_digest`·`predecessor_release_generation`·`predecessor_
release_set_digest`·`policy_binding`·`scope: SupplyChainScope`(:14-23·9차원)·`release_artifact_manifest_
set_digest`(:24·**set-digest·member tuple 아님·M1**)·`artifact_admission_decision_set_digest`(:25)·
`artifact_lineage_graph_digest`(:26)·`consumer_compatibility_graph_digest`(:27·**M1 — `compatibility_
state_digest` 아님**)·`deployment_plan_digest`(:28)·required 3(:29-30)·trust-bundle 2(:31-32)·`release_
restriction_floor`(:33·**M1**)·`release_restriction_set_digest`(:34·**M1 — 2필드**)·`incident_scope_
binding_digest`(:35)·`owner_epoch`(:36)·`commit_record_digest`(:37)·`committed`(:38)·`complete`(:39·
**M1 — `is_complete` 아님**)·`current`(:40)·`compatibility_complete`(:41)·`restriction_state`(:42)·
`result: AdmissionResult`(:9)·`*_permitted` 5(:44-48·음극성)·`authority`. `_REQUIRED_COVERED={release_
set_id, release_generation, policy_binding.software_release_policy_id, release_artifact_manifest_set_digest}`.

**`SourceRevisionManifest`(§9)** — 리뷰어 "무결(유지)"·`_ID_FIELD="manifest_id"`. covered key: `manifest_
id`·`source_continuity_generation`·`canonical_digest`·`repository_identity`(:12)·`source_revision_
digest`(:14)·`source_tree_digest`(:15)·`source_history_head_digest`(:16)·`source_history_continuity_
proof_digest`(:17·C3 재료)·`source_review_*_digest`(:18-20)·`source_author_effective_principal_id`(:21)·
`reviewer_effective_principal_set_digest`(:22)·`effective_principal_independence_result: IndependenceResult`
(:23)·closure digests(:24-31·generated/submodule/large-file/vendored/external/schema-migration/build-
script/code-generator)·`history_rewrite_detected`(:33·음극성·C3)·`closure_complete`(:34·양극성·**M1 —
`closure_complete`는 여기 소속**)·`review_current`(:35)·`*_permitted` 4(:38-41·음극성)·`authority`
(`clears_safety_state` variant). `_REQUIRED_COVERED={manifest_id, repository_identity, source_revision_
digest, source_tree_digest}`.

**`DependencyToolchainClosureManifest`(§11)** — `_ID_FIELD="manifest_id"`. covered key: `manifest_id`·
`closure_generation`·`canonical_digest`·**17개 closure set digest**(§4.9·:15-34)·`resolution_policy_
digest`(:31)·`software_bill_of_materials_digest`(:32)·`correction_and_revocation_state_digest`(:33·M8)·
`transitive_closure_complete`(:36·양극성·**M1 — `closure_complete` 아님**)·`all_content_digests_
verified`(:37)·`all_sources_approved`(:38)·`all_corrections_and_revocations_current`(:39·M8)·`floating_
version_permitted`(:42·음극성·**M1 명제 상이 — state 아닌 policy-permission**)·`undeclared_network_
resolution_permitted`(:43)·`runtime_dynamic_resolution_permitted`(:44)·`*_patch/union_permitted`(:45-46)·
`authority`. `_REQUIRED_COVERED={manifest_id, closure_generation, resolution_policy_digest}`.

**`BuildProvenanceAttestation`(§12)** — `_ID_FIELD="attestation_id"`. covered key: `attestation_id`·
`builder_continuity_generation`·`canonical_digest`·`result: str | None`(:8·NEW-6·**MINOR-2 — provenance
result ≠ admission result·§5.2 미소비·SCI-INV-004: provenance는 ADMIT을 낼 수 없음·불투명**)·`policy_binding`(:9-12·
NEW-6)·bindings(:13-18)·build_recipe(:19-20)·builder(:21-26)·declared/observed input·environment(:27-30)·
`output_artifact_digest`(:31)·`independent_build_attestation_digest`(:33·§12 independent reproduction
anchor·NEW-6)·`reproducibility_comparison_
digest`(:34·**M1 — enum 아닌 digest**)·nondeterminism(:35-36)·`common_mode_analysis_digest`(:37)·
`trustworthy_time_binding`(:38-43·**5필드 블록·M1**)·`all_inputs_declared`(:44)·`builder_identity_
current`(:45)·`reproducibility_requirement_satisfied`(:46·양극성·**M7 — ReproductionResult enum 대체**)·
`provenance_complete`(:47)·`favorable_output_selection_permitted`(:50·음극성)·signer(:52-54)·`authority`
(`proves_semantic_correctness`+`creates_artifact_admission` variant·**M2 — SCI-INV-004 실현**). `_REQUIRED_
COVERED={attestation_id, builder_continuity_generation, output_artifact_digest}`.

**`ReleaseArtifactManifest`(§5.6)** — `_ID_FIELD="manifest_id"`. covered key: `manifest_id`·`artifact_
generation`·`canonical_digest`·**lineage 3분리 블록**(`source_revision_manifest_binding`:13-15·`dependency_
and_toolchain_binding`:16-18·`build_provenance_binding`:19-21·**M1**)·`artifact_identity`(:22)·`artifact_
content_digest`(:23·주입 opaque)·format/platform/layer(:24-26)·set digests(:27-29)·`software_bill_of_
materials_digest`(:30·**M1 — `sbom_digest` 아님**)·schema/protocol/migration(:31-33)·`consumer_
compatibility_graph_digest`(:34·**M1**)·**required 3**(`required_configuration_bundle_digest`:35·
`required_hard_safety_envelope_digest`:36·`required_broker_capability_profile_digest`:37·**M1**)·`target_
scope_digest`(:38·**M1 — `intended_deployment_scope` 아님**)·registry/signer(:39-43)·`signing_key_status:
UNKNOWN`(:44·+Security·Gap)·scan/finding(:45-46)·`lineage_complete`(:47)·`registry_custody_current`(:48)·
`compatibility_complete`(:49)·`mutable_tag_is_identity`(:51·음극성·Gap)·`*_permitted` 3(:52-54)·`authority`.
`_REQUIRED_COVERED={manifest_id, artifact_content_digest, platform_and_architecture_digest}`. (**M1 —
`dependency_closure_digest` top-level 부재·binding 블록에만**.)

**`RuntimeArtifactAttestation`(§18·M3 신규)** — `_ID_FIELD="attestation_id"`. covered key: `attestation_
id`·`runtime_continuity_generation`·`canonical_digest`·`result: str | None`(:8·**MINOR-2 — attestation
result ≠ admission·§7 line 232 "attestation is a fact, not permission"·불투명**)·`release_binding`(:9-16)·`scope: SupplyChainScope`
(:17-25·**8차원·legal_portfolio 없음·M9**)·workload/deployment(:26-30)·actual digests(:31-35)·`expected_
runtime_artifact_set_digest`(:36)·`observed_runtime_artifact_set_digest`(:37)·`runtime_artifact_match`
(:38·양극성)·`consumer_compatibility_result: UNKNOWN`(:39)·attestor(:40-42)·`release_restriction_floor`
(:44)·trustworthy-time(:46-51)·`current`(:52)·`invalidated: true`(:53·음극성 — must be False)·`self_
report_only_is_sufficient`(:55·음극성)·`desired_state_is_actual_state`(:56·음극성)·`*_permitted` 2·
`authority`. `_REQUIRED_COVERED={attestation_id, runtime_continuity_generation, observed_runtime_artifact_
set_digest}`. 술어는 +L2/+Security(not-Phase-1)·`software_deployment_ok_verdict`(§5.6e)가 `runtime_
artifact_match`(:38)·`current`(:52) 소비.

**`ReleaseRestriction`(§5.11/§16/§20·템플릿 없음·ADR-파생)** — `_ID_FIELD="restriction_id"`. covered key:
`restriction_id`·`restriction_generation`·`restricted_scope: SupplyChainScope`(greatest credible closure·
§20)·`trigger_class: str`·`predecessor_restriction_digest`·`authority: AllFalseSupplyChainAuthority`.
`_REQUIRED_COVERED={restriction_id, restriction_generation, restricted_scope}`. §5.11 "A monotonic scope-
complete fact … cannot support future new-risk permission." **restriction은 clear/revoke 불가**(§20 line
406·SCI-INV-016)·**floor advance ordering은 cur `fence_advances_floor` 소유**(§5.6c·M4).

**`AllFalseSupplyChainAuthority`(all-false·SCI-INV-001·§7·M2 — 템플릿 실명 20필드 union).** 템플릿별
authority 블록이 변동하므로(실측) **관측된 전 필드의 union**을 담고 전부 `= False` default·`model_
validator` any-True ⇒ `ArtifactIntegrityError`(rcl/egress/cur/rlp/wdr `AllFalse*Authority` 동형·**로컬
재표현·import 아님**). union 20필드(축별 출처 anchor·§6.2): `active`(대부분)/`policy_active`(policy:56)·
`creates_source_approval`·`creates_artifact_admission`(**M2 필수 복원 — §5.2 SCI-INV-004 논증의 핵심**·
admitted-set:52·source-revision:48·release-artifact:58·dependency:53·provenance:58·runtime:61)/`creates_
artifact_admission_without_release_commit`+`commits_release_generation`(decision:50-51 variant)·`proves_
semantic_correctness`(provenance:57 variant·SCI-INV-004)·`deploys_software`·`activates_configuration`·
`creates_capacity`·`mutates_or_releases_capacity`·`creates_protective_classification`·`creates_live_
authorization`·`creates_transmission_capability`·`permits_broker_transmission`·`clears_safety_state`
(source/release-artifact/dependency/provenance)/`clears_halt_latch_gap_restriction_or_incident`
(decision/admitted-set/runtime/policy)·`establishes_recovery_readiness`·`restores_scope`·`permits_rearm`.
근거: SCI-INV-001 line 155 verbatim(전 축 열거). **§6.2 anchor**: 각 템플릿 authority 블록 ⊆ union·
per-template native 필드 주석.

---

## 3. canonical / ordering REUSE + sibling edge 0 + 형제 경계 (§3.5 노른자)

### 3.1 canonical REUSE
`tos.canonical` REUSE(import): `IndependentIdArtifact`(`_base.py:328`)·`classify_record_pair`+`RecordPairKind`
{IDEMPOTENT_DUP/CRITICAL_CONFLICT/DIVERGENT_EMISSION/DISTINCT/NOT_COMPARABLE}(`record_pair.py:31/52`·
policy/decision/release-set/restriction append-only 무결성·same-`*_id`/different-bytes)·`CanonicalDecimal`·
`FrozenModel`·`EVL1ProvisionalCanonicalizer`. pre-issuance(digest None) ⇒ `NOT_COMPARABLE`(`record_pair.py:87`).

### 3.2 ordering REUSE
`tos.ordering` REUSE(`compare_order`): Release Generation monotonic fence(§5.8)·predecessor floor(§16)·
rollback-new-generation(§22·SCI-INV-012)·**restriction 순서 정합(단 floor advance mechanism은 cur·M4)**.
**PROMOTE 0**. clock-free(`MAX_*_ms` wall-clock age는 secondary +Security/INSTANCE·§8).

### 3.3 REUSE 요약 표
| 대상 | 결정 | 근거 |
|---|---|---|
| `tos.canonical`(IndependentIdArtifact·classify_record_pair·RecordPairKind·CanonicalDecimal·FrozenModel·EVL1ProvisionalCanonicalizer) | **REUSE (import)** | base digest substrate·전 시리즈 선례 |
| `tos.ordering`(compare_order) | **REUSE (import)** | Release Generation floor·predecessor·rollback-new-gen |
| 형제 tos 패키지 전부(rcl·spg·hag·iap·egress·cur·evidence·liveauth·authority·time·ioc·are·afg·sbr·capsule·venue·protective·recon·brokercap·orthostate·dsl·nontrade·replacement·**posttrade[착지]**·rlp·wdr·failuredomain + 미래 **sir/stm**) | **NO import (sibling edge 0)** | 주입 좌표로만(§3.4). rcl edge 0·§0.4g. **(M5: posttrade 착지·미착지는 sir/stm뿐; firewall 배제 목록은 구 placeholder `tos.ptf` 사용)** |
| `_NonTruthyStrEnum`·`AllFalseSupplyChainAuthority`·`is_mutable_name_notation` | **로컬 재표현 (import 아님)** | iap/cur/wdr·rcl/egress/cur/rlp/wdr·rlp `is_wildcard_value` 선례 |

### 3.4 sibling edge 0 정책
SCI는 **어떤 형제 tos 패키지도 import하지 않는다**(canonical·ordering 제외). 형제/미착지 owner의 verdict/
generation/digest는 전부 **주입 좌표**. **PROMOTE 0**. import-closure allowlist `⊆ {canonical, ordering,
sci}`(§7.1).

### 3.5 소유권 / seam 분할표 (본 문서 최대 함정 — 코드 실측·v1.1 전수 재검증)

| ADR 조항/개념 | SCI 소유 (Phase 1) | 형제 소유 (재저작 금지·실측) | seam·명제 동일성 |
|---|---|---|---|
| **§18/§1 `software_deployment_ok`**(produced-value·착지 소비자) | admission ADMIT ∧ attestation-match ∧ currentness ∧ no-restriction ⇒ bool fold(`software_deployment_ok_verdict`·§5.6e) | **spg** `software_deployment_ok: bool\|None`(`records.py:206`·step 8·`records.py:190`)·gate `is not True`(`predicates.py:467`) | brokercap #10 decoupled seam·SCI producer·spg consumer·**import edge 0**·§6.2 seam test |
| **§8/§16 BundleMember 7-item 이연(M5 정정)** | Release Generation·compatibility graph·runtime-attestation requirements·software compatibility manifests(4/7) | **spg** `vocabulary.py:185-187` verbatim "(Release Generation, compatibility graph, runtime-attestation requirements, **Post-Trade Obligation Generation, obligation/finality compatibility, software compatibility manifests, referenced policy objects**) are owned by **ADR-002-029/030** and deferred to Phase-0 bundle-binding" | spg가 -029/-030 공동 owner로 지명·SCI가 4항목 content 생산·spg는 `BundleMemberRef`로 Phase-0 주입 |
| **§23/§29 Post-Trade 지분(M5 신규·posttrade 착지)** | (미소유) | **posttrade**(ADR-002-030·**착지** `tos/src/tos/posttrade/`) — spg 7-item 중 Post-Trade Obligation Generation·obligation/finality compatibility(2/7) | SCI ≠ posttrade — 둘 다 spg 7-item deferral에 지명되나 항목 분할(SCI 4·posttrade 2·referenced policy objects 1 공유)·**SCI는 posttrade import 0**(negative-seam) |
| **§4.1/RFC §24.1 supply-chain 좌표 4종** | (미소유) governance content만 | **failuredomain** `FailureDomainKind.{SOURCE_REPOSITORY,BUILD_TOOLCHAIN,ARTIFACT_SIGNING,ARTIFACT_REGISTRY}`(`vocabulary.py:89-95`) | coordinate/governance split·`vocabulary.py:59-60`·SCI 4좌표 재소유 안 함(negative-seam) |
| **§9/§12 effective-principal independence** | (미소유) `independence_unproven_is_common_mode`(§5.1) | **hag** collapse/quorum(#20·ADR-002-015) | hag #20 liveauth 선례·SCI는 `IndependenceResult` verdict 주입·재저작 안 함(§0.4e) |
| **§7/§23 capacity** | (미소유) worst-effect envelope 주입 opaque | **rcl** `CapacityVector`·`within_limits` | §7:235·§23:451·**edge 0**(§0.4g) |
| **§16/§20 restriction floor advance(M4 신규 봉합)** | ReleaseRestriction=supply-chain 도메인 **사실** 생산(`trigger_class`·`restricted_scope`·greatest-scope·비-소생·§5.6c) | **cur** `RestrictiveFenceRecord`(`records.py:315`, `IndependentIdArtifact`)·`fence_advances_floor`(`predicates.py:415`)·`AllFalseCurrentnessAuthority` | **명제 분리**: SCI가 restriction FACT 생산·cur가 범-아티팩트 fence 순서화·floor 전진 소유(§20:404 "through ADR-002-024"). SCI `restriction_is_monotonic_non_revival`은 floor advance 재저작 아님(§5.6c)·docstring 분리 선언. **cur `AllFalseCurrentnessAuthority` ↔ SCI `AllFalseSupplyChainAuthority`는 pattern-only 중복**(각 로컬·import 0·필드 상이). §6.2 negative-token에 `RestrictiveFenceRecord`/`fence_advances_floor` 부재 assert. **NEW-1: floor 좌표는 `int` ordering scalar**(cur `quorum_commit_index` 정합)·SCI는 `restriction_floor_not_behind`(not-behind)·cur는 `floor_strictly_advances`(strict advance)로 명제 분리 |
| **§7/§19 final egress·currentness** | (미소유) `active_currentness_is_negative_gate`(§5.6d) | **egress**(#22)·**cur**(#23·Safety Currentness Vector·per-send transaction) | §19:389·negative gate·SCI는 release facts 생산(하류 cur 소비·forward)·재저작 안 함 |
| **§7/§13/§17 config activation·protection·production·live** | (미소유) | **spg**(014 activation)·**protective**·**rlp**(#25)·**liveauth** | §7:233/236·§17:360·SCI all-false·주입·발급 안 함 |
| **§7/§24 evidence·recovery·re-arm** | (미소유) non-revival 구조(§5.6) | **evidence**(016)·**sbr**(017)·**authority/liveauth**(re-arm) | §24:467/469·SCI는 record 생산·custody evidence·재저작 안 함 |
| **§20 incident handoff(미착지 -027)** | (미소유) generation/digest 주입 | **sir(-027·미착지)** | §20:406·**코드 인용 0·조건부 seam**(§0.4f) |
| **dsl `AdmissibilityResult`(명제-동일성 비-seam)** | (무관) | **dsl** `AdmissibilityResult`(`evidence.py:58`)·"separate from ADR-002-029 software-artifact admission"(`evidence.py:66`) | dsl "admissibility"(command) ≠ SCI "admission"(release)·**소비 seam 아님·disambiguation**(anti-phantom 확증) |

> **핵심 소유권 판정(명제-동일성 함정 봉합)**: (1) **spg produced-value seam**(records.py:206·SCI producer·
> spg consumer·edge 0). (2) **FD coordinate/governance split**(vocabulary.py:89-95·SCI 재소유 0). (3) **hag
> instance-consumer**(collapse hag-owned·SCI verdict 주입). (4) **cur fence 분리(M4)**: SCI가 restriction
> FACT 생산·cur `fence_advances_floor`가 floor advance 소유·재저작 0. (5) **posttrade 분할(M5)**: spg 7-item
> deferral을 SCI 4·posttrade 2로 분할·상호 import 0. (6) **dsl 비-seam**: disambiguation note.

---

## 4. ADR 조항 + 템플릿 verbatim 전사표 (field/row group 통째 누락 금지 — WDR MAJOR-1)

> **규율(§6.2)**: §6 INV(16)·§7 owner(17)·§8 policy(9 산문 group·17 template digest)·§11 closure(17)·§15
> admission(10)·§16 scope(9)·§19 currentness(8)·§21 failure(12)·§27 AC(12)·§30 gate(14)를 전사·§6.2 drift-
> anchor가 1:1 강제.

### 4.1 SCI-INV-001..016 (§6 line 153-215, verbatim 제목)
001 Supply-Chain Artifacts Are Not Authority / 002 Artifact Identity Is Exact and Immutable / 003 Source-
to-Artifact Lineage Is Closed / 004 Provenance Is Not Correctness / 005 Dependency and Toolchain Closure Is
Complete / 006 Admission Is Deterministic and Exact-Scope / 007 Effective Independence Is Required / 008
Signature Is Not Current Admission / 009 One Complete Release Generation Governs Scope / 010 Actual Runtime
Bytes Must Match / 011 Unknown Compatibility Is Incompatibility / 012 Rollback and Restore Are New
Generations / 013 Active Release Currentness Is a Negative Gate / 014 Restriction Dominates Send Races /
015 Economic Effect Outlives Artifact State / 016 Evidence and Recovery Do Not Revive.

### 4.2 §7 Authority Ownership 17행 (line 221-241, verbatim Action→Owner)
Propose source change→source author / Approve exact source revision→independent source-review authority /
Build artifact and provenance→fenced build service / Resolve dependency-toolchain closure→governed resolver
and verifier / Sign artifact or attestation→independently controlled artifact signer / Store and retrieve
artifact→immutable artifact registry / Decide artifact admission→independent Release Admission Authority /
Commit Release Generation→fenced Release Registry / ordering domain / Deploy exact admitted artifact→
deployment controller / Attest actual runtime bytes→independent runtime-attestation path / Activate
configuration→ADR-002-014 governance / Restrict current use→ADR-002-024 restrictive path and existing
owners / Mutate or release capacity→**Risk Capacity Ledger only** / Classify protection→Protective Action
Controller / Declare or close incident→ADR-002-027 governance / Transmit→Broker Adapter / Egress Gateway /
Establish readiness and re-arm→ADR-002-017 then ADR-002-007/015. **line 241**: "No source, build,
dependency, signing, registry, admission, deployment, attestation, scan, CI/CD, evidence, or replay
identity may hold a usable live-order credential and broker route."

### 4.3 §8 Software Release Policy — 9 산문 group (line 249-257) + 17 template `*_policy_digest` (M1)
산문 9 group: 1.exact policy identity·generation·digest·predecessor·scope / 2.source repositories·review·
effective-principal·history / 3.build recipes·builders·network·determinism·nondeterminism / 4.dependency·
toolchain·package-source·base-image·plugin·code-generation·runtime-loading / 5.provenance·independent-build·
reproducibility·differential·scan·test·evidence / 6.signer·key·threshold·rotation·revocation·registry·
custody / 7.artifact-manifest·admission·compatibility·deployment·runtime-attestation·Release Generation /
8.restriction·incident·rollback·restore·hotfix·recovery·final-egress currentness / 9.numeric bounds·age
limits. **template 17 `*_policy_digest`(SOFTWARE-RELEASE-POLICY:19-35)**: source_review·effective_principal·
build_recipe·builder_identity·build_network·determinism_and_reproducibility·dependency_and_toolchain·
package_source·artifact_signing_and_key·artifact_registry_custody·artifact_admission·compatibility·
deployment_promotion·runtime_attestation·restriction_and_incident·recovery_and_restore·evidence + `approved_
bound_set_digest`(:40)·`approved_limit_set_digest`(:41). **line 259**: "Unknown fields, mutable references,
hidden defaults … or `latest` resolution are prohibited."

### 4.4 §15 Admission Protocol 10 step (line 325-336, verbatim)
1.bind exact current Software Release Policy and target scope / 2.verify Source Revision Manifest identity·
review·continuity·effective-principal independence / 3.verify complete dependency and toolchain closure and
correction state / 4.verify Build Provenance Attestation·builder epoch·output digest·required independent
reproduction / 5.verify Release Artifact Manifest·signature·registry custody·schemas·protocols·migrations·
compatibility graph / 6.verify required scans·tests·evidence receipts·unresolved findings without treating
them as authority / 7.verify predecessor Release Generation and every current restriction floor / 8.issue one
immutable `ADMIT`/`DENY`/`UNKNOWN` decision / 9.independently commit any eligible `ADMIT` into one new
complete Admitted Release Set and Release Generation / 10.invalidate single-use decision and every stale
competing candidate. **line 338**: "Decisions cannot be patched, unioned, replayed, widened, or silently
re-evaluated with newer favorable inputs."

### 4.5 §19 Active Currentness 8-item (line 376-385, verbatim)
1.Software Release Policy identity·generation·digest / 2.Release Generation·Admitted Release Set digest /
3.applicable Release Artifact Manifest·lineage-graph digests / 4.artifact-signing trust-bundle·key-status
generation / 5.deployment·workload·environment·Safety Cell·runtime-attestation identities / 6.compatibility
result for every consumer·broker-egress edge / 7.restriction floors·incident scope·stale-owner fences /
8.approved ages·trustworthy-time evidence·invalidation state. **line 389**: "Final egress verifies exact
facts and conformance; … Failure or ambiguity denies new risk. No valid release state can override a HALT,
UNKNOWN, capacity denial, venue denial, approval denial, or any other restrictive fact." (**negative-gate
verbatim은 §1 line 27**, §5.6d 참조·m1.)

### 4.6 §21 Partition/Failure 12행 (line 412-425, verbatim Failure→Result)
source/review history unavailable/conflicting→quarantine;deny / builder/dep-source/toolchain/signer/registry
unavailable→no favorable fallback;effects persist;new admission denied / admission registry·Release Generation
conflict→fence writers;deny scope / control plane partitioned + broker egress reachable→final egress denies
unless exact current release state independently proven / retrieval digest/platform/layer/signature mismatch→
quarantine;restriction+incident / runtime attestation missing/stale/mixed/conflicting→deny;treat scope unknown /
deployment queue backpressure→do not extend admission or drain by enabling send / revocation delivery delayed/
lost→independent restrictive ingress+local latch preserve denial / signer/registry compromise suspected→
restrict greatest credible shared scope;rotate/fence;preserve history / evidence/scanner unavailable→gap;no
admission or PASS / unknown instance remains→potentially active until hard-fenced;live authority denied /
recovery completes→no revival;fresh admission/recovery/re-arm mandatory. **line 427**: "No retry, mirror,
cache, alternate registry, previous artifact, emergency signer, manual copy, or operator assertion may select
a more permissive state when provenance, ordering, currentness, or scope is unknown."

### 4.7 SCI-AC-001..012 (§27 line 552-598, verbatim 제목·AC↔EV 1:1)
001 Source Identity and Review Integrity / 002 Build Isolation, Provenance, and Reproducibility / 003
Dependency and Toolchain Closure / 004 Signer, Key, and Attestation Compromise / 005 Registry Custody and
Artifact Substitution / 006 Independent Admission and Compatibility / 007 Release Generation and Stale Fencing /
008 Deployment Attestation and Environment Confinement / 009 Mixed Version, Promotion, Rollback, and Restore /
010 Active Currentness, Revocation, Partition, and Send Race / 011 Authority Separation, Broker Finality, and
Economic Continuity / 012 Evidence, Recovery, Hotfix, and Non-Revival. **§27 line 550**: "Written cases
define obligations only. They are not completed evidence."

### 4.8 §30 Approval Gate 14항 (line 641-658, 핵심)
1.8 canonical schema 승인 / 2-9.source/build/signer/admission/deployment/currentness/rollback security-review·
fault-injection / 10.numeric bounds VP 승인+측정 / 11.**SCI-EV-001..012 executed·retained·independently
reviewed** / 12.negative/missing/conflicting/rollback/restore/stale outcomes 보존 / 13.no Critical/Major open /
14.Architecture Gate explicit·document review alone ↛ promote. **⇒ Phase-1은 게이트 1·11의 EV-L1 layer 일부만
저작·2-10·12-14 전부 잔존**(§9).

### 4.9 §11 Dependency/Toolchain Closure — 17 template set digest (DEPENDENCY-...-MANIFEST:15-34·M8)
`build_dependency_set_digest`(:15)·`runtime_dependency_set_digest`(:16)·`build_script_set_digest`(:17)·
`plugin_set_digest`(:18)·`compiler_and_linker_set_digest`(:19)·`interpreter_set_digest`(:20)·`sdk_set_
digest`(:21)·`code_generator_set_digest`(:22)·`base_image_set_digest`(:23)·`operating_system_package_set_
digest`(:24)·`native_library_set_digest`(:25)·`dynamic_module_set_digest`(:26)·`sidecar_and_proxy_component_
set_digest`(:27)·`migration_tool_set_digest`(:28)·`signer_component_set_digest`(:29)·`package_source_set_
digest`(:30)·`compatibility_edge_set_digest`(:34) + `resolution_policy_digest`(:31)·`software_bill_of_
materials_digest`(:32)·`correction_and_revocation_state_digest`(:33). §11 line 285-289 근거. §5.3 판정 대상.

### 4.10 SupplyChainScope — 9 template scope 차원 (M9)
9차원(POLICY:9-18·ADMITTED-SET:14-23): `environment`·`safety_cell`·`capacity_domain`·`legal_portfolio`·
`account_scope_digest`·`broker_scope_digest`·`component_scope_digest`·`dependency_closure_digest`·`scope_
complete`. **RUNTIME-ARTIFACT-ATTESTATION은 8차원**(:17-25·**`legal_portfolio` 없음**·M9 변동 명기).
§5.4 item 6 `scope_complete is True` 게이트.

---

## 5. 핵심 L1 술어 (§5 — 5 노른자 + cross-cutting 구조 술어)

### 5.0 극성 규율 (§0.5-5·템플릿 실필드만·M7 재작성)

**규율**: 음극성 clear는 **`is False`만**(`is not True` 금지·None을 clear로 오독하는 fail-open). 양극성
allow `is True`. None 양쪽 deny. **v1.1: phantom 필드(`source_continuity_proven`·`predecessor_conflict_
present`·`floating_resolution_present`) 폐기·tri-state/bool 이중표현(`reproduction_disagrees`·`compatibility_
unknown`·`identity` 2종) 제거·전 필드 템플릿 실명(M7)**.

| 필드(템플릿 실명) | 극성 | clear | deny | 근거 |
|---|---|---|---|---|
| SourceRevision `history_rewrite_detected`(:33) | **음극성** | `is False` | `is not False` | §9 line 269·C3 |
| SourceRevision `closure_complete`(:34)·`review_current`(:35) | **양극성** | `is True` | `is not True` | §9·SCI-INV-003 |
| Dependency `transitive_closure_complete`(:36)·`all_content_digests_verified`(:37)·`all_sources_approved`(:38)·`all_corrections_and_revocations_current`(:39) | **양극성** | `is True` | `is not True` | §11·SCI-INV-005·M8 |
| Dependency `floating_version_permitted`(:42)·`undeclared_network_resolution_permitted`(:43)·`runtime_dynamic_resolution_permitted`(:44) | **음극성** | `is False` | `is not False` | §11 line 289·**명제=policy-permission·M1** |
| Provenance `all_inputs_declared`(:44)·`builder_identity_current`(:45)·`reproducibility_requirement_satisfied`(:46)·`provenance_complete`(:47) | **양극성** | `is True` | `is not True` | §12·SCI-INV-004·**M7 reproduction bool** |
| Provenance `favorable_output_selection_permitted`(:50) | **음극성** | `is False` | `is not False` | §12 line 299 |
| ReleaseArtifact `lineage_complete`(:47)·`registry_custody_current`(:48)·`compatibility_complete`(:49) | **양극성** | `is True` | `is not True` | §5.6·§14 |
| ReleaseArtifact `mutable_tag_is_identity`(:51) | **음극성** | `is False` | `is not False` | SCI-INV-002·Gap |
| Decision `current_release_restriction_floor`(:27·**int·NEW-1**) via `restriction_floor_not_behind` | **양극성(구조)** | present ∧ not-behind(BEFORE/equal) | absent/AFTER/**AMBIGUOUS**/None | §15 step 7·C1·NEW-1 |
| Decision `consumed`(:39) | **음극성** | `is False` | `is not False` | §15 step 10·single-use·M1 |
| Decision `current`(:41)·AdmittedSet `complete`(:39)·`committed`(:38)·`current`(:40)·`compatibility_complete`(:41) | **양극성** | `is True` | `is not True` | §16·M1·**§5.4/§5.5 실소비·NEW-4** |
| AdmittedSet `restriction_state`(:42·enum) | **양성 identity** | positively-resolved(UNKNOWN 아님·비-restricted 값=template INSTANCE) | `is UNKNOWN`/None | §16·NEW-4 |
| Decision/Set `*_permitted`(patch/union/widen/readmit/partial/favorable-subset/historical-reuse) | **음극성** | `is False` | `is not False` | §15 line 338·§16 line 346·SCI-INV-006/009 |
| Scope `scope_complete`(:23) | **양극성** | `is True` | `is not True` | §16·M9 |
| Runtime `runtime_artifact_match`(:38)·`current`(:52) | **양극성** | `is True` | `is not True` | §18·SCI-INV-010 |
| Runtime `invalidated`(:53)·`self_report_only_is_sufficient`(:55)·`desired_state_is_actual_state`(:56) | **음극성** | `is False` | `is not False` | §18 line 368-370 |
| `software_deployment_ok_verdict` args `runtime_attestation_matches`·`active_currentness_current`·`restriction_state_resolved` | **양극성** | `is True` | `is not True` | §5.6e·M6 |
| `software_deployment_ok_verdict` arg `restriction_present` | **음극성** | `is False` | `is not False` | §5.6e·M6 |

**ordering 헬퍼 2종(NEW-1·`compare_order`는 `OrderingEvent` 전용·str 불가·`Ordering`{BEFORE/AFTER/AMBIGUOUS}
미매핑 시 fail-open)**. generation/floor 좌표는 **`int | None` ordering scalar**(cur `quorum_commit_index:
int`·`ordering/_ordering.py:58`). 두 로컬 헬퍼(cur `floor_strictly_advances`(`cur/state.py:190`) shape
REUSE·**import 아님**·`_NonTruthyStrEnum` 선례 동형·내부 `OrderingEvent(quorum_commit_index=...)` wrapping):
- `restriction_floor_not_behind(decision_floor: int | None, active_floor: int | None) -> bool` — None ⇒
  `False`; `decision_floor == active_floor` ⇒ `True`(현재 restriction 반영); else `compare_order(Ordering
  Event(quorum_commit_index=active_floor), OrderingEvent(quorum_commit_index=decision_floor)) is Ordering.
  BEFORE`(active가 decision보다 앞 ⇒ decision 앞섬 ⇒ not-behind) ⇒ `True`; **`Ordering.AFTER`(decision
  뒤짐)·`Ordering.AMBIGUOUS` ⇒ `False`(deny 명시)**. (§5.4 item 4.)
- `generation_strictly_advances(predecessor: int | None, successor: int | None) -> bool` — None ⇒ `False`;
  `compare_order(OrderingEvent(quorum_commit_index=predecessor), OrderingEvent(quorum_commit_index=
  successor)) is Ordering.BEFORE` ⇒ `True`; **equal(§5.8 reuse 금지)·`Ordering.AMBIGUOUS`·`AFTER` ⇒
  `False`**(cur `floor_strictly_advances`와 동일 극성). (§5.4 item 8·§5.6b.)

**리뷰 정신 대비 정합(보고 b)**: 리뷰어는 단일 `restriction_floor_not_behind` 치환을 지시했으나, item 8·
§5.6b는 **generation 좌표**(reuse=equal 금지·strict advance 필수·§5.8 line 131)이고 floor(item 4)는
at-or-ahead(equal 허용)라 명제가 달라 2종으로 분리했다 — floor 헬퍼를 generation에 쓰면 equal(reuse)이
통과하는 fail-open. 두 헬퍼 모두 str 불가·`AMBIGUOUS⇒deny`·OrderingEvent wrapping·cur shape REUSE라 리뷰
핵심 처방(str 금지·AMBIGUOUS 봉인)을 완전 충족.

**tri-state enum 게이트(양성 identity·§0.5-4)**: `result is AdmissionResult.ADMIT`·`... is IndependenceResult.
INDEPENDENT` — 양성 멤버만 통과(잔여 공간 금지).

**전수 점검 회귀(`test_sci_polarity.py`·§6.3)**: 음극성 필드 None 입력 ⇒ deny 수렴·`is not True`가 음극성
소비에 부재 grep. **tri-state→bool 투영 뮤턴트 KILLED**(M7).

### 5.1 `source_identity_exact_and_reviewed` (SCI-EV-001 노른자·§9·§15 step 2·+Security 잔여)

**시그니처**: `source_identity_exact_and_reviewed(manifest: SourceRevisionManifest | None) -> bool`.

**판정(전부 AND·fail-closed)**:
1. **∅-seal**: `manifest is None` ⇒ `False`.
2. **exact digest identity 게이트(양성·SCI-INV-002·NEW-3 회귀 복원)**: `source_revision_digest`(:14)·
   `source_tree_digest`(:15)·`source_history_head_digest`(:16) 전부 present·concrete AND **각각
   `is_mutable_name_notation(...) is False`**(음극성 실게이트 — `source_revision_digest="latest"` 류를
   거부·지지 술어 `mutable_name_is_not_identity` 실소비·**v1.1의 비-게이트 서술 회귀 복원**). `repository_
   identity`(:12)는 mutable name일 수 있으나 **identity를 대체하지 않는다**(비-게이트 note로 분리·§1 line
   19 "A branch, tag, package name, registry path … is not artifact identity"·**§1:19**).
3. **effective-principal independence(hag 주입·양성 identity)**: `effective_principal_independence_result
   is IndependenceResult.INDEPENDENT`(:23). `COMMON_MODE`/`UNKNOWN`/None ⇒ deny(§9·SCI-INV-007·hag-owned).
4. **continuity(음극성+양성·C3 정정)**: `history_rewrite_detected is False`(:33·음극성·`is not False`⇒deny)
   AND `source_history_continuity_proof_digest`(:17) present·concrete AND `review_current is True`(:35).
   (**phantom `source_continuity_proven` 폐기·C3**·§9 line 269 "Force push, history rewrite … invalidates
   affected unconsumed admission".)
5. **closure present(양극성)**: `closure_complete is True`(:34) AND generated/submodule/external closure
   digests(:24-31) present·concrete(§9·SCI-INV-003).

**반환**: 전부 성립시에만 `True`. **SCI-EV-001을 닫지 않음**(`/3`+`+Security` — 실 effective-principal
collapse "한 사람 여러 계정" 저항은 hag + +Security). **지지**: `mutable_name_is_not_identity`·`independence_
unproven_is_common_mode`.

### 5.2 `provenance_is_not_admission` (SCI-EV-002 노른자·§12·SCI-INV-004·+Security 잔여)

**시그니처**: `provenance_is_not_admission(attestation: BuildProvenanceAttestation | None) -> bool`.

**판정(전부 AND·fail-closed·핵심: provenance-valid는 필요조건이지 admission/correctness 아님)**:
1. **∅-seal**: `attestation is None` ⇒ `False`.
2. **builder continuity(양극성)**: `builder_identity_current is True`(:45) AND `all_inputs_declared is
   True`(:44)(§10 line 279·§12).
3. **reproduction 만족(양극성·§12 line 299·M7 — bool)**: `reproducibility_requirement_satisfied is True`
   (:46) AND `favorable_output_selection_permitted is False`(:50·음극성 — §12 line 299 "the release process
   cannot select the favorable artifact"). 실 바이트 비교(`reproducibility_comparison_digest`:34)는 주입·+L2.
4. **provenance ≠ correctness ≠ admission 구조 봉인(SCI-INV-004·핵심·M2)**: `attestation.authority.proves_
   semantic_correctness is False`(:57) AND `attestation.authority.creates_artifact_admission is False`(:58).
   (**M2 — `creates_artifact_admission` 복원 없으면 본 논증이 공허**.) `provenance_complete is True`(:47)이되
   이는 admission을 부여하지 않는다(§15 step 4 하나일 뿐).

**반환**: 전부 성립시에만 `True`. **SCI-EV-002를 닫지 않음**(`/2`·`/3`·+Security — hermetic build·독립
재현·common-mode 분석은 +L2/+Security).

### 5.3 `closure_complete_or_restrictive` (SCI-EV-003 노른자·§11·SCI-INV-003/005·+Security 잔여·M8)

**시그니처**: `closure_complete_or_restrictive(manifest: DependencyToolchainClosureManifest | None) -> bool`
(**M1 — `declared_input_present` 3분기 폐기·∅⇒deny 결정적·리뷰어 ⑦**).

**판정(전부 AND·fail-closed·∅⇒deny)**:
1. **∅-seal**: `manifest is None` ⇒ `False`. **∅ closure**(17차원 set digest 전부 absent) ⇒ `transitive_
   closure_complete`가 True일 수 없음 ⇒ `False`(§0.5-2·§1 line 17 "incompletely closed … grants zero
   eligibility").
2. **17차원 closure + correction present·concrete(§4.9·M8·NEW-7 결정적 정의)**: `resolution_policy_
   digest`(:31) present AND **`resolution_policy_digest`가 명시 배제하지 않은 §4.9 전 17 set digest**가
   present·concrete("declared 축" 폐기 — 배제되지 않은 전 축 필수·resolution policy가 배제-집합의 SoT).
   `correction_and_revocation_state_digest`(:33) present.
3. **completeness/verification(양극성)**: `transitive_closure_complete is True`(:36·**M1 — `closure_complete`
   아님**) AND `all_content_digests_verified is True`(:37) AND `all_sources_approved is True`(:38) AND
   `all_corrections_and_revocations_current is True`(:39·M8·§11 line 289 "unresolved correction is
   restrictive").
4. **no floating/dynamic(음극성·명제=policy-permission·M1)**: `floating_version_permitted is False`(:42)
   AND `undeclared_network_resolution_permitted is False`(:43) AND `runtime_dynamic_resolution_permitted
   is False`(:44). §11 line 289 "Missing dependency, floating version, mutable package source … is
   restrictive". **음극성 `is False`만**.

**반환**: 전부 성립시에만 `True`. **SCI-EV-003을 닫지 않음**(+Security — transitive resolution·common-mode
source 분석 +L2/+Security). **exactness 정직(§0.5-8)**: mutable-source 감지 비전수.

### 5.4 `admission_admits_only_positive` (SCI-EV-006 노른자·§15·SCI-INV-006·ADMIT 양성·C1 전면 개정)

**시그니처(C1·NEW-1·NEW-2·MINOR-1)**: `admission_admits_only_positive(decision: ArtifactAdmissionDecision |
None, active_restriction_floor: int | None, restriction_floor_resolved: bool | None, target_scope:
SupplyChainScope | None, scope_resolved: bool | None, release_artifact_manifest: ReleaseArtifactManifest |
None, manifest_resolved: bool | None) -> bool`. (**NEW-1 floor는 `int` ordering scalar·NEW-2 scope는 주입·
MINOR-1 release-artifact-manifest는 주입** — decision은 `release_artifact_binding`(id/digest)만 담고
manifest 객체는 별도 주입이라 `release_artifact_identity_exact` 배선 완결·item 11.)

**판정(전부 AND·fail-closed)**:
1. **∅-seal**: `decision is None` ⇒ `False`. `restriction_floor_resolved is not True` ⇒ `False`(조회 실패
   보수·C1).
2. **ADMIT 양성 identity(§0.5-4·AFG C1·truthy 봉인)**: `decision.result is AdmissionResult.ADMIT`(잔여
   공간 아님·§5.7).
3. **exact-scope binding 완전성(구조 파생·§15 step 1-6·no-mutable-name)**: policy_binding·`release_artifact_
   binding`(id/digest)·`source_revision_manifest_digest`(:16)·`dependency_and_toolchain_closure_manifest_
   digest`(:17)·`build_provenance_attestation_digest`(:18)·**`artifact_signature_and_key_status_digest`(:19)·
   `registry_custody_proof_digest`(:20)·`compatibility_graph_digest`(:21)·`scan_test_and_finding_evidence_
   digest`(:22)**(**C1-1 — signature/custody/compatibility/scan 4 binding 소비**)·`common_mode_analysis_
   digest`(:23)·`target_scope_digest`(:24) 전부 present·concrete·`is_mutable_name_notation` False. 하나라도
   None/`"TBD"`/mutable ⇒ not-admitted(malformed-model validator 2층·§2.3). **실 검증(서명 유효성·scan
   clean)은 digest에 봉입된 +Security 결과** — SCI는 binding 구조 완전성만(§0.2 over-realization).
4. **restriction floor(§15 step 7·C1-1·NEW-1 헬퍼)**: `restriction_floor_resolved is not True ⇒ False`.
   `decision.current_release_restriction_floor`(:27·int) present·concrete AND `restriction_floor_not_
   behind(decision.current_release_restriction_floor, active_restriction_floor)`(§5.0 ordering 헬퍼·
   **`Ordering.AMBIGUOUS` ⇒ deny·str 전달 금지**). active floor보다 뒤진 decision floor(`Ordering.AFTER`)
   ⇒ not-admitted(§15 step 7 "every current restriction floor").
5. **independence(§15 step 2·C1 note)**: `decision.effective_principal_independence_result is
   IndependenceResult.INDEPENDENT`(:29).
6. **scope 완전성(M9·NEW-2 도달 가능)**: `scope_resolved is not True ⇒ False`. `decision.target_scope_
   digest`(:24) present AND `target_scope.scope_complete is True`(주입 `SupplyChainScope`·§4.10·양극성)·
   no-mutable.
7. **no patch/union/widen/readmit(SCI-INV-006·음극성)**: `decision_patch_permitted`(:43)·`decision_union_
   permitted`(:44)·`scope_widening_permitted`(:45)·`automatic_readmission_permitted`(:46) 전부 `is False`.
8. **predecessor 정합(C3·NEW-1 헬퍼)**: `predecessor_release_generation`(:25·int) present AND
   `predecessor_admitted_release_set_digest`(:26) present AND `generation_strictly_advances(predecessor_
   release_generation, candidate_release_generation)`(:5·§5.0 ordering 헬퍼·strict BEFORE·equal[reuse]/
   `AMBIGUOUS`/`AFTER` ⇒ deny·candidate는 predecessor를 반드시 앞섬·§5.8 reuse 금지·**phantom
   `predecessor_conflict_present` 폐기·C3**·§16·SCI-INV-009).
9. **single-use(4-field·음극성·M1)**: `consumed is False`(:39)(consumed ⇒ reject reuse·§15 step 10).
10. **decision current(양극성·NEW-4b dead-row 해소)**: `decision.current is True`(:41). `is not True` ⇒
    not-admitted(비-current decision은 admit 근거 불가).
11. **release-artifact identity 정합(MINOR-1 배선 완결)**: `manifest_resolved is not True ⇒ False`(양극성
    게이트). `release_artifact_identity_exact(release_artifact_manifest)` 성립 필수(하단 지지 술어 —
    decision `release_artifact_binding`이 가리키는 manifest의 exact identity·mutable-tag 거부·lineage/
    custody/compatibility). 미성립 ⇒ not-admitted.

**compatibility 경계(NEW-4d 일원화)**: 본 술어는 `compatibility_graph_digest`(:21) **binding present**(구조)만
검사하고 **compatibility verdict(`compatibility_complete` bool) 판정은 §5.5 소관**(§17:358 "Unknown
compatibility denies"·SCI-INV-011·중복 판정 회피).

**지지 술어 `release_artifact_identity_exact`(NEW-4c·§5.0 dead-row 해소)**: `release_artifact_identity_
exact(manifest: ReleaseArtifactManifest | None) -> bool` — `manifest is None ⇒ False`; `mutable_tag_is_
identity is False`(:51·음극성·§2.2 실소비처) AND `lineage_complete is True`(:47) AND `registry_custody_
current is True`(:48) AND `compatibility_complete is True`(:49)(전 양극성). decision `release_artifact_
binding`이 가리키는 manifest identity 정합(SCI-INV-002/003).

**반환**: item 1-11 전부 성립시에만 `True`(item 11이 `release_artifact_identity_exact`를 명시 편입·
MINOR-1 배선 완결). **SCI-EV-006을 닫지 않음**
(`/3`+`+Security` — common-mode review·self-approval 저항). enum-drift: binding 집합 == §15 step 1-7 anchor(§6.2).

### 5.5 `admitted_set_no_permissive_union` (SCI-EV-006 노른자·§16·SCI-INV-009·C2 ∅⇒deny)

**시그니처(C2·M1)**: `admitted_set_no_permissive_union(release_set: AdmittedReleaseSet | None, applicable_
manifest_digests: frozenset[str] | None, member_manifest_digests: frozenset[str], applicable_set_resolved:
bool | None) -> bool`. (**M1 — member/applicable 전부 주입 frozenset·모델은 `release_artifact_manifest_set_
digest`(:24) canonical 디지트만·subset 비교 불가하므로 인자 주입**.)

**판정(전부 AND·fail-closed·∅⇒deny·C2)**:
1. **∅-seal + resolution 게이트(C2·§0.5-2)**: `release_set is None` ⇒ `False`. `applicable_set_resolved is
   not True` ⇒ `False`(None/False⇒deny). **`applicable_manifest_digests` ∅ + `member_manifest_digests` ∅ +
   `complete is True` ⇒ `False`(deny)** — **ADR explicit-empty 부재 negative-grep(§5.9/§16 grep 0)·§1 line
   17 "grants zero eligibility"·§16 line 346 "Missing artifact … invalidates the set for the affected
   scope"(m5 완전 인용). 운영자가 뒤집으려면 §16 에라타 필요**(§10.1). (**C2 — v1.0 공허-True 제거·§5.3과
   통일**.)
2. **completeness both-ways(§16 line 346)**: `applicable_manifest_digests ⊆ member_manifest_digests` AND
   역방향 — 누락(applicable ⊄ member) 또는 잉여(member ⊄ applicable) ⇒ deny.
3. **no permissive union(SCI-INV-009 line 187)**: favorable subset ↛ permissive(SCI-INV-009 line 187
   "Partial deployment and favorable subsets cannot form a permissive union"·**SCI-INV-009:187·m2 정정**)·
   `partial_set_permitted`(:44)·`set_union_permitted`(:46)·`favorable_subset_permitted`(:47) 전부 `is False`.
4. **complete·committed·current·compatibility·restriction_state(양극성·NEW-4a + 1b dead-row 해소)**:
   `release_set.complete is True`(:39·**`is_complete` 아님**) AND `committed is True`(:38) AND `current is
   True`(:40) AND `compatibility_complete is True`(:41·**(1b) — SCI-INV-011 core·§17:358 "Unknown
   compatibility denies"·digest-presence 불충분·bool 게이트**) AND `restriction_state`가 positively-
   resolved(UNKNOWN 아님·:42·비-restricted 값은 template INSTANCE·Phase-0). 하나라도 `is not True`/UNKNOWN
   ⇒ invalid(§16 line 344 "The committed record binds"·SCI-INV-009 line 187 "one complete current Release
   Generation and Admitted Release Set").
5. **generation 정합**: `release_generation` mixed 아님(§16)·`historical_generation_reuse_permitted is
   False`(:48)·generation floor는 `generation_strictly_advances`(§5.0·§5.6b).

**반환**: 전부 성립시에만 `True`. **SCI-EV-006을 닫지 않음**.

### 5.6 cross-cutting 구조 술어 (§1 core 원칙·형제 일반화 불가)

**(a) `supply_chain_artifact_not_authority(authority: AllFalseSupplyChainAuthority | None) -> bool`
(SCI-INV-001)**: 전 union 20필드(§2.4·M2) `is False` + validator any-True ⇒ 구성 불가. `None` ⇒ `False`.

**(b) `release_generation_monotonic` + `rollback_is_new_generation` (SCI-INV-012·§5.8·§22·ordering·NEW-1)**:
`generation_strictly_advances(predecessor, successor)`(§5.0 ordering 헬퍼·strict `Ordering.BEFORE`·
equal[reuse]/`AMBIGUOUS`/`AFTER` ⇒ `False`)로 generation predecessor 후진·재사용 없음. rollback/restore/
rebuild/re-sign/hotfix/identical-bytes ⇒ 새 generation(§22 line 433)·이전 generation 소생 불가(§5.8 line
131). authority `recovery_generation_revives_nothing` shape 동형(ordering REUSE·**`compare_order` 직접
호출 아님·헬퍼 경유·str 금지·AMBIGUOUS 봉인**).

**(c) `restriction_is_monotonic_non_revival` (SCI-INV-008/016·§20·M4 — floor advance는 cur 이연·재정의)**:
SCI는 (i) `ReleaseRestriction`이 recorded 후 어떤 SCI artifact로도 revive/clear 불가(SCI-INV-016·§20 line
406 "does not readmit … clear a release restriction"), (ii) `restricted_scope`가 greatest-credible closure
(§20 line 404·any-broaden-wins·smallest 반전 금지·§0.5-13)를 판정한다. **floor ADVANCE ordering 자체는 cur
`fence_advances_floor`(`predicates.py:415`) 소유**(§20:404 "reduces future authority **through ADR-002-
024**")·SCI 재저작 아님(§3.5·M4·docstring 분리 선언). §6.2 negative-token `fence_advances_floor` 부재 assert.
SCI 자신의 admission-time floor 비교(§5.4 item 4)는 로컬 `restriction_floor_not_behind`(int·§5.0 헬퍼·
NEW-1)로 하되 이는 **floor advance mechanism이 아니라 not-behind 판정**이며 cur `fence_advances_floor`
(범-아티팩트 strict advance)와 명제 분리(int floor 타입 정합·NEW-1e).

**(d) `active_currentness_is_negative_gate` (SCI-INV-013·§1 line 27)**: currentness verdict는 negative
gate만 — 성공 check가 capacity/authority/protection/approval/admissibility/permission 부여 불가(§1 line 27
verbatim "A successful check is only a negative gate. It cannot supply capacity, authority, protection,
approval, admissibility, or permission that another owner has not independently granted"·SCI-INV-013 line
201). per-send transaction은 cur/egress(§3.5·명제 비동일 — SCI는 구조 술어·cur가 mechanism·리뷰어 ⑨ SCI
귀속 확정). **인용 정정 주의(§0.5-12)**: 이 verbatim은 §1 line 27이며 §19 line 389는 별개 문장.

**(e) `software_deployment_ok_verdict` (produced-value seam·§18·spg 소비·M6 완전 시그니처)**:
`software_deployment_ok_verdict(admission_result: AdmissionResult | None, runtime_attestation_matches:
bool | None, active_currentness_current: bool | None, restriction_present: bool | None, restriction_state_
resolved: bool | None) -> bool`. 판정: `restriction_state_resolved is not True ⇒ False`(조회 실패 보수)·
`admission_result is AdmissionResult.ADMIT` ∧ `runtime_attestation_matches is True`(양극성·RuntimeArtifact
Attestation.`runtime_artifact_match`:38 출처) ∧ `active_currentness_current is True`(양극성·cur 주입) ∧
`restriction_present is False`(음극성) ⇒ `True`, else `False`. **각 arg owner는 §3.5**·spg `software_
deployment_ok: bool\|None`(records.py:206) 소비 slot·gate `is not True`(predicates.py:467)·SCI producer·
import 0·§6.2 seam test.

---

## 6. property-test 하네스 · import-closure · drift-lock · 뮤테이션

**닫는 SCI-EV = 0건** — 규율 태그 부착. 각 술어 both-ways canary·fixture clean-vs-illegal 정합. hypothesis는
∅/None/mutable-name/tri-state-UNKNOWN/forgery 명시 포함.

- **§5 노른자 5 + cross-cutting 5 + 지지 술어 3(MINOR-1)**: (i) 전 AND 조건 개별 발화, (ii) ∅ ⇒ deny(양방향·C2), (iii) None⇒deny
  극성, (iv) tri-state 양성 identity(ADMIT/INDEPENDENT만 통과), (v) malformed-model 구성 불가(ADMIT+
  incomplete binding·`complete`+missing set·INDEPENDENT+no-reviewer), (vi) **restriction floor 미달⇒not-
  admitted**(C1·§5.4-4).
- **§2 enum per-member 바인딩(§0.5-6)**: `AdmissionResult`(3)·`IndependenceResult`(3)·`RecordPairKind`(5)
  개별 계수·`__bool__⇒TypeError`.
- **§2.4 record 불변식**: 9 tos 모델 (i) frozen, (ii) `authority` all-false union 20필드(any-True 구성
  실패·M2), (iii) same-`*_id`/different-bytes ⇒ CRITICAL_CONFLICT, (iv) pre-issuance ⇒ NOT_COMPARABLE,
  (v) `_REQUIRED_COVERED` 누락 ⇒ 구성 불가.
- **규율 태그**: "EV-L1 predicate/model substrate only; closes no SCI-EV; all 12 rows +Security — gate
  unmet; acceptance deferred to EV-L3(+Security)".

### 6.1 import-closure 검증 (§0.3·allowlist·저작-레벨)
서브프로세스 `import tos.sci` 후 `sys.modules` top-level `tos.*` ⊆ {`tos.canonical`, `tos.ordering`, 자기}
assert; `shared.config`·`os.environ`·numpy/pandas/yaml·전 형제 부재 assert. **저작-레벨 잠금(FD #27)**:
서브모듈 `vars()`+AST import 스윕. required check(`tools/tos_firewall_check.py`+`.importlinter`) green.

### 6.2 sibling/template seam drift-lock (§3.5·§4 anchor)
- **spg produced-value seam**: test-only `import tos.spg`로 `SafetyChangeInputs.software_deployment_ok`
  필드 존재 drift-lock(brokercap #10).
- **§4 verbatim anchor drift(WDR MAJOR-1)**: §8 17 `*_policy_digest`(§4.3)·§11 17 closure(§4.9)·§15
  10-step(§4.4)·§16 9 scope(§4.10)·§19 8-item(§4.5)·§21 12행(§4.6)·§6 16 INV(§4.1)·§27 12 AC(§4.7)가 ADR/
  template 수·이름 1:1(field-group 통째 누락 ⇒ FAIL). **canonical 템플릿 필드 ↔ 모델 필드 1:1 anchor-drift**
  (M1 전건·명제 상이 2건[`floating_version_permitted`·member-set-digest vs tuple]은 **명시 예외+사유
  등록**·§5.3/§5.5 재정의 참조).
- **negative-token(§0.5·anti-phantom)**: FD 좌표 4종·cur `RestrictiveFenceRecord`/`fence_advances_floor`
  (M4)·dsl `AdmissibilityResult`(소비 아님)가 **SCI에 부재** assert.

### 6.3 뮤테이션 canary 실효성 (§0.5-11·PTF 선례)
뮤테이션 주입 후 property FAIL 전환 실측: (a) 극성 반전(`is False`→`is not True`·음극성 fail-open), (b)
tri-state 게이트 완화(`is ADMIT`→`is not DENY`·UNKNOWN 누출·AFG C1), (c) ∅ 방향 반전(∅ admitted-set⇒True·
C2 재현), (d) enum value-swap(ADMIT↔DENY), (e) all-false 필드 default True, (f) **tri-state→bool 투영
뮤턴트**(reproduction/independence를 bool로 투영해 UNKNOWN 누출·M7), (g) restriction-floor 게이트 제거(C1),
(h) **`Ordering.AMBIGUOUS`를 통과로 접는 뮤턴트**(`is Ordering.BEFORE`→`is not Ordering.AFTER`·AMBIGUOUS
누출·NEW-1 fail-open·`restriction_floor_not_behind`/`generation_strictly_advances` 양쪽), (i) **`restriction_
floor_not_behind`의 `equal ⇒ True` 단락을 `compare_order` 뒤로 이동하는 뮤턴트**(정상 equal-floor decision을
`compare_order`가 AMBIGUOUS로 접어 전면 봉쇄하는 **false-negative canary**·2-helper 분리 정당성 회귀 고정),
(j) **`generation_strictly_advances`에 `equal ⇒ True` 주입 뮤턴트**(§5.8 reuse fail-open 재현·floor↔
generation 명제 차이 박제). 각 뮤턴트 최소 1 property로 KILLED·**등가-뮤턴트 전수 열거**(PTF #24 선례).

---

## 7. firewall · import-closure allowlist
층① AST gate(§3.2 allowlist·PR-gated line 422)·층② import-linter forbidden(source_modules=`tos`). SCI는
canonical/ordering만 import·**무수정 자동 포섭**. allowlist `⊆ {canonical, ordering, sci}`·denylist 아님
(§0.5-9). 착지 형제 8개 파일이 `tos.sci`를 "not-landed excluded"로 열거하나 import하지 않으므로 SCI 착지가
형제 테스트 무손상(§0.3·§9.2 문서 위생 후속·firewall 배제 목록 `tos.ptf`≠`tos.posttrade` 불일치 포함).

---

## 8. bounds — SCI 전용 VP-002 키 실측 (신규 저작 0건·anti-phantom)
ADR §29 item 12의 10 VP 키 전수 기존재(각 1 hit·line anchor 실측):

| VP-002 키 | line | 상태 |
|---|---|---|
| `B_supply_chain_compromise_detect` | 492 | `value_ms: null`·`owner: TBD`·`failure_response: STOP_NEW_RISK_AND_RESTRICT_RELEASE_SCOPE` |
| `B_release_restriction_to_authority_restrict` | 499 | `null`·"release restriction to denial at every dependent new-risk authority issuer" |
| `B_release_restriction_to_egress_deny` | 506 | `null`·"to denial at every dependent final egress" |
| `B_release_generation_fence` | 513 | `null`·"Release Generation advance/restore/rollback/revocation to rejection of superseded publishers" |
| `B_runtime_artifact_drift_detect` | 520 | `null`·"divergence to restrictive detection and runtime fencing" |
| `MAX_build_provenance_age_ms` | 742 | `null` |
| `MAX_artifact_admission_decision_age_ms` | 743 | `null` |
| `MAX_admitted_release_set_age_ms` | 744 | `null` |
| `MAX_runtime_artifact_attestation_age_ms` | 745 | `null` |
| `MAX_release_key_status_age_ms` | 746 | `null` |

⇒ **SCI는 신규 VP-002 키 0건 저작**. 10키 값 승인(전부 `null`·`owner: TBD`)을 Phase-0 Bounds-Approver 이관.
모델은 numeric 슬롯(`age_within_approved_limit`·§2.3)을 주입만·하드코딩 0.

---

## 9. Phase-0 인간 게이트 이관 · 명시 이연 목록

### 9.1 후속 구현 작업
`tos/src/tos/sci/` 어휘(§2.2 2 tri-state enum + `is_mutable_name_notation`)·record shape 9(§2.4·`Independent
IdArtifact`)·§5 술어(5 노른자 + cross-cutting 5 + 지지 술어 3[MINOR-1])·§6 property/import-closure/drift-lock/anchor-drift/seam.
`tos.canonical`+`tos.ordering` 의존. EV-L1 근거: VER-002-001 §"EV-L1 — Model and Property Verification".
**SCI-EV/SCI-AC 행 자체는 L3(+Security) 도달 전까지 NOT_IMPLEMENTED**(§1·§30 게이트 11).

### 9.2 Phase-0 인간 게이트로 넘기는 항목
1. **8 canonical schema 승인 + INSTANCE**(ADR §30-1) — §2.4 shape는 틀·실 값 인간 승인.
2. **10 VP-002 키 값 승인**(§8·전부 `null`·`owner: TBD`).
3. **+Security 전수 boundary assessment(전 12행)** — 어떤 SCI-EV도 코드만으로 닫히지 않음(§1).
4. **+Broker 실측(SCI-EV-011)**.
5. **sir(-027) incident handoff seam 확정(§0.4f)**: 구현 시점 sir 착지 재실측 — 착지 시 seam test·미착지
   시 이연 docstring·**sir 타입 import 금지**. **posttrade(-030)는 착지 — spg 7-item 중 SCI 4·posttrade 2
   분할 거버넌스 확정**(M5·§3.5).
6. **형제 verdict 소유 거버넌스(§3.5)**: hag independence·rcl capacity·spg activation + `software_deployment_
   ok` 소비·cur currentness + **`fence_advances_floor`**·egress final·rlp promotion·evidence·sbr — 각 owner
   verdict 생산·주입 계약 Phase-0 명시(SCI 소비만).
7. **패키지 명 확정**(§0.4a·§10.1): `tos.sci`(권고·8 파일 지명) — 단 배제-목록 명명 ≠ 착지-명명 확정(`tos.
   ptf`≠`tos.posttrade` 선례).
8. **Independent-Safety-Reviewer 지정** 및 §6 EV-L1 evidence 수용 서명(저자/통합자 배제).
9. **문서 위생 후속**: 착지 형제 8 파일의 "`tos.sci` not-landed excluded" 주석 + firewall `tos.ptf`
   placeholder를 착지 후 정정(비준 시 오케스트레이터·INDEX.md 포함).

---

## 10. 개정 로그 + 판단 지점 + open questions

### 10.1 운영자 판단 지점 (리뷰어 판정 반영)
1. **패키지 명**(§0.4a): `tos.sci`(권고) — 배제-목록 명명이 곧 착지-명명 아님(M5).
2. **9 tos 모델 전수 vs not-L1 축소**(§2.4·§10.2-③): runtime-attestation(§18·008 not-L1)·release-
   restriction(§20)은 shape만·술어 +L2 이연. 운영자가 not-L1 shape 축소 가능하나 **ADR §30-1 "eight
   schemas" 정합**(runtime-attestation 포함) 유지 권고.
3. **∅ 규칙(리뷰어 ⑦⑧ 해제)**: closure·admitted-set 모두 **∅⇒deny 확정**(C2·§5.3/§5.5 통일). 뒤집으려면
   ADR §16 에라타 필요.
4. **record shape = `IndependentIdArtifact`**(§0.4c): 8 템플릿 독립 `*_id` ⊥ `canonical_digest` 근거 확정.

### 10.2 독립 리뷰어 공격 지점 (open questions·리뷰어 판정 반영)
1. **ReleaseRestriction 저작 vs cur 이연**(M4·리뷰어 "방어 가능한 분할 존재·봉합이 처방"): 저작 유지 +
   §3.5/§5.6c 봉합(SCI=FACT 생산·cur=floor advance)을 기본으로 하되 재확인.
2. **posttrade seam 필요성**(M5): spg 7-item 분할(SCI 4·posttrade 2·referenced policy objects 1 공유)에서
   SCI↔posttrade 직접 seam 부재 재확인(둘 다 spg에 개별 주입).
3. **§30-1 "eight schemas" 정합**: 9 tos 모델 중 8이 템플릿·ReleaseRestriction은 ADR-파생 — §30-1 계수와
   정합(runtime-attestation 포함·restriction 제외) 재확인.
4. **FD 좌표 / hag collapse 재저작 우려**(§0.4d/e): negative-grep 확증·재확인.
5. **mutable-name 비전수 정직**(§2.2): catalogued sentinel·메타문자만·신종 +Security 이연.
6. **malformed-model 2층 봉인**(§2.3): `model_construct` 우회 적대 검토.
7. **`active_currentness_is_negative_gate` SCI 귀속(리뷰어 ⑨ 확정)**: cur `ProofResult`와 명제 비동일·cur
   `AllFalseCurrentnessAuthority` 중복은 pattern-only(§3.5 봉합).

### 10.3 개정 로그
- 2026-07-28: **v1.0 초안.** register 실측(core 4행·전 12행 +Security·닫는 SCI-EV 0). SCI = greenfield
  release-admission 생산자 + 착지 소비자(spg) + 통합 레이어. canonical+ordering REUSE·edge 0·전 아티팩트
  IndependentIdArtifact. 5 노른자 + cross-cutting. 소유권 분할 봉합·VP 키 신규 0·anti-phantom §0.5.
- 2026-07-28: **v1.1 — 독립 비평 REJECT(CRITICAL 3·MAJOR 9·MINOR 7·Gap 6·오케스트레이터 전건 확정) 반영.**
  8 canonical 템플릿 + cur/posttrade/spg/dsl **전수 재실측**(리뷰어 인용 재검증). **CRITICAL**: (C1) §5.4
  ADMIT 게이트에 §15 step 7 `current_release_restriction_floor`(:27) + `compare_order` + step 4-6 digest
  binding(:19-22) + independence(:29) 편입·invented bool 제거; (C2) §5.5 ∅ admitted-set **공허-True→deny**
  (§5.3 통일·ADR explicit-empty 부재 negative-grep); (C3) phantom `source_continuity_proven`→`history_
  rewrite_detected`(:33)·`predecessor_conflict_present`→`predecessor_release_generation`(:25). **MAJOR**:
  (M1) §2.4 골격 21건 템플릿 실명 정정(`canonical_digest`·`release_artifact_binding`·4-field consumption·
  `complete`·`transitive_closure_complete`·`consumer_compatibility_graph_digest`·17 policy-digest 등); (M2)
  `AllFalseSupplyChainAuthority` 템플릿 실명 20필드 union + `creates_artifact_admission` 복원(SCI-INV-004);
  (M3) `RuntimeArtifactAttestation` 골격 신설·"9 tos 모델" 통일; (M4) cur `RestrictiveFenceRecord`(records.py:315)/
  `fence_advances_floor`(predicates.py:415) 충돌 봉합·§5.6c 재정의; (M5) **"ptf 미착지" 거짓→posttrade 착지**
  (미착지 sir/stm)·spg 7-item 정확 인용·§3.5 posttrade 행; (M6) §5.6e 완전 5-arg 시그니처; (M7) §5.0 극성표
  실필드 재작성·ReproductionResult enum 폐기(`reproducibility_requirement_satisfied` bool); (M8) §4.9 closure
  17차원 전사; (M9) §4.10 scope 9차원 전사(runtime 8). **MINOR/Gap**: §3.5 "§19 line 386"→376(m1)·절
  오귀속 4건(§0.2 §5.7:127→§1:21·"§5 line 19"×2→§1:19·"§16 line 187"→SCI-INV-009:187·m2)·dsl :57→58(m3)·
  §0.4c "전수 result:UNKNOWN" 제거·id⊥digest만 근거(m4)·인용 절단 3건 복원(§9:267·§16:346·§21:427·m5)·"7개
  파일"→8(m7)·`mutable_tag_is_identity`(:51)·`signing_key_status`(:44)·`self_report_only_is_sufficient`·
  `desired_state_is_actual_state` 앵커·`age_within_approved_limit` numeric-vs-구조 §2.3·등가-뮤턴트 §6.3(Gap).
  아키텍처 7건(edge 0·IndependentId·spg seam·FD split·hag consumer·rcl edge 0·`tos.sci`)은 리뷰어 전원
  지지·유지.
- 2026-07-28: **v1.2 — 델타 재검증 REVISE(v1.1 신규 유입 MAJOR 4·MINOR 3·(1b)) 반영, 국소·기계적.**
  ordering/cur 코드 전수 재실측(전건 확정). **NEW-1**(MAJOR·C1 기제 호출 불가): `compare_order`가
  `OrderingEvent` 전용(str 불가)·`Ordering`{BEFORE/AFTER/AMBIGUOUS} 미매핑 fail-open을 §5.0 ordering 헬퍼
  2종(`restriction_floor_not_behind`[not-behind·equal 허용]·`generation_strictly_advances`[strict·§5.8
  reuse 금지]·둘 다 `OrderingEvent(quorum_commit_index=int)` wrapping·`Ordering.AMBIGUOUS⇒deny`·cur
  `floor_strictly_advances`(`state.py:190`) shape REUSE·import 아님)으로 봉인·§5.4 item4/item8·§5.6b 치환·
  §2.4 floor/generation `int` 타입·§6.3(h) AMBIGUOUS 뮤턴트·§3.5 M4 int 정합. **NEW-2**(MAJOR·scope 도달
  불가): §5.4 시그니처에 `target_scope: SupplyChainScope|None`+`scope_resolved` 추가·item6 배선. **NEW-3**
  (MAJOR·회귀): §5.1 item2 `is_mutable_name_notation(...) is False` 실게이트 복원(`source_revision_digest=
  "latest"` 통과 봉쇄·SCI-INV-002:159). **NEW-4+1b**(MAJOR·dead-row 7): §5.5 item4에 `committed`(:38)·
  `current`(:40)·`compatibility_complete`(:41·bool 게이트·SCI-INV-011)·`restriction_state`(:42) 편입·§5.4
  item10 decision `current`·신규 지지 술어 `release_artifact_identity_exact`(RELEASE-ARTIFACT 4행 소비:
  `mutable_tag_is_identity`/`lineage_complete`/`registry_custody_current`/`compatibility_complete`)·§5.0
  `restriction_state` 행 추가. **NEW-5**(MINOR): §2.2 `mutable_tag_is_identity` xref §5.1→`release_artifact_
  identity_exact`. **NEW-6**(MINOR): §2.4 BuildProvenance 골격에 `result`(:8)·`policy_binding`(:9-12)·
  `independent_build_attestation_digest`(:33) 추가. **NEW-7**(MINOR): §5.3 item2 "declared 축"→"`resolution_
  policy_digest` 미배제 전 17축" 결정적. 아키텍처 7건·§2.4 골격·C1-C3·M1-M9는 UPHOLD(리뷰어 M4·M5 "모범"·
  C1 digest-binding "bool 처방보다 우수"). **반론(보고 b)**: NEW-1 헬퍼를 리뷰어 지시(단일 `restriction_
  floor_not_behind`)와 달리 2종으로 분리 — 1차 소스 근거: item8·§5.6b는 generation 좌표라 §5.8 line 131
  "cannot be reused"로 equal(reuse) 금지·strict 필수인데 floor의 not-behind(equal 허용)를 쓰면 reuse
  fail-open. 둘 다 str 금지·AMBIGUOUS⇒deny·cur shape REUSE라 리뷰 핵심 처방 완전 충족(정신 반영·실현 정밀화).

- 2026-07-28: **v1.3 — 최종 판정 ACCEPT-WITH-MINOR·비준 진행 가능(마이크로 개정).** 2-helper 분리 반론이
  리뷰어 `_cmp`(`ordering/_ordering.py:77-83`·equal⇒None⇒AMBIGUOUS) 실측으로 **UPHOLD**("저작자 옳음·
  리뷰어 처방 오류"·시리즈 모범 사례 기록). 잔여 MINOR 2 + 권고 canary 2 반영: **MINOR-1** §5.4 시그니처에
  `release_artifact_manifest`+`manifest_resolved` 추가·**item 11**로 `release_artifact_identity_exact`
  명시 편입(§5.0 dead-row 지지 술어 배선 완결)·산출물 계수 "5 노른자 + cross-cutting 5 + **지지 술어 3**
  (`mutable_name_is_not_identity`·`independence_unproven_is_common_mode`·`release_artifact_identity_exact`)"
  로 §0.1-4·§6·§9.1·승인문 통일. **MINOR-2** BuildProvenance `result`(:8)·RuntimeAttestation `result`(:8)
  → 불투명 `str | None`(**§7 line 232 "attestation is a fact, not permission"**·SCI-INV-004: provenance는
  ADMIT을 낼 수 없음)·§2.2 `AdmissionResult` 매핑을 **admission-decision:8·admitted-set:9로 한정**. **권고
  canary(§6.3 i·j)**: (i) `restriction_floor_not_behind` `equal⇒True` 단락 이동 뮤턴트(정상 equal-floor
  전면 봉쇄 false-negative)·(j) `generation_strictly_advances` `equal⇒True` 주입 뮤턴트(§5.8 reuse
  fail-open)로 2-helper 분리 결정 회귀 고정. 아키텍처 7건·§2.4 골격·C1-C3·M1-M9·NEW-1~7 전부 UPHOLD·무변경.

**본 계약이 승인하는 것**: `tos/src/tos/sci/` Phase 1(EV-L1) 어휘(2 tri-state enum + `is_mutable_name_
notation`) + record shape 9(8 template-backed `IndependentIdArtifact` + `ReleaseRestriction`) + 노른자
술어 5 + cross-cutting 5 + 지지 술어 3(MINOR-1) + property/import-closure/drift-lock/anchor-drift/seam 테스트 **작성 착수**.
**SCI-EV 0건 완결**(전 12행 `+Security`·acceptance는 EV-L3(+Security) fault injection 이연); §9.2 Phase-0
9항목·독립 리뷰어·8 schema·10 VP 키 값 승인·sir seam은 별도 게이트. ADR-002-029는 **Proposed** 유지
(§30 14 조건 미충족·§30 line 658).
