"""Tests for TrendPullbackEntry multi-timeframe (daily) functionality."""
import pytest
from datetime import datetime
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_context(
    code: str = "005930",
    close: float = 72000.0,
    bb_lower: float = 69000.0,
    bb_middle: float = 71000.0,
    rsi: float = 30.0,
    volume: float = 2000.0,
    volume_ma: float = 1000.0,
    atr: float = 1440.0,  # 1440/72000 = 2.0% > round_trip_cost(0.5%) * min_ratio(2.0) = 1.0%
    williams_r: float = -75.0,
    sma_200: float = 70000.0,  # Daily SMA(200) - default allows signal (close > sma_200)
    timestamp: datetime = None,
    watchlist_codes: list = None,
    include_watchlist: bool = True,
    use_daily_prefix: bool = False,
):
    """Build an EntryContext for trend_pullback MTF tests."""
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

    # Support both direct and daily_ prefixed indicators
    # (orchestrator injects with daily_ prefix for paper trading)
    sma_key = "daily_sma_200" if use_daily_prefix else "sma_200"

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
            sma_key: sma_200,
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
# Daily Trend Filter Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_allows_signal_when_above_daily_sma200():
    """close > daily SMA(200) + BB touch → signal (with-trend)."""
    strategy = _make_strategy()

    # close=70200 > sma_200=70000 → with trend
    # close=70200 <= bb_lower(70000) * 1.005(70350) → BB touch
    ctx = _make_context(
        close=70200.0,
        bb_lower=70000.0,
        sma_200=70000.0,  # close > sma_200
        rsi=30.0,
        atr=1404.0,  # 1404/70200 = 2.0%
    )
    signal = await strategy.generate(ctx)

    assert signal is not None
    assert signal.code == "005930"
    assert signal.strategy == "trend_pullback"
    assert signal.metadata.get("signal_direction") == "long"
    assert signal.metadata.get("trigger") == "bb_touch"


@pytest.mark.asyncio
async def test_blocks_signal_when_below_daily_sma200():
    """close <= daily SMA(200) → reject (counter-trend)."""
    strategy = _make_strategy()

    # close=68000 < sma_200=70000 → counter-trend, blocked
    ctx = _make_context(
        close=68000.0,
        bb_lower=67000.0,  # BB touch would trigger
        sma_200=70000.0,  # close < sma_200 → reject
        rsi=30.0,
        atr=1360.0,  # 1360/68000 = 2.0%
    )
    signal = await strategy.generate(ctx)

    assert signal is None


@pytest.mark.asyncio
async def test_blocks_signal_when_equal_to_daily_sma200():
    """close == daily SMA(200) → reject (not strictly above)."""
    strategy = _make_strategy()

    # close=70000 == sma_200=70000 → reject (not > sma_200)
    ctx = _make_context(
        close=70000.0,
        bb_lower=69000.0,  # BB touch would trigger
        sma_200=70000.0,  # close == sma_200 → reject
        rsi=30.0,
        atr=1400.0,  # 1400/70000 = 2.0%
    )
    signal = await strategy.generate(ctx)

    assert signal is None


@pytest.mark.asyncio
async def test_blocks_signal_when_sma200_missing():
    """Missing daily SMA(200) indicator → reject."""
    strategy = _make_strategy()

    # Build context without sma_200
    from shared.strategy.base import EntryContext

    ctx = EntryContext(
        market_data={
            "code": "005930",
            "name": "삼성전자",
            "close": 72000.0,
        },
        indicators={
            "bb_lower": 70000.0,
            "bb_middle": 71000.0,
            "rsi": 30.0,
            "volume": 2000.0,
            "volume_ma": 1000.0,
            "atr": 1440.0,
            "momentum_5m": {"williams_r": -75.0},
            # sma_200 missing
        },
        timestamp=datetime(2026, 2, 26, 10, 30, 0),
        metadata={
            "daily_watchlist": {
                "strategies": {
                    "trend_pullback": ["005930"],
                }
            }
        },
    )
    signal = await strategy.generate(ctx)

    # Missing sma_200 → _get() returns 0.0 → close > 0 is True, but sma_200 <= 0 check rejects
    assert signal is None


@pytest.mark.asyncio
async def test_blocks_signal_when_sma200_invalid():
    """Invalid daily SMA(200) (0 or negative) → reject."""
    strategy = _make_strategy()

    # sma_200 = 0 → invalid
    ctx = _make_context(
        close=72000.0,
        bb_lower=70000.0,
        sma_200=0.0,  # invalid
        rsi=30.0,
    )
    signal = await strategy.generate(ctx)
    assert signal is None

    # sma_200 = negative → invalid
    ctx = _make_context(
        close=72000.0,
        bb_lower=70000.0,
        sma_200=-1000.0,  # invalid
        rsi=30.0,
    )
    signal = await strategy.generate(ctx)
    assert signal is None


@pytest.mark.asyncio
async def test_wr_reversal_respects_daily_trend():
    """Williams %R reversal signal also requires close > SMA(200)."""
    strategy = _make_strategy()
    code = "005935"

    # First tick: establish prev_wr in oversold zone
    ctx1 = _make_context(
        code=code,
        close=72000.0,
        bb_lower=68000.0,  # no BB touch
        sma_200=70000.0,  # above trend
        rsi=32.0,
        williams_r=-85.0,  # oversold
    )
    sig1 = await strategy.generate(ctx1)
    assert sig1 is None  # No trigger yet

    # Second tick: WR crosses from oversold to reversal zone
    # close > sma_200 → allow
    ctx2 = _make_context(
        code=code,
        close=72000.0,
        bb_lower=68000.0,
        sma_200=70000.0,  # above trend
        rsi=32.0,
        williams_r=-68.0,  # >= reversal threshold
        timestamp=datetime(2026, 2, 26, 10, 31, 0),
    )
    sig2 = await strategy.generate(ctx2)

    assert sig2 is not None
    assert sig2.metadata.get("trigger") == "wr_reversal"
    assert sig2.metadata.get("signal_direction") == "long"

    # Third tick: same WR reversal but close < sma_200 → reject
    ctx3 = _make_context(
        code=code,
        close=68000.0,  # below sma_200
        bb_lower=66000.0,
        sma_200=70000.0,  # close < sma_200 → reject
        rsi=32.0,
        williams_r=-68.0,  # WR reversal still present
        timestamp=datetime(2026, 2, 26, 10, 32, 0),
    )
    sig3 = await strategy.generate(ctx3)

    assert sig3 is None  # Counter-trend rejected


# ---------------------------------------------------------------------------
# daily_ Prefix Compatibility Tests (Paper Trading)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_supports_daily_prefix_for_paper_trading():
    """Orchestrator injects daily indicators with 'daily_' prefix → strategy handles both."""
    strategy = _make_strategy()

    # Use daily_ prefix (paper trading mode)
    ctx = _make_context(
        close=70200.0,
        bb_lower=70000.0,
        sma_200=70000.0,  # close > sma_200
        rsi=30.0,
        atr=1404.0,  # 1404/70200 = 2.0%
        use_daily_prefix=True,  # indicators["daily_sma_200"]
    )
    signal = await strategy.generate(ctx)

    assert signal is not None
    assert signal.code == "005930"
    assert signal.strategy == "trend_pullback"


@pytest.mark.asyncio
async def test_daily_prefix_also_respects_trend_filter():
    """daily_ prefix indicators also enforce trend filter."""
    strategy = _make_strategy()

    # close < daily_sma_200 → reject
    ctx = _make_context(
        close=68000.0,
        bb_lower=67000.0,
        sma_200=70000.0,  # close < sma_200 → reject
        rsi=30.0,
        atr=1360.0,
        use_daily_prefix=True,  # indicators["daily_sma_200"]
    )
    signal = await strategy.generate(ctx)

    assert signal is None


# ---------------------------------------------------------------------------
# Multi-Timeframe Integration Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_daily_trend_plus_intraday_bb_touch():
    """Daily trend (SMA200) + Intraday BB touch → signal."""
    strategy = _make_strategy()

    # Daily: close > SMA(200) → uptrend
    # Intraday: BB touch + RSI oversold → pullback entry
    ctx = _make_context(
        close=70800.0,
        bb_lower=70500.0,  # close <= bb_lower * 1.005(70852.5)
        sma_200=69000.0,   # close > sma_200 → with trend
        rsi=28.0,          # oversold
        volume=1500.0,
        volume_ma=1000.0,
        atr=1416.0,        # 1416/70800 = 2.0%
    )
    signal = await strategy.generate(ctx)

    assert signal is not None
    assert signal.metadata.get("trigger") == "bb_touch"
    assert signal.metadata.get("signal_direction") == "long"


@pytest.mark.asyncio
async def test_daily_trend_plus_intraday_wr_reversal():
    """Daily trend (SMA200) + Intraday WR reversal → signal."""
    strategy = _make_strategy()
    code = "005930"

    # First tick: establish oversold WR
    ctx1 = _make_context(
        code=code,
        close=72000.0,
        bb_lower=68000.0,  # no BB touch
        sma_200=70000.0,   # above trend
        rsi=32.0,
        williams_r=-85.0,  # oversold
    )
    await strategy.generate(ctx1)  # Store prev_wr

    # Second tick: WR reversal + daily uptrend
    ctx2 = _make_context(
        code=code,
        close=72000.0,
        bb_lower=68000.0,
        sma_200=70000.0,   # above trend
        rsi=32.0,
        williams_r=-68.0,  # reversal
        timestamp=datetime(2026, 2, 26, 10, 31, 0),
    )
    signal = await strategy.generate(ctx2)

    assert signal is not None
    assert signal.metadata.get("trigger") == "wr_reversal"
    assert signal.metadata.get("signal_direction") == "long"


@pytest.mark.asyncio
async def test_strong_daily_uptrend_allows_weak_pullback():
    """Strong daily uptrend (close >> SMA200) allows weaker intraday pullback."""
    strategy = _make_strategy()

    # Daily: close 10% above SMA(200) → strong uptrend
    # Intraday: marginal BB touch + RSI near threshold
    ctx = _make_context(
        close=76800.0,     # 9.7% above sma_200
        bb_lower=76500.0,  # close <= bb_lower * 1.005(76882.5) → marginal touch
        sma_200=70000.0,   # close >> sma_200 → strong uptrend
        rsi=34.5,          # just below 35 threshold
        volume=1200.0,
        volume_ma=1000.0,
        atr=1536.0,        # 1536/76800 = 2.0%
    )
    signal = await strategy.generate(ctx)

    assert signal is not None
    assert signal.metadata.get("trigger") == "bb_touch"
    # Confidence should reflect strong trend
    assert signal.confidence >= 0.6


@pytest.mark.asyncio
async def test_weak_daily_uptrend_still_enforces_filter():
    """Weak daily uptrend (close slightly > SMA200) still allows signal."""
    strategy = _make_strategy()

    # Daily: close 0.3% above SMA(200) → weak uptrend (but still valid)
    # Intraday: strong BB touch + deep RSI oversold
    ctx = _make_context(
        close=70200.0,     # 0.3% above sma_200
        bb_lower=70000.0,  # close <= bb_lower * 1.005(70350)
        sma_200=70000.0,   # close > sma_200 (barely)
        rsi=25.0,          # deep oversold
        volume=2000.0,
        volume_ma=1000.0,
        atr=1404.0,        # 1404/70200 = 2.0%
    )
    signal = await strategy.generate(ctx)

    assert signal is not None
    assert signal.metadata.get("trigger") == "bb_touch"


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_required_indicators_includes_daily_sma200():
    """Strategy declares daily_sma_200 in required_indicators."""
    strategy = _make_strategy()

    assert "daily_sma_200" in strategy.required_indicators


@pytest.mark.asyncio
async def test_multiple_symbols_independent_daily_trend():
    """Each symbol's daily trend is evaluated independently."""
    strategy = _make_strategy()

    # Symbol A: above trend → signal
    ctx_a = _make_context(
        code="005930",
        close=70200.0,
        bb_lower=70000.0,
        sma_200=70000.0,  # above trend
        rsi=30.0,
        atr=1404.0,  # 1404/70200 = 2.0%
    )
    sig_a = await strategy.generate(ctx_a)
    assert sig_a is not None

    # Symbol B: below trend → reject
    ctx_b = _make_context(
        code="005935",
        close=68000.0,
        bb_lower=67000.0,
        sma_200=70000.0,  # below trend
        rsi=30.0,
        atr=1360.0,
    )
    sig_b = await strategy.generate(ctx_b)
    assert sig_b is None


@pytest.mark.asyncio
async def test_daily_trend_filter_runs_before_cooldown():
    """Daily trend filter is checked before cooldown (fail fast)."""
    strategy = _make_strategy(signal_cooldown_seconds=300)
    code = "005930"

    # First signal: above trend → allowed
    ctx1 = _make_context(
        code=code,
        close=70200.0,
        bb_lower=70000.0,
        sma_200=70000.0,  # above trend
        rsi=30.0,
        atr=1404.0,  # 1404/70200 = 2.0%
        timestamp=datetime(2026, 2, 26, 10, 30, 0),
    )
    sig1 = await strategy.generate(ctx1)
    assert sig1 is not None

    # Second signal: below trend + within cooldown → reject (trend filter runs first)
    ctx2 = _make_context(
        code=code,
        close=68000.0,
        bb_lower=67000.0,
        sma_200=70000.0,  # below trend → reject before cooldown check
        rsi=30.0,
        atr=1360.0,
        timestamp=datetime(2026, 2, 26, 10, 31, 0),  # 1 min later (within 5 min cooldown)
    )
    sig2 = await strategy.generate(ctx2)
    assert sig2 is None  # Rejected by trend filter, not cooldown


@pytest.mark.asyncio
async def test_daily_trend_filter_runs_after_watchlist():
    """Watchlist filter runs before daily trend filter (Layer 1 → Layer 2)."""
    strategy = _make_strategy()

    # Not in watchlist + above trend → reject (watchlist checked first)
    ctx = _make_context(
        code="005930",
        close=72000.0,
        bb_lower=70000.0,
        sma_200=70000.0,  # above trend
        rsi=30.0,
        watchlist_codes=["999999"],  # different code
    )
    signal = await strategy.generate(ctx)
    assert signal is None


@pytest.mark.asyncio
async def test_daily_trend_filter_runs_before_intraday_triggers():
    """Daily trend filter is evaluated before checking BB touch or WR reversal."""
    strategy = _make_strategy()

    # Perfect intraday conditions but below daily trend → reject
    ctx = _make_context(
        close=68000.0,
        bb_lower=67900.0,  # strong BB touch (close < bb_lower * 1.005)
        sma_200=70000.0,   # close < sma_200 → reject before checking BB
        rsi=20.0,          # deep oversold
        volume=3000.0,     # high volume
        volume_ma=1000.0,
        atr=1360.0,
    )
    signal = await strategy.generate(ctx)
    assert signal is None
