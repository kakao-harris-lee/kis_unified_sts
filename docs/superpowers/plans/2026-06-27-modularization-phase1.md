# Modularization Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create small, stable module boundaries that let instruments, dashboard API, frontend builder, and CLI specialists work independently.

**Architecture:** This phase avoids behavior changes. It extracts pure helpers and thin command/contract modules behind existing public imports, then updates call sites to use the new owner modules. Each task has a disjoint write set so workers can run in parallel.

**Tech Stack:** Python 3, pytest, ruff, black, mypy for touched shared modules, TypeScript/Vitest for `strategy-builder-ui`.

---

## File Structure

- Create `shared/instruments/futures.py`
  - Neutral futures contract calendar/code module. Execution should not depend on historical collector internals.
- Modify `shared/execution/futures_instrument.py`
  - Import front-month resolution from `shared.instruments.futures`.
- Modify `shared/collector/historical/futures.py`
  - Re-export neutral instrument functions to preserve existing collector imports.
- Modify `tests/unit/collector/test_futures_codes.py`
  - Keep existing compatibility tests.
- Create `tests/unit/instruments/test_futures.py`
  - New owner tests for neutral futures instrument code.
- Create `services/dashboard/domain/assets.py`
  - Shared dashboard asset selector validation helpers.
- Modify dashboard route modules that currently import private helpers from `services.dashboard.routes.trading`.
- Create or extend `tests/unit/dashboard/routes/test_asset_class_param.py`.
- Create `strategy-builder-ui/src/lib/builder/autoConditions.ts`
  - Pure auto-condition generation.
- Modify `strategy-builder-ui/src/lib/builder/reducer.ts`
  - Keep reducer as state dispatcher.
- Create `strategy-builder-ui/src/lib/builder/autoConditions.test.ts`.
- Modify `strategy-builder-ui/src/lib/builder/reducer.test.ts` only if expectations need to move.
- Create `cli/commands/data.py`
  - Data command group and `validate-parquet` command.
- Modify `cli/main.py`
  - Register `data_cmd` from the command module.
- Modify `tests/unit/test_cli_commands.py` only if import expectations need a new module-level assertion.

Workers must not edit outside their ownership unless the controller explicitly reassigns scope. The controller owns final integration, verification, commit, and push.

---

### Task 1: Neutral Futures Instruments Module

**Owner:** Instruments worker.

**Files:**
- Create: `shared/instruments/__init__.py`
- Create: `shared/instruments/futures.py`
- Create: `tests/unit/instruments/test_futures.py`
- Modify: `shared/execution/futures_instrument.py`
- Modify: `shared/collector/historical/futures.py`
- Modify: `tests/unit/collector/test_futures_codes.py` only if import ownership is updated.

- [ ] **Step 1: Write failing owner tests**

Create `tests/unit/instruments/test_futures.py`:

```python
"""Tests for neutral futures instrument contract-code helpers."""

from datetime import date

from shared.instruments.futures import get_expiry_date, get_front_month_code


def test_mini_front_month_uses_legacy_a05_prefix():
    code = get_front_month_code(product="mini", target_date=date(2026, 3, 1))
    assert code == "A05603"


def test_kospi200_rolls_after_expiry():
    expiry = get_expiry_date(2026, 3)
    day_after = date(expiry.year, expiry.month, expiry.day + 1)
    assert get_front_month_code(product="kospi200", target_date=day_after) == "A01606"
```

- [ ] **Step 2: Verify RED**

Run:

```bash
pytest tests/unit/instruments/test_futures.py -q
```

Expected: fail because `shared.instruments.futures` does not exist.

- [ ] **Step 3: Create neutral module and compatibility exports**

Move the futures contract-code helpers from `shared/collector/historical/futures.py` into `shared/instruments/futures.py` or, if a full move is too large for this phase, copy the contract-calendar functions exactly and turn collector imports into compatibility re-exports. Preserve these function names:

```python
get_expiry_date
make_code
make_code_legacy
get_front_month_code
```

Then update `shared/execution/futures_instrument.py`:

```python
from shared.instruments.futures import get_front_month_code
```

Do not change runtime behavior or default product semantics.

- [ ] **Step 4: Verify instruments and compatibility tests**

Run:

```bash
pytest tests/unit/instruments/test_futures.py tests/unit/collector/test_futures_codes.py tests/unit/execution/test_futures_instrument_config.py -q
```

Expected: all pass.

- [ ] **Step 5: Lint/type touched Python files**

Run:

```bash
ruff check shared/instruments shared/execution/futures_instrument.py shared/collector/historical/futures.py tests/unit/instruments/test_futures.py tests/unit/collector/test_futures_codes.py tests/unit/execution/test_futures_instrument_config.py
black --check shared/instruments shared/execution/futures_instrument.py shared/collector/historical/futures.py tests/unit/instruments/test_futures.py tests/unit/collector/test_futures_codes.py tests/unit/execution/test_futures_instrument_config.py
.venv/bin/mypy shared/instruments/futures.py shared/execution/futures_instrument.py --ignore-missing-imports --no-error-summary
```

---

### Task 2: Dashboard Asset Domain Helpers

**Owner:** Dashboard API worker.

**Files:**
- Create: `services/dashboard/domain/__init__.py`
- Create: `services/dashboard/domain/assets.py`
- Modify: `services/dashboard/routes/trading.py`
- Modify: `services/dashboard/routes/trades.py`
- Modify: `services/dashboard/routes/signals.py`
- Modify: `services/dashboard/routes/coverage.py`
- Modify: `services/dashboard/routes/event_context.py`
- Modify: `services/dashboard/routes/health.py`
- Modify: `tests/unit/dashboard/routes/test_asset_class_param.py`

- [ ] **Step 1: Write failing helper-level tests**

Extend `tests/unit/dashboard/routes/test_asset_class_param.py` with direct helper tests:

```python
from fastapi import HTTPException

from services.dashboard.domain.assets import normalize_asset_class, target_assets


def test_asset_helper_defaults_to_futures():
    assert normalize_asset_class(None) == "futures"


def test_asset_helper_expands_all():
    assert target_assets("all") == ("futures", "stock")


def test_asset_helper_rejects_invalid_value():
    with pytest.raises(HTTPException):
        normalize_asset_class("options")
```

- [ ] **Step 2: Verify RED**

Run:

```bash
pytest tests/unit/dashboard/routes/test_asset_class_param.py -q
```

Expected: fail because `services.dashboard.domain.assets` does not exist.

- [ ] **Step 3: Extract helper module**

Create `services/dashboard/domain/assets.py` with the existing behavior from `routes/trading.py`:

```python
from fastapi import HTTPException

VALID_ASSET = {"stock", "futures", "all"}
ASSET_CLASSES = ("futures", "stock")


def normalize_asset_class(value: str | None) -> str:
    if value is None:
        return "futures"
    normalized = value.strip().lower()
    if normalized not in VALID_ASSET:
        raise HTTPException(
            status_code=400,
            detail="asset_class must be stock, futures, or all",
        )
    return normalized


def target_assets(asset_class: str) -> tuple[str, ...]:
    return ASSET_CLASSES if asset_class == "all" else (asset_class,)
```

In `services/dashboard/routes/trading.py`, keep private compatibility aliases so old imports do not break during the phase:

```python
from services.dashboard.domain.assets import (
    ASSET_CLASSES,
    VALID_ASSET,
    normalize_asset_class,
    target_assets,
)

_normalize_asset_class = normalize_asset_class
_target_assets = target_assets
```

Update other dashboard route modules to import public helpers from `services.dashboard.domain.assets`.

- [ ] **Step 4: Verify dashboard route behavior**

Run:

```bash
pytest tests/unit/dashboard/routes/test_asset_class_param.py tests/unit/dashboard/test_trades.py tests/unit/dashboard/test_event_context.py -q
```

Expected: all pass.

- [ ] **Step 5: Lint touched Python files**

Run:

```bash
ruff check services/dashboard/domain services/dashboard/routes/trading.py services/dashboard/routes/trades.py services/dashboard/routes/signals.py services/dashboard/routes/coverage.py services/dashboard/routes/event_context.py services/dashboard/routes/health.py tests/unit/dashboard/routes/test_asset_class_param.py
black --check services/dashboard/domain services/dashboard/routes/trading.py services/dashboard/routes/trades.py services/dashboard/routes/signals.py services/dashboard/routes/coverage.py services/dashboard/routes/event_context.py services/dashboard/routes/health.py tests/unit/dashboard/routes/test_asset_class_param.py
```

---

### Task 3: Frontend Builder Auto-Condition Module

**Owner:** Frontend builder worker.

**Files:**
- Create: `strategy-builder-ui/src/lib/builder/autoConditions.ts`
- Create: `strategy-builder-ui/src/lib/builder/autoConditions.test.ts`
- Modify: `strategy-builder-ui/src/lib/builder/reducer.ts`
- Modify: `strategy-builder-ui/src/lib/builder/reducer.test.ts` only if needed.

- [ ] **Step 1: Write failing pure-module tests**

Create `strategy-builder-ui/src/lib/builder/autoConditions.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import type { BuilderIndicator } from "@/types/builder";
import { generateAutoConditions } from "./autoConditions";

function indicator(
  id: string,
  indicatorId: string,
  alias: string,
  params: Record<string, number | string> = {}
): BuilderIndicator {
  return {
    id,
    indicatorId,
    alias,
    params,
    output: "value",
  };
}

describe("generateAutoConditions", () => {
  it("creates default RSI entry and exit thresholds", () => {
    const result = generateAutoConditions([
      indicator("rsi-instance", "rsi", "rsi_1", { period: 14 }),
    ]);

    expect(result.entry[0]).toMatchObject({
      left: { type: "indicator", indicatorAlias: "rsi_1", indicatorOutput: "value" },
      operator: "cross_above",
      right: { type: "value", value: 30 },
    });
    expect(result.exit[0]).toMatchObject({
      left: { type: "indicator", indicatorAlias: "rsi_1", indicatorOutput: "value" },
      operator: "cross_below",
      right: { type: "value", value: 70 },
    });
  });

  it("creates same-type moving-average crossover conditions", () => {
    const result = generateAutoConditions([
      indicator("sma-fast", "sma", "sma_fast", { period: 5 }),
      indicator("sma-slow", "sma", "sma_slow", { period: 20 }),
    ]);

    expect(result.entry).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          left: { type: "indicator", indicatorAlias: "sma_fast", indicatorOutput: "value" },
          operator: "cross_above",
          right: { type: "indicator", indicatorAlias: "sma_slow", indicatorOutput: "value" },
        }),
      ])
    );
    expect(result.exit).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          left: { type: "indicator", indicatorAlias: "sma_fast", indicatorOutput: "value" },
          operator: "cross_below",
          right: { type: "indicator", indicatorAlias: "sma_slow", indicatorOutput: "value" },
        }),
      ])
    );
  });
});
```

- [ ] **Step 2: Verify RED**

Run:

```bash
npm --prefix strategy-builder-ui test -- autoConditions
```

Expected: fail because `autoConditions.ts` does not exist.

- [ ] **Step 3: Extract `generateAutoConditions`**

Move `generateAutoConditions` and its indicator classification constants from `strategy-builder-ui/src/lib/builder/reducer.ts` into `strategy-builder-ui/src/lib/builder/autoConditions.ts`. Export it:

```typescript
export function generateAutoConditions(
  indicators: BuilderIndicator[]
): { entry: BuilderCondition[]; exit: BuilderCondition[] } {
  // existing implementation moved unchanged
}
```

Update `reducer.ts` to import:

```typescript
import { generateAutoConditions } from "@/lib/builder/autoConditions";
```

Do not change reducer behavior or action semantics.

- [ ] **Step 4: Verify frontend tests**

Run:

```bash
npm --prefix strategy-builder-ui test -- autoConditions reducer
```

Expected: new pure tests and existing reducer tests pass.

- [ ] **Step 5: Lint frontend touched files**

Run:

```bash
npm --prefix strategy-builder-ui run lint
```

Expected: no new errors. Pre-existing warnings are acceptable only if unchanged.

---

### Task 4: CLI Data Command Module

**Owner:** CLI worker.

**Files:**
- Create: `cli/commands/__init__.py`
- Create: `cli/commands/data.py`
- Modify: `cli/main.py`
- Modify: `tests/unit/test_cli_commands.py` only if needed.

- [ ] **Step 1: Write failing command-module import test**

Add to `tests/unit/test_cli_commands.py` near `TestDataCommands`:

```python
def test_data_command_group_is_importable_from_command_module():
    from cli.commands.data import data_cmd

    assert data_cmd.name == "data"
```

- [ ] **Step 2: Verify RED**

Run:

```bash
pytest tests/unit/test_cli_commands.py::TestDataCommands -q
```

Expected: fail because `cli.commands.data` does not exist.

- [ ] **Step 3: Extract data command group**

Create `cli/commands/data.py` and move these from `cli/main.py` unchanged:

```python
data_cmd
_resolve_parquet_export_root
data_validate_parquet
```

Required imports in the new module:

```python
from pathlib import Path
import sys

import click
```

In `cli/main.py`, import the command group:

```python
from cli.commands.data import data_cmd
```

Keep the command registered under the same `sts data validate-parquet` path.

- [ ] **Step 4: Verify CLI behavior**

Run:

```bash
pytest tests/unit/test_cli_commands.py::TestDataCommands -q
```

Expected: all data command tests pass.

- [ ] **Step 5: Lint touched CLI files**

Run:

```bash
ruff check cli/main.py cli/commands tests/unit/test_cli_commands.py
black --check cli/main.py cli/commands tests/unit/test_cli_commands.py
```

---

## Controller Integration

- [ ] **Step 1: Review worker summaries**

Confirm each worker reports:

```text
Status: DONE
Files changed: ...
Tests run: ...
Concerns: ...
```

- [ ] **Step 2: Check combined diff**

Run:

```bash
git status --short
git diff --stat
```

Expected: no unexpected files and no overlapping worker conflicts.

- [ ] **Step 3: Run combined verification**

Run:

```bash
pytest tests/unit/instruments/test_futures.py tests/unit/collector/test_futures_codes.py tests/unit/execution/test_futures_instrument_config.py tests/unit/dashboard/routes/test_asset_class_param.py tests/unit/dashboard/test_trades.py tests/unit/dashboard/test_event_context.py tests/unit/test_cli_commands.py::TestDataCommands -q
npm --prefix strategy-builder-ui test -- autoConditions reducer
ruff check .
black --check shared/instruments shared/execution/futures_instrument.py shared/collector/historical/futures.py services/dashboard/domain services/dashboard/routes/trading.py services/dashboard/routes/trades.py services/dashboard/routes/signals.py services/dashboard/routes/coverage.py services/dashboard/routes/event_context.py services/dashboard/routes/health.py cli/main.py cli/commands tests/unit/instruments/test_futures.py tests/unit/dashboard/routes/test_asset_class_param.py tests/unit/test_cli_commands.py
.venv/bin/mypy shared/instruments/futures.py shared/execution/futures_instrument.py --ignore-missing-imports --no-error-summary
```

- [ ] **Step 4: Commit and push**

Run:

```bash
git add docs/superpowers/plans/2026-06-27-modularization-phase1.md shared/instruments shared/execution/futures_instrument.py shared/collector/historical/futures.py tests/unit/instruments/test_futures.py services/dashboard/domain services/dashboard/routes/trading.py services/dashboard/routes/trades.py services/dashboard/routes/signals.py services/dashboard/routes/coverage.py services/dashboard/routes/event_context.py services/dashboard/routes/health.py tests/unit/dashboard/routes/test_asset_class_param.py strategy-builder-ui/src/lib/builder/autoConditions.ts strategy-builder-ui/src/lib/builder/autoConditions.test.ts strategy-builder-ui/src/lib/builder/reducer.ts strategy-builder-ui/src/lib/builder/reducer.test.ts cli/commands cli/main.py tests/unit/test_cli_commands.py
git commit -m "Extract first modularization boundaries"
git push origin modularization-phase1
```
