from datetime import date

import pandas as pd

from scripts.daily_indicator_scanner import (
    compute_indicators,
    get_clickhouse_client,
    is_fresh_daily_data,
    latest_candle_date,
    load_daily_candles,
)
import scripts.daily_indicator_scanner as scanner
from shared.collector.historical.calendar import trading_day_lag
from shared.collector.historical.daily_quality import DailyCandleQualityConfig


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


def test_compute_indicators_includes_daily_volume_ratio():
    rows = []
    for i in range(220):
        rows.append(
            {
                "date": date(2026, 1, 1),
                "open": 100.0 + i,
                "high": 102.0 + i,
                "low": 99.0 + i,
                "close": 101.0 + i,
                "volume": 1_000_000 if i < 219 else 2_000_000,
            }
        )
    df = pd.DataFrame(rows)

    indicators = compute_indicators(df, volume_lookback=20)

    assert indicators is not None
    assert "daily_volume_ratio" in indicators
    assert indicators["daily_volume_ratio"] == 2.0


def test_get_clickhouse_client_loads_repo_env(tmp_path, monkeypatch):
    calls = {}

    def fake_load_dotenv(path, override=False):
        calls["dotenv"] = (path, override)

    def fake_get_client(**kwargs):
        calls["client"] = kwargs
        return object()

    monkeypatch.setattr(scanner, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(scanner, "load_dotenv", fake_load_dotenv)
    monkeypatch.setenv("CLICKHOUSE_USER", "u")
    monkeypatch.setenv("CLICKHOUSE_PASSWORD", "p")
    monkeypatch.setattr("clickhouse_connect.get_client", fake_get_client)

    get_clickhouse_client()

    assert calls["dotenv"] == (tmp_path / ".env", False)
    assert calls["client"]["username"] == "u"
    assert calls["client"]["password"] == "p"


def test_load_daily_candles_fetches_extra_and_filters_placeholder_run():
    class Result:
        result_rows = [
            ("005930", date(2026, 1, 1), 50500, 50500, 50500, 50500, 1_000_000),
            ("005930", date(2026, 1, 2), 50500, 50500, 50500, 50500, 1_000_000),
            ("005930", date(2026, 1, 3), 50500, 50500, 50500, 50500, 1_000_000),
            ("005930", date(2026, 1, 4), 100, 105, 95, 102, 900_000),
            ("005930", date(2026, 1, 5), 102, 108, 101, 107, 950_000),
        ]

    class Client:
        def __init__(self):
            self.parameters = None

        def query(self, _query, parameters):
            self.parameters = parameters
            return Result()

    client = Client()
    cfg = DailyCandleQualityConfig(fetch_multiplier=3, repeated_ohlcv_run_min=3)

    df = load_daily_candles(client, "005930", days=2, quality_config=cfg)

    assert client.parameters == {"code": "005930", "limit": 6}
    assert df["date"].tolist() == [date(2026, 1, 4), date(2026, 1, 5)]
