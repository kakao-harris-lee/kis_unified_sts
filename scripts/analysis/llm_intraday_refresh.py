#!/usr/bin/env python3
"""
LLM Intraday Refresh — Lightweight stock scoring every 2 hours.

Runs a fast stock analysis pipeline (no backtest, DART, KSD, LLM scoring)
and publishes fresh quality scores to Redis for the fusion ranker.

Cron: 0 9,11,13,15 * * 1-5
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.analysis.llm_job_common import configure_logger

logger = configure_logger(__name__)


async def main():
    from shared.calendar import is_market_open_today
    from shared.llm import run_unified_analysis

    logger.info("LLM Intraday Refresh Started")

    if not is_market_open_today():
        logger.info("Market closed today. Skipping.")
        return

    stock_plans, _, _ = await run_unified_analysis(
        notifier=None,
        mode="stock",
        send_telegram=False,
        intraday=True,
    )
    logger.info(f"Intraday refresh complete: {len(stock_plans)} stocks scored")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        raise
