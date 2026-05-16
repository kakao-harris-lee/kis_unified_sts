"""Tests for institutional ownership signals."""

from types import SimpleNamespace

from shared.llm.institutional_signals import build_nps_ownership_signal
from shared.llm.stock_screening import score_nps_ownership_signal


def test_build_nps_ownership_signal_picks_latest_matching_report():
    dart_data = {
        "major_shareholders": [
            {
                "rcept_no": "20260506000282",
                "rcept_dt": "2026-05-06",
                "repror": "국민연금공단",
                "report_tp": "약식",
                "report_resn": "단순추가취득/처분",
                "stkqy": "989,244",
                "stkqy_irds": "-220,090",
                "stkrt": "5.00",
                "stkrt_irds": "-1.11",
            }
        ],
        "executive_major_shareholders": [
            {
                "rcept_no": "20260514000962",
                "rcept_dt": "2026-05-14",
                "repror": "국민연금공단",
                "isu_main_shrholdr": "10%이상주주",
                "sp_stock_lmp_cnt": "4,042,185",
                "sp_stock_lmp_irds_cnt": "-860",
                "sp_stock_lmp_rate": "9.99",
                "sp_stock_lmp_irds_rate": "-0.03",
            }
        ],
    }

    signal = build_nps_ownership_signal(dart_data, SimpleNamespace())

    assert signal["available"] is True
    assert signal["source"] == "elestock"
    assert signal["rcept_no"] == "20260514000962"
    assert signal["holding_shares"] == 4_042_185
    assert signal["holding_ratio_pct"] == 9.99
    assert signal["matched_reports"] == 2


def test_score_nps_ownership_signal_weights_ratio_and_change():
    config = SimpleNamespace(
        stock_nps_enabled=True,
        stock_nps_holding_ratio_anchor_pct=10.0,
        stock_nps_base_score_max=10.0,
        stock_nps_change_pctp_multiplier=2.0,
        stock_nps_change_score_cap=5.0,
        stock_nps_score_cap=15.0,
        stock_nps_max_report_age_days=99999,
        stock_nps_stale_score_multiplier=0.5,
    )
    screening = {
        "nps_ownership": {
            "available": True,
            "holding_ratio_pct": 10.01,
            "holding_ratio_change_pctp": 10.01,
            "rcept_dt": "2026-05-14",
        }
    }

    assert score_nps_ownership_signal(screening, config) == 15.0


def test_score_nps_ownership_signal_disabled_or_missing_is_neutral():
    config = SimpleNamespace(stock_nps_enabled=False)
    assert score_nps_ownership_signal({}, config) == 0.0
