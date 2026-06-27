from dataclasses import FrozenInstanceError

import pytest

from shared.news.base import NewsItem, NewsSource


def test_news_item_construction():
    item = NewsItem(
        news_id="dart_001",
        source="dart",
        published_at_ms=1_700_000_000_000,
        received_at_ms=1_700_000_001_000,
        title="title",
        body="body",
        url="https://example.com/1",
        source_version="dart-v1",
        lang="ko",
        keywords=["공시"],
    )
    assert item.news_id == "dart_001"
    assert item.keywords == ["공시"]


def test_news_item_is_frozen():
    item = NewsItem(
        news_id="x",
        source="y",
        published_at_ms=0,
        received_at_ms=0,
        title="",
        body="",
        url="",
        source_version="",
        lang="ko",
        keywords=[],
    )
    with pytest.raises(FrozenInstanceError):
        item.title = "changed"  # type: ignore[misc]


def test_news_item_to_stream_fields_are_strings():
    item = NewsItem(
        news_id="x",
        source="y",
        published_at_ms=1000,
        received_at_ms=2000,
        title="T",
        body="B" * 3000,
        url="u",
        source_version="v",
        lang="ko",
        keywords=["a", "b"],
    )
    d = item.to_stream_dict(max_body_chars=2000)
    assert d["news_id"] == "x"
    assert len(d["body"]) <= 2000 + len("...[truncated]")
    assert d["body"].endswith("...[truncated]")
    # published/received as ms integers (kept as-is; publisher converts to str)
    assert d["published_at_ms"] == 1000


def test_news_source_is_abstract():
    with pytest.raises(TypeError):
        NewsSource()  # type: ignore[abstract]
