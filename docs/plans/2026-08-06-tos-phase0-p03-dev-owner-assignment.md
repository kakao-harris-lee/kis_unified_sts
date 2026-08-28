# Phase-0 이행 기록 — P0-3 개발 트랙 오너 배정 (2026-08-06)

> **문서 성격**: 프로젝트 측 **이행 기록**. 2026-07-29 운영자 D1 결정의 **기계적 집행**이며 새로운 승인 행위가
> 아니다. GOV-001의 세 거버넌스 행위(G1)가 아니고, 어떤 EV 항목도 상태 전이시키지 않으며, 어떤 ADR-DEV
> acceptance·restricted-live·production 권한도 만들지 않는다.
> **대상**: `tos-spec/src/part-3-development/verification/EVIDENCE-REGISTER-DEV.csv` 중 **plain-TBD 98행**
> 및 그 미러인 `EVIDENCE-REGISTER-DEV.md` 레지스터 표의 동일 98행(§2-1).

---

## 1. 권한 근거 — 이 편집은 새 승인이 아니다

이 편집은 **이미 내려진 운영자 결정(D1)이 지정한 기입 문자열을, 이미 지정된 대상 범위에 기계적으로 적용**한
것이다. 세 근거가 독립적으로 이를 뒷받침한다.

| # | 근거 | 인용 |
|---|---|---|
| (a) | **D1 역할 체계** — 운영자 2026-07-29 결정 "혼합 — AI 리뷰 + 운영자 서명". Implementation owner=`ai-impl(claude-orchestrated)` / Evidence owner=`operator` / Independent-Reviewer=`ai-review(decorrelated)+operator-countersign`. 이 표가 **기입 문자열의 정본**이며, 표 머리는 "register CSV **등** 기입 문자열"로 **비망라** 표현이다(`:13`) | `docs/plans/2026-07-29-tos-phase0-role-scheme-and-disposition.md:13–20` (역할 표), `:33` (원문: "**효력**: 이 배정으로 P0-3(register **372행** owner/evidence-owner/reviewer 지정)의 기입 값이 확정된다") |
| (b) | **gate-status §7 step 2** — 개발 트랙 레지스터를 명문으로 스코프에 포함: "Assign implementation owners, evidence owners, and independent reviewers for all 372 items in EVIDENCE-REGISTER-002.csv, **and for all 118 items in EVIDENCE-REGISTER-DEV.csv**." | `tos-spec/src/part-1-foundation/ARCHITECTURE-GATE-STATUS.md:1343` |
| (c) | **human-gate register §2** — Phase-0가 소화할 step 2의 몫을 "**372+98행 지정**"으로 계량 | `docs/plans/2026-07-29-tos-phase0-human-gate-register.md:74` ("GATE-STATUS §7 13단계 중 Phase-0는 step 2(372+98행 지정)·step 3(bounds 승인)에 해당"); P0-3 게이트 정의는 `:51` |

**(c)의 "98"이 현재 plain-TBD 98행과 동일 집합임을 구조적으로 실측**(자기신고 아님): 2026-08-02 ECO/IOM 등재
직전 리비전(`git show acd45c43^`)의 DEV 레지스터는 정확히 98행이며, 그 `evidence_id` 집합은 현 CSV의
plain-TBD 98행 집합과 **대칭차 ∅**로 일치한다. 즉 register §2가 "98"로 계량한 대상은 이번 편집 대상과 같은
행들이고, 이후(2026-08-02) 등재된 ECO 12·IOM 8행은 그 계량에 포함된 적이 없다.

**스코프 확장 권한의 출처 (근거 분리)**: D1 효력 문언(`:33`)은 **372행을 명시**하나 역할 표 자체는
"register CSV **등**"으로 비망라이며, **DEV 98행으로의 스코프 확장 권한은 (a)가 아니라 (b) gate-status §7
step 2 문언**("and for all 118 items in EVIDENCE-REGISTER-DEV.csv", `:1343`)**과 (c) human-gate register §2
"372+98행"에서 온다.** (a)는 *어떤 문자열을 기입할지*를 확정하고, (b)·(c)는 *어느 행에 기입할지*를 확정한다 —
이 편집은 두 축의 교집합이며 어느 축도 새로 만들지 않는다.

**Part-1 선례**: 동일 D1 규약으로 `EVIDENCE-REGISTER-002.csv` 372행은 2026-07-29 커밋 `f85434c3`(P0-3)에서
이미 기입 완료. 이번 편집은 그 P0-3의 **개발 트랙 잔여분**이다.

---

## 2. 범위 — plain-TBD 98행

3개 오너 열이 **전부 정확히 `TBD`**인 98행만 대상으로 했다. 편집 전 실측에서 3열의 TBD 여부가 행 내에서
엇갈리는 행(mixed)은 **0건**이었다 — 즉 98/20 분할은 깨끗하다.

| 열 | 편집 전 (98행) | 편집 후 (98행) |
|---|---|---|
| `implementation_owner` | `TBD` | `ai-impl(claude-orchestrated)` |
| `evidence_owner` | `TBD` | `operator` |
| `independent_reviewer` | `TBD` | `ai-review(decorrelated)+operator-countersign` |

그 외 어떤 열도 건드리지 않았다(§4 근거).

### 2-1. MD 미러 — 매핑 규약 (Part-1 선례 채택)

`EVIDENCE-REGISTER-DEV.md:52`의 레지스터 표는 **CSV 3개 오너 열을 2열로 축약 표현**한다. 그 표의 기존
표현 규약을 그대로 따랐고(신설 없음), 매핑은 다음과 같다. **Part-1과 동일함의 근거 3중**:
(ㄱ) `EVIDENCE-REGISTER-002.md:27`이 `Owner ← implementation_owner` + 나머지 CSV 전용을 **성문화**,
(ㄴ) `:31`의 표 헤더가 `| ID | Domain | Test | ADR | Minimum level | Status | Owner | Reviewer |`로 DEV
`:52`와 **8열 문자열 동일**, (ㄷ) 두 레지스터의 데이터 행이 동일 기입 문자열을 렌더(Part-1 372행 및 DEV의
이번 98행 모두 `… | ai-impl(claude-orchestrated) | ai-review(decorrelated)+operator-countersign |`).

| MD 표 열 (`:52` 헤더) | CSV 열 | 이번 편집 |
|---|---|---|
| `Owner` | `implementation_owner` | `TBD` → `ai-impl(claude-orchestrated)` |
| `Reviewer` | `independent_reviewer` | `TBD` → `ai-review(decorrelated)+operator-countersign` |
| (대응 열 없음) | `evidence_owner` | **CSV 전용** — MD에 열이 존재하지 않으므로 미러 대상 아님 |
| `ID`/`Domain`/`Test`/`ADR`/`Minimum level`/`Status` | `evidence_id`/`domain`/`title`/`primary_adr`/`minimum_evidence_level`/`status` | 무변경 (전수 대조로 확인 — §7) |

**매핑 근거의 성격**: 이 매핑은 **관측된 표 구조에서 도출**했다(헤더 8열 + ECO/IOM 20행이 이미
`| TBD-economic-evidence-implementation-owner | TBD-independent-investment-reviewer |`로 렌더돼 있어 열 대응이
구조적으로 확정됨). **관측 기록**: Part-1 레지스터는 이 매핑을 "Mirror column mapping" 문단으로 명문화하고
있으나(`EVIDENCE-REGISTER-002.md:27`), **DEV 레지스터에는 대응 문단이 존재하지 않는다**(양방향 grep 확인).
Part-1과의 구조 차이로 **기록만 남기며, 본 작업에서 문단을 신설하지 않는다**(범위 밖 — 레지스터 본문 규약
신설은 별개 판단).

**정본 관계는 불변**: CSV가 machine-editable source이고 MD는 미러다
(`EVIDENCE-REGISTER-DEV.md:12–13`, `VER-DEV-001:6`). 이 편집은 그 관계를 바꾸지 않고 미러를 정본에
재동기화할 뿐이다.

---

## 3. 명시 제외 — ECO 12행 · IOM 8행 (20행)

이 20행은 **named-TBD**(`TBD-economic-evidence-implementation-owner`,
`TBD-independent-investment-operating-reviewer` 등)를 유지한다. 제외 사유:

1. **범위 밖** — §1(c)의 "98행" 계량에 포함되지 않은, 2026-08-02 등재분이다.
2. **역할이 아직 존재하지 않음** — 레지스터 자신이 "Every row is `NOT_IMPLEMENTED` with **pending accountable
   owner/reviewer roles**"라고 기록한다
   (`tos-spec/src/part-3-development/verification/EVIDENCE-REGISTER-DEV.md:189–199`). D1은 개발 트랙 일반
   역할을 배정했을 뿐 **investment/economic 책임 역할**을 창설하지 않았다. 존재하지 않는 역할을 일반
   `ai-impl`/`operator`로 덮어쓰면 **미결정을 결정된 것처럼 보이게 하는 fail-open**이 된다.
3. **G6 대기** — 두 계열 모두 **Proposed amendment 등재분**이며 등재 자체가 amendment를 발효시키지 않는다
   (`VER-DEV-001:30–32` — "their registration does not enact either G6 amendment"). 역할 배정은 그 amendment
   처분(GOV-001 G6)의 종속 결정이다.

따라서 이 20행의 named-TBD는 **정직한 fail-closed 상태**이며, 유지가 정답이다. 편집 후 이 20행은
CSV·MD **양쪽에서 바이트 동일**함을 검증했다(§7 check (e), (M6)).

**기계적 확증 (가)**: 이 제외는 판단일 뿐 아니라 리포 검사기가 **강제**하는 사항이다.
`tools/tos_spec_status.py:1223`(ECO 계열)과 `:1322`(IOM 계열)가 각각
`for field in ("implementation_owner", "evidence_owner", "independent_reviewer"):` 아래
`if not row[field].startswith("TBD-"): raise StatusError(… must expose pending {field})`를 돌린다. 즉
**이 20행을 일반 역할(`ai-impl…`/`operator`)로 덮었다면 검사기가 즉시 실패**한다 — §3의 fail-closed 판단이
독립적으로 기계 확증된다(검사기 PASS 실측은 §7-3).

---

## 4. 다른 열을 채우지 않은 근거 (fail-closed 판단)

DEV 트랙의 지정 요건 정본은 레지스터 MD의 **Required Administrative Fields**뿐이다:

> "Before an item becomes `READY`, assign implementation owner, evidence owner, independent reviewer,
> Verification Profile version, applicable Broker Capability Profile (Part-2/3 evidence is broker-agnostic,
> so this is `N/A` by default), and evidence storage location."
> — `tos-spec/src/part-3-development/verification/EVIDENCE-REGISTER-DEV.md:32–35`

**존재·부재 양방향 grep 실측** (`VER-DEV-001-Development-Track-Verification-Evidence-Specification.md`, 989행
전문):

| 검색어 | 히트 |
|---|---|
| `READY` / `ready` | **0** — READY 전이 절 자체가 없음 |
| `Verification Profile` / `verification_profile` | **0** |
| `evidence_location` / `evidence storage` | **0** |
| `Broker Capability` | **0** |
| `Administrative` | **0** |
| `reviewer` | 히트 있음(`:47`, `:233–252`, `:824–859`) — 그러나 **독립성 판정 기준**(ADR-DEV-005 §7)이지 **CSV 열 기입 규약이 아님** |

⇒ **VER-DEV-001에는 열 기입 규약이 부재**한다. 이 문서는 상태 어휘(§2)·게이트 규칙(§3)을 VER-002-001과
`EVIDENCE-REGISTER-002`에 **by reference**로 위임할 뿐 자신의 지정 규약을 정의하지 않는다.

이에 따른 열별 처분:

| 열 | 규약 유무 | 처분 | 근거 |
|---|---|---|---|
| `broker_capability_profile_version` | **존재** — "Part-2/3 evidence is broker-agnostic, so this is `N/A` by default" (DEV MD:34) | **무변경** (이미 충족) | 98행 전부 이미 `N/A`. 편집 불요. **두 술어를 분리 실측**: `broker_capability_profile_version != 'N/A'`인 행 = **9행**, `minimum_evidence_level`에 `+Broker`를 포함한 행 = **7행**(ECO-EV-002/007/008, IOM-EV-004/005/006/007). 차집합 2행(**ECO-EV-012, IOM-EV-008** — 둘 다 `Profile-dependent`)은 `+Broker` 최소레벨이 아니면서도 broker 열이 `TBD-approved-broker-capability-profile`로 fail-closed다. 9행 전부 ECO/IOM 소속 = 범위 밖 |
| `verification_profile_version` | **부재** | **`TBD` 유지** | DEV 트랙에 대응하는 Verification Profile 아티팩트가 없다. D1 `:34–36`이 지정한 `2.1`(PROPOSED 병기)은 **"P0-3(register 372행 …)"** 문맥, 즉 Part-1 `VERIFICATION-PROFILE-002` 스코프다. 이를 Part-2/3 행에 전용(轉用)하는 것은 D1이 내리지 않은 판단을 대행하는 것이므로 거부. ECO/IOM이 각각 `ECO-0.1-PROPOSED`/`IOM-0.1-PROPOSED`라는 **자기 계열 전용 프로파일**을 쓰는 사실이, 프로파일이 트랙-불가지가 아님을 방증한다(`VER-DEV-001:691`). |
| `evidence_location` | **부재** | **빈칸 유지** | `tos-evidence/<evidence-id>/<run-id>/` 경로 규약은 **Part-1 레지스터에만** 성문화돼 있다(`EVIDENCE-REGISTER-002.md:10`). DEV MD에는 대응 문장이 없고(`tos-evidence` 히트 0), 현재 값도 `TBD`가 아닌 **빈 문자열**이라 형태부터 다르다. 규약 없이 경로를 발명하지 않는다. |
| `status` | — | **무변경** | 118/118 `NOT_IMPLEMENTED` 불변 (§7 check (c)) |
| `latest_run_id` / `latest_result_date` / `notes` | — | **무변경** | 실행 산출물 열. 이 편집은 실행이 아니다. |

**요약**: DEV MD가 요구하는 **지정 6요소 중 4요소**(3 오너 + broker profile)가 충족됐고, **2요소**
(Verification Profile version, evidence storage location)는 **정본 규약 부재로 미충족 상태 유지**다.

**기계적 확증 (나)**: 이 2요소 미충족은 **방치가 아니라 유효한 차단**이다. `tools/tos_spec_status.py:390–397`이
```python
if status != "NOT_IMPLEMENTED":
    for field in ("implementation_owner", "evidence_owner", "independent_reviewer",
                  "verification_profile_version", "evidence_location"):
```
아래에서 값이 `{"", "TBD", "UNKNOWN", "UNASSIGNED"}`이면 `"{status} requires assigned {field}"` 오류를 쌓는다.
⇒ `verification_profile_version`이 `TBD`이고 `evidence_location`이 빈칸인 한 **어떤 행도
`NOT_IMPLEMENTED`를 벗어날 수 없다**. §4의 보수적 미기입 판단은 정확히 fail-closed 방향으로 작동하며, 규약
없이 임의 값을 채웠다면 오히려 이 차단을 해제했을 것이다.

---

## 5. 이 편집이 만들지 않는 것

- **READY 전이 없음.** DEV MD:32–35의 지정 6요소 중 2요소가 미충족이므로 `READY` 선행조건이 닫히지 않는다.
  또한 **VER-DEV-001 자체가 `Status: Proposed`**이다(`VER-DEV-001:3`). 98행은 전부 `NOT_IMPLEMENTED`로
  남는다.
- **status 무변경.** 118행 전부 `NOT_IMPLEMENTED`. 편집 전후 동일.
- **어떤 승인·권한도 없음.** ADR-DEV acceptance 없음, restricted-live/production 권한 없음, capacity 없음,
  live arming 없음(Live-Armer는 D1에서 의도적 미지정 fail-closed —
  `role-scheme-and-disposition.md:20`). VER-DEV-001 §4 narrow-only 제약이 그대로 유지된다.
- **gate-status §7 step 2를 종결시키지 않음.** step 2 문언은 DEV 118행 전체를 요구하나 이 편집은 98행만
  처분했다. **잔여 20행(ECO 12·IOM 8)은 §3 사유로 열린 채로 남는다** — step 2의 개발 트랙 몫은
  "98행 완결 + 20행 G6 종속 대기"로 정직하게 기록한다.
- **독립 리뷰가 수행된 것이 아님.** 리뷰어 **배정**은 리뷰 **수행**이 아니다. 실제 EV 리뷰는 ADR-DEV-005 §7
  decorrelation 입증 + provenance 기록 + 운영자 countersign을 각 건마다 요구한다.

---

## 6. SoD 하드 제약 재확인 (PLAN:165 — D1 당시 `:157`, 드리프트 +8)

D1 §1의 검증이 개발 트랙 98행에도 그대로 적용되며, 이번 기입이 어떤 제약도 무너뜨리지 않음을 확인한다.

정본 문언(재실측, `verification/IMPLEMENTATION-PLAN-002.md:165`): "Exclusions (hard): Impl ≠
Independent-Reviewer; Bounds-Approver ≠ Live-Armer; author/integrator of RFC-002/ADRs ≠
Independent-Reviewer." **ANCHOR DRIFT NOTE**: D1 기록(2026-07-29)은 같은 문장을 `:157`로 인용했다. 당시
리비전 기준으로 그 인용은 정확하므로 **D1 원문을 재작성하지 않으며**, 본 문서는 재실측 앵커 `:165`를
인용한다(드리프트 +8).

- **`Impl ≠ Independent-Reviewer`**: 기입값이 `ai-impl(claude-orchestrated)` vs
  `ai-review(decorrelated)+operator-countersign`으로 상이. 단 AI-on-AI common-mode 우려는 **문자열 기입으로
  해소되지 않는다** — ADR-DEV-005 §7의 4배제(저자 아님·저자 재실행 아님·common-mode 아님·provenance 기록)에
  대한 **건별 적극 입증**만이 해소 수단이며, 입증 실패 시 그 리뷰는 fail-closed로 무효다. 정식 EV 서명
  리뷰에는 저작 세션과 **다른 모델 계열** 사용을 우선한다.
- **`Bounds-Approver ≠ Live-Armer`**: 운영자=Bounds-Approver, Live-Armer=미지정 ⇒ 충족(불변).
- **`아키텍처 저자/통합자 ≠ Independent-Reviewer`**: tos-spec 저작 AI 계열과 EV 리뷰 AI의 decorrelation
  입증 의무에 포섭.
- **개발 트랙 고유 주의**: 98행 중 `AIR-EV-001..005`(ADR-DEV-005 — 독립 리뷰 자체를 검증하는 계열)와
  `BFA-EV-001..007`은 **리뷰 독립성을 대상으로 하는 evidence**다. 이들의 independent_reviewer가
  `ai-review(decorrelated)+…`인 이상, 해당 건 리뷰의 decorrelation 입증은 **자기참조 위험이 가장 큰
  지점**이므로 실행 시 우선적으로 다른 모델 계열을 배정한다.

---

## 7. 검증 증거

편집 전후 전수 검증. **naive grep/sed 계수 금지** — 모든 계수·비교는 Python `csv` 모듈 파싱 기준이며,
바이트 레이아웃 보존은 행-단위 문자열 치환(재직렬화 없음)으로 확보했다.

**편집 방식**: 대상 행의 행-말 리터럴 `,NOT_IMPLEMENTED,TBD,TBD,TBD,TBD,N/A,,,,` (행당 정확히 1회, 행 끝
앵커)를 오너 3열만 치환한 문자열로 교체. 신규 값에 콤마·따옴표가 없어 인용 규칙 변경이 발생하지 않는다.

**바이트 레이아웃**: BOM `True`→`True`, CRLF `0`→`0`, LF `119`→`119`, 후행 개행 `True`→`True`,
큰따옴표 개수 `0`→`0`. (22,597 → 29,555 bytes; 증가분은 기입 문자열 길이)

```text
[PASS] (a) row count 118 invariant — 118 -> 118
[PASS] (b) evidence_id sequence invariant
[PASS] (b') evidence_id uniqueness (118 unique)
[PASS] (c) status all NOT_IMPLEMENTED
[PASS] (c') header byte-identical
[PASS] (d) exactly 98 rows changed — changed=98
[PASS] (d') changed columns are exactly the 3 owner columns
[PASS] (d'') all changed rows carry exactly the D1 triple
[PASS] (e-parsed) 20 ECO/IOM rows field-identical — n=20
[PASS] (e-bytes) every non-target line byte-identical — n=22 (header + 20 ECO/IOM + 후행 빈 줄)
[PASS] (e') no distinguished TBD-* value was altered
[PASS] (f) plain 'TBD' remains only in verification_profile_version (98); 오너 3열에 잔존 'TBD' 0
OVERALL: PASS
```

**열 census (csv 모듈, 118행)**

| 열 | 편집 전 | 편집 후 |
|---|---|---|
| `implementation_owner` | TBD 98 / TBD-economic…12 / TBD-investment-operating…8 | **ai-impl(claude-orchestrated) 98** / (동일 20) |
| `evidence_owner` | TBD 98 / TBD-investment-evidence-owner 12 / …operating…8 | **operator 98** / (동일 20) |
| `independent_reviewer` | TBD 98 / TBD-independent-investment-reviewer 12 / …operating…8 | **ai-review(decorrelated)+operator-countersign 98** / (동일 20) |
| `status` | NOT_IMPLEMENTED 118 | NOT_IMPLEMENTED 118 (불변) |
| `verification_profile_version` | TBD 98 / ECO-0.1-PROPOSED 12 / IOM-0.1-PROPOSED 8 | 동일 (불변) |
| `broker_capability_profile_version` | N/A 109 / TBD-approved-broker-capability-profile 9 | 동일 (불변) |
| `evidence_location` | `''` 118 | 동일 (불변) |

### 7-1. MD 미러 검증 (`EVIDENCE-REGISTER-DEV.md`)

동일 규율 적용: 표 행 앵커(`| NOT_IMPLEMENTED | TBD | TBD |` 행-말 리터럴, 행당 1회) 기반 행-단위 치환,
재렌더링 없음. 대상 98행은 전부 레지스터 표 범위(`:54–171`) 안임을 사전 확인했다.

**바이트 레이아웃**: BOM 없음(불변), CRLF `0`→`0`, LF `199`→`199`, 후행 개행 `True`→`True`.
(23,404 → 29,872 bytes)

```text
[PASS] (M1) table row count 118 invariant — 118 -> 118
[PASS] (M2) header + separator byte-identical
[PASS] (M3) exactly 98 lines changed
[PASS] (M4) every non-target line byte-identical — n=102
[PASS] (M5) all changed rows: only Owner/Reviewer cells differ
[PASS] (M6) ECO/IOM 20 MD rows byte-identical — n=20
[PASS] (M7) byte layout preserved (no BOM, LF-only, trailing LF)
```

### 7-2. CSV ↔ MD 전수 대조

미러 8열 × 118행 전수 비교(§2-1 매핑 기준). **자기신고가 아니라 두 파일을 독립 파싱해 셀 단위로 대조**한다.

```text
[PASS] (X1) row counts equal — csv=118 md=118
[PASS] (X2) evidence_id sequence identical
[PASS] (X3) all 8 mirrored columns agree on all 118 rows — mismatches=0
[PASS] (X4) owner/reviewer agree 118/118
[PASS] (X5) evidence_owner is CSV-only (no MD column)
OVERALL: PASS
```

`mismatches=0`은 **오너 2열뿐 아니라 `ID`/`Domain`/`Test`/`ADR`/`Minimum level`/`Status` 6열도 전 118행에서
일치**함을 뜻한다 — 미러 재동기화가 오너 열에 국한됐고 다른 열에 표류가 없음을 양방향으로 확인한 것이다.

### 7-3. 리포 검사기 (`tools/tos_spec_status.py`)

편집 후 실행. **저작 세션이 만들지 않은 독립 검사기**이며, §3(가)·§4(나)의 강제 조항을 실제로 통과한다.

```text
$ .venv/bin/python tools/tos_spec_status.py
TOS spec status PASS: documents=13, ADRs=45, Part1=372, DEV=118, direct_traceability=29/30,
source_gap_adrs=1, p2_carried=28, CONST-003=INCONCLUSIVE, migration_rows=54, broker_sites=9,
count_transcriptions=11, restricted_live=NOT_AUTHORIZED, production=NOT_AUTHORIZED
```

핵심: `DEV=118`(행수 불변) · `restricted_live=NOT_AUTHORIZED` · `production=NOT_AUTHORIZED`(§5 "어떤 권한도
만들지 않는다"의 기계 확증) · Part-1 `372` 불변.

> **실행 환경 주석(정직 기록)**: 시스템 `python3`로는 `ModuleNotFoundError: No module named 'yaml'`로
> 즉시 종료된다. 이는 인터프리터 선택 문제이지 검사 실패가 아니며, 프로젝트 venv(`.venv/bin/python`)로
> 실행해야 한다. **Part-1 CSV를 동시 편집 중인 다른 레인으로 인한 transient 실패(mid-edit 창 — 기지 결함
> 클래스)는 이번 실행에서 관측되지 않았다**(첫 venv 실행에서 곧바로 PASS·재시도 불요). 위 두 실패 양태는
> 서로 구분해 기록한다.

**`git diff --stat` / `git status --porcelain` (동시 레인 변경 배제를 위한 경로-스코프 출력)**

워킹트리에는 본 작업과 무관한 다른 레인의 동시 변경이 존재하므로, 아래는 **본 작업 경로로 스코프한 실제 도구
출력 verbatim**이다(합성 아님).

```text
$ git diff --stat -- tos-spec/src/part-3-development/verification/ docs/plans/INDEX.md
 docs/plans/INDEX.md                                |   1 +
 .../verification/EVIDENCE-REGISTER-DEV.csv         | 196 ++++++++++-----------
 .../verification/EVIDENCE-REGISTER-DEV.md          | 196 ++++++++++-----------
 3 files changed, 197 insertions(+), 196 deletions(-)

$ git status --porcelain -- tos-spec/src/part-3-development/verification/ docs/plans/INDEX.md \
    docs/plans/2026-08-06-tos-phase0-p03-dev-owner-assignment.md
 M docs/plans/INDEX.md
 M tos-spec/src/part-3-development/verification/EVIDENCE-REGISTER-DEV.csv
 M tos-spec/src/part-3-development/verification/EVIDENCE-REGISTER-DEV.md
?? docs/plans/2026-08-06-tos-phase0-p03-dev-owner-assignment.md
```

두 레지스터 파일 모두 삽입/삭제가 정확히 98/98로 대칭이며, INDEX는 `1 insertion(+)`뿐이다(기존 행 무변경).
합계 `197 insertions / 196 deletions`의 차 1은 INDEX 신규 1행이다. 본 작업 산출물은 위 4개 경로가 전부다.

---

## 8. 관측 이상 및 후속

**처리 완료 (오케스트레이터 판정 2026-08-06)**

1. **MD 미러 갱신 — Part-1 선례 채택.** 최초 편집은 CSV만 대상이었고 MD 표 98행이 `| TBD | TBD |`로 남아
   있었다. CSV가 정본이라는 명문 규정이 있어 정합성 붕괴는 아니었으나, **Part-1 선례 `f85434c3`이 CSV와 MD를
   같은 커밋에서 갱신**한 점을 따라 미러를 재동기화했다(§2-1 매핑, §7-1/§7-2 검증).
2. **`docs/plans/INDEX.md` 등재 완료.** `## Active` 표 최상단에 주변 행과 동일 형식(2셀 `| [링크](파일) |
   **제목 — 요약** |`)으로 1행 추가. 기존 행 무변경(diff `1 insertion(+)`). `Current update:`/`Last updated:`
   머리말은 갱신하지 않았다 — 선행 2026-08-06 등재 2건도 갱신하지 않은 기존 관행을 따랐다.

**잔존 (비차단, 이 기록의 범위 밖)**

3. **gate-status §7 step 2 문언 vs 실제** — step 2는 "all 118 items"를 요구하나 이 편집은 98행만 닫는다.
   step 2 종결 주장 시 20행 잔여를 반드시 병기해야 한다(§5). **문서 §5/§8 기록으로 충분**하다는 판정에 따라
   별도 조치 없음.
4. **DEV 레지스터에 "Mirror column mapping" 문단 부재** — Part-1 `EVIDENCE-REGISTER-002.md:27`에는 있고 DEV
   레지스터에는 없다(§2-1). **관측만 기록하며 신설하지 않는다** — 레지스터 본문 규약 신설은 별개 판단이다.
