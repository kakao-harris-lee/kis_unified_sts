# decision_engine Live Producer (F-2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `FUTURES_STRATEGY_DAEMON=live` produce real candidate signals to `signal.candidate.futures` using the same (mode-agnostic) real context provider as shadow; `off`/unset stays inert.

**Architecture:** The producer builder is already mode-agnostic and only wired in the `shadow` branch (shadow-first). Generalize it to all "producing" modes (shadow|live) via a `_is_producing_mode` predicate + a `_resolve_context_provider` selector. The candidate stream is already mode-correct (F-1 `_candidate_stream_for`). The producer is ungated (emits candidates, not orders — `order_router` is the gated stage).

**Tech Stack:** Python 3.11+ asyncio, pytest (fakeredis for integration). Internal refactor of `services/decision_engine/main.py`.

**Spec:** `docs/superpowers/specs/2026-06-07-decision-engine-live-producer-f2-design.md`

**Worktree:** Implement in `/tmp/f2-impl` (branch `feat/decision-engine-live-producer-f2`). Run venv tools from `cd /tmp/f2-impl` using `/home/deploy/project/kis_unified_sts/.venv/bin/{pytest,black,ruff,mypy}`.

**GIT HYGIENE (critical):** NEVER run `git stash`/`pop`/`apply`/`drop` — repo-global across worktrees, corrupts the operator's stash. Use `git add <explicit paths>` + `git commit` only. Do not touch `/home/deploy/project/kis_unified_sts`.

**Out of scope:** enabling the live chain (systemd env — operator step); risk_filter/order_router gating (already correct); F-8/F-9.

---

## File Structure

- Modify: `services/decision_engine/main.py` (`_is_producing_mode`, rename `_build_shadow_context_provider`→`_build_context_provider`, `_resolve_context_provider`, `_build_and_run` wiring + docstring).
- Modify: `tests/unit/decision_engine/test_shadow_wiring.py` (add `_is_producing_mode` + `_resolve_context_provider` tests).
- Modify: `tests/integration/test_futures_strategy_daemon_shadow.py` (parametrize over shadow + live stream).

---

## Task 1: producer wiring (shadow|live) + unit tests

**Files:** Modify `services/decision_engine/main.py`, `tests/unit/decision_engine/test_shadow_wiring.py`.

- [ ] **Step 1: Write the failing unit tests**

Append to `tests/unit/decision_engine/test_shadow_wiring.py`:
```python
import pytest


def test_is_producing_mode():
    assert dem._is_producing_mode("shadow") is True
    assert dem._is_producing_mode("live") is True
    assert dem._is_producing_mode("off") is False
    assert dem._is_producing_mode("garbage") is False


@pytest.mark.asyncio
async def test_resolve_context_provider_off_is_inert_stub():
    cp, feed, sync = await dem._resolve_context_provider("off", object())
    assert feed is None
    assert sync is None
    assert await cp() is None  # stub emits nothing


@pytest.mark.asyncio
async def test_resolve_context_provider_live_builds_real(monkeypatch):
    called = {}

    async def _fake_builder(redis_client):
        called["redis"] = redis_client
        return ("PROVIDER", "FEED", "SYNC")

    monkeypatch.setattr(dem, "_build_context_provider", _fake_builder)
    sentinel = object()
    cp, feed, sync = await dem._resolve_context_provider("live", sentinel)
    assert called["redis"] is sentinel  # real builder invoked for live
    assert (cp, feed, sync) == ("PROVIDER", "FEED", "SYNC")


@pytest.mark.asyncio
async def test_resolve_context_provider_shadow_builds_real(monkeypatch):
    async def _fake_builder(redis_client):
        return ("PROVIDER", "FEED", "SYNC")

    monkeypatch.setattr(dem, "_build_context_provider", _fake_builder)
    cp, feed, sync = await dem._resolve_context_provider("shadow", object())
    assert cp == "PROVIDER"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /tmp/f2-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/decision_engine/test_shadow_wiring.py -q`
Expected: FAIL (`_is_producing_mode`/`_resolve_context_provider` don't exist).

- [ ] **Step 3: Add `_is_producing_mode`**

In `services/decision_engine/main.py`, after `_candidate_stream_for` (the existing helper), add:
```python
def _is_producing_mode(mode: str) -> bool:
    """True when the daemon builds a REAL context provider (shadow|live).

    off / unset / unknown → False → inert stub (no candidates emitted). The
    candidate stream is mode-correct via _candidate_stream_for regardless.
    """
    return mode in ("shadow", "live")
```

- [ ] **Step 4: Rename + generalize the builder**

Rename `async def _build_shadow_context_provider(` → `async def _build_context_provider(`. Update its docstring first line to:
```python
    """Wire indicator engine + StreamConsumerFeed(raw_data) + FuturesContextProvider.

    Mode-agnostic: used for both shadow and live producing modes. Returns
    ``(context_provider, feed, sync_redis)``.  The caller is responsible for
    calling ``await feed.stop()`` and ``sync_redis.close()`` on shutdown.
    """
```
And change the symbol guard message:
```python
        raise RuntimeError("FUTURES_STRATEGY_SYMBOL must be set for shadow/live mode")
```
(The body is otherwise unchanged.)

- [ ] **Step 5: Add `_resolve_context_provider`**

Add (after `_build_context_provider`):
```python
async def _resolve_context_provider(mode: str, redis_client: Any) -> tuple[Any, Any, Any]:
    """Return (context_provider, feed, sync_redis) for the mode.

    Producing modes (shadow|live) → real FuturesContextProvider (+ feed +
    sync_redis to close on shutdown). Otherwise an inert stub returning None,
    with feed=sync_redis=None.
    """
    if _is_producing_mode(mode):
        return await _build_context_provider(redis_client)

    async def _stub_context_provider() -> None:
        return None

    return _stub_context_provider, None, None
```
Ensure `Any` is imported at module top (it is used elsewhere in the file; confirm `from typing import Any` exists — if not, add it).

- [ ] **Step 6: Wire `_build_and_run`**

In `_build_and_run`, replace the block:
```python
    feed = None
    sync_redis = None
    if mode == "shadow":
        context_provider, feed, sync_redis = await _build_shadow_context_provider(
            redis_client
        )
    else:

        async def _stub_context_provider() -> None:
            # off mode: emit nothing (inert stub — original Task 10 behaviour).
            return None

        context_provider = _stub_context_provider
```
with:
```python
    context_provider, feed, sync_redis = await _resolve_context_provider(
        mode, redis_client
    )
```
And update the `_build_and_run` docstring to document live:
```python
    """Production entrypoint — flag-gated (FUTURES_STRATEGY_DAEMON=off|shadow|live).

    off / unset: inert stub (context_provider returns None, no signals emitted).
    shadow:      real context_provider → signal.candidate.futures.shadow.
    live:        real context_provider → signal.candidate.futures.
    The producer is ungated (emits candidates, not orders — order_router is the
    gated, wallet-authority stage).
    """
```
(The `finally` block already handles `feed`/`sync_redis` being None — unchanged.)

- [ ] **Step 7: Run to verify it passes**

Run: `cd /tmp/f2-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/decision_engine/ -q`
Expected: PASS (new wiring tests + existing decision_engine tests green).

- [ ] **Step 8: Format + mypy + commit**

```bash
cd /tmp/f2-impl
/home/deploy/project/kis_unified_sts/.venv/bin/black services/decision_engine/main.py tests/unit/decision_engine/test_shadow_wiring.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix services/decision_engine/main.py tests/unit/decision_engine/test_shadow_wiring.py
/home/deploy/project/kis_unified_sts/.venv/bin/mypy services/decision_engine/main.py 2>&1 | tail -4
git add services/decision_engine/main.py tests/unit/decision_engine/test_shadow_wiring.py
git commit -m "feat(f-2): decision_engine live producer (real provider for shadow|live)"
git rev-parse HEAD
```
(mypy: no NEW errors attributable to main.py; pre-existing repo-wide errors are fine.)

---

## Task 2: live-stream integration coverage + full gate + PR

**Files:** Modify `tests/integration/test_futures_strategy_daemon_shadow.py`.

- [ ] **Step 1: Parametrize the integration test over shadow + live streams**

In `tests/integration/test_futures_strategy_daemon_shadow.py`, parametrize the test over both candidate streams so the producer→daemon path is proven for the LIVE stream too. Change the test function:
- Add the decorator above `async def test_event_breakout_produces_shadow_candidate():`:
```python
@pytest.mark.parametrize(
    "candidate_stream",
    ["signal.candidate.futures.shadow", "signal.candidate.futures"],
)
```
- Rename it to `async def test_event_breakout_produces_candidate(candidate_stream):`.
- In the `DecisionEngineDaemon(...)` construction, change `candidate_stream=_SHADOW_STREAM,` → `candidate_stream=candidate_stream,`.
- In the final assertion, change `entries = await redis_assert.xrange(_SHADOW_STREAM)` → `entries = await redis_assert.xrange(candidate_stream)` and update the assert message to `"Expected at least one candidate on the stream"`.
(Keep `_SHADOW_STREAM` constant if other code references it; if it becomes unused, remove it to satisfy ruff. Check with ruff.)

- [ ] **Step 2: Run to verify it passes**

Run: `cd /tmp/f2-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/integration/test_futures_strategy_daemon_shadow.py -q`
Expected: PASS (2 parametrized cases — shadow + live both carry a candidate).

- [ ] **Step 3: Format + commit**

```bash
cd /tmp/f2-impl
/home/deploy/project/kis_unified_sts/.venv/bin/black tests/integration/test_futures_strategy_daemon_shadow.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix tests/integration/test_futures_strategy_daemon_shadow.py
git add tests/integration/test_futures_strategy_daemon_shadow.py
git commit -m "test(f-2): integration covers live + shadow candidate streams"
git rev-parse HEAD
```

- [ ] **Step 4: Full gate (CI parity) + mypy**

```bash
cd /tmp/f2-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -m "not serial" -n auto -q --ignore=tests/performance -p no:randomly 2>&1 | grep -E "FAILED|ERROR|passed|failed" | tail -12
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -m serial -q 2>&1 | grep -E "FAILED|ERROR|passed|failed" | tail -6
/home/deploy/project/kis_unified_sts/.venv/bin/mypy services/decision_engine/main.py 2>&1 | tail -4
```
Expected: green; mypy no new errors. (A local xdist flake on `test_handles_arbitrary_dicts` / `test_entry_path_100_symbols` is a known pre-existing artifact — confirm any failure is NOT a decision_engine test; CI is the gate.)

- [ ] **Step 5: Push + PR**

```bash
cd /tmp/f2-impl
git push -u origin feat/decision-engine-live-producer-f2
gh pr create --base main --head feat/decision-engine-live-producer-f2 \
  --title "feat(f-2): decision_engine live producer (real provider for shadow|live)" \
  --body "$(cat <<'EOF'
## What
Make `FUTURES_STRATEGY_DAEMON=live` produce real candidate signals to `signal.candidate.futures`,
using the same (mode-agnostic) real `FuturesContextProvider` as shadow. `off`/unset stays inert.

## Why
`live` mode was an inert stub (emitted nothing) — shadow-first incrementalism. The producer builder
(`_build_shadow_context_provider`) was already mode-agnostic (real raw_data feed + indicator engine +
daily ref + macro + events), and F-1 already made the candidate stream mode-correct. So the only thing
missing for a live producer was letting `live` use the real builder. This completes the producer side
of the decoupled futures chain.

## Design
- `_is_producing_mode(mode)` → True for shadow|live (off/unknown → inert stub).
- Renamed `_build_shadow_context_provider` → `_build_context_provider` (it was never shadow-specific).
- `_resolve_context_provider(mode, redis)` selects the real provider (shadow|live) or an inert stub
  (off) — makes the mode→provider wiring unit-testable without heavy I/O.
- `_build_and_run` delegates to it; the candidate stream is `_candidate_stream_for(mode)` (F-1):
  shadow → `signal.candidate.futures.shadow`, live → `signal.candidate.futures`.

## Safety
The live producer is **ungated** — it emits candidate signals to a stream, NOT orders. This matches
`stock_strategy` and the guard-at-order-layer principle: `LiveModeGuard` gates `order_router` (the
wallet-authority stage); `risk_filter`/`order_router` are independently gated. A live decision_engine
producing while the chain is suspended/off is harmless (no order_router action). **Nothing is enabled
by default** — `FUTURES_STRATEGY_DAEMON=live` is an explicit operator env step; `off`/`shadow` behavior
is unchanged.

## How tested
`_is_producing_mode` (off/shadow/live/unknown); `_resolve_context_provider` (off→inert stub returns
None + feed/sync None; live & shadow→real builder invoked); integration parametrized over both streams
(shadow + live each carry a candidate end-to-end). Existing decision_engine tests green; full gate
green; mypy/ruff/black clean.

> CI note: a local `-n auto` run may flake on the unrelated `test_handles_arbitrary_dicts` /
> `test_entry_path_100_symbols` (known pre-existing artifacts). CI `test` gate is the arbiter.

Spec: `docs/superpowers/specs/2026-06-07-decision-engine-live-producer-f2-design.md`
Plan: `docs/superpowers/plans/archive/2026-06-07-decision-engine-live-producer-f2.md`

## Follow-ups
With F-2 the decoupled chain can produce candidates in live. Phase C remains (Gate-gated):
F-8 (systemd reconciliation + `FUTURES_ORCHESTRATOR_ENABLED` guard to prevent double-trading at
cutover), F-9 (futures cutover runbook, Gate 1-3 + written approval). Plus the operator step of
actually enabling a shadow/live run via systemd env.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 6: Run code review** — `/code-review` on the PR and address findings.

---

## Self-Review (plan vs spec)

**Spec coverage:** §4.1 `_is_producing_mode` → Task 1 Step 3; §4.2 rename → Task 1 Step 4; §4.3 `_resolve_context_provider` → Task 1 Step 5; §4.4 `_build_and_run` wiring + docstring → Task 1 Step 6; §7 testing → Task 1 (unit) + Task 2 (integration); §10 acceptance → Tasks 1-2. ✓

**Placeholder scan:** none — complete code in every step.

**Type consistency:** `_is_producing_mode(mode: str) -> bool`; `_build_context_provider(redis_client) -> tuple[Any, Any, Any]` (renamed, same signature); `_resolve_context_provider(mode: str, redis_client: Any) -> tuple[Any, Any, Any]`; `_build_and_run` unpacks `(context_provider, feed, sync_redis)` exactly as before. The stub returns `None` (matches the prior inline stub). `finally` still guards `feed`/`sync_redis` not-None.

**Open questions resolved:** producer ungated (matches stock + guard-at-order-layer); builder renamed (no external refs); selector extracted for testability; integration parametrized over both streams.
