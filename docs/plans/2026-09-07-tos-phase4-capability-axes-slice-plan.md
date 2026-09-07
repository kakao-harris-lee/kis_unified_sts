# TOS Phase 4 슬라이스 #1 — Broker 환경·작업 capability 축 (§5.1) 아티팩트 스키마

- **상위 계획**: `docs/plans/2026-08-11-tos-completion-development-plan.md` §5 (축·허용 행렬·라우팅 불변식) · §6 Phase 4 작업 1
- **운영자 지시 (2026-09-07)**: 「병렬로 Phase 진행 가능하면 바로 착수」 — Phase 4 중 Phase 2 런타임·모의투자 실측에 의존하지 않는 항목만
- **저작**: 세션 모델 단독 · **권한 부여 없음** (이 스키마는 어떤 경로도 열지 않는다 — 닫힌 허용표를 «표현»할 뿐)

## 1. 범위

| 포함 | 제외 (이유) |
|---|---|
| §5.1 축 5종 enum · capability tuple 레코드 · §5.2 허용 행렬의 닫힌 whitelist 술어 · §5.3 라우팅 불변식 중 커널 측 술어 3종 | 작업 3 provenance **데이터** 채움(P0-2 프로브 산출물 결속 — 프로브 게이트) · 작업 4(P0-2 10 bound — 프로브 게이트) · 작업 5(17-item stand-in 교체 — Phase 2 actor 의존) · 작업 6(SEND_STARTED 이전 봉인 tuple — `egressgw/gateway.py` 는 PR #655 리뷰 중이라 머지 후) · 작업 7(adapter 1 outbound→1 result — 설계 #34 §5.4 가 이미 구조 봉인, 별도 검증 슬라이스) |

## 2. 서베이 결과 (2026-09-07 실측)

- `tos/src/tos/brokercap/` 는 ADR-002-004 축자 어휘(`ProfileKey` 10좌표 · `CapabilityDimension` 17 · `ConformanceClass` 등)이며 **§5.1 의 5축·tuple 은 어디에도 없다** (brokercap/venue/egressgw/liveauth 전수).
- `ProfileKey.environment`·`credential_scope` 는 opaque 문자열 좌표(broker-agnostic). §5.1 축은 그 위의 **닫힌 enum 층**이다.
- 핀: `tos/tests/brokercap/test_brokercap_import_closure.py` 형제-엣지-0(liveauth/orthostate/recon/rcl/evidence/capsule/time/authority/dsl 부재 · numpy/pandas/yaml 부재 · clock/os.environ 부재) · `test_brokercap_vocabulary.py:57` `CapabilityDimension==17` 카운트 핀. 신설 enum 은 **별도 모듈**이라 이 핀을 건드리지 않는다.
- Phase 0 완료 계약(BC-EV-003 등)은 편집하지 않는다.

## 3. 결정

1. **모듈**: `tos/src/tos/brokercap/routing.py` 신설 (vocabulary/records/predicates 를 한 파일에 — 100줄 함수·1000줄 모듈 budget 준수). `brokercap/__init__.py` 재-export 는 기존 저작-레벨 잠금 규율대로.
2. **enum 명명은 broker-agnostic**: 계획 §5.1 의 예시 `KIS_MOCK`/`KIS_REAL` 을 커널에 쓰지 않는다 — `BrokerEnvironment = {SYNTHETIC, BROKER_SIMULATION, BROKER_PRODUCTION}`. 브로커 식별은 `ProfileKey.broker_id` 좌표가 이미 담당한다(ADR-002-004 §21 인스턴스 소관). 나머지 4축은 계획 문언 그대로: `OperationClass{MARKET_DATA_READ, ACCOUNT_READ, CAPABILITY_PROBE, ORDER_SEND, CANCEL_REPLACE}` · `EconomicEffect{NONE, BROKER_RESOURCE_ONLY, POSITION_OR_CASH}` · `AssetScope{STOCK, FUTURES}` · `AuthorizationClass{NON_AUTHORIZING_READ, MOCK_ORDER, REAL_ORDER}`.
3. **`CapabilityTuple`** (FrozenModel, 5축 전부 필수 · None 불허): 결합 validator 로 축 간 모순을 구성 시점에 거부 — (규칙 1) `ORDER_SEND`/`CANCEL_REPLACE` 는 `EconomicEffect.NONE` 과 공존 불가, **단 `SYNTHETIC`×`SYNTHETIC_ORDER` 는 예외**(합성 체결은 경제효과 0 이 정의다 — 상위 §5.2 1행) · (규칙 2) `NON_AUTHORIZING_READ` 는 `ORDER_SEND`/`CANCEL_REPLACE` 와 공존 불가 · (규칙 3) `SYNTHETIC` 환경은 `REAL_ORDER`/`MOCK_ORDER` 와 공존 불가 · (규칙 3′) `SYNTHETIC_ORDER` 는 `SYNTHETIC` 환경 밖에서 공존 불가 · (규칙 4) `BROKER_PRODUCTION`+(`ORDER_SEND`|`CANCEL_REPLACE`)+`FUTURES` 는 **표현 불가**(생성 자체 거부 — «영구 차단»은 술어가 아니라 타입 수준 봉인 · 루트 CLAUDE.md 비협상).
   **v1.1 정정(2026-09-07)**: `AuthorizationClass` 에 넷째 멤버 `SYNTHETIC_ORDER`(비권위 합성 체결 · 브로커 자원 0)를 둔다. 상위 계획 §5.1 의 3멤버는 «예시»이고 같은 계획 Phase 4 작업 2 가 `SYNTHETIC_FUTURES_ORDER` 스코프를 명시하므로 이 멤버 없이는 §5.2 1행(synthetic backtest/fill)이 표현 불가였다. 허용 행렬에 1b행 추가: `SYNTHETIC`×{`ORDER_SEND`,`CANCEL_REPLACE`}×`NONE`×{`STOCK`,`FUTURES`}×`SYNTHETIC_ORDER` = ADMISSIBLE(non-authoritative).
4. **허용 행렬 = 닫힌 whitelist** `routing_admissibility(tuple) -> Admissibility`(기존 `Admissibility{ADMISSIBLE, REDUCED, PROHIBITED}` 재사용 · 신규 어휘 발명 금지): §5.2 6행을 tuple 집합으로 옮기고 **목록 밖은 전부 PROHIBITED**(denylist 금지 — 플레이북 §2.E). REDUCED 는 «profile/evidence 충족 시 허용» 행(MOCK 주식 주문)에 쓰며, 충족 판정은 주입 인자 `profile_evidence_ok: bool | None`(True 만 양성).
5. **라우팅 불변식 술어(§5.3)** — 커널에서 표현 가능한 셋만: (i) `endpoint_binding_from_profile_ok(tuple, profile_key)` — tuple 의 환경·자산 축이 `ProfileKey.environment`/`instrument_class` 와 **정확히** 결속(문자열 대응표는 주입 인자, 커널 상수 아님 · 결속 부재 = False) (ii) `credential_principal_separation_ok(read_principal, order_principal)` — 둘이 같으면 False · None 은 False (iii) `unsupported_is_deny(...)` — MOCK 미지원 요청이 REAL 로 재작성될 수 없음을 tuple 불변(frozen)+환경 축 교체 금지로 표현: «재작성»을 표현하는 함수를 두지 않고, 그 부재를 negative-grep 테스트로 고정. (iv) probe manifest 는 작업 3 소관이라 이 슬라이스에서 **레코드 형상만**(`ProbeManifest`: `emits_orders: Literal[False]` · allowed_methods · retention · ttl · provenance 문자열) 두고 소비자는 두지 않는다.
6. **테스트**(TDD · happy+negative): enum 카운트 핀 5종 · tuple 모순 조합 전수(음성) · 허용 6행 양성 + 목록 밖 무작위(hypothesis) 전부 PROHIBITED · `BROKER_PRODUCTION×ORDER_SEND×FUTURES` 표현 불가 · 술어 (i)(ii) 극성(None=False) · 임포트 closure(형제-엣지-0 유지 — `test_brokercap_import_closure.py` 확장) · `CapabilityDimension==17` 불변.

## 4. 기각 대안

- vocabulary.py 에 enum 추가 → 카운트 핀·모듈 크기 budget 압박, 별도 모듈이 더 낮은 결합.
- YAML 로 허용 행렬 외부화 → brokercap 은 yaml 부재 핀(형제-엣지-0)이며 행렬은 «정책 값»이 아니라 «구조적 봉인» — 실행 시 바뀌면 안 되는 표. 값형 문턱이 아니다.
- `is_mock: bool` 라우팅 유지 → 계획 §5.1 이 명시 기각.

## 5. 종료 조건

- `tos/tests/brokercap` + 기존 전체 `tos/tests` green · mypy/ruff/black 0 · `tools/tos_size_budget.py --check` 0 · firewall PASS
- 이 슬라이스는 어떤 EV 행도 닫지 않으며(BC-EV 상태 불변) 어떤 경로도 열지 않는다.
