# 작업 메모 — tos-spec 잔여 ADR의 EV-L1 표면 실측 및 사이클 규모 판정 (2026-07-26)

> **문서 성격 (규범성 선언)**: 본 문서는 **비규범 작업 메모**다. **비준(ratification) 대상이 아니며**,
> GOV-001의 세 거버넌스 행위(비준 / ADR acceptance / live authorization) 중 어느 것도 수행하지 않는다.
> ADR·RFC·VER·register의 어떤 상태도 변경하지 않고, 어떤 EV 항목도 `NOT_IMPLEMENTED`에서 이동시키지
> 않는다. 본 문서의 유일한 산출은 **후속 설계 사이클의 규모 산정을 위한 1차 소스 실측 기록**이다.
> 여기에 기록된 판정은 **사이클 착수 순서·규모의 권고**일 뿐, 설계 비준·구현 승인이 아니다.

- **대상**: ADR-002-009 (Failure Domain Isolation), 거버넌스 ADR-002-025 / -026 / -027 / -028 / -029 / -030
- **방법**: EVIDENCE-REGISTER-002 전수 파싱(머신 파싱, grep head 절단 없음) + ADR 원문 전수 정규식 열거
- **git 커밋 없음 / 읽기 전용 조사**(본 메모 파일 생성 외 어떤 파일도 수정하지 않음)

---

## 0. 요약 판정 (한 줄씩)

| ADR | family | EV 행 수 | **EV-L1 슬라이스 보유 행 수** | 판정 |
|---|---|---|---|---|
| ADR-002-009 Failure Domain Isolation | `FD-EV` | 12 | **0** | **0건 완결 predicate-only 사이클** (선례: TIME-EV 0건). 단 12행 중 6행이 `+Security` — 아래 §5.1 단서 참조 |
| ADR-002-025 Restricted-Live / Promotion Governance | `RLP-EV` | 12 | **4** (001·005·006·012) | **full 사이클 필요 (L1×4)** |
| ADR-002-026 Safety Waiver / Deviation / Residual Risk | `WDR-EV` | 12 | **5** (001·002·007·010·012) | **full 사이클 필요 (L1×5)** — 거버넌스 6건 중 최대 tie |
| ADR-002-027 Safety Incident / Controlled Shutdown | `SIR-EV` | 12 | **3** (001·002·009) | **full 사이클 필요 (L1×3)** |
| ADR-002-028 Safety Telemetry / Continuous Monitoring | `STM-EV` | 12 | **2** (001·005) | **full 사이클 필요 (L1×2)** — 거버넌스 6건 중 최소 |
| ADR-002-029 Software Supply-Chain / Artifact Admission | `SCI-EV` | 12 | **4** (001·002·003·006) | **full 사이클 필요 (L1×4)** |
| ADR-002-030 Post-Trade Obligations / Settlement Finality | `PTF-EV` | 12 | **5** (001·002·004·006·008) | **full 사이클 필요 (L1×5)** — 거버넌스 6건 중 최대 tie; **12행 전부 `+Broker`** (§5.7 단서) |

**핵심 정정**: 거버넌스 6건은 "EV-L1 표면 per-ADR 판정 미실시" 상태였는데, 실측 결과 **6건 전부 L1 슬라이스를
보유**한다(L1 합계 = 4+5+3+2+4+5 = **23행**). 즉 **"거버넌스 = predicate-only" 가정은 실측으로 기각**된다.
`+Security` / `+Broker` 좌표 태그가 지배적이지만, 그 태그들은 **EV-Ln을 대체하거나 낮추지 않는다**(§2 근거).

---

## 1. Verification register 위치 실측

`EV-L1` / `EV-L2` / `EV-L3` 표기와 EV id 패턴을 tos-spec 전역 grep한 결과, **Part-1의 정규 register는 다음
두 파일의 쌍**이다(동일 내용, CSV가 머신 편집 소스):

| 역할 | 절대 경로 | 크기 |
|---|---|---|
| **머신 편집 소스 (정본)** | `/Users/harris/Development/private/kis_unified_sts/tos-spec/src/part-1-foundation/verification/EVIDENCE-REGISTER-002.csv` | 373행 (헤더 1 + **데이터 372행**) |
| 사람 판독용 미러 | `/Users/harris/Development/private/kis_unified_sts/tos-spec/src/part-1-foundation/verification/EVIDENCE-REGISTER-002.md` | 401행 |

> `EVIDENCE-REGISTER-002.md` line 7 (verbatim): "This register tracks execution evidence. The initial state is
> intentionally `NOT_IMPLEMENTED`; document creation is not test completion. **The CSV version is the
> machine-editable source.**"

**부수 위치(대상 아님, 참고)**:

- 레벨 정의 규범: `.../part-1-foundation/VER-002-001-Safety-Critical-Architecture-Verification-Evidence-Specification.md`
  (line 142 `### EV-L1 — Model and Property Verification`, line 146 L2, 150 L3, 154 L4, 158 L5, 162 L6)
- Phase 배정: `.../part-1-foundation/verification/IMPLEMENTATION-PLAN-002.md` (line 165 `### Phase 1 — Model & property verification (EV-L1)`)
- 프로파일/바운드: `.../part-1-foundation/verification/VERIFICATION-PROFILE-002.yaml`
- 게이트 상태: `.../part-1-foundation/ARCHITECTURE-GATE-STATUS.md`
- **Part-3 개발 트랙 별도 register**(본 조사 범위 밖): `.../part-3-development/verification/EVIDENCE-REGISTER-DEV.csv` (98 items, gate-status line 982)
- `tos-spec/book/**` 하위 동명 파일은 mdBook 빌드 산출물이며 소스가 아니다. 실측은 전부 `src/` 기준.

**register 전역 status 실측** (`EVIDENCE-REGISTER-002.md` line 12–16):
`Total evidence items: 372` / `NOT_IMPLEMENTED: 372` / `PASS: 0` / `FAIL: 0` / `INCONCLUSIVE: 0`.
→ **대상 7개 ADR의 84개 EV 행은 예외 없이 전부 `NOT_IMPLEMENTED`이며, `PASS`가 0건이다.**

### 1.1 ADR → EV family 전수 매핑 (372행 머신 집계)

| primary_adr | family | 행 수 | | primary_adr | family | 행 수 |
|---|---|---:|---|---|---|---:|
| ADR-002-001 | `PRD` | 2 | | ADR-002-016 | `ERI` | 12 |
| ADR-002-002 | `RC` | 18 | | ADR-002-017 | `SBR` | 12 |
| ADR-002-002/003/004 | `X` | 12 | | ADR-002-018 | `CII` | 12 |
| ADR-002-003 | `SA` | 15 | | ADR-002-019 | `VTG` | 12 |
| ADR-002-004 | `BC` | 22 | | ADR-002-020 | `IOC` | 12 |
| ADR-002-005 | `STATE` | 5 | | ADR-002-021 | `ARE` | 12 |
| ADR-002-006 | `RECON` | 5 | | ADR-002-022 | `AFG` | 12 |
| ADR-002-007 | `REARM` | 12 | | ADR-002-023 | `IAP` | 12 |
| ADR-002-008 | `TIME` | 10 | | **ADR-002-024** | `CUR` | 12 |
| **ADR-002-009** | **`FD`** | **12** | | **ADR-002-025** | **`RLP`** | **12** |
| ADR-002-010 | `NT` | 12 | | **ADR-002-026** | **`WDR`** | **12** |
| ADR-002-011 | `PR` | 12 | | **ADR-002-027** | **`SIR`** | **12** |
| ADR-002-012 | `RCLP` | 12 | | **ADR-002-028** | **`STM`** | **12** |
| ADR-002-013 | `EGRESS` | 13 | | **ADR-002-029** | **`SCI`** | **12** |
| ADR-002-014 | `SPG` | 12 | | **ADR-002-030** | **`PTF`** | **12** |
| ADR-002-015 | `HAG` | 18 | | | **합계** | **372** |

---

## 2. 판정 규칙 — "EV-L1 슬라이스 보유"의 규범 근거

VER-002-001 line 170 (verbatim):

> "`EV-Ln+X` requires the named EV-Ln evidence **and** the supplementary evidence or assessment `X`;
> **`+X` never replaces or lowers EV-Ln.** `+Broker` requires applicable Broker Capability Profile evidence
> at the broker level required by that profile and approval gate. `+Security` requires an independent
> security-boundary assessment covering identity, credential, authorization, fencing, and bypass paths."

VER-002-001 line 172 (verbatim):

> "Short forms such as `EV-L2/3` mean `EV-L2/EV-L3`. Combined forms such as `EV-L1/3+Broker` apply both
> rules: **staged EV-L1/EV-L3 evidence** plus the required broker evidence. Multiple suffixes are cumulative:
> `EV-L3/5+Broker+Security` requires the staged EV-L3/EV-L5 evidence, applicable broker evidence, and the
> independent security-boundary assessment."

⇒ **적용 규칙(본 메모 전역)**:

1. **L1 슬라이스 보유** = `minimum_evidence_level` 필드의 `+` **앞** 기본부(`EV-L…`)의 슬래시 집합에 `1`이 포함.
   예: `EV-L1/3`, `EV-L1/2`, `EV-L1/3+Security`, `EV-L1/2/3+Broker+Security` = **보유**.
   예: `EV-L2/3`, `EV-L3+Security`, `EV-L3/5` = **부재**.
2. **`+Security` / `+Broker`는 L1 카운트에서 행을 제외하지 않는다** (line 170 "never replaces or lowers").
3. **L1 슬라이스 보유 ≠ EV closure**. `EV-L1/3`은 *staged* L1 **및** L3을 모두 요구하므로, Phase 1의 L1 모델·
   property test는 해당 행을 **닫지 못한다**. 후속 설계 문서는 선례대로 **"EV-L1-complete 주장 금지"** 규율
   태그를 유지해야 한다.
4. **절단 방지**: 모든 카운트는 CSV/ADR **전수 파싱**(Python `csv` + 전 파일 정규식)으로 산출했다.
   `grep | head` 류의 절단 위험 명령은 카운트 산출에 사용하지 않았다(선례 오류 #12 회피).

### 2.1 선례 캘리브레이션 — 본 규칙이 완결 사이클을 재현하는지 검증

동일 규칙을 이미 완결된 세 사이클에 역적용해 재현성을 확인했다:

| 사이클 | family | 본 규칙 산출 | 해당 설계 문서의 기록값 | 일치 |
|---|---|---:|---|---|
| #13 Aggregate Risk Projection | `ARE` | **5** (001·002·003·004·006) | `docs/plans/2026-07-25-tos-aggregate-risk-projection-design.md` line 339–340: "**`EV-L1` 슬라이스 보유(5행)** = 001(`EV-L1/3` line 276)·002(`EV-L1/3+Security` 277)·003(`EV-L1/3+Broker` 278)·004(`EV-L1/3` 279)·006(`EV-L1/3+Broker` 281)" | ✅ |
| #12 Safety Profile Governance | `SPG` | **8** (001–006·008·012) | `docs/plans/2026-07-25-tos-safety-profile-governance-design.md` line 453–454: "**EV-L1 슬라이스 보유(8행)** = 001(`EV-L1/3+Security` line 186)·002(`EV-L1/2` 187)·003(`EV-L1/2+Security` 188)·004(`EV-L1/3` 189)·005(`EV-L1/3` 190)·006(`EV-L1/3` 191)·008(`EV-L1/3` 193)·012(`EV-L1/3` 197)" | ✅ |
| Trustworthy Time (0건 선례) | `TIME` | **0** | `docs/plans/2026-07-21-tos-trustworthy-time-design.md` line 105–106: "**어떤 TIME-EV 항목도 완결하지 않는다** … register 최소 레벨이 **전부 EV-L2 이상**이므로(EVIDENCE-REGISTER-002.csv line 69–78) Phase 1은 **TIME-EV 0건**을 닫는다." | ✅ |

⇒ 규칙은 **`+Security`/`+Broker` 태그 행을 L1 카운트에 포함**하는 선례 관행과 정확히 일치한다
(ARE-EV-002 = `EV-L1/3+Security`, ARE-EV-003/006 = `EV-L1/3+Broker`가 5행에 포함되어 있음). 본 메모의
거버넌스 판정은 이와 **동일한 기준**을 쓴다.

---

## 3. ADR-002-009 Failure Domain Isolation — `FD-EV` 실측표

**원문**: `tos-spec/src/part-1-foundation/ADR-002-009-Failure-Domain-Isolation-and-Deployment-Safety.md` (513행)
**register 구간**: `EVIDENCE-REGISTER-002.md` line **125–136** / `.csv` line **101–112** (12행, 결번 없음)

| EV id | register 제목 | **최소 레벨 (verbatim)** | L1 슬라이스 | 분류 | md line | csv line |
|---|---|---|:---:|---|---:|---:|
| `FD-EV-001` | Strategy-to-Safety Isolation | `EV-L3+Security` | ✗ | not-Phase-1 (+Security) | 125 | 101 |
| `FD-EV-002` | Stale Deployment and Duplicate Active Generation | `EV-L3+Security` | ✗ | not-Phase-1 (+Security) | 126 | 102 |
| `FD-EV-003` | Control-Plane-to-Egress Partition | `EV-L3+Security` | ✗ | not-Phase-1 (+Security) | 127 | 103 |
| `FD-EV-004` | Cache Failure Cannot Create Permission | `EV-L3` | ✗ | predicate-only (≥L3) | 128 | 104 |
| `FD-EV-005` | Restrictive Event Distribution Failure | `EV-L3` | ✗ | predicate-only (≥L3) | 129 | 105 |
| `FD-EV-006` | Live and Non-Live Environment Isolation | `EV-L3+Security` | ✗ | not-Phase-1 (+Security) | 130 | 106 |
| `FD-EV-007` | Risk Capacity Ledger Failover Fence | `EV-L3+Security` | ✗ | not-Phase-1 (+Security) | 131 | 107 |
| `FD-EV-008` | Shared Time Common Mode | `EV-L3` | ✗ | predicate-only (≥L3) | 132 | 108 |
| `FD-EV-009` | Partial Deployment and Configuration Rollback | `EV-L3+Security` | ✗ | not-Phase-1 (+Security) | 133 | 109 |
| `FD-EV-010` | Shared Broker Resource Exhaustion | `EV-L3/5` | ✗ | not-Phase-1 (L5 = Restricted Production) | 134 | 110 |
| `FD-EV-011` | Safety-Cell Blast-Radius Containment | `EV-L3` | ✗ | predicate-only (≥L3) | 135 | 111 |
| `FD-EV-012` | Region and Datastore Recovery | `EV-L3` | ✗ | predicate-only (≥L3) | 136 | 112 |

**레벨 히스토그램**: `EV-L3+Security` ×6 / `EV-L3` ×5 / `EV-L3/5` ×1 · **L1 슬라이스 보유 = 0행**
**최소 레벨의 하한**: 12행 전부 **EV-L3 이상**. (TIME은 하한이 L2였고 FD는 L3 — FD가 **더 강한 0건**이다.)
**status**: 12행 전부 `NOT_IMPLEMENTED` / **criticality**: 12행 전부 `Critical`

### 3.1 자체 INV/AC 시리즈 실측

- **`FD-AC-001` … `FD-AC-012`** — 12건, 결번 없음. §17 Acceptance Cases (line 392–409, 표 형식).
  §17 preamble line 394 (verbatim): "The following cases are mandatory and **map one-to-one to `FD-EV-001`
  through `FD-EV-012`**. Registration is not execution; every item remains incomplete until its required
  evidence is executed, retained, and independently reviewed:"
- **`FD-INV-###` 시리즈는 존재하지 않는다.** ADR-002-009은 §6 "Mandatory Isolation Invariants"(line 136–176)를
  **번호 없는 산문 소절 6.1–6.7**로 기술한다. 이는 -025..-030 (INV 15–18건 번호 부여)과 **구조가 다르다**.
  ⇒ 후속 설계 시 **`FD-INV-###` 인용 금지**(phantom id 위험). §6.1–§6.7 소절 번호로 인용해야 한다.

### 3.2 Phase 1 배정 실측 (register 0건과 별개로 모델 산출물은 존재)

`IMPLEMENTATION-PLAN-002.md` line 224 (verbatim):

> "- Implement pure models for the five orthogonal state dimensions and CPL invariants, per-field
>   evidence confidence, **Failure-Domain Allocation Matrix**, protection gap/overlap, and conservative
>   non-trade transition envelope (ADR-002-005/006/**009**/011/010)."

`IMPLEMENTATION-PLAN-002.md` line 231 (verbatim):

> "- Deliverable: EV-L1 evidence for every RC/SA/TIME/REARM/STATE/RECON/**FD**/PR/NT/RCLP/EGRESS/SPG/HAG/
>   ERI/SBR/CII/VTG/IOC/ARE/AFG/IAP/CUR/RLP/WDR/SIR/STM/SCI/PTF item **marked EV-L1-reachable**."

`ARCHITECTURE-GATE-STATUS.md` §7 Immediate Engineering Sequence line 985 (verbatim):

> "5. Implement orthogonal state, reconciliation-confidence, **failure-domain**, replacement, and non-trade
>    transition models."

⇒ FD는 **Phase 1 모델 산출물("Failure-Domain Allocation Matrix" 순수 모델)을 배정받았으나**, line 231의
한정어 "**marked EV-L1-reachable**"에 해당하는 `FD-EV` 행이 **0건**이므로 **어떤 FD-EV도 닫지 않는다**.
이는 TIME 선례와 **완전히 동형**이다.

### 3.3 판정

> **ADR-002-009 = "0건 완결 predicate-only 사이클"** (L1×0).
> 근거: `EVIDENCE-REGISTER-002.csv` line 101–112 / `.md` line 125–136 — 12행 최소 레벨이 전부 EV-L3 이상.
> 선례 TIME-EV 0건(`docs/plans/2026-07-21-tos-trustworthy-time-design.md` line 105–106)과 동형이되,
> **하한이 L2가 아니라 L3**이므로 TIME보다도 L1 거리가 멀다.

**단서 (사이클 규모 산정 시 반드시 반영)**:

1. **`+Security` 6/12 지배**. `+Security`는 "independent security-boundary assessment covering identity,
   credential, authorization, fencing, and bypass paths"(VER-002-001 line 170)를 요구하는 **조직적 게이트**로,
   코드 사이클로 진전시킬 수 없다. 나머지 6행도 EV-L3(integrated system fault test) 또는 EV-L3/5(restricted
   production)로, **전부 Phase 2/3 이후 좌표**다.
2. FD의 Phase-1 산출물은 **`FD-EV`를 닫는 것이 아니라 다른 family의 substrate**로 소비된다. 실측 근거:
   `docs/plans/2026-07-25-tos-degraded-mode-protective-capacity-design.md` line 411–412·417 —
   `FD-EV-001`(protective classification), `FD-EV-010`(exhaustion), `FD-EV-008`(common-mode broker)이
   **PRD 사이클에서 이미 "닫지 않는 substrate"로 인용**되어 있다. 즉 **FD 좌표의 일부는 이미 배포된
   `tos/src/tos/protective/`가 간접 커버**한다.
3. ⇒ **권고: 저비용 predicate-only 사이클로 처리하거나, 잔여 non-governance 사이클 뒤로 이연.**
   full 설계 사이클(#12/#13급)을 배정할 register 근거는 **없다**.

---

## 4. 거버넌스 ADR-002-025 … -030 — 실측표

### 4.1 ADR-002-025 Restricted-Live Verification / Progressive Scope Promotion / Production Authorization

**원문**: `ADR-002-025-Restricted-Live-Verification-Progressive-Scope-Promotion-and-Production-Authorization-Governance.md` (761행)
**register 구간**: `.md` line **324–335** / `.csv` line **293–304**

| EV id | 제목 | **최소 레벨 (verbatim)** | L1 | 분류 | md/csv line |
|---|---|---|:---:|---|---:|
| `RLP-EV-001` | Exact Pre-Registered Scope | `EV-L1/3` | **✔** | **core (L1 슬라이스)** | 324 / 293 |
| `RLP-EV-002` | Worst-Credible Effect and RCL Separation | `EV-L2/3+Broker` | ✗ | not-Phase-1 (+Broker) | 325 / 294 |
| `RLP-EV-003` | No Trial Safety Bypass | `EV-L2/3+Broker` | ✗ | not-Phase-1 (+Broker) | 326 / 295 |
| `RLP-EV-004` | Abort Dominance and Race | `EV-L3+Security` | ✗ | not-Phase-1 (+Security, 하한 L3) | 327 / 296 |
| `RLP-EV-005` | Evidence Completeness and Negative-Result Retention | `EV-L1/3` | **✔** | **core (L1 슬라이스)** | 328 / 297 |
| `RLP-EV-006` | Coverage and Non-Extrapolation | `EV-L1/3` | **✔** | **core (L1 슬라이스)** | 329 / 298 |
| `RLP-EV-007` | Progressive Single-Use Promotion | `EV-L2/3+Security` | ✗ | not-Phase-1 (+Security) | 330 / 299 |
| `RLP-EV-008` | Independent Governance and Authority Separation | `EV-L2/3+Security` | ✗ | not-Phase-1 (+Security) | 331 / 300 |
| `RLP-EV-009` | Expiry and Economic Continuity | `EV-L2/3+Broker` | ✗ | not-Phase-1 (+Broker) | 332 / 301 |
| `RLP-EV-010` | Restart, Recovery, and Non-Revival | `EV-L2/3+Security` | ✗ | not-Phase-1 (+Security) | 333 / 302 |
| `RLP-EV-011` | Continuous Conformance and Demotion | `EV-L2/3+Broker` | ✗ | not-Phase-1 (+Broker) | 334 / 303 |
| `RLP-EV-012` | Gate Honesty and Status Separation | `EV-L1/3` | **✔** | **core (L1 슬라이스)** | 335 / 304 |

**히스토그램**: `EV-L1/3` ×4 · `EV-L2/3+Broker` ×4 · `EV-L2/3+Security` ×3 · `EV-L3+Security` ×1
**L1 슬라이스 = 4행 (001·005·006·012)** — 모두 **좌표 태그 없는 순수 `EV-L1/3`** (거버넌스 6건 중 유일)
**자체 시리즈**: `RLP-INV-001..015` (15건, 결번 없음, §6 Safety Invariants line 146–) / `RLP-AC-001..012` (12건, §26 line 630–)
**1:1 근거** (line 632 verbatim): "The following cases are mandatory and **map one-to-one to `RLP-EV-001`
through `RLP-EV-012`**. Written cases are not completed evidence."
**AC↔EV 제목 대조**: 12/12 **문자열 완전 일치**(머신 대조, 불일치 0)

> **판정: full 사이클 필요 (L1×4).** L1 4행이 전부 순수 `EV-L1/3`(추가 좌표 게이트 없음)이라 **거버넌스
> 6건 중 L1 접근성이 가장 깨끗**하다. 주제는 trial plan/run scope 정합, evidence completeness·negative-result
> retention, coverage non-extrapolation, gate honesty — **전부 순수·비전송 모델로 표현 가능**한 성격이다.

### 4.2 ADR-002-026 Safety Waiver / Deviation / Residual Risk Governance

**원문**: `ADR-002-026-Safety-Waiver-Deviation-and-Residual-Risk-Governance.md` (774행)
**register 구간**: `.md` line **336–347** / `.csv` line **305–316**

| EV id | 제목 | **최소 레벨 (verbatim)** | L1 | 분류 | md/csv line |
|---|---|---|:---:|---|---:|
| `WDR-EV-001` | Non-Waivable Boundary | `EV-L1/3+Security` | **✔** | **core (L1) +Security 잔여** | 336 / 305 |
| `WDR-EV-002` | Exact Scope and Dependency Closure | `EV-L1/3` | **✔** | **core (L1 슬라이스)** | 337 / 306 |
| `WDR-EV-003` | Compensating-Control Effectiveness | `EV-L2/3+Security` | ✗ | not-Phase-1 (+Security) | 338 / 307 |
| `WDR-EV-004` | Independent Effective-Person Approval | `EV-L2/3+Security` | ✗ | not-Phase-1 (+Security) | 339 / 308 |
| `WDR-EV-005` | Non-Authorizing Single-Use Activation | `EV-L2/3+Security` | ✗ | not-Phase-1 (+Security) | 340 / 309 |
| `WDR-EV-006` | Currentness, Revocation, and Send Race | `EV-L3+Security` | ✗ | not-Phase-1 (+Security, 하한 L3) | 341 / 310 |
| `WDR-EV-007` | UNKNOWN, Capacity, and Protective Confinement | `EV-L1/3+Broker` | **✔** | **core (L1) +Broker 잔여** | 342 / 311 |
| `WDR-EV-008` | Broker Finality and Economic Continuity | `EV-L2/3+Broker` | ✗ | not-Phase-1 (+Broker) | 343 / 312 |
| `WDR-EV-009` | Expiry, Renewal, Recovery, and Non-Revival | `EV-L2/3+Security` | ✗ | not-Phase-1 (+Security) | 344 / 313 |
| `WDR-EV-010` | Evidence and Status Honesty | `EV-L1/3` | **✔** | **core (L1 슬라이스)** | 345 / 314 |
| `WDR-EV-011` | Security, Alternate Route, and Emergency Behavior | `EV-L2/3+Broker+Security` | ✗ | not-Phase-1 (+Broker+Security) | 346 / 315 |
| `WDR-EV-012` | Combined Deviations and Gate Separation | `EV-L1/3+Security` | **✔** | **core (L1) +Security 잔여** | 347 / 316 |

**히스토그램**: `EV-L2/3+Security` ×4 · `EV-L1/3+Security` ×2 · `EV-L1/3` ×2 · `EV-L1/3+Broker` ×1 ·
`EV-L2/3+Broker` ×1 · `EV-L2/3+Broker+Security` ×1 · `EV-L3+Security` ×1
**L1 슬라이스 = 5행 (001·002·007·010·012)** — 순수 2행 + `+Security` 2행 + `+Broker` 1행
**자체 시리즈**: `WDR-INV-001..015` (15건) / `WDR-AC-001..012` (12건, §25 line 637–)
**1:1 근거** (line 639 verbatim): "…**map one-to-one to `WDR-EV-001` through `WDR-EV-012`**. Written cases are
not completed evidence." · **AC↔EV 제목 대조 12/12 완전 일치**
**독립 리뷰 실측** (`ARCHITECTURE-GATE-STATUS.md` line 793 verbatim 발췌): "The independent ADR-002-026
document, adversarial-sequence, integration, and traceability review **passed cleanly at EV-L0 with zero
Critical, Major, or Minor findings.** WDR acceptance/evidence titles are exact 1:1 (WDR-AC-001..012 ↔
WDR-EV-001..012)…"

> **판정: full 사이클 필요 (L1×5).** 거버넌스 6건 중 **PTF와 공동 최대**. L1 5행의 주제(Non-Waivable
> Boundary 불변, exact scope + dependency closure, UNKNOWN/capacity/protective confinement, evidence·status
> honesty, combined deviation 합성)는 **순수 술어·모델 표현에 매우 적합**하다. 특히 001 Non-Waivable Boundary는
> **"hard and non-erodable"**(gate-status line 793) 성격이라 property test 대상으로 강한 선례를 가진다.

### 4.3 ADR-002-027 Safety Incident Declaration / Containment / Controlled Shutdown / Closure

**원문**: `ADR-002-027-Safety-Incident-Declaration-Containment-Controlled-Shutdown-and-Closure-Governance.md` (772행)
**register 구간**: `.md` line **348–359** / `.csv` line **317–328**

| EV id | 제목 | **최소 레벨 (verbatim)** | L1 | 분류 | md/csv line |
|---|---|---|:---:|---|---:|
| `SIR-EV-001` | Restrictive Detection and Declaration | `EV-L1/3+Security` | **✔** | **core (L1) +Security 잔여** | 348 / 317 |
| `SIR-EV-002` | Exact Scope and Combined Incidents | `EV-L1/3` | **✔** | **core (L1 슬라이스)** | 349 / 318 |
| `SIR-EV-003` | Containment Authority Separation | `EV-L2/3+Security` | ✗ | not-Phase-1 (+Security) | 350 / 319 |
| `SIR-EV-004` | Controlled Shutdown and Hard Fencing | `EV-L3+Broker+Security` | ✗ | not-Phase-1 (하한 L3, +Broker+Security) | 351 / 320 |
| `SIR-EV-005` | Protection and Ongoing Obligations | `EV-L2/3+Broker` | ✗ | not-Phase-1 (+Broker) | 352 / 321 |
| `SIR-EV-006` | UNKNOWN, Broker Finality, and Capacity | `EV-L2/3+Broker` | ✗ | not-Phase-1 (+Broker) | 353 / 322 |
| `SIR-EV-007` | Incident Currentness and Send Race | `EV-L3+Security` | ✗ | not-Phase-1 (하한 L3, +Security) | 354 / 323 |
| `SIR-EV-008` | Partition, Common Mode, and Compromise | `EV-L3+Security` | ✗ | not-Phase-1 (하한 L3, +Security) | 355 / 324 |
| `SIR-EV-009` | Evidence, Communication, and Status Honesty | `EV-L1/3` | **✔** | **core (L1 슬라이스)** | 356 / 325 |
| `SIR-EV-010` | Independent Non-Permissive Closure | `EV-L2/3+Security` | ✗ | not-Phase-1 (+Security) | 357 / 326 |
| `SIR-EV-011` | External Activity and Demotion | `EV-L2/3+Broker+Security` | ✗ | not-Phase-1 (+Broker+Security) | 358 / 327 |
| `SIR-EV-012` | Recovery and Non-Revival | `EV-L2/3+Security` | ✗ | not-Phase-1 (+Security) | 359 / 328 |

**히스토그램**: `EV-L2/3+Security` ×3 · `EV-L3+Security` ×2 · `EV-L1/3` ×2 · `EV-L2/3+Broker` ×2 ·
`EV-L1/3+Security` ×1 · `EV-L3+Broker+Security` ×1 · `EV-L2/3+Broker+Security` ×1
**L1 슬라이스 = 3행 (001·002·009)**
**자체 시리즈**: `SIR-INV-001..016` (**16건**, 결번 없음) / `SIR-AC-001..012` (12건, §26 line 642–)
**1:1 근거** (line 644 verbatim): "…**map one-to-one to `SIR-EV-001` through `SIR-EV-012`**." · **AC↔EV 제목 12/12 일치**

> **판정: full 사이클 필요 (L1×3).** L1 3행은 restrictive detection/declaration, exact scope + combined
> incidents 합성, evidence·status honesty — **모델화 가능**하다. 단 12행 중 **하한이 L3인 행이 3건**
> (004·007·008)으로 거버넌스 6건 중 가장 많아, register 표면 자체가 통합 시스템 결함 시험 쪽으로 기울어 있다.
> INV 16건은 L1 3행 대비 **불변식 밀도가 높은 편**이므로, 설계 시 "INV 전수 ↔ L1 3행" 매핑에서
> **닫지 않는 predicate substrate 비중이 클 것**을 미리 예상해야 한다.

### 4.4 ADR-002-028 Safety Telemetry Integrity / Continuous Conformance Monitoring / Alert Escalation

**원문**: `ADR-002-028-Safety-Telemetry-Integrity-Continuous-Conformance-Monitoring-and-Alert-Escalation-Governance.md` (711행)
**register 구간**: `.md` line **360–371** / `.csv` line **329–340**

| EV id | 제목 | **최소 레벨 (verbatim)** | L1 | 분류 | md/csv line |
|---|---|---|:---:|---|---:|
| `STM-EV-001` | Complete Critical Coverage | `EV-L1/3+Security` | **✔** | **core (L1) +Security 잔여** | 360 / 329 |
| `STM-EV-002` | Provenance, Continuity, Semantics, and Time | `EV-L2/3+Security` | ✗ | not-Phase-1 (+Security) | 361 / 330 |
| `STM-EV-003` | UNKNOWN, Silence, and Stale Green State | `EV-L2/3` | ✗ | predicate-only (하한 L2) | 362 / 331 |
| `STM-EV-004` | Effective Independence and Common Mode | `EV-L2/3+Security` | ✗ | not-Phase-1 (+Security) | 363 / 332 |
| `STM-EV-005` | Deterministic Evaluation and Bound Integrity | `EV-L1/3+Security` | **✔** | **core (L1) +Security 잔여** | 364 / 333 |
| `STM-EV-006` | Suppression and Maintenance Safety | `EV-L2/3+Security` | ✗ | not-Phase-1 (+Security) | 365 / 334 |
| `STM-EV-007` | Alert Correlation, Delivery, and Escalation | `EV-L2/3+Security` | ✗ | not-Phase-1 (+Security) | 366 / 335 |
| `STM-EV-008` | Restrictive and Incident Handoff | `EV-L2/3+Security` | ✗ | not-Phase-1 (+Security) | 367 / 336 |
| `STM-EV-009` | Active Currentness and Send Race | `EV-L3+Security` | ✗ | not-Phase-1 (하한 L3, +Security) | 368 / 337 |
| `STM-EV-010` | UNKNOWN, Broker Finality, and Economic Continuity | `EV-L2/3+Broker` | ✗ | not-Phase-1 (+Broker) | 369 / 338 |
| `STM-EV-011` | Compromise, Fencing, and Failure Domains | `EV-L3+Security` | ✗ | not-Phase-1 (하한 L3, +Security) | 370 / 339 |
| `STM-EV-012` | Evidence, Recovery, and Non-Revival | `EV-L2/3+Security` | ✗ | not-Phase-1 (+Security) | 371 / 340 |

**히스토그램**: `EV-L2/3+Security` ×6 · `EV-L1/3+Security` ×2 · `EV-L3+Security` ×2 · `EV-L2/3` ×1 · `EV-L2/3+Broker` ×1
**L1 슬라이스 = 2행 (001·005)** — **둘 다 `+Security` 태그** (좌표 태그 없는 L1 행 0건)
**`+Security` 비중 10/12** — 거버넌스 6건 중 **최고**
**자체 시리즈**: `STM-INV-001..016` (16건) / `STM-AC-001..012` (12건, §27 line 592–, 소절 형식)
**1:1 근거**: -028은 **"map one-to-one" 문장을 사용하지 않는다.** §27 preamble line 594 (verbatim):
"Written cases define obligations only. They are not completed evidence." ⇒ 대신 **AC 제목 ↔ EV 제목 12/12
문자열 완전 일치**를 머신 대조로 확인했고, gate-status line 797이 이를 뒷받침한다 (verbatim 발췌):
"Two Minor traceability and authority-ownership clarity findings were resolved in commit `c442dd82`:
**STM acceptance/evidence titles now match exactly**…"

> **판정: full 사이클 필요 (L1×2) — 단, 거버넌스 6건 중 최소 규모이며 "+Security 지배" 경고 부착.**
> L1 2행(complete critical coverage 매핑 완전성, deterministic evaluation + bound integrity)은 모델화 가능하나,
> **register 표면의 83%가 `+Security`**라 사이클 산출물 대비 EV 진전 기여가 6건 중 가장 낮다.
> ⇒ **거버넌스 그룹 내 후순위 권고**(§6 참조). 대안으로 -027 SIR 사이클에 **incident handoff 좌표를
> 공유하는 축소 결합 사이클**로 접기를 검토할 수 있다(STM-EV-008 "Restrictive and Incident Handoff",
> ADR-002-028 → ADR-002-027 참조 **9회**로 6건 중 최다 결합 — §5.2).

### 4.5 ADR-002-029 Software Supply-Chain Integrity / Release Artifact Admission / Deployment Provenance

**원문**: `ADR-002-029-Software-Supply-Chain-Integrity-Release-Artifact-Admission-and-Deployment-Provenance-Governance.md` (658행)
**register 구간**: `.md` line **372–383** / `.csv` line **341–352**

| EV id | 제목 | **최소 레벨 (verbatim)** | L1 | 분류 | md/csv line |
|---|---|---|:---:|---|---:|
| `SCI-EV-001` | Source Identity and Review Integrity | `EV-L1/3+Security` | **✔** | **core (L1) +Security 잔여** | 372 / 341 |
| `SCI-EV-002` | Build Isolation, Provenance, and Reproducibility | `EV-L1/2/3+Security` | **✔** | **core (L1) +Security·L2·L3 잔여** | 373 / 342 |
| `SCI-EV-003` | Dependency and Toolchain Closure | `EV-L1/2/3+Security` | **✔** | **core (L1) +Security·L2·L3 잔여** | 374 / 343 |
| `SCI-EV-004` | Signer, Key, and Attestation Compromise | `EV-L2/3+Security` | ✗ | not-Phase-1 (+Security) | 375 / 344 |
| `SCI-EV-005` | Registry Custody and Artifact Substitution | `EV-L2/3+Security` | ✗ | not-Phase-1 (+Security) | 376 / 345 |
| `SCI-EV-006` | Independent Admission and Compatibility | `EV-L1/3+Security` | **✔** | **core (L1) +Security 잔여** | 377 / 346 |
| `SCI-EV-007` | Release Generation and Stale Fencing | `EV-L2/3+Security` | ✗ | not-Phase-1 (+Security) | 378 / 347 |
| `SCI-EV-008` | Deployment Attestation and Environment Confinement | `EV-L2/3+Security` | ✗ | not-Phase-1 (+Security) | 379 / 348 |
| `SCI-EV-009` | Mixed Version, Promotion, Rollback, and Restore | `EV-L2/3+Security` | ✗ | not-Phase-1 (+Security) | 380 / 349 |
| `SCI-EV-010` | Active Currentness, Revocation, Partition, and Send Race | `EV-L3+Security` | ✗ | not-Phase-1 (하한 L3, +Security) | 381 / 350 |
| `SCI-EV-011` | Authority Separation, Broker Finality, and Economic Continuity | `EV-L2/3+Broker+Security` | ✗ | not-Phase-1 (+Broker+Security) | 382 / 351 |
| `SCI-EV-012` | Evidence, Recovery, Hotfix, and Non-Revival | `EV-L2/3+Security` | ✗ | not-Phase-1 (+Security) | 383 / 352 |

**히스토그램**: `EV-L2/3+Security` ×6 · `EV-L1/3+Security` ×2 · `EV-L1/2/3+Security` ×2 · `EV-L3+Security` ×1 · `EV-L2/3+Broker+Security` ×1
**L1 슬라이스 = 4행 (001·002·003·006)** — **4행 전부 `+Security`**; **`+Security` 12/12 (전 행)** — 거버넌스 6건 중 유일한 전수 `+Security`
**`EV-L1/2/3` 3단 staged 행 2건(002·003)** — 이 형태는 register 전역에서 -029(2건)와 -030(5건)에만 존재
**자체 시리즈**: `SCI-INV-001..016` (16건) / `SCI-AC-001..012` (12건, §27 line 548–, 소절 형식)
**1:1 근거**: -029도 **"map one-to-one" 문장 없음**. §27 preamble line 550: "Written cases define obligations
only. They are not completed evidence." ⇒ **AC↔EV 제목 12/12 문자열 완전 일치**(머신 대조) + gate-status
line 799 (verbatim 발췌): "**SCI acceptance/evidence titles are exact 1:1**, all 351 then-registered items
remained `NOT_IMPLEMENTED`…"

> **판정: full 사이클 필요 (L1×4) — 단, "+Security 전수(12/12)" 경고 부착.**
> L1 4행(reviewed-source identity·review independence, build isolation/provenance/reproducibility,
> dependency·toolchain closure, independent admission·compatibility)은 **순수 모델·property로 표현 가능**하며,
> 특히 002/003의 closure·reproducibility는 결정론 property test의 전형적 대상이다.
> 반면 **모든 행이 독립 보안-경계 평가를 요구**하므로, 어떤 SCI-EV도 코드만으로는 닫히지 않는다.
> ⇒ 설계 시 규율 태그에 **"+Security 12/12 — 조직 게이트 전면 미충족"**을 명시적으로 부착할 것.

### 4.6 ADR-002-030 Post-Trade Economic Obligations / Settlement Finality / Conservative Account State

**원문**: `ADR-002-030-Post-Trade-Economic-Obligations-Settlement-Finality-and-Conservative-Account-State-Governance.md` (738행)
**register 구간**: `.md` line **384–395** / `.csv` line **353–364**

| EV id | 제목 | **최소 레벨 (verbatim)** | L1 | 분류 | md/csv line |
|---|---|---|:---:|---|---:|
| `PTF-EV-001` | Fill/FQP vs Post-Trade Obligation Separation | `EV-L1/2/3+Broker` | **✔** | **core (L1) +Broker·L2·L3 잔여** | 384 / 353 |
| `PTF-EV-002` | Fee/Tax/Interest/Financing Legs and Corrections | `EV-L1/2/3+Broker` | **✔** | **core (L1) +Broker·L2·L3 잔여** | 385 / 354 |
| `PTF-EV-003` | Settlement, Cash Availability, Partial/Failure Semantics | `EV-L2/3+Broker` | ✗ | not-Phase-1 (+Broker) | 386 / 355 |
| `PTF-EV-004` | Margin/Collateral/Encumbrance/Haircut/Double-Use | `EV-L1/2/3+Broker` | **✔** | **core (L1) +Broker·L2·L3 잔여** | 387 / 356 |
| `PTF-EV-005` | Borrow/Recall/Return/Buy-In | `EV-L2/3+Broker` | ✗ | not-Phase-1 (+Broker) | 388 / 357 |
| `PTF-EV-006` | Exercise/Assignment/Delivery/Corporate-Action Obligations | `EV-L1/2/3+Broker` | **✔** | **core (L1) +Broker·L2·L3 잔여** | 389 / 358 |
| `PTF-EV-007` | Custody/Transfer/In-Flight/Legal-Title Behavior | `EV-L2/3+Broker+Security` | ✗ | not-Phase-1 (+Broker+Security) | 390 / 359 |
| `PTF-EV-008` | Statement Coverage, Provenance, Conflict/Common-Mode | `EV-L1/2/3+Broker+Security` | **✔** | **core (L1) +Broker+Security·L2·L3 잔여** | 391 / 360 |
| `PTF-EV-009` | Breaks/Busts/Corrections/Reversal/Finality Reopen | `EV-L2/3+Broker+Security` | ✗ | not-Phase-1 (+Broker+Security) | 392 / 361 |
| `PTF-EV-010` | RCL Transfer/Release + Generation Currentness/Send Race | `EV-L2/3+Broker+Security` | ✗ | not-Phase-1 (+Broker+Security) | 393 / 362 |
| `PTF-EV-011` | Partition/Compromise/Stale Writer/Route Bypass | `EV-L3+Broker+Security` | ✗ | not-Phase-1 (하한 L3, +Broker+Security) | 394 / 363 |
| `PTF-EV-012` | Evidence/Recovery/Non-Revival/Status Honesty | `EV-L2/3+Broker+Security` | ✗ | not-Phase-1 (+Broker+Security) | 395 / 364 |

**히스토그램**: `EV-L1/2/3+Broker` ×4 · `EV-L2/3+Broker+Security` ×4 · `EV-L2/3+Broker` ×2 ·
`EV-L1/2/3+Broker+Security` ×1 · `EV-L3+Broker+Security` ×1
**L1 슬라이스 = 5행 (001·002·004·006·008)** — **5행 전부 3단 staged `EV-L1/2/3`**
**`+Broker` 12/12 (전 행)** — register 전역에서 **전 행 `+Broker`인 유일한 family**
**자체 시리즈**: `PTF-INV-001..018` (**18건** — 대상 7개 ADR 중 최다) / `PTF-AC-001..012` (12건, §27 line 631–)
**1:1 근거**: -030도 **"map one-to-one" 문장 없음**. §27 preamble line 633: "Written cases define obligations
only. They are not completed evidence." ⇒ **AC↔EV 제목 12/12 문자열 완전 일치**(머신 대조) + gate-status
line 801 (verbatim 발췌): "**PTF acceptance/evidence titles are exact 1:1 (PTF-AC-001..012 ↔ PTF-EV-001..012)**…"

**Phase 1 명시적 배정 (대상 7건 중 유일)** — `IMPLEMENTATION-PLAN-002.md` line 219–221 (verbatim):

> "- Implement ADR-002-030 Post-Trade Finality Policy, Economic Obligation Record and Active Economic
>   Obligation Set, Fill/FQP vs post-trade obligation separation, Post-Trade Obligation Generation,
>   field-specific finality, statement coverage, break/correction/reversal, conservative RCL coupling,
>   and non-revival models; **property tests for PTF-EV-001**."

⇒ 계획 문서가 **개별 EV id를 지목해 property test를 지시한 유일한 사례**다. 다른 6개 대상 ADR에는 이런
행 단위 지목이 없다.

> **판정: full 사이클 필요 (L1×5) — 거버넌스 6건 중 WDR과 공동 최대이며, Phase-1 배정 근거가 가장 강함.**
> 근거: (a) L1 5행, (b) `IMPLEMENTATION-PLAN-002` line 221의 **명시적 `PTF-EV-001` property test 지시**,
> (c) 상류 의존이 이미 배포된 패키지(`tos/src/tos/` 의 `recon`(ADR-002-006)·`are`(ADR-002-021)·
> `brokercap`(ADR-002-004))에 상당 부분 존재.
> **단서**: `+Broker` 12/12 — Broker Capability Profile 증거는 **첫 broker-specific profile 완성**
> (gate-status §7 step 8)이 선행 조건이라 **어떤 PTF-EV도 Phase 1에서 닫히지 않는다**. 또한 L1 5행이 전부
> `EV-L1/2/3` 3단 staged라 **L1은 3단 중 1단에 불과**하다. 설계 시 이 3단 성격을 규율 태그에 명시할 것.

---

## 5. 교차 실측 — 좌표 태그·의존 체인·상류 구현 상태

### 5.1 좌표 태그 분포 (대상 7개 ADR, 84행)

| ADR | `+Security` 행 | `+Broker` 행 | 좌표 태그 없는 행 | 하한이 L3 이상인 행 |
|---|---:|---:|---:|---:|
| -009 FD | 6 | 0 | 6 | **12 (전 행)** |
| -025 RLP | 4 | 4 | 4 | 1 |
| -026 WDR | 8 | 3 | 2 | 1 |
| -027 SIR | 8 | 4 | 2 | 3 |
| -028 STM | **10** | 1 | 1 | 2 |
| -029 SCI | **12 (전 행)** | 1 | 0 | 1 |
| -030 PTF | 6 | **12 (전 행)** | 0 | 1 |

### 5.2 거버넌스 6건 상호 참조 실측 (ADR 원문 전수 정규식 카운트)

`ADR-002-0NN` 패턴을 각 원문 전수 스캔한 결과 (자기 참조 제외, 대상 7건 사이만 표시):

| 출처 → | -009 | -025 | -026 | -027 | -028 | -029 | -030 |
|---|---:|---:|---:|---:|---:|---:|---:|
| **ADR-002-009** | — | 0 | 0 | 0 | 0 | 1 | 0 |
| **ADR-002-025** | 0 | — | 0 | 1 | 1 | 1 | 0 |
| **ADR-002-026** | 1 | **2** | — | 1 | 0 | 0 | 0 |
| **ADR-002-027** | 0 | **3** | **3** | — | 1 | 1 | 0 |
| **ADR-002-028** | 0 | **4** | 1 | **9** | — | 1 | 1 |
| **ADR-002-029** | 1 | **2** | 0 | **5** | 1 | — | 0 |
| **ADR-002-030** | 0 | 0 | 0 | 0 | 0 | 1 | — |

**정정 사항 (§7.3에 재기재)**: 과제 지시는 "**-025→…→-030 순번 의존**"을 전제했다. 실측 결과 참조는
**단선 체인이 아니라 양방향 상호 참조**다 — gate-status line 801은 이를 명시한다 (verbatim 발췌):
"The upstream corpus (ADR-002-002/004/010/016/017/019/021 and RFC-002 §§9.1/10.32/23.1) already carries
consistent **bidirectional forward-references**."

다만 **가중치를 보면 번호 순서가 최선의 위상 근사**다:

- 무거운 참조(≥2회)는 **전부 번호 순방향**을 따른다: 028→027 (9), 029→027 (5), 028→025 (4), 027→025 (3),
  027→026 (3), 026→025 (2), 029→025 (2).
- 역방향 참조는 **전부 1회짜리 단발 상호참조**다: 025→027/028/029 각 1, 027→028/029 각 1, 028→030 (1), 029→028 (1).

⇒ **번호 순서(-025 → -026 → -027 → -028 → -029 → -030)를 유지하되, "순번 의존"이 아니라
"참조 가중치 기준 위상 근사"로 재기술**해야 한다.

### 5.3 상류 구현 상태 실측 (`tos/src/tos/` 배포 패키지 15개)

`are`, `authority`, `brokercap`, `canonical`, `capsule`, `dsl`, `evidence`, `liveauth`, `ordering`,
`orthostate`, `protective`, `rcl`, `recon`, `spg`, `time`

대상 ADR의 최다 참조 상류(자기·대상 제외) 대비 구현 상태:

| ADR | 최다 참조 상류 (횟수) | 구현 상태 |
|---|---|---|
| -009 FD | -007 (5), -008 (2), -012 (2), -013 (2), -014 (2), -015 (2) | liveauth ✅ / time ✅ / RCLP ❌ / EGRESS ❌ / spg ✅ / HAG ❌ |
| -025 RLP | -015 (7), -007 (6), -014 (4), -024 (3) | HAG ❌ / liveauth ✅ / spg ✅ / CUR ❌ |
| -026 WDR | -014 (10), -015 (8), -016 (3), -024 (3) | spg ✅ / HAG ❌ / ERI ❌ / CUR ❌ |
| -027 SIR | -017 (6), -015 (5), -014 (3), -016 (3), -007 (3) | SBR ❌ / HAG ❌ / spg ✅ / ERI ❌ / liveauth ✅ |
| -028 STM | -027 (9), -024 (7), -025 (4), -013 (2) | SIR ❌ / CUR ❌ / RLP ❌ / EGRESS ❌ |
| -029 SCI | -014 (6), -024 (6), -027 (5), -013 (3) | spg ✅ / CUR ❌ / SIR ❌ / EGRESS ❌ |
| -030 PTF | -013 (5), -010 (5), -006 (4), -016 (4), -017 (4), -021 (4) | EGRESS ❌ / NT ❌ / recon ✅ / ERI ❌ / SBR ❌ / are ✅ |

⇒ **거버넌스 6건은 전부 미구현 상류(HAG/CUR/SBR/EGRESS/ERI/NT 등)에 강하게 의존**한다. 이는 기존 잔여
순서안이 거버넌스를 **최후미**에 둔 판단을 실측으로 뒷받침한다.

### 5.4 patch 영향 확인 (EV 레벨 개정 여부)

`tos-spec/src/part-1-foundation/patches/` 내 대상 ADR 관련 파일 5건을 확인했다:
`ADR-002-026-Patch-0050.md`, `ADR-002-028-Patch-0027.md`,
`PATCH-ADR-002-025/026/027-v0.2-Single-Operator-Re-Arm-Recognition.md`.

- `ADR-002-026-Patch-0050.md` line 21 (verbatim): "…no new WDR-INV invariant, requirement, numeric bound,
  or EV; no broker proper noun. … **the Evidence Register count is held (Part-1 372)**."
- `ADR-002-028-Patch-0027.md` line 40–41 (verbatim): "…requirement, numeric bound, or **new EV ID is
  introduced; the Evidence Register count is unchanged (372)**."

⇒ **어떤 patch도 대상 ADR의 EV 레벨·행 수를 변경하지 않았다.** §3–§4의 실측값은 patch 반영 후 최신 상태다.

---

## 6. 거버넌스 6건 권장 처리 순서

**전제**: 잔여 non-governance 사이클(-023 IAP · -022 AFG · -017 SBR · -019 VTG · -015 HAG · -010 NT ·
-011 PR · -013 EGRESS · -024 CUR · -009 FD)을 **먼저 완결**한다 (§5.3 근거 — 거버넌스 6건 전부가
미구현 상류에 강하게 의존).

**권장 순서 (번호 순 유지, 근거 재기술)**:

| # | ADR | L1 | 순서 근거 (실측) |
|---|---|---:|---|
| 1 | **-025 RLP** | 4 | 6건 중 **가장 많은 무거운 인바운드 참조**(026×2, 027×3, 028×4, 029×2). L1 4행이 **전부 좌표 태그 없는 순수 `EV-L1/3`** — 유일. Trial Policy / Promotion Generation을 후속 4건이 소비 |
| 2 | **-026 WDR** | **5** | -025만 앞서 참조(2회). L1 5행으로 최대 tie. 독립 리뷰 **zero-finding 통과**(gate-status line 793) — 저작 안정성 최상 |
| 3 | **-027 SIR** | 3 | -025(3)·-026(3)을 참조하므로 두 건 뒤. **-028의 최대 상류**(028→027 9회) 및 -029의 주요 상류(5회) |
| 4 | **-029 SCI** | 4 | -027(5)·-025(2)·-014 spg(6, ✅ 구현됨)를 참조. **-028보다 L1이 많고**(4 vs 2) -028 참조는 1회뿐이라 **-028보다 앞 배치 권고** |
| 5 | **-028 STM** | **2** | L1 **6건 중 최소**, `+Security` 10/12로 최고. -027(9)·-025(4)·-029(1)를 참조하므로 자연히 후미. **축소 사이클 또는 -027 SIR과의 결합 사이클 검토 권고**(§4.4) |
| 6 | **-030 PTF** | **5** | **참조 그래프상 가장 독립적**(아웃바운드 1건: -029; 인바운드 1건: -028). L1 5행 + `IMPLEMENTATION-PLAN-002` line 221의 **명시적 `PTF-EV-001` property test 지시**로 근거는 강하나, `+Broker` 12/12 — **첫 Broker Capability Profile 완성**(gate-status §7 step 8)이 선행. 독립성이 높아 **순서 이동이 가장 자유로움** |

**대안 배치 (검토용, 비권고 아님)**: -030 PTF는 참조 그래프상 거의 독립적이고 L1이 5행으로 최대 tie이며
상류 `recon`·`are`·`brokercap`이 이미 배포되어 있으므로, **-025 다음(2순위)으로 당기는 배치도 실측상
방어 가능**하다. 단 `+Broker` 12/12 게이트를 사이클 산출물이 전혀 진전시키지 못한다는 점은 동일하다.

**-009 FD 배치**: 위 6건과 별개로, §3.3 판정에 따라 **저비용 predicate-only 사이클** 또는 **이연**.
full 사이클을 배정할 register 근거는 없다. 잔여 순서안의 기존 위치(거버넌스 직전)를 유지해도 무방하다.

---

## 7. 사전 지도와의 차이 — 정정 명시

### 7.1 정정 없음 (확인)

- **"ADR-002-009 = L1×0"** — **실측으로 확정**. `EVIDENCE-REGISTER-002.csv` line 101–112 / `.md` line 125–136,
  12행 최소 레벨이 전부 EV-L3 이상, L1 슬라이스 0행. 사전 지도와 **불일치 없음**.
  (추가 정보: 하한이 L3이라 TIME의 L2 하한보다도 L1 거리가 멀다 — 사전 지도가 담지 않았던 사실.)

### 7.2 신규 측정 — "거버넌스 = predicate-only" 암묵 가정 기각

- 사전 지도는 거버넌스 6건을 "**EV-L1 표면 per-ADR 판정 미실시**"로만 표기했다.
- 실측 결과 **6건 전부 L1 슬라이스를 보유**한다: -025 (4) · -026 (5) · -027 (3) · -028 (2) · -029 (4) ·
  -030 (5) — **합계 23행**.
- ⇒ **6건 전부 "full 사이클 필요"**이며, 어느 것도 "0건 완결 predicate-only 사이클"에 해당하지 않는다.
  거버넌스 ADR이라 하여 L1 표면이 없을 것이라는 암묵 가정은 **기각**된다.
- 규모 감각: 완결 사이클 선례 대비 **-026/-030 (L1×5) = ARE (L1×5)와 동급**, **-028 (L1×2)이 최소**.
  거버넌스 6건 어느 것도 SPG (L1×8) 규모에는 이르지 않는다.

### 7.3 정정 — "-025→…→-030 순번 의존" 표현

- 과제 전제 "순번 의존"은 **부정확**하다. 실측상 참조는 **양방향 상호 참조**이며, gate-status line 801이
  "**bidirectional forward-references**"로 명시한다.
- **정정된 표현**: "번호 순서는 **참조 가중치 기준 위상 근사**다 — 무거운 참조(≥2회) 7건이 전부 번호
  순방향이고, 역방향 참조는 전부 1회짜리 단발이다." (§5.2 실측표)
- **부가 정정**: 순서를 L1 수·독립성으로 재조정하면 **-029 SCI(L1×4)를 -028 STM(L1×2)보다 앞**에 두는 것이
  실측상 더 타당하다(§6). 즉 번호 순서를 그대로 쓰지 말고 4/5번을 교환하는 배치를 권고한다.

### 7.4 정정 — ADR-002-009의 자체 시리즈 형태

- 다른 대상 6건은 전부 `<FAM>-INV-###` 번호 시리즈(15–18건)를 가지나, **ADR-002-009에는 `FD-INV-###`가
  존재하지 않는다**(§3.1). §6 "Mandatory Isolation Invariants"는 번호 없는 산문 소절 6.1–6.7이다.
- ⇒ FD 설계 시 **`FD-INV-001` 등 존재하지 않는 id 인용 금지**(phantom id). 이는 기존 교훈
  "**phantom 금지(인용 전 grep)**"의 직접 적용 대상이다.

### 7.5 정정 — register 총 항목 수 표기 불일치 (기존 문서의 내부 에라타)

- `ARCHITECTURE-GATE-STATUS.md` line 192 (verbatim): "The Evidence Register contains **363**
  `NOT_IMPLEMENTED` items…"
- 그러나 같은 파일 line 982 (§7): "…all **372** items in EVIDENCE-REGISTER-002.csv…", line 409:
  "…no new EV (**Part-1 stays 372**)"
- `EVIDENCE-REGISTER-002.md` line 12–13: "Total evidence items: **372** / NOT_IMPLEMENTED: **372**"
- **머신 실측: CSV 데이터 행 = 372.**
- ⇒ **line 192의 "363"은 과거 스냅샷의 잔존 수치**로 보이며 현재값과 불일치한다. 본 메모는 이를
  **정정 제안이 아니라 관측 사실로만 기록**한다(비규범 메모이므로 corpus를 수정하지 않는다).
  기존 open 에라타 목록에 추가 검토 항목으로 올릴 것을 권고한다.

---

## 8. 직접 확인하지 못한 항목 — 정직 공개

본 메모의 판정은 아래 항목들을 **직접 검증하지 않은 상태**에서 내려졌다. 후속 설계 사이클은 해당 항목을
착수 시 1차 소스로 재확인해야 한다.

1. **판정 규칙의 선례 검증 범위** — L1 카운팅 규칙(§2)은 **완결 사이클 3건(ARE·SPG·TIME)**의 설계 문서에만
   역적용해 재현성을 확인했다(§2.1). `docs/plans/` 내 나머지 tos 설계 문서 14건
   (`2026-07-15`, `2026-07-20` ×4, `2026-07-21` ×2, `2026-07-23`, `2026-07-24`, `2026-07-25` ×5 중 대조분 제외)의
   L1 카운트는 **대조하지 않았다.** 3건 모두 정확히 일치했으므로 규칙은 안정적이라고 판단하나,
   **전수 검증은 아니다.** 또한 사이클 번호(#N)와 설계 문서의 대응 관계는 확인하지 않았으므로
   본 메모는 메모리 인덱스에 기록된 번호(#12 SPG, #13 ARE)를 **인용만** 하고 검증하지 않았다.

2. **Part-3 개발 트랙 register 미측정** — `part-3-development/verification/EVIDENCE-REGISTER-DEV.csv`
   (98 items, gate-status line 982)는 조사 범위 밖이다. 대상 7개 ADR은 전부 Part-1 소속이지만,
   **DEV 트랙에 대상 ADR을 참조하는 EV 행이 있는지는 확인하지 않았다.**
   (단, gate-status line 352에서 `ADR-DEV-005` 패치가 `RLP-EV-008`에 바인딩된 사례를 관측했으므로,
   **DEV↔Part-1 교차 바인딩은 실재한다.** -025 설계 시 우선 확인 대상.)

3. **VERIFICATION-PROFILE-002.yaml 미측정** — 대상 ADR별 scope key / bound / limit 커버리지를 확인하지
   않았다. gate-status line 767에 따르면 프로파일은 `2.1-PROPOSED`이고 `approved_by: []`(미승인)이다.
   **바운드 승인은 Phase-0 게이트이며 EV-L1 카운트와 독립**이므로 본 판정에 영향은 없다고 판단하나,
   각 사이클 착수 시 별도 확인이 필요하다.

4. **`TRACEABILITY-MATRIX-002.md` 미확인** — `verification/TRACEABILITY-MATRIX-002.md`(24KB)를 읽지 않았다.
   여기에 대상 ADR의 SAFE-xxx / 요구사항 매핑이 있을 수 있으며, 설계 시 §-clause ↔ SAFE-xxx 인용에
   필요할 것으로 예상된다.

5. **ADR 본문의 조항별 L1 도달성 미분석** — 본 메모는 **register EV 레벨 표면만** 측정했다. 각 ADR의
   §-clause를 core / predicate-only / not-Phase-1로 분류하는 작업(선례 문서들의 §1 범위 매핑 표에
   해당)은 **수행하지 않았다.** 이는 각 설계 사이클의 §1에서 수행할 작업이다.
   ⇒ 따라서 본 메모의 "L1×N"은 **사이클 규모의 상한 지표**이지, 실제 저작 분량의 확정치가 아니다.

6. **`reviews/` 디렉터리 미확인** — `tos-spec/src/part-1-foundation/reviews/`(24개 항목)를 열지 않았다.
   대상 ADR의 EV-L0 리뷰 원문에 EV 레벨 관련 finding이 있을 가능성을 배제하지 못한다.
   (간접 확인: gate-status line 787–801의 리뷰 요약 문단들은 읽었고, EV **레벨** 변경을 시사하는 서술은
   없었다. -028의 Minor 2건은 title 일치·authority ownership 문제로 commit `c442dd82`에서 해소되었다고
   기록되어 있다.)

7. **`ADR-002-028`의 `TAB-INV-006` 미조사** — -028 원문 전수 스캔 중 `STM-INV-###`와 별개로
   `TAB-INV-006` 참조 1건을 관측했으나, 이 시리즈의 출처 ADR과 성격은 확인하지 않았다.
   -028 설계 시 확인 대상.

8. **register `notes` / `evidence_location` 열 미검토** — CSV의 `latest_run_id`, `latest_result_date`,
   `evidence_location`, `notes` 열은 값을 확인하지 않았다(전 행 `NOT_IMPLEMENTED`이므로 공란으로
   추정하나 **직접 검증하지 않았다**).

9. **`+Security` / `+Broker` 게이트의 조직적 충족 경로 미조사** — 두 좌표가 실제로 어떤 산출물·승인으로
   충족되는지(누가 independent security-boundary assessment를 수행하는지 등)는 조사하지 않았다.
   본 메모는 이를 "코드 사이클로 진전 불가"로만 취급했다.

---

## 9. 부록 — 재현 절차

본 메모의 모든 카운트는 아래 절차로 재현 가능하다 (읽기 전용):

```bash
cd /Users/harris/Development/private/kis_unified_sts/tos-spec/src/part-1-foundation/verification
python3 - <<'EOF'
import csv, re, collections
with open('EVIDENCE-REGISTER-002.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
def has_l1(level):
    base = level.split('+')[0]                    # '+Security'/'+Broker' 제거
    m = re.match(r'^EV-L([\d/]+)$', base)
    return bool(m) and '1' in m.group(1).split('/')
by = collections.OrderedDict()
for r in rows:
    by.setdefault(r['primary_adr'].strip(), []).append(r)
for adr, rs in by.items():
    l1 = [r['evidence_id'] for r in rs if has_l1(r['minimum_evidence_level'])]
    print(f"{adr:<20} rows={len(rs):>2} L1={len(l1):>2}  {l1}")
EOF
```

**주의**: `Profile-dependent` 레벨 값 1건(`BC-EV-###`, ADR-002-004)은 정규식에 매칭되지 않으므로 L1 부재로
처리된다. 대상 7개 ADR에는 이 값이 없다(전 84행이 `EV-L…` 형식).

