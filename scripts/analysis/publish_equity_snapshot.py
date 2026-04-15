"""Publish end-of-day equity snapshot to Redis timeline.

Intended cron: 15:40 KST Mon-Fri, after market close and position reconciliation.
Writes to `trading:{asset}:equity_timeline` sorted set (one entry per day).
"""
from __future__ import annotations

import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def snapshot_one(asset_class: str) -> bool:
    """Capture and publish one equity snapshot for an asset class."""
    from shared.streaming.trading_state import TradingStatePublisher, TradingStateReader

    reader = TradingStateReader(asset_class=asset_class)
    publisher = TradingStatePublisher(asset_class=asset_class)

    status = reader.get_status()
    if not status:
        logger.warning("%s: no status found in Redis", asset_class)
        return False

    stats = status.get("stats", {}) or {}
    positions_meta = status.get("positions", {}) or {}
    config_meta = status.get("config", {}) or {}

    capital = float(config_meta.get("capital", 0.0) or 0.0)
    open_positions_value = float(positions_meta.get("open_positions_value", 0.0) or 0.0)
    closed_pnl = float(stats.get("total_pnl", 0.0) or 0.0)

    # cash_balance = capital - open_positions_value (if positions are bought with capital)
    cash_balance = max(capital - open_positions_value, 0.0)

    publisher.publish_equity_snapshot(
        as_of=date.today(),
        cash_balance=cash_balance,
        open_positions_value=open_positions_value,
        closed_pnl=closed_pnl,
    )

    total_equity = cash_balance + open_positions_value + closed_pnl
    logger.info(
        "Published %s equity snapshot: total=%.0f, cash=%.0f, positions=%.0f, closed_pnl=%.0f",
        asset_class,
        total_equity,
        cash_balance,
        open_positions_value,
        closed_pnl,
    )
    return True


def main() -> int:
    """Publish equity snapshots for both asset classes."""
    exit_code = 0
    for asset_class in ("stock", "futures"):
        try:
            snapshot_one(asset_class)
        except Exception as e:
            logger.error(
                "snapshot_one(%s) failed: %s", asset_class, e, exc_info=True
            )
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
