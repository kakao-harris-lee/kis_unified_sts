from datetime import date

import pandas as pd

from scripts.daily_indicator_scanner import (
    is_fresh_daily_data,
    latest_candle_date,
)
from shared.collector.historical.calendar import trading_day_lag


def test_latest_candle_date_returns_max_date():
    df = pd.DataFrame({"date": [date(2026, 5, 14), date(2026, 5, 15)]})

    assert latest_candle_date(df) == date(2026, 5, 15)


def test_daily_indicator_freshness_allows_weekend_gap():
    df = pd.DataFrame({"date": [date(2026, 5, 15)]})

    assert is_fresh_daily_data(
        df,
        expected_latest=date(2026, 5, 15),
        max_stale_trading_days=0,
    )


def test_daily_indicator_freshness_rejects_old_trading_day():
    df = pd.DataFrame({"date": [date(2026, 5, 13)]})

    assert not is_fresh_daily_data(
        df,
        expected_latest=date(2026, 5, 15),
        max_stale_trading_days=1,
    )


def test_trading_day_lag_skips_weekends():
    assert trading_day_lag(date(2026, 5, 15), date(2026, 5, 18)) == 1
