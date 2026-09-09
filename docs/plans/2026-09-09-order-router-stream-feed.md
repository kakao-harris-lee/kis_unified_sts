# order-router 피드 소스 전환 — 자체 KIS WS 대신 `raw_data` 스트림 소비 (DUAL-WS 해소)

작성 2026-09-09 · 세션 모델 단독 저작(운영자 지시 2026-09-04) · 기준 main `8a31038c` · 상태 **초안 → 운영자 "설계 변경 방식으로 계획 작성해서 진행" 지시(2026-09-09)에 따라 구현 착수**

배경: F-9 Gate 1b 의 `slippage_gate: blocked` 실측은 `futures-order-router` 안에서만 나오는데, order-router 는 자체
KIS 선물 WebSocket 을 열고 그 연결이 `trader-futures`(orchestrator) 와 같은 계정을 경합한다. 2026-09-07/08 양방향
실측으로 "같은 계정 선물 WS 2연결 불가, 먼저 잡은 쪽이 유지되고 나중 연결이 즉시 끊김" 이 확정됐고(09-08 08:45~09:15
orchestrator raw_data 25분 정지, order-router 정지로 복구), 그 뒤 order-router 는 정지 상태다. Setup D 편입(PR #660)으로
섀도 후보는 나오기 시작했지만 order-router 가 꺼져 있는 한 거부 실측은 구조적으로 0 이다. 이 문서는 order-router 가
WS 를 열지 않고 다른 프로세스가 발행하는 데이터를 소비하도록 바꾸는 최소 변경을 정의한다.

## 0. 측정 (main `8a31038c`)

### 0-1. order-router 가 피드에서 실제로 쓰는 것

| 소비처 | 호출 | 필요 데이터 |
|---|---|---|
| 슬리피지 게이트(F-9 Gate 1b) | `services/order_router/main.py:~553-566` `feed.get_orderbook_snapshot(symbol)` → `FuturesSlippageController.evaluate_entry` | `bid_price_1/ask_price_1/bid_qty_1/ask_qty_1/spread/timestamp` (스프레드 틱·잔량 배수·호가 신선도 `max_price_staleness_seconds: 30`, `config/execution.yaml:255`) |
| 변동성 쿨다운 틱 등록 | `main.py:~952` `feed.set_tick_callback(_register_slippage_tick)` | 체결 틱 `(symbol, data{close…}, ts)` |
| PseudoOCO stop/target/만료·close intent | `main.py:~282, ~403` `await feed.get_current_price(symbol)` → `close` | 최신 체결가 |
| paper 체결 시뮬 | `shared/execution/paper_kis_futures_adapter.py:70-112` `feed.get_current_price` + `feed.get_orderbook_snapshot` | 체결가 + 최우선 호가 |
| 피드 헬스 발행 | `feed.get_staleness_seconds()/get_health_status()/is_healthy()` (`tests/unit/services/test_feed_observability.py`) | 신선도·드롭 카운트 |
| 심볼 등록 | `feed.update_symbols([symbol], auxiliary_symbols=[cross_asset])` (`main.py:~928`) | cross-asset 은 paper 에서 `enabled: false` |

자체 WS 를 쓰는 이유는 코드 주석에 있다(`main.py:~905-908`): "KIS 모의투자 serves no futures realtime feed, so the real WS
is the only orderbook source". 즉 필요한 것은 **실전 계정의 실시간 호가·체결**이지 "order-router 자신의 연결" 이 아니다.

### 0-2. 이미 발행되고 있는 것

- **orchestrator**: `services/trading/orchestrator.py:1104-1154` `_on_futures_tick` 은 `KISFuturesPriceFeed` 의 **체결 틱 콜백**이다.
  `monitor_data = dict(data)` 로 `self._tick_stream_publisher.publish("futures", symbol, monitor_data)` 하는데, `data` 는 피드가
  콜백에 넘기는 **체결 전용 페이로드**(`shared/kis/futures_feed.py:530-556`: `self._tick_callback(tick.symbol, payload, ts)` — 병합
  `_prices` dict 가 아니다). 즉 producer 측 dict 에도 `bid_price_1/ask_price_1/bid_qty_1/ask_qty_1/spread` 가 **없다**. (초안은
  "루프마다 병합 스냅샷 발행" 으로 적었으나 재확인 결과 오류 — 발행 주기는 체결 틱, 실측 분당 ~90건은 체결 빈도다.)
  피드의 병합 스냅샷은 `get_orderbook_snapshot(symbol)`(`futures_feed.py:419-436`) 로만 읽을 수 있다.
- **스키마** `shared/models/stream_models.py::MarketTickMessage`(`:90`, **`extra="ignore"`** — 상위 `StreamMessage` 만 `forbid`)는
  asset/symbol/price/timestamp/name/open/high/low/volume/cumulative_volume/tick_volume/volume_is_cumulative 만 가지며
  `TickStreamPublisher._build_fields` 도 그 필드만 싣는다. 실측 entry: `schema_version, asset, symbol, price, timestamp, open, high,
  low, volume, code, close, current_price` — 호가 없음. 무명 키는 producer·consumer 양쪽에서 **조용히 버려진다**.
- **futures-market-ingest**(컷오버 후 WS 소유자, `services/market_ingest/main.py:~201-206`): 같은 체결 틱 콜백 `data` 를 그대로
  `publisher.publish`. 호가 전용 틱(H0IFASP0)은 두 producer 모두 콜백을 타지 않는다(`payload is None → return`, `:529-530`).
- **소비자**: `shared/streaming/consumer_feed.py::StreamConsumerFeed` 가 decision-engine 에서 이미 `raw_data` 를 XREAD 한다.
  API: `get_current_price`(async) · `update_symbols(symbols)` · `set_tick_callback` · `get_staleness_seconds` · `is_healthy` ·
  `get_health_status` · `supports_instant_read` · `start/stop`. **없는 것**: `get_orderbook_snapshot`, `update_symbols(...,
  auxiliary_symbols=)`. 엔트리 파싱은 `decode → MarketTickMessage → to_price_dict()` 라 스키마에 없는 필드는 여기서도 버려진다.
- **동일 계약 근거**: `KISFuturesPriceFeed.get_orderbook_snapshot` 의 폴백 분기(`futures_feed.py:419-436`)는 이미 "`_prices`
  병합 dict 에서 `code/timestamp/bid_price_1/bid_qty_1/ask_price_1/ask_qty_1` 만 추린다" — 스트림에서 같은 필드를 복원해 같은 dict
  를 돌려주면 게이트·paper 어댑터 입장에서 소스 차이가 없다.

### 0-3. 갭 (여섯, 전부 배선)

1. **스키마**: `MarketTickMessage` 에 호가 필드가 없다 → 선택적 필드 5개 추가(`bid_price_1, bid_qty_1, ask_price_1, ask_qty_1, spread`),
   `_build_fields`/`to_price_dict` 가 있을 때만 싣고 돌려준다. `extra="ignore"` 유지(현행 — 무명 키는 계속 무시, 명시 필드만 흐른다).
2. **producer 두 곳**: 체결 틱 페이로드에 호가 병합. 공용 헬퍼 `orderbook_publish_fields(snapshot)`(`tick_stream_publisher.py`,
   bid·ask > 0 일 때만 5키 반환, 아니면 `{}`)을 (a) ingest `_on_tick`(futures 만) 과 (b) orchestrator `_on_futures_tick` 의 **publish
   블록만**(`orchestrator.py:~1146-1154`, `getattr(feed, "get_orderbook_snapshot", None)` 가드) 에서 호출. orchestrator 의 다른
   코드는 손대지 않는다.
3. **소비자**: `StreamConsumerFeed.get_orderbook_snapshot(symbol)` 추가(WS 피드 폴백 분기와 같은 키 집합 + `spread`), `update_symbols`
   에 `auxiliary_symbols` 키워드 수용(스트림 모드에선 producer 가 구독하는 심볼만 흐르므로 경고 로그 후 무시).
4. **콜드 스타트**: `StreamConsumerFeed` 는 `_last_id="$"` 로 시작해 다음 틱까지 아무것도 모른다(`consumer_feed.py:75,159-202`).
   `seed_latest=True, seed_count=50` 옵션 — `start()` 가 `XREVRANGE stream + - COUNT n` 으로 구독 심볼의 최신 entry 를 먼저 적용하고
   `$` 부터 이어 읽는다(재생 없음, 신선도는 seed entry 의 producer timestamp 기준). router 만 켠다.
5. **호가 신선도 게이트(fail-closed)**: `FuturesSlippageController.evaluate_entry` 는 `max_signal_age_seconds` 만 보고 **호가
   timestamp 는 검사하지 않는다**(`slippage_control.py:~410-442`; `paper_broker.max_price_staleness_seconds` 는 VirtualBroker 체결
   가드로 별개). 스트림은 체결 틱마다만 갱신되므로 체결 공백 구간의 호가가 stale-but-parseable 로 게이트를 통과할 수 있다 →
   `order_router_gate` 선례(`execution.yaml:199-200`, 모놀리식은 무시)를 따라 `futures_slippage_control.
   order_router_max_quote_age_seconds: ${FUTURES_ROUTER_MAX_QUOTE_AGE_SECONDS:10}`(0 = 비활성) 추가, router 가 `evaluate_entry`
   직전에 `quote_stale:<age>s` 로 차단(`slippage_blocked_count` 증가, 기존 `signal_timestamp_missing` 분기와 같은 로그 형식). 나이
   계산은 `slippage_control.py` 의 공개 헬퍼로(타임스탬프 파싱 중복 금지). ws 모드에도 동일 적용(피드가 아니라 게이트의 속성).
6. **order-router 피드 선택**: env `FUTURES_ORDER_ROUTER_FEED=stream|ws`(compose 배선, 기본 `stream`). `stream` 은
   `StreamConsumerFeed(redis, stream=FUTURES_TICK_STREAM, seed_latest=True)` 을 만들고 WS·approval key 를 **열지 않는다**; `ws` 는
   현행 자체 피드(ingest 가 없는 배치용 명시 opt-in). `PaperKISFuturesAdapter` 는 피드 객체를 duck-typing 하므로 무변경.

### 0-4. 신선도·주기 검토

- 섀도(현재)·컷오버 후 모두: producer 는 **체결 틱마다** 발행(orchestrator 콜백 / ingest 콜백, 세션 중 실측 ~1.5/s; publisher 심볼
  스로틀 `futures_min_interval_seconds` 0.2s, 배치 conflation). 발행 시점에 피드 캐시의 최신 호가(H0IFASP0 로 갱신)를 병합하므로
  체결이 흐르는 동안 호가 나이 ≤ 체결 간격. 게이트는 entry 의 `timestamp`(producer 틱 시각, 소비 시각 아님)를 쓴다 — 소비자
  `to_price_dict` 가 보존.
- 체결 공백 구간(>`order_router_max_quote_age_seconds`, 기본 10s): 마지막 entry 의 호가가 stale 이므로 router 게이트가 `quote_stale`
  로 차단한다(모놀리식의 인메모리 캐시는 H0IFASP0 로 계속 갱신되므로 이 점이 모놀리식과 다르다 — 문서화된 한계). 전방월 KOSPI200
  세션 중엔 드문 조건. 후속(§8): 호가 전용 틱 발행 또는 ingest REST 폴링 경로(`INGEST_REFRESH_SECONDS`)의 주기 발행.
- 스트림 부하: entry 당 필드 5개 증가(문자열 ~60B). maxlen 10,000·TTL 24h(`TickStreamPublisherConfig`) 불변.

## 1. 목표 · 범위

- 목표: order-router 가 KIS WS 를 열지 않고도 슬리피지 게이트·PseudoOCO·paper 체결을 돌려, orchestrator 와 **동시에** 섀도 운전이
  가능해지고 Gate 1b `slippage_gate: blocked` 실측이 열린다.
- 범위 안: 스트림 스키마 확장, ingest 호가 병합, `StreamConsumerFeed.get_orderbook_snapshot`, router 피드 선택, compose/env 템플릿,
  테스트(스키마·소비자·WS↔스트림 스냅샷 파리티·router 팩토리), 런북 DUAL-WS 절 교체.
- 범위 안(추가): orchestrator `_on_futures_tick` publish 블록의 호가 병합(헬퍼 호출 1줄 + 가드), router `quote_stale` 게이트 + 설정
  키, `StreamConsumerFeed` 콜드 스타트 시딩.
- 범위 밖: `KISFuturesPriceFeed`·WS 어댑터 변경, orchestrator 의 publish 블록 밖 변경, cross-asset(`cross_asset_enabled`) 스트림
  지원(ingest 가 `101S6000` 을 구독하지 않으므로 stream 모드에선 cross 호가 없음 — paper_override 기본 `false`), live
  `KISFuturesAdapter` 의 passive 지정가 호가 의존(스트림 모드 live 는 F-9 Gate 2 이후 별도 검토), ingest 호가 전용 틱 발행(§8).

## 2. 검토한 대안 (기각 사유)

- **호가 전용 스트림 `futures:orderbook` 신설 + 피드에 orderbook 콜백 추가** — H0IFASP0 갱신마다 발행하면 파리티가 더 좋지만
  피드·publisher·소비자 세 곳에 새 경로가 생긴다. 체결 틱에 호가를 병합하는 방식 대비 얻는 것은 "체결 공백 구간의 호가 갱신" 뿐이고
  그 구간은 `quote_stale` 로 fail-closed 처리된다 → 후속 후보(§8), 지금은 기각.
- **`FuturesSlippageController.evaluate_entry` 자체에 호가 나이 검사 추가** — 공유 컨트롤러라 모놀리식 paper 의 동작도 바뀐다. 이번
  범위는 order-router 이므로 `order_router_gate` 선례대로 router 전용 키로 한정(모놀리식 무영향). 컨트롤러 승격은 Gate 2 검토 항목.
- **order-router 가 REST 로 호가를 조회** — 게이트 호출 시점마다 REST 왕복(레이트리밋 5 req/s 공유), paper 체결 시뮬도 REST 의존.
  스트림이 이미 있는데 두 번째 데이터 경로를 만드는 셈 → 기각.
- **trader-futures 정지 창에서만 order-router 운전** — Gate 1 의 "orchestrator raw_data 재사용" 전제와 충돌하고 paper 포지션 관리를
  세션 중 멈춰야 함 → 기각(운영자도 설계 변경을 선택).
- **`StreamConsumerFeed` 를 복제해 router 전용 피드 클래스 작성** — DRY 위반. 기존 클래스에 메서드 하나·키워드 하나 추가로 충분.
- **`MarketTickMessage` 를 `extra="allow"` 로 완화** — 무명 필드가 조용히 흐르는 것이 #533/#537 류 사고의 원인. 현행 `extra="ignore"`
  유지, 명시 필드 추가만.

## 3. 변경 (신규 모듈 0)

### 3-A. `shared/models/stream_models.py` · `services/monitoring/tick_stream_publisher.py`
- `MarketTickMessage`: `bid_price_1: float | None`, `bid_qty_1: float | None`, `ask_price_1: float | None`, `ask_qty_1: float | None`,
  `spread: float | None` (전부 optional, `ge=0` 검증). `to_price_dict()` 는 값이 있을 때만 키를 포함.
- `_build_fields`: 위 5키를 payload 에서 있을 때만 싣는다. `schema_version` 은 필드 추가가 하위호환(optional)이므로 **불변**; 소비자
  `decode` 가 옛 entry 도 그대로 파싱해야 한다(테스트로 고정).
- `orderbook_publish_fields(snapshot: Mapping) -> dict`: producer 공용 헬퍼. bid·ask 가 모두 > 0 일 때만 5키를 돌려주고 아니면 `{}`.

### 3-B. producer 두 곳
- `services/market_ingest/main.py` `_on_tick`(futures 만): `data = {**data, **orderbook_publish_fields(feed.get_orderbook_snapshot(symbol))}`
  — 호가 캐시가 비면 병합 없음. stock 은 무변경(`asset == "futures"` 분기).
- `services/trading/orchestrator.py` `_on_futures_tick` publish 블록(`:~1146-1154`)만: `monitor_data.update(orderbook_publish_fields(
  snapshot_fn(symbol)))` — `snapshot_fn = getattr(self._futures_price_feed, "get_orderbook_snapshot", None)` 가 없으면 건너뜀. 다른
  줄은 무접촉.

### 3-C. `shared/streaming/consumer_feed.py`
- `get_orderbook_snapshot(symbol) -> dict`: 캐시된 price dict 에서 `code/timestamp/bid_price_1/bid_qty_1/ask_price_1/ask_qty_1/spread`
  를 추려 반환, 없으면 `{}` — `KISFuturesPriceFeed.get_orderbook_snapshot` 폴백 분기와 **동일 키 집합**.
- `update_symbols(symbols, auxiliary_symbols=None)`: 키워드 수용, aux 가 있으면 "stream 모드는 producer 구독 심볼만 흐름" WARNING.
- `get_health_status()` 에 `orderbook_age_seconds` 추가(호가 신선도 관측).
- `__init__(..., seed_latest: bool = False, seed_count: int = 50)`: `start()` 진입 시 `XREVRANGE` 로 구독 심볼의 최신 entry 를
  오래된 순으로 적용 후 `$` 부터 XREAD(§0-3 ④).

### 3-D. `services/order_router/main.py` · `docker-compose.yml` · `.env.*.example`
- `_build_price_feed(mode, redis, symbol, slippage_cfg) -> feed`: `FUTURES_ORDER_ROUTER_FEED` 가 `stream`(기본)이면
  `StreamConsumerFeed(redis=aioredis, stream=os.environ["FUTURES_TICK_STREAM"|"raw_data"], stale_threshold_seconds=slippage_cfg.
  max_price_staleness_seconds)`; `ws` 면 현행 `KISFuturesPriceFeed`. 기동 로그 1줄: `order_router feed=stream stream=raw_data (no KIS
  WS opened)` / `feed=ws`. cross-asset 이 켜져 있고 `stream` 이면 WARNING 후 cross 호가 없이 진행(게이트의 `cross_asset` 검사는
  `permissive_on_missing` 의미론을 따른다 — 확인해 문서화).
- compose `futures-order-router`: `FUTURES_ORDER_ROUTER_FEED: "${FUTURES_ORDER_ROUTER_FEED:-stream}"`, `FUTURES_TICK_STREAM` 전달
  (decision-engine 과 동일 표현식). `.env.paper.example`/`.env.live.example` + 템플릿 테스트.
- `ws` 모드일 때만 `x-kis-runtime-env` 자격증명이 필요하다는 점을 주석으로 명시(env 자체는 유지 — REST 주문 경로가 쓴다).
- **`quote_stale` 게이트**(§0-3 ⑤): `config/execution.yaml` `futures_slippage_control.order_router_max_quote_age_seconds:
  ${FUTURES_ROUTER_MAX_QUOTE_AGE_SECONDS:10}` → `SlippageControlConfig.order_router_max_quote_age_seconds`(`from_dict`) → router
  `_execute_signal` 이 `evaluate_entry` 직전에 `quote_age_seconds(quote_payload, now)`(`slippage_control.py` 공개 헬퍼) 로 판정.
  빈 payload 는 컨트롤러의 `orderbook_unavailable` 에 맡긴다.

### 3-E. 문서
- `docs/runbooks/futures-pipeline-cutover-f9.md`: DUAL-WS CAVEAT 절을 "stream 모드 기본, WS 는 opt-in; Gate 1 은 order-router 를
  orchestrator 와 동시에 운전" 으로 교체, Gate 1 체크리스트에 "order-router 로그에 `Approval key obtained`/`[KIS WS]` 가 없고
  `feed=stream` 이 찍힌다" 추가, Live-path requirements 의 Dual-WS 항목 갱신, §0-4 신선도 한계(컷오버 후 체결 부재 구간) 기록.

## 4. 검증

단위(hermetic):
- 스키마: 호가 필드 있는/없는 entry 모두 `decode` 가능(하위호환), `to_price_dict` 키 포함 규칙, `_build_fields` 가 5키를 싣고 무명
  키는 여전히 거부.
- **파리티 계약 테스트**: 같은 합성 KIS 호가+체결 틱을 (a) `KISFuturesPriceFeed._on_tick` → `get_orderbook_snapshot`, (b) 콜백
  페이로드 + `orderbook_publish_fields(feed.get_orderbook_snapshot)` → `TickStreamPublisher.publish` → fakeredis →
  `StreamConsumerFeed` → `get_orderbook_snapshot` 로 흘려 두 dict 가 키·값 동일(spread 포함, timestamp = producer 틱 시각).
- 소비자: `auxiliary_symbols` 키워드 수용·경고, `orderbook_age_seconds`, 호가 없는 entry 에서 `{}`, `seed_latest` 시딩(구독 심볼만,
  재생 없음, 신선도 = producer timestamp).
- producer: ingest futures `_on_tick` 병합(호가 캐시 유/무), stock 무변경; orchestrator publish 블록(호가 병합, `get_orderbook_snapshot`
  없는 피드에서 무병합) — 둘 다 fake 로.
- `quote_stale`: 키 파싱(기본·env·0 비활성), 나이 헬퍼(epoch/iso/누락), router 차단 경로(카운터·reason·어댑터 미호출), 신선한 호가는
  `evaluate_entry` 로 통과.
- router: env 별 피드 팩토리(`stream` 이 `KISFuturesPriceFeed` 를 생성하지 않음 — WS 클래스 생성 0 회 assert), 기동 로그, `ws` 는
  현행 그대로; 기존 `_FakeOrderbookFeed` 계열 테스트 무변경 통과.
- compose/템플릿 테스트, ruff/black, tos-firewall, `tests/unit` 2-pass.

paper 서버(운영자 실행, 장외):
1. 머지 후 `trader-futures`(producer 병합)·`futures-order-router`(소비자) 재빌드. **trader-futures 재기동은 장외**(WS 소유자).
   재기동 전까지 `raw_data` 에는 호가가 없으므로 order-router 는 `orderbook_unavailable`/`quote_stale` 로만 차단된다(정상).
2. `futures-order-router` 를 `FUTURES_ORDER_ROUTER_FEED=stream` 으로 기동 → 로그에 `feed=stream`, `[KIS WS]`/`Approval key` 0줄.
3. 다음 세션: `raw_data` 최신 entry 에 `bid_price_1/ask_price_1` 존재, `trader-futures` WS 재연결·breaker 0, order-router 의
   `slippage_gate` 결정 로그(blocked/passed)와 `order.fill.futures.shadow` 체결, `risk:state:futures:shadow` 갱신.
4. 롤백: `FUTURES_ORDER_ROUTER_FEED=ws` 는 **DUAL-WS 를 되살리므로 orchestrator 정지 창에서만** — 평시 롤백은 order-router 정지.

## 5. 수용 기준

- [ ] order-router 가 `stream` 모드에서 KIS WS 를 열지 않는다(테스트 + 기동 로그).
- [ ] `raw_data` entry 가 호가 5필드를 싣고, 옛 entry 도 파싱된다.
- [ ] WS 피드와 스트림 피드의 `get_orderbook_snapshot` 파리티 테스트 통과.
- [ ] `quote_stale` 게이트가 설정 키로 동작하고(0 = 비활성) 모놀리식은 무영향, 콜드 스타트 시딩 테스트 통과.
- [ ] 섀도 세션에서 orchestrator WS 무영향(재연결 0) + order-router `slippage_gate` 결정이 실측된다.
- [ ] 런북 DUAL-WS 절 교체·Gate 1 체크 갱신, `.env.*.example` + 템플릿 테스트.
- [ ] ruff/black/tos-firewall/2-pass green.

## 6. 롤아웃 · 롤백
PR → Claude 측 코드 리뷰 → CI → 머지(운영자) → 장외에 trader-futures·order-router 재빌드·재기동 → 다음 세션 관측. 롤백 =
order-router 정지(스키마 확장은 optional 필드라 producer 롤백 불필요).

## 7. 운영자 결정
| # | 결정 | 권고 |
|---|---|---|
| ① | `FUTURES_ORDER_ROUTER_FEED` 기본값 | `stream` (WS 는 명시 opt-in) |
| ② | cross-asset 호가(paper `enabled: false`) 스트림 지원 | 이번 범위 밖, 켜면 WARNING |
| ③ | 호가 전용 발행(체결 부재 구간 신선도, 섀도·컷오버 공통) | 후속(§8), Gate 2 전 판단 |
| ④ | `order_router_max_quote_age_seconds` 기본 10s(0 = 비활성) | 유지 — 체결 간격 실측(~0.7s) 대비 여유, 30s 체결 공백은 stale 로 봄 |
| ⑤ | orchestrator publish 블록 1줄 변경 허용 | 허용 — 호가 없이는 stream 모드가 성립하지 않음(§0-2 정정) |

## 8. 범위 밖 (정직 기록)
- 호가 전용 틱 발행(H0IFASP0 콜백, producer 두 곳) — 체결 부재 구간의 `quote_stale` 차단을 없애려면 필요. 별도 PR.
- live `KISFuturesAdapter` passive 지정가의 호가 의존 — stream 모드 live 는 Gate 2 검토(현재 live 비활성).
- cross-asset 심볼 스트림 구독 — producer 가 aux 심볼을 구독·발행해야 함.
- order-router 의 `_FakeFeed` 계열 테스트 더블은 그대로 두되, 실제 클래스 파리티는 §4 계약 테스트가 담당.
