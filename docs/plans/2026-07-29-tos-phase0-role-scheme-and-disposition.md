# Phase-0 결정 기록 — 역할 체계(D1) + 미결 판단 지점 처분(D3) (2026-07-29)

> **문서 성격**: 프로젝트 측 **결정 기록**(P0-4 경계 비준 기록과 동급의 project-workflow 산출물). GOV-001의
> 세 거버넌스 행위가 아니며 어떤 EV 항목도 이동시키지 않는다. 근거 결정 = 운영자 2026-07-29 D1~D4 응답
> (register `docs/plans/2026-07-29-tos-phase0-human-gate-register.md` §11의 결정 패키지에 대한 답변).

---

## 1. D1 — 역할 체계 확정 (IMPLEMENTATION-PLAN-002 §3 role scheme의 프로젝트 측 배정)

**운영자 결정(2026-07-29): "혼합 — AI 리뷰 + 운영자 서명".**

| 역할 (PLAN §3) | 배정 | 기록 규약 (register CSV 등 기입 문자열) |
|---|---|---|
| System owner | **운영자(harris.lee)** | `operator` |
| Bounds-Approver (Safety/Risk authority) | **운영자(harris.lee)** | `operator` (PROFILE `approved_by`) |
| Implementation owner | **AI 오케스트레이션 세션**(본 시리즈 저작·구현 주체) — provenance 의무: 모델/세션 식별 기록(ADR-DEV-005 §7) | `ai-impl(claude-orchestrated)` |
| Evidence owner | **운영자(harris.lee)** (수집·보존 책임; 조립 실무는 AI 위임 가능하되 책임 귀속은 운영자) | `operator` |
| **Independent-Reviewer** | **혼합**: ① decorrelation 입증된 별도-컨텍스트 AI 리뷰(저작/구현 세션과 상이한 컨텍스트·프롬프트 계보, provenance[모델·substrate·determining inputs] 기록 의무 — ADR-DEV-005 §7 4배제 각각에 대한 근거 문서화) + ② **운영자 최종 서명**(evidence manifest countersign — VER-002-001 §9.5:364–366의 서명 주체) | `ai-review(decorrelated)+operator-countersign` |
| Live-Armer | **의도적 미지정(fail-closed)** — live track(GOV-001 제3행위·ADR-002-007/-025)은 별도 게이트이며, 미지정 상태에서는 어떤 live arming도 구조적으로 불가 | (공란 유지) |

**SoD 하드 제약 충족 검증(PLAN:157)**:
- `Impl ≠ Independent-Reviewer`: 구현 주체(AI 오케스트레이션 세션)와 리뷰 주체(별도-컨텍스트 AI + 운영자
  서명)는 상이 — 단 **AI-on-AI common-mode 우려는 ADR-DEV-005 §7이 요구하는 decorrelation 적극 입증으로만
  해소**되며, 입증 실패 시 해당 리뷰는 fail-closed로 무효(리뷰마다 provenance 기록이 입증 수단). 본 시리즈의
  적대적 코드 리뷰 관행(별도 컨텍스트·별도 브리프·실측 의무)이 그 입증의 기초 형식이나, **정식 EV 서명
  리뷰에는 저작 세션과 다른 모델 계열 사용을 우선**한다(가용 시).
- `Bounds-Approver ≠ Live-Armer`: 운영자 = Bounds-Approver, Live-Armer = 미지정 ⇒ 충족(운영자를 Live-Armer로
  배정하려면 **Bounds-Approver 재배정이 선행**되어야 함을 명문화 — 미래 live track의 선결 조건).
- `아키텍처 저자/통합자 ≠ Independent-Reviewer`: tos-spec 저작 AI 계열과 EV 리뷰 AI의 decorrelation 입증
  의무에 포섭(위 provenance 규약).

**효력**: 이 배정으로 P0-3(register 372행 owner/evidence-owner/reviewer 지정)의 기입 값이 확정된다. CSV 기입
자체는 후속 기계 편집(§3-1)으로 실행한다. `verification_profile_version` 열은 `2.1`(승인 전이므로 PROPOSED
상태 병기), `evidence_location`은 `tos-evidence/`(리포 내 규약 경로 — 실제 저장 substrate는 ADR-002-016
ENGINE 트랙 소관, 그 전까지 경로 예약만)로 기입한다.

---

## 2. D3 — 미결 운영자 판단 지점 23건 처분

**운영자 결정(2026-07-29): "일괄 소급 승인 + AFG 2건만 특정".**

### 2.1 일괄 소급 승인 (21건)

register §9의 9문서 판단 지점 중 AFG 2건을 제외한 전 항목(명명 8건·edge/소유/세분 판정 13건)을 **현상 유지로
일괄 소급 승인**한다. 근거: (a) 전부 위임 자동비준(2026-07-25 지시) 기간의 산출물로, 각 건은 독립 비평 리뷰
통과·구현 착지·적대적 코드 리뷰 통과를 거쳤다 — 위임의 포괄 범위에 판단 지점 승인이 포함됨을 본 기록으로
소급 명문화; (b) 뒤집을 경우 재작업 비용이 크고, 어떤 건도 안전 방향(fail-closed) 훼손 우려가 리뷰에서 제기
되지 않았다. **개별 목록은 register §9 표가 정본이며 본 기록이 그 전 행에 "승인(2026-07-29 소급)"을 부여한다.**
"독립 리뷰어 재검토 지점"으로 명시된 5건(cur latch 소유·rlp 세분/boundary-seal·wdr greenfield/rcl edge)도
동일 승인하되, **향후 EV 정식 리뷰(P0-3 배정 리뷰어) 수행 시 재검토 대상 목록으로 이월**한다(승인이 재검토
의무를 소멸시키지 않음).

### 2.2 AFG 2건 특정 결과 (INDEX "4건 승인" vs §10.3 6열거)

실측: `2026-07-26-tos-action-flow-budgeting-design.md` §10.3:1271–1284는 6항목, INDEX.md 기록은 "판단 지점
4건 승인". 미포함 2건 특정:

| 항목 | 내용 | 판정·처분 |
|---|---|---|
| §10.3 항목 4 (:1278) | VP-002 bounds 8키 Bounds-Approver 승인 | **기록 오류 아님** — 이는 설계 판단 지점이 아니라 **P0-1 그 자체**(G1). 비준 시점에 승인 불가능한 분류였음. 처분 = **D2 bounds draft 패키지 흐름에 합류**(afg 8키는 register §8-3에 이미 계상) |
| §10.3 항목 6 (:1283) | dimension-id 전역 namespace 규약(Gap-1) — `CapacityVector` 4소비자(rcl/are/ioc/afg) 간 disjointness | **기록 오류 아님** — cross-package Phase-0 규약 결정. 처분 = **D2 draft 패키지에 규약 초안 포함 지시**(권고 초안: 패키지 접두사 `rcl.`/`are.`/`ioc.`/`afg.`를 dimension-id에 의무화하고 무접두사는 rcl 소유 기존 id로 한정 — 채택 여부는 D2 승인 시 운영자 결정) |

⇒ INDEX.md:35의 "4건"은 **설계-비준 대상 4건(항목 1·2·3·5)에 대한 정확한 기록**으로 판정. 정정 불요, 본
기록으로 해소.

---

## 3. 후속 배선 (이 기록이 여는 작업)

1. **P0-3 실행**: §1 기입 규약으로 `EVIDENCE-REGISTER-002.csv` 372행의 6열(implementation_owner·
   evidence_owner·independent_reviewer·verification_profile_version·broker_capability_profile[해당 행]·
   evidence_location)을 기계 편집 + 편집 전후 전수 검증(행수·id 불변·status 무변경). broker_capability_profile
   열은 +Broker 행에 `pending-P0-2`로 기입(INSTANCE 미착지 정직 표기).
2. **D4 패치 트랙**(병렬 진행): 누락 키 26항 신설(null·owner TBD로 신설해 D2 흐름 합류) + PLAN:3 stale 문구
   정정 + P0-4 교차 기록. GOV-001 change process(patch 문서 + 대상 파일 편집) 준수.
3. **D2 bounds draft 패키지**(D4 착지 후): 비-broker 전 키(기존 82+50 중 비-broker + D4 신설분)의 키별
   후보값·근거·보수 방향·owner 후보 + per-bound 스키마 보강(scope·review date 2속성) + dimension-id 규약
   초안(§2.2) → 운영자 일괄 검토·승인 → YAML `APPROVED` 갱신.
