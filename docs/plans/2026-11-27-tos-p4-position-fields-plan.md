# TOS P4 — 포지션 값을 DSL 에 · 손절/목표/수량을 YAML 로 (계획)

작성 2026-11-27 · 기준 main `92b81b76` · 로드맵 [§P4](2026-11-11-tos-platform-roadmap.md) 의 실행 계획.
등급 **A**(커널·런타임 변경, 주문 수량 도출) — 단계별 등급은 §4.

## 0. 한 줄과 완료 판정

**지금 tenant 규칙은 자기가 포지션을 들고 있는지 모른다.** 그래서 손절·목표·시간 청산을 YAML 로 쓸 수 없고,
수량은 1 로 고정돼 있다. P4 는 커널이 이미 가진 증거에서 포지션 값을 투영해 DSL 이 읽게 한다.

완료(측정으로만):

1. 손절 규칙을 YAML 로 선언한 tenant 가 **리플레이에서** 손절 결정과 가상 체결을 낸다(CI 정답에 고정).
2. 같은 tenant 가 **MOCK 세션에서** 손절 규칙으로 FLAT 체결을 한 번 낸다(`sts tos perf` 의 그 행이 증거).
3. 이 PR 묶음 전후로 포지션 값을 켜지 않은 트리의 리플레이 정답이 **바이트 동일**하다.
4. 포지션 값을 켠 잎이 재부팅 뒤 `EngineReplayDiverged` 없이 올라온다(hermetic 테스트 + 실제 다음 날 부팅).

## 1. 지금 — 실측(2026-11-27)

| 사실 | 자리 |
| --- | --- |
| DSL 환경은 `{capsule: {…, resolved_values: {…}}, config: {…}}` 둘뿐이다 | `tos/src/tos/dsl/determinism.py::build_environment` |
| `resolved_values` 는 시세 스냅샷에 묶인 `ContextValueView` — 생산자 journal 이 원천이다 | `tos/src/tos/marketfeed/value.py` · `dsl/context_value.py` |
| DSL 은 비교와 결합뿐이다. 산술이 없고, 모르는 피연산자는 그 비교를 **거짓**으로 만든다 | `dsl/vocabulary.py::eval_compare` |
| 규칙은 위에서부터 첫 번째로 맞는 것 하나가 결정이다 | `dsl/vocabulary.py::evaluate_policy` |
| 결정 이벤트 payload 가 `value_view` 를 싣고, 파이프라인은 payload 에 실린 것만 평가한다 | `engine/records.py::DecisionTickPayload` · `engine/pipeline.py:243` |
| 부팅은 inbox 의 지난 이벤트를 다시 도출해 기록과 대조한다(주식 트리 창 = 1,000,000 이벤트) | `compose/_boot_integrity.py::verify_engine_replay_or_halt` · `engine_driver.yaml` |
| 보유 수량은 이미 증명된다 — RCL + 청산 이력에서 «열린 진입의 남은 수량» | `tos_runtime/riskstate/close_bound.py::DurableEntryCloseBoundReader` |
| 그 값은 FLAT 주문의 수량에만 쓰이고(`held_position_magnitude`) DSL 은 못 읽는다 | `compose/_attempt_shape.py` · `egressgw/construction.py:188` |
| 체결가는 증거에 있다 — `FILL_OBSERVED.avg_execution_price`, 없으면 `SEND_SEALED.send_seal.outbound_price` | `posttrade/fill_observer.py:422` · `tools/tos_cp3/perf.py` 가 같은 우선순위로 읽는다 |
| 수량 = `risk_budget / per_unit_risk` 를 lot 으로 내림, 범위 밖이면 **거부(절대 clamp 하지 않음)** | `egressgw/construction.py::derive_order_size` |
| 두 값은 설정의 상수다 — 주식 트리 `1 / 1` | `order_construction_policy.yaml:110-111` |
| 이미 포지션이 있으면 새 진입은 capacity 단계에서 멈춘다(`AT_MOST_ONE_EXPOSURE_HELD`) | `engine/sequencer.py` |
| 리플레이(P3)는 신호만 본다 — 포지션을 모른다 | `docs/plans/2026-11-27-tos-replay-plan.md` §6 |

확인하지 못한 것(§4 S0 에서 잰다): SYNTHETIC venue 원장이 체결가를 어떤 키로 남기는지 ·
진입 결정의 봉 시각을 증거 사슬에서 한 번의 조회로 얻을 수 있는지.

## 2. 설계 결정

**D1 — 포지션 값은 이벤트 payload 에 실어 들인다. 평가 시점에 다시 계산하지 않는다.**
`DecisionTickPayload` 에 `position_context` 를 더한다(없으면 직렬화에서 빠진다 — 그 파일의 `_omit_when_none`
관례). 런타임이 봉마다 capsule 을 발행할 때 증거에서 읽어 채우고, 파이프라인은 payload 에 실린 값만 본다.
이유: 부팅 리플레이는 inbox 의 payload 로 결정을 다시 도출한다. 평가 시점에 원장을 읽으면 재부팅 때의 원장이
그때와 달라 결정이 갈리고, 그 잎은 영구히 못 올라온다(2026-11-12 사고와 같은 종류).

**D2 — 자리는 `capsule.position`, 값은 닫힌 목록 일곱.** `resolved_values` 와 나란한 예약 이름공간이다
(충돌 검사도 같은 방식). `resolved_values` 에 섞지 않는 이유: 그 뷰는 시세 스냅샷의 id·다이제스트에 묶여 있고,
포지션 값의 출처는 시세가 아니라 RCL·finality 다 — 출처가 다른 값을 한 다이제스트 아래 두지 않는다.

| 필드 | 형 | 뜻 |
| --- | --- | --- |
| `side` | `"FLAT"` · `"LONG"` · `"SHORT"` | 증명된 보유 방향 |
| `held_qty` | int | 증명된 남은 수량. FLAT 이면 0 |
| `entry_price` | int | 진입가, 그 트리의 `price_field_key` 와 **같은 정수 스케일** |
| `entry_price_basis` | `"EXECUTION"` · `"ORDER"` | 브로커 평균 체결가인지, 보낸 지정가로 떨어졌는지 |
| `unrealized` | int | 방향을 반영한 가격 차(유리하면 양수), `entry_price` 와 같은 스케일 |
| `unrealized_bp` | int | `unrealized / entry_price` 를 bp 로(0 쪽으로 버림) |
| `bars_held` | int | 진입 결정 봉에서 이 봉까지 지난 봉 수 |

`unrealized*` 가 방향을 이미 반영하므로 LONG·SHORT 트리가 **같은 문장**의 손절 규칙을 쓴다(선물 대칭 규칙).
로드맵은 «미실현 손익(틱)» 이라 적었으나 틱이 아니라 가격 스케일과 bp 로 낸다: 주식 호가단위는 가격대별
사다리라 «틱 수» 가 한 숫자로 정해지지 않는다.

**D3 — 모르면 이름공간 전체가 없다.** 보유 증명이 거부됐거나(`EntryCloseBound.refusal`), 미해결 전송이
있거나, 진입가를 못 찾으면 `position` 을 통째로 싣지 않는다. 그러면 포지션을 읽는 비교가 전부 거짓이 되어
손절도 진입(`side EQ FLAT`)도 발화하지 않는다. 일부만 채운 값은 만들지 않는다.

**D4 — 계산은 커널의 순수 함수 하나.** `tos/src/tos/dsl/position_context.py`(§10 ④) 에 «(증명된 수량·방향·진입가·
진입 봉 시각, 이번 봉의 가격·시각) → `PositionContext`» 를 둔다. 런타임 발행 경로와 리플레이 시뮬레이션(D7)이
같은 함수를 부른다 — 두 구현이 갈라지면 리플레이가 라이브와 다른 손절을 보여 준다.

**D5 — 트리마다 켠다. 기본은 꺼짐.** `marketfeed.yaml::position_context: {enabled, price_field_key}`.
꺼진 트리는 payload·환경·서명이 지금과 바이트 동일하다(완료 3). 켜진 트리에서는 포지션 컨텍스트의
다이제스트가 `RecordedInputSignature.captured_external_value_refs` 에 더해진다 — 결정이 무엇을 읽었는지
증거에 남아야 하기 때문이다. 전략이 `capsule.position.*` 를 참조하는데 트리가 꺼져 있으면 **부팅 거부**
(`tos_runtime/strategy/resolve.py` 의 기존 바인딩 거부와 같은 자리).

**D6 — 수량: 위험 단위를 필드에서 읽을 수 있게 한다.** 수량 한도 설정에 `per_unit_risk_field_key` 를 더한다
(`price_field_key` 와 같은 방식 — 승인된 정수 값 하나를 뷰에서 정확히 읽고, 없거나 모호하면 거부).
- 고정 N: 지금도 된다 — `risk_budget: N, per_unit_risk: 1`. 코드 변경 없음.
- ATR 기반: 생산자 카탈로그 필드(예: `k × ATR` 을 가격 스케일 정수로)를 `per_unit_risk_field_key` 로 지정.
- **«범위 밖은 거부, clamp 없음» 은 그대로 둔다.** 수량 상·하한에 맞추는 일은 카탈로그의 몫이다
  (위험 단위에 하한을 거는 `max` 연산). 커널이 조용히 줄여 보내는 주문은 만들지 않는다.
- 한도는 기존 `aggregate_risk_policy` · `action_flow_policy` · venue 제약이 그대로 건다.

**D7 — 리플레이가 포지션을 시뮬레이션한다.** 리플레이의 평가기(`tos/runtime/cp3/inspect_session`, 방화벽 안쪽)가
봉을 돌며 포지션 상태를 들고 D4 의 함수로 `capsule.position` 을 만든다. 체결 모델은 한 줄이다:
**ACTION·FLAT 결정은 그 봉의 `price_field_key` 값에 전량 체결된다**(construction 이 보내는 지정가와 같은 값).
이 모델은 MOCK 의 미체결·부분 체결을 모른다 — 차이는 P5 가 숫자로 낸다. 기록된 세션을 보는
`sts tos inspect` 는 시뮬레이션하지 않고 payload 에 실렸던 값을 그대로 읽는다.

**D8 — 손절은 봉 마감에서 본다.** 손절·목표는 1분봉 결정으로 나가는 LIMIT/DAY 주문이다. 브로커 쪽
조건부 주문(스탑·OCO)은 쓰지 않는다 — 커널의 주문 형태는 LIMIT/DAY 하나이고, 그 밖의 형태는 주문 경로 전체
(승인·예약·적합성 증명)를 새로 여는 일이다. 한계는 §6 에 적는다.

## 3. tenant 쪽 — 첫 적용

- 대상: `cp3-setup-d-stock-000660`(실험 A). 카나리아 005930 은 건드리지 않는다 — 그 트리는 전략이 아니라
  경로 생존을 잰다.
- 규칙(순서가 뜻이다 — 위에서 첫 번째로 맞는 것):
  1. 손절: `side NE FLAT` ∧ `unrealized_bp LE config.stop_loss_bp` → FLAT
  2. 목표: `side NE FLAT` ∧ `unrealized_bp GE config.take_profit_bp` → FLAT
  3. ~~시간: `side NE FLAT` ∧ `bars_held GE config.max_bars_held` → FLAT~~ — **첫 적용에서 뺀다**(§11 결정 3)
  4. 기존 R2(VWAP 복귀) · R3(EOD)
  5. 기존 R1 진입에 `side EQ FLAT` 을 더한다(지금은 capacity 단계가 대신 막는다 — 결정이 깨끗해진다)
- 두 숫자는 `strategy_bindings.yaml` 에 둔다. 초기값은 리플레이(호스트 실데이터, 000660)로 후보 폭 몇 가지의
  발동 횟수·가상 손익을 표로 본 뒤 추천값으로 적용한다(§11 결정 7) — 이 계획이 숫자를 정하지 않는다.
- **규칙이 바뀌므로 잎을 새로 연다**(지속 잎 + 규칙 변경 = `EngineReplayDiverged`, 2026-11-12). 옛 잎은 보관.
- **새 잎을 열기 전날 장 마감 뒤 모의 계좌 잔고를 본다**(§11 결정 4): `tools/tos_cp3/ops/mock_flat_check.py`
  로 그 종목이 비었는지 확인하고, 남아 있으면 `mock_flatten.py` 로 모의 주문으로 정리한다. 새 잎의 증거는
  비어 있어서, 전날 주식이 남아 있어도 `side` 는 FLAT 으로 읽힌다 — 진입 규칙이 발화하고 남은 주식의 손절은
  영영 발화하지 않는다(S2 리뷰 MEDIUM-1).
- 선물 두 트리(SYNTHETIC)는 S4 뒤에 같은 규칙 문장으로 켠다 — 대칭 확인이 그 PR 의 수용 기준이다.

## 4. 단계

| 단계 | 내용 | 등급 | 완료 측정 |
| --- | --- | --- | --- |
| S0 | 실측: SYNTHETIC 원장의 체결가 키 · 진입 봉 시각 조회 경로 · payload 필드 추가가 기존 잎의 리플레이에 주는 영향(기록된 잎 하나를 새 코드로 부팅 리플레이) | C | 표 하나(명령·숫자·로그 경로) |
| S1 | 커널: `PositionContext` 레코드 · 순수 함수 · `capsule.position` 이름공간 · 서명 반영 · payload 필드 | A | hermetic 테스트(경계값·UNKNOWN·대칭) · `tos_redigest --check` · 꺼진 경로 바이트 동일 테스트 |
| S2 | 런타임: 증거 → 포지션 읽기 · capsule 발행 때 payload 에 싣기 · `position_context` 설정 · 참조-꺼짐 부팅 거부 · 재부팅 리플레이 일치 테스트 | A | `tos/runtime/tests` — 진입→재부팅→같은 결정 · 미해결 전송 중에는 이름공간 없음 |
| S3 | 리플레이 포지션 시뮬레이션 · `inspect` 가 기록된 값 표시 · 가상 손익을 같은 체결 모델로 통일 | B | 기존 정답 5개 바이트 동일(전부 꺼진 트리) · 포지션 켠 합성 트리 1개의 정답 추가 |
| S4 | 000660 에 손절·목표·시간 규칙 · 새 잎 · 정답 갱신 | B | 완료 1 · 다음 날 부팅 green · 완료 2 는 손절이 실제로 걸리는 날까지 관측 |
| S5 | `per_unit_risk_field_key` · 카탈로그 위험 단위 필드 · 수량 범위 거부 테스트 | A | 고정 N 과 ATR 기반 두 경우의 수량이 리플레이·MOCK 에서 선언대로 |
| S6 | 주식 트리를 종목 목록에서 렌더(`scripts/tos/render_paper_config.py` 재사용) — 종목 추가 = 목록 한 줄 | B | 지금 세 트리가 렌더 결과와 바이트 동일 · 네 번째 종목 추가 diff 가 목록 한 줄 + 생성물 |

순서의 이유: S1·S2 가 없으면 나머지가 설 자리가 없다. S3 를 S4 앞에 두는 것은 규칙을 MOCK 에 올리기 전에
리플레이로 먼저 보기 위해서다. S5·S6 은 서로와 S4 에 독립이라 병행할 수 있다.
S1·S2 는 PR 하나로 묶지 않는다 — 커널 PR 이 작아야 A 등급 리뷰가 읽는다.

일정: 로드맵은 2027-01 로 적었으나 선행 단계(P1~P3)가 끝났으므로 지금 시작한다. 2주를 넘기면 범위를 줄인다
(로드맵 일정 규칙) — 줄일 순서는 S6 → S5 → 선물 트리 적용.

## 5. 회귀를 막는 것

| 변경 | 고정하는 것 |
| --- | --- |
| payload·환경·서명(S1) | 꺼진 경로의 직렬화·다이제스트 바이트 동일 테스트 · 기존 hermetic 스위트 · `tos-gate` |
| 포지션 읽기(S2) | 재부팅 리플레이 일치 · 복구 drill(CI) · 증명 거부 사유별 «이름공간 없음» 테스트 |
| 순수 함수(S1) | 손계산 정답표 — LONG/SHORT 대칭, bp 버림 방향, 0·음수 진입가 거부 |
| 리플레이(S3) | P3 정답(`tos-replay-golden`) — 꺼진 트리 불변, 켠 트리 새 정답 |
| tenant YAML(S4) | 부팅 시 참조 해석 거부 · 정답 diff 가 PR 에 보인다 |
| 수량(S5) | 범위 밖 거부 · 필드 없음/모호 거부 · 단위 불일치 거부(기존 테스트 형식 그대로) |

새 검사기·새 CI 잡은 만들지 않는다(R5). 전부 기존 잡 안의 테스트다.

## 6. 한계와 위험

- **손절은 1분 늦고, 체결을 보장하지 않는다.** 봉 마감 가격으로 판단해 그 가격에 지정가를 낸다. 가격이 계속
  밀리면 미체결로 남고 다음 봉에서 다시 FLAT 을 낸다. 급변 구간의 실제 손실은 선언한 손절 폭보다 크다.
  이것이 문제라는 숫자가 P5 에서 나오면 그때 주문 형태를 넓히는 별도 계획을 쓴다.
- **`entry_price_basis: ORDER` 인 날.** 브로커 체결 행이 모호해 지정가로 떨어진 진입은 실제 체결가와 다를 수
  있다. 값은 내되 basis 를 함께 실어, 엄격한 tenant 는 `entry_price_basis EQ EXECUTION` 을 규칙에 더할 수 있다.
- **봉 사이의 상태 변화.** 포지션 값은 capsule 발행 시점의 것이다. 발행과 평가 사이에 체결이 오면 그 봉의
  결정은 한 봉 전 상태로 난다. 수량 쪽 안전은 기존대로 construction·capacity 단계가 진다(FLAT 수량은 전송
  직전의 증명된 남은 수량).
- **커널 리비전을 가로지르는 잎.** 래퍼가 매일 `origin/main` 으로 워크트리를 새로 만든다. S1·S2 가 기존 잎의
  재도출을 바꾸면 다음 날 아침 그 잎이 held 로 떨어진다 — S0 의 세 번째 측정이 머지 전에 이것을 본다.
- **리플레이 체결 모델은 낙관적이다**(전량·즉시). 리플레이 손익은 회귀 검출용이지 성과 약속이 아니다.

## 7. 하지 않는 것

- 실전 주문, 실 증거금, 실전 선물 주문 경로(비협상 규칙). P4 전체가 MOCK·SYNTHETIC 안이다.
- DSL 산술·사용자 함수(로드맵 §4). 필요한 계산은 커널의 닫힌 포지션 값 또는 카탈로그 필드로 낸다.
- 브로커 조건부 주문, 부분 청산·분할 진입, 추적 손절(진입 후 최고가가 필요 — 포지션 값 하나를 더하는
  후속으로 남긴다), tenant 당 포지션 둘 이상(운용 규칙 U1).
- 주식 스윙의 일괄 장 마감 청산 추가(비협상 규칙). 시간 청산은 tenant 가 선언한 규칙일 뿐 기본값이 아니다.
- 전략별 파이썬 코드. 새 전략·새 손절은 `config/` 아래 파일만 바뀐다.

## 8. 기각한 대안

| 대안 | 기각 이유 |
| --- | --- |
| 생산자가 포지션 필드를 journal 에 쓴다 | 생산자는 방화벽 밖이고 체결을 모른다. 주문 경로의 상태가 시세 통로로 들어오는 옆문이 된다 |
| 파이프라인이 평가 때 원장에서 읽는다 | 재부팅 리플레이가 그때의 원장을 복원하지 못하면 결정이 갈린다(D1) |
| `resolved_values` 에 합친다 | 시세 스냅샷 다이제스트 아래 출처가 다른 값이 들어간다(D2) |
| 커널 `BacktestDriver` 로 리플레이 | P3 에서 본 대로 결정이 아닌 다이제스트만 낸다. 포지션 시뮬레이션은 평가기 안 수십 줄로 충족된다. 체결 모델을 정교하게 할 이유가 P5 숫자로 생기면 다시 본다 |
| 수량을 범위에 맞춰 clamp | «조용히 다른 수량» 은 construction 이 금지해 온 수리(repair)다(D6) |

## 9. 운영자가 볼 결정 — 추천으로 진행한다

1. 첫 적용 tenant = **000660**(카나리아는 그대로).
2. 손익 단위 = **가격 스케일 + bp**(틱 아님).
3. 손절 방식 = **봉 마감 판단 + LIMIT**(브로커 조건부 주문 없음).
4. 시작 = **지금**(2027-01 을 기다리지 않는다). 첫 PR 은 S0 측정 기록이다.

## 11. 운영자 결정 (2026-11-28)

| # | 물은 것 | 결정 |
| --- | --- | --- |
| 1 | `run_decision_pipeline` 가 한 줄 늘어 크기 등재와 어긋남(S1) | 실측값으로 재등재(154→155) |
| 2 | `compose_paper_runtime` 을 351줄에 맞추려 배선을 객체로 묶은 구현(S2) | 걷어내고 평평하게 배선, 실측값으로 재등재 — 줄 수에 맞춘 코드는 두지 않는다 |
| 3 | `bars_held` 는 벽시계로 센다 — 주식을 다음 날로 넘기면 첫 봉에 약 1,000봉 이상 | S4 는 손절·목표만. 시간 청산은 «세션 봉 수» 값이 필요한지 P5 숫자를 본 뒤 정한다 |
| 4 | 새 잎을 열 때 모의 계좌에 전날 주식이 남아 있으면 FLAT 으로 읽힘 | 열기 전 잔고 확인·정리를 절차로 둔다(§3). 리더의 브로커 잔고 대조는 하지 않는다 |
| 5 | 크기 예산 등재 11건의 기한 2026-12-31 | 2027-03-31 로 연장. 분해는 P4 뒤 |
| 6 | 실데이터 리플레이에 쓸 분봉(저장소는 2026-10-08 에서 끝남) | 매일 장 마감 뒤 그날 세션 분봉을 호스트 저장소에 쌓는다. 과거 공백 백필은 하지 않는다 |
| 7 | 손절·목표 폭 | 리플레이 비교 뒤 추천값으로 적용. 데이터가 얇다는 것(000660, 10-08 까지 7 세션)을 표에 함께 적는다 |
| 8 | 부팅마다 전 이력 재도출(잎당 최대 약 6초) | 손대지 않는다. 잎당 60초를 넘으면 다시 논의 |

같은 날 정한 P4 밖의 둘: 2027 휴장일은 지금 채우고 KRX 공지로 재확인한다 · 옛 ref 20개는 squash 이전 번들의
호스트 밖 사본이 확인된 뒤에 지운다.

S2 리뷰가 남긴, 코드가 아니라 운용이 알아야 할 것: 엔진이 내려가 있는 동안 쌓인 틱은 **쌓일 때의** 포지션
값을 갖는다(같은 값으로 연속 결정이 날 수 있다 — 수량 쪽은 capacity·close-bound 단계가 그대로 막는다).

## 10. S0 실측 결과 (2026-11-27, main `f53b2e5f`, 코드 읽기)

| # | 물은 것 | 답 | 자리 | 계획에 주는 영향 |
| --- | --- | --- | --- | --- |
| ① | SYNTHETIC 체결가 | **어디에도 남지 않는다.** 원장 테이블에 가격 열이 없고 `FILL_OBSERVED` 는 KIS mock 관측자만 쓴다 | `venue_ledger/synthetic.py:44-59` · `compose/_broker_posttrade_wiring.py:510-545` | 선물 트리의 `entry_price_basis` 는 항상 `ORDER` |
| ② | 모든 전송에 있는 가격 | `SEND_SEALED.send_seal.outbound_price` — 전송 전에 커널 게이트웨이가 쓰고, 값은 `price_field_key` 뷰 정수 **그대로**(같은 스케일) | `egressgw/gateway.py:604-615,868-878` | 진입가의 기본 원천. `avg_execution_price`(원 단위)는 `× price_scale` 해야 같은 스케일 |
| ③ | 진입 봉 시각 | 한 번의 조회는 없다. attempt → `event_id`(`ATTEMPT_REQUEST_CREATED`, 증분 색인 있음 — 비공개) → inbox payload 의 `value_view.values[*].as_of` | `rcl/reservation_lookup.py:36-98` · `engine/inbox.py:33` | S2 가 inbox 에 id 조회 하나와 색인의 공개 접근자 하나를 더한다 |
| ④ | 엔진 import 폐쇄 | 엔진 폐쇄 표에 `tos.position` 이 없다 — 거기 둔 형을 `engine/records.py` 가 import 하면 폐쇄 테스트가 깨진다 | `tos/tests/_closure_table.py:446-449` | 레코드와 순수 함수는 `ContextValueView` 옆 `tos.dsl` 에 둔다(폐쇄를 넓히지 않는다) |
| ⑤ | payload 필드 추가의 호환 | `exclude_if=_omit_when_none` 인 필드는 None 이면 `model_dump` 에서 빠져, 그 필드가 없는 이벤트의 id·다이제스트가 바이트 동일하다. 수신 지문은 payload 가 아니라 결과에서 나온다 | `engine/records.py:124,241-245` · `engine/flow_fingerprint.py:19-45` · 선례 테스트 `tos/tests/engine/test_engine_egress_trading_date.py:64-77` | D1·D5 그대로 성립 |
| ⑥ | 봉마다 읽는 비용 | `durable_close_history` 는 호출마다 RCL 전이 이력과 증거 종류 다섯을 통째로 훑는다(증거 크기에 선형, 캐시는 조인 색인뿐) | `posttrade/close_history.py:205-223,824,911` | S2 가 지속 잎(000660)에서 호출 시간을 재고, 봉 주기에 비해 크면 증분 캐시를 같은 PR 에 넣는다 |
| ⑦ | payload 가 만들어지는 자리 | 커널 `MarketFeedContextResolver.resolve`; 스케줄러는 증거 저장소만 갖고 RCL·보유 증명 리더는 없다. 리더는 같은 조립 함수 안에 이미 있다 | `marketfeed/resolver.py:114-119` · `marketfeed/scheduler.py:269-273` · `compose/root.py:233-239,442` | S2 는 조립 루트에서 리더를 스케줄러에 주입한다. 가격 키는 `construction.yaml::price_field_key` 를 그대로 쓴다(D5 의 `price_field_key` 중복 선언은 뺀다) |

S0 표의 «기록된 잎을 새 코드로 부팅 리플레이» 는 코드가 있어야 잴 수 있어 S1 의 수용 기준으로 옮긴다.
