# MarketContext Builder Unification (F-4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract a single canonical `build_market_context(...)` assembler (one default policy for the three fields Setup A/C never read) that both the decoupled and orchestrator `MarketContext` builders call, + an invariant test locking that A/C ignore those three fields.

**Architecture:** New module function in `shared/decision/context.py`; both call sites (`services/decision_engine/context_provider.py::FuturesContextProvider.__call__` and `shared/strategy/entry/setup_adapters.py::_build_market_context`) delegate the `MarketContext` assembly + default policy to it. Default policy = orchestrator heuristics (`vwap→current_price`, `atr_90th_percentile→atr_14*1.5`, `current_spread_ticks→1.0`): zero live-orchestrator change; the decoupled path's `0.0→non-zero` is invisible (A/C don't read them).

**Tech Stack:** Python 3.11+, pytest. Pure-function refactor.

**Spec:** `docs/superpowers/specs/2026-06-07-market-context-unify-f4-design.md`

**Worktree:** Implement in `/tmp/f4-impl` (branch `feat/market-context-unify-f4`). Run venv tools from `cd /tmp/f4-impl` using `/home/deploy/project/kis_unified_sts/.venv/bin/{pytest,black,ruff,mypy}`.

**GIT HYGIENE (critical):** NEVER run `git stash`/`pop`/`apply`/`drop` — repo-global across worktrees, corrupts the operator's stash. Use `git add <explicit paths>` + `git commit` only. Do not touch `/home/deploy/project/kis_unified_sts`.

**Out of scope:** unifying raw-value extraction (different sources); computing real vwap/spread for the decoupled path; F-2.

---

## File Structure

- Modify: `shared/decision/context.py` (add `build_market_context`)
- Modify: `services/decision_engine/context_provider.py` (delegate assembly)
- Modify: `shared/strategy/entry/setup_adapters.py` (delegate assembly)
- Modify: `tests/unit/decision_engine/test_context_provider.py` (update spread assertion + add vwap/atr_90th)
- Create: `tests/unit/decision/test_build_market_context.py`
- Create: `tests/unit/strategy/test_setup_ac_field_invariance.py`

---

## Task 1: `build_market_context` assembler

**Files:** Modify `shared/decision/context.py`; Test `tests/unit/decision/test_build_market_context.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/decision/test_build_market_context.py`:
```python
"""F-4: canonical MarketContext assembler + default policy."""

from __future__ import annotations

from datetime import UTC, datetime

from shared.decision.context import MarketContext, build_market_context

_NOW = datetime(2026, 6, 8, 0, 30, tzinfo=UTC)


def _base() -> dict:
    return dict(
        now=_NOW, symbol="A05603", current_price=331.20, prev_close=331.00,
        today_open=331.10, atr_14=2.0, last_15min_high=332.0, last_15min_low=330.0,
    )


def test_defaults_applied_when_omitted() -> None:
    ctx = build_market_context(**_base())
    assert isinstance(ctx, MarketContext)
    assert ctx.vwap == 331.20  # -> current_price
    assert ctx.atr_90th_percentile == 3.0  # -> atr_14 * 1.5
    assert ctx.current_spread_ticks == 1.0  # -> 1.0
    assert ctx.scheduled_events == []


def test_explicit_values_honored() -> None:
    ctx = build_market_context(
        **_base(), vwap=999.0, atr_90th_percentile=5.0, current_spread_ticks=2.0
    )
    assert ctx.vwap == 999.0
    assert ctx.atr_90th_percentile == 5.0
    assert ctx.current_spread_ticks == 2.0


def test_core_fields_passed_through() -> None:
    ctx = build_market_context(**_base())
    assert ctx.now == _NOW
    assert ctx.symbol == "A05603"
    assert ctx.current_price == 331.20
    assert ctx.prev_close == 331.00
    assert ctx.today_open == 331.10
    assert ctx.atr_14 == 2.0
    assert ctx.last_15min_high == 332.0
    assert ctx.last_15min_low == 330.0
    assert ctx.macro_overnight is None
```

- [ ] **Step 2: Run to verify it fails** — `cd /tmp/f4-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/decision/test_build_market_context.py -q` → FAIL (ImportError).

- [ ] **Step 3: Implement** — add to `shared/decision/context.py` (after `load_scheduled_events`):
```python
def build_market_context(
    *,
    now: datetime,
    symbol: str,
    current_price: float,
    prev_close: float,
    today_open: float,
    atr_14: float,
    last_15min_high: float,
    last_15min_low: float,
    vwap: float | None = None,
    atr_90th_percentile: float | None = None,
    current_spread_ticks: float | None = None,
    macro_overnight: object | None = None,
    scheduled_events: list[ScheduledEvent] | None = None,
) -> MarketContext:
    """Assemble a MarketContext with the canonical default policy (F-4).

    Setup A and Setup C read NONE of ``vwap`` / ``atr_90th_percentile`` /
    ``current_spread_ticks`` (locked by the F-4 invariance test). They are
    assembled here with shared defaults so the decoupled (decision_engine) and
    orchestrator (setup_adapters) builders stay consistent: vwap→current_price,
    atr_90th→atr_14*1.5, spread→1.0. ``current_spread_ticks`` is uncomputable
    from the OHLCV-only tick stream, so the decoupled path always defaults it.
    """
    return MarketContext(
        now=now,
        symbol=symbol,
        current_price=current_price,
        prev_close=prev_close,
        today_open=today_open,
        vwap=vwap if vwap is not None else current_price,
        atr_14=atr_14,
        atr_90th_percentile=(
            atr_90th_percentile if atr_90th_percentile is not None else atr_14 * 1.5
        ),
        last_15min_high=last_15min_high,
        last_15min_low=last_15min_low,
        current_spread_ticks=(
            current_spread_ticks if current_spread_ticks is not None else 1.0
        ),
        macro_overnight=macro_overnight,
        scheduled_events=list(scheduled_events) if scheduled_events else [],
    )
```

- [ ] **Step 4: Run to verify it passes** — pytest → PASS (3).

- [ ] **Step 5: Format + mypy + commit**
```bash
cd /tmp/f4-impl
/home/deploy/project/kis_unified_sts/.venv/bin/black shared/decision/context.py tests/unit/decision/test_build_market_context.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix shared/decision/context.py tests/unit/decision/test_build_market_context.py
/home/deploy/project/kis_unified_sts/.venv/bin/mypy shared/decision/context.py 2>&1 | tail -3
git add shared/decision/context.py tests/unit/decision/test_build_market_context.py
git commit -m "feat(f-4): canonical build_market_context assembler + default policy"
git rev-parse HEAD
```
(If `tests/unit/decision/` lacks `__init__.py`, namespace pkg is fine — create the test file. mypy: no new errors in context.py.)

---

## Task 2: delegate both builders to the assembler

**Files:** Modify `services/decision_engine/context_provider.py`, `shared/strategy/entry/setup_adapters.py`, `tests/unit/decision_engine/test_context_provider.py`.

- [ ] **Step 1: Update the decoupled test for the new defaults (make it fail first)**

In `tests/unit/decision_engine/test_context_provider.py`, change the assertion `assert ctx.current_spread_ticks == 0.0` to:
```python
    assert ctx.current_spread_ticks == 1.0  # F-4 canonical default
    assert ctx.vwap == ctx.current_price  # F-4: vwap defaults to current_price
    assert ctx.atr_90th_percentile == ctx.atr_14 * 1.5  # F-4 default
```

- [ ] **Step 2: Run to verify it fails** — `cd /tmp/f4-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/decision_engine/test_context_provider.py -q` → FAIL (still 0.0).

- [ ] **Step 3: Refactor the decoupled builder**

In `services/decision_engine/context_provider.py`:
- Add to imports: `from shared.decision.context import MarketContext, ScheduledEvent, build_market_context` (extend the existing import line).
- Replace the final `return MarketContext(...)` block (the one with `vwap=0.0`/`atr_90th_percentile=0.0`/`current_spread_ticks=0.0`) with:
```python
        return build_market_context(
            now=now_kst,
            symbol=symbol,
            current_price=current_price,
            prev_close=prev_close,
            today_open=today_open,
            atr_14=atr_14,
            last_15min_high=float(last_15min_high),
            last_15min_low=float(last_15min_low),
            macro_overnight=macro,
            scheduled_events=list(events),
        )
```
(Omitting vwap/atr_90th_percentile/current_spread_ticks → canonical defaults. `MarketContext` import may now be unused in this file — if ruff flags it, remove it from the import, keeping `ScheduledEvent` + `build_market_context`. Keep `ScheduledEvent` (used in the type hints).)

- [ ] **Step 4: Refactor the orchestrator builder**

In `shared/strategy/entry/setup_adapters.py::_build_market_context`:
- Ensure `build_market_context` is imported (find the existing `from shared.decision.context import ...` and add `build_market_context`; if MarketContext/ScheduledEvent are imported there, extend that line).
- Replace the final `return MarketContext(...)` block (lines ~439-453) with:
```python
    return build_market_context(
        now=ts_kst,
        symbol=symbol,
        current_price=current_price,
        prev_close=prev_close,
        today_open=today_open,
        atr_14=atr_14,
        last_15min_high=last_15min_high,
        last_15min_low=last_15min_low,
        vwap=vwap,
        atr_90th_percentile=atr_90th,
        current_spread_ticks=spread_ticks,
        macro_overnight=macro_overnight,
        scheduled_events=scheduled_events,
    )
```
(Passes the `_get_float`-computed `vwap`/`atr_90th`/`spread_ticks` explicitly → orchestrator behavior byte-identical. The fast-path `if isinstance(mc, MarketContext): return mc` and all extraction logic above stay UNCHANGED. `MarketContext` is still referenced by the fast-path `isinstance` check, so keep that import.)

- [ ] **Step 5: Run to verify it passes + regression**
```bash
cd /tmp/f4-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/decision_engine/test_context_provider.py tests/unit/strategy/ -q
```
Expected: PASS (decoupled test with new defaults + all setup_adapters/strategy tests still green — orchestrator behavior unchanged).

- [ ] **Step 6: Format + mypy + commit**
```bash
cd /tmp/f4-impl
/home/deploy/project/kis_unified_sts/.venv/bin/black services/decision_engine/context_provider.py shared/strategy/entry/setup_adapters.py tests/unit/decision_engine/test_context_provider.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix services/decision_engine/context_provider.py shared/strategy/entry/setup_adapters.py tests/unit/decision_engine/test_context_provider.py
/home/deploy/project/kis_unified_sts/.venv/bin/mypy shared/strategy/entry/setup_adapters.py 2>&1 | tail -3
git add services/decision_engine/context_provider.py shared/strategy/entry/setup_adapters.py tests/unit/decision_engine/test_context_provider.py
git commit -m "feat(f-4): both MarketContext builders delegate to build_market_context"
git rev-parse HEAD
```

---

## Task 3: invariant test + full gate + PR

**Files:** Create `tests/unit/strategy/test_setup_ac_field_invariance.py`.

- [ ] **Step 1: Write the invariance test**

First inspect how Setup A / Setup C are constructed + invoked in existing tests (read `tests/unit/decision_engine/` or `tests/` for `SetupAGapReversion` / `SetupCEventReaction` usage, and `shared/decision/setups/gap_reversion.py` / `event_reaction.py` for the `.check(ctx)` API). Then create `tests/unit/strategy/test_setup_ac_field_invariance.py` that, for BOTH setups, builds two MarketContexts identical except `vwap`/`atr_90th_percentile`/`current_spread_ticks` (e.g. all-0.0 vs vwap=9999/atr_90th=9999/spread=9999) and asserts the `.check()` result is equivalent (both None, or both a Signal with identical direction/entry_price/stop_loss/take_profit). Use `build_market_context` to construct the contexts, choosing core field values that make each setup fire (mirror the fixtures in the existing setup tests — read them so the contexts actually trigger a signal).

Skeleton (adapt the triggering field values to what the existing setup tests use):
```python
"""F-4 invariant: Setup A/C ignore vwap / atr_90th_percentile / current_spread_ticks."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from shared.decision.context import build_market_context
from shared.decision.setups.event_reaction import SetupCEventReaction
from shared.decision.setups.gap_reversion import SetupAGapReversion

_KST = ZoneInfo("Asia/Seoul")


def _ctx(**overrides):
    base = dict(
        now=datetime(2026, 6, 8, 9, 5, tzinfo=_KST),
        symbol="A05603",
        current_price=331.20,
        prev_close=335.00,   # gap down -> Setup A long bias (tune to fire)
        today_open=331.30,
        atr_14=2.0,
        last_15min_high=332.0,
        last_15min_low=330.0,
    )
    base.update(overrides)
    return build_market_context(**base)


def _sig_tuple(sig):
    if sig is None:
        return None
    return (sig.direction, sig.entry_price, sig.stop_loss, sig.take_profit)


@pytest.mark.parametrize("setup", [SetupAGapReversion(), SetupCEventReaction()])
def test_signal_invariant_to_unused_fields(setup):
    lo = _ctx(vwap=0.0, atr_90th_percentile=0.0, current_spread_ticks=0.0)
    hi = _ctx(vwap=9999.0, atr_90th_percentile=9999.0, current_spread_ticks=9999.0)
    assert _sig_tuple(setup.check(lo)) == _sig_tuple(setup.check(hi))
```
Note: the goal is invariance (equal results under varied fields), which holds whether or not the setup actually fires for these inputs — but prefer core values that make at least Setup A fire (so the test proves invariance on a real signal, not just None==None). If a setup needs scheduled_events/macro to fire, pass them identically in both contexts. Read the existing setup unit tests and reuse their triggering fixtures.

- [ ] **Step 2: Run to verify it passes** — `cd /tmp/f4-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/strategy/test_setup_ac_field_invariance.py -q` → PASS. (If it fails because a setup DOES read one of the three fields, that's a real finding — STOP and report; the spec's premise would be wrong.)

- [ ] **Step 3: Format + commit**
```bash
cd /tmp/f4-impl
/home/deploy/project/kis_unified_sts/.venv/bin/black tests/unit/strategy/test_setup_ac_field_invariance.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix tests/unit/strategy/test_setup_ac_field_invariance.py
git add tests/unit/strategy/test_setup_ac_field_invariance.py
git commit -m "test(f-4): lock Setup A/C invariance to vwap/atr_90th/spread"
git rev-parse HEAD
```

- [ ] **Step 4: Full gate (CI parity) + mypy**
```bash
cd /tmp/f4-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -m "not serial" -n auto -q --ignore=tests/performance -p no:randomly 2>&1 | grep -E "FAILED|ERROR|passed|failed" | tail -15
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -m serial -q 2>&1 | grep -E "FAILED|ERROR|passed|failed" | tail -8
/home/deploy/project/kis_unified_sts/.venv/bin/mypy shared/decision/context.py shared/strategy/entry/setup_adapters.py services/decision_engine/context_provider.py 2>&1 | tail -6
```
Expected: green; mypy no new errors. (A local xdist flake on `test_handles_arbitrary_dicts`/`test_entry_path_100_symbols` is a known pre-existing artifact — confirm any failure is NOT a context/setup_adapters/context_provider test; CI is the gate.)

- [ ] **Step 5: Push + PR**
```bash
cd /tmp/f4-impl
git push -u origin feat/market-context-unify-f4
gh pr create --base main --head feat/market-context-unify-f4 \
  --title "feat(f-4): unify MarketContext builder (single assembler + A/C field-invariance test)" \
  --body "$(cat <<'EOF'
## What
Extract a single canonical `build_market_context(...)` (`shared/decision/context.py`) that both the
decoupled (`decision_engine/context_provider.py`) and orchestrator (`setup_adapters._build_market_context`)
`MarketContext` builders call, with one default policy for the three fields Setup A/C never read
(`vwap`, `atr_90th_percentile`, `current_spread_ticks`). Plus an invariant test locking that A/C ignore them.

## Why
The two builders duplicated the `MarketContext` assembly and DISAGREED on the defaults for those three
fields (decoupled hardcoded 0.0; orchestrator used heuristics) — the memory's flagged "builder drift".
No signal impact today (A/C read none of them), but genuine duplication + a latent inconsistency a future
Setup could trip over.

## Design
- **Canonical default policy = orchestrator heuristics** (operator decision): vwap→current_price,
  atr_90th_percentile→atr_14*1.5, current_spread_ticks→1.0. **Zero behavior change for the live
  orchestrator** (it already passed these); the decoupled path's 0.0→non-zero is invisible — A/C don't
  read them and the `MarketContext` fields aren't serialized downstream (only the resulting `Signal` is
  published).
- Raw-value *extraction* is intentionally NOT unified (genuinely different sources: indicator-engine
  object vs market_data/indicators dicts) — only the assembly + default policy is shared.
- The orchestrator fast-path (return an already-built `MarketContext`) is preserved.

## Invariant test
`test_setup_ac_field_invariance.py` runs Setup A + Setup C over contexts identical except
vwap/atr_90th/spread and asserts identical signals — so any future code that reads one of these fields
in A/C breaks loudly, keeping the de-duplicated builder safe.

## How tested
build_market_context unit tests (defaults + explicit overrides + passthrough); decoupled test updated
for the canonical defaults (`current_spread_ticks` 0.0→1.0, + vwap/atr_90th asserts); orchestrator tests
unchanged + green (byte-identical behavior); A/C field-invariance test. Full gate green; mypy/ruff/black
clean.

> CI note: a local `-n auto` run may flake on the unrelated `test_handles_arbitrary_dicts` /
> `test_entry_path_100_symbols` (known pre-existing artifacts). CI `test` gate is the arbiter.

Spec: `docs/superpowers/specs/2026-06-07-market-context-unify-f4-design.md`
Plan: `docs/superpowers/plans/archive/2026-06-07-market-context-unify-f4.md`

## Follow-ups (Phase B complete after this)
F-2 (decision_engine live producer), then F-8/F-9 cutover. If a future Setup needs real vwap/spread,
the single assembler is the one place to wire it (+ an ingest-layer change for spread).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 6: Run code review** — `/code-review` on the PR and address findings.

---

## Self-Review (plan vs spec)

**Spec coverage:** §4.1 assembler → Task 1; §4.2 decoupled delegate → Task 2; §4.3 orchestrator delegate (+ fast-path preserved) → Task 2; §4.4 invariant test → Task 3; §6 testing → Tasks 1-3. ✓

**Placeholder scan:** none — complete code, except Task 3 Step 1 which (correctly) instructs reading the existing setup test fixtures to choose triggering values rather than guessing the exact gap thresholds.

**Type consistency:** `build_market_context(*, now, symbol, current_price, prev_close, today_open, atr_14, last_15min_high, last_15min_low, vwap=None, atr_90th_percentile=None, current_spread_ticks=None, macro_overnight=None, scheduled_events=None) -> MarketContext`. Decoupled omits the 3 optional → defaults; orchestrator passes them explicitly → byte-identical. Default policy (current_price / atr_14*1.5 / 1.0) consistent between the assembler, the orchestrator's prior inline defaults, and the updated decoupled test assertions.

**Open questions resolved:** default policy = orchestrator heuristics; assembler is a module function in `shared/decision/context.py`; extraction not unified; invariant test reuses existing setup fixtures for triggering values.
