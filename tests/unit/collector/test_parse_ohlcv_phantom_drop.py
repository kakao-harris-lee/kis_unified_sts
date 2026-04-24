"""Tests for phantom-print filtering in ``parse_ohlcv``.

KIS's tick feed emits off-market volume=2 quotes at recurring clock
times. The aggregator now drops any minute bar below
``KIS_MINUTE_BAR_MIN_VOLUME`` before persistence so
``kospi.kospi200f_1m`` stops accumulating phantoms.
"""

from __future__ import annotations

from shared.collector.historical.backfill import parse_ohlcv


def _tick(time_str: str, price: float, volume: int) -> dict:
    """Build a single KIS API output row."""
    return {
        "stck_cntg_hour": time_str,
        "futs_oprc": price,
        "futs_hgpr": price,
        "futs_lwpr": price,
        "futs_prpr": price,
        "cntg_vol": volume,
    }


def test_parse_ohlcv_drops_phantom_volume_bars(monkeypatch) -> None:
    monkeypatch.delenv("KIS_MINUTE_BAR_MIN_VOLUME", raising=False)
    data = {
        "output2": [
            _tick("092200", 400.0, 2),  # phantom: volume below default floor
            _tick("093000", 401.0, 500),  # real
            _tick("110100", 399.0, 2),  # phantom
            _tick("120000", 402.0, 1000),  # real
        ]
    }
    rows = parse_ohlcv("101S6000", "20260701", data)
    minutes = {row[1].strftime("%H:%M") for row in rows}
    assert "09:30" in minutes
    assert "12:00" in minutes
    assert "09:22" not in minutes, "phantom volume=2 bar was not dropped"
    assert "11:01" not in minutes, "phantom volume=2 bar was not dropped"


def test_parse_ohlcv_respects_env_threshold_override(monkeypatch) -> None:
    # Raise threshold very high — everything becomes a phantom.
    monkeypatch.setenv("KIS_MINUTE_BAR_MIN_VOLUME", "10000")
    data = {
        "output2": [
            _tick("093000", 401.0, 500),
            _tick("100000", 402.0, 800),
        ]
    }
    rows = parse_ohlcv("101S6000", "20260701", data)
    assert rows == []


def test_parse_ohlcv_threshold_zero_keeps_everything(monkeypatch) -> None:
    monkeypatch.setenv("KIS_MINUTE_BAR_MIN_VOLUME", "0")
    data = {
        "output2": [
            _tick("092200", 400.0, 2),  # would normally drop
            _tick("093000", 401.0, 500),
        ]
    }
    rows = parse_ohlcv("101S6000", "20260701", data)
    minutes = {row[1].strftime("%H:%M") for row in rows}
    assert minutes == {"09:22", "09:30"}


def test_parse_ohlcv_default_threshold_is_10(monkeypatch) -> None:
    monkeypatch.delenv("KIS_MINUTE_BAR_MIN_VOLUME", raising=False)
    data = {
        "output2": [
            _tick("092200", 400.0, 9),  # just below default
            _tick("093000", 401.0, 10),  # exactly at default — kept
            _tick("100000", 402.0, 11),  # above default
        ]
    }
    rows = parse_ohlcv("101S6000", "20260701", data)
    minutes = {row[1].strftime("%H:%M") for row in rows}
    assert "09:22" not in minutes
    assert "09:30" in minutes  # volume=10 >= 10 threshold (strict <)
    assert "10:00" in minutes
