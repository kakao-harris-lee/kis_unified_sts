# Futures Strategy Daemon (M2+M3, futures) — Design

- Date: 2026-06-05
- Status: Design (pending implementation plan)
- Goal: Isolate the futures **strategy stage** (indicator computation + Setup A/C decision) off the monolithic orchestrator event loop into a single stream-connected daemon that consumes `raw_data` ticks and publishes `signal.candidate.futures` — completing the end-to-end futures pub/sub vertical (ingest → strategy → risk → order). Built by refactoring the currently-stubbed `decision_engine`, run **shadow-first** (default-off, no live impact).

## 1. Goal & context

The stream-pipeline decoupling roadmap's M2 (indicator daemon) + M3 (decision daemon) are **merged into one "strategy daemon"** because indicators and strategy are tightly coupled through the `StreamingIndicatorResolver` (the strategy reads a resolved indicator dict per cycle). Splitting them across a stream boundary would force serializing a rich per-symbol indicator snapshot (including a momentum DataFrame) between two cheap (µs) stages. Keeping them in one process preserves the coupling with zero marshaling and still isolates the real strategy cost from the orchestrator loop.

**Why futures first:** the futures downstream daemons already exist and are code-complete (`risk_filter` → `order_router`), and `decision_engine` already exists as the stream tail's head but with a **stubbed input** (the "Task 17" `context_provider` returns `None`, so it emits 0 signals). Wiring real indicator + Setup A/C logic into it completes a full end-to-end futures vertical. Stock has no decision/risk/order daemons yet (deferred to a later increment).

**Stage 0 reminder:** indicator `on_tick` is µs (O(1), no I/O); the bottleneck is event-loop/GIL contention from heavy siblings (LLM, order I/O). This daemon's value is **process isolation of the strategy stage + completing the futures vertical** (and removing the stub), not raw indicator-compute speedup.

## 2. Locked decisions (brainstorming 2026-06-05)

| 결정 | 선택 |
|---|---|
| 증분 범위 | M2+M3 **합친 strategy 데몬** (지표+전략 한 프로세스) |
| 자산 | **선물 먼저** (stock 별도 증분) |
| 구현 | 기존 stub `decision_engine`를 실제 strategy 데몬으로 **리팩터** (신규 데몬 아님) |
| 롤아웃 | **shadow 먼저** (default-off, 라이브 무영향, cutover 별도 증분) |
| 의사결정 로직 | **pure Setup A/C** + 실 context(macro/events). **regime gate·LLM veto/튜닝 모두 미포함** — 이들은 orchestrator **어댑터-레이어** 로직이고 `MarketContext`/pure setup에는 regime/LLM 필드 자체가 없음(parity 증분에서 어댑터 포팅) |
| shadow 대상 | `signal.candidate.futures.shadow` 스트림 + shadow recorder (counterfactual/EOD-proxy 비교) |
| flag | `FUTURES_STRATEGY_DAEMON` = `off`(기본) \| `shadow` (candidate 스트림 타깃 선택) |
| 프레임워크 | **기존 `DecisionEngineDaemon`(타이머 루프, 변경 없음) 재사용** + **M1b `StreamConsumerFeed` 재사용**(raw_data→지표엔진) + **신규 `FuturesContextProvider`**(주입형 context_provider). StreamStage 신규 작성 아님 |
| 지표 warmup | `ParquetMarketDataStore` 1분봉 시드 (post-clickhouse 정상) — atr_14·15분 high/low 워밍 |

## 3. Architecture (reuse-first)

The existing `DecisionEngineDaemon` (`services/decision_engine/main.py`) is **already the right loop**: it polls an injected `context_provider() → MarketContext | None` every `tick_interval_seconds` (~60s), runs each `setup.check(ctx)`, and XADDs emitted `Signal.to_stream_dict()` (+`signal_id`) to a candidate stream — with a complete error taxonomy. The **only** missing piece is a real `context_provider` (the "Task 17" stub returns `None`). So this increment supplies that, plus a background tick→indicator feeder. **Three reused parts, one new part.**

```
[market-ingest M1a] ──XADD──> raw_data (futures trade ticks)
                                  │ XREAD (background task)
                                  ▼
            StreamConsumerFeed (REUSED from M1b)  ──on_tick──>  StreamingIndicatorEngine
                                                                  (daemon-local, warm state)
                                                                       ▲ get_indicators / atr / 15m hi-lo
   Redis stream:macro.overnight ──read_latest_macro_snapshot──┐       │
   config/scheduled_events.yaml ──load_scheduled_events───────┤       │
   parquet (prev_close/today_open + 1m warmup) ───────────────┤       │
                                                              ▼       │
                                          FuturesContextProvider (NEW) ┘
                                              builds MarketContext per poll
                                                       │
                                                       ▼ injected as context_provider
            DecisionEngineDaemon (REUSED, timer loop)  ── setup.check(ctx) ──> Signal
                                                       │  XADD .to_stream_dict()+signal_id
                                                       ▼
                            signal.candidate.futures.shadow   (shadow mode; NOT the live stream)

  [risk_filter] -> signal.final -> [order_router]  (UNCHANGED; consumes the real
        stream:signal.candidate from the orchestrator path; untouched by shadow)
```

The indicator engine is fed continuously (every tick via `StreamConsumerFeed`) so `atr_14` / 15-min high-low stay correct; the `DecisionEngineDaemon` timer (~60s ≈ 1-min bar) reads a fresh `MarketContext` each poll. Both indicator state and strategy live **in one daemon process** (the M2+M3 merge), off the orchestrator loop.

## 4. Components & responsibilities

| Unit | New/Reused | Responsibility | Depends on |
|---|---|---|---|
| `DecisionEngineDaemon` | **reused, unchanged** | timer loop: context→`setup.check`→XADD candidate (error taxonomy, graceful stop) | redis, setups, context_provider |
| `StreamConsumerFeed` | **reused (M1b)** | consume `raw_data`, push each tick to the indicator engine | redis, indicator engine |
| `StreamingIndicatorEngine` | **reused** | daemon-local rolling indicators (atr_14, 15m hi/lo, current_price) | — |
| Setup A/C (`SetupAGapReversion`/`SetupCEventReaction`) | **reused, unchanged** | pure `check(MarketContext) → Signal` | `MarketContext` |
| **`FuturesContextProvider`** | **NEW** | build `MarketContext` from indicator engine + parquet (prev_close/today_open) + macro (Redis) + events (YAML) | indicator engine, redis, parquet, events YAML |
| `_build_and_run` (futures strategy entrypoint) | **modified** | wire all of the above; flag-select candidate stream; parquet warmup; signal handlers | all |

**Single responsibility & reuse:** the proven daemon loop and the M1b feed are untouched; the only genuinely new unit is `FuturesContextProvider`, a pure builder of `MarketContext`. Setup A/C are the same pure classes (no duplication).

## 5. `MarketContext` builder — exact fields

`FuturesContextProvider` populates `MarketContext` (`shared/decision/context.py`). The two setups read **only** these (verbatim audit of `gap_reversion.py` / `event_reaction.py`):

| Field | Source |
|---|---|
| `now` | `datetime.now(KST)` |
| `symbol` | configured futures trade symbol (e.g. `A05xxx` mini front-month) |
| `current_price` | indicator engine latest tick / `get_indicators` |
| `prev_close`, `today_open` | parquet daily/session bars (the values the orchestrator's MarketDataProvider supplies) |
| `atr_14` | indicator engine |
| `last_15min_high`, `last_15min_low` | indicator engine (15-min window) |
| `macro_overnight` | Redis `stream:macro.overnight` via `read_latest_macro_snapshot` (MacroSnapshot, `sp500_change_pct`) |
| `scheduled_events` | `load_scheduled_events("config/scheduled_events.yaml")` (or Redis-backed; plan decides) |

**Defaulted (NOT read by either setup → no extra infra):** `vwap = 0.0`, `atr_90th_percentile = 0.0`, `current_spread_ticks = 0.0`. This is the key simplification: **no orderbook** (Setup A/C don't use spread) and **no 60-day ATR-percentile warmup** are required. Decision cadence = the daemon's `tick_interval_seconds` (~60s, one MarketContext per minute); the indicator engine is kept warm by the continuous tick feed.

## 6. Decision-logic scope (this increment)

Included: indicator computation (daemon-local) + **pure `SetupAGapReversion` / `SetupCEventReaction`** + real `MarketContext` (macro overnight + scheduled events).

**Deferred (next increment — adapter-layer logic, ABSENT from the decision path):** the **regime gate**, **LLM veto**, and **LLM tuning** live in the orchestrator's `SetupAEntryAdapter`/`SetupCEntryAdapter` (`shared/strategy/entry/setup_adapters.py`), NOT in the pure decision setups — `MarketContext` has no `regime`/LLM field at all. Porting them is a parity step before cutover, out of scope here. (This corrects the brainstorm's tentative "include regime gate": the verbatim shows it isn't part of the decision setups.)

## 7. Shadow rollout & safety

- **Flag:** `FUTURES_STRATEGY_DAEMON` = `off` (default) | `shadow`, read in the entrypoint.
  - `off`/unset → the entrypoint keeps the **inert stub** (`context_provider` returns `None`, 0 signals) — preserves the existing (Phase-5-gated, not-running) `kis-decision-engine` unit's current behavior; merging is operationally inert.
  - `shadow` → wire the real `FuturesContextProvider` + `StreamConsumerFeed(raw_data)` + parquet warmup, publishing to **`signal.candidate.futures.shadow`**.
- **Shadow target:** `signal.candidate.futures.shadow` is a **separate stream**; the existing `risk_filter` (consuming `stream:signal.candidate`) → `order_router` are **untouched** → no second paper/live path, no positions from the daemon.
- **Validation:** a shadow recorder persists daemon candidates (plan picks SQLite-ledger shadow table vs JSONL); compared against the orchestrator's actual futures signals via counterfactual / EOD-proxy PnL (the regime-gate-analyst method) to confirm the core stream path is sound.
- **systemd:** a unit (`kis-futures-strategy-daemon`, or `kis-decision-engine` with `FUTURES_STRATEGY_DAEMON=shadow`) is delivered **disabled**. Plan decides whether to reuse the decision_engine entrypoint/unit or add a sibling.
- **No cutover here:** pointing the daemon at the live `stream:signal.candidate` + standing down the orchestrator's futures strategy stage is a later increment (gated by shadow validation + regime/LLM parity + Phase 5 operator sign-off).

## 8. Error handling

Reuses the proven `DecisionEngineDaemon` taxonomy (its module docstring): a setup raising → log + skip that setup (others still run); `context_provider` returning `None` → no signal this tick, sleep; XADD failure → logged (and on a fatal error the supervisor/systemd restarts). The new `FuturesContextProvider` is **fail-safe**: indicator engine not warm → return `None` (no context, no signal); macro read failure / `macro_overnight=None` → still return a context but Setup A self-guards (it requires macro and returns `None`); no scheduled events → Setup C self-guards (no recent event → `None`). The `StreamConsumerFeed` background task owns its own XREAD retry (from M1b). Graceful shutdown: stop the feed, stop the daemon, close async redis.

## 9. Testing

- **Unit — `FuturesContextProvider` (the new unit):** given a mocked indicator engine + mocked macro snapshot (Redis) + loaded events, it builds a `MarketContext` with every field correct (current_price/atr_14/15m hi-lo from engine; prev_close/today_open from market data; macro from Redis; events from YAML; vwap/percentile/spread defaulted). Returns `None` until the indicator engine is warm (`is_warm`).
- **Unit — setups stay green:** existing `SetupAGapReversion`/`SetupCEventReaction` tests are unchanged (pure classes untouched). Add a test that a provider-built context flows through `setup.check` to a `Signal` whose `to_stream_dict()` matches the 11-field schema `risk_filter` parses (`_signal_from_stream_fields`).
- **Integration:** fake-redis XADD ticks to `raw_data` → `StreamConsumerFeed` warms the engine → provider builds context → `DecisionEngineDaemon` publishes a candidate to `signal.candidate.futures.shadow`. Reuse the `test_signal_to_fill_e2e` harness pattern.
- **Regression:** with flag `off`/unset, the entrypoint is the inert stub (0 signals) — existing `decision_engine` tests green; `DecisionEngineDaemon` class unchanged; orchestrator futures paper path unchanged.
- Whole `tests/` suite green; ruff/black/mypy clean.

## 10. Out of scope

- LLM veto/tuning parity with the orchestrator adapter (next increment).
- Cutover: orchestrator futures strategy stand-down + daemon → live `signal.candidate.futures` (separate increment, Phase 5 gated).
- Stock strategy daemon (later; stock has no risk/order daemons yet).
- Changes to `risk_filter` / `order_router` (already exist; schema-compatible).
- Orderbook transport (Setup A/C don't need it; execution-side slippage is unchanged).

## 11. Risks & mitigations

| 리스크 | 완화 |
|---|---|
| 데몬이 orchestrator 선물 경로와 충돌(이중 paper) | shadow 스트림 분리 + 실 risk_filter 미연결 → 라이브/paper 무영향 |
| 지표 콜드스타트 미성숙 시그널 | parquet warmup + `is_warm` 게이트 → warm 전 provider가 `None` 반환(루프 무신호) |
| 기존 decision_engine 회귀 | `DecisionEngineDaemon` 클래스 **무변경**; flag off → 기존 stub(0 신호) 보존; 기존 테스트 게이트 |
| candidate 스키마 불일치 → risk_filter 파싱 실패 | `to_stream_dict`↔`_signal_from_stream_fields` 왕복 단위테스트로 계약 고정 |
| macro/events 누락 | fail-safe — `macro_overnight=None`이면 Setup A 미발화(이미 그 가드 있음); events 없으면 Setup C 미발화 |
| prev_close/today_open 소스(데몬은 MarketDataProvider 없음) | parquet 일봉/세션 바에서 읽기(plan에서 정확 경로 확정) |
| 운영 중 origin/main 이동(concurrent operator) | 각 단계 fetch+rebase |

## 12. Acceptance criteria

- [ ] `FuturesContextProvider` (NEW) builds a correct `MarketContext` from indicator engine + parquet (prev_close/today_open) + macro (Redis `stream:macro.overnight`) + events (YAML); returns `None` until warm; vwap/percentile/spread defaulted.
- [ ] `StreamConsumerFeed` (reused) consumes `raw_data` and keeps the daemon-local `StreamingIndicatorEngine` warm; `DecisionEngineDaemon` (reused, unchanged) polls the provider and publishes `Signal.to_stream_dict()`+`signal_id` to `signal.candidate.futures.shadow`.
- [ ] Emitted candidate round-trips through `risk_filter._signal_from_stream_fields` (11-field contract locked by test).
- [ ] **No regime/LLM** in the daemon (documented as adapter-layer, deferred); no orderbook dependency.
- [ ] Flag `off`/unset → entrypoint inert (stub, 0 signals); existing `decision_engine` + orchestrator futures tests green.
- [ ] systemd unit delivered **disabled**; shadow stream not consumed by `risk_filter`.
- [ ] Unit + integration + full suite green; lint/type clean.

## 13. Open questions (resolve in the plan)

- `prev_close` / `today_open` source for the daemon (no MarketDataProvider): which parquet daily/session read to reuse.
- `scheduled_events` source: `config/scheduled_events.yaml` (static) vs a Redis-backed loader — confirm what exists today and whether a YAML is present.
- Shadow recorder storage: SQLite runtime-ledger shadow table vs JSONL log.
- Entrypoint shape: modify `services/decision_engine/main.py::_build_and_run` to be flag-aware vs add a sibling `services/futures_strategy_daemon/main.py` reusing `DecisionEngineDaemon` (+ which systemd unit).
- `StreamConsumerFeed` reuse details: it needs an `indicator_engine` + async redis + `stream="raw_data"`; confirm its `set_volume_baseline`/futures-tick handling suits futures (cumulative volume).
- The indicator-engine getter for `last_15min_high`/`last_15min_low` (confirm the exact method/keys) + `atr_14` key name.
