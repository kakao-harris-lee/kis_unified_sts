# Runtime Refactoring Next Priorities Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the remaining high-value runtime refactoring targets after the 2026-07-04 decomposition merge, without changing trading behavior or bypassing the F-9 futures cutover path.

**Architecture:** Work in isolated branches/worktrees per priority lane. Keep compatibility facades in place, add characterization/delegation tests before moving behavior, and prefer owner modules that can be read without loading `services/trading/orchestrator.py`. The futures monolith remains a compatibility runtime until F-9 gates approve the event-driven chain.

**Tech Stack:** Python 3, pytest, ruff, black, Redis DB 1 runtime contracts, SQLite RuntimeLedger, Click CLI, FastAPI dashboard routes, Next.js Workbench.

---

## Current Baseline

Use `main` at or after `59e18a72 Refactor runtime command and parser ownership
slices`.

Already merged:

- thin interface files: `shared/decision/interfaces.py`, `shared/strategy/interfaces.py`, `shared/portfolio/interfaces.py`;
- retry decorator: `shared/resilience/retry.py::retry_on_disconnect`;
- strategy registry/factory split: `shared/strategy/factory.py`, `shared/strategy/builtin_components.py`;
- setup adapter decomposition and class-owner split:
  `shared/strategy/entry/setup_{a,c,d}_adapter.py`,
  `setup_entry_configs.py`, `setup_context_builder.py`,
  `setup_signal_mapper.py`, `setup_eval_publisher.py`, `setup_llm_gate.py`;
- trading facade/runtime slices:
  `services/trading/runtime_config.py`, `reentry_guard.py`,
  `execution_facade.py`, `execution_runtime.py`, `recovery.py`,
  `market_data_bootstrap.py`, `startup_sequence.py`;
- second-wave pure runtime/parser splits:
  `services/trading/initialization_runtime.py`,
  `services/trading/kill_switch_runtime.py`,
  `services/trading/entry_runtime.py`, `signals_all_runtime.py`,
  `session_calendar.py::next_session_wake`,
  `runtime_config.py::risk_params_for_runtime_capital`,
  `shared/kis/target_price.py`,
  `shared/collector/historical/ohlcv_parser.py`,
  `services/dashboard/routes/trades_lifecycle_data.py`;
- CLI command modules:
  `cli/commands/backfill.py`, `stock_backfill.py`, `trading_control.py`,
  `paper.py`, `health.py`, `common.py`;
- package lazy imports in `services/trading/__init__.py`.

Current large-file scan after the second-wave refactor branch:

| File | Lines | Priority |
|---|---:|---|
| `services/trading/orchestrator.py` | 6995 | P1 |
| `cli/main.py` | 1184 | P2 |
| `shared/kis/client.py` | 1237 | P3 |
| `services/screener.py` | 1172 | P3 |
| `shared/kis/websocket.py` | 1074 | P3 |
| `shared/collector/historical/parquet_backfill.py` | 1030 | P3 |
| `shared/collector/historical/backfill.py` | 1019 | P3 |
| `services/dashboard/routes/trades_lifecycle.py` | 501 | P2 |
| `services/dashboard/routes/health.py` | 490 | P3 |
| `services/dashboard/routes/kis_builder.py` | 464 | P3 |
| `services/dashboard/routes/signals.py` | 359 | P3 |
| `services/dashboard/routes/trades.py` | 330 | P2 |

## Conflict Rules

- Current-state caution: `initialization_runtime.py` and
  `kill_switch_runtime.py` are already merged. Do not recreate those lanes as
  first-time extraction work; only extend them when a new owner-helper boundary
  is covered by tests.
- Create one worktree per task lane. Do not work in the default checkout if it has user files.
- Do not edit `shared/llm/*` in this plan unless a task explicitly adds a test proving no LLM runtime behavior changed.
- Do not change stock swing exit policy; no blanket EOD liquidation.
- Do not change futures long/short symmetry; `signal_direction` remains the source of truth.
- Do not replace the monolithic futures primary runtime outside the F-9 runbook.
- Any new Redis key must use DB 1 and document TTL ownership.
- If a route, command, import, or private monkeypatch surface currently works, keep a compatibility facade and add a regression test.

## Verification Commands

Run focused checks after each task:

```bash
pytest <task-specific tests> -q --tb=short
ruff check <changed python files>
black --check <changed python files>
python3 -m py_compile <changed python files>
git diff --check
```

Before merging a lane that touches orchestrator execution, recovery, live-mode,
or stream behavior, also run:

```bash
pytest \
  tests/unit/trading/test_startup_sequence.py \
  tests/unit/trading/test_execution_runtime.py \
  tests/unit/trading/test_recovery_helpers.py \
  tests/unit/trading/test_position_recovery.py \
  tests/unit/trading/test_orchestrator_db_schema.py \
  tests/unit/trading/test_broker_verification.py \
  tests/unit/trading/test_reconciliation_pnl.py \
  tests/unit/trading/test_eod_close_policy.py \
  tests/unit/trading/test_orchestrator_exit_enrichment.py::TestOvernightSwingInjection \
  tests/unit/trading/test_orchestrator_live_guard.py \
  tests/unit/trading/test_package_imports.py \
  -q --tb=short
```

---

## Priority 1: Orchestrator Runtime Slices

Target: reduce `services/trading/orchestrator.py` by extracting behavior owner
modules while keeping existing public/private orchestrator methods callable.

### Task 1.1: Entry/Exit Execution Lifecycle Owner

**Files:**

- Modify: `services/trading/execution_runtime.py`
- Modify: `services/trading/orchestrator.py`
- Test: `tests/unit/trading/test_execution_runtime.py`
- Test: `tests/unit/trading/test_orchestrator_execution_delegation.py`

- [ ] **Step 1: Add characterization tests for pure execution helpers**

Append tests that cover every helper before moving any additional logic:

```python
from types import SimpleNamespace

from services.trading.execution_runtime import (
    finalize_entry_execution_metadata,
    mock_mirror_exit_should_skip,
    record_mock_mirror_result,
)


def test_finalize_entry_execution_metadata_keeps_source_mapping_immutable():
    source = {"submit_price": 101.0}
    signal = SimpleNamespace(price=100.0)

    result = finalize_entry_execution_metadata(
        signal=signal,
        fill_price=99.5,
        is_short=False,
        execution_meta=source,
        tick_size=0.5,
    )

    assert source == {"submit_price": 101.0}
    assert result["signal_price"] == 100.0
    assert result["submit_price"] == 101.0
    assert result["fill_price"] == 99.5
    assert "slippage_ticks" in result


def test_record_mock_mirror_result_normalizes_missing_result():
    position = SimpleNamespace(metadata={})
    stats: dict[str, int] = {}

    record_mock_mirror_result(position, stats, "entry", None)

    assert position.metadata["mock_mirror"]["entry"]["success"] is False
    assert stats == {"entry_failed": 1}


def test_mock_mirror_exit_should_skip_after_entry_failure():
    position = SimpleNamespace(
        metadata={"mock_mirror": {"entry": {"success": False}}}
    )

    assert mock_mirror_exit_should_skip(position) is True
```

- [ ] **Step 2: Run tests and confirm baseline**

Run:

```bash
pytest tests/unit/trading/test_execution_runtime.py -q --tb=short
```

Expected: PASS before behavior moves.

- [ ] **Step 3: Move only pure metadata/result code first**

Move additional pure helpers from `orchestrator.py` into
`execution_runtime.py` only when they have no broker/network/Redis side effects.
Keep orchestrator methods as delegating wrappers:

```python
def _finalize_entry_execution_meta(
    self,
    signal: Signal,
    fill_price: float,
    is_short: bool,
    execution_meta: dict[str, Any],
) -> dict[str, Any]:
    return execution_runtime.finalize_entry_execution_metadata(
        signal=signal,
        fill_price=fill_price,
        is_short=is_short,
        execution_meta=execution_meta,
        tick_size=self._futures_tick_size,
    )
```

- [ ] **Step 4: Add delegation guard**

Create `tests/unit/trading/test_orchestrator_execution_delegation.py`:

```python
from types import SimpleNamespace

from services.trading.orchestrator import TradingOrchestrator


def test_orchestrator_finalizes_entry_metadata_through_runtime(monkeypatch):
    orchestrator = TradingOrchestrator.__new__(TradingOrchestrator)
    orchestrator._futures_tick_size = 0.25
    signal = SimpleNamespace(price=100.0)
    calls = []

    def fake_finalize(**kwargs):
        calls.append(kwargs)
        return {"ok": True}

    monkeypatch.setattr(
        "services.trading.execution_runtime.finalize_entry_execution_metadata",
        fake_finalize,
    )

    result = orchestrator._finalize_entry_execution_meta(
        signal=signal,
        fill_price=101.0,
        is_short=True,
        execution_meta={"submit_price": 100.5},
    )

    assert result == {"ok": True}
    assert calls[0]["signal"] is signal
    assert calls[0]["fill_price"] == 101.0
    assert calls[0]["is_short"] is True
    assert calls[0]["tick_size"] == 0.25
```

- [ ] **Step 5: Verify**

Run:

```bash
pytest tests/unit/trading/test_execution_runtime.py tests/unit/trading/test_orchestrator_execution_delegation.py -q --tb=short
ruff check services/trading/execution_runtime.py services/trading/orchestrator.py tests/unit/trading/test_execution_runtime.py tests/unit/trading/test_orchestrator_execution_delegation.py
black --check services/trading/execution_runtime.py services/trading/orchestrator.py tests/unit/trading/test_execution_runtime.py tests/unit/trading/test_orchestrator_execution_delegation.py
python3 -m py_compile services/trading/execution_runtime.py services/trading/orchestrator.py tests/unit/trading/test_execution_runtime.py tests/unit/trading/test_orchestrator_execution_delegation.py
git diff --check
```

- [ ] **Step 6: Commit**

```bash
git add services/trading/execution_runtime.py services/trading/orchestrator.py tests/unit/trading/test_execution_runtime.py tests/unit/trading/test_orchestrator_execution_delegation.py
git commit -m "Refactor orchestrator execution metadata delegation"
```

### Task 1.2: Initialization Dependency Wiring Owner

Status: complete. `services/trading/initialization_runtime.py` exists, is
registered as a lazy `services.trading` package attribute, and is covered by
`tests/unit/trading/test_initialization_runtime.py` plus package import-laziness
tests. The orchestrator delegates futures contract-validation checks through
`should_require_futures_contract_validation()`.

**Do not redo this as a first-time extraction.** Future work may extend this
owner only for pure initialization decisions. Keep broker construction, notifier
setup, Redis connections, live-order wiring, and startup side effects in their
current owners unless a focused test proves the behavior boundary.

Verification anchor:

```bash
pytest tests/unit/trading/test_initialization_runtime.py tests/unit/trading/test_package_imports.py -q --tb=short
ruff check services/trading/initialization_runtime.py services/trading/__init__.py services/trading/orchestrator.py tests/unit/trading/test_initialization_runtime.py tests/unit/trading/test_package_imports.py
black --check services/trading/initialization_runtime.py services/trading/__init__.py services/trading/orchestrator.py tests/unit/trading/test_initialization_runtime.py tests/unit/trading/test_package_imports.py
python3 -m py_compile services/trading/initialization_runtime.py services/trading/__init__.py services/trading/orchestrator.py tests/unit/trading/test_initialization_runtime.py tests/unit/trading/test_package_imports.py
git diff --check
```

### Task 1.3: Kill-Switch Runtime Boundary

Status: complete for request parsing. `services/trading/kill_switch_runtime.py`
owns `KillSwitchRequest` and `parse_force_flatten_request()`, including string
and bytes payload handling. `services/trading/orchestrator.py` still owns stream
polling/ACK state, sentinel lifecycle, notification, flatten side effects, and
live-guard behavior.

**Do not move side effects in the next small slice.** If this lane continues,
keep Redis stream ACK/pending behavior, Telegram messages, kill-switch sentinel
deletion, and flatten order submission in the orchestrator until each side
effect has a named characterization test.

Verification anchor:

```bash
pytest tests/unit/trading/test_kill_switch_runtime.py tests/unit/trading/test_kill_switch_consumer.py tests/unit/trading/test_orchestrator_live_guard.py -q --tb=short
ruff check services/trading/kill_switch_runtime.py services/trading/orchestrator.py tests/unit/trading/test_kill_switch_runtime.py tests/unit/trading/test_kill_switch_consumer.py tests/unit/trading/test_orchestrator_live_guard.py
black --check services/trading/kill_switch_runtime.py services/trading/orchestrator.py tests/unit/trading/test_kill_switch_runtime.py tests/unit/trading/test_kill_switch_consumer.py tests/unit/trading/test_orchestrator_live_guard.py
python3 -m py_compile services/trading/kill_switch_runtime.py services/trading/orchestrator.py tests/unit/trading/test_kill_switch_runtime.py tests/unit/trading/test_kill_switch_consumer.py tests/unit/trading/test_orchestrator_live_guard.py
git diff --check
```

---

## Priority 2: Independent Large Surface Splits

These can run in parallel with Priority 1 because they do not need to edit the
same files.

### Task 2.1: Dashboard Trades Route Query/Response Split

Status: partially complete. `services/dashboard/routes/trades_lifecycle.py`
now owns lifecycle response assembly, while lifecycle row helpers and
SQL/Redis loading live in `services/dashboard/routes/trades_lifecycle_data.py`.
`services/dashboard/routes/trades.py` remains the route facade, and
`services/dashboard/routes/trades_data.py` owns general trade query/stat helpers.

**Files:**

- Done: `services/dashboard/routes/trades_lifecycle_data.py`
- Existing: `services/dashboard/routes/trades_lifecycle.py`
- Existing: `services/dashboard/routes/trades_data.py`
- Modify: `services/dashboard/routes/trades.py`
- Test: `tests/unit/dashboard/test_trades.py`

- [x] **Step 1: Keep lifecycle step builders in a route-adjacent module**

`trades_lifecycle.py` owns `_missing_lifecycle_step`, `_signal_step`,
`_order_step`, `_fill_step`, `_position_step`, `_closed_trade_step`, and
`_build_lifecycle_response`.

- [x] **Step 2: Move lifecycle row loading/data helpers**

`trades_lifecycle_data.py` owns `_query_lifecycle_table`,
`_query_lifecycle_batch`, `_load_lifecycle_ledger_rows`,
`_load_lifecycle_redis_rows`, and row-shape helpers. SQL strings, Redis key
lookups, broad/direct-id behavior, and ledger ownership semantics are unchanged.

- [ ] **Step 3: Optional remaining trade-query split**

Only if `trades_data.py` grows again, split general trade list/stat query helpers
into `trades_queries.py`. Do not move lifecycle builders in that same commit.

- [x] **Step 4: Verify route behavior**

```bash
pytest tests/unit/dashboard/test_trades.py -q --tb=short
ruff check services/dashboard/routes/trades.py services/dashboard/routes/trades_data.py services/dashboard/routes/trades_lifecycle.py services/dashboard/routes/trades_lifecycle_data.py tests/unit/dashboard/test_trades.py tests/unit/dashboard/test_signals_trace.py
black --check services/dashboard/routes/trades.py services/dashboard/routes/trades_data.py services/dashboard/routes/trades_lifecycle.py services/dashboard/routes/trades_lifecycle_data.py tests/unit/dashboard/test_trades.py tests/unit/dashboard/test_signals_trace.py
python3 -m py_compile services/dashboard/routes/trades.py services/dashboard/routes/trades_data.py services/dashboard/routes/trades_lifecycle.py services/dashboard/routes/trades_lifecycle_data.py tests/unit/dashboard/test_trades.py tests/unit/dashboard/test_signals_trace.py
git diff --check
```

- [x] **Step 5: Include in combined branch commit**

This slice is included in the combined runtime-decomposition branch commit for
this run rather than a standalone task commit.

### Task 2.2: CLI Command Module Split

Status: partially complete. The CLI now uses the existing `cli/commands/`
package pattern. Backfill, stock-backfill, trade, paper, health, and shared
dashboard URL defaults have moved out of `cli/main.py`. Backtest/experiment
commands remain in `cli/main.py` and are the next safe CLI slice.

**Files:**

- Existing: `cli/commands/backfill.py`
- Existing: `cli/commands/stock_backfill.py`
- Existing: `cli/commands/trading_control.py`
- Existing: `cli/commands/paper.py`
- Existing: `cli/commands/health.py`
- Existing: `cli/commands/common.py`
- Optional next: `cli/commands/backtest.py`
- Modify: `cli/main.py`
- Test: `tests/unit/test_cli_commands.py`

- [x] **Step 1: Keep CLI smoke coverage through existing tests**

`tests/unit/test_cli_commands.py::TestCLIHelp` plus `python -m cli.main
--help` verify the extracted top-level commands remain listed.

- [x] **Step 2: Extract one command group at a time**

Move only the `backfill` group and stock-backfill commands first into
`cli/commands/backfill.py` and `cli/commands/stock_backfill.py`. Export a group
named `backfill` and a group named `stock_backfill`.

- [x] **Step 3: Register extracted groups in `cli/main.py`**

In `cli/main.py`, keep the top-level `cli` group and register extracted groups:

```python
from cli.commands.backfill import backfill
from cli.commands.stock_backfill import stock_backfill

cli.add_command(backfill)
cli.add_command(stock_backfill)
```

- [x] **Step 4: Repeat for trade/paper/health only after tests pass**

Completed:

- `cli/commands/trading_control.py`: `trade`, orchestrator guard helpers;
- `cli/commands/paper.py`: `paper`;
- `cli/commands/health.py`: `health`;
- `cli/commands/common.py`: dashboard URL defaults.

- [ ] **Step 5: Optional remaining backtest/experiment split**

Move `backtest`, `experiment`, and helper `_run_tier_backtest` to
`cli/commands/backtest.py` only after adding focused compatibility tests for
`from cli.main import _run_tier_backtest`.

- [x] **Step 6: Verify**

```bash
pytest tests/unit/test_cli_commands.py tests/unit/test_cli_paper.py tests/unit/test_cli_stock_guard.py tests/unit/test_cli_futures_guard.py tests/unit/test_cli_portfolio.py -q
python -m cli.main --help
ruff check cli/main.py cli/commands tests/conftest.py
black --check cli/main.py cli/commands tests/conftest.py
python3 -m py_compile cli/main.py cli/commands/backfill.py cli/commands/stock_backfill.py cli/commands/trading_control.py cli/commands/paper.py cli/commands/health.py cli/commands/common.py
git diff --check
```

- [x] **Step 7: Include in combined branch commit**

This slice is included in the combined runtime-decomposition branch commit for
this run rather than a standalone task commit.

### Task 2.3: Orchestrator Universe And Market Data Runtime Helpers

**Files:**

- Create: `services/trading/universe_runtime.py`
- Create: `services/trading/market_data_runtime.py`
- Modify: `services/trading/orchestrator.py`
- Test: `tests/unit/trading/test_universe_runtime.py`
- Test: `tests/unit/trading/test_market_data_runtime.py`

- [ ] **Step 1: Extract pure symbol set operations**

Create `services/trading/universe_runtime.py`:

```python
"""Universe owner helpers for trading orchestrator compatibility runtime."""

from __future__ import annotations


def merge_symbol_sets(*groups: set[str] | list[str] | tuple[str, ...]) -> set[str]:
    merged: set[str] = set()
    for group in groups:
        merged.update(str(symbol) for symbol in group if str(symbol).strip())
    return merged


def stable_universe_delta(current: set[str], next_symbols: set[str]) -> tuple[set[str], set[str]]:
    return next_symbols - current, current - next_symbols
```

- [ ] **Step 2: Add tests**

Create `tests/unit/trading/test_universe_runtime.py`:

```python
from services.trading.universe_runtime import merge_symbol_sets, stable_universe_delta


def test_merge_symbol_sets_drops_empty_symbols():
    assert merge_symbol_sets({"A001", ""}, ["A002"], ("A001",)) == {"A001", "A002"}


def test_stable_universe_delta_returns_added_and_removed():
    added, removed = stable_universe_delta({"A001", "A002"}, {"A002", "A003"})

    assert added == {"A003"}
    assert removed == {"A001"}
```

- [ ] **Step 3: Extract market-data diagnostics helpers**

Create `services/trading/market_data_runtime.py`:

```python
"""Market-data owner helpers for trading orchestrator compatibility runtime."""

from __future__ import annotations

from statistics import median


def median_float(values: list[float]) -> float | None:
    if not values:
        return None
    return float(median(values))


def filter_market_data_by_symbols(
    market_data: dict[str, dict],
    symbols: set[str] | None,
) -> dict[str, dict]:
    if symbols is None:
        return market_data
    return {symbol: row for symbol, row in market_data.items() if symbol in symbols}
```

- [ ] **Step 4: Add tests**

Create `tests/unit/trading/test_market_data_runtime.py`:

```python
from services.trading.market_data_runtime import (
    filter_market_data_by_symbols,
    median_float,
)


def test_median_float_returns_none_for_empty_input():
    assert median_float([]) is None


def test_filter_market_data_by_symbols_keeps_only_requested_symbols():
    data = {"A001": {"price": 1}, "A002": {"price": 2}}

    assert filter_market_data_by_symbols(data, {"A002"}) == {"A002": {"price": 2}}
```

- [ ] **Step 5: Delegate only matching pure helpers**

Replace orchestrator-local implementations of `_median_float` and
`_filter_market_data_by_symbols` first. Defer loop extraction until these
helpers are stable.

- [ ] **Step 6: Verify**

```bash
pytest tests/unit/trading/test_universe_runtime.py tests/unit/trading/test_market_data_runtime.py -q --tb=short
ruff check services/trading/universe_runtime.py services/trading/market_data_runtime.py services/trading/orchestrator.py tests/unit/trading/test_universe_runtime.py tests/unit/trading/test_market_data_runtime.py
black --check services/trading/universe_runtime.py services/trading/market_data_runtime.py services/trading/orchestrator.py tests/unit/trading/test_universe_runtime.py tests/unit/trading/test_market_data_runtime.py
python3 -m py_compile services/trading/universe_runtime.py services/trading/market_data_runtime.py services/trading/orchestrator.py tests/unit/trading/test_universe_runtime.py tests/unit/trading/test_market_data_runtime.py
git diff --check
```

- [ ] **Step 7: Commit**

```bash
git add services/trading/universe_runtime.py services/trading/market_data_runtime.py services/trading/orchestrator.py tests/unit/trading/test_universe_runtime.py tests/unit/trading/test_market_data_runtime.py
git commit -m "Extract orchestrator universe and market-data helpers"
```

---

## Priority 3: Adapter And Test-Hygiene Backlog

### Task 3.1: KIS REST Client Request/Response Split

Status: partially complete. Analyst target-price summary/normalization logic now
lives in `shared/kis/target_price.py`; `KISClient` keeps compatibility wrappers
and owns auth/session/rate-limit behavior. The remaining safe slice is generic
quotation response parsing/mapping.

**Files:**

- Done: `shared/kis/target_price.py`
- Optional next: `shared/kis/response_parsing.py`
- Optional later: `shared/kis/request_runtime.py`
- Modify: `shared/kis/client.py`
- Test: `tests/unit/kis/test_target_price.py`

- [x] **Step 1: Move target-price normalization helpers only**

Move `_empty_target_price_summary`, `_normalize_target_price_report`,
`_calc_target_revision_pct`, `_target_revision_direction`, and the row summary
workflow into `shared/kis/target_price.py`. Do not move auth/session/rate-limit
calls.

- [x] **Step 2: Keep compatibility wrappers**

`KISClient.summarize_target_price()` fetches rows and delegates to
`summarize_target_price_rows()`. Private static/class methods remain as wrappers
for downstream tests/imports.

- [ ] **Step 3: Optional remaining response parser split**

Use existing fixtures in `tests/unit/kis/test_client.py`; add focused tests for
the moved parser functions so they can run without network credentials. Keep
`_quotations_get()` in `KISClient` until request/session behavior has separate
coverage.

- [x] **Step 4: Verify**

```bash
pytest tests/unit/kis/test_target_price.py -q
ruff check shared/kis/client.py shared/kis/target_price.py tests/unit/kis/test_target_price.py
black --check shared/kis/client.py shared/kis/target_price.py tests/unit/kis/test_target_price.py
python3 -m py_compile shared/kis/client.py shared/kis/target_price.py
git diff --check
```

- [x] **Step 5: Include in combined branch commit**

This slice is included in the combined runtime-decomposition branch commit for
this run rather than a standalone task commit.

### Task 3.2: Historical Backfill Planner/Sink Split

Status: partially complete. KIS futures/index OHLCV parsing now lives in
`shared/collector/historical/ohlcv_parser.py`, while
`shared.collector.historical.backfill.parse_ohlcv` remains the compatibility
import path used by parquet backfill monkeypatch tests. Planning/sink extraction
is still open.

**Files:**

- Done: `shared/collector/historical/ohlcv_parser.py`
- Optional next: `shared/collector/historical/backfill_plan.py`
- Optional next: `shared/collector/historical/backfill_sink.py`
- Modify: `shared/collector/historical/backfill.py`
- Test: `tests/unit/collector/test_parse_ohlcv_divergent_dedup.py`
- Test: `tests/unit/collector/test_parse_ohlcv_phantom_drop.py`
- Test: `tests/unit/collector/test_parquet_backfill.py`

- [x] **Step 1: Extract OHLCV parser first**

Move `_first_present`, `_resolve_minute_bars`, `_DIVERGENCE_MAX_STEP_FRACTION`,
and `parse_ohlcv` into `ohlcv_parser.py`. Keep the legacy import path in
`backfill.py` so tests and dynamic imports can monkeypatch it.

- [ ] **Step 2: Extract date/chunk planning**

Move pure date range, chunk, and resume planning helpers into
`backfill_plan.py`. Keep network fetch and file writes in the existing module.

- [ ] **Step 3: Extract sink write adapter**

Move sink dispatch and output-path resolution into `backfill_sink.py`. Preserve
existing CLI options and output paths.

- [x] **Step 4: Verify parser extraction**

```bash
pytest tests/unit/collector/test_parse_ohlcv_divergent_dedup.py tests/unit/collector/test_parse_ohlcv_phantom_drop.py tests/unit/collector/test_parquet_backfill.py -q
ruff check shared/collector/historical/backfill.py shared/collector/historical/ohlcv_parser.py tests/unit/collector/test_parse_ohlcv_divergent_dedup.py tests/unit/collector/test_parse_ohlcv_phantom_drop.py tests/unit/collector/test_parquet_backfill.py
black --check shared/collector/historical/backfill.py shared/collector/historical/ohlcv_parser.py tests/unit/collector/test_parse_ohlcv_divergent_dedup.py tests/unit/collector/test_parse_ohlcv_phantom_drop.py tests/unit/collector/test_parquet_backfill.py
python3 -m py_compile shared/collector/historical/backfill.py shared/collector/historical/ohlcv_parser.py
git diff --check
```

- [x] **Step 5: Include in combined branch commit**

This slice is included in the combined runtime-decomposition branch commit for
this run rather than a standalone task commit.

### Task 3.3: Large Test File Decomposition

**Files:**

- Split: `tests/integration/test_orchestrator_lifecycle.py`
- Split: `tests/unit/strategy/test_setup_adapters.py`
- Split: `tests/unit/trading/test_orchestrator.py`

- [ ] **Step 1: Split by behavior, not line count**

Use these target files:

- `tests/integration/test_orchestrator_lifecycle_start_stop.py`
- `tests/integration/test_orchestrator_lifecycle_recovery.py`
- `tests/integration/test_orchestrator_lifecycle_execution.py`
- `tests/unit/strategy/entry/test_setup_adapter_generation.py`
- `tests/unit/strategy/entry/test_setup_adapter_llm_gate.py`
- `tests/unit/trading/test_orchestrator_entry_flow.py`
- `tests/unit/trading/test_orchestrator_exit_flow.py`

- [ ] **Step 2: Move tests without changing assertions**

Only move test functions and shared fixtures. Do not rewrite behavior assertions
in the same commit.

- [ ] **Step 3: Verify moved tests**

```bash
pytest \
  tests/integration/test_orchestrator_lifecycle_start_stop.py \
  tests/integration/test_orchestrator_lifecycle_recovery.py \
  tests/integration/test_orchestrator_lifecycle_execution.py \
  tests/unit/strategy/entry/test_setup_adapter_generation.py \
  tests/unit/strategy/entry/test_setup_adapter_llm_gate.py \
  tests/unit/trading/test_orchestrator_entry_flow.py \
  tests/unit/trading/test_orchestrator_exit_flow.py \
  -q --tb=short
ruff check tests/integration/test_orchestrator_lifecycle_start_stop.py tests/integration/test_orchestrator_lifecycle_recovery.py tests/integration/test_orchestrator_lifecycle_execution.py tests/unit/strategy/entry/test_setup_adapter_generation.py tests/unit/strategy/entry/test_setup_adapter_llm_gate.py tests/unit/trading/test_orchestrator_entry_flow.py tests/unit/trading/test_orchestrator_exit_flow.py
black --check tests/integration/test_orchestrator_lifecycle_start_stop.py tests/integration/test_orchestrator_lifecycle_recovery.py tests/integration/test_orchestrator_lifecycle_execution.py tests/unit/strategy/entry/test_setup_adapter_generation.py tests/unit/strategy/entry/test_setup_adapter_llm_gate.py tests/unit/trading/test_orchestrator_entry_flow.py tests/unit/trading/test_orchestrator_exit_flow.py
python3 -m py_compile tests/integration/test_orchestrator_lifecycle_start_stop.py tests/integration/test_orchestrator_lifecycle_recovery.py tests/integration/test_orchestrator_lifecycle_execution.py tests/unit/strategy/entry/test_setup_adapter_generation.py tests/unit/strategy/entry/test_setup_adapter_llm_gate.py tests/unit/trading/test_orchestrator_entry_flow.py tests/unit/trading/test_orchestrator_exit_flow.py
git diff --check
```

- [ ] **Step 4: Commit**

```bash
git add tests/integration tests/unit/strategy tests/unit/trading
git commit -m "Split large orchestrator and setup adapter tests"
```

---

## Parallel Execution Map

Safe parallel lanes:

| Lane | Branch | Primary files | Conflict risk |
|---|---|---|---|
| P1-A execution lifecycle | `refactor/orchestrator-execution-runtime` | `services/trading/orchestrator.py`, `services/trading/execution_runtime.py` | Conflicts with other orchestrator edits |
| P2-C universe helpers | `refactor/orchestrator-universe-runtime` | `services/trading/orchestrator.py`, `services/trading/universe_runtime.py` | Conflicts with P1 |
| P3-A KIS client | `refactor/kis-client-response-split` | `shared/kis/*.py` | Low |
| P3-B backfill | `refactor/historical-backfill-split` | `shared/collector/historical/*.py` | Low |
| P2-B CLI backtest split | `refactor/cli-backtest-command-split` | `cli/main.py`, `cli/commands/backtest.py` | Low |
| P3-C tests | `refactor/large-test-split` | `tests/**` | Medium if code lanes add tests |

Recommended next wave:

1. Run exactly one orchestrator lane at a time. Start with P2-C
   universe/market-data helpers because it only moves pure set/filter/median
   helpers and leaves loops/side effects in place.
2. In parallel with that, run P3-A KIS response parsing and P3-B backfill
   planning/sink splits because they do not edit orchestrator files.
3. Run the CLI backtest split after adding compatibility tests for
   `from cli.main import _run_tier_backtest`.
4. Run P3-C after code movement stabilizes so test-file moves do not collide
   with newly added regression tests.

## Merge Gate

A lane is merge-ready only when:

- focused tests pass;
- ruff/black/py_compile/diff-check pass for touched files;
- `git diff --stat` shows behavior moved to owner modules without deleting
  compatibility imports/methods;
- no F-9, live-mode, stock swing, futures direction, Redis TTL, or stream ACK
  policy changed without a named test;
- docs that mention file ownership are updated in the same branch.
