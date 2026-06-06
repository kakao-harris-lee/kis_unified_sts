# Daily Risk Reset Cron (M5c) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A small idempotent single-shot cron (`scripts/maintenance/daily_risk_reset.py`) that calls the existing `RuntimeRiskState.reset_daily()` for stock + futures at the KST session boundary, so the decoupled M4 pipeline's daily risk counters (`daily_trade_count`, `daily_pnl_krw`) actually reset each trading day.

**Architecture:** A thin standalone caller. `run_reset(now_kst)` loops `("stock", "futures")`; per asset it constructs the **unchanged** `RuntimeRiskState(redis, asset_class=asset)` and, guarded by `should_reset_daily()` (so a mid-day re-run never wipes the session's counters), calls `reset_daily()`. Per-asset try/except isolates failures; any failure → exit 1 (operator cron-mail). No shadow/live mode (the `risk:state:{asset}` keys are decoupled-pipeline-only — the orchestrator uses a separate in-memory RiskManager, so there's no live key to clobber). Market-day gating is the crontab's job.

**Tech Stack:** Python 3.11+, asyncio, `redis.asyncio` (prod), `fakeredis.aioredis` (tests), `zoneinfo`, pytest.

**Spec:** `docs/superpowers/specs/2026-06-06-daily-risk-reset-cron-m5c-design.md`

**Worktree:** Implement in the isolated worktree `/tmp/m5c-impl` (branch `feat/daily-risk-reset-cron-m5c`) — the operator is concurrently using the main repo dir. Run venv tools from `cd /tmp/m5c-impl` using absolute paths: `/home/deploy/project/kis_unified_sts/.venv/bin/{pytest,black,ruff,mypy}`.

**PR strategy:** Land as **one PR** (`feat/daily-risk-reset-cron-m5c`).

**Out of scope:** any change to `RuntimeRiskState`/the M4 daemons/the orchestrator; resetting `consecutive_losses`/`weekly_pnl_krw` (preserved); a shadow/live mode gate; snapshot/rollover; a daemon / Prometheus pull endpoint.

---

## File Structure

**Create:**
- `scripts/maintenance/daily_risk_reset.py` — the cron script (`_assets`, `reset_asset`, `run_reset`, `main`).
- `tests/unit/scripts/maintenance/test_daily_risk_reset.py` — unit tests (reset+preserve, idempotent-skip, both assets, per-asset error isolation).

**Modify:** none (M5c is purely additive — `RuntimeRiskState`, the M4 daemons, and the orchestrator are unchanged).

**Verified facts:**
- `RuntimeRiskState(*, redis, asset_class="futures")` (keyword-only); `async reset_daily(*, now_kst: datetime)` zeros `daily_pnl_krw`+`daily_trade_count` and sets `risk:state:{asset}:meta` `last_reset_date_kst`; `async should_reset_daily(*, now_kst: datetime) -> bool`. Public mutators for test setup: `async record_trade(*, pnl_krw)` (incr daily_pnl_krw, weekly_pnl_krw, daily_trade_count), `async record_loss()` (incr consecutive_losses); `async snapshot() -> RiskStateSnapshot`.
- `RiskStateSnapshot` fields: `daily_pnl_krw`, `weekly_pnl_krw`, `consecutive_losses`, `daily_trade_count`, `atr_90th_percentile`.
- redis is an **async** client; M4 builds `redis.asyncio.from_url(...)`. Tests use `fakeredis.aioredis.FakeRedis(db=1)` (the existing `tests/unit/risk/test_runtime_state.py` pattern).
- `scripts.maintenance` + `tests/unit/scripts/maintenance/` exist (implicit namespace packages).

---

## Task 1: Cron script + unit tests

**Files:**
- Create: `scripts/maintenance/daily_risk_reset.py`
- Test: `tests/unit/scripts/maintenance/test_daily_risk_reset.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/scripts/maintenance/test_daily_risk_reset.py`:

```python
"""M5c daily risk reset: zero daily counters, preserve cumulative, idempotent, isolate."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import fakeredis.aioredis
import pytest

import scripts.maintenance.daily_risk_reset as m
from shared.risk.runtime_state import RuntimeRiskState

_KST = ZoneInfo("Asia/Seoul")


def _kst_open(year: int, month: int, day: int) -> datetime:
    """08:59 KST on the given date (1 min before the 09:00 session open)."""
    return datetime(year, month, day, 8, 59, tzinfo=_KST)


def _decode(value: object) -> str | None:
    if isinstance(value, (bytes, bytearray)):
        return value.decode()
    return None if value is None else str(value)


@pytest.mark.asyncio
async def test_reset_zeros_daily_preserves_cumulative() -> None:
    redis = fakeredis.aioredis.FakeRedis(db=1)
    rs = RuntimeRiskState(redis=redis, asset_class="stock")
    await rs.record_trade(pnl_krw=-5000.0)
    await rs.record_trade(pnl_krw=3000.0)
    await rs.record_loss()  # consecutive_losses -> 1

    now = _kst_open(2026, 6, 8)
    did_reset = await m.reset_asset(redis, "stock", now_kst=now)

    assert did_reset is True
    snap = await rs.snapshot()
    assert snap.daily_trade_count == 0  # reset
    assert snap.daily_pnl_krw == 0.0  # reset
    assert snap.consecutive_losses == 1  # PRESERVED
    assert snap.weekly_pnl_krw == -2000.0  # PRESERVED
    meta = await redis.hget("risk:state:stock:meta", "last_reset_date_kst")
    assert _decode(meta) == "2026-06-08"


@pytest.mark.asyncio
async def test_reset_idempotent_does_not_wipe_midsession() -> None:
    redis = fakeredis.aioredis.FakeRedis(db=1)
    rs = RuntimeRiskState(redis=redis, asset_class="stock")
    now = _kst_open(2026, 6, 8)

    assert await m.reset_asset(redis, "stock", now_kst=now) is True
    # a trade lands after the morning reset
    await rs.record_trade(pnl_krw=1000.0)
    # a second run on the SAME KST day must SKIP — never wipe the day's counters
    did_reset = await m.reset_asset(redis, "stock", now_kst=now)

    assert did_reset is False
    snap = await rs.snapshot()
    assert snap.daily_trade_count == 1  # NOT wiped
    assert snap.daily_pnl_krw == 1000.0  # NOT wiped


@pytest.mark.asyncio
async def test_run_reset_resets_both_assets() -> None:
    redis = fakeredis.aioredis.FakeRedis(db=1)
    now = _kst_open(2026, 6, 8)

    rc = await m.run_reset(now_kst=now, redis_client=redis)

    assert rc == 0
    for asset in ("stock", "futures"):
        meta = await redis.hget(f"risk:state:{asset}:meta", "last_reset_date_kst")
        assert _decode(meta) == "2026-06-08"


@pytest.mark.asyncio
async def test_run_reset_isolates_per_asset_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = fakeredis.aioredis.FakeRedis(db=1)
    now = _kst_open(2026, 6, 8)
    attempted: list[str] = []

    async def fake_reset_asset(r: object, asset: str, *, now_kst: datetime) -> bool:
        attempted.append(asset)
        if asset == "futures":
            raise RuntimeError("redis down for futures")
        return True

    monkeypatch.setattr(m, "reset_asset", fake_reset_asset)

    rc = await m.run_reset(now_kst=now, redis_client=redis)

    assert rc == 1  # any asset failure -> exit 1 (cron-mail)
    assert attempted == ["stock", "futures"]  # both attempted (isolation)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /tmp/m5c-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/scripts/maintenance/test_daily_risk_reset.py -v`
Expected: FAIL (ModuleNotFoundError: scripts.maintenance.daily_risk_reset).

- [ ] **Step 3: Implement**

Create `scripts/maintenance/daily_risk_reset.py`:

```python
"""Daily risk-counter reset cron (M5c).

Resets the decoupled M4 pipeline's per-day risk counters
(``daily_trade_count`` / ``daily_pnl_krw`` in ``risk:state:{asset}``) at the KST
session boundary by calling the existing ``RuntimeRiskState.reset_daily()`` for
stock + futures. Cumulative fields (``consecutive_losses`` / ``weekly_pnl_krw``)
are preserved. A ``should_reset_daily()`` guard makes the run idempotent — a
mid-day re-run skips, never wiping the session's accumulated counters.

No shadow/live mode: ``risk:state:{asset}`` is written/read only by the decoupled
M4 daemons (the orchestrator uses a separate in-memory RiskManager), so there is
no live key to clobber. Market-day gating is the crontab's job.

Recommended crontab (KST, CRON_TZ=Asia/Seoul; operator-managed):
  59 8 * * 1-5  /home/deploy/project/kis_unified_sts/.venv/bin/python -m scripts.maintenance.daily_risk_reset
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

_KST = ZoneInfo("Asia/Seoul")


def _assets() -> tuple[str, ...]:
    """Asset classes whose daily risk counters M5c resets (idempotent / harmless)."""
    return ("stock", "futures")


async def reset_asset(redis_client: Any, asset_class: str, *, now_kst: datetime) -> bool:
    """Reset one asset's daily counters if not already reset today.

    Returns True if a reset was performed, False if skipped (already reset for
    this KST date). Reuses the unchanged RuntimeRiskState semantics.
    """
    from shared.risk.runtime_state import RuntimeRiskState

    state = RuntimeRiskState(redis=redis_client, asset_class=asset_class)
    if not await state.should_reset_daily(now_kst=now_kst):
        logger.info("%s already reset today (%s); skipping", asset_class, now_kst.date())
        return False
    await state.reset_daily(now_kst=now_kst)
    logger.info("reset %s daily risk counters (date=%s)", asset_class, now_kst.date())
    return True


async def run_reset(
    *, now_kst: datetime | None = None, redis_client: Any | None = None
) -> int:
    """Reset every asset's daily counters; return 0 if all ok, 1 if any failed.

    Per-asset failures are isolated (one asset's error does not block the others)
    but yield a non-zero exit so the operator's cron-mail surfaces a failed reset.
    """
    if now_kst is None:
        now_kst = datetime.now(_KST)

    owns_redis = redis_client is None
    if redis_client is None:
        import redis.asyncio as aioredis

        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
        redis_client = aioredis.from_url(redis_url)

    rc = 0
    try:
        for asset in _assets():
            try:
                await reset_asset(redis_client, asset, now_kst=now_kst)
            except Exception:
                logger.exception("daily risk reset failed asset=%s", asset)
                rc = 1
    finally:
        if owns_redis:
            await redis_client.aclose()
    return rc


def main() -> int:
    """Entry point: configure logging, reset all assets, return the exit code."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    return asyncio.run(run_reset())


if __name__ == "__main__":
    import sys

    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /tmp/m5c-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/scripts/maintenance/test_daily_risk_reset.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Format + mypy + commit**

```bash
cd /tmp/m5c-impl
/home/deploy/project/kis_unified_sts/.venv/bin/black scripts/maintenance/daily_risk_reset.py tests/unit/scripts/maintenance/test_daily_risk_reset.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix scripts/maintenance/daily_risk_reset.py tests/unit/scripts/maintenance/test_daily_risk_reset.py
/home/deploy/project/kis_unified_sts/.venv/bin/mypy scripts/maintenance/daily_risk_reset.py
git add scripts/maintenance/daily_risk_reset.py tests/unit/scripts/maintenance/test_daily_risk_reset.py
git commit -m "feat(m5c): daily risk reset cron (idempotent, stock+futures)"
```
Note: mypy may report transitive errors from `shared.risk.runtime_state`'s imports — confirm NO errors attributable to `scripts/maintenance/daily_risk_reset.py` itself.

---

## Task 2: Full gate + crontab doc + PR

- [ ] **Step 1: Lint/format/type + targeted + regression**

```bash
cd /tmp/m5c-impl
/home/deploy/project/kis_unified_sts/.venv/bin/black scripts/maintenance/daily_risk_reset.py tests/unit/scripts/maintenance/test_daily_risk_reset.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check scripts/maintenance/daily_risk_reset.py tests/unit/scripts/maintenance/test_daily_risk_reset.py
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/scripts/maintenance/test_daily_risk_reset.py tests/unit/risk/test_runtime_state.py -v
```
Expected: clean + all PASS (the second file proves the untouched `RuntimeRiskState` still works).

- [ ] **Step 2: Full gate (CI parity)**

```bash
cd /tmp/m5c-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -m "not serial" -n auto -q --ignore=tests/performance && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -m serial -q
```
Expected: green.

- [ ] **Step 3: Push + PR**

```bash
cd /tmp/m5c-impl
git push -u origin feat/daily-risk-reset-cron-m5c
gh pr create --base main --head feat/daily-risk-reset-cron-m5c \
  --title "feat(m5c): daily risk reset cron (idempotent, stock+futures)" \
  --body "$(cat <<'EOF'
## What
The third M5 sub-project: a small idempotent cron
(`scripts/maintenance/daily_risk_reset.py`) that calls the existing
`RuntimeRiskState.reset_daily()` for stock + futures at the KST session boundary,
so the decoupled M4 pipeline's daily risk counters reset each trading day.

## Why
`RuntimeRiskState` (Redis `risk:state:{asset}`) already has `reset_daily()` +
`should_reset_daily()`, but **nothing calls them** — so `daily_trade_count` /
`daily_pnl_krw` accumulate forever and M4-R's `DailyTradeCountFilter` /
`DailyMDDFilter` block all entries permanently after N trades. M5c provides the
missing scheduled reset. This is needed as soon as the M4 shadow pipeline runs
(so the daily gating validates over multiple days), not just at cutover.

## Approach — cron, no mode
A once-a-day idempotent reset is a textbook cron. Unlike M5a/M5b, there is **no
shadow/live mode**: `risk:state:{asset}` is written/read only by the decoupled M4
daemons (M4-X writes, M4-R/kill_switch read); the orchestrator uses a separate
in-memory RiskManager and never touches this key (verified by grep), so there is
no live key to clobber. The crontab entry is the opt-in:
```
59 8 * * 1-5  /home/deploy/project/kis_unified_sts/.venv/bin/python -m scripts.maintenance.daily_risk_reset
```
(08:59 KST Mon–Fri — after the 08:55 daemon start, before the 09:00 open.)

## Safety
`should_reset_daily()` guards each reset, so a mid-day re-run (accidental cron,
manual, restart) SKIPS rather than wiping the session's accumulated counters.
`consecutive_losses` and `weekly_pnl_krw` are preserved (only the daily counters
reset). Per-asset try/except isolates failures; any failure → exit 1 (cron-mail),
because a stale reset would mis-gate M4-R next session. `RuntimeRiskState`, the M4
daemons, and the orchestrator are UNCHANGED — the diff is 2 new files.

## How tested
Unit over `fakeredis.aioredis` (reset zeros daily + preserves cumulative + sets
meta; idempotent re-run does NOT wipe mid-session counters; both assets reset;
per-asset error isolation → exit 1), regression (`test_runtime_state.py` still
green), full `tests/` gate green, ruff/black clean. Implemented subagent-driven in
an isolated worktree.

Spec: `docs/superpowers/specs/2026-06-06-daily-risk-reset-cron-m5c-design.md`
Plan: `docs/superpowers/plans/2026-06-06-daily-risk-reset-cron-m5c.md`

## Follow-ups
M5d (cutover flip + runbook + rollback), M5e (orchestrator reduction); document the
crontab entries (M5b + M5c) in an ops runbook; consider an ops-monitor freshness
check on `risk:state:{asset}:meta::last_reset_date_kst`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: Run code review** — `/code-review` on the PR and address findings.

---

## Self-Review (plan vs spec)

**Spec coverage:**
- §5.2 flow (loop assets, should_reset guard → reset_daily, per-asset try/except, rc) → Task 1 `run_reset`/`reset_asset`. ✓
- §5.3 idempotency guard → Task 1 `reset_asset` + `test_reset_idempotent_does_not_wipe_midsession`. ✓
- §5.4 structure (`_assets`/`reset_asset`/`run_reset`/`main`) → Task 1. ✓
- §5.5 crontab schedule → script docstring + PR body. ✓
- §6.1 error handling (per-asset isolation, any failure → exit 1) → Task 1 `run_reset` + `test_run_reset_isolates_per_asset_failure`. ✓
- §7 testing (reset+preserve, idempotent, both assets, isolation, regression) → Tasks 1–2. ✓
- §8 acceptance (zero daily + preserve cumulative + meta; idempotent; per-asset isolation/exit 1; unchanged RuntimeRiskState/M4/orchestrator; crontab doc; redis-only/now_kst injectable) → Tasks 1/2. ✓

**Placeholder scan:** none — complete code in every step.

**Type consistency:** `_assets() -> tuple[str, ...]`, `reset_asset(redis_client, asset_class, *, now_kst) -> bool`, `run_reset(*, now_kst=None, redis_client=None) -> int`, `main() -> int` consistent across script + tests. `RuntimeRiskState(*, redis, asset_class)` + `async reset_daily(*, now_kst)` / `should_reset_daily(*, now_kst)` / `record_trade(*, pnl_krw)` / `record_loss()` / `snapshot()` + `RiskStateSnapshot.{daily_pnl_krw,daily_trade_count,consecutive_losses,weekly_pnl_krw}` match `shared/risk/runtime_state.py` + `shared/risk/state.py`. The `redis_client` param name avoids shadowing the lazily-imported `redis.asyncio` module. Tests use `fakeredis.aioredis.FakeRedis(db=1)` (the existing risk-test pattern) and `monkeypatch.setattr(m, "reset_asset", ...)` (module-global, which `run_reset` calls).

**Open questions resolved:** crontab time = 08:59 KST (after 08:55 daemon start, before 09:00 open); test location = `tests/unit/scripts/maintenance/` (exists); `_assets()` hardcoded (YAGNI); crontab doc in PR body + ops-runbook follow-up.
