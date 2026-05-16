from shared.llm.data_classes import MarketSignal
from shared.llm.market_context import MarketContext
from shared.strategy.entry.llm_directed_indicator import (
    LLMDirectedIndicatorConfig,
    _map_llm_bias,
)


def _cfg(**kw) -> LLMDirectedIndicatorConfig:
    base = dict(bias_confidence_min=0.6)
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
