#!/usr/bin/env python3
"""
LLM Pre-Market Briefing (08:30)

Sends morning briefing with stock and futures recommendations.
Cron: 30 8 * * 1-5
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


def is_market_open_today() -> bool:
    """Check if market is open today (simple weekday check)."""
    from datetime import datetime

    today = datetime.now()
    # Monday=0, Sunday=6
    return today.weekday() < 5


async def main():
    logger.info("Pre-Market Briefing Started")

    if not is_market_open_today():
        logger.info("Market closed today. Skipping.")
        return

    try:
        # Import notifier if available
        notifier = None
        try:
            from shared.notification import TelegramNotifier

            notifier = TelegramNotifier()
            await notifier.send_message(
                "<b>🌅 장전 최종 브리핑</b>\n━━━━━━━━━━━━━━━━━━━━",
                is_critical=True,
            )
        except ImportError:
            logger.warning("TelegramNotifier not available, running without notifications")

        stock_plans, futures_plan, _ = await run_unified_analysis(
            notifier=notifier, mode="all", send_telegram=notifier is not None
        )
        logger.info(f"Complete: {len(stock_plans)} stock recommendations")

        if futures_plan:
            logger.info(f"Futures: {futures_plan.direction}")

    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
