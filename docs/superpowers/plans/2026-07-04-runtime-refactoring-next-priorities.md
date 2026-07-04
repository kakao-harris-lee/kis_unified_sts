# Runtime Refactoring Next Priorities Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the remaining high-value runtime refactoring targets after the 2026-07-04 decomposition merge, without changing trading behavior or bypassing the F-9 futures cutover path.

**Architecture:** Work in isolated branches/worktrees per priority lane. Keep compatibility facades in place, add characterization/delegation tests before moving behavior, and prefer owner modules that can be read without loading `services/trading/orchestrator.py`. The futures monolith remains a compatibility runtime until F-9 gates approve the event-driven chain.

**Tech Stack:** Python 3, pytest, ruff, black, Redis DB 1 runtime contracts, SQLite RuntimeLedger, Click CLI, FastAPI dashboard routes, Next.js Workbench.

---

## Current Baseline

Use `main` at or after `2140c9ed Merge runtime decomposition follow-ups`.

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
- package lazy imports in `services/trading/__init__.py`.

Current large-file scan on `main`:

| File | Lines | Priority |
|---|---:|---|
| `services/trading/orchestrator.py` | 7102 | P1 |
| `cli/main.py` | 2282 | P2 |
| `services/dashboard/routes/trades.py` | 1540 | P2 |
| `shared/kis/client.py` | 1373 | P3 |
| `shared/collector/historical/backfill.py` | 1295 | P3 |
| `services/dashboard/routes/kis_builder.py` | 1234 | P3 |
| `services/screener.py` | 1172 | P3 |
| `shared/kis/websocket.py` | 1074 | P3 |
| `services/dashboard/routes/signals.py` | 1033 | P3 |
| `shared/collector/historical/parquet_backfill.py` | 1030 | P3 |
| `services/dashboard/routes/health.py` | 1018 | P3 |

## Conflict Rules

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

**Files:**

- Create: `services/trading/initialization_runtime.py`
- Modify: `services/trading/orchestrator.py`
- Test: `tests/unit/trading/test_initialization_runtime.py`
- Test: `tests/unit/trading/test_package_imports.py`

- [ ] **Step 1: Add import-laziness test**

Append to `tests/unit/trading/test_package_imports.py`:

```python
def test_initialization_runtime_package_attribute_resolves_without_orchestrator() -> None:
    result = _run_python("""
        import sys
        import services.trading as trading

        assert trading.initialization_runtime is not None
        assert "services.trading.orchestrator" not in sys.modules
        """)

    assert result.returncode == 0, result.stderr
```

- [ ] **Step 2: Create owner module**

Create `services/trading/initialization_runtime.py` with pure helpers only:

```python
"""Initialization owner helpers for the trading orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExecutionLayerInputs:
    asset_class: str
    use_real_broker: bool
    futures_live_enabled: bool
    futures_tick_size: float


def execution_layer_mode(inputs: ExecutionLayerInputs) -> str:
    if inputs.asset_class == "futures" and inputs.futures_live_enabled:
        return "futures_live"
    if inputs.use_real_broker:
        return "real_broker"
    return "paper"


def should_require_futures_contract_validation(asset_class: str) -> bool:
    return asset_class == "futures"
```

- [ ] **Step 3: Add tests**

Create `tests/unit/trading/test_initialization_runtime.py`:

```python
from services.trading.initialization_runtime import (
    ExecutionLayerInputs,
    execution_layer_mode,
    should_require_futures_contract_validation,
)


def test_execution_layer_mode_prefers_futures_live_guard():
    mode = execution_layer_mode(
        ExecutionLayerInputs(
            asset_class="futures",
            use_real_broker=False,
            futures_live_enabled=True,
            futures_tick_size=0.05,
        )
    )

    assert mode == "futures_live"


def test_execution_layer_mode_keeps_paper_default():
    mode = execution_layer_mode(
        ExecutionLayerInputs(
            asset_class="stock",
            use_real_broker=False,
            futures_live_enabled=False,
            futures_tick_size=0.05,
        )
    )

    assert mode == "paper"


def test_futures_contract_validation_gate_is_asset_scoped():
    assert should_require_futures_contract_validation("futures") is True
    assert should_require_futures_contract_validation("stock") is False
```

- [ ] **Step 4: Register lazy submodule**

Add to `services/trading/__init__.py` `_SUBMODULES`:

```python
"initialization_runtime": "services.trading.initialization_runtime",
```

- [ ] **Step 5: Delegate one low-risk decision first**

Use the helpers from `_init_execution_layer` or contract validation guard only.
Do not move broker construction, notifier setup, Redis connections, or live
order wiring in the first commit.

- [ ] **Step 6: Verify**

```bash
pytest tests/unit/trading/test_initialization_runtime.py tests/unit/trading/test_package_imports.py -q --tb=short
ruff check services/trading/initialization_runtime.py services/trading/__init__.py services/trading/orchestrator.py tests/unit/trading/test_initialization_runtime.py tests/unit/trading/test_package_imports.py
black --check services/trading/initialization_runtime.py services/trading/__init__.py services/trading/orchestrator.py tests/unit/trading/test_initialization_runtime.py tests/unit/trading/test_package_imports.py
python3 -m py_compile services/trading/initialization_runtime.py services/trading/__init__.py services/trading/orchestrator.py tests/unit/trading/test_initialization_runtime.py tests/unit/trading/test_package_imports.py
git diff --check
```

- [ ] **Step 7: Commit**

```bash
git add services/trading/initialization_runtime.py services/trading/__init__.py services/trading/orchestrator.py tests/unit/trading/test_initialization_runtime.py tests/unit/trading/test_package_imports.py
git commit -m "Extract orchestrator initialization runtime decisions"
```

### Task 1.3: Kill-Switch Runtime Boundary

**Files:**

- Create: `services/trading/kill_switch_runtime.py`
- Modify: `services/trading/orchestrator.py`
- Test: `tests/unit/trading/test_kill_switch_runtime.py`
- Test: `tests/unit/trading/test_orchestrator_live_guard.py`

- [ ] **Step 1: Create pure payload parser tests**

Create `tests/unit/trading/test_kill_switch_runtime.py`:

```python
from services.trading.kill_switch_runtime import (
    KillSwitchRequest,
    parse_force_flatten_request,
)


def test_parse_force_flatten_request_defaults_reason():
    request = parse_force_flatten_request({"event_id": "1-0", "source": "unit"})

    assert request == KillSwitchRequest(
        event_id="1-0",
        source="unit",
        reason="force_flatten",
        dry_run=False,
    )


def test_parse_force_flatten_request_handles_string_dry_run():
    request = parse_force_flatten_request(
        {"event_id": "2-0", "source": "unit", "dry_run": "true"}
    )

    assert request.dry_run is True
```

- [ ] **Step 2: Implement owner module**

Create `services/trading/kill_switch_runtime.py`:

```python
"""Kill-switch owner helpers for trading orchestrator compatibility runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class KillSwitchRequest:
    event_id: str
    source: str
    reason: str
    dry_run: bool


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def parse_force_flatten_request(payload: dict[str, Any]) -> KillSwitchRequest:
    return KillSwitchRequest(
        event_id=str(payload.get("event_id") or ""),
        source=str(payload.get("source") or "unknown"),
        reason=str(payload.get("reason") or "force_flatten"),
        dry_run=_as_bool(payload.get("dry_run")),
    )
```

- [ ] **Step 3: Delegate parsing from orchestrator loop**

Use `parse_force_flatten_request()` where `_kill_switch_consumer_loop` currently
interprets payload fields. Keep stream ACK, pending, Telegram, and flatten side
effects in the orchestrator for this first commit.

- [ ] **Step 4: Verify no live-guard regression**

```bash
pytest tests/unit/trading/test_kill_switch_runtime.py tests/unit/trading/test_orchestrator_live_guard.py -q --tb=short
ruff check services/trading/kill_switch_runtime.py services/trading/orchestrator.py tests/unit/trading/test_kill_switch_runtime.py tests/unit/trading/test_orchestrator_live_guard.py
black --check services/trading/kill_switch_runtime.py services/trading/orchestrator.py tests/unit/trading/test_kill_switch_runtime.py tests/unit/trading/test_orchestrator_live_guard.py
python3 -m py_compile services/trading/kill_switch_runtime.py services/trading/orchestrator.py tests/unit/trading/test_kill_switch_runtime.py tests/unit/trading/test_orchestrator_live_guard.py
git diff --check
```

- [ ] **Step 5: Commit**

```bash
git add services/trading/kill_switch_runtime.py services/trading/orchestrator.py tests/unit/trading/test_kill_switch_runtime.py tests/unit/trading/test_orchestrator_live_guard.py
git commit -m "Extract kill-switch request parsing"
```

---

## Priority 2: Independent Large Surface Splits

These can run in parallel with Priority 1 because they do not need to edit the
same files.

### Task 2.1: Dashboard Trades Route Query/Response Split

**Files:**

- Create: `services/dashboard/routes/trades_queries.py`
- Create: `services/dashboard/routes/trades_lifecycle.py`
- Modify: `services/dashboard/routes/trades.py`
- Test: `tests/unit/dashboard/test_trades.py`

- [ ] **Step 1: Move pure ledger row conversion first**

Move these functions from `trades.py` into `trades_lifecycle.py`:

- `_parse_tz_aware`
- `_parse_optional_tz_aware`
- `_ledger_row_to_trade_dict`
- `_ledger_trade_to_closed_dict`
- `_ledger_fill_to_dict`
- `_statistics_from_trade_dicts`

Keep imports in `trades.py` so route functions remain unchanged.

- [ ] **Step 2: Move lifecycle step builders**

Move these functions into `trades_lifecycle.py`:

- `_missing_lifecycle_step`
- `_signal_step`
- `_order_step`
- `_fill_step`
- `_position_step`
- `_closed_trade_step`
- `_build_lifecycle_response`

Keep the existing response model imports stable.

- [ ] **Step 3: Move DB/ledger queries**

Move these functions into `trades_queries.py`:

- `_load_runtime_ledger_trades`
- `_load_runtime_ledger_fills`
- `_query_lifecycle_table`
- `_query_lifecycle_batch`
- `_load_lifecycle_ledger_rows`
- `_load_lifecycle_redis_rows`

Do not change SQL strings or Redis key names in the same commit.

- [ ] **Step 4: Verify route behavior**

```bash
pytest tests/unit/dashboard/test_trades.py -q --tb=short
ruff check services/dashboard/routes/trades.py services/dashboard/routes/trades_queries.py services/dashboard/routes/trades_lifecycle.py tests/unit/dashboard/test_trades.py
black --check services/dashboard/routes/trades.py services/dashboard/routes/trades_queries.py services/dashboard/routes/trades_lifecycle.py tests/unit/dashboard/test_trades.py
python3 -m py_compile services/dashboard/routes/trades.py services/dashboard/routes/trades_queries.py services/dashboard/routes/trades_lifecycle.py tests/unit/dashboard/test_trades.py
git diff --check
```

- [ ] **Step 5: Commit**

```bash
git add services/dashboard/routes/trades.py services/dashboard/routes/trades_queries.py services/dashboard/routes/trades_lifecycle.py tests/unit/dashboard/test_trades.py
git commit -m "Split dashboard trades lifecycle helpers"
```

### Task 2.2: CLI Command Module Split

**Files:**

- Create: `cli/backtest_commands.py`
- Create: `cli/backfill_commands.py`
- Create: `cli/trade_commands.py`
- Modify: `cli/main.py`
- Test: `tests/unit/cli/test_main_imports.py`

- [ ] **Step 1: Add import smoke test**

Create `tests/unit/cli/test_main_imports.py`:

```python
from click.testing import CliRunner

from cli.main import cli


def test_cli_lists_existing_top_level_commands():
    result = CliRunner().invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "backtest" in result.output
    assert "backfill" in result.output
    assert "trade" in result.output
    assert "paper" in result.output
```

- [ ] **Step 2: Extract one command group at a time**

Move only the `backfill` group and stock-backfill commands first into
`cli/backfill_commands.py`. Export a group named `backfill` and a group named
`stock_backfill`.

- [ ] **Step 3: Register extracted groups in `cli/main.py`**

In `cli/main.py`, keep the top-level `cli` group and register extracted groups:

```python
from cli.backfill_commands import backfill, stock_backfill

cli.add_command(backfill)
cli.add_command(stock_backfill, name="stock-backfill")
```

- [ ] **Step 4: Repeat for `backtest` and `trade` only after tests pass**

Use the same pattern for:

- `cli/backtest_commands.py`: `backtest`, `experiment`, helper `_run_tier_backtest`;
- `cli/trade_commands.py`: `trade`, `paper`, `health`, orchestrator guard helpers.

- [ ] **Step 5: Verify**

```bash
pytest tests/unit/cli/test_main_imports.py -q --tb=short
python -m cli.main --help >/tmp/sts-cli-help.txt
ruff check cli/main.py cli/backtest_commands.py cli/backfill_commands.py cli/trade_commands.py tests/unit/cli/test_main_imports.py
black --check cli/main.py cli/backtest_commands.py cli/backfill_commands.py cli/trade_commands.py tests/unit/cli/test_main_imports.py
python3 -m py_compile cli/main.py cli/backtest_commands.py cli/backfill_commands.py cli/trade_commands.py tests/unit/cli/test_main_imports.py
git diff --check
```

- [ ] **Step 6: Commit**

```bash
git add cli/main.py cli/backtest_commands.py cli/backfill_commands.py cli/trade_commands.py tests/unit/cli/test_main_imports.py
git commit -m "Split CLI command groups"
```

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

**Files:**

- Create: `shared/kis/request_runtime.py`
- Create: `shared/kis/response_parsing.py`
- Modify: `shared/kis/client.py`
- Test: `tests/unit/kis/test_client.py`

- [ ] **Step 1: Move response-normalization helpers only**

Move pure payload parsing and response normalization from `shared/kis/client.py`
into `shared/kis/response_parsing.py`. Do not move auth/session/rate-limit
calls in the first commit.

- [ ] **Step 2: Add tests around payload parsing**

Use existing fixtures in `tests/unit/kis/test_client.py`; add focused tests for
the moved parser functions so they can run without network credentials.

- [ ] **Step 3: Verify**

```bash
pytest tests/unit/kis/test_client.py -q --tb=short
ruff check shared/kis/client.py shared/kis/request_runtime.py shared/kis/response_parsing.py tests/unit/kis/test_client.py
black --check shared/kis/client.py shared/kis/request_runtime.py shared/kis/response_parsing.py tests/unit/kis/test_client.py
python3 -m py_compile shared/kis/client.py shared/kis/request_runtime.py shared/kis/response_parsing.py tests/unit/kis/test_client.py
git diff --check
```

- [ ] **Step 4: Commit**

```bash
git add shared/kis/client.py shared/kis/request_runtime.py shared/kis/response_parsing.py tests/unit/kis/test_client.py
git commit -m "Split KIS REST response parsing"
```

### Task 3.2: Historical Backfill Planner/Sink Split

**Files:**

- Create: `shared/collector/historical/backfill_plan.py`
- Create: `shared/collector/historical/backfill_sink.py`
- Modify: `shared/collector/historical/backfill.py`
- Test: `tests/unit/collector/test_backfill.py`

- [ ] **Step 1: Extract date/chunk planning**

Move pure date range, chunk, and resume planning helpers into
`backfill_plan.py`. Keep network fetch and file writes in the existing module.

- [ ] **Step 2: Extract sink write adapter**

Move sink dispatch and output-path resolution into `backfill_sink.py`. Preserve
existing CLI options and output paths.

- [ ] **Step 3: Verify**

```bash
pytest tests/unit/collector/test_backfill.py -q --tb=short
ruff check shared/collector/historical/backfill.py shared/collector/historical/backfill_plan.py shared/collector/historical/backfill_sink.py tests/unit/collector/test_backfill.py
black --check shared/collector/historical/backfill.py shared/collector/historical/backfill_plan.py shared/collector/historical/backfill_sink.py tests/unit/collector/test_backfill.py
python3 -m py_compile shared/collector/historical/backfill.py shared/collector/historical/backfill_plan.py shared/collector/historical/backfill_sink.py tests/unit/collector/test_backfill.py
git diff --check
```

- [ ] **Step 4: Commit**

```bash
git add shared/collector/historical/backfill.py shared/collector/historical/backfill_plan.py shared/collector/historical/backfill_sink.py tests/unit/collector/test_backfill.py
git commit -m "Split historical backfill planning and sinks"
```

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
| P1-B initialization | `refactor/orchestrator-initialization-runtime` | `services/trading/orchestrator.py`, `services/trading/initialization_runtime.py` | Conflicts with other orchestrator edits |
| P1-C kill switch | `refactor/orchestrator-kill-switch-runtime` | `services/trading/orchestrator.py`, `services/trading/kill_switch_runtime.py` | Conflicts with other orchestrator edits |
| P2-A trades route | `refactor/dashboard-trades-route-split` | `services/dashboard/routes/trades*.py` | Low |
| P2-B CLI split | `refactor/cli-command-split` | `cli/*.py` | Low |
| P2-C universe helpers | `refactor/orchestrator-universe-runtime` | `services/trading/orchestrator.py`, `services/trading/universe_runtime.py` | Conflicts with P1 |
| P3-A KIS client | `refactor/kis-client-response-split` | `shared/kis/*.py` | Low |
| P3-B backfill | `refactor/historical-backfill-split` | `shared/collector/historical/*.py` | Low |
| P3-C tests | `refactor/large-test-split` | `tests/**` | Medium if code lanes add tests |

Recommended first wave:

1. Run P2-A, P2-B, P3-A, and P3-B in parallel.
2. Run only one orchestrator lane at a time, or coordinate exact line ownership
   before dispatching multiple orchestrator workers.
3. Run P3-C after code movement stabilizes so test-file moves do not collide
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
