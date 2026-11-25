"""Tests for divergent-duplicate de-duplication in ``parse_ohlcv``."""

from __future__ import annotations

from shared.collector.historical.ohlcv_parser import parse_ohlcv


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
    assert v == 1779


def test_divergent_six_row_minute_picks_continuous_series() -> None:
    """Replicates the A01603 20260304 15:32 case."""
    data = {
        "output2": [
            _row("153100", 757.20, 758.10, 756.80, 757.40, 1200),
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
    assert (o, h, low, c) == (758.70, 759.85, 758.15, 758.40)
    assert v == 1009
    assert h < 800.0
    assert h >= max(o, c)
    assert low <= min(o, c)


def test_no_bar_violates_ohlc_consistency() -> None:
    """Every emitted bar satisfies high >= max(open, close), low <= min(...)."""
    data = {
        "output2": [
            _row("140000", 800.0, 801.0, 799.0, 800.5, 500),
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
    closes = [row[5] for row in rows]
    assert max(closes) < 850.0


def test_divergence_count_flip_does_not_decide() -> None:
    """The phantom may be the majority early and the minority late."""
    data = {
        "output2": [
            _row("140600", 770.0, 771.0, 769.0, 770.5, 600),
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
    """A minute whose only candidate is a phantom-offset jump is dropped."""
    data = {
        "output2": [
            _row("140000", 800.0, 801.0, 799.0, 800.0, 500),
            _row("140100", 800.0, 801.5, 799.5, 800.5, 500),
            _row("140200", 900.5, 901.0, 900.0, 900.5, 200),
            _row("140300", 800.5, 802.0, 800.0, 801.0, 500),
        ]
    }
    rows = parse_ohlcv("A01603", "20260101", data)
    bars = _as_dict(rows)
    assert "14:02" not in bars, "phantom-only minute must be dropped, not emitted"
    assert "14:03" in bars
    assert bars["14:03"][5] == 801.0
    assert max(row[5] for row in rows) < 850.0


def test_phantom_orphan_before_divergent_open_keeps_real_track() -> None:
    """A phantom-only orphan that sorts BEFORE a divergent real open must not"""
    out = [
        _row("090000", 900.0, 901.0, 899.0, 900.0, 300),
        _row("090100", 800.0, 801.0, 799.0, 800.5, 800),
        _row("090100", 901.0, 902.0, 900.0, 901.5, 250),
        _row("090200", 800.5, 802.0, 800.0, 801.5, 850),
        _row("090200", 901.5, 903.0, 901.0, 902.5, 240),
        _row("090300", 801.5, 803.0, 801.0, 802.5, 900),
        _row("090300", 902.5, 904.0, 902.0, 903.5, 230),
    ]
    price = 803.5
    for i in range(4, 21):
        out.append(
            _row(f"09{i:02d}00", price, price + 0.5, price - 0.5, price + 0.3, 900)
        )
        price += 0.3

    rows = parse_ohlcv("A01603", "20260304", {"output2": out})
    closes = [row[5] for row in rows]
    assert closes, "expected emitted bars"
    assert all(c < 850.0 for c in closes), f"phantom track leaked: {closes}"
    assert any(795.0 <= c < 850.0 for c in closes), "real track was dropped"
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
