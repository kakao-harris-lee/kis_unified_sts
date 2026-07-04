"""Test StochRSI trend entry strategy."""

from datetime import datetime

import pytest


@pytest.mark.asyncio
async def test_stochrsi_entry_signal_buy():
    """Test StochRSI entry signal generation for BUY (oversold)."""
    from shared.strategy.base import EntryContext
    from shared.strategy.entry.stochrsi_trend import StochRSIConfig, StochRSITrendEntry

    config = StochRSIConfig(
        rsi_period=14,
        stoch_period=14,
        k_period=3,
        d_period=3,
        oversold=20,
        overbought=80,
    )

    strategy = StochRSITrendEntry(config)

    # Create test data with oversold StochRSI crossing up
    context = EntryContext(
        market_data={
            "code": "005930",
            "name": "삼성전자",
            "close": 58000,
            "stochrsi_k": 25,  # K line
            "stochrsi_d": 15,  # D line - K crossing above D (bullish)
            "stochrsi_k_prev": 12,  # Previous K was below current
        },
        indicators={},
        current_positions=[],
        timestamp=datetime.now(),
    )

    signal = await strategy.generate(context)

    assert signal is not None
    assert signal.code == "005930"
    assert signal.strategy == "stochrsi_trend"


@pytest.mark.asyncio
async def test_stochrsi_entry_signal_sell():
    """Test StochRSI entry signal generation for SELL (overbought)."""
    from shared.strategy.base import EntryContext
    from shared.strategy.entry.stochrsi_trend import StochRSIConfig, StochRSITrendEntry

    config = StochRSIConfig()
    strategy = StochRSITrendEntry(config)

    # Create test data with overbought StochRSI crossing down
    context = EntryContext(
        market_data={
            "code": "005930",
            "close": 62000,
            "stochrsi_k": 75,  # K line
            "stochrsi_d": 85,  # D line - K crossing below D (bearish)
            "stochrsi_k_prev": 88,  # Previous K was higher (crossing down)
        },
        timestamp=datetime.now(),
    )

    signal = await strategy.generate(context)

    # Short signal in overbought zone
    assert signal is not None
    assert signal.strategy == "stochrsi_trend"


@pytest.mark.asyncio
async def test_stochrsi_no_signal_in_neutral_zone():
    """Test StochRSI returns None in neutral zone."""
    from shared.strategy.base import EntryContext
    from shared.strategy.entry.stochrsi_trend import StochRSIConfig, StochRSITrendEntry

    config = StochRSIConfig()
    strategy = StochRSITrendEntry(config)

    context = EntryContext(
        market_data={
            "code": "005930",
            "close": 60000,
            "stochrsi_k": 50,  # Neutral zone
            "stochrsi_d": 50,
            "stochrsi_k_prev": 48,
        },
        timestamp=datetime.now(),
    )

    signal = await strategy.generate(context)
    assert signal is None


def test_stochrsi_required_indicators():
    """Test StochRSI reports required indicators."""
    from shared.strategy.entry.stochrsi_trend import StochRSIConfig, StochRSITrendEntry

    config = StochRSIConfig()
    strategy = StochRSITrendEntry(config)

    indicators = strategy.required_indicators
    assert "stochrsi_k" in indicators
    assert "stochrsi_d" in indicators


# ---------------------------------------------------------------------------
# M2 (2026-07-04): runtime producer wiring — the strategy was inert (always
# read the neutral-50 default) because nothing produced stochrsi_k/d/k_prev.
# StreamingIndicatorEngine.get_indicators now emits them (config-gated).
# ---------------------------------------------------------------------------

import math  # noqa: E402

from services.trading.indicator_engine import StreamingIndicatorEngine  # noqa: E402

_STOCHRSI_SYMBOL = "101W9000"


def _stochrsi_series(n: int) -> list[float]:
    """RNG-free oscillating close series that sweeps StochRSI across 0..100.

    Two coprime sinusoids on a mild uptrend give RSI (and thus StochRSI)
    intermediate values, producing genuine %K/%D crossovers in both the
    oversold and overbought zones (a monotonic series only yields degenerate
    0/100 StochRSI and never a strict in-zone crossover).
    """
    return [
        100.0 + 8.0 * math.sin(i / 5.0) + 3.0 * math.sin(i / 2.0) + 0.05 * i
        for i in range(n)
    ]


def _warm_stochrsi_engine(
    closes: list[float], *, enabled: bool
) -> StreamingIndicatorEngine:
    engine = StreamingIndicatorEngine(
        bb_period=20, staleness_seconds=0, stochrsi_enabled=enabled
    )
    engine.seed_candles(
        _STOCHRSI_SYMBOL,
        [
            {"open": c, "high": c + 0.4, "low": c - 0.4, "close": c, "volume": 1000 + i}
            for i, c in enumerate(closes)
        ],
    )
    return engine


def test_get_indicators_omits_stochrsi_keys_by_default():
    """Default (disabled) engine emits NO stochrsi keys — byte-for-byte backward
    compatible with pre-M2 behavior; the producer is opt-in only."""
    engine = _warm_stochrsi_engine(_stochrsi_series(51), enabled=False)
    ind = engine.get_indicators(_STOCHRSI_SYMBOL)
    assert ind  # engine is warm and returns the usual indicators
    assert "stochrsi_k" not in ind
    assert "stochrsi_d" not in ind
    assert "stochrsi_k_prev" not in ind


def test_get_indicators_emits_stochrsi_keys_when_enabled():
    """Enabled engine produces the three flat keys the strategy consumes, and the
    values reflect real StochRSI (not the neutral-50 the strategy used to read)."""
    engine = _warm_stochrsi_engine(_stochrsi_series(51), enabled=True)
    ind = engine.get_indicators(_STOCHRSI_SYMBOL)
    for key in ("stochrsi_k", "stochrsi_d", "stochrsi_k_prev"):
        assert key in ind
        assert 0.0 <= ind[key] <= 100.0
    # At end=51 the series is deeply oversold — proves the producer is live and
    # NOT returning the neutral 50 default that made the strategy inert.
    assert ind["stochrsi_k"] < 20.0
    assert ind["stochrsi_d"] < 20.0


@pytest.mark.asyncio
async def test_stochrsi_producer_feeds_buy_signal():
    """End-to-end: producer output drives a real BUY (bullish crossover, oversold)."""
    from shared.strategy.base import EntryContext
    from shared.strategy.entry.stochrsi_trend import StochRSIConfig, StochRSITrendEntry

    closes = _stochrsi_series(51)  # end=51 => oversold %K crosses above %D
    engine = _warm_stochrsi_engine(closes, enabled=True)
    ind = engine.get_indicators(_STOCHRSI_SYMBOL)

    market_data = dict(ind)
    market_data.update(code=_STOCHRSI_SYMBOL, name="test", close=closes[-1])
    strategy = StochRSITrendEntry(StochRSIConfig())
    signal = await strategy.generate(
        EntryContext(
            market_data=market_data,
            indicators={},
            current_positions=[],
            timestamp=datetime.now(),
        )
    )

    assert signal is not None, "producer wiring failed — strategy still inert"
    assert signal.metadata["signal_direction"] == "long"
    assert signal.strategy == "stochrsi_trend"


@pytest.mark.asyncio
async def test_stochrsi_producer_feeds_short_signal():
    """End-to-end: producer output drives a real SELL (bearish crossover, overbought)."""
    from shared.strategy.base import EntryContext
    from shared.strategy.entry.stochrsi_trend import StochRSIConfig, StochRSITrendEntry

    closes = _stochrsi_series(51)[:42]  # end=42 => overbought %K crosses below %D
    engine = _warm_stochrsi_engine(closes, enabled=True)
    ind = engine.get_indicators(_STOCHRSI_SYMBOL)

    market_data = dict(ind)
    market_data.update(code=_STOCHRSI_SYMBOL, name="test", close=closes[-1])
    strategy = StochRSITrendEntry(StochRSIConfig())
    signal = await strategy.generate(
        EntryContext(
            market_data=market_data,
            indicators={},
            current_positions=[],
            timestamp=datetime.now(),
        )
    )

    assert signal is not None, "producer wiring failed — strategy still inert"
    assert signal.metadata["signal_direction"] == "short"
    assert signal.strategy == "stochrsi_trend"
