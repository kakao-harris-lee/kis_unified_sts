"""Stock cutover verification (M5d) — read-only decoupled-pipeline health check.

Confirms the decoupled stock pipeline (M4-P/R/O + M5a/b/c) is wired and fresh,
in SHADOW (pre-cutover gate) or LIVE (post-cutover check). Read-only: no key is
mutated. Returns exit 0 if all CRITICAL checks pass, 1 otherwise; warn-level
checks never fail the run. Process liveness (`docker compose ps`) is the runbook's
job — this script only inspects Redis.

Suffix rules (verified):
  streams      -> ".shadow" in shadow, "" in live   (M4 _streams_for)
  dashboard keys -> ":shadow" in shadow, "" in live  (TRADING_STATE_KEY_SUFFIX _key)
  daemon positions -> STOCK_POSITIONS_KEY or stock:daemon:positions, never suffixed
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

from shared.streaming.stock_keys import (
    DASHBOARD_STOCK_POSITIONS_KEY,
    stock_daemon_positions_key,
)

logger = logging.getLogger(__name__)

_KST = ZoneInfo("Asia/Seoul")

# (stream base, expected consumer group). Streams are suffixed per mode.
# M4-R reads candidates; M4-O reads finals; M5a monitor reads fills.
# (M4-X polls the positions hash — no group — so its liveness is compose-only.)
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
    """Extract group names from xinfo_groups output (str-keyed dicts, bytes-or-str values)."""
    names: set[str] = set()
    for g in groups:
        if isinstance(g, dict):
            raw = g.get("name")
            if raw is not None:
                names.add(_decode(raw))
    return names


async def _check_group(
    redis: Any, stream: str, group: str, *, critical: bool
) -> CheckResult:
    """Check that ``group`` exists as a consumer group on ``stream``."""
    try:
        groups = await redis.xinfo_groups(stream)
    except Exception as exc:
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
    """Check core (critical) and observability (warn) consumer groups are wired."""
    sfx = _stream_suffix(mode)
    results: list[CheckResult] = []
    for base, group in _CORE_GROUPS:
        results.append(await _check_group(redis, f"{base}{sfx}", group, critical=True))
    for base, group in _OBSERVABILITY_GROUPS:
        results.append(await _check_group(redis, f"{base}{sfx}", group, critical=False))
    return results


async def check_risk_freshness(redis: Any, now_kst: datetime) -> CheckResult:
    """Check the risk:state:stock daily counter was reset today (KST)."""
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
    """Check the market_context key is present and looks valid (warn-level)."""
    key = f"trading:stock:market_context{_key_suffix(mode)}"
    raw = await redis.get(key)
    ok = raw is not None and b"generated_at" in (
        raw if isinstance(raw, bytes) else raw.encode()
    )
    return CheckResult(
        name="market_context",
        ok=ok,
        critical=False,
        detail="present" if ok else f"{key} missing/invalid",
    )


async def check_positions(redis: Any, mode: str) -> CheckResult:
    """Surface dashboard and daemon open-position counts (warn-level)."""
    dashboard_key = f"{DASHBOARD_STOCK_POSITIONS_KEY}{_key_suffix(mode)}"
    daemon_key = stock_daemon_positions_key()
    try:
        dashboard_count = await redis.hlen(dashboard_key)
    except Exception:
        dashboard_count = 0
    try:
        daemon_count = await redis.hlen(daemon_key)
    except Exception:
        daemon_count = 0
    return CheckResult(
        name="positions",
        ok=True,
        critical=False,
        detail=(
            f"dashboard={dashboard_key} count={dashboard_count}; "
            f"daemon={daemon_key} count={daemon_count}"
        ),
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
    _client: Any = redis_client
    if _client is None:
        import redis.asyncio as aioredis

        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
        _client = aioredis.from_url(redis_url)

    try:
        results: list[CheckResult] = []
        results.extend(await check_streams(_client, mode))
        results.append(await check_risk_freshness(_client, now_kst))
        results.append(await check_market_context(_client, mode))
        results.append(await check_positions(_client, mode))
    finally:
        if owns_redis:
            await _client.aclose()

    critical_failed = False
    for r in results:
        level = "OK  " if r.ok else ("FAIL" if r.critical else "WARN")
        logger.info("[%s] %s — %s", level, r.name, r.detail)
        if r.critical and not r.ok:
            critical_failed = True

    rc = 1 if critical_failed else 0
    logger.info("verify mode=%s result=%s", mode, "FAIL" if rc else "PASS")
    return rc


def main() -> int:
    """CLI entry point: parse --mode and run the verification, returning its rc."""
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
