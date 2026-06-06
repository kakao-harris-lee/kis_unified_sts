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
    sfx = _stream_suffix(mode)
    results: list[CheckResult] = []
    for base, group in _CORE_GROUPS:
        results.append(await _check_group(redis, f"{base}{sfx}", group, critical=True))
    for base, group in _OBSERVABILITY_GROUPS:
        results.append(await _check_group(redis, f"{base}{sfx}", group, critical=False))
    return results


async def check_risk_freshness(redis: Any, now_kst: datetime) -> CheckResult:
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
    key = f"trading:stock:positions{_key_suffix(mode)}"
    try:
        count = await redis.hlen(key)
    except Exception:
        count = 0
    return CheckResult(
        name="positions",
        ok=True,
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
            await redis_client.aclose()  # type: ignore[union-attr]

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
