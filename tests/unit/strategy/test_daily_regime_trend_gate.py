from __future__ import annotations

from shared.strategy.gates.daily_regime_trend_gate import (
    DailyRegimeTrendFilterConfig,
    apply_daily_regime_trend_filter,
)


def _indicators(**overrides):
    data = {
        "daily_close": 110.0,
        "daily_ema_20": 105.0,
        "daily_ema_20_prev": 104.0,
        "daily_ema_60": 100.0,
        "daily_rsi_14": 62.0,
    }
    data.update(overrides)
    return data


def test_long_bias_blocks_short_candidate():
    cfg = DailyRegimeTrendFilterConfig(enabled=True)

    decision = apply_daily_regime_trend_filter(
        config=cfg,
        indicators=_indicators(),
        signal_direction="short",
    )

    assert decision.allowed is False
    assert decision.bias == "long"
    assert decision.reason == "daily_long_bias_blocks_short"


def test_long_bias_allows_long_candidate():
    cfg = DailyRegimeTrendFilterConfig(enabled=True)

    decision = apply_daily_regime_trend_filter(
        config=cfg,
        indicators=_indicators(),
        signal_direction="long",
    )

    assert decision.allowed is True
    assert decision.bias == "long"


def test_sideways_regime_blocks_when_configured():
    cfg = DailyRegimeTrendFilterConfig(enabled=True, block_sideways=True)

    decision = apply_daily_regime_trend_filter(
        config=cfg,
        indicators=_indicators(
            daily_close=101.0,
            daily_ema_20=100.2,
            daily_ema_20_prev=100.1,
            daily_ema_60=100.0,
            daily_rsi_14=50.0,
        ),
        signal_direction="long",
    )

    assert decision.allowed is False
    assert decision.bias == "sideways"


def test_missing_inputs_are_permissive_by_default():
    cfg = DailyRegimeTrendFilterConfig(enabled=True)

    decision = apply_daily_regime_trend_filter(
        config=cfg,
        indicators={},
        signal_direction="long",
    )

    assert decision.allowed is True
    assert decision.bias == "unknown"
    assert decision.reason.startswith("missing_daily_regime:")


def test_zero_rsi_is_valid_short_bias_input():
    cfg = DailyRegimeTrendFilterConfig(enabled=True)

    decision = apply_daily_regime_trend_filter(
        config=cfg,
        indicators=_indicators(
            daily_close=90.0,
            daily_ema_20=95.0,
            daily_ema_20_prev=96.0,
            daily_ema_60=100.0,
            daily_rsi_14=0.0,
        ),
        signal_direction="short",
    )

    assert decision.allowed is True
    assert decision.bias == "short"
