# Orchestrator Decomposition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split low-risk responsibilities out of `services/trading/orchestrator.py` while preserving the facade import surface and keeping F-9 as the futures runtime replacement path.

**Architecture:** Extract small owner modules behind compatibility re-exports. The orchestrator remains the public facade until tests and callers move. Runtime behavior, Redis stream contracts, stock swing exit policy, and futures long/short symmetry do not change.

**Tech Stack:** Python 3.11/3.12, pytest, ruff, black, py_compile, Redis Stream architecture via existing F-9 services.

---

## File Structure

- Create `services/trading/session_calendar.py`
  - Own sync holiday loading, sync `HolidayCache`, `TradingState`,
    `MarketSchedule`, and `is_trading_day`.
- Modify `services/trading/orchestrator.py`
  - Import those names from `session_calendar` and re-export them for existing
    imports.
- Create `tests/unit/trading/test_session_calendar.py`
  - Owner tests for the new module and facade compatibility tests.
- Modify `docs/superpowers/plans/INDEX.md`
  - Add this active implementation plan.
- Modify `docs/plans/2026-07-04-runtime-refactoring-roadmap.md`
  - Link this design/plan under Phase R3.

Later tasks in this plan should follow the same facade pattern for re-entry
guards, runtime config, recovery, and execution. Do not extract execution before
the session-calendar slice is green.

---

### Task 1: Extract Session Calendar Owner Module

Status: implemented in branch.

**Files:**
- Create: `services/trading/session_calendar.py`
- Create: `tests/unit/trading/test_session_calendar.py`
- Modify: `services/trading/orchestrator.py`

- [x] **Step 1: Write failing owner and compatibility tests**

Create `tests/unit/trading/test_session_calendar.py`:

```python
"""Session calendar extraction tests."""

from __future__ import annotations

from datetime import date, time

from services.trading import orchestrator
from services.trading.session_calendar import (
    HolidayCache,
    MarketSchedule,
    TradingState,
    is_trading_day,
)


def test_market_schedule_defaults_match_orchestrator_contract() -> None:
    schedule = MarketSchedule()

    assert schedule.get_open_time("stock") == time(9, 0)
    assert schedule.get_close_time("stock") == time(15, 30)
    assert schedule.get_open_time("futures") == time(8, 45)
    assert schedule.get_close_time("futures") == time(15, 45)


def test_is_trading_day_respects_weekends_and_explicit_holidays() -> None:
    assert is_trading_day(date(2026, 7, 6), holidays=set()) is True
    assert is_trading_day(date(2026, 7, 4), holidays=set()) is False
    assert (
        is_trading_day(
            date(2026, 7, 6),
            holidays={date(2026, 7, 6)},
        )
        is False
    )


def test_holiday_cache_invalidates_until_next_get_on_reload() -> None:
    calls = 0

    def loader(config_path: str) -> set[date]:
        nonlocal calls
        calls += 1
        assert config_path == "custom.yaml"
        return {date(2026, 1, 1)}

    cache = HolidayCache(loader=loader, config_path="custom.yaml")

    assert cache.get() == {date(2026, 1, 1)}
    assert cache.get() == {date(2026, 1, 1)}
    assert calls == 1

    cache.reload()

    assert calls == 1
    assert cache.get() == {date(2026, 1, 1)}
    assert calls == 2


def test_orchestrator_reexports_session_calendar_symbols() -> None:
    assert orchestrator.MarketSchedule is MarketSchedule
    assert orchestrator.HolidayCache is HolidayCache
    assert orchestrator.HolidayLoader is HolidayLoader
    assert orchestrator.TradingState is TradingState
    assert orchestrator.default_holiday_loader is default_holiday_loader
    assert orchestrator.is_trading_day is is_trading_day
    assert orchestrator.reload_holidays is reload_holidays
    assert orchestrator.set_holiday_cache is set_holiday_cache
```

- [x] **Step 2: Verify RED**

Run:

```bash
pytest tests/unit/trading/test_session_calendar.py -q
```

Expected: fail because `services.trading.session_calendar` does not exist.

- [x] **Step 3: Create owner module**

Move the existing sync calendar code from `services/trading/orchestrator.py` into
`services/trading/session_calendar.py`:

```python
"""Session calendar and legacy sync holiday helpers for TradingOrchestrator."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from datetime import time as dt_time
from enum import Enum
from pathlib import Path
from typing import Protocol

import yaml

logger = logging.getLogger(__name__)

MAX_YAML_FILE_SIZE = 1_024 * 1_024


class HolidayLoader(Protocol):
    def __call__(self, config_path: str) -> set[date]:
        ...


def default_holiday_loader(
    config_path: str = "config/market_schedule.yaml",
) -> set[date]:
    holidays: set[date] = set()
    path = Path(config_path)
    if not path.exists():
        logger.warning("Holiday config not found: %s, using empty set", config_path)
        return holidays
    try:
        file_size = path.stat().st_size
        if file_size > MAX_YAML_FILE_SIZE:
            logger.error(
                "Holiday config file too large: %s bytes > %s bytes",
                file_size,
                MAX_YAML_FILE_SIZE,
            )
            return holidays
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            logger.warning("Invalid holiday config format in %s", config_path)
            return holidays
        for holiday_str in data.get("holidays", []):
            try:
                if isinstance(holiday_str, str):
                    holidays.add(date.fromisoformat(holiday_str))
                elif isinstance(holiday_str, date):
                    holidays.add(holiday_str)
            except (ValueError, TypeError) as exc:
                logger.debug("Skipping invalid holiday entry: %s - %s", holiday_str, exc)
    except (OSError, yaml.YAMLError) as exc:
        logger.error("Failed to load holidays from config file: %s", exc, exc_info=True)
    except (KeyError, TypeError, AttributeError) as exc:
        logger.error("Invalid holiday config format: %s", exc, exc_info=True)
    return holidays
```

Also include the moved `HolidayCache`, `_get_holidays`, `reload_holidays`,
`set_holiday_cache`, `TradingState`, `MarketSchedule`, and `is_trading_day`
definitions unchanged except for module-local imports.

- [x] **Step 4: Re-export from orchestrator facade**

In `services/trading/orchestrator.py`, replace the moved definitions with imports:

```python
from services.trading.session_calendar import (
    HolidayCache,
    HolidayLoader,
    MarketSchedule,
    TradingState,
    default_holiday_loader,
    is_trading_day,
    reload_holidays,
    set_holiday_cache,
)
```

Keep all existing downstream references unchanged.

- [x] **Step 5: Verify GREEN**

Run:

```bash
pytest tests/unit/trading/test_session_calendar.py -q
pytest tests/unit/trading/test_orchestrator.py::TestIsTradingDay -q
pytest tests/unit/trading/test_orchestrator.py::TestMarketSchedule -q
pytest tests/unit/trading/test_orchestrator.py::TestHolidayCache -q
```

Expected: all pass.

- [x] **Step 6: Format and lint**

Run:

```bash
ruff check services/trading/session_calendar.py services/trading/orchestrator.py tests/unit/trading/test_session_calendar.py
black --check services/trading/session_calendar.py services/trading/orchestrator.py tests/unit/trading/test_session_calendar.py
python3 -m py_compile services/trading/session_calendar.py services/trading/orchestrator.py tests/unit/trading/test_session_calendar.py
```

Expected: all pass.

- [x] **Step 7: Stage**

Run:

```bash
git add services/trading/session_calendar.py services/trading/orchestrator.py tests/unit/trading/test_session_calendar.py
```

---

## Next Extraction Candidates

These are not executable tasks yet. Expand each into a full plan section before
implementation.

- `services/trading/reentry_guard.py`: pure cooldown key/record/block helpers
  are branch-implemented; `EntryReentryGuardConfig` lives in
  `services/trading/runtime_config.py`.
- `services/trading/execution_facade.py`: public owner helpers
  `normalize_entry_order_result` and `get_signal_direction` are
  branch-implemented from the underscored orchestrator compatibility methods;
  keep broker submission on `TradingOrchestrator` until a dedicated
  execution-service plan exists.
- `services/trading/recovery.py`: extract Redis/ledger recovery and broker
  reconciliation behind existing startup tests.
- `services/trading/runtime_config.py`: extract env parsing and `TradingConfig`
  after the smaller helpers have moved.

---

## Self-Review

- Spec coverage: This plan implements the first facade extraction and records
  the next extraction candidates.
- Placeholder scan: The executable Task 1 contains exact files, tests, commands,
  and expected results. Follow-up candidates are not checkbox tasks.
- Type consistency: `MarketSchedule`, `HolidayCache`, `TradingState`, and
  `is_trading_day` stay public through `services.trading.orchestrator`.
