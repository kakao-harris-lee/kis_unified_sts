# Futures Orchestrator Guard (F-8) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `FUTURES_ORCHESTRATOR_ENABLED` flag + guard so `sts trade start --asset futures` refuses to run when disabled — the futures mirror of stock's M5e guard — preventing orchestrator↔decoupled-chain double-trading at cutover.

**Architecture:** Pure CLI guard in `cli/main.py`, mirroring `_stock_orchestrator_enabled`/`_stock_orchestrator_blocked` + the `trade_start` gate. Default `true` (orchestrator is today's futures path); operator sets `false` at cutover. Environment-agnostic (Docker `trader` container runs the gated CLI).

**Tech Stack:** Python 3.11+, Click, pytest (CliRunner).

**Spec:** `docs/superpowers/specs/2026-06-07-futures-orchestrator-guard-f8-design.md`

**Worktree:** Implement in `/tmp/f8-impl` (branch `feat/futures-orchestrator-guard-f8`). Run venv tools from `cd /tmp/f8-impl` using `/home/deploy/project/kis_unified_sts/.venv/bin/{pytest,black,ruff,mypy}`.

**GIT HYGIENE (critical):** NEVER run `git stash`/`pop`/`apply`/`drop` — repo-global, corrupts the operator's stash. Use `git add <explicit paths>` + `git commit` only. Do not touch `/home/deploy/project/kis_unified_sts`.

**Out of scope:** systemd/compose changes; deploying the decoupled daemons (F-9); CLAUDE.md/systemd cleanup.

---

## File Structure

- Modify: `cli/main.py` (add `_futures_orchestrator_enabled`/`_futures_orchestrator_blocked` + `trade_start` gate)
- Create: `tests/unit/test_cli_futures_guard.py`

---

## Task 1: `FUTURES_ORCHESTRATOR_ENABLED` guard + tests

**Files:** Modify `cli/main.py`; Create `tests/unit/test_cli_futures_guard.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_cli_futures_guard.py`:
```python
"""F-8: orchestrator futures decommission guard in `sts trade start`."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

import cli.main as m


def test_enabled_defaults_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FUTURES_ORCHESTRATOR_ENABLED", raising=False)
    assert m._futures_orchestrator_enabled() is True


def test_enabled_false_and_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FUTURES_ORCHESTRATOR_ENABLED", "false")
    assert m._futures_orchestrator_enabled() is False
    monkeypatch.setenv("FUTURES_ORCHESTRATOR_ENABLED", " FALSE ")
    assert m._futures_orchestrator_enabled() is False
    monkeypatch.setenv("FUTURES_ORCHESTRATOR_ENABLED", "true")
    assert m._futures_orchestrator_enabled() is True


def test_enabled_truthy_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FUTURES_ORCHESTRATOR_ENABLED", "1")
    assert m._futures_orchestrator_enabled() is True
    monkeypatch.setenv("FUTURES_ORCHESTRATOR_ENABLED", "YES")
    assert m._futures_orchestrator_enabled() is True
    monkeypatch.setenv("FUTURES_ORCHESTRATOR_ENABLED", "0")
    assert m._futures_orchestrator_enabled() is False
    monkeypatch.setenv("FUTURES_ORCHESTRATOR_ENABLED", "no")
    assert m._futures_orchestrator_enabled() is False


def test_blocked_matrix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FUTURES_ORCHESTRATOR_ENABLED", "false")
    assert m._futures_orchestrator_blocked("futures") is True
    assert m._futures_orchestrator_blocked("stock") is False  # only futures is blocked
    monkeypatch.delenv("FUTURES_ORCHESTRATOR_ENABLED", raising=False)
    assert m._futures_orchestrator_blocked("futures") is False  # default-true => allowed


def test_cli_blocks_futures_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FUTURES_ORCHESTRATOR_ENABLED", "false")
    result = CliRunner().invoke(
        m.cli, ["trade", "start", "--asset", "futures", "--paper"]
    )
    assert result.exit_code == 1
    assert "decoupled chain" in result.output
    assert "FUTURES_ORCHESTRATOR_ENABLED=true" in result.output  # rollback hint


def test_cli_allows_futures_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default-true: the guard does NOT block futures (it proceeds past the gate).

    We don't run a full session — just assert the guard's block message is absent.
    """
    monkeypatch.delenv("FUTURES_ORCHESTRATOR_ENABLED", raising=False)
    # Invoke with an invalid strategy so it exits quickly AFTER the guard; the
    # key assertion is that the FUTURES guard message never appears.
    result = CliRunner().invoke(
        m.cli,
        ["trade", "start", "--asset", "futures", "--paper", "--strategy", "__nope__"],
    )
    assert "the monolithic orchestrator no longer runs futures" not in result.output
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /tmp/f8-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/test_cli_futures_guard.py -q`
Expected: FAIL (`_futures_orchestrator_enabled` doesn't exist).

- [ ] **Step 3: Add the guard functions**

In `cli/main.py`, immediately after `_stock_orchestrator_blocked` (the existing function, before the `@trade.command("start")` decorator), add:
```python
def _futures_orchestrator_enabled() -> bool:
    """The monolithic orchestrator runs futures only when explicitly enabled.

    Default ``True`` (the orchestrator IS today's futures path). The operator
    sets ``FUTURES_ORCHESTRATOR_ENABLED=false`` at the futures cutover so the
    orchestrator refuses futures — the decoupled chain (decision_engine →
    risk_filter → order_router) owns it, preventing double-trading on the same
    account. Rollback: set it back to ``true`` (``1``/``yes`` also accepted).
    """
    return os.getenv("FUTURES_ORCHESTRATOR_ENABLED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _futures_orchestrator_blocked(asset: str) -> bool:
    """True when the orchestrator must refuse this asset (futures + flag disabled)."""
    return asset == "futures" and not _futures_orchestrator_enabled()
```

- [ ] **Step 4: Wire the `trade_start` gate**

In `trade_start`, immediately after the existing stock-blocked `if _stock_orchestrator_blocked(asset): ... sys.exit(1)` block, add:
```python
    if _futures_orchestrator_blocked(asset):
        click.echo(
            "Error: the monolithic orchestrator no longer runs futures — futures "
            "trades via the decoupled chain (decision_engine → risk_filter → "
            "order_router).",
            err=True,
        )
        click.echo(
            "  Rollback to the orchestrator futures path: set "
            "FUTURES_ORCHESTRATOR_ENABLED=true.",
            err=True,
        )
        sys.exit(1)
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd /tmp/f8-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/test_cli_futures_guard.py tests/unit/test_cli_stock_guard.py -q`
Expected: PASS (new futures guard tests + the stock guard tests still green).
Note: if `test_cli_allows_futures_by_default` behaves unexpectedly (e.g. the invalid strategy path emits something that trips an assertion), simplify it to assert only `"the monolithic orchestrator no longer runs futures" not in result.output` regardless of exit code — the point is the guard didn't fire. Do NOT change production code to satisfy it.

- [ ] **Step 6: Format + commit**

```bash
cd /tmp/f8-impl
/home/deploy/project/kis_unified_sts/.venv/bin/black cli/main.py tests/unit/test_cli_futures_guard.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix cli/main.py tests/unit/test_cli_futures_guard.py
git add cli/main.py tests/unit/test_cli_futures_guard.py
git commit -m "feat(f-8): FUTURES_ORCHESTRATOR_ENABLED double-trade guard in sts trade start"
git rev-parse HEAD
```

---

## Task 2: full gate + PR

- [ ] **Step 1: Targeted + regression**

```bash
cd /tmp/f8-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/test_cli_futures_guard.py tests/unit/test_cli_stock_guard.py -q
```
Expected: all PASS.

- [ ] **Step 2: Full gate (CI parity)**

```bash
cd /tmp/f8-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -m "not serial" -n auto -q --ignore=tests/performance -p no:randomly 2>&1 | grep -E "FAILED|ERROR|passed|failed" | tail -12
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -m serial -q 2>&1 | grep -E "FAILED|ERROR|passed|failed" | tail -6
```
Expected: green. (A local xdist flake on `test_handles_arbitrary_dicts` / `test_entry_path_100_symbols` is a known pre-existing artifact — confirm any failure is NOT a cli guard test; CI is the gate.)

- [ ] **Step 3: Push + PR**

```bash
cd /tmp/f8-impl
git push -u origin feat/futures-orchestrator-guard-f8
gh pr create --base main --head feat/futures-orchestrator-guard-f8 \
  --title "feat(f-8): FUTURES_ORCHESTRATOR_ENABLED double-trade guard" \
  --body "$(cat <<'EOF'
## What
Add a `FUTURES_ORCHESTRATOR_ENABLED` flag + guard so `sts trade start --asset futures` (what the
Docker `trader` container runs) refuses to start when disabled — the futures mirror of stock's M5e
`STOCK_ORCHESTRATOR_ENABLED` guard.

## Why
The decoupled futures chain is now fully functional (F-1..F-7) but dormant. At cutover, bringing up
the decoupled futures daemons while the orchestrator still trades futures would **double-trade** the
same account. This guard lets the operator make the orchestrator stand down for futures
(`FUTURES_ORCHESTRATOR_ENABLED=false`) so only the decoupled chain trades.

## Design
- `_futures_orchestrator_enabled()` — default **true** (the orchestrator IS today's futures path);
  `1/true/yes` enabled. Set `false` at cutover; rollback `true`.
- `_futures_orchestrator_blocked(asset)` — `asset == "futures" and not enabled`.
- `trade_start` gate (mirrors the stock branch): blocked → exit 1 with a clear message + rollback hint.
- **Default-true → zero behavior change** until set; stock guard untouched.

## Docker (deployment is Docker, not systemd)
At cutover the operator sets `FUTURES_ORCHESTRATOR_ENABLED=false` in the `trader` service env and brings
up the decoupled futures daemons as compose services. paper/live is unchanged (Docker env →
`--paper`/`--live`), orthogonal to this guard. F-8 is guard-only — no compose/systemd changes, nothing
deployed or enabled.

## How tested
Mirror of `test_cli_stock_guard.py`: enabled default-true / false / case-insensitive / truthy set;
blocked matrix (futures+disabled→True, stock→False, default→False); CLI blocks futures when disabled
(exit 1 + decoupled-chain message + rollback hint); CLI allows futures by default (guard doesn't fire).
Stock guard tests unchanged + green. Full gate green; ruff/black clean.

Spec: `docs/superpowers/specs/2026-06-07-futures-orchestrator-guard-f8-design.md`
Plan: `docs/superpowers/plans/archive/2026-06-07-futures-orchestrator-guard-f8.md`

## Follow-ups
F-9 (futures cutover runbook: add decoupled daemons to docker-compose, set this flag false, Phase-5
Gate 1-3 + written approval). The decoupled chain stays dormant until then.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: Run code review** — `/code-review` on the PR and address findings.

---

## Self-Review (plan vs spec)

**Spec coverage:** §4.1 guard functions → Task 1 Step 3; §4.2 trade_start gate → Task 1 Step 4; §6 testing → Task 1 + Task 2; §8 acceptance → Tasks 1-2. ✓

**Placeholder scan:** none — complete code in every step.

**Type consistency:** `_futures_orchestrator_enabled() -> bool`, `_futures_orchestrator_blocked(asset: str) -> bool` — identical shape to the stock pair. Default-true via the `{1,true,yes}` truthy set matching stock. The `trade_start` gate uses `sys.exit(1)` + `click.echo(..., err=True)` exactly like the stock branch. `os`/`click`/`sys` are already imported in `cli/main.py` (used by the stock guard).

**Open questions resolved:** guard-only (no systemd/compose); mirror (parallel per-asset functions, not a generalize-and-touch-stock refactor) to keep the working stock guard intact; default-true preserves current behavior.
