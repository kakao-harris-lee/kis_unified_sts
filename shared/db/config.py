"""ClickHouse configuration."""
import os
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClickHouseConfig(BaseModel):
    """ClickHouse connection configuration."""

    model_config = ConfigDict(frozen=True)

    host: str = Field(default="localhost", description="ClickHouse host")
    port: int = Field(default=9000, description="ClickHouse native port")
    http_port: int = Field(default=8123, description="ClickHouse HTTP port")
    user: str = Field(default="default", description="Username")
    password: str = Field(default="", description="Password")
    database: str = Field(default="market", description="Database name")

    @field_validator("database")
    @classmethod
    def validate_database_name(cls, v: str) -> str:
        """Validate database name to prevent SQL injection in DDL."""
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError(
                "Database name must contain only alphanumeric characters and underscores"
            )
        return v

    # Connection pool settings
    pool_size: int = Field(default=5, description="Connection pool size")
    connect_timeout: int = Field(default=10, description="Connection timeout seconds")

    @classmethod
    def from_env(cls, database: str | None = None) -> "ClickHouseConfig":
        """Create config from environment variables."""
        return cls(
            host=os.environ.get("CLICKHOUSE_HOST", "localhost"),
            port=int(os.environ.get("CLICKHOUSE_PORT", "9000")),
            user=os.environ.get("CLICKHOUSE_USER", "default"),
            password=os.environ.get("CLICKHOUSE_PASSWORD", ""),
            database=database or os.environ.get("CLICKHOUSE_STOCK_DATABASE", "market"),
        )

    def __str__(self) -> str:
        return f"ClickHouse({self.user}@{self.host}:{self.port}/{self.database})"
