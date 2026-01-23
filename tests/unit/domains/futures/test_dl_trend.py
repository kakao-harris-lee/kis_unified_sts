"""Tests for DL Trend Entry Strategy - Triple Barrier Probability Handling"""

import pytest

from domains.futures.strategies.dl_trend import (
    EnsembleFilter,
    FilterResult,
    TechnicalData,
)


@pytest.fixture
def ensemble_filter():
    """Basic ensemble filter with default settings"""
    return EnsembleFilter(
        dl_threshold=0.55,
        max_atr_threshold=1.5,
        zscore_trigger_threshold=1.0,
        zscore_long_confirm_threshold=0.5,
        zscore_short_confirm_threshold=0.0,
    )


@pytest.fixture
def bullish_tech():
    """Bullish technical conditions"""
    return TechnicalData(
        ma_fast=100.0,
        ma_slow=95.0,
        ichimoku_span_a=90.0,
        ichimoku_span_b=88.0,
        atr=1.0,
        is_ready=True,
        current_price=105.0,
    )


@pytest.fixture
def bearish_tech():
    """Bearish technical conditions"""
    return TechnicalData(
        ma_fast=90.0,
        ma_slow=95.0,
        ichimoku_span_a=98.0,
        ichimoku_span_b=100.0,
        atr=1.0,
        is_ready=True,
        current_price=85.0,
    )


@pytest.fixture
def neutral_tech():
    """Neutral technical conditions"""
    return TechnicalData(
        ma_fast=95.0,
        ma_slow=95.0,
        ichimoku_span_a=92.0,
        ichimoku_span_b=98.0,
        atr=1.0,
        is_ready=True,
        current_price=95.0,
    )


# =============================================================================
# Binary Probability Tests (Backward Compatibility)
# =============================================================================


def test_binary_probability_long_signal(ensemble_filter, bullish_tech):
    """Binary mode: up_prob=0.7 should work as before"""
    result = ensemble_filter.check_entry(up_prob=0.7, tech=bullish_tech)

    assert result.can_enter is True
    assert result.direction == "LONG"
    assert result.dl_passed is True
    assert result.ma_passed is True
    assert result.ichimoku_passed is True


def test_binary_probability_short_signal(ensemble_filter, bearish_tech):
    """Binary mode: down_prob calculated as 1-up_prob"""
    result = ensemble_filter.check_entry(up_prob=0.3, tech=bearish_tech)

    assert result.can_enter is True
    assert result.direction == "SHORT"


def test_binary_probability_no_signal(ensemble_filter, neutral_tech):
    """Binary mode: low probability rejects"""
    result = ensemble_filter.check_entry(up_prob=0.5, tech=neutral_tech)

    assert result.can_enter is False
    assert result.direction is None


# =============================================================================
# Triple Barrier Tests (New Behavior)
# =============================================================================


def test_triple_barrier_explicit_probabilities(ensemble_filter, bullish_tech):
    """Triple barrier: explicit up/down/hold probabilities"""
    result = ensemble_filter.check_entry(
        up_prob=0.6,
        tech=bullish_tech,
        down_prob=0.25,
        hold_prob=0.15,
    )

    assert result.can_enter is True
    assert result.direction == "LONG"


def test_triple_barrier_hold_dominant_rejects(ensemble_filter, bullish_tech):
    """Hold probability dominant → reject entry"""
    result = ensemble_filter.check_entry(
        up_prob=0.35,
        tech=bullish_tech,
        down_prob=0.25,
        hold_prob=0.4,  # Hold is dominant
    )

    assert result.can_enter is False
    assert result.direction is None
    rejection = result.rejection_reason.lower()
    assert "weak" in rejection or "hold" in rejection


def test_triple_barrier_down_prob_without_hold(ensemble_filter, bearish_tech):
    """down_prob explicit, hold calculated automatically"""
    result = ensemble_filter.check_entry(
        up_prob=0.2,
        tech=bearish_tech,
        down_prob=0.7,
        # hold_prob should be calculated as 1 - 0.2 - 0.7 = 0.1
    )

    assert result.can_enter is True
    assert result.direction == "SHORT"


def test_triple_barrier_close_probabilities_reject(ensemble_filter, neutral_tech):
    """Up and down too close → weak prediction"""
    result = ensemble_filter.check_entry(
        up_prob=0.45,
        tech=neutral_tech,
        down_prob=0.45,
        hold_prob=0.1,
    )

    # Neither direction has strong conviction
    assert result.can_enter is False


def test_triple_barrier_invalid_probabilities_normalized(ensemble_filter, bullish_tech):
    """Probabilities not summing to 1.0 should be handled"""
    result = ensemble_filter.check_entry(
        up_prob=0.5,
        tech=bullish_tech,
        down_prob=0.3,
        hold_prob=0.1,  # Sum = 0.9, should handle gracefully
    )

    # Should work (normalized internally or clamped)
    assert isinstance(result, FilterResult)


def test_triple_barrier_short_signal(ensemble_filter, bearish_tech):
    """Triple barrier SHORT signal"""
    result = ensemble_filter.check_entry(
        up_prob=0.2,
        tech=bearish_tech,
        down_prob=0.65,
        hold_prob=0.15,
    )

    assert result.can_enter is True
    assert result.direction == "SHORT"


def test_triple_barrier_edge_case_zero_hold(ensemble_filter, bullish_tech):
    """Edge case: hold_prob=0 (no neutral prediction)"""
    result = ensemble_filter.check_entry(
        up_prob=0.7,
        tech=bullish_tech,
        down_prob=0.3,
        hold_prob=0.0,
    )

    assert result.can_enter is True
    assert result.direction == "LONG"


def test_triple_barrier_equal_up_down(ensemble_filter, neutral_tech):
    """Edge case: up and down equal with small hold"""
    result = ensemble_filter.check_entry(
        up_prob=0.45,
        tech=neutral_tech,
        down_prob=0.45,
        hold_prob=0.1,
    )

    # Ambiguous prediction should reject
    assert result.can_enter is False


# =============================================================================
# Technical Filter Tests
# =============================================================================


def test_technical_not_ready(ensemble_filter):
    """Technical indicators not ready"""
    tech = TechnicalData(
        ma_fast=0,
        ma_slow=0,
        ichimoku_span_a=0,
        ichimoku_span_b=0,
        atr=0,
        is_ready=False,
        current_price=100.0,
    )

    result = ensemble_filter.check_entry(up_prob=0.8, tech=tech)

    assert result.can_enter is False
    assert "warming up" in result.rejection_reason.lower()


def test_ma_filter_rejects_long(ensemble_filter):
    """MA bearish should reject LONG"""
    tech = TechnicalData(
        ma_fast=90.0,  # Below slow
        ma_slow=100.0,
        ichimoku_span_a=85.0,
        ichimoku_span_b=83.0,
        atr=1.0,
        is_ready=True,
        current_price=110.0,  # Above cloud but MA bearish
    )

    result = ensemble_filter.check_entry(up_prob=0.8, tech=tech)

    assert result.can_enter is False
    assert result.ma_passed is False


def test_ichimoku_filter_rejects_long(ensemble_filter):
    """Price below cloud should reject LONG"""
    tech = TechnicalData(
        ma_fast=100.0,
        ma_slow=90.0,  # MA bullish
        ichimoku_span_a=110.0,
        ichimoku_span_b=112.0,
        atr=1.0,
        is_ready=True,
        current_price=105.0,  # Below cloud
    )

    result = ensemble_filter.check_entry(up_prob=0.8, tech=tech)

    assert result.can_enter is False
    assert result.ichimoku_passed is False


# =============================================================================
# Statistics Tests
# =============================================================================


def test_statistics_tracking(ensemble_filter, bullish_tech):
    """Stats should track rejections"""
    ensemble_filter.check_entry(up_prob=0.8, tech=bullish_tech)
    ensemble_filter.check_entry(up_prob=0.4, tech=bullish_tech)

    stats = ensemble_filter.get_stats()
    assert stats["total_checks"] == 2
    assert stats["long_signals"] >= 1
    assert stats["rejected_dl"] >= 1


def test_reset_stats(ensemble_filter):
    """Reset should clear stats"""
    ensemble_filter._stats["total_checks"] = 100
    ensemble_filter.reset_stats()

    stats = ensemble_filter.get_stats()
    assert stats["total_checks"] == 0
