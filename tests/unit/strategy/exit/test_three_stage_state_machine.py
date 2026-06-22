"""Unit tests for ThreeStageExit state machine (SURVIVAL → BREAKEVEN → MAXIMIZE)."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from shared.models.position import Position, PositionSide, PositionState
from shared.models.signal import ExitReason
from shared.strategy.base import ExitContext, MarketStateAdapter
from shared.strategy.exit.three_stage import ThreeStageExit, ThreeStageExitConfig

_KST = ZoneInfo("Asia/Seoul")


def _minimal_config(**overrides) -> ThreeStageExitConfig:
    defaults = {
        "stop_loss_pct": -0.02,
        "breakeven_threshold_pct": 0.015,
        "maximize_threshold_pct": 0.03,
        "trailing_stop_pct": -0.03,
        "overshoot_threshold_pct": 0.07,
        "overshoot_trailing_pct": -0.015,
        "time_cut_minutes": 20,
        "eod_close_hour": 15,
        "eod_close_minute": 15,
        "fee_rate": 0.003,
        "enable_bear_exit": True,
    }
    defaults.update(overrides)
    return ThreeStageExitConfig(**defaults)


def _position(
    *,
    entry_price: float = 100_000.0,
    state: PositionState = PositionState.SURVIVAL,
    entry_time: datetime | None = None,
    highest_price: float = 0.0,
    stop_price: float = 0.0,
) -> Position:
    # Use a recent morning entry time to avoid TIME_CUT firing.
    pos = Position(
        id="pos_005930",
        code="005930",
        name="Samsung",
        side=PositionSide.LONG,
        quantity=10,
        entry_price=entry_price,
        entry_time=entry_time or datetime(2026, 5, 15, 9, 55, 0, tzinfo=_KST),
        state=state,
        highest_price=highest_price or entry_price,
        stop_price=stop_price,
    )
    return pos


def _context(position: Position, *, close: float, market_state=None) -> ExitContext:
    # Weekday morning KST → EOD branch skipped regardless of calendar state.
    ts = datetime(2026, 5, 15, 10, 0, 0, tzinfo=_KST)
    return ExitContext(
        position=position,
        market_data={position.code: {"close": close}},
        indicators={},
        timestamp=ts,
        market_state=market_state,
    )


# -----------------------------------------------------------------------------
# State transitions via update_position_state
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_survival_to_breakeven_transition_sets_breakeven_stop():
    """profit >= breakeven_threshold_pct → state=BREAKEVEN, stop=entry*(1+fee)."""
    cfg = _minimal_config()
    strategy = ThreeStageExit(cfg)
    position = _position(state=PositionState.SURVIVAL)

    target_price = position.entry_price * (1.0 + cfg.breakeven_threshold_pct + 0.0001)
    new_state = await strategy.update_position_state(position, target_price)

    assert new_state == PositionState.BREAKEVEN
    assert position.state == PositionState.BREAKEVEN
    expected_stop = position.entry_price * (1.0 + cfg.fee_rate)
    assert position.stop_price == pytest.approx(expected_stop)


@pytest.mark.asyncio
async def test_breakeven_to_maximize_transition():
    """profit >= maximize_threshold_pct from BREAKEVEN → MAXIMIZE."""
    cfg = _minimal_config()
    strategy = ThreeStageExit(cfg)
    position = _position(state=PositionState.BREAKEVEN)

    target_price = position.entry_price * (1.0 + cfg.maximize_threshold_pct + 0.0001)
    new_state = await strategy.update_position_state(position, target_price)

    assert new_state == PositionState.MAXIMIZE
    assert position.state == PositionState.MAXIMIZE


@pytest.mark.asyncio
async def test_no_transition_below_breakeven_threshold():
    """profit just below breakeven_threshold → no transition (edge)."""
    cfg = _minimal_config()
    strategy = ThreeStageExit(cfg)
    position = _position(state=PositionState.SURVIVAL)

    just_below = position.entry_price * (1.0 + cfg.breakeven_threshold_pct - 0.0001)
    new_state = await strategy.update_position_state(position, just_below)
    assert new_state is None
    assert position.state == PositionState.SURVIVAL


# -----------------------------------------------------------------------------
# should_exit per-stage exits
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_survival_stage_hard_stop_triggers_stop_loss():
    """SURVIVAL stage + profit <= stop_loss_pct → STOP_LOSS exit."""
    cfg = _minimal_config()
    strategy = ThreeStageExit(cfg)
    position = _position(state=PositionState.SURVIVAL)

    stop_close = position.entry_price * (1.0 + cfg.stop_loss_pct)
    ctx = _context(position, close=stop_close)
    should_exit, signal = await strategy.should_exit(ctx)

    assert should_exit is True
    assert signal is not None
    assert signal.reason == ExitReason.STOP_LOSS
    assert signal.priority == 1


@pytest.mark.asyncio
async def test_breakeven_stage_stop_hit_triggers_breakeven_stop():
    """BREAKEVEN stage + price <= breakeven_stop → BREAKEVEN_STOP exit.

    The default config makes the breakeven_stop (entry*(1+fee_rate)=100_300)
    yield only +0.3% profit, which is below breakeven_threshold (1.5%) and would
    classify the stage as SURVIVAL. To exercise the BREAKEVEN branch we use a
    config with a lower breakeven_threshold and a very loose stop_loss so the
    hard-stop path does not preempt.
    """
    cfg = _minimal_config(
        breakeven_threshold_pct=0.001,  # 0.1%
        maximize_threshold_pct=0.05,
        stop_loss_pct=-0.50,  # ensure hard stop won't trigger
    )
    strategy = ThreeStageExit(cfg)
    position = _position(state=PositionState.BREAKEVEN)
    position.stop_price = position.entry_price * (1.0 + cfg.fee_rate)
    # Price equals breakeven stop → stop_hit = True. Profit = +0.3% which sits
    # between breakeven_threshold (0.1%) and maximize_threshold (5%) → BREAKEVEN.
    ctx = _context(position, close=position.stop_price)
    should_exit, signal = await strategy.should_exit(ctx)

    assert should_exit is True
    assert signal is not None
    assert signal.reason == ExitReason.BREAKEVEN_STOP
    assert signal.priority == 2


@pytest.mark.asyncio
async def test_maximize_stage_trailing_stop_triggers():
    """MAXIMIZE stage + price below trailing stop → TRAILING_STOP."""
    cfg = _minimal_config()
    strategy = ThreeStageExit(cfg)

    # Build a position whose highest_price is far above entry, then price drops.
    position = _position(state=PositionState.MAXIMIZE)
    # highest_price = +10% above entry → gain_from_entry > overshoot_threshold (7%)
    # → trailing gap = abs(overshoot_trailing_pct) = 1.5%
    position.highest_price = position.entry_price * 1.10

    overshoot_gap = abs(cfg.overshoot_trailing_pct)
    trailing_stop = position.highest_price * (1.0 - overshoot_gap)

    # Drop close just below trailing stop; profit must still keep stage = MAXIMIZE,
    # i.e. profit_pct >= maximize_threshold_pct.
    close = trailing_stop - 1.0
    profit_pct = (close - position.entry_price) / position.entry_price
    assert profit_pct >= cfg.maximize_threshold_pct  # sanity: still MAXIMIZE

    ctx = _context(position, close=close)
    should_exit, signal = await strategy.should_exit(ctx)

    assert should_exit is True
    assert signal is not None
    assert signal.reason == ExitReason.TRAILING_STOP
    assert signal.priority == 2


@pytest.mark.asyncio
async def test_bear_market_triggers_bear_exit_when_enabled():
    """BEAR regime + enable_bear_exit → BEAR_EXIT (priority 1)."""
    cfg = _minimal_config(enable_bear_exit=True)
    strategy = ThreeStageExit(cfg)
    position = _position(state=PositionState.SURVIVAL)

    # Small profit so stage stays SURVIVAL but no stop is hit.
    ctx = _context(
        position,
        close=position.entry_price * 1.001,
        market_state=MarketStateAdapter("BEAR"),
    )
    should_exit, signal = await strategy.should_exit(ctx)

    assert should_exit is True
    assert signal is not None
    assert signal.reason == ExitReason.BEAR_EXIT


@pytest.mark.asyncio
async def test_bear_exit_skipped_for_override_symbol():
    """scan_positions: override symbol is NOT bear-exited; non-override IS.

    Two positions in a bear market with enable_bear_exit=True:
    - pos_005930 is in bear_override_symbols → must NOT return BEAR_EXIT.
    - pos_000660 is NOT in bear_override_symbols → MUST return BEAR_EXIT.
    Default call (no bear_override_symbols) → both positions are BEAR_EXIT.
    """
    cfg = _minimal_config(enable_bear_exit=True)
    strategy = ThreeStageExit(cfg)

    bear_state = MarketStateAdapter("BEAR")
    # Both prices give a small profit so no stop/trailing fires.
    base_price = 100_000.0
    market_data = {
        "005930": {"close": base_price * 1.001},
        "000660": {"close": base_price * 1.001},
    }
    # Pin wall-clock to 10:00 KST (before EOD) so scan_positions's now_kst()
    # does not trigger EOD_CLOSE ahead of the BEAR check.
    _morning_kst = datetime(2026, 5, 15, 10, 0, 0, tzinfo=_KST)

    def _make_position(code: str) -> Position:
        return Position(
            id=f"pos_{code}",
            code=code,
            name=code,
            side=PositionSide.LONG,
            quantity=10,
            entry_price=base_price,
            entry_time=datetime(2026, 5, 15, 9, 55, 0, tzinfo=_KST),
            state=PositionState.SURVIVAL,
            highest_price=base_price,
            stop_price=0.0,
        )

    _module = "shared.strategy.exit.three_stage"
    with (
        patch(f"{_module}.now_kst", return_value=_morning_kst),
        patch(f"{_module}.is_trading_day_kst", return_value=False),
    ):
        pos_override = _make_position("005930")  # in override set
        pos_normal = _make_position("000660")  # NOT in override set

        # --- With override ---
        signals_with_override = await strategy.scan_positions(
            positions=[pos_override, pos_normal],
            market_data=market_data,
            market_state=bear_state,
            bear_override_symbols={"005930"},
        )
        reasons = {s.code: s.reason for s in signals_with_override}
        # Override symbol must NOT be BEAR_EXIT
        assert "005930" not in reasons or reasons["005930"] != ExitReason.BEAR_EXIT
        # Non-override symbol MUST be BEAR_EXIT
        assert reasons.get("000660") == ExitReason.BEAR_EXIT

        # --- Default (no override) → both positions are BEAR_EXIT ---
        pos_override2 = _make_position("005930")
        pos_normal2 = _make_position("000660")
        signals_default = await strategy.scan_positions(
            positions=[pos_override2, pos_normal2],
            market_data=market_data,
            market_state=bear_state,
        )
        reasons_default = {s.code: s.reason for s in signals_default}
        assert reasons_default.get("005930") == ExitReason.BEAR_EXIT
        assert reasons_default.get("000660") == ExitReason.BEAR_EXIT


@pytest.mark.asyncio
async def test_survival_stage_within_band_no_exit():
    """SURVIVAL stage + profit above stop and below breakeven → no exit."""
    cfg = _minimal_config()
    strategy = ThreeStageExit(cfg)
    position = _position(state=PositionState.SURVIVAL)

    # Just above hard stop, well below breakeven threshold.
    close = position.entry_price * (1.0 + cfg.stop_loss_pct + 0.005)
    ctx = _context(position, close=close)
    should_exit, signal = await strategy.should_exit(ctx)
    assert should_exit is False
    assert signal is None
