# tests/unit/decision/test_market_context.py
from datetime import datetime
from zoneinfo import ZoneInfo

from shared.decision.context import MarketContext, ScheduledEvent

KST = ZoneInfo("Asia/Seoul")


def _ctx(**overrides):
    base = {
        "now": datetime(2026, 4, 23, 9, 30, tzinfo=KST),
        "symbol": "A05603",
        "current_price": 350.25,
        "prev_close": 348.00,
        "today_open": 352.50,
        "vwap": 351.10,
        "atr_14": 0.85,
        "atr_90th_percentile": 1.20,
        "last_15min_high": 351.00,
        "last_15min_low": 349.20,
        "current_spread_ticks": 1.0,
        "macro_overnight": None,
        "scheduled_events": [],
    }
    base.update(overrides)
    return MarketContext(**base)


def test_market_open_time_returns_kst_900():
    ctx = _ctx()
    assert ctx.market_open_time() == datetime(2026, 4, 23, 9, 0, tzinfo=KST)


def test_minutes_since_open():
    ctx = _ctx(now=datetime(2026, 4, 23, 10, 15, tzinfo=KST))
    assert abs(ctx.minutes_since_open() - 75) < 0.01


def test_find_recent_event_within_window():
    evt = ScheduledEvent(
        event_id="us_cpi",
        event_type="US_CPI",
        scheduled_at=datetime(2026, 4, 23, 9, 20, tzinfo=KST),
        impact_tier=1,
    )
    ctx = _ctx(now=datetime(2026, 4, 23, 9, 30, tzinfo=KST), scheduled_events=[evt])
    recent = ctx.find_recent_event(window_minutes=15, min_tier=2)
    assert recent is evt


def test_find_recent_event_outside_window():
    evt = ScheduledEvent(
        event_id="us_cpi",
        event_type="US_CPI",
        scheduled_at=datetime(2026, 4, 23, 9, 10, tzinfo=KST),
        impact_tier=1,
    )
    ctx = _ctx(now=datetime(2026, 4, 23, 9, 30, tzinfo=KST), scheduled_events=[evt])
    assert ctx.find_recent_event(window_minutes=15, min_tier=2) is None


def test_find_recent_event_tier_filter():
    evt = ScheduledEvent(
        event_id="x",
        event_type="minor",
        scheduled_at=datetime(2026, 4, 23, 9, 25, tzinfo=KST),
        impact_tier=3,
    )
    ctx = _ctx(now=datetime(2026, 4, 23, 9, 30, tzinfo=KST), scheduled_events=[evt])
    assert ctx.find_recent_event(window_minutes=15, min_tier=2) is None
