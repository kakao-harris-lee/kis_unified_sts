"""Test ATRDynamicExit position.metadata overrides for trend mode."""

import pytest
from datetime import datetime, timedelta, timezone
from shared.models.position import Position, PositionSide, PositionState
from shared.strategy.exit.atr_dynamic import ATRDynamicExit, ATRDynamicExitConfig

KST = timezone(timedelta(hours=9))


def _make_position(
    entry_price=50000.0,
    current_price=50000.0,
    highest_price=50000.0,
    metadata=None,
    entry_minutes_ago=60,
) -> Position:
    now = datetime(2026, 3, 2, 11, 0, tzinfo=KST)
    return Position(
        id="test-pos-1",
        code="005930",
        name="삼성전자",
        side=PositionSide.LONG,
        quantity=10,
        entry_price=entry_price,
        entry_time=now - timedelta(minutes=entry_minutes_ago),
        current_price=current_price,
        highest_price=highest_price,
        lowest_price=entry_price * 0.98,
        stop_price=entry_price * 0.95,
        state=PositionState.SURVIVAL,
        metadata=metadata or {},
    )


def test_exit_uses_metadata_stop_override():
    """ATRDynamicExit uses exit_stop_atr_multiplier from position.metadata."""
    config = ATRDynamicExitConfig(stop_atr_multiplier=2.0)
    exit_strategy = ATRDynamicExit(config)

    pos = _make_position(
        entry_price=50000.0,
        current_price=49000.0,  # -2% loss
        metadata={"exit_stop_atr_multiplier": 3.0},
    )
    snapshot = {"close": 49000.0, "atr": 500.0}
    now = datetime(2026, 3, 2, 11, 0, tzinfo=KST)

    # Config stop (2.0): stop_distance = 500*2.0 = 1000, stop_pct = -2% → triggers
    # Metadata override (3.0): stop_distance = 500*3.0 = 1500, stop_pct = -3% → does NOT trigger
    signal = exit_strategy._check_position(pos, snapshot, now)
    assert signal is None  # wider stop from metadata prevents exit


def test_exit_uses_metadata_trail_override():
    """ATRDynamicExit uses exit_trail_atr_multiplier from position.metadata."""
    config = ATRDynamicExitConfig(
        trail_activation_atr=1.0,
        trail_atr_multiplier=1.5,
        stop_atr_multiplier=5.0,
    )
    exit_strategy = ATRDynamicExit(config)

    pos = _make_position(
        entry_price=50000.0,
        current_price=50200.0,
        highest_price=51000.0,
        metadata={"exit_trail_atr_multiplier": 3.0},
    )
    snapshot = {"close": 50200.0, "atr": 500.0}
    now = datetime(2026, 3, 2, 11, 0, tzinfo=KST)

    # Trail activated: peak (51000) >= entry (50000) + 500*1.0 = 50500 ✓
    # Config trail stop: 51000 - 500*1.5 = 50250 → current 50200 < 50250 → TRIGGERS
    # Metadata trail stop: 51000 - 500*3.0 = 49500 → current 50200 > 49500 → NO TRIGGER
    signal = exit_strategy._check_position(pos, snapshot, now)
    assert signal is None  # wider trail from metadata prevents exit


def test_exit_uses_metadata_max_hold_override():
    """ATRDynamicExit uses exit_max_hold_days from position.metadata."""
    config = ATRDynamicExitConfig(
        max_hold_days=8,
        stop_atr_multiplier=5.0,
    )
    exit_strategy = ATRDynamicExit(config)

    pos = _make_position(
        entry_price=50000.0,
        current_price=50500.0,
        highest_price=50500.0,
        entry_minutes_ago=10 * 24 * 60,  # 10 days
        metadata={"exit_max_hold_days": 15},
    )
    snapshot = {"close": 50500.0, "atr": 500.0}
    now = datetime(2026, 3, 2, 11, 0, tzinfo=KST)

    # Config max_hold=8 → 10 days > 8 → TRIGGERS
    # Metadata max_hold=15 → 10 days < 15 → NO TRIGGER
    signal = exit_strategy._check_position(pos, snapshot, now)
    assert signal is None  # extended hold from metadata


def test_exit_falls_back_to_config_without_metadata():
    """Without metadata overrides, ATRDynamicExit uses config values."""
    config = ATRDynamicExitConfig(stop_atr_multiplier=2.0)
    exit_strategy = ATRDynamicExit(config)

    pos = _make_position(
        entry_price=50000.0,
        current_price=49000.0,  # -2% loss
        metadata={},
    )
    snapshot = {"close": 49000.0, "atr": 500.0}
    now = datetime(2026, 3, 2, 11, 0, tzinfo=KST)

    # stop_distance = 500*2.0 = 1000, stop_pct = -2%
    # loss = -2% at stop → triggers
    signal = exit_strategy._check_position(pos, snapshot, now)
    assert signal is not None
    assert signal.reason.value == "stop_loss"
