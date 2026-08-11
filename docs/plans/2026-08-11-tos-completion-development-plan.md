# TOS 완주 개발 계획 — 독립 경계 완성 후 root tenant 전환

> **작성일**: 2026-08-11 KST  
> **기준 브랜치 / 커밋**: `mission-critical-trading-operating-system` / `867327e9`  
> **문서 성격**: 비규범 개발 계획. RFC/ADR 비준, ADR acceptance, Evidence `PASS`,
> restricted-live 또는 production authorization을 부여하지 않는다.  
> **현재 권한**: `restricted_live=NOT_AUTHORIZED`, `production=NOT_AUTHORIZED` 유지.  
> **후속 관계**: 이 계획의 TOS 완료 게이트를 통과하기 전에는 root 런타임을 TOS에
> 의존시키지 않는다. 완료 후 root 전체 리팩터링은 별도 실행 계획으로 착수한다.

## 0. 결정 요약

이 브랜치와 워크트리의 최종 목표는 **현재 root 런타임을 점진적으로 고치는 것**이
아니라, 먼저 `tos/` 경계 안의 Trading Operating System을 독립적으로 완성하는 것이다.
그 후 root의 전략·시장 데이터·주문·리스크·운영 코드를 TOS의 첫 tenant로
리팩터링하고, 기존 직접 주문 경로를 스코프별로 폐기한다.

현재 경계 분리는 결함이 아니라 의도된 개발 순서다.

```text
현재                         TOS 완료                     후속 root 전환

root runtime                TOS kernel + runtime         root strategy/content/UI
     ║                            │                                  │
     ║ import 0                   ├─ authority/RCL/evidence           ▼
     ║                            ├─ engine/recovery/egress       stable TOS contracts
tos EV-L1 kernel             └─ broker capability/adapters            │
                                                                       ▼
                                                            legacy direct egress 제거
```

이 계획은 다음 판정을 고정한다.

1. root와 `tos/`의 현행 양방향 import 금지는 TOS 완성 전까지 유지한다.
2. **실서버 사용 여부**와 **경제적 효과가 있는 주문 여부**를 같은 축으로 취급하지
   않는다. `REAL_READ`는 허용 가능한 관측 capability이고 `REAL_ORDER`는 별도 권한이다.
3. KIS MOCK 서버가 제공하지 않는 선물 시세·세션·거래 조건은 공식 명세, 실서버
   GET/WS, mock-derived bound로 확인할 수 있다. 이 관측은 주문 권한을 만들지 않는다.
4. 선물 실주문은 저장소 운영 정책에 따라 영구 차단한다. 계좌 입금이나 실체결을
   TOS 완료 조건으로 요구하지 않는다.
5. TOS 코드 완료와 live authorization은 독립된 상태다. TOS가 완료돼도 권한
   레지스터의 별도 인간 행위 없이는 restricted-live/production으로 전환하지 않는다.

---

## 1. 현재 기준선

2026-08-11 `tools/tos_spec_status.py --check` 기준:

| 항목 | 현재 상태 |
|---|---:|
| RFC-class 문서 | 13 `RATIFIED` |
| ADR | 45 `PROPOSED` |
| Part 1 Evidence | 372: 291 `NOT_IMPLEMENTED`, 79 `READY`, 2 `PASS` |
| Part 2/3 DEV Evidence | 118: 전부 `NOT_IMPLEMENTED` |
| 직접 traceability | 29/30, ADR-002-002 직접 표 누락 |
| Verification Profile | 147/163 값 승인, 16개 null/fail-closed |
| Broker census | 9개 등록, migration row 54개 |
| 제한 라이브 / 프로덕션 | 모두 `NOT_AUTHORIZED` |

구현 기준선:

- `tos/tests`: 8,742개 통과.
- `tests/tos_l3`: 13개 통과. 이는 로컬 복구 모델 테스트이지 EV-L3 `PASS`가 아니다.
- firewall, import-linter, Ruff, spec status, mdBook은 통과한다.
- mypy는 8건 실패하고 Black은 70개 파일의 형식 차이를 보고한다.
- RCL은 순수 모델/술어이며 consensus, quorum, replication, persistence가 없다.
- Evidence Store는 영속 서비스가 아니라 provisional chain이다.
- Engine은 19-step Normal Commitment Flow 중 1·12단계를 직접 구현하고, 권위
  단계에는 stand-in을 사용한다.
- Egress는 synthetic transport만 실행한다. 실 Broker Capability Profile과
  credential/route confinement는 미완료다.

작업트리의 `uv.lock`, `.claude/rules/`, `.mcp.json`, `open-trading-api/`는 이 계획
작성 시점의 사용자 변경/미추적 자료다. `open-trading-api/`는 명세·동작 오라클로
참조할 수 있지만, 별도 채택·provenance·SCI admission 전에는 TOS 의존성이나
canonical broker census로 간주하지 않는다.

---

## 2. 이전 진단의 교정과 유지되는 발견사항

### 2.1 교정: REAL 접속 자체는 결함이 아니다

다음 사용은 의도에 맞고 TOS에서도 지원해야 한다.

- 실 KIS GET을 이용한 잔고·상품·장 상태·거래 조건 확인
- MOCK에 없는 선물 WebSocket/호가를 읽어 VirtualBroker에 공급
- 실서버와 MOCK 서버의 스키마·세션·제약 차이 측정
- 실체결을 요구하지 않는 broker capability probe
- 실체결이 필요한 수치의 mock-derived bound 적용

따라서 Broker Capability Profile은 `MOCK`/`REAL` 이진 플래그가 아니라
**환경 × 작업 클래스 × 경제적 효과**로 모델링한다.

### 2.2 유지: 주문 capability의 암묵적 REAL 폴백은 허용하지 않는다

관측과 주문은 다른 권한이다. `MOCK_ORDER` 요청이 "MOCK 선물 미지원"을 이유로
`REAL_ORDER` endpoint에 전달되는 동작은 관측 보완이 아니라 주문 권한 확대다.
TOS에서는 다음 불변식을 강제한다.

```text
requested_environment == effective_environment
requested_operation_class == effective_operation_class
economic_effect may never increase during fallback
UNKNOWN or unsupported => DENY, never widen
```

### 2.3 유지: 완주 전에 해결해야 할 구현·아키텍처 결함

| ID | 발견사항 | TOS 완료에 미치는 영향 |
|---|---|---|
| TOS-GAP-001 | `CandidateConstruction.conformance_result=None`이 egress 검증에서 `AttributeError` 발생 | 구조적 DENY와 증거 기록을 우회하므로 완료 전 수정 |
| TOS-GAP-002 | 실 transport는 `tos/` 밖 주입인데 모든 외부 Python의 `tos` import도 금지 | 운영 shell/composition root를 정의하는 경계 개정 필요 |
| TOS-GAP-003 | RCL·Safety Authority·IAP·AFG·ARE가 stand-in 또는 순수 술어 | 19-step의 권위 경로가 실제로 존재하지 않음 |
| TOS-GAP-004 | durable Evidence Store, SEND_STARTED durability, recovery/reconciliation runtime 부재 | crash 후 potentially-live 상태를 닫을 수 없음 |
| TOS-GAP-005 | KIS Broker Capability Profile의 실측·VERIFIED 차원과 P0-2 bounds 미완료 | 실제 broker-consuming 경로 승인 불가 |
| TOS-GAP-006 | traceability 29/30, mypy 8건, Black 70개, required CI 여부 미증명 | acceptance 입력물과 변경 방어선 불완전 |
| TOS-GAP-007 | 1,000~1,600줄 모듈과 180~297줄 함수 다수 | 안전 코드 리뷰·mutation 격리·소유권 경계 약화 |
| TOS-GAP-008 | root 상태/로드맵과 TOS 생성 상태의 시점·진입점 불일치 | 운영자가 완료도와 권한 상태를 혼동할 수 있음 |

---

## 3. 완료 상태의 정의

`TOS 완료`를 하나의 모호한 플래그로 만들지 않고 네 상태로 분리한다.

### G1. `TOS_CODE_COMPLETE`

- Normal Commitment Flow 19단계에 non-authoritative stand-in이 없다.
- 모든 권위 actor와 durable state owner가 실제 구현으로 연결된다.
- synthetic, VirtualBroker, broker-consuming transport가 동일한 검증 경계를 사용한다.
- 정상·거부·UNKNOWN·crash 경로가 모두 evidence를 남긴다.
- root와의 통합 없이 독립 패키지/프로세스로 실행 가능하다.

### G2. `TOS_VERIFIED_NONLIVE`

- 필수 Evidence row가 규정된 EV-L1~L4 단계에서 실행·독립 리뷰된다.
- 아직 실행할 수 없는 항목은 임의 `PASS`로 바꾸지 않고, 규범 문서가 허용하는
  상태와 근거를 기록한다. 새로운 상태 vocabulary가 필요하면 먼저 VER/RFC를 개정한다.
- synthetic 및 VirtualBroker 기반 end-to-end, restart, partition, clock fault,
  partial-fill, unknown-finality, replay 검증을 통과한다.

### G3. `TOS_TENANT_READY`

- root가 소비할 versioned contract, migration protocol, rollback protocol이 동결된다.
- 동일 계좌·스코프에서 legacy/TOS 두 주문 경로가 동시에 활성화되지 않도록 generation,
  credential, queue, network-route fencing 계약이 검증된다.
- 이 상태가 root 리팩터링 실행 계획의 유일한 시작 조건이다.

### G4. 권한 상태

- `restricted_live`와 `production`은 G1~G3에서 자동으로 바뀌지 않는다.
- 선물 `REAL_ORDER`는 G1~G3 완료 후에도 `POLICY_BLOCKED` 의미를 유지한다. 이를
  Evidence 상태 vocabulary로 임의 추가하지 말고 capability/policy artifact와
  authority register에서 표현한다.
- 주식이나 향후 허용된 다른 스코프의 live 진입은 별도 권한 행위와 해당 scope의
  Evidence `PASS`가 있을 때만 검토한다.

---

## 4. 목표 아키텍처와 경계 결정

### 4.1 보존할 커널 경계

현재 `tos/src/tos`의 순수 커널 성질은 유지한다.

- ambient env, credential, wall clock, network, 동적 import 금지
- frozen artifact와 explicit injected input
- UNKNOWN은 제한 방향
- authority와 evidence의 분리
- backtest/paper/runtime이 같은 결정 코어와 19-step 순서를 공유

### 4.2 새로 필요한 운영 shell

TOS를 실제로 운영하려면 kernel과 root 사이가 아니라 **kernel과 TOS-owned runtime
shell 사이**에 명시적 composition 경계가 필요하다. 첫 구현 작업은 다음 두 안을
비교하는 ADR이다.

| 안 | 구조 | 장점 | 비용/위험 |
|---|---|---|---|
| A. TOS 경계 안의 별도 `tos-runtime` distribution | runtime만 `tos` import 허용; root는 계속 금지 | 커널 hermetic 보존, network/persistence 격리, 독립 배포 용이 | 현 R-역방향의 좁은 예외와 별도 패키징 필요 |
| B. process/IPC 완전 분리 | 양쪽 import 0; schema/digest로만 통신 | failure domain과 자격증명 격리 최강 | IPC 소유권·durability·schema migration 복잡도 증가 |

**권고 기본안은 A**다. 예를 들어 filesystem은 `tos/runtime/`, import distribution은
`tos_runtime`으로 두어 root와 분리된 TOS 제품 경계 안에 유지할 수 있다. 최종 이름과
배치는 boundary ADR이 결정한다. 허용 예외는 TOS-owned runtime composition root
하나로 닫고 다음 방향만 허용한다.

```text
root ─X→ tos kernel
root ─X→ tos runtime       # G3 전까지
tos kernel ─X→ tos runtime
tos runtime ───→ tos kernel
tos runtime ───→ approved persistence/network adapters
```

runtime shell은 적어도 다음을 소유한다.

- RCL persistence/consensus/fencing
- Safety Authority epoch와 leader/writer fencing
- durable Evidence Store와 transactional outbox/inbox
- Trustworthy Time 및 currentness quorum
- IAP, ARE, AFG 실행 서비스
- Recovery Coordinator, Reconciliation, post-trade finality
- credential-isolated Broker Adapter와 Egress Gateway composition
- configuration/profile/release admission
- authority-neutral telemetry와 operator projection

경계 ADR이 승인되기 전에는 네트워크 코드를 `tos/` 커널 안에 임시로 넣지 않는다.

---

## 5. Broker 환경·작업 capability 모델

### 5.1 필수 타입 축

`is_mock: bool` 하나로 라우팅하지 않고 다음 축을 독립된 enum/artifact로 만든다.

| 축 | 예시 |
|---|---|
| `BrokerEnvironment` | `SYNTHETIC`, `KIS_MOCK`, `KIS_REAL` |
| `OperationClass` | `MARKET_DATA_READ`, `ACCOUNT_READ`, `CAPABILITY_PROBE`, `ORDER_SEND`, `CANCEL_REPLACE` |
| `EconomicEffect` | `NONE`, `BROKER_RESOURCE_ONLY`, `POSITION_OR_CASH` |
| `AssetScope` | `STOCK`, `FUTURES` |
| `AuthorizationClass` | `NON_AUTHORIZING_READ`, `MOCK_ORDER`, `REAL_ORDER` |

### 5.2 허용 행렬

| 사용 사례 | Endpoint | 주문/경제 효과 | TOS 정책 |
|---|---|---|---|
| synthetic backtest/fill | synthetic | 없음 | 허용, non-authoritative |
| 선물 paper + 실호가 | KIS REAL GET/WS + VirtualBroker | 실주문 0 | 허용, read credential만 |
| MOCK 주식 주문 검증 | KIS MOCK | mock broker resource | profile/evidence 충족 시 허용 |
| MOCK에 없는 조건 측정 | 공식 명세 또는 KIS REAL GET | 실주문 0 | 허용, probe manifest 필수 |
| 선물 실체결 필요 bound | 없음 | 실주문 필요 | 실체결하지 않고 mock-derived bound 사용 |
| 선물 REAL 주문 | KIS REAL order endpoint | 실제 포지션/현금 | 영구 차단 |

### 5.3 라우팅 불변식

- endpoint 선택은 호출자 문자열이나 ambient env가 아니라 승인된 Capability Profile의
  exact tuple로 결정한다.
- read credential과 order credential은 다른 principal·secret·network policy를 쓴다.
- read-only 프로세스에는 order method 자체를 노출하지 않는다.
- MOCK 미지원은 `UNSUPPORTED`/DENY다. 같은 요청을 REAL order endpoint로 재작성하지 않는다.
- probe는 `emits_orders=false`, 허용 HTTP method/TR ID, 데이터 보존 범위, TTL,
  provenance를 manifest에 기록한다.
- 실시장 조회 결과도 freshness, source continuity, session, instrument scope를 Capsule에
  봉인한 뒤에만 의사결정 입력으로 사용한다.

---

## 6. 실행 단계

### Phase 0 — 완료 계약과 기준선 봉인

**목표**: 구현량이 아니라 완료 판정을 먼저 기계화한다.

작업:

1. 본 계획을 입력으로 `TOS-COMPLETION-STATUS` 생성 규칙을 설계한다.
2. 490개 현재 Evidence row를 package/runtime/test/fault/reviewer owner에 재매핑한다.
3. ADR-002-002 직접 Traceability table을 추가해 30/30을 복원한다.
4. `CURRENT-STATUS`, Architecture Gate, Verification Profile, migration register 간
   count와 authority 축을 하나의 checker로 검증한다.
5. 오래된 package docstring의 P0-1/P0-3 표현을 현재 profile 상태와 맞춘다.

종료 조건:

- source traceability 30/30
- phantom owner/row 0
- completion state가 authority state를 변경하지 않는 회귀 테스트
- current status 생성 결과와 문서 진입점 일치

### Phase 1 — 커널 결함 제거와 품질 hard gate

**목표**: runtime 확장 전에 현재 EV-L1 기반을 정적·동적 검사 모두 green으로 만든다.

작업:

1. `CandidateConstruction`의 command/conformance/numerical result 결합 validator 추가.
2. malformed construction이 예외가 아니라 UNKNOWN/DENIED와 `SEND_REFUSED` evidence로
   귀결되는 테스트 추가.
3. potentially-live projection 이후 모든 예외에 대해 reservation/evidence 불변식 검증.
4. mypy 8건을 실제 결함과 narrowing 문제로 분리해 0건으로 만든다.
5. Black baseline 70개를 별도 기계적 커밋으로 정리한다.
6. 대형 모듈과 함수에 configurable budget을 도입하고, 기존 초과분은 owner·분해
   순서·만료일이 있는 예외 register로 관리한다.
7. CI required job에 firewall, import-linter, TOS tests, tool tests, L3 tests, Ruff,
   Black, mypy, status checker, mdBook을 포함한다.

종료 조건:

- focused regression + 전체 `tos/tests` green
- Ruff/Black/mypy 0
- 미등록 budget exception 0
- GitHub branch protection에서 TOS gate required 상태 증거 보존

### Phase 2 — runtime shell과 권위 기반 구현

**목표**: 순수 술어를 실제 authority-owning runtime으로 승격한다.

선행 결정:

1. composition boundary ADR(A/B안)
2. RCL storage/consensus/fault model ADR
3. Evidence Store durability/retention/backup ADR
4. workload identity, key rotation, credential custody ADR

구현 순서:

1. Trustworthy Time + generation/epoch service
2. durable Evidence Store + append/commit receipt + outbox
3. linearizable RCL + writer fencing + reservation lifecycle
4. Safety Authority + Independent Approval
5. Aggregate Risk Authority + Action Flow Governor
6. currentness/quorum and release-admission

각 서비스는 정상 API보다 먼저 다음 fault contract를 구현한다.

- stale epoch writer
- duplicate command / same ID different bytes
- partition and quorum loss
- crash before/after durable commit
- replay after restart
- clock regression/skew
- evidence store unavailable or partially committed

종료 조건:

- stand-in 없이 steps 4, 6~10, 13~14 실행
- kill -9/restart 후 capacity와 attempt가 보수적으로 복구
- quorum/currentness 상실 시 신규 위험과 send가 양성 확인 없이 거부
- authoritative state와 operator projection 불일치가 경보로 표면화

### Phase 3 — 단일 이벤트 코어와 19-step 완성

**목표**: backtest, synthetic paper, broker-consuming 실행이 동일한 ordering과 정책을
사용하도록 한다.

작업:

1. Engine의 19-step sequencer를 실제 Phase 2 actor에 연결한다.
2. durable event inbox/outbox와 deterministic replay를 구현한다.
3. serialized DSL admission, escape closure, Capsule provenance를 완성한다.
4. marketfeed snapshot lineage와 가격·사이징·주문 가격 동일성 계약을 강화한다.
5. partial fill, cancel/replace, no-ack UNKNOWN, timeout, late result를 event vocabulary와
   post-trade finality에 연결한다.
6. backtest fill model을 synthetic/paper 관측치로 calibration하되 deviation budget을
   초과하면 expectancy claim을 금지한다.

종료 조건:

- 19단계 순서 누락·재배열·중복 실행 mutation 0 생존
- 같은 Capsule/정책/seed에서 replay digest 동일
- backtest와 paper가 같은 decision/commit core 사용
- send 결과 유실·지연·역전이 blind resubmit으로 이어지지 않음

### Phase 4 — Broker Capability Profile과 adapter 완성

**목표**: REAL 조회의 합법적 활용을 보존하면서 주문 권한 확대를 구조적으로 막는다.

작업:

1. §5의 enum과 capability tuple을 artifact schema로 구현한다.
2. KIS profile을 `REAL_READ`, `MOCK_STOCK_ORDER`, `SYNTHETIC_FUTURES_ORDER`,
   `REAL_ORDER` scope로 분해한다.
3. 공식 `open-trading-api`, 공식 문서, 내부 `shared/kis`, 통제된 GET probe를 서로
   다른 provenance class로 기록한다.
4. P0-2 10개 broker bound를 실주문 없이 가능한 probe와 mock-derived bound로 닫는다.
5. 17-item final verify의 5개 stand-in과 6개 deferred item을 실제 service/proof로 교체한다.
6. exact outbound bytes, credential principal, endpoint, account, environment, request digest를
   SEND_STARTED 이전에 하나의 불변 tuple로 봉인한다.
7. adapter는 one verified outbound → one result만 제공하고 내부 blind retry를 금지한다.

종료 조건:

- `MOCK_ORDER → REAL_ORDER` 폴백 mutation이 모두 검출됨
- read-only principal로 order endpoint 도달 불가
- futures REAL order capability가 config/env 변경만으로 생성되지 않음
- MOCK 미지원 조건도 evidence/provenance를 가진 read/probe로 측정 가능
- broker-consuming mock 경로가 17-item verify와 durable evidence를 통과

### Phase 5 — 복구·조정·관측·운영 완성

**목표**: 정상 주문보다 실패 후 보수적 복귀를 먼저 운영 가능하게 만든다.

작업:

1. startup recovery barrier와 broker/RCL/evidence 삼자 reconciliation
2. potentially-live, unknown finality, orphan broker order, stale reservation 처리
3. post-trade obligation/finality와 capacity release
4. incident, waiver, protective action, controlled shutdown, re-arm workflow
5. backup/restore, schema migration, key rotation, dependency admission
6. authority-neutral operator state와 alert ownership
7. KST session/calendar, corporate action, rollover, long/short symmetry 시나리오

종료 조건:

- evidence나 broker truth가 불명확하면 자동 re-arm/용량 반환 없음
- 복구 drill에서 duplicate send 0
- operator dashboard가 authority source가 아님을 API와 UI 모두 강제
- 모든 Redis key가 DB 1과 TTL 정책을 따르고, authoritative durability는 선택된
  storage ADR을 따름
- stock swing에 blanket EOD liquidation을 추가하지 않음

### Phase 6 — Evidence 실행과 독립 acceptance 준비

**목표**: 테스트 통과를 Evidence `PASS`로 오인하지 않고, 등록된 절차로 실행한다.

검증 층:

1. EV-L1: deterministic/property/mutation/formal state transition
2. EV-L2: process boundary, dependency, fault injection
3. EV-L3: persistence, restart, partition, stale writer, schema migration
4. EV-L4: controlled operating-server synthetic/VirtualBroker soak와 recovery drill

Evidence package는 최소한 다음을 포함한다.

- git SHA, clean/dirty target digest, build artifact digest
- interpreter/dependency/config/profile/policy versions
- seed/fault schedule와 JUnit 결과
- broker environment/operation/economic-effect tuple
- before/after authority state와 evidence receipt
- 독립 reviewer provenance와 countersign
- claim scope, residual uncertainty, non-authority statement

종료 조건:

- `NOT_IMPLEMENTED` 필수 row 0 또는 규범적으로 승인된 명시적 이연만 존재
- 모든 READY/PASS 이동에 실행 패키지와 독립 review chain 존재
- ADR acceptance 조건이 충족된 ADR만 `Accepted` 후보가 됨
- `CONST-003=INCONCLUSIVE` 등 의도된 보류를 readiness로 번역하지 않음

### Phase 7 — 독립 TOS 완료 선언

**목표**: root를 아직 변경하지 않은 상태에서 G1~G3를 판정한다.

최종 시나리오:

```text
DSL strategy
  -> KIS REAL read or recorded market data
  -> Capsule/currentness
  -> decision + independent approval
  -> ARE/AFG/RCL atomic commitment
  -> order construction + 17-item verify
  -> synthetic or allowed MOCK transport
  -> partial/final result
  -> evidence/reconciliation/post-trade finality
  -> restart and deterministic replay
```

필수 산출물:

- versioned TOS distribution과 SBOM/provenance
- approved non-live verification profile
- KIS capability profiles와 policy-blocked futures REAL order scope
- standalone deployment manifest와 operator runbooks
- recovery/rollback/incident/credential-rotation drill evidence
- root tenant contract와 migration protocol
- 생성형 `TOS-COMPLETION-STATUS`

G1~G3가 모두 충족돼야 root 리팩터링 계획을 활성화한다. 이 선언은 live 권한이 아니다.

---

## 7. root 리팩터링 후속 경계

root 전체 리팩터링은 TOS가 제공할 계약이 고정되기 전에 시작하면 안 된다. 그렇지
않으면 TOS가 기존 런타임 요구에 역제약을 받고 greenfield 경계가 무너진다.

### 7.1 TOS 완료 전 root freeze

- root의 대규모 구조 리팩터링 금지
- TOS 코드의 root import 금지
- 신규 직접 broker-order route 추가 금지
- 예외는 현재 영구 차단 정책을 강제하는 최소 안전 수정, 비밀 유출 수정, 운영 장애
  복구뿐이며 TOS 구현과 같은 변경에 섞지 않는다.

### 7.2 G3 이후 후속 계획의 순서

1. root 코드·entrypoint·queue·credential·broker read/order site 전수 census
2. 순수 계산을 content/DSL/profile로 이동
3. market-data read를 TOS Capsule ingress로 이동
4. strategy/decision/risk path를 shadow tenant로 연결
5. stock과 futures paper를 각각 VirtualBroker/TOS paper 경로로 검증
6. 계좌·asset·action scope별 단일 egress cutover
7. broker finality와 queue drain 증명 후 legacy `OrderExecutor` caller 제거
8. root의 중복 shared/service 코드와 오래된 config/runbook 폐기

동일 계좌·스코프에서 legacy와 TOS order egress를 동시에 켜지 않는다. rollback도
두 경로 동시 활성화가 아니라 generation과 credential route를 원자적으로 되돌리는
방식이어야 한다. 선물 REAL order는 이 후속 리팩터링에서도 활성화 대상이 아니다.

---

## 8. 작업 단위와 커밋 규율

각 구현 단위는 다음 순서를 지킨다.

1. source RFC/ADR/EV와 current gap을 지정한 설계 문서
2. 독립 adversarial review와 disposition
3. 작은 package/runtime slice 구현
4. negative/fault/mutation 테스트
5. 전체 TOS 회귀와 firewall
6. status/register/docstring 갱신
7. 별도 Evidence 실행·review

한 커밋에서 다음을 섞지 않는다.

- 기계적 Black 포맷과 동작 변경
- TOS kernel과 root runtime 리팩터링
- authority policy 변경과 구현
- broker profile 측정값과 측정 도구 변경
- Evidence 결과와 Evidence 하네스 변경

기본 검증 스택:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest tos/tests -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/tos_l3 tests/tools -q -p no:cacheprovider
python tools/tos_firewall_check.py
lint-imports
python tools/tos_spec_status.py --check
ruff check tos/src tos/tests tests/tos_l3 tools
black --check tos/src tos/tests tests/tos_l3 tools
mypy tos/src/tos --ignore-missing-imports --no-error-summary
mdbook build tos-spec -d /private/tmp/tos-completion-book
git diff --check
```

Evidence 실행은 위 개발 테스트와 별개다. 로컬 green을 row `PASS`로 전사하지 않는다.

---

## 9. 중단 조건

다음 중 하나면 해당 phase를 중단하고 상위 설계/권한 단계로 되돌아간다.

- missing/UNKNOWN fact를 기본값으로 메워 send 또는 capacity를 허용
- MOCK/unsupported operation이 REAL order로 폴백
- root가 G3 전에 TOS kernel/runtime을 import
- 두 writer, 두 egress, 두 credential route가 같은 scope에서 활성화 가능
- crash 후 SEND_STARTED 또는 potentially-live 상태를 증명할 수 없음
- evidence harness가 실행 대상·자기 자신·config digest를 보존하지 못함
- reviewer independence 또는 human authority provenance가 불명확
- 실선물 주문/입금을 완료 조건으로 요구
- 상태 문서와 canonical register가 서로 다른 readiness를 표시

---

## 10. 최종 성공 판정

이 계획은 다음 문장이 모두 참일 때 완료된다.

1. TOS는 root 없이 독립 실행·복구·검증된다.
2. 19-step commitment flow에 stand-in과 미소유 durable state가 없다.
3. REAL read는 필요한 시장 사실을 제공하지만 order authority를 만들지 않는다.
4. MOCK 미지원은 측정 가능한 read/probe로 보완되며 REAL order 폴백은 없다.
5. 선물 REAL order는 코드·capability·credential·network 경계에서 영구 차단된다.
6. 등록 Evidence와 ADR 상태가 실제 실행·review 결과만 반영한다.
7. root 리팩터링이 의존할 versioned tenant contract와 rollback protocol이 동결됐다.
8. restricted-live/production은 여전히 별도 인간 권한 행위로만 변경된다.

그 다음 작업은 이 문서를 늘리는 것이 아니라, **TOS tenant contract를 기준으로 root
전체를 리팩터링하는 별도 실행 계획**을 작성하고 스코프별 migration/cutover를 수행하는
것이다.
