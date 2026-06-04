# Orchestrator Stock Data-Source Cutover (M1c) — Design

- Date: 2026-06-04
- Status: Design (pending implementation plan)
- Goal: Let the trading orchestrator consume the Redis tick stream (via the M1b `StreamConsumerFeed`) instead of owning the KIS WebSocket feed — behind a per-asset, default-off flag — so the WS reader can live in the M1a ingest daemon. This is the M1 cutover that realizes the WS-ingest isolation SLO.

## 1. Goal & context

M1a (ingest daemon, PR #410) and M1b (`StreamConsumerFeed`, PR #411) are merged: the producer publishes ticks to `market:ticks`/`raw_data`, and the consumer (`StreamConsumerFeed`) implements the `MarketDataSource` surface (`get_current_price` + `supports_instant_read` + `get_health_status`) and pushes each tick to the indicator engine (decision A). M1c connects them: the orchestrator, behind a flag, uses `StreamConsumerFeed` as its `data_source` and stops constructing its own KIS feed.

**Seam** (from the M1 audit): `_init_price_feeds(kis_config)` returns a `data_source` that `_init_data_provider` passes to `MarketDataProvider(kis_client=self._kis_client, data_source=...)`. Swapping the `data_source` is the whole cut — the strategy cycle, position management, and `_market_data_snapshot` poll read through `MarketDataProvider.get_data()` unchanged.

**Scope: stock only.** The tick stream carries no orderbook fields; the futures slippage controller (enabled by default) blocks futures entries without an orderbook. So futures stays on `websocket`; the flag only enables `stream` for stock. Futures stream cutover is a later increment (needs an orderbook transport).

## 2. Locked decisions (brainstorming 2026-06-04)

| 결정 | 선택 |
|---|---|
| Flag | per-asset env `STOCK_MARKET_DATA_SOURCE` = `websocket` (default) \| `stream` |
| 기본값 | `websocket` — 머지해도 운영 무변경(코드만 준비) |
| 자산 범위 | **stock only** (futures `websocket` 고정 — orderbook 미해결) |
| 지표 갱신 | StreamConsumerFeed가 per-tick `indicator_engine.on_tick` push (decision A) |
| stale 동작 | **REST 폴백 유지** — `data_provider` failover가 `_kis_client`로 degrade (이미 배선) |
| 롤백 | flag를 `websocket`로 → KIS feed 경로 복귀 (재시작만) |
| 활성화 | operator 단계 (ingest 유닛 enable + flag flip + 라이브 SLO 검증) — 코드와 분리 |

## 3. Orchestrator changes (3 seams)

### 3.1 `_init_price_feeds(kis_config)` — choose the data source
- Read the flag: `STOCK_MARKET_DATA_SOURCE` (default `websocket`).
- **stock + `stream`**: construct `self._stream_consumer_feed = StreamConsumerFeed(redis=<async redis>, stream="market:ticks", stale_threshold_seconds=…)`; set `data_source = self._stream_consumer_feed`; **do NOT** construct `KISStockPriceFeed` (`self._stock_price_feed` stays `None` → no KIS WebSocket connection). Return `data_source`.
- **else** (websocket default, or futures, or no kis_client): current behavior (build the KIS feed).
- `_kis_client` is retained unchanged (REST fallback).
- **Wiring requirement:** `StreamConsumerFeed` needs an async Redis client (`redis.asyncio`). The orchestrator constructs/obtains one for the stream path (the plan wires this — e.g. `redis.asyncio.from_url(REDIS_URL)`), stored for shutdown.

### 3.2 `_init_indicator_engine` — wire the indicator push, skip the WS callback
- When the data source is the stream feed: set `self._stream_consumer_feed.indicator_engine = self._indicator_engine` (so it pushes `on_tick` per tick — decision A), and **skip** the `self._stock_price_feed.set_tick_callback(_on_stock_tick)` wiring (there is no KIS feed). The `_on_stock_tick` closure is simply not registered.
- websocket path: unchanged.

### 3.3 `_start_market_data_loop` / `_stop_market_data_loop` — generalize feed lifecycle
- Today these reference `self._stock_price_feed` directly for `start()`/`stop()`/`update_symbols()`. Generalize to operate on the active **feed-like data source** (anything exposing `start`/`stop`/`update_symbols` — both `KIS*PriceFeed` and `StreamConsumerFeed` do). When the stream feed is active, start/stop it and call `update_symbols(universe)` (for the health denominator; the stream already carries only subscribed symbols).
- This is the largest edit — the existing `_stock_price_feed`-direct references become data-source-generic. Keep the futures path (`_futures_price_feed`) exactly as-is.

### 3.4 tick stream publisher
- With the stream source, no `_on_stock_tick` callback fires → the orchestrator's `_tick_stream_publisher` is unfed (the M1a ingest daemon publishes ticks now). Skip constructing/feeding it on the stock-stream path (no-op either way; do not double-publish).

## 4. stale behavior — REST fallback (kept)

The existing `MarketDataProvider` failover loop already monitors `data_source` health via `get_health_status` / `is_healthy` and switches to REST polling (`_kis_client`) when the source goes stale. `StreamConsumerFeed.get_health_status` returns the keys that loop reads (`running`/`connected`/`staleness_seconds`/`fresh_symbol_count`/`symbol_count`). So if the ingest daemon dies/lags, the orchestrator degrades to KIS REST polling rather than no-data — a safety net at ~zero added cost (`_kis_client` already present, failover already wired).

## 5. Safety properties

- **default off** → merging M1c changes nothing operationally; the code is staged behind the flag.
- **No dual WS** → on the stream path the orchestrator owns no WS feed, so it can't conflict with the M1a ingest daemon's WS connection.
- **Futures unchanged** → `websocket` fixed; futures path untouched.
- **Rollback = flag flip** → set `websocket`, restart; the KIS-feed code path is unchanged and resumes.

## 6. Activation (operator runbook — not part of the code merge)

1. Ensure the stock ingest daemon (`kis-market-ingest-stock`, M1a) is running and healthy (publishing to `market:ticks`; `tick_count` rising).
2. Set `STOCK_MARKET_DATA_SOURCE=stream` and restart the stock orchestrator.
3. **Validate the SLO** with the existing metrics: `market_data_staleness` p99, tick→XADD latency, `trading_signal_latency_ms` — should be flat/improved and independent of downstream load; positions/signals/fills normal vs the websocket baseline.
4. If anything regresses: set `STOCK_MARKET_DATA_SOURCE=websocket`, restart (rollback).

The runbook is delivered as `docs/runbooks/stock-stream-cutover.md`.

## 7. Testing

The orchestrator is large and heavily mocked; M1c tests focus on the **flag routing seam**, not a full orchestrator run:
- With `STOCK_MARKET_DATA_SOURCE=stream` (stock): `_init_price_feeds` returns a `StreamConsumerFeed` (not a `KISStockPriceFeed`); `_stock_price_feed is None`; after `_init_indicator_engine`, the stream feed's `indicator_engine` is the orchestrator's engine and no `_on_stock_tick` callback was registered on a KIS feed.
- With `STOCK_MARKET_DATA_SOURCE=websocket` / unset (default): current behavior unchanged — `_init_price_feeds` builds the KIS feed; existing orchestrator lifecycle tests stay green.
- Futures path unaffected regardless of the flag.
- The `_start/_stop_market_data_loop` generalization: a fake feed-like data source (with `start`/`stop`/`update_symbols`) is started/stopped/updated; assert the futures path still uses `_futures_price_feed`.
- Reuse the existing orchestrator test fixtures/patterns (`tests/integration/test_orchestrator_lifecycle.py`, `tests/unit/trading/*`). Keep the whole `tests/` suite green (the change must be behaviorally inert when the flag is off).

## 8. Risks & mitigations

| 리스크 | 완화 |
|---|---|
| 거대 orchestrator 편집 회귀 | default-off flag → off 경로 동작 불변; 기존 lifecycle 테스트가 게이트; 편집은 3개 seam에 국한 |
| stream 경로 초기 지표 미성숙(콜드스타트) | StreamConsumerFeed warmup은 stream tick으로 채워짐; data_provider warmup(ClickHouse/parquet)은 별도 — 본 증분에서 변경 안 함 |
| ingest 데몬 미가동인데 flag on | StreamConsumerFeed stale → REST 폴백(§4); 활성화 runbook이 ① ingest healthy 확인 선행 |
| async redis 배선 누락 | plan에서 명시 배선 + 종료 시 close |
| 선물 실수 활성화 | flag는 stock에만 적용; 선물 코드 경로 무변경 |

## 9. Acceptance criteria

- [ ] `STOCK_MARKET_DATA_SOURCE=stream` (stock) → orchestrator uses `StreamConsumerFeed`, builds no KIS stock feed (no WS connection), wires indicator push, skips `_on_stock_tick`.
- [ ] flag off/unset → behavior identical to today (existing tests green).
- [ ] `_start/_stop_market_data_loop` generalized to data-source feed lifecycle; futures path unchanged.
- [ ] stale stream → REST fallback (failover loop) still degrades via `_kis_client`.
- [ ] rollback by flag flip; runbook documents activation + SLO validation; futures excluded.
- [ ] whole `tests/` suite green; lint clean.

## 10. Out of scope

- Futures stream cutover (needs an orderbook transport — separate increment).
- Enabling the M1a ingest systemd units (operator activation step).
- Removing/retiring the KIS-feed code path (kept for rollback + futures).
- data_provider warmup source (ClickHouse→parquet is the separate runtime-storage migration).
- M2+ (indicator/decision daemons).

## 11. Open questions (resolved in the plan)

- Exact env-flag read site + name constant placement (orchestrator config vs `os.environ`).
- Whether `update_symbols` on the stream feed should mirror the universe-refresh loop or be a one-shot (health-denominator only).
- async redis client lifecycle ownership (construct in `_init_price_feeds` vs a dedicated init).
