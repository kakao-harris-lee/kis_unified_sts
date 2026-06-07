# Futures Chain Stream-Naming Coherence (F-1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the decoupled futures chain (decision_engine → risk_filter → order_router) mode-coherent and shadow-isolatable — stock-style stream base names with a `.shadow` suffix, per-daemon `_resolve_mode`/`_streams_for` helpers, and a non-live shadow risk-state — so a later increment can run an isolated futures shadow pipeline.

**Architecture:** Each futures daemon's module-level `_build_and_run()` derives its stream names from a per-mode helper (the daemon *classes* already take stream names as constructor args, so they are unchanged). Shadow pipeline = decision_engine `shadow` + risk_filter `shadow` + order_router `paper`, all on `.shadow` streams + `risk:state:futures:shadow`. Live pipeline = all unsuffixed. `off` = inert. `RuntimeRiskState` gains a backward-compatible `key_suffix` so the shadow chain reads an isolated risk-state key.

**Tech Stack:** Python 3.11+ asyncio, Redis streams (fakeredis in tests), pytest. Mirrors the stock M4 daemons (`services/stock_{strategy,risk_filter,order_router}/main.py`).

**Spec:** `docs/superpowers/specs/2026-06-07-futures-stream-naming-coherence-f1-design.md`

**Worktree:** Implement in `/tmp/f1-impl` (branch `feat/futures-stream-naming-coherence`). Run venv tools from `cd /tmp/f1-impl` using `/home/deploy/project/kis_unified_sts/.venv/bin/{pytest,black,ruff,mypy}`.

**GIT HYGIENE (critical):** NEVER run `git stash`/`pop`/`apply`/`drop` — it is repo-global across worktrees and corrupts the operator's stash. Use `git add <explicit paths>` + `git commit` only. Do not touch `/home/deploy/project/kis_unified_sts` (operator's main checkout).

**Stream base names (live form → shadow form):**
- candidate: `signal.candidate.futures` → `signal.candidate.futures.shadow`
- final: `signal.final.futures` → `signal.final.futures.shadow`
- fill: `order.fill.futures` → `order.fill.futures.shadow`

**Env vars:** decision_engine `FUTURES_STRATEGY_DAEMON` (existing, off/shadow/live), risk_filter **`FUTURES_RISK_FILTER`** (new, off/shadow/live), order_router `FUTURES_ORDER_ROUTER` (existing, off/paper/live). Stream env-overrides (consumer/router side, mirroring stock): `FUTURES_CANDIDATE_STREAM`, `FUTURES_FINAL_STREAM`, `FUTURES_FILL_STREAM`.

**Out of scope:** enabling a shadow run (systemd `Environment=` edits), F-2 (decision_engine live producer), shared-helper DRY extraction, futures monitor/dashboard `:shadow`, shadow kill_switch.

---

## File Structure

**Modify (production):**
- `shared/risk/runtime_state.py` — add `key_suffix` param (backward-compatible).
- `services/decision_engine/main.py` — `_candidate_stream_for` live/off base → `signal.candidate.futures`.
- `services/risk_filter/main.py` — add `_resolve_mode()` (`FUTURES_RISK_FILTER`) + `_streams_for(mode)` + off-inert gate; derive candidate/final streams + risk-state `key_suffix` in `_build_and_run`.
- `services/order_router/main.py` — add `_final_stream_for(mode)` + `_fill_stream_for(mode)`; wire into `_build_and_run` (daemon `final_stream` + FillLogger `stream`).

**Modify (tests):**
- `tests/unit/decision_engine/test_shadow_wiring.py` — update the `_candidate_stream_for("off")` assertion.
- `tests/unit/services/test_decision_engine_main.py` — update local `CANDIDATE_STREAM` constant (fidelity).
- `tests/unit/services/test_risk_filter_main.py` — update local constants (fidelity) + add `_resolve_mode`/`_streams_for` tests.
- `tests/unit/services/test_order_router_main.py` — add `_final_stream_for`/`_fill_stream_for` tests (keep F-3 `_resolve_mode` tests).
- `tests/integration/test_signal_to_fill_e2e.py` — update local stream constants to new bases (fidelity; test is self-consistent).

**Add (tests):**
- `tests/unit/risk/test_runtime_state_key_suffix.py` — `key_suffix` behavior + default-unchanged.

**Unchanged (verified):** daemon classes (`DecisionEngineDaemon`/`RiskFilterDaemon`/`OrderRouterDaemon`) take stream names as args; `StreamStage`; `tests/integration/test_futures_strategy_daemon_shadow.py` (uses the shadow name, unchanged); stock chain; kill_switch.

---

## Task 1: `RuntimeRiskState.key_suffix` (backward-compatible)

**Files:**
- Modify: `shared/risk/runtime_state.py` (the `__init__`, currently ~lines 32-36)
- Test: `tests/unit/risk/test_runtime_state_key_suffix.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/risk/test_runtime_state_key_suffix.py`:

```python
"""F-1: RuntimeRiskState.key_suffix isolates shadow risk-state keys."""

from __future__ import annotations

import fakeredis.aioredis
import pytest

from shared.risk.runtime_state import RuntimeRiskState


def _redis():
    return fakeredis.aioredis.FakeRedis()


def test_default_suffix_unchanged() -> None:
    rs = RuntimeRiskState(redis=_redis(), asset_class="futures")
    assert rs._risk_state._key == "risk:state:futures"
    assert rs._meta_key == "risk:state:futures:meta"


def test_shadow_suffix_isolates_keys() -> None:
    rs = RuntimeRiskState(redis=_redis(), asset_class="futures", key_suffix="shadow")
    assert rs._risk_state._key == "risk:state:futures:shadow"
    assert rs._meta_key == "risk:state:futures:shadow:meta"


def test_empty_suffix_is_noop() -> None:
    rs = RuntimeRiskState(redis=_redis(), asset_class="stock", key_suffix="")
    assert rs._risk_state._key == "risk:state:stock"
    assert rs._meta_key == "risk:state:stock:meta"


@pytest.mark.asyncio
async def test_shadow_writes_do_not_touch_live_key() -> None:
    redis = _redis()
    live = RuntimeRiskState(redis=redis, asset_class="futures")
    shadow = RuntimeRiskState(redis=redis, asset_class="futures", key_suffix="shadow")
    await shadow.record_trade(pnl_krw=-100_000.0)
    live_snap = await live.snapshot()
    shadow_snap = await shadow.snapshot()
    assert live_snap.daily_pnl_krw == 0.0  # live untouched
    assert shadow_snap.daily_pnl_krw == -100_000.0  # shadow accumulated
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /tmp/f1-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/risk/test_runtime_state_key_suffix.py -v`
Expected: FAIL (`TypeError: __init__() got an unexpected keyword argument 'key_suffix'`).

- [ ] **Step 3: Implement**

In `shared/risk/runtime_state.py`, replace the `__init__` (currently):
```python
    def __init__(self, *, redis: Any, asset_class: str = "futures") -> None:
        self._redis = redis
        self._asset_class = asset_class
        self._risk_state = RiskState(redis, asset_class)
        self._meta_key = f"risk:state:{asset_class}:meta"
```
with:
```python
    def __init__(
        self, *, redis: Any, asset_class: str = "futures", key_suffix: str = ""
    ) -> None:
        self._redis = redis
        self._asset_class = asset_class
        # key_suffix isolates a shadow/paper run's risk-state from live
        # (F-1). Default "" → identical keys to before (stock + all existing
        # callers unaffected). Colon-delimited to match the key convention.
        suffix = f":{key_suffix}" if key_suffix else ""
        self._risk_state = RiskState(
            redis, asset_class, key=f"risk:state:{asset_class}{suffix}"
        )
        self._meta_key = f"risk:state:{asset_class}{suffix}:meta"
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd /tmp/f1-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/risk/test_runtime_state_key_suffix.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Regression + mypy + commit**

```bash
cd /tmp/f1-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/risk/ tests/unit/stock_exit/ tests/unit/stock_risk_filter/ -q
/home/deploy/project/kis_unified_sts/.venv/bin/black shared/risk/runtime_state.py tests/unit/risk/test_runtime_state_key_suffix.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix shared/risk/runtime_state.py tests/unit/risk/test_runtime_state_key_suffix.py
/home/deploy/project/kis_unified_sts/.venv/bin/mypy shared/risk/runtime_state.py
git add shared/risk/runtime_state.py tests/unit/risk/test_runtime_state_key_suffix.py
git commit -m "feat(f-1): RuntimeRiskState.key_suffix for shadow risk-state isolation"
```
Expected: existing risk/stock_exit/stock_risk_filter tests still green (default suffix unchanged); mypy clean.

---

## Task 2: decision_engine — live candidate base = `signal.candidate.futures`

**Files:**
- Modify: `services/decision_engine/main.py` (`_candidate_stream_for`, currently ~lines 125-135)
- Test: `tests/unit/decision_engine/test_shadow_wiring.py`, `tests/unit/services/test_decision_engine_main.py`

- [ ] **Step 1: Update the helper test to the new live base (failing)**

In `tests/unit/decision_engine/test_shadow_wiring.py`, change the last assertion:
```python
    assert dem._candidate_stream_for("off") == "stream:signal.candidate"
```
to:
```python
    assert dem._candidate_stream_for("off") == "signal.candidate.futures"
    assert dem._candidate_stream_for("live") == "signal.candidate.futures"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /tmp/f1-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/decision_engine/test_shadow_wiring.py -v`
Expected: FAIL (helper still returns `stream:signal.candidate`).

- [ ] **Step 3: Implement**

In `services/decision_engine/main.py`, change `_candidate_stream_for`:
```python
def _candidate_stream_for(mode: str) -> str:
    """Map a mode string to the Redis stream name for signal candidates.

    shadow → isolated shadow stream; any other value (off / live) → the live
    candidate stream. Bases mirror the stock chain (F-1): asset-infixed,
    `.shadow` suffix for the shadow form.
    """
    return (
        "signal.candidate.futures.shadow"
        if mode == "shadow"
        else "signal.candidate.futures"
    )
```

- [ ] **Step 4: Update the fidelity constant in the daemon-level test**

In `tests/unit/services/test_decision_engine_main.py`, change:
```python
CANDIDATE_STREAM = "stream:signal.candidate"
```
to:
```python
CANDIDATE_STREAM = "signal.candidate.futures"
```
(This is a local constant passed to `DecisionEngineDaemon`; the test stays self-consistent. Updated for fidelity to production.)

- [ ] **Step 5: Run to verify it passes**

Run: `cd /tmp/f1-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/decision_engine/ tests/unit/services/test_decision_engine_main.py -q`
Expected: PASS.

- [ ] **Step 6: Format + commit**

```bash
cd /tmp/f1-impl
/home/deploy/project/kis_unified_sts/.venv/bin/black services/decision_engine/main.py tests/unit/decision_engine/test_shadow_wiring.py tests/unit/services/test_decision_engine_main.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix services/decision_engine/main.py tests/unit/decision_engine/test_shadow_wiring.py tests/unit/services/test_decision_engine_main.py
git add services/decision_engine/main.py tests/unit/decision_engine/test_shadow_wiring.py tests/unit/services/test_decision_engine_main.py
git commit -m "feat(f-1): decision_engine live candidate base = signal.candidate.futures"
```

---

## Task 3: risk_filter — mode + `_streams_for` + off-inert + shadow risk-state

**Files:**
- Modify: `services/risk_filter/main.py` (add module-level helpers; modify `_build_and_run`, currently ~lines 174-196)
- Test: `tests/unit/services/test_risk_filter_main.py`

- [ ] **Step 1: Write the failing helper tests**

Append to `tests/unit/services/test_risk_filter_main.py` (and add `_resolve_mode, _streams_for` to the existing `from services.risk_filter.main import ...` line):

```python
def test_resolve_mode_defaults_off(monkeypatch) -> None:
    monkeypatch.delenv("FUTURES_RISK_FILTER", raising=False)
    assert _resolve_mode() == "off"


def test_resolve_mode_shadow_and_live(monkeypatch) -> None:
    monkeypatch.setenv("FUTURES_RISK_FILTER", "shadow")
    assert _resolve_mode() == "shadow"
    monkeypatch.setenv("FUTURES_RISK_FILTER", "LIVE")
    assert _resolve_mode() == "live"


def test_resolve_mode_unknown_falls_through_to_off(monkeypatch) -> None:
    monkeypatch.setenv("FUTURES_RISK_FILTER", "garbage")
    assert _resolve_mode() == "off"


def test_streams_for_shadow_and_live(monkeypatch) -> None:
    monkeypatch.delenv("FUTURES_CANDIDATE_STREAM", raising=False)
    monkeypatch.delenv("FUTURES_FINAL_STREAM", raising=False)
    assert _streams_for("shadow") == (
        "signal.candidate.futures.shadow",
        "signal.final.futures.shadow",
    )
    assert _streams_for("live") == (
        "signal.candidate.futures",
        "signal.final.futures",
    )


def test_streams_for_env_override(monkeypatch) -> None:
    monkeypatch.setenv("FUTURES_CANDIDATE_STREAM", "custom.candidate")
    monkeypatch.setenv("FUTURES_FINAL_STREAM", "custom.final")
    assert _streams_for("live") == ("custom.candidate", "custom.final")
```

Update the import at the top of the file:
```python
from services.risk_filter.main import (
    RiskFilterDaemon,
    _resolve_mode,
    _signal_from_stream_fields,
    _streams_for,
)
```
And update the fidelity constants:
```python
CANDIDATE_STREAM = "signal.candidate.futures"
FINAL_STREAM = "signal.final.futures"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /tmp/f1-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/services/test_risk_filter_main.py -q`
Expected: FAIL (`ImportError: cannot import name '_resolve_mode'`).

- [ ] **Step 3: Add the module-level helpers**

In `services/risk_filter/main.py`, add near the top (after the imports / `logger = ...`, before `_build_and_run`):
```python
def _resolve_mode() -> str:
    """risk_filter mode: off (default, inert) | shadow | live."""
    import os

    mode = os.getenv("FUTURES_RISK_FILTER", "off").strip().lower()
    return mode if mode in ("shadow", "live") else "off"


def _streams_for(mode: str) -> tuple[str, str]:
    """Return (candidate, final) stream names for the mode (F-1).

    shadow → `.shadow`-suffixed isolated streams; live → unsuffixed. Both are
    env-overridable (FUTURES_CANDIDATE_STREAM / FUTURES_FINAL_STREAM), mirroring
    the stock chain.
    """
    import os

    if mode == "shadow":
        candidate = "signal.candidate.futures.shadow"
        final = "signal.final.futures.shadow"
    else:  # live
        candidate = "signal.candidate.futures"
        final = "signal.final.futures"
    return (
        os.getenv("FUTURES_CANDIDATE_STREAM", candidate),
        os.getenv("FUTURES_FINAL_STREAM", final),
    )
```

- [ ] **Step 4: Wire mode + streams + shadow risk-state into `_build_and_run`**

In `services/risk_filter/main.py::_build_and_run`, immediately after `redis_client = aioredis.from_url(redis_url)` add the off-inert gate:
```python
    mode = _resolve_mode()
    if mode not in ("shadow", "live"):
        logger.info("FUTURES_RISK_FILTER=%s (off) — risk_filter inert, exiting", mode)
        await redis_client.aclose()
        return 0
    candidate_stream, final_stream = _streams_for(mode)
    risk_state_suffix = "shadow" if mode == "shadow" else ""
```
(`logger` is module-level; confirm it exists — if not, use the module logger already used elsewhere in the file.)

Change the `RuntimeRiskState` construction:
```python
    runtime_state = RuntimeRiskState(redis=redis_client, asset_class="futures")
```
to:
```python
    runtime_state = RuntimeRiskState(
        redis=redis_client, asset_class="futures", key_suffix=risk_state_suffix
    )
```

Change the `RiskFilterDaemon(...)` stream args:
```python
        candidate_stream="stream:signal.candidate",
        final_stream="stream:signal.final",
```
to:
```python
        candidate_stream=candidate_stream,
        final_stream=final_stream,
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd /tmp/f1-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/services/test_risk_filter_main.py -q`
Expected: PASS. Then a smoke check on the off gate:
```bash
cd /tmp/f1-impl && FUTURES_RISK_FILTER=off /home/deploy/project/kis_unified_sts/.venv/bin/python -c "import services.risk_filter.main as m; print('off ->', m._resolve_mode(), '| streams live ->', m._streams_for('live'))"
```
Expected: `off -> off | streams live -> ('signal.candidate.futures', 'signal.final.futures')`.

- [ ] **Step 6: Format + commit**

```bash
cd /tmp/f1-impl
/home/deploy/project/kis_unified_sts/.venv/bin/black services/risk_filter/main.py tests/unit/services/test_risk_filter_main.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix services/risk_filter/main.py tests/unit/services/test_risk_filter_main.py
git add services/risk_filter/main.py tests/unit/services/test_risk_filter_main.py
git commit -m "feat(f-1): risk_filter FUTURES_RISK_FILTER mode + _streams_for + shadow risk-state"
```

---

## Task 4: order_router — `_final_stream_for` + `_fill_stream_for`

**Files:**
- Modify: `services/order_router/main.py` (add helpers near `_resolve_mode` ~line 294; wire FillLogger `stream` ~line 363 and daemon `final_stream` ~line 415 in `_build_and_run`)
- Test: `tests/unit/services/test_order_router_main.py`

- [ ] **Step 1: Write the failing helper tests**

Append to `tests/unit/services/test_order_router_main.py` (add `_final_stream_for, _fill_stream_for` to the existing `from services.order_router.main import ...` line):

```python
def test_final_stream_for_paper_and_live(monkeypatch) -> None:
    monkeypatch.delenv("FUTURES_FINAL_STREAM", raising=False)
    assert _final_stream_for("paper") == "signal.final.futures.shadow"
    assert _final_stream_for("live") == "signal.final.futures"


def test_fill_stream_for_paper_and_live(monkeypatch) -> None:
    monkeypatch.delenv("FUTURES_FILL_STREAM", raising=False)
    assert _fill_stream_for("paper") == "order.fill.futures.shadow"
    assert _fill_stream_for("live") == "order.fill.futures"


def test_stream_helpers_env_override(monkeypatch) -> None:
    monkeypatch.setenv("FUTURES_FINAL_STREAM", "custom.final")
    monkeypatch.setenv("FUTURES_FILL_STREAM", "custom.fill")
    assert _final_stream_for("paper") == "custom.final"
    assert _fill_stream_for("live") == "custom.fill"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /tmp/f1-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/services/test_order_router_main.py -q`
Expected: FAIL (`ImportError: cannot import name '_final_stream_for'`).

- [ ] **Step 3: Add the helpers**

In `services/order_router/main.py`, just after `_resolve_mode` (~line 304), add:
```python
def _final_stream_for(mode: str) -> str:
    """Final-signal stream the order_router consumes (F-1).

    paper → `.shadow` isolated stream (forms the shadow pipeline with
    risk_filter shadow); live → unsuffixed. Env-overridable.
    """
    import os

    base = "signal.final.futures.shadow" if mode == "paper" else "signal.final.futures"
    return os.getenv("FUTURES_FINAL_STREAM", base)


def _fill_stream_for(mode: str) -> str:
    """Fill stream FillLogger writes (F-1). paper → `.shadow`; live → unsuffixed."""
    import os

    base = "order.fill.futures.shadow" if mode == "paper" else "order.fill.futures"
    return os.getenv("FUTURES_FILL_STREAM", base)
```

- [ ] **Step 4: Wire into `_build_and_run`**

`mode` is already resolved (`mode = _resolve_mode()`, ~line 338) before the FillLogger block. Change the FillLogger `stream`:
```python
        stream="stream:order.fill",
```
to:
```python
        stream=_fill_stream_for(mode),
```
And change the daemon `final_stream`:
```python
        final_stream="stream:signal.final",
```
to:
```python
        final_stream=_final_stream_for(mode),
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd /tmp/f1-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/services/test_order_router_main.py tests/unit/execution/ -q`
Expected: PASS (new helper tests + F-3 `_resolve_mode` tests + execution suites all green).

- [ ] **Step 6: Format + commit**

```bash
cd /tmp/f1-impl
/home/deploy/project/kis_unified_sts/.venv/bin/black services/order_router/main.py tests/unit/services/test_order_router_main.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix services/order_router/main.py tests/unit/services/test_order_router_main.py
git add services/order_router/main.py tests/unit/services/test_order_router_main.py
git commit -m "feat(f-1): order_router _final_stream_for/_fill_stream_for (paper→shadow, live→live)"
```

---

## Task 5: integration-test fidelity + full gate + PR

**Files:**
- Modify: `tests/integration/test_signal_to_fill_e2e.py` (local stream constants → new bases; self-consistent, stays green)

- [ ] **Step 1: Update the e2e local constants for fidelity**

In `tests/integration/test_signal_to_fill_e2e.py`, change:
```python
CANDIDATE = "stream:signal.candidate"
FINAL = "stream:signal.final"
ORDER_FILL = "stream:order.fill"
```
to:
```python
CANDIDATE = "signal.candidate.futures"
FINAL = "signal.final.futures"
ORDER_FILL = "order.fill.futures"
```
(These are local constants passed to the daemon constructors; the chain stays internally consistent. Updated so the e2e test reflects production names.)

- [ ] **Step 2: Targeted + regression**

```bash
cd /tmp/f1-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/integration/test_signal_to_fill_e2e.py tests/integration/test_futures_strategy_daemon_shadow.py -q
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -k "decision_engine or risk_filter or order_router or runtime_state or signal_to_fill or strategy_daemon_shadow" -q
```
Expected: all PASS (the shadow integration test is unchanged — it uses the shadow name; e2e is self-consistent on the new names).

- [ ] **Step 3: Full gate (CI parity) + mypy**

```bash
cd /tmp/f1-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -m "not serial" -n auto -q --ignore=tests/performance && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -m serial -q
/home/deploy/project/kis_unified_sts/.venv/bin/mypy shared/risk/runtime_state.py
```
Expected: green; mypy clean. (Note: the local xdist full run may flake on an unrelated `ConfigLoader`-singleton test — a known pre-existing env artifact, see the F-3 PR. Confirm any failure is NOT in a futures-chain / runtime_state test; CI is the merge gate.)

- [ ] **Step 4: Commit + push + PR**

```bash
cd /tmp/f1-impl
git add tests/integration/test_signal_to_fill_e2e.py
git commit -m "test(f-1): e2e uses production futures stream bases"
git push -u origin feat/futures-stream-naming-coherence
gh pr create --base main --head feat/futures-stream-naming-coherence \
  --title "feat(f-1): futures chain mode-coherent stream naming + shadow isolation" \
  --body "$(cat <<'EOF'
## What
Make the decoupled futures chain (decision_engine → risk_filter → order_router) mode-coherent
and shadow-isolatable, mirroring the stock M4 chain: stock-style stream bases
(`signal.{candidate,final}.futures`, `order.fill.futures`) with a `.shadow` suffix, per-daemon
`_resolve_mode`/`_streams_for` helpers, and a non-live shadow risk-state.

## Why
The futures chain was incoherent and couldn't run end-to-end: decision_engine shadow wrote
`signal.candidate.futures.shadow` but off/live wrote the legacy `stream:signal.candidate`;
risk_filter had no mode and hardcoded `stream:signal.candidate`/`stream:signal.final`;
order_router (post-F-3) had off/paper/live execution but hardcoded stream names with no `.shadow`
form. F-1 is the prerequisite for any full-chain shadow run (and precedes F-2).

## Pipelines after F-1
- **Shadow (isolated):** decision_engine `FUTURES_STRATEGY_DAEMON=shadow` + risk_filter
  `FUTURES_RISK_FILTER=shadow` + order_router `FUTURES_ORDER_ROUTER=paper` — all on `.shadow`
  streams + `risk:state:futures:shadow`.
- **Live (future, gated):** all unsuffixed + `risk:state:futures`.
- **off:** inert everywhere (default). risk_filter gains the off-inert gate it lacked.

## Safe risk-state
`RuntimeRiskState` gains a backward-compatible `key_suffix` (default `""` → stock + all existing
callers unchanged). risk_filter shadow reads `risk:state:futures:shadow`. order_router paper is
already risk-isolated (Gate-3 daily-trade counter + caps are behind `if guard is not None`, and
paper sets `guard=None` per F-3) — confirmed, no change. kill_switch stays live-only. A shadow run
cannot trip the live kill_switch or move live risk counters. (Deliberate divergence from stock's
shared risk-state — futures is real-money.)

## Scope / unchanged
Daemon classes (take stream names as args) unchanged; `StreamStage` unchanged; stock chain
untouched (default suffix). Out of scope: enabling a shadow run (systemd env), F-2 live producer,
shared-helper DRY extraction, futures monitor/dashboard `:shadow`, shadow kill_switch.

## How tested
Per-daemon helper unit tests (`_resolve_mode`/`_streams_for`/`_final_stream_for`/`_fill_stream_for`),
`RuntimeRiskState.key_suffix` isolation tests (incl. shadow-writes-don't-touch-live), updated
decision_engine helper assertion, e2e on production bases, shadow integration test unchanged
(uses the shadow name). Full gate green; mypy/ruff/black clean.

Spec: `docs/superpowers/specs/2026-06-07-futures-stream-naming-coherence-f1-design.md`
Plan: `docs/superpowers/plans/2026-06-07-futures-stream-naming-coherence-f1.md`

## Follow-ups
F-2 (decision_engine live producer), F-4/F-5/F-6, F-8/F-9 cutover. Shared `signal_streams` helper
(DRY) if the two chains drift.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 5: Run code review** — `/code-review` on the PR and address findings.

---

## Self-Review (plan vs spec)

**Spec coverage:**
- §4.1 base names → Tasks 2/3/4 use `signal.{candidate,final}.futures` + `.shadow`. ✓
- §4.2 per-daemon mode→stream wiring → Task 2 (decision_engine), Task 3 (risk_filter `FUTURES_RISK_FILTER` + `_streams_for` + off-inert), Task 4 (order_router `_final_stream_for`/`_fill_stream_for`, paper→shadow). ✓
- §4.3 safe risk-state → Task 1 (`key_suffix`) + Task 3 (risk_filter shadow suffix); order_router paper already isolated (asserted via existing F-3 tests; documented). ✓
- §4.4 unchanged components → daemon classes/StreamStage/FillLogger internals untouched; only `_build_and_run` wiring + class args change. ✓
- §6 off-default everywhere → Task 3 adds risk_filter gate; decision_engine/order_router already off-default. ✓
- §7 testing → Tasks 1-5 cover every listed test. ✓
- §10 acceptance → Tasks 1-5. ✓

**Placeholder scan:** none — complete code in every step.

**Type consistency:** `RuntimeRiskState(*, redis, asset_class, key_suffix="")`; `_resolve_mode() -> str`; risk_filter `_streams_for(mode) -> tuple[str,str]` returns `(candidate, final)`; order_router `_final_stream_for(mode)/_fill_stream_for(mode) -> str`. Stream bases identical across producer/consumer (decision_engine candidate = risk_filter candidate; risk_filter final = order_router final; order_router fill = FillLogger stream). Shadow forms: candidate/final/fill all `.shadow`. risk-state suffix `:shadow` (colon). Env overrides: `FUTURES_CANDIDATE_STREAM` (risk_filter), `FUTURES_FINAL_STREAM` (risk_filter producer + order_router consumer — same name keeps them aligned), `FUTURES_FILL_STREAM` (order_router). decision_engine intentionally has no env override (mirrors stock_strategy); its default aligns with risk_filter's default.

**Open questions resolved:** clean-mirror per-module (no shared helper); paper→shadow streams; safe (suffixed) shadow risk-state via `key_suffix`; kill_switch live-only; integration tests are self-consistent (class args) so only the helper-assertion test must change.
