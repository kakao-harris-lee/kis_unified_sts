# tests/unit/risk/test_filter_base.py
"""TDD tests for RiskFilter ABC and FilterResult dataclass."""

from __future__ import annotations

import pytest

from shared.decision.signal import Signal
from shared.risk.filters.base import FilterResult, RiskFilter
from shared.risk.state import RiskStateSnapshot

# ---------------------------------------------------------------------------
# FilterResult tests
# ---------------------------------------------------------------------------


def test_filter_result_pass():
    r = FilterResult(passed=True, filter_name="t", skip_reason=None)
    assert r.passed
    assert r.skip_reason is None


def test_filter_result_reject():
    r = FilterResult(passed=False, filter_name="t", skip_reason="reason_tag")
    assert not r.passed
    assert r.skip_reason == "reason_tag"


def test_filter_result_default_size_multiplier():
    """size_multiplier defaults to 1.0 when not provided."""
    r = FilterResult(passed=True, filter_name="t")
    assert r.size_multiplier == 1.0


def test_filter_result_custom_size_multiplier():
    """size_multiplier can be set to a reduced value (e.g. 0.5)."""
    r = FilterResult(passed=True, filter_name="half", size_multiplier=0.5)
    assert r.size_multiplier == 0.5


def test_filter_result_size_multiplier_zero_allowed():
    r = FilterResult(passed=False, filter_name="f", size_multiplier=0.0)
    assert r.size_multiplier == 0.0


def test_filter_result_size_multiplier_one_allowed():
    r = FilterResult(passed=True, filter_name="f", size_multiplier=1.0)
    assert r.size_multiplier == 1.0


def test_filter_result_size_multiplier_above_one_raises():
    """size_multiplier > 1.0 is invalid — filters may only reduce size."""
    with pytest.raises(ValueError, match="size_multiplier"):
        FilterResult(passed=True, filter_name="f", size_multiplier=1.01)


def test_filter_result_size_multiplier_negative_raises():
    """Negative size_multiplier is invalid."""
    with pytest.raises(ValueError, match="size_multiplier"):
        FilterResult(passed=True, filter_name="f", size_multiplier=-0.1)


def test_filter_result_is_frozen():
    """FilterResult is a frozen dataclass — mutation must raise."""
    r = FilterResult(passed=True, filter_name="t")
    with pytest.raises((AttributeError, TypeError)):
        r.passed = False  # type: ignore[misc]


def test_filter_result_equality():
    a = FilterResult(
        passed=True, filter_name="x", skip_reason=None, size_multiplier=0.5
    )
    b = FilterResult(
        passed=True, filter_name="x", skip_reason=None, size_multiplier=0.5
    )
    assert a == b


# ---------------------------------------------------------------------------
# RiskFilter ABC tests
# ---------------------------------------------------------------------------


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


class AlwaysPassFilter(RiskFilter):
    name = "always_pass"

    def check(self, signal: Signal, state_snapshot: RiskStateSnapshot) -> FilterResult:
        _ = signal, state_snapshot
        return FilterResult(passed=True, filter_name=self.name)


class AlwaysRejectFilter(RiskFilter):
    name = "always_reject"

    def check(self, signal: Signal, state_snapshot: RiskStateSnapshot) -> FilterResult:
        _ = signal, state_snapshot
        return FilterResult(
            passed=False,
            filter_name=self.name,
            skip_reason="test_rejection",
        )


class ReduceSizeFilter(RiskFilter):
    name = "reduce_size"

    def check(self, signal: Signal, state_snapshot: RiskStateSnapshot) -> FilterResult:
        _ = signal, state_snapshot
        return FilterResult(
            passed=True,
            filter_name=self.name,
            size_multiplier=0.5,
        )


def test_risk_filter_subclass_can_be_instantiated():
    f = AlwaysPassFilter()
    assert f.name == "always_pass"


def test_risk_filter_check_returns_passed_result():
    f = AlwaysPassFilter()
    signal = _make_signal()
    snap = RiskStateSnapshot()
    result = f.check(signal, snap)
    assert result.passed is True
    assert result.filter_name == "always_pass"


def test_risk_filter_check_returns_rejected_result():
    f = AlwaysRejectFilter()
    signal = _make_signal()
    snap = RiskStateSnapshot()
    result = f.check(signal, snap)
    assert result.passed is False
    assert result.skip_reason == "test_rejection"
    assert result.filter_name == "always_reject"


def test_risk_filter_can_signal_size_reduction_without_reject():
    """A filter can pass but reduce size_multiplier (e.g. ConsecutiveLossFilter)."""
    f = ReduceSizeFilter()
    signal = _make_signal()
    snap = RiskStateSnapshot()
    result = f.check(signal, snap)
    assert result.passed is True
    assert result.size_multiplier == 0.5


def test_risk_filter_is_abstract():
    """RiskFilter cannot be instantiated without implementing check()."""
    with pytest.raises(TypeError):
        RiskFilter()  # type: ignore[abstract]


def test_risk_filter_name_is_class_attribute():
    """name must be defined on the subclass (RiskFilter.name is abstract sentinel)."""
    assert AlwaysPassFilter.name == "always_pass"
    assert AlwaysRejectFilter.name == "always_reject"
