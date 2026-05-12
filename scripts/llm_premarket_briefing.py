#!/usr/bin/env python3
"""
LLM Pre-Market Briefing

Sends morning briefing with stock and futures recommendations.
Cron: 30 6 * * 1-5 (06:30 KST — analysis historically takes ~1h27m–1h47m,
so a 06:30 start finishes around 08:00–08:30 KST, comfortably pre-market.
"""

import asyncio
import logging
import os
import sys

# Add project root to path, then load env BEFORE importing shared modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from shared.llm.llm_analyzer import run_unified_analysis  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

ANALYSIS_TIMEOUT_SECONDS = 7200  # 2h — historical runs complete in 1h15m–1h47m


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

    notifier = None
    try:
        from shared.notification import notifier_for_domain

        notifier = notifier_for_domain("briefing")
        if notifier is None:
            logger.warning(
                "Briefing Telegram channel not configured; running without notifications"
            )
    except ImportError:
        logger.warning("TelegramNotifier not available, running without notifications")

    try:
        stock_plans, futures_plan, _ = await asyncio.wait_for(
            run_unified_analysis(
                notifier=notifier, mode="all", send_telegram=notifier is not None
            ),
            timeout=ANALYSIS_TIMEOUT_SECONDS,
        )
        logger.info(f"Complete: {len(stock_plans)} stock recommendations")

        if futures_plan:
            logger.info(f"Futures: {futures_plan.direction}")

    except TimeoutError:
        logger.error(
            f"Pre-market analysis exceeded {ANALYSIS_TIMEOUT_SECONDS}s timeout — aborting"
        )
        if notifier is not None:
            try:
                await notifier.send_message(
                    f"⚠️ <b>장전 브리핑 타임아웃</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"분석이 {ANALYSIS_TIMEOUT_SECONDS // 60}분을 초과하여 중단되었습니다.\n"
                    f"외부 API (KIS / DART / KRX) 응답 지연 가능성. 로그 확인 필요.",
                    is_critical=True,
                )
            except Exception as send_err:  # noqa: BLE001
                logger.error(f"Failed to send timeout alert: {send_err}")
        raise
    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
