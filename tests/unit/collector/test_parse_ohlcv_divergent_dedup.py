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


def _row(time_str: str, o: float, h: float, l: float, c: float, v: int) -> dict:
    """Build a single KIS futures ``output2`` row (a complete 1-minute bar)."""
    return {
        "stck_cntg_hour": time_str,
        "futs_oprc": f"{o:.2f}",
        "futs_hgpr": f"{h:.2f}",
        "futs_lwpr": f"{l:.2f}",
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
    _code, _dt, o, h, l, c, v = rows[0]
    assert (o, h, l, c) == (821.15, 822.55, 815.70, 819.95)
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
    _code, _dt, o, h, l, c, v = bars["15:32"]
    # Real 758-series chosen, not the phantom 862-series.
    assert (o, h, l, c) == (758.70, 759.85, 758.15, 758.40)
    assert v == 1009
    # Never a Frankenstein bar: high == max(o,c) region, no 862 spike.
    assert h < 800.0
    assert h >= max(o, c)
    assert l <= min(o, c)


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
    for _code, _dt, o, h, l, c, _v in rows:
        assert h >= max(o, c) - 1e-9, f"high {h} < max(open {o}, close {c})"
        assert l <= min(o, c) + 1e-9, f"low {l} > min(open {o}, close {c})"
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
    _code, _dt, o, h, l, c, _v = bars["14:07"]
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
