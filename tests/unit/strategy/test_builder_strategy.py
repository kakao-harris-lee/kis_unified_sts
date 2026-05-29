"""Tests for the builder_v1 entry + exit (no-code Strategy Builder runtime)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from shared.models.signal import ExitReason, SignalType
from shared.strategy.base import EntryContext, ExitContext
from shared.strategy.entry.builder_strategy import (
    BuilderStrategyConfig,
    BuilderStrategyEntry,
)
from shared.strategy.exit.builder_strategy_exit import (
    BuilderStrategyExit,
    BuilderStrategyExitConfig,
)


def _make_state(asset_class: str = "stock") -> dict:
    """Minimal BuilderState dict that the evaluator can parse.

    Entry: rsi > 30 (single-condition AND group).
    Exit:  rsi > 70.
    """
    return {
        "metadata": {
            "id": "test_strategy",
            "name": "Test Strategy",
            "description": "",
            "category": "custom",
            "tags": ["test"],
            "author": "test",
        },
        "asset_class": asset_class,
        "indicators": [
            {
                "indicator_id": "rsi",
                "alias": "rsi",
                "params": {},
                "output": "value",
            }
        ],
        "entry": {
            "logic": "AND",
            "conditions": [
                {
                    "left": {
                        "type": "indicator",
                        "indicator_alias": "rsi",
                        "indicator_output": "value",
                    },
                    "operator": "greater_than",
                    "right": {"type": "value", "value": 30.0},
                }
            ],
        },
        "exit": {
            "logic": "AND",
            "conditions": [
                {
                    "left": {
                        "type": "indicator",
                        "indicator_alias": "rsi",
                        "indicator_output": "value",
                    },
                    "operator": "greater_than",
                    "right": {"type": "value", "value": 70.0},
                }
            ],
        },
        "risk": {
            "order_amount": 1_000_000,
            "stop_loss": {"enabled": True, "percent": 5.0},
            "take_profit": {"enabled": False, "percent": 10.0},
            "trailing_stop": {"enabled": False, "percent": 3.0},
        },
    }


# --- Entry tests --------------------------------------------------------


def test_entry_registers_and_initializes() -> None:
    entry = BuilderStrategyEntry(BuilderStrategyConfig(builder_state=_make_state()))
    assert entry.name == "builder_v1::test_strategy"
    assert entry.required_indicators == []


@pytest.mark.asyncio
async def test_entry_emits_signal_when_conditions_pass() -> None:
    entry = BuilderStrategyEntry(BuilderStrategyConfig(builder_state=_make_state()))
    ctx = EntryContext(
        market_data={"code": "005930", "name": "삼성전자", "close": 70000.0},
        indicators={"rsi.value": 45.0},
        timestamp=datetime.now(UTC),
    )
    signal = await entry.generate(ctx)
    assert signal is not None
    assert signal.signal_type == SignalType.ENTRY
    assert signal.metadata["signal_direction"] == "long"
    assert signal.metadata["builder_state_id"] == "test_strategy"
    assert 0.0 < signal.confidence <= 1.0


@pytest.mark.asyncio
async def test_entry_no_signal_when_conditions_fail() -> None:
    entry = BuilderStrategyEntry(BuilderStrategyConfig(builder_state=_make_state()))
    ctx = EntryContext(
        market_data={"code": "005930", "name": "삼성전자", "close": 70000.0},
        indicators={"rsi.value": 20.0},  # below threshold 30
        timestamp=datetime.now(UTC),
    )
    assert await entry.generate(ctx) is None


@pytest.mark.asyncio
async def test_entry_no_signal_when_indicator_missing() -> None:
    entry = BuilderStrategyEntry(BuilderStrategyConfig(builder_state=_make_state()))
    ctx = EntryContext(
        market_data={"code": "005930", "name": "삼성전자", "close": 70000.0},
        indicators={},  # no rsi
        timestamp=datetime.now(UTC),
    )
    assert await entry.generate(ctx) is None


@pytest.mark.asyncio
async def test_entry_skips_non_stock_asset() -> None:
    entry = BuilderStrategyEntry(
        BuilderStrategyConfig(builder_state=_make_state(asset_class="futures"))
    )
    ctx = EntryContext(
        market_data={"code": "101S6000", "close": 1000.0},
        indicators={"rsi.value": 50.0},
        timestamp=datetime.now(UTC),
    )
    assert await entry.generate(ctx) is None


# --- Exit tests ---------------------------------------------------------


class _Pos:
    """Minimal Position-like stub."""

    def __init__(self, code: str, entry_price: float, quantity: int = 1):
        self.code = code
        self.name = ""
        self.id = "pos_1"
        self.entry_price = entry_price
        self.current_price = entry_price
        self.quantity = quantity


@pytest.mark.asyncio
async def test_exit_stop_loss_triggers_on_drawdown() -> None:
    exit_strat = BuilderStrategyExit(
        BuilderStrategyExitConfig(builder_state=_make_state(), stop_loss_pct=5.0)
    )
    ctx = ExitContext(
        position=_Pos("005930", entry_price=10000.0),
        market_data={"close": 9000.0},  # -10%
        indicators={"rsi.value": 50.0},
        timestamp=datetime.now(UTC),
    )
    triggered, signal = await exit_strat.should_exit(ctx)
    assert triggered
    assert signal is not None
    assert signal.reason == ExitReason.STOP_LOSS


@pytest.mark.asyncio
async def test_exit_take_profit_triggers_on_gain() -> None:
    exit_strat = BuilderStrategyExit(
        BuilderStrategyExitConfig(
            builder_state=_make_state(),
            stop_loss_pct=0,
            take_profit_pct=10.0,
        )
    )
    ctx = ExitContext(
        position=_Pos("005930", entry_price=10000.0),
        market_data={"close": 12000.0},  # +20%
        indicators={"rsi.value": 50.0},
        timestamp=datetime.now(UTC),
    )
    triggered, signal = await exit_strat.should_exit(ctx)
    assert triggered
    assert signal is not None
    assert signal.reason == ExitReason.TARGET_REACHED


@pytest.mark.asyncio
async def test_exit_conditions_fire_strategy_exit() -> None:
    exit_strat = BuilderStrategyExit(
        BuilderStrategyExitConfig(
            builder_state=_make_state(),
            stop_loss_pct=0,
            take_profit_pct=0,
        )
    )
    ctx = ExitContext(
        position=_Pos("005930", entry_price=10000.0),
        market_data={"close": 10500.0},  # +5% (neither SL nor TP)
        indicators={"rsi.value": 75.0},  # exit condition (rsi > 70)
        timestamp=datetime.now(UTC),
    )
    triggered, signal = await exit_strat.should_exit(ctx)
    assert triggered
    assert signal is not None
    assert signal.reason == ExitReason.STRATEGY_EXIT


@pytest.mark.asyncio
async def test_exit_holds_when_conditions_not_met() -> None:
    exit_strat = BuilderStrategyExit(
        BuilderStrategyExitConfig(
            builder_state=_make_state(),
            stop_loss_pct=5.0,
            take_profit_pct=10.0,
        )
    )
    ctx = ExitContext(
        position=_Pos("005930", entry_price=10000.0),
        market_data={"close": 10200.0},  # +2% — neither SL/TP nor rsi>70
        indicators={"rsi.value": 50.0},
        timestamp=datetime.now(UTC),
    )
    triggered, signal = await exit_strat.should_exit(ctx)
    assert not triggered
    assert signal is None


# --- Trailing stop tests ------------------------------------------------


def _trailing_exit(trailing_pct: float) -> BuilderStrategyExit:
    return BuilderStrategyExit(
        BuilderStrategyExitConfig(
            builder_state=_make_state(),
            stop_loss_pct=0,
            take_profit_pct=0,
            trailing_stop_pct=trailing_pct,
        )
    )


async def _step(exit_strat: BuilderStrategyExit, pos: _Pos, price: float):
    ctx = ExitContext(
        position=pos,
        market_data={"close": price},
        indicators={"rsi.value": 50.0},  # never trips the rsi>70 exit
        timestamp=datetime.now(UTC),
    )
    return await exit_strat.should_exit(ctx)


@pytest.mark.asyncio
async def test_exit_trailing_stop_triggers_after_peak() -> None:
    exit_strat = _trailing_exit(3.0)
    pos = _Pos("005930", entry_price=10000.0)
    # Rally to 11000 (HWM=11000); 3% trail floor = 10670 → still above, hold.
    triggered, _ = await _step(exit_strat, pos, 11000.0)
    assert not triggered
    # Retrace to 10600 (≤ 10670) → trailing stop fires.
    triggered, signal = await _step(exit_strat, pos, 10600.0)
    assert triggered
    assert signal is not None
    assert signal.reason == ExitReason.TRAILING_STOP


@pytest.mark.asyncio
async def test_exit_trailing_stop_holds_within_band() -> None:
    exit_strat = _trailing_exit(3.0)
    pos = _Pos("005930", entry_price=10000.0)
    await _step(exit_strat, pos, 11000.0)  # HWM=11000
    # Pull back to 10800 — still above 10670 floor → hold.
    triggered, signal = await _step(exit_strat, pos, 10800.0)
    assert not triggered
    assert signal is None


@pytest.mark.asyncio
async def test_exit_trailing_stop_not_armed_before_profit() -> None:
    # Price never exceeds entry → trailing must not fire (that is stop-loss's
    # job). HWM stays at entry, so the trailing branch stays disarmed.
    exit_strat = _trailing_exit(3.0)
    pos = _Pos("005930", entry_price=10000.0)
    triggered, signal = await _step(exit_strat, pos, 9600.0)  # -4%, SL is off
    assert not triggered
    assert signal is None


@pytest.mark.asyncio
async def test_exit_trailing_stop_disabled_when_pct_zero() -> None:
    exit_strat = _trailing_exit(0.0)
    pos = _Pos("005930", entry_price=10000.0)
    await _step(exit_strat, pos, 12000.0)  # big rally
    triggered, signal = await _step(exit_strat, pos, 10000.0)  # large retrace
    assert not triggered
    assert signal is None


@pytest.mark.asyncio
async def test_exit_trailing_stop_seeds_from_position_highest_price() -> None:
    # Simulate a process restart: a fresh exit instance (empty _hwm) inherits a
    # position whose highest_price (restored from Redis) is already above entry.
    # The trailing stop must arm immediately on a retrace, not reset to entry.
    exit_strat = _trailing_exit(3.0)
    pos = _Pos("005930", entry_price=10000.0)
    pos.highest_price = 11000.0  # peak before the restart; 3% floor = 10670
    assert not exit_strat._hwm  # fresh instance, no in-memory peak
    # First tick after restart retraces below the 10670 floor → fire.
    triggered, signal = await _step(exit_strat, pos, 10600.0)
    assert triggered
    assert signal is not None
    assert signal.reason == ExitReason.TRAILING_STOP


# --- Registry integration ----------------------------------------------


def test_registry_exposes_builder_v1() -> None:
    from shared.strategy.registry import (
        EntryRegistry,
        ExitRegistry,
        register_builtin_components,
    )

    register_builtin_components()
    assert EntryRegistry.is_registered("builder_v1")
    assert ExitRegistry.is_registered("builder_v1_exit")
