# 작업 메모 — KIS Broker Capability Profile INSTANCE 초안 (2026-07-29)

> **⚠ 후보(candidate)일 뿐 — P0-2 종결은 운영자/권한자 승인 행위다.**
> 본 메모와 동반 YAML은 Phase-0 게이트 **P0-2**("broker-specific bounds는 승인된
> Broker Capability Profile에서 **MEASURED, not guessed**" — IMPLEMENTATION-PLAN-002
> §1:34; VERIFICATION-PROFILE-002:9–10)의 **선행물**이다. 저작 행위는 게이트를 닫지
> 않는다. 레지스터 행: `docs/plans/2026-07-29-tos-phase0-human-gate-register.md:50`
> (P0-2 — 현재 "**열림**: `broker_capability_profiles: []`·템플릿만 실재·GATE-STATUS:940").
> 승인 조건은 §8에 정리했다.

> **문서 성격(규범성 선언)**: **비규범 작업 메모**. GOV-001의 세 거버넌스 행위(비준 /
> ADR acceptance / live authorization) 중 어느 것도 수행하지 않는다. tos-spec 규범
> 텍스트(RFC/ADR/VER/템플릿/프로파일)를 **변경하지 않았다**. broker-agnostic 원칙
> (project memory `tos-spec-broker-agnostic`; ADR-002-004 line 798; 설계 #10 header:17)
> 상 KIS 고유 사실은 규범 문서에 들어가지 않으며, 본 초안은 **non-normative INSTANCE**
> (ADR-002-004 §21)로만 존재한다.

- **산출물**: `docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml` (신규) +
  본 메모 (신규). 그 외 어떤 파일도 수정하지 않았고 git 커밋도 하지 않았다.
- **방법**: anti-phantom 규율(존재 주장·부재 주장 **양방향** grep, 전 인용 file:line).
  스키마 정합은 실행 검증으로 확인(§4).

---

## 1. 배치 결정 근거

| 질문 | 판정 | 근거 |
|---|---|---|
| 템플릿 위치 | `tos-spec/src/part-1-foundation/verification/BROKER-CAPABILITY-PROFILE-template.yaml` | `find tos-spec -iname "*BROKER*CAPABILITY*"` 실측(book/ 사본 제외 시 원본 1개) |
| 인스턴스 배치 지침 존재? | **부재** | 설계 #10 전문 grep: 배치 위치를 지정하는 문장 0건. header:17이 "배치는 구현 트랙의 non-normative Profile INSTANCE 소관"이라고만 함. 템플릿 헤더에도 지침 없음(템플릿은 주석 0줄) |
| 채택 위치 | `docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml` (신설 디렉터리) | 지침 부재 시 과업 지정 경로. tos-spec 규범 텍스트 **밖**이므로 broker-agnostic 원칙 준수 |
| 모의/실전 분리 방식 | **인스턴스 분리** (한 파일 안 2 YAML 문서) | 템플릿 스키마가 정하는 방식을 따름 — `profile_identity.environment`는 **단일 스칼라**이고 `ProfileKey.environment`(`tos/src/tos/brokercap/records.py:63`)도 단수. scope 필드 방식은 스키마가 제공하지 않음 |

**현상 실측**: `docs/broker-profiles/` 디렉터리는 본 작업 전 **존재하지 않았다**
(`ls` 실측). tos-spec 상태표도 "Broker-specific Capability Profile | **Template only**"
(`tos-spec/src/part-1-foundation/ARCHITECTURE-GATE-STATUS.md:940`). 즉 인스턴스 0개에서
1개(초안)로 가는 첫 문서다.

**MOCK→REAL 비상속 구성**: 문서 2(REAL_PROD)는 문서 1(MOCK_VTS)의 declaration을
하나도 상속하지 않는다. ADR-002-004 §13.14 / BC-INV-009(설계 #10 §6.4) — 샌드박스
증거는 그 자체로 live capability를 성립시키지 않는다. 이는 **누락이 아니라 구성**이다.

---

## 2. 측정 상태 3분류의 의미론과 CapabilityStatus 정합

과업이 요구한 3분류(A/B/C)는 **저작 출처(provenance) 축**이며, brokercap의
`CapabilityStatus`(권한 축)와 **다른 좌표계**다. 둘을 혼동하면 "우리 코드가 X를
한다"가 "broker가 X를 보증한다"로 미끄러진다 — 이번 저작의 핵심 규율이다.

| 3분류 | YAML 표기 | CapabilityStatus로의 사상 | 근거 |
|---|---|---|---|
| (A) CODE-EVIDENCED | `_kis.measurement: CODE-EVIDENCED` | **자동 사상 없음.** 우리 클라이언트 사실은 broker 보증이 아니다. broker 의미론까지 문서/검증된 경우에만 `DOCUMENTED_NOT_VERIFIED` | `vocabulary.py:42-47` — VERIFIED / 승인된 VERIFIED_WITH_RESTRICTION만 live 권한 |
| (B) OFFICIAL-DOC | `_kis.measurement: OFFICIAL-DOC` | `DOCUMENTED_NOT_VERIFIED` + `AssuranceLevel.LEVEL_1_DOCUMENTED` | `vocabulary.py:51`, `:107` — "Level 1 — Documented; not operationally verified" |
| (C) NEEDS-LIVE-MEASUREMENT | `_kis.measurement: NEEDS-LIVE-MEASUREMENT` | `UNKNOWN` + `LEVEL_0_UNKNOWN` | `vocabulary.py:54`, `:106`; BC-INV-001 — 미선언/UNKNOWN은 unavailable |

**AssuranceLevel 상한 고정 판단**: 이 시스템은 수개월간 모의투자로 운영되어 왔다.
그럼에도 전 차원을 `LEVEL_1_DOCUMENTED` 이하로 유지했다. 이유는
`LEVEL_2_CONTROLLED_TEST_VERIFIED`(`vocabulary.py:108`)가 **설계된 통제 시험**을
요구하는데 BC-EV 실행 기록이 0건이기 때문이다(EVIDENCE-REGISTER-002 전 항목
`NOT_IMPLEMENTED` — register 메모:50). "운영해 왔으니 검증된 것"은 정확히
P0-2가 금지하는 추측이다.

---

## 3. 차원별 커버리지 (17 CapabilityDimension 전수 + 템플릿 전용 2키)

### 3.1 MOCK_VTS 문서

| # | CapabilityDimension | 템플릿 키 | status | 측정 상태 | 핵심 근거 (file:line) |
|---|---|---|---|---|---|
| 1 | ORDER_IDENTITY | client_generated_order_id | UNKNOWN | A + C | `executor.py:315-322`, `:386-399` (요청 본문에 클라이언트 식별자 필드 0개), `:335`, `:412` (ODNO = broker 부여) |
| 2 | SUBMISSION_IDEMPOTENCY | submission_idempotency | UNKNOWN | C | dedup 보증 미확인. 우리 측 결함 Q-IDEMP-1/2 (§5) |
| 3 | ACKNOWLEDGEMENT_SEMANTICS | acknowledgement_semantics | DOCUMENTED_NOT_VERIFIED | A | `executor.py:332-338`, `:404-412` (rt_cd/msg1/ODNO 결합 코드) → §8.3:331 최약 해석 |
| 4 | FILL_EVENTS | fill_event_ordering | UNKNOWN | A + C | `executor.py:530-596` (폴링 파생), `:580-582` (누적 스냅샷). push 구독 0건 |
| 5 | OPEN_ORDER_QUERY | open_order_query | DOCUMENTED_NOT_VERIFIED | A | `tr_ids.py:48-50` (선물 전용 TR), `executor.py:562-563` (연속키 미사용) |
| 6 | ORDER_HISTORY_QUERY | order_history_query | DOCUMENTED_NOT_VERIFIED | A + C | `executor.py:546-547` (today/today-1 = **우리 질의 창**, broker 보존기간 아님) |
| 7 | CANCELLATION | cancellation_finality | DOCUMENTED_NOT_VERIFIED | A | `executor.py:598-641`, `:613-627`, `:635` (취소 응답이 새 ODNO 반환) |
| 8 | REPLACE_OR_AMEND | replace_semantics | UNKNOWN | A + C | `executor.py:617` — `RVSE_CNCL_DVSN_CD` 리터럴 전 repo 1건, 값 `"02"`(취소)만. 정정 경로 미실행 |
| 9 | REDUCE_ONLY | reduce_only | UNKNOWN | A + C | `executor.py:386-399` (본문에 플래그 없음); `futures_margin.py:314-315`·`hedge.py:683`는 **로컬 라벨** |
| 10 | ACCOUNT_EVENT_PUSH | account_event_push | UNKNOWN | A(부재) | grep `H0STCNI|H0IFCNI|체결통보` over `shared/ services/ cli/` → **0 hits**. `streaming.yaml:48-49`, `:65-66` (시세 전용) |
| 11 | POSITIONS_BALANCES_MARGIN | position_balance_margin | DOCUMENTED_NOT_VERIFIED | A + C | `client.py:901`/`:935`, `:1023`/`:1059`; `execution.yaml:78-81` (broker↔Redis 조정 로직 존재 = 불일치 관측 정황) |
| 12 | CORPORATE_ADMINISTRATIVE_EVENTS | corporate_actions | UNKNOWN | A(부재) + C | grep `corporate_action|권리락|액면분할` → **0 hits** |
| 13 | RATE_LIMITS | rate_limits | DOCUMENTED_NOT_VERIFIED | **B + C** | 공식 README(정성) + `hard_limits: {}` 의도적 공백 (§5 Q 및 아래 상세) |
| 14 | SESSION_CONNECTION_MODEL | sessions | DOCUMENTED_NOT_VERIFIED | A + C | `websocket.py:433-434`, `:754`; `approval_cache.py:3,10-11,22`; `streaming.yaml:50,52,59-64` |
| 15 | CREDENTIALS_AUTHORIZATION | credentials_and_revocation | DOCUMENTED_NOT_VERIFIED | **B + A** | 공식 "토큰 재발급 - 1분당 1회"; `auth.py:472,583,161,396-410`; `config/kis/auth.yaml:17,20-24` |
| 16 | BROKER_TIME | broker_time | UNKNOWN | A(부재) + C | grep `server_time|broker_time` over `shared/kis/` → **0 hits**. `executor.py:546,449,452` (로컬 시계) |
| 17 | MARKET_INSTRUMENT_CONSTRAINTS | market_and_instrument_constraints | UNKNOWN | A + C | `market_schedule.yaml:9-10,26-27,34-36`·`execution.yaml:149,154,230` = **로컬 설정**. broker 조회 코드 없음 |
| — | (대응 dimension 없음) | account_margin_borrow_and_settlement_constraints | UNKNOWN | C | §6-2 |
| — | (대응 dimension 없음) | command_construction_and_wire_semantics | UNKNOWN | A | `executor.py:315-322,386-399,613-627` (인라인 dict, 정규화·송출관측 없음) |

**MOCK 집계 (17 dimension 기준)**
- CapabilityStatus: `DOCUMENTED_NOT_VERIFIED` **8** · `UNKNOWN` **9** · `VERIFIED` **0** ·
  `VERIFIED_WITH_RESTRICTION` **0** · `UNSUPPORTED` **0** · `CONTRADICTORY` **0** · `EXPIRED` **0**
- AssuranceLevel: `LEVEL_1_DOCUMENTED` **8** · `LEVEL_0_UNKNOWN` **9** · L2/L3/L4 **0**
- 측정 상태(중복 계상 — 한 차원이 2태그를 가질 수 있음):
  **CODE-EVIDENCED 15** · **OFFICIAL-DOC 2** · **NEEDS-LIVE-MEASUREMENT 12**
- 단일 태그 분해: 순수 CODE-EVIDENCED **4**(3,5,7,10) · 순수 NEEDS-LIVE-MEASUREMENT
  **1**(2) · CODE+NLM **10** · OFFICIAL+NLM **1**(13) · OFFICIAL+CODE **1**(15)
- **live 권한 부여 차원 0개.** `VERIFIED`/승인된 `VERIFIED_WITH_RESTRICTION`이 0이므로
  `capability_admissible`는 어떤 action class에도 `ADMISSIBLE`을 낼 수 없다.

**19키 포함 집계**: `DOCUMENTED_NOT_VERIFIED` 8 · `UNKNOWN` 11.

### 3.2 REAL_PROD 문서

| 항목 | 값 |
|---|---|
| `UNKNOWN` / `LEVEL_0_UNKNOWN` | **16** dimension (+ 템플릿 전용 2키) |
| `DOCUMENTED_NOT_VERIFIED` / `LEVEL_1_DOCUMENTED` | **1** — CREDENTIALS_AUTHORIZATION만 |
| 측정 상태 | NEEDS-LIVE-MEASUREMENT **16** · OFFICIAL-DOC **1** |

CREDENTIALS_AUTHORIZATION만 예외인 이유: 근거가 **환경 무관한 공식 문서 진술**
("토큰 재발급 - 1분당 1회 발급됩니다")이지 MOCK 관측의 외삽이 아니기 때문이다.
`direct_worker_access_prohibited: false` 역시 우리 시스템 **구조**의 사실이라 환경에
무관하다. 나머지 16개는 실전 측정 0건이므로 UNKNOWN이 정직한 값이다.

실전 고유 TR 표면(모의에 없음): `futures_order_night_real`(STTN1101U) ·
`futures_cancel_night_real`(STTN1103U) · `futures_inquire_night_real`(STTN5201R) —
`shared/execution/tr_ids.py:40-50`. 야간세션 관련 capability는 **구조적으로**
모의에서 검증 불가.

---

## 4. 스키마 정합 검증 (실행 결과)

`tos/src/tos/brokercap/vocabulary.py`·`records.py` 및 템플릿 YAML 양측에 대해 실행 검증:

```
== MOCK_VTS                              == REAL_PROD
 top-level missing vs template: []        top-level missing vs template: []
 top-level extra   vs template: []        top-level extra   vs template: []
 cap keys missing: []                     cap keys missing: []
 cap keys extra  : []                     cap keys extra  : []
 dims missing vs enum: [] | extra: []     dims missing vs enum: [] | extra: []
 statuses all valid: True                 statuses all valid: True
 model assurance levels valid: True       model assurance levels valid: True
```

- 템플릿 top-level 15키 **전수 일치**(누락 0·잉여 0), capability 19키 **전수 일치**.
- `CapabilityDimension` **17멤버 전수 순회** — 누락 0·잉여 0.
- 사용된 모든 `status` / `assurance_level`이 `CapabilityStatus` / `AssuranceLevel`
  실제 멤버.
- YAML 2문서 모두 `yaml.safe_load_all` 파싱 성공.

**주석 규약**: `_` 접두 키(`_model_view`, `_kis`, `_note`, `_mismatch_ref`)는
인스턴스-로컬 주석이며 템플릿 스키마가 아니다. 현재 repo에서 이 파일(또는 템플릿)을
**파싱하는 로더는 존재하지 않는다** — grep `BROKER-CAPABILITY-PROFILE|broker_capability_profile`
over `tos/ shared/ services/` 결과는 tos 테스트의 **필드명** 매칭뿐이고 파일 로더 0건.
따라서 `extra="forbid"`(`records.py` docstring:3-4) 위반 위험은 현시점 없다. 로더를
만들 때는 `_` 접두 키를 벗겨내는 전처리가 필요하다.

---

## 5. 발견한 quirk 16건

심각도는 **TOS 안전 관점**(fail-open 가능성)이며 운영 버그 판정이 아니다.

### HIGH (6)

| ID | 차원 | 내용 | 근거 |
|---|---|---|---|
| **Q-IDEMP-1** | SUBMISSION_IDEMPOTENCY | 주문 재시도 루프가 `order_no` 확보 시엔 재시도를 멈추지만(`:225-232`), **예외 경로**(타임아웃/네트워크)에서는 order_no 미상인 채 최대 3회 재전송. 전송되었을 수 있는 주문의 blind retry | `executor.py:218`, `:225-232`, `:238-241`; `config/execution.yaml:3-4` |
| **Q-IDEMP-2** | SUBMISSION_IDEMPOTENCY | `_request_json`이 **주문 POST 포함 모든 호출**을 `retry_once_on_token_expiry`로 감싸 동일 본문을 1회 재전송. 판정이 응답 payload 기반이라 "서버 수락 후 만료 응답" 케이스를 배제 못 함 | `executor.py:403`, `:674+`; `auth.py:64-104` |
| **Q-OOQ-1** | OPEN_ORDER_QUERY | 연속조회 키 `CTX_AREA_FK200`/`NK200`을 빈 문자열로 보내고 응답 연속키를 쓰지 않음 → 항상 1페이지. ADR §15.3 금지 근거 `ONE_OPEN_ORDER_QUERY_OMISSION`(`vocabulary.py:267`) 그 자체 | `executor.py:562-563`, `:575-579` |
| **Q-SESS-1** | SESSION_CONNECTION_MODEL | WebSocket이 **평문 `ws://`** (wss 아님). 시세 전용이나 approval_key가 평문 경로로 오감 | `websocket.py:433-434` |
| **Q-CRED-1** | CREDENTIALS_AUTHORIZATION | 템플릿 기본값 `direct_worker_access_prohibited: true`가 현행 시스템에서 **거짓**. 모든 워커가 env로 raw app_key/app_secret 보유. 사실대로 `false` 기재 | `config/kis/auth.yaml:7-8`; `mock_mirror.py:31-33` |
| **Q-MIC-1** | MARKET_INSTRUMENT_CONSTRAINTS | **모의투자에 야간세션 TR이 없다** — order/cancel/inquire 3계열 모두 `*_night_real`만 존재. MOCK→REAL 외삽 금지의 구체적 근거 | `tr_ids.py:40-50`; `executor.py:565-567` |

### MEDIUM (6)

| ID | 차원 | 내용 | 근거 |
|---|---|---|---|
| **Q-OOQ-2** | OPEN_ORDER_QUERY | 조회 창이 today/today-1 2일로 하드 제한 — 날짜 경계를 넘어 살아 있는 주문은 구조적으로 관측 불가 | `executor.py:546-547` |
| **Q-POS-1** | POSITIONS_BALANCES_MARGIN | 잔고 조회에 만료 재시도 래퍼가 있고 broker↔Redis 조정 로직(`auto_track_external`/`remove_redis_only`)이 켜져 있음 = 불일치가 실제로 관측되어 왔다는 간접 증거 | `client.py:967`; `execution.yaml:78-81` |
| **Q-SESS-2** | SESSION_CONNECTION_MODEL | KIS는 표준 WS ping에 PONG하지 않고 자체 PINGPONG(echo) 사용 → client ping을 켜면 정상 연결이 끊김. 그래서 `ping_interval: 0`. 결과적으로 반쪽 연결 감지가 OS TCP keepalive + staleness에만 의존 | `streaming.yaml:52`; `websocket.py:803` |
| **Q-SESS-3** | SESSION_CONNECTION_MODEL | 무한 재연결이 **KIS 계정 차단**을 유발할 수 있다는 운영 지식이 circuit breaker로 코드화(연속 6회 → open; 600초 창 4회 초과 → open). broker 측 제재 임계는 미측정 | `streaming.yaml:59-64`, `:75-78` |
| **Q-CRED-2** | CREDENTIALS_AUTHORIZATION | 인증 계층 circuit breaker가 자격증명 오류와 인프라 오류를 **같은 차단기**로 처리(5회 → 60초 차단) | `config/kis/auth.yaml:20-24`; `auth.py:656` |
| **Q-WIRE-1** | (command_construction) | 숫자 인코딩이 자산군 간 비대칭 — 주식 `ORD_UNPR = str(int(price))`(정수 절단) vs 선물 `UNIT_PRICE = str(price)`(float 문자열). broker 파서 동작 미확인 | `executor.py:321`, `:393` |
| **Q-MIC-2** | MARKET_INSTRUMENT_CONSTRAINTS | 주식에 ATS(넥스트레이드) 전용 TR 4종 + `order-ats` 엔드포인트가 별도 존재하나 `ats_routing.enabled: false`라 실사용 증거 없음 | `tr_ids.py:35-38`; `executor.py:326`; `execution.yaml:110-111` |

### INFORMATIONAL / POSITIVE (4)

| ID | 내용 | 근거 |
|---|---|---|
| **Q-CXL-1** | 취소 응답이 **새 ODNO**를 반환 — 취소는 자체 식별자를 가진 별개 주문. 취소 ack는 원주문 최종수량을 증명 못 함(§15.3 `CANCEL_ACKNOWLEDGEMENT`, `vocabulary.py:266`) | `executor.py:635` |
| **Q-CXL-2** (POSITIVE) | 현행 코드가 취소 후 **재조회**로 체결수량 갱신 — "취소 ack 단독"을 근거로 쓰지 않음. FQP 관점에서 옳은 기존 행위 | `executor.py:511-520` |
| **Q-MIC-3** | 주문유형 코드계가 주식/선물 간 다름(주식 `ORD_DVSN` 00=지정가·01=시장가 ↔ 선물 `ORD_DVSN_CD` 01=지정가·02=시장가). 미지 값은 `"01"`로 **조용히 폴백** — permissive repair 금지 원칙과 충돌 | `executor.py:785-795` |
| **Q-RATE-1** | 같은 repo에 5 req/s(YAML)와 20 req/s(코드 기본값)가 공존. 어느 쪽도 측정된 broker 한도가 아니므로 모순이 아니라 **둘 다 미근거**임을 드러내는 신호 | `streaming.yaml:96`; `execution.yaml:5`; `rate_limiter.py:16`, `:158` |

### RATE_LIMITS `hard_limits: {}`를 비운 판단 (P0-2의 핵심)

흔히 인용되는 "실전 초당 20건 / 모의 초당 2건"을 **기재하지 않았다.**
공식 원전(`github.com/koreainvestment/open-trading-api` README,
`apiportal.koreainvestment.com`)에서 수치를 확인하지 못했기 때문이다.
확인된 공식 진술은 정성적 방향뿐:

> "모의투자 계좌는 REST API 호출 제한이 낮습니다."
> — https://github.com/koreainvestment/open-trading-api/blob/main/README.md

repo의 5/20 req/s는 **우리가 스스로 건 상한**이지 측정된 broker 한도가 아니다.
이 구분을 흐리면 P0-2가 요구하는 "MEASURED"가 "guessed"로 바뀐다.

### 확인된 OFFICIAL-DOC 사실 2건 (전체)

| 사실 | 원문 | 출처 |
|---|---|---|
| 토큰 재발급 빈도 제한 | "토큰 재발급 - 1분당 1회 발급됩니다" | https://github.com/koreainvestment/open-trading-api/blob/main/README.md |
| 모의 REST 호출 제한 < 실전 | "모의투자 계좌는 REST API 호출 제한이 낮습니다." | 동상 |

**미확인으로 남긴 것**: 유량 수치(실전/모의 초당 건수), WebSocket 동시 구독 상한
(repo 주석은 "KIS 제한: 41" — `streaming.yaml:50` — 이나 공식 확인 실패; 커뮤니티
라이브러리에서만 언급되므로 quirk 후보 표기에 그침), approval_key 유효기간
(repo 주석 "~24h" — `approval_cache.py:3,22` — 공식 미확인), 토큰 `expires_in`
공식 값(우리 fallback 86400은 `auth.py:472,583`의 **우리 기본값**), 자격증명 폐기
API/전파 시한.

### 측정 프로시저 제안 (모의투자 서버 실측 — 로컬 확정 불가)

> 프로젝트 규약(project memory `verify-on-paper-server-not-local-cron`)상 이 프로브는
> **모의투자 서버**에서 수행한다. 전 프로브는 `futures_live.enabled: false` 하에서
> 모의 계좌로만 수행하며, 실전 프로브는 ADR-002-025 restricted-live trial 거버넌스
> 승인 후에만 가능하다.

| ID | 대상 | 절차 | 산출 필드 |
|---|---|---|---|
| **P-2** | SUBMISSION_IDEMPOTENCY | 동일 본문 주문을 의도적으로 2회 전송 → `inquire-ccnl`로 ODNO 생성 수 확인. 2건이면 dedup 없음(UNSUPPORTED 확정), 1건이면 전송 간격을 이분탐색해 창 길이 산출 | `deduplication_window_ms` |
| **P-1** | ORDER_IDENTITY | 공식 API 명세에서 주문 요청 필드 전수 확인 → 클라이언트 주문번호 필드 존재 여부 확정 | `status` UNKNOWN→UNSUPPORTED/VERIFIED |
| **P-5** | OPEN_ORDER_QUERY | 주문 수락(ODNO 수신) 시각 t0부터 해당 ODNO가 조회 결과에 나타나는 시각 t1까지 지연을 N≥100회 측정 → max + 마진 | `eventual_consistency_bound_ms` |
| **P-5b** | OPEN_ORDER_QUERY | 연속조회 키를 실제로 사용해 페이지 경계 동작 확인(Q-OOQ-1 해소 전제) | `completeness`, `pagination` |
| **P-8** | REPLACE_OR_AMEND | `RVSE_CNCL_DVSN_CD="01"`(정정) 1회 실행 후 원주문/신주문 ODNO 관계와 중첩 구간 관측 | `mode` (ReplaceSemantics 5값 중 확정) |
| **P-13** | RATE_LIMITS | 이미 존재하는 `KISApiErrorRateTracker`(5분 롤링, Redis 발행 — `shared/kis/error_rate.py:1-8`; `streaming.yaml:110-114`)를 계측기로 사용해 호출률을 계단 상승시키며 429 최초 발생점 탐색. submit/cancel/query별 분리 측정 | `hard_limits`, `scope`, `sustained_and_burst_semantics` |
| **P-14** | SESSION_CONNECTION_MODEL | 동시 세션 수를 1→N으로 늘리며 거부/기존세션 무효화 관측. 구독 심볼을 40→41→42로 올려 실제 상한 확정 | `concurrent_sessions`, 구독 상한 |
| **P-15** | CREDENTIALS_AUTHORIZATION | 토큰 재발급을 1분 내 2회 시도해 거부 응답 코드/메시지 확정(Q-IDEMP-2 상호작용 확인) | 재발급 거부 semantics |
| **P-16** | BROKER_TIME | 응답 헤더/바디의 broker 시각과 로컬 KST의 편차를 세션 전체에 걸쳐 샘플링 | `timezone`, `precision`, skew 상한 |
| **P-11** | POSITIONS_BALANCES_MARGIN | 주문 수락 후 잔고 반영 지연 측정, 체결 스냅샷과 잔고 대조 | `consistency_model` |
| **P-EXT** | external_activity | HTS/MTS로 동일 계좌에 수동 주문 후 우리 시스템의 탐지 지연 측정 | `detection_bound_ms`, `containment_bound_ms` |
| **P-FQP** | final_quantity_proof | 취소 직후~late-event 창에서 교차체결/정정 발생 여부를 반복 관측 | `late_event_window_ms`, §15.4 마커 |

---

## 6. 템플릿 ↔ brokercap 모델 불일치 (수정하지 않고 보고만)

과업 지시대로 **어느 쪽도 고치지 않았다.** 인스턴스는 템플릿 키를 verbatim 재현하고,
모델 관점은 `_model_view` 주석으로 병기했다.

| # | 불일치 | 템플릿 | 모델 | 영향 |
|---|---|---|---|---|
| **6-1** | order type 다중성 | `profile_identity.order_types: []` (리스트) | `ProfileKey.order_type: str \| None` (`records.py:66`, 단수) | 프로파일 키 좌표 수가 달라짐. 모델대로면 주문유형별 **별개 프로파일**, 템플릿대로면 한 프로파일이 복수 유형 커버 |
| **6-2** | capability 키 개수 | **19키** | `CapabilityDimension` **17멤버** (`vocabulary.py:70-86`) | 템플릿 전용 2키(`account_margin_borrow_and_settlement_constraints`, `command_construction_and_wire_semantics`)에 대응 dimension 부재 → 이 2키는 `declaration_for()`(`records.py:365`)로 조회 불가 |
| **6-3** | assurance 어휘 | `EV-L0` | `LEVEL_0_UNKNOWN`..`LEVEL_4_CONTINUOUSLY_MONITORED` (`vocabulary.py:106-110`) | 토큰 자체가 다름. 추가로 템플릿의 `EV-L*`는 evidence-register의 EV-L0..L5 표기와 **같은 문자열 공간을 공유**하는데 축이 다름(assurance level ≠ evidence level) — 좌표 붕괴 위험(설계 #10 §4.4 동형) |
| **6-4** | conformance class 어휘 | `CLASS-D` | `ConformanceClass.CLASS_D_NON_LIVE` (`vocabulary.py:146`) | 하이픈/언더스코어 + 접미사 차이. 문자열 비교로 매칭 불가 |
| **6-5** | capability 키 이름 ≠ dimension 이름 | `client_generated_order_id`, `fill_event_ordering`, `cancellation_finality`, `sessions`, `position_balance_margin`, `corporate_actions`, `credentials_and_revocation`, `market_and_instrument_constraints`, `replace_semantics` | `ORDER_IDENTITY`, `FILL_EVENTS`, `CANCELLATION`, `SESSION_CONNECTION_MODEL`, `POSITIONS_BALANCES_MARGIN`, `CORPORATE_ADMINISTRATIVE_EVENTS`, `CREDENTIALS_AUTHORIZATION`, `MARKET_INSTRUMENT_CONSTRAINTS`, `REPLACE_OR_AMEND` | 9/17이 이름 불일치. 설계 #10 §2.2는 "spec terms = code terms … ADR §8 소절 제목 verbatim"을 주장하는데 코드는 ADR §8을 따르고 템플릿은 다른 명명을 쓴다. **repo 내에 매핑표가 존재하지 않는다**(본 문서 §3.1 표가 최초) |
| **6-6** | 모델에 있고 템플릿에 없는 필드 | — | `CapabilityDeclaration.restriction_approved` (`records.py:108`), `.assurance_sources` (`:110`) | **하중 큼**: `restriction_approved`는 §5.3 line 146의 명시 승인 게이트다. 템플릿만으로 작성된 프로파일은 `VERIFIED_WITH_RESTRICTION`을 권한화하는 **유일한 플래그를 표현할 수 없다** |
| **6-7** | 버전 블록 | `profile_identity`에 `profile_version`/`effective_from`/`expires_at`/`approvers` 산재 | `ProfileVersion` 7필드 (`records.py:81-87`) — `evidence_package_version`, `superseded_version_link`, `change_reason` 부재 | `superseded_version_link` 부재는 append-only 승계 사슬(`records.py:313-317`)을 YAML에서 표현 불가하게 만듦 |
| **6-8** | FQP recipe 스키마 | `final_quantity_proof.recipes: []` — 원소 스키마 없음 | `FinalQuantityProofRule` 4필드 (`records.py:149-152`) | §15.4 마커 2개(`no_later_change_asserted`/`late_event_window_defined`)를 템플릿이 요구하지 않음 → adequacy 판정 불가능한 recipe가 작성될 수 있음 |
| **6-9** | live_scope 필드 집합 | 12필드 (accounts/venues/market_segments/instruments/session_phases/order_types/time_in_force_values/action_classes/maximum_concurrency/maximum_quantity/maximum_risk_vector/manual_activity_policy) | `LiveScope` 8필드 (`records.py:125-132`) | 교집합은 `action_classes` **1개뿐**. 특히 모델의 `reduced_off_unattended_partition_protection`(§13.15 게이트, `partition_class_scope_ok` 입력)에 대응 템플릿 필드가 **없다** |
| **6-10** | 식별/증거 참조 | `artifact_id`, `verification.evidence_digest` | `profile_id` (독립 id, `records.py:351`), `evidence_package_ref` (`:360`) | 대응 관계가 명시되지 않음. 모델은 `id != f(digest)`를 의도적 설계로 삼는데(`records.py:306-317`) 템플릿의 `artifact_id`/`byte_digest`/`canonical_semantic_digest` 3자 관계는 미정의 |

**추가 관측(부재 실측)**: 템플릿 YAML에는 주석이 **0줄**이고, 인스턴스 작성 지침·
필수/선택 구분·enum 허용값 목록이 없다. 위 10건 중 6-6/6-8/6-9는 "템플릿만 보고
작성한 프로파일이 모델의 안전 게이트를 표현하지 못한다"는 같은 결함 클래스다.

---

## 7. 미결 항목 — 설계 #10 Phase-0 매핑

설계 문서 #10 §9.2(`docs/plans/2026-07-25-tos-broker-capability-design.md`)의 Phase-0
이관 항목 중 본 초안과 직접 관련된 것들:

| 설계 #10 항목 | 라인 | 본 초안에서의 상태 | 필요한 판단 |
|---|---|---|---|
| **item 3** — Broker Capability Profile INSTANCE bound family 값·키 승인 (rate/admission budget·polling detection bound·late-event/correction window·evidence freshness/expiry/revalidation) | `:1213-1216` | **전부 미충족.** `hard_limits: {}`·`eventual_consistency_bound_ms: null`·`late_event_window_ms: null`·`detection_bound_ms: null`·`containment_bound_ms: null`·`revocation_bound_ms: null`·`expires_at: null` | §5의 P-13/P-5/P-FQP/P-EXT 프로브 실행 → **Bounds-Approver**(≠ Live-Armer) 승인. 기존 `B_external_activity_detect`/`_contain`·`B_egress_hard_fence` 키와 cross-ref |
| **item 4** — 한 broker의 실제 capability 값·status·assurance·conformance class 할당 | `:1217-1219` | **본 문서 전체가 이 항목의 후보 산출물.** 17차원 전수 선언, 단 VERIFIED 0건 | 운영자/권한자가 (a) 각 차원 status·assurance 확정, (b) 프로파일 승인(`approvers` 채움), (c) `status: DRAFT`→활성 전이 |
| **item 4 부속** — §13.15 partition-protective-class에 KIS가 포함되는지 | `:1220` | **미판정.** `LiveScope.reduced_off_unattended_partition_protection: null`(fail-closed). 템플릿에 대응 필드 부재(§6-9) | KIS가 무인 분단 시 자율 보호를 제공하는지 판정 → 아니면 scope 축소 또는 CLASS-C/D 분류 |
| **item 9** — required-capability-set / minimum-live-gate 정의 | `:1230-1232` | **미작성.** 어떤 action class가 어떤 차원·assurance level·minimum gate를 요구하는지의 승인된 매핑이 없다. `RequiredCapabilitySet`(`records.py:189-192`)은 주입 모델이고 빈 집합은 "17차원 전부·최고 level"로 fail-closed 해석됨(`:180-181`) | action class 목록 확정 → 차원×level 매핑 승인. 이것 없이는 프로파일이 승인돼도 admissibility 질의를 만들 수 없다 |
| **item 10** — conformance class 승인 + restricted-live scope 승인 | `:1233-1234` | **CLASS-D 고정**(두 문서 모두). 자체 승격 금지 원칙대로 초안이 스스로 올리지 않았다 | profile activation + independent safety review + CLASS 할당은 인간 게이트. §10 line 584 "A class cannot override a failed mandatory dimension" 준수 필요 |
| **item 11** — cross-package 좌표 조정 의무 | `:1235-1238` | **본 초안은 위반하지 않으나 위험 노출.** `_model_view.status`는 `CapabilityStatus` 토큰이고 orthostate `KnowledgeState`/recon `FieldConfidenceClass`/capsule `FieldState`와 `UNKNOWN` 토큰을 공유한다. YAML은 타입 없는 문자열이므로 **로더가 생기는 순간** 축 붕괴 경로가 열린다 | 프로파일 로더를 만들 때 4축을 반드시 **별개 typed 필드**로 파싱(공유 raw-string slot 금지). §6-3의 `EV-L*` 이중 의미도 같은 결함 클래스 |

### 7.1 추가 미결 (본 초안이 발견해 올림)

| # | 항목 | 이유 |
|---|---|---|
| **U-1** | canonicalization / digest 알고리즘 | `canonicalization_version`·`canonical_semantic_digest`·`byte_digest` 전부 TBD. 설계 #10 §9.2 item 2(G2 게이트) 미결이라 **산출 자체가 불가**. 프로파일 승인 전 필수 |
| **U-2** | 프로파일 인스턴스 배치 규약 | 본 초안이 `docs/broker-profiles/`를 신설했으나 이는 지침 부재 하의 선택이다. 정식 규약(경로·명명·버전 파일 분리 여부) 확정 필요 |
| **U-3** | 템플릿↔모델 정합 (§6 10건) | 어느 쪽을 정본으로 삼을지의 판단. 특히 6-6(`restriction_approved` 부재)은 템플릿 패치 없이는 `VERIFIED_WITH_RESTRICTION` 경로가 YAML에서 표현 불가 — GOV-001 change process 대상 후보 |
| **U-4** | 세션 좌표 분리 필요 여부 | 실전 야간세션(18:00-05:00)은 `ProfileKey.session_type`이 다르고 모의에 대응이 없다(Q-MIC-1). 야간용 **제3 프로파일**이 필요한지 판정 |
| **U-5** | 주식 경로 capability 공백 | 주식 미체결조회·취소 경로가 repo에 **부재**(실측). 주식 CANCELLATION/OPEN_ORDER_QUERY는 UNKNOWN이며, 주식 live scope는 FQP recipe 없이 승인될 수 없다 |
| **U-6** | Independent-Reviewer 실체 | 본 초안 저작자(AI)는 IMPLEMENTATION-PLAN-002 §3상 리뷰어가 될 수 없다. register의 **D1** 결정(레지스터 메모:287-294)에 종속 |
| **U-7** | Q-IDEMP-1/2 처분 | 두 재시도 경로는 현행 운영 코드다. 프로파일이 이를 residual risk로 **수용**할지, 코드 수정을 선행 조건으로 걸지의 판단. (본 초안은 수용/수정 어느 쪽도 결정하지 않고 RR-1로 기록만 함) |

---

## 8. P0-2 종결 조건 (체크리스트 — 전부 인간 게이트)

- [ ] §5 프로브 12건 실행 → 측정값 기록 (모의투자 서버, `futures_live.enabled: false` 하)
- [ ] `hard_limits` 등 bound family 값 확정 → **Bounds-Approver** 승인 (설계 #10 :1213)
- [ ] U-1 canonicalization 결정 → digest 3필드 산출
- [ ] U-3 템플릿↔모델 불일치 처분 (특히 6-6)
- [ ] 차원별 status/assurance 확정 → **VERIFIED 승격 여부** 판정 (:1217)
- [ ] required-capability-set / minimum-live-gate 매핑 승인 (:1230)
- [ ] conformance class 할당 + restricted-live scope 승인 (:1233)
- [ ] independent safety review (저작자 배제 — U-6)
- [ ] `profile_identity.approvers` 채움 + `status: DRAFT` 해제
- [ ] `docs/plans/2026-07-29-tos-phase0-human-gate-register.md:50` P0-2 행을
      "닫힘"으로 갱신 + `scope.broker_capability_profiles` 링크 배선

**현재 상태: 위 10개 항목 전부 미충족. P0-2는 열려 있다.**

---

## 9. 저작 규율 자기점검 (anti-phantom)

- 본 메모와 YAML의 **모든 코드/설정 인용은 grep 후 file:line**으로 기록했다.
- **부재 주장 5건**을 실제 grep으로 검증했다: 계좌 이벤트 push 구독(`H0STCNI|H0IFCNI|체결통보`
  → 0 hits) · corporate action 처리(`corporate_action|권리락|액면분할` → 0 hits) ·
  broker 서버시각(`server_time|broker_time` over `shared/kis/` → 0 hits) ·
  프로파일 YAML 로더(`BROKER-CAPABILITY-PROFILE|broker_capability_profile` over
  `tos/ shared/ services/` → 필드명 매칭만, 로더 0건) · `docs/broker-profiles/` 디렉터리
  부재(`ls` → No such file).
- **존재 주장도 실측**했다: `reduce_only` 토큰은 존재하나 broker 필드가 **아니라**
  로컬 라벨임을 확인(`futures_margin.py:314-315`) — 이름만 보고 capability로 계상하는
  오류를 차단했다. (#27 FD 사이클 교훈: "미검증 존재 주장이 대칭 사각")
- **미확인은 미확인으로 남겼다**: 유량 수치·WS 구독 상한 41·approval_key 24h는
  repo 주석 또는 커뮤니티 소스에만 존재하므로 **값으로 승격하지 않고** quirk 후보
  표기에 그쳤다. pykis/mojito 등 2차 원천은 값 확정 근거로 쓰지 않았다.
- **스키마 정합은 주장이 아니라 실행으로 확인**했다(§4 출력).
