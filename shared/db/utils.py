"""Removed database helper compatibility module."""

from __future__ import annotations

from typing import Any

from shared.db.client import ClickHouseRemovedError


def clickhouse_client_from_env(*, database: str) -> Any:
    """Compatibility helper that always fails."""
    _ = database
    raise ClickHouseRemovedError(
        "ClickHouse client support has been removed; use RuntimeLedger/Parquet"
    )
