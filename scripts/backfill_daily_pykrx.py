"""KIS 일봉 백필 스크립트 (legacy filename: backfill_daily_pykrx.py).

`pykrx` 의존 없이 KIS 일봉 API(FHKST03010100)를 사용해
`market.daily_candles`를 백필한다.

Usage:
    python scripts/backfill_daily_pykrx.py --days 500
    python scripts/backfill_daily_pykrx.py --days 500 --symbols 005930,000660
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from shared.collector.historical.daily_stock import collect_daily_candles
from shared.collector.historical.stock import STOCK_UNIVERSE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_SYMBOLS = [item["code"] for item in STOCK_UNIVERSE]


def _parse_symbols(raw: str | None) -> list[str]:
    if not raw:
        return list(DEFAULT_SYMBOLS)
    return [s.strip() for s in raw.split(",") if s.strip()]


async def _run(days: int, symbols: list[str]) -> int:
    logger.info("Backfilling %d symbols (~%d trading days) via KIS daily API", len(symbols), days)
    return await collect_daily_candles(codes=symbols, days=days, verbose=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="KIS 일봉 백필 to ClickHouse")
    parser.add_argument("--days", type=int, default=500, help="백필 거래일 수 (default: 500)")
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="종목 코드 (콤마 구분, default: stock universe)",
    )
    args = parser.parse_args()

    symbols = _parse_symbols(args.symbols)
    if not symbols:
        logger.error("No symbols provided")
        return 1

    rows = asyncio.run(_run(args.days, symbols))
    logger.info("Done! Total inserted rows: %d", rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
