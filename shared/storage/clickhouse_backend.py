"""ClickHouse backend wiring for optional storage paths.

Runtime services should not import ClickHouse drivers directly. They can call
these helpers only when an explicit storage config enables a ClickHouse mirror
or analytics backend.
"""

from __future__ import annotations

from typing import Any


def create_sync_clickhouse_client(database: str | None = None) -> Any:
    """Create a native synchronous ClickHouse client from environment config."""
    from clickhouse_driver import Client as CHSyncClient

    from shared.db.config import ClickHouseConfig

    cfg = ClickHouseConfig.from_env(database=database)
    return CHSyncClient(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        database=cfg.database,
    )


def create_sync_clickhouse_client_from_url(connection_string: str) -> Any:
    """Create a synchronous ClickHouse client from a connection URL."""
    from clickhouse_driver import Client as CHSyncClient

    return CHSyncClient.from_url(connection_string)


async def create_async_clickhouse_client(database: str | None = None) -> Any:
    """Create and connect an asynchronous ClickHouse client."""
    from shared.db.client import AsyncClickHouseClient
    from shared.db.config import ClickHouseConfig

    client = AsyncClickHouseClient(ClickHouseConfig.from_env(database=database))
    await client.connect()
    return client


def create_clickhouse_client_wrapper(config_or_database: Any | None = None) -> Any:
    """Create the legacy ClickHouseClient wrapper for backend-only callers."""
    from shared.db.client import ClickHouseClient
    from shared.db.config import ClickHouseConfig

    if isinstance(config_or_database, str) or config_or_database is None:
        config = ClickHouseConfig.from_env(database=config_or_database)
    else:
        config = config_or_database
    return ClickHouseClient(config)


def get_clickhouse_client_wrapper(database: str | None = None) -> Any:
    """Return the legacy singleton wrapper bound to a database."""
    from shared.db.client import get_clickhouse_client
    from shared.db.config import ClickHouseConfig

    return get_clickhouse_client(ClickHouseConfig.from_env(database=database))
