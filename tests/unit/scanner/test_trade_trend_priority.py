"""Tests for trade-trend screener priority adjustment."""

from __future__ import annotations

from datetime import date

import pandas as pd

from shared.scanner.trade_trend_priority import (
    TradeTrendPriorityConfig,
    TradeTrendPriorityRanker,
    load_trade_trend_snapshot,
)


def test_trade_trend_ranker_reorders_by_bounded_sector_bonus(tmp_path):
    snapshot_path = tmp_path / "trade.csv"
    pd.DataFrame(
        [
            {
                "period": "2026-05",
                "sector": "semiconductors",
                "trade_trend_score": 1.0,
            }
        ]
    ).to_csv(snapshot_path, index=False)
    config = TradeTrendPriorityConfig(
        snapshot_path=str(snapshot_path),
        max_bonus=0.2,
        symbol_sectors={"000660": ["semiconductor"]},
        sector_aliases={"semiconductors": "semiconductor"},
    )

    result = TradeTrendPriorityRanker(config).rank_codes(
        ["005930", "000660"],
        {"005930": 1.0, "000660": 0.9},
    )

    assert result.codes == ["000660", "005930"]
    assert result.scores["000660"] > result.scores["005930"]
    assert result.metadata["000660"]["trade_trend_priority"]["bonus"] == 0.2
    assert result.summary["status"] == "loaded"


def test_trade_trend_ranker_missing_snapshot_preserves_order(tmp_path):
    config = TradeTrendPriorityConfig(
        snapshot_path=str(tmp_path / "missing.parquet"),
        symbol_sectors={"000660": ["semiconductor"]},
    )

    result = TradeTrendPriorityRanker(config).rank_codes(
        ["005930", "000660"],
        {"005930": 1.0, "000660": 0.9},
    )

    assert result.codes == ["005930", "000660"]
    assert result.metadata == {}
    assert result.summary["status"] == "missing"


def test_trade_trend_snapshot_computes_score_from_growth_columns(tmp_path):
    snapshot_path = tmp_path / "trade.csv"
    pd.DataFrame(
        [
            {
                "yyyymm": "202605",
                "sector": "auto",
                "export_yoy_pct": 20.0,
                "export_mom_pct": 5.0,
                "import_yoy_pct": 10.0,
            }
        ]
    ).to_csv(snapshot_path, index=False)
    config = TradeTrendPriorityConfig(
        snapshot_path=str(snapshot_path),
        pct_scale=20.0,
        export_yoy_weight=0.7,
        export_mom_weight=0.2,
        import_yoy_weight=-0.1,
    )

    snapshot = load_trade_trend_snapshot(config, today=date(2026, 6, 5))

    assert snapshot.available is True
    assert snapshot.as_of_date == date(2026, 5, 31)
    assert snapshot.sector_scores is not None
    assert snapshot.sector_scores["auto"] == 0.7
