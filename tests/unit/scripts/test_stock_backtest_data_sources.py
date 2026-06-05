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


def test_trend_pullback_parquet_loader_uses_market_data_store(monkeypatch):
    calls = []

    def fake_loader(**kwargs):
        calls.append(kwargs)
        return _minute_df()

    monkeypatch.setattr(trend_script, "load_market_bars_for_backtest", fake_loader)

    df = trend_script.load_parquet_data(
        "005930",
        datetime(2026, 5, 15, 9, 30),
        datetime(2026, 5, 15, 15, 30),
    )

    assert calls[0]["symbol"] == "005930"
    assert calls[0]["asset_class"] == "stock"
    assert calls[0]["timeframe"] == "minute"
    assert calls[0]["start"] == datetime(2026, 5, 15).date()
    assert calls[0]["end"] == datetime(2026, 5, 15).date()
    assert df["datetime"].tolist() == [
        pd.Timestamp("2026-05-15 10:00:00"),
        pd.Timestamp("2026-05-15 15:00:00"),
    ]


def test_momentum_breakout_parquet_loader_uses_market_data_store(monkeypatch):
    calls = []

    def fake_loader(**kwargs):
        calls.append(kwargs)
        return _minute_df()

    monkeypatch.setattr(momentum_script, "load_market_bars_for_backtest", fake_loader)

    df = momentum_script.load_parquet_data(
        "005930",
        datetime(2026, 5, 15, 8, 0),
        datetime(2026, 5, 15, 10, 30),
    )

    assert calls[0]["symbol"] == "005930"
    assert calls[0]["asset_class"] == "stock"
    assert calls[0]["timeframe"] == "minute"
    assert calls[0]["start"] == datetime(2026, 5, 15).date()
    assert calls[0]["end"] == datetime(2026, 5, 15).date()
    assert df["datetime"].tolist() == [
        pd.Timestamp("2026-05-15 09:00:00"),
        pd.Timestamp("2026-05-15 10:00:00"),
    ]


def test_parquet_loader_filters_timezone_aware_timestamps(monkeypatch):
    aware_df = _minute_df()
    aware_df["datetime"] = aware_df["datetime"].dt.tz_localize("Asia/Seoul")

    monkeypatch.setattr(
        trend_script,
        "load_market_bars_for_backtest",
        lambda **_kwargs: aware_df,
    )

    df = trend_script.load_parquet_data(
        "005930",
        datetime(2026, 5, 15, 9, 30),
        datetime(2026, 5, 15, 10, 30),
    )

    assert df["datetime"].tolist() == [
        pd.Timestamp("2026-05-15 10:00:00", tz="Asia/Seoul")
    ]


def test_parquet_loader_returns_empty_when_symbol_has_no_data(monkeypatch):
    def missing_loader(**_kwargs):
        return pd.DataFrame()

    monkeypatch.setattr(trend_script, "load_market_bars_for_backtest", missing_loader)

    df = trend_script.load_parquet_data(
        "034020",
        datetime(2026, 5, 15, 9, 0),
        datetime(2026, 5, 15, 15, 30),
    )

    assert df.empty


class _FakeParquetStore:
    def __init__(self):
        self.symbols: list[str] = []

    def get_minute_bars(self, symbol: str):
        self.symbols.append(symbol)
        first_date = datetime.now() - timedelta(days=220)
        return pd.DataFrame(
            {
                "code": [symbol, symbol],
                "datetime": [first_date, datetime.now()],
                "open": [100.0, 101.0],
                "high": [101.0, 102.0],
                "low": [99.0, 100.0],
                "close": [100.5, 101.5],
                "volume": [10_000, 11_000],
            }
        )


def test_verify_backtest_data_checks_parquet_store():
    store = _FakeParquetStore()

    results = check_data_availability(store, ["005930"], min_months=6)

    assert results["symbols_with_data"] == ["005930"]
    assert store.symbols == ["005930"]
