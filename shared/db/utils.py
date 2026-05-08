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

    Uses the native protocol (clickhouse_driver) on CLICKHOUSE_NATIVE_PORT.
    Falls back to CLICKHOUSE_PORT, but if that resolves to 8123 (the HTTP
    port that some deployments set in .env), uses 9000 instead so the
    native driver doesn't try to speak its protocol on the HTTP port.
    Mirrors the resolution in ``shared/db/config.py::from_env``.

    The password default is an empty string — never a hardcoded credential.

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

    # Mirror the port-resolution logic in shared/db/config.py::from_env so
    # both helpers behave the same way.  In this repo CLICKHOUSE_PORT is
    # often set to the HTTP port (8123); the native driver needs 9000.
    raw_native_port = os.getenv("CLICKHOUSE_NATIVE_PORT")
    if raw_native_port:
        port = int(raw_native_port)
    else:
        http_port = int(os.getenv("CLICKHOUSE_PORT", "9000"))
        port = 9000 if http_port == 8123 else http_port

    return clickhouse_driver.Client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=port,
        user=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        database=database,
    )
