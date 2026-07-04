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

Status: branch implemented.

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

Status: branch implemented.

Split `shared/strategy/entry/setup_adapters.py` into focused modules:

- `setup_entry_configs.py`: Pydantic config classes.
- `setup_context_builder.py`: `EntryContext` -> decision `MarketContext`.
- `setup_signal_mapper.py`: decision signal -> orchestrator signal.
- `setup_llm_gate.py`: LLM tuning, veto, and regime-label helpers.
- `setup_eval_publisher.py`: setup evaluation Redis/latest/history publisher.

Keep `setup_adapters.py` as the compatibility facade and adapter-class owner
until a later adapter-class split can retire legacy private monkeypatch points.
No behavior changes are allowed in this phase.

### Phase R2 - Strategy Registry And Factory Split

Status: branch implemented.

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

Status: branch implemented for runtime configuration; broader service
extraction remains in progress.

Design and executable Task 1 plan:

- `docs/superpowers/specs/2026-07-04-orchestrator-decomposition-design.md`
- `docs/superpowers/plans/2026-07-04-orchestrator-decomposition.md`

Continue extracting `services/trading/orchestrator.py` by existing ownership
boundaries, not by arbitrary line counts:

- runtime configuration and entry re-entry guard config: branch implemented in
  `services/trading/runtime_config.py` with orchestrator facade exports;
- trading package facade: branch implemented with lazy top-level exports so
  runtime config and other lightweight submodule imports do not eagerly load
  the monolithic orchestrator;
- re-entry guard helpers: branch implemented in
  `services/trading/reentry_guard.py`; orchestrator compatibility methods now
  delegate cooldown key/record/block logic to the owner module;
- initialization and dependency wiring;
- recovery and reconciliation;
- execution setup and order submission;
- position state transitions;
- kill-switch and live-mode guard hooks;
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

- Which orchestrator boundary should follow runtime configuration:
  initialization/dependency wiring or recovery/reconciliation?
- Should monitor bridges migrate to `MultiStreamStage`, or should they stay as
  direct multi-stream loops with explicit retry documentation?
- After F-9, how long should the monolithic futures runtime remain as rollback
  code before archival or hard disablement?
