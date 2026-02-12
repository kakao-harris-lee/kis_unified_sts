"""Tests for refactored fallback/score helpers in LLM modules."""

from shared.llm.analyzers import StockTechnicalAnalyzer
from shared.llm.collectors import FuturesFlowCollector
from shared.llm.config import LLMConfig
from shared.llm.data_classes import BondData, ETFFlowData, FuturesData, OptionsData, RiskMode
from shared.llm.llm_analyzer import LLMAnalyzer
from shared.llm.unified_market_analyzer import UnifiedMarketAnalyzer


def test_llm_fallback_analysis_scores_buy_signal():
    analyzer = LLMAnalyzer(api_key="")
    technical = {"rsi": 25, "macd_hist": 1.2}
    backtest = {"win_rate": 60, "total_return": 12}

    result = analyzer._fallback_analysis("000000", "테스트", technical, backtest)

    assert result.overall_score == 55
    assert result.recommendation == "강력매수"
    assert "RSI 과매도" in result.key_reasons[0]
    assert "MACD 상승 신호" in result.key_reasons
    assert any("백테스트 승률 우수" in r for r in result.key_reasons)
    assert any("백테스트 수익률 양호" in r for r in result.key_reasons)


def test_llm_fallback_analysis_defaults_when_empty():
    analyzer = LLMAnalyzer(api_key="")

    result = analyzer._fallback_analysis("000000", "테스트", None, None)

    assert result.recommendation == "관망"
    assert result.key_reasons == ["분석 데이터 부족"]
    assert result.risk_factors == ["데이터 불충분으로 판단 불확실"]


def test_unified_market_fallback_analysis_builds_summary_and_strategy(tmp_path):
    cfg = LLMConfig(output_dir=str(tmp_path))
    analyzer = UnifiedMarketAnalyzer(config=cfg)

    etf_flows = [
        ETFFlowData(
            sector="반도체",
            etf_code="0000",
            etf_name="ETF",
            volume_5d_avg=1,
            volume_20d_avg=1,
            volume_ratio=1.2,
            price_change_5d=2.0,
            price_change_20d=3.0,
            money_flow=100.0,
            signal="강세",
        ),
        ETFFlowData(
            sector="바이오",
            etf_code="0001",
            etf_name="ETF",
            volume_5d_avg=1,
            volume_20d_avg=1,
            volume_ratio=0.8,
            price_change_5d=-1.0,
            price_change_20d=-2.0,
            money_flow=50.0,
            signal="상승",
        ),
    ]
    futures = FuturesData(
        product_name="KOSPI200",
        close_price=300.0,
        change=1.0,
        change_rate=0.5,
        volume=100,
        open_interest=200,
        basis=-0.8,
    )
    options = OptionsData(call_volume=10, put_volume=20, put_call_ratio=1.3)
    bonds = BondData(
        bond_index=100.0,
        bond_change=0.1,
        yield_3y=3.2,
        yield_10y=3.5,
        yield_spread=0.3,
        risk_mode=RiskMode.RISK_ON,
    )

    summary, strategy, key_points = analyzer._fallback_analysis(
        etf_flows, futures, options, bonds, indices=[]
    )

    assert "반도체" in summary
    assert "풋콜비율" in summary
    assert "반도체" in strategy
    assert any("베이시스" in k for k in key_points)
    assert any("리스크모드" in k for k in key_points)


def test_stock_technical_signal_scoring_strong_buy():
    analyzer = StockTechnicalAnalyzer()

    signal = analyzer._determine_signal(
        rsi=25,
        macd_hist=1.0,
        bb_pos=0.1,
        trend="상승",
        price=105,
        ma5=100,
        ma20=95,
    )

    assert signal.value == "강력매수"


def test_futures_flow_score_combines_components():
    flow_score = FuturesFlowCollector._compute_flow_score(
        basis=0.5,
        put_call=1.2,
        micro_data={"microstructure_score": 2.5},
    )

    assert flow_score == 2.5
