# config/tos_runtime/cp3-setup-d-stock-005380/

CP-3 **주식 tenant** 설정 트리 — 종목 **005380(현대차)**.

운영자 지시 2026-11-19: 「유동성이 큰 대형주들로 최종 모의투자에서 매수/매도가 잘 동작하게
완료해」. 운영자 결정: **종목당 열린 포지션 1개**(커널의 no-pyramiding 그대로) · 슬롯 3개
이상은 **종목 3개 이상**에서 나온다 · **1주 고정 그대로**.

이 트리는 `cp3-setup-d-stock-005930/` 에서 파생됐고, **그 트리의 README 가 정본**이다 —
MOCK 주문 scope, band 원천, 체결·완결·해제, 상시 승인, R4 M2 프로브, 하지 않는 것까지 전부
거기 적혀 있고 이 트리도 같다. 여기에는 **다른 것만** 적는다.

## 005930 트리와 다른 것

| 파일 | 다른 값 | 이유 |
| --- | --- | --- |
| `RENDER.yaml` | `tree_id` · `instrument.pattern: "005380"` | 트리는 단일 종목이다(아래) |
| `venue_constraint_policy.yaml` | `policy_id` · `scope.instruments` 슬롯 · `approved_by` · `effective_from` · 헤더의 종목·근거 | 내용이 다르니 id 도 다르다(LONG 헤더의 규칙). 호가단위 사다리는 **가격대별**이라 종목과 무관하게 같다 |
| `critical_input_policy.yaml` | `policy_id` · `issuer_principal_id` | 같은 규칙 |
| `fields.yaml` · `fill_observer.yaml` | 주석의 종목·생산자 설정 경로 | 런타임이 읽는 값은 005930 과 같다 |

나머지 파일은 005930 트리와 **바이트 동일**이다 — `strategies/setup_d_long.strategy.yaml`
(R1~R3 + R4 M2 프로브) · `strategy_bindings.yaml` · `engine.yaml` · `authority.yaml` ·
`calendar.yaml` · `broker_scopes.yaml` · `broker_facts.yaml` · `egress_coordinates.yaml` ·
`release.yaml` 전부 포함. 이 분류는
`tos/runtime/tests/compose/test_tenant_tree_stock_siblings.py` 가 파일·키 경로 단위로 고정한다.

전략·바인딩·`engine.yaml` 이 바이트 동일하므로 **decision digest 가 005930 과 같다** —
`config/tos_runtime/decision_generations.yaml` 의 이 tenant 항목이 같은 digest 를 쓰고,
`generation` 은 **1**(이 잎이 태어날 계약)이다. 005930 의 2 는 그 잎이 3규칙에서 태어나
4규칙으로 바뀐 이력이고, 이 잎은 처음부터 4규칙이다.

## 호가단위 사다리는 종목별이 아니다

`venue_constraint_policy.yaml::_model_view.shape_constraints.price_band_ticks` 는 KRX **가격대별**
호가가격단위 표(1원~9,999,999.99원 7행)다 — 유가증권시장 업무규정 시행세칙 제32조제2항제1호
가~사목. 종목코드가 아니라 **그 순간의 가격**이 칸을 고르므로 005930 과 같은 표를 쓴다.
그날의 상·하한가(기준가 ±30 %)는 정적 값이 아니라 `_runtime.band_source` 가 세션마다
band 프로브의 주식현재가 GET 으로 읽는다. 그래서 이 트리에는 종목별 실측 가격이 없다.

## 계좌는 005930 과 **같다** — 무엇이 공유되고 무엇이 안 되는가

세 주식 tenant 는 하나의 KIS 모의투자 **주식 계좌**(`.env.mock::KIS_STOCK_ACCOUNT_NO`)와
하나의 모의 앱 키를 쓴다. 그래서:

- **증인은 이미 종목으로 좁혀져 있다.** `KisStockBrokerWitness._read_order_rows` 는
  주식일별주문체결조회를 `PDNO = scope.instrument_keys[*].instrument` 로 질의하고,
  `_read_balance` 는 그 종목 집합으로 잔고 행을 거른다. 해제·복구·체결 관찰의 모든
  `WitnessScope` 는 자기 tenant 의 종목 하나만 담는다(`posttrade/fill_observer_plan.py` ·
  `posttrade/release_consumer.py` · `recovery/reconciliation.py`). 다른 tenant 의 주문은
  이 tenant 의 읽기에 **나타나지 않으므로** `ORPHAN_BROKER_ORDER` 가 되지 않는다.
  종목이 겹치지 않는 것이 그 보장의 전제다 — 한 종목에 두 tenant 를 두면 안 된다.
- **요청률은 공유된다.** `fill_observer.yaml` 머리의 «TENANT COUNT» 주석을 읽을 것:
  관찰 주기는 단일 tenant 값의 3 배다.
- **custody 는 공유하지 않는다.** 상시 승인 산출물 경로는 custody 루트 기준 고정이고
  승인은 **렌더된 설정**에 묶이므로, tenant 마다 자기 custody 루트가 있어야 한다
  (`$STATE/cp3-setup-d-stock-005380-custody`). 데이터 잎 · 세션 디렉터리 · 락 · 크론 로그도
  tenant 마다 따로다 — `tools/tos_cp3/runners/cp3_tenant_daily.sh` 의 `STOCK:<종목>` 참조.
- **현금과 `nrcvb` 는 공유된다.** 1주 × 3종목은 운영자가 확인한 주문가능현금(~₩9.9M)
  안에 넉넉히 들어간다. 모자라면 브로커가 거부하고 그 시도는 fail-closed 로 끝난다.

## 시세

`config/tos_probes/cp3-live-producer-stock-005380.yaml` 의 생산자(주식일별분봉조회
FHKST03010230, GET 전용, 실전 시세 키). 세 주식 생산자는 **같은 실전 주식 앱 키**를 쓰므로
`token_cache_dir` 을 공유한다 — 캐시된 토큰을 재사용해 「앱 키당 분당 토큰 1회」에 걸리지
않게 한다(그래서 005930 생산자와 같은 디렉터리다).
