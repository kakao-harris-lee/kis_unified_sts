"""Daily Scanner Entry Point — pre-market universe selection.

Scans stock universe using daily candle data and publishes filtered watchlists
to Redis for consumption by intraday trading strategies.

Applies Layer 1 filters:
- Minimum edge (ATR vs trading costs)
- Trend pullback (uptrend + RSI pullback)
- Momentum breakout (near N-day high + rising volume)

Results are published to Redis key ``system:daily_watchlist:latest`` with 24h TTL.

Usage:
    python scripts/run_daily_scanner.py [--symbols 005930,000660]

Cron: 30 8 * * 1-5  (08:30 KST, before market open)
"""

from __future__ import annotations

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_daily_scanner")

# Import stock universe constant
from shared.collector.historical.stock import STOCK_UNIVERSE
from services.daily_scanner import DailyScanner, DailyScannerConfig


DEFAULT_SYMBOLS = [item["code"] for item in STOCK_UNIVERSE]


def _parse_symbols(raw: str | None) -> list[str]:
    """Parse comma-separated symbol string or return default universe."""
    if not raw:
        return list(DEFAULT_SYMBOLS)
    return [s.strip() for s in raw.split(",") if s.strip()]


def main() -> int:
    """Entry point for daily scanner.

    Returns:
        Exit code (0 on success, 1 on error).
    """
    parser = argparse.ArgumentParser(
        description="Daily scanner for pre-market universe selection"
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Comma-separated stock codes (default: STOCK_UNIVERSE)",
    )
    args = parser.parse_args()

    symbols = _parse_symbols(args.symbols)
    if not symbols:
        logger.error("No symbols provided")
        return 1

    logger.info("=" * 60)
    logger.info("Daily Scanner Starting")
    logger.info(f"Universe size: {len(symbols)} stocks")
    logger.info("=" * 60)

    try:
        # Load configuration
        config = DailyScannerConfig.from_yaml()
        logger.info("Loaded DailyScannerConfig from daily_scanner.yaml")

        # Initialize scanner
        scanner = DailyScanner(config)

        # Run scan and publish to Redis
        result = scanner.scan_and_publish(symbols)

        # Log summary
        logger.info("=" * 60)
        logger.info("Daily Scanner Completed Successfully")
        logger.info(f"  Trend pullback watchlist:    {len(result['trend_pullback']):>5} stocks")
        logger.info(f"  Momentum breakout watchlist: {len(result['momentum_breakout']):>5} stocks")
        logger.info(f"  Published to Redis: {config.redis_key}")
        logger.info(f"  TTL: {config.redis_ttl_seconds}s ({config.redis_ttl_seconds // 3600}h)")
        logger.info("=" * 60)

        return 0

    except Exception as exc:
        logger.exception("Daily scanner failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
