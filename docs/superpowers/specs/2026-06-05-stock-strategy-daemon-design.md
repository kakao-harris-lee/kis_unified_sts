# Stock Strategy Daemon (M4-P) — Design

- Date: 2026-06-05
- Status: Design (pending implementation plan)
- Goal: Build the **stock signal producer** the stream pipeline is missing — a shadow-first daemon that consumes `market:ticks`, runs the enabled stock entry strategies via the existing `StrategyManager`, and publishes entry candidates to `signal.candidate.stock.shadow`. This is the prerequisite for M4 (stock risk_filter/order_router generalization); it isolates the stock strategy stage off the monolithic orchestrator loop. Default-off, no live impact.

## 1. Goal & context

The futures strategy daemon (M2+M3, merged #414) completed the futures producer. Stock has **no** stream signal producer — stock entry signals are generated in-process in the orchestrator (`StrategyManager.check_entries` per cycle). So the M4 stock risk_filter/order_router daemons would have no input. M4-P builds that producer.

**Reuse-first.** The stock strategy path is already a clean unit: `StrategyManager.check_entries(EntryContext) → Signal`. This increment wires it into a daemon that owns a daemon-local indicator engine (fed from `market:ticks` via the M1b `StreamConsumerFeed`), builds an `EntryContext` per universe symbol per decision cadence, and publishes the resulting signals. The only genuinely new code is the daemon loop, a dynamic universe-refresh loop, and a stock-native candidate serializer.

**Why a new loop (not `DecisionEngineDaemon` reuse like futures):** stock is multi-symbol with a **dynamic, screener-driven universe** (vs the futures single front-month), and uses `StrategyManager` + `EntryContext` + the resolver (vs futures' pure `Setup.check(MarketContext)`). So the loop iterates the universe and builds a per-symbol `EntryContext`.

## 2. Locked decisions (brainstorming 2026-06-05)

| 결정 | 선택 |
|---|---|
| 증분 | M4의 첫 하위 증분 = **주식 시그 producer**(전략 데몬). risk/order/exit는 후속(M4-R/O/X) |
| 롤아웃 | **shadow-first**, flag `STOCK_STRATEGY_DAEMON=off`(기본)\|`shadow`, systemd disabled |
| 스키마 | **주식-native** `signal.candidate.stock.shadow` (orchestrator Signal 직렬화). 선물 11-필드 decision 스키마 미사용(주식은 진입시 stop/target 없음) |
| 전략 범위 | 현재 활성 주식 전략 그대로 (`williams_r`, `pattern_pullback`) — self-contained(어댑터 LLM/regime 게이트 없음 → parity 무관) |
| 유니버스 | 동적 — Redis `system:daily_watchlist:latest` 30s 폴 → `feed.update_symbols`, ≤40 |
| 프레임워크 | 재사용 `StreamConsumerFeed`(M1b) + `StreamingIndicatorEngine` + `StreamingIndicatorResolver` + `StrategyManager`. 신규: 데몬 루프 + 유니버스 루프 + 후보 직렬화기 |
| warmup | `ParquetMarketDataStore` 1분봉 시드 (M2+M3 헬퍼 패턴 재사용) |

## 3. Architecture

```
[market-ingest M1a] ──XADD──> market:ticks (stock ticks, all subscribed symbols)
                                  │ XREAD (background task)
                                  ▼
        StreamConsumerFeed (REUSED M1b) ──on_tick──> StreamingIndicatorEngine (daemon-local)
                                                         ▲ resolver.collect_entry_indicators(symbol)
  Redis system:daily_watchlist:latest ──30s poll──> universe ──feed.update_symbols(codes)──┘
                                  │
  decision cadence (1-min close): for each symbol in universe:
     build EntryContext(indicators=resolver(symbol), market_data=latest tick,
                        current_positions=[], timestamp=now, market_context=None)
       → StrategyManager.check_entries(ctx) → list[Signal]   (orchestrator model)
         → StockCandidate.from_signal(...).to_stream_dict() + signal_id
           → XADD signal.candidate.stock.shadow
```

The feed pushes ticks to the engine continuously (warm state); the daemon's decision loop evaluates strategies on the 1-min cadence. Both indicator state and strategy live in **one daemon process**, off the orchestrator loop.

## 4. Components & responsibilities

| Unit | New/Reused | Responsibility |
|---|---|---|
| `StockStrategyDaemon` | **NEW** | own the indicator engine + feed + StrategyManager; decision-cadence loop; publish candidates |
| universe-refresh loop | **NEW** (in the daemon) | poll `system:daily_watchlist:latest` (30s) → parse codes → `feed.update_symbols` |
| `StockCandidate` serializer | **NEW** | orchestrator `Signal` → stock candidate `dict[str,str]` (+ `signal_id`) for XADD |
| `StreamConsumerFeed` | **reused (M1b)** | `market:ticks` → indicator engine |
| `StreamingIndicatorEngine` | **reused** | daemon-local per-symbol indicators |
| `StreamingIndicatorResolver` | **reused** | `collect_entry_indicators(symbol)` → indicator dict |
| `StrategyManager` (+ stock `EntryRegistry`) | **reused** | `check_entries(EntryContext) → list[Signal]` |
| parquet warmup helper | **reused pattern** | seed 1-min bars per symbol at startup |

**Single responsibility:** the daemon owns the stock entry stage (tick → candidate). The strategy logic is the existing `StrategyManager`/registry (no duplication).

## 5. Stock-native candidate schema

`signal.candidate.stock.shadow` entry fields (all stringified for Redis):

| field | source (orchestrator `Signal`) |
|---|---|
| `signal_id` | `uuid4().hex` (fresh per emission) |
| `code` | `Signal.code` |
| `name` | `Signal.name` |
| `strategy` | `Signal.strategy` |
| `direction` | `Signal.metadata["signal_direction"]` (default `"long"`) |
| `price` | `Signal.price` |
| `quantity` | `Signal.quantity` |
| `confidence` | `Signal.confidence` |
| `generated_at_ms` | `Signal.timestamp` epoch ms |
| `metadata_json` | `json.dumps(Signal.metadata)` (carries `atr`, etc. the risk filters need later) |

This is a **new** stock serializer (the orchestrator `Signal` has no `to_stream_dict`); the spec adds one. Stock has no entry-time stop/take-profit (the `three_stage` exit owns stops), so the futures 11-field decision schema is not reused. M4-R will teach the generalized `risk_filter` to parse this schema (the 8 filters need symbol/timestamp/size/atr/spread/direction — all present or in `metadata_json`).

## 6. Decision cadence, universe, warmth

- **Cadence:** the enabled stock strategies are 1-min; the daemon evaluates on the 1-min close boundary (the same decision-cadence the orchestrator applies). The feed keeps the engine warm per-tick.
- **Universe (dynamic):** poll `system:daily_watchlist:latest` every 30s; parse the screener JSON (`strategies`/codes), cap at the configured max (≤40); on change, `feed.update_symbols(codes)`. New symbols warm from live ticks (and optionally a parquet top-up).
- **Warmth:** per-symbol `engine.is_warm(symbol)` gates evaluation; a symbol not yet warm is skipped (no candidate) until it has enough candles.
- **EntryContext per symbol:** `indicators = resolver.collect_entry_indicators(symbol)`, `market_data = latest tick dict` (from the engine/feed), `current_positions = []` (the risk_filter re-checks open positions later; the producer doesn't need them), `timestamp = now (UTC)`, `market_context = None` (stock strategies are self-contained; `williams_r`'s `market_state_filter` derives state from indicators, not external LLM).

## 7. Shadow rollout & safety

- **Flag:** `STOCK_STRATEGY_DAEMON` = `off` (default) | `shadow`, read in the entrypoint. `off`/unset → the daemon does not run (systemd unit disabled); merging is operationally inert.
- **Shadow target:** publishes to `signal.candidate.stock.shadow` (separate stream). No consumer exists until M4-R (risk_filter generalization), so no live/paper path and no positions result. The orchestrator's in-process stock entry path is **untouched**.
- **Validation:** the shadow candidates are compared against the orchestrator's actual stock entry signals (counterfactual) to confirm the daemon reproduces the in-process strategy decisions before any cutover.
- **systemd:** `kis-stock-strategy-daemon.service` delivered **disabled**.
- **No cutover here:** standing down the orchestrator's stock strategy stage + wiring the stock risk/order daemons is M4-R/O/X (later).

## 8. Error handling

The daemon loop is fail-safe per symbol: a strategy/resolver raising for one symbol is logged and skipped (others still evaluate). The universe-refresh loop tolerates a missing/malformed Redis key (keeps the prior universe + logs). The `StreamConsumerFeed` owns its own XREAD retry (M1b). XADD failure on a candidate is logged (the candidate is dropped; shadow). Graceful shutdown: stop the feed, stop the loops, close async redis.

## 9. Testing

- **Unit — universe refresh:** parse `system:daily_watchlist:latest` JSON → code list (cap respected); malformed/missing → keep prior; change → `update_symbols` called.
- **Unit — `StockCandidate` serializer:** orchestrator `Signal` → the stock field dict (all keys, types, `direction` from metadata, `generated_at_ms` epoch ms, `metadata_json` round-trips).
- **Unit — EntryContext build + warm-gating:** a not-warm symbol is skipped; a warm symbol builds a context with resolved indicators and is passed to `check_entries`.
- **Integration:** fake-redis `market:ticks` ticks for N symbols + a `system:daily_watchlist:latest` key → daemon warms the engine → publishes a stock candidate to `signal.candidate.stock.shadow` (a strategy fires). Reuse the futures daemon integration harness pattern.
- **Regression:** flag `off`/unset → daemon inert; orchestrator stock path + existing tests unchanged.
- Whole `tests/` suite green; ruff/black clean.

## 10. Out of scope

- M4-R (risk_filter stock generalization), M4-O (order_router stock entry + ATS), M4-X (stock exit daemon — `three_stage` stateful, EOD policy).
- Cutover: orchestrator stock strategy stand-down + live stock candidate stream.
- LLM/regime adapter gates for stock (stock strategies are self-contained today).
- Position sizing fidelity at the candidate stage (sizer needs portfolio cash; the producer emits a nominal quantity, risk/order refine later).

## 10b. Known warmup-fidelity limitations (validate in shadow; fix before cutover)

Surfaced during implementation (Task 5). The producer is correct for the **1-min** strategy path, but warmup fidelity is partial — these are deliberate for the shadow producer and are exactly what shadow validation should catch before any cutover:

- **Daily-dependent strategies are dormant.** `_warmup_engine_from_parquet` seeds only **1-min** candles. `pattern_pullback` (a daily strategy: `sma_200/60/20`, `highest_high`, daily `volume_ratio`) needs the engine's **daily** candles (the orchestrator calls `seed_daily_candles` from parquet daily bars); the daemon does not seed those, so `pattern_pullback` produces no candidates until daily-candle seeding is added. **Validatable path = `williams_r` (1-min).**
- **MTF buckets / multi-day tracking not seeded.** The 1-min warmup omits the `datetime` column, so seeded candles collapse to MTF bucket 0 and daily-high/close tracking is skipped (identical to the merged futures daemon — fix both consistently). Affects strategies relying on MTF or multi-day-from-warmup.
- **`market_state` for `williams_r`** comes from the LLM nightly-analysis context, which `StrategyManager.check_entries` injects via its own `LLMContextProvider` (so it works in production where the nightly LLM data is in Redis) — NOT from the daemon's `EntryContext.metadata`. In a synthetic test with no LLM data, `williams_r`'s `market_state_filter` blocks (hence Task 5's pipeline-integrity fallback).

Follow-up (a small increment before cutover): seed daily candles + include `datetime` in 1-min warmup (across both daemons), then re-validate the shadow counterfactual covers all enabled stock strategies.

## 11. Risks & mitigations

| 리스크 | 완화 |
|---|---|
| 데몬이 orchestrator 주식 경로와 충돌 | shadow 스트림 분리 + 소비자 없음 → 라이브/paper 무영향 |
| 동적 유니버스 변경 시 지표 콜드스타트 | per-symbol `is_warm` 게이트(미warm skip) + 신규 심볼 parquet top-up(가능 시) |
| `StrategyManager`가 orchestrator에 결합 | `check_entries(EntryContext)`는 독립 호출 가능(orchestrator도 동일 호출); 데몬이 동일 컨텍스트 구성 |
| 후보 스키마가 risk_filter와 불일치(M4-R) | metadata_json에 risk 필터 입력(atr/spread) 포함; M4-R에서 파서 일반화 |
| `williams_r` market_state_filter가 외부 컨텍스트 필요 | 지표 기반 self-contained 확인(plan에서 검증); 필요 시 데몬이 동일 소스 제공 |
| 운영 중 origin/main 이동 | 각 단계 fetch+rebase |

## 12. Acceptance criteria

- [ ] `StockStrategyDaemon` consumes `market:ticks` (reused `StreamConsumerFeed` → daemon-local engine), refreshes a dynamic universe from `system:daily_watchlist:latest`, and on the 1-min cadence builds an `EntryContext` per warm symbol and calls `StrategyManager.check_entries`.
- [ ] Emitted signals serialize to the stock-native schema and XADD to `signal.candidate.stock.shadow` with a fresh `signal_id`.
- [ ] Warm-gating: not-warm symbols skipped; per-symbol failures isolated.
- [ ] Flag `off`/unset → daemon inert; orchestrator stock path + existing tests green; systemd unit disabled.
- [ ] Unit + integration + full suite green; lint clean.

## 13. Open questions (resolve in the plan)

- Exact `system:daily_watchlist:latest` JSON shape + the code-extraction (reuse the orchestrator's `_load_static_watchlist`/universe-parse logic vs a small parser).
- The decision-cadence trigger in the daemon (a 60s timer like the futures daemon vs a candle-close signal from the engine) — and how to evaluate "1-min close" for many symbols.
- `EntryContext.market_data` source for each symbol (the feed's `get_current_price(symbol)` cache vs the engine) and which enriched fields the enabled strategies require.
- Whether `StrategyManager` needs the indicator engine wired (`set_indicator_engine`) for the decision-cadence gate, and how to construct it standalone (config load of enabled stock strategies).
- Parquet warmup for a dynamic multi-symbol universe (warm on first appearance vs batch at startup).
- Shadow recorder storage for counterfactual comparison (reuse the futures approach).
