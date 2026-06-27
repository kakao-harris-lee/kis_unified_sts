"""Edge case tests for VolumeAccumulationBreakoutEntry.

Covers the minute-overflow fix in _check_time_filter:
  Before the fix, if market_open_minute + skip_market_open_minutes >= 60 the
  code constructed time(hour=9, minute=75) which raises ValueError.
  After the fix the overflow is normalised:
    open_minute = 30 + 45 = 75 → hour += 75//60 = 1, minute = 75%60 = 15
    → time(10, 15)  (i.e. 09:00 + 1h15m = 10:15)
"""
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def _make_strategy(
    *,
    market_open_hour: int = 9,
    market_open_minute: int = 0,
    skip_market_open_minutes: int = 15,
    market_close_hour: int = 15,
    market_close_minute: int = 30,
    skip_market_close_minutes: int = 30,
    **kwargs,
):
    from shared.strategy.entry.volume_accumulation import (
        VolumeAccumulationBreakoutEntry,
        VolumeAccumulationConfig,
    )

    config = VolumeAccumulationConfig(
        market_open_hour=market_open_hour,
        market_open_minute=market_open_minute,
        skip_market_open_minutes=skip_market_open_minutes,
        market_close_hour=market_close_hour,
        market_close_minute=market_close_minute,
        skip_market_close_minutes=skip_market_close_minutes,
        **kwargs,
    )
    return VolumeAccumulationBreakoutEntry(config)


# ---------------------------------------------------------------------------
# Minute overflow tests
# ---------------------------------------------------------------------------


def test_time_filter_minute_overflow_no_value_error():
    """market_open_minute=30 + skip=45 → sum=75 must not raise ValueError.

    Before the fix, time(9, 75) raised ValueError.
    After the fix it normalises to time(10, 15).
    """
    strategy = _make_strategy(
        market_open_hour=9,
        market_open_minute=30,
        skip_market_open_minutes=45,  # 30+45 = 75 → overflow
    )

    # A timestamp well after 10:15 and before close buffer — should return True.
    ts = datetime(2026, 2, 18, 10, 30, 0, tzinfo=KST)

    # Must not raise ValueError
    result = strategy._check_time_filter(ts)
    assert result is True, (
        "Expected _check_time_filter to return True for 10:30 "
        "when effective open is 10:15 (09:30 + 45min skip)."
    )


def test_time_filter_minute_overflow_correct_open_time():
    """After normalisation the effective open should be 10:15 (not some wrong time)."""
    strategy = _make_strategy(
        market_open_hour=9,
        market_open_minute=30,
        skip_market_open_minutes=45,
    )

    # 10:14 is before effective open (10:15) → should be filtered out
    before_open = datetime(2026, 2, 18, 10, 14, 0, tzinfo=KST)
    assert strategy._check_time_filter(before_open) is False, (
        "10:14 should be before the effective open time of 10:15."
    )

    # 10:15 is exactly at effective open → should pass
    at_open = datetime(2026, 2, 18, 10, 15, 0, tzinfo=KST)
    assert strategy._check_time_filter(at_open) is True, (
        "10:15 should be allowed (exactly at effective open)."
    )

    # 10:16 is clearly within window → should pass
    after_open = datetime(2026, 2, 18, 10, 16, 0, tzinfo=KST)
    assert strategy._check_time_filter(after_open) is True


def test_time_filter_no_overflow_unchanged():
    """Normal case (no overflow) must still work correctly."""
    strategy = _make_strategy(
        market_open_hour=9,
        market_open_minute=0,
        skip_market_open_minutes=15,  # 0+15=15, no overflow
    )

    before = datetime(2026, 2, 18, 9, 14, 0, tzinfo=KST)
    assert strategy._check_time_filter(before) is False

    at = datetime(2026, 2, 18, 9, 15, 0, tzinfo=KST)
    assert strategy._check_time_filter(at) is True

    after = datetime(2026, 2, 18, 9, 30, 0, tzinfo=KST)
    assert strategy._check_time_filter(after) is True


def test_time_filter_exactly_60_minute_boundary():
    """Edge: market_open_minute=0 + skip=60 → sum=60 → overflow to next hour exactly."""
    strategy = _make_strategy(
        market_open_hour=9,
        market_open_minute=0,
        skip_market_open_minutes=60,  # exactly 1h skip → 10:00
    )

    before = datetime(2026, 2, 18, 9, 59, 59, tzinfo=KST)
    assert strategy._check_time_filter(before) is False

    at = datetime(2026, 2, 18, 10, 0, 0, tzinfo=KST)
    assert strategy._check_time_filter(at) is True


def test_time_filter_close_underflow_unchanged():
    """Close-side underflow (existing fix) still works: 30 - 45 = -15 → 29:45 → 14:45."""
    strategy = _make_strategy(
        market_close_hour=15,
        market_close_minute=30,
        skip_market_close_minutes=45,  # 30-45 = -15 → 14:45
    )

    after_close = datetime(2026, 2, 18, 14, 46, 0, tzinfo=KST)
    assert strategy._check_time_filter(after_close) is False

    before_close = datetime(2026, 2, 18, 14, 44, 0, tzinfo=KST)
    assert strategy._check_time_filter(before_close) is True
