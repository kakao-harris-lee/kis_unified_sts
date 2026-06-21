"""Tests validating Setup C fires against the real event calendar entries.

Covers the new in-session event types added to config/scheduled_events.yaml:
  - BOK_rate_decision at 10:00 KST (tier 1)
  - CHINA_PMI at 09:00 KST (tier 2)
  - KOSPI200_REBALANCE at 09:00 KST (tier 2)
  - KR_CPI_RELEASE at 08:00 KST (tier 3 — outside window, should NOT fire)

Also checks that the calendar YAML round-trips cleanly and that the
out-of-session US events (FOMC/CPI/NFP) do NOT fire Setup C during KR hours.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from shared.decision.context import ScheduledEvent, build_market_context, load_scheduled_events
from shared.decision.setups.event_reaction import SetupCConfig, SetupCEventReaction

KST = ZoneInfo("Asia/Seoul")
UTC = ZoneInfo("UTC")

# Path to the real event calendar (project root relative)
_CALENDAR_PATH = Path(__file__).parent.parent.parent.parent / "config" / "scheduled_events.yaml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _evt(
    event_id: str,
    event_type: str,
    kst_time: datetime,
    impact_tier: int,
) -> ScheduledEvent:
    """Build a ScheduledEvent pinned to a specific KST moment."""
    return ScheduledEvent(
        event_id=event_id,
        event_type=event_type,
        scheduled_at=kst_time,  # tz-aware KST is fine; find_recent_event compares aware datetimes
        impact_tier=impact_tier,
    )


def _ctx_with_long_breakout(
    now: datetime,
    events: list[ScheduledEvent],
    *,
    atr: float = 1.0,
) -> object:
    """Build a MarketContext with a clean long breakout just above the 15m high."""
    last_15min_high = 350.0
    last_15min_low = 348.0
    # current_price just above high but within breakout_buffer_atr_mult=0.5 * atr
    current_price = last_15min_high + 0.3 * atr
    return build_market_context(
        now=now,
        symbol="A05603",
        current_price=current_price,
        prev_close=349.0,
        today_open=349.5,
        atr_14=atr,
        last_15min_high=last_15min_high,
        last_15min_low=last_15min_low,
        scheduled_events=events,
    )


def _ctx_with_short_breakout(
    now: datetime,
    events: list[ScheduledEvent],
    *,
    atr: float = 1.0,
) -> object:
    """Build a MarketContext with a clean short breakout just below the 15m low."""
    last_15min_high = 352.0
    last_15min_low = 350.0
    # current_price just below low but within buffer
    current_price = last_15min_low - 0.3 * atr
    return build_market_context(
        now=now,
        symbol="A05603",
        current_price=current_price,
        prev_close=351.0,
        today_open=350.8,
        atr_14=atr,
        last_15min_high=last_15min_high,
        last_15min_low=last_15min_low,
        scheduled_events=events,
    )


# ---------------------------------------------------------------------------
# Calendar load tests
# ---------------------------------------------------------------------------


def test_real_calendar_loads_without_error():
    """The production calendar YAML must load without exception."""
    events = load_scheduled_events(str(_CALENDAR_PATH))
    assert len(events) >= 24, f"Expected >= 24 events, got {len(events)}"


def test_real_calendar_has_in_session_events():
    """At least 20 events must fall in KR session hours with tier <= 2."""
    events = load_scheduled_events(str(_CALENDAR_PATH))
    in_session = [
        e
        for e in events
        if (
            e.impact_tier <= 2
            and (
                lambda ts: (
                    (ts.hour > 8 or (ts.hour == 8 and ts.minute >= 45))
                    and (ts.hour < 15 or (ts.hour == 15 and ts.minute <= 45))
                )
            )(e.scheduled_at.astimezone(KST))
        )
    ]
    assert len(in_session) >= 20, (
        f"Expected >= 20 in-session tier<=2 events, got {len(in_session)}"
    )


def test_real_calendar_covers_backtest_window():
    """Must have >= 8 in-session events in the Nov 2025 – Apr 2026 backtest window."""
    from datetime import date

    events = load_scheduled_events(str(_CALENDAR_PATH))
    bt_start = date(2025, 11, 1)
    bt_end = date(2026, 4, 30)

    in_window = [
        e
        for e in events
        if (
            e.impact_tier <= 2
            and bt_start <= e.scheduled_at.astimezone(KST).date() <= bt_end
            and (
                lambda ts: (
                    (ts.hour > 8 or (ts.hour == 8 and ts.minute >= 45))
                    and ts.hour < 16
                )
            )(e.scheduled_at.astimezone(KST))
        )
    ]
    assert len(in_window) >= 8, (
        f"Expected >= 8 in-session events in backtest window, got {len(in_window)}"
    )


# ---------------------------------------------------------------------------
# BOK rate decision tests (10:00 KST, tier 1)
# ---------------------------------------------------------------------------


def test_setup_c_fires_on_bok_event_long():
    """Setup C emits a long signal 5 min after a tier-1 BOK event (10:00 KST)."""
    bok_at = datetime(2026, 1, 16, 10, 0, 0, tzinfo=KST)
    evt = _evt("bok_2026_jan", "BOK_rate_decision", bok_at, impact_tier=1)
    now = datetime(2026, 1, 16, 10, 5, 0, tzinfo=KST)
    ctx = _ctx_with_long_breakout(now, [evt])

    setup = SetupCEventReaction()
    signal = setup.check(ctx)

    assert signal is not None, f"Expected signal, got reject: {setup.last_reject_reason}"
    assert signal.direction == "long"
    assert signal.confidence == pytest.approx(0.75)
    assert "event_BOK_rate_decision" in signal.reason_tags
    assert "tier_1" in signal.reason_tags


def test_setup_c_fires_on_bok_event_short():
    """Setup C emits a short signal 3 min after a tier-1 BOK event."""
    bok_at = datetime(2026, 4, 17, 10, 0, 0, tzinfo=KST)
    evt = _evt("bok_2026_apr", "BOK_rate_decision", bok_at, impact_tier=1)
    now = datetime(2026, 4, 17, 10, 3, 0, tzinfo=KST)
    ctx = _ctx_with_short_breakout(now, [evt])

    setup = SetupCEventReaction()
    signal = setup.check(ctx)

    assert signal is not None, f"Expected signal, got reject: {setup.last_reject_reason}"
    assert signal.direction == "short"
    assert "event_BOK_rate_decision" in signal.reason_tags


# ---------------------------------------------------------------------------
# China PMI tests (09:00 KST, tier 2)
# ---------------------------------------------------------------------------


def test_setup_c_fires_on_china_pmi_long():
    """Setup C fires 10 min after China PMI (09:00 KST, tier 2) with long breakout."""
    pmi_at = datetime(2026, 2, 27, 9, 0, 0, tzinfo=KST)
    evt = _evt("china_pmi_2026_feb", "CHINA_PMI", pmi_at, impact_tier=2)
    now = datetime(2026, 2, 27, 9, 10, 0, tzinfo=KST)
    ctx = _ctx_with_long_breakout(now, [evt])

    setup = SetupCEventReaction()
    signal = setup.check(ctx)

    assert signal is not None, f"Expected signal, got reject: {setup.last_reject_reason}"
    assert signal.direction == "long"
    assert signal.confidence == pytest.approx(0.70)
    assert "event_CHINA_PMI" in signal.reason_tags
    assert "tier_2" in signal.reason_tags


def test_setup_c_no_signal_china_pmi_outside_window():
    """Setup C returns None when China PMI is older than window_minutes."""
    pmi_at = datetime(2026, 2, 27, 9, 0, 0, tzinfo=KST)
    evt = _evt("china_pmi_2026_feb", "CHINA_PMI", pmi_at, impact_tier=2)
    # 20 minutes later — outside the default 15-minute window
    now = datetime(2026, 2, 27, 9, 20, 0, tzinfo=KST)
    ctx = _ctx_with_long_breakout(now, [evt])

    setup = SetupCEventReaction()
    signal = setup.check(ctx)

    assert signal is None
    assert "no_event_in_window" in (setup.last_reject_reason or "")


# ---------------------------------------------------------------------------
# KOSPI200 rebalance tests (09:00 KST, tier 2)
# ---------------------------------------------------------------------------


def test_setup_c_fires_on_kospi200_rebalance():
    """Setup C fires on KOSPI200 rebalance effective day open (09:00 KST)."""
    rebal_at = datetime(2026, 3, 12, 9, 0, 0, tzinfo=KST)
    evt = _evt("kospi200_rebalance_2026_mar", "KOSPI200_REBALANCE", rebal_at, impact_tier=2)
    now = datetime(2026, 3, 12, 9, 8, 0, tzinfo=KST)
    ctx = _ctx_with_short_breakout(now, [evt])

    setup = SetupCEventReaction()
    signal = setup.check(ctx)

    assert signal is not None, f"Expected signal, got reject: {setup.last_reject_reason}"
    assert "event_KOSPI200_REBALANCE" in signal.reason_tags


# ---------------------------------------------------------------------------
# Out-of-session events (FOMC / US CPI / NFP) must NOT fire Setup C
# ---------------------------------------------------------------------------


def test_setup_c_does_not_fire_on_fomc_during_kr_session():
    """FOMC at 03:00 KST (pre-session) is already >6 hours stale at 09:05 KST."""
    fomc_at = datetime(2026, 1, 29, 4, 0, 0, tzinfo=KST)  # 04:00 KST pre-session
    evt = _evt("fomc_2026_jan", "FOMC_rate_decision", fomc_at, impact_tier=1)
    # Check at 09:05 KST: 5h5min elapsed >> window_minutes=15
    now = datetime(2026, 1, 29, 9, 5, 0, tzinfo=KST)
    ctx = _ctx_with_long_breakout(now, [evt])

    setup = SetupCEventReaction()
    signal = setup.check(ctx)

    assert signal is None
    assert "no_event_in_window" in (setup.last_reject_reason or "")


def test_setup_c_does_not_fire_on_us_cpi_during_kr_session():
    """US CPI at 22:30 KST is in the future during the KR morning session."""
    # US CPI fires at 22:30 KST — it hasn't happened yet during the 09:05 KST check
    cpi_at = datetime(2026, 4, 10, 22, 30, 0, tzinfo=KST)  # 22:30 KST
    evt = _evt("us_cpi_2026_apr", "US_CPI", cpi_at, impact_tier=1)
    # Check at 09:05 KST same day — event is in the FUTURE
    now = datetime(2026, 4, 10, 9, 5, 0, tzinfo=KST)
    ctx = _ctx_with_long_breakout(now, [evt])

    setup = SetupCEventReaction()
    signal = setup.check(ctx)

    assert signal is None
    assert "no_event_in_window" in (setup.last_reject_reason or "")


# ---------------------------------------------------------------------------
# KR CPI (tier 3) must be filtered by min_impact_tier=2
# ---------------------------------------------------------------------------


def test_setup_c_filters_kr_cpi_tier3():
    """KR CPI at tier 3 is excluded by the default min_impact_tier=2 filter."""
    # Even if we put it at 08:55 KST (barely within the 15-min window for a 09:00 check),
    # tier 3 is > min_impact_tier=2 so it is rejected.
    cpi_at = datetime(2026, 1, 30, 8, 55, 0, tzinfo=KST)
    evt = _evt("kr_cpi_2026_feb", "KR_CPI_RELEASE", cpi_at, impact_tier=3)
    now = datetime(2026, 1, 30, 9, 5, 0, tzinfo=KST)  # 10 min elapsed — within window_minutes
    ctx = _ctx_with_long_breakout(now, [evt])

    setup = SetupCEventReaction()
    signal = setup.check(ctx)

    assert signal is None
    assert "no_event_in_window" in (setup.last_reject_reason or "")


# ---------------------------------------------------------------------------
# Late-session cutoff (360 min = 15:00 KST)
# ---------------------------------------------------------------------------


def test_setup_c_cutoff_after_15h00_kst():
    """Setup C rejects entries after 15:00 KST even with a valid in-session event."""
    bok_at = datetime(2026, 1, 16, 10, 0, 0, tzinfo=KST)
    evt = _evt("bok_2026_jan", "BOK_rate_decision", bok_at, impact_tier=1)
    # Put the event 5 min before now so it's in window
    now = datetime(2026, 1, 16, 15, 5, 0, tzinfo=KST)
    # Re-anchor the event to be within 5 minutes of now (but still after 09:00)
    evt_recent = _evt("bok_2026_jan_late", "BOK_rate_decision",
                      datetime(2026, 1, 16, 15, 1, 0, tzinfo=KST), impact_tier=1)
    ctx = _ctx_with_long_breakout(now, [evt_recent])

    setup = SetupCEventReaction()
    signal = setup.check(ctx)

    assert signal is None
    assert "after_cutoff" in (setup.last_reject_reason or "")
