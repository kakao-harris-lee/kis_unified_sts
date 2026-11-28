# config/tos_runtime/cp3-setup-d-stock-000660/

CP-3 **주식 tenant** 설정 트리 — 종목 **000660(SK하이닉스)**.

운영자 지시 2026-11-19: 「유동성이 큰 대형주들로 최종 모의투자에서 매수/매도가 잘 동작하게
완료해」. 운영자 결정: **종목당 열린 포지션 1개**(커널의 no-pyramiding 그대로) · 슬롯 3개
이상은 **종목 3개 이상**에서 나온다 · **1주 고정 그대로**.

이 트리는 `cp3-setup-d-stock-005930/` 에서 파생됐고, **그 트리의 README 가 정본**이다 —
MOCK 주문 scope, band 원천, 체결·완결·해제, 상시 승인, R4 M2 프로브, 하지 않는 것까지 전부
거기 적혀 있고 이 트리도 같다. 여기에는 **다른 것만** 적는다.

## 역할: 실험 A — Setup D LONG, R4 프로브 끔, YAML 손절·목표 켬

`docs/plans/2026-11-19-tos-usage-plan.md` §4.1 의 역할 분담(운영자 결정 2026-11-19 §8-②
「채택 — R4 는 005930 에만 남긴다」): 005930 은 주문 경로가 매일 살아 있는지 재는 **카나리아**
(R4 프로브 유지), 이 트리는 **실험 A**, 005380 은 실험 B(RSI / Williams %R 되돌림)다.

끄는 방법은 바인딩 한 줄이다 — `strategy_bindings.yaml::m2_probe_entry_enabled: false`.
규칙 `R4-M2-PROBE-ENTRY-LONG` 은 전략 파일에 **그대로 남고** 발화만 하지 않는다(그 규칙의
셋째 비교가 `entry_window EQ config.m2_probe_entry_enabled` 이므로 진입창이 열린 바에서
`true == false` 로 거짓).

## 포지션 값을 읽는 첫 tenant (P4 S4)

`docs/plans/2026-11-27-tos-p4-position-fields-plan.md` §3 의 첫 적용. 이 트리만
`marketfeed.yaml::position_context` 를 켜고(나머지 네 트리는 꺼진 채로 — 그래서 그들의
payload·환경·서명이 그대로다), 손절과 목표를 **규칙 두 개와 숫자 두 개**로 선언한다.

규칙 순서가 뜻이다(첫 일치가 결정):

| # | 규칙 | 조건 | 결정 |
| --- | --- | --- | --- |
| 1 | `R1-ENTRY-LONG` | `position.side EQ "FLAT"` ∧ Setup D 다섯 게이트 | ACTION |
| 2 | `R5-EXIT-STOP-LOSS` | `side EQ "LONG"` ∧ `unrealized_bp LE config.stop_loss_bp` | FLAT |
| 3 | `R6-EXIT-TAKE-PROFIT` | `side EQ "LONG"` ∧ `unrealized_bp GE config.take_profit_bp` | FLAT |
| 4 | `R2-EXIT-VWAP-REVERTED` | `vwap_reverted` | FLAT |
| 5 | `R3-EXIT-EOD` | `eod` | FLAT |
| 6 | `R4-M2-PROBE-ENTRY-LONG` | `side EQ "FLAT"` ∧ 진입창 ∧ 프로브 바인딩 | ACTION (이 트리에서 꺼짐) |

- **R1 이 첫 자리에 남는다.** 그 target 이 `&account`·`&instrument` 앵커를 **정의**하므로
  청산 규칙을 앞으로 옮기면 YAML 이 정의 전 별칭을 만나 파일이 통째로 로드되지 않는다.
  `side EQ "FLAT"` 가드가 있어 보유 중에는 발화하지 않으니 청산을 가리지 않는다.
- **시간 청산은 없다**(운영자 결정 2026-11-28 §11 #3: `bars_held` 는 벽시계로 세므로
  주식을 다음 날로 넘기면 첫 봉에 ~1,000봉이 된다).
- **청산 가드는 `side EQ "LONG"` 이다** — `NE "FLAT"` 이 아니다. 이 전략은 롱만 열지만
  `NE "FLAT"` 은 어떤 경로로든 SHORT 가 투영된 봉을 통과시키고, 그러면 두 규칙의
  `direction: SHORT` · `position_effect: CLOSE` target 이 숏을 **키우는** 주문이 된다.
- **이름공간이 없는 봉에서는 아무것도 발화하지 않는다.** 모르는 피연산자는 연산자와
  무관하게 그 비교를 거짓으로 만든다(`tos/src/tos/dsl/vocabulary.py::eval_compare`) —
  손절·목표도, 가드가 붙은 두 진입도 발화하지 않는다(계획 §2 D3). R2·R3 는
  `resolved_values` 만 읽으므로 그대로다.
- 두 숫자를 바꾸는 것은 `strategy_bindings.yaml` 두 줄 + generation 재도출이다.

## 005930 트리와 다른 것

| 파일 | 다른 값 | 이유 |
| --- | --- | --- |
| `RENDER.yaml` | `tree_id` · `instrument.pattern: "000660"` | 트리는 단일 종목이다(아래) |
| `venue_constraint_policy.yaml` | `policy_id` · `scope.instruments` 슬롯 · `approved_by` · `effective_from` · 헤더의 종목·근거 | 내용이 다르니 id 도 다르다(LONG 헤더의 규칙). 호가단위 사다리는 **가격대별**이라 종목과 무관하게 같다 |
| `critical_input_policy.yaml` | `policy_id` · `issuer_principal_id` | 같은 규칙 |
| `strategy_bindings.yaml` | `m2_probe_entry_enabled: false` · `stop_loss_bp` · `take_profit_bp` | 실험 A — 위 두 절 |
| `marketfeed.yaml` | `position_context: {enabled: true, bar_interval_ms: 60000}` | 포지션 값은 트리마다 켠다 — 위 절 |
| `strategies/setup_d_long.strategy.yaml` | R5 · R6 두 규칙 + R1·R4 의 FLAT 가드 | 같은 절 |
| `engine.yaml` | 주석의 정적 스텝 수(31 → 51) | 예산 64 는 그대로 — 51 ≤ 64 |
| `fields.yaml` · `fill_observer.yaml` | 주석의 종목·생산자 설정 경로 | 런타임이 읽는 값은 005930 과 같다 |

나머지 파일은 005930 트리와 **바이트 동일**이다 — `authority.yaml` · `calendar.yaml` ·
`broker_scopes.yaml` · `broker_facts.yaml` · `egress_coordinates.yaml` · `release.yaml`
전부 포함. 이 분류는
`tos/runtime/tests/compose/test_tenant_tree_stock_siblings.py` 가 파일·키 경로 단위로 고정한다.

**decision digest 는 005930 과 다르다** — 규칙과 바인딩이 결정 계약의 일부이기 때문이다
(`config/tos_runtime/decision_generations.yaml` 가 그 이유를 적는다). 이 tenant 는
`generation` **3**: 1 은 11-20 에 프로브를 켠 채 태어난 계약, 2 는 그 바인딩을 끈 계약,
3 이 손절·목표를 더한 지금의 계약이다.
⚠ generation 이 오른 잎은 **재-genesis** 해야 배포된다(`docs/runbooks/tos-paper-boot.md`
§7.2-f-1) — 전날 장 마감 뒤 이 종목이 모의 계좌에서 비었는지 GET 으로 확인하고(남아 있으면
모의 주문으로 정리) 잎을 `archive/` 로 옮긴다. 새 잎의 증거는 비어 있어서, 남은 주식이
있어도 `side` 는 FLAT 으로 읽힌다 — 진입이 발화하고 그 주식의 손절은 영영 발화하지 않는다.

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
  (`$STATE/cp3-setup-d-stock-000660-custody`). 데이터 잎 · 세션 디렉터리 · 락 · 크론 로그도
  tenant 마다 따로다 — `tools/tos_cp3/runners/cp3_tenant_daily.sh` 의 `STOCK:<종목>` 참조.
- **현금과 `nrcvb` 는 공유된다.** 1주 × 3종목은 운영자가 확인한 주문가능현금(~₩9.9M)
  안에 넉넉히 들어간다. 모자라면 브로커가 거부하고 그 시도는 fail-closed 로 끝난다.

## 시세

`config/tos_probes/cp3-live-producer-stock-000660.yaml` 의 생산자(주식일별분봉조회
FHKST03010230, GET 전용, 실전 시세 키). 세 주식 생산자는 **같은 실전 주식 앱 키**를 쓰므로
`token_cache_dir` 을 공유한다 — 캐시된 토큰을 재사용해 「앱 키당 분당 토큰 1회」에 걸리지
않게 한다(그래서 005930 생산자와 같은 디렉터리다).
