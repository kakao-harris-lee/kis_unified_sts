# Stock Stream Cutover (M5d) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The operator artifacts to flip stock paper trading from the monolithic orchestrator to the decoupled M4 pipeline + M5a/b/c: a read-only mode-aware verification script (`scripts/ops/stock_cutover_verify.py`), a rollback script (`scripts/ops/stock_cutover_rollback.sh`), and a gated runbook (`docs/runbooks/stock-pipeline-cutover-m5d.md`).

**Architecture:** No new trading code — the cutover is operational. `verify.py` confirms decoupled-pipeline health over Redis (stream consumer groups + risk-state freshness + market-context + positions), mode-aware (shadow checks `.shadow` streams / `:shadow` keys; live checks unsuffixed), returning exit 1 on any critical failure. `rollback.sh` stops the decoupled daemons and restores the orchestrator (idempotent, `--dry-run`). The runbook mirrors the futures Phase-5 pattern (gates → cutover sequence → rollback).

**Tech Stack:** Python 3.11+ asyncio + `redis.asyncio` (verify), `fakeredis.aioredis` (tests), bash + shellcheck (rollback), markdown (runbook).

**Spec:** `docs/superpowers/specs/2026-06-06-stock-stream-cutover-m5d-design.md`

**Worktree:** Implement in `/tmp/m5d-impl` (branch `feat/stock-stream-cutover-m5d`). Run venv tools from `cd /tmp/m5d-impl` using `/home/deploy/project/kis_unified_sts/.venv/bin/{pytest,black,ruff,mypy}`.

**PR strategy:** One PR (`feat/stock-stream-cutover-m5d`).

**Out of scope:** any M4/orchestrator/RuntimeRiskState change; a kill-switch consumer (manual `systemctl stop`); position migration (operator: flatten + abandon); residual paper-account cleanup (follow-up); M5e.

---

## File Structure & verified topology

**Create:**
- `scripts/ops/stock_cutover_verify.py` — read-only mode-aware health checker.
- `scripts/ops/stock_cutover_rollback.sh` — decoupled-stop + orchestrator-restore (idempotent, `--dry-run`).
- `docs/runbooks/stock-pipeline-cutover-m5d.md` — gated cutover runbook.
- `tests/unit/scripts/ops/test_stock_cutover_verify.py` — verify unit tests (create the dir; namespace package, no `__init__.py`).

**Modify:** none (purely additive).

**Verified facts (2026-06-06):**
- **Suffix asymmetry**: M4 STREAMS use a `.shadow` dot-suffix (`services/*/main.py::_streams_for`); dashboard KEYS use a `:shadow` colon-suffix (`shared/streaming/trading_state.py::_key` appends `:{suffix}`); `risk:state:stock`(+`:meta`) is **never suffixed** (`shared/risk/runtime_state.py:36`, no `TRADING_STATE_KEY_SUFFIX`).
- **Consumer groups**: `signal.candidate.stock{sfx}` → `stock_risk_filter` (M4-R); `signal.final.stock{sfx}` → `stock_order_router` (M4-O) [+ `stock_monitor`]; `order.fill.stock{sfx}` → `stock_monitor` (M5a). **M4-X (exit) does NOT use a consumer group** — it polls `trading:stock:positions` (`services/stock_exit/daemon.py:76`), so its liveness is via `systemctl is-active` (runbook) + `risk:state` freshness, NOT a stream group.
- `fakeredis.aioredis.FakeRedis(db=1)` supports `xadd`/`xgroup_create`/`xinfo_groups`; `xinfo_groups` returns a list of dicts (bytes keys/values, e.g. `{b'name': b'stock_risk_filter', ...}`); on a missing stream it raises.
- systemd units: `kis-stock-{strategy-daemon,risk-filter,order-router,exit-daemon}.service` + `kis-stock-monitor-daemon.service` (all DISABLED, `Environment=STOCK_*_DAEMON=shadow`). Orchestrator: `scripts/cron/stock_trading.sh {start,stop}`. Flatten: `scripts/trading/flatten_all.py`. `scripts/ops/` exists (`promote_live.sh` style).

---

## Task 1: Verification script + unit tests

**Files:**
- Create: `scripts/ops/stock_cutover_verify.py`
- Test: `tests/unit/scripts/ops/test_stock_cutover_verify.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/scripts/ops/test_stock_cutover_verify.py`:

```python
"""M5d cutover verify: stream groups + risk freshness + market_context, mode-aware."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import fakeredis.aioredis
import pytest

import scripts.ops.stock_cutover_verify as m

_KST = ZoneInfo("Asia/Seoul")


def _now() -> datetime:
    return datetime(2026, 6, 8, 10, 0, tzinfo=_KST)


async def _setup_healthy(redis, *, stream_sfx: str, key_sfx: str, reset_date: str) -> None:
    # the consumer groups a healthy pipeline has on each (suffixed) stream
    for stream, group in (
        (f"signal.candidate.stock{stream_sfx}", "stock_risk_filter"),
        (f"signal.final.stock{stream_sfx}", "stock_order_router"),
        (f"order.fill.stock{stream_sfx}", "stock_monitor"),
    ):
        await redis.xadd(stream, {"x": "1"})
        await redis.xgroup_create(stream, group, id="0")
    # risk state (NOT suffixed) + meta reset today
    await redis.hset("risk:state:stock", "daily_trade_count", "0")
    await redis.hset("risk:state:stock:meta", "last_reset_date_kst", reset_date)
    # market context (colon-suffixed key)
    await redis.set(
        f"trading:stock:market_context{key_sfx}",
        '{"regime": "NEUTRAL", "generated_at": "2026-06-08T01:00:00+00:00"}',
    )


@pytest.mark.asyncio
async def test_verify_shadow_healthy_returns_0() -> None:
    redis = fakeredis.aioredis.FakeRedis(db=1)
    await _setup_healthy(redis, stream_sfx=".shadow", key_sfx=":shadow", reset_date="2026-06-08")
    rc = await m.run_verify(mode="shadow", now_kst=_now(), redis_client=redis)
    assert rc == 0


@pytest.mark.asyncio
async def test_verify_live_healthy_returns_0() -> None:
    redis = fakeredis.aioredis.FakeRedis(db=1)
    await _setup_healthy(redis, stream_sfx="", key_sfx="", reset_date="2026-06-08")
    rc = await m.run_verify(mode="live", now_kst=_now(), redis_client=redis)
    assert rc == 0


@pytest.mark.asyncio
async def test_verify_missing_core_group_returns_1() -> None:
    redis = fakeredis.aioredis.FakeRedis(db=1)
    await _setup_healthy(redis, stream_sfx=".shadow", key_sfx=":shadow", reset_date="2026-06-08")
    # destroy the M4-O consumer group on the final stream -> critical failure
    await redis.xgroup_destroy("signal.final.stock.shadow", "stock_order_router")
    rc = await m.run_verify(mode="shadow", now_kst=_now(), redis_client=redis)
    assert rc == 1


@pytest.mark.asyncio
async def test_verify_stale_risk_reset_returns_1() -> None:
    redis = fakeredis.aioredis.FakeRedis(db=1)
    # reset date is yesterday -> M5c did not run today -> critical failure
    await _setup_healthy(redis, stream_sfx=".shadow", key_sfx=":shadow", reset_date="2026-06-05")
    rc = await m.run_verify(mode="shadow", now_kst=_now(), redis_client=redis)
    assert rc == 1


@pytest.mark.asyncio
async def test_verify_shadow_does_not_inspect_live_keys() -> None:
    redis = fakeredis.aioredis.FakeRedis(db=1)
    # only LIVE (unsuffixed) streams exist; shadow verify must still fail (looks at .shadow)
    await _setup_healthy(redis, stream_sfx="", key_sfx="", reset_date="2026-06-08")
    rc = await m.run_verify(mode="shadow", now_kst=_now(), redis_client=redis)
    assert rc == 1


@pytest.mark.asyncio
async def test_verify_missing_market_context_is_warn_not_fail() -> None:
    redis = fakeredis.aioredis.FakeRedis(db=1)
    await _setup_healthy(redis, stream_sfx=".shadow", key_sfx=":shadow", reset_date="2026-06-08")
    await redis.delete("trading:stock:market_context:shadow")  # warn-level, not critical
    rc = await m.run_verify(mode="shadow", now_kst=_now(), redis_client=redis)
    assert rc == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /tmp/m5d-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/scripts/ops/test_stock_cutover_verify.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement**

Create `scripts/ops/stock_cutover_verify.py`:

```python
"""Stock cutover verification (M5d) — read-only decoupled-pipeline health check.

Confirms the decoupled stock pipeline (M4-P/R/O + M5a/b/c) is wired and fresh,
in SHADOW (pre-cutover gate) or LIVE (post-cutover check). Read-only: no key is
mutated. Returns exit 0 if all CRITICAL checks pass, 1 otherwise; warn-level
checks never fail the run. Process liveness (systemctl is-active) is the runbook's
job — this script only inspects Redis.

Suffix rules (verified):
  streams      -> ".shadow" in shadow, "" in live   (M4 _streams_for)
  dashboard keys -> ":shadow" in shadow, "" in live  (TRADING_STATE_KEY_SUFFIX _key)
  risk:state:stock(+:meta) -> NEVER suffixed         (decoupled-only)

Usage:
  python -m scripts.ops.stock_cutover_verify --mode shadow
  python -m scripts.ops.stock_cutover_verify --mode live
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

_KST = ZoneInfo("Asia/Seoul")

# (stream base, expected consumer group). Streams are suffixed per mode.
# M4-R reads candidates; M4-O reads finals; M5a monitor reads fills.
# (M4-X polls the positions hash — no group — so its liveness is systemctl-only.)
_CORE_GROUPS: tuple[tuple[str, str], ...] = (
    ("signal.candidate.stock", "stock_risk_filter"),
    ("signal.final.stock", "stock_order_router"),
)
_OBSERVABILITY_GROUPS: tuple[tuple[str, str], ...] = (
    ("order.fill.stock", "stock_monitor"),
)


@dataclass
class CheckResult:
    name: str
    ok: bool
    critical: bool
    detail: str


def _stream_suffix(mode: str) -> str:
    return ".shadow" if mode == "shadow" else ""


def _key_suffix(mode: str) -> str:
    return ":shadow" if mode == "shadow" else ""


def _decode(value: Any) -> str:
    if isinstance(value, (bytes, bytearray)):
        return value.decode()
    return str(value)


def _group_names(groups: list[Any]) -> set[str]:
    """Extract group names from xinfo_groups output (bytes-or-str dict keys)."""
    names: set[str] = set()
    for g in groups:
        if isinstance(g, dict):
            raw = g.get("name", g.get(b"name"))
            if raw is not None:
                names.add(_decode(raw))
    return names


async def _check_group(
    redis: Any, stream: str, group: str, *, critical: bool
) -> CheckResult:
    try:
        groups = await redis.xinfo_groups(stream)
    except Exception as exc:  # missing stream or unreadable
        return CheckResult(
            name=f"group {group}@{stream}",
            ok=False,
            critical=critical,
            detail=f"stream missing/unreadable ({type(exc).__name__})",
        )
    present = group in _group_names(groups)
    return CheckResult(
        name=f"group {group}@{stream}",
        ok=present,
        critical=critical,
        detail="connected" if present else "consumer group absent",
    )


async def check_streams(redis: Any, mode: str) -> list[CheckResult]:
    sfx = _stream_suffix(mode)
    results: list[CheckResult] = []
    for base, group in _CORE_GROUPS:
        results.append(await _check_group(redis, f"{base}{sfx}", group, critical=True))
    for base, group in _OBSERVABILITY_GROUPS:
        results.append(await _check_group(redis, f"{base}{sfx}", group, critical=False))
    return results


async def check_risk_freshness(redis: Any, now_kst: datetime) -> CheckResult:
    # risk:state:stock is NEVER suffixed (decoupled-only).
    today = now_kst.date().isoformat()
    last = await redis.hget("risk:state:stock:meta", "last_reset_date_kst")
    last_str = _decode(last) if last is not None else None
    ok = last_str == today
    return CheckResult(
        name="risk:state:stock daily reset",
        ok=ok,
        critical=True,
        detail=f"last_reset_date_kst={last_str} (expected {today})",
    )


async def check_market_context(redis: Any, mode: str) -> CheckResult:
    key = f"trading:stock:market_context{_key_suffix(mode)}"
    raw = await redis.get(key)
    ok = raw is not None and b"generated_at" in (raw if isinstance(raw, bytes) else raw.encode())
    return CheckResult(
        name="market_context",
        ok=ok,
        critical=False,  # warn — M5b may be absent in some envs
        detail="present" if ok else f"{key} missing/invalid",
    )


async def check_positions(redis: Any, mode: str) -> CheckResult:
    key = f"trading:stock:positions{_key_suffix(mode)}"
    try:
        count = await redis.hlen(key)
    except Exception:
        count = 0
    return CheckResult(
        name="positions",
        ok=True,  # informational only
        critical=False,
        detail=f"{key} count={count}",
    )


async def run_verify(
    *, mode: str, now_kst: datetime | None = None, redis_client: Any | None = None
) -> int:
    """Run all checks; return 0 if every CRITICAL check passes, else 1."""
    if mode not in ("shadow", "live"):
        logger.error("unknown mode %r (expected shadow|live)", mode)
        return 1
    if now_kst is None:
        now_kst = datetime.now(_KST)

    owns_redis = redis_client is None
    if redis_client is None:
        import redis.asyncio as aioredis

        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
        redis_client = aioredis.from_url(redis_url)

    try:
        results: list[CheckResult] = []
        results.extend(await check_streams(redis_client, mode))
        results.append(await check_risk_freshness(redis_client, now_kst))
        results.append(await check_market_context(redis_client, mode))
        results.append(await check_positions(redis_client, mode))
    finally:
        if owns_redis:
            await redis_client.aclose()

    critical_failed = False
    for r in results:
        level = "OK " if r.ok else ("FAIL" if r.critical else "WARN")
        logger.info("[%s] %s — %s", level, r.name, r.detail)
        if r.critical and not r.ok:
            critical_failed = True

    rc = 1 if critical_failed else 0
    logger.info("verify mode=%s result=%s", mode, "FAIL" if rc else "PASS")
    return rc


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    parser = argparse.ArgumentParser(description="Stock cutover health verification")
    parser.add_argument("--mode", choices=("shadow", "live"), required=True)
    args = parser.parse_args()
    return asyncio.run(run_verify(mode=args.mode))


if __name__ == "__main__":
    import sys

    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /tmp/m5d-impl && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/scripts/ops/test_stock_cutover_verify.py -v`
Expected: PASS (6 passed). If `xinfo_groups` returns a different dict shape, adapt `_group_names` to the actual keys revealed (the test's `xgroup_create` setup is the source of truth).

- [ ] **Step 5: Format + mypy + commit**

```bash
cd /tmp/m5d-impl
/home/deploy/project/kis_unified_sts/.venv/bin/black scripts/ops/stock_cutover_verify.py tests/unit/scripts/ops/test_stock_cutover_verify.py
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check --fix scripts/ops/stock_cutover_verify.py tests/unit/scripts/ops/test_stock_cutover_verify.py
/home/deploy/project/kis_unified_sts/.venv/bin/mypy scripts/ops/stock_cutover_verify.py
git add scripts/ops/stock_cutover_verify.py tests/unit/scripts/ops/test_stock_cutover_verify.py
git commit -m "feat(m5d): stock cutover verification script (read-only, mode-aware)"
```
Note: confirm NO mypy errors attributable to `stock_cutover_verify.py` itself (transitive `redis`/stdlib stubs aside).

---

## Task 2: Rollback script

**Files:**
- Create: `scripts/ops/stock_cutover_rollback.sh`
- Test: a `--dry-run` assertion (Step 2) + shellcheck (Step 3)

- [ ] **Step 1: Implement the rollback script**

Create `scripts/ops/stock_cutover_rollback.sh`:

```bash
#!/usr/bin/env bash
# Stock cutover rollback (M5d): stop the decoupled stock pipeline and restore the
# monolithic orchestrator. Idempotent. Paper-only — no real-money side effects.
#
#   bash scripts/ops/stock_cutover_rollback.sh [--dry-run]
#
# --dry-run echoes every mutating command WITHOUT executing it (operator preview).
set -euo pipefail

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

REPO="/home/deploy/project/kis_unified_sts"
REDIS_DB="${REDIS_DB:-1}"
UNITS=(
  kis-stock-strategy-daemon
  kis-stock-risk-filter
  kis-stock-order-router
  kis-stock-exit-daemon
  kis-stock-monitor-daemon
)

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "DRY-RUN: $*"
  else
    echo "RUN: $*"
    "$@"
  fi
}

echo "== M5d rollback: decoupled stock pipeline -> orchestrator =="

# 1. Stop the decoupled daemons (idempotent; ignore not-loaded units).
for unit in "${UNITS[@]}"; do
  run systemctl stop "${unit}.service" || true
done

# 2. Abandon decoupled live positions (paper — the data is disposable).
run redis-cli -n "$REDIS_DB" del trading:stock:positions

# 3. Restore the orchestrator's LLM context publisher (it owns it again).
echo "NOTE: re-enable config/llm.yaml::market_context_publisher.enabled: true"
echo "NOTE: revert the M5b crontab entry STOCK_LLM_CONTEXT=live back to =shadow"

# 4. Restart the orchestrator stock process.
run bash "${REPO}/scripts/cron/stock_trading.sh" start

# 5. Verify the orchestrator came up.
if [[ "$DRY_RUN" -eq 0 ]]; then
  sleep 2
  if [[ -f "${REPO}/pids/stock_trading.pid" ]] && kill -0 "$(cat "${REPO}/pids/stock_trading.pid")" 2>/dev/null; then
    echo "OK: orchestrator stock process is up (pid $(cat "${REPO}/pids/stock_trading.pid"))"
  else
    echo "WARN: orchestrator pid not found/alive — check scripts/cron/stock_trading.sh logs"
  fi
fi

echo "== rollback complete (dry-run=${DRY_RUN}) =="
```

- [ ] **Step 2: Verify --dry-run is non-destructive**

Run:
```bash
cd /tmp/m5d-impl && chmod +x scripts/ops/stock_cutover_rollback.sh
bash scripts/ops/stock_cutover_rollback.sh --dry-run
```
Expected: every mutating line prints `DRY-RUN: systemctl stop ...` / `DRY-RUN: redis-cli ... del ...` / `DRY-RUN: bash .../stock_trading.sh start` and NOTHING executes (no systemctl/redis/process calls). Confirm no `RUN:` lines appear.

- [ ] **Step 3: shellcheck**

Run: `cd /tmp/m5d-impl && shellcheck scripts/ops/stock_cutover_rollback.sh` (if `shellcheck` is unavailable, run `bash -n scripts/ops/stock_cutover_rollback.sh` for a syntax check).
Expected: no errors. Fix any warnings (quote expansions, etc.).

- [ ] **Step 4: Commit**

```bash
cd /tmp/m5d-impl
git add scripts/ops/stock_cutover_rollback.sh
git commit -m "feat(m5d): stock cutover rollback script (idempotent, --dry-run)"
```

---

## Task 3: Runbook + full gate + PR

**Files:**
- Create: `docs/runbooks/stock-pipeline-cutover-m5d.md`

- [ ] **Step 1: Write the runbook**

Create `docs/runbooks/stock-pipeline-cutover-m5d.md`:

```markdown
# Runbook: Stock Stream Cutover (M5d)

Flip stock **paper** trading from the monolithic orchestrator to the decoupled M4
pipeline (M4-P → M4-R → M4-O → M4-X) + M5a monitor + M5b LLM context cron + M5c
daily risk reset cron. Paper→paper (VirtualBroker in both shadow and live; the only
difference is the stream suffix), so there is no real-money risk — the risks are
operational (silent stop, double-trading, no halt). Reversible via the rollback script.

Spec: `docs/superpowers/specs/2026-06-06-stock-stream-cutover-m5d-design.md`

## Gate 0 — Prerequisites
- M4-P/R/O/X + M5a monitor running in SHADOW (`systemctl status kis-stock-*`).
- M5b crontab (`STOCK_LLM_CONTEXT=shadow`) and M5c crontab (`scripts.maintenance.daily_risk_reset`) installed.
- Orchestrator stock running normally (`scripts/cron/stock_trading.sh status` / pid alive).
- Operator has read this runbook AND the rollback section.

## Gate 1 — Shadow validation (>= 3-5 trading days)
Each trading day:
- `python -m scripts.ops.stock_cutover_verify --mode shadow` → PASS (exit 0).
- M5a dashboard (`:shadow` keys) shows decoupled positions / fills / signals flowing.
- No unbounded stream backlog; no daemon crash (`systemctl status kis-stock-*`).
- (Optional) sanity-compare decoupled shadow paper trades vs orchestrator live paper
  trades — directional agreement only (different broker/timing, not an exact match).

## Gate 2 — Operator written approval
Record the date + a one-line shadow-validation summary before proceeding.

## Cutover sequence (run OFF-HOURS — after 16:00 KST or a weekend)
1. **Flatten + clear positions** (current paper data is disposable):
   - `python scripts/trading/flatten_all.py --asset stock`  (optional — close orchestrator positions)
   - `bash scripts/cron/stock_trading.sh stop`
   - Disable the orchestrator cron (comment out the `stock_trading.sh` + watchdog lines in the crontab) so the 5-min watchdog does not resurrect it.
   - `redis-cli -n 1 del trading:stock:positions`  (decoupled starts clean; M4-X skips no foreign records)
2. **Flip M4 daemons to live** (per unit, via systemd drop-in — keeps the repo-tracked unit unmodified):
   ```
   sudo mkdir -p /etc/systemd/system/kis-stock-strategy-daemon.service.d
   printf '[Service]\nEnvironment=STOCK_STRATEGY_DAEMON=live\n' | sudo tee /etc/systemd/system/kis-stock-strategy-daemon.service.d/live.conf
   # repeat for: kis-stock-risk-filter (STOCK_RISK_FILTER=live),
   #             kis-stock-order-router (STOCK_ORDER_ROUTER=live),
   #             kis-stock-exit-daemon (STOCK_EXIT_DAEMON=live)
   sudo systemctl daemon-reload
   sudo systemctl enable --now kis-stock-strategy-daemon kis-stock-risk-filter kis-stock-order-router kis-stock-exit-daemon
   ```
3. **Flip M5a/b/c to live**:
   - M5a: drop-in `Environment=STOCK_MONITOR_DAEMON=live` for `kis-stock-monitor-daemon`, `daemon-reload`, `systemctl restart kis-stock-monitor-daemon`.
   - M5b: change the crontab entry to `STOCK_LLM_CONTEXT=live`; set `config/llm.yaml::market_context_publisher.enabled: false`.
   - M5c: no change (mode-agnostic).
4. **Post-cutover verification**:
   - `python -m scripts.ops.stock_cutover_verify --mode live` → PASS (exit 0).
   - `systemctl is-active kis-stock-strategy-daemon kis-stock-risk-filter kis-stock-order-router kis-stock-exit-daemon kis-stock-monitor-daemon` → all `active`.
   - Watch the first 09:00 KST session on the M5a dashboard (live keys): positions/fills appear.

## Rollback triggers
Roll back if ANY of: `verify --mode live` fails; no fills flowing for >10 min during
market hours while signals are present; a stream backlog grows unbounded; a daemon
crash-loops; M5a emits a health-anomaly Telegram alert.

## Rollback
```
bash scripts/ops/stock_cutover_rollback.sh --dry-run   # preview
bash scripts/ops/stock_cutover_rollback.sh             # execute
```
Then: re-enable `config/llm.yaml::market_context_publisher.enabled: true`, revert the
M5b crontab to `STOCK_LLM_CONTEXT=shadow`, re-enable the orchestrator cron, and confirm
`verify --mode shadow` + orchestrator pid alive.

## Notes
- Residual positions in the paper (KIS mock) account from the orchestrator are a
  documented FOLLOW-UP cleanup — out of M5d scope (operator decision: current paper
  data is disposable).
- A decoupled-pipeline kill-switch consumer is deferred; the paper-grade halt is
  `systemctl stop kis-stock-*`.
```

- [ ] **Step 2: Lint/format/type + targeted**

```bash
cd /tmp/m5d-impl
/home/deploy/project/kis_unified_sts/.venv/bin/ruff check scripts/ops/stock_cutover_verify.py tests/unit/scripts/ops/test_stock_cutover_verify.py
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/unit/scripts/ops/test_stock_cutover_verify.py -v
```
Expected: clean + 6 PASS.

- [ ] **Step 3: Full gate (CI parity)**

```bash
cd /tmp/m5d-impl
/home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -m "not serial" -n auto -q --ignore=tests/performance && /home/deploy/project/kis_unified_sts/.venv/bin/pytest tests/ -m serial -q
```
Expected: green (M5d is additive — scripts + doc only — so no regression).

- [ ] **Step 4: Commit runbook + push + PR**

```bash
cd /tmp/m5d-impl
git add docs/runbooks/stock-pipeline-cutover-m5d.md
git commit -m "docs(m5d): stock stream cutover runbook (gates, sequence, rollback)"
git push -u origin feat/stock-stream-cutover-m5d
gh pr create --base main --head feat/stock-stream-cutover-m5d \
  --title "feat(m5d): stock stream cutover — runbook + verify + rollback" \
  --body "$(cat <<'EOF'
## What
The fourth M5 sub-project: the operator artifacts to flip stock **paper** trading
from the monolithic orchestrator to the decoupled M4 pipeline + M5a/b/c —
a read-only mode-aware verification script (`scripts/ops/stock_cutover_verify.py`),
an idempotent rollback script (`scripts/ops/stock_cutover_rollback.sh`), and a gated
runbook (`docs/runbooks/stock-pipeline-cutover-m5d.md`).

## Why
M4-P/R/O/X + M5a/b/c are all built and running shadow. M5d is the cutover itself —
a gated, reversible procedure with automated health verification.

## Paper→paper, no real-money risk
M4-O executes via VirtualBroker (in-memory paper) in BOTH shadow and live; the only
difference is the stream suffix (`.shadow` vs unsuffixed). So the cutover carries no
real-money risk — the risks are operational (silent stop, double-trade, no halt), which
the verify script + runbook gates + rollback address.

## Approach — no new trading code
`verify.py` (read-only) checks the decoupled pipeline over Redis: M4 stream consumer
groups (`stock_risk_filter`@candidate, `stock_order_router`@final, `stock_monitor`@fill),
`risk:state:stock` daily-reset freshness (M5c ran today), market_context (M5b, warn-level),
positions. Mode-aware: shadow inspects `.shadow` streams + `:shadow` keys; live inspects
unsuffixed. (Note the suffix asymmetry — streams use `.shadow`, dashboard keys use
`:shadow`, `risk:state` is never suffixed.) `rollback.sh` stops the decoupled daemons +
clears positions + restarts the orchestrator (idempotent, `--dry-run`). The runbook
mirrors the futures Phase-5 gate pattern.

## Position handling
Current paper data is disposable (operator decision): at cutover, flatten + `del
trading:stock:positions` → decoupled starts clean (M4-X skips no foreign records). No
migration. Residual paper-account positions = documented follow-up.

## Scope / limitations
M4/orchestrator/RuntimeRiskState UNCHANGED (diff is 3 new files + 1 test). The actual
cutover is an operator action gated on shadow validation + written approval — this PR
ships the artifacts, not the flip. A decoupled kill-switch consumer is deferred (manual
`systemctl stop` is the paper-grade halt).

## How tested
verify.py unit tests over `fakeredis.aioredis` (shadow/live healthy → 0; missing core
group → 1; stale risk reset → 1; shadow ignores live keys; missing market_context →
warn not fail), rollback.sh `--dry-run` non-destructive + shellcheck, full `tests/`
gate green.

Spec: `docs/superpowers/specs/2026-06-06-stock-stream-cutover-m5d-design.md`
Plan: `docs/superpowers/plans/archive/2026-06-06-stock-stream-cutover-m5d.md`

## Follow-ups
M5e (orchestrator reduction to supervisor/health, after the cutover proves stable);
decoupled kill-switch consumer; residual paper-account cleanup; document the M5b/M5c/M5d
crontab + drop-ins in a consolidated ops runbook.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 5: Run code review** — `/code-review` on the PR and address findings.

---

## Self-Review (plan vs spec)

**Spec coverage:**
- §5.1 verify.py (mode-aware read-only; stream groups / risk freshness / market_context / positions; critical→exit 1; now_kst injectable; Redis-only) → Task 1 + 6 tests. ✓
- §5.2 rollback.sh (`--dry-run`, shellcheck, idempotent stop+restore) → Task 2. ✓
- §5.3 / §6 runbook (Gate 0-2 + cutover sequence + rollback triggers/procedure + position handling) → Task 3. ✓
- §4 position handling (`del trading:stock:positions` + fresh; residual=follow-up) → runbook cutover step 1 + rollback step 2 + Notes. ✓
- §8 acceptance (verify mode-aware/critical/now_kst/Redis-only; rollback dry-run/shellcheck/idempotent; runbook gates+sequence+rollback+position; M4/orchestrator unchanged; verify unit tests + rollback dry-run/shellcheck) → Tasks 1-3. ✓

**Placeholder scan:** none — complete code/script/runbook in every step.

**Type consistency:** `run_verify(*, mode, now_kst=None, redis_client=None) -> int`, `CheckResult(name, ok, critical, detail)`, `_stream_suffix`/`_key_suffix`/`_group_names`/`check_streams`/`check_risk_freshness`/`check_market_context`/`check_positions` consistent between script and tests. The suffix asymmetry (`.shadow` streams / `:shadow` keys / unsuffixed risk:state) is applied uniformly. The test's `_setup_healthy(stream_sfx, key_sfx, reset_date)` matches the script's suffix functions. Consumer-group topology (`stock_risk_filter`/`stock_order_router` critical, `stock_monitor` observability; M4-X has no group) matches the verified daemon code. `redis_client` param avoids shadowing the lazily-imported `redis.asyncio`.

**Open questions resolved:** verify location `scripts/ops/` + test `tests/unit/scripts/ops/` (new dir, namespace package); market_context = warn (not critical, avoids false fail when M5b absent); `--strict` recency gate omitted (YAGNI for v1); live drop-in (repo-tracked unit unmodified); rollback reverts to shadow (re-cutover easy).
