"""External source and news helpers for stock analysis."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from .data_classes import StockInfo
from .llm_scoring import collect_target_price_signal
from .scored_news import summarize_scored_news_sentiment

if TYPE_CHECKING:
    from .unified_trading_analyzer import UnifiedTradingAnalyzer

logger = logging.getLogger("shared.llm.stock_analysis")


def _collect_mk_news(
    analyzer: UnifiedTradingAnalyzer,
    stock: StockInfo,
    intraday: bool,
) -> dict[str, Any]:
    mk_news: dict[str, Any] = {}
    try:
        mk_news = analyzer.mk_news_collector.collect(stock.code)
        if intraday:
            # Intraday mode keeps only per-symbol headlines for lower latency and
            # to avoid repeatedly scoring the same market headlines each symbol.
            stock_news = mk_news.get("stock_news", [])
            mk_news = {
                "market_news": [],
                "stock_news": stock_news,
                "analysis": [],
                "theme_news": [],
            }
            all_news = stock_news
        else:
            all_news = mk_news.get("market_news", []) + mk_news.get("stock_news", [])
        mk_news["sentiment"] = analyzer.mk_news_collector.analyze_sentiment(
            all_news
        ).value
    except Exception as e:
        logger.debug(f"MK news failed for {stock.code}: {e}")
    return mk_news


def _collect_dart_data(
    analyzer: UnifiedTradingAnalyzer,
    stock: StockInfo,
    intraday: bool,
) -> dict[str, Any]:
    dart_data: dict[str, Any] = {}
    if intraday:
        return dart_data
    try:
        corp_code = analyzer._dart_corp_mapper.get_corp_code(stock.code)
        dart_data = (
            analyzer.dart_collector.collect(corp_code)
            if corp_code
            else {"error": "corp_code_not_found"}
        )
    except Exception as e:
        logger.debug(f"DART data failed for {stock.code}: {e}")
    return dart_data


def _collect_ksd_data(
    analyzer: UnifiedTradingAnalyzer,
    stock: StockInfo,
    intraday: bool,
) -> dict[str, Any]:
    ksd_data: dict[str, Any] = {}
    if intraday:
        return ksd_data
    try:
        ksd_data = analyzer.ksd_collector.collect(stock.code)
    except Exception as e:
        logger.debug(f"KSD data failed for {stock.code}: {e}")
    return ksd_data


def _collect_krx_stock_info(
    analyzer: UnifiedTradingAnalyzer,
    stock: StockInfo,
) -> dict[str, Any]:
    try:
        return analyzer.krx_collector.get_stock_info(stock.code) or {}
    except Exception as e:
        logger.debug(f"KRX stock info failed for {stock.code}: {e}")
        return {}


def _build_texts_to_scan(
    stock: StockInfo,
    mk_news: dict[str, Any],
    krx_stock_info: dict[str, Any],
    dart_data: dict[str, Any],
    scored_news: list[dict[str, Any]] | None = None,
) -> list[str]:
    texts_to_scan: list[str] = [stock.name]
    texts_to_scan.extend([n.get("title", "") for n in mk_news.get("stock_news", [])])
    texts_to_scan.extend([n.get("title", "") for n in mk_news.get("market_news", [])])
    texts_to_scan.append(json.dumps(krx_stock_info, ensure_ascii=False, default=str))
    if dart_data.get("recent_disclosures"):
        texts_to_scan.extend(
            [d.get("report_nm", "") for d in dart_data.get("recent_disclosures", [])]
        )
    for item in scored_news or []:
        texts_to_scan.append(str(item.get("title", "")))
        texts_to_scan.append(str(item.get("reasoning", "")))
    return texts_to_scan


def _build_news_payload(
    analyzer: UnifiedTradingAnalyzer,
    stock: StockInfo,
    mk_news: dict[str, Any],
    intraday: bool,
    scored_news: list[dict[str, Any]] | None,
    config,
) -> dict[str, Any]:
    scored_items = list(scored_news or [])[
        : max(1, int(getattr(config, "stock_scored_news_max_per_stock", 3)))
    ]
    if intraday:
        mk_news_count = len(mk_news.get("market_news", [])) + len(
            mk_news.get("stock_news", [])
        )
        payload: dict[str, Any] = {
            "sentiment": mk_news.get("sentiment", "중립"),
            "news_count": mk_news_count + len(scored_items),
        }
        if mk_news.get("stock_news"):
            payload["mk_headlines"] = [
                n.get("title") for n in mk_news["stock_news"][:3]
            ]
        return _attach_scored_news_payload(payload, scored_items, config)

    news = analyzer.stock_news_analyzer.analyze(stock.code, stock.name)
    if mk_news.get("sentiment"):
        news["sentiment"] = mk_news["sentiment"]
    if mk_news.get("stock_news"):
        news["mk_headlines"] = [n.get("title") for n in mk_news["stock_news"][:3]]
    mk_news_count = len(mk_news.get("market_news", [])) + len(
        mk_news.get("stock_news", [])
    )
    news["news_count"] = mk_news_count + len(scored_items)
    return _attach_scored_news_payload(news, scored_items, config)


def _attach_scored_news_payload(
    payload: dict[str, Any],
    scored_news: list[dict[str, Any]],
    config,
) -> dict[str, Any]:
    if not scored_news:
        return payload

    compact_items = [_compact_scored_news_item(item) for item in scored_news]
    payload["marketaux_scored_news"] = compact_items
    payload["scored_news_headlines"] = [
        item["title"] for item in compact_items if item.get("title")
    ]
    if payload.get("sentiment", "중립") == "중립":
        payload["sentiment"] = summarize_scored_news_sentiment(scored_news, config)
    return payload


def _compact_scored_news_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "news_id": item.get("news_id", ""),
        "source": item.get("source", item.get("raw_source", "")),
        "title": item.get("title", ""),
        "url": item.get("url", ""),
        "category": item.get("category", ""),
        "sentiment": item.get("sentiment", 0.0),
        "impact_score": item.get("impact_score", 0.0),
        "direction_bias": item.get("direction_bias", ""),
        "confidence": item.get("confidence", 0.0),
        "keywords": list(item.get("keywords", []))[:5],
        "raw_keywords": list(item.get("raw_keywords", []))[:5],
        "reasoning": item.get("reasoning", ""),
    }


async def _build_target_signal(
    analyzer: UnifiedTradingAnalyzer,
    stock: StockInfo,
    intraday: bool,
) -> dict[str, Any]:
    if intraday:
        return {
            "available": False,
            "target_price": 0.0,
            "latest_target_price": 0.0,
            "latest_target_upside_pct": 0.0,
            "target_upside_pct": 0.0,
            "target_opinion": "",
            "target_date": "",
            "target_latest_broker": "",
            "target_sample_count": 0,
            "target_coverage_count": 0,
            "target_dispersion_pct": 0.0,
            "target_revision_30d_pct": 0.0,
            "target_revision_direction": "",
            "target_staleness_days": 0,
            "target_opinion_distribution": {},
            "target_recent_reports": [],
        }
    return await collect_target_price_signal(
        analyzer, stock.code, current_price=float(stock.price)
    )
