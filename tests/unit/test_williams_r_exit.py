"""Williams %R Exit Strategy Tests."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from shared.models.position import Position, PositionSide, PositionState
from shared.models.signal import ExitReason
from shared.strategy.base import ExitContext
from shared.strategy.exit.williams_r_exit import WilliamsRExit, WilliamsRExitConfig

KST = timezone(timedelta(hours=9))


@pytest.fixture
def config():
    return WilliamsRExitConfig(
        overbought_threshold=-20.0,
        max_stop_loss_pct=-0.03,
        time_cut_minutes=120,
        eod_close_hour=15,
        eod_close_minute=15,
        default_exit_confidence=0.8,
    )


@pytest.fixture
def exit_strategy(config):
    return WilliamsRExit(config)


def _make_position(
    code="005930",
    entry_price=50000,
    quantity=10,
    entry_hour=10,
    entry_minute=0,
):
    return Position(
        id="test-pos-1",
        code=code,
        name="삼성전자",
        side=PositionSide.LONG,
        quantity=quantity,
        entry_price=entry_price,
        entry_time=datetime(2026, 2, 25, entry_hour, entry_minute, tzinfo=KST),
        current_price=entry_price,
        highest_price=entry_price,
        lowest_price=entry_price,
        state=PositionState.SURVIVAL,
        strategy="williams_r",
    )


def _make_exit_context(
    position,
    current_price=50000,
    williams_r=-50.0,
    hour=12,
    minute=0,
    is_backtest=False,
):
    now = datetime(2026, 2, 25, hour, minute, tzinfo=KST)
    return ExitContext(
        position=position,
        market_data={
            position.code: {"close": current_price, "price": current_price},
        },
        indicators={
            "momentum_5m": {"williams_r": williams_r},
        },
        timestamp=now,
        metadata={"is_backtest": is_backtest},
    )


@pytest.mark.asyncio
async def test_hard_stop_triggers(exit_strategy):
    """Hard stop (-3%) 트리거."""
    pos = _make_position(entry_price=50000)
    ctx = _make_exit_context(pos, current_price=48400)  # -3.2%

    should, signal = await exit_strategy.should_exit(ctx)
    assert should is True
    assert signal is not None
    assert signal.reason == ExitReason.STOP_LOSS
    assert signal.priority == 1


@pytest.mark.asyncio
async def test_hard_stop_not_reached(exit_strategy):
    """손절 미도달 시 트리거 안함."""
    pos = _make_position(entry_price=50000)
    ctx = _make_exit_context(pos, current_price=49000, hour=10, minute=30)  # -2%, 30min

    should, signal = await exit_strategy.should_exit(ctx)
    assert should is False


@pytest.mark.asyncio
@patch("shared.strategy.exit.williams_r_exit.now_kst")
@patch("shared.strategy.exit.williams_r_exit.is_trading_day_kst", return_value=True)
async def test_eod_close(mock_trading_day, mock_now, exit_strategy):
    """EOD 청산 트리거."""
    mock_now.return_value = datetime(2026, 2, 25, 15, 20, tzinfo=KST)
    pos = _make_position(entry_price=50000)
    ctx = _make_exit_context(pos, current_price=51000, hour=15, minute=20)

    should, signal = await exit_strategy.should_exit(ctx)
    assert should is True
    assert signal.reason == ExitReason.EOD_CLOSE


@pytest.mark.asyncio
@patch("shared.strategy.exit.williams_r_exit.now_kst")
async def test_time_cut(mock_now, exit_strategy):
    """시간 손절: 120분 경과 + 수익 없음."""
    mock_now.return_value = datetime(2026, 2, 25, 13, 0, tzinfo=KST)
    pos = _make_position(entry_price=50000, entry_hour=10, entry_minute=0)
    # 3h elapsed, no profit
    ctx = _make_exit_context(pos, current_price=49900, hour=13, minute=0)

    should, signal = await exit_strategy.should_exit(ctx)
    assert should is True
    assert signal.reason == ExitReason.TIME_CUT


@pytest.mark.asyncio
@patch("shared.strategy.exit.williams_r_exit.now_kst")
async def test_time_cut_not_triggered_with_profit(mock_now, exit_strategy):
    """시간 초과해도 수익 있으면 time cut 안함."""
    mock_now.return_value = datetime(2026, 2, 25, 13, 0, tzinfo=KST)
    pos = _make_position(entry_price=50000, entry_hour=10, entry_minute=0)
    ctx = _make_exit_context(pos, current_price=51000, hour=13, minute=0)

    should, signal = await exit_strategy.should_exit(ctx)
    # Should not be TIME_CUT (might be overbought exit if williams_r triggers)
    if signal:
        assert signal.reason != ExitReason.TIME_CUT


@pytest.mark.asyncio
@patch("shared.strategy.exit.williams_r_exit.now_kst")
async def test_overbought_exit(mock_now, exit_strategy):
    """Williams %R 과매수 청산."""
    mock_now.return_value = datetime(2026, 2, 25, 11, 0, tzinfo=KST)
    pos = _make_position(entry_price=50000)
    ctx = _make_exit_context(pos, current_price=52000, williams_r=-15.0, hour=11, minute=0)

    should, signal = await exit_strategy.should_exit(ctx)
    assert should is True
    assert signal.reason == ExitReason.INDICATOR_EXIT
    assert signal.metadata.get("williams_r") == -15.0


@pytest.mark.asyncio
@patch("shared.strategy.exit.williams_r_exit.now_kst")
async def test_no_exit_neutral_williams_r(mock_now, exit_strategy):
    """%R 중립값 시 청산 안함."""
    mock_now.return_value = datetime(2026, 2, 25, 11, 0, tzinfo=KST)
    pos = _make_position(entry_price=50000)
    ctx = _make_exit_context(pos, current_price=50500, williams_r=-50.0, hour=11, minute=0)

    should, signal = await exit_strategy.should_exit(ctx)
    assert should is False


@pytest.mark.asyncio
async def test_hard_stop_priority_over_overbought(exit_strategy):
    """Hard stop이 과매수보다 우선."""
    pos = _make_position(entry_price=50000)
    # Price dropped below stop AND williams_r is overbought
    ctx = _make_exit_context(pos, current_price=48000, williams_r=-15.0)

    should, signal = await exit_strategy.should_exit(ctx)
    assert should is True
    assert signal.reason == ExitReason.STOP_LOSS  # priority 1


def test_config_defaults():
    """Config 기본값 검증."""
    config = WilliamsRExitConfig()
    assert config.overbought_threshold == -20.0
    assert config.max_stop_loss_pct == -0.03
    assert config.time_cut_minutes == 120
    assert config.eod_close_hour == 15
    assert config.eod_close_minute == 15
    assert config.default_exit_confidence == 0.8


def test_config_validation():
    """Config 유효성 검증."""
    with pytest.raises(ValueError, match="max_stop_loss_pct must be negative"):
        config = WilliamsRExitConfig(max_stop_loss_pct=0.01)
        config.validate()

    with pytest.raises(ValueError, match="time_cut_minutes must be positive"):
        config = WilliamsRExitConfig(time_cut_minutes=0)
        config.validate()
