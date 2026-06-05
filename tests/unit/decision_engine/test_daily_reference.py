"""FuturesDailyReference — prev_close from parquet + today_open tracking."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pandas as pd

from services.decision_engine.daily_reference import FuturesDailyReference

_KST = ZoneInfo("Asia/Seoul")


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


# ---------------------------------------------------------------------------
# Bug B: pre-open guard — observe() before 09:00 KST must not capture today_open
# ---------------------------------------------------------------------------


def test_observe_before_market_open_does_not_capture_today_open():
    """Bug B regression: pre-open call must NOT set today_open.

    08:55 KST is before 09:00 KST open — the warmup-seeded price must not
    poison today_open for Setup A's gap calculation.
    """
    ref = FuturesDailyReference(store=_FakeStore(pd.DataFrame()), symbol="A05")
    pre_open_kst = datetime(2026, 6, 5, 8, 55, tzinfo=_KST)
    ref.observe(price=999.0, now=pre_open_kst)
    assert (
        ref.today_open() == 0.0
    ), "today_open must stay 0.0 when observe is called before 09:00 KST"


def test_observe_at_and_after_market_open_captures_today_open():
    """Bug B: first in-session price IS captured as today_open."""
    ref = FuturesDailyReference(store=_FakeStore(pd.DataFrame()), symbol="A05")
    # Call once before open (should be ignored)
    ref.observe(price=999.0, now=datetime(2026, 6, 5, 8, 55, tzinfo=_KST))
    # First in-session call at exactly 09:01 KST
    in_session_kst = datetime(2026, 6, 5, 9, 1, tzinfo=_KST)
    ref.observe(price=350.0, now=in_session_kst)
    assert (
        ref.today_open() == 350.0
    ), "today_open must be captured from the first in-session price"
    # Subsequent in-session call same day must NOT change today_open
    ref.observe(price=360.0, now=datetime(2026, 6, 5, 9, 5, tzinfo=_KST))
    assert ref.today_open() == 350.0
