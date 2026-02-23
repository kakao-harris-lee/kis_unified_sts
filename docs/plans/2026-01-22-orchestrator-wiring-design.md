# Orchestrator Strategy Wiring Design

**Date:** 2026-01-22
**Status:** Implemented (2026-01-22)

## Problem

The `TradingOrchestrator._create_pipeline()` uses dummy handlers instead of real strategy components:

```python
# Current (dummy)
async def dummy_entry():
    return None
```

The `StrategyFactory` and strategy implementations exist but aren't wired to the pipeline.

## Solution Overview

Wire the orchestrator to use real strategies via:
1. **StrategyManager** - Load and execute multiple strategies
2. **MarketDataProvider** - Shared data fetching with cache
3. **PositionTracker** - Track positions and state transitions
4. **Real pipeline handlers** - Connect components to pipeline stages

## Architecture

```
TradingOrchestrator
    │
    ├── MarketDataProvider (shared)
    │       └── Fetches data once per interval
    │       └── Caches for all strategies
    │
    ├── StrategyManager
    │       └── Loads all enabled strategies via StrategyFactory
    │       └── Runs entry/exit checks across all strategies
    │
    ├── PositionTracker
    │       └── Tracks open positions
    │       └── Manages state transitions (SURVIVAL → BREAKEVEN → MAXIMIZE)
    │
    └── TradingPipeline (4 stages)
            ├── REGIME: Detect market state (shared across strategies)
            ├── ENTRY: Run all entry strategies → collect signals
            ├── MONITORING: Update position states
            └── EXIT: Run all exit strategies → collect signals
```

## Files to Create/Modify

### New Files

#### 1. `services/trading/data_provider.py`
Market data provider with caching:
- Fetches data for configured symbols
- Caches data with TTL to reduce API calls
- Provides data with calculated indicators

#### 2. `services/trading/strategy_manager.py`
Multi-strategy manager:
- Loads strategies via `StrategyFactory`
- Calls `register_builtin_components()` on init
- Aggregates entry signals from all strategies
- Routes exit checks to appropriate strategy per position

#### 3. `services/trading/position_tracker.py`
Position state management:
- Tracks open positions
- Updates highest prices for trailing stops
- Manages state transitions
- Maps positions to their originating strategy

### Modified Files

#### 4. `services/trading/orchestrator.py`
- Initialize `MarketDataProvider`, `StrategyManager`, `PositionTracker`
- Implement real handlers: `_handle_regime`, `_handle_entry`, `_handle_monitoring`, `_handle_exit`
- Connect to `PaperBroker` when `config.paper_trading=True`

## Handler Specifications

### `_handle_regime()` (every 5 min)
1. Fetch market data
2. Calculate MFI/ADX indicators
3. Classify market state (BULL, BEAR, SIDEWAYS_*)
4. Store in `self._current_regime`

### `_handle_entry()` (every 1 sec)
1. Skip if BEAR market or max positions reached
2. Fetch market data
3. Build `EntryContext` with indicators
4. Call `strategy_manager.check_entries(context)`
5. Execute orders for valid signals
6. Track new positions

### `_handle_monitoring()` (every 0.1 sec)
1. Update current prices for all positions
2. Update highest prices (for trailing stops)
3. Call `exit_strategy.update_position_state()` for state transitions

### `_handle_exit()` (every 0.5 sec)
1. Get open positions
2. Fetch market data
3. Call `strategy_manager.check_exits()`
4. Execute exit orders
5. Remove closed positions from tracker

## Execution Layer

```python
async def _execute_entry(self, signal: Signal):
    if self.config.paper_trading:
        order = await self._paper_broker.submit_order(...)
    else:
        order = await self._kis_client.place_order(...)

    if order.is_filled:
        self._position_tracker.add_position(order, signal.strategy)
```

## Implementation Order

1. `data_provider.py` - No internal dependencies
2. `position_tracker.py` - Uses `shared/models`
3. `strategy_manager.py` - Uses registry, strategies
4. `orchestrator.py` - Integrates all components

## Testing Strategy

1. Unit tests for each new component
2. Integration test: Orchestrator with paper trading
3. Test with mock market data
4. Verify position state transitions work correctly

## Out of Scope

- Live KIS API trading (uses paper trading)
- Real-time WebSocket data (uses polling)
- Multiple asset classes in single orchestrator
- Dashboard/UI updates
