#!/usr/bin/env python3
"""
LLM Stock Screener - Nightly Analysis (21:00)

Runs unified trading analysis and sends results via Telegram.
Cron: 0 21 * * 1-5
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.llm import run_unified_analysis
from shared.notification import TelegramNotifier
from shared.calendar import is_market_open_today

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("LLM Nightly Analysis Started")

    if not is_market_open_today():
        logger.info("Market closed today. Skipping.")
        return

    try:
        notifier = TelegramNotifier()
        stock_plans, futures_plan, _ = await run_unified_analysis(
            notifier=notifier,
            mode='all',
            send_telegram=True
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
