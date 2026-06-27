"""Tests for the futures-minute OHLC corruption scanner."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from scripts.analysis.scan_futures_minute_ohlc_corruption import scan_store
from shared.storage.market_data_store import ParquetMarketDataStore


def _bar(dt: datetime, o: float, h: float, low: float, c: float, v: int = 500) -> dict:
    return {
        "code": "A01603",
        "datetime": dt,
        "open": o,
        "high": h,
        "low": low,
        "close": c,
        "volume": v,
    }


def _clean_day(day: date) -> list[dict]:
    """A consistent day with small wicks (~0.1%)."""
    rows = []
    base = datetime(day.year, day.month, day.day, 9, 0)
    price = 400.0
    for i in range(60):
        dt = base + timedelta(minutes=i)
        rows.append(_bar(dt, price, price + 0.4, price - 0.4, price + 0.1))
        price += 0.1
    return rows


def _phantom_day(day: date) -> list[dict]:
    """A day with a sustained ~2% phantom upper-wick cluster (corruption)."""
    rows = []
    base = datetime(day.year, day.month, day.day, 9, 0)
    price = 400.0
    for i in range(60):
        dt = base + timedelta(minutes=i)
        # 20 bars carry a phantom high ~2% above the body — the divergence wick.
        high = price * 1.02 if 20 <= i < 40 else price + 0.4
        rows.append(_bar(dt, price, high, price - 0.4, price + 0.1))
        price += 0.1
    return rows


def test_scan_flags_phantom_day_not_clean_day(tmp_path):
    store = ParquetMarketDataStore(tmp_path / "market", asset_class="futures")
    clean = date(2026, 3, 2)
    corrupt = date(2026, 3, 4)
    store.replace_minute_day("A01603", clean, _clean_day(clean))
    store.replace_minute_day("A01603", corrupt, _phantom_day(corrupt))

    reports = scan_store(
        root=str(tmp_path / "market"),
        codes=["A01603"],
        wick_pct=1.0,
        min_cluster=8,
    )

    flagged_dates = {r.trade_date for r in reports}
    assert corrupt in flagged_dates, "phantom-wick day must be flagged"
    assert clean not in flagged_dates, "clean day must not be flagged"
    rep = next(r for r in reports if r.trade_date == corrupt)
    assert rep.big_wick_bars >= 8
    assert rep.median_big_wick_pct >= 1.0


def test_scan_reports_ohlc_violation(tmp_path):
    """A literal OHLC ordering violation is always flagged, regardless of cluster."""
    store = ParquetMarketDataStore(tmp_path / "market", asset_class="futures")
    day = date(2026, 3, 4)
    base = datetime(2026, 3, 4, 9, 0)
    rows = [_bar(base, 400.0, 401.0, 399.0, 400.5)]
    # One bar with high below the close (ordering violation).
    rows.append(_bar(base + timedelta(minutes=1), 400.5, 401.0, 400.0, 450.0))
    store.replace_minute_day("A01603", day, rows)

    reports = scan_store(root=str(tmp_path / "market"), codes=["A01603"])
    assert any(r.trade_date == day and r.ohlc_violations >= 1 for r in reports)
