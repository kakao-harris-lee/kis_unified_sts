# Code Quality Cleanup Multi-Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Reduce high-maintenance code by extracting repeated strategy gate logic, splitting oversized frontend builder/trades modules, centralizing runtime defaults, and preparing bounded orchestrator decompositions.

**Architecture:** Execute in waves. Wave 1 creates shared foundations and low-conflict constants. Wave 2 applies those foundations to disjoint backend/frontend slices in parallel. Wave 3 handles larger orchestrator extractions one at a time because they touch shared runtime state.

**Tech Stack:** Python 3.11, pytest, ruff, FastAPI, Redis, TypeScript, React/Next.js, Vitest, ESLint.

---

## Coordination Rules

- Use one coordinator in the main workspace.
- Use one worker per task in isolated worktrees or subagent forks.
- Workers are not alone in the codebase. They must not revert unrelated edits and must report any files they changed.
- Workers may run tests, but only the coordinator decides final integration order.
- Parallel workers must have disjoint write sets. If a worker needs to touch a file outside its assignment, it must stop and report.
- Each worker final report must include changed files, commands run, failing commands if any, and residual risk.

## Execution Waves

| Wave | Parallel? | Tasks | Reason |
|---|---:|---|---|
| 0 | No | Baseline and branch hygiene | Prevent ambiguous failures. |
| 1 | Yes | Task 1, Task 4, Task 5, Task 7 | Disjoint backend helper, frontend constants, docs/runtime defaults, registry table. |
| 2 | Yes after Task 1 | Task 2, Task 3, Task 6 | Strategy files and frontend pages are independent once helpers exist. |
| 3 | Mostly sequential | Task 8, Task 9, Task 10 | Orchestrator and LLM config extractions have wider blast radius. |

## Baseline Commands

Run before dispatching workers:

```bash
git status --short
scripts/dev/check_no_dead_imports.sh
pytest tests/unit/strategy/test_setup_adapters.py tests/unit/dashboard/test_cors.py -q
npm --prefix strategy-builder-ui run lint
npm --prefix strategy-builder-ui test
git diff --check
```

Expected:
- `git status --short` is empty.
- Dead import check prints `OK: no dead imports detected`.
- pytest and npm test pass.
- ESLint exits 0.
- `git diff --check` exits 0.

## Task 1: Backend Strategy Entry Gate Foundation

**Priority:** P0

**Owner:** Backend strategy foundation worker.

**Write set:**
- Create: `shared/strategy/entry/gates.py`
- Create: `tests/unit/strategy/entry/test_entry_gates.py`
- Do not modify individual strategy files in this task.

**Purpose:** Extract repeated KST session-window and cooldown checks used by `generate()` methods so strategy-specific files can later become smaller without changing behavior.

- [x] **Step 1: Create tests for session gate behavior**

Add tests in `tests/unit/strategy/entry/test_entry_gates.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime

from shared.strategy.entry.gates import MarketSessionWindow, is_in_entry_session


def _utc(hour: int, minute: int) -> datetime:
    return datetime(2026, 6, 25, hour, minute, tzinfo=UTC)


def test_entry_session_allows_mid_session_kst_time() -> None:
    window = MarketSessionWindow(
        market_open_hour=9,
        market_open_minute=0,
        market_close_hour=15,
        market_close_minute=30,
        skip_market_open_minutes=5,
        skip_market_close_minutes=10,
    )

    assert is_in_entry_session(_utc(1, 0), window) is True


def test_entry_session_blocks_before_open_buffer() -> None:
    window = MarketSessionWindow(
        market_open_hour=9,
        market_open_minute=0,
        market_close_hour=15,
        market_close_minute=30,
        skip_market_open_minutes=5,
        skip_market_close_minutes=10,
    )

    assert is_in_entry_session(_utc(0, 2), window) is False


def test_entry_session_blocks_close_buffer() -> None:
    window = MarketSessionWindow(
        market_open_hour=9,
        market_open_minute=0,
        market_close_hour=15,
        market_close_minute=30,
        skip_market_open_minutes=5,
        skip_market_close_minutes=10,
    )

    assert is_in_entry_session(_utc(6, 25), window) is False
```

- [x] **Step 2: Run the new test and verify it fails**

Run:

```bash
pytest tests/unit/strategy/entry/test_entry_gates.py -q
```

Expected before implementation:
- Fails with `ModuleNotFoundError` or missing function.

- [x] **Step 3: Implement the session and cooldown helpers**

Create `shared/strategy/entry/gates.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from shared.utils.timezone import KST, to_kst


@dataclass(frozen=True)
class MarketSessionWindow:
    market_open_hour: int
    market_open_minute: int
    market_close_hour: int
    market_close_minute: int
    skip_market_open_minutes: int = 0
    skip_market_close_minutes: int = 0


def is_in_entry_session(timestamp: datetime, window: MarketSessionWindow) -> bool:
    now_kst = to_kst(timestamp)
    open_dt = datetime.combine(
        now_kst.date(),
        time(window.market_open_hour, window.market_open_minute),
        tzinfo=KST,
    )
    close_dt = datetime.combine(
        now_kst.date(),
        time(window.market_close_hour, window.market_close_minute),
        tzinfo=KST,
    )

    if now_kst < open_dt:
        return False

    if window.skip_market_open_minutes > 0:
        if now_kst < open_dt + timedelta(minutes=window.skip_market_open_minutes):
            return False

    if window.skip_market_close_minutes > 0:
        if now_kst >= close_dt - timedelta(minutes=window.skip_market_close_minutes):
            return False

    return True


def cooldown_elapsed(
    *,
    now: datetime,
    last_signal_at: datetime | None,
    cooldown_seconds: float,
) -> bool:
    if cooldown_seconds <= 0 or last_signal_at is None:
        return True
    return (now - last_signal_at).total_seconds() >= cooldown_seconds
```

- [x] **Step 4: Run focused tests**

Run:

```bash
pytest tests/unit/strategy/entry/test_entry_gates.py -q
```

Expected: all tests pass.

- [x] **Step 5: Run impact checks**

Run:

```bash
python3 -m py_compile shared/strategy/entry/gates.py
pytest tests/unit/strategy/test_setup_adapters.py -q
```

Expected: both pass.

## Task 2: Apply Strategy Gate Helper To Mean Reversion And Williams %R

**Priority:** P0

**Depends on:** Task 1 merged.

**Owner:** Backend strategy worker A.

**Write set:**
- Modify: `shared/strategy/entry/mean_reversion.py`
- Modify: `shared/strategy/entry/williams_r.py`
- Modify or create focused tests only under `tests/unit/strategy/entry/`

**Purpose:** Remove repeated time-window/cooldown code from two high-complexity strategies without changing signal behavior.

- [x] **Step 1: Add regression tests for helper-equivalent behavior**

Create tests that instantiate the real strategy with a normal config and verify:
- signal is blocked during open skip window.
- signal is blocked during close skip window.
- cooldown blocks a second signal for the same symbol.

Use existing strategy config defaults where possible. Do not assert exact confidence unless already covered elsewhere.

- [x] **Step 2: Replace local time-window checks**

In each strategy, import:

```python
from shared.strategy.entry.gates import MarketSessionWindow, cooldown_elapsed, is_in_entry_session
```

Build the window from strategy config:

```python
window = MarketSessionWindow(
    market_open_hour=self.config.market_open_hour,
    market_open_minute=self.config.market_open_minute,
    market_close_hour=self.config.market_close_hour,
    market_close_minute=self.config.market_close_minute,
    skip_market_open_minutes=self.config.skip_market_open_minutes,
    skip_market_close_minutes=self.config.skip_market_close_minutes,
)
if not is_in_entry_session(context.timestamp, window):
    return None
```

Replace cooldown blocks with:

```python
if not cooldown_elapsed(
    now=context.timestamp,
    last_signal_at=self._last_signal_at.get(code),
    cooldown_seconds=self.config.signal_cooldown_seconds,
):
    return None
```

- [x] **Step 3: Run focused tests**

Run:

```bash
pytest tests/unit/strategy/entry/test_entry_gates.py -q
pytest tests/unit/strategy/test_setup_adapters.py -q
python3 -m py_compile shared/strategy/entry/mean_reversion.py shared/strategy/entry/williams_r.py
```

Expected: all pass.

## Task 3: Apply Strategy Gate Helper To Momentum Breakout And Opening Volume Surge

**Priority:** P0

**Depends on:** Task 1 merged.

**Owner:** Backend strategy worker B.

**Write set:**
- Modify: `shared/strategy/entry/momentum_breakout.py`
- Modify: `shared/strategy/entry/opening_volume_surge.py`
- Modify or create focused tests only under `tests/unit/strategy/entry/`

**Purpose:** Reduce repeated gate code in two more complex entry strategies.

- [x] **Step 1: Add regression tests**

Cover:
- `momentum_breakout` respects open/close skip windows.
- `momentum_breakout` respects cooldown.
- `opening_volume_surge` respects open and entry cutoff behavior.

- [x] **Step 2: Use the shared session helper in `momentum_breakout.py`**

Use the same `MarketSessionWindow` pattern from Task 2.

- [x] **Step 3: Use the shared session helper in `opening_volume_surge.py` where compatible**

For `opening_volume_surge`, preserve `only_first_minutes` and `entry_cutoff_*` behavior. Only replace the common "before open" computation. Do not change score, spike-window, or volume-gate logic.

- [x] **Step 4: Run focused tests**

Run:

```bash
pytest tests/unit/strategy/entry/test_entry_gates.py -q
pytest tests/unit/strategy/test_setup_adapters.py -q
python3 -m py_compile shared/strategy/entry/momentum_breakout.py shared/strategy/entry/opening_volume_surge.py
```

Expected: all pass.

## Task 4: Convert Builtin Strategy Registration To Declarative Tables

**Priority:** P1

**Owner:** Backend registry worker.

**Write set:**
- Modify: `shared/strategy/registry.py`
- Create: `tests/unit/strategy/test_registry_builtin_components.py`

**Purpose:** Replace repeated import/register/except blocks with small registration tables.

- [x] **Step 1: Add tests for idempotent registration**

Create `tests/unit/strategy/test_registry_builtin_components.py`:

```python
from shared.strategy.registry import EntryRegistry, register_builtin_components


def test_register_builtin_components_registers_core_entries() -> None:
    register_builtin_components()

    assert EntryRegistry.get("mean_reversion") is not None
    assert EntryRegistry.get("momentum_breakout") is not None
    assert EntryRegistry.get("williams_r") is not None


def test_register_builtin_components_is_idempotent() -> None:
    register_builtin_components()
    first = EntryRegistry.get("mean_reversion")
    register_builtin_components()

    assert EntryRegistry.get("mean_reversion") is first
```

- [x] **Step 2: Run tests and verify current behavior**

Run:

```bash
pytest tests/unit/strategy/test_registry_builtin_components.py -q
```

Expected: pass before refactor.

- [x] **Step 3: Introduce table-driven registration**

Inside `shared/strategy/registry.py`, replace repeated blocks with:

```python
ENTRY_COMPONENTS = (
    ("stochrsi_trend", "shared.strategy.entry.stochrsi_trend", "StochRSITrendEntry"),
    ("mean_reversion", "shared.strategy.entry.mean_reversion", "MeanReversionEntry"),
    ("breakout", "shared.strategy.entry.breakout", "BreakoutEntry"),
)
```

Add a helper:

```python
def _register_class_from_path(registry, key: str, module_path: str, class_name: str) -> None:
    try:
        module = importlib.import_module(module_path)
    except ImportError:
        logger.debug("%s not available", class_name)
        return
    registry.register_class(key, getattr(module, class_name))
```

Then iterate entry, exit, and position-sizer tables. Include all currently registered components before deleting old blocks.

- [x] **Step 4: Run registry and strategy tests**

Run:

```bash
pytest tests/unit/strategy/test_registry_builtin_components.py tests/unit/strategy/test_setup_adapters.py -q
python3 -m py_compile shared/strategy/registry.py
```

Expected: all pass.

## Task 5: Centralize Runtime Defaults And Fix Runtime Guidance Drift

**Priority:** P1

**Owner:** Runtime defaults worker.

**Write set:**
- Create: `shared/config/runtime_defaults.py`
- Modify selected service entrypoints that use `os.environ.get("REDIS_URL", "redis://localhost:6379/1")`
- Modify: `CLAUDE.md`
- Test: `tests/unit/config/test_runtime_defaults.py`

**Purpose:** Keep Redis URL and dashboard host-port defaults in one code location and fix the remaining 5080 source-of-truth drift.

- [x] **Step 1: Add default tests**

Create `tests/unit/config/test_runtime_defaults.py`:

```python
from shared.config.runtime_defaults import (
    DEFAULT_DASHBOARD_HOST_PORT,
    DEFAULT_REDIS_URL,
    redis_url_from_env,
)


def test_runtime_default_redis_url_uses_db_1() -> None:
    assert DEFAULT_REDIS_URL == "redis://localhost:6379/1"


def test_runtime_default_dashboard_port_is_5081() -> None:
    assert DEFAULT_DASHBOARD_HOST_PORT == "5081"


def test_redis_url_from_env_prefers_override(monkeypatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://example:6379/1")
    assert redis_url_from_env() == "redis://example:6379/1"
```

- [x] **Step 2: Create runtime defaults module**

Create `shared/config/runtime_defaults.py`:

```python
from __future__ import annotations

import os

DEFAULT_REDIS_URL = "redis://localhost:6379/1"
DEFAULT_DASHBOARD_HOST_PORT = "5081"


def redis_url_from_env() -> str:
    return os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)


def dashboard_host_port_from_env() -> str:
    return os.environ.get("DASHBOARD_HOST_PORT", DEFAULT_DASHBOARD_HOST_PORT)
```

- [x] **Step 3: Replace repeated Redis default reads in runtime entrypoints**

Change only service entrypoints in this task. Example replacement:

```python
from shared.config.runtime_defaults import redis_url_from_env

redis_url = redis_url_from_env()
```

Prioritize:
- `services/futures_monitor/main.py`
- `services/decision_engine/main.py`
- `services/order_router/main.py`
- `services/stock_strategy/main.py`
- `services/stock_risk_filter/main.py`
- `services/stock_order_router/main.py`
- `services/stock_exit/main.py`
- `services/stock_monitor/main.py`
- `services/news_collector/main.py`
- `services/news_scorer/main.py`
- `services/market_ingest/main.py`
- `services/risk_filter/main.py`
- `services/kill_switch/main.py`

- [x] **Step 4: Fix `CLAUDE.md` port drift**

Replace:

```markdown
`DASHBOARD_HOST_PORT=5080`
```

with:

```markdown
`DASHBOARD_HOST_PORT=5081` for paper/local; Caddy still listens on container `:5080`.
```

- [x] **Step 5: Run tests**

Run:

```bash
pytest tests/unit/config/test_runtime_defaults.py -q
python3 -m py_compile shared/config/runtime_defaults.py services/futures_monitor/main.py services/decision_engine/main.py services/order_router/main.py
rg -n "redis://localhost:6379/1" services shared/config cli | cat
```

Expected:
- tests pass.
- py_compile passes.
- remaining Redis URL literals are either tests, docs, or non-runtime examples. Worker must list remaining matches in final report.

## Task 6: Split Strategy Builder State Logic From React Hook

**Priority:** P1

**Owner:** Frontend builder worker.

**Write set:**
- Modify: `strategy-builder-ui/src/hooks/useStrategyBuilder.ts`
- Create: `strategy-builder-ui/src/lib/builder/reducer.ts`
- Create: `strategy-builder-ui/src/lib/builder/yamlSerializer.ts`
- Create: `strategy-builder-ui/src/lib/builder/reducer.test.ts`
- Create: `strategy-builder-ui/src/lib/builder/yamlSerializer.test.ts`

**Purpose:** Reduce `useStrategyBuilder.ts` responsibility and make reducer/YAML conversion independently testable.

- [x] **Step 1: Move reducer without behavior changes**

Move `builderReducer` and `INITIAL_STATE` dependencies needed by the reducer into `src/lib/builder/reducer.ts`.

Export:

```ts
export { INITIAL_STATE, builderReducer };
```

Do not move React hook action wrappers in this step.

- [x] **Step 2: Add reducer tests**

Create `strategy-builder-ui/src/lib/builder/reducer.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { builderReducer, INITIAL_STATE } from "./reducer";

describe("builderReducer", () => {
  it("updates metadata without mutating existing state", () => {
    const next = builderReducer(INITIAL_STATE, {
      type: "SET_METADATA",
      payload: { name: "Test strategy" },
    });

    expect(next.metadata.name).toBe("Test strategy");
    expect(INITIAL_STATE.metadata.name).not.toBe("Test strategy");
  });
});
```

- [x] **Step 3: Move YAML conversion**

Create `src/lib/builder/yamlSerializer.ts` with:

```ts
export function toYamlStrategy(state: BuilderState): YamlStrategy {
  // Move the current toYaml useMemo body here.
}

export function toYamlString(strategy: YamlStrategy): string {
  // Move the current toYamlString useMemo serialization body here.
}
```

The hook should call these functions inside `useMemo`.

- [x] **Step 4: Add YAML serializer tests**

Create `strategy-builder-ui/src/lib/builder/yamlSerializer.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { INITIAL_STATE } from "./reducer";
import { toYamlStrategy, toYamlString } from "./yamlSerializer";

describe("yamlSerializer", () => {
  it("serializes base metadata and strategy id", () => {
    const yaml = toYamlStrategy(INITIAL_STATE);
    const text = toYamlString(yaml);

    expect(text).toContain("metadata:");
    expect(text).toContain("strategy:");
    expect(text).toContain(`id: ${yaml.strategy.id}`);
  });
});
```

- [x] **Step 5: Run frontend checks**

Run:

```bash
npm --prefix strategy-builder-ui test -- src/lib/builder/reducer.test.ts src/lib/builder/yamlSerializer.test.ts
npm --prefix strategy-builder-ui run lint
npm --prefix strategy-builder-ui test
```

Expected: all pass.

## Task 7: Centralize Frontend Polling Intervals

**Priority:** P1

**Owner:** Frontend runtime constants worker.

**Write set:**
- Create: `strategy-builder-ui/src/lib/dashboard/queryIntervals.ts`
- Modify pages/components with `refetchInterval` literals.

**Purpose:** Make dashboard refresh policy explicit and easy to tune.

- [x] **Step 1: Create constants**

Create `strategy-builder-ui/src/lib/dashboard/queryIntervals.ts`:

```ts
export const QUERY_INTERVALS_MS = {
  fast: 10_000,
  normal: 15_000,
  slow: 30_000,
  experiments: 60_000,
} as const;
```

- [x] **Step 2: Replace literals**

Replace:
- `10000` with `QUERY_INTERVALS_MS.fast`
- `15000` with `QUERY_INTERVALS_MS.normal`
- `30000` with `QUERY_INTERVALS_MS.slow`
- `60000` with `QUERY_INTERVALS_MS.experiments`

Prioritize files:
- `strategy-builder-ui/src/app/trades/page.tsx`
- `strategy-builder-ui/src/app/risk/page.tsx`
- `strategy-builder-ui/src/app/coverage/page.tsx`
- `strategy-builder-ui/src/app/event-context/page.tsx`
- `strategy-builder-ui/src/app/signals/page.tsx`
- `strategy-builder-ui/src/app/positions/page.tsx`
- `strategy-builder-ui/src/components/dashboard/*.tsx`

- [x] **Step 3: Run checks**

Run:

```bash
npm --prefix strategy-builder-ui run lint
npm --prefix strategy-builder-ui test
rg -n "refetchInterval: (10000|15000|30000|60000)" strategy-builder-ui/src
```

Expected:
- lint and tests pass.
- final `rg` has no matches, except if worker explicitly documents a justified exception.

## Task 8: Split Trades Page Into Tabs And Data Hooks

**Priority:** P2

**Owner:** Frontend trades worker.

**Write set:**
- Modify: `strategy-builder-ui/src/app/trades/page.tsx`
- Create directory: `strategy-builder-ui/src/app/trades/components/`
- Create: `strategy-builder-ui/src/app/trades/components/LiveTradesTab.tsx`
- Create: `strategy-builder-ui/src/app/trades/components/HistoryTradesTab.tsx`
- Create: `strategy-builder-ui/src/app/trades/components/TradesTabList.tsx`
- Create: `strategy-builder-ui/src/app/trades/hooks.ts`

**Purpose:** Reduce `trades/page.tsx` from a 1,000-line mixed data/render file to a shell plus focused tab components.

- [x] **Step 1: Move tab keyboard logic to `TradesTabList.tsx`**

Export:

```tsx
export type TradesTab = "live" | "history";

export function TradesTabList({
  activeTab,
  onChange,
}: {
  activeTab: TradesTab;
  onChange: (tab: TradesTab) => void;
}) {
  // Move current tablist markup and keyboard handler here.
}
```

- [x] **Step 2: Move `LiveTab` into `LiveTradesTab.tsx`**

Keep imports local to the new component. Do not change query keys or returned UI.

- [x] **Step 3: Move `HistoryTab` into `HistoryTradesTab.tsx`**

Keep imports local to the new component. Do not change lifecycle behavior.

- [x] **Step 4: Keep `page.tsx` as shell only**

`page.tsx` should only manage:
- `activeTab`
- `HeaderBar`
- `TradesTabList`
- active tab panel selection

- [x] **Step 5: Run focused checks**

Run:

```bash
npm --prefix strategy-builder-ui test -- src/app/quant-ops-workbench.smoke.test.tsx
npm --prefix strategy-builder-ui run lint
npm --prefix strategy-builder-ui test
```

Expected: all pass.

## Task 9: Extract Orchestrator Broker Verification

**Priority:** P2, run after strategy cleanup is merged.

**Owner:** Orchestrator worker A.

**Write set:**
- Modify: `services/trading/orchestrator.py`
- Create: `services/trading/broker_verification.py`
- Create: `tests/unit/services/test_broker_verification.py`

**Purpose:** Move `_verify_positions_with_broker` out of the 8k-line orchestrator and make broker/ledger comparison independently testable.

- [x] **Step 1: Create pure comparison tests**

Test cases:
- no Redis positions and no broker positions returns no action.
- futures paper mode skips verification.
- missing KIS client skips verification.
- mismatched positions produce a warning payload.

- [x] **Step 2: Create `BrokerPositionVerifier`**

Create `services/trading/broker_verification.py` with a `BrokerPositionVerifier`
class and move the body of `TradingOrchestrator._verify_positions_with_broker`
into `BrokerPositionVerifier.verify(...)`. Preserve the current skip order:
config disabled, missing KIS client, futures paper mode, futures mock server,
broker inquiry failure, and empty-on-both-sides short circuit. The verifier must
receive the current trading config, KIS client, and position tracker as keyword
arguments so the orchestrator keeps ownership of runtime dependencies.

- [x] **Step 3: Delegate from orchestrator**

In `TradingOrchestrator._verify_positions_with_broker`, delegate:

```python
await self._broker_position_verifier.verify(
    config=self.config,
    kis_client=self._kis_client,
    position_tracker=self._position_tracker,
)
```

- [x] **Step 4: Run backend checks**

Run:

```bash
pytest tests/unit/services/test_broker_verification.py tests/unit/services/test_order_router_main.py -q
python3 -m py_compile services/trading/orchestrator.py services/trading/broker_verification.py
```

Expected: all pass.

## Task 10: Split LLM YAML Config Loading Helpers

**Priority:** P3

**Owner:** LLM config worker.

**Write set:**
- Modify: `shared/llm/config.py`
- Create: `tests/unit/llm/test_config_yaml_loading.py` if not already present.

**Purpose:** Reduce `LLMConfig.from_yaml` from a 400-line method into named helper functions while preserving provider and legacy format support.

- [x] **Step 1: Add behavior tests around current `from_yaml`**

Tests must cover:
- absolute YAML path loading.
- legacy `stock_screening` fallback.
- env overrides when `apply_env_overrides=True`.

- [x] **Step 2: Extract helpers**

Create private helpers inside `shared/llm/config.py`:

```python
def _load_yaml_mapping(path: str | Path) -> dict:
    from shared.config.loader import ConfigLoader

    path_str = str(path)
    if os.path.isabs(path_str):
        import yaml as _yaml

        with open(path_str, encoding="utf-8") as fh:
            loaded = _yaml.safe_load(fh) or {}
    else:
        loaded = ConfigLoader.load(path_str)
    return loaded if isinstance(loaded, dict) else {}

def _section(data: dict, primary: str, fallback: str | None = None) -> dict:
    value = data.get(primary)
    if value is None and fallback is not None:
        value = data.get(fallback, {})
    return value if isinstance(value, dict) else {}
```

Then extract the existing `config_dict = {...}` literal from `from_yaml` into a
private `_build_config_dict(...) -> dict` helper. Move the current keys and
default values unchanged. `from_yaml` should only load data, derive sections,
apply env overrides, and return `cls(**config_dict)`.

- [x] **Step 3: Run checks**

Run:

```bash
pytest tests/unit/llm/test_config_yaml_loading.py -q
python3 -m py_compile shared/llm/config.py
```

Expected: all pass.

## Integration Gate

After each worker result, coordinator runs the focused test command from that task.

After each wave, coordinator runs:

```bash
scripts/dev/check_no_dead_imports.sh
pytest tests/unit/strategy/test_setup_adapters.py tests/unit/dashboard/test_cors.py -q
npm --prefix strategy-builder-ui run lint
npm --prefix strategy-builder-ui test
git diff --check
```

Before final merge, coordinator runs:

```bash
scripts/dev/check_no_dead_imports.sh
pytest tests/unit/strategy/test_setup_adapters.py tests/unit/dashboard/test_cors.py tests/unit/services/test_order_router_main.py -q
npm --prefix strategy-builder-ui run lint
npm --prefix strategy-builder-ui test
npm --prefix strategy-builder-ui run build
docker compose config --services
git diff --check
```

Expected:
- All commands exit 0.
- Next build may print the existing multiple-lockfile root warning; that warning is not a failure.

## Commit Strategy

- Commit after each task or wave, not after all work.
- Suggested commit messages:
  - `refactor: add shared strategy entry gates`
  - `refactor: simplify entry strategy session gates`
  - `refactor: table-drive strategy registry`
  - `refactor: centralize runtime defaults`
  - `refactor: split strategy builder state logic`
  - `refactor: centralize dashboard query intervals`
  - `refactor: split trades dashboard tabs`
  - `refactor: extract broker position verification`
  - `refactor: split llm config yaml loading`

## Rollback Guidance

- If Task 1 breaks strategy behavior, revert Tasks 1-3 together.
- If Task 6 breaks builder output, revert Task 6 only; it should not affect runtime APIs.
- If Task 8 breaks trades UI, revert Task 8 only.
- If Task 9 breaks runtime startup, revert Task 9 only.
- Do not revert unrelated cleanup commits unless explicitly instructed.
