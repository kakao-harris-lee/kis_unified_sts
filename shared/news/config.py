"""Pydantic config models for news collector."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field

from shared.config.base import ServiceConfigBase


class DedupeConfig(BaseModel):
    memory_size: int = Field(default=20000, gt=0)
    redis_ttl_days: int = Field(default=7, gt=0)


class SourceCommon(BaseModel):
    enabled: bool = True
    poll_interval_seconds: int = Field(default=60, gt=0)


class DartSourceConfig(SourceCommon):
    pass


class YonhapSourceConfig(SourceCommon):
    rss_url: str


class ReutersSourceConfig(SourceCommon):
    rss_url: str


class MKSourceConfig(SourceCommon):
    mode: str = "adapter"


class SourcesConfig(BaseModel):
    dart: DartSourceConfig
    yonhap: YonhapSourceConfig
    reuters: ReutersSourceConfig
    mk: MKSourceConfig


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
