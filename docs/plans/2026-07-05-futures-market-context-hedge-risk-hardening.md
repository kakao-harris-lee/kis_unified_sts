# Futures Market Context / Hedge / Risk Hardening Design

- 날짜: 2026-07-05
- 성격: 개선안 + 설계 문서
- 범위: 선물 Market Context Engine, Hedge Advisor, Risk Management Engine의
  만기/롤오버·베이시스·OI·외국인 수급·증거금·청산·헤지비율·슬리피지 보강
- 비범위: 즉시 자동 헤지 주문, live enforcement 플립, 기존 Setup A/C/D 진입
  로직 값 변경. 이 문서는 설계와 실행 순서를 정의하며, 실주문 권한을 부여하지 않는다.

---

## 0. TL;DR

현재 시스템은 **시장구조 입력**은 꽤 잘 갖춰져 있다. `market_structure_collector`
와 `market_risk_engine`은 외국인 선물 수급, 베이시스, OI, 프로그램,
환율/해외선물, HAR-RV, 추세를 합성해 `market:risk:latest`로 발행하고,
`market_risk_gate`가 stock/futures 신규 진입 후보에 shadow trace를 붙인다.

하지만 운영 리스크 관점에서는 세 축이 아직 닫히지 않았다.

1. **만기/롤오버 실행 정책이 약하다.** 근월물 코드/만기일 계산은 있지만,
   roll window에서 신규 진입 차단, 보유 포지션 이전/청산 권고, 야간선물
   코드 자동 갱신까지 이어지는 단일 계약 상태 엔진은 없다.
2. **증거금/레버리지/청산 리스크가 모델이 아니다.** 포지션 사이저는
   손절거리 기반 계약당 손실위험을 계산하지만, 실제 계좌 증거금률,
   유지증거금, 청산가 버퍼, 스트레스 손실을 발행하는 엔진은 없다.
3. **헤지는 권고 전용이며 실행 가능성 검사가 부족하다.** β 노출 기반 미니
   KOSPI200 숏 권고는 있지만, 목표 헤지비율, 증거금 여력, 예상 슬리피지,
   롤오버 상태, 강제청산 버퍼를 함께 고려하지 않는다.

개선 방향은 새 거대 엔진이 아니라, 작은 계약면을 추가하는 것이다.

- `FuturesContractState`: front/next contract, days-to-expiry, roll state,
  day/night symbol 상태를 한 곳에서 발행한다.
- `FuturesMarginRiskState`: 계좌/포지션/계약 스펙으로 증거금 사용률,
  청산 버퍼, 스트레스 손실을 계산해 신규 진입/헤지 권고가 읽게 한다.
- `FuturesMarketContextV2`: 기존 Market Risk Score와 LLM MarketContext를
  섞지 않고, 선물 전용 구조화 context를 별도 Redis hash/stream으로 발행한다.
- `HedgeAdvisorV2`: 기존 advisory-only 원칙을 유지하되, 목표 헤지비율과
  실행 가능성 검사를 추가한다.
- enforcement는 마지막 단계다. 기본은 shadow/read-only로 검증한 뒤 operator가
  개별 게이트를 켜는 구조를 유지한다.

---

## 1. 현재 커버리지 요약

### 1.1 이미 잘 들어간 부분

| 항목 | 현재 상태 | 근거 파일 |
|---|---|---|
| 외국인 선물 수급 | 당일 + 20일 누적을 Market Risk Score 25% 가중치로 반영 | `config/market_risk.yaml`, `services/market_structure_collector/main.py` |
| 베이시스 | 선물-현물 basis와 fair-value 대비 `basis_dev`, `basis_dev_ma5` 산출 | `services/market_structure_collector/main.py`, `shared/arbitrage/basis_calculator.py` |
| 미결제약정 | OI 변화 × 가격 방향을 `new_shorts`, `long_liquidation` 등으로 분류 | `services/market_structure_collector/derived.py`, `config/market_risk.yaml` |
| 해외/환율/변동성 | ES/NQ/SOX, USD/KRW, HAR-RV를 score component로 반영 | `config/market_risk.yaml`, `services/market_risk_engine/main.py` |
| 진입 슬리피지 | 스프레드, depth, signal age, 가격 괴리, 변동성 cooldown, cross-asset spread 필터 | `shared/execution/slippage_control.py`, `config/execution.yaml` |
| 계약 상수 | 미니/풀 승수, 틱 크기, 틱 가치, 수수료율 설정화 | `config/execution.yaml` |
| 현물 β 헤지 권고 | Track B 현물 β 노출과 기존 선물 signed notional을 합산해 미니 숏 계약 권고 | `shared/portfolio/hedge.py` |

### 1.2 현재 흐름이 끊긴 부분

| gap | 왜 위험한가 | 현재 증상 |
|---|---|---|
| 롤오버 상태가 신호/리스크/헤지에 공통 입력으로 없음 | 만기 근접 포지션을 새 진입·헤지 권고·night capture가 서로 다르게 볼 수 있음 | day front helper와 night code config가 분리됨 |
| term structure가 단일 basis 수치에 머묾 | 콘탱고/백워데이션의 방향, 심화 속도, 만기효과를 정책으로 쓰기 어려움 | `basis_dev`는 있으나 `basis_regime`, `carry_pressure` 없음 |
| 증거금 사용률/청산가 버퍼 없음 | 손절 기반 리스크가 맞아도 계좌 margin call 위험을 놓칠 수 있음 | RiskManager는 PnL/MDD/position count 중심 |
| Hedge 권고가 실행 가능성 검사를 하지 않음 | 권고 계약 수가 margin/slippage/roll window에서 불가능할 수 있음 | `recommended_short_contracts`는 net β exposure 기준 |
| live/paper enforcement 경계가 흩어짐 | 어떤 gate가 shadow인지 enforce인지 한눈에 보기 어려움 | Market Risk Gate는 shadow, risk_filter/live guard/kill_switch는 별도 |
| 실패 정책이 목적별로 다르지 않음 | 데이터 누락 시 신규 진입은 fail-open이어도 live hedge/margin은 fail-closed가 맞을 수 있음 | 대부분 fail-open 관성 |

---

## 2. 설계 원칙

1. **기존 Market Risk Score를 대체하지 않는다.** 현재 0-100 score와 band는
   시장위험의 상위 신호로 유지한다.
2. **LLM MarketContext에 모든 필드를 밀어 넣지 않는다.** LLM context는 regime,
   signal, risk score, confidence 중심으로 유지하고, 선물 구조화 필드는
   `FuturesMarketContextV2`로 분리한다.
3. **계약·증거금·헤지 상태는 config-driven이다.** 증거금률, roll window, stress
   shock, hedge target ratio는 YAML/env로 둔다.
4. **read-model first.** 모든 신규 엔진은 Redis hash + stream + TTL을 먼저
   발행하고, 대시보드/리포트/테스트에서 shadow 관찰 후 enforcement를 붙인다.
5. **live는 fail-closed, paper/shadow는 fail-open을 기본으로 한다.** 계좌 증거금
   데이터가 없을 때 live 신규 진입·자동 주문은 멈추고, paper는 trace를 남기며 통과한다.
6. **헤지는 계속 advisory-only로 시작한다.** 자동 헤지 주문은 별도 operator
   승인 문서 없이는 도입하지 않는다.
7. **선물 long/short symmetry를 보존한다.** 리스크 게이트는 side별 allow/size만
   판단하고, 방향 자체는 `signal_direction`과 hedge policy가 결정한다.

---

## 3. 제안 아키텍처

```text
market data / broker state
    |
    +--> FuturesContractStatePublisher
    |       Redis: futures:contract:latest
    |       Stream: stream:futures.contract
    |
    +--> MarketStructureCollector / MarketRiskEngine  (existing)
    |       Redis: market:structure:latest, market:risk:latest
    |
    +--> FuturesMarginRiskEngine
    |       Redis: futures:risk:latest
    |       Stream: stream:futures.risk
    |
    +--> FuturesMarketContextPublisher
    |       Reads contract + market structure + market risk + margin risk
    |       Redis: futures:context:latest
    |       Stream: stream:futures.context
    |
    +--> HedgeAdvisorV2
            Reads positions + market risk + contract + margin risk + slippage snapshot
            Redis: portfolio:hedge:latest (expanded contract)
            Stream: stream:portfolio.hedge
```

Runtime consumers:

- `services/decision_engine`: 신규 진입 candidate에 contract/risk gate trace를 붙인다.
- `services/risk_filter`: existing 8-filter chain 뒤에 optional margin/roll filters를
  추가한다.
- `services/order_router`: live mode에서 margin state가 stale/missing이면 skip한다.
- `services/portfolio_monitor`: hedge advice v2를 equity snapshot 뒤에 계산한다.
- Dashboard `/market`, `/risk`, `/signals`: latest/read-only 상태와 would-block 이유를 보여준다.

---

## 4. 데이터 계약

### 4.1 `FuturesContractState`

Redis:

- latest key: `futures:contract:latest`
- stream: `stream:futures.contract`
- TTL: 24h, close/premarket 스케줄에는 48h fallback을 허용

필드:

| field | type | 설명 |
|---|---|---|
| `schema_version` | int | 시작값 1 |
| `product` | str | `mini` 또는 `kospi200` |
| `front_symbol` | str | 현재 day-session front code |
| `next_symbol` | str | 다음 월물 code |
| `night_front_symbol` | str | 야간장 8-char code |
| `night_next_symbol` | str | 야간장 다음 월물 code |
| `expiry_date` | date | front 만기일 |
| `next_expiry_date` | date | next 만기일 |
| `days_to_expiry` | int | KST trade date 기준 |
| `roll_state` | enum | `normal`, `pre_roll`, `roll_required`, `expired`, `unknown` |
| `roll_reason` | str | `days_to_expiry<=N`, `liquidity_flip`, `manual_override`, `missing_master` |
| `new_entry_front_allowed` | bool | front 신규 진입 허용 여부 |
| `hedge_front_allowed` | bool | front로 헤지 추가 허용 여부 |
| `source` | str | `calendar`, `kis_short_code`, `night_master`, `manual_override` |
| `asof_ts` | datetime | KST naive ISO |

정책:

- `normal`: 신규 진입과 헤지 모두 front 허용.
- `pre_roll`: front 신규 진입은 shadow 경고, hedge는 기존 정책 유지.
- `roll_required`: front 신규 진입 차단, hedge 신규 계약은 next 또는 no-op 권고.
- `expired`: front 신규 진입 차단, 보유 포지션은 exit/roll advisory를 발행.
- `unknown`: paper는 fail-open trace, live는 fail-closed.

### 4.2 `FuturesMarginRiskState`

Redis:

- latest key: `futures:risk:latest`
- stream: `stream:futures.risk`
- TTL: 5-15분. 계좌 상태는 짧게 둔다.

필드:

| field | type | 설명 |
|---|---|---|
| `schema_version` | int | 시작값 1 |
| `account_equity_krw` | float | 계좌 평가금 또는 설정 fallback |
| `cash_available_krw` | float | 주문 가능 현금/증거금 대용 |
| `initial_margin_required_krw` | float | 현재 포지션 기준 위탁증거금 추정 |
| `maintenance_margin_required_krw` | float | 유지증거금 추정 |
| `margin_usage_pct` | float | `initial_margin_required / account_equity` |
| `maintenance_buffer_krw` | float | `equity - maintenance_margin_required` |
| `maintenance_buffer_pct` | float | equity 대비 buffer |
| `liquidation_buffer_points` | float | 계좌가 유지증거금까지 견딜 수 있는 adverse points |
| `liquidation_buffer_ticks` | float | tick 단위 buffer |
| `stress_loss_1atr_krw` | float | 1 ATR adverse move 손실 |
| `stress_loss_2atr_krw` | float | 2 ATR adverse move 손실 |
| `stress_loss_gap_krw` | float | overnight/event shock 손실 |
| `max_additional_contracts` | int | 현재 margin policy에서 추가 가능한 계약 수 |
| `risk_level` | enum | `ok`, `watch`, `reduce_only`, `block_new_entries`, `critical` |
| `degraded` | bool | 계좌/가격/스펙 일부 결측 |
| `missing_components` | list[str] | 결측 source |
| `asof_ts` | datetime | KST naive ISO |

계산 정책:

- 실제 broker margin rate를 읽을 수 없으면 `config/futures_margin.yaml`의
  conservative initial/maintenance rate를 사용한다.
- live에서 account snapshot이 missing/stale이면 `risk_level=critical`로 취급한다.
- paper에서는 `degraded=true` + trace만 남기고 기존 평가를 유지한다.

### 4.3 `FuturesMarketContextV2`

목적은 LLM용 서술 context가 아니라, 전략/게이트가 읽을 구조화 context다.

Redis:

- latest key: `futures:context:latest`
- stream: `stream:futures.context`
- TTL: 24h

필드:

| group | fields |
|---|---|
| contract | `front_symbol`, `days_to_expiry`, `roll_state`, `new_entry_front_allowed` |
| basis | `basis`, `basis_dev`, `basis_dev_ma5`, `basis_regime`, `carry_pressure` |
| OI | `fut_oi_qty`, `fut_oi_change`, `oi_price_signal` |
| foreign flow | `fut_foreign_net_qty`, `fut_foreign_net_qty_cum20`, `foreign_flow_regime` |
| risk score | `market_risk_score`, `market_risk_band`, `unified_regime` |
| margin | `margin_usage_pct`, `liquidation_buffer_ticks`, `margin_risk_level` |
| execution | `slippage_guard_state`, `spread_ticks`, `depth_ratio`, `tick_value_krw` |
| health | `degraded`, `missing_components`, `asof_ts` |

Derived labels:

- `basis_regime`: `deep_backwardation`, `backwardation`, `fair`, `contango`,
  `deep_contango`.
- `carry_pressure`: 만기까지 남은 일수로 보정한 `basis_dev` 압력.
- `foreign_flow_regime`: `strong_sell`, `sell`, `neutral`, `buy`, `strong_buy`.
- `margin_risk_level`: `ok`, `watch`, `reduce_only`, `block_new_entries`, `critical`.

### 4.4 `HedgeAdviceV2`

기존 `portfolio:hedge:latest` 18필드는 하위호환 유지한다. 새 필드는 append-only로
추가한다.

추가 필드:

| field | type | 설명 |
|---|---|---|
| `target_hedge_ratio` | float | 밴드/레짐/운영정책 기준 목표 헤지 비율 |
| `current_hedge_ratio` | float | 현재 선물 노출 / 현물 β 노출 |
| `delta_short_contracts` | int | 목표까지 필요한 추가/축소 숏 계약 |
| `max_contracts_by_margin` | int | margin policy상 가능한 추가 계약 |
| `margin_after_hedge_pct` | float | 권고 실행 후 예상 margin usage |
| `estimated_slippage_ticks` | float | hedge 수량 기준 예상 진입 slippage |
| `roll_adjustment` | str | `none`, `use_next`, `close_front_first`, `manual_review` |
| `execution_feasibility` | enum | `feasible`, `limited_by_margin`, `limited_by_liquidity`, `blocked_by_roll`, `degraded` |
| `operator_action` | enum | `none`, `review`, `place_manual_hedge`, `reduce_existing_hedge`, `roll_position` |

목표 헤지비율 기본안:

| Market Risk Band | target hedge ratio |
|---|---:|
| LOW | 0.00 |
| NEUTRAL | 0.00 |
| ELEVATED | 0.25 |
| HIGH | 0.50 |
| CRITICAL | 0.75 |

조정:

- `margin_risk_level in {reduce_only, block_new_entries, critical}`이면 추가 hedge를
  자동 권고하지 않고 `operator_action=review`로 둔다. 필요 시 기존 포지션 축소가 우선이다.
- `roll_state in {roll_required, expired}`이면 front 추가 hedge를 막고 next 사용 또는
  수동 rollover review를 권고한다.
- `estimated_slippage_ticks`가 config threshold를 넘으면 계약 수를 줄이거나
  `limited_by_liquidity`로 둔다.

---

## 5. 게이트/정책 매트릭스

### 5.1 신규 진입

| 상태 | paper/shadow | live/enforce |
|---|---|---|
| `market_risk.degraded=true` | fail-open trace | 기존 Market Risk Gate 정책 유지 |
| `contract.roll_state=pre_roll` | would-warn | size factor 감소 또는 front 신규 진입 차단 |
| `contract.roll_state=roll_required/expired` | would-block | 신규 front 진입 차단 |
| `margin_risk_level=watch` | trace | size factor 감소 |
| `margin_risk_level=reduce_only` | would-block | 신규 진입 차단, exit만 허용 |
| `margin_risk_level=block_new_entries/critical` | would-block | 신규 진입 차단 |
| slippage guard block | 현행 정책 | 현행 정책 |

### 5.2 헤지 권고

| 상태 | 권고 |
|---|---|
| net β exposure <= 0 | 추가 숏 0, 기존 과헤지 여부만 표시 |
| target ratio > current ratio, margin ok, liquidity ok | `place_manual_hedge` 권고 |
| target ratio > current ratio, margin 부족 | `review`, 계약 수 margin cap까지 제한 |
| roll_required | next 사용 또는 manual roll review |
| CRITICAL + margin critical | 신규 헤지보다 포지션 축소/리스크 오프 우선 |
| price/margin/contract stale | 권고 0, degraded + missing components |

### 5.3 청산/축소

자동 청산은 이 문서의 목표가 아니다. 다만 아래 상태는 반드시 operator-facing
action으로 보여야 한다.

- `liquidation_buffer_ticks`가 `config.futures_margin.critical_buffer_ticks`보다 작음.
- `stress_loss_1atr_krw`가 maintenance buffer를 초과.
- `roll_state=expired`인데 open futures position이 존재.
- front 포지션이 roll window 안에 있고 next liquidity가 충분함.

---

## 6. 설정 파일 제안

새 파일: `config/futures_margin.yaml`

```yaml
futures_margin:
  enabled: true
  account_snapshot_max_age_seconds: 300
  price_max_age_seconds: 30
  product_defaults:
    kospi200_mini:
      initial_margin_rate: 0.08
      maintenance_margin_rate: 0.06
      stress_gap_points: 5.0
    kospi200_full:
      initial_margin_rate: 0.08
      maintenance_margin_rate: 0.06
      stress_gap_points: 5.0
  thresholds:
    watch_margin_usage_pct: 0.45
    reduce_only_margin_usage_pct: 0.65
    block_new_entries_margin_usage_pct: 0.80
    critical_margin_usage_pct: 0.90
    watch_liquidation_buffer_ticks: 80
    critical_liquidation_buffer_ticks: 40
  redis:
    latest_key: "futures:risk:latest"
    latest_ttl_seconds: 900
    stream_key: "stream:futures.risk"
    stream_maxlen: 5000
    stream_ttl_seconds: 900
```

새 파일: `config/futures_contract.yaml`

```yaml
futures_contract:
  enabled: true
  product: "${FUTURES_TRADING_PRODUCT:mini}"
  roll:
    pre_roll_days: 5
    block_front_new_entries_days: 2
    require_roll_on_expiry_day: true
    liquidity_flip_enabled: false
  night_master:
    enabled: true
    stale_after_days: 20
    manual_override_allowed: true
  redis:
    latest_key: "futures:contract:latest"
    latest_ttl_seconds: 86400
    stream_key: "stream:futures.contract"
    stream_maxlen: 5000
    stream_ttl_seconds: 86400
```

새 section: `config/hedge_advisor.yaml::risk_adjustment`

```yaml
risk_adjustment:
  target_hedge_ratio_by_band:
    LOW: 0.0
    NEUTRAL: 0.0
    ELEVATED: 0.25
    HIGH: 0.50
    CRITICAL: 0.75
  max_estimated_slippage_ticks: 2.0
  require_margin_state: true
  require_contract_state: true
  margin_limited_action: "review"
  roll_limited_action: "review"
```

---

## 7. 구현 단계

### Phase A — Contract State read-model

목표: 만기/롤오버/야간코드 상태를 단일 Redis 계약으로 발행한다.

작업:

1. `shared/instruments/futures.py`에 front/next contract 상태 계산 helper 추가.
2. `services/futures_contract/main.py` one-shot publisher 추가.
3. `config/futures_contract.yaml` 추가.
4. `night_futures_collector`가 수동 `tr_key`만 읽지 않고 contract state를 우선 참조하게 한다.
5. Dashboard health에 `roll_state`, `days_to_expiry`, `night_front_symbol` 표시.

검증:

- 만기 전 5/2/0/만기+1일 fixture.
- mini/full product 모두.
- night symbol missing이면 `roll_state=unknown`, live fail-closed trace.

### Phase B — Margin Risk Engine

목표: 증거금/청산 버퍼를 포지션과 계좌 상태에서 계산해 발행한다.

작업:

1. `shared/risk/futures_margin.py` 순수 계산 모듈 추가.
2. `services/futures_margin_risk/main.py` one-shot 또는 short interval daemon 추가.
3. broker account snapshot reader interface 추가. 실제 KIS 계좌 응답이 불안정하면
   첫 버전은 injected provider + config fallback을 사용한다.
4. `futures:risk:latest` Redis 계약과 RuntimeLedger risk event 기록 추가.
5. `/risk`와 `/market`에 margin usage, liquidation buffer, stress loss 표시.

검증:

- long/short 손익 부호 대칭.
- mini/full tick value와 multiplier 일치.
- stale account snapshot: paper degraded, live critical.
- stress loss가 maintenance buffer를 넘으면 `risk_level>=reduce_only`.

### Phase C — FuturesMarketContextV2

목표: 기존 market risk score, contract state, margin risk, slippage snapshot을
전략/게이트가 읽을 하나의 구조화 context로 묶는다.

작업:

1. `shared/models/futures_context.py` Pydantic 모델 추가.
2. `services/futures_context/main.py` publisher 추가.
3. `services/decision_engine/context_provider.py`가 기존 Setup context는 유지하되,
   optional `futures_context`를 trace metadata에 붙이도록 확장.
4. `services/futures_monitor/serializers.py`와 `/signals` trace에 degraded/missing 표시.

검증:

- upstream key 하나씩 결측될 때 context는 발행되며 missing_components가 채워진다.
- LLM `MarketContext.risk_score`와 composite `market_risk_score` 명칭 혼동 없음.

### Phase D — HedgeAdvisorV2

목표: 권고 계약 수를 목표 헤지비율, margin cap, roll state, slippage constraint로
제한한다. 자동 주문은 추가하지 않는다.

작업:

1. 기존 `shared/portfolio/hedge.py`에 append-only v2 fields 추가.
2. `compute_hedge_advice`를 작은 내부 함수로 분리:
   - exposure fold
   - target hedge ratio
   - contract delta
   - margin feasibility
   - roll feasibility
   - slippage feasibility
3. `services/portfolio_monitor/hedge_advisor.py`가 `futures:contract:latest`,
   `futures:risk:latest`, slippage snapshot을 읽는다.
4. Dashboard Hedge card에 `execution_feasibility`, `operator_action`,
   `margin_after_hedge_pct`, `roll_adjustment`를 표시한다.

검증:

- 기존 18필드 계약 하위호환.
- margin cap이 권고 계약 수를 줄이는 케이스.
- roll_required에서 front 추가 hedge 차단.
- stale/missing risk state에서 권고 0 + degraded.
- execution import 금지 가드 유지.

### Phase E — Enforcement wiring

목표: 충분한 shadow 관찰 후 operator가 개별 게이트를 enforce로 켤 수 있게 한다.

작업:

1. `market_risk_gate`와 별도 `futures_operational_risk_gate`를 분리한다.
2. `decision_engine` candidate trace에 market/contract/margin/slippage gate를 모두 기록.
3. `risk_filter`는 margin/roll filters를 optional append한다.
4. `order_router` live mode는 `futures:risk:latest` stale/missing이면 fail-closed.
5. runbook에 shadow 기간, acceptance metrics, rollback command를 추가한다.

검증:

- `mode=shadow`: would-block만 기록, 주문 수량 변화 없음.
- `mode=enforce`: 신규 진입 차단/size factor 적용.
- exit/force-close path는 막지 않음.
- CRITICAL 상태에서도 헤지/청산성 주문과 신규 진입 구분.

---

## 8. 테스트 전략

### Unit

- contract calendar: 월물, 만기일, pre-roll/roll-required/expired.
- basis regime: contango/backwardation/deep labels.
- margin math: long/short, mini/full, tick value, stress loss, stale inputs.
- hedge v2: ratio target, margin cap, roll block, slippage limit, degraded outputs.
- gate: shadow/enforce/fail-open/fail-closed matrix.

### Integration

- market structure -> market risk -> futures context -> decision_engine trace.
- portfolio_monitor -> hedge v2 -> Redis latest/stream -> dashboard parser.
- order_router live guard with stale/missing margin state.
- scheduler one-shot order: contract state before night/market risk/hedge jobs.

### Replay / shadow validation

- 최소 10 trading days:
  - would-block count
  - would-size-reduce count
  - margin critical false positive
  - roll window warnings
  - hedge recommendation changes vs existing advisor
  - slippage-limited hedge counts
- enforce 전환 전 operator report:
  - blocked trades that would have won/lost
  - avoided drawdown estimate
  - hedge residual exposure distribution

---

## 9. 운영 / 스케줄

권장 크론 순서(KST):

```text
05:45 futures_contract premarket
05:48 night_futures_collector
08:00 market_structure premarket
08:05 market_risk premarket
08:10 futures_margin_risk premarket
08:15 futures_context premarket
08:50 portfolio_monitor + hedge_advisor

09:00-15:30 market_risk intraday every 30m
09:00-15:30 futures_margin_risk every 1-5m
09:00-15:30 futures_context every 1-5m

18:40 market_structure close
18:45 market_risk close
18:50 futures_margin_risk close
18:55 futures_context close
19:00 portfolio_monitor + hedge_advisor
```

주말/휴일 정책:

- contract state는 휴일에도 발행 가능하다.
- market structure와 risk score는 market calendar를 따른다.
- hedge advice는 최신 market risk/contract/margin timestamp를 각각 표시하고,
  stale이면 권고 0 + degraded로 발행한다.

---

## 10. 리스크와 대응

| 리스크 | 대응 |
|---|---|
| KIS 계좌 증거금 API shape 불안정 | provider interface + config fallback + live fail-closed |
| night master 자동 갱신 실패 | `roll_state=unknown`, manual override field, dashboard alert |
| 증거금률 config가 실제와 다름 | 보수적 default + operator review + monthly validation |
| hedge v2 필드가 UI/API 하위호환 깨뜨림 | append-only 필드, 기존 18필드 고정 테스트 |
| Market Risk Score와 FuturesContext 역할 혼동 | score는 상위 regime, context는 선물 운영 상태로 문서/API 명칭 분리 |
| CRITICAL에서 hedge가 오히려 margin을 악화 | margin risk가 `critical`이면 추가 hedge 대신 exposure reduction review |
| roll_required에서 기존 포지션 exit까지 막힘 | 신규 진입 gate와 exit/force-close path 분리 테스트 |

---

## 11. 완료 기준

Phase A-D 완료 기준:

- `futures:contract:latest`, `futures:risk:latest`, `futures:context:latest`,
  expanded `portfolio:hedge:latest`가 모두 Redis DB 1에 TTL과 stream으로 발행된다.
- Dashboard는 contract/margin/hedge feasibility를 read-only로 표시한다.
- 기존 Market Risk Score, LLM MarketContext, Hedge 18필드 계약이 깨지지 않는다.
- paper/shadow 모드에서 주문 수량과 주문 여부가 기존과 bit-for-bit 동일하다.
- 10 trading days shadow report에 false stale, false critical, excessive block
  후보가 정리된다.

Phase E 완료 기준:

- operator가 `market_risk_gate`, `futures_operational_risk_gate`,
  `live_mode_guard`의 mode를 각각 독립적으로 켜고 끌 수 있다.
- live 신규 진입은 stale/missing margin state에서 fail-closed한다.
- exit/force-close/수동 청산성 주문은 신규 진입 gate에 막히지 않는다.
- runbook에는 enable, rollback, Redis key inspection, expected dashboard state가 있다.

---

## 12. 다음 작업 제안

1. **Phase A + B를 먼저 구현한다.** Contract state와 Margin risk는 다른 모든
   보강의 기반이다.
2. 그 다음 **Phase C read-model**을 붙여 decision trace와 dashboard에서 shadow
   관찰을 시작한다.
3. **HedgeAdvisorV2는 Phase A/B/C가 발행한 상태를 읽도록 보강**한다.
4. Enforcement는 최소 10 trading days shadow report와 operator 승인 뒤 별도
   plan으로 진행한다.

이 순서가 가장 안전하다. 기존 market risk/hedge/strategy 경로의 행동을 바로
바꾸지 않고, 먼저 누락된 운영 상태를 관찰 가능한 read-model로 만든다.
