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
| 의사결정 로직 | 지표 + Setup A/C + **regime gate(Redis read)** + macro/events context. **LLM veto/튜닝 미포함**(다음 증분) |
| shadow 대상 | `signal.candidate.futures.shadow` 스트림 + shadow recorder (counterfactual/EOD-proxy 비교) |
| flag | `FUTURES_STRATEGY_DAEMON` = `off`(기본) \| `shadow` |
| 프레임워크 | `StreamStage` 상속 (DRY; risk_filter/order_router/news_scorer와 동일) |
| 지표 warmup | `ParquetMarketDataStore` 1분봉 시드 (post-clickhouse 정상) |

## 3. Architecture

```
[market-ingest M1a] ──XADD──> raw_data (futures trade ticks)
                                  │ XREADGROUP (consumer group)
                                  ▼
┌──────────────── FuturesStrategyStage(StreamStage) ─────────────────┐
│ on_startup:                                                         │
│   - build StreamingIndicatorEngine (daemon-local)                  │
│   - parquet warmup: seed 1-min bars per symbol (is_warm gate)      │
│   - build StrategyManager with Setup A/C (StrategyFactory/registry)│
│   - connect Redis context reader (macro/events/regime keys)        │
│ handle_message(msg_id, fields) -> bool:                            │
│   1. parse tick fields -> (symbol, price_dict, ts)                 │
│   2. indicator_engine.on_tick(symbol, price_dict, ts)   # µs       │
│   3. decision-cadence gate: only at closed-bar boundary            │
│        - resolver.collect_entry_indicators(symbol)                 │
│        - read Redis context (macro_overnight, scheduled_events,    │
│          regime state)                                             │
│        - StrategyManager check_entries / check_exits (Setup A/C)   │
│        - if signal: XADD signal.candidate.futures.shadow           │
│   4. return True  # XACK
│ on_shutdown: flush, close redis                                    │
└────────────────────────────────────────────────────────────────────┘
        (shadow: NOT wired to live risk_filter -> no double paper path)

  [risk_filter] -> signal.final -> [order_router] (live gate suspended)
        ^ unchanged; consumes the REAL signal.candidate.futures (orchestrator path)
```

## 4. Components & responsibilities

| Unit | Responsibility | Depends on | State |
|---|---|---|---|
| `FuturesStrategyStage` | StreamStage subclass: tick→on_tick→(cadence)→Setup A/C→candidate | raw_data stream, indicator engine, StrategyManager, Redis context, parquet warmup | per-symbol rolling (indicator engine) |
| Indicator engine (daemon-local) | `StreamingIndicatorEngine` fed by ticks | — | per-symbol candle/MTF deques |
| Context reader | read `macro_overnight`/`scheduled_events`/regime from Redis keys | Redis | none |
| Setup A/C strategies | reused pure logic via `StrategyFactory`/registry (`setup_a_gap_reversion`, `setup_c_event_reaction`, `setup_target_exit`) | indicator dict + context | none |
| Shadow publisher | XADD candidates to `signal.candidate.futures.shadow` + record for comparison | Redis | none |

**Single responsibility:** the daemon owns the futures strategy stage end-to-end (tick→candidate). The indicator engine is daemon-local (no cross-process snapshot). Setup A/C remain pure classes shared with the orchestrator (no duplication).

## 5. Data flow & decision cadence

- **Per tick:** parse → `indicator_engine.on_tick` only (cheap; keeps state warm).
- **Decision cadence:** Setup A/C are evaluated only at closed-bar boundaries (the same decision-cadence gate the orchestrator uses via `StrategyManager.set_indicator_engine`), NOT every tick. Avoids per-tick candidate spam and matches orchestrator behavior.
- **Inputs split:** ticks from `raw_data` (XREADGROUP); `macro_overnight` (SP500 overnight %), `scheduled_events` (event calendar), regime state from **Redis KEY reads** (per master spec §4.1). These are the inputs the stubbed `context_provider` failed to supply.
- **Output:** `signal.candidate.futures.shadow` with the established 11-field candidate schema (`setup_type, direction, symbol, entry_price, stop_loss, take_profit, confidence, reason_tags_json, generated_at_ms, valid_until_ms, signal_id`) so it is schema-compatible with what `risk_filter` consumes (validates the contract before any cutover).

## 6. Decision-logic scope (this increment)

Included: indicator computation + **Setup A/C** entry/exit + **regime gate** (Redis read) + **macro/events context**.

Deferred (next increment, before cutover): **LLM veto + LLM tuning** (the orchestrator adapter applies these on top of pure Setup A/C). They are refinements; the shadow can be extended with them once the core path is validated. Strict orchestrator parity + cutover is a separate increment.

## 7. Shadow rollout & safety

- **Flag:** `FUTURES_STRATEGY_DAEMON` = `off` (default) | `shadow`. Off → the daemon does nothing (the systemd unit ships disabled; merging is operationally inert).
- **Shadow target:** the daemon publishes to `signal.candidate.futures.shadow` (a separate stream), **not** the live `signal.candidate.futures`. The existing `risk_filter` → `order_router` are untouched, so no second paper path is created and no live/paper position can result from the daemon.
- **Validation:** a shadow recorder logs daemon candidates; they are compared against the orchestrator's actual futures signals via counterfactual / EOD-proxy PnL (the regime-gate-analyst validation method) to confirm the core stream path produces sound signals.
- **No cutover here:** stopping the orchestrator's futures strategy stage and pointing the daemon at the live `signal.candidate.futures` is explicitly a later increment, gated by shadow validation + LLM parity + operator sign-off (Phase 5).

## 8. Error handling

Inherits `StreamStage` policy: parse error → XACK drop (poison-pill); processing failure → NO-XACK (retry); publish failure → NO-XACK. Indicator warmup incomplete → suppress signals until `is_warm(symbol)` (same gate as the orchestrator). Graceful shutdown (flush + close async redis). Redis context read failure → treat as "no context" (fail-safe: Setup C event reaction simply doesn't fire; Setup A gap reversion degrades to no-macro behavior — to be specified per strategy in the plan).

## 9. Testing

- **Unit:** `handle_message` performs tick→`on_tick`→(cadence)→Setup A/C→shadow XADD correctly; signals suppressed before `is_warm`; Redis context reads mocked; emitted candidate matches the 11-field schema `risk_filter` consumes.
- **Integration:** fake-redis XADD to `raw_data` → daemon → assert candidate on `signal.candidate.futures.shadow`. Reuse the `test_signal_to_fill_e2e` harness pattern.
- **Regression:** the orchestrator futures paper path is unchanged; with the flag `off`, behavior is identical to today; the stubbed `decision_engine` behavior (0 live signals) is preserved on the real stream.
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
| 지표 콜드스타트 미성숙 시그널 | parquet warmup + `is_warm` 게이트(orchestrator 동일) |
| decision_engine 리팩터 회귀 | flag off → 무동작; 기존 stub 동작(0 신호) 보존; 기존 테스트 게이트 |
| candidate 스키마 불일치 → risk_filter 파싱 실패 | 11-필드 스키마 단위테스트로 계약 고정(cutover 전 검증) |
| Redis context 누락 | fail-safe(컨텍스트 없음으로 처리, 전략별 명시) |
| 운영 중 origin/main 이동(concurrent operator) | 각 단계 fetch+rebase |

## 12. Acceptance criteria

- [ ] `FuturesStrategyStage(StreamStage)` consumes `raw_data`, runs daemon-local indicator engine + Setup A/C, publishes `signal.candidate.futures.shadow` (11-field schema).
- [ ] Decision cadence: Setup A/C evaluated at closed-bar boundaries, not per-tick.
- [ ] Inputs: ticks via XREADGROUP; macro/events/regime via Redis keys; warmup via parquet; `is_warm` gating.
- [ ] regime gate applied; LLM veto/tuning explicitly absent (documented).
- [ ] Flag `off` (default) → daemon inert, orchestrator futures path unchanged, existing tests green.
- [ ] systemd unit delivered **disabled**; shadow does not touch live `signal.candidate.futures`.
- [ ] Unit + integration + full suite green; lint/type clean.

## 13. Open questions (resolve in the plan)

- Exact decision-cadence hook reuse (`StrategyManager.set_indicator_engine` gating vs an explicit closed-bar trigger in the daemon).
- Redis key names for `macro_overnight` / `scheduled_events` / regime (reuse the orchestrator's existing keys — confirm exact keys).
- Shadow recorder storage (SQLite runtime ledger shadow table vs a JSONL log) for counterfactual comparison.
- Whether `decision_engine`'s current module/entrypoint is already `StreamStage`-shaped or needs reshaping (confirmed during planning).
- Async redis client lifecycle in the daemon (mirror the M1/M0 daemon idiom).
