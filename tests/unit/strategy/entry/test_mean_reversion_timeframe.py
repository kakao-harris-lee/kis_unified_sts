from shared.strategy.entry.mean_reversion import (
    MeanReversionConfig,
    MeanReversionEntry,
)


def test_default_is_1m_no_mtf_base_key():
    e = MeanReversionEntry(MeanReversionConfig())
    assert "mtf_base_15m" not in e.required_indicators
    assert "bb_lower" in e.required_indicators


def test_timeframe_minutes_adds_mtf_base_key():
    e = MeanReversionEntry(MeanReversionConfig(timeframe_minutes=15))
    ri = e.required_indicators
    assert "mtf_base_15m" in ri
    assert {"bb_lower", "bb_upper", "bb_middle", "rsi"} <= set(ri)
