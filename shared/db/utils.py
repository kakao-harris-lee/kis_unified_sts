"""Shared ClickHouse helpers for analysis scripts.

Centralizes connection construction so scripts do not duplicate env-var
handling or hardcode fallback credentials. All values come from env; no
defaults for secrets.
"""
from __future__ import annotations

import os
from typing import Any


def clickhouse_client_from_env(*, database: str) -> Any:
    """Construct a clickhouse_driver.Client using CLICKHOUSE_* env vars.

    Uses the native protocol (clickhouse_driver) on CLICKHOUSE_NATIVE_PORT
    (falling back to CLICKHOUSE_PORT, default 9000).  The password default
    is an empty string — never a hardcoded credential.

    Args:
        database: ClickHouse database to connect to (required).

    Returns:
        clickhouse_driver.Client ready to execute queries.

    Raises:
        ValueError: if database is empty.
        ImportError: if clickhouse_driver is not installed.
    """
    if not database:
        raise ValueError("database is required (non-empty)")

    import clickhouse_driver

    port_str = os.getenv(
        "CLICKHOUSE_NATIVE_PORT",
        os.getenv("CLICKHOUSE_PORT", "9000"),
    )

    return clickhouse_driver.Client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(port_str),
        user=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        database=database,
    )
