"""Tests for Parquet-first historical backfill."""

from __future__ import annotations

import asyncio
import importlib
from datetime import date


def _futures_payload() -> dict:
    return {
        "rt_cd": "0",
        "output2": [
            {
                "stck_cntg_hour": "090000",
                "futs_oprc": "380.0",
                "futs_hgpr": "381.0",
                "futs_lwpr": "379.5",
                "futs_prpr": "380.5",
                "cntg_vol": "100",
            }
        ],
    }


def test_futures_parquet_backfill_writes_and_resumes(monkeypatch, tmp_path):
    from shared.collector.historical import futures as futures_module
    from shared.collector.historical.parquet_backfill import backfill_futures_parquet
    from shared.storage import ParquetMarketDataStore

    legacy_backfill = importlib.import_module("shared.collector.historical.backfill")

    async def fake_fetch(_client, code, date_str):
        return code, date_str, _futures_payload()

    monkeypatch.setattr(
        futures_module, "get_active_codes_for_date", lambda _day: ["A05603"]
    )
    monkeypatch.setattr(legacy_backfill, "fetch_minute_async", fake_fetch)

    result = asyncio.run(
        backfill_futures_parquet(
            root=tmp_path / "market",
            mini=True,
            index=False,
            futures=False,
            resume=True,
            verbose=False,
            trading_days=[date(2026, 6, 3)],
        )
    )

    assert result.tasks == 1
    assert result.rows == 1
    assert result.failed == 0

    store = ParquetMarketDataStore(tmp_path / "market", asset_class="futures")
    df = store.get_minute_bars("A05603", start=date(2026, 6, 3), end=date(2026, 6, 3))
    assert len(df) == 1
    assert df.iloc[0]["close"] == 380.5

    resumed = asyncio.run(
        backfill_futures_parquet(
            root=tmp_path / "market",
            mini=True,
            index=False,
            futures=False,
            resume=True,
            verbose=False,
            trading_days=[date(2026, 6, 3)],
        )
    )

    assert resumed.tasks == 1
    assert resumed.skipped == 1
    assert resumed.rows == 0


def test_stock_minute_parquet_backfill_uses_ohlcv_subset(monkeypatch, tmp_path):
    from shared.collector.historical import stock as stock_module
    from shared.collector.historical.parquet_backfill import (
        backfill_stock_minute_parquet,
    )
    from shared.storage import ParquetMarketDataStore

    async def fake_fetch(_client, code, date_str):
        return (
            code,
            date_str,
            {
                "rt_cd": "0",
                "output2": [
                    {
                        "stck_bsop_date": date_str,
                        "stck_cntg_hour": "090000",
                        "stck_oprc": "71000",
                        "stck_hgpr": "71100",
                        "stck_lwpr": "70900",
                        "stck_prpr": "71050",
                        "cntg_vol": "1000",
                        "acml_tr_pbmn": "71050000",
                    }
                ],
            },
        )

    monkeypatch.setattr(stock_module, "STOCK_UNIVERSE", [{"code": "005930"}])
    monkeypatch.setattr(stock_module, "fetch_stock_minute_async", fake_fetch)

    result = asyncio.run(
        backfill_stock_minute_parquet(
            root=tmp_path / "market",
            codes=["005930"],
            resume=True,
            verbose=False,
            trading_days=[date(2026, 6, 3)],
        )
    )

    assert result.rows == 1
    store = ParquetMarketDataStore(tmp_path / "market", asset_class="stock")
    df = store.get_minute_bars("005930", start=date(2026, 6, 3), end=date(2026, 6, 3))
    assert len(df) == 1
    assert list(df.columns) == [
        "code",
        "datetime",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]
