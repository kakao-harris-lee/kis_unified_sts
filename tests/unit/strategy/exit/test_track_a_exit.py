"""Unit tests for TrackAExit pure math helpers."""
from __future__ import annotations
import pytest
from shared.models.position import PositionSide
from shared.strategy.exit.track_a_exit import (
    catastrophic_stop_hit, crash_triggered, trail_activated, trail_stop_price,
)

def test_trail_stop_long():
    assert trail_stop_price(PositionSide.LONG, favorable_extreme=105.0, atr=2.0, trail_atr_mult=3.0) == pytest.approx(99.0)
def test_trail_stop_short():
    assert trail_stop_price(PositionSide.SHORT, favorable_extreme=95.0, atr=2.0, trail_atr_mult=3.0) == pytest.approx(101.0)
def test_trail_not_activated_at_entry_long():
    assert trail_activated(PositionSide.LONG, entry_price=100.0, favorable_extreme=100.0, atr=2.0, trail_activate_atr_mult=1.0) is False
def test_trail_activated_long():
    assert trail_activated(PositionSide.LONG, entry_price=100.0, favorable_extreme=102.5, atr=2.0, trail_activate_atr_mult=1.0) is True
def test_trail_not_activated_long_below_threshold():
    assert trail_activated(PositionSide.LONG, entry_price=100.0, favorable_extreme=101.5, atr=2.0, trail_activate_atr_mult=1.0) is False
def test_trail_activated_short():
    assert trail_activated(PositionSide.SHORT, entry_price=100.0, favorable_extreme=97.5, atr=2.0, trail_activate_atr_mult=1.0) is True
def test_trail_not_activated_short_adverse():
    assert trail_activated(PositionSide.SHORT, entry_price=100.0, favorable_extreme=102.0, atr=2.0, trail_activate_atr_mult=1.0) is False
def test_crash_triggered_long():
    assert crash_triggered(PositionSide.LONG, current_price=93.0, prev_price=100.0, atr=2.0, crash_atr_mult=3.5) is True
def test_crash_not_triggered_long_small_move():
    assert crash_triggered(PositionSide.LONG, current_price=97.0, prev_price=100.0, atr=2.0, crash_atr_mult=3.5) is False
def test_crash_triggered_short():
    assert crash_triggered(PositionSide.SHORT, current_price=107.0, prev_price=100.0, atr=2.0, crash_atr_mult=3.5) is True
def test_crash_not_triggered_on_favorable_spike_long():
    assert crash_triggered(PositionSide.LONG, current_price=103.0, prev_price=100.0, atr=2.0, crash_atr_mult=3.5) is False
def test_catastrophic_long():
    assert catastrophic_stop_hit(PositionSide.LONG, entry_price=100.0, current_price=88.0, atr=2.0, catastrophic_atr_mult=6.0) is True
def test_catastrophic_short():
    assert catastrophic_stop_hit(PositionSide.SHORT, entry_price=100.0, current_price=112.0, atr=2.0, catastrophic_atr_mult=6.0) is True
def test_catastrophic_not_triggered_within_threshold():
    assert catastrophic_stop_hit(PositionSide.LONG, entry_price=100.0, current_price=90.0, atr=2.0, catastrophic_atr_mult=6.0) is False
