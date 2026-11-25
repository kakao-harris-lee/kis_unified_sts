"""Unit tests for the deterministic replay primitives."""

from datetime import date

import pandas as pd

from shared.determinism import (
    DEFAULT_WARMUP_BARS,
    KST,
    SessionIndex,
    build_prev_session_close,
    build_session_index,
    ensure_kst,
    session_date,
)


def test_default_warmup_bars_is_60():
    assert DEFAULT_WARMUP_BARS == 60


def test_ensure_kst_localizes_naive():
    ts = pd.Timestamp("2026-01-02 09:30:00")
    out = ensure_kst(ts)
    assert out.tzinfo is not None
    assert str(out.tzinfo) == str(KST)
    assert (out.hour, out.minute) == (9, 30)


def test_ensure_kst_converts_aware():
    ts = pd.Timestamp("2026-01-02 00:30:00", tz="UTC")
    out = ensure_kst(ts)
    assert str(out.tzinfo) == str(KST)
    assert (out.hour, out.minute) == (9, 30)


def test_session_date():
    ts = ensure_kst(pd.Timestamp("2026-01-02 23:45:00"))
    assert session_date(ts) == date(2026, 1, 2)


def test_build_session_index_segments_by_kst_date():
    timestamps = [
        pd.Timestamp("2026-01-02 09:00:00"),
        pd.Timestamp("2026-01-02 09:01:00"),
        pd.Timestamp("2026-01-02 15:20:00"),
        pd.Timestamp("2026-01-05 09:00:00"),
        pd.Timestamp("2026-01-05 09:01:00"),
    ]
    idx = build_session_index(timestamps)
    assert isinstance(idx, SessionIndex)
    assert len(idx) == 5
    assert idx.session_dates == [
        date(2026, 1, 2),
        date(2026, 1, 2),
        date(2026, 1, 2),
        date(2026, 1, 5),
        date(2026, 1, 5),
    ]
    assert idx.session_start_idx == [0, 0, 0, 3, 3]


def test_build_session_index_accepts_pandas_series():
    series = pd.Series(
        pd.to_datetime(
            [
                "2026-01-02 09:00:00",
                "2026-01-02 09:01:00",
                "2026-01-05 09:00:00",
            ]
        )
    )
    idx = build_session_index(series)
    assert idx.session_start_idx == [0, 0, 2]


def test_build_prev_session_close():
    session_dates = [
        date(2026, 1, 2),
        date(2026, 1, 2),
        date(2026, 1, 5),
        date(2026, 1, 5),
        date(2026, 1, 6),
    ]
    closes = [100.0, 101.0, 200.0, 202.0, 300.0]
    prev = build_prev_session_close(session_dates, closes)
    assert date(2026, 1, 2) not in prev
    assert prev[date(2026, 1, 5)] == 101.0
    assert prev[date(2026, 1, 6)] == 202.0


def test_build_prev_session_close_exact_boundaries():
    """The recorded prev-close is the last close seen before the date flips."""
    session_dates = [date(2026, 1, 2), date(2026, 1, 5)]
    closes = [111.0, 222.0]
    prev = build_prev_session_close(session_dates, closes)
    assert prev == {date(2026, 1, 5): 111.0}
