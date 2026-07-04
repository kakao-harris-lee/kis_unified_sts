"""Thin interface contracts for decision-engine setup inputs."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from shared.decision.context import MarketContext, ScheduledEvent
from shared.decision.interfaces import (
    FuturesMarketView,
    ScheduledEventView,
    SetupSignalGenerator,
)
from shared.decision.setups.event_reaction import SetupCConfig, SetupCEventReaction
from shared.decision.setups.gap_reversion import SetupAConfig, SetupAGapReversion
from shared.decision.setups.vwap_reversion import SetupDConfig, SetupDVWAPReversion

KST = ZoneInfo("Asia/Seoul")


def _market_context(
    *,
    scheduled_events: list[ScheduledEvent] | None = None,
) -> MarketContext:
    return MarketContext(
        now=datetime(2026, 4, 23, 9, 30, tzinfo=KST),
        symbol="A05603",
        current_price=348.5,
        prev_close=350.0,
        today_open=347.0,
        vwap=348.0,
        atr_14=1.0,
        atr_90th_percentile=1.5,
        last_15min_high=349.0,
        last_15min_low=347.5,
        current_spread_ticks=1.0,
        macro_overnight=None,
        scheduled_events=scheduled_events or [],
    )


def test_market_context_satisfies_futures_market_view() -> None:
    ctx = _market_context()

    assert isinstance(ctx, FuturesMarketView)

    view: FuturesMarketView = ctx
    assert view.symbol == "A05603"
    assert view.current_price == pytest.approx(348.5)
    assert view.minutes_since_open() == pytest.approx(45.0)
    assert view.find_recent_event(window_minutes=15, min_tier=1) is None


def test_scheduled_event_satisfies_scheduled_event_view() -> None:
    event = ScheduledEvent(
        event_id="us_cpi",
        event_type="US_CPI",
        scheduled_at=datetime(2026, 4, 23, 9, 20, tzinfo=KST),
        impact_tier=1,
    )
    ctx: FuturesMarketView = _market_context(scheduled_events=[event])

    assert isinstance(event, ScheduledEventView)

    recent = ctx.find_recent_event(window_minutes=15, min_tier=1)
    assert recent is event
    assert recent.event_id == "us_cpi"


@pytest.mark.parametrize(
    "setup",
    [
        SetupAGapReversion(config=SetupAConfig()),
        SetupCEventReaction(config=SetupCConfig()),
        SetupDVWAPReversion(config=SetupDConfig()),
    ],
)
def test_existing_setup_classes_satisfy_signal_generator_contract(
    setup: SetupSignalGenerator,
) -> None:
    assert isinstance(setup, SetupSignalGenerator)

    signal = setup.check(_market_context())

    assert signal is None or signal.symbol == "A05603"
