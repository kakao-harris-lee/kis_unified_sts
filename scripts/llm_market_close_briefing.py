#!/usr/bin/env python3
"""
Market Close Summary Briefing (15:30)

Sends end-of-day summary with trading performance.
Cron: 30 15 * * 1-5
"""
import asyncio
import logging
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def is_market_open_today() -> bool:
    """Check if market is open today (simple weekday check)."""
    today = datetime.now()
    return today.weekday() < 5


async def get_daily_performance() -> dict:
    """Get today's trading performance from Redis."""
    try:
        import redis.asyncio as redis

        r = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/1"))
        today = datetime.now().strftime("%Y-%m-%d")

        stats = {
            "total_trades": 0,
            "winning_trades": 0,
            "total_pnl": 0.0,
            "win_rate": 0.0,
        }

        daily_stats = await r.hgetall(f"stats:daily:{today}")
        if daily_stats:
            stats["total_trades"] = int(daily_stats.get(b"total_trades", 0))
            stats["winning_trades"] = int(daily_stats.get(b"winning_trades", 0))
            stats["total_pnl"] = float(daily_stats.get(b"total_pnl", 0))
            if stats["total_trades"] > 0:
                stats["win_rate"] = (
                    stats["winning_trades"] / stats["total_trades"] * 100
                )

        await r.aclose()
        return stats
    except Exception as e:
        logger.warning(f"Failed to get performance: {e}")
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "total_pnl": 0.0,
            "win_rate": 0.0,
        }


async def main():
    logger.info("Market Close Briefing Started")

    if not is_market_open_today():
        logger.info("Market closed today. Skipping.")
        return

    try:
        today = datetime.now().strftime("%Y-%m-%d")
        stats = await get_daily_performance()

        pnl_emoji = "📈" if stats["total_pnl"] >= 0 else "📉"
        pnl_sign = "+" if stats["total_pnl"] >= 0 else ""

        message = f"""<b>🔔 장 마감 브리핑</b>
━━━━━━━━━━━━━━━━━━━━
📅 {today}

<b>📊 오늘의 성과</b>
• 총 거래: {stats['total_trades']}건
• 승률: {stats['win_rate']:.1f}%
• 손익: {pnl_emoji} {pnl_sign}{stats['total_pnl']:,.0f}원

━━━━━━━━━━━━━━━━━━━━
<i>내일도 성공적인 트레이딩 되세요!</i>"""

        # Send via Telegram if available
        try:
            from shared.notification import TelegramNotifier

            notifier = TelegramNotifier()
            await notifier.send_message(message, is_critical=True)
            logger.info("Briefing sent via Telegram")
        except ImportError:
            logger.info("TelegramNotifier not available")
            print(message.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", ""))

    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
