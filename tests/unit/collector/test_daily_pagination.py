"""Tests for paginating stock DAILY Parquet backfill (SMA(200) depth).

The KIS daily-chart API returns at most ~100 bars per call. ``collect_stock_daily_parquet``
must page the window backward so a deep ``days`` request fills > 100 daily bars.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta


def _make_daily_rows(end: date, count: int) -> list[dict]:
    """KIS-style output2 rows: ``count`` consecutive calendar days ending at ``end``."""
    rows = []
    for i in range(count):
        d = end - timedelta(days=i)
        rows.append(
            {
                "stck_bsop_date": d.strftime("%Y%m%d"),
                "stck_oprc": "1000",
                "stck_hgpr": "1010",
                "stck_lwpr": "990",
                "stck_clpr": "1005",
                "acml_vol": "1000",
                "acml_tr_pbmn": "1005000",
                "prdy_ctrt": "0.5",
            }
        )
    return rows


def test_daily_backfill_paginates_beyond_single_page(monkeypatch, tmp_path):
    """A deep request must page backward and exceed the ~100-bar single-call cap."""
    from shared.collector.historical import daily_stock as daily_module
    from shared.collector.historical.parquet_backfill import (
        DAILY_PAGE_MAX_ROWS,
        collect_stock_daily_parquet,
    )
    from shared.storage import ParquetMarketDataStore

    calls: list[tuple[date, date]] = []

    async def fake_fetch(_client, code, start_date, end_date):
        calls.append((start_date, end_date))
        # Emulate KIS: return at most DAILY_PAGE_MAX_ROWS bars ending at end_date,
        # but never older than start_date.
        page = _make_daily_rows(end_date, DAILY_PAGE_MAX_ROWS)
        page = [
            r
            for r in page
            if datetime.strptime(r["stck_bsop_date"], "%Y%m%d").date() >= start_date
        ]
        return code, {"rt_cd": "0", "output2": page}

    monkeypatch.setattr(daily_module, "fetch_daily_candles_async", fake_fetch)

    result = asyncio.run(
        collect_stock_daily_parquet(
            root=tmp_path / "market",
            codes=["005930"],
            days=400,
            resume=True,
            verbose=False,
        )
    )

    assert len(calls) >= 2, "deep request must issue more than one page"
    # Each successive page must walk strictly backward.
    for prev, cur in zip(calls, calls[1:]):
        assert cur[1] < prev[1], "page end-date must move backward"

    store = ParquetMarketDataStore(tmp_path / "market", asset_class="stock")
    df = store.get_daily_bars("005930", limit=0)
    assert len(df) > DAILY_PAGE_MAX_ROWS, "must exceed single-page cap"
    assert len(df) >= 200, "must reach SMA(200) depth"
    assert result.rows >= 200


def test_daily_backfill_stops_when_history_exhausted(monkeypatch, tmp_path):
    """A recent listing (short first page) must stop paging, not loop."""
    from shared.collector.historical import daily_stock as daily_module
    from shared.collector.historical.parquet_backfill import collect_stock_daily_parquet
    from shared.storage import ParquetMarketDataStore

    call_count = {"n": 0}

    async def fake_fetch(_client, code, start_date, end_date):
        call_count["n"] += 1
        # Only 40 bars exist (recent listing): a single short page.
        page = _make_daily_rows(end_date, 40)
        page = [
            r
            for r in page
            if datetime.strptime(r["stck_bsop_date"], "%Y%m%d").date() >= start_date
        ]
        return code, {"rt_cd": "0", "output2": page}

    monkeypatch.setattr(daily_module, "fetch_daily_candles_async", fake_fetch)

    result = asyncio.run(
        collect_stock_daily_parquet(
            root=tmp_path / "market",
            codes=["999999"],
            days=400,
            resume=True,
            verbose=False,
        )
    )

    assert call_count["n"] == 1, "short page must stop pagination (no infinite loop)"
    store = ParquetMarketDataStore(tmp_path / "market", asset_class="stock")
    df = store.get_daily_bars("999999", limit=0)
    assert len(df) == 40
    assert result.failed == 0, "writing a valid short page is not a failure"


def test_daily_backfill_resume_skips_completed_days(monkeypatch, tmp_path):
    """A second run with resume=True must not re-write already-stored days."""
    from shared.collector.historical import daily_stock as daily_module
    from shared.collector.historical.parquet_backfill import collect_stock_daily_parquet

    async def fake_fetch(_client, code, start_date, end_date):
        page = _make_daily_rows(end_date, 100)
        page = [
            r
            for r in page
            if datetime.strptime(r["stck_bsop_date"], "%Y%m%d").date() >= start_date
        ]
        return code, {"rt_cd": "0", "output2": page}

    monkeypatch.setattr(daily_module, "fetch_daily_candles_async", fake_fetch)

    first = asyncio.run(
        collect_stock_daily_parquet(
            root=tmp_path / "market",
            codes=["005930"],
            days=300,
            resume=True,
            verbose=False,
        )
    )
    assert first.rows > 0

    second = asyncio.run(
        collect_stock_daily_parquet(
            root=tmp_path / "market",
            codes=["005930"],
            days=300,
            resume=True,
            verbose=False,
        )
    )
    assert second.rows == 0, "resume must skip already-completed days"
    assert second.skipped > 0
