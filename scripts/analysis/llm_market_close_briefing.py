#!/usr/bin/env python3
"""
Market Close Summary Briefing (15:30)

Sends end-of-day summary.
Cron: 30 15 * * 1-5
"""
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.notification import TelegramNotifier
from shared.calendar import is_market_open_today

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)


async def get_daily_performance() -> dict:
    """Get today's trading performance.

    Returns placeholder stats. In production, this would fetch from:
    - Redis for real-time stats
    - SQLite/PostgreSQL for trade records
    """
    stats = {
        'total_trades': 0,
        'winning_trades': 0,
        'total_pnl': 0.0,
        'win_rate': 0.0
    }

    # TODO: Integrate with actual trading system
    # try:
    #     from services.trading.orchestrator import get_orchestrator
    #     orchestrator = get_orchestrator()
    #     stats = await orchestrator.get_daily_stats()
    # except Exception as e:
    #     logger.warning(f"Failed to get performance: {e}")

    return stats


async def main():
    logger.info("Market Close Briefing Started")

    if not is_market_open_today():
        logger.info("Market closed today. Skipping.")
        return

    try:
        notifier = TelegramNotifier()
        today = datetime.now().strftime('%Y-%m-%d')
        stats = await get_daily_performance()

        pnl_emoji = "📈" if stats['total_pnl'] >= 0 else "📉"
        pnl_sign = "+" if stats['total_pnl'] >= 0 else ""

        message = f"""<b>🔔 장 마감 브리핑</b>
━━━━━━━━━━━━━━━━━━━━
📅 {today}

<b>📊 오늘의 성과</b>
• 총 거래: {stats['total_trades']}건
• 승률: {stats['win_rate']:.1f}%
• 손익: {pnl_emoji} {pnl_sign}{stats['total_pnl']:,.0f}원

━━━━━━━━━━━━━━━━━━━━
<i>내일도 성공적인 트레이딩 되세요!</i>"""

        await notifier.send_message(message, is_critical=True)
        logger.info("Briefing sent")
    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
