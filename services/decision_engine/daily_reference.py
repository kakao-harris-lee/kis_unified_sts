"""Daily reference (prev_close / today_open) for the futures strategy daemon.

The daemon has no MarketDataProvider; prev_close comes from the parquet daily
bars and today_open is captured from the first observed price of the session.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


class FuturesDailyReference:
    """Provide prev_close (parquet) + today_open (first observed tick)."""

    def __init__(self, *, store: Any, symbol: str) -> None:
        self._store = store
        self._symbol = symbol
        self._today_open: float | None = None
        self._today: date | None = None

    def prev_close(self) -> float:
        """Most recent daily close from parquet, or 0.0 if unavailable."""
        try:
            df = self._store.get_daily_bars(self._symbol, limit=2)
        except Exception:
            return 0.0
        if df is None or len(df) == 0 or "close" not in df.columns:
            return 0.0
        try:
            return float(df["close"].iloc[-1])
        except (TypeError, ValueError, IndexError):
            return 0.0

    def observe(self, *, price: float, now: datetime) -> None:
        """Record the session's first price as today_open (resets daily)."""
        d = now.date()
        if self._today != d:
            self._today = d
            self._today_open = price

    def today_open(self) -> float:
        """Today's session open (0.0 before the first observe())."""
        return self._today_open if self._today_open is not None else 0.0
