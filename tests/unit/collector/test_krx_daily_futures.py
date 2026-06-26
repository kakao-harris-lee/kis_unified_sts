"""Unit tests for the KRX KOSPI200 futures daily settlement bar collector.

All tests are hermetic — no network calls, no KRX API key required.
The fixture population mirrors the KRX ``drv/fut_bydd_trd`` response format.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures — KRX API response format
# ---------------------------------------------------------------------------


def _make_krx_item(
    bas_dd: str,
    close: float,
    volume: int = 200_000,
    prod_nm: str = "코스피200 선물",
    mkt_nm: str = "정규",
    contract: str = "코스피200 F 202412 (주간)",
) -> dict:
    """Build a synthetic KRX ``drv/fut_bydd_trd`` item."""
    return {
        "BAS_DD": bas_dd,
        "PROD_NM": prod_nm,
        "MKT_NM": mkt_nm,
        "ISU_CD": "101V3000",
        "ISU_NM": contract,
        "TDD_CLSPRC": str(close),
        "CMPPREVDD_PRC": "0.00",
        "TDD_OPNPRC": str(close - 1.0),
        "TDD_HGPRC": str(close + 2.0),
        "TDD_LWPRC": str(close - 2.0),
        "SPOT_PRC": str(close - 0.5),
        "SETL_PRC": str(close),
        "ACC_TRDVOL": str(volume),
        "ACC_TRDVAL": "50000000000",
        "ACC_OPNINT_QTY": "300000",
    }


def _make_day_items(bas_dd: str, close: float = 350.0, num_contracts: int = 5) -> list[dict]:
    """Build a realistic day response with num_contracts varying volumes."""
    items = []
    for i in range(num_contracts):
        # First contract has the highest volume (= front-month)
        vol = 200_000 - i * 40_000
        items.append(
            _make_krx_item(
                bas_dd=bas_dd,
                close=close + i * 0.5,
                volume=max(vol, 1000),
                contract=f"코스피200 F 20240{i + 3} (주간)",
            )
        )
    # Add a night-session item that should be filtered out
    items.append(
        _make_krx_item(bas_dd=bas_dd, close=close - 0.1, mkt_nm="야간", volume=50_000)
    )
    return items


# ---------------------------------------------------------------------------
# Import helper (lazy so collection never requires KRX env)
# ---------------------------------------------------------------------------


def _import_m():
    from shared.collector.historical import krx_daily_futures as m

    return m


# ---------------------------------------------------------------------------
# TestSelectFrontMonth
# ---------------------------------------------------------------------------


class TestSelectFrontMonth:
    def test_highest_volume_contract_selected(self):
        m = _import_m()
        items = _make_day_items("20240108", close=350.0, num_contracts=5)
        front = m._select_front_month(items)
        assert front is not None
        # Highest volume is the first item (200_000)
        assert int(front["ACC_TRDVOL"]) == 200_000

    def test_night_session_excluded(self):
        m = _import_m()
        # Only a night-session item — should return None
        items = [_make_krx_item("20240108", close=350.0, mkt_nm="야간", volume=999_999)]
        result = m._select_front_month(items)
        assert result is None

    def test_non_kospi200_excluded(self):
        m = _import_m()
        items = [_make_krx_item("20240108", close=350.0, prod_nm="미니금 선물", volume=500_000)]
        assert m._select_front_month(items) is None

    def test_low_volume_returns_none(self):
        m = _import_m()
        items = [_make_krx_item("20240108", close=350.0, volume=500)]  # below min 1000
        assert m._select_front_month(items) is None

    def test_empty_input_returns_none(self):
        m = _import_m()
        assert m._select_front_month([]) is None


# ---------------------------------------------------------------------------
# TestParseBar
# ---------------------------------------------------------------------------


class TestParseBar:
    def test_valid_bar(self):
        m = _import_m()
        raw = _make_krx_item("20240108", close=347.40, volume=229_936)
        bar = m._parse_bar(raw, "krx_kospi200f_continuous")
        assert bar is not None
        assert bar["code"] == "krx_kospi200f_continuous"
        assert bar["datetime"] == datetime(2024, 1, 8)
        assert bar["close"] == pytest.approx(347.40)
        assert bar["open"] == pytest.approx(346.40)
        assert bar["high"] == pytest.approx(349.40)
        assert bar["low"] == pytest.approx(345.40)
        assert bar["volume"] == 229_936

    def test_ohlc_inversion_rejected(self):
        m = _import_m()
        raw = _make_krx_item("20240108", close=347.40)
        # Force high < open — violation
        raw["TDD_HGPRC"] = "300.00"
        raw["TDD_OPNPRC"] = "350.00"
        assert m._parse_bar(raw, "krx_kospi200f_continuous") is None

    def test_zero_price_rejected(self):
        m = _import_m()
        raw = _make_krx_item("20240108", close=0.0)
        assert m._parse_bar(raw, "krx_kospi200f_continuous") is None

    def test_malformed_date_rejected(self):
        m = _import_m()
        raw = _make_krx_item("20240108", close=347.40)
        raw["BAS_DD"] = "bad-date"
        assert m._parse_bar(raw, "krx_kospi200f_continuous") is None

    def test_comma_in_numbers_handled(self):
        m = _import_m()
        raw = _make_krx_item("20240108", close=1_350.00)
        raw["TDD_CLSPRC"] = "1,350.00"
        raw["TDD_OPNPRC"] = "1,349.00"
        raw["TDD_HGPRC"] = "1,352.00"
        raw["TDD_LWPRC"] = "1,348.00"
        raw["ACC_TRDVOL"] = "229,936"
        bar = m._parse_bar(raw, "krx_kospi200f_continuous")
        assert bar is not None
        assert bar["close"] == pytest.approx(1350.0)
        assert bar["volume"] == 229_936


# ---------------------------------------------------------------------------
# TestReturnGate
# ---------------------------------------------------------------------------


class TestReturnGate:
    def test_normal_returns_pass(self):
        m = _import_m()
        bars = [
            {"code": "k", "datetime": datetime(2024, 1, 8), "close": 350.0,
             "open": 349.0, "high": 352.0, "low": 348.0, "volume": 200_000},
            {"code": "k", "datetime": datetime(2024, 1, 9), "close": 352.5,
             "open": 350.5, "high": 354.0, "low": 350.0, "volume": 195_000},
        ]
        accepted, last = m._apply_return_gate(bars, prev_close=349.0)
        assert len(accepted) == 2
        assert last == pytest.approx(352.5)

    def test_extreme_return_rejected(self):
        m = _import_m()
        bars = [
            {"code": "k", "datetime": datetime(2024, 1, 8), "close": 350.0,
             "open": 349.0, "high": 352.0, "low": 348.0, "volume": 200_000},
            # 50% jump — well above 25% gate
            {"code": "k", "datetime": datetime(2024, 1, 9), "close": 525.0,
             "open": 520.0, "high": 530.0, "low": 519.0, "volume": 195_000},
        ]
        accepted, _ = m._apply_return_gate(bars, prev_close=350.0)
        assert len(accepted) == 1
        assert accepted[0]["close"] == pytest.approx(350.0)

    def test_no_prev_close_first_bar_passes(self):
        m = _import_m()
        bars = [
            {"code": "k", "datetime": datetime(2024, 1, 8), "close": 999.0,
             "open": 990.0, "high": 1005.0, "low": 985.0, "volume": 100_000},
        ]
        accepted, last = m._apply_return_gate(bars, prev_close=None)
        assert len(accepted) == 1
        assert last == pytest.approx(999.0)


# ---------------------------------------------------------------------------
# TestCollectKrxFuturesDaily — integration-style with fake HTTP
# ---------------------------------------------------------------------------


class TestCollectKrxFuturesDaily:
    def _run(self, tmp_path: Path, day_map: dict[str, list[dict] | None]) -> dict:
        """Run collect_krx_futures_daily with fake _fetch_day responses.

        day_map: {date_str: items_list or None (simulates empty)}
        """
        m = _import_m()

        def fake_fetch_day(api_key: str, trading_day: date, max_retries: int = 3) -> list:
            key = trading_day.strftime("%Y%m%d")
            result = day_map.get(key)
            return result or []

        with patch.object(m, "_fetch_day", side_effect=fake_fetch_day):
            return m.collect_krx_futures_daily(
                start_date=date(2024, 1, 8),
                end_date=date(2024, 1, 12),
                storage_symbol="krx_kospi200f_continuous",
                data_root=tmp_path,
                api_key="test_key",
                verbose=False,
            )

    def test_writes_bars_for_each_trading_day(self, tmp_path):
        day_map = {
            "20240108": _make_day_items("20240108", close=347.40),
            "20240109": _make_day_items("20240109", close=348.00),
            "20240110": _make_day_items("20240110", close=350.20),
            "20240111": _make_day_items("20240111", close=349.80),
            "20240112": _make_day_items("20240112", close=351.00),
        }
        result = self._run(tmp_path, day_map)
        assert result["bars_written"] == 5  # 5 trading days (Mon–Fri) provided
        assert result["days_attempted"] == 5

    def test_idempotent_double_write(self, tmp_path):
        """Re-running must not create duplicates."""
        day_map = {
            "20240108": _make_day_items("20240108", close=347.40),
            "20240109": _make_day_items("20240109", close=348.00),
        }
        result1 = self._run(tmp_path, day_map)
        result2 = self._run(tmp_path, day_map)
        # Same bars written both times — no duplicates
        assert result1["bars_written"] == result2["bars_written"]

        m = _import_m()
        status = m.get_krx_futures_daily_status(data_root=tmp_path)
        assert status["bar_count"] == result1["bars_written"]

    def test_empty_api_response_counted_as_skipped(self, tmp_path):
        day_map = {"20240108": None, "20240109": None}
        result = self._run(tmp_path, day_map)
        assert result["bars_written"] == 0
        assert result["days_skipped"] >= 0

    def test_status_returns_empty_when_no_partition(self, tmp_path):
        m = _import_m()
        status = m.get_krx_futures_daily_status(data_root=tmp_path)
        assert status["bar_count"] == 0
        assert "error" in status

    def test_storage_symbol_constant(self):
        m = _import_m()
        assert m._KRX_STORAGE_SYMBOL == "krx_kospi200f_continuous"

    def test_earliest_date_constant(self):
        m = _import_m()
        assert date(2010, 1, 4) == m._KRX_EARLIEST_DATE

    def test_no_api_key_raises(self, tmp_path, monkeypatch):
        m = _import_m()
        # Clear the env var so the function cannot fall back to it
        monkeypatch.delenv("KRX_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="KRX_API_KEY"):
            m.collect_krx_futures_daily(
                start_date=date(2024, 1, 8),
                end_date=date(2024, 1, 9),
                data_root=tmp_path,
                api_key="",
            )

    def test_ohlc_violation_not_written(self, tmp_path):
        """A bar with OHLC inversion must be counted as error and not written."""
        m = _import_m()
        bad_item = _make_krx_item("20240108", close=350.0)
        bad_item["TDD_HGPRC"] = "200.0"  # high < open — force violation
        day_map = {"20240108": [bad_item]}

        def fake_fetch_day(api_key, trading_day, max_retries=3):
            key = trading_day.strftime("%Y%m%d")
            return day_map.get(key) or []

        with patch.object(m, "_fetch_day", side_effect=fake_fetch_day):
            result = m.collect_krx_futures_daily(
                start_date=date(2024, 1, 8),
                end_date=date(2024, 1, 8),
                data_root=tmp_path,
                api_key="test_key",
                verbose=False,
            )

        assert result["bars_written"] == 0

    def test_night_session_contracts_excluded_from_front_month(self, tmp_path):
        """Night-session contracts must never become the front-month selection."""
        m = _import_m()
        # Day has only a night-session KOSPI200 item (high volume) + no daytime item
        night_only = [_make_krx_item("20240108", close=350.0, mkt_nm="야간", volume=999_999)]
        day_map = {"20240108": night_only}

        def fake_fetch_day(api_key, trading_day, max_retries=3):
            return day_map.get(trading_day.strftime("%Y%m%d"), [])

        with patch.object(m, "_fetch_day", side_effect=fake_fetch_day):
            result = m.collect_krx_futures_daily(
                start_date=date(2024, 1, 8),
                end_date=date(2024, 1, 8),
                data_root=tmp_path,
                api_key="test_key",
                verbose=False,
            )

        # No regular-session bar found → skipped
        assert result["bars_written"] == 0
