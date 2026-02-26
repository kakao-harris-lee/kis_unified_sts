"""Tests for TrendPullbackEntry strategy."""
import pytest
from datetime import datetime, timedelta
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_context(
    code: str = "005930",
    close: float = 70000.0,
    bb_lower: float = 69000.0,
    bb_middle: float = 71000.0,
    rsi: float = 30.0,
    volume: float = 2000.0,
    volume_ma: float = 1000.0,
    atr: float = 1400.0,  # atr/close = 2.0% > round_trip_cost(0.5%) * min_ratio(2.0) = 1.0%
    williams_r: float = -75.0,
    timestamp: datetime = None,
    watchlist_codes: list = None,
    include_watchlist: bool = True,
):
    """Build an EntryContext for trend_pullback tests."""
    from shared.strategy.base import EntryContext

    if timestamp is None:
        timestamp = datetime(2026, 2, 26, 10, 30, 0)

    metadata: dict[str, Any] = {}
    if include_watchlist:
        codes = watchlist_codes if watchlist_codes is not None else [code]
        metadata["daily_watchlist"] = {
            "strategies": {
                "trend_pullback": codes,
            }
        }

    return EntryContext(
        market_data={
            "code": code,
            "name": "삼성전자",
            "close": close,
        },
        indicators={
            "bb_lower": bb_lower,
            "bb_middle": bb_middle,
            "rsi": rsi,
            "volume": volume,
            "volume_ma": volume_ma,
            "atr": atr,
            "momentum_5m": {"williams_r": williams_r},
        },
        timestamp=timestamp,
        metadata=metadata,
    )


def _make_strategy(
    bb_touch_buffer: float = 1.005,
    rsi_oversold: float = 35.0,
    williams_r_oversold: float = -80.0,
    williams_r_reversal: float = -70.0,
    volume_threshold: float = 1.0,
    min_atr_cost_ratio: float = 2.0,
    round_trip_cost: float = 0.005,
    skip_market_open_minutes: int = 30,
    skip_market_close_minutes: int = 15,
    signal_cooldown_seconds: int = 300,
    confidence_base: float = 0.6,
):
    from shared.strategy.entry.trend_pullback import TrendPullbackEntry, TrendPullbackConfig

    config = TrendPullbackConfig(
        bb_touch_buffer=bb_touch_buffer,
        rsi_oversold=rsi_oversold,
        williams_r_oversold=williams_r_oversold,
        williams_r_reversal=williams_r_reversal,
        volume_threshold=volume_threshold,
        min_atr_cost_ratio=min_atr_cost_ratio,
        round_trip_cost=round_trip_cost,
        skip_market_open_minutes=skip_market_open_minutes,
        skip_market_close_minutes=skip_market_close_minutes,
        signal_cooldown_seconds=signal_cooldown_seconds,
        confidence_base=confidence_base,
    )
    return TrendPullbackEntry(config)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generates_signal_on_bb_touch():
    """BB touch + RSI oversold + in watchlist → signal."""
    strategy = _make_strategy()

    # close = 69200 <= bb_lower(69000) * 1.005(69345) = True
    ctx = _make_context(
        close=69200.0,
        bb_lower=69000.0,
        rsi=30.0,  # < 35
        atr=1400.0,  # 1400/69200 ≈ 2.02% >= 0.005*2.0 = 1.0%
    )
    signal = await strategy.generate(ctx)

    assert signal is not None
    assert signal.code == "005930"
    assert signal.strategy == "trend_pullback"
    assert signal.metadata.get("signal_direction") == "long"
    assert signal.metadata.get("trigger") == "bb_touch"
    assert signal.metadata.get("stop_loss") is not None


@pytest.mark.asyncio
async def test_generates_signal_on_wr_reversal():
    """Williams %R reversal + RSI oversold → signal."""
    strategy = _make_strategy()
    code = "005935"

    # First tick: establish prev_wr in oversold zone
    ctx1 = _make_context(
        code=code,
        close=70000.0,
        bb_lower=68000.0,  # no BB touch (close > bb_lower * buffer)
        rsi=32.0,
        williams_r=-85.0,  # oversold
    )
    sig1 = await strategy.generate(ctx1)
    # No BB touch, prev_wr not yet established as prev → None
    assert sig1 is None

    # Second tick: WR crosses from oversold to reversal zone
    ctx2 = _make_context(
        code=code,
        close=70000.0,
        bb_lower=68000.0,
        rsi=32.0,
        williams_r=-68.0,  # >= reversal threshold (-70)
        timestamp=datetime(2026, 2, 26, 10, 31, 0),
    )
    sig2 = await strategy.generate(ctx2)

    assert sig2 is not None
    assert sig2.metadata.get("trigger") == "wr_reversal"
    assert sig2.metadata.get("signal_direction") == "long"


@pytest.mark.asyncio
async def test_rejects_not_in_watchlist():
    """Code not in daily watchlist → None."""
    strategy = _make_strategy()

    ctx = _make_context(
        code="005930",
        close=69000.0,
        bb_lower=69500.0,
        rsi=30.0,
        watchlist_codes=["999999"],  # different code
    )
    signal = await strategy.generate(ctx)
    assert signal is None


@pytest.mark.asyncio
async def test_rejects_no_bb_touch_high_rsi():
    """No BB touch and RSI above threshold → None."""
    strategy = _make_strategy()

    ctx = _make_context(
        close=72000.0,    # well above bb_lower
        bb_lower=69000.0,
        rsi=50.0,         # not oversold
        williams_r=-50.0, # not in oversold zone
    )
    signal = await strategy.generate(ctx)
    assert signal is None


@pytest.mark.asyncio
async def test_minimum_edge_filter():
    """Low ATR/close ratio → None (insufficient edge to cover costs)."""
    strategy = _make_strategy(min_atr_cost_ratio=2.0, round_trip_cost=0.005)

    # atr/close = 100/70000 = 0.143% < 0.005*2.0 = 1.0%
    ctx = _make_context(
        close=70000.0,
        bb_lower=70000.0,
        rsi=30.0,
        atr=100.0,  # very low ATR
    )
    signal = await strategy.generate(ctx)
    assert signal is None


@pytest.mark.asyncio
async def test_skip_market_open():
    """Signal during first 30 min of session → None."""
    strategy = _make_strategy(skip_market_open_minutes=30)

    # 09:15 is within first 30 min (09:00 + 30 = 09:30)
    ctx = _make_context(
        close=69000.0,
        bb_lower=69500.0,
        rsi=30.0,
        timestamp=datetime(2026, 2, 26, 9, 15, 0),
    )
    signal = await strategy.generate(ctx)
    assert signal is None


@pytest.mark.asyncio
async def test_skip_market_close():
    """Signal during last 15 min of session → None."""
    strategy = _make_strategy(skip_market_close_minutes=15)

    # 15:05 is within last 15 min (15:15 - 15 = 15:00)
    ctx = _make_context(
        close=69000.0,
        bb_lower=69500.0,
        rsi=30.0,
        timestamp=datetime(2026, 2, 26, 15, 5, 0),
    )
    signal = await strategy.generate(ctx)
    assert signal is None


@pytest.mark.asyncio
async def test_volume_filter_blocks():
    """Low volume → None."""
    strategy = _make_strategy(volume_threshold=1.0)

    ctx = _make_context(
        close=69000.0,
        bb_lower=69500.0,
        rsi=30.0,
        volume=500.0,     # < volume_ma(1000) * 1.0
        volume_ma=1000.0,
    )
    signal = await strategy.generate(ctx)
    assert signal is None


@pytest.mark.asyncio
async def test_cooldown():
    """Signal within cooldown window → None."""
    strategy = _make_strategy(signal_cooldown_seconds=300)
    code = "005930"

    t0 = datetime(2026, 2, 26, 10, 30, 0)

    # Fire first signal
    ctx1 = _make_context(
        code=code,
        close=69000.0,
        bb_lower=69500.0,
        rsi=30.0,
        timestamp=t0,
    )
    sig1 = await strategy.generate(ctx1)
    assert sig1 is not None

    # Attempt second signal 60s later (still within 300s cooldown)
    ctx2 = _make_context(
        code=code,
        close=69000.0,
        bb_lower=69500.0,
        rsi=30.0,
        timestamp=t0 + timedelta(seconds=60),
    )
    sig2 = await strategy.generate(ctx2)
    assert sig2 is None

    # After cooldown expires → signal fires again
    ctx3 = _make_context(
        code=code,
        close=69000.0,
        bb_lower=69500.0,
        rsi=30.0,
        timestamp=t0 + timedelta(seconds=301),
    )
    sig3 = await strategy.generate(ctx3)
    assert sig3 is not None


def test_config_defaults():
    """TrendPullbackConfig has expected defaults."""
    from shared.strategy.entry.trend_pullback import TrendPullbackConfig

    cfg = TrendPullbackConfig()
    assert cfg.bb_period == 20
    assert cfg.bb_std == 2.0
    assert cfg.bb_touch_buffer == 1.005
    assert cfg.rsi_oversold == 35.0
    assert cfg.williams_r_oversold == -80.0
    assert cfg.williams_r_reversal == -70.0
    assert cfg.volume_threshold == 1.0
    assert cfg.min_atr_cost_ratio == 2.0
    assert cfg.round_trip_cost == 0.005
    assert cfg.skip_market_open_minutes == 30
    assert cfg.skip_market_close_minutes == 15
    assert cfg.signal_cooldown_seconds == 300
    assert cfg.allow_short is False
    assert cfg.confidence_base == 0.6


def test_required_indicators():
    """TrendPullbackEntry reports all required indicators."""
    from shared.strategy.entry.trend_pullback import TrendPullbackEntry, TrendPullbackConfig

    strategy = TrendPullbackEntry(TrendPullbackConfig())
    indicators = strategy.required_indicators

    assert "bb_lower" in indicators
    assert "bb_middle" in indicators
    assert "rsi" in indicators
    assert "volume" in indicators
    assert "volume_ma" in indicators
    assert "atr" in indicators
    assert "momentum_5m" in indicators


@pytest.mark.asyncio
async def test_no_watchlist_key_passes_all():
    """When daily_watchlist is absent entirely, Layer 1 gate is skipped."""
    strategy = _make_strategy()

    ctx = _make_context(
        close=69000.0,
        bb_lower=69500.0,
        rsi=30.0,
        include_watchlist=False,  # no watchlist in metadata
    )
    signal = await strategy.generate(ctx)
    # Should not be blocked by watchlist — may still pass or fail other checks
    # In this case all other conditions pass so we expect a signal
    assert signal is not None


@pytest.mark.asyncio
async def test_config_from_dict():
    """TrendPullbackConfig.from_dict() works correctly."""
    from shared.strategy.entry.trend_pullback import TrendPullbackConfig

    cfg = TrendPullbackConfig.from_dict({
        "bb_period": 14,
        "rsi_oversold": 40.0,
        "unknown_field": "ignored",
    })
    assert cfg.bb_period == 14
    assert cfg.rsi_oversold == 40.0
    assert cfg.bb_std == 2.0  # default


@pytest.mark.asyncio
async def test_stop_loss_in_metadata():
    """stop_loss in metadata = close - atr * 2.5."""
    strategy = _make_strategy()

    close = 69000.0
    atr = 1400.0
    ctx = _make_context(close=close, bb_lower=69500.0, rsi=30.0, atr=atr)
    signal = await strategy.generate(ctx)

    assert signal is not None
    expected_sl = close - atr * 2.5
    assert abs(signal.metadata["stop_loss"] - expected_sl) < 0.01
