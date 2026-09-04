# 작업 메모 — Phase-0 인간 게이트 register: 전수 인벤토리·실태·실행 계획 (2026-07-29)

> **문서 성격 (규범성 선언)**: 본 문서는 **비규범 작업 메모**다(EV-L1 survey `06de78ce` 동형). **비준 대상이
> 아니며**, GOV-001의 세 거버넌스 행위(비준 / ADR acceptance / live authorization) 중 어느 것도 수행하지
> 않는다. ADR·RFC·VER·register·VERIFICATION-PROFILE의 어떤 상태도 변경하지 않는다. 유일한 산출은 **Phase-0
> 인간 게이트의 전수 인벤토리·현상태 실측·운영자 결정 준비물**이다. 여기 기록된 권고는 결정이 아니다 —
> Phase-0 게이트는 정의상 인간(운영자·지정 권한자)만 닫을 수 있다.

- **방법**: 병렬 추출 2트랙 — ① 설계 문서 31편 전수(§6–§9 원천) ② 규범 원천 실측(IMPLEMENTATION-PLAN-002·
  VERIFICATION-PROFILE-002.yaml·EVIDENCE-REGISTER-002·VER-002-001·ARCHITECTURE-GATE-STATUS·GOV-001; §1–§5
  원천). 두 트랙 모두 anti-phantom 규율(존재/부재 양방향 grep·file:line) 하 수행. 오케스트레이터가 하중 주장
  3건(PROFILE:17–21 PROPOSED/approved_by []·CSV 372행 전부 reviewer TBD/status NOT_IMPLEMENTED·PLAN:29–38
  Phase-0 표 verbatim)을 직접 재실측 확정.
- git 상태 변경 없음(본 메모 파일 생성 외).

---

## 0. 요약 판정

1. **규범 Phase-0 게이트는 정확히 4개**(IMPLEMENTATION-PLAN-002 §1:29–38): P0-1 bounds 승인 · P0-2
   broker-specific bounds 측정 · P0-3 owner/evidence-owner/독립 리뷰어 지정(372행) · P0-4 plan/경계/substrate
   비준. **P0-4만 프로젝트 측에서 닫혀 있고(2026-07-20 운영자 비준) 나머지 3개는 0% 진행.**
2. 설계 문서 31편이 이관한 항목 총 **375건**은 공통 게이트 13종(G1–G13, §6)과 문서 고유 게이트(§7)로
   정리되며, 공통 게이트는 전부 P0-1/2/3 또는 **Phase-1 범위 밖 후속 트랙**(런타임·+Security·+Broker·ENGINE)
   으로 귀속된다. Phase-0에서 지금 닫을 수 있는 것과 나중 트랙 소관을 §6에서 분리했다.
3. 수치 키 실태: **승인 대기 ~150키**(실재·null/TBD — Bounds-Approver 값 승인만 필요) · **확정 누락 26항**
   (프로파일에 키 자체가 없음 — 신설 필요) · **candidate 8군**(누락 확정도 커버 확정도 아님). 전 프로파일
   `status: PROPOSED`·`approved_by: []` — "an unapproved or placeholder bound is not an approved bound"
   (PROFILE:5·VER-002-001:252).
4. **미결 운영자 판단 지점 23건/9문서**(§9) — 위임 자동비준 기간(#14 이후)의 문서들은 INDEX에 "판단 지점
   전건 승인" 기록이 없는 것이 있다(자동비준 위임이 판단 지점 승인을 포괄했는지의 소급 확인 대상).
5. 관측 이상 3건(§10): #16 AFG 판단 지점 6열거 vs INDEX "4건 승인" · IMPLEMENTATION-PLAN-002:3 "no
   implementation code has been written" stale 문구(현 30패키지와 모순) · P0-4 프로젝트 측 비준의 tos-spec
   텍스트 미반영(비준 레코드 0건 — 단 PLAN:20이 "project workflow"로 위임했으므로 규범 위반은 아님).
6. **의존 사슬 확정**: P0-3 지정 ≺ `READY` ≺ 실행 ≺ 독립 서명 ≺ `PASS` ≺ ADR `Accepted`. bounds 승인(P0-1)도
   `READY` 앞(Profile-dependent 해소·"bounds were measured"가 evidence 완결 8조건). **즉 P0-1과 P0-3이 전
   acceptance 트랙의 이중 관문이다.**

---

## 1. 규범 Phase-0 게이트 4개 (정의·종결 요건·현상태)

원천: `tos-spec/src/part-1-foundation/verification/IMPLEMENTATION-PLAN-002.md` §1:29–38 (표 verbatim 실측).
마감 문장 :38 — "I will not fabricate any of these. I can *draft candidates* (done for bounds; role scheme
in §3) for you to ratify."

| # | 게이트 | 정의 원천 | 종결 요건 (주체·기록) | 현상태 (실측) |
|---|---|---|---|---|
| **P0-1** | bounds 승인 | PLAN:33 "unapproved bounds are not bounds"·PLAN:16(VER §6·SoD) | **Safety/Risk authority**(=Bounds-Approver, PLAN:154 "MUST NOT arm live trading"). 기록 = PROFILE 자체: `status: PROPOSED→APPROVED`·`approved_by` 비공집합·`effective_from`/`review_due` 설정·각 `value_ms` 확정(PROFILE:7–13 비준 규칙) | **열림 0%**: `version: 2.1-PROPOSED`·`approved_by: []`·bounds 82 중 null 75/PROPOSED 7·`owner: TBD` 82/82 |
| **P0-2** | broker-specific bounds 측정 | PLAN:34·PROFILE:9–10 "MEASURED from an approved Broker Capability Profile, not guessed" | **Broker/Exec eng**. 기록 = 승인된 Broker Capability Profile INSTANCE + `scope.broker_capability_profiles` 링크 + 해당 bounds 값 | **열림**: `broker_capability_profiles: []`·템플릿만 실재(`BROKER-CAPABILITY-PROFILE-template.yaml`)·GATE-STATUS:940 |
| **P0-3** | owner + evidence owner + **독립 리뷰어** 지정 | PLAN:35·PLAN:17–18(RFC-001 §11.4)·배제 PLAN:157 "Impl ≠ Independent-Reviewer; Bounds-Approver ≠ Live-Armer; author/integrator ≠ Independent-Reviewer" | **System owner**(지정 행위). 기록 = CSV 3열(implementation_owner/evidence_owner/independent_reviewer) + PROFILE:754. 독립성 판정 = ADR-DEV-005 §7(:165–204 — 저자 아님·저자 재실행 아님·저자와 common-mode 아님·**provenance 기록**; AI-on-AI는 decorrelation 적극 입증 없으면 fail-closed) | **열림 0/372**: 3열 전부 TBD 372/372·`verification_profile_version` TBD 372/372·VER:3834 "Independent review: NOT STARTED" |
| **P0-4** | plan + §2 greenfield boundary + mechanism substrate 비준 | PLAN:36·PLAN:19–20 "(project workflow)" | **Architecture board** — tos-spec 내부 기록 스키마 없음(project workflow 위임·GOV-001 G5 스키마는 RFC-class 전용) | **프로젝트 측 닫힘**: `docs/plans/2026-07-20-tos-boundary-and-import-firewall-design.md:3–4` 2026-07-20 운영자 비준(v2·Phase 1 착수 승인·"bounds 승인·독립 리뷰어 지정은 별도 게이트로 유지"). tos-spec 텍스트 미반영(§10-3) |

### 1.1 같은 사슬의 후속 게이트 (Phase-0 이후)

| 게이트 | 원천 | 요건 | 상태 |
|---|---|---|---|
| VER-002-001 자체 승인(§383) | VER:3861–3874 | Proposed → Approved for Execution 8조건(traceability·**Profile schema 승인**·evidence package format·artifact integrity + reviewer sign-off workflow·fault-injection 책임·broker production-test safety rules·retention/access) | 열림(VER:3 Proposed·GATE-STATUS:1069) |
| `READY` 전이 | EVIDENCE-REGISTER-002.md:20 | owner/evidence-owner/독립 리뷰어/Profile version/Broker Profile/evidence 저장 위치 **전부 지정** | 열림 372/372 |
| `PASS` 완결 | VER:364–366(§9.5)+VER:62–66(§2.4)+GATE-STATUS:961–974(§6 8조건) | 독립 리뷰어의 evidence manifest 서명(provenance 포함) + "bounds were measured" + 실제 fault 주입 등; "A written test case, mock output, or design review is not completed verification evidence"(:974) | 열림(전 도메인 NOT EXECUTED) |
| ADR acceptance | EVIDENCE-REGISTER-002.md:401 Gate Rule + GOV-001:22 G1 | 전 필수 evidence 항목이 accepting state(PASS / 결속된 WAIVED / 결속된 SUPERSEDED)일 때만 | 열림(ADR-002-001..030 전부 Proposed) |

---

## 2. 의존 사슬 (실측 확정)

```
P0-4 (닫힘, 프로젝트 측)
P0-3 지정 ──┬──≺ READY ≺ 실행(EV-L1~L3) ≺ 독립 서명 ≺ PASS ≺ ADR Accepted
P0-1 승인 ──┘        (bounds 미승인이면 "bounds were measured" 불성립·Profile-dependent 미해소는 READY 차단, VER:173)
P0-2 측정 ──── +Broker 표기 bounds·행에만 관여(broker profile INSTANCE 선행 — gate-status §7 step 8)
```

- GATE-STATUS §7 13단계 중 Phase-0는 **step 2(372+98행 지정)·step 3(bounds 승인)**에 해당. step 4–7(모델
  구현)은 이미 tos/ 30패키지로 완료된 상태이므로, 남은 시퀀스는 2·3 → 8(broker profile) → 9(fault injection)
  → 10(EV-L1~L3 실행) → 12(독립 리뷰) → 13(acceptance 재평가).
- GOV-001 귀속: P0-1/2/3은 **ADR acceptance 행위의 선행조건**(ratification 사다리 밖 — G2). 부모 RFC 13건은
  이미 Ratified(RR-0001~0013)라 acceptance 측 문서-전제는 충족.
- PLAN:399–407 저자 자기제약 — 계획 저자(AI)는 bounds 승인·실명 지정·독립 리뷰어 서명·live 실행·Accepted
  선언을 **할 수 없음**을 자기 선언. 본 register도 같은 제약 하에 있다(준비물만 저작).

---

## 3. bounds / 프로파일 실태 (VERIFICATION-PROFILE-002.yaml, 756행 — 키 231)

| 블록 | 키 수 | 미정/placeholder | 확정값 |
|---|---:|---|---|
| `scope:` | 91 | TBD 62 · null 26 · 빈 리스트 2(`accounts: []`·`broker_capability_profiles: []`) | 1 (`environment: non-live-test`) |
| `bounds:` | 82 | `value_ms: null` **75**(rationale "MEASURE…") | 수치 7(전부 "PROPOSED…" 라벨): `B_authority_partition_detect 2000`·`B_risk_increase_revoke 500`·`B_stale_epoch_reject 0`·`B_external_activity_contain 1000`·`B_startup_reconciliation 60000`·`B_protective_request_start 1000`·`B_operator_escalation 30000` |
| `limits:` | 55 | null 50 | 5: `MAX_normal_capability_age_ms 1000`·`MAX_degraded_lease_holdover_ms 5000`·`MAX_clock_drift_ppm 200`·`MAX_process_suspension_ms 2000`·`MAX_unresolved_send_per_scope 1` |
| `review:` | 3 | TBD 3/3(`independent_reviewer`·`evidence_location`·`approval_record`) | — |

- 템플릿 정합: `VERIFICATION-PROFILE-002-template.yaml`과 키 집합 완전 일치(231=231·GATE-STATUS:767 일치).
- bounds 하위 필드는 82/82 동일 6필드(`value_ms·semantics·owner·rationale·measurement_source·failure_response`).
  **VER §6:242–250이 요구하는 7속성 중 `applicable broker/profile/scope`·`review date` per-bound 키 부재**
  (프로파일 전역 레벨에만 존재) — 승인 작업 시 스키마 보강 여부 결정 필요(§11 D2-b).
- 승인 규칙은 PROFILE:7–14에 명문(각 value 확정·broker_specific는 MEASURED·`approved_by` = SoD 분리 권한자·
  `effective_from`/`review_due` 설정).

---

## 4. register 실태 (EVIDENCE-REGISTER-002.csv, 372행)

- `status`: **NOT_IMPLEMENTED 372/372** · owner/evidence-owner/reviewer/profile-version **TBD 372/372** ·
  `latest_run_id`/`evidence_location` 공란 372/372.
- 최소 레벨에 L1 포함 행 = **99건**(EV-L1 단독 0건 — 전부 `EV-L1/Lm` staged; VER:171 "higher level applies
  for acceptance"·:175 "A lower level cannot substitute"). ⇒ **Phase-1 산출물(30패키지·pytest 7482)은 이 99행의
  L1 슬라이스 증거 후보이나, P0-1/P0-3 완료 + 정식 실행·서명 전에는 어떤 행도 READY/PASS로 이동 불가.**
- `Profile-dependent` 1건(BC-EV-003) — 승인된 Profile이 정확한 최소 레벨을 해소해야 READY 가능(VER:173).

---

## 5. 상태 전이 규칙 (원천 verbatim 위치)

- 상태 어휘 10종: VER §4:113–128(+WAIVED 제한 :130).
- `NOT_IMPLEMENTED → READY`: EVIDENCE-REGISTER-002.md:20 (지정 6요소 전부).
- `→ PASS`: VER §9.5:364–366(독립 서명+provenance) ∧ VER §2.4:62–66(INCONCLUSIVE는 PASS 아님·게이트 차단) ∧
  GATE-STATUS §6:961–974(8조건).
- acceptance: EVIDENCE-REGISTER-002.md:401 **Gate Rule**(accepting state = PASS / 6요소 결속 WAIVED /
  승계-결속 SUPERSEDED; 그 외 전 상태는 차단).

---

## 6. 설계 문서 31편 이관 항목 총괄 — 공통 게이트 13종과 P0 귀속

커버리지: 31/31(파일 글롭 실측 — #1·#2·#4–#30 + Strategy-DSL·Trustworthy-Time 무번호 2편; **#3은 부재**,
DSL/Time 트랙으로 흡수). 이관 항목 총 **375건** = 공통 인스턴스 ~200 + 문서 고유 ~175.

| G# | 공통 게이트 | 언급 | **귀속 판정** |
|---|---|---:|---|
| G1 | VERIFICATION-PROFILE bounds 값 승인 | **31/31** | **= P0-1** (지금 착수 대상) |
| G2 | 프로덕션 canonical serialization·digest 알고리즘 승인(`ev-l1-provisional-0`·sha256 = 비프로덕션) | 25 | Phase-0 결정 사항(스펙-측 mechanism substrate 후속 — P0-4 계열의 프로덕션 확장; EV-L2+ 실행 전 필요) |
| G3 | Independent-Safety-Reviewer 지정 + EV-L1 수용 서명 | 29 | **= P0-3** (지금 착수 대상) |
| G4 | ADR acceptance 결정 | 15 | 후속(§2 사슬 종점 — P0 완료+실행+서명 후) |
| G5 | ADR-002-016 Evidence Integrity·Replay ENGINE | 14 | 후속 트랙(런타임 구현 — Phase 1 범위 밖) |
| G6 | Broker Capability Profile INSTANCE 값 | 15 | **= P0-2** (별도 트랙 — broker-agnostic 원칙상 non-normative INSTANCE 문서·[[tos-spec-broker-agnostic]]) |
| G7 | 첫 restricted-live scope 승인 | 5 | 후속(live-track — ADR-002-007/-025·GOV-001 제3행위) |
| G8 | 서명 키 custody·rotation·암호 검증 | 9 | 후속(+Security 조직 게이트) |
| G9 | dual-control/effective-principal/quorum 런타임 | 10 | 후속(ADR-002-015 런타임) |
| G10 | 패키지 명명 확정 | 10 | §9 미결 판단 지점에 포함(문서별 처분) |
| G11 | sibling edge/PROMOTE/seam 채택 승인 | 13 | 대부분 비준 시 승인됨 — §9 미결분만 잔여 |
| G12 | failure-domain 분리 + 독립 security review | 12 | 후속(+Security) |
| G13 | ADR-002-024 currentness/final-egress 런타임 | 12 | 후속(런타임) |

**판정**: 지금 여는 Phase-0 작업은 **G1(=P0-1)·G3(=P0-3)·G2(프로덕션 canonicalization 결정)·G10/G11 잔여
판단 지점(§9)·수치 키 신설(§8-1)**이고, 나머지 공통 게이트는 P0-2(broker INSTANCE)·런타임/+Security/live
후속 트랙이다.

---

## 7. 문서별 고유 게이트 (전수 — 원 추출 표 축약 없이 보존)

> 아래 표는 추출 트랙 ①의 문서별 고유 게이트 전수다. "런타임/+Security/+Broker/후속 ADR 소관"으로 명시
> 이연된 항목은 Phase-0 지금-결정 대상이 아니라 **후속 트랙의 착수 목록**이다. 지금-결정 대상은 굵게 표시.

| # · 문서 | 항목(요지·file:line) |
|---|---|
| #1 boundary | 고유 없음(G1·G3 비대체 선언 :41–43) |
| #2 capsule | **digest 자기제외 집합 비준(:776–779)** · **수치 canonical form 정책(:782–784, G2)** · **id↔digest 정책(:786–787)** |
| DSL | Proposal id 유도(-020/-023 공동, :571) · Proposal target field set(:572) · realization family 선택(:568) · **cross-scheme collision 해소(:547–551, G2 결속)** |
| #4 evidence | integrity-anchor 알고리즘·chain-vs-Merkle(G2, :858–859) · cross-scheme id-collision(:862–863) · **record-class matrix + causal-parent rules(:866–867)** · **retention/tombstone 기간(:868–869)** · status attestation 경로(:870–872) · CapsuleIntegrityError assert 확인(:875–878) |
| #5 rcl | **writer-epoch scope(:868–869)** · Capacity Domain 경계+f/2f+1+consensus 제품(:865–867, Phase B) · broker FQP 규칙(P0-2, :870–872) |
| Time | **TIME-HEALTH-SNAPSHOT 스키마 독립 리뷰·상류 승격(:685–687)** · ordering PROMOTE home(승인됨·기록 확인, :688–689) · 런타임 continuity 플랫폼(:695–697) |
| #6 authority | **Authority Domain granularity(:1004–1005)** · Epoch Registry consensus(:1006–1007) · Hard Egress Fence(:1011–1012) · re-arm dual-control(G9, :1013–1014) |
| #7 liveauth | **첫 restricted-live scope 차원(G7, :1140–1142)** · fenced single-use capability(:1143–1145) · safety-config artifacts(:1149–1151) · recovery readiness(:1152–1153) · partial-expand evidence 정책(:1154–1155) |
| #8 orthostate | orthostate→rcl edge(승인됨) · **per-dimension conservatism lattice 비준(:968–969)** · **static-vs-transition ADR-owner 해소(:984–990)** · STALE threshold·전용 키 여부(:970–973, §8-2) |
| #9 recon | CanonicalDecimal PROMOTE(승인됨) · PTOL finality recipe(-030 소관, :1046–1047) · **freshness_marker "aged" caller-precondition 문서화(:1059–1065)** |
| #10 brokercap | seam decoupled(승인됨) · **broker capability 값·class 할당(P0-2 코어, :1217–1220)** · Broker Adapter 런타임(:1221–1222) · **required-capability-set/minimum-live-gate 매핑(:1230–1232)** · conformance class 승인(:1233–1234) · **cross-package 좌표 조정 의무(:1235–1238)** |
| #11 protective | **broker별 protective resource domain 열거(P0-2, :1329–1333)** · PAC 런타임(:1334–1335) · **required-protective-domain-set/per-mode 매핑(:1342–1344)** · **§8.3.1 pre-approved emergency-action set(:1345–1347)** · 좌표 조정(:1352–1355) |
| #12 spg | signing/approval-workflow/registry 제품(G8/G9, :1200) · **deterministic restrictive-comparison 시스템(:1203–1204)** · Compatibility Manifest(:1205) · SCL command schema(:1206) · **per-cell 필수 attestation consumer 집합(:1207)** · aggregate constraint 직렬화(:1208) · re-arm vs scoped suspension 매핑(:1209) · emergency envelope(:1210) · DR retention(:1211) · **§27 item 11–19 bundle-binding(:1216–1218)** |
| #13 are | **dimension/unit/scope/비교 규칙(:1008–1009)** · consistency-cut(:1010–1011) · valuation/stress 모델 선택(:1012–1013) · **scenario set 거버넌스(:1014–1015)** · benefit proof 런타임(:1016–1017) · deterministic numeric 메커니즘(:1018) · risk generation fence(:1021–1022) · **non-live 조합 목록(:1027–1028)** · restricted-production evidence(:1029–1030) · AFG/IAP binding(:1031–1032) |
| #14 ioc | **conformance registry(계좌/심볼/틱 등, :1053–1054)** · final-egress wire 관측(:1057–1058) · **transport-only field 판정(:1059)** · broker semantics(P0-2, :1060–1061) · Construction Generation fence(:1062–1063) · 격리·reconcile(:1067) · Proposal id scheme(-020/-023, :1071–1073) |
| #15 iap | **policy language+evaluator(:1109–1110)** · independent source path(:1111–1112) · TAG fencing(:1114–1115) · Intent Registry 런타임(:1116–1117) · signature format(G8, :1120–1121) · **human-approval class 결정(:1124–1125)** · correction closure(:1126–1127) · orthostate 배선(:1132–1134) · IOC binding(:1135–1137) |
| #16 afg | RCL vector schema 확장(:1105–1106) · **atomic 2-slot commit protocol 미해결 rcl 확장(:1107–1110)** · scope graph(:1111–1112) · ordering evidence(:1114–1115) · SDK claim-boundary(:1116–1117) · cause lineage(:1118–1119) · **protective 분류 per broker(P0-2, :1120–1121)** · sub-ledger lease(:1122) · traffic 격리(:1125–1126) · **dimension-id 전역 namespace 규약(Gap-1, :1283–1284)** |
| #17 sbr | **Barrier Policy schema·trigger classifier(:1086–1087)** · SCL topology(:1088–1089) · broker query 프로토콜(P0-2, :1092–1093) · **partial recovery 허용 dependency 판정(:1094–1095)** · corroboration 규칙(-006, :1096–1097) · RCL 명령(:1098–1099) · workflow 제품(:1100–1101) · **HAG roles(§21 SHALL NOT 정합, :1102–1103)** · control-plane loss 합성(:1104–1105) · DR(:1106–1107) · downstream obligations(:1113–1122) |
| #18 replacement | **atomic-replace 증명 조합(P0-2, :1346–1347)** · overlap-first first-live scope(G7, :1348) · **cancel-first 허용 여부(bounds 후, :1349–1350)** · reservation 증거(:1351) · FQP event sequence(P0-2, :1352–1353) · **§15↔VP 미매핑 4 timing point 매핑 확정(:1303–1315)** · rcl 원자 commit(:1357–1358) · -019 admissibility(:1362–1364) · **residual risk 명시 수용(:1365)** |
| #19 venue | **approved sources per scope(:1073–1075)** · session-phase 모델(:1076–1077) · dynamic policy content(:1080–1081) · broker query+assurance(P0-2, :1082–1083) · 단일-소스 검증 정책(:1084–1085) · Constraint Generation 런타임(:1086–1088) · partial semantics(:1091–1092) · 격리·reconcile(:1096–1097) |
| #20 hag | **identity provider·authenticator 선정(:995–996)** · principal graph 시스템(:997–998) · **quorum N·role matrix(:999–1000)** · **조직 분리 conflict 목록(:1001–1002)** · **attestation/서명 format(:1003–1004)** · SCL 소비(:1005–1006) · **delegation/succession policy(:1007–1008)** · HALT authenticator(:1009–1010) · restrictive latch(:1011–1013) · containment 사전 정의(:1014–1016) · compromise 대응(:1017–1018) · -025/-026 상류(착지됨 — 배선 후속, :1032–1033) |
| #21 nontrade | **source-authority rules(:1631–1633)** · broker adjustment semantics(P0-2, :1634–1635) · first-live scope(G7, :1636–1637) · **transition protocol 선택(:1638–1639)** · **residual risk 수용(:1640–1641)** |
| #22 egress | **signer·credential model 선정(:971–972)** · 네트워크 route(:973–974) · **QCC schema·quorum rule·crypto library(:975–976)** · trust bundle rotation(:977–978) · egress topology(:979–980) · broker semantics(P0-2, :981–982) · Hard Egress Fence Proof(:983–984) · proxy 경계 분류(:985–986) · manual portal 거버넌스(:987–988) · protective 배타성(:989–990) · **SoD 독립 identity(:994–995)** · 미착지 상류 배선(-024/-029/-030/-025/-026/-010 — **전부 착지됨, 배선 후속**, :1006–1009) |
| #23 cur | Ordering Domain 커플링(:732) · owner-auth 메커니즘(:733) · latch storage(:734) · per-send 원자 트랜잭션(:735) · barrier(:736) · 신호 delivery(:737) · first-byte 증명(:738) · degraded subset(P0-2, :740) · DR(:741) · quorum/암호(:745) · -025 trial 차원(착지 — 배선 후속, :746) · governance generation 차원(-026/-027/-028/-029/-030 전부 착지 — 배선 후속, :747) |
| #24 posttrade | **finality recipes(:1777–1778)** · statement coverage rules(:1779) · **legally enforceable netting/reuse rules(법무·인간, :1780–1781)** · **brokercap settlement dimension 신설 여부(:1784–1785)** |
| #25 rlp | worst-credible 계산(rcl, :887) · per-action binding(egress, :888–889) · abort/HALT 독립성(:890) · evidence 조립(:891–892) · promotion registry(:893) · hard-fence(:894) · identity 분리(:895) · finding-0+traceability(:899) · **independent review workflow(G3/G9, :901)** · **Single-Operator Variant 채택(:902)** · trial Live Authorization(:903) · eligibility 12항목(:904) · EV-L6 모니터링(-028 착지 — 배선 후속, :905) |
| #26 wdr | **boundary classifier 독립 리뷰(:969)** · deterministic 평가(:970) · compensating-control 정책(:971) · activation(:973) · Deviation Generation 런타임(:974–975) · fault injection(:976) · recovery(:977) · identity 분리(:978) · worst-credible(rcl, :984) · Hard Safety Envelope(spg, :985) · -027 착지 — 실좌표 배선 후속(:988) |
| #27 fd | **배포 프로파일 + Allocation Matrix INSTANCE 승인(:717–718)** · **§10.1 무주인 2항 소유자 지명(per-cell egress-identity 유일성·market-data credential 분리, :723–726)** · **identity inventory·cell 6-field·에스컬레이션 지명(:727–729)** · isolation-claim↔sbr 좌표 거버넌스(:730–732) · environment class INSTANCE(:733–735) · §8.4 partition 3-boolean 저작 여부(:815–817 — Phase-1 미저작 권고 유지) |
| #28 sir | **signal registry·classifier 독립 리뷰(:1163)** · Incident Generation 런타임(:1164–1165) · HALT 독립성(:1166) · identity 분리(:1167–1168) · deny-before-stop 런타임(:1169–1170) · broker containment(P0-2, :1171) · closure 거버넌스(hag·+Security, :1172) · -025/-026/-017 배선(:1173) · 경제효과 보수 표현(rcl, :1178) · -028/-029 좌표(착지 — 배선 후속, :1184–1185) |
| #29 sci | **8 canonical schema 승인+INSTANCE(:1041)** · +Security 전수 평가(:1043) · +Broker 실측(:1044) · sir handoff seam 확정(:1045–1047) · **형제 verdict 소유 거버넌스(:1048–1050)** · **문서 위생 후속("not-landed" 주석 8파일+firewall `tos.ptf` placeholder 정정, :1054–1055)** |
| #30 stm | **registry·coverage compiler 독립 리뷰(:1375)** · source 구현·보안 리뷰(:1376) · **deterministic evaluator differential test(:1377–1378)** · Monitor Generation 런타임(:1379–1380) · suppression/escalation 프로토콜(:1381–1382) · identity 분리(:1383–1384) · -025 EV-L6·-027 handoff 계약(:1385–1386) · finding-0(:1391) · 형제 이관·-029 주입(:1394–1397) |

---

## 8. 수치 키 전수 (3-tier)

### 8-1. 확정 누락 — 프로파일에 키 자체가 없음 (신설 27항)

| 항목 | 출처 |
|---|---|
| source production delay 전용 키 | capsule:745 (ADR-018 §14:356) |
| transport-and-queue delay 전용 키 | capsule:746–748 |
| consumer receipt age 전용 키 | capsule:748–749 |
| correction/late-revision horizon 전용 키 | capsule:749–750 |
| `MAX_anchor_cadence_ms` / `B_evidence_anchor` | evidence-store:823–829 |
| `evidence_integrity_policy` id/gen/digest·`evidence_location` | evidence-store:830–831 |
| transport-and-queue uncertainty | trustworthy-time:642–644 |
| clock-domain-conversion uncertainty | trustworthy-time:645 |
| source-disagreement tolerance | trustworthy-time:646–647 |
| offset bound(drift ppm 외) | trustworthy-time:648–649 |
| stabilization interval | trustworthy-time:650 |
| future-timestamp tolerance | trustworthy-time:651 |
| holdover safety margin(전용) | trustworthy-time:652–654 |
| source precision·source-sequence-gap | trustworthy-time:653–654 |
| Reserved Protective Capacity 최소 magnitude | rcl:819–824 |
| Capacity Domain 경계·f/2f+1 | rcl:825–827(Phase B) |
| quarantine escalation horizon | rcl:828–830 |
| **Lease-Expiry Fence 지속시간** | safety-authority:952–958 |
| **Live Authorization maximum-validity** | liveauth:1089–1097 |
| `MAX_safety_profile_validity_ms` | spg:1158–1159 |
| `MAX_envelope_review_interval_ms` | spg:1159 |
| `MAX_activation_staging_age_ms` | spg:1159 |
| `MAX_compatibility_attestation_age_ms` | spg:1159–1160 |
| blast-radius 상한(cell-blast) | failuredomain:693–695 |
| safety-cell HALT→global HALT 에스컬레이션 조건 | failuredomain:695–696 |
| DCE-INV-007 DSL evaluation time/resource bound | strategy-dsl:540–546 |
| `MAX_time_conservative_freshness_age_ms` (UNCHK-024 잔여 1필드 — resolver `BarTimeProjection.max_age_bound`) | ADR-002-008 §9; 등록 2026-09-04(값 null, 승인 대기) — `docs/plans/2026-09-04-tos-unchk024-max-age-bound-key-disposition-draft.md` §2 |

### 8-2. Candidate (누락 확정도 커버 확정도 아님 — 8군)

orthostate 지식-staleness 키(-006 의존, orthostate:929–938) · recon bound family 3종(recon:980–988) ·
brokercap INSTANCE bound family(brokercap:1176–1181) · protective reserve matrix·retry budget(protective:
1274–1286) · afg rate/burst 계열(afg:1065–1072 — INSTANCE 귀속) · replacement §15 timing 4점 매핑(replacement:
1303–1315) · posttrade brokercap dimension 신설 여부(posttrade:1784–1785) · fd `B_rate_limit_recovery` 충분성
(failuredomain:696–697).

**병기 — brokercap INSTANCE bound family(brokercap:1176–1181) 군 (설계 #36 구현 커밋에서 등재, 2026-08-06)**

| 항목 | 내용 |
|---|---|
| 키 | brokercap venue shape constraint bound — band/tick per scope (`price_min`/`price_max`/`tick_size`) |
| 현상 | 슬라이스 provisional stand-in(`tos/tests/slice/_slice_fixtures.py::venue_shape_constraints` = 1000 / 9,000,000 / 500). 값이 아니라 **충족 조건만** 승인됨: `price_min ≤ V ≤ price_max` ∧ `(V − price_min) mod tick_size == 0`, 여기서 `V` = step 3에 도달하는 모든 값-표면 shape 가격 |
| 소유 | **P0-2 Broker Capability Profile INSTANCE** (설계 #34 §9 broker-specific bound 행) |
| cross-ref | KIS 초안 dimension 17 `MARKET_INSTRUMENT_CONSTRAINTS`(broker-capability-profile-kis-draft:88 · status **UNKNOWN** · 근거 = 로컬 설정, broker 조회 코드 없음) · 동 문서 §7 item 3/4 게이트(`:273–274` — INSTANCE bound family 값·키 승인 / capability 값·conformance class 할당) |
| 교체 트리거 | 슬라이스 scope의 Broker Capability Profile INSTANCE가 **측정된** venue shape 제약으로 승인되어 dimension 17이 UNKNOWN→VERIFIED로 승격되는 관측 시(PASS 규율 `:60` "bounds were measured" + 독립 리뷰어 서명, `broker_specific`=MEASURED `:97`) → 슬라이스 fixture stand-in을 프로파일-유도 값으로 교체 |
| VERIFICATION-PROFILE 영향 | **신규 키 0건.** venue #19 §8.0 비준 판정(venue-tradability-design:1001 — tick/lot/band는 `VenueConstraintPolicy` policy content 주입이지 코드 상수 아님)과 정합하므로 §8-1(VP·P0-1 Bounds-Approver 트랙)에는 행을 추가하지 않는다 |
| 전방 입력 (미해소) | 이 제약의 진짜 상류가 P0-2(broker INSTANCE)가 아니라 **policy 아티팩트 거버넌스**(`VenueConstraintPolicy` policy-content · spg §27 q1)일 가능성 — 소관 재정밀화를 후속 계약 입력물로 남긴다 |
| provenance | 오케스트레이터 판정 2026-08-06. **정본 = 설계 #36 §10-2**(`docs/plans/2026-08-05-tos-venue-shape-value-surface-design.md`) 비준 기록 자체이며 외부 커밋 아티팩트 인용이 아니다 |

### 8-3. 승인 대기 — 키 실재·값 null/TBD (~150키, Bounds-Approver 값 승인 대상)

문서별 소유 키 목록은 추출 실측대로: Time 5 · #4 5 · #5 11 · #6 6 · #7 5(§25 12 bound 실재) · #8 1 · #10 5 ·
#11 5 · #13 4 · #14 3 · #15 5 · #16 8 · #17 7 · #18 4 · #19 5 · #20 5 · #21 3 · #22 6 · #23 7 · #24 19 ·
#25 12 · #26 6 · #27 2 · #28 8 · #29 10 · #30 11. (키명 전수는 각 설계 문서 §8 표가 정본 — 본 register는
중복 전사 대신 소유-문서 참조를 유지한다. 전 키가 `owner: TBD`이므로 **키별 owner 지정도 승인 작업의 일부**.)

---

## 9. 미결 운영자 판단 지점 (23건 / 9문서)

위임 자동비준 기간 문서 중 INDEX.md에 "판단 지점 … 승인" 절이 없는 것들. **성격: 대부분 "이미 구현이 그
전제로 착지한 사후 확인"이며, 뒤집으면 재작업이 발생한다. 일괄 소급 승인(현상 유지) 또는 개별 재심 중 택.**

| 문서 | 판단 지점 | 뒤집을 때 비용 |
|---|---|---|
| #14 ioc | 명명 `ioc`(TIF 오독 리스크) · `EconomicEffectEnvelope`=rcl CapacityVector 별칭(5번째 edge) · IndependentId 선택 | 구현 완료 — 개명/edge 제거는 대규모 재작업 |
| #15 iap | 명명 `tos.iap` · sibling edge 0 · `ApprovalConsumptionRecord` 소유 · IndependentId 선택 | 동상 |
| #17 sbr | 명명 `tos.sbr` · iap `invalidation_closure` 로컬 재저작(DRY) · edge 0 vs typed-reuse | 동상 |
| #19 venue | 명명 `tos.venue` · time `SessionContext` typed-reuse 여부 | 동상 |
| #20 hag | 명명 `tos.hag` | 동상 |
| #23 cur | 명명 `tos.cur` · **Local Restrictive Latch 소유=egress 유지**("독립 리뷰어 재검토 지점") | latch 이관 시 egress+cur 재작업 |
| #25 rlp | 명명 `tos.rlp`(soft load-bearing) · not-Phase-1 세분 · content-owner/boundary-seal 존치 | 동상 |
| #26 wdr | 명명 `tos.wdr` · greenfield 판정 · **rcl edge 0** · 세분 | 동상 |
| #16 afg | §10.3 6열거 vs INDEX "4건 승인" — **미포함 2건 특정·소급 처분 필요** | 확인 후 기록 정정 |

---

## 10. 관측 이상 (사실 기록)

1. **#16 AFG 승인 계수 불일치**: 설계 §10.3:1271–1284는 판단 지점 6항목, INDEX.md:35는 "판단 지점 4건 승인".
   미포함 2건의 특정과 소급 처분 필요.
2. **IMPLEMENTATION-PLAN-002:3 stale**: "no implementation code has been written"은 현 디스크(tos/ 30패키지·
   pytest 7482)와 모순. :7 "This plan authorizes nothing"은 여전히 유효. 스펙 텍스트 갱신은 GOV-001 change
   process 소관(패치 트랙) — 본 register는 기록만.
3. **P0-4 tos-spec 미반영**: 프로젝트 측 비준(2026-07-20)이 tos-spec 텍스트에 반영된 흔적 0건(negative-grep
   실측). PLAN:20이 "project workflow"로 위임했으므로 규범 위반 아님 — 단 gate-status류에 교차 기록이 없어
   후속 독자가 P0-4를 열린 것으로 오독할 수 있음(패치 후보).

---

## 11. 권고 실행 계획 + 운영자 즉시 결정 항목

**단계 (의존 순서)**:

1. **D1 역할 체계 확정** → 2. **P0-3 지정 실행**(CSV 372행 3열 채움 — 기계 편집) + **P0-1 bounds 승인
   패키지**(비-broker 키부터: 오케스트레이터가 키별 후보값+근거 draft 저작 → Bounds-Approver 승인 →
   YAML 갱신·`status: APPROVED`) → 3. **§8-1 누락 키 26항 신설**(스펙 패치 트랙 — GOV-001 change process) →
   4. **§9 미결 판단 지점 23건 일괄 처분** → 5. **P0-2 착수**(KIS Broker Capability Profile INSTANCE —
   non-normative·별도 트랙) → 6. G2 프로덕션 canonicalization 결정 → 7. VER §383 8조건 충족 확인 →
   EV 실행·독립 서명·acceptance 재평가(§2 사슬).

**즉시 결정 필요 (운영자)**:

- **D1 — 역할 체계**: PLAN §3 역할(Bounds-Approver·System-owner·Impl·Evidence-owner·Independent-Reviewer·
  Live-Armer)에 실명/실체 배정. 하드 제약: Impl ≠ Independent-Reviewer(전 사이클의 저작·구현 AI는 리뷰어
  불가), Bounds-Approver ≠ Live-Armer, 아키텍처 저자/통합자 ≠ Independent-Reviewer. **1인 운영 환경의 핵심
  쟁점 = Independent-Reviewer의 실체**: (a) 외부 인간 지정, (b) ADR-DEV-005 §7 하 AI 리뷰어 + decorrelation
  적극 입증(모델/substrate provenance 기록 — 별도 모델·별도 컨텍스트·common-mode 부정 근거 문서화), (c)
  혼합(AI 리뷰 + 인간 최종 서명). ADR-DEV-005 §7은 AI-on-AI를 decorrelation 입증 없으면 common-mode로
  fail-closed 처리.
- **D2 — bounds 승인 방식**: (a) 오케스트레이터가 82키(+limits 50)의 키별 후보값·근거·보수 방향 draft를
  일괄 저작 → 운영자(=Bounds-Approver 배정 시) 검토·승인, broker-측 키는 P0-2 이후로 명시 분리; (b) per-bound
  스키마 보강 여부(VER §6 요구 7속성 중 부재 2속성 — `applicable scope`·`review date` — 추가는 스펙 패치).
- **D3 — §9 미결 판단 지점 23건**: 일괄 소급 승인(현상 유지 — 전부 구현 착지 완료 상태) vs 개별 재심.
  #16 AFG 2건은 특정 후 별도 처분.
- **D4 — §8-1 누락 키 26항**: 스펙 패치 트랙 착수 승인(GOV-001 change process 하 VERIFICATION-PROFILE 키
  신설 — 값은 null로 신설하고 D2 승인 흐름에 합류).

---

## 12. 실측 규율 기록

- 두 추출 트랙 모두 anti-phantom(존재/부재 양방향 grep·file:line·`grep|head` 절단 금지) 하 수행. 트랙 ①은
  31/31 커버리지 체크리스트로 누락 0을 증명, 트랙 ②는 부재 주장 6건 negative-grep 표를 병기.
- 오케스트레이터 재실측 3건: PROFILE:17–21(version 2.1-PROPOSED·status PROPOSED·approved_by []·effective_from
  null) · CSV 372행 전수 파싱(reviewer TBD 372·status 단일값 NOT_IMPLEMENTED) · PLAN:29–38(Phase-0 표 4행
  verbatim) — 전부 추출 보고와 일치.
- 본 문서의 문서별 file:line 인용은 추출 시점(2026-07-29) 실측값이다. 설계 문서가 이후 개정되면 행번호가
  이동할 수 있다 — 재사용 시 재실측.
