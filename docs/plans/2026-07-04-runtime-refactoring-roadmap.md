# Runtime Refactoring And Event-Driven Roadmap

> Status: Active planning. This plan adds architecture direction only; it does
> not approve runtime behavior changes, live trading changes, or F-9 cutover.

## Goal

Reduce coupling and agent context cost while preserving the current trading
contracts: config-driven behavior, Redis DB 1 runtime state, signal-driven stock
swing exits, futures long/short symmetry, and producer -> processor -> read-model
publisher boundaries.

The refactor should make new strategy or hedge code writable from small contract
files instead of requiring agents or developers to load large runtime modules.

## Current Findings

- The repo already has the important architecture primitives: strategy registry
  and `StrategyFactory`, `StreamStage`, `TradingStatePublisher`, Redis stream
  contracts, setup adapters, and shared config loaders.
- The main debt is not a missing pattern; it is pattern surface area spread
  across large modules. High-cost examples are:
  - `services/trading/orchestrator.py`: monolithic futures paper/live runtime
    with initialization, recovery, execution setup, position state, kill-switch
    hooks, and signal flow in one class.
  - `shared/strategy/entry/setup_adapters.py`: setup configs, context
    conversion, LLM gates, veto, daily bias, signal mapping, and adapter classes
    in one file.
  - Monitor and router services: several loops use local retry or direct stream
    reads instead of a uniform small contract surface.
- Stock trading is already on a decoupled event-driven pipeline. Futures has a
  decoupled chain implemented behind profiles, but the monolithic
  `trader-futures` path remains the primary futures paper runtime until F-9.

## Completed Progress

### 2026-07-04 - Runtime Refactoring Follow-Ups

Status: done in `2140c9ed`.

Merged the additive pattern surfaces and first orchestrator decomposition
follow-ups:

- `shared/decision/interfaces.py`, `shared/strategy/interfaces.py`, and
  `shared/portfolio/interfaces.py` provide thin Protocol-style contracts.
- `shared/resilience/retry.py::retry_on_disconnect` provides the narrow retry
  decorator surface for disconnect/timeout-safe infrastructure calls.
- `shared/strategy/factory.py` and `shared/strategy/builtin_components.py`
  split strategy assembly and builtin registration while
  `shared/strategy/registry.py` stays the compatibility facade.
- `shared/strategy/entry/setup_adapters.py` is now a small compatibility
  facade; setup config, context, signal mapping, LLM gate, setup-eval
  publishing, and Setup A/C/D adapter classes live in owner modules.
- `services/trading/__init__.py` lazily resolves lightweight submodules without
  importing the monolithic orchestrator.
- `services/trading/runtime_config.py`, `reentry_guard.py`,
  `startup_sequence.py`, `execution_facade.py`, `execution_runtime.py`,
  `market_data_bootstrap.py`, and `recovery.py::PositionRecoveryService` own the
  first runtime slices while orchestrator compatibility methods remain.

Verification included targeted pytest for strategy interfaces, retry,
registry/setup adapters, startup sequence, execution runtime, recovery, package
imports, and orchestrator behavior guards, plus targeted `ruff check`,
`black --check`, `python3 -m py_compile`, and `git diff --check`.

### 2026-07-04 - Runtime Large-File Split Priority 3

Status: done in `83e94681`.

Completed the runtime large-file split for the requested priority-3 files
without changing runtime behavior or public imports:

- `services/trading/position_tracker.py`: kept `PositionTracker` as the public
  shell and moved config/event models, runtime-ledger persistence, legacy
  archive persistence, auto-flush lifecycle, and event-view helpers into focused
  modules.
- `services/trading/indicator_engine.py`: kept `StreamingIndicatorEngine` as
  the public shell and moved candle primitives, query/read methods, and
  calculation helpers into focused modules.
- `services/trading/data_provider.py`: kept `MarketDataProvider` as the public
  shell and moved provider model types plus runtime/failover/cache behavior into
  separate modules.
- `services/stock_strategy/daemon.py`: kept `StockStrategyDaemon` as the public
  shell and moved market-risk gate handling, LLM discovery, and evaluation loop
  behavior into mixins.
- `shared/storage/runtime_ledger.py`: kept `SQLiteRuntimeLedger` as the public
  shell and moved schema, record, portfolio, prediction, helper, and error
  surfaces into separate modules.

Verification:

- Targeted pytest for position tracking, data provider, indicator engine,
  stock-strategy daemon, and runtime ledger passed.
- Targeted `ruff check`, `black --check`, and `python3 -m py_compile` passed
  for the 25 touched runtime files.

## Refactoring Principles

- Add thin contracts before moving behavior. New interfaces, decorators, and
  factories should be additive and covered by characterization tests first.
- Do not rewrite large modules only because they are large. Extract low-risk
  seams that already have a stable dependency boundary.
- Keep stream ownership explicit. Producers publish events, processors consume
  and emit the next event, read-model publishers update dashboard state.
- Preserve ACK/NOACK semantics. A poison pill is consumed; a transient broker,
  Redis, or publish failure remains pending or retries according to the owning
  stage contract.
- Keep thresholds, symbols, Redis keys, TTLs, ports, risk values, and schedules
  in YAML/env/config files.

## Pattern Plan

### 1. Interface Pattern - Thin Context Contracts

Create small contract files that expose only method names and input/output
types. Existing dataclasses can continue to satisfy them structurally.

Initial files:

- `shared/decision/interfaces.py`
  - `ScheduledEventView`
  - `FuturesMarketView`
  - `SetupSignalGenerator`
- `shared/strategy/interfaces.py`
  - `EntrySignalGeneratorProtocol`
  - `ExitSignalGeneratorProtocol`
  - `PositionSizerProtocol`
- `shared/portfolio/interfaces.py`
  - `HedgeExposureView`
  - `HedgeAdvisorProtocol`

Expected outcome: a developer or agent can implement a futures setup or hedge
advisor by reading a small interface file plus one focused test, without loading
the orchestrator or full setup-adapter module.

### 2. Decorator Pattern - Retry And Disconnect Defense

Add one reusable decorator surface for infrastructure retries:

- `shared/resilience/retry.py::retry_on_disconnect`

The decorator should wrap the existing retry policy rather than introduce a
new policy. It should default to a narrow transient exception set such as
`ConnectionError` and `TimeoutError`, with explicit config for attempts, delay,
and opt-in custom exception tuples. Broad `OSError` retry should remain caller
opt-in.

Do not apply it to Redis stream handlers blindly. `StreamStage.handle_message`
already owns ACK/NOACK semantics, so retry decoration belongs around small
infrastructure calls where retry is safe and idempotency is clear.

### 3. Factory Pattern - Stop Conditional Exploration

Keep the existing registry behavior, but split factory concerns so future edits
do not require loading the whole registry file:

- `shared/strategy/factory.py`: strategy assembly from config.
- `shared/strategy/builtin_components.py`: builtin registration table.
- `shared/strategy/entry/setup_factory.py`: Setup A/C/D config -> setup instance.
- `shared/strategy/registry.py`: registry API and backward-compatible exports.

The first change should be re-export compatible so imports such as
`from shared.strategy.registry import StrategyFactory` continue to work.

## Monolith Decomposition Sequence

### Phase R0 - Contract Tests

Status: done.

- Added Protocol/import compatibility tests for the new decision, strategy, and
  portfolio interface files.
- Added focused retry-decorator tests, including the non-disconnect `OSError`
  guard.
- Re-ran existing characterization tests around `StrategyFactory.create_all`
  and Setup A/C/D adapter behavior before moving code.
- Verification target:
  - `pytest tests/unit/strategy/test_registry_builtin_components.py -v`
  - `pytest tests/unit/strategy/test_setup_adapters.py -v`
  - `pytest tests/unit/decision/test_setup_a_gap_reversion.py tests/unit/decision/test_setup_c_event_reaction.py tests/unit/decision/test_setup_d_vwap_reversion.py -v`

### Phase R1 - Setup Adapter Split

Status: done.

Split `shared/strategy/entry/setup_adapters.py` into focused modules:

- `setup_entry_configs.py`: Pydantic config classes.
- `setup_context_builder.py`: `EntryContext` -> decision `MarketContext`.
- `setup_signal_mapper.py`: decision signal -> orchestrator signal.
- `setup_llm_gate.py`: LLM tuning, veto, and regime-label helpers.
- `setup_eval_publisher.py`: setup evaluation Redis/latest/history publisher.

`setup_adapters.py` now stays as the compatibility facade. Setup A/C/D adapter
classes live in `setup_a_adapter.py`, `setup_c_adapter.py`, and
`setup_d_adapter.py`; legacy top-level symbols and monkeypatch points are
preserved by facade tests. No behavior changes were made in this phase.

### Phase R2 - Strategy Registry And Factory Split

Status: done.

Move builtin tables and factory assembly out of `shared/strategy/registry.py`.
The registry module should remain the stable public import surface while the
implementation becomes small and searchable.

Implemented split:

- `shared/strategy/factory.py`: `StrategyFactory` assembly from config.
- `shared/strategy/builtin_components.py`: builtin component tables and
  registration helper.
- `shared/strategy/registry.py`: registry classes, exceptions, and backward
  compatible facade exports.

### Phase R3 - Orchestrator Service Extraction

Status: in progress. The first owner modules are merged; the orchestrator is
still the largest compatibility runtime at 7,102 lines.

Design and executable Task 1 plan:

- `docs/superpowers/specs/2026-07-04-orchestrator-decomposition-design.md`
- `docs/superpowers/plans/2026-07-04-orchestrator-decomposition.md`

Continue extracting `services/trading/orchestrator.py` by existing ownership
boundaries, not by arbitrary line counts. The next actionable priority plan is:

- `docs/superpowers/plans/2026-07-04-runtime-refactoring-next-priorities.md`

Merged owner modules:

- runtime configuration and entry re-entry guard config: done in
  `services/trading/runtime_config.py` with orchestrator facade exports;
- trading package facade: done with lazy top-level exports so
  runtime config and other lightweight submodule imports do not eagerly load
  the monolithic orchestrator;
- re-entry guard helpers: done in
  `services/trading/reentry_guard.py`; orchestrator compatibility methods now
  delegate cooldown key/record/block logic to the owner module;
- startup sequence: done in `services/trading/startup_sequence.py`;
- execution helpers/runtime: done in `services/trading/execution_facade.py` and
  `services/trading/execution_runtime.py`; orchestrator compatibility methods
  now delegate pure entry-order result normalization, signal direction
  extraction, entry metadata finalization, state-transition serialization,
  entry slippage-stat accumulation, and mock-mirror metadata helpers to owner
  modules;
- initialization and kill-switch runtime helper micro-slice: done in
  `services/trading/initialization_runtime.py` and
  `services/trading/kill_switch_runtime.py`; orchestrator keeps startup ordering,
  Redis polling, flattening, sentinel cleanup, notifications, and live-guard side
  effects while delegating futures-asset guard checks and force-flatten request
  metadata parsing;
- recovery service: done in `services/trading/recovery.py`; Redis recovery,
  freshness checks, `Position` reconstruction, tracker registration, symbol
  subscription injection, and SQLite fallback delegation live in the owner
  service;
- market-data bootstrap helpers: done in
  `services/trading/market_data_bootstrap.py`; orchestrator compatibility
  methods now assign KIS client, price feed, data provider, and tick publisher
  results returned by the owner module;

Remaining high-priority slices:

- execution/order lifecycle beyond pure metadata helpers;
- initialization ordering and dependency wiring beyond pure guard checks;
- position state transitions;
- kill-switch and live-mode guard side effects;
- universe and market-data runtime helpers;
- strategy-entry context assembly.

Each extraction must have a delegation guard or characterization test before
the orchestration call site changes. This phase must not alter stock swing exit
policy or futures long/short symmetry.

## Event-Driven Transition Plan

### Event-Driven Target Shape

The target runtime should keep this shape:

```text
producer -> stream -> processor -> stream -> read-model publisher
```

For futures, the intended chain remains:

```text
market_ingest -> decision_engine -> risk_filter -> order_router -> futures_monitor
```

For stock, preserve the current decoupled chain:

```text
stock_ingest -> stock_strategy -> stock_risk_filter -> stock_order_router
-> stock_exit -> stock_monitor
```

### Futures Primary Runtime

The monolithic futures path should be treated as a compatibility runtime until
F-9 gates approve the decoupled chain as primary. Do not create a second
side-channel around the stream pipeline. The safe sequence is:

1. Keep the monolith stable while R0-R3 reduce shared strategy and runtime
   configuration context cost.
2. Use F-9 shadow evidence to validate the decoupled futures stream chain.
3. Resolve O13 kill-switch coverage for the monolithic path before cutover.
4. After written operator approval, flip the primary runtime through the
   existing F-9 runbook and daemon-mode environment flags.
5. After cutover, retire or quarantine monolithic futures entry/execution
   code behind explicit rollback documentation.

### Stream Framework Consolidation

Use `StreamStage` or `MultiStreamStage` as the preferred consumer-group loop for
new processors. Direct `xreadgroup` loops should remain only when they are
monitor bridges or have a documented reason. Where direct loops stay, they must
still document:

- stream names and TTL ownership;
- poison-pill vs transient failure behavior;
- pending retry or deliberate non-retry policy;
- dashboard/read-model publication contract.

## Acceptance Gates

- New contracts are small enough to read independently and have direct tests.
- Existing imports continue to work during transition.
- No runtime Redis key loses its TTL.
- No stream ACK/NOACK behavior changes without a test that names the old and new
  behavior.
- Stock pipeline remains decoupled and signal-exit driven.
- Futures direction handling remains symmetric.
- F-9 remains the only approved path for replacing the primary futures
  orchestrator runtime.

## Open Questions

- Which orchestrator boundary should follow the latest merged recovery service:
  execution/order lifecycle or initialization/dependency wiring?
- Should monitor bridges migrate to `MultiStreamStage`, or should they stay as
  direct multi-stream loops with explicit retry documentation?
- After F-9, how long should the monolithic futures runtime remain as rollback
  code before archival or hard disablement?
