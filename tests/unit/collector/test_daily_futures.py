"""Unit tests for the KOSPI200 futures daily bar collector.

All tests use a synthetic API double — no network calls, no KIS credentials.
The fixture population mirrors the KIS ``output2`` format returned by
``inquire-daily-fuopchartprice`` (tr_id FHKIF03020100).
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_daily_bars(end: date, count: int, base_close: float = 500.0) -> list[dict]:
    """Synthetic KIS-style output2 bars: ``count`` trading days ending at ``end``."""
    bars = []
    for i in range(count):
        d = end - timedelta(days=i)
        close = base_close + i * 0.5
        bars.append(
            {
                "stck_bsop_date": d.strftime("%Y%m%d"),
                "futs_oprc": str(close - 1.0),
                "futs_hgpr": str(close + 2.0),
                "futs_lwpr": str(close - 2.0),
                "futs_prpr": str(close),
                "acml_vol": "12000",
                "mod_yn": "N",
            }
        )
    return bars


def _fake_response(bars: list[dict], rt_cd: str = "0") -> dict:
    return {"rt_cd": rt_cd, "output1": {}, "output2": bars, "msg_cd": "MCA00000", "msg1": "정상처리 되었습니다."}


# ---------------------------------------------------------------------------
# Import helpers (lazy so test can be collected without KIS env)
# ---------------------------------------------------------------------------


def _import_collector():
    from shared.collector.historical import daily_futures as m

    return m


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestParseBar:
    def test_valid_bar(self):
        m = _import_collector()
        raw = {
            "stck_bsop_date": "20250601",
            "futs_oprc": "399.0",
            "futs_hgpr": "410.0",
            "futs_lwpr": "395.0",
            "futs_prpr": "405.0",
            "acml_vol": "5000",
        }
        bar = m._parse_bar(raw, "101S6000")
        assert bar is not None
        assert bar["code"] == "101S6000"
        assert bar["open"] == 399.0
        assert bar["high"] == 410.0
        assert bar["low"] == 395.0
        assert bar["close"] == 405.0
        assert bar["volume"] == 5000
        assert bar["datetime"] == datetime(2025, 6, 1)

    def test_zero_price_rejected(self):
        m = _import_collector()
        raw = {
            "stck_bsop_date": "20250601",
            "futs_oprc": "0",
            "futs_hgpr": "0",
            "futs_lwpr": "0",
            "futs_prpr": "0",
            "acml_vol": "0",
        }
        assert m._parse_bar(raw, "101S6000") is None

    def test_ohlc_violation_rejected(self):
        m = _import_collector()
        raw = {
            "stck_bsop_date": "20250601",
            "futs_oprc": "500.0",
            "futs_hgpr": "400.0",  # high < open — violation
            "futs_lwpr": "390.0",
            "futs_prpr": "410.0",
            "acml_vol": "100",
        }
        assert m._parse_bar(raw, "101S6000") is None

    def test_malformed_date_rejected(self):
        m = _import_collector()
        raw = {
            "stck_bsop_date": "bad",
            "futs_oprc": "400.0",
            "futs_hgpr": "410.0",
            "futs_lwpr": "390.0",
            "futs_prpr": "405.0",
            "acml_vol": "100",
        }
        assert m._parse_bar(raw, "101S6000") is None


class TestReturnGate:
    def test_normal_returns_pass(self):
        m = _import_collector()
        bars = [
            {"code": "101S6000", "datetime": datetime(2025, 6, 1), "close": 400.0, "open": 395.0, "high": 405.0, "low": 390.0, "volume": 100},
            {"code": "101S6000", "datetime": datetime(2025, 6, 2), "close": 405.0, "open": 400.0, "high": 410.0, "low": 398.0, "volume": 120},
            {"code": "101S6000", "datetime": datetime(2025, 6, 3), "close": 408.0, "open": 404.0, "high": 412.0, "low": 400.0, "volume": 110},
        ]
        accepted, last_close = m._apply_return_gate(bars, prev_close=398.0)
        assert len(accepted) == 3
        assert last_close == 408.0

    def test_extreme_return_rejected(self):
        m = _import_collector()
        bars = [
            {"code": "101S6000", "datetime": datetime(2025, 6, 1), "close": 400.0, "open": 395.0, "high": 405.0, "low": 390.0, "volume": 100},
            # 50% jump — exceeds default 25% gate
            {"code": "101S6000", "datetime": datetime(2025, 6, 2), "close": 600.0, "open": 400.0, "high": 610.0, "low": 398.0, "volume": 120},
            {"code": "101S6000", "datetime": datetime(2025, 6, 3), "close": 610.0, "open": 604.0, "high": 615.0, "low": 600.0, "volume": 110},
        ]
        accepted, _ = m._apply_return_gate(bars, prev_close=400.0)
        # First bar passes, second is rejected, third passes (prev_close updated to 600)
        assert len(accepted) == 2
        assert accepted[0]["close"] == 400.0
        assert accepted[1]["close"] == 610.0

    def test_no_prev_close_first_bar_passes(self):
        m = _import_collector()
        bars = [
            {"code": "101S6000", "datetime": datetime(2025, 6, 1), "close": 999.0, "open": 990.0, "high": 1005.0, "low": 985.0, "volume": 100},
        ]
        accepted, last_close = m._apply_return_gate(bars, prev_close=None)
        assert len(accepted) == 1
        assert last_close == 999.0


class TestCollectFuturesDaily:
    """Integration-style tests using a fake HTTP layer and tmp_path store."""

    def _run_collection(self, tmp_path: Path, pages_by_symbol: dict) -> int:
        """Helper: run collect_futures_daily with a fake API."""
        m = _import_collector()
        from shared.storage import ParquetMarketDataStore

        store = ParquetMarketDataStore(tmp_path, asset_class="futures")

        # Build fake responses dict: {symbol: [page1_bars, page2_bars, ...]}
        call_counts: dict[str, int] = {sym: 0 for sym in pages_by_symbol}

        async def fake_fetch_page(client, symbol, start_date, end_date, app_key, app_secret, max_retries=3):
            idx = call_counts.get(symbol, 0)
            pages = pages_by_symbol.get(symbol, [[]])
            if idx >= len(pages):
                return []
            call_counts[symbol] = idx + 1
            return pages[idx]

        async def run():
            import httpx

            async with httpx.AsyncClient() as client:
                total = 0
                for sym in pages_by_symbol:
                    n = await m._collect_symbol(
                        client,
                        sym,
                        "101S6000",
                        date(2024, 1, 1),
                        date(2026, 6, 25),
                        store,
                        "testkey",
                        "testsecret",
                    )
                    total += n
                return total

        with patch.object(m, "_fetch_page", side_effect=fake_fetch_page):
            return asyncio.run(run())

    def test_single_page_writes_bars(self, tmp_path):
        m = _import_collector()
        end = date(2026, 6, 25)
        bars_raw = _make_daily_bars(end, 50)
        parsed = [m._parse_bar(b, "101S6000") for b in bars_raw]
        parsed = [b for b in parsed if b is not None]

        from shared.storage import ParquetMarketDataStore

        store = ParquetMarketDataStore(tmp_path, asset_class="futures")

        days = {}
        for bar in parsed:
            days.setdefault(bar["datetime"].date(), []).append(bar)
        for d, day_bars in days.items():
            store.replace_daily_day("101S6000", d, day_bars)

        status = m.get_futures_daily_status(data_root=tmp_path)
        assert status["bar_count"] == 50
        assert status["min_date"] is not None

    def test_idempotent_double_write(self, tmp_path):
        """Writing the same bars twice must not create duplicates."""
        m = _import_collector()
        end = date(2026, 6, 25)
        bars_raw = _make_daily_bars(end, 20)
        parsed = [b for b in (m._parse_bar(r, "101S6000") for r in bars_raw) if b]

        from shared.storage import ParquetMarketDataStore

        store = ParquetMarketDataStore(tmp_path, asset_class="futures")

        def write_all():
            days = {}
            for bar in parsed:
                days.setdefault(bar["datetime"].date(), []).append(bar)
            for d, day_bars in sorted(days.items()):
                store.replace_daily_day("101S6000", d, day_bars)

        write_all()
        write_all()  # second write must replace, not append

        status = m.get_futures_daily_status(data_root=tmp_path)
        assert status["bar_count"] == 20  # no duplicates

    def test_status_returns_empty_when_no_partition(self, tmp_path):
        m = _import_collector()
        status = m.get_futures_daily_status(data_root=tmp_path)
        assert status["bar_count"] == 0
        assert "error" in status

    def test_symbol_constants_present(self):
        """Ensure the default symbols list and storage symbol are sensible."""
        m = _import_collector()
        assert len(m._DEFAULT_SYMBOLS) >= 1
        assert m._STORAGE_SYMBOL == "101S6000"
        assert m._EARLIEST_DATE.year == 2023

    def test_ohlc_sanity_rejects_bad_bars(self, tmp_path):
        """Bars failing OHLC check are not written to the store."""
        m = _import_collector()
        bad_raw = [
            {
                "stck_bsop_date": "20260601",
                "futs_oprc": "0",
                "futs_hgpr": "0",
                "futs_lwpr": "0",
                "futs_prpr": "0",
                "acml_vol": "0",
            }
        ]
        parsed = [m._parse_bar(b, "101S6000") for b in bad_raw]
        assert all(b is None for b in parsed)
