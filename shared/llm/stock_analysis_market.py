"""Market-data preparation helpers for stock analysis."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from .data_classes import StockInfo
from .stock_screening import name_exclusion_reasons

if TYPE_CHECKING:
    from .unified_trading_analyzer import UnifiedTradingAnalyzer

logger = logging.getLogger("shared.llm.stock_analysis")


def _collect_market_frames(
    analyzer: UnifiedTradingAnalyzer,
) -> tuple[list[pd.DataFrame], list[str]]:
    market_kospi = analyzer.stock_collector.collect("KOSPI")
    market_kosdaq = analyzer.stock_collector.collect("KOSDAQ")
    frames: list[pd.DataFrame] = []
    markets: list[str] = []
    if market_kospi is not None and len(market_kospi) > 0:
        frames.append(market_kospi)
        markets.append("KOSPI")
    if market_kosdaq is not None and len(market_kosdaq) > 0:
        frames.append(market_kosdaq)
        markets.append("KOSDAQ")
    return frames, markets


def _merge_market_frames(
    frames: list[pd.DataFrame],
) -> pd.DataFrame | None:
    if not frames:
        return None
    if len(frames) == 1:
        return frames[0]
    return pd.concat(frames, axis=0)


def _analysis_status(
    status: str,
    reason: str,
    *,
    detail: Any | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": status,
        "reason": reason,
    }
    if detail is not None:
        payload["detail"] = detail
    return payload


def _analysis_failure_meta(reason: str, detail: Any | None = None) -> dict[str, Any]:
    error_reason = reason if detail is None else f"{reason}:{detail}"
    return {
        "_analysis_status": _analysis_status("failed", reason, detail=detail),
        "_excluded": {"_error": [error_reason]},
        "_excluded_features": {},
    }


def _prepare_market_df(
    market_df: pd.DataFrame,
) -> tuple[pd.DataFrame | None, bool, dict | None]:
    if market_df is None or len(market_df) == 0:
        logger.error("Failed to collect market data")
        return None, False, _analysis_failure_meta("market_data_unavailable")

    required_cols = ["종가", "시가", "거래량", "시가총액"]
    missing_cols = [c for c in required_cols if c not in market_df.columns]
    if missing_cols:
        logger.error(f"Market data missing columns: {missing_cols}")
        return (
            None,
            False,
            _analysis_failure_meta(
                "market_data_missing_columns",
                ",".join(missing_cols),
            ),
        )

    trade_value_fallback = False
    if "거래대금" not in market_df.columns:
        trade_value_fallback = True
        market_df = market_df.copy()
        market_df["거래대금"] = market_df["종가"] * market_df["거래량"]

    market_df["거래대금"] = pd.to_numeric(market_df["거래대금"], errors="coerce")
    market_df["시가총액"] = pd.to_numeric(market_df["시가총액"], errors="coerce")
    market_df["거래량"] = pd.to_numeric(market_df["거래량"], errors="coerce")
    market_df = market_df.dropna(
        subset=["거래대금", "시가총액", "거래량", "종가", "시가"]
    )
    return market_df, trade_value_fallback, None


def _filter_market_df(
    market_df: pd.DataFrame,
    config,
) -> pd.DataFrame:
    filtered = market_df[
        (market_df["종가"] >= config.stock_min_price)
        & (market_df["시가총액"] >= config.stock_min_market_cap)
        & (market_df["시가총액"] <= config.stock_max_market_cap)
        & (market_df["거래대금"] >= config.stock_min_trade_value)
    ].copy()

    filtered["거래대금비율"] = filtered["거래대금"] / filtered["시가총액"].replace(
        0, np.nan
    )
    filtered = filtered[filtered["거래대금비율"] >= config.stock_min_turnover]
    filtered["등락률"] = (filtered["종가"] - filtered["시가"]) / filtered["시가"] * 100
    return filtered


def _load_sector_theme_data(
    analyzer: UnifiedTradingAnalyzer,
    markets: list[str],
) -> tuple[dict[str, str], dict[str, str]]:
    sector_classifications: dict[str, str] = {}
    sector_rotation: dict[str, str] = {}
    try:
        from .market_analyzers import ETFFlowAnalyzer

        etf_flows = ETFFlowAnalyzer(analyzer.config).analyze()
        sector_rotation = {e.sector: e.signal for e in etf_flows}
        logger.info(
            f"Theme data loaded: {len(sector_classifications)} stocks, "
            f"{len(sector_rotation)} sector signals"
        )
    except Exception as e:
        logger.warning(f"Theme/sector data collection failed (scoring disabled): {e}")
    return sector_classifications, sector_rotation


def _collect_krx_market_data(analyzer: UnifiedTradingAnalyzer) -> dict[str, Any]:
    krx_data: dict[str, Any] = {}
    try:
        krx_data = analyzer.krx_collector.collect()
        logger.info("KRX investor/program trading data collected")
    except Exception as e:
        logger.warning(f"KRX data collection failed: {e}")
    return krx_data


def _build_screened_stocks(
    analyzer: UnifiedTradingAnalyzer,
    top_volume: pd.DataFrame,
    config,
) -> tuple[list[StockInfo], dict[str, list[str]], dict[str, dict[str, Any]]]:
    stocks: list[StockInfo] = []
    excluded: dict[str, list[str]] = {}
    excluded_features: dict[str, dict[str, Any]] = {}
    for code in top_volume.index:
        row = top_volume.loc[code]
        name = analyzer.stock_collector.get_stock_name(code)
        name_exclusions = name_exclusion_reasons(name, config)
        if name_exclusions:
            excluded[code] = name_exclusions
            excluded_features[code] = {
                "price": float(row.get("종가", 0)),
                "change_pct": float(row.get("등락률", 0)),
                "volume": float(row.get("거래량", 0)),
                "market_cap": float(row.get("시가총액", 0)),
                "trade_value": float(row.get("거래대금", 0)),
                "turnover": float(row.get("거래대금비율", 0)),
            }
            continue
        stocks.append(
            StockInfo(
                code=code,
                name=name,
                price=row["종가"],
                change_pct=round(row["등락률"], 2),
                volume=int(row["거래량"]),
                volume_ratio=1.0,
                market_cap=row["시가총액"],
                trade_value=float(row.get("거래대금", 0.0)),
                turnover=float(row.get("거래대금비율", 0.0)),
            )
        )
    return stocks, excluded, excluded_features


def _compute_liquidity_metrics(
    df: pd.DataFrame,
    stock: StockInfo,
    config,
) -> tuple[float, float]:
    lookback = max(1, int(config.stock_volume_lookback_days))
    vol_window = df["거래량"].tail(lookback + 1)
    avg_volume = (
        float(vol_window.iloc[:-1].mean())
        if len(vol_window) > 1
        else float(vol_window.mean())
    )
    stock.volume_ratio = round(
        (stock.volume / avg_volume) if avg_volume > 0 else 1.0, 2
    )

    trade_window = df["거래대금"].tail(lookback + 1)
    avg_trade_value = (
        float(trade_window.iloc[:-1].mean())
        if len(trade_window) > 1
        else float(trade_window.mean())
    )
    return avg_volume, avg_trade_value
