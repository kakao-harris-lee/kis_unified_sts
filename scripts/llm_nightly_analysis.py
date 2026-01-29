#!/usr/bin/env python3
"""
LLM Stock Screener - Nightly Analysis (21:00)

Runs unified trading analysis and sends results via Telegram.
Cron: 0 21 * * 1-5
"""
import asyncio
import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from shared.llm.llm_analyzer import run_unified_analysis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("LLM Nightly Analysis Started")

    try:
        # Import notifier if available
        notifier = None
        try:
            from shared.notification import TelegramNotifier

            notifier = TelegramNotifier()
        except ImportError:
            logger.warning("TelegramNotifier not available, running without notifications")

        stock_plans, futures_plan, _ = await run_unified_analysis(
            notifier=notifier, mode="all", send_telegram=notifier is not None
        )

        logger.info(
            f"Complete: {len(stock_plans)} stocks, "
            f"futures={futures_plan.direction if futures_plan else 'N/A'}"
        )

    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
