"""Removed database client compatibility module.

ClickHouse is no longer a supported runtime or research dependency. New code
must use ``shared.storage.runtime_ledger`` for operational records and
``shared.storage.market_data_store`` for Parquet market data.
"""

from __future__ import annotations


class ClickHouseRemovedError(RuntimeError):
    """Raised when legacy ClickHouse client code is invoked."""


SCHEMAS: dict[str, str] = {}
HAS_ASYNC = False
SyncClient = object


class ClickHouseClient:
    """Compatibility stub for removed ClickHouse client API."""

    def __init__(self, *_args, **_kwargs):
        raise ClickHouseRemovedError(
            "ClickHouse client support has been removed; use RuntimeLedger/Parquet"
        )

    @classmethod
    def reset_singleton(cls) -> None:
        return None


class AsyncClickHouseClient:
    """Compatibility stub for removed async ClickHouse client API."""

    def __init__(self, *_args, **_kwargs):
        raise ClickHouseRemovedError(
            "ClickHouse client support has been removed; use RuntimeLedger/Parquet"
        )


def get_clickhouse_client(*_args, **_kwargs) -> ClickHouseClient:
    """Compatibility factory that always fails."""
    raise ClickHouseRemovedError(
        "ClickHouse client support has been removed; use RuntimeLedger/Parquet"
    )
