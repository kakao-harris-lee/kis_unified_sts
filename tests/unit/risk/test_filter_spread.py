# tests/unit/risk/test_filter_spread.py
"""TDD tests for SpreadFilter.

Written BEFORE / alongside implementation (TDD red-green cycle).

The filter accepts a ``current_spread_provider`` callable and a
``max_spread_ticks`` threshold.  Tests supply a ``lambda: value`` to control
the current spread without touching live infrastructure.
"""

from __future__ import annotations

from shared.decision.signal import Signal
from shared.risk.filters.spread import SpreadFilter
from shared.risk.state import RiskStateSnapshot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MAX_SPREAD = 2.0  # ticks


def _make_signal(symbol: str = "A05603") -> Signal:
    return Signal(
        setup_type="test_setup",
        direction="long",
        symbol=symbol,
        entry_price=360.0,
        stop_loss=355.0,
        take_profit=370.0,
        confidence=0.8,
    )


def _make_snapshot() -> RiskStateSnapshot:
    return RiskStateSnapshot()


def _make_filter(
    current_spread: float, max_spread: float = _MAX_SPREAD
) -> SpreadFilter:
    """Return a SpreadFilter whose provider always returns *current_spread*."""
    return SpreadFilter(
        max_spread_ticks=max_spread,
        current_spread_provider=lambda: current_spread,
    )


# ---------------------------------------------------------------------------
# Filter metadata
# ---------------------------------------------------------------------------


def test_filter_name():
    f = _make_filter(current_spread=1.0)
    assert f.name == "spread"


def test_filter_stores_max_spread_ticks():
    f = SpreadFilter(max_spread_ticks=3.5, current_spread_provider=lambda: 0.0)
    assert f._max_spread_ticks == 3.5


def test_filter_stores_provider():
    provider = lambda: 1.0  # noqa: E731
    f = SpreadFilter(max_spread_ticks=_MAX_SPREAD, current_spread_provider=provider)
    assert f._current_spread_provider is provider


# ---------------------------------------------------------------------------
# Pass — spread < max_spread_ticks
# ---------------------------------------------------------------------------


def test_pass_when_spread_below_max():
    """Spread = 1.0 < max 2.0 → pass."""
    f = _make_filter(current_spread=1.0)
    result = f.check(_make_signal(), _make_snapshot())
    assert result.passed is True
    assert result.skip_reason is None
    assert result.filter_name == "spread"


def test_pass_when_spread_is_zero():
    """Spread = 0.0 → trivially below threshold → pass."""
    f = _make_filter(current_spread=0.0)
    result = f.check(_make_signal(), _make_snapshot())
    assert result.passed is True


def test_pass_when_spread_much_below_max():
    """Spread = 0.1 vs max 10.0 → pass."""
    f = _make_filter(current_spread=0.1, max_spread=10.0)
    result = f.check(_make_signal(), _make_snapshot())
    assert result.passed is True


# ---------------------------------------------------------------------------
# Boundary — spread == max_spread_ticks (strict > comparison → passes)
# ---------------------------------------------------------------------------


def test_pass_when_spread_exactly_equals_max():
    """Spread == max_spread_ticks: strict '>' so equality does NOT reject → pass."""
    f = _make_filter(current_spread=_MAX_SPREAD)
    result = f.check(_make_signal(), _make_snapshot())
    assert result.passed is True
    assert result.skip_reason is None


# ---------------------------------------------------------------------------
# Reject — spread > max_spread_ticks
# ---------------------------------------------------------------------------


def test_reject_when_spread_above_max():
    """Spread = 3.0 > max 2.0 → rejected."""
    f = _make_filter(current_spread=3.0)
    result = f.check(_make_signal(), _make_snapshot())
    assert result.passed is False
    assert result.skip_reason == "spread_too_wide"
    assert result.filter_name == "spread"


def test_reject_when_spread_just_above_max():
    """Spread = 2.001 → just above 2.0 → rejected."""
    f = _make_filter(current_spread=2.001)
    result = f.check(_make_signal(), _make_snapshot())
    assert result.passed is False
    assert result.skip_reason == "spread_too_wide"


def test_reject_when_spread_far_above_max():
    """Spread = 20.0, max = 2.0 → extreme spread → rejected."""
    f = _make_filter(current_spread=20.0)
    result = f.check(_make_signal(), _make_snapshot())
    assert result.passed is False
    assert result.skip_reason == "spread_too_wide"


# ---------------------------------------------------------------------------
# Provider is called on each check() invocation (not cached at construction)
# ---------------------------------------------------------------------------


def test_provider_called_on_each_check():
    """Verify the provider callable is invoked for every check, not cached."""
    call_count = [0]

    def counting_provider() -> float:
        call_count[0] += 1
        return 1.0  # always below threshold

    f = SpreadFilter(
        max_spread_ticks=_MAX_SPREAD,
        current_spread_provider=counting_provider,
    )
    snap = _make_snapshot()

    f.check(_make_signal(), snap)
    f.check(_make_signal(), snap)
    f.check(_make_signal(), snap)

    assert call_count[0] == 3


def test_provider_returns_different_values_over_time():
    """A stateful provider can change the filter result between calls."""
    spread_values = iter([1.0, 1.0, 3.0])  # first two pass, third rejects

    f = SpreadFilter(
        max_spread_ticks=_MAX_SPREAD,
        current_spread_provider=lambda: next(spread_values),
    )
    snap = _make_snapshot()

    assert f.check(_make_signal(), snap).passed is True
    assert f.check(_make_signal(), snap).passed is True
    assert f.check(_make_signal(), snap).passed is False


# ---------------------------------------------------------------------------
# size_multiplier is always 1.0 (filter does not reduce size, only rejects)
# ---------------------------------------------------------------------------


def test_pass_has_full_size_multiplier():
    f = _make_filter(current_spread=1.0)
    result = f.check(_make_signal(), _make_snapshot())
    assert result.size_multiplier == 1.0


def test_rejected_has_default_size_multiplier():
    f = _make_filter(current_spread=99.0)
    result = f.check(_make_signal(), _make_snapshot())
    assert result.size_multiplier == 1.0
