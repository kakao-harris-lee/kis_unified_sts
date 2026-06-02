"""Pydantic config models for news collector."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, Field

from shared.config.base import ServiceConfigBase


class DedupeConfig(BaseModel):
    memory_size: int = Field(default=20000, gt=0)
    redis_ttl_days: int = Field(default=7, gt=0)


class SourceCommon(BaseModel):
    enabled: bool = True
    poll_interval_seconds: int = Field(default=60, gt=0)


class DartSourceConfig(SourceCommon):
    lookback_days: int = Field(default=3, ge=0)
    page_count: int = Field(default=100, gt=0, le=100)


class GDELTSourceConfig(SourceCommon):
    enabled: bool = False
    poll_interval_seconds: int = Field(default=600, gt=0)
    query: str = (
        '("Federal Reserve" OR "bond yields" OR "equity market" OR '
        '"semiconductor stocks")'
    )
    max_records: int = Field(default=20, gt=0, le=100)
    timespan: str = "6h"
    sort: str = "datedesc"
    timeout_seconds: float = Field(default=20.0, gt=0)


class MarketauxSourceConfig(SourceCommon):
    enabled: bool = False
    poll_interval_seconds: int = Field(default=600, gt=0)
    api_token: str = ""
    endpoint: str = "https://api.marketaux.com/v1/news/all"
    limit: int = Field(default=20, gt=0, le=100)
    language: str = "en,ko"
    countries: str = "us,kr"
    symbols: str = ""
    entity_types: str = "equity,index"
    industries: str = ""
    search: str = ""
    domains: str = ""
    exclude_domains: str = ""
    filter_entities: bool = True
    must_have_entities: bool = False
    group_similar: bool = True
    published_after_minutes: int = Field(default=720, ge=0)
    timeout_seconds: float = Field(default=20.0, gt=0)


class NaverNewsSearchSourceConfig(SourceCommon):
    enabled: bool = False
    poll_interval_seconds: int = Field(default=300, gt=0)
    client_id: str = ""
    client_secret: str = ""
    endpoint: str = "https://openapi.naver.com/v1/search/news.json"
    queries: list[str] = Field(
        default_factory=lambda: [
            "인포스탁 개장전 주요이슈 점검",
            "인포스탁 테마별 등락율 순위",
            "개장전 주요이슈 점검",
            "테마별 등락율 순위",
        ]
    )
    display: int = Field(default=10, ge=1, le=100)
    sort: Literal["sim", "date"] = "date"
    timeout_seconds: float = Field(default=10.0, gt=0)


class GenericRSSFeedConfig(SourceCommon):
    name: str
    rss_url: str
    lang: str = "ko"
    version: str | None = None
    timeout_seconds: float = Field(default=10.0, gt=0)


class YonhapSourceConfig(SourceCommon):
    rss_url: str


class ReutersSourceConfig(SourceCommon):
    rss_url: str


class MKSourceConfig(SourceCommon):
    mode: str = "adapter"


class SourcesConfig(BaseModel):
    dart: DartSourceConfig
    gdelt: GDELTSourceConfig = Field(default_factory=GDELTSourceConfig)
    marketaux: MarketauxSourceConfig = Field(default_factory=MarketauxSourceConfig)
    naver_search: NaverNewsSearchSourceConfig = Field(
        default_factory=NaverNewsSearchSourceConfig
    )
    yonhap: YonhapSourceConfig
    reuters: ReutersSourceConfig
    mk: MKSourceConfig
    rss_feeds: list[GenericRSSFeedConfig] = Field(default_factory=list)


class NewsCollectorConfig(ServiceConfigBase):
    _default_config_file: ClassVar[str] = "news_sources.yaml"
    _default_section: ClassVar[str] = "news_collector"

    redis_stream: str
    redis_maxlen: int = Field(default=100000, gt=0)
    clickhouse_batch_size: int = Field(default=50, gt=0)
    clickhouse_flush_interval_seconds: int = Field(default=10, gt=0)
    body_truncate_chars: int = Field(default=2000, gt=0)
    dedupe: DedupeConfig
    sources: SourcesConfig
