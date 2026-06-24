from __future__ import annotations
from datetime import datetime


class OutcomeData:
    """No-look-ahead market outcome accessor.

    All data returned is restricted to bars at or after `captured_at`
    to prevent future-leakage into scoring.
    """

    def __init__(self, store: object, now_kst: datetime) -> None:
        self._store = store
        self._now = now_kst

    def bars_after(self, symbol: str, date_kst: str, after: datetime):
        """Return minute bars for `symbol` on `date_kst` at/after `after`."""
        try:
            df = self._store.get_minute_bars(symbol, start=date_kst, end=date_kst)
        except Exception:
            return None
        if df is None or len(df) == 0:
            return None
        # Handle real store (datetime column) vs fake store (DatetimeIndex)
        import pandas as pd
        if "datetime" in getattr(df, "columns", []):
            df = df.set_index("datetime")
            df.index = pd.to_datetime(df.index)
        # Now filter by after timestamp (tz-naive comparison)
        after_ts = pd.Timestamp(after)
        df = df[df.index >= after_ts]
        return df if len(df) else None

    def session_return(self, symbol: str, date_kst: str, captured_at: datetime) -> float | None:
        """Open-to-close % return using only bars at/after `captured_at`.

        Returns None when data is missing or insufficient (unscorable).
        """
        df = self.bars_after(symbol, date_kst, captured_at)
        if df is None or len(df) < 2:
            return None
        o = float(df.iloc[0]["open"])
        c = float(df.iloc[-1]["close"])
        if o == 0:
            return None
        return (c - o) / o * 100.0
