"""Runtime and market-data storage configuration.

This module is the configuration entry point for the runtime storage
decoupling work. It intentionally does not import ClickHouse clients; it only
describes which storage backend should be selected by factories/call sites.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field, field_validator

from shared.config.base import ServiceConfigBase
from shared.config.loader import ConfigNotFoundError

RuntimeStorageBackend = Literal["sqlite", "clickhouse", "null"]
MarketDataSource = Literal["parquet", "clickhouse"]
DashboardTradeStatsSource = Literal["runtime_ledger", "clickhouse"]


def _env_bool(name: str) -> bool | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return None
    return value.lower() in ("true", "1", "yes", "on")


_EMBEDDED_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::([^}]*))?\}")


def _resolve_embedded_env(value: str) -> str:
    """Resolve embedded ${VAR} / ${VAR:default} fragments in storage paths."""

    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        default = match.group(2) if match.group(2) is not None else ""
        return os.environ.get(name, default)

    return _EMBEDDED_ENV_PATTERN.sub(_replace, value)


class SQLiteStorageConfig(BaseModel):
    """SQLite runtime ledger settings."""

    path: str = Field(
        default="data/runtime/dev/runtime.db",
        description="SQLite runtime ledger path",
    )
    wal: bool = Field(default=True, description="Enable WAL journal mode")
    busy_timeout_ms: int = Field(
        default=5000,
        ge=0,
        description="SQLite busy timeout in milliseconds",
    )
    synchronous: Literal["OFF", "NORMAL", "FULL", "EXTRA"] = Field(
        default="NORMAL",
        description="SQLite synchronous pragma",
    )

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        path = str(value).strip()
        if not path:
            raise ValueError("sqlite.path must not be empty")
        return path

    @field_validator("synchronous", mode="before")
    @classmethod
    def _normalize_synchronous(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.upper()
        return value


class ClickHouseMirrorConfig(BaseModel):
    """Best-effort ClickHouse runtime mirror settings."""

    enabled: bool = Field(
        default=False,
        description="Mirror runtime ledger writes to ClickHouse best-effort",
    )
    database: str = Field(default="market", description="ClickHouse mirror database")


class RuntimeStorageConfig(BaseModel):
    """Runtime durable ledger backend selection."""

    backend: RuntimeStorageBackend = Field(
        default="sqlite",
        description="Primary runtime ledger backend",
    )
    sqlite: SQLiteStorageConfig = Field(default_factory=SQLiteStorageConfig)
    clickhouse_mirror: ClickHouseMirrorConfig = Field(
        default_factory=ClickHouseMirrorConfig
    )


class ParquetMarketDataConfig(BaseModel):
    """Parquet/DuckDB research data root."""

    root: str = Field(default="data/market", description="Market-data parquet root")

    @field_validator("root")
    @classmethod
    def _validate_root(cls, value: str) -> str:
        root = str(value).strip()
        if not root:
            raise ValueError("parquet.root must not be empty")
        return root


class ClickHouseMarketDataConfig(BaseModel):
    """Optional ClickHouse historical market-data source."""

    enabled: bool = Field(default=False, description="Enable ClickHouse market data")
    stock_database: str = Field(default="market", description="Stock database")
    futures_database: str = Field(default="kospi", description="Futures database")


class MarketDataStorageConfig(BaseModel):
    """Historical market-data backend selection."""

    source: MarketDataSource = Field(
        default="parquet",
        description="Historical market-data source",
    )
    parquet: ParquetMarketDataConfig = Field(default_factory=ParquetMarketDataConfig)
    clickhouse: ClickHouseMarketDataConfig = Field(
        default_factory=ClickHouseMarketDataConfig
    )


class DashboardStorageConfig(BaseModel):
    """Dashboard storage/read-source selection."""

    trade_stats_source: DashboardTradeStatsSource = Field(
        default="runtime_ledger",
        description="Primary source for dashboard trade statistics",
    )


class StorageConfig(ServiceConfigBase):
    """Top-level storage configuration loaded from ``config/storage.yaml``."""

    _default_config_file: ClassVar[str] = "storage.yaml"

    runtime_storage: RuntimeStorageConfig = Field(default_factory=RuntimeStorageConfig)
    market_data: MarketDataStorageConfig = Field(
        default_factory=MarketDataStorageConfig
    )
    dashboard: DashboardStorageConfig = Field(default_factory=DashboardStorageConfig)

    @classmethod
    def from_yaml(
        cls,
        path: str | None = None,
        section: str | None = None,
        *,
        sections: list[str] | None = None,
        apply_env_overrides: bool = True,
        env_prefix: str | None = None,
    ) -> StorageConfig:
        """Load storage config, applying explicit nested env overrides by default."""
        config = super().from_yaml(
            path=path,
            section=section,
            sections=sections,
            apply_env_overrides=False,
            env_prefix=env_prefix,
        )
        if apply_env_overrides:
            config.apply_env_overrides()
        return config

    @classmethod
    def load_or_default(cls, path: str | None = None) -> StorageConfig:
        """Load from YAML when available, otherwise return validated defaults."""
        try:
            return cls.from_yaml(path)
        except ConfigNotFoundError:
            return cls.from_env()

    @classmethod
    def from_env(cls, env_prefix: str | None = None, **overrides: Any) -> StorageConfig:
        """Create storage config from supported environment variables."""
        _ = env_prefix
        config = cls(**overrides)
        config.apply_env_overrides()
        return config

    def apply_env_overrides(self) -> None:
        """Apply nested storage env vars.

        ServiceConfigBase's generic env loader maps flat top-level fields only.
        Storage config is deliberately nested, so the few operator-facing
        overrides are handled explicitly here.
        """
        if backend := os.environ.get("RUNTIME_STORAGE_BACKEND"):
            self.runtime_storage.backend = backend.lower()  # type: ignore[assignment]

        if sqlite_path := os.environ.get("RUNTIME_STORAGE_SQLITE_PATH"):
            self.runtime_storage.sqlite.path = sqlite_path

        sqlite_wal = _env_bool("RUNTIME_STORAGE_SQLITE_WAL")
        if sqlite_wal is not None:
            self.runtime_storage.sqlite.wal = sqlite_wal

        if busy_timeout := os.environ.get("RUNTIME_STORAGE_SQLITE_BUSY_TIMEOUT_MS"):
            self.runtime_storage.sqlite.busy_timeout_ms = int(busy_timeout)

        if synchronous := os.environ.get("RUNTIME_STORAGE_SQLITE_SYNCHRONOUS"):
            self.runtime_storage.sqlite.synchronous = synchronous.upper()  # type: ignore[assignment]

        mirror_enabled = _env_bool("RUNTIME_STORAGE_CLICKHOUSE_MIRROR_ENABLED")
        if mirror_enabled is None:
            mirror_enabled = _env_bool("CLICKHOUSE_MIRROR_ENABLED")
        if mirror_enabled is not None:
            self.runtime_storage.clickhouse_mirror.enabled = mirror_enabled

        if mirror_database := os.environ.get("RUNTIME_STORAGE_CLICKHOUSE_DATABASE"):
            self.runtime_storage.clickhouse_mirror.database = mirror_database

        if source := os.environ.get("MARKET_DATA_SOURCE"):
            self.market_data.source = source.lower()  # type: ignore[assignment]

        if parquet_root := os.environ.get("MARKET_DATA_PARQUET_ROOT"):
            self.market_data.parquet.root = parquet_root

        clickhouse_enabled = _env_bool("MARKET_DATA_CLICKHOUSE_ENABLED")
        if clickhouse_enabled is not None:
            self.market_data.clickhouse.enabled = clickhouse_enabled

        if stock_db := os.environ.get("MARKET_DATA_CLICKHOUSE_STOCK_DATABASE"):
            self.market_data.clickhouse.stock_database = stock_db

        if futures_db := os.environ.get("MARKET_DATA_CLICKHOUSE_FUTURES_DATABASE"):
            self.market_data.clickhouse.futures_database = futures_db

        if trade_stats_source := os.environ.get("DASHBOARD_TRADE_STATS_SOURCE"):
            self.dashboard.trade_stats_source = trade_stats_source.lower()  # type: ignore[assignment]

        self.runtime_storage.sqlite.path = _resolve_embedded_env(
            self.runtime_storage.sqlite.path
        )
        self.market_data.parquet.root = _resolve_embedded_env(
            self.market_data.parquet.root
        )

        # Re-validate mutated nested models so assignment coercion and Literal
        # constraints are enforced consistently.
        validated = self.__class__.model_validate(self.model_dump())
        self.runtime_storage = validated.runtime_storage
        self.market_data = validated.market_data
        self.dashboard = validated.dashboard

    @property
    def runtime_sqlite_path(self) -> Path:
        """Runtime SQLite path as a Path object."""
        return Path(self.runtime_storage.sqlite.path)
