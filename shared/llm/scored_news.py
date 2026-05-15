"""Join LLM-scored news stream entries to stock candidates."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from shared.streaming.client import RedisClient

from .data_classes import StockInfo

logger = logging.getLogger(__name__)


def collect_scored_news_for_stocks(
    stocks: list[StockInfo],
    config: Any,
    *,
    redis_client: Any | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Load recent scored news once and group matching Marketaux items by stock."""
    if not bool(getattr(config, "stock_scored_news_enabled", True)):
        return {}
    if not stocks:
        return {}

    try:
        client = redis_client or RedisClient.get_client()
        stream = str(getattr(config, "stock_scored_news_stream", "stream:news.scored"))
        max_entries = max(1, int(getattr(config, "stock_scored_news_max_entries", 500)))
        raw_entries = client.xrevrange(stream, max="+", min="-", count=max_entries)
    except Exception as exc:
        logger.debug("Scored news fetch failed: %s", exc)
        return {}

    parsed_items = [
        item
        for _msg_id, fields in raw_entries
        if (item := _parse_scored_news_fields(fields)) is not None
    ]
    eligible = _filter_scored_news(parsed_items, config)
    grouped: dict[str, list[dict[str, Any]]] = {stock.code: [] for stock in stocks}

    for item in eligible:
        for stock in stocks:
            if _matches_stock(item, stock):
                grouped[stock.code].append(item)

    per_stock = max(1, int(getattr(config, "stock_scored_news_max_per_stock", 3)))
    return {
        code: sorted(items, key=_sort_key, reverse=True)[:per_stock]
        for code, items in grouped.items()
        if items
    }


def summarize_scored_news_sentiment(
    scored_news: list[dict[str, Any]],
    config: Any,
) -> str:
    """Convert matched scored news sentiment into the existing Korean labels."""
    if not scored_news:
        return "중립"
    weighted_sum = 0.0
    weight_total = 0.0
    for item in scored_news:
        weight = max(float(item.get("impact_score", 0.0) or 0.0), 0.05)
        weight *= max(float(item.get("confidence", 0.0) or 0.0), 0.25)
        weighted_sum += float(item.get("sentiment", 0.0) or 0.0) * weight
        weight_total += weight
    if weight_total <= 0:
        return "중립"

    avg = weighted_sum / weight_total
    positive = float(
        getattr(config, "stock_scored_news_positive_sentiment_threshold", 0.2)
    )
    negative = float(
        getattr(config, "stock_scored_news_negative_sentiment_threshold", -0.2)
    )
    if avg >= positive:
        return "긍정"
    if avg <= negative:
        return "부정"
    return "중립"


def _filter_scored_news(
    items: list[dict[str, Any]],
    config: Any,
) -> list[dict[str, Any]]:
    sources = {
        str(source).strip().lower()
        for source in getattr(config, "stock_scored_news_sources", ["marketaux"])
        if str(source).strip()
    }
    lookback_ms = (
        max(0, int(getattr(config, "stock_scored_news_lookback_seconds", 86400))) * 1000
    )
    min_impact = float(getattr(config, "stock_scored_news_min_impact_score", 0.1))
    now_ms = int(time.time() * 1000)

    filtered: list[dict[str, Any]] = []
    for item in items:
        raw_source = str(item.get("raw_source", "")).lower()
        if sources and raw_source not in sources:
            continue
        if float(item.get("impact_score", 0.0) or 0.0) < min_impact:
            continue
        published_ms = int(item.get("published_at_ms", 0) or 0)
        if lookback_ms and published_ms and now_ms - published_ms > lookback_ms:
            continue
        filtered.append(item)
    return filtered


def _parse_scored_news_fields(fields: dict[Any, Any]) -> dict[str, Any] | None:
    def _s(key: str, default: str = "") -> str:
        value = fields.get(key)
        if value is None:
            value = fields.get(key.encode())
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        if value is None:
            return default
        return str(value)

    news_id = _s("news_id").strip()
    if not news_id:
        return None
    raw_source = _s("raw_source").strip().lower()
    if not raw_source and news_id.startswith("marketaux_"):
        raw_source = "marketaux"

    raw_keywords = _json_list(_s("raw_keywords_json", "[]"))
    keywords = _json_list(_s("keywords_json", "[]"))
    published_at_ms = _to_int(_s("raw_published_at_ms", "0"))
    if published_at_ms <= 0:
        published_at_ms = _to_int(_s("scored_at_ms", "0"))
    return {
        "news_id": news_id,
        "source": _s("raw_source") or raw_source,
        "raw_source": raw_source,
        "title": _s("raw_title").strip(),
        "url": _s("raw_url").strip(),
        "published_at_ms": published_at_ms,
        "category": _s("category").strip(),
        "sentiment": _to_float(_s("sentiment", "0")),
        "impact_score": _to_float(_s("impact_score", "0")),
        "direction_bias": _s("direction_bias").strip(),
        "confidence": _to_float(_s("confidence", "0")),
        "keywords": keywords,
        "raw_keywords": raw_keywords,
        "reasoning": _s("reasoning").strip(),
    }


def _matches_stock(item: dict[str, Any], stock: StockInfo) -> bool:
    aliases = _stock_aliases(stock)
    searchable_values = [
        item.get("title", ""),
        item.get("reasoning", ""),
        *item.get("keywords", []),
        *item.get("raw_keywords", []),
    ]
    searchable = " ".join(str(value) for value in searchable_values if value)
    searchable_lower = searchable.lower()
    searchable_compact = searchable_lower.replace(" ", "")
    return any(
        alias in searchable_lower or alias.replace(" ", "") in searchable_compact
        for alias in aliases
    )


def _stock_aliases(stock: StockInfo) -> set[str]:
    code = str(stock.code).strip()
    name = str(stock.name).strip().lower()
    aliases = {
        code.lower(),
        f"{code}.ks".lower(),
        f"{code}.kq".lower(),
        f"krx:{code}".lower(),
    }
    if name:
        aliases.add(name)
        aliases.add(name.replace(" ", ""))
    return {alias for alias in aliases if alias}


def _json_list(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item).strip() for item in parsed if str(item).strip()]


def _to_float(raw: str) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _to_int(raw: str) -> int:
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return 0


def _sort_key(item: dict[str, Any]) -> tuple[float, float, int]:
    return (
        float(item.get("impact_score", 0.0) or 0.0),
        float(item.get("confidence", 0.0) or 0.0),
        int(item.get("published_at_ms", 0) or 0),
    )
