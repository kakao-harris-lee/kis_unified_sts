"""FuturesDailyReference — prev_close from parquet + today_open tracking."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import fakeredis
import pandas as pd

from services.decision_engine.daily_reference import FuturesDailyReference
from shared.streaming.daily_reference import (
    SOURCE_KIS_REST,
    publish_futures_daily_reference,
)

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


# ---------------------------------------------------------------------------
# G1: prev_close read-model (futures:daily_reference:{symbol}) → parquet → 0.0
#
# The parquet daily partition only ever held the TRAINING symbols (101S6000 /
# krx_kospi200f_continuous, stale since 2026-06-25), so the trading symbol had
# no daily bar at all and Setup A was permanently blind. These tests pin the
# source order, the KST-day freshness gate, and the once-per-day log latches.
# ---------------------------------------------------------------------------


def _publish(redis_client, *, symbol, prev_close, asof):
    asyncio.run(
        publish_futures_daily_reference(
            redis_client,
            symbol=symbol,
            prev_close=prev_close,
            source=SOURCE_KIS_REST,
            producer="trader-futures",
            asof=asof,
        )
    )


def _parquet_frame(close: float) -> pd.DataFrame:
    return pd.DataFrame({"datetime": ["2026-06-04"], "close": [close]})


def test_prev_close_prefers_a_fresh_redis_read_model_over_parquet(caplog):
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    _publish(redis_client, symbol="A05609", prev_close=411.25, asof=datetime.now(_KST))
    ref = FuturesDailyReference(
        store=_FakeStore(_parquet_frame(351.5)), symbol="A05609", redis=redis_client
    )
    with caplog.at_level("INFO"):
        assert ref.prev_close() == 411.25
    assert "prev_close source=redis symbol=A05609" in caplog.text


def test_prev_close_ignores_a_read_model_from_a_previous_kst_day(caplog):
    """The key's 24h TTL outlives a trade date — yesterday's value must not be
    read as today's reference."""
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    _publish(
        redis_client,
        symbol="A05609",
        prev_close=411.25,
        asof=datetime.now(_KST) - timedelta(days=1),
    )
    ref = FuturesDailyReference(
        store=_FakeStore(_parquet_frame(351.5)), symbol="A05609", redis=redis_client
    )
    with caplog.at_level("INFO"):
        assert ref.prev_close() == 351.5
    assert "prev_close source=parquet symbol=A05609" in caplog.text


def test_prev_close_warns_once_per_day_when_no_source_has_it(caplog):
    """Regression: the parquet miss used to emit one WARNING per 60s tick
    (830 lines on 2026-09-10)."""
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    ref = FuturesDailyReference(
        store=_FakeStore(pd.DataFrame()), symbol="A05609", redis=redis_client
    )
    with caplog.at_level("WARNING"):
        assert ref.prev_close() == 0.0
        assert ref.prev_close() == 0.0
        assert ref.prev_close() == 0.0
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1
    assert "prev_close unavailable for A05609" in warnings[0].getMessage()


def test_prev_close_is_read_once_per_day_then_cached():
    """The decision loop asks every ~60s; the read-model is a daily constant."""
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    _publish(redis_client, symbol="A05609", prev_close=411.25, asof=datetime.now(_KST))
    reads = {"n": 0}
    real_hgetall = redis_client.hgetall

    def _counting_hgetall(key):
        reads["n"] += 1
        return real_hgetall(key)

    redis_client.hgetall = _counting_hgetall
    ref = FuturesDailyReference(
        store=_FakeStore(pd.DataFrame()), symbol="A05609", redis=redis_client
    )
    assert [ref.prev_close() for _ in range(5)] == [411.25] * 5
    assert reads["n"] == 1


def test_a_missing_prev_close_is_not_cached_so_a_late_publish_is_picked_up():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    ref = FuturesDailyReference(
        store=_FakeStore(pd.DataFrame()), symbol="A05609", redis=redis_client
    )
    assert ref.prev_close() == 0.0
    _publish(redis_client, symbol="A05609", prev_close=411.25, asof=datetime.now(_KST))
    assert ref.prev_close() == 411.25


def test_prev_close_without_a_redis_client_is_parquet_only():
    """Old two-argument construction (tests, any caller with no Redis) still works."""
    ref = FuturesDailyReference(
        store=_FakeStore(_parquet_frame(351.5)), symbol="A05609"
    )
    assert ref.prev_close() == 351.5
