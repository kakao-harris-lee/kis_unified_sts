#!/usr/bin/env python3
"""
LLM Intraday Refresh — Lightweight stock scoring every hour.

Runs a fast stock analysis pipeline (no backtest, DART, KSD, LLM scoring)
and publishes fresh quality scores to Redis for the fusion ranker.
When new stocks are discovered, sends a Telegram notification.

Cron: 0 10,11,12,13,14,15 * * 1-5
"""
import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.analysis.llm_job_common import configure_logger

logger = configure_logger(__name__)


def _load_previous_codes() -> set[str]:
    """Load final_codes from current Redis snapshot before refresh."""
    try:
        from shared.streaming.client import RedisClient

        raw = RedisClient.get_client().get("system:llm_quality:latest")
        if raw:
            return set(json.loads(raw).get("final_codes", []))
    except Exception as e:
        logger.warning(f"Failed to load previous codes: {e}")
    return set()


def _load_current_snapshot() -> dict:
    """Load the freshly updated Redis snapshot after refresh."""
    try:
        from shared.streaming.client import RedisClient

        raw = RedisClient.get_client().get("system:llm_quality:latest")
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.warning(f"Failed to load current snapshot: {e}")
    return {}


async def _notify_new_stocks(
    prev_codes: set[str], snapshot: dict
) -> None:
    """Send Telegram alert if new stocks appeared in the refresh."""
    new_codes = set(snapshot.get("final_codes", []))
    added = new_codes - prev_codes
    if not added:
        return

    names = snapshot.get("names", {})
    quality = snapshot.get("quality", {})

    lines = ["🔍 <b>LLM 장중 신규 발굴 종목</b>", ""]
    for code in sorted(added):
        name = names.get(code, code)
        score = quality.get(code, 0)
        lines.append(f"• {name} ({code}) — 품질 {score:.0%}")

    from shared.notification import notifier_for_domain

    notifier = notifier_for_domain("briefing")
    if notifier is None:
        logger.warning("Briefing Telegram channel not configured; intraday alert skipped")
        return
    await notifier.send_message("\n".join(lines))
    logger.info(f"Telegram alert sent for {len(added)} new stocks: {sorted(added)}")


async def main():
    from shared.calendar import is_market_open_today
    from shared.llm import run_unified_analysis

    logger.info("LLM Intraday Refresh Started")

    if not is_market_open_today():
        logger.info("Market closed today. Skipping.")
        return

    prev_codes = _load_previous_codes()

    stock_plans, _, _ = await run_unified_analysis(
        notifier=None,
        mode="stock",
        send_telegram=False,
        intraday=True,
    )
    logger.info(f"Intraday refresh complete: {len(stock_plans)} stocks scored")

    snapshot = _load_current_snapshot()
    await _notify_new_stocks(prev_codes, snapshot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        raise
