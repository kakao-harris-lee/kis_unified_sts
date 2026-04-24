# tests/unit/risk/test_filter_consecutive_loss.py
"""TDD tests for ConsecutiveLossFilter.

Written BEFORE / alongside implementation (TDD red-green cycle).

Thresholds used throughout: soft=4, hard=6.
"""

from __future__ import annotations

import pytest

from shared.decision.signal import Signal
from shared.risk.filters.consecutive_loss import ConsecutiveLossFilter
from shared.risk.state import RiskStateSnapshot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SOFT = 4
_HARD = 6


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


def _make_snapshot(consecutive_losses: int = 0) -> RiskStateSnapshot:
    return RiskStateSnapshot(consecutive_losses=consecutive_losses)


def _make_filter(
    soft: int = _SOFT, hard: int = _HARD
) -> ConsecutiveLossFilter:
    return ConsecutiveLossFilter(soft_threshold=soft, hard_threshold=hard)


# ---------------------------------------------------------------------------
# Filter metadata
# ---------------------------------------------------------------------------


def test_filter_name():
    f = _make_filter()
    assert f.name == "consecutive_loss"


def test_filter_stores_thresholds():
    f = _make_filter(soft=3, hard=7)
    assert f.soft_threshold == 3
    assert f.hard_threshold == 7


# ---------------------------------------------------------------------------
# Construction guard-rails
# ---------------------------------------------------------------------------


def test_raises_if_soft_threshold_zero():
    with pytest.raises(ValueError, match="soft_threshold"):
        ConsecutiveLossFilter(soft_threshold=0, hard_threshold=4)


def test_raises_if_hard_not_greater_than_soft():
    with pytest.raises(ValueError, match="hard_threshold"):
        ConsecutiveLossFilter(soft_threshold=4, hard_threshold=4)


def test_raises_if_hard_less_than_soft():
    with pytest.raises(ValueError, match="hard_threshold"):
        ConsecutiveLossFilter(soft_threshold=5, hard_threshold=3)


# ---------------------------------------------------------------------------
# Pass — losses < soft_threshold (full size)
# ---------------------------------------------------------------------------


def test_pass_zero_losses():
    """No losses at all → pass with size_multiplier=1.0."""
    f = _make_filter()
    result = f.check(_make_signal(), _make_snapshot(0))
    assert result.passed is True
    assert result.size_multiplier == 1.0
    assert result.skip_reason is None
    assert result.filter_name == "consecutive_loss"


def test_pass_one_loss():
    """Single loss (< soft=4) → pass full size."""
    f = _make_filter()
    result = f.check(_make_signal(), _make_snapshot(1))
    assert result.passed is True
    assert result.size_multiplier == 1.0


def test_pass_soft_minus_one():
    """losses = soft - 1 (= 3) → still full size."""
    f = _make_filter()
    result = f.check(_make_signal(), _make_snapshot(_SOFT - 1))
    assert result.passed is True
    assert result.size_multiplier == 1.0


# ---------------------------------------------------------------------------
# Soft zone — losses in [soft, hard) → pass with size_multiplier=0.5
# ---------------------------------------------------------------------------


def test_soft_zone_exactly_at_soft_threshold():
    """losses == soft → pass with size_multiplier=0.5."""
    f = _make_filter()
    result = f.check(_make_signal(), _make_snapshot(_SOFT))
    assert result.passed is True
    assert result.size_multiplier == 0.5
    assert result.skip_reason is None
    assert result.filter_name == "consecutive_loss"


def test_soft_zone_between_soft_and_hard():
    """losses = soft + 1 (= 5) → still pass with 0.5 (below hard=6)."""
    f = _make_filter()
    result = f.check(_make_signal(), _make_snapshot(_SOFT + 1))
    assert result.passed is True
    assert result.size_multiplier == 0.5


def test_soft_zone_hard_minus_one():
    """losses = hard - 1 (= 5) → pass with 0.5, NOT rejected."""
    f = _make_filter()
    result = f.check(_make_signal(), _make_snapshot(_HARD - 1))
    assert result.passed is True
    assert result.size_multiplier == 0.5


# ---------------------------------------------------------------------------
# Hard zone — losses >= hard_threshold → reject
# ---------------------------------------------------------------------------


def test_reject_exactly_at_hard_threshold():
    """losses == hard → rejected."""
    f = _make_filter()
    result = f.check(_make_signal(), _make_snapshot(_HARD))
    assert result.passed is False
    assert result.skip_reason == "consecutive_losses_cooldown"
    assert result.filter_name == "consecutive_loss"


def test_reject_above_hard_threshold():
    """losses > hard → rejected."""
    f = _make_filter()
    result = f.check(_make_signal(), _make_snapshot(_HARD + 3))
    assert result.passed is False
    assert result.skip_reason == "consecutive_losses_cooldown"


def test_reject_much_above_hard_threshold():
    """Very high loss count (pathological) → still rejected."""
    f = _make_filter()
    result = f.check(_make_signal(), _make_snapshot(100))
    assert result.passed is False
    assert result.skip_reason == "consecutive_losses_cooldown"


# ---------------------------------------------------------------------------
# size_multiplier is not set on rejected results
# (FilterResult defaults to 1.0 but rejection is the primary indicator)
# ---------------------------------------------------------------------------


def test_rejected_result_has_default_size_multiplier():
    """Rejected FilterResult has size_multiplier=1.0 (default)."""
    f = _make_filter()
    result = f.check(_make_signal(), _make_snapshot(_HARD))
    # passed=False is the definitive signal; size_multiplier still defaults
    assert result.size_multiplier == 1.0
