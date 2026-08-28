# B-6 — required-capability-set / minimum-live-gate 매핑 제안서 (2026-07-29)

> **문서 성격**: **후보 제안서(candidate proposal)** — P0-2 T4의 선행물(B-6)이다.
> 이 문서는 **어떤 게이트도 닫지 않으며 승인 효력이 없다.** 여기 실린 매핑은
> 운영자(및 독립 리뷰) 승인 대상 *후보*일 뿐이며, 승인되기 전에는 어떤 런타임에도
> 주입되지 않는다. 승인 절차는 P0-2 실행 계획 §T4(`docs/plans/2026-07-29-tos-phase0-p02-execution-plan.md:52-57`).
>
> **규범성**: **NON-NORMATIVE**. 매핑 *규칙*은 ADR-002-004(broker-agnostic)에서 도출했고
> 특정 broker를 명명하지 않는다. KIS는 §6 canary 절(현 INSTANCE 대조)에서만 등장한다.
> 이 문서는 tos-spec/ 로 이동될 수 없고 어떤 RFC/ADR/VER도 이를 규범으로 인용할 수 없다.
>
> **커밋 금지**(작업 지시). anti-phantom: 모든 인용은 실측(grep/read) 후 앵커.

---

## 0. 목적과 요구 표면

설계 #10 §9.2 item 9(`docs/plans/2026-07-25-tos-broker-capability-design.md:1230-1232`)는
"어떤 action_class가 어떤 차원·assurance level·minimum gate를 요구하는지의 승인된 매핑"을
**Phase-0 인간 게이트**로 명시 이연했다 — Phase 1은 이를 하드코딩하지 않고 hypothesis
주입으로 property 검증만 한다(§5.1/§7). 즉 매핑의 *내용*은 코드가 아니라 **승인된 주입
데이터**로 존재해야 한다. 이 문서가 그 주입 데이터의 **후보 초안**이다.

ADR-002-004 §11(`ADR-002-004-Broker-Capability-Requirements-and-Fallbacks.md:588-609`)이
minimum-live-gate 14항을 정의하고, §8(:293-508)이 17 capability dimension을, §9(:516-540)이
5 assurance level을 정의한다. 이 문서는 그 위에서 (a) action-class × dimension × 최소
assurance 매핑, (b) 환경별 층위, (c) `minimum_live_gate_satisfied` 판정 규칙을 제안한다.

---

## 1. 매핑이 실제로 무엇인가 — 기계적 프레이밍 (실측 근거)

중앙 술어 `capability_admissible`(`tos/src/tos/brokercap/predicates.py:118-198`)의 시그니처는

```
capability_admissible(profile, action_class, required: RequiredCapabilitySet | None,
                      *, version_current: bool | None = None) -> Admissibility
```

인데, **`action_class` 인자는 실측상 opaque하다** — 본문 첫 줄 `del action_class`
(`predicates.py:165`, docstring `:156-157` "opaque label ... non-load-bearing")로 즉시
버려진다. 요구 조건은 전부 세 번째 인자 `required`(`RequiredCapabilitySet`)가 운반한다.
`RequiredCapabilitySet`(`tos/src/tos/brokercap/records.py:160-192`)의 4필드:

| 필드 | 타입 | 판정에서의 역할 (predicates.py) |
|---|---|---|
| `required_dimensions` | `frozenset[CapabilityDimension]` | 반드시 authorize되어야 할 차원 집합. **빈 집합 ⇒ 미지정 ⇒ 17차원 전부 @ `LEVEL_4`로 fail-closed** (`predicates.py:175-180`) |
| `required_level` | `AssuranceLevel \| None` | 모든 required 차원에 **동일 적용**되는 최소 level. `None ⇒ PROHIBITED`(`:181-182`) |
| `minimum_live_gate_satisfied` | `bool \| None` | `is not True ⇒ PROHIBITED`(`:183-184`) |
| `approved_fallback_dimensions` | `frozenset[CapabilityDimension]` | 결핍 차원이 **전부** 이 집합에 속하면 `REDUCED`, 아니면 `PROHIBITED`(`:194-198`) |

따라서 **이 문서가 제안하는 "매핑"은 정확히 다음 함수다**:

> **`(action_class, environment) ↦ RequiredCapabilitySet`**

action_class 문자열 자체는 판정에 무관하므로, action-class별 차이는 **오직 주입되는
`RequiredCapabilitySet` 내용의 차이로만** 표현된다. 매핑 승인 = 이 함수의 각 출력값
(차원 집합·level·gate bool·fallback 집합) 승인이다.

추가 입력 `version_current`는 `RequiredCapabilitySet`에 없다 — profile-version producer
`profile_version_current(...)`(`predicates.py:465-498`)가 별도로 공급한다. 매핑은
`required`만 정의하고, `version_current`는 profile 상태에서 런타임에 산출된다. **ADMISSIBLE는
`required`의 모든 조건 + `version_current is True`가 동시에 성립할 때만** 나온다.

`_declaration_authorizes`(`predicates.py:67-110`) 재확인: 차원이 authorize되려면
`status ∈ AUTHORIZING_STATUSES = {VERIFIED, VERIFIED_WITH_RESTRICTION}`
(`vocabulary.py:283-288`), `VERIFIED_WITH_RESTRICTION`는 `restriction_approved is True`
추가 요구, 그리고 `declared_rank ≥ required_rank`(`ASSURANCE_LEVEL_RANK`,
`vocabulary.py:116-122`). 그 외 전부 `False`(fail-closed).

### 1.1 모델 한계 (실측 발견 — 매핑 설계를 제약함)

`required_level`은 **`RequiredCapabilitySet`당 단일 스칼라**이고 루프
(`predicates.py:189-191`)가 *모든* required 차원에 같은 level을 적용한다. 즉 현 모델은
**"차원별로 다른 최소 level"을 표현할 수 없다.** 그러므로 이 매핑은 action-class×environment당
level 하나를 고른다(= 그 클래스가 의존하는 차원 중 **가장 높은 요구를 내는 차원**이 결정하는
binding level). 차원별 차등 level이 미래에 필요하면 그것은 모델 변경 사안이며 본 제안 범위
밖이다(§7 운영자 결정 항목에 이연으로 기재).

---

## 2. 게이트·FQP는 "차원"이 아니다 — 실현 매핑 (anti-phantom)

매핑에서 흔한 함정: §11 게이트나 §15 Final Quantity Proof를 "required dimension"으로
넣는 것. 그러나 `CapabilityDimension`(`vocabulary.py:70-86`)은 **정확히 17멤버**이고
아래 개념들은 그 멤버가 **아니다**. 이들은 하나 이상의 실제 차원(+주입 bound)으로 *실현*된다.

| 개념(§) | dimension 멤버인가 | 어느 실제 차원(+bound)으로 실현되나 |
|---|---|---|
| Deterministic attribution (§5.5:163) | 아니오 | `ORDER_IDENTITY` + `SUBMISSION_IDEMPOTENCY` (모호 시 §13.1 containment) |
| Uncertain-send 행위 (§11.2:593; §12.4:635-646) | 아니오 | `SUBMISSION_IDEMPOTENCY` + 구조적 verdict(`uncertain_send_policy`) |
| Final Quantity Proof (§11.3:594; §15:835-863) | 아니오 | `OPEN_ORDER_QUERY`+`ORDER_HISTORY_QUERY`+`FILL_EVENTS`(+`CANCELLATION` late-event, `BROKER_TIME`) — `fqp_adequate`가 별도 소비 |
| External-activity detection bound (§11.8:599; §16) | 아니오 | polling path(`FILL_EVENTS`/`OPEN_ORDER_QUERY`) + 주입 bound(`external_detection_ok`) — `ACCOUNT_EVENT_PUSH` 부재는 §13.9로 흡수 |
| Credential/egress fencing (§11.10:601; §18) | 아니오(런타임) | `CREDENTIALS_AUTHORIZATION` 차원 + 런타임 enforcement는 +Security(ADR-002-013, not-Phase-1) |

**따라서 매핑 표의 required_dimensions에는 위 개념명이 절대 들어가지 않는다.** 이들은
§11 게이트(→ `minimum_live_gate_satisfied`, §5)와 실제 17차원의 조합으로만 표현된다.

특히 `ACCOUNT_EVENT_PUSH`는 어떤 action class의 required_dimensions에도 넣지 않는다:
§13.9(:737-744)가 bounded-polling 완전 대체를 규정하므로, 그것이 운반할 요구(적시 외부변화
감지, §11.8)는 polling 차원 + 주입 detection bound로 실현된다. push 부재는 결함이 아니라
설계된 대체 경로다.

---

## 3. 매핑 표 — action class × required dimensions × 최소 assurance

### 3.1 action class 분류 (제안 — ADR §8/§12/§15 구조에서 도출)

ADR은 action-class **taxonomy를 고정하지 않는다**(§5.10:181-183은 "action class"를 scope
좌표로만 열거). 따라서 아래 5분류 자체는 **제안(PROPOSED)**이며, 각 분류는 ADR 섹션에 앵커된다.
운영자는 이 taxonomy를 승인/수정할 수 있다(§7 D1).

| 코드 | 정의 | ADR 앵커 |
|---|---|---|
| `READ_ONLY_QUERY` | 상태 변경 없는 읽기(포지션·잔고·미체결·이력). BC-INV-011상 **safety input**으로 취급 | §8.5:346, §8.6:359, §8.10:406, BC-INV-011:231 |
| `ORDER_SUBMIT` | 신규 진입 주문 전송 | §12:611-625 |
| `ORDER_CANCEL` | 기존 주문 취소 | §8.7:370-380, §12.5:648-652 |
| `ORDER_REPLACE` | 정정/수정(replace/amend) | §8.8:382-394 |
| `PROTECTIVE_REDUCE` | reduce-only/close/보호적 청산 — CLASS-C의 "narrow protective action" | §8.9:396-404, §10 CLASS-C:576-578 |

**공통 인프라 집합**(모든 클래스가 요구, 인수분해): `CREDENTIALS_AUTHORIZATION`(§8.15) ·
`RATE_LIMITS`(§8.13) · `SESSION_CONNECTION_MODEL`(§8.14) — 모든 broker 상호작용이 자격증명·
rate·세션을 쓴다. 주문 방출 클래스는 여기에 `MARKET_INSTRUMENT_CONSTRAINTS`(§8.17)를 더한다.

### 3.2 크로스탭 (17 dimension × 5 class)

범례: **C**=required·ADR확정 / **P**=required·제안(강) / **p**=required·제안(근거 미약) /
`fb§13.x`=결핍 시 승인 fallback으로 `REDUCED` 허용(→ `approved_fallback_dimensions` 후보) /
**—**=해당 클래스 불요.

| # | CapabilityDimension | READ | SUBMIT | CANCEL | REPLACE | REDUCE |
|---|---|---|---|---|---|---|
| 1 | `ORDER_IDENTITY` | — | C `fb§13.1` | C | C | C |
| 2 | `SUBMISSION_IDEMPOTENCY` | — | C `fb§13.3` | P | C | C `fb§13.3` |
| 3 | `ACKNOWLEDGEMENT_SEMANTICS` | — | C | C | C | C |
| 4 | `FILL_EVENTS` | — | C `fb§13.4` | C | C | C `fb§13.4` |
| 5 | `OPEN_ORDER_QUERY` | C | C `fb§13.5` | C | C | C |
| 6 | `ORDER_HISTORY_QUERY` | C | C | C | C | C |
| 7 | `CANCELLATION` | — | P | C | C | P |
| 8 | `REPLACE_OR_AMEND` | — | — | — | C `fb§13.7` | — |
| 9 | `REDUCE_ONLY` | — | — | — | — | C `fb§13.8` |
| 10 | `POSITIONS_BALANCES_MARGIN` | C | P | — | P | C |
| 11 | `ACCOUNT_EVENT_PUSH` | — | — `(§13.9 흡수)` | — `(§13.9)` | — `(§13.9)` | — `(§13.9)` |
| 12 | `CORPORATE_ADMINISTRATIVE_EVENTS` | — | 조건부 `fb§13.13` | — | 조건부 `fb§13.13` | 조건부 `fb§13.13` |
| 13 | `RATE_LIMITS` | C | C `fb§13.10` | C | C `fb§13.10` | C `fb§13.10` |
| 14 | `SESSION_CONNECTION_MODEL` | P | C `fb§13.11` | C | C `fb§13.11` | C `fb§13.11` |
| 15 | `CREDENTIALS_AUTHORIZATION` | C | C `fb§13.12` | C | C `fb§13.12` | C `fb§13.12` |
| 16 | `BROKER_TIME` | p | p | P | P | P |
| 17 | `MARKET_INSTRUMENT_CONSTRAINTS` | — | C | — | C | P |

**읽는 법**: 각 클래스 열의 `required_dimensions` = C/P/p로 표시된 차원 집합.
`approved_fallback_dimensions`(승인 시) = 그 열에서 `fb§13.x`가 붙은 차원의 부분집합.
`ORDER_REPLACE`가 가장 무겁다(submit ∪ cancel ∪ overlap 처리) — §13.7 non-atomic replace의
overlap/gap 규율 때문. `PROTECTIVE_REDUCE`는 CLASS-C 축소 경로(§10:576-578)로 별도 취급.

### 3.3 차원별 근거 앵커 (표의 모든 C/P 셀 정당화)

| dimension | 요구 근거(ADR 앵커) | 실현하는 §11 gate | fallback(§13) |
|---|---|---|---|
| `ORDER_IDENTITY` | §8.1:295-306; §5.5:163; CLASS-A "deterministic order attribution":552; canary §5.1:892 | gate1(:592) | §13.1:658-671 → REDUCED/CLASS-B |
| `SUBMISSION_IDEMPOTENCY` | §8.2:308-316; §12.5:650-652; BC-INV-002:195 | gate2(:593) | §13.3:683-689 |
| `ACKNOWLEDGEMENT_SEMANTICS` | §8.3:318-331; §12.3:631-633("weakest state") | — | (weakest-safe 내장) |
| `FILL_EVENTS` | §8.4:333-344 | gate4(:595) | §13.4:691-698(polling) |
| `OPEN_ORDER_QUERY` | §8.5:346-357; BC-INV-004:203; BC-INV-011:231 | gate7(:598) | §13.5:700-707 |
| `ORDER_HISTORY_QUERY` | §8.6:359-368; §15.2 valid window:849 | gate7(:598) | (queries 결합, §13.5) |
| `CANCELLATION` | §8.7:370-380; §15.3 cancel-ack 금지:859 | gate5(:596) | (finality는 fb 불가 — FQP 필수) |
| `REPLACE_OR_AMEND` | §8.8:382-394 | gate6(:597) | §13.7:718-725(overlap/gap) |
| `REDUCE_ONLY` | §8.9:396-404 | — | §13.8:727-735(target-position) |
| `POSITIONS_BALANCES_MARGIN` | §8.10:406-417; §12.1 "current capacity":620; §13.8 confirmed position:733 | gate11(:602) | — (release 증거는 fb 불가, BC-INV-004) |
| `ACCOUNT_EVENT_PUSH` | §8.11:419-428 | gate8(:599, polling 대체) | §13.9:737-744 (요구 자체를 대체) |
| `CORPORATE_ADMINISTRATIVE_EVENTS` | §8.12:430-442 | — | §13.13:775-782 (독립 참조원) |
| `RATE_LIMITS` | §8.13:444-455; §12.1 "budget permits":624; BC-INV-007:215 | gate9(:600) | §13.10:746-754 |
| `SESSION_CONNECTION_MODEL` | §8.14:457-468 | gate9(:600) | §13.11:756-764 |
| `CREDENTIALS_AUTHORIZATION` | §8.15:470-481; §12.1:617; §18.3 read/trade:970 | gate10(:601) | §13.12:766-773 |
| `BROKER_TIME` | §8.16:483-493; §15.4 late-event:867 | (FQP ordering 실현) | — |
| `MARKET_INSTRUMENT_CONSTRAINTS` | §8.17:495-508; §12.1 units/session:623; ADR-002-019 ceiling:510 | — | — |

### 3.4 제안(P/p) 셀의 정직한 근거 명시

ADR가 **직접** "이 action에 이 차원 필수"라고 말하지 않는 셀은 아래뿐이다(나머지는 C):

- **`CANCELLATION`=P on SUBMIT/REDUCE**: §11 gate5(:596)가 cancellation 정의를 *scope 수준*
  live 전제조건으로 요구하므로, 개별 action의 required_dimensions에 넣는 것은 **방어심층**
  ("나갈 수 없는 곳에 들어가지 않는다"). 작업 지시가 주문 제출 계열 필수로 `CANCELLATION`을
  예시한 것과 정렬. 근거는 강하나 "action별 필수"의 문자적 ADR 근거는 gate 수준이라 P.
- **`SUBMISSION_IDEMPOTENCY`=P on CANCEL**: §8.7:377 "whether cancel is idempotent"에서 도출.
  취소 재전송의 idempotency는 명시되나 "필수 차원"으로 못박히진 않음 → P.
- **`POSITIONS_BALANCES_MARGIN`=P on SUBMIT/REPLACE**: §12.1 "current authority and capacity
  capability":620에서 capacity 확인 도출. 사이징엔 필요하나 §11 gate11은 scope 수준이라 P.
- **`BROKER_TIME`=P on CANCEL/REPLACE/REDUCE**: §15.4 late-event window:867 + §8.7 late-event:379.
  finality의 시간 축은 필요하나 dimension-필수의 직접 문구는 없음 → P.
- **`MARKET_INSTRUMENT_CONSTRAINTS`=P on REDUCE**: §8.9:404 "instrument and order-type
  restrictions"에서 도출 → P.
- **`SESSION_CONNECTION_MODEL`=P on READ**, **`BROKER_TIME`=p on READ/SUBMIT**,
  **`CORPORATE...`=조건부**: 근거가 약하거나 instrument 의존. **p/조건부 = ADR근거 미약,
  운영자 재량 셀**(§7 D2 후보).

**발명 최소화 확인**: C 셀 전부 §8.x/§12/§15의 명시 문구 또는 CLASS-A 특성(:552-558)에 앵커됨.
P/p/조건부 셀은 위 목록이 전부이며 각각 근거 강도를 표기했다.

---

## 4. 환경별 층위

`required_dimensions`는 환경 무관(어떤 차원이 그 action에 안전-관련인지는 물리적 사실).
**환경은 `required_level`과 `minimum_live_gate_satisfied`(및 conformance class)를 정한다.**

| 층위 | 상태 | `required_level`(단일, §1.1) | `minimum_live_gate_satisfied` | conformance | live 전송 |
|---|---|---|---|---|---|
| **NLT** — non-live-test | **현 스코프** | `LEVEL_2_CONTROLLED_TEST_VERIFIED`(§9:528-530 sandbox ceiling) | **§6 참조** — 실 profile에선 `False` | CLASS-D | 없음(BC-INV-009:223) |
| **RL** — restricted-live | **미래·참고 초안** | `LEVEL_3_RESTRICTED_PRODUCTION`(§9:540 "normally L3 or L4") | 14 gate 전부 정의 시 `True` | CLASS-B/C | 축소 live |
| **FL** — full-live | **미래·참고만** | `LEVEL_4_CONTINUOUSLY_MONITORED`(§9:536,540) | `True` | CLASS-A | 광범위 live |

### 4.1 NLT (non-live-test) — 현재 유일 활성 층위

설계 #10 §9.2 item 9의 Phase-1 용도는 **런타임 authorization이 아니라 property 검증**
("hypothesis 주입으로 property 검증":1231)이다. 그러므로 NLT 층위에서 이 매핑은
**EV-L2/L3 하네스가 주입하는 `RequiredCapabilitySet` 사양**이다:

- **양성 fixture**: required 차원 전부 `VERIFIED`@`LEVEL_2`, `minimum_live_gate_satisfied=True`,
  `version_current=True` ⇒ `ADMISSIBLE` 도달 가능성 증명(positive 경로가 vacuous 아님).
- **음성 fixture**: 임의 차원을 sub-threshold로 떨어뜨리거나 gate/version을 끄면
  `PROHIBITED`/`REDUCED` — fail-closed 전이 증명(§13.x fallback은 `REDUCED`).
- **실 MOCK_VTS profile**: §6 canary대로 `PROHIBITED`(gate·version·차원 전부 미달).

NLT의 `minimum_live_gate_satisfied`는 **테스트 변수**다(양성 fixture에서 `True`로 세팅해
ADMISSIBLE 분기 도달을 증명; 실 profile에선 `False`). NLT에서 어떤 실 live 전송도 일어나지
않으며, MOCK_VTS가 설령 green이 되어도 REAL_PROD를 authorize하지 못한다(BC-INV-009 +
INSTANCE 분리, KIS draft:99-107). **비-live 스코프는 정의상 CLASS-D이므로 §11 게이트의
"live" 의미는 NLT에 실 적용되지 않는다** — NLT는 검증 사양이지 arming이 아니다.

### 4.2 RL / FL — 미래 참고 초안 (지금 승인 대상 아님)

RL/FL 행은 **참고 초안**이다. live 승인은 **별개 게이트**다: profile activation(§7.3:272-281)·
independent safety review·CLASS 할당은 설계 #10 §9.2 item 10(:1233-1234)상 인간 게이트이고,
brokercap은 자체 승격하지 않는다(§4.1/§5.3). 본 제안의 §7은 **NLT 층위만 지금 승인 요청**하고
RL/FL은 이연 가능으로 표시한다.

---

## 5. `minimum_live_gate_satisfied` 판정 규칙 제안

`predicates.py:183-184`는 이 주입 bool이 `is not True`면 즉시 `PROHIBITED`. 값을 `True`로
세팅하는 **규칙**을 제안한다(값 자체는 승인 주체가 세팅).

### 5.1 규칙 (§11:588-609 verbatim 도출)

> `minimum_live_gate_satisfied(scope) := True` **iff** 아래 14 게이트가 해당 scope에 대해
> **전부 정의(defined)**되어 있고 승인 주체가 이를 확인함. 하나라도 미정의 ⇒ `False`
> (§11:607 "A missing gate results in CLASS-D for the affected scope").

| gate | §11 항목(:592-605) | 본 매핑에서의 실현 |
|---|---|---|
| 1 | deterministic/bounded order attribution | `ORDER_IDENTITY`(+§13.1) |
| 2 | explicit uncertain-send behavior | `SUBMISSION_IDEMPOTENCY` + `uncertain_send_policy` |
| 3 | broker-specific Final Quantity Proof | FQP recipe(§2 실현) + `fqp_adequate` |
| 4 | partial-fill & duplicate-event handling | `FILL_EVENTS` |
| 5 | cancellation crossing-fill behavior | `CANCELLATION` |
| 6 | replace semantics | `REPLACE_OR_AMEND` |
| 7 | open-order & history query completeness limits | `OPEN_ORDER_QUERY`+`ORDER_HISTORY_QUERY` |
| 8 | external-activity detection bound | polling path + 주입 bound(`external_detection_ok`) |
| 9 | rate-limit & session model | `RATE_LIMITS`+`SESSION_CONNECTION_MODEL` |
| 10 | credential & egress fencing model | `CREDENTIALS_AUTHORIZATION`(+런타임 ADR-002-013) |
| 11 | position/balance/margin evidence semantics | `POSITIONS_BALANCES_MARGIN` |
| 12 | capability version & revalidation process | `ProfileVersion`(§7.2) + `version_current` |
| 13 | approved fallback for every unavailable capability | `approved_fallback_dimensions` 충분성 |
| 14 | verification evidence at required assurance level | `required_level` + `_declaration_authorizes` |

### 5.2 게이트와 술어의 중첩 (구조적 belt-and-suspenders)

gate 13·14는 술어가 **호출마다 재검증**한다: gate가 `True`로 표시돼도 per-call로 결핍
차원이 있으면 `PROHIBITED`(gate 13 ↔ `deficient ⊆ approved_fallback_dimensions`,
`:194-198`)·level 미달이면 deficient(gate 14 ↔ `_declaration_authorizes` level 비교).
이는 §10:584 "A class cannot override a failed mandatory dimension"의 구조적 실현 —
**게이트 bool이 per-차원 판정을 덮어쓰지 못한다.** gate bool은 *scope 수준 전제조건*,
술어는 *호출 수준 재확인*.

### 5.3 read-scope 변형 (제안 — 운영자 판단)

§11 14게이트는 **전송(transmission) 지향**이다("No live scope ... approved"). 순수
`READ_ONLY_QUERY`는 전송이 아니므로 전체 14게이트가 과할 수 있다. 두 선택지:

- **(A) 균일 적용**: read도 14게이트 전부 요구(가장 보수적).
- **(B) read-scope 부분집합**: read 관련 게이트만(7·10·11·12·14) 요구.

술어는 `minimum_live_gate_satisfied`를 균일 소비하므로(action_class 무시), (B)를 택하면
read용 `RequiredCapabilitySet`에 read-부분집합 규칙으로 산출한 bool을 주입하면 된다(표현
가능). **본 제안 기본값 = (A) 균일**(fail-closed 편향); (B)는 §7 D3 운영자 결정으로 이연.

---

## 6. 정직 절 (canary) — 현 INSTANCE로는 전 행 PROHIBITED

**매핑 승인은 admissibility를 만들지 않는다.** 실측으로 확인:

현 KIS INSTANCE draft(`docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml`)의
declaration status 분포(grep 실측):

- `VERIFIED`: **0건** · `VERIFIED_WITH_RESTRICTION`: **0건**
- `DOCUMENTED_NOT_VERIFIED`: 18 · `UNKNOWN`: 62 · profile `status: DRAFT`: 4
- `conformance_class: CLASS-D`(:176) · `approvers: []`(:138) · `profile_version: 0.1.0-draft`(:134) ·
  `canonical_semantic_digest / byte_digest: TBD`(:120-121)

`AUTHORIZING_STATUSES = {VERIFIED, VERIFIED_WITH_RESTRICTION}`(`vocabulary.py:283-288`)에
속하는 declaration이 **하나도 없으므로**, `_declaration_authorizes`(`predicates.py:95-110`)는
모든 17차원에서 `False`. 임의 action class의 임의 non-empty required_dimensions에 대해:

**워크드 트레이스** (`ORDER_SUBMIT`, RL 층위 가정 `required_level=LEVEL_3`):
1. `profile is None or required is None`? 아니오 → 통과.
2. `required_dimensions` 비었나? 아니오(§3.2 SUBMIT 집합).
3. `required_level is None`? 아니오(L3).
4. `minimum_live_gate_satisfied is not True`? — 현 profile은 14게이트 미정의(대부분 UNKNOWN),
   CLASS-D(§11:607) ⇒ 규칙상 `False` ⇒ **`PROHIBITED` 즉시 반환(`:183-184`)**.
   (설령 이 게이트를 통과시켜도 다음이 막는다:)
5. `version_current is not True`? DRAFT·digest TBD ⇒ `False` ⇒ **`PROHIBITED`(`:185-186`)**.
6. (설령 4·5 통과해도) 모든 required 차원이 non-authorizing(VERIFIED 0) ⇒ 전부 deficient ⇒
   `deficient ⊆ approved_fallback_dimensions`도 불성립(승인 fallback 0) ⇒ **`PROHIBITED`**.

⇒ **현 INSTANCE에서 5개 action class 전부, 3개 환경 층위 전부 `PROHIBITED`.** NLT 양성
fixture(합성 VERIFIED@L2)만이 test에서 ADMISSIBLE에 도달하며, 이는 실 broker admissibility가
아니다. **status를 올리는 것은 매핑 승인이 아니라 프로브/검증 결과**(P0-2 T2 측정 →
declaration을 `VERIFIED`@요구 level로 승격 + 14게이트 정의 + version 승인)뿐이다.

---

## 7. 운영자 결정 항목

| ID | 결정 | 지금/이연 | 기본 제안 |
|---|---|---|---|
| **D1** | action-class taxonomy 5분류(§3.1) 승인/수정 | 지금 | 5분류 승인 |
| **D2** | 각 클래스 `required_dimensions`(§3.2 C/P 셀) 승인 — 특히 P/p/조건부 셀(§3.4) | 지금 | C 셀 승인·P 셀 승인·**p/조건부 셀은 명시 검토** |
| **D3** | read-scope gate 변형 (A)균일 vs (B)부분집합(§5.3) | 지금 | (A) 균일(fail-closed) |
| **D4** | `minimum_live_gate_satisfied` 14-gate 규칙(§5.1) 승인 | 지금 | 14-gate 규칙 승인 |
| **D5** | 환경→level 바인딩(NLT=L2 / RL=L3 / FL=L4, §4) 승인 | NLT만 지금 | NLT 승인·RL/FL 이연 |
| **D6** | 차원별 차등 level 필요 여부(§1.1 모델 한계) | 이연 | 미필요(단일 level 유지) |
| **D7** | 각 클래스 `approved_fallback_dimensions`(§13 fb 셀) 개별 승인 | 이연 | §13 fallback 각각 §5.3 독립 승인 대기 |
| **D8** | RL/FL 층위 + restricted-live scope 승인 | 이연 | 별개 게이트(item 10) |

**지금 승인 요청 = D1·D2·D3·D4·D5(NLT 부분)** — 즉 "NLT 층위에서 EV-L2/L3 하네스가 주입할
매핑 사양". **이연 = D6·D7·D8 + RL/FL** — live 관련 일체는 별도 게이트.

승인돼도(§6) admissibility는 안 생긴다 — 매핑은 *요구*를 정의할 뿐, *충족*은 프로브/검증
(T2)이 status를 올려야 한다.

---

## 8. 근거 강도 분포 + 개정 로그

**§3.2 크로스탭 등급 분포**(85셀 = 17차원 × 5클래스; 실측 재검산):

- **C (ADR확정)**: **47셀** — §8.x/§12/§15 명시 문구 또는 CLASS-A 특성(:552-558) 직접 앵커.
- **P (제안·강)**: **10셀** — §3.4 목록(CANCELLATION-on-SUBMIT/REDUCE ×2, IDEMPOTENCY-on-CANCEL ×1,
  POSITIONS-on-SUBMIT/REPLACE ×2, BROKER_TIME-on-CANCEL/REPLACE/REDUCE ×3, MARKET-on-REDUCE ×1,
  SESSION-on-READ ×1).
- **p (제안·근거 미약)**: **2셀** — BROKER_TIME-on-READ/SUBMIT.
- **조건부(instrument 의존)**: **3셀** — CORPORATE_ADMINISTRATIVE_EVENTS(SUBMIT/REPLACE/REDUCE).
- **—(불요)**: **23셀**, 그중 `ACCOUNT_EVENT_PUSH` 4셀(SUBMIT/CANCEL/REPLACE/REDUCE)은 §13.9 흡수.
- 등급 합 = 47+10+2+3 = **62 배정셀** + 23 불요셀 = 85. ⇒ 배정셀의 **76%가 ADR확정(C)**,
  발명은 taxonomy(제안) + P(10)/p(2)/조건부(3)에 국한.

환경 층위·게이트 규칙은 전부 **C**: NLT=L2(§9:528-530)·RL=L3(§9:540)·FL=L4(§9:536)·
14-gate(§11:592-605)·gate/술어 중첩(§10:584). ⇒ **매핑 규칙 골격은 ADR확정 우세**,
발명은 taxonomy(제안)와 10+2+3 셀에 국한되며 각각 근거 강도 표기.

### 개정 로그

- 2026-07-29: v0.1 후보 초안 최초 저작(B-6). 근거: ADR-002-004 §5.3/§8/§9/§10/§11/§12/§13/
  §14/§15/§18 실측 · `tos/src/tos/brokercap/{predicates,records,vocabulary}.py` 실측 ·
  설계 #10 §5.1/§9.2 item 9-10 · P0-2 실행계획 §T4 · KIS INSTANCE draft canary(VERIFIED 0 실측).
  **승인 효력 없음** — 운영자 D1~D5(NLT) 승인 + 독립 리뷰(T4) 전까지 주입 금지.
