# LLM Market-Context Cron (M5b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A shadow-first, default-off single-shot cron (`scripts/analysis/llm_market_context.py`) that runs the existing `LLMContextPublisher("stock")` once per invocation and publishes `trading:stock:market_context` — extracting the orchestrator's 60-min LLM loop into a standalone, market-hours-gated job so the context survives the M5 cutover.

**Architecture:** A thin cron wrapper. `run_once(mode)` resolves the `STOCK_LLM_CONTEXT` flag (off/shadow/live), fail-safe-forces `TRADING_STATE_KEY_SUFFIX=shadow` in shadow mode (so it never clobbers the orchestrator's live key — same mechanism as M5a), constructs the **unchanged** `LLMContextPublisher`, calls `run_analysis()` (OpenAI, mocked in tests) → `publish_to_redis()`. Market-hours gating is the crontab schedule's job, not code. The consumer (`StrategyManager`/`LLMContextProvider`) already reads the key — unchanged.

**Tech Stack:** Python 3.11+, asyncio, `fakeredis` (tests), `unittest.mock` (AsyncMock for the OpenAI call), pytest.

**Spec:** `docs/superpowers/specs/2026-06-06-llm-context-cron-m5b-design.md`

**Worktree:** Implement in the isolated worktree `/tmp/m5b-impl` (branch `feat/llm-context-cron-m5b`) — the operator is concurrently using the main repo dir. Run venv tools from `cd /tmp/m5b-impl` using absolute paths: `/home/deploy/project/kis_unified_sts/.venv/bin/{pytest,black,ruff,mypy}`.

**PR strategy:** Land as **one PR** (`feat/llm-context-cron-m5b`).

**Out of scope:** the M5d cutover flip (crontab→live + orchestrator publisher gate-off), futures market context, on-demand `request_refresh()`, a long-running daemon / Prometheus pull endpoint, consumer changes, Pushgateway.

---

## File Structure

**Create:**
- `scripts/analysis/llm_market_context.py` — the cron script (`_resolve_mode`, `_ensure_shadow_isolation`, `run_once`, `main`).
- `tests/unit/scripts/test_llm_market_context.py` — unit tests (mode/isolation/off-inert/shadow-publish/None-skip; OpenAI mocked).
- `tests/integration/test_llm_market_context_cron.py` — integration test (shadow → `:shadow` key, live key untouched, read-back).

**Modify:** none (M5b is purely additive — `LLMContextPublisher`, orchestrator, `trading_state`, and the consumer are unchanged).

**Note:** `scripts.analysis` is an implicit namespace package (no `__init__.py`), and `import scripts.analysis.llm_market_context` works (verified). `tests/unit/scripts/` is the established script-test location.

---

## Task 1: Cron script + unit tests

**Files:**
- Create: `scripts/analysis/llm_market_context.py`
- Test: `tests/unit/scripts/test_llm_market_context.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/scripts/test_llm_market_context.py`:

```python
"""M5b cron: mode routing, fail-safe shadow isolation, single-shot run+publish."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

import scripts.analysis.llm_market_context as m


def test_resolve_mode_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STOCK_LLM_CONTEXT", raising=False)
    assert m._resolve_mode() == "off"


def test_ensure_shadow_isolation_forces_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    # setenv (tracked) so teardown removes it even though _ensure writes os.environ
    # directly — mirrors the M5a env-leak fix.
    monkeypatch.setenv("TRADING_STATE_KEY_SUFFIX", "")
    m._ensure_shadow_isolation("shadow")
    assert os.environ["TRADING_STATE_KEY_SUFFIX"] == "shadow"


def test_ensure_shadow_isolation_live_leaves_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRADING_STATE_KEY_SUFFIX", "")
    m._ensure_shadow_isolation("live")
    assert os.environ.get("TRADING_STATE_KEY_SUFFIX", "") == ""


def test_run_once_off_is_inert(monkeypatch: pytest.MonkeyPatch) -> None:
    cls = MagicMock()
    monkeypatch.setattr(
        "services.trading.llm_context_publisher.LLMContextPublisher", cls
    )
    rc = asyncio.run(m.run_once("off"))
    assert rc == 0
    cls.assert_not_called()  # off path constructs no publisher (no OpenAI/Redis)


def test_run_once_shadow_runs_and_publishes(monkeypatch: pytest.MonkeyPatch) -> None:
    inst = MagicMock()
    inst.run_analysis = AsyncMock(return_value=MagicMock(regime="BULL_STRONG", confidence=0.8))
    cls = MagicMock(return_value=inst)
    monkeypatch.setattr(
        "services.trading.llm_context_publisher.LLMContextPublisher", cls
    )
    monkeypatch.setenv("TRADING_STATE_KEY_SUFFIX", "")

    rc = asyncio.run(m.run_once("shadow"))

    assert rc == 0
    cls.assert_called_once_with("stock")
    inst.run_analysis.assert_awaited_once()
    inst.publish_to_redis.assert_called_once()
    assert os.environ["TRADING_STATE_KEY_SUFFIX"] == "shadow"  # fail-safe isolation


def test_run_once_none_analysis_skips_publish(monkeypatch: pytest.MonkeyPatch) -> None:
    inst = MagicMock()
    inst.run_analysis = AsyncMock(return_value=None)  # OpenAI failure -> None
    cls = MagicMock(return_value=inst)
    monkeypatch.setattr(
        "services.trading.llm_context_publisher.LLMContextPublisher", cls
    )
    monkeypatch.setenv("TRADING_STATE_KEY_SUFFIX", "")

    rc = asyncio.run(m.run_once("shadow"))

    assert rc == 0  # graceful — prior context persists via Redis TTL
    inst.publish_to_redis.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /tmp/m5b-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/scripts/test_llm_market_context.py -v`
Expected: FAIL (ModuleNotFoundError: scripts.analysis.llm_market_context).

- [ ] **Step 3: Implement**

Create `scripts/analysis/llm_market_context.py`:

```python
"""Standalone LLM market-context publisher (M5b cron, shadow-first, default-off).

Extracts the orchestrator's 60-min LLMContextPublisher loop into a single-shot
cron. Each invocation runs ONE market analysis and publishes
``trading:stock:market_context`` (to the ``:shadow`` namespace in shadow mode).
Market-hours gating is the crontab schedule's job, not this script.

Modes (env ``STOCK_LLM_CONTEXT``):
  off (default) — inert: no OpenAI/Redis, exit 0.
  shadow        — publish to trading:stock:market_context:shadow (fail-safe
                  TRADING_STATE_KEY_SUFFIX). Never clobbers the orchestrator's
                  live key — for side-by-side validation before the M5d cutover.
  live (M5d)    — publish to the live key (orchestrator publisher gated off).

Recommended crontab (KST, CRON_TZ=Asia/Seoul; operator-managed):
  30 8  * * 1-5  STOCK_LLM_CONTEXT=shadow  python -m scripts.analysis.llm_market_context
  0 9-15 * * 1-5 STOCK_LLM_CONTEXT=shadow  python -m scripts.analysis.llm_market_context
"""

from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger(__name__)


def _resolve_mode() -> str:
    """Return the cron mode from STOCK_LLM_CONTEXT (default 'off')."""
    return os.getenv("STOCK_LLM_CONTEXT", "off").strip().lower()


def _ensure_shadow_isolation(mode: str) -> None:
    """Fail-safe: in shadow, force TRADING_STATE_KEY_SUFFIX if the operator
    forgot it, so the publish can never clobber the orchestrator's live key."""
    if mode == "shadow" and not os.environ.get("TRADING_STATE_KEY_SUFFIX", "").strip():
        os.environ["TRADING_STATE_KEY_SUFFIX"] = "shadow"


async def run_once(mode: str) -> int:
    """Run a single market analysis and publish the context (or inert when off)."""
    if mode not in ("shadow", "live"):
        logger.info("STOCK_LLM_CONTEXT=%s (off) — inert, exiting", mode)
        return 0

    _ensure_shadow_isolation(mode)

    from services.trading.llm_context_publisher import LLMContextPublisher

    publisher = LLMContextPublisher("stock")
    context = await publisher.run_analysis()
    if context is not None:
        publisher.publish_to_redis(context)
        logger.info(
            "llm market context published mode=%s regime=%s confidence=%.2f",
            mode,
            context.regime,
            context.confidence,
        )
    else:
        logger.warning(
            "llm analysis returned None; skipping publish (mode=%s)", mode
        )
    return 0


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    return asyncio.run(run_once(_resolve_mode()))


if __name__ == "__main__":
    import sys

    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /tmp/m5b-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/scripts/test_llm_market_context.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
cd /tmp/m5b-impl
/home/deploy/project/kis_unified_sts/.venv/bin/black scripts/analysis/llm_market_context.py tests/unit/scripts/test_llm_market_context.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix scripts/analysis/llm_market_context.py tests/unit/scripts/test_llm_market_context.py
/home/deploy/project/kis_unified_sts/.venv/bin/mypy scripts/analysis/llm_market_context.py
git add scripts/analysis/llm_market_context.py tests/unit/scripts/test_llm_market_context.py
git commit -m "feat(m5b): standalone LLM market-context cron (shadow-first, default off)"
```
Note: mypy may report transitive errors from `services.trading.llm_context_publisher`'s imports — confirm NO errors attributable to `scripts/analysis/llm_market_context.py` itself.

---

## Task 2: Integration test — shadow publishes to the isolated key

**Files:**
- Test: `tests/integration/test_llm_market_context_cron.py`

Proves the REAL `publish_to_redis` path writes the `:shadow` key (never the live key) and that the dashboard/consumer reader can read it back — with OpenAI mocked and the SQLite ledger no-op'd.

- [ ] **Step 1: Write the test**

Create `tests/integration/test_llm_market_context_cron.py`:

```python
"""e2e: M5b cron shadow run -> trading:stock:market_context:shadow (live key untouched)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import fakeredis
import pytest

import scripts.analysis.llm_market_context as m
import shared.streaming.trading_state as ts
from services.trading import llm_context_publisher as lcp
from shared.llm.market_context import MarketContext
from shared.streaming.trading_state import TradingStateReader


@pytest.mark.asyncio
async def test_shadow_publishes_to_suffixed_key(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = fakeredis.FakeStrictRedis(db=1)
    monkeypatch.setattr(ts, "_get_redis", lambda: fake)
    monkeypatch.setenv("TRADING_STATE_KEY_SUFFIX", "")  # run_once forces 'shadow'

    ctx = MarketContext(regime="BULL_STRONG", confidence=0.8)
    monkeypatch.setattr(lcp.LLMContextPublisher, "run_analysis", AsyncMock(return_value=ctx))
    # no-op the SQLite ledger append so the test has no filesystem side effects
    monkeypatch.setattr(
        lcp.LLMContextPublisher, "_append_market_context_history", lambda self, c: None
    )

    rc = await m.run_once("shadow")
    assert rc == 0

    # shadow key written; live key untouched (orchestrator's dashboard safe)
    assert fake.exists("trading:stock:market_context:shadow") == 1
    assert fake.exists("trading:stock:market_context") == 0

    # the consumer's reader (with the suffix set) reads it back
    read = TradingStateReader("stock").get_market_context()
    assert read is not None
    assert read.regime == "BULL_STRONG"
    assert read.confidence == 0.8
```

- [ ] **Step 2: Run + iterate**

Run: `cd /tmp/m5b-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/integration/test_llm_market_context_cron.py -v`
Expected: PASS (1 passed). If `TradingStateReader.get_market_context()` returns None, confirm `_get_redis` is the correct patch target (both publisher's `publish_market_context` and the reader call the module-level `shared.streaming.trading_state._get_redis`). If `MarketContext.from_dict` round-trip drops `confidence`, inspect `shared/llm/market_context.py::to_dict`/`from_dict` and adjust the assertion to the round-trip-stable fields (regime is guaranteed).

- [ ] **Step 3: Commit**

```bash
cd /tmp/m5b-impl
/home/deploy/project/kis_unified_sts/.venv/bin/black tests/integration/test_llm_market_context_cron.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix tests/integration/test_llm_market_context_cron.py
git add tests/integration/test_llm_market_context_cron.py
git commit -m "test(m5b): e2e cron shadow -> market_context:shadow key, live untouched"
```

---

## Task 3: Full gate + crontab doc + PR

- [ ] **Step 1: Lint/format/type**

```bash
cd /tmp/m5b-impl
/home/deploy/project/kis_unified_sts/.venv/bin/black scripts/analysis/llm_market_context.py tests/unit/scripts/test_llm_market_context.py tests/integration/test_llm_market_context_cron.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check scripts/analysis/llm_market_context.py tests/unit/scripts/test_llm_market_context.py tests/integration/test_llm_market_context_cron.py
/home/deploy/project/kis_unified_sts/.venv/bin/mypy scripts/analysis/llm_market_context.py
```
Expected: clean (transitive import errors from services/shared are pre-existing and out of the `mypy shared/ domains/` gate scope).

- [ ] **Step 2: Targeted + regression**

```bash
cd /tmp/m5b-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/scripts/test_llm_market_context.py tests/integration/test_llm_market_context_cron.py -v
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -k "llm_context or trading_state" -q
```
Expected: all PASS (the second proves the untouched `LLMContextPublisher` + `trading_state` paths still work).

- [ ] **Step 3: Full gate (CI parity)**

```bash
cd /tmp/m5b-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -m "not serial" -n auto -q --ignore=tests/performance && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -m serial -q
```
Expected: green. (Watch for env leaks: the new tests use `monkeypatch.setenv("TRADING_STATE_KEY_SUFFIX","")` so the suffix is tracked and removed on teardown — verify no `trading_state` test fails after the M5b tests, the M5a lesson.)

- [ ] **Step 4: Push + PR**

```bash
cd /tmp/m5b-impl
git push -u origin feat/llm-context-cron-m5b
gh pr create --base main --head feat/llm-context-cron-m5b \
  --title "feat(m5b): standalone LLM market-context cron (shadow-first, default off)" \
  --body "$(cat <<'EOF'
## What
The second M5 sub-project: a market-hours-gated, single-shot cron
(`scripts/analysis/llm_market_context.py`) that runs the existing
`LLMContextPublisher("stock")` once per invocation and publishes
`trading:stock:market_context`. Extracts the orchestrator's 60-min in-loop LLM
publisher into a standalone job so the context survives the M5 cutover.

## Why
M4-P's `StrategyManager` already CONSUMES `trading:stock:market_context` (via
`LLMContextProvider`) — used by `mean_reversion`'s regime filter and `williams_r`.
But the only runtime PRODUCER is the orchestrator's background loop. M5b extracts
it so the decoupled stock pipeline keeps its LLM regime feed after cutover.

## Approach — cron, not a daemon
A periodic, stateless, market-hours-gated LLM job is a textbook cron (the project's
LLM briefings are all crons). Market-hours gating is the crontab's job — the
recommended schedule (operator-managed, `CRON_TZ=Asia/Seoul`) is 08:30 pre-market +
hourly 09:00–15:00 KST = 8 runs/weekday, ~65% fewer OpenAI calls than the
orchestrator's 24/7 loop, and after cutover M5b's 8/day REPLACES the orchestrator's
~24/day (net reduction):
```
30 8  * * 1-5  STOCK_LLM_CONTEXT=shadow  python -m scripts.analysis.llm_market_context
0 9-15 * * 1-5 STOCK_LLM_CONTEXT=shadow  python -m scripts.analysis.llm_market_context
```

## Shadow isolation
Shadow forces `TRADING_STATE_KEY_SUFFIX=shadow` (fail-safe) → publishes
`trading:stock:market_context:shadow`, never clobbering the orchestrator's live key
(side-by-side validation before M5d). `LLMContextPublisher`, the orchestrator, and
the consumer (`StrategyManager`/`LLMContextProvider`) are UNCHANGED — purely additive.

## Scope / limitations (v1)
Stock only (futures context = separate Phase-5 path). The M5d cutover flip (crontab→
live + orchestrator `market_context_publisher.enabled: false`) is separate. Cron is
short-lived so the publisher's Prometheus counters can't be scraped — observability is
logs + the SQLite ledger's latest `generated_at` freshness (Pushgateway = follow-up).

## How tested
Unit (mode routing, fail-safe shadow isolation, off-inert, shadow run+publish,
None-analysis skip — OpenAI mocked), integration (shadow → `:shadow` key, live key
untouched, reader round-trip), full `tests/` gate green, ruff/black clean.

Spec: `docs/superpowers/specs/2026-06-06-llm-context-cron-m5b-design.md`
Plan: `docs/superpowers/plans/archive/2026-06-06-llm-context-cron-m5b.md`

## Follow-ups
M5c (daily risk reset), M5d (cutover flip + runbook + rollback), M5e (orchestrator
reduction); futures market-context cron; Pushgateway metrics; document the crontab
entries in an ops runbook.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 5: Run code review** — `/code-review` on the PR and address findings.

---

## Self-Review (plan vs spec)

**Spec coverage:**
- §4.2 single-shot flow (mode gate → run_analysis → publish) → Task 1 `run_once`. ✓
- §4.3 testable structure (`_resolve_mode`/`_ensure_shadow_isolation`/`run_once`/`main`) → Task 1. ✓
- §4.4 crontab schedule → documented in the script docstring + PR body (Task 1/3). ✓
- §5.1 shadow isolation (fail-safe suffix) → Task 1 `_ensure_shadow_isolation` + Task 2 proves `:shadow` key. ✓
- §5.2 consumer unchanged → no modification; Task 2 reads back via `TradingStateReader`. ✓
- §6.1 error handling (None → skip + return 0) → Task 1 `run_once` + `test_run_once_none_analysis_skips_publish`. ✓
- §6.4 observability limitation → PR body note (cron / no prom scrape). ✓
- §7 testing (unit + integration + regression) → Tasks 1–3. ✓
- §8 acceptance (off-inert, shadow `:shadow`, live key, unchanged publisher/consumer, OpenAI mocked, no live-key clobber) → Tasks 1/2/3. ✓

**Placeholder scan:** none — complete code in every step.

**Type consistency:** `_resolve_mode() -> str`, `_ensure_shadow_isolation(mode) -> None`, `run_once(mode) -> int`, `main() -> int` consistent across tasks. The patch target `services.trading.llm_context_publisher.LLMContextPublisher` matches the lazy import in `run_once`. `LLMContextPublisher(asset_class)` + async `run_analysis()` + `publish_to_redis(ctx)` + `_append_market_context_history(self, ctx)` match `services/trading/llm_context_publisher.py`. `MarketContext(regime=, confidence=)` (all-defaulted dataclass) + `to_dict`/`from_dict` + `TradingStateReader("stock").get_market_context()` match `shared/llm/market_context.py` + `shared/streaming/trading_state.py`. `_get_redis` patch target correct (module-level, used by both publisher and reader). `TRADING_STATE_KEY_SUFFIX` tracked via `monkeypatch.setenv` (M5a env-leak lesson applied).

**Open questions resolved:** crontab times = 08:30 + hourly 09:00–15:00 (script docstring + PR); script test location = `tests/unit/scripts/` (established); no `--mode` CLI (env-only, YAGNI); crontab doc in PR body + a follow-up runbook note.
