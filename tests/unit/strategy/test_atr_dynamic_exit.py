"""Tests for ATRDynamicExit strategy."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from shared.strategy.exit.atr_dynamic import ATRDynamicExit, ATRDynamicExitConfig
from shared.models.position import Position, PositionSide, PositionState
from shared.models.signal import ExitReason


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

KST = timezone(timedelta(hours=9))


def _make_position(
    code: str = "005930",
    entry_price: float = 10000.0,
    current_price: float = 10000.0,
    quantity: int = 10,
    side: PositionSide = PositionSide.LONG,
    highest_price: float = 0.0,
    lowest_price: float = float("inf"),
    entry_time: datetime | None = None,
) -> Position:
    if entry_time is None:
        entry_time = datetime(2026, 2, 26, 9, 30, 0, tzinfo=KST)
    pos = Position(
        id="test-pos-1",
        code=code,
        name="Test Stock",
        side=side,
        quantity=quantity,
        entry_price=entry_price,
        entry_time=entry_time,
        current_price=current_price,
    )
    if highest_price:
        pos.highest_price = highest_price
    if lowest_price != float("inf"):
        pos.lowest_price = lowest_price
    return pos


def _make_snapshot(
    close: float = 10000.0,
    atr: float = 200.0,
    volume_velocity: float = 0.0,
) -> dict:
    return {
        "close": close,
        "atr": atr,
        "volume_velocity": volume_velocity,
    }


def _make_exit(config: ATRDynamicExitConfig | None = None) -> ATRDynamicExit:
    if config is None:
        config = ATRDynamicExitConfig()
    return ATRDynamicExit(config)


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


def test_config_defaults():
    config = ATRDynamicExitConfig()
    assert config.atr_period == 14
    assert config.stop_atr_multiplier == 2.5
    assert config.trail_activation_atr == 1.0
    assert config.trail_atr_multiplier == 2.0
    assert config.momentum_decay_exit is False
    assert config.max_hold_days == 0
    assert config.eod_close_enabled is False
    assert config.eod_close_hour == 15
    assert config.eod_close_minute == 15
    assert config.default_exit_confidence == 0.85


def test_config_from_dict():
    config = ATRDynamicExitConfig.from_dict({
        "stop_atr_multiplier": 3.0,
        "trail_activation_atr": 1.5,
        "momentum_decay_exit": True,
        "max_hold_days": 5,
    })
    assert config.stop_atr_multiplier == 3.0
    assert config.trail_activation_atr == 1.5
    assert config.momentum_decay_exit is True
    assert config.max_hold_days == 5


def test_config_from_dict_with_params_key():
    config = ATRDynamicExitConfig.from_dict({
        "params": {"stop_atr_multiplier": 2.0, "max_hold_days": 3}
    })
    assert config.stop_atr_multiplier == 2.0
    assert config.max_hold_days == 3


def test_config_validation_negative_multiplier():
    with pytest.raises(ValueError, match="stop_atr_multiplier must be positive"):
        ATRDynamicExitConfig(stop_atr_multiplier=-1.0).validate()


def test_config_validation_invalid_confidence():
    with pytest.raises(ValueError, match="default_exit_confidence"):
        ATRDynamicExitConfig(default_exit_confidence=0.0).validate()


# ---------------------------------------------------------------------------
# Hard stop tests
# ---------------------------------------------------------------------------


def test_hard_stop_triggers():
    """Loss exceeds ATR × stop_multiplier → STOP_LOSS."""
    config = ATRDynamicExitConfig(stop_atr_multiplier=2.5, max_loss_pct=0)
    exit_strategy = _make_exit(config)

    entry_price = 10000.0
    atr = 200.0
    # stop_pct = -(200 * 2.5) / 10000 = -0.05
    # price drop = -6% → below stop
    current_price = entry_price * 0.94

    pos = _make_position(entry_price=entry_price, current_price=current_price)
    snapshot = _make_snapshot(close=current_price, atr=atr)
    now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=KST)

    signal = exit_strategy._check_position(pos, snapshot, now)

    assert signal is not None
    assert signal.reason == ExitReason.STOP_LOSS
    assert signal.priority == 1
    assert signal.metadata["stop_type"] == "atr_hard_stop"
    assert signal.confidence == config.default_exit_confidence


def test_max_loss_pct_safety_stop():
    """Loss exceeds max_loss_pct → STOP_LOSS with priority 0 (safety net)."""
    config = ATRDynamicExitConfig(max_loss_pct=5.0)
    exit_strategy = _make_exit(config)

    entry_price = 10000.0
    # -6% loss → exceeds 5% max_loss_pct
    current_price = entry_price * 0.94

    pos = _make_position(entry_price=entry_price, current_price=current_price)
    # No ATR data — simulates stale indicator scenario
    snapshot = _make_snapshot(close=current_price, atr=0)
    now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=KST)

    signal = exit_strategy._check_position(pos, snapshot, now)

    assert signal is not None
    assert signal.reason == ExitReason.STOP_LOSS
    assert signal.priority == 0
    assert signal.metadata["stop_type"] == "max_loss_pct_safety"


def test_hard_stop_not_reached():
    """Loss is within ATR stop threshold → no stop signal."""
    config = ATRDynamicExitConfig(stop_atr_multiplier=2.5)
    exit_strategy = _make_exit(config)

    entry_price = 10000.0
    atr = 200.0
    # stop_pct = -5%, price drop = -2% → well within stop
    current_price = entry_price * 0.98

    pos = _make_position(entry_price=entry_price, current_price=current_price)
    snapshot = _make_snapshot(close=current_price, atr=atr)
    now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=KST)

    signal = exit_strategy._check_position(pos, snapshot, now)

    assert signal is None


def test_hard_stop_exact_boundary():
    """Loss exactly at stop threshold → triggers stop."""
    config = ATRDynamicExitConfig(stop_atr_multiplier=2.0)
    exit_strategy = _make_exit(config)

    entry_price = 10000.0
    atr = 200.0
    # stop_pct = -(200 * 2.0) / 10000 = -0.04
    current_price = entry_price * (1 - 0.04)  # exactly at boundary

    pos = _make_position(entry_price=entry_price, current_price=current_price)
    snapshot = _make_snapshot(close=current_price, atr=atr)
    now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=KST)

    signal = exit_strategy._check_position(pos, snapshot, now)

    assert signal is not None
    assert signal.reason == ExitReason.STOP_LOSS


def test_hard_stop_short_position():
    """Short position: price rises > ATR × stop_multiplier → STOP_LOSS."""
    config = ATRDynamicExitConfig(stop_atr_multiplier=2.5)
    exit_strategy = _make_exit(config)

    entry_price = 10000.0
    atr = 200.0
    # For short: profit = (entry - current) / entry
    # stop_pct = -0.05 (loss threshold)
    # price rise = +6% → profit = -6% < -5% → triggers stop
    current_price = entry_price * 1.06

    pos = _make_position(
        entry_price=entry_price,
        current_price=current_price,
        side=PositionSide.SHORT,
        lowest_price=entry_price,
    )
    snapshot = _make_snapshot(close=current_price, atr=atr)
    now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=KST)

    signal = exit_strategy._check_position(pos, snapshot, now)

    assert signal is not None
    assert signal.reason == ExitReason.STOP_LOSS


# ---------------------------------------------------------------------------
# Trailing stop tests
# ---------------------------------------------------------------------------


def test_trailing_stop_activates_and_trails():
    """Profit exceeds trail_activation_atr → trailing stop triggers when price retraces."""
    config = ATRDynamicExitConfig(
        stop_atr_multiplier=2.5,
        trail_activation_atr=1.0,
        trail_atr_multiplier=2.0,
    )
    exit_strategy = _make_exit(config)

    entry_price = 10000.0
    atr = 200.0
    # trail_activation_pct = (200 * 1.0) / 10000 = 0.02
    # Peak was 10400 → trail_stop = 10400 - (200 * 2.0) = 10000
    # Current = 9999 → below trail_stop → triggers
    peak_price = 10400.0
    current_price = 9999.0

    pos = _make_position(
        entry_price=entry_price,
        current_price=current_price,
        highest_price=peak_price,
    )
    snapshot = _make_snapshot(close=current_price, atr=atr)
    now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=KST)

    signal = exit_strategy._check_position(pos, snapshot, now)

    assert signal is not None
    assert signal.reason == ExitReason.TRAILING_STOP
    assert signal.priority == 2
    assert "trail_stop_price" in signal.metadata
    assert signal.metadata["trail_stop_price"] == pytest.approx(peak_price - atr * 2.0)


def test_trailing_stop_not_yet_activated():
    """Profit below trail_activation → no trailing stop."""
    config = ATRDynamicExitConfig(
        stop_atr_multiplier=2.5,
        trail_activation_atr=1.0,
        trail_atr_multiplier=2.0,
    )
    exit_strategy = _make_exit(config)

    entry_price = 10000.0
    atr = 200.0
    # trail_activation_pct = 0.02 but profit is only 0.5%
    current_price = 10050.0

    pos = _make_position(
        entry_price=entry_price,
        current_price=current_price,
        highest_price=current_price,
    )
    snapshot = _make_snapshot(close=current_price, atr=atr)
    now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=KST)

    signal = exit_strategy._check_position(pos, snapshot, now)

    assert signal is None


def test_trailing_stop_activated_but_price_above_trail():
    """Profit exceeds activation but price still above trail stop → no exit."""
    config = ATRDynamicExitConfig(
        stop_atr_multiplier=2.5,
        trail_activation_atr=1.0,
        trail_atr_multiplier=2.0,
    )
    exit_strategy = _make_exit(config)

    entry_price = 10000.0
    atr = 200.0
    # peak = 10400, trail_stop = 10000, current = 10300 (above trail stop)
    peak_price = 10400.0
    current_price = 10300.0

    pos = _make_position(
        entry_price=entry_price,
        current_price=current_price,
        highest_price=peak_price,
    )
    snapshot = _make_snapshot(close=current_price, atr=atr)
    now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=KST)

    signal = exit_strategy._check_position(pos, snapshot, now)

    assert signal is None


def test_trailing_stop_short_position():
    """Short: price rises above low + trail_distance → TRAILING_STOP."""
    config = ATRDynamicExitConfig(
        stop_atr_multiplier=2.5,
        trail_activation_atr=1.0,
        trail_atr_multiplier=2.0,
    )
    exit_strategy = _make_exit(config)

    entry_price = 10000.0
    atr = 200.0
    # Short profit = (entry - current) / entry
    # Low since entry = 9600 (profit = 4% > activation 2%)
    # trail_stop = 9600 + (200 * 2) = 10000
    # current = 10001 → above trail_stop → triggers
    low_since_entry = 9600.0
    current_price = 10001.0

    pos = _make_position(
        entry_price=entry_price,
        current_price=current_price,
        side=PositionSide.SHORT,
        lowest_price=low_since_entry,
    )
    snapshot = _make_snapshot(close=current_price, atr=atr)
    now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=KST)

    signal = exit_strategy._check_position(pos, snapshot, now)

    assert signal is not None
    assert signal.reason == ExitReason.TRAILING_STOP


# ---------------------------------------------------------------------------
# Max hold days tests
# ---------------------------------------------------------------------------


def test_max_hold_days_exceeded():
    """Position held beyond max_hold_days → TIME_CUT."""
    config = ATRDynamicExitConfig(max_hold_days=3)
    exit_strategy = _make_exit(config)

    entry_time = datetime(2026, 2, 20, 9, 30, 0, tzinfo=KST)
    now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=KST)  # 6 days later

    pos = _make_position(entry_price=10000.0, current_price=10050.0, entry_time=entry_time)
    snapshot = _make_snapshot(close=10050.0, atr=200.0)

    signal = exit_strategy._check_position(pos, snapshot, now)

    assert signal is not None
    assert signal.reason == ExitReason.TIME_CUT
    assert signal.metadata["max_hold_days"] == 3


def test_max_hold_days_not_exceeded():
    """Position within max_hold_days → no TIME_CUT."""
    config = ATRDynamicExitConfig(max_hold_days=5)
    exit_strategy = _make_exit(config)

    entry_time = datetime(2026, 2, 25, 9, 30, 0, tzinfo=KST)
    now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=KST)  # ~1 day

    pos = _make_position(entry_price=10000.0, current_price=10050.0, entry_time=entry_time)
    snapshot = _make_snapshot(close=10050.0, atr=200.0)

    signal = exit_strategy._check_position(pos, snapshot, now)

    assert signal is None


def test_max_hold_days_zero_disabled():
    """max_hold_days=0 (default) → no time-based exit even after many days."""
    config = ATRDynamicExitConfig(max_hold_days=0)
    exit_strategy = _make_exit(config)

    entry_time = datetime(2026, 1, 1, 9, 30, 0, tzinfo=KST)
    now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=KST)  # ~56 days

    pos = _make_position(entry_price=10000.0, current_price=10050.0, entry_time=entry_time)
    snapshot = _make_snapshot(close=10050.0, atr=200.0)

    signal = exit_strategy._check_position(pos, snapshot, now)

    assert signal is None


# ---------------------------------------------------------------------------
# Momentum decay tests
# ---------------------------------------------------------------------------


def test_momentum_decay_triggers():
    """Retracement > ATR and volume_velocity < 0 → MOMENTUM_DECAY."""
    config = ATRDynamicExitConfig(momentum_decay_exit=True)
    exit_strategy = _make_exit(config)

    entry_price = 10000.0
    atr = 200.0
    # peak = 10500, current = 10250 → retracement = 250 > atr = 200
    # volume_velocity = -100 (negative)
    peak_price = 10500.0
    current_price = 10250.0

    pos = _make_position(
        entry_price=entry_price,
        current_price=current_price,
        highest_price=peak_price,
    )
    snapshot = _make_snapshot(close=current_price, atr=atr, volume_velocity=-100.0)
    now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=KST)

    signal = exit_strategy._check_position(pos, snapshot, now)

    assert signal is not None
    assert signal.reason == ExitReason.MOMENTUM_DECAY
    assert signal.metadata["volume_velocity"] == -100.0
    assert signal.metadata["retracement"] == pytest.approx(250.0)


def test_momentum_decay_positive_velocity_no_exit():
    """Volume velocity positive → no momentum decay exit."""
    config = ATRDynamicExitConfig(momentum_decay_exit=True)
    exit_strategy = _make_exit(config)

    entry_price = 10000.0
    atr = 200.0
    peak_price = 10500.0
    current_price = 10250.0  # retracement > ATR

    pos = _make_position(
        entry_price=entry_price,
        current_price=current_price,
        highest_price=peak_price,
    )
    snapshot = _make_snapshot(close=current_price, atr=atr, volume_velocity=50.0)
    now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=KST)

    signal = exit_strategy._check_position(pos, snapshot, now)

    assert signal is None


def test_momentum_decay_disabled_by_default():
    """momentum_decay_exit=False by default → retracement + negative velocity → no exit."""
    config = ATRDynamicExitConfig(momentum_decay_exit=False)
    exit_strategy = _make_exit(config)

    entry_price = 10000.0
    atr = 200.0
    peak_price = 10500.0
    current_price = 10250.0

    pos = _make_position(
        entry_price=entry_price,
        current_price=current_price,
        highest_price=peak_price,
    )
    snapshot = _make_snapshot(close=current_price, atr=atr, volume_velocity=-100.0)
    now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=KST)

    signal = exit_strategy._check_position(pos, snapshot, now)

    assert signal is None


def test_momentum_decay_retracement_below_atr():
    """Retracement < ATR → no momentum decay even if velocity is negative."""
    config = ATRDynamicExitConfig(momentum_decay_exit=True)
    exit_strategy = _make_exit(config)

    entry_price = 10000.0
    atr = 200.0
    peak_price = 10300.0
    current_price = 10200.0  # retracement = 100 < ATR = 200

    pos = _make_position(
        entry_price=entry_price,
        current_price=current_price,
        highest_price=peak_price,
    )
    snapshot = _make_snapshot(close=current_price, atr=atr, volume_velocity=-100.0)
    now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=KST)

    signal = exit_strategy._check_position(pos, snapshot, now)

    assert signal is None


# ---------------------------------------------------------------------------
# No exit / normal conditions
# ---------------------------------------------------------------------------


def test_no_exit_normal_conditions():
    """Profitable position well within all thresholds → no exit."""
    config = ATRDynamicExitConfig(
        stop_atr_multiplier=2.5,
        trail_activation_atr=2.0,
        trail_atr_multiplier=1.5,
        momentum_decay_exit=False,
        max_hold_days=0,
        eod_close_enabled=False,
    )
    exit_strategy = _make_exit(config)

    entry_price = 10000.0
    atr = 100.0
    current_price = 10100.0  # +1%, trail activation needs +2% (200 pts)

    pos = _make_position(
        entry_price=entry_price,
        current_price=current_price,
        highest_price=current_price,
    )
    snapshot = _make_snapshot(close=current_price, atr=atr)
    now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=KST)

    signal = exit_strategy._check_position(pos, snapshot, now)

    assert signal is None


def test_no_exit_when_no_atr_within_safety():
    """Missing ATR but loss within max_loss_pct → no exit."""
    exit_strategy = _make_exit()

    pos = _make_position(entry_price=10000.0, current_price=9600.0)
    snapshot = {"close": 9600.0}  # no ATR key, -4% loss (within 5% safety)
    now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=KST)

    signal = exit_strategy._check_position(pos, snapshot, now)

    # Without ATR, hard stop can't trigger; loss within safety threshold
    assert signal is None


def test_no_atr_safety_stop_triggers():
    """Missing ATR with loss exceeding max_loss_pct → safety stop."""
    exit_strategy = _make_exit()

    pos = _make_position(entry_price=10000.0, current_price=9000.0)
    snapshot = {"close": 9000.0}  # no ATR key, -10% loss
    now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=KST)

    signal = exit_strategy._check_position(pos, snapshot, now)

    # Safety net catches positions when ATR is unavailable
    assert signal is not None
    assert signal.reason == ExitReason.STOP_LOSS
    assert signal.metadata["stop_type"] == "max_loss_pct_safety"


def test_no_exit_missing_price():
    """No price data in snapshot, no current_price on position → returns None."""
    exit_strategy = _make_exit()

    pos = _make_position(entry_price=10000.0, current_price=0.0)
    pos.current_price = 0.0  # explicitly zero
    snapshot = {}
    now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=KST)

    signal = exit_strategy._check_position(pos, snapshot, now)

    assert signal is None


# ---------------------------------------------------------------------------
# scan_positions tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scan_positions_returns_signals():
    """scan_positions returns signals for positions that hit stop."""
    config = ATRDynamicExitConfig(stop_atr_multiplier=2.0)
    exit_strategy = _make_exit(config)

    entry_price = 10000.0
    atr = 200.0
    # stop_pct = -4%; current drop -5% → triggers
    pos1 = _make_position(code="A", entry_price=entry_price, current_price=9500.0)
    pos2 = _make_position(code="B", entry_price=entry_price, current_price=9980.0)

    market_data = {
        "A": {"close": 9500.0, "atr": atr},
        "B": {"close": 9980.0, "atr": atr},
    }

    signals = await exit_strategy.scan_positions([pos1, pos2], market_data)

    assert len(signals) == 1
    assert signals[0].code == "A"
    assert signals[0].reason == ExitReason.STOP_LOSS


@pytest.mark.asyncio
async def test_scan_positions_empty_list():
    """Empty positions list → empty signals."""
    exit_strategy = _make_exit()
    signals = await exit_strategy.scan_positions([], {})
    assert signals == []


# ---------------------------------------------------------------------------
# Priority ordering: hard stop wins over trailing stop
# ---------------------------------------------------------------------------


def test_hard_stop_takes_priority_over_trailing():
    """When both hard stop and trailing stop would trigger, hard stop wins (priority=1)."""
    config = ATRDynamicExitConfig(
        stop_atr_multiplier=2.5,
        trail_activation_atr=1.0,
        trail_atr_multiplier=0.5,  # very tight trail
    )
    exit_strategy = _make_exit(config)

    entry_price = 10000.0
    atr = 200.0
    # Hard stop: -5% → current = 9400 is below stop
    # But we check hard stop first, so it should return STOP_LOSS
    current_price = 9400.0
    peak_price = 10300.0

    pos = _make_position(
        entry_price=entry_price,
        current_price=current_price,
        highest_price=peak_price,
    )
    snapshot = _make_snapshot(close=current_price, atr=atr)
    now = datetime(2026, 2, 26, 10, 0, 0, tzinfo=KST)

    signal = exit_strategy._check_position(pos, snapshot, now)

    assert signal is not None
    assert signal.reason == ExitReason.STOP_LOSS


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------


def test_registry_integration():
    """ATRDynamicExit can be created via ExitRegistry after register_builtin_components()."""
    from shared.strategy.registry import ExitRegistry, register_builtin_components

    register_builtin_components()

    assert ExitRegistry.is_registered("atr_dynamic")

    exit_inst = ExitRegistry.create("atr_dynamic", {"stop_atr_multiplier": 3.0})
    assert exit_inst.name == "atr_dynamic"
    assert exit_inst.config.stop_atr_multiplier == 3.0


def test_name_property():
    exit_strategy = _make_exit()
    assert exit_strategy.name == "atr_dynamic"
