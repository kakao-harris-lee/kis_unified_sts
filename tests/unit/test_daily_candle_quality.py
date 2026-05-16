from datetime import date

import pandas as pd

from shared.collector.historical.daily_quality import (
    DailyCandleQualityConfig,
    clean_daily_candle_frame,
    quality_fetch_limit,
)


def test_clean_daily_candle_frame_dedupes_by_date_and_keeps_latest():
    cfg = DailyCandleQualityConfig(repeated_ohlcv_run_min=5)
    df = pd.DataFrame(
        [
            ["005930", date(2026, 5, 14), 100, 110, 90, 105, 1000],
            ["005930", date(2026, 5, 14), 101, 111, 91, 106, 1200],
            ["005930", date(2026, 5, 15), 106, 112, 100, 110, 1300],
        ],
        columns=["code", "date", "open", "high", "low", "close", "volume"],
    )

    cleaned = clean_daily_candle_frame(df, config=cfg)

    assert cleaned["date"].tolist() == [date(2026, 5, 14), date(2026, 5, 15)]
    assert cleaned["close"].tolist() == [106.0, 110.0]
    assert cleaned["volume"].tolist() == [1200.0, 1300.0]


def test_clean_daily_candle_frame_drops_repeated_placeholder_run():
    cfg = DailyCandleQualityConfig(repeated_ohlcv_run_min=3)
    rows = []
    for day in range(1, 5):
        rows.append(["005930", date(2026, 1, day), 50000, 51000, 49000, 50500, 1_000_000])
    rows.extend(
        [
            ["005930", date(2026, 1, 5), 51000, 51500, 50500, 51200, 900000],
            ["005930", date(2026, 1, 6), 51200, 52000, 51000, 51800, 950000],
        ]
    )
    df = pd.DataFrame(
        rows,
        columns=["code", "date", "open", "high", "low", "close", "volume"],
    )

    cleaned = clean_daily_candle_frame(df, config=cfg)

    assert cleaned["date"].tolist() == [date(2026, 1, 5), date(2026, 1, 6)]


def test_clean_daily_candle_frame_applies_tail_limit_after_filtering():
    cfg = DailyCandleQualityConfig(repeated_ohlcv_run_min=3)
    df = pd.DataFrame(
        [
            ["005930", date(2026, 1, 1), 100, 101, 99, 100, 1000],
            ["005930", date(2026, 1, 2), 101, 102, 100, 101, 1000],
            ["005930", date(2026, 1, 3), 102, 103, 101, 102, 1000],
        ],
        columns=["code", "date", "open", "high", "low", "close", "volume"],
    )

    cleaned = clean_daily_candle_frame(df, config=cfg, limit=2)

    assert cleaned["date"].tolist() == [date(2026, 1, 2), date(2026, 1, 3)]


def test_quality_fetch_limit_uses_configured_multiplier():
    cfg = DailyCandleQualityConfig(fetch_multiplier=4)

    assert quality_fetch_limit(250, cfg) == 1000
