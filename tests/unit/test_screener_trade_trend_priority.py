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
