"""Stock screening and scoring helper functions.

Pure functions extracted from UnifiedTradingAnalyzer for screening,
filtering, and scoring stock candidates.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pandas as pd

from .data_classes import BacktestResult, Signal, StockInfo, TechnicalAnalysis

if TYPE_CHECKING:
    from .config import LLMConfig


# ------------------------------------------------------------------
# KRX 업종명 → ETF 섹터 테마 매핑
# ------------------------------------------------------------------

INDUSTRY_TO_THEME: dict[str, list[str]] = {
    "전기·전자": ["반도체"],
    "화학": ["2차전지", "에너지"],
    "제약": ["바이오"],
    "의료·정밀기기": ["바이오"],
    "기타금융": ["금융"],
    "금융": ["금융"],  # KOSDAQ 업종명
    "보험": ["금융"],
    "은행": ["금융"],
    "증권": ["금융"],
    "운송장비·부품": ["자동차"],
    "금속": ["철강"],
    "비금속": ["철강"],
    "건설": ["건설"],
    "전기·가스": ["에너지"],
    "전기·가스·수도": ["에너지"],  # KOSDAQ 업종명
    "IT 서비스": ["인터넷"],
    "오락·문화": ["게임"],
    "통신": ["인터넷"],
    "기계·장비": ["자동차", "조선"],
}


# ------------------------------------------------------------------
# Name / keyword filtering
# ------------------------------------------------------------------


def is_preferred_share(name: str) -> bool:
    """Check if the stock name indicates a preferred share."""
    normalized = name.strip()
    return (
        "우선주" in normalized
        or normalized.endswith("우")
        or normalized.endswith("우B")
        or normalized.endswith("우C")
    )


def name_exclusion_reasons(name: str, config: LLMConfig) -> list[str]:
    """Return exclusion reasons based on the stock name."""
    reasons: list[str] = []

    if config.stock_exclude_preferred_shares and is_preferred_share(name):
        reasons.append("preferred_share")

    for kw in config.stock_exclude_name_keywords:
        if kw and kw in name:
            reasons.append(f"name_keyword:{kw}")

    return reasons


def find_keyword_hits(texts: list[str], keywords: list[str]) -> list[str]:
    """Return unique keyword hits found in *texts*."""
    hits: list[str] = []
    if not keywords:
        return hits

    for t in texts:
        if not t:
            continue
        for kw in keywords:
            if kw and kw in t and kw not in hits:
                hits.append(kw)
    return hits


# ------------------------------------------------------------------
# Technical / risk metrics
# ------------------------------------------------------------------


def calc_max_drawdown(close: pd.Series) -> float:
    """Maximum drawdown as a positive fraction (0‒1)."""
    if close is None or len(close) < 2:
        return 0.0
    roll_max = close.cummax()
    drawdown = (close / roll_max) - 1.0
    return float(abs(drawdown.min())) if len(drawdown) else 0.0


def calc_atr_pct(df: pd.DataFrame, period: int = 14) -> float:
    """ATR as a fraction of the last close price."""
    if df is None or len(df) < period + 1:
        return 0.0
    high = df["고가"].astype(float)
    low = df["저가"].astype(float)
    close = df["종가"].astype(float)
    prev_close = close.shift(1)
    tr = (high - low).abs()
    tr = tr.combine((high - prev_close).abs(), max)
    tr = tr.combine((low - prev_close).abs(), max)
    atr = tr.rolling(period).mean().iloc[-1]
    last_close = close.iloc[-1]
    if pd.isna(atr) or last_close == 0:
        return 0.0
    return float(atr / last_close)


def calc_consecutive_up(returns: pd.Series) -> int:
    """Count consecutive positive returns from the tail."""
    if returns is None or len(returns) == 0:
        return 0
    count = 0
    for val in reversed(returns.dropna().tolist()):
        if val > 0:
            count += 1
        else:
            break
    return count


def calc_momentum_metrics(close: pd.Series, lookback: int) -> dict[str, float]:
    """Compute multi‑horizon return and proximity metrics."""
    metrics: dict[str, float] = {}
    if close is None or len(close) < 2:
        return metrics

    def _ret(days: int) -> float:
        if len(close) <= days:
            return 0.0
        prev = float(close.iloc[-days - 1])
        cur = float(close.iloc[-1])
        return ((cur / prev) - 1.0) * 100 if prev else 0.0

    metrics["ret_5d"] = _ret(5)
    metrics["ret_20d"] = _ret(20)
    metrics["ret_60d"] = _ret(60)

    window = close.tail(min(len(close), lookback))
    high = float(window.max()) if len(window) else 0.0
    metrics["high_lookback"] = high
    metrics["high_proximity"] = float(close.iloc[-1] / high) if high else 0.0
    return metrics


# ------------------------------------------------------------------
# Target‑price scoring
# ------------------------------------------------------------------


def score_target_price_signal(screening: dict[str, Any]) -> float:
    """Score analyst target-price signal from KIS invest-opinion."""
    if not screening.get("target_available"):
        return 0.0

    upside = float(screening.get("target_upside_pct", 0.0))
    opinion = str(screening.get("target_opinion", "")).strip().lower()
    score = 0.0

    if upside >= 30:
        score += 10
    elif upside >= 20:
        score += 8
    elif upside >= 10:
        score += 5
    elif upside >= 5:
        score += 3
    elif upside <= -20:
        score -= 10
    elif upside <= -10:
        score -= 6
    elif upside < 0:
        score -= 3

    opinion_weights = [
        ("강력매수", 2.5),
        ("매수", 1.5),
        ("buy", 1.5),
        ("비중확대", 1.2),
        ("outperform", 1.2),
        ("중립", 0.0),
        ("hold", 0.0),
        ("관망", 0.0),
        ("underperform", -1.2),
        ("비중축소", -1.2),
        ("매도", -1.5),
        ("sell", -1.5),
    ]
    for needle, weight in opinion_weights:
        if needle in opinion:
            score += weight
            break

    return max(min(score, 12.0), -12.0)


# ------------------------------------------------------------------
# Theme / sector relevance scoring
# ------------------------------------------------------------------


def score_theme_relevance(
    industry: str,
    sector_rotation: dict[str, str],
) -> tuple[float, str]:
    """Score a stock's theme relevance based on sector rotation.

    Args:
        industry: KRX 업종명 (e.g. "전기·전자", "운송·창고")
        sector_rotation: {sector: signal} from ETFFlowAnalyzer
            signal is one of: "강세", "상승", "중립", "하락", "약세"

    Returns:
        (score, matched_theme) — score in [-8, +8], matched theme name or ""
    """
    if not industry or not sector_rotation:
        return 0.0, ""

    themes = INDUSTRY_TO_THEME.get(industry, [])
    if not themes:
        # 매핑되지 않은 업종: 주도 테마와 무관하므로 소폭 감점
        return -2.0, ""

    signal_scores = {"강세": 8, "상승": 4, "중립": 0, "하락": -4, "약세": -8}

    best_score = -999.0
    best_theme = ""
    for theme in themes:
        signal = sector_rotation.get(theme, "")
        if signal in signal_scores:
            s = float(signal_scores[signal])
            if s > best_score:
                best_score = s
                best_theme = theme

    if best_score == -999.0:
        # 관련 테마가 sector_rotation에 없음
        return -1.0, ""

    return best_score, best_theme


# ------------------------------------------------------------------
# Composite candidate scoring
# ------------------------------------------------------------------


def score_stock_candidate(
    stock: StockInfo,
    tech: TechnicalAnalysis,
    best: BacktestResult | None,
    news: dict[str, Any],
    screening: dict[str, Any],
    config: LLMConfig,
) -> tuple[float, dict[str, float]]:
    """Score a stock candidate and return (total_score, breakdown)."""
    momentum = screening.get("momentum", {})
    ret_5d = float(momentum.get("ret_5d", 0.0))
    ret_20d = float(momentum.get("ret_20d", 0.0))
    ret_60d = float(momentum.get("ret_60d", 0.0))
    high_prox = float(momentum.get("high_proximity", 0.0))
    consecutive_up = int(screening.get("consecutive_up", 0))

    momentum_raw = ret_5d * 0.6 + ret_20d * 0.3 + ret_60d * 0.1
    momentum_score = max(min(momentum_raw, 20.0), -20.0)

    # (#2) 52주 고점 보너스: 모멘텀 raw가 양수면 이미 상승이 반영되어 이중 계산 방지
    if high_prox >= 0.95 and momentum_raw <= 0:
        momentum_score += 5
    elif high_prox <= 0.75:
        momentum_score -= 5
    if consecutive_up >= 3:
        momentum_score += 3

    # (#1) RSI 과매수 모멘텀 감점: 이미 과열된 종목의 모멘텀 점수 차감
    if tech.rsi > 70:
        momentum_score -= 8
    elif tech.rsi > 65:
        momentum_score -= 4

    signal_map = {
        Signal.STRONG_BUY: 12,
        Signal.BUY: 6,
        Signal.HOLD: 0,
        Signal.SELL: -6,
        Signal.STRONG_SELL: -12,
    }
    technical_score = float(signal_map.get(tech.signal, 0))

    if best is not None:
        win_rate_score = (best.win_rate - 50) * 0.6
        total_return = max(min(best.total_return, 30.0), -30.0)
        return_score = total_return * 0.4
        backtest_score = win_rate_score + return_score
        # (#3) 백테스트 거래 수 부족 시 강화된 패널티
        if best.trade_count < 10:
            backtest_score *= 0.5
        elif best.trade_count < 15:
            backtest_score *= 0.7
    else:
        backtest_score = 0.0

    sentiment = news.get("sentiment", "중립")
    news_score = 0.0
    if sentiment in ["긍정", "매우 긍정"]:
        news_score += 5
    elif sentiment in ["부정", "매우 부정"]:
        news_score -= 5

    # (#4) 뉴스 부재 페널티: 뉴스 0건이면 기관/애널리스트 관심 부족으로 감점
    news_count = int(news.get("news_count", 0))
    if news_count == 0:
        news_score -= 3

    risk_hits = screening.get("risk_keywords", [])
    if risk_hits:
        news_score -= min(len(risk_hits) * 2, 6)

    liquidity_score = 0.0
    trade_value = float(stock.trade_value or 0.0)
    min_trade_value = float(config.stock_min_trade_value)
    if trade_value >= min_trade_value * 3:
        liquidity_score += 6
    elif trade_value >= min_trade_value * 2:
        liquidity_score += 4
    elif trade_value >= min_trade_value:
        liquidity_score += 2
    else:
        liquidity_score -= 4

    turnover = float(stock.turnover or 0.0)
    min_turnover = float(config.stock_min_turnover)
    if turnover >= min_turnover * 2:
        liquidity_score += 3
    elif turnover >= min_turnover:
        liquidity_score += 1

    if stock.volume_ratio >= 2.0:
        liquidity_score += 3
    elif stock.volume_ratio >= 1.5:
        liquidity_score += 1

    target_price_score = score_target_price_signal(screening)

    # 테마/섹터 연관성 점수 (ETFFlowAnalyzer 기반)
    theme_score = float(screening.get("theme_score", 0.0))

    risk_penalty = 0.0
    atr_pct = float(screening.get("atr_pct", 0.0))
    max_dd = float(screening.get("max_drawdown_pct", 0.0))
    volatility = float(screening.get("volatility", 0.0))

    # Graduated ATR penalty (soft filter: extreme values heavily penalized)
    max_atr = float(config.stock_max_atr_pct)
    if atr_pct >= max_atr * 1.5:
        risk_penalty += 15
    elif atr_pct >= max_atr:
        risk_penalty += 8
    elif atr_pct >= max_atr * 0.8:
        risk_penalty += 3

    # Graduated drawdown penalty (soft filter)
    max_drawdown = float(config.stock_max_drawdown_pct)
    if max_dd >= max_drawdown * 1.5:
        risk_penalty += 15
    elif max_dd >= max_drawdown:
        risk_penalty += 8
    elif max_dd >= max_drawdown * 0.8:
        risk_penalty += 3

    if volatility >= 0.8:
        risk_penalty += 6
    elif volatility >= 0.6:
        risk_penalty += 3

    weights = {
        "momentum": config.stock_score_weight_momentum,
        "technical": config.stock_score_weight_technical,
        "backtest": config.stock_score_weight_backtest,
        "news": config.stock_score_weight_news,
        "liquidity": config.stock_score_weight_liquidity,
        "target_price": config.stock_score_weight_target_price,
        "theme": config.stock_score_weight_theme,
        "risk": config.stock_score_weight_risk,
    }

    total_score = (
        momentum_score * weights["momentum"]
        + technical_score * weights["technical"]
        + backtest_score * weights["backtest"]
        + news_score * weights["news"]
        + liquidity_score * weights["liquidity"]
        + target_price_score * weights["target_price"]
        + theme_score * weights["theme"]
        - risk_penalty * weights["risk"]
    )

    if screening.get("is_new_listing"):
        total_score *= config.stock_new_listing_penalty

    breakdown = {
        "momentum": momentum_score,
        "technical": technical_score,
        "backtest": backtest_score,
        "news": news_score,
        "liquidity": liquidity_score,
        "target_price": target_price_score,
        "theme": theme_score,
        "theme_matched": str(screening.get("theme_matched", "")),
        "risk_penalty": risk_penalty,
        "is_new_listing": screening.get("is_new_listing", False),
        "total": total_score,
    }

    return total_score, breakdown
