"""Metrics API endpoints for dashboard."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from fastapi import APIRouter

router = APIRouter()
logger = logging.getLogger(__name__)


def _empty_venue_metrics() -> Dict[str, Any]:
    """Return empty venue metrics payload.

    The frontend expects these exact keys.
    """
    return {
        "krx_count": 0,
        "ats_count": 0,
        "krx_fill_rate": 0.0,
        "ats_fill_rate": 0.0,
        "avg_price_improvement_bps": 0.0,
        "ats_price_improvement_bps": 0.0,
    }


def _normalize_database_name(database: str) -> str:
    """Validate ClickHouse database identifier."""
    normalized = str(database or "").strip()
    if not normalized:
        raise ValueError("Database name must be non-empty")
    if not normalized.replace("_", "").isalnum():
        raise ValueError(f"Invalid database name: {database!r}")
    return normalized


def _candidate_databases() -> list[str]:
    """Return unique ClickHouse databases that may contain trading data."""
    from shared.config.secrets import SecretsManager

    candidates = [
        SecretsManager.clickhouse_database("stock"),
        SecretsManager.clickhouse_database("futures"),
        SecretsManager.clickhouse_database(),
    ]

    unique: list[str] = []
    seen: set[str] = set()
    for database in candidates:
        try:
            normalized = _normalize_database_name(database)
        except ValueError:
            continue
        if normalized not in seen:
            unique.append(normalized)
            seen.add(normalized)
    return unique


def _query_venue_counts_for_database(database: str) -> dict[str, int]:
    """Query execution venue counts for one ClickHouse database.

    Aggregates both RL closed trades and closed swing positions when those
    tables exist. Missing tables are ignored gracefully.
    """
    from clickhouse_driver import Client as SyncClient

    from shared.db.config import ClickHouseConfig

    database = _normalize_database_name(database)
    cfg = ClickHouseConfig.from_env(database=database)
    client = SyncClient(host=cfg.host, port=cfg.port, user=cfg.user, password=cfg.password)

    try:
        table_rows = client.execute(
            "SELECT name FROM system.tables "
            "WHERE database = %(database)s AND name IN ('rl_trades', 'swing_positions')",
            {"database": database},
        )
        available_tables = {str(row[0]) for row in table_rows}
        if not available_tables:
            return {"KRX": 0, "ATS": 0}

        subqueries: list[str] = []
        if "rl_trades" in available_tables:
            subqueries.append(
                f"SELECT execution_venue FROM {database}.rl_trades"
            )
        if "swing_positions" in available_tables:
            subqueries.append(
                f"SELECT execution_venue FROM {database}.swing_positions WHERE is_open = 0"
            )

        if not subqueries:
            return {"KRX": 0, "ATS": 0}

        sql = (
            "SELECT upper(ifNull(execution_venue, 'KRX')) AS venue, count() AS trade_count "
            f"FROM ({' UNION ALL '.join(subqueries)}) "
            "GROUP BY venue"
        )
        rows = client.execute(sql)

        counts = {"KRX": 0, "ATS": 0}
        for venue, trade_count in rows:
            normalized_venue = str(venue or "KRX").upper()
            if normalized_venue in counts:
                counts[normalized_venue] += int(trade_count or 0)
        return counts
    finally:
        client.disconnect()


def _collect_venue_metrics_sync() -> Dict[str, Any]:
    """Collect venue metrics from ClickHouse.

    Only persisted execution venue counts are currently stored durably.
    Fill-rate and price-improvement values degrade gracefully until those
    inputs are persisted or queried from Prometheus.
    """
    metrics = _empty_venue_metrics()

    total_counts = {"KRX": 0, "ATS": 0}
    for database in _candidate_databases():
        try:
            db_counts = _query_venue_counts_for_database(database)
        except Exception as e:
            logger.warning("Failed to query venue counts for database %s: %s", database, e)
            continue
        total_counts["KRX"] += db_counts.get("KRX", 0)
        total_counts["ATS"] += db_counts.get("ATS", 0)

    metrics["krx_count"] = total_counts["KRX"]
    metrics["ats_count"] = total_counts["ATS"]

    # Persisted trade tables only contain executed fills, so completed-trade
    # fill rate is 1.0 when any venue-specific executions exist. We keep price
    # improvement at 0.0 until that metric is durably stored.
    metrics["krx_fill_rate"] = 1.0 if total_counts["KRX"] > 0 else 0.0
    metrics["ats_fill_rate"] = 1.0 if total_counts["ATS"] > 0 else 0.0
    return metrics


@router.get("/api/metrics/venue")
async def get_venue_metrics() -> Dict[str, Any]:
    """
    Get execution venue distribution and performance metrics.

    Returns venue statistics for monitoring ATS vs KRX routing effectiveness.

    Returns:
        Dict containing:
        - krx_count: Number of orders routed to KRX
        - ats_count: Number of orders routed to ATS
        - krx_fill_rate: Fill rate for KRX orders (0.0-1.0)
        - ats_fill_rate: Fill rate for ATS orders (0.0-1.0)
        - avg_price_improvement_bps: Average price improvement across all venues (basis points)
        - ats_price_improvement_bps: ATS-specific price improvement (basis points)
    """
    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _collect_venue_metrics_sync)
    except Exception as e:
        logger.error(f"Error fetching venue metrics: {e}")
        # Return zeros on error to prevent dashboard crash
        return _empty_venue_metrics()
