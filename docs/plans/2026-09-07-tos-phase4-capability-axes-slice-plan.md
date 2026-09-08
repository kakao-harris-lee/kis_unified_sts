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

### 3-A. v1.2 정정 (2026-09-07 · Phase 4 브랜치 독립 리뷰 medium 2건 처분)

**R-1 «표현 불가»의 정확한 범위.** 규칙 4 의 봉인은 *validated construction* 에 한정된다 — pydantic 의 `model_construct`/`model_copy(update=)` 는 validator 를 건너뛰며 이것은 brokercap 안에서 상대화할 수 없는(다른 레코드에 validator 가 없다) 라이브러리 전역 사실이다. 따라서 봉인은 **2층**이다: ① validated 생성 거부 ② 닫힌 whitelist 가 우회 tuple 도 PROHIBITED 로 판정. 문언을 «validated-construction seal» 로 좁히고 ②를 **음성 테스트로 고정**한다(우회 tuple 2종 — `model_construct` · `model_copy(update=)` — 이 `routing_admissibility` 에서 PROHIBITED · `ProbeManifest.model_construct(emits_orders=True)` 는 소비 술어가 없으므로 «형상만» 이라는 기존 선언을 유지하고 테스트로 그 한계를 기록).

**R-2 whitelist 는 §5.2 의 축자 전사가 아니라 파생이다.** 상위 계획 §5.2 는 «사용 사례 표»이고 라우팅 전수 행렬이 아니다(리뷰 판정 수용). 닫힌 whitelist 는 유지하되 행 집합을 다음 **파생 규칙**으로 정의한다 — 값을 발명하지 않고 상위 계획의 명시 결정에서만 끌어온다:
- **읽기 클래스 규칙**(상위 계획 §0 결정 2 「`REAL_READ` 는 허용 가능한 관측 capability이고 `REAL_ORDER` 는 별도 권한」· §5.3 「read credential 만」· §5.1 `NON_AUTHORIZING_READ` 의 정의): `∀ env ∈ {SYNTHETIC, BROKER_SIMULATION, BROKER_PRODUCTION}` × `op ∈ {MARKET_DATA_READ, ACCOUNT_READ, CAPABILITY_PROBE}` × `NONE` × `∀ asset` × `NON_AUTHORIZING_READ` ⇒ ADMISSIBLE. 읽기는 정의상 권한을 만들지 않는다. (기존 1·2·4행은 이 규칙의 부분집합이 되어 흡수된다. `CAPABILITY_PROBE` 는 `ProbeManifest` 결속이 별도 의무 — §5.3 «probe manifest 필수»는 이 술어가 아니라 provenance 술어 소관.)
- **합성 주문 규칙**(1b · v1.1 그대로): `SYNTHETIC` × {`ORDER_SEND`,`CANCEL_REPLACE`} × `NONE` × ∀ asset × `SYNTHETIC_ORDER` ⇒ ADMISSIBLE.
- **MOCK 주식 주문 검증 규칙**(§5.2 3행): `BROKER_SIMULATION` × {`ORDER_SEND`, **`CANCEL_REPLACE`**} × `BROKER_RESOURCE_ONLY` × `STOCK` × `MOCK_ORDER` ⇒ REDUCED(`profile_evidence_ok is True` 만). CANCEL_REPLACE 포함은 «주문 검증»이 취소·정정을 포함한다는 상위 §6 Phase 3 작업 5(partial fill·cancel/replace 어휘) 에서 파생. MOCK **선물** 주문은 열거하지 않는다(상위 §5.2 에 근거 없음 · KIS MOCK 은 선물 미제공이 §0 결정 3 의 전제).
- 그 밖 전부 PROHIBITED. 특히 `BROKER_PRODUCTION` × 주문 작업은 STOCK 이라도 열거하지 않는다(§5.2 에 실주식 주문 행 없음 — 리뷰 확인).
- hypothesis 테스트는 «whitelist = 위 규칙의 외연» 을 **두 방향**으로 고정(규칙이 admit 하면 whitelist 에 있고, whitelist 에 있으면 규칙이 admit).

**R-3 축 오버로드 해소.** §5.2 4행의 «공식 명세»는 환경이 아니라 **출처**다 — `ProvenanceClass.OFFICIAL_DOCUMENT` 가 담당하며 환경 축에 싣지 않는다. 읽기 클래스 규칙이 `SYNTHETIC×CAPABILITY_PROBE` 를 자동 포함하지만 이는 «합성 환경에서의 프로브» 라는 정직한 의미이고 문서 출처의 대역이 아니다(docstring 정정).

**R-4 문언.** «the same discipline as every other brokercap record» → «brokercap 최초의 결합 validator» 로 정정.

운영자 확인 지점: R-2 의 읽기 클래스 규칙과 3행 CANCEL_REPLACE 포함은 상위 계획에서 파생했으나 **행렬 자체는 상위 §5.2 소유자의 승인 대상**이다 — PR 리뷰 시 명시 확인 요청.

## 4. 기각 대안

- vocabulary.py 에 enum 추가 → 카운트 핀·모듈 크기 budget 압박, 별도 모듈이 더 낮은 결합.
- YAML 로 허용 행렬 외부화 → brokercap 은 yaml 부재 핀(형제-엣지-0)이며 행렬은 «정책 값»이 아니라 «구조적 봉인» — 실행 시 바뀌면 안 되는 표. 값형 문턱이 아니다.
- `is_mock: bool` 라우팅 유지 → 계획 §5.1 이 명시 기각.

## 5-A. 슬라이스 #2 (같은 브랜치 · 슬라이스 #1 `5912a4f9` 위) — 작업 3 스키마 절반 + 작업 7 계약 고정

**작업 3 스키마 절반 — provenance 클래스**: `tos/src/tos/brokercap/routing.py` 에 `ProvenanceClass{OFFICIAL_SDK, OFFICIAL_DOCUMENT, INTERNAL_CLIENT, CONTROLLED_GET_PROBE}`(상위 계획 작업 3 의 넷: 공식 `open-trading-api` · 공식 문서 · 내부 `shared/kis` · 통제된 GET probe — 커널에는 클래스 이름만, 구체 소스 이름은 인스턴스 소관) + `CapabilityProvenance(FrozenModel)`: `provenance_class` · `source_ref: str`(opaque) · `captured_at: str`(주입 스칼라 · 클록 없음) · `evidence_ref: BrokerEvidenceRef | None`(기존 records.py 재사용) · `probe_manifest: ProbeManifest | None` — 결합 validator: `CONTROLLED_GET_PROBE` ⇒ `probe_manifest` 필수(그 외 클래스는 None 필수). 술어 `provenance_admits_claim(provenance, claim_kind)`: 어떤 provenance 도 `REAL_ORDER` 관련 claim 을 admit 하지 않는다(구조) · `OFFICIAL_DOCUMENT`/`INTERNAL_CLIENT` 는 «측정값» claim 을 admit 하지 않는다(문서는 측정이 아니다) · 나머지는 주입 `evidence_ref` 존재 시만. **데이터 채움(P0-2 캠페인 결속)은 이 슬라이스 밖**.

**작업 7 — adapter 1 outbound → 1 result 계약 고정**: `tos/src/tos/brokeradapter/protocol.py` 의 `Transport` 를 읽고 (a) 계약 docstring 에 «한 attempt 당 `send_once` 정확히 1회 · 내부 재시도 금지 · 결과 미도착은 UNKNOWN(비수락 아님)» 이 이미 있는지 확인, 부재 시만 추가 (b) 기존 합성 transport 구현(`brokeradapter/` 의 paper transport)이 내부 재시도 루프·`sleep`·`for _ in range` 재전송을 갖지 않음을 **negative-grep 테스트**로 고정 (c) `tos/tests/brokeradapter/` 에 «같은 attempt 로 `send_once` 두 번 호출 시 두 번째는 거부/예외» 가 이미 고정돼 있는지 확인, 부재 시 추가. src 변경은 docstring 외 0 이어야 하며 그 이상이 필요하면 보고.

## 5-B. 독립 리뷰 처분 (Claude 측 `code-reviewer` 레인 · 2026-09-07)

- 1차(`5912a4f9`·`ea770657`·`bda929dc`): **needs-attention** · medium 2(규칙 4 봉인 범위 · §5.2 축자 전사) · 비협상 위반 0 → §3-A v1.2 로 처분 · 커밋 `64d0cf80`.
- 재심(`64d0cf80`): **approve** · 뮤테이션 M1~M3 실측(우회 tuple 핀 2건 red · MOCK 규칙/읽기 규칙 변조 시 양방향 테스트 red) · 360 전 곱 자체 재계수 ADMISSIBLE 22 · REDUCED 2 · PROHIBITED 156 · 표현 불가 180 · BROKER_PRODUCTION 주문 tuple 은 STOCK/FUTURES 모두 규칙 밖 · LOW 1(`ProbeManifest` docstring 과대 문언) → 이 커밋에서 정정.
- ~~열린 운영자 확인 지점: §3-A R-2 파생 행렬(읽기 클래스 규칙 · MOCK 주식 CANCEL_REPLACE 편입)의 승인.~~ → **운영자 승인 2026-09-08** («1,2,3,4 모두 비준, 승인» 의 3항). 파생 행렬은 승인된 라우팅 행렬이며 변경은 이 계획의 개정으로만.

## 5. 종료 조건

- `tos/tests/brokercap` + 기존 전체 `tos/tests` green · mypy/ruff/black 0 · `tools/tos_size_budget.py --check` 0 · firewall PASS
- 이 슬라이스는 어떤 EV 행도 닫지 않으며(BC-EV 상태 불변) 어떤 경로도 열지 않는다.
