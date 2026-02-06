"""
LLM 분석 데이터 클래스
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, List


# ============================================================
# Enums
# ============================================================


class MarketBias(Enum):
    """시장 방향성"""

    STRONG_BULLISH = "강세"
    BULLISH = "약간 강세"
    NEUTRAL = "중립"
    BEARISH = "약간 약세"
    STRONG_BEARISH = "약세"


class Signal(Enum):
    """매매 신호"""

    STRONG_BUY = "강력매수"
    BUY = "매수"
    HOLD = "관망"
    SELL = "매도"
    STRONG_SELL = "강력매도"


class NewsSentiment(Enum):
    """뉴스 감성"""

    VERY_POSITIVE = "매우 긍정"
    POSITIVE = "긍정"
    NEUTRAL = "중립"
    NEGATIVE = "부정"
    VERY_NEGATIVE = "매우 부정"


class MarketSignal(Enum):
    """시장 신호 (KRX 분석용)"""

    STRONG_BULLISH = "강한 상승"
    BULLISH = "상승"
    NEUTRAL = "중립"
    BEARISH = "하락"
    STRONG_BEARISH = "강한 하락"


class RiskMode(Enum):
    """리스크 모드"""

    RISK_ON = "위험선호"
    NEUTRAL = "중립"
    RISK_OFF = "위험회피"


# ============================================================
# KRX API Data Classes
# ============================================================


@dataclass
class ETFData:
    """KRX API ETF 데이터"""

    code: str
    name: str
    close_price: float
    change_rate: float
    volume: int
    trade_value: float  # 거래대금
    sector: str = ""


@dataclass
class ETFFlowData:
    """ETF 자금흐름 데이터 (FinanceDataReader)"""

    sector: str
    etf_code: str
    etf_name: str
    volume_5d_avg: float
    volume_20d_avg: float
    volume_ratio: float  # 5일/20일 비율
    price_change_5d: float  # 5일 수익률
    price_change_20d: float  # 20일 수익률
    money_flow: float  # 추정 자금유입 (거래대금)
    signal: str  # 강세/약세/중립


@dataclass
class FuturesData:
    """선물 데이터"""

    product_name: str
    close_price: float
    change: float
    change_rate: float
    volume: int
    open_interest: int
    basis: float = 0.0


@dataclass
class OptionsData:
    """옵션 데이터"""

    call_volume: int
    put_volume: int
    put_call_ratio: float
    call_oi: int = 0
    put_oi: int = 0
    pcr_5d_avg: float = 0.0
    implied_vol: float = 0.0
    iv_percentile: float = 0.0
    signal: str = ""  # 과매수/과매도/중립


@dataclass
class BondData:
    """채권 시장 데이터"""

    bond_index: float  # 채권지수
    bond_change: float
    yield_3y: float  # 국고채 3년
    yield_10y: float  # 국고채 10년
    yield_spread: float  # 장단기 스프레드
    risk_mode: RiskMode = RiskMode.NEUTRAL


@dataclass
class BondIndexData:
    """KRX 채권지수 데이터"""

    index_name: str
    index_value: float
    change: float
    change_rate: float


@dataclass
class IndexData:
    """지수 데이터 (확장)"""

    name: str
    price: float
    change_1d: float = 0.0
    change_5d: float = 0.0
    change_20d: float = 0.0
    change_rate: float = 0.0
    volume: int = 0
    volume_ratio: float = 0.0
    trade_value: float = 0.0
    rsi: float = 50.0
    trend: str = ""


@dataclass
class MarketAnalysis:
    """종합 시장 분석 결과"""

    date: str

    # 각 분석 결과
    etf_flows: List["ETFFlowData"] = field(default_factory=list)
    futures: "FuturesData" = None
    options: "OptionsData" = None
    bonds: "BondData" = None
    indices: List["IndexData"] = field(default_factory=list)

    # 종합 판단
    overall_signal: MarketSignal = MarketSignal.NEUTRAL
    risk_mode: RiskMode = RiskMode.NEUTRAL
    sector_rotation: Dict[str, str] = field(default_factory=dict)  # 섹터별 강세/약세

    # LLM 분석
    llm_summary: str = ""
    llm_strategy: str = ""
    key_points: List[str] = field(default_factory=list)


# ============================================================
# Analysis Data Classes
# ============================================================


@dataclass
class TechnicalAnalysis:
    """기술적 분석 결과"""

    rsi: float
    macd: float
    macd_signal: float
    macd_hist: float
    bb_position: float
    ma5: float
    ma20: float
    ma60: float
    trend: str
    signal: Signal


@dataclass
class BacktestResult:
    """백테스트 결과"""

    strategy_name: str
    total_return: float
    win_rate: float
    max_drawdown: float
    sharpe_ratio: float
    trade_count: int
    avg_profit: float
    avg_loss: float


@dataclass
class StockInfo:
    """종목 정보"""

    code: str
    name: str
    price: float
    change_pct: float
    volume: int
    volume_ratio: float
    market_cap: float
    sector: str = ""


# ============================================================
# Market Data Classes
# ============================================================


@dataclass
class GlobalMarketData:
    """글로벌 시장 데이터"""

    # Index values
    sp500: float = 0.0
    nasdaq: float = 0.0
    nikkei: float = 0.0
    shanghai: float = 0.0

    # Change percentages
    sp500_change_pct: float = 0.0
    nasdaq_change_pct: float = 0.0
    nikkei_change_pct: float = 0.0
    shanghai_change_pct: float = 0.0

    # Other indicators
    vix: float = 0.0
    wti: float = 0.0
    gold: float = 0.0
    dxy: float = 0.0
    usd_krw: float = 0.0

    # Computed
    global_score: float = 0.0
    global_bias: MarketBias = MarketBias.NEUTRAL

    # Legacy fields (backwards compatibility)
    sp500_futures: float = 0.0
    nasdaq_futures: float = 0.0
    vix_change: float = 0.0
    usd_krw_change: float = 0.0
    china_change_pct: float = 0.0
    japan_change_pct: float = 0.0


@dataclass
class FlowData:
    """수급 데이터"""

    # Current positions
    foreign_futures: float | None = None
    institution_futures: float | None = None
    retail_futures: float | None = None

    # 5-day cumulative
    foreign_futures_5d: float | None = None
    institution_futures_5d: float | None = None

    # Market indicators
    basis: float | None = None
    put_call_ratio: float | None = None

    # Microstructure proxy (orderbook/trades)
    orderbook_imbalance: float | None = None
    ofi_zscore: float | None = None
    aggressor_ratio: float | None = None
    aggressor_balance: float | None = None
    oi_change: float | None = None
    price_change: float | None = None
    microstructure_score: float | None = None

    # Computed
    flow_score: float = 0.0
    flow_bias: MarketBias = MarketBias.NEUTRAL

    # Legacy fields (backwards compatibility)
    foreign_futures_net: float | None = None
    institution_futures_net: float | None = None
    retail_futures_net: float | None = None
    basis_rate: float | None = None


@dataclass
class EconomicEvent:
    """경제 이벤트"""

    date: str
    time: str
    country: str
    event: str
    importance: str
    impact_analysis: str = ""


# ============================================================
# Trading Plan Data Classes
# ============================================================


@dataclass
class AnalysisResult:
    """LLM 분석 결과 (Legacy Compatible)"""

    code: str
    name: str
    overall_score: int  # -100 ~ +100
    recommendation: str  # "강력매수", "매수", "관망", "매도", "강력매도"
    confidence: str  # "높음", "중간", "낮음"
    key_reasons: List[str]  # 주요 매매 근거
    risk_factors: List[str]  # 리스크 요인
    entry_strategy: str  # 진입 전략
    exit_strategy: str  # 손절/익절 전략
    position_size: float  # 추천 포지션 비중 (0~1)
    time_horizon: str  # "단기(1-3일)", "중기(1-2주)"

    def as_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

    def to_telegram_message(self) -> str:
        """텔레그램 알림용 메시지 생성"""
        emoji = {
            "강력매수": "🟢🟢",
            "매수": "🟢",
            "관망": "⚪",
            "매도": "🔴",
            "강력매도": "🔴🔴",
        }.get(self.recommendation, "⚪")

        reasons_text = "\n".join(f"  • {r}" for r in self.key_reasons[:3])
        risks_text = "\n".join(f"  • {r}" for r in self.risk_factors[:2])

        return f"""
{emoji} <b>AI 분석: {self.name} ({self.code})</b>
━━━━━━━━━━━━━━━━━━━━
<b>추천:</b> {self.recommendation} (점수: {self.overall_score:+d})
<b>신뢰도:</b> {self.confidence}
<b>포지션:</b> {self.position_size*100:.0f}%
<b>기간:</b> {self.time_horizon}

<b>📈 매매 근거:</b>
{reasons_text}

<b>⚠️ 리스크:</b>
{risks_text}

<b>진입:</b> {self.entry_strategy}
<b>청산:</b> {self.exit_strategy}
━━━━━━━━━━━━━━━━━━━━
"""


@dataclass
class StockTradingPlan:
    """주식 매매 계획"""

    code: str
    name: str
    strategy: str
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size: float
    confidence: str
    reasons: List[str]
    news_sentiment: str = ""
    key_events: List[str] = field(default_factory=list)

    def to_telegram_message(self) -> str:
        """텔레그램 메시지 변환"""
        reasons_text = "\n".join(f"  • {r}" for r in self.reasons[:4])
        return f"""
📈 <b>{self.name} ({self.code})</b>
━━━━━━━━━━━━━━━━━━━━
<b>전략:</b> {self.strategy}
<b>진입가:</b> {self.entry_price:,.0f}원
<b>손절가:</b> {self.stop_loss:,.0f}원 ({(self.stop_loss/self.entry_price-1)*100:.1f}%)
<b>익절가:</b> {self.take_profit:,.0f}원 (+{(self.take_profit/self.entry_price-1)*100:.1f}%)
<b>포지션:</b> {self.position_size*100:.0f}%
<b>신뢰도:</b> {self.confidence}

<b>📊 매매 근거:</b>
{reasons_text}
━━━━━━━━━━━━━━━━━━━━
"""


@dataclass
class FuturesTradingPlan:
    """선물 매매 계획"""

    direction: str  # "롱", "숏", "관망"
    confidence: str
    entry_condition: str
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size: str
    time_horizon: str
    key_levels: List[float] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)
    catalysts: List[str] = field(default_factory=list)

    def to_telegram_message(self) -> str:
        """텔레그램 메시지 변환"""
        emoji = "📈" if self.direction == "롱" else "📉" if self.direction == "숏" else "⏸️"
        catalysts_text = "\n".join(f"  • {c}" for c in self.catalysts[:3])
        risks_text = "\n".join(f"  ⚠️ {r}" for r in self.risk_factors[:3])

        return f"""
{emoji} <b>선물 브리핑: {self.direction}</b>
━━━━━━━━━━━━━━━━━━━━
<b>신뢰도:</b> {self.confidence}
<b>진입조건:</b> {self.entry_condition}
<b>예상진입:</b> {self.entry_price:.2f}
<b>손절:</b> {self.stop_loss:.2f}
<b>익절:</b> {self.take_profit:.2f}
<b>포지션:</b> {self.position_size}
<b>보유기간:</b> {self.time_horizon}

<b>상승 촉매:</b>
{catalysts_text}

<b>리스크:</b>
{risks_text}
━━━━━━━━━━━━━━━━━━━━
"""


@dataclass
class StockDetailedBriefing:
    """종목 상세 브리핑"""

    # 기본 정보
    code: str
    name: str
    generated_at: str

    # 가격 정보
    current_price: float
    change_pct: float
    market_cap: float
    volume: int
    volume_ratio: float

    # 기술적 분석
    rsi: float
    macd_hist: float
    bb_position: float
    trend: str
    ma5: float
    ma20: float
    ma60: float
    tech_signal: str

    # 백테스트 결과
    best_strategy: str
    backtest_win_rate: float
    backtest_return: float
    backtest_trades: int
    backtest_max_drawdown: float

    # 매매 계획
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size: float
    confidence: str
    time_horizon: str

    # 선정 이유
    selection_reasons: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)

    # 데이터 소스 정보
    news_sentiment: str = "중립"
    news_headlines: List[str] = field(default_factory=list)
    dart_disclosures: List[str] = field(default_factory=list)
    short_selling_status: str = ""
    investor_trend: str = ""

    def to_telegram_message(self) -> str:
        """텔레그램 상세 브리핑 메시지"""
        if self.confidence == "높음":
            conf_emoji = "🟢"
        elif self.confidence == "중간":
            conf_emoji = "🟡"
        else:
            conf_emoji = "🔴"

        trend_emoji = "📈" if self.trend == "상승" else "📉" if self.trend == "하락" else "➡️"
        reasons_text = "\n".join(f"  • {r}" for r in self.selection_reasons[:4])
        risks_text = "\n".join(f"  ⚠️ {r}" for r in self.risk_factors[:2])

        news_text = ""
        if self.news_headlines:
            news_items = [
                f"  • {n[:35]}..." if len(n) > 35 else f"  • {n}"
                for n in self.news_headlines[:3]
            ]
            news_text = "\n".join(news_items)

        return f"""
📋 <b>상세 브리핑: {self.name} ({self.code})</b>
━━━━━━━━━━━━━━━━━━━━

<b>💰 가격 정보</b>
현재가: {self.current_price:,.0f}원 ({self.change_pct:+.1f}%)
시가총액: {self.market_cap / 1_000_000_000_000:.1f}조
거래량: {self.volume_ratio:.1f}배 (평균대비)

<b>📊 기술적 분석</b>
{trend_emoji} 추세: {self.trend}
RSI: {self.rsi:.0f} {'⚡과매도' if self.rsi < 30 else '⚡과매수' if self.rsi > 70 else ''}
MACD: {'🔺상승' if self.macd_hist > 0 else '🔻하락'}
신호: {self.tech_signal}

<b>📈 백테스트 ({self.best_strategy})</b>
승률: {self.backtest_win_rate:.1f}% | 수익: {self.backtest_return:+.1f}%
거래: {self.backtest_trades}회 | MDD: {self.backtest_max_drawdown:.1f}%

<b>🎯 매매 계획</b>
진입: {self.entry_price:,.0f}원
손절: {self.stop_loss:,.0f}원 ({(self.stop_loss/self.entry_price-1)*100:.1f}%)
익절: {self.take_profit:,.0f}원 (+{(self.take_profit/self.entry_price-1)*100:.1f}%)
포지션: {self.position_size*100:.0f}%
{conf_emoji} 신뢰도: {self.confidence}

<b>✅ 선정 이유</b>
{reasons_text}

<b>⚠️ 리스크</b>
{risks_text}

<b>📰 뉴스 ({self.news_sentiment})</b>
{news_text if news_text else '  관련 뉴스 없음'}
━━━━━━━━━━━━━━━━━━━━
<i>생성: {self.generated_at}</i>
"""

    def to_dict(self) -> Dict:
        """JSON 직렬화용 딕셔너리"""
        return asdict(self)
