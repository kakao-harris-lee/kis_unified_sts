from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

import scripts.run_momentum_breakout_backtest as momentum_script
import scripts.run_trend_pullback_backtest as trend_script
from scripts.verify_backtest_data import check_data_availability


def _minute_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "code": ["005930", "005930", "005930"],
            "datetime": pd.to_datetime(
                [
                    "2026-05-15 09:00:00",
                    "2026-05-15 10:00:00",
                    "2026-05-15 15:00:00",
                ]
            ),
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 101.5, 102.5],
            "volume": [1000, 1100, 1200],
        }
    )


def test_trend_pullback_clickhouse_loader_uses_canonical_minute_loader(monkeypatch):
    calls = []

    def fake_loader(code, start_date=None, end_date=None):
        calls.append((code, start_date, end_date))
        return _minute_df()

    monkeypatch.setattr(trend_script, "load_stock_minute_from_clickhouse", fake_loader)

    df = trend_script.load_clickhouse_data(
        "005930",
        datetime(2026, 5, 15, 9, 30),
        datetime(2026, 5, 15, 15, 30),
    )

    assert calls == [
        ("005930", datetime(2026, 5, 15).date(), datetime(2026, 5, 15).date())
    ]
    assert df["datetime"].tolist() == [
        pd.Timestamp("2026-05-15 10:00:00"),
        pd.Timestamp("2026-05-15 15:00:00"),
    ]


def test_momentum_breakout_clickhouse_loader_uses_canonical_minute_loader(monkeypatch):
    calls = []

    def fake_loader(code, start_date=None, end_date=None):
        calls.append((code, start_date, end_date))
        return _minute_df()

    monkeypatch.setattr(
        momentum_script, "load_stock_minute_from_clickhouse", fake_loader
    )

    df = momentum_script.load_clickhouse_data(
        "005930",
        datetime(2026, 5, 15, 8, 0),
        datetime(2026, 5, 15, 10, 30),
    )

    assert calls == [
        ("005930", datetime(2026, 5, 15).date(), datetime(2026, 5, 15).date())
    ]
    assert df["datetime"].tolist() == [
        pd.Timestamp("2026-05-15 09:00:00"),
        pd.Timestamp("2026-05-15 10:00:00"),
    ]


def test_clickhouse_loader_filters_timezone_aware_timestamps(monkeypatch):
    aware_df = _minute_df()
    aware_df["datetime"] = aware_df["datetime"].dt.tz_localize("Asia/Seoul")

    monkeypatch.setattr(
        trend_script,
        "load_stock_minute_from_clickhouse",
        lambda *_args, **_kwargs: aware_df,
    )

    df = trend_script.load_clickhouse_data(
        "005930",
        datetime(2026, 5, 15, 9, 30),
        datetime(2026, 5, 15, 10, 30),
    )

    assert df["datetime"].tolist() == [
        pd.Timestamp("2026-05-15 10:00:00", tz="Asia/Seoul")
    ]


def test_clickhouse_loader_returns_empty_when_symbol_has_no_data(monkeypatch):
    def missing_loader(*_args, **_kwargs):
        raise ValueError("No data found")

    monkeypatch.setattr(
        trend_script, "load_stock_minute_from_clickhouse", missing_loader
    )

    df = trend_script.load_clickhouse_data(
        "034020",
        datetime(2026, 5, 15, 9, 0),
        datetime(2026, 5, 15, 15, 30),
    )

    assert df.empty


class _FakeResult:
    def __init__(self, rows):
        self.result_rows = rows


class _FakeClickHouseClient:
    def __init__(self):
        self.queries: list[str] = []

    def query(self, query: str, parameters=None):
        self.queries.append(query)
        first_date = datetime.now() - timedelta(days=220)
        return _FakeResult([("005930", first_date, datetime.now(), 10_000, 220)])


def test_verify_backtest_data_checks_minute_candles_table(monkeypatch):
    monkeypatch.setenv("CLICKHOUSE_STOCK_DATABASE", "market")
    monkeypatch.delenv("CLICKHOUSE_STOCK_MINUTE_TABLE", raising=False)
    client = _FakeClickHouseClient()

    results = check_data_availability(client, ["005930"], min_months=6)

    assert results["symbols_with_data"] == ["005930"]
    assert any("FROM market.minute_candles" in query for query in client.queries)
    assert all("bars_1m" not in query for query in client.queries)
