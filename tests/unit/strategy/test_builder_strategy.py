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
async def test_entry_emits_long_signal_for_futures() -> None:
    entry = BuilderStrategyEntry(
        BuilderStrategyConfig(builder_state=_make_state(asset_class="futures"))
    )
    ctx = EntryContext(
        market_data={"code": "101S6000", "close": 1000.0},
        indicators={"rsi.value": 50.0},  # rsi > 30 → entry condition passes
        timestamp=datetime.now(UTC),
    )
    signal = await entry.generate(ctx)
    assert signal is not None
    assert signal.signal_type == SignalType.ENTRY
    assert signal.metadata["signal_direction"] == "long"  # Phase 1: long-only
    assert signal.code == "101S6000"  # futures symbol flows through
    assert signal.metadata["builder_state_id"] == "test_strategy"
    assert 0.0 < signal.confidence <= 1.0


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
        BuilderStrategyExitConfig(
            builder_state=_make_state(), stop_loss_pct=5.0
        )
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


# --- Futures safety guards (EOD close + hard-stop cap) -----------------


def _futures_state() -> dict:
    state = _make_state(asset_class="futures")
    state["exit"]["conditions"] = []  # isolate SL/EOD behavior from conditions
    return state


@pytest.mark.asyncio
async def test_futures_exit_hard_stop_caps_loose_user_stop() -> None:
    # User sets a loose 10% stop; futures cap (3%) must trigger earlier.
    exit_strat = BuilderStrategyExit(
        BuilderStrategyExitConfig(builder_state=_futures_state(), stop_loss_pct=10.0)
    )
    ctx = ExitContext(
        position=_Pos("101S6000", entry_price=400.0),
        market_data={"close": 384.0},  # -4% → beyond the 3% cap, within user's 10%
        indicators={},
        timestamp=datetime(2026, 6, 1, 1, 0, tzinfo=UTC),  # 10:00 KST (intraday)
    )
    triggered, signal = await exit_strat.should_exit(ctx)
    assert triggered
    assert signal is not None
    assert signal.reason == ExitReason.STOP_LOSS


@pytest.mark.asyncio
async def test_futures_exit_hard_stop_applies_when_user_disables() -> None:
    # User disables the stop (0); futures still enforces the cap.
    exit_strat = BuilderStrategyExit(
        BuilderStrategyExitConfig(builder_state=_futures_state(), stop_loss_pct=0.0)
    )
    ctx = ExitContext(
        position=_Pos("101S6000", entry_price=400.0),
        market_data={"close": 386.0},  # -3.5%
        indicators={},
        timestamp=datetime(2026, 6, 1, 1, 0, tzinfo=UTC),  # 10:00 KST
    )
    triggered, signal = await exit_strat.should_exit(ctx)
    assert triggered
    assert signal is not None
    assert signal.reason == ExitReason.STOP_LOSS


@pytest.mark.asyncio
async def test_futures_exit_eod_close_after_cutoff() -> None:
    exit_strat = BuilderStrategyExit(
        BuilderStrategyExitConfig(builder_state=_futures_state(), stop_loss_pct=5.0)
    )
    ctx = ExitContext(
        position=_Pos("101S6000", entry_price=400.0),
        market_data={"close": 401.0},  # +0.25% — no SL/TP
        indicators={},
        timestamp=datetime(2026, 6, 1, 6, 20, tzinfo=UTC),  # 15:20 KST ≥ 15:15
    )
    triggered, signal = await exit_strat.should_exit(ctx)
    assert triggered
    assert signal is not None
    assert signal.reason == ExitReason.EOD_CLOSE


@pytest.mark.asyncio
async def test_stock_exit_unaffected_by_futures_safety() -> None:
    # Stock with a 10% stop at -4% must NOT exit (no futures cap applies).
    exit_strat = BuilderStrategyExit(
        BuilderStrategyExitConfig(builder_state=_make_state(), stop_loss_pct=10.0)
    )
    # remove the rsi>70 exit condition so only SL/EOD logic is under test
    exit_strat.config.builder_state["exit"]["conditions"] = []
    ctx = ExitContext(
        position=_Pos("005930", entry_price=10000.0),
        market_data={"close": 9600.0},  # -4%
        indicators={},
        timestamp=datetime(2026, 6, 1, 6, 20, tzinfo=UTC),  # 15:20 KST
    )
    triggered, _ = await exit_strat.should_exit(ctx)
    assert not triggered


@pytest.mark.asyncio
async def test_futures_exit_eod_close_fires_exactly_at_cutoff() -> None:
    # 15:15 KST is the cutoff; EOD must fire at exactly the boundary.
    exit_strat = BuilderStrategyExit(
        BuilderStrategyExitConfig(builder_state=_futures_state(), stop_loss_pct=5.0)
    )
    ctx = ExitContext(
        position=_Pos("101S6000", entry_price=400.0),
        market_data={"close": 401.0},  # +0.25% — no SL/TP
        indicators={},
        timestamp=datetime(2026, 6, 1, 6, 15, tzinfo=UTC),  # 15:15 KST == cutoff
    )
    triggered, signal = await exit_strat.should_exit(ctx)
    assert triggered
    assert signal is not None
    assert signal.reason == ExitReason.EOD_CLOSE


@pytest.mark.asyncio
async def test_futures_exit_no_eod_close_before_cutoff() -> None:
    # 15:14 KST is one minute before the cutoff; EOD must NOT fire and a flat
    # price keeps the (uncapped) stop dormant → no exit.
    exit_strat = BuilderStrategyExit(
        BuilderStrategyExitConfig(builder_state=_futures_state(), stop_loss_pct=5.0)
    )
    ctx = ExitContext(
        position=_Pos("101S6000", entry_price=400.0),
        market_data={"close": 401.0},  # +0.25% — no SL/TP
        indicators={},
        timestamp=datetime(2026, 6, 1, 6, 14, tzinfo=UTC),  # 15:14 KST < cutoff
    )
    triggered, _ = await exit_strat.should_exit(ctx)
    assert not triggered


@pytest.mark.asyncio
async def test_futures_exit_take_profit_not_preempted_by_safety() -> None:
    # A gain beyond TP must still fire TARGET_REACHED on futures: the futures
    # safety block (EOD/hard-stop) sits before TP but neither fires on a +gain
    # intraday, so control falls through to the take-profit branch.
    exit_strat = BuilderStrategyExit(
        BuilderStrategyExitConfig(
            builder_state=_futures_state(), stop_loss_pct=0, take_profit_pct=10.0
        )
    )
    ctx = ExitContext(
        position=_Pos("101S6000", entry_price=400.0),
        market_data={"close": 444.0},  # +11% → beyond TP 10%
        indicators={},
        timestamp=datetime(2026, 6, 1, 1, 0, tzinfo=UTC),  # 10:00 KST intraday
    )
    triggered, signal = await exit_strat.should_exit(ctx)
    assert triggered
    assert signal is not None
    assert signal.reason == ExitReason.TARGET_REACHED
