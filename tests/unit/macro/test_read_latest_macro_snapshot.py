"""Tests for shared.macro.base.read_latest_macro_snapshot.

Root-cause context: Setup A (gap reversion) hard-requires
``ctx.macro_overnight.sp500_change_pct``. The collector interleaves
``overnight_us_close`` (sp500, once/day) and ``overnight_fx`` (usdkrw,
every 15 min) on one stream — a naive latest-entry read returns an fx row
with sp500=None and Setup A no-ops forever. The reader must forward-fill
per field across a recent window.
"""
from __future__ import annotations

import json

from shared.macro.base import read_latest_macro_snapshot


class _FakeRedis:
    """xrevrange returns entries newest-first, like real redis."""

    def __init__(self, entries: list[tuple[str, dict]]):
        self._entries = entries  # already newest-first

    def xrevrange(self, stream: str, count: int = 1):  # noqa: ARG002
        return self._entries[:count]


def _fx(ts_ms: int, usdkrw: float) -> tuple[str, dict]:
    return (
        f"{ts_ms}-0",
        {
            "ts_ms": str(ts_ms),
            "session": "overnight_fx",
            "usdkrw": str(usdkrw),
            "usdkrw_change_pct": "0.5",
            "sp500_change_pct": "",  # collector emits "" for None
            "collected_from_json": json.dumps(["ecos"]),
        },
    )


def _us(ts_ms: int, sp500_pct: float) -> tuple[str, dict]:
    return (
        f"{ts_ms}-0",
        {
            "ts_ms": str(ts_ms),
            "session": "overnight_us_close",
            "sp500_close": "5400.0",
            "sp500_change_pct": str(sp500_pct),
            "vix": "17.2",
            "usdkrw": "",
            "collected_from_json": json.dumps(["yahoo"]),
        },
    )


def test_empty_stream_returns_none():
    assert read_latest_macro_snapshot(_FakeRedis([]), "s") is None


def test_read_failure_returns_none():
    class _Boom:
        def xrevrange(self, *a, **k):
            raise RuntimeError("redis down")

    assert read_latest_macro_snapshot(_Boom(), "s") is None


def test_latest_fx_only_has_no_sp500():
    """Sanity: a stream of only fx rows yields sp500=None (the bug case)."""
    snap = read_latest_macro_snapshot(
        _FakeRedis([_fx(3000, 1484.3), _fx(2000, 1483.0)]), "s"
    )
    assert snap is not None
    assert snap.sp500_change_pct is None
    assert snap.usdkrw == 1484.3


def test_merges_sp500_from_older_us_close_into_latest_fx():
    """The fix: newest is fx (no sp500) but the day's us_close sp500 is
    forward-filled from a window scan."""
    entries = [
        _fx(5000, 1485.0),   # newest
        _fx(4000, 1484.5),
        _us(3000, 0.77),     # the day's US close — has sp500
        _fx(2000, 1483.0),
    ]
    snap = read_latest_macro_snapshot(_FakeRedis(entries), "s", scan=200)
    assert snap is not None
    # newest observation metadata
    assert snap.ts_ms == 5000
    assert snap.session == "overnight_fx"
    # merged: sp500 from us_close, usdkrw from newest fx
    assert snap.sp500_change_pct == 0.77
    assert snap.usdkrw == 1485.0
    assert snap.vix == 17.2


def test_newest_value_wins_over_older():
    """Forward-fill takes the *most recent* non-None per field."""
    entries = [_us(3000, 0.90), _us(2000, 0.10)]
    snap = read_latest_macro_snapshot(_FakeRedis(entries), "s")
    assert snap is not None
    assert snap.sp500_change_pct == 0.90  # newest us_close, not 0.10


def test_malformed_ts_entries_skipped():
    bad = ("x-0", {"ts_ms": "notanint", "session": "overnight_fx"})
    good = _us(2000, 0.55)
    snap = read_latest_macro_snapshot(_FakeRedis([bad, good]), "s")
    assert snap is not None
    assert snap.ts_ms == 2000
    assert snap.sp500_change_pct == 0.55
