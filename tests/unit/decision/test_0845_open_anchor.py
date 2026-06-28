"""Tests for the 08:45 KST futures regular-session open anchor.

Validates that all setups correctly anchor their time windows to the new
08:45 open, and that a MarketContext built without explicit open fields still
works (safe fallback to dataclass defaults).

Coverage
--------
- minutes_since_open() accuracy at key boundary times (0, 10, 15, 375 min).
- Setup A: rejected before 08:55, eligible at 08:56, rejected after 10:15.
- Setup C: eligible at 14:59 (375 min boundary), rejected at / after 15:00.
- Setup D: rejected at 08:55 (before_window < 15), rejected after 14:45 (> 360).
- Regression: a MarketContext constructed with no explicit open fields uses the
  08:45 default safely.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from shared.decision.context import MarketContext, ScheduledEvent, build_market_context
from shared.decision.setups.event_reaction import SetupCConfig, SetupCEventReaction
from shared.decision.setups.gap_reversion import SetupAConfig, SetupAGapReversion
from shared.decision.setups.vwap_reversion import SetupDConfig, SetupDVWAPReversion
from shared.macro.base import MacroSnapshot

KST = ZoneInfo("Asia/Seoul")

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_DATE = (2026, 6, 28)  # Arbitrary trading day


def _mc(
    h: int,
    m: int,
    *,
    current_price: float = 350.0,
    prev_close: float = 348.0,
    today_open: float = 349.0,
    vwap: float = 350.0,
    atr_14: float = 1.0,
    last_15min_high: float | None = None,
    last_15min_low: float | None = None,
    macro_overnight: object | None = None,
    scheduled_events: list[ScheduledEvent] | None = None,
    market_open_hour: int = 8,
    market_open_minute: int = 45,
) -> MarketContext:
    """Build a MarketContext fixed at *h:m* KST with the 08:45 open."""
    if last_15min_high is None:
        last_15min_high = current_price
    if last_15min_low is None:
        last_15min_low = current_price
    return MarketContext(
        now=datetime(*_DATE, h, m, tzinfo=KST),
        symbol="A05603",
        current_price=current_price,
        prev_close=prev_close,
        today_open=today_open,
        vwap=vwap,
        atr_14=atr_14,
        atr_90th_percentile=atr_14 * 1.5,
        last_15min_high=last_15min_high,
        last_15min_low=last_15min_low,
        current_spread_ticks=1.0,
        macro_overnight=macro_overnight,
        scheduled_events=scheduled_events or [],
        market_open_hour=market_open_hour,
        market_open_minute=market_open_minute,
    )


def _macro(pct: float) -> MacroSnapshot:
    return MacroSnapshot(
        ts_ms=1_700_000_000_000, session="overnight_us_close", sp500_change_pct=pct
    )


# ---------------------------------------------------------------------------
# minutes_since_open() — boundary values
# ---------------------------------------------------------------------------


def test_minutes_since_open_at_open_is_zero():
    """At exactly 08:45 KST the session is 0 minutes old."""
    ctx = _mc(8, 45)
    assert abs(ctx.minutes_since_open() - 0.0) < 0.01


def test_minutes_since_open_at_0855_is_10():
    """08:55 KST = 10 min since 08:45 open."""
    ctx = _mc(8, 55)
    assert abs(ctx.minutes_since_open() - 10.0) < 0.01


def test_minutes_since_open_at_0900_is_15():
    """09:00 KST = 15 min since 08:45 open."""
    ctx = _mc(9, 0)
    assert abs(ctx.minutes_since_open() - 15.0) < 0.01


def test_minutes_since_open_at_1500_is_375():
    """15:00 KST = 375 min since 08:45 open."""
    ctx = _mc(15, 0)
    assert abs(ctx.minutes_since_open() - 375.0) < 0.01


# ---------------------------------------------------------------------------
# Setup A — valid_minutes_min=10, valid_minutes_max=90
# ---------------------------------------------------------------------------
#
# With 08:45 open:
#   window start = 08:55 KST (08:45 + 10 min)
#   window end   = 10:15 KST (08:45 + 90 min)


def _setup_a() -> SetupAGapReversion:
    """Setup A with the research-calibrated YAML config values."""
    return SetupAGapReversion(
        config=SetupAConfig(
            valid_minutes_min=10,
            valid_minutes_max=90,
            min_sp500_gap_pct=0.5,
            min_kr_gap_pct=0.3,
            retrace_min=0.30,
            retrace_max=0.55,
        )
    )


def _gap_down_ctx(h: int, m: int) -> MarketContext:
    """A valid gap-down retrace context at *h:m* for Setup A fire testing."""
    return _mc(
        h,
        m,
        current_price=348.5,
        prev_close=350.0,
        today_open=347.0,
        atr_14=1.0,
        macro_overnight=_macro(-1.2),
    )


def test_setup_a_rejected_before_0855():
    """Before 08:55 (< 10 min since open) → rejected as outside_time_window."""
    setup = _setup_a()
    ctx = _gap_down_ctx(8, 50)  # 5 min since 08:45 — before window
    result = setup.check(ctx)
    assert result is None
    assert setup.last_reject_reason is not None
    assert "outside_time_window" in setup.last_reject_reason


def test_setup_a_eligible_at_0856():
    """08:56 (11 min since open, within [10, 90]) → fires (given other conditions)."""
    setup = _setup_a()
    ctx = _gap_down_ctx(8, 56)
    result = setup.check(ctx)
    assert (
        result is not None
    ), f"Expected Setup A signal at 08:56; rejected because: {setup.last_reject_reason}"


def test_setup_a_rejected_after_1015():
    """10:20 (95 min since open, > 90) → rejected as outside_time_window."""
    setup = _setup_a()
    ctx = _gap_down_ctx(10, 20)  # 95 min since 08:45 — after window
    result = setup.check(ctx)
    assert result is None
    assert setup.last_reject_reason is not None
    assert "outside_time_window" in setup.last_reject_reason


# ---------------------------------------------------------------------------
# Setup C — no_entry_after_minutes_since_open=375 (15:00 KST)
# ---------------------------------------------------------------------------


def _setup_c() -> SetupCEventReaction:
    return SetupCEventReaction(
        config=SetupCConfig(
            no_entry_after_minutes_since_open=375,
            window_minutes=15,
            breakout_buffer_atr_mult=0.5,
            target_atr_mult=2.5,
            stop_buffer_atr_mult=0.5,
        )
    )


def _event_at(h: int, m: int) -> ScheduledEvent:
    """Return a ScheduledEvent 10 minutes before *h:m* (handles hour roll)."""
    from datetime import timedelta

    t = datetime(*_DATE, h, m, tzinfo=KST) - timedelta(minutes=10)
    return ScheduledEvent(
        event_id="fomc_2026",
        event_type="FOMC",
        scheduled_at=t,
        impact_tier=1,
    )


def _event_ctx(h: int, m: int) -> MarketContext:
    """A breakout context with a recent qualifying event, valid for Setup C."""
    return _mc(
        h,
        m,
        current_price=352.0,  # above last_15min_high → breakout
        prev_close=348.0,
        today_open=349.0,
        last_15min_high=351.5,
        last_15min_low=348.0,
        atr_14=1.0,
        scheduled_events=[_event_at(h, m)],
    )


def test_setup_c_eligible_at_1459():
    """14:59 KST = 374 min since open < 375 cutoff → eligible (check fires if conditions met)."""
    setup = _setup_c()
    # 14:59 → 374 min < 375 → should NOT be rejected on the cutoff alone.
    ctx = _event_ctx(14, 59)
    result = setup.check(ctx)
    # If it fires, great. If it doesn't, it must NOT be because of after_cutoff.
    if result is None:
        assert setup.last_reject_reason is not None
        assert (
            "after_cutoff" not in setup.last_reject_reason
        ), f"14:59 should NOT be after_cutoff (374 < 375); got: {setup.last_reject_reason}"


def test_setup_c_rejected_after_1500():
    """15:01 KST = 376 min since open > 375 cutoff → rejected as after_cutoff.

    Note: the cutoff check uses strict >; 15:00 exactly (375 == 375) still passes.
    The cutoff blocks entries strictly *after* 15:00.
    """
    setup = _setup_c()
    ctx = _event_ctx(15, 1)
    result = setup.check(ctx)
    assert result is None
    assert setup.last_reject_reason is not None
    assert (
        "after_cutoff" in setup.last_reject_reason
    ), f"15:01 should be after_cutoff (376 > 375); got: {setup.last_reject_reason}"


# ---------------------------------------------------------------------------
# Setup D — valid_minutes_min=15, no_entry_after_minutes_since_open=360 (14:45 KST)
# ---------------------------------------------------------------------------


def _setup_d() -> SetupDVWAPReversion:
    return SetupDVWAPReversion(
        config=SetupDConfig(
            valid_minutes_min=15,
            no_entry_after_minutes_since_open=360,
        )
    )


def _warm_d(setup: SetupDVWAPReversion, atr: float = 1.0, n: int = 200) -> None:
    """Feed calm bars to warm up the vol window so the vol gate doesn't block."""
    for _i in range(n):
        ctx = _mc(10, 0, current_price=100.0, vwap=100.0, atr_14=atr)
        setup.check(ctx)


def test_setup_d_rejected_at_0855_before_window():
    """08:55 KST = 10 min < valid_minutes_min=15 → before_window."""
    setup = _setup_d()
    ctx = _mc(8, 55, current_price=104.0, vwap=100.0, atr_14=1.0)
    result = setup.check(ctx)
    assert result is None
    assert setup.last_reject_reason is not None
    assert "before_window" in setup.last_reject_reason


def test_setup_d_rejected_after_1445():
    """14:50 KST = 365 min since 08:45 open > no_entry_after=360 → after_cutoff."""
    setup = _setup_d()
    ctx = _mc(14, 50, current_price=104.0, vwap=100.0, atr_14=1.0)
    result = setup.check(ctx)
    assert result is None
    assert setup.last_reject_reason is not None
    assert "after_cutoff" in setup.last_reject_reason


# ---------------------------------------------------------------------------
# Regression — MarketContext with no open fields uses 08:45 default safely
# ---------------------------------------------------------------------------


def test_default_open_is_0845():
    """A MarketContext with default market_open_hour/minute uses 08:45."""
    ctx = MarketContext(
        now=datetime(2026, 6, 28, 9, 0, tzinfo=KST),
        symbol="A05603",
        current_price=350.0,
        prev_close=348.0,
        today_open=349.0,
        vwap=350.0,
        atr_14=1.0,
        atr_90th_percentile=1.5,
        last_15min_high=350.0,
        last_15min_low=349.0,
        current_spread_ticks=1.0,
        macro_overnight=None,
        scheduled_events=[],
        # No market_open_hour / market_open_minute — should default to 8/45
    )
    # 09:00 KST = 15 min since 08:45 open
    assert abs(ctx.minutes_since_open() - 15.0) < 0.01
    assert ctx.market_open_time() == datetime(2026, 6, 28, 8, 45, tzinfo=KST)


def test_build_market_context_explicit_open_overrides_config(tmp_path):
    """Explicit market_open_hour/minute beat the config-file read."""
    ctx = build_market_context(
        now=datetime(2026, 6, 28, 9, 30, tzinfo=KST),
        symbol="A05603",
        current_price=350.0,
        prev_close=348.0,
        today_open=349.0,
        atr_14=1.0,
        last_15min_high=350.0,
        last_15min_low=349.0,
        market_open_hour=9,
        market_open_minute=0,
        config_path=str(tmp_path / "nonexistent.yaml"),  # ignored when explicit
    )
    # Explicit 09:00 open: 09:30 → 30 min
    assert abs(ctx.minutes_since_open() - 30.0) < 0.01
