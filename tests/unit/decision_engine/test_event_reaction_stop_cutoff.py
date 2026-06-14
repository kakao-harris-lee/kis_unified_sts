"""Regression tests for Setup C (event reaction) fast-stop + over-trading fixes.

Two behaviours added 2026-06-14 to curb 3-5 min stop-outs and late-session churn:
- `stop_buffer_atr_mult`: protective stop is pushed BEYOND the opposite 15-min
  range edge by stop_buffer_atr_mult * ATR (was placed exactly at the edge → ~1.3×
  1-min ATR away → whipsawed out).
- `no_entry_after_minutes_since_open`: no new entries after 15:00 KST (360 min
  since the 09:00 open).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from shared.decision.context import ScheduledEvent, build_market_context
from shared.decision.setups.event_reaction import SetupCConfig, SetupCEventReaction

KST = ZoneInfo("Asia/Seoul")
_ATR = 4.0
_LOW = 400.0
_HIGH = 405.0


def _event(now: datetime) -> ScheduledEvent:
    return ScheduledEvent(
        event_id=f"evt-{now.isoformat()}",
        event_type="FOMC",
        scheduled_at=now - timedelta(minutes=5),  # within the 15-min window
        impact_tier=1,
    )


def _ctx(now: datetime, current_price: float):
    return build_market_context(
        now=now,
        symbol="A05606",
        current_price=current_price,
        prev_close=_LOW,
        today_open=_LOW,
        atr_14=_ATR,
        last_15min_high=_HIGH,
        last_15min_low=_LOW,
        scheduled_events=[_event(now)],
    )


def test_short_stop_is_buffered_beyond_range_high():
    now = datetime(2026, 6, 11, 10, 0, tzinfo=KST)  # 60 min since open
    # price just below the 15-min low → short breakout
    ctx = _ctx(now, current_price=_LOW - 1.0)
    sig = SetupCEventReaction(config=SetupCConfig()).check(ctx)
    assert sig is not None and sig.direction == "short"
    # stop = 15min_high + stop_buffer_atr_mult(0.5) * atr(4) = 405 + 2 = 407
    assert sig.stop_loss == _HIGH + 0.5 * _ATR


def test_long_stop_is_buffered_beyond_range_low():
    now = datetime(2026, 6, 11, 10, 0, tzinfo=KST)
    ctx = _ctx(now, current_price=_HIGH + 1.0)  # short breakout above high → long
    sig = SetupCEventReaction(config=SetupCConfig()).check(ctx)
    assert sig is not None and sig.direction == "long"
    # stop = 15min_low - 0.5 * atr = 400 - 2 = 398
    assert sig.stop_loss == _LOW - 0.5 * _ATR


def test_no_entry_after_cutoff():
    # 15:30 KST = 390 min since open > 360 cutoff → no entry even with a valid event/breakout
    now = datetime(2026, 6, 11, 15, 30, tzinfo=KST)
    ctx = _ctx(now, current_price=_LOW - 1.0)
    assert SetupCEventReaction(config=SetupCConfig()).check(ctx) is None


def test_entry_allowed_just_before_cutoff():
    # 14:59 KST = 359 min < 360 → still fires
    now = datetime(2026, 6, 11, 14, 59, tzinfo=KST)
    ctx = _ctx(now, current_price=_LOW - 1.0)
    assert SetupCEventReaction(config=SetupCConfig()).check(ctx) is not None


def test_cutoff_is_configurable():
    now = datetime(2026, 6, 11, 14, 0, tzinfo=KST)  # 300 min since open
    ctx = _ctx(now, current_price=_LOW - 1.0)
    # tighten cutoff to 240 min (13:00 KST) → 300 > 240 → blocked
    cfg = SetupCConfig(no_entry_after_minutes_since_open=240)
    assert SetupCEventReaction(config=cfg).check(ctx) is None
