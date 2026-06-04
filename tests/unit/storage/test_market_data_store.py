"""Market-data store tests."""

from datetime import date, datetime

import pandas as pd
import pytest


def test_parquet_market_data_store_appends_and_queries_minute_bars(tmp_path):
    from shared.storage import ParquetMarketDataStore

    store = ParquetMarketDataStore(tmp_path / "market", asset_class="stock")
    written = store.append_minute_bars(
        [
            {
                "code": "005930",
                "datetime": datetime(2026, 6, 3, 9, 1),
                "open": 71000,
                "high": 71100,
                "low": 70900,
                "close": 71050,
                "volume": 1000,
            },
            {
                "code": "005930",
                "datetime": datetime(2026, 6, 3, 9, 2),
                "open": 71050,
                "high": 71200,
                "low": 71000,
                "close": 71180,
                "volume": 900,
            },
            {
                "code": "000660",
                "datetime": datetime(2026, 6, 3, 9, 1),
                "open": 120000,
                "high": 121000,
                "low": 119500,
                "close": 120500,
                "volume": 500,
            },
        ]
    )

    assert written == 3

    df = store.get_minute_bars(
        "005930",
        start=date(2026, 6, 3),
        end=date(2026, 6, 3),
    )

    assert list(df["code"]) == ["005930", "005930"]
    assert list(df["close"]) == [71050, 71180]
    assert df["datetime"].is_monotonic_increasing


def test_parquet_market_data_store_supports_daily_bars_and_limit(tmp_path):
    from shared.storage import ParquetMarketDataStore

    store = ParquetMarketDataStore(tmp_path / "market", asset_class="stock")
    written = store.append_daily_bars(
        pd.DataFrame(
            {
                "code": ["005930", "005930"],
                "date": [date(2026, 6, 2), date(2026, 6, 3)],
                "open": [70000, 71000],
                "high": [71000, 72000],
                "low": [69000, 70500],
                "close": [70800, 71800],
                "volume": [10000, 12000],
            }
        )
    )

    assert written == 2

    df = store.get_daily_bars("005930", limit=1)

    assert len(df) == 1
    assert df.iloc[0]["close"] == 70800


def test_parquet_market_data_store_manifest_without_manifest_file(tmp_path):
    from shared.storage import ParquetMarketDataStore

    store = ParquetMarketDataStore(tmp_path / "market", asset_class="futures")
    store.append_minute_bars(
        [
            {
                "code": "101S6000",
                "datetime": "2026-06-03T09:00:00",
                "open": 380.0,
                "high": 381.0,
                "low": 379.5,
                "close": 380.5,
                "volume": 100,
            }
        ]
    )

    manifest = store.dataset_manifest()

    assert manifest["parquet_files"] == 1
    assert manifest["row_count"] == 1
    assert manifest["min_datetime"].startswith("2026-06-03")


def test_parquet_market_data_store_rejects_missing_columns(tmp_path):
    from shared.storage import MarketDataStoreError, ParquetMarketDataStore

    store = ParquetMarketDataStore(tmp_path / "market", asset_class="stock")

    with pytest.raises(MarketDataStoreError, match="missing required columns"):
        store.append_minute_bars([{"code": "005930", "close": 71000}])


def test_load_market_bars_for_backtest_uses_storage_config(tmp_path):
    from shared.storage import (
        MarketDataStorageConfig,
        ParquetMarketDataConfig,
        StorageConfig,
        load_market_bars_for_backtest,
    )

    root = tmp_path / "market"
    config = StorageConfig(
        market_data=MarketDataStorageConfig(
            source="parquet",
            parquet=ParquetMarketDataConfig(root=str(root)),
        )
    )

    from shared.storage import ParquetMarketDataStore

    ParquetMarketDataStore(root, asset_class="futures").append_minute_bars(
        [
            {
                "code": "101S6000",
                "datetime": "2026-06-03T09:00:00",
                "open": 380.0,
                "high": 381.0,
                "low": 379.5,
                "close": 380.5,
                "volume": 100,
            }
        ]
    )

    df = load_market_bars_for_backtest(
        symbol="101S6000",
        asset_class="futures",
        config=config,
    )

    assert len(df) == 1
    assert df.iloc[0]["code"] == "101S6000"


def test_clickhouse_market_data_store_uses_configured_futures_database(monkeypatch):
    from shared.storage import ClickHouseMarketDataStore

    captured: dict[str, object] = {}

    class FakeClient:
        def __init__(self, database: str):
            captured["database"] = database

        def execute(self, query, params):
            captured["query"] = query
            captured["params"] = params
            return [
                (
                    "101S6000",
                    datetime(2026, 6, 3, 9, 0),
                    380.0,
                    381.0,
                    379.5,
                    380.5,
                    100,
                )
            ]

        def disconnect(self):
            captured["disconnected"] = True

    monkeypatch.setattr(
        "shared.storage.market_data_store.create_sync_clickhouse_client",
        lambda database: FakeClient(database),
    )

    store = ClickHouseMarketDataStore(
        asset_class="futures",
        futures_database="custom_kospi",
        futures_table="custom_1m",
    )
    df = store.get_minute_bars(
        "101S6000",
        start=date(2026, 6, 3),
        end=date(2026, 6, 3),
    )

    assert captured["database"] == "custom_kospi"
    assert "FROM custom_kospi.custom_1m" in str(captured["query"])
    assert captured["params"]["code"] == "101S6000"
    assert captured["disconnected"] is True
    assert len(df) == 1
    assert df.iloc[0]["code"] == "101S6000"


def test_clickhouse_market_data_store_daily_uses_configured_stock_database(
    monkeypatch,
):
    from shared.storage import ClickHouseMarketDataStore

    captured: dict[str, object] = {}

    class FakeClient:
        def __init__(self, database: str):
            captured["database"] = database

        def execute(self, query, params):
            captured["query"] = query
            captured["params"] = params
            return [
                (
                    "005930",
                    date(2026, 6, 3),
                    71000.0,
                    71100.0,
                    70900.0,
                    71050.0,
                    1000,
                )
            ]

        def disconnect(self):
            captured["disconnected"] = True

    monkeypatch.setattr(
        "shared.storage.market_data_store.create_sync_clickhouse_client",
        lambda database: FakeClient(database),
    )

    store = ClickHouseMarketDataStore(asset_class="stock", stock_database="stockdb")
    df = store.get_daily_bars("005930", start=date(2026, 6, 3))

    assert captured["database"] == "stockdb"
    assert "FROM stockdb.daily_candles" in str(captured["query"])
    assert captured["params"]["code"] == "005930"
    assert captured["disconnected"] is True
    assert len(df) == 1
    assert df.iloc[0]["code"] == "005930"
