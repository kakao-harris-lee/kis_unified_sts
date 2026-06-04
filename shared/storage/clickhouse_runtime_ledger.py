"""ClickHouse runtime persistence helpers.

This module contains the ClickHouse-specific client wiring for legacy runtime
position persistence. Runtime services should depend on the RuntimeLedger
interface or on PositionTracker methods, not import ClickHouse clients
directly.
"""

from __future__ import annotations


def get_clickhouse_db_client(database_override: str = "") -> tuple[object, str]:
    """Return a ClickHouse client and validated database name."""
    from shared.db.client import ClickHouseClient
    from shared.db.config import ClickHouseConfig

    cfg = ClickHouseConfig.from_env(database=database_override or None)
    ch = ClickHouseClient(cfg)
    database = database_override if database_override else cfg.database
    if not database.replace("_", "").isalnum():
        raise ValueError(f"Invalid database name: {database}")
    return ch, database
