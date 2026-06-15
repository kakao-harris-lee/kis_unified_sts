"""Tests for SetupCEventReaction — TDD step 1 (written before implementation).

Test cases
----------
a) Event in window + breakout above 15m high + buffer OK → emits long Signal,
   marks event as traded
b) Event in window + breakout below 15m low + buffer OK → emits short Signal
c) No event in window → None
d) Same event_id already in tracker → None (even if breakout is valid)
e) Breakout exceeds buffer (current_price - last_15min_high >= buffer) → None
f) Event tier > min_impact_tier → None (handled by find_recent_event; still verify)
g) Confidence formula correctness for tiers 1, 2, 3
h) valid_until is ctx.now + timedelta(minutes=signal_ttl_minutes)
i) reason_tags contain all three expected tags
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from shared.decision.context import MarketContext, ScheduledEvent
from shared.decision.setups.event_reaction import (
    EventTradeTracker,
    SetupCConfig,
    SetupCEventReaction,
)

KST = ZoneInfo("Asia/Seoul")
UTC = ZoneInfo("UTC")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(
    event_id: str = "fomc_2026_may",
    event_type: str = "FOMC_rate_decision",
    minutes_ago: float = 5.0,
    impact_tier: int = 1,
    now: datetime | None = None,
) -> ScheduledEvent:
    """Build a ScheduledEvent that occurred ``minutes_ago`` before *now*."""
    if now is None:
        now = datetime(2026, 5, 1, 14, 0, 0, tzinfo=KST)
    scheduled_at = now - timedelta(minutes=minutes_ago)
    return ScheduledEvent(
        event_id=event_id,
        event_type=event_type,
        scheduled_at=scheduled_at,
        impact_tier=impact_tier,
    )


def _ctx(
    *,
    now: datetime | None = None,
    symbol: str = "A05603",
    current_price: float = 350.50,
    last_15min_high: float = 350.00,
    last_15min_low: float = 348.00,
    atr_14: float = 1.0,
    scheduled_events: list[ScheduledEvent] | None = None,
    prev_close: float = 349.00,
    today_open: float = 349.50,
    vwap: float = 349.75,
    atr_90th_percentile: float = 1.2,
    current_spread_ticks: float = 1.0,
) -> MarketContext:
    if now is None:
        now = datetime(2026, 5, 1, 14, 0, 0, tzinfo=KST)
    if scheduled_events is None:
        scheduled_events = []
    return MarketContext(
        now=now,
        symbol=symbol,
        current_price=current_price,
        prev_close=prev_close,
        today_open=today_open,
        vwap=vwap,
        atr_14=atr_14,
        atr_90th_percentile=atr_90th_percentile,
        last_15min_high=last_15min_high,
        last_15min_low=last_15min_low,
        current_spread_ticks=current_spread_ticks,
        macro_overnight=None,
        scheduled_events=scheduled_events,
    )


def _default_config() -> SetupCConfig:
    """Return default SetupCConfig (mirrors spec defaults)."""
    return SetupCConfig()


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestSetupCEventReaction:
    """Test SetupCEventReaction logic according to spec §5.1."""

    # (a) Long breakout happy path
    def test_long_breakout_emits_signal_and_marks_event(self) -> None:
        """Event in window + price above 15m-high within buffer → long Signal; event marked."""
        cfg = _default_config()
        tracker = EventTradeTracker()
        setup = SetupCEventReaction(config=cfg, tracker=tracker)

        now = datetime(2026, 5, 1, 14, 0, 0, tzinfo=KST)
        event = _make_event(minutes_ago=5.0, impact_tier=1, now=now)

        # current_price just above last_15min_high, within buffer (0.5 ATR = 0.5)
        # last_15min_high=350.00, atr=1.0, buffer=0.5 → price must be in (350.00, 350.50)
        ctx = _ctx(
            now=now,
            current_price=350.30,
            last_15min_high=350.00,
            last_15min_low=348.00,
            atr_14=1.0,
            scheduled_events=[event],
        )

        signal = setup.check(ctx)

        assert signal is not None, "Expected a long Signal"
        assert signal.direction == "long"
        assert signal.entry_price == 350.30
        # stop = opposite edge − stop_buffer_atr_mult(0.5)×atr(1.0) = 348.00 − 0.5
        assert signal.stop_loss == ctx.last_15min_low - 0.5 * ctx.atr_14  # 347.50
        # target = entry + target_atr_mult * atr = 350.30 + 2.5 * 1.0 = 352.80
        assert signal.take_profit == pytest.approx(352.80)
        # Event is now marked as traded
        assert tracker.already_traded(event.event_id)

    # (b) Short breakout happy path
    def test_short_breakout_emits_signal(self) -> None:
        """Event in window + price below 15m-low within buffer → short Signal."""
        cfg = _default_config()
        tracker = EventTradeTracker()
        setup = SetupCEventReaction(config=cfg, tracker=tracker)

        now = datetime(2026, 5, 1, 14, 0, 0, tzinfo=KST)
        event = _make_event(minutes_ago=8.0, impact_tier=2, now=now)

        # last_15min_low=348.00, atr=1.0, buffer=0.5 → price must be in (347.50, 348.00)
        ctx = _ctx(
            now=now,
            current_price=347.70,
            last_15min_high=350.00,
            last_15min_low=348.00,
            atr_14=1.0,
            scheduled_events=[event],
        )

        signal = setup.check(ctx)

        assert signal is not None, "Expected a short Signal"
        assert signal.direction == "short"
        assert signal.entry_price == 347.70
        # stop = opposite edge + stop_buffer_atr_mult(0.5)×atr(1.0) = 350.00 + 0.5
        assert signal.stop_loss == ctx.last_15min_high + 0.5 * ctx.atr_14  # 350.50
        # target = entry - target_atr_mult * atr = 347.70 - 2.5 * 1.0 = 345.20
        assert signal.take_profit == pytest.approx(345.20)
        assert tracker.already_traded(event.event_id)

    # (c) No event in window → None
    def test_no_event_in_window_returns_none(self) -> None:
        """No ScheduledEvent within window_minutes → None, even if breakout would be valid."""
        cfg = _default_config()
        setup = SetupCEventReaction(config=cfg)

        now = datetime(2026, 5, 1, 14, 0, 0, tzinfo=KST)
        # Event happened 20 minutes ago — outside default window_minutes=15
        event = _make_event(minutes_ago=20.0, impact_tier=1, now=now)

        ctx = _ctx(
            now=now,
            current_price=350.30,
            last_15min_high=350.00,
            last_15min_low=348.00,
            atr_14=1.0,
            scheduled_events=[event],
        )

        assert setup.check(ctx) is None

    # (c-2) Completely empty scheduled_events
    def test_empty_scheduled_events_returns_none(self) -> None:
        cfg = _default_config()
        setup = SetupCEventReaction(config=cfg)
        ctx = _ctx(
            current_price=350.30,
            last_15min_high=350.00,
            last_15min_low=348.00,
            atr_14=1.0,
        )
        assert setup.check(ctx) is None

    # (d) Same event_id already in tracker → None
    def test_already_traded_event_returns_none(self) -> None:
        """If event_id is already marked as traded, return None even if breakout is valid."""
        cfg = _default_config()
        tracker = EventTradeTracker()
        setup = SetupCEventReaction(config=cfg, tracker=tracker)

        now = datetime(2026, 5, 1, 14, 0, 0, tzinfo=KST)
        event = _make_event(minutes_ago=5.0, impact_tier=1, now=now)

        # Pre-mark this event as traded
        tracker.mark(event.event_id)

        ctx = _ctx(
            now=now,
            current_price=350.30,
            last_15min_high=350.00,
            last_15min_low=348.00,
            atr_14=1.0,
            scheduled_events=[event],
        )

        assert setup.check(ctx) is None

    # (e) Breakout exceeds buffer → None
    def test_long_breakout_exceeds_buffer_returns_none(self) -> None:
        """current_price - last_15min_high >= buffer → None (breakout too far)."""
        cfg = _default_config()
        setup = SetupCEventReaction(config=cfg)

        now = datetime(2026, 5, 1, 14, 0, 0, tzinfo=KST)
        event = _make_event(minutes_ago=5.0, impact_tier=1, now=now)

        # buffer = 0.5 * 1.0 = 0.5
        # current_price - last_15min_high = 350.60 - 350.00 = 0.60 >= 0.5 → reject
        ctx = _ctx(
            now=now,
            current_price=350.60,
            last_15min_high=350.00,
            last_15min_low=348.00,
            atr_14=1.0,
            scheduled_events=[event],
        )

        assert setup.check(ctx) is None

    def test_short_breakout_exceeds_buffer_returns_none(self) -> None:
        """last_15min_low - current_price >= buffer → None."""
        cfg = _default_config()
        setup = SetupCEventReaction(config=cfg)

        now = datetime(2026, 5, 1, 14, 0, 0, tzinfo=KST)
        event = _make_event(minutes_ago=5.0, impact_tier=1, now=now)

        # buffer = 0.5 * 1.0 = 0.5
        # last_15min_low - current_price = 348.00 - 347.40 = 0.60 >= 0.5 → reject
        ctx = _ctx(
            now=now,
            current_price=347.40,
            last_15min_high=350.00,
            last_15min_low=348.00,
            atr_14=1.0,
            scheduled_events=[event],
        )

        assert setup.check(ctx) is None

    # (f) Event tier > min_impact_tier → None
    def test_event_tier_exceeds_min_impact_tier_returns_none(self) -> None:
        """Events with impact_tier > min_impact_tier (default=2) are ignored."""
        cfg = _default_config()  # min_impact_tier=2
        setup = SetupCEventReaction(config=cfg)

        now = datetime(2026, 5, 1, 14, 0, 0, tzinfo=KST)
        # tier 3 > min_impact_tier 2 → find_recent_event will exclude it
        event = _make_event(minutes_ago=5.0, impact_tier=3, now=now)

        ctx = _ctx(
            now=now,
            current_price=350.30,
            last_15min_high=350.00,
            last_15min_low=348.00,
            atr_14=1.0,
            scheduled_events=[event],
        )

        assert setup.check(ctx) is None

    # (g) Confidence formula correctness for tiers 1, 2, 3
    def test_confidence_tier1(self) -> None:
        """Tier 1 event → confidence = 0.65 + 0.1 * (3 - 1) / 2 = 0.75."""
        cfg = _default_config()
        tracker = EventTradeTracker()
        setup = SetupCEventReaction(config=cfg, tracker=tracker)

        now = datetime(2026, 5, 1, 14, 0, 0, tzinfo=KST)
        event = _make_event(minutes_ago=5.0, impact_tier=1, now=now)
        ctx = _ctx(
            now=now,
            current_price=350.30,
            last_15min_high=350.00,
            last_15min_low=348.00,
            atr_14=1.0,
            scheduled_events=[event],
        )
        signal = setup.check(ctx)
        assert signal is not None
        assert signal.confidence == pytest.approx(0.75)

    def test_confidence_tier2(self) -> None:
        """Tier 2 event → confidence = 0.65 + 0.1 * (3 - 2) / 2 = 0.70."""
        cfg = _default_config()
        tracker = EventTradeTracker()
        setup = SetupCEventReaction(config=cfg, tracker=tracker)

        now = datetime(2026, 5, 1, 14, 0, 0, tzinfo=KST)
        event = _make_event(minutes_ago=5.0, impact_tier=2, now=now)
        ctx = _ctx(
            now=now,
            current_price=350.30,
            last_15min_high=350.00,
            last_15min_low=348.00,
            atr_14=1.0,
            scheduled_events=[event],
        )
        signal = setup.check(ctx)
        assert signal is not None
        assert signal.confidence == pytest.approx(0.70)

    def test_confidence_tier3(self) -> None:
        """Tier 3 event → confidence = 0.65 + 0.1 * (3 - 3) / 2 = 0.65.

        Note: tier 3 > min_impact_tier=2 by default, so we must use min_impact_tier=3
        to allow the event through.
        """
        cfg = SetupCConfig(min_impact_tier=3)  # allow tier 3
        tracker = EventTradeTracker()
        setup = SetupCEventReaction(config=cfg, tracker=tracker)

        now = datetime(2026, 5, 1, 14, 0, 0, tzinfo=KST)
        event = _make_event(minutes_ago=5.0, impact_tier=3, now=now)
        ctx = _ctx(
            now=now,
            current_price=350.30,
            last_15min_high=350.00,
            last_15min_low=348.00,
            atr_14=1.0,
            scheduled_events=[event],
        )
        signal = setup.check(ctx)
        assert signal is not None
        assert signal.confidence == pytest.approx(0.65)

    # (h) valid_until correctness
    def test_valid_until_equals_now_plus_ttl(self) -> None:
        """valid_until must equal ctx.now + timedelta(minutes=signal_ttl_minutes)."""
        cfg = SetupCConfig(signal_ttl_minutes=30)
        tracker = EventTradeTracker()
        setup = SetupCEventReaction(config=cfg, tracker=tracker)

        now = datetime(2026, 5, 1, 14, 0, 0, tzinfo=KST)
        event = _make_event(minutes_ago=5.0, impact_tier=1, now=now)
        ctx = _ctx(
            now=now,
            current_price=350.30,
            last_15min_high=350.00,
            last_15min_low=348.00,
            atr_14=1.0,
            scheduled_events=[event],
        )
        signal = setup.check(ctx)
        assert signal is not None
        expected_valid_until = now + timedelta(minutes=30)
        assert signal.valid_until == expected_valid_until

    # (i) reason_tags contain all three expected tags
    def test_reason_tags_contain_all_expected_tags(self) -> None:
        """reason_tags must include event_{type}, tier_{tier}, and breakout_15m."""
        cfg = _default_config()
        tracker = EventTradeTracker()
        setup = SetupCEventReaction(config=cfg, tracker=tracker)

        now = datetime(2026, 5, 1, 14, 0, 0, tzinfo=KST)
        event = _make_event(
            event_id="fomc_2026_may",
            event_type="FOMC_rate_decision",
            minutes_ago=5.0,
            impact_tier=1,
            now=now,
        )
        ctx = _ctx(
            now=now,
            current_price=350.30,
            last_15min_high=350.00,
            last_15min_low=348.00,
            atr_14=1.0,
            scheduled_events=[event],
        )
        signal = setup.check(ctx)
        assert signal is not None

        tags = list(signal.reason_tags)
        assert "event_FOMC_rate_decision" in tags
        assert "tier_1" in tags
        assert "breakout_15m" in tags

    # Additional: setup_type correctness
    def test_setup_type_is_c_event_reaction(self) -> None:
        """Emitted signal has setup_type='C_event_reaction'."""
        cfg = _default_config()
        tracker = EventTradeTracker()
        setup = SetupCEventReaction(config=cfg, tracker=tracker)

        now = datetime(2026, 5, 1, 14, 0, 0, tzinfo=KST)
        event = _make_event(minutes_ago=5.0, impact_tier=1, now=now)
        ctx = _ctx(
            now=now,
            current_price=350.30,
            last_15min_high=350.00,
            last_15min_low=348.00,
            atr_14=1.0,
            scheduled_events=[event],
        )
        signal = setup.check(ctx)
        assert signal is not None
        assert signal.setup_type == "C_event_reaction"

    # Additional: price at exact 15m-high boundary (not a breakout)
    def test_price_at_15min_high_boundary_returns_none(self) -> None:
        """Price == last_15min_high is not a breakout (must be strictly above)."""
        cfg = _default_config()
        setup = SetupCEventReaction(config=cfg)

        now = datetime(2026, 5, 1, 14, 0, 0, tzinfo=KST)
        event = _make_event(minutes_ago=5.0, impact_tier=1, now=now)
        ctx = _ctx(
            now=now,
            current_price=350.00,  # exactly at the 15m high
            last_15min_high=350.00,
            last_15min_low=348.00,
            atr_14=1.0,
            scheduled_events=[event],
        )
        assert setup.check(ctx) is None


class TestSetupCRejectReason:
    """Observability: check() records WHY it rejected, clears on fired signal."""

    def test_no_event_in_window_reason(self) -> None:
        setup = SetupCEventReaction(config=_default_config())
        now = datetime(2026, 5, 1, 14, 0, 0, tzinfo=KST)
        assert setup.check(_ctx(now=now, scheduled_events=[])) is None
        assert setup.last_reject_reason.startswith("no_event_in_window")

    def test_after_cutoff_reason(self) -> None:
        setup = SetupCEventReaction(config=_default_config())
        now = datetime(2026, 5, 1, 15, 30, 0, tzinfo=KST)  # 390 min > 360 cutoff
        event = _make_event(minutes_ago=5.0, now=now)
        assert setup.check(_ctx(now=now, scheduled_events=[event])) is None
        assert setup.last_reject_reason.startswith("after_cutoff")

    def test_fired_clears_reason(self) -> None:
        setup = SetupCEventReaction(config=_default_config())
        now = datetime(2026, 5, 1, 14, 0, 0, tzinfo=KST)
        event = _make_event(minutes_ago=5.0, impact_tier=1, now=now)
        sig = setup.check(
            _ctx(
                now=now,
                current_price=350.30,
                last_15min_high=350.00,
                last_15min_low=348.00,
                atr_14=1.0,
                scheduled_events=[event],
            )
        )
        assert sig is not None
        assert setup.last_reject_reason is None


class TestEventTradeTracker:
    """Unit tests for the in-memory EventTradeTracker."""

    def test_new_tracker_has_no_traded_events(self) -> None:
        tracker = EventTradeTracker()
        assert not tracker.already_traded("any_event_id")

    def test_mark_then_already_traded_returns_true(self) -> None:
        tracker = EventTradeTracker()
        tracker.mark("fomc_2026_may")
        assert tracker.already_traded("fomc_2026_may")

    def test_mark_does_not_affect_other_events(self) -> None:
        tracker = EventTradeTracker()
        tracker.mark("fomc_2026_may")
        assert not tracker.already_traded("us_cpi_2026_05")

    def test_mark_idempotent(self) -> None:
        """Marking the same event twice is safe and still reads as traded."""
        tracker = EventTradeTracker()
        tracker.mark("fomc_2026_may")
        tracker.mark("fomc_2026_may")
        assert tracker.already_traded("fomc_2026_may")

    def test_multiple_events_tracked_independently(self) -> None:
        tracker = EventTradeTracker()
        tracker.mark("event_a")
        tracker.mark("event_b")
        assert tracker.already_traded("event_a")
        assert tracker.already_traded("event_b")
        assert not tracker.already_traded("event_c")
