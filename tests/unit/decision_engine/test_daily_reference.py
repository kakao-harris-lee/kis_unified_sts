"""FuturesDailyReference — prev_close from parquet + today_open tracking."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from services.decision_engine.daily_reference import FuturesDailyReference


class _FakeStore:
    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df

    def get_daily_bars(self, _symbol, **_kwargs):
        return self._df


def test_prev_close_is_last_daily_close_before_today():
    df = pd.DataFrame(
        {
            "date": ["2026-06-03", "2026-06-04"],
            "close": [340.0, 351.5],
            "open": [338.0, 349.0],
        }
    )
    ref = FuturesDailyReference(store=_FakeStore(df), symbol="A05")
    assert ref.prev_close() == 351.5  # most recent daily close


def test_today_open_tracks_first_observed_price_of_day():
    ref = FuturesDailyReference(store=_FakeStore(pd.DataFrame()), symbol="A05")
    now = datetime(2026, 6, 5, 9, 0, tzinfo=UTC)
    ref.observe(price=352.0, now=now)
    ref.observe(price=353.0, now=now)  # later same day → today_open unchanged
    assert ref.today_open() == 352.0


def test_prev_close_zero_when_no_daily_bars():
    ref = FuturesDailyReference(store=_FakeStore(pd.DataFrame()), symbol="A05")
    assert ref.prev_close() == 0.0  # Setup A self-guards on prev_close<=0
