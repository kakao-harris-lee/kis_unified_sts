#!/usr/bin/env python3
"""
LLM Pre-Market Briefing (08:30)

Sends morning briefing with stock and futures recommendations.
Cron: 30 8 * * 1-5
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
    logger.info("Pre-Market Briefing Started")

    if not is_market_open_today():
        logger.info("Market closed today. Skipping.")
        return

    try:
        notifier = TelegramNotifier()
        await notifier.send_message(
            "<b>🌅 장전 최종 브리핑</b>\n━━━━━━━━━━━━━━━━━━━━",
            is_critical=True
        )
        stock_plans, futures_plan, _ = await run_unified_analysis(
            notifier=notifier,
            mode='all',
            send_telegram=True
        )
        logger.info(f"Complete: {len(stock_plans)} recommendations")
    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
