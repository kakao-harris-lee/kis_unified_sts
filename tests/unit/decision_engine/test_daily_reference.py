"""FuturesDailyReference — prev_close from parquet + today_open tracking."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from services.decision_engine.daily_reference import FuturesDailyReference


class _FakeStore:
    """Honors the real store contract: ASC by datetime, returns ALL rows
    (the real get_daily_bars LIMIT takes the head, so prev_close must not
    rely on limit — it fetches all and tails after excluding today)."""

    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df

    def get_daily_bars(self, _symbol, **_kwargs):
        return self._df


def test_prev_close_is_most_recent_close_before_today():
    # ASC by datetime; includes today's (2026-06-05) partial bar which must be excluded
    df = pd.DataFrame(
        {
            "datetime": ["2026-06-03", "2026-06-04", "2026-06-05"],
            "close": [340.0, 351.5, 999.0],
            "open": [338.0, 349.0, 352.0],
        }
    )
    ref = FuturesDailyReference(store=_FakeStore(df), symbol="A05")
    ref.observe(price=352.0, now=datetime(2026, 6, 5, 9, 0, tzinfo=UTC))  # sets _today
    assert ref.prev_close() == 351.5  # 06-04 close, NOT today's 999.0 nor oldest 340.0


def test_today_open_tracks_first_observed_price_of_day():
    ref = FuturesDailyReference(store=_FakeStore(pd.DataFrame()), symbol="A05")
    now = datetime(2026, 6, 5, 9, 0, tzinfo=UTC)
    ref.observe(price=352.0, now=now)
    ref.observe(price=353.0, now=now)  # later same day → today_open unchanged
    assert ref.today_open() == 352.0


def test_prev_close_zero_when_no_daily_bars():
    ref = FuturesDailyReference(store=_FakeStore(pd.DataFrame()), symbol="A05")
    assert ref.prev_close() == 0.0  # Setup A self-guards on prev_close<=0
