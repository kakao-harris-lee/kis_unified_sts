"""Tests for trade-trend priority in the realtime screener."""

from __future__ import annotations

import pandas as pd

from services.screener import _select_top_codes
from shared.scanner.trade_trend_priority import (
    TradeTrendPriorityConfig,
    TradeTrendPriorityRanker,
)


def test_select_top_codes_applies_trade_trend_priority_before_top_n(tmp_path):
    snapshot_path = tmp_path / "trade.csv"
    pd.DataFrame(
        [
            {
                "period": "2026-05",
                "sector": "semiconductor",
                "trade_trend_score": 1.0,
            }
        ]
    ).to_csv(snapshot_path, index=False)
    ranker = TradeTrendPriorityRanker(
        TradeTrendPriorityConfig(
            snapshot_path=str(snapshot_path),
            max_bonus=0.15,
            symbol_sectors={"000660": ["semiconductor"]},
        )
    )

    codes, scores, info, metadata, summary = _select_top_codes(
        {
            "kospi_volume": [
                {"code": "005930", "name": "삼성전자", "trade_value": 100},
                {"code": "000660", "name": "SK하이닉스", "trade_value": 90},
            ],
            "kosdaq_volume": [],
            "kospi_gainer": [],
            "kosdaq_gainer": [],
        },
        rank_limit=10,
        top_n=1,
        weight_trade_value=0.6,
        weight_gainer=0.4,
        trade_trend_ranker=ranker,
    )

    assert codes == ["000660"]
    assert scores["000660"] == 1.0
    assert info["000660"]["name"] == "SK하이닉스"
    assert metadata["000660"]["trade_trend_priority"]["matched_sector"] == (
        "semiconductor"
    )
    assert summary["status"] == "loaded"


def test_select_top_codes_applies_swing_discovery_sources():
    codes, scores, info, metadata, summary = _select_top_codes(
        {
            "kospi_volume": [
                {"code": "005930", "name": "삼성전자", "trade_value": 100}
            ],
            "kosdaq_volume": [],
            "kospi_gainer": [],
            "kosdaq_gainer": [],
            "kospi_volume_power": [
                {
                    "code": "123456",
                    "name": "스윙후보",
                    "price": 12000,
                    "change_pct": 5.0,
                    "volume_power": 190.5,
                    "buy_volume": 5000,
                    "sell_volume": 2000,
                }
            ],
            "kosdaq_volume_power": [],
            "kospi_near_new_high": [
                {
                    "code": "123456",
                    "name": "스윙후보",
                    "near_high_rate": 0.8,
                    "new_high": 12300,
                    "bid_quantity": 100,
                    "ask_quantity": 90,
                }
            ],
            "kosdaq_near_new_high": [],
        },
        rank_limit=10,
        top_n=1,
        weight_trade_value=0.10,
        weight_gainer=0.0,
        weight_volume_power=0.55,
        weight_near_new_high=0.35,
    )

    assert codes == ["123456"]
    assert scores["123456"] == 1.0
    assert info["123456"]["name"] == "스윙후보"
    swing = metadata["123456"]["swing_discovery"]
    assert swing["score"] == 1.0
    assert swing["source_hits"] == ["volume_power", "near_new_high"]
    assert swing["volume_power"] == 190.5
    assert swing["near_high_rate"] == 0.8
    assert summary["swing_discovery"]["candidate_count"] == 1
    assert summary["swing_discovery"]["selected_count"] == 1
