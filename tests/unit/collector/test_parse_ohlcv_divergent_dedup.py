"""Tests for divergent-duplicate de-duplication in ``parse_ohlcv``.

KIS ``inquire-time-fuopchartprice`` (tr_id FHKIF03020200) echoes each
1-minute bar 5-7 times in ``output2``.  On some sessions a *second*,
internally-consistent-but-divergent price series is interleaved with the real
one for the same minute timestamps (a sustained parallel offset, e.g. ~100
points on full-size KOSPI200 futures).  The legacy aggregator merged these with
(open=first, high=max, low=min, close=last, volume=sum), producing Frankenstein
bars (high from one series, close from the other) and ~5x inflated volume.

``parse_ohlcv`` now collapses byte-identical echoes to one bar (true per-bar
volume) and resolves divergent minutes by price continuity, never by duplicate
count.
"""

from __future__ import annotations

from shared.collector.historical.backfill import parse_ohlcv


def _row(time_str: str, o: float, h: float, low: float, c: float, v: int) -> dict:
    """Build a single KIS futures ``output2`` row (a complete 1-minute bar)."""
    return {
        "stck_cntg_hour": time_str,
        "futs_oprc": f"{o:.2f}",
        "futs_hgpr": f"{h:.2f}",
        "futs_lwpr": f"{low:.2f}",
        "futs_prpr": f"{c:.2f}",
        "cntg_vol": str(v),
    }


def _as_dict(rows: list[tuple]) -> dict[str, tuple]:
    """Index parsed (code, dt, o, h, l, c, v) tuples by HH:MM."""
    return {row[1].strftime("%H:%M"): row for row in rows}


def test_identical_echoes_collapse_without_volume_inflation() -> None:
    """5 byte-identical echoes of one bar => one bar, volume NOT summed."""
    data = {"output2": [_row("084500", 821.15, 822.55, 815.70, 819.95, 1779)] * 5}
    rows = parse_ohlcv("A01603", "20260304", data)
    assert len(rows) == 1
    _code, _dt, o, h, low, c, v = rows[0]
    assert (o, h, low, c) == (821.15, 822.55, 815.70, 819.95)
    # Volume is the single bar's volume (1779), never 5 * 1779 == 8895.
    assert v == 1779


def test_divergent_six_row_minute_picks_continuous_series() -> None:
    """Replicates the A01603 20260304 15:32 case.

    output2 carries the real bar {o758.70, c758.40} once and a phantom
    {o861.95, c862.00} five times.  With the prior minute anchored near 758,
    the resolver must pick the 758 series despite the phantom's 5x majority,
    and must emit an internally consistent bar (never high 862 with close 758).
    """
    data = {
        "output2": [
            # 15:31 — establishes continuity near 757.
            _row("153100", 757.20, 758.10, 756.80, 757.40, 1200),
            # 15:32 — divergent: real 758-series x1, phantom 862-series x5.
            _row("153200", 758.70, 759.85, 758.15, 758.40, 1009),
            _row("153200", 861.95, 862.35, 861.15, 862.00, 849),
            _row("153200", 861.95, 862.35, 861.15, 862.00, 849),
            _row("153200", 861.95, 862.35, 861.15, 862.00, 849),
            _row("153200", 861.95, 862.35, 861.15, 862.00, 849),
            _row("153200", 861.95, 862.35, 861.15, 862.00, 849),
        ]
    }
    rows = parse_ohlcv("A01603", "20260304", data)
    bars = _as_dict(rows)
    assert "15:32" in bars
    _code, _dt, o, h, low, c, v = bars["15:32"]
    # Real 758-series chosen, not the phantom 862-series.
    assert (o, h, low, c) == (758.70, 759.85, 758.15, 758.40)
    assert v == 1009
    # Never a Frankenstein bar: high == max(o,c) region, no 862 spike.
    assert h < 800.0
    assert h >= max(o, c)
    assert low <= min(o, c)


def test_no_bar_violates_ohlc_consistency() -> None:
    """Every emitted bar satisfies high >= max(open, close), low <= min(...)."""
    data = {
        "output2": [
            _row("140000", 800.0, 801.0, 799.0, 800.5, 500),
            # Phantom series ~100pt above, interleaved.
            _row("140100", 800.5, 802.0, 800.0, 801.0, 500),
            _row("140100", 900.0, 901.0, 899.0, 900.5, 500),
            _row("140200", 801.0, 803.0, 800.5, 802.5, 500),
            _row("140200", 900.5, 902.0, 900.0, 901.5, 500),
        ]
    }
    rows = parse_ohlcv("A01603", "20260101", data)
    assert rows, "expected at least one parsed bar"
    for _code, _dt, o, h, low, c, _v in rows:
        assert h >= max(o, c) - 1e-9, f"high {h} < max(open {o}, close {c})"
        assert low <= min(o, c) + 1e-9, f"low {low} > min(open {o}, close {c})"
    # All bars track the continuous ~800 series, none jumped to the 900 phantom.
    closes = [row[5] for row in rows]
    assert max(closes) < 850.0


def test_divergence_count_flip_does_not_decide() -> None:
    """The phantom may be the majority early and the minority late.

    Continuity, not duplicate count, must drive selection in both regimes.
    """
    data = {
        "output2": [
            # Anchor near 770.
            _row("140600", 770.0, 771.0, 769.0, 770.5, 600),
            # 14:07 — phantom (870) is the MAJORITY (x3), real (770) is the
            # minority (x1).  Continuity must still pick 770.
            _row("140700", 770.5, 772.0, 769.5, 771.0, 600),
            _row("140700", 877.0, 879.0, 876.0, 879.2, 200),
            _row("140700", 877.0, 879.0, 876.0, 879.2, 200),
            _row("140700", 877.0, 879.0, 876.0, 879.2, 200),
        ]
    }
    rows = parse_ohlcv("A01603", "20260101", data)
    bars = _as_dict(rows)
    _code, _dt, o, h, _low, c, _v = bars["14:07"]
    assert (o, c) == (770.5, 771.0), "continuity must beat duplicate-count majority"
    assert h < 800.0


def test_phantom_only_minute_is_dropped_not_emitted() -> None:
    """A minute whose only candidate is a phantom-offset jump is dropped.

    Replicates the illiquid back-month gap: the real bar is absent for a minute
    and only the phantom (~100pt above) appears.  Emitting it would both corrupt
    that bar and poison the continuity anchor for every later minute, so the
    resolver drops it, leaving a 1-bar gap, and stays on the real track.
    """
    data = {
        "output2": [
            _row("140000", 800.0, 801.0, 799.0, 800.0, 500),
            _row("140100", 800.0, 801.5, 799.5, 800.5, 500),
            # 14:02 — ONLY the phantom (~+100pt) is present.
            _row("140200", 900.5, 901.0, 900.0, 900.5, 200),
            # 14:03 — the real bar returns near 801.
            _row("140300", 800.5, 802.0, 800.0, 801.0, 500),
        ]
    }
    rows = parse_ohlcv("A01603", "20260101", data)
    bars = _as_dict(rows)
    assert "14:02" not in bars, "phantom-only minute must be dropped, not emitted"
    assert "14:03" in bars
    # The anchor stayed on the real track: 14:03 is near 801, not the 900 phantom.
    assert bars["14:03"][5] == 801.0
    assert max(row[5] for row in rows) < 850.0


def test_phantom_orphan_before_divergent_open_keeps_real_track() -> None:
    """A phantom-only orphan that sorts BEFORE a divergent real open must not
    seed the anchor onto the phantom track.

    Regression for the anchor-seed fragility: the resolver used to seed from the
    chronologically-first single-candidate minute.  If that minute is an isolated
    phantom orphan (the real bar absent while a phantom prints) and the real
    session-open minutes are themselves divergent, the anchor locked onto the
    phantom (~+100pt) and every real bar was then dropped as a >6% jump, leaving a
    clean-looking but WRONG-track day that passes the OHLC + price-sanity gates.

    The seed is now chosen by whole-session continuity support, so the real track
    (which spans the full session) wins and the phantom orphan is dropped.
    """
    out = [
        # 09:00 — phantom-only orphan (single candidate, ~+100pt). Sorts FIRST.
        _row("090000", 900.0, 901.0, 899.0, 900.0, 300),
        # 09:01-09:03 — divergent real (~800) + phantom (~901).
        _row("090100", 800.0, 801.0, 799.0, 800.5, 800),
        _row("090100", 901.0, 902.0, 900.0, 901.5, 250),
        _row("090200", 800.5, 802.0, 800.0, 801.5, 850),
        _row("090200", 901.5, 903.0, 901.0, 902.5, 240),
        _row("090300", 801.5, 803.0, 801.0, 802.5, 900),
        _row("090300", 902.5, 904.0, 902.0, 903.5, 230),
    ]
    # 09:04..09:20 — the real track continues alone (the real-world structure: the
    # phantom is a bounded window, the real track spans the whole session).
    price = 803.5
    for i in range(4, 21):
        out.append(
            _row(f"09{i:02d}00", price, price + 0.5, price - 0.5, price + 0.3, 900)
        )
        price += 0.3

    rows = parse_ohlcv("A01603", "20260304", {"output2": out})
    closes = [row[5] for row in rows]
    assert closes, "expected emitted bars"
    # Real track (~800) kept; phantom track (>=850) entirely dropped.
    assert all(c < 850.0 for c in closes), f"phantom track leaked: {closes}"
    assert any(795.0 <= c < 850.0 for c in closes), "real track was dropped"
    # The phantom orphan minute itself is not emitted.
    bars = _as_dict(rows)
    assert "09:00" not in bars or bars["09:00"][5] < 850.0


def test_single_row_per_minute_is_unchanged() -> None:
    """Index/clean paths return one row per minute: behaviour is preserved."""
    data = {
        "output2": [
            _row("093000", 400.0, 401.0, 399.5, 400.5, 500),
            _row("093100", 400.5, 402.0, 400.0, 401.5, 600),
        ]
    }
    rows = parse_ohlcv("A01603", "20260101", data)
    bars = _as_dict(rows)
    assert bars["09:30"][2:7] == (400.0, 401.0, 399.5, 400.5, 500)
    assert bars["09:31"][2:7] == (400.5, 402.0, 400.0, 401.5, 600)
