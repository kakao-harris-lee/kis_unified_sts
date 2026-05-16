from datetime import datetime, timedelta, timezone

import pytest

from shared.models.position import Position, PositionSide, PositionState
from shared.models.signal import ExitReason
from shared.strategy.base import ExitContext
from shared.strategy.exit.llm_directed_indicator_exit import (
    LLMDirectedIndicatorExit,
    LLMDirectedIndicatorExitConfig,
)

KST = timezone(timedelta(hours=9))


def _pos(side=PositionSide.LONG, entry=300.0):
    return Position(
        id="p1", code="101S6000", name="KF", side=side, quantity=1,
        entry_price=entry, entry_time=datetime(2026, 5, 18, 10, 0,
                                               tzinfo=KST),
        current_price=entry, highest_price=entry, lowest_price=entry,
        state=PositionState.SURVIVAL, strategy="llm_directed_indicator")


def _exit():
    return LLMDirectedIndicatorExit(LLMDirectedIndicatorExitConfig())


def _ctx(pos, price, hour=10, minute=30):
    now = datetime(2026, 5, 18, hour, minute, tzinfo=KST)
    # ATRDynamicExit.should_exit passes context.market_data straight into
    # _check_position as the per-symbol snapshot (no get_symbol_snapshot
    # re-extraction), so market_data must be the FLAT root-level snapshot
    # the sub-exits consume — NOT a code-keyed dict. With a code-keyed dict
    # ATR can't read the price and the hard-stop is never exercised.
    snapshot = {"close": price, "price": price}
    return ExitContext(
        position=pos,
        market_data=snapshot,
        indicators={"momentum_5m": {"williams_r": -50.0}},
        timestamp=now, metadata={"is_backtest": True})


@pytest.mark.asyncio
async def test_hard_stop_fires():
    p = _pos(entry=300.0)
    should, sig = await _exit().should_exit(_ctx(p, 285.0))  # -5%
    assert should is True
    assert sig.reason == ExitReason.STOP_LOSS


@pytest.mark.asyncio
async def test_no_exit_when_flat_and_in_range():
    p = _pos(entry=300.0)
    should, _ = await _exit().should_exit(_ctx(p, 300.5, hour=10,
                                               minute=30))
    assert should is False


@pytest.mark.asyncio
async def test_scan_positions_returns_list():
    p = _pos(entry=300.0)
    sigs = await _exit().scan_positions(
        [p], {p.code: {"close": 285.0, "price": 285.0}})
    assert isinstance(sigs, list)
    assert len(sigs) == 1


@pytest.mark.asyncio
async def test_atr_subexit_exception_logged_not_silently_swallowed(caplog):
    import logging
    ex = _exit()

    async def _boom(ctx):
        raise RuntimeError("atr boom")

    ex._atr.should_exit = _boom  # type: ignore[assignment]
    p = _pos(entry=300.0)
    with caplog.at_level(logging.ERROR):
        should, sig = await ex.should_exit(_ctx(p, 300.5))
    # composite stays resilient (momentum sees nothing → no exit) ...
    assert should is False and sig is None
    # ... but the ATR failure was logged LOUD (ERROR), not swallowed
    assert any(r.levelno >= logging.ERROR and "ATR sub-exit raised" in r.message
               for r in caplog.records)
