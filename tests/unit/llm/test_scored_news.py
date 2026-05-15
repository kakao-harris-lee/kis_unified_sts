import json
import time

from shared.llm.data_classes import StockInfo
from shared.llm.scored_news import (
    collect_scored_news_for_stocks,
    summarize_scored_news_sentiment,
)


class _FakeRedis:
    def __init__(self, entries):
        self._entries = entries

    def xrevrange(self, stream, max="+", min="-", count=500):  # noqa: A002
        return self._entries[:count]


class _Config:
    stock_scored_news_enabled = True
    stock_scored_news_stream = "stream:news.scored"
    stock_scored_news_sources = ["marketaux"]
    stock_scored_news_lookback_seconds = 86400
    stock_scored_news_max_entries = 100
    stock_scored_news_max_per_stock = 2
    stock_scored_news_min_impact_score = 0.1
    stock_scored_news_positive_sentiment_threshold = 0.2
    stock_scored_news_negative_sentiment_threshold = -0.2


def _stock(code="005930", name="삼성전자"):
    return StockInfo(
        code=code,
        name=name,
        price=70000,
        change_pct=0.0,
        volume=1000,
        volume_ratio=1.0,
        market_cap=1_000_000_000_000,
        trade_value=1_000_000_000,
        turnover=0.01,
    )


def _fields(**overrides):
    base = {
        "news_id": "marketaux_1",
        "category": "corporate",
        "sentiment": "0.45",
        "impact_score": "0.35",
        "direction_bias": "long",
        "confidence": "0.8",
        "keywords_json": json.dumps(["AI", "earnings"]),
        "reasoning": "삼성전자 AI 수요 긍정",
        "raw_source": "marketaux",
        "raw_title": "Samsung Electronics shares rise on AI demand",
        "raw_url": "https://example.com/1",
        "raw_published_at_ms": str(int(time.time() * 1000)),
        "raw_keywords_json": json.dumps(["005930.KS", "삼성전자"]),
    }
    base.update(overrides)
    return base


def test_collect_scored_news_groups_marketaux_items_by_stock():
    redis = _FakeRedis([("1-0", _fields())])

    grouped = collect_scored_news_for_stocks([_stock()], _Config(), redis_client=redis)

    assert list(grouped) == ["005930"]
    item = grouped["005930"][0]
    assert item["source"] == "marketaux"
    assert item["title"].startswith("Samsung Electronics")
    assert item["impact_score"] == 0.35
    assert "005930.KS" in item["raw_keywords"]


def test_collect_scored_news_filters_source_and_impact():
    redis = _FakeRedis(
        [
            ("1-0", _fields(news_id="marketaux_low", impact_score="0.01")),
            ("2-0", _fields(news_id="gdelt_1", raw_source="gdelt")),
        ]
    )

    grouped = collect_scored_news_for_stocks([_stock()], _Config(), redis_client=redis)

    assert grouped == {}


def test_collect_scored_news_uses_scored_at_when_raw_timestamp_missing():
    redis = _FakeRedis(
        [
            (
                "1-0",
                _fields(
                    raw_published_at_ms="0",
                    scored_at_ms=str(int(time.time() * 1000)),
                ),
            )
        ]
    )

    grouped = collect_scored_news_for_stocks([_stock()], _Config(), redis_client=redis)

    assert grouped["005930"][0]["published_at_ms"] > 0


def test_summarize_scored_news_sentiment_uses_weighted_average():
    assert summarize_scored_news_sentiment([_fields()], _Config()) == "긍정"
    assert (
        summarize_scored_news_sentiment([_fields(sentiment="-0.5")], _Config())
        == "부정"
    )
