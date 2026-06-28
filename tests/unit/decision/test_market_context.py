# tests/unit/decision/test_market_context.py
from datetime import datetime
from zoneinfo import ZoneInfo

from shared.decision.context import MarketContext, ScheduledEvent

KST = ZoneInfo("Asia/Seoul")


def _ctx(**overrides):
    """Build a MarketContext with 08:45 KST open (futures default)."""
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
        # Explicit 08:45 futures open (matches the config default).
        "market_open_hour": 8,
        "market_open_minute": 45,
    }
    base.update(overrides)
    return MarketContext(**base)


# ---------------------------------------------------------------------------
# Core: 08:45 configured open (futures day session)
# ---------------------------------------------------------------------------


def test_market_open_time_returns_kst_0845():
    """Default futures open is 08:45 KST."""
    ctx = _ctx()
    assert ctx.market_open_time() == datetime(2026, 4, 23, 8, 45, tzinfo=KST)


def test_minutes_since_open_at_0845_is_zero():
    """At 08:45 KST minutes_since_open == 0."""
    ctx = _ctx(now=datetime(2026, 4, 23, 8, 45, tzinfo=KST))
    assert abs(ctx.minutes_since_open() - 0.0) < 0.01


def test_minutes_since_open_at_0855_is_ten():
    """At 08:55 KST (08:45 + 10 min) minutes_since_open == 10."""
    ctx = _ctx(now=datetime(2026, 4, 23, 8, 55, tzinfo=KST))
    assert abs(ctx.minutes_since_open() - 10.0) < 0.01


def test_minutes_since_open_at_0900_is_fifteen():
    """At 09:00 KST (08:45 + 15 min) minutes_since_open == 15."""
    ctx = _ctx(now=datetime(2026, 4, 23, 9, 0, tzinfo=KST))
    assert abs(ctx.minutes_since_open() - 15.0) < 0.01


def test_minutes_since_open_at_1500_is_375():
    """At 15:00 KST (08:45 + 375 min) minutes_since_open == 375."""
    ctx = _ctx(now=datetime(2026, 4, 23, 15, 0, tzinfo=KST))
    assert abs(ctx.minutes_since_open() - 375.0) < 0.01


# ---------------------------------------------------------------------------
# Regression: explicit 09:00 open still works (stock/legacy callers)
# ---------------------------------------------------------------------------


def test_market_open_time_explicit_0900():
    """Explicit 09:00 open fields produce 09:00 KST open."""
    ctx = _ctx(market_open_hour=9, market_open_minute=0)
    assert ctx.market_open_time() == datetime(2026, 4, 23, 9, 0, tzinfo=KST)


def test_minutes_since_open_explicit_0900():
    """minutes_since_open with explicit 09:00 open: 10:15 KST → 75 min."""
    ctx = _ctx(
        now=datetime(2026, 4, 23, 10, 15, tzinfo=KST),
        market_open_hour=9,
        market_open_minute=0,
    )
    assert abs(ctx.minutes_since_open() - 75.0) < 0.01


# ---------------------------------------------------------------------------
# find_recent_event (unchanged behaviour)
# ---------------------------------------------------------------------------


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
