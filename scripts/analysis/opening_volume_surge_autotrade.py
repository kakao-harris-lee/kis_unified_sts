#!/usr/bin/env python3
"""
Auto-trade runner for the Opening Volume Surge strategy.

Workflow:
  1) Run `scripts/analysis/llm_after_close_watchlist.py` after close.
  2) Next day, run this script before/at open.
     - It loads output/llm/watchlist_latest.json
     - Runs TradingOrchestrator with strategy=opening_volume_surge
     - Uses prev_day_volume baseline from watchlist for the 09:00~09:30 trigger

Execution mode:
  - TRADING_MODE=PAPER  -> paper_trading=True (default)
  - TRADING_MODE=MOCK/REAL -> paper_trading=False (KIS order executor wiring may be added separately)
"""

import asyncio
import json
import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

load_dotenv()

from services.trading.orchestrator import run_stock_trading

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _load_watchlist(path: str) -> tuple[list[str], dict]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    items = payload.get("items", []) or []
    symbols = []
    meta = {}
    for it in items:
        code = str(it.get("code", "")).strip()
        if not code:
            continue
        symbols.append(code)
        meta[code] = {
            "name": it.get("name", code),
            "market": it.get("market", ""),
            "prev_day_close": it.get("prev_close", 0),
            "prev_day_volume": it.get("prev_volume", 0),
            "prev_day_trade_value": it.get("prev_trade_value", 0),
            "watchlist_score": it.get("score", 0),
        }

    return symbols, meta


async def main():
    watchlist_path = os.getenv("WATCHLIST_PATH", "output/llm/watchlist_latest.json")
    if not os.path.exists(watchlist_path):
        raise FileNotFoundError(f"Watchlist not found: {watchlist_path}")

    symbols, symbol_metadata = _load_watchlist(watchlist_path)
    if not symbols:
        logger.error("No symbols in watchlist")
        return

    mode = (os.getenv("TRADING_MODE", "PAPER") or "PAPER").upper()
    paper_trading = mode == "PAPER"

    capital = float(os.getenv("TRADING_CAPITAL", "10000000"))

    logger.info(
        f"Starting opening volume surge trading: mode={mode} paper={paper_trading} "
        f"symbols={len(symbols)} capital={capital:,.0f}"
    )

    await run_stock_trading(
        strategy="opening_volume_surge",
        symbols=symbols,
        capital=capital,
        paper_trading=paper_trading,
        execution_mode=mode if not paper_trading else "",
        symbol_metadata=symbol_metadata,
        daemon=False,
    )


if __name__ == "__main__":
    asyncio.run(main())

