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
from pathlib import Path

# Add project root to path and ensure consistent working directory
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from shared.llm.llm_analyzer import run_unified_analysis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("LLM Nightly Analysis Started")

    try:
        # Import notifier if available — LLM nightly analysis is the
        # full-portfolio briefing (stock + futures), so it MUST go to
        # TELEGRAM_BRIEFING_* (not the legacy `TELEGRAM_BOT_TOKEN`,
        # which `.env` aliases to TELEGRAM_STOCK_*).
        notifier = None
        try:
            from shared.notification import notifier_for_domain

            notifier = notifier_for_domain(
                "briefing",
                notification_start="00:00",
                notification_end="23:59",
            )
            if notifier is None:
                logger.warning(
                    "TELEGRAM_BRIEFING_* credentials missing; running without notifications"
                )
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
