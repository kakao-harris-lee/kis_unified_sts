# tests/unit/risk/test_risk_filter_layer.py
"""TDD tests for RiskFilterLayer — Task 13 of Phase 3."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from shared.risk.filters.base import FilterResult, RiskFilter
from shared.risk.layer import LayerResult, RiskFilterLayer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_filter(
    *,
    name: str,
    passed: bool,
    skip_reason: str | None = None,
    size_multiplier: float = 1.0,
) -> RiskFilter:
    """Build a MagicMock RiskFilter with a canned FilterResult."""
    mock = MagicMock(spec=RiskFilter)
    mock.name = name
    mock.check.return_value = FilterResult(
        passed=passed,
        filter_name=name,
        skip_reason=skip_reason,
        size_multiplier=size_multiplier,
    )
    return mock


def _signal():
    """Minimal signal stand-in (content irrelevant to RiskFilterLayer)."""
    return MagicMock()


def _snapshot():
    """Minimal state_snapshot stand-in."""
    return MagicMock()


# ---------------------------------------------------------------------------
# (a) All 8 filters pass — LayerResult.passed=True, size_multiplier=1.0
# ---------------------------------------------------------------------------


def test_all_filters_pass_returns_passed_layer_result():
    filter_names = [
        "trading_hours",
        "daily_mdd",
        "weekly_mdd",
        "consecutive_loss",
        "daily_trade_count",
        "volatility",
        "spread",
        "open_position",
    ]
    filters = [_make_filter(name=n, passed=True) for n in filter_names]
    layer = RiskFilterLayer(filters=filters)

    result = layer.evaluate(_signal(), _snapshot())

    assert isinstance(result, LayerResult)
    assert result.passed is True
    assert result.skip_reason is None
    assert result.size_multiplier == pytest.approx(1.0)
    assert len(result.filter_outcomes) == 8
    for outcome in result.filter_outcomes:
        assert outcome.passed is True


# ---------------------------------------------------------------------------
# (b) First filter rejects — short-circuit, outcomes has exactly 1 entry
# ---------------------------------------------------------------------------


def test_first_filter_rejects_short_circuits():
    f_reject = _make_filter(
        name="trading_hours", passed=False, skip_reason="outside_trading_hours"
    )
    f_never = _make_filter(name="daily_mdd", passed=True)

    layer = RiskFilterLayer(filters=[f_reject, f_never])
    result = layer.evaluate(_signal(), _snapshot())

    assert result.passed is False
    assert result.skip_reason == "outside_trading_hours"
    assert result.size_multiplier == pytest.approx(1.0)
    assert len(result.filter_outcomes) == 1
    assert result.filter_outcomes[0].filter_name == "trading_hours"
    # Second filter must never be called
    f_never.check.assert_not_called()


# ---------------------------------------------------------------------------
# (c) Middle filter rejects — outcomes has N entries; later filters NOT called
# ---------------------------------------------------------------------------


def test_middle_filter_rejects_stops_chain():
    f1 = _make_filter(name="trading_hours", passed=True)
    f2 = _make_filter(name="daily_mdd", passed=True)
    f3 = _make_filter(name="weekly_mdd", passed=False, skip_reason="weekly_mdd_breach")
    f4 = _make_filter(name="consecutive_loss", passed=True)
    f5 = _make_filter(name="daily_trade_count", passed=True)

    layer = RiskFilterLayer(filters=[f1, f2, f3, f4, f5])
    result = layer.evaluate(_signal(), _snapshot())

    assert result.passed is False
    assert result.skip_reason == "weekly_mdd_breach"
    assert len(result.filter_outcomes) == 3
    assert result.filter_outcomes[-1].filter_name == "weekly_mdd"
    # Filters after the rejector must not be called
    f4.check.assert_not_called()
    f5.check.assert_not_called()


# ---------------------------------------------------------------------------
# (d) Soft-reduce + strict pass → size_multiplier multiplied (0.5 × 1.0 = 0.5)
# ---------------------------------------------------------------------------


def test_soft_reduce_with_strict_pass_compounds_multiplier():
    f_soft = _make_filter(name="consecutive_loss", passed=True, size_multiplier=0.5)
    f_strict = _make_filter(name="daily_mdd", passed=True, size_multiplier=1.0)
    f_strict2 = _make_filter(name="volatility", passed=True, size_multiplier=1.0)

    layer = RiskFilterLayer(filters=[f_soft, f_strict, f_strict2])
    result = layer.evaluate(_signal(), _snapshot())

    assert result.passed is True
    assert result.size_multiplier == pytest.approx(0.5 * 1.0 * 1.0)
    assert len(result.filter_outcomes) == 3


# ---------------------------------------------------------------------------
# (e) Two soft-reduce filters compound (0.5 × 0.5 = 0.25)
# ---------------------------------------------------------------------------


def test_two_soft_reduce_filters_compound():
    f1 = _make_filter(name="consecutive_loss", passed=True, size_multiplier=0.5)
    f2 = _make_filter(name="volatility", passed=True, size_multiplier=0.5)

    layer = RiskFilterLayer(filters=[f1, f2])
    result = layer.evaluate(_signal(), _snapshot())

    assert result.passed is True
    assert result.size_multiplier == pytest.approx(0.25)
    assert len(result.filter_outcomes) == 2


# ---------------------------------------------------------------------------
# (f) Empty filter list → passed=True, size_multiplier=1.0, outcomes=[]
# ---------------------------------------------------------------------------


def test_empty_filter_list_passes_through():
    layer = RiskFilterLayer(filters=[])
    result = layer.evaluate(_signal(), _snapshot())

    assert result.passed is True
    assert result.skip_reason is None
    assert result.size_multiplier == pytest.approx(1.0)
    assert result.filter_outcomes == []


# ---------------------------------------------------------------------------
# Extra: LayerResult is a frozen dataclass
# ---------------------------------------------------------------------------


def test_layer_result_is_frozen():
    r = LayerResult(
        passed=True, skip_reason=None, size_multiplier=1.0, filter_outcomes=[]
    )
    with pytest.raises((AttributeError, TypeError)):
        r.passed = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Extra: size_multiplier=1.0 on rejection (not accumulated)
# ---------------------------------------------------------------------------


def test_rejected_result_size_multiplier_is_one():
    """Even if earlier filters reduced size, LayerResult for a rejection reports 1.0."""
    f1 = _make_filter(name="consecutive_loss", passed=True, size_multiplier=0.5)
    f2 = _make_filter(name="trading_hours", passed=False, skip_reason="outside_hours")

    layer = RiskFilterLayer(filters=[f1, f2])
    result = layer.evaluate(_signal(), _snapshot())

    assert result.passed is False
    assert result.size_multiplier == pytest.approx(1.0)
    assert len(result.filter_outcomes) == 2
