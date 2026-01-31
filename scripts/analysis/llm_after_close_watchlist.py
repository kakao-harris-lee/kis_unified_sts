#!/usr/bin/env python3
"""
After-close watchlist generator (KOSPI + KOSDAQ).

Goal:
  - Run after market close to create next-day watchlist (top 30).
  - Include baseline prev-day total volume for next-day opening surge checks.
  - Optionally notify via Telegram.
"""

import asyncio
import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

load_dotenv()

from shared.llm.watchlist import WatchlistGenerator, save_watchlist

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _render_watchlist_message(items) -> str:
    lines = [
        "<b>🧾 내일 모니터링 후보 (KOSPI+KOSDAQ)</b>",
        "━━━━━━━━━━━━━━━━━━━━",
    ]
    for i, it in enumerate(items, start=1):
        lines.append(
            f"{i:02d}. <b>{it.name}</b> ({it.code}) [{it.market}]"
            f"  chg {it.change_pct:+.1f}%"
            f"  vTrend {it.volume_trend:.2f}"
            f"  valTrend {it.value_trend:.2f}"
            f"  news {it.news_count} ({it.news_sentiment})"
        )
    return "\n".join(lines)


async def main():
    logger.info("After-close watchlist generation started")

    generator = WatchlistGenerator()
    items = generator.generate(list_size=30)
    if not items:
        logger.error("No watchlist items generated")
        return

    path = save_watchlist(items, output_dir="output/llm", filename_prefix="watchlist")
    logger.info(f"Saved: {path}")

    # Optional Telegram
    try:
        from shared.notification import TelegramNotifier

        notifier = TelegramNotifier()
        await notifier.send_message(_render_watchlist_message(items), is_critical=True)
    except Exception as e:
        logger.warning(f"Telegram notify skipped: {e}")

    logger.info("Done")


if __name__ == "__main__":
    asyncio.run(main())

