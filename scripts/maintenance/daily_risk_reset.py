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


async def reset_asset(
    redis_client: Any, asset_class: str, *, now_kst: datetime
) -> bool:
    """Reset one asset's daily counters if not already reset today.

    Returns True if a reset was performed, False if skipped (already reset for
    this KST date). Reuses the unchanged RuntimeRiskState semantics.
    """
    from shared.risk.runtime_state import RuntimeRiskState

    state = RuntimeRiskState(redis=redis_client, asset_class=asset_class)
    if not await state.should_reset_daily(now_kst=now_kst):
        logger.info(
            "%s already reset today (%s); skipping", asset_class, now_kst.date()
        )
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
    _client: Any = redis_client  # widen to Any so mypy won't narrow .aclose()
    if _client is None:
        import redis.asyncio as aioredis

        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/1")
        _client = aioredis.from_url(redis_url)

    rc = 0
    try:
        for asset in _assets():
            try:
                await reset_asset(_client, asset, now_kst=now_kst)
            except Exception:
                logger.exception("daily risk reset failed asset=%s", asset)
                rc = 1
    finally:
        if owns_redis:
            await _client.aclose()
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
