#!/usr/bin/env python3
"""
LLM Stock Screener - Nightly Analysis (21:00)

Runs unified trading analysis and sends results via Telegram.
Cron: 0 21 * * 1-5
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
            start_message="LLM Nightly Analysis Started",
        )
    except Exception as e:
        logger.error(f"Failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
