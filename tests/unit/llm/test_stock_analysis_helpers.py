"""Tests for stock_analysis helper functions."""

from types import SimpleNamespace

import pandas as pd

from shared.llm.config import LLMConfig
from shared.llm.data_classes import BacktestResult, Signal, StockInfo
from shared.llm.stock_analysis import (
    _attach_market_data,
    _build_screening_meta,
    _build_stock_trading_plan,
    _build_technical_consensus_metrics,
    _filter_candidates_by_min_score,
    _initialize_analysis_results,
    _select_final_candidates,
    _update_analysis_results_with_candidate,
)


def test_filter_candidates_by_min_score():
    candidates = [(1.0, "a"), (5.0, "b"), (10.0, "c")]
    filtered, removed = _filter_candidates_by_min_score(candidates, 5.0)

    assert [c[1] for c in filtered] == ["b", "c"]
    assert removed == 1


def test_select_final_candidates_sorts_and_limits():
    candidates = [(3.0, "a"), (9.0, "b"), (5.0, "c")]
    final = _select_final_candidates(candidates, 2)

    assert [c[1] for c in final] == ["b", "c"]


def test_build_screening_meta_counts(tmp_path):
    cfg = LLMConfig(output_dir=str(tmp_path))
    analysis_results = {
        "_excluded": {
            "A": ["min_trade_value:1", "keyword:foo"],
            "B": ["min_trade_value:2"],
        }
    }

    meta = _build_screening_meta(
        analysis_results,
        cfg,
        intraday=True,
        trade_value_fallback=True,
    )

    assert meta["mode"] == "intraday"
    assert meta["excluded_count"] == 2
    assert meta["excluded_reasons"]["min_trade_value"] == 2
    assert meta["excluded_reasons"]["keyword"] == 1
    assert meta["trade_value_fallback"] is True
    assert meta["filters"]["min_trade_value"] == cfg.stock_min_trade_value


def test_build_stock_trading_plan_uses_scoring_signals(tmp_path):
    cfg = LLMConfig(output_dir=str(tmp_path))
    stock = StockInfo(
        code="0001",
        name="테스트",
        price=1000.0,
        change_pct=0.0,
        volume=1000,
        volume_ratio=2.5,
        market_cap=1_000_000_000,
        trade_value=0.0,
        turnover=0.0,
    )
    tech = SimpleNamespace(signal=Signal.BUY, rsi=35)
    best = BacktestResult(
        strategy_name="변동성 전략",
        total_return=10.0,
        win_rate=56.0,
        max_drawdown=5.0,
        sharpe_ratio=1.0,
        trade_count=20,
        avg_profit=1.0,
        avg_loss=-1.0,
    )
    news = {"sentiment": "긍정", "mk_headlines": ["h1", "h2"]}
    screening = {
        "is_new_listing": True,
        "momentum": {"ret_20d": 5.0, "high_proximity": 0.95},
        "atr_pct": 0.03,
        "target_available": True,
        "target_upside_pct": 12.0,
        "target_opinion": "매수",
        "theme_matched": "AI",
        "theme_score": 2.0,
        "technical_consensus": {
            "entry_signal": True,
            "exit_signal": False,
            "entry_vote_count": 3,
            "exit_vote_count": 0,
        },
    }

    plan = _build_stock_trading_plan(stock, tech, best, news, screening, cfg)

    assert plan.confidence == "높음"
    assert plan.entry_price == 1000.0
    assert plan.stop_loss == 950.0
    assert plan.take_profit == 1080.0
    assert plan.position_size == round(cfg.stock_max_position, 2)
    assert "신규 상장 종목" in plan.reasons
    assert any("KIS 목표가 괴리" in reason for reason in plan.reasons)
    assert any("기술지표 합의 진입" in reason for reason in plan.reasons)


def test_build_technical_consensus_metrics_from_korean_ohlcv(tmp_path):
    cfg = LLMConfig(output_dir=str(tmp_path))
    close = [100 - i for i in range(20)] + [82, 84, 87, 90, 94]
    df = pd.DataFrame(
        {
            "종가": close,
            "고가": [v + 2 for v in close],
            "저가": [v - 2 for v in close],
            "거래량": [1000] * (len(close) - 1) + [1800],
        }
    )

    metrics = _build_technical_consensus_metrics(df, cfg)

    assert "entry_vote_count" in metrics
    assert "entry_core_vote_count" in metrics
    assert "summary" in metrics


def test_update_analysis_results_and_attach_market_data():
    analysis_results = _initialize_analysis_results({}, {})
    stock = StockInfo(
        code="0002",
        name="테스트2",
        price=1000.0,
        change_pct=0.0,
        volume=1000,
        volume_ratio=1.0,
        market_cap=1_000_000_000,
        trade_value=0.0,
        turnover=0.0,
    )

    _update_analysis_results_with_candidate(
        analysis_results,
        stock,
        {"technical": {"rsi": 50}},
        ["history_missing:foo"],
        {"avg_volume": 100},
    )
    _attach_market_data(analysis_results, {"foo": "bar"})

    assert analysis_results["_excluded"][stock.code] == ["history_missing:foo"]
    assert analysis_results["_excluded_features"][stock.code]["avg_volume"] == 100
    assert analysis_results[stock.code]["technical"]["rsi"] == 50
    assert analysis_results["_market_data"]["krx"]["foo"] == "bar"
