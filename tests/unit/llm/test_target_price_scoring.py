"""Tests for target-price scoring and score_stock_candidate in LLM screener."""

import pytest

pytest.importorskip("httpx")

from shared.llm.data_classes import Signal, StockInfo, TechnicalAnalysis
from shared.llm.llm_analyzer import UnifiedTradingAnalyzer


def test_score_target_price_signal_positive_case():
    score = UnifiedTradingAnalyzer._score_target_price_signal(
        {
            "target_available": True,
            "target_upside_pct": 22.5,
            "target_opinion": "매수",
        }
    )
    assert score > 0


def test_score_target_price_signal_negative_case():
    score = UnifiedTradingAnalyzer._score_target_price_signal(
        {
            "target_available": True,
            "target_upside_pct": -15.0,
            "target_opinion": "매도",
        }
    )
    assert score < 0


def test_score_target_price_signal_unavailable_case():
    score = UnifiedTradingAnalyzer._score_target_price_signal(
        {
            "target_available": False,
            "target_upside_pct": 30.0,
            "target_opinion": "매수",
        }
    )
    assert score == 0.0


def test_score_stock_candidate_best_none_new_listing():
    """best=None (new listing) → backtest_score=0, penalty applied."""
    stock = StockInfo(
        code="999999",
        name="테스트신규",
        price=50000,
        change_pct=3.0,
        volume=100000,
        volume_ratio=2.0,
        market_cap=1_000_000_000_000,
        trade_value=5_000_000_000,
        turnover=0.005,
    )
    tech = TechnicalAnalysis(
        rsi=45.0,
        macd=0.1,
        macd_signal=0.05,
        macd_hist=0.05,
        bb_position=0.5,
        ma5=49000,
        ma20=48000,
        ma60=47000,
        trend="상승",
        signal=Signal.BUY,
    )
    screening = {
        "momentum": {
            "ret_5d": 2.0,
            "ret_20d": 5.0,
            "ret_60d": 0.0,
            "high_proximity": 0.85,
        },
        "consecutive_up": 1,
        "atr_pct": 0.03,
        "max_drawdown_pct": 0.10,
        "volatility": 0.25,
        "risk_keywords": [],
        "target_available": False,
        "target_upside_pct": 0.0,
        "target_opinion": "",
        "is_new_listing": True,
    }
    news = {"sentiment": "중립"}

    analyzer = object.__new__(UnifiedTradingAnalyzer)
    analyzer.config = type(
        "C",
        (),
        {
            "stock_score_weight_momentum": 0.35,
            "stock_score_weight_technical": 0.15,
            "stock_score_weight_backtest": 0.20,
            "stock_score_weight_news": 0.10,
            "stock_score_weight_liquidity": 0.10,
            "stock_score_weight_target_price": 0.10,
            "stock_score_weight_risk": 0.10,
            "stock_min_trade_value": 500_000_000,
            "stock_min_turnover": 0.003,
            "stock_max_atr_pct": 0.08,
            "stock_max_drawdown_pct": 0.25,
            "stock_new_listing_penalty": 0.7,
            "stock_enable_kis_target_price": True,
        },
    )()

    score, breakdown = analyzer._score_stock_candidate(
        stock, tech, None, news, screening
    )
    assert breakdown["backtest"] == 0.0
    assert breakdown["is_new_listing"] is True
    # Score should be penalized by new_listing_penalty (0.7)
    assert score == breakdown["total"]
