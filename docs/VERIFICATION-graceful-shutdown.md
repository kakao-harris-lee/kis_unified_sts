# Verification Report: SIGTERM/SIGINT Handlers in CLI Commands

**Task:** Subtask 1-1 - Verify SIGTERM/SIGINT handlers in CLI commands
**Date:** 2026-03-05
**Reviewer:** Claude Agent

## Executive Summary

✅ **PASS** - SIGTERM/SIGINT signal handlers are correctly implemented in all CLI commands that use `TradingOrchestrator`.

Both commands implement proper signal handling with:
- Duplicate signal prevention via `shutdown_requested` flag
- Graceful shutdown via `orchestrator.stop()`
- Proper cleanup in `finally` block

## Commands Verified

### 1. `sts trade start` (cli/main.py:1315-1398)

**Location:** Lines 1368-1398
**Signal Handler:** Lines 1373-1381
**Orchestrator Usage:** Line 1363

**Implementation:**
```python
def _request_shutdown():
    nonlocal shutdown_requested
    if shutdown_requested:
        return
    shutdown_requested = True
    logging.getLogger("cli.main").info(
        "Shutdown signal received, stopping gracefully..."
    )
    asyncio.ensure_future(orchestrator.stop())

for sig in (signal.SIGTERM, signal.SIGINT):
    loop.add_signal_handler(sig, _request_shutdown)
```

**Findings:**
- ✅ Handles both SIGTERM and SIGINT
- ✅ Uses `shutdown_requested` flag to prevent concurrent shutdown attempts
- ✅ Calls `orchestrator.stop()` via `asyncio.ensure_future()`
- ✅ Logs shutdown event
- ✅ `finally` block ensures cleanup even if signal wasn't received (line 1392-1393)
- ⚠️ **NOTE:** No timeout parameter passed to `orchestrator.stop()` - uses default 10.0s

### 2. `sts rl paper` (cli/main.py:2262-2358)

**Location:** Lines 2327-2358
**Signal Handler:** Lines 2333-2341
**Orchestrator Usage:** Line 2325

**Implementation:**
```python
def _request_shutdown():
    nonlocal shutdown_requested
    if shutdown_requested:
        return
    shutdown_requested = True
    logging.getLogger("cli.main").info(
        "Shutdown signal received, stopping gracefully..."
    )
    asyncio.ensure_future(orchestrator.stop())

for sig in (signal.SIGTERM, signal.SIGINT):
    loop.add_signal_handler(sig, _request_shutdown)
```

**Findings:**
- ✅ Handles both SIGTERM and SIGINT
- ✅ Uses `shutdown_requested` flag to prevent concurrent shutdown attempts
- ✅ Calls `orchestrator.stop()` via `asyncio.ensure_future()`
- ✅ Logs shutdown event
- ✅ `finally` block ensures cleanup even if signal wasn't received (line 2352-2353)
- ⚠️ **NOTE:** No timeout parameter passed to `orchestrator.stop()` - uses default 10.0s

## Other Async Commands

The following async commands do **NOT** use `TradingOrchestrator` and therefore do not require orchestrator-specific signal handlers:

### `sts collect start` (cli/main.py:1209)
- Uses `DataCollector` instead of `TradingOrchestrator`
- Relies on `KeyboardInterrupt` exception handling (line 1248)
- Calls `collector.stop()` in `finally` block (line 1241)
- ⚠️ **POTENTIAL GAP:** Does not handle SIGTERM, only SIGINT (Ctrl+C)

### `sts paper start` (cli/main.py:1488)
- Uses `PaperTradingEngine` instead of `TradingOrchestrator`
- Relies on `KeyboardInterrupt` exception handling (line 1559)
- Calls `engine.stop()` in `finally` block (line 1545)
- ⚠️ **POTENTIAL GAP:** Does not handle SIGTERM, only SIGINT (Ctrl+C)

## Critical Findings

### 1. Timeout Mismatch (CRITICAL)

**Issue:** The orchestrator uses a default timeout of 10.0s (services/trading/orchestrator.py:2231), but cron scripts use a 5s grace period before SIGKILL.

**Impact:** If graceful shutdown takes longer than 5 seconds, the process will be killed before it completes, potentially losing position data.

**Evidence:**
- `orchestrator.stop(timeout=10.0)` - default timeout is 10 seconds
- Cron scripts use `sleep 5` before SIGKILL (needs verification in subtask-1-3)
- CLI signal handlers call `orchestrator.stop()` without timeout parameter

**Recommendation:** See implementation_plan.json subtask-3-2 for resolution options.

### 2. Shutdown Request Flag Pattern (GOOD)

**Implementation:**
- Both commands use identical `shutdown_requested` flag pattern
- Flag prevents concurrent shutdown attempts
- Flag is checked in `finally` block to avoid double-stop

**Validation:**
- ✅ Flag is set before calling `orchestrator.stop()`
- ✅ Guard clause returns early if flag is already set
- ✅ `finally` block checks flag before calling `stop()` again
- ✅ Thread-safe (all operations on event loop thread via signal handlers)

## Pattern Consistency

Both signal handler implementations are **identical** (DRY violation potential):
- Same variable names (`shutdown_requested`, `loop`)
- Same signal handling logic
- Same logging patterns
- Same `asyncio.ensure_future()` usage

**Recommendation:** Consider extracting this pattern into a reusable function/decorator if more commands adopt TradingOrchestrator.

## Verification Checklist

- [x] `sts trade start` has SIGTERM/SIGINT handlers
- [x] `sts rl paper` has SIGTERM/SIGINT handlers
- [x] Handlers call `orchestrator.stop()`
- [x] Handlers use `shutdown_requested` flag correctly
- [x] `finally` blocks prevent double-stop
- [x] All TradingOrchestrator usages covered
- [ ] Timeout alignment with cron scripts (see subtask-1-3)
- [ ] Other async commands may need SIGTERM handling

## Recommendations

### High Priority
1. **Verify cron timeout alignment** (subtask-1-3) - Critical for data safety
2. **Consider adding SIGTERM handlers to `collect start` and `paper start`** - Currently only handle SIGINT

### Low Priority
3. **Extract signal handler pattern** - Reduce code duplication if more commands adopt this pattern
4. **Consider explicit timeout in CLI** - Currently relies on orchestrator default (10.0s)

## Conclusion

✅ **The current implementation correctly handles SIGTERM/SIGINT for all TradingOrchestrator commands.**

The signal handlers:
- Register both SIGTERM and SIGINT
- Call `orchestrator.stop()` for graceful shutdown
- Prevent concurrent shutdowns via flag
- Ensure cleanup in `finally` blocks

**Next Steps:**
1. Proceed to subtask-1-2 (verify Redis flush)
2. Proceed to subtask-1-3 (verify cron timeouts) - CRITICAL for timeout mismatch issue
3. Consider adding SIGTERM handlers to other async commands
