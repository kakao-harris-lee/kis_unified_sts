#!/usr/bin/env python3
"""
LLM Pre-Market Briefing (08:30)

Sends morning briefing with stock and futures recommendations.
Cron: 30 8 * * 1-5
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.analysis.llm_job_common import configure_logger, run_unified_job

logger = configure_logger(__name__)


async def main():
    try:
        await run_unified_job(
            logger=logger,
            start_message="Pre-Market Briefing Started",
            pre_telegram_message="<b>🌅 장전 최종 브리핑</b>\n━━━━━━━━━━━━━━━━━━━━",
        )
    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
