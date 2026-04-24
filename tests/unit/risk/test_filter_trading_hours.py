# tests/unit/risk/test_filter_trading_hours.py
"""TDD tests for TradingHoursFilter.

Written BEFORE implementation (red phase).  Each test case covers a distinct
scenario: pass, reject, boundary, multi-window.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from shared.decision.signal import Signal
from shared.risk.filters.trading_hours import TradingHoursFilter
from shared.risk.state import RiskStateSnapshot

# KST = UTC+9
KST = timezone(timedelta(hours=9))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_signal(kst_hour: int, kst_minute: int, kst_second: int = 0) -> Signal:
    """Create a Signal with ``generated_at`` set to a specific KST clock time.

    The date is fixed at 2026-04-22 (Tuesday) — a regular trading day.
    """
    generated_at = datetime(2026, 4, 22, kst_hour, kst_minute, kst_second, tzinfo=KST)
    return Signal(
        setup_type="test_setup",
        direction="long",
        symbol="A05603",
        entry_price=360.0,
        stop_loss=355.0,
        take_profit=370.0,
        confidence=0.8,
        generated_at=generated_at,
    )


def _make_snapshot() -> RiskStateSnapshot:
    return RiskStateSnapshot()


# ---------------------------------------------------------------------------
# Filter instantiation
# ---------------------------------------------------------------------------


def test_trading_hours_filter_name():
    f = TradingHoursFilter(trading_windows=["09:00-10:30"])
    assert f.name == "trading_hours"


def test_trading_hours_filter_stores_windows():
    """Constructor stores the trading window strings for later use."""
    windows = ["09:00-10:30", "14:30-15:20"]
    f = TradingHoursFilter(trading_windows=windows)
    assert f.trading_windows == windows


# ---------------------------------------------------------------------------
# Single-window: signal inside window  →  PASS
# ---------------------------------------------------------------------------


def test_pass_signal_inside_single_window():
    """09:30 is inside 09:00-10:30 → passed=True."""
    f = TradingHoursFilter(trading_windows=["09:00-10:30"])
    signal = _make_signal(9, 30)
    result = f.check(signal, _make_snapshot())
    assert result.passed is True
    assert result.filter_name == "trading_hours"
    assert result.skip_reason is None


# ---------------------------------------------------------------------------
# Single-window: signal outside window  →  REJECT
# ---------------------------------------------------------------------------


def test_reject_signal_outside_single_window():
    """11:00 is outside 09:00-10:30 → passed=False, skip_reason='outside_trading_hours'."""
    f = TradingHoursFilter(trading_windows=["09:00-10:30"])
    signal = _make_signal(11, 0)
    result = f.check(signal, _make_snapshot())
    assert result.passed is False
    assert result.filter_name == "trading_hours"
    assert result.skip_reason == "outside_trading_hours"


# ---------------------------------------------------------------------------
# Boundary tests — window is [start, end) half-open
# ---------------------------------------------------------------------------


def test_pass_signal_exactly_at_window_start():
    """09:00:00 is the first moment of [09:00, 10:30) → should pass."""
    f = TradingHoursFilter(trading_windows=["09:00-10:30"])
    signal = _make_signal(9, 0, 0)
    result = f.check(signal, _make_snapshot())
    assert result.passed is True


def test_reject_signal_exactly_at_window_end():
    """10:30:00 is the moment AFTER the half-open window [09:00, 10:30) → should reject."""
    f = TradingHoursFilter(trading_windows=["09:00-10:30"])
    signal = _make_signal(10, 30, 0)
    result = f.check(signal, _make_snapshot())
    assert result.passed is False
    assert result.skip_reason == "outside_trading_hours"


def test_pass_signal_one_second_before_window_end():
    """10:29:59 is still inside [09:00, 10:30) → pass."""
    f = TradingHoursFilter(trading_windows=["09:00-10:30"])
    signal = _make_signal(10, 29, 59)
    result = f.check(signal, _make_snapshot())
    assert result.passed is True


# ---------------------------------------------------------------------------
# Multi-window tests
# ---------------------------------------------------------------------------


def test_pass_signal_in_first_of_two_windows():
    """09:10 is inside first window [09:00-10:30] with a second window also present."""
    f = TradingHoursFilter(trading_windows=["09:00-10:30", "14:30-15:20"])
    signal = _make_signal(9, 10)
    result = f.check(signal, _make_snapshot())
    assert result.passed is True


def test_pass_signal_in_second_of_two_windows():
    """15:00 is inside second window [14:30-15:20]."""
    f = TradingHoursFilter(trading_windows=["09:00-10:30", "14:30-15:20"])
    signal = _make_signal(15, 0)
    result = f.check(signal, _make_snapshot())
    assert result.passed is True


def test_reject_signal_between_two_windows():
    """12:00 falls between [09:00-10:30] and [14:30-15:20] → rejected."""
    f = TradingHoursFilter(trading_windows=["09:00-10:30", "14:30-15:20"])
    signal = _make_signal(12, 0)
    result = f.check(signal, _make_snapshot())
    assert result.passed is False
    assert result.skip_reason == "outside_trading_hours"


# ---------------------------------------------------------------------------
# Empty windows list — every signal rejected
# ---------------------------------------------------------------------------


def test_reject_when_no_windows_configured():
    """Empty trading_windows means no time is ever valid."""
    f = TradingHoursFilter(trading_windows=[])
    signal = _make_signal(10, 0)
    result = f.check(signal, _make_snapshot())
    assert result.passed is False
    assert result.skip_reason == "outside_trading_hours"


# ---------------------------------------------------------------------------
# UTC signal is correctly converted to KST
# ---------------------------------------------------------------------------


def test_utc_signal_converted_to_kst():
    """A UTC signal at 00:30 UTC = 09:30 KST → passes [09:00-10:30]."""
    generated_at = datetime(2026, 4, 22, 0, 30, tzinfo=UTC)
    signal = Signal(
        setup_type="test_setup",
        direction="long",
        symbol="A05603",
        entry_price=360.0,
        stop_loss=355.0,
        take_profit=370.0,
        confidence=0.8,
        generated_at=generated_at,
    )
    f = TradingHoursFilter(trading_windows=["09:00-10:30"])
    result = f.check(signal, _make_snapshot())
    assert result.passed is True
