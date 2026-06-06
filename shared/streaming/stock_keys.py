"""Stock streaming Redis key conventions."""

from __future__ import annotations

import os

DEFAULT_STOCK_DAEMON_POSITIONS_KEY = "stock:daemon:positions"
DASHBOARD_STOCK_POSITIONS_KEY = "trading:stock:positions"


def stock_daemon_positions_key() -> str:
    """Return the M4 stock daemon working-store key.

    This is deliberately separate from the dashboard-native
    ``trading:stock:positions`` key that ``TradingStatePublisher`` owns.
    """
    return os.environ.get("STOCK_POSITIONS_KEY", DEFAULT_STOCK_DAEMON_POSITIONS_KEY)
