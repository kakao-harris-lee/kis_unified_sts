# Order Router Paper Execution (F-3) — Design

- Date: 2026-06-07
- Status: Design (pending implementation plan)
- Parent effort: futures decoupling roadmap ([[futures-decoupling-state]]); **F-3** (the "linchpin" for stock-level paper validation of the decoupled futures chain)
- Scope: **F-3 — a paper execution mode for the decoupled futures `order_router`.** Inject a `PaperKISFuturesAdapter` into the (unchanged) `PassiveMaker` so the daemon reads the REAL orderbook (real WS) but simulates passive-limit fills locally with NO real KIS order. Enables the operator's "real data + local virtual fills, zero real orders" model for the futures execution path — and directly fixes the "orderbook problem in 모의투자" (KIS mock has no futures realtime feed).

## 1. Goal & scope

The decoupled futures `order_router` is real-execution-only: it wires `PassiveMaker` over a real `KISFuturesAdapter` that calls `kis.get_futures_orderbook` (real WS, `H0IFASP0`) and places real KIS orders. Run against KIS 모의투자 (`KIS_FUTURES_MARKET=mock`) it connects to the mock WS which serves NO futures realtime data → the orderbook cache stays empty → `get_futures_orderbook` raises → every signal fails (the "orderbook problem"). And there is no paper path at all, so the chain cannot be validated without real orders.

`PassiveMaker` is already decoupled via a duck-typed `kis_client` interface (`get_futures_orderbook` / `place_futures_order` / `await_fill` / `cancel_order`). F-3 adds a `PaperKISFuturesAdapter` implementing that interface against a REAL feed (real orderbook) + a faithful local fill simulation (no KIS order), and a `FUTURES_ORDER_ROUTER` mode flag selecting paper vs live. `PassiveMaker`, `PseudoOCO`, the `OrderRouterDaemon`, and `FillLogger` are unchanged.

**Success criterion:** `FUTURES_ORDER_ROUTER=paper` runs the order_router with the real futures WS feed (real orderbook) + `PaperKISFuturesAdapter` — passive-limit entries are filled/missed by a faithful tick-watch simulation against the real book, recorded to the local `FillLogger` (SQLite + `order.fill` stream), with ZERO real KIS orders. `=live` uses the real adapter + `LiveModeGuard` (unchanged). `=off` is inert.

비목표(out of scope): orderbook transport / streaming the book (the order_router uses its own real WS like the orchestrator — deferred dual-WS optimization); F-1 stream-naming coherence (separate — full-chain shadow validation also needs F-1; F-3 delivers the paper-execution capability + unit/integration validation); PseudoOCO live-close semantics (it is fill_logger-only — already paper-compatible, unchanged); the LIVE execution path (real adapter + LiveModeGuard unchanged); a mock-KIS-account order path (F-3 paper = local sim, no KIS orders at all).

## 2. Locked decisions (브레인스토밍 2026-06-07)

| 결정 | 선택 | 근거 |
|---|---|---|
| 형태 | **paper kis_client 주입** (PassiveMaker/PseudoOCO/daemon 무변경) | PassiveMaker가 이미 kis_client 인터페이스로 분리 → 어댑터 교체만 |
| 데이터 | **피드 항상 is_real=True(실 오더북) + 실행만 paper/live 분리** | KIS 모의투자는 선물 실시간 미지원 → 실 WS가 유일 오더북 소스. orchestrator의 "is_real 피드 + paper 실행" 분리와 동일 |
| 체결 시뮬 | **틱 관찰 충실 모델** | PassiveMaker의 핵심(패시브 지정가 miss 가능)을 실데이터로 충실 모델링(운영자 검증 목적) |
| 오더북 transport | **deferred** | order_router 자기 실 WS 사용; 스트리밍은 dual-WS 최적화 별도 |
| F-1 의존 | **독립 설계, 전체체인 검증만 F-1 후** | F-3 단독 = paper 어댑터 + 모드 + 단위/통합 검증 |

## 3. Current state (감사 2026-06-07)

- **PassiveMaker** (`shared/execution/passive_maker.py`): `place_passive_limit_futures(*, signal, signal_id, quantity, spec, timeout_seconds)` → `kis.get_futures_orderbook(symbol)` → `limit = round(best_bid if long else best_ask)` → `kis.place_futures_order(...)` → `kis.await_fill(order_id, timeout)` → on fill log via FillLogger; on None → `kis.cancel_order` + `OrderResult.missed`. **kis_client는 duck-typed 인터페이스** (테스트는 AsyncMock 주입). `Fill(order_id, price, quantity, filled_at_ms)`.
- **real `KISFuturesAdapter`** (`shared/execution/kis_futures_adapter.py`): 4 메서드. `get_futures_orderbook(symbol) -> SimpleNamespace(bid=[SimpleNamespace(price=float)], ask=[...])` ← `feed.get_orderbook_snapshot(symbol)` dict(`bid_price_1`/`ask_price_1`), 빈값이면 RuntimeError. `place_futures_order(*, symbol, side, quantity, order_type, price) -> str`(실 executor place+await+autocancel을 한 번에, fill stash). `await_fill(order_id, timeout) -> Fill|None`(stash 조회). `cancel_order(order_id) -> bool`.
- **order_router build** (`services/order_router/main.py:355-400`): `KISAuthConfig(is_real=KIS_FUTURES_MARKET=="real")` → `KISFuturesPriceFeed(config)` → `futures_feed.start()` → `KISFuturesAdapter(order_executor, futures_feed)` → `PassiveMaker(kis_client=adapter, fill_logger)` → `PseudoOCO(fill_logger)` → `OrderRouterDaemon(passive_maker, pseudo_oco, ..., live_mode_guard)`. **모드 플래그 없음**(stock과 달리). 데몬은 `passive_maker.place_passive_limit_futures` 호출(`main.py:247`).
- **PseudoOCO** (`shared/execution/pseudo_oco.py`): `__init__(*, fill_logger)` — **kis_client 없음**. `on_tick`(틱 피드)으로 stop/target 판정 → `_close`가 fill_logger 기록. **실주문 없음 → 이미 paper 호환.**
- **KISFuturesPriceFeed**: `get_orderbook_snapshot(symbol)`(WS H0IFASP0 캐시, `bid_price_1`/`ask_price_1`) + `get_current_price(symbol)`(last trade `close`). 선물 실시간 WS는 **실전 전용**(모의투자 미지원).
- **stock 참조**: `services/stock_order_router/`는 `STOCK_ORDER_ROUTER`(off/shadow) + VirtualBroker paper. (선물은 패시브 지정가라 VirtualBroker 고정슬리피지가 아닌 패시브 sim 필요 — F-3.)

## 4. Components

### 4.1 신규 `shared/execution/paper_kis_futures_adapter.py::PaperKISFuturesAdapter`
실 `KISFuturesAdapter`의 4개 메서드 미러. 실주문 0 — 구조적으로 KIS 주문 호출 경로 없음.
```python
class PaperKISFuturesAdapter:
    def __init__(self, *, futures_price_feed, poll_interval: float = 0.2) -> None:
        self.feed = futures_price_feed
        self._poll_interval = poll_interval
        self._pending: dict[str, _PaperOrder] = {}   # order_id -> (symbol, side, limit, quantity)

    async def get_futures_orderbook(self, symbol):   # real data
        snap = self.feed.get_orderbook_snapshot(symbol)
        if not snap:
            raise RuntimeError(f"no orderbook snapshot for {symbol}")
        return SimpleNamespace(bid=[SimpleNamespace(price=float(snap["bid_price_1"]))],
                               ask=[SimpleNamespace(price=float(snap["ask_price_1"]))])

    async def place_futures_order(self, *, symbol, side, quantity, order_type, price) -> str:
        order_id = f"PAPER-{uuid4().hex[:12]}"        # synthetic, no KIS call
        self._pending[order_id] = _PaperOrder(symbol, side, float(price), int(quantity))
        return order_id

    async def await_fill(self, order_id, timeout_seconds) -> Fill | None:
        # faithful tick-watch fill model (§5)
        ...

    async def cancel_order(self, order_id) -> bool:
        self._pending.pop(order_id, None)             # no-op cancel
        return True
```

### 4.2 `services/order_router/main.py` 모드 배선
- `_resolve_mode() -> str` = env `FUTURES_ORDER_ROUTER` (off 기본 | paper | live).
- off → inert(log + return 0, like other daemons).
- **paper**: 피드 `is_real=True`(실 오더북) → `PaperKISFuturesAdapter(futures_price_feed=feed)` → `PassiveMaker(kis_client=paper_adapter, fill_logger)`. LiveModeGuard 불필요(실주문 0). 데몬/PseudoOCO 그대로.
- **live**: 현재 경로(실 `KISFuturesAdapter` + LiveModeGuard), 무변경.
- **피드 is_real 분리**: paper·live 모두 피드 `is_real=True`(실 오더북). 깨진 `KIS_FUTURES_MARKET=mock` 피드 경로 제거. (live의 주문 계좌 real/mock은 기존 executor 설정 유지.)

### 4.3 무변경
PassiveMaker / PseudoOCO(fill_logger-only) / OrderRouterDaemon / FillLogger — 주입 kis_client만 다름.

## 5. Faithful tick-watch fill model (`await_fill`)

PassiveMaker는 best_bid(long)/best_ask(short)에 limit L 게시 → `await_fill`. paper는 실 피드를 관찰:

### 체결 조건 (순수함수 `_passive_filled`)
```python
def _passive_filled(side, limit, last_trade, best_bid, best_ask) -> bool:
    if side == "long":   # bid 대기: 시장이 내려와 내 가격 도달 시 체결
        return (last_trade is not None and last_trade <= limit) or (best_ask is not None and best_ask <= limit)
    return (last_trade is not None and last_trade >= limit) or (best_bid is not None and best_bid >= limit)  # short
```
게시 시점엔 best_ask>L(long, 정상 스프레드) → 즉시 체결 안 됨(패시브 대기, 정확).

### 흐름
```
order = self._pending[order_id]
deadline = monotonic() + timeout_seconds
while monotonic() < deadline:
    price = (self.feed.get_current_price(order.symbol) or {}).get("close")
    snap  = self.feed.get_orderbook_snapshot(order.symbol) or {}
    bid, ask = snap.get("bid_price_1"), snap.get("ask_price_1")
    if _passive_filled(order.side, order.limit, _f(price), _f(bid), _f(ask)):
        return Fill(order_id, price=order.limit, quantity=order.quantity, filled_at_ms=_now_ms())
    await asyncio.sleep(self._poll_interval)
return None   # timeout -> PassiveMaker cancels -> OrderResult.missed
```
- **체결가 = limit L**(패시브 resting limit은 게시가 또는 더 유리하게 체결) → PassiveMaker slippage_ticks=0(패시브 본질).
- **timeout → None → miss**(패시브 미체결 리스크 모델링).
- **staleness**: 틱 없으면 체결 확인 불가 → miss(보수적) + WARNING.
- `poll_interval`/`timeout` 주입 → 테스트는 tiny값으로 실 sleep 없이 fill/miss 검증.

## 6. Error handling · cost
- paper 어댑터는 **구조적 실주문 불가**(place/cancel 로컬, await_fill read-only). KIS 주문 호출 0.
- 피드 staleness → miss(보수적). 모드: off→inert, unknown→off.
- 비용: await_fill가 timeout 동안 ~0.2s 폴링(in-memory read, 무시 가능).

## 7. Testing
- **단위 `_passive_filled`**(순수): long(trade≤limit / ask≤limit / 미도달), short(trade≥limit / bid≥limit / 미도달).
- **`PaperKISFuturesAdapter`**: `place_futures_order`→`PAPER-` id + pending 기록, 실호출 0 · `get_futures_orderbook`→피드 위임(빈값 RuntimeError) · `await_fill` fill(조건충족 fake feed→Fill@limit, qty) / miss(미충족+tiny timeout→None) · `cancel_order`→no-op True.
- **통합**: PassiveMaker + PaperKISFuturesAdapter + fake feed + 실 FillLogger(fakeredis) → `place_passive_limit_futures` long → best_bid 체결 + `order.fill` 스트림/SQLite 기록(slippage 0, 실주문 0); 미충족 → `OrderResult.missed`(+ cancel 호출).
- **모드 배선**: order_router build에서 paper→PaperKISFuturesAdapter 선택(실 어댑터 아님), off→inert, live→실 어댑터.
- **회귀**: PassiveMaker/PseudoOCO/daemon/FillLogger 무변경 → 기존 테스트 green. full gate.

## 8. Acceptance criteria
- [ ] `FUTURES_ORDER_ROUTER=paper` → 피드 is_real=True + `PaperKISFuturesAdapter`(실 오더북 + 패시브 체결 sim + 로컬 기록, **실 KIS 주문 0**); `=live` → 실 어댑터 + LiveModeGuard; `=off` → inert.
- [ ] 체결: `_passive_filled` 충실 모델(long/short), 체결가=limit(slippage 0), timeout→miss.
- [ ] 피드 항상 is_real=True; mock이 선물 오더북을 깨뜨리지 않음.
- [ ] paper 체결이 FillLogger(로컬 SQLite + `order.fill` 스트림)에 기록, 실 KIS 주문 0.
- [ ] PassiveMaker/PseudoOCO/OrderRouterDaemon/FillLogger **무변경**(신규 paper 어댑터 + 모드 배선만).
- [ ] 단위(`_passive_filled` + 어댑터) + 통합(PassiveMaker e2e) + 회귀 green.

### 운영 검증 (머지 후)
`FUTURES_ORDER_ROUTER=paper`로 order_router 기동(실 WS 피드) → 선물 시그널이 실 오더북 대비 패시브 체결/miss로 시뮬되고 `order.fill`에 기록, 실 주문 0. (전체 체인 decision→risk→order는 F-1 스트림 정합 후.)

## 9. Open questions (구현 계획에서 확정)
- `_passive_filled` 가격 단위: 체결가 `last_trade`(get_current_price 'close') vs 오더북 크로스 — 둘 다 OR로 충분(위). qty 부분체결은 모델 안 함(전량/miss, YAGNI).
- 모드 플래그명 `FUTURES_ORDER_ROUTER`(stock `STOCK_ORDER_ROUTER` 패턴) 확정.
- 테스트 위치: `tests/unit/execution/test_paper_kis_futures_adapter.py` + 통합 `tests/integration/`(기존 패턴 확인).
- live의 `KIS_FUTURES_MARKET` 의미(주문 계좌 real/mock) — F-3는 피드만 항상 real로 분리, 주문 계좌 설정은 기존 유지.
