# config/tos_runtime/cp3-setup-d-stock-{{SYMBOL}}/

CP-3 **주식 tenant** 설정 트리 — 종목 **{{SYMBOL}}({{SYMBOL_NAME}})**.

운영자 지시 2026-11-19: 「유동성이 큰 대형주들로 최종 모의투자에서 매수/매도가 잘 동작하게
완료해」. 운영자 결정: **종목당 열린 포지션 1개**(커널의 no-pyramiding 그대로) · 슬롯 3개
이상은 **종목 3개 이상**에서 나온다 · **1주 고정 그대로**.

이 트리는 `cp3-setup-d-stock-005930/` 에서 파생됐고, 주문 경로에 관한 한 **그 트리의 README 가
정본**이다 — MOCK 주문 scope, band 원천, 체결·완결·해제, 상시 승인, 하지 않는 것까지 전부
거기 적혀 있고 이 트리도 같다. 여기에는 **다른 것만** 적는다. 전략은 다르다(아래).

## 역할: 실험 B — RSI / Williams %R 되돌림

`docs/plans/2026-11-19-tos-usage-plan.md` §4.1 의 역할 분담(운영자 결정 2026-11-19 §8-②):
005930 카나리아(R4 프로브 유지) · 000660 실험 A(Setup D LONG, R4 끔) · **{{SYMBOL}} 실험 B**.
이 트리는 Setup D 를 쓰지 않는다 — 전략 파일도 `strategies/rsi_wr_reversion_long.strategy.yaml`
로 바뀌었고(005930 의 `setup_d_long.strategy.yaml` 은 이 트리에 **없다**), 그래서 필드 선언과
그 필드 선언이 공개하는 집합도 다르다.

| 규칙 | 조건(전부 `fields.yaml` 이 공개하는 bool) | 결정 |
| --- | --- | --- |
| R1-ENTRY-LONG-RSI-WR | `entry_window` ∧ `rsi_oversold` ∧ `wr_oversold` | ACTION — LONG OPEN (수량 1주) |
| R2-EXIT-RSI-RECOVERED | `rsi_recovered` | FLAT — CLOSE |
| R3-EXIT-EOD | `eod` | FLAT — CLOSE |
| R0 (기본) | 그 밖 | NO_ACTION |

R2 는 **교차가 아니라 수준**이다 — RSI 가 50 이상인 **모든** 바에서 청산을 제안한다
(Setup D 의 `vwap_reverted` 와 같은 모양). 기록 봉 실측으로 청산 제안 바가 42.5 %(Setup D
6.2 %)이고, 포지션이 없는 바에서는 아무것도 보내지 않는다. 그 대가로 청산 송신이 한 번
실패해도 다음 바에서 다시 제안한다 — 교차로 만들면 그 한 번을 놓친 포지션이 EOD 까지 남는다.

파라미터와 근거(한 줄씩 `fields.yaml` 에 적혀 있다): RSI 창 14 · 과매도 30 · 중앙선 50
(Wilder 1978, TA-Lib `TA_RSI` 기본값) · Williams %R 창 14 · 과매도 −80(−20/−80 밴드) ·
진입창 09:15~14:45 · EOD 15:15 — 뒤 둘은 005930 트리와 같은 값이다. 지표 연산 자체는
카탈로그의 `rsi` · `williams_r`(#1119, TA-Lib 참조 구현과 비트 동치)이고, 이 PR 은 코드를
건드리지 않는다.

**임계값이 `strategy_bindings.yaml` 이 아니라 `fields.yaml` 의 `const` 인 이유.** 공개 필드는
모든 바에서 값이 있어야 하는데(`tos_runtime/marketfeed/journal.py` 는 키 하나만 비어도 폴
전체를 거부) `rsi` · `williams_r` 는 웜업 동안 값이 없고, 값 없음을 해소하는 `permissive` 는
bool 전용이다. 그래서 RSI 수치를 공개할 수 없고 비교가 선언 쪽에서 끝난다 — 이 트리의
`strategy_bindings.yaml` 은 그 결과 `strategies: {}` 다(쓰지 않는 키를 남기면 기동 거부).
그 대가로 저널에는 RSI 값이 아니라 관문 bool 만 남는다: `sts tos inspect` 로 보는 것은
「어느 비교식이 막았나」이지 「RSI 가 몇이었나」가 아니다.

## 005930 트리와 다른 것

| 파일 | 다른 값 | 이유 |
| --- | --- | --- |
| `RENDER.yaml` | `tree_id` · `instrument.pattern: "{{SYMBOL}}"` · 전략 슬롯 3개의 `file` | 트리는 단일 종목이다(아래) · 전략 파일 이름이 다르다 |
| `strategies/` | `rsi_wr_reversion_long.strategy.yaml` (005930 의 `setup_d_long.strategy.yaml` 없음) | 실험 B — 위 절 |
| `strategy_bindings.yaml` | `strategies: {}` | 같은 절 |
| `fields.yaml` | RSI·%R 관문과 그 임계값; Setup D 의 z·stall·reversal 필드 없음 | 같은 절 |
| `critical_input_policy.yaml` | `policy_id` · `issuer_principal_id` · 공개 필드 15 → **13** | id 는 LONG 헤더의 규칙. 필드 목록은 `fields.yaml::publish` 와 **정확히 같아야** 한다(생산자가 기동 때 비교) |
| `engine.yaml` | 주석의 정적 스텝 수 31 → **18** | 예산 64 는 그대로(18 ≤ 64) |
| `venue_constraint_policy.yaml` | `policy_id` · `scope.instruments` 슬롯 · `approved_by` · `effective_from` · 헤더의 종목·근거 | 내용이 다르니 id 도 다르다. 호가단위 사다리는 **가격대별**이라 종목과 무관하게 같다 |
| `fill_observer.yaml` | 주석의 종목·생산자 설정 경로 | 런타임이 읽는 값은 005930 과 같다 |

나머지 파일은 005930 트리와 **바이트 동일**이다 — `authority.yaml` · `calendar.yaml` ·
`broker_scopes.yaml` · `broker_facts.yaml` · `egress_coordinates.yaml` · `release.yaml` ·
`construction.yaml`(`price_field_key: close_x100` — 전략이 바뀌어도 이 필드는 공개한다) 포함.
이 분류는 `tos/runtime/tests/compose/test_tenant_tree_stock_siblings.py` 가 파일·키 경로
단위로 고정한다.

**decision digest 는 005930 과 다르다** — 전략·바인딩이 다르기 때문이다. 이 tenant 는
`generation` **2**: 1 은 11-20 에 Setup D 계약으로 태어난 잎이고, 2 가 실험 B 계약이다.
⚠ generation 이 오른 잎은 **재-genesis** 해야 배포된다(`docs/runbooks/tos-paper-boot.md`
§7.2-f) — 계좌 평탄을 GET 으로 확인한 뒤 잎을 `archive/` 로 옮긴다.

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
  (`$STATE/cp3-setup-d-stock-{{SYMBOL}}-custody`). 데이터 잎 · 세션 디렉터리 · 락 · 크론 로그도
  tenant 마다 따로다 — `tools/tos_cp3/runners/cp3_tenant_daily.sh` 의 `STOCK:<종목>` 참조.
- **현금과 `nrcvb` 는 공유된다.** 1주 × 3종목은 운영자가 확인한 주문가능현금(~₩9.9M)
  안에 넉넉히 들어간다. 모자라면 브로커가 거부하고 그 시도는 fail-closed 로 끝난다.

## 시세

`config/tos_probes/cp3-live-producer-stock-{{SYMBOL}}.yaml` 의 생산자(주식일별분봉조회
FHKST03010230, GET 전용, 실전 시세 키). 세 주식 생산자는 **같은 실전 주식 앱 키**를 쓰므로
`token_cache_dir` 을 공유한다 — 캐시된 토큰을 재사용해 「앱 키당 분당 토큰 1회」에 걸리지
않게 한다(그래서 005930 생산자와 같은 디렉터리다).
