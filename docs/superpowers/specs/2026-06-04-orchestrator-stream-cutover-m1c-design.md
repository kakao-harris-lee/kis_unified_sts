# Orchestrator Stock Data-Source Cutover (M1c) — Design

- Date: 2026-06-04
- Status: Design (pending implementation plan)
- Goal: Let the trading orchestrator consume the Redis tick stream (via the M1b `StreamConsumerFeed`) instead of owning the KIS WebSocket feed — behind a per-asset, default-off flag — so the WS reader can live in the M1a ingest daemon. This is the M1 cutover that realizes the WS-ingest isolation SLO.

## 1. Goal & context

M1a (ingest daemon, PR #410) and M1b (`StreamConsumerFeed`, PR #411) are merged: the producer publishes ticks to `market:ticks`/`raw_data`, and the consumer (`StreamConsumerFeed`) implements the `MarketDataSource` surface (`get_current_price` + `supports_instant_read` + `get_health_status`) and can push each tick to an indicator engine (decision A). M1c connects them: the orchestrator, behind a flag, uses `StreamConsumerFeed` as its `data_source` and stops constructing its own KIS feed.

**Per-tick processing — preserve the full WS callback (planning finding).** The orchestrator's `_on_stock_tick` (orchestrator.py:1789–1821, defined in `_init_indicator_engine`) does **three** things per tick: (1) `indicator_engine.on_tick` (with `set_volume_baseline` guard), (2) `paper_broker.record_price_observation` (paper-mode mark-to-market), (3) `tick_stream_publisher.publish` (monitoring). M1b's `StreamConsumerFeed` only does (1). So the cut must **reuse the existing `_on_stock_tick`**, not just the indicator push — otherwise paper-mode loses per-tick price observations. The clean realization: `StreamConsumerFeed` gains `set_tick_callback(cb)` (mirroring the `KIS*PriceFeed` contract); the orchestrator wires the *same* `_on_stock_tick` to whichever stock feed is active. Publish (3) is gated off on the stream path because `_tick_stream_publisher` is `None` there (the M1a ingest daemon owns publishing) — so `_on_stock_tick`'s `if self._tick_stream_publisher:` guard no-ops, no double-publish.

**Seam** (from the M1 audit): `_init_price_feeds(kis_config)` returns a `data_source` that `_init_data_provider` passes to `MarketDataProvider(kis_client=self._kis_client, data_source=...)`. Swapping the `data_source` is the whole cut — the strategy cycle, position management, and `_market_data_snapshot` poll read through `MarketDataProvider.get_data()` unchanged.

**Scope: stock only.** The tick stream carries no orderbook fields; the futures slippage controller (enabled by default) blocks futures entries without an orderbook. So futures stays on `websocket`; the flag only enables `stream` for stock. Futures stream cutover is a later increment (needs an orderbook transport).

## 2. Locked decisions (brainstorming 2026-06-04)

| 결정 | 선택 |
|---|---|
| Flag | per-asset env `STOCK_MARKET_DATA_SOURCE` = `websocket` (default) \| `stream` |
| 기본값 | `websocket` — 머지해도 운영 무변경(코드만 준비) |
| 자산 범위 | **stock only** (futures `websocket` 고정 — orderbook 미해결) |
| per-tick 처리 | StreamConsumerFeed가 `set_tick_callback`로 **기존 `_on_stock_tick` 재사용** → 지표 `on_tick` + `paper_broker.record_price_observation` 보존. publish는 ingest 소유(stream 경로는 `_tick_stream_publisher=None`으로 게이트오프) |
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

### 3.2 `_init_indicator_engine` — wire `_on_stock_tick` to the active stock feed
- The existing stock-callback block is gated `if self._stock_price_feed:` (orchestrator.py:1787) and registers `_on_stock_tick`. Generalize the gate to the active stock feed: `stock_feed = self._stock_price_feed or self._stream_consumer_feed; if stock_feed: stock_feed.set_tick_callback(_on_stock_tick)`. The closure is **unchanged** — it does indicator `on_tick` + `paper_broker.record_price_observation` + (gated) publish. On the stream path `_stock_price_feed is None`, so the same `_on_stock_tick` binds to `StreamConsumerFeed`.
- `StreamConsumerFeed` is constructed **without** an indicator engine on this path (the callback does `on_tick`) → no double push. When a `tick_callback` is set, `StreamConsumerFeed._apply_entry` invokes the callback **instead of** its own `_push_indicator`.
- websocket path: `_stream_consumer_feed is None` → unchanged.

### 3.3 `_start_market_data_loop` / `_stop_market_data_loop` — additive stream-feed lifecycle
- **Additive, not a rewrite** (lower regression risk): keep the existing `if self._stock_price_feed:` / `if self._futures_price_feed:` blocks exactly as-is, and add a new sibling block `if self._stream_consumer_feed:` that `await`s `start()` + `update_symbols(self.config.symbols)` (start loop) and `await`s `stop()` + closes the async redis (stop loop). On the websocket path `_stream_consumer_feed is None` → the new blocks no-op; on the stream path `_stock_price_feed is None` → the existing stock block no-ops. Futures path (`_futures_price_feed`) untouched.
- `update_symbols(universe)` feeds the health denominator (`symbol_count`); the stream already carries only subscribed symbols.

### 3.4 tick stream publisher
- On the stream path, **skip constructing** `self._tick_stream_publisher` in `_init_tick_stream_publisher` (it stays `None`). The M1a ingest daemon owns publishing now. Because `_on_stock_tick`'s publish is guarded `if self._tick_stream_publisher:`, leaving it `None` makes the reused callback no-op the publish — no double-publish, no separate code branch.

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

The orchestrator is directly constructible in tests (`TradingOrchestrator(TradingConfig.stock())`, per `tests/unit/trading/test_orchestrator.py`); M1c tests focus on the **flag routing seam** + the `StreamConsumerFeed.set_tick_callback` unit, not a full orchestrator run:
- `StreamConsumerFeed` unit (`tests/unit/trading/test_stream_consumer_feed.py`): with a `tick_callback` set, `_apply_entry` invokes the callback `(symbol, price_dict, datetime)` **and does not** call the indicator engine's `on_tick`; with no callback, the M1b indicator push is unchanged (existing tests stay green).
- With `STOCK_MARKET_DATA_SOURCE=stream` (stock, `_kis_client` stubbed truthy): `_init_price_feeds` returns a `StreamConsumerFeed`; `_stock_price_feed is None`; `_stream_consumer_feed is not None`. After `_init_indicator_engine`, the stream feed has a `tick_callback` set (the closure) and its `indicator_engine is None`. `_init_tick_stream_publisher` leaves `_tick_stream_publisher is None`.
- With flag unset/`websocket` (default): `_init_price_feeds` does **not** take the stream branch — `_stream_consumer_feed is None`; existing behavior/tests unchanged.
- Futures path unaffected regardless of the flag (`asset_class == "futures"` never reads the stock flag).
- `_start/_stop_market_data_loop`: with a fake `_stream_consumer_feed` (recording `start`/`stop`/`update_symbols` calls) the new blocks start/stop/update it; with `_stream_consumer_feed is None` they no-op and the existing feed handling is untouched.
- Keep the whole `tests/` suite green (the change is behaviorally inert when the flag is off).

## 8. Risks & mitigations

| 리스크 | 완화 |
|---|---|
| 거대 orchestrator 편집 회귀 | default-off flag → off 경로 동작 불변; 기존 lifecycle 테스트가 게이트; 편집은 3개 seam에 국한 |
| stream 경로 초기 지표 미성숙(콜드스타트) | StreamConsumerFeed warmup은 stream tick으로 채워짐; data_provider warmup(ClickHouse/parquet)은 별도 — 본 증분에서 변경 안 함 |
| ingest 데몬 미가동인데 flag on | StreamConsumerFeed stale → REST 폴백(§4); 활성화 runbook이 ① ingest healthy 확인 선행 |
| async redis 배선 누락 | plan에서 명시 배선 + 종료 시 close |
| 선물 실수 활성화 | flag는 stock에만 적용; 선물 코드 경로 무변경 |

## 9. Acceptance criteria

- [ ] `STOCK_MARKET_DATA_SOURCE=stream` (stock) → orchestrator uses `StreamConsumerFeed`, builds no KIS stock feed (no WS connection), reuses `_on_stock_tick` via `set_tick_callback` (indicator + paper_broker preserved), `_tick_stream_publisher is None` (publish gated off).
- [ ] `StreamConsumerFeed.set_tick_callback` invokes the callback per tick instead of the indicator push; no-callback path unchanged.
- [ ] flag off/unset → behavior identical to today (existing tests green; `_stream_consumer_feed is None`).
- [ ] `_start/_stop_market_data_loop` start/stop/update the stream feed (additive blocks) + close the async redis; futures path unchanged.
- [ ] stale stream → REST fallback (failover loop) still degrades via `_kis_client`.
- [ ] rollback by flag flip; runbook documents activation + SLO validation; futures excluded.
- [ ] whole `tests/` suite green; lint clean.

## 10. Out of scope

- Futures stream cutover (needs an orderbook transport — separate increment).
- Enabling the M1a ingest systemd units (operator activation step).
- Removing/retiring the KIS-feed code path (kept for rollback + futures).
- data_provider warmup source (ClickHouse→parquet is the separate runtime-storage migration).
- M2+ (indicator/decision daemons).

## 11. Resolved during planning (verbatim audit 2026-06-04)

- **Env-flag read:** `os.getenv("STOCK_MARKET_DATA_SOURCE", "websocket").strip().lower()` read inside `_init_price_feeds` (matches the daemons' `os.environ.get` idiom; no new config field). Gate stock-only via the existing `self.config.asset_class == "stock"` branch.
- **async redis lifecycle:** construct in `_init_price_feeds` stream branch with `redis.asyncio.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/1"))` (the exact idiom `services/risk_filter`, `services/market_ingest` use — DB 1; `from_url` is lazy so no connection at construction), store as `self._stream_redis`, and `await self._stream_redis.aclose()` in `_stop_market_data_loop`.
- **`update_symbols`:** one-shot `update_symbols(self.config.symbols)` at start (health-denominator only); the universe-refresh loop already re-subscribes the KIS feed on the websocket path and is out of scope for the stream feed in M1c.
- **`paper_broker` per-tick:** preserved by reusing `_on_stock_tick` via `set_tick_callback` (see §1, §3.2) — not dropped.
