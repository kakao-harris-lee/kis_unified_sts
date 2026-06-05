"""Daily reference (prev_close / today_open) for the futures strategy daemon.

The daemon has no MarketDataProvider; prev_close comes from the parquet daily
bars and today_open is captured from the first observed price of the session.
"""

from __future__ import annotations

import contextlib
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
        """Most recent daily close STRICTLY BEFORE today, or 0.0 if unavailable.

        IMPORTANT: ``ParquetMarketDataStore.get_daily_bars`` orders ``datetime``
        ASC and ``LIMIT`` takes the HEAD — so we must NOT use ``limit`` to get
        recent bars. Fetch the (small) daily history, drop today's in-progress
        bar (``self._today``, set by ``observe``), and take the tail.
        """
        import pandas as pd

        try:
            df = self._store.get_daily_bars(self._symbol)
        except Exception:
            return 0.0
        if df is None or len(df) == 0 or "close" not in df.columns:
            return 0.0
        # Exclude today's (partial) bar so prev_close is yesterday's close.
        dt_col = (
            "datetime"
            if "datetime" in df.columns
            else ("date" if "date" in df.columns else None)
        )
        if self._today is not None and dt_col is not None:
            with contextlib.suppress(Exception):
                df = df[pd.to_datetime(df[dt_col]).dt.date < self._today]
        if len(df) == 0:
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
