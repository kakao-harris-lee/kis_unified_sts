#!/usr/bin/env python3
"""Legacy wrapper — delegates to scripts.analysis.llm_market_close_briefing."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.analysis.llm_market_close_briefing import main

if __name__ == "__main__":
    asyncio.run(main())
