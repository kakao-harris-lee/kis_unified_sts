"""Tests for Parquet-first historical backfill."""

from __future__ import annotations

import asyncio
import importlib
from datetime import date
from unittest.mock import patch


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

    # Disable the completeness gate: test focuses on write/resume state-machine
    # mechanics, not bar-count completeness.  A 1-bar payload would otherwise
    # trigger the gate and mark the day failed.
    with patch(
        "shared.collector.historical.parquet_backfill._is_day_closed",
        return_value=False,
    ):
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
        df = store.get_minute_bars(
            "A05603", start=date(2026, 6, 3), end=date(2026, 6, 3)
        )
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


# ---------------------------------------------------------------------------
# Task 3: Completeness gate — short days must not be marked success
# ---------------------------------------------------------------------------


def _make_row_payload(n: int, date_str: str) -> dict:
    """Return a KIS-style payload with exactly n minute bars for date_str."""
    return {
        "rt_cd": "0",
        "output2": [
            {
                "stck_cntg_hour": f"{9 + i // 60:02d}{i % 60:02d}00",
                "futs_oprc": "380.0",
                "futs_hgpr": "381.0",
                "futs_lwpr": "379.5",
                "futs_prpr": "380.5",
                "cntg_vol": "100",
            }
            for i in range(n)
        ],
    }


def test_completeness_gate_short_day_marked_failed(monkeypatch, tmp_path):
    """A closed full day with only 102 rows must be marked failed (not success).

    A failed state means is_completed() == False, so a resume run will
    re-attempt the day rather than skipping it forever.
    """
    from shared.collector.historical import futures as futures_module
    from shared.collector.historical.parquet_backfill import (
        MINUTE_COMPLETENESS_MIN_ROWS,
        ParquetBackfillState,
        backfill_futures_parquet,
    )

    legacy_backfill = importlib.import_module("shared.collector.historical.backfill")

    # 102 rows — well below the expected full-day threshold
    short_payload = _make_row_payload(102, "20260603")

    async def fake_fetch(_client, code, date_str):
        return code, date_str, short_payload

    monkeypatch.setattr(
        futures_module, "get_active_codes_for_date", lambda _day: ["A05603"]
    )
    monkeypatch.setattr(legacy_backfill, "fetch_minute_async", fake_fetch)

    trade_date = date(2026, 6, 3)  # a known past trading day (definitely closed)

    # Patch _is_day_closed so the gate always sees this as a closed day
    with patch(
        "shared.collector.historical.parquet_backfill._is_day_closed",
        return_value=True,
    ):
        result = asyncio.run(
            backfill_futures_parquet(
                root=tmp_path / "market",
                mini=True,
                index=False,
                futures=False,
                resume=True,
                verbose=False,
                trading_days=[trade_date],
            )
        )

    # 102 < MINUTE_COMPLETENESS_MIN_ROWS → should be counted as failed
    assert (
        result.failed == 1
    ), f"Expected 1 failed (102 rows < {MINUTE_COMPLETENESS_MIN_ROWS}), got {result.failed}"
    assert result.rows == 0 or result.rows == 102  # rows may be written to parquet

    state = ParquetBackfillState(
        tmp_path / "market" / "_metadata" / "backfill_state.sqlite3"
    )
    completed = state.is_completed(
        asset_class="futures",
        timeframe="minute",
        dataset="kospi_mini_1m",
        code="A05603",
        trade_date=trade_date,
    )
    assert not completed, "Short day must NOT be marked success (resume would lock it)"

    # A second run with resume=True must NOT skip this day (it should retry it)
    retry_calls = []

    async def counting_fetch(_client, code, date_str):
        retry_calls.append((code, date_str))
        return code, date_str, short_payload

    monkeypatch.setattr(legacy_backfill, "fetch_minute_async", counting_fetch)

    with patch(
        "shared.collector.historical.parquet_backfill._is_day_closed",
        return_value=True,
    ):
        asyncio.run(
            backfill_futures_parquet(
                root=tmp_path / "market",
                mini=True,
                index=False,
                futures=False,
                resume=True,
                verbose=False,
                trading_days=[trade_date],
            )
        )

    assert (
        len(retry_calls) == 1
    ), "Resume should retry a failed (short) day, but fetch was not called"


def test_completeness_gate_full_day_marked_success(monkeypatch, tmp_path):
    """A closed full day with >= expected rows must still be marked success."""
    from shared.collector.historical import futures as futures_module
    from shared.collector.historical.parquet_backfill import (
        MINUTE_COMPLETENESS_MIN_ROWS,
        ParquetBackfillState,
        backfill_futures_parquet,
    )

    legacy_backfill = importlib.import_module("shared.collector.historical.backfill")

    # Use exactly MINUTE_COMPLETENESS_MIN_ROWS so the test is threshold-relative
    full_payload = _make_row_payload(MINUTE_COMPLETENESS_MIN_ROWS, "20260603")

    async def fake_fetch(_client, code, date_str):
        return code, date_str, full_payload

    monkeypatch.setattr(
        futures_module, "get_active_codes_for_date", lambda _day: ["A05603"]
    )
    monkeypatch.setattr(legacy_backfill, "fetch_minute_async", fake_fetch)

    trade_date = date(2026, 6, 3)

    with patch(
        "shared.collector.historical.parquet_backfill._is_day_closed",
        return_value=True,
    ):
        result = asyncio.run(
            backfill_futures_parquet(
                root=tmp_path / "market",
                mini=True,
                index=False,
                futures=False,
                resume=True,
                verbose=False,
                trading_days=[trade_date],
            )
        )

    assert result.failed == 0, f"Full day should not be failed, got {result.failed}"

    state = ParquetBackfillState(
        tmp_path / "market" / "_metadata" / "backfill_state.sqlite3"
    )
    assert state.is_completed(
        asset_class="futures",
        timeframe="minute",
        dataset="kospi_mini_1m",
        code="A05603",
        trade_date=trade_date,
    ), "Full day must be marked success"


def test_completeness_gate_skips_inprogress_day(monkeypatch, tmp_path):
    """A day that is NOT yet after market close must not be failed even with few rows.

    This prevents false-failing a still-in-progress current day.
    """
    from shared.collector.historical import futures as futures_module
    from shared.collector.historical.parquet_backfill import (
        ParquetBackfillState,
        backfill_futures_parquet,
    )

    legacy_backfill = importlib.import_module("shared.collector.historical.backfill")

    # Only 102 bars — would normally trigger the gate
    short_payload = _make_row_payload(102, "20260603")

    async def fake_fetch(_client, code, date_str):
        return code, date_str, short_payload

    monkeypatch.setattr(
        futures_module, "get_active_codes_for_date", lambda _day: ["A05603"]
    )
    monkeypatch.setattr(legacy_backfill, "fetch_minute_async", fake_fetch)

    trade_date = date(2026, 6, 3)

    # Market is still open AND day is today (in-progress) → gate must not fire
    with patch(
        "shared.collector.historical.parquet_backfill._is_day_closed",
        return_value=False,
    ):
        result = asyncio.run(
            backfill_futures_parquet(
                root=tmp_path / "market",
                mini=True,
                index=False,
                futures=False,
                resume=True,
                verbose=False,
                trading_days=[trade_date],
            )
        )

    # Should succeed (or at least not fail due to the completeness gate)
    assert (
        result.failed == 0
    ), "An in-progress day with 102 rows must not be failed by the completeness gate"

    state = ParquetBackfillState(
        tmp_path / "market" / "_metadata" / "backfill_state.sqlite3"
    )
    assert state.is_completed(
        asset_class="futures",
        timeframe="minute",
        dataset="kospi_mini_1m",
        code="A05603",
        trade_date=trade_date,
    ), "In-progress day with rows written should still be marked success"


def test_completeness_gate_past_day_with_market_open(monkeypatch, tmp_path):
    """A PAST day with < threshold rows must be marked failed even if market is open.

    The gate is day-aware: a day is closed if it is strictly before today (KST),
    regardless of whether the market is currently open. This prevents a daytime
    manual backfill run from incorrectly allowing short past days.
    """
    from shared.collector.historical import futures as futures_module
    from shared.collector.historical.parquet_backfill import (
        MINUTE_COMPLETENESS_MIN_ROWS,
        ParquetBackfillState,
        backfill_futures_parquet,
    )

    legacy_backfill = importlib.import_module("shared.collector.historical.backfill")

    # Only 102 bars — below the expected threshold
    short_payload = _make_row_payload(102, "20260602")

    async def fake_fetch(_client, code, date_str):
        return code, date_str, short_payload

    monkeypatch.setattr(
        futures_module, "get_active_codes_for_date", lambda _day: ["A05603"]
    )
    monkeypatch.setattr(legacy_backfill, "fetch_minute_async", fake_fetch)

    # Use a date strictly before today (e.g., 2026-06-02, when running on 2026-06-03+)
    trade_date = date(2026, 6, 2)

    # _is_day_closed returns True for a past day, even though we could also test
    # the composition (day < today OR day==today and is_after_market_close()).
    # Here we directly test that a past day with short bars is marked failed.
    with patch(
        "shared.collector.historical.parquet_backfill._is_day_closed",
        return_value=True,
    ):
        result = asyncio.run(
            backfill_futures_parquet(
                root=tmp_path / "market",
                mini=True,
                index=False,
                futures=False,
                resume=True,
                verbose=False,
                trading_days=[trade_date],
            )
        )

    # 102 < MINUTE_COMPLETENESS_MIN_ROWS → should be counted as failed
    assert (
        result.failed == 1
    ), f"Past day with 102 rows must be marked failed even if market open. Got {result.failed}"

    state = ParquetBackfillState(
        tmp_path / "market" / "_metadata" / "backfill_state.sqlite3"
    )
    completed = state.is_completed(
        asset_class="futures",
        timeframe="minute",
        dataset="kospi_mini_1m",
        code="A05603",
        trade_date=trade_date,
    )
    assert not completed, "Past short day must NOT be marked success"


def test_completeness_gate_no_half_day_support_documented(monkeypatch, tmp_path):
    """Documents that calendar.py has no half-day/early-close signal.

    The conservative threshold (MINUTE_COMPLETENESS_MIN_ROWS < actual session bars)
    acts as the safety margin.  Any truly short legitimate session would need a
    half-day calendar to exempt — this test records that limitation.
    """
    from shared.collector.historical.calendar import MARKET_CLOSE, MARKET_OPEN
    from shared.collector.historical.parquet_backfill import (
        MINUTE_COMPLETENESS_MIN_ROWS,
        MINUTE_SESSION_BARS,
    )

    # Verify the session bar count is derived from the actual market hours
    open_h, open_m = int(MARKET_OPEN.split(":")[0]), int(MARKET_OPEN.split(":")[1])
    close_h, close_m = int(MARKET_CLOSE.split(":")[0]), int(MARKET_CLOSE.split(":")[1])
    expected_session = (close_h * 60 + close_m) - (open_h * 60 + open_m)
    assert expected_session == MINUTE_SESSION_BARS, (
        f"MINUTE_SESSION_BARS ({MINUTE_SESSION_BARS}) should match "
        f"market hours {MARKET_OPEN}-{MARKET_CLOSE} ({expected_session} bars)"
    )

    # The min-rows threshold must be strictly less than the full session to
    # provide a tolerance margin (no half-day calendar support)
    assert (
        MINUTE_COMPLETENESS_MIN_ROWS < MINUTE_SESSION_BARS
    ), "MINUTE_COMPLETENESS_MIN_ROWS must be < MINUTE_SESSION_BARS (tolerance margin)"
    # Must also be > 102 (the per-call KIS max) so partial first-page fetches fail
    assert (
        MINUTE_COMPLETENESS_MIN_ROWS > 102
    ), "MINUTE_COMPLETENESS_MIN_ROWS must be > 102 (KIS single-page cap)"
