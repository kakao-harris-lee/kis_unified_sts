import csv as _csv
import datetime as dt
import importlib.util
import pathlib

_REPO = pathlib.Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "bck", _REPO / "scripts" / "forecasting" / "build_clean_kospi200f_csv.py")
bck = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bck)


def _row(code, ts, close, vol):
    # (code, datetime, open, high, low, close, volume)
    return (code, ts, close, close, close, close, vol)


def test_select_dominant_one_day():
    # One day, two contracts; A01603 has 1000 vol, A01606 has 200 → A01603 wins
    d1 = dt.datetime(2025, 11, 17, 9, 0)
    d2 = dt.datetime(2025, 11, 17, 9, 1)
    rows = [
        _row("A01603", d1, 580.0, 600),
        _row("A01603", d2, 580.5, 400),
        _row("A01606", d1, 600.0, 100),
        _row("A01606", d2, 600.5, 100),
    ]
    out = bck.select_dominant_per_day(rows)
    # Only A01603 rows survive; A01606 rows dropped
    assert len(out) == 2
    assert all(r[0] == "A01603" for r in out)
    # Bars preserved in original order
    assert out[0][1] == d1
    assert out[1][1] == d2


def test_select_dominant_far_month_fallback():
    # Outlier-day shape: A01603 was missing; A01609 has the only data
    d1 = dt.datetime(2025, 11, 14, 9, 0)
    rows = [
        _row("A01609", d1, 506.8, 173),  # all the day's volume on far-month
    ]
    out = bck.select_dominant_per_day(rows)
    # The function does NOT discriminate quality — it picks dominant-volume.
    # Far-month wins by default if it's the only source. This is correct
    # behavior: we faithfully replicate the rebuild's policy. The
    # operator decides downstream whether the day is usable.
    assert len(out) == 1
    assert out[0][0] == "A01609"


def test_select_dominant_tie_break_deterministic():
    # Tie on volume → first contract code alphabetically wins (matches
    # _build_continuous_rows: `sorted(... key=lambda i: (-i[1], i[0]))[0][0]`).
    d1 = dt.datetime(2025, 12, 1, 9, 0)
    rows = [
        _row("A01606", d1, 600.0, 500),
        _row("A01603", d1, 580.0, 500),
    ]
    out = bck.select_dominant_per_day(rows)
    assert len(out) == 1
    assert out[0][0] == "A01603"  # alphabetic tie-break


def test_write_csv_schema(tmp_path):
    d1 = dt.datetime(2025, 11, 17, 9, 0)
    d2 = dt.datetime(2025, 11, 17, 9, 1)
    rows = [
        ("A01603", d1, 580.0, 580.5, 579.8, 580.2, 100),
        ("A01603", d2, 580.2, 580.4, 580.0, 580.3, 150),
    ]
    out = tmp_path / "clean.csv"
    n = bck.write_csv(out, rows)
    assert n == 2
    with open(out) as f:
        r = list(_csv.DictReader(f))
    assert len(r) == 2
    # Schema must match the existing kospi200f_1m_ch_101S6000.csv columns
    # (datetime, open, high, low, close, volume). NO 'code' column — keeps
    # parity with what the gate runner already consumes.
    assert set(r[0].keys()) == {"datetime", "open", "high", "low", "close", "volume"}
    assert r[0]["datetime"] == "2025-11-17 09:00:00"
    assert float(r[0]["close"]) == 580.2
    assert int(r[0]["volume"]) == 100


def test_select_dominant_with_force_keeps_only_forced_code():
    # New helper: filter_to_single_code(rows, "A01603") keeps only A01603 rows
    d1 = dt.datetime(2025, 11, 17, 9, 0)
    d2 = dt.datetime(2025, 11, 17, 9, 1)
    rows = [
        _row("A01603", d1, 580.0, 600),
        _row("A01606", d1, 600.0, 100),
        _row("A01603", d2, 580.5, 400),
        _row("A01606", d2, 600.5, 100),
    ]
    out = bck.filter_to_single_code(rows, "A01603")
    assert len(out) == 2
    assert all(r[0] == "A01603" for r in out)


def test_select_dominant_with_force_drops_non_matching_days():
    # Days that don't have the forced code at all are dropped
    d_has = dt.datetime(2025, 11, 17, 9, 0)
    d_missing = dt.datetime(2025, 11, 14, 9, 0)
    rows = [
        _row("A01603", d_has, 580.0, 600),
        _row("A01609", d_missing, 506.8, 173),  # this day has no A01603 → dropped
    ]
    out = bck.filter_to_single_code(rows, "A01603")
    assert len(out) == 1
    assert out[0][1].date() == dt.date(2025, 11, 17)


def test_filter_to_single_code_empty_returns_empty():
    assert bck.filter_to_single_code([], "A01603") == []
