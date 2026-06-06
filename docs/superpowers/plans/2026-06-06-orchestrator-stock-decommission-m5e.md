# Orchestrator Stock Decommission (M5e) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A flag-gated CLI guard (`STOCK_ORCHESTRATOR_ENABLED`, default `"true"`) in `sts trade start` that lets the operator permanently block the monolithic orchestrator's stock path after the M5d cutover, plus deprecation notes on the stock-orchestrator scripts and doc updates — so the decoupled M4 pipeline is the permanent stock path with no double-trade risk.

**Architecture:** A single guard at the one chokepoint (`cli/main.py::trade_start`): two pure module-level helpers (`_stock_orchestrator_enabled` reads the env flag default-true; `_stock_orchestrator_blocked(asset)` = stock + disabled) and an early fail-fast guard that rejects `--asset stock` with a decoupled-pipeline message. Default-true ⇒ merging changes nothing; the operator flips the flag post-cutover. The orchestrator class, shared strategy/indicator code, and screener/fusion are unchanged.

**Tech Stack:** Python 3.11+, click + `click.testing.CliRunner` (tests), pytest. No Redis/external.

**Spec:** `docs/superpowers/specs/2026-06-06-orchestrator-stock-decommission-m5e-design.md`

**Worktree:** Implement in `/tmp/m5e-impl` (branch `feat/orchestrator-stock-decommission-m5e`). Run venv tools from `cd /tmp/m5e-impl` using `/home/deploy/project/kis_unified_sts/.venv/bin/{pytest,black,ruff,mypy}`.

**PR strategy:** One PR (`feat/orchestrator-stock-decommission-m5e`).

**Out of scope:** TradingOrchestrator class reduction (stays for futures); shared strategy/indicator changes (M4-P uses them); screener/fusion changes (M4-P consumes same keys); an orchestrator `__init__` second guard (CLI is the only path — YAGNI); futures decommission.

---

## File Structure

**Modify:**
- `cli/main.py` — add `_stock_orchestrator_enabled()` + `_stock_orchestrator_blocked(asset)` (module level, just above `@trade.command("start")` at line 1660) + the guard as the first executable statement of `trade_start` (line 1660+).
- `scripts/cron/stock_trading.sh` — header deprecation comment.
- `scripts/cron/install_stock_trading_watchdog.sh` — header deprecation comment.
- `CLAUDE.md` — CLI section deprecation + env-var table entry + stock section note.
- `docs/runbooks/stock-pipeline-cutover-m5d.md` — cutover final step (`STOCK_ORCHESTRATOR_ENABLED=false`) + rollback step (`=true`).

**Create:**
- `tests/unit/test_cli_stock_guard.py` — guard unit tests (4: helper default/case, blocked matrix, CliRunner exit-1).

**Verified facts:** `trade_start(strategy, asset, capital, paper, daemon, yes_live)` is `@trade.command("start")` (cli/main.py:1660); `os` is imported module-level (used by the existing `KIS_REAL_TRADING` check). CLI tests use `from cli.main import cli` + `CliRunner().invoke(cli, ["trade", "start", ...])`. No `tests/unit/cli/` dir — CLI tests live directly under `tests/unit/` (`test_cli_commands.py`).

---

## Task 1: CLI guard + unit tests

**Files:**
- Modify: `cli/main.py`
- Test: `tests/unit/test_cli_stock_guard.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_cli_stock_guard.py`:

```python
"""M5e: orchestrator stock decommission guard in `sts trade start`."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

import cli.main as m


def test_enabled_defaults_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STOCK_ORCHESTRATOR_ENABLED", raising=False)
    assert m._stock_orchestrator_enabled() is True


def test_enabled_false_and_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STOCK_ORCHESTRATOR_ENABLED", "false")
    assert m._stock_orchestrator_enabled() is False
    monkeypatch.setenv("STOCK_ORCHESTRATOR_ENABLED", " FALSE ")
    assert m._stock_orchestrator_enabled() is False
    monkeypatch.setenv("STOCK_ORCHESTRATOR_ENABLED", "true")
    assert m._stock_orchestrator_enabled() is True


def test_blocked_matrix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STOCK_ORCHESTRATOR_ENABLED", "false")
    assert m._stock_orchestrator_blocked("stock") is True
    assert m._stock_orchestrator_blocked("futures") is False  # only stock is blocked
    monkeypatch.delenv("STOCK_ORCHESTRATOR_ENABLED", raising=False)
    assert m._stock_orchestrator_blocked("stock") is False  # default-true ⇒ allowed


def test_cli_blocks_stock_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STOCK_ORCHESTRATOR_ENABLED", "false")
    result = CliRunner().invoke(m.cli, ["trade", "start", "--asset", "stock", "--paper"])
    assert result.exit_code == 1
    assert "decoupled M4 pipeline" in result.output
    assert "STOCK_ORCHESTRATOR_ENABLED=true" in result.output  # rollback hint
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /tmp/m5e-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/test_cli_stock_guard.py -v`
Expected: FAIL (`AttributeError: module 'cli.main' has no attribute '_stock_orchestrator_enabled'`).

- [ ] **Step 3: Add the helpers**

In `cli/main.py`, add these two functions at module level immediately above the `@trade.command("start")` decorator (line ~1660). `os` is already imported at module level.

```python
def _stock_orchestrator_enabled() -> bool:
    """The monolithic orchestrator runs stock only when explicitly enabled.

    Default ``True`` (pre-cutover behaviour). The operator sets
    ``STOCK_ORCHESTRATOR_ENABLED=false`` as the final M5d cutover step so the
    orchestrator permanently refuses stock — the decoupled M4 pipeline owns it.
    Rollback: set it back to ``true``.
    """
    return os.getenv("STOCK_ORCHESTRATOR_ENABLED", "true").strip().lower() == "true"


def _stock_orchestrator_blocked(asset: str) -> bool:
    """True when the orchestrator must refuse this asset (stock + flag disabled)."""
    return asset == "stock" and not _stock_orchestrator_enabled()
```

- [ ] **Step 4: Add the guard to `trade_start`**

In `cli/main.py::trade_start`, insert the guard as the FIRST executable statement of the function body — immediately after the function's docstring and BEFORE `import asyncio` / the `mode_str`/`click.echo("Starting ...")` block — so it fails fast before any orchestrator construction.

The current body begins:
```python
def trade_start(
    strategy: str,
    asset: str,
    capital: float,
    paper: bool,
    daemon: bool,
    yes_live: bool,
):
    """트레이딩 시작

    \b
    Example:
        sts trade start -s bb_reversion -a stock
        sts trade start -s pure_micro -a futures --capital 5000000
        sts trade start -s bb_reversion -a stock --daemon
    """
    import asyncio
```
Change it to insert the guard between the docstring and `import asyncio`:
```python
    """트레이딩 시작

    \b
    Example:
        sts trade start -s bb_reversion -a stock
        sts trade start -s pure_micro -a futures --capital 5000000
        sts trade start -s bb_reversion -a stock --daemon
    """
    if _stock_orchestrator_blocked(asset):
        click.echo(
            "Error: the monolithic orchestrator no longer runs stock — stock trades "
            "via the decoupled M4 pipeline "
            "(kis-stock-{strategy-daemon,risk-filter,order-router,exit-daemon}).",
            err=True,
        )
        click.echo(
            "  Rollback to the orchestrator stock path: set "
            "STOCK_ORCHESTRATOR_ENABLED=true.",
            err=True,
        )
        raise SystemExit(1)

    import asyncio
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /tmp/m5e-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/test_cli_stock_guard.py -v`
Expected: PASS (4 passed). The CliRunner test exits 1 cleanly (the guard fires before `import asyncio`, so no orchestrator/asyncio startup runs).

- [ ] **Step 6: Format + mypy + commit**

```bash
cd /tmp/m5e-impl
/home/deploy/project/kis_unified_sts/.venv/bin/black cli/main.py tests/unit/test_cli_stock_guard.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix cli/main.py tests/unit/test_cli_stock_guard.py
/home/deploy/project/kis_unified_sts/.venv/bin/mypy cli/main.py
git add cli/main.py tests/unit/test_cli_stock_guard.py
git commit -m "feat(m5e): flag-gated guard blocking orchestrator stock path (default-allow)"
```
Note: `mypy cli/main.py` may report pre-existing errors elsewhere in the large file — confirm the two new helpers + the guard introduce NO new errors. If pre-existing `cli/main.py` errors make this noisy, diff against the baseline (`git stash && mypy cli/main.py > /tmp/base.txt; git stash pop`) is acceptable but usually unnecessary — just confirm none mention the new function names or the guard lines.

---

## Task 2: Script deprecation + docs + runbook + gate + PR

**Files:**
- Modify: `scripts/cron/stock_trading.sh`, `scripts/cron/install_stock_trading_watchdog.sh`, `CLAUDE.md`, `docs/runbooks/stock-pipeline-cutover-m5d.md`

- [ ] **Step 1: Deprecation comment on the stock-orchestrator scripts**

In `scripts/cron/stock_trading.sh`, add a comment block immediately after the shebang line (`#!/usr/bin/env bash` or `#!/bin/bash`):
```bash
# DEPRECATED (M5e): the monolithic orchestrator no longer runs stock once the
# M5d cutover is complete. Stock trades via the decoupled M4 pipeline
# (kis-stock-{strategy-daemon,risk-filter,order-router,exit-daemon}). This script
# invokes `sts trade start --asset stock`, which the CLI refuses when
# STOCK_ORCHESTRATOR_ENABLED=false (set by the operator at cutover).
# Runbook: docs/runbooks/stock-pipeline-cutover-m5d.md
```

In `scripts/cron/install_stock_trading_watchdog.sh`, add immediately after the shebang:
```bash
# DEPRECATED (M5e): installs the stock-orchestrator watchdog cron. Superseded by
# the decoupled M4 pipeline + its systemd units after the M5d cutover. Do not
# install on a cut-over host. Runbook: docs/runbooks/stock-pipeline-cutover-m5d.md
```

- [ ] **Step 2: Update CLAUDE.md**

In `CLAUDE.md`, find the CLI commands section (the block containing `sts trade start --strategy bb_reversion --asset stock --paper`). Replace that stock line with a deprecation note and keep the futures example:
```bash
# 트레이딩/모의
# (DEPRECATED) sts trade start --asset stock — 컷오버 후 orchestrator는 stock 미운용.
#   stock은 decoupled M4 파이프라인(kis-stock-{strategy-daemon,risk-filter,order-router,exit-daemon})으로 운용.
#   롤백: STOCK_ORCHESTRATOR_ENABLED=true. 런북: docs/runbooks/stock-pipeline-cutover-m5d.md
sts trade start --strategy pure_micro --asset futures   # 선물은 orchestrator 경로 유지
sts paper start --strategy bb_reversion --asset stock
```
(If the exact stock line differs, preserve surrounding lines and only swap the stock `trade start` example for the deprecation note + keep a futures example.)

In the env-var table (the `## 🔑 환경 변수` section), add a row:
```markdown
| `STOCK_ORCHESTRATOR_ENABLED` | 모놀리식 orchestrator의 stock 경로 허용 (기본 `true`). 컷오버 후 `false`로 stock 영구 차단 (M5e) |
```

In the stock trading overview (the `#### 주식 (Stock)` section), add one line near the top:
```markdown
- **운용 경로**: stock은 decoupled M4 파이프라인(M4-P/R/O/X + M5a/b/c)으로 운용한다 (M5d 컷오버 후). orchestrator 경로는 `STOCK_ORCHESTRATOR_ENABLED=false`로 차단되며 futures 전용으로 남는다. 롤백은 플래그를 `true`로 되돌린다.
```

- [ ] **Step 3: Wire M5e into the M5d runbook**

In `docs/runbooks/stock-pipeline-cutover-m5d.md`, in the `## Cutover sequence` section, append a step 5:
```markdown
5. **Permanently block the orchestrator stock path** (M5e): set `STOCK_ORCHESTRATOR_ENABLED=false` in the operator `.env` so `sts trade start --asset stock` (and the stock cron) is refused at the CLI even if accidentally invoked. (Belt-and-suspenders on top of disabling the cron in step 1.)
```
And in the `## Rollback` section, add to the manual-revert list:
```markdown
- Set `STOCK_ORCHESTRATOR_ENABLED=true` (re-allow the orchestrator stock path) before re-enabling the orchestrator cron.
```

- [ ] **Step 4: Lint + targeted + full gate**

```bash
cd /tmp/m5e-impl
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check cli/main.py tests/unit/test_cli_stock_guard.py
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/test_cli_stock_guard.py tests/unit/test_cli_commands.py -v
bash -n scripts/cron/stock_trading.sh && bash -n scripts/cron/install_stock_trading_watchdog.sh && echo "shell syntax OK"
```
Expected: ruff clean; CLI tests PASS (new guard tests + existing command tests unaffected); shell scripts still parse.

```bash
cd /tmp/m5e-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -m "not serial" -n auto -q --ignore=tests/performance && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -m serial -q
```
Expected: green (M5e only adds a guard + docs; futures/stock-daemon/existing tests unaffected).

- [ ] **Step 5: Commit + push + PR**

```bash
cd /tmp/m5e-impl
git add scripts/cron/stock_trading.sh scripts/cron/install_stock_trading_watchdog.sh CLAUDE.md docs/runbooks/stock-pipeline-cutover-m5d.md
git commit -m "docs(m5e): deprecate stock-orchestrator scripts + wire flag into runbook/CLAUDE"
git push -u origin feat/orchestrator-stock-decommission-m5e
gh pr create --base main --head feat/orchestrator-stock-decommission-m5e \
  --title "feat(m5e): orchestrator stock decommission — flag-gated guard + docs" \
  --body "$(cat <<'EOF'
## What
The final M5 sub-project: a flag-gated CLI guard (`STOCK_ORCHESTRATOR_ENABLED`,
default `true`) in `sts trade start` that lets the operator permanently block the
monolithic orchestrator's stock path after the M5d cutover, plus deprecation notes
on the stock-orchestrator scripts and CLAUDE.md/runbook updates.

## Why
Post-M5d-cutover, stock trades via the decoupled M4 pipeline. The orchestrator can
still be started for stock (`sts trade start --asset stock`), which would double-trade.
M5e codifies a permanent, operator-controlled block at the single CLI chokepoint.

## Merge-safe, operator-activated
The flag defaults to `true` — merging changes NOTHING (the orchestrator stock path
still works). The operator sets `STOCK_ORCHESTRATOR_ENABLED=false` as the final M5d
cutover step, after which `--asset stock` is refused with a decoupled-pipeline message.
This matches the M5 philosophy (default-off / operator-gated) and avoids a stock
blackout that a hard guard merged before the cutover would cause.

## Approach — guard + decommission + docs, no class reduction
The `TradingOrchestrator` is generic over `asset_class` and STAYS for futures
(Phase-5). M5e only guards the STOCK entry path: two pure helpers
(`_stock_orchestrator_enabled` / `_stock_orchestrator_blocked`) + a fail-fast guard in
`trade_start` (the one chokepoint all stock starts converge through — CLI, cron,
watchdog). Futures unaffected. The orchestrator class, shared strategy/indicator code,
and the screener→fusion pipeline (which M4-P consumes) are UNCHANGED.

## How tested
Unit (`tests/unit/test_cli_stock_guard.py`): helper default-true / case+whitespace;
blocked matrix (stock+off→blocked, futures+off→allowed, stock+default→allowed);
CliRunner `trade start --asset stock` with the flag off → exit 1 + decoupled message
(fires before orchestrator startup). Existing CLI tests + full `tests/` gate green.
`bash -n` on the deprecated scripts.

Spec: `docs/superpowers/specs/2026-06-06-orchestrator-stock-decommission-m5e-design.md`
Plan: `docs/superpowers/plans/2026-06-06-orchestrator-stock-decommission-m5e.md`

## Follow-ups
This completes the M5 stream-pipeline-decoupling series (M0a–M5e). Future: residual
paper-account cleanup; a futures decoupling track (separate from Phase-5); optional
orchestrator `__init__` defense-in-depth guard if a non-CLI start path ever appears.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 6: Run code review** — `/code-review` on the PR and address findings.

---

## Self-Review (plan vs spec)

**Spec coverage:**
- §4.1 CLI guard (`_stock_orchestrator_enabled`/`_stock_orchestrator_blocked` + `trade_start` guard) → Task 1. ✓
- §4.2 script deprecation → Task 2 Step 1. ✓
- §4.3 docs (CLAUDE.md + M5d runbook enable/rollback) → Task 2 Steps 2-3. ✓
- §5 sequencing safety (default-true merge-safe) → Task 1 helper default `"true"` + the blocked-matrix test (stock+default→allowed). ✓
- §6 testing (helpers + CliRunner exit-1) → Task 1 Step 1 (4 tests). ✓
- §7 acceptance (guard matrix; default true; script comments; CLAUDE.md+runbook; orchestrator/shared/screener unchanged; tests green, no Redis) → Tasks 1-2. ✓

**Placeholder scan:** none — complete code/edits in every step.

**Type consistency:** `_stock_orchestrator_enabled() -> bool`, `_stock_orchestrator_blocked(asset: str) -> bool`, guard `raise SystemExit(1)`, message substrings (`"decoupled M4 pipeline"`, `"STOCK_ORCHESTRATOR_ENABLED=true"`) match between cli/main.py and the test assertions. Test imports `import cli.main as m` + `m.cli` (the click group) + `m._stock_orchestrator_enabled`/`_stock_orchestrator_blocked` — all defined in Task 1. CliRunner invoke args `["trade", "start", "--asset", "stock", "--paper"]` match the `@trade.command("start")` + `--asset` option. The env flag name `STOCK_ORCHESTRATOR_ENABLED` is identical across helper, guard, tests, docs, and runbook.

**Open questions resolved:** test location = `tests/unit/test_cli_stock_guard.py` (new file; CLI tests live under `tests/unit/`); no orchestrator `__init__` second guard (CLI is the only path — YAGNI); scripts get a comment only (CLI guard enforces); guard message text fixed in §4.1.
