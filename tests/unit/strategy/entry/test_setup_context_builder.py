"""Regression: setup MarketContext must not shift a naive KST bar timestamp +9h.

`build_setup_market_context` (used by Setup A/C/D adapters) once labeled a naive
timestamp as UTC and `astimezone(KST)`'d it, adding +9h. Backtest bars are naive
**KST** wall-clock, so a 09:10 bar became 18:10 → `minutes_since_open()` = 565 →
every bar tripped the setups' time-window cutoff → 0 trades. Live was unaffected
(orchestrator passes tz-aware UTC). This pins naive→KST for the setup path.
"""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from shared.strategy.base import EntryContext
from shared.strategy.entry.setup_context_builder import build_setup_market_context

KST = ZoneInfo("Asia/Seoul")

_MARKET_DATA = {
    "code": "101S6000",
    "close": 350.0,
    "current_price": 350.0,
    "open": 349.0,
    "prev_close": 348.0,
    "atr": 2.0,
    "vwap": 350.0,
}

# setup_d cutoff (no_entry_after_minutes_since_open); the bug produced 565 > 345.
_SETUP_CUTOFF_MIN = 345


def test_naive_bar_timestamp_is_treated_as_kst_not_utc() -> None:
    """A naive 09:10 bar stays 09:10 KST — not shifted to 18:10 (+9h)."""
    ctx = EntryContext(
        market_data=dict(_MARKET_DATA), timestamp=datetime(2026, 1, 5, 9, 10)
    )
    mc = build_setup_market_context(ctx)
    assert mc is not None
    # The context's KST `now` must equal the input wall-clock (config-independent).
    assert (mc.now.hour, mc.now.minute) == (9, 10)
    # And the morning bar sits well inside the entry window, not past the cutoff.
    assert mc.minutes_since_open() < _SETUP_CUTOFF_MIN
    # Sanity: with the canonical 08:45 open it is exactly 25 minutes.
    assert mc.minutes_since_open() == 25.0


def test_late_morning_bar_no_longer_reads_as_after_cutoff() -> None:
    """An 11:00 bar → 135 min since open (in-window), not 675 (the +9h artifact)."""
    ctx = EntryContext(
        market_data=dict(_MARKET_DATA), timestamp=datetime(2026, 1, 5, 11, 0)
    )
    mc = build_setup_market_context(ctx)
    assert mc is not None
    assert mc.minutes_since_open() < _SETUP_CUTOFF_MIN


def test_tz_aware_utc_timestamp_still_converts_to_kst() -> None:
    """Live path: a tz-aware UTC instant converts correctly (00:10 UTC = 09:10 KST)."""
    ctx = EntryContext(
        market_data=dict(_MARKET_DATA),
        timestamp=datetime(2026, 1, 5, 0, 10, tzinfo=UTC),
    )
    mc = build_setup_market_context(ctx)
    assert mc is not None
    assert (mc.now.hour, mc.now.minute) == (9, 10)
    assert mc.minutes_since_open() == 25.0


def test_tz_aware_kst_timestamp_unchanged() -> None:
    """A tz-aware KST timestamp passes through unshifted."""
    ctx = EntryContext(
        market_data=dict(_MARKET_DATA),
        timestamp=datetime(2026, 1, 5, 9, 10, tzinfo=KST),
    )
    mc = build_setup_market_context(ctx)
    assert mc is not None
    assert (mc.now.hour, mc.now.minute) == (9, 10)
