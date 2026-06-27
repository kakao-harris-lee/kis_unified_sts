"""Removed database configuration compatibility module."""

from __future__ import annotations

from pydantic import BaseModel


class ClickHouseConfig(BaseModel):
    """Compatibility stub for removed ClickHouse configuration."""

    database: str = "market"

    @classmethod
    def from_env(cls, database: str | None = None) -> ClickHouseConfig:
        return cls(database=database or "market")

    def __str__(self) -> str:
        return "clickhouse-removed"
