from __future__ import annotations
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    import pandas as pd


class _MinuteBarStore(Protocol):
    def get_minute_bars(
        self, symbol: str, start: Any = ..., end: Any = ...
    ) -> "pd.DataFrame | None": ...


class OutcomeData:
    """No-look-ahead market outcome accessor.

    All data returned is restricted to bars at or after `captured_at`
    to prevent future-leakage into scoring.
    """

    def __init__(self, store: _MinuteBarStore, now_kst: datetime) -> None:
        self._store = store
        self._now = now_kst

    def bars_after(
        self, symbol: str, date_kst: str, after: datetime
    ) -> "pd.DataFrame | None":
        """Return minute bars for `symbol` on `date_kst` at/after `after`."""
        try:
            _day = datetime.strptime(date_kst, "%Y-%m-%d")
            df = self._store.get_minute_bars(
                symbol,
                start=_day,
                end=_day + timedelta(days=1) - timedelta(microseconds=1),
            )
        except Exception:
            return None
        if df is None or len(df) == 0:
            return None
        # Handle real store (datetime column) vs fake store (DatetimeIndex)
        import pandas as pd
        if "datetime" in getattr(df, "columns", []):
            df = df.set_index("datetime")
        df.index = pd.to_datetime(df.index)
        # Drop tz so comparison against the tz-naive KST captured_at is valid
        if getattr(df.index, "tz", None) is not None:
            df.index = df.index.tz_localize(None)
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
