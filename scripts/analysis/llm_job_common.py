"""Shared runner for LLM analysis cron jobs."""

from __future__ import annotations

import logging

from shared.calendar import is_market_open_today
from shared.llm import run_unified_analysis
from shared.notification import notifier_for_domain


def configure_logger(name: str) -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    return logging.getLogger(name)


async def run_unified_job(
    logger: logging.Logger,
    start_message: str,
    pre_telegram_message: str | None = None,
) -> None:
    logger.info(start_message)

    if not is_market_open_today():
        logger.info("Market closed today. Skipping.")
        return

    notifier = notifier_for_domain("briefing")
    if notifier is None:
        logger.warning(
            "Briefing Telegram channel not configured; running analysis without notifications"
        )
    elif pre_telegram_message:
        await notifier.send_message(pre_telegram_message, is_critical=True)

    stock_plans, futures_plan, _ = await run_unified_analysis(
        notifier=notifier,
        mode="all",
        send_telegram=notifier is not None,
    )
    logger.info(
        "Complete: %s stocks, futures=%s",
        len(stock_plans),
        futures_plan.direction if futures_plan else "N/A",
    )
