# 작업 메모 — tos-spec EV-L2 (Component Fault Test) 파일럿 설계 (2026-07-29)

> **v1.2** (델타 재검증 REVISE의 기계적 정정 7건 — 오케스트레이터 직접 적용[리뷰어 권고·#20/#23 선례];
> 개정 로그 §12). **v1.1** (독립 비평 REJECT 개정; 개정 로그 §12). 리뷰가 구현 직접 실행 계측·착지 L1 아티팩트 대조로
> 실증한 C1~C3·M1~M10을 1차 소스 재실측 후 반영했다. **핵심 방향 전환: v1.0이 STATE-EV-001의 /2
> durable 층을 "in-memory 직렬화 경계"로 재정의한 것을 철회한다**(C1 — 비준 문서 정반대·증거 오염 경로).
>
> **이 문서의 성격**: `STATE-EV-001`(ADR-002-005)·`SPG-EV-002`(ADR-002-014) 두 행의 착지한 EV-L1 stage
> 위에 얹을 **EV-L2 component-fault 층**의 **설계·실행 계획**이다. 코드는 작성하지 않는다(설계 계약 단계).
> **어떤 acceptance/PASS도 선언하지 않는다** — L2 실행이 완료돼도 P0-1·독립 서명·**VER §2.7 coverage
> argument**·(STATE) durable-axis residual 잔여 게이트가 남는다(§9). "L2 설계·실행 계획이며 PASS 선언 아님."
>
> **브리핑 규율 상속**: 방법론 플레이북 §0(저작자 절, :27)·부록 B(§0.5 체크리스트, **:529**)·부록 D(극성,
> **:598**). anti-phantom: 모든 인용 grep/Read 실측·file:line 부록 A 병기·존재/부재 대칭(부재=negative-grep).

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

**확정한다**: (1) EV-L2 의미 실측 + **순수 모델 계층에서 EV-L2가 원리적으로 성립하는가**의 명시 논증(§2);
(2) /2 durable 규범 충돌의 정직한 명시(§2, C1); (3) fault 카탈로그(§3 STATE·§4 SPG, falsifiable Expected만);
(4) **L2 실행 선행 L1 하드닝 명세**(§5, C2); (5) 하네스 확장 계약(§6, coverage_argument·§3-미충족 목록 등);
(6) §10 갭 처분(§7); (7) 테스트 스위트(§8); (8) 수용 주장의 **축소된** 정확한 형태 + 잔여 게이트(§9).

**하지 않는다**:

- **PASS/acceptance 선언.** 하네스는 원리적으로 row status를 이동시키지 않는다(`tools/tos_evidence_run.py:26`).
- **/2 durable 층의 재정의.** STATE-EV-001 Expected "durable"(VER:1024)의 지시체는 **실 durable 저장·크래시
  후 복원**(ADR-002-005 §13:197 "SHALL be durable and reconstructable after crash"·AC-005-1:237 "and
  **persisted**")이다. 이 축은 persistence 기술 미결정(ADR §4:61)이자 EV-L3(VER:152)이라 **본 파일럿은
  증거하지 않고 residual로 등재**한다(§9, VER §2.7/§378).
- **SPG-EV-003 커버 주장.** unknown/duplicated/aliased/omitted-**field** 축은 SPG-EV-003(`EV-L1/2+Security`,
  VER:1553·1555)이다(§7).
- **L1 하드닝의 구현.** §5는 코드 수정 **명세**만 확정한다 — 구현은 별도 단계(executor)다.

---

## 0.5. 선제-봉합 체크리스트 (플레이북 부록 B:529 상속 + 본 문서 앵커)

| # | 규율 | 본 문서 적용 |
|---|------|-------------|
| 1 | **anti-phantom (부재·존재 대칭)** | 전 인용 file:line 부록 A. 부재 3건 negative-grep(§7 undeclared-field·§8 l2 dir 부재·§4 overflow Expected 부재). **v1.0 자기위반 교정**: 부록 B/D·§6.1 앵커가 sed-재번호 드리프트(150/219/94 → 실측 529/598/469) — 인용-드리프트(2.C:221)를 저작자가 재발, §12에 발원 기록 |
| 2 | **∅-seal 양방향** | "fault 0건 주입"≠"위반 없음". `all_faults_met`에 "Expected 미정의 fault 0건" 구조 게이트 신설(§6, C2-c) |
| 3 | **구조 파생 > 자기신고** | Expected는 self-report 아닌 구조적 fail-closed(ValidationError·reason_set 비공허)에서 관측 |
| 4 | **falsifiable Expected만 등재** (신설) | Expected가 결정적·반증가능하지 않은 fault는 카탈로그 제외·residual 이연(§4 SPG-07; C2-b) |
| 5 | **음극성 `is False`만 (부록 D:598)** | 극성 코드 미신설. SPG 오라클 소비 flag는 양극성(`consistent`/`reproducible`)이라 `is not True` deny 정당(실측 `predicates.py:448·456·460`) |
| 6 | **register CSV 전수 파싱** | PASS-후보 집계 csv 모듈(naive awk가 SPG-EV-002 콤마로 오집계 — 실측·§1.2) |
| 7 | **over-scope 금지 (정직 이연)** | /2 durable·SPG-EV-003·adversarial·실스토리지 명시 이연(§9·§10) |
| 8 | **뮤테이션 canary 실효성** | 각 L2 fault: both-ways + fault 제거 mutant가 테스트 FAIL 실측 의무(§8.4) |

---

## 1. EV-L2의 의미 실측 (VER-002-001 verbatim — 리뷰 무결 확인·유지)

### 1.1 강도 레벨 정의 (VER §5:142-152)

```text
EV-L1 (VER:142-144)  Model and Property Verification — state-machine exploration,
                     model checking, property-based testing, deterministic simulation.
EV-L2 (VER:146-148)  Component Fault Test — "A component is tested with controlled
                     failure injection and authoritative state inspection."
EV-L3 (VER:150-152)  Integrated System Fault Test — "Multiple live-path components are
                     tested together with real persistence, identity, and network boundaries."
```

**세 문장의 차이가 본 설계의 전 경계를 규정**: L1=valid 공간 속성; L2=단일 컴포넌트 + 통제된 실패 주입 +
**권위 상태 검사**; L3=다중 컴포넌트 + **실 persistence·identity·network**. ⇒ 통합·실스토리지·크래시
복원·adversarial 전부 L3+.

### 1.2 두 행이 PASS-도달 유이 후보인 이유 (register 전수 파싱)

`EVIDENCE-REGISTER-002.csv` 372 행 csv 전수: minimum이 L1/L2만 쓰고 suffix 없는 행 = **정확히 2행, 둘 다
READY** — `STATE-EV-001`(`EV-L1/2`, CSV:91, ADR-002-005)·`SPG-EV-002`(`EV-L1/2`, CSV:162, ADR-002-014).
bare `EV-L2` 5행은 전부 NOT_IMPLEMENTED. `+Security`/`+Broker`/`/3` 행은 순수 모델로 안 닫힌다. naive
`awk -F,`는 SPG-EV-002 Description 인용부호 콤마로 오집계(실측) — csv 모듈만 신뢰.

### 1.3 per-EV Injection/Expected (VER verbatim)

**STATE-EV-001 — Orthogonal Composite Persistence** (VER:1019-1024):
- Minimum: `EV-L1/EV-L2`(1021). Supports: AC-005-1(1022).
- **Injection**(1023): "Generate every valid composite in ADR-002-005 §14 plus boundary combinations where
  one dimension changes while the other four remain unchanged; **persist, reload, and replay** each state."
- **Expected**(1024): "Every valid composite remains **representable and durable**; **no dimension is
  silently derived** from another except through an explicit CPL invariant and owned transition."

**SPG-EV-002 — Semantic Units, Numeric, and Cross-Field Validation** (VER:1544-1549):
- Minimum: `EV-L1/EV-L2`(1546). Supports: SPG-AC-002(1547).
- **Injection**(1548): "Mutate units, currency, multiplier, sign, precision, rounding, boundary inclusion,
  overflow, underflow, NaN, infinity, vector dimension, aggregate formula, and cross-field constraints
  across otherwise valid artifacts."
- **Expected**(1549): "Every unsafe or incomparable semantic mutation is **rejected deterministically
  before activation**; no parser or consumer interpretation grants a more permissive result."

**Security suffix 부재 재실측**: 두 행 모두 suffix 없음(1021·1546). 대조 witness STATE-EV-005 "plus security
assessment"(1049)·SPG-EV-003 동(1553) ⇒ 존재-대조로 확증.

### 1.4 §7 아티팩트 "as applicable" + §9.1 + §2.7 coverage

- **§7**(256-295): "as applicable"(258) 34종. 순수 모델 L2는 applicable 부분집합만(§6.3). item3=fault
  timeline(262)·item30-34=invariant/final/pass-fail/reviewer/digests(289-293).
- **§9.1**(350): "test identity, baseline, **seed, and fault schedule** SHALL be append-only."
- **§2.7**(76-78, 신규 반영): "**A finite set of executed evidence cases does not by itself discharge a
  universally-quantified safety claim** ... SHALL carry a coverage argument ... at minimum the boundary
  values of each governed dimension **and the adversarial combinations of the approved Adverse Scenario
  Set (ADR-002-021)** ... any part ... not exercised as residual (§378)." VER:3170도 "abstract or bounded
  model still requires the §2.7 coverage argument"라 못 박음. ⇒ **두 행의 L2 주장은 모두 universally-
  quantified**("every valid composite"·"every ... mutation")이라 §2.7 coverage argument 의무(§9).

---

## 2. EV-L2가 순수 모델 계층에서 성립하는가 (원리 논증 + /2 규범 충돌)

### 2.1 규범 충돌의 명시 (C1 — v1.0 재정의 철회)

**충돌 실측**: (a) VER:152 — 실 persistence는 EV-L3. (b) ADR-002-005 §13:197 — 다섯 차원 "SHALL be
durable and reconstructable after crash". (c) AC-005-1:237 — "representable **and persisted**"(STATE-EV-001
지목). (d) 설계 #8:320 verbatim — "/2 = 실제 durable 저장·크래시 후 복원(persistence 기술 — ADR §4 line
61 미결정)". ⇒ **STATE-EV-001 Expected "durable"의 지시체는 실 durable 저장이며, 이는 (i) persistence
기술 미결정(ADR §4:61 "does not decide the persistence technology")과 (ii) EV-L3(VER:152·STATE-EV-004
`EV-L3` VER:1042) 양쪽에 걸린다.**

**v1.0의 오류**: /2를 "in-memory 직렬화 round-trip"으로 재정의해 L2가 /2를 닫는다고 함축한 것은 **비준
문서(설계 #8:320)를 정면으로 반증**하며, in-memory-only run이 durable 축을 covered로 오주장하는 **증거
오염 경로**다. **본 파일럿은 /2를 재정의하지 않는다.**

### 2.2 "authoritative state inspection의 지시체"는 순수 모델 계층에 존재하는가

EV-L2(VER:148)의 3요건 = (1)컴포넌트 (2)통제된 실패 주입 (3)권위 상태 검사. 두 행 개별 판정:

**SPG-EV-002 — 순수 모델 L2가 완전 valid**:
- 컴포넌트 = Safety Profile Validator(`semantic_validation`·`profile_within_envelope`) — 자기완결 결정
  컴포넌트. 주입 = otherwise-valid bundle에 단일 semantic 변조. 권위 상태 = `SemanticValidationResult`
  (valid+reason_set) verdict — **검증 컴포넌트의 권위 verdict가 곧 지시체**. "before activation"(1549)은
  구조적 충족(spg는 representation·비-enforcement, `_base.py:17-22`). durable-저장 의존 **없음**. ⇒ 순수
  모델 L2 = SPG-EV-002의 **완전한 EV-L2**(단 §2.7 coverage·§5 하드닝 선행).

**STATE-EV-001 — 순수 모델 L2가 부분 valid (축 분할)**:
- 컴포넌트 = `CompositeState` (역)직렬화·재구성. 주입 = 직렬 형태 오염. 권위 상태 검사의 지시체는 **축마다
  다르다**:
  - **저장-독립 축**(representability·**no silent derivation**·구조 무결성·dimension-swap): 재구성된
    composite / 발화된 ValidationError가 well-defined 지시체 ⇒ 순수 모델 L2가 **valid**.
  - **durable 축**("durable" VER:1024·crash 복원 ADR §13:197): 지시체 = 실 fault(전원상실·부분쓰기)를
    견딘 **실 persisted 권위 record** — in-memory에 **부재** ⇒ 순수 모델 L2로 **도달 불가**.

### 2.3 대안 명시 검토 (리뷰 Open Q)

| 대안 | 논증 | 판정 |
|---|---|---|
| **A. 순수 모델 L2가 /2 전부를 닫는다**(v1.0) | durable 지시체가 in-memory에 부재하므로 거짓·증거 오염 | **기각** |
| **B. 순수 모델 EV-L2 불가 ⇒ 두 행 READY 유지·미실행** | SPG는 완전 valid L2 존재(2.2)·STATE 저장-독립 축도 실 fault 표면 보유 ⇒ 미실행은 정보 손실 | **기각**(단 STATE durable 축엔 부분 채택 — 그 축은 미실행 residual) |
| **C. 축 분할: 성립하는 축만 EV-L2 실행, durable 축 residual**(채택) | SPG=완전 L2; STATE=저장-독립 축 L2 + durable 축 §378 residual. 과대주장 없이 증거 전진 | **채택** |

**귀결**: SPG-EV-002는 순수 모델에서 완전 EV-L2(하드닝·coverage 선행). **STATE-EV-001은 저장-독립 축만
EV-L2 실행**하고 durable 축은 residual — 따라서 **본 파일럿만으로 STATE-EV-001은 evidence 축에서 PASS-
적격이 아니다**(자기 Expected "durable" 미방전). 이 비대칭을 §3/§4 태그·§9 수용주장·§10 경계표가 관철한다.

---

## 3. Fault 카탈로그 — STATE-EV-001 (저장-독립 축; CompositeState (역)직렬화·재구성)

**컴포넌트**: `CompositeState`(`records.py:39-102`) + digest-binding 기반(`canonical/_base.py:99`). **커버
축**: representability + **no-silent-derivation**(VER:1024) + 구조 무결성. **CPL-1..7 정합은 커버하지
않는다**(fault 0건 — CPL coupling은 STATE-EV-003 `EV-L1/3` 소관, M6 반영·v1.0 잉여 선언 제거). seed=0
(`--hypothesis-seed=0`+`PYTHONHASHSEED=0`). 주입-지점 열 = 가드 실현 코드 라인 **또는 그 계약
docstring**(M7 부분 이행 — ST-01/02/03/08/12는 docstring 앵커[v1.2 N3 정직화]; **fault-timeline 작성 시
실 가드 라인을 실측해 `injection_point`에 기록하는 것이 구현 의무**); 계약 앵커 별도 열.

| id | fault (주입 방법) | 가드 코드 라인 | Expected (fail-closed) | 계약 앵커 | 태그 |
|---|---|---|---|---|---|
| ST-01 | 필수 차원 탈락 + **silent-derivation 프로브**(이웃이 함의해도 파생 금지; ST-10 병합) | `records.py:42-47` | `ValidationError` (no default·이웃 파생 없음) | VER:1024; comp test `composite.py:103` | L1-인접 |
| ST-02 | NONE↔None 치환 | `vocabulary.py:78-79` | `ValidationError` (NONE≠None) | `composite.py:112` | L1-인접 |
| ST-03 | 차원-swap 값 오염 | `vocabulary.py:19-22` | `ValidationError` (StrEnum 거부) | `composite.py:144` | L1-인접 |
| ST-04 | enum-외 토큰 | `vocabulary.py:110-118` | `ValidationError` | vocabulary test | L1-인접 |
| ST-05 | covered 변조 + digest 유지 | `canonical/_base.py:201` | `ValidationError(cause=ArtifactIntegrityError)` (M3) | VER:1024 | **L2-신규** |
| ST-06 | digest 변조 + covered 유지 | `canonical/_base.py:201` | `ValidationError(cause=ArtifactIntegrityError)` | — | **L2-신규** |
| ST-07 | canonicalization_version 미등록 값 | `canonicalization.py:248` | **하드닝 후** `ValidationError`; **하드닝 전 raw KeyError = DEVIATION**(M4·§5) | §5 H-4 | **L2-신규·하드닝 선행** |
| ST-08 | same-id / different-bytes | `records.py:5-7` | `CRITICAL_CONFLICT` | `composite.py:200·247` | L1-인접 |
| ST-09 | status/lifecycle 모순(ISSUED+null digest) | `canonical/_base.py:187-196` | `ValidationError(cause=ArtifactIntegrityError)` | — | **L2-신규** |
| ST-11 | scalar meta 타입 오염(`observation_revision:"two"`) | `records.py:102` | `ValidationError` | — | L1-인접 |
| ST-12 | self-excluded 필드 변경 round-trip 안정(양성 canary) | `records.py:64-65·101-102` | digest 불변·재구성 동일 | §2.3 both-ways | **L2-신규** |

**규모: STATE = 11 fault** (L2-신규 5 = ST-05·06·07·09·12; L1-인접 6). ST-10(silent-derivation) → ST-01
병합(M6; "탈락 차원이 이웃에서 파생되지 않음"은 필수-필드-없음의 관측면). `reconstruct_conservative`
(`predicates.py:688`)는 L3 restart projection이라 미호출(경계 준수).

---

## 4. Fault 카탈로그 — SPG-EV-002 (semantic/numeric/cross-field 검증 컴포넌트)

**컴포넌트**: `GovernedDimensionLimit`(`records.py:87-114`) + `semantic_validation`(`predicates.py:353`) +
`profile_within_envelope`(`predicates.py:142`). **규칙(§0.5-4)**: Expected가 결정적·반증가능하지 않은
fault는 카탈로그 제외.

| id | fault (주입 방법) | 가드 코드 라인 | Expected (fail-closed) | 계약 앵커 | 태그 |
|---|---|---|---|---|---|
| SPG-01 | unit mismatch | `predicates.py:425-427` | `UNIT_OR_MULTIPLIER_MISMATCH` | ADR §11 step3:304 | L1-인접 |
| SPG-02 | multiplier mismatch | `predicates.py:350·425` | `UNIT_OR_MULTIPLIER_MISMATCH` | step3:304 | L1-인접 |
| SPG-03 | sign mismatch | `predicates.py:350·425` | `UNIT_OR_MULTIPLIER_MISMATCH` | step3:304 | L1-인접 |
| SPG-05 | **NaN magnitude** | `records.py:107-108`(CanonicalDecimal 필드) | `ValidationError` (**§5 H-1 pin 선행**; M8) | step3:304 | **L2-신규·하드닝 선행** |
| SPG-06 | **Infinity magnitude** | `records.py:107-108` | `ValidationError` (§5 H-1) | step3:304 | **L2-신규·하드닝 선행** |
| SPG-08 | **precision/rounding/boundary 메타 mismatch + 경계 동등**(env=EXCLUSIVE·profile==max) | `predicates.py:233·350` | **fail-closed**(reject) — **§5 H-2 하드닝 선행** (C2: 현재 valid=True·∅ 실측 fail-open) | step3:304 "precision, rounding ... boundary inclusion" | **L2-신규·하드닝 선행** |
| SPG-09 | over-envelope(profile>max) | `predicates.py:233` | `EXCEEDS_ENVELOPE` | SPG-INV-001 | L1-인접 |
| SPG-10 | undeclared dimension(vector-dim 축) | `predicates.py:228-229` | `EXCEEDS_ENVELOPE` | step6:307 | L1-인접 |
| SPG-11 | mandatory dim 탈락(dominance omit-limb) | `predicates.py:213-218` | rejected(공허 통과 불가) | step6:307(**M5 부분 반론**) | L1-인접 |
| SPG-13 | cross-field 위반(injected `cross_field_consistent`) | `predicates.py:448` | `CROSS_FIELD_CONSTRAINT_VIOLATION` | step5:306 | L1-인접·플래그 |
| SPG-14 | vector-dim 집합 cardinality/identity 불일치 | `predicates.py:204-234` | rejected | step6:307(매핑) | **L2-신규·매핑** |
| SPG-15 | None magnitude | `predicates.py:233`·`records.py:102-103` | rejected(missing=over-envelope) | SPG-INV-001 | L1-인접 |

**규모: SPG = 12 fault** (L2-신규 4 = SPG-05·06·08·14; L1-인접 8) (**v1.2 N1 정정 — 표 실측 12행**).
**카탈로그 제외/이연**:
- **SPG-12 duplicate** → **SPG-EV-003 substrate**(ADR §11 step12:313 "duplicated ... fields" verbatim = SPG-
  EV-003 Injection VER:1555 "duplicate"). §7 논리 적용해 제거(M5 채택).
- **SPG-04 currency** → **residual**: `GovernedDimensionLimit`에 currency 독립 필드 부재(`unit`만) — 독립
  변조 불가. §378 residual 등재(MINOR 채택).
- **SPG-07 overflow/underflow** → **residual**: Decimal 임의정밀이라 float-overflow 부재; "안전 범위 초과"
  Expected는 **Verification Profile bound 의존**(P0-1 미승인) ⇒ Expected bound-dependent, fault_count 제외
  (§0.5-4·C2-b).

> **M5 부분 반론(1차 소스 재실측)**: SPG-11(mandatory **dimension** 탈락)은 `profile_within_envelope`
> omit-limb(`predicates.py:213-218`) = **step6 dominance**(ADR:307)이지 step12 "omitted **fields**"
> (ADR:313·SPG-EV-003)가 아니다 — 차원 탈락은 dominance 파괴(SPG-EV-002 "vector dimension" 축). ⇒ SPG-11
> 은 SPG-EV-002 유지. SPG-12(duplicate)만 step12=SPG-EV-003으로 제거. (리뷰 M5를 SPG-12에 채택, SPG-11에
> 재실측 반론. **v1.2 N2**: 리뷰어가 반론 내용은 인용[M5 SPG-11 부분 철회]하되 v1.1의 step 앵커 3건
> [305→306·309→307·315→313]이 전부 오기였음을 실측 — 일괄 정정, 인용-드리프트 재발 기록.)

**정직 종합**: SPG 12 중 8건은 L1 술어 테스트가 거부 커버 — L2는 fault-schedule 프레이밍·otherwise-valid
단일 변조로 재조직(재커버 아님). **L2 고유 실질 = SPG-05·06·08·14**(construction-rejection 실증·**실측
fail-open 봉인**·vector 매핑). **총 카탈로그 = STATE 11 + SPG 12 = 23 fault**(L2-신규 9·L1-인접 14)
(**v1.2 N1 정정**).

---

## 5. L1 하드닝 선행 명세 (L2 실행의 전제 — 코드 수정 명세; 구현은 별도 단계)

C2가 실측한 fail-open과 M4/M8이 지목한 미핀 가정은 **L2 실행 전에** L1 슬라이스 하드닝으로 닫아야 한다
(그러지 않으면 SPG-08 등이 공허-MET 또는 DEVIATION으로 실행됨). 각 항은 **ADR SHALL의 실현**이므로
spg/orthostate 설계와 **강화-충실**(약화 아님)이다.

| id | 하드닝 | 근거(ADR SHALL) | 검증 의무 |
|---|---|---|---|
| **H-1** | `FrozenModel`에 `allow_inf_nan=False` **명시 핀**(pydantic 기본에 의존 금지) + `enforcement_owner` 귀속 주석 | §11 step3:304 "NaN, infinity" | NaN/inf construct → `ValidationError` 회귀 + 뮤테이션(pin 제거 → 테스트 FAIL) KILLED |
| **H-2** | `profile_within_envelope`/`semantic_validation` 비교가 **precision·rounding·boundary 메타 일치**를 검사 + **boundary inclusion 인지 비교**(EXCLUSIVE ⇒ `>=` 거부; INCLUSIVE ⇒ `>`) | §11 step3:304 "precision, rounding ... boundary inclusion"; SPG-AC-002:621 | env=EXCLUSIVE·profile==max ⇒ reject 회귀; 메타 mismatch ⇒ 신규 reason 또는 `UNIT_OR_MULTIPLIER_MISMATCH` 확장; 뮤테이션 KILLED |
| **H-3** | (선택) `_UNIT_METADATA_KEYS` 확장 vs boundary 전용 비교 — spg 설계 #12 §5.2와 정합 노트 필수(reason 어휘 신설 시 ratified set 확장 절차) | §11 step3:304 | reason 어휘 drift-lock |
| **H-4** | canonicalization scheme 조회 실패(`get_scheme`/KeyError)를 **`ArtifactIntegrityError`로 감싸** raw KeyError 탈출 제거 | VER §9.2·구조 fail-closed | ST-07 미등록 version → `ValidationError` 회귀 |

**게이팅**: H-1·H-2·H-4는 **SPG-05/06/08·ST-07의 L2 실행 선행 필수**. 미하드닝 상태로 실행하면 해당 fault
는 DEVIATION(§6.1 `outcome != GREEN`)으로 기록된다 — **삼키지 않는다**. H-3는 H-2 구현 방식 선택지.

---

## 6. 하네스 확장 계약 (`tools/tos_evidence_run.py`)

현 하네스 = "EV-L1 evidence run harness (7 items)"(harness:2)·manifest v1·seed 고정·`never moves a row to
PASS`(harness:26)·`NOT_APPLICABLE_EV_L1`(harness:87). L2는 **additive 확장**.

### 6.1 fault schedule + seed (VER §9.1 append-only)

append-only `fault-timeline.jsonl`(1 라인 1 fault). `observed_disposition`은 **런타임 관측값**이라 설계
문서에 예시하지 않고 `<runtime-observed>` 플레이스홀더로 계약한다(M3 — fabricated 관측 금지). 필드:
`{fault_id, evidence_id, target_component, guard_code_line, fault_kind, seed, input_witness_ref,
expected_disposition, observed_disposition:"<runtime-observed>", outcome:"MET|DEVIATION"}`. **DEVIATION 1건
이라도 outcome ≠ GREEN**(§0.5-2).

### 6.2 manifest v1 → v2 (필드그룹 additive·이름 명시)

> **v1.2 N8 — additive의 정확한 의미**: v2는 v1의 **전 필드를 유지**한다(`verification_profile_version`
> `2.1 (PROPOSED — P0-1 open)`·`register_status_at_run_time`·`note` 포함 — 소실 금지). DISCIPLINE_TAG는
> 신문구로 갱신: "EV-L2 stage execution record only; not a row PASS; L1 hardening prereq + coverage
> argument + P0-1 + independent review remain as stated in claim/coverage_argument blocks."

```yaml
schema: tos-evidence/manifest/v2
evidence_level_stage: EV-L2
prior_stage_runs:                          # [M9] L1 run 바인딩 + baseline 화해
  - run_id: 20260729T054343Z-ea4bee5e
    stage: EV-L1
    sha256sums_digest: <L1 sha256sums.txt digest>   # [M9] L1 아티팩트 폐포 바인딩
    baseline_commit_sha: <L1 baseline commit>       # [M9] baseline 동일성
    reconcile_note: "L1 traceability:2 declared '/2 durable persistence deferred';
      this L2 covers the storage-independent axis only (design §2.2/§2.3)."   # [C1-c]
fault_injection:                           # [신규 필드그룹]
  catalog_ref: docs/plans/2026-07-29-tos-ev-l2-pilot-design.md#3   # (#4 = SPG)
  schedule_artifact: fault-timeline.jsonl
  seed: 0
  fault_count: <per-row>                   # STATE=11 / SPG=12 (v1.2 N1 — 표 실측과 1:1, 자동 재집계 의무)
  all_faults_met: true                     # [C2-c] false거나 Expected-미정의 fault>0 ⇒ GREEN 불가
  l1_hardening_prereq_met: true            # [§5] H-1/H-2/H-4 착지 확인
coverage_argument:                         # [M1] VER §2.7 필수
  boundary_values: "per-dimension boundary combinations exercised (seed-fixed)"
  adverse_scenario_set: "ADR-002-021 PROPOSED (unapproved) — adversarial-combination
    leg UNMET; applicability to non-risk row = OQ; residual per §378"   # [추가조사]
  unexercised_residual_ref: "§378 Residual Risk Register: STATE durable/persisted axis;
    SPG overflow(bound-dependent), currency(no independent field)"
    # [v1.2 N4] §378 인스턴스 레지스터는 현재 **부재**(negative-grep: verification/에 RESIDUAL-RISK-
    # ACCEPTANCE-RECORD-template.yaml만·tos-evidence/에 residual 아티팩트 0) — **레지스터 생성이 선행
    # 작업**. 각 등재는 VER:3293-3306의 12필드 SHALL 전수(risk identity·affected requirement/ADR·scope·
    # credible failure sequence·maximum economic effect·existing controls·detection/containment bound·
    # **owner**·**approver**·expiration/review date·required scope reduction·evidence references) —
    # owner/approver 확보는 P0-3 역할 체계(D1) 경유. 위 3건 ref는 포인터이지 union이 아님(VER:3308
    # "Separate residual risks SHALL NOT be unioned at a consumer" — 각 residual은 독립 등재).
claim:
  closes_evidence_item: false
  minimum_evidence_level: EV-L1/2
  stages_executed: [EV-L1, EV-L2]
  covered_axis: "STATE: representability + non-derivation ONLY (NOT durable);
    SPG: semantic-validation component (post-hardening)"   # [C1-b] '필요충분' 삭제
  independent_review: NOT_SIGNED (VER §9.5)
  p0_1_bounds_approval: OPEN
```

**M9 수용 조건 명문화**: `baseline_commit_sha`가 L1과 다르면 → **L1 stage 재실행 후 L2**(PTF cross-proof
동형; baseline 이동 시 L1 증거 진부화). **M2 baseline 노트 갱신(삭제 아님)**: `EV-L2 component-fault; VER §3
22-field 미충족 목록 + 사유 유지(NOT_APPLICABLE_EV_L1 → NOT_APPLICABLE_PURE_MODEL_L2); {broker,authority,
recon,human,network,recovery} 부재.` **M2 하네스 canary**: substring 매칭이 아니라 **"§3 미충족 필드 목록이
비어있지 않음"** 구조 검사로 강화 + 하네스 self-test(`tests/tools/test_tos_evidence_run.py`) 갱신(§8.5).

### 6.3 §7 applicable 부분집합

item 1·2·3(fault-timeline 신규)·4·5·13(STATE)·30-34 = ✓. item 6-12·14-29(broker/authority/recon/human/
network/recovery) = **N/A(순수 모델·비전송)**. "as applicable"(VER:258)이 정당화·baseline 노트 명기.

---

## 7. SPG-EV-002 §10 갭 처분 (리뷰 m4 — 유지·리뷰 정확 확인)

**갭 실측**: `test_extra_field_forbidden`(`test_spg_records.py:154-157`)은 `HardSafetyEnvelope(unexpected_
field=1)`만 — **1/5 citizen**. RuntimeSafetyProfile 등 4 citizen extra-field 거부 테스트 **부재**(negative-
grep). 메커니즘은 공유 기반(`records.py:3-8` `extra="forbid"`)이라 존재 ⇒ **코드 fail-open 아닌 검증-레인
갭**. **처분**: "unknown/extension field 추가"는 SPG-EV-002 Injection(1548)에 **없고** SPG-EV-003(1555·+Security)
축이며 construction-time 스키마 불변식(EV-L1 성격)이다. ⇒ **L1 보강**: 신규 parametrized
`test_extra_field_forbidden_all_citizens`(5 IndependentIdArtifact 서브클래스) — 태그 SPG-EV-003 substrate.
**SPG-EV-002 L2 acceptance 미게이트·SPG-EV-003 커버 미주장**(over-scope 금지).

---

## 8. 테스트 스위트 계획

### 8.1 배치
per-package 관행(`tos/tests/{orthostate,spg}/`; `tos/tests/l2/`·`@pytest.mark.l2_fault` **부재** 실측). ⇒
신규 `test_orthostate_l2_fault.py`(ST-*)·`test_spg_l2_fault.py`(SPG-*) + marker `l2_fault` 등록. `tos/tests/
l2/` 단일 트리는 per-package import-closure 관행·co-location을 깨므로 기각.

### 8.2 strategy 재사용
valid witness = 기존 `_orthostate_strategies.py`·`_spg_strategies.py` 재사용, L2는 fault transform만 얹음.

### 8.3 비중복 매핑 (재-거부 금지)

| L2 fault | 인접 L1 노드 | L2 추가분 |
|---|---|---|
| ST-01·02·03 | `composite.py:103·111·141` | fault-schedule 프레이밍만(재-거부 아님) |
| ST-04·08·11 | vocabulary/canonical | 동 |
| ST-05·06·07·09·12 | (없음) | **신규**(component-specific 재구성 fault·양성 canary) |
| SPG-01·02·03·09·10·11·13·15 | test_spg_semantic/dominance | fault-schedule + 단일 변조 |
| SPG-05·06·08·14 | (없음/미실증/fail-open) | **신규 실질** |

### 8.4 뮤테이션 canary 실효성 (플레이북 §3.8)
each fault both-ways: (a) 변조 시 발화, (b) valid witness 정당 통과. **fault 주입 제거 mutant가 테스트를
FAIL시키는지 실측**. SPG-05/06/08·ST-07은 **§5 하드닝 mutant(pin/비교 제거)가 KILLED됨을 실증** — 그
결과가 OQ-1/OQ-2의 경험적 답.

### 8.5 하네스 self-test 갱신
`tests/tools/test_tos_evidence_run.py`에 v2 manifest·fault_injection 필드그룹·coverage_argument·§3-미충족-
목록 canary(M2)·all_faults_met 게이트(C2-c) 검증 추가.

---

## 9. 수용 기준 (축소된 정확한 형태 + 잔여 게이트)

**L2 실행 성립 주장(PASS 아님)**: "STATE-EV-001(·SPG-EV-002)의 EV-L2 component-fault stage가 seed=0 하
결정론적 실행됐고, §3(·§4) 카탈로그 전 fault가 fail-closed Expected를 MET(또는 DEVIATION 기록·처분)했으며,
fault-schedule·manifest v2·sha256 폐포·§5 하드닝 선행 착지가 확인됐다. 이 run은 register row를 PASS로
이동시키지 않는다."

**축별 covered 주장(C1-b — '필요충분' 삭제)**:
- **STATE-EV-001**: **representability + non-derivation 축만**. **durable/persisted 축은 미증거** — VER §2.7
  coverage 미방전 부분으로 **§378 residual 등재**. ⇒ 본 파일럿만으로 evidence 축 **미완**(PASS 부적격).
- **SPG-EV-002**: semantic-validation 컴포넌트 축(§5 하드닝 후). durable 얽힘 없음 ⇒ evidence 축은 **하드닝
  + coverage argument 충족 시** 완결 가능.

**minimum level**: 두 행 = `EV-L1/EV-L2`(1021·1546 재실측; +Security/+Broker/L3 없음 — 존재-대조). staged
규칙(VER:171)상 L1(착지)+L2 필요. **단 STATE의 L2는 durable 축 미방전이라 "L1+L2=필요충분"이 성립하지
않는다**(v1.0 문구 삭제).

**PASS 전 잔여 게이트**:
1. **§5 L1 하드닝**(H-1/H-2/H-4) — SPG-EV-002 L2 실행의 코드-정합 선행.
2. **VER §2.7 coverage argument**(76-78): boundary-value leg 충족 가능; **adversarial-combination leg =
   approved Adverse Scenario Set(ADR-002-021) 필요**. **ADR-002-021 = Status PROPOSED(:3, 미승인)**.
   **v1.2 N9 보수화**: 적용성 **미해소 상태의 기본값은 "적용 간주" = 현재 블로커**(VER §2.4:64-66
   "INCONCLUSIVE blocks the relevant approval gate"·VER:173 "Missing resolution is a blocker and SHALL
   NOT default to the lowest level") — 해제는 소유자가 두 행에 대한 inapplicability를 **명시 정당화
   기록한 경우에만**. 어느 쪽이든 **coverage argument 없이는 universally-quantified L2 주장 미방전**
   (§378 residual). (추가조사 반영.)
3. **STATE durable 축 residual**(§378): persistence 기술 결정(ADR §4:61) + 실 durable EV-L2/L3(STATE-EV-004)
   전까지 미증거. Critical이라 `WAIVED_WITH_RESIDUAL_RISK` 불가(VER:130) — 진짜 gap.
4. **P0-1 bounds/Profile 승인**(OPEN)·**독립 리뷰 서명**(VER §9.5, NOT_SIGNED; 저작⊥리뷰 레인 — 본 저작자·
   L2 구현자 서명 불가).
5. **VER §3 complete-baseline 미충족**(v1.2 N7): VER:109 "A run without a complete baseline is invalid"는
   §7:258과 달리 "as applicable" 조항이 없어 **P0-1·서명과 동급 게이트** — §6.2 baseline 노트가 미충족
   필드 목록·사유를 in-band 유지(M2)하며, 완전 baseline은 해당 아티팩트들의 실체화(ENGINE·live 트랙) 전까지
   구조적 미충족으로 잔존.
6. **DEVIATION run 보존**(v1.2 N6 — OQ-6의 §9 실제 편입): 실패/DEVIATION run 패키지는 **삭제·대체 금지
   보존**(VER §2.2:44-46), 후속 run manifest에 `supersedes_run_id` + 사유 기록 — GREEN으로 삼키지 않음.

⇒ **acceptance = (L1∧L2 실행) ∧ §5 하드닝 ∧ §2.7 coverage(ADR-002-021 승인 의존) ∧ STATE durable residual
해소 ∧ P0-1 ∧ 독립 서명.** 본 파일럿은 이 중 **L2 실행 1건 + §5 하드닝 명세 + residual/coverage 정직
등재**를 담당한다. **STATE-EV-001의 "최초 PASS" 전제는 durable 축 residual로 인해 본 파일럿 범위에서
성립하지 않으며, SPG-EV-002가 상대적으로 청정한 후보다**(하드닝·coverage 선행).

---

## 10. L2/L3 경계 판정 요약 (정직 이연표)

| 축 | **L2 (본 파일럿)** | **L3+ / residual (이연)** | 앵커 |
|---|---|---|---|
| 컴포넌트 | 단일 | 다중 live-path 통합 | VER:148 vs 150-152 |
| **STATE durable/persisted** | **미포함(residual)** | 실 durable 저장·크래시 복원 | ADR §13:197·§4:61·STATE-EV-004 `EV-L3`(1042); §378 |
| STATE 저장-독립 축 | 포함(representability·non-derivation·integrity) | — | VER:1024 |
| SPG semantic 컴포넌트 | 포함(하드닝 후) | — | VER:1549 |
| 실행 모델 | 동기·결정론·seed=0 | 비동기·real timing | VER:152 |
| identity/network | 없음 | real 경계 | VER:152 |
| adversarial/security | 없음 | +Security | STATE-EV-005·SPG-EV-003(1049·1553) |
| unknown/duplicate **field** | 범위 밖 | SPG-EV-003(step12:313) | VER:1555 |
| aggregate formula·overflow | injected/bound-dependent만 | ARE/ADR-002-021·P0-1 bound | ADR-002-021 PROPOSED:3 |

**한 줄**: L2 = 단일 컴포넌트 (역)직렬화·ingestion 경계에서 seed-고정 fault 주입 + 권위 verdict/재구성 검사.
**STATE durable 축·실스토리지·통합·network·adversarial·실 aggregate·overflow-bound 전부 L3+/residual 이연.**

---

## 11. 판단 지점 · Open Questions

- **OQ-1 (M8 실측 닫힘)**: NaN/inf construction 거부 — 리뷰 실측 "pydantic 2.12.5 finite_number 거부(주장
  참)". **그러나 TOS FrozenModel에 `allow_inf_nan=False` 미핀**(pydantic 기본 의존) ⇒ **§5 H-1 명시 핀
  선행**(기본이 미래 변경되면 fail-open). enforcement_owner 귀속. OQ-1은 "핀 필요"로 닫힘.
- **OQ-2 (C2 실측 닫힘)**: precision/rounding/boundary — 리뷰 실측 fail-open(env=EXCLUSIVE·profile==max ⇒
  valid=True·∅). **열린 질문 아님** — §5 H-2 하드닝으로 fail-closed 확정. SPG-08 Expected 확정.
- **OQ-3 (신규·최상위)**: **ADR-002-021 Adverse Scenario Set의 적용성** — VER §2.7이 "adversarial
  combinations of the approved Adverse Scenario Set"을 universally-quantified 주장 최소 요건으로 요구하나
  ADR-002-021은 PROPOSED. 비-risk·비-adversarial인 STATE-EV-001·SPG-EV-002에 Adverse Scenario Set이
  적용되는지 = coverage-argument 소유자 판정. **v1.2 N9: 미해소 기본값 = 적용 간주 ⇒ 현재 블로커**(§9-2;
  해제는 소유자의 inapplicability 명시 정당화 기록으로만).
- **OQ-4 (L2 존재론 — §2 반영)**: 순수 모델 L2의 정당성은 §2.2/§2.3 논증으로 확정(SPG 완전·STATE 부분).
  SPG L1-인접 8/12이 재커버 아님을 §8.3 태그가 관철(v1.2 N1). STATE durable 축 미방전을 §9가 관철.
- **OQ-5**: manifest v2 superset 권고(§6.2) — 하네스 소유자 확인.
- **OQ-6 (M10)**: DEVIATION run 처분 — 실패 run **보존** + `supersedes_run_id` + 사유(VER §2.2) — **§9
  게이트 6으로 편입 완료(v1.2 N6)**. DEVIATION을 GREEN으로 삼키지 않음.

### 11.x 잔여 판단 지점 (오케스트레이터 보고용)
(a) **C1 처분 방향 = 철회**(erratum 아님) — 근거: 설계 #8:320·ADR §13:197·AC-005-1:237이 durable 지시체를
실 저장으로 고정해 in-memory 재정의가 비준 문서와 정면 충돌·증거 오염이므로 약화 정정(erratum)이 아니라
**주장 철회 + 축 분할**이 정답. (b) **fault_count 최종**: STATE 11·SPG 12(총 23; 제외 SPG-04/07/12·ST-10
병합 — v1.2 N1 정정). (c) **L1 하드닝 선행 목록**: §5 H-1(allow_inf_nan 핀)·H-2(precision/rounding/boundary+경계 inclusion)·
H-4(canonicalization scheme wrap)·H-3(선택). (d) **잔여 OQ**: OQ-3(ADR-002-021 적용성 — 미해소 기본값
"적용 간주" 블로커[v1.2 N9])·
OQ-5(manifest 소유자)·STATE durable residual 해소 경로(persistence 기술 결정).

---

## 12. 개정 로그

- **v1.2 (2026-07-29)** — 델타 재검증 **REVISE**(CRITICAL 0·신규 MAJOR 4[N1~N4]·MINOR 5[N5~N9] — 전부
  기계적 정정) 반영, **오케스트레이터 직접 적용**(리뷰어 명시 권고·#20 HAG/#23 CUR 선례): N1 SPG fault
  카운트 11→**12**(신규4·인접8)·총 22→**23**(신규9·인접14) 전 사이트 정정 + manifest `fault_count` per-row
  자동 재집계 의무화; N2 v1.1 신규 ADR §11 step 앵커 3건 오기 일괄 정정(step5 **306**·step6 **307**·step12
  **313** — SPG-11 반론 **내용은 리뷰어 인용**[M5 부분 철회]·앵커만 오류, 인용-드리프트 같은-사이클 재발
  기록); N3 §3 주입-지점 선언 정직 축소(5행 docstring 앵커 자인 + fault-timeline 작성 시 실 가드 라인 실측
  의무); N4 §378 레지스터 **인스턴스 부재** negative-grep 등재 + 12필드 SHALL 전사 + owner/approver 경로 +
  non-union(VER:3308); N5 착지 L1 앵커 `composite.py:112`·`:144` 정정; N6 OQ-6를 §9 게이트 6으로 실제
  편입(DEVIATION 보존+supersedes_run_id); N7 §9 게이트 5 신설(VER §3:109 complete-baseline — "as
  applicable" 없음·동급 게이트); N8 §6.2 v1 전 필드 유지+DISCIPLINE_TAG 신문구 명시; N9 OQ-3 보수화
  ("미해소=적용 간주 ⇒ 현재 블로커" — VER §2.4:64-66·VER:173). 리뷰어 확인분: C1 철회+축 분할 "처방 초과
  이행"·화해 노트 정확·STATE 저장-독립 축 L2 정당·SPG-11 반론 승·회귀 0.
- **v1.1 (2026-07-29)** — 독립 비평 REJECT(C3·M10·m6) 반영, 1차 소스 재실측 후:
  - **C1(철회)**: §2 재작성 — /2 in-memory 재정의 철회, 규범 충돌 명시(설계#8:320·ADR §13:197·AC-005-1:237),
    L2 원리-성립 논증(축 분할·대안 A/B/C), §9 수용주장 축소('필요충분' 삭제·durable residual), manifest
    reconcile_note(C1-c).
  - **C2(fail-open 봉인)**: OQ-2 닫음·SPG-08 fail-closed 확정·**§5 L1 하드닝 선행 명세 신설**·§0.5-4
    "falsifiable Expected만" 규칙·all_faults_met 구조 게이트.
  - **C3(허위 신규 3건)**: ST-01/02/03 L1-인접 재태깅(`composite.py:103·111·141` 실측)·§8.3 이동·§2 비대칭
    재작성.
  - **M1** coverage_argument 필드그룹(VER §2.7)·**M2** baseline 갱신(삭제 아님)+§3-미충족 canary·**M3**
    Expected=`ValidationError(cause=ArtifactIntegrityError)`+observed 플레이스홀더·**M4** ST-07 DEVIATION/
    H-4·**M5** SPG-12 제거(채택)·SPG-11 유지(재실측 반론)·**M6** CPL 선언 제거·ST-10→ST-01 병합·**M7**
    phantom `records.py:201`→`canonical/_base.py:201`·플레이북 앵커 정정(529/598/469)·주입-지점=가드
    코드라인+계약앵커 분리·**M8** OQ-1 실측 닫음+H-1 핀·**M9** prior_stage_runs 바인딩+L1 재실행 조건·
    **M10** DEVIATION 보존.
  - **MINOR/추가조사**: SPG-04 currency residual·SPG-13 플래그 한계 고지·SPG-14 태그 정직·ADR-002-021
    PROPOSED 실측(OQ-3·P0-1급 잠재 블로커).
  - **자기위반 교정**: v1.0이 인용-드리프트(2.C:221)를 재발(부록 B/D·§6.1 sed-재번호 앵커) — 발원 기록.

---

## 부록 A. 실측 인용 대장 (anti-phantom — file:line)

**VER-002-001**: EV-L2 def 146-148·EV-L3 150-152·composite 표기 170-172·§7 as-applicable 256-295(item3=262)·
§8 fault-timeline 314·**§9.1 350**·§9.2 354·§9.5 366·**§2.7 coverage 76-78**·bounded-model 3170·**§378
Residual Risk Register 3291**·WAIVED 금지 130·STATE-EV-001 1019-1024(min 1021·inj 1023·exp 1024)·
STATE-EV-004 `EV-L3` 1042·STATE-EV-005 "+security" 1049·SPG-EV-002 1544-1549(min 1546·inj 1548·exp 1549)·
SPG-EV-003 "+security" 1553·SPG-EV-003 Injection(omit/duplicate/unknown) 1555·staged 규칙 171.

**register CSV**: 372행·STATE-EV-001=91·SPG-EV-002=162·EV-L1/2 no-suffix 2행 둘 다 READY.

**ADR-002-005**: §4 "does not decide the persistence technology" 61·§13 "durable and reconstructable after
crash" **197**·§14 composite 5개 204-212·CPL-1..7 156-162·§17 EV-L1/L2·L3 235·**AC-005-1 "representable
and persisted" 237**. **ADR-002-014**: §11 step3(units/currencies/precision/rounding/overflow/NaN/infinity/
boundary) **304**·step5 **306**·step6 **307**·step12(omitted/duplicated/extension **fields**) **313**(v1.2 N2 정정)·§10 277·SPG-AC-002
621. **ADR-002-021**: **Status Proposed 3**·no-authority 736·register 12행 {NOT_IMPLEMENTED,READY} 미승인.

**orthostate 구현**: CompositeState 5차원 non-Optional `records.py:39-102`(swap 12-15)·NONE≠None
`vocabulary.py:78-79`·string distinctness 19-22·coupling `predicates.py:94·206`·reconstruct_conservative 688·
digest base `_base.py:26-32`. **착지 L1 테스트**: 필드탈락 `composite.py:103`·NONE `:111`·swap `:141`·
classify_record_pair `:200·247`·digest 결정성 `:88·95`.

**spg 구현**: FrozenModel extra="forbid" `records.py:3-8`·GovernedDimensionLimit(unit/multiplier/sign/
precision/rounding/boundary + CanonicalDecimal 107-108) `records.py:87-114`·SemanticValidationResult ∅-seal
138-169·5 citizen 320/396/461/505/551·semantic_validation `predicates.py:353-479`(NaN 주장 366-372·431-434·
unit 425-427·duplicate step12 436-445·cross-field 448)·profile_within_envelope 142-247(비교 `>` **233**·
undeclared 228·omit-limb 213-218)·`_UNIT_METADATA_KEYS=(unit,multiplier,sign)` 350·CanonicalDecimal
`canonicalization.py:134`·scheme KeyError 248. **spg L1 테스트**: `test_extra_field_forbidden`
(HardSafetyEnvelope **만**) `test_spg_records.py:154-157`.

**canonical 기반**: DigestBoundArtifact `_base.py:99`·digest==canonicalize(covered) **201**·issue 215/290·
**ArtifactIntegrityError(ValueError) pydantic wrap 50-55**.

**harness/evidence**: EV-L1 subset(7 items) `tos_evidence_run.py:2·7-8`·never PASS 26·NOT_APPLICABLE 87·
self-test `tests/tools/test_tos_evidence_run.py`. STATE manifest stage EV-L1·seed 30-35·traceability:2 "[…/2
durable persistence deferred]". SPG manifest test_nodes(test_extra_field_forbidden 51).

**부재 (negative-grep)**: (1) RuntimeSafetyProfile-특정 extra-field 테스트 부재. (2) `tos/tests/l2/`·
`@pytest.mark.l2_fault` 부재. (3) overflow/underflow Expected(bound) 부재·`OVERFLOW_UNDERFLOW_NAN_INFINITY`
발화 테스트 부재(docstring 자인 `predicates.py:371-372`).

**플레이북**: 저작자 절 27·§2.A(음극성 is False 156·None-축 157)·§2.B ∅ 186-190·§2.C(anti-phantom 215·
dead-row 220·**drift 221**)·**§6.1 메타 교훈 469**·**부록 B §0.5 529**·**부록 D 극성 598**. **설계 doc**:
orthostate(/2 durable 320·persist 이연 122·137-140)·safety-profile(§5.2 both-ways canary 951-957·§10→
SPG-EV-002/003 474).
