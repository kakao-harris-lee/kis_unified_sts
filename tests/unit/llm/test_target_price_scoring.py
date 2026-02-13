"""Tests for target-price scoring and score_stock_candidate in LLM screener."""

import pytest

pytest.importorskip("httpx")

from shared.llm.data_classes import Signal, StockInfo, TechnicalAnalysis
from shared.llm.llm_analyzer import UnifiedTradingAnalyzer
from shared.llm.stock_screening import score_stock_candidate


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
            "stock_score_weight_theme": 0.15,
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


def _make_config(**overrides):
    """Create a minimal mock config for scoring tests."""
    defaults = {
        "stock_score_weight_momentum": 0.35,
        "stock_score_weight_technical": 0.15,
        "stock_score_weight_backtest": 0.20,
        "stock_score_weight_news": 0.10,
        "stock_score_weight_liquidity": 0.10,
        "stock_score_weight_target_price": 0.10,
        "stock_score_weight_theme": 0.15,
        "stock_score_weight_risk": 0.10,
        "stock_min_trade_value": 500_000_000,
        "stock_min_turnover": 0.003,
        "stock_max_atr_pct": 0.08,
        "stock_max_drawdown_pct": 0.25,
        "stock_new_listing_penalty": 0.7,
        "stock_enable_kis_target_price": True,
    }
    defaults.update(overrides)
    return type("C", (), defaults)()


def test_soft_filter_extreme_atr_gets_heavy_penalty():
    """Extreme ATR (was hard-filtered) → heavy risk penalty, but still scored."""
    stock = StockInfo(
        code="123456",
        name="변동성종목",
        price=10000,
        change_pct=5.0,
        volume=500000,
        volume_ratio=1.5,
        market_cap=500_000_000_000,
        trade_value=2_000_000_000,
        turnover=0.004,
    )
    tech = TechnicalAnalysis(
        rsi=50.0,
        macd=0.0,
        macd_signal=0.0,
        macd_hist=0.0,
        bb_position=0.5,
        ma5=10000,
        ma20=10000,
        ma60=10000,
        trend="횡보",
        signal=Signal.HOLD,
    )
    config = _make_config()

    # Normal ATR (0.05 < max 0.08)
    screening_normal = {
        "momentum": {"ret_5d": 0, "ret_20d": 0, "ret_60d": 0, "high_proximity": 0.8},
        "consecutive_up": 0,
        "atr_pct": 0.05,
        "max_drawdown_pct": 0.10,
        "volatility": 0.3,
        "risk_keywords": [],
        "target_available": False,
        "is_new_listing": False,
    }
    normal_score, normal_bd = score_stock_candidate(
        stock, tech, None, {"sentiment": "중립", "news_count": 0}, screening_normal, config
    )

    # Extreme ATR (0.15 > max*1.5 = 0.12)
    screening_extreme = dict(screening_normal, atr_pct=0.15)
    extreme_score, extreme_bd = score_stock_candidate(
        stock, tech, None, {"sentiment": "중립", "news_count": 0}, screening_extreme, config
    )

    # Extreme ATR should produce a score (not excluded), but much lower
    assert isinstance(extreme_score, float)
    assert extreme_bd["risk_penalty"] >= 15
    assert extreme_score < normal_score


def test_soft_filter_extreme_drawdown_gets_heavy_penalty():
    """Extreme drawdown (was hard-filtered) → heavy risk penalty."""
    stock = StockInfo(
        code="654321",
        name="낙폭종목",
        price=20000,
        change_pct=-2.0,
        volume=300000,
        volume_ratio=1.0,
        market_cap=800_000_000_000,
        trade_value=3_000_000_000,
        turnover=0.004,
    )
    tech = TechnicalAnalysis(
        rsi=35.0,
        macd=-0.1,
        macd_signal=0.0,
        macd_hist=-0.1,
        bb_position=0.2,
        ma5=20500,
        ma20=21000,
        ma60=22000,
        trend="하락",
        signal=Signal.SELL,
    )
    config = _make_config()

    # Extreme drawdown (0.45 > max*1.5 = 0.375)
    screening = {
        "momentum": {"ret_5d": -3, "ret_20d": -8, "ret_60d": -15, "high_proximity": 0.6},
        "consecutive_up": 0,
        "atr_pct": 0.06,
        "max_drawdown_pct": 0.45,
        "volatility": 0.5,
        "risk_keywords": [],
        "target_available": False,
        "is_new_listing": False,
    }
    score, bd = score_stock_candidate(
        stock, tech, None, {"sentiment": "중립", "news_count": 0}, screening, config
    )

    assert isinstance(score, float)
    assert bd["risk_penalty"] >= 15
    # Should have a strongly negative total score
    assert score < 0
