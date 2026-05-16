from datetime import datetime, timedelta, timezone

import pytest

from shared.llm.data_classes import MarketSignal
from shared.llm.market_context import MarketContext
from shared.strategy.base import EntryContext
from shared.strategy.entry.llm_directed_indicator import (
    LLMDirectedIndicatorConfig,
    LLMDirectedIndicatorEntry,
    _map_llm_bias,
)


def _cfg(**kw) -> LLMDirectedIndicatorConfig:
    base = {"bias_confidence_min": 0.6}
    base.update(kw)
    return LLMDirectedIndicatorConfig(**base)


def test_none_context_is_flat():
    assert _map_llm_bias(None, _cfg()) == "FLAT"


def test_low_confidence_is_flat():
    mc = MarketContext(overall_signal=MarketSignal.STRONG_BULLISH,
                        confidence=0.3)
    assert _map_llm_bias(mc, _cfg()) == "FLAT"


def test_confident_bullish_is_long_bias():
    mc = MarketContext(overall_signal=MarketSignal.BULLISH, confidence=0.8)
    assert _map_llm_bias(mc, _cfg()) == "LONG_BIAS"


def test_confident_bearish_is_short_bias():
    mc = MarketContext(overall_signal=MarketSignal.STRONG_BEARISH,
                        confidence=0.9)
    assert _map_llm_bias(mc, _cfg()) == "SHORT_BIAS"


def test_confident_neutral_is_flat():
    mc = MarketContext(overall_signal=MarketSignal.NEUTRAL, confidence=0.9)
    assert _map_llm_bias(mc, _cfg()) == "FLAT"


def test_mask_mode_defaults_hard():
    # spec section 7: ship the switch (hard only implemented; soft = future Path B)
    assert _cfg().mask_mode == "hard"


def test_confidence_exactly_at_threshold_is_directional():
    # conf == bias_confidence_min passes the >= gate (boundary contract)
    mc = MarketContext(overall_signal=MarketSignal.BULLISH, confidence=0.6)
    assert _map_llm_bias(mc, _cfg(bias_confidence_min=0.6)) == "LONG_BIAS"


def test_raising_context_degrades_to_flat():
    class _Boom:
        confidence = 0.9

        def is_bullish(self):
            raise RuntimeError("boom")

        def is_bearish(self):
            return False

    assert _map_llm_bias(_Boom(), _cfg()) == "FLAT"


KST = timezone(timedelta(hours=9))


def _entry(**kw):
    return LLMDirectedIndicatorEntry(_cfg(signal_cooldown_seconds=0, **kw))


def _ctx(*, mom_rsi=10.0, ema_f=103.0, ema_s=100.0, adx=45.0,
         vwap=99.0, close=103.0, vel=0.8, rvol=2.0, atr=0.5,
         mc=None, hour=10, minute=30):
    now = datetime(2026, 5, 18, hour, minute, tzinfo=KST)
    return EntryContext(
        market_data={"code": "101S6000", "name": "KF", "close": close},
        indicators={
            "momentum_5m": {"rsi": mom_rsi, "williams_r": -95.0,
                            "sto_k": 5.0},
            "ema_5": ema_f, "ema_20": ema_s, "adx": adx,
            "vwap": vwap, "close": close,
            "volume_velocity": vel, "rvol": rvol, "atr": atr,
        },
        timestamp=now,
        market_context=mc,
    )


@pytest.mark.asyncio
async def test_flat_bias_long_signal_fires():
    sig = await _entry().generate(_ctx())   # bullish indicators, FLAT bias
    assert sig is not None
    assert sig.metadata["signal_direction"] == "long"


@pytest.mark.asyncio
async def test_long_bias_blocks_short_signal():
    mc = MarketContext(overall_signal=MarketSignal.STRONG_BULLISH,
                        confidence=0.9)
    # bearish indicators (overbought + downtrend) -> would be short
    sig = await _entry().generate(_ctx(
        mom_rsi=90.0, ema_f=97.0, ema_s=100.0, vwap=101.0, close=97.0,
        vel=-0.8, mc=mc))
    assert sig is None  # LONG_BIAS masks the short


@pytest.mark.asyncio
async def test_below_threshold_no_signal():
    sig = await _entry(entry_threshold=0.95).generate(_ctx())
    assert sig is None


@pytest.mark.asyncio
async def test_outside_market_hours_no_signal():
    sig = await _entry().generate(_ctx(hour=8, minute=0))
    assert sig is None


@pytest.mark.asyncio
async def test_missing_indicators_degrades_not_raises():
    now = datetime(2026, 5, 18, 10, 30, tzinfo=KST)
    ctx = EntryContext(market_data={"code": "X", "close": 100.0},
                       indicators={}, timestamp=now)
    sig = await _entry().generate(ctx)  # all scores 0 -> no signal, no raise
    assert sig is None


def _ctx_short(*, mc=None, hour=10, minute=30):
    # unambiguously bearish: overbought momentum + downtrend + outflow
    now = datetime(2026, 5, 18, hour, minute, tzinfo=KST)
    return EntryContext(
        market_data={"code": "101S6000", "name": "KF", "close": 97.0},
        indicators={
            "momentum_5m": {"rsi": 92.0, "williams_r": -5.0, "sto_k": 95.0},
            "ema_5": 97.0, "ema_20": 100.0, "adx": 45.0,
            "vwap": 101.0, "close": 97.0,
            "volume_velocity": -0.8, "rvol": 2.0, "atr": 0.5,
        },
        timestamp=now, market_context=mc)


@pytest.mark.asyncio
async def test_flat_bias_short_signal_fires():
    sig = await _entry().generate(_ctx_short())
    assert sig is not None
    assert sig.metadata["signal_direction"] == "short"


@pytest.mark.asyncio
async def test_short_bias_blocks_long_signal():
    mc = MarketContext(overall_signal=MarketSignal.STRONG_BEARISH,
                        confidence=0.9)
    # bullish indicators (the default _ctx) -> would be long; SHORT_BIAS masks
    sig = await _entry().generate(_ctx(mc=mc))
    assert sig is None
