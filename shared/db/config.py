"""ClickHouse configuration."""
import os

from pydantic import Field

from shared.config.base import ServiceConfigBase


class ClickHouseConfig(ServiceConfigBase):
    """ClickHouse connection configuration.

    Inherits database name validation from ServiceConfigBase.
    Provides custom from_env() method with specialized port handling logic.
    """

    # Class-level defaults for ServiceConfigBase
    _env_prefix = "CLICKHOUSE_"

    host: str = Field(default="localhost", description="ClickHouse host")
    port: int = Field(default=9000, description="ClickHouse native port")
    http_port: int = Field(default=8123, description="ClickHouse HTTP port")
    user: str = Field(default="default", description="Username")
    password: str = Field(default="", description="Password")
    database: str = Field(default="market", description="Database name")

    # Connection pool settings
    pool_size: int = Field(default=5, description="Connection pool size")
    connect_timeout: int = Field(default=10, description="Connection timeout seconds")

    # TCP keepalive settings — keep the idle native connection alive so the
    # server/NAT does not reap it after ~1h of inactivity (which surfaces as a
    # noisy transparent reconnect WARNING on the next query).
    tcp_keepalive: bool = Field(
        default=True, description="Enable TCP keepalive on the native connection"
    )
    tcp_keepalive_idle: int = Field(
        default=60, description="Seconds idle before the first keepalive probe"
    )
    tcp_keepalive_interval: int = Field(
        default=15, description="Seconds between keepalive probes"
    )
    tcp_keepalive_count: int = Field(
        default=4, description="Failed probes before dropping the connection"
    )

    # TLS/SSL settings
    secure: bool = Field(default=False, description="Enable TLS/SSL connection")
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")
    ca_cert: str | None = Field(default=None, description="Path to CA certificate file")
    client_cert: str | None = Field(
        default=None, description="Path to client certificate file (for mutual TLS)"
    )
    client_key: str | None = Field(
        default=None, description="Path to client key file (for mutual TLS)"
    )

    @classmethod
    def from_env(cls, database: str | None = None) -> "ClickHouseConfig":
        """Create config from environment variables.

        Args:
            database: Optional database name override. If not provided,
                      uses CLICKHOUSE_STOCK_DATABASE env var or "market" default.

        Returns:
            ClickHouseConfig instance with values from environment

        Note:
            This method has custom port handling logic:
            - CLICKHOUSE_PORT is typically the HTTP port (8123)
            - CLICKHOUSE_NATIVE_PORT is the native protocol port (9000)
            - If native port is not set, defaults to 9000 when HTTP port is 8123

            TLS environment variables:
            - CLICKHOUSE_SECURE: Enable TLS (true/false)
            - CLICKHOUSE_VERIFY_SSL: Verify SSL certificates (true/false)
            - CLICKHOUSE_CA_CERT: Path to CA certificate
            - CLICKHOUSE_CLIENT_CERT: Path to client certificate (mutual TLS)
            - CLICKHOUSE_CLIENT_KEY: Path to client key (mutual TLS)
        """
        http_port = int(os.environ.get("CLICKHOUSE_PORT", "8123"))
        raw_native_port = os.environ.get("CLICKHOUSE_NATIVE_PORT")
        if raw_native_port:
            native_port = int(raw_native_port)
        else:
            # In this repo, CLICKHOUSE_PORT is often used as HTTP port (8123).
            # Keep native protocol default on 9000 unless an explicit native port is provided.
            native_port = 9000 if http_port == 8123 else http_port

        # Parse boolean TLS settings
        secure = os.environ.get("CLICKHOUSE_SECURE", "false").lower() in (
            "true",
            "1",
            "yes",
        )
        verify_ssl = os.environ.get("CLICKHOUSE_VERIFY_SSL", "true").lower() in (
            "true",
            "1",
            "yes",
        )

        tcp_keepalive = os.environ.get("CLICKHOUSE_TCP_KEEPALIVE", "true").lower() in (
            "true",
            "1",
            "yes",
        )

        return cls(
            host=os.environ.get("CLICKHOUSE_HOST", "localhost"),
            port=native_port,
            http_port=http_port,
            user=os.environ.get("CLICKHOUSE_USER", "default"),
            password=os.environ.get("CLICKHOUSE_PASSWORD", ""),
            database=database or os.environ.get("CLICKHOUSE_STOCK_DATABASE", "market"),
            secure=secure,
            verify_ssl=verify_ssl,
            ca_cert=os.environ.get("CLICKHOUSE_CA_CERT"),
            client_cert=os.environ.get("CLICKHOUSE_CLIENT_CERT"),
            client_key=os.environ.get("CLICKHOUSE_CLIENT_KEY"),
            tcp_keepalive=tcp_keepalive,
            tcp_keepalive_idle=int(
                os.environ.get("CLICKHOUSE_TCP_KEEPALIVE_IDLE", "60")
            ),
            tcp_keepalive_interval=int(
                os.environ.get("CLICKHOUSE_TCP_KEEPALIVE_INTERVAL", "15")
            ),
            tcp_keepalive_count=int(
                os.environ.get("CLICKHOUSE_TCP_KEEPALIVE_COUNT", "4")
            ),
        )

    def __str__(self) -> str:
        protocol = "clickhouses" if self.secure else "clickhouse"
        return f"{protocol}://{self.user}@{self.host}:{self.port}/{self.database}"
