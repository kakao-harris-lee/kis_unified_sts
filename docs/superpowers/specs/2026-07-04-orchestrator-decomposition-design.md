# Orchestrator Decomposition Design

Date: 2026-07-04

## Goal

Reduce `services/trading/orchestrator.py` from a monolithic compatibility
runtime into a thin facade over focused owner modules, while keeping F-9 as the
only approved path for replacing the primary futures runtime.

## Context

`TradingOrchestrator` still owns futures paper/live unless the F-9 cutover is
explicitly performed. It also contains legacy stock-path compatibility code,
session scheduling, universe refresh, indicator feed wiring, strategy context
assembly, risk checks, order execution, position transitions, metrics,
Telegram, and Redis state publication. The file is large because stage handlers
are injected into `TradingPipeline`, but the stage implementations still live
inside the same class.

The repo already has the target event-driven futures chain:

```text
market_ingest -> decision_engine -> risk_filter -> order_router -> futures_monitor
```

This design does not create another runtime path. It makes the remaining
orchestrator easier to reason about until F-9 shadow/live gates allow that
compatibility path to be disabled.

## Architecture

Keep `services.trading.orchestrator` as the stable import surface. Move cohesive
responsibilities into small modules and import/re-export public compatibility
names from the facade. Existing tests and callers that import `TradingConfig`,
`TradingState`, `MarketSchedule`, `HolidayCache`, or `is_trading_day` from
`services.trading.orchestrator` must continue to work.

Extract in this order:

1. Session calendar and status types.
2. Entry re-entry guard configuration and state helpers.
3. Runtime config and pipeline creation helpers.
4. Recovery and broker reconciliation.
5. Execution submission and position transition handlers.

Each extraction starts with owner-module tests plus compatibility tests through
the orchestrator import path. The orchestrator method can remain as a facade
while internals delegate to the owner module.

## Event-Driven Transition

Futures primary-runtime replacement remains F-9 only. The decomposition work is
not a cutover and must not start `futures-market-ingest` while `trader-futures`
owns the KIS futures WebSocket. Shadow evidence, O13 kill-switch coverage, and
operator approval remain required before `FUTURES_ORCHESTRATOR_ENABLED=false`.

After F-9 cutover, the monolithic futures entry/execution code can be
quarantined behind rollback documentation. Before cutover, it is compatibility
code and should be stabilized, not rewritten wholesale.

## Error Handling

Do not change Redis stream ACK/NOACK behavior in this refactor. New stream
processors should use `StreamStage` or document why they do not. New Redis keys
must keep TTLs. Existing stock swing exits remain signal-driven, and futures
entry/exit direction must continue to follow `signal_direction`.

## Testing

Every extraction needs:

- Owner-module tests for the new module.
- Compatibility tests through `services.trading.orchestrator`.
- Existing targeted orchestrator tests for the touched surface.
- `ruff`, `black --check`, and `py_compile` over touched files.

The first implementation slice extracts session calendar concerns into a new
module without changing runtime behavior.
