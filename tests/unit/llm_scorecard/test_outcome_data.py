# tests/unit/llm_scorecard/test_outcome_data.py
from datetime import datetime

import pandas as pd

from shared.llm_scorecard.outcome_data import OutcomeData


class _Store:
    def __init__(self, df): self._df = df
    def get_minute_bars(self, symbol, start=None, end=None): return self._df


class _BoundaryStore:
    """Store double that actually filters by start/end bounds (like the real store).

    Seeded with a full day including a pre-market bar.  Returns rows where
    ``start <= index <= end`` — identical to what _normalize_boundary + DuckDB
    SQL produces.  This means the test will fail if OutcomeData passes a string
    "YYYY-MM-DD" instead of a datetime (the end boundary collapses to midnight,
    excluding all intraday bars → empty → None).
    """

    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df.copy()

    def get_minute_bars(
        self, symbol: str, start: datetime | None = None, end: datetime | None = None
    ) -> pd.DataFrame:
        df = self._df.copy()
        if start is not None:
            df = df[df.index >= pd.Timestamp(start)]
        if end is not None:
            df = df[df.index <= pd.Timestamp(end)]
        return df


def _df():
    idx = pd.to_datetime(["2026-06-25 08:50","2026-06-25 09:00","2026-06-25 15:20"])
    return pd.DataFrame({"open":[100,101,109],"close":[100,101,110]}, index=idx)


def test_session_return_excludes_pre_capture_bars():
    od = OutcomeData(_Store(_df()), now_kst=datetime(2026,6,25,16,0))
    cap = datetime(2026,6,25,8,55)  # after 08:50 pre-market print
    r = od.session_return("X", "2026-06-25", cap)
    assert round(r, 2) == round((110-101)/101*100, 2)  # open=101 (09:00), close=110


def test_missing_data_returns_none():
    class Empty:
        def get_minute_bars(self, *a, **k): return None
    assert OutcomeData(Empty(), now_kst=datetime(2026,6,25,16,0)).session_return("X","2026-06-25",datetime(2026,6,25,8,55)) is None


def _df_with_datetime_column():
    # Mirrors the real ParquetMarketDataStore.get_minute_bars shape:
    # a "datetime" COLUMN (not an index), tz-naive KST.
    return pd.DataFrame({
        "code": ["X", "X", "X"],
        "datetime": pd.to_datetime(["2026-06-25 08:50", "2026-06-25 09:00", "2026-06-25 15:20"]),
        "open": [100, 101, 109],
        "high": [100, 101, 110],
        "low": [100, 101, 109],
        "close": [100, 101, 110],
        "volume": [1, 2, 3],
    })


def test_session_return_with_datetime_column_excludes_pre_capture_bars():
    # Exercises the production path where get_minute_bars returns a datetime COLUMN.
    od = OutcomeData(_Store(_df_with_datetime_column()), now_kst=datetime(2026, 6, 25, 16, 0))
    cap = datetime(2026, 6, 25, 8, 55)  # after 08:50 pre-market print
    r = od.session_return("X", "2026-06-25", cap)
    assert round(r, 2) == round((110 - 101) / 101 * 100, 2)  # open=101 (09:00), close=110


def test_session_return_with_tz_aware_datetime_column():
    # tz-aware datetime column must not raise on comparison against tz-naive captured_at.
    df = _df_with_datetime_column()
    df["datetime"] = df["datetime"].dt.tz_localize("Asia/Seoul")
    od = OutcomeData(_Store(df), now_kst=datetime(2026, 6, 25, 16, 0))
    cap = datetime(2026, 6, 25, 8, 55)
    r = od.session_return("X", "2026-06-25", cap)
    assert round(r, 2) == round((110 - 101) / 101 * 100, 2)


def _full_day_df_indexed() -> pd.DataFrame:
    """Intraday day with a pre-market bar at 08:50 + session bars 09:00, 15:20."""
    idx = pd.to_datetime(
        ["2026-06-25 08:50", "2026-06-25 09:00", "2026-06-25 15:20"]
    )
    return pd.DataFrame(
        {"open": [100, 101, 109], "close": [100, 101, 110]}, index=idx
    )


def test_boundary_respecting_store_returns_non_none():
    """Integration guard: OutcomeData must pass datetime bounds, not a bare string.

    _BoundaryStore filters rows by start/end exactly as the real ParquetMarketDataStore
    does.  If OutcomeData passes ``start="2026-06-25"`` (string) the end boundary
    collapses to midnight → every intraday bar is excluded → session_return returns None.
    The fix (converting date_kst to a datetime range) is what makes this pass.
    """
    store = _BoundaryStore(_full_day_df_indexed())
    od = OutcomeData(store, now_kst=datetime(2026, 6, 25, 16, 0))
    cap = datetime(2026, 6, 25, 8, 55)  # after 08:50 pre-market bar
    r = od.session_return("X", "2026-06-25", cap)
    # Must be non-None: open=101 (09:00), close=110 (15:20)
    assert r is not None, (
        "session_return returned None — OutcomeData likely passed a string "
        "date instead of a datetime range to get_minute_bars"
    )
    assert round(r, 2) == round((110 - 101) / 101 * 100, 2)
