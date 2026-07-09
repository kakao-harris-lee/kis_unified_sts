"""Live indicator payload key-set pins (P2-b resolver-path safety net).

``StreamingIndicatorResolver.collect_entry_indicators`` forwards the payloads
built here verbatim to live strategies, so the exact key names ARE the live
contract. These pins freeze the key sets of ``get_indicators`` /
``get_indicators_tf`` / ``get_indicator_features`` so refactoring the name
derivations (e.g. onto the shared ``flat_key`` catalog) can be proven
payload-identical. A failing pin means the live payload changed — that is
never a refactor.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from services.trading.indicator_engine import StreamingIndicatorEngine

_BASE_KEYS = {
    "adx",
    "atr",
    "bb_lower",
    "bb_middle",
    "bb_upper",
    "ema_5",
    "ema_20",
    "ema_60",
    "ema_aligned",
    "ema_daily_aligned",
    "high_5",
    "mfi",
    "rsi",
    "rvol",
    "stochrsi_d",
    "stochrsi_k",
    "stochrsi_k_prev",
    "volume_acceleration",
    "volume_ma",
    "volume_velocity",
    "vwap",
}

_TF_KEYS = {"bb_lower", "bb_middle", "bb_upper", "rsi"}

_FEATURE_KEYS = {
    "atr",
    "bb_lower_dist",
    "bb_position",
    "bb_upper_dist",
    "bb_width",
    "candle_body",
    "ema_ratio_5",
    "ema_ratio_10",
    "ema_ratio_20",
    "hl_range",
    "ma_ratio_5",
    "ma_ratio_10",
    "ma_ratio_20",
    "macd",
    "macd_hist",
    "macd_signal",
    "price_change_5",
    "returns",
    "rsi",
    "sma_ratio_60",
    "sma_ratio_120",
    "stoch_d",
    "stoch_k",
    "volatility",
    "volume_ratio",
}


@pytest.fixture
def warm_engine() -> StreamingIndicatorEngine:
    engine = StreamingIndicatorEngine(
        bb_period=20,
        rsi_period=14,
        high_period=5,
        rvol_short=5,
        rvol_long=20,
        staleness_seconds=0,
        mtf_timeframes=[5],
        ema_periods=[5, 20, 60],
        stochrsi_enabled=True,
    )
    symbol = "005930"
    cumulative_volume = 0
    for minute in range(180):
        ts = datetime(2026, 2, 17, 9 + minute // 60, minute % 60, 30)
        price = 70000.0 + (minute % 13) * 40 - (minute % 7) * 25 + minute * 3
        cumulative_volume += 1000 + minute * 10
        engine.on_tick(
            symbol,
            {
                "close": price,
                "high": price + 50,
                "low": price - 50,
                "volume": cumulative_volume,
            },
            ts,
        )
    return engine


def test_get_indicators_key_set_is_pinned(
    warm_engine: StreamingIndicatorEngine,
) -> None:
    assert set(warm_engine.get_indicators("005930")) == _BASE_KEYS


def test_get_indicators_tf_key_set_is_pinned(
    warm_engine: StreamingIndicatorEngine,
) -> None:
    assert set(warm_engine.get_indicators_tf("005930", 5)) == _TF_KEYS


def test_get_indicator_features_key_set_is_pinned(
    warm_engine: StreamingIndicatorEngine,
) -> None:
    assert set(warm_engine.get_indicator_features("005930")) == _FEATURE_KEYS
