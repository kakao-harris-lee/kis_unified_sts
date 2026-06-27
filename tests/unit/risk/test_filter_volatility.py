# tests/unit/risk/test_filter_volatility.py
"""TDD tests for VolatilityFilter.

Written BEFORE / alongside implementation (TDD red-green cycle).

The filter accepts a ``current_atr_provider`` callable.  Tests supply a
``lambda: value`` to control the current ATR without touching live infrastructure.
"""

from __future__ import annotations

from shared.decision.signal import Signal
from shared.risk.filters.volatility import VolatilityFilter
from shared.risk.state import RiskStateSnapshot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PERCENTILE_90 = 5.0  # 90th-percentile ATR stored in state snapshot


def _make_signal() -> Signal:
    return Signal(
        setup_type="test_setup",
        direction="long",
        symbol="A05603",
        entry_price=360.0,
        stop_loss=355.0,
        take_profit=370.0,
        confidence=0.8,
    )


def _make_snapshot(atr_90th: float = _PERCENTILE_90) -> RiskStateSnapshot:
    return RiskStateSnapshot(atr_90th_percentile=atr_90th)


def _make_filter(current_atr: float) -> VolatilityFilter:
    """Return a VolatilityFilter whose provider always returns *current_atr*."""
    return VolatilityFilter(current_atr_provider=lambda: current_atr)


# ---------------------------------------------------------------------------
# Filter metadata
# ---------------------------------------------------------------------------


def test_filter_name():
    f = _make_filter(current_atr=1.0)
    assert f.name == "volatility"


def test_filter_stores_provider():
    provider = lambda: 2.5  # noqa: E731
    f = VolatilityFilter(current_atr_provider=provider)
    assert f._current_atr_provider is provider


# ---------------------------------------------------------------------------
# Pass — current ATR < 90th-percentile
# ---------------------------------------------------------------------------


def test_pass_when_atr_below_percentile():
    """ATR = 3.0 < 90th-percentile 5.0 → pass."""
    f = _make_filter(current_atr=3.0)
    result = f.check(_make_signal(), _make_snapshot(atr_90th=_PERCENTILE_90))
    assert result.passed is True
    assert result.skip_reason is None
    assert result.filter_name == "volatility"


def test_pass_when_atr_is_zero():
    """ATR = 0.0 → trivially below threshold → pass."""
    f = _make_filter(current_atr=0.0)
    result = f.check(_make_signal(), _make_snapshot(atr_90th=_PERCENTILE_90))
    assert result.passed is True


def test_pass_when_atr_much_below_percentile():
    """ATR = 1.0 vs percentile 100.0 → pass."""
    f = _make_filter(current_atr=1.0)
    result = f.check(_make_signal(), _make_snapshot(atr_90th=100.0))
    assert result.passed is True


# ---------------------------------------------------------------------------
# Boundary — current ATR == 90th-percentile (strict > comparison → passes)
# ---------------------------------------------------------------------------


def test_pass_when_atr_exactly_equals_percentile():
    """ATR == 90th-percentile: strict '>' so equality does NOT reject → pass."""
    f = _make_filter(current_atr=_PERCENTILE_90)
    result = f.check(_make_signal(), _make_snapshot(atr_90th=_PERCENTILE_90))
    assert result.passed is True
    assert result.skip_reason is None


# ---------------------------------------------------------------------------
# Reject — current ATR > 90th-percentile
# ---------------------------------------------------------------------------


def test_reject_when_atr_above_percentile():
    """ATR = 6.0 > 90th-percentile 5.0 → rejected."""
    f = _make_filter(current_atr=6.0)
    result = f.check(_make_signal(), _make_snapshot(atr_90th=_PERCENTILE_90))
    assert result.passed is False
    assert result.skip_reason == "volatility_too_high"
    assert result.filter_name == "volatility"


def test_reject_when_atr_just_above_percentile():
    """ATR = 5.001 → just above 5.0 → rejected."""
    f = _make_filter(current_atr=5.001)
    result = f.check(_make_signal(), _make_snapshot(atr_90th=_PERCENTILE_90))
    assert result.passed is False
    assert result.skip_reason == "volatility_too_high"


def test_reject_when_atr_far_above_percentile():
    """ATR = 50.0, 90th = 5.0 → extreme volatility → rejected."""
    f = _make_filter(current_atr=50.0)
    result = f.check(_make_signal(), _make_snapshot(atr_90th=_PERCENTILE_90))
    assert result.passed is False
    assert result.skip_reason == "volatility_too_high"


# ---------------------------------------------------------------------------
# Provider is called on each check() invocation (not cached at construction)
# ---------------------------------------------------------------------------


def test_provider_called_on_each_check():
    """Verify the provider callable is invoked for every check, not cached."""
    call_count = [0]

    def counting_provider() -> float:
        call_count[0] += 1
        return 3.0  # always below threshold

    f = VolatilityFilter(current_atr_provider=counting_provider)
    snap = _make_snapshot(atr_90th=_PERCENTILE_90)

    f.check(_make_signal(), snap)
    f.check(_make_signal(), snap)
    f.check(_make_signal(), snap)

    assert call_count[0] == 3


def test_provider_returns_different_values_over_time():
    """A stateful provider can change the filter result between calls."""
    atr_values = iter([3.0, 3.0, 7.0])  # first two pass, third rejects

    f = VolatilityFilter(current_atr_provider=lambda: next(atr_values))
    snap = _make_snapshot(atr_90th=_PERCENTILE_90)

    assert f.check(_make_signal(), snap).passed is True
    assert f.check(_make_signal(), snap).passed is True
    assert f.check(_make_signal(), snap).passed is False


# ---------------------------------------------------------------------------
# size_multiplier is always 1.0 (filter does not reduce size, only rejects)
# ---------------------------------------------------------------------------


def test_pass_has_full_size_multiplier():
    f = _make_filter(current_atr=2.0)
    result = f.check(_make_signal(), _make_snapshot())
    assert result.size_multiplier == 1.0


def test_rejected_has_default_size_multiplier():
    f = _make_filter(current_atr=99.0)
    result = f.check(_make_signal(), _make_snapshot())
    assert result.size_multiplier == 1.0
