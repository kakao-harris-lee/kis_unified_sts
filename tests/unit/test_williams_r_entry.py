"""Williams %R Entry Strategy Tests."""

from datetime import datetime, timedelta, timezone

import pytest

from shared.strategy.base import EntryContext
from shared.strategy.entry.williams_r import WilliamsRConfig, WilliamsREntry


@pytest.fixture
def config():
    return WilliamsRConfig(
        williams_r_period=14,
        oversold_threshold=-80.0,
        reversal_threshold=-80.0,
        trend_filter=True,
        volume_confirm=True,
        volume_threshold=1.0,
        signal_cooldown_seconds=300,
        skip_market_open_minutes=30,
        skip_market_close_minutes=15,
    )


@pytest.fixture
def entry(config):
    return WilliamsREntry(config)


def _make_context(
    code="005930",
    close=50000,
    bb_middle=49000,
    volume=1000,
    volume_ma=900,
    williams_r=-75.0,
    hour=10,
    minute=30,
):
    """Helper to create an EntryContext with Williams %R data."""
    now = datetime(2026, 2, 25, hour, minute, tzinfo=timezone(timedelta(hours=9)))
    return EntryContext(
        market_data={"code": code, "name": "삼성전자", "close": close},
        indicators={
            "bb_middle": bb_middle,
            "volume": volume,
            "volume_ma": volume_ma,
            "momentum_5m": {"williams_r": williams_r},
        },
        timestamp=now,
    )


@pytest.mark.asyncio
async def test_oversold_reversal_signal(entry):
    """과매도 반전 시 진입 시그널 발생."""
    # First call: set previous %R (deep oversold)
    ctx1 = _make_context(williams_r=-90.0, hour=10, minute=0)
    result1 = await entry.generate(ctx1)
    assert result1 is None  # No previous value yet

    # Second call: %R crossed above reversal threshold
    ctx2 = _make_context(williams_r=-75.0, hour=10, minute=5)
    result2 = await entry.generate(ctx2)
    assert result2 is not None
    assert result2.code == "005930"
    assert result2.strategy == "williams_r"
    assert result2.metadata["signal_direction"] == "long"
    assert result2.metadata["williams_r"] == -75.0
    assert result2.metadata["prev_williams_r"] == -90.0
    assert result2.metadata["wr_reversal_points"] == 15.0
    assert result2.metadata["wr_depth_points"] == 10.0
    assert result2.metadata["bb_distance_pct"] > 0
    assert 0 < result2.metadata["confidence"] <= 1.0


@pytest.mark.asyncio
async def test_no_signal_without_oversold(entry):
    """과매도 구간 미진입 시 시그널 없음."""
    # Previous was not oversold
    ctx1 = _make_context(williams_r=-70.0)
    await entry.generate(ctx1)

    # Current doesn't matter — previous wasn't in oversold zone
    ctx2 = _make_context(williams_r=-60.0, minute=35)
    result = await entry.generate(ctx2)
    assert result is None


@pytest.mark.asyncio
async def test_trend_filter_blocks(entry):
    """추세 필터 (close <= bb_middle) 시 차단."""
    ctx1 = _make_context(williams_r=-90.0)
    await entry.generate(ctx1)

    # close < bb_middle → blocked
    ctx2 = _make_context(williams_r=-75.0, close=48000, bb_middle=49000, minute=35)
    result = await entry.generate(ctx2)
    assert result is None


@pytest.mark.asyncio
async def test_trend_filter_disabled(config):
    """추세 필터 비활성화 시 close <= bb_middle 통과."""
    config.trend_filter = False
    entry = WilliamsREntry(config)

    ctx1 = _make_context(williams_r=-90.0)
    await entry.generate(ctx1)

    ctx2 = _make_context(williams_r=-75.0, close=48000, bb_middle=49000, minute=35)
    result = await entry.generate(ctx2)
    assert result is not None


@pytest.mark.asyncio
async def test_volume_filter_blocks(entry):
    """거래량 부족 시 차단."""
    ctx1 = _make_context(williams_r=-90.0)
    await entry.generate(ctx1)

    # volume < volume_threshold * volume_ma
    ctx2 = _make_context(williams_r=-75.0, volume=500, volume_ma=900, minute=35)
    result = await entry.generate(ctx2)
    assert result is None


@pytest.mark.asyncio
async def test_cooldown(entry):
    """쿨다운 기간 내 재진입 차단."""
    # Generate first signal
    ctx1 = _make_context(williams_r=-90.0, hour=10, minute=0)
    await entry.generate(ctx1)
    ctx2 = _make_context(williams_r=-75.0, hour=10, minute=5)
    result1 = await entry.generate(ctx2)
    assert result1 is not None

    # Reset prev_williams_r for new reversal
    entry._prev_williams_r["005930"] = -90.0

    # Within cooldown (300s = 5min) → blocked
    ctx3 = _make_context(williams_r=-75.0, hour=10, minute=8)
    result2 = await entry.generate(ctx3)
    assert result2 is None


@pytest.mark.asyncio
async def test_skip_market_open(entry):
    """장 시작 30분 스킵."""
    ctx1 = _make_context(williams_r=-90.0, hour=9, minute=10)
    result = await entry.generate(ctx1)
    assert result is None


@pytest.mark.asyncio
async def test_skip_market_close(entry):
    """장 마감 15분 전 스킵."""
    ctx1 = _make_context(williams_r=-90.0, hour=15, minute=5)
    result = await entry.generate(ctx1)
    assert result is None


@pytest.mark.asyncio
async def test_no_momentum_data(entry):
    """모멘텀 데이터 없을 때 None 반환."""
    now = datetime(2026, 2, 25, 10, 30, tzinfo=timezone(timedelta(hours=9)))
    ctx = EntryContext(
        market_data={"code": "005930", "name": "삼성전자", "close": 50000},
        indicators={"bb_middle": 49000},
        timestamp=now,
    )
    result = await entry.generate(ctx)
    assert result is None


def test_config_defaults():
    """Config 기본값 검증."""
    config = WilliamsRConfig()
    assert config.williams_r_period == 14
    assert config.oversold_threshold == -80.0
    assert config.reversal_threshold == -80.0
    assert config.trend_filter is True
    assert config.volume_confirm is True
    assert config.volume_threshold == 1.0
    assert config.allow_short is False
    assert config.stop_loss_pct == 3.0
    assert config.signal_cooldown_seconds == 300
    assert config.skip_market_open_minutes == 30
    assert config.skip_market_close_minutes == 15


def test_confidence_calculation(entry):
    """Confidence 계산 검증."""
    # Deep reversal + above bb_middle → higher confidence
    c1 = entry._calculate_confidence(-95.0, -75.0, 51000, 49000)
    # Shallow reversal + at bb_middle → lower confidence
    c2 = entry._calculate_confidence(-82.0, -78.0, 49100, 49000)
    assert 0 < c1 <= 1.0
    assert 0 < c2 <= 1.0
    assert c1 > c2


@pytest.mark.asyncio
async def test_overextended_signal_gets_position_size_multiplier(config):
    """BB 중심선에서 멀어진 과확장 반전은 작은 탐색 포지션으로 표시."""
    config.max_full_size_bb_distance_pct = 1.0
    config.overextended_position_size_multiplier = 0.2
    entry = WilliamsREntry(config)

    await entry.generate(
        _make_context(williams_r=-90.0, close=55_000, bb_middle=49_000)
    )
    result = await entry.generate(
        _make_context(williams_r=-75.0, close=55_000, bb_middle=49_000, minute=35)
    )

    assert result is not None
    assert result.metadata["bb_distance_pct"] > 1.0
    assert result.metadata["position_size_multiplier"] == 0.2
